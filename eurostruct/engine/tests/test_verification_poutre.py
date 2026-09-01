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

from eurostruct_engine.ec2.beam_verification import (
    BeamGeometry,
    BeamVerificationInput,
    LongitudinalBars,
    TransverseLinks,
    preflight_beam,
    required_parameters_for_beam,
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
    assert a.engineering_inputs_hash == b.engineering_inputs_hash
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


@pytest.mark.parametrize("libelle,remplace", [
    ("V_Ed negatif", {"V_Ed": Q_(-10, "kN")}),
    ("M_Ed negatif", {"M_Ed": Q_(-10, "kN*m")}),
    ("M_qp negatif", {"M_qp": Q_(-10, "kN*m")}),
    ("M_char negatif", {"M_char": Q_(-10, "kN*m")}),
    ("fluage negatif", {"phi_creep": -1.0}),
    ("cot(theta) nul", {"cot_theta": 0.0}),
    ("largeur nulle", {"geometry": BeamGeometry(
        b=Q_(0, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"),
        l_eff=Q_(6000, "mm"))}),
    ("hauteur negative", {"geometry": BeamGeometry(
        b=Q_(300, "mm"), h=Q_(-600, "mm"), d=Q_(550, "mm"),
        l_eff=Q_(6000, "mm"))}),
    ("portee nulle", {"geometry": BeamGeometry(
        b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"),
        l_eff=Q_(0, "mm"))}),
    ("enrobage impossible", {"cover": Q_(140, "mm")}),
    ("diametre d'etrier nul", {"links": TransverseLinks(
        legs=2, diameter=Q_(0, "mm"), spacing=Q_(150, "mm"))}),
    ("espacement d'etrier negatif", {"links": TransverseLinks(
        legs=2, diameter=Q_(10, "mm"), spacing=Q_(-150, "mm"))}),
    ("une seule barre", {"bars": LongitudinalBars(
        count=1, diameter=Q_(20, "mm"))}),
])
def test_une_saisie_invalide_est_refusee_pas_conservee(
        params, libelle, remplace) -> None:
    """CES CAS SONT DES REFUS, PAS DES ETUDES INCOMPLETES.

    Une redaction precedente attrapait tout `InconsistentInput` remonte d'un
    module et le transformait en `not_evaluated`. Trop large: une saisie
    reellement fausse — un moment negatif, un fluage negatif — serait devenue
    un dossier « incomplete » au lieu d'etre refusee. Le filet est desormais
    pose AVANT les modules, et rien ne l'attrape apres.
    """
    with pytest.raises(InconsistentInput):
        verify_beam(_entree(**remplace), params=params)


def test_une_dependance_amont_est_dite_par_un_code_pas_par_un_texte(
        params) -> None:
    """`prerequisite_failed:flexure` se teste, se traduit et se stocke.

    La dispense de §7.4.2 n'a pas de sens sous une flexion non satisfaite, et
    `check_span_depth` le dit lui-meme. Mais on ne l'APPELLE pas pour attraper
    son refus et en deviner la cause dans un message: la dependance est
    declaree en amont.
    """
    etude = verify_beam(
        _entree(bars=LongitudinalBars(count=3, diameter=Q_(16, "mm"))),
        params=params)
    fleche = _section(etude, "deflection")
    assert fleche.status == "not_evaluated"
    assert fleche.reason == "prerequisite_failed:flexure"
    assert _section(etude, "flexure").status == "failed"
    assert etude.status == "failed", (
        "un rouge certain prime sur le silence qu'il provoque")


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
    """LE VOCABULAIRE EST LE SUJET, ET IL A SON PROPRE ETAT.

    Une dispense non acquise n'est ni un echec de la poutre, ni un silence: le
    module a TOURNE, et il conclut qu'un calcul explicite de fleche reste a
    faire. La ranger dans `failed` ferait refuser des poutres correctes; la
    ranger dans `not_evaluated` cacherait qu'on sait quelque chose.
    """
    etude = verify_beam(_entree(geometry=BeamGeometry(
        b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"),
        l_eff=Q_(12000, "mm"))), params=params)
    fleche = _section(etude, "deflection")
    assert fleche.status == "additional_analysis_required"
    #: LE MODULE A TOURNE: il y a donc un taux, contrairement a un silence.
    assert fleche.utilisation is not None
    assert "calcul explicite" in (fleche.remedy or "").lower()
    assert "echec de la poutre" in (fleche.remedy or "")

    #: LE VERDICT GLOBAL EST `incomplete`, PAS `failed`.
    assert etude.status == "incomplete"
    assert etude.requires_additional_analysis
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


def test_une_etude_verte_mais_exploratoire_ne_se_finalise_pas(params) -> None:
    """LE CAS DECISIF, ET IL EST DANGEREUX PARCE QU'IL PARAIT VERT.

    `params` est charge avec `strict=False`. Les cinq sections sont
    satisfaites, le statut est `passed`, tous les taux sont sous 1,0 — et
    l'etude reste EXPLORATOIRE: elle a tourne sur des valeurs nationales que
    personne n'a relevees.

    Faire de `may_be_finalised` un synonyme de « statut passed » laisserait
    signer cela. C'est precisement ce que la premiere redaction faisait.
    """
    etude = verify_beam(_entree(), params=params)

    assert etude.status == "passed"
    assert all(s.status == "passed" for s in etude.sections)

    assert not etude.strict_ndp
    assert etude.is_exploratory
    assert not etude.may_be_finalised, (
        "une etude exploratoire ne se finalise pas, meme entierement verte")


def test_le_resultat_porte_son_contexte_normatif(params) -> None:
    """Sans lui, rien en aval ne distingue un vert exploratoire d'un signable."""
    etude = verify_beam(_entree(), params=params)
    assert etude.country == "BE"
    assert etude.ndp_as_of == AS_OF
    assert etude.strict_ndp is False
    assert etude.preflight_ready in (True, False)
    assert len(etude.ndp_snapshot_id) == 64
    assert len(etude.calculation_fingerprint) == 64
    for cle in ("strict_ndp", "country", "region", "ndp_as_of",
                "preflight_ready", "ndp_snapshot_id",
                "calculation_fingerprint", "is_exploratory"):
        assert cle in etude.to_dict()


def test_la_region_entre_dans_l_instantane_et_dans_l_empreinte() -> None:
    sans = load_parameter_set(PAYS, strict=False, as_of=AS_OF)
    avec = load_parameter_set(PAYS, region="Wallonie", strict=False, as_of=AS_OF)
    a = verify_beam(_entree(), params=sans)
    b = verify_beam(_entree(), params=avec)

    assert b.region == "Wallonie"
    assert b.ndp_summary["region"] == "Wallonie"
    assert a.ndp_snapshot_id != b.ndp_snapshot_id
    assert a.calculation_fingerprint != b.calculation_fingerprint


def test_le_pays_la_date_et_le_mode_strict_changent_l_empreinte() -> None:
    """Les memes nombres sous un autre referentiel ne sont pas la meme etude.

    ON COMPARE LES INSTANTANES, PAS DES ETUDES COMPLETES, ET C'EST FORCE: en
    mode strict, sans confirmations, `verify_beam` REFUSE — ce qui est le
    comportement correct et precisement ce que la correction 1 installe. Faire
    tourner une etude stricte ici pour comparer son empreinte demanderait de
    contourner le refus, donc de tester autre chose que le produit.
    """
    from eurostruct_engine.ec2.beam_verification import _empreinte_normative

    reference = _empreinte_normative(
        load_parameter_set("BE", strict=False, as_of=AS_OF))
    variantes = {
        "date": load_parameter_set("BE", strict=False, as_of=date(2025, 1, 1)),
        "strict": load_parameter_set("BE", strict=True, as_of=AS_OF),
        "region": load_parameter_set("BE", region="Wallonie", strict=False,
                                     as_of=AS_OF),
        "pays": load_parameter_set("FR", strict=False, as_of=AS_OF),
    }
    for nom, jeu in variantes.items():
        assert _empreinte_normative(jeu) != reference, (
            f"changer « {nom} » n'a pas change l'instantane normatif")

    #: ET L'EMPREINTE DE L'ETUDE EN HERITE: elle combine l'entree gelee et
    #: l'instantane, donc deux etudes aux memes nombres sous des referentiels
    #: differents ne la partagent pas.
    a = verify_beam(_entree(), params=load_parameter_set(
        "BE", strict=False, as_of=AS_OF))
    b = verify_beam(_entree(), params=load_parameter_set(
        "BE", region="Wallonie", strict=False, as_of=AS_OF))
    assert a.engineering_inputs_hash == b.engineering_inputs_hash, "les nombres saisis sont identiques"
    assert a.calculation_fingerprint != b.calculation_fingerprint, "mais pas le referentiel"


# ---------------------------------------------------------------------------
# Le preflight global: cinq modules, UNE reponse
# ---------------------------------------------------------------------------
def test_le_preflight_est_strict_par_defaut_et_bloque_sans_provider() -> None:
    """BE_STRICT_BLOCKED_WITHOUT_CONFIRMED_PROVIDER_DATA.

    Le referentiel livre ne porte aucune valeur relevee. En mode strict — le
    DEFAUT — le preflight doit donc bloquer, et nommer chaque parametre en
    attente. Une premiere redaction chargeait le jeu avec `strict=False` en
    dur: elle se declarait prete sur un referentiel dont rien n'etait releve.
    Un preflight permissif par defaut est pire que pas de preflight: il
    rassure.
    """
    pf = preflight_beam(country="BE", as_of=AS_OF)
    assert pf.strict is True, "le preflight doit etre strict par defaut"
    assert not pf.ready
    assert pf.blocking
    assert any(b.reason == "pending_verification" for b in pf.blocking), (
        "sans provider, les valeurs non relevees doivent bloquer")
    assert pf.provider_identity is None


def test_le_preflight_non_strict_laisse_passer_les_valeurs_transcrites() -> None:
    """BE_EXPLORATORY_FIVE_SECTIONS_EXECUTABLE.

    Hors mode strict les valeurs transcrites sont utilisables — mais le
    resultat reste exploratoire, ce que `test_une_etude_verte_mais_exploratoire`
    verifie de son cote.
    """
    pf = preflight_beam(country="BE", as_of=AS_OF, strict=False)
    assert pf.strict is False
    assert pf.ready, (
        "hors mode strict, le referentiel belge ne doit plus bloquer: "
        f"{[b.to_dict() for b in pf.blocking]}")


def test_le_preflight_transmet_la_region() -> None:
    """Elle ne l'etait pas: une region qui modifie un parametre etait ignoree."""
    pf = preflight_beam(country="BE", as_of=AS_OF, region="Wallonie",
                        strict=False)
    assert pf.region == "Wallonie"
    assert pf.to_dict()["region"] == "Wallonie"


def test_le_preflight_reunit_l_union_des_cinq_modules() -> None:
    """Un parametre partage apparait pour CHAQUE module qui le reclame."""
    #: L'UNION DEPEND DU PAYS, et c'est un defaut que la premiere redaction
    #: portait: `beam_shear.required_parameters` prend un `country_code`, et un
    #: pays dont les regles typees sont transcrites n'exige plus les scalaires
    #: qu'elles remplacent. En omettant le pays, le preflight belge rendait
    #: sept bloquants que le calcul ne reclame pas — plus severe que le moteur,
    #: donc faux.
    union = required_parameters_for_beam("BE")
    assert len(union) == len(set(union)), "l'union ne doit pas doublonner"
    pf = preflight_beam(country="BE", as_of=AS_OF)
    assert set(pf.required) == set(union)

    sans_pays = required_parameters_for_beam()
    assert set(union) < set(sans_pays), (
        "la Belgique doit reclamer STRICTEMENT MOINS de scalaires que le jeu "
        "generique: ses regles typees en remplacent sept")


def test_le_preflight_strict_applique_les_confirmations_du_provider() -> None:
    """Le pont existe deja: `confirmer_depuis_le_provider`.

    On ne verifie pas ici qu'un provider FICTIF debloque le calcul — il ne le
    doit pas. On verifie que le provider est REELLEMENT interroge et que son
    identite est inscrite: un preflight qui ignorerait le provider rendrait le
    meme resultat, et rien ne le distinguerait.
    """
    from eurostruct_engine.ndp.confirmation import InMemoryConfirmationProvider

    provider = InMemoryConfirmationProvider(confirmations=(), revocations=())
    pf = preflight_beam(country="BE", as_of=AS_OF, provider=provider)

    assert pf.provider_identity is not None
    assert pf.provider_is_fictional is True
    #: SANS CONFIRMATION SUFFISANTE, LES PARAMETRES EN ATTENTE RESTENT
    #: BLOQUANTS. C'est le fait produit sur le referentiel livre, pas une
    #: limite du pont.
    assert not pf.ready


def test_not_representable_bloque_meme_hors_mode_strict() -> None:
    """FR_EXPLORATORY_SLS_NOT_EVALUATED_FORMULA_MODEL_GAP.

    Une formule que le modele scalaire ne sait pas porter ne devient pas
    portable parce qu'on a baisse les exigences.
    """
    pf = preflight_beam(country="FR", as_of=AS_OF, strict=False)
    assert not pf.ready
    assert any(b.reason == "not_representable" for b in pf.blocking)


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
