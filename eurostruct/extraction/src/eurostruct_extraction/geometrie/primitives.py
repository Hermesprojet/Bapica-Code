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

L'INFORMATION DXF STANDARD (N1) EST LUE, PAS ENCORE INTERPRÉTÉE
-----------------------------------------------------------------
Motif de chaque type de ligne (``types_de_ligne``), remplissage plein ou à
motif des hachures, multilignes (``multilignes``), définitions de blocs et
comptes d'insertions (``definitions``), échelle des insertions, calques
dépendant d'une référence externe, couleur résolue de chaque primitive :
la phase G1 de ``docs/GEOMETRIE_D_ABORD.md``, détaillée dans
``docs/GEOMETRIE_D_ABORD_G1.md``. AUCUN DÉTECTEUR NE LES LIT ENCORE : ils
servent les détections « géométrie d'abord » (G2 à G6). D'ici là, aucune
sortie ne change — les champs nouveaux d'une primitive sont hors égalité
(``compare=False``), une multiligne reste comptée « entité non lue », les
bornes ne les comptent pas, et une information N1 illisible vaut ``None``
(l'incident est compté dans ``n1_incidents``) sans jamais rendre une
entité illisible.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from .noyau import Point, boite_de, normale, unitaire

__all__ = [
    "PRIMITIVES_MAX",
    "PROFONDEUR_MAX",
    "Cercle",
    "ClasseDeMotif",
    "Contour",
    "CoteDxf",
    "DefinitionDeBloc",
    "InfoCalque",
    "Insertion",
    "MotifDeLigne",
    "Multiligne",
    "Primitive",
    "PrimitivesDxf",
    "Segment",
    "Source",
    "Texte",
    "classe_de_motif",
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

#: LA CLASSE D'UN MOTIF DE TYPE DE LIGNE (N1), lue sur ses éléments (code 49),
#: jamais sur son nom : un trait est PONCTUEL s'il est nul ou au plus 0,2 fois
#: le plus long blanc (« . » de ``DOT``, ``ACAD_ISO07W100``) ; parmi les autres,
#: un trait est COURT s'il mesure moins de la moitié du plus long (« - » de
#: ``CENTER``). Voir ``docs/GEOMETRIE_D_ABORD_G1.md`` (F1).
PONCTUEL: Final[float] = 0.2
COURT: Final[float] = 0.5
ClasseDeMotif = Literal["continu", "tirets", "mixte", "points"]
#: Justification d'une multiligne (code 70).
_JUSTIFICATIONS: Final[dict[int, str]] = {0: "haut", 1: "zero", 2: "bas"}
#: Drapeaux DXF (code 70) : bloc anonyme, référence externe, superposée ;
#: calque dépendant d'une référence externe.
_BLOC_ANONYME: Final[int] = 1
_CALQUE_DEPEND_XREF: Final[int] = 16
#: Le style de multiligne remplit l'espace entre ses éléments (code 70).
_STYLE_REMPLI: Final[int] = 1


def classe_de_motif(elements: Sequence[float]) -> ClasseDeMotif:
    """``continu``, ``tirets``, ``mixte`` (trait-point, ISO 128) ou ``points``.

    Un motif sans élément, ou sans blanc, ne découpe pas le trait : continu
    (un motif dégénéré, sans aucun trait, l'est aussi)."""
    blancs = [-e for e in elements if e < 0]
    traits = [e for e in elements if e >= 0]
    if not blancs or not traits:
        return "continu"
    seuil = PONCTUEL * max(blancs)
    ponctuels = [e for e in traits if e <= seuil]
    longs = [e for e in traits if e > seuil]
    if not longs:
        return "points"
    plus_long = max(longs)
    if ponctuels or any(e < COURT * plus_long for e in longs):
        return "mixte"
    return "tirets"


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
    #: N1 — la couleur RÉSOLUE (``aci:N`` ou ``rvb:#RRGGBB``) : ``BYLAYER`` par
    #: le calque effectif, ``BYBLOCK`` par l'``INSERT``. Une clé de regroupement
    #: (partitions apprises, G6), jamais un sens ; hors égalité.
    couleur: str | None = field(default=None, kw_only=True, compare=False)


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
    #: N1 — ``plein`` (hachure pleine, ``SOLID``, ``TRACE``), ``motif`` (hachure
    #: à motif), ``None`` ailleurs : le « coupé » des poteaux et des voiles (G4,
    #: G5). Le nom du motif (code 2) est cité, jamais un critère. Hors égalité.
    remplissage: Literal["plein", "motif"] | None = field(default=None, kw_only=True,
                                                          compare=False)
    motif_hachure: str | None = field(default=None, kw_only=True, compare=False)


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
    #: Pour la copie d'une cote de bloc : la mesure placée sur la mesure dans
    #: le bloc (l'échelle de l'insertion, 1 hors bloc). Le texte d'une cote de
    #: bloc est sa mesure DANS LE BLOC × ``DIMLFAC`` : l'insertion ne le change pas.
    echelle: float = 1.0


@dataclass(frozen=True)
class Insertion(Primitive):
    nom_bloc: str
    point: Point
    rotation: float
    attributs: tuple[tuple[str, str], ...]
    #: N1 — échelle (x, y) de l'insertion (codes 41, 42) ; composée pour une
    #: copie imbriquée. « Même définition à l'échelle 1 » des sections répétées
    #: (G4). Hors égalité.
    echelle: tuple[float, float] | None = field(default=(1.0, 1.0), kw_only=True,
                                                compare=False)


@dataclass(frozen=True)
class Multiligne(Primitive):
    """N1 — une ``MLINE`` : le voile explicite de G5. Aucun détecteur ne la lit
    encore, et elle reste comptée « entité non lue » dans ``ecartees``."""

    sommets: tuple[Point, ...]
    ferme: bool
    #: ``haut``, ``zero``, ``bas`` (code 70).
    justification: str
    #: Facteur d'échelle EFFECTIF (code 40, corrigé pour une copie de bloc) ;
    #: ``None`` si l'insertion n'est pas à échelle uniforme.
    echelle: float | None
    #: Décalage de chaque élément du style par rapport à la ligne des sommets,
    #: en unités du dessin (justification et échelle appliquées).
    decalages: tuple[float, ...] | None
    #: Le tracé de chaque élément : sommet + onglet × premier paramètre.
    elements: tuple[tuple[Point, ...], ...] | None
    #: Le style remplit l'espace entre ses éléments.
    remplie: bool | None

    @property
    def epaisseur(self) -> float | None:
        """L'écart entre les éléments extrêmes : l'épaisseur d'un voile."""
        if not self.decalages:
            return None
        return max(self.decalages) - min(self.decalages)


@dataclass(frozen=True)
class MotifDeLigne:
    """N1 — le motif d'un type de ligne (table ``LTYPE``), lu sans son nom."""

    nom: str
    #: Longueurs signées (code 49) : > 0 trait, < 0 blanc, 0 point.
    elements: tuple[float, ...]
    #: Longueur totale du motif (code 40).
    longueur: float
    #: Un élément porte un texte ou une forme (code 74 ≠ 0).
    complexe: bool
    classe: ClasseDeMotif


@dataclass
class DefinitionDeBloc:
    """N1 — une définition de bloc placée par au moins un ``INSERT`` lu."""

    nom: str
    #: Drapeaux du ``BLOCK`` (code 70) : anonyme, référence externe, superposée.
    anonyme: bool
    xref: bool
    superposee: bool
    #: Nombre d'entités de chaque type DANS la définition (premier niveau).
    types: dict[str, int]
    #: Nombre d'``ATTDEF`` : une bulle-bloc en a un (G2).
    attributs: int
    #: Polylignes fermées de la définition.
    fermes: int
    #: ``INSERT`` lus qui la placent (référence externe et profondeur dépassée
    #: comprises) ; copies dont le contenu a été lu (lignes × colonnes d'un
    #: ``MINSERT``).
    insertions: int = 0
    copies: int = 0


@dataclass(frozen=True)
class InfoCalque:
    nom: str
    type_ligne: str
    eteint: bool
    gele: bool
    imprime: bool
    #: N1 — couleur du calque (résolution ``BYLAYER``) ; calque apporté par une
    #: référence externe non liée (code 70, bit 16). Hors égalité.
    couleur: str | None = field(default=None, kw_only=True, compare=False)
    depend_xref: bool = field(default=False, kw_only=True, compare=False)


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
    #: N1 (``docs/GEOMETRIE_D_ABORD_G1.md``) — lus, pas encore interprétés.
    #: Motif de chaque type de ligne de la table, par nom en MAJUSCULES.
    types_de_ligne: dict[str, MotifDeLigne] = field(default_factory=dict)
    multilignes: list[Multiligne] = field(default_factory=list)
    #: Les définitions placées par un ``INSERT`` lu, par nom.
    definitions: dict[str, DefinitionDeBloc] = field(default_factory=dict)
    #: raison -> nombre : une information N1 illisible (laissée à ``None``).
    n1_incidents: dict[str, int] = field(default_factory=dict)

    def nombre(self) -> int:
        # LES LISTES N1 NE COMPTENT PAS : la borne et ``tronquee`` restent ceux
        # d'avant G1 (les multilignes ont leur propre borne).
        return (len(self.segments) + len(self.contours) + len(self.cercles)
                + len(self.arcs) + len(self.textes) + len(self.cotes)
                + len(self.insertions))

    def motif_de(self, type_ligne: str) -> MotifDeLigne | None:
        """Le motif d'un type de ligne EFFECTIF (celui d'une primitive)."""
        return self.types_de_ligne.get(type_ligne.upper())

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


def _code_couleur(aci: int | None, rvb: Any) -> str | None:
    """``rvb:#RRGGBB`` (couleur vraie, code 420) ou ``aci:N`` (code 62)."""
    if rvb is not None:
        r, g, b = (int(c) for c in rvb)
        return f"rvb:#{r:02X}{g:02X}{b:02X}"
    if aci is None:
        return None
    return f"aci:{abs(int(aci))}"


def _motifs_de_ligne(document: Any, incident: Any) -> dict[str, MotifDeLigne]:
    """N1 — le motif de chaque type de ligne de la table ``LTYPE``."""
    motifs: dict[str, MotifDeLigne] = {}
    try:
        table = list(document.linetypes)
    except Exception:  # noqa: BLE001 — une table illisible ne dit rien
        incident("table des types de ligne illisible")
        return motifs
    for type_ in table:
        try:
            nom = str(type_.dxf.name)
            elements: list[float] = []
            complexe, longueur = False, 0.0
            for etiquette in type_.pattern_tags.tags:
                if etiquette.code == 49:
                    elements.append(float(etiquette.value))
                elif etiquette.code == 74 and int(etiquette.value) != 0:
                    complexe = True
                elif etiquette.code == 40:
                    longueur = float(etiquette.value)
            motifs[nom.upper()] = MotifDeLigne(nom, tuple(elements), longueur, complexe,
                                               classe_de_motif(elements))
        except Exception:  # noqa: BLE001
            incident("type de ligne illisible")
    return motifs


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
            # N1, LU A PART : un calque dont la couleur est illisible garde son
            # état éteint ou gelé, lu comme avant.
            try:
                couleur = _code_couleur(calque.dxf.get("color", 7), calque.rgb)
                depend_xref = bool(int(calque.dxf.get("flags", 0) or 0) & _CALQUE_DEPEND_XREF)
            except Exception:  # noqa: BLE001
                self.incident("couleur ou drapeaux de calque illisibles")
                couleur, depend_xref = None, False
            self.p.calques[nom.upper()] = InfoCalque(
                nom=nom, type_ligne=str(calque.dxf.get("linetype", "CONTINUOUS")).upper(),
                eteint=eteint, gele=gele, imprime=bool(calque.dxf.get("plot", 1)),
                couleur=couleur, depend_xref=depend_xref)
        self.p.types_de_ligne = _motifs_de_ligne(document, self.incident)

    # ---------------------------------------------------------- utilitaires
    def ecarter(self, raison: str, nombre: int = 1) -> None:
        self.p.ecartees[raison] = self.p.ecartees.get(raison, 0) + nombre

    def incident(self, raison: str) -> None:
        """N1 illisible : compté à part, jamais dans ``ecartees`` (sorties inchangées)."""
        self.p.n1_incidents[raison] = self.p.n1_incidents.get(raison, 0) + 1

    def _couleur(self, entite: Any, calque: str, couleur_parent: str | None,
                 dans_un_bloc: bool) -> str | None:
        """N1 — la couleur résolue, par les règles du DAO (``BYLAYER`` : calque
        EFFECTIF ; ``BYBLOCK`` : l'``INSERT`` ; hors bloc, ``BYBLOCK`` est
        dessiné en couleur 7, comme son type de ligne l'est en continu)."""
        try:
            rvb = entite.rgb
            if rvb is not None:
                return _code_couleur(None, rvb)
            aci = int(entite.dxf.get("color", 256))
            if aci == 256:
                # UN CALQUE ABSENT DE LA TABLE est créé à la lecture avec ses
                # valeurs par défaut (couleur 7) — comme son type de ligne est
                # déjà lu CONTINUOUS.
                info = self.p.calques.get(calque.upper())
                return info.couleur if info is not None else "aci:7"
            if aci == 0:
                return couleur_parent if dans_un_bloc else "aci:7"
            return _code_couleur(aci, None)
        except Exception:  # noqa: BLE001
            self.incident("couleur illisible")
            return None

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
                poignee_parent: str = "", couleur_parent: str | None = None,
                echelle_insertion: float | None = 1.0) -> None:
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
        couleur = self._couleur(entite, calque, couleur_parent, bool(insertions))
        try:
            self._lire(entite, type_, calque, ligne, source, insertions, blocs, profondeur,
                       couleur, echelle_insertion)
        except Exception:  # noqa: BLE001 — une entite mal formee n'arrete pas le plan
            self.ecarter(f"entite illisible: {type_}")

    def _lire(self, entite: Any, type_: str, calque: str, ligne: str, source: Source,
              insertions: tuple[str, ...], blocs: tuple[str, ...], profondeur: int,
              couleur: str | None, echelle_insertion: float | None) -> None:
        if type_ == "LINE":
            a, b = _xy(entite.dxf.start), _xy(entite.dxf.end)
            if a != b:
                self.p.segments.append(Segment(calque, ligne, source, a, b, couleur=couleur))
        elif type_ == "LWPOLYLINE":
            sommets = [(float(x), float(y), float(bulge))
                       for x, y, bulge in entite.get_points("xyb")]
            self._polyligne(sommets, bool(entite.closed), calque, ligne, source,
                            epaisseur=float(entite.dxf.get("const_width", 0.0) or 0.0),
                            couleur=couleur)
        elif type_ == "POLYLINE":
            if not (entite.is_2d_polyline or entite.is_3d_polyline):
                self.ecarter("entite non lue: POLYLINE maillage")
                return
            sommets = [(float(v.dxf.location.x), float(v.dxf.location.y),
                        float(v.dxf.get("bulge", 0.0) or 0.0)) for v in entite.vertices]
            self._polyligne(sommets, bool(entite.is_closed), calque, ligne, source,
                            epaisseur=float(entite.dxf.get("default_start_width", 0.0) or 0.0),
                            couleur=couleur)
        elif type_ == "CIRCLE":
            self.p.cercles.append(Cercle(calque, ligne, source, _xy(entite.dxf.center),
                                         float(entite.dxf.radius), couleur=couleur))
        elif type_ == "ARC":
            self.p.arcs.append(Arc(calque, ligne, source, _xy(entite.dxf.center),
                                   float(entite.dxf.radius), float(entite.dxf.start_angle),
                                   float(entite.dxf.end_angle), couleur=couleur))
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
                                               True, "solide", couleur=couleur,
                                               remplissage="plein"))
        elif type_ in ("HATCH", "MPOLYGON"):
            self._hachure(entite, calque, ligne, source, couleur)
        elif type_ in ("TEXT", "ATTRIB"):
            self._texte_simple(entite, calque, ligne, source, couleur)
        elif type_ == "MTEXT":
            self._texte_multiligne(entite, calque, ligne, source, couleur)
        elif type_ == "MULTILEADER":
            # L'ETIQUETTE D'UNE LIGNE DE RAPPEL est un texte comme un autre ; ses
            # traits, eux, ne sont pas de la structure.
            for v in entite.virtual_entities():
                if v.dxftype() in ("MTEXT", "TEXT"):
                    self.visiter(v, calque_parent=calque, ligne_parent=ligne,
                                 insertions=insertions, blocs=blocs, profondeur=profondeur,
                                 poignee_parent=source.poignee, couleur_parent=couleur,
                                 echelle_insertion=echelle_insertion)
        elif type_ == "DIMENSION":
            self._cote(entite, calque, ligne, source, couleur)
        elif type_ == "INSERT":
            self._insertion(entite, calque, ligne, source, insertions, blocs, profondeur,
                            couleur)
        elif type_ == "MLINE":
            # COMPTÉE NON LUE COMME AVANT G1 — aucun détecteur ne l'interprète
            # avant G5 — et LUE QUAND MÊME : sa géométrie est l'information N1
            # d'un voile. La lecture N1 ne lève jamais (ecartees inchangé).
            self.ecarter(f"entite non lue: {type_}")
            self._multiligne(entite, calque, ligne, source, couleur, echelle_insertion)
        else:
            self.ecarter(f"entite non lue: {type_}")

    def _polyligne(self, sommets: list[tuple[float, float, float]], fermee: bool,
                   calque: str, ligne: str, source: Source, *, epaisseur: float,
                   couleur: str | None) -> None:
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
                self.p.segments.append(Segment(calque, ligne, source, a, b, couleur=couleur))
                if epaisseur > 0.0 and not fermee:
                    self._bande_epaisse(a, b, epaisseur, calque, ligne, source, couleur)
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
                self.p.segments.append(Segment(calque, ligne, source, p, q, courbe=True,
                                               couleur=couleur))
            points_contour.extend(arc[1:-1])
        if fermee and len(points_contour) >= 3:
            self.p.contours.append(Contour(calque, ligne, source, tuple(points_contour),
                                           False, "polyligne", couleur=couleur))

    def _bande_epaisse(self, a: Point, b: Point, epaisseur: float, calque: str,
                       ligne: str, source: Source, couleur: str | None) -> None:
        """Une polyligne à largeur constante est dessinée comme une bande pleine."""
        u = unitaire(a, b)
        if u is None:
            return
        n = normale(u)
        h = epaisseur / 2.0
        coins = ((a[0] + n[0] * h, a[1] + n[1] * h), (b[0] + n[0] * h, b[1] + n[1] * h),
                 (b[0] - n[0] * h, b[1] - n[1] * h), (a[0] - n[0] * h, a[1] - n[1] * h))
        self.p.contours.append(Contour(calque, ligne, source, coins, True,
                                       "polyligne_epaisse", couleur=couleur))

    def _hachure(self, entite: Any, calque: str, ligne: str, source: Source,
                 couleur: str | None) -> None:
        from ezdxf import path as chemins

        # N1 : PLEINE (drapeau, code 70 ; 71 d'une MPOLYGON), À MOTIF (lignes de
        # motif, codes 53 et suivants), ou rien de tracé (une MPOLYGON sans
        # l'un ni l'autre) ; le nom du motif cité (code 2). Lu à part : une
        # information illisible laisse ``None``, la hachure reste lue.
        remplissage: Literal["plein", "motif"] | None
        try:
            if int(entite.dxf.get("solid_fill", 0) or 0):
                remplissage = "plein"
            elif entite.pattern is not None and len(entite.pattern.lines) > 0:
                remplissage = "motif"
            else:
                remplissage = None
            motif = str(entite.dxf.get("pattern_name", "") or "") or None
        except Exception:  # noqa: BLE001
            self.incident("remplissage de hachure illisible")
            remplissage, motif = None, None
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
                                               True, "hachure", couleur=couleur,
                                               remplissage=remplissage, motif_hachure=motif))

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

    def _texte_simple(self, entite: Any, calque: str, ligne: str, source: Source,
                      couleur: str | None) -> None:
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
                                                     len(texte)), couleur=couleur))

    def _texte_multiligne(self, entite: Any, calque: str, ligne: str, source: Source,
                          couleur: str | None) -> None:
        texte = str(entite.plain_text(split=False)).strip()
        if not texte:
            return
        ancrage = _xy(entite.dxf.insert)
        hauteur = float(entite.dxf.get("char_height", 1.0) or 1.0)
        rotation = float(entite.get_rotation())
        plus_longue = max((len(x) for x in texte.splitlines()), default=1)
        self.p.textes.append(Texte(calque, ligne, source, texte, ancrage, rotation, hauteur,
                                   self._boite_texte(entite, ancrage, hauteur, rotation,
                                                     plus_longue), couleur=couleur))

    def _cote(self, entite: Any, calque: str, ligne: str, source: Source,
              couleur: str | None) -> None:
        from ..lecteurs.dxf_cotes import mesure_de_cote

        # LA MESURE PAR TYPE, la même que celle des propositions : une cote
        # alignée mesure la distance de ses deux points (docs/GEOMETRIE_COTES_DXF.md).
        mesuree = mesure_de_cote(entite)
        p1, p2 = _xy(entite.dxf.defpoint2), _xy(entite.dxf.defpoint3)
        point_ligne = _xy(entite.dxf.defpoint)
        if mesuree.nature == "lineaire":
            angle = math.radians(float(entite.dxf.get("angle", 0.0) or 0.0))
            direction: Point | None = (math.cos(angle), math.sin(angle))
            genre = "lineaire"
        elif mesuree.nature == "alignee":
            direction = unitaire(p1, p2)
            genre = "alignee"
        else:
            direction, genre = None, "autre"
        mesure = mesuree.valeur if mesuree.valeur is not None else math.nan
        try:
            facteur = float(entite.override().get("dimlfac", 1.0) or 1.0)
        except Exception:  # noqa: BLE001
            facteur = 1.0
        if direction is None:
            direction, genre = (1.0, 0.0), "autre"
        # UNE COTE DE BLOC AFFICHE SA MESURE DANS LE BLOC : la copie placée par
        # une insertion mise à l'échelle mesure autrement que ce qu'elle affiche.
        echelle = 1.0
        origine = getattr(entite, "source_of_copy", None)
        if origine is not None and genre != "autre" and mesure > 0.0:
            dans_le_bloc = mesure_de_cote(origine).valeur
            if dans_le_bloc is not None and dans_le_bloc > 0.0:
                rapport = mesure / dans_le_bloc
                echelle = 1.0 if abs(rapport - 1.0) <= 1e-9 else rapport
        self.p.cotes.append(CoteDxf(calque, ligne, source, p1, p2, point_ligne, direction,
                                    mesure, facteur, str(entite.dxf.get("text", "") or ""),
                                    genre, echelle, couleur=couleur))

    def _insertion(self, entite: Any, calque: str, ligne: str, source: Source,
                   insertions: tuple[str, ...], blocs: tuple[str, ...],
                   profondeur: int, couleur: str | None) -> None:
        nom = str(entite.dxf.name)
        definition = self.document.blocks.get(nom)
        if definition is None:
            self.ecarter("bloc introuvable")
            return
        fiche = self._definition(nom, definition)
        fiche.insertions += 1
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
            float(entite.dxf.get("rotation", 0.0) or 0.0), attributs, couleur=couleur,
            echelle=self._echelle(entite)))
        chaine, noms = insertions + (poignee,), blocs + (nom,)
        for attribut in entite.attribs:
            self.visiter(attribut, calque_parent=calque, ligne_parent=ligne,
                         insertions=chaine, blocs=noms, profondeur=profondeur + 1,
                         couleur_parent=couleur)
        rangees = int(entite.dxf.get("row_count", 1) or 1)
        colonnes = int(entite.dxf.get("column_count", 1) or 1)
        if rangees * colonnes > 1:
            fiche.copies += rangees * colonnes
            for unique in entite.multi_insert():
                self._contenu(unique, calque, ligne, chaine, noms, profondeur, couleur)
            return
        fiche.copies += 1
        self._contenu(entite, calque, ligne, chaine, noms, profondeur, couleur)

    def _contenu(self, entite: Any, calque: str, ligne: str, chaine: tuple[str, ...],
                 noms: tuple[str, ...], profondeur: int, couleur: str | None) -> None:
        try:
            virtuelles: Iterable[Any] = list(entite.virtual_entities())
        except Exception:  # noqa: BLE001 — une echelle non uniforme mal geree
            self.ecarter("bloc non explose (transformation non prise en charge)")
            return
        echelle = self._echelle_uniforme(entite)
        for virtuelle in virtuelles:
            if virtuelle.dxftype() == "ATTDEF":
                continue
            self.visiter(virtuelle, calque_parent=calque, ligne_parent=ligne,
                         insertions=chaine, blocs=noms, profondeur=profondeur + 1,
                         couleur_parent=couleur, echelle_insertion=echelle)

    # ------------------------------------------------------------------ N1
    def _echelle(self, entite: Any) -> tuple[float, float] | None:
        """N1 — l'échelle (x, y) d'un ``INSERT`` (1 par défaut, selon le DXF)."""
        try:
            return (float(entite.dxf.get("xscale", 1.0)), float(entite.dxf.get("yscale", 1.0)))
        except Exception:  # noqa: BLE001
            self.incident("echelle d'insertion illisible")
            return None

    def _echelle_uniforme(self, entite: Any) -> float | None:
        """L'échelle d'un ``INSERT`` dans le plan du dessin si elle est la même
        en x et en y (au signe près, un miroir reste uniforme) ; sinon ``None``."""
        echelle = self._echelle(entite)
        if echelle is None:
            return None
        x, y = abs(echelle[0]), abs(echelle[1])
        if x == 0.0 or abs(x - y) > 1e-9 * max(x, y):
            return None
        return x

    def _definition(self, nom: str, definition: Any) -> DefinitionDeBloc:
        """N1 — la fiche d'une définition, lue une fois : drapeaux, contenu."""
        fiche = self.p.definitions.get(nom)
        if fiche is not None:
            return fiche
        anonyme = xref = superposee = False
        types: dict[str, int] = {}
        attributs = fermes = 0
        try:
            entete = definition.block
            anonyme = bool(int(entete.dxf.get("flags", 0) or 0) & _BLOC_ANONYME)
            xref = bool(getattr(entete, "is_xref", False))
            superposee = bool(getattr(entete, "is_xref_overlay", False))
            for membre in definition:
                genre = membre.dxftype()
                types[genre] = types.get(genre, 0) + 1
                if genre == "ATTDEF":
                    attributs += 1
                elif ((genre == "LWPOLYLINE" and membre.closed)
                      or (genre == "POLYLINE" and membre.is_closed)):
                    fermes += 1
        except Exception:  # noqa: BLE001
            self.incident("definition de bloc illisible")
        fiche = DefinitionDeBloc(nom, anonyme, xref, superposee, types, attributs, fermes)
        self.p.definitions[nom] = fiche
        return fiche

    def _multiligne(self, entite: Any, calque: str, ligne: str, source: Source,
                    couleur: str | None, echelle_insertion: float | None) -> None:
        """N1 — une ``MLINE``, lue telle que le DXF la porte. Ne lève jamais.

        UNE COPIE DE BLOC : ezdxf transforme ses sommets, mais ne met pas son
        facteur d'échelle à l'échelle de l'insertion quand celle-ci est tournée.
        Échelle effective = échelle d'origine × échelle (uniforme) de
        l'insertion ; décalages et tracés sont ramenés à cette échelle. Une
        insertion non uniforme ne dit pas l'épaisseur : ``None``."""
        if len(self.p.multilignes) >= PRIMITIVES_MAX:
            self.incident("multilignes au-dela de la borne")
            return
        try:
            sommets = tuple(_xy(v.location) for v in entite.vertices)
            if not sommets:
                self.incident("multiligne sans sommet")
                return
            ferme = bool(entite.is_closed)
            justification = _JUSTIFICATIONS.get(int(entite.dxf.get("justification", 0) or 0),
                                                "haut")
            lue = float(entite.dxf.get("scale_factor", 1.0))
            origine = getattr(entite, "source_of_copy", None)
            correction: float | None = 1.0
            if origine is not None and origine.dxftype() == "MLINE":
                attendue = (float(origine.dxf.get("scale_factor", 1.0)) * echelle_insertion
                            if echelle_insertion is not None else None)
                correction = attendue / lue if (attendue is not None and lue) else None
            style = entite.style
            remplie = (bool(int(style.dxf.get("flags", 0) or 0) & _STYLE_REMPLI)
                       if style is not None else None)
            echelle = lue * correction if correction is not None else None
            decalages: tuple[float, ...] | None = None
            elements: tuple[tuple[Point, ...], ...] | None = None
            if correction is not None:
                decalages_style = ([float(e.offset) for e in style.elements]
                                   if style is not None else [])
                if decalages_style and echelle is not None:
                    reference = (max(decalages_style) if justification == "haut"
                                 else min(decalages_style) if justification == "bas" else 0.0)
                    decalages = tuple((d - reference) * echelle for d in decalages_style)
                parametres = [v.line_params for v in entite.vertices]
                nombre = len(parametres[0])
                if nombre and all(len(p) == nombre and all(p) for p in parametres):
                    elements = tuple(
                        tuple((float(v.location.x) + float(v.miter_direction.x)
                               * float(v.line_params[i][0]) * correction,
                               float(v.location.y) + float(v.miter_direction.y)
                               * float(v.line_params[i][0]) * correction)
                              for v in entite.vertices)
                        for i in range(nombre))
            self.p.multilignes.append(Multiligne(
                calque, ligne, source, sommets, ferme, justification, echelle, decalages,
                elements, remplie, couleur=couleur))
        except Exception:  # noqa: BLE001
            self.incident("multiligne illisible")


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
