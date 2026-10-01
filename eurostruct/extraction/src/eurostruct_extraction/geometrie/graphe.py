"""Le graphe structurel : les appuis de chaque poutre, ses travées, ses consoles.

LES APPUIS D'UNE POUTRE
------------------------
Pour une bande d'axe ``o + t·u``, de largeur ``b`` et d'étendue ``[t₀, t₁]`` :

1. un POTEAU ou un VOILE est un appui si son contour, découpé par la bande,
   en couvre au moins la moitié de la largeur et se trouve dans l'étendue
   prolongée de ``e = max(2 tolérances, 0,1·b)`` à chaque bout (un trait qui
   s'arrête à 1 cm du nu touche son appui). La projection de la découpe sur
   ``u`` donne les NUS ``[a, c]`` ; le centre est celui du poteau, ou l'axe du
   voile traversant ;
2. une autre POUTRE ``Q`` (à 30° au moins) est un appui si l'intersection des
   axes est à une EXTRÉMITÉ de la poutre et À L'INTÉRIEUR de ``Q`` : jonction
   en T, ``Q`` continue, la poutre s'y arrête. Intérieure aux deux : un
   croisement, aucune ne porte l'autre. Extrémité des deux : un angle sans
   appui, signalé ;
3. deux appuis qui se recouvrent n'en font qu'un ; le poteau prime.

LES TRAVÉES
-----------
Entre deux appuis consécutifs ``Sᵢ``, ``Sᵢ₊₁`` :

    entre-axes  L  = centre(Sᵢ₊₁) − centre(Sᵢ)
    nu à nu     Lₙ = a(Sᵢ₊₁) − c(Sᵢ)

Un dépassement au-delà du premier ou du dernier appui est une CONSOLE.

CE QUI N'EST PAS CALCULÉ EST DIT. Une poutre sans appui n'a pas de portée ;
deux appuis qui se recouvrent ne donnent pas de travée ; une bande d'un calque
générique qui ne touche pas deux appuis n'est pas une poutre. Chaque cas va
dans ``non_resolus``, avec sa raison.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from .modele import Appui, Bande, Grille, NonResolu, Poteau, Poutre, Travee, Voile
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    angle_deg,
    boite_de,
    distance,
    ecart_angulaire,
    intersection_droites,
    projeter,
    unitaire,
)
from .poutres import intervalle_sur_bande

__all__ = ["construire_poutres"]

#: En dessous, deux poutres ne se portent pas : elles sont presque parallèles.
ANGLE_PORTEUSE_MIN: Final[float] = 30.0
_PRIORITE: Final[dict[str, int]] = {"poteau": 0, "voile": 1, "poutre": 2}


@dataclass(frozen=True)
class _Support:
    ident: str
    genre: str
    contour: tuple[Point, ...]
    centre: Point
    confiance: float
    noeud: str | None
    #: Direction de l'axe d'un voile (pour écarter un voile parallèle).
    direction_voile: float | None = None


def _extension(bande: Bande, tolerances: Tolerances) -> float:
    return max(2.0 * tolerances.longueur, 0.1 * (bande.largeur or 0.0))


def _demi_largeur(bande: Bande, tolerances: Tolerances) -> float:
    if bande.largeur is None:
        # UNE POUTRE FILAIRE: l'axe seul. La bande de recherche est étroite.
        return 5.0 * tolerances.longueur
    return bande.largeur / 2.0 + tolerances.longueur


def _appuis_verticaux(bande: Bande, index: IndexSpatial, supports: list[_Support],
                      tolerances: Tolerances) -> list[tuple[Appui, float]]:
    e = _extension(bande, tolerances)
    demi = _demi_largeur(bande, tolerances)
    a0, a1 = bande.point(bande.debut - e), bande.point(bande.fin + e)
    boite = boite_de((a0, a1))
    trouves: list[tuple[Appui, float]] = []
    for rang in index.pres_de(boite, marge=demi + e):
        support = supports[rang]
        # UN VOILE PARALLELE N'EST PAS UN APPUI: la poutre le longe.
        if (support.genre == "voile" and support.direction_voile is not None
                and ecart_angulaire(support.direction_voile, angle_deg(bande.direction))
                < ANGLE_PORTEUSE_MIN):
            continue
        intervalle = intervalle_sur_bande(support.contour, bande.origine, bande.direction, demi)
        if intervalle is None:
            continue
        a, c = intervalle
        if c < bande.debut - e or a > bande.fin + e:
            continue
        if support.genre == "poteau":
            centre = projeter(support.centre, bande.origine, bande.direction)
        else:
            centre = (a + c) / 2.0
        ecart = max(0.0, bande.debut - c, a - bande.fin)
        contact = c <= bande.debut + tolerances.longueur or a >= bande.fin - tolerances.longueur
        trouves.append((Appui(support.ident, support.genre, centre, (a, c), support.noeud,
                              contact, ecart), support.confiance))
    return trouves


def _jonctions(bande: Bande, autres: list[Bande], tolerances: Tolerances, grille: Grille
               ) -> tuple[list[tuple[Appui, float]], list[str]]:
    """Les poutres qui portent celle-ci (jonction en T), et celles qu'elle croise."""
    portees: list[tuple[Appui, float]] = []
    croisees: list[str] = []
    e = _extension(bande, tolerances)
    for q in autres:
        if q.id == bande.id:
            continue
        ecart = ecart_angulaire(angle_deg(bande.direction), angle_deg(q.direction))
        if ecart < ANGLE_PORTEUSE_MIN:
            continue
        j = intersection_droites(bande.origine, bande.direction, q.origine, q.direction)
        if j is None:
            continue
        t_p = projeter(j, bande.origine, bande.direction)
        t_q = projeter(j, q.origine, q.direction)
        sinus = math.sin(math.radians(ecart))
        demi_q = ((q.largeur or 0.0) / 2.0) / sinus
        demi_p = ((bande.largeur or 0.0) / 2.0) / sinus
        pres_debut = abs(t_p - bande.debut) <= demi_q + e
        pres_fin = abs(t_p - bande.fin) <= demi_q + e
        interieur_p = bande.debut + demi_q + e < t_p < bande.fin - demi_q - e
        interieur_q = (q.debut + demi_p + tolerances.longueur < t_q
                       < q.fin - demi_p - tolerances.longueur)
        dans_q = q.debut - tolerances.longueur <= t_q <= q.fin + tolerances.longueur
        if (pres_debut or pres_fin) and interieur_q:
            noeud = None
            for n in grille.noeuds:
                if distance(n.point, j) <= max(demi_q, 5.0 * tolerances.longueur):
                    noeud = n.nom
                    break
            portees.append((Appui(q.id, "poutre", t_p, (t_p - demi_q, t_p + demi_q), noeud,
                                  contact=True, ecart=0.0), 0.9 * q.confiance))
        elif interieur_p and interieur_q:
            croisees.append(q.id)
        elif (pres_debut or pres_fin) and dans_q and not interieur_q:
            croisees.append(f"angle:{q.id}")
    return portees, croisees


def _fusionner_appuis(appuis: list[tuple[Appui, float]], tolerances: Tolerances
                      ) -> list[tuple[Appui, float]]:
    """Deux appuis qui se recouvrent le long de la poutre n'en font qu'un."""
    tries = sorted(appuis, key=lambda x: (x[0].faces[0], _PRIORITE[x[0].genre]))
    sortie: list[tuple[Appui, float]] = []
    for appui, confiance in tries:
        if sortie:
            dernier, conf_dernier = sortie[-1]
            if appui.faces[0] <= dernier.faces[1] - tolerances.longueur:
                if _PRIORITE[appui.genre] < _PRIORITE[dernier.genre]:
                    sortie[-1] = (appui, confiance)
                continue
        sortie.append((appui, confiance))
    return sortie


def _travees(bande: Bande, appuis: list[tuple[Appui, float]], tolerances: Tolerances
             ) -> tuple[list[Travee], list[NonResolu]]:
    travees: list[Travee] = []
    doutes: list[NonResolu] = []
    numero = int(bande.id.split(":")[1]) if ":" in bande.id else 0
    portees: list[tuple[Appui, Appui, float]] = []
    for (s1, c1), (s2, c2) in zip(appuis, appuis[1:], strict=False):
        nu = s2.faces[0] - s1.faces[1]
        if nu <= tolerances.longueur:
            doutes.append(NonResolu(bande.id, (
                f"appuis {s1.element} et {s2.element} qui se recouvrent: aucune "
                "portee n'est mesuree entre eux")))
            continue
        portees.append((s1, s2, min(bande.confiance, c1, c2)))
    nombre = len(portees)
    for index, (s1, s2, confiance) in enumerate(portees, start=1):
        travees.append(Travee(
            id=f"span:{numero}.{index}", poutre=bande.id, index=index, nombre=nombre,
            genre="travee", debut=s1, fin=s2, entre_axes=s2.centre - s1.centre,
            nu_a_nu=s2.faces[0] - s1.faces[1], confiance=round(confiance, 3)))
    if appuis:
        premier, conf_premier = appuis[0]
        dernier, conf_dernier = appuis[-1]
        if bande.debut < premier.faces[0] - tolerances.longueur:
            travees.insert(0, Travee(
                id=f"cantilever:{numero}.debut", poutre=bande.id, index=0, nombre=nombre,
                genre="console", debut=None, fin=premier,
                entre_axes=premier.centre - bande.debut, nu_a_nu=premier.faces[0] - bande.debut,
                confiance=round(max(0.05, min(bande.confiance, conf_premier) - 0.05), 3)))
        if bande.fin > dernier.faces[1] + tolerances.longueur:
            travees.append(Travee(
                id=f"cantilever:{numero}.fin", poutre=bande.id, index=nombre + 1,
                nombre=nombre, genre="console", debut=dernier, fin=None,
                entre_axes=bande.fin - dernier.centre, nu_a_nu=bande.fin - dernier.faces[1],
                confiance=round(max(0.05, min(bande.confiance, conf_dernier) - 0.05), 3)))
    return travees, doutes


def construire_poutres(bandes: list[Bande], poteaux: list[Poteau], voiles: list[Voile],
                       grille: Grille, tolerances: Tolerances
                       ) -> tuple[list[Poutre], list[NonResolu], dict[str, int]]:
    """Les poutres retenues, les doutes, et le compte des bandes écartées."""
    supports: list[_Support] = []
    for p in poteaux:
        supports.append(_Support(p.id, "poteau", p.contour, p.centre, p.confiance, p.noeud))
    for v in voiles:
        direction = None
        if v.axe is not None:
            u = unitaire(v.axe[0], v.axe[1])
            direction = angle_deg(u) if u else None
        centre = ((v.axe[0][0] + v.axe[1][0]) / 2.0, (v.axe[0][1] + v.axe[1][1]) / 2.0) \
            if v.axe else v.contour[0]
        supports.append(_Support(v.id, "voile", v.contour, centre, v.confiance, None, direction))

    emprise_tout = [pt for s in supports for pt in s.contour] or [(0.0, 0.0), (1.0, 1.0)]
    x0, y0, x1, y1 = boite_de(emprise_tout)
    case = max((grille.entraxe_median() or 0.0) / 2.0, math.hypot(x1 - x0, y1 - y0) / 50.0,
               10.0 * tolerances.longueur)
    index = IndexSpatial(case)
    for s in supports:
        index.ajouter(boite_de(s.contour))

    verticaux = {b.id: _appuis_verticaux(b, index, supports, tolerances) for b in bandes}
    # PREMIER PASSAGE: une bande devient poutre par ses appuis verticaux (ou
    # parce que son calque le dit).
    retenues = [b for b in bandes if not b.provisoire or len(verticaux[b.id]) >= 2]
    # SECOND PASSAGE: les jonctions en T, contre les poutres retenues. Une
    # bande candidate portée par une poutre et un poteau devient une poutre
    # secondaire.
    poutres: list[Poutre] = []
    doutes: list[NonResolu] = []
    ecartees = 0
    jonctions = {b.id: _jonctions(b, retenues, tolerances, grille) for b in bandes}
    for bande in bandes:
        portees, croisees = jonctions[bande.id]
        appuis = verticaux[bande.id] + portees
        if bande.provisoire and len(_fusionner_appuis(appuis, tolerances)) < 2:
            ecartees += 1
            continue
        appuis = _fusionner_appuis(appuis, tolerances)
        if not appuis:
            doutes.append(NonResolu(bande.id, (
                "aucun appui trouve (poteau, voile ou poutre porteuse): aucune "
                "portee n'est mesuree")))
            poutres.append(Poutre(bande.id, bande, (), (), bande.confiance))
            continue
        travees, doutes_travees = _travees(bande, appuis, tolerances)
        doutes.extend(doutes_travees)
        if len(appuis) == 1:
            doutes.append(NonResolu(bande.id, (
                f"un seul appui ({appuis[0][0].element}): seules les consoles sont "
                "mesurees")))
        for angle in (c for c in croisees if c.startswith("angle:")):
            doutes.append(NonResolu(bande.id, (
                f"angle sans appui avec {angle.split(':', 1)[1]}: aucun poteau ni "
                "voile sous la jonction")))
        portee_par = tuple(sorted({a.element for a, _ in appuis if a.genre == "poutre"}))
        poutres.append(Poutre(bande.id, replace(bande, provisoire=False),
                              tuple(a for a, _ in appuis), tuple(travees), bande.confiance,
                              portee_par=portee_par))
    return poutres, doutes, {"candidate_bands_rejected": ecartees}
