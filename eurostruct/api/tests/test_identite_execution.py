"""Un calcul conservé doit dire QUEL CODE l'a produit, et sous QUEL RÉFÉRENTIEL.

CE QU'``inputs_hash`` NE PROUVE PAS
-----------------------------------
``0001`` commente ``inputs_hash`` ainsi : « deux calculs de meme hash doivent
produire le meme resultat bit-a-bit ». C'est faux sous deux conditions que
cette empreinte ne porte pas :

* **le code** — ``ENGINE_VERSION`` vaut ``0.3.0`` et les six derniers commits
  la portent tous. Le contrat de versionnement le veut : un PATCH ne change
  aucun résultat, donc la version ne bouge pas. Elle est exacte et
  insuffisante ;
* **le référentiel** — une confirmation arrivée entre deux calculs change la
  valeur d'un paramètre national, donc le résultat, pour une requête
  strictement identique.

``execution_identity`` porte les trois. Deux exécutions de même identité
doivent rendre le même résultat ; deux résultats différents sous la même
identité sont un défaut qui mérite d'être cherché.

CE QUE CE FICHIER ÉTABLIT
--------------------------
1. même requête, autre build → même ``inputs_hash``, identité différente ;
2. même requête, autre instantané NDP → identité différente ;
3. un succès incomplet et un refus accompagné d'un faux résultat font un
   **rollback complet** — la ligne de calcul n'existe pas non plus ;
4. sans identité de build, la persistance refuse ; l'exploratoire reste servi.

Lancé par ``db/test/atelier_projet.sh``.
"""
from __future__ import annotations

import json
import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_ATELIER_ACTEUR_A", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason="decor absent: ce module se lance par db/test/atelier_projet.sh.",
    ),
]

ISSUER = "https://fictif.atelier.test/auth/v1"
AUDIENCE = "authenticated"
KID = "atelier-1"

PAYS = "BE"
REGION = "Wallonie"
DATE_REF = "2024-01-15"


@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _application(cle):
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    ra = ReglagesAuth(jwks_url="https://fictif.invalid/jwks", issuer=ISSUER,
                      audience=AUDIENCE, algorithmes=("RS256",),
                      tolerance_horloge_s=0)
    app = creer_application(Reglages(auth=ra, base=ReglagesBase(dsn=DSN)))
    app.state.authentificateur = AuthentificateurSupabase(
        ra, trousseau=TrousseauJwks("https://fictif.invalid/jwks",
                                    lecteur=lambda _u: {"keys": [jwk]}))
    app.state.fabrique_connexion = FabriqueConnexionPostgres(ReglagesBase(dsn=DSN))
    return app


@pytest.fixture(scope="module")
def client(cle):
    from fastapi.testclient import TestClient

    return TestClient(_application(cle))


@pytest.fixture(scope="module")
def entete(cle):
    maintenant = int(time.time())
    j = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": ACTEUR_A,
                    "iat": maintenant - 5, "nbf": maintenant - 5,
                    "exp": maintenant + 3600},
                   cle, algorithm="RS256", headers={"kid": KID})
    return {"Authorization": f"Bearer {j}"}


def _projet(client, entete, nom: str) -> str:
    r = client.post("/v1/projects", headers=entete,
                    json={"name": nom, "reference": "FICTIF-EXE",
                          "country": PAYS, "region": REGION,
                          "ndp_as_of": DATE_REF})
    assert r.status_code == 201, r.text
    return r.json()["project_id"]


def _corps(strict: bool = False) -> dict:
    return {
        "element": "P1", "strict_ndp": strict,
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 500.0, "unit": "mm"},
                    "d": {"value": 450.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 180.0, "unit": "kN*m"},
    }


def _calculer(client, entete, projet_id: str, strict: bool = False):
    return client.post(
        f"/v1/projects/{projet_id}/calculations/ec2/beam-flexure",
        json=_corps(strict), headers=entete)


# ===========================================================================
# 1. MEME REQUETE, AUTRE BUILD
# ===========================================================================
def test_meme_requete_autre_build_meme_empreinte_autre_identite(
        client, entete, monkeypatch):
    """LES DEUX EMPREINTES NE RÉPONDENT PAS À LA MÊME QUESTION.

    ``inputs_hash`` répond « est-ce la même demande ? » — et oui, elle l'est.
    ``execution_identity`` répond « est-ce la même exécution ? » — et non,
    puisque le code a changé. Les fondre ferait perdre la première question,
    qui est celle qu'un ingénieur pose en rouvrant un dossier.
    """
    projet = _projet(client, entete, "FICTIF — deux builds")

    un = _calculer(client, entete, projet)
    assert un.status_code == 201, un.text

    #: LE MEME PROCESSUS, UN AUTRE BUILD. C'est exactement ce qui se passe
    #: quand une image est reconstruite: meme version, autre code.
    monkeypatch.setenv("EUROSTRUCT_BUILD_SHA", "FICTIF-autre-build-0000001")
    deux = _calculer(client, entete, projet)
    assert deux.status_code == 201, deux.text

    a, b = un.json(), deux.json()
    assert a["inputs_hash"] == b["inputs_hash"], (
        "la requete est la meme: son empreinte doit l'etre aussi.")
    assert a["engine_version"] == b["engine_version"], (
        "la version n'a pas change — et c'est le probleme qu'on ferme.")
    assert a["engine_build_sha"] != b["engine_build_sha"]
    assert a["execution_identity"] != b["execution_identity"], (
        "deux builds distincts portent la meme identite d'execution: elle ne "
        "designe donc pas le code qui a tourne.")


def test_meme_requete_meme_build_meme_identite(client, entete):
    """L'IDENTITÉ EST STABLE, sinon elle ne sert à rien.

    Une identité qui bouge à chaque appel distinguerait tout de tout, y
    compris ce qui doit être identique — et ne permettrait plus de dire « ces
    deux calculs sont la même exécution ».
    """
    projet = _projet(client, entete, "FICTIF — identite stable")
    un = _calculer(client, entete, projet)
    deux = _calculer(client, entete, projet)
    assert (un.status_code, deux.status_code) == (201, 201)
    assert un.json()["execution_identity"] == deux.json()["execution_identity"]


# ===========================================================================
# 2. MEME REQUETE, AUTRE INSTANTANE NDP
# ===========================================================================
def test_un_autre_instantane_ndp_donne_une_autre_identite():
    """CALCULÉE DIRECTEMENT, parce que le référentiel ne se déplace pas à la demande.

    Faire arriver une confirmation entre deux calculs demanderait le cycle
    d'autorité complet — que ``decision_vers_strict.sh`` éprouve déjà. Ici on
    éprouve la PROPRIÉTÉ : l'instantané entre dans l'identité, et deux états
    du référentiel donnent deux identités.
    """
    from eurostruct_engine.ndp.execution import identite_execution

    requete = {"project_id": "p", "country": PAYS, "as_of": DATE_REF}
    commun = {"request": requete, "engine_name": "eurostruct-engine",
              "engine_version": "0.3.0", "build_sha": "FICTIF-build-0000001"}

    avant = identite_execution(
        ndp_snapshot={"country": PAYS, "confirmed": 0}, **commun)
    apres = identite_execution(
        ndp_snapshot={"country": PAYS, "confirmed": 1}, **commun)
    assert avant.digest != apres.digest, (
        "une confirmation arrivee entre deux calculs ne change pas l'identite "
        "d'execution: elle ne porte donc pas le referentiel applique, et deux "
        "resultats differents seraient indiscernables.")

    # ET SANS BUILD, ELLE REFUSE DE SE CONSTRUIRE. La fabriquer quand meme
    # produirait une valeur qui a l'air d'une preuve.
    with pytest.raises(ValueError):
        identite_execution(ndp_snapshot={}, request=requete,
                           engine_name="e", engine_version="0.3.0",
                           build_sha="")


# ===========================================================================
# 3. UN ENREGISTREMENT INCOMPLET NE LAISSE RIEN
# ===========================================================================
@pytest.mark.parametrize("cas,charge", [
    ("succes sans resultat", {"status": "succeeded", "result": None,
                              "journal": None, "verifications": None}),
    ("succes sans verification", {"status": "succeeded",
                                  "result": {"As_required": 1.0},
                                  "journal": {"title": "t", "steps": [{"s": 1}],
                                              "clauses": []},
                                  "verifications": []}),
    ("succes sans journal", {"status": "succeeded",
                             "result": {"As_required": 1.0},
                             "journal": {"title": "t", "steps": [],
                                         "clauses": []},
                             "verifications": [{"name": "x", "standard": "EN",
                                                "clause": "1",
                                                "utilisation": 0.5,
                                                "status": "pass",
                                                "acting": "a",
                                                "resisting": "r"}]}),
    ("refus portant un faux resultat", {"status": "refused",
                                        "result": {"As_required": 1.0},
                                        "journal": None,
                                        "verifications": None}),
])
def test_un_enregistrement_incoherent_fait_un_rollback_complet(cas, charge):
    """LA LIGNE DE CALCUL N'EXISTE PAS NON PLUS.

    Refuser le résultat mais garder le calcul laisserait un « succeeded » sans
    contenu : la relecture rendrait un écran vide, et personne ne saurait
    lequel des deux croire. Le refus porte sur la transaction entière.

    ``refused`` AVEC UN RÉSULTAT est le cas le plus grave : il présenterait
    comme conclu ce que le moteur a refusé de conclure.
    """
    import psycopg2

    projet_id = _projet_direct(f"FICTIF — {cas}")
    cx = psycopg2.connect(DSN)
    try:
        cur = cx.cursor()
        cur.execute("begin")
        cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                    (ACTEUR_A,))
        requete = json.dumps({"project_id": projet_id, "country": PAYS,
                              "region": REGION, "as_of": DATE_REF})
        with pytest.raises(psycopg2.Error):
            cur.execute(
                "select project_calculation_record("
                "%s::uuid, %s::calculation_status, %s, false, %s,"
                " %s::jsonb, %s::jsonb, null, %s::jsonb, %s::jsonb,"
                " %s::jsonb, %s::jsonb, %s, %s)",
                (projet_id, charge["status"], "0" * 64, "FICTIF-0.0.0",
                 requete, json.dumps({}),
                 json.dumps({"error": "x", "detail": "FICTIF"})
                 if charge["status"] == "refused" else None,
                 json.dumps(charge["result"]) if charge["result"] else None,
                 json.dumps(charge["journal"]) if charge["journal"] else None,
                 json.dumps(charge["verifications"])
                 if charge["verifications"] is not None else None,
                 "FICTIF-identite", "FICTIF-build-0000001"))
    finally:
        cx.rollback()
        cx.close()

    assert _calculs_du_projet(projet_id) == 0, (
        f"« {cas} » a laisse une ligne de calcul.")
    assert _resultats_du_projet(projet_id) == 0


# ===========================================================================
# 4. SANS IDENTITE DE BUILD, LA PERSISTANCE REFUSE
# ===========================================================================
def test_sans_identite_de_build_la_persistance_refuse(client, entete,
                                                      monkeypatch):
    """503, ET L'EXPLORATOIRE RESTE SERVI.

    Ce n'est pas l'appelant qui est en faute : le service tourne sans savoir
    quel code il exécute. Refuser d'enregistrer est la seule réponse honnête ;
    refuser aussi de calculer punirait l'ingénieur d'un défaut de déploiement.
    """
    projet = _projet(client, entete, "FICTIF — sans build")
    monkeypatch.delenv("EUROSTRUCT_BUILD_SHA", raising=False)

    r = _calculer(client, entete, projet)
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["error"] == "service_non_pret"
    assert _calculs_du_projet(projet) == 0

    # LE CALCUL EXPLORATOIRE, LUI, REPOND. Il ne pretend rien et ne survit a
    # rien: aucune ligne n'affirmera plus tard quel code l'a produit.
    exploratoire = client.post(
        "/v1/calculations/ec2/beam-flexure",
        json={"project_id": "exploratoire", "country": PAYS, **_corps()})
    assert exploratoire.status_code == 200, exploratoire.text


@pytest.mark.parametrize("valeur", ["", "   ", "unknown", "$(git rev-parse HEAD)"])
def test_une_identite_de_build_mal_formee_vaut_absence(monkeypatch, valeur):
    """CHACUNE DE CES VALEURS RESSEMBLE À UNE IDENTITÉ ET N'EN EST PAS UNE.

    Les accepter ferait enregistrer un calcul qui désigne « unknown » comme le
    code qui l'a produit — pire qu'un refus, parce que ça se lit comme une
    réponse.
    """
    from eurostruct_engine.build import BuildInconnu, identite_de_build

    monkeypatch.setenv("EUROSTRUCT_BUILD_SHA", valeur)
    with pytest.raises(BuildInconnu):
        identite_de_build()


# ===========================================================================
# OBSERVATION
# ===========================================================================
class _Observation:
    def __init__(self) -> None:
        import psycopg2

        self._cx = psycopg2.connect(DSN_OBS)
        self._cur = self._cx.cursor()

    def __enter__(self):
        return self._cur

    def __exit__(self, *_exc) -> bool:
        try:
            self._cx.rollback()
        finally:
            self._cur.close()
            self._cx.close()
        return False


def _calculs_du_projet(projet_id: str) -> int:
    with _Observation() as cur:
        cur.execute("select count(*) from calculations where project_id = %s",
                    (projet_id,))
        return int(cur.fetchone()[0])


def _resultats_du_projet(projet_id: str) -> int:
    with _Observation() as cur:
        cur.execute("select count(*) from results r join calculations c"
                    "  on c.id = r.calculation_id where c.project_id = %s",
                    (projet_id,))
        return int(cur.fetchone()[0])


def _projet_direct(nom: str) -> str:
    import psycopg2

    cx = psycopg2.connect(DSN)
    try:
        cur = cx.cursor()
        cur.execute("begin")
        cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                    (ACTEUR_A,))
        cur.execute(
            "select project_workspace_create(%s, %s, %s::country_code,"
            " %s::date, null::uuid, %s)",
            (nom, "FICTIF-EXE", PAYS, DATE_REF, REGION))
        identifiant = str(cur.fetchone()[0])
        cx.commit()
        return identifiant
    finally:
        cx.close()
