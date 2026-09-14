"""Le DXF est-il un livrable de projet, ou un téléchargement qui s'évapore ?

LE DEFAUT PRODUIT QUE CE MODULE FERME
---------------------------------------
`POST /v1/calculations/ec2/beam-section.dxf` rend un DXF correct — vérifié
avant d'être dessiné, refusant si le ferraillage ne passe pas. Et il est
**sans état**. Rien n'est déposé, rien n'est enregistré, rien n'est rattaché
au projet.

Concrètement, pour un bureau d'études :

* le plan disparaît au rechargement de la page ;
* il n'apparaît ni dans la liste des livrables, ni dans le dossier de revue ;
* aucune empreinte n'est conservée, donc **personne ne peut dire dix ans plus
  tard quel plan a été remis** ;
* et le relecteur qui atteste une note de calcul n'atteste rien du dessin.

La note de calcul, elle, est un livrable depuis le lot précédent : déposée,
relue, empreinte enregistrée, téléchargeable après redémarrage. Le DXF doit
l'être aussi, **par le même chemin** — sinon deux documents du même projet
obéissent à deux régimes de preuve différents.

CE QUE LE NAVIGATEUR PEUT ENVOYER, ET CE QU'IL NE PEUT PAS
------------------------------------------------------------
Il envoie **le choix des barres** — nombre, diamètre, enrobage, cadres. C'est
une décision d'ingénieur, pas une valeur dérivable : `As_required` dit combien
d'acier il faut, jamais comment le disposer.

Il n'envoie **ni la section, ni les matériaux, ni l'effort, ni le référentiel
normatif** : les quatre sont relus dans le calcul gelé. Un appelant ne peut
donc pas faire dessiner une poutre qui n'a pas été vérifiée — c'est exactement
le défaut mesuré le 30/08 sur l'endpoint sans état, et il ne doit pas
reparaître par une autre porte.

Lancé par `db/test/livrable_validation.sh`, qui pose le décor complet.
"""
# Le nom d'une fixture importée reparaît en paramètre de chaque test qui la
# demande ; ruff y voit une redéfinition alors que c'est le mécanisme même de
# pytest. La levée est déclarée ici plutôt que répétée sur chaque signature.
# ruff: noqa: F811

from __future__ import annotations

import hashlib
import io
import json

import pytest

from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    DECOR_PRESENT,
    DSN,
    DSN_OBS,
    ORG_A,
    _brouillon,
    _entete,
    _localisation,
    _objets_du_magasin,
    _observer,
    _requete_de_calcul,
    calcul_exploratoire,
    calcul_strict,
    cle,
    client,
    client_neuf,
    jeton,
    projet,
)

#: LE MEME PORTILLON QUE `test_livrables`, ET LA MEME CONDITION.
#:
#: Ce module partage son décor : sans les DSN, le magasin et les six adhésions,
#: ses fixtures échouent. La condition est **importée**, jamais recopiée — deux
#: conditions écrites deux fois finissent par diverger, et le jour où elles
#: divergent, un module se met à ÉCHOUER là où l'autre s'ignore.
#:
#: `skipif` et non `importorskip`: un saut à l'import empêche la COLLECTE, et
#: `run_tests.sh` compare collectés et exécutés précisément pour repérer les cas
#: qui disparaissent.
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/livrable_validation.sh, qui pose la base deployee, "
                "les adhesions, la racine d'autorite et le magasin d'objets."),
    ),
]

#: LE FERRAILLAGE QUI VERIFIE la poutre du décor (300 x 500, d = 450,
#: C30/37, B500B, M_Ed = 180 kN·m). Il n'est pas déduit du calcul : c'est le
#: choix de l'ingénieur, et c'est précisément ce que le corps porte.
FERRAILLAGE = {
    "cover": 30.0,
    "link_diameter": 8.0,
    "link_spacing": 200.0,
    "bottom": [{"count": 4, "diameter": 20.0, "mark": "A1"}],
}

#: UN FERRAILLAGE MANIFESTEMENT INSUFFISANT pour la même poutre.
FERRAILLAGE_INSUFFISANT = {
    "cover": 30.0,
    "link_diameter": 8.0,
    "link_spacing": 200.0,
    "bottom": [{"count": 2, "diameter": 8.0, "mark": "A1"}],
}


def _creer_dxf(client, jeton, projet, calcul_id, ferraillage=None):
    return client.post(
        f"/v1/projects/{projet['project_id']}/deliverables",
        json={"calculation_id": calcul_id, "format": "dxf",
              "reinforcement": ferraillage or FERRAILLAGE},
        headers=_entete(jeton(ACTEUR_A)))


# ===========================================================================
# 1 — LE DXF EXISTE COMME LIVRABLE, ET IL EST ENREGISTRE
# ===========================================================================
def test_un_dxf_devient_un_livrable_du_projet(
        client, jeton, projet, calcul_strict):
    """CE QUE LA LIGNE DOIT PORTER, ET QUI FAIT D'UN FICHIER UNE PIECE.

    Genre, type de media, empreinte, taille, build du moteur, identite
    d'execution, date. Sans eux, un DXF est un fichier que quelqu'un a
    telecharge un jour — pas un document qu'on peut rattacher a un calcul dix
    ans plus tard.
    """
    r = _creer_dxf(client, jeton, projet, calcul_strict)
    assert r.status_code == 201, r.text
    livrable = r.json()

    assert livrable["kind"] == "rebar_drawing_dxf"
    assert livrable["media_type"] == "image/vnd.dxf"
    assert livrable["filename"].endswith(".dxf")
    assert livrable["calculation_id"] == calcul_strict
    assert livrable["state"] == "draft"

    _, chemin, sha, taille = _localisation(livrable["deliverable_id"])
    assert chemin.endswith(".dxf")
    assert sha in chemin, "le chemin doit deriver de l'empreinte"
    assert taille > 0

    # LES IDENTITES VIENNENT DU CALCUL GELE, PAS DU CORPS.
    ligne = _observer(
        "select engine_version, engine_build_sha, execution_identity, "
        "       inputs_hash, ndp_as_of, generated_at "
        "  from deliverables where id = %s", (livrable["deliverable_id"],))[0]
    # `deliverables.engine_version` est un texte fige; `calculations` porte la
    # cle etrangere `engine_version_id`. La jointure est donc la seule facon de
    # confronter les deux, et c'est bien la confrontation qui compte ici.
    calc = _observer(
        "select v.version, c.engine_build_sha, c.execution_identity, "
        "       c.inputs_hash, c.ndp_as_of "
        "  from calculations c "
        "  join engine_versions v on v.id = c.engine_version_id "
        " where c.id = %s", (calcul_strict,))[0]
    assert ligne[:5] == calc, (
        "le livrable ne porte pas le contexte gele du calcul dont il est tire")
    assert ligne[5] is not None


def test_les_octets_dxf_telecharges_portent_l_empreinte_enregistree(
        client, jeton, projet, calcul_strict):
    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()
    _, _, sha, taille = _localisation(livrable["deliverable_id"])

    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{livrable['deliverable_id']}/download",
                   headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/vnd.dxf"
    assert hashlib.sha256(r.content).hexdigest() == sha
    assert len(r.content) == taille
    assert ".dxf" in r.headers["content-disposition"]


def test_le_dxf_revient_apres_un_rechargement_complet(
        client, client_neuf, jeton, projet, calcul_strict):
    """F5 N'EST PAS UN SECOND APPEL DANS LE MEME PROCESSUS.

    `client_neuf` reconstruit l'application entiere: nouvelle fabrique de
    connexion, nouveau magasin, aucun cache. C'est ce qui distingue « les
    octets sont conserves » de « ils sont encore en memoire ».
    """
    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()
    _, _, sha, _ = _localisation(livrable["deliverable_id"])

    r = client_neuf.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                        f"{livrable['deliverable_id']}/download",
                        headers=_entete(jeton(ACTEUR_A)))

    assert r.status_code == 200, r.text
    assert hashlib.sha256(r.content).hexdigest() == sha


def test_le_dxf_apparait_dans_la_liste_des_livrables(
        client, jeton, projet, calcul_strict):
    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()

    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    par_id = {d["deliverable_id"]: d for d in r.json()["deliverables"]}
    assert livrable["deliverable_id"] in par_id
    assert par_id[livrable["deliverable_id"]]["kind"] == "rebar_drawing_dxf"


def test_le_dossier_de_revue_d_un_dxf_porte_le_dessin(
        client, jeton, projet, calcul_strict):
    """UN RELECTEUR QUI ATTESTE DOIT VOIR CE QU'IL ATTESTE."""
    import zipfile

    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()
    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{livrable['deliverable_id']}/review-bundle",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        manifeste = json.loads(archive.read("manifeste.json"))
        octets = archive.read(f"documents/{livrable['filename']}")

    _, _, sha, _ = _localisation(livrable["deliverable_id"])
    assert hashlib.sha256(octets).hexdigest() == sha
    assert manifeste["deliverable"]["kind"] == "rebar_drawing_dxf"
    # LE GENRE PRESENTE N'EST JAMAIS DECLARE ABSENT.
    assert "rebar_drawing_dxf" not in manifeste["artifacts_not_produced"]


# ===========================================================================
# 2 — LE CAS DECISIF : LA SECTION DESSINEE EST LA SECTION CALCULEE
# ===========================================================================
def test_la_section_dessinee_est_exactement_la_section_calculee(
        client, jeton, projet, calcul_strict):
    """LE CAS QUI ECHOUE SI LA GEOMETRIE VENAIT D'AILLEURS.

    On relit le DXF servi avec `ezdxf` — le meme lecteur que celui qui l'a
    ecrit, mais en sens inverse — et on mesure le contour de coffrage
    reellement trace. Il doit valoir la section du calcul GELE, au dixieme de
    millimetre.

    C'ETAIT LE DEFAUT DU 30/08, PAR UNE AUTRE PORTE. L'interface envoyait une
    section codee en dur a l'endpoint de dessin, qui la dessinait
    correctement: l'ingenieur recevait le plan d'une poutre jamais verifiee,
    portant la mention obligatoire et son propre repere. Si un jour la
    geometrie du livrable revenait a etre lue dans le corps de la requete, ce
    cas rougirait.
    """
    ezdxf = pytest.importorskip("ezdxf")

    livrable = _creer_dxf(client, jeton, projet, calcul_strict).json()
    r = client.get(f"/v1/projects/{projet['project_id']}/deliverables/"
                   f"{livrable['deliverable_id']}/download",
                   headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text

    doc = ezdxf.read(io.StringIO(r.content.decode("utf-8")))
    assert doc.dxfversion == "AC1032", "le DXF n'est pas en R2018"

    # LE CONTOUR DE COFFRAGE, mesure sur les entites du calque.
    points: list[tuple[float, float]] = []
    for entite in doc.modelspace().query('*[layer=="COFFRAGE"]'):
        if entite.dxftype() == "LWPOLYLINE":
            points.extend((p[0], p[1]) for p in entite.get_points())
        elif entite.dxftype() == "LINE":
            points.append((entite.dxf.start.x, entite.dxf.start.y))
            points.append((entite.dxf.end.x, entite.dxf.end.y))
    assert points, "aucune entite sur le calque COFFRAGE"

    largeur = max(x for x, _ in points) - min(x for x, _ in points)
    hauteur = max(y for _, y in points) - min(y for _, y in points)

    requete = _observer("select request from calculations where id = %s",
                        (calcul_strict,))[0][0]
    b = float(requete["section"]["b"]["value"])
    h = float(requete["section"]["h"]["value"])

    assert abs(largeur - b) < 0.1, (
        f"le dessin fait {largeur} mm de large, le calcul {b} mm")
    assert abs(hauteur - h) < 0.1, (
        f"le dessin fait {hauteur} mm de haut, le calcul {h} mm")


def test_le_corps_ne_peut_pas_nommer_une_geometrie(
        client, jeton, projet, calcul_strict):
    """LA SECTION NE TRAVERSE PAS DEPUIS LE NAVIGATEUR.

    `Strict` refuse les champs supplementaires: un corps qui porterait une
    section, des materiaux ou un effort recoit 422. La geometrie n'a donc
    aucun chemin pour entrer autrement que par le calcul gele.
    """
    for champ, valeur in (
        ("section", {"b": {"value": 999.0, "unit": "mm"},
                     "h": {"value": 999.0, "unit": "mm"},
                     "d": {"value": 900.0, "unit": "mm"}}),
        ("materials", {"concrete_grade": "C50/60", "steel_grade": "B500B"}),
        ("M_Ed", {"value": 1.0, "unit": "kN*m"}),
        ("sha256", "0" * 64),
        ("execution_identity", "f" * 64),
        ("engine_build_sha", "FICTIF-autre"),
    ):
        r = client.post(
            f"/v1/projects/{projet['project_id']}/deliverables",
            json={"calculation_id": calcul_strict, "format": "dxf",
                  "reinforcement": FERRAILLAGE, champ: valeur},
            headers=_entete(jeton(ACTEUR_A)))
        assert r.status_code == 422, (champ, r.status_code, r.text)


# ===========================================================================
# 3 — UN FERRAILLAGE INSUFFISANT NE PRODUIT AUCUN FICHIER
# ===========================================================================
def test_un_ferraillage_insuffisant_ne_produit_ni_ligne_ni_octet(
        client, jeton, projet, calcul_strict):
    """UN DESSIN QUI ECHOUE A SA PROPRE VERIFICATION A L'AIR D'UN DESSIN VALIDE.

    Entre les mains de celui qui l'ouvre, rien ne distingue un plan verifie
    d'un plan qui ne l'est pas. Le refus doit donc etre TOTAL: pas de ligne,
    et pas un octet dans le magasin.
    """
    avant_lignes = _observer("select count(*) from deliverables")[0][0]
    prefixe = f"{projet['organization_id']}/{projet['project_id']}/"
    avant_objets = _objets_du_magasin(prefixe)

    r = _creer_dxf(client, jeton, projet, calcul_strict,
                   FERRAILLAGE_INSUFFISANT)

    assert r.status_code == 422, r.text
    detail = json.dumps(r.json()).lower()
    assert "ferraillage" in detail or "verifie" in detail

    assert _observer("select count(*) from deliverables")[0][0] == avant_lignes
    assert _objets_du_magasin(prefixe) == avant_objets, (
        "un ferraillage refuse a tout de meme fait ecrire dans le magasin")


def test_un_calcul_refuse_ne_produit_aucun_dxf(client, jeton, projet):
    """LE MOTEUR A REFUSE: il n'y a rien a dessiner.

    UN REFUS NE REVIENT PAS DANS LA REPONSE, IL SE LIT DANS L'HISTORIQUE. La
    route de calcul rend 422 — le moteur n'a pas conclu — **et** enregistre la
    ligne avec `status = 'refused'`. C'est cette ligne-la qu'un appelant peut
    ensuite designer pour en tirer un dessin, donc c'est elle qu'il faut viser
    ici. Attendre un 201 portant `status == "refused"` etait une erreur sur le
    contrat de la route, pas un defaut du produit.
    """
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json={**_requete_de_calcul(strict=True),
              "M_Ed": {"value": 1.0e9, "unit": "kN*m"}},
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text

    refuses = _observer(
        "select id from calculations "
        " where project_id = %s and status = 'refused' "
        " order by created_at desc limit 1", (projet["project_id"],))
    assert refuses, "le refus du moteur n'a pas ete enregistre comme refus"
    refuse = str(refuses[0][0])

    avant = _observer("select count(*) from deliverables")[0][0]
    prefixe = f"{projet['organization_id']}/{projet['project_id']}/"
    objets = _objets_du_magasin(prefixe)

    r = _creer_dxf(client, jeton, projet, refuse)
    assert r.status_code == 422, r.text
    assert "refuse par le moteur" in json.dumps(r.json()).lower()

    # NI LIGNE, NI OCTET. Un dessin depose puis non enregistre serait un
    # orphelin dans le magasin: le refus doit tomber avant le depot.
    assert _observer("select count(*) from deliverables")[0][0] == avant
    assert _objets_du_magasin(prefixe) == objets


# ===========================================================================
# 4 — L'EXPLORATOIRE EST DESSINABLE, MAIS JAMAIS SIGNABLE
# ===========================================================================
def test_un_dxf_exploratoire_porte_le_filigrane(
        client, jeton, projet, calcul_exploratoire):
    """INTERDICTION N° 6 ET N° 8, SUR LE DESSIN AUSSI.

    Un calcul exploratoire peut donner un dessin — c'est utile pour avancer —
    mais il ne doit jamais avoir l'air d'une piece signable.
    """
    r = _creer_dxf(client, jeton, projet, calcul_exploratoire)
    assert r.status_code == 201, r.text
    livrable = r.json()

    assert livrable["mention"], "un dessin exploratoire sans filigrane"
    assert "NON SIGNABLE" in livrable["mention"]

    telecharge = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{livrable['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A)))
    assert telecharge.status_code == 200
    # LA MENTION EST DANS LE FICHIER, pas seulement dans la ligne.
    assert b"NON SIGNABLE" in telecharge.content


def test_deux_dxf_du_meme_calcul_et_du_meme_ferraillage_sont_identiques(
        client, jeton, projet, calcul_strict):
    """L'ADRESSAGE PAR CONTENU EXIGE UN DESSIN REPRODUCTIBLE.

    `ezdxf` est deterministe et les calques sont declares dans un ordre fixe;
    si un horodatage ou un identifiant aleatoire entrait dans le fichier, deux
    dessins du meme calcul occuperaient deux cles pour un seul document.
    """
    un = _creer_dxf(client, jeton, projet, calcul_strict).json()
    deux = _creer_dxf(client, jeton, projet, calcul_strict).json()

    assert un["deliverable_id"] != deux["deliverable_id"]
    _, chemin_un, sha_un, _ = _localisation(un["deliverable_id"])
    _, chemin_deux, sha_deux, _ = _localisation(deux["deliverable_id"])
    assert sha_un == sha_deux, "le DXF n'est pas reproductible"
    assert chemin_un == chemin_deux
