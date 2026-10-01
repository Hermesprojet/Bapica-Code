"""Le DWG : conservé, identifié, non lu — et prêt pour une conversion sous licence."""

from __future__ import annotations

import pytest

from eurostruct_extraction import (
    FormatNonPrisEnCharge,
    extract_engineering_data,
    parse_document,
)
from fabrique import dxf_de_plan, entete_dwg


def test_un_dwg_n_est_pas_lu_et_le_dit_avec_le_remede():
    analyse = parse_document(entete_dwg("AC1032"))
    assert analyse.format == "dwg"
    assert analyse.statut == "non_lu"
    assert analyse.version_dwg == "AC1032"
    assert "licence ODA ou RealDWG" in analyse.detail
    assert "Exportez le plan en DXF" in analyse.detail
    assert analyse.compte_rendu["dwg_release"] == "AutoCAD 2018"
    assert extract_engineering_data(analyse).candidats == ()


class ConversionDeTest:
    """UNE CONVERSION DE TEST, déclarée comme telle : elle ignore le DWG et
    rend un DXF fabriqué. Elle éprouve le CHEMIN qu'une conversion sous
    licence emprunterait — elle ne prétend rien convertir."""

    nom = "conversion-de-test"

    def convertir(self, octets: bytes) -> bytes:
        return dxf_de_plan()


def test_une_conversion_configuree_suit_le_chemin_du_dxf_et_se_nomme():
    analyse = parse_document(entete_dwg(), convertisseur_dwg=ConversionDeTest())
    assert analyse.format == "dwg"
    assert analyse.statut == "analyse"
    assert analyse.compte_rendu["conversion"]["converter"] == "conversion-de-test"
    assert analyse.compte_rendu["conversion"]["dwg_version"] == "AC1032"
    assert analyse.detail.startswith("converti par conversion-de-test")
    categories = {c.categorie for c in extract_engineering_data(analyse).candidats}
    assert {"grid_line", "grid_spacing", "concrete_class"} <= categories


def test_une_conversion_qui_ne_rend_pas_un_dxf_fait_echouer_l_analyse():
    class ConversionFautive:
        nom = "conversion-fautive"

        def convertir(self, octets: bytes) -> bytes:
            return b"FICTIF: pas un DXF"

    with pytest.raises(FormatNonPrisEnCharge):
        parse_document(entete_dwg(), convertisseur_dwg=ConversionFautive())
