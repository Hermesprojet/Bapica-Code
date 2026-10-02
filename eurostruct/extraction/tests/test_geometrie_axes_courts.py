"""Les traits d'axe plus courts que le seuil, gardés par leur bulle : le défaut
qu'un plan de structure réel a montré, rejoué sur un plan fabriqué
(``docs/GEOMETRIE_SEUIL_DES_AXES.md``).

Sur le plan réel, une légende éloignée agrandissait l'emprise : le seuil d'un
axe nommé par son calque (10 % de la diagonale) passait au-dessus des traits
des axes « L6 » et « L8 », qui finissaient pourtant sur leur bulle. Aucun seuil
de longueur ne les séparait des morceaux sans bulle : la preuve est la bulle.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie.axes import RAYONS_MIN_AXE_COURT
from fabrique_geometrie import dxf_axes_courts_a_bulle

Point = tuple[float, float]


@pytest.fixture(scope="module")
def lecture():
    analyse = parse_document(dxf_axes_courts_a_bulle(), ocr=None)
    return analyse, extract_engineering_data(analyse)


def _axe(modele: dict, etiquette: str) -> dict:
    return next(a for a in modele["grid"] if a.get("label") == etiquette)


def _axes_par(modele: dict, point: Point) -> list[dict]:
    """Les axes du modèle dont la droite passe par ``point`` (1 mm), entre leurs bouts."""
    trouves = []
    for a in modele["grid"]:
        (x0, y0), (x1, y1) = a["line"]
        longueur = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / longueur, (y1 - y0) / longueur
        t = (point[0] - x0) * ux + (point[1] - y0) * uy
        ecart = abs((point[0] - x0) * uy - (point[1] - y0) * ux)
        if ecart <= 1.0 and -1.0 <= t <= longueur + 1.0:
            trouves.append(a)
    return trouves


# ===================================================================== le seuil
def test_le_seuil_passe_au_dessus_des_traits_courts(lecture) -> None:
    """LA LÉGENDE ÉLOIGNÉE agrandit l'emprise : 10 % de la diagonale dépasse le
    plus long des traits courts (5 200 mm). Sans elle, la règle ne serait pas
    éprouvée."""
    analyse, _ = lecture
    x0, y0, x1, y1 = analyse.primitives_dxf.emprise()
    assert 0.1 * math.hypot(x1 - x0, y1 - y0) > 5200.0


# ============================================================ gardés, et dits
def test_un_axe_court_qui_finit_sur_sa_bulle_est_un_axe(lecture) -> None:
    _, resultat = lecture
    axe = _axe(resultat.structure, "1'")
    assert axe["line"] == [[3000.0, 1000.0], [3000.0, 6000.0]]
    source = axe["label_source"]
    assert source["via"] == "bulle"
    admis = source["admitted"]
    assert admis["rule"] == "trait d'axe plus court que le seuil, termine par sa bulle etiquetee"
    assert admis["lengths"] == [5000.0]
    assert admis["threshold"] > 5000.0


def test_deux_traits_courts_paralleles_se_soutiennent(lecture) -> None:
    """« R1 » et « R2 », à 80° : aucun axe admis par le seuil n'a leur
    direction, mais ils la partagent — comme « LF », « LG », « LH » sur le plan
    réel."""
    _, resultat = lecture
    for etiquette in ("R1", "R2"):
        source = _axe(resultat.structure, etiquette)["label_source"]
        assert source["via"] == "bulle"
        assert source["form"] == "lettres_et_chiffres"
        assert "admitted" in source


def test_les_axes_admis_par_le_seuil_ne_changent_pas(lecture) -> None:
    _, resultat = lecture
    for etiquette in ("1", "2", "3", "A", "B", "C"):
        source = _axe(resultat.structure, etiquette)["label_source"]
        assert source["via"] == "bulle"
        assert "admitted" not in source


# ======================================================== refusés, un par un
@pytest.mark.parametrize(("cas", "point"), [
    ("sans bulle", (9000.0, 3500.0)),
    ("trait de rappel de 3 rayons", (4500.0, 7400.0)),
    ("direction isolée", (8750.0, 7750.0)),
    ("bulle d'un autre axe", (-4400.0, 10050.0)),
    ("deux bulles qui se contredisent", (12050.0, 14300.0)),
    ("pieu au bout", (10500.0, 3500.0)),
    ("type de ligne d'axe, hors calque nommé", (7500.0, 3500.0)),
])
def test_un_trait_court_sans_toutes_les_preuves_n_est_pas_un_axe(
        lecture, cas: str, point: Point) -> None:
    _, resultat = lecture
    assert _axes_par(resultat.structure, point) == [], cas


def test_un_trait_de_rappel_est_sous_le_minimum_de_rayons() -> None:
    """Le rappel de la fabrique mesure 3 rayons ; les axes courts, 12,5."""
    assert 3.0 < RAYONS_MIN_AXE_COURT <= 12.5


def test_la_direction_partagee_fait_l_axe() -> None:
    """LE MÊME TRAIT À 45° devient un axe dès qu'un axe admis par le seuil
    partage sa direction : c'est bien la direction qui le refusait."""
    resultat = extract_engineering_data(parse_document(
        dxf_axes_courts_a_bulle(appui_a_45=True), ocr=None))
    axe = _axe(resultat.structure, "Q")
    assert axe["label_source"]["via"] == "bulle"
    assert "admitted" in axe["label_source"]


# ================================================ ce qu'un trait retiré a pris
def test_une_bulle_prise_par_un_trait_retire_revient_a_son_axe(lecture) -> None:
    """LE TRAIT x = 12 050 touche la bulle « 3 » avant l'axe « 3 » ; sa bulle « 7 »
    le contredit, il est retiré — et tout est relu sans lui : l'axe « 3 » garde
    son étiquette, et aucun conflit n'est signalé pour un trait qui n'est pas un
    axe."""
    _, resultat = lecture
    axe = _axe(resultat.structure, "3")
    assert axe["line"] == [[12000.0, -1000.0], [12000.0, 10600.0]]
    assert _axe(resultat.structure, "C")["line"] == [[-1000.0, 10000.0], [13000.0, 10000.0]]
    assert resultat.structure["unresolved"] == []


def test_les_files_proposees(lecture) -> None:
    _, resultat = lecture
    files = sorted(c.valeur for c in resultat.candidats
                   if c.methode == "geometrie" and c.categorie == "grid_line")
    assert files == ["1", "1'", "2", "3", "A", "B", "C", "R1", "R2"]
