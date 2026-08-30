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

LE BORNAGE DOIT ÊTRE ATOMIQUE, ET IL NE L'ÉTAIT PAS
----------------------------------------------------
Décider « ai-je le droit de recharger ? » puis recharger sont deux opérations.
Entre les deux, dix requêtes portant le même `kid` inconnu franchissaient
toutes le portillon avant qu'aucune n'ait posé la date : dix appels réseau. Le
bornage ne bornait donc rien **sous charge**, c'est-à-dire au seul moment où
il compte.

Le rechargement est désormais *single-flight* : un seul appel réseau est en vol
à la fois, et les autres demandeurs attendent son résultat au lieu d'en lancer
un second. La décision et l'action sont prises sous le même verrou.

LA TOLÉRANCE À LA PANNE EST BORNÉE, ELLE AUSSI
-----------------------------------------------
Quand le JWKS ne répond plus, servir une clé déjà connue vaut mieux qu'un refus
général : refuser tous les jetons ressemble à une attaque et coupe le service
pour une cause qui n'est pas de notre côté.

Mais cette tolérance ne peut pas être infinie. Sans borne, une panne de
plusieurs jours laisse accepter des jetons signés par une clé que l'émetteur a
peut-être révoquée entre-temps — et la rotation, qui existe précisément pour
cela, ne sert plus à rien. Au-delà de `AGE_MAX_CACHE_PERIME_S`, le trousseau
refuse **même une clé anciennement connue**, et le refus dit qu'on ne sait
plus, pas que le jeton est faux.

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

# LES TROIS DUREES CI-DESSOUS NE SONT PAS ALIGNEES SUR LA DOCUMENTATION
# SUPABASE, ET C'EST UN FAIT, PAS UN CHOIX.
#
#     alignement_durees_supabase = pending_verification
#
# CE QUI MANQUE, EXACTEMENT: les deux pages
# https://supabase.com/docs/guides/auth/signing-keys et
# https://supabase.com/docs/guides/auth/sessions — c'est-à-dire la durée de vie
# annoncée d'une clé de signature, le `Cache-Control` que l'émetteur pose sur
# son JWKS, la fenêtre de recouvrement d'une rotation, et la durée de vie d'un
# jeton d'accès. Sans ces quatre nombres, aligner reviendrait à en inventer
# quatre — précisément ce que l'interdiction sur les valeurs non tracées
# refuse, et une valeur inventée ici décide pendant combien de temps une clé
# RÉVOQUÉE reste acceptée.
#
# CE QUI A ÉTÉ TENTÉ ET N'A PAS ABOUTI: les deux pages ont été demandées depuis
# cet environnement; le proxy de sortie refuse `supabase.com`
# (EGRESS_BLOCKED). Aucune valeur n'a donc été relevée, et aucune n'a été
# devinée à la place.
#
# CE QUE VALENT LES TROIS VALEURS ACTUELLES: des bornes de PRUDENCE choisies
# par nous, documentées ligne à ligne, et volontairement plus courtes que ce
# qu'un émetteur tolérerait. Elles ne prétendent pas refléter Supabase.

#: Fenêtre minimale entre deux rechargements déclenchés par un `kid` inconnu.
#: Un attaquant qui envoie mille jetons forgés provoque au plus un appel.
DELAI_RECHARGEMENT_S = 60.0

#: Au-delà, le trousseau est considéré comme périmé et rechargé de lui-même,
#: sans qu'un `kid` inconnu ait à le demander.
DUREE_DE_VIE_S = 600.0

#: AU-DELÀ, ON REFUSE MÊME CE QU'ON CONNAÎT.
#:
#: C'est la borne de la tolérance à la panne. Une heure laisse largement passer
#: un incident réseau ou un redéploiement de l'émetteur ; elle ne laisse pas
#: passer une clé révoquée pendant un week-end. La valeur est un compromis
#: assumé, et elle est ici pour être discutée plutôt que découverte.
AGE_MAX_CACHE_PERIME_S = 3600.0

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
        #: L'ETAT DU VOL PARTAGE. `None` quand aucun appel n'est en cours;
        #: sinon l'`Event` que le meneur posera à la fin de SON appel, et que
        #: tous les autres attendent. C'est ce qui rend le rechargement
        #: réellement *single-flight*: un appel réseau, un seul résultat, et
        #: tout le monde le reçoit.
        self._vol: threading.Event | None = None
        self._cles: dict[str, Any] = {}
        self._charge_a: float = 0.0
        self._dernier_essai: float = 0.0
        #: Compteur d'appels réseau réellement effectués. Exposé pour que les
        #: tests puissent prouver le bornage plutôt que le supposer.
        self.appels_reseau = 0

    # ------------------------------------------------------------------ API
    def cle_pour(self, kid: str | None) -> Any:
        """Rend la clé publique du ``kid``, en rechargeant au plus une fois.

        :raises CleInconnue: ``kid`` absent, vide, ou introuvable après un
            rechargement autorisé.
        :raises JwksIndisponible: le cache est périmé au-delà de
            ``AGE_MAX_CACHE_PERIME_S`` et n'a pas pu être renouvelé. On ne sait
            plus — et on ne prétend pas savoir.
        """
        if not kid:
            raise CleInconnue(
                "jeton sans « kid ». Choisir une cle « probable » dans un "
                "trousseau qui en contient plusieurs reviendrait a deviner "
                "qui a signe."
            )

        cle, age = self._cle_et_age(kid)
        if cle is not None and age <= DUREE_DE_VIE_S:
            return cle

        # PÉRIMÉ, OU KID INCONNU: une seule et même réponse — tenter un
        # rechargement, borné dans le temps et unique en vol.
        self._recharger_si_permis()
        cle, age = self._cle_et_age(kid)

        # DEUX REFUS QUI NE DISENT PAS LA MÊME CHOSE, ET QU'IL NE FAUT PAS
        # CONFONDRE.
        #
        # ``CleInconnue`` dit « ce jeton nomme une clé que l'émetteur ne
        # publie pas » — c'est ce qu'on lit dans un jeton forgé.
        # ``JwksIndisponible`` dit « nous ne savons pas » — c'est notre côté
        # qui est en panne, et l'appelant doit le voir comme tel.
        #
        # Une rédaction intermédiaire les avait fusionnés: le rechargement
        # avalait la panne, le cache restait vide, et l'appel finissait en
        # « clé inconnue ». Une panne de notre JWKS se serait lue comme une
        # tentative d'intrusion, dans les journaux comme dans le diagnostic.
        if not self._contient_des_cles():
            raise JwksIndisponible(
                "aucune cle publique disponible: le JWKS n'a pas pu etre "
                "charge. Ce n'est pas un jeton douteux, c'est notre cote qui "
                "ne sait pas verifier."
            )

        if age > AGE_MAX_CACHE_PERIME_S:
            raise JwksIndisponible(
                f"trousseau perime depuis {int(age)} s (borne "
                f"{int(AGE_MAX_CACHE_PERIME_S)} s) et injoignable. Au-dela de "
                "cette borne une cle anciennement connue n'est plus une "
                "preuve: l'emetteur a pu la revoquer sans qu'on l'apprenne."
            )

        if cle is None:
            raise CleInconnue(
                f"aucune cle publique ne porte ce « kid » ({_masque(kid)}), "
                "rechargement compris."
            )
        # Connue, et le cache est périmé mais dans la tolérance: on sert.
        return cle

    def precharger(self) -> int:
        """Charge le trousseau maintenant, **inconditionnellement**.

        Réservé au démarrage et aux tests. ``/ready`` n'appelle PAS ceci — une
        sonde qui recharge à chaque passage martèle l'émetteur.
        """
        with self._verrou:
            self.appels_reseau += 1
        self._recharger()
        with self._verrou:
            return len(self._cles)

    def cache_frais(self) -> bool:
        """Le cache est-il utilisable sans aller sur le réseau ?

        C'est la question de ``/ready`` : « puis-je vérifier un jeton
        maintenant ? », et non « l'émetteur répond-il à l'instant ? ». La
        seconde question coûte un appel sortant à chaque sonde.
        """
        with self._verrou:
            return bool(self._cles) and (
                time.monotonic() - self._charge_a) <= DUREE_DE_VIE_S

    def assurer_charge(self) -> int:
        """Garantit un cache frais, en rechargeant seulement si nécessaire.

        Rend le nombre de clés. C'est ce qu'appelle ``/ready``.
        """
        if not self.cache_frais():
            self._recharger_si_permis()
        with self._verrou:
            if not self._cles:
                raise JwksIndisponible(
                    "aucune cle publique utilisable: le JWKS n'a jamais pu "
                    "etre charge.")
            if (time.monotonic() - self._charge_a) > AGE_MAX_CACHE_PERIME_S:
                raise JwksIndisponible(
                    "trousseau perime au-dela de la borne de tolerance.")
            return len(self._cles)

    def purger(self) -> None:
        """Vide le cache. Le prochain besoin rechargera.

        POURQUOI CETTE PRIMITIVE EXISTE, ET POURQUOI ELLE N'EST PAS UNE ROUTE.
        Une clé compromise doit pouvoir être chassée sans redémarrer le
        processus. Mais une route de purge, même « interne », offrirait au
        premier venu le moyen de vider notre cache puis de nous faire marteler
        l'émetteur : la purge s'appelle depuis le processus, jamais par HTTP.

        On remet aussi la date du dernier essai à zéro : purger pour découvrir
        qu'on doit attendre une minute avant de recharger n'aurait aucun sens.
        """
        with self._verrou:
            self._cles = {}
            self._charge_a = 0.0
            self._dernier_essai = 0.0

    def etat(self) -> dict[str, Any]:
        """Ce qu'on peut dire du cache **sans rien en révéler**.

        Des nombres et des booléens. Aucun ``kid``, aucun matériel
        cryptographique, aucune URL : un diagnostic qui recopie ce qu'il
        décrit est une fuite déguisée en aide au débogage.
        """
        with self._verrou:
            age = time.monotonic() - self._charge_a if self._charge_a else None
            return {
                "cles": len(self._cles),
                "age_s": None if age is None else round(age, 1),
                "frais": bool(self._cles) and age is not None
                         and age <= DUREE_DE_VIE_S,
                "appels_reseau": self.appels_reseau,
            }

    def vieillir_pour_essai(self, secondes: float) -> None:
        """Fait vieillir le cache de ``secondes``. **Tests uniquement.**

        Le vieillissement se mesure sur ``time.monotonic()``, qu'on ne peut pas
        déplacer. L'alternative — attendre une heure dans un test — n'en est
        pas une, et truquer l'horloge globale contaminerait tout le processus.
        On déplace donc la seule date que ce trousseau détient.
        """
        with self._verrou:
            self._charge_a -= secondes
            self._dernier_essai -= secondes

    # -------------------------------------------------------------- interne
    def _contient_des_cles(self) -> bool:
        with self._verrou:
            return bool(self._cles)

    def _cle_et_age(self, kid: str) -> tuple[Any | None, float]:
        with self._verrou:
            age = (time.monotonic() - self._charge_a) if self._charge_a \
                else float("inf")
            return self._cles.get(kid), age

    def _recharger_si_permis(self) -> None:
        """Recharge, au plus une fois par fenêtre, et **tout le monde attend**.

        CE QUE LA REDACTION PRECEDENTE NE FAISAIT PAS, ET QUI COMPTE SUR CACHE
        FROID. Le bornage par fenêtre était pris en premier: le premier fil
        posait ``_dernier_essai`` puis partait sur le réseau, et les suivants
        voyaient une date fraîche et **rendaient la main immédiatement** — avec
        un cache encore vide. Ils levaient alors ``JwksIndisponible`` alors que
        la réponse arrivait dans la milliseconde qui suivait: un 503 transitoire
        pour chaque requête concurrente au démarrage, exactement au moment où
        elles sont le plus nombreuses.

        « Un seul appel réseau » n'est donc pas la propriété qu'il faut: c'est
        « un seul appel réseau, et **le même résultat pour tous** ». Le vol est
        matérialisé par un ``Event``. Trois cas, et trois seulement:

        * un vol est en cours -> on l'attend, puis on relit le cache;
        * aucun vol, et la fenêtre est fermée -> on ne tente rien;
        * aucun vol, et la fenêtre est ouverte -> on devient le meneur.

        LE MENEUR SIGNALE TOUJOURS, panne comprise. Un ``Event`` jamais posé
        laisserait les autres attendre le délai plein pour rien.
        """
        while True:
            with self._verrou:
                vol = self._vol
                if vol is None:
                    maintenant = time.monotonic()
                    if self._dernier_essai and (
                            maintenant - self._dernier_essai
                    ) < DELAI_RECHARGEMENT_S:
                        # Fenêtre fermée ET personne en vol: il n'y a rien à
                        # attendre, et rien à tenter.
                        return
                    # LA DATE EST POSÉE AVANT L'APPEL, et c'est délibéré: elle
                    # borne les TENTATIVES, pas les succès. Un émetteur en
                    # panne ne doit pas être sollicité mille fois parce que
                    # mille tentatives ont échoué.
                    self._dernier_essai = maintenant
                    # L'APPEL EST COMPTÉ ICI, AVANT DE PARTIR. Le compter au
                    # retour ne comptait que les succès: le bornage se
                    # mesurait alors sur le seul cas où il n'est pas en jeu.
                    self.appels_reseau += 1
                    vol = threading.Event()
                    self._vol = vol
                    meneur = True
                else:
                    meneur = False

            if not meneur:
                # ON ATTEND LE RESULTAT DU MENEUR, PAS UN DELAI. La borne est
                # celle du réseau plus une marge: un meneur tué net ne doit
                # pas suspendre les autres pour toujours.
                if not vol.wait(timeout=DELAI_RESEAU_S * 2):
                    return
                # Le vol est fini. Si un AUTRE a redémarré entre-temps, la
                # boucle le verra; sinon on sort et l'appelant relit le cache.
                with self._verrou:
                    if self._vol is None or self._vol is vol:
                        return
                continue

            try:
                self._recharger()
            except JwksIndisponible:
                # Une panne n'est pas une exception ici: l'appelant décidera
                # s'il peut se contenter de ce qu'il a déjà, et jusqu'à quel
                # âge. Les attendants reçoivent le MEME verdict.
                pass
            finally:
                with self._verrou:
                    self._vol = None
                vol.set()
            return

    def _recharger(self) -> None:
        from jwt import PyJWK

        document = self._lecteur(self._url)
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
            self._dernier_essai = maintenant


def _masque(kid: str) -> str:
    """Un `kid` n'est pas un secret, mais il vient d'une entrée non fiable.

    On en montre assez pour diagnostiquer, jamais assez pour qu'un attaquant
    fasse d'un message d'erreur un oracle confortable.
    """
    return kid[:8] + "…" if len(kid) > 8 else kid
