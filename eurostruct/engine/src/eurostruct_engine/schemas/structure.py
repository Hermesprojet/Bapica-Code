"""Le modèle structurel qu'un DXF donne par sa géométrie (``eurostruct.structure/1``).

CE CONTRAT DÉCRIT UNE LECTURE, PAS UN CALCUL
--------------------------------------------
Les longueurs sont dans l'unité DU DESSIN (``units.drawing``), ou sans unité
quand le dessin ne la déclare pas ; rien n'y est converti, rien n'y est
arrondi au-delà du bruit des flottants (``units.quantum``). Une portée y est
une distance entre appuis (``axis_length``) ou entre leurs nus
(``clear_length``) — jamais la portée utile l_eff, qui reste à l'ingénieur.

CHAQUE ÉLÉMENT CITE CE QUI L'A FAIT RECONNAÎTRE (``evidence``) : poignées des
entités, calques, blocs, et la règle — bloc, calque, type de ligne, forme, ou
signature géométrique (``geometrie`` : la forme et le motif ont décidé, un nom
qui concorde est cité).
Ce qui n'a pas permis de conclure est dans ``unresolved``, avec sa raison.

LE CONTRAT EST FERMÉ (``Strict``) : une clé ajoutée par l'extracteur sans être
décrite ici fait échouer la réponse, et les tests de l'API le voient.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from .common import Strict

__all__ = [
    "AppuiDeTravee",
    "AreteDuGraphe",
    "AxeDeGrille",
    "BordDeDalle",
    "CoteDeTravee",
    "CoteDuDessin",
    "DalleLue",
    "EntraxeDeGrille",
    "FamilleDeGrille",
    "GrapheStructurel",
    "LibelleAffecte",
    "MentionDeNiveau",
    "ModeleStructurel",
    "NiveauLu",
    "NoeudDeGrille",
    "NoeudDuGraphe",
    "NonResolu",
    "PieuLu",
    "PoteauLu",
    "PoutreLue",
    "PreuveGeometrique",
    "ResumeDeStructure",
    "TraveeLue",
    "TremieLue",
    "UnitesDuDessin",
    "VoileLu",
]

Nombre = int | float
#: Un point du dessin, [x, y], dans l'unité du dessin.
Point = list[Nombre]


class _Lecture(Strict):
    """Les clés ``from`` et ``schema`` sont des mots réservés côté Python."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PreuveGeometrique(_Lecture):
    handles: list[str] = Field(
        description="Poignées DXF des entités citées (rang de l'objet sur une feuille PDF).")
    layers: list[str] = Field(
        description="Calques DXF ; sur une feuille PDF, style du trait (pdf:#RRGGBB:épaisseur).")
    entity_types: list[str]
    classified_by: Literal["bloc", "calque", "style", "type_de_ligne", "forme",
                           "geometrie"] = Field(
        description="style : un style de trait APPRIS d'une feuille PDF (axes, cotes) ; "
                    "geometrie : une signature géométrique complète a décidé (axe : bulle "
                    "et famille, ou trait-point parallèle à une famille ; pieu : classe "
                    "de diamètre ; poteau : section coupée au nœud de la grille, ou grille "
                    "implicite sans axes, ou section vide d'un bloc répété), quel que soit "
                    "le nom du calque ou du bloc.")
    handles_not_listed: int | None = None
    inserts: list[str] | None = Field(
        default=None, description="Poignées des INSERT qui ont placé les entités.")
    blocks: list[str] | None = None
    matched_name: str | None = Field(
        default=None, description="Le nom (calque, bloc, type de ligne) qui a décidé ; pour "
                                  "une décision geometrie, le nom qui la confirme.")
    signature: list[str] | None = Field(
        default=None, description="Les critères géométriques vus — axe : bulle, famille, "
                                  "motif_mixte, parallele_a_une_famille, zone ; pieu : "
                                  "classe_de_diametre, motif_tirets, rempli ; poteau : "
                                  "section, coupe, au_noeud, zone, section_repetee, "
                                  "bloc_repete, repere, grille_implicite.")


class UnitesDuDessin(_Lecture):
    drawing: str | None = Field(
        description="mm, cm, m, in, ft — ou null : le dessin ne déclare pas son unité.")
    basis: Literal["declaration", "absente"]
    source: str | None = Field(
        description="$INSUNITS, declaration_et_cotes (mention écrite ET cotes), "
                    "echelle_de_presentation (DXF : échelle écrite dans la présentation ET "
                    "fenêtre), ou echelle_ecrite_et_cotes (feuille PDF : échelle écrite ET "
                    "cotes).")
    insunits: int | None
    tolerance: float
    quantum: float
    evidence: dict[str, Any] | None = None
    sheet: dict[str, Any] | None = Field(
        default=None,
        description="Feuille PDF : page, mm_per_point (null sans échelle établie), "
                    "page_height_pt, page_width_pt.")


class AxeDeGrille(_Lecture):
    id: str
    label: str | None = Field(description="L'étiquette LUE ; jamais inventée.")
    name: str = Field(description="L'étiquette, ou « famille.rang » à défaut.")
    family: int
    line: list[Point]
    confidence: float
    label_source: dict[str, Any] | None
    evidence: PreuveGeometrique


class EntraxeDeGrille(_Lecture):
    from_: str = Field(alias="from")
    to: str
    labels: list[str | None]
    distance: Nombre


class FamilleDeGrille(_Lecture):
    index: int
    angle_deg: float
    axes: list[str]
    spacings: list[EntraxeDeGrille]


class NoeudDeGrille(_Lecture):
    id: str
    label: str | None
    name: str
    point: Point
    axes: list[str]


class PoteauLu(_Lecture):
    id: str
    mark: str | None
    shape: Literal["rectangle", "cercle", "polygone"]
    outline: list[Point]
    centre: Point
    width: Nombre | None = Field(description="Selon l'axe x de la grille.")
    depth: Nombre | None
    diameter: Nombre | None
    angle_deg: float
    grid_node: str | None
    filled: bool
    confidence: float
    mark_source: dict[str, Any] | None
    evidence: PreuveGeometrique


class PieuLu(_Lecture):
    """Un pieu : montré et compté, jamais un poteau ; aucune valeur n'en est
    proposée (fondations profondes hors du domaine validé du moteur)."""

    id: str
    mark: str | None
    shape: Literal["rectangle", "cercle", "polygone"]
    centre: Point
    diameter: Nombre | None
    width: Nombre | None
    depth: Nombre | None
    outline: list[Point] | None = Field(
        description="Le contour, sauf pour un cercle (centre et diamètre suffisent).")
    grid_node: str | None
    confidence: float
    mark_source: dict[str, Any] | None
    evidence: PreuveGeometrique


class VoileLu(_Lecture):
    id: str
    mark: str | None
    outline: list[Point]
    axis: list[Point] | None
    thickness: Nombre | None
    length: Nombre | None
    confidence: float
    evidence: PreuveGeometrique


class PoutreLue(_Lecture):
    id: str
    marks: list[str]
    width: Nombre | None
    axis: list[Point]
    drawn_as: str = Field(description="rectangle, paire_de_traits, filaire.")
    supports: list[str]
    spans: list[str]
    supported_by_beams: list[str]
    merged_through: list[str] = Field(
        description="Les appuis à travers lesquels deux morceaux dessinés ont été réunis.")
    labels: list[dict[str, Any]]
    confidence: float
    evidence: PreuveGeometrique


class AppuiDeTravee(_Lecture):
    support: str
    kind: Literal["poteau", "voile", "poutre"]
    centre: Nombre
    faces: list[Nombre]
    width: Nombre
    grid_node: str | None
    touching_only: bool
    gap: Nombre


class CoteDeTravee(_Lecture):
    handle: str
    measures: str
    measured: Nombre
    displayed: str
    measure_agrees: bool = Field(
        description="Les points de définition mesurent l'élément.")
    forced_mismatch: bool = Field(description="Le texte forcé contredit la mesure.")


class TraveeLue(_Lecture):
    id: str
    beam: str
    kind: Literal["span", "cantilever"]
    mark: str | None
    mark_source: str | None
    index: int
    count: int
    from_: AppuiDeTravee | None = Field(alias="from")
    to: AppuiDeTravee | None
    line: list[Point] = Field(
        description="Dans le plan : d'un centre d'appui à l'autre ; pour une "
                    "console, du centre de l'appui au bout dessiné.")
    axis_length: Nombre | None = Field(description="Entre les centres des appuis.")
    clear_length: Nombre | None = Field(description="Entre les nus des appuis.")
    dimensions: list[CoteDeTravee]
    confidence: float


class BordDeDalle(_Lecture):
    side: str
    supported_by: str | None = Field(description="null : bord libre.")


class DalleLue(_Lecture):
    id: str
    mark: str | None
    kind: Literal["panneau", "contour"]
    outline: list[Point]
    edges: list[BordDeDalle]
    lx: Nombre | None
    ly: Nombre | None
    cross_marker: bool
    crossed_by: list[str] = Field(
        description="Travées qui traversent le panneau ; il n'est pas subdivisé.")
    label: str | None
    confidence: float
    evidence: PreuveGeometrique


class TremieLue(_Lecture):
    id: str
    outline: list[Point]
    width: Nombre | None
    length: Nombre | None
    slab: str | None
    evidence: PreuveGeometrique


class CoteDuDessin(_Lecture):
    id: str
    handle: str
    layer: str
    p1: Point
    p2: Point
    measured: Nombre
    dimlfac: float
    displayed: str
    forced: bool
    forced_mismatch: bool
    measures: dict[str, Any] | None = Field(
        description="Ce que la cote mesure (entraxe, travée, largeur…), ou null.")
    measure_agrees: bool | None
    chain: str | None


class MentionDeNiveau(_Lecture):
    text: str
    point: Point
    handle: str


class NiveauLu(_Lecture):
    value: float
    mentions: list[MentionDeNiveau]


class LibelleAffecte(_Lecture):
    text: str
    handle: str
    mark: str
    assigned_to: str
    cost: float


class NoeudDuGraphe(_Lecture):
    id: str
    type: Literal["column", "wall"]
    mark: str | None
    grid_node: str | None = None


class AreteDuGraphe(_Lecture):
    id: str
    type: Literal["beam_span", "cantilever", "beam_on_beam"]
    beam: str | None = None
    mark: str | None = None
    from_: str | None = Field(alias="from")
    to: str | None
    axis_length: Nombre | None = None
    clear_length: Nombre | None = None


class GrapheStructurel(_Lecture):
    nodes: list[NoeudDuGraphe]
    edges: list[AreteDuGraphe]


class NonResolu(_Lecture):
    element: str
    reason: str


class ModeleStructurel(_Lecture):
    schema_: Literal["eurostruct.structure/1"] = Field(alias="schema")
    units: UnitesDuDessin
    grid: list[AxeDeGrille]
    grid_families: list[FamilleDeGrille]
    grid_nodes: list[NoeudDeGrille]
    columns: list[PoteauLu]
    piles: list[PieuLu] = Field(
        default_factory=list,
        description="Les pieux (absents des modèles enregistrés avant leur lecture).")
    walls: list[VoileLu]
    beams: list[PoutreLue]
    spans: list[TraveeLue]
    slabs: list[DalleLue]
    openings: list[TremieLue]
    dimensions: list[CoteDuDessin]
    levels: list[NiveauLu]
    labels: list[LibelleAffecte]
    graph: GrapheStructurel
    unresolved: list[NonResolu]
    counts: dict[str, int]
    report: dict[str, Any]


class ResumeDeStructure(_Lecture):
    """Ce que la liste des documents dit du modèle, sans le transporter."""

    schema_version: str
    drawing_units: str | None
    unit_basis: str
    counts: dict[str, int]
