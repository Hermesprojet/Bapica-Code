"""Les pages sans couche texte : OCR borné, confiance plafonnée, pages non lues nommées."""

from __future__ import annotations

import pytest

from eurostruct_extraction import OcrTesseract, extract_engineering_data, parse_document
from eurostruct_extraction.modele import Boite, Mot
from fabrique import pdf_de_texte, pdf_numerise

RAISON_TESSERACT = OcrTesseract().indisponible()


class OcrDeTest:
    """UN LECTEUR DE TEST, déclaré comme tel : il « lit » toujours la même
    ligne, pour éprouver les bornes sans dépendre de Tesseract."""

    nom = "ocr-de-test"

    def __init__(self) -> None:
        self.appels = 0

    def indisponible(self) -> str | None:
        return None

    def lire_image(self, image, *, echelle):
        self.appels += 1
        return [Mot("Béton", Boite(40, 40, 70, 50), "ocr", 0.95),
                Mot("C30/37", Boite(75, 40, 110, 50), "ocr", 0.42)]


def _pages_blanches(nombre: int) -> bytes:
    return pdf_de_texte([[] for _ in range(nombre)])


def test_l_ocr_est_borne_et_les_pages_laissees_sont_nommees():
    ocr = OcrDeTest()
    analyse = parse_document(_pages_blanches(3), ocr=ocr, pages_max_ocr=1)
    assert ocr.appels == 1
    assert analyse.statut == "partiel"
    assert [n["page"] for n in analyse.compte_rendu["not_read"]] == [2, 3]
    assert all("borne d'OCR de 1 pages" in n["motif"]
               for n in analyse.compte_rendu["not_read"])


def test_sans_ocr_un_pdf_sans_couche_texte_n_est_pas_lu_et_le_dit():
    analyse = parse_document(_pages_blanches(2), ocr=None)
    assert analyse.statut == "non_lu"
    assert analyse.couche_texte is False
    assert "non lue" in analyse.detail
    assert extract_engineering_data(analyse).candidats == ()


def test_la_confiance_d_une_lecture_ocr_est_celle_de_son_mot_le_plus_faible():
    analyse = parse_document(_pages_blanches(1), ocr=OcrDeTest())
    classe = [c for c in extract_engineering_data(analyse).candidats
              if c.categorie == "concrete_class"][0]
    assert classe.methode == "ocr"
    assert classe.confiance == 0.42


def test_la_confiance_ocr_est_plafonnee_meme_quand_tesseract_est_sur():
    class OcrTropSur(OcrDeTest):
        def lire_image(self, image, *, echelle):
            return [Mot("C30/37", Boite(40, 40, 80, 50), "ocr", 0.99)]

    analyse = parse_document(_pages_blanches(1), ocr=OcrTropSur())
    classe = extract_engineering_data(analyse).candidats[0]
    assert classe.confiance == 0.6


@pytest.mark.skipif(RAISON_TESSERACT is not None,
                    reason=f"Tesseract indisponible: {RAISON_TESSERACT}")
def test_une_page_numerisee_est_lue_par_tesseract():
    octets = pdf_numerise(["Beton C30/37 classe XC3", "Poutre P1 30x60 cm",
                           "Enrobage 30 mm"])
    analyse = parse_document(octets)
    assert analyse.statut == "analyse"
    assert analyse.couche_texte is False
    assert analyse.compte_rendu["pages"][0]["method"] == "ocr"
    candidats = {c.categorie: c for c in extract_engineering_data(analyse).candidats}
    assert candidats["concrete_class"].valeur == "C30/37"
    assert candidats["beam_width"].valeur == 30
    assert candidats["beam_width"].unite == "cm"
    assert candidats["concrete_cover"].valeur == 30
    for candidat in candidats.values():
        assert candidat.methode == "ocr"
        assert candidat.confiance <= 0.6
        # LA BOITE EST EN POINTS, PAS EN PIXELS: elle tient dans la page A4.
        x0, y0, x1, y1 = candidat.boite.en_liste()
        assert 0 <= x0 < x1 <= 596 and 0 <= y0 < y1 <= 843
