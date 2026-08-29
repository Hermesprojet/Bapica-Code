"""La fabrique de connexion PostgreSQL, configurée par l'environnement seul.

CE QU'ELLE REFUSE
------------------
Une DSN absente ou illisible est un **refus**, pas un repli. Il n'existe ici
ni base par défaut, ni ``localhost`` implicite : une connexion devinée irait
vers une base que personne n'a désignée, et le provider y écrirait des
décisions d'autorité réelles.

POURQUOI ELLE VIT DANS CETTE COUCHE
------------------------------------
``creer_provider_de_production`` attend une ``FabriqueDeConnexion`` — un
appelable qui rend un objet satisfaisant le protocole ``Connexion``. Le moteur
ne connaît pas ``psycopg2`` et ne doit pas le connaître : c'est ce qui lui
permet d'être testé sans base et déployé sans pilote. Le pilote est une
dépendance de **cette** couche.

UNE CONNEXION PAR UNITÉ DE TRAVAIL, ET ELLE SE FERME
------------------------------------------------------
Pas de pool ici. ``_UniteDeTravail`` ouvre une transaction explicite, pose
``SET LOCAL eurostruct.actor_id``, et la transaction meurt avec le réglage.
Partager une connexion entre requêtes HTTP concurrentes ferait cohabiter deux
identités dans la même session : exactement la fuite que 6.3c interdit. Une
connexion par requête, fermée après, est plus lente et vérifiablement sûre.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from .config import ConfigurationInvalide, ReglagesBase

__all__ = ["FabriqueConnexionPostgres", "connexion_ephemere"]


class FabriqueConnexionPostgres:
    """Appelable qui ouvre une connexion PostgreSQL neuve. Rien de plus."""

    def __init__(self, reglages: ReglagesBase) -> None:
        if not reglages.configure:
            raise ConfigurationInvalide(
                "EUROSTRUCT_DATABASE_URL absente. Aucune base par defaut "
                "n'est choisie: une connexion devinee irait vers une base que "
                "personne n'a designee, et l'autorite y ecrirait pour de vrai."
            )
        self._dsn = reglages.dsn

    def __call__(self) -> Any:
        import psycopg2

        # `connect` leve si la DSN est invalide ou le serveur injoignable.
        # `creer_provider_de_production` enveloppe cette exception dans
        # `PiloteIndisponible`, qui est un refus explicite.
        connexion = psycopg2.connect(self._dsn)
        # AUTOCOMMIT COTE PILOTE, TRANSACTION EXPLICITE COTE UNITE DE TRAVAIL.
        # `_UniteDeTravail` emet `begin` lui-meme; laisser psycopg2 ouvrir sa
        # propre transaction implicite en superposerait une seconde, et le
        # `commit` de l'unite ne fermerait pas celle qu'on croit.
        connexion.autocommit = True
        return connexion


@contextmanager
def connexion_ephemere(fabrique: FabriqueConnexionPostgres):
    """Ouvre, prête, ferme. Le `finally` est le point.

    Une connexion laissée ouverte par un chemin d'erreur retient un backend
    PostgreSQL et, avec lui, tout réglage de session qui aurait survécu.
    """
    connexion = fabrique()
    try:
        yield connexion
    finally:
        try:
            connexion.close()
        except Exception:  # noqa: BLE001 — fermer ne doit jamais masquer
            pass
