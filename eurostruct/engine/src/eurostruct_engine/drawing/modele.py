"""Le modele geometrique d'une coupe — LA SEULE SOURCE DES COORDONNEES.

POURQUOI CE MODULE EXISTE
--------------------------
Le DXF telecharge et l'apercu affiche a l'ecran doivent montrer la meme poutre.
La facon sure d'y arriver n'est pas de relire deux codes en esperant qu'ils
concordent: c'est de n'avoir qu'un seul endroit ou une coordonnee est calculee.

Ce module est cet endroit. Il ne connait **aucune** bibliotheque de dessin —
ni ``ezdxf``, ni SVG, ni PDF. Il produit un :class:`ModeleSection` gele, que
les rendus consomment sans jamais recalculer quoi que ce soit. Un test verifie
qu'aucun import de rendu n'entre ici; c'est ce qui empeche la geometrie de se
dedoubler a la premiere retouche.

Repere: origine au coin inferieur gauche du beton, X vers la droite, Y vers le
haut, en millimetres vrais (cahier des charges §7.2, « echelle vraie »).
``plot_scale`` ne gouverne que la taille des annotations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from ..exceptions import InconsistentInput
from ..legal import DRAFT_WATERMARK, MANDATORY_NOTICE, Language
from ..version import ENGINE_VERSION
from .layers import (
    L_CARTOUCHE,
    L_COFFRAGE,
    L_COTATION,
    L_FERR_PRINCIPAL,
    L_FERR_TRANSVERSAL,
    L_TEXTE,
)

__all__ = [
    "LEGAL_NOTICE",
    "BarRow",
    "BeamSectionSpec",
    "Cote",
    "Disque",
    "ModeleSection",
    "Polyligne",
    "RebarScheduleRow",
    "Texte",
    "construire_modele",
    "masse_kg",
    "spec_depuis_dict",
]

#: Mention obligatoire — cahier des charges §9, sur chaque page de chaque
#: livrable. Prise dans :mod:`eurostruct_engine.legal` pour que les cinq
#: versions linguistiques ne divergent pas d'un type de document a l'autre.
LEGAL_NOTICE: Final = MANDATORY_NOTICE[Language.FR]

#: Bulge d'un arc de 90 degres dans une polyligne: tan(90/4).
_BULGE_90: Final = math.tan(math.radians(90.0) / 4.0)

#: Masse volumique nominale de l'acier — EN 1992-1-1 §3.2.7(3).
_STEEL_DENSITY_KG_PER_M3: Final = 7850.0


# ---------------------------------------------------------------------------
# Ce que l'appelant fournit
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BarRow:
    """Un lit de barres longitudinales identiques.

    :param count: nombre de barres du lit.
    :param diameter: diametre nominal, mm.
    :param mark: repere porte par le dessin et la nomenclature.
    :param length: longueur developpee d'une barre, mm, pour la nomenclature.
        Facultative: une coupe seule ne la determine pas, l'elevation si.
    """

    count: int
    diameter: float
    mark: str
    length: float | None = None

    def area(self) -> float:
        """Aire totale du lit, mm²."""
        return self.count * math.pi * self.diameter**2 / 4.0


@dataclass(frozen=True, slots=True)
class BeamSectionSpec:
    """Tout ce qu'il faut pour dessiner une coupe.

    :param b: largeur, mm.
    :param h: hauteur totale, mm.
    :param cover: enrobage nominal jusqu'a la face exterieure des cadres, mm
        (``c_nom``, EN 1992-1-1 §4.4.1).
    :param link_diameter: diametre des armatures transversales, mm.
    :param bottom: lits inferieurs (tendus).
    :param top: lits superieurs.
    :param link_spacing: espacement des cadres, mm, porte par l'etiquette.
    :param plot_scale: denominateur de l'echelle de trace, 20 pour 1:20.
    """

    b: float
    h: float
    cover: float
    link_diameter: float
    bottom: tuple[BarRow, ...] = ()
    top: tuple[BarRow, ...] = ()
    link_spacing: float | None = None
    link_mark: str = "C1"
    plot_scale: float = 20.0
    title: str = "COUPE POUTRE"
    project: str = ""
    element: str = ""
    concrete_grade: str = ""
    steel_grade: str = ""
    exposure_class: str = ""
    index: str = "A"
    date: str = ""
    #: Mention supplementaire portee par le cartouche — par exemple
    #: « PROJET — NON SIGNABLE » quand des parametres nationaux non confirmes
    #: ont pu servir. DISTINCTE du filigrane de brouillon: celui-la dit que
    #: personne n'a valide la feuille, celle-ci dit que les nombres eux-memes
    #: reposent sur des parametres qu'aucune source officielle n'a confirmes.
    #: Un dessin qui ne porterait que le premier se lirait « il ne manque
    #: qu'une signature », ce qui serait faux.
    mention: str = ""
    #: Langue des mentions imprimees (§11: FR/NL/EN/ES/DE).
    language: Language = Language.FR
    #: Faux tant qu'un ingenieur habilite n'a pas valide le calcul. Une feuille
    #: non validee porte le filigrane de brouillon — §9: un livrable que
    #: personne n'a signe ne doit pas ressembler a un livrable signe.
    validated: bool = False

    def __post_init__(self) -> None:
        if self.b <= 0 or self.h <= 0:
            raise InconsistentInput("b et h doivent etre strictement positifs")
        if self.cover < 0:
            raise InconsistentInput("l'enrobage ne peut pas etre negatif")
        free = self.b - 2.0 * (self.cover + self.link_diameter)
        if free <= 0:
            raise InconsistentInput(
                f"largeur insuffisante: b = {self.b} mm ne laisse aucune place "
                f"entre les cadres pour un enrobage de {self.cover} mm et des "
                f"cadres de {self.link_diameter} mm."
            )
        for row in (*self.bottom, *self.top):
            if row.count < 1:
                raise InconsistentInput(f"le lit '{row.mark}' doit compter au moins une barre")
            if row.count > 1 and row.count * row.diameter >= free:
                raise InconsistentInput(
                    f"le lit '{row.mark}' ({row.count} HA{row.diameter:g}) ne tient pas "
                    f"dans la largeur libre de {free:.0f} mm entre cadres."
                )


@dataclass(frozen=True, slots=True)
class RebarScheduleRow:
    """Une ligne de nomenclature — cahier des charges §7.2."""

    mark: str
    diameter: float
    count: int
    unit_length_mm: float | None
    total_length_mm: float | None
    mass_kg: float | None
    shape_code: str
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mark": self.mark,
            "diameter_mm": self.diameter,
            "count": self.count,
            "unit_length_mm": self.unit_length_mm,
            "total_length_mm": self.total_length_mm,
            "mass_kg": self.mass_kg,
            "shape_code": self.shape_code,
            "comment": self.comment,
        }


# ---------------------------------------------------------------------------
# Ce que le modele porte
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Polyligne:
    """Suite de sommets ``(x, y, bulge)``.

    ``bulge`` vaut la tangente du quart de l'angle de l'arc qui part du sommet;
    0 pour un segment droit. C'est la convention DXF, retenue ici parce qu'elle
    decrit un conge sans le discretiser: chaque rendu choisit sa finesse.
    """

    sommets: tuple[tuple[float, float, float], ...]
    calque: str
    fermee: bool = True


@dataclass(frozen=True, slots=True)
class Disque:
    """Une barre longitudinale vue en coupe."""

    x: float
    y: float
    rayon: float
    calque: str
    plein: bool = True


@dataclass(frozen=True, slots=True)
class Texte:
    contenu: str
    x: float
    y: float
    hauteur: float
    calque: str
    rotation: float = 0.0
    #: « gauche » ou « centre » — l'ancrage du point (x, y).
    ancrage: str = "gauche"
    #: Index de couleur ACI, ou None pour la couleur du calque.
    couleur: int | None = None


@dataclass(frozen=True, slots=True)
class Cote:
    """Une cote lineaire, avec la valeur qu'elle DOIT afficher.

    La valeur est portee par le modele plutot que laissee au moteur de cotation
    du format: un rendu qui afficherait autre chose que ``valeur`` serait faux,
    et c'est verifiable.
    """

    base: tuple[float, float]
    p1: tuple[float, float]
    p2: tuple[float, float]
    angle: float
    valeur: float
    calque: str = L_COTATION


@dataclass(frozen=True, slots=True)
class ModeleSection:
    """Une coupe entiere, gelee. Les rendus n'y ajoutent aucune coordonnee."""

    #: Les valeurs d'origine, telles que le calcul les a fixees. Elles sont
    #: conservees a cote de la geometrie pour qu'un controle puisse confronter
    #: ce qui est dessine a ce qui a ete demande, sans re-mesurer le trace.
    b: float
    h: float
    enrobage: float
    diametre_cadre: float
    espacement_cadre: float | None
    echelle: float

    polylignes: tuple[Polyligne, ...]
    disques: tuple[Disque, ...]
    textes: tuple[Texte, ...]
    cotes: tuple[Cote, ...]
    nomenclature: tuple[RebarScheduleRow, ...]

    titre: str
    mention: str
    notice: str
    #: Filigrane de brouillon, ou chaine vide si la feuille est validee.
    filigrane: str

    @property
    def barres(self) -> tuple[Disque, ...]:
        """Les barres longitudinales seules — sans les cadres ni le coffrage."""
        return tuple(d for d in self.disques if d.calque == L_FERR_PRINCIPAL)

    def etendue(self) -> tuple[float, float, float, float]:
        """Boite englobante du COFFRAGE seul, mm: (x0, y0, x1, y1).

        Volontairement pas celle de la feuille: c'est la section qu'un controle
        veut confronter au calcul, pas le cartouche ni les etiquettes.
        """
        xs: list[float] = []
        ys: list[float] = []
        for p in self.polylignes:
            if p.calque != L_COFFRAGE:
                continue
            xs.extend(s[0] for s in p.sommets)
            ys.extend(s[1] for s in p.sommets)
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# La construction, une seule fois
# ---------------------------------------------------------------------------
def _rounded_rect_points(
    x0: float, y0: float, x1: float, y1: float, r: float
) -> tuple[tuple[float, float, float], ...]:
    """Sommets d'un rectangle a coins arrondis, ``(x, y, bulge)``, sens direct.

    Sert au trace de l'axe d'un cadre ferme, dont les coins suivent le rayon de
    mandrin d'EN 1992-1-1 §8.3.
    """
    b = _BULGE_90
    return (
        (x0 + r, y0, 0.0),
        (x1 - r, y0, b),
        (x1, y0 + r, 0.0),
        (x1, y1 - r, b),
        (x1 - r, y1, 0.0),
        (x0 + r, y1, b),
        (x0, y1 - r, 0.0),
        (x0, y0 + r, b),
    )


def _bar_x_positions(spec: BeamSectionSpec, row: BarRow) -> list[float]:
    """Abscisses des centres de barres d'un lit, reparties regulierement.

    Les barres extremes touchent la face interieure des cadres, decalees d'un
    demi-diametre.
    """
    inset = spec.cover + spec.link_diameter + row.diameter / 2.0
    left, right = inset, spec.b - inset
    if row.count == 1:
        return [spec.b / 2.0]
    step = (right - left) / (row.count - 1)
    return [left + i * step for i in range(row.count)]


def masse_kg(diameter_mm: float, length_mm: float) -> float:
    """Masse d'une barre, kg, depuis son diametre nominal et sa longueur."""
    area_m2 = math.pi * (diameter_mm / 1000.0) ** 2 / 4.0
    return area_m2 * (length_mm / 1000.0) * _STEEL_DENSITY_KG_PER_M3


def _schedule_row(row: BarRow, shape_code: str, comment: str) -> RebarScheduleRow:
    total = row.length * row.count if row.length is not None else None
    return RebarScheduleRow(
        mark=row.mark,
        diameter=row.diameter,
        count=row.count,
        unit_length_mm=row.length,
        total_length_mm=total,
        mass_kg=masse_kg(row.diameter, total) if total is not None else None,
        shape_code=shape_code,
        comment=comment,
    )


def wrap(text: str, width: int) -> list[str]:
    """Retour a la ligne glouton, deterministe pour une entree donnee.

    Fait ici et pas par un moteur de texte: un DXF ne sait pas refluer, et la
    mention doit rester lisible quel que soit le logiciel qui l'ouvre.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def construire_modele(spec: BeamSectionSpec) -> ModeleSection:
    """La geometrie de la coupe, calculee une fois, pour tous les rendus."""
    s = spec.plot_scale
    txt_h = 2.5 * s  # 2,5 mm sur la feuille tracee

    polylignes: list[Polyligne] = []
    disques: list[Disque] = []
    textes: list[Texte] = []
    cotes: list[Cote] = []
    nomenclature: list[RebarScheduleRow] = []

    # --- contour du beton --------------------------------------------------
    polylignes.append(Polyligne(
        sommets=((0.0, 0.0, 0.0), (spec.b, 0.0, 0.0),
                 (spec.b, spec.h, 0.0), (0.0, spec.h, 0.0)),
        calque=L_COFFRAGE,
    ))

    # --- cadre ferme -------------------------------------------------------
    # Axe du cadre, rentre de l'enrobage plus un demi-diametre de cadre.
    off = spec.cover + spec.link_diameter / 2.0
    # Diametre minimal de mandrin, EN 1992-1-1 Tab. 8.1N: 4*phi jusqu'a 16 mm,
    # 7*phi au-dela. Le rayon a l'axe ajoute un demi-diametre.
    mandrel = 4.0 if spec.link_diameter <= 16.0 else 7.0
    r_centre = mandrel * spec.link_diameter / 2.0 + spec.link_diameter / 2.0
    r_centre = min(r_centre, (min(spec.b, spec.h) - 2.0 * off) / 2.0)
    polylignes.append(Polyligne(
        sommets=_rounded_rect_points(off, off, spec.b - off, spec.h - off, r_centre),
        calque=L_FERR_TRANSVERSAL,
    ))

    # --- barres longitudinales ---------------------------------------------
    for row in spec.bottom:
        y = spec.cover + spec.link_diameter + row.diameter / 2.0
        for x in _bar_x_positions(spec, row):
            disques.append(Disque(x=x, y=y, rayon=row.diameter / 2.0,
                                  calque=L_FERR_PRINCIPAL))
        nomenclature.append(_schedule_row(row, "00", "lit inferieur"))
    for row in spec.top:
        y = spec.h - (spec.cover + spec.link_diameter + row.diameter / 2.0)
        for x in _bar_x_positions(spec, row):
            disques.append(Disque(x=x, y=y, rayon=row.diameter / 2.0,
                                  calque=L_FERR_PRINCIPAL))
        nomenclature.append(_schedule_row(row, "00", "lit superieur"))

    if spec.link_diameter > 0:
        # Longueur developpee de l'axe REELLEMENT trace: le perimetre a angles
        # vifs, moins ce que chaque conge a 90 degres retranche. La garder
        # coherente avec la geometrie compte — la nomenclature et le dessin
        # doivent decrire la meme barre.
        sharp = 2.0 * ((spec.b - 2.0 * off) + (spec.h - 2.0 * off))
        bend_saving = 4.0 * r_centre * (2.0 - math.pi / 2.0)
        developed = sharp - bend_saving
        nomenclature.append(RebarScheduleRow(
            mark=spec.link_mark,
            diameter=spec.link_diameter,
            count=1,
            unit_length_mm=developed,
            total_length_mm=developed,
            mass_kg=masse_kg(spec.link_diameter, developed),
            shape_code="51",
            comment=(
                (f"cadre ferme, espacement {spec.link_spacing:g} mm. "
                 if spec.link_spacing else "cadre ferme. ")
                + "Longueur developpee du trace: retours d'ancrage NON compris "
                "(EN 1992-1-1 §8.5) — a completer par le module de faconnage."
            ),
        ))

    # --- cotation ----------------------------------------------------------
    off_dim = 18.0 * s
    cotes.append(Cote(base=(spec.b / 2.0, -off_dim), p1=(0.0, 0.0),
                      p2=(spec.b, 0.0), angle=0.0, valeur=spec.b))
    cotes.append(Cote(base=(-off_dim, spec.h / 2.0), p1=(0.0, 0.0),
                      p2=(0.0, spec.h), angle=90.0, valeur=spec.h))

    # --- annotations -------------------------------------------------------
    titre = f"{spec.title} {spec.element}".strip()
    textes.append(Texte(titre, 0.0, spec.h + 6.0 * s, txt_h * 1.4, L_TEXTE))
    textes.append(Texte(
        f"{spec.b:g} x {spec.h:g} mm — enrobage {spec.cover:g} mm",
        0.0, spec.h + 2.5 * s, txt_h, L_TEXTE))

    label_x = spec.b + 8.0 * s
    line = 0
    for row in spec.bottom:
        textes.append(Texte(f"{row.mark}: {row.count} HA{row.diameter:g} (inf.)",
                            label_x, spec.h * 0.25 - line * 4.0 * s, txt_h, L_TEXTE))
        line += 1
    for row in spec.top:
        textes.append(Texte(f"{row.mark}: {row.count} HA{row.diameter:g} (sup.)",
                            label_x, spec.h * 0.75 + line * 4.0 * s, txt_h, L_TEXTE))
        line += 1
    if spec.link_diameter > 0:
        sp = f" e = {spec.link_spacing:g} mm" if spec.link_spacing else ""
        textes.append(Texte(f"{spec.link_mark}: cadre HA{spec.link_diameter:g}{sp}",
                            label_x, spec.h * 0.5, txt_h, L_TEXTE))

    notice = MANDATORY_NOTICE[spec.language]
    cadre, lignes = _cartouche(spec, txt_h, notice)
    polylignes.append(cadre)
    textes.extend(lignes)

    filigrane = "" if spec.validated else DRAFT_WATERMARK[spec.language]
    if filigrane:
        textes.append(Texte(filigrane, spec.b / 2.0, spec.h / 2.0, txt_h * 2.2,
                            L_TEXTE, rotation=45.0, ancrage="centre", couleur=8))

    return ModeleSection(
        b=spec.b, h=spec.h, enrobage=spec.cover,
        diametre_cadre=spec.link_diameter, espacement_cadre=spec.link_spacing,
        echelle=spec.plot_scale,
        polylignes=tuple(polylignes), disques=tuple(disques),
        textes=tuple(textes), cotes=tuple(cotes),
        nomenclature=tuple(nomenclature),
        titre=titre, mention=spec.mention, notice=notice, filigrane=filigrane,
    )


def _cartouche(spec: BeamSectionSpec, txt_h: float,
               notice: str) -> tuple[Polyligne, list[Texte]]:
    """Cartouche — son cadre ET ses lignes, cahier des charges §9.

    Les deux sortent d'ici ensemble parce qu'ils partagent le meme coin: les
    calculer separement ferait deriver le texte hors du cadre a la premiere
    retouche de l'un des deux.
    """
    s = spec.plot_scale
    w, h = 180.0 * s, 46.0 * s
    x0 = spec.b + 8.0 * s
    y0 = -h - 26.0 * s
    cadre = Polyligne(
        sommets=((x0, y0, 0.0), (x0 + w, y0, 0.0),
                 (x0 + w, y0 + h, 0.0), (x0, y0 + h, 0.0)),
        calque=L_CARTOUCHE,
    )

    elements: list[Texte] = []
    pad = 2.0 * s
    rows = (
        spec.project or "—",
        f"Element: {spec.element or '—'}    Indice: {spec.index}    Date: {spec.date or '—'}",
        f"Beton: {spec.concrete_grade or '—'}    Acier: {spec.steel_grade or '—'}"
        f"    Exposition: {spec.exposure_class or '—'}",
        f"Echelle 1:{spec.plot_scale:g}    Cotes en mm    "
        f"Moteur: eurostruct-engine {ENGINE_VERSION}",
    )
    y = y0 + h - pad - txt_h
    for i, text in enumerate(rows):
        elements.append(Texte(text, x0 + pad, y, txt_h * (1.3 if i == 0 else 1.0),
                              L_CARTOUCHE))
        y -= txt_h * 2.0

    # LA MENTION AVANT LA NOTICE, ET PLUS GRASSE. Elle dit que les nombres
    # eux-memes reposent sur des parametres non confirmes; la notice dit qu'un
    # ingenieur doit relire. Un lecteur qui ne lirait qu'une ligne doit lire
    # celle-la.
    if spec.mention:
        y -= txt_h * 0.4
        for chunk in wrap(spec.mention, 64):
            elements.append(Texte(chunk, x0 + pad, y, txt_h * 1.1, L_CARTOUCHE))
            y -= txt_h * 1.5

    y -= txt_h * 0.4
    for chunk in wrap(notice, 78):
        elements.append(Texte(chunk, x0 + pad, y, txt_h * 0.85, L_CARTOUCHE))
        y -= txt_h * 1.2

    return cadre, elements


def spec_depuis_dict(donnees: dict) -> BeamSectionSpec:
    """Recompose une coupe depuis sa forme sérialisée.

    LA COUPE EST GELÉE AVEC L'ÉTUDE, PAS RECALCULÉE À L'AFFICHAGE. Un plan
    produit six mois plus tard doit montrer la section qui a été *vérifiée*,
    pas celle qu'un moteur d'aujourd'hui déduirait des mêmes entrées. Cette
    fonction est donc le seul chemin de retour, et elle ne complète aucune
    valeur absente : ce qui n'a pas été gelé n'est pas inventé.
    """
    def _lits(cle: str) -> tuple[BarRow, ...]:
        return tuple(
            BarRow(count=int(r["count"]), diameter=float(r["diameter"]),
                   mark=str(r.get("mark") or ""))
            for r in (donnees.get(cle) or ()))

    return BeamSectionSpec(
        b=float(donnees["b"]),
        h=float(donnees["h"]),
        cover=float(donnees["cover"]),
        link_diameter=float(donnees["link_diameter"]),
        bottom=_lits("bottom"),
        top=_lits("top"),
        link_spacing=(None if donnees.get("link_spacing") is None
                      else float(donnees["link_spacing"])),
        link_mark=str(donnees.get("link_mark") or "C1"),
        plot_scale=float(donnees.get("plot_scale") or 20.0),
        element=str(donnees.get("element") or ""),
        concrete_grade=str(donnees.get("concrete_grade") or ""),
        steel_grade=str(donnees.get("steel_grade") or ""),
        exposure_class=str(donnees.get("exposure_class") or ""),
    )
