"""La géométrie plane, la classification des calques et la lecture des repères.

Des briques sans fichier DXF : ce que chacune décide doit pouvoir se lire ici.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_extraction.geometrie.classification import (
    classer,
    est_type_de_ligne_cache,
    est_type_de_ligne_d_axe,
    role_du_nom,
)
from eurostruct_extraction.geometrie.construction import tolerances_du_dessin
from eurostruct_extraction.geometrie.libelles import lire_repere
from eurostruct_extraction.geometrie.noyau import (
    IndexSpatial,
    Tolerances,
    decouper_par_bande,
    point_dans_polygone,
    quantifier,
    rectangle_de,
)
from eurostruct_extraction.geometrie.primitives import PrimitivesDxf

MM = Tolerances(longueur=1.0, quantum=0.001, mm_par_unite=1.0)


# ------------------------------------------------------------------ noyau
def test_la_quantification_efface_le_bruit_des_flottants_et_rien_d_autre():
    assert quantifier(600.0000000001, 0.0001) == 600
    assert isinstance(quantifier(600.0000000001, 0.0001), int)
    # UNE MESURE DE 599,96 RESTE 599,96: aucun arrondi « metier ».
    assert quantifier(599.96, 0.0001) == 599.96
    assert quantifier(5699.9999999, 0.001) == 5700


@pytest.mark.parametrize(("unite", "quantum"), [
    ("mm", 0.001), ("cm", 0.0001), ("m", 1e-6),
    # UN MICROMETRE EN POUCES (3,9e-5) DEVIENT 1e-5: un pas decimal.
    ("in", 1e-5), ("ft", 1e-6),
])
def test_le_pas_de_quantification_est_decimal_et_vaut_au_plus_un_micrometre(unite, quantum):
    tol = tolerances_du_dessin(PrimitivesDxf(), unite)
    assert math.isclose(tol.quantum, quantum)
    assert quantifier(120.0 + 1e-9, tol.quantum) == 120


def test_sans_unite_les_seuils_suivent_l_emprise_du_dessin():
    tol = tolerances_du_dessin(PrimitivesDxf(), None)
    assert tol.mm_par_unite is None
    assert math.log10(tol.quantum) == int(math.log10(tol.quantum))


def test_un_rectangle_tourne_est_reconnu_avec_ses_cotes():
    a = math.radians(30)
    u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    coins = [(100 + su * 200 * u[0] + sv * 150 * v[0], 50 + su * 200 * u[1] + sv * 150 * v[1])
             for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    rect = rectangle_de(coins, MM)
    assert rect is not None
    assert sorted((round(rect.longueur_u, 6), round(rect.longueur_v, 6))) == [300, 400]
    assert rect.centre == pytest.approx((100, 50))


def test_un_trapeze_n_est_pas_un_rectangle():
    assert rectangle_de([(0, 0), (400, 0), (300, 200), (100, 200)], MM) is None


def test_la_bande_d_une_poutre_decoupe_un_poteau():
    # Le poteau 400 x 400 centre en (6000, 0), une bande de 300 de large le long de x.
    poteau = [(5800, -200), (6200, -200), (6200, 200), (5800, 200)]
    morceau = decouper_par_bande(poteau, (0.0, 0.0), (0.0, 1.0), 150.0)
    xs = sorted({round(p[0], 6) for p in morceau})
    ys = sorted({round(p[1], 6) for p in morceau})
    assert (xs[0], xs[-1], ys[0], ys[-1]) == (5800, 6200, -150, 150)
    assert point_dans_polygone((6000, 0), poteau)
    assert not point_dans_polygone((6300, 0), poteau)


def test_une_recherche_de_l_index_est_bornee_par_ce_qui_est_range():
    # Des cases de 1e-4 et une boite de recherche de 4 x 4: 1,6e9 cases, que
    # la recherche ne parcourt plus.
    import time

    index = IndexSpatial(1e-4)
    petit = index.ajouter((0.0, 0.0, 0.0, 0.0))
    grand = index.ajouter((-1000.0, -1000.0, 1000.0, 1000.0))  # rangee a part
    loin = index.ajouter((50.0, 50.0, 50.0, 50.0))
    debut = time.perf_counter()
    assert index.pres_de((0.0, 0.0, 0.0, 0.0), marge=2.0) == [petit, grand]
    assert index.pres_de((49.0, 49.0, 49.0, 49.0), marge=2.0) == [grand, loin]
    assert time.perf_counter() - debut < 1.0
    assert IndexSpatial(1e-4).pres_de((0, 0, 1, 1), marge=1.0) == []


def test_l_index_spatial_ne_rend_que_ce_qui_est_proche():
    index = IndexSpatial(1000.0)
    proches = [index.ajouter((x, x, x, x)) for x in (0.0, 500.0, 5000.0)]
    assert index.pres_de((0, 0, 0, 0), marge=600) == proches[:2]
    assert index.pres_de((4900, 4900, 4900, 4900), marge=200) == [proches[2]]


# --------------------------------------------------------- classification
@pytest.mark.parametrize(("nom", "role"), [
    ("S-COLS", "poteau"), ("POTEAUX", "poteau"), ("Kolommen", "poteau"),
    ("Stützen", "poteau"), ("COL-400x400", "poteau"),
    ("S-BEAM", "poutre"), ("POUTRES", "poutre"), ("Retombées", "poutre"),
    ("BALKEN", "poutre"), ("Unterzüge", "poutre"),
    ("VOILES", "voile"), ("S-WALL", "voile"), ("Wanden", "voile"),
    ("DALLES", "dalle"), ("Vloer", "dalle"), ("Decke", "dalle"),
    ("S-GRID", "axe"), ("AXES", "axe"), ("Stramien", "axe"), ("Achsen", "axe"),
    ("COTES", "cote"), ("S-ANNO-DIMS", "cote"), ("Maatvoering", "cote"),
    ("S-ANNO-TEXT", "texte"), ("FERRAILLAGE", "armature"), ("Wapening", "armature"),
    ("CARTOUCHE", "cadre"), ("TREMIES", "tremie"), ("Sparingen", "tremie"),
    ("NIVEAUX", "niveau"),
    # Des noms qui ne disent rien de l'element.
    ("COFFRAGE", None), ("0", None), ("STRUCTURE", None), ("MURIEL", None),
])
def test_le_nom_d_un_calque_designe_un_role_en_quatre_langues(nom, role):
    assert role_du_nom(nom) == role


def test_le_bloc_l_emporte_sur_le_calque_et_le_dit():
    c = classer("S-BEAM", ("COL-400x400",), "CONTINUOUS")
    assert (c.role, c.regle, c.motif) == ("poteau", "bloc", "COL-400x400")
    # LE BLOC LE PLUS INTERIEUR est le plus precis.
    c = classer("0", ("ETAGE-TYPE", "POUTRE-30"), "CONTINUOUS")
    assert (c.role, c.motif) == ("poutre", "POUTRE-30")


def test_un_trait_mixte_sur_un_calque_muet_est_un_axe():
    c = classer("0", (), "CENTER")
    assert (c.role, c.regle) == ("axe", "type_de_ligne")
    assert est_type_de_ligne_d_axe("ACAD_ISO04W100")


def test_un_trait_cache_sur_un_calque_generique_est_un_indice_de_retombee():
    c = classer("COFFRAGE", (), "HIDDEN")
    assert c.role == "inconnu" and c.cache and c.generique
    assert est_type_de_ligne_cache("DASHED")


# --------------------------------------------------------------- repères
@pytest.mark.parametrize(("texte", "marque", "genre", "section"), [
    ("P1 30x60", "P1", "poutre", ("30", "60")),
    ("P5 25x50", "P5", "poutre", ("25", "50")),
    ("C1", "C1", "poteau", None),
    ("B1 300x600", "B1", "poutre", ("300", "600")),
    ("V2", "V2", "voile", None),
    ("Poutre P12 (30×60)", "P12", "poutre", ("30", "60")),
])
def test_un_repere_est_lu_avec_sa_section_ecrite(texte, marque, genre, section):
    lu = lire_repere(texte)
    assert lu is not None
    assert lu["marque"] == marque
    assert (lu["genre_mot"] or lu["genre_prefixe"]) == genre
    assert lu["section"] == section


@pytest.mark.parametrize("texte", [
    "C30/37", "B500B", "BE 500 S", "HA12", "T16", "XC4", "R+1", "N+2",
    "IPE 300", "HEA 200", "Dalle pleine ép. 20", "",
])
def test_une_designation_n_est_pas_un_repere(texte):
    assert lire_repere(texte) is None
