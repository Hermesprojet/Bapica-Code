"""Le parcours de travail, depuis l'API, sur un vrai PostgreSQL.

CE QUE CE MODULE ÉPROUVE
-------------------------
Les sept étapes du parcours produit, dans l'ordre où un ingénieur les fait :

  1. un utilisateur connecté voit les projets de SON organisation ;
  2. il crée un projet — nom, référence, pays, date de référence ;
  3. il le sélectionne ;
  4. il lance un calcul de flexion ;
  5. la requête exacte, le statut, la version du moteur, l'état NDP, le
     journal, les résultats et les vérifications sont enregistrés
     **atomiquement** ;
  6. après relecture complète — nouvelle connexion, nouvelle application —
     l'historique réapparaît ;
  7. le calcul sauvegardé se rouvre avec les MÊMES entrées et résultats.

Et la propriété qui vaut autant que les sept : **une autre organisation ne lit
ni ne modifie ce projet**. Le décor pose deux organisations disjointes et deux
identités, chacune avec son jeton signé.

AUCUN PROVIDER MÉMOIRE NE PEUT CONSTITUER CETTE PREUVE
--------------------------------------------------------
Un provider mémoire prouverait que l'application appelle ce qu'elle croit
appeler. Il ne prouverait rien sur le cloisonnement — qui est dans les
politiques RLS — ni sur l'atomicité — qui est dans une transaction PostgreSQL.
La chaîne traversée ici est celle de l'exploitation :

    jeton Bearer brut
      -> AuthentificateurSupabase (signature réellement vérifiée)
      -> ContexteAuthentifie
      -> creer_atelier_de_production
      -> transaction PostgreSQL explicite
      -> SET LOCAL eurostruct.actor_id
      -> primitive SECURITY DEFINER
      -> RLS
      -> commit / rollback

CE QUI N'EST PAS UN SUPABASE RÉEL
----------------------------------
Le trousseau JWKS est local et les clés sont générées en mémoire. La
vérification est celle de production ; l'origine des clés ne l'est pas.
``SUPABASE_UNVERIFIED`` reste vrai.

Lancé par ``db/test/atelier_projet.sh``, qui pose le décor et fournit la DSN
par l'environnement — jamais en argument, donc jamais visible dans ``ps``.
"""
from __future__ import annotations

import json
import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
#: DSN D'OBSERVATION SEULEMENT. Le login de service n'a aucun privilege de
#: table: prouver qu'une transaction interrompue n'a RIEN laisse demande de
#: regarder les tables. Aucune route ne voit cette DSN.
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_ATELIER_ACTEUR_A", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_ATELIER_ACTEUR_B", "")
ORG_A = os.environ.get("EUROSTRUCT_ATELIER_ORG_A", "")
ORG_B = os.environ.get("EUROSTRUCT_ATELIER_ORG_B", "")

#: ON SAUTE PAR MARQUEUR, PAS AU NIVEAU DU MODULE: `skip(allow_module_level)`
#: empeche la COLLECTE, et `run_tests.sh` compare collectes et executes
#: precisement pour reperer les cas qui disparaissent.
DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A and ACTEUR_B and ORG_A and ORG_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par db/test/atelier_projet.sh, "
                "qui pose la base deployee, les deux organisations, et fournit "
                "les DSN par l'environnement."),
    ),
]

ISSUER = "https://fictif.atelier.test/auth/v1"
AUDIENCE = "authenticated"
KID = "atelier-1"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _construire_application(cle):
    """Une application NEUVE, avec sa propre fabrique de connexion.

    APPELEE DEUX FOIS, ET C'EST TOUT L'INTERET. L'etape 6 du parcours —
    « apres rechargement complet, l'historique reapparait » — n'est pas
    eprouvee par un second appel sur la meme application: le cache de la
    couche, les connexions ouvertes et l'etat en memoire survivraient. Une
    seconde application, construite de zero, est ce qui ressemble a un F5.
    """
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from jwt.algorithms import RSAAlgorithm

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
    return app


@pytest.fixture(scope="module")
def client(cle):
    from fastapi.testclient import TestClient

    return TestClient(_construire_application(cle))


@pytest.fixture()
def client_neuf(cle):
    """Une application entierement reconstruite. C'est le rechargement."""
    from fastapi.testclient import TestClient

    return TestClient(_construire_application(cle))


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


def _requete_de_calcul(strict: bool = False) -> dict:
    """Une poutre FICTIVE, mais dimensionnellement crédible.

    ``strict_ndp=False`` par defaut: aucun parametre national belge n'est
    confirme sur cette base neuve, et le mode strict refuserait — ce qui est
    le comportement JUSTE, et fait l'objet de son propre cas.

    ``project_id`` EST DELIBEREMENT FAUX ICI. La route doit l'ecraser par
    l'identifiant du chemin: si elle ne le faisait pas, la note porterait un
    projet different de celui ou elle est enregistree, et le cas
    `test_le_project_id_du_corps_ne_survit_pas` le verrait.
    """
    return {
        "project_id": "DEMO-001",
        "element": "P1",
        "country": "BE",
        "strict_ndp": strict,
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 500.0, "unit": "mm"},
                    "d": {"value": 450.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 180.0, "unit": "kN*m"},
    }


def _projet_neuf(client, jeton, acteur: str, nom: str) -> dict:
    corps = {"name": nom, "reference": "FICTIF-REF-01", "country": "BE",
             "ndp_as_of": "2024-01-15"}
    r = client.post("/v1/projects", json=corps, headers=_entete(jeton(acteur)))
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# 1 a 3 — VOIR, CREER, SELECTIONNER
# ===========================================================================
def test_un_utilisateur_connecte_voit_les_projets_de_son_organisation(
        client, jeton):
    """Et la liste est une LISTE, pas un refus. Le parcours commence ici."""
    r = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["projects"], list)


def test_sans_identite_l_atelier_ne_montre_rien(client):
    """Un projet nomme un client et une adresse: ce n'est pas public."""
    r = client.get("/v1/projects")
    assert r.status_code == 401, r.text
    assert "projects" not in r.json()


def test_bearer_nimporte_quoi_n_obtient_aucun_projet(client):
    """La meme frontiere que sur le chemin d'autorite, et pour la meme raison."""
    r = client.get("/v1/projects",
                   headers={"Authorization": "Bearer nimporte-quoi"})
    assert r.status_code == 401, r.text
    assert "projects" not in r.json()


def test_creer_un_projet_le_rend_immediatement_visible(client, jeton):
    """CREE PUIS RELU, dans la meme requete.

    Rendre l'identifiant seul obligerait l'ecran a un second appel, et a
    construire le projet de son cote en attendant — donc a afficher des champs
    que la base n'a pas confirmes.
    """
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — Halle A")
    assert projet["name"] == "FICTIF — Halle A"
    assert projet["reference"] == "FICTIF-REF-01"
    assert projet["country"] == "BE"
    assert projet["ndp_as_of"] == "2024-01-15"
    assert projet["organization_id"] == ORG_A
    assert projet["organization_name"]
    assert projet["calculation_count"] == 0

    r = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_A)))
    assert projet["project_id"] in {p["project_id"] for p in r.json()["projects"]}


def test_aucun_org_id_du_client_n_est_cru(client, jeton):
    """A NOMME L'ORGANISATION DE B. La base refuse, et ne dit pas pourquoi.

    Distinguer « organisation inexistante » de « vous n'en etes pas membre »
    donnerait un oracle d'existence a qui essaie des uuid.
    """
    corps = {"name": "FICTIF — tentative", "country": "BE",
             "ndp_as_of": "2024-01-15", "organization_id": ORG_B}
    r = client.post("/v1/projects", json=corps, headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert "organisation" in r.text.lower()

    # ET RIEN N'A ETE ECRIT. La transaction a fait rollback en entier.
    assert _compter_projets_de(ORG_B) == 0


def test_une_date_de_reference_sans_referentiel_est_refusee(client, jeton):
    """Aucun jeu d'annexes publie avant cette date: on refuse, on n'approche pas.

    Prendre « le plus proche » inventerait un referentiel — interdiction n° 2.
    """
    corps = {"name": "FICTIF — trop tot", "country": "BE",
             "ndp_as_of": "1990-01-01"}
    r = client.post("/v1/projects", json=corps, headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert "annexe nationale" in r.text.lower()


# ===========================================================================
# 4 et 5 — CALCULER, ENREGISTRER ATOMIQUEMENT
# ===========================================================================
def test_un_calcul_enregistre_porte_tout_ce_qui_permet_de_le_relire(
        client, jeton):
    """La requete exacte, le statut, la version, l'etat NDP, le journal,
    les resultats ET les verifications. En une fois."""
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — Halle calcul")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    calcul = r.json()

    assert calcul["status"] == "succeeded"
    assert calcul["strict_ndp"] is False
    assert calcul["engine_version"]
    assert len(calcul["inputs_hash"]) == 64
    assert calcul["request"]["element"] == "P1"
    assert calcul["ndp_snapshot"] is not None
    assert calcul["result"], "aucun resultat enregistre"
    assert calcul["journal"], "aucun journal enregistre"
    assert calcul["verifications"], "aucune verification enregistree"
    # LA MENTION OBLIGATOIRE ACCOMPAGNE LE CALCUL, comme sur la route
    # exploratoire: aucun logiciel ne signe une note.
    assert "ingenieur" in calcul["notice"].lower() \
        or "ingénieur" in calcul["notice"].lower()
    # ET LA MENTION CONDITIONNELLE, puisque ce calcul est exploratoire.
    assert calcul["mention"] == "PROJET — NON SIGNABLE"

    # LES QUATRE TABLES ONT ETE ECRITES, ET ON LE CONSTATE EN BASE.
    with _observer() as cur:
        cur.execute(
            "select c.status, c.request is not null,"
            "       c.ndp_snapshot is not null,"
            "       (select count(*) from results r"
            "         where r.calculation_id = c.id),"
            "       (select count(*) from results r"
            "          join verifications v on v.result_id = r.id"
            "         where r.calculation_id = c.id)"
            "  from calculations c where c.id = %s",
            (calcul["calculation_id"],))
        statut, a_requete, a_ndp, nb_res, nb_ver = cur.fetchone()
    assert statut == "succeeded"
    assert a_requete and a_ndp
    assert nb_res == 1, f"{nb_res} resultat(s): l'ecriture n'est pas complete"
    assert nb_ver >= 1, "aucune verification: le calcul est enregistre a moitie"


def test_le_project_id_du_corps_ne_survit_pas(client, jeton):
    """« DEMO-001 » N'A PLUS AUCUN EFFET.

    Le champ `project_id` de la requete moteur est un libelle de note. La route
    l'ecrase par l'identifiant du chemin AVANT le calcul: sans cela, une note
    porterait un projet different de celui ou elle est enregistree.
    """
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — libelle")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    assert r.json()["request"]["project_id"] == projet["project_id"]
    assert "DEMO-001" not in r.text


def test_un_refus_strict_est_enregistre_comme_refus(client, jeton):
    """LE CAS QUI COMPTE LE PLUS POUR UN AUDIT.

    Aucun parametre national belge n'est confirme sur cette base: le mode
    strict refuse, et c'est le comportement JUSTE. Ce refus doit apparaitre
    dans l'historique en tant que refus — ni omis, ni degrade en echec
    technique, et surtout jamais range en succes.
    """
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — refus strict")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(strict=True), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text

    h = client.get(f"/v1/projects/{projet['project_id']}/calculations",
                   headers=_entete(jeton(ACTEUR_A)))
    assert h.status_code == 200, h.text
    lignes = h.json()["calculations"]
    assert len(lignes) == 1, "le refus n'est pas dans l'historique"
    assert lignes[0]["status"] == "refused"
    assert lignes[0]["strict_ndp"] is True
    # AUCUNE VERIFICATION: le moteur n'a rien conclu, et `0.0` se lirait
    # « largement verifie » la ou rien ne l'a ete.
    assert lignes[0]["max_utilisation"] is None

    relu = client.get(
        f"/v1/projects/{projet['project_id']}/calculations/"
        f"{lignes[0]['calculation_id']}", headers=_entete(jeton(ACTEUR_A)))
    assert relu.status_code == 200, relu.text
    assert relu.json()["refusal"], "le refus est enregistre sans son motif"
    assert relu.json()["result"] is None


def test_un_projet_d_une_autre_organisation_refuse_le_calcul(client, jeton):
    """B TENTE D'ECRIRE DANS LE PROJET DE A. Rien n'est ecrit."""
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — isolation ecriture")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 422, r.text

    with _observer() as cur:
        cur.execute("select count(*) from calculations where project_id = %s",
                    (projet["project_id"],))
        assert cur.fetchone()[0] == 0, "un calcul a ete ecrit par une autre org"


# ===========================================================================
# 6 et 7 — RECHARGER, ROUVRIR
# ===========================================================================
def test_apres_rechargement_complet_l_historique_reapparait(
        client, client_neuf, jeton):
    """L'APPLICATION EST RECONSTRUITE DE ZERO. C'est ce qui ressemble a un F5.

    Un second appel sur la meme application ne prouverait rien: le cache de la
    couche et les connexions ouvertes survivraient.
    """
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — persistance")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    avant = r.json()

    # --- RECHARGEMENT ------------------------------------------------------
    liste = client_neuf.get("/v1/projects", headers=_entete(jeton(ACTEUR_A)))
    assert liste.status_code == 200, liste.text
    vu = [p for p in liste.json()["projects"]
          if p["project_id"] == projet["project_id"]]
    assert vu, "le projet a disparu apres rechargement"
    assert vu[0]["calculation_count"] == 1

    h = client_neuf.get(f"/v1/projects/{projet['project_id']}/calculations",
                        headers=_entete(jeton(ACTEUR_A)))
    assert h.status_code == 200, h.text
    assert [c["calculation_id"] for c in h.json()["calculations"]] \
        == [avant["calculation_id"]]


def test_le_calcul_rouvert_porte_les_memes_entrees_et_les_memes_resultats(
        client, client_neuf, jeton):
    """LE CAS DECISIF DU PARCOURS.

    Rouvrir ne recalcule rien: relancer le moteur rendrait le resultat
    d'aujourd'hui pour un calcul d'hier — avec le code d'aujourd'hui, et
    l'etat d'aujourd'hui du referentiel national. La comparaison est EXACTE,
    champ par champ.
    """
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — reouverture")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    avant = r.json()

    relu = client_neuf.get(
        f"/v1/projects/{projet['project_id']}/calculations/"
        f"{avant['calculation_id']}", headers=_entete(jeton(ACTEUR_A)))
    assert relu.status_code == 200, relu.text
    apres = relu.json()

    assert apres["request"] == avant["request"], "les entrees ont bouge"
    assert apres["result"] == avant["result"], "les resultats ont bouge"
    assert apres["journal"] == avant["journal"], "le journal a bouge"
    assert apres["verifications"] == avant["verifications"]
    assert apres["inputs_hash"] == avant["inputs_hash"]
    assert apres["engine_version"] == avant["engine_version"]
    assert apres["ndp_snapshot"] == avant["ndp_snapshot"]
    # ET LA MENTION SUIT LE CALCUL, pas l'ecran: un calcul exploratoire rouvert
    # six mois plus tard reste exploratoire.
    assert apres["mention"] == "PROJET — NON SIGNABLE"


# ===========================================================================
# L'ISOLATION, EN LECTURE
# ===========================================================================
def test_une_autre_organisation_ne_voit_pas_le_projet(client, jeton):
    """B NE VOIT RIEN DE A, ni dans sa liste, ni en le nommant."""
    projet = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — isolation lecture")
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    calcul_id = r.json()["calculation_id"]

    liste = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_B)))
    assert liste.status_code == 200, liste.text
    assert projet["project_id"] not in {p["project_id"]
                                        for p in liste.json()["projects"]}

    for chemin in (f"/v1/projects/{projet['project_id']}/calculations",
                   f"/v1/projects/{projet['project_id']}/calculations/{calcul_id}"):
        refus = client.get(chemin, headers=_entete(jeton(ACTEUR_B)))
        assert refus.status_code == 422, (chemin, refus.text)
        # LE REFUS NE DIT PAS CE QU'IL CACHE. Ni le nom du projet, ni son
        # organisation: un message trop precis est un oracle.
        assert "FICTIF — isolation lecture" not in refus.text
        assert ORG_A not in refus.text


def test_le_calcul_d_un_projet_ne_se_lit_pas_depuis_un_autre(client, jeton):
    """DEUX PROJETS DE LA MEME ORGANISATION restent distincts.

    Le cloisonnement par organisation ne suffit pas: nommer le calcul de l'un
    depuis l'autre ferait apparaitre dans un dossier des nombres calcules pour
    un autre ouvrage.
    """
    un = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — projet un")
    deux = _projet_neuf(client, jeton, ACTEUR_A, "FICTIF — projet deux")
    r = client.post(
        f"/v1/projects/{un['project_id']}/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(), headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    calcul_id = r.json()["calculation_id"]

    croise = client.get(
        f"/v1/projects/{deux['project_id']}/calculations/{calcul_id}",
        headers=_entete(jeton(ACTEUR_A)))
    assert croise.status_code == 422, croise.text


# ===========================================================================
# OBSERVATION — jamais le chemin du produit
# ===========================================================================
class _Observation:
    """Un curseur de lecture seule, sur la DSN d'observation."""

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


def _compter_projets_de(org_id: str) -> int:
    with _observer() as cur:
        cur.execute("select count(*) from projects where org_id = %s", (org_id,))
        return int(cur.fetchone()[0])
