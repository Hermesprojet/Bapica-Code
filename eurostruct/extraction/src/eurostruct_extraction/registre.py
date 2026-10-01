"""La chaîne d'extraction : quels extracteurs passent, et dans quel ordre.

CHAÎNE PAR DÉFAUT : la GÉOMÉTRIE d'un DXF d'abord (``geometrie/``), puis les
règles de texte (couche native, OCR, textes DXF), puis les entités DXF que la
géométrie n'a pas rattachées (cotes, étiquettes d'axes). AUCUN modèle de
vision : il s'ajoute en passant une chaîne explicite, et il n'en change pas le
contrat.

DEUX PROPOSITIONS IDENTIQUES SUR UNE MÊME PAGE N'EN FONT QU'UNE. « C30/37 »
répété dans la légende et dans une note ne demande pas deux décisions ; la
première lue est gardée — et c'est la géométrie, qui passe en premier. Une
relecture par une AUTRE méthode n'est pas perdue : elle devient une
corroboration de la proposition gardée (``corroborated_by``), et la
confiance gagne 0,05. Deux longueurs égales dans des unités différentes
(30 cm et 300 mm) sont la même grandeur.

DEUX VALEURS DIFFÉRENTES POUR UN MÊME ÉLÉMENT RESTENT DEUX PROPOSITIONS. La
largeur mesurée de P1 et celle écrite dans « P1 25x60 » se contredisent : les
deux sont gardées, chacune porte ``conflicts_with``, et l'ingénieur tranche.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Protocol

from .extracteurs.dxf_entites import ExtracteurEntitesDxf
from .extracteurs.lignes import Ligne, lignes_de_la_page, lignes_du_dxf
from .extracteurs.motifs import Contexte, extraire_des_lignes
from .extracteurs.unites import declarations_d_unite
from .geometrie.extracteur import ExtracteurGeometrieDxf
from .geometrie.noyau import MM_PAR_UNITE
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
    ExtracteurGeometrieDxf(), ExtracteurMotifs(), ExtracteurEntitesDxf())

#: Plafond d'une confiance relevée par corroboration.
PLAFOND_CORROBORE: Final[float] = 0.90
#: Les catégories qui décrivent UN élément : deux valeurs pour un même repère
#: s'y contredisent.
CATEGORIES_D_ELEMENT: Final[frozenset[str]] = frozenset({
    "beam_width", "beam_depth", "beam_span", "beam_clear_span", "cantilever_length",
    "column_width", "column_depth", "column_diameter", "wall_thickness",
    "grid_spacing", "slab_thickness",
})


@dataclass(frozen=True)
class ResultatExtraction:
    candidats: tuple[Candidat, ...]
    compte_rendu: dict[str, Any] = field(default_factory=dict)
    #: Le modèle structurel reconstruit (JSON), quand le document en a un.
    structure: dict[str, Any] | None = None


def _grandeur(c: Candidat) -> tuple[str, str | None]:
    """La valeur comparable : une longueur métrique est ramenée au millimètre."""
    if (c.unite in MM_PAR_UNITE and isinstance(c.valeur, int | float)
            and not isinstance(c.valeur, bool)):
        try:
            mm = (Decimal(str(c.valeur)) * MM_PAR_UNITE[c.unite]).normalize()
            return (format(mm, "f"), "mm")
        except InvalidOperation:  # pragma: no cover — str(float) est lisible
            pass
    return (str(c.valeur), c.unite)


def _cle(c: Candidat) -> tuple[Any, ...]:
    valeur, unite = _grandeur(c)
    return (c.categorie, valeur, unite, c.page, c.repere)


def _trace(c: Candidat) -> dict[str, Any]:
    trace: dict[str, Any] = {"method": c.methode, "raw_text": c.texte_brut[:200],
                             "value": c.valeur, "unit": c.unite}
    if c.boite is not None:
        trace["bbox"] = c.boite.en_liste()
    if c.position and c.position.get("handle"):
        trace["handle"] = c.position["handle"]
    return trace


def _confronter(candidats: list[Candidat]) -> list[Candidat]:
    """Deux valeurs différentes pour un même élément : chacune nomme l'autre.

    Seules se confrontent des valeurs de même unité : « 300 » sans unité (un
    texte « B1 300x600 ») ne contredit pas une largeur de 300 mm mesurée, et ne
    la corrobore pas non plus.
    """
    groupes: dict[tuple[Any, ...], list[int]] = {}
    for i, c in enumerate(candidats):
        if c.categorie in CATEGORIES_D_ELEMENT and c.repere:
            groupes.setdefault((c.categorie, c.page, c.repere, _grandeur(c)[1]),
                               []).append(i)
    sortie = list(candidats)
    for indices in groupes.values():
        valeurs = {_grandeur(candidats[i]) for i in indices}
        methodes = {candidats[i].methode for i in indices}
        if len(valeurs) < 2 or len(methodes) < 2:
            continue
        for i in indices:
            autres = [_trace(candidats[j]) for j in indices
                      if _grandeur(candidats[j]) != _grandeur(candidats[i])]
            sortie[i] = replace(sortie[i], fondement={**sortie[i].fondement,
                                                     "conflicts_with": autres})
    return sortie


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

    rang_de: dict[tuple[Any, ...], int] = {}
    uniques: list[Candidat] = []
    corroborations = 0
    for candidat in brutes:
        cle = _cle(candidat)
        if cle in rang_de:
            garde = uniques[rang_de[cle]]
            if candidat.methode != garde.methode:
                # UNE RELECTURE PAR UNE AUTRE METHODE CORROBORE: elle est citee.
                corroborations += 1
                fondement = dict(garde.fondement)
                fondement["corroborated_by"] = [*fondement.get("corroborated_by", []),
                                                _trace(candidat)]
                uniques[rang_de[cle]] = replace(
                    garde, fondement=fondement,
                    confiance=round(min(max(garde.confiance, candidat.confiance) + 0.05,
                                        max(PLAFOND_CORROBORE, garde.confiance)), 3))
            continue
        rang_de[cle] = len(uniques)
        uniques.append(candidat)
    uniques = _confronter(uniques)

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
        "corroborations": corroborations,
        "not_recorded_beyond_limit": max(0, len(ordonnes) - CANDIDATS_MAX),
        "by_category": dict(sorted(par_categorie.items())),
        "unit_declarations": [d.citation() for d in contexte.declarations],
    }
    if contexte.structure is not None:
        compte_rendu["geometry"] = {"counts": contexte.structure.get("counts", {}),
                                    "units": contexte.structure.get("units", {})}
    return ResultatExtraction(tuple(retenus), compte_rendu, contexte.structure)
