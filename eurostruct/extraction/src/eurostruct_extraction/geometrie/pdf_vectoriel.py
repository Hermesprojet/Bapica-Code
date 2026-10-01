"""La géométrie d'un PDF vectoriel : des traits de la feuille aux primitives.

Voir ``docs/GEOMETRIE_PDF.md``. Un PDF exporté d'un logiciel de DAO ne garde
souvent ni calques ni entités : un axe en trait mixte y est une suite de
segments de quelques points, une bulle un cercle pointillé découpé, une cote
une ligne, des traits d'attache et un nombre. Ce module RECONSTITUE ce que
l'export a découpé, APPREND de la feuille le style de ses axes et de ses cotes
— aucune couleur n'est écrite en dur —, établit l'échelle par deux sources, et
rend des primitives en millimètres réels à la même chaîne que le DXF.

Rien n'est supposé : sans échelle écrite ET confirmée par les cotes, les
longueurs restent en points-papier, sans unité.
"""

from __future__ import annotations

import io
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Final

from .axes import ETIQUETTE_AXE
from .echelle import Echelle, etablir_echelle, mm_par_point
from .noyau import IndexSpatial, Point, boite_de, distance, projeter
from .primitives import Cercle, Contour, CoteDxf, PrimitivesDxf, Segment, Source, Texte

__all__ = ["TRAITS_MAX", "TRAITS_MIN", "LectureGeometriePdf", "lire_geometrie_pdf"]

#: En dessous, la page n'est pas un dessin (un cahier des charges a des filets).
TRAITS_MIN: Final[int] = 200
#: Au-delà, la feuille n'est pas lue comme un dessin (borne de mémoire et de
#: temps ; les feuilles mesurées en ont 16 000 et 34 000).
TRAITS_MAX: Final[int] = 400_000
#: Le motif d'un nombre de cote : « 650 », « 17,5 », « 1232.1 ».
_NOMBRE: Final[re.Pattern[str]] = re.compile(r"\d{1,5}(?:[.,]\d{1,2})?")
#: Pas d'aplatissement d'une courbe de Bézier.
_PAS_BEZIER: Final[int] = 8
#: Une bulle : au moins huit morceaux d'arc tangents (un cercle pointillé
#: découpé en a une quarantaine, un cercle de Bézier aplati trente-deux).
ARCS_MIN: Final[int] = 8
#: Un style de cotes se voit sous au moins cinq nombres.
COTES_MIN_STYLE: Final[int] = 5


@dataclass
class LectureGeometriePdf:
    primitives: PrimitivesDxf | None
    #: Pourquoi la géométrie n'a pas été lue, le cas échéant.
    motif: str | None
    compte_rendu: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ styles
def _rvb(couleur: Any) -> tuple[float, float, float] | None:
    """Gris, RVB ou CMJN en RVB ; ``None`` pour un motif (hachure en pattern)."""
    if couleur is None:
        return (0.0, 0.0, 0.0)
    if isinstance(couleur, int | float):
        return (float(couleur),) * 3  # type: ignore[return-value]
    try:
        valeurs = [float(v) for v in couleur]
    except (TypeError, ValueError):
        return None
    if len(valeurs) == 1:
        return (valeurs[0],) * 3  # type: ignore[return-value]
    if len(valeurs) == 4:  # CMJN
        c, m, j, n = valeurs
        return ((1 - c) * (1 - n), (1 - m) * (1 - n), (1 - j) * (1 - n))
    if len(valeurs) >= 3:
        return (valeurs[0], valeurs[1], valeurs[2])
    return (0.0, 0.0, 0.0)


def _hexa(couleur: Any) -> str:
    rvb = _rvb(couleur)
    if rvb is None:
        return "motif"
    r, v, b = rvb
    return "#" + "".join(f"{max(0, min(255, round(255 * c))):02X}" for c in (r, v, b))


def _style(objet: dict[str, Any]) -> str:
    """« pdf:#DE0000:1.5 », « pdf:#555555:1.5:tirets » — le nom lisible d'un style."""
    motif = objet.get("dash")
    tirets = bool(motif and motif[0])
    epaisseur = float(objet.get("linewidth") or 0.0)
    return f"pdf:{_hexa(objet.get('stroking_color'))}:{epaisseur:g}" + (":tirets" if tirets else "")


def _style_de_fond(objet: dict[str, Any]) -> str:
    return f"pdf:fond:{_hexa(objet.get('non_stroking_color'))}"


# ------------------------------------------------------------------- traits
def _bezier(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    points = []
    for k in range(1, _PAS_BEZIER + 1):
        t = k / _PAS_BEZIER
        u = 1 - t
        poids = (u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3)
        points.append((sum(w * p[0] for w, p in zip(poids, (p0, p1, p2, p3), strict=True)),
                       sum(w * p[1] for w, p in zip(poids, (p0, p1, p2, p3), strict=True))))
    return points


def _traits_et_contours(page: Any, hauteur: float
                        ) -> tuple[list[Segment], list[Contour]]:
    """Chaque morceau droit d'un chemin tracé ; chaque chemin fermé, un contour."""
    segments: list[Segment] = []
    contours: list[Contour] = []
    y = lambda p: (float(p[0]), hauteur - float(p[1]))  # noqa: E731 — y vers le haut
    for rang, objet in enumerate(list(page.lines) + list(page.rects) + list(page.curves)):
        chemin = objet.get("path") or []
        if not chemin and objet.get("pts"):
            pts = objet["pts"]
            chemin = [("m", pts[0])] + [("l", p) for p in pts[1:]]
        trace = bool(objet.get("stroke", True))
        style = _style(objet)
        source = Source(f"o{rang}", f"PDF_{str(objet.get('object_type', 'chemin')).upper()}")
        courant: Point | None = None
        depart: Point | None = None
        points: list[Point] = []
        ferme = False
        for op in chemin:
            code = op[0]
            if code == "m":
                courant = depart = y(op[1])
                points = [courant]
            elif code == "l" and courant is not None:
                p = y(op[1])
                if trace and p != courant:
                    segments.append(Segment(style, "CONTINUOUS", source, courant, p))
                courant = p
                points.append(p)
            elif code == "c" and courant is not None:
                arc = _bezier(courant, y(op[1]), y(op[2]), y(op[3]))
                for p in arc:
                    if trace and p != courant:
                        segments.append(Segment(style, "CONTINUOUS", source, courant, p,
                                                courbe=True))
                    courant = p
                points.extend(arc)
            elif code == "h" and courant is not None and depart is not None:
                if trace and courant != depart:
                    segments.append(Segment(style, "CONTINUOUS", source, courant, depart))
                courant = depart
                ferme = True
        if len(points) >= 4 and points[0] == points[-1]:
            ferme = True
            points = points[:-1]
        if ferme and len(points) >= 3:
            rempli = bool(objet.get("fill"))
            contours.append(Contour(style if trace else _style_de_fond(objet), "CONTINUOUS",
                                    source, tuple(points), rempli,
                                    "pdf_rempli" if rempli else "pdf_chemin"))
    return segments, contours


# --------------------------------------------------------------------- mots
def _corps(ch: dict[str, Any]) -> float:
    """La hauteur du caractère sur la page.

    La matrice d'un caractère (pdfminer) ne contient pas le corps de la police
    (``Tf``) : un export écrit ``1 Tf`` et met l'échelle dans ``Tm``, un autre
    ``10 Tf`` et une rotation seule. Le corps se retrouve depuis la boîte : la
    glyphe est un rectangle ``avance × corps`` que la matrice transforme, et sa
    boîte alignée mesure ``|a|·avance + |c|·corps`` sur ``|b|·avance + |d|·corps``.
    """
    a, b, c, d = (float(v) for v in ch["matrix"][:4])
    avance = float(ch.get("adv") or 0.0)
    largeur = float(ch["x1"]) - float(ch["x0"])
    haut = float(ch["bottom"]) - float(ch["top"])
    if abs(d) >= abs(c) and abs(d) > 1e-9:
        corps = (haut - abs(b) * avance) / abs(d)
    elif abs(c) > 1e-9:
        corps = (largeur - abs(a) * avance) / abs(c)
    else:
        corps = 1.0
    return max(corps, 1e-6) * math.hypot(c, d)


def _mots(page: Any, hauteur: float) -> list[Texte]:
    """Les mots, reconstitués depuis les caractères — rotation comprise."""
    mots: list[Texte] = []
    courant: list[dict[str, Any]] = []

    def clore() -> None:
        if not courant:
            return
        a, b, _, _, e, f = (float(v) for v in courant[0]["matrix"])
        x0 = min(float(ch["x0"]) for ch in courant)
        x1 = max(float(ch["x1"]) for ch in courant)
        haut = min(float(ch["top"]) for ch in courant)
        bas = max(float(ch["bottom"]) for ch in courant)
        mots.append(Texte(
            f"pdf:texte:{_hexa(courant[0].get('non_stroking_color'))}", "CONTINUOUS",
            Source(f"t{len(mots)}", "PDF_TEXTE"),
            "".join(str(ch["text"]) for ch in courant), (e, f),
            math.degrees(math.atan2(b, a)), _corps(courant[0]),
            (x0, hauteur - bas, x1, hauteur - haut)))
        courant.clear()

    for ch in page.chars:
        texte = str(ch.get("text", ""))
        if not texte.strip():
            clore()
            continue
        if courant:
            prec = courant[-1]
            pa, pb, _, _, pe, pf = (float(v) for v in prec["matrix"])
            a, b, _c, _d, e, f = (float(v) for v in ch["matrix"])
            taille = _corps(ch)
            angle = math.atan2(pb, pa)
            ux, uy = math.cos(angle), math.sin(angle)
            dx, dy = e - pe, f - pf
            le_long, en_travers = dx * ux + dy * uy, -dx * uy + dy * ux
            meme = (abs(math.degrees(math.atan2(b, a) - angle)) < 0.5
                    and _hexa(ch.get("non_stroking_color")) == _hexa(prec.get("non_stroking_color"))
                    and abs(taille - _corps(prec)) <= 0.05 * taille
                    and 0 < le_long <= 1.6 * taille and abs(en_travers) <= 0.3 * taille)
            if not meme:
                clore()
        courant.append(ch)
    clore()
    return mots


# ------------------------------------------------------------------- bulles
def _cercle_ajuste(points: list[Point]) -> tuple[Point, float, float] | None:
    """Kåsa : centre, rayon, écart moyen relatif — ou ``None``."""
    import numpy as np

    if len(points) < 6:
        return None
    m = np.array(points, dtype=float)
    a = np.column_stack([m[:, 0], m[:, 1], np.ones(len(m))])
    b = -(m[:, 0] ** 2 + m[:, 1] ** 2)
    try:
        (dd, ee, ff), *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = -dd / 2.0, -ee / 2.0
    r2 = cx * cx + cy * cy - ff
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    ecarts = np.abs(np.hypot(m[:, 0] - cx, m[:, 1] - cy) - r)
    return (float(cx), float(cy)), float(r), float(ecarts.mean() / r)


def _couverture(points: list[Point], centre: Point) -> float:
    """La part du tour couverte par les points (le plus grand trou retiré)."""
    angles = sorted(math.atan2(p[1] - centre[1], p[0] - centre[0]) for p in points)
    if len(angles) < 2:
        return 0.0
    trous = [b - a for a, b in zip(angles, angles[1:], strict=False)]
    trous.append(2 * math.pi - (angles[-1] - angles[0]))
    return 1.0 - max(trous) / (2 * math.pi)


def _tangent(s: Segment, centre: Point, r: float) -> bool:
    """Un morceau de l'arc : ses deux bouts sur le cercle, sa direction tangente."""
    if (abs(distance(s.a, centre) - r) > 0.15 * r
            or abs(distance(s.b, centre) - r) > 0.15 * r or s.longueur <= 0):
        return False
    milieu = ((s.a[0] + s.b[0]) / 2 - centre[0], (s.a[1] + s.b[1]) / 2 - centre[1])
    rayon = math.hypot(*milieu)
    if rayon <= 0:
        return False
    u = ((s.b[0] - s.a[0]) / s.longueur, (s.b[1] - s.a[1]) / s.longueur)
    return abs(u[0] * milieu[0] + u[1] * milieu[1]) / rayon <= math.sin(math.radians(30.0))


@dataclass(frozen=True)
class _Bulle:
    cercle: Cercle
    #: Les morceaux de l'arc (rangs dans les segments).
    arcs: tuple[int, ...]


def _bulles(mots: list[Texte], segments: list[Segment], index: IndexSpatial) -> list[_Bulle]:
    """Un cercle ajusté sur les arcs tangents qui entourent une étiquette d'axe.

    Un amas de traits d'attache autour d'un nombre de cote s'ajuste aussi sur un
    cercle ; il n'en est pas un : ses traits sont radiaux ou obliques, pas
    tangents. Seuls les morceaux tangents comptent, et ils doivent couvrir au
    moins la moitié du tour.
    """
    bulles: list[_Bulle] = []
    for mot in mots:
        if not ETIQUETTE_AXE.fullmatch(mot.texte.strip()):
            continue
        h = mot.hauteur
        c = mot.centre
        rangs = [i for i in index.pres_de((c[0], c[1], c[0], c[1]), marge=2.5 * h)
                 if segments[i].longueur <= 1.2 * h]
        points = [p for i in rangs for p in (segments[i].a, segments[i].b)
                  if distance(p, c) <= 2.5 * h]
        ajuste = _cercle_ajuste(points)
        for _ in range(2):  # retirer ce qui n'est pas sur le cercle, puis réajuster
            if ajuste is None:
                break
            centre, r, _ecart = ajuste
            points = [p for p in points if abs(distance(p, centre) - r) <= 0.15 * r]
            ajuste = _cercle_ajuste(points)
        if ajuste is None:
            continue
        centre, r, ecart = ajuste
        if not (0.5 * h <= r <= 2.5 * h and distance(centre, c) <= 0.35 * r and ecart <= 0.06):
            continue
        arcs = [i for i in rangs if _tangent(segments[i], centre, r)]
        if (len(arcs) < ARCS_MIN
                or _couverture([p for i in arcs for p in (segments[i].a, segments[i].b)],
                               centre) < 0.5
                or any(distance(b.cercle.centre, centre) <= 0.2 * r for b in bulles)):
            continue
        style = Counter(segments[i].calque for i in arcs).most_common(1)[0][0]
        bulles.append(_Bulle(Cercle(style, "CONTINUOUS",
                                    Source(f"bulle{len(bulles)}", "PDF_BULLE"), centre, r),
                             tuple(arcs)))
    return bulles


# --------------------------------------------------------------------- axes
@dataclass
class _AxeLu:
    origine: Point
    direction: Point
    debut: float
    fin: float
    morceaux: set[int]
    bulles: set[int]

    def point(self, t: float) -> Point:
        return (self.origine[0] + t * self.direction[0], self.origine[1] + t * self.direction[1])


def _axe_depuis_bulle(cercle: Cercle, rangs: list[int], a: Any, b: Any,
                      longueur_min: float) -> _AxeLu | None:
    """L'axe qui part d'une bulle : ses morceaux colinéaires, de proche en proche.

    La direction est celle des morceaux qui partent de la bulle ; la droite est
    ensuite réajustée sur tous les morceaux de son couloir. L'axe s'arrête au
    premier trou de plus de dix rayons : deux axes alignés de part et d'autre
    d'un bâtiment restent deux axes.
    """
    import numpy as np

    c = np.array(cercle.centre, dtype=float)
    r = cercle.rayon
    d = b - a
    longueurs = np.hypot(d[:, 0], d[:, 1])
    u = d / longueurs[:, None]
    milieu = (a + b) / 2.0 - c
    dm = np.hypot(milieu[:, 0], milieu[:, 1])
    pres = np.minimum(np.hypot(*(a - c).T), np.hypot(*(b - c).T))
    radial = np.abs(u[:, 0] * milieu[:, 1] - u[:, 1] * milieu[:, 0]) <= math.sin(
        math.radians(6.0)) * np.maximum(dm, 1e-9)
    traverse = np.abs(u[:, 0] * (c[1] - a[:, 1]) - u[:, 1] * (c[0] - a[:, 0])) <= 0.25 * r
    depart = (pres >= 0.9 * r) & (pres <= 8.0 * r) & radial & traverse
    if longueurs[depart].sum() < 0.5 * r:
        return None
    sens = np.sign((u[depart] * milieu[depart]).sum(axis=1))
    direction = (u[depart] * (sens * longueurs[depart])[:, None]).sum(axis=0)
    direction /= np.hypot(*direction)
    # LA DROITE EST CELLE DES MORCEAUX, pas celle du centre ajusté : sur les
    # feuilles mesurées, l'axe passe à 0,2 rayon du centre de sa bulle.
    origine = ((a[depart] + b[depart]) / 2.0 * longueurs[depart][:, None]).sum(axis=0) \
        / longueurs[depart].sum()
    pris = np.zeros(len(rangs), dtype=bool)
    for couloir in (0.15 * r, 0.03 * r):
        n = np.array([-direction[1], direction[0]])
        dans = ((np.abs((a - origine) @ n) <= couloir) & (np.abs((b - origine) @ n) <= couloir)
                & (np.maximum((a - c) @ direction, (b - c) @ direction) > 0.5 * r))
        if dans.sum() == 0:
            return None
        points = np.vstack([a[dans], b[dans]])
        origine = points.mean(axis=0)
        _, _, vt = np.linalg.svd(points - origine, full_matrices=False)
        nouvelle = vt[0] if vt[0] @ direction >= 0 else -vt[0]
        direction = nouvelle / np.hypot(*nouvelle)
        pris = dans
    # Les abscisses comptées depuis la projection du centre de la bulle.
    o = origine + ((c - origine) @ direction) * direction
    ta, tb = (a - o) @ direction, (b - o) @ direction
    debuts, fins = np.minimum(ta, tb), np.maximum(ta, tb)
    ordre = [k for k in np.argsort(debuts) if pris[k] and fins[k] > 0.5 * r]
    if not ordre or debuts[ordre[0]] > 8.0 * r:
        return None
    debut, fin = float(debuts[ordre[0]]), float(fins[ordre[0]])
    membres = set()
    for k in ordre:
        if debuts[k] - fin > 10.0 * r:
            break
        fin = max(fin, float(fins[k]))
        membres.add(rangs[k])
    if fin - debut < longueur_min:
        return None
    return _AxeLu((float(o[0]), float(o[1])), (float(direction[0]), float(direction[1])),
                  max(debut, 0.0), fin, membres, set())


def _axes_du_style(bulles: list[_Bulle], segments: list[Segment], style: str,
                   longueur_min: float) -> list[_AxeLu]:
    """Les axes d'un style, chacun partant d'au moins une bulle."""
    import numpy as np

    rangs = [i for i, s in enumerate(segments)
             if s.calque == style and not s.courbe and s.longueur > 0]
    if not rangs:
        return []
    a = np.array([segments[i].a for i in rangs], dtype=float)
    b = np.array([segments[i].b for i in rangs], dtype=float)
    axes: list[_AxeLu] = []
    for rang, bulle in enumerate(bulles):
        axe = _axe_depuis_bulle(bulle.cercle, rangs, a, b, longueur_min)
        if axe is None:
            continue
        axe.bulles.add(rang)
        # UNE BULLE A CHAQUE BOUT donne deux fois le même axe : réunis.
        for autre in axes:
            sinus = abs(autre.direction[0] * axe.direction[1]
                        - autre.direction[1] * axe.direction[0])
            if sinus > math.sin(math.radians(0.2)):
                continue
            n = (-autre.direction[1], autre.direction[0])
            pa, pb = axe.point(axe.debut), axe.point(axe.fin)
            if max(abs((p[0] - autre.origine[0]) * n[0] + (p[1] - autre.origine[1]) * n[1])
                   for p in (pa, pb)) > 0.05 * bulle.cercle.rayon:
                continue
            t = sorted(projeter(p, autre.origine, autre.direction) for p in (pa, pb))
            trou = 10.0 * bulle.cercle.rayon
            if t[0] > autre.fin + trou or t[1] < autre.debut - trou:
                continue
            autre.debut, autre.fin = min(autre.debut, t[0]), max(autre.fin, t[1])
            autre.morceaux |= axe.morceaux
            autre.bulles |= axe.bulles
            break
        else:
            axes.append(axe)
    return axes


def _style_des_axes(bulles: list[_Bulle], segments: list[Segment], index: IndexSpatial,
                    longueur_min: float) -> tuple[str | None, list[_AxeLu]]:
    """Le style des traits qui partent des bulles et s'y prolongent en axe.

    Candidats : les styles des morceaux radiaux autour d'au moins deux bulles.
    Retenu : celui dont les axes reconstitués partent du plus grand nombre de
    bulles (au moins deux). Aucune couleur n'est supposée.
    """
    arcs = {i for b in bulles for i in b.arcs}
    vus: dict[str, set[int]] = defaultdict(set)
    for rang, bulle in enumerate(bulles):
        c, r = bulle.cercle.centre, bulle.cercle.rayon
        for i in index.pres_de((c[0], c[1], c[0], c[1]), marge=8.0 * r):
            s = segments[i]
            if i in arcs or s.courbe or s.longueur <= 0:
                continue
            if not 0.9 * r <= min(distance(s.a, c), distance(s.b, c)) <= 8.0 * r:
                continue
            milieu = ((s.a[0] + s.b[0]) / 2, (s.a[1] + s.b[1]) / 2)
            radial = math.atan2(milieu[1] - c[1], milieu[0] - c[0])
            direction = math.atan2(s.b[1] - s.a[1], s.b[0] - s.a[0])
            if abs((math.degrees(direction - radial) + 90.0) % 180.0 - 90.0) <= 6.0:
                vus[s.calque].add(rang)
    meilleur: tuple[int, float, str, list[_AxeLu]] | None = None
    for style in sorted(st for st, b in vus.items() if len(b) >= 2):
        axes = _axes_du_style(bulles, segments, style, longueur_min)
        servies = len({k for axe in axes for k in axe.bulles})
        longueur = sum(axe.fin - axe.debut for axe in axes)
        if servies >= 2 and (meilleur is None or (servies, longueur) > meilleur[:2]):
            meilleur = (servies, longueur, style, axes)
    if meilleur is None:
        return None, []
    return meilleur[2], meilleur[3]


# -------------------------------------------------------------------- cotes
@dataclass(frozen=True)
class _CoteLue:
    texte: str
    valeur: float
    a: Point
    b: Point
    style: str
    mot: Texte


def _nombre(texte: str) -> float | None:
    texte = texte.strip()
    if not _NOMBRE.fullmatch(texte):
        return None
    return float(texte.replace(",", "."))


def _paralleles(mot: Texte, segments: list[Segment], index: IndexSpatial
                ) -> list[tuple[float, int]]:
    """Les lignes parallèles au nombre, sous (ou sur) lui, à moins de 2,5 hauteurs."""
    u = (math.cos(math.radians(mot.rotation)), math.sin(math.radians(mot.rotation)))
    c = mot.centre
    h = mot.hauteur
    trouvees: list[tuple[float, int]] = []
    for i in index.pres_de((c[0], c[1], c[0], c[1]), marge=3.0 * h):
        s = segments[i]
        longueur = s.longueur
        if s.courbe or longueur < 0.5 * h:
            continue
        v = ((s.b[0] - s.a[0]) / longueur, (s.b[1] - s.a[1]) / longueur)
        if abs(u[0] * v[1] - u[1] * v[0]) > math.sin(math.radians(3.0)):
            continue
        t = ((c[0] - s.a[0]) * v[0] + (c[1] - s.a[1]) * v[1]) / longueur
        if not 0.0 <= t <= 1.0:
            continue
        ecart = abs((c[0] - s.a[0]) * v[1] - (c[1] - s.a[1]) * v[0])
        if ecart <= 2.5 * h:
            trouvees.append((ecart, i))
    return sorted(trouvees)


def _styles_des_cotes(nombres: list[Texte], segments: list[Segment], index: IndexSpatial
                      ) -> list[str]:
    """Les styles des lignes qui portent des nombres, du plus fréquent au moins
    fréquent (au moins cinq nombres) — chaque nombre compte une fois par style."""
    styles: Counter[str] = Counter()
    for mot in nombres:
        styles.update({segments[i].calque for _, i in _paralleles(mot, segments, index)})
    return [st for st, n in styles.most_common() if n >= COTES_MIN_STYLE]


def _intersection(ligne: Segment, autre: Segment) -> tuple[float, float, float] | None:
    """(abscisse sur ``ligne``, sinus de l'angle, longueur de ``autre``) si les
    deux segments se coupent (à un point près)."""
    L = ligne.longueur
    w = (autre.b[0] - autre.a[0], autre.b[1] - autre.a[1])
    lw = math.hypot(*w)
    if L <= 0 or lw <= 0:
        return None
    v = ((ligne.b[0] - ligne.a[0]) / L, (ligne.b[1] - ligne.a[1]) / L)
    denom = v[0] * w[1] - v[1] * w[0]
    sinus = denom / lw
    if abs(sinus) < math.sin(math.radians(20.0)):
        return None
    dx, dy = autre.a[0] - ligne.a[0], autre.a[1] - ligne.a[1]
    t = (dx * w[1] - dy * w[0]) / denom
    s = (dx * v[1] - dy * v[0]) / denom
    if -1.0 <= t <= L + 1.0 and -1.0 / lw <= s <= 1.0 + 1.0 / lw:
        return t, sinus, lw
    return None


def _styles_des_marques(style: str, segments: list[Segment], index: IndexSpatial,
                        h: float) -> set[str]:
    """Le style des cotes, et ceux des marques posées AUX BOUTS de ses lignes
    (tirets obliques, points) : une marque d'un autre style ne coupe une ligne
    de cote que si la feuille montre qu'elle en marque les bouts."""
    lignes = [s for s in segments if s.calque == style and not s.courbe]
    vues: Counter[str] = Counter()
    for ligne in lignes:
        for k in index.pres_de(boite_de((ligne.a, ligne.b)), marge=1.0):
            autre = segments[k]
            if autre.calque == style or autre.longueur > 2.5 * h:
                continue
            coupe = _intersection(ligne, autre)
            if coupe is not None and min(coupe[0], ligne.longueur - coupe[0]) <= 0.5:
                vues[autre.calque] += 1
    seuil = max(COTES_MIN_STYLE, 0.1 * len(lignes))
    return {style} | {st for st, n in vues.items() if n >= seuil}


def _ligne_prolongee(ligne: Segment, segments: list[Segment], index: IndexSpatial
                     ) -> tuple[Point, Point, float, float]:
    """La ligne de cote entière : ``ligne`` et ses morceaux colinéaires du même
    style qui la touchent (dépassements au-delà des marques, chaîne dessinée en
    plusieurs traits), de proche en proche. Rend (origine, direction, début, fin)."""
    L = ligne.longueur
    o = ligne.a
    v = ((ligne.b[0] - o[0]) / L, (ligne.b[1] - o[1]) / L)
    n = (-v[1], v[0])
    debut, fin = 0.0, L
    vus: set[int] = set()
    grandit = True
    while grandit:
        grandit = False
        a = (o[0] + debut * v[0], o[1] + debut * v[1])
        b = (o[0] + fin * v[0], o[1] + fin * v[1])
        for k in index.pres_de(boite_de((a, b)), marge=1.0):
            autre = segments[k]
            if k in vus or autre.calque != ligne.calque or autre.courbe:
                continue
            if max(abs((p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1])
                   for p in (autre.a, autre.b)) > 0.3:
                continue
            ta = (autre.a[0] - o[0]) * v[0] + (autre.a[1] - o[1]) * v[1]
            tb = (autre.b[0] - o[0]) * v[0] + (autre.b[1] - o[1]) * v[1]
            if min(ta, tb) > fin + 0.5 or max(ta, tb) < debut - 0.5:
                continue
            vus.add(k)
            if min(ta, tb) < debut or max(ta, tb) > fin:
                debut, fin = min(debut, ta, tb), max(fin, ta, tb)
                grandit = True
    return o, v, debut, fin


def _cotes(nombres: list[Texte], segments: list[Segment], index: IndexSpatial,
           style: str, h_type: float) -> list[_CoteLue]:
    """Chaque nombre, entre les deux coupes de sa ligne de cote qui l'encadrent.

    Une coupe : une marque (§ ``_styles_des_marques``) ou un trait d'attache
    qui S'ARRÊTE près de la ligne. Le trait d'attache d'une chaîne voisine qui
    la traverse de part en part ne la coupe pas. Le nombre doit être posé vers
    le milieu de son intervalle.
    """
    marques = _styles_des_marques(style, segments, index, h_type)
    cotes: list[_CoteLue] = []
    # LE STYLE DES NOMBRES DE COTE s'apprend aussi : celui de la majorité des
    # nombres posés sur une ligne de cote. Un numéro de marche ou une hauteur
    # d'allège d'un autre style, posé sur la même ligne, n'est pas une cote.
    portes = Counter(mot.calque for mot in nombres
                     if any(segments[i].calque == style
                            for _, i in _paralleles(mot, segments, index)))
    if not portes:
        return []
    style_texte = portes.most_common(1)[0][0]
    for mot in nombres:
        if mot.calque != style_texte:
            continue
        valeur = _nombre(mot.texte)
        if valeur is None or valeur <= 0:
            continue
        h = mot.hauteur
        portees = [i for _, i in _paralleles(mot, segments, index)
                   if segments[i].calque == style]
        if not portees:
            continue
        o, v, debut, fin = _ligne_prolongee(segments[portees[0]], segments, index)
        n = (-v[1], v[0])
        entiere = Segment(style, "CONTINUOUS", segments[portees[0]].source,
                          (o[0] + debut * v[0], o[1] + debut * v[1]),
                          (o[0] + fin * v[0], o[1] + fin * v[1]))
        coupes = [debut, fin]
        for k in index.pres_de(boite_de((entiere.a, entiere.b)), marge=1.0):
            autre = segments[k]
            if autre.calque not in marques or autre.courbe:
                continue
            coupe = _intersection(entiere, autre)
            if coupe is None:
                continue
            t, _sinus, lw = coupe
            bout = min(abs((p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1])
                       for p in (autre.a, autre.b))
            if lw <= 2.5 * h or bout <= 2.0 * h:
                coupes.append(debut + min(max(t, 0.0), fin - debut))
        # Une marque et un trait d'attache au même point : une seule coupe.
        reunies: list[list[float]] = []
        for t in sorted(coupes):
            if reunies and t - reunies[-1][-1] <= 0.5:
                reunies[-1].append(t)
            else:
                reunies.append([t])
        coupes = [sum(g) / len(g) for g in reunies]
        c = mot.centre
        tc = (c[0] - o[0]) * v[0] + (c[1] - o[1]) * v[1]
        avant = [t for t in coupes if t <= tc]
        apres = [t for t in coupes if t > tc]
        if not avant or not apres:
            continue
        t0, t1 = avant[-1], apres[0]
        if t1 - t0 <= 0 or abs(tc - (t0 + t1) / 2.0) > max(0.3 * (t1 - t0), 1.5 * h):
            continue
        a = (o[0] + t0 * v[0], o[1] + t0 * v[1])
        b = (o[0] + t1 * v[0], o[1] + t1 * v[1])
        cotes.append(_CoteLue(mot.texte.strip(), valeur, a, b, style, mot))
    return cotes


# ---------------------------------------------------------------- l'entrée
def _index(segments: list[Segment], h_type: float) -> IndexSpatial:
    index = IndexSpatial(4.0 * h_type)
    for s in segments:
        index.ajouter(boite_de((s.a, s.b)))
    return index


def _mise_a_l_echelle(k: float, segments: list[Segment], contours: list[Contour],
                      cercles: list[Cercle], mots: list[Texte]
                      ) -> tuple[list[Segment], list[Contour], list[Cercle], list[Texte]]:
    m = lambda p: (p[0] * k, p[1] * k)  # noqa: E731
    return ([replace(s, a=m(s.a), b=m(s.b)) for s in segments],
            [replace(c, points=tuple(m(p) for p in c.points)) for c in contours],
            [replace(c, centre=m(c.centre), rayon=c.rayon * k) for c in cercles],
            [replace(t, ancrage=m(t.ancrage), hauteur=t.hauteur * k,
                     boite=(t.boite[0] * k, t.boite[1] * k, t.boite[2] * k, t.boite[3] * k))
             for t in mots])


def lire_geometrie_pdf(octets: bytes) -> LectureGeometriePdf:
    """La géométrie de la page d'un PDF d'une page, ou pourquoi elle n'est pas lue."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(octets)) as pdf:
        if len(pdf.pages) != 1:
            return LectureGeometriePdf(None, (
                f"document de {len(pdf.pages)} pages: la geometrie n'est lue que sur un plan "
                "d'une seule feuille"))
        page = pdf.pages[0]
        hauteur, largeur = float(page.height), float(page.width)
        segments, contours = _traits_et_contours(page, hauteur)
        if len(segments) < TRAITS_MIN:
            return LectureGeometriePdf(None, (
                f"{len(segments)} trait(s) seulement: la page n'est pas un dessin"))
        if len(segments) > TRAITS_MAX:
            return LectureGeometriePdf(None, (
                f"{len(segments)} traits: au-dela de la borne de {TRAITS_MAX}, la feuille "
                "n'est pas lue comme un dessin"))
        mots = _mots(page, hauteur)

    hauteurs = sorted(t.hauteur for t in mots) or [10.0]
    h_type = hauteurs[len(hauteurs) // 2]
    index = _index(segments, h_type)
    bulles = _bulles(mots, segments, index)
    style_axes, axes_lus = _style_des_axes(bulles, segments, index, 20.0 * h_type)
    # Seules les bulles d'où part un axe restent des bulles ; les morceaux de
    # leurs arcs et ceux des axes sont remplacés par le cercle et l'axe
    # reconstitués. Les autres traits du style des axes gardent leur style.
    servies = sorted({k for axe in axes_lus for k in axe.bulles})
    retires = {i for k in servies for i in bulles[k].arcs}
    retires |= {i for axe in axes_lus for i in axe.morceaux}
    segments = [s for i, s in enumerate(segments) if i not in retires]
    cercles = [bulles[k].cercle for k in servies]
    axes = [Segment("pdf:axe:" + (style_axes or "").removeprefix("pdf:"), "CONTINUOUS",
                    Source(f"axe{rang}", "PDF_AXE"), axe.point(axe.debut), axe.point(axe.fin))
            for rang, axe in enumerate(axes_lus)]

    nombres = [t for t in mots if _nombre(t.texte) is not None]
    index = _index(segments, h_type)
    # LE STYLE DES COTES : parmi les trois styles qui portent le plus de
    # nombres, celui dont les cotes confirment une échelle écrite ; à défaut,
    # le plus fréquent (et l'échelle reste non établie).
    style_cotes: str | None = None
    cotes: list[_CoteLue] = []
    echelle: Echelle | None = None
    for style in _styles_des_cotes(nombres, segments, index)[:3]:
        lues = _cotes(nombres, segments, index, style, h_type)
        essai = etablir_echelle(mots, [(c.texte, c.valeur, distance(c.a, c.b)) for c in lues])
        if echelle is None or (essai.etablie and (not echelle.etablie
                                                  or essai.concordantes > echelle.concordantes)):
            style_cotes, cotes, echelle = style, lues, essai
    if echelle is None:
        echelle = etablir_echelle(mots, [])
    if style_cotes:
        segments = [replace(s, calque="pdf:cote:" + s.calque.removeprefix("pdf:"))
                    if s.calque == style_cotes else s for s in segments]

    compte_rendu: dict[str, Any] = {
        "page": 1, "page_size_pt": [round(largeur, 3), round(hauteur, 3)],
        "segments": len(segments), "outlines": len(contours), "words": len(mots),
        "circles_around_labels": len(bulles), "axis_bubbles": len(cercles),
        "axis_style": style_axes, "axes_rebuilt": len(axes),
        "dimension_style": style_cotes, "dimensions_rebuilt": len(cotes),
        "scale": echelle.en_json(),
    }
    prims = PrimitivesDxf()
    tous = segments + axes
    if echelle.etablie and echelle.n:
        k = mm_par_point(echelle.n)
        tous, contours, cercles, mots = _mise_a_l_echelle(k, tous, contours, cercles, mots)
        mm_unite = echelle.mm_par_unite_des_cotes
        for rang, c in enumerate(cotes):
            a, b = (c.a[0] * k, c.a[1] * k), (c.b[0] * k, c.b[1] * k)
            mesure = distance(a, b)
            direction = ((b[0] - a[0]) / mesure, (b[1] - a[1]) / mesure)
            prims.cotes.append(CoteDxf(
                "pdf:cote:" + c.style.removeprefix("pdf:"), "CONTINUOUS",
                Source(f"cote{rang}", "PDF_COTE"), a, b, a, direction, mesure,
                1.0 / mm_unite, c.texte, "pdf"))
        prims.unites = "mm"
        prims.origine_unites = echelle.citation()
    elif echelle.note:
        prims.remarques.append(("echelle", echelle.note))
    prims.segments = tous
    prims.contours = contours
    prims.cercles = cercles
    prims.textes = mots
    prims.cadre = {"page": 1, "mm_per_point": mm_par_point(echelle.n)
                   if echelle.etablie and echelle.n else None,
                   "page_height_pt": hauteur, "page_width_pt": largeur}
    return LectureGeometriePdf(prims, None, compte_rendu)
