"""La seule façon officielle d'obtenir un provider de **production**.

CE QUE CE MODULE N'EST PAS
---------------------------
Ce n'est pas une route. Aucun chemin produit ne consomme aujourd'hui de
:class:`ConfirmationProvider` — mesuré sur l'ensemble du dépôt le 28/08 :
``confirmations_for``, ``revocations_for`` et
``assert_provider_is_usable_in_production`` ne sont appelés que par des tests.
Inventer un point d'entrée pour faire semblant du contraire donnerait une
fausse assurance.

CE QU'IL EST
-------------
Une **composition minimale fail-closed**, pour que le jour où un consommateur
existera, le chemin sûr soit déjà là et soit le seul praticable. La factory :

* ne construit **que** :class:`PostgresConfirmationProvider` ;
* exige une configuration PostgreSQL explicite ;
* exige un authentificateur **concret et non fictif** ;
* exige le pilote — son absence est un refus, jamais un repli ;
* appelle **effectivement**
  :func:`assert_provider_is_usable_in_production` avant de rendre l'objet ;
* n'a aucun repli mémoire, et ne choisit jamais une fixture par son nom.

Le provider mémoire reste disponible pour les tests et pour le moteur ; il
n'est simplement pas atteignable *par ici*.

POURQUOI LE CROCHET DOIT ÊTRE APPELÉ ICI
-----------------------------------------
``assert_provider_is_usable_in_production`` existait déjà, et **rien ne
l'appelait** hors des tests. Un crochet que seul le test invoque protège le
test, pas le produit. La factory est l'endroit où il devient inévitable :
on ne peut pas obtenir un provider de production sans l'avoir traversé.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .confirmation import (
    ConfirmationProvider,
    assert_provider_is_usable_in_production,
)
from .postgres_provider import (
    AuthentificationRequise,
    Authentificateur,
    Connexion,
    PostgresConfirmationProvider,
)

__all__ = [
    "ConfigurationProviderInvalide",
    "PiloteIndisponible",
    "FabriqueDeConnexion",
    "creer_provider_de_production",
]


class ConfigurationProviderInvalide(ValueError):
    """La configuration ne permet pas de construire un provider de production.

    Distincte de :class:`PiloteIndisponible` : ici la demande elle-même est mal
    formée, et aucun pilote n'y changerait rien.
    """


class PiloteIndisponible(RuntimeError):
    """Aucun pilote PostgreSQL utilisable.

    C'est un **refus**, jamais un repli. Un repli mémoire à cet endroit
    rendrait une règle réelle confirmée par des confirmations fabriquées, pour
    toute une juridiction, sans que personne n'ait lu l'annexe.
    """


@runtime_checkable
class FabriqueDeConnexion(Protocol):
    """Ce que l'appelant fournit pour ouvrir la connexion.

    Le module ne connaît **pas** ``psycopg2`` : il reçoit de quoi ouvrir une
    connexion et vérifie que le résultat satisfait :class:`Connexion`. Cela
    garde le moteur sans dépendance de pilote — la règle du paquet — tout en
    refusant l'absence de pilote au lieu de la contourner.
    """

    def __call__(self) -> Connexion: ...


def creer_provider_de_production(
    *,
    fabrique_de_connexion: FabriqueDeConnexion,
    authentificateur: Authentificateur,
) -> ConfirmationProvider:
    """Rend un provider de production, ou lève. Jamais de troisième issue.

    Les deux paramètres sont **nommés obligatoirement** : un appel positionnel
    permettrait d'inverser silencieusement la connexion et l'authentificateur,
    et la construction réussirait en plaçant l'authentification du mauvais
    côté de la frontière.

    Aucun paramètre ne reçoit d'acteur. L'identité vient de
    l'authentificateur, à l'ouverture de chaque unité de travail, et de nulle
    part ailleurs — c'est la propriété A1 du contrat du provider.
    """
    if fabrique_de_connexion is None or not callable(fabrique_de_connexion):
        raise ConfigurationProviderInvalide(
            "aucune fabrique de connexion fournie. La factory de production "
            "n'ouvre pas de connexion implicite: une connexion devinee irait "
            "vers une base que personne n'a designee."
        )
    if authentificateur is None:
        raise AuthentificationRequise(
            "aucun authentificateur fourni. Le sous-systeme d'autorite reste "
            "BLOCKED_BY_REAL_AUTH: refus avant toute requete privilegiee."
        )
    if not isinstance(authentificateur, Authentificateur):
        raise AuthentificationRequise(
            "l'objet fourni comme authentificateur ne satisfait pas le "
            "protocole Authentificateur: il ne peut pas produire d'identite, "
            "et la factory refuse plutot que de deviner."
        )

    # L'AUTHENTIFICATEUR FICTIF EST REFUSE ICI, ET PAS SEULEMENT PLUS TARD.
    # `assert_provider_is_usable_in_production` le refuserait de toute facon a
    # la fin, mais construire d'abord ouvrirait une connexion pour un objet
    # qu'on sait deja irrecevable.
    if getattr(authentificateur, "est_fictif", True):
        raise ConfigurationProviderInvalide(
            "authentificateur FICTIF refuse par la factory de production. Un "
            "provider branche sur un authentificateur de test n'est pas "
            "« presque reel »: les identites qu'il pose sont fabriquees."
        )

    try:
        connexion: Any = fabrique_de_connexion()
    except Exception as cause:  # noqa: BLE001 — la cause est rendue telle quelle
        raise PiloteIndisponible(
            f"la connexion PostgreSQL n'a pas pu etre ouverte ({cause}). "
            "C'est un refus: il n'existe aucun repli memoire, et un provider "
            "fictif rendrait une regle REELLE confirmee."
        ) from cause

    if connexion is None or not isinstance(connexion, Connexion):
        raise PiloteIndisponible(
            "la fabrique n'a pas rendu un objet satisfaisant le protocole "
            "Connexion (cursor/commit/rollback). Le pilote est absent ou "
            "inattendu; la factory refuse au lieu de deviner."
        )

    provider = PostgresConfirmationProvider(
        connexion=connexion, authentificateur=authentificateur,
    )

    # LE CROCHET EST APPELE, ET C'EST TOUT L'OBJET DE CE MODULE. Il existait
    # deja et rien ne l'appelait hors des tests: un crochet que seul le test
    # invoque protege le test, pas le produit.
    assert_provider_is_usable_in_production(provider)
    return provider
