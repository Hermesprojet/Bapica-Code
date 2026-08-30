"""Le câblage : jeton porteur -> authentificateur réel -> provider de production.

LA CHAÎNE, ET AUCUN RACCOURCI
------------------------------
1. en-tête ``Authorization: Bearer <jeton>`` — brut, non interprété ;
2. ``AuthentificateurSupabase`` — signature, ``alg``, ``kid``, ``iss``,
   ``aud``, ``exp``, ``nbf``, ``sub`` ;
3. ``ContexteAuthentifie`` — la seule forme d'identité que le provider accepte ;
4. transaction PostgreSQL explicite ;
5. ``SET LOCAL eurostruct.actor_id`` ;
6. l'opération ;
7. ``commit`` ou ``rollback`` ;
8. disparition du contexte avec la transaction.

Les étapes 4 à 8 sont dans le moteur (``_UniteDeTravail``) et ne sont pas
réécrites ici : les réimplémenter donnerait deux mécanismes, dont un seul
serait éprouvé par la campagne de mutations.

CE QUE LES ROUTES NE REÇOIVENT JAMAIS
--------------------------------------
Ni ``actor_id``, ni proposant, ni approbateur. Le jeton **est** l'identité.
Une route qui accepterait un acteur en paramètre rendrait la vérification
décorative : il suffirait de mentir dans le corps.

POURQUOI LE PROVIDER EST CONSTRUIT PAR REQUÊTE
------------------------------------------------
Une connexion par unité de travail (voir ``base.py``). Le coût est réel et
assumé : deux requêtes concurrentes qui partageraient une session
partageraient aussi ``eurostruct.actor_id``.
"""
from __future__ import annotations

from typing import Any

from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.ndp.provider_factory import (
    ConfigurationProviderInvalide,
    PiloteIndisponible,
    creer_provider_de_production,
)
from fastapi import Depends, Header, HTTPException, Request

__all__ = ["acteur_authentifie", "jeton_porteur", "ouvrir_provider",
           "provider_de_lecture"]


def jeton_porteur(authorization: str | None = Header(default=None)) -> str:
    """Extrait le jeton compact de l'en-tête. Refuse tout le reste.

    On n'accepte que le schéma ``Bearer``. Un schéma inconnu n'est pas
    « probablement un jeton » : c'est une requête qu'on ne sait pas lire.
    """
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=401,
            detail={"error": "authentification_requise",
                    "what": "Authorization",
                    "detail": "en-tete Authorization absent."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    morceaux = authorization.strip().split(None, 1)
    if len(morceaux) != 2 or morceaux[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"error": "authentification_requise",
                    "what": "Authorization",
                    "detail": "schema attendu: « Bearer <jeton> »."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return morceaux[1].strip()


def acteur_authentifie(requete: Request,
                       jeton: str = Depends(jeton_porteur)) -> str:
    """Vérifie le JWT et rend l'identité. **Sans ouvrir de transaction.**

    POURQUOI CETTE DEPENDANCE EXISTE
    ---------------------------------
    ``jeton_porteur`` extrait une chaîne d'un en-tête. Il ne vérifie **rien** :
    ni signature, ni émetteur, ni audience, ni expiration. Une route qui n'en
    demande pas plus laisse passer ``Bearer nimporte-quoi``.

    C'était le cas de ``POST /v1/authority/review-packages``, qui compose le
    dossier de revue d'un paramètre : elle rendait la valeur, l'unité, la
    clause, le folio et l'empreinte du document d'une annexe **sous licence**
    à qui présentait n'importe quelle chaîne.

    ELLE N'OUVRE AUCUNE CONNEXION, ET C'EST DELIBERE. ``ouvrir_provider``
    ouvre une transaction PostgreSQL parce que les trois primitives d'autorité
    écrivent. Composer un dossier ne touche pas la base : le registre est en
    mémoire. Prendre une connexion ici la retiendrait du pool pour une lecture
    qui n'en a pas besoin.

    LE VALIDATEUR N'EST PAS DUPLIQUE. C'est le même ``AuthentificateurSupabase``
    que le reste du chemin d'autorité, pris sur l'état de l'application : deux
    validateurs, c'est un de trop, et c'est toujours le plus faible qui finit
    par décider.
    """
    authentificateur = getattr(requete.app.state, "authentificateur", None)
    if authentificateur is None:
        # PAS D'AUTHENTIFICATEUR, PAS DE SERVICE. Le refus est 503 et non 401:
        # ce n'est pas l'appelant qui est en faute.
        raise HTTPException(
            status_code=503,
            detail={"error": "service_non_pret",
                    "what": "authentification",
                    "detail": ("le service n'a pas de configuration "
                               "d'authentification utilisable. Voir /ready.")},
        )
    try:
        contexte = authentificateur.authentifier(jeton)
    except AuthentificationRequise as cause:
        raise HTTPException(
            status_code=401,
            detail={"error": "authentification_refusee",
                    "what": "jeton",
                    # Le message de l'authentificateur ne distingue pas
                    # « signature fausse » de « audience fausse »: il ne donne
                    # aucun oracle a qui essaie.
                    "detail": str(cause)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from cause
    return contexte.actor_id


class _ProviderOuvert:
    """Un provider de production et la connexion qu'il faudra fermer."""

    __slots__ = ("provider", "_connexion")

    def __init__(self, provider: Any, connexion: Any) -> None:
        self.provider = provider
        self._connexion = connexion

    def fermer(self) -> None:
        try:
            self._connexion.close()
        except Exception:  # noqa: BLE001 — fermer ne doit jamais masquer
            pass


def ouvrir_provider(requete: Request) -> _ProviderOuvert:
    """Construit le provider de production pour CETTE requête.

    Traduit les refus de la factory en réponses HTTP, sans jamais les
    transformer en succès :

    * pas d'authentificateur configuré -> 503, le service n'est pas prêt ;
    * pilote ou base indisponible -> 503, ce n'est pas la faute de l'appelant ;
    * configuration invalide -> 503, elle est de notre côté.
    """
    etat = requete.app.state
    authentificateur = getattr(etat, "authentificateur", None)
    fabrique = getattr(etat, "fabrique_connexion", None)
    if authentificateur is None or fabrique is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "service_non_pret",
                    "what": "authentification ou base",
                    "detail": ("le service n'a pas de configuration "
                               "d'authentification ou de base utilisable. "
                               "Voir /ready.")},
        )

    connexion = None

    def _fabrique_tracante() -> Any:
        nonlocal connexion
        connexion = fabrique()
        return connexion

    try:
        provider = creer_provider_de_production(
            fabrique_de_connexion=_fabrique_tracante,
            authentificateur=authentificateur,
        )
    except (PiloteIndisponible, ConfigurationProviderInvalide,
            AuthentificationRequise) as cause:
        if connexion is not None:
            try:
                connexion.close()
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(
            status_code=503,
            detail={"error": "service_non_pret",
                    "what": type(cause).__name__,
                    "detail": str(cause)},
        ) from cause
    return _ProviderOuvert(provider, connexion)


class _LectureOuverte:
    """Un provider de LECTURE et la connexion qu'il faudra fermer.

    LA LECTURE DES CONFIRMATIONS N'AUTHENTIFIE PERSONNE, et c'est voulu: une
    confirmation belge vaut pour toutes les etudes belges. Le calcul n'exige
    donc pas d'identite — mais il a besoin de savoir CE QUI EST CONFIRME, sans
    quoi le mode strict lirait encore un fichier du depot.
    """

    __slots__ = ("provider", "_connexion")

    def __init__(self, provider: Any, connexion: Any) -> None:
        self.provider = provider
        self._connexion = connexion

    def fermer(self) -> None:
        try:
            self._connexion.close()
        except Exception:  # noqa: BLE001 — fermer ne doit jamais masquer
            pass


def provider_de_lecture(requete: Request) -> _LectureOuverte | None:
    """Le provider qui dit ce qui est confirme, ou ``None``.

    ``None`` N'EST PAS UN MODE DEGRADE. Sans source de confirmation, le mode
    strict refuse — c'est le comportement fail-closed du moteur, et l'etat
    reel du produit aujourd'hui. Ce qui serait un mode degrade, ce serait de
    laisser passer.

    On ne leve donc pas quand la base manque: le calcul EXPLORATOIRE, lui,
    doit rester utilisable sans base. C'est la difference entre « je ne sais
    pas ce qui est confirme » et « je ne peux pas travailler ».
    """
    etat = requete.app.state
    authentificateur = getattr(etat, "authentificateur", None)
    fabrique = getattr(etat, "fabrique_connexion", None)
    if authentificateur is None or fabrique is None:
        return None

    connexion = None

    def _fabrique_tracante() -> Any:
        nonlocal connexion
        connexion = fabrique()
        return connexion

    try:
        provider = creer_provider_de_production(
            fabrique_de_connexion=_fabrique_tracante,
            authentificateur=authentificateur,
        )
    except (PiloteIndisponible, ConfigurationProviderInvalide,
            AuthentificationRequise):
        if connexion is not None:
            try:
                connexion.close()
            except Exception:  # noqa: BLE001
                pass
        return None
    return _LectureOuverte(provider, connexion)
