"""Décor commun. Des clés RSA VRAIES, générées ici, et jamais un secret réel.

POURQUOI DE VRAIES CLÉS PLUTÔT QU'UN AUTHENTIFICATEUR DE TEST
--------------------------------------------------------------
Un double qui rendrait ``est_fictif = False`` pour satisfaire la factory
serait exactement ce que le dépôt interdit : un décor promu au rang de preuve.
On garde donc l'authentificateur **de production**, et on lui donne un
trousseau JWKS local alimenté par une paire de clés générée dans le processus
de test. La signature est réellement vérifiée ; seule l'origine du trousseau
change, et elle est injectée par un paramètre prévu pour cela.

Aucune clé n'est écrite sur disque, aucune valeur d'environnement réelle n'est
lue, et rien de tout ceci n'existe en dehors des tests.
"""
from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://fictif.supabase.test/auth/v1"
AUDIENCE = "authenticated"
KID = "cle-de-test-1"
KID_AUTRE = "cle-de-test-2"


@pytest.fixture(scope="session")
def paire_rsa() -> dict[str, Any]:
    """Une paire RSA de test, générée en mémoire."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {"privee": cle, "publique": cle.public_key()}


@pytest.fixture(scope="session")
def paire_rsa_etrangere() -> dict[str, Any]:
    """Une SECONDE paire, qui n'est dans aucun trousseau.

    Elle sert à fabriquer des jetons parfaitement bien formés et correctement
    signés — mais par quelqu'un que nous n'avons jamais publié.
    """
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {"privee": cle, "publique": cle.public_key()}


def _jwk_de(cle_publique: Any, kid: str) -> dict[str, Any]:
    from jwt.algorithms import RSAAlgorithm
    import json as _json

    jwk = _json.loads(RSAAlgorithm.to_jwk(cle_publique))
    jwk["kid"] = kid
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return jwk


@pytest.fixture()
def trousseau_local(paire_rsa):
    """Un ``TrousseauJwks`` dont le lecteur réseau est remplacé.

    Le remplacement porte sur **l'accès réseau**, pas sur la vérification :
    ``cle_pour`` et toute la logique de rotation restent celles du produit.
    """
    from eurostruct_api.auth.jwks import TrousseauJwks

    document = {"keys": [_jwk_de(paire_rsa["publique"], KID)]}
    return TrousseauJwks("https://fictif.invalid/jwks", lecteur=lambda _url: document)


@pytest.fixture()
def reglages_auth():
    from eurostruct_api.config import ReglagesAuth

    return ReglagesAuth(
        jwks_url="https://fictif.invalid/jwks",
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithmes=("RS256",),
        tolerance_horloge_s=0,
    )


@pytest.fixture()
def authentificateur(reglages_auth, trousseau_local):
    """L'authentificateur DE PRODUCTION, avec un trousseau local."""
    from eurostruct_api.auth.supabase import AuthentificateurSupabase

    return AuthentificateurSupabase(reglages_auth, trousseau=trousseau_local)


@pytest.fixture()
def forger(paire_rsa):
    """Fabrique un jeton signé par la clé du trousseau."""

    def _forger(*, sub: str = "11111111-1111-1111-1111-111111111111",
                iss: str = ISSUER, aud: str = AUDIENCE,
                exp_dans_s: int = 3600, nbf_dans_s: int = -10,
                kid: str = KID, alg: str = "RS256",
                cle: Any = None, **extra: Any) -> str:
        maintenant = int(time.time())
        charge: dict[str, Any] = {
            "iss": iss, "aud": aud, "sub": sub,
            "iat": maintenant - 10,
            "nbf": maintenant + nbf_dans_s,
            "exp": maintenant + exp_dans_s,
        }
        charge.update(extra)
        for vide in [k for k, v in charge.items() if v is None]:
            del charge[vide]
        return jwt.encode(charge, cle or paire_rsa["privee"],
                          algorithm=alg, headers={"kid": kid})

    return _forger


@pytest.fixture()
def application(reglages_auth, authentificateur):
    """Application sans base : suffit pour les calculs et les refus JWT."""
    from eurostruct_api.app import creer_application
    from eurostruct_api.config import Reglages, ReglagesBase

    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn="")))
    app.state.authentificateur = authentificateur
    return app


@pytest.fixture()
def client(application):
    from fastapi.testclient import TestClient

    return TestClient(application)
