"""L'authentificateur Supabase réel. Il vit ici, jamais dans le moteur.

CE QU'IL EST
-------------
Une implémentation concrète du protocole ``Authentificateur`` défini par
``eurostruct_engine.ndp.postgres_provider``. Il transforme un **jeton porteur
brut** en ``ContexteAuthentifie``, ou il lève. Jamais de troisième issue, et
jamais ``None``.

``est_fictif`` rend ``False`` — et c'est la seule chose de tout le dépôt qui a
le droit de le faire en dehors d'un test. La factory de production refuse les
authentificateurs fictifs ; c'est cette classe, et sa vérification de
signature, qui justifie le ``False``.

CE QU'IL VÉRIFIE, ET POURQUOI CHACUN COMPTE
--------------------------------------------
=========================  =================================================
vérification               ce qu'elle empêche
=========================  =================================================
signature                  un jeton fabriqué de toutes pièces
algorithme dans une liste  la substitution d'algorithme: ``none``, ou ``HS256``
                           signé avec la clé publique du JWKS
``kid`` connu              une clé que nous n'avons jamais publiée
``iss``                    un jeton d'un AUTRE projet Supabase, correctement
                           signé par lui
``aud``                    un jeton légitime destiné à une autre application
``exp``                    la réutilisation d'un jeton périmé
``nbf``                    un jeton pré-daté
``sub``                    un jeton valide qui ne nomme personne
=========================  =================================================

L'ordre n'est pas indifférent : ``pyjwt`` vérifie la signature **avant** les
revendications. Une charge utile n'est jamais lue avant d'être prouvée.

CE QU'IL NE FAIT PAS
---------------------
Il ne lit aucun ``actor_id`` d'un corps de requête, d'un paramètre ou d'un
en-tête. L'identité sort du jeton vérifié, et de là seulement — c'est la
propriété A1 du contrat du provider, et la raison d'être de tout 6.3c.
"""
from __future__ import annotations

from typing import Any

import jwt
from eurostruct_engine.ndp.postgres_provider import (
    AuthentificationRequise,
    ContexteAuthentifie,
    creer_contexte,
)

from ..config import ReglagesAuth
from .jwks import CleInconnue, JwksIndisponible, TrousseauJwks

__all__ = ["AuthentificateurSupabase"]


class AuthentificateurSupabase:
    """Vérifie un jeton Supabase et en tire une identité.

    Satisfait ``Authentificateur`` structurellement : deux propriétés et une
    méthode. Le provider ne connaît pas cette classe, et c'est voulu.
    """

    def __init__(self, reglages: ReglagesAuth,
                 trousseau: TrousseauJwks | None = None) -> None:
        if not reglages.configure:
            raise AuthentificationRequise(
                "authentificateur Supabase non configure: il manque l'URL "
                "JWKS, l'issuer ou l'audience. Deviner l'un des trois "
                "reviendrait a accepter les jetons d'un emetteur que "
                "personne n'a choisi."
            )
        self._reglages = reglages
        self._trousseau = trousseau or TrousseauJwks(reglages.jwks_url)

    # ------------------------------------------------ protocole Authentificateur
    @property
    def identite_de_l_authentificateur(self) -> str:
        """Inscrit dans la trace: on doit savoir QUI a authentifié.

        L'``issuer`` y figure — c'est lui qui distingue deux projets Supabase.
        Il est public par construction (il voyage dans chaque jeton) et n'est
        pas un secret.
        """
        return f"supabase:{self._reglages.issuer}"

    @property
    def est_fictif(self) -> bool:
        """``False``, et c'est vérifiable: cette classe valide une signature."""
        return False

    def authentifier(self, preuve: Any) -> ContexteAuthentifie:
        """Jeton porteur brut -> identité. Lève sur tout le reste.

        :param preuve: le jeton compact, sans le préfixe ``Bearer``.
        :raises AuthentificationRequise: sur toute anomalie, sans jamais
            distinguer « signature fausse » de « audience fausse » dans un
            détail exploitable par un attaquant.
        """
        jeton = self._jeton_de(preuve)
        try:
            entete = jwt.get_unverified_header(jeton)
        except jwt.PyJWTError as cause:
            raise AuthentificationRequise(
                "jeton illisible: l'en-tete n'est pas un en-tete JWT."
            ) from cause

        # L'ALGORITHME EST LU POUR ETRE REFUSE TOT, PAS POUR ETRE SUIVI.
        # `jwt.decode` recoit de toute facon la liste blanche; ce test rend le
        # refus explicite et le message utile.
        algorithme = entete.get("alg")
        if algorithme not in self._reglages.algorithmes:
            raise AuthentificationRequise(
                f"algorithme de jeton refuse ({algorithme!r}). Seuls "
                f"{', '.join(self._reglages.algorithmes)} sont acceptes."
            )

        try:
            cle = self._trousseau.cle_pour(entete.get("kid"))
        except CleInconnue as cause:
            raise AuthentificationRequise(f"cle de signature inconnue: {cause}") from cause
        except JwksIndisponible as cause:
            # LE TROUSSEAU INDISPONIBLE EST UN REFUS, PAS UN LAISSEZ-PASSER.
            raise AuthentificationRequise(
                f"impossible de verifier la signature ({cause}). Le refus est "
                "la seule issue: accepter sans verifier ferait de la panne "
                "reseau une porte ouverte."
            ) from cause

        try:
            revendications = jwt.decode(
                jeton,
                key=cle,
                algorithms=list(self._reglages.algorithmes),
                issuer=self._reglages.issuer,
                audience=self._reglages.audience,
                leeway=self._reglages.tolerance_horloge_s,
                options={
                    "require": ["exp", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError as cause:
            raise AuthentificationRequise("jeton expire.") from cause
        except jwt.ImmatureSignatureError as cause:
            raise AuthentificationRequise("jeton pas encore valide (nbf).") from cause
        except jwt.InvalidAudienceError as cause:
            raise AuthentificationRequise(
                "jeton destine a une autre audience: il peut etre parfaitement "
                "valide ailleurs, il ne l'est pas ici."
            ) from cause
        except jwt.InvalidIssuerError as cause:
            raise AuthentificationRequise(
                "jeton emis par un autre issuer que celui configure."
            ) from cause
        except jwt.MissingRequiredClaimError as cause:
            raise AuthentificationRequise(
                f"revendication obligatoire absente: {cause}."
            ) from cause
        except jwt.PyJWTError as cause:
            # SIGNATURE INVALIDE ET FORME INVALIDE PARTAGENT CE MESSAGE.
            # Les distinguer donnerait a un attaquant un oracle sur la raison
            # exacte de son echec.
            raise AuthentificationRequise("jeton refuse: signature ou forme invalide.") from cause

        sub = revendications.get("sub")
        if not isinstance(sub, str) or not sub.strip():
            raise AuthentificationRequise(
                "jeton sans « sub » exploitable: un jeton valide qui ne nomme "
                "personne n'authentifie personne."
            )
        return creer_contexte(sub.strip(), self.identite_de_l_authentificateur)

    # -------------------------------------------------------------- utilitaires
    def precharger_trousseau(self) -> int:
        """Pour ``/ready``: prouve que le JWKS est réellement joignable."""
        return self._trousseau.precharger()

    @staticmethod
    def _jeton_de(preuve: Any) -> str:
        if not isinstance(preuve, str) or not preuve.strip():
            raise AuthentificationRequise(
                "aucun jeton presente. Le provider ne travaille pas sans "
                "reponse de l'authentificateur."
            )
        jeton = preuve.strip()
        # On accepte l'en-tete complet par commodite d'appel, mais on ne
        # devine rien d'autre: un schema inconnu est refuse.
        if jeton.lower().startswith("bearer "):
            jeton = jeton[7:].strip()
        if " " in jeton:
            raise AuthentificationRequise(
                "jeton mal forme: un JWT compact ne contient pas d'espace."
            )
        return jeton
