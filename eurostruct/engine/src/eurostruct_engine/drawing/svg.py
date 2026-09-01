"""Apercu SVG d'une coupe, rendu depuis le MEME modele que le DXF.

CE MODULE NE CALCULE AUCUNE COORDONNEE DE SECTION. Il recoit un
:class:`~.modele.ModeleSection` deja gele et se contente de le transcrire. La
seule arithmetique qu'il s'autorise est celle du cadrage — passer du repere
millimetrique, Y vers le haut, au repere SVG, Y vers le bas — et elle
s'applique indistinctement a tout ce que le modele contient.

C'est la garantie qui compte: l'apercu affiche a l'ecran et le fichier
telecharge decrivent la meme poutre parce qu'ils viennent du meme objet, pas
parce que deux codes ont ete relus l'un a cote de l'autre.

L'APERCU N'EST PAS UN LIVRABLE. Il porte sa propre mention, il n'est pas
depose, il n'a pas d'empreinte enregistree, et rien de ce qui s'y affiche ne
peut servir de piece. Le DXF, lui, l'est.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from .layers import (
    L_CARTOUCHE,
    L_COFFRAGE,
    L_COTATION,
    L_FERR_PRINCIPAL,
    L_FERR_TRANSVERSAL,
    L_TEXTE,
)
from .modele import Cote, ModeleSection, Polyligne, Texte

__all__ = ["MEDIA_TYPE_SVG", "MENTION_APERCU", "rendre_svg"]

MEDIA_TYPE_SVG = "image/svg+xml"

#: Affichee sur l'apercu lui-meme, pas seulement dans l'interface: une image
#: se copie, se colle et se transmet sans son bouton.
MENTION_APERCU = "APERCU NON CONTRACTUEL — le fichier DXF fait foi"

#: Couleurs de trait par calque. Les index ACI du DXF ne veulent rien dire dans
#: un navigateur; ce qui doit se retrouver d'un rendu a l'autre, c'est la
#: DISTINCTION entre coffrage, armatures principales, cadres, cotes et textes.
_TRAIT: dict[str, str] = {
    L_COFFRAGE: "#1f2933",
    L_FERR_PRINCIPAL: "#c0392b",
    L_FERR_TRANSVERSAL: "#1e8449",
    L_COTATION: "#7d3c98",
    L_TEXTE: "#1f2933",
    L_CARTOUCHE: "#52606d",
}

#: Epaisseurs, en 1/100 mm comme dans `layers.py`, converties en unites du
#: dessin au moment du rendu.
_EPAISSEUR: dict[str, float] = {
    L_COFFRAGE: 35.0,
    L_FERR_PRINCIPAL: 50.0,
    L_FERR_TRANSVERSAL: 35.0,
    L_COTATION: 18.0,
    L_TEXTE: 18.0,
    L_CARTOUCHE: 25.0,
}


def _n(valeur: float) -> str:
    """Un nombre stable: trois decimales, jamais de -0, jamais de notation E.

    LE DETERMINISME EST UNE EXIGENCE ICI AUSSI. Un apercu qui changerait d'un
    appel a l'autre rendrait tout controle de correspondance illusoire.
    """
    arrondi = round(valeur, 3)
    if arrondi == 0.0:
        arrondi = 0.0
    return f"{arrondi:.3f}".rstrip("0").rstrip(".") or "0"


def _arc_svg(x0: float, y0: float, x1: float, y1: float, bulge: float) -> str:
    """Segment d'arc SVG equivalent au bulge DXF entre deux sommets.

    Le bulge vaut tan(theta/4) ou theta est l'angle au centre. Le rayon et le
    sens s'en deduisent exactement — aucune discretisation, donc aucun ecart
    de trace entre l'apercu et le fichier.
    """
    if bulge == 0.0:
        return f"L {_n(x1)} {_n(y1)}"
    theta = 4.0 * math.atan(bulge)
    corde = math.hypot(x1 - x0, y1 - y0)
    rayon = abs(corde / (2.0 * math.sin(theta / 2.0)))
    grand = 1 if abs(theta) > math.pi else 0
    # Y est inverse a la transcription, donc le sens de rotation l'est aussi.
    sens = 0 if bulge > 0 else 1
    return f"A {_n(rayon)} {_n(rayon)} 0 {grand} {sens} {_n(x1)} {_n(y1)}"


class _Toile:
    """Le repere du dessin vers celui du SVG: Y descend, X ne bouge pas."""

    __slots__ = ("hauteur",)

    def __init__(self, y_max: float) -> None:
        self.hauteur = y_max

    def y(self, valeur: float) -> float:
        return self.hauteur - valeur


def _polyligne(p: Polyligne, t: _Toile) -> str:
    sommets = p.sommets
    x0, y0 = sommets[0][0], t.y(sommets[0][1])
    parties = [f"M {_n(x0)} {_n(y0)}"]
    for i in range(1, len(sommets)):
        precedent = sommets[i - 1]
        courant = sommets[i]
        parties.append(_arc_svg(precedent[0], t.y(precedent[1]),
                                courant[0], t.y(courant[1]), precedent[2]))
    if p.fermee:
        dernier = sommets[-1]
        parties.append(_arc_svg(dernier[0], t.y(dernier[1]), x0, y0, dernier[2]))
        parties.append("Z")
    trait = _TRAIT.get(p.calque, "#1f2933")
    ep = _EPAISSEUR.get(p.calque, 25.0) / 100.0
    return (f'<path class="{p.calque}" d="{" ".join(parties)}" fill="none" '
            f'stroke="{trait}" stroke-width="{_n(ep)}" '
            f'vector-effect="non-scaling-stroke"/>')


def _cote(c: Cote, t: _Toile, hauteur: float) -> str:
    """Une cote: ses deux lignes d'attache, sa ligne de cote, et sa VALEUR.

    La valeur affichee est celle que le modele porte, jamais une mesure refaite
    ici — un apercu qui recalculerait ses cotes pourrait afficher autre chose
    que le fichier, ce qui est exactement le defaut a empecher.
    """
    trait = _TRAIT[L_COTATION]
    ep = _EPAISSEUR[L_COTATION] / 100.0
    x1, y1 = c.p1[0], t.y(c.p1[1])
    x2, y2 = c.p2[0], t.y(c.p2[1])
    if c.angle == 0.0:
        yb = t.y(c.base[1])
        ligne = (f'<path d="M {_n(x1)} {_n(y1)} L {_n(x1)} {_n(yb)} '
                 f'M {_n(x2)} {_n(y2)} L {_n(x2)} {_n(yb)} '
                 f'M {_n(x1)} {_n(yb)} L {_n(x2)} {_n(yb)}"')
        tx, ty = (c.p1[0] + c.p2[0]) / 2.0, yb
        decalage = -2.0
    else:
        xb = c.base[0]
        ligne = (f'<path d="M {_n(x1)} {_n(y1)} L {_n(xb)} {_n(y1)} '
                 f'M {_n(x2)} {_n(y2)} L {_n(xb)} {_n(y2)} '
                 f'M {_n(xb)} {_n(y1)} L {_n(xb)} {_n(y2)}"')
        tx, ty = xb, (y1 + y2) / 2.0
        decalage = -2.0
    return (
        f'{ligne} class="{L_COTATION}" fill="none" stroke="{trait}" '
        f'stroke-width="{_n(ep)}" vector-effect="non-scaling-stroke"/>'
        f'<text class="{L_COTATION}" x="{_n(tx)}" y="{_n(ty + decalage)}" '
        f'font-size="{_n(hauteur)}" fill="{trait}" text-anchor="middle">'
        f'{escape(f"{c.valeur:g}")}</text>'
    )


def _texte(e: Texte, t: _Toile) -> str:
    couleur = _TRAIT.get(e.calque, "#1f2933")
    x, y = e.x, t.y(e.y)
    ancre = "middle" if e.ancrage == "centre" else "start"
    # Le DXF pose le texte par sa ligne de base et tourne dans le sens direct;
    # le SVG tourne dans l'autre. Le signe suit, sinon un filigrane a 45 degres
    # partirait dans la mauvaise diagonale.
    rotation = (f' transform="rotate({_n(-e.rotation)} {_n(x)} {_n(y)})"'
                if e.rotation else "")
    return (f'<text class="{e.calque}" x="{_n(x)}" y="{_n(y)}" '
            f'font-size="{_n(e.hauteur)}" fill="{couleur}" '
            f'text-anchor="{ancre}"{rotation}>{escape(e.contenu)}</text>')


def rendre_svg(modele: ModeleSection) -> str:
    """Le SVG de l'apercu. Deterministe: memes entrees, memes octets."""
    xs: list[float] = []
    ys: list[float] = []
    for p in modele.polylignes:
        xs.extend(s[0] for s in p.sommets)
        ys.extend(s[1] for s in p.sommets)
    for d in modele.disques:
        xs.extend((d.x - d.rayon, d.x + d.rayon))
        ys.extend((d.y - d.rayon, d.y + d.rayon))
    for c in modele.cotes:
        xs.extend((c.base[0], c.p1[0], c.p2[0]))
        ys.extend((c.base[1], c.p1[1], c.p2[1]))
    for e in modele.textes:
        xs.append(e.x)
        ys.extend((e.y, e.y + e.hauteur))

    marge = max(modele.b, modele.h) * 0.08
    x0, x1 = min(xs) - marge, max(xs) + marge
    y0, y1 = min(ys) - marge, max(ys) + marge
    largeur, hauteur = x1 - x0, y1 - y0
    toile = _Toile(y1)

    corps: list[str] = []
    for p in modele.polylignes:
        corps.append(_polyligne(p, toile))
    for d in modele.disques:
        trait = _TRAIT.get(d.calque, "#1f2933")
        remplissage = trait if d.plein else "none"
        corps.append(
            f'<circle class="{d.calque}" cx="{_n(d.x)}" cy="{_n(toile.y(d.y))}" '
            f'r="{_n(d.rayon)}" fill="{remplissage}" stroke="{trait}" '
            f'stroke-width="{_n(_EPAISSEUR.get(d.calque, 25.0) / 100.0)}" '
            f'vector-effect="non-scaling-stroke"/>')
    # 2,5 mm sur la feuille tracee, comme la cotation du DXF (`dimtxt = 2.5`).
    txt_cote = 2.5 * modele.echelle
    for c in modele.cotes:
        corps.append(_cote(c, toile, txt_cote))
    for e in modele.textes:
        corps.append(_texte(e, toile))

    # LA MENTION D'APERCU EN DERNIER, donc au-dessus de tout le reste.
    bandeau = 3.0 * 2.5 * modele.echelle
    corps.append(
        f'<text class="apercu" x="{_n(x0 + marge / 2.0)}" '
        f'y="{_n(bandeau)}" font-size="{_n(bandeau * 0.8)}" fill="#b03a2e" '
        f'font-weight="bold">{escape(MENTION_APERCU)}</text>')

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{_n(x0)} 0 {_n(largeur)} {_n(hauteur)}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet" '
        f'font-family="ui-sans-serif, system-ui, sans-serif" '
        f'role="img" aria-label="{escape(modele.titre)}">'
        f'<title>{escape(modele.titre)}</title>'
        + "".join(corps)
        + "</svg>"
    )
