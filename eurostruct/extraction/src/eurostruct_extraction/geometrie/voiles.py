"""Les voiles : des contours longs et minces, ou deux traits parallèles sur un calque de voile.

RECONNUS PAR LEUR CALQUE (`VOILES`, `MURS`, `S-WALL`, `WANDEN`) ou, sur un
calque générique, par une convention de dessin courante : un rectangle long,
mince et PLEIN (hachuré) est un voile coupé — une poutre, elle, est vue en
dessous et dessinée en contour ou en tirets. Le fondement dit laquelle des
deux règles a servi.

UN VOILE COMPOSITE (en L, en T) RESTE UN APPUI. Son contour se découpe par la
bande d'une poutre comme celui d'un poteau ; aucune épaisseur n'en est
proposée, faute de savoir laquelle.
"""

from __future__ import annotations

from typing import Final

from .appariement import apparier
from .classification import classer
from .modele import Grille, Voile, preuve_de
from .noyau import Point, Tolerances, centroide, rectangle_de
from .poteaux import ELANCEMENT_MAX, Forme
from .primitives import PrimitivesDxf, Segment

__all__ = ["detecter_voiles"]

#: Épaisseur plausible d'un voile (mm réels), quand l'unité est connue.
EPAISSEUR_MIN_MM: Final[float] = 80.0
EPAISSEUR_MAX_MM: Final[float] = 600.0


def _epaisseur_plausible(e: float, tolerances: Tolerances, entraxe: float | None) -> bool:
    if tolerances.mm_par_unite:
        return EPAISSEUR_MIN_MM <= e * tolerances.mm_par_unite <= EPAISSEUR_MAX_MM
    if entraxe:
        return e <= 0.1 * entraxe
    return False


def detecter_voiles(prims: PrimitivesDxf, tolerances: Tolerances, grille: Grille,
                    formes: list[Forme], formes_prises: set[int]
                    ) -> tuple[list[Voile], set[int], set[int]]:
    """Les voiles, les rangs des formes et les ``id`` des segments utilisés."""
    entraxe = grille.entraxe_median()
    trouves: list[tuple[tuple[Point, ...], tuple[Point, Point] | None, float | None,
                        float | None, list, str, str | None, float]] = []
    prises: set[int] = set()
    for rang, forme in enumerate(formes):
        if rang in formes_prises or forme.genre == "cercle":
            continue
        role = forme.classement.role
        rect = rectangle_de(forme.points, tolerances)
        if role == "voile" or (role == "poteau" and rect is not None
                               and rect.elancement > ELANCEMENT_MAX):
            regle, motif, confiance = forme.classement.regle, forme.classement.motif, 0.8
        elif (role == "inconnu" and forme.rempli and rect is not None
              and rect.elancement >= ELANCEMENT_MAX
              and _epaisseur_plausible(rect.petit_cote, tolerances, entraxe)):
            regle, motif, confiance = "forme", None, 0.55
        else:
            continue
        prises.add(rang)
        if rect is not None:
            u = rect.direction_longue()
            demi = rect.grand_cote / 2.0
            axe = ((rect.centre[0] - u[0] * demi, rect.centre[1] - u[1] * demi),
                   (rect.centre[0] + u[0] * demi, rect.centre[1] + u[1] * demi))
            trouves.append((forme.points, axe, rect.petit_cote, rect.grand_cote,
                            list(forme.primitives), regle, motif, confiance))
        else:
            trouves.append((forme.points, None, None, None, list(forme.primitives),
                            regle, motif, confiance))

    # DEUX TRAITS PARALLELES SUR UN CALQUE DE VOILE — hors les traits d'un
    # contour déjà reconnu (le voile ci-dessus, ou un poteau).
    sources_prises = {p.source.cle for rang in prises | formes_prises
                      for p in formes[rang].primitives}
    segments_voile: list[Segment] = [
        s for s in prims.segments
        if not s.courbe and s.source.cle not in sources_prises
        and classer(s.calque, s.source.blocs, s.type_ligne).role == "voile"]
    segments_pris: set[int] = set()
    if segments_voile:
        if tolerances.mm_par_unite:
            e_min = EPAISSEUR_MIN_MM / tolerances.mm_par_unite
            e_max = EPAISSEUR_MAX_MM / tolerances.mm_par_unite
        elif entraxe:
            e_min, e_max = 0.005 * entraxe, 0.1 * entraxe
        else:
            e_min = e_max = 0.0
        if e_max > 0:
            for paire in apparier(segments_voile, tolerances, largeur_min=e_min,
                                  largeur_max=e_max):
                longueur = paire.fin - paire.debut
                if longueur < 2.0 * paire.largeur:
                    continue
                u, n = paire.u, (-paire.u[1], paire.u[0])
                o = (paire.decalage * n[0], paire.decalage * n[1])
                a = (o[0] + paire.debut * u[0], o[1] + paire.debut * u[1])
                b = (o[0] + paire.fin * u[0], o[1] + paire.fin * u[1])
                h = paire.largeur / 2.0
                contour = ((a[0] - n[0] * h, a[1] - n[1] * h), (b[0] - n[0] * h, b[1] - n[1] * h),
                           (b[0] + n[0] * h, b[1] + n[1] * h), (a[0] + n[0] * h, a[1] + n[1] * h))
                classement = classer(paire.segments[0].calque, paire.segments[0].source.blocs,
                                     paire.segments[0].type_ligne)
                trouves.append((contour, (a, b), paire.largeur, longueur,
                                list(paire.segments), classement.regle, classement.motif, 0.8))
                segments_pris.update(id(s) for s in paire.segments)

    trouves.sort(key=lambda x: (round(centroide(x[0])[1], 6), round(centroide(x[0])[0], 6)))
    voiles = [Voile(id=f"wall:{rang}", contour=tuple(contour), axe=axe, epaisseur=epaisseur,
                    longueur=longueur, preuve=preuve_de(sources, regle, motif),
                    confiance=confiance)
              for rang, (contour, axe, epaisseur, longueur, sources, regle, motif, confiance)
              in enumerate(trouves, start=1)]
    return voiles, prises, segments_pris
