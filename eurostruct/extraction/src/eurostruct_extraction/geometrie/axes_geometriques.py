"""Les axes par leur SIGNATURE, sans regarder les noms (phase G2).

Voir ``docs/GEOMETRIE_D_ABORD_G2.md`` ; les règles viennent de
``docs/GEOMETRIE_D_ABORD.md`` § 3. Rien ici ne lit un nom de calque, de bloc
ou de type de ligne : seulement la forme, la position, et l'information DXF
standard (N1) que la phase G1 a lue — le motif d'un type de ligne, la
structure d'une définition de bloc.

LA BULLE EST UNE FORME QUI PORTE UN TEXTE COURT. Un cercle, une polyligne
fermée régulière (carré, hexagone, octogone), ou un bloc dont la définition a
un cercle (ou une polyligne fermée) et UN attribut ; exactement un texte court
dedans (1 à 4 lettres, chiffres, point, prime, tiret), lu tel quel.

UNE CLASSE DE CERCLES SE JUGE EN ENTIER. Les bulles sont regroupées par rayon
(5 %) ; une classe n'est faite de bulles d'axes que si la moitié au moins de
ses membres sont AU BOUT d'une droite (≥ 20 rayons, passant par leur centre,
finissant juste avant ou un peu au-delà) : des pieux numérotés, des repères de
locaux, nombreux et loin des bouts de droites, sont écartés ensemble.

LES DROITES SE LISENT PAR PARTITION. Les traits droits d'une même partition
anonyme — même calque et même type de ligne, quels que soient leurs noms —
qui sont colinéaires font une droite : un nu de voile colinéaire à un axe ne
le prolonge pas.

SIGNATURE A : une droite finit sur une bulle, mesure au moins 20 de ses
rayons, et a au moins une parallèle qui fait de même avec une bulle de même
rayon. SIGNATURE B : une droite en trait-point (motif ``mixte``, lu sur le
motif), parallèle à une famille A, longue d'au moins 10 % de la diagonale de
la ZONE STRUCTURELLE (l'enveloppe des droites A élargie d'un entraxe médian)
et qui la traverse.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    angle_deg,
    boite_de,
    distance,
    distance_point_droite,
    ecart_angulaire,
    normale,
    point_dans_polygone,
    projeter,
    unitaire,
)
from .primitives import Cercle, Contour, Primitive, PrimitivesDxf, Segment, Texte

__all__ = [
    "PART_AU_BOUT",
    "RAYONS_MIN_A",
    "TEXTE_COURT",
    "Bulle",
    "Droite",
    "SignaturesAxes",
    "signatures_d_axes",
]

#: Le texte d'une bulle : 1 à 4 lettres, chiffres, point, prime, tiret, lu tel
#: quel (``GEOMETRIE_D_ABORD.md`` § 3.5).
TEXTE_COURT: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9.'’-]{1,4}")
#: Signature A : la droite mesure au moins ce nombre de rayons de sa bulle.
RAYONS_MIN_A: Final[float] = 20.0
#: Même rayon de bulle, même polygone régulier : à 5 % près.
ECART_RAYON: Final[float] = 0.05
#: Une classe de cercles est une classe de bulles si la moitié au moins de ses
#: membres sont au bout d'une droite (choix G2, ``GEOMETRIE_D_ABORD_G2.md`` § 2.1).
PART_AU_BOUT: Final[float] = 0.5
#: Les polygones réguliers qui font une bulle.
COTES_DE_BULLE: Final[frozenset[int]] = frozenset({4, 6, 8})
#: Signature B : au moins cette fraction de la diagonale de la zone structurelle.
FRACTION_ZONE_B: Final[float] = 0.10


@dataclass(frozen=True)
class Bulle:
    centre: Point
    rayon: float
    #: Le texte court, tel qu'écrit.
    texte: str
    #: La poignée du texte ; pour une bulle-bloc sans texte dedans, celle de
    #: l'``INSERT``.
    poignee: str
    #: ``cercle``, ``polygone``, ``bloc``.
    forme: str
    contour: Primitive
    hauteur: float | None = None


@dataclass
class Droite:
    """Une droite candidate : les morceaux colinéaires d'une même partition."""

    theta: float
    u: Point
    decalage: float
    debut: float
    fin: float
    segments: list[Segment]
    #: Les bulles à ses extrémités (0 : début, 1 : fin), d'une classe de bulles.
    bulles: dict[int, Bulle] = field(default_factory=dict)
    #: Les critères vus : ``bulle``, ``famille``, ``motif_mixte``,
    #: ``parallele_a_une_famille``, ``zone``.
    signature: set[str] = field(default_factory=set)

    @property
    def longueur(self) -> float:
        return self.fin - self.debut

    @property
    def origine(self) -> Point:
        n = normale(self.u)
        return (self.decalage * n[0], self.decalage * n[1])

    def point(self, t: float) -> Point:
        o = self.origine
        return (o[0] + t * self.u[0], o[1] + t * self.u[1])


@dataclass
class SignaturesAxes:
    #: Les droites de signature complète (A ou B), réunies quand elles coïncident.
    droites: list[Droite]
    #: Toutes les bulles d'une classe de bulles (pour les étiquettes).
    bulles: list[Bulle]
    #: L'enveloppe des droites A élargie d'un entraxe médian.
    zone: tuple[float, float, float, float] | None
    tolerances: Tolerances
    #: Les formes à un texte court d'une classe ÉCARTÉE (pieux numérotés,
    #: repères de locaux) : elles n'étiquettent pas un axe.
    ecartees: list[Bulle] = field(default_factory=list)

    def criteres(self, theta: float, u: Point, decalage: float, debut: float, fin: float,
                 segments: Sequence[Segment], prims: PrimitivesDxf) -> set[str]:
        """Les critères qu'une droite (nommée) satisfait SEULE : bulle à un bout,
        motif trait-point. Une signature partielle : citée, jamais décisive."""
        vus: set[str] = set()
        droite = Droite(theta, u, decalage, debut, fin, list(segments))
        if any(_bout(droite, b) is not None for b in self.bulles):
            vus.add("bulle")
        if _motif_majoritaire(segments, prims) == "mixte":
            vus.add("motif_mixte")
        return vus


# ------------------------------------------------------------------ bulles
def _direction(a: Point, b: Point, tolerances: Tolerances) -> tuple[float, Point] | None:
    """La direction canonique d'un trait — la même que celle des axes nommés."""
    u = unitaire(a, b)
    if u is None:
        return None
    theta = angle_deg(u)
    if theta > 180.0 - tolerances.parallele_deg:
        theta -= 180.0
    rad = math.radians(theta)
    return theta, (math.cos(rad), math.sin(rad))


def _regulier(points: Sequence[Point]) -> tuple[Point, float] | None:
    """Le centre et le rayon d'un polygone régulier à 4, 6 ou 8 côtés, ou ``None``."""
    if len(points) not in COTES_DE_BULLE:
        return None
    centre = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
    rayons = [distance(p, centre) for p in points]
    cotes = [distance(p, q) for p, q in zip(points, (*points[1:], points[0]), strict=True)]
    r, c = sum(rayons) / len(rayons), sum(cotes) / len(cotes)
    if r <= 0 or c <= 0:
        return None
    if (max(abs(x - r) for x in rayons) > ECART_RAYON * r
            or max(abs(x - c) for x in cotes) > ECART_RAYON * c):
        return None
    return centre, r


def _bulles(prims: PrimitivesDxf) -> list[Bulle]:
    """Toutes les bulles par leur structure, avant le jugement des classes."""
    index = IndexSpatial(_case_textes(prims.textes))
    for t in prims.textes:
        index.ajouter((t.centre[0], t.centre[1], t.centre[0], t.centre[1]))

    def textes_dans(boite: tuple[float, float, float, float], dedans) -> list[Texte]:  # noqa: ANN001
        return [prims.textes[k] for k in index.pres_de(boite) if dedans(prims.textes[k].centre)]

    bulles: list[Bulle] = []
    pris: set[int] = set()
    for cercle in prims.cercles:
        c, r = cercle.centre, cercle.rayon
        if r <= 0:
            continue
        textes = textes_dans((c[0] - r, c[1] - r, c[0] + r, c[1] + r),
                             lambda p, c=c, r=r: distance(p, c) <= r)
        if len(textes) == 1 and TEXTE_COURT.fullmatch(textes[0].texte.strip()):
            t = textes[0]
            bulles.append(Bulle(c, r, t.texte.strip(), t.source.poignee, "cercle", cercle,
                                t.hauteur))
            pris.add(id(cercle))
    for contour in prims.contours:
        if contour.origine != "polyligne":
            continue
        regulier = _regulier(contour.points)
        if regulier is None:
            continue
        c, r = regulier
        textes = textes_dans(boite_de(contour.points),
                             lambda p, pts=contour.points: point_dans_polygone(p, pts))
        if len(textes) == 1 and TEXTE_COURT.fullmatch(textes[0].texte.strip()):
            t = textes[0]
            bulles.append(Bulle(c, r, t.texte.strip(), t.source.poignee, "polygone", contour,
                                t.hauteur))
            pris.add(id(contour))
    bulles.extend(_bulles_blocs(prims, pris))
    return bulles


def _bulles_blocs(prims: PrimitivesDxf, pris: set[int]) -> list[Bulle]:
    """Les bulles-blocs par leur STRUCTURE (G1, F4) : une définition à un cercle
    ou une polyligne fermée et UN attribut — quel que soit le nom du bloc. Une
    bulle déjà reconnue par son contour (l'attribut est dedans) n'est pas
    comptée deux fois."""
    formes: dict[tuple[str, ...], list[Primitive]] = defaultdict(list)
    for p in (*prims.cercles, *prims.contours):
        if p.source.insertions:
            formes[p.source.insertions].append(p)
    bulles: list[Bulle] = []
    for insertion in prims.insertions:
        definition = prims.definitions.get(insertion.nom_bloc)
        if (definition is None or definition.attributs != 1 or len(insertion.attributs) != 1
                or not (definition.types.get("CIRCLE", 0) or definition.fermes)):
            continue
        valeur = insertion.attributs[0][1].strip()
        if not TEXTE_COURT.fullmatch(valeur):
            continue
        chaine = (*insertion.source.insertions, insertion.source.poignee)
        for forme in formes.get(chaine, ()):
            if id(forme) in pris:
                break
            if isinstance(forme, Cercle) and forme.rayon > 0:
                centre, r = forme.centre, forme.rayon
            elif isinstance(forme, Contour) and forme.origine == "polyligne":
                regulier = _regulier(forme.points)
                if regulier is None:
                    continue
                centre, r = regulier
            else:
                continue
            bulles.append(Bulle(centre, r, valeur, insertion.source.poignee, "bloc", forme))
            break
    return bulles


def _case_textes(textes: Sequence[Texte]) -> float:
    hauteurs = sorted(t.hauteur for t in textes if t.hauteur > 0)
    return 4.0 * hauteurs[len(hauteurs) // 2] if hauteurs else 1.0


# ------------------------------------------------------------------ droites
def _droites(segments: Iterable[Segment], tolerances: Tolerances) -> list[Droite]:
    """Les morceaux colinéaires d'une même partition (calque, type de ligne)."""
    pas_theta = max(tolerances.parallele_deg, 1e-9)
    pas_decalage = max(2.0 * tolerances.longueur, 1e-12)
    par_partition: dict[tuple[str, str], list[tuple[float, Point, float, float, float, Segment]]]
    par_partition = defaultdict(list)
    for s in segments:
        if s.courbe:
            continue
        canon = _direction(s.a, s.b, tolerances)
        if canon is None:
            continue
        theta, u = canon
        n = normale(u)
        decalage = s.a[0] * n[0] + s.a[1] * n[1]
        ta, tb = s.a[0] * u[0] + s.a[1] * u[1], s.b[0] * u[0] + s.b[1] * u[1]
        par_partition[(s.calque, s.type_ligne)].append(
            (theta, u, decalage, min(ta, tb), max(ta, tb), s))
    droites: list[Droite] = []
    for cle in sorted(par_partition):
        morceaux = sorted(par_partition[cle], key=lambda m: (round(m[0], 3), m[2], m[3]))
        casier: dict[tuple[int, int], list[int]] = defaultdict(list)
        locales: list[Droite] = []
        for theta, u, decalage, debut, fin, s in morceaux:
            ci, cj = math.floor(theta / pas_theta), math.floor(decalage / pas_decalage)
            cible: Droite | None = None
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for k in casier.get((ci + di, cj + dj), ()):
                        d = locales[k]
                        if (ecart_angulaire(d.theta, theta) <= tolerances.parallele_deg
                                and abs(d.decalage - decalage) <= pas_decalage):
                            cible = d
                            break
                    if cible is not None:
                        break
                if cible is not None:
                    break
            if cible is None:
                casier[(ci, cj)].append(len(locales))
                locales.append(Droite(theta, u, decalage, debut, fin, [s]))
            else:
                cible.debut, cible.fin = min(cible.debut, debut), max(cible.fin, fin)
                cible.segments.append(s)
        droites.extend(locales)
    return droites


def _bout(droite: Droite, bulle: Bulle) -> int | None:
    """L'extrémité (0, 1) où la bulle est posée — centre sur le prolongement à
    0,25 rayon près, entre un rayon avant le bout et quatre au-delà —, ou ``None``."""
    r = bulle.rayon
    if distance_point_droite(bulle.centre, droite.origine, droite.u) > max(0.25 * r, 1e-9):
        return None
    t = projeter(bulle.centre, droite.origine, droite.u)
    for bout, t_bout, sens in ((0, droite.debut, -1.0), (1, droite.fin, 1.0)):
        if -r <= (t - t_bout) * sens <= 4.0 * r:
            return bout
    return None


def _motif_majoritaire(segments: Sequence[Segment], prims: PrimitivesDxf) -> str | None:
    """La classe de motif (G1, F1) de la plus grande longueur de traits."""
    longueurs: dict[str, float] = defaultdict(float)
    for s in segments:
        motif = prims.motif_de(s.type_ligne)
        if motif is not None:
            longueurs[motif.classe] += s.longueur
    if not longueurs:
        return None
    return max(sorted(longueurs), key=lambda c: longueurs[c])


def _familles(droites: Sequence[Droite], tolerances: Tolerances) -> list[list[Droite]]:
    """Les droites regroupées par direction (0,2°), le voisinage de 0° et 180° réuni."""
    ordre = sorted(droites, key=lambda d: (d.theta, d.decalage, d.debut))
    groupes: list[list[Droite]] = []
    for d in ordre:
        if groupes and ecart_angulaire(groupes[-1][0].theta, d.theta) <= tolerances.parallele_deg:
            groupes[-1].append(d)
        else:
            groupes.append([d])
    if (len(groupes) > 1 and ecart_angulaire(groupes[0][0].theta, groupes[-1][0].theta)
            <= tolerances.parallele_deg):
        groupes[0].extend(groupes.pop())
    return groupes


def _meme_rayon(a: float, b: float) -> bool:
    return abs(a - b) <= ECART_RAYON * max(a, b)


def _coupe(droite: Droite, zone: tuple[float, float, float, float]) -> bool:
    """Le segment [début, fin] de la droite coupe-t-il le rectangle ?"""
    (x0, y0), (x1, y1) = droite.point(droite.debut), droite.point(droite.fin)
    t0, t1 = 0.0, 1.0
    dx, dy = x1 - x0, y1 - y0
    for p, q in ((-dx, x0 - zone[0]), (dx, zone[2] - x0), (-dy, y0 - zone[1]),
                 (dy, zone[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        r = q / p
        if p < 0.0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


# ------------------------------------------------------------- signatures
def signatures_d_axes(prims: PrimitivesDxf, tolerances: Tolerances) -> SignaturesAxes:
    """Les droites de signature A ou B d'un DXF, et les bulles de ses classes de bulles."""
    toutes_bulles = _bulles(prims)
    # LE CÔTÉ D'UN CONTOUR FERMÉ N'EST PAS UNE DROITE : les côtés alignés des
    # bulles hexagonales d'une rangée ne font pas un trait-point de grille.
    fermes = {c.source.cle for c in prims.contours if c.origine == "polyligne"}
    droites = _droites((s for s in prims.segments if s.source.cle not in fermes), tolerances)
    if not toutes_bulles and not droites:
        return SignaturesAxes([], [], None, tolerances)

    # LES BOUTS DE DROITES, RANGÉS : une bulle ne regarde que les droites dont
    # une extrémité est près d'elle.
    rayon_max = max((b.rayon for b in toutes_bulles), default=0.0)
    index = IndexSpatial(max(5.0 * rayon_max, 10.0 * tolerances.longueur))
    for d in droites:
        for p in (d.point(d.debut), d.point(d.fin)):
            index.ajouter((p[0], p[1], p[0], p[1]))

    def bouts(bulle: Bulle) -> list[tuple[Droite, int]]:
        marge = 5.0 * bulle.rayon
        c = bulle.centre
        vus: list[tuple[Droite, int]] = []
        for k in index.pres_de((c[0] - marge, c[1] - marge, c[0] + marge, c[1] + marge)):
            d = droites[k // 2]
            if d.longueur < RAYONS_MIN_A * bulle.rayon:
                continue
            bout = _bout(d, bulle)
            if bout is not None and (d, bout) not in vus:
                vus.append((d, bout))
        return vus

    au_bout = [bouts(b) for b in toutes_bulles]

    # LES CLASSES DE RAYONS, jugées en entier.
    ordre = sorted(range(len(toutes_bulles)), key=lambda i: (toutes_bulles[i].rayon, i))
    classes: list[list[int]] = []
    for i in ordre:
        if classes and _meme_rayon(toutes_bulles[classes[-1][0]].rayon, toutes_bulles[i].rayon):
            classes[-1].append(i)
        else:
            classes.append([i])
    valides: set[int] = set()
    for membres in classes:
        if sum(1 for i in membres if au_bout[i]) >= PART_AU_BOUT * len(membres):
            valides.update(membres)
    bulles = [toutes_bulles[i] for i in sorted(valides)]
    ecartees = [b for i, b in enumerate(toutes_bulles) if i not in valides]

    # SIGNATURE A : une bulle au bout, 20 rayons, une parallèle de même rayon.
    candidates: dict[int, Droite] = {}
    for i in sorted(valides):
        for d, bout in au_bout[i]:
            d.bulles.setdefault(bout, toutes_bulles[i])
            candidates[id(d)] = d
    signees_a: list[Droite] = []
    for famille in _familles(list(candidates.values()), tolerances):
        for d in famille:
            rayons = [b.rayon for b in d.bulles.values()]
            # UNE PARALLÈLE, PAS UNE COPIE : la même droite dessinée deux fois
            # (la feuille et sa xréf) ne fait pas une famille.
            if any(_meme_rayon(r, b.rayon) for autre in famille
                   if abs(autre.decalage - d.decalage) > 2.0 * tolerances.longueur
                   for b in autre.bulles.values() for r in rayons):
                d.signature.update(("bulle", "famille"))
                signees_a.append(d)
    if not signees_a:
        return SignaturesAxes([], bulles, None, tolerances, ecartees)

    # LA ZONE STRUCTURELLE : l'enveloppe des droites A, élargie d'un entraxe médian.
    x0, y0, x1, y1 = boite_de([p for d in signees_a for p in (d.point(d.debut),
                                                                d.point(d.fin))])
    ecarts: list[float] = []
    for famille in _familles(signees_a, tolerances):
        decalages = sorted({round(d.decalage, 9) for d in famille})
        ecarts.extend(b - a for a, b in zip(decalages, decalages[1:], strict=False)
                      if b - a > 2.0 * tolerances.longueur)
    marge = sorted(ecarts)[len(ecarts) // 2] if ecarts else 0.0
    zone = (x0 - marge, y0 - marge, x1 + marge, y1 + marge)
    diagonale = math.hypot(zone[2] - zone[0], zone[3] - zone[1])

    # SIGNATURE B : trait-point, parallèle à une famille A, long, dans la zone.
    directions = [famille[0].theta for famille in _familles(signees_a, tolerances)]
    retenues = list(signees_a)
    pris = {id(d) for d in signees_a}
    for d in droites:
        mixte = _motif_majoritaire(d.segments, prims) == "mixte"
        if mixte and id(d) in pris:
            d.signature.add("motif_mixte")
            continue
        if (not mixte or id(d) in pris or d.longueur < FRACTION_ZONE_B * diagonale
                or not any(ecart_angulaire(d.theta, t) <= tolerances.parallele_deg
                           for t in directions)
                or not _coupe(d, zone)):
            continue
        d.signature.update(("motif_mixte", "parallele_a_une_famille", "zone"))
        retenues.append(d)
        pris.add(id(d))

    # DEUX MORCEAUX ADMIS D'UN MÊME AXE, sur deux partitions, sont un seul axe.
    reunies: list[Droite] = []
    for d in sorted(retenues, key=lambda x: (round(x.theta, 3), x.decalage, x.debut)):
        for cible in reunies:
            if (ecart_angulaire(cible.theta, d.theta) <= tolerances.parallele_deg
                    and abs(cible.decalage - d.decalage) <= 2.0 * tolerances.longueur):
                cible.debut, cible.fin = min(cible.debut, d.debut), max(cible.fin, d.fin)
                cible.segments.extend(d.segments)
                cible.signature |= d.signature
                for bout, b in d.bulles.items():
                    cible.bulles.setdefault(bout, b)
                break
        else:
            reunies.append(d)
    return SignaturesAxes(reunies, bulles, zone, tolerances, ecartees)
