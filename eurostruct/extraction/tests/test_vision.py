"""Le contrat d'un futur modèle de vision — éprouvé par un détecteur DE TEST."""

from __future__ import annotations

from eurostruct_extraction import (
    CHAINE_PAR_DEFAUT,
    ExtracteurVision,
    ObjetDetecte,
    ValeurLue,
    extract_engineering_data,
    parse_document,
)
from eurostruct_extraction.modele import Boite
from fabrique import LIGNES_DU_PLAN, pdf_de_texte


class DetecteurDeTest:
    """UN DÉTECTEUR DE TEST, déclaré comme tel. Il ne regarde pas l'image : il
    rend toujours les mêmes objets, pour éprouver la conversion en
    propositions. Il n'est inscrit dans aucune chaîne de production."""

    nom = "detecteur-de-test"
    version = "0"

    def __init__(self) -> None:
        self.pages_vues: list[int] = []

    def detecter(self, page):
        self.pages_vues.append(page.numero)
        assert page.echelle > 0 and page.image is not None
        return [
            ObjetDetecte("beam", Boite(40, 90, 120, 102), 0.99,
                         {"width": ValeurLue(30, "cm", "30x60"),
                          "colour": ValeurLue("rouge", None)}, repere="P1"),
            ObjetDetecte("column", Boite(40, 250, 90, 262), 0.5),
            ObjetDetecte("staircase", Boite(1, 1, 2, 2), 0.9),
        ]


def test_la_chaine_par_defaut_ne_contient_aucun_modele_de_vision():
    assert [e.nom for e in CHAINE_PAR_DEFAUT] == ["geometrie", "motifs", "entites_dxf"]
    analyse = parse_document(pdf_de_texte([LIGNES_DU_PLAN]), ocr=None)
    assert all(c.methode != "vision"
               for c in extract_engineering_data(analyse).candidats)


def test_une_detection_devient_une_proposition_tracee_et_plafonnee():
    detecteur = DetecteurDeTest()
    analyse = parse_document(pdf_de_texte([LIGNES_DU_PLAN]), ocr=None)
    resultat = extract_engineering_data(analyse, [ExtracteurVision(detecteur)])
    assert detecteur.pages_vues == [1]
    par_categorie = {c.categorie: c for c in resultat.candidats}

    largeur = par_categorie["beam_width"]
    assert (largeur.valeur, largeur.unite, largeur.repere) == (30, "cm", "P1")
    assert largeur.methode == "vision"
    assert largeur.confiance == 0.9          # 0,99 plafonne
    assert largeur.texte_brut == "30x60"
    assert largeur.fondement["model"] == "detecteur-de-test"

    # UNE DETECTION SANS VALEUR: la classe, rien de plus.
    poteau = par_categorie["detected_element"]
    assert poteau.valeur == "column"
    assert "sans texte lu" in poteau.texte_brut

    # UN ATTRIBUT SANS CATEGORIE, UNE CLASSE INCONNUE: rien n'est devine.
    assert "rouge" not in [c.valeur for c in resultat.candidats]
    assert "staircase" not in [c.valeur for c in resultat.candidats]
    assert resultat.compte_rendu["extractors"] == ["vision:detecteur-de-test/0"]
