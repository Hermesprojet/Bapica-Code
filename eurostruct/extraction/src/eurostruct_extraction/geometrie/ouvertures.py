"""Ce qui dit qu'un contour est une OUVERTURE (trémie, gaine) et non un élément.

Deux conventions de dessin, partagées par la détection des dalles et par celle
des poteaux (``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md``, § 2) :

* **la croix** : un rectangle barré de ses deux diagonales, d'angle à angle ;
* **le nom** : un texte posé dans le contour qui le nomme — gaine, ascenseur,
  trémie, vide, réservation, shaft, lift, koker, Schacht, Aufzug, sparing…
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from .noyau import IndexSpatial, Point, distance
from .primitives import Segment

__all__ = ["diagonales", "nomme_une_ouverture"]

#: Les mots d'une ouverture, en français, néerlandais, anglais et allemand.
_OUVERTURE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Z])(?:GAINES?|ASC(?:ENSEURS?)?(?![A-Z])|MONTE[ -]?(?:CHARGES?|PLATS?)|"
    r"TREMIES?|VIDES?(?![A-Z])|RESERVATIONS?|OUVERTURES?|SHAFTS?|LIFTS?(?![A-Z])|"
    r"LIFTKOKERS?|KOKERS?(?![A-Z])|VOIDS?(?![A-Z])|OPENINGS?|SCHACHTE?(?![A-Z])|"
    r"AUFZ(?:UG|UGE|UEGE)|SPARINGEN|SPARING|AUSSPARUNGEN|AUSSPARUNG|DURCHBRUCH|"
    r"DURCHBRUECHE|DURCHBRUCHE)")


def nomme_une_ouverture(texte: str) -> bool:
    norme = "".join(c for c in unicodedata.normalize("NFKD", texte)
                    if not unicodedata.combining(c)).upper()
    return bool(_OUVERTURE.search(norme))


def diagonales(coins: tuple[Point, Point, Point, Point], segments: list[Segment],
               rayon: float, index: IndexSpatial) -> list[Segment]:
    """Les segments qui relient deux coins opposés (à ``rayon`` près).

    Seuls ceux dont la boîte touche le voisinage du premier ou du deuxième coin
    sont examinés (``index`` : les boîtes de ``segments``, dans leur ordre) : une
    feuille PDF porte des dizaines de milliers de traits, et chaque panneau de
    la grille les parcourait tous.
    """
    trouvees = []
    paires = ((coins[0], coins[2]), (coins[1], coins[3]))
    proches: set[int] = set()
    for coin in coins[:2]:
        proches.update(index.pres_de((coin[0], coin[1], coin[0], coin[1]), marge=rayon))
    for rang in sorted(proches):
        s = segments[rang]
        for c1, c2 in paires:
            if ((distance(s.a, c1) <= rayon and distance(s.b, c2) <= rayon)
                    or (distance(s.a, c2) <= rayon and distance(s.b, c1) <= rayon)):
                trouvees.append(s)
    return trouvees
