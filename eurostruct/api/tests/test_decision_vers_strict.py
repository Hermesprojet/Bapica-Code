"""De la décision consommée jusqu'au calcul strict, par les routes publiques.

CE QUE CE MODULE ÉPROUVE, ET QU'AUCUN AUTRE N'ÉPROUVE
-------------------------------------------------------
``test_e2e_postgres.py`` prouve que le quatre-yeux fonctionne : proposer,
refuser l'auto-approbation, approuver, consommer une fois. Il s'arrête là.
``test_passerelle.py`` prouve que la passerelle sait lire des confirmations et
ouvrir le portillon — mais il les lui **fournit** par un provider fictif.

Entre les deux, il manquait le fil : *une décision consommée produit-elle une
confirmation que le provider PostgreSQL relit ?* Les deux chemins étaient
disjoints, et aucun test ne pouvait le voir parce qu'aucun ne les traversait
tous les deux.

**AUCUN PROVIDER FICTIF ICI.** Le provider est celui de production, sur la base
jetable ; les jetons sont signés ; les routes sont publiques. La seule chose
qui ne soit pas de production est l'origine des clés RSA.

Lancé par ``db/test/decision_vers_strict.sh``, qui pose le décor et fournit les
DSN par l'environnement — jamais en argument, donc jamais visible dans ``ps``.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_E2E_ACTEUR_A", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_E2E_ACTEUR_B", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A and ACTEUR_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/decision_vers_strict.sh."),
    ),
]

ISSUER = "https://fictif.decision.test/auth/v1"
AUDIENCE = "authenticated"
KID = "decision-1"
PAYS = "BE"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def application(cle):
    """L'application DE PRODUCTION. Seul le trousseau est local."""
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
    def _jeton(sub: str) -> str:
        maintenant = int(time.time())
        import jwt as pyjwt

        return pyjwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + 3600},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


# ------------------------------------------------------------------ le calcul
def _requete_stricte() -> dict:
    return {
        "project_id": "FICTIF-DEC", "element": "P1", "country": PAYS,
        "strict_ndp": True,
        "M_Ed": {"value": 150, "unit": "kN*m"},
        "section": {"b": {"value": 300, "unit": "mm"},
                    "h": {"value": 500, "unit": "mm"},
                    "d": {"value": 450, "unit": "mm"}},
        "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
    }


def _blocages(client) -> list[str]:
    """Les clés que le calcul strict refuse, telles que l'API les rend."""
    r = client.post("/v1/calculations/ec2/beam-flexure", json=_requete_stricte())
    if r.status_code == 200:
        return []
    assert r.status_code == 422, r.text
    # LE CORPS EST L'`EngineErrorDTO` LUI-MEME, pas un `detail` qui l'enveloppe:
    # `reponse_de_refus` le rend tel quel, et son champ `detail` est une PHRASE.
    corps = r.json()
    preflight = corps.get("preflight") or {}
    return [b["key"] for b in preflight.get("blocking", [])]


def _parametre(cle: str):
    """La fiche du registre pour cette clé. On ne recopie rien à la main."""
    from eurostruct_engine.ndp import load_parameter_set

    jeu = load_parameter_set(PAYS, strict=True)
    p = jeu.find(cle)
    assert p is not None, f"{cle} absent du registre"
    return p


# ---------------------------------------------------------------- le parcours
def test_le_calcul_strict_refuse_et_nomme_ses_blocages(client):
    """Le point de départ, et il est mesuré, pas supposé."""
    blocages = _blocages(client)
    assert len(blocages) == 8, (
        f"{len(blocages)} blocage(s) au lieu de 8: {blocages}")


def test_une_decision_consommee_debloque_le_parametre_qu_elle_vise(client, jeton):
    """LE FIL QUI MANQUAIT, ÉPROUVÉ PAR LES ROUTES PUBLIQUES.

    A propose le dossier exact d'un paramètre, ne peut pas s'approuver, B
    approuve, la décision se consomme — et le calcul strict doit alors cesser
    de bloquer **sur cette clé-là**, et sur elle seule.

    Aujourd'hui ce cas est ROUGE : ``normative_decision_consume()`` change
    l'état de la décision et écrit l'audit, mais ne produit **aucun effet
    normatif**. Le provider ne relit donc rien, et le blocage demeure.
    """
    avant = _blocages(client)
    assert avant, "aucun blocage au depart: le cas ne prouverait rien"
    cle_visee = avant[0]
    p = _parametre(cle_visee)

    corps = {
        "subject_kind": "ndp_parameter",
        "subject_id": cle_visee,
        "org_id": None,
        "country_code": p.country_code,
        "standard_family": p.standard_family,
        "part": p.part,
        "edition": p.edition,
        "permission": "can_validate_normative_reference",
        "reason": f"FICTIF revue de {cle_visee} pour la preuve de bout en bout",
    }

    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]

    # A ne peut pas s'approuver.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text

    # B approuve.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 204, r.text

    # Consommation.
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 200, r.text
    assert r.json()["consumed"] is True

    # ET LE CALCUL STRICT DOIT CESSER DE BLOQUER SUR CETTE CLE.
    apres = _blocages(client)
    assert cle_visee not in apres, (
        f"« {cle_visee} » bloque encore apres une decision CONSOMMEE. La "
        "decision a change d'etat sans produire d'effet normatif: aucune "
        "confirmation n'a ete creee, et le provider ne relit rien.")
    assert set(apres) == set(avant) - {cle_visee}, (
        "la consommation a debloque autre chose que le parametre vise: "
        f"avant {sorted(avant)}, apres {sorted(apres)}")


def test_une_consommation_cree_une_trace_normative_durable(client, jeton):
    """LA MOITIÉ QUE LE CODE DE RETOUR NE DIT PAS.

    Un 200 sur la consommation ne prouve pas qu'un effet a été produit — c'est
    exactement la leçon de ``autocommit=True``. On regarde la table depuis une
    AUTRE connexion.
    """
    import psycopg2

    avant = _blocages(client)
    assert avant
    cle_visee = avant[-1]
    p = _parametre(cle_visee)

    corps = {
        "subject_kind": "ndp_parameter", "subject_id": cle_visee,
        "org_id": None, "country_code": p.country_code,
        "standard_family": p.standard_family, "part": p.part,
        "edition": p.edition,
        "permission": "can_validate_normative_reference",
        "reason": f"FICTIF trace durable pour {cle_visee}",
    }
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]
    client.post(f"/v1/authority/decisions/{decision_id}/approval",
                headers=_entete(jeton(ACTEUR_B)))
    client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                headers=_entete(jeton(ACTEUR_B)))

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(
                "select count(*) from normative_rule_confirmations "
                " where rule_id = %s", (cle_visee,))
            combien = curseur.fetchone()[0]
    finally:
        connexion.close()

    assert combien >= 2, (
        f"{combien} confirmation(s) pour « {cle_visee} » apres une decision "
        "consommee. Le quatre-yeux exige DEUX regards, et la consommation "
        "doit les produire de facon durable — sinon la decision n'a produit "
        "aucun effet normatif.")


def test_le_referentiel_versionne_reste_a_zero_sur_zero_vingt_neuf():
    """LE DÉCOR EST JETABLE, LE DÉPÔT NE BOUGE PAS.

    Rien de ce parcours n'écrit dans les fichiers du registre. Un `confirmed`
    y resterait, et le mode strict s'ouvrirait pour tout le monde.
    """
    from eurostruct_engine.ndp import available_countries, load_parameter_set

    for pays in available_countries():
        jeu = load_parameter_set(pays, strict=True)
        utilisables = [k for k in jeu.keys()
                       if (p := jeu.find(k)) is not None
                       and p.usable_in_strict_mode]
        assert utilisables == [], f"{pays}: {utilisables}"


def test_aucun_corps_ne_peut_nommer_un_verificateur(client, jeton):
    """Le client ne fournit ni ``verifier_id``, ni proposant, ni approbateur."""
    corps = {
        "subject_kind": "ndp_parameter",
        "subject_id": "EN 1992-1-1:alpha_cc",
        "org_id": None, "country_code": PAYS,
        "standard_family": "EN 1992", "part": "1-1", "edition": "2010",
        "permission": "can_validate_normative_reference",
        "reason": "FICTIF",
        "verifier_id": str(uuid.uuid4()),
    }
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
