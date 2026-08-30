"""L'identité du BUILD : quel code exactement a produit ces nombres.

POURQUOI LA VERSION NE SUFFIT PAS
----------------------------------
``ENGINE_VERSION`` vaut ``0.3.0``. Les six derniers commits la portent tous —
c'est le contrat de versionnement qui le veut : un PATCH ne change aucun
résultat numérique, donc la version ne bouge pas. Elle est donc **exacte et
insuffisante** : elle dit ce que le code promet, jamais quel code a tourné.

Un calcul conservé dix ans au titre de la décennale doit pouvoir désigner le
code qui l'a produit. « 0.3.0 » ne le désigne pas.

CE QU'ON LIT, ET CE QU'ON NE LIT PAS
--------------------------------------
On lit **une variable d'environnement**, injectée explicitement par ``dev.sh``,
par l'image Docker et par la CI.

ON NE LIT PAS ``.git``. Un conteneur de production n'a pas de dépôt ; s'il en
avait un, ce serait celui du répertoire courant au moment de l'appel, c'est-à-
dire n'importe lequel. Une identité de build qui dépend du répertoire de
travail n'est pas une identité : c'est une coïncidence. Et lancer ``git`` dans
un processus qui sert des requêtes est un coût et une surface pour rien.

``None`` N'EST PAS UNE PANNE, C'EST UN ÉTAT
---------------------------------------------
Un développement lancé à la main n'a pas d'identité de build, et c'est normal.
Ce qui ne l'est pas, c'est d'**enregistrer** un calcul dans ce cas : la ligne
prétendrait désigner un code qu'elle ne sait pas nommer. La persistance refuse
donc ; le calcul **exploratoire** reste disponible, parce qu'il ne prétend
rien et ne survit à rien.
"""

from __future__ import annotations

import os
import re
from typing import Final

__all__ = [
    "VARIABLE_BUILD",
    "BuildInconnu",
    "identite_de_build",
    "identite_de_build_ou_none",
]

#: LA VARIABLE, ET UNE SEULE. Deux noms acceptés deviendraient deux façons de
#: configurer le même fait, dont une oubliée quelque part.
VARIABLE_BUILD: Final[str] = "EUROSTRUCT_BUILD_SHA"

#: CE QU'UNE IDENTITE DE BUILD A LE DROIT D'ETRE.
#:
#: Un SHA git — complet ou abrégé — ou un identifiant de build équivalent
#: composé de caractères sûrs. La borne haute n'est pas décorative: cette
#: valeur part en base et s'affiche sur une note; une chaîne arbitraire de
#: quelques mégaoctets n'y a pas sa place.
_FORME = re.compile(r"^[A-Za-z0-9._@:+-]{7,128}$")

#: LES SENTINELLES QUI PASSENT LA FORME ET NE DESIGNENT RIEN.
#:
#: `unknown` est exactement ce qu'une CI distraite ecrit quand la substitution
#: a echoue: sept caracteres alphanumeriques, donc conforme. L'accepter ferait
#: enregistrer un calcul qui designe « unknown » comme le code qui l'a produit
#: — pire qu'un refus, parce que ca se lit comme une reponse.
#:
#: La liste est COURTE ET NOMMEE: on n'essaie pas de deviner toutes les facons
#: de se tromper, seulement celles qu'on a vues.
_SENTINELLES = frozenset({
    "unknown", "unset", "none", "null", "undefined", "todo", "changeme",
    "0000000", "000000000000000000000000000000000000000",
})


class BuildInconnu(RuntimeError):
    """Aucune identité de build utilisable n'est déclarée.

    Distincte d'une erreur de configuration ordinaire : elle n'empêche pas le
    moteur de calculer. Elle empêche d'**enregistrer** ce calcul comme
    reproductible, ce qui est une décision différente.
    """


def identite_de_build_ou_none() -> str | None:
    """L'identité déclarée, ou ``None``. Ne lève jamais.

    UNE VALEUR MAL FORMÉE VAUT ABSENCE, et c'est délibéré. ``EUROSTRUCT_BUILD_
    SHA=""``, ``"$(git rev-parse HEAD)"`` non substitué, ``"unknown"`` : chacune
    de ces valeurs *ressemble* à une identité et n'en est pas une. Les deux
    premières échouent sur la forme ; la troisième la passe — sept caractères
    alphanumériques — et c'est pour elle qu'existe la liste de sentinelles.
    """
    brut = (os.environ.get(VARIABLE_BUILD) or "").strip()
    if not brut or not _FORME.match(brut):
        return None
    if brut.lower() in _SENTINELLES:
        return None
    return brut


def identite_de_build() -> str:
    """L'identité déclarée, ou un refus qui dit comment la fournir.

    :raises BuildInconnu: rien n'est déclaré, ou la valeur n'a pas la forme
        d'un identifiant de build.
    """
    identite = identite_de_build_ou_none()
    if identite is None:
        raise BuildInconnu(
            f"aucune identite de build declaree ({VARIABLE_BUILD}). Un calcul "
            "conserve doit pouvoir designer le code exact qui l'a produit, et "
            "la version seule ne le fait pas: six commits successifs portent "
            "la meme. Injecter la variable au demarrage — dev.sh, l'image "
            "Docker et la CI le font. Le calcul exploratoire, lui, reste "
            "disponible: il ne pretend rien et ne survit a rien."
        )
    return identite
