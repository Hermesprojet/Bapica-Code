"""Le contrat des pièces déposées et des valeurs qu'on en extrait.

CE QU'AUCUN DE CES CORPS NE PORTE
-----------------------------------
Ni ``org_id``, ni identité du déposant ou du décideur, ni nom, ni date de
décision, ni empreinte, ni chemin de stockage, ni format. L'organisation vient
du projet ; l'identité, du jeton ; le nom du décideur, de son adhésion ; la
date, du serveur ; l'empreinte et le format, des octets eux-mêmes. ``Strict``
refuse ces champs par un 422 : un client qui les envoie apprend qu'ils n'ont
aucun effet, au lieu de le croire.

CE QUE CES RÉPONSES NE DISENT JAMAIS
-------------------------------------
Qu'une valeur proposée est juste. Une proposition est le résultat d'une
lecture ; elle n'entre dans aucun calcul avant qu'une personne nommée l'ait
confirmée ou corrigée, et la base l'enregistre.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import ProvenanceDTO, Strict
from .structure import ModeleStructurel, ResumeDeStructure

__all__ = [
    "SOURCES_DE_VALEUR",
    "ChampPrerempli",
    "ConflitDePreremplissage",
    "DecisionExtraction",
    "DocumentDepose",
    "DocumentTeleverse",
    "Extraction",
    "ListeDocuments",
    "ListeExtractions",
    "NonReportable",
    "Preremplissage",
    "StructureDuDocument",
    "ValeurExtraite",
]

NatureDeDocument = Literal["architect_drawing", "formwork_drawing", "cctp", "other"]
StatutAnalyse = Literal["en_attente", "analyse", "partiel", "non_lu", "echec"]
StatutExtraction = Literal["proposed", "confirmed", "corrected", "rejected"]
#: D'OU VIENT UNE VALEUR, pour que la revue les distingue : le texte d'un PDF,
#: l'OCR d'un PDF numérisé, un texte ou une cote du DXF, la géométrie du DXF,
#: un détecteur visuel.
SourceDeValeur = Literal["text", "ocr", "cad_text", "geometry", "vision"]
#: La méthode enregistrée (``extractions.method``) -> sa source, et son libellé.
SOURCES_DE_VALEUR: dict[str, tuple[SourceDeValeur, str]] = {
    "texte_natif": ("text", "Texte du PDF"),
    "ocr": ("ocr", "OCR (PDF numérisé)"),
    "dxf": ("cad_text", "Texte ou cote du DXF"),
    "geometrie": ("geometry", "Géométrie du DXF"),
    "vision": ("vision", "Détection visuelle"),
}


class ValeurExtraite(Strict):
    """Une grandeur : un nombre ou un texte, et son unité — ou ``null``.

    ``null`` VEUT DIRE « AUCUNE UNITÉ N'EST ÉCRITE », jamais « en millimètres ».
    Une longueur sans unité ne se reporte pas dans une étude : elle se corrige
    d'abord.
    """

    value: int | float | str
    unit: str | None = Field(
        description="Unité lisible par pint (mm, m, kN/m^2), ou null quand "
                    "aucune n'est écrite ni déclarée.")


class DocumentDepose(Strict):
    document_id: str
    kind: str = Field(description="Nature déclarée au dépôt.")
    kind_label: str
    filename: str
    format: Literal["pdf", "dxf", "dwg"] = Field(
        description="Constaté sur la signature des octets.")
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int | None = None
    text_layer: bool | None = None
    analysis_status: StatutAnalyse
    analysis_status_label: str
    analysis_detail: str | None = None
    analysis_report: dict[str, Any] | None = None
    extractor_version: str | None = None
    analysed_at: str | None = None
    uploaded_by_me: bool
    created_at: str
    proposed_count: int = Field(ge=0)
    confirmed_count: int = Field(ge=0)
    corrected_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    can_reanalyse: bool = Field(
        description="Vrai tant qu'aucune proposition n'est enregistrée : une "
                    "nouvelle analyse ne contredit alors rien.")
    has_structure: bool = Field(
        default=False,
        description="Un modèle structurel a été reconstruit depuis la géométrie "
                    "(DXF) ; il se lit sur /documents/{id}/structure.")
    structure_summary: ResumeDeStructure | None = None


class ListeDocuments(Strict):
    project_id: str
    documents: list[DocumentDepose]


class DocumentTeleverse(Strict):
    """La réponse au dépôt : le document, et ce que son analyse a proposé."""

    document: DocumentDepose
    already_present: bool = Field(
        description="Les mêmes octets étaient déjà déposés dans ce projet : "
                    "le document existant est rendu, sans seconde analyse.")
    extractions_created: int = Field(ge=0)
    notice: str


class Extraction(Strict):
    extraction_id: str
    document_id: str
    document_filename: str
    kind: str
    kind_label: str
    proposed_value: ValeurExtraite
    final_value: ValeurExtraite | None = None
    status: StatutExtraction
    page: int
    bbox: list[float] | None = Field(
        default=None,
        description="[x0, y0, x1, y1] en points PDF, origine en haut à gauche.")
    position: dict[str, Any] | None = Field(
        default=None,
        description="Dimensions de la page, ou calque / poignée / point "
                    "d'insertion pour un DXF.")
    confidence: float = Field(ge=0, lt=1)
    method: str
    model_name: str
    raw_text: str
    element_label: str | None = None
    basis: dict[str, Any] | None = None
    confirmed_by_name: str | None = None
    confirmed_at: str | None = None
    decision_note: str | None = None
    created_at: str
    form_field: str | None = Field(
        default=None,
        description="Le chemin de l'étude que cette catégorie peut renseigner, "
                    "ou null si aucun champ ne la reçoit.")
    form_field_label: str | None = None
    form_warning: str | None = Field(
        default=None,
        description="Ce que l'ingénieur doit vérifier avant de reporter, "
                    "p. ex. qu'une portée entre axes n'est pas toujours la "
                    "portée utile.")
    source_type: SourceDeValeur = Field(
        description="text, ocr, cad_text (texte ou cote du DXF), geometry "
                    "(mesurée sur le dessin), vision.")
    source_label: str


class ListeExtractions(Strict):
    project_id: str
    extractions: list[Extraction]
    notice: str


class DecisionExtraction(Strict):
    """Ce que la personne décide. Ni son nom, ni la date : le serveur les pose."""

    decision: Literal["confirm", "correct", "reject"]
    final_value: ValeurExtraite | None = Field(
        default=None,
        description="Exigée pour une correction, interdite pour un rejet, "
                    "facultative pour une confirmation (elle doit alors être "
                    "la valeur proposée).")
    note: str | None = Field(default=None, max_length=1000)


class ChampPrerempli(Strict):
    path: str = Field(description="Chemin du contrat de l'étude, p. ex. geometry.b.")
    label: str
    value: int | float | str = Field(
        description="Dans l'unité du champ : aucune conversion n'est laissée "
                    "au navigateur.")
    unit: str | None
    extraction_id: str
    provenance: ProvenanceDTO = Field(
        description="À renvoyer telle quelle avec la requête de calcul : le "
                    "serveur la vérifiera et la réécrira depuis la base.")
    source_value: ValeurExtraite = Field(
        description="La valeur retenue, telle qu'elle a été décidée.")
    element_label: str | None = None
    warning: str | None = None


class ConflitDePreremplissage(Strict):
    path: str
    label: str
    candidates: list[ChampPrerempli]
    reason: str


class NonReportable(Strict):
    extraction_id: str
    kind: str
    kind_label: str
    reason: str


class Preremplissage(Strict):
    project_id: str
    element: str | None = None
    fields: list[ChampPrerempli]
    conflicts: list[ConflitDePreremplissage]
    not_reportable: list[NonReportable]
    notice: str


class StructureDuDocument(Strict):
    """Le modèle structurel d'un DXF, tel qu'il a été enregistré avec l'analyse.

    Il est figé avec les propositions qu'il a produites : la même lecture,
    relue dix ans plus tard, montre les mêmes poteaux et les mêmes travées.
    """

    project_id: str
    document_id: str
    filename: str
    extractor_version: str | None
    structure: ModeleStructurel
    notice: str
