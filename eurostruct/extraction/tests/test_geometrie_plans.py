"""Des plans DXF fabriqués, lus par leur géométrie : le modèle structurel et ce
qu'il propose.

LA QUESTION DE LA PHASE 2 : un plan qui n'écrit NULLE PART « Portée P1 : 6 m »
donne-t-il quand même les portées, les sections de poteaux et les liaisons ?
Chaque test le vérifie sur un dessin dont on connaît la réponse, et vérifie
aussi qu'un dessin qui ne permet pas de conclure est refusé, avec sa raison.
"""

from __future__ import annotations

import json
import time

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import PLAFOND_GEOMETRIE, SCHEMA
from fabrique_geometrie import (
    dxf_charpente_mm,
    dxf_coffrage_s101,
    dxf_grande_grille,
    dxf_refus,
    dxf_sans_calques_m,
)


def _lire(octets: bytes):
    analyse = parse_document(octets)
    resultat = extract_engineering_data(analyse)
    return analyse, resultat


def _par_id(liste: list[dict], cle: str = "id") -> dict[str, dict]:
    return {x[cle]: x for x in liste}


def _geometrie(resultat, categorie: str) -> dict[str | None, list]:
    trouves: dict[str | None, list] = {}
    for c in resultat.candidats:
        if c.methode == "geometrie" and c.categorie == categorie:
            trouves.setdefault(c.repere, []).append(c)
    return trouves


# ============================================================ S-101 (cm)
@pytest.fixture(scope="module")
def s101():
    return _lire(dxf_coffrage_s101())


def test_le_plan_ne_dit_aucune_portee_et_la_geometrie_les_donne(s101):
    analyse, resultat = s101
    textes = [e.texte or "" for e in analyse.entites_dxf]
    assert textes and not any("portée" in t.lower() or "portee" in t.lower()
                              for t in textes)
    portees = _geometrie(resultat, "beam_span")
    assert {r: (c[0].valeur, c[0].unite) for r, c in portees.items()} == {
        "P1": (600, "cm"), "P2": (450, "cm"), "P3": (600, "cm"), "P4": (450, "cm"),
        "P5": (600, "cm")}
    nus = _geometrie(resultat, "beam_clear_span")
    assert {r: c[0].valeur for r, c in nus.items()} == {
        "P1": 570, "P2": 420, "P3": 570, "P4": 420, "P5": 570}
    # AUCUNE AUTRE METHODE N'A PROPOSE DE PORTEE: elles viennent du dessin seul.
    assert all(c.methode == "geometrie" for c in resultat.candidats
               if c.categorie in ("beam_span", "beam_clear_span"))


def test_une_portee_cite_ses_appuis_sa_regle_et_la_cote_qui_la_confirme(s101):
    _, resultat = s101
    [p1] = _geometrie(resultat, "beam_span")["P1"]
    assert p1.texte_brut.startswith("P1 — travee 1/2 : C1 · A1 -> C1 · B1, entre-axes 600 cm")
    assert p1.position["source"] == "geometry"
    assert p1.position["element"] == {"type": "span", "id": "span:1.1"}
    assert [a["grid_node"] for a in p1.fondement["supports"]] == ["A1", "B1"]
    assert p1.fondement["rule"] == "entre_axes_des_appuis"
    assert p1.fondement["support_widths"] == [30, 30]
    assert p1.fondement["unit_basis"] == "declaration"
    [cote] = p1.fondement["dimensions"]
    assert (cote["measures"], cote["displayed"], cote["measure_agrees"],
            cote["forced_mismatch"]) == ("axis_length", "600", True, False)
    assert p1.confiance <= PLAFOND_GEOMETRIE


def test_les_poteaux_sont_aux_noeuds_avec_leur_section(s101):
    _, resultat = s101
    modele = resultat.structure
    poteaux = _par_id(modele["columns"])
    assert sorted(poteaux) == ["column:A1", "column:A2", "column:B1", "column:B2",
                               "column:C1", "column:C2"]
    assert {(p["width"], p["depth"], p["mark"]) for p in poteaux.values()} == {(30, 30, "C1")}
    [largeur] = _geometrie(resultat, "column_width")["C1"]
    assert (largeur.valeur, largeur.unite) == (30, "cm")
    # LE TEXTE « C1 30x30 » CORROBORE la mesure: il est cite, pas propose a part.
    assert [x["method"] for x in largeur.fondement["corroborated_by"]] == ["dxf"]


def test_le_graphe_relie_chaque_travee_a_ses_deux_poteaux(s101):
    _, resultat = s101
    graphe = resultat.structure["graph"]
    aretes = {(a["mark"], a["from"], a["to"]) for a in graphe["edges"]}
    assert aretes == {("P1", "column:A1", "column:B1"), ("P2", "column:B1", "column:C1"),
                      ("P3", "column:A2", "column:B2"), ("P4", "column:B2", "column:C2"),
                      ("P5", "column:B1", "column:B2")}
    assert {n["id"] for n in graphe["nodes"]} == {p["id"] for p in resultat.structure["columns"]}


def test_la_grille_ses_entraxes_et_la_chaine_de_cotes(s101):
    _, resultat = s101
    modele = resultat.structure
    assert [a["label"] for a in modele["grid"]] == ["1", "2", "A", "B", "C"]
    assert {a["label_source"]["via"] for a in modele["grid"]} == {"bulle"}
    entraxes = {r: c[0].valeur for r, c in _geometrie(resultat, "grid_spacing").items()}
    assert entraxes == {"1-2": 600, "A-B": 600, "B-C": 450}
    [chaine] = modele["report"]["dimension_chains"]
    assert chaine["sum"] == 1050 and chaine["total"]["agrees"] is True


def test_les_dalles_sont_les_cellules_portees_de_la_grille(s101):
    _, resultat = s101
    dalles = _par_id(resultat.structure["slabs"])
    assert sorted(dalles) == ["slab:A-B/1-2", "slab:B-C/1-2"]
    ab = dalles["slab:A-B/1-2"]
    assert (ab["lx"], ab["ly"], ab["cross_marker"]) == (600, 600, True)
    assert ab["label"] == "Dalle pleine ép. 20"
    assert {e["side"]: e["supported_by"] for e in ab["edges"]} == {
        "1": "P1", "2": "P3", "B": "P5", "A": None}
    assert dalles["slab:B-C/1-2"]["lx"] == 450


def test_la_coupe_au_1_20_ne_fait_ni_poteau_ni_poutre(s101):
    # LE RECTANGLE DE LA COUPE A-A et ses cotes a DIMLFAC 0,4 restent hors du
    # modele; les cotes affichent 30 et 60, en cm par la mention ecrite.
    _, resultat = s101
    modele = resultat.structure
    assert modele["counts"]["columns"] == 6 and modele["counts"]["beams"] == 3
    coupe = [c for c in modele["dimensions"] if c["dimlfac"] != 1.0]
    assert sorted(c["displayed"] for c in coupe) == ["30", "60"]
    assert all(c["measures"] is None for c in coupe)
    cotes = sorted((c.valeur, c.unite, c.fondement["unit_declaration"]["source"])
                   for c in resultat.candidats if c.categorie == "dimension")
    assert cotes == [(30, "cm", "mention_ecrite"), (60, "cm", "mention_ecrite")]


def test_un_niveau_ecrit_trois_fois_est_un_niveau(s101):
    _, resultat = s101
    [niveau] = resultat.structure["levels"]
    assert niveau["value"] == 3.2 and len(niveau["mentions"]) == 3


def test_le_modele_est_un_json_stable_et_ses_comptes_le_resument(s101):
    _, resultat = s101
    modele = resultat.structure
    assert modele["schema"] == SCHEMA == "eurostruct.structure/1"
    for cle in ("columns", "beams", "slabs", "spans", "grid", "walls", "openings",
                "dimensions", "levels", "labels", "graph", "unresolved"):
        assert cle in modele
    assert modele["counts"] == {
        "grid_axes": 5, "grid_nodes": 6, "columns": 6, "walls": 0, "beams": 3,
        "spans": 5, "cantilevers": 0, "slabs": 2, "openings": 0, "dimensions": 6,
        "levels": 1, "unresolved": 0}
    assert modele["unresolved"] == []
    json.dumps(modele)
    # DETERMINISTE: les memes octets, le meme modele.
    assert extract_engineering_data(parse_document(dxf_coffrage_s101())).structure == modele


def test_le_compte_rendu_dit_ce_que_la_geometrie_a_lu(s101):
    analyse, resultat = s101
    assert "geometrie: 38 trait(s)" in analyse.detail
    assert resultat.compte_rendu["geometry"]["counts"]["spans"] == 5
    assert resultat.compte_rendu["found_by_extractor"]["geometrie"] == 26


# -------------------------------------------------------- variantes S-101
def test_le_meme_plan_tourne_de_30_degres_donne_les_memes_portees():
    _, resultat = _lire(dxf_coffrage_s101(rotation_deg=30.0))
    portees = {r: c[0].valeur for r, c in _geometrie(resultat, "beam_span").items()}
    assert portees == {"P1": 600, "P2": 450, "P3": 600, "P4": 450, "P5": 600}
    poteaux = resultat.structure["columns"]
    assert {(p["width"], p["depth"]) for p in poteaux} == {(30, 30)}
    assert len(resultat.structure["slabs"]) == 2


def test_sans_insunits_la_mention_ecrite_et_les_cotes_donnent_l_unite():
    _, resultat = _lire(dxf_coffrage_s101(insunits=0))
    unites = resultat.structure["units"]
    assert (unites["drawing"], unites["basis"], unites["source"]) == (
        "cm", "declaration", "declaration_et_cotes")
    assert "en cm" in unites["evidence"]["declaration"]["raw_text"]
    assert len(unites["evidence"]["dimensions"]) >= 2
    [p1] = _geometrie(resultat, "beam_span")["P1"]
    assert (p1.valeur, p1.unite) == (600, "cm")


def test_sans_insunits_ni_mention_les_longueurs_restent_sans_unite():
    _, resultat = _lire(dxf_coffrage_s101(insunits=0, declaration=False))
    assert resultat.structure["units"]["drawing"] is None
    [p1] = _geometrie(resultat, "beam_span")["P1"]
    assert (p1.valeur, p1.unite) == (600, None)
    assert "(unite non declaree)" in p1.texte_brut
    assert p1.confiance == pytest.approx(0.45)
    assert p1.fondement["unit_basis"] == "absente"


def test_une_portee_ecrite_egale_corrobore_la_geometrie():
    _, resultat = _lire(dxf_coffrage_s101(note_portee="Portée P1 : 6,00 m"))
    [p1] = _geometrie(resultat, "beam_span")["P1"]
    assert (p1.valeur, p1.unite) == (600, "cm")
    assert [(x["method"], x["value"], x["unit"]) for x in p1.fondement["corroborated_by"]] \
        == [("dxf", 6.0, "m")]
    assert p1.confiance == pytest.approx(0.75)
    assert not [c for c in resultat.candidats
                if c.categorie == "beam_span" and c.methode != "geometrie"]


def test_une_portee_ecrite_differente_est_confrontee_sans_etre_tranchee():
    _, resultat = _lire(dxf_coffrage_s101(note_portee="Portée P1 : 6,50 m"))
    portees = [c for c in resultat.candidats
               if c.categorie == "beam_span" and c.repere == "P1"]
    assert {(c.methode, c.valeur, c.unite) for c in portees} == {
        ("geometrie", 600, "cm"), ("dxf", 6.5, "m")}
    for c in portees:
        [autre] = c.fondement["conflicts_with"]
        assert autre["method"] != c.methode


# ======================================================= charpente (mm)
@pytest.fixture(scope="module")
def charpente():
    return _lire(dxf_charpente_mm())


def test_les_poteaux_en_blocs_et_le_bloc_tourne(charpente):
    _, resultat = charpente
    poteaux = _par_id(resultat.structure["columns"])
    assert len(poteaux) == 8 and "column:B3" not in poteaux
    assert (poteaux["column:C3"]["width"], poteaux["column:C3"]["depth"]) == (500, 300)
    assert (poteaux["column:A1"]["width"], poteaux["column:A1"]["depth"]) == (400, 400)
    preuve = poteaux["column:A1"]["evidence"]
    assert preuve["classified_by"] == "bloc" and preuve["blocks"] == ["COL-400x400"]
    assert preuve["inserts"]
    assert {r for r in _geometrie(resultat, "column_width")} == {"C1", None}


def test_une_poutre_interrompue_au_poteau_est_une_poutre_continue(charpente):
    _, resultat = charpente
    poutres = _par_id(resultat.structure["beams"])
    file1 = poutres["beam:1"]
    assert file1["drawn_as"] == "paire_de_traits" and file1["width"] == 300
    assert file1["merged_through"] == ["column:B1"]
    assert file1["supports"] == ["column:A1", "column:B1", "column:C1"]
    assert file1["marks"] == ["B1", "B2"]
    travees = _par_id(resultat.structure["spans"])
    assert (travees["span:1.1"]["axis_length"], travees["span:1.1"]["clear_length"]) == (
        6000, 5600)


def test_une_cote_forcee_qui_contredit_le_dessin_plafonne_la_confiance(charpente):
    _, resultat = charpente
    [b2] = _geometrie(resultat, "beam_span")["B2"]
    assert (b2.valeur, b2.unite) == (5800, "mm")
    assert b2.confiance == pytest.approx(0.4)
    [cote] = b2.fondement["dimensions"]
    assert (cote["displayed"], cote["measure_agrees"], cote["forced_mismatch"]) == (
        "6000", True, True)
    [entraxe] = _geometrie(resultat, "grid_spacing")["B-C"]
    assert (entraxe.valeur, entraxe.confiance) == (5800, pytest.approx(0.4))


def test_une_cote_forcee_egale_a_la_mesure_n_est_pas_une_contradiction():
    _, resultat = _lire(dxf_charpente_mm(cote_forcee="5800"))
    [b2] = _geometrie(resultat, "beam_span")["B2"]
    assert b2.confiance == pytest.approx(0.85)
    assert b2.fondement["dimensions"][0]["forced_mismatch"] is False


def test_une_console_au_dela_du_dernier_poteau(charpente):
    _, resultat = charpente
    console = _par_id(resultat.structure["spans"])["cantilever:2.fin"]
    assert console["kind"] == "cantilever"
    assert (console["axis_length"], console["clear_length"]) == (1700, 1500)
    assert console["from"]["support"] == "column:C2" and console["to"] is None
    [proposee] = _geometrie(resultat, "cantilever_length")["B3"]
    assert (proposee.valeur, proposee.unite) == (1500, "mm")


def test_une_poutre_qui_arrive_sur_un_voile_y_prend_appui(charpente):
    _, resultat = charpente
    [voile] = resultat.structure["walls"]
    assert (voile["thickness"], voile["length"]) == (200, 2000)
    b4 = _par_id(resultat.structure["spans"])["span:3.1"]
    assert (b4["from"]["support"], b4["to"]["support"]) == ("column:A3", voile["id"])
    assert (b4["axis_length"], b4["clear_length"]) == (6000, 5700)


def test_une_solive_portee_par_deux_poutres(charpente):
    _, resultat = charpente
    modele = resultat.structure
    sb1 = _par_id(modele["beams"])["beam:4"]
    assert sb1["marks"] == ["SB1"] and sb1["width"] == 250
    assert sb1["supported_by_beams"] == ["beam:1", "beam:2"]
    aretes = {(a["type"], a["from"], a["to"]) for a in modele["graph"]["edges"]}
    assert {("beam_on_beam", "beam:4", "beam:1"),
            ("beam_on_beam", "beam:4", "beam:2")} <= aretes
    [portee] = _geometrie(resultat, "beam_span")["SB1"]
    assert (portee.valeur, portee.unite) == (5000, "mm")
    # L'APPUI EST NOMME PAR LA TRAVEE PORTEUSE sous le point d'appui.
    assert "B1 -> B3" in portee.texte_brut
    [nu] = _geometrie(resultat, "beam_clear_span")["SB1"]
    assert nu.valeur == 4700
    # Le panneau A-B/1-2 est traverse par la solive: il le dit, sans se subdiviser.
    dalles = _par_id(modele["slabs"])
    assert dalles["slab:A-B/1-2"]["crossed_by"] == ["SB1"]


def test_une_largeur_ecrite_sans_unite_ne_contredit_pas_une_largeur_mesuree(charpente):
    _, resultat = charpente
    assert not [c for c in resultat.candidats if c.fondement.get("conflicts_with")]


# ===================================================== sans calques (m)
def test_sans_calques_la_forme_et_le_type_de_ligne_suffisent():
    _, resultat = _lire(dxf_sans_calques_m())
    modele = resultat.structure
    assert {a["evidence"]["classified_by"] for a in modele["grid"]} == {"type_de_ligne"}
    # AUCUNE ETIQUETTE N'EST INVENTEE: les axes sont nommes famille.rang.
    assert all(a["label"] is None for a in modele["grid"])
    assert [a["name"] for a in modele["grid"]] == ["0.1", "0.2", "1.1", "1.2", "1.3"]
    poteaux = modele["columns"]
    assert len(poteaux) == 6
    assert {(p["width"], p["depth"], p["filled"]) for p in poteaux} == {(0.3, 0.3, True)}
    assert {p["evidence"]["classified_by"] for p in poteaux} == {"forme"}
    portees = [c for c in resultat.candidats if c.categorie == "beam_span"]
    assert len(portees) == 4
    assert {(c.valeur, c.unite) for c in portees} == {(6, "m")}
    assert {c.repere for c in portees} == {"beam:1/1", "beam:1/2", "beam:2/1", "beam:2/2"}
    assert {c.valeur for c in resultat.candidats if c.categorie == "beam_clear_span"} == {5.7}


# =============================================================== refus
def test_ce_qui_ne_permet_pas_de_conclure_est_refuse_avec_sa_raison():
    _, resultat = _lire(dxf_refus())
    modele = resultat.structure
    raisons = {n["element"]: n["reason"] for n in modele["unresolved"]}
    assert "xref:XREF_ARCHI" in raisons
    assert "reference externe" in raisons["xref:XREF_ARCHI"]
    assert "poutre courbe" in raisons["arcs"]
    assert "aucun appui" in raisons["beam:1"]
    assert modele["spans"] == []
    # RIEN N'EST PROPOSE d'un element non resolu, pas meme sa largeur.
    assert resultat.candidats == ()


# ======================================================== grande grille
def test_une_grille_de_20_x_20_se_lit_en_temps_borne():
    octets = dxf_grande_grille(20)
    debut = time.perf_counter()
    analyse, resultat = _lire(octets)
    duree = time.perf_counter() - debut
    comptes = resultat.structure["counts"]
    assert (comptes["columns"], comptes["spans"], comptes["slabs"]) == (400, 760, 361)
    assert comptes["unresolved"] == 0
    # LARGE: une machine d'integration lente ne doit pas faire mentir le test,
    # un algorithme quadratique (> 20 s mesures avant correction), si.
    assert duree < 15.0, duree
    # La borne de propositions s'applique; le modele, lui, est complet.
    assert resultat.compte_rendu["not_recorded_beyond_limit"] > 0
    assert analyse.statut == "analyse"
