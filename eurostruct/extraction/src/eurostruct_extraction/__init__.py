"""EUROSTRUCT — lecture des plans et des cahiers des charges.

Des octets vers des PROPOSITIONS tracées. Jamais vers des valeurs confirmées :
la confirmation est un geste humain, signé, enregistré par la base.

    from eurostruct_extraction import parse_document, extract_engineering_data

    analyse = parse_document(octets)
    resultat = extract_engineering_data(analyse)
    for candidat in resultat.candidats:
        ...  # catégorie, valeur, unité, texte lu, page, boîte, confiance

Ce paquet ne connaît ni la base, ni le réseau, ni l'identité, ni le moteur de
calcul. Voir ``docs/LECTURE_DES_PLANS.md``.
"""

from .analyse import OCR_PAR_DEFAUT, parse_document
from .categories import CATEGORIES, Categorie, categorie
from .extracteurs.vision import (
    ExtracteurVision,
    ModeleDeVision,
    ObjetDetecte,
    PageRendue,
    ValeurLue,
)
from .formats import FormatDetecte, FormatNonPrisEnCharge, detecter_format
from .lecteurs.dwg import ConvertisseurDWG
from .lecteurs.ocr import LecteurOcr, OcrTesseract
from .modele import Boite, Candidat, DocumentAnalyse
from .registre import (
    CHAINE_PAR_DEFAUT,
    Extracteur,
    ResultatExtraction,
    extract_engineering_data,
)
from .version import VERSION_EXTRACTEUR

__all__ = [
    "CATEGORIES",
    "CHAINE_PAR_DEFAUT",
    "OCR_PAR_DEFAUT",
    "VERSION_EXTRACTEUR",
    "Boite",
    "Candidat",
    "Categorie",
    "ConvertisseurDWG",
    "DocumentAnalyse",
    "Extracteur",
    "ExtracteurVision",
    "FormatDetecte",
    "FormatNonPrisEnCharge",
    "LecteurOcr",
    "ModeleDeVision",
    "ObjetDetecte",
    "OcrTesseract",
    "PageRendue",
    "ResultatExtraction",
    "ValeurLue",
    "categorie",
    "detecter_format",
    "extract_engineering_data",
    "parse_document",
]
