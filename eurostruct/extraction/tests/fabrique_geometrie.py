"""Des plans DXF FABRIQUÉS pour la lecture géométrique — aucun plan réel.

Chaque fabrique suit une convention de dessin courante, et la nomme :

* ``dxf_coffrage_s101`` : un plan de coffrage belge en cm, tout sur un calque
  GÉNÉRIQUE (``COFFRAGE``) — poteaux pleins aux nœuds, poutres en rectangles,
  repères par travée, notes générales, cartouche, coupe au 1/20. Les éléments
  ne s'y reconnaissent que par leur forme et leur position. Optionnellement
  tourné, ou sans unité déclarée ;
* ``dxf_charpente_mm`` : calques normés AIA (``S-GRID``, ``S-COLS``…), en mm —
  poteaux en BLOCS (dont un tourné), bulles d'axes en blocs à attribut, poutres
  en PAIRES DE TRAITS cachés interrompues aux poteaux, une poutre secondaire
  portée par deux poutres, une console, un voile porteur, une cote forcée qui
  contredit le dessin ;
* ``dxf_sans_calques_m`` : tout sur le calque ``0``, en mètres — axes par type
  de ligne, poteaux hachurés ;
* ``dxf_refus`` : une référence externe, une poutre courbe, une poutre sans
  appui ;
* ``dxf_grille_polaire`` : six axes rayonnants autour d'un centre ;
* ``dxf_cercle_sans_unite`` : un seul cercle, sans unité déclarée — la forme
  du fichier réel « R12_with_trash_beyond_EOF.dxf » des tests d'ezdxf, qui
  prenait 30 s ;
* ``dxf_grande_grille`` : n × n axes, pour le temps de lecture ;
* ``dxf_fondations_pieux`` : un plan de fondations SANS unité déclarée, dont la
  PRÉSENTATION dit l'échelle (« 1/100 », fenêtre à 10 unités par mm) — poteaux
  préfabriqués sur des socles cachés concentriques, une paroi de pieux sécants
  dessinée deux fois (calque et xréf) avec remplissages et lentilles, des pieux
  aux nœuds (calque, bloc, repère), une cage d'ascenseur (cabine, chevron), une
  trémie barrée, une gaine nommée, une semelle ;
* ``dxf_etiquettes_d_axes`` : une lettre géante et une lettre égarée au bout
  d'axes à bulle, deux bulles qui se contredisent, un pieu numéroté au bout
  d'un axe.

Tous les textes disent FICTIF là où un plan réel porterait un nom.
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable

Point = tuple[float, float]


def _ecrire(document) -> bytes:  # noqa: ANN001 — un document ezdxf
    flux = io.StringIO()
    document.write(flux)
    return flux.getvalue().encode("utf-8")


# ----------------------------------------------------------------- S-101
def dxf_coffrage_s101(*, insunits: int = 5, rotation_deg: float = 0.0,
                      declaration: bool = True, note_portee: str | None = None) -> bytes:
    """Le plan de coffrage S-101 (cm) : 3 files A–C, 2 files 1–2, 6 poteaux,
    poutres P1/P2 (file 1), P3/P4 (file 2), P5 (file B), deux dalles.

    Aucun texte n'y écrit une portée ; ``note_portee`` en ajoute une aux notes
    (« Portée P1 : 6,50 m »), pour confronter le texte à la géométrie."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    angle = math.radians(rotation_deg)

    def T(p: Point) -> Point:  # noqa: N802 — la transformation du plan entier
        return (p[0] * math.cos(angle) - p[1] * math.sin(angle),
                p[0] * math.sin(angle) + p[1] * math.cos(angle))

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    for nom, couleur, trait in (("AXES", 1, "DASHDOT"), ("COFFRAGE", 7, "CONTINUOUS"),
                                ("COTES", 3, "CONTINUOUS"), ("TEXTES", 7, "CONTINUOUS"),
                                ("FERRAILLAGE", 5, "CONTINUOUS"), ("CADRE", 7, "CONTINUOUS")):
        doc.layers.add(nom, color=couleur, linetype=trait)

    def texte(t: str, x: float, y: float, h: float = 12.5, align=A.BOTTOM_LEFT,  # noqa: ANN001
              rot: float = 0.0, calque: str = "TEXTES") -> None:
        msp.add_text(t, height=h, rotation=rot + rotation_deg,
                     dxfattribs={"layer": calque}).set_placement(T((x, y)), align=align)

    def ligne(p: Point, q: Point, calque: str = "COFFRAGE") -> None:
        msp.add_line(T(p), T(q), dxfattribs={"layer": calque})

    def rect(x0: float, y0: float, x1: float, y1: float, calque: str = "COFFRAGE") -> None:
        msp.add_lwpolyline([T(p) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))],
                           close=True, dxfattribs={"layer": calque})

    def cote(p1: Point, p2: Point, base: Point, angle_cote: float = 0.0,
             style: str = "COTES_CM") -> None:
        msp.add_linear_dim(base=T(base), p1=T(p1), p2=T(p2), angle=angle_cote + rotation_deg,
                           dimstyle=style, dxfattribs={"layer": "COTES"}).render()

    rect(-350, -560, 1750, 925, "CADRE")
    axes_x = {"A": 0.0, "B": 600.0, "C": 1050.0}
    axes_y = {"1": 0.0, "2": 600.0}
    for nom, x in axes_x.items():
        ligne((x, -90), (x, 700), "AXES")
        msp.add_circle(T((x, 735)), 32, dxfattribs={"layer": "AXES"})
        texte(nom, x, 735, 25, A.MIDDLE_CENTER, calque="AXES")
    for nom, y in axes_y.items():
        ligne((-90, y), (1140, y), "AXES")
        msp.add_circle(T((-125, y)), 32, dxfattribs={"layer": "AXES"})
        texte(nom, -125, y, 25, A.MIDDLE_CENTER, calque="AXES")

    style = doc.dimstyles.duplicate_entry("EZDXF", "COTES_CM")
    style.dxf.dimtxt, style.dxf.dimasz, style.dxf.dimtsz = 12.5, 0, 6
    style.dxf.dimexe, style.dxf.dimexo, style.dxf.dimgap = 8, 6, 4
    style.dxf.dimdec, style.dxf.dimtad, style.dxf.dimlfac = 0, 1, 1
    for (x0, x1), y in (((0, 600), 800), ((600, 1050), 800), ((0, 1050), 860)):
        cote((x0, 700), (x1, 700), (x0, y))
    cote((-90, 0), (-90, 600), (-230, 0), angle_cote=90)

    for y in axes_y.values():
        rect(-15, y - 15, 1065, y + 15)
    rect(587.5, 15, 612.5, 585)
    for x in axes_x.values():
        for y in axes_y.values():
            msp.add_solid([T(p) for p in ((x - 15, y - 15), (x + 15, y - 15),
                                          (x - 15, y + 15), (x + 15, y + 15))],
                          dxfattribs={"layer": "COFFRAGE"})
    for (x0, x1) in ((15, 587.5), (612.5, 1035)):
        ligne((x0, 15), (x1, 585))
        ligne((x0, 585), (x1, 15))
    texte("P1 30x60", 300, 22, 15, A.BOTTOM_CENTER)
    texte("P2 30x50", 825, 22, 15, A.BOTTOM_CENTER)
    texte("P3 30x60", 300, 622, 15, A.BOTTOM_CENTER)
    texte("P4 30x50", 825, 622, 15, A.BOTTOM_CENTER)
    texte("P5 25x50", 580, 300, 15, A.BOTTOM_CENTER, rot=90)
    texte("C1 30x30", 22, -48, 12.5)
    for x, y in ((622, -48), (1072, -48), (22, 552), (622, 552), (1072, 552)):
        texte("C1", x, y, 12.5)
    for cx in (300, 825):
        texte("Dalle pleine ép. 20", cx, 330, 15, A.BOTTOM_CENTER)
        texte("Niv. +3,20", cx, 300, 12.5, A.TOP_CENTER)
    ligne((420, -60), (420, 60))
    texte("A", 420, -75, 17.5, A.TOP_CENTER)
    texte("A", 420, 75, 17.5, A.BOTTOM_CENTER)

    # LA COUPE A-A DE P1, AU 1/20 (x2,5): un rectangle hors grille, des cotes
    # a DIMLFAC 0,4 — ni poteau, ni poutre, ni portee.
    k, x0, y0 = 2.5, 60.0, -470.0
    rect(x0, y0, x0 + 30 * k, y0 + 60 * k)
    rect(x0 + 3 * k, y0 + 3 * k, x0 + 27 * k, y0 + 57 * k, "FERRAILLAGE")
    coupe = doc.dimstyles.duplicate_entry("COTES_CM", "COTES_1_20")
    coupe.dxf.dimlfac = 1 / k
    cote((x0, y0), (x0 + 30 * k, y0), (x0, y0 - 30), style="COTES_1_20")
    cote((x0, y0), (x0, y0 + 60 * k), (x0 - 35, y0), angle_cote=90, style="COTES_1_20")
    texte("3 Ø16", x0 + 130, y0 + 10, 12.5, A.MIDDLE_LEFT, calque="FERRAILLAGE")
    texte("2 Ø12", x0 + 130, y0 + 140, 12.5, A.MIDDLE_LEFT, calque="FERRAILLAGE")
    texte("Etr. Ø8 / 15", x0 + 130, y0 + 75, 12.5, A.MIDDLE_LEFT, calque="FERRAILLAGE")
    texte("COUPE A-A — POUTRE P1 (éch. 1/20)", x0, y0 + 60 * k + 25, 15)

    notes = ["NOTES GÉNÉRALES",
             "2. Béton : C30/37 — XC1 (intérieur), XC4 (façades).",
             "3. Armatures : BE 500 S.",
             "4. Enrobage nominal : 25 mm (intérieur), 40 mm (façades).",
             "5. Charge d'exploitation : 3,0 kN/m² (bureaux, catégorie B).",
             "6. Charges permanentes complémentaires : 1,5 kN/m².",
             "7. Ne pas mesurer sur le plan."]
    if declaration:
        notes.insert(1, "1. Toutes les cotes sont en cm et à vérifier sur chantier.")
    if note_portee:
        notes.append(f"8. {note_portee}")
    for i, t in enumerate(notes):
        texte(t, 1180, 680 - i * 32, 17.5 if i == 0 else 12.5)
    rect(1150, -540, 1730, -250, "CADRE")
    for t, y in (("FICTIF — EXEMPLE DE DÉMONSTRATION, NON RÉEL", -285),
                 ("Projet : FICTIF Immeuble de bureaux R+1", -340),
                 ("Plan de coffrage — plancher haut du rez-de-chaussée", -400),
                 ("Niv. +3,20 — Échelle 1/50", -460),
                 ("Bureau d'études FICTIF — Plan S-101 — Indice A", -520)):
        texte(t, 1165, y, 12.5, calque="CADRE")
    return _ecrire(doc)


# --------------------------------------------------------- charpente (mm)
def dxf_charpente_mm(*, cote_forcee: str = "6000") -> bytes:
    """Calques AIA en mm. Files A (x=0), B (6000), C (11800) ; 1 (y=0), 2 (5000),
    3 (10000). Poteaux en blocs, voile en B3, poutres en paires de traits."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for nom, trait in (("S-GRID", "CENTER"), ("S-COLS", "CONTINUOUS"), ("S-BEAM", "HIDDEN"),
                       ("S-WALL", "CONTINUOUS"), ("S-ANNO-TEXT", "CONTINUOUS"),
                       ("S-ANNO-DIMS", "CONTINUOUS")):
        doc.layers.add(nom, linetype=trait)

    bulle = doc.blocks.new("GRID_BUBBLE")
    bulle.add_circle((0, 0), 400)
    bulle.add_attdef("LABEL", (0, 0), dxfattribs={"height": 300}).set_placement(
        (0, 0), align=A.MIDDLE_CENTER)
    for nom, (a, b) in (("COL-400x400", (400, 400)), ("COL-300x500", (300, 500))):
        bloc = doc.blocks.new(nom)
        coins = [(-a / 2, -b / 2), (a / 2, -b / 2), (a / 2, b / 2), (-a / 2, b / 2)]
        bloc.add_lwpolyline(coins, close=True)
        hachure = bloc.add_hatch()
        hachure.paths.add_polyline_path(coins, is_closed=True)

    xs = {"A": 0.0, "B": 6000.0, "C": 11800.0}
    ys = {"1": 0.0, "2": 5000.0, "3": 10000.0}
    for nom, x in xs.items():
        msp.add_line((x, -1000), (x, 11000), dxfattribs={"layer": "S-GRID"})
        msp.add_blockref("GRID_BUBBLE", (x, 11400), dxfattribs={"layer": "S-GRID"}
                         ).add_auto_attribs({"LABEL": nom})
    for nom, y in ys.items():
        msp.add_line((-1000, y), (14000, y), dxfattribs={"layer": "S-GRID"})
        msp.add_blockref("GRID_BUBBLE", (-1400, y), dxfattribs={"layer": "S-GRID"}
                         ).add_auto_attribs({"LABEL": nom})

    for x in xs.values():
        for y in ys.values():
            if (x, y) == (6000.0, 10000.0):
                continue  # B3: un voile, pas un poteau
            if (x, y) == (11800.0, 10000.0):
                msp.add_blockref("COL-300x500", (x, y),
                                 dxfattribs={"layer": "S-COLS", "rotation": 90})
            else:
                msp.add_blockref("COL-400x400", (x, y), dxfattribs={"layer": "S-COLS"})
    msp.add_lwpolyline([(5900, 9000), (6100, 9000), (6100, 11000), (5900, 11000)],
                       close=True, dxfattribs={"layer": "S-WALL"})

    def paire(x0: float, x1: float, y: float, w: float, vertical: bool = False) -> None:
        for d in (-w / 2, w / 2):
            if vertical:
                msp.add_line((y + d, x0), (y + d, x1), dxfattribs={"layer": "S-BEAM"})
            else:
                msp.add_line((x0, y + d), (x1, y + d), dxfattribs={"layer": "S-BEAM"})

    # File 1: interrompue aux poteaux (fusion à travers l'appui).
    paire(200, 5800, 0, 300)
    paire(6200, 11600, 0, 300)
    # File 2: continue, et une console de 1500 au-delà du nu de C2.
    paire(200, 13500, 5000, 300)
    # File 3: de A3 au voile B3.
    paire(200, 5900, 10000, 300)
    # Poutre secondaire x = 3000, portée par les poutres des files 1 et 2.
    paire(150, 4850, 3000, 250, vertical=True)

    def texte(t: str, x: float, y: float, rot: float = 0.0) -> None:
        msp.add_text(t, height=250, rotation=rot,
                     dxfattribs={"layer": "S-ANNO-TEXT"}).set_placement((x, y))

    texte("B1 300x600", 1200, 300)
    texte("B2 300x600", 8000, 300)
    texte("B3", 1200, 5300)
    texte("SB1 250x500", 2700, 1500, rot=90)
    texte("B4", 1200, 10300)
    texte("C1", 300, -700)

    # UN STYLE DE COTE EN mm (DIMLFAC = 1): le style « EZDXF » par défaut
    # d'ezdxf affiche des centimètres pour un dessin en mètres (DIMLFAC = 100).
    style = doc.dimstyles.duplicate_entry("EZDXF", "COTES_MM")
    style.dxf.dimtxt, style.dxf.dimasz, style.dxf.dimlfac, style.dxf.dimdec = 250, 150, 1, 0
    for (x0, x1), texte_cote in (((0, 6000), "<>"), ((6000, 11800), cote_forcee)):
        d = msp.add_linear_dim(base=(x0, 12500), p1=(x0, 11000), p2=(x1, 11000),
                               dimstyle="COTES_MM", dxfattribs={"layer": "S-ANNO-DIMS"},
                               text=texte_cote)
        d.render()
    msp.add_linear_dim(base=(0, 13200), p1=(0, 11000), p2=(11800, 11000),
                       dimstyle="COTES_MM", dxfattribs={"layer": "S-ANNO-DIMS"}).render()
    for y0, y1 in ((0, 5000), (5000, 10000)):
        msp.add_linear_dim(base=(-2500, y0), p1=(-1000, y0), p2=(-1000, y1), angle=90,
                           dimstyle="COTES_MM", dxfattribs={"layer": "S-ANNO-DIMS"}).render()
    return _ecrire(doc)


# --------------------------------------------------------- sans calques (m)
def dxf_sans_calques_m() -> bytes:
    """Tout sur le calque 0, en mètres : axes par type de ligne CENTER, poteaux
    hachurés 0,30 aux nœuds, poutres en paires de traits continus 0,25."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    xs, ys = (0.0, 6.0, 12.0), (0.0, 5.0)
    for x in xs:
        msp.add_line((x, -1.0), (x, 6.0), dxfattribs={"linetype": "CENTER"})
    for y in ys:
        msp.add_line((-1.0, y), (13.0, y), dxfattribs={"linetype": "CENTER"})
    for x in xs:
        for y in ys:
            hachure = msp.add_hatch()
            hachure.paths.add_polyline_path(
                [(x - 0.15, y - 0.15), (x + 0.15, y - 0.15), (x + 0.15, y + 0.15),
                 (x - 0.15, y + 0.15)], is_closed=True)
    for y in ys:
        for x0, x1 in ((0.15, 5.85), (6.15, 11.85)):
            for d in (-0.125, 0.125):
                msp.add_line((x0, y + d), (x1, y + d))
    return _ecrire(doc)


# --------------------------------------------------------------- refus
def dxf_refus() -> bytes:
    """Une référence externe, une poutre courbe, une poutre sans appui."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    doc.layers.add("POUTRES")
    doc.add_xref_def("FICTIF-archi.dxf", "XREF_ARCHI")
    msp.add_blockref("XREF_ARCHI", (0, 0))
    msp.add_arc((500, 500), 300, 0, 90, dxfattribs={"layer": "POUTRES"})
    msp.add_arc((500, 500), 330, 0, 90, dxfattribs={"layer": "POUTRES"})
    msp.add_lwpolyline([(2000, 0), (2600, 0), (2600, 30), (2000, 30)], close=True,
                       dxfattribs={"layer": "POUTRES"})
    return _ecrire(doc)


# ------------------------------------------------------------ grille polaire
def dxf_grille_polaire() -> bytes:
    """Six axes rayonnants (tous les 30°) autour de l'origine, étiquetés 1 à 6
    à leur extrémité : une grille polaire, hors du domaine reconnu."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    doc.layers.add("AXES", linetype="CENTER")
    for i in range(6):
        a = math.radians(30.0 * i)
        bout = (12000 * math.cos(a), 12000 * math.sin(a))
        msp.add_line((0, 0), bout, dxfattribs={"layer": "AXES"})
        msp.add_text(str(i + 1), height=300, dxfattribs={"layer": "AXES"}).set_placement(
            (12600 * math.cos(a), 12600 * math.sin(a)))
    return _ecrire(doc)


# ------------------------------------------------------- cercle sans unité
def dxf_cercle_sans_unite() -> bytes:
    """Un cercle de rayon 1,5 à l'origine, ``$INSUNITS = 0``, rien d'autre."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 0
    doc.modelspace().add_circle((0, 0), 1.5)
    return _ecrire(doc)


# ------------------------------------------------------------ grande grille
def dxf_grande_grille(n: int = 20, *, entraxe: float = 6000.0) -> bytes:
    """n × n axes en mm, un poteau bloc à chaque nœud, des poutres rectangles
    entre les nus dans les deux directions."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for nom in ("AXES", "POTEAUX", "POUTRES"):
        doc.layers.add(nom)
    bloc = doc.blocks.new("POT40")
    bloc.add_lwpolyline([(-200, -200), (200, -200), (200, 200), (-200, 200)], close=True)
    etendue = (n - 1) * entraxe
    lettres: Callable[[int], str] = lambda i: (chr(65 + i) if i < 26  # noqa: E731
                                               else chr(65 + i // 26 - 1) + chr(65 + i % 26))
    for i in range(n):
        c = i * entraxe
        msp.add_line((c, -1000), (c, etendue + 1000), dxfattribs={"layer": "AXES"})
        msp.add_text(lettres(i), height=300, dxfattribs={"layer": "AXES"}).set_placement(
            (c, etendue + 1500))
        msp.add_line((-1000, c), (etendue + 1000, c), dxfattribs={"layer": "AXES"})
        msp.add_text(str(i + 1), height=300, dxfattribs={"layer": "AXES"}).set_placement(
            (-1800, c))
    for i in range(n):
        for j in range(n):
            msp.add_blockref("POT40", (i * entraxe, j * entraxe), dxfattribs={"layer": "POTEAUX"})
    for i in range(n):
        for j in range(n - 1):
            a, b = j * entraxe + 200, (j + 1) * entraxe - 200
            c = i * entraxe
            msp.add_lwpolyline([(a, c - 150), (b, c - 150), (b, c + 150), (a, c + 150)],
                               close=True, dxfattribs={"layer": "POUTRES"})
            msp.add_lwpolyline([(c - 150, a), (c + 150, a), (c + 150, b), (c - 150, b)],
                               close=True, dxfattribs={"layer": "POUTRES"})
    return _ecrire(doc)


# ------------------------------------------------------- FONDATIONS (cm)
def dxf_fondations_pieux(*, echelles: tuple[str, ...] = ("1/100",), rapport: float = 10.0,
                         insunits: int = 0, mention: str | None = None,
                         presentation: bool = True) -> bytes:
    """Un plan de fondations en cm, SANS ``$INSUNITS`` : la présentation « H »
    écrit ``echelles`` et sa fenêtre montre ``rapport`` unités par mm de papier.

    Files A–D (0, 600, 1200, 1800) et 1–3 (0, 500, 1000), bulles en haut et à
    gauche. Aux nœuds : A1, B1, C1, A2 poteaux préfabriqués 50 × 50 hachurés,
    chacun sur un socle caché 170 × 170 ; B2 une cage d'ascenseur 190 × 180
    (cabine, chevron plein) ; C2 une trémie 80 × 80 barrée ; D1 une gaine
    60 × 60 nommée « GAINE » ; D2 une semelle 120 × 120 (calque ``SEMELLES``) ;
    A3, B3 des pieux Ø 60 (calque ; le premier en double dans une xréf, rempli,
    repéré « P12 » ; le second repéré « PIEU 13 ») ; C3 un pieu par bloc
    ``PIEU_D60``. Sous la grille, une paroi de huit pieux sécants Ø 63 tous les
    50 cm : calque, copie cachée de xréf, remplissages, lentilles.

    ``mention`` écrit une note (« Cotes en mm ») et deux cotes d'axe à axe :
    la règle « mention et cotes » s'applique alors aussi."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    # « DASHED » : le trait caché du gabarit d'ezdxf (le plan réel dit « HIDDEN »).
    for nom, trait in (("AXES", "DASHDOT"), ("BETON_PREFAB_COUPE", "CONTINUOUS"),
                       ("HACH_BETON_PREFAB", "CONTINUOUS"), ("BETON_CACHE", "DASHED"),
                       ("PIEUX_COUPE", "CONTINUOUS"), ("XREF$0$PIEUX_COUPE", "DASHED"),
                       ("HACH_BETON_CACHE", "CONTINUOUS"), ("HACH_PIEUX_COUPE", "CONTINUOUS"),
                       ("PIEUX_TEXTE", "CONTINUOUS"), ("TEXTES", "CONTINUOUS"),
                       ("SEMELLES", "CONTINUOUS"), ("OMBRE", "CONTINUOUS"),
                       ("EQUIPEMENT", "CONTINUOUS"), ("BETON_COUPE", "CONTINUOUS"),
                       ("COTES", "CONTINUOUS"), ("DIVERS", "CONTINUOUS")):
        doc.layers.add(nom, linetype=trait)

    def rect(cx: float, cy: float, lx: float, ly: float, calque: str) -> list[Point]:
        pts = [(cx - lx / 2, cy - ly / 2), (cx + lx / 2, cy - ly / 2),
               (cx + lx / 2, cy + ly / 2), (cx - lx / 2, cy + ly / 2)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": calque})
        return pts

    def plein(points: list[Point], calque: str) -> None:
        hachure = msp.add_hatch(color=8, dxfattribs={"layer": calque})
        hachure.paths.add_polyline_path(points, is_closed=True)

    def disque(cx: float, cy: float, r: float, calque: str) -> None:
        hachure = msp.add_hatch(color=8, dxfattribs={"layer": calque})
        hachure.paths.add_edge_path().add_arc((cx, cy), r, 0, 360)

    def texte(t: str, x: float, y: float, h: float, calque: str = "TEXTES") -> None:
        msp.add_text(t, height=h, dxfattribs={"layer": calque}).set_placement(
            (x, y), align=A.MIDDLE_CENTER)

    axes_x = {"A": 0.0, "B": 600.0, "C": 1200.0, "D": 1800.0}
    axes_y = {"1": 0.0, "2": 500.0, "3": 1000.0}
    for nom, x in axes_x.items():
        msp.add_line((x, -100), (x, 1100), dxfattribs={"layer": "AXES"})
        msp.add_circle((x, 1140), 40, dxfattribs={"layer": "AXES"})
        texte(nom, x, 1140, 30, "AXES")
    for nom, y in axes_y.items():
        msp.add_line((-100, y), (1900, y), dxfattribs={"layer": "AXES"})
        msp.add_circle((-140, y), 40, dxfattribs={"layer": "AXES"})
        texte(nom, -140, y, 30, "AXES")

    # Poteaux préfabriqués hachurés, chacun sur un socle caché concentrique.
    for x, y in ((0, 0), (600, 0), (1200, 0), (0, 500)):
        plein(rect(x, y, 50, 50, "BETON_PREFAB_COUPE"), "HACH_BETON_PREFAB")
        rect(x, y, 170, 170, "BETON_CACHE")
    texte("C1", 45, -45, 12)

    # B2 : la cage d'ascenseur, la cabine, le chevron plein du symbole.
    rect(600, 500, 190, 180, "BETON_COUPE")
    rect(600, 490, 120, 100, "EQUIPEMENT")
    chevron = [(520, 575), (670, 575), (540, 555), (520, 430)]
    msp.add_lwpolyline(chevron, close=True, dxfattribs={"layer": "OMBRE"})
    plein(chevron, "OMBRE")
    # C2 : une trémie barrée de ses deux diagonales.
    coins = rect(1200, 500, 80, 80, "BETON_COUPE")
    msp.add_line(coins[0], coins[2], dxfattribs={"layer": "BETON_COUPE"})
    msp.add_line(coins[1], coins[3], dxfattribs={"layer": "BETON_COUPE"})
    # D1 : une gaine nommée ; D2 : une semelle.
    rect(1800, 0, 60, 60, "BETON_COUPE")
    texte("GAINE", 1800, 0, 10)
    rect(1800, 500, 120, 120, "SEMELLES")

    # A3, B3 : des pieux sur un calque de pieux ; C3 : un pieu par bloc.
    for x in (0, 600):
        msp.add_circle((x, 1000), 30, dxfattribs={"layer": "PIEUX_COUPE"})
    msp.add_circle((0, 1000), 30, dxfattribs={"layer": "XREF$0$PIEUX_COUPE"})
    disque(0, 1000, 30, "HACH_BETON_CACHE")
    texte("P12", 45, 1040, 12, "PIEUX_TEXTE")
    texte("PIEU 13", 660, 1040, 12)
    bloc = doc.blocks.new("PIEU_D60")
    bloc.add_circle((0, 0), 30, dxfattribs={"layer": "0"})
    msp.add_blockref("PIEU_D60", (1200, 1000), dxfattribs={"layer": "DIVERS"})

    # La paroi de pieux sécants, sous la grille.
    centres = [(100.0 + 50.0 * i, -250.0) for i in range(8)]
    for cx, cy in centres:
        msp.add_circle((cx, cy), 31.5, dxfattribs={"layer": "PIEUX_COUPE"})
        msp.add_circle((cx, cy), 31.5, dxfattribs={"layer": "XREF$0$PIEUX_COUPE"})
        disque(cx, cy, 31.5, "HACH_BETON_CACHE")
    demi = math.degrees(math.acos(25.0 / 31.5))
    for (ax, ay), (bx, by) in zip(centres, centres[1:], strict=False):
        lentille = msp.add_hatch(color=8, dxfattribs={"layer": "HACH_PIEUX_COUPE"})
        chemin = lentille.paths.add_edge_path()
        chemin.add_arc((ax, ay), 31.5, -demi, demi)
        chemin.add_arc((bx, by), 31.5, 180.0 - demi, 180.0 + demi)

    if mention is not None:
        texte(mention, 900, -450, 15)
        style = doc.dimstyles.duplicate_entry("EZDXF", "COTES_1")
        style.dxf.dimlfac, style.dxf.dimdec = 1, 0
        for x0, x1 in ((0, 600), (600, 1200)):
            msp.add_linear_dim(base=(x0, 1250), p1=(x0, 1100), p2=(x1, 1100),
                               dimstyle="COTES_1", dxfattribs={"layer": "COTES"}).render()

    if presentation:
        papier = doc.paperspace()
        papier.page_setup(size=(1189, 841), margins=(0, 0, 0, 0), units="mm")
        papier.add_viewport(center=(600, 420), size=(1000, 700), view_center_point=(900, 450),
                            view_height=700 * rapport)
        for rang, echelle in enumerate(echelles):
            papier.add_text(echelle, height=2.5, dxfattribs={"layer": "CARTOUCHE"}).set_placement(
                (1100, 40 + 10 * rang))
        papier.add_text("PLAN DE FONDATIONS FICTIF", height=5,
                        dxfattribs={"layer": "CARTOUCHE"}).set_placement((900, 20))
    return _ecrire(doc)


# ------------------------------------------------------- ÉTIQUETTES (mm)
def dxf_etiquettes_d_axes() -> bytes:
    """Une grille en mm, bulles en haut (A–C) et à gauche (1–4), et ce qui a
    trompé l'étiquetage sur des feuilles réelles :

    * au bout de l'axe 2, une lettre « B » de 1 200 mm (un noyau d'ascenseur),
      quatre fois la hauteur des étiquettes de bulle ;
    * au bout de l'axe 3, une lettre « K » de la hauteur des étiquettes, sans
      bulle ;
    * au bout de l'axe 4, une seconde BULLE, « 8 » : deux preuves de même force ;
    * au bout de l'axe C, un pieu numéroté « 12 » (cercle d'un calque de pieux)."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for nom in ("AXES", "TEXTES", "PIEUX"):
        doc.layers.add(nom)

    def texte(t: str, x: float, y: float, h: float, calque: str) -> None:
        msp.add_text(t, height=h, dxfattribs={"layer": calque}).set_placement(
            (x, y), align=A.MIDDLE_CENTER)

    for nom, x in (("A", 0.0), ("B", 6000.0), ("C", 12000.0)):
        msp.add_line((x, -1000), (x, 11000), dxfattribs={"layer": "AXES"})
        msp.add_circle((x, 11400), 400, dxfattribs={"layer": "AXES"})
        texte(nom, x, 11400, 300, "AXES")
    for nom, y in (("1", 0.0), ("2", 3500.0), ("3", 7000.0), ("4", 10000.0)):
        msp.add_line((-1000, y), (13000, y), dxfattribs={"layer": "AXES"})
        msp.add_circle((-1400, y), 400, dxfattribs={"layer": "AXES"})
        texte(nom, -1400, y, 300, "AXES")
    texte("B", 14500, 3500, 1200, "TEXTES")
    texte("K", 13500, 7000, 300, "TEXTES")
    msp.add_circle((13400, 10000), 400, dxfattribs={"layer": "AXES"})
    texte("8", 13400, 10000, 300, "AXES")
    msp.add_circle((12000, -1400), 400, dxfattribs={"layer": "PIEUX"})
    texte("12", 12000, -1400, 300, "PIEUX")
    return _ecrire(doc)
