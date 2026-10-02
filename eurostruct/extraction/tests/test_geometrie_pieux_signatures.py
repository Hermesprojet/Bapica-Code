"""Les pieux par leur SIGNATURE, quel que soit leur nom (phase G3).

Voir ``docs/GEOMETRIE_D_ABORD_G3.md``. LA QUESTION : un plan de fondations dont
aucun calque, aucun bloc ne porte un nom connu — renommé, dans une autre
langue, ou sans convention — donne-t-il ses pieux, et ses dessins de pieux
cessent-ils d'être des « poteaux » ? Et un plan dont les noms sont reconnus
garde-t-il exactement ses pieux ?
"""

from __future__ import annotations

import pytest

import fabrique_geometrie as F
from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import pieux as module_pieux
from fabrique_geometrie import dxf_pieux_signatures


def _modele(octets: bytes) -> dict:
    return extract_engineering_data(parse_document(octets)).structure


def _pieux(modele: dict) -> list[tuple]:
    return [(p["id"], p["centre"], p["diameter"], p["grid_node"], p["mark"])
            for p in modele["piles"]]


def _classes(modele: dict) -> dict:
    return {c["diameter"]: c["verdict"]
            for c in modele["report"]["piles"].get("diameter_classes", [])}


# ======================================================== sans aucun nom
def test_un_plan_de_pieux_sans_aucun_nom_donne_ses_pieux():
    modele = _modele(dxf_pieux_signatures())
    pieux = modele["piles"]
    assert len(pieux) == 30 and {p["diameter"] for p in pieux} == {60}
    assert {p["evidence"]["classified_by"] for p in pieux} == {"geometrie"}
    assert {p["confidence"] for p in pieux} == {0.85}
    assert all("classe_de_diametre" in p["evidence"]["signature"] for p in pieux)
    assert all("matched_name" not in p["evidence"] for p in pieux)
    assert _classes(modele) == {60: "pieux"}
    assert modele["report"]["piles"]["by_rule"] == {"geometrie": 30}
    # LA PAROI, dessinée deux fois (continu, tirets) et remplie : les
    # corroborations sont citées, un pieu par centre.
    paroi = [p for p in pieux if p["centre"][1] == -400]
    assert len(paroi) == 10
    assert all({"motif_tirets", "rempli"} <= set(p["evidence"]["signature"]) for p in paroi)


def test_aucun_poteau_n_est_tire_du_dessin_d_un_pieu():
    """Les quatre pieux seuls, centrés sur les nœuds de la file 1, étaient des
    poteaux ronds sans leur nom : ils sont écartés comme pieux."""
    modele = _modele(dxf_pieux_signatures())
    assert len(modele["columns"]) == 8
    assert {c["shape"] for c in modele["columns"]} == {"rectangle"}
    assert modele["report"]["column_candidates_rejected"] == {"pieu": 4}


def test_les_noms_ne_font_que_confirmer():
    """Le même plan, ses calques nommés : mêmes pieux (identifiants, centres,
    diamètres, nœuds), mêmes poteaux. Le nom concordant est cité et ajoute 0,05."""
    sans_noms = _modele(dxf_pieux_signatures())
    nomme = _modele(dxf_pieux_signatures(noms=True))
    assert _pieux(sans_noms) == _pieux(nomme)
    assert [c["id"] for c in sans_noms["columns"]] == [c["id"] for c in nomme["columns"]]
    assert {p["confidence"] for p in nomme["piles"]} == {0.9}
    assert {p["evidence"]["matched_name"] for p in nomme["piles"]} == {"PIEUX"}
    assert {p["evidence"]["classified_by"] for p in nomme["piles"]} == {"geometrie"}
    assert nomme["report"]["column_candidates_rejected"] == {"pieu": 4}


def test_sans_grille_l_unite_suffit_a_borner_le_diametre():
    modele = _modele(dxf_pieux_signatures(grille=False))
    assert len(modele["piles"]) == 30 and modele["columns"] == []


def test_sans_unite_la_grille_borne_le_diametre_sans_l_une_ni_l_autre_rien():
    assert len(_modele(dxf_pieux_signatures(unite=False))["piles"]) == 30
    modele = _modele(dxf_pieux_signatures(unite=False, grille=False))
    assert modele["piles"] == []
    assert _classes(modele) == {60: "diametre_non_verifiable"}


# ================================================ ce qui n'est pas un pieu
def test_une_classe_de_poteaux_ronds_pleins_seuls_aux_noeuds_reste_aux_poteaux():
    modele = _modele(dxf_pieux_signatures(poteaux_ronds=True))
    assert _classes(modele) == {50: "poteaux_ronds", 60: "pieux"}
    # Douze poteaux ronds, un par nœud : leur cercle et leur hachure (le poteau
    # se dit par sa hachure, la forme la plus sûre du groupe).
    assert len(modele["columns"]) == 12
    assert all(c["grid_node"] and "CIRCLE" in c["evidence"]["entity_types"]
               for c in modele["columns"])
    assert len(modele["piles"]) == 34 and {p["diameter"] for p in modele["piles"]} == {60}


@pytest.mark.parametrize("fabrique", [lambda: F.dxf_grille_signatures(bas_minuscules=True),
                                      F.dxf_axes_courts_a_bulle],
                         ids=["bulles_aux_deux_bouts", "bulles_d_axes_courts"])
def test_des_bulles_d_axes_ne_sont_pas_des_pieux(fabrique):
    """Onze bulles au bout d'axes longs (G2) ; quatorze de Ø 800 mm, dont celles
    d'axes nommés plus courts que 20 rayons : des bulles, pas des pieux."""
    modele = _modele(fabrique())
    assert _classes(modele) == {800: "bulles"}
    assert not any(p["evidence"]["classified_by"] == "geometrie" for p in modele["piles"])
    assert not any(u["element"].startswith("pile:") for u in modele["unresolved"])


def test_des_pieux_numerotes_restent_des_pieux_meme_au_pied_d_un_axe():
    """Un numéro dans chaque pieu, et un pieu numéroté au pied de l'axe A : la
    classe est décidée par la position, pas par l'étiquette."""
    modele = _modele(dxf_pieux_signatures(numerotes=True))
    assert _classes(modele) == {60: "pieux"} and len(modele["piles"]) == 31
    assert sorted(a["label"] for a in modele["grid"]) == sorted("ABCD123")
    assert not any(p["mark"] for p in modele["piles"])


def test_des_regards_trop_petits_ne_sont_pas_des_pieux():
    modele = _modele(dxf_pieux_signatures(regards=True))
    assert _classes(modele) == {15: "diametre_hors_bornes", 60: "pieux"}
    assert len(modele["piles"]) == 30


def test_six_pieux_ne_font_pas_une_classe_le_nom_les_complete():
    sans_noms = _modele(dxf_pieux_signatures(peu=True))
    assert sans_noms["piles"] == [] and _classes(sans_noms) == {}
    nomme = _modele(dxf_pieux_signatures(peu=True, noms=True))
    assert len(nomme["piles"]) == 6
    assert {(p["evidence"]["classified_by"], p["confidence"]) for p in nomme["piles"]} == {
        ("calque", 0.85)}
    assert not any("classe_de_diametre" in (p["evidence"].get("signature") or [])
                   for p in nomme["piles"])


# ================================================================ conflit
def test_une_classe_de_pieux_sur_un_calque_de_poteaux_est_un_conflit_dit():
    modele = _modele(dxf_pieux_signatures(calque_pieux="POTEAUX"))
    assert len(modele["piles"]) == 30 and {p["confidence"] for p in modele["piles"]} == {0.4}
    assert {p["evidence"]["classified_by"] for p in modele["piles"]} == {"geometrie"}
    # Un germe de pieu n'est jamais un poteau, même nommé poteau.
    assert len(modele["columns"]) == 8
    assert {c["shape"] for c in modele["columns"]} == {"rectangle"}
    doutes = [u for u in modele["unresolved"] if u["element"].startswith("pile:")]
    assert len(doutes) == 30 and all("poteau (POTEAUX)" in u["reason"] for u in doutes)


# ============================================ les pieux nommés restent (K1)
FABRIQUES = {
    "fondations": F.dxf_fondations_pieux,
    "fondations_sans_presentation": lambda: F.dxf_fondations_pieux(presentation=False),
    "pieux_nommes": lambda: dxf_pieux_signatures(noms=True),
    "pieux_nommes_peu": lambda: dxf_pieux_signatures(noms=True, peu=True),
    "pieux_nommes_ronds": lambda: dxf_pieux_signatures(noms=True, poteaux_ronds=True),
    "axes_courts": F.dxf_axes_courts_a_bulle,
}


@pytest.mark.parametrize("nom", sorted(FABRIQUES))
def test_la_signature_ne_retire_ni_ne_deplace_aucun_pieu_nomme(monkeypatch, nom):
    """Sur chaque plan dont les pieux sont nommés, sans la signature P puis
    avec : mêmes pieux, identifiants, centres, diamètres, nœuds, repères, mêmes
    poteaux. Seules la règle, la confiance et les critères cités changent."""
    octets = FABRIQUES[nom]()
    avec = _modele(octets)
    monkeypatch.setattr(module_pieux, "_signature_p",
                        lambda *a, **k: module_pieux._SignatureP({}, []))
    sans = _modele(octets)
    assert _pieux(avec) == _pieux(sans)
    assert [c["id"] for c in avec["columns"]] == [c["id"] for c in sans["columns"]]
    for a, s in zip(avec["piles"], sans["piles"], strict=True):
        if a["evidence"]["classified_by"] == "geometrie":
            assert a["confidence"] == 0.9
        else:
            assert a["confidence"] == s["confidence"]


def test_une_feuille_pdf_ne_passe_pas_par_la_signature(monkeypatch):
    from fabrique_pdf_vectoriel import pdf_plan_vectoriel

    def interdite(*_a: object, **_k: object) -> None:
        raise AssertionError("signature P evaluee sur une feuille PDF")

    monkeypatch.setattr(module_pieux, "_signature_p", interdite)
    modele = extract_engineering_data(parse_document(pdf_plan_vectoriel(), ocr=None)).structure
    assert "diameter_classes" not in modele["report"]["piles"]
