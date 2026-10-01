"""``construire_modele`` : des primitives au modèle structurel, dans un ordre fixe.

    tolérances → axes → contours → pieux → poteaux → voiles → bandes → graphe
    → cotes → repères → dalles et trémies → niveaux

L'UNITÉ D'UN DESSIN QUI NE LA DÉCLARE PAS (``$INSUNITS = 0``) n'est attachée
que si DEUX sources concordent : une mention écrite (« Cotes en cm ») ET au
moins deux cotes rattachées qui affichent leur propre mesure (``DIMLFAC = 1``,
aucun texte forcé discordant). Le modèle est alors reconstruit avec cette
unité — les seuils de plausibilité en millimètres s'appliquent — et la
proposition cite les deux sources. Sinon, les longueurs restent sans unité.

OU SI SA PRÉSENTATION LE DIT (``presentation.py``) : une échelle écrite au
cartouche et une fenêtre qui montre ``r`` unités du dessin par mm de papier
donnent ``n / r`` mm par unité — une unité si c'est celui du mm, du cm, du m,
du pouce ou du pied à 0,5 % près. Si la mention écrite et la présentation se
contredisent, rien n'est établi, et c'est dit.

UNE FEUILLE PDF (``prims.cadre``) arrive déjà convertie en millimètres réels
quand son échelle est écrite ET confirmée par ses cotes (``echelle.py``) ;
sinon en points-papier, sans unité. Aucune inférence de plus n'est tentée :
l'échelle est la seule source d'unité d'une feuille.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from ..extracteurs.unites import Declaration, unite_declaree
from .axes import detecter_axes
from .classification import classer
from .cotes import Rattachements, lire_cotes, rattacher_cotes
from .dalles import detecter_dalles
from .graphe import construire_poutres
from .libelles import affecter_libelles
from .modele import ModeleStructurel, NonResolu, Poutre, UnitesDessin
from .niveaux import lire_niveaux
from .noyau import MM_PAR_UNITE, IndexSpatial, Tolerances, boite_de, distance
from .pieux import detecter_pieux
from .poteaux import detecter_poteaux, formes_fermees
from .poutres import detecter_bandes
from .presentation import unite_par_presentation
from .primitives import PrimitivesDxf, Segment
from .voiles import detecter_voiles

__all__ = ["construire_modele", "tolerances_du_dessin"]


def _puissance_de_dix(pas: float) -> float:
    """Le pas décimal immédiatement plus fin : un micromètre en pouces
    (3,9e-5) devient 1e-5, pour qu'une cote de 120 in ne s'écrive pas
    120,00002."""
    return 10.0 ** math.floor(math.log10(pas))


#: Une feuille PDF : la précision des coordonnées (0,01 pt ≈ 0,18 mm au 1/50)
#: interdit de quantifier plus fin que le dixième de millimètre.
QUANTUM_FEUILLE_MM = 0.1
#: Deux points d'une feuille sont confondus sous 1 mm réel, ou sous deux
#: centièmes de point à l'échelle quand c'est plus grand.
CENTIEMES_DE_POINT = 0.02


def tolerances_du_dessin(prims: PrimitivesDxf, unite: str | None) -> Tolerances:
    mm_par_point = (prims.cadre or {}).get("mm_per_point")
    if unite == "mm" and mm_par_point:
        return Tolerances(longueur=max(1.0, CENTIEMES_DE_POINT * float(mm_par_point)),
                          quantum=QUANTUM_FEUILLE_MM, mm_par_unite=1.0)
    if unite in MM_PAR_UNITE:
        mm = float(MM_PAR_UNITE[unite])  # type: ignore[index]
        return Tolerances(longueur=1.0 / mm, quantum=_puissance_de_dix(0.001 / mm),
                          mm_par_unite=mm)
    emprise = prims.emprise()
    diagonale = (math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
                 if emprise else 1.0) or 1.0
    return Tolerances(longueur=1e-5 * diagonale, quantum=_puissance_de_dix(1e-8 * diagonale))


def _segments_pour_rectangles(prims: PrimitivesDxf, noeuds: list, entraxe: float | None,
                              tolerances: Tolerances) -> list[Segment]:
    """Les ``LINE`` qui peuvent dessiner un poteau : sur un calque de poteaux, ou
    près d'un nœud de la grille."""
    retenus: list[Segment] = []
    index: IndexSpatial | None = None
    rayon = 0.3 * entraxe if entraxe else 0.0
    if noeuds and rayon > 0:
        index = IndexSpatial(max(rayon, 10.0 * tolerances.longueur))
        for n in noeuds:
            index.ajouter((n.point[0], n.point[1], n.point[0], n.point[1]))
    for s in prims.segments:
        if s.courbe:
            continue
        role = classer(s.calque, s.source.blocs, s.type_ligne).role
        if role == "poteau":
            retenus.append(s)
        elif role == "inconnu" and index is not None and s.longueur <= rayon:
            boite = boite_de((s.a, s.b))
            proches = index.pres_de(boite, marge=rayon)
            if any(distance(s.a, noeuds[i].point) <= rayon
                   and distance(s.b, noeuds[i].point) <= rayon for i in proches):
                retenus.append(s)
    return retenus


def _avec_cotes(poutres: list[Poutre], rattachements: Rattachements) -> list[Poutre]:
    sortie = []
    for poutre in poutres:
        travees = tuple(
            replace(t, cotes=tuple(rattachements.par_travee.get(t.id, ())),
                    confiance=_confiance_cotes(t.confiance, rattachements.par_travee.get(t.id, ())))
            for t in poutre.travees)
        sortie.append(replace(poutre, travees=travees))
    return sortie


def _confiance_cotes(confiance: float, notes: Any) -> float:
    """Une cote concordante ajoute 0,05 ; une cote forcée discordante plafonne à 0,4."""
    notes = list(notes)
    if any(n.discordante for n in notes):
        return round(min(confiance, 0.4), 3)
    if any(n.concordante for n in notes):
        return round(min(confiance + 0.05, 0.9), 3)
    return confiance


def _refus(prims: PrimitivesDxf) -> list[NonResolu]:
    refus: list[NonResolu] = []
    for nom in sorted(set(prims.references_externes)):
        refus.append(NonResolu(f"xref:{nom}", (
            "reference externe non incluse dans ce fichier: son contenu n'est pas lu "
            "(deposer le dessin lie, ou le lier dans le DXF)")))
    arcs_poutre = sum(1 for a in prims.arcs
                      if classer(a.calque, a.source.blocs, a.type_ligne).role == "poutre")
    if arcs_poutre:
        refus.append(NonResolu("arcs", (
            f"{arcs_poutre} arc(s) sur un calque de poutres: poutre courbe non prise en "
            "charge, aucune portee n'en est tiree")))
    if prims.tronquee:
        refus.append(NonResolu("lecture", (
            "lecture arretee a la borne de primitives: le modele est partiel")))
    for element, raison in prims.remarques:
        refus.append(NonResolu(element, raison))
    return refus


def _construire(prims: PrimitivesDxf, declarations: list[Declaration], unites: UnitesDessin
                ) -> ModeleStructurel:
    tol = unites.tolerances
    grille, etiquettes, doutes_axes = detecter_axes(prims, tol)
    lignes = _segments_pour_rectangles(prims, list(grille.noeuds), grille.entraxe_median(), tol)
    formes = formes_fermees(prims, tol, lignes)
    pieux = detecter_pieux(prims, tol, grille, formes)
    poteaux, formes_poteaux, doutes_poteaux, rejets = detecter_poteaux(
        prims, tol, grille, formes, pieux.formes_prises)
    voiles, formes_voiles, segments_voiles = detecter_voiles(
        prims, tol, grille, formes, formes_poteaux | pieux.formes_prises)
    prises = formes_poteaux | formes_voiles | pieux.formes_prises
    refus_feuille: list[NonResolu] = []
    if prims.cadre is not None:
        # UNE FEUILLE PDF NE DIT PAS OÙ SONT LES POUTRES : aucun style n'en est
        # appris, et deux traits parallèles d'un plan d'architecte sont des
        # murs, des marches ou du mobilier. Aucune poutre n'est tirée de la
        # seule forme ; le refus est dit.
        bandes = []
        refus_feuille.append(NonResolu("poutres", (
            "feuille PDF: aucune poutre n'est reconnue par la seule forme (aucun style de "
            "poutre n'est appris de la feuille; deux traits paralleles y sont aussi des "
            "murs, des marches ou du mobilier): aucune portee n'en est tiree")))
    else:
        bandes = detecter_bandes(prims, tol, grille, formes, prises, segments_voiles, poteaux,
                                 voiles)
    poutres, doutes_graphe, compte = construire_poutres(bandes, poteaux, voiles, grille, tol)
    cotes, rattachements = rattacher_cotes(lire_cotes(prims.cotes), grille, poteaux, voiles,
                                           poutres, tol)
    poutres = _avec_cotes(poutres, rattachements)
    poteaux, voiles, poutres, libelles = affecter_libelles(
        prims.textes, poteaux, voiles, poutres, grille, tol, declarations, etiquettes)
    dalles, tremies = detecter_dalles(prims, tol, grille, poteaux, voiles, poutres, formes,
                                      prises)
    niveaux = lire_niveaux(prims)
    compte_rendu: dict[str, Any] = {
        "entities_not_read": dict(sorted(prims.ecartees.items())),
        "external_references": sorted(set(prims.references_externes)),
        "truncated": prims.tronquee,
        "primitives": {"segments": len(prims.segments), "outlines": len(prims.contours),
                       "circles": len(prims.cercles), "arcs": len(prims.arcs),
                       "texts": len(prims.textes), "dimensions": len(prims.cotes),
                       "inserts": len(prims.insertions)},
        "dimension_chains": rattachements.chaines,
        "piles": pieux.compte_rendu,
        "column_candidates_rejected": dict(sorted(rejets.items())),
        **compte,
    }
    modele = ModeleStructurel(
        unites=unites, grille=grille, poteaux=poteaux, pieux=pieux.pieux, voiles=voiles,
        poutres=poutres,
        dalles=dalles, tremies=tremies, cotes=cotes, niveaux=niveaux, libelles=libelles,
        non_resolus=(doutes_axes + doutes_poteaux + doutes_graphe + refus_feuille
                     + _refus(prims)),
        compte_rendu=compte_rendu, absorbees=set(etiquettes) | rattachements.absorbees,
        rattachements=rattachements)
    return modele


def _unites_declarees(prims: PrimitivesDxf, unite: str | None) -> UnitesDessin:
    tol = tolerances_du_dessin(prims, unite)
    if prims.cadre is not None:
        if unite is not None:
            return UnitesDessin(unite, "declaration", "echelle_ecrite_et_cotes", None, tol,
                                prims.origine_unites, prims.cadre)
        return UnitesDessin(None, "absente", None, None, tol, cadre=prims.cadre)
    if unite is not None:
        return UnitesDessin(unite, "declaration", "$INSUNITS", prims.insunits, tol)
    return UnitesDessin(None, "absente", None, prims.insunits, tol)


def _inferer(modele: ModeleStructurel, declarations: list[Declaration]
             ) -> tuple[str, dict[str, Any]] | None:
    declaration = unite_declaree(1, declarations)
    if declaration is None or declaration.unite not in MM_PAR_UNITE:
        return None
    rattachees = [c for c in modele.cotes if c.rattachement is not None]
    concordantes = [c for c in rattachees
                    if c.facteur == 1.0 and not c.discordante
                    and c.valeur_affichee is not None
                    and abs(c.valeur_affichee - c.mesure) <= modele.unites.tolerances.longueur]
    if len(concordantes) < 2 or any(c.discordante or c.facteur != 1.0 for c in rattachees):
        return None
    return declaration.unite, {
        "rule": ("le dessin ne declare pas son unite ($INSUNITS = 0); une mention "
                 "ecrite la donne, et les cotes rattachees affichent leur propre mesure"),
        "declaration": declaration.citation(),
        "dimensions": sorted(c.poignee for c in concordantes)[:20],
    }


def construire_modele(prims: PrimitivesDxf, declarations: list[Declaration]
                      ) -> ModeleStructurel:
    modele = _construire(prims, declarations, _unites_declarees(prims, prims.unites))
    if prims.unites is not None or prims.cadre is not None:
        return modele
    par_mention = _inferer(modele, declarations)
    unite_p, citation_p, refus_p = unite_par_presentation(prims.presentations)
    choix: tuple[str, str, dict[str, Any]] | None = None
    doutes: list[NonResolu] = []
    if par_mention is not None and unite_p is not None and par_mention[0] != unite_p:
        doutes.append(NonResolu("unite", (
            f"la mention ecrite et les cotes donnent {par_mention[0]}, la presentation "
            f"{unite_p}: les deux sources se contredisent, les longueurs restent sans unite")))
    elif unite_p is not None and citation_p is not None:
        citation = dict(citation_p)
        if par_mention is not None:
            citation["confirmed_by_mention"] = par_mention[1]
        choix = (unite_p, "echelle_de_presentation", citation)
    elif par_mention is not None:
        choix = (par_mention[0], "declaration_et_cotes", par_mention[1])
    elif refus_p is not None:
        doutes.append(NonResolu("unite", refus_p))
    if choix is not None:
        unite, source, citation = choix
        tol = tolerances_du_dessin(prims, unite)
        modele = _construire(prims, declarations, UnitesDessin(
            unite, "declaration", source, prims.insunits, tol, citation))
    modele.non_resolus.extend(doutes)
    return modele
