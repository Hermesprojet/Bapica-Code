"""Le modèle structurel reconstruit d'un dessin, et sa forme JSON.

TOUT ÉLÉMENT DIT D'OÙ IL VIENT. ``Preuve`` porte les poignées des entités
sources, les ``INSERT`` qui les ont placées, les calques, les blocs, et la
RÈGLE qui a classé l'élément (``calque``, ``bloc``, ``type_de_ligne``,
``forme``). Rien n'est reconnu « parce que ça ressemble » sans que le
fondement le dise.

LES VALEURS SONT EN UNITÉS DU DESSIN, quantifiées au micromètre réel ;
l'unité est dite une fois, en tête du modèle, avec sa source.

LA FORME JSON (``eurostruct.structure/1``) a des clés anglaises, comme le
reste du contrat d'API. Elle est enregistrée dans le compte rendu d'analyse
du document — figée avec les propositions qui en sont tirées — et servie
telle quelle à l'écran de revue.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from .noyau import Point, Tolerances, quantifier
from .primitives import Primitive

__all__ = [
    "SCHEMA",
    "Appui",
    "Axe",
    "Bande",
    "CoteLue",
    "Dalle",
    "Famille",
    "Grille",
    "LibelleAffecte",
    "ModeleStructurel",
    "Niveau",
    "Noeud",
    "NonResolu",
    "Poteau",
    "Poutre",
    "Preuve",
    "Travee",
    "Tremie",
    "UnitesDessin",
    "Voile",
    "preuve_de",
]

SCHEMA: Final[str] = "eurostruct.structure/1"

#: Au-delà, la liste des poignées d'un élément est coupée (et le compte dit).
POIGNEES_CITEES_MAX: Final[int] = 40


# ------------------------------------------------------------------ preuve
@dataclass(frozen=True)
class Preuve:
    poignees: tuple[str, ...]
    calques: tuple[str, ...]
    insertions: tuple[str, ...]
    blocs: tuple[str, ...]
    types: tuple[str, ...]
    #: ``calque``, ``bloc``, ``type_de_ligne``, ``forme``.
    regle: str
    #: Le nom qui a décidé (calque, bloc, type de ligne), s'il y en a un.
    motif: str | None = None

    def fusion(self, autre: Preuve) -> Preuve:
        def union(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(sorted(set(a) | set(b)))
        regle = self.regle if _RANG_REGLE[self.regle] <= _RANG_REGLE[autre.regle] else autre.regle
        motif = self.motif if regle == self.regle else autre.motif
        return Preuve(union(self.poignees, autre.poignees), union(self.calques, autre.calques),
                      union(self.insertions, autre.insertions), union(self.blocs, autre.blocs),
                      union(self.types, autre.types), regle, motif)

    def en_json(self) -> dict[str, Any]:
        sortie: dict[str, Any] = {
            "handles": list(self.poignees[:POIGNEES_CITEES_MAX]),
            "layers": list(self.calques),
            "entity_types": list(self.types),
            "classified_by": self.regle,
        }
        if len(self.poignees) > POIGNEES_CITEES_MAX:
            sortie["handles_not_listed"] = len(self.poignees) - POIGNEES_CITEES_MAX
        if self.insertions:
            sortie["inserts"] = list(self.insertions[:POIGNEES_CITEES_MAX])
        if self.blocs:
            sortie["blocks"] = list(self.blocs)
        if self.motif:
            sortie["matched_name"] = self.motif
        return sortie


#: Plus le rang est petit, plus la règle est forte.
_RANG_REGLE: Final[dict[str, int]] = {"bloc": 0, "calque": 1, "type_de_ligne": 2,
                                      "forme": 3}


def preuve_de(primitives: Iterable[Primitive], regle: str,
              motif: str | None = None) -> Preuve:
    poignees: set[str] = set()
    calques: set[str] = set()
    insertions: set[str] = set()
    blocs: set[str] = set()
    types: set[str] = set()
    for p in primitives:
        if p.source.poignee:
            poignees.add(p.source.poignee)
        calques.add(p.calque)
        insertions.update(i for i in p.source.insertions if i)
        blocs.update(p.source.blocs)
        types.add(p.source.type)
    return Preuve(tuple(sorted(poignees)), tuple(sorted(calques)), tuple(sorted(insertions)),
                  tuple(sorted(blocs)), tuple(sorted(types)), regle, motif)


# ------------------------------------------------------------------ unités
@dataclass(frozen=True)
class UnitesDessin:
    #: ``mm``, ``cm``, ``m``, ``in``, ``ft`` — ou ``None`` : non déclarée.
    unite: str | None
    #: ``declaration`` ou ``absente`` (vocabulaire de ``unit_basis``).
    base: str
    #: ``$INSUNITS`` ou ``declaration_et_cotes`` ; ``None`` si absente.
    source: str | None
    insunits: int | None
    tolerances: Tolerances
    #: Pour une unité inférée : la mention écrite et les cotes concordantes.
    citation: dict[str, Any] | None = None

    def fondement(self) -> dict[str, Any]:
        sortie: dict[str, Any] = {"unit_basis": self.base}
        if self.base == "declaration":
            declaration: dict[str, Any] = {"source": self.source, "unit": self.unite}
            if self.source == "$INSUNITS":
                declaration["value"] = self.insunits
            if self.citation:
                declaration.update(self.citation)
            sortie["unit_declaration"] = declaration
        return sortie

    def en_json(self) -> dict[str, Any]:
        return {"drawing": self.unite, "basis": self.base, "source": self.source,
                "insunits": self.insunits, "tolerance": self.tolerances.longueur,
                "quantum": self.tolerances.quantum,
                **({"evidence": self.citation} if self.citation else {})}


# ---------------------------------------------------------------- éléments
@dataclass(frozen=True)
class Axe:
    id: str
    etiquette: str | None
    famille: int
    origine: Point
    direction: Point
    decalage: float
    debut: float
    fin: float
    preuve: Preuve
    confiance: float
    #: Comment l'étiquette a été trouvée : bulle, bloc, texte ; et sa poignée.
    etiquette_source: dict[str, Any] | None = None

    def point(self, t: float) -> Point:
        return (self.origine[0] + t * self.direction[0], self.origine[1] + t * self.direction[1])

    @property
    def extremites(self) -> tuple[Point, Point]:
        return (self.point(self.debut), self.point(self.fin))

    @property
    def nom(self) -> str:
        """L'étiquette lue ; à défaut, « famille.rang » (``0.1``) — jamais une
        lettre ou un chiffre que le dessin n'écrit pas."""
        return self.etiquette or self.id.removeprefix("grid:")


@dataclass(frozen=True)
class Famille:
    index: int
    angle: float
    #: Les axes, triés par décalage croissant.
    axes: tuple[str, ...]


@dataclass(frozen=True)
class Noeud:
    id: str
    etiquette: str | None
    point: Point
    axes: tuple[str, str]

    @property
    def nom(self) -> str:
        """« A1 » ; sans étiquettes, les noms des deux axes (``0.1x1.2``)."""
        return self.etiquette or self.id.removeprefix("node:")


@dataclass(frozen=True)
class Grille:
    axes: tuple[Axe, ...] = ()
    familles: tuple[Famille, ...] = ()
    noeuds: tuple[Noeud, ...] = ()
    #: Repère de la grille : l'axe des x est la direction de la famille la
    #: plus proche de l'horizontale. Sans grille, le repère du dessin.
    repere_x: Point = (1.0, 0.0)

    def axe(self, ident: str) -> Axe:
        return next(a for a in self.axes if a.id == ident)

    def entraxe_median(self) -> float | None:
        ecarts: list[float] = []
        for famille in self.familles:
            axes = [self.axe(i) for i in famille.axes]
            ecarts.extend(abs(b.decalage - a.decalage)
                          for a, b in zip(axes, axes[1:], strict=False))
        ecarts = sorted(e for e in ecarts if e > 0)
        return ecarts[len(ecarts) // 2] if ecarts else None


@dataclass(frozen=True)
class Poteau:
    id: str
    #: ``rectangle``, ``cercle``, ``polygone``.
    forme: str
    contour: tuple[Point, ...]
    centre: Point
    #: Côtés dans le repère de la grille (largeur selon x, profondeur selon y).
    largeur: float | None
    profondeur: float | None
    diametre: float | None
    angle: float
    noeud: str | None
    rempli: bool
    preuve: Preuve
    confiance: float
    repere: str | None = None
    repere_source: dict[str, Any] | None = None


@dataclass(frozen=True)
class Voile:
    id: str
    contour: tuple[Point, ...]
    axe: tuple[Point, Point] | None
    epaisseur: float | None
    longueur: float | None
    preuve: Preuve
    confiance: float
    repere: str | None = None
    repere_source: dict[str, Any] | None = None


@dataclass(frozen=True)
class Bande:
    """La géométrie d'une poutre en plan : un axe, une largeur, une étendue."""

    id: str
    origine: Point
    direction: Point
    #: Décalage de l'axe : ``n·x`` avec ``n = normale(direction)``.
    decalage: float
    largeur: float | None
    debut: float
    fin: float
    preuve: Preuve
    confiance: float
    #: ``paire_de_traits``, ``rectangle``, ``filaire``.
    dessin: str
    #: Vrai si la bande ne devient poutre qu'avec au moins deux appuis.
    provisoire: bool = False
    #: Appuis à travers lesquels deux morceaux ont été fusionnés.
    fusions: tuple[str, ...] = ()

    def point(self, t: float) -> Point:
        return (self.origine[0] + t * self.direction[0], self.origine[1] + t * self.direction[1])


@dataclass(frozen=True)
class Appui:
    element: str
    #: ``poteau``, ``voile``, ``poutre``.
    genre: str
    centre: float
    faces: tuple[float, float]
    noeud: str | None
    #: Vrai si l'appui ne fait que toucher la poutre (sans la traverser).
    contact: bool = False
    #: L'écart entre la fin du trait et l'appui, quand il y en a un.
    ecart: float = 0.0

    @property
    def largeur(self) -> float:
        return self.faces[1] - self.faces[0]


@dataclass(frozen=True)
class RattachementCote:
    poignee: str
    #: ``axis_length``, ``clear_length``, ``grid_spacing``, ``beam_width``…
    mesure_de: str
    mesure: float
    affichee: str
    #: Les points de définition mesurent l'élément (à la tolérance près).
    concordante: bool
    #: Le texte forcé contredit la mesure.
    discordante: bool


@dataclass(frozen=True)
class Travee:
    id: str
    poutre: str
    index: int
    nombre: int
    #: ``travee`` (entre deux appuis) ou ``console`` (porte-à-faux).
    genre: str
    debut: Appui | None
    fin: Appui | None
    entre_axes: float | None
    nu_a_nu: float | None
    confiance: float
    repere: str | None = None
    #: ``libelle``, ``poutre_continue``, ``grille``.
    repere_source: str | None = None
    cotes: tuple[RattachementCote, ...] = ()


@dataclass(frozen=True)
class Poutre:
    id: str
    bande: Bande
    appuis: tuple[Appui, ...]
    travees: tuple[Travee, ...]
    confiance: float
    reperes: tuple[str, ...] = ()
    #: Poutres qui portent celle-ci (jonctions en T).
    portee_par: tuple[str, ...] = ()
    libelles: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CoteLue:
    id: str
    poignee: str
    calque: str
    p1: Point
    p2: Point
    direction: Point
    mesure: float
    facteur: float
    #: La valeur que le dessin AFFICHE (mesure × DIMLFAC, ou texte forcé).
    affichee: str
    valeur_affichee: float | None
    forcee: bool
    #: Texte forcé numérique qui diffère de la valeur affichable.
    discordante: bool
    #: Ce que la cote mesure, si elle est rattachée : type et éléments.
    rattachement: dict[str, Any] | None = None
    concordante: bool | None = None
    chaine: str | None = None
    #: Un point de la ligne de cote (``defpoint``) : c'est elle qui fait la chaîne.
    ligne: Point | None = None


@dataclass(frozen=True)
class Dalle:
    id: str
    contour: tuple[Point, ...]
    #: ``panneau`` (cellule de grille portée), ``contour`` (calque de dalle).
    origine: str
    #: côté -> élément porteur, ou ``None`` pour un bord libre.
    bords: tuple[tuple[str, str | None], ...]
    lx: float | None
    ly: float | None
    marqueur: bool
    libelle: str | None
    preuve: Preuve
    confiance: float
    repere: str | None = None
    #: Les travées qui traversent le panneau : il n'est pas subdivisé, elles
    #: sont citées pour que l'ingénieur le voie.
    traversee_par: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tremie:
    id: str
    contour: tuple[Point, ...]
    largeur: float | None
    longueur: float | None
    dalle: str | None
    preuve: Preuve


@dataclass(frozen=True)
class Niveau:
    texte: str
    valeur: float
    point: Point
    poignee: str


@dataclass(frozen=True)
class LibelleAffecte:
    texte: str
    poignee: str
    marque: str
    element: str
    cout: float


@dataclass(frozen=True)
class NonResolu:
    element: str
    raison: str


@dataclass
class ModeleStructurel:
    unites: UnitesDessin
    grille: Grille = field(default_factory=Grille)
    poteaux: list[Poteau] = field(default_factory=list)
    voiles: list[Voile] = field(default_factory=list)
    poutres: list[Poutre] = field(default_factory=list)
    dalles: list[Dalle] = field(default_factory=list)
    tremies: list[Tremie] = field(default_factory=list)
    cotes: list[CoteLue] = field(default_factory=list)
    niveaux: list[Niveau] = field(default_factory=list)
    libelles: list[LibelleAffecte] = field(default_factory=list)
    non_resolus: list[NonResolu] = field(default_factory=list)
    compte_rendu: dict[str, Any] = field(default_factory=dict)
    #: Les poignées que la géométrie a absorbées (cotes rattachées, étiquettes
    #: d'axes) : l'extracteur d'entités ne les propose pas une seconde fois.
    absorbees: set[str] = field(default_factory=set)
    #: Les cotes rattachées, par élément (``cotes.Rattachements``). Hors JSON.
    rattachements: Any = field(default=None, repr=False, compare=False)

    # -------------------------------------------------------------- JSON
    def _q(self, valeur: float | None) -> int | float | None:
        if valeur is None:
            return None
        return quantifier(valeur, self.unites.tolerances.quantum)

    def _pt(self, p: Point) -> list[int | float | None]:
        return [self._q(p[0]), self._q(p[1])]

    def _pts(self, points: Sequence[Point]) -> list[list[int | float | None]]:
        return [self._pt(p) for p in points]

    def _appui(self, appui: Appui | None) -> dict[str, Any] | None:
        if appui is None:
            return None
        return {"support": appui.element, "kind": appui.genre, "centre": self._q(appui.centre),
                "faces": [self._q(appui.faces[0]), self._q(appui.faces[1])],
                "width": self._q(appui.largeur), "grid_node": appui.noeud,
                "touching_only": appui.contact, "gap": self._q(appui.ecart)}

    def _ligne_de(self, t: Travee, b: Bande) -> list[list[int | float | None]]:
        """La travée dans le plan : d'un centre d'appui à l'autre ; pour une
        console, du centre de l'appui au bout dessiné."""
        debut = t.debut.centre if t.debut else b.debut
        fin = t.fin.centre if t.fin else b.fin
        return self._pts((b.point(debut), b.point(fin)))

    def travees(self) -> list[Travee]:
        return [t for p in self.poutres for t in p.travees]

    def resume(self) -> dict[str, int]:
        return {"grid_axes": len(self.grille.axes), "grid_nodes": len(self.grille.noeuds),
                "columns": len(self.poteaux), "walls": len(self.voiles),
                "beams": len(self.poutres),
                "spans": sum(1 for t in self.travees() if t.genre == "travee"),
                "cantilevers": sum(1 for t in self.travees() if t.genre == "console"),
                "slabs": len(self.dalles), "openings": len(self.tremies),
                "dimensions": len(self.cotes), "levels": len({n.valeur for n in self.niveaux}),
                "unresolved": len(self.non_resolus)}

    def en_json(self) -> dict[str, Any]:
        g = self.grille
        grille = [{"id": a.id, "label": a.etiquette, "name": a.nom, "family": a.famille,
                   "line": self._pts(a.extremites), "confidence": a.confiance,
                   "label_source": a.etiquette_source, "evidence": a.preuve.en_json()}
                  for a in g.axes]
        familles = []
        for f in g.familles:
            axes = [g.axe(i) for i in f.axes]
            familles.append({
                "index": f.index, "angle_deg": round(f.angle, 6), "axes": list(f.axes),
                "spacings": [{"from": a.id, "to": b.id,
                              "labels": [a.etiquette, b.etiquette],
                              "distance": self._q(abs(b.decalage - a.decalage))}
                             for a, b in zip(axes, axes[1:], strict=False)]})
        poteaux = [{"id": p.id, "mark": p.repere, "shape": p.forme,
                    "outline": self._pts(p.contour), "centre": self._pt(p.centre),
                    "width": self._q(p.largeur), "depth": self._q(p.profondeur),
                    "diameter": self._q(p.diametre), "angle_deg": round(p.angle, 6),
                    "grid_node": p.noeud, "filled": p.rempli, "confidence": p.confiance,
                    "mark_source": p.repere_source, "evidence": p.preuve.en_json()}
                   for p in self.poteaux]
        voiles = [{"id": v.id, "mark": v.repere, "outline": self._pts(v.contour),
                   "axis": self._pts(v.axe) if v.axe else None,
                   "thickness": self._q(v.epaisseur), "length": self._q(v.longueur),
                   "confidence": v.confiance, "evidence": v.preuve.en_json()}
                  for v in self.voiles]
        poutres = []
        for p in self.poutres:
            b = p.bande
            poutres.append({
                "id": p.id, "marks": list(p.reperes), "width": self._q(b.largeur),
                "axis": self._pts((b.point(b.debut), b.point(b.fin))),
                "drawn_as": b.dessin, "supports": [a.element for a in p.appuis],
                "spans": [t.id for t in p.travees], "supported_by_beams": list(p.portee_par),
                "merged_through": list(b.fusions), "labels": list(p.libelles),
                "confidence": p.confiance, "evidence": b.preuve.en_json()})
        bandes = {p.id: p.bande for p in self.poutres}
        travees = [{"id": t.id, "beam": t.poutre, "kind": "span" if t.genre == "travee"
                    else "cantilever", "mark": t.repere, "mark_source": t.repere_source,
                    "index": t.index, "count": t.nombre,
                    "from": self._appui(t.debut), "to": self._appui(t.fin),
                    "line": self._ligne_de(t, bandes[t.poutre]),
                    "axis_length": self._q(t.entre_axes), "clear_length": self._q(t.nu_a_nu),
                    "dimensions": [{"handle": c.poignee, "measures": c.mesure_de,
                                    "measured": self._q(c.mesure), "displayed": c.affichee,
                                    "measure_agrees": c.concordante,
                                    "forced_mismatch": c.discordante}
                                   for c in t.cotes],
                    "confidence": t.confiance}
                   for t in self.travees()]
        dalles = [{"id": d.id, "mark": d.repere, "kind": d.origine,
                   "outline": self._pts(d.contour),
                   "edges": [{"side": cote, "supported_by": porteur}
                             for cote, porteur in d.bords],
                   "lx": self._q(d.lx), "ly": self._q(d.ly), "cross_marker": d.marqueur,
                   "crossed_by": list(d.traversee_par),
                   "label": d.libelle, "confidence": d.confiance,
                   "evidence": d.preuve.en_json()} for d in self.dalles]
        tremies = [{"id": t.id, "outline": self._pts(t.contour), "width": self._q(t.largeur),
                    "length": self._q(t.longueur), "slab": t.dalle,
                    "evidence": t.preuve.en_json()} for t in self.tremies]
        cotes = [{"id": c.id, "handle": c.poignee, "layer": c.calque,
                  "p1": self._pt(c.p1), "p2": self._pt(c.p2),
                  "measured": self._q(c.mesure), "dimlfac": c.facteur,
                  "displayed": c.affichee, "forced": c.forcee, "forced_mismatch": c.discordante,
                  "measures": c.rattachement, "measure_agrees": c.concordante,
                  "chain": c.chaine}
                 for c in self.cotes]
        noeuds_graphe: list[dict[str, Any]] = (
            [{"id": p.id, "type": "column", "mark": p.repere, "grid_node": p.noeud}
             for p in self.poteaux]
            + [{"id": v.id, "type": "wall", "mark": v.repere} for v in self.voiles])
        aretes: list[dict[str, Any]] = []
        for p in self.poutres:
            for t in p.travees:
                aretes.append({"id": t.id, "type": "beam_span" if t.genre == "travee"
                               else "cantilever", "beam": p.id, "mark": t.repere,
                               "from": t.debut.element if t.debut else None,
                               "to": t.fin.element if t.fin else None,
                               "axis_length": self._q(t.entre_axes),
                               "clear_length": self._q(t.nu_a_nu)})
            for porteuse in p.portee_par:
                aretes.append({"id": f"{p.id}>{porteuse}", "type": "beam_on_beam",
                               "from": p.id, "to": porteuse})
        return {
            "schema": SCHEMA,
            "units": self.unites.en_json(),
            "grid": grille,
            "grid_families": familles,
            "grid_nodes": [{"id": n.id, "label": n.etiquette, "name": n.nom,
                            "point": self._pt(n.point),
                            "axes": list(n.axes)} for n in g.noeuds],
            "columns": poteaux,
            "walls": voiles,
            "beams": poutres,
            "spans": travees,
            "slabs": dalles,
            "openings": tremies,
            "dimensions": cotes,
            "levels": [{"value": valeur,
                        "mentions": [{"text": n.texte, "point": self._pt(n.point),
                                      "handle": n.poignee}
                                     for n in self.niveaux if n.valeur == valeur]}
                       for valeur in sorted({n.valeur for n in self.niveaux})],
            "labels": [{"text": lab.texte, "handle": lab.poignee, "mark": lab.marque,
                        "assigned_to": lab.element, "cost": round(lab.cout, 3)}
                       for lab in self.libelles],
            "graph": {"nodes": noeuds_graphe, "edges": aretes},
            "unresolved": [{"element": n.element, "reason": n.raison}
                           for n in self.non_resolus],
            "counts": self.resume(),
            "report": self.compte_rendu,
        }
