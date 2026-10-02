"""Les files : axes de la grille, leurs étiquettes, leurs familles, leurs nœuds.

UN AXE EST UNE DROITE, PAS UN TRAIT. Un axe dessiné en trois morceaux reste un
axe ; deux axes parallèles à 600 cm l'un de l'autre sont à 600 cm partout —
c'est la distance entre deux droites parallèles, exacte, que l'entraxe cite.

L'ÉTIQUETTE EST LUE LÀ OÙ LE DESSIN LA MET : dans une bulle (cercle centré sur
le prolongement de l'axe), dans un bloc de bulle (attribut), ou dans un texte
court posé dans le prolongement. Une bulle ou un bloc l'emporte sur un texte
libre, qui est cité comme écarté ; un texte libre bien plus grand ou plus petit
que les étiquettes en bulle du dessin n'est pas une étiquette. Deux extrémités
qui portent deux étiquettes différentes de MÊME force ne sont pas départagées :
l'axe reste sans étiquette, et c'est signalé. Un pieu n'est jamais une bulle.

UNE ÉTIQUETTE EN LETTRES ET CHIFFRES (« L1 »… « L10 », une seconde grille sur
le même dessin) n'est lue que dans une bulle ou un bloc de bulle, jamais comme
texte libre, ni dans un cercle ou un texte de cartouche ; et seulement là où
aucune étiquette de forme courante n'est candidate : elle complète, elle ne
remplace ni ne contredit jamais une étiquette courante — écartée, elle est
citée. Voir ``docs/GEOMETRIE_BULLES_LETTRES_CHIFFRES.md``.

UN TRAIT PLUS COURT QUE LE SEUIL (un dixième de la diagonale du dessin, pour un
trait nommé axe par son calque ou son bloc) n'est un axe que sur une preuve
qui n'est pas une longueur : il finit sur une bulle étiquetée, mesure au moins
dix rayons de cette bulle, partage sa direction avec un autre axe — et cette
bulle l'étiquette. Sinon il est retiré, et tout est relu sans lui. Il le dit
dans ``label_source.admitted``. Voir ``docs/GEOMETRIE_SEUIL_DES_AXES.md``.

GRILLE POLAIRE OU COURBE : non prise en charge. Seules les droites sont des
axes ; trois directions ou plus portant chacune UN axe, concourants en un même
point, sont une grille rayonnante : elle est nommée dans ``unresolved`` et ses
axes sont écartés — ni files, ni nœuds, ni étiquettes absorbées.

LA GÉOMÉTRIE D'ABORD (``docs/GEOMETRIE_D_ABORD_G2.md``). Sur un DXF, les droites
de SIGNATURE complète (``axes_geometriques.py`` : A, une bulle au bout et une
famille ; B, un trait-point parallèle à une famille, dans la zone) sont des
axes même sans aucun nom. Un axe reconnu par son nom le reste, avec ses traits
et son étendue ; si une signature complète le confirme, la décision devient
``geometrie`` (le nom cité, + 0,05). Une droite de signature complète que rien
ne nomme est ajoutée ; nommée d'un AUTRE rôle, elle l'est aussi, le conflit dit
et la confiance plafonnée à 0,4. Une feuille PDF garde ses styles appris.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final

from .axes_geometriques import TEXTE_COURT, Bulle, Droite, SignaturesAxes, signatures_d_axes
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
from .primitives import Cercle, Insertion, PrimitivesDxf, Segment, Texte

__all__ = ["ETIQUETTE_AXE", "ETIQUETTE_LETTRES_CHIFFRES", "detecter_axes"]

#: « A », « AA », « A' », « 1 », « 12 », « 1' » — et rien de plus long.
ETIQUETTE_AXE: Final[re.Pattern[str]] = re.compile(r"[A-Z]{1,2}'?|\d{1,3}'?")
#: « L1 », « L10 », « AB12 », « L1' » : des lettres puis des chiffres. Lue
#: seulement dans une bulle ou un bloc de bulle, en complément (voir plus haut).
ETIQUETTE_LETTRES_CHIFFRES: Final[re.Pattern[str]] = re.compile(r"[A-Z]{1,2}\d{1,3}'?")

#: Ecart angulaire minimal entre deux familles pour qu'elles se croisent.
_ANGLE_FAMILLES_MIN: Final[float] = 10.0
#: UN TRAIT D'AXE PLUS COURT QUE LE SEUIL reste un axe s'il finit sur une bulle
#: étiquetée et mesure au moins ce nombre de rayons de cette bulle : un trait de
#: rappel vers une bulle déportée (quelques rayons) n'en est pas un.
#: Voir ``docs/GEOMETRIE_SEUIL_DES_AXES.md``.
RAYONS_MIN_AXE_COURT: Final[float] = 10.0
#: Ni une bulle, ni la preuve d'un axe court : un pieu, un massif, un cartouche.
_JAMAIS_BULLE: Final[frozenset[str]] = frozenset({"pieu", "fondation", "cadre"})
#: Confiance d'un axe de signature complète (``GEOMETRIE_D_ABORD_G2.md`` § 2.8) :
#: étiqueté par une bulle ou un bloc, par un texte libre, sans étiquette ; un nom
#: concordant ajoute 0,05 (plafond 0,90) ; un nom d'un autre rôle plafonne à 0,4.
_CONFIANCE_SIGNATURE: Final[dict[str | None, float]] = {"bulle": 0.85, "bloc": 0.85,
                                                        "texte": 0.75, None: 0.6}
_NOM_CONCORDANT: Final[float] = 0.05
_PLAFOND_AXE: Final[float] = 0.90
_PLAFOND_CONFLIT: Final[float] = 0.4


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
    #: Pour une ligne faite SEULEMENT de traits courts gardés par leur bulle :
    #: la règle, leurs longueurs, le seuil. ``None`` si un trait a passé le seuil.
    admise: dict[str, Any] | None = None
    #: G2 : les critères géométriques vus ; ``complete`` si une signature A ou B
    #: a décidé ; le nom qui concorde (motif) ; le rôle d'un nom qui contredit.
    signature: set[str] = field(default_factory=set)
    complete: bool = False
    concordant: str | None = None
    conflit: str | None = None


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


def _ligne_de(s: Segment, theta: float, u: Point, regle: str, motif: str | None,
              admise: dict[str, Any] | None = None) -> _Ligne:
    n = normale(u)
    decalage = s.a[0] * n[0] + s.a[1] * n[1]
    ta, tb = s.a[0] * u[0] + s.a[1] * u[1], s.b[0] * u[0] + s.b[1] * u[1]
    return _Ligne(theta, u, decalage, min(ta, tb), max(ta, tb), [s], regle, motif, admise)


def _lignes_candidates(prims: PrimitivesDxf, tolerances: Tolerances,
                       diagonale: float) -> list[_Ligne]:
    lignes: list[_Ligne] = []
    seuil_nomme = max(10.0 * tolerances.longueur, 0.1 * diagonale)
    courts: list[tuple[Segment, float, Point, str, str | None]] = []
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
                 else seuil_nomme)
        canon = _direction_canonique(s.a, s.b, tolerances)
        if canon is None:
            continue
        theta, u = canon
        if s.longueur < seuil:
            if classement.regle in ("calque", "bloc"):
                courts.append((s, theta, u, classement.regle, classement.motif))
            continue
        lignes.append(_ligne_de(s, theta, u, classement.regle, classement.motif))
    lignes.extend(_courtes_a_bulle(courts, prims, tolerances, [x.theta for x in lignes],
                                   seuil_nomme))
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
                if ligne.admise is None or cible.admise is None:
                    # Un morceau admis par le seuil suffit à faire la ligne.
                    cible.admise = None
                else:
                    cible.admise = {**cible.admise, "lengths": sorted(
                        cible.admise["lengths"] + ligne.admise["lengths"], reverse=True)}
                break
        else:
            fusionnees.append(ligne)
    return fusionnees


def _courtes_a_bulle(courts: list[tuple[Segment, float, Point, str, str | None]],
                     prims: PrimitivesDxf, tolerances: Tolerances,
                     thetas_admis: list[float], seuil: float) -> list[_Ligne]:
    """Les traits nommés axe, plus courts que le seuil, gardés par leur bulle.

    Trois conditions, toutes : le trait finit sur une BULLE ÉTIQUETÉE (cercle
    centré sur son prolongement, à son bout, texte d'étiquette dedans ; ni pieu,
    ni massif, ni cartouche) ; il mesure au moins ``RAYONS_MIN_AXE_COURT`` rayons
    de cette bulle ; sa DIRECTION est partagée par un axe admis par le seuil ou
    par un autre trait gardé ainsi. ``detecter_axes`` retire ensuite la ligne si
    elle n'est pas étiquetée par une bulle."""
    if not courts:
        return []
    etiquettes = [t for t in prims.textes
                  if (ETIQUETTE_AXE.fullmatch(t.texte.strip())
                      or ETIQUETTE_LETTRES_CHIFFRES.fullmatch(t.texte.strip()))
                  and classer(t.calque, t.source.blocs, t.type_ligne).role not in _JAMAIS_BULLE]
    if not etiquettes:
        return []
    bulles = [c for c in prims.cercles
              if classer(c.calque, c.source.blocs, c.type_ligne).role not in _JAMAIS_BULLE]

    def rayon_de_bulle(s: Segment, u: Point) -> float | None:
        t_a, t_b = projeter(s.a, s.a, u), projeter(s.b, s.a, u)
        for t_bout, sens in ((min(t_a, t_b), -1.0), (max(t_a, t_b), 1.0)):
            for c in bulles:
                r = c.rayon
                if distance_point_droite(c.centre, s.a, u) > max(0.25 * r, 1e-9):
                    continue
                if not -r <= (projeter(c.centre, s.a, u) - t_bout) * sens <= 4.0 * r:
                    continue
                if any(distance(t.centre, c.centre) <= r for t in etiquettes):
                    return r
        return None

    gardes: list[tuple[Segment, float, Point, str, str | None]] = []
    for s, theta, u, regle, motif in courts:
        r = rayon_de_bulle(s, u)
        if r is not None and s.longueur >= RAYONS_MIN_AXE_COURT * r:
            gardes.append((s, theta, u, regle, motif))
    lignes: list[_Ligne] = []
    for s, theta, u, regle, motif in gardes:
        appuis = thetas_admis + [g[1] for g in gardes if g[0] is not s]
        if not any(ecart_angulaire(theta, t) <= tolerances.parallele_deg for t in appuis):
            continue
        lignes.append(_ligne_de(s, theta, u, regle, motif, {
            "rule": "trait d'axe plus court que le seuil, termine par sa bulle etiquetee",
            "lengths": [round(s.longueur, 4)], "threshold": round(seuil, 4)}))
    return lignes


@dataclass(frozen=True)
class _Candidat:
    texte: str
    poignee: str
    via: str
    distance: float
    #: La hauteur du texte, quand l'étiquette est un texte (bulle ou libre).
    hauteur: float | None = None
    #: « L1 »… : lettres et chiffres, lue en complément (rang toujours inférieur).
    alphanumerique: bool = False
    #: Un texte court hors format (« a », « A.1 ») dans une bulle : en complément.
    hors_format: bool = False


#: UNE BULLE OU UN BLOC EST UNE PREUVE PLUS FORTE QU'UN TEXTE LIBRE : un cercle
#: centré sur le prolongement de l'axe, l'étiquette dedans. Entre deux preuves
#: de forces différentes, la plus forte l'emporte et l'autre est citée ; entre
#: deux preuves de même force qui se contredisent, l'axe reste sans étiquette.
_FORCE: Final[dict[str, int]] = {"bulle": 2, "bloc": 2, "texte": 1}
#: Quand le dessin a des étiquettes en bulle, un texte libre n'est candidat que
#: si sa hauteur est entre la moitié et le double de leur hauteur médiane : la
#: lettre de 54 pt d'un noyau d'ascenseur n'étiquette pas un axe dont les
#: bulles portent des lettres de 16 pt.
_HAUTEUR_LIBRE: Final[tuple[float, float]] = (0.5, 2.0)


def _rang(candidat: _Candidat) -> tuple[int, int]:
    """Une étiquette de forme courante l'emporte toujours sur une étiquette en
    lettres et chiffres ou hors format ; à forme égale, une bulle ou un bloc sur
    un texte libre."""
    return (0 if candidat.alphanumerique or candidat.hors_format else 1, _FORCE[candidat.via])


def _etiquettes_possibles(ligne: _Ligne, cercles: list[Cercle], courts: list[Texte],
                          bulles_bloc: list[tuple[Insertion, str]],
                          hauteur_type: float, *, textes_libres: bool = True,
                          formes: Sequence[Bulle] = ()) -> list[tuple[int, _Candidat]]:
    """Les étiquettes candidates, pour chaque extrémité (0 : début, 1 : fin).

    ``formes`` : des bulles par leur structure (G2) dont le texte est déjà lu —
    polygones réguliers, bulles-blocs —, posées comme un cercle."""
    origine = (ligne.decalage * normale(ligne.u)[0], ligne.decalage * normale(ligne.u)[1])
    trouves: list[tuple[int, _Candidat]] = []
    for bout, t_bout, sens in ((0, ligne.debut, -1.0), (1, ligne.fin, 1.0)):
        extremite = (origine[0] + t_bout * ligne.u[0], origine[1] + t_bout * ligne.u[1])
        # (a) une bulle: un cercle centré sur le prolongement, un texte dedans.
        for cercle in cercles:
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
                                                "bulle", distance(extremite, cercle.centre),
                                                texte.hauteur)))
        # (b) un bloc de bulle et son attribut.
        for insertion, valeur in bulles_bloc:
            if distance_point_droite(insertion.point, origine, ligne.u) > 2.0 * hauteur_type:
                continue
            au_dela = (projeter(insertion.point, origine, ligne.u) - t_bout) * sens
            if not -2.0 * hauteur_type <= au_dela <= 8.0 * hauteur_type:
                continue
            trouves.append((bout, _Candidat(valeur, insertion.source.poignee, "bloc",
                                            distance(extremite, insertion.point))))
        # (b') une bulle par sa structure : polygone régulier, bulle-bloc.
        for bulle in formes:
            r = bulle.rayon
            if distance_point_droite(bulle.centre, origine, ligne.u) > max(0.25 * r, 1e-9):
                continue
            au_dela = (projeter(bulle.centre, origine, ligne.u) - t_bout) * sens
            if not -r <= au_dela <= 4.0 * r:
                continue
            trouves.append((bout, _Candidat(bulle.texte, bulle.poignee,
                                            "bloc" if bulle.forme == "bloc" else "bulle",
                                            distance(extremite, bulle.centre), bulle.hauteur)))
        # (c) un texte court posé dans le prolongement.
        for texte in (courts if textes_libres else ()):
            h = texte.hauteur
            if distance_point_droite(texte.centre, origine, ligne.u) > 1.5 * h:
                continue
            au_dela = (projeter(texte.centre, origine, ligne.u) - t_bout) * sens
            if not -h <= au_dela <= 4.0 * h:
                continue
            trouves.append((bout, _Candidat(texte.texte.strip(), texte.source.poignee,
                                            "texte", distance(extremite, texte.centre) + h, h)))
    return trouves


def detecter_axes(prims: PrimitivesDxf, tolerances: Tolerances
                  ) -> tuple[Grille, set[str], list[NonResolu]]:
    """La grille du dessin, les poignées d'étiquettes absorbées, et les doutes."""
    # UNE FEUILLE PDF reconnaît déjà ses axes par le style appris de ses bulles
    # (GEOMETRIE_D_ABORD_G2.md, J3) : les signatures ne regardent qu'un DXF.
    geo = signatures_d_axes(prims, tolerances) if prims.cadre is None else None
    return _detecter(prims, tolerances, frozenset(), geo)


def _cle(ligne: _Ligne) -> tuple[float, float, float, float]:
    return (ligne.theta, ligne.decalage, ligne.debut, ligne.fin)


def _coincide(ligne: _Ligne, droite: Droite, tolerances: Tolerances) -> bool:
    """La même droite infinie : un axe est une droite, pas un trait."""
    return (ecart_angulaire(ligne.theta, droite.theta) <= tolerances.parallele_deg
            and abs(ligne.decalage - droite.decalage) <= 2.0 * tolerances.longueur)


def _avec_signatures(lignes: list[_Ligne], geo: SignaturesAxes, prims: PrimitivesDxf,
                     tolerances: Tolerances) -> list[_Ligne]:
    """L'ÉCHELLE DE PREUVES, pour les axes (GEOMETRIE_D_ABORD_G2.md § 2.6).

    Une droite de signature complète qui coïncide avec un axe nommé le confirme :
    l'axe nommé garde ses traits et son étendue, la décision devient géométrique,
    son nom concorde. Une droite de signature complète que rien ne nomme est
    ajoutée ; nommée d'un autre rôle, elle l'est aussi, et le conflit sera dit.
    Un axe nommé sans signature complète cite les critères qu'il a seuls."""
    sortie = list(lignes)
    for droite in geo.droites:
        cible = next((x for x in lignes if _coincide(x, droite, tolerances)), None)
        if cible is not None:
            cible.complete = True
            cible.signature |= droite.signature
            cible.concordant = cible.motif or ""
            continue
        ajoutee = _Ligne(droite.theta, droite.u, droite.decalage, droite.debut, droite.fin,
                         list(droite.segments), "geometrie", None, None,
                         set(droite.signature), True)
        for s in droite.segments:
            classement = classer(s.calque, s.source.blocs, s.type_ligne)
            if classement.role == "axe":
                ajoutee.concordant = classement.motif or ""
                ajoutee.conflit = None
                break
            if classement.role != "inconnu" and ajoutee.conflit is None:
                ajoutee.conflit = f"{classement.role} ({classement.motif})"
        sortie.append(ajoutee)
    for ligne in lignes:
        if not ligne.complete:
            ligne.signature = geo.criteres(ligne.theta, ligne.u, ligne.decalage, ligne.debut,
                                           ligne.fin, ligne.segments, prims)
    return sortie


def _detecter(prims: PrimitivesDxf, tolerances: Tolerances,
              sans: frozenset[tuple[float, float, float, float]],
              geo: SignaturesAxes | None = None
              ) -> tuple[Grille, set[str], list[NonResolu]]:
    emprise = prims.emprise()
    if emprise is None:
        return Grille(), set(), []
    diagonale = math.hypot(emprise[2] - emprise[0], emprise[3] - emprise[1])
    lignes = [x for x in _lignes_candidates(prims, tolerances, diagonale) if _cle(x) not in sans]
    if geo is not None:
        lignes = _avec_signatures(lignes, geo, prims, tolerances)
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

    # UN PIEU N'EST PAS UNE BULLE: un pieu numéroté au bout d'une file de pieux
    # n'étiquette pas un axe.
    cercles = [c for c in prims.cercles
               if classer(c.calque, c.source.blocs, c.type_ligne).role not in ("pieu",
                                                                              "fondation")]
    # G2 : UN CERCLE D'UNE CLASSE ÉCARTÉE (pieux numérotés, repères de locaux :
    # nombreux, loin des bouts de droites) n'étiquette pas un axe — sauf si son
    # nom dit « axe » : le nom complète, comme avant G2.
    if geo is not None and geo.ecartees:
        ecartes = {id(b.contour) for b in geo.ecartees}
        cercles = [c for c in cercles if id(c) not in ecartes
                   or classer(c.calque, c.source.blocs, c.type_ligne).role == "axe"]

    # G2 : LES BULLES PAR LEUR STRUCTURE — polygones réguliers et bulles-blocs,
    # quel que soit leur nom — étiquettent comme un cercle ; un pieu n'en est
    # jamais une.
    def pas_un_pieu(bulle: Bulle) -> bool:
        c = bulle.contour
        return classer(c.calque, c.source.blocs, c.type_ligne).role not in ("pieu", "fondation")

    structurelles = [b for b in (geo.bulles if geo is not None else ()) if pas_un_pieu(b)]
    formes = [b for b in structurelles
              if b.forme != "cercle" and ETIQUETTE_AXE.fullmatch(b.texte)]
    # L'AFFECTATION DES ETIQUETTES EST GLOBALE: un texte sert un seul axe, le
    # plus proche.
    propositions: list[tuple[float, int, int, _Candidat]] = []
    for rang, ligne in enumerate(lignes):
        for bout, candidat in _etiquettes_possibles(ligne, cercles, courts, bulles_bloc,
                                                    hauteur_type, formes=formes):
            propositions.append((candidat.distance, rang, bout, candidat))
    hauteurs_bulles = sorted(c.hauteur for *_, c in propositions
                             if c.via == "bulle" and c.hauteur)
    if hauteurs_bulles:
        h_bulle = hauteurs_bulles[len(hauteurs_bulles) // 2]
        bas, haut = _HAUTEUR_LIBRE[0] * h_bulle, _HAUTEUR_LIBRE[1] * h_bulle
        propositions = [x for x in propositions if x[3].via != "texte"
                        or (x[3].hauteur is not None and bas <= x[3].hauteur <= haut)]
    propositions.sort(key=lambda x: (x[0], x[1], x[2], x[3].poignee))
    par_bout: dict[tuple[int, int], _Candidat] = {}
    utilisees: set[str] = set()
    for _, rang, bout, candidat in propositions:
        if (rang, bout) in par_bout or (candidat.poignee and candidat.poignee in utilisees):
            continue
        par_bout[(rang, bout)] = candidat
        if candidat.poignee:
            utilisees.add(candidat.poignee)

    # LES ÉTIQUETTES EN LETTRES ET CHIFFRES COMPLÈTENT, ELLES NE REMPLACENT RIEN :
    # lues seulement dans une bulle ou un bloc de bulle (jamais en texte libre),
    # jamais dans un cercle ou un texte de cartouche, et seulement à une
    # extrémité qui n'a aucune étiquette de forme courante.
    def hors_cartouche(p: Cercle | Texte) -> bool:
        return classer(p.calque, p.source.blocs, p.type_ligne).role != "cadre"

    mixtes = [t for t in prims.textes
              if ETIQUETTE_LETTRES_CHIFFRES.fullmatch(t.texte.strip()) and hors_cartouche(t)]
    blocs_mixtes: list[tuple[Insertion, str]] = []
    for insertion in prims.insertions:
        if role_du_nom(insertion.nom_bloc) != "axe" or any(
                ETIQUETTE_AXE.fullmatch(v.strip()) for _, v in insertion.attributs):
            continue
        valeurs = [v.strip() for _, v in insertion.attributs
                   if ETIQUETTE_LETTRES_CHIFFRES.fullmatch(v.strip())]
        if valeurs:
            blocs_mixtes.append((insertion, valeurs[0]))
    formes_mixtes = [b for b in structurelles
                     if b.forme != "cercle" and ETIQUETTE_LETTRES_CHIFFRES.fullmatch(b.texte)
                     and hors_cartouche(b.contour)]
    if mixtes or blocs_mixtes or formes_mixtes:
        bulles = [c for c in cercles if hors_cartouche(c)]
        complements: list[tuple[float, int, int, _Candidat]] = []
        for rang, ligne in enumerate(lignes):
            for bout, candidat in _etiquettes_possibles(ligne, bulles, mixtes, blocs_mixtes,
                                                        hauteur_type, textes_libres=False,
                                                        formes=formes_mixtes):
                complements.append((candidat.distance, rang, bout,
                                    replace(candidat, alphanumerique=True)))
        complements.sort(key=lambda x: (x[0], x[1], x[2], x[3].poignee))
        for _, rang, bout, candidat in complements:
            if (rang, bout) in par_bout or (candidat.poignee and candidat.poignee in utilisees):
                continue
            par_bout[(rang, bout)] = candidat
            if candidat.poignee:
                utilisees.add(candidat.poignee)

    # G2 : UN TEXTE COURT HORS FORMAT DANS UNE BULLE (« a », « A.1 », « 1a ») est
    # lu tel quel, EN COMPLÉMENT comme « L1 » : jamais contre une étiquette de
    # forme courante, jamais hors d'une bulle, jamais dans un cartouche.
    hors_format = [b for b in structurelles
                   if not ETIQUETTE_AXE.fullmatch(b.texte)
                   and not ETIQUETTE_LETTRES_CHIFFRES.fullmatch(b.texte)
                   and TEXTE_COURT.fullmatch(b.texte) and hors_cartouche(b.contour)]
    if hors_format:
        complements_hf: list[tuple[float, int, int, _Candidat]] = []
        for rang, ligne in enumerate(lignes):
            for bout, candidat in _etiquettes_possibles(ligne, [], [], [], hauteur_type,
                                                        textes_libres=False,
                                                        formes=hors_format):
                complements_hf.append((candidat.distance, rang, bout,
                                       replace(candidat, hors_format=True)))
        complements_hf.sort(key=lambda x: (x[0], x[1], x[2], x[3].poignee))
        for _, rang, bout, candidat in complements_hf:
            if (rang, bout) in par_bout or (candidat.poignee and candidat.poignee in utilisees):
                continue
            par_bout[(rang, bout)] = candidat
            if candidat.poignee:
                utilisees.add(candidat.poignee)

    doutes: list[NonResolu] = []
    etiquettes: list[tuple[str | None, dict[str, Any] | None]] = []
    for rang in range(len(lignes)):
        a, b = par_bout.get((rang, 0)), par_bout.get((rang, 1))
        ecarte: _Candidat | None = None
        if a and b and a.texte != b.texte:
            if _rang(a) == _rang(b):
                doutes.append(NonResolu(f"axe {rang + 1}", (
                    f"etiquettes contradictoires aux deux extremites: « {a.texte} » "
                    f"({a.via}) et « {b.texte} » ({b.via}), preuves de meme force; "
                    "l'axe reste sans etiquette")))
                etiquettes.append((None, None))
                continue
            if _rang(a) < _rang(b):
                a, b = b, a
            ecarte, b = b, None
        choisi = a or b
        source: dict[str, Any] | None = None
        if choisi:
            source = {"via": choisi.via, "handle": choisi.poignee}
            if choisi.alphanumerique:
                source["form"] = "lettres_et_chiffres"
            elif choisi.hors_format:
                source["form"] = "texte_court"
            if ecarte is not None:
                source["discarded"] = {
                    "text": ecarte.texte, "via": ecarte.via, "handle": ecarte.poignee,
                    "reason": (f"« {ecarte.texte} » ({ecarte.via}, lettres et chiffres) a "
                               "l'autre extremite: une etiquette de forme courante l'emporte"
                               if ecarte.alphanumerique else
                               f"« {ecarte.texte} » ({ecarte.via}, texte court hors format) a "
                               "l'autre extremite: une etiquette de forme courante l'emporte"
                               if ecarte.hors_format else
                               f"« {ecarte.texte} » ({ecarte.via}) a l'autre extremite: une "
                               f"{choisi.via} l'emporte sur un texte libre")}
            if lignes[rang].admise is not None:
                source["admitted"] = lignes[rang].admise
        etiquettes.append((choisi.texte, source) if choisi else (None, None))

    # UN TRAIT COURT GARDÉ PAR SA BULLE N'EST UN AXE QUE S'IL EN PORTE L'ÉTIQUETTE :
    # une bulle prise par un autre axe, deux bulles qui se contredisent, ou une
    # étiquette venue d'ailleurs ne font pas un axe d'un trait sous le seuil. Il
    # est retiré, et tout est relu sans lui : ce qu'il avait pris revient aux autres.
    retirees = frozenset(_cle(ligne) for rang, ligne in enumerate(lignes)
                         if ligne.admise is not None and not ligne.complete
                         and (etiquettes[rang][1] or {}).get("via") != "bulle")
    if retirees:
        return _detecter(prims, tolerances, sans | retirees, geo)

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
            if ligne.complete:
                # LA SIGNATURE A DÉCIDÉ (GEOMETRIE_D_ABORD_G2.md § 2.8).
                via = (origine_etiquette or {}).get("via") if etiquette else None
                confiance = _CONFIANCE_SIGNATURE.get(via, _CONFIANCE_SIGNATURE["texte"])
                if ligne.concordant is not None:
                    confiance = min(round(confiance + _NOM_CONCORDANT, 2), _PLAFOND_AXE)
                if ligne.conflit is not None:
                    confiance = min(confiance, _PLAFOND_CONFLIT)
                    doutes.append(NonResolu(ident, (
                        f"signature geometrique complete ({', '.join(sorted(ligne.signature))}) "
                        f"sur un trait nomme d'un autre role: {ligne.conflit}; l'axe est garde, "
                        "sa confiance plafonnee a 0,4")))
                preuve = preuve_de(ligne.segments, "geometrie", ligne.concordant or None,
                                   ligne.signature)
            else:
                confiance = (0.85 if etiquette and ligne.regle != "type_de_ligne"
                             else 0.75 if etiquette else 0.6)
                preuve = preuve_de(ligne.segments, ligne.regle, ligne.motif, ligne.signature)
            axes.append(Axe(
                id=ident, etiquette=etiquette, famille=index_famille,
                origine=(ligne.decalage * n[0], ligne.decalage * n[1]), direction=ligne.u,
                decalage=ligne.decalage, debut=ligne.debut, fin=ligne.fin,
                preuve=preuve, confiance=confiance, etiquette_source=origine_etiquette))
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
    """« A » et « 1 » donnent « A1 » ; deux lettres ou deux chiffres, « A/B ».
    Une étiquette en lettres et chiffres garde le séparateur : « L10/3 », pas
    « L103 »."""
    if not a or not b:
        return None
    if ETIQUETTE_LETTRES_CHIFFRES.fullmatch(a) or ETIQUETTE_LETTRES_CHIFFRES.fullmatch(b):
        return f"{a}/{b}"
    if a[0].isalpha() and b[0].isdigit():
        return f"{a}{b}"
    if b[0].isalpha() and a[0].isdigit():
        return f"{b}{a}"
    return f"{a}/{b}"
