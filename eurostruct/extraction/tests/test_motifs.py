"""Les règles de lecture : ce qu'elles lisent en trois langues — et ce qu'elles
refusent de deviner."""

from __future__ import annotations

import pytest

from eurostruct_extraction.extracteurs.lignes import Ligne
from eurostruct_extraction.extracteurs.motifs import Contexte, extraire_des_lignes
from eurostruct_extraction.modele import Boite, Mot


def _ligne(texte: str) -> Ligne:
    mots, debuts, x, curseur = [], [], 10.0, 0
    for mot in texte.split(" "):
        mots.append(Mot(mot, Boite(x, 100, x + 5 * len(mot), 110), "texte_natif"))
        debuts.append(curseur)
        curseur += len(mot) + 1
        x += 5 * len(mot) + 5
    return Ligne(1, texte, "texte_natif", tuple(mots), tuple(debuts),
                 largeur_page=595, hauteur_page=842)


def _lire(texte: str) -> list[tuple]:
    return [(c.categorie, c.valeur, c.unite)
            for c in extraire_des_lignes([_ligne(texte)], Contexte())]


@pytest.mark.parametrize(("texte", "attendu"), [
    # NEERLANDAIS
    ("Balk B3 30x50 cm", [("beam_width", 30, "cm"), ("beam_depth", 50, "cm")]),
    ("Kolom K2 400x400 mm", [("column_width", 400, "mm"), ("column_depth", 400, "mm")]),
    ("overspanning 5,40 m", [("beam_span", 5.4, "m")]),
    ("Dekking 25 mm", [("concrete_cover", 25, "mm")]),
    ("Stramien 1-2: 5400 mm", [("grid_spacing", 5400, "mm")]),
    ("verdiepingshoogte 3,20 m", [("story_height", 3.2, "m")]),
    ("nuttige last 3 kN/m2", [("load_value", 3, "kN/m^2")]),
    # ANGLAIS
    ("stirrups T8@150 mm", [("link_diameter", 8, "mm"), ("link_spacing", 150, "mm")]),
    ("Beam B1 300x600 mm", [("beam_width", 300, "mm"), ("beam_depth", 600, "mm")]),
    ("slab thickness 250 mm", [("slab_thickness", 250, "mm")]),
    ("live load 5 kPa", [("load_value", 5, "kPa")]),
    ("overall length 32,50 m", [("building_dimension", 32.5, "m")]),
    # FRANCAIS
    ("4Ø20 + 2Ø12", [("bar_count", 4, None), ("bar_diameter", 20, "mm"),
                     ("bar_count", 2, None), ("bar_diameter", 12, "mm")]),
    ("emprise 12,00 x 24,00 m", [("building_dimension", 12.0, "m"),
                                 ("building_dimension", 24.0, "m")]),
    ("C25/30 XC4 XF1", [("concrete_class", "C25/30", None),
                        ("exposure_class", "XC4", None), ("exposure_class", "XF1", None)]),
    ("Profil IPE 300 S355J2", [("steel_grade", "S355J2", None)]),
    ("Armatures B400A et B600C", [("steel_grade", "B400A", None),
                                  ("steel_grade", "B600C", None),
                                  ("material_specification",
                                   "Armatures B400A et B600C", None)]),
    ("niveau -0,60", [("floor_level", -0.6, "m")]),
])
def test_ce_qui_est_ecrit_est_lu(texte, attendu):
    assert _lire(texte) == attendu


@pytest.mark.parametrize("texte", [
    "C30/35",                       # pas une classe de l'EN 206
    "Q = 2",                        # une charge sans unite n'est pas une charge
    "Echelle 1/50",                 # une echelle n'est pas une section
    "30x60",                        # une section sans repere ni mot-cle: de quoi ?
    "Plancher haut +3,20 m",        # un niveau, pas une epaisseur
    "mur mitoyen 3,00 m",           # un mur sans « ep. »: rien n'est suppose
    "4 HA 23",                      # pas un diametre du commerce
    "Ref. A1 12x18",                # repere de prefixe inconnu
    "Terras 2",                     # « as » dans un mot: pas un axe (plan reel)
    "Glas 4 mm",                    # idem
    "profiles 2",                   # « files » dans un mot
])
def test_ce_qui_n_est_pas_dit_n_est_pas_devine(texte):
    lu = _lire(texte)
    categories = {c for c, _, _ in lu}
    assert not categories - {"floor_level"}, lu
    if texte.startswith("Plancher"):
        assert lu == [("floor_level", 3.2, "m")]


@pytest.mark.parametrize(("texte", "attendu"), [
    ("as B", [("grid_line", "B", None)]),
    ("Axe 3", [("grid_line", "3", None)]),
    ("Terras 2 - as 4", [("grid_line", "4", None)]),
])
def test_un_axe_nomme_par_un_mot_entier_reste_lu(texte, attendu):
    assert _lire(texte) == attendu


def test_un_meme_texte_ne_nourrit_qu_une_proposition():
    """« C30/37 » n'est pas aussi une section 30/37 du poteau voisin."""
    lu = _lire("Poteau C1 béton C30/37")
    assert ("concrete_class", "C30/37", None) in lu
    assert not [x for x in lu if x[0].startswith("column_")]


def test_le_prefixe_de_repere_classe_et_le_dit_avec_une_confiance_basse():
    candidats = extraire_des_lignes([_ligne("P2 (25/50) cm")], Contexte())
    largeur = [c for c in candidats if c.categorie == "beam_width"][0]
    assert largeur.fondement["classement"] == "prefixe_de_repere:P"
    assert largeur.confiance < 0.5


def test_une_section_sans_unite_ni_mention_reste_sans_unite():
    largeur = extraire_des_lignes([_ligne("Poutre P1 30x60")], Contexte())[0]
    assert largeur.unite is None
    assert largeur.fondement["unit_basis"] == "absente"


def test_un_bloc_de_notes_est_lu_ligne_a_ligne():
    lignes = [_ligne("NOTES GENERALES"), _ligne("- Toutes les cotes sont a verifier"),
              _ligne("- Beton de proprete ep. 5 cm"), _ligne("Cartouche")]
    notes = [c.valeur for c in extraire_des_lignes(lignes, Contexte())
             if c.categorie == "structural_note"]
    assert notes == ["- Toutes les cotes sont a verifier", "- Beton de proprete ep. 5 cm"]
