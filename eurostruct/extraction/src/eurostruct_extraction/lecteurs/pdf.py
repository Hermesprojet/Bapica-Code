"""Le PDF : la couche texte d'abord, l'OCR pour les pages qui n'en ont pas.

Un plan exporté d'un logiciel de DAO porte presque toujours une couche texte —
les étiquettes y sont des caractères, avec leur position exacte. Un plan
numérisé n'en porte aucune : ce sont des pixels, et seul l'OCR peut en tirer
quelque chose, avec moins de certitude.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Final

from ..modele import Boite, Mot, PageLue
from .ocr import LecteurOcr, rendre_page

__all__ = ["LecturePdf", "PAGES_MAX_OCR", "PAGES_MAX_TEXTE", "lire_pdf"]

#: Un cahier des charges de trois cents pages se lit en entier ; au-delà, les
#: pages restantes sont nommées « non lues ».
PAGES_MAX_TEXTE: Final[int] = 300

#: L'OCR coûte des secondes par page : au plus quatre pages par document.
PAGES_MAX_OCR: Final[int] = 4


@dataclass
class LecturePdf:
    pages: list[PageLue] = field(default_factory=list)
    nombre_de_pages: int = 0
    couche_texte: bool = False
    non_lues: list[dict[str, Any]] = field(default_factory=list)


def lire_pdf(octets: bytes, *, ocr: LecteurOcr | None,
             pages_max_texte: int = PAGES_MAX_TEXTE,
             pages_max_ocr: int = PAGES_MAX_OCR) -> LecturePdf:
    """Lit chaque page, et dit pour chacune comment — ou pourquoi pas.

    Lève l'exception de pdfplumber si le fichier ne s'ouvre pas : c'est à
    l'appelant de la transformer en analyse « echec », avec un motif lisible.
    """
    import pdfplumber

    lecture = LecturePdf()
    a_ocr: list[tuple[int, float, float]] = []
    raison_sans_ocr = ocr.indisponible() if ocr is not None else (
        "l'OCR n'est pas active pour cette analyse")

    with pdfplumber.open(io.BytesIO(octets)) as pdf:
        lecture.nombre_de_pages = len(pdf.pages)
        for numero, page in enumerate(pdf.pages, start=1):
            largeur, hauteur = float(page.width), float(page.height)
            if numero > pages_max_texte:
                lecture.non_lues.append({
                    "page": numero,
                    "motif": f"au-dela de la borne de {pages_max_texte} pages"})
                continue
            brut = page.extract_words(keep_blank_chars=False,
                                      use_text_flow=False,
                                      x_tolerance=1.5, y_tolerance=2.0)
            mots = tuple(
                Mot(texte=str(m["text"]),
                    boite=Boite(float(m["x0"]), float(m["top"]),
                                float(m["x1"]), float(m["bottom"])),
                    methode="texte_natif")
                for m in brut if str(m["text"]).strip())
            if mots:
                lecture.couche_texte = True
                lecture.pages.append(PageLue(numero, largeur, hauteur,
                                             "texte_natif", mots))
            else:
                a_ocr.append((numero, largeur, hauteur))

    for rang, (numero, largeur, hauteur) in enumerate(a_ocr):
        if raison_sans_ocr is not None:
            motif = f"aucune couche texte, et {raison_sans_ocr}"
        elif rang >= pages_max_ocr:
            motif = (f"aucune couche texte, et au-dela de la borne d'OCR de "
                     f"{pages_max_ocr} pages")
        else:
            motif = None
        if motif is not None:
            lecture.non_lues.append({"page": numero, "motif": motif})
            lecture.pages.append(PageLue(numero, largeur, hauteur, "non_lue",
                                         (), motif))
            continue
        assert ocr is not None
        try:
            image, echelle, largeur_pt, hauteur_pt = rendre_page(octets, numero - 1)
            mots_ocr = tuple(ocr.lire_image(image, echelle=echelle))
        except Exception as cause:  # noqa: BLE001 — une page, pas le document
            motif = f"l'OCR a echoue sur cette page ({type(cause).__name__})"
            lecture.non_lues.append({"page": numero, "motif": motif})
            lecture.pages.append(PageLue(numero, largeur, hauteur, "non_lue",
                                         (), motif))
            continue
        lecture.pages.append(PageLue(numero, largeur_pt, hauteur_pt, "ocr",
                                     mots_ocr))

    lecture.pages.sort(key=lambda p: p.numero)
    return lecture
