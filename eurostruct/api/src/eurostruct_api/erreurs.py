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

CE QU'UN 500 DOIT DIRE, ET CE QU'IL NE DOIT SURTOUT PAS DIRE
-------------------------------------------------------------
Mesuré sur les trois routes d'autorité : elles rendaient ``str(cause)`` au
client. ``psycopg2.OperationalError`` porte la chaîne de connexion — **mot de
passe compris** ; ``UndefinedTable`` porte le nom de la table et le fragment de
requête. Tout cela partait, en 422, c'est-à-dire sous un code que n'importe
quel appelant authentifié lit sans alerte et recopie volontiers dans un ticket.

La réponse ne porte donc plus rien d'interne — mais elle n'est pas muette pour
autant. Un 500 générique qui ne dit rien du tout est ininstrumentable :
l'appelant signale « ça ne marche pas » et personne ne sait de quelle requête
il parle. Elle porte un **identifiant de corrélation**, dans le corps et dans
un en-tête, qui ne révèle rien par lui-même et relie la réponse au journal
serveur.

LE JOURNAL NON PLUS N'A PAS BESOIN DU MESSAGE
----------------------------------------------
``logger.exception`` écrit la trace complète, dernière ligne comprise —
c'est-à-dire le message, c'est-à-dire la DSN. Un journal d'application se
recopie dans des tickets, se transmet à des prestataires, et survit bien plus
longtemps qu'une réponse HTTP. On journalise donc le **type** de l'exception,
la corrélation et la route ; jamais le message brut. On perd la trace ; on la
retrouve en rejouant la requête que la corrélation désigne, dans un
environnement où l'on a le droit de tout voir.
"""
from __future__ import annotations

import logging
import uuid

from eurostruct_engine.exceptions import EurostructEngineError
from eurostruct_engine.service import error_of
from fastapi import Request
from fastapi.responses import JSONResponse

_journal = logging.getLogger("eurostruct.api")

#: Le contrat le dit, on ne fait que l'honorer.
STATUT_REFUS = 422

#: L'en-tête qui porte la corrélation. Exposé au navigateur par la politique
#: CORS: sans cela, une interface ne pourrait pas l'afficher à l'utilisateur,
#: et l'identifiant ne servirait qu'à ceux qui lisent les journaux.
ENTETE_CORRELATION = "X-Eurostruct-Correlation-Id"

__all__ = [
    "ENTETE_CORRELATION",
    "STATUT_REFUS",
    "installer_gestionnaires",
    "journaliser_defaut",
    "reponse_de_defaut",
    "reponse_de_refus",
]


def reponse_de_refus(exc: EurostructEngineError) -> JSONResponse:
    """Rend le refus structuré, ou relève si le moteur ne sait pas le nommer."""
    dto = error_of(exc)          # relève lui-même sur une erreur inconnue
    return JSONResponse(status_code=STATUT_REFUS,
                        content=dto.model_dump(mode="json", exclude_none=True))


def journaliser_defaut(exc: Exception, requete: Request | None = None) -> str:
    """Journalise ce qu'on a le droit de savoir. Rend la corrélation.

    NI ``exc_info``, NI ``str(exc)``. Le message d'une exception de pilote
    contient la chaîne de connexion; celui d'une erreur SQL contient la
    requête. Le type, la route et la corrélation suffisent à retrouver la
    trace en rejouant l'appel là où on a le droit de tout voir.
    """
    correlation = uuid.uuid4().hex[:16]
    _journal.error(
        "defaut non traduit correlation=%s type=%s methode=%s chemin=%s",
        correlation,
        type(exc).__name__,
        getattr(requete, "method", "?") if requete else "?",
        # `url.path` et non `str(url)`: une chaîne de requête peut porter ce
        # qu'un appelant y a mis, y compris ce qu'il n'aurait pas dû.
        getattr(getattr(requete, "url", None), "path", "?") if requete else "?",
    )
    return correlation


def reponse_de_defaut(exc: Exception, requete: Request | None = None, *,
                      mode_debogage: bool = False) -> JSONResponse:
    """Le 500 générique: une prise pour le diagnostic, aucun détail interne."""
    correlation = journaliser_defaut(exc, requete)
    contenu: dict[str, object] = {
        "error": "internal_error",
        "what": "erreur non traduite",
        "detail": ("le service a rencontre une erreur qu'il ne sait pas "
                   "qualifier. Ce n'est pas un refus normatif. Citez "
                   "l'identifiant de correlation pour qu'elle soit retrouvee."),
        "correlation_id": correlation,
    }
    if mode_debogage:
        # LOCAL UNIQUEMENT, et jamais posé par défaut. `EUROSTRUCT_DEBUG`
        # n'assouplit aucune vérification: il change seulement ce qu'un refus
        # 500 raconte, sur un poste où la DSN est déjà celle du développeur.
        contenu["debug"] = f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content=contenu,
                        headers={ENTETE_CORRELATION: correlation})


def installer_gestionnaires(app, *, mode_debogage: bool = False) -> None:
    """Branche les deux seuls gestionnaires globaux dont la couche a besoin."""

    @app.exception_handler(EurostructEngineError)
    async def _refus(_: Request, exc: EurostructEngineError) -> JSONResponse:
        return reponse_de_refus(exc)

    @app.exception_handler(Exception)
    async def _defaut(requete: Request, exc: Exception) -> JSONResponse:
        return reponse_de_defaut(exc, requete, mode_debogage=mode_debogage)
