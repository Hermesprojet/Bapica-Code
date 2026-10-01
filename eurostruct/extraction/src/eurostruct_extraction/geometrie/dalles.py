"""Les dalles et les trémies.

UN PANNEAU EST UNE CELLULE DE LA GRILLE PORTÉE SUR SES CÔTÉS
-------------------------------------------------------------
Entre deux axes consécutifs de chaque famille, une cellule dont l'intérieur ne
contient ni poteau ni voile, et dont au moins deux côtés sont portés — une
poutre ou un voile couvrant 80 % du côté. Chaque côté est dit : « porté par
P1 », ou « bord libre ». Un marqueur en croix (diagonales d'angle à angle) ou
un texte de dalle à l'intérieur confirment le panneau.

L'ÉPAISSEUR N'EST PAS UN TRAIT. Le texte « Dalle pleine ép. 20 » lu par les
règles de texte est rattaché au panneau qui le contient ; la géométrie d'un
plan ne montre pas une épaisseur, elle ne l'invente pas.

UNE POUTRE QUI TRAVERSE UN PANNEAU (une solive portée par deux poutres) ne le
subdivise pas : le panneau la cite (``crossed_by``), l'ingénieur tranche.

UNE TRÉMIE est un contour sur un calque de trémie, ou un PETIT rectangle barré
d'une croix à l'intérieur d'un panneau. La croix qui couvre tout le panneau,
elle, est le marqueur de la dalle.
"""

from __future__ import annotations

import re
from typing import Final

from .classification import classer
from .modele import Dalle, Grille, Poteau, Poutre, Tremie, Voile, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    angle_deg,
    boite_de,
    centroide,
    distance,
    distance_point_droite,
    ecart_angulaire,
    intersection_droites,
    point_dans_polygone,
    projeter,
    rectangle_de,
    unitaire,
)
from .poteaux import Forme
from .primitives import PrimitivesDxf, Segment, Texte

__all__ = ["detecter_dalles"]

_TEXTE_DALLE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:dalles?|slabs?|plaat|vloer|decke|hourdis|pr[ée]dalles?|plancher)\b|"
    r"(?i:\b[ée]p\.?\s*\d)|(?i:[ée]paisseur)")
COUVERTURE_MIN: Final[float] = 0.8


def _cote_porte(a: Point, b: Point, poutres: list[Poutre], voiles: list[Voile],
                tolerances: Tolerances) -> str | None:
    """L'élément qui porte le côté ``[a, b]`` sur au moins 80 % de sa longueur."""
    u = unitaire(a, b)
    if u is None:
        return None
    longueur = distance(a, b)
    theta = angle_deg(u)
    for poutre in poutres:
        bande = poutre.bande
        if ecart_angulaire(angle_deg(bande.direction), theta) > tolerances.parallele_deg:
            continue
        if distance_point_droite(a, bande.origine, bande.direction) > \
                (bande.largeur or 0.0) / 2.0 + tolerances.longueur:
            continue
        ta, tb = sorted((projeter(a, bande.origine, bande.direction),
                         projeter(b, bande.origine, bande.direction)))
        couvert = max(0.0, min(tb, bande.fin) - max(ta, bande.debut))
        if couvert >= COUVERTURE_MIN * longueur:
            reperes = [t.repere for t in poutre.travees
                       if t.repere and t.debut and t.fin
                       and min(t.debut.centre, t.fin.centre) <= (ta + tb) / 2.0
                       <= max(t.debut.centre, t.fin.centre)]
            return reperes[0] if reperes else poutre.id
    for voile in voiles:
        if voile.axe is None:
            continue
        uv = unitaire(voile.axe[0], voile.axe[1])
        if uv is None or ecart_angulaire(angle_deg(uv), theta) > tolerances.parallele_deg:
            continue
        if distance_point_droite(a, voile.axe[0], uv) > (voile.epaisseur or 0.0) / 2.0 + \
                tolerances.longueur:
            continue
        ta, tb = sorted((projeter(a, voile.axe[0], uv), projeter(b, voile.axe[0], uv)))
        couvert = max(0.0, min(tb, voile.longueur or 0.0) - max(ta, 0.0))
        if couvert >= COUVERTURE_MIN * longueur:
            return voile.repere or voile.id
    return None


def _diagonales(coins: tuple[Point, Point, Point, Point], segments: list[Segment],
                rayon: float) -> list[Segment]:
    """Les segments qui relient deux coins opposés (à ``rayon`` près)."""
    trouvees = []
    paires = ((coins[0], coins[2]), (coins[1], coins[3]))
    for s in segments:
        for c1, c2 in paires:
            if ((distance(s.a, c1) <= rayon and distance(s.b, c2) <= rayon)
                    or (distance(s.a, c2) <= rayon and distance(s.b, c1) <= rayon)):
                trouvees.append(s)
    return trouvees


def detecter_dalles(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                    poteaux: list[Poteau], voiles: list[Voile], poutres: list[Poutre],
                    formes: list[Forme], formes_prises: set[int]
                    ) -> tuple[list[Dalle], list[Tremie]]:
    dalles: list[Dalle] = []
    tremies: list[Tremie] = []
    libres = [s for s in prims.segments if not s.courbe
              and classer(s.calque, s.source.blocs, s.type_ligne).role in ("inconnu", "dalle",
                                                                          "tremie")]
    textes_dalle: list[Texte] = [t for t in prims.textes if _TEXTE_DALLE.search(t.texte)]

    familles = sorted((f for f in grille.familles if len(f.axes) >= 2),
                      key=lambda f: (-len(f.axes), f.index))
    paire = None
    for i, f0 in enumerate(familles):
        for f1 in familles[i + 1:]:
            if ecart_angulaire(f0.angle, f1.angle) >= 10.0:
                paire = (f0, f1)
                break
        if paire:
            break
    # LE MILIEU DE CHAQUE TRAVEE, pour dire quelles poutres traversent un panneau.
    milieux: list[tuple[Point, str]] = []
    index_milieux = IndexSpatial(max(grille.entraxe_median() or 0.0, 10.0 * tolerances.longueur))
    for poutre in poutres:
        for t in poutre.travees:
            if t.debut is not None and t.fin is not None:
                m = poutre.bande.point((t.debut.centre + t.fin.centre) / 2.0)
                milieux.append((m, t.repere or t.id))
                index_milieux.ajouter((m[0], m[1], m[0], m[1]))
    if paire is not None:
        f0, f1 = paire
        axes0 = [grille.axe(i) for i in f0.axes]
        axes1 = [grille.axe(i) for i in f1.axes]
        for a0, a1 in zip(axes0, axes0[1:], strict=False):
            for b0, b1 in zip(axes1, axes1[1:], strict=False):
                coins_ = [intersection_droites(x.origine, x.direction, y.origine, y.direction)
                          for x, y in ((a0, b0), (a0, b1), (a1, b1), (a1, b0))]
                if any(c is None for c in coins_):
                    continue
                coins: tuple[Point, Point, Point, Point] = tuple(coins_)  # type: ignore[assignment]
                interieur = [p for p in poteaux
                             if point_dans_polygone(p.centre, coins)
                             and min(distance_point_droite(p.centre, x.origine, x.direction)
                                     for x in (a0, a1, b0, b1)) > 10.0 * tolerances.longueur]
                if interieur:
                    continue
                cotes_cellule = ((a0.nom, coins[0], coins[1]),
                                 (b1.nom, coins[1], coins[2]),
                                 (a1.nom, coins[2], coins[3]),
                                 (b0.nom, coins[3], coins[0]))
                bords = tuple((nom, _cote_porte(p, q, poutres, voiles, tolerances))
                              for nom, p, q in cotes_cellule)
                lx = abs(a1.decalage - a0.decalage)
                ly = abs(b1.decalage - b0.decalage)
                rayon = max(0.2 * min(lx, ly), 2.0 * tolerances.longueur)
                diagonales = _diagonales(coins, libres, rayon)
                marqueur = len({id(s) for s in diagonales}) >= 2
                libelle = next((t.texte for t in sorted(
                    textes_dalle, key=lambda t: distance(t.centre, centroide(coins)))
                    if point_dans_polygone(t.centre, coins)), None)
                portes = sum(1 for _, porteur in bords if porteur)
                if portes < 2 and not (marqueur or libelle):
                    continue
                marge = 10.0 * tolerances.longueur
                traversee = tuple(sorted({
                    milieux[k][1] for k in index_milieux.pres_de(boite_de(coins))
                    if point_dans_polygone(milieux[k][0], coins)
                    and min(distance_point_droite(milieux[k][0], x.origine, x.direction)
                            for x in (a0, a1, b0, b1)) > marge}))
                # LES LETTRES D'ABORD (« A-B/1-2 »), comme on nomme une travée.
                noms_a = f"{a0.nom}-{a1.nom}"
                noms_b = f"{b0.nom}-{b1.nom}"
                nom = (f"{noms_a}/{noms_b}" if (a0.etiquette or "0")[0].isalpha()
                       else f"{noms_b}/{noms_a}")
                # lx SELON L'AXE x DE LA GRILLE: l'entraxe de la famille dont les
                # droites sont perpendiculaires à cet axe.
                horizontale = ecart_angulaire(f0.angle, angle_deg(grille.repere_x)) <= 45.0
                lx, ly = (abs(ly), abs(lx)) if horizontale else (abs(lx), abs(ly))
                preuve = preuve_de(diagonales, "forme") if diagonales else preuve_de(
                    [], "forme")
                dalles.append(Dalle(
                    id=f"slab:{nom}", contour=coins, origine="panneau", bords=bords,
                    lx=lx, ly=ly, marqueur=marqueur, libelle=libelle,
                    preuve=preuve, confiance=0.7 if (marqueur or libelle) else 0.55,
                    repere=nom, traversee_par=traversee))

    # LES CONTOURS SUR CALQUE DE DALLE, ET LES TREMIES.
    for rang, forme in enumerate(formes):
        if rang in formes_prises or forme.genre == "cercle":
            continue
        role = forme.classement.role
        rect = rectangle_de(forme.points, tolerances)
        if role == "dalle":
            dalles.append(Dalle(
                id=f"slab:contour:{len(dalles) + 1}", contour=forme.points, origine="contour",
                bords=(), lx=rect.longueur_u if rect else None,
                ly=rect.longueur_v if rect else None, marqueur=False, libelle=None,
                preuve=preuve_de(forme.primitives, forme.classement.regle,
                                 forme.classement.motif), confiance=0.7))
            continue
        barre = False
        if role == "inconnu" and rect is not None:
            u, v = rect.u, rect.v
            hu, hv = rect.longueur_u / 2.0, rect.longueur_v / 2.0
            c = rect.centre
            coins_rect = tuple((c[0] + su * hu * u[0] + sv * hv * v[0],
                                c[1] + su * hu * u[1] + sv * hv * v[1])
                               for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)))
            barre = len({id(s) for s in _diagonales(coins_rect, libres,  # type: ignore[arg-type]
                                                    2.0 * tolerances.longueur)}) >= 2
        if role == "tremie" or barre:
            panneau = next((d.id for d in dalles if d.origine == "panneau"
                            and point_dans_polygone(centroide(forme.points), d.contour)), None)
            if role != "tremie" and (panneau is None or rect is None):
                continue
            if role != "tremie":
                cellule = next(d for d in dalles if d.id == panneau)
                if rect.grand_cote > 0.5 * min(cellule.lx or 0.0, cellule.ly or 0.0):
                    continue
            tremies.append(Tremie(
                id=f"opening:{len(tremies) + 1}", contour=forme.points,
                largeur=rect.longueur_u if rect else None,
                longueur=rect.longueur_v if rect else None, dalle=panneau,
                preuve=preuve_de(forme.primitives, forme.classement.regle if role == "tremie"
                                 else "forme", forme.classement.motif)))
    return dalles, tremies
