"""Le DXF : textes, axes et cotes, avec leur calque, leur poignée et leur unité."""

from __future__ import annotations

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from fabrique import dxf_de_plan


@pytest.fixture(scope="module", params=[False, True], ids=["ascii", "binaire"])
def resultat(request):
    analyse = parse_document(dxf_de_plan(binaire=request.param))
    return analyse, extract_engineering_data(analyse).candidats


def test_l_espace_objet_est_lu_et_son_unite_aussi(resultat):
    analyse, _ = resultat
    assert analyse.statut == "analyse"
    assert analyse.format == "dxf"
    assert analyse.unites_dxf == "mm"
    assert analyse.compte_rendu["insunits"] == 4
    assert analyse.nombre_de_pages == 1


def test_les_etiquettes_d_axes_deviennent_des_files(resultat):
    _, candidats = resultat
    files = sorted(c.valeur for c in candidats if c.categorie == "grid_line")
    assert files == ["A", "B"]
    a = [c for c in candidats if c.valeur == "A"][0]
    assert a.position["layer"] == "AXES"
    assert a.position["handle"]
    assert a.boite is None and a.page == 1


def test_une_cote_sur_un_calque_d_axes_est_un_entraxe_dans_l_unite_du_dessin(resultat):
    _, candidats = resultat
    entraxe = [c for c in candidats if c.categorie == "grid_spacing"][0]
    assert (entraxe.valeur, entraxe.unite) == (6000, "mm")
    assert entraxe.fondement["unit_basis"] == "declaration"
    assert entraxe.fondement["unit_declaration"]["source"] == "$INSUNITS"
    assert entraxe.methode == "dxf"


def test_une_cote_ailleurs_reste_une_cote_non_classee(resultat):
    _, candidats = resultat
    cote = [c for c in candidats if c.categorie == "dimension"][0]
    assert (cote.valeur, cote.unite) == (2500, "mm")
    assert cote.position["layer"] == "COTES"


def test_les_regles_de_texte_lisent_aussi_les_textes_du_dessin(resultat):
    _, candidats = resultat
    assert [c.valeur for c in candidats if c.categorie == "concrete_class"] == ["C25/30"]
    enrobage = [c for c in candidats if c.categorie == "concrete_cover"][0]
    assert (enrobage.valeur, enrobage.unite) == (30, "mm")
    # LE TEXTE « 30x60 » N'HERITE PAS DE $INSUNITS: l'unite du dessin dit en
    # quoi la geometrie est tracee, pas en quoi les annotations sont ecrites.
    largeur = [c for c in candidats if c.categorie == "beam_width"][0]
    assert largeur.unite is None
    assert largeur.fondement["unit_basis"] == "absente"


@pytest.mark.parametrize(("force", "valeur"), [("2450", 2450), ("2 450", 2450),
                                               ("2450 mm", 2450)])
def test_un_texte_force_numerique_est_la_valeur_que_le_plan_montre(force, valeur):
    analyse = parse_document(dxf_de_plan(texte_force=force))
    cote = [c for c in extract_engineering_data(analyse).candidats
            if c.categorie == "dimension"][0]
    assert cote.valeur == valeur
    assert cote.unite == "mm"
    assert cote.fondement["rule"] == "cote_dxf_texte_force"
    # LA MESURE GEOMETRIQUE EST CITEE A COTE: un plan « hors echelle » se voit.
    assert cote.fondement["measured"] == "2500"


def test_un_texte_force_non_numerique_ne_propose_rien():
    analyse = parse_document(dxf_de_plan(texte_force="VAR"))
    assert not [c for c in extract_engineering_data(analyse).candidats
                if c.categorie == "dimension"]


def test_un_dessin_sans_unite_donne_des_cotes_sans_unite():
    analyse = parse_document(dxf_de_plan(insunits=0))
    entraxe = [c for c in extract_engineering_data(analyse).candidats
               if c.categorie == "grid_spacing"][0]
    assert entraxe.unite is None
    assert entraxe.fondement["unit_basis"] == "absente"
