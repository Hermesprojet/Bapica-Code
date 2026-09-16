"""Le plan tiré d'une étude complète porte la mention du MODE du calcul.

MESURE LE 16/09 EN OUVRANT LE DXF D'UNE ÉTUDE EXPLORATOIRE DANS LibreCAD
2.2.0.2 : le cartouche portait le filigrane de brouillon et la notice de
validation, mais pas « PROJET — NON SIGNABLE ». La coupe gelée avec l'étude
(``drawing_spec``) ne porte que la GÉOMÉTRIE ; la mention, elle, se lit sur le
mode du calcul — et ``_modele_du_dessin`` la laissait tomber sur ce chemin,
alors que le chemin de la flexion seule la posait (cas 4 de
``test_livrable_dxf.py``).

Aucune base ici : la fonction est appelée directement sur une ligne de calcul
telle que l'atelier la relit, avec une coupe gelée.
"""

from __future__ import annotations

import io

from eurostruct_api.routes.livrables import _modele_du_dessin
from eurostruct_engine.drawing.beam_section import rendre_dxf

MENTION = "PROJET — NON SIGNABLE"

COUPE_GELEE = {
    "b": 300.0, "h": 600.0, "cover": 40.0, "link_diameter": 10.0,
    "link_spacing": 150.0, "link_mark": "C1",
    "bottom": [{"count": 4, "diameter": 20.0, "mark": "A1"}],
    "top": [],
    "element": "P1", "concrete_grade": "C30/37", "steel_grade": "B500B",
    "exposure_class": "XC3", "plot_scale": 20.0,
}


def _calcul_avec_coupe() -> dict:
    return {"strict_ndp": False,
            "result": {"result": {"drawing_spec": dict(COUPE_GELEE)}}}


def test_la_mention_est_posee_sur_le_plan_d_une_etude_gelee() -> None:
    modele = _modele_du_dessin(_calcul_avec_coupe(), None, MENTION)
    assert modele.mention == MENTION
    cartouche = [t.contenu for t in modele.textes if t.calque == "CARTOUCHE"]
    assert any("NON SIGNABLE" in t for t in cartouche), cartouche


def test_le_dxf_de_l_etude_gelee_porte_la_mention() -> None:
    """Jusqu'aux octets : c'est le fichier que l'ingénieur ouvrira."""
    modele = _modele_du_dessin(_calcul_avec_coupe(), None, MENTION)
    tampon = io.StringIO()
    rendre_dxf(modele).write(tampon)
    assert "NON SIGNABLE" in tampon.getvalue()


def test_sans_mention_le_plan_n_en_invente_aucune() -> None:
    """Un calcul strict n'en porte pas, et la coupe gelée n'en fabrique pas."""
    modele = _modele_du_dessin(_calcul_avec_coupe(), None, None)
    assert modele.mention == ""
    assert not any("NON SIGNABLE" in t.contenu for t in modele.textes)


def test_la_geometrie_gelee_n_est_pas_touchee_par_la_mention() -> None:
    """La mention s'ajoute au cartouche ; la coupe reste celle qui a été vérifiée."""
    sans = _modele_du_dessin(_calcul_avec_coupe(), None, None)
    avec = _modele_du_dessin(_calcul_avec_coupe(), None, MENTION)
    assert avec.polylignes == sans.polylignes
    assert avec.disques == sans.disques
    assert avec.cotes == sans.cotes
