"""Deux traits parallèles qui se font face : les deux faces d'une poutre ou d'un voile.

L'APPARIEMENT EST MUTUEL. Un trait s'apparie à son plus proche voisin
parallèle dans la plage de largeurs admise, de chaque côté — et seulement si
ce voisin le choisit aussi. Deux poutres voisines (quatre traits) donnent deux
bandes, jamais une bande à cheval sur les deux.

LES TRAITS SONT RANGÉS PAR DIRECTION, PUIS PAR DÉCALAGE. Chercher un vis-à-vis
ne parcourt que les traits de même direction et de décalage voisin : un plan
de dix mille traits ne se compare pas deux à deux.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from dataclasses import dataclass

from .noyau import Point, Tolerances, angle_deg, normale, unitaire
from .primitives import Segment

__all__ = ["Paire", "TraitOriente", "apparier", "orienter"]


@dataclass(frozen=True)
class TraitOriente:
    segment: Segment
    theta: float
    u: Point
    decalage: float
    debut: float
    fin: float

    @property
    def longueur(self) -> float:
        return self.fin - self.debut


@dataclass(frozen=True)
class Paire:
    theta: float
    u: Point
    #: Décalage de l'axe médian.
    decalage: float
    largeur: float
    debut: float
    fin: float
    segments: tuple[Segment, Segment]


def orienter(segment: Segment, tolerances: Tolerances) -> TraitOriente | None:
    u = unitaire(segment.a, segment.b)
    if u is None:
        return None
    theta = angle_deg(u)
    if theta > 180.0 - tolerances.parallele_deg:
        theta -= 180.0
    rad = math.radians(theta)
    u = (math.cos(rad), math.sin(rad))
    n = normale(u)
    decalage = segment.a[0] * n[0] + segment.a[1] * n[1]
    ta = segment.a[0] * u[0] + segment.a[1] * u[1]
    tb = segment.b[0] * u[0] + segment.b[1] * u[1]
    return TraitOriente(segment, theta, u, decalage, min(ta, tb), max(ta, tb))


def _recouvrement(a: TraitOriente, b: TraitOriente) -> float:
    return min(a.fin, b.fin) - max(a.debut, b.debut)


def apparier(segments: list[Segment], tolerances: Tolerances, *, largeur_min: float,
             largeur_max: float, recouvrement_min: float = 0.3) -> list[Paire]:
    """Les paires de traits parallèles écartés d'une largeur dans ``[min, max]``."""
    traits = [t for t in (orienter(s, tolerances) for s in segments if not s.courbe)
              if t is not None and t.longueur > tolerances.longueur]
    pas = tolerances.parallele_deg
    paquets: dict[int, list[TraitOriente]] = defaultdict(list)
    for t in traits:
        paquets[int(math.floor(t.theta / pas))].append(t)
    rangees: dict[int, tuple[list[TraitOriente], list[float]]] = {}

    def rangee_de(t: TraitOriente) -> tuple[list[TraitOriente], list[float]]:
        """Les traits des paquets voisins, triés par décalage (mis en cache)."""
        cle = int(math.floor(t.theta / pas))
        if cle not in rangees:
            reunis = [x for k in (cle - 1, cle, cle + 1) for x in paquets.get(k, ())]
            reunis.sort(key=lambda x: x.decalage)
            rangees[cle] = (reunis, [x.decalage for x in reunis])
        return rangees[cle]

    def meilleur(t: TraitOriente, sens: int) -> TraitOriente | None:
        rangee, cles = rangee_de(t)
        if sens > 0:
            i = bisect.bisect_left(cles, t.decalage + largeur_min - tolerances.longueur)
            plage = rangee[i:]
        else:
            i = bisect.bisect_right(cles, t.decalage - largeur_min + tolerances.longueur)
            plage = list(reversed(rangee[:i]))
        for x in plage:
            ecart = (x.decalage - t.decalage) * sens
            if ecart > largeur_max + tolerances.longueur:
                break
            if (x is t or ecart < largeur_min - tolerances.longueur
                    or abs(x.theta - t.theta) > pas):
                continue
            seuil = max(recouvrement_min * min(t.longueur, x.longueur), tolerances.longueur)
            if _recouvrement(t, x) >= seuil:
                return x
        return None

    paires: list[Paire] = []
    vues: set[tuple[int, int]] = set()
    for t in traits:
        haut = meilleur(t, +1)
        if haut is None or meilleur(haut, -1) is not t:
            continue
        clef = (id(t.segment), id(haut.segment))
        if clef in vues:
            continue
        vues.add(clef)
        debut, fin = max(t.debut, haut.debut), min(t.fin, haut.fin)
        paires.append(Paire(theta=t.theta, u=t.u,
                            decalage=(t.decalage + haut.decalage) / 2.0,
                            largeur=haut.decalage - t.decalage, debut=debut, fin=fin,
                            segments=(t.segment, haut.segment)))
    paires.sort(key=lambda p: (round(p.theta, 3), round(p.decalage, 6), p.debut))
    return paires
