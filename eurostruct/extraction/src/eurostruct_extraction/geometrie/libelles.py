"""Les repères (P1, C1, V1…) : lus dans les textes, rattachés aux éléments.

L'AFFECTATION EST UN COÛT, PAS UNE DEVINETTE
---------------------------------------------
Pour chaque texte qui se lit comme un repère et chaque élément compatible :

    coût = distance(boîte du texte, élément) / hauteur du texte
         + 2   si le texte n'est pas parallèle à la poutre (à 10° près)
         + 1,5 si le préfixe suggère un autre type d'élément (C… pour une poutre)
         − 1   si la section écrite (« 30x60 ») concorde avec la largeur mesurée

Au-delà de six hauteurs de texte (ou deux tailles d'élément), aucun lien.
Les liens sont pris par coût croissant ; un texte sert une fois. Un texte
vertical est une étiquette comme une autre : le DXF la donne exacte.

UNE POUTRE PEUT PORTER PLUSIEURS REPÈRES : un par travée (P1 de A à B, P2 de B
à C sur un même rectangle). Un repère UNIQUE sur une poutre continue s'étend à
toutes ses travées, et le fondement le dit. Une travée sans repère reçoit un
repère de GRILLE (``1:A-B`` : file 1, de A à B) — jamais aucun, car une valeur
sans repère serait préremplie pour tous les éléments.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Final

from ..extracteurs.unites import Declaration, unite_declaree
from ..nombres import lire_nombre
from .modele import Grille, LibelleAffecte, Poteau, Poutre, Travee, Voile
from .noyau import (
    MM_PAR_UNITE,
    Point,
    Tolerances,
    angle_deg,
    distance_point_droite,
    distance_point_polygone,
    distance_point_segment,
    ecart_angulaire,
    point_dans_polygone,
    projeter,
)
from .primitives import Texte

__all__ = ["affecter_libelles", "lire_repere"]

_MOTS: Final[str] = (r"poutres?|poteaux?|voiles?|murs?|beams?|columns?|walls?|balken|balk|"
                     r"kolommen|kolom|wanden|wand|linteaux|linteau|lintels?")
_LIBELLE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:(?P<kw>" + _MOTS + r")\s+)?"
    r"(?P<lettres>[A-Za-z]{1,3})\s?[-.]?\s?(?P<num>\d{1,3}[a-z]?)(?![\d/,.]\d)(?![\d/])"
    r"(?:\s*[:(\[–-]?\s*(?P<a>\d{1,4}(?:[.,]\d+)?)\s*[x×X*/]\s*(?P<b>\d{1,4}(?:[.,]\d+)?)"
    r"\s*[)\]]?)?\b(?P<reste>.*)$", re.IGNORECASE)
#: Ce qui ressemble à un repère sans en être un : désignations et symboles.
_EXCLUS: Final[re.Pattern[str]] = re.compile(
    r"^(?:L?C\d{1,3}/\d{1,3}|B\d{3}[A-C]?|BE\s?\d{3}\s?S?|FE\s?E?\s?\d{3}|S\s?\d{3}|"
    r"HA\s?\d{1,2}|T\s?\d{1,2}|X[0CDSFA]\d?|R\s?[+\-]\s?\d{1,2}|N\s?[+\-]\s?\d{1,2}|"
    r"DN\s?\d+|IPE\s?\d+|HE[ABM]\s?\d+)\b", re.IGNORECASE)
_PREFIXES: Final[dict[str, str]] = {
    **{p: "poutre" for p in ("P", "B", "BM", "BA", "PT", "POU", "L", "LN", "LT", "R", "BK")},
    **{p: "poteau" for p in ("C", "K", "CO", "COL", "PO", "POT", "PC", "ST")},
    **{p: "voile" for p in ("V", "VO", "M", "MU", "W", "WA")},
}
_MOTS_GENRE: Final[tuple[tuple[str, str], ...]] = (
    ("pout", "poutre"), ("beam", "poutre"), ("balk", "poutre"), ("lint", "poutre"),
    ("linteau", "poutre"), ("pote", "poteau"), ("colu", "poteau"), ("kolo", "poteau"),
    ("voil", "voile"), ("mur", "voile"), ("wall", "voile"), ("wand", "voile"),
)
#: Au-delà, un texte n'est pas le repère d'un élément. Six hauteurs : une
#: étiquette posée sous un poteau, décalée d'un trait de rappel, reste lue.
DISTANCE_MAX_HAUTEURS: Final[float] = 6.0


def lire_repere(texte: str) -> dict[str, Any] | None:
    """« P1 30x60 » → repère, genre suggéré, section écrite ; ``None`` sinon."""
    plat = " ".join(texte.split())
    if not plat or _EXCLUS.match(plat):
        return None
    m = _LIBELLE.match(plat)
    if m is None:
        return None
    lettres = m.group("lettres").upper()
    marque = f"{lettres}{m.group('num').upper()}"
    if _EXCLUS.match(marque):
        return None
    genre_mot = None
    if m.group("kw"):
        mot = m.group("kw").lower()
        genre_mot = next((g for debut, g in _MOTS_GENRE if mot.startswith(debut)), None)
    section = None
    if m.group("a") and m.group("b"):
        section = (m.group("a"), m.group("b"))
    return {"marque": marque, "genre_mot": genre_mot,
            "genre_prefixe": _PREFIXES.get(lettres), "section": section}


def _egale(ecrit: str, mesure: float, tolerances: Tolerances,
           declaration: Declaration | None) -> bool:
    """La section écrite concorde-t-elle avec la mesure ? (en mm si on le sait)"""
    valeur = float(lire_nombre(ecrit))
    if declaration is not None and tolerances.mm_par_unite:
        ecrit_mm = valeur * float(MM_PAR_UNITE[declaration.unite])
        return abs(ecrit_mm - mesure * tolerances.mm_par_unite) <= 1.0
    return abs(valeur - mesure) <= tolerances.longueur


def _cout(texte: Texte, info: dict[str, Any], genre: str, distance_: float,
          parallele: bool | None, section_ok: bool) -> float | None:
    if info["genre_mot"] is not None and info["genre_mot"] != genre:
        return None
    h = max(texte.hauteur, 1e-9)
    cout = distance_ / h
    if parallele is False:
        cout += 2.0
    if info["genre_prefixe"] is not None and info["genre_prefixe"] != genre:
        cout += 1.5
    if section_ok:
        cout -= 1.0
    return cout


def _travee_sous(poutre: Poutre, t: float) -> Travee | None:
    meilleure: tuple[float, Travee] | None = None
    for travee in poutre.travees:
        a = travee.debut.centre if travee.debut else poutre.bande.debut
        b = travee.fin.centre if travee.fin else poutre.bande.fin
        if a <= t <= b:
            return travee
        d = min(abs(t - a), abs(t - b))
        if meilleure is None or d < meilleure[0]:
            meilleure = (d, travee)
    return meilleure[1] if meilleure else None


def _autre_etiquette(noeud: str | None, axe: str) -> str | None:
    if not noeud:
        return None
    if "/" in noeud:
        parties = [p for p in noeud.split("/") if p != axe]
        return parties[0] if len(parties) == 1 else None
    if noeud.startswith(axe):
        return noeud[len(axe):] or None
    if noeud.endswith(axe):
        return noeud[: -len(axe)] or None
    return None


def _repere_de_grille(poutre: Poutre, travee: Travee, grille: Grille,
                      tolerances: Tolerances) -> str:
    b = poutre.bande
    for axe in grille.axes:
        if (ecart_angulaire(angle_deg(axe.direction), angle_deg(b.direction))
                <= tolerances.parallele_deg
                and distance_point_droite(b.point((b.debut + b.fin) / 2.0), axe.origine,
                                          axe.direction)
                <= (b.largeur or 0.0) / 2.0 + tolerances.longueur and axe.etiquette):
            de = _autre_etiquette(travee.debut.noeud if travee.debut else None, axe.etiquette)
            a = _autre_etiquette(travee.fin.noeud if travee.fin else None, axe.etiquette)
            if de or a:
                return f"{axe.etiquette}:{de or '?'}-{a or '?'}"
    return f"{poutre.id}/{travee.index}"


def affecter_libelles(textes: list[Texte], poteaux: list[Poteau], voiles: list[Voile],
                      poutres: list[Poutre], grille: Grille, tolerances: Tolerances,
                      declarations: list[Declaration], deja_pris: set[str]
                      ) -> tuple[list[Poteau], list[Voile], list[Poutre], list[LibelleAffecte]]:
    declaration = unite_declaree(1, declarations)
    lus = []
    for texte in textes:
        if texte.source.poignee and texte.source.poignee in deja_pris:
            continue
        info = lire_repere(texte.texte)
        if info is not None:
            lus.append((texte, info))

    liens: list[tuple[float, int, str, Any, Point]] = []
    for rang, (texte, info) in enumerate(lus):
        centre = texte.centre
        h = texte.hauteur
        for p in poteaux:
            d = 0.0 if point_dans_polygone(centre, p.contour) else distance_point_polygone(
                centre, p.contour)
            taille = max(p.largeur or 0.0, p.profondeur or 0.0, p.diametre or 0.0)
            if d > max(DISTANCE_MAX_HAUTEURS * h, 2.0 * taille):
                continue
            section_ok = False
            if info["section"] and p.largeur and p.profondeur:
                a, b = info["section"]
                section_ok = ((_egale(a, p.largeur, tolerances, declaration)
                               and _egale(b, p.profondeur, tolerances, declaration))
                              or (_egale(a, p.profondeur, tolerances, declaration)
                                  and _egale(b, p.largeur, tolerances, declaration)))
            cout = _cout(texte, info, "poteau", d, None, section_ok)
            if cout is not None:
                liens.append((cout, rang, "poteau", p.id, centre))
        for v in voiles:
            d = 0.0 if point_dans_polygone(centre, v.contour) else distance_point_polygone(
                centre, v.contour)
            if d > max(DISTANCE_MAX_HAUTEURS * h, 1.5 * (v.epaisseur or 0.0)):
                continue
            cout = _cout(texte, info, "voile", d, None, False)
            if cout is not None:
                liens.append((cout, rang, "voile", v.id, centre))
        for poutre in poutres:
            b = poutre.bande
            a0, a1 = b.point(b.debut), b.point(b.fin)
            t = projeter(centre, b.origine, b.direction)
            w = b.largeur or 0.0
            if not b.debut - w <= t <= b.fin + w:
                continue
            d = max(0.0, distance_point_segment(centre, a0, a1) - w / 2.0)
            if d > max(DISTANCE_MAX_HAUTEURS * h, 1.5 * w):
                continue
            parallele = ecart_angulaire(texte.rotation % 180.0, angle_deg(b.direction)) <= 10.0
            section_ok = bool(info["section"] and b.largeur
                              and _egale(info["section"][0], b.largeur, tolerances, declaration))
            cout = _cout(texte, info, "poutre", d, parallele, section_ok)
            if cout is not None:
                liens.append((cout, rang, "poutre", poutre.id, centre))

    liens.sort(key=lambda x: (x[0], x[1], x[3]))
    textes_pris: set[int] = set()
    elements_pris: set[str] = set()
    marques_travees: dict[str, tuple[str, dict[str, Any]]] = {}
    affectes: list[LibelleAffecte] = []
    poteaux_par_id = {p.id: p for p in poteaux}
    voiles_par_id = {v.id: v for v in voiles}
    poutres_par_id = {p.id: p for p in poutres}
    for cout, rang, genre, ident, centre in liens:
        if rang in textes_pris:
            continue
        texte, info = lus[rang]
        source = {"text": texte.texte, "handle": texte.source.poignee, "cost": round(cout, 3)}
        if genre in ("poteau", "voile"):
            if ident in elements_pris:
                continue
            elements_pris.add(ident)
            if genre == "poteau":
                poteaux_par_id[ident] = replace(poteaux_par_id[ident], repere=info["marque"],
                                                repere_source=source)
            else:
                voiles_par_id[ident] = replace(voiles_par_id[ident], repere=info["marque"],
                                               repere_source=source)
        else:
            poutre = poutres_par_id[ident]
            travee = _travee_sous(poutre, projeter(centre, poutre.bande.origine,
                                                   poutre.bande.direction))
            if travee is None or travee.id in marques_travees:
                continue
            marques_travees[travee.id] = (info["marque"], source)
        textes_pris.add(rang)
        affectes.append(LibelleAffecte(texte.texte, texte.source.poignee, info["marque"],
                                       ident, cout))

    nouvelles: list[Poutre] = []
    for poutre in poutres:
        marques = sorted({marques_travees[t.id][0] for t in poutre.travees
                          if t.id in marques_travees})
        travees: list[Travee] = []
        for travee in poutre.travees:
            if travee.id in marques_travees:
                travees.append(replace(travee, repere=marques_travees[travee.id][0],
                                       repere_source="libelle"))
            elif len(marques) == 1:
                travees.append(replace(travee, repere=marques[0],
                                       repere_source="poutre_continue"))
            else:
                travees.append(replace(travee, repere=_repere_de_grille(
                    poutre, travee, grille, tolerances), repere_source="grille"))
        libelles = tuple(marques_travees[t.id][1] for t in poutre.travees
                         if t.id in marques_travees)
        nouvelles.append(replace(poutre, travees=tuple(travees), reperes=tuple(marques),
                                 libelles=libelles))
    return (list(poteaux_par_id.values()), list(voiles_par_id.values()), nouvelles, affectes)
