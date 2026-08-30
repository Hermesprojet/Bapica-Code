"""L'état du référentiel, tel que le produit le rend.

CE QUE CES CAS PROTÈGENT
-------------------------
Le compte. Un total écrit à la main quelque part se désynchronise le jour où
une annexe est transcrite, et personne ne s'en aperçoit — un chiffre faux se
lit exactement comme un chiffre juste.
"""
from __future__ import annotations

import pytest

PAYS = ("BE", "FR", "ES", "DE")


def test_les_quatre_pays_ont_un_referentiel(client):
    r = client.get("/v1/ndp/countries")
    assert r.status_code == 200
    assert set(PAYS) <= set(r.json()["countries"])


@pytest.mark.parametrize("pays", PAYS)
def test_aucun_pays_ne_peut_produire_de_note_signable_aujourd_hui(client, pays):
    """Le fait central du produit, et il doit être lisible sans calculer.

    Zéro valeur confirmée veut dire qu'aucune note signable ne peut sortir de
    ce pays, quel que soit le projet. Le jour où ce cas tombe, c'est que le
    référentiel a réellement avancé — et il faudra le constater, pas le
    contourner.
    """
    corps = client.get(f"/v1/ndp/{pays}").json()
    assert corps["signable_possible"] is False
    assert corps["referentiel"]["confirmed"] == 0


#: Totaux MESURES le 30/08/2026, paramètres en vigueur à la date du jour.
#: Écrits en dur volontairement: si le référentiel grandit, ces nombres
#: changent, et c'est **exactement** le moment où un humain doit le voir.
#: Un test qui recalculerait le total par la même boucle que la route ne
#: pourrait constater aucune dérive — il vérifierait qu'une fonction est
#: égale à elle-même.
TOTAUX = {"BE": 29, "FR": 29, "ES": 29, "DE": 29}


@pytest.mark.parametrize("pays", PAYS)
def test_le_total_est_celui_qu_on_a_mesure(client, pays):
    assert client.get(f"/v1/ndp/{pays}").json()["referentiel"]["total"] == TOTAUX[pays]


@pytest.mark.parametrize("pays", PAYS)
def test_les_statuts_se_totalisent_sans_reste(client, pays):
    """Un paramètre est dans un état et un seul: la somme doit retomber juste."""
    comptes = client.get(f"/v1/ndp/{pays}").json()["referentiel"]
    total = comptes.pop("total")
    assert sum(comptes.values()) == total


def test_le_mode_strict_bloque_et_le_dit(client):
    corps = client.get("/v1/ndp/BE", params={"strict": "true"}).json()
    assert corps["strict"] is True
    assert corps["ok"] is False
    assert corps["blocking"], "le mode strict doit nommer ce qui bloque"
    # Chaque blocage nomme sa clause et son annexe: c'est ce qui rend la liste
    # actionnable plutot que decorative.
    for b in corps["blocking"]:
        assert b["key"] and b["reason"]


def test_le_mode_exploratoire_ne_debloque_pas_tout(client):
    """Une valeur obsolète ou non représentable bloque dans TOUS les modes.

    Confondre « exploratoire » et « sans garde-fou » ferait passer une valeur
    connue fausse dans un pré-dimensionnement.
    """
    strict = client.get("/v1/ndp/BE", params={"strict": "true"}).json()
    large = client.get("/v1/ndp/BE", params={"strict": "false"}).json()
    assert large["strict"] is False
    raisons = {b["reason"] for b in large["blocking"]}
    assert "pending_verification" not in raisons
    assert len(large["blocking"]) <= len(strict["blocking"])


def test_le_defaut_est_strict(client):
    """`strict_ndp` vaut vrai par defaut partout, y compris ici."""
    assert client.get("/v1/ndp/BE").json()["strict"] is True


def test_un_pays_inconnu_est_refuse_sans_le_faire_passer_pour_libre(client):
    """Un pays absent n'est pas un pays sans exigences."""
    r = client.get("/v1/ndp/ZZ")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] == "COUNTRY_NOT_IN_REFERENTIAL"
    assert set(PAYS) <= set(detail["countries"])


def test_la_date_de_reference_est_acceptee(client):
    """Une etude reste reproductible: l'edition en vigueur depend de la date."""
    r = client.get("/v1/ndp/BE", params={"as_of": "2020-01-01"})
    assert r.status_code == 200
    assert r.json()["as_of"] == "2020-01-01"


def test_la_route_ne_demande_aucune_identite(client):
    """Le referentiel national n'est pas une donnee de locataire.

    Une confirmation belge vaut pour toutes les etudes belges: exiger un jeton
    ici laisserait croire que la reponse depend de qui demande.
    """
    assert client.get("/v1/ndp/BE").status_code == 200
