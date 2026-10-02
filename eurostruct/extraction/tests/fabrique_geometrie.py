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
  d'un axe ;
* ``dxf_bulles_lettres_chiffres`` : une seconde grille étiquetée « L1 »…
  (lettres et chiffres), dessinée dans un bloc de référence externe liée dont
  le calque des bulles se nomme ``…C_AXES_TITRE`` — une bulle seule, une ligne
  partagée avec une bulle courante, deux bulles qui se contredisent, un texte
  « L6 » sans bulle, un cercle et un texte « L7 » de cartouche ;
* ``dxf_axes_courts_a_bulle`` : une légende éloignée qui agrandit l'emprise, et
  des traits d'axe plus courts que le seuil — un axe court à bulle, deux qui
  se soutiennent, et ceux qui ne sont pas des axes (sans bulle, trait de
  rappel, direction isolée, bulle d'un autre axe, deux bulles qui se
  contredisent, pieu, type de ligne) ;
* ``dxf_cotes_de_tous_types`` : chaque type de cote, valeur connue par
  construction, les cotes alignées écrites comme AutoCAD les écrit (type 1,
  sans code 50) — linéaires, alignées, rayon, diamètre, angles, ordonnées,
  longueur d'arc, ``DIMLFAC``, textes forcés, un détail en mm inséré au 1/10 ;
* ``dxf_information_n1`` : l'information DXF standard que lit la phase G1
  (``docs/GEOMETRIE_D_ABORD_G1.md``) — types de ligne de la bibliothèque, ISO,
  RENOMMÉS et complexes ; hachures pleines, à motif, ``SOLID``, ``MPOLYGON``
  remplie et vide ; multilignes (justifications, fermée, dans un bloc tourné
  et mis à l'échelle, à échelle non uniforme, sur calque gelé) ; bulles-blocs
  à attribut, ``MINSERT``, blocs imbriqués mis à l'échelle, bloc anonyme,
  références externes (liée et superposée), calque dépendant d'une xréf ;
  couleurs ACI, vraies, ``BYLAYER``, ``BYBLOCK``, calque absent de la table —
  autour d'une petite grille à bulles et de poteaux pleins aux nœuds.

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


# --------------------------------------------- BULLES EN LETTRES ET CHIFFRES
def dxf_bulles_lettres_chiffres() -> bytes:
    """Deux grilles sur un plan en mm : la première, courante (« 1 »… « 3 »
    verticaux, « B » horizontal) ; la seconde, étiquetée « L1 »… comme sur le
    plan réel qui a montré le défaut, dessinée dans le bloc d'une référence
    externe liée (``AXES_GRILLE2``) dont les bulles sont sur un calque nommé
    ``AXES_GRILLE2$0$C_AXES_TITRE`` — lu « cadre » par son nom, « axe » par son
    bloc. Horizontaux, de bas en haut :

    * y = 0 : une bulle « L1 » à gauche, seule ;
    * y = 3 500 : une ligne partagée — bulle courante « B » à gauche, bulle
      « L9 » à droite ;
    * y = 7 000 : « L4 » à gauche, « L5 » à droite : deux bulles qui se
      contredisent ;
    * y = 10 000 : un texte « L6 » au bout, sans bulle ;
    * y = 13 000 : un cercle et un texte « L7 » au bout, sur le calque
      ``CARTOUCHE``, hors de tout bloc d'axes."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    bulles2, lignes2 = "AXES_GRILLE2$0$C_AXES_TITRE", "AXES_GRILLE2$0$C_AXES"
    for nom in ("AXES", "TEXTES", "CARTOUCHE", bulles2, lignes2):
        doc.layers.add(nom)
    grille2 = doc.blocks.new("AXES_GRILLE2")

    def texte(cible, t: str, x: float, y: float, calque: str) -> None:  # noqa: ANN001
        cible.add_text(t, height=300, dxfattribs={"layer": calque}).set_placement(
            (x, y), align=A.MIDDLE_CENTER)

    def bulle(cible, t: str, x: float, y: float, calque: str) -> None:  # noqa: ANN001
        cible.add_circle((x, y), 400, dxfattribs={"layer": calque})
        texte(cible, t, x, y, calque)

    for nom, x in (("1", 0.0), ("2", 6000.0), ("3", 12000.0)):
        msp.add_line((x, -1000), (x, 14000), dxfattribs={"layer": "AXES"})
        bulle(msp, nom, x, 14400, "AXES")
    # La ligne partagée : dessinée par la première grille, bulle « B » à gauche.
    msp.add_line((-1000, 3500), (13000, 3500), dxfattribs={"layer": "AXES"})
    bulle(msp, "B", -1400, 3500, "AXES")
    # La seconde grille, dans son bloc.
    for y in (0.0, 7000.0, 10000.0, 13000.0):
        grille2.add_line((-1000, y), (13000, y), dxfattribs={"layer": lignes2})
    bulle(grille2, "L1", -1400, 0, bulles2)
    bulle(grille2, "L9", 13400, 3500, bulles2)
    bulle(grille2, "L4", -1400, 7000, bulles2)
    bulle(grille2, "L5", 13400, 7000, bulles2)
    texte(grille2, "L6", -1400, 10000, bulles2)
    msp.add_blockref("AXES_GRILLE2", (0, 0))
    # Le cartouche : son cercle et son texte, hors du bloc d'axes.
    bulle(msp, "L7", -1400, 13000, "CARTOUCHE")
    return _ecrire(doc)


# ------------------------------------------------- AXES COURTS À BULLE
def dxf_axes_courts_a_bulle(*, appui_a_45: bool = False) -> bytes:
    """Une grille en mm (« 1 »… « 3 » verticaux, « A »… « C » horizontaux, bulles
    de 400), et une LÉGENDE FICTIVE éloignée qui agrandit l'emprise : le seuil
    d'un axe nommé par son calque (0,1 × diagonale) passe à 9 140 mm, au-dessus
    des traits ci-dessous — la forme du plan réel qui a montré le défaut
    (``docs/GEOMETRIE_SEUIL_DES_AXES.md``). Des traits du calque ``AXES`` :

    * x = 3 000 : bulle « 1' » au bout, 12,5 rayons — un axe court ;
    * à 80°, deux traits parallèles, bulles « R1 » et « R2 » : ils se soutiennent ;
    * x = 9 000 : aucune bulle — un morceau, pas un axe ;
    * x = 4 500 : bulle « 4 » au bout d'un trait de 3 rayons — un rappel ;
    * à 45° : bulle « Q » au bout, une direction qu'aucun axe ne partage
      (``appui_a_45`` : un axe à 45°, admis par le seuil, la partage) ;
    * y = 10 050 : pointé vers la bulle « C », plus loin que l'axe « C » ;
    * x = 12 050 : entre la bulle « 3 », qu'il touche avant l'axe « 3 » (qui
      s'arrête à deux rayons de sa bulle), et une bulle « 7 » : deux bulles qui
      se contredisent ;
    * x = 10 500 : un pieu numéroté « 12 » au bout (calque ``PIEUX``) ;
    * x = 7 500, calque ``0``, type de ligne d'axe : bulle « 8 » au bout."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for nom in ("AXES", "PIEUX", "LEGENDE"):
        doc.layers.add(nom)

    def bulle(t: str, x: float, y: float, calque: str = "AXES") -> None:
        msp.add_circle((x, y), 400, dxfattribs={"layer": calque})
        msp.add_text(t, height=300, dxfattribs={"layer": calque}).set_placement(
            (x, y), align=A.MIDDLE_CENTER)

    def trait(a: Point, b: Point, calque: str = "AXES", **attributs: str) -> None:
        msp.add_line(a, b, dxfattribs={"layer": calque, **attributs})

    # LA GRILLE, admise par le seuil (12 000 et 14 000 mm).
    for nom, x, haut in (("1", 0.0, 11000.0), ("2", 6000.0, 11000.0), ("3", 12000.0, 10600.0)):
        trait((x, -1000), (x, haut))
        bulle(nom, x, 11400)
    for nom, y in (("A", 0.0), ("B", 5000.0), ("C", 10000.0)):
        trait((-1000, y), (13000, y))
        bulle(nom, -1400, y)
    msp.add_lwpolyline([(60000, 50000), (66000, 50000), (66000, 54000), (60000, 54000)],
                       close=True, dxfattribs={"layer": "LEGENDE"})
    msp.add_text("LEGENDE FICTIVE", height=300, dxfattribs={"layer": "LEGENDE"}).set_placement(
        (63000, 52000), align=A.MIDDLE_CENTER)

    trait((3000, 1000), (3000, 6000))
    bulle("1'", 3000, 6400)
    c80, s80 = math.cos(math.radians(80)), math.sin(math.radians(80))
    for nom, x in (("R1", 15000.0), ("R2", 16500.0)):
        fin = (x + 5000 * c80, 5000 * s80)
        trait((x, 0), fin)
        bulle(nom, fin[0] + 400 * c80, fin[1] + 400 * s80)
    trait((9000, 1000), (9000, 6000))
    trait((4500, 6800), (4500, 8000))
    bulle("4", 4500, 8400)
    trait((7000, 6000), (10500, 9500))
    bulle("Q", 10500 + 400 / math.sqrt(2), 9500 + 400 / math.sqrt(2))
    if appui_a_45:
        trait((20000, 20000), (30000, 30000))
    trait((-7000, 10050), (-1800, 10050))
    trait((12050, 11800), (12050, 16800))
    bulle("7", 12050, 17200)
    trait((10500, 1000), (10500, 6000))
    bulle("12", 10500, 6400, "PIEUX")
    trait((7500, 1000), (7500, 6000), "0", linetype="CENTER")
    bulle("8", 7500, 6400, "0")
    return _ecrire(doc)


# ------------------------------------------------- COTES DE TOUS TYPES
def _cote_alignee_comme_autocad(dimension) -> None:  # noqa: ANN001 — une entité ezdxf
    """UNE COTE ALIGNÉE TELLE QU'AUTOCAD L'ÉCRIT : type 1 (drapeaux gardés), sans
    code 50 — l'angle n'appartient qu'aux cotes tournées. ezdxf écrit une cote
    « alignée » comme une cote tournée (type 0, code 50 = sa direction), ce qui
    masque le défaut de sa mesure (``docs/GEOMETRIE_COTES_DXF.md``)."""
    dimension.dxf.dimtype = (dimension.dxf.dimtype & ~15) | 1
    dimension.dxf.discard("angle")


def dxf_cotes_de_tous_types(*, mesure_autocad_contredite: bool = False) -> bytes:
    """Chaque type de cote d'un plan en cm, valeur connue par construction :

    * linéaires : horizontale 3 000, verticale 2 500, tournée de 30° (1 366,025) ;
    * alignées, écrites comme AutoCAD : 3-4-5 (500, avec le code 42 d'AutoCAD),
      verticale (700), à 45° (1 414,214), horizontale (1 000) ;
    * rayon 40, diamètre 63 ;
    * angles de 90° (deux lignes) et de 60° (trois points), ordonnées X (1 200)
      et Y (300), une longueur d'arc ;
    * une alignée à ``DIMLFAC`` 0,1 (5 000 tracés, 500 affichés) ;
    * une alignée de 450 au texte forcé « 450 » (concordant), une linéaire de
      600 au texte forcé « 580 » (discordant) ;
    * un détail en mm (``DIMLFAC`` 0,1 : il affiche des cm) inséré au 1/10 : une
      linéaire et une alignée de 6 000 mm, qui affichent 600.

    ``mesure_autocad_contredite`` : la linéaire de 3 000 porte un code 42 de
    2 900, que ses points de définition contredisent."""
    import ezdxf

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    doc.layers.add("COTES")
    style = doc.dimstyles.duplicate_entry("EZDXF", "COTES_CM")
    style.dxf.dimlfac = 1.0
    detail = doc.dimstyles.duplicate_entry("EZDXF", "DETAIL_MM")
    detail.dxf.dimlfac = 0.1
    attributs = {"layer": "COTES"}

    def poser(cote, *, alignee: bool = False, autocad: float | None = None) -> None:  # noqa: ANN001
        cote.render()
        if alignee:
            _cote_alignee_comme_autocad(cote.dimension)
        if autocad is not None:
            cote.dimension.dxf.actual_measurement = autocad

    poser(msp.add_linear_dim(base=(0, -500), p1=(0, 0), p2=(3000, 0), angle=0,
                             dimstyle="COTES_CM", dxfattribs=attributs),
          autocad=2900.0 if mesure_autocad_contredite else None)
    poser(msp.add_linear_dim(base=(-500, 0), p1=(0, 0), p2=(0, 2500), angle=90,
                             dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_linear_dim(base=(5000, 800), p1=(5000, 0), p2=(6000, 1000), angle=30,
                             dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_aligned_dim(p1=(10000, 0), p2=(10300, 400), distance=200,
                              dimstyle="COTES_CM", dxfattribs=attributs),
          alignee=True, autocad=500.0)
    poser(msp.add_aligned_dim(p1=(12000, 0), p2=(12000, 700), distance=200,
                              dimstyle="COTES_CM", dxfattribs=attributs), alignee=True)
    poser(msp.add_aligned_dim(p1=(14000, 0), p2=(15000, 1000), distance=200,
                              dimstyle="COTES_CM", dxfattribs=attributs), alignee=True)
    poser(msp.add_aligned_dim(p1=(16000, 0), p2=(17000, 0), distance=200,
                              dimstyle="COTES_CM", dxfattribs=attributs), alignee=True)
    poser(msp.add_radius_dim(center=(20000, 0), radius=40, angle=45, dimstyle="COTES_CM",
                             dxfattribs=attributs))
    poser(msp.add_diameter_dim(center=(21000, 0), radius=31.5, angle=30, dimstyle="COTES_CM",
                               dxfattribs=attributs))
    poser(msp.add_angular_dim_2l(base=(23500, 500), line1=((23000, 0), (24000, 0)),
                                 line2=((23000, 0), (23000, 1000)), dimstyle="COTES_CM",
                                 dxfattribs=attributs))
    sommet = (26000 + 1000 * math.cos(math.radians(60)), 1000 * math.sin(math.radians(60)))
    poser(msp.add_angular_dim_3p(base=(26300, 300), center=(26000, 0), p1=(27000, 0), p2=sommet,
                                 dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_ordinate_x_dim(feature_location=(1200, 300), offset=(0, 600), origin=(0, 0),
                                 dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_ordinate_y_dim(feature_location=(1200, 300), offset=(600, 0), origin=(0, 0),
                                 dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_arc_dim_cra(center=(30000, 0), radius=100, start_angle=0, end_angle=90,
                              distance=50, dimstyle="COTES_CM", dxfattribs=attributs))
    poser(msp.add_aligned_dim(p1=(0, 5000), p2=(3000, 9000), distance=200, dimstyle="COTES_CM",
                              override={"dimlfac": 0.1}, dxfattribs=attributs), alignee=True)
    poser(msp.add_aligned_dim(p1=(5000, 5000), p2=(5270, 5360), distance=200, text="450",
                              dimstyle="COTES_CM", dxfattribs=attributs), alignee=True)
    poser(msp.add_linear_dim(base=(8000, 4500), p1=(8000, 5000), p2=(8600, 5000), angle=0,
                             text="580", dimstyle="COTES_CM", dxfattribs=attributs))
    bloc = doc.blocks.new("DETAIL_MM")
    poser(bloc.add_linear_dim(base=(0, -300), p1=(0, 0), p2=(6000, 0), angle=0,
                              dimstyle="DETAIL_MM", dxfattribs=attributs))
    poser(bloc.add_aligned_dim(p1=(0, 1000), p2=(3600, 5800), distance=300, dimstyle="DETAIL_MM",
                               dxfattribs=attributs), alignee=True)
    msp.add_blockref("DETAIL_MM", (40000, 0), dxfattribs={
        "xscale": 0.1, "yscale": 0.1, "zscale": 0.1, "layer": "COTES"})
    return _ecrire(doc)


# ------------------------------------------------------------- information N1
#: Les motifs ISO d'``acadiso.lin`` (longueur totale, éléments), et le motif de
#: ``CENTER`` sous un nom qui ne dit rien.
MOTIFS_N1: dict[str, list[float]] = {
    "ACAD_ISO02W100": [15.0, 12.0, -3.0],
    "ACAD_ISO03W100": [30.0, 12.0, -18.0],
    "ACAD_ISO04W100": [30.5, 24.0, -3.0, 0.5, -3.0],
    "ACAD_ISO07W100": [3.5, 0.5, -3.0],
    "ACAD_ISO08W100": [36.0, 24.0, -3.0, 6.0, -3.0],
    "LT07": [5.08, 3.175, -0.635, 0.635, -0.635],
}


def dxf_information_n1() -> bytes:
    """Un plan en mm, riche en information N1 (voir la liste du module).

    Repères pour les tests : grille A–C × 1–3 au pas de 6000 sur le calque
    ``AXES`` en type ``LT07`` (le motif de ``CENTER``) ; poteaux 400 × 400
    hachurés pleins aux nœuds (calque ``C001``) ; multilignes en y = 20000 à
    24000 ; blocs et références externes en x ≥ 30000."""
    import ezdxf
    from ezdxf import const
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    for nom, motif in MOTIFS_N1.items():
        doc.linetypes.add(nom, pattern=motif)
    doc.linetypes.add("GAZ_FICTIF",
                      pattern='A,.5,-.2,["GAS",STANDARD,S=.1,U=0.0,X=-0.1,Y=-.05],-.25',
                      description="FICTIF ----GAS----", length=1)
    doc.layers.add("AXES", color=1, linetype="LT07")
    doc.layers.add("C001", color=3)
    doc.layers.add("C002", color=4).rgb = (10, 20, 30)
    doc.layers.add("C003", color=5, linetype="ACAD_ISO02W100")
    eteint = doc.layers.add("C004", color=6)
    eteint.off()
    gele = doc.layers.add("C005")
    gele.freeze()
    dependant = doc.layers.add("FOND_FICTIF|C006")
    dependant.dxf.flags |= 16
    msp = doc.modelspace()

    # LA GRILLE ET LES POTEAUX : la détection a de quoi travailler.
    xs, ys = (0.0, 6000.0, 12000.0), (0.0, 6000.0, 12000.0)
    for i, x in enumerate(xs):
        msp.add_line((x, -1500), (x, 13500), dxfattribs={"layer": "AXES"})
        msp.add_circle((x, 13900), 400, dxfattribs={"layer": "AXES"})
        msp.add_text("ABC"[i], height=350, dxfattribs={"layer": "AXES"}).set_placement(
            (x, 13900), align=A.MIDDLE_CENTER)
    for j, y in enumerate(ys):
        msp.add_line((-1500, y), (13500, y), dxfattribs={"layer": "AXES"})
        msp.add_circle((-1900, y), 400, dxfattribs={"layer": "AXES"})
        msp.add_text(str(j + 1), height=350, dxfattribs={"layer": "AXES"}).set_placement(
            (-1900, y), align=A.MIDDLE_CENTER)
    for x in xs:
        for y in ys:
            coins = [(x - 200, y - 200), (x + 200, y - 200), (x + 200, y + 200),
                     (x - 200, y + 200)]
            msp.add_lwpolyline(coins, close=True, dxfattribs={"layer": "C001"})
            msp.add_hatch(dxfattribs={"layer": "C001"}).paths.add_polyline_path(
                coins, is_closed=True)

    # LES TYPES DE LIGNE : par le calque, par l'entité, complexe, BYBLOCK.
    msp.add_line((0, -4000), (12000, -4000), dxfattribs={"layer": "C003"})
    msp.add_line((0, -4500), (12000, -4500), dxfattribs={"layer": "C001",
                                                          "linetype": "GAZ_FICTIF"})
    msp.add_line((0, -5000), (12000, -5000), dxfattribs={"layer": "C001",
                                                          "linetype": "ACAD_ISO07W100"})
    trait = doc.blocks.new("B_TRAIT")
    trait.add_line((0, 0), (1000, 0), dxfattribs={"linetype": "BYBLOCK"})
    msp.add_blockref("B_TRAIT", (0, -5500), dxfattribs={"layer": "C001",
                                                         "linetype": "DASHDOT"})

    # LES REMPLISSAGES (hors de la grille, à y = -8000).
    ansi = msp.add_hatch(dxfattribs={"layer": "C002"})
    ansi.set_pattern_fill("ANSI31", scale=10)
    ansi.paths.add_polyline_path([(0, -8000), (300, -8000), (300, -7700)], is_closed=True)
    msp.add_solid([(1000, -8000), (1300, -8000), (1000, -7700), (1300, -7700)],
                  dxfattribs={"layer": "C002"})
    pleine = msp.add_mpolygon(fill_color=2, dxfattribs={"layer": "C002"})
    pleine.paths.add_polyline_path([(2000, -8000), (2300, -8000), (2300, -7700)],
                                   is_closed=True)
    vide = msp.add_mpolygon(dxfattribs={"layer": "C002"})
    vide.paths.add_polyline_path([(3000, -8000), (3300, -8000), (3300, -7700)],
                                 is_closed=True)

    # LES MULTILIGNES (style « Standard » : décalages +0,5 et -0,5).
    for k, justification in enumerate((const.MLINE_TOP, const.MLINE_ZERO, const.MLINE_BOTTOM)):
        ml = msp.add_mline([(0, 20000 + 1000 * k), (5000, 20000 + 1000 * k)],
                           dxfattribs={"layer": "C001", "scale_factor": 200})
        ml.set_justification(justification)
    msp.add_mline([(7000, 20000), (11000, 20000), (11000, 24000), (7000, 24000)], close=True,
                  dxfattribs={"layer": "C001", "scale_factor": 250})
    msp.add_mline([(0, 26000), (5000, 26000)], dxfattribs={"layer": "C005"})
    mur = doc.blocks.new("B_MUR")
    mur.add_mline([(0, 0), (1000, 0)], dxfattribs={"scale_factor": 100})
    msp.add_blockref("B_MUR", (14000, 20000), dxfattribs={"rotation": 90, "xscale": 2,
                                                          "yscale": 2, "zscale": 2})
    msp.add_blockref("B_MUR", (16000, 20000), dxfattribs={"xscale": 2, "yscale": 3})

    # LES BLOCS ET LES RÉFÉRENCES EXTERNES (x ≥ 30000).
    bulle = doc.blocks.new("B_BULLE")
    bulle.add_circle((0, 0), 400)
    bulle.add_attdef("N", (0, 0), dxfattribs={"height": 350})
    for k, x in enumerate((30000, 32000, 34000)):
        ref = msp.add_blockref("B_BULLE", (x, 0))
        ref.add_auto_attribs({"N": "XYZ"[k]})
    section = doc.blocks.new("B_SECTION")
    section.add_lwpolyline([(-150, -150), (150, -150), (150, 150), (-150, 150)], close=True)
    reseau = msp.add_blockref("B_SECTION", (30000, 5000))
    reseau.grid(size=(2, 3), spacing=(1000, 1000))
    exterieur = doc.blocks.new("B_EXTERIEUR")
    exterieur.add_blockref("B_SECTION", (0, 0), dxfattribs={"xscale": 1.5, "yscale": 1.5})
    msp.add_blockref("B_EXTERIEUR", (36000, 5000), dxfattribs={"xscale": 2, "yscale": 2})
    msp.add_blockref("B_SECTION", (38000, 5000), dxfattribs={"xscale": 2, "yscale": -1})
    anonyme = doc.blocks.new_anonymous_block("U")
    anonyme.add_circle((0, 0), 100)
    msp.add_blockref(anonyme.name, (40000, 5000))
    doc.add_xref_def("FICTIF-fond.dwg", "XREF_FOND")
    doc.add_xref_def("FICTIF-fond2.dwg", "XREF_SUPERPOSEE",
                     flags=const.BLK_XREF_OVERLAY | const.BLK_EXTERNAL)
    msp.add_blockref("XREF_FOND", (0, 0))
    msp.add_blockref("XREF_SUPERPOSEE", (0, 0))

    # LES COULEURS (à y = -10000).
    msp.add_line((0, -10000), (1000, -10000), dxfattribs={"layer": "C001", "color": 2})
    msp.add_line((0, -10100), (1000, -10100), dxfattribs={
        "layer": "C001", "true_color": ezdxf.rgb2int((255, 0, 0))})
    msp.add_line((0, -10200), (1000, -10200), dxfattribs={"layer": "C002"})
    msp.add_line((0, -10300), (1000, -10300), dxfattribs={"layer": "C001", "color": 0})
    msp.add_line((0, -10400), (1000, -10400), dxfattribs={"layer": "CALQUE_ABSENT"})
    couleurs = doc.blocks.new("B_COULEURS")
    couleurs.add_line((0, 0), (100, 0), dxfattribs={"layer": "0", "color": 0})
    couleurs.add_line((0, 10), (100, 10), dxfattribs={"layer": "0"})
    couleurs.add_line((0, 20), (100, 20), dxfattribs={"layer": "C001"})
    msp.add_blockref("B_COULEURS", (0, -11000), dxfattribs={"layer": "C002", "color": 6})
    msp.add_line((0, -12000), (1000, -12000), dxfattribs={"layer": "C004"})
    msp.add_text("FICTIF", height=200, dxfattribs={"layer": "C001"}).set_placement((0, -13000))
    return _ecrire(doc)


# --------------------------------------------------------- axes par signature
def dxf_grille_signatures(*, noms: bool = False, forme: str = "cercles", motif: bool = True,
                          intermediaire: bool = False, coupe: bool = False,
                          reperes: bool = False, pieux_numerotes: bool = False,
                          conflit: bool = False, minuscules: bool = False,
                          bas_minuscules: bool = False, bulles: bool = True) -> bytes:
    """Une grille A–D × 1–3 en mm (G2, ``docs/GEOMETRIE_D_ABORD_G2.md``).

    ``noms`` : calque ``AXES``, bloc ``GRID_BUBBLE``, type de ligne ``CENTER`` ;
    sinon ``C001``, ``B001`` et ``LT07`` — le MOTIF de ``CENTER`` sous un nom qui
    ne dit rien (``motif=False`` : tout en continu). ``forme`` : bulles
    ``cercles``, ``hexagones``, ``blocs`` (cercle et attribut au centre) ou
    ``blocs_attribut_dehors`` (l'attribut hors du cercle). Options : un axe
    intermédiaire en trait-point sans bulle (x = 9000, signature B) ; un repère
    de coupe hors de la zone (deux petits cercles « 1 ») ; des repères de locaux
    dans des cercles ; treize pieux numérotés dans des cercles, dont un au bout
    de l'axe A ; un axe E (x = 24000) sur un calque nommé ``COTES`` ; des
    étiquettes en minuscules ; ``bas_minuscules`` : une seconde bulle, en
    minuscule, au pied des axes A–D ; ``bulles=False`` : aucune bulle."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment as A

    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.linetypes.add("LT07", pattern=MOTIFS_N1["LT07"])
    calque = "AXES" if noms else "C001"
    trait = ("CENTER" if noms else "LT07") if motif else "CONTINUOUS"
    doc.layers.add(calque, linetype=trait)
    doc.layers.add("C002")
    doc.layers.add("COTES")
    msp = doc.modelspace()
    nom_bloc = "GRID_BUBBLE" if noms else "B001"
    if forme.startswith("blocs"):
        bloc = doc.blocks.new(nom_bloc)
        bloc.add_circle((0, 0), 400)
        dehors = forme == "blocs_attribut_dehors"
        bloc.add_attdef("N", (0, 600) if dehors else (0, 0), dxfattribs={"height": 300})

    def bulle(texte: str, x: float, y: float, cible: str = calque) -> None:
        if not bulles:
            return
        if forme.startswith("blocs"):
            ref = msp.add_blockref(nom_bloc, (x, y), dxfattribs={"layer": cible})
            ref.add_auto_attribs({"N": texte})
            return
        if forme == "hexagones":
            msp.add_lwpolyline([(x + 400 * math.cos(math.radians(60 * k)),
                                 y + 400 * math.sin(math.radians(60 * k))) for k in range(6)],
                               close=True, dxfattribs={"layer": cible})
        else:
            msp.add_circle((x, y), 400, dxfattribs={"layer": cible})
        msp.add_text(texte, height=300, dxfattribs={"layer": cible}).set_placement(
            (x, y), align=A.MIDDLE_CENTER)

    lettres = "abcd" if minuscules else "ABCD"
    for i, x in enumerate((0.0, 6000.0, 12000.0, 18000.0)):
        msp.add_line((x, -1500), (x, 13500), dxfattribs={"layer": calque})
        bulle(lettres[i], x, 13900)
        if bas_minuscules:
            bulle("abcd"[i], x, -1900)
    for j, y in enumerate((0.0, 6000.0, 12000.0)):
        msp.add_line((-1500, y), (19500, y), dxfattribs={"layer": calque})
        bulle(str(j + 1), -1900, y)
    for x in (0.0, 6000.0, 12000.0, 18000.0):
        for y in (0.0, 6000.0, 12000.0):
            coins = [(x - 200, y - 200), (x + 200, y - 200), (x + 200, y + 200), (x - 200, y + 200)]
            msp.add_hatch(dxfattribs={"layer": "C002"}).paths.add_polyline_path(coins,
                                                                                 is_closed=True)
    if intermediaire:
        msp.add_line((9000, -1500), (9000, 13500), dxfattribs={"layer": calque})
    if coupe:
        msp.add_line((40000, 0), (40000, 10000), dxfattribs={"layer": calque})
        for y in (-300.0, 10300.0):
            msp.add_circle((40000, y), 250, dxfattribs={"layer": calque})
            msp.add_text("1", height=200, dxfattribs={"layer": calque}).set_placement(
                (40000, y), align=A.MIDDLE_CENTER)
    if reperes:
        for k, (x, y) in enumerate(((3000.0, 3000.0), (9000.0, 3000.0), (15000.0, 9000.0))):
            msp.add_circle((x, y), 350, dxfattribs={"layer": "C002"})
            msp.add_text(str(101 + k), height=250, dxfattribs={"layer": "C002"}).set_placement(
                (x, y), align=A.MIDDLE_CENTER)
    if pieux_numerotes:
        places = [(x + 900.0, y + 900.0) for x in (0.0, 6000.0, 12000.0, 18000.0)
                  for y in (0.0, 6000.0, 12000.0)] + [(0.0, -1700.0)]
        for k, (x, y) in enumerate(places):
            msp.add_circle((x, y), 200, dxfattribs={"layer": "C002"})
            msp.add_text(str(k + 1), height=150, dxfattribs={"layer": "C002"}).set_placement(
                (x, y), align=A.MIDDLE_CENTER)
    if conflit:
        msp.add_line((24000, -1500), (24000, 13500), dxfattribs={"layer": "COTES"})
        bulle("E", 24000, 13900, "COTES")
    return _ecrire(doc)
