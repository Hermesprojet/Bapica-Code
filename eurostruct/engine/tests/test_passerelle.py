"""La passerelle: seule une confirmation exacte ouvre le portillon du strict.

CE QUE CE MODULE ÉPROUVE
-------------------------
Que le mode strict ne s'ouvre **que** par le chemin d'autorité, et que chaque
écart le referme. Les cas négatifs sont la matière principale : c'est un
portillon, et un portillon se juge sur ce qu'il refuse.

TOUTES LES FIXTURES POSITIVES SONT EXPLICITEMENT FICTIVES
----------------------------------------------------------
Les identités portent le préfixe ``FICTIF``, les empreintes de document sont
des chaînes reconnaissables, et rien de ce fichier n'est utilisable comme
donnée normative. **Aucune valeur nationale réelle n'est confirmée ici** : le
registre livré reste à 0 confirmation sur 29, et un cas le vérifie.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime

import pytest

from eurostruct_engine.ndp.canonical import (
    CANONICALIZATION_VERSION,
    digest_of,
)
from eurostruct_engine.ndp.confirmation import (
    ConfirmationPolicy,
    ConfirmationStatus,
    EvidenceItem,
    NormativeReviewPackage,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
    NormativeStack,
    NormativeStackComponent,
)
from eurostruct_engine.ndp.model import (
    NationalAnnex,
    NationalParameter,
    RegulatoryFramework,
    SourceType,
    ValidationStatus,
    ValueProvenance,
)
from eurostruct_engine.ndp.passerelle import (
    POLITIQUE_PAR_DEFAUT,
    appliquer_confirmations,
    evaluer_parametre,
)
from eurostruct_engine.ndp.registry import CountryRegistry, ParameterSet

#: Un cadre FICTIF. Il n'entre dans aucun controle de la passerelle: il est la
#: parce que `CountryRegistry` l'exige, et il est nomme fictif pour qu'on ne
#: puisse pas le confondre avec le cadre reel d'un pays.
CADRE = RegulatoryFramework(
    binding_reference="FICTIF — cadre de test",
    eurocode_status="FICTIF",
    verification_regime="FICTIF",
    notes="FICTIF — aucune portee normative.",
)


def registre(annexes) -> CountryRegistry:
    return CountryRegistry(country_code="BE", country_name="FICTIF Belgique",
                           regulatory_framework=CADRE, annexes=tuple(annexes))

FICTIF = "FICTIF-"
DOC_ANB = "d" * 64
DOC_AUTRE = "f" * 64
INSTANT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
AU = date(2026, 8, 30)

CLE = "EN 1992-1-1:alpha_cc"
VALEUR = 0.85
EDITION = "2010"
ANNEXE_REF = "FICTIF NBN EN 1992-1-1 ANB"


# ---------------------------------------------------------------- le registre
def parametre(**ecarts) -> NationalParameter:
    """Un paramètre national **fictif**, complet et cohérent."""
    champs = {
        "country_code": "BE",
        "standard_family": "EN 1992",
        "part": "1-1",
        "national_annex_reference": ANNEXE_REF,
        "edition": EDITION,
        "effective_from": date(2010, 1, 1),
        "effective_to": None,
        "parameter_name": "alpha_cc",
        "parameter_value": VALEUR,
        "unit": "dimensionless",
        "source_official": "FICTIF NBN",
        "source_url_or_doc_id": None,
        "source_doc_id": DOC_ANB,
        "source_page": 22,
        "source_type": SourceType.NATIONAL_ANNEX,
        "validation_status": ValidationStatus.PENDING_VERIFICATION,
        "verified_at": None,
        "verified_by": None,
        "notes": None,
        "clause": "§3.1.6(1)P",
        "description": "FICTIF — coefficient de longue duree",
        "en_recommended": 1.0,
        "value_provenance": ValueProvenance.NATIONAL_ANNEX,
    }
    champs.update(ecarts)
    return NationalParameter(**champs)


def jeu_de(p: NationalParameter, *, strict: bool = True) -> ParameterSet:
    annexe = NationalAnnex(
        country_code=p.country_code, standard_family=p.standard_family,
        part=p.part, reference=p.national_annex_reference, edition=p.edition,
        effective_from=date(2010, 1, 1), effective_to=None,
        source_official="FICTIF NBN", source_url_or_doc_id=None,
        parameters=(p,),
    )
    return ParameterSet(
        registry=registre((annexe,)),
        region=None, as_of=AU, strict=strict,
    )


# ------------------------------------------------------------ le dossier signé
def payload_de_spec(**ecarts) -> dict:
    """La forme que ``normative_spec_digest`` produit, valeur comprise."""
    charge = {
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": CLE,
        "rule_type": "scalar",
        "output_unit": "dimensionless",
        "value_provenance": "national_annex",
        "scalar_value": VALEUR,
        "inputs": [],
        "domain": [],
        "expression_sources": [],
        "normative_authority": {
            "country_code": "BE",
            "reference": ANNEXE_REF,
            "edition": EDITION,
            "clause": "§3.1.6(1)P",
            "effect": "FICTIF — fixe la valeur nationale",
            "document_digest": DOC_ANB,
        },
    }
    autorite = ecarts.pop("normative_authority", None)
    charge.update(ecarts)
    if autorite:
        charge["normative_authority"] = {**charge["normative_authority"],
                                         **autorite}
    return charge


IMPL = digest_of({"regle": CLE, "quoi": "FICTIF implementation"})
IMPL_AUTRE = digest_of({"regle": CLE, "quoi": "FICTIF autre implementation"})


def pile(*, edition: str = EDITION, doc: str = DOC_ANB) -> NormativeStack:
    return NormativeStack.of(
        country_code="BE", standard_family="EN 1992", part="1-1",
        components=(
            NormativeStackComponent("annexe", ANNEXE_REF, edition, 1, doc),
        ),
    )


def dossier(spec) -> tuple[EvidenceItem, ...]:
    """Une preuve par source déclarée, exactement."""
    from eurostruct_engine.ndp.confirmation import required_sources

    return tuple(
        EvidenceItem(
            document_digest=s.document_digest, document_role=s.role,
            reference=s.reference, edition=s.edition or EDITION,
            clause=s.clause, page_printed=22,
            quote="FICTIF — citation relevee a la page indiquee.",
            page_pdf=None,
        )
        for s in required_sources(spec)
    )


def paquet(*, spec=None, impl=IMPL, rule_id: str = CLE,
           stack: NormativeStack | None = None,
           country_code: str = "BE") -> NormativeReviewPackage:
    spec = spec if spec is not None else digest_of(payload_de_spec())
    return NormativeReviewPackage.of(
        country_code=country_code, standard_family="EN 1992", part="1-1",
        rule_id=rule_id, stack=stack or pile(), normative_spec=spec,
        implementation=impl, evidence_items=dossier(spec),
    )


def confirmation(p: NormativeReviewPackage, qui: str) -> NormativeRuleConfirmation:
    return NormativeRuleConfirmation.for_package(
        p,
        confirmation_id=f"{FICTIF}conf-{qui}",
        verifier_id=f"{FICTIF}{qui}",
        verifier_name=f"FICTIF {qui.title()}",
        verified_at=INSTANT,
        authorisations_at_signature=frozenset({"can_validate_normative_reference"}),
        authorisation_scope_at_signature="BE/EN 1992/1-1",
        statement="FICTIF — j'ai relu l'annexe a la page indiquee.",
        idempotency_key=f"{FICTIF}idem-{qui}",
    )


class Fournisseur:
    """Un provider **fictif**, qui rend ce qu'on lui a donné.

    Il porte ``is_fictional = True`` : rien de ce module ne peut être pris pour
    une confirmation réelle.
    """

    provider_identity = "FICTIF://passerelle-tests"
    is_fictional = True

    def __init__(self, confirmations=(), revocations=()) -> None:
        self._c = tuple(confirmations)
        self._r = tuple(revocations)

    def confirmations_for(self, rule_id: str):
        return tuple(c for c in self._c if c.rule_id == rule_id)

    def revocations_for(self, rule_id: str):
        return self._r


def deux_signatures(p: NormativeReviewPackage) -> Fournisseur:
    return Fournisseur((confirmation(p, "alice"), confirmation(p, "bob")))


# ===========================================================================
# 1. LE CHEMIN QUI OUVRE — et il est le seul
# ===========================================================================
def test_deux_regards_sur_le_sujet_exact_rendent_le_parametre_utilisable() -> None:
    """Le cas positif, et tout ce qu'il a fallu pour l'obtenir."""
    p = parametre()
    dossier_signe = paquet()
    jeu = jeu_de(p)

    assert not p.usable_in_strict_mode          # au depart: rien
    apres, rapports = appliquer_confirmations(
        jeu, {CLE: dossier_signe}, provider=deux_signatures(dossier_signe))

    assert len(rapports) == 1
    assert rapports[0].status is ConfirmationStatus.CONFIRMED
    assert rapports[0].usable
    assert rapports[0].verifiers == {f"{FICTIF}alice", f"{FICTIF}bob"}

    confirme = apres.find(CLE)
    assert confirme is not None
    assert confirme.usable_in_strict_mode
    # LA VALEUR N'A PAS BOUGE. La superposition ne touche que le statut.
    assert confirme.parameter_value == VALEUR
    assert confirme.unit == p.unit
    assert confirme.value_provenance is p.value_provenance


def test_le_preflight_strict_s_ouvre_alors_pour_CE_parametre() -> None:
    """Le fait produit: le portillon laisse passer, et il est le vrai."""
    dossier_signe = paquet()
    jeu = jeu_de(parametre())

    assert not jeu.preflight([CLE]).ok
    apres, _ = appliquer_confirmations(
        jeu, {CLE: dossier_signe}, provider=deux_signatures(dossier_signe))
    assert apres.preflight([CLE]).ok


def test_le_jeu_d_origine_n_est_pas_modifie() -> None:
    """Aucun effet de bord: un appelant qui n'est pas passe par la ne voit rien."""
    dossier_signe = paquet()
    jeu = jeu_de(parametre())
    appliquer_confirmations(jeu, {CLE: dossier_signe},
                            provider=deux_signatures(dossier_signe))
    assert not jeu.preflight([CLE]).ok
    assert not jeu.find(CLE).usable_in_strict_mode


# ===========================================================================
# 2. CE QUI NE SUFFIT PAS — et chaque cas nomme sa raison
# ===========================================================================
def test_aucune_confirmation_ne_suffit_pas() -> None:
    dossier_signe = paquet()
    rapport = evaluer_parametre(parametre(), dossier_signe,
                                provider=Fournisseur())
    assert rapport.status is ConfirmationStatus.UNCONFIRMED
    assert not rapport.usable


def test_un_seul_signataire_ne_suffit_pas() -> None:
    """UN SEUL REGARD N'EST PAS DEUX. C'est toute la regle du quatre-yeux."""
    dossier_signe = paquet()
    rapport = evaluer_parametre(
        parametre(), dossier_signe,
        provider=Fournisseur((confirmation(dossier_signe, "alice"),)))
    assert rapport.status is ConfirmationStatus.PARTIALLY_CONFIRMED
    assert not rapport.usable


def test_le_meme_signataire_deux_fois_ne_fait_pas_deux_regards() -> None:
    """Deux attestations, un seul verificateur: toujours un seul regard."""
    dossier_signe = paquet()
    deux = (confirmation(dossier_signe, "alice"),
            dataclasses.replace(confirmation(dossier_signe, "alice"),
                                confirmation_id=f"{FICTIF}conf-alice-bis",
                                idempotency_key=f"{FICTIF}idem-alice-bis"))
    rapport = evaluer_parametre(parametre(), dossier_signe,
                                provider=Fournisseur(deux))
    assert not rapport.usable
    assert rapport.verifiers == {f"{FICTIF}alice"}


def test_une_confirmation_revoquee_ne_compte_pas() -> None:
    dossier_signe = paquet()
    signatures = (confirmation(dossier_signe, "alice"),
                  confirmation(dossier_signe, "bob"))
    revocations = tuple(
        NormativeRuleConfirmationRevocation(
            revocation_id=f"{FICTIF}rev-{i}",
            confirmation_id=c.confirmation_id,
            revoked_by=f"{FICTIF}carol",
            revoked_by_name="FICTIF Carol",
            revoked_at=INSTANT,
            authorisations_at_revocation=frozenset(
                {"can_validate_normative_reference"}),
            reason="FICTIF — relecture erronee",
        )
        for i, c in enumerate(signatures)
    )
    rapport = evaluer_parametre(
        parametre(), dossier_signe,
        provider=Fournisseur(signatures, revocations))
    assert rapport.status is ConfirmationStatus.REVOKED
    assert not rapport.usable


def test_aucun_dossier_ne_suffit_pas() -> None:
    rapport = evaluer_parametre(parametre(), None, provider=Fournisseur())
    assert rapport.status is None
    assert not rapport.usable
    assert "aucun dossier" in rapport.reason


# ===========================================================================
# 3. LA CORRESPONDANCE EXACTE — chaque ecart referme le portillon
# ===========================================================================
@pytest.mark.parametrize("nom,ecarts,motif", [
    ("valeur", {"scalar_value": 1.0}, "valeur"),
    ("unite", {"output_unit": "MPa"}, "unite"),
    ("provenance", {"value_provenance": "eurocode_recommended"}, "provenance"),
    ("edition", {"normative_authority": {"edition": "2018"}}, "edition"),
    ("annexe", {"normative_authority": {"reference": "FICTIF AUTRE ANB"}},
     "annexe"),
    ("document", {"normative_authority": {"document_digest": DOC_AUTRE}},
     "document"),
])
def test_un_ecart_dans_la_specification_referme_le_portillon(
        nom, ecarts, motif) -> None:
    """LE DOSSIER PEUT ETRE SIGNE DEUX FOIS ET NE RIEN CONFIRMER ICI.

    Les deux signatures sont authentiques et le dossier est cohérent — il
    porte simplement sur autre chose que ce que le registre détient.
    """
    spec = digest_of(payload_de_spec(**ecarts))
    dossier_signe = paquet(spec=spec)
    rapport = evaluer_parametre(parametre(), dossier_signe,
                                provider=deux_signatures(dossier_signe))
    assert not rapport.usable, f"l'ecart de {nom} n'a pas ete vu"
    assert motif in rapport.reason


def test_une_mauvaise_empreinte_d_implementation_referme_le_portillon() -> None:
    """LE CODE QUI EXECUTE FAIT PARTIE DU SUJET.

    Les deux ingenieurs ont signe le comportement d'une implementation
    precise. Une autre implementation, meme correcte, n'a pas ete relue.
    """
    signe = paquet(impl=IMPL)
    autre = paquet(impl=IMPL_AUTRE)
    rapport = evaluer_parametre(parametre(), autre,
                                provider=deux_signatures(signe))
    assert not rapport.usable
    assert rapport.status is ConfirmationStatus.UNCONFIRMED


def test_une_mauvaise_empreinte_de_specification_referme_le_portillon() -> None:
    """Les attestations portent sur une spec, le paquet presente en est une autre."""
    signe = paquet()
    # Meme valeur, mais une clause differente: autre payload, autre empreinte.
    autre = paquet(spec=digest_of(payload_de_spec(
        normative_authority={"clause": "§3.1.6(2)"})))
    rapport = evaluer_parametre(parametre(), autre,
                                provider=deux_signatures(signe))
    assert not rapport.usable


def test_un_mauvais_pays_referme_le_portillon() -> None:
    rapport = evaluer_parametre(
        parametre(country_code="FR"), paquet(), provider=Fournisseur())
    assert not rapport.usable
    assert "pays" in rapport.reason


def test_une_autre_regle_referme_le_portillon() -> None:
    """LA GARDE EST EN AMONT, ET C'EST MIEUX AINSI.

    `NormativeReviewPackage` refuse deja qu'un paquet annonce une regle et
    porte l'empreinte d'une autre: le dossier n'existe meme pas. La passerelle
    n'a donc jamais l'occasion de le voir — et son propre controle de `rule_id`
    reste utile pour un paquet coherent portant sur une AUTRE regle, ce que le
    cas suivant montre.
    """
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    with pytest.raises(ConfirmationDomainError, match="annonce la regle"):
        paquet(rule_id="EN 1992-1-1:gamma_C")


def test_un_dossier_coherent_portant_sur_une_AUTRE_regle_est_refuse() -> None:
    """Le dossier est valide, signe deux fois, et parle d'autre chose."""
    autre = paquet(spec=digest_of(payload_de_spec(
        rule_id="EN 1992-1-1:gamma_C")), rule_id="EN 1992-1-1:gamma_C")
    rapport = evaluer_parametre(parametre(), autre,
                                provider=deux_signatures(autre))
    assert not rapport.usable
    assert "regle" in rapport.reason


def test_une_pile_a_une_autre_edition_referme_le_portillon() -> None:
    """La meme regle confirmee pour deux editions fait DEUX sujets."""
    rapport = evaluer_parametre(
        parametre(), paquet(stack=pile(edition="2018")),
        provider=Fournisseur())
    assert not rapport.usable
    assert "edition" in rapport.reason


def test_une_pile_portant_un_autre_document_referme_le_portillon() -> None:
    rapport = evaluer_parametre(
        parametre(), paquet(stack=pile(doc=DOC_AUTRE)),
        provider=Fournisseur())
    assert not rapport.usable


def test_sans_empreinte_de_document_le_registre_ne_peut_rien_confirmer() -> None:
    """RIEN NE RELIE ALORS LA SIGNATURE AU FICHIER QUI A ETE LU.

    Le refus est explicite plutot que silencieux: on ne fabrique pas
    l'empreinte manquante, et on dit laquelle manque.
    """
    dossier_signe = paquet()
    rapport = evaluer_parametre(parametre(source_doc_id=None), dossier_signe,
                                provider=deux_signatures(dossier_signe))
    assert not rapport.usable
    assert "source_doc_id" in rapport.reason


def test_un_parametre_absent_du_registre_ne_se_confirme_pas() -> None:
    """Un dossier ne peut pas confirmer ce que le registre ne detient pas.

    Le dossier est ici parfaitement coherent — regle annoncee et regle signee
    concordent — mais le registre n'a aucun parametre de ce nom en vigueur.
    """
    inconnue = "EN 1992-1-1:inexistant"
    jeu = jeu_de(parametre())
    _, rapports = appliquer_confirmations(
        jeu,
        {inconnue: paquet(spec=digest_of(payload_de_spec(rule_id=inconnue)),
                          rule_id=inconnue)},
        provider=Fournisseur())
    assert not rapports[0].usable
    assert "aucun parametre de ce nom" in rapports[0].reason


# ===========================================================================
# 4. LA SUPERPOSITION EST ETROITE
# ===========================================================================
def test_seule_la_regle_correspondante_devient_utilisable() -> None:
    """Confirmer alpha_cc n'ouvre pas gamma_C, qui n'a rien recu."""
    alpha = parametre()
    gamma = parametre(parameter_name="gamma_C", parameter_value=1.5,
                      source_doc_id=DOC_ANB)
    annexe = NationalAnnex(
        country_code="BE", standard_family="EN 1992", part="1-1",
        reference=ANNEXE_REF, edition=EDITION,
        effective_from=date(2010, 1, 1), effective_to=None,
        source_official="FICTIF NBN", source_url_or_doc_id=None,
        parameters=(alpha, gamma),
    )
    jeu = ParameterSet(
        registry=registre((annexe,)),
        region=None, as_of=AU, strict=True)

    dossier_signe = paquet()
    apres, _ = appliquer_confirmations(
        jeu, {CLE: dossier_signe}, provider=deux_signatures(dossier_signe))

    assert apres.find(CLE).usable_in_strict_mode
    assert not apres.find("EN 1992-1-1:gamma_C").usable_in_strict_mode
    # Et le preflight d'un calcul qui exige LES DEUX refuse toujours.
    assert not apres.preflight([CLE, "EN 1992-1-1:gamma_C"]).ok


def test_une_politique_plus_exigeante_est_honoree() -> None:
    """Trois regards exiges, deux fournis: refus."""
    dossier_signe = paquet()
    rapport = evaluer_parametre(
        parametre(), dossier_signe, provider=deux_signatures(dossier_signe),
        policy=ConfirmationPolicy(policy_version="esc-policy/3-yeux",
                                  minimum_independent_confirmations=3))
    assert not rapport.usable


def test_la_politique_par_defaut_exige_bien_deux_regards() -> None:
    assert POLITIQUE_PAR_DEFAUT.minimum_independent_confirmations == 2


# ===========================================================================
# 5. LE REFERENTIEL LIVRE RESTE A ZERO
# ===========================================================================
def test_le_referentiel_livre_n_a_aucune_confirmation() -> None:
    """LA REALITE 0/29 EST CONSERVEE, ET ELLE EST VERIFIEE ICI.

    Ce module ne rend pas le strict possible: il rend possible qu'il le
    devienne. Aucun pays livre n'a de valeur nationale confirmee, et aucun
    fichier du depot ne peut en produire une.
    """
    from eurostruct_engine.ndp import available_countries, load_parameter_set

    for pays in available_countries():
        jeu = load_parameter_set(pays, strict=True, as_of=AU)
        confirmes = [k for k in jeu.keys()  # noqa: SIM118 — methode du domaine, pas un dict
                     if (p := jeu.find(k)) is not None
                     and p.usable_in_strict_mode]
        assert confirmes == [], (
            f"{pays}: {len(confirmes)} parametre(s) deja utilisable(s) en "
            "mode strict sans passer par le chemin d'autorite")


def test_un_fichier_du_depot_ne_peut_pas_porter_confirmed() -> None:
    """La seconde porte de la meme piece, verifiee depuis ce module.

    La passerelle n'a de sens que si l'autre chemin reste ferme: pouvoir
    ecrire « confirmed » dans un JSON rendrait tout ce module decoratif.
    """
    from eurostruct_engine.ndp.registry import _statut_transcrit

    with pytest.raises(ValueError, match="ne peut pas porter le statut"):
        _statut_transcrit("confirmed", "BE", "EN 1992-1-1:alpha_cc")


def test_la_specification_signee_porte_bien_la_valeur() -> None:
    """Garde de la garde: si le payload cessait de porter la valeur, le
    controle de valeur ne comparerait plus rien et passerait toujours.

    LA CANONICALISATION ENVELOPPE LES FLOTTANTS (`{"__float__": "0.85"}`):
    comparer au flottant nu passerait a cote. On compare donc les deux formes
    canoniques, ce que la passerelle fait aussi.
    """
    from eurostruct_engine.ndp.canonical import canonical_json

    charge = json.loads(digest_of(payload_de_spec()).canonical_payload)
    assert charge["scalar_value"] == json.loads(canonical_json(VALEUR))
    assert charge["value_provenance"] == "national_annex"


# ===========================================================================
# 6. LE CHEMIN REEL: le calcul ne connait que le parametre et le provider
# ===========================================================================
def test_le_chemin_reel_ouvre_sur_deux_regards_exacts() -> None:
    """Sans qu'aucun paquet ne lui soit fourni, la passerelle le relit."""
    from eurostruct_engine.ndp.passerelle import confirmer_depuis_le_provider

    dossier_signe = paquet()
    jeu = jeu_de(parametre())
    apres, rapports = confirmer_depuis_le_provider(
        jeu, (CLE,), provider=deux_signatures(dossier_signe))

    assert rapports[0].status is ConfirmationStatus.CONFIRMED
    assert apres.preflight([CLE]).ok


def test_le_chemin_reel_sans_attestation_dit_pourquoi() -> None:
    from eurostruct_engine.ndp.passerelle import confirmer_depuis_le_provider

    jeu = jeu_de(parametre())
    apres, rapports = confirmer_depuis_le_provider(
        jeu, (CLE,), provider=Fournisseur())

    assert rapports[0].status is ConfirmationStatus.UNCONFIRMED
    assert "chemin d'autorite" in rapports[0].reason
    assert not apres.preflight([CLE]).ok
    assert apres is jeu          # rien n'a ete reconstruit pour rien


def test_deux_signataires_ne_peuvent_pas_faire_dire_au_registre_autre_chose() -> None:
    """LE CAS QUI JUSTIFIE DE RELIRE LE PAQUET DANS L'ATTESTATION.

    Le dossier candidat vient de l'attestation, donc de ceux qui signent. Deux
    verificateurs qui s'entendraient definiraient ainsi leur propre sujet — et
    c'est vrai. Ce que ce cas montre, c'est ou s'arrete leur pouvoir: ils
    signent un dossier portant 1,00, le registre porte 0,85, et le parametre
    reste bloque. La garantie ne vient pas de la forme, elle vient du registre,
    qui n'est pas sous leur controle.
    """
    from eurostruct_engine.ndp.passerelle import confirmer_depuis_le_provider

    menteur = paquet(spec=digest_of(payload_de_spec(scalar_value=1.0)))
    jeu = jeu_de(parametre())          # le registre porte 0.85
    apres, rapports = confirmer_depuis_le_provider(
        jeu, (CLE,), provider=deux_signatures(menteur))

    assert not rapports[0].usable
    assert "valeur" in rapports[0].reason
    assert not apres.preflight([CLE]).ok


def test_le_chemin_reel_conserve_la_realite_du_referentiel_livre() -> None:
    """SUR LE VRAI REGISTRE, LE VERDICT NE BOUGE PAS: rien n'est confirme.

    C'est le fait produit central, et il doit rester vrai APRES le
    branchement: brancher la passerelle ne debloque rien par elle-meme.
    """
    from eurostruct_engine.basis import DesignSituation
    from eurostruct_engine.ec2.beam_flexure import required_parameters
    from eurostruct_engine.ndp import available_countries, load_parameter_set
    from eurostruct_engine.ndp.passerelle import confirmer_depuis_le_provider

    exiges = tuple(required_parameters(DesignSituation.PERSISTENT))
    for pays in available_countries():
        jeu = load_parameter_set(pays, strict=True, as_of=AU)
        apres, rapports = confirmer_depuis_le_provider(
            jeu, exiges, provider=Fournisseur())
        assert not apres.preflight(exiges).ok, (
            f"{pays}: le preflight strict passe alors qu'aucune valeur n'est "
            "confirmee")
        assert all(not r.usable for r in rapports)


# ===========================================================================
# 7. LE CALCUL LUI-MEME: la passerelle est sur le chemin, pas a cote
# ===========================================================================
#
# CE QUE CES DEUX CAS ETABLISSENT ENSEMBLE. Le premier montre que le calcul
# strict refuse aujourd'hui — la realite 0/29, inchangee. Le second montre que
# ce refus tient a l'ABSENCE de confirmation et non a une porte condamnee: le
# meme calcul aboutit des lors qu'un provider rend deux attestations exactes.
#
# Sans le second, on ne saurait pas distinguer « le portillon fonctionne » de
# « le portillon est mure ».

def _requete_stricte(pays: str = "BE") -> dict:
    return {
        "project_id": "FICTIF-001", "element": "P1", "country": pays,
        "strict_ndp": True,
        "M_Ed": {"value": 150, "unit": "kN*m"},
        "section": {"b": {"value": 300, "unit": "mm"},
                    "h": {"value": 500, "unit": "mm"},
                    "d": {"value": 450, "unit": "mm"}},
        "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
    }


def test_le_calcul_strict_refuse_aujourd_hui_meme_avec_un_provider() -> None:
    """0/29 CONSERVE. Un provider branche mais sans attestation ne debloque rien."""
    from eurostruct_engine.exceptions import NationalAnnexIncomplete
    from eurostruct_engine.schemas.ec2_beam import Ec2BeamFlexureRequest
    from eurostruct_engine.service import run_ec2_beam_flexure

    requete = Ec2BeamFlexureRequest.model_validate(_requete_stricte())
    with pytest.raises(NationalAnnexIncomplete):
        run_ec2_beam_flexure(requete, provider=Fournisseur())


def test_sans_provider_le_calcul_strict_refuse_AUSSI() -> None:
    """FAIL-CLOSED: l'absence de source de confirmation ne debloque rien."""
    from eurostruct_engine.exceptions import NationalAnnexIncomplete
    from eurostruct_engine.schemas.ec2_beam import Ec2BeamFlexureRequest
    from eurostruct_engine.service import run_ec2_beam_flexure

    requete = Ec2BeamFlexureRequest.model_validate(_requete_stricte())
    with pytest.raises(NationalAnnexIncomplete):
        run_ec2_beam_flexure(requete)


def test_le_calcul_strict_ABOUTIT_quand_tous_les_parametres_sont_confirmes() -> None:
    """LE CAS QUI PROUVE QUE LE PORTILLON N'EST PAS MURE.

    On confirme, par le chemin d'autorite et pour ce seul test, les huit
    parametres que la flexion demande — sur le registre REEL, avec les valeurs
    REELLES qu'il porte. Rien n'est invente: chaque dossier fictif reprend la
    valeur, l'unite, la provenance, l'edition et l'empreinte de document du
    registre, faute de quoi la passerelle le refuserait.

    Les DEUX signataires sont fictifs et nommes comme tels. Aucune donnee de ce
    cas n'existe hors du processus de test.
    """
    from eurostruct_engine.basis import DesignSituation
    from eurostruct_engine.ec2.beam_flexure import required_parameters
    from eurostruct_engine.ndp import load_parameter_set
    from eurostruct_engine.schemas.ec2_beam import Ec2BeamFlexureRequest
    from eurostruct_engine.service import run_ec2_beam_flexure

    jeu = load_parameter_set("BE", strict=True)
    exiges = tuple(required_parameters(DesignSituation.PERSISTENT))

    signatures = []
    sautes = []
    for cle in exiges:
        p = jeu.find(cle)
        assert p is not None, cle
        if not p.source_doc_id:
            # SANS EMPREINTE DE DOCUMENT, RIEN NE PEUT ETRE CONFIRME — et ce
            # n'est pas un defaut du test: c'est ce que la passerelle refuse.
            sautes.append(cle)
            continue
        charge = payload_de_spec(
            rule_id=cle,
            scalar_value=p.parameter_value,
            output_unit=p.unit,
            value_provenance=p.value_provenance.value,
            normative_authority={
                "country_code": p.country_code,
                "reference": p.national_annex_reference,
                "edition": p.edition,
                "clause": p.clause,
                "effect": "FICTIF — fixe la valeur nationale",
                "document_digest": p.source_doc_id,
            },
        )
        spec = digest_of(charge)
        dossier_signe = NormativeReviewPackage.of(
            country_code=p.country_code, standard_family=p.standard_family,
            part=p.part, rule_id=cle,
            stack=NormativeStack.of(
                country_code=p.country_code,
                standard_family=p.standard_family, part=p.part,
                components=(NormativeStackComponent(
                    "annexe", p.national_annex_reference, p.edition, 1,
                    p.source_doc_id),),
            ),
            normative_spec=spec, implementation=IMPL,
            evidence_items=dossier(spec),
        )
        signatures.extend((confirmation(dossier_signe, "alice"),
                           confirmation(dossier_signe, "bob")))

    assert not sautes, (
        "des parametres requis n'ont pas d'empreinte de document deposee: "
        f"{sautes}. Le cas ne pourrait pas etre concluant.")

    requete = Ec2BeamFlexureRequest.model_validate(_requete_stricte())
    reponse = run_ec2_beam_flexure(requete, provider=Fournisseur(signatures))
    assert reponse.result.As_required.value > 0

    # ET LE MEME CALCUL, AVEC UN SEUL SIGNATAIRE PAR PARAMETRE, REFUSE.
    from eurostruct_engine.exceptions import NationalAnnexIncomplete

    seuls = [c for c in signatures if c.verifier_id == f"{FICTIF}alice"]
    with pytest.raises(NationalAnnexIncomplete):
        run_ec2_beam_flexure(requete, provider=Fournisseur(seuls))
