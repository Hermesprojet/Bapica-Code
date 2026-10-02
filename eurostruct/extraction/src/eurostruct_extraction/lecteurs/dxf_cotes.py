"""La mesure d'une cote DXF, par type : la même pour les deux lecteurs.

UNE COTE ALIGNÉE MESURE LA DISTANCE ENTRE SES DEUX POINTS (13 et 14). ezdxf
(1.4.4) la mesure comme une cote tournée, en projetant ses points sur l'angle
du code 50 — qu'AutoCAD n'écrit que pour les cotes tournées : l'angle vaut
alors 0, et la « mesure » est la projection horizontale. Elle est donc
calculée ici. Voir ``docs/GEOMETRIE_COTES_DXF.md``.

UN ANGLE N'EST PAS UNE LONGUEUR. Une cote angulaire est mesurée en degrés et
dite « angulaire » ; une cote d'ordonnée, ou d'un type inconnu, n'est pas
mesurée.

LA MESURE D'AUTOCAD (code 42) est rendue telle quelle, pour être citée et
comparée : jamais pour remplacer la mesure des points de définition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

__all__ = ["LONGUEURS", "MesureDeCote", "mesure_de_cote"]

#: Les natures de cote qui mesurent une longueur.
LONGUEURS: Final[frozenset[str]] = frozenset({"lineaire", "alignee", "rayon", "diametre"})
#: Le type de la cote (code 70, sans ses drapeaux) et sa nature.
_NATURES: Final[dict[int, str]] = {0: "lineaire", 1: "alignee", 2: "angulaire", 3: "diametre",
                                   4: "rayon", 5: "angulaire", 6: "ordonnee"}


@dataclass(frozen=True)
class MesureDeCote:
    #: En unités du dessin pour une longueur, en degrés pour un angle ;
    #: ``None`` : la cote n'est pas mesurée.
    valeur: float | None
    #: ``lineaire``, ``alignee``, ``rayon``, ``diametre``, ``angulaire``,
    #: ``ordonnee`` ou ``autre``.
    nature: str
    #: La mesure enregistrée par AutoCAD (code 42), si le fichier en porte une
    #: (≥ 0) ; en radians pour un angle.
    autocad: float | None = None


def mesure_de_cote(entite: Any) -> MesureDeCote:
    """La grandeur qu'une entité ``DIMENSION`` représente."""
    nature = _NATURES.get(int(entite.dimtype), "autre")
    autocad: float | None = None
    try:
        if entite.dxf.hasattr("actual_measurement"):
            brute = float(entite.dxf.actual_measurement)
            if math.isfinite(brute) and brute >= 0.0:
                autocad = brute
    except (TypeError, ValueError):
        autocad = None
    if nature in ("ordonnee", "autre"):
        return MesureDeCote(None, nature, autocad)
    valeur: float | None
    try:
        if nature == "alignee":
            from ezdxf.math import Vec3

            valeur = (Vec3(entite.dxf.defpoint3) - Vec3(entite.dxf.defpoint2)).magnitude
        else:
            mesuree = entite.get_measurement()
            valeur = None if hasattr(mesuree, "x") else float(mesuree)
    except Exception:  # noqa: BLE001 — une cote illisible n'arrete rien
        valeur = None
    if valeur is not None and not math.isfinite(valeur):
        valeur = None
    return MesureDeCote(valeur, nature, autocad)
