"""Toute proposition passe les règles que la base lui opposera (0028).

Une seule proposition refusée par ``extraction_is_traced`` ou
``extraction_value_shape`` ferait échouer l'enregistrement de TOUTE l'analyse :
la propriété est donc vérifiée ici, sur chaque proposition de chaque format.
"""

from __future__ import annotations

import json
import re

import pytest

from eurostruct_extraction import (
    CATEGORIES,
    VERSION_EXTRACTEUR,
    Candidat,
    extract_engineering_data,
    parse_document,
)
from eurostruct_extraction.modele import Boite
from fabrique import LIGNES_DU_PLAN, dxf_de_plan, pdf_de_texte
from fabrique_geometrie import (
    dxf_bulles_lettres_chiffres,
    dxf_charpente_mm,
    dxf_coffrage_s101,
    dxf_etiquettes_d_axes,
    dxf_fondations_pieux,
    dxf_sans_calques_m,
)
from fabrique_pdf_vectoriel import pdf_plan_gaine, pdf_plan_sans_echelle_ecrite, pdf_plan_vectoriel

#: Les méthodes que ``extraction_is_traced`` admet (0029).
METHODES = {"texte_natif", "ocr", "dxf", "vision", "geometrie"}

_DOCUMENTS = {
    "pdf": lambda: pdf_de_texte([LIGNES_DU_PLAN]),
    "dxf": dxf_de_plan,
    # LA GEOMETRIE: chaque proposition d'un modele structurel passe aussi.
    "coffrage_cm": dxf_coffrage_s101,
    "coffrage_sans_unite": lambda: dxf_coffrage_s101(insunits=0, declaration=False),
    "charpente_mm": dxf_charpente_mm,
    "sans_calques_m": dxf_sans_calques_m,
    # UNE FEUILLE PDF: boite sur la feuille ET position, ensemble.
    "feuille_pdf": pdf_plan_vectoriel,
    "feuille_pdf_sans_echelle": pdf_plan_sans_echelle_ecrite,
    # PIEUX, GAINES, ETIQUETTES, UNITE PAR LA PRESENTATION.
    "fondations_pieux": dxf_fondations_pieux,
    "etiquettes_d_axes": dxf_etiquettes_d_axes,
    "feuille_pdf_gaine": pdf_plan_gaine,
    # ETIQUETTES EN LETTRES ET CHIFFRES, LUES EN BULLE.
    "bulles_lettres_chiffres": dxf_bulles_lettres_chiffres,
}


@pytest.fixture(scope="module", params=list(_DOCUMENTS))
def candidats(request):
    octets = _DOCUMENTS[request.param]()
    resultat = extract_engineering_data(parse_document(octets, ocr=None))
    assert resultat.candidats
    return resultat.candidats


def test_chaque_proposition_porte_tout_ce_que_la_base_exige(candidats):
    for c in candidats:
        ligne = c.en_ligne()
        assert ligne["raw_text"].strip(), c
        assert ligne["page"] >= 1
        if ligne["bbox"] is not None:
            x0, y0, x1, y1 = ligne["bbox"]
            assert x0 <= x1 and y0 <= y1
        else:
            assert isinstance(ligne["position"], dict)
        assert 0 <= ligne["confidence"] < 1
        assert ligne["method"] in METHODES
        assert re.fullmatch(r"[a-z][a-z0-9_]{1,63}", ligne["kind"])
        assert ligne["kind"] in CATEGORIES
        valeur = ligne["proposed_value"]
        assert set(valeur) == {"value", "unit"}
        assert isinstance(valeur["value"], int | float | str)
        if isinstance(valeur["value"], str):
            assert valeur["value"].strip()
        assert valeur["unit"] is None or valeur["unit"].strip()
        # SERIALISABLE TEL QUEL: c'est ce qui part a la base.
        json.dumps(ligne)


def test_aucune_proposition_n_est_une_certitude(candidats):
    assert max(c.confiance for c in candidats) <= 0.95


def test_chaque_proposition_dit_sa_regle(candidats):
    assert all(c.fondement.get("rule") for c in candidats)


def test_la_version_est_nommee():
    assert re.fullmatch(r"eurostruct-extraction/\d+\.\d+\.\d+", VERSION_EXTRACTEUR)


@pytest.mark.parametrize("fausse", [
    {"texte_brut": " "},
    {"page": 0},
    {"boite": None, "position": None},
    {"confiance": 1.0},
    {"confiance": -0.01},
    {"valeur": "  "},
    {"unite": ""},
])
def test_une_proposition_que_la_base_refuserait_n_existe_pas_ici_non_plus(fausse):
    champs = dict(categorie="beam_width", valeur=30, unite="cm", texte_brut="P1 30x60",
                  page=1, confiance=0.5, methode="texte_natif",
                  boite=Boite(1, 2, 3, 4), position=None)
    champs.update(fausse)
    with pytest.raises(ValueError):
        Candidat(**champs)
