"""Le chemin strict belge COMPLET, du dossier de revue aux cinq chapitres.

CE QUE CE FICHIER ETABLIT, ET CE QU'IL N'ETABLIT PAS
-----------------------------------------------------
Il etablit que **le produit sait aller au bout**: composer, par son propre
code, le dossier de revue de chacun des parametres que la verification de
poutre reclame en Belgique, recevoir deux regards independants sur chacun, et
rendre les cinq chapitres en mode strict.

Jusqu'au 13/09 c'etait impossible, et pas pour une raison logicielle:
`EN 1992-1-1:w_max` portait la provenance `national_annex_pending`, et la
passerelle refusait — a juste titre — de confirmer une valeur que personne
n'avait relevee dans l'Annexe Nationale publiee. La lecture du
Tableau 7.1N-ANB (folio 18, page PDF 20) a leve ce blocage documentaire.

Il n'etablit **rien** sur la validite normative du referentiel. Les deux
signataires sont fictifs, le provider se declare fictif, et aucune de ces
confirmations n'existe hors du processus de test. Le registre reel reste a
0 confirmee sur 116 — c'est `test_ndp.py` qui le mesure, et c'est vrai apres
ce fichier comme avant.

Aucune identite reelle, aucun secret, aucune base de donnees.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime

import pytest

from eurostruct_engine.ec2.beam_verification import (
    BeamGeometry,
    BeamVerificationInput,
    LongitudinalBars,
    TransverseLinks,
    preflight_beam,
    required_parameters_for_beam,
    resolve_beam_context,
    verify_beam,
)
from eurostruct_engine.ec2.deflection import StructuralSystem
from eurostruct_engine.ec2.serviceability import ExposureClass
from eurostruct_engine.ndp import load_parameter_set
from eurostruct_engine.ndp.canonical import EvidenceItem
from eurostruct_engine.ndp.confirmation import (
    NormativeReviewPackage,
    NormativeRuleConfirmation,
    required_sources,
)
from eurostruct_engine.ndp.dossier import CitationDeRevue, composer_dossier
from eurostruct_engine.ndp.passerelle import evaluer_depuis_le_provider
from eurostruct_engine.units import Q_

FICTIF = "FICTIF-"
INSTANT = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)
AU = date(2026, 9, 13)
PAYS = "BE"
W_MAX = "EN 1992-1-1:w_max"

#: La poutre du parcours de reference: 300 x 600, portee 6 m, C30/37, B500B,
#: 4 HA20 en travee, cadres HA8 tous les 200 mm, classe XC3 — la classe dont
#: le Tableau 7.1N-ANB donne 0,30 mm.
POUTRE = BeamVerificationInput(
    element="P1",
    geometry=BeamGeometry(b=Q_(300, "mm"), h=Q_(600, "mm"),
                          d=Q_(550, "mm"), l_eff=Q_(6.0, "m")),
    concrete_grade="C30/37",
    steel_grade="B500B",
    M_Ed=Q_(180, "kN*m"), V_Ed=Q_(150, "kN"),
    M_char=Q_(140, "kN*m"), M_qp=Q_(100, "kN*m"),
    phi_creep=2.0,
    exposure_class=ExposureClass.XC3,
    system=StructuralSystem.SIMPLY_SUPPORTED,
    bars=LongitudinalBars(count=4, diameter=Q_(20, "mm")),
    links=TransverseLinks(legs=2, diameter=Q_(8, "mm"), spacing=Q_(200, "mm")),
    cot_theta=1.0,
    cover=Q_(30, "mm"),
    anchorage_available=Q_(600, "mm"),
)


class FournisseurFictif:
    """Rend les confirmations qu'on lui a donnees, et se declare fictif."""

    provider_identity = "FICTIF://chemin-strict-belge"
    is_fictional = True

    def __init__(self, confirmations=()) -> None:
        self._c = tuple(confirmations)

    def confirmations_for(self, rule_id: str):
        return tuple(c for c in self._c if c.rule_id == rule_id)

    def revocations_for(self, rule_id: str):
        return ()


def _compose(parametre):
    """Le dossier de revue, COMPOSE PAR LE CODE DE PRODUCTION.

    Rien n'est fabrique a la main ici: la specification, l'empreinte
    d'implementation, la pile normative et la preuve sortent toutes de
    `composer_dossier`, c'est-a-dire du meme code que l'ecran de revue. Si le
    produit ne savait pas composer le dossier d'un parametre, le cas
    echouerait ici — et c'est exactement ce qui arrivait a `w_max`.
    """
    return composer_dossier(
        parametre,
        statement=(
            f"FICTIF — relu {parametre.national_annex_reference} "
            f"{parametre.clause}, folio {parametre.source_page}."
        ),
        citations=(CitationDeRevue(
            document_digest=parametre.source_doc_id,
            quote=f"FICTIF — texte relu pour {parametre.parameter_name}.",
            page_printed=parametre.source_page or 1,
        ),),
    )


def _paquet(parametre) -> NormativeReviewPackage:
    compose = _compose(parametre)
    items = tuple(
        EvidenceItem(
            document_digest=s.document_digest, document_role=s.role,
            reference=s.reference, edition=s.edition or parametre.edition,
            clause=s.clause, page_printed=parametre.source_page or 1,
            quote=f"FICTIF — texte relu pour {parametre.parameter_name}.",
            page_pdf=None,
        )
        for s in required_sources(compose.normative_spec)
    )
    return NormativeReviewPackage.of(
        country_code=parametre.country_code,
        standard_family=parametre.standard_family,
        part=parametre.part,
        rule_id=parametre.key,
        stack=compose.stack,
        normative_spec=compose.normative_spec,
        implementation=compose.implementation,
        evidence_items=items,
    )


def _signatures(paquet: NormativeReviewPackage, nom: str) -> list:
    return [
        NormativeRuleConfirmation.for_package(
            paquet,
            confirmation_id=f"{FICTIF}conf-{qui}-{nom}",
            verifier_id=f"{FICTIF}{qui}",
            verifier_name=f"FICTIF {qui.title()}",
            verified_at=INSTANT,
            authorisations_at_signature=frozenset(
                {"can_validate_normative_reference"}),
            authorisation_scope_at_signature="BE/EN 1992/1-1",
            statement=f"FICTIF — {qui} a relu la clause a la page citee.",
            idempotency_key=f"{FICTIF}idem-{qui}-{nom}",
        )
        for qui in ("alice", "bob")
    ]


@pytest.fixture(scope="module")
def fournisseur() -> FournisseurFictif:
    """Deux regards fictifs sur CHAQUE parametre requis par les cinq modules.

    La liste vient de `required_parameters_for_beam`, pas d'une enumeration
    recopiee: un module qui reclamerait un parametre de plus ferait echouer
    ce decor, et non passer un calcul incomplet.
    """
    jeu = load_parameter_set(PAYS, strict=True, as_of=AU)
    confirmations = []
    for cle in required_parameters_for_beam(PAYS):
        p = jeu.find(cle)
        assert p is not None, cle
        paquet = _paquet(p)
        confirmations.extend(_signatures(paquet, p.parameter_name))
    return FournisseurFictif(confirmations)


# ===========================================================================
# 1. w_max, le parametre qui bloquait
# ===========================================================================
def test_w_max_se_confirme_desormais_par_le_quatre_yeux(fournisseur) -> None:
    """LA MESURE DU LOT. Avant la lecture du tableau, ce cas etait rouge.

    La passerelle refusait sur la provenance, avant meme de regarder les
    signatures: « aucune valeur n'y a ete relevee dans l'Annexe Nationale
    publiee ». Ce refus etait juste tant que la fiche portait les nombres du
    Tableau 7.1N de l'EN. Il ne l'est plus: ils viennent du Tableau 7.1N-ANB.
    """
    jeu = load_parameter_set(PAYS, strict=True, as_of=AU)
    rapport = evaluer_depuis_le_provider(jeu.find(W_MAX), provider=fournisseur)
    assert rapport.usable, rapport.reason
    assert rapport.verifiers == frozenset({f"{FICTIF}alice", f"{FICTIF}bob"})


def test_le_dossier_de_w_max_porte_ses_deux_branches() -> None:
    """Deux ingenieurs ne peuvent pas signer un sujet sans nombres.

    `w_max` n'a pas de scalaire — le registre porte `parameter_value = null`,
    et c'est correct: la valeur depend de la classe d'exposition. Les nombres
    du sujet sont donc les branches, et le dossier doit les porter, sans quoi
    la signature ne couvrirait rien de ce que le calcul utilise.
    """
    jeu = load_parameter_set(PAYS, strict=True, as_of=AU)
    compose = _compose(jeu.find(W_MAX))
    charge = json.loads(compose.normative_spec.canonical_payload)

    assert charge["rule_type"] == "conditional_scalar"
    assert charge["scalar_value"] is None
    conditions = {v["condition"]: v["value"] for v in charge["variants"]}
    assert set(conditions) == {"X0_XC1", "XC2_XC4_XD_XS"}

    # Et l'ecran de revue les montre: sans cela l'ingenieur approuve un vide.
    assert compose.resume["variants"] == [
        {"condition": "X0_XC1", "value": 0.4},
        {"condition": "XC2_XC4_XD_XS", "value": 0.3},
    ]
    # Le dossier cite le folio de la fiche, pas un folio choisi ici.
    assert compose.resume["source_page"] == 18
    assert compose.resume["source_doc_id"].startswith("3a195362")

    # ET UN PARAMETRE SCALAIRE N'A PAS DE LIGNE « variants » DU TOUT. Une
    # ligne vide sur chacune des vingt-huit autres fiches s'apprendrait a
    # sauter — et se sauterait aussi le jour ou elle porte quelque chose.
    scalaire = _compose(jeu.find("EN 1992-1-1:gamma_C_persistent"))
    assert "variants" not in scalaire.resume
    assert json.loads(
        scalaire.normative_spec.canonical_payload)["rule_type"] == "scalar"


def test_un_dossier_dont_une_branche_a_bouge_est_refuse() -> None:
    """Le controle de valeur, pour un parametre conditionnel.

    Un dossier signe sur 0,4 mm partout ne confirme pas un registre qui porte
    0,3 mm en XC2-XC4 — meme signe deux fois, meme sur la bonne clause, la
    bonne edition et le bon document.
    """
    jeu = load_parameter_set(PAYS, strict=True, as_of=AU)
    vrai = jeu.find(W_MAX)
    faux = dataclasses.replace(vrai, variants=tuple(
        dataclasses.replace(v, value=0.4) for v in vrai.variants
    ))
    paquet = _paquet(faux)
    rapport = evaluer_depuis_le_provider(
        vrai, provider=FournisseurFictif(_signatures(paquet, "w_max-faux")))
    assert not rapport.usable
    # LE MOTIF COMPTE AUTANT QUE LE REFUS. Un refus generique — « le dossier
    # porte des branches que le registre n'a pas » — laisserait croire que la
    # comparaison branche a branche a eu lieu alors qu'elle aurait ete
    # court-circuitee. Le rapport doit citer les DEUX jeux de valeurs.
    assert "variantes" in rapport.reason
    assert "0.3" in rapport.reason, rapport.reason
    assert "0.4" in rapport.reason, rapport.reason


# ===========================================================================
# 2. Les cinq chapitres, en mode strict
# ===========================================================================
def test_le_referentiel_du_depot_bloque_TOUS_les_requis_sans_confirmation(
) -> None:
    """Sans provider, tout bloque — et c'est le comportement voulu.

    C'est la contre-mesure du cas suivant. Si le referentiel du depot ouvrait
    quoi que ce soit, la confirmation fictive ne prouverait rien.
    """
    prevol = preflight_beam(country=PAYS, as_of=AU, strict=True)
    assert not prevol.ready
    bloques = {b.parameter for b in prevol.blocking}
    assert bloques == set(required_parameters_for_beam(PAYS))
    assert W_MAX in bloques


def test_le_preflight_belge_ne_bloque_plus_apres_confirmation_fictive(
    fournisseur,
) -> None:
    """Le compte, mesure et non recopie: zero bloquant sur les requis."""
    prevol = preflight_beam(country=PAYS, as_of=AU, strict=True,
                            provider=fournisseur)
    assert prevol.ready, [b.parameter for b in prevol.blocking]
    assert prevol.provider_is_fictional is True


def test_les_cinq_chapitres_aboutissent_en_mode_strict(fournisseur) -> None:
    """LE CHEMIN COMPLET. Cinq sections evaluees, aucune `not_evaluated`."""
    contexte = resolve_beam_context(country=PAYS, as_of=AU, strict=True,
                                    provider=fournisseur)
    etude = verify_beam(POUTRE, params=contexte.parameters)

    cles = [s.key for s in etude.sections]
    assert cles == ["flexure", "shear", "anchorage", "serviceability",
                    "deflection"]
    non_evaluees = [s.key for s in etude.sections
                    if s.status == "not_evaluated"]
    assert non_evaluees == [], f"chapitres non evalues: {non_evaluees}"

    # Et le chapitre ELS a bien lu 0,30 mm — la ligne XC2-XC4 du tableau.
    els = next(s for s in etude.sections if s.key == "serviceability")
    assert els.design.w_max.to("mm").magnitude == pytest.approx(0.30)
    # La ligne UTILISEE est nommee dans le journal du chapitre.
    assert "XC2_XC4_XD_XS" in els.design.journal.to_json()


def test_le_meme_calcul_avec_un_seul_signataire_refuse(fournisseur) -> None:
    """Le quatre-yeux n'est pas decoratif: un seul regard ne suffit pas."""
    seuls = FournisseurFictif(
        c for c in fournisseur._c if c.verifier_id == f"{FICTIF}alice")
    prevol = preflight_beam(country=PAYS, as_of=AU, strict=True,
                            provider=seuls)
    assert not prevol.ready
    assert W_MAX in {b.parameter for b in prevol.blocking}
