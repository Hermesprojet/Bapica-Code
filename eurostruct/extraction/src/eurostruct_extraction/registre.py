"""La chaîne d'extraction : quels extracteurs passent, et dans quel ordre.

CHAÎNE PAR DÉFAUT : les règles de texte (couche native, OCR, textes DXF),
puis les entités DXF (cotes, étiquettes d'axes). AUCUN modèle de vision : il
s'ajoute en passant une chaîne explicite, et il n'en change pas le contrat.

DEUX PROPOSITIONS IDENTIQUES SUR UNE MÊME PAGE N'EN FONT QU'UNE. « C30/37 »
répété dans la légende et dans une note ne demande pas deux décisions ; la
première lue, dans l'ordre de lecture, est gardée.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from .extracteurs.dxf_entites import ExtracteurEntitesDxf
from .extracteurs.lignes import Ligne, lignes_de_la_page, lignes_du_dxf
from .extracteurs.motifs import Contexte, extraire_des_lignes
from .extracteurs.unites import declarations_d_unite
from .modele import Candidat, DocumentAnalyse
from .version import VERSION_EXTRACTEUR

__all__ = [
    "CANDIDATS_MAX",
    "CHAINE_PAR_DEFAUT",
    "Extracteur",
    "ExtracteurMotifs",
    "ResultatExtraction",
    "extract_engineering_data",
]

#: Au-delà, les propositions restantes ne sont pas enregistrées — et le compte
#: rendu dit combien. Mille décisions sur un seul document ne seraient plus
#: une revue.
CANDIDATS_MAX: Final[int] = 1000


class Extracteur(Protocol):
    nom: str

    def extraire(self, analyse: DocumentAnalyse,
                 contexte: Contexte) -> list[Candidat]: ...


def _lignes(analyse: DocumentAnalyse) -> list[Ligne]:
    lignes: list[Ligne] = []
    for page in analyse.pages:
        lignes.extend(lignes_de_la_page(page))
    lignes.extend(lignes_du_dxf(analyse.entites_dxf, unites=analyse.unites_dxf))
    return lignes


class ExtracteurMotifs:
    nom = "motifs"

    def extraire(self, analyse: DocumentAnalyse, contexte: Contexte) -> list[Candidat]:
        return extraire_des_lignes(_lignes(analyse), contexte)


CHAINE_PAR_DEFAUT: Final[tuple[Extracteur, ...]] = (
    ExtracteurMotifs(), ExtracteurEntitesDxf())


@dataclass(frozen=True)
class ResultatExtraction:
    candidats: tuple[Candidat, ...]
    compte_rendu: dict[str, Any] = field(default_factory=dict)


def _cle(c: Candidat) -> tuple[Any, ...]:
    return (c.categorie, str(c.valeur), c.unite, c.page, c.repere)


def extract_engineering_data(
    analyse: DocumentAnalyse,
    extracteurs: Sequence[Extracteur] | None = None,
) -> ResultatExtraction:
    """``extractEngineeringData()`` : les propositions tracées d'un document.

    Aucune n'est confirmée ; aucune ne peut l'être ici. Le résultat est
    déterministe pour des octets et une version donnés.
    """
    chaine = tuple(extracteurs) if extracteurs is not None else CHAINE_PAR_DEFAUT
    contexte = Contexte(declarations=declarations_d_unite(_lignes(analyse)))

    brutes: list[Candidat] = []
    par_extracteur: dict[str, int] = {}
    for extracteur in chaine:
        trouves = extracteur.extraire(analyse, contexte)
        par_extracteur[extracteur.nom] = len(trouves)
        brutes.extend(trouves)

    vus: set[tuple[Any, ...]] = set()
    uniques: list[Candidat] = []
    for candidat in brutes:
        cle = _cle(candidat)
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(candidat)

    # L'ORDRE DE LECTURE: page, puis de haut en bas, de gauche a droite. Le
    # rang d'origine departage, pour qu'un tri ne depende jamais d'un hasard.
    ordonnes = [c for _, c in sorted(
        enumerate(uniques),
        key=lambda paire: (paire[1].page,
                           paire[1].boite.y0 if paire[1].boite else 0.0,
                           paire[1].boite.x0 if paire[1].boite else 0.0,
                           paire[0]))]

    retenus = ordonnes[:CANDIDATS_MAX]
    par_categorie: dict[str, int] = {}
    for c in retenus:
        par_categorie[c.categorie] = par_categorie.get(c.categorie, 0) + 1
    compte_rendu = {
        "extractor_version": VERSION_EXTRACTEUR,
        "extractors": list(par_extracteur),
        "found_by_extractor": par_extracteur,
        "duplicates_merged": len(brutes) - len(uniques),
        "not_recorded_beyond_limit": max(0, len(ordonnes) - CANDIDATS_MAX),
        "by_category": dict(sorted(par_categorie.items())),
        "unit_declarations": [d.citation() for d in contexte.declarations],
    }
    return ResultatExtraction(tuple(retenus), compte_rendu)
