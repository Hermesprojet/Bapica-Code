"""La verification COMPLETE d'une poutre: les cinq sections, ensemble.

CE QUE CE FICHIER EXISTE POUR ATTRAPER
---------------------------------------
`test_note.py` assemble deja les cinq modules — flexion, tranchant, ancrage,
ELS, dispense de fleche — mais il le fait DANS UN TEST. Chaque appel y recoit
ses propres arguments, ecrits a la main, et rien n'oblige la geometrie de la
flexion a etre celle du tranchant, ni le ferraillage de l'ELS a etre celui du
dessin. L'assemblage tient parce que quelqu'un a recopie les memes nombres cinq
fois.

Un produit ne peut pas reposer la-dessus. Ce fichier eprouve un ORCHESTRATEUR:
une seule entree, gelee, d'ou les cinq sections derivent. Les proprietes qui
comptent ne sont pas « chaque module calcule juste » — leurs propres tests s'en
chargent — mais L'INTERDEPENDANCE:

  * changer `V_Ed` doit bouger le tranchant et RIEN d'autre;
  * changer les barres doit se propager aux CINQ sections et au dessin;
  * changer les etriers doit bouger le tranchant et le plan, pas la flexion.

Un orchestrateur qui recopierait une valeur au lieu de la deriver passerait les
tests de chaque module et echouerait ici.

LE VOCABULAIRE EST NORMATIF, PAS COSMETIQUE
--------------------------------------------
Une dispense de fleche NON ACQUISE ne veut pas dire que la poutre echoue: elle
veut dire qu'un CALCUL EXPLICITE DE FLECHE reste necessaire. Confondre les deux
ferait refuser des poutres correctes. Les tests l'exigent mot pour mot.

AUCUN RESULTAT PRODUIT ICI N'EST UNE VERIFICATION REELLE. Les donnees sont
fictives et le registre national reste a 0/29.
"""

from __future__ import annotations

from datetime import date

import pytest

from eurostruct_engine.ec2 import ExposureClass, StructuralSystem
from eurostruct_engine.ec2.anchorage import BondCondition

# LE MODULE N'EXISTE PAS ENCORE. C'est le sujet de ce lot, et cet import est la
# premiere preuve rouge: l'application ne sait pas produire cette etude.
from eurostruct_engine.ec2.beam_verification import (
    BeamGeometry,
    BeamVerificationInput,
    LongitudinalBars,
    TransverseLinks,
    preflight_beam,
    verify_beam,
)
from eurostruct_engine.exceptions import InconsistentInput
from eurostruct_engine.ndp.registry import load_parameter_set
from eurostruct_engine.units import Q_

AS_OF = date(2026, 1, 1)

#: LA BELGIQUE, ET C'EST UN CHOIX MESURE.
#:
#: Mesure du 01/09: avec les donnees nationales REELLES, la Belgique execute
#: les cinq sections, et la France non — son NA rend `k3` fonction de
#: l'enrobage (« 3,4 (25/c)^(2/3) »), une FORMULE que le modele scalaire des
#: NDP ne sait pas porter. L'ELS francais est donc bloque en
#: `not_representable`, ce que `test_la_france_bloque_l_els` constate.
#:
#: On ne substitue AUCUNE valeur pour contourner cela: ce serait inventer un
#: parametre national (interdiction 2).
PAYS = "BE"


@pytest.fixture
def params():
    return load_parameter_set(PAYS, strict=False, as_of=AS_OF)


def _entree(**remplace):
    """L'etude de reference: une poutre qui passe les cinq verifications.

    `cot(theta) = 1,5` et non 2,5: la borne nationale belge, CALCULEE sur le
    ferraillage obtenu, refuse 2,5 — et ce refus est correct.
    """
    base = dict(
        element="P1",
        geometry=BeamGeometry(b=Q_(300, "mm"), h=Q_(600, "mm"),
                              d=Q_(550, "mm"), l_eff=Q_(6000, "mm")),
        concrete_grade="C30/37",
        steel_grade="B500B",
        M_Ed=Q_(250, "kN*m"),
        V_Ed=Q_(300, "kN"),
        M_char=Q_(180, "kN*m"),
        M_qp=Q_(120, "kN*m"),
        phi_creep=2.0,
        exposure_class=ExposureClass.XC3,
        system=StructuralSystem.SIMPLY_SUPPORTED,
        supports_brittle_partitions=False,
        bars=LongitudinalBars(count=4, diameter=Q_(20, "mm")),
        links=TransverseLinks(legs=2, diameter=Q_(10, "mm"),
                              spacing=Q_(150, "mm")),
        cot_theta=1.5,
        cover=Q_(40, "mm"),
        bond_condition=BondCondition.GOOD,
        anchorage_available=Q_(800, "mm"),
    )
    base.update(remplace)
    return BeamVerificationInput(**base)


def _section(etude, cle):
    for s in etude.sections:
        if s.key == cle:
            return s
    raise AssertionError(f"section « {cle} » absente de l'etude")


# ---------------------------------------------------------------------------
# L'etude de reference tourne, et elle tourne entierement
# ---------------------------------------------------------------------------
def test_les_cinq_sections_sont_evaluees(params) -> None:
    etude = verify_beam(_entree(), params=params)
    assert [s.key for s in etude.sections] == [
        "flexure", "shear", "anchorage", "serviceability", "deflection",
    ], "l'ordre des cinq sections est celui de la note, et il est fixe"
    for s in etude.sections:
        assert s.status != "not_evaluated", f"{s.key} n'a pas ete evaluee"
    assert etude.status == "passed"


def test_l_orchestrateur_est_deterministe(params) -> None:
    a = verify_beam(_entree(), params=params)
    b = verify_beam(_entree(), params=params)
    assert a.inputs_hash == b.inputs_hash
    assert [s.utilisation for s in a.sections] == [s.utilisation for s in b.sections]


# ---------------------------------------------------------------------------
# L'INTERDEPENDANCE — ce qu'aucun test de module ne peut prouver
# ---------------------------------------------------------------------------
def test_changer_l_effort_tranchant_ne_touche_pas_la_flexion(params) -> None:
    """Un orchestrateur qui recopierait mal propagerait V_Ed a tout."""
    a = verify_beam(_entree(), params=params)
    b = verify_beam(_entree(V_Ed=Q_(360, "kN")), params=params)

    assert _section(b, "shear").utilisation != _section(a, "shear").utilisation
    assert _section(b, "flexure").utilisation == _section(a, "flexure").utilisation
    assert (_section(b, "serviceability").utilisation
            == _section(a, "serviceability").utilisation)
    assert (_section(b, "deflection").utilisation
            == _section(a, "deflection").utilisation)


def test_changer_les_barres_se_propage_aux_cinq_sections_et_au_dessin(params) -> None:
    """LE CAS DECISIF DE L'ORCHESTRATEUR.

    Les barres longitudinales entrent dans la flexion (A_s), dans le tranchant
    (A_sl du terme V_Rd,c), dans l'ancrage (le diametre), dans l'ELS (A_s et
    l'espacement) et dans le dessin. Une seule de ces cinq derivations oubliee,
    et le produit dessine autre chose que ce qu'il a calcule.
    """
    a = verify_beam(_entree(), params=params)
    b = verify_beam(
        _entree(bars=LongitudinalBars(count=5, diameter=Q_(20, "mm"))),
        params=params)

    for cle in ("flexure", "anchorage", "serviceability", "deflection"):
        assert _section(b, cle).utilisation != _section(a, cle).utilisation, (
            f"changer les barres n'a rien change a « {cle} »")

    #: LE TRANCHANT SE REGARDE DANS SON JOURNAL, PAS DANS SON TAUX, et c'est
    #: une correction de mon attente initiale.
    #:
    #: `A_sl` n'entre que dans `V_Rd,c`, la resistance SANS armatures d'effort
    #: tranchant. Des que les cadres sont requis, c'est `V_Rd,s` qui gouverne,
    #: et le taux ne bouge pas d'un iota quand on ajoute une barre
    #: longitudinale. Exiger le contraire aurait ete exiger un faux: la bonne
    #: propriete est que `A_sl` ATTEINT le module, ce que le journal montre.
    for symbole in ("rho_l", "V_Rd_c"):
        av = _section(a, "shear").design.journal.get(symbole).value
        ap = _section(b, "shear").design.journal.get(symbole).value
        assert av != ap, (
            f"A_sl n'atteint pas « {symbole} »: les barres longitudinales ne "
            "se propagent pas au tranchant")

    # ET LE DESSIN SUIT LA MEME ENTREE. Le plan et le calcul ne peuvent pas
    # diverger s'ils derivent du meme objet gele.
    assert b.drawing_spec.bottom[0].count == 5
    assert a.drawing_spec.bottom[0].count == 4


def test_changer_les_etriers_bouge_le_tranchant_et_le_plan_pas_la_flexion(
        params) -> None:
    a = verify_beam(_entree(), params=params)
    b = verify_beam(
        _entree(links=TransverseLinks(legs=2, diameter=Q_(8, "mm"),
                                      spacing=Q_(200, "mm"))),
        params=params)

    assert _section(b, "shear").utilisation != _section(a, "shear").utilisation
    assert _section(b, "flexure").utilisation == _section(a, "flexure").utilisation
    assert b.drawing_spec.link_diameter == 8.0
    assert b.drawing_spec.link_spacing == 200.0


def test_l_aire_d_acier_derive_des_barres_et_ne_se_declare_pas() -> None:
    """Interdiction de la donnee redondante: deux sources divergent un jour."""
    assert not hasattr(BeamVerificationInput, "A_s")
    assert not hasattr(BeamVerificationInput, "A_sw")


def test_l_espacement_des_barres_vient_du_modele_geometrique(params) -> None:
    """L'ELS a besoin de l'entraxe reel; il se DERIVE, il ne se saisit pas."""
    assert not hasattr(BeamVerificationInput, "bar_spacing")
    etude = verify_beam(_entree(), params=params)
    # Quatre barres de 20 entre les cadres: (300 - 2*(40+10+10))/3 = 60 mm.
    assert etude.bar_spacing.to("mm").magnitude == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Les refus: une entree incoherente n'est pas un resultat rouge
# ---------------------------------------------------------------------------
def test_m_char_inferieur_a_m_qp_est_refuse(params) -> None:
    """La combinaison caracteristique majore la quasi-permanente, par nature."""
    with pytest.raises(InconsistentInput, match="M_char"):
        verify_beam(_entree(M_char=Q_(100, "kN*m"), M_qp=Q_(120, "kN*m")),
                    params=params)


def test_un_refus_ne_laisse_aucune_etude_partielle(params) -> None:
    """Quatre sections vertes et une exception ne font pas une etude reussie."""
    with pytest.raises(InconsistentInput):
        verify_beam(_entree(M_char=Q_(100, "kN*m"), M_qp=Q_(120, "kN*m")),
                    params=params)


# ---------------------------------------------------------------------------
# Les rouges: executes, non satisfaits, avec taux ET remede
# ---------------------------------------------------------------------------
def test_un_ferraillage_longitudinal_insuffisant_est_non_conforme(params) -> None:
    etude = verify_beam(
        _entree(bars=LongitudinalBars(count=3, diameter=Q_(16, "mm"))),
        params=params)
    flexion = _section(etude, "flexure")
    assert flexion.status == "failed"
    assert flexion.utilisation > 1.0
    assert flexion.remedy, "un rouge sans remede n'aide personne"
    assert etude.status == "failed"


def test_des_etriers_insuffisants_sont_non_conformes(params) -> None:
    etude = verify_beam(
        _entree(links=TransverseLinks(legs=2, diameter=Q_(6, "mm"),
                                      spacing=Q_(300, "mm"))),
        params=params)
    tranchant = _section(etude, "shear")
    assert tranchant.status == "failed"
    assert tranchant.utilisation > 1.0
    assert etude.status == "failed"


def test_un_ancrage_insuffisant_est_visible_et_bloque_la_finalisation(
        params) -> None:
    """`design_anchorage` calcule une LONGUEUR; il ne verifie rien.

    La verification est la comparaison a la longueur REELLEMENT disponible, que
    l'ingenieur declare. Sans elle, l'ancrage serait le seul chapitre de la
    note sans verdict.
    """
    etude = verify_beam(_entree(anchorage_available=Q_(200, "mm")), params=params)
    ancrage = _section(etude, "anchorage")
    assert ancrage.status == "failed"
    assert ancrage.utilisation > 1.0
    assert etude.status == "failed"
    assert not etude.may_be_finalised


def test_une_fissuration_excessive_est_visible_avec_son_taux(params) -> None:
    etude = verify_beam(
        _entree(bars=LongitudinalBars(count=3, diameter=Q_(20, "mm")),
                M_char=Q_(260, "kN*m"), M_qp=Q_(240, "kN*m")),
        params=params)
    els = _section(etude, "serviceability")
    assert els.status == "failed"
    assert els.utilisation > 1.0


def test_une_dispense_non_acquise_demande_un_calcul_explicite(params) -> None:
    """LE VOCABULAIRE EST LE SUJET.

    Une dispense non acquise n'est pas un echec de la poutre: c'est l'annonce
    qu'un calcul de fleche reste a faire. Le dire autrement ferait refuser des
    poutres correctes.
    """
    etude = verify_beam(_entree(geometry=BeamGeometry(
        b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"),
        l_eff=Q_(12000, "mm"))), params=params)
    fleche = _section(etude, "deflection")
    assert fleche.status == "failed"
    assert "calcul explicite" in (fleche.remedy or "").lower()
    assert not etude.may_be_finalised


# ---------------------------------------------------------------------------
# Une etude rouge se conserve, mais ne devient jamais un livrable final
# ---------------------------------------------------------------------------
def test_une_etude_rouge_se_conserve_mais_ne_se_finalise_pas(params) -> None:
    etude = verify_beam(
        _entree(bars=LongitudinalBars(count=3, diameter=Q_(16, "mm"))),
        params=params)
    assert etude.status == "failed"
    assert not etude.may_be_finalised
    assert etude.to_dict(), "une etude rouge reste exploitable pour diagnostic"


def test_une_etude_verte_peut_etre_finalisee(params) -> None:
    assert verify_beam(_entree(), params=params).may_be_finalised


# ---------------------------------------------------------------------------
# Le preflight global: cinq modules, UNE reponse
# ---------------------------------------------------------------------------
def test_le_preflight_reunit_les_bloquants_des_cinq_modules() -> None:
    """Le mode strict ne doit pas echouer cinq fois de suite.

    La France est le cas reel: son ELS est bloque par un parametre que le
    modele scalaire ne sait pas porter. Le preflight doit le dire AVANT le
    calcul, en nommant le module, la clause, l'annexe et la raison.
    """
    pf = preflight_beam(country="FR", as_of=AS_OF)
    assert not pf.ready
    assert pf.blocking, "aucun bloquant rendu alors que l'ELS francais est bloque"
    for item in pf.blocking:
        assert item.module
        assert item.parameter
        assert item.clause
        assert item.annex
        assert item.reason
    assert {i.module for i in pf.blocking} <= {
        "flexure", "shear", "anchorage", "serviceability", "deflection"}


def test_le_preflight_nomme_la_raison_du_blocage_francais() -> None:
    """« non representable » n'est pas « non confirme », et la nuance compte.

    Un parametre non confirme s'obtient en le faisant confirmer. Un parametre
    que le modele ne sait pas PORTER — ici une formule en l'enrobage — ne
    s'obtient pas ainsi: il demande de changer le modele. Presenter le second
    comme le premier enverrait un ingenieur chercher une confirmation qui
    n'existe pas.
    """
    pf = preflight_beam(country="FR", as_of=AS_OF)
    els = [i for i in pf.blocking if i.module == "serviceability"]
    assert els, "l'ELS francais doit figurer parmi les bloquants"
    assert any("representable" in i.reason for i in els)


def test_la_france_bloque_l_els(params) -> None:
    """Constat, pas contournement: on ne substitue aucune valeur nationale."""
    fr = load_parameter_set("FR", strict=False, as_of=AS_OF)
    etude = verify_beam(_entree(), params=fr)
    els = _section(etude, "serviceability")
    assert els.status == "not_evaluated"
    assert els.reason, "une section non evaluee doit dire pourquoi"
    assert els.utilisation is None, "une section non evaluee n'a pas de taux"
    assert not etude.may_be_finalised, (
        "une etude dont une section n'est pas evaluee ne se finalise pas")


def test_une_section_non_evaluee_n_est_jamais_conforme(params) -> None:
    fr = load_parameter_set("FR", strict=False, as_of=AS_OF)
    etude = verify_beam(_entree(), params=fr)
    for s in etude.sections:
        assert s.status in ("passed", "failed", "not_evaluated")
        if s.status == "not_evaluated":
            assert s.utilisation is None
    assert etude.status == "incomplete"
