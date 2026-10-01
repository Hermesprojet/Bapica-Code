"""Les poutres en plan : des bandes — un axe, une largeur, une étendue.

TROIS DESSINS, UNE MÊME BANDE
------------------------------
* un RECTANGLE allongé (élancement ≥ 2 sur un calque de poutre, ≥ 3 ailleurs) ;
* deux TRAITS PARALLÈLES appariés mutuellement (``appariement.py``) ;
* un trait SEUL sur un calque de poutre (plans de charpente) : une poutre
  « filaire », dont la largeur n'est pas dessinée — utilisable pour les portées,
  jamais pour une largeur.

SUR UN CALQUE GÉNÉRIQUE, UNE BANDE N'EST QU'UNE CANDIDATE (``provisoire``) :
elle ne devient poutre que si elle touche au moins deux appuis (graphe.py). Un
rectangle de coupe, un cartouche ou une trémie ne touchent pas deux poteaux.

UNE POUTRE DESSINÉE INTERROMPUE AUX POTEAUX EST UNE SEULE POUTRE : deux bandes
colinéaires de même largeur, séparées par un intervalle entièrement couvert
par un appui, sont fusionnées — et l'appui est cité dans ``fusions``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Final

from .appariement import apparier, orienter
from .classification import Classement, classer
from .modele import Bande, Grille, Poteau, Preuve, Voile, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    angle_deg,
    boite_de,
    decouper_par_bande,
    ecart_angulaire,
    intervalle_projete,
    normale,
    rectangle_de,
)
from .poteaux import Forme
from .primitives import Primitive, PrimitivesDxf, Segment

__all__ = ["detecter_bandes", "intervalle_sur_bande"]

LARGEUR_MIN_MM: Final[float] = 80.0
LARGEUR_MAX_MM: Final[float] = 1500.0

#: Ce qu'une bande ne peut jamais être.
_EXCLUS: Final[frozenset[str]] = frozenset(
    {"axe", "cote", "texte", "niveau", "armature", "cadre", "tremie", "dalle", "voile",
     "poteau", "hachure"})


def intervalle_sur_bande(points: tuple[Point, ...], origine: Point, u: Point,
                         demi_largeur: float, *, couverture_min: float = 0.5
                         ) -> tuple[float, float] | None:
    """L'intervalle qu'un contour occupe le long d'une bande — ou ``None``.

    Le contour est découpé par la bande ; il faut qu'il en couvre au moins
    ``couverture_min`` de la largeur (un poteau qui ne fait qu'effleurer le
    flanc d'une poutre n'est pas son appui).
    """
    n = normale(u)
    decoupe = decouper_par_bande(points, origine, n, demi_largeur)
    if len(decoupe) < 3:
        return None
    a_n, c_n = intervalle_projete(decoupe, origine, n)
    if (c_n - a_n) < couverture_min * 2.0 * demi_largeur:
        return None
    return intervalle_projete(decoupe, origine, u)


@dataclass
class _Brute:
    theta: float
    u: Point
    decalage: float
    largeur: float | None
    debut: float
    fin: float
    primitives: list[Primitive]
    regle: str
    motif: str | None
    confiance: float
    dessin: str
    provisoire: bool
    fusions: list[str] = field(default_factory=list)

    @property
    def origine(self) -> Point:
        n = normale(self.u)
        return (self.decalage * n[0], self.decalage * n[1])


def _bornes(tolerances: Tolerances, entraxe: float | None, diagonale: float,
            role_poutre: bool) -> tuple[float, float] | None:
    if tolerances.mm_par_unite:
        return (LARGEUR_MIN_MM / tolerances.mm_par_unite,
                LARGEUR_MAX_MM / tolerances.mm_par_unite)
    if entraxe:
        return (0.005 * entraxe, 0.25 * entraxe)
    if role_poutre:
        return (10.0 * tolerances.longueur, 0.05 * diagonale)
    return None


def _depuis_rectangle(forme: Forme, tolerances: Tolerances, regle: str,
                      motif: str | None, confiance: float, provisoire: bool) -> _Brute | None:
    rect = rectangle_de(forme.points, tolerances)
    if rect is None:
        return None
    longue = rect.direction_longue()
    theta = angle_deg(longue)
    if theta > 180.0 - tolerances.parallele_deg:
        theta -= 180.0
    rad = math.radians(theta)
    u = (math.cos(rad), math.sin(rad))
    n = normale(u)
    t_centre = rect.centre[0] * u[0] + rect.centre[1] * u[1]
    demi = rect.grand_cote / 2.0
    return _Brute(theta, u, rect.centre[0] * n[0] + rect.centre[1] * n[1], rect.petit_cote,
                  t_centre - demi, t_centre + demi, list(forme.primitives), regle, motif,
                  confiance, "rectangle", provisoire)


def detecter_bandes(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                    formes: list[Forme], formes_prises: set[int],
                    segments_pris: set[int], poteaux: list[Poteau],
                    voiles: list[Voile]) -> list[Bande]:
    entraxe = grille.entraxe_median()
    emprise = prims.emprise()
    diagonale = (math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
                 if emprise else 1.0)
    brutes: list[_Brute] = []
    # LES TRAITS D'UN CONTOUR DEJA RECONNU (poteau, voile, poutre-rectangle) ne
    # sont pas des faces de poutre: on les retire de l'appariement.
    sources_prises: set[tuple[str, tuple[str, ...]]] = set()
    for rang in formes_prises:
        sources_prises.update(p.source.cle for p in formes[rang].primitives)

    for rang, forme in enumerate(formes):
        if rang in formes_prises or forme.genre != "rectangle":
            continue
        classement: Classement = forme.classement
        rect = rectangle_de(forme.points, tolerances)
        if rect is None:
            continue
        brute: _Brute | None = None
        if classement.role == "poutre" and rect.elancement >= 2.0:
            brute = _depuis_rectangle(forme, tolerances, classement.regle, classement.motif,
                                      0.8, False)
        elif classement.role == "inconnu" and not forme.rempli and rect.elancement >= 3.0:
            bornes = _bornes(tolerances, entraxe, diagonale, False)
            if bornes and bornes[0] <= rect.petit_cote <= bornes[1]:
                regle = "type_de_ligne" if classement.cache else "forme"
                brute = _depuis_rectangle(forme, tolerances, regle, None,
                                          0.7 if classement.cache else 0.6, True)
        if brute is not None:
            brutes.append(brute)
            sources_prises.update(p.source.cle for p in forme.primitives)

    # DEUX TRAITS PARALLELES.
    par_role: dict[str, list[Segment]] = {"poutre": [], "inconnu": [], "cache": []}
    for s in prims.segments:
        if s.courbe or id(s) in segments_pris or s.source.cle in sources_prises:
            continue
        classement = classer(s.calque, s.source.blocs, s.type_ligne)
        if classement.role in _EXCLUS:
            continue
        if classement.role == "poutre":
            par_role["poutre"].append(s)
        elif classement.cache:
            par_role["cache"].append(s)
        else:
            par_role["inconnu"].append(s)
    apparies: set[int] = set()
    for role, segments in par_role.items():
        bornes = _bornes(tolerances, entraxe, diagonale, role == "poutre")
        if not segments or bornes is None:
            continue
        for paire in apparier(segments, tolerances, largeur_min=bornes[0],
                              largeur_max=bornes[1]):
            if paire.fin - paire.debut < 2.0 * paire.largeur:
                continue
            premier = paire.segments[0]
            classement = classer(premier.calque, premier.source.blocs, premier.type_ligne)
            if role == "poutre":
                regle, motif, confiance, provisoire = (classement.regle, classement.motif,
                                                       0.8, False)
            elif role == "cache":
                regle, motif, confiance, provisoire = "type_de_ligne", premier.type_ligne, 0.7, True
            else:
                regle, motif, confiance, provisoire = "forme", None, 0.6, True
            brutes.append(_Brute(paire.theta, paire.u, paire.decalage, paire.largeur,
                                 paire.debut, paire.fin, list(paire.segments), regle, motif,
                                 confiance, "paire_de_traits", provisoire))
            apparies.update(id(s) for s in paire.segments)

    # LA POUTRE FILAIRE: un trait seul, sur un calque de poutre.
    seuil_filaire = max(20.0 * tolerances.longueur, 0.02 * diagonale)
    for s in par_role["poutre"]:
        if id(s) in apparies or s.longueur < seuil_filaire:
            continue
        trait = orienter(s, tolerances)
        if trait is None:
            continue
        classement = classer(s.calque, s.source.blocs, s.type_ligne)
        brutes.append(_Brute(trait.theta, trait.u, trait.decalage, None, trait.debut,
                             trait.fin, [s], classement.regle, classement.motif, 0.7,
                             "filaire", False))

    fusionnees = _fusionner(brutes, tolerances, poteaux, voiles)
    fusionnees.sort(key=lambda b: (round(b.theta, 3), round(b.decalage, 6), round(b.debut, 6)))
    bandes: list[Bande] = []
    for rang, b in enumerate(fusionnees, start=1):
        preuve: Preuve = preuve_de(b.primitives, b.regle, b.motif)
        bandes.append(Bande(id=f"beam:{rang}", origine=b.origine, direction=b.u,
                            decalage=b.decalage, largeur=b.largeur, debut=b.debut, fin=b.fin,
                            preuve=preuve, confiance=b.confiance, dessin=b.dessin,
                            provisoire=b.provisoire, fusions=tuple(b.fusions)))
    return bandes


def _couvert_par_appui(b: _Brute, debut: float, fin: float, tolerances: Tolerances,
                       appuis: list[tuple[str, tuple[Point, ...]]], index: IndexSpatial
                       ) -> str | None:
    """L'appui qui couvre l'intervalle ``[debut, fin]`` le long de la bande.
    Seuls les appuis qui touchent la boîte de l'intervalle sont examinés."""
    demi = (b.largeur or 0.0) / 2.0 + tolerances.longueur
    n = normale(b.u)
    o = b.origine
    coins = [(o[0] + t * b.u[0] + s * demi * n[0], o[1] + t * b.u[1] + s * demi * n[1])
             for t in (debut, fin) for s in (-1.0, 1.0)]
    for rang in index.pres_de(boite_de(coins), marge=tolerances.longueur):
        element_id, contour = appuis[rang]
        intervalle = intervalle_sur_bande(contour, b.origine, b.u, demi)
        if intervalle is None:
            continue
        a, c = intervalle
        if a <= debut + tolerances.longueur and c >= fin - tolerances.longueur:
            return element_id
    return None


def _fusionner(brutes: list[_Brute], tolerances: Tolerances, poteaux: list[Poteau],
               voiles: list[Voile]) -> list[_Brute]:
    groupes: list[list[_Brute]] = []
    for b in sorted(brutes, key=lambda x: (round(x.theta, 3), x.decalage, x.debut)):
        for groupe in groupes:
            g = groupe[0]
            meme_largeur = ((b.largeur is None and g.largeur is None)
                            or (b.largeur is not None and g.largeur is not None
                                and abs(b.largeur - g.largeur) <= 2.0 * tolerances.longueur))
            if (ecart_angulaire(g.theta, b.theta) <= tolerances.parallele_deg
                    and abs(g.decalage - b.decalage) <= 2.0 * tolerances.longueur
                    and meme_largeur):
                groupe.append(b)
                break
        else:
            groupes.append([b])

    appuis = [(p.id, p.contour) for p in poteaux] + [(v.id, v.contour) for v in voiles]
    boites = [boite_de(contour) for _, contour in appuis]
    index = IndexSpatial(max((max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in boites),
                             default=0.0) * 4.0 or 1.0)
    for boite in boites:
        index.ajouter(boite)

    sortie: list[_Brute] = []
    for groupe in groupes:
        groupe.sort(key=lambda x: x.debut)
        courante = replace(groupe[0], primitives=list(groupe[0].primitives),
                           fusions=list(groupe[0].fusions))
        for b in groupe[1:]:
            ecart = b.debut - courante.fin
            appui = None
            if ecart > 2.0 * tolerances.longueur:
                appui = _couvert_par_appui(courante, courante.fin, b.debut, tolerances,
                                           appuis, index)
                if appui is None:
                    sortie.append(courante)
                    courante = replace(b, primitives=list(b.primitives), fusions=list(b.fusions))
                    continue
            courante.fin = max(courante.fin, b.fin)
            courante.primitives.extend(b.primitives)
            courante.confiance = min(courante.confiance, b.confiance)
            courante.provisoire = courante.provisoire and b.provisoire
            if b.regle != courante.regle and b.regle in ("bloc", "calque"):
                courante.regle, courante.motif = b.regle, b.motif
            if appui is not None:
                courante.fusions.append(appui)
        sortie.append(courante)
    return sortie
