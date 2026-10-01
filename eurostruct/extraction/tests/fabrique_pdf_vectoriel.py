"""Des feuilles PDF VECTORIELLES fabriquées pour la lecture géométrique — aucun
plan réel n'est commité.

La feuille est écrite opérateur par opérateur (aucune dépendance nouvelle), sur
le modèle de ce qu'un logiciel de DAO exporte quand il aplatit ses calques :

* le plan est TOURNÉ (10°) et dessiné au 1/50 ; les longueurs réelles sont
  données en millimètres et converties ici, une seule fois ;
* les axes sont un trait mixte rouge DÉCOUPÉ en morceaux (le motif n'est pas
  un attribut, il est dessiné) ; leurs bulles sont des cercles pointillés
  découpés, l'étiquette rouge au centre, tournée avec le plan ;
* les cotes sont des chaînes bleues : une ligne par cote avec ses
  dépassements, des tirets obliques d'un autre style aux bouts, des traits
  d'attache qui dépassent la ligne, le nombre en cm au-dessus du milieu ;
* « 1/50 » est écrit au cartouche, loin de tout ;
* les poteaux sont des carrés pleins aux nœuds, un voile un rectangle long et
  plein, une poutre deux traits parallèles (qu'une feuille ne permet pas de
  reconnaître : le test vérifie le refus).

Variantes : sans échelle écrite ; « 1/50 » écrit mais dessiné au 1/100 ; motif
de tirets par ATTRIBUT et bulles en courbes de Bézier, texte en ``1 Tf`` mis à
l'échelle par ``Tm`` (la convention d'un autre exporteur) ; deux pages ; une
page de texte sans dessin ; une cage d'ascenseur au nœud B2 (contour, cabine,
chevron plein) et la lettre géante d'un noyau au bout de l'axe 2.

Tous les textes disent FICTIF là où un plan réel porterait un nom.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence

Point = tuple[float, float]

#: Millimètres réels par point-papier au 1/50.
MM_PAR_POINT_50 = 25.4 / 72.0 * 50.0
#: Les axes fabriqués : (étiquette, abscisse ou ordonnée en mm réels).
AXES_X = (("A", 0.0), ("B", 6000.0), ("C", 12000.0))
AXES_Y = (("1", 0.0), ("2", 5000.0))
POTEAU_MM = 300.0
VOILE_MM = 200.0

#: Largeurs Helvetica (millièmes du corps) des caractères écrits ici.
_LARGEURS = {**dict.fromkeys("0123456789", 556), "A": 667, "B": 667, "C": 722,
             "/": 278, ",": 278, " ": 278, "F": 611, "I": 278, "T": 611}


def _largeur(texte: str, corps: float) -> float:
    return sum(_LARGEURS.get(ch, 600) for ch in texte) * corps / 1000.0


def _echapper(texte: str) -> bytes:
    return texte.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(
        b")", b"\\)")


def assembler(flux: Sequence[bytes], *, largeur: float = 1190.55,
              hauteur: float = 841.89) -> bytes:
    """Un PDF d'autant de pages que de flux de contenu (Helvetica, WinAnsi)."""
    objets: list[bytes] = [b"", b""]
    objets.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                  b"/Encoding /WinAnsiEncoding >>")
    enfants = []
    for contenu in flux:
        objets.append(b"<< /Length %d >>\nstream\n" % len(contenu) + contenu
                      + b"\nendstream")
        objets.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] "
                      b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
                      % (largeur, hauteur, len(objets)))
        enfants.append(len(objets))
    objets[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objets[1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % e for e in enfants)
                 + b"] /Count %d >>" % len(enfants))
    sortie = io.BytesIO()
    sortie.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, corps in enumerate(objets, start=1):
        positions.append(sortie.tell())
        sortie.write(b"%d 0 obj\n" % numero + corps + b"\nendobj\n")
    xref = sortie.tell()
    sortie.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1))
    for position in positions:
        sortie.write(b"%010d 00000 n \n" % position)
    sortie.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                 % (len(objets) + 1, xref))
    return sortie.getvalue()


class _Feuille:
    """Un plan en mm réels, posé sur la page : tourné, à l'échelle, décalé."""

    def __init__(self, *, echelle: int, angle_deg: float, origine: Point,
                 tirets_par_attribut: bool, corps_dans_tm: bool) -> None:
        self.k = 25.4 / 72.0 * echelle
        self.angle = math.radians(angle_deg)
        self.origine = origine
        self.attribut = tirets_par_attribut
        self.corps_dans_tm = corps_dans_tm
        self.ops: list[str] = []

    # ---------------------------------------------------------- repère
    def p(self, x_mm: float, y_mm: float) -> Point:
        x, y = x_mm / self.k, y_mm / self.k
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (self.origine[0] + c * x - s * y, self.origine[1] + s * x + c * y)

    def r(self, vx: float, vy: float) -> Point:
        """Un vecteur de la feuille (points) tourné avec le plan."""
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (c * vx - s * vy, s * vx + c * vy)

    # ---------------------------------------------------------- traits
    def style(self, rvb: tuple[float, float, float], epaisseur: float,
              tirets: str = "[] 0") -> None:
        self.ops.append(f"{rvb[0]:g} {rvb[1]:g} {rvb[2]:g} RG {epaisseur:g} w {tirets} d")

    def trait(self, a: Point, b: Point) -> None:
        self.ops.append(f"{a[0]:.3f} {a[1]:.3f} m {b[0]:.3f} {b[1]:.3f} l S")

    def trait_mm(self, a: tuple[float, float], b: tuple[float, float]) -> None:
        self.trait(self.p(*a), self.p(*b))

    def mixte(self, a: Point, b: Point) -> None:
        """Un trait mixte (12, 3, 1, 3 pt) : par attribut, ou découpé en morceaux."""
        if self.attribut:
            self.ops.append("[12 3 1 3] 0 d")
            self.trait(a, b)
            self.ops.append("[] 0 d")
            return
        longueur = math.dist(a, b)
        u = ((b[0] - a[0]) / longueur, (b[1] - a[1]) / longueur)
        t = 0.0
        while t < longueur:
            for plein, vide in ((12.0, 3.0), (1.0, 3.0)):
                fin = min(t + plein, longueur)
                if fin > t:
                    self.trait((a[0] + t * u[0], a[1] + t * u[1]),
                               (a[0] + fin * u[0], a[1] + fin * u[1]))
                t = fin + vide
                if t >= longueur:
                    break

    def cercle_pointille(self, centre: Point, rayon: float) -> None:
        if self.attribut:
            # Quatre arcs de Bézier, tirets par attribut.
            kappa = 0.5523 * rayon
            cx, cy = centre
            self.ops.append("[2 2] 0 d")
            self.ops.append(
                f"{cx + rayon:.3f} {cy:.3f} m "
                f"{cx + rayon:.3f} {cy + kappa:.3f} {cx + kappa:.3f} {cy + rayon:.3f} "
                f"{cx:.3f} {cy + rayon:.3f} c "
                f"{cx - kappa:.3f} {cy + rayon:.3f} {cx - rayon:.3f} {cy + kappa:.3f} "
                f"{cx - rayon:.3f} {cy:.3f} c "
                f"{cx - rayon:.3f} {cy - kappa:.3f} {cx - kappa:.3f} {cy - rayon:.3f} "
                f"{cx:.3f} {cy - rayon:.3f} c "
                f"{cx + kappa:.3f} {cy - rayon:.3f} {cx + rayon:.3f} {cy - kappa:.3f} "
                f"{cx + rayon:.3f} {cy:.3f} c S")
            self.ops.append("[] 0 d")
            return
        pas = 2 * math.pi / 48
        for i in range(0, 48, 2):
            a = (centre[0] + rayon * math.cos(i * pas), centre[1] + rayon * math.sin(i * pas))
            b = (centre[0] + rayon * math.cos((i + 1) * pas),
                 centre[1] + rayon * math.sin((i + 1) * pas))
            self.trait(a, b)

    def contour(self, points_mm: Sequence[tuple[float, float]]) -> None:
        """Un contour fermé, tracé, non rempli."""
        pts = [self.p(*q) for q in points_mm]
        chemin = " ".join(f"{x:.3f} {y:.3f} {'m' if i == 0 else 'l'}"
                          for i, (x, y) in enumerate(pts))
        self.ops.append(f"0 G 0.6 w [] 0 d {chemin} h S")

    def plein(self, points_mm: Sequence[tuple[float, float]], gris: float) -> None:
        pts = [self.p(*q) for q in points_mm]
        chemin = " ".join(f"{x:.3f} {y:.3f} {'m' if i == 0 else 'l'}"
                          for i, (x, y) in enumerate(pts))
        self.ops.append(f"{gris:g} g 0 G 0.6 w {chemin} h B")

    # ---------------------------------------------------------- texte
    def texte(self, texte: str, base: Point, corps: float, rvb: tuple[float, float, float],
              *, tourne: bool = True, de_plus: float = 0.0) -> None:
        angle = (self.angle if tourne else 0.0) + de_plus
        c, s = math.cos(angle), math.sin(angle)
        couleur = f"{rvb[0]:g} {rvb[1]:g} {rvb[2]:g} rg"
        if self.corps_dans_tm:
            tm = f"{corps * c:.5f} {corps * s:.5f} {-corps * s:.5f} {corps * c:.5f}"
            self.ops.append(f"BT {couleur} /F1 1 Tf {tm} {base[0]:.3f} {base[1]:.3f} Tm "
                            f"({_echapper(texte).decode('cp1252')}) Tj ET")
        else:
            self.ops.append(f"BT {couleur} /F1 {corps:g} Tf {c:.5f} {s:.5f} {-s:.5f} {c:.5f} "
                            f"{base[0]:.3f} {base[1]:.3f} Tm "
                            f"({_echapper(texte).decode('cp1252')}) Tj ET")

    def texte_centre(self, texte: str, centre: Point, corps: float,
                     rvb: tuple[float, float, float], *, de_plus: float = 0.0) -> None:
        """Le texte dont la boîte de glyphe (descente comprise) est centrée."""
        # Helvetica : descente 207, corps 1000 → milieu de boîte à 0,293 corps.
        angle = self.angle + de_plus
        vx, vy = -_largeur(texte, corps) / 2.0, -0.293 * corps
        dx = math.cos(angle) * vx - math.sin(angle) * vy
        dy = math.sin(angle) * vx + math.cos(angle) * vy
        self.texte(texte, (centre[0] + dx, centre[1] + dy), corps, rvb, de_plus=de_plus)

    def flux(self) -> bytes:
        return ("\n".join(self.ops) + "\n").encode("cp1252")


ROUGE = (0.87, 0.0, 0.0)
BLEU = (0.0, 0.0, 1.0)
NOIR = (0.0, 0.0, 0.0)


def _cote(f: _Feuille, a_mm: tuple[float, float], b_mm: tuple[float, float],
          ecart_mm: float, texte: str, *, attache_mm: float) -> None:
    """Une cote de ``a`` à ``b``, sa ligne décalée de ``ecart_mm`` (à gauche de
    a→b), ses attaches depuis ``attache_mm`` de l'objet, ses tirets, son nombre."""
    ux, uy = b_mm[0] - a_mm[0], b_mm[1] - a_mm[1]
    long_ = math.hypot(ux, uy)
    ux, uy = ux / long_, uy / long_
    nx, ny = -uy, ux
    pa = (a_mm[0] + nx * ecart_mm, a_mm[1] + ny * ecart_mm)
    pb = (b_mm[0] + nx * ecart_mm, b_mm[1] + ny * ecart_mm)
    signe = 1.0 if ecart_mm >= 0 else -1.0
    depasse = 2.0 * f.k  # 2 pt au-delà de la ligne
    f.style(BLEU, 1.0)
    f.trait_mm(pa, pb)
    for q, coin in ((a_mm, pa), (b_mm, pb)):
        f.trait_mm((q[0] + nx * signe * attache_mm, q[1] + ny * signe * attache_mm),
                   (coin[0] + nx * signe * depasse, coin[1] + ny * signe * depasse))
    # Les tirets obliques (45°), d'un autre style que la ligne.
    f.style(BLEU, 2.0)
    for coin in (pa, pb):
        c = f.p(*coin)
        d = f.r(3.0, 3.0)
        f.trait((c[0] - d[0], c[1] - d[1]), (c[0] + d[0], c[1] + d[1]))
    # Le nombre : 7 pt au-delà de la ligne, parallèle à elle, lisible.
    milieu = f.p((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)
    n_pt = f.r(nx * signe, ny * signe)
    de_plus = math.atan2(uy, ux)
    if de_plus > math.pi / 2:
        de_plus -= math.pi
    f.texte_centre(texte, (milieu[0] + 7.0 * n_pt[0], milieu[1] + 7.0 * n_pt[1]), 8.0, BLEU,
                   de_plus=de_plus)


def _rectangle(cx: float, cy: float, lx: float, ly: float) -> list[tuple[float, float]]:
    return [(cx - lx / 2, cy - ly / 2), (cx + lx / 2, cy - ly / 2),
            (cx + lx / 2, cy + ly / 2), (cx - lx / 2, cy + ly / 2)]


def _plan(*, echelle: int = 50, ecrite: str | None = "1/50", tirets_par_attribut: bool = False,
          corps_dans_tm: bool = False, gaine: bool = False) -> _Feuille:
    f = _Feuille(echelle=echelle, angle_deg=10.0, origine=(260.0, 150.0),
                 tirets_par_attribut=tirets_par_attribut, corps_dans_tm=corps_dans_tm)
    x_min, x_max = AXES_X[0][1], AXES_X[-1][1]
    y_min, y_max = AXES_Y[0][1], AXES_Y[-1][1]
    depasse = 1800.0
    rayon_pt = 10.0
    rayon_mm = rayon_pt * f.k

    # Les poteaux pleins aux nœuds, le voile, la poutre (deux traits).
    for _, x in AXES_X:
        for _, y in AXES_Y:
            if gaine and (x, y) == (6000.0, 5000.0):
                continue
            d = POTEAU_MM / 2.0
            f.plein([(x - d, y - d), (x + d, y - d), (x + d, y + d), (x - d, y + d)], 0.2)
    if gaine:
        # B2 : la cage d'ascenseur (1,9 × 1,8 m), la cabine, le chevron plein.
        f.contour(_rectangle(6000.0, 5000.0, 1900.0, 1800.0))
        f.contour(_rectangle(6000.0, 4900.0, 1200.0, 1000.0))
        f.plein([(5200.0, 5750.0), (6700.0, 5750.0), (5400.0, 5550.0), (5200.0, 4300.0)], 0.13)
    e = VOILE_MM / 2.0
    f.plein([(6000 + 150, 5000 - e), (12000 - 150, 5000 - e), (12000 - 150, 5000 + e),
             (6000 + 150, 5000 + e)], 0.35)
    f.style(NOIR, 0.6)
    for dy in (-125.0, 125.0):
        f.trait_mm((150.0, dy), (5850.0, dy))
    # Des murs non porteurs et du mobilier : des traits qui ne sont rien.
    for i in range(40):
        f.trait_mm((800.0 + 120.0 * i, 1500.0), (800.0 + 120.0 * i, 1900.0))

    # Les axes, découpés en trait mixte, et leurs bulles pointillées.
    for etiquette, x in AXES_X:
        a, b = (x, y_min - depasse), (x, y_max + depasse)
        f.style(ROUGE, 1.5)
        f.mixte(f.p(*a), f.p(*b))
        f.cercle_pointille(f.p(x, y_max + depasse + rayon_mm), rayon_pt)
        f.texte_centre(etiquette, f.p(x, y_max + depasse + rayon_mm), 10.0, ROUGE)
    for etiquette, y in AXES_Y:
        a, b = (x_min - depasse, y), (x_max + depasse, y)
        f.style(ROUGE, 1.5)
        f.mixte(f.p(*a), f.p(*b))
        f.cercle_pointille(f.p(x_min - depasse - rayon_mm, y), rayon_pt)
        f.texte_centre(etiquette, f.p(x_min - depasse - rayon_mm, y), 10.0, ROUGE)

    # Les cotes, en cm. Une chaîne sous la grille, la cote globale plus bas,
    # une chaîne à droite, une en haut — dont UNE écrite « 605 » (forcée).
    for (_, xa), (_, xb) in zip(AXES_X, AXES_X[1:], strict=False):
        _cote(f, (xa, y_min), (xb, y_min), -900.0, f"{(xb - xa) / 10:g}", attache_mm=300.0)
    _cote(f, (x_min, y_min), (x_max, y_min), -1400.0, f"{(x_max - x_min) / 10:g}",
          attache_mm=300.0)
    _cote(f, (x_max, y_min), (x_max, y_max), -900.0, f"{(y_max - y_min) / 10:g}",
          attache_mm=300.0)
    _cote(f, (x_min, y_min), (x_min, y_max), 900.0, f"{(y_max - y_min) / 10:g}",
          attache_mm=300.0)
    _cote(f, (x_min, y_max), (6000.0, y_max), 900.0, "600", attache_mm=300.0)
    _cote(f, (6000.0, y_max), (x_max, y_max), 900.0, "605", attache_mm=300.0)

    if gaine:
        # La lettre du noyau, trois fois la hauteur des étiquettes de bulle,
        # posée au bout de l'axe 2 (sans bulle de ce côté).
        f.texte_centre("B", f.p(x_max + depasse + 1500.0, AXES_Y[-1][1]), 30.0, NOIR)
    # Un repère de local : un nombre noir, sur aucune ligne de cote.
    f.texte("12", f.p(3000.0, 2500.0), 8.0, NOIR)
    # Le cartouche : l'échelle écrite, loin du dessin, non tournée.
    f.texte("PLAN FICTIF", (900.0, 60.0), 9.0, NOIR, tourne=False)
    if ecrite:
        f.texte(ecrite, (1080.0, 60.0), 9.0, NOIR, tourne=False)
    return f


def pdf_plan_vectoriel(**options: object) -> bytes:
    """La feuille de base : 1/50 écrit, tracé au 1/50, cotes en cm."""
    return assembler([_plan(**options).flux()])  # type: ignore[arg-type]


def pdf_plan_sans_echelle_ecrite() -> bytes:
    return assembler([_plan(ecrite=None).flux()])


def pdf_plan_hors_echelle() -> bytes:
    """« 1/50 » écrit, mais tracé au 1/100 : les cotes ne le confirment pas."""
    return assembler([_plan(echelle=100).flux()])


def pdf_plan_tirets_par_attribut() -> bytes:
    """Le motif des axes et des bulles par attribut ``d``, le corps dans ``Tm``."""
    return assembler([_plan(tirets_par_attribut=True, corps_dans_tm=True).flux()])


def pdf_plan_gaine() -> bytes:
    """La feuille de base, avec une cage d'ascenseur au lieu du poteau B2 et
    la lettre géante d'un noyau au bout de l'axe 2."""
    return assembler([_plan(gaine=True).flux()])


def pdf_deux_pages() -> bytes:
    return assembler([_plan().flux(), _plan().flux()])


def pdf_texte_seul() -> bytes:
    """Une page de cahier des charges : du texte et deux filets."""
    ops = ["0 0 0 RG 0.5 w 50 800 m 545 800 l S 50 60 m 545 60 l S"]
    for i, ligne in enumerate(("CAHIER DES CHARGES FICTIF", "Beton C30/37",
                               "Acier B500B")):
        ops.append(f"BT /F1 10 Tf 60 {760 - 20 * i} Td ({ligne}) Tj ET")
    return assembler([("\n".join(ops) + "\n").encode("cp1252")], largeur=595.0,
                     hauteur=842.0)
