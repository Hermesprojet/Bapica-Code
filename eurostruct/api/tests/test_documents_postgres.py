"""La lecture des plans, de bout en bout, contre un PostgreSQL réel.

Dépôt → analyse → revue → décision → préremplissage → calcul. Chaque refus est
éprouvé là où il compte : un format inconnu, un lecteur, une autre
organisation, une personne sans nom, une décision déjà prise, une valeur
modifiée après report, une extraction d'un autre projet.

Lancé par ``db/test/documents_extractions.sh``, qui déploie la base, pose les
cinq identités FICTIVES, crée le magasin et fournit les DSN par
l'environnement — jamais en argument. Aucun plan réel : le PDF, le DXF et
l'en-tête DWG sont fabriqués par les tests du module d'extraction.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
MAGASIN = os.environ.get("EUROSTRUCT_STORAGE_DIR", "")
A = os.environ.get("EUROSTRUCT_DOCUMENTS_ACTEUR_A", "")
V = os.environ.get("EUROSTRUCT_DOCUMENTS_ACTEUR_V", "")
W = os.environ.get("EUROSTRUCT_DOCUMENTS_ACTEUR_W", "")
N = os.environ.get("EUROSTRUCT_DOCUMENTS_ACTEUR_N", "")
B = os.environ.get("EUROSTRUCT_DOCUMENTS_ACTEUR_B", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and MAGASIN and A and V and W and N and B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/documents_extractions.sh, qui deploie la base, pose "
                "les identites, cree le magasin et fournit les DSN."),
    ),
]

# LES FABRIQUES DE DOCUMENTS DU MODULE D'EXTRACTION — les memes octets que ses
# propres tests lisent. Aucune copie: une seconde fabrique deriverait.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "extraction" / "tests"))
from fabrique import LIGNES_DU_PLAN, dxf_de_plan, entete_dwg, pdf_de_texte  # noqa: E402
from fabrique_geometrie import dxf_coffrage_s101
from fabrique_pdf_vectoriel import pdf_plan_vectoriel

ISSUER = "https://fictif.documents.test/auth/v1"
AUDIENCE = "authenticated"
KID = "documents-1"
PDF = pdf_de_texte([LIGNES_DU_PLAN])


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def client(cle):
    from fastapi.testclient import TestClient
    from jwt.algorithms import RSAAlgorithm

    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase

    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    trousseau = TrousseauJwks("https://fictif.invalid/jwks",
                              lecteur=lambda _u: {"keys": [jwk]})
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer=ISSUER, audience=AUDIENCE,
                                 algorithmes=("RS256",), tolerance_horloge_s=0)
    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn=DSN)))
    app.state.authentificateur = AuthentificateurSupabase(reglages_auth,
                                                          trousseau=trousseau)
    app.state.fabrique_connexion = FabriqueConnexionPostgres(ReglagesBase(dsn=DSN))
    return TestClient(app)


@pytest.fixture(scope="module")
def entete(cle):
    def _entete(sub: str) -> dict[str, str]:
        maintenant = int(time.time())
        jeton = jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub, "iat": maintenant - 5,
             "nbf": maintenant - 5, "exp": maintenant + 3600},
            cle, algorithm="RS256", headers={"kid": KID})
        return {"Authorization": f"Bearer {jeton}"}

    return _entete


def _observer(sql: str, *params):
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        with connexion.cursor() as curseur:
            curseur.execute(sql, params)
            return curseur.fetchall()
    finally:
        connexion.close()


def _fichiers_du_magasin() -> set[str]:
    return {str(p.relative_to(MAGASIN)) for p in Path(MAGASIN).rglob("*") if p.is_file()}


def _creer_projet(client, entete, nom: str) -> dict:
    reponse = client.post("/v1/projects", headers=entete(A), json={
        "name": nom, "reference": None, "country": "BE",
        "ndp_as_of": "2026-07-26"})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _deposer(client, entete, projet, octets: bytes, *, qui: str = A,
             kind: str = "architect_drawing", nom: str = "FICTIF plan R+1.pdf"):
    return client.post(f"/v1/projects/{projet['project_id']}/documents",
                       params={"kind": kind, "filename": nom}, content=octets,
                       headers={**entete(qui), "Content-Type": "application/octet-stream"})


@pytest.fixture(scope="module")
def projet(client, entete):
    return _creer_projet(client, entete, "FICTIF Immeuble R+1 (lecture des plans)")


@pytest.fixture(scope="module")
def plan(client, entete, projet):
    reponse = _deposer(client, entete, projet, PDF)
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    extractions = client.get(
        f"/v1/projects/{projet['project_id']}/extractions",
        params={"document_id": corps["document"]["document_id"]},
        headers=entete(A)).json()["extractions"]
    return corps, extractions


def _une(extractions, kind, value=None):
    trouvees = [x for x in extractions if x["kind"] == kind
                and (value is None or x["proposed_value"]["value"] == value)]
    assert len(trouvees) == 1, (kind, value, trouvees)
    return trouvees[0]


def _decider(client, entete, projet, extraction, decision, qui=A, **corps):
    return client.post(
        f"/v1/projects/{projet['project_id']}/extractions/"
        f"{extraction['extraction_id']}/decision",
        json={"decision": decision, **corps}, headers=entete(qui))


@pytest.fixture(scope="module")
def decisions(client, entete, projet, plan):
    """Les décisions d'un ingénieur nommé sur le plan déposé."""
    _, extractions = plan
    faites = {}
    for kind, valeur in (("beam_width", 30), ("beam_span", 6.0),
                         ("concrete_class", "C30/37"), ("steel_grade", "B500B"),
                         ("exposure_class", "XC3"), ("bar_count", 4),
                         ("bar_diameter", 20), ("link_diameter", 8),
                         ("link_spacing", 15)):
        reponse = _decider(client, entete, projet, _une(extractions, kind, valeur),
                           "confirm")
        assert reponse.status_code == 200, reponse.text
        faites[kind] = reponse.json()
    reponse = _decider(client, entete, projet, _une(extractions, "beam_depth"),
                       "correct", final_value={"value": 65, "unit": "cm"},
                       note="FICTIF: hauteur lue sur la coupe A-A")
    assert reponse.status_code == 200, reponse.text
    faites["beam_depth"] = reponse.json()
    for kind in ("concrete_cover", "load_value"):
        reponse = _decider(client, entete, projet, _une(extractions, kind),
                           "reject", note="FICTIF: valeur du CCTP retenue")
        assert reponse.status_code == 200, reponse.text
        faites[kind] = reponse.json()
    return faites


# ==================================================================== dépôt
def test_un_plan_depose_est_conserve_analyse_et_ses_valeurs_proposees(plan):
    corps, extractions = plan
    document = corps["document"]
    assert corps["already_present"] is False
    assert document["format"] == "pdf" and document["mime_type"] == "application/pdf"
    assert document["analysis_status"] == "analyse"
    assert document["text_layer"] is True and document["page_count"] == 1
    assert corps["extractions_created"] == len(extractions) >= 20
    assert document["proposed_count"] == len(extractions)
    assert "PROPOSITIONS" in corps["notice"]
    for x in extractions:
        assert x["status"] == "proposed" and x["final_value"] is None
        assert x["raw_text"].strip() and x["page"] == 1
        assert x["bbox"] is not None and 0 <= x["confidence"] < 1
        assert x["method"] == "texte_natif"
        assert x["model_name"].startswith("eurostruct-extraction/")
    # LES OCTETS SONT LA, A L'ADRESSE DE LEUR EMPREINTE.
    assert any(f.startswith("pieces/") and document["sha256"] in f
               for f in _fichiers_du_magasin())


def test_la_base_porte_la_tracabilite_complete(plan):
    corps, _ = plan
    (manquantes,) = _observer(
        "select count(*) from extractions where document_id = %s and "
        "(raw_text is null or page is null or confidence is null or method is null "
        " or (bbox is null and position is null) or status <> 'proposed')",
        corps["document"]["document_id"])[0]
    assert manquantes == 0


def test_les_memes_octets_ne_font_pas_un_second_document(client, entete, projet, plan):
    reponse = _deposer(client, entete, projet, PDF, nom="FICTIF copie.pdf")
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["already_present"] is True and corps["extractions_created"] == 0
    assert corps["document"]["document_id"] == plan[0]["document"]["document_id"]
    assert corps["document"]["filename"] == "FICTIF plan R+1.pdf"


def test_un_format_inconnu_est_refuse_sans_rien_deposer(client, entete, projet, plan):
    avant = _fichiers_du_magasin()
    reponse = _deposer(client, entete, projet, b"PK\x03\x04 FICTIF archive",
                       nom="plan.pdf")
    assert reponse.status_code == 415
    assert reponse.json()["detail"]["error"] == "format_non_pris_en_charge"
    assert _fichiers_du_magasin() == avant


def test_un_lecteur_lit_mais_ne_depose_pas(client, entete, projet, plan):
    avant = _fichiers_du_magasin()
    reponse = _deposer(client, entete, projet, pdf_de_texte([[(40, 40, 10, "FICTIF W")]]),
                       qui=W)
    assert reponse.status_code == 422
    assert "ne depose pas" in reponse.json()["detail"]["detail"]
    assert _fichiers_du_magasin() == avant
    liste = client.get(f"/v1/projects/{projet['project_id']}/documents",
                       headers=entete(W))
    assert liste.status_code == 200 and liste.json()["documents"]


def test_une_autre_organisation_ne_voit_ni_ne_depose(client, entete, projet, plan):
    avant = _fichiers_du_magasin()
    base = f"/v1/projects/{projet['project_id']}"
    assert client.get(f"{base}/documents", headers=entete(B)).status_code == 422
    assert client.get(f"{base}/extractions", headers=entete(B)).status_code == 422
    assert _deposer(client, entete, projet, PDF, qui=B).status_code == 422
    assert _fichiers_du_magasin() == avant


def test_le_telechargement_rend_les_octets_deposes(client, entete, projet, plan):
    document = plan[0]["document"]
    reponse = client.get(
        f"/v1/projects/{projet['project_id']}/documents/{document['document_id']}/download",
        headers=entete(W))
    assert reponse.status_code == 200
    assert reponse.content == PDF
    # LE NOM EXACT VOYAGE DANS LA FORME RFC 5987; la forme ASCII de repli est
    # assainie par `disposition_de_fichier`, comme pour un livrable.
    assert "filename*=UTF-8''FICTIF%20plan%20R%2B1.pdf" in (
        reponse.headers["content-disposition"])


def test_un_validateur_depose_un_dxf_qui_est_lu(client, entete, projet):
    reponse = _deposer(client, entete, projet, dxf_de_plan(), qui=V,
                       kind="formwork_drawing", nom="FICTIF coffrage.dxf")
    assert reponse.status_code == 201, reponse.text
    document = reponse.json()["document"]
    assert (document["format"], document["analysis_status"]) == ("dxf", "analyse")
    assert reponse.json()["extractions_created"] > 0


def test_un_dwg_est_conserve_non_lu_et_peut_etre_analyse_a_nouveau(client, entete, projet):
    reponse = _deposer(client, entete, projet, entete_dwg(), nom="FICTIF plan.dwg")
    assert reponse.status_code == 201, reponse.text
    document = reponse.json()["document"]
    assert document["format"] == "dwg" and document["analysis_status"] == "non_lu"
    assert "licence ODA ou RealDWG" in document["analysis_detail"]
    assert document["can_reanalyse"] is True
    encore = client.post(
        f"/v1/projects/{projet['project_id']}/documents/{document['document_id']}/analysis",
        headers=entete(A))
    assert encore.status_code == 200, encore.text
    assert encore.json()["document"]["analysis_status"] == "non_lu"


def test_un_document_qui_porte_des_propositions_ne_se_reanalyse_pas(
        client, entete, projet, plan):
    document = plan[0]["document"]
    assert document["can_reanalyse"] is False
    reponse = client.post(
        f"/v1/projects/{projet['project_id']}/documents/{document['document_id']}/analysis",
        headers=entete(A))
    assert reponse.status_code == 422
    assert "deja ete analyse" in reponse.json()["detail"]["detail"]


# ================================================================= décisions
def test_confirmer_enregistre_le_nom_de_l_adhesion_et_la_date_du_serveur(decisions):
    largeur = decisions["beam_width"]
    assert largeur["status"] == "confirmed"
    assert largeur["final_value"] == largeur["proposed_value"] == {"value": 30, "unit": "cm"}
    assert largeur["confirmed_by_name"] == "FICTIF Ing. A"
    assert largeur["confirmed_at"]


def test_corriger_retient_une_autre_valeur_et_son_motif(decisions):
    hauteur = decisions["beam_depth"]
    assert hauteur["status"] == "corrected"
    assert hauteur["proposed_value"] == {"value": 60, "unit": "cm"}
    assert hauteur["final_value"] == {"value": 65, "unit": "cm"}
    assert hauteur["decision_note"] == "FICTIF: hauteur lue sur la coupe A-A"


def test_rejeter_ne_retient_rien(decisions):
    assert decisions["concrete_cover"]["status"] == "rejected"
    assert decisions["concrete_cover"]["final_value"] is None


def test_une_decision_est_definitive(client, entete, projet, decisions):
    reponse = _decider(client, entete, projet, decisions["beam_width"], "reject")
    assert reponse.status_code == 422
    assert "definitive" in reponse.json()["detail"]["detail"]


def test_sans_nom_enregistre_on_ne_decide_pas(client, entete, projet, plan):
    reponse = _decider(client, entete, projet, _une(plan[1], "slab_thickness"),
                       "confirm", qui=N)
    assert reponse.status_code == 422
    assert "aucun nom" in reponse.json()["detail"]["detail"]


def test_un_lecteur_et_une_autre_organisation_ne_decident_pas(client, entete, projet, plan):
    for qui in (W, B):
        reponse = _decider(client, entete, projet, _une(plan[1], "slab_thickness"),
                           "confirm", qui=qui)
        assert reponse.status_code == 422, qui


def test_un_corps_qui_nomme_le_decideur_est_refuse(client, entete, projet, plan):
    reponse = _decider(client, entete, projet, _une(plan[1], "story_height"),
                       "confirm", confirmed_by_name="FICTIF usurpateur")
    assert reponse.status_code == 422


def test_une_correction_identique_a_la_proposition_est_refusee(client, entete, projet, plan):
    reponse = _decider(client, entete, projet, _une(plan[1], "story_height"),
                       "correct", final_value={"value": 3.0, "unit": "m"})
    assert reponse.status_code == 422
    assert "confirmez-la" in reponse.json()["detail"]["detail"]


def test_les_decomptes_du_document_suivent_les_decisions(client, entete, projet, plan,
                                                         decisions):
    documents = client.get(f"/v1/projects/{projet['project_id']}/documents",
                           headers=entete(A)).json()["documents"]
    document = next(d for d in documents
                    if d["document_id"] == plan[0]["document"]["document_id"])
    assert (document["confirmed_count"], document["corrected_count"],
            document["rejected_count"]) == (9, 1, 2)


# ============================================================ préremplissage
def test_le_preremplissage_rend_les_valeurs_decidees_dans_l_unite_du_champ(
        client, entete, projet, decisions):
    reponse = client.get(f"/v1/projects/{projet['project_id']}/extractions/prefill",
                         params={"element": "P1"}, headers=entete(A))
    assert reponse.status_code == 200, reponse.text
    champs = {c["path"]: (c["value"], c["unit"]) for c in reponse.json()["fields"]}
    assert champs == {
        "geometry.b": (300, "mm"), "geometry.h": (650, "mm"),
        "geometry.l_eff": (6000, "mm"),
        "materials.concrete_grade": ("C30/37", None),
        "materials.steel_grade": ("B500B", None), "exposure_class": ("XC3", None),
        "bars.count": (4, None), "bars.diameter": (20, "mm"),
        "links.diameter": (8, "mm"), "links.spacing": (150, "mm"),
    }
    # REJETEE, LA VALEUR D'ENROBAGE NE SE REPORTE PAS — elle se saisit.
    assert "cover" not in champs


# ======================================================== calcul et provenance
def _requete_depuis(prefill: dict, **remplace) -> dict:
    champs = {c["path"]: c for c in prefill["fields"]}

    def mm(chemin):
        return {"value": champs[chemin]["value"], "unit": "mm"}

    corps = {
        "element": "P1", "strict_ndp": False,
        "geometry": {"b": mm("geometry.b"), "h": mm("geometry.h"),
                     "d": {"value": 600, "unit": "mm"},
                     "l_eff": mm("geometry.l_eff")},
        "materials": {"concrete_grade": champs["materials.concrete_grade"]["value"],
                      "steel_grade": champs["materials.steel_grade"]["value"]},
        "M_Ed": {"value": 250, "unit": "kN*m"}, "V_Ed": {"value": 300, "unit": "kN"},
        "M_char": {"value": 180, "unit": "kN*m"},
        "M_qp": {"value": 120, "unit": "kN*m"},
        "phi_creep": 2.0, "exposure_class": champs["exposure_class"]["value"],
        "structural_system": "simply_supported",
        "supports_brittle_partitions": False,
        "bars": {"count": champs["bars.count"]["value"], "diameter": mm("bars.diameter")},
        "links": {"legs": 2, "diameter": mm("links.diameter"),
                  "spacing": mm("links.spacing")},
        "cot_theta": 1.5, "cover": {"value": 40, "unit": "mm"},
        "anchorage_available": {"value": 800, "unit": "mm"},
        # LA PROVENANCE TELLE QUE LE CLIENT POURRAIT LA TRAFIQUER: le nom et le
        # detail sont faux. Le serveur doit les remplacer par ceux de la base.
        "provenance": {chemin: {**c["provenance"], "confirmed_by": "FICTIF usurpateur",
                                "detail": "FICTIF detail invente"}
                       for chemin, c in champs.items()},
    }
    corps.update(remplace)
    return corps


@pytest.fixture(scope="module")
def prefill(client, entete, projet, decisions):
    return client.get(f"/v1/projects/{projet['project_id']}/extractions/prefill",
                      params={"element": "P1"}, headers=entete(A)).json()


def _nombre_de_calculs(projet) -> int:
    return _observer("select count(*) from calculations where project_id = %s",
                     projet["project_id"])[0][0]


def test_un_calcul_accepte_la_provenance_decidee_et_la_reecrit(
        client, entete, projet, prefill):
    url = f"/v1/projects/{projet['project_id']}/beam-verifications"
    reponse = client.post(url, json=_requete_depuis(prefill), headers=entete(A))
    assert reponse.status_code == 201, reponse.text
    etude = reponse.json()
    provenance = etude["request"]["provenance"]
    assert set(provenance) == {c["path"] for c in prefill["fields"]}
    for origine in provenance.values():
        assert origine["confirmed_by"] == "FICTIF Ing. A"
        assert "FICTIF detail invente" not in origine["detail"]
        assert "FICTIF plan R+1.pdf" in origine["detail"]

    # LA REQUETE GELEE PORTE LA PROVENANCE REECRITE, ET LA RELECTURE AUSSI.
    ((gelee,),) = _observer("select request->'provenance' from calculations where id = %s",
                            etude["calculation_id"])
    assert gelee["geometry.b"]["confirmed_by"] == "FICTIF Ing. A"
    relue = client.get(f"{url}/{etude['calculation_id']}", headers=entete(A)).json()
    assert relue["request"]["provenance"]["geometry.h"]["extraction_id"] == (
        provenance["geometry.h"]["extraction_id"])

    # LA NOTE DIT D'OU VIENNENT CES ENTREES, et la correction ce qui etait lu.
    note = client.get(
        f"/v1/projects/{projet['project_id']}/calculations/{etude['calculation_id']}/note.html",
        headers=entete(A))
    assert note.status_code == 200
    assert "Origine des données d'entrée" in note.text
    assert "FICTIF Ing. A" in note.text and "FICTIF usurpateur" not in note.text
    assert "valeur corrigée (lue : 60 cm)" in note.text


def test_une_etude_saisie_garde_sa_charge_d_hier(client, entete, projet, prefill):
    url = f"/v1/projects/{projet['project_id']}/beam-verifications"
    corps = _requete_depuis(prefill)
    del corps["provenance"]
    reponse = client.post(url, json=corps, headers=entete(A))
    assert reponse.status_code == 201, reponse.text
    ((a_la_cle,),) = _observer("select request ? 'provenance' from calculations where id = %s",
                               reponse.json()["calculation_id"])
    assert a_la_cle is False
    note = client.get(
        f"/v1/projects/{projet['project_id']}/calculations/"
        f"{reponse.json()['calculation_id']}/note.html", headers=entete(A))
    assert note.status_code == 200
    assert "Origine des données d'entrée" not in note.text


@pytest.mark.parametrize("cas", ["valeur_modifiee", "proposee", "rejetee", "autre_projet",
                                 "identifiant_invalide"])
def test_une_provenance_sans_decision_valable_refuse_le_calcul_sans_ecriture(
        client, entete, projet, plan, prefill, cas):
    url = f"/v1/projects/{projet['project_id']}/beam-verifications"
    corps = _requete_depuis(prefill)
    if cas == "valeur_modifiee":
        corps["geometry"]["b"] = {"value": 310, "unit": "mm"}
        chemin = "geometry.b"
    elif cas == "proposee":
        xc4 = _une(plan[1], "exposure_class", "XC4")
        corps["exposure_class"] = "XC4"
        corps["provenance"]["exposure_class"] = {
            "kind": "document_extraction", "detail": "x", "confirmed_by": "X",
            "extraction_id": xc4["extraction_id"]}
        chemin = "exposure_class"
    elif cas == "rejetee":
        enrobage = _une(plan[1], "concrete_cover")
        corps["cover"] = {"value": 30, "unit": "mm"}
        corps["provenance"]["cover"] = {
            "kind": "document_extraction", "detail": "x", "confirmed_by": "X",
            "extraction_id": enrobage["extraction_id"]}
        chemin = "cover"
    elif cas == "autre_projet":
        ailleurs = _creer_projet(client, entete, f"FICTIF autre projet {cas}")
        depot = _deposer(client, entete, ailleurs, PDF).json()
        extractions = client.get(
            f"/v1/projects/{ailleurs['project_id']}/extractions",
            params={"document_id": depot["document"]["document_id"]},
            headers=entete(A)).json()["extractions"]
        etrangere = _une(extractions, "beam_width")
        assert _decider(client, entete, ailleurs, etrangere, "confirm").status_code == 200
        corps["provenance"]["geometry.b"] = {
            **corps["provenance"]["geometry.b"],
            "extraction_id": etrangere["extraction_id"]}
        chemin = "geometry.b"
    else:
        corps["provenance"]["geometry.b"] = {
            **corps["provenance"]["geometry.b"], "extraction_id": "pas-un-uuid"}
        chemin = "geometry.b"

    avant = _nombre_de_calculs(projet)
    reponse = client.post(url, json=corps, headers=entete(A))
    assert reponse.status_code == 422, reponse.text
    detail = reponse.json()["detail"]
    assert detail["error"] == "provenance_refusee"
    assert chemin in {f["path"] for f in detail["fields"]}
    assert _nombre_de_calculs(projet) == avant


# ================================================ la géométrie d'un DXF
#: LE PLAN S-101: aucun texte n'y ecrit une portee; la geometrie les donne.
S101 = dxf_coffrage_s101()


@pytest.fixture(scope="module")
def projet_geo(client, entete):
    return _creer_projet(client, entete, "FICTIF S-101 (geometrie du dessin)")


@pytest.fixture(scope="module")
def coffrage(client, entete, projet_geo):
    reponse = _deposer(client, entete, projet_geo, S101, kind="formwork_drawing",
                       nom="FICTIF-S-101-coffrage.dxf")
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    extractions = client.get(
        f"/v1/projects/{projet_geo['project_id']}/extractions",
        params={"document_id": corps["document"]["document_id"]},
        headers=entete(A)).json()["extractions"]
    return corps, extractions


def test_un_dxf_depose_donne_un_modele_structurel_et_des_propositions_geometriques(
        coffrage):
    corps, extractions = coffrage
    document = corps["document"]
    assert document["has_structure"] is True
    assert document["structure_summary"]["counts"]["spans"] == 5
    assert document["structure_summary"]["drawing_units"] == "cm"
    # LA LISTE NE TRANSPORTE PAS LE MODELE; la base, elle, le garde.
    assert "structure" not in (document["analysis_report"] or {})
    ((schema,),) = _observer(
        "select analysis_report->'structure'->>'schema' from documents where id = %s",
        document["document_id"])
    assert schema == "eurostruct.structure/1"
    portees = {x["element_label"]: x for x in extractions
               if x["kind"] == "beam_span" and x["method"] == "geometrie"}
    assert {r: x["proposed_value"] for r, x in portees.items()} == {
        "P1": {"value": 600, "unit": "cm"}, "P2": {"value": 450, "unit": "cm"},
        "P3": {"value": 600, "unit": "cm"}, "P4": {"value": 450, "unit": "cm"},
        "P5": {"value": 600, "unit": "cm"}}
    assert {x["source_type"] for x in portees.values()} == {"geometry"}
    assert all(x["status"] == "proposed" for x in extractions)
    # LA BASE A ADMIS LA METHODE (0029), position tracee comprise.
    lignes = _observer(
        "select method, position->>'source', position->'element'->>'type' "
        "from extractions where document_id = %s and kind = 'beam_span'",
        document["document_id"])
    assert set(lignes) == {("geometrie", "geometry", "span")}


def test_le_modele_structurel_se_lit_par_sa_route(client, entete, projet_geo, coffrage):
    corps, _ = coffrage
    url = (f"/v1/projects/{projet_geo['project_id']}/documents/"
           f"{corps['document']['document_id']}/structure")
    reponse = client.get(url, headers=entete(V))
    assert reponse.status_code == 200, reponse.text
    modele = reponse.json()["structure"]
    assert modele["schema"] == "eurostruct.structure/1"
    assert {(t["mark"], t["from"]["support"], t["to"]["support"], t["axis_length"])
            for t in modele["spans"]} == {
        ("P1", "column:A1", "column:B1", 600), ("P2", "column:B1", "column:C1", 450),
        ("P3", "column:A2", "column:B2", 600), ("P4", "column:B2", "column:C2", 450),
        ("P5", "column:B1", "column:B2", 600)}
    # UNE AUTRE ORGANISATION NE LE LIT PAS.
    assert client.get(url, headers=entete(B)).status_code in (403, 404, 422)


@pytest.fixture(scope="module")
def feuille_pdf(client, entete, projet_geo):
    reponse = _deposer(client, entete, projet_geo, pdf_plan_vectoriel(),
                       kind="architect_drawing", nom="FICTIF-feuille-vectorielle.pdf")
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    extractions = client.get(
        f"/v1/projects/{projet_geo['project_id']}/extractions",
        params={"document_id": corps["document"]["document_id"]},
        headers=entete(A)).json()["extractions"]
    return corps, extractions


def test_une_feuille_pdf_vectorielle_donne_un_modele_et_des_mesures_tracees(
        client, entete, projet_geo, feuille_pdf):
    corps, extractions = feuille_pdf
    document = corps["document"]
    assert document["has_structure"] is True
    assert document["structure_summary"]["drawing_units"] == "mm"
    entraxes = {x["element_label"]: x for x in extractions
                if x["kind"] == "grid_spacing" and x["method"] == "geometrie"}
    assert {r: x["proposed_value"] for r, x in entraxes.items()} == {
        "A-B": {"value": 6000, "unit": "mm"}, "B-C": {"value": 6000, "unit": "mm"},
        "1-2": {"value": 5000, "unit": "mm"}}
    assert {x["source_label"] for x in entraxes.values()} == {"Géométrie du PDF"}
    # LA BASE A ADMIS LA BOITE SUR LA FEUILLE ET LA POSITION, ENSEMBLE.
    lignes = _observer(
        "select page, bbox is not null, position->>'space' from extractions "
        "where document_id = %s and method = 'geometrie'", document["document_id"])
    assert lignes and set(lignes) == {(1, True, "page")}
    modele = client.get(
        f"/v1/projects/{projet_geo['project_id']}/documents/"
        f"{document['document_id']}/structure", headers=entete(V)).json()["structure"]
    assert modele["units"]["source"] == "echelle_ecrite_et_cotes"
    assert modele["units"]["sheet"]["page"] == 1
    assert {n["element"] for n in modele["unresolved"]} >= {"poutres"}


def test_un_document_sans_geometrie_n_a_pas_de_modele(client, entete, projet, plan):
    corps, _ = plan
    reponse = client.get(
        f"/v1/projects/{projet['project_id']}/documents/"
        f"{corps['document']['document_id']}/structure", headers=entete(A))
    assert reponse.status_code == 404
    assert reponse.json()["detail"]["error"] == "structure_absente"


def test_une_portee_mesuree_sur_le_dessin_decidee_entre_dans_le_calcul(
        client, entete, projet_geo, coffrage):
    _, extractions = coffrage
    p1 = [x for x in extractions if x["kind"] == "beam_span" and x["method"] == "geometrie"
          and x["element_label"] == "P1"]
    largeur = [x for x in extractions if x["kind"] == "beam_width"
               and x["method"] == "geometrie" and x["element_label"] == "P1"]
    assert len(p1) == 1 and len(largeur) == 1
    for extraction in (p1[0], largeur[0]):
        reponse = _decider(client, entete, projet_geo, extraction, "confirm")
        assert reponse.status_code == 200, reponse.text
        assert reponse.json()["confirmed_by_name"] == "FICTIF Ing. A"

    prefill = client.get(f"/v1/projects/{projet_geo['project_id']}/extractions/prefill",
                         params={"element": "P1"}, headers=entete(A)).json()
    champs = {c["path"]: c for c in prefill["fields"]}
    assert (champs["geometry.l_eff"]["value"], champs["geometry.l_eff"]["unit"]) == (
        6000, "mm")
    assert (champs["geometry.b"]["value"], champs["geometry.b"]["unit"]) == (300, "mm")
    assert "(géométrie du dxf)" in champs["geometry.l_eff"]["provenance"]["detail"]
    assert "5.3.2.2" in champs["geometry.l_eff"]["warning"]

    corps = {
        "element": "P1", "strict_ndp": False,
        "geometry": {"b": {"value": 300, "unit": "mm"}, "h": {"value": 600, "unit": "mm"},
                     "d": {"value": 550, "unit": "mm"},
                     "l_eff": {"value": 6000, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"}, "V_Ed": {"value": 300, "unit": "kN"},
        "M_char": {"value": 180, "unit": "kN*m"}, "M_qp": {"value": 120, "unit": "kN*m"},
        "phi_creep": 2.0, "exposure_class": "XC3",
        "structural_system": "simply_supported", "supports_brittle_partitions": False,
        "bars": {"count": 4, "diameter": {"value": 20, "unit": "mm"}},
        "links": {"legs": 2, "diameter": {"value": 10, "unit": "mm"},
                  "spacing": {"value": 150, "unit": "mm"}},
        "cot_theta": 1.5, "cover": {"value": 40, "unit": "mm"},
        "anchorage_available": {"value": 800, "unit": "mm"},
        "provenance": {chemin: champs[chemin]["provenance"]
                       for chemin in ("geometry.l_eff", "geometry.b")},
    }
    reponse = client.post(f"/v1/projects/{projet_geo['project_id']}/beam-verifications",
                          json=corps, headers=entete(A))
    assert reponse.status_code == 201, reponse.text
    provenance = reponse.json()["request"]["provenance"]
    assert set(provenance) == {"geometry.l_eff", "geometry.b"}
    assert "FICTIF-S-101-coffrage.dxf" in provenance["geometry.l_eff"]["detail"]
    assert "géométrie du dxf" in provenance["geometry.l_eff"]["detail"]
    assert provenance["geometry.l_eff"]["extraction_id"] == p1[0]["extraction_id"]


# ============================================================ rapprochement
def test_le_rapprochement_voit_chaque_piece_deposee(plan):
    import psycopg2

    from eurostruct_api.reconciliation import INTACT, _lignes_du_magasin, rapprocher
    from eurostruct_api.stockage import StockageLocal

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.set_session(readonly=True)
        lignes = _lignes_du_magasin(connexion)
    finally:
        connexion.close()
    pieces = [ligne for ligne in lignes if ligne["source"] == "documents"]
    assert pieces
    rapport = rapprocher(lignes, StockageLocal(MAGASIN), empreintes=True)
    assert rapport.sain, [c for c in rapport.constats if c.verdict != INTACT]
    assert {c.document_id for c in rapport.constats if c.document_id} == {
        ligne["id"] for ligne in pieces}
