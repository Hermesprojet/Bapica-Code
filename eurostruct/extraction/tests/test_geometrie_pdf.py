"""Des feuilles PDF vectorielles fabriquées, lues par leur géométrie.

LA QUESTION : un plan exporté en PDF, sans calques ni entités — des traits,
des caractères, des couleurs —, donne-t-il la grille, ses entraxes en
millimètres réels, les poteaux et le voile ? Et une feuille qui ne permet pas
de conclure (échelle absente ou contredite, plusieurs pages, pas de dessin)
est-elle refusée avec sa raison, sans rien convertir ?

Les deux feuilles réelles qui ont guidé ce lecteur ne sont pas commitées ;
``docs/GEOMETRIE_PDF.md`` dit ce qu'elles ont donné.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie.echelle import etablir_echelle, mm_par_point
from eurostruct_extraction.geometrie.pdf_vectoriel import lire_geometrie_pdf
from eurostruct_extraction.geometrie.primitives import Source, Texte
from eurostruct_extraction.geometrie.propositions import PLAFOND_GEOMETRIE_PDF
from fabrique_pdf_vectoriel import (
    MM_PAR_POINT_50,
    pdf_deux_pages,
    pdf_plan_hors_echelle,
    pdf_plan_sans_echelle_ecrite,
    pdf_plan_tirets_par_attribut,
    pdf_plan_vectoriel,
    pdf_texte_seul,
)

LARGEUR_PAGE, HAUTEUR_PAGE = 1190.55, 841.89


def _lire(octets: bytes):
    analyse = parse_document(octets, ocr=None)
    return analyse, extract_engineering_data(analyse)


def _geometrie(resultat, categorie: str) -> dict[str | None, list]:
    trouves: dict[str | None, list] = {}
    for c in resultat.candidats:
        if c.methode == "geometrie" and c.categorie == categorie:
            trouves.setdefault(c.repere, []).append(c)
    return trouves


@pytest.fixture(scope="module")
def feuille():
    return _lire(pdf_plan_vectoriel())


# ================================================================ la feuille
def test_la_feuille_donne_la_grille_en_millimetres_reels(feuille):
    _, resultat = feuille
    etiquettes = {c.valeur for c in resultat.candidats
                  if c.methode == "geometrie" and c.categorie == "grid_line"}
    assert etiquettes == {"A", "B", "C", "1", "2"}
    entraxes = _geometrie(resultat, "grid_spacing")
    assert {r: (c[0].valeur, c[0].unite) for r, c in entraxes.items()} == {
        "A-B": (6000, "mm"), "B-C": (6000, "mm"), "1-2": (5000, "mm")}
    [extremes] = _geometrie(resultat, "building_dimension")["A-C"]
    assert (extremes.valeur, extremes.unite) == (12000, "mm")


def test_les_poteaux_pleins_aux_noeuds_et_le_voile_plein(feuille):
    _, resultat = feuille
    [largeur] = _geometrie(resultat, "column_width")[None]
    [profondeur] = _geometrie(resultat, "column_depth")[None]
    assert (largeur.valeur, profondeur.valeur, largeur.unite) == (300, 300, "mm")
    assert largeur.position["count"] == 6
    assert {i["grid_node"] for i in largeur.position["instances"]} == {
        "A1", "A2", "B1", "B2", "C1", "C2"}
    [voile] = _geometrie(resultat, "wall_thickness")[None]
    assert (voile.valeur, voile.unite) == (200, "mm")


def test_aucune_poutre_n_est_tiree_de_la_seule_forme_et_le_refus_est_dit(feuille):
    """Deux traits parallèles sont dessinés entre A1 et B1 : sur une feuille,
    rien ne dit que c'est une poutre plutôt qu'un mur ou une marche."""
    _, resultat = feuille
    assert not any(c.categorie in ("beam_span", "beam_clear_span", "beam_width",
                                   "cantilever_length") for c in resultat.candidats)
    refus = {n["element"]: n["reason"] for n in resultat.structure["unresolved"]}
    assert "aucune poutre n'est reconnue par la seule forme" in refus["poutres"]


def test_l_echelle_cite_ses_deux_sources(feuille):
    _, resultat = feuille
    [entraxe] = _geometrie(resultat, "grid_spacing")["A-B"]
    declaration = entraxe.fondement["unit_declaration"]
    assert declaration["source"] == "echelle_ecrite_et_cotes"
    assert declaration["unit"] == "mm"
    assert declaration["scale"] == "1/50"
    assert declaration["written"]["text"] == "1/50"
    assert declaration["dimension_unit"] == "cm"
    # Six cotes sur sept concordent: la septième est écrite « 605 » sur 600.
    assert (declaration["concordant_dimensions"], declaration["dimensions_read"]) == (6, 7)
    unites = resultat.structure["units"]
    assert unites["source"] == "echelle_ecrite_et_cotes"
    assert unites["sheet"]["page"] == 1
    assert unites["sheet"]["mm_per_point"] == pytest.approx(MM_PAR_POINT_50)


def test_une_cote_ecrite_qui_contredit_le_dessin_plafonne_l_entraxe(feuille):
    _, resultat = feuille
    [bc] = _geometrie(resultat, "grid_spacing")["B-C"]
    [ab] = _geometrie(resultat, "grid_spacing")["A-B"]
    assert bc.confiance <= 0.4 < ab.confiance
    assert [n["displayed"] for n in bc.fondement["dimensions"]
            if n["forced_mismatch"]] == ["605"]
    assert any(n["measure_agrees"] for n in ab.fondement["dimensions"])


def test_chaque_proposition_porte_sa_page_sa_boite_et_le_plafond_pdf(feuille):
    _, resultat = feuille
    geometriques = [c for c in resultat.candidats if c.methode == "geometrie"]
    assert geometriques
    for c in geometriques:
        assert c.page == 1
        assert c.position["space"] == "page"
        assert c.confiance <= PLAFOND_GEOMETRIE_PDF
        b = c.boite
        assert b is not None
        assert 0 <= b.x0 <= b.x1 <= LARGEUR_PAGE and 0 <= b.y0 <= b.y1 <= HAUTEUR_PAGE


def test_la_boite_d_un_axe_est_ou_il_est_dessine(feuille):
    """L'axe A va de (0, -1800) à (0, 6800) mm réels, posé à (260, 150) pt,
    tourné de 10° : sa boîte, origine en haut à gauche, s'en déduit."""
    _, resultat = feuille
    [a] = [c for c in resultat.candidats
           if c.methode == "geometrie" and c.categorie == "grid_line" and c.valeur == "A"]

    def page(x_mm: float, y_mm: float) -> tuple[float, float]:
        x, y = x_mm / MM_PAR_POINT_50, y_mm / MM_PAR_POINT_50
        c, s = math.cos(math.radians(10)), math.sin(math.radians(10))
        return (260.0 + c * x - s * y, HAUTEUR_PAGE - (150.0 + s * x + c * y))

    (xa, ya), (xb, yb) = page(0.0, -1800.0), page(0.0, 6800.0)
    b = a.boite
    # Le trait mixte finit par un vide: l'axe s'arrête au dernier morceau.
    assert b.x0 == pytest.approx(min(xa, xb), abs=4.0)
    assert b.x1 == pytest.approx(max(xa, xb), abs=4.0)
    assert b.y0 == pytest.approx(min(ya, yb), abs=4.0)
    assert b.y1 == pytest.approx(max(ya, yb), abs=4.0)


def test_le_compte_rendu_dit_ce_que_la_feuille_a_donne(feuille):
    analyse, _ = feuille
    assert "echelle 1/50 ecrite et confirmee par 6 cote(s) sur 7 (lues en cm)" in analyse.detail
    lu = analyse.compte_rendu["geometry_read"]
    assert lu["read"] is True
    assert lu["axis_style"] == "pdf:#DE0000:1.5"
    assert lu["dimension_style"] == "pdf:#0000FF:1"
    assert (lu["axis_bubbles"], lu["axes_rebuilt"], lu["dimensions_rebuilt"]) == (5, 5, 7)
    assert lu["scale"]["established"] is True


# ========================================================== l'autre exporteur
def test_tirets_par_attribut_et_corps_dans_tm_donnent_la_meme_grille():
    """Motif de tirets par l'opérateur ``d``, bulles en courbes de Bézier,
    texte en ``1 Tf`` mis à l'échelle par ``Tm`` : la même lecture."""
    analyse, resultat = _lire(pdf_plan_tirets_par_attribut())
    assert analyse.compte_rendu["geometry_read"]["axis_style"] == "pdf:#DE0000:1.5:tirets"
    entraxes = _geometrie(resultat, "grid_spacing")
    assert {r: c[0].valeur for r, c in entraxes.items()} == {
        "A-B": 6000, "B-C": 6000, "1-2": 5000}


def test_le_corps_du_texte_est_retrouve_quel_que_soit_l_exporteur():
    """``10 Tf`` et une rotation seule, ou ``1 Tf`` et l'échelle dans ``Tm`` :
    l'étiquette d'axe mesure 10 pt, soit 176,4 mm réels au 1/50."""
    for octets in (pdf_plan_vectoriel(), pdf_plan_tirets_par_attribut()):
        prims = lire_geometrie_pdf(octets).primitives
        [a] = [t for t in prims.textes if t.texte == "A"]
        assert a.hauteur == pytest.approx(10.0 * MM_PAR_POINT_50, rel=1e-3)
        assert a.rotation == pytest.approx(10.0, abs=0.01)


# ===================================================================== refus
def test_sans_echelle_ecrite_rien_n_est_converti():
    analyse, resultat = _lire(pdf_plan_sans_echelle_ecrite())
    assert "echelle non etablie, longueurs en points sans unite" in analyse.detail
    assert resultat.structure["units"]["drawing"] is None
    refus = {n["element"]: n["reason"] for n in resultat.structure["unresolved"]}
    assert "aucune echelle ecrite sur la feuille" in refus["echelle"]
    # Au 1/5 en mm ou au 1/50 en cm, les nombres se lisent pareil: les deux
    # lectures sont dites, aucune n'est appliquée.
    assert "1/5 lues en mm ou 1/50 lues en cm" in refus["echelle"]
    [ab] = _geometrie(resultat, "grid_spacing")["A-B"]
    assert ab.unite is None
    assert ab.valeur == pytest.approx(6000.0 / MM_PAR_POINT_50, abs=0.01)
    assert ab.fondement["unit_basis"] == "absente"


def test_une_echelle_ecrite_que_les_cotes_contredisent_n_est_pas_appliquee():
    """« 1/50 » au cartouche, mais tracé au 1/100."""
    _, resultat = _lire(pdf_plan_hors_echelle())
    assert resultat.structure["units"]["drawing"] is None
    refus = {n["element"]: n["reason"] for n in resultat.structure["unresolved"]}
    assert "echelle ecrite (1/50) non confirmee par les cotes: 0 sur 7" in refus["echelle"]
    assert "1/100 lues en cm" in refus["echelle"]
    assert not any(c.unite == "mm" for c in resultat.candidats if c.methode == "geometrie")


def test_un_pdf_de_deux_pages_n_est_lu_que_pour_son_texte():
    analyse, resultat = _lire(pdf_deux_pages())
    assert analyse.primitives_dxf is None
    assert analyse.compte_rendu["geometry_read"] == {
        "read": False,
        "reason": "document de 2 pages: la geometrie n'est lue que sur un plan d'une seule "
                  "feuille"}
    assert resultat.structure is None
    assert not any(c.methode == "geometrie" for c in resultat.candidats)


def test_une_page_de_texte_n_est_pas_un_dessin_et_son_texte_reste_lu():
    analyse, resultat = _lire(pdf_texte_seul())
    assert analyse.compte_rendu["geometry_read"]["read"] is False
    assert "la page n'est pas un dessin" in analyse.compte_rendu["geometry_read"]["reason"]
    assert any(c.categorie == "concrete_class" and c.valeur == "C30/37"
               for c in resultat.candidats)


# ==================================================================== échelle
def _mot(texte: str) -> Texte:
    return Texte("pdf:texte:#000000", "CONTINUOUS", Source("t", "PDF_TEXTE"), texte,
                 (0.0, 0.0), 0.0, 9.0, (0.0, 0.0, 20.0, 9.0))


def _cotes_cm(valeurs: list[float], n: int = 50) -> list[tuple[str, float, float]]:
    return [(f"{v:g}", v, v * 10.0 / mm_par_point(n)) for v in valeurs]


def test_l_echelle_exige_cinq_cotes_concordantes():
    quatre = etablir_echelle([_mot("1/50")], _cotes_cm([600, 500, 450, 300]))
    assert not quatre.etablie
    cinq = etablir_echelle([_mot("1:50")], _cotes_cm([600, 500, 450, 300, 120]))
    assert cinq.etablie and (cinq.n, cinq.unite_des_cotes) == (50, "cm")


def test_l_echelle_exige_que_les_concordantes_soient_la_majorite():
    """Cinq cotes concordent sur dix: 50 % < 60 %, rien n'est établi."""
    bonnes = _cotes_cm([600, 500, 450, 300, 120])
    fausses = [(t, v, m * 1.3) for t, v, m in _cotes_cm([700, 800, 900, 410, 220])]
    echelle = etablir_echelle([_mot("1/50")], bonnes + fausses)
    assert not echelle.etablie
    assert "5 sur 10 concordent" in echelle.note
