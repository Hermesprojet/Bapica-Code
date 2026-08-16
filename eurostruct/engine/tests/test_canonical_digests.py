"""Jalon 6.2 — canonicalisation et empreintes.

Deux familles de tests, et il faut les deux :

**Stabilité** — ce qui n'a aucun effet normatif ne doit pas changer l'empreinte.
Sinon les vérificateurs re-signent pour un reformatage, et la signature perd
son sens à force d'être demandée.

**Sensibilité** — toute modification normative doit la changer. C'est la
propriété qui empêche qu'une règle fausse reste ``strict-ready``.

Une seule des deux ne suffirait pas : une fonction constante serait
parfaitement stable, et un horodatage parfaitement sensible.
"""

from __future__ import annotations

import dataclasses
import unicodedata

import pytest

from eurostruct_engine.ndp import canonical as C
from eurostruct_engine.ndp import rules_be_ec2 as R
from eurostruct_engine.ndp.canonical import (
    ALLOWED_EXCEPTIONS,
    ALLOWED_EXTERNAL_SYMBOLS,
    CANONICALIZATION_VERSION,
    KERNEL_ALLOWED_SYMBOLS,
    Digest,
    EvidenceItem,
    UnresolvableDependency,
    canonical_json,
    digest_of,
    evaluation_kernel_digest,
    evidence_digest,
    implementation_digest,
    normative_spec_digest,
)
from eurostruct_engine.ndp.rules import (
    RuleImplementationMissing,
    RuleKind,
    all_rules,
)
from eurostruct_engine.units import Q_, Quantity

REGLES_BE = (
    R.NU_STRENGTH_REDUCTION, R.ALPHA_CW, R.RHO_W_MIN,
    R.S_L_MAX, R.S_T_MAX, R.COT_THETA_MAX,
)


# ---------------------------------------------------------------------------
# Stabilité
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("regle", REGLES_BE, ids=lambda r: r.rule_id)
def test_les_empreintes_sont_reproductibles(regle) -> None:
    """Deux calculs de suite donnent le même résultat, à l'octet près.

    Un ensemble non trié, un dictionnaire non ordonné ou un flottant formaté
    par défaut suffiraient à casser cela — et la panne serait intermittente,
    donc découverte en production.
    """
    for calcul in (normative_spec_digest, implementation_digest):
        a, b = calcul(regle), calcul(regle)
        assert a.digest == b.digest
        assert a.canonical_payload == b.canonical_payload
        assert a.canonicalization_version == CANONICALIZATION_VERSION


@pytest.mark.parametrize("regle", REGLES_BE, ids=lambda r: r.rule_id)
def test_la_prose_ne_change_pas_la_specification(regle) -> None:
    """description, notes et tests sont du travail, pas de la prescription.

    Les changer ne doit rien coûter. S'ils entraient dans l'empreinte, corriger
    une faute de frappe dans un commentaire invaliderait deux signatures
    humaines.
    """
    avant = normative_spec_digest(regle)
    variante = dataclasses.replace(
        regle,
        description="AUTRE DESCRIPTION",
        notes="autres notes",
        tests=("test_invente",),
    )
    assert normative_spec_digest(variante).digest == avant.digest


def test_l_unite_d_affichage_et_la_page_pdf_ne_changent_pas_la_specification() -> None:
    """Présentation et navigation, pas prescription.

    ``page_pdf`` en particulier : il dépend du tirage du fichier, et deux
    exemplaires du même document peuvent le porter différent — c'est arrivé
    dans ce dépôt.
    """
    from eurostruct_engine.ndp.rules import InputSpec

    avant = normative_spec_digest(R.S_T_MAX)
    variante = dataclasses.replace(
        R.S_T_MAX,
        inputs=(InputSpec("d", "[length]", "Hauteur utile", "cm"),),  # display_unit
    )
    assert normative_spec_digest(variante).digest == avant.digest

    autorite = dataclasses.replace(R.S_T_MAX.normative_authority, page_pdf=999)
    assert normative_spec_digest(
        dataclasses.replace(R.S_T_MAX, normative_authority=autorite)
    ).digest == avant.digest


def test_la_citation_n_appartient_pas_a_la_specification_mais_a_la_preuve() -> None:
    """D1 arbitrée : corriger une transcription ne change pas la mathématique.

    Mais la modifier APRÈS signature doit rester détectable — d'où sa présence
    dans l'empreinte de preuve, où le test suivant la vérifie.
    """
    avant = normative_spec_digest(R.NU_STRENGTH_REDUCTION)
    autorite = dataclasses.replace(
        R.NU_STRENGTH_REDUCTION.normative_authority,
        quote="La valeur recommandee (formule 6.6N) est normative",  # point retiré
    )
    apres = normative_spec_digest(
        dataclasses.replace(R.NU_STRENGTH_REDUCTION, normative_authority=autorite)
    )
    assert apres.digest == avant.digest


# ---------------------------------------------------------------------------
# Sensibilité — spécification
# ---------------------------------------------------------------------------
def _spec_change(regle, **remplacements) -> bool:
    avant = normative_spec_digest(regle).digest
    return normative_spec_digest(
        dataclasses.replace(regle, **remplacements)
    ).digest != avant


def test_changer_une_unite_de_sortie_change_la_specification() -> None:
    assert _spec_change(R.S_T_MAX, output_unit="cm")


def test_changer_une_dimension_d_entree_change_la_specification() -> None:
    from eurostruct_engine.ndp.rules import InputSpec

    assert _spec_change(
        R.S_T_MAX,
        inputs=(InputSpec("d", "[pressure]", "Hauteur utile", "mm"),),
    )


def test_renommer_une_variable_change_la_specification() -> None:
    """Le nom d'une entrée est son contrat: l'appelant la passe par ce nom."""
    from eurostruct_engine.ndp.rules import InputSpec

    assert _spec_change(
        R.S_T_MAX,
        inputs=(InputSpec("hauteur", "[length]", "Hauteur utile", "mm"),),
    )


def test_retrecir_un_domaine_change_la_specification() -> None:
    """Un domaine plus étroit refuse ce qu'il acceptait: autre règle."""
    from eurostruct_engine.ndp.rules import DomainBound

    assert _spec_change(
        R.NU_STRENGTH_REDUCTION,
        domain=(DomainBound("f_ck", minimum=Q_(20.0, "MPa"),
                            maximum=Q_(90.0, "MPa"), reason="essai"),),
    )


def test_changer_l_unite_d_une_borne_change_la_specification() -> None:
    """12 MPa et 12000 kPa sont la même grandeur et deux DÉCLARATIONS.

    Les canonicaliser en unité de base les confondrait, et masquerait un
    changement d'unité dans une borne — ce que l'empreinte existe pour
    attraper.
    """
    from eurostruct_engine.ndp.rules import DomainBound

    assert _spec_change(
        R.NU_STRENGTH_REDUCTION,
        domain=(DomainBound("f_ck", minimum=Q_(12000.0, "kPa"),
                            maximum=Q_(90.0, "MPa"),
                            reason=R.NU_STRENGTH_REDUCTION.domain[0].reason),),
    )


def test_deplacer_une_borne_de_branche_change_la_specification() -> None:
    """0,25 f_cd déplacé en 0,30 f_cd est une autre règle nationale."""

    branches = list(R.ALPHA_CW.branches)
    branches[1] = dataclasses.replace(branches[1], upper=0.30)
    assert _spec_change(R.ALPHA_CW, branches=tuple(branches))


def test_changer_l_inclusivite_d_une_branche_change_la_specification() -> None:
    """« <= 0,25 f_cd » et « < 0,25 f_cd » ne décident pas pareil à la borne."""
    branches = list(R.ALPHA_CW.branches)
    branches[1] = dataclasses.replace(branches[1], upper_inclusive=False)
    assert _spec_change(R.ALPHA_CW, branches=tuple(branches))


def test_changer_une_valeur_de_branche_change_la_specification() -> None:
    branches = list(R.ALPHA_CW.branches)
    branches[2] = dataclasses.replace(branches[2], value_scalar=1.30)
    assert _spec_change(R.ALPHA_CW, branches=tuple(branches))


def test_changer_l_edition_de_l_autorite_change_la_specification() -> None:
    """L'édition fait l'applicabilité: 2010 et 2018 ne sont pas la même règle."""
    autorite = dataclasses.replace(R.RHO_W_MIN.normative_authority, edition="2018")
    assert _spec_change(R.RHO_W_MIN, normative_authority=autorite)


def test_changer_la_juridiction_change_la_specification() -> None:
    autorite = dataclasses.replace(R.RHO_W_MIN.normative_authority, country_code="FR")
    assert _spec_change(R.RHO_W_MIN, normative_authority=autorite)


def test_changer_un_document_source_change_la_specification() -> None:
    """Le digest du document EST la source: un autre exemplaire, une autre règle."""
    sources = list(R.RHO_W_MIN.expression_sources)
    sources[0] = dataclasses.replace(sources[0], doc_id_sha256="0" * 64)
    assert _spec_change(R.RHO_W_MIN, expression_sources=tuple(sources))


def test_changer_l_effet_d_une_couche_change_la_specification() -> None:
    """« non modifiée » et « modifiée » sont deux affirmations opposées."""
    sources = list(R.RHO_W_MIN.expression_sources)
    sources[1] = dataclasses.replace(sources[1], effect="MODIFIEE par AC:2010")
    assert _spec_change(R.RHO_W_MIN, expression_sources=tuple(sources))


def test_retirer_une_couche_de_la_pile_change_la_specification() -> None:
    """Ne plus attester que l'A1 laisse la formule intacte est un changement."""
    assert _spec_change(
        R.RHO_W_MIN, expression_sources=R.RHO_W_MIN.expression_sources[:2]
    )


def test_changer_l_ordre_d_evaluation_change_la_specification() -> None:
    """Pour une NormativeFunction, l'ordre dit COMMENT elle s'insère.

    Passer d'une vérification a posteriori à un bridage a priori change ce que
    le moteur produit, sans toucher à une seule constante.
    """
    assert _spec_change(
        R.COT_THETA_MAX,
        evaluation_order="POINT FIXE, autre strategie de reprise, budget 10.",
    )


def test_la_specification_d_un_parent_depend_des_DIGESTS_de_ses_enfants() -> None:
    """D5: les digests exacts, jamais les seuls rule_id.

    Sans cela, modifier ``alpha_cw_linear`` — la branche (1 + sigma_cp/f_cd) —
    laisserait ``alpha_cw`` confirmée alors que son résultat a changé.
    """
    import json

    payload = json.loads(normative_spec_digest(R.ALPHA_CW).canonical_payload)
    assert "__digest__" in payload["selector"]
    porteuses = [b for b in payload["branches"] if b["value_rule"] is not None]
    assert porteuses, "aucune branche ne renvoie a une regle"
    for b in porteuses:
        assert "__digest__" in b["value_rule"]
        assert len(b["value_rule"]["__digest__"]) == 64


# ---------------------------------------------------------------------------
# Sensibilité — implémentation
# ---------------------------------------------------------------------------
def test_changer_une_constante_du_calcul_change_l_implementation() -> None:
    """0,6 -> 0,61, le cas qui a motivé toute cette empreinte.

    L'extraction brute du PDF rendait « 0,61- » là où le texte donne
    0,6[1 - ...]. Si quelqu'un « corrigeait » l'implémentation dans ce sens,
    la spécification ne bougerait pas d'un octet — seule cette empreinte-ci
    le voit.
    """
    def _nu_correct(f_ck: Quantity) -> Quantity:
        fck = f_ck.to("MPa").magnitude
        return Q_(0.6 * (1.0 - fck / 250.0), "dimensionless")

    def _nu_faux(f_ck: Quantity) -> Quantity:
        fck = f_ck.to("MPa").magnitude
        return Q_(0.61 * (1.0 - fck / 250.0), "dimensionless")

    from eurostruct_engine.ndp.canonical import _closure

    a: list = []
    b: list = []
    _closure(_nu_correct, a, set())
    _closure(_nu_faux, b, set())
    assert digest_of(a).digest != digest_of(b).digest


def test_reformater_ou_commenter_ne_change_pas_l_implementation() -> None:
    """Les commentaires ne sont pas dans l'AST, l'espacement non plus.

    C'est la contrepartie du test precedent: une empreinte qui bougerait a
    chaque reformatage serait re-signee machinalement, donc sans lecture.

    Les deux variantes portent le MEME NOM, chacune dans sa portee. Le nom
    d'une fonction fait partie de son identite et entre legitimement dans
    l'empreinte; un premier jet comparait `_a` et `_b` et mesurait donc le
    renommage au lieu de la mise en forme.
    """
    from eurostruct_engine.ndp.canonical import _closure

    def serree():
        def _impl(f_ck: Quantity) -> Quantity:
            fck = f_ck.to("MPa").magnitude
            return Q_(0.6 * (1.0 - fck / 250.0), "dimensionless")

        return _impl

    def aeree():
        def _impl(f_ck: Quantity) -> Quantity:
            # Un commentaire ajoute, et l'expression ecrite sur trois lignes.
            fck = f_ck.to("MPa").magnitude

            return Q_(
                0.6 * (1.0 - fck / 250.0),
                "dimensionless",
            )

        return _impl

    a: list = []
    b: list = []
    _closure(serree(), a, set())
    _closure(aeree(), b, set())
    # L'AST est identique: c'est la propriete visee — la mise en forme et les
    # commentaires n'y figurent pas.
    assert a[0]["ast"] == b[0]["ast"]

    # Les EMPREINTES, elles, different: la fermeture enregistre aussi le nom
    # QUALIFIE, et ces deux `_impl` vivent dans deux portees distinctes. C'est
    # correct — deux fonctions homonymes de modules differents ne sont pas la
    # meme — et cela montre ce que le nom qualifie apporte. En conditions
    # reelles, reformater une implementation ne deplace pas sa portee.
    assert a[0]["function"] != b[0]["function"]


def test_l_implementation_d_un_parent_depend_de_celle_de_ses_enfants() -> None:
    """alpha_cw n'a pas de mathématique propre: toute la sienne est déléguée."""
    import json

    payload = json.loads(implementation_digest(R.ALPHA_CW).canonical_payload)
    assert payload["closure"] == [], "alpha_cw ne devrait avoir aucun code propre"
    # Selecteur + les DEUX branches qui delèguent a une regle. Les deux
    # autres branches portent un scalaire (1 et 1,25) et n'ont pas de regle.
    # L'attente initiale disait 4: c'etait l'attente qui etait fausse.
    assert len(payload["internal_rules"]) == 3, (
        "selecteur + une regle par branche PORTEUSE (2 des 4 branches)"
    )
    for d in payload["internal_rules"]:
        assert len(d["__digest__"]) == 64


def test_la_fermeture_couvre_les_dependances_transitives() -> None:
    """Ce que la fermeture atteint réellement, vérifié et non annoncé."""
    import json

    payload = json.loads(implementation_digest(R.RHO_W_MIN).canonical_payload)
    fragments = payload["closure"]
    fonctions = [f["function"] for f in fragments if "function" in f]
    modules = [f["module"] for f in fragments if "module" in f]
    externes = [f["external_symbol"] for f in fragments if "external_symbol" in f]

    assert any("_rho_w_min" in f for f in fonctions)
    assert "math" in modules, "math.sqrt est utilise et doit etre trace"
    # Le SYMBOLE, pas seulement son module: nommer « math » sans dire « sqrt »
    # laissait `math.sqrt` et `math.tan` apparaitre comme declares-non-utilises
    # a l'inventaire, alors que rho_w_min et s_l_max s'en servent.
    assert "math.sqrt" in externes, "la racine de f_ck doit etre nommee"
    assert "pint.Quantity" in externes, "Q_ vient de Pint"
    # Chaque dependance externe porte sa version: une mise a jour de Pint ou
    # de Python change l'empreinte, elle ne passe pas inapercue.
    for f in fragments:
        if "module" in f or "external_symbol" in f:
            assert f["version"], f"{f}: dependance externe sans version"


# ---------------------------------------------------------------------------
# Refus explicites
# ---------------------------------------------------------------------------
def test_un_appel_dynamique_est_refuse() -> None:
    """getattr, eval, globals: la cible n'est pas déterminable statiquement.

    Refuser est le comportement voulu. Une empreinte calculée malgré tout
    prétendrait couvrir un code dont elle ignore une partie — et inspirerait
    une confiance qu'elle ne mérite pas.
    """
    from eurostruct_engine.ndp.canonical import _closure

    def _dynamique(x):
        return getattr(x, "magnitude")

    with pytest.raises(UnresolvableDependency, match="getattr"):
        _closure(_dynamique, [], set())


def test_un_import_dans_l_implementation_est_refuse() -> None:
    from eurostruct_engine.ndp.canonical import _closure

    def _importe(x):
        import statistics

        return statistics.mean([x])

    with pytest.raises(UnresolvableDependency, match="import"):
        _closure(_importe, [], set())


def test_un_module_hors_frontiere_est_refuse() -> None:
    """Ajouter un module à la frontière est une décision, pas un détail."""
    import statistics

    from eurostruct_engine.ndp.canonical import _closure

    def _hors_frontiere(x):
        return statistics.mean([x])

    _hors_frontiere.__globals__["statistics"] = statistics
    with pytest.raises(UnresolvableDependency, match="racines versionnees"):
        _closure(_hors_frontiere, [], set())


def test_un_etat_mutable_global_est_refuse() -> None:
    """Un dictionnaire de module dans un calcul normatif: refus.

    Son contenu peut changer entre deux exécutions sans qu'aucune empreinte
    ne bouge.
    """
    from eurostruct_engine.ndp.canonical import _closure

    _REGISTRE = {"a": 1}

    def _lit_un_registre(x):
        return _REGISTRE["a"] * x

    _lit_un_registre.__globals__["_REGISTRE"] = _REGISTRE
    with pytest.raises(UnresolvableDependency, match="dict"):
        _closure(_lit_un_registre, [], set())


def test_une_valeur_non_canonicalisable_est_refusee() -> None:
    """Plutôt qu'une représentation par défaut, silencieuse et instable."""
    with pytest.raises(UnresolvableDependency, match="non canonicalisable"):
        canonical_json({"objet": object()})


def test_une_source_python_indisponible_est_refusee() -> None:
    """6.2b — pas de source, pas d'AST, donc pas d'empreinte.

    Une fonction compilée à la volée, ou venant d'un module dont le fichier a
    disparu, ne peut pas être décrite. Produire une empreinte quand même
    reviendrait à sceller une boîte dont on n'a pas regardé l'intérieur.
    """
    from eurostruct_engine.ndp.canonical import _closure

    espace: dict = {}
    exec(compile("def _sans_source(x):\n    return x", "<inexistant>", "exec"),
         espace)

    with pytest.raises((UnresolvableDependency, OSError, TypeError)):
        _closure(espace["_sans_source"], [], set())


def test_un_cycle_de_dependances_ne_boucle_pas() -> None:
    """6.2b — deux fonctions qui s'appellent l'une l'autre.

    ``seen`` coupe la récursion : la fermeture est finie et chaque fonction
    n'y figure qu'une fois. Sans cela, l'empreinte ne se calculerait jamais —
    une panne silencieuse par épuisement de pile, pas un refus.
    """
    from eurostruct_engine.ndp.canonical import _closure

    def _pair(n):
        return _impair(n - 1)

    def _impair(n):
        return _pair(n - 1)

    for f in (_pair, _impair):
        f.__globals__["_pair"] = _pair
        f.__globals__["_impair"] = _impair
        f.__module__ = "eurostruct_engine.faux_cycle"

    fragments: list = []
    _closure(_pair, fragments, set())
    noms = [f["function"] for f in fragments if "function" in f]
    assert sorted(noms) == sorted(set(noms)), "une fonction deux fois"
    assert len(noms) == 2


def test_un_cycle_dans_une_valeur_est_refuse() -> None:
    """6.2b — un objet qui se contient lui-même, côté données cette fois."""
    boucle: dict = {"a": 1}
    boucle["moi"] = boucle
    with pytest.raises(UnresolvableDependency, match="cycle"):
        canonical_json(boucle)


def test_appeler_un_parametre_est_refuse() -> None:
    """6.2b — appel indirect: la cible n'est connue qu'à l'exécution.

    La fermeture ne peut pas dire quel code s'exécutera, et une empreinte qui
    prétend le couvrir ment.
    """
    from eurostruct_engine.ndp.canonical import _closure

    def _applique(x, f):
        return f(x)

    with pytest.raises(UnresolvableDependency, match="appel indirect"):
        _closure(_applique, [], set())


def test_appeler_un_alias_local_est_refuse() -> None:
    """6.2b — le trou était SILENCIEUX, ce qui est pire qu'un refus.

    ``math.sqrt(x)`` écrit directement passe par le contrôle de liste blanche.
    Le même appel via ``f = math.sqrt`` n'inscrivait aucun symbole externe et
    ne passait par aucun contrôle.
    """
    import math

    from eurostruct_engine.ndp.canonical import _closure

    def _par_alias(x):
        f = math.floor
        return f(x)

    _par_alias.__globals__["math"] = math
    with pytest.raises(UnresolvableDependency, match="appel indirect"):
        _closure(_par_alias, [], set())


def test_la_resolution_d_une_liaison_reste_permise() -> None:
    """L'unique appel indirect légitime, reconnu sur sa forme exacte.

    ``fn = _IMPLEMENTATIONS[rule_id]`` puis ``fn(...)`` est le dispatch du
    moteur : le registre figure au payload, la liaison est inscrite par le
    décorateur, et la fonction visée a sa propre empreinte. Interdire tout
    appel indirect aurait rendu le noyau lui-même incalculable.
    """
    assert _fonctions_du_noyau(RuleKind.FORMULA), "le noyau formula se calcule"


def test_un_attribut_dynamique_est_refuse() -> None:
    """6.2b — ``getattr(obj, nom)`` où ``nom`` est calculé."""
    from eurostruct_engine.ndp.canonical import _closure

    def _attribut_dynamique(x, nom):
        return getattr(x, nom)

    with pytest.raises(UnresolvableDependency, match="getattr"):
        _closure(_attribut_dynamique, [], set())


# ---------------------------------------------------------------------------
# 6.2b — noyau générique d'évaluation
#
# `alpha_cw` ne possède aucun code propre : elle choisit une branche et
# délègue. Tout ce qu'elle « fait » vit dans le moteur générique. Tant que
# l'empreinte ne couvrait que le code propre, modifier le sélecteur de branche
# ou le contrôle des bornes changeait son résultat sans changer son empreinte
# — une règle fausse serait restée confirmée.
# ---------------------------------------------------------------------------
#: Composition attendue, écrite ici pour qu'un ajout ou un retrait dans le
#: noyau soit une modification VISIBLE du test, jamais un effet de bord.
NOYAU_ATTENDU = {
    "scalar": [
        "ndp.rules.NormativeRule._validate_inputs",
        "units.require_dimension",
        "ndp.rules.DomainBound.check",
        "ndp.rules.ScalarRule.evaluate",
    ],
    "formula": [
        "ndp.rules.NormativeRule._validate_inputs",
        "units.require_dimension",
        "ndp.rules.DomainBound.check",
        "ndp.rules.FormulaRule.evaluate",
        "ndp.rules._dim_of",
        "ndp.rules.implementation",
    ],
    "conditional_rule": [
        "ndp.rules.NormativeRule._validate_inputs",
        "units.require_dimension",
        "ndp.rules.DomainBound.check",
        "ndp.rules.ConditionalRule.evaluate",
        "ndp.rules.get_rule",
        "ndp.rules.Branch.contains",
    ],
    "function": [
        "ndp.rules.NormativeRule._validate_inputs",
        "units.require_dimension",
        "ndp.rules.DomainBound.check",
        "ndp.rules.NormativeFunction.evaluate",
        "ndp.rules._dim_of",
        "ndp.rules.implementation",
    ],
}


def _fonctions_du_noyau(kind) -> list[str]:
    import json

    payload = json.loads(evaluation_kernel_digest(kind).canonical_payload)
    return [
        f["function"].replace("eurostruct_engine.", "")
        for f in payload["closure"] if "function" in f
    ]


@pytest.mark.parametrize("kind", list(RuleKind), ids=lambda k: k.value)
def test_le_noyau_couvre_exactement_les_fonctions_declarees(kind) -> None:
    """La liste exacte, par type de règle — annoncée et vérifiée."""
    assert _fonctions_du_noyau(kind) == NOYAU_ATTENDU[kind.value]


def test_chaque_type_de_regle_a_son_propre_noyau() -> None:
    """Quatre types, quatre chemins d'évaluation, quatre empreintes.

    Un noyau commun aux quatre aurait fait dépendre l'empreinte d'une règle
    scalaire du sélecteur de branches, qu'elle n'emprunte jamais.
    """
    empreintes = {k: evaluation_kernel_digest(k).digest for k in RuleKind}
    assert len(set(empreintes.values())) == len(RuleKind)


def test_modifier_le_selecteur_de_branche_change_l_empreinte_d_alpha_cw(
    monkeypatch,
) -> None:
    """La démonstration demandée: le sélecteur de branche est sous empreinte.

    La variante retire les inclusivités — exactement le genre de modification
    qui déplace la frontière entre deux branches d'``alpha_cw`` sans toucher
    une ligne de la règle elle-même.
    """
    from eurostruct_engine.ndp import rules as _r

    avant_noyau = evaluation_kernel_digest(RuleKind.CONDITIONAL_RULE).digest
    avant_regle = implementation_digest(R.ALPHA_CW).digest

    def _contains_modifie(self, x: float) -> bool:
        if self.lower is not None and x < self.lower:
            return False
        if self.upper is not None and x > self.upper:
            return False
        return True

    monkeypatch.setattr(_r.Branch, "contains", _contains_modifie)

    assert evaluation_kernel_digest(RuleKind.CONDITIONAL_RULE).digest != avant_noyau
    assert implementation_digest(R.ALPHA_CW).digest != avant_regle, (
        "alpha_cw n'a aucun code propre: si le selecteur de branche change "
        "sans que son empreinte bouge, une regle fausse reste confirmee."
    )


def test_modifier_le_controle_des_bornes_change_l_empreinte_d_alpha_cw(
    monkeypatch,
) -> None:
    """Idem pour le contrôle du domaine — ici carrément désarmé."""
    from eurostruct_engine.ndp import rules as _r

    avant = implementation_digest(R.ALPHA_CW).digest

    def _check_desarme(self, valeurs, rule_id):
        return None

    monkeypatch.setattr(_r.DomainBound, "check", _check_desarme)
    assert implementation_digest(R.ALPHA_CW).digest != avant


def test_le_noyau_entre_dans_toutes_les_empreintes_d_implementation() -> None:
    """Pas seulement dans celle d'``alpha_cw``."""
    import json

    for regle in all_rules():
        payload = json.loads(implementation_digest(regle).canonical_payload)
        assert "evaluation_kernel" in payload, regle.rule_id
        assert len(payload["evaluation_kernel"]["__digest__"]) == 64


# ---------------------------------------------------------------------------
# 6.2b — politique des décorateurs
# ---------------------------------------------------------------------------
def test_la_preuve_d_identite_est_statique_et_n_execute_rien() -> None:
    """6.2c — la sonde qui APPELAIT le decorateur est supprimee.

    Elle avait deux defauts, et le second est redhibitoire: elle inscrivait sa
    sonde dans `_IMPLEMENTATIONS` (annule seulement par une restauration
    explicite des registres DECLARES, donc pas pour un effet de bord ailleurs),
    et surtout calculer une empreinte executait du code applicatif. Une
    empreinte decrit; elle ne doit rien faire arriver.
    """
    from eurostruct_engine.ndp.canonical import _preuve_identite_statique
    from eurostruct_engine.ndp.rules import implementation

    assert _preuve_identite_statique(implementation) == "esc-identity/1/fabrique"
    assert not hasattr(C, "_verifie_identite"), (
        "la sonde executee doit avoir disparu du module, pas seulement de "
        "son chemin d'appel"
    )


def test_la_preuve_statique_reconnait_la_forme_directe() -> None:
    from eurostruct_engine.ndp.canonical import _preuve_identite_statique

    def _direct(fn):
        return fn

    assert _preuve_identite_statique(_direct) == "esc-identity/1/direct"


@pytest.mark.parametrize(
    ("variante", "motif"),
    [
        # Enveloppe: la voie de retour ne rend pas le parametre.
        ("""
def _v(rule_id):
    def decorate(fn):
        def emballage(*a, **k):
            return fn(*a, **k)
        return emballage
    return decorate
""", "ne rend pas"),
        # Reaffectation: `return fn` est vrai syntaxiquement, faux en fait.
        ("""
def _v(rule_id):
    def decorate(fn):
        fn = staticmethod(fn)
        return fn
    return decorate
""", "reaffecte"),
        # Chute en fin de corps: rend None sur une des voies.
        ("""
def _v(rule_id):
    def decorate(fn):
        if rule_id:
            return fn
    return decorate
""", "voies de sortie"),
        # La fabrique ne rend pas son decorateur interne.
        ("""
def _v(rule_id):
    def decorate(fn):
        return fn
    return staticmethod(decorate)
""", "ne rend pas"),
        # Plus d'un parametre: la preuve ne sait pas lequel porte la fonction.
        ("""
def _v(rule_id):
    def decorate(fn, autre):
        return fn
    return decorate
""", "exactement un parametre"),
    ],
    ids=["enveloppe", "reaffectation", "chute", "fabrique_infidele", "deux_params"],
)
def test_un_decorateur_qui_ne_rend_pas_la_fonction_est_refuse(
    tmp_path, variante, motif,
) -> None:
    """6.2c — chaque facon de rompre le contrat, prouvee sur l'AST seul.

    Aucune de ces variantes n'est EXECUTEE: c'est tout l'objet du correctif.
    """
    from eurostruct_engine.ndp.canonical import _preuve_identite_statique

    module = tmp_path / "variante_deco.py"
    module.write_text(variante, encoding="utf-8")
    espace: dict = {}
    exec(compile(variante, str(module), "exec"), espace)
    fn = espace["_v"]
    fn.__module__ = "eurostruct_engine.faux_deco"

    with pytest.raises(UnresolvableDependency, match=motif):
        _preuve_identite_statique(fn)


def test_un_decorateur_connu_hors_contrat_est_refuse(monkeypatch) -> None:
    """6.2c, exigence 5 — l'AST ne respecte plus le contrat: refus.

    Le decorateur reste declare dans `_KNOWN_IDENTITY_DECORATORS`, mais sa
    preuve statique echoue. La regle devient incalculable plutot que de
    recevoir une empreinte qui atteste une identite fausse.
    """
    from eurostruct_engine.ndp import rules_be_ec2 as _rbe

    def implementation(rule_id):
        def decorate(fn):
            def emballage(*a, **k):
                return fn(*a, **k)
            return emballage
        return decorate

    implementation.__module__ = "eurostruct_engine.ndp.rules"
    monkeypatch.setattr(_rbe, "implementation", implementation)

    with pytest.raises(UnresolvableDependency, match="ne rend pas"):
        C._closure(_rbe._nu, [], set())


def test_modifier_le_decorateur_change_l_empreinte(monkeypatch) -> None:
    """6.2c — « toute modification du decorateur doit changer l'empreinte ».

    Sa fermeture — AST et dependances — entre au payload comme celle de
    n'importe laquelle de nos fonctions. La variante ci-dessous respecte le
    contrat d'identite (elle rend bien `fn`) mais n'ecrit plus dans le
    registre: le comportement change, l'empreinte doit changer.
    """
    from eurostruct_engine.ndp import rules_be_ec2 as _rbe

    avant = implementation_digest(R.NU_STRENGTH_REDUCTION).digest

    def implementation(rule_id):
        def decorate(fn):
            return fn
        return decorate

    implementation.__module__ = "eurostruct_engine.ndp.rules"
    monkeypatch.setattr(_rbe, "implementation", implementation)

    apres = implementation_digest(R.NU_STRENGTH_REDUCTION)
    assert apres.digest != avant
    assert "esc-identity/1/fabrique" in apres.canonical_payload


def test_modifier_la_liaison_change_l_empreinte() -> None:
    """L'autre moitie de la meme exigence: `rule_id -> fonction qualifiee`."""
    import json

    a = json.loads(implementation_digest(R.RHO_W_MIN).canonical_payload)
    b = json.loads(implementation_digest(R.S_T_MAX).canonical_payload)
    liaison = lambda p: [d["binding"] for f in p["closure"]
                         for d in f.get("decorators", [])]
    assert liaison(a) != liaison(b)
    assert liaison(a) == [{"rule_id": "be.ec2.rho_w_min",
                           "function": "eurostruct_engine.ndp.rules_be_ec2._rho_w_min"}]


def test_la_liaison_rule_id_vers_fonction_est_enregistree() -> None:
    """Identité, arguments et liaison canonique — les trois."""
    import json

    payload = json.loads(implementation_digest(R.RHO_W_MIN).canonical_payload)
    decos = [d for f in payload["closure"] for d in f.get("decorators", [])]
    assert len(decos) == 1
    (deco,) = decos
    assert deco["decorator"] == "eurostruct_engine.ndp.rules.implementation"
    assert deco["arguments"] == ["be.ec2.rho_w_min"]
    assert deco["identity_proof"] == "esc-identity/1/fabrique"
    assert deco["binding"] == {
        "rule_id": "be.ec2.rho_w_min",
        "function": "eurostruct_engine.ndp.rules_be_ec2._rho_w_min",
    }


def test_le_mecanisme_qui_resout_la_liaison_est_dans_le_noyau() -> None:
    """L'autre moitié: qui va CHERCHER la fonction au moment d'évaluer.

    Une liaison n'est vérifiable que si ses deux moitiés sont sous empreinte —
    celle qui inscrit (``implementation``) et celle qui résout
    (``FormulaRule.evaluate`` lisant ``_IMPLEMENTATIONS``).
    """
    import json

    payload = json.loads(
        evaluation_kernel_digest(RuleKind.FORMULA).canonical_payload
    )
    registres = [
        f["binding_registry"] for f in payload["closure"] if "binding_registry" in f
    ]
    assert "eurostruct_engine.ndp.rules._IMPLEMENTATIONS" in registres
    assert "ndp.rules.implementation" in _fonctions_du_noyau(RuleKind.FORMULA)


def test_un_decorateur_inconnu_est_refuse() -> None:
    """Aucun traitement superficiel par défaut.

    ``_marqueur_exterieur`` est pourtant un décorateur d'identité parfaitement
    inoffensif. Il est refusé quand même : la fermeture ne le sait pas, et
    « inoffensif » n'est pas une propriété qu'on suppose.
    """
    from eurostruct_engine.ndp.canonical import _closure

    with pytest.raises(UnresolvableDependency, match="decorateur"):
        _closure(_avec_decorateur_inconnu, [], set())


def test_un_decorateur_de_notre_paquet_voit_sa_fermeture_resolue() -> None:
    """L'alternative au refus: résolution transitive complète.

    Le décorateur n'est PAS résumé par une liaison — son propre code entre au
    payload, avec les dépendances qu'il lit.
    """
    from eurostruct_engine.ndp.canonical import _closure

    fragments: list = []
    _closure(_avec_decorateur_interne, fragments, set())
    decos = [d for f in fragments for d in f.get("decorators", [])]
    assert len(decos) == 1
    (deco,) = decos
    assert "binding" not in deco, "un decorateur non declare n'a pas droit au resume"
    noms = [f["function"] for f in deco["closure"] if "function" in f]
    assert any("_decorateur_interne" in n for n in noms)


# ---------------------------------------------------------------------------
# 6.2b — liste blanche de symboles externes
# ---------------------------------------------------------------------------
def _symboles_utilises() -> tuple[set[str], set[str]]:
    """Ce que les empreintes ENREGISTRENT réellement comme symboles externes."""
    import json

    regles: set[str] = set()
    for regle in all_rules():
        payload = json.loads(implementation_digest(regle).canonical_payload)
        regles |= {
            f["external_symbol"] for f in payload["closure"]
            if "external_symbol" in f
        }
    noyau: set[str] = set()
    for kind in RuleKind:
        payload = json.loads(evaluation_kernel_digest(kind).canonical_payload)
        noyau |= {
            f["external_symbol"] for f in payload["closure"]
            if "external_symbol" in f
        }
    return regles, noyau


def test_aucun_symbole_declare_n_est_inutilise() -> None:
    """La liste blanche vaut ce que vaut sa minimalité.

    ``_autoriser`` garantit déjà « utilisé ⊆ déclaré ». Ce test ferme l'autre
    sens: une entrée morte est un élargissement latent, et c'est ainsi que
    ``builtins.getattr`` avait fini dans la liste du noyau — alors que
    ``_free_names`` refuse de toute façon tout appel à ``getattr``.
    """
    regles, noyau = _symboles_utilises()
    assert ALLOWED_EXTERNAL_SYMBOLS == regles - set(ALLOWED_EXCEPTIONS)
    assert KERNEL_ALLOWED_SYMBOLS == noyau - set(ALLOWED_EXCEPTIONS)
    assert ALLOWED_EXCEPTIONS == (regles | noyau) & set(ALLOWED_EXCEPTIONS)


def test_les_deux_listes_repondent_a_deux_questions_differentes() -> None:
    """Le noyau n'est pas le sur-ensemble des règles, ni l'inverse.

    Chaîner les deux faisait entrer ``math.sqrt`` dans le noyau, qui ne calcule
    aucune racine, et ``sorted`` dans le domaine d'une règle, qui ne trie rien.
    """
    assert "math.sqrt" in ALLOWED_EXTERNAL_SYMBOLS
    assert "math.sqrt" not in KERNEL_ALLOWED_SYMBOLS
    assert "builtins.sorted" in KERNEL_ALLOWED_SYMBOLS
    assert "builtins.sorted" not in ALLOWED_EXTERNAL_SYMBOLS


def test_un_symbole_autorise_passe() -> None:
    """Verrou 1/4: ``min`` est déclaré, une règle a le droit de l'appeler."""
    from eurostruct_engine.ndp.canonical import _closure

    def _plafonne(x):
        return min(x, 3.0)

    fragments: list = []
    _closure(_plafonne, fragments, set())
    assert any(f.get("external_symbol") == "builtins.min" for f in fragments)


def test_un_builtin_non_autorise_est_refuse() -> None:
    """Verrou 2/4: ``len`` n'a rien à faire dans une formule d'Eurocode."""
    from eurostruct_engine.ndp.canonical import _closure

    def _compte(x):
        return len(x)

    with pytest.raises(UnresolvableDependency, match="builtins.len"):
        _closure(_compte, [], set())


def test_une_fonction_externe_non_autorisee_est_refusee() -> None:
    """Verrou 3/4: ``math`` est une racine versionnée, ``math.floor`` non.

    Autoriser un module entier laissait passer tout son contenu. C'est la
    différence exacte entre l'ancienne frontière et la liste actuelle.
    """
    import math

    from eurostruct_engine.ndp.canonical import _closure

    def _arrondit(x):
        return math.floor(x)

    _arrondit.__globals__["math"] = math
    with pytest.raises(UnresolvableDependency, match="math.floor"):
        _closure(_arrondit, [], set())


def test_modifier_la_liste_d_autorisation_change_les_empreintes(monkeypatch) -> None:
    """Verrou 4/4: la liste elle-même est sous empreinte.

    Elle entre au payload : élargir ce qu'une règle a le droit d'appeler est un
    changement normatif de la méthode, pas un réglage interne. Une confirmation
    signée sous l'ancienne liste ne vaut plus sous la nouvelle.
    """
    from eurostruct_engine.ndp import canonical as _c

    avant = implementation_digest(R.RHO_W_MIN).digest
    monkeypatch.setattr(
        _c, "ALLOWED_EXTERNAL_SYMBOLS",
        frozenset(ALLOWED_EXTERNAL_SYMBOLS | {"math.floor"}),
    )
    assert implementation_digest(R.RHO_W_MIN).digest != avant


def test_la_liste_appliquee_est_celle_qui_est_declaree(monkeypatch) -> None:
    """Ce qui est ANNONCÉ et ce qui est APPLIQUÉ ne doivent pas diverger.

    La liste était une valeur par défaut d'argument, liée à l'import: la
    redéfinir changeait le payload sans changer le refus. Une liste blanche
    dont l'annonce et l'application peuvent diverger ne garantit rien.
    """
    import math

    from eurostruct_engine.ndp import canonical as _c

    def _arrondit(x):
        return math.floor(x)

    _arrondit.__globals__["math"] = math
    with pytest.raises(UnresolvableDependency):
        _c._closure(_arrondit, [], set())

    monkeypatch.setattr(
        _c, "ALLOWED_EXTERNAL_SYMBOLS",
        frozenset(ALLOWED_EXTERNAL_SYMBOLS | {"math.floor"}),
    )
    _c._closure(_arrondit, [], set())      # ne leve plus


# ---------------------------------------------------------------------------
# 6.2b — garanties de représentation canonique
# ---------------------------------------------------------------------------
def test_les_chaines_sont_normalisees_en_NFC() -> None:
    """Deux ecritures Unicode du meme texte donnent la meme empreinte.

    Recopier une citation depuis un PDF change l'une en l'autre sans qu'aucune
    difference soit visible a l'ecran. Sans normalisation, un verificateur
    devrait re-signer pour un copier-coller.

    Les deux formes sont construites par ECHAPPEMENTS et non ecrites en clair:
    ecrites en clair elles seraient indiscernables dans le source, un editeur
    les uniformiserait, et le test passerait en ne verifiant plus rien. C'est
    arrive a la premiere redaction de ce test.
    """
    compose = "\u00e9paisseur"          # e accent aigu precompose  (U+00E9)
    decompose = "e\u0301paisseur"       # e + accent combinant      (U+0065 U+0301)
    assert compose != decompose, "les deux formes doivent differer en memoire"
    assert unicodedata.normalize("NFC", decompose) == compose
    assert digest_of({"c": compose}).digest == digest_of({"c": decompose}).digest


def test_deux_cles_qui_se_normalisent_pareil_sont_refusees() -> None:
    """Sinon l'une ecrase l'autre en silence dans le mapping canonique.

    Le tri se faisait sur la forme BRUTE et la normalisation venait apres:
    l'ordre etait donc defini sur une forme absente du payload, et surtout la
    comprehension de dictionnaire perdait une des deux cles sans un mot.
    """
    deux_cles = {"\u00e9": 1, "e\u0301": 2}
    assert len(deux_cles) == 2, "le dict de depart porte bien deux cles"
    with pytest.raises(UnresolvableDependency, match="se normalisent"):
        canonical_json(deux_cles)


def test_deux_elements_d_ensemble_qui_se_normalisent_pareil_sont_refuses() -> None:
    """Meme perte silencieuse, cote ensembles."""
    deux_elements = {"\u00e9", "e\u0301"}
    assert len(deux_elements) == 2
    with pytest.raises(UnresolvableDependency, match="meme forme canonique"):
        canonical_json({"s": deux_elements})


def test_le_payload_est_de_l_UTF_8_reel_sans_echappement_ascii() -> None:
    """Le digest porte sur l'encodage UTF-8 du texte, pas sur des \\uXXXX."""
    texte = canonical_json({"c": "§6.2.2 — épaisseur"})
    assert "§" in texte and "\\u" not in texte
    assert texte.encode("utf-8").decode("utf-8") == texte


def test_NaN_et_les_infinis_sont_refuses() -> None:
    """Aucune lecture d'annexe ne les produit, et ``NaN != NaN``.

    Une empreinte contenant NaN rendrait toute comparaison fausse en silence —
    exactement la panne qu'une empreinte existe pour empêcher.
    """
    for valeur in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(UnresolvableDependency, match="non finie"):
            canonical_json({"v": valeur})
        with pytest.raises(UnresolvableDependency, match="non finie"):
            canonical_json({"v": Q_(valeur, "MPa")})


def test_moins_zero_et_zero_donnent_la_meme_empreinte() -> None:
    """``-0.0 == 0.0``, et les deux se comportent identiquement sur une borne.

    Les distinguer produirait un changement d'empreinte sans changement de
    sens: un vérificateur re-signerait pour rien.
    """
    assert digest_of({"v": -0.0}).digest == digest_of({"v": 0.0}).digest
    assert digest_of({"v": Q_(-0.0, "MPa")}).digest == digest_of(
        {"v": Q_(0.0, "MPa")}).digest


def test_True_1_et_1_0_restent_distincts() -> None:
    """Trois déclarations différentes, délibérément.

    Une borne de domaine qui passe de l'entier au flottant est un changement de
    déclaration, même si Python les tient pour égaux.
    """
    empreintes = {digest_of({"v": v}).digest for v in (True, 1, 1.0)}
    assert len(empreintes) == 3
    assert '"v":true' in canonical_json({"v": True})
    assert '"v":1' in canonical_json({"v": 1})
    assert '"__float__":"1.0"' in canonical_json({"v": 1.0})


def test_l_ordre_d_ecriture_d_un_mapping_est_sans_effet() -> None:
    """Les clés sont triées: deux dicts égaux ont la même empreinte."""
    a = {"b": 1, "a": 2, "c": 3}
    b = {"c": 3, "a": 2, "b": 1}
    assert digest_of(a).digest == digest_of(b).digest
    assert canonical_json(a).index('"a"') < canonical_json(a).index('"b"')


def test_les_ensembles_sont_tries_sur_leur_forme_canonique() -> None:
    """Et non selon un ordre Python, qui n'existe pas pour des dictionnaires.

    Un flottant se canonicalise en ``{"__float__": ...}``. ``sorted`` sur de
    tels éléments lèverait ``TypeError`` — deux dicts ne sont pas comparables.
    Trier sur la forme sérialisée est défini pour tous les cas, et l'ordre
    obtenu est lexicographique et non numérique: 1.0, 10.0, 2.0.
    """
    texte = canonical_json({"s": frozenset({1.0, 10.0, 2.0})})
    assert texte.index('"1.0"') < texte.index('"10.0"') < texte.index('"2.0"')
    # Même ensemble, construit dans un autre ordre: même empreinte.
    assert digest_of({"s": frozenset({2.0, 1.0, 10.0})}).digest == digest_of(
        {"s": frozenset({10.0, 2.0, 1.0})}).digest
    # Et des Quantity, qui se canonicalisent aussi en mappings.
    assert digest_of({"s": frozenset({Q_(1, "MPa"), Q_(2, "MPa")})}).digest == (
        digest_of({"s": frozenset({Q_(2, "MPa"), Q_(1, "MPa")})}).digest)


def test_l_empreinte_est_stable_sous_plusieurs_PYTHONHASHSEED() -> None:
    """L'ordre d'itération d'un set dépend du seed de hachage du processus.

    Le vérifier DANS ce processus ne prouverait rien: il faut de vrais
    interpréteurs, avec de vrais seeds différents.
    """
    import os
    import subprocess
    import sys
    import textwrap

    programme = textwrap.dedent(
        """
        from eurostruct_engine.ndp import rules_be_ec2 as R
        from eurostruct_engine.ndp.canonical import (
            digest_of, implementation_digest, normative_spec_digest,
        )
        jeu = {"a", "b", "c", "d", "e", "f", "g", "h"}
        print(digest_of({"s": frozenset(jeu), "d": {k: 1 for k in jeu}}).digest)
        print(normative_spec_digest(R.ALPHA_CW).digest)
        print(implementation_digest(R.ALPHA_CW).digest)
        """
    )
    sorties = []
    for seed in ("0", "1", "42", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run(
            [sys.executable, "-c", programme],
            capture_output=True, text=True, env=env, check=True,
        )
        sorties.append(r.stdout)
    assert len(set(sorties)) == 1, f"empreintes instables selon le seed: {sorties}"


def _decorateur_interne(fn):
    """Décorateur d'identité, mais NON déclaré comme tel: sa fermeture doit
    être résolue entièrement plutôt que résumée par une liaison."""
    return fn


# Le traitement « fermeture résolue » vise NOTRE code. Le décorateur est donc
# rattaché au paquet, sans quoi il tomberait dans la branche « inconnu ».
_decorateur_interne.__module__ = "eurostruct_engine.faux_decorateur"


@_decorateur_interne
def _avec_decorateur_interne(x):
    return x


def _marqueur_exterieur(fn):
    return fn


@_marqueur_exterieur
def _avec_decorateur_inconnu(x):
    return x


# ---------------------------------------------------------------------------
# 6.2c — PURETE de la canonicalisation
#
# La canonicalisation est une operation PURE: lecture et serialisation
# uniquement. Elle ne mute aucun etat et n'execute aucun code applicatif.
#
# Ce n'etait pas le cas: la sonde d'identite APPELAIT `implementation`, qui
# inscrivait sa sonde dans `_IMPLEMENTATIONS`. Une restauration explicite
# annulait l'effet sur les registres DECLARES — donc pas un effet de bord
# ailleurs. Une empreinte decrit; elle ne doit rien faire arriver.
# ---------------------------------------------------------------------------
#: Modifiee par `_decorateur_a_effet_de_bord` chaque fois qu'il est APPELE.
SENTINELLE: list[str] = []


def _decorateur_a_effet_de_bord(rule_id):
    SENTINELLE.append(rule_id)

    def decorate(fn):
        SENTINELLE.append(f"decore:{rule_id}")
        return fn
    return decorate


@_decorateur_a_effet_de_bord("a_l_import")
def _fonction_a_decorateur_observable(x):
    return x


def _etat_mutable_des_modules() -> dict:
    """Instantane de tout l'etat mutable de portee module qui nous concerne."""
    from eurostruct_engine.ndp import canonical as _c
    from eurostruct_engine.ndp import rules as _r

    instantane: dict = {}
    for module in (_c, _r):
        for nom, valeur in vars(module).items():
            if isinstance(valeur, (dict, list, set)) and not nom.startswith("__"):
                instantane[f"{module.__name__}.{nom}"] = (
                    sorted(map(str, valeur)) if isinstance(valeur, set)
                    else str(valeur)
                )
    return instantane


def _toutes_les_empreintes() -> dict[str, tuple[str, str]]:
    return {
        r.rule_id: (normative_spec_digest(r).digest, implementation_digest(r).digest)
        for r in all_rules()
    }


def test_calculer_les_empreintes_ne_modifie_aucun_registre() -> None:
    """Purete 1/7 — les registres de liaison sont intacts apres calcul."""
    from eurostruct_engine.ndp.rules import _IMPLEMENTATIONS, _RULES

    avant_i, avant_r = dict(_IMPLEMENTATIONS), dict(_RULES)
    empreintes = _toutes_les_empreintes()
    assert len(empreintes) == 9, "les neuf regles declarees"
    for kind in RuleKind:
        evaluation_kernel_digest(kind)

    assert _IMPLEMENTATIONS == avant_i
    assert _RULES == avant_r
    assert not [k for k in _IMPLEMENTATIONS if "sonde" in k]


def test_calculer_plusieurs_fois_ne_modifie_aucun_etat_mutable() -> None:
    """Purete 2/7 — aucun etat mutable de module ne bouge, sur trois passes.

    Porte sur TOUT dict, list ou set de portee module dans `canonical` et
    `rules`, et pas seulement sur ceux qu'on pense concernes: `_IN_PROGRESS`
    etait un ensemble global mute pendant le calcul et restaure par un
    `finally` — nul en net, donc invisible a un test qui ne regarde qu'avant
    et apres. Il est desormais passe en parametre.
    """
    avant = _etat_mutable_des_modules()
    for _ in range(3):
        _toutes_les_empreintes()
    assert _etat_mutable_des_modules() == avant


def test_l_ordre_de_calcul_ne_change_ni_les_payloads_ni_les_digests() -> None:
    """Purete 3/7 — aucun cache ni accumulateur ne fait dependre A de B."""
    regles = list(all_rules())

    croissant = {
        r.rule_id: (normative_spec_digest(r).canonical_payload,
                    implementation_digest(r).canonical_payload)
        for r in regles
    }
    decroissant = {
        r.rule_id: (normative_spec_digest(r).canonical_payload,
                    implementation_digest(r).canonical_payload)
        for r in reversed(regles)
    }
    assert croissant == decroissant


def test_un_decorateur_a_effet_de_bord_est_refuse_sans_etre_execute() -> None:
    """Purete 4/7 — la sentinelle ne bouge pas, parce que rien n'est appele.

    Le decorateur s'execute une fois a l'import, comme tout decorateur Python;
    c'est la valeur APRES import qui sert de reference. Calculer l'empreinte
    ne doit pas l'incrementer d'un cran.
    """
    assert SENTINELLE == ["a_l_import", "decore:a_l_import"], (
        "temoin: le decorateur a bien tourne une fois, a l'import"
    )
    avant = list(SENTINELLE)

    with pytest.raises(UnresolvableDependency, match="inconnu"):
        C._closure(_fonction_a_decorateur_observable, [], set())

    assert SENTINELLE == avant, (
        "le canonicaliseur a EXECUTE le decorateur au lieu de le refuser"
    )


def test_aucun_decorateur_n_est_execute_pendant_le_calcul_des_empreintes(
    monkeypatch,
) -> None:
    """Purete 4/7 bis — y compris le decorateur CONNU.

    On remplace `implementation` par une variante qui respecte le contrat
    d'identite mais consigne chacun de ses appels. Elle ne doit jamais etre
    appelee: la preuve est desormais statique.
    """
    from eurostruct_engine.ndp import rules_be_ec2 as _rbe

    def implementation(rule_id):
        # Si le canonicaliseur APPELLE ce decorateur, ceci remonte et le test
        # echoue bruyamment. Consigner les appels dans une liste aurait
        # demande une globale mutable, que la fermeture refuse par ailleurs.
        #
        # La preuve statique accepte cette forme: une fonction dont la seule
        # voie de sortie leve ne rend jamais de substitut, donc « elle rend
        # exactement ce qu'elle a recu » y est vrai par vacuite.
        raise RuleImplementationMissing(
            f"le canonicaliseur a EXECUTE le decorateur pour {rule_id}"
        )

    implementation.__module__ = "eurostruct_engine.ndp.rules"
    monkeypatch.setattr(_rbe, "implementation", implementation)

    for regle in all_rules():
        implementation_digest(regle)          # ne doit rien lever


def test_les_empreintes_sont_identiques_dans_un_processus_neuf() -> None:
    """Purete 6/7 — aucun etat accumule dans CE processus ne les influence.

    Distinct du test PYTHONHASHSEED, qui compare des processus neufs entre eux:
    ici on compare le processus courant — qui a deja calcule des centaines
    d'empreintes et monkeypatche des modules — a un processus vierge.
    """
    import json
    import os
    import subprocess
    import sys
    import textwrap

    ici = _toutes_les_empreintes()

    programme = textwrap.dedent(
        """
        import json
        from eurostruct_engine.ndp import rules_be_ec2  # noqa: F401
        from eurostruct_engine.ndp.rules import all_rules
        from eurostruct_engine.ndp.canonical import (
            implementation_digest, normative_spec_digest,
        )
        print(json.dumps({
            r.rule_id: [normative_spec_digest(r).digest,
                        implementation_digest(r).digest]
            for r in all_rules()
        }))
        """
    )
    r = subprocess.run(
        [sys.executable, "-c", programme],
        capture_output=True, text=True, check=True,
        env=dict(os.environ, PYTHONHASHSEED="7"),
    )
    ailleurs = {k: tuple(v) for k, v in json.loads(r.stdout).items()}
    assert ici == ailleurs


def test_le_canonicaliseur_ne_mute_aucun_etat_de_portee_module() -> None:
    """Purete 2/7 bis — prouve sur le SOURCE, pas par observation.

    Un instantane pris avant et apres le calcul ne voit pas une mutation
    transitoire: `_IN_PROGRESS` etait un ensemble global sur lequel on faisait
    `.add()` puis `.discard()` dans un `finally`. Nul en net, donc invisible —
    et pourtant la canonicalisation n'etait pas pure, ni reentrante.

    Ce test lit le source du module et refuse toute mutation d'un conteneur de
    portee module: affectation par indice, `del`, `+=`, ou appel d'une methode
    mutante. C'est la forme verifiable de la phrase « lecture et serialisation
    uniquement ».
    """
    import ast as _ast
    import inspect as _inspect

    MUTANTES = {
        "add", "append", "extend", "insert", "remove", "pop", "clear",
        "update", "discard", "setdefault", "popitem", "sort", "reverse",
    }

    arbre = _ast.parse(_inspect.getsource(C))

    conteneurs: set[str] = set()
    for noeud in arbre.body:
        if isinstance(noeud, (_ast.Assign, _ast.AnnAssign)):
            cibles = (noeud.targets if isinstance(noeud, _ast.Assign)
                      else [noeud.target])
            valeur = noeud.value
            mutable = isinstance(valeur, (_ast.Dict, _ast.List, _ast.Set)) or (
                isinstance(valeur, _ast.Call)
                and isinstance(valeur.func, _ast.Name)
                and valeur.func.id in ("dict", "list", "set")
            )
            if mutable:
                conteneurs |= {c.id for c in cibles if isinstance(c, _ast.Name)}

    # Temoin: si ce module n'a plus AUCUN conteneur mutable de portee module,
    # le test ne verifie plus rien et doit le dire.
    assert conteneurs, (
        "aucun conteneur mutable de portee module: verifier que ce test a "
        "encore un objet, plutot que de le croire vert"
    )

    fautes: list[str] = []
    for noeud in _ast.walk(arbre):
        if isinstance(noeud, _ast.Call) and isinstance(noeud.func, _ast.Attribute):
            base = noeud.func.value
            if (isinstance(base, _ast.Name) and base.id in conteneurs
                    and noeud.func.attr in MUTANTES):
                fautes.append(f"ligne {noeud.lineno}: {base.id}.{noeud.func.attr}()")
        elif isinstance(noeud, (_ast.Assign, _ast.AugAssign, _ast.Delete)):
            cibles = (noeud.targets if isinstance(noeud, _ast.Assign)
                      else [noeud.target] if isinstance(noeud, _ast.AugAssign)
                      else noeud.targets)
            for c in cibles:
                if isinstance(c, _ast.Subscript) and isinstance(c.value, _ast.Name):
                    if c.value.id in conteneurs:
                        fautes.append(f"ligne {noeud.lineno}: {c.value.id}[...]")

    assert fautes == [], (
        "la canonicalisation mute un etat de portee module: " + "; ".join(fautes)
    )


def test_les_listes_tenues_a_la_main_sont_controlees() -> None:
    """Purete 7/7 — ni entree morte, ni usage reel non declare.

    Les deux listes sont des DECISIONS humaines, pas des proprietes deduites.
    Ce test les tient a leur usage reel dans les deux sens.
    """
    import json

    from eurostruct_engine.ndp import rules as _r
    from eurostruct_engine.ndp.canonical import (
        _BINDING_REGISTRIES,
        _KNOWN_IDENTITY_DECORATORS,
        _preuve_identite_statique,
    )

    # --- registres de liaison ---------------------------------------------
    declares = {f"eurostruct_engine.ndp.rules.{n}" for n in _BINDING_REGISTRIES}
    for nom in _BINDING_REGISTRIES:
        assert isinstance(getattr(_r, nom, None), dict), (
            f"{nom} declare comme registre mais absent ou non-dict"
        )

    utilises: set[str] = set()
    for kind in RuleKind:
        payload = json.loads(evaluation_kernel_digest(kind).canonical_payload)
        utilises |= {f["binding_registry"] for f in payload["closure"]
                     if "binding_registry" in f}
    for regle in all_rules():
        payload = json.loads(implementation_digest(regle).canonical_payload)
        utilises |= {f["binding_registry"] for f in payload["closure"]
                     if "binding_registry" in f}
        for f in payload["closure"]:
            for d in f.get("decorators", []):
                utilises |= {g["binding_registry"] for g in d["closure"]
                             if "binding_registry" in g}
    assert declares == utilises, (
        f"declares={sorted(declares)} utilises={sorted(utilises)}"
    )

    # --- decorateurs a identite -------------------------------------------
    for nom in _KNOWN_IDENTITY_DECORATORS:
        obj = getattr(_r, nom, None)
        assert obj is not None, f"{nom} declare mais introuvable dans rules"
        # Declare veut dire PROUVABLE: une entree dont la preuve echoue rendrait
        # toute regle qui l'emploie incalculable, sans que rien ne l'annonce.
        assert _preuve_identite_statique(obj).startswith("esc-identity/")

    employes: set[str] = set()
    for regle in all_rules():
        payload = json.loads(implementation_digest(regle).canonical_payload)
        for f in payload["closure"]:
            for d in f.get("decorators", []):
                if "identity_proof" in d:
                    employes.add(d["decorator"].rsplit(".", 1)[-1])
    assert employes == set(_KNOWN_IDENTITY_DECORATORS), (
        f"declares={sorted(_KNOWN_IDENTITY_DECORATORS)} employes={sorted(employes)}"
    )


# ---------------------------------------------------------------------------
# Empreinte de preuve
# ---------------------------------------------------------------------------
def _preuve(**remplacements) -> Digest:
    base = EvidenceItem(
        document_digest="a" * 64, document_role="annexe",
        reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.2(6)", page_printed=15,
        quote="La valeur recommandee (formule 6.6N) est normative.",
        page_pdf=17,
    )
    return evidence_digest((dataclasses.replace(base, **remplacements),))


def test_retoucher_une_citation_apres_signature_est_detectable() -> None:
    """D1: la citation est la preuve, et la preuve doit être scellée."""
    assert _preuve().digest != _preuve(quote="Autre citation.").digest


def test_changer_le_folio_change_la_preuve() -> None:
    """Le folio est ce qu'un ingénieur rouvre pour contrôler."""
    assert _preuve().digest != _preuve(page_printed=16).digest


def test_la_page_pdf_ne_change_pas_la_preuve() -> None:
    """D2: aide de navigation, sans autorité normative.

    Deux exemplaires du même document peuvent la porter différente — c'est
    arrivé dans ce dépôt, où folio = pdf - 2 pour l'ANB et pas pour la base.
    """
    assert _preuve().digest == _preuve(page_pdf=999).digest


def test_changer_de_document_change_la_preuve() -> None:
    assert _preuve().digest != _preuve(document_digest="b" * 64).digest


def test_l_ordre_des_preuves_compte() -> None:
    """La pile est ordonnée: base, corrigenda, amendement, annexe.

    L'ordre d'application est normatif — un corrigendum appliqué après
    l'annexe ne donne pas le même texte.
    """
    a = EvidenceItem("a" * 64, "base", "EN 1992-1-1", "2004", "§6.2.2(6)", 102, "x")
    b = EvidenceItem("b" * 64, "annexe", "NBN ANB", "2010", "§6.2.2(6)", 15, "y")
    assert evidence_digest((a, b)).digest != evidence_digest((b, a)).digest


def test_changer_le_role_d_un_document_change_la_preuve() -> None:
    """6.2b — lire la même phrase dans la base ou dans l'annexe n'est pas
    la même attestation.

    Le rôle dit à quel étage de la pile la lecture a été faite. Une valeur lue
    dans la base et déclarée comme venant de l'annexe est précisément l'erreur
    que la traçabilité doit rendre visible.
    """
    assert _preuve().digest != _preuve(document_role="base").digest


def test_l_ordre_de_la_pile_normative_est_significatif() -> None:
    """6.2b, autre axe que le précédent: la pile côté SPÉCIFICATION.

    ``expression_sources`` est une suite ordonnée — base, corrigenda,
    amendement, annexe. Permuter deux couches change la règle applicable, donc
    doit changer ``normative_spec_digest``.
    """
    sources = list(R.RHO_W_MIN.expression_sources)
    assert len(sources) >= 2, "il faut au moins deux couches pour permuter"
    permutees = tuple([sources[1], sources[0], *sources[2:]])
    assert _spec_change(R.RHO_W_MIN, expression_sources=permutees)


def test_la_preuve_et_la_specification_sont_deux_axes_independants() -> None:
    """6.2b — « modifier la citation ne change QUE l'empreinte de preuve ».

    Vrai par construction, et c'est ce qu'il faut dire: un ``EvidenceItem``
    n'appartient pas à une règle. La preuve est portée par une CONFIRMATION,
    qui n'existe pas encore — c'est l'objet du jalon 6.3. Aucune des deux
    empreintes d'une règle ne peut donc bouger quand une citation change.
    """
    import json

    for regle in all_rules():
        for empreinte in (normative_spec_digest(regle), implementation_digest(regle)):
            payload = json.loads(empreinte.canonical_payload)
            assert "quote" not in empreinte.canonical_payload, regle.rule_id
            assert "page_printed" not in payload, regle.rule_id
            assert "evidence" not in payload, regle.rule_id

    # Et symétriquement, l'empreinte de preuve ne porte aucune mathématique.
    preuve = json.loads(_preuve().canonical_payload)
    assert set(preuve["items"][0]) == {
        "document_digest", "document_role", "reference", "edition", "clause",
        "page_printed", "quote", "quote_digest",
    }


def test_la_citation_est_scellee_par_son_propre_digest() -> None:
    """Le texte ET son empreinte: retoucher l'un sans l'autre est détectable."""
    import json

    preuve = json.loads(_preuve().canonical_payload)
    item = preuve["items"][0]
    import hashlib

    assert item["quote_digest"] == hashlib.sha256(
        item["quote"].encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Toutes les règles, et rien de confirmé
# ---------------------------------------------------------------------------
def test_chaque_regle_declaree_produit_ses_trois_empreintes() -> None:
    """Aucune règle du registre ne doit être hors de portée de la méthode."""
    for regle in all_rules():
        spec = normative_spec_digest(regle)
        impl = implementation_digest(regle)
        for d in (spec, impl):
            assert len(d.digest) == 64
            assert d.canonical_payload.startswith("{")
            assert d.canonicalization_version == CANONICALIZATION_VERSION


def test_calculer_une_empreinte_ne_confirme_rien() -> None:
    """Une empreinte décrit; elle ne valide pas.

    Le jalon 6.2 ne crée aucune confirmation: la validation normative humaine
    reste entièrement due.
    """
    from eurostruct_engine.ndp.model import ValidationStatus

    for regle in all_rules():
        normative_spec_digest(regle)
        implementation_digest(regle)
        assert regle.validation_status is ValidationStatus.PENDING_VERIFICATION
        assert not regle.usable_in_strict_mode
