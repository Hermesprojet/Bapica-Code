"""La lecture des plans, côté service — sans base.

Ce qui se juge ici sans PostgreSQL : le report d'une valeur DÉCIDÉE dans
l'unité d'un champ, le préremplissage, le contrôle de provenance d'un calcul,
et les refus d'une route avant toute base. Le parcours complet — dépôt réel,
analyse, revue, décision, report, calcul — est dans
``test_documents_postgres.py``, lancé par ``db/test/documents_extractions.sh``.
"""
from __future__ import annotations

import pytest
from eurostruct_engine.schemas.ec2_verification import (
    PROVENANCE_CHEMINS,
    Ec2BeamVerificationRequest,
)
from pydantic import ValidationError

from eurostruct_api import documents as service

PROJET = "aaaaaaaa-0000-0000-0000-00000000000a"


def _ligne(kind: str, value, unit, *, status: str = "confirmed",
           label: str | None = None, ident: str = "e1",
           proposee=None) -> dict:
    """Une extraction telle que ``PostgresAtelier.extractions`` la rend."""
    return {
        "extraction_id": ident, "document_id": "d1",
        "document_filename": "FICTIF-plan.pdf", "document_sha256": "a" * 64,
        "kind": kind,
        "proposed_value": proposee or {"value": value, "unit": unit},
        "final_value": ({"value": value, "unit": unit}
                        if status in ("confirmed", "corrected") else None),
        "status": status, "page": 2, "bbox": [10.0, 20.0, 60.0, 30.0],
        "position": None, "confidence": 0.6, "method": "texte_natif",
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
