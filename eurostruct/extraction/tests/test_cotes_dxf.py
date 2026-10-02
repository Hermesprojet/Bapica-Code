"""Les cotes DXF : la mesure par type, et ce qui en est proposé
(``docs/GEOMETRIE_COTES_DXF.md``).

Le défaut qu'un plan réel a montré : 82 cotes alignées sur 106 lues faux, de
−0,6 % à −100 % — ezdxf mesure une cote alignée comme une cote tournée, sur
un code 50 qu'AutoCAD n'écrit pas : la « mesure » était la projection
horizontale. Le plan fabriqué écrit ses cotes alignées comme AutoCAD.
"""

from __future__ import annotations

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.extracteurs.dxf_entites import CONFIANCE_MESURE_CONTREDITE
from eurostruct_extraction.lecteurs.dxf_cotes import mesure_de_cote
from fabrique_geometrie import _cote_alignee_comme_autocad, dxf_cotes_de_tous_types


@pytest.fixture(scope="module")
def lecture():
    analyse = parse_document(dxf_cotes_de_tous_types(), ocr=None)
    return analyse, extract_engineering_data(analyse)


def _cotes(resultat) -> list:  # noqa: ANN001
    return [c for c in resultat.candidats
            if c.methode == "dxf" and c.categorie in ("dimension", "grid_spacing")]


def _par_nature(resultat, nature: str) -> list[tuple]:  # noqa: ANN001
    return sorted((c.valeur, c.unite or "") for c in _cotes(resultat)
                  if c.fondement.get("dimension_type") == nature)


def _cote_du_modele(resultat, p1: tuple[float, float]) -> dict:  # noqa: ANN001
    return next(d for d in resultat.structure["dimensions"]
                if abs(d["p1"][0] - p1[0]) < 1e-6 and abs(d["p1"][1] - p1[1]) < 1e-6)


# ================================================================ la mesure
def _alignee_comme_autocad(p1: tuple[float, float], p2: tuple[float, float]):  # noqa: ANN202
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    cote = doc.modelspace().add_aligned_dim(p1=p1, p2=p2, distance=100)
    cote.render()
    _cote_alignee_comme_autocad(cote.dimension)
    return cote.dimension


@pytest.mark.parametrize(("p2", "attendu"), [
    ((300, 400), 500.0), ((0, 700), 700.0), ((1000, 0), 1000.0), ((-600, -800), 1000.0)])
def test_une_cote_alignee_mesure_la_distance_de_ses_deux_points(p2, attendu) -> None:
    """SANS CODE 50, COMME AUTOCAD L'ÉCRIT : la mesure n'est plus la projection
    horizontale (300, 0, 1 000, 600)."""
    dimension = _alignee_comme_autocad((0, 0), p2)
    assert not dimension.dxf.hasattr("angle")
    mesure = mesure_de_cote(dimension)
    assert mesure.nature == "alignee"
    assert mesure.valeur == pytest.approx(attendu, abs=1e-9)


def test_la_mesure_d_autocad_est_rendue_telle_quelle() -> None:
    dimension = _alignee_comme_autocad((0, 0), (300, 400))
    assert mesure_de_cote(dimension).autocad is None
    dimension.dxf.actual_measurement = 500.0
    assert mesure_de_cote(dimension).autocad == 500.0
    # −1 : AutoCAD n'a rien enregistré (cotes des références externes liées).
    dimension.dxf.actual_measurement = -1.0
    assert mesure_de_cote(dimension).autocad is None


# ============================================================ propositions
def test_les_cotes_alignees_proposent_leur_vraie_longueur(lecture) -> None:
    _, resultat = lecture
    valeurs = {(c.valeur, c.unite) for c in _cotes(resultat)}
    assert {(700, "cm"), (1414.213562, "cm")} <= valeurs
    # Les projections horizontales d'avant : 300 pour la 3-4-5, 0 pour la verticale.
    assert not {(300, "cm"), (0, "cm"), (300, None)} & valeurs
    assert _par_nature(resultat, "alignee") == [
        (450, "cm"), (500, ""), (500, "cm"), (700, "cm"), (1000, "cm"), (1414.213562, "cm")]


def test_les_cotes_lineaires_ne_changent_pas(lecture) -> None:
    """Vrai avant comme après le correctif : seules les alignées changent."""
    _, resultat = lecture
    valeurs = {(c.valeur, c.unite) for c in _cotes(resultat)}
    assert {(3000, "cm"), (2500, "cm"), (1366.025404, "cm"), (580, "cm")} <= valeurs


def test_un_rayon_et_un_diametre_disent_leur_nature(lecture) -> None:
    _, resultat = lecture
    rayon = next(c for c in _cotes(resultat) if c.fondement.get("dimension_type") == "rayon")
    diametre = next(c for c in _cotes(resultat)
                    if c.fondement.get("dimension_type") == "diametre")
    assert (rayon.valeur, rayon.categorie) == (40, "dimension")
    assert rayon.texte_brut.startswith("cote R40 ")
    assert (diametre.valeur, diametre.categorie) == (63, "dimension")
    assert diametre.texte_brut.startswith("cote ∅63 ")


def test_un_angle_n_est_jamais_propose_comme_une_longueur(lecture) -> None:
    analyse, resultat = lecture
    assert analyse.compte_rendu["dimension_types"]["angulaire"] == 2
    natures = {c.fondement.get("dimension_type") for c in _cotes(resultat)}
    assert natures == {"lineaire", "alignee", "rayon", "diametre"}
    assert not [c for c in _cotes(resultat) if c.valeur in (60, 90)]


def test_ordonnees_et_longueur_d_arc_sont_comptees_pas_proposees(lecture) -> None:
    analyse, resultat = lecture
    types = analyse.compte_rendu["dimension_types"]
    assert (types["ordonnee"], types["longueur_arc"]) == (2, 1)
    assert not [c for c in _cotes(resultat) if c.valeur in (1200, 300)]


def test_la_mesure_d_autocad_est_citee(lecture) -> None:
    _, resultat = lecture
    cote = next(c for c in _cotes(resultat) if c.fondement.get("autocad_measurement"))
    assert (cote.valeur, cote.fondement["autocad_measurement"]) == (500, "500")
    assert "measurement_conflict" not in cote.fondement


def test_une_mesure_que_le_code_42_contredit_est_signalee_pas_corrigee() -> None:
    """La linéaire de 3 000 porte un code 42 de 2 900 : rien n'est choisi entre
    les deux — la mesure des points est proposée, la contradiction est dite."""
    resultat = extract_engineering_data(parse_document(
        dxf_cotes_de_tous_types(mesure_autocad_contredite=True), ocr=None))
    cote = next(c for c in _cotes(resultat) if c.fondement.get("measurement_conflict"))
    assert (cote.valeur, cote.fondement["autocad_measurement"]) == (3000, "2900")
    assert cote.confiance <= CONFIANCE_MESURE_CONTREDITE


# ================================================================== modèle
def test_les_cotes_alignees_du_modele_mesurent_leur_vraie_longueur(lecture) -> None:
    _, resultat = lecture
    for p1, affiche in (((10000, 0), "500"), ((12000, 0), "700"), ((14000, 0), "1414.214"),
                        ((16000, 0), "1000"), ((0, 5000), "500")):
        assert _cote_du_modele(resultat, p1)["displayed"] == affiche


def test_un_texte_force_se_juge_contre_la_vraie_mesure(lecture) -> None:
    """« 450 » SUR UNE ALIGNÉE DE 450 n'est pas discordant ; « 580 » sur une
    linéaire de 600 l'est."""
    _, resultat = lecture
    assert _cote_du_modele(resultat, (5000, 5000))["forced_mismatch"] is False
    assert _cote_du_modele(resultat, (8000, 5000))["forced_mismatch"] is True


def test_une_cote_de_bloc_affiche_sa_mesure_dans_le_bloc(lecture) -> None:
    """UN DÉTAIL EN MM (DIMLFAC 0,1) INSÉRÉ AU 1/10 : la copie placée mesure 600
    cm, et la cote affiche 6 000 mm × 0,1 = 600 — pas 600 × 0,1 = 60."""
    _, resultat = lecture
    for p1 in ((40000, 0), (40000, 100)):
        cote = _cote_du_modele(resultat, p1)
        assert (cote["displayed"], cote["dimlfac"]) == ("600", 0.1)
        assert cote["measured"] == pytest.approx(600)
