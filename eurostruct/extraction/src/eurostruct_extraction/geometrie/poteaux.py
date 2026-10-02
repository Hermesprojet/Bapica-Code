"""Les poteaux : des contours fermés, pleins ou non, ronds ou rectangulaires.

DEUX MANIÈRES DE LES RECONNAÎTRE, ET LE FONDEMENT DIT LAQUELLE
---------------------------------------------------------------
* par leur CALQUE ou leur BLOC (`POTEAUX`, `S-COLS`, bloc `POT30x30`) :
  confiance 0,85 ;
* par leur FORME ET LEUR POSITION sur un calque qui ne dit rien (`COFFRAGE`,
  `0`) : un contour fermé, d'élancement au plus 4, qui CONTIENT un nœud de la
  grille (ou y est centré). Confiance 0,6. Hors nœud, un rectangle isolé n'est
  pas un poteau : c'est souvent une coupe, un détail, une réservation.

UNE SECTION DE POTEAU EST PLEINE ET COMPACTE (``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md``,
§ 2). Un candidat reconnu par la seule forme est écarté, et la raison comptée,
s'il est le dessin d'un pieu, s'il CONTIENT un autre contour fermé plus petit
(socle, massif, gaine, pièce), s'il n'est pas compact (chevron de gaine, flèche),
s'il est barré de ses deux diagonales (trémie), si un texte posé dedans le
nomme ouverture (« GAINE », « ASC. »), ou si, VIDE, il est posé dans une
enceinte continue de la taille d'un poteau (la cabine dans la gaine) — une
enceinte cachée, elle, est sous la coupe (un socle) : le poteau qu'elle porte
reste un poteau. Un poteau nommé par son calque ou son bloc garde la règle de
son nom. Un pieu, un massif ne sont jamais des poteaux.

UN POTEAU DESSINÉ DEUX FOIS (contour ET hachure) N'EST QU'UN POTEAU, avec deux
preuves. Un poteau dessiné en quatre ``LINE`` est reconstitué : quatre
segments qui se ferment à angles droits.

LES CÔTÉS SONT DONNÉS DANS LE REPÈRE DE LA GRILLE : la largeur selon la
famille d'axes la plus proche de l'horizontale, la profondeur selon l'autre.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Collection
from dataclasses import dataclass, replace
from typing import Final

from .classification import Classement, classer
from .modele import Grille, NonResolu, Poteau, Preuve, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    angle_deg,
    boite_de,
    centroide,
    compacite,
    distance,
    distance_point_polygone,
    ecart_angulaire,
    point_dans_polygone,
    rectangle_de,
)
from .ouvertures import diagonales, nomme_une_ouverture
from .primitives import Primitive, PrimitivesDxf, Segment

__all__ = ["Forme", "detecter_poteaux", "formes_fermees"]

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

    def _case(self) -> float:
        emprise = self.prims.emprise()
        diagonale = (math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
                     if emprise else 1.0)
        return max(10.0 * self.tol.longueur, 0.01 * diagonale)

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


def detecter_poteaux(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                     formes: list[Forme], exclues: Collection[int] = frozenset()
                     ) -> tuple[list[Poteau], set[int], list[NonResolu], Counter[str]]:
    """Les poteaux, les rangs des formes utilisées, les doutes, et les candidats
    écartés par raison. ``exclues`` : les formes qui sont le dessin d'un pieu."""
    entraxe = grille.entraxe_median()
    index_noeuds = _index_des_noeuds(grille, tolerances)
    retenus: list[tuple[Forme, int, float, str, str | None]] = []
    doutes: list[NonResolu] = []
    rejets: Counter[str] = Counter()
    #: Un contour écarté compte une fois, même dessiné deux fois (polyligne et
    #: ses traits, calque et copie de xréf).
    rejets_vus: set[tuple[str, tuple[int, ...]]] = set()
    pas = max(2.0 * tolerances.longueur, 1e-9)
    controle = _Controle(prims, formes, tolerances, entraxe)
    for rang, forme in enumerate(formes):
        role, regle = forme.classement.role, forme.classement.regle
        if role in _JAMAIS and role not in ("pieu", "fondation"):
            continue
        cotes = _cotes_de(forme, tolerances)
        if cotes is None:
            continue
        centre = centroide(forme.points) if forme.genre != "cercle" else (
            sum(p[0] for p in forme.points) / len(forme.points),
            sum(p[1] for p in forme.points) / len(forme.points))
        noeud = _noeud_proche(centre, 0.5 * max(cotes), grille, forme.points, tolerances,
                              index_noeuds)
        if role == "poteau":
            if not _plausible(cotes, tolerances, entraxe):
                if max(cotes) / max(min(cotes), 1e-12) > ELANCEMENT_MAX:
                    continue  # allongé: un voile sur un calque de poteaux (voiles.py)
                doutes.append(NonResolu(
                    f"contour {forme.primitives[0].source.poignee}",
                    "contour sur calque de poteaux hors des dimensions plausibles"))
                continue
            retenus.append((forme, rang, 0.85, regle, forme.classement.motif))
        elif noeud is not None and _plausible(cotes, tolerances, entraxe):
            # SANS CALQUE NI BLOC, LA FORME ET LA POSITION: au nœud de la grille —
            # si ce n'est ni un pieu, ni un massif, ni le dessin d'un pieu, et
            # si la forme est celle d'une section.
            if role in ("pieu", "fondation"):
                raison: str | None = role
            elif rang in exclues:
                raison = "dessin_de_pieu"
            else:
                raison = controle.raison(rang, forme, cotes)
            if raison is not None:
                cle = (raison, tuple(round(v / pas) for v in boite_de(forme.points)))
                if cle not in rejets_vus:
                    rejets_vus.add(cle)
                    rejets[raison] += 1
                continue
            retenus.append((forme, rang, 0.65 if forme.rempli else 0.6, "forme", None))

    # UN POTEAU DESSINE DEUX FOIS (contour et hachure) N'EN FAIT QU'UN.
    groupes: list[list[tuple[Forme, int, float, str, str | None]]] = []
    tetes: list[tuple[Point, tuple[float, float]]] = []
    index_groupes = IndexSpatial(max(0.5 * (entraxe or 0.0), 10.0 * tolerances.longueur))
    for item in sorted(retenus, key=lambda x: (-x[2], x[1])):
        forme = item[0]
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

    poteaux: list[Poteau] = []
    utilises: set[int] = set()
    repere_x = grille.repere_x
    angle_x = angle_deg(repere_x)
    for groupe in groupes:
        forme, _, confiance, regle, motif = groupe[0]
        utilises.update(item[1] for item in groupe)
        preuve: Preuve = preuve_de([p for item in groupe for p in item[0].primitives],
                                   regle, motif)
        rempli = any(item[0].rempli for item in groupe)
        if forme.genre == "cercle" and forme.rayon is not None:
            centre = (sum(p[0] for p in forme.points) / len(forme.points),
                      sum(p[1] for p in forme.points) / len(forme.points))
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

    # DES IDENTIFIANTS STABLES: par nœud quand il y en a un, sinon par position.
    poteaux.sort(key=lambda p: (p.noeud is None, p.noeud or "", round(p.centre[1], 6),
                                round(p.centre[0], 6)))
    vus: dict[str, int] = {}
    nommes: list[Poteau] = []
    for rang, p in enumerate(poteaux, start=1):
        base = f"column:{p.noeud}" if p.noeud else f"column:{rang}"
        if base in vus:
            vus[base] += 1
            base = f"{base}#{vus[base]}"
        else:
            vus[base] = 1
        nommes.append(replace(p, id=base))
    return nommes, utilises, doutes, rejets
