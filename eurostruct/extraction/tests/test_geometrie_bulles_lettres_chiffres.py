"""Les étiquettes d'axes en lettres et chiffres (« L1 »… « L10 ») : le défaut
qu'un plan de structure réel a montré, rejoué sur un plan fabriqué
(``docs/GEOMETRIE_BULLES_LETTRES_CHIFFRES.md``).

Sur le plan réel, sept axes finissaient sur une bulle « L1 »… « L10 » et
restaient sans étiquette : le motif des étiquettes n'admettait que des lettres
OU des chiffres. Le calque des bulles (``…C_AXES_TITRE…``) est lu « cadre »
par son nom, mais leur bloc les lit « axe » : ce n'était pas la cause.
"""

from __future__ import annotations

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie.axes import ETIQUETTE_AXE, ETIQUETTE_LETTRES_CHIFFRES
from eurostruct_extraction.geometrie.classification import classer, role_du_nom
from fabrique_geometrie import dxf_bulles_lettres_chiffres


@pytest.fixture(scope="module")
def lecture():
    analyse = parse_document(dxf_bulles_lettres_chiffres(), ocr=None)
    return analyse, extract_engineering_data(analyse)


def _axe_a(modele: dict, y: float) -> dict:
    """L'axe horizontal à l'ordonnée ``y``."""
    return next(a for a in modele["grid"]
                if abs(a["line"][0][1] - y) < 1 and abs(a["line"][1][1] - y) < 1)


# ===================================================================== motif
@pytest.mark.parametrize("texte", ["L1", "L10", "AB12", "L1'", "B999"])
def test_le_motif_en_lettres_et_chiffres_admet(texte: str) -> None:
    assert ETIQUETTE_LETTRES_CHIFFRES.fullmatch(texte)
    assert not ETIQUETTE_AXE.fullmatch(texte)


@pytest.mark.parametrize("texte", ["L", "10", "C03-50", "L1000", "ABC1", "1L", "l1", "L 1"])
def test_le_motif_en_lettres_et_chiffres_refuse(texte: str) -> None:
    assert not ETIQUETTE_LETTRES_CHIFFRES.fullmatch(texte)


# ========================================================== la cause, exacte
def test_le_calque_des_bulles_est_lu_cadre_mais_le_bloc_les_lit_axe(lecture) -> None:
    """LA CAUSE N'ÉTAIT PAS LE CARTOUCHE : le nom du calque dit « TITRE » et se
    lit « cadre », mais la bulle est dans le bloc de la référence externe, et
    le bloc prime sur le calque."""
    analyse, _ = lecture
    calque = "AXES_GRILLE2$0$C_AXES_TITRE"
    assert role_du_nom(calque) == "cadre"
    bulle = next(c for c in analyse.primitives_dxf.cercles if c.calque == calque)
    classement = classer(bulle.calque, bulle.source.blocs, bulle.type_ligne)
    assert (classement.role, classement.regle, classement.motif) == ("axe", "bloc",
                                                                       "AXES_GRILLE2")


# =================================================================== lecture
def test_une_bulle_en_lettres_et_chiffres_etiquette_son_axe(lecture) -> None:
    _, resultat = lecture
    axe = _axe_a(resultat.structure, 0.0)
    assert axe["label"] == "L1"
    assert axe["label_source"]["via"] == "bulle"
    assert axe["label_source"]["form"] == "lettres_et_chiffres"


def test_une_etiquette_courante_l_emporte_et_l_autre_est_citee(lecture) -> None:
    """LA LIGNE PARTAGÉE PAR DEUX GRILLES garde son étiquette courante : la
    bulle « L9 » de l'autre bout ne la contredit pas, elle est citée."""
    _, resultat = lecture
    axe = _axe_a(resultat.structure, 3500.0)
    assert axe["label"] == "B"
    assert "form" not in axe["label_source"]
    ecartee = axe["label_source"]["discarded"]
    assert (ecartee["text"], ecartee["via"]) == ("L9", "bulle")
    assert "lettres et chiffres" in ecartee["reason"]
    assert "forme courante" in ecartee["reason"]


def test_deux_bulles_en_lettres_et_chiffres_qui_se_contredisent_restent_un_conflit(
        lecture) -> None:
    _, resultat = lecture
    assert _axe_a(resultat.structure, 7000.0)["label"] is None
    raisons = [u["reason"] for u in resultat.structure["unresolved"]]
    assert any("« L4 »" in r and "« L5 »" in r and "meme force" in r for r in raisons)


def test_un_texte_libre_en_lettres_et_chiffres_n_est_pas_une_etiquette(lecture) -> None:
    _, resultat = lecture
    assert _axe_a(resultat.structure, 10000.0)["label"] is None


def test_le_cartouche_n_etiquette_pas_un_axe(lecture) -> None:
    """MÊME GÉOMÉTRIE QUE « L1 » (cercle et texte au bout de l'axe), mais sur le
    calque d'un cartouche, hors de tout bloc d'axes : rien n'est lu."""
    analyse, resultat = lecture
    cercle = next(c for c in analyse.primitives_dxf.cercles if c.calque == "CARTOUCHE")
    assert classer(cercle.calque, cercle.source.blocs, cercle.type_ligne).role == "cadre"
    assert _axe_a(resultat.structure, 13000.0)["label"] is None
    assert not [a for a in resultat.structure["grid"] if a.get("label") == "L7"]


def test_les_etiquettes_courantes_ne_changent_pas(lecture) -> None:
    _, resultat = lecture
    etiquettes = sorted(str(a.get("label")) for a in resultat.structure["grid"])
    assert etiquettes == ["1", "2", "3", "B", "L1", "None", "None", "None"]
    for a in resultat.structure["grid"]:
        if a.get("label") in ("1", "2", "3", "B"):
            assert a["label_source"]["via"] == "bulle"


def test_un_noeud_garde_le_separateur(lecture) -> None:
    """« L1 » × « 1 » ne donne pas « L11 », qui se lirait comme un autre axe."""
    _, resultat = lecture
    noms = {n["id"] for n in resultat.structure["grid_nodes"]}
    assert {"node:L1/1", "node:L1/2", "node:L1/3"} <= noms
    assert "node:L11" not in noms


def test_l_etiquette_lue_est_proposee_comme_file(lecture) -> None:
    _, resultat = lecture
    files = sorted(c.valeur for c in resultat.candidats
                   if c.methode == "geometrie" and c.categorie == "grid_line")
    assert files == ["1", "2", "3", "B", "L1"]
