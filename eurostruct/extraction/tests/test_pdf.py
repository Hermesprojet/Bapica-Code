"""Un plan PDF à couche texte : chaque catégorie, à sa place, avec son texte lu."""

from __future__ import annotations

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from fabrique import LIGNES_DU_PLAN, pdf_de_texte


@pytest.fixture(scope="module")
def resultat():
    analyse = parse_document(pdf_de_texte([LIGNES_DU_PLAN]), ocr=None)
    return analyse, extract_engineering_data(analyse)


def _un(resultat, categorie, **filtre):
    trouves = [c for c in resultat[1].candidats if c.categorie == categorie
               and all(getattr(c, k) == v for k, v in filtre.items())]
    assert len(trouves) == 1, (categorie, filtre, trouves)
    return trouves[0]


def test_le_plan_est_lu_par_sa_couche_texte(resultat):
    analyse, _ = resultat
    assert analyse.statut == "analyse"
    assert analyse.couche_texte is True
    assert analyse.nombre_de_pages == 1
    assert analyse.compte_rendu["pages"][0]["method"] == "texte_natif"


@pytest.mark.parametrize(("categorie", "valeur", "unite", "repere"), [
    ("beam_width", 30, "cm", "P1"),
    ("beam_depth", 60, "cm", "P1"),
    ("beam_span", 6.0, "m", "P1"),
    ("concrete_class", "C30/37", None, None),
    ("steel_grade", "B500B", None, None),
    ("concrete_cover", 30, "mm", None),
    ("bar_count", 4, None, "P1"),
    ("bar_diameter", 20, "mm", "P1"),
    ("link_diameter", 8, "mm", "P1"),
    ("link_spacing", 15, "cm", "P1"),
    ("slab_thickness", 20, "cm", None),
    ("floor_level", 3.2, "m", "Niveau +1"),
    ("story_height", 3.0, "m", None),
    ("column_width", 30, "cm", "C1"),
    ("column_depth", 30, "cm", "C1"),
    ("load_value", 2.5, "kN/m^2", None),
    ("building_dimension", 24.0, "m", None),
    ("grid_spacing", 6.0, "m", "A-B"),
])
def test_chaque_categorie_est_proposee_avec_sa_valeur_et_son_unite(
        resultat, categorie, valeur, unite, repere):
    candidat = _un(resultat, categorie, repere=repere)
    assert candidat.valeur == valeur
    assert candidat.unite == unite
    assert candidat.methode == "texte_natif"
    assert candidat.page == 1


def test_les_classes_d_exposition_sont_lues_ou_elles_sont(resultat):
    valeurs = sorted(c.valeur for c in resultat[1].candidats
                     if c.categorie == "exposure_class")
    assert valeurs == ["XC3", "XC4"]


def test_la_note_et_la_specification_sont_proposees_telles_quelles(resultat):
    note = _un(resultat, "structural_note")
    assert note.valeur == "NOTE : les cotes sont à vérifier sur chantier"
    specs = [c.valeur for c in resultat[1].candidats
             if c.categorie == "material_specification"]
    assert "Béton C30/37 - classe d'exposition XC3" in specs


def test_la_boite_couvre_les_mots_lus_et_pas_la_ligne_entiere(resultat):
    """« C30/37 » est au milieu de sa ligne : sa boîte commence après « Béton »."""
    classe = _un(resultat, "concrete_class")
    x0, y0, x1, y1 = classe.boite.en_liste()
    assert 60 < x0 < x1 < 120
    assert 125 <= y0 < y1 <= 145
    # La ligne entiere est le texte brut cite, pas la boite.
    assert classe.texte_brut == "Béton C30/37 - classe d'exposition XC3"


def test_une_etiquette_eloignee_sur_la_meme_hauteur_ne_se_colle_pas(resultat):
    """« XC4 » est à x = 400, sur la hauteur de « Poutre P1 30x60 »."""
    xc4 = [c for c in resultat[1].candidats if c.valeur == "XC4"][0]
    assert xc4.texte_brut == "XC4"
    assert xc4.boite.x0 >= 399


def test_l_unite_d_une_section_vient_de_la_mention_citee(resultat):
    largeur = _un(resultat, "beam_width")
    assert largeur.fondement["unit_basis"] == "declaration"
    citation = largeur.fondement["unit_declaration"]
    assert citation["raw_text"] == "Cotes en cm"
    assert citation["page"] == 1
    assert largeur.fondement["convention_section"] == "largeur x hauteur (b x h)"


def test_le_niveau_dit_que_son_unite_est_une_convention(resultat):
    niveau = _un(resultat, "floor_level")
    assert niveau.fondement["unit_basis"] == "convention"
    assert niveau.fondement["convention"] == "niveau_m"


def test_la_charge_dit_sa_nature_et_n_est_rien_d_autre(resultat):
    charge = _un(resultat, "load_value")
    assert charge.fondement["load_nature"] == "exploitation"


def test_la_position_donne_les_dimensions_de_la_page(resultat):
    classe = _un(resultat, "concrete_class")
    assert classe.position == {"origin": "top-left", "unit": "pt",
                               "page_width": 595.0, "page_height": 842.0}


def test_sans_mention_d_unite_la_section_n_a_pas_d_unite():
    lignes = [line for line in LIGNES_DU_PLAN if line[3] != "Cotes en cm"]
    analyse = parse_document(pdf_de_texte([lignes]), ocr=None)
    largeur = [c for c in extract_engineering_data(analyse).candidats
               if c.categorie == "beam_width"][0]
    assert largeur.unite is None
    assert largeur.fondement["unit_basis"] == "absente"
    # ET ELLE LE PAIE: une valeur sans unite vaut moins qu'une valeur citee.
    assert largeur.confiance < 0.5


def test_deux_mentions_contradictoires_ne_valent_aucune():
    page1 = [(40, 40, 10, "Cotes en cm"), (40, 60, 10, "Poutre P1 30x60")]
    page2 = [(40, 40, 10, "Cotes en mm")]
    page3 = [(40, 40, 10, "Poutre P2 25x50")]
    analyse = parse_document(pdf_de_texte([page1, page2, page3]), ocr=None)
    candidats = extract_engineering_data(analyse).candidats
    p1 = [c for c in candidats if c.repere == "P1" and c.categorie == "beam_width"][0]
    p2 = [c for c in candidats if c.repere == "P2" and c.categorie == "beam_width"][0]
    assert p1.unite == "cm"          # la mention de SA page
    assert p2.unite is None          # le document se contredit: rien n'est suppose


def test_les_pages_sont_numerotees_a_partir_de_un():
    analyse = parse_document(pdf_de_texte([[(40, 40, 10, "FICTIF")],
                                           [(40, 40, 10, "Béton C25/30")]]), ocr=None)
    classe = [c for c in extract_engineering_data(analyse).candidats
              if c.categorie == "concrete_class"][0]
    assert classe.page == 2


def test_un_pdf_illisible_est_une_analyse_en_echec_et_non_une_exception():
    analyse = parse_document(b"%PDF-1.4\nFICTIF tronque", ocr=None)
    assert analyse.statut == "echec"
    assert analyse.detail.startswith("lecture impossible")
    assert extract_engineering_data(analyse).candidats == ()


def test_la_lecture_est_deterministe():
    octets = pdf_de_texte([LIGNES_DU_PLAN])
    def lire():
        analyse = parse_document(octets, ocr=None)
        return [c.en_ligne() for c in extract_engineering_data(analyse).candidats]

    assert lire() == lire()
