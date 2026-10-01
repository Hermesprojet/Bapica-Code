"""La lecture des plans, côté service — sans base.

Ce qui se juge ici sans PostgreSQL : le report d'une valeur DÉCIDÉE dans
l'unité d'un champ, le préremplissage, le contrôle de provenance d'un calcul,
et les refus d'une route avant toute base. Le parcours complet — dépôt réel,
analyse, revue, décision, report, calcul — est dans
``test_documents_postgres.py``, lancé par ``db/test/documents_extractions.sh``.
"""
from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import pytest
from eurostruct_engine.schemas.ec2_verification import (
    PROVENANCE_CHEMINS,
    Ec2BeamVerificationRequest,
)
from pydantic import ValidationError

from eurostruct_api import documents as service

# LES PLANS FABRIQUES DU MODULE D'EXTRACTION, les memes que ses tests lisent.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "extraction" / "tests"))
from fabrique_geometrie import dxf_coffrage_s101, dxf_fondations_pieux
from fabrique_pdf_vectoriel import pdf_plan_vectoriel

PROJET = "aaaaaaaa-0000-0000-0000-00000000000a"


def _ligne(kind: str, value, unit, *, status: str = "confirmed",
           label: str | None = None, ident: str = "e1",
           proposee=None, methode: str = "texte_natif") -> dict:
    """Une extraction telle que ``PostgresAtelier.extractions`` la rend."""
    return {
        "extraction_id": ident, "document_id": "d1",
        "document_filename": "FICTIF-plan.pdf", "document_sha256": "a" * 64,
        "kind": kind,
        "proposed_value": proposee or {"value": value, "unit": unit},
        "final_value": ({"value": value, "unit": unit}
                        if status in ("confirmed", "corrected") else None),
        "status": status, "page": 2, "bbox": [10.0, 20.0, 60.0, 30.0],
        "position": None, "confidence": 0.6, "method": methode,
        "model_name": "eurostruct-extraction/0.1.0",
        "raw_text": "Poutre P1 30x60", "element_label": label, "basis": None,
        "confirmed_by": "11111111-1111-1111-1111-111111111111",
        "confirmed_by_name": "FICTIF Ing. A",
        "confirmed_at": "2026-10-01 10:00:00+00:00",
        "decision_note": None, "created_at": "2026-10-01 09:00:00+00:00",
    }


def _corps(**remplace) -> dict:
    base = {
        "element": "P1", "strict_ndp": False,
        "geometry": {"b": {"value": 300, "unit": "mm"},
                     "h": {"value": 600, "unit": "mm"},
                     "d": {"value": 550, "unit": "mm"},
                     "l_eff": {"value": 6000, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"}, "V_Ed": {"value": 300, "unit": "kN"},
        "M_char": {"value": 180, "unit": "kN*m"},
        "M_qp": {"value": 120, "unit": "kN*m"},
        "phi_creep": 2.0, "exposure_class": "XC3",
        "structural_system": "simply_supported",
        "supports_brittle_partitions": False,
        "bars": {"count": 4, "diameter": {"value": 20, "unit": "mm"}},
        "links": {"legs": 2, "diameter": {"value": 10, "unit": "mm"},
                  "spacing": {"value": 150, "unit": "mm"}},
        "cot_theta": 1.5, "cover": {"value": 40, "unit": "mm"},
        "anchorage_available": {"value": 800, "unit": "mm"},
    }
    base.update(remplace)
    return base


def _provenance(ident: str = "e1", qui: str = "FICTIF n'importe qui") -> dict:
    return {"kind": "document_extraction", "detail": "ce que le client raconte",
            "extraction_id": ident, "confirmed_by": qui}


# ======================================================== le report exact
def test_les_champs_reportables_sont_exactement_les_chemins_du_contrat():
    assert tuple(service.CHAMPS_REPORTABLES) == PROVENANCE_CHEMINS


def test_aucune_charge_ni_aucune_grandeur_derivee_ne_se_reporte():
    categories = {c for champ in service.CHAMPS_REPORTABLES.values()
                  for c in champ.categories}
    assert "load_value" not in categories
    assert not {"geometry.d", "M_Ed", "V_Ed", "M_char", "M_qp"} & set(
        service.CHAMPS_REPORTABLES)


@pytest.mark.parametrize(("valeur", "unite", "attendue"), [
    (30, "cm", 300), (0.3, "m", 300), (6.05, "m", 6050), (12.5, "cm", 125),
    (1234.5, "mm", 1234.5), (6, "m", 6000),
])
def test_une_longueur_decidee_se_reporte_par_un_facteur_exact(valeur, unite, attendue):
    champ = service.CHAMPS_REPORTABLES["geometry.b"]
    assert service.valeur_du_champ(champ, {"value": valeur, "unit": unite}) == (
        attendue, "mm")


@pytest.mark.parametrize(("retenue", "motif"), [
    ({"value": 30, "unit": None}, "aucune unite"),
    ({"value": 12, "unit": "in"}, "pas une longueur metrique"),
    ({"value": 0, "unit": "mm"}, "nulle ou negative"),
    ({"value": "trente", "unit": "cm"}, "pas un nombre"),
    (None, "aucune valeur"),
])
def test_ce_qui_ne_se_reporte_pas_exactement_ne_se_reporte_pas(retenue, motif):
    champ = service.CHAMPS_REPORTABLES["geometry.b"]
    with pytest.raises(service.NonReportableErreur, match=motif):
        service.valeur_du_champ(champ, retenue)


def test_un_nombre_de_barres_est_un_entier_sans_unite():
    champ = service.CHAMPS_REPORTABLES["bars.count"]
    assert service.valeur_du_champ(champ, {"value": 4, "unit": None}) == (4, None)
    for retenue in ({"value": 4.5, "unit": None}, {"value": 4, "unit": "mm"},
                    {"value": 0, "unit": None}):
        with pytest.raises(service.NonReportableErreur):
            service.valeur_du_champ(champ, retenue)


@pytest.mark.parametrize(("chemin", "valeur", "admise"), [
    ("materials.concrete_grade", "C30/37", True),
    ("materials.concrete_grade", "C100/115", False),
    ("materials.steel_grade", "B500B", True),
    ("materials.steel_grade", "S355", False),
    ("materials.steel_grade", "BE500S", False),
    ("exposure_class", "XC3", True),
    ("exposure_class", "XZ9", False),
])
def test_une_designation_ne_se_reporte_que_si_le_moteur_la_verifie(chemin, valeur, admise):
    champ = service.CHAMPS_REPORTABLES[chemin]
    if admise:
        assert service.valeur_du_champ(champ, {"value": valeur, "unit": None}) == (
            valeur, None)
    else:
        with pytest.raises(service.NonReportableErreur, match="ne sait verifier|pas une valeur"):
            service.valeur_du_champ(champ, {"value": valeur, "unit": None})


# =========================================================== préremplissage
def test_le_preremplissage_ne_prend_que_les_valeurs_decidees():
    lignes = [_ligne("beam_width", 30, "cm", status="proposed", ident="p"),
              _ligne("beam_width", 35, "cm", status="rejected", ident="r"),
              _ligne("beam_depth", 65, "cm", status="corrected", ident="c",
                     proposee={"value": 60, "unit": "cm"})]
    rempli = service.preremplissage(PROJET, lignes, None)
    assert [(c.path, c.value, c.unit, c.extraction_id) for c in rempli.fields] == [
        ("geometry.h", 650, "mm", "c")]
    assert rempli.notice == service.AVIS_PROPOSITIONS


def test_la_provenance_rendue_est_celle_de_la_decision_enregistree():
    (champ,) = service.preremplissage(PROJET, [_ligne("beam_width", 30, "cm")], None).fields
    provenance = champ.provenance
    assert provenance.kind.value == "document_extraction"
    assert provenance.extraction_id == "e1"
    assert provenance.confirmed_by == "FICTIF Ing. A"
    assert provenance.page == 2 and provenance.document_id == "d1"
    assert "Poutre P1 30x60" in provenance.detail and "FICTIF-plan.pdf" in provenance.detail
    assert (champ.source_value.value, champ.source_value.unit) == (30, "cm")


def test_une_valeur_d_un_autre_repere_n_est_pas_proposee():
    lignes = [_ligne("beam_width", 30, "cm", label="P1", ident="a"),
              _ligne("beam_width", 25, "cm", label="P2", ident="b")]
    rempli = service.preremplissage(PROJET, lignes, "p 1")
    assert [(c.value, c.extraction_id) for c in rempli.fields] == [(300, "a")]
    assert not rempli.conflicts


def test_deux_valeurs_differentes_font_un_conflit_pas_un_choix():
    lignes = [_ligne("beam_width", 30, "cm", label="P1", ident="a"),
              _ligne("beam_width", 25, "cm", label="P2", ident="b")]
    rempli = service.preremplissage(PROJET, lignes, None)
    assert not rempli.fields
    (conflit,) = rempli.conflicts
    assert conflit.path == "geometry.b"
    assert {c.extraction_id for c in conflit.candidates} == {"a", "b"}


def test_deux_ecritures_de_la_meme_grandeur_ne_sont_pas_un_conflit():
    lignes = [_ligne("beam_width", 30, "cm", ident="a"),
              _ligne("beam_width", 300, "mm", ident="b")]
    rempli = service.preremplissage(PROJET, lignes, None)
    assert [(c.value, c.extraction_id) for c in rempli.fields] == [(300, "a")]


def test_une_valeur_decidee_qui_ne_se_reporte_pas_est_nommee_avec_sa_raison():
    rempli = service.preremplissage(PROJET, [_ligne("beam_width", 30, None)], None)
    (non,) = rempli.not_reportable
    assert non.kind == "beam_width" and "aucune unite" in non.reason


def test_une_portee_porte_son_avertissement():
    (champ,) = service.preremplissage(PROJET, [_ligne("beam_span", 6, "m")], None).fields
    assert champ.path == "geometry.l_eff" and champ.value == 6000
    assert "5.3.2.2" in champ.warning


# ==================================================== contrôle de provenance
def test_le_contrat_refuse_une_provenance_sans_decision():
    for provenance in ({"geometry.b": {"kind": "document_extraction", "detail": "x",
                                       "confirmed_by": "X"}},
                       {"geometry.b": {"kind": "document_extraction", "detail": "x",
                                       "extraction_id": "e1"}},
                       {"M_Ed": _provenance()},
                       {"geometry.d": _provenance()},
                       {"geometry.b": {"kind": "user_input", "detail": "saisie"}}):
        with pytest.raises(ValidationError):
            Ec2BeamVerificationRequest.model_validate(_corps(provenance=provenance))


def test_une_provenance_confirmee_et_egale_est_reecrite_depuis_la_base():
    corps = Ec2BeamVerificationRequest.model_validate(
        _corps(provenance={"geometry.b": _provenance("e1")}))
    reecrites = service.verifier_provenance(
        corps, {"e1": _ligne("beam_width", 30, "cm", ident="e1")})
    origine = reecrites["geometry.b"]
    # CE QUE LE CLIENT AVAIT ECRIT A DISPARU: nom et detail viennent de la base.
    assert origine.confirmed_by == "FICTIF Ing. A"
    assert origine.detail != "ce que le client raconte"
    assert origine.extraction_id == "e1"


def test_une_valeur_modifiee_apres_report_est_refusee():
    corps = Ec2BeamVerificationRequest.model_validate(_corps(
        geometry={"b": {"value": 310, "unit": "mm"}, "h": {"value": 600, "unit": "mm"},
                  "d": {"value": 550, "unit": "mm"},
                  "l_eff": {"value": 6000, "unit": "mm"}},
        provenance={"geometry.b": _provenance("e1")}))
    with pytest.raises(service.ProvenanceRefusee) as refus:
        service.verifier_provenance(corps, {"e1": _ligne("beam_width", 30, "cm")})
    ((chemin, motif),) = refus.value.motifs
    assert chemin == "geometry.b" and "redevient une saisie" in motif


def test_aucune_tolerance_n_est_accordee_a_l_egalite():
    corps = Ec2BeamVerificationRequest.model_validate(_corps(
        geometry={"b": {"value": 300.0001, "unit": "mm"},
                  "h": {"value": 600, "unit": "mm"}, "d": {"value": 550, "unit": "mm"},
                  "l_eff": {"value": 6000, "unit": "mm"}},
        provenance={"geometry.b": _provenance("e1")}))
    with pytest.raises(service.ProvenanceRefusee):
        service.verifier_provenance(corps, {"e1": _ligne("beam_width", 30, "cm")})


@pytest.mark.parametrize(("ligne", "motif"), [
    (_ligne("beam_width", 30, "cm", status="proposed"), "« proposed »"),
    (_ligne("beam_width", 30, "cm", status="rejected"), "« rejected »"),
    (_ligne("beam_depth", 30, "cm"), "ne renseigne pas"),
    (None, "introuvable"),
])
def test_une_provenance_sans_decision_valable_est_refusee(ligne, motif):
    corps = Ec2BeamVerificationRequest.model_validate(
        _corps(provenance={"geometry.b": _provenance("e1")}))
    lues = {"e1": ligne} if ligne else {}
    with pytest.raises(service.ProvenanceRefusee) as refus:
        service.verifier_provenance(corps, lues)
    assert motif in refus.value.motifs[0][1]


def test_une_designation_reportee_doit_rester_la_meme():
    corps = Ec2BeamVerificationRequest.model_validate(_corps(
        materials={"concrete_grade": "C35/45", "steel_grade": "B500B"},
        provenance={"materials.concrete_grade": _provenance("e1")}))
    with pytest.raises(service.ProvenanceRefusee):
        service.verifier_provenance(
            corps, {"e1": _ligne("concrete_class", "C30/37", None)})


# ========================================================= routes sans base
def test_un_depot_sans_jeton_est_refuse_avant_toute_lecture(client):
    reponse = client.post(f"/v1/projects/{PROJET}/documents",
                          params={"kind": "other", "filename": "x.pdf"},
                          content=b"%PDF-1.4")
    assert reponse.status_code == 401


def test_un_depot_au_dela_de_la_borne_est_refuse_pendant_la_lecture(client, forger):
    from eurostruct_api.stockage import TAILLE_MAX

    def flux():
        bloc = b"\0" * (1024 * 1024)
        for _ in range(TAILLE_MAX // len(bloc) + 1):
            yield bloc

    reponse = client.post(f"/v1/projects/{PROJET}/documents",
                          params={"kind": "other", "filename": "x.pdf"},
                          content=flux(),
                          headers={"Authorization": f"Bearer {forger()}"})
    assert reponse.status_code == 413
    assert reponse.json()["detail"]["error"] == "piece_trop_grosse"


def test_sans_base_le_depot_est_un_service_non_pret(client, forger):
    reponse = client.post(f"/v1/projects/{PROJET}/documents",
                          params={"kind": "other", "filename": "x.pdf"},
                          content=b"%PDF-1.4 FICTIF",
                          headers={"Authorization": f"Bearer {forger()}"})
    assert reponse.status_code == 503


def test_les_routes_de_revue_existent_et_exigent_une_identite(client):
    for methode, chemin in (
            ("get", f"/v1/projects/{PROJET}/documents"),
            ("get", f"/v1/projects/{PROJET}/extractions"),
            ("get", f"/v1/projects/{PROJET}/extractions/prefill"),
            ("post", f"/v1/projects/{PROJET}/extractions/e1/decision")):
        reponse = getattr(client, methode)(chemin, **(
            {"json": {"decision": "confirm"}} if methode == "post" else {}))
        assert reponse.status_code == 401, (chemin, reponse.status_code)


def test_une_decision_ne_porte_ni_nom_ni_date():
    from eurostruct_engine.schemas.documents import DecisionExtraction

    for intrus in ({"confirmed_by_name": "X"}, {"confirmed_at": "2026-01-01"},
                   {"confirmed_by": "X"}):
        with pytest.raises(ValidationError):
            DecisionExtraction.model_validate({"decision": "confirm", **intrus})


# ================================================== la note dit l'origine
def test_la_note_cite_l_origine_dans_l_ordre_du_contrat_et_rien_sans_provenance():
    from eurostruct_api.note_verification import _origines

    calcul = {"request": {"provenance": {
        "materials.concrete_grade": {"detail": "« Béton C30/37 » — plan.pdf, page 1",
                                     "confirmed_by": "FICTIF Ing. A",
                                     "confirmed_at": "2026-10-01 10:00:00+00:00"},
        "geometry.b": {"detail": "« P1 30x60 » — plan.pdf, page 1",
                       "confirmed_by": "FICTIF Ing. A",
                       "confirmed_at": "2026-10-01 10:01:00+00:00"}}}}
    assert [ligne[0] for ligne in _origines(calcul)] == ["Largeur b", "Classe de béton"]
    assert _origines({"request": {}}) == [] and _origines({}) == []


def test_un_caractere_sans_glyphe_est_dit_et_non_remplace_en_silence():
    from eurostruct_api.note_verification import _citation_pdf

    assert _citation_pdf("Poteau ⌀40 — Ø40, φ") == "Poteau [U+2300]40 — Ø40, φ"


# =========================================== la geometrie et sa source
@cache
def _analyse_s101():
    return service.analyser(dxf_coffrage_s101())


def _document(rapport: dict | None, *, ident: str = "d1") -> dict:
    """Un document tel que ``PostgresAtelier.documents`` le rend."""
    return {
        "document_id": ident, "kind": "formwork_drawing",
        "filename": "FICTIF-S-101.dxf", "format": "dxf", "mime_type": "image/vnd.dxf",
        "size_bytes": 1000, "sha256": "b" * 64, "page_count": 1, "text_layer": None,
        "analysis_status": "analyse", "analysis_detail": "lu",
        "analysis_report": rapport, "extractor_version": "eurostruct-extraction/0.2.0",
        "analysed_at": "2026-10-01 09:00:00+00:00", "uploaded_by_me": True,
        "created_at": "2026-10-01 09:00:00+00:00", "proposed_count": 26,
        "confirmed_count": 0, "corrected_count": 0, "rejected_count": 0,
    }


@pytest.mark.parametrize(("methode", "source"), [
    ("texte_natif", "text"), ("ocr", "ocr"), ("dxf", "cad_text"),
    ("geometrie", "geometry"), ("vision", "vision"),
])
def test_chaque_valeur_dit_sa_source(methode, source):
    extraction = service.en_extraction(_ligne("beam_span", 600, "cm", methode=methode))
    assert extraction.source_type == source
    assert extraction.source_label


class _AtelierQuiRetient:
    def __init__(self):
        self.recu: dict = {}

    def enregistrer_analyse(self, jeton, **champs):
        self.recu = champs
        return len(champs["extractions"])


def test_le_modele_structurel_est_enregistre_avec_l_analyse():
    analyse, resultat = _analyse_s101()
    atelier = _AtelierQuiRetient()
    ouvert = type("Ouvert", (), {"atelier": atelier})()
    crees = service.create_extraction_records(ouvert, "jeton", "d1", analyse, resultat)
    assert crees == len(resultat.candidats) > 0
    rapport = atelier.recu["report"]
    assert rapport["structure"]["schema"] == "eurostruct.structure/1"
    assert rapport["structure"]["counts"]["spans"] == 5
    assert {x["method"] for x in atelier.recu["extractions"]} >= {"geometrie", "dxf"}


def test_la_liste_ne_transporte_pas_le_modele_mais_le_resume():
    _, resultat = _analyse_s101()
    document = service.en_document(_document({"insunits": 5,
                                              "structure": resultat.structure}))
    assert document.has_structure is True
    assert "structure" not in document.analysis_report
    assert document.analysis_report["insunits"] == 5
    resume = document.structure_summary
    assert (resume.schema_version, resume.drawing_units, resume.unit_basis) == (
        "eurostruct.structure/1", "cm", "declaration")
    assert resume.counts["columns"] == 6
    sans = service.en_document(_document({"insunits": 5}))
    assert sans.has_structure is False and sans.structure_summary is None


def test_le_modele_se_lit_type_tel_qu_il_a_ete_enregistre():
    _, resultat = _analyse_s101()
    lu = service.en_structure(PROJET, _document({"structure": resultat.structure}))
    assert lu is not None and lu.document_id == "d1"
    portees = {t.mark: (t.axis_length, t.clear_length) for t in lu.structure.spans}
    assert portees == {"P1": (600, 570), "P2": (450, 420), "P3": (600, 570),
                       "P4": (450, 420), "P5": (600, 570)}
    assert lu.structure.spans[0].from_.grid_node == "A1"
    # LE CONTRAT EST FERME ET SANS PERTE: relu par alias, c'est le meme JSON.
    assert lu.structure.model_dump(mode="json", by_alias=True,
                                   exclude_none=True)["counts"] == resultat.structure["counts"]
    assert "distance entre appuis" in lu.notice
    assert service.en_structure(PROJET, _document({"insunits": 5})) is None
    assert service.en_structure(PROJET, _document(None)) is None


@cache
def _analyse_feuille_pdf():
    return service.analyser(pdf_plan_vectoriel())


def test_le_modele_d_une_feuille_pdf_se_relit_par_le_contrat():
    """Une feuille PDF fabriquée: le style appris et la feuille (page, échelle)
    passent le contrat fermé du modèle sans perte."""
    _, resultat = _analyse_feuille_pdf()
    lu = service.en_structure(PROJET, _document({"structure": resultat.structure}))
    assert lu is not None
    unites = lu.structure.units
    assert (unites.drawing, unites.source) == ("mm", "echelle_ecrite_et_cotes")
    assert unites.sheet is not None and unites.sheet["page"] == 1
    assert {a.label for a in lu.structure.grid} == {"A", "B", "C", "1", "2"}
    assert {a.evidence.classified_by for a in lu.structure.grid} == {"style"}


def test_un_modele_avec_pieux_et_unite_de_presentation_se_relit_par_le_contrat():
    """Les pieux passent le contrat fermé du modèle ; un modèle enregistré avant
    eux (sans la clé) aussi."""
    _, resultat = service.analyser(dxf_fondations_pieux())
    lu = service.en_structure(PROJET, _document({"structure": resultat.structure}))
    assert lu is not None
    assert len(lu.structure.piles) == 11
    assert lu.structure.units.source == "echelle_de_presentation"
    assert {p.diameter for p in lu.structure.piles} == {60, 63}
    ancien = {k: v for k, v in resultat.structure.items() if k != "piles"}
    relu = service.en_structure(PROJET, _document({"structure": ancien}))
    assert relu is not None and relu.structure.piles == []
    resume = service.en_document(_document({"structure": resultat.structure})).structure_summary
    assert (resume.drawing_units, resume.counts["piles"]) == ("cm", 11)


def test_une_mesure_sur_une_feuille_pdf_dit_qu_elle_vient_du_pdf():
    ligne = _ligne("beam_span", 6000, "mm", label="P1", methode="geometrie")
    ligne["position"] = {"source": "geometry", "space": "page"}
    extraction = service.en_extraction(ligne)
    assert (extraction.source_type, extraction.source_label) == ("geometry", "Géométrie du PDF")
    (champ,) = service.preremplissage(PROJET, [ligne], "P1").fields
    assert champ.source_label == "Géométrie du PDF"
    assert "(géométrie du pdf)" in champ.provenance.detail


def test_meme_valeur_par_le_texte_et_la_geometrie_la_provenance_est_la_geometrie():
    lignes = [_ligne("beam_span", 6, "m", label="P1", ident="texte", methode="dxf"),
              _ligne("beam_span", 600, "cm", label="P1", ident="geo", methode="geometrie")]
    (champ,) = service.preremplissage(PROJET, lignes, "P1").fields
    assert (champ.value, champ.extraction_id) == (6000, "geo")
    assert (champ.source_type, champ.source_label) == ("geometry", "Géométrie du DXF")
    assert "(géométrie du dxf)" in champ.provenance.detail


def test_deux_valeurs_differentes_restent_un_conflit_geometrie_en_tete():
    lignes = [_ligne("beam_span", 6.5, "m", label="P1", ident="ocr", methode="ocr"),
              _ligne("beam_span", 600, "cm", label="P1", ident="geo", methode="geometrie")]
    rempli = service.preremplissage(PROJET, lignes, "P1")
    assert not rempli.fields
    (conflit,) = rempli.conflicts
    assert [(c.extraction_id, c.source_type) for c in conflit.candidates] == [
        ("geo", "geometry"), ("ocr", "ocr")]


def test_la_route_du_modele_exige_une_identite(client):
    reponse = client.get(f"/v1/projects/{PROJET}/documents/d1/structure")
    assert reponse.status_code == 401

