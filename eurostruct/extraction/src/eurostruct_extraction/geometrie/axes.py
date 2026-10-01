"""Les files : axes de la grille, leurs étiquettes, leurs familles, leurs nœuds.

UN AXE EST UNE DROITE, PAS UN TRAIT. Un axe dessiné en trois morceaux reste un
axe ; deux axes parallèles à 600 cm l'un de l'autre sont à 600 cm partout —
c'est la distance entre deux droites parallèles, exacte, que l'entraxe cite.

L'ÉTIQUETTE EST LUE LÀ OÙ LE DESSIN LA MET : dans une bulle (cercle centré sur
le prolongement de l'axe), dans un bloc de bulle (attribut), ou dans un texte
court posé dans le prolongement. Deux extrémités qui portent deux étiquettes
différentes ne sont pas départagées : l'axe reste sans étiquette, et c'est
signalé.

GRILLE POLAIRE OU COURBE : non prise en charge. Seules les droites sont des
axes ; trois directions ou plus portant chacune UN axe, concourants en un même
point, sont une grille rayonnante : elle est nommée dans ``unresolved`` et ses
axes sont écartés — ni files, ni nœuds, ni étiquettes absorbées.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Final

from .classification import classer, role_du_nom
from .modele import Axe, Famille, Grille, Noeud, NonResolu, preuve_de
from .noyau import (
    Point,
    Tolerances,
    angle_deg,
    distance,
    distance_point_droite,
    ecart_angulaire,
    intersection_droites,
    normale,
    projeter,
    unitaire,
)
from .primitives import Insertion, PrimitivesDxf, Segment, Texte

__all__ = ["ETIQUETTE_AXE", "detecter_axes"]

#: « A », « AA », « A' », « 1 », « 12 », « 1' » — et rien de plus long.
ETIQUETTE_AXE: Final[re.Pattern[str]] = re.compile(r"[A-Z]{1,2}'?|\d{1,3}'?")

#: Ecart angulaire minimal entre deux familles pour qu'elles se croisent.
_ANGLE_FAMILLES_MIN: Final[float] = 10.0


@dataclass
class _Ligne:
    theta: float
    u: Point
    decalage: float
    debut: float
    fin: float
    segments: list[Segment] = field(default_factory=list)
    regle: str = "calque"
    motif: str | None = None


def _direction_canonique(a: Point, b: Point, tolerances: Tolerances) -> tuple[float, Point] | None:
    u = unitaire(a, b)
    if u is None:
        return None
    theta = angle_deg(u)
    # UNE DROITE A 179,9° EST LA MEME QU'A -0,1°: on ramene le voisinage de
    # 180° pres de 0, pour que deux morceaux d'un même axe se retrouvent.
    if theta > 180.0 - tolerances.parallele_deg:
        theta -= 180.0
    rad = math.radians(theta)
    return theta, (math.cos(rad), math.sin(rad))


def _lignes_candidates(prims: PrimitivesDxf, tolerances: Tolerances,
                       diagonale: float) -> list[_Ligne]:
    lignes: list[_Ligne] = []
    for s in prims.segments:
        if s.courbe:
            continue
        classement = classer(s.calque, s.source.blocs, s.type_ligne)
        if classement.role != "axe":
            continue
        # UN AXE D'UNE FEUILLE PDF (règle « style ») est déjà reconstitué depuis
        # sa bulle et borné en longueur par le lecteur: le cartouche agrandit
        # l'emprise, et un dixième de la feuille écarterait les axes courts.
        seuil = (0.3 * diagonale if classement.regle == "type_de_ligne"
                 else 10.0 * tolerances.longueur if classement.regle == "style"
                 else max(10.0 * tolerances.longueur, 0.1 * diagonale))
        if s.longueur < seuil:
            continue
        canon = _direction_canonique(s.a, s.b, tolerances)
        if canon is None:
            continue
        theta, u = canon
        n = normale(u)
        decalage = s.a[0] * n[0] + s.a[1] * n[1]
        ta, tb = s.a[0] * u[0] + s.a[1] * u[1], s.b[0] * u[0] + s.b[1] * u[1]
        lignes.append(_Ligne(theta, u, decalage, min(ta, tb), max(ta, tb), [s],
                             classement.regle, classement.motif))
    # FUSION DES MORCEAUX COLINEAIRES: même direction, même décalage.
    lignes.sort(key=lambda x: (round(x.theta, 3), x.decalage, x.debut))
    fusionnees: list[_Ligne] = []
    for ligne in lignes:
        for cible in fusionnees:
            if (ecart_angulaire(cible.theta, ligne.theta) <= tolerances.parallele_deg
                    and abs(cible.decalage - ligne.decalage) <= 2.0 * tolerances.longueur):
                cible.debut = min(cible.debut, ligne.debut)
                cible.fin = max(cible.fin, ligne.fin)
                cible.segments.extend(ligne.segments)
                break
        else:
            fusionnees.append(ligne)
    return fusionnees


@dataclass(frozen=True)
class _Candidat:
    texte: str
    poignee: str
    via: str
    distance: float


def _etiquettes_possibles(ligne: _Ligne, prims: PrimitivesDxf, courts: list[Texte],
                          bulles_bloc: list[tuple[Insertion, str]],
                          hauteur_type: float) -> list[tuple[int, _Candidat]]:
    """Les étiquettes candidates, pour chaque extrémité (0 : début, 1 : fin)."""
    origine = (ligne.decalage * normale(ligne.u)[0], ligne.decalage * normale(ligne.u)[1])
    trouves: list[tuple[int, _Candidat]] = []
    for bout, t_bout, sens in ((0, ligne.debut, -1.0), (1, ligne.fin, 1.0)):
        extremite = (origine[0] + t_bout * ligne.u[0], origine[1] + t_bout * ligne.u[1])
        # (a) une bulle: un cercle centré sur le prolongement, un texte dedans.
        for cercle in prims.cercles:
            r = cercle.rayon
            if distance_point_droite(cercle.centre, origine, ligne.u) > max(0.25 * r, 1e-9):
                continue
            au_dela = (projeter(cercle.centre, origine, ligne.u) - t_bout) * sens
            if not -r <= au_dela <= 4.0 * r:
                continue
            dedans = [t for t in courts if distance(t.centre, cercle.centre) <= r]
            if dedans:
                texte = min(dedans, key=lambda t: distance(t.centre, cercle.centre))
                trouves.append((bout, _Candidat(texte.texte.strip(), texte.source.poignee,
                                                "bulle", distance(extremite, cercle.centre))))
        # (b) un bloc de bulle et son attribut.
        for insertion, valeur in bulles_bloc:
            if distance_point_droite(insertion.point, origine, ligne.u) > 2.0 * hauteur_type:
                continue
            au_dela = (projeter(insertion.point, origine, ligne.u) - t_bout) * sens
            if not -2.0 * hauteur_type <= au_dela <= 8.0 * hauteur_type:
                continue
            trouves.append((bout, _Candidat(valeur, insertion.source.poignee, "bloc",
                                            distance(extremite, insertion.point))))
        # (c) un texte court posé dans le prolongement.
        for texte in courts:
            h = texte.hauteur
            if distance_point_droite(texte.centre, origine, ligne.u) > 1.5 * h:
                continue
            au_dela = (projeter(texte.centre, origine, ligne.u) - t_bout) * sens
            if not -h <= au_dela <= 4.0 * h:
                continue
            trouves.append((bout, _Candidat(texte.texte.strip(), texte.source.poignee,
                                            "texte", distance(extremite, texte.centre) + h)))
    return trouves


def detecter_axes(prims: PrimitivesDxf, tolerances: Tolerances
                  ) -> tuple[Grille, set[str], list[NonResolu]]:
    """La grille du dessin, les poignées d'étiquettes absorbées, et les doutes."""
    emprise = prims.emprise()
    if emprise is None:
        return Grille(), set(), []
    diagonale = math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
    lignes = _lignes_candidates(prims, tolerances, diagonale)
    if not lignes:
        return Grille(), set(), []

    courts = [t for t in prims.textes if ETIQUETTE_AXE.fullmatch(t.texte.strip())]
    hauteurs = sorted(t.hauteur for t in courts) or [tolerances.longueur * 100]
    hauteur_type = hauteurs[len(hauteurs) // 2]
    bulles_bloc: list[tuple[Insertion, str]] = []
    for insertion in prims.insertions:
        if role_du_nom(insertion.nom_bloc) != "axe":
            continue
        valeurs = [v.strip() for _, v in insertion.attributs if ETIQUETTE_AXE.fullmatch(v.strip())]
        if valeurs:
            bulles_bloc.append((insertion, valeurs[0]))

    # L'AFFECTATION DES ETIQUETTES EST GLOBALE: un texte sert un seul axe, le
    # plus proche.
    propositions: list[tuple[float, int, int, _Candidat]] = []
    for rang, ligne in enumerate(lignes):
        for bout, candidat in _etiquettes_possibles(ligne, prims, courts, bulles_bloc,
                                                    hauteur_type):
            propositions.append((candidat.distance, rang, bout, candidat))
    propositions.sort(key=lambda x: (x[0], x[1], x[2], x[3].poignee))
    par_bout: dict[tuple[int, int], _Candidat] = {}
    utilisees: set[str] = set()
    for _, rang, bout, candidat in propositions:
        if (rang, bout) in par_bout or (candidat.poignee and candidat.poignee in utilisees):
            continue
        par_bout[(rang, bout)] = candidat
        if candidat.poignee:
            utilisees.add(candidat.poignee)

    doutes: list[NonResolu] = []
    etiquettes: list[tuple[str | None, dict[str, Any] | None]] = []
    for rang in range(len(lignes)):
        a, b = par_bout.get((rang, 0)), par_bout.get((rang, 1))
        if a and b and a.texte != b.texte:
            doutes.append(NonResolu(f"axe {rang + 1}", (
                f"etiquettes contradictoires aux deux extremites: « {a.texte} » et "
                f"« {b.texte} »; l'axe reste sans etiquette")))
            etiquettes.append((None, None))
            continue
        choisi = a or b
        etiquettes.append((choisi.texte, {"via": choisi.via, "handle": choisi.poignee})
                          if choisi else (None, None))

    # FAMILLES: directions egales a la tolerance pres.
    ordre = sorted(range(len(lignes)), key=lambda i: lignes[i].theta)
    familles_idx: list[list[int]] = []
    for i in ordre:
        if familles_idx and ecart_angulaire(lignes[familles_idx[-1][0]].theta,
                                             lignes[i].theta) <= tolerances.parallele_deg:
            familles_idx[-1].append(i)
        else:
            familles_idx.append([i])
    # Le voisinage de 0° et de 180° ne fait qu'une famille.
    if (len(familles_idx) > 1 and ecart_angulaire(lignes[familles_idx[0][0]].theta,
                                                  lignes[familles_idx[-1][0]].theta)
            <= tolerances.parallele_deg):
        familles_idx[0].extend(familles_idx.pop())

    # UNE GRILLE RAYONNANTE N'EST PAS UNE GRILLE DE FILES: elle est nommee et
    # ecartee, jamais approchee par des files d'un seul axe.
    seules = [m[0] for m in familles_idx if len(m) == 1]
    if len(seules) >= 3:
        def origine(i: int) -> Point:
            n = normale(lignes[i].u)
            return (lignes[i].decalage * n[0], lignes[i].decalage * n[1])

        centre = intersection_droites(origine(seules[0]), lignes[seules[0]].u,
                                      origine(seules[1]), lignes[seules[1]].u)
        if centre is not None and all(
                distance_point_droite(centre, origine(i), lignes[i].u)
                <= 10.0 * tolerances.longueur for i in seules):
            familles_idx = [m for m in familles_idx if len(m) != 1]
            doutes.append(NonResolu("grille", (
                f"{len(seules)} axes concourants en un meme point (grille polaire ou "
                "rayonnante): non prise en charge; ils ne forment pas de files et "
                "aucun noeud n'en est tire")))
    gardes = {i for membres in familles_idx for i in membres}

    vues: dict[str, int] = {}
    axes: list[Axe] = []
    familles: list[Famille] = []
    for index_famille, membres in enumerate(familles_idx):
        # L'ORDRE DE LECTURE: de gauche a droite pour des axes verticaux, de bas
        # en haut pour des axes horizontaux — A, B, C et 1, 2, 3, pas l'inverse.
        signe = _sens_de_lecture(lignes[membres[0]].u)
        membres.sort(key=lambda i: signe * lignes[i].decalage)
        ids: list[str] = []
        for position, i in enumerate(membres):
            ligne = lignes[i]
            etiquette, origine_etiquette = etiquettes[i]
            ident = f"grid:{etiquette}" if etiquette else f"grid:{index_famille}.{position + 1}"
            if ident in vues:
                doutes.append(NonResolu(ident, "deux axes portent la meme etiquette"))
                ident = f"{ident}#{vues[ident] + 1}"
            vues[ident] = vues.get(ident, 0) + 1
            n = normale(ligne.u)
            confiance = (0.85 if etiquette and ligne.regle != "type_de_ligne"
                         else 0.75 if etiquette else 0.6)
            axes.append(Axe(
                id=ident, etiquette=etiquette, famille=index_famille,
                origine=(ligne.decalage * n[0], ligne.decalage * n[1]), direction=ligne.u,
                decalage=ligne.decalage, debut=ligne.debut, fin=ligne.fin,
                preuve=preuve_de(ligne.segments, ligne.regle, ligne.motif),
                confiance=confiance, etiquette_source=origine_etiquette))
            ids.append(ident)
        angle = lignes[membres[0]].theta % 180.0
        familles.append(Famille(index_famille, angle, tuple(ids)))

    # LE REPERE DE LA GRILLE: la famille la plus proche de l'horizontale.
    repere_x: Point = (1.0, 0.0)
    if familles:
        horizontale = min(familles, key=lambda f: (min(f.angle, 180.0 - f.angle), f.index))
        rad = math.radians(horizontale.angle if horizontale.angle < 90.0
                           else horizontale.angle - 180.0)
        repere_x = (math.cos(rad), math.sin(rad))

    noeuds: list[Noeud] = []
    par_id = {a.id: a for a in axes}
    marge = 10.0 * tolerances.longueur
    for i, fa in enumerate(familles):
        for fb in familles[i + 1:]:
            if ecart_angulaire(fa.angle, fb.angle) < _ANGLE_FAMILLES_MIN:
                continue
            for ia in fa.axes:
                a = par_id[ia]
                for ib in fb.axes:
                    b = par_id[ib]
                    p = intersection_droites(a.origine, a.direction, b.origine, b.direction)
                    if p is None:
                        continue
                    ta = projeter(p, a.origine, a.direction)
                    tb = projeter(p, b.origine, b.direction)
                    if not (a.debut - marge <= ta <= a.fin + marge
                            and b.debut - marge <= tb <= b.fin + marge):
                        continue
                    etiquette = _nom_de_noeud(a.etiquette, b.etiquette)
                    ident = (f"node:{etiquette}" if etiquette
                             else f"node:{a.nom}x{b.nom}")
                    noeuds.append(Noeud(ident, etiquette, p, (a.id, b.id)))
    absorbees = {c.poignee for (rang, _), c in par_bout.items()
                 if c.poignee and rang in gardes}
    return Grille(tuple(axes), tuple(familles), tuple(noeuds), repere_x), absorbees, doutes


def _sens_de_lecture(u: Point) -> float:
    """+1 ou -1 : le signe qui fait croître le décalage vers la droite ou vers le haut."""
    n = normale(u)
    if abs(n[0]) >= abs(n[1]):
        return 1.0 if n[0] > 0 else -1.0
    return 1.0 if n[1] > 0 else -1.0


def _nom_de_noeud(a: str | None, b: str | None) -> str | None:
    """« A » et « 1 » donnent « A1 » ; deux lettres ou deux chiffres, « A/B »."""
    if not a or not b:
        return None
    if a[0].isalpha() and b[0].isdigit():
        return f"{a}{b}"
    if b[0].isalpha() and a[0].isdigit():
        return f"{b}{a}"
    return f"{a}/{b}"
