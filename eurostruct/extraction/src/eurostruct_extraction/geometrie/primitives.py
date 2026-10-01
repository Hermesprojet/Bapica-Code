"""Les primitives d'un DXF : l'espace objet, blocs explosés, dans le repère du dessin.

LES RÈGLES DU DAO SONT APPLIQUÉES, PAS SUPPOSÉES
-------------------------------------------------
* un élément de bloc posé sur le calque ``0`` prend le calque de l'``INSERT``
  qui le place ; un type de ligne ``BYBLOCK`` prend celui de l'``INSERT``,
  ``BYLAYER`` celui du calque ;
* un calque éteint ou gelé n'est pas lu : le plan imprimé ne le montre pas ;
* un ``MINSERT`` (réseau de blocs) est déplié élément par élément.

CHAQUE PRIMITIVE SAIT D'OÙ ELLE VIENT. ``Source.poignee`` est la poignée de
l'entité d'origine — dans la définition du bloc si elle y est —, et
``Source.insertions`` la chaîne des ``INSERT`` qui l'ont placée. Un poteau
inséré cinquante fois se retrouve cinquante fois, chacun par son ``INSERT``.

CE QUI N'EST PAS LU EST COMPTÉ ET NOMMÉ. Une référence externe (XREF) n'est
pas dans le fichier : elle est citée, pas devinée. Solides 3D, régions ACIS,
entités proxy et images sont comptés dans ``ecartees``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Final

from .noyau import Point, boite_de, normale, unitaire

__all__ = [
    "PRIMITIVES_MAX",
    "PROFONDEUR_MAX",
    "Cercle",
    "Contour",
    "CoteDxf",
    "InfoCalque",
    "Insertion",
    "Primitive",
    "PrimitivesDxf",
    "Segment",
    "Source",
    "Texte",
    "lire_primitives",
]

#: Profondeur d'imbrication des blocs au-delà de laquelle on s'arrête.
PROFONDEUR_MAX: Final[int] = 8
#: Au-delà, la lecture s'arrête et le statut devient « partiel ».
PRIMITIVES_MAX: Final[int] = 200_000

#: Les entités qu'un plan de structure ne dessine pas en 2D, ou que ce lecteur
#: ne sait pas interpréter : comptées, jamais approchées.
_NON_LUES: Final[frozenset[str]] = frozenset({
    "3DSOLID", "BODY", "REGION", "SURFACE", "MESH", "ACAD_PROXY_ENTITY",
    "IMAGE", "WIPEOUT", "OLE2FRAME", "VIEWPORT", "3DFACE", "POLYFACE",
    "UNDERLAY", "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY",
})
#: Silencieuses : sans géométrie utile (un point de cote, une ligne de
#: construction infinie, un repère de vue).
_SANS_OBJET: Final[frozenset[str]] = frozenset({
    "POINT", "XLINE", "RAY", "ATTDEF", "SEQEND", "VERTEX", "LEADER", "TOLERANCE",
    "SHAPE",
})


@dataclass(frozen=True)
class Source:
    """La trace d'une primitive : quelle entité, placée par quels ``INSERT``."""

    poignee: str
    type: str
    insertions: tuple[str, ...] = ()
    blocs: tuple[str, ...] = ()

    @property
    def cle(self) -> tuple[str, tuple[str, ...]]:
        """Une entité placée par un chemin d'``INSERT`` : les traits et le
        contour d'une même polyligne fermée partagent cette clé."""
        return (self.poignee, self.insertions)


@dataclass(frozen=True)
class Primitive:
    calque: str
    type_ligne: str
    source: Source


@dataclass(frozen=True)
class Segment(Primitive):
    a: Point
    b: Point
    #: Morceau d'une courbe aplatie : jamais apparié comme face de poutre.
    courbe: bool = False

    @property
    def longueur(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])


@dataclass(frozen=True)
class Contour(Primitive):
    points: tuple[Point, ...]
    rempli: bool
    #: ``polyligne``, ``polyligne_epaisse``, ``solide``, ``hachure``, ``lignes``
    origine: str


@dataclass(frozen=True)
class Cercle(Primitive):
    centre: Point
    rayon: float


@dataclass(frozen=True)
class Arc(Primitive):
    centre: Point
    rayon: float
    debut_deg: float
    fin_deg: float


@dataclass(frozen=True)
class Texte(Primitive):
    texte: str
    ancrage: Point
    rotation: float
    hauteur: float
    #: Boîte réelle dans le repère du dessin (métrique des polices d'ezdxf).
    boite: tuple[float, float, float, float]

    @property
    def centre(self) -> Point:
        x0, y0, x1, y1 = self.boite
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


@dataclass(frozen=True)
class CoteDxf(Primitive):
    #: Origines des lignes d'attache (``defpoint2``, ``defpoint3``).
    p1: Point
    p2: Point
    #: Un point de la ligne de cote (``defpoint``).
    ligne: Point
    #: Direction de mesure (unitaire).
    direction: Point
    #: La mesure géométrique, en unités du dessin, AVANT ``DIMLFAC``.
    mesure: float
    #: ``DIMLFAC`` effectif (style + surcharges).
    facteur: float
    #: Le texte saisi : vide ou ``<>`` = la mesure ; sinon un texte forcé.
    texte: str
    #: ``lineaire`` (tournée), ``alignee``, ``autre`` (angulaire, rayon…).
    genre: str


@dataclass(frozen=True)
class Insertion(Primitive):
    nom_bloc: str
    point: Point
    rotation: float
    attributs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class InfoCalque:
    nom: str
    type_ligne: str
    eteint: bool
    gele: bool
    imprime: bool


@dataclass
class PrimitivesDxf:
    segments: list[Segment] = field(default_factory=list)
    contours: list[Contour] = field(default_factory=list)
    cercles: list[Cercle] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)
    textes: list[Texte] = field(default_factory=list)
    cotes: list[CoteDxf] = field(default_factory=list)
    insertions: list[Insertion] = field(default_factory=list)
    calques: dict[str, InfoCalque] = field(default_factory=dict)
    #: raison -> nombre d'entités non lues.
    ecartees: dict[str, int] = field(default_factory=dict)
    references_externes: list[str] = field(default_factory=list)
    tronquee: bool = False
    insunits: int | None = None
    unites: str | None = None
    #: Pour une feuille PDF : page, millimètres réels par point (``None`` si
    #: l'échelle n'est pas établie), dimensions de la page en points.
    cadre: dict[str, Any] | None = None
    #: Pour une feuille PDF : les deux sources de l'échelle (écrite, cotes).
    origine_unites: dict[str, Any] | None = None
    #: Ce que la lecture n'a pas pu établir : (élément, raison).
    remarques: list[tuple[str, str]] = field(default_factory=list)
    #: Les présentations d'un DXF (échelles écrites, fenêtres, papier), pour
    #: l'unité d'un dessin qui ne la déclare pas (``presentation.py``).
    presentations: list[Any] = field(default_factory=list)

    def nombre(self) -> int:
        return (len(self.segments) + len(self.contours) + len(self.cercles)
                + len(self.arcs) + len(self.textes) + len(self.cotes)
                + len(self.insertions))

    def emprise(self) -> tuple[float, float, float, float] | None:
        """L'emprise des TRAITS (sans les textes) : l'échelle du dessin."""
        points: list[Point] = []
        for s in self.segments:
            points.extend((s.a, s.b))
        for c in self.contours:
            points.extend(c.points)
        for c in self.cercles:
            points.extend(((c.centre[0] - c.rayon, c.centre[1] - c.rayon),
                           (c.centre[0] + c.rayon, c.centre[1] + c.rayon)))
        return boite_de(points) if points else None


# ---------------------------------------------------------------- lecture
def _xy(v: Any) -> Point:
    return (float(v[0]), float(v[1]))


def _poignee(entite: Any) -> str:
    """La poignée de l'entité d'origine : dans le bloc si c'est une copie."""
    origine = getattr(entite, "source_of_copy", None)
    if origine is not None:
        poignee = origine.dxf.get("handle", "") if hasattr(origine, "dxf") else ""
        if poignee:
            return str(poignee)
    return str(entite.dxf.get("handle", "") or "")


class _Lecteur:
    def __init__(self, document: Any) -> None:
        self.document = document
        self.p = PrimitivesDxf()
        for calque in document.layers:
            nom = str(calque.dxf.name)
            try:
                eteint, gele = bool(calque.is_off()), bool(calque.is_frozen())
            except Exception:  # noqa: BLE001 — une table mal formee n'arrete rien
                eteint = gele = False
            self.p.calques[nom.upper()] = InfoCalque(
                nom=nom, type_ligne=str(calque.dxf.get("linetype", "CONTINUOUS")).upper(),
                eteint=eteint, gele=gele, imprime=bool(calque.dxf.get("plot", 1)))

    # ---------------------------------------------------------- utilitaires
    def ecarter(self, raison: str, nombre: int = 1) -> None:
        self.p.ecartees[raison] = self.p.ecartees.get(raison, 0) + nombre

    def _plein(self) -> bool:
        if self.p.nombre() >= PRIMITIVES_MAX:
            self.p.tronquee = True
            return True
        return False

    def _calque_et_ligne(self, entite: Any, calque_parent: str | None,
                         ligne_parent: str | None) -> tuple[str, str] | None:
        calque = str(entite.dxf.get("layer", "0") or "0")
        if calque == "0" and calque_parent is not None:
            calque = calque_parent
        info = self.p.calques.get(calque.upper())
        if info is not None and (info.eteint or info.gele):
            self.ecarter(f"calque eteint ou gele: {info.nom}")
            return None
        ligne = str(entite.dxf.get("linetype", "BYLAYER") or "BYLAYER").upper()
        if ligne == "BYLAYER":
            ligne = info.type_ligne if info is not None else "CONTINUOUS"
        elif ligne == "BYBLOCK":
            ligne = ligne_parent or "CONTINUOUS"
        return calque, ligne

    # ------------------------------------------------------------- parcours
    def visiter(self, entite: Any, *, calque_parent: str | None = None,
                ligne_parent: str | None = None, insertions: tuple[str, ...] = (),
                blocs: tuple[str, ...] = (), profondeur: int = 0,
                poignee_parent: str = "") -> None:
        if self.p.tronquee or self._plein():
            return
        type_ = entite.dxftype()
        if type_ in _SANS_OBJET:
            return
        if type_ in _NON_LUES:
            self.ecarter(f"entite non lue: {type_}")
            return
        resolu = self._calque_et_ligne(entite, calque_parent, ligne_parent)
        if resolu is None:
            return
        calque, ligne = resolu
        # UNE COPIE SANS POIGNEE (le texte d'une ligne de rappel) est tracee par
        # l'entite qui l'a produite.
        source = Source(_poignee(entite) or poignee_parent, type_, insertions, blocs)
        try:
            self._lire(entite, type_, calque, ligne, source, insertions, blocs, profondeur)
        except Exception:  # noqa: BLE001 — une entite mal formee n'arrete pas le plan
            self.ecarter(f"entite illisible: {type_}")

    def _lire(self, entite: Any, type_: str, calque: str, ligne: str, source: Source,
              insertions: tuple[str, ...], blocs: tuple[str, ...], profondeur: int) -> None:
        if type_ == "LINE":
            a, b = _xy(entite.dxf.start), _xy(entite.dxf.end)
            if a != b:
                self.p.segments.append(Segment(calque, ligne, source, a, b))
        elif type_ == "LWPOLYLINE":
            sommets = [(float(x), float(y), float(bulge))
                       for x, y, bulge in entite.get_points("xyb")]
            self._polyligne(sommets, bool(entite.closed), calque, ligne, source,
                            epaisseur=float(entite.dxf.get("const_width", 0.0) or 0.0))
        elif type_ == "POLYLINE":
            if not (entite.is_2d_polyline or entite.is_3d_polyline):
                self.ecarter("entite non lue: POLYLINE maillage")
                return
            sommets = [(float(v.dxf.location.x), float(v.dxf.location.y),
                        float(v.dxf.get("bulge", 0.0) or 0.0)) for v in entite.vertices]
            self._polyligne(sommets, bool(entite.is_closed), calque, ligne, source,
                            epaisseur=float(entite.dxf.get("default_start_width", 0.0) or 0.0))
        elif type_ == "CIRCLE":
            self.p.cercles.append(Cercle(calque, ligne, source, _xy(entite.dxf.center),
                                         float(entite.dxf.radius)))
        elif type_ == "ARC":
            self.p.arcs.append(Arc(calque, ligne, source, _xy(entite.dxf.center),
                                   float(entite.dxf.radius), float(entite.dxf.start_angle),
                                   float(entite.dxf.end_angle)))
        elif type_ in ("ELLIPSE", "SPLINE"):
            self.ecarter(f"courbe non lue: {type_}")
        elif type_ in ("SOLID", "TRACE"):
            sommets = [_xy(entite.dxf.get(f"vtx{i}")) for i in (0, 1, 3, 2)]
            uniques: list[Point] = []
            for p in sommets:
                if p not in uniques:
                    uniques.append(p)
            if len(uniques) >= 3:
                self.p.contours.append(Contour(calque, ligne, source, tuple(uniques),
                                               True, "solide"))
        elif type_ in ("HATCH", "MPOLYGON"):
            self._hachure(entite, calque, ligne, source)
        elif type_ in ("TEXT", "ATTRIB"):
            self._texte_simple(entite, calque, ligne, source)
        elif type_ == "MTEXT":
            self._texte_multiligne(entite, calque, ligne, source)
        elif type_ == "MULTILEADER":
            # L'ETIQUETTE D'UNE LIGNE DE RAPPEL est un texte comme un autre ; ses
            # traits, eux, ne sont pas de la structure.
            for v in entite.virtual_entities():
                if v.dxftype() in ("MTEXT", "TEXT"):
                    self.visiter(v, calque_parent=calque, ligne_parent=ligne,
                                 insertions=insertions, blocs=blocs, profondeur=profondeur,
                                 poignee_parent=source.poignee)
        elif type_ == "DIMENSION":
            self._cote(entite, calque, ligne, source)
        elif type_ == "INSERT":
            self._insertion(entite, calque, ligne, source, insertions, blocs, profondeur)
        else:
            self.ecarter(f"entite non lue: {type_}")

    def _polyligne(self, sommets: list[tuple[float, float, float]], fermee: bool,
                   calque: str, ligne: str, source: Source, *, epaisseur: float) -> None:
        if len(sommets) < 2:
            return
        from ezdxf.math import bulge_to_arc

        points_contour: list[Point] = []
        n = len(sommets)
        aretes = n if fermee else n - 1
        for i in range(aretes):
            x0, y0, bulge = sommets[i]
            x1, y1, _ = sommets[(i + 1) % n]
            a, b = (x0, y0), (x1, y1)
            if a == b:
                continue
            points_contour.append(a)
            if abs(bulge) < 1e-12:
                self.p.segments.append(Segment(calque, ligne, source, a, b))
                if epaisseur > 0.0 and not fermee:
                    self._bande_epaisse(a, b, epaisseur, calque, ligne, source)
                continue
            # UN ARRONDI EST UN ARC, PAS UNE CORDE: aplati en petits segments
            # marques « courbe », que l'appariement des poutres ignore. Le sens
            # du parcours est fixe par la geometrie (le premier point est celui
            # qui touche `a`), pas par le signe du bulge.
            centre, debut, fin, rayon = bulge_to_arc(a, b, bulge)
            if fin < debut:
                fin += 2 * math.pi
            pas = max(4, int(math.ceil(math.degrees(fin - debut) / 10.0)))
            arc = [(float(centre[0]) + rayon * math.cos(debut + (fin - debut) * k / pas),
                    float(centre[1]) + rayon * math.sin(debut + (fin - debut) * k / pas))
                   for k in range(pas + 1)]
            if math.dist(arc[0], a) > math.dist(arc[0], b):
                arc.reverse()
            arc[0], arc[-1] = a, b
            for p, q in zip(arc, arc[1:], strict=False):
                self.p.segments.append(Segment(calque, ligne, source, p, q, courbe=True))
            points_contour.extend(arc[1:-1])
        if fermee and len(points_contour) >= 3:
            self.p.contours.append(Contour(calque, ligne, source, tuple(points_contour),
                                           False, "polyligne"))

    def _bande_epaisse(self, a: Point, b: Point, epaisseur: float, calque: str,
                       ligne: str, source: Source) -> None:
        """Une polyligne à largeur constante est dessinée comme une bande pleine."""
        u = unitaire(a, b)
        if u is None:
            return
        n = normale(u)
        h = epaisseur / 2.0
        coins = ((a[0] + n[0] * h, a[1] + n[1] * h), (b[0] + n[0] * h, b[1] + n[1] * h),
                 (b[0] - n[0] * h, b[1] - n[1] * h), (a[0] - n[0] * h, a[1] - n[1] * h))
        self.p.contours.append(Contour(calque, ligne, source, coins, True,
                                       "polyligne_epaisse"))

    def _hachure(self, entite: Any, calque: str, ligne: str, source: Source) -> None:
        from ezdxf import path as chemins

        for chemin in chemins.from_hatch(entite):
            controles = [_xy(v) for v in chemin.control_vertices()]
            if len(controles) < 3:
                continue
            x0, y0, x1, y1 = boite_de(controles)
            fleche = max(math.hypot(x1 - x0, y1 - y0) * 1e-3, 1e-9)
            points = [_xy(v) for v in chemin.flattening(fleche)]
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()
            if len(points) >= 3:
                self.p.contours.append(Contour(calque, ligne, source, tuple(points),
                                               True, "hachure"))

    def _boite_texte(self, entite: Any, ancrage: Point, hauteur: float,
                     rotation: float, longueur: int) -> tuple[float, float, float, float]:
        from ezdxf import bbox

        try:
            etendue = bbox.extents([entite], fast=True)
            if etendue.has_data:
                return (float(etendue.extmin.x), float(etendue.extmin.y),
                        float(etendue.extmax.x), float(etendue.extmax.y))
        except Exception:  # noqa: BLE001 — une police introuvable: estimation
            pass
        # ESTIMATION, DITE COMME TELLE: 0,7 hauteur par caractere.
        largeur = 0.7 * hauteur * max(longueur, 1)
        a = math.radians(rotation)
        coins = [(0.0, 0.0), (largeur, 0.0), (largeur, hauteur), (0.0, hauteur)]
        tournes = [(ancrage[0] + x * math.cos(a) - y * math.sin(a),
                    ancrage[1] + x * math.sin(a) + y * math.cos(a)) for x, y in coins]
        return boite_de(tournes)

    def _texte_simple(self, entite: Any, calque: str, ligne: str, source: Source) -> None:
        texte = str(entite.plain_text()).strip()
        if not texte:
            return
        alignement, p1, p2 = entite.get_placement()
        nom = getattr(alignement, "name", str(alignement))
        point = p2 if (p2 is not None and nom not in ("LEFT", "ALIGNED", "FIT")) else p1
        ancrage = _xy(point)
        hauteur = float(entite.dxf.get("height", 1.0) or 1.0)
        rotation = float(entite.dxf.get("rotation", 0.0) or 0.0)
        self.p.textes.append(Texte(calque, ligne, source, texte, ancrage, rotation, hauteur,
                                   self._boite_texte(entite, ancrage, hauteur, rotation,
                                                     len(texte))))

    def _texte_multiligne(self, entite: Any, calque: str, ligne: str, source: Source) -> None:
        texte = str(entite.plain_text(split=False)).strip()
        if not texte:
            return
        ancrage = _xy(entite.dxf.insert)
        hauteur = float(entite.dxf.get("char_height", 1.0) or 1.0)
        rotation = float(entite.get_rotation())
        plus_longue = max((len(x) for x in texte.splitlines()), default=1)
        self.p.textes.append(Texte(calque, ligne, source, texte, ancrage, rotation, hauteur,
                                   self._boite_texte(entite, ancrage, hauteur, rotation,
                                                     plus_longue)))

    def _cote(self, entite: Any, calque: str, ligne: str, source: Source) -> None:
        genre_dxf = int(entite.dimtype) & 7
        p1, p2 = _xy(entite.dxf.defpoint2), _xy(entite.dxf.defpoint3)
        point_ligne = _xy(entite.dxf.defpoint)
        if genre_dxf == 0:
            angle = math.radians(float(entite.dxf.get("angle", 0.0) or 0.0))
            direction: Point | None = (math.cos(angle), math.sin(angle))
            genre = "lineaire"
        elif genre_dxf == 1:
            direction = unitaire(p1, p2)
            genre = "alignee"
        else:
            direction, genre = None, "autre"
        try:
            mesure_brute = entite.get_measurement()
            mesure = float(mesure_brute) if not hasattr(mesure_brute, "x") else math.nan
        except Exception:  # noqa: BLE001 — une cote illisible n'arrete rien
            mesure = math.nan
        try:
            facteur = float(entite.override().get("dimlfac", 1.0) or 1.0)
        except Exception:  # noqa: BLE001
            facteur = 1.0
        if direction is None:
            direction, genre = (1.0, 0.0), "autre"
        self.p.cotes.append(CoteDxf(calque, ligne, source, p1, p2, point_ligne, direction,
                                    mesure, facteur, str(entite.dxf.get("text", "") or ""),
                                    genre))

    def _insertion(self, entite: Any, calque: str, ligne: str, source: Source,
                   insertions: tuple[str, ...], blocs: tuple[str, ...],
                   profondeur: int) -> None:
        nom = str(entite.dxf.name)
        definition = self.document.blocks.get(nom)
        if definition is None:
            self.ecarter("bloc introuvable")
            return
        entete = definition.block
        if getattr(entete, "is_xref", False) or getattr(entete, "is_xref_overlay", False):
            # UNE REFERENCE EXTERNE N'EST PAS DANS CE FICHIER: la nommer, ne
            # rien supposer de ce qu'elle contient.
            self.p.references_externes.append(nom)
            return
        if profondeur >= PROFONDEUR_MAX:
            self.ecarter("blocs imbriques au-dela de la profondeur lue")
            return
        poignee = source.poignee
        attributs = tuple((str(a.dxf.tag), str(a.dxf.text)) for a in entite.attribs)
        self.p.insertions.append(Insertion(
            calque, ligne, source, nom, _xy(entite.dxf.insert),
            float(entite.dxf.get("rotation", 0.0) or 0.0), attributs))
        chaine, noms = insertions + (poignee,), blocs + (nom,)
        for attribut in entite.attribs:
            self.visiter(attribut, calque_parent=calque, ligne_parent=ligne,
                         insertions=chaine, blocs=noms, profondeur=profondeur + 1)
        rangees = int(entite.dxf.get("row_count", 1) or 1)
        colonnes = int(entite.dxf.get("column_count", 1) or 1)
        if rangees * colonnes > 1:
            for unique in entite.multi_insert():
                self._contenu(unique, calque, ligne, chaine, noms, profondeur)
            return
        self._contenu(entite, calque, ligne, chaine, noms, profondeur)

    def _contenu(self, entite: Any, calque: str, ligne: str, chaine: tuple[str, ...],
                 noms: tuple[str, ...], profondeur: int) -> None:
        try:
            virtuelles: Iterable[Any] = list(entite.virtual_entities())
        except Exception:  # noqa: BLE001 — une echelle non uniforme mal geree
            self.ecarter("bloc non explose (transformation non prise en charge)")
            return
        for virtuelle in virtuelles:
            if virtuelle.dxftype() == "ATTDEF":
                continue
            self.visiter(virtuelle, calque_parent=calque, ligne_parent=ligne,
                         insertions=chaine, blocs=noms, profondeur=profondeur + 1)


def lire_primitives(document: Any, *, insunits: int | None = None,
                    unites: str | None = None) -> PrimitivesDxf:
    """Toutes les primitives de l'espace objet d'un document ezdxf ouvert."""
    lecteur = _Lecteur(document)
    lecteur.p.insunits = insunits
    lecteur.p.unites = unites
    for entite in document.modelspace():
        if lecteur.p.tronquee:
            break
        lecteur.visiter(entite)
    from .presentation import lire_presentations

    try:
        lecteur.p.presentations = lire_presentations(document)
    except Exception:  # noqa: BLE001 — une présentation illisible ne dit rien
        lecteur.ecarter("presentation illisible")
    return lecteur.p
