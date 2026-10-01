"""Les catégories de proposition : ce qu'une valeur lue prétend décrire.

UNE SEULE LISTE, ET C'EST ELLE QUE L'ÉCRAN AFFICHE. L'API rend le libellé de
chaque catégorie depuis ce module ; l'interface ne le réécrit pas. Deux listes
divergeraient au premier ajout.

LA NATURE DIT QUELLE FORME LA VALEUR PEUT PRENDRE, PAS CE QU'ELLE VAUT :
``longueur`` (une unité de longueur), ``niveau`` (une altitude signée, en
mètres par convention de notation), ``charge`` (une unité de charge), ``entier``
(un dénombrement, sans unité), ``texte`` (une désignation : classe, nuance,
repère, note).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

__all__ = ["CATEGORIES", "Categorie", "categorie"]

Nature = Literal["longueur", "niveau", "charge", "entier", "texte"]


@dataclass(frozen=True)
class Categorie:
    cle: str
    libelle: str
    nature: Nature


_LISTE: Final[tuple[Categorie, ...]] = (
    Categorie("grid_line", "Axe (file)", "texte"),
    Categorie("grid_spacing", "Entraxe de files", "longueur"),
    Categorie("beam_span", "Portée de poutre", "longueur"),
    #: Mesurée entre les nus des deux appuis (géométrie) : revue seulement.
    Categorie("beam_clear_span", "Portée libre (nu à nu)", "longueur"),
    #: Porte-à-faux depuis le nu de l'appui (géométrie) : revue seulement.
    Categorie("cantilever_length", "Longueur de console", "longueur"),
    Categorie("beam_width", "Largeur de poutre", "longueur"),
    Categorie("beam_depth", "Hauteur de poutre", "longueur"),
    Categorie("slab_thickness", "Épaisseur de dalle", "longueur"),
    Categorie("wall_thickness", "Épaisseur de voile", "longueur"),
    Categorie("floor_level", "Niveau de plancher", "niveau"),
    Categorie("story_height", "Hauteur d'étage", "longueur"),
    Categorie("column_width", "Largeur de poteau", "longueur"),
    Categorie("column_depth", "Profondeur de poteau", "longueur"),
    Categorie("column_diameter", "Diamètre de poteau", "longueur"),
    Categorie("concrete_class", "Classe de béton", "texte"),
    Categorie("steel_grade", "Nuance d'acier", "texte"),
    Categorie("exposure_class", "Classe d'exposition", "texte"),
    Categorie("concrete_cover", "Enrobage", "longueur"),
    Categorie("bar_count", "Nombre de barres", "entier"),
    Categorie("bar_diameter", "Diamètre des barres", "longueur"),
    Categorie("link_diameter", "Diamètre des cadres", "longueur"),
    Categorie("link_spacing", "Espacement des cadres", "longueur"),
    Categorie("load_value", "Charge", "charge"),
    Categorie("building_dimension", "Dimension du bâtiment", "longueur"),
    Categorie("dimension", "Cote", "longueur"),
    Categorie("material_specification", "Spécification de matériau", "texte"),
    Categorie("structural_note", "Note structurelle", "texte"),
    #: Ce qu'un futur modèle de vision repère sans en lire la cote : une
    #: poutre, un poteau, une dalle, un voile, une cote. La valeur est la
    #: classe détectée ; elle se confirme ou se rejette comme le reste.
    Categorie("detected_element", "Élément détecté", "texte"),
)

CATEGORIES: Final[dict[str, Categorie]] = {c.cle: c for c in _LISTE}


def categorie(cle: str) -> Categorie:
    try:
        return CATEGORIES[cle]
    except KeyError as cause:
        raise ValueError(f"categorie inconnue: « {cle} »") from cause
