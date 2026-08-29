"""``/health`` et ``/ready`` ne répondent pas à la même question.

* ``/health`` : *le processus est-il vivant ?* Il ne touche ni la base ni le
  réseau. Un ``/health`` qui interroge PostgreSQL fait redémarrer un processus
  parfaitement sain parce qu'une base est lente — c'est une panne fabriquée
  par la sonde.
* ``/ready`` : *puis-je servir une requête d'autorité maintenant ?* Il vérifie
  pour de vrai — le JWKS est joignable, la base s'ouvre, et
  ``creer_provider_de_production`` rend un objet. Sans ces trois-là, la
  réponse est **503**, pas « probablement ».

CE QUE ``/ready`` NE RÉVÈLE PAS
--------------------------------
Aucune DSN, aucune URL complète, aucun secret, aucun fragment de jeton.
Il rend des booléens et des noms de vérifications. Un diagnostic qui recopie
un mot de passe pour dire qu'il est présent est une fuite déguisée en aide au
débogage.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

routeur = APIRouter(tags=["exploitation"])


@routeur.get("/health")
def sante() -> dict[str, Any]:
    """Le processus répond. Rien de plus n'est affirmé."""
    from .. import __version__

    return {"status": "ok", "service": "eurostruct-api", "version": __version__}


@routeur.get("/ready")
def pret(requete: Request, reponse: Response) -> dict[str, Any]:
    """Chaque dépendance est éprouvée, pas supposée."""
    etat = requete.app.state
    reglages = etat.reglages
    verifications: list[dict[str, Any]] = []

    # 1. CONFIGURATION D'AUTHENTIFICATION
    diag = reglages.diagnostic()
    verifications.append({
        "nom": "auth_configuree",
        "ok": diag["auth"]["configure"],
        "detail": diag["auth"],
    })

    # 2. LE JWKS EST-IL REELLEMENT JOIGNABLE ?
    # Une URL posee mais injoignable n'est pas une configuration prete: tous
    # les jetons seraient refuses, et le refus ressemblerait a une attaque.
    if diag["auth"]["configure"] and etat.authentificateur is not None:
        try:
            n = etat.authentificateur.precharger_trousseau()
            verifications.append({"nom": "jwks_joignable", "ok": True,
                                  "detail": {"cles": n}})
        except Exception as cause:  # noqa: BLE001 — la cause est resumee, pas recopiee
            verifications.append({"nom": "jwks_joignable", "ok": False,
                                  "detail": {"echec": type(cause).__name__}})
    else:
        verifications.append({"nom": "jwks_joignable", "ok": False,
                              "detail": {"echec": "auth non configuree"}})

    # 3. CONFIGURATION DE BASE
    verifications.append({
        "nom": "base_configuree",
        "ok": diag["base"]["configure"],
        "detail": diag["base"],
    })

    # 4. LA BASE S'OUVRE-T-ELLE, ET LE PROVIDER SE CONSTRUIT-IL ?
    # C'est la verification qui compte: elle traverse
    # `creer_provider_de_production`, donc le crochet
    # `assert_provider_is_usable_in_production`.
    if diag["base"]["configure"] and etat.fabrique_connexion is not None \
            and etat.authentificateur is not None:
        verifications.append(_verifier_provider(etat))
    else:
        verifications.append({"nom": "provider_constructible", "ok": False,
                              "detail": {"echec": "base ou auth non configuree"}})

    tout_ok = all(v["ok"] for v in verifications)
    if not tout_ok:
        reponse.status_code = 503
    return {
        "ready": tout_ok,
        "verifications": verifications,
        # SUPABASE_UNVERIFIED reste vrai tant qu'un staging reel n'a pas ete
        # eprouve de bout en bout. `/ready` vert sur une instance locale ne
        # vaut pas preuve de compatibilite Supabase.
        "notes": ["SUPABASE_UNVERIFIED"] if not tout_ok else [],
    }


def _verifier_provider(etat: Any) -> dict[str, Any]:
    from eurostruct_engine.ndp.provider_factory import (
        creer_provider_de_production,
    )

    connexion = None

    def _fabrique() -> Any:
        nonlocal connexion
        connexion = etat.fabrique_connexion()
        return connexion

    try:
        creer_provider_de_production(
            fabrique_de_connexion=_fabrique,
            authentificateur=etat.authentificateur,
        )
        return {"nom": "provider_constructible", "ok": True,
                "detail": {"factory": "creer_provider_de_production"}}
    except Exception as cause:  # noqa: BLE001
        return {"nom": "provider_constructible", "ok": False,
                "detail": {"echec": type(cause).__name__}}
    finally:
        if connexion is not None:
            try:
                connexion.close()
            except Exception:  # noqa: BLE001
                pass
