"""Un refus du domaine reste un refus. Il ne devient jamais un résultat.

CE QUE CETTE COUCHE NE FAIT PAS
--------------------------------
Elle ne fabrique pas de réponse partielle, pas de tuple vide, pas de « succès
avec avertissement ». Le moteur lève ``EurostructEngineError`` ; ``error_of``
le convertit en ``EngineErrorDTO`` ; on l'expédie en **422** tel quel.

Le code 422 est celui que le contrat annonce déjà, dans le schéma JSON comme
dans le TypeScript généré : *« A refusal. The API returns this with HTTP 422,
never a partial result. »* On ne le choisit pas ici, on l'honore.

POURQUOI UNE ERREUR INCONNUE N'EST PAS UN 422
----------------------------------------------
``error_of`` relève l'exception qu'il ne sait pas traduire, délibérément. Une
erreur moteur qu'on ne sait pas nommer n'est pas un refus normatif : c'est un
défaut. La transformer en 422 la ferait passer pour une décision d'ingénierie
et l'enterrerait dans les logs du client. Elle ressort en **500**, sans détail
en production.
"""
from __future__ import annotations

import logging

from eurostruct_engine.exceptions import EurostructEngineError
from eurostruct_engine.service import error_of
from fastapi import Request
from fastapi.responses import JSONResponse

_journal = logging.getLogger("eurostruct.api")

#: Le contrat le dit, on ne fait que l'honorer.
STATUT_REFUS = 422


def reponse_de_refus(exc: EurostructEngineError) -> JSONResponse:
    """Rend le refus structuré, ou relève si le moteur ne sait pas le nommer."""
    dto = error_of(exc)          # relève lui-même sur une erreur inconnue
    return JSONResponse(status_code=STATUT_REFUS,
                        content=dto.model_dump(mode="json", exclude_none=True))


def installer_gestionnaires(app, *, mode_debogage: bool = False) -> None:
    """Branche les deux seuls gestionnaires globaux dont la couche a besoin."""

    @app.exception_handler(EurostructEngineError)
    async def _refus(_: Request, exc: EurostructEngineError) -> JSONResponse:
        return reponse_de_refus(exc)

    @app.exception_handler(Exception)
    async def _defaut(_: Request, exc: Exception) -> JSONResponse:
        # LE DETAIL NE SORT PAS EN PRODUCTION. Un message d'exception porte
        # des noms de tables, des chemins, parfois des fragments de requete.
        _journal.exception("erreur non traduite: %s", type(exc).__name__)
        contenu: dict[str, object] = {
            "error": "internal_error",
            "what": "erreur non traduite",
            "detail": ("le service a rencontre une erreur qu'il ne sait pas "
                       "qualifier. Ce n'est pas un refus normatif."),
        }
        if mode_debogage:
            contenu["debug"] = f"{type(exc).__name__}: {exc}"
        return JSONResponse(status_code=500, content=contenu)
