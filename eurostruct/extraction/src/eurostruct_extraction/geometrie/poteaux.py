"""Les poteaux : des sections coupées, posées sur un nœud de la grille.

LA GÉOMÉTRIE D'ABORD (G4, ``docs/GEOMETRIE_D_ABORD_G4.md``)
------------------------------------------------------------
Un poteau est reconnu par ce qu'il EST, avant de regarder les noms. La
SIGNATURE C1 : une SECTION (rectangle, cercle, polygone inscrit), COUPÉE
(remplie — elle-même, ou par un contour rempli de même centre et de même
taille, QUEL QUE SOIT SON CALQUE), de taille plausible, posée SUR UN NŒUD de la
grille, DANS LA ZONE STRUCTURELLE, qui n'est ni un pieu (même sans nom), ni un
contenant, ni une trémie barrée ou nommée, ni un BOUT DE VOILE. Sans aucune
grille, la SIGNATURE C2 : des sections identiques alignées en deux directions,
à un entraxe implicite d'au moins quatre sections (une grille implicite : des
poteaux, jamais des axes).

* C1 complète : 0,85 ; et un contour nommé poteau qui concorde : 0,90 ;
* une section VIDE est partielle : un nom de poteau (calque ou bloc, 0,85, la
  règle du nom d'aujourd'hui), un bloc répété à l'échelle 1 (0,75) ou un repère
  de poteau voisin (0,6) la complète ; sinon rien, et c'est compté ;
* C1 complète sur un contour nommé d'un AUTRE rôle : un poteau à 0,4, et le
  conflit est dit. Le nom qui compte est celui du contour de la section, jamais
  celui de son remplissage.

LES RAISONS D'AUJOURD'HUI SONT ÉVALUÉES D'ABORD (``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md``,
§ 2) : un candidat au nœud est écarté, et la raison comptée, s'il est le
dessin d'un pieu, s'il CONTIENT un autre contour fermé plus petit (socle,
massif, gaine, pièce), s'il n'est pas compact (chevron de gaine, flèche), s'il
est barré de ses deux diagonales (trémie), si un texte posé dedans le nomme
ouverture (« GAINE », « ASC. »), ou si, VIDE, il est posé dans une enceinte
continue de la taille d'un poteau (la cabine dans la gaine). Les raisons de
G4 (``section_irreguliere``, ``hors_zone``, ``bout_de_voile``,
``partielle_vide``) ne comptent donc que ce qui était un poteau avant elles.

UN POTEAU DESSINÉ DEUX FOIS (contour ET hachure) N'EST QU'UN POTEAU, avec deux
preuves. Un poteau dessiné en quatre ``LINE`` est reconstitué : quatre
segments qui se ferment à angles droits.

LES CÔTÉS SONT DONNÉS DANS LE REPÈRE DE LA GRILLE : la largeur selon la
famille d'axes la plus proche de l'horizontale, la profondeur selon l'autre.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from .classification import Classement, classer, nomme_un_pieu
from .libelles import lire_repere
from .modele import Grille, NonResolu, Pieu, Poteau, Preuve, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Rectangle,
    Tolerances,
    _sommets_utiles,
    angle_deg,
    boite_de,
    centroide,
    compacite,
    distance,
    distance_point_droite,
    distance_point_polygone,
    ecart_angulaire,
    normale,
    point_dans_polygone,
    projeter,
    rectangle_de,
)
from .ouvertures import diagonales, nomme_une_ouverture
from .primitives import Insertion, Primitive, PrimitivesDxf, Segment, Source

__all__ = ["Forme", "centre_et_taille", "detecter_poteaux", "formes_fermees"]

#: Bornes de plausibilité d'un côté de poteau (mm réels), quand l'unité est connue.
COTE_MIN_MM: Final[float] = 100.0
COTE_MAX_MM: Final[float] = 2000.0
ELANCEMENT_MAX: Final[float] = 4.0
#: Au plus cette fraction de l'entraxe médian, quand l'unité n'est pas connue.
FRACTION_ENTRAXE_MAX: Final[float] = 0.3

#: Les rôles qui ne sont JAMAIS un poteau.
_JAMAIS: Final[frozenset[str]] = frozenset(
    {"axe", "cote", "texte", "niveau", "armature", "cadre", "tremie", "poutre", "voile",
     "dalle", "pieu", "fondation"})
#: En dessous, l'aire d'un contour par rapport à son enveloppe convexe ne fait
#: pas une section : un L courant est vers 0,7, un chevron de gaine vers 0,3.
COMPACITE_MIN: Final[float] = 0.5
#: Un contour CONTENU est plus petit que 90 % du petit côté du contenant : la
#: hachure d'un poteau, de même taille, ne fait pas de lui un contenant.
TAILLE_CONTENUE_MAX: Final[float] = 0.9
#: Ces contours ne font pas d'une forme un contenant (une armature, un cadre de
#: texte, une flèche de cote dessinés dans un poteau).
_CONTENU_IGNORE: Final[frozenset[str]] = frozenset(
    {"cote", "texte", "niveau", "armature", "cadre"})

#: G4 — L'ÉCHELLE DE PREUVES DES POTEAUX (``docs/GEOMETRIE_D_ABORD_G4.md`` § 3.6).
CONFIANCE_C1: Final[float] = 0.85
CONFIANCE_CONCORDANTE: Final[float] = 0.90
CONFIANCE_BLOC_REPETE: Final[float] = 0.75
CONFIANCE_C2: Final[float] = 0.65
CONFIANCE_NOM: Final[float] = 0.85
CONFIANCE_REPERE: Final[float] = 0.6
PLAFOND_CONFLIT: Final[float] = 0.4
#: Même centre et même taille à 5 % près : le jumeau rempli d'un contour, le
#: dessin d'un pieu ; un côté égal à l'épaisseur d'un voile.
ECART_RELATIF: Final[float] = 0.05
#: Un polygone inscrit : au moins 5 sommets, tous à la même distance du centre.
SOMMETS_INSCRIT_MIN: Final[int] = 5
#: Un bloc répété : la même définition insérée au moins 3 fois à l'échelle 1.
INSERTIONS_BLOC_MIN: Final[int] = 3
#: Des sections identiques : côtés triés égaux à 1 %.
ECART_SECTION: Final[float] = 0.01
#: C2 : au moins 3 sections par file, alignées à 1° ; un entraxe implicite d'au
#: moins 4 grands côtés et d'au plus 20 m.
SECTIONS_PAR_FILE_C2: Final[int] = 3
ALIGNEMENT_C2_DEG: Final[float] = 1.0
ENTRAXE_C2_MIN_COTES: Final[float] = 4.0
ENTRAXE_C2_MAX_MM: Final[float] = 20000.0
#: Ces contours ne disent rien : la géométrie décide. Les autres rôles ne
#: comptent que pour un conflit (§ 3.6, cas 5).
_SANS_ROLE: Final[frozenset[str]] = frozenset({"inconnu", "hachure"})


@dataclass(frozen=True)
class Forme:
    """Un contour fermé candidat, quelle que soit la façon dont il est dessiné."""

    points: tuple[Point, ...]
    rempli: bool
    primitives: tuple[Primitive, ...]
    classement: Classement
    #: ``rectangle``, ``cercle``, ``polygone``.
    genre: str
    rayon: float | None = None


def _rectangles_de_lignes(segments: list[Segment], tolerances: Tolerances) -> list[Forme]:
    """Quatre ``LINE`` qui se ferment à angles droits font un rectangle."""
    pas = tolerances.longueur * 2.0

    def cle(p: Point) -> tuple[int, int]:
        return (round(p[0] / pas), round(p[1] / pas))

    extremites: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, s in enumerate(segments):
        extremites[cle(s.a)].append(i)
        extremites[cle(s.b)].append(i)

    def autre_bout(i: int, p: Point) -> Point:
        s = segments[i]
        return s.b if distance(s.a, p) <= pas else s.a

    vus: set[tuple[int, ...]] = set()
    formes: list[Forme] = []
    for i, s in enumerate(segments):
        depart, p = s.a, s.b
        chemin = [i]
        sommets = [depart, p]
        for _ in range(3):
            suivants = [j for j in extremites[cle(p)] if j not in chemin]
            if not suivants:
                break
            j = suivants[0]
            q = autre_bout(j, p)
            chemin.append(j)
            sommets.append(q)
            p = q
        if len(chemin) != 4 or distance(sommets[-1], depart) > pas:
            continue
        clef = tuple(sorted(chemin))
        if clef in vus:
            continue
        vus.add(clef)
        points = tuple(sommets[:4])
        if rectangle_de(points, tolerances) is None:
            continue
        prims = tuple(segments[k] for k in chemin)
        formes.append(Forme(points, False, prims,
                            classer(s.calque, s.source.blocs, s.type_ligne), "rectangle"))
    return formes


def formes_fermees(prims: PrimitivesDxf, tolerances: Tolerances,
                   segments_lignes: list[Segment]) -> list[Forme]:
    """Tous les contours fermés du dessin : polylignes, solides, hachures, cercles,
    et rectangles reconstitués à partir de ``LINE``."""
    formes: list[Forme] = []
    for c in prims.contours:
        classement = classer(c.calque, c.source.blocs, c.type_ligne)
        genre = "rectangle" if rectangle_de(c.points, tolerances) else "polygone"
        formes.append(Forme(c.points, c.rempli, (c,), classement, genre))
    for c in prims.cercles:
        classement = classer(c.calque, c.source.blocs, c.type_ligne)
        points = tuple((c.centre[0] + c.rayon * math.cos(2 * math.pi * k / 24),
                        c.centre[1] + c.rayon * math.sin(2 * math.pi * k / 24))
                       for k in range(24))
        formes.append(Forme(points, False, (c,), classement, "cercle", c.rayon))
    formes.extend(_rectangles_de_lignes(segments_lignes, tolerances))
    return formes


def _plausible(cotes: tuple[float, float], tolerances: Tolerances,
               entraxe: float | None) -> bool:
    petit, grand = min(cotes), max(cotes)
    if petit <= 0 or grand / petit > ELANCEMENT_MAX:
        return False
    if tolerances.mm_par_unite:
        return (petit * tolerances.mm_par_unite >= COTE_MIN_MM
                and grand * tolerances.mm_par_unite <= COTE_MAX_MM)
    if entraxe:
        return grand <= FRACTION_ENTRAXE_MAX * entraxe
    return True


def _cotes_de(forme: Forme, tolerances: Tolerances) -> tuple[float, float] | None:
    if forme.genre == "cercle" and forme.rayon is not None:
        return (2 * forme.rayon, 2 * forme.rayon)
    rect = rectangle_de(forme.points, tolerances)
    if rect is not None:
        return (rect.longueur_u, rect.longueur_v)
    x0, y0, x1, y1 = boite_de(forme.points)
    return (x1 - x0, y1 - y0)


def centre_et_taille(forme: Forme) -> tuple[Point, float]:
    """Le centre et la taille d'une forme : le cercle par son diamètre, le reste
    par le grand côté de sa boîte. « Même centre et même taille à 5 % » font le
    jumeau rempli d'un contour, et le dessin d'un pieu (G3)."""
    if forme.genre == "cercle" and forme.rayon is not None:
        pts = forme.points
        return ((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)),
                2.0 * forme.rayon)
    x0, y0, x1, y1 = boite_de(forme.points)
    return centroide(forme.points), max(x1 - x0, y1 - y0)


def _section(forme: Forme, tolerances: Tolerances) -> bool:
    """C1.1 — une SECTION : un rectangle, un cercle, ou un polygone inscrit (au
    moins 5 sommets, tous à la même distance de leur centre à 5 % près :
    hexagone, octogone, bord polygonal d'une hachure de cercle). Un triangle, un
    chevron, une barre biaise, un nuage n'en sont pas. Le genre d'une forme dit
    déjà si ``rectangle_de`` la reconnaît (``formes_fermees``)."""
    if forme.genre in ("cercle", "rectangle"):
        return True
    sommets = _sommets_utiles(forme.points, tolerances.longueur)
    if len(sommets) < SOMMETS_INSCRIT_MIN:
        return False
    centre = centroide(sommets)
    rayons = [distance(centre, p) for p in sommets]
    moyen = sum(rayons) / len(rayons)
    return moyen > 0 and all(abs(r - moyen) <= ECART_RELATIF * moyen for r in rayons)


def _index_des_noeuds(grille: Grille, tolerances: Tolerances) -> IndexSpatial:
    index = IndexSpatial(max(0.5 * (grille.entraxe_median() or 0.0), 10.0 * tolerances.longueur))
    for noeud in grille.noeuds:
        index.ajouter((noeud.point[0], noeud.point[1], noeud.point[0], noeud.point[1]))
    return index


def _noeud_proche(centre: Point, rayon: float, grille: Grille, points: tuple[Point, ...],
                  tolerances: Tolerances, index: IndexSpatial) -> str | None:
    """Le nœud le plus proche du centre : dans le contour, ou à ``rayon`` près.
    Seuls les nœuds de la boîte élargie du contour sont examinés."""
    meilleur: tuple[float, str] | None = None
    for rang in index.pres_de(boite_de(points), marge=rayon):
        noeud = grille.noeuds[rang]
        d = distance(centre, noeud.point)
        dedans = point_dans_polygone(noeud.point, points, tolerances.longueur)
        if (dedans or d <= rayon) and (meilleur is None or d < meilleur[0]):
            meilleur = (d, noeud.nom)
    return meilleur[1] if meilleur else None


class _Controle:
    """Les cinq règles d'une section, sur des index construits à la demande."""

    def __init__(self, prims: PrimitivesDxf, formes: list[Forme],
                 tolerances: Tolerances, entraxe: float | None) -> None:
        self.prims = prims
        self.formes = formes
        self.tol = tolerances
        self.entraxe = entraxe
        self._formes: IndexSpatial | None = None
        self._segments: IndexSpatial | None = None
        self._textes: IndexSpatial | None = None
        self._case_lue: float | None = None

    def _case(self) -> float:
        """La case des index : 1 % de la diagonale de l'emprise, lue une fois."""
        if self._case_lue is None:
            emprise = self.prims.emprise()
            diagonale = (math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
                         if emprise else 1.0)
            self._case_lue = max(10.0 * self.tol.longueur, 0.01 * diagonale)
        return self._case_lue

    def raison(self, rang: int, forme: Forme, cotes: tuple[float, float]) -> str | None:
        if forme.genre != "cercle" and compacite(forme.points) < COMPACITE_MIN:
            return "non_compact"
        if self._contient(rang, forme, cotes):
            return "contenant"
        if forme.genre == "rectangle" and self._barree(forme):
            return "ouverture_barree"
        if self._nommee(forme):
            return "ouverture_nommee"
        if not forme.rempli and self._dans_une_enceinte(rang, forme, cotes):
            return "dans_une_enceinte"
        return None

    def _index_des_formes(self) -> IndexSpatial:
        if self._formes is None:
            self._formes = IndexSpatial(self._case())
            for f in self.formes:
                self._formes.ajouter(boite_de(f.points) if f.points else (0.0, 0.0, 0.0, 0.0))
        return self._formes

    def _dans_une_enceinte(self, rang: int, forme: Forme, cotes: tuple[float, float]) -> bool:
        """Un contour VIDE dans un contour continu, vide, de la taille d'un poteau.

        Le contour d'un poteau hachuré a un JUMEAU plein (sa hachure, même
        boîte) : c'est une section, jamais l'équipement d'une gaine."""
        x0, y0, x1, y1 = boite_de(forme.points)
        grand = max(cotes)
        bord = 2.0 * self.tol.longueur
        voisins = self._index_des_formes().pres_de((x0, y0, x1, y1), marge=bord)
        for j in voisins:
            autre = self.formes[j]
            if j != rang and autre.rempli and autre.points:
                bx0, by0, bx1, by1 = boite_de(autre.points)
                if max(abs(bx0 - x0), abs(by0 - y0), abs(bx1 - x1), abs(by1 - y1)) <= bord:
                    return False
        for j in voisins:
            autre = self.formes[j]
            if (j == rang or not autre.points or autre.rempli or autre.classement.cache
                    or autre.classement.role != "inconnu"):
                continue
            bx0, by0, bx1, by1 = boite_de(autre.points)
            if not (bx0 < x0 and by0 < y0 and bx1 > x1 and by1 > y1):
                continue
            cotes_autre = _cotes_de(autre, self.tol)
            if (cotes_autre is None or grand > TAILLE_CONTENUE_MAX * min(cotes_autre)
                    or not _plausible(cotes_autre, self.tol, self.entraxe)):
                continue
            if all(point_dans_polygone(p, autre.points) for p in forme.points):
                return True
        return False

    def _contient(self, rang: int, forme: Forme, cotes: tuple[float, float]) -> bool:
        x0, y0, x1, y1 = boite_de(forme.points)
        petit = min(cotes)
        bord = self.tol.longueur
        for j in self._index_des_formes().pres_de((x0, y0, x1, y1)):
            autre = self.formes[j]
            if j == rang or not autre.points or autre.classement.role in _CONTENU_IGNORE:
                continue
            bx0, by0, bx1, by1 = boite_de(autre.points)
            if (bx0 <= x0 + bord or by0 <= y0 + bord or bx1 >= x1 - bord or by1 >= y1 - bord
                    or max(bx1 - bx0, by1 - by0) > TAILLE_CONTENUE_MAX * petit):
                continue
            if all(point_dans_polygone(p, forme.points)
                   and distance_point_polygone(p, forme.points) > bord for p in autre.points):
                return True
        return False

    def _barree(self, forme: Forme) -> bool:
        rect = rectangle_de(forme.points, self.tol)
        if rect is None:
            return False
        if self._segments is None:
            self._segments = IndexSpatial(self._case())
            for s in self.prims.segments:
                self._segments.ajouter(boite_de((s.a, s.b)))
        u, v = rect.u, rect.v
        hu, hv = rect.longueur_u / 2.0, rect.longueur_v / 2.0
        c = rect.centre
        coins = tuple((c[0] + su * hu * u[0] + sv * hv * v[0],
                       c[1] + su * hu * u[1] + sv * hv * v[1])
                      for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)))
        rayon = max(2.0 * self.tol.longueur, 0.02 * rect.petit_cote)
        trouvees = diagonales(coins, self.prims.segments, rayon,  # type: ignore[arg-type]
                              self._segments)
        paires = ((coins[0], coins[2]), (coins[1], coins[3]))

        def barre(c1: Point, c2: Point) -> bool:
            return any((distance(s.a, c1) <= rayon and distance(s.b, c2) <= rayon)
                       or (distance(s.a, c2) <= rayon and distance(s.b, c1) <= rayon)
                       for s in trouvees)

        return all(barre(c1, c2) for c1, c2 in paires)

    def _nommee(self, forme: Forme) -> bool:
        if self._textes is None:
            self._textes = IndexSpatial(self._case())
            for t in self.prims.textes:
                self._textes.ajouter((t.centre[0], t.centre[1], t.centre[0], t.centre[1]))
        for k in self._textes.pres_de(boite_de(forme.points)):
            t = self.prims.textes[k]
            if point_dans_polygone(t.centre, forme.points) and nomme_une_ouverture(t.texte):
                return True
        return False


def _centre_de(forme: Forme) -> Point:
    if forme.genre != "cercle":
        return centroide(forme.points)
    return (sum(p[0] for p in forme.points) / len(forme.points),
            sum(p[1] for p in forme.points) / len(forme.points))


def _echelle_un(echelle: tuple[float, float] | None) -> bool:
    return (echelle is not None and abs(abs(echelle[0]) - 1.0) <= 1e-9
            and abs(abs(echelle[1]) - 1.0) <= 1e-9)


#: Ce qu'une définition de bloc répété peut contenir : un contour de section, sa hachure.
_TYPES_DE_SECTION: Final[frozenset[str]] = frozenset(
    {"LWPOLYLINE", "POLYLINE", "CIRCLE", "HATCH", "SOLID"})


def zone_des_poteaux(grille: Grille, zone_g2: tuple[float, float, float, float] | None
                     ) -> tuple[tuple[float, float, float, float] | None, str]:
    """C1.5 — la zone structurelle : celle de G2 (les axes à bulle et famille,
    élargis d'un entraxe médian) ; à défaut (feuille PDF, grille nommée sans
    signature A), l'enveloppe des axes ÉTIQUETÉS élargie d'un entraxe médian ;
    sans axe étiqueté, le critère ne s'applique pas — et le compte rendu le dit."""
    if zone_g2 is not None:
        return zone_g2, "signature_a"
    etiquetes = [p for a in grille.axes if a.etiquette for p in a.extremites]
    if not etiquetes:
        return None, "non_applicable"
    x0, y0, x1, y1 = boite_de(etiquetes)
    marge = grille.entraxe_median() or 0.0
    return (x0 - marge, y0 - marge, x1 + marge, y1 + marge), "axes_etiquetes"


@dataclass
class _Candidat:
    """Un contour qui peut faire un poteau, et ce qui le décide."""

    forme: Forme
    rang: int
    #: L'ORDRE D'AUJOURD'HUI choisit la forme qui donne sa géométrie au poteau :
    #: 0 nommé poteau, 1 sans rôle et rempli, 2 sans rôle et vide ; 3 d'un autre
    #: rôle (le jumeau rempli d'une section, ou le cas 5).
    ordre: int
    #: C1 complète (le nom mis à part).
    complet: bool
    #: Coupé : rempli, ou doublé d'un contour rempli de même centre et taille.
    coupe: bool
    #: Le rang de ce jumeau rempli, quand il coupe un contour vide.
    jumeau: int | None = None
    #: Ce qui fait poteau d'une section vide : ``bloc_repete``, ``repere`` ; ou
    #: ``grille_implicite`` (C2, sans grille).
    completion: str | None = None


class _Signature:
    """Les critères de G4 qui demandent un index, construits à la demande."""

    def __init__(self, prims: PrimitivesDxf, formes: list[Forme], tolerances: Tolerances,
                 entraxe: float | None, zone: tuple[float, float, float, float] | None,
                 pieux_lus: Sequence[Pieu], case: float) -> None:
        self.prims = prims
        self.formes = formes
        self.tol = tolerances
        self.entraxe = entraxe
        self.zone = zone
        self.pieux_lus = pieux_lus
        self.case = case
        self._jumeaux: dict[int, int | None] = {}
        self._pleins: tuple[IndexSpatial, list[int]] | None = None
        self._pieux: tuple[IndexSpatial, list[tuple[Point, float]]] | None = None
        self._plages: tuple[IndexSpatial, list[tuple[int, Rectangle]]] | None = None
        self._reperes: tuple[IndexSpatial, list[int]] | None = None
        self._insertions: tuple[dict[tuple[str, tuple[str, ...]], Insertion],
                                Counter[str]] | None = None

    # ------------------------------------------------------------ C1.2 coupé
    def jumeau(self, rang: int, forme: Forme) -> int | None:
        """Le contour rempli de même centre et de même taille (5 %) qui double un
        contour vide, QUEL QUE SOIT SON CALQUE : la hachure d'un poteau posée sur
        un calque d'annotation coupe toujours le poteau (N1)."""
        if forme.rempli or not forme.points:
            return None
        if rang in self._jumeaux:
            return self._jumeaux[rang]
        if self._pleins is None:
            rangs = [k for k, f in enumerate(self.formes) if f.rempli and f.points]
            index = IndexSpatial(self.case)
            for k in rangs:
                index.ajouter(boite_de(self.formes[k].points))
            self._pleins = (index, rangs)
        index, rangs = self._pleins
        centre, taille = centre_et_taille(forme)
        seuil = max(2.0 * self.tol.longueur, ECART_RELATIF * taille)
        trouve: int | None = None
        for k in index.pres_de(boite_de(forme.points), marge=seuil):
            j = rangs[k]
            if j == rang:
                continue
            cj, tj = centre_et_taille(self.formes[j])
            if distance(cj, centre) <= seuil and abs(tj - taille) <= seuil:
                trouve = j
                break
        self._jumeaux[rang] = trouve
        return trouve

    def coupe(self, rang: int, forme: Forme) -> bool:
        return forme.rempli or self.jumeau(rang, forme) is not None

    # ---------------------------------------------------- C1.5 zone, C1.6 pieu
    def dans_la_zone(self, centre: Point) -> bool:
        z = self.zone
        return z is None or (z[0] <= centre[0] <= z[2] and z[1] <= centre[1] <= z[3])

    def pieu_sans_nom(self, forme: Forme) -> bool:
        """Même centre et même taille (5 %) qu'un pieu de G3, quel que soit le
        calque : G3 n'absorbe dans le dessin d'un pieu que les contours sans rôle
        ou de pieu ; la hachure d'un pieu sur un calque « texte » n'est pas plus
        un poteau que les autres."""
        if not self.pieux_lus or not forme.points:
            return False
        if self._pieux is None:
            empreintes: list[tuple[Point, float]] = []
            index = IndexSpatial(self.case)
            for pieu in self.pieux_lus:
                if pieu.diametre is not None:
                    taille = pieu.diametre
                elif pieu.contour:
                    x0, y0, x1, y1 = boite_de(pieu.contour)
                    taille = max(x1 - x0, y1 - y0)
                else:
                    continue
                empreintes.append((pieu.centre, taille))
                r = taille / 2.0
                index.ajouter((pieu.centre[0] - r, pieu.centre[1] - r,
                               pieu.centre[0] + r, pieu.centre[1] + r))
            self._pieux = (index, empreintes)
        index, empreintes = self._pieux
        centre, taille = centre_et_taille(forme)
        marge = max(5.0 * self.tol.longueur, ECART_RELATIF * taille)
        for k in index.pres_de((centre[0], centre[1], centre[0], centre[1]), marge=marge):
            cp, tp = empreintes[k]
            seuil = max(5.0 * self.tol.longueur, ECART_RELATIF * max(tp, taille))
            if distance(cp, centre) <= seuil and abs(tp - taille) <= seuil:
                return True
        return False

    # ------------------------------------------------------ C1.10 bout de voile
    def bout_de_voile(self, rang: int, forme: Forme, cotes: tuple[float, float],
                      centre: Point) -> bool:
        """Un côté égal (5 %) à l'épaisseur d'une plage remplie allongée
        (élancement 4 au moins, épaisseur plausible de voile), le centre sur
        l'axe de la plage (5 % de l'épaisseur), une face sur son extrémité (deux
        tolérances) : le bout d'un voile, pas un poteau."""
        if self._plages is None:
            from .voiles import _epaisseur_plausible  # voiles lit ce module

            plages: list[tuple[int, Rectangle]] = []
            index = IndexSpatial(self.case)
            for k, f in enumerate(self.formes):
                if not f.rempli or f.genre != "rectangle" or not f.points:
                    continue
                rect = rectangle_de(f.points, self.tol)
                if (rect is None or rect.elancement < ELANCEMENT_MAX
                        or not _epaisseur_plausible(rect.petit_cote, self.tol, self.entraxe)):
                    continue
                plages.append((k, rect))
                index.ajouter(boite_de(f.points))
            self._plages = (index, plages)
        index, plages = self._plages
        bord = 2.0 * self.tol.longueur
        for k in index.pres_de(boite_de(forme.points), marge=bord):
            rang_plage, rect = plages[k]
            if rang_plage == rang:
                continue
            e = rect.petit_cote
            if not any(abs(c - e) <= ECART_RELATIF * e for c in cotes):
                continue
            u = rect.direction_longue()
            if distance_point_droite(centre, rect.centre, u) > ECART_RELATIF * e:
                continue
            abscisses = [projeter(p, rect.centre, u) for p in forme.points]
            demi = rect.grand_cote / 2.0
            if abs(min(abscisses) - demi) <= bord or abs(max(abscisses) + demi) <= bord:
                return True
        return False

    # ---------------------------------------------------- les complétions
    def bloc_repete(self, forme: Forme) -> bool:
        """N1 — une section VIDE complétée par un bloc répété : la même définition
        insérée au moins 3 fois à l'échelle 1 (|x| = |y| = 1), celle-ci comprise,
        qui ne contient qu'un contour fermé de section — et peut-être sa
        hachure —, sans attribut ni texte. Un repère de niveau (un triangle, un
        trait, un attribut, inséré à l'échelle 5) n'en est pas un."""
        source: Source = forme.primitives[0].source
        if not source.blocs or not source.insertions:
            return False
        nom = source.blocs[-1]
        definition = self.prims.definitions.get(nom)
        if definition is None or definition.attributs or definition.xref:
            return False
        types = definition.types
        polylignes = types.get("LWPOLYLINE", 0) + types.get("POLYLINE", 0)
        if (definition.fermes + types.get("CIRCLE", 0) != 1 or polylignes != definition.fermes
                or types.get("HATCH", 0) + types.get("SOLID", 0) > 1
                or any(t not in _TYPES_DE_SECTION for t in types)):
            return False
        if self._insertions is None:
            par_cle = {(i.source.poignee, i.source.insertions): i for i in self.prims.insertions}
            a_l_echelle_un = Counter(i.nom_bloc for i in self.prims.insertions
                                     if _echelle_un(i.echelle))
            self._insertions = (par_cle, a_l_echelle_un)
        par_cle, a_l_echelle_un = self._insertions
        insertion = par_cle.get((source.insertions[-1], source.insertions[:-1]))
        return (insertion is not None and _echelle_un(insertion.echelle)
                and a_l_echelle_un[nom] >= INSERTIONS_BLOC_MIN)

    def repere(self, forme: Forme, cotes: tuple[float, float], centre: Point) -> bool:
        """Une section VIDE complétée par un repère de poteau voisin — un texte
        aux préfixes de poteau du lecteur de repères (``C3``, ``POT12``,
        « poteau P3 ») —, dans la section ou à moins d'un grand côté de son
        centre. Un texte de pieu n'est le repère d'aucun poteau."""
        if self._reperes is None:
            rangs: list[int] = []
            index = IndexSpatial(self.case)
            for k, t in enumerate(self.prims.textes):
                role = classer(t.calque, t.source.blocs, t.type_ligne).role
                if role in ("pieu", "fondation") or nomme_un_pieu(t.texte):
                    continue
                lu = lire_repere(t.texte)
                if lu is None or not (lu["genre_mot"] == "poteau" or (
                        lu["genre_mot"] is None and lu["genre_prefixe"] == "poteau")):
                    continue
                rangs.append(k)
                index.ajouter((t.centre[0], t.centre[1], t.centre[0], t.centre[1]))
            self._reperes = (index, rangs)
        index, rangs = self._reperes
        grand = max(cotes)
        for k in index.pres_de(boite_de(forme.points), marge=grand):
            t = self.prims.textes[rangs[k]]
            if point_dans_polygone(t.centre, forme.points) or distance(t.centre, centre) <= grand:
                return True
        return False


def _files(points: list[tuple[float, float]], rangs: set[int], long: int, eps: float
           ) -> list[list[int]]:
    """Les files de sections alignées le long d'une direction : ``long`` est la
    coordonnée le long de la file (0 ou 1), l'autre doit être la même à ``eps``
    près, et deux voisines alignées à 1° au plus."""
    travers = 1 - long
    ordre = sorted(rangs, key=lambda i: (points[i][travers], points[i][long]))
    paquets: list[list[int]] = []
    for i in ordre:
        if paquets and abs(points[i][travers] - points[paquets[-1][-1]][travers]) <= eps:
            paquets[-1].append(i)
        else:
            paquets.append([i])
    tangente = math.tan(math.radians(ALIGNEMENT_C2_DEG))
    files: list[list[int]] = []
    for paquet in paquets:
        paquet.sort(key=lambda i: points[i][long])
        courante = [paquet[0]]
        for i in paquet[1:]:
            j = courante[-1]
            if abs(points[i][travers] - points[j][travers]) <= (
                    tangente * abs(points[i][long] - points[j][long]) + 1e-12):
                courante.append(i)
            else:
                files.append(courante)
                courante = [i]
        files.append(courante)
    return files


def _grille_implicite(formes: list[Forme], tolerances: Tolerances, sig: _Signature,
                      controle: _Controle, pieux: Collection[int], exclues: Collection[int]
                      ) -> list[_Candidat]:
    """C2 — SANS AUCUNE GRILLE : au moins 3 sections identiques (côtés triés à
    1 %), coupées, de taille plausible (UNITÉ CONNUE : sans grille, aucun
    entraxe ne borne la taille), qui ne sont ni un pieu, ni un contenant, ni une
    trémie, ni un bout de voile, dont les centres s'alignent dans deux
    directions perpendiculaires (celle de la section et sa normale, à 1°), au
    moins 3 par file dans chaque direction, à un entraxe implicite (médiane des
    écarts entre voisines d'une file) de 4 grands côtés au moins et de 20 m au
    plus. Des poteaux, jamais des axes : rien n'est inventé."""
    if not tolerances.mm_par_unite:
        return []
    retenues: list[tuple[int, Forme, tuple[float, float], Point]] = []
    for rang, forme in enumerate(formes):
        if forme.classement.role not in _SANS_ROLE or not forme.points:
            continue
        cotes = _cotes_de(forme, tolerances)
        if cotes is None or not _plausible(cotes, tolerances, None):
            continue
        centre = _centre_de(forme)
        if (not _section(forme, tolerances) or not sig.coupe(rang, forme)
                or rang in pieux or rang in exclues or sig.pieu_sans_nom(forme)
                or controle.raison(rang, forme, cotes) is not None
                or sig.bout_de_voile(rang, forme, cotes, centre)):
            continue
        retenues.append((rang, forme, cotes, centre))

    # UNE POSITION PAR SECTION : son contour, sa hachure, leurs copies.
    positions: list[tuple[Point, tuple[float, float], list[int]]] = []
    index = IndexSpatial(sig.case)
    for k, (_r, _f, cotes, centre) in enumerate(retenues):
        seuil = max(5.0 * tolerances.longueur, ECART_RELATIF * max(cotes))
        for g in index.pres_de((centre[0], centre[1], centre[0], centre[1]), marge=seuil):
            gc, gcotes, membres = positions[g]
            if (distance(gc, centre) <= seuil and abs(max(gcotes) - max(cotes)) <= seuil
                    and abs(min(gcotes) - min(cotes)) <= seuil):
                membres.append(k)
                break
        else:
            positions.append((centre, cotes, [k]))
            index.ajouter((centre[0], centre[1], centre[0], centre[1]))

    # LES CLASSES DE SECTIONS IDENTIQUES : même forme, côtés triés à 1 %, et,
    # pour un rectangle, même orientation à 1°.
    def orientation(k: int) -> float | None:
        forme = retenues[positions[k][2][0]][1]
        rect = rectangle_de(forme.points, tolerances)
        return None if rect is None else angle_deg(rect.u) % 90.0

    classes: list[list[int]] = []
    for k, (_c, cotes, membres) in enumerate(positions):
        genre = retenues[membres[0]][1].genre
        petit, grand = sorted(cotes)
        theta = orientation(k)
        for classe in classes:
            k0 = classe[0]
            p0, g0 = sorted(positions[k0][1])
            t0 = orientation(k0)
            if (retenues[positions[k0][2][0]][1].genre == genre
                    and abs(p0 - petit) <= ECART_SECTION * p0
                    and abs(g0 - grand) <= ECART_SECTION * g0
                    and ((theta is None and t0 is None) or (
                        theta is not None and t0 is not None
                        and ecart_angulaire(theta, t0) <= ALIGNEMENT_C2_DEG))):
                classe.append(k)
                break
        else:
            classes.append([k])

    candidats: list[_Candidat] = []
    for classe in classes:
        if len(classe) < SECTIONS_PAR_FILE_C2:
            continue
        theta = orientation(classe[0])
        u = ((1.0, 0.0) if theta is None
             else (math.cos(math.radians(theta)), math.sin(math.radians(theta))))
        v = normale(u)
        points = [(projeter(positions[k][0], (0.0, 0.0), u),
                   projeter(positions[k][0], (0.0, 0.0), v)) for k in classe]
        grand = max(max(positions[k][1]) for k in classe)
        eps = max(2.0 * tolerances.longueur, ECART_RELATIF * grand)
        bons = set(range(len(classe)))
        while bons:
            dans_u = {i for f in _files(points, bons, 0, eps)
                      if len(f) >= SECTIONS_PAR_FILE_C2 for i in f}
            dans_v = {i for f in _files(points, bons, 1, eps)
                      if len(f) >= SECTIONS_PAR_FILE_C2 for i in f}
            garder = dans_u & dans_v
            if garder == bons:
                break
            bons = garder
        if not bons:
            continue
        ecarts: list[float] = []
        for long in (0, 1):
            for f in _files(points, bons, long, eps):
                if len(f) >= SECTIONS_PAR_FILE_C2:
                    ecarts.extend(points[b][long] - points[a][long]
                                  for a, b in zip(f, f[1:], strict=False))
        if not ecarts:
            continue
        ecarts.sort()
        entraxe = ecarts[len(ecarts) // 2]
        if (entraxe < ENTRAXE_C2_MIN_COTES * grand
                or entraxe * tolerances.mm_par_unite > ENTRAXE_C2_MAX_MM):
            continue
        for i in sorted(bons):
            for m in positions[classe[i]][2]:
                rang, forme, _cotes, _centre = retenues[m]
                candidats.append(_Candidat(forme, rang, 1 if forme.rempli else 2, False, True,
                                           sig.jumeau(rang, forme), "grille_implicite"))
    return candidats


def detecter_poteaux(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                     formes: list[Forme], exclues: Collection[int] = frozenset(),
                     pieux: Collection[int] = frozenset(), *,
                     zone: tuple[float, float, float, float] | None = None,
                     pieux_lus: Sequence[Pieu] = ()
                     ) -> tuple[list[Poteau], set[int], list[NonResolu], Counter[str],
                                dict[str, Any]]:
    """Les poteaux, les rangs des formes utilisées, les doutes, les candidats
    écartés par raison, et le compte rendu des poteaux. ``exclues`` : les formes
    qui sont le dessin d'un pieu ; ``pieux`` : celles qui SONT un pieu (germes
    nommés ou géométriques, G3) ; ``pieux_lus`` : les pieux, pour reconnaître
    leur dessin sur n'importe quel calque ; ``zone`` : la zone structurelle de G2."""
    entraxe = grille.entraxe_median()
    index_noeuds = _index_des_noeuds(grille, tolerances)
    doutes: list[NonResolu] = []
    rejets: Counter[str] = Counter()
    #: Un contour écarté compte une fois, même dessiné deux fois (polyligne et
    #: ses traits, calque et copie de xréf).
    rejets_vus: set[tuple[str, tuple[int, ...]]] = set()
    pas = max(2.0 * tolerances.longueur, 1e-9)
    controle = _Controle(prims, formes, tolerances, entraxe)
    boite_zone, source_zone = zone_des_poteaux(grille, zone)
    sig = _Signature(prims, formes, tolerances, entraxe, boite_zone, pieux_lus,
                     controle._case())

    def rejeter(raison: str, forme: Forme) -> None:
        cle = (raison, tuple(round(v / pas) for v in boite_de(forme.points)))
        if cle not in rejets_vus:
            rejets_vus.add(cle)
            rejets[raison] += 1

    def complete(rang: int, forme: Forme, cotes: tuple[float, float], centre: Point) -> bool:
        """C1, le nom mis à part — le nœud et la taille sont déjà vus. Les
        critères les moins coûteux d'abord."""
        return (_section(forme, tolerances) and sig.dans_la_zone(centre)
                and sig.coupe(rang, forme) and rang not in pieux and rang not in exclues
                and not sig.pieu_sans_nom(forme)
                and controle.raison(rang, forme, cotes) is None
                and not sig.bout_de_voile(rang, forme, cotes, centre))

    candidats: list[_Candidat] = []
    #: Les formes de pieu ou de fondation à C1 complète : comptées comme
    #: aujourd'hui, sauf si elles font un poteau du cas 5.
    reportees: dict[int, str] = {}
    for rang, forme in enumerate(formes):
        role = forme.classement.role
        cotes = _cotes_de(forme, tolerances)
        if cotes is None:
            continue
        if (role not in _SANS_ROLE and role not in ("poteau", "pieu", "fondation")
                and not (_plausible(cotes, tolerances, entraxe) and _section(forme, tolerances)
                         and sig.coupe(rang, forme))):
            continue  # d'un autre rôle, sans section coupée : ignoré, comme aujourd'hui
        centre = _centre_de(forme)
        noeud = _noeud_proche(centre, 0.5 * max(cotes), grille, forme.points, tolerances,
                              index_noeuds)
        if role == "poteau":
            if rang in pieux:
                # UN GERME DE PIEU N'EST JAMAIS UN POTEAU, même sur un calque de
                # poteaux : la signature P décide, le conflit est dit par pieux.py.
                continue
            if not _plausible(cotes, tolerances, entraxe):
                if max(cotes) / max(min(cotes), 1e-12) > ELANCEMENT_MAX:
                    continue  # allongé: un voile sur un calque de poteaux (voiles.py)
                doutes.append(NonResolu(
                    f"contour {forme.primitives[0].source.poignee}",
                    "contour sur calque de poteaux hors des dimensions plausibles"))
                continue
            candidats.append(_Candidat(
                forme, rang, 0, noeud is not None and complete(rang, forme, cotes, centre),
                sig.coupe(rang, forme), sig.jumeau(rang, forme)))
            continue
        if noeud is None or not _plausible(cotes, tolerances, entraxe):
            continue
        if role not in _SANS_ROLE:
            # D'UN AUTRE RÔLE : seule une C1 complète en fait un poteau (cas 5,
            # ou le jumeau rempli d'une section) ; sinon comme aujourd'hui.
            if complete(rang, forme, cotes, centre):
                candidats.append(_Candidat(forme, rang, 3, True, True, sig.jumeau(rang, forme)))
                if role in ("pieu", "fondation"):
                    reportees[rang] = role
            elif role in ("pieu", "fondation"):
                rejeter(role, forme)
            continue
        # SANS RÔLE, AU NŒUD : les raisons d'aujourd'hui d'abord, puis celles de G4.
        if rang in pieux:
            raison: str | None = "pieu"
        elif rang in exclues or sig.pieu_sans_nom(forme):
            raison = "dessin_de_pieu"
        else:
            raison = controle.raison(rang, forme, cotes)
        if raison is None and not _section(forme, tolerances):
            raison = "section_irreguliere"
        if raison is None and not sig.dans_la_zone(centre):
            raison = "hors_zone"
        if raison is None and sig.bout_de_voile(rang, forme, cotes, centre):
            raison = "bout_de_voile"
        if raison is not None:
            rejeter(raison, forme)
            continue
        if sig.coupe(rang, forme):
            candidats.append(_Candidat(forme, rang, 1 if forme.rempli else 2, True, True,
                                       sig.jumeau(rang, forme)))
            continue
        # PARTIELLE (vide) : un bloc répété ou un repère de poteau la complète.
        if sig.bloc_repete(forme):
            completion: str | None = "bloc_repete"
        elif sig.repere(forme, cotes, centre):
            completion = "repere"
        else:
            rejeter("partielle_vide", forme)
            continue
        candidats.append(_Candidat(forme, rang, 2, False, False, None, completion))

    if not grille.familles:
        candidats.extend(_grille_implicite(formes, tolerances, sig, controle, pieux, exclues))

    # UN POTEAU DESSINE DEUX FOIS (contour et hachure) N'EN FAIT QU'UN. La forme
    # qui donne sa géométrie est celle d'aujourd'hui : nommée, puis pleine.
    groupes: list[list[_Candidat]] = []
    tetes: list[tuple[Point, tuple[float, float]]] = []
    index_groupes = IndexSpatial(max(0.5 * (entraxe or 0.0), 10.0 * tolerances.longueur))
    for item in sorted(candidats, key=lambda c: (c.ordre, c.rang)):
        forme = item.forme
        c = centroide(forme.points)
        cotes = _cotes_de(forme, tolerances) or (0.0, 0.0)
        # Le seuil d'un groupe vaut au plus ~5,3 % de ses côtés, qui sont ceux
        # de la forme à 5 % près: 6 % de la forme borne la recherche.
        marge = max(5.0 * tolerances.longueur, 0.06 * max(cotes))
        for g in index_groupes.pres_de((c[0], c[1], c[0], c[1]), marge=marge):
            gc, gcotes = tetes[g]
            seuil = max(5.0 * tolerances.longueur, 0.05 * max(gcotes))
            if (distance(c, gc) <= seuil
                    and abs(max(cotes) - max(gcotes)) <= seuil
                    and abs(min(cotes) - min(gcotes)) <= seuil):
                groupes[g].append(item)
                break
        else:
            groupes.append([item])
            tetes.append((c, cotes))
            index_groupes.ajouter((c[0], c[1], c[0], c[1]))

    zone_vue = ("zone",) if boite_zone is not None else ()
    poteaux: list[Poteau] = []
    cotes_des_poteaux: list[tuple[float, float]] = []
    conflits: list[str | None] = []
    utilises: set[int] = set()
    repere_x = grille.repere_x
    angle_x = angle_deg(repere_x)
    for groupe in groupes:
        tete = groupe[0]
        propres = [c for c in groupe if c.ordre != 3]
        # LE NOM QUI COMPTE EST CELUI DU CONTOUR de la section ; une section
        # dessinée par sa seule hachure prend le nom de la hachure.
        conflit: str | None = None
        signature: tuple[str, ...] = ()
        #: La décision a lu « coupé » (C1.2, C2, cas 5) : le jumeau rempli qui
        #: coupe un contour vide est cité, et le poteau est plein.
        par_la_coupe = True
        if not propres:
            # CAS 5 : une signature complète sur un contour d'un autre rôle.
            contours = [c for c in groupe if not c.forme.rempli] or groupe
            autre = contours[0].forme.classement
            confiance, regle, motif = PLAFOND_CONFLIT, "geometrie", None
            signature = ("section", "coupe", "au_noeud", *zone_vue)
            conflit = (f"signature geometrique de poteau (section coupee au noeud) sur un "
                       f"contour nomme d'un autre role: {autre.role} ({autre.motif}); le poteau "
                       f"est garde, sa confiance plafonnee a 0,4")
            utilises.update(c.rang for c in groupe)
        else:
            utilises.update(c.rang for c in propres)
            contours = [c for c in propres if not c.forme.rempli] or propres
            nomme = next((c for c in contours if c.ordre == 0), None)
            complet = any(c.complet for c in propres)
            if nomme is not None and complet:
                confiance, regle = CONFIANCE_CONCORDANTE, "geometrie"
                motif = nomme.forme.classement.motif
                signature = ("section", "coupe", "au_noeud", *zone_vue)
            elif complet:
                confiance, regle, motif = CONFIANCE_C1, "geometrie", None
                signature = ("section", "coupe", "au_noeud", *zone_vue)
            elif tete.ordre == 0:
                # La règle du nom, comme aujourd'hui.
                confiance = CONFIANCE_NOM
                regle, motif = tete.forme.classement.regle, tete.forme.classement.motif
                par_la_coupe = False
            else:
                # UNE SECTION VIDE, COMPLÉTÉE : celle que rien ne complète a été
                # écartée, et comptée (``partielle_vide``).
                completion = next(c.completion for c in propres if c.completion)
                motif = None
                if completion == "grille_implicite":
                    confiance, regle = CONFIANCE_C2, "geometrie"
                    signature = ("section", "coupe", "grille_implicite")
                elif completion == "bloc_repete":
                    confiance, regle = CONFIANCE_BLOC_REPETE, "geometrie"
                    signature = ("section", "au_noeud", "bloc_repete", *zone_vue)
                    par_la_coupe = False
                else:
                    confiance, regle = CONFIANCE_REPERE, "forme"
                    signature = ("section", "au_noeud", "repere", *zone_vue)
                    par_la_coupe = False
        forme = tete.forme
        primitives = [p for item in groupe for p in item.forme.primitives]
        if par_la_coupe:
            primitives.extend(p for item in groupe if item.jumeau is not None
                              for p in formes[item.jumeau].primitives)
        preuve: Preuve = preuve_de(primitives, regle, motif, signature)
        rempli = any(item.coupe if par_la_coupe else item.forme.rempli for item in groupe)
        if forme.genre == "cercle" and forme.rayon is not None:
            centre = _centre_de(forme)
            largeur = profondeur = None
            diametre: float | None = 2.0 * forme.rayon
            angle = 0.0
            genre = "cercle"
        else:
            rect = rectangle_de(forme.points, tolerances)
            diametre = None
            if rect is not None:
                centre = rect.centre
                ecart = ecart_angulaire(angle_deg(rect.u), angle_x)
                if ecart <= 45.0:
                    largeur, profondeur = rect.longueur_u, rect.longueur_v
                else:
                    largeur, profondeur = rect.longueur_v, rect.longueur_u
                angle = ((angle_deg(rect.u) - angle_x + 45.0) % 90.0) - 45.0
                genre = "rectangle"
            else:
                centre = centroide(forme.points)
                largeur = profondeur = None
                angle = 0.0
                genre = "polygone"
        cotes = _cotes_de(forme, tolerances) or (0.0, 0.0)
        noeud = _noeud_proche(centre, 0.5 * max(cotes), grille, forme.points, tolerances,
                              index_noeuds)
        poteaux.append(Poteau(
            id="", forme=genre, contour=forme.points, centre=centre, largeur=largeur,
            profondeur=profondeur, diametre=diametre, angle=angle, noeud=noeud,
            rempli=rempli, preuve=preuve, confiance=confiance))
        cotes_des_poteaux.append((min(cotes), max(cotes)))
        conflits.append(conflit)

    # SECTION RÉPÉTÉE : une corroboration citée, jamais décisive — la section
    # appartient à une classe d'au moins deux sections identiques (côtés triés à 1 %).
    for i, p in enumerate(poteaux):
        if not p.preuve.signature:
            continue
        petit, grand = cotes_des_poteaux[i]
        if any(j != i and q.forme == p.forme
               and abs(cotes_des_poteaux[j][0] - petit) <= ECART_SECTION * max(petit, 1e-12)
               and abs(cotes_des_poteaux[j][1] - grand) <= ECART_SECTION * max(grand, 1e-12)
               for j, q in enumerate(poteaux)):
            poteaux[i] = replace(p, preuve=replace(
                p.preuve, signature=tuple(sorted({*p.preuve.signature, "section_repetee"}))))

    for rang, raison in sorted(reportees.items()):
        if rang not in utilises:
            rejeter(raison, formes[rang])

    # DES IDENTIFIANTS STABLES: par nœud quand il y en a un, sinon par position.
    ordre = sorted(range(len(poteaux)), key=lambda i: (
        poteaux[i].noeud is None, poteaux[i].noeud or "", round(poteaux[i].centre[1], 6),
        round(poteaux[i].centre[0], 6)))
    vus: dict[str, int] = {}
    nommes: list[Poteau] = []
    for rang, i in enumerate(ordre, start=1):
        p = poteaux[i]
        base = f"column:{p.noeud}" if p.noeud else f"column:{rang}"
        if base in vus:
            vus[base] += 1
            base = f"{base}#{vus[base]}"
        else:
            vus[base] = 1
        nommes.append(replace(p, id=base))
        conflit_dit = conflits[i]
        if conflit_dit is not None:
            doutes.append(NonResolu(base, conflit_dit))
    compte_rendu: dict[str, Any] = {}
    if nommes or grille.noeuds:
        compte_rendu = {
            "by_rule": dict(sorted(Counter(p.preuve.regle for p in nommes).items())),
            "structural_zone": source_zone}
    return nommes, utilises, doutes, rejets, compte_rendu
