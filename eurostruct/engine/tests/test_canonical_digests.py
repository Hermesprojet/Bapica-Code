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

import pytest

from eurostruct_engine.ndp import rules_be_ec2 as R
from eurostruct_engine.ndp.canonical import (
    CANONICALIZATION_VERSION,
    EXTERNAL_BOUNDARY,
    Digest,
    EvidenceItem,
    UnresolvableDependency,
    canonical_json,
    digest_of,
    evidence_digest,
    implementation_digest,
    normative_spec_digest,
)
from eurostruct_engine.ndp.rules import all_rules
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
    from eurostruct_engine.ndp.rules import Branch

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
    externes = [f["external_callable"] for f in fragments if "external_callable" in f]

    assert any("_rho_w_min" in f for f in fonctions)
    assert "math" in modules, "math.sqrt est utilise et doit etre trace"
    assert any("pint" in e for e in externes), "Q_ vient de Pint"
    # Chaque dependance externe porte sa version: une mise a jour de Pint ou
    # de Python change l'empreinte, elle ne passe pas inapercue.
    for f in fragments:
        if "module" in f or "external_callable" in f:
            assert f["version"], f"{f}: dependance externe sans version"


def test_la_frontiere_externe_est_courte_et_declaree() -> None:
    """Chaque entrée est une chose que l'empreinte ne surveille plus en détail.

    Le rappeler par un test empêche qu'elle s'allonge sans qu'on s'en aperçoive:
    allonger la frontière, c'est réduire ce que l'empreinte garantit.
    """
    assert EXTERNAL_BOUNDARY == frozenset({"math", "builtins", "pint"})


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
    with pytest.raises(UnresolvableDependency, match="hors de la fronti"):
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
