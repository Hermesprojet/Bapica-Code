"""Attester la note de calcul laissait croire que le plan l'était aussi.

LE DEFAUT QUE CE MODULE FERME
-------------------------------
Un ingenieur atteste UN livrable: ces octets-la, cette empreinte-la. Le
dossier de revue qu'il telecharge ne parlait que de celui-la — et ne disait
rien des autres. Or un meme calcul porte maintenant plusieurs artefacts: la
note HTML, la note PDF, le plan DXF.

Consequence pratique, et elle est grave. Le dossier de revue d'une note PDF
attestee ne mentionnait pas qu'un plan DXF existait pour le meme calcul. Qui
recevait ce dossier pouvait en conclure que l'etude entiere avait ete relue,
alors que l'attestation ne couvrait qu'une piece. **Le silence sur les autres
artefacts se lit comme leur approbation.**

CE QUE LE MANIFESTE DOIT DIRE
-------------------------------
1. L'INSTANTANE du dossier au moment ou il est constitue: tous les artefacts
   du meme calcul, avec leur genre, leur nom, leur etat et leur SHA-256.
2. Ce que l'attestation COUVRE — exactement un artefact, nomme par son
   empreinte.
3. Ce qu'elle NE COUVRE PAS, nomme aussi. Ne pas nommer revient a laisser
   supposer.

Lance par `db/test/livrable_validation.sh`, qui pose le decor complet.
"""
# Le nom d'une fixture importée reparaît en paramètre de chaque test qui la
# demande ; ruff y voit une redéfinition alors que c'est le mécanisme même de
# pytest. La levée est déclarée ici plutôt que répétée sur chaque signature.
# ruff: noqa: F811

from __future__ import annotations

import io
import json
import zipfile

import pytest

from .test_livrable_dxf import _creer_dxf  # noqa: F401 — même décor
from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    ACTEUR_V,
    DECOR_PRESENT,
    _brouillon_pdf,
    _entete,
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


def _manifeste_du_dossier(client, jeton, projet, deliverable_id) -> dict:
    r = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{deliverable_id}/review-bundle",
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        return json.loads(archive.read("manifeste.json"))


# ===========================================================================
# 1 — L'INSTANTANE: TOUT CE QUI EXISTE, AVEC SON EMPREINTE
# ===========================================================================
def test_le_dossier_nomme_les_autres_artefacts_du_meme_calcul(
        client, jeton, projet, calcul_strict):
    """LE SILENCE SUR UN ARTEFACT SE LIT COMME SON APPROBATION.

    Deux documents sont produits depuis le meme calcul: une note PDF et un
    plan DXF. Le dossier de revue de la note doit nommer le plan — son genre,
    son nom, son etat et son empreinte — sans quoi celui qui le recoit peut
    croire que l'etude entiere a ete relue.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    plan = _creer_dxf(client, jeton, projet, calcul_strict).json()

    m = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])

    instantane = m["review_snapshot"]
    par_id = {a["deliverable_id"]: a for a in instantane["artifacts"]}
    assert note["deliverable_id"] in par_id
    assert plan["deliverable_id"] in par_id, (
        "le plan DXF du meme calcul est absent de l'instantane: le dossier "
        "laisse croire qu'il n'existe pas")

    dessin = par_id[plan["deliverable_id"]]
    assert dessin["kind"] == "rebar_drawing_dxf"
    assert dessin["sha256"] == plan["sha256"]
    assert dessin["filename"] == plan["filename"]
    assert dessin["state"] == plan["state"]
    assert instantane["calculation_id"] == calcul_strict
    # L'INSTANTANE SE DATE PAR SES PROPRES ARTEFACTS, jamais par l'horloge:
    # une horloge rendrait le dossier non deterministe.
    assert instantane["artifacts_as_of"] == max(
        a["generated_at"] for a in [note, plan])


def test_l_instantane_ne_liste_pas_les_artefacts_d_un_autre_calcul(
        client, jeton, projet, calcul_strict):
    """UN INSTANTANE QUI RATISSE TROP EST AUSSI FAUX QU'UN QUI OUBLIE.

    Le projet porte d'autres calculs et d'autres livrables. Les melanger
    ferait dire au dossier que l'attestation d'une poutre laisse de cote des
    documents qui ne la concernent pas.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    m = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])

    for artefact in m["review_snapshot"]["artifacts"]:
        assert artefact["calculation_id"] == calcul_strict


# ===========================================================================
# 2 — CE QUE L'ATTESTATION COUVRE, ET CE QU'ELLE NE COUVRE PAS
# ===========================================================================
def test_l_attestation_nomme_ce_qu_elle_couvre_et_ce_qu_elle_ne_couvre_pas(
        client, jeton, projet, calcul_strict):
    """VALIDER LE PDF NE VALIDE PAS LE DXF, ET LE DOSSIER DOIT L'ECRIRE."""
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    plan = _creer_dxf(client, jeton, projet, calcul_strict).json()

    base = f"/v1/projects/{projet['project_id']}/deliverables/"
    r = client.post(f"{base}{note['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    r = client.post(
        f"{base}{note['deliverable_id']}/validation",
        json={"statement": "FICTIF — relu et verifie pour ce test.",
              "reservations": "FICTIF — aucune."},
        headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text

    m = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])
    attestation = m["attestation"]

    assert attestation["validation_id"], "le decor doit avoir atteste"
    # CE QU'ELLE COUVRE: un artefact, nomme par son empreinte.
    couvre = attestation["covers"]
    assert couvre["deliverable_id"] == note["deliverable_id"]
    assert couvre["sha256"] == note["sha256"]

    # CE QU'ELLE NE COUVRE PAS: nomme aussi, et pas seulement deduit.
    non_couverts = {a["deliverable_id"] for a in attestation["does_not_cover"]}
    assert plan["deliverable_id"] in non_couverts, (
        "le plan DXF n'est pas couvert par cette attestation, et le dossier "
        "doit le dire plutot que de le taire")
    assert note["deliverable_id"] not in non_couverts

    assert attestation["is_qualified_electronic_signature"] is False


def test_un_brouillon_non_atteste_ne_couvre_rien(
        client, jeton, projet, calcul_strict):
    """PAS D'ATTESTATION, PAS DE COUVERTURE — et des champs a `null`.

    Des champs absents se liraient moins clairement que des champs vides: le
    lecteur ne saurait pas si la question a ete posee.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    m = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])

    assert m["attestation"]["validation_id"] is None
    assert m["attestation"]["covers"] is None
    assert m["attestation"]["does_not_cover"] == []


def test_le_dossier_reste_deterministe_avec_l_instantane(
        client, jeton, projet, calcul_strict):
    """UN DOSSIER DONT L'EMPREINTE BOUGE NE PEUT RIEN ATTESTER.

    RIEN N'EST EXCLU DE LA COMPARAISON, et c'est un correctif. La premiere
    version de l'instantane portait l'heure de l'horloge: deux telechargements
    separes par une seconde donnaient des octets differents, et
    `test_deux_telechargements_du_dossier_rendent_les_memes_octets` est tombe.
    L'instantane se date desormais par le plus recent de ses propres
    artefacts — une valeur qui vient des donnees, donc stable.
    """
    note = _brouillon_pdf(client, jeton, projet, calcul_strict)
    a = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])
    b = _manifeste_du_dossier(client, jeton, projet, note["deliverable_id"])

    assert a == b
