"""``ExtracteurGeometrieDxf`` : la lecture géométrique dans la chaîne d'extraction.

IL PASSE EN PREMIER POUR UN DXF. Ce qu'il propose est mesuré sur les traits ;
les règles de texte passent ensuite, et ce qu'elles relisent à l'identique
devient une CORROBORATION de la proposition géométrique (registre). Les cotes
et les étiquettes d'axes qu'il a rattachées ne sont plus proposées par
l'extracteur d'entités.

Il laisse dans le contexte le modèle structurel (JSON) : le compte rendu
d'analyse l'enregistre, et l'écran de revue le dessine.
"""

from __future__ import annotations

from typing import Any

from ..modele import Candidat, DocumentAnalyse
from .construction import construire_modele
from .propositions import propositions_du_modele

__all__ = ["ExtracteurGeometrieDxf"]


class ExtracteurGeometrieDxf:
    nom = "geometrie"

    def extraire(self, analyse: DocumentAnalyse, contexte: Any) -> list[Candidat]:
        primitives = getattr(analyse, "primitives_dxf", None)
        if primitives is None:
            return []
        modele = construire_modele(primitives, list(getattr(contexte, "declarations", [])))
        if contexte is not None:
            contexte.structure = modele.en_json()
            contexte.absorbees.update(modele.absorbees)
        return propositions_du_modele(modele)
