"""Le PROJET détermine le référentiel. Le corps de la requête ne le peut pas.

LE DÉFAUT, ET POURQUOI IL EST GRAVE
------------------------------------
Un projet porte ``country``, ``region`` et ``ndp_as_of`` : ensemble, ils
désignent l'édition d'Annexe Nationale en vigueur, donc les valeurs qui
entreront dans les formules. La route d'enregistrement ne remplaçait que
``project_id``. Le reste du contexte normatif venait du corps :

* ``country`` — un projet belge pouvait recevoir un calcul français ;
* ``region`` — jamais transmise, jamais figée ;
* ``as_of`` — absente de l'interface, donc **la date du jour** côté moteur.

Et PostgreSQL, lui, écrivait ``calculations.ndp_as_of`` depuis le PROJET. La
ligne enregistrée affirmait donc une date que le calcul n'avait pas utilisée.
Deux vérités dans la même transaction, dont une fausse — et c'est la ligne en
base qu'un audit lit des années plus tard.

CE QUE CE FICHIER ÉTABLIT
--------------------------
1. le contexte normatif de la requête moteur vient EXCLUSIVEMENT du projet ;
2. un corps qui prétend le contraire est refusé par le contrat, pas absorbé ;
3. ``request.country``, ``request.region``, ``request.as_of``,
   ``calculations.ndp_as_of`` et ``ndp_snapshot`` disent la même chose ;
4. la garantie ne dépend pas de la route : ``project_calculation_record``
   refuse elle-même une requête dont le contexte contredit le projet.

Le point 4 est le seul qui tienne si quelqu'un ajoute demain une seconde route
d'enregistrement. Une frontière qui n'existe que dans un adaptateur HTTP n'est
pas une frontière : c'est une convention.

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
ORG_A = os.environ.get("EUROSTRUCT_ATELIER_ORG_A", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A and ORG_A)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par db/test/atelier_projet.sh, "
                "qui pose la base deployee et les deux organisations."),
    ),
]

ISSUER = "https://fictif.atelier.test/auth/v1"
AUDIENCE = "authenticated"
KID = "atelier-1"

#: LE PROJET DE REFERENCE DE CE FICHIER. Belge, wallon, fige au 15/01/2024.
#: Les trois valeurs sont distinctes de tout defaut plausible — « FR », une
#: autre region, et la date du jour — pour qu'une substitution se VOIE.
PAYS_PROJET = "BE"
REGION_PROJET = "Wallonie"
DATE_PROJET = "2024-01-15"

#: CE QU'UN CLIENT MALVEILLANT — OU DISTRAIT — TENTERAIT.
PAYS_INTRUS = "FR"
REGION_INTRUSE = "Ile-de-France"
DATE_INTRUSE = "2030-01-01"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def client(cle):
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from fastapi.testclient import TestClient
    from jwt.algorithms import RSAAlgorithm

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
    return TestClient(app)


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str) -> str:
        maintenant = int(time.time())
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + 3600},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


def _projet(client, jeton, nom: str) -> dict:
    """Un projet BE / Wallonie / 2024-01-15."""
    r = client.post("/v1/projects", headers=_entete(jeton(ACTEUR_A)),
                    json={"name": nom, "reference": "FICTIF-CTX",
                          "country": PAYS_PROJET, "region": REGION_PROJET,
                          "ndp_as_of": DATE_PROJET})
    assert r.status_code == 201, r.text
    return r.json()


def _corps_de_calcul(**extra) -> dict:
    """Le corps du calcul de projet. Il ne nomme AUCUN contexte normatif."""
    corps = {
        "element": "P1",
        "strict_ndp": False,
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 500.0, "unit": "mm"},
                    "d": {"value": 450.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 180.0, "unit": "kN*m"},
    }
    corps.update(extra)
    return corps


def _calculer(client, jeton, projet_id: str, **extra):
    return client.post(
        f"/v1/projects/{projet_id}/calculations/ec2/beam-flexure",
        json=_corps_de_calcul(**extra), headers=_entete(jeton(ACTEUR_A)))


# ===========================================================================
# 1. LE CAS DECISIF: LE CORPS NE PEUT PAS SUBSTITUER UN AUTRE REFERENTIEL
# ===========================================================================
def test_un_corps_qui_nomme_un_autre_pays_est_refuse(client, jeton):
    """ROUGE AUJOURD'HUI: le calcul est ACCEPTE, et il est francais.

    Le projet est belge. Le corps annonce « FR ». La route ne remplace que
    ``project_id``, si bien que le moteur charge le referentiel FRANCAIS et
    que la ligne enregistree porte pourtant la date du projet BELGE.

    Le refus attendu est **422**: le contrat du calcul de projet ne porte pas
    de champ ``country``, et `Strict` interdit les champs supplementaires. Un
    client qui en envoie un obtient une reponse, pas un effet silencieux.
    """
    projet = _projet(client, jeton, "FICTIF — substitution de pays")
    r = _calculer(client, jeton, projet["project_id"], country=PAYS_INTRUS)
    assert r.status_code == 422, (
        f"un corps annoncant « {PAYS_INTRUS} » sur un projet "
        f"« {PAYS_PROJET} » obtient {r.status_code}: le referentiel du calcul "
        "ne vient pas du projet.")
    # ET RIEN N'A ETE ECRIT. Un refus qui laisserait une ligne serait pire
    # qu'une acceptation: l'historique porterait un calcul sans reponse.
    assert _calculs_du_projet(projet["project_id"]) == 0


def test_un_corps_qui_nomme_une_autre_region_est_refuse(client, jeton):
    """La region change les parametres nationaux: Wallonie n'est pas Flandre."""
    projet = _projet(client, jeton, "FICTIF — substitution de region")
    r = _calculer(client, jeton, projet["project_id"], region=REGION_INTRUSE)
    assert r.status_code == 422, r.text
    assert _calculs_du_projet(projet["project_id"]) == 0


def test_un_corps_qui_nomme_une_autre_date_est_refuse(client, jeton):
    """LA DATE EST CE QUI CHOISIT L'EDITION EN VIGUEUR.

    Une requete datee de 2030 sur un projet fige en 2024 citerait une annexe
    que le dossier ne connait pas — et PostgreSQL enregistrerait quand meme
    `ndp_as_of` = 2024.
    """
    projet = _projet(client, jeton, "FICTIF — substitution de date")
    r = _calculer(client, jeton, projet["project_id"], as_of=DATE_INTRUSE)
    assert r.status_code == 422, r.text
    assert _calculs_du_projet(projet["project_id"]) == 0


def test_un_corps_qui_nomme_un_project_id_est_refuse(client, jeton):
    """« DEMO-001 » n'est plus ECRASE: il est REFUSE.

    Ecraser marche tant qu'une seule route existe. Refuser dit au client que
    son champ n'a aucun effet, au lieu de le lui laisser croire.
    """
    projet = _projet(client, jeton, "FICTIF — project_id dans le corps")
    r = _calculer(client, jeton, projet["project_id"], project_id="DEMO-001")
    assert r.status_code == 422, r.text


# ===========================================================================
# 2. CE QUI EST ENREGISTRE DIT LA MEME CHOSE QUE LE PROJET
# ===========================================================================
def test_le_contexte_enregistre_vient_du_projet_et_de_lui_seul(client, jeton):
    """Cinq champs, une seule vérité.

    ``request.country``, ``request.region``, ``request.as_of``,
    ``calculations.ndp_as_of`` et l'instantane NDP doivent tous designer le
    referentiel du projet. C'est l'invariant que la substitution brisait en
    silence.
    """
    projet = _projet(client, jeton, "FICTIF — contexte coherent")
    r = _calculer(client, jeton, projet["project_id"])
    assert r.status_code == 201, r.text
    calcul = r.json()

    requete = calcul["request"]
    assert requete["project_id"] == projet["project_id"]
    assert requete["country"] == PAYS_PROJET
    assert requete["region"] == REGION_PROJET
    assert requete["as_of"] == DATE_PROJET, (
        "la requete moteur n'est pas datee du projet: le moteur a resolu "
        "l'edition en vigueur a une autre date que celle du dossier.")

    # LA LIGNE EN BASE DIT LA MEME CHOSE. C'est elle qu'un audit lit.
    with _observer() as cur:
        cur.execute(
            "select c.ndp_as_of::text, c.request->>'country',"
            "       c.request->>'region', c.request->>'as_of',"
            "       c.ndp_snapshot->>'country'"
            "  from calculations c where c.id = %s",
            (calcul["calculation_id"],))
        as_of, pays, region, req_as_of, ndp_pays = cur.fetchone()
    assert as_of == DATE_PROJET
    assert pays == PAYS_PROJET
    assert region == REGION_PROJET
    assert req_as_of == DATE_PROJET
    # L'INSTANTANE NDP EST CELUI DU PAYS DU PROJET. S'il portait « FR », le
    # calcul aurait applique des valeurs francaises sous une date belge.
    assert ndp_pays in (None, PAYS_PROJET), (
        f"l'instantane NDP annonce « {ndp_pays} » pour un projet "
        f"« {PAYS_PROJET} »")


def test_le_corps_enregistre_est_celui_envoye_au_moteur(client, jeton):
    """OCTET POUR OCTET.

    Enregistrer une requete RECONSTRUITE apres coup laisserait diverger ce que
    le moteur a calcule et ce que la note affichera. La seule facon de le
    garantir est que la requete enregistree soit l'objet meme qui a servi:
    on le constate en recalculant son empreinte.
    """
    import hashlib

    projet = _projet(client, jeton, "FICTIF — corps identique")
    r = _calculer(client, jeton, projet["project_id"])
    assert r.status_code == 201, r.text
    calcul = r.json()

    canonique = json.dumps(calcul["request"], sort_keys=True,
                           ensure_ascii=False, separators=(",", ":"))
    attendue = hashlib.sha256(canonique.encode("utf-8")).hexdigest()
    assert calcul["inputs_hash"] == attendue, (
        "l'empreinte enregistree ne correspond pas a la requete enregistree: "
        "l'une des deux a ete reconstruite.")


def test_la_region_du_projet_est_lisible(client, jeton):
    """Elle est saisie, figee, et RENDUE. Une region non relue n'existe pas.

    ``projects.region`` existait depuis 0001 et aucune primitive ne l'ecrivait
    ni ne la lisait: l'ecran ne pouvait donc ni la saisir, ni la verifier.
    """
    projet = _projet(client, jeton, "FICTIF — region lisible")
    assert projet["region"] == REGION_PROJET

    liste = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_A)))
    assert liste.status_code == 200, liste.text
    revu = [p for p in liste.json()["projects"]
            if p["project_id"] == projet["project_id"]]
    assert revu and revu[0]["region"] == REGION_PROJET


# ===========================================================================
# 3. LA GARANTIE N'EST PAS DANS LA ROUTE
# ===========================================================================
def test_la_primitive_refuse_elle_meme_un_contexte_qui_contredit_le_projet():
    """LE CAS QUI TIENT SI QUELQU'UN AJOUTE UNE SECONDE ROUTE.

    On appelle `project_calculation_record` DIRECTEMENT, sous le login de
    service et l'acteur pose, avec une requete dont le pays contredit le
    projet. La primitive doit refuser — sans quoi la frontiere n'existe que
    dans un adaptateur HTTP, c'est-a-dire nulle part.

    ON N'EMPRUNTE PAS LA ROUTE ICI, ET C'EST TOUT L'INTERET: la route ne peut
    pas produire ce corps-la. Un attaquant qui atteindrait la base, lui, le
    pourrait.
    """
    import psycopg2

    projet_id = _projet_direct("FICTIF — postcondition SQL")
    cx = psycopg2.connect(DSN)
    try:
        cur = cx.cursor()
        cur.execute("begin")
        cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                    (ACTEUR_A,))
        requete = json.dumps({"project_id": projet_id, "country": PAYS_INTRUS,
                              "region": REGION_INTRUSE, "as_of": DATE_INTRUSE,
                              "element": "P1"})
        with pytest.raises(psycopg2.Error) as refus:
            cur.execute(
                # UNE IDENTITE DE BUILD VALIDE EST FOURNIE, et c'est
                # necessaire: sans elle, la garde de build repondrait la
                # premiere — a juste titre — et ce cas n'eprouverait plus le
                # contexte normatif qu'il vise.
                "select project_calculation_record("
                "%s::uuid, 'succeeded'::calculation_status, %s, false, %s,"
                " %s::jsonb, %s::jsonb, null, null, %s::jsonb, %s::jsonb,"
                " %s::jsonb, %s, %s)",
                (projet_id, "0" * 64, "FICTIF-0.0.0", requete,
                 json.dumps({"country": PAYS_INTRUS}),
                 json.dumps({"As_required": {"value": 1.0, "unit": "mm**2"}}),
                 json.dumps({"title": "t", "steps": [{"s": 1}], "clauses": []}),
                 json.dumps([{"name": "x", "standard": "EN",
                              "clause": "1", "utilisation": 0.5,
                              "status": "pass", "acting": "a",
                              "resisting": "r"}]),
                 "FICTIF-identite-0000001", "FICTIF-build-0000001"))
        message = str(refus.value).lower()
        assert "contexte" in message or "projet" in message, (
            f"la primitive a refuse pour une autre raison: {refus.value}")
    finally:
        cx.rollback()
        cx.close()

    assert _calculs_du_projet(projet_id) == 0


# ===========================================================================
# OBSERVATION — jamais le chemin du produit
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


def _observer() -> _Observation:
    return _Observation()


def _calculs_du_projet(projet_id: str) -> int:
    with _observer() as cur:
        cur.execute("select count(*) from calculations where project_id = %s",
                    (projet_id,))
        return int(cur.fetchone()[0])


def _projet_direct(nom: str) -> str:
    """Un projet cree par la PRIMITIVE, sans passer par la route.

    Le cas de postcondition SQL n'a pas de client HTTP: il lui faut quand meme
    un projet reel, avec son contexte normatif fige.
    """
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
            (nom, "FICTIF-CTX", PAYS_PROJET, DATE_PROJET, REGION_PROJET))
        identifiant = str(cur.fetchone()[0])
        cx.commit()
        return identifiant
    finally:
        cx.close()
