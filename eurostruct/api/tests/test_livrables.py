"""Du brouillon à l'émission, par les routes réelles, sur un vrai PostgreSQL.

LE DÉFAUT PRODUIT QUE CE MODULE FERME
--------------------------------------
La machine à états ``draft → review → validated → final`` existait en base
depuis longtemps, avec ses transitions interdites, sa chaîne de révisions, son
journal, et l'exigence qu'un signataire soit membre **actif** et porteur du
rôle de validation. **Rien n'y accédait.** Le backend authentifié n'atteint que
les fonctions qu'on lui déclare, et aucune ne touchait ``deliverables`` ni
``validations``. Mesure du jour, avant ce lot : toute route de livrable rendait
**404**.

CE QUE CE MODULE ÉPROUVE
-------------------------
Le parcours entier, dans l'ordre où un bureau d'études le fait, plus tous les
refus qui le bordent. La chaîne traversée est celle de l'exploitation :

    jeton Bearer brut
      -> AuthentificateurSupabase (signature réellement vérifiée)
      -> transaction PostgreSQL explicite
      -> SET LOCAL eurostruct.actor_id
      -> primitive SECURITY DEFINER
      -> machine à états et déclencheurs
      -> RLS
      -> magasin d'objets réel, relu avant d'être promis

LES COMPTES SONT EXPLICITEMENT FICTIFS
----------------------------------------
``FICTIF Ing. V (compte de test)`` vit dans une base jetable détruite à la fin
du harnais. **Aucune attestation produite ici n'est une validation réelle.**
Le registre national reste à 0/29, la mention « PROJET — NON SIGNABLE » reste
vraie de tout calcul non strict, et ``SUPABASE_UNVERIFIED`` reste vrai.

CE QUE LE PRODUIT ENREGISTRE, ET COMMENT IL LE NOMME
------------------------------------------------------
Une **attestation métier authentifiée**, jamais une signature électronique
qualifiée. Le nom est le même ici, dans PostgreSQL, dans l'API et à l'écran.

Lancé par ``db/test/livrable_validation.sh``, qui pose le décor — deux
organisations, six adhésions aux rôles distincts, la racine d'autorité, les
habilitations du quatre-yeux et un magasin d'objets réel — et fournit les DSN
par l'environnement, jamais en argument, donc jamais visibles dans ``ps``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_A", "")
ACTEUR_V = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_V", "")
ACTEUR_W = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_W", "")
ACTEUR_D = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_D", "")
ACTEUR_N = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_N", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_LIVRABLE_ACTEUR_B", "")
ORG_A = os.environ.get("EUROSTRUCT_LIVRABLE_ORG_A", "")
ORG_B = os.environ.get("EUROSTRUCT_LIVRABLE_ORG_B", "")
MAGASIN = os.environ.get("EUROSTRUCT_STORAGE_DIR", "")

#: ON SAUTE PAR MARQUEUR, PAS AU NIVEAU DU MODULE: `skip(allow_module_level)`
#: empeche la COLLECTE, et `run_tests.sh` compare collectes et executes
#: precisement pour reperer les cas qui disparaissent.
DECOR_PRESENT = bool(DSN and DSN_OBS and MAGASIN and ACTEUR_A and ACTEUR_V
                     and ACTEUR_W and ACTEUR_D and ACTEUR_N and ACTEUR_B
                     and ORG_A and ORG_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/livrable_validation.sh, qui pose la base deployee, "
                "les six adhesions, la racine d'autorite et le magasin "
                "d'objets, et fournit les DSN par l'environnement."),
    ),
]

ISSUER = "https://fictif.livrable.test/auth/v1"
AUDIENCE = "authenticated"
KID = "livrable-1"
PAYS = "BE"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _construire_application(cle):
    """Une application NEUVE, avec sa propre fabrique de connexion.

    APPELÉE PLUSIEURS FOIS, ET C'EST TOUT L'INTÉRÊT. « Après rechargement
    complet, les mêmes octets reviennent » n'est pas éprouvé par un second
    appel sur la même application : caches, connexions ouvertes et état en
    mémoire survivraient. Une seconde application construite de zéro est ce
    qui ressemble à un F5.
    """
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
    return app


@pytest.fixture(scope="module")
def client(cle):
    from fastapi.testclient import TestClient

    return TestClient(_construire_application(cle))


@pytest.fixture()
def client_neuf(cle):
    """Une application entièrement reconstruite. C'est le rechargement."""
    from fastapi.testclient import TestClient

    return TestClient(_construire_application(cle))


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str, *, duree: int = 3600) -> str:
        maintenant = int(time.time())
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + duree},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


# ------------------------------------------------------------------ décor SQL
def _observer(requete: str, parametres: tuple = ()):
    """Une lecture directe, hors du produit. Pour CONSTATER, jamais pour agir.

    Le login de service n'a aucun privilège de table : prouver qu'un refus n'a
    **rien** écrit demande de regarder les tables, ce que le service ne peut
    pas faire. Aucune route ne voit cette DSN.
    """
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(requete, parametres)
            return curseur.fetchall()
    finally:
        connexion.close()


def _refus_de_la_primitive(sql: str, parametres: tuple,
                           acteur: str | None = None) -> str:
    """Appelle une primitive DIRECTEMENT et rend le message de son refus.

    ON N'EMPRUNTE AUCUNE ROUTE ICI, ET C'EST TOUT L'INTÉRÊT. Une garde
    applicative rend un message utilisable ; la frontière, elle, est dans la
    primitive. Un attaquant qui atteindrait la base ne passerait pas par
    FastAPI, et c'est ce chemin-là qu'il faut éprouver.
    """
    import psycopg2

    cx = psycopg2.connect(DSN)
    try:
        cur = cx.cursor()
        cur.execute("begin")
        cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                    (acteur or ACTEUR_A,))
        with pytest.raises(psycopg2.Error) as refus:
            cur.execute(sql, parametres)
        return str(refus.value).lower()
    finally:
        cx.rollback()
        cx.close()


# ------------------------------------------------------- ouvrir le mode strict
def _requete_de_calcul(strict: bool) -> dict:
    """Une poutre FICTIVE, mais dimensionnellement crédible.

    LE CORPS NE NOMME AUCUN RÉFÉRENTIEL. Ni ``project_id``, ni ``country``, ni
    ``region``, ni ``as_of`` : les quatre sont figés sur le projet, et le
    contrat du calcul de projet les refuse.
    """
    return {
        "element": "P1",
        "strict_ndp": strict,
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 500.0, "unit": "mm"},
                    "d": {"value": 450.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 180.0, "unit": "kN*m"},
    }


def _parametre(cle_regle: str):
    from eurostruct_engine.ndp import load_parameter_set

    jeu = load_parameter_set(PAYS, strict=True)
    p = jeu.find(cle_regle)
    assert p is not None, f"{cle_regle} absent du registre"
    return p


def _blocages(client) -> list[str]:
    """Les clés que le mode strict refuse, telles que l'API les rend."""
    r = client.post("/v1/calculations/ec2/beam-flexure",
                    json={"project_id": "FICTIF-LIV", "country": PAYS,
                          **_requete_de_calcul(strict=True)})
    if r.status_code == 200:
        return []
    assert r.status_code == 422, r.text
    preflight = r.json().get("preflight") or {}
    return [b["key"] for b in preflight.get("blocking", [])]


def _confirmer(client, jeton, cle_regle: str) -> None:
    """Le quatre-yeux complet pour une règle : composer, proposer, approuver.

    C'EST LE SEUL CHEMIN QUI OUVRE LE MODE STRICT, et le harnais fait ce qu'un
    bureau d'études ferait — par les routes du produit, avec deux identités
    distinctes, chacune habilitée. Court-circuiter en écrivant une confirmation
    à la main prouverait que la validation fonctionne sur une base où
    n'importe qui peut en fabriquer une.

    AUCUNE VALEUR NORMATIVE N'EST INVENTÉE. La valeur vient du registre du
    moteur, où elle est marquée ``pending_verification`` ; ce qui est produit
    ici est une **décision humaine fictive à deux regards**, pas une valeur.
    """
    p = _parametre(cle_regle)
    brouillon = {
        "country_code": p.country_code,
        "rule_id": p.key,
        "statement": f"FICTIF — dossier de revue de {p.key} (base jetable).",
        "citations": [{
            "document_digest": p.source_doc_id,
            "quote": f"FICTIF — citation relevee pour {p.key}.",
            "page_printed": p.source_page or 1,
        }],
    }
    r = client.post("/v1/authority/review-packages", json=brouillon,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    paquet = r.json()["package"]

    corps = {
        "subject_kind": "ndp_parameter", "subject_id": p.key, "org_id": None,
        "country_code": p.country_code, "standard_family": p.standard_family,
        "part": p.part, "edition": p.edition,
        "permission": "can_validate_normative_reference",
        "reason": f"FICTIF revue de {p.key}",
        "review_package": paquet,
    }
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision = r.json()["decision_id"]

    # LE SECOND REGARD EST CELUI DE V, ET IL N'EST PAS CELUI DE A. Le
    # quatre-yeux refuse l'auto-approbation, et c'est la propriete qui rend la
    # confirmation autre chose qu'une case cochée.
    r = client.post(f"/v1/authority/decisions/{decision}/approval",
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 204, r.text
    r = client.post(f"/v1/authority/decisions/{decision}/consumption",
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
def projet(client, jeton) -> dict:
    corps = {"name": "FICTIF Halle", "reference": "FICTIF-LIV-01",
             "country": PAYS, "region": "Wallonie", "ndp_as_of": "2024-01-15"}
    r = client.post("/v1/projects", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def calcul_strict(client, jeton, projet) -> str:
    """Un calcul STRICT qui aboutit, seul socle possible d'une attestation.

    ON CONFIRME D'ABORD, ON CALCULE ENSUITE. Le mode strict refuse tant qu'un
    paramètre national reste non confirmé — c'est le comportement juste, et
    c'est précisément ce qui rend une attestation possible : un calcul strict
    abouti n'a employé que des valeurs confirmées.
    """
    # ON N'EXIGE PAS QU'IL Y AIT DES BLOCAGES AU DEPART, et c'est necessaire
    # depuis qu'un second module partage cette base: le premier a deja ouvert
    # le mode strict, et exiger le contraire ferait echouer un decor
    # parfaitement valide. Ce qui compte est l'etat d'ARRIVEE — plus aucun
    # blocage — et il est verifie plus bas.
    # LA BOUCLE RELIT LES BLOCAGES A CHAQUE TOUR. Confirmer une regle peut en
    # decouvrir d'autres — le prevol s'arrete au premier paquet manquant — et
    # une liste prise une fois pour toutes laisserait le calcul refuser encore.
    for _ in range(40):
        restants = _blocages(client)
        if not restants:
            break
        for cle_regle in restants:
            _confirmer(client, jeton, cle_regle)
    assert not _blocages(client), (
        f"le mode strict reste ferme: {_blocages(client)}")

    r = client.post(f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
                    json=_requete_de_calcul(strict=True),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    corps = r.json()
    assert corps["status"] == "succeeded", corps
    assert corps["strict_ndp"] is True
    return corps["calculation_id"]


@pytest.fixture(scope="module")
def calcul_exploratoire(client, jeton, projet) -> str:
    """Un calcul NON strict : il a pu employer des paramètres non confirmés."""
    r = client.post(f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
                    json=_requete_de_calcul(strict=False),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    corps = r.json()
    assert corps["status"] == "succeeded", corps
    assert corps["strict_ndp"] is False
    return corps["calculation_id"]


def _brouillon(client, jeton, projet, calcul_id: str, acteur=None) -> dict:
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": calcul_id},
                    headers=_entete(jeton(acteur or ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def brouillon(client, jeton, projet, calcul_strict) -> dict:
    """Un brouillon NEUF par cas. Les transitions sont irréversibles."""
    return _brouillon(client, jeton, projet, calcul_strict)


@pytest.fixture()
def en_relecture(client, jeton, projet, brouillon) -> dict:
    r = client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{brouillon['deliverable_id']}/review",
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    return r.json()


# ===========================================================================
# 1 — LE BROUILLON EST TIRE DES DONNEES GELEES, ET SES OCTETS EXISTENT
# ===========================================================================
def test_un_calcul_refuse_ne_produit_aucun_livrable(client, jeton, projet):
    """UN REFUS N'EST PAS UNE CONCLUSION, et un livrable se lit comme une.

    Le décor referme le mode strict pour ce cas en visant un projet dont la
    date de référence précède l'annexe : le moteur refuse, la ligne est écrite
    comme refus, et aucun document ne peut en être tiré.
    """
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json={**_requete_de_calcul(strict=True),
              "M_Ed": {"value": 1.0e9, "unit": "kN*m"}},
        headers=_entete(jeton(ACTEUR_A)))
    # LA ROUTE REND 422 **ET** ENREGISTRE LE REFUS. Les deux comptent: le
    # client apprend que le moteur n'a pas conclu, et l'historique garde
    # exactement les calculs qu'un audit chercherait.
    assert r.status_code == 422, r.text

    refuses = _observer(
        "select id from calculations "
        " where project_id = %s and status = 'refused' "
        " order by created_at desc limit 1", (projet["project_id"],))
    assert refuses, "le refus du moteur n'a pas ete enregistre comme refus"
    refuse = str(refuses[0][0])

    avant = _observer("select count(*) from deliverables")[0][0]
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": refuse},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert "refuse par le moteur" in json.dumps(r.json()).lower()
    assert _observer("select count(*) from deliverables")[0][0] == avant

    # ET LA BASE REFUSE ELLE AUSSI, SANS PASSER PAR LA ROUTE.
    #
    # La garde applicative rend un message utilisable; celle-ci est la
    # frontiere. Si quelqu'un ajoute une seconde route demain, c'est elle qui
    # tiendra — et elle nomme l'etat plutot que de parler d'un resultat absent.
    refus = _refus_de_la_primitive(
        "select project_deliverable_create(%s::uuid, %s::uuid,"
        " 'calculation_note_html'::deliverable_kind, %s, %s, %s, %s, %s,"
        " %s::bigint, null, null)",
        (projet["project_id"], refuse, "FICTIF.html", "text/html", "local",
         "o/p/" + "b" * 64 + ".html", "b" * 64, 10))
    assert "refused" in refus, refus
    assert "conclut pas" in refus, refus


def test_un_brouillon_reprend_le_contexte_fige_du_calcul(
        client, jeton, projet, calcul_strict, brouillon):
    """AUCUNE DE CES VALEURS N'EST VENUE DU NAVIGATEUR.

    Version du moteur, build, identité d'exécution et empreinte des entrées
    sont **copiés du calcul** par la primitive. Le corps envoyé ne portait
    qu'un identifiant de calcul.
    """
    r = client.get(f"/v1/projects/{projet['project_id']}/calculations/"
                   f"{calcul_strict}", headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    calcul = r.json()

    assert brouillon["state"] == "draft"
    assert brouillon["revision"] == 1
    assert brouillon["validation_id"] is None
    assert brouillon["calculation_id"] == calcul_strict
    assert brouillon["engine_version"] == calcul["engine_version"]
    assert brouillon["engine_build_sha"] == calcul["engine_build_sha"]
    assert brouillon["execution_identity"] == calcul["execution_identity"]
    assert brouillon["inputs_hash"] == calcul["inputs_hash"]
    assert brouillon["ndp_as_of"] == calcul["ndp_as_of"]
    assert brouillon["size_bytes"] > 0
    assert len(brouillon["sha256"]) == 64
    # UN CALCUL STRICT NE PORTE PAS « PROJET — NON SIGNABLE »: aucune valeur
    # non confirmee n'a servi. La mention obligatoire, elle, reste.
    assert brouillon["mention"] is None
    assert "ingenieur" in brouillon["notice"].lower() \
        or "ingénieur" in brouillon["notice"].lower()


def test_les_octets_telecharges_portent_l_empreinte_enregistree(
        client, jeton, projet, brouillon):
    """LE SEUL MOMENT OU UNE ALTERATION PEUT ENCORE ETRE ATTRAPEE.

    Un document altéré qui s'affiche est pire qu'un document absent, parce
    qu'on le lit. La route revérifie l'empreinte sur les octets qu'elle sert,
    et ce cas vérifie qu'elle sert bien ceux qu'elle a promis.
    """
    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{brouillon['deliverable_id']}/download",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    octets = r.content

    assert hashlib.sha256(octets).hexdigest() == brouillon["sha256"]
    assert len(octets) == brouillon["size_bytes"]
    assert r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["x-content-type-options"] == "nosniff"

    texte = octets.decode("utf-8")
    # LE DOCUMENT EST AUTONOME: aucun script, aucune ressource externe.
    assert "<script" not in texte.lower()
    assert "http://" not in texte and "https://" not in texte
    assert "url(" not in texte
    # ET IL PORTE CE QUI PERMET DE LE RATTACHER A SON CALCUL.
    assert brouillon["engine_build_sha"] in texte
    assert brouillon["execution_identity"] in texte


def test_apres_rechargement_les_memes_octets_reviennent(
        client, client_neuf, jeton, projet, brouillon):
    """LE F5. Une application reconstruite de zéro sert les mêmes octets."""
    chemin = (f"/v1/projects/{projet['project_id']}/deliverables/"
              f"{brouillon['deliverable_id']}/download")
    premiers = client.get(chemin, headers=_entete(jeton(ACTEUR_A))).content
    seconds = client_neuf.get(chemin, headers=_entete(jeton(ACTEUR_A))).content
    assert premiers == seconds
    assert hashlib.sha256(seconds).hexdigest() == brouillon["sha256"]

    # ET LA LISTE LE RETROUVE, avec le même état.
    r = client_neuf.get(f"/v1/projects/{projet['project_id']}/deliverables",
                        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    trouve = [d for d in r.json()["deliverables"]
              if d["deliverable_id"] == brouillon["deliverable_id"]]
    assert len(trouve) == 1
    assert trouve[0]["sha256"] == brouillon["sha256"]


def test_le_chemin_enregistre_permet_reellement_de_retrouver_les_octets(
        brouillon):
    """LA CONTRAINTE SQL, CONSTATEE SUR LA LIGNE REELLEMENT ECRITE.

    ``storage_path_derives_from_sha`` exige que le chemin contienne
    l'empreinte : aucune ligne ne peut désigner un emplacement sans rapport
    avec le contenu qu'elle annonce.
    """
    lignes = _observer(
        "select storage_backend, storage_path, sha256, size_bytes "
        "  from deliverables where id = %s", (brouillon["deliverable_id"],))
    assert len(lignes) == 1
    backend, chemin, sha, taille = lignes[0]
    assert backend == "local"
    assert sha in chemin
    assert sha == brouillon["sha256"]
    assert taille == brouillon["size_bytes"]

    # ET LES OCTETS SONT LA, VUS DEPUIS LE SYSTEME DE FICHIERS.
    from pathlib import Path

    fichier = Path(MAGASIN) / chemin
    assert fichier.is_file(), f"aucun octet a {fichier}"
    assert hashlib.sha256(fichier.read_bytes()).hexdigest() == sha


# ===========================================================================
# 2 — LE PARCOURS DE RELECTURE
# ===========================================================================
def test_la_soumission_a_la_relecture_est_journalisee_et_attribuee(
        client, jeton, projet, en_relecture):
    """UN HISTORIQUE QUI NE NOMME PERSONNE NE SERT A RIEN.

    Le déclencheur de journal retombait sur ``auth.uid()`` — le GUC d'un accès
    direct depuis le navigateur, que notre backend ne pose jamais. Toutes les
    transitions du chemin produit auraient été journalisées sans acteur.
    """
    assert en_relecture["state"] == "review"
    transitions = en_relecture["transitions"]
    assert [t["to_state"] for t in transitions] == ["draft", "review"]
    assert transitions[0]["from_state"] is None
    assert transitions[1]["from_state"] == "draft"
    assert all(t["actor_id"] == ACTEUR_A for t in transitions), transitions
    assert all(t["occurred_at"] for t in transitions)


def test_le_retour_au_brouillon_exige_un_motif_et_le_conserve(
        client, jeton, projet, en_relecture):
    """UN RETOUR MUET EST UNE DECISION QU'ON NE PEUT PAS RELIRE."""
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")

    r = client.post(f"{base}/draft", json={"reason": ""},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text

    r = client.post(f"{base}/draft", json={},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text

    motif = "FICTIF — la portee de la poutre ne correspond pas au plan."
    r = client.post(f"{base}/draft", json={"reason": motif},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["state"] == "draft"
    assert corps["last_reason"] == motif
    assert corps["transitions"][-1]["reason"] == motif
    assert corps["transitions"][-1]["actor_id"] == ACTEUR_V


def test_l_attestation_derive_le_nom_le_role_et_le_numero_de_l_adhesion(
        client, jeton, projet, en_relecture):
    """L'APPELANT N'A ENVOYE QUE SON TEXTE.

    Nom, rôle et numéro d'inscription sortent de ``organization_members``.
    C'est ce qui rend impossible d'attester sous le nom de quelqu'un d'autre.
    """
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")
    texte = ("FICTIF — j'ai relu les hypotheses, les charges et le "
             "ferraillage de cette poutre.")
    reserves = "FICTIF — sous reserve du controle de l'enrobage a l'execution."

    r = client.post(f"{base}/validation",
                    json={"statement": texte, "reservations": reserves},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    corps = r.json()

    assert corps["state"] == "validated"
    assert corps["validation_id"]
    assert corps["validator_name"] == "FICTIF Ing. V (compte de test)"
    assert corps["validator_role"] == "validating_engineer"
    assert corps["professional_id"] == "FICTIF-ORDRE-0001"
    assert corps["statement"] == texte
    assert corps["reservations"] == reserves
    assert corps["validated_at"]

    # LA LIGNE DE VALIDATION PORTE LE CONTEXTE EXACT DU CALCUL.
    lignes = _observer(
        "select v.validated_by, v.execution_identity, v.engine_build_sha, "
        "       v.inputs_hash, v.deliverable_sha256, v.ndp_set_version "
        "  from validations v where v.id = %s", (corps["validation_id"],))
    assert len(lignes) == 1
    par, identite, build, entrees, octets, ndp = lignes[0]
    assert str(par) == ACTEUR_V
    assert identite == corps["execution_identity"]
    assert build == corps["engine_build_sha"]
    assert entrees == corps["inputs_hash"]
    assert octets == corps["sha256"]
    assert ndp, "l'instantane normatif atteste doit etre designe"

    # ET LA CONSERVATION DECENNALE S'EST REELLEMENT OUVERTE.
    retention = _observer("select retention_until from projects where id = %s",
                          (projet["project_id"],))[0][0]
    assert retention is not None, (
        "une attestation sans conservation decennale ne vaut rien")


def test_l_emission_exige_l_attestation_puis_la_suit(
        client, jeton, projet, en_relecture):
    """EMETTRE N'EST PAS VALIDER, et l'ordre n'est pas negociable."""
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")

    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text
    assert "attestation" in json.dumps(r.json()).lower()

    r = client.post(f"{base}/validation",
                    json={"statement": "FICTIF — relu et approuve."},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text

    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "final"


def test_un_livrable_emis_ne_se_modifie_plus(
        client, jeton, projet, en_relecture):
    """CORRIGER APRES ATTESTATION, C'EST EMETTRE L'INDICE SUIVANT."""
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")
    client.post(f"{base}/validation",
                json={"statement": "FICTIF — relu et approuve."},
                headers=_entete(jeton(ACTEUR_V)))
    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text

    for action, corps in (("review", None), ("draft", {"reason": "FICTIF"})):
        r = client.post(f"{base}/{action}", json=corps,
                        headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 422, (action, r.text)

    # ET L'ETAT N'A PAS BOUGE.
    r = client.get(base, headers=_entete(jeton(ACTEUR_A)))
    assert r.json()["state"] == "final"


def test_une_revision_remplace_l_indice_precedent(
        client, jeton, projet, calcul_strict, en_relecture):
    """LE SEUL CHEMIN DE CORRECTION APRES ATTESTATION."""
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")
    client.post(f"{base}/validation",
                json={"statement": "FICTIF — relu et approuve."},
                headers=_entete(jeton(ACTEUR_V)))
    client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))

    r = client.post(f"{base}/revision", json={"calculation_id": calcul_strict},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    indice = r.json()
    assert indice["state"] == "draft"
    assert indice["revision"] == en_relecture["revision"] + 1
    assert indice["supersedes_id"] == en_relecture["deliverable_id"]
    assert indice["validation_id"] is None


# ===========================================================================
# 3 — LES REFUS
# ===========================================================================
def _routes_du_livrable(projet, deliverable_id) -> list[tuple[str, str, dict]]:
    base = f"/v1/projects/{projet['project_id']}/deliverables"
    return [
        ("get", base, {}),
        ("post", base, {"calculation_id": "00000000-0000-0000-0000-000000000000"}),
        ("get", f"{base}/{deliverable_id}", {}),
        ("get", f"{base}/{deliverable_id}/download", {}),
        ("post", f"{base}/{deliverable_id}/review", None),
        ("post", f"{base}/{deliverable_id}/draft", {"reason": "FICTIF"}),
        ("post", f"{base}/{deliverable_id}/validation",
         {"statement": "FICTIF"}),
        ("post", f"{base}/{deliverable_id}/final", None),
    ]


def _appeler(client, methode, chemin, corps, entetes):
    if methode == "get":
        return client.get(chemin, headers=entetes)
    return client.post(chemin, json=corps, headers=entetes)


@pytest.mark.parametrize("nom,entetes", [
    ("absent", {}),
    ("vide", {"Authorization": "Bearer "}),
    ("falsifie", {"Authorization": "Bearer " + "a.b.c"}),
])
def test_sans_jeton_valable_aucune_route_de_livrable_ne_repond(
        client, projet, brouillon, nom, entetes):
    """UN LIVRABLE NOMME UN CLIENT ET UNE ETUDE: ce n'est pas public."""
    for methode, chemin, corps in _routes_du_livrable(
            projet, brouillon["deliverable_id"]):
        r = _appeler(client, methode, chemin, corps, entetes)
        assert r.status_code == 401, (nom, methode, chemin, r.status_code)


def test_un_jeton_expire_est_refuse(client, jeton, projet, brouillon):
    """LA TOLERANCE D'HORLOGE EST A ZERO: un jeton perime est perime."""
    perime = jeton(ACTEUR_A, duree=-60)
    for methode, chemin, corps in _routes_du_livrable(
            projet, brouillon["deliverable_id"]):
        r = _appeler(client, methode, chemin, corps, _entete(perime))
        assert r.status_code == 401, (methode, chemin, r.status_code)


def test_un_role_insuffisant_n_atteste_pas(client, jeton, projet, en_relecture):
    """« viewer » NE PORTE PAS LA VALIDATION TECHNIQUE, et le message le dit."""
    avant = _observer("select count(*) from validations")[0][0]
    r = client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{en_relecture['deliverable_id']}/validation",
        json={"statement": "FICTIF — je valide."},
        headers=_entete(jeton(ACTEUR_W)))
    assert r.status_code == 422, r.text
    assert "viewer" in json.dumps(r.json())
    assert _observer("select count(*) from validations")[0][0] == avant


def test_un_membre_desactive_n_atteste_pas(client, jeton, projet, en_relecture):
    """UN ACCES REVOQUE NE PEUT PLUS ENGAGER LE BUREAU D'ETUDES.

    La ligne d'adhésion survit — un ancien collaborateur doit rester lisible
    dans une note de dix ans — et le droit de signer, non.

    DEPUIS 0023, IL N'ATTEINT MEME PLUS LE LIVRABLE. ``is_active`` est entré
    dans ``project_actor_is_member``, donc dans la politique de lecture de
    ``deliverables`` : la primitive ne trouve aucune ligne et refuse avant
    d'avoir à parler de rôle. Le refus change de mot — « introuvable » plutôt
    que « révoqué » — et ce n'est pas une régression : un accès coupé ne doit
    rien apprendre, pas même l'existence de la pièce.
    """
    avant = _observer("select count(*) from validations")[0][0]
    r = client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{en_relecture['deliverable_id']}/validation",
        json={"statement": "FICTIF — je valide."},
        headers=_entete(jeton(ACTEUR_D)))
    assert r.status_code == 422, r.text
    message = json.dumps(r.json()).lower()
    assert "revoque" in message or "introuvable" in message, r.text
    assert _observer("select count(*) from validations")[0][0] == avant


def test_un_membre_sans_nom_enregistre_n_atteste_pas(
        client, jeton, projet, en_relecture):
    """UNE ATTESTATION PORTE LE NOM D'UNE PERSONNE.

    Substituer l'identifiant technique donnerait une attestation signée
    « 2222… », qui ne nomme personne tout en ayant l'air complète.
    """
    avant = _observer("select count(*) from validations")[0][0]
    r = client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{en_relecture['deliverable_id']}/validation",
        json={"statement": "FICTIF — je valide."},
        headers=_entete(jeton(ACTEUR_N)))
    assert r.status_code == 422, r.text
    assert "nom" in json.dumps(r.json()).lower()
    assert _observer("select count(*) from validations")[0][0] == avant


def test_un_calcul_exploratoire_produit_un_brouillon_filigrane_et_rien_de_plus(
        client, jeton, projet, calcul_exploratoire):
    """LE CŒUR DE L'INTERDICTION N° 2, DANS LE PARCOURS PRODUIT.

    Un calcul mené en mode non strict a pu employer des paramètres nationaux
    non confirmés. Il peut donner un brouillon — filigrané — parce qu'un
    ingénieur a le droit d'explorer. Il ne peut jamais être attesté : ce serait
    faire porter une signature humaine sur des nombres qu'aucune Annexe
    Nationale ne soutient.
    """
    livrable = _brouillon(client, jeton, projet, calcul_exploratoire)
    assert livrable["state"] == "draft"
    assert livrable["watermark"] == "PROJET — NON SIGNABLE"
    assert livrable["mention"] == "PROJET — NON SIGNABLE"

    octets = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{livrable['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A))).content
    assert "PROJET — NON SIGNABLE" in octets.decode("utf-8")

    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{livrable['deliverable_id']}")
    r = client.post(f"{base}/review", headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    avant = _observer("select count(*) from validations")[0][0]
    r = client.post(f"{base}/validation",
                    json={"statement": "FICTIF — je valide."},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text
    assert "strict" in json.dumps(r.json()).lower()
    assert _observer("select count(*) from validations")[0][0] == avant

    # ET IL N'ATTEINT NI `validated` NI `final`.
    r = client.get(base, headers=_entete(jeton(ACTEUR_A)))
    assert r.json()["state"] == "review"


def test_une_organisation_voisine_ne_lit_ni_ne_telecharge(
        client, jeton, projet, brouillon):
    """L'AILLEURS SANS LEQUEL L'ISOLATION NE SE PROUVE PAS.

    B présente son propre jeton, valide, signé de la même clé. Il n'est
    simplement membre d'aucune organisation de ce projet.
    """
    for methode, chemin, corps in _routes_du_livrable(
            projet, brouillon["deliverable_id"]):
        r = _appeler(client, methode, chemin, corps, _entete(jeton(ACTEUR_B)))
        assert r.status_code == 422, (methode, chemin, r.status_code)
        assert "introuvable" in json.dumps(r.json()).lower(), (methode, chemin)


def test_un_calcul_d_un_autre_projet_ne_produit_pas_de_livrable(
        client, jeton, projet, calcul_strict):
    """RLS NE L'ATTRAPERAIT PAS: la ligne insérée porterait le bon ``org_id``.

    C'est le contrôle explicite de la primitive — « ce calcul appartient-il à
    ce projet » — qui ferme ce chemin.
    """
    r = client.post("/v1/projects",
                    json={"name": "FICTIF Autre", "country": PAYS,
                          "ndp_as_of": "2024-01-15"},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    autre = r.json()["project_id"]

    avant = _observer("select count(*) from deliverables")[0][0]
    r = client.post(f"/v1/projects/{autre}/deliverables",
                    json={"calculation_id": calcul_strict},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert _observer("select count(*) from deliverables")[0][0] == avant


@pytest.mark.parametrize("champ,valeur", [
    ("org_id", ORG_B),
    ("organization_id", ORG_B),
    ("sha256", "0" * 64),
    ("storage_path", "ailleurs/fichier.html"),
    ("state", "final"),
    ("engine_build_sha", "FICTIF-autre-build"),
    ("execution_identity", "f" * 64),
    ("validator_name", "FICTIF quelqu'un d'autre"),
])
def test_le_corps_ne_peut_nommer_aucune_valeur_derivee(
        client, jeton, projet, calcul_strict, champ, valeur):
    """UN CHAMP REFUSE VAUT MIEUX QU'UN CHAMP IGNORE.

    Écraser silencieusement marcherait tant qu'une seule route existe ;
    refuser dit au client que sa valeur n'a **aucun** effet, plutôt que de le
    laisser croire qu'elle en a un.
    """
    avant = _observer("select count(*) from deliverables")[0][0]
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": calcul_strict, champ: valeur},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, (champ, r.text)
    assert _observer("select count(*) from deliverables")[0][0] == avant


def test_l_attestation_ne_peut_nommer_ni_validateur_ni_calcul(
        client, jeton, projet, en_relecture):
    """Même règle, sur le corps de l'attestation."""
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}/validation")
    for champ, valeur in (("validated_by", ACTEUR_A),
                          ("validator_name", "FICTIF autre"),
                          ("validator_role", "validating_engineer"),
                          ("professional_id", "FICTIF-9999"),
                          ("calculation_id", "00000000-0000-0000-0000-000000000000"),
                          ("deliverable_sha256", "0" * 64)):
        r = client.post(base, json={"statement": "FICTIF", champ: valeur},
                        headers=_entete(jeton(ACTEUR_V)))
        assert r.status_code == 422, (champ, r.text)


def test_une_transition_interdite_est_refusee(
        client, jeton, projet, brouillon):
    """LA MACHINE A ETATS N'EST PAS REECRITE DANS L'API: elle est demandee.

    Valider un brouillon qui n'est pas en relecture est refusé par la
    primitive, pas par une règle applicative parallèle qui pourrait diverger.
    """
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{brouillon['deliverable_id']}")

    avant = _observer("select count(*) from validations")[0][0]
    r = client.post(f"{base}/validation", json={"statement": "FICTIF"},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text
    assert "relecture" in json.dumps(r.json()).lower()
    assert _observer("select count(*) from validations")[0][0] == avant

    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text

    # ET UN BROUILLON NE « REVIENT » PAS AU BROUILLON.
    #
    # MESURE DU JOUR: c'etait ACCEPTE. Le declencheur de la machine a etats ne
    # controle que les changements d'etat — a juste titre — si bien qu'aucune
    # ligne de journal n'etait ecrite mais que `last_reason` etait ecrase.
    # L'ecran affichait un motif de refus sur une piece que personne n'avait
    # refusee, sans que l'historique dise d'ou il venait.
    # LE RETOUR AU BROUILLON EST UN GESTE DE RELECTEUR (0023): c'est donc V qui
    # le tente ici. Le demander sous l'identite du redacteur eprouverait le
    # controle de capacite, pas la transition — et ce cas-ci vise la seconde.
    r = client.post(f"{base}/draft", json={"reason": "FICTIF"},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 422, r.text
    assert "deja" in json.dumps(r.json()).lower()

    r = client.get(base, headers=_entete(jeton(ACTEUR_A)))
    assert r.json()["last_reason"] is None
    assert [t["to_state"] for t in r.json()["transitions"]] == ["draft"]


def test_sans_magasin_configure_la_creation_refuse_par_503(
        client, jeton, projet, calcul_strict, monkeypatch):
    """UN 503, PAS UN 422. La demande est bonne; le service ne peut pas la tenir.

    Et surtout : **aucune ligne n'est écrite**. Une ligne enregistrée sans
    octets promettrait un document introuvable, découvert dix ans plus tard.
    """
    monkeypatch.delenv("EUROSTRUCT_STORAGE_DIR", raising=False)
    avant = _observer("select count(*) from deliverables")[0][0]
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": calcul_strict},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 503, r.text
    assert "EUROSTRUCT_STORAGE_DIR" in json.dumps(r.json())
    assert _observer("select count(*) from deliverables")[0][0] == avant


def test_un_magasin_qui_ne_relit_pas_ce_qu_il_ecrit_n_enregistre_rien(
        client, jeton, projet, calcul_strict, monkeypatch):
    """LA RELECTURE AVANT ENREGISTREMENT, MISE EN ECHEC EXPRES.

    Un magasin qui accepte silencieusement et perd le contenu — disque plein,
    quota, montage en lecture seule mal diagnostiqué — laisserait une ligne
    parfaitement formée devant un document introuvable. Ce cas simule
    exactement cela, et vérifie qu'aucune ligne n'est écrite.
    """
    from eurostruct_api import stockage as mod
    from eurostruct_api.routes import livrables as routes

    class MagasinMenteur(mod.StockageLocal):
        def lire(self, chemin: str) -> bytes:
            return b"FICTIF - ces octets ne sont pas ceux qui ont ete deposes"

    monkeypatch.setattr(routes, "stockage_configure",
                        lambda: MagasinMenteur(MAGASIN))
    avant = _observer("select count(*) from deliverables")[0][0]
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": calcul_strict},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 503, r.text
    assert _observer("select count(*) from deliverables")[0][0] == avant


def test_la_base_refuse_elle_meme_un_chemin_qui_ne_designe_pas_les_octets():
    """LA SECURITE NE DOIT PAS DEPENDRE UNIQUEMENT DE LA ROUTE.

    Ce cas n'emprunte aucune route : il écrit directement, avec les privilèges
    du propriétaire de la base, un livrable dont le chemin ne contient pas
    l'empreinte. La contrainte de table le refuse.
    """
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        with connexion, connexion.cursor() as curseur:
            curseur.execute(
                "select d.org_id, d.project_id, d.calculation_id, "
                "       d.engine_version, d.generated_by "
                "  from deliverables d limit 1")
            modele = curseur.fetchone()
            assert modele, "aucun livrable de reference"
            with pytest.raises(psycopg2.errors.CheckViolation):
                curseur.execute(
                    "insert into deliverables (org_id, project_id, "
                    "  calculation_id, kind, filename, storage_path, sha256, "
                    "  size_bytes, engine_version, generated_by) "
                    "values (%s, %s, %s, 'calculation_note_html', "
                    "  'FICTIF.html', 'ailleurs/sans-rapport.html', %s, 10, "
                    "  %s, %s)",
                    (modele[0], modele[1], modele[2], "a" * 64,
                     modele[3], modele[4]))
    finally:
        connexion.rollback()
        connexion.close()


def test_le_projet_dit_le_role_de_l_appelant_dans_cette_organisation(
        client, jeton, projet):
    """L'ÉCRAN DOIT SAVOIR CE QU'IL A LE DROIT DE FAIRE.

    Sans cette information, il n'a que deux mauvaises réponses : afficher
    « Attester le calcul » à un dessinateur, qui cliquera et recevra un refus ;
    ou cacher le bouton sans un mot, ce qui ne s'explique pas.

    LE RÔLE EST DÉRIVÉ, PAS DÉCLARÉ. Il sort de ``organization_members`` sous
    l'identité du jeton, exactement comme la primitive d'attestation le dérive
    au moment d'agir. Il sert à MONTRER ou EXPLIQUER ; la frontière reste dans
    PostgreSQL, et les cas de refus plus haut l'établissent.

    ET IL EST PAR PROJET, PAS PAR SESSION : un ingénieur peut être validateur
    dans un bureau et simple lecteur dans un autre.
    """
    attendus = {
        ACTEUR_A: ("engineer", "FICTIF Ing. A", True),
        ACTEUR_V: ("validating_engineer", "FICTIF Ing. V (compte de test)", True),
        ACTEUR_W: ("viewer", "FICTIF Lecteur W", True),
        ACTEUR_N: ("validating_engineer", None, True),
    }
    for acteur, (role, nom, actif) in attendus.items():
        r = client.get("/v1/projects", headers=_entete(jeton(acteur)))
        assert r.status_code == 200, (acteur, r.text)
        vus = [p for p in r.json()["projects"]
               if p["project_id"] == projet["project_id"]]
        assert len(vus) == 1, (acteur, vus)
        assert vus[0]["member_role"] == role, acteur
        assert vus[0]["member_name"] == nom, acteur
        assert vus[0]["member_active"] is actif, acteur

    # ET DEUX IDENTITES NE VOIENT PAS CE PROJET DU TOUT: celle de
    # l'organisation voisine, et celle dont l'acces a ete REVOQUE. Le role
    # rendu n'ouvre rien — il decrit une appartenance qui doit d'abord exister
    # et etre active.
    for absent, pourquoi in ((ACTEUR_B, "autre organisation"),
                             (ACTEUR_D, "acces revoque")):
        r = client.get("/v1/projects", headers=_entete(jeton(absent)))
        assert r.status_code == 200, r.text
        assert all(p["project_id"] != projet["project_id"]
                   for p in r.json()["projects"]), pourquoi


# ===========================================================================
# 4 — LE DOSSIER DE REVUE
# ===========================================================================
def test_le_dossier_de_revue_porte_le_document_et_son_rattachement(
        client, jeton, projet, brouillon):
    """ENVOYER LA NOTE SEULE OBLIGE SON DESTINATAIRE À CROIRE SUR PAROLE.

    Le dossier porte, à côté des octets exacts, un manifeste qui nomme
    l'organisation, le projet, le contexte normatif, la version et le SHA du
    moteur, l'identité d'exécution, l'empreinte des entrées, et les DEUX
    empreintes du document : celle enregistrée, et celle des octets qui
    partent dans l'archive. Un manifeste qui n'en porterait qu'une ne
    permettrait pas de constater qu'elles s'accordent — il l'affirmerait.
    """
    import io
    import zipfile

    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{brouillon['deliverable_id']}/review-bundle",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/zip")
    assert "attachment" in r.headers["content-disposition"]
    # LES DEUX FORMES DE LA RFC 6266, comme sur le telechargement du
    # document. L'ancienne assertion regardait la FIN de l'en-tete: elle
    # supposait que `filename=` etait le dernier champ, ce qui a cesse d'etre
    # vrai des que `filename*` l'a suivi. On verifie le NOM, pas sa position.
    disposition = r.headers["content-disposition"]
    assert 'filename="dossier-revue-' in disposition
    assert ".zip" in disposition
    assert "filename*=UTF-8''" in disposition
    #: LE NOM SUIT LE DOCUMENT ENREGISTRE, extension comprise: c'est ce qui
    #: distingue le dossier d'une note HTML de celui d'une note PDF.
    assert brouillon["filename"] in disposition

    archive = zipfile.ZipFile(io.BytesIO(r.content))
    noms = sorted(archive.namelist())
    assert noms == sorted([f"documents/{brouillon['filename']}",
                           "manifeste.json"]), noms

    # LES OCTETS SONT CEUX DU LIVRABLE, PAS UN DOCUMENT RECOMPOSE.
    octets = archive.read(f"documents/{brouillon['filename']}")
    assert hashlib.sha256(octets).hexdigest() == brouillon["sha256"]

    m = json.loads(archive.read("manifeste.json"))
    assert m["kind"] == "eurostruct/review-bundle"
    assert m["organization"]["id"] == ORG_A
    assert m["project"]["id"] == projet["project_id"]
    assert m["project"]["region"] == "Wallonie"
    assert m["calculation"]["id"] == brouillon["calculation_id"]
    assert m["calculation"]["engine_build_sha"] == brouillon["engine_build_sha"]
    assert m["calculation"]["execution_identity"] == brouillon["execution_identity"]
    assert m["calculation"]["inputs_hash"] == brouillon["inputs_hash"]
    assert m["files"][0]["sha256_recorded"] == brouillon["sha256"]
    assert m["files"][0]["sha256_served"] == brouillon["sha256"]
    assert m["files"][0]["size_bytes"] == len(octets)

    # CE QUI N'EXISTE PAS EST NOMME. Un dossier qui listerait seulement ce
    # qu'il contient laisserait croire que le reste n'a pas ete demande.
    assert "calculation_note_pdf" in m["artifacts_not_produced"]
    assert "ifc_export" in m["artifacts_not_produced"]

    # ET IL NE SE DIT JAMAIS SIGNE ELECTRONIQUEMENT.
    assert m["attestation"]["kind"] == "attestation_metier_authentifiee"
    assert m["attestation"]["is_qualified_electronic_signature"] is False
    assert m["attestation"]["validation_id"] is None
    assert m["mention"] is None


def test_deux_telechargements_du_dossier_rendent_les_memes_octets(
        client, jeton, projet, brouillon):
    """UN DOSSIER DONT L'EMPREINTE CHANGE NE PEUT RIEN ATTESTER.

    ZIP n'a pas de champ « sans date » : prendre l'heure courante rendrait deux
    archives du même dossier différentes d'un octet, donc d'empreinte. On ne
    pourrait alors pas dire « voici le dossier que j'ai relu ».
    """
    chemin = (f"/v1/projects/{projet['project_id']}/deliverables/"
              f"{brouillon['deliverable_id']}/review-bundle")
    premier = client.get(chemin, headers=_entete(jeton(ACTEUR_A)))
    second = client.get(chemin, headers=_entete(jeton(ACTEUR_A)))
    assert premier.status_code == second.status_code == 200
    assert premier.content == second.content
    assert (hashlib.sha256(premier.content).hexdigest()
            == hashlib.sha256(second.content).hexdigest())


def test_le_dossier_d_une_piece_attestee_porte_l_attestation(
        client, jeton, projet, en_relecture):
    """ET IL LA NOMME POUR CE QU'ELLE EST."""
    import io
    import zipfile

    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")
    texte = "FICTIF — relu, sous reserve du controle d'enrobage."
    r = client.post(f"{base}/validation",
                    json={"statement": texte, "reservations": "FICTIF — reserve."},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text

    r = client.get(f"{base}/review-bundle", headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    m = json.loads(zipfile.ZipFile(io.BytesIO(r.content)).read("manifeste.json"))

    assert m["attestation"]["validator_name"] == "FICTIF Ing. V (compte de test)"
    assert m["attestation"]["validator_role"] == "validating_engineer"
    assert m["attestation"]["professional_id"] == "FICTIF-ORDRE-0001"
    assert m["attestation"]["statement"] == texte
    assert m["attestation"]["signed_at"]
    assert m["attestation"]["is_qualified_electronic_signature"] is False
    assert m["deliverable"]["state"] == "validated"
    assert [t["to_state"] for t in m["transitions"]] == ["draft", "review",
                                                         "validated"]


def test_une_organisation_voisine_n_obtient_aucun_dossier_de_revue(
        client, jeton, projet, brouillon):
    """MEME ISOLATION QUE LA LECTURE, PAR LE MEME CHEMIN."""
    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{brouillon['deliverable_id']}/review-bundle",
                   headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 422, r.text
    assert "introuvable" in json.dumps(r.json()).lower()

    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{brouillon['deliverable_id']}/review-bundle")
    assert r.status_code == 401, r.text


# ===========================================================================
# 9 — UN REFUS NE DOIT RIEN LAISSER DANS LE MAGASIN
#
# LA POLITIQUE DES ORPHELINS REND CE POINT IRRATTRAPABLE. `docs/STOCKAGE.md`
# etablit que RIEN n'est jamais supprime du magasin par le produit, et que
# `ClientS3` n'a aucune methode de suppression. C'est une bonne regle: elle
# rend impossible la suppression d'un objet encore reference.
#
# Mais elle a une contrepartie que rien ne mesurait: tout objet depose puis
# abandonne reste la POUR TOUJOURS. Il n'existe aucun geste, aucune commande
# et aucune route capable de le nommer, encore moins de le reprendre. Chaque
# refus prononce APRES un depot est donc une fuite definitive.
#
# `_creer` le sait pour l'autorisation — le commentaire « un refus prononce
# apres le depot laisse un objet orphelin » est ecrit a la ligne 233 — et
# place le controle de capacite avant le magasin. Les cas ci-dessous
# demandent si TOUS les refus ont recu le meme soin.
# ===========================================================================
def _objets_du_magasin(prefixe: str = "") -> set[str]:
    """Les objets reellement presents sous la racine du magasin local.

    ON REGARDE LE DISQUE, PAS LA BASE. Toute la question est justement de
    savoir si les deux disent la meme chose; les interroger tous les deux par
    le meme chemin ne prouverait rien.
    """
    racine = Path(MAGASIN)
    if not racine.is_dir():
        return set()
    return {str(c.relative_to(racine)) for c in racine.rglob("*")
            if c.is_file() and str(c.relative_to(racine)).startswith(prefixe)}


@pytest.fixture()
def projet_vierge(client, jeton) -> dict:
    """Un projet NEUF, dont le prefixe de magasin n'a jamais rien recu.

    POURQUOI PAS LE PROJET DU MODULE. Le chemin d'un livrable est derive de
    son CONTENU: deux depots des memes octets ecrivent au meme endroit. Un
    orphelin qui reprendrait le chemin d'un document deja depose serait
    rigoureusement invisible a un comptage de fichiers — non pas parce qu'il
    n'y en a pas, mais parce qu'on ne saurait pas le voir. Un projet neuf
    donne un prefixe `org/projet/` vide, ou tout fichier qui apparait est
    forcement ne de ce cas-ci.
    """
    r = client.post("/v1/projects",
                    json={"name": "FICTIF Vierge", "reference": "FICTIF-ORPH",
                          "country": PAYS, "region": "Wallonie",
                          "ndp_as_of": "2024-01-15"},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def calcul_du_projet_vierge(client, jeton, projet_vierge, calcul_strict) -> str:
    """Un calcul abouti DANS ce projet neuf.

    Il depend de `calcul_strict` uniquement pour son effet de bord: c'est lui
    qui a confirme les parametres nationaux et ouvert le mode strict.
    """
    r = client.post(
        f"/v1/projects/{projet_vierge['project_id']}"
        "/calculations/ec2/beam-flexure",
        json=_requete_de_calcul(strict=True),
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    corps = r.json()
    assert corps["status"] == "succeeded", corps
    return corps["calculation_id"]


def test_une_revision_refusee_ne_laisse_pas_d_objet_que_rien_ne_reference(
        client, jeton, projet_vierge, calcul_du_projet_vierge):
    """LE REFUS EST JUSTE, ET IL ARRIVE TROP TARD.

    `supersedes_id` n'est controle NULLE PART avant `creer_livrable`: ni la
    route, ni le module d'atelier ne le regardent. La sequence est donc
    composer -> DEPOSER -> relire -> enregistrer, et c'est l'enregistrement
    qui decouvre que le livrable remplace n'appartient pas au projet.

    A cet instant les octets sont deja dans le magasin, aucune ligne ne les
    reference, et aucun code de ce depot ne peut les reprendre.

    LE CLIENT N'A RIEN FAIT D'ANORMAL. Se tromper d'identifiant de livrable
    est l'erreur la plus banale qui soit — une page rouverte, un identifiant
    d'un autre projet colle dans l'URL — et elle coute un objet definitif.
    """
    prefixe = f"{projet_vierge['organization_id']}/" \
              f"{projet_vierge['project_id']}/"
    assert not _objets_du_magasin(prefixe), (
        "le decor est cense partir d'un prefixe vide")
    avant = _observer("select count(*) from deliverables")[0][0]

    inconnu = str(uuid.uuid4())
    r = client.post(
        f"/v1/projects/{projet_vierge['project_id']}"
        f"/deliverables/{inconnu}/revision",
        json={"calculation_id": calcul_du_projet_vierge},
        headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 422, r.text
    assert _observer("select count(*) from deliverables")[0][0] == avant, (
        "aucune ligne ne doit naitre d'un refus")

    apparus = _objets_du_magasin(prefixe)
    assert not apparus, (
        "LE REFUS A LAISSE DES OCTETS DERRIERE LUI. Objets deposes puis "
        f"abandonnes sous « {prefixe} »: {sorted(apparus)}. Aucune ligne de "
        "`deliverables` ne les reference, et la politique du magasin interdit "
        "de les supprimer: ils sont definitifs."
    )


def test_un_calcul_d_un_autre_projet_ne_laisse_pas_d_octets(
        client, jeton, projet_vierge, calcul_strict):
    """LE MEME SOUPCON, SUR L'AUTRE REFUS TARDIF CONNU.

    `test_un_calcul_d_un_autre_projet_ne_produit_pas_de_livrable` etablit
    depuis longtemps qu'aucune LIGNE ne nait de ce chemin. Il ne regarde pas
    le magasin — et la question n'est pas la meme.

    Ce cas la pose. S'il passe du premier coup, il ne mesure pas un correctif:
    il constate que `_octets_du_document` refuse AVANT le depot, et il verrouille
    cet ordre pour la suite.
    """
    prefixe = f"{projet_vierge['organization_id']}/" \
              f"{projet_vierge['project_id']}/"
    assert not _objets_du_magasin(prefixe)

    r = client.post(
        f"/v1/projects/{projet_vierge['project_id']}/deliverables",
        json={"calculation_id": calcul_strict},
        headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 422, r.text
    apparus = _objets_du_magasin(prefixe)
    assert not apparus, (
        "un calcul etranger au projet a tout de meme fait ecrire dans le "
        f"magasin: {sorted(apparus)}"
    )


# ===========================================================================
# 10 — LA MEME NOTE, EN PDF, PAR LES MEMES ROUTES
# ===========================================================================
def _localisation(deliverable_id: str) -> tuple[str, str, str, int]:
    """``(storage_backend, storage_path, sha256, size_bytes)``, lus EN BASE.

    On interroge la base d'observation, pas la reponse HTTP: ce qui compte est
    ce que la LIGNE enregistre, puisque c'est elle qui servira a retrouver les
    octets dans dix ans.
    """
    lignes = _observer(
        "select storage_backend, storage_path, sha256, size_bytes "
        "  from deliverables where id = %s", (deliverable_id,))
    assert lignes, f"aucune ligne de livrable pour {deliverable_id}"
    return lignes[0]


def _brouillon_pdf(client, jeton, projet, calcul_id: str) -> dict:
    r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                    json={"calculation_id": calcul_id, "format": "pdf"},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


def test_un_brouillon_pdf_enregistre_sa_nature_et_son_type_reels(
        client, jeton, projet, calcul_strict):
    """LES QUATRE VALEURS SE DECIDENT ENSEMBLE, OU ELLES MENTENT.

    Genre enregistre, type de media, extension du chemin, extension du nom de
    fichier. Une ligne qui annoncerait `calculation_note_pdf` devant un objet
    `.html` ferait servir l'un en promettant l'autre.
    """
    livrable = _brouillon_pdf(client, jeton, projet, calcul_strict)

    assert livrable["kind"] == "calculation_note_pdf"
    assert livrable["media_type"] == "application/pdf"
    assert livrable["filename"].endswith(".pdf")

    backend, chemin, sha, _ = _localisation(livrable["deliverable_id"])
    assert backend == "local"
    assert chemin.endswith(".pdf")
    assert chemin.startswith(f"{projet['organization_id']}/"
                             f"{projet['project_id']}/")
    assert sha in chemin, "le chemin doit deriver de l'empreinte"


def test_les_octets_pdf_telecharges_portent_l_empreinte_enregistree(
        client, jeton, projet, calcul_strict):
    livrable = _brouillon_pdf(client, jeton, projet, calcul_strict)
    _, _, sha, taille = _localisation(livrable["deliverable_id"])

    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{livrable['deliverable_id']}/download",
                   headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert hashlib.sha256(r.content).hexdigest() == sha
    assert len(r.content) == taille
    assert r.content.startswith(b"%PDF-")
    # RFC 6266: les deux formes du nom, et l'extension juste dans les deux.
    disposition = r.headers["content-disposition"]
    assert ".pdf" in disposition


def test_le_pdf_servi_s_ouvre_avec_un_lecteur_tiers_et_porte_la_mention(
        client, jeton, projet, calcul_exploratoire):
    """LE TEMOIN EST EXTERIEUR, ET IL LIT LES OCTETS REELLEMENT SERVIS.

    Pas le document composé en mémoire : ceux qui sont sortis du magasin et
    ont traversé le transport. Un PDF valide à la composition et corrompu au
    téléchargement passerait tous les autres cas.
    """
    pypdf = pytest.importorskip("pypdf")
    import io

    livrable = _brouillon_pdf(client, jeton, projet, calcul_exploratoire)
    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{livrable['deliverable_id']}/download",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    lecteur = pypdf.PdfReader(io.BytesIO(r.content))
    texte = "\n".join(p.extract_text() for p in lecteur.pages)

    # INTERDICTION N° 8: la mention de validation est sur TOUT document.
    assert "n'est pas un livrable final" in texte
    # Le calcul est exploratoire: le filigrane doit y etre.
    assert "NON SIGNABLE" in texte
    assert livrable["mention"], "la ligne doit porter le filigrane elle aussi"


def test_deux_pdf_du_meme_calcul_ecrivent_au_meme_endroit(
        client, jeton, projet, calcul_strict):
    """LE PDF EST DETERMINISTE, DONC L'ADRESSAGE PAR CONTENU FONCTIONNE.

    Si la composition inscrivait une date, les deux empreintes differeraient
    et le magasin porterait deux objets pour un seul et meme calcul — sans
    qu'aucun chiffre du document n'ait bouge. C'est ce cas qui le constate par
    le chemin produit.
    """
    un = _brouillon_pdf(client, jeton, projet, calcul_strict)
    deux = _brouillon_pdf(client, jeton, projet, calcul_strict)

    assert un["deliverable_id"] != deux["deliverable_id"]
    _, chemin_un, sha_un, _ = _localisation(un["deliverable_id"])
    _, chemin_deux, sha_deux, _ = _localisation(deux["deliverable_id"])
    assert sha_un == sha_deux, (
        "deux compositions du meme calcul n'ont pas rendu les memes octets")
    assert chemin_un == chemin_deux


def test_le_pdf_et_le_html_du_meme_calcul_sont_deux_objets_distincts(
        client, jeton, projet, calcul_strict):
    """MEME CALCUL, DEUX FICHIERS — ET AUCUN NE DOIT ECRASER L'AUTRE.

    Les chemins different par l'extension ET par l'empreinte. Le contraire
    ferait qu'un depot PDF viendrait recouvrir la note HTML du meme calcul.
    """
    html = _brouillon(client, jeton, projet, calcul_strict)
    pdf = _brouillon_pdf(client, jeton, projet, calcul_strict)

    _, chemin_html, sha_html, _ = _localisation(html["deliverable_id"])
    _, chemin_pdf, sha_pdf, _ = _localisation(pdf["deliverable_id"])

    assert chemin_html != chemin_pdf
    assert sha_html != sha_pdf
    assert chemin_html.endswith(".html")
    assert chemin_pdf.endswith(".pdf")


def test_une_forme_inconnue_est_refusee_et_ne_depose_rien(
        client, jeton, projet_vierge, calcul_du_projet_vierge):
    """LE CHOIX EST BORNE PAR LE MODELE, DONC REFUSE AVANT TOUT DEPOT.

    `Literal["html", "pdf"]` fait rendre 422 a la validation du corps: la
    route n'est pas atteinte, et le magasin n'est pas touche.
    """
    prefixe = f"{projet_vierge['organization_id']}/" \
              f"{projet_vierge['project_id']}/"
    assert not _objets_du_magasin(prefixe)

    r = client.post(
        f"/v1/projects/{projet_vierge['project_id']}/deliverables",
        json={"calculation_id": calcul_du_projet_vierge, "format": "docx"},
        headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 422, r.text
    assert not _objets_du_magasin(prefixe)


def test_le_dossier_de_revue_d_un_pdf_porte_le_pdf_et_un_nom_distinct(
        client, jeton, projet, calcul_strict):
    """DEUX DOSSIERS DU MEME CALCUL DOIVENT SE DISTINGUER AU TELECHARGEMENT.

    Un relecteur qui demande le dossier de la note HTML puis celui de la note
    PDF recevait deux archives PORTANT LE MEME NOM: son navigateur les range
    en « (1) », et plus rien ne dit laquelle contient quoi.

    LA CAUSE ETAIT UN NOM RECALCULE. Le nom de l'archive etait reconstruit
    depuis le projet — `_nom_de_fichier(projet, calcul)` — au lieu de suivre le
    document reellement enregistre. Recalculer une valeur qui existe deja est
    exactement la façon dont deux verites divergent.
    """
    import io
    import zipfile

    html = _brouillon(client, jeton, projet, calcul_strict)
    pdf = _brouillon_pdf(client, jeton, projet, calcul_strict)

    noms = {}
    for etiquette, livrable in (("html", html), ("pdf", pdf)):
        r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                       f"{livrable['deliverable_id']}/review-bundle",
                       headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 200, r.text
        noms[etiquette] = r.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
            manifeste = json.loads(archive.read("manifeste.json"))
            octets = archive.read(f"documents/{livrable['filename']}")

        # LES OCTETS DANS L'ARCHIVE SONT CEUX DU MAGASIN, a l'octet pres.
        _, _, sha, taille = _localisation(livrable["deliverable_id"])
        assert hashlib.sha256(octets).hexdigest() == sha
        assert len(octets) == taille
        assert manifeste["files"][0]["sha256_recorded"] == sha
        assert manifeste["files"][0]["sha256_served"] == sha
        if etiquette == "pdf":
            assert octets.startswith(b"%PDF-"), (
                "l'archive du PDF ne contient pas un PDF")

    assert noms["html"] != noms["pdf"], (
        "les deux dossiers se telechargent sous le meme nom: "
        f"{noms['html']}")
