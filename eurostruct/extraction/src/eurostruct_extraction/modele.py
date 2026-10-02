"""Ce qu'une lecture produit, et ce qu'une proposition porte.

Tout est gelé : une proposition qu'on peut retoucher après coup finit par dire
autre chose que ce qui a été lu.

LES COORDONNÉES SONT CELLES DU DOCUMENT
----------------------------------------
Pour un PDF : des **points PDF** (1/72 de pouce), origine en **haut à gauche**
de la page, ``y`` croissant vers le bas — la convention de pdfplumber, et celle
d'un écran qui surligne la zone. Une page OCR est ramenée à la même unité :
l'image est rendue à une échelle connue, et chaque boîte est divisée par elle.

Pour un DXF : il n'y a pas de page. L'espace objet est la « page 1 », et la
position est donnée dans les unités du dessin (point d'insertion, calque,
poignée), dans ``position`` plutôt que dans une boîte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Boite",
    "Candidat",
    "DocumentAnalyse",
    "EntiteDxf",
    "Mot",
    "PageLue",
]


@dataclass(frozen=True)
class Boite:
    """Un rectangle ``[x0, y0, x1, y1]`` en points PDF, origine en haut à gauche."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(
                f"boite desordonnee: [{self.x0}, {self.y0}, {self.x1}, {self.y1}]")

    def union(self, autre: Boite) -> Boite:
        return Boite(min(self.x0, autre.x0), min(self.y0, autre.y0),
                     max(self.x1, autre.x1), max(self.y1, autre.y1))

    @property
    def centre_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def hauteur(self) -> float:
        return self.y1 - self.y0

    def en_liste(self) -> list[float]:
        """Arrondie au centième de point : au-delà, c'est du bruit de lecture,
        et deux lectures du même document doivent rendre les mêmes nombres."""
        return [round(self.x0, 2), round(self.y0, 2),
                round(self.x1, 2), round(self.y1, 2)]


@dataclass(frozen=True)
class Mot:
    """Un mot lu, sa boîte, et comment il a été lu.

    ``confiance`` n'existe que pour l'OCR (0 à 1, rendue par Tesseract) : un
    caractère de la couche texte d'un PDF n'est pas « deviné ».
    """

    texte: str
    boite: Boite
    methode: str
    confiance: float | None = None


@dataclass(frozen=True)
class PageLue:
    """Une page, ses dimensions, et ce qui en a été lu — ou pourquoi rien."""

    numero: int
    largeur: float
    hauteur: float
    methode: str
    mots: tuple[Mot, ...] = ()
    motif: str | None = None


@dataclass(frozen=True)
class EntiteDxf:
    """Une entité de l'espace objet, réduite à ce que les règles lisent."""

    type: str
    calque: str
    poignee: str
    texte: str | None = None
    point: tuple[float, float] | None = None
    mesure: float | None = None
    points_de_definition: tuple[tuple[float, float], ...] = ()
    hauteur_texte: float | None = None
    #: Pour une cote : ``DIMLFAC`` effectif — la valeur affichée est
    #: ``mesure × facteur`` (un détail au 1/20 sur un plan au 1/50).
    facteur: float | None = None
    #: Pour une cote : sa nature (``lineaire``, ``alignee``, ``rayon``,
    #: ``diametre``, ``angulaire``, ``ordonnee``, ``autre``) et la mesure
    #: qu'AutoCAD a enregistrée (code 42), si le fichier en porte une.
    genre: str | None = None
    mesure_autocad: float | None = None


@dataclass(frozen=True)
class DocumentAnalyse:
    """Ce que ``parse_document`` a lu, et ce qu'il n'a pas pu lire.

    ``statut`` reprend le vocabulaire de ``documents.analysis_status`` :
    ``analyse``, ``partiel``, ``non_lu``, ``echec``. Le compte rendu est
    sérialisable tel quel en JSON — c'est lui qui est enregistré.
    """

    format: str
    statut: str
    detail: str | None
    nombre_de_pages: int | None
    couche_texte: bool | None
    pages: tuple[PageLue, ...] = ()
    entites_dxf: tuple[EntiteDxf, ...] = ()
    unites_dxf: str | None = None
    version_dwg: str | None = None
    compte_rendu: dict[str, Any] = field(default_factory=dict)
    #: Les octets lus, pour les extracteurs qui doivent RENDRE une page (vision).
    #: Hors de la représentation : un ``repr`` de 30 Mio n'aide personne.
    octets: bytes = field(default=b"", repr=False, compare=False)
    #: Pour un DXF, ou un PDF vectoriel d'une page : les primitives
    #: géométriques (``geometrie.PrimitivesDxf``). Hors représentation.
    primitives_dxf: Any = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Candidat:
    """Une proposition : une grandeur, et tout ce qui permet de la retrouver.

    ``valeur`` est un nombre ou un texte, ``unite`` une unité lisible par pint
    ou ``None`` — jamais une unité supposée sans le dire : ``fondement``
    porte ``unit_basis`` (``explicite``, ``declaration``, ``convention``,
    ``absente``) et, pour une déclaration, la mention citée et sa page.
    """

    categorie: str
    valeur: float | int | str
    unite: str | None
    texte_brut: str
    page: int
    confiance: float
    methode: str
    boite: Boite | None = None
    position: dict[str, Any] | None = None
    repere: str | None = None
    fondement: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # LES MEMES REGLES QUE LA BASE (0028), DITES PLUS TOT. Une proposition
        # que la base refuserait ferait echouer l'enregistrement de TOUTE
        # l'analyse; elle n'a donc pas le droit d'exister ici non plus.
        if not self.texte_brut.strip():
            raise ValueError("une proposition sans texte brut n'est pas tracee")
        if self.page < 1:
            raise ValueError("une page commence a 1")
        if self.boite is None and not self.position:
            raise ValueError("une proposition sans boite ni position")
        if not 0.0 <= self.confiance < 1.0:
            raise ValueError(
                f"confiance {self.confiance} hors de [0, 1[: elle est "
                "indicative et n'est jamais une certitude")
        if isinstance(self.valeur, str) and not self.valeur.strip():
            raise ValueError("une valeur texte blanche n'est pas une valeur")
        if self.unite is not None and not self.unite.strip():
            raise ValueError("une unite vide s'ecrit None")

    def en_ligne(self) -> dict[str, Any]:
        """La forme qu'attend ``project_document_record_analysis``."""
        return {
            "kind": self.categorie,
            "proposed_value": {"value": self.valeur, "unit": self.unite},
            "page": self.page,
            "bbox": self.boite.en_liste() if self.boite else None,
            "position": self.position,
            "confidence": self.confiance,
            "raw_text": self.texte_brut,
            "element_label": self.repere,
            "method": self.methode,
            "basis": self.fondement or None,
        }
