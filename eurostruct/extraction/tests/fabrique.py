"""Des documents FABRIQUÉS par les tests — aucun plan réel n'est commité.

Chaque fabrique écrit le strict nécessaire pour que le lecteur ait quelque
chose à lire, et rien qui ressemble à un document d'un vrai bureau :

* ``pdf_de_texte`` : un PDF minimal à couche texte (Helvetica, WinAnsi),
  écrit à la main pour que la position de chaque ligne soit CONNUE du test ;
* ``pdf_numerise`` : une image de texte enregistrée en PDF — aucune couche
  texte, seul l'OCR peut la lire ;
* ``dxf_de_plan`` : un DXF R2018 écrit par ezdxf, avec textes, axes et cotes ;
* ``entete_dwg`` : SIX octets de signature suivis de zéros. Ce n'est PAS un
  dessin : c'est exactement ce que le produit lit d'un DWG, et rien de plus.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

#: (x, y_haut, taille, texte) en points, origine en haut à gauche.
Texte = tuple[float, float, float, str]


def _echapper(texte: str) -> bytes:
    brut = texte.encode("cp1252")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def pdf_de_texte(pages: Sequence[Sequence[Texte]], *, largeur: float = 595.0,
                 hauteur: float = 842.0) -> bytes:
    """Un PDF à couche texte ; une page vide n'a AUCUN caractère."""
    objets: list[bytes] = []

    def ajouter(corps: bytes) -> int:
        objets.append(corps)
        return len(objets)

    catalogue = ajouter(b"")  # rempli plus bas
    racine_pages = ajouter(b"")
    police = ajouter(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                     b"/Encoding /WinAnsiEncoding >>")
    enfants: list[int] = []
    for page in pages:
        flux = b"".join(
            b"BT /F1 %.2f Tf %.2f %.2f Td (" % (taille, x, hauteur - y - taille)
            + _echapper(texte) + b") Tj ET\n"
            for x, y, taille, texte in page)
        contenu = ajouter(b"<< /Length %d >>\nstream\n" % len(flux) + flux
                          + b"\nendstream")
        enfants.append(ajouter(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (racine_pages, largeur, hauteur, police, contenu)))
    objets[catalogue - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % racine_pages
    objets[racine_pages - 1] = (
        b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % e for e in enfants)
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
    sortie.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                 % (len(objets) + 1, catalogue, xref))
    return sortie.getvalue()


def pdf_numerise(lignes: Sequence[str], *, dpi: int = 200) -> bytes:
    """Une page A4 « numérisée » : du texte dessiné en pixels, sans couche texte."""
    from PIL import Image, ImageDraw, ImageFont

    largeur, hauteur = int(8.27 * dpi), int(11.69 * dpi)
    image = Image.new("L", (largeur, hauteur), 255)
    dessin = ImageDraw.Draw(image)
    try:
        police = ImageFont.truetype("DejaVuSans.ttf", size=int(dpi * 0.2))
    except OSError:
        police = ImageFont.load_default(size=int(dpi * 0.2))
    y = int(dpi * 1.0)
    for ligne in lignes:
        dessin.text((int(dpi * 0.8), y), ligne, fill=0, font=police)
        y += int(dpi * 0.45)
    sortie = io.BytesIO()
    image.save(sortie, format="PDF", resolution=float(dpi))
    return sortie.getvalue()


def dxf_de_plan(*, insunits: int = 4, binaire: bool = False,
                texte_force: str | None = None, dimlfac: float = 1.0,
                mention: str | None = None) -> bytes:
    """Un plan DXF R2018 : textes, deux axes étiquetés, une cote d'axes, une cote."""
    import ezdxf

    document = ezdxf.new("R2018", setup=True)
    document.header["$INSUNITS"] = insunits
    for calque in ("AXES", "TEXTE", "COTES"):
        document.layers.add(calque)
    espace = document.modelspace()
    espace.add_text("Poutre P1 30x60",
                    dxfattribs={"layer": "TEXTE", "height": 100}).set_placement((1000, 2000))
    espace.add_mtext("Beton C25/30\\PEnrobage 30 mm",
                     dxfattribs={"layer": "TEXTE", "char_height": 100}).set_location((1000, 3000))
    if mention:
        espace.add_text(mention, dxfattribs={"layer": "TEXTE", "height": 100}
                        ).set_placement((1000, 4000))
    espace.add_line((0, 0), (0, 10000), dxfattribs={"layer": "AXES"})
    espace.add_line((6000, 0), (6000, 10000), dxfattribs={"layer": "AXES"})
    espace.add_text("A", dxfattribs={"layer": "AXES", "height": 250}).set_placement((0, 10500))
    espace.add_text("B", dxfattribs={"layer": "AXES", "height": 250}).set_placement((6000, 10500))
    # UN STYLE DE COTE QUI AFFICHE LA MESURE (DIMLFAC = 1) : le style « EZDXF »
    # d'ezdxf, fait pour un dessin en m coté en cm, la multiplie par 100.
    style = document.dimstyles.duplicate_entry("EZDXF", "COTES_MM")
    style.dxf.dimlfac = dimlfac
    espace.add_linear_dim(base=(0, 11000), p1=(0, 10000), p2=(6000, 10000),
                          dimstyle="COTES_MM", dxfattribs={"layer": "AXES"}).render()
    cote = espace.add_linear_dim(base=(0, -1000), p1=(0, 0), p2=(2500, 0),
                                 text=texte_force or "<>", dimstyle="COTES_MM",
                                 dxfattribs={"layer": "COTES"})
    cote.render()
    if binaire:
        sortie = io.BytesIO()
        document.write(sortie, fmt="bin")
        return sortie.getvalue()
    flux = io.StringIO()
    document.write(flux)
    return flux.getvalue().encode("utf-8")


def entete_dwg(version: str = "AC1032") -> bytes:
    """La signature d'un DWG, et des zéros : rien d'un dessin."""
    return version.encode("ascii") + bytes(122)


#: LE PLAN DE TEST: une ligne par catégorie, à une position connue.
LIGNES_DU_PLAN: tuple[Texte, ...] = (
    (40, 40, 12, "FICTIF - PLAN DE COFFRAGE - NIVEAU +1"),
    (40, 60, 9, "Cotes en cm"),
    (40, 90, 10, "Poutre P1 30x60"),
    (40, 110, 10, "Portée P1 : 6,00 m"),
    (40, 130, 10, "Béton C30/37 - classe d'exposition XC3"),
    (40, 150, 10, "Armatures B500B - enrobage 30 mm"),
    (40, 170, 10, "P1 : 4 HA 20 - cadres HA8 e=15"),
    (40, 190, 10, "Dalle ép. 20 cm"),
    (40, 210, 10, "Niveau +1 : +3,20"),
    (40, 230, 10, "Hauteur d'étage 3,00 m"),
    (40, 250, 10, "Poteau C1 30x30"),
    (40, 270, 10, "Charge d'exploitation Q = 2,5 kN/m²"),
    (40, 290, 10, "Longueur totale 24,00 m"),
    (40, 310, 10, "Axes A-B : 6,00 m"),
    (40, 330, 10, "NOTE : les cotes sont à vérifier sur chantier"),
    # UNE ETIQUETTE ELOIGNEE SUR LA MEME HAUTEUR: elle ne doit pas se coller
    # a la ligne de gauche.
    (400, 90, 10, "XC4"),
)
