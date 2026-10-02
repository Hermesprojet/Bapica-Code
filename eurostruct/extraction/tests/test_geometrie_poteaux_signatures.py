"""Les poteaux par leur SIGNATURE, quel que soit leur nom (phase G4).

Voir ``docs/GEOMETRIE_D_ABORD_G4.md``. LA QUESTION : un plan dont aucun calque,
aucun bloc ne dit « poteau » donne-t-il ses poteaux — et seulement eux : ni les
cercles d'annotation, ni les dessins de pieux, ni les bouts de voile, ni les
symboles, ni un détail hors de la grille ? Et un plan dont les noms sont
reconnus garde-t-il exactement ses poteaux ?
"""

from __future__ import annotations

import pytest

import fabrique_geometrie as F
from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import poteaux as module_poteaux
from fabrique_geometrie import dxf_grille_implicite, dxf_poteaux_signatures

#: Les poteaux 40 × 40, contour et hachure, du plan de ``dxf_poteaux_signatures``.
HACHURES = ("A2", "C2", "F3", "F4")


def _resultat(octets: bytes, **options: object):  # noqa: ANN202
    return extract_engineering_data(parse_document(octets, **options))


def _modele(octets: bytes) -> dict:
    return _resultat(octets).structure


def _par_noeud(modele: dict) -> dict[str, dict]:
    return {c["grid_node"]: c for c in modele["columns"] if c["grid_node"]}


@pytest.fixture(scope="module")
def neutre() -> dict:
    return _modele(dxf_poteaux_signatures())


# ======================================================== sans aucun nom
def test_des_sections_coupees_aux_noeuds_sans_aucun_nom_sont_des_poteaux(neutre):
    poteaux = _par_noeud(neutre)
    for noeud in HACHURES:
        c = poteaux[noeud]
        assert (c["width"], c["depth"], c["filled"]) == (40, 40, True)
        assert (c["evidence"]["classified_by"], c["confidence"]) == ("geometrie", 0.85)
        assert {"section", "coupe", "au_noeud", "zone", "section_repetee"} <= set(
            c["evidence"]["signature"])
        assert "matched_name" not in c["evidence"]
    assert neutre["report"]["columns"]["structural_zone"] == "signature_a"


def test_les_noms_ne_font_que_confirmer(neutre):
    """Les mêmes poteaux nommés ``POTEAUX`` : mêmes identifiants, centres,
    sections, nœuds ; le nom concordant est cité et ajoute 0,05."""
    nomme = _modele(dxf_poteaux_signatures(noms=True))

    def geometrie(modele: dict) -> set[tuple]:
        return {(c["id"], tuple(c["centre"]), c["width"], c["depth"], c["grid_node"])
                for c in modele["columns"] if c["grid_node"] in HACHURES}

    assert len(geometrie(neutre)) == 4 and geometrie(neutre) == geometrie(nomme)
    for noeud in HACHURES:
        c = _par_noeud(nomme)[noeud]
        assert (c["evidence"]["classified_by"], c["confidence"]) == ("geometrie", 0.9)
        assert c["evidence"]["matched_name"] == "POTEAUX"


def test_une_hachure_sur_un_calque_texte_coupe_toujours_le_poteau(neutre):
    """Le remplissage est une preuve N1 : le nom de son calque ne compte pas — ni
    confirmation, ni conflit. Il est cité dans la preuve."""
    modele = _modele(dxf_poteaux_signatures(hachures_texte=True))
    poteaux = _par_noeud(modele)
    for noeud in HACHURES:
        c = poteaux[noeud]
        assert c["filled"] and (c["evidence"]["classified_by"], c["confidence"]) == (
            "geometrie", 0.85)
        assert "TEXTES" in c["evidence"]["layers"]
    assert [c["id"] for c in modele["columns"]] == [c["id"] for c in neutre["columns"]]
    assert [u["element"] for u in modele["unresolved"]] == ["column:F1"]


# ================================================ ce qui n'est pas un poteau
def test_les_cercles_d_annotation_vides_ne_sont_pas_des_poteaux(neutre):
    assert not {"A1", "B1"} & set(_par_noeud(neutre))
    # Deux cercles, deux poteaux vides sans repère (C4, D4), deux blocs qui ne
    # sont pas des poteaux-types (D3, E3) : des sections vides, comptées.
    assert neutre["report"]["column_candidates_rejected"]["partielle_vide"] == 6


def test_la_hachure_d_un_pieu_sur_un_calque_texte_n_est_pas_un_poteau(neutre):
    """C1.6 sans nom : même centre et même taille qu'un pieu, quel que soit le
    calque — ni un poteau, ni un conflit."""
    assert not {"C1", "D1"} & set(_par_noeud(neutre))
    assert {"C1", "D1"} <= {p["grid_node"] for p in neutre["piles"]}
    assert not any(u["element"] in ("column:C1", "column:D1") for u in neutre["unresolved"])


def test_un_massif_plein_nomme_semelle_au_noeud_est_un_conflit_dit(neutre):
    f1 = _par_noeud(neutre)["F1"]
    assert (f1["width"], f1["depth"], f1["confidence"]) == (150, 150, 0.4)
    assert f1["evidence"]["classified_by"] == "geometrie"
    (doute,) = [u for u in neutre["unresolved"] if u["element"] == f1["id"]]
    assert "fondation (SEMELLES)" in doute["reason"]


def test_un_bout_de_voile_n_est_pas_un_poteau_un_poteau_au_bout_d_un_voile_en_est_un(neutre):
    poteaux = _par_noeud(neutre)
    assert "B2" not in poteaux
    assert (poteaux["C2"]["width"], poteaux["C2"]["depth"]) == (40, 40)
    assert neutre["report"]["column_candidates_rejected"]["bout_de_voile"] == 1


def test_ce_qui_n_est_pas_une_section_n_est_pas_un_poteau(neutre):
    """Un triangle, une barre biaise (sections irrégulières), un chevron (non
    compact), pleins, aux nœuds."""
    assert not {"D2", "E2", "F2"} & set(_par_noeud(neutre))
    rejets = neutre["report"]["column_candidates_rejected"]
    assert (rejets["section_irreguliere"], rejets["non_compact"]) == (2, 1)


def test_un_poteau_rond_dessine_par_sa_seule_hachure_ne_propose_rien():
    resultat = _resultat(dxf_poteaux_signatures())
    e1 = _par_noeud(resultat.structure)["E1"]
    assert (e1["shape"], e1["filled"], e1["confidence"]) == ("polygone", True, 0.85)
    assert not [c for c in resultat.candidats if c.categorie == "column_diameter"]


def test_un_detail_hors_de_la_zone_structurelle_n_est_pas_un_poteau(neutre):
    assert len(neutre["grid_nodes"]) == 25
    assert all(c["centre"][0] < 4000 for c in neutre["columns"])
    assert neutre["report"]["column_candidates_rejected"]["hors_zone"] == 1


def test_un_massif_sur_pieux_et_un_socle_vide_sont_des_contenants(neutre):
    poteaux = _par_noeud(neutre)
    assert "E4" not in poteaux
    assert (poteaux["F4"]["width"], poteaux["F4"]["depth"]) == (40, 40)
    assert neutre["report"]["column_candidates_rejected"]["contenant"] == 2


# ============================================================ complétions
def test_un_poteau_vide_en_bloc_repete_a_l_echelle_1_est_complete(neutre):
    poteaux = _par_noeud(neutre)
    for noeud in ("A3", "B3", "C3"):
        c = poteaux[noeud]
        assert not c["filled"] and c["confidence"] == 0.75
        assert c["evidence"]["classified_by"] == "geometrie"
        assert "bloc_repete" in c["evidence"]["signature"]
        assert c["evidence"]["blocks"] == ["B010"]
    # Un bloc à attribut, un bloc inséré à l'échelle 5 : rien.
    assert not {"D3", "E3"} & set(poteaux)


def test_un_poteau_vide_est_complete_par_un_repere_de_poteau(neutre):
    poteaux = _par_noeud(neutre)
    assert (poteaux["A4"]["mark"], poteaux["B4"]["mark"]) == ("C3", "POT12")
    for noeud in ("A4", "B4"):
        c = poteaux[noeud]
        assert (c["evidence"]["classified_by"], c["confidence"]) == ("forme", 0.6)
        assert "repere" in c["evidence"]["signature"]
    # Sans repère, ou « P1 » — un repère de POUTRE pour le lecteur de repères : rien.
    assert not {"C4", "D4"} & set(poteaux)


# ================================================== sans aucune grille : C2
def test_une_grille_implicite_donne_des_poteaux_jamais_des_axes():
    modele = _modele(dxf_grille_implicite(carrelage=True))
    assert modele["grid"] == [] and modele["grid_nodes"] == []
    poteaux = modele["columns"]
    assert len(poteaux) == 12 and all(c["grid_node"] is None for c in poteaux)
    assert {(c["width"], c["depth"], c["confidence"]) for c in poteaux} == {(40, 40, 0.65)}
    assert all({"grille_implicite", "coupe", "section"} <= set(c["evidence"]["signature"])
               for c in poteaux)
    assert modele["report"]["columns"]["structural_zone"] == "non_applicable"


def test_sans_unite_la_grille_implicite_ne_s_applique_pas():
    assert _modele(dxf_grille_implicite(unite=False))["columns"] == []


# ============================================================ feuille PDF
def test_une_feuille_pdf_garde_ses_poteaux_et_ecarte_ce_qui_n_est_pas_une_section():
    from fabrique_pdf_vectoriel import pdf_plan_vectoriel

    resultat = _resultat(pdf_plan_vectoriel(formes_non_poteau=True), ocr=None)
    modele = resultat.structure
    assert {c["grid_node"] for c in modele["columns"]} == {"A1", "B1", "B2", "C2"}
    assert {(c["evidence"]["classified_by"], c["confidence"])
            for c in modele["columns"]} == {("geometrie", 0.85)}
    assert modele["report"]["columns"]["structural_zone"] == "axes_etiquetes"
    assert modele["report"]["column_candidates_rejected"] == {"section_irreguliere": 2}


# ===================================== les poteaux nommés restent (K1 de G4)
FABRIQUES = {
    "charpente_mm": F.dxf_charpente_mm,
    "grande_grille": lambda: F.dxf_grande_grille(6),
    "pieux_nommes": lambda: F.dxf_pieux_signatures(noms=True),
    "poteaux_nommes": lambda: dxf_poteaux_signatures(noms=True),
}


@pytest.mark.parametrize("nom", sorted(FABRIQUES))
def test_la_signature_ne_retire_ni_ne_deplace_aucun_poteau_nomme(monkeypatch, nom):
    """Sans la signature (aucune section reconnue) puis avec : chaque poteau
    nommé garde son identifiant, son centre, sa section, son nœud, son repère.
    Seules la règle, la confiance et les critères cités changent."""
    octets = FABRIQUES[nom]()
    avec = {c["id"]: c for c in _modele(octets)["columns"]}
    monkeypatch.setattr(module_poteaux, "_section", lambda *_a, **_k: False)
    sans = [c for c in _modele(octets)["columns"]
            if c["evidence"]["classified_by"] in ("calque", "bloc")]
    assert sans
    for s in sans:
        a = avec[s["id"]]
        for cle in ("shape", "centre", "width", "depth", "diameter", "grid_node", "mark"):
            assert a[cle] == s[cle], (s["id"], cle)
        if a["evidence"]["classified_by"] == "geometrie":
            assert a["confidence"] == 0.9
            assert a["evidence"]["matched_name"] == s["evidence"]["matched_name"]
        else:
            assert (a["confidence"], a["evidence"]["classified_by"]) == (
                s["confidence"], s["evidence"]["classified_by"])
