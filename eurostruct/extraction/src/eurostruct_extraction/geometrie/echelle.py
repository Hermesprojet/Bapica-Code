"""L'échelle d'une feuille PDF : écrite ET confirmée par ses cotes, ou rien.

Un PDF mesure en points (1/72 de pouce). Passer aux millimètres réels exige
l'échelle du dessin — une valeur qu'on ne suppose pas (interdiction 2). Elle
est établie par DEUX sources qui concordent :

* écrite : un mot « 1/50 » ou « 1:50 » sur la feuille, cité avec sa boîte ;
* confirmée : les cotes reconstituées dont le nombre égale la longueur mesurée
  à cette échelle — au moins cinq, et au moins 60 % d'entre elles. L'unité des
  nombres (mm, cm, m) est celle qui concorde, et elle est citée.

Une échelle que seules les cotes suggèrent, sans être écrite, est DITE, pas
appliquée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

from .primitives import Texte

__all__ = ["Echelle", "etablir_echelle", "mm_par_point"]

MM_PAR_POINT_PAPIER: Final[float] = 25.4 / 72.0
_ECRITE: Final[re.Pattern[str]] = re.compile(r"1\s?[:/]\s?(\d{1,4})")
#: Les échelles qu'on cherche quand aucune n'est écrite — pour le dire, jamais
#: pour l'appliquer.
_COURANTES: Final[tuple[int, ...]] = (1, 2, 5, 10, 20, 25, 50, 75, 100, 200, 250, 500, 1000)
_UNITES: Final[tuple[tuple[str, float], ...]] = (("mm", 1.0), ("cm", 10.0), ("m", 1000.0))
COTES_MIN: Final[int] = 5
PART_MIN: Final[float] = 0.6


def mm_par_point(n: int) -> float:
    """Millimètres réels par point-papier à l'échelle 1/n."""
    return MM_PAR_POINT_PAPIER * n


def _demi_unite(texte: str) -> float:
    for separateur in (",", "."):
        if separateur in texte:
            return 0.5 * 10 ** (-len(texte.split(separateur)[-1]))
    return 0.5


def _concordantes(cotes: list[tuple[str, float, float]], n: int, mm_unite: float
                  ) -> list[tuple[str, float, float]]:
    k = mm_par_point(n)
    sortie = []
    for texte, valeur, mesure_pt in cotes:
        ecrit = valeur * mm_unite
        tolerance = max(_demi_unite(texte) * mm_unite, 0.005 * ecrit, 1.0)
        if abs(ecrit - mesure_pt * k) <= tolerance:
            sortie.append((texte, valeur, mesure_pt))
    return sortie


@dataclass
class Echelle:
    etablie: bool = False
    n: int | None = None
    unite_des_cotes: str | None = None
    mm_par_unite_des_cotes: float = 1.0
    concordantes: int = 0
    cotes: int = 0
    ecrites: list[dict[str, Any]] = field(default_factory=list)
    exemples: list[str] = field(default_factory=list)
    note: str | None = None

    def en_json(self) -> dict[str, Any]:
        return {"established": self.etablie, "scale": f"1/{self.n}" if self.n else None,
                "dimension_unit": self.unite_des_cotes, "concordant": self.concordantes,
                "dimensions": self.cotes, "written": self.ecrites[:5],
                "examples": self.exemples[:8], "note": self.note}

    def citation(self) -> dict[str, Any]:
        """Les deux sources, pour le fondement de chaque longueur."""
        ecrite = next((e for e in self.ecrites if e["scale"] == f"1/{self.n}"), None)
        return {
            "rule": ("echelle ecrite sur la feuille, confirmee par les cotes: leur nombre "
                     "egale la longueur mesuree a cette echelle"),
            "scale": f"1/{self.n}", "written": ecrite,
            "dimension_unit": self.unite_des_cotes,
            "concordant_dimensions": self.concordantes, "dimensions_read": self.cotes,
            "examples": self.exemples[:8],
        }


def etablir_echelle(mots: list[Texte], cotes: list[tuple[str, float, float]]) -> Echelle:
    """``cotes`` : (texte, valeur, longueur mesurée en points) de chaque cote."""
    echelle = Echelle(cotes=len(cotes))
    ecrites: dict[int, dict[str, Any]] = {}
    for mot in mots:
        m = _ECRITE.fullmatch(mot.texte.strip())
        if m and 1 <= int(m.group(1)) <= 1000:
            n = int(m.group(1))
            ecrites.setdefault(n, {"scale": f"1/{n}", "text": mot.texte.strip(),
                                   "box_pt": [round(v, 2) for v in mot.boite]})
    echelle.ecrites = list(ecrites.values())

    meilleur: tuple[int, int, str, float, list[Any]] | None = None
    for n in ecrites:
        for unite, mm in _UNITES:
            ok = _concordantes(cotes, n, mm)
            if meilleur is None or len(ok) > meilleur[0]:
                meilleur = (len(ok), n, unite, mm, ok)
    if (meilleur is not None and meilleur[0] >= COTES_MIN
            and meilleur[0] >= PART_MIN * len(cotes)):
        nombre, n, unite, mm, ok = meilleur
        echelle.etablie = True
        echelle.n, echelle.unite_des_cotes, echelle.mm_par_unite_des_cotes = n, unite, mm
        echelle.concordantes = nombre
        echelle.exemples = sorted({t for t, _, _ in ok}, key=lambda t: -float(t.replace(",", ".")))
        return echelle

    # NON ETABLIE: dire pourquoi, et ce que les cotes suggèrent sans l'appliquer.
    # Sans échelle écrite, « 600 » au 1/5 en mm et au 1/50 en cm sont la même
    # lecture : toutes les lectures aussi concordantes sont dites.
    par_lecture = {(n, unite): len(_concordantes(cotes, n, mm))
                   for n in _COURANTES for unite, mm in _UNITES}
    plus = max(par_lecture.values(), default=0)
    lectures = [f"1/{n} lues en {unite}" for (n, unite), nombre in par_lecture.items()
                if nombre == plus]
    if not cotes:
        echelle.note = "aucune cote reconstituee: l'echelle ne peut pas etre confirmee"
    elif not ecrites:
        echelle.note = "aucune echelle ecrite sur la feuille"
    else:
        ecrit = ", ".join(e["scale"] for e in echelle.ecrites)
        echelle.note = (f"echelle ecrite ({ecrit}) non confirmee par les cotes"
                        + (f": {meilleur[0]} sur {len(cotes)} concordent" if meilleur else ""))
    if plus >= COTES_MIN and plus >= PART_MIN * len(cotes):
        echelle.note += (f"; les cotes suggerent {' ou '.join(lectures)} ({plus} sur "
                         f"{len(cotes)}), non applique sans echelle ecrite qui le dise")
    if meilleur:
        echelle.concordantes = meilleur[0]
    echelle.note = (echelle.note or "") + ": les longueurs restent en points-papier, sans unite"
    return echelle
