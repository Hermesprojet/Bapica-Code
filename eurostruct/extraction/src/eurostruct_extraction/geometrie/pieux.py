"""Les pieux : reconnus par leur nom, regroupés avec tout leur dessin, comptés.

Voir ``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md`` (§ 1). Un pieu n'est JAMAIS un
poteau. Sur un plan de fondations réel, 475 pieux étaient dessinés deux fois
(le calque de la feuille et sa copie dans une xréf), leurs remplissages et les
lentilles d'une paroi de pieux sécants l'étaient sur d'autres calques : sans
ce module, 98 de ces formes devenaient des « poteaux » aux nœuds de la grille.

1. **Germes** : les cercles et les contours fermés (hors hachures) de rôle
   ``pieu`` — calque ou bloc.
2. **Doublons** : même centre et même taille à 5 % près → un pieu, deux preuves.
3. **Dessin du pieu** : un contour fermé, de n'importe quel calque, qui
   coïncide avec un pieu, ou dont la moitié au moins des sommets sont sur le
   bord d'un ou deux pieux et le centre dedans (remplissage, lentille,
   croissant). Un poteau posé sur un pieu n'a pas ses sommets sur son bord.
4. **Hachures orphelines** de rôle ``pieu`` : un pieu si elles sont compactes ;
   sinon des fragments, comptés.
5. **Repère** : un texte de rôle ``pieu`` ou qui nomme un pieu, rattaché au
   pieu le plus proche.

RIEN N'EST PROPOSÉ : le modèle montre et compte les pieux ; dimensionner une
fondation profonde est hors du domaine validé du moteur.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Final

from .classification import classer, nomme_un_pieu
from .modele import Grille, Pieu, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    boite_de,
    centroide,
    compacite,
    distance,
    distance_point_polygone,
    point_dans_polygone,
    quantifier,
    rectangle_de,
)
from .poteaux import Forme, _index_des_noeuds, _noeud_proche
from .primitives import Contour, PrimitivesDxf, Texte

__all__ = ["DetectionPieux", "detecter_pieux"]

CONFIANCE_PIEU: Final[float] = 0.85
#: Même pieu : centres et tailles à 5 % de la taille près.
ECART_RELATIF: Final[float] = 0.05
#: Un sommet est « sur le bord » d'un pieu à 2 % de sa taille près.
BORD_RELATIF: Final[float] = 0.02
#: La moitié des sommets sur le bord : le contour fait partie du dessin du pieu.
PART_SUR_LE_BORD: Final[float] = 0.5
#: Une hachure orpheline n'est un pieu que compacte, et pas plus allongée.
COMPACITE_ORPHELINE: Final[float] = 0.9
ELANCEMENT_ORPHELIN: Final[float] = 1.5
#: Seules ces formes peuvent être le dessin d'un pieu : une forme sur un
#: calque de poteau, de voile ou de poutre garde son rôle, même si elle
#: coïncide avec un pieu (un pieu-colonne existe).
_ABSORBABLES: Final[frozenset[str]] = frozenset({"inconnu", "hachure", "pieu"})


@dataclass
class _Groupe:
    centre: Point
    taille: float
    forme: Forme
    membres: list[int] = field(default_factory=list)


@dataclass
class DetectionPieux:
    pieux: list[Pieu]
    #: Les rangs des formes qui sont le dessin d'un pieu : plus jamais un poteau,
    #: un voile, une poutre.
    formes_prises: set[int]
    compte_rendu: dict[str, Any]


def _centre_et_taille(forme: Forme) -> tuple[Point, float]:
    if forme.genre == "cercle" and forme.rayon is not None:
        pts = forme.points
        return ((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)),
                2.0 * forme.rayon)
    x0, y0, x1, y1 = boite_de(forme.points)
    return centroide(forme.points), max(x1 - x0, y1 - y0)


def _hachure(forme: Forme) -> bool:
    return any(isinstance(p, Contour) and p.origine == "hachure" for p in forme.primitives)


def _sur_le_bord(p: Point, groupe: _Groupe, tolerances: Tolerances) -> bool:
    marge = max(2.0 * tolerances.longueur, BORD_RELATIF * groupe.taille)
    if groupe.forme.genre == "cercle":
        return abs(distance(p, groupe.centre) - groupe.taille / 2.0) <= marge
    return distance_point_polygone(p, groupe.forme.points) <= marge


def _dedans(p: Point, groupe: _Groupe, tolerances: Tolerances) -> bool:
    marge = max(2.0 * tolerances.longueur, BORD_RELATIF * groupe.taille)
    if groupe.forme.genre == "cercle":
        return distance(p, groupe.centre) <= groupe.taille / 2.0 + marge
    return point_dans_polygone(p, groupe.forme.points, marge)


def detecter_pieux(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                   formes: list[Forme]) -> DetectionPieux:
    groupes: list[_Groupe] = []
    index = IndexSpatial(max(10.0 * tolerances.longueur,
                             0.05 * (grille.entraxe_median() or 0.0)))

    def meme(centre: Point, taille: float) -> _Groupe | None:
        marge = max(5.0 * tolerances.longueur, ECART_RELATIF * taille)
        for rang in index.pres_de((centre[0], centre[1], centre[0], centre[1]), marge=marge):
            g = groupes[rang]
            seuil = max(5.0 * tolerances.longueur, ECART_RELATIF * max(g.taille, taille))
            if distance(g.centre, centre) <= seuil and abs(g.taille - taille) <= seuil:
                return g
        return None

    def ajouter(rang: int, forme: Forme) -> None:
        centre, taille = _centre_et_taille(forme)
        groupe = meme(centre, taille)
        if groupe is not None:
            groupe.membres.append(rang)
            return
        groupes.append(_Groupe(centre, taille, forme, [rang]))
        r = taille / 2.0
        index.ajouter((centre[0] - r, centre[1] - r, centre[0] + r, centre[1] + r))

    # 1-2. LES GERMES, LE CERCLE AVANT LE CONTOUR, ET LEURS DOUBLONS.
    nommes = [i for i, f in enumerate(formes) if f.classement.role == "pieu"]
    germes = sorted((i for i in nommes if not _hachure(formes[i])),
                    key=lambda i: (formes[i].genre != "cercle",
                                   -_centre_et_taille(formes[i])[1], i))
    for i in germes:
        ajouter(i, formes[i])

    # 3. LE DESSIN DU PIEU, DE N'IMPORTE QUEL CALQUE.
    pris = {i for g in groupes for i in g.membres}
    absorbees = 0
    orphelines: list[int] = []
    for i, forme in enumerate(formes):
        if i in pris or forme.classement.role not in _ABSORBABLES or not forme.points:
            continue
        centre, taille = _centre_et_taille(forme)
        groupe = meme(centre, taille)
        if groupe is not None:
            groupe.membres.append(i)
            pris.add(i)
            absorbees += 1
            continue
        x0, y0, x1, y1 = boite_de(forme.points)
        voisins = [groupes[r] for r in index.pres_de((x0, y0, x1, y1),
                                                       marge=2.0 * tolerances.longueur)]
        if voisins:
            sur_bord = sum(1 for p in forme.points
                           if any(_sur_le_bord(p, g, tolerances) for g in voisins))
            hote = next((g for g in voisins if _dedans(centre, g, tolerances)), None)
            if hote is not None and sur_bord >= PART_SUR_LE_BORD * len(forme.points):
                hote.membres.append(i)
                pris.add(i)
                absorbees += 1
                continue
        if forme.classement.role == "pieu":
            orphelines.append(i)

    # 4. LES HACHURES ORPHELINES : UN PIEU SI COMPACTES, SINON DES FRAGMENTS.
    fragments = 0
    for i in orphelines:
        forme = formes[i]
        rect = rectangle_de(forme.points, tolerances)
        x0, y0, x1, y1 = boite_de(forme.points)
        petit, grand = sorted((x1 - x0, y1 - y0))
        if (petit > 0 and grand / petit <= ELANCEMENT_ORPHELIN
                and (rect is not None or compacite(forme.points) >= COMPACITE_ORPHELINE)):
            ajouter(i, forme)
            pris.add(i)
        else:
            fragments += 1
            pris.add(i)

    pieux = _pieux(groupes, formes, grille, tolerances)
    pieux = _reperes(pieux, prims.textes)
    diametres = Counter(str(quantifier(p.diametre, tolerances.quantum))
                        for p in pieux if p.diametre is not None)
    compte_rendu = {"count": len(pieux), "by_diameter": dict(diametres.most_common()),
                    "drawing_shapes_absorbed": absorbees, "drawing_fragments": fragments}
    return DetectionPieux(pieux, pris, compte_rendu)


def _pieux(groupes: list[_Groupe], formes: list[Forme], grille: Grille,
           tolerances: Tolerances) -> list[Pieu]:
    index_noeuds = _index_des_noeuds(grille, tolerances)
    pieux: list[Pieu] = []
    for g in groupes:
        forme = g.forme
        classement = formes[g.membres[0]].classement
        regle = classement.regle if classement.role == "pieu" else "forme"
        preuve = preuve_de([p for i in g.membres for p in formes[i].primitives], regle,
                           classement.motif if classement.role == "pieu" else None)
        diametre = largeur = profondeur = None
        if forme.genre == "cercle":
            diametre = g.taille
        else:
            rect = rectangle_de(forme.points, tolerances)
            if rect is not None:
                largeur, profondeur = rect.longueur_u, rect.longueur_v
        noeud = _noeud_proche(g.centre, 0.5 * g.taille, grille, forme.points, tolerances,
                              index_noeuds)
        pieux.append(Pieu(id="", forme=forme.genre if forme.genre != "polygone" or largeur is None
                          else "rectangle", contour=forme.points, centre=g.centre,
                          diametre=diametre, largeur=largeur, profondeur=profondeur,
                          noeud=noeud, preuve=preuve, confiance=CONFIANCE_PIEU))
    pieux.sort(key=lambda p: (p.noeud is None, p.noeud or "", round(p.centre[1], 6),
                              round(p.centre[0], 6)))
    vus: dict[str, int] = {}
    nommes: list[Pieu] = []
    for rang, p in enumerate(pieux, start=1):
        base = f"pile:{p.noeud}" if p.noeud else f"pile:{rang}"
        if base in vus:
            vus[base] += 1
            base = f"{base}#{vus[base]}"
        else:
            vus[base] = 1
        nommes.append(replace(p, id=base))
    return nommes


def _reperes(pieux: list[Pieu], textes: list[Texte]) -> list[Pieu]:
    """Un texte de pieu au pieu le plus proche ; un texte sert une fois."""
    if not pieux:
        return pieux
    index = IndexSpatial(max(p.diametre or p.largeur or 1.0 for p in pieux))
    for p in pieux:
        index.ajouter((p.centre[0], p.centre[1], p.centre[0], p.centre[1]))
    liens: list[tuple[float, int, int]] = []
    for rang_t, t in enumerate(textes):
        if not (classer(t.calque, t.source.blocs, t.type_ligne).role == "pieu"
                or nomme_un_pieu(t.texte)) or not t.texte.strip() or len(t.texte) > 24:
            continue
        for rang_p in index.pres_de((t.centre[0], t.centre[1], t.centre[0], t.centre[1]),
                                    marge=6.0 * t.hauteur):
            p = pieux[rang_p]
            portee = max(6.0 * t.hauteur, 2.0 * (p.diametre or p.largeur or 0.0))
            d = distance(t.centre, p.centre)
            if d <= portee:
                liens.append((d, rang_t, rang_p))
    liens.sort()
    pris_t: set[int] = set()
    pris_p: set[int] = set()
    sortie = list(pieux)
    for _d, rang_t, rang_p in liens:
        if rang_t in pris_t or rang_p in pris_p:
            continue
        pris_t.add(rang_t)
        pris_p.add(rang_p)
        t = textes[rang_t]
        sortie[rang_p] = replace(sortie[rang_p], repere=" ".join(t.texte.split()),
                                 repere_source={"text": t.texte, "handle": t.source.poignee,
                                                "layer": t.calque})
    return sortie
