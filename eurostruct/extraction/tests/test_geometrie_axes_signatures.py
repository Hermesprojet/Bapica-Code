"""Les axes par leur SIGNATURE, quel que soit leur nom (phase G2).

Voir ``docs/GEOMETRIE_D_ABORD_G2.md``. LA QUESTION : une grille dont aucun
calque, aucun bloc, aucun type de ligne ne porte un nom connu — renommée,
dans une autre langue, ou sans convention — est-elle lue ? Et un plan dont les
noms sont reconnus garde-t-il exactement ses axes ?
"""

from __future__ import annotations

import pytest

import fabrique_geometrie as F
from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import axes as module_axes
from eurostruct_extraction.geometrie.axes_geometriques import SignaturesAxes
from fabrique_geometrie import dxf_grille_signatures

LETTRES = ["1", "2", "3", "A", "B", "C", "D"]


def _modele(octets: bytes) -> dict:
    return extract_engineering_data(parse_document(octets)).structure


def _grille(modele: dict) -> list[tuple]:
    return [(a["id"], a["label"], a["line"]) for a in modele["grid"]]


# ======================================================== sans aucun nom
@pytest.mark.parametrize("forme", ["cercles", "hexagones", "blocs", "blocs_attribut_dehors"])
def test_une_grille_sans_aucun_nom_est_lue_par_ses_bulles(forme):
    modele = _modele(dxf_grille_signatures(forme=forme))
    axes = modele["grid"]
    assert sorted(a["label"] for a in axes) == sorted(LETTRES)
    assert {a["evidence"]["classified_by"] for a in axes} == {"geometrie"}
    assert all({"bulle", "famille"} <= set(a["evidence"]["signature"]) for a in axes)
    assert {a["confidence"] for a in axes} == {0.85}
    assert all("matched_name" not in a["evidence"] for a in axes)
    attendu = "bloc" if forme == "blocs_attribut_dehors" else "bulle"
    assert {a["label_source"]["via"] for a in axes} == {attendu}
    # LA GRILLE PORTE LE RESTE : les nœuds, et les poteaux pleins à ces nœuds.
    assert len(modele["grid_nodes"]) == 12 and modele["counts"]["columns"] == 12


@pytest.mark.parametrize("forme", ["cercles", "hexagones", "blocs"])
def test_les_noms_ne_changent_que_la_confiance_et_le_nom_cite(forme):
    """La même grille, ses calques, blocs et types de ligne renommés (motifs
    gardés) : mêmes axes, mêmes étiquettes, mêmes nœuds. Le nom qui concorde
    est cité et ajoute 0,05."""
    sans_noms = _modele(dxf_grille_signatures(forme=forme))
    nommee = _modele(dxf_grille_signatures(forme=forme, noms=True))
    assert _grille(sans_noms) == _grille(nommee)
    assert [n["id"] for n in sans_noms["grid_nodes"]] == [n["id"] for n in nommee["grid_nodes"]]
    assert {a["confidence"] for a in nommee["grid"]} == {0.9}
    assert {a["evidence"]["matched_name"] for a in nommee["grid"]} <= {"AXES", "GRID_BUBBLE"}
    assert {a["evidence"]["classified_by"] for a in nommee["grid"]} == {"geometrie"}


def test_sans_motif_la_signature_a_suffit():
    modele = _modele(dxf_grille_signatures(motif=False))
    assert sorted(a["label"] for a in modele["grid"]) == sorted(LETTRES)
    assert not any("motif_mixte" in a["evidence"]["signature"] for a in modele["grid"])


# ============================================================ signature B
def test_un_trait_point_parallele_a_une_famille_est_un_axe_sans_etiquette():
    modele = _modele(dxf_grille_signatures(intermediaire=True))
    (b,) = [a for a in modele["grid"] if a["label"] is None]
    assert b["line"][0][0] == pytest.approx(9000.0) and b["line"][1][0] == pytest.approx(9000.0)
    assert set(b["evidence"]["signature"]) == {"motif_mixte", "parallele_a_une_famille", "zone"}
    assert b["evidence"]["classified_by"] == "geometrie" and b["confidence"] == 0.6
    # Un axe sans étiquette n'est pas proposé : aucune « file » inventée.
    assert len(modele["grid"]) == 8


def test_sans_motif_le_trait_intermediaire_n_est_pas_un_axe():
    modele = _modele(dxf_grille_signatures(intermediaire=True, motif=False))
    assert len(modele["grid"]) == 7


# ================================================== ce qui n'est pas un axe
def test_un_repere_de_coupe_hors_de_la_zone_n_est_pas_un_axe():
    modele = _modele(dxf_grille_signatures(coupe=True))
    assert len(modele["grid"]) == 7
    assert all(a["line"][0][0] < 40000 for a in modele["grid"])


def test_reperes_de_locaux_et_pieux_numerotes_ne_sont_pas_des_bulles():
    """Treize pieux numérotés dans des cercles, l'un au bout de l'axe A : leur
    classe est écartée en entier (un seul au bout d'une droite) ; l'axe A garde
    son étiquette, sans doute ni contradiction."""
    for options in ({"reperes": True}, {"pieux_numerotes": True}):
        modele = _modele(dxf_grille_signatures(**options))
        assert sorted(a["label"] for a in modele["grid"]) == sorted(LETTRES), options
        assert modele["unresolved"] == [], options


def test_sans_bulle_ni_nom_aucun_axe_n_est_devine():
    modele = _modele(dxf_grille_signatures(bulles=False))
    assert modele["grid"] == [] and modele["grid_nodes"] == []
    # G4 : les douze poteaux pleins alignés font une grille IMPLICITE (C2) —
    # des poteaux, sans nœud, jamais des axes.
    assert modele["counts"]["columns"] == 12
    assert all(c["grid_node"] is None and "grille_implicite" in c["evidence"]["signature"]
               for c in modele["columns"])


# ================================================================ conflit
def test_une_signature_complete_sur_un_calque_d_un_autre_role_est_un_conflit_dit():
    modele = _modele(dxf_grille_signatures(conflit=True))
    (e,) = [a for a in modele["grid"] if a["label"] == "E"]
    assert e["evidence"]["classified_by"] == "geometrie" and e["confidence"] == 0.4
    assert e["evidence"]["layers"] == ["COTES"]
    (doute,) = modele["unresolved"]
    assert doute["element"] == "grid:E" and "cote (COTES)" in doute["reason"]


# ============================================================ étiquettes
def test_une_etiquette_en_minuscule_dans_une_bulle_est_lue_en_complement():
    modele = _modele(dxf_grille_signatures(minuscules=True))
    verticales = sorted((a for a in modele["grid"] if a["label"] in "abcd"),
                        key=lambda a: a["label"])
    assert [a["label"] for a in verticales] == ["a", "b", "c", "d"]
    assert {a["label_source"]["form"] for a in verticales} == {"texte_court"}


def test_une_minuscule_ne_contredit_jamais_une_etiquette_courante():
    modele = _modele(dxf_grille_signatures(bas_minuscules=True))
    assert sorted(a["label"] for a in modele["grid"]) == sorted(LETTRES)
    ecartees = [a["label_source"]["discarded"] for a in modele["grid"]
                if a["label"] in "ABCD"]
    assert len(ecartees) == 4
    assert all("texte court hors format" in d["reason"] for d in ecartees)
    assert modele["unresolved"] == []


# ============================================ les axes nommés restent (J1)
FABRIQUES = {
    "s101": F.dxf_coffrage_s101,
    "s101_tourne": lambda: F.dxf_coffrage_s101(rotation_deg=17.0),
    "charpente": F.dxf_charpente_mm,
    "sans_calques": F.dxf_sans_calques_m,
    "grande_grille": lambda: F.dxf_grande_grille(6),
    "fondations_pieux": F.dxf_fondations_pieux,
    "etiquettes": F.dxf_etiquettes_d_axes,
    "lettres_chiffres": F.dxf_bulles_lettres_chiffres,
    "axes_courts": F.dxf_axes_courts_a_bulle,
    "information_n1": F.dxf_information_n1,
}


@pytest.mark.parametrize("nom", sorted(FABRIQUES))
def test_la_geometrie_ne_retire_ni_ne_deplace_aucun_axe_nomme(monkeypatch, nom):
    """Sur chaque plan nommé, sans les signatures puis avec : les mêmes axes,
    mêmes étiquettes, mêmes droites, mêmes nœuds. Seules la règle, la
    confiance et les critères cités peuvent changer."""
    octets = FABRIQUES[nom]()
    avec = _modele(octets)
    monkeypatch.setattr(module_axes, "signatures_d_axes",
                        lambda prims, tolerances: SignaturesAxes([], [], None, tolerances))
    sans = _modele(octets)
    assert _grille(avec) == _grille(sans)
    assert avec["grid_nodes"] == sans["grid_nodes"]
    for a, s in zip(avec["grid"], sans["grid"], strict=True):
        if a["evidence"]["classified_by"] == "geometrie":
            assert a["confidence"] == min(round(s["confidence"] + 0.05, 2), 0.9) or (
                s["evidence"]["classified_by"] == "type_de_ligne")
        else:
            assert a["confidence"] == s["confidence"]


def test_une_feuille_pdf_garde_ses_styles_appris():
    from fabrique_pdf_vectoriel import pdf_plan_vectoriel

    analyse = parse_document(pdf_plan_vectoriel(), ocr=None)
    modele = extract_engineering_data(analyse).structure
    assert {a["evidence"]["classified_by"] for a in modele["grid"]} == {"style"}
    assert not any("signature" in a["evidence"] for a in modele["grid"])
