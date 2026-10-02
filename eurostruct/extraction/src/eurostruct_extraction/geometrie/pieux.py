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

LA GÉOMÉTRIE D'ABORD (G3, ``docs/GEOMETRIE_D_ABORD_G3.md``) : sur un DXF, les
cercles d'un même diamètre (1 %) sont rangés en classes ; une classe d'au moins
10 cercles distincts, de diamètre plausible, qui n'est ni une classe de bulles
(G2) ni une classe de poteaux ronds (80 % pleins, seuls, à un nœud), a la
SIGNATURE P : ses cercles sont des germes, QUEL QUE SOIT LEUR NOM. Les germes
nommés sont regroupés d'abord, dans l'ordre d'aujourd'hui (un pieu reconnu par
son nom garde son représentant) ; les germes géométriques les rejoignent ou
font des pieux nouveaux. Le nom ne fait que compléter (un pieu hors de toute
classe) ou confirmer (+ 0,05) ; un germe géométrique nommé d'un autre rôle est
un pieu à 0,4, et le conflit est dit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Final

from .axes_geometriques import Bulle, signatures_d_axes
from .classification import Classement, classer, nomme_un_pieu
from .modele import Grille, NonResolu, Pieu, preuve_de
from .noyau import (
    IndexSpatial,
    Point,
    Tolerances,
    boite_de,
    compacite,
    distance,
    distance_point_droite,
    distance_point_polygone,
    point_dans_polygone,
    projeter,
    quantifier,
    rectangle_de,
)
from .poteaux import Forme, _index_des_noeuds, _noeud_proche
from .poteaux import centre_et_taille as _centre_et_taille
from .primitives import Cercle, Contour, PrimitivesDxf, Texte

__all__ = ["DetectionPieux", "detecter_pieux"]

CONFIANCE_PIEU: Final[float] = 0.85
#: La signature et un nom concordant (§ 2.8) ; un nom d'un autre rôle plafonne.
CONFIANCE_CONCORDANTE: Final[float] = 0.90
PLAFOND_CONFLIT: Final[float] = 0.4
#: SIGNATURE P : au moins 10 cercles distincts d'un même diamètre à 1 % près.
MEMBRES_P: Final[int] = 10
ECART_DIAMETRE_P: Final[float] = 0.01
#: Diamètre plausible d'un pieu (mm réels) quand l'unité est connue ; sinon au
#: plus cette fraction de l'entraxe médian ; sans l'un ni l'autre, invérifiable.
DIAMETRE_MIN_MM: Final[float] = 250.0
DIAMETRE_MAX_MM: Final[float] = 2000.0
FRACTION_ENTRAXE_P: Final[float] = 0.3
#: Une classe dont 80 % des membres sont pleins, seuls et à un nœud : des poteaux ronds.
PART_POTEAUX_RONDS: Final[float] = 0.8
#: Une classe dont la moitié des membres sont des bulles d'axes : des bulles
#: (la règle des classes de bulles de G2).
PART_BULLES: Final[float] = 0.5
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
    #: Les rangs des formes qui SONT un pieu (germes nommés ou géométriques,
    #: hachures orphelines) : jamais un poteau, même sur un calque de poteaux.
    germes: set[int] = field(default_factory=set)
    #: Les conflits entre une signature P et un nom d'un autre rôle.
    doutes: list[NonResolu] = field(default_factory=list)


@dataclass(frozen=True)
class _SignatureP:
    #: Les rangs des cercles des classes P, et le diamètre de leur classe.
    germes: dict[int, float]
    #: Chaque classe d'au moins 10 cercles distincts, et son verdict.
    classes: list[dict[str, Any]]


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


def _distincts(rangs: list[int], formes: list[Forme], tolerances: Tolerances
               ) -> list[list[int]]:
    """Les membres distincts d'une classe : les cercles de même centre réunis
    (la feuille et sa copie dans une xréf font un pieu)."""
    seuil = max(5.0 * tolerances.longueur, ECART_RELATIF * 2.0 * (formes[rangs[0]].rayon or 0.0))
    index = IndexSpatial(max(seuil, 10.0 * tolerances.longueur))
    membres: list[list[int]] = []
    centres: list[Point] = []
    for i in rangs:
        c = _centre_et_taille(formes[i])[0]
        proche = next((m for m in index.pres_de((c[0], c[1], c[0], c[1]), marge=seuil)
                       if distance(centres[m], c) <= seuil), None)
        if proche is None:
            membres.append([i])
            centres.append(c)
            index.ajouter((c[0], c[1], c[0], c[1]))
        else:
            membres[proche].append(i)
    return membres


def _plausible(diametre: float, tolerances: Tolerances, entraxe: float | None) -> bool | None:
    if tolerances.mm_par_unite:
        mm = diametre * tolerances.mm_par_unite
        return DIAMETRE_MIN_MM <= mm <= DIAMETRE_MAX_MM
    if entraxe:
        return diametre <= FRACTION_ENTRAXE_P * entraxe
    return None


class _Bulles:
    """Les bulles d'axes, calculées une fois, seulement si une classe les demande.

    Un cercle est une bulle s'il est une bulle d'une classe de bulles de G2, ou
    s'il a la FORME d'une bulle (un seul texte court dedans) et qu'un axe de la
    grille finit sur lui — quelle que soit la règle qui a reconnu l'axe : la
    bulle d'un axe court, nommé, en est une (``docs/GEOMETRIE_D_ABORD_G3.md``
    § 2.5)."""

    def __init__(self, prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille) -> None:
        self.prims, self.tol, self.grille = prims, tolerances, grille
        self._pret = False
        self._validees: list[Bulle] = []
        self._formes: list[Bulle] = []
        self._index_validees = IndexSpatial(1.0)
        self._index_formes = IndexSpatial(1.0)
        self._index_bouts = IndexSpatial(1.0)

    def _preparer(self) -> None:
        geo = signatures_d_axes(self.prims, self.tol)
        self._validees = [b for b in geo.bulles if b.forme == "cercle"]
        self._formes = [b for b in (*geo.bulles, *geo.ecartees) if b.forme == "cercle"]
        case = max((b.rayon for b in self._formes), default=1.0)
        self._index_validees = IndexSpatial(case)
        for b in self._validees:
            self._index_validees.ajouter((b.centre[0], b.centre[1], b.centre[0], b.centre[1]))
        self._index_formes = IndexSpatial(case)
        for b in self._formes:
            self._index_formes.ajouter((b.centre[0], b.centre[1], b.centre[0], b.centre[1]))
        self._index_bouts = IndexSpatial(5.0 * case)
        for a in self.grille.axes:
            for p in a.extremites:
                self._index_bouts.ajouter((p[0], p[1], p[0], p[1]))
        self._pret = True

    def _parmi(self, bulles: list[Bulle], index: IndexSpatial, centre: Point,
               rayon: float) -> bool:
        seuil = max(5.0 * self.tol.longueur, ECART_RELATIF * 2.0 * rayon)
        return any(distance(bulles[k].centre, centre) <= seuil
                   and abs(bulles[k].rayon - rayon) <= ECART_RELATIF * rayon
                   for k in index.pres_de((centre[0], centre[1], centre[0], centre[1]),
                                          marge=seuil))

    def _au_bout_d_un_axe(self, centre: Point, rayon: float) -> bool:
        """La fenêtre de G2 : centre sur le prolongement à 0,25 rayon près, entre
        un rayon avant le bout de l'axe et quatre au-delà."""
        for k in self._index_bouts.pres_de((centre[0], centre[1], centre[0], centre[1]),
                                           marge=5.0 * rayon):
            a = self.grille.axes[k // 2]
            if distance_point_droite(centre, a.origine, a.direction) > max(0.25 * rayon, 1e-9):
                continue
            t = projeter(centre, a.origine, a.direction)
            t_bout, sens = (a.debut, -1.0) if k % 2 == 0 else (a.fin, 1.0)
            if -rayon <= (t - t_bout) * sens <= 4.0 * rayon:
                return True
        return False

    def contient(self, centre: Point, rayon: float) -> bool:
        if not self._pret:
            self._preparer()
        if self._parmi(self._validees, self._index_validees, centre, rayon):
            return True
        return (self._parmi(self._formes, self._index_formes, centre, rayon)
                and self._au_bout_d_un_axe(centre, rayon))


def _poteaux_ronds(membres: list[list[int]], formes: list[Forme], grille: Grille,
                   tolerances: Tolerances, pleins: tuple[IndexSpatial, list[int]]) -> int:
    """Combien de membres distincts ressemblent à un poteau rond : un nœud dans
    le cercle, aucun autre membre à moins d'un demi-entraxe, un contour rempli
    de même centre et même taille (``docs/GEOMETRIE_D_ABORD_G3.md`` § 2.6)."""
    entraxe = grille.entraxe_median()
    if not grille.noeuds or not entraxe:
        return 0
    index_noeuds = _index_des_noeuds(grille, tolerances)
    centres = [_centre_et_taille(formes[m[0]])[0] for m in membres]
    voisins = IndexSpatial(0.5 * entraxe)
    for c in centres:
        voisins.ajouter((c[0], c[1], c[0], c[1]))
    index_pleins, rangs_pleins = pleins
    ronds = 0
    for rang, m in enumerate(membres):
        forme = formes[m[0]]
        c, taille = centres[rang], 2.0 * (forme.rayon or 0.0)
        seuil = max(5.0 * tolerances.longueur, ECART_RELATIF * taille)
        if _noeud_proche(c, 0.5 * taille, grille, forme.points, tolerances, index_noeuds) is None:
            continue
        if any(k != rang and distance(centres[k], c) < 0.5 * entraxe
               for k in voisins.pres_de((c[0], c[1], c[0], c[1]), marge=0.5 * entraxe)):
            continue
        boite = (c[0] - taille / 2, c[1] - taille / 2, c[0] + taille / 2, c[1] + taille / 2)
        for k in index_pleins.pres_de(boite, marge=seuil):
            cp, tp = _centre_et_taille(formes[rangs_pleins[k]])
            if distance(cp, c) <= seuil and abs(tp - taille) <= seuil:
                ronds += 1
                break
    return ronds


def _signature_p(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                 formes: list[Forme]) -> _SignatureP:
    """Les classes de diamètre des cercles, leur verdict, et les germes des classes P."""
    cercles = sorted((i for i, f in enumerate(formes) if f.genre == "cercle" and f.rayon),
                     key=lambda i: (formes[i].rayon, i))
    classes: list[list[int]] = []
    for i in cercles:
        if classes and formes[i].rayon <= formes[classes[-1][0]].rayon * (1.0 + ECART_DIAMETRE_P):
            classes[-1].append(i)
        else:
            classes.append([i])
    entraxe = grille.entraxe_median()
    bulles = _Bulles(prims, tolerances, grille)
    pleins: tuple[IndexSpatial, list[int]] | None = None
    germes: dict[int, float] = {}
    lues: list[dict[str, Any]] = []
    for rangs in classes:
        membres = _distincts(rangs, formes, tolerances)
        if len(membres) < MEMBRES_P:
            continue
        diametre = 2.0 * (formes[rangs[0]].rayon or 0.0)
        plausible = _plausible(diametre, tolerances, entraxe)
        if plausible is None:
            verdict = "diametre_non_verifiable"
        elif not plausible:
            verdict = "diametre_hors_bornes"
        elif sum(1 for m in membres if any(bulles.contient(*_centre_et_rayon(formes[i]))
                                           for i in m)) >= PART_BULLES * len(membres):
            verdict = "bulles"
        else:
            if pleins is None:
                rangs_pleins = [k for k, f in enumerate(formes) if f.rempli and f.points]
                index_pleins = IndexSpatial(max(10.0 * tolerances.longueur, diametre))
                for k in rangs_pleins:
                    index_pleins.ajouter(boite_de(formes[k].points))
                pleins = (index_pleins, rangs_pleins)
            ronds = _poteaux_ronds(membres, formes, grille, tolerances, pleins)
            verdict = "poteaux_ronds" if ronds >= PART_POTEAUX_RONDS * len(membres) else "pieux"
        if verdict == "pieux":
            germes.update(dict.fromkeys(rangs, diametre))
        lues.append({"diameter": quantifier(diametre, tolerances.quantum), "circles": len(rangs),
                     "distinct": len(membres), "verdict": verdict})
    return _SignatureP(germes, lues)


def _centre_et_rayon(forme: Forme) -> tuple[Point, float]:
    centre, taille = _centre_et_taille(forme)
    return centre, taille / 2.0


def _corroborations(membres: Iterable[int], formes: list[Forme],
                    prims: PrimitivesDxf) -> tuple[str, ...]:
    """Les critères N1 vus, jamais décisifs : un cercle tracé en tirets (le
    motif, pas le nom), un contour rempli dans le dessin du pieu."""
    membres = list(membres)
    vus: list[str] = []
    for i in membres:
        for p in formes[i].primitives:
            motif = prims.motif_de(p.type_ligne) if isinstance(p, Cercle) else None
            if motif is not None and motif.classe == "tirets":
                vus.append("motif_tirets")
                break
        if vus:
            break
    if any(formes[i].rempli for i in membres):
        vus.append("rempli")
    return tuple(vus)


def detecter_pieux(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                   formes: list[Forme]) -> DetectionPieux:
    # LA SIGNATURE P, SUR UN DXF : une feuille PDF n'a ni motif, ni remplissage,
    # ni blocs, et ses cercles répétés ne sont pas des pieux.
    signature = (_signature_p(prims, tolerances, grille, formes) if prims.cadre is None
                 else _SignatureP({}, []))
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

    # 1-2. LES GERMES, LE CERCLE AVANT LE CONTOUR, ET LEURS DOUBLONS : LES GERMES
    # NOMMÉS D'ABORD, dans l'ordre d'aujourd'hui (un pieu reconnu par son nom
    # garde son représentant), PUIS LES GERMES GÉOMÉTRIQUES, qui les rejoignent
    # ou font des pieux nouveaux.
    def rang_de_germe(i: int) -> tuple[bool, float, int]:
        return (formes[i].genre != "cercle", -_centre_et_taille(formes[i])[1], i)

    nommes = [i for i, f in enumerate(formes) if f.classement.role == "pieu"]
    germes = sorted((i for i in nommes if not _hachure(formes[i])), key=rang_de_germe)
    germes += sorted(set(signature.germes) - set(germes), key=rang_de_germe)
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
            germes.append(i)
        else:
            fragments += 1
            pris.add(i)

    avec_conflits = _pieux(groupes, formes, grille, tolerances, prims, signature.germes)
    pieux = _reperes([p for p, _ in avec_conflits], prims.textes)
    doutes = [NonResolu(p.id, conflit) for p, (_, conflit) in zip(pieux, avec_conflits,
                                                                  strict=True) if conflit]
    diametres = Counter(str(quantifier(p.diametre, tolerances.quantum))
                        for p in pieux if p.diametre is not None)
    compte_rendu: dict[str, Any] = {
        "count": len(pieux), "by_diameter": dict(diametres.most_common()),
        "drawing_shapes_absorbed": absorbees, "drawing_fragments": fragments}
    if pieux:
        compte_rendu["by_rule"] = dict(sorted(Counter(p.preuve.regle for p in pieux).items()))
    if signature.classes:
        compte_rendu["diameter_classes"] = signature.classes
    return DetectionPieux(pieux, pris, compte_rendu, set(germes), doutes)


def _concordant(membres: list[int], formes: list[Forme]) -> Classement | None:
    """Le nom de pieu qui confirme : celui du représentant s'il est nommé, sinon
    le premier membre nommé."""
    return next((formes[i].classement for i in membres if formes[i].classement.role == "pieu"),
                None)


def _pieux(groupes: list[_Groupe], formes: list[Forme], grille: Grille,
           tolerances: Tolerances, prims: PrimitivesDxf, geometriques: dict[int, float]
           ) -> list[tuple[Pieu, str | None]]:
    """Les pieux, rangés et nommés, chacun avec son conflit nom / signature."""
    index_noeuds = _index_des_noeuds(grille, tolerances)
    pieux: list[tuple[Pieu, str | None]] = []
    for g in groupes:
        forme = g.forme
        classement = formes[g.membres[0]].classement
        primitives = [p for i in g.membres for p in formes[i].primitives]
        vus = _corroborations(g.membres, formes, prims)
        geo = [i for i in g.membres if i in geometriques]
        conflit: str | None = None
        confiance = CONFIANCE_PIEU
        if geo:
            # L'ÉCHELLE DE PREUVES : la signature décide ; un nom de pieu confirme
            # (+ 0,05) ; un nom d'un autre rôle est un conflit dit (0,4).
            nom = _concordant(g.membres, formes)
            if nom is not None:
                confiance = CONFIANCE_CONCORDANTE
            autre = next((formes[i].classement for i in geo
                          if formes[i].classement.role not in _ABSORBABLES), None)
            if autre is not None:
                confiance = min(confiance, PLAFOND_CONFLIT)
                conflit = (f"signature geometrique de pieu (classe de diametre "
                           f"{quantifier(geometriques[geo[0]], tolerances.quantum)}) sur un "
                           f"cercle nomme d'un autre role: {autre.role} ({autre.motif}); le "
                           f"pieu est garde, sa confiance plafonnee a 0,4")
            preuve = preuve_de(primitives, "geometrie", nom.motif if nom else None,
                               ("classe_de_diametre", *vus))
        else:
            regle = classement.regle if classement.role == "pieu" else "forme"
            preuve = preuve_de(primitives, regle,
                               classement.motif if classement.role == "pieu" else None, vus)
        diametre = largeur = profondeur = None
        if forme.genre == "cercle":
            diametre = g.taille
        else:
            rect = rectangle_de(forme.points, tolerances)
            if rect is not None:
                largeur, profondeur = rect.longueur_u, rect.longueur_v
        noeud = _noeud_proche(g.centre, 0.5 * g.taille, grille, forme.points, tolerances,
                              index_noeuds)
        pieux.append((Pieu(id="", forme=forme.genre if forme.genre != "polygone"
                           or largeur is None else "rectangle", contour=forme.points,
                           centre=g.centre, diametre=diametre, largeur=largeur,
                           profondeur=profondeur, noeud=noeud, preuve=preuve,
                           confiance=confiance), conflit))
    pieux.sort(key=lambda pc: (pc[0].noeud is None, pc[0].noeud or "",
                               round(pc[0].centre[1], 6), round(pc[0].centre[0], 6)))
    vus: dict[str, int] = {}
    nommes: list[tuple[Pieu, str | None]] = []
    for rang, (p, conflit) in enumerate(pieux, start=1):
        base = f"pile:{p.noeud}" if p.noeud else f"pile:{rang}"
        if base in vus:
            vus[base] += 1
            base = f"{base}#{vus[base]}"
        else:
            vus[base] = 1
        nommes.append((replace(p, id=base), conflit))
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
