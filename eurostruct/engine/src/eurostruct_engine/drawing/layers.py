"""Normalised drawing layers.

Cahier des charges section 7.2 fixes the layer names. They are defined once
here so that every generator writes the same structure and a downstream office
can rely on it.

Colours are ACI indices, which every CAD application resolves without needing
a colour book.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "ACI_JAUNE",
    "LayerSpec",
    "LAYERS",
    "L_COFFRAGE",
    "L_FERR_PRINCIPAL",
    "L_FERR_TRANSVERSAL",
    "L_COTATION",
    "L_TEXTE",
    "L_CARTOUCHE",
    "L_AXES",
]

L_COFFRAGE: Final = "COFFRAGE"
L_FERR_PRINCIPAL: Final = "FERR-PRINCIPAL"
L_FERR_TRANSVERSAL: Final = "FERR-TRANSVERSAL"
L_COTATION: Final = "COTATION"
L_TEXTE: Final = "TEXTE"
L_CARTOUCHE: Final = "CARTOUCHE"
L_AXES: Final = "AXES"


@dataclass(frozen=True, slots=True)
class LayerSpec:
    name: str
    color: int
    linetype: str
    #: Lineweight in 1/100 mm, as stored in DXF. -3 means "by default".
    lineweight: int
    description: str


#: Declared in a fixed order so the generated DXF is byte-stable.
#:
#: LES TEXTES SONT EN 7 (NOIR SUR PAPIER, BLANC A L'ECRAN SOMBRE), PAS EN 2.
#: Mesure le 16/09 sur l'impression couleur de LibreCAD 2.2.0.2: les reperes
#: de barres et le titre du calque `TEXTE` sortaient JAUNES sur fond blanc,
#: illisibles — la couleur 2 est une couleur d'ecran sombre, pas de tirage.
#: La couleur 7 est celle que tout logiciel CAO inverse selon le fond: noire
#: a l'impression, blanche sur un espace de travail sombre. `COFFRAGE` et
#: `CARTOUCHE` la portaient deja; `TEXTE` la rejoint.
LAYERS: Final[tuple[LayerSpec, ...]] = (
    LayerSpec(L_COFFRAGE, 7, "CONTINUOUS", 35, "Contours de coffrage (beton)"),
    LayerSpec(L_FERR_PRINCIPAL, 1, "CONTINUOUS", 50, "Armatures longitudinales"),
    LayerSpec(L_FERR_TRANSVERSAL, 3, "CONTINUOUS", 35, "Armatures transversales (cadres, etriers)"),
    LayerSpec(L_COTATION, 4, "CONTINUOUS", 18, "Cotation"),
    LayerSpec(L_TEXTE, 7, "CONTINUOUS", 18, "Textes et reperes"),
    LayerSpec(L_CARTOUCHE, 7, "CONTINUOUS", 25, "Cartouche"),
    LayerSpec(L_AXES, 5, "CENTER", 13, "Axes et lignes de construction"),
)

#: LA COULEUR 2 (JAUNE) N'EST PORTEE PAR AUCUN CALQUE QUI ECRIT DU TEXTE.
#: Gardee comme constante nommee pour que le test qui l'interdit dise ce
#: qu'il interdit, et pourquoi.
ACI_JAUNE: Final[int] = 2
