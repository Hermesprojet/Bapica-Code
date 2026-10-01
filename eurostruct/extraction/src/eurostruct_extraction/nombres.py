"""Lire un nombre écrit à la française, à l'anglaise ou à la néerlandaise.

``6,00`` et ``6.00`` valent six ; ``1 250,5`` vaut mille deux cent cinquante
et demi. LE POINT N'EST JAMAIS UN SÉPARATEUR DE MILLIERS ICI : sur un plan,
``1.250`` est une altitude ou une longueur en mètres bien plus souvent qu'un
millier — et se tromper multiplierait la valeur par mille. Une valeur que la
lecture ne sait pas trancher n'est pas proposée.

AUCUN ARRONDI. Le nombre rendu est celui qui est écrit ; le texte brut, lui,
voyage avec la proposition pour qu'on puisse le relire tel quel.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["NOMBRE", "NOMBRE_AVEC_MILLIERS", "lire_nombre"]

#: Un nombre simple : chiffres, puis éventuellement une virgule ou un point
#: et des décimales. Pas de signe : le signe a un sens (un niveau) que seule
#: la règle qui le lit sait porter.
NOMBRE: Final[str] = r"\d+(?:[.,]\d+)?"

#: Un nombre à séparateur de milliers par espace (``6 000``), admis seulement
#: là où une unité suit : sans elle, « 6 000 » pourrait être deux nombres.
NOMBRE_AVEC_MILLIERS: Final[str] = r"\d{1,3}(?:[   ]\d{3})+(?:,\d+)?"

_ESPACES: Final[re.Pattern[str]] = re.compile(r"[   ]")


def lire_nombre(texte: str) -> int | float:
    """Le nombre écrit, entier s'il n'a pas de décimales.

    ``ValueError`` si le texte n'est pas un nombre de l'une des deux formes.
    """
    net = _ESPACES.sub("", texte.strip())
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", net):
        raise ValueError(f"« {texte} » n'est pas un nombre lisible")
    if "," in net or "." in net:
        return float(net.replace(",", "."))
    return int(net)
