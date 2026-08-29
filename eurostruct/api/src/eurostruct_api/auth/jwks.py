"""Le trousseau JWKS, et sa rotation.

CE QUE CE MODULE EXISTE POUR EMPÊCHER
--------------------------------------
Deux fautes symétriques, et il faut les deux gardes :

* **ne jamais recharger.** Supabase fait tourner ses clés. Un trousseau figé au
  démarrage refuse, au bout de quelques semaines, tous les jetons légitimes —
  et la panne ressemble à une attaque ;
* **recharger à chaque `kid` inconnu.** Un `kid` inconnu est exactement ce
  qu'un attaquant met dans un jeton forgé. S'il déclenche un appel réseau, le
  premier venu pilote nos requêtes sortantes depuis un en-tête non
  authentifié. Le rechargement est donc **borné dans le temps** : au plus un
  par `DELAI_RECHARGEMENT_S`, et un `kid` toujours inconnu après cela est un
  refus, pas une nouvelle tentative.

CE QU'IL NE FAIT PAS
---------------------
Il ne va pas chercher la clé « la plus probable » quand le `kid` manque. Un
jeton sans `kid` face à un trousseau qui en contient plusieurs n'est pas
ambigu : il est irrecevable.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any

#: Fenêtre minimale entre deux rechargements déclenchés par un `kid` inconnu.
#: Un attaquant qui envoie mille jetons forgés provoque au plus un appel.
DELAI_RECHARGEMENT_S = 60.0

#: Au-delà, le trousseau est considéré comme périmé et rechargé de lui-même,
#: sans qu'un `kid` inconnu ait à le demander.
DUREE_DE_VIE_S = 600.0

#: Bornes de lecture réseau. Un JWKS qui ne répond pas doit faire échouer la
#: vérification, pas suspendre le processus.
DELAI_RESEAU_S = 5.0

#: Un JWKS légitime tient largement là-dedans. Une réponse plus grosse est
#: refusée sans être lue en entier.
TAILLE_MAX_OCTETS = 512 * 1024


class JwksIndisponible(RuntimeError):
    """Le trousseau n'a pas pu être obtenu. Refus, jamais repli."""


class CleInconnue(LookupError):
    """Aucune clé ne porte ce ``kid``, rechargement compris."""


def _lire_url(url: str) -> dict[str, Any]:
    requete = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_RESEAU_S) as reponse:
            brut = reponse.read(TAILLE_MAX_OCTETS + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as cause:
        raise JwksIndisponible(f"JWKS injoignable: {type(cause).__name__}") from cause
    if len(brut) > TAILLE_MAX_OCTETS:
        raise JwksIndisponible("JWKS anormalement volumineux: refuse sans lecture complete")
    try:
        document = json.loads(brut.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as cause:
        raise JwksIndisponible("JWKS illisible: ce n'est pas du JSON") from cause
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise JwksIndisponible("JWKS mal forme: aucune liste « keys »")
    return document


class TrousseauJwks:
    """Cache de clés publiques, rechargeable, borné, sûr en concurrence."""

    def __init__(self, url: str, *, lecteur=_lire_url) -> None:
        self._url = url
        self._lecteur = lecteur
        self._verrou = threading.Lock()
        self._cles: dict[str, Any] = {}
        self._charge_a: float = 0.0
        self._dernier_rechargement: float = 0.0
        #: Compteur d'appels réseau réellement effectués. Exposé pour que les
        #: tests puissent prouver le bornage plutôt que le supposer.
        self.appels_reseau = 0

    # ------------------------------------------------------------------ API
    def cle_pour(self, kid: str | None) -> Any:
        """Rend la clé publique du ``kid``, en rechargeant au plus une fois.

        :raises CleInconnue: ``kid`` absent, vide, ou introuvable après un
            rechargement autorisé.
        """
        if not kid:
            raise CleInconnue(
                "jeton sans « kid ». Choisir une cle « probable » dans un "
                "trousseau qui en contient plusieurs reviendrait a deviner "
                "qui a signe."
            )
        cle = self._chercher(kid)
        if cle is not None:
            return cle
        # KID INCONNU: on recharge, mais au plus une fois par fenêtre.
        if self._rechargement_autorise():
            self._recharger()
            cle = self._chercher(kid)
            if cle is not None:
                return cle
        raise CleInconnue(
            f"aucune cle publique ne porte ce « kid » ({_masque(kid)}), "
            "rechargement compris."
        )

    def precharger(self) -> int:
        """Charge le trousseau maintenant. Rend le nombre de clés.

        Utilisé par ``/ready`` : une configuration qui pointe vers un JWKS
        injoignable n'est pas une configuration prête.
        """
        self._recharger()
        return len(self._cles)

    # -------------------------------------------------------------- interne
    def _chercher(self, kid: str) -> Any | None:
        with self._verrou:
            perime = (time.monotonic() - self._charge_a) > DUREE_DE_VIE_S
            cle = self._cles.get(kid)
        if cle is not None and not perime:
            return cle
        if perime:
            # PERIMEE: on recharge de nous-mêmes, sans qu'un `kid` inconnu
            # ait eu à le demander. La rotation normale passe par ici.
            try:
                self._recharger()
            except JwksIndisponible:
                # Un trousseau périmé mais connu vaut mieux qu'un refus
                # général pendant une panne réseau — à condition que la clé
                # existe déjà. Une clé inconnue restera inconnue.
                pass
            with self._verrou:
                return self._cles.get(kid)
        return cle

    def _rechargement_autorise(self) -> bool:
        with self._verrou:
            return (time.monotonic() - self._dernier_rechargement) >= DELAI_RECHARGEMENT_S

    def _recharger(self) -> None:
        from jwt import PyJWK

        document = self._lecteur(self._url)
        self.appels_reseau += 1
        cles: dict[str, Any] = {}
        for jwk in document["keys"]:
            if not isinstance(jwk, dict):
                continue
            kid = jwk.get("kid")
            if not kid:
                # Une clé sans `kid` ne peut être désignée par aucun jeton:
                # la garder ferait croire le trousseau plus fourni qu'il n'est.
                continue
            try:
                cles[str(kid)] = PyJWK.from_dict(jwk).key
            except Exception:  # noqa: BLE001 — une clé illisible est ignorée,
                # jamais devinée. Les autres restent utilisables.
                continue
        if not cles:
            raise JwksIndisponible(
                "le JWKS ne contient aucune cle exploitable (kid + materiel "
                "cryptographique lisible)."
            )
        maintenant = time.monotonic()
        with self._verrou:
            self._cles = cles
            self._charge_a = maintenant
            self._dernier_rechargement = maintenant


def _masque(kid: str) -> str:
    """Un `kid` n'est pas un secret, mais il vient d'une entrée non fiable.

    On en montre assez pour diagnostiquer, jamais assez pour qu'un attaquant
    fasse d'un message d'erreur un oracle confortable.
    """
    return kid[:8] + "…" if len(kid) > 8 else kid
