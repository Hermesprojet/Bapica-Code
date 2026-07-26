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
LAYERS: Final[tuple[LayerSpec, ...]] = (
    LayerSpec(L_COFFRAGE, 7, "CONTINUOUS", 35, "Contours de coffrage (beton)"),
    LayerSpec(L_FERR_PRINCIPAL, 1, "CONTINUOUS", 50, "Armatures longitudinales"),
    LayerSpec(L_FERR_TRANSVERSAL, 3, "CONTINUOUS", 35, "Armatures transversales (cadres, etriers)"),
    LayerSpec(L_COTATION, 4, "CONTINUOUS", 18, "Cotation"),
    LayerSpec(L_TEXTE, 2, "CONTINUOUS", 18, "Textes et reperes"),
    LayerSpec(L_CARTOUCHE, 7, "CONTINUOUS", 25, "Cartouche"),
    LayerSpec(L_AXES, 5, "CENTER", 13, "Axes et lignes de construction"),
)
