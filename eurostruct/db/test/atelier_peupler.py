"""PEUPLER UN ATELIER PAR LE PRODUIT, PUIS CONSTATER QU'IL A SURVECU.

    ESC_PEUPLE_DSN=... ESC_PEUPLE_ACTEUR=<uuid> ESC_PEUPLE_STOCKAGE=<dossier> \
    PYTHONPATH=<arbre>/api/src:<arbre>/engine/src \
      python3 db/test/atelier_peupler.py peupler|verifier <etat.json>

POURQUOI CE FICHIER EXISTE
---------------------------
La mise a niveau d'une base en service doit conserver les etudes, leurs
variantes et leurs documents. Le prouver demande une installation REELLEMENT
peuplee — pas des lignes posees a la main en SQL, qui ne passeraient par
aucune primitive et ne porteraient ni empreinte de calcul, ni octets de
livrable.

Ce script peuple donc par le PRODUIT: il construit l'application comme les
tests d'API la construisent, et appelle ses routes. `PYTHONPATH` decide de
QUELLE version du produit: la recette peuple avec l'ANCIENNE et verifie avec
la NOUVELLE. C'est tout l'interet.

CE QU'IL NE FAIT PAS. Il ne regarde aucune table: ce qu'il compare, ce sont
les reponses du produit et les octets des fichiers. La comparaison ligne pour
ligne, elle, est faite de l'exterieur par `db/test/comparer_contenu.sh`, avec
un lecteur qui contourne RLS.

AUCUN SECRET REEL. La cle de signature est tiree a chaque execution et n'existe
que dans ce processus; l'emetteur et l'audience sont fictifs.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

ISSUER = "https://fictif.mise-a-niveau.test/auth/v1"
AUDIENCE = "authenticated"
KID = "mise-a-niveau-1"

DSN = os.environ["ESC_PEUPLE_DSN"]
ACTEUR = os.environ["ESC_PEUPLE_ACTEUR"]


def _application():
    """L'application, construite comme les tests d'API la construisent."""
    import jwt  # noqa: F401  (verifie la presence du paquet avant d'aller plus loin)
    from cryptography.hazmat.primitives.asymmetric import rsa
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from fastapi.testclient import TestClient
    from jwt.algorithms import RSAAlgorithm

    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer=ISSUER, audience=AUDIENCE,
                                 algorithmes=("RS256",), tolerance_horloge_s=0)
    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn=DSN)))
    app.state.authentificateur = AuthentificateurSupabase(
        reglages_auth,
        trousseau=TrousseauJwks("https://fictif.invalid/jwks",
                                lecteur=lambda _u: {"keys": [jwk]}))
    app.state.fabrique_connexion = FabriqueConnexionPostgres(ReglagesBase(dsn=DSN))
    return TestClient(app), cle


def _entete(cle) -> dict[str, str]:
    import jwt

    maintenant = int(time.time())
    jeton = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": ACTEUR,
         "iat": maintenant - 5, "nbf": maintenant - 5, "exp": maintenant + 3600},
        cle, algorithm="RS256", headers={"kid": KID})
    return {"Authorization": f"Bearer {jeton}"}


#: L'ETUDE BELGE DE REFERENCE — la meme que celle du parcours de demonstration.
def _corps(**remplace):
    base = {
        "element": "P1", "strict_ndp": False,
        "geometry": {"b": {"value": 300, "unit": "mm"},
                     "h": {"value": 600, "unit": "mm"},
                     "d": {"value": 550, "unit": "mm"},
                     "l_eff": {"value": 6000, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"},
        "V_Ed": {"value": 300, "unit": "kN"},
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


def _exige(condition, message):
    if not condition:
        print(f"ECHEC: {message}", file=sys.stderr)
        sys.exit(1)


def _resume(etude: dict) -> dict:
    """Ce qui doit etre IDENTIQUE avant et apres la mise a niveau."""
    return {
        "calculation_id": etude["calculation_id"],
        "derived_from_calculation_id": etude.get("derived_from_calculation_id"),
        "status": etude["status"],
        "engineering_inputs_hash": etude["engineering_inputs_hash"],
        "calculation_fingerprint": etude["calculation_fingerprint"],
        "ndp_snapshot_id": etude["ndp_snapshot_id"],
        "execution_identity": etude["execution_identity"],
        "engine_version": etude["engine_version"],
        "inputs": etude.get("inputs") or {},
        "sections": [{"key": s["key"], "status": s["status"],
                      "utilisation": s.get("utilisation")}
                     for s in etude["sections"]],
    }


def peupler(chemin: str) -> None:
    client, cle = _application()
    entete = _entete(cle)
    jeton_court = os.environ.get("ESC_PEUPLE_JETON", "man")

    r = client.post("/v1/organizations", headers=entete, json={
        "name": f"FICTIF Bureau de mise a niveau {jeton_court}", "country": "BE",
        "display_name": "Ingenieur d'essai (mise a niveau)",
        "professional_id": None})
    _exige(r.status_code == 201, f"fondation du bureau: {r.status_code} {r.text[:200]}")
    org = r.json()["organization_id"]

    r = client.post("/v1/projects", headers=entete, json={
        "name": "FICTIF Poutre belge conservee", "reference": f"MAN-{jeton_court}",
        "country": "BE", "region": None, "ndp_as_of": "2026-01-01",
        "organization_id": org})
    _exige(r.status_code == 201, f"creation du projet: {r.status_code} {r.text[:200]}")
    projet = r.json()["project_id"]
    url = f"/v1/projects/{projet}/beam-verifications"

    r = client.post(url, headers=entete, json=_corps())
    _exige(r.status_code == 201, f"etude initiale: {r.status_code} {r.text[:300]}")
    etude = r.json()
    _exige(etude["status"] == "passed", f"l'etude ne conclut pas: {etude['status']}")

    r = client.post(url, headers=entete, json=_corps(
        bars={"count": 5, "diameter": {"value": 20, "unit": "mm"}},
        derived_from_calculation_id=etude["calculation_id"]))
    _exige(r.status_code == 201, f"variante: {r.status_code} {r.text[:300]}")
    variante = r.json()
    _exige(variante["derived_from_calculation_id"] == etude["calculation_id"],
           "la variante ne nomme pas son origine")

    livrables = []
    for calcul, format_ in ((etude["calculation_id"], "pdf"),
                            (etude["calculation_id"], "dxf"),
                            (variante["calculation_id"], "pdf")):
        r = client.post(f"/v1/projects/{projet}/deliverables", headers=entete,
                        json={"calculation_id": calcul, "format": format_})
        _exige(r.status_code == 201, f"livrable {format_}: {r.status_code} {r.text[:200]}")
        cree = r.json()
        octets = client.get(
            f"/v1/projects/{projet}/deliverables/{cree['deliverable_id']}/download",
            headers=entete)
        _exige(octets.status_code == 200, f"telechargement {format_}: {octets.status_code}")
        recu = hashlib.sha256(octets.content).hexdigest()
        _exige(recu == cree["sha256"],
               f"{format_}: les octets recus ne portent pas l'empreinte enregistree")
        livrables.append({"deliverable_id": cree["deliverable_id"],
                          "calculation_id": calcul, "kind": cree["kind"],
                          "sha256": recu, "taille": len(octets.content)})

    etat = {"organization_id": org, "project_id": projet,
            "etude": _resume(etude), "variante": _resume(variante),
            "livrables": livrables}
    with open(chemin, "w", encoding="utf-8") as sortie:
        json.dump(etat, sortie, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"peuple: projet {projet}, etude {etude['calculation_id']}, "
          f"variante {variante['calculation_id']}, {len(livrables)} livrable(s)")


def verifier(chemin: str) -> None:
    with open(chemin, encoding="utf-8") as entree:
        etat = json.load(entree)
    client, cle = _application()
    entete = _entete(cle)
    projet = etat["project_id"]

    #: L'HISTORIQUE: les deux etudes sont la, et la filiation aussi.
    r = client.get(f"/v1/projects/{projet}/calculations", headers=entete)
    _exige(r.status_code == 200, f"historique: {r.status_code} {r.text[:200]}")
    lignes = {l["calculation_id"]: l for l in r.json()["calculations"]}
    for quoi in ("etude", "variante"):
        _exige(etat[quoi]["calculation_id"] in lignes,
               f"{quoi} absente de l'historique apres la mise a niveau")
    origine = etat["etude"]["calculation_id"]
    variante = etat["variante"]["calculation_id"]
    _exige(lignes[variante].get("derived_from_calculation_id") == origine,
           "la ligne d'historique de la variante ne nomme plus son origine")
    _exige(lignes[origine].get("derived_from_calculation_id") is None,
           "l'etude initiale se presente comme une variante")

    #: LA REOUVERTURE: memes entrees, memes resultats, memes empreintes.
    for quoi in ("etude", "variante"):
        calcul = etat[quoi]["calculation_id"]
        relu = client.get(f"/v1/projects/{projet}/beam-verifications/{calcul}",
                          headers=entete)
        _exige(relu.status_code == 200,
               f"reouverture de {quoi}: {relu.status_code} {relu.text[:200]}")
        obtenu = _resume(relu.json())
        attendu = etat[quoi]
        for champ in sorted(attendu):
            _exige(obtenu[champ] == attendu[champ],
                   f"{quoi}: « {champ} » a change — "
                   f"avant {attendu[champ]!r}, apres {obtenu[champ]!r}")

    #: LES DOCUMENTS: les MEMES octets, pas un document recompose.
    for livrable in etat["livrables"]:
        octets = client.get(
            f"/v1/projects/{projet}/deliverables/{livrable['deliverable_id']}/download",
            headers=entete)
        _exige(octets.status_code == 200,
               f"telechargement de {livrable['kind']}: {octets.status_code}")
        recu = hashlib.sha256(octets.content).hexdigest()
        _exige(recu == livrable["sha256"],
               f"{livrable['kind']} {livrable['deliverable_id']}: "
               f"{recu[:12]} au lieu de {livrable['sha256'][:12]}")
        _exige(len(octets.content) == livrable["taille"],
               f"{livrable['kind']}: {len(octets.content)} o au lieu de {livrable['taille']}")

    print(f"verifie: 2 etudes relues a l'identique (empreintes comprises), "
          f"{len(etat['livrables'])} livrable(s) aux memes octets, filiation intacte")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("peupler", "verifier"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    (peupler if sys.argv[1] == "peupler" else verifier)(sys.argv[2])
