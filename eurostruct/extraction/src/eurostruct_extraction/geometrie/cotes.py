"""Les cotes : ce qu'elles affichent, ce qu'elles mesurent, et à quoi elles se rattachent.

LA VALEUR AFFICHÉE N'EST PAS LA MESURE BRUTE. Une cote affiche
``mesure × DIMLFAC`` — un détail au 1/20 dessiné à l'échelle du plan au 1/50
affiche 30 là où le trait mesure 75. Le lecteur d'entités l'ignorait ; ici,
le facteur est appliqué et cité.

UNE COTE FORCÉE QUI CONTREDIT LE DESSIN EST SIGNALÉE, PAS CORRIGÉE. « 600 »
écrit sur une cote qui mesure 580 est le piège classique d'un plan « hors
échelle » : la mesure géométrique et le texte sont cités côte à côte, la
cote est marquée ``forced_mismatch``, et la proposition qu'elle touche voit
sa confiance plafonnée (interdiction 9 : rien n'est arrondi pour concorder).

UNE COTE RATTACHÉE CORROBORE, ELLE NE PROPOSE PAS. Ses points d'attache sont
accrochés aux axes, aux centres et aux nus des appuis, aux flancs des poutres,
aux faces des poteaux ; la paire d'accroches dit ce qu'elle mesure. Une cote
non rattachée reste une « cote » pour l'extracteur d'entités.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import replace
from typing import Any, Final

from ..nombres import lire_nombre
from .modele import CoteLue, Grille, Poteau, Poutre, RattachementCote, Voile
from .noyau import (
    Point,
    Tolerances,
    angle_deg,
    distance,
    distance_point_droite,
    distance_point_polygone,
    ecart_angulaire,
    normale,
    projeter,
    rectangle_de,
)
from .primitives import CoteDxf

__all__ = ["Rattachements", "lire_cotes", "rattacher_cotes"]

_NOMBRE_SEUL: Final[re.Pattern[str]] = re.compile(
    r"\s*(\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(mm|cm|m)?\s*")
#: Écart angulaire admis pour dire qu'une cote mesure le long d'un élément.
_EQUERRE_COTE: Final[float] = 1.0


def _format(valeur: float) -> str:
    return f"{valeur:.3f}".rstrip("0").rstrip(".")


def _texte_brut(texte: str) -> str:
    try:
        from ezdxf.tools.text import plain_mtext

        return plain_mtext(texte).strip()
    except Exception:  # noqa: BLE001 — un code de mise en forme inconnu: tel quel
        return texte.strip()


def _demi_unite(texte_nombre: str) -> float:
    """La moitié du dernier chiffre écrit : « 600 » → 0,5 ; « 6,05 » → 0,005."""
    decimales = 0
    for separateur in (",", "."):
        if separateur in texte_nombre:
            decimales = len(texte_nombre.split(separateur)[-1])
    return 0.5 * 10 ** (-decimales)


def lire_cotes(cotes: list[CoteDxf]) -> list[CoteLue]:
    lues: list[CoteLue] = []
    for rang, c in enumerate(sorted(cotes, key=lambda x: (x.source.poignee,
                                                          x.p1, x.p2)), start=1):
        if c.genre == "autre" or math.isnan(c.mesure):
            continue
        # LA VALEUR AFFICHÉE D'UNE COTE DE BLOC est sa mesure dans le bloc × DIMLFAC.
        affichable = c.mesure / c.echelle * c.facteur
        texte = _texte_brut(c.texte)
        forcee = discordante = False
        valeur: float | None = affichable
        if texte in ("", "<>"):
            affichee = _format(affichable)
        elif "<>" in texte:
            affichee = texte.replace("<>", _format(affichable))
        else:
            affichee = texte
            # SUR UNE FEUILLE PDF, le nombre écrit EST la cote: il n'en
            # remplace aucune; sa concordance se juge comme celle d'un texte forcé.
            forcee = c.genre != "pdf"
            lu = _NOMBRE_SEUL.fullmatch(texte)
            if lu is None:
                valeur = None
            else:
                valeur = float(lire_nombre(lu.group(1)))
                discordante = abs(valeur - affichable) > _demi_unite(lu.group(1)) + 1e-9
        lues.append(CoteLue(
            id=f"dim:{c.source.poignee or rang}", poignee=c.source.poignee, calque=c.calque,
            p1=c.p1, p2=c.p2, direction=c.direction, mesure=c.mesure, facteur=c.facteur,
            affichee=affichee, valeur_affichee=valeur, forcee=forcee,
            discordante=discordante, ligne=c.ligne))
    return lues


class Rattachements:
    """Ce que chaque élément a reçu comme cotes : travées, entraxes, largeurs…"""

    def __init__(self) -> None:
        self.par_travee: dict[str, list[RattachementCote]] = defaultdict(list)
        self.par_entraxe: dict[tuple[str, str], list[RattachementCote]] = defaultdict(list)
        self.par_extremes: dict[tuple[str, str], list[RattachementCote]] = defaultdict(list)
        self.par_largeur: dict[str, list[RattachementCote]] = defaultdict(list)
        self.par_poteau: dict[str, list[RattachementCote]] = defaultdict(list)
        self.absorbees: set[str] = set()
        #: Les chaînes de cotes, et leur somme comparée à la cote globale.
        self.chaines: list[dict[str, Any]] = []


def _accroches(p: Point, grille: Grille, poteaux: list[Poteau], voiles: list[Voile],
               poutres: list[Poutre], seuil: float) -> list[tuple[str, str, Any]]:
    trouvees: list[tuple[str, str, Any]] = []
    for axe in grille.axes:
        if distance_point_droite(p, axe.origine, axe.direction) <= seuil:
            trouvees.append(("axe", axe.id, None))
    for poteau in poteaux:
        if distance(p, poteau.centre) <= seuil:
            trouvees.append(("centre", poteau.id, None))
        elif distance_point_polygone(p, poteau.contour) <= seuil:
            trouvees.append(("face", poteau.id, None))
    for voile in voiles:
        if distance_point_polygone(p, voile.contour) <= seuil:
            trouvees.append(("face", voile.id, None))
    for poutre in poutres:
        b = poutre.bande
        if b.largeur is None:
            continue
        n = normale(b.direction)
        lateral = (p[0] * n[0] + p[1] * n[1]) - b.decalage
        t = projeter(p, b.origine, b.direction)
        if (abs(abs(lateral) - b.largeur / 2.0) <= seuil
                and b.debut - b.largeur <= t <= b.fin + b.largeur):
            trouvees.append(("flanc", poutre.id, 1 if lateral > 0 else -1))
    return trouvees


def rattacher_cotes(cotes: list[CoteLue], grille: Grille, poteaux: list[Poteau],
                    voiles: list[Voile], poutres: list[Poutre], tolerances: Tolerances
                    ) -> tuple[list[CoteLue], Rattachements]:
    seuil = 5.0 * tolerances.longueur
    r = Rattachements()
    axes = {a.id: a for a in grille.axes}
    rang_dans_famille = {i: (f.index, k) for f in grille.familles
                         for k, i in enumerate(f.axes)}
    sortie: list[CoteLue] = []
    for cote in cotes:
        angle_cote = angle_deg(cote.direction)
        h1 = _accroches(cote.p1, grille, poteaux, voiles, poutres, seuil)
        h2 = _accroches(cote.p2, grille, poteaux, voiles, poutres, seuil)
        rattachement: dict[str, Any] | None = None
        concordante: bool | None = None
        aussi: list[str] = []

        def noter(mesure_de: str, valeur: float, cote: CoteLue = cote) -> RattachementCote:
            return RattachementCote(cote.poignee, mesure_de, cote.mesure, cote.affichee,
                                    abs(cote.mesure - valeur) <= tolerances.longueur,
                                    cote.discordante)

        # 1. UN ENTRAXE: deux axes de la meme famille, mesure perpendiculaire.
        axes1 = [x[1] for x in h1 if x[0] == "axe"]
        axes2 = [x[1] for x in h2 if x[0] == "axe"]
        for a1 in axes1:
            for a2 in axes2:
                if a1 == a2 or a1 not in rang_dans_famille or a2 not in rang_dans_famille:
                    continue
                f1, k1 = rang_dans_famille[a1]
                f2, k2 = rang_dans_famille[a2]
                famille_angle = grille.familles[f1].angle
                if f1 != f2 or ecart_angulaire(angle_cote, famille_angle) < 90.0 - _EQUERRE_COTE:
                    continue
                bas, haut = (a1, a2) if k1 < k2 else (a2, a1)
                valeur = abs(axes[haut].decalage - axes[bas].decalage)
                note = noter("grid_spacing" if abs(k1 - k2) == 1 else "grid_extent", valeur)
                cible = r.par_entraxe if abs(k1 - k2) == 1 else r.par_extremes
                cible[(bas, haut)].append(note)
                rattachement = {"type": note.mesure_de, "refs": [bas, haut]}
                concordante = note.concordante
        # 2. UNE TRAVEE: entre-axes ou nu a nu, le long de la poutre.
        for poutre in poutres:
            b = poutre.bande
            if ecart_angulaire(angle_cote, angle_deg(b.direction)) > _EQUERRE_COTE:
                continue
            t1 = projeter(cote.p1, b.origine, b.direction)
            t2 = projeter(cote.p2, b.origine, b.direction)
            t_bas, t_haut = min(t1, t2), max(t1, t2)
            bas_h, haut_h = (h1, h2) if t1 <= t2 else (h2, h1)
            for travee in poutre.travees:
                if travee.debut is None or travee.fin is None:
                    continue
                s1, s2 = travee.debut, travee.fin
                au_centre = (abs(t_bas - s1.centre) <= seuil and abs(t_haut - s2.centre) <= seuil
                             and any(x[0] in ("axe", "centre") for x in bas_h)
                             and any(x[0] in ("axe", "centre") for x in haut_h))
                aux_nus = (abs(t_bas - s1.faces[1]) <= seuil and abs(t_haut - s2.faces[0]) <= seuil
                           and any(x[0] == "face" and x[1] == s1.element for x in bas_h)
                           and any(x[0] == "face" and x[1] == s2.element for x in haut_h))
                if au_centre and travee.entre_axes is not None:
                    note = noter("axis_length", travee.entre_axes)
                    r.par_travee[travee.id].append(note)
                    aussi.append(travee.id)
                    if rattachement is None:
                        rattachement = {"type": "axis_length", "refs": [travee.id]}
                        concordante = note.concordante
                elif aux_nus and travee.nu_a_nu is not None:
                    note = noter("clear_length", travee.nu_a_nu)
                    r.par_travee[travee.id].append(note)
                    aussi.append(travee.id)
                    if rattachement is None:
                        rattachement = {"type": "clear_length", "refs": [travee.id]}
                        concordante = note.concordante
        # 3. UNE LARGEUR DE POUTRE: les deux flancs, mesure perpendiculaire.
        for x1 in h1:
            for x2 in h2:
                if (x1[0] == x2[0] == "flanc" and x1[1] == x2[1] and x1[2] != x2[2]):
                    poutre = next(p for p in poutres if p.id == x1[1])
                    b = poutre.bande
                    if (b.largeur is None or ecart_angulaire(angle_cote, angle_deg(b.direction))
                            < 90.0 - _EQUERRE_COTE):
                        continue
                    note = noter("beam_width", b.largeur)
                    r.par_largeur[poutre.id].append(note)
                    rattachement = rattachement or {"type": "beam_width", "refs": [poutre.id]}
                    concordante = note.concordante if concordante is None else concordante
        # 4. UN COTE DE POTEAU: deux faces du même poteau, le long d'un côté.
        for x1 in h1:
            for x2 in h2:
                if not (x1[0] == x2[0] == "face" and x1[1] == x2[1]):
                    continue
                poteau = next((p for p in poteaux if p.id == x1[1]), None)
                if poteau is None or poteau.forme != "rectangle":
                    continue
                rect = rectangle_de(poteau.contour, tolerances)
                if rect is None:
                    continue
                for longueur, direction in ((rect.longueur_u, rect.u), (rect.longueur_v, rect.v)):
                    if ecart_angulaire(angle_cote, angle_deg(direction)) <= _EQUERRE_COTE:
                        note = noter("column_side", longueur)
                        r.par_poteau[poteau.id].append(note)
                        rattachement = rattachement or {"type": "column_side",
                                                        "refs": [poteau.id]}
                        concordante = note.concordante if concordante is None else concordante
        if rattachement is not None:
            if aussi:
                rattachement = {**rattachement, "also": sorted(set(aussi))}
            r.absorbees.add(cote.poignee)
        sortie.append(replace(cote, rattachement=rattachement, concordante=concordante))

    # LES CHAINES: même direction, même ligne de cote.
    groupes: dict[tuple[int, int], list[int]] = defaultdict(list)
    pas_angle = tolerances.parallele_deg
    for i, cote in enumerate(sortie):
        n = normale(cote.direction)
        point = cote.ligne or cote.p1
        ligne = point[0] * n[0] + point[1] * n[1]
        if cote.rattachement is None:
            continue
        cle = (int(round(angle_deg(cote.direction) / pas_angle)),
               int(round(ligne / max(seuil, 1e-12))))
        groupes[cle].append(i)
    numero = 0
    for cle in sorted(groupes):
        membres = groupes[cle]
        if len(membres) < 2:
            continue
        numero += 1
        for i in membres:
            sortie[i] = replace(sortie[i], chaine=f"chain:{numero}")
        r.chaines.append(_somme_de_chaine(f"chain:{numero}", [sortie[i] for i in membres],
                                          sortie, seuil, tolerances))
    return sortie, r


def _somme_de_chaine(nom: str, membres: list[CoteLue], toutes: list[CoteLue],
                     seuil: float, tolerances: Tolerances) -> dict[str, Any]:
    """La somme des partielles, comparée à une cote globale de même étendue."""
    d = membres[0].direction
    origine = (0.0, 0.0)
    intervalles = [sorted((projeter(c.p1, origine, d), projeter(c.p2, origine, d)))
                   for c in membres]
    debut, fin = min(i[0] for i in intervalles), max(i[1] for i in intervalles)
    somme = sum(c.mesure for c in membres)
    resume: dict[str, Any] = {"chain": nom, "dimensions": [c.poignee for c in membres],
                              "sum": somme}
    for autre in toutes:
        if autre in membres or ecart_angulaire(angle_deg(autre.direction), angle_deg(d)) > 1.0:
            continue
        a, b = sorted((projeter(autre.p1, origine, d), projeter(autre.p2, origine, d)))
        if abs(a - debut) <= seuil and abs(b - fin) <= seuil:
            resume["total"] = {"handle": autre.poignee, "measured": autre.mesure,
                               "agrees": abs(autre.mesure - somme) <= tolerances.longueur}
            break
    return resume
