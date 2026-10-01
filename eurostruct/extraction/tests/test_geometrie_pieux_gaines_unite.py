"""Pieux, gaines, étiquettes d'axes, unité : les défauts qu'un plan de structure
réel a montrés, rejoués sur des plans fabriqués (``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md``).

Le plan réel n'est pas commité ; ce qu'il a donné, avant et après, est dit
dans la même documentation.
"""

from __future__ import annotations

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import axes as module_axes
from eurostruct_extraction.geometrie.classification import nomme_un_pieu, role_du_nom
from eurostruct_extraction.geometrie.ouvertures import nomme_une_ouverture
from fabrique_geometrie import (
    dxf_charpente_mm,
    dxf_coffrage_s101,
    dxf_etiquettes_d_axes,
    dxf_fondations_pieux,
    dxf_sans_calques_m,
)
from fabrique_pdf_vectoriel import pdf_plan_gaine


def _lire(octets: bytes):
    analyse = parse_document(octets, ocr=None)
    return analyse, extract_engineering_data(analyse)


@pytest.fixture(scope="module")
def fondations():
    return _lire(dxf_fondations_pieux())


@pytest.fixture(scope="module")
def etiquettes():
    return _lire(dxf_etiquettes_d_axes())


def _pieux_par_noeud(modele: dict) -> dict[str, dict]:
    return {p["grid_node"]: p for p in modele["piles"] if p["grid_node"]}


# ================================================================ vocabulaire
@pytest.mark.parametrize(("nom", "role"), [
    ("Pr_Pieux_coupe", "pieu"), ("Pr_Hach_Pieux_Coupe", "pieu"), ("XREF$0$Pr_Pieux_coupe", "pieu"),
    ("MICROPIEUX", "pieu"), ("Micro-pieu", "pieu"), ("S-PILE", "pieu"), ("PILING", "pieu"),
    ("PILOTES", "pieu"), ("Funderingspalen", "pieu"), ("HEIPAAL", "pieu"), ("Paalkop", "pieu"),
    ("Bohrpfähle", "pieu"), ("PFAHL", "pieu"), ("Pfahlkopf", "pieu"),
    # La tête d'un groupe n'est pas un pieu ; une semelle non plus.
    ("PILE_CAP", "fondation"), ("S-PILECAP", "fondation"), ("POEREN", "fondation"),
    ("Pfahlkopfplatte", "fondation"), ("SEMELLES", "fondation"), ("Massifs", "fondation"),
    ("FOOTINGS", "fondation"), ("Streifenfundament", "fondation"),
    # Un axe de pieux n'est pas un axe de grille ; un texte de pieux, un repère de pieu.
    ("Pr_Pieux_axe", "pieu"), ("PIEUX_TEXTE", "pieu"), ("NIVEAU_PIEUX", "pieu"),
    ("PIEUX_COTES", "cote"),
    # Ce qui n'en est pas.
    ("PILOTIS", None), ("BEPAALD", None), ("Spalenburg", None), ("COMPILE", None),
    ("PILIER", "poteau"), ("Pr_Voiles_fondation_Coupe", "voile"),
])
def test_le_vocabulaire_des_pieux_et_des_fondations(nom, role):
    assert role_du_nom(nom) == role


def test_un_texte_qui_nomme_un_pieu_ou_une_ouverture():
    assert all(nomme_un_pieu(t) for t in ("PIEU 12", "Pieux Ø63", "pile P3", "Paal 4"))
    assert not any(nomme_un_pieu(t) for t in ("P12", "C03-50", "VP2", "à 9h"))
    assert all(nomme_une_ouverture(t) for t in ("GAINE", "Asc.", "Trémie 60x60", "VIDE SUR",
                                                "Liftkoker", "Schacht", "Aufzüge", "sparing"))
    assert not any(nomme_une_ouverture(t) for t in ("B", "Ascension", "VIDEO", "LIFTING"))


# ===================================================================== pieux
def test_les_pieux_sont_comptes_et_ne_sont_jamais_des_poteaux(fondations):
    _, resultat = fondations
    modele = resultat.structure
    assert modele["counts"]["piles"] == 11
    assert modele["report"]["piles"]["by_diameter"] == {"63": 8, "60": 3}
    assert set(_pieux_par_noeud(modele)) == {"A3", "B3", "C3"}
    assert not {"A3", "B3", "C3"} & {c["grid_node"] for c in modele["columns"]}
    assert not any(c.categorie == "column_diameter" for c in resultat.candidats)


def test_tout_le_dessin_d_un_pieu_lui_revient(fondations):
    """Le calque, la copie cachée de la xréf, le remplissage, les lentilles des
    pieux sécants : un seul pieu par position, aucun fragment."""
    _, resultat = fondations
    modele = resultat.structure
    paroi = [p for p in modele["piles"] if p["diameter"] == 63]
    assert len(paroi) == 8
    for pieu in paroi:
        assert {"PIEUX_COUPE", "XREF$0$PIEUX_COUPE", "HACH_BETON_CACHE"} <= set(
            pieu["evidence"]["layers"])
    assert sum("HACH_PIEUX_COUPE" in p["evidence"]["layers"] for p in paroi) >= 7
    assert modele["report"]["piles"]["drawing_fragments"] == 0
    a3 = _pieux_par_noeud(modele)["A3"]
    assert set(a3["evidence"]["layers"]) == {"PIEUX_COUPE", "XREF$0$PIEUX_COUPE",
                                             "HACH_BETON_CACHE"}


def test_le_bloc_d_un_pieu_et_les_reperes_de_pieux(fondations):
    _, resultat = fondations
    modele = resultat.structure
    pieux = _pieux_par_noeud(modele)
    assert pieux["A3"]["mark"] == "P12"
    assert pieux["B3"]["mark"] == "PIEU 13"
    assert pieux["C3"]["evidence"]["classified_by"] == "bloc"
    assert pieux["C3"]["evidence"]["blocks"] == ["PIEU_D60"]
    # Un repère de pieu n'est le repère d'aucun poteau.
    assert {c["mark"] for c in modele["columns"]} == {"C1", None}
    assert all(lab["text"] not in ("P12", "PIEU 13") for lab in modele["labels"])


def test_rien_n_est_propose_pour_un_pieu(fondations):
    _, resultat = fondations
    for c in resultat.candidats:
        element = (c.position or {}).get("element", {})
        assert not str(element.get("id", "")).startswith("pile:")


# ================================================== gaines, trémies, socles
def test_seuls_les_poteaux_prefabriques_restent_des_poteaux(fondations):
    """Socles cachés, cage d'ascenseur et sa cabine, chevron, trémie barrée,
    gaine nommée, semelle, pieux : écartés, chacun avec sa raison."""
    _, resultat = fondations
    modele = resultat.structure
    assert {c["grid_node"] for c in modele["columns"]} == {"A1", "B1", "C1", "A2"}
    assert {(c["width"], c["depth"]) for c in modele["columns"]} == {(50, 50)}
    # Le contour d'un poteau hachuré reste sa preuve, avec la hachure.
    assert all({"LWPOLYLINE", "HATCH"} <= set(c["evidence"]["entity_types"])
               for c in modele["columns"])
    assert modele["report"]["column_candidates_rejected"] == {
        "contenant": 5, "dans_une_enceinte": 1, "dessin_de_pieu": 1, "fondation": 1,
        "non_compact": 1, "ouverture_barree": 1, "ouverture_nommee": 1, "pieu": 3}


def test_la_cage_d_ascenseur_d_une_feuille_pdf_n_est_pas_un_poteau():
    _, resultat = _lire(pdf_plan_gaine())
    modele = resultat.structure
    assert {c["grid_node"] for c in modele["columns"]} == {"A1", "A2", "B1", "C1", "C2"}
    assert modele["report"]["column_candidates_rejected"] == {
        "contenant": 1, "dans_une_enceinte": 1, "non_compact": 1}
    largeurs = {c.valeur for c in resultat.candidats if c.categorie == "column_width"}
    assert largeurs == {300}


@pytest.mark.parametrize("fabrique", [dxf_coffrage_s101, dxf_charpente_mm, dxf_sans_calques_m])
def test_les_regles_de_section_ne_retirent_aucun_poteau_des_plans_existants(fabrique):
    _, resultat = _lire(fabrique())
    assert resultat.structure["report"]["column_candidates_rejected"] == {}
    assert resultat.structure["counts"]["piles"] == 0


# ======================================================= étiquettes d'axes
def _axes(modele: dict) -> dict[str, dict]:
    return {a["label"]: a for a in modele["grid"] if a["label"]}


def test_une_bulle_l_emporte_sur_une_lettre_egaree_qui_est_citee(etiquettes):
    _, resultat = etiquettes
    source = _axes(resultat.structure)["3"]["label_source"]
    assert source["via"] == "bulle"
    assert (source["discarded"]["text"], source["discarded"]["via"]) == ("K", "texte")


def test_une_lettre_geante_n_est_pas_une_etiquette(etiquettes):
    """La lettre de 1 200 mm au bout de l'axe 2 n'est même pas candidate."""
    _, resultat = etiquettes
    source = _axes(resultat.structure)["2"]["label_source"]
    assert source == {"via": "bulle", "handle": source["handle"]}


def test_sans_le_filtre_de_hauteur_la_lettre_geante_est_ecartee_par_le_rang(monkeypatch):
    """Les deux règles tiennent chacune seule : sans le filtre de hauteur, la
    bulle l'emporte encore, et la lettre est citée comme écartée."""
    monkeypatch.setattr(module_axes, "_HAUTEUR_LIBRE", (0.0, float("inf")))
    _, resultat = _lire(dxf_etiquettes_d_axes())
    source = _axes(resultat.structure)["2"]["label_source"]
    assert source["discarded"]["text"] == "B"


def test_deux_bulles_qui_se_contredisent_laissent_l_axe_sans_etiquette(etiquettes):
    _, resultat = etiquettes
    modele = resultat.structure
    assert set(_axes(modele)) == {"1", "2", "3", "A", "B", "C"}
    assert sum(1 for a in modele["grid"] if a["label"] is None) == 1
    [doute] = [n["reason"] for n in modele["unresolved"] if n["element"].startswith("axe")]
    assert "« 4 » (bulle) et « 8 » (bulle), preuves de meme force" in doute


def test_un_pieu_numerote_n_est_pas_une_bulle(etiquettes):
    _, resultat = etiquettes
    modele = resultat.structure
    assert _axes(modele)["C"]["label_source"]["via"] == "bulle"
    [pieu] = modele["piles"]
    assert pieu["mark"] == "12"


# ===================================================================== unité
def test_l_unite_vient_de_la_presentation(fondations):
    _, resultat = fondations
    unites = resultat.structure["units"]
    assert (unites["drawing"], unites["source"]) == ("cm", "echelle_de_presentation")
    preuve = unites["evidence"]
    assert preuve["written"]["text"] == "1/100"
    assert preuve["viewport"]["drawing_units_per_paper_unit"] == 10.0
    assert (preuve["paper_unit"], preuve["mm_per_drawing_unit"], preuve["deviation"]) == (
        "mm", 10.0, 0.0)
    entraxes = {c.repere: (c.valeur, c.unite) for c in resultat.candidats
                if c.methode == "geometrie" and c.categorie == "grid_spacing"}
    assert entraxes["A-B"] == (600, "cm")
    [ab] = [c for c in resultat.candidats
            if c.categorie == "grid_spacing" and c.repere == "A-B"]
    assert ab.fondement["unit_declaration"]["source"] == "echelle_de_presentation"


@pytest.mark.parametrize(("options", "raison"), [
    ({"echelles": ("1/50",)}, "aucune paire echelle ecrite (1/50)"),
    ({"echelles": ("1/100", "1/10")}, "ambiguite"),
    ({"echelles": ()}, "aucune echelle ecrite"),
])
def test_une_presentation_qui_ne_suffit_pas_ne_donne_aucune_unite(options, raison):
    _, resultat = _lire(dxf_fondations_pieux(**options))
    modele = resultat.structure
    assert modele["units"]["drawing"] is None
    [doute] = [n["reason"] for n in modele["unresolved"] if n["element"] == "unite"]
    assert raison in doute


def test_sans_presentation_rien_n_est_deduit_ni_dit():
    _, resultat = _lire(dxf_fondations_pieux(presentation=False))
    modele = resultat.structure
    assert modele["units"]["drawing"] is None
    assert not [n for n in modele["unresolved"] if n["element"] == "unite"]


def test_une_unite_declaree_prime_sur_la_presentation():
    _, resultat = _lire(dxf_fondations_pieux(insunits=4))
    unites = resultat.structure["units"]
    assert (unites["drawing"], unites["source"]) == ("mm", "$INSUNITS")


def test_la_mention_et_la_presentation_qui_concordent_sont_citees_ensemble():
    _, resultat = _lire(dxf_fondations_pieux(mention="Cotes en cm"))
    unites = resultat.structure["units"]
    assert (unites["drawing"], unites["source"]) == ("cm", "echelle_de_presentation")
    assert unites["evidence"]["confirmed_by_mention"]["declaration"]["unit"] == "cm"


def test_la_mention_et_la_presentation_qui_se_contredisent_ne_donnent_aucune_unite():
    _, resultat = _lire(dxf_fondations_pieux(mention="Cotes en mm"))
    modele = resultat.structure
    assert modele["units"]["drawing"] is None
    [doute] = [n["reason"] for n in modele["unresolved"] if n["element"] == "unite"]
    assert "mm" in doute and "cm" in doute and "se contredisent" in doute
