"""L'unité d'un DXF qui ne la déclare pas, lue dans sa PRÉSENTATION.

Voir ``docs/GEOMETRIE_PIEUX_GAINES_UNITE.md`` (§ 4). Un dessin sans
``$INSUNITS`` peut quand même dire son unité, par deux sources qui se
recoupent :

* **écrite** : l'échelle du cartouche, « 1/100 », dans une présentation
  (textes, attributs, un niveau de bloc) ;
* **mesurée** : chaque fenêtre de cette présentation montre ``hauteur de vue``
  unités du dessin sur ``hauteur`` unités de papier ; le papier est en mm (ou
  en pouces) à l'échelle de traçage de la présentation.

Une paire (échelle écrite ``1/n``, fenêtre de rapport ``r`` unités du dessin
par mm de papier) donne ``n / r`` millimètres réels par unité du dessin. Elle
désigne une unité si ce nombre est celui de ``mm``, ``cm``, ``m``, ``in`` ou
``ft`` à 0,5 % près. L'unité est ÉTABLIE si toutes les fenêtres qu'une échelle
écrite explique désignent la même unité, et une seule. Sinon rien n'est
établi, et la raison est rendue.

Sur le plan de fondations mesuré : « 1/100 » écrit, 8 400 unités sur 840 mm
de papier → 100 / 10 = 10 mm par unité → cm, à 0 % près.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

__all__ = ["EchelleEcrite", "Fenetre", "Presentation", "lire_presentations",
           "unite_par_presentation"]

#: « 1/100 », « 1:50 », « ECH.: 1/100 » — pas une date (« 1/12/2017 »).
_ECRITE: Final[re.Pattern[str]] = re.compile(r"(?<![\d/.,])1\s?[:/]\s?(\d{1,4})(?![\d/.,])")
#: Le champ d'échelle d'un cartouche : l'échelle seule, ou précédée de son nom.
#: C'est lui qui est cité de préférence (pas un modèle de titre qui la répète).
_CHAMP: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:ECH(?:ELLE)?|SCHAAL|SCALE|MA(?:SS|ß)STAB)\.?\s*:?\s*)?1\s?[:/]\s?\d{1,4}$",
    re.IGNORECASE)
#: Les unités qu'une paire peut désigner : millimètres réels par unité.
_UNITES: Final[tuple[tuple[str, float], ...]] = (
    ("mm", 1.0), ("cm", 10.0), ("m", 1000.0), ("in", 25.4), ("ft", 304.8))
ECART_MAX: Final[float] = 0.005
#: Bornes de lecture : une présentation n'a pas besoin de plus.
TEXTES_MAX: Final[int] = 5000


@dataclass(frozen=True)
class Fenetre:
    poignee: str
    #: Hauteur sur le papier (unités de la présentation) et hauteur de la vue
    #: (unités du dessin).
    hauteur_papier: float
    hauteur_vue: float

    @property
    def rapport(self) -> float:
        return self.hauteur_vue / self.hauteur_papier


@dataclass(frozen=True)
class EchelleEcrite:
    n: int
    texte: str
    poignee: str
    calque: str


@dataclass(frozen=True)
class Presentation:
    nom: str
    #: ``mm`` ou ``in`` (réglage de traçage), ``None`` si inconnu.
    unite_papier: str | None
    #: Millimètres de papier par unité de la présentation (échelle de traçage
    #: comprise), ``None`` si l'unité du papier est inconnue.
    mm_par_unite_papier: float | None
    fenetres: tuple[Fenetre, ...]
    echelles: tuple[EchelleEcrite, ...]


def _textes(presentation: Any) -> list[tuple[str, str, str]]:
    """(texte, poignée, calque) des textes, attributs, et textes de blocs (un niveau)."""
    sortie: list[tuple[str, str, str]] = []

    def garder(texte: Any, entite: Any) -> None:
        if texte and len(sortie) < TEXTES_MAX:
            sortie.append((str(texte), str(entite.dxf.handle or ""), str(entite.dxf.layer)))

    for entite in presentation:
        if len(sortie) >= TEXTES_MAX:
            break
        genre = entite.dxftype()
        if genre == "TEXT":
            garder(entite.dxf.text, entite)
        elif genre == "MTEXT":
            garder(entite.plain_text(), entite)
        elif genre == "INSERT":
            for attribut in entite.attribs:
                garder(attribut.dxf.text, entite)
            try:
                virtuelles = list(entite.virtual_entities())
            except Exception:  # noqa: BLE001 — un bloc illisible ne dit rien
                continue
            for v in virtuelles:
                if v.dxftype() == "TEXT":
                    garder(v.dxf.text, entite)
                elif v.dxftype() == "MTEXT":
                    garder(v.plain_text(), entite)
    return sortie


def lire_presentations(document: Any) -> list[Presentation]:
    sortie: list[Presentation] = []
    for presentation in document.layouts:
        if presentation.name == "Model":
            continue
        reglages = presentation.dxf_layout.dxf
        unite = {1: "mm", 0: "in"}.get(reglages.get("plot_paper_units", None))
        mm_papier: float | None = None
        if unite is not None:
            numerateur = float(reglages.get("scale_numerator", 1.0) or 1.0)
            denominateur = float(reglages.get("scale_denominator", 1.0) or 1.0)
            mm_papier = (1.0 if unite == "mm" else 25.4) * numerateur / denominateur
        fenetres: list[Fenetre] = []
        for vp in presentation.query("VIEWPORT"):
            d = vp.dxf
            hauteur = float(d.get("height", 0.0) or 0.0)
            vue = float(d.get("view_height", 0.0) or 0.0)
            # La fenêtre n° 1 est la présentation elle-même, pas une vue du dessin.
            if d.get("id", 0) == 1 or hauteur <= 0 or vue <= 0:
                continue
            fenetres.append(Fenetre(str(d.handle or ""), hauteur, vue))
        echelles: list[EchelleEcrite] = []
        vues: set[tuple[int, str]] = set()
        for texte, poignee, calque in _textes(presentation):
            plat = " ".join(texte.split())[:80]
            for trouve in _ECRITE.finditer(texte):
                n = int(trouve.group(1))
                if 1 <= n <= 5000 and (n, plat) not in vues:
                    vues.add((n, plat))
                    echelles.append(EchelleEcrite(n, plat, poignee, calque))
        if fenetres or echelles:
            sortie.append(Presentation(presentation.name, unite, mm_papier, tuple(fenetres),
                                       tuple(echelles)))
    return sortie


def _unites_de(fenetre: Fenetre, presentation: Presentation
               ) -> dict[str, tuple[EchelleEcrite, float, float]]:
    """unité -> (échelle écrite, mm par unité, écart relatif) pour cette fenêtre."""
    trouvees: dict[str, tuple[EchelleEcrite, float, float]] = {}
    if presentation.mm_par_unite_papier is None:
        return trouvees
    def preference(e: EchelleEcrite, ecart: float) -> tuple[float, bool, int]:
        return (round(ecart, 9), not _CHAMP.match(e.texte), len(e.texte))

    for echelle in presentation.echelles:
        mm_par_unite = echelle.n * presentation.mm_par_unite_papier / fenetre.rapport
        for unite, facteur in _UNITES:
            ecart = abs(mm_par_unite - facteur) / facteur
            if ecart <= ECART_MAX and (
                    unite not in trouvees
                    or preference(echelle, ecart) < preference(trouvees[unite][0],
                                                               trouvees[unite][2])):
                trouvees[unite] = (echelle, mm_par_unite, ecart)
    return trouvees


def unite_par_presentation(presentations: list[Presentation]
                           ) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """(unité, citation, ``None``) si elle est établie ; (``None``, ``None``,
    raison) si la présentation ne suffit pas ; trois ``None`` si le dessin n'a
    aucune présentation qui parle d'échelle."""
    if not presentations:
        return None, None, None
    expliquees: list[tuple[Presentation, Fenetre, dict[str, Any]]] = []
    non_expliquees = 0
    for p in presentations:
        for f in p.fenetres:
            unites = _unites_de(f, p)
            if unites:
                expliquees.append((p, f, unites))
            else:
                non_expliquees += 1
    ecrites = sorted({f"1/{e.n}" for p in presentations for e in p.echelles})
    rapports = sorted({round(f.rapport, 4) for p in presentations for f in p.fenetres})
    if not expliquees:
        if not ecrites:
            return None, None, (
                f"presentation: {len(rapports)} fenetre(s) ({', '.join(map(str, rapports))} "
                "unites du dessin par unite de papier) mais aucune echelle ecrite: l'unite "
                "n'est pas deduite")
        if not rapports:
            return None, None, (
                f"presentation: echelle ecrite ({', '.join(ecrites)}) mais aucune fenetre: "
                "l'unite n'est pas deduite")
        return None, None, (
            f"presentation: aucune paire echelle ecrite ({', '.join(ecrites)}) / fenetre "
            f"({', '.join(map(str, rapports))} unites par unite de papier) ne tombe sur une "
            "unite connue a 0,5 % pres: l'unite n'est pas deduite")
    communes = set(expliquees[0][2])
    for _, _, unites in expliquees[1:]:
        communes &= set(unites)
    if len(communes) != 1:
        dit = sorted({u for _, _, unites in expliquees for u in unites})
        return None, None, (
            f"presentation: les fenetres et les echelles ecrites ({', '.join(ecrites)}) "
            f"designent {' ou '.join(dit)} — "
            + ("ambiguite" if communes else "contradiction")
            + ": l'unite n'est pas deduite")
    unite = communes.pop()
    p, f, unites = max(expliquees, key=lambda x: x[1].hauteur_papier)
    echelle, mm_par_unite, ecart = unites[unite]
    return unite, {
        "rule": ("echelle ecrite dans la presentation, confirmee par la fenetre: 1/n de "
                 "papier montre r unites du dessin, n/r millimetres par unite"),
        "layout": p.nom,
        "written": {"scale": f"1/{echelle.n}", "text": echelle.texte, "handle": echelle.poignee,
                    "layer": echelle.calque},
        "viewport": {"handle": f.poignee, "view_height": round(f.hauteur_vue, 6),
                     "paper_height": round(f.hauteur_papier, 6),
                     "drawing_units_per_paper_unit": round(f.rapport, 6)},
        "paper_unit": p.unite_papier,
        "mm_per_drawing_unit": round(mm_par_unite, 6),
        "deviation": round(ecart, 6),
        "viewports_explained": len(expliquees),
        "viewports_unexplained": non_expliquees,
    }, None
