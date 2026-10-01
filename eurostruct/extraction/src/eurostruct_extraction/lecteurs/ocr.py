"""La reconnaissance de caractères, pour les pages sans couche texte.

BORNÉE, ET LA BORNE EST DITE. Un plan A1 rendu à 300 dpi pèse 70 millions de
pixels ; Tesseract y passerait des minutes, pour un service qui répond à une
requête. Le rendu est donc plafonné en pixels (la résolution baisse sur les
grands formats) et en nombre de pages ; chaque page laissée de côté est nommée
dans le compte rendu, avec son motif.

UNE LECTURE OCR N'EST PAS UNE LECTURE DE TEXTE. Sa confiance est celle que
Tesseract rend, mot par mot, et les propositions qui en sortent la portent —
plafonnée bien en dessous d'une lecture de couche texte.

PDFIUM N'EST PAS RÉENTRANT. Le service traite les requêtes dans un groupe de
fils ; deux rendus simultanés dans la même bibliothèque peuvent la faire
tomber. Tout appel à pypdfium2 passe donc par un verrou de module.
"""

from __future__ import annotations

import io
import math
import shutil
import threading
from typing import Any, Final, Protocol

from ..modele import Boite, Mot

__all__ = [
    "LecteurOcr",
    "OcrTesseract",
    "PIXELS_MAX",
    "VERROU_PDFIUM",
    "rendre_page",
]

#: Le plafond de pixels d'une page rendue : un A4 à 300 dpi (8,7 Mpx) passe
#: entier ; un A1 descend autour de 170 dpi.
PIXELS_MAX: Final[int] = 25_000_000

#: La résolution visée quand le plafond le permet.
DPI_MAX: Final[int] = 300

#: Un mot que Tesseract lit avec moins de 30 % de confiance est du bruit : sur
#: un plan, ce sont des hachures et des cotes tournées lues comme des lettres.
CONFIANCE_MIN_MOT: Final[float] = 0.30

VERROU_PDFIUM: Final[threading.Lock] = threading.Lock()


class LecteurOcr(Protocol):
    """Ce qu'un moteur d'OCR doit savoir faire pour servir ici."""

    nom: str

    def indisponible(self) -> str | None:
        """``None`` s'il peut lire ; sinon, la raison, en clair."""
        ...

    def lire_image(self, image: Any, *, echelle: float) -> list[Mot]:
        """Les mots de l'image, boîtes ramenées en points (÷ ``echelle``)."""
        ...


class OcrTesseract:
    """Tesseract, en français et en anglais, en mode « texte épars ».

    LE MODE ÉPARS (``--psm 11``) parce qu'un plan n'a pas de paragraphes : des
    étiquettes dispersées, des cotes, un cartouche. Le regroupement en lignes
    est fait ensuite, sur les positions, par ``extracteurs.lignes`` — le même
    code que pour une couche texte native.
    """

    nom = "tesseract"

    def __init__(self, langues: str = "fra+eng", psm: int = 11,
                 delai_s: float = 90.0) -> None:
        self.langues = langues
        self.psm = psm
        self.delai_s = delai_s

    def indisponible(self) -> str | None:
        try:
            import pytesseract
        except ImportError:
            return "le pilote pytesseract n'est pas installe sur ce serveur"
        if shutil.which("tesseract") is None:
            return "le programme tesseract n'est pas installe sur ce serveur"
        try:
            langues = set(pytesseract.get_languages(config=""))
        except Exception as cause:  # noqa: BLE001 — on rend la raison, pas la pile
            return f"tesseract ne repond pas ({type(cause).__name__})"
        manquantes = [lg for lg in self.langues.split("+") if lg not in langues]
        if manquantes:
            return ("langue(s) d'OCR absente(s) sur ce serveur: "
                    + ", ".join(manquantes))
        return None

    def lire_image(self, image: Any, *, echelle: float) -> list[Mot]:
        import pytesseract

        donnees = pytesseract.image_to_data(
            image, lang=self.langues, config=f"--psm {self.psm}",
            output_type=pytesseract.Output.DICT, timeout=self.delai_s)
        mots: list[Mot] = []
        for i, brut in enumerate(donnees["text"]):
            texte = (brut or "").strip()
            try:
                confiance = float(donnees["conf"][i]) / 100.0
            except (TypeError, ValueError):
                continue
            if not texte or confiance < CONFIANCE_MIN_MOT:
                continue
            gauche, haut = donnees["left"][i], donnees["top"][i]
            largeur, hauteur = donnees["width"][i], donnees["height"][i]
            mots.append(Mot(
                texte=texte,
                boite=Boite(gauche / echelle, haut / echelle,
                            (gauche + largeur) / echelle,
                            (haut + hauteur) / echelle),
                methode="ocr",
                confiance=round(min(confiance, 1.0), 3),
            ))
        return mots


def rendre_page(octets: bytes, index: int, *,
                pixels_max: int = PIXELS_MAX) -> tuple[Any, float, float, float]:
    """L'image d'une page, l'échelle (pixels par point), et la taille en points.

    ``index`` commence à 0. L'échelle vise 300 dpi et descend juste assez pour
    tenir dans ``pixels_max``.
    """
    import pypdfium2 as pdfium

    with VERROU_PDFIUM:
        document = pdfium.PdfDocument(io.BytesIO(octets))
        try:
            page = document[index]
            largeur, hauteur = page.get_size()
            echelle = min(DPI_MAX / 72.0,
                          math.sqrt(pixels_max / max(largeur * hauteur, 1.0)))
            image = page.render(scale=echelle).to_pil()
            page.close()
        finally:
            document.close()
    return image, echelle, float(largeur), float(hauteur)
