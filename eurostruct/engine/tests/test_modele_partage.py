"""Le DXF et l'apercu montrent-ils la meme poutre, ou seulement des poutres
qui se ressemblent ?

LE DEFAUT QUE CE MODULE FERME
-------------------------------
Un apercu SVG ecrit a cote du generateur DXF est un second calcul de la meme
geometrie. Les deux concordent le jour ou on les ecrit, et divergent le jour ou
l'un des deux est corrige — sans que rien ne le signale. L'ingenieur valide
alors ce qu'il voit a l'ecran, et telecharge autre chose.

La seule facon sure de l'empecher n'est pas de relire les deux codes: c'est de
n'avoir qu'un seul endroit ou une coordonnee est calculee, et de faire
consommer aux deux rendus le MEME objet gele.

Ce module verifie exactement cela:

* un modele geometrique existe, et il ne connait aucune bibliotheque de rendu ;
* le DXF et le SVG en sortent tous les deux ;
* ce que le SVG affiche — section, barres, cadres, enrobage, unites, mention —
  est ce que le modele porte, et donc ce que le DXF porte ;
* deux rendus du meme modele donnent les memes octets.
"""

from __future__ import annotations

import math

import ezdxf
import pytest

from eurostruct_engine.drawing.beam_section import build_beam_section, rendre_dxf
from eurostruct_engine.drawing.layers import L_COFFRAGE, L_FERR_PRINCIPAL
from eurostruct_engine.drawing.modele import (
    BarRow,
    BeamSectionSpec,
    ModeleSection,
    construire_modele,
)
from eurostruct_engine.drawing.svg import MENTION_APERCU, rendre_svg

B, H, COVER, LINK = 300.0, 600.0, 30.0, 8.0


@pytest.fixture
def spec() -> BeamSectionSpec:
    return BeamSectionSpec(
        b=B, h=H, cover=COVER, link_diameter=LINK,
        bottom=(BarRow(count=4, diameter=20, mark="A1", length=6200),),
        top=(BarRow(count=2, diameter=12, mark="A2", length=6200),),
        link_spacing=200, plot_scale=20,
        title="COUPE", element="P1", project="EUROSTRUCT — cas de reference",
        concrete_grade="C30/37", steel_grade="B500B", exposure_class="XC1",
        date="2026-07-26", mention="PROJET — NON SIGNABLE",
    )


@pytest.fixture
def modele(spec) -> ModeleSection:
    return construire_modele(spec)


# ===========================================================================
# 1 — UN SEUL ENDROIT CALCULE LA GEOMETRIE
# ===========================================================================
def test_le_modele_ne_connait_aucune_bibliotheque_de_rendu() -> None:
    """LA REGLE STRUCTURELLE, ET ELLE EST VERIFIABLE.

    Si `modele.py` importait `ezdxf`, rien n'empecherait plus une coordonnee
    d'y etre calculee « juste pour le DXF ». Le controle porte sur le texte du
    module: c'est grossier, et c'est precisement pour cela qu'il ne peut pas
    etre contourne par inadvertance.
    """
    from eurostruct_engine.drawing import modele as module

    source = __import__("pathlib").Path(module.__file__).read_text(encoding="utf-8")
    for interdit in ("import ezdxf", "from ezdxf", "<svg", "reportlab"):
        assert interdit not in source, (
            f"« {interdit} » entre dans le modele geometrique: la geometrie "
            "va se dedoubler.")


def test_le_dxf_est_rendu_depuis_le_modele(spec, modele) -> None:
    """`build_beam_section` ne doit pas etre un second chemin.

    Le document construit depuis le modele et celui construit depuis la spec
    doivent porter les memes octets: si `build_beam_section` gardait sa propre
    geometrie, ils differeraient.
    """
    import io

    a, b = io.StringIO(), io.StringIO()
    rendre_dxf(modele).write(a)
    build_beam_section(spec)[0].write(b)
    assert a.getvalue() == b.getvalue()


# ===========================================================================
# 2 — CE QUE L'APERCU MONTRE EST CE QUE LE MODELE PORTE
# ===========================================================================
def test_l_apercu_porte_la_section_le_ferraillage_et_les_unites(modele) -> None:
    svg = rendre_svg(modele)

    assert svg.startswith("<svg ") and svg.endswith("</svg>")
    # La section, telle que le calcul l'a fixee.
    assert f"{B:g} x {H:g} mm" in svg
    assert f"enrobage {COVER:g} mm" in svg
    # Les barres: nombre et diametre, lit par lit.
    assert "4 HA20" in svg
    assert "2 HA12" in svg
    # Les cadres: diametre et espacement.
    assert "cadre HA8" in svg
    assert "e = 200 mm" in svg
    # Les cotes, avec leur valeur.
    assert ">300<" in svg and ">600<" in svg
    # Les unites, dites une fois pour toutes.
    assert "Cotes en mm" in svg


def test_l_apercu_se_declare_non_contractuel(modele) -> None:
    """UNE IMAGE SE COPIE ET SE TRANSMET SANS SON BOUTON.

    La mention doit etre DANS le dessin, pas seulement a cote dans l'interface.
    """
    svg = rendre_svg(modele)
    assert MENTION_APERCU in svg
    assert "NON CONTRACTUEL" in MENTION_APERCU


def test_l_apercu_porte_la_mention_et_la_notice_obligatoire(modele) -> None:
    """INTERDICTION N° 8, SUR L'APERCU AUSSI."""
    svg = rendre_svg(modele)
    assert "NON SIGNABLE" in svg
    assert "ingenieur" in svg.lower() or "ingénieur" in svg.lower()


def test_le_nombre_de_barres_dessinees_est_celui_du_modele(modele) -> None:
    assert len(modele.barres) == 6          # 4 en bas, 2 en haut
    assert svg_cercles(rendre_svg(modele)) == 6


def svg_cercles(svg: str) -> int:
    return svg.count(f'class="{L_FERR_PRINCIPAL}" cx=')


# ===========================================================================
# 3 — LE CAS DECISIF: LES DEUX RENDUS DECRIVENT LA MEME SECTION
# ===========================================================================
def test_la_section_du_svg_et_celle_du_dxf_sont_la_meme(spec, modele, tmp_path) -> None:
    """SI LES DEUX GEOMETRIES DIVERGENT, CE CAS TOMBE.

    Le contour du coffrage est mesure de part et d'autre — dans le DXF relu par
    `ezdxf`, et dans le chemin SVG du calque COFFRAGE — puis confronte a la
    section demandee. Un apercu qui dessinerait 250 x 600 pendant que le DXF
    dessine 300 x 600 ne passerait pas ici.
    """
    chemin = tmp_path / "coupe.dxf"
    rendre_dxf(modele).saveas(chemin)
    relu = ezdxf.readfile(chemin)

    contours = [e for e in relu.modelspace()
                if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == L_COFFRAGE]
    assert len(contours) == 1, "un seul contour de coffrage"
    points = [(p[0], p[1]) for p in contours[0].get_points("xy")]
    largeur_dxf = max(x for x, _ in points) - min(x for x, _ in points)
    hauteur_dxf = max(y for _, y in points) - min(y for _, y in points)

    x0, y0, x1, y1 = modele.etendue()
    largeur_modele, hauteur_modele = x1 - x0, y1 - y0

    assert math.isclose(largeur_dxf, spec.b, abs_tol=1e-6)
    assert math.isclose(hauteur_dxf, spec.h, abs_tol=1e-6)
    assert math.isclose(largeur_modele, spec.b, abs_tol=1e-6)
    assert math.isclose(hauteur_modele, spec.h, abs_tol=1e-6)

    # Et le SVG trace bien ce contour-la, aux memes coordonnees.
    svg = rendre_svg(modele)
    assert f'class="{L_COFFRAGE}"' in svg


def test_deux_apercus_du_meme_modele_sont_identiques(modele) -> None:
    """MEME EXIGENCE QUE POUR LE DXF, ET POUR LA MEME RAISON."""
    assert rendre_svg(modele) == rendre_svg(modele)


def test_le_modele_conserve_les_valeurs_demandees(spec, modele) -> None:
    """LES VALEURS D'ORIGINE VOYAGENT AVEC LA GEOMETRIE.

    Un controle doit pouvoir confronter ce qui est dessine a ce qui a ete
    demande sans re-mesurer le trace.
    """
    assert (modele.b, modele.h) == (spec.b, spec.h)
    assert modele.enrobage == spec.cover
    assert modele.diametre_cadre == spec.link_diameter
    assert modele.espacement_cadre == spec.link_spacing
    assert modele.echelle == spec.plot_scale
