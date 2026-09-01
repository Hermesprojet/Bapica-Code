"""L'aperçu montre-t-il la poutre que le DXF contient, ou une autre ?

LE DEFAUT QUE CE MODULE FERME
-------------------------------
Choisir un ferraillage sans le voir oblige a telecharger, ouvrir un logiciel
de CAO, regarder, revenir, corriger. Un apercu supprime ce va-et-vient — a une
condition, et c'est toute la question: qu'il montre EXACTEMENT ce que le
fichier contiendra.

Un apercu ecrit a cote du generateur DXF est un second calcul de la meme
geometrie. Les deux concordent le jour ou on les ecrit, et divergent le jour ou
l'un des deux est corrige, sans que rien ne le signale. L'ingenieur valide
alors ce qu'il voit a l'ecran et telecharge autre chose.

Ce module verifie que les deux sortent du MEME modele gele: la section, les
barres, les cadres, l'enrobage et les mentions lues dans le SVG sont celles du
calcul conserve, et celles que le DXF servi porte.

CE QUE L'APERCU N'EST PAS
---------------------------
Un livrable. Rien n'est depose, aucune ligne n'est ecrite, aucune empreinte
n'est conservee — et c'est verifie ici, parce qu'un apercu qui laisserait des
octets dans le magasin creerait des orphelins que la politique de stockage
interdit de supprimer.

Lance par `db/test/livrable_validation.sh`, qui pose le decor complet.
"""
# Le nom d'une fixture importée reparaît en paramètre de chaque test qui la
# demande ; ruff y voit une redéfinition alors que c'est le mécanisme même de
# pytest. La levée est déclarée ici plutôt que répétée sur chaque signature.
# ruff: noqa: F811

from __future__ import annotations

import re

import ezdxf
import pytest

from .test_livrable_dxf import (
    FERRAILLAGE,
    FERRAILLAGE_INSUFFISANT,
    _creer_dxf,
)
from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    DECOR_PRESENT,
    _entete,
    _objets_du_magasin,
    _observer,
    calcul_exploratoire,
    calcul_strict,
    cle,
    client,
    jeton,
    projet,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/livrable_validation.sh, qui pose la base deployee, "
                "les adhesions, la racine d'autorite et le magasin d'objets."),
    ),
]


def _apercu(client, jeton, projet, calcul_id, ferraillage=None):
    return client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/preview",
        json={"calculation_id": calcul_id, "format": "dxf",
              "reinforcement": ferraillage or FERRAILLAGE},
        headers=_entete(jeton(ACTEUR_A)))


# ===========================================================================
# 1 — L'APERCU EXISTE, ET IL EST DU SVG
# ===========================================================================
def test_l_apercu_rend_du_svg(client, jeton, projet, calcul_strict):
    r = _apercu(client, jeton, projet, calcul_strict)

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.startswith("<svg ")
    assert r.text.rstrip().endswith("</svg>")


def test_l_apercu_ne_depose_rien_et_n_enregistre_rien(
        client, jeton, projet, calcul_strict):
    """UN APERCU QUI LAISSERAIT DES OCTETS CREERAIT DES ORPHELINS.

    La politique du magasin (`docs/STOCKAGE.md` §5) interdit au produit toute
    suppression: un objet depose pour un simple coup d'oeil serait DEFINITIF.
    """
    lignes = _observer("select count(*) from deliverables")[0][0]
    prefixe = f"{projet['organization_id']}/{projet['project_id']}/"
    objets = _objets_du_magasin(prefixe)

    assert _apercu(client, jeton, projet, calcul_strict).status_code == 200

    assert _observer("select count(*) from deliverables")[0][0] == lignes
    assert _objets_du_magasin(prefixe) == objets


def test_l_apercu_se_declare_non_contractuel(client, jeton, projet, calcul_strict):
    """UNE IMAGE SE COPIE ET SE TRANSMET SANS SON BOUTON."""
    svg = _apercu(client, jeton, projet, calcul_strict).text
    assert "NON CONTRACTUEL" in svg
    assert "DXF" in svg


# ===========================================================================
# 2 — LE CAS DECISIF: LE SVG ET LE DXF DECRIVENT LA MEME POUTRE
# ===========================================================================
def _etendue_du_dxf(octets: bytes) -> tuple[float, float]:
    """Largeur et hauteur du contour de coffrage, relues dans le DXF servi."""
    import io

    doc = ezdxf.read(io.StringIO(octets.decode("utf-8")))
    contours = [e for e in doc.modelspace()
                if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "COFFRAGE"]
    assert len(contours) == 1, "un seul contour de coffrage"
    pts = [(p[0], p[1]) for p in contours[0].get_points("xy")]
    return (max(x for x, _ in pts) - min(x for x, _ in pts),
            max(y for _, y in pts) - min(y for _, y in pts))


def test_l_apercu_et_le_dxf_decrivent_la_section_du_calcul_conserve(
        client, jeton, projet, calcul_strict):
    """SI LES DEUX GEOMETRIES DIVERGENT, CE CAS TOMBE.

    Trois sources sont confrontees, et pas deux: la section GELEE en base, le
    contour mesure dans le DXF telecharge, et ce que le SVG affiche. Comparer
    seulement le SVG au DXF laisserait passer deux rendus faux de la meme
    facon; c'est le calcul conserve qui arbitre.
    """
    section = _observer(
        "select request -> 'section' from calculations where id = %s",
        (calcul_strict,))[0][0]
    b = float(section["b"]["value"])
    h = float(section["h"]["value"])

    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()
    telecharge = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{livrable['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A)))
    assert telecharge.status_code == 200, telecharge.text
    largeur, hauteur = _etendue_du_dxf(telecharge.content)
    assert abs(largeur - b) < 0.1 and abs(hauteur - h) < 0.1

    svg = _apercu(client, jeton, projet, calcul_strict).text
    # LA SECTION EST ECRITE EN TOUTES LETTRES DANS L'APERCU, et elle doit dire
    # les memes millimetres que le contour du DXF.
    assert f"{b:g} x {h:g} mm" in svg
    # ET LES COTES PORTENT CES VALEURS-LA.
    valeurs = set(re.findall(r">(\d+)</text>", svg))
    assert f"{b:g}" in valeurs, (b, sorted(valeurs))
    assert f"{h:g}" in valeurs, (h, sorted(valeurs))


def test_l_apercu_porte_le_ferraillage_demande(client, jeton, projet, calcul_strict):
    """LES BARRES DE L'APERCU SONT CELLES DU CORPS, PAS D'UN EXEMPLE."""
    lit = FERRAILLAGE["bottom"][0]
    svg = _apercu(client, jeton, projet, calcul_strict).text

    assert f"{lit['count']} HA{lit['diameter']:g}" in svg
    assert f"cadre HA{FERRAILLAGE['link_diameter']:g}" in svg
    assert f"e = {FERRAILLAGE['link_spacing']:g} mm" in svg
    assert f"enrobage {FERRAILLAGE['cover']:g} mm" in svg
    # Une barre dessinee par barre demandee, sur le calque des armatures.
    assert svg.count('class="FERR-PRINCIPAL" cx=') == lit["count"]


def test_deux_apercus_du_meme_choix_sont_identiques(
        client, jeton, projet, calcul_strict):
    """MEME EXIGENCE QUE POUR LE DXF, ET POUR LA MEME RAISON.

    Un apercu qui changerait d'un appel a l'autre rendrait illusoire tout
    controle de correspondance avec le fichier.
    """
    a = _apercu(client, jeton, projet, calcul_strict).text
    b = _apercu(client, jeton, projet, calcul_strict).text
    assert a == b


# ===========================================================================
# 3 — CE QUE L'APERCU REFUSE, IL LE REFUSE COMME LE FICHIER
# ===========================================================================
def test_un_ferraillage_insuffisant_n_a_pas_d_apercu(
        client, jeton, projet, calcul_strict):
    """UN DESSIN FAUX RESSEMBLE TRAIT POUR TRAIT A UN DESSIN JUSTE.

    A l'ecran comme sur le papier. Le refus doit donc etre le meme des deux
    cotes, sinon l'apercu devient la porte par laquelle on regarde ce que le
    produit refuse de livrer.
    """
    r = _apercu(client, jeton, projet, calcul_strict, FERRAILLAGE_INSUFFISANT)

    assert r.status_code == 422, r.text
    detail = r.text.lower()
    assert "ferraillage" in detail or "verifie" in detail


def test_l_apercu_exploratoire_porte_le_filigrane(
        client, jeton, projet, calcul_exploratoire):
    """INTERDICTION N° 8, SUR L'APERCU AUSSI."""
    svg = _apercu(client, jeton, projet, calcul_exploratoire).text
    assert "NON SIGNABLE" in svg


def test_l_apercu_refuse_une_geometrie_venue_du_corps(
        client, jeton, projet, calcul_strict):
    """LA SECTION NE S'ENVOIE PAS, ELLE SE RELIT.

    `Strict` refuse les champs supplementaires: un appelant qui tenterait de
    dicter la poutre a dessiner recoit 422 plutot que de croire que sa valeur
    a servi.
    """
    for champ in ("b", "h", "section", "M_Ed", "materials"):
        r = client.post(
            f"/v1/projects/{projet['project_id']}/deliverables/preview",
            json={"calculation_id": calcul_strict, "format": "dxf",
                  "reinforcement": FERRAILLAGE, champ: 9999},
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 422, (champ, r.status_code, r.text)
