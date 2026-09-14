"""Le parcours d'autorité complet, depuis l'API, sur un vrai PostgreSQL.

CE QUE CE MODULE ÉPROUVE, ET QUI N'EST ÉPROUVÉ NULLE PART AILLEURS
--------------------------------------------------------------------
``provider_contract.sh`` prouve que le provider pose l'identité que
l'authentificateur rend, avec un authentificateur **FICTIF**. Ici, les deux
identités A et B sont portées par des **jetons RSA signés**, vérifiés par
l'authentificateur de production, et la chaîne entière est traversée :

    jeton Bearer brut
      -> AuthentificateurSupabase (signature réellement vérifiée)
      -> ContexteAuthentifie
      -> creer_provider_de_production  (donc le crochet de production)
      -> transaction PostgreSQL explicite
      -> SET LOCAL eurostruct.actor_id
      -> primitive
      -> commit / rollback
      -> le contexte a disparu

CE QUI N'EST PAS UN SUPABASE RÉEL
----------------------------------
Le trousseau JWKS est local et les clés sont générées en mémoire. La
**vérification** est celle de production ; l'origine des clés ne l'est pas.
``SUPABASE_UNVERIFIED`` reste donc vrai : ce module ne prouve rien sur une
instance Supabase, et ne prétend pas le contraire.

Lancé par ``db/test/api_e2e.sh``, qui pose le décor et fournit la DSN par
l'environnement — jamais en argument, donc jamais visible dans ``ps``.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
#: DSN D'OBSERVATION SEULEMENT. Le login de service n'a aucun privilege de
#: table — tout passe par les trois primitives SECURITY DEFINER, et c'est
#: exactement ce qu'on veut. Mais prouver qu'un jeton forge n'a RIEN ecrit
#: demande de regarder la table. Aucune route ne voit cette DSN.
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_E2E_ACTEUR_A", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_E2E_ACTEUR_B", "")

#: ON SAUTE PAR MARQUEUR, PAS AU NIVEAU DU MODULE.
#:
#: `pytest.skip(allow_module_level=True)` empeche la COLLECTE: pytest rend
#: alors « 0 collecte, 1 execute » pour ce fichier, et `run_tests.sh` — qui
#: compare les deux, precisement pour reperer les tests qui disparaissent —
#: signalait « 32 collectes mais 33 executes ». L'instrument avait raison de
#: se plaindre: un module non collecte est un module dont on ne sait plus
#: combien de cas il porte.
#:
#: Avec un marqueur, les dix cas sont COLLECTES puis sautes: les deux comptes
#: coincident, et le nombre de cas reste visible meme sans decor.
DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A and ACTEUR_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par db/test/api_e2e.sh, qui "
                "pose la base deployee et fournit les DSN par l'environnement."),
    ),
]

ISSUER = "https://fictif.e2e.test/auth/v1"
AUDIENCE = "authenticated"
KID = "e2e-1"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def cle_etrangere():
    """Une clé que le trousseau ne publie pas. Sert au jeton forgé."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def application(cle):
    """L'application DE PRODUCTION, avec un trousseau local.

    Rien n'est substitué au-delà du trousseau : l'authentificateur, la
    fabrique de connexion et la factory de production sont ceux qui
    tourneront en exploitation.
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
def client(application):
    from fastapi.testclient import TestClient

    return TestClient(application)


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str, *, cle_de_signature=None) -> str:
        maintenant = int(time.time())
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + 3600},
            cle_de_signature or cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


#: Une empreinte de document FICTIVE, reconnaissable, et constante: ce module
#: n'eprouve pas le rapprochement au registre — c'est le travail de
#: `test_decision_vers_strict.py` — mais le cycle a quatre yeux lui-meme.
DOC_FICTIF = "e2e" + "0" * 61


def _dossier_fictif(subject_id: str) -> dict[str, str]:
    """Un dossier de revue structurellement valide, et entierement fictif.

    DEPUIS 0016, UNE DECISION « ndp_parameter » SE PROPOSE AVEC SON DOSSIER.
    Sans lui, elle pourrait etre approuvee et consommee sans produire aucun
    effet normatif — et c'est precisement le trou que 0016 ferme. Le refus
    tombe donc a la proposition, la ou l'auteur peut encore corriger.

    Les payloads sont produits par les fonctions canoniques du moteur: la base
    verifie que les citations sont scellees et que les quatre payloads disent
    ce qu'ils sont.
    """
    from eurostruct_engine.ndp.canonical import (
        CANONICALIZATION_VERSION,
        digest_of,
        evidence_digest,
    )
    from eurostruct_engine.ndp.confirmation import (
        EvidenceItem,
        NormativeStack,
        NormativeStackComponent,
        required_sources,
    )

    spec = digest_of({
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": subject_id, "rule_type": "scalar",
        "output_unit": "dimensionless", "value_provenance": "national_annex",
        "scalar_value": 0.85, "inputs": [], "domain": [],
        "expression_sources": [],
        "normative_authority": {
            "country_code": "BE", "reference": "FICTIF ANB",
            "edition": "2004", "clause": "§FICTIF",
            "effect": "FICTIF", "document_digest": DOC_FICTIF},
    })
    # ENTIEREMENT FICTIVE, ET C'EST LE POINT DE CE HARNAIS. Il eprouve les
    # trois primitives, pas la passerelle: son sujet n'existe dans aucun
    # registre, donc aucune empreinte d'implementation ne peut lui etre
    # derivee. Le dossier reste structurellement valide et normativement nul.
    impl = digest_of({
        "kind": "implementation",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": subject_id, "quoi": "FICTIF"})
    pile = NormativeStack.of(
        country_code="BE", standard_family="EN 1992", part="1-1",
        components=(NormativeStackComponent(
            "annexe", "FICTIF ANB", "2004", 1, DOC_FICTIF),))
    items = tuple(
        EvidenceItem(document_digest=s.document_digest, document_role=s.role,
                     reference=s.reference, edition=s.edition or "2004",
                     clause=s.clause, page_printed=1,
                     quote=f"FICTIF — citation pour {subject_id}.",
                     page_pdf=None)
        for s in required_sources(spec))
    preuve = evidence_digest(items)
    return {
        "rule_id": subject_id,
        "statement": f"FICTIF — dossier de {subject_id}.",
        "digest_algorithm": "sha256",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "normative_spec_payload": spec.canonical_payload,
        "implementation_payload": impl.canonical_payload,
        "evidence_payload": preuve.canonical_payload,
        "stack_payload": pile.digest.canonical_payload,
    }


def _proposition(suffixe: str) -> dict[str, object]:
    sujet = f"EN 1992-1-1:alpha_cc#{suffixe}"
    return {
        "subject_kind": "ndp_parameter",
        "subject_id": sujet,
        "org_id": None,
        "country_code": "BE",
        "standard_family": "EN 1992",
        "part": "1-1",
        "edition": "2004",
        "permission": "can_validate_normative_reference",
        "reason": f"FICTIF e2e {suffixe}",
        "review_package": _dossier_fictif(sujet),
    }


def _acteur_de_session() -> str:
    """Ce que la session voit MAINTENANT, hors transaction."""
    import psycopg2

    connexion = psycopg2.connect(DSN)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(
                "select coalesce(current_setting('eurostruct.actor_id', true), '')")
            ligne = curseur.fetchone()
            return (ligne[0] if ligne else "") or ""
    finally:
        connexion.close()


def _observer(requete: str, parametres: tuple) -> tuple:
    """Regarde la table depuis une connexion d'OBSERVATION, hors API."""
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(requete, parametres)
            return curseur.fetchone()
    finally:
        connexion.close()


# ------------------------------------------------------------------ le parcours
def test_ready_est_vert_sur_une_base_deployee(client):
    """Toute la chaîne est réellement disponible, provider compris."""
    r = client.get("/ready")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["ready"] is True
    noms = {v["nom"]: v["ok"] for v in corps["verifications"]}
    assert noms["jwks_joignable"] is True
    # C'est la verification qui traverse `creer_provider_de_production`, donc
    # le crochet `assert_provider_is_usable_in_production`.
    assert noms["provider_constructible"] is True
    # ET LA NOTE RESTE, SUR LE SEUL /ready REELLEMENT VERT DE TOUTE LA SUITE.
    # C'est ici qu'elle serait lue comme une garantie: base deployee, chaine
    # complete, tout au vert. Le trousseau reste pourtant local et les cles
    # sont nees dans ce processus — rien de tout cela ne dit quoi que ce soit
    # d'une instance Supabase.
    assert "SUPABASE_UNVERIFIED" in corps["notes"], (
        "la note a disparu sur un /ready vert obtenu avec un emetteur local")


def test_une_proposition_est_REELLEMENT_ecrite(client, jeton):
    """LE CAS QUI MANQUAIT, ET QUI A COUTE UN FAUX SUCCES COMPLET.

    La première fabrique de connexion posait ``autocommit = True``, en croyant
    laisser l'unité de travail gérer sa transaction. Mesure :

        autocommit=True  -> begin; insert; commit(); select -> 1 ligne
                         -> rollback;                  select -> 0 ligne
        autocommit=False -> begin; insert; commit(); select -> 1 ligne

    En autocommit, ``commit()`` de psycopg2 est un **no-op** : le pilote croit
    qu'aucune transaction n'est en cours, alors que le ``begin`` explicite en a
    ouvert une côté serveur. La fermeture de la connexion la rollbackait.

    ``POST /v1/authority/decisions`` rendait donc **201 avec un identifiant**
    — lu par ``returning`` DANS la transaction — et rien n'était écrit. Tous
    les cas qui n'observaient que le code de retour passaient au vert.

    Ce cas regarde la table depuis une AUTRE connexion. C'est la seule façon
    de distinguer « écrit » de « rendu ».
    """
    suffixe = uuid.uuid4().hex[:8]
    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]

    ligne = _observer(
        "select proposer_id::text, state::text "
        "from normative_authority_decisions where id = %s", (decision_id,))
    assert ligne is not None, (
        "201 rendu, aucune ligne en base: la transaction n'a pas ete validee")
    proposant, etat = ligne
    # ET LE PROPOSANT EST L'IDENTITE DU JETON, pas une valeur du corps.
    assert proposant == ACTEUR_A
    assert etat == "PENDING"


def test_parcours_quatre_yeux_complet(client, jeton):
    """A propose, A ne peut pas approuver, B approuve, on consomme une fois."""
    suffixe = uuid.uuid4().hex[:8]
    jeton_a, jeton_b = jeton(ACTEUR_A), jeton(ACTEUR_B)

    # 1. A PROPOSE. Aucun champ du corps ne nomme le proposant.
    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton_a))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]
    assert decision_id

    # 2. A NE PEUT PAS APPROUVER SA PROPRE PROPOSITION.
    # PostgreSQL refuse, par contrainte de table. L'API rend 422: c'est un
    # refus du domaine, pas une panne.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton_a))
    assert r.status_code == 422, r.text
    assert "result" not in r.json()

    # 3. B APPROUVE.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton_b))
    assert r.status_code == 204, r.text

    # 4. LA CONSOMMATION A LIEU UNE FOIS.
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton_b))
    assert r.status_code == 200, r.text
    assert r.json()["consumed"] is True

    # 5. ET LE REJEU EST REFUSE.
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton_b))
    assert r.status_code == 422, r.text


def test_jeton_forge_refuse_avant_toute_requete(client, jeton, cle_etrangere):
    """Signé par une clé que nous n'avons jamais publiée: 401, et rien n'est écrit.

    LE « AVANT TOUTE REQUETE » EST LA MOITIE QUI COMPTE. On vérifie qu'aucune
    décision n'est apparue — un refus qui laisse une ligne derrière lui n'est
    pas un refus.
    """
    suffixe = uuid.uuid4().hex[:8]
    sujet = _proposition(suffixe)["subject_id"]

    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton(ACTEUR_A, cle_de_signature=cle_etrangere)))
    assert r.status_code == 401, r.text

    reste = _observer("select count(*) from normative_authority_decisions "
                      "where subject_id = %s", (sujet,))
    assert reste[0] == 0, "une decision a ete ecrite malgre un jeton forge"


def test_sans_en_tete_authorization(client):
    r = client.post("/v1/authority/decisions", json=_proposition("x"))
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_schema_non_bearer_refuse(client, jeton):
    r = client.post("/v1/authority/decisions", json=_proposition("x"),
                    headers={"Authorization": "Basic " + jeton(ACTEUR_A)})
    assert r.status_code == 401


def test_aucun_endpoint_n_accepte_un_acteur(client, jeton):
    """Mentir dans le corps ne change pas l'identité.

    On envoie un ``actor_id`` en plus. Le contrat est ``Strict`` : le champ
    surnuméraire est refusé. C'est la propriété qui rend la vérification de
    signature non décorative.
    """
    corps = dict(_proposition(uuid.uuid4().hex[:8]))
    corps["actor_id"] = ACTEUR_B
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text


def test_contexte_absent_apres_commit(client, jeton):
    """Le réglage meurt avec la transaction. Vérifié sur une session neuve."""
    suffixe = uuid.uuid4().hex[:8]
    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    assert _acteur_de_session() == "", (
        "eurostruct.actor_id survit a la transaction: le contexte fuit")


def test_contexte_absent_apres_refus(client, jeton):
    """Après un rollback comme après une erreur, rien ne survit.

    L'approbation par le proposant lève côté PostgreSQL : l'unité de travail
    part donc par son chemin d'exception.
    """
    suffixe = uuid.uuid4().hex[:8]
    jeton_a = jeton(ACTEUR_A)
    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton_a))
    decision_id = r.json()["decision_id"]

    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton_a))
    assert r.status_code == 422
    assert _acteur_de_session() == "", (
        "eurostruct.actor_id survit a un rollback: le contexte fuit")


def test_identite_vient_du_jeton_et_non_du_corps(client, jeton):
    """B approuve une décision de A: c'est le JETON qui distingue les deux.

    Si l'identité venait d'ailleurs que du jeton, ce cas passerait avec deux
    jetons identiques. Il échoue.
    """
    suffixe = uuid.uuid4().hex[:8]
    r = client.post("/v1/authority/decisions", json=_proposition(suffixe),
                    headers=_entete(jeton(ACTEUR_A)))
    decision_id = r.json()["decision_id"]

    # Le MEME jeton (donc la meme identite) est refuse...
    assert client.post(f"/v1/authority/decisions/{decision_id}/approval",
                       headers=_entete(jeton(ACTEUR_A))).status_code == 422
    # ...et un jeton portant l'AUTRE sujet passe.
    assert client.post(f"/v1/authority/decisions/{decision_id}/approval",
                       headers=_entete(jeton(ACTEUR_B))).status_code == 204


# ---------------------------------------------------------------- la LECTURE
def _provider_de_service():
    """Le provider de production, sur la connexion de service du décor.

    Le login de service porte ``eurostruct_authority_backend``, que la
    politique de lecture des confirmations couvre en ``using (true)``.
    """
    import psycopg2

    from eurostruct_engine.ndp.postgres_provider import (
        PostgresConfirmationProvider,
        creer_contexte,
    )

    class _AuthDeLecture:
        """Aucune lecture ne l'appelle — et c'est la propriété qu'on montre.

        La lecture du référentiel normatif ne pose pas d'acteur: une
        confirmation belge vaut pour toutes les études belges. Si un jour un
        chemin de lecture authentifiait, ce double le dirait en levant.
        """

        identite_de_l_authentificateur = "e2e://lecture"
        est_fictif = False

        def authentifier(self, preuve):
            raise AssertionError(
                "la lecture des confirmations ne doit authentifier personne"
            )

        # Le protocole exige la forme; `creer_contexte` reste inutilisé ici.
        _ = creer_contexte

    connexion = psycopg2.connect(DSN)
    connexion.autocommit = False
    return PostgresConfirmationProvider(
        connexion=connexion, authentificateur=_AuthDeLecture(),
    ), connexion


def test_la_lecture_des_confirmations_traverse_un_vrai_postgresql():
    """Le SQL de lecture est accepté par le serveur, colonnes comprises.

    CE QUE CE CAS ATTRAPE ET QUE LES AUTRES NE PEUVENT PAS. Les vingt-et-un
    cas de ``test_projection.py`` tournent sans base : ils prouvent la
    projection, pas que ``COLONNES_CONFIRMATION`` nomme des colonnes qui
    existent. Un nom mal orthographié y passerait inaperçu et ne se
    manifesterait qu'en exploitation.

    Zéro confirmation est ici la **bonne** réponse — aucune n'a été signée sur
    cette base — et elle n'est acceptable que parce que le garde de rôle a
    répondu avant : sans lui, zéro ligne ne se distinguerait pas d'un refus.
    """
    provider, connexion = _provider_de_service()
    try:
        assert provider.confirmations_for("be.ec2.aucune_regle_de_ce_nom") == ()
        assert provider.revocations_for("be.ec2.aucune_regle_de_ce_nom") == ()
    finally:
        connexion.close()


def test_le_role_de_service_est_couvert_par_une_politique_de_lecture():
    """Le garde interroge PostgreSQL, il ne suppose pas.

    Si la migration cessait un jour d'accorder ``eurostruct_authority_backend``
    au login de service, ce cas tomberait — et ``confirmations_for``
    refuserait au lieu de rendre un tuple vide trompeur.
    """
    provider, connexion = _provider_de_service()
    try:
        # Ne lève pas: c'est l'assertion.
        provider._exiger_un_role_qui_voit()
    finally:
        connexion.close()


def test_la_lecture_ne_laisse_aucune_transaction_ouverte():
    """Une lecture qui garde sa transaction tient un instantané indéfiniment.

    ``idle in transaction`` est ce qui empêche ``VACUUM`` de récupérer les
    versions mortes: une connexion de service oubliée là fait grossir la base
    sans que rien n'échoue.
    """
    import psycopg2.extensions as ext

    provider, connexion = _provider_de_service()
    try:
        provider.confirmations_for("be.ec2.aucune_regle_de_ce_nom")
        assert connexion.get_transaction_status() == ext.TRANSACTION_STATUS_IDLE
    finally:
        connexion.close()


def test_la_lecture_n_emet_aucun_avertissement_postgresql():
    """« there is already a transaction in progress », a chaque lecture.

    CE QUE CE CAS A TROUVE. Le garde de role interrogeait la base sur son
    propre curseur AVANT la requete. Avec une connexion en
    ``autocommit=False``, ce premier ordre ouvre deja la transaction : le
    ``begin`` explicite qui suivait arrivait donc toujours en second, et
    PostgreSQL repondait par un WARNING — a chaque lecture, sans que rien
    n'echoue.

    Un avertissement que personne ne regarde est un defaut qui dure. Ce cas le
    regarde.
    """
    provider, connexion = _provider_de_service()
    try:
        del connexion.notices[:]
        provider.confirmations_for("be.ec2.aucune_regle_de_ce_nom")
        provider.revocations_for("be.ec2.aucune_regle_de_ce_nom")
        avertissements = [n.strip() for n in connexion.notices]
        assert not avertissements, avertissements
    finally:
        connexion.close()
