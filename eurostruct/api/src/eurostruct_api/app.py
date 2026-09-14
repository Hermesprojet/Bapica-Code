"""La fabrique d'application. Fail-closed au démarrage, lisible à la sonde.

POURQUOI LE PROCESSUS DÉMARRE MÊME MAL CONFIGURÉ
-------------------------------------------------
Mourir au boot sur une variable absente donne un conteneur qui redémarre en
boucle et n'explique rien. Le processus démarre donc, ``/health`` répond, et
``/ready`` dit **précisément** ce qui manque — sans révéler aucune valeur.

Mais aucune route d'autorité ne sert pour autant : sans authentificateur, la
dépendance rend **503**. C'est la différence entre « je démarre en mode
dégradé » — qu'on refuse — et « je démarre pour pouvoir dire pourquoi je ne
peux pas servir » — qu'on veut.

L'AUTHENTIFICATEUR FICTIF N'EXISTE PAS ICI
-------------------------------------------
Il n'y a aucun chemin, aucune variable d'environnement, aucun drapeau qui
substitue un double de test à ``AuthentificateurSupabase``. Les tests
construisent leur propre application avec leurs propres clés ; ils ne
retournent pas un interrupteur dans le code de production.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from . import __version__, erreurs
from .auth.supabase import AuthentificateurSupabase
from .base import FabriqueConnexionPostgres
from .config import Reglages, charger
from .erreurs import installer_gestionnaires
from .routes import (
    autorite,
    calculs,
    livrables,
    organisations,
    projets,
    referentiel,
    sante,
)

_journal = logging.getLogger("eurostruct.api")

__all__ = ["creer_application"]


def creer_application(reglages: Reglages | None = None) -> FastAPI:
    """Construit l'application. Ne lève pas sur une configuration absente."""
    reglages = reglages or charger()

    app = FastAPI(
        title="EUROSTRUCT API",
        version=__version__,
        description=(
            "Couche HTTP d'EUROSTRUCT. Le moteur deterministe reste sans "
            "dependance HTTP, IA ou reseau. Les refus du domaine sont rendus "
            "en 422 comme des EngineErrorDTO, jamais comme des resultats "
            "partiels."
        ),
    )
    app.state.reglages = reglages

    # AUTHENTIFICATEUR: construit s'il est configurable, sinon ABSENT.
    # `None` n'est pas un mode degrade: c'est ce qui fait rendre 503 aux
    # routes d'autorite et echouer /ready.
    app.state.authentificateur = None
    if reglages.auth.configure:
        try:
            app.state.authentificateur = AuthentificateurSupabase(reglages.auth)
        except Exception:  # noqa: BLE001 — /ready dira quoi, sans le crier ici
            _journal.warning("authentificateur non construit: voir /ready")

    # FABRIQUE DE CONNEXION: meme regle.
    app.state.fabrique_connexion = None
    if reglages.base.configure:
        try:
            app.state.fabrique_connexion = FabriqueConnexionPostgres(reglages.base)
        except Exception:  # noqa: BLE001
            _journal.warning("fabrique de connexion non construite: voir /ready")

    # CORS — SANS LUI, L'INTERFACE NE PEUT PAS APPELER L'API.
    #
    # Trouve en pilotant l'ecran dans un VRAI navigateur: les tests passent par
    # `TestClient`, qui n'applique aucune politique d'origine, et ne pouvaient
    # donc pas le voir. Un navigateur, lui, refuse la requete de `:3000` vers
    # `:8000` si la reponse ne porte pas l'en-tete.
    #
    # LES ORIGINES SONT DECLAREES, JAMAIS `*` — la configuration refuse le
    # joker. `allow_credentials` reste FAUX: l'identite voyage dans un en-tete
    # `Authorization` explicite, pas dans un cookie que le navigateur joindrait
    # tout seul. C'est ce qui rend la falsification de requete inter-site sans
    # objet ici.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(reglages.origines),
        allow_credentials=False,
        # `PATCH` ET `DELETE` SONT ARRIVES AVEC L'ADMINISTRATION DES MEMBRES,
        # ET LEUR ABSENCE A COUTE UN PARCOURS ENTIER.
        #
        # Mesure du jour, dans un vrai Chromium: « Response to preflight
        # request doesn't pass access control check » sur le PATCH d'une
        # adhesion. La route repondait parfaitement — la suite d'API le prouve
        # — et le NAVIGATEUR n'y arrivait jamais: le prevol `OPTIONS` ne
        # trouvait pas la methode dans `Access-Control-Allow-Methods`, et
        # `fetch` echouait AVANT d'emettre la requete reelle. C'est exactement
        # le defaut qu'aucune suite d'API ne peut voir, et que seul un parcours
        # navigateur revele.
        #
        # LA LISTE RESTE ENUMEREE, JAMAIS `*`: un joker autoriserait aussi les
        # methodes qu'on n'expose pas, et cesserait de dire ce que l'API fait.
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        # L'IDENTIFIANT DE CORRELATION DOIT ETRE LISIBLE PAR L'INTERFACE.
        # Sans `expose_headers`, le navigateur le recoit et le cache: seule
        # une personne ayant acces aux journaux pourrait relier une panne a sa
        # trace, et l'utilisateur qui la signale n'aurait rien a citer.
        #
        # `Content-Disposition` EST ARRIVE AVEC LE PDF, ET SON ABSENCE FAISAIT
        # ENREGISTRER UN PDF SOUS UN NOM `.html`.
        #
        # Mesure du jour, dans un vrai Chromium: le navigateur proposait
        # « livrable-c4d2960f-….html » pour une note PDF. `telechargerLivrable`
        # lit pourtant l'en-tete — mais un en-tete NON EXPOSE est invisible a
        # `fetch`, et le client retombait sur son nom de secours. Le systeme de
        # l'utilisateur aurait ouvert un PDF avec un lecteur HTML.
        #
        # LE DEFAUT EXISTAIT DEJA POUR LE HTML, ET PERSONNE NE POUVAIT LE VOIR:
        # le nom de secours finissait en `.html`, ce qui se trouvait etre juste.
        # Il a fallu un second format pour que le mensonge devienne visible.
        #
        # C'est le meme piege que `allow_methods` au lot precedent: l'API
        # repondait correctement, et le NAVIGATEUR n'en voyait rien. Aucune
        # suite d'API ne peut l'attraper — `TestClient` n'applique aucune
        # politique d'origine et lit tous les en-tetes.
        expose_headers=[
            "Content-Disposition",
            "X-Eurostruct-Rebar-Rows",
            erreurs.ENTETE_CORRELATION,
        ],
    )

    installer_gestionnaires(app, mode_debogage=reglages.mode_debogage)
    app.include_router(sante.routeur)
    app.include_router(calculs.routeur)
    # AVANT les routes d'autorite: aucune identite requise, le referentiel
    # national est le meme pour tout le monde.
    app.include_router(referentiel.routeur)
    app.include_router(autorite.routeur)
    # L'ATELIER EN DERNIER: il exige a la fois une identite verifiee et
    # une base, la ou les routes precedentes se contentent de l'une ou de
    # l'autre. L'ordre d'enregistrement n'a aucun effet sur le routage —
    # aucun prefixe ne se recouvre — et rend l'exigence lisible.
    app.include_router(projets.routeur)
    # LES LIVRABLES PARTAGENT LE PREFIXE `/v1/projects` ET NE LE RECOUVRENT
    # PAS: aucune de leurs routes n'a la forme d'une route de calcul. Elles
    # sont montees apres parce qu'elles exigent une contrainte de plus — un
    # magasin d'objets — et que l'ordre rend cette dependance lisible.
    app.include_router(livrables.routeur)
    # L'ENTREE — fonder son bureau, inviter, administrer les membres.
    #
    # MONTEE APRES L'ATELIER, ET C'EST LE CONTRAIRE DE L'ORDRE D'USAGE: on
    # fonde son bureau AVANT d'avoir un projet. L'ordre ici ne dit rien du
    # parcours, il dit ce que chaque routeur exige — et celui-ci exige la
    # meme chose que l'atelier: une identite verifiee et une base.
    #
    # LES DEUX ROUTEURS SONT DISTINCTS PARCE QUE LEURS PREFIXES LE SONT. Un
    # invite ne connait PAS l'organisation qui l'invite — c'est le secret qui
    # la lui apprend — et une route sous `/v1/organizations/{org_id}/…`
    # l'obligerait a nommer un identifiant qu'il n'a pas.
    app.include_router(organisations.routeur)
    app.include_router(organisations.routeur_invitations)
    return app


#: Cible d'`uvicorn eurostruct_api.app:app`.
app = creer_application()
