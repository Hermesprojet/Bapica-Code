"""Lecture géométrique des DXF : du dessin au modèle structurel.

Voir ``docs/GEOMETRIE_DXF.md``. Le module ne connaît ni la base, ni le réseau,
ni le moteur de calcul ; il n'utilise qu'ezdxf et la géométrie plane écrite
dans ``noyau.py``.
"""

from .construction import construire_modele, tolerances_du_dessin
from .extracteur import ExtracteurGeometrieDxf
from .modele import SCHEMA, ModeleStructurel
from .primitives import PrimitivesDxf, lire_primitives
from .propositions import PLAFOND_GEOMETRIE, propositions_du_modele

__all__ = [
    "PLAFOND_GEOMETRIE",
    "SCHEMA",
    "ExtracteurGeometrieDxf",
    "ModeleStructurel",
    "PrimitivesDxf",
    "construire_modele",
    "lire_primitives",
    "propositions_du_modele",
    "tolerances_du_dessin",
]
