"""La géométrie plane dont la reconnaissance a besoin, et rien de plus.

POURQUOI PAS UNE BIBLIOTHÈQUE DE GÉOMÉTRIE. Les opérations utiles sont peu
nombreuses — projeter, découper un polygone par une bande, reconnaître un
rectangle, tester l'appartenance d'un point — et chacune est écrite ici en
quelques lignes lisibles. Une dépendance native de plus dans l'image (GEOS)
ne lirait pas mieux un plan ; elle ajouterait une surface à auditer.

TOUT EST EN UNITÉS DU DESSIN. Les tolérances sont dites une fois
(:class:`Tolerances`) et passées partout : aucune comparaison de flottants
n'est faite « à l'œil » au milieu d'un module.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

__all__ = [
    "IndexSpatial",
    "MM_PAR_UNITE",
    "Point",
    "Rectangle",
    "Tolerances",
    "aire",
    "angle_deg",
    "boite_de",
    "centroide",
    "decouper_par_bande",
    "distance",
    "distance_point_droite",
    "distance_point_polygone",
    "distance_point_segment",
    "ecart_angulaire",
    "intersection_droites",
    "intervalle_projete",
    "normale",
    "point_dans_polygone",
    "projeter",
    "quantifier",
    "rectangle_de",
    "unitaire",
]

Point = tuple[float, float]

#: Les facteurs EXACTS vers le millimètre — les mêmes que ceux du report
#: (API). Une unité absente de cette table n'est pas convertie.
MM_PAR_UNITE: Final[dict[str, Decimal]] = {
    "mm": Decimal(1), "cm": Decimal(10), "m": Decimal(1000),
    "in": Decimal("25.4"), "ft": Decimal("304.8"),
}


@dataclass(frozen=True)
class Tolerances:
    """Les seuils de comparaison, en unités du dessin et en degrés.

    ``longueur`` : deux points plus proches sont confondus (1 mm réel quand
    l'unité est connue). ``quantum`` : le pas de quantification d'une valeur
    mesurée (1 µm réel), qui retire le bruit des flottants sans arrondir.
    """

    longueur: float
    quantum: float
    parallele_deg: float = 0.2
    equerre_deg: float = 1.0
    #: Millimètres par unité de dessin, si l'unité est connue.
    mm_par_unite: float | None = None

    def en_mm(self, valeur: float) -> float | None:
        return valeur * self.mm_par_unite if self.mm_par_unite else None

    def depuis_mm(self, valeur_mm: float) -> float | None:
        return valeur_mm / self.mm_par_unite if self.mm_par_unite else None


# ------------------------------------------------------------------ vecteurs
def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def unitaire(a: Point, b: Point) -> Point | None:
    """Le vecteur unitaire de ``a`` vers ``b``, ou ``None`` s'ils sont confondus."""
    d = distance(a, b)
    if d == 0.0:
        return None
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def normale(u: Point) -> Point:
    """La normale directe (rotation de +90°)."""
    return (-u[1], u[0])


def projeter(p: Point, origine: Point, u: Point) -> float:
    """L'abscisse de ``p`` sur la droite ``origine + t·u``."""
    return (p[0] - origine[0]) * u[0] + (p[1] - origine[1]) * u[1]


def angle_deg(u: Point) -> float:
    """La direction d'une droite, dans [0, 180[ : une droite n'a pas de sens."""
    a = math.degrees(math.atan2(u[1], u[0])) % 180.0
    return 0.0 if a >= 180.0 - 1e-12 else a


def ecart_angulaire(a: float, b: float) -> float:
    """L'écart entre deux directions de droites, dans [0, 90]."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def distance_point_droite(p: Point, origine: Point, u: Point) -> float:
    n = normale(u)
    return abs((p[0] - origine[0]) * n[0] + (p[1] - origine[1]) * n[1])


def distance_point_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    longueur2 = dx * dx + dy * dy
    if longueur2 == 0.0:
        return distance(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / longueur2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def intersection_droites(o1: Point, u1: Point, o2: Point, u2: Point) -> Point | None:
    """L'intersection de deux droites, ou ``None`` si elles sont parallèles."""
    det = u1[0] * u2[1] - u1[1] * u2[0]
    if abs(det) < 1e-12:
        return None
    t = ((o2[0] - o1[0]) * u2[1] - (o2[1] - o1[1]) * u2[0]) / det
    return (o1[0] + t * u1[0], o1[1] + t * u1[1])


# ----------------------------------------------------------------- polygones
def aire(points: Sequence[Point]) -> float:
    """Aire signée (positive dans le sens trigonométrique)."""
    s = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def centroide(points: Sequence[Point]) -> Point:
    """Le centre de gravité de la surface ; la moyenne des sommets si elle est nulle."""
    a = aire(points)
    if abs(a) < 1e-12:
        return (sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points))
    cx = cy = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (6.0 * a), cy / (6.0 * a))


def boite_de(points: Iterable[Point]) -> tuple[float, float, float, float]:
    xs, ys = zip(*points, strict=True)
    return (min(xs), min(ys), max(xs), max(ys))


def point_dans_polygone(p: Point, points: Sequence[Point], tolerance: float = 0.0) -> bool:
    """Vrai si ``p`` est à l'intérieur — ou sur le bord, à la tolérance près."""
    if tolerance > 0.0 and distance_point_polygone(p, points) <= tolerance:
        return True
    dedans = False
    x, y = p
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xi > x:
                dedans = not dedans
    return dedans


def distance_point_polygone(p: Point, points: Sequence[Point]) -> float:
    """La distance au BORD du polygone (nulle sur le bord)."""
    return min(distance_point_segment(p, points[i], points[(i + 1) % len(points)])
               for i in range(len(points)))


def _decouper_demi_plan(points: list[Point], n: Point, c: float,
                        garder_inferieur: bool) -> list[Point]:
    """Sutherland–Hodgman sur le demi-plan ``n·x ≤ c`` (ou ``≥ c``)."""
    if not points:
        return []

    def dedans(q: Point) -> bool:
        v = q[0] * n[0] + q[1] * n[1]
        return v <= c if garder_inferieur else v >= c

    def couper(a: Point, b: Point) -> Point:
        va = a[0] * n[0] + a[1] * n[1]
        vb = b[0] * n[0] + b[1] * n[1]
        t = (c - va) / (vb - va)
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

    sortie: list[Point] = []
    for i, courant in enumerate(points):
        precedent = points[i - 1]
        if dedans(courant):
            if not dedans(precedent):
                sortie.append(couper(precedent, courant))
            sortie.append(courant)
        elif dedans(precedent):
            sortie.append(couper(precedent, courant))
    return sortie


def decouper_par_bande(points: Sequence[Point], origine: Point, n: Point,
                       demi_largeur: float) -> list[Point]:
    """La partie du polygone comprise dans la bande ``|n·(x − o)| ≤ demi_largeur``.

    C'est la question « quelle part de ce poteau la poutre traverse-t-elle ? » :
    la projection du résultat sur l'axe de la poutre donne les nus de l'appui.
    """
    c0 = origine[0] * n[0] + origine[1] * n[1]
    garde = _decouper_demi_plan(list(points), n, c0 + demi_largeur, True)
    return _decouper_demi_plan(garde, n, c0 - demi_largeur, False)


def intervalle_projete(points: Iterable[Point], origine: Point, u: Point) -> tuple[float, float]:
    ts = [projeter(p, origine, u) for p in points]
    return (min(ts), max(ts))


# ---------------------------------------------------------------- rectangles
@dataclass(frozen=True)
class Rectangle:
    """Un rectangle reconnu : centre, direction du premier côté, deux côtés."""

    centre: Point
    u: Point
    longueur_u: float
    longueur_v: float

    @property
    def v(self) -> Point:
        return normale(self.u)

    @property
    def grand_cote(self) -> float:
        return max(self.longueur_u, self.longueur_v)

    @property
    def petit_cote(self) -> float:
        return min(self.longueur_u, self.longueur_v)

    @property
    def elancement(self) -> float:
        return self.grand_cote / self.petit_cote if self.petit_cote > 0 else math.inf

    def direction_longue(self) -> Point:
        return self.u if self.longueur_u >= self.longueur_v else self.v


def _sommets_utiles(points: Sequence[Point], tolerance: float) -> list[Point]:
    """Retire le point de fermeture répété et les sommets alignés ou confondus."""
    pts = list(points)
    if len(pts) > 1 and distance(pts[0], pts[-1]) <= tolerance:
        pts.pop()
    nettoyes: list[Point] = []
    for p in pts:
        if not nettoyes or distance(p, nettoyes[-1]) > tolerance:
            nettoyes.append(p)
    if len(nettoyes) > 1 and distance(nettoyes[0], nettoyes[-1]) <= tolerance:
        nettoyes.pop()
    changement = True
    while changement and len(nettoyes) > 3:
        changement = False
        for i in range(len(nettoyes)):
            a, b, c = nettoyes[i - 1], nettoyes[i], nettoyes[(i + 1) % len(nettoyes)]
            if distance_point_segment(b, a, c) <= tolerance:
                del nettoyes[i]
                changement = True
                break
    return nettoyes


def rectangle_de(points: Sequence[Point], tolerances: Tolerances) -> Rectangle | None:
    """Le rectangle que décrivent ces sommets — ou ``None`` si ce n'en est pas un.

    Quatre sommets utiles, quatre angles droits à l'équerre près, côtés opposés
    égaux à la tolérance près. Un losange, un trapèze ou un L ne passent pas.
    """
    sommets = _sommets_utiles(points, tolerances.longueur)
    if len(sommets) != 4:
        return None
    cotes = [(sommets[i], sommets[(i + 1) % 4]) for i in range(4)]
    directions = [unitaire(a, b) for a, b in cotes]
    if any(d is None for d in directions):
        return None
    for i in range(4):
        d0, d1 = directions[i], directions[(i + 1) % 4]
        cosinus = abs(d0[0] * d1[0] + d0[1] * d1[1])  # type: ignore[index]
        if cosinus > math.sin(math.radians(tolerances.equerre_deg)):
            return None
    longueurs = [distance(a, b) for a, b in cotes]
    if (abs(longueurs[0] - longueurs[2]) > tolerances.longueur
            or abs(longueurs[1] - longueurs[3]) > tolerances.longueur):
        return None
    centre = (sum(p[0] for p in sommets) / 4.0, sum(p[1] for p in sommets) / 4.0)
    l0 = (longueurs[0] + longueurs[2]) / 2.0
    l1 = (longueurs[1] + longueurs[3]) / 2.0
    a0 = angle_deg(directions[0])  # type: ignore[arg-type]
    a1 = angle_deg(directions[1])  # type: ignore[arg-type]
    # LE COTE DE REFERENCE EST CELUI QUI EST LE PLUS PRES DE L'HORIZONTALE, et
    # sa direction est prise dans [0, 180[ : deux dessins du même rectangle
    # (sens horaire ou non, autre sommet de départ) rendent la même chose.
    if (_ecart_horizontal(a1), a1) < (_ecart_horizontal(a0), a0):
        a0, l0, l1 = a1, l1, l0
    u = (math.cos(math.radians(a0)), math.sin(math.radians(a0)))
    return Rectangle(centre, u, l0, l1)


def _ecart_horizontal(a: float) -> float:
    return min(a, 180.0 - a)


# -------------------------------------------------------------- quantifier
def quantifier(valeur: float, quantum: float) -> int | float:
    """Ramène une mesure au pas ``quantum`` (bruit des flottants), sans arrondi métier.

    Le pas est un micromètre réel : ``600.0000000001`` cm devient ``600`` ; une
    mesure de 599,96 cm reste 599,96 cm. La valeur brute est citée à côté par
    l'appelant.
    """
    if quantum <= 0:
        return valeur
    decimales = max(0, -int(math.floor(math.log10(quantum))))
    q = round(round(valeur / quantum) * quantum, decimales)
    if q == int(q):
        return int(q)
    return q


# ---------------------------------------------------------- index spatial
class IndexSpatial:
    """Une grille de cases : retrouver vite ce qui est près d'une boîte.

    Sans elle, chercher les appuis de chaque poutre parmi tous les poteaux
    serait quadratique — un plan de 400 poteaux et 800 poutres le sentirait.
    """

    def __init__(self, case: float) -> None:
        self.case = case if case > 0 else 1.0
        self._cases: dict[tuple[int, int], list[int]] = {}
        self._boites: list[tuple[float, float, float, float]] = []

    def _clefs(self, boite: tuple[float, float, float, float]) -> Iterable[tuple[int, int]]:
        x0, y0, x1, y1 = boite
        i0, j0 = math.floor(x0 / self.case), math.floor(y0 / self.case)
        i1, j1 = math.floor(x1 / self.case), math.floor(y1 / self.case)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield (i, j)

    def ajouter(self, boite: tuple[float, float, float, float]) -> int:
        rang = len(self._boites)
        self._boites.append(boite)
        for clef in self._clefs(boite):
            self._cases.setdefault(clef, []).append(rang)
        return rang

    def pres_de(self, boite: tuple[float, float, float, float],
                marge: float = 0.0) -> list[int]:
        x0, y0, x1, y1 = boite
        cherche = (x0 - marge, y0 - marge, x1 + marge, y1 + marge)
        trouves: set[int] = set()
        for clef in self._clefs(cherche):
            trouves.update(self._cases.get(clef, ()))
        resultat = []
        for rang in sorted(trouves):
            bx0, by0, bx1, by1 = self._boites[rang]
            if bx1 >= cherche[0] and bx0 <= cherche[2] and by1 >= cherche[1] and by0 <= cherche[3]:
                resultat.append(rang)
        return resultat
