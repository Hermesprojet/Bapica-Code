"""La place d'un futur modèle de vision : poutres, poteaux, dalles, voiles,
cotes, repérés directement sur l'image du plan.

AUCUN MODÈLE N'EST LIVRÉ. Ce module fixe le CONTRAT qu'un modèle devra tenir,
et la façon dont ses détections deviennent des propositions — les mêmes que
celles des règles de texte : tracées, plafonnées, et soumises à la même
décision humaine. Un modèle ne pourra jamais faire plus que proposer : la
règle qui l'interdit est dans la base (statut ``proposed`` à l'écriture,
décision signée), pas dans le modèle.

CE QU'UN MODÈLE REND : des objets d'une des cinq classes, une boîte en points
PDF, une confiance, et — s'il les a lues — des valeurs avec leur unité et le
texte qu'il a lu pour les obtenir. Une détection sans valeur devient une
proposition « élément détecté » : la classe, rien de plus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

from ..lecteurs.ocr import rendre_page
from ..modele import Boite, Candidat, DocumentAnalyse

__all__ = [
    "ATTRIBUTS_VISION",
    "ClasseVision",
    "ExtracteurVision",
    "ModeleDeVision",
    "ObjetDetecte",
    "PageRendue",
    "ValeurLue",
]

ClasseVision = Literal["beam", "column", "slab", "wall", "dimension"]
CLASSES_VISION: Final[frozenset[str]] = frozenset(
    {"beam", "column", "slab", "wall", "dimension"})

#: (classe, attribut) → catégorie de proposition. Un attribut absent de cette
#: table n'est pas proposé : on ne range pas une valeur dans une catégorie
#: qu'on a devinée.
ATTRIBUTS_VISION: Final[dict[tuple[str, str], str]] = {
    ("beam", "width"): "beam_width",
    ("beam", "depth"): "beam_depth",
    ("beam", "span"): "beam_span",
    ("column", "width"): "column_width",
    ("column", "depth"): "column_depth",
    ("column", "diameter"): "column_diameter",
    ("slab", "thickness"): "slab_thickness",
    ("wall", "thickness"): "wall_thickness",
    ("dimension", "value"): "dimension",
}

#: Une détection ne vaut jamais plus que cela.
PLAFOND_VISION: Final[float] = 0.90


@dataclass(frozen=True)
class ValeurLue:
    valeur: float | int | str
    unite: str | None
    texte_brut: str | None = None


@dataclass(frozen=True)
class ObjetDetecte:
    classe: str
    boite: Boite
    confiance: float
    attributs: Mapping[str, ValeurLue] = field(default_factory=dict)
    repere: str | None = None


@dataclass(frozen=True)
class PageRendue:
    numero: int
    image: Any
    #: Pixels par point PDF : une boîte en pixels se divise par ce nombre.
    echelle: float
    largeur: float
    hauteur: float


class ModeleDeVision(Protocol):
    nom: str
    version: str

    def detecter(self, page: PageRendue) -> Sequence[ObjetDetecte]: ...


class ExtracteurVision:
    """Adapte un :class:`ModeleDeVision` à la chaîne d'extraction."""

    def __init__(self, modele: ModeleDeVision, *, pages_max: int = 4) -> None:
        self.modele = modele
        self.pages_max = pages_max
        self.nom = f"vision:{modele.nom}/{modele.version}"

    def extraire(self, analyse: DocumentAnalyse, contexte: Any = None) -> list[Candidat]:
        if analyse.format != "pdf" or not analyse.octets:
            return []
        candidats: list[Candidat] = []
        for page in analyse.pages[: self.pages_max]:
            image, echelle, largeur, hauteur = rendre_page(analyse.octets, page.numero - 1)
            rendue = PageRendue(page.numero, image, echelle, largeur, hauteur)
            for objet in self.modele.detecter(rendue):
                candidats.extend(self._propositions(objet, rendue))
        return candidats

    def _propositions(self, objet: ObjetDetecte, page: PageRendue) -> list[Candidat]:
        if objet.classe not in CLASSES_VISION:
            return []
        confiance = round(min(max(float(objet.confiance), 0.0), PLAFOND_VISION), 3)
        position = {"origin": "top-left", "unit": "pt",
                    "page_width": round(page.largeur, 2),
                    "page_height": round(page.hauteur, 2)}
        fondement_commun = {"rule": "vision", "model": self.modele.nom,
                            "model_version": self.modele.version,
                            "class": objet.classe}
        if not objet.attributs:
            return [Candidat(
                categorie="detected_element", valeur=objet.classe, unite=None,
                texte_brut=(f"{objet.classe} detecte par {self.modele.nom} "
                            f"{self.modele.version}, sans texte lu"),
                page=page.numero, confiance=confiance, methode="vision",
                boite=objet.boite, position=position, repere=objet.repere,
                fondement=dict(fondement_commun))]
        propositions = []
        for attribut, lue in sorted(objet.attributs.items()):
            categorie = ATTRIBUTS_VISION.get((objet.classe, attribut))
            if categorie is None:
                continue
            fondement = dict(fondement_commun, attribute=attribut,
                             unit_basis="explicite" if lue.unite else "absente")
            propositions.append(Candidat(
                categorie=categorie, valeur=lue.valeur, unite=lue.unite,
                texte_brut=(lue.texte_brut or
                            f"{objet.classe}.{attribut} lu par {self.modele.nom}"),
                page=page.numero, confiance=confiance, methode="vision",
                boite=objet.boite, position=position, repere=objet.repere,
                fondement=fondement))
        return propositions
