"""Qui a le droit de faire quoi, et ce que le produit laissait passer.

CE QUE CE MODULE ÉPROUVE
-------------------------
La matrice d'autorisation, **rôle par rôle**, sur le chemin produit réel :

===========================  ==========================================
membre actif ``viewer``      lecture seulement
membre actif ``owner``,      création de brouillon, révision, soumission
``admin``, ``engineer``
membre actif                 retour motivé, attestation, émission
``validating_engineer``
membre **désactivé**         aucun accès métier, pas même en lecture
autre organisation           rien d'exploitable
===========================  ==========================================

CE QU'ELLE N'EST PAS : une préférence d'écran. Chaque ligne est éprouvée par
un appel HTTP réel **et** par un appel direct à la primitive, parce qu'une
règle qui ne vit que dans FastAPI n'existe pas pour qui atteint la base.

LES CINQ DÉFAUTS QUE CE MODULE A RÉVÉLÉS
------------------------------------------
Mesurés sur les octets de ``950259c``, par le chemin produit :

1. **``is_active`` n'était vérifié nulle part** sauf dans la primitive
   d'attestation. Ni ``project_actor_is_member``, ni
   ``project_actor_can_write``, ni ``project_workspace_list``, ni aucune des
   primitives de livrable ne le lisaient. Un accès révoqué gardait la lecture
   **et l'écriture**.

2. **Un simple ``engineer`` pouvait émettre** un livrable déjà attesté :
   ``project_deliverable_finalize`` ne contrôlait aucun rôle.

3. **Une mutation refusée répondait 200.** Les politiques RLS filtrent la
   ligne par leur clause ``using`` : l'``update`` touche alors ZÉRO ligne,
   sans erreur, et la primitive rendait quand même l'état visé. Un refus qui
   se présente comme un succès est pire qu'un refus.

4. **Les octets étaient déposés avant le contrôle d'autorisation.** Une
   tentative refusée laissait un objet dans le magasin, que plus aucune ligne
   ne référençait.

5. **Le ``viewer`` n'était bloqué que par accident** — par la clause ``with
   check`` d'une politique écrite pour autre chose — et le message ne disait
   pas pourquoi.

Lancé par ``db/test/livrable_validation.sh``, qui pose six adhésions aux rôles
distincts, un magasin d'objets réel, et fournit les DSN par l'environnement.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .test_livrables import (  # noqa: F401 — fixtures partagées, décor commun
    ACTEUR_A,
    ACTEUR_B,
    ACTEUR_D,
    ACTEUR_N,
    ACTEUR_V,
    ACTEUR_W,
    DSN,
    DSN_OBS,
    MAGASIN,
    ORG_A,
    _brouillon,
    _entete,
    _observer,
    _refus_de_la_primitive,
    brouillon,
    calcul_exploratoire,
    calcul_strict,
    cle,
    client,
    client_neuf,
    en_relecture,
    jeton,
    projet,
    pytestmark,
)


def _objets_du_magasin() -> set[str]:
    """Ce que le magasin contient, vu du système de fichiers.

    ON NE PASSE PAS PAR L'ABSTRACTION DU PRODUIT. Un test qui interrogerait le
    magasin par la même couche que la route prouverait que la couche est
    cohérente avec elle-même, pas qu'un octet existe.
    """
    racine = Path(MAGASIN)
    return {str(p.relative_to(racine)) for p in racine.rglob("*") if p.is_file()}


def _lignes_de_livrable() -> int:
    return _observer("select count(*) from deliverables")[0][0]


def _transitions() -> int:
    return _observer("select count(*) from deliverable_state_transitions")[0][0]


def _validations() -> int:
    return _observer("select count(*) from validations")[0][0]


def _etat(deliverable_id: str) -> str:
    return _observer("select state::text from deliverables where id = %s",
                     (deliverable_id,))[0][0]


def _mutations_de_livrable(projet_id: str, deliverable_id: str, calcul_id: str):
    """Toutes les routes qui MODIFIENT quelque chose, avec leur corps."""
    base = f"/v1/projects/{projet_id}/deliverables"
    return [
        ("creation", "post", base, {"calculation_id": calcul_id}),
        ("revision", "post", f"{base}/{deliverable_id}/revision",
         {"calculation_id": calcul_id}),
        ("soumission", "post", f"{base}/{deliverable_id}/review", None),
        ("retour", "post", f"{base}/{deliverable_id}/draft",
         {"reason": "FICTIF — motif de retour"}),
        ("attestation", "post", f"{base}/{deliverable_id}/validation",
         {"statement": "FICTIF — je valide."}),
        ("emission", "post", f"{base}/{deliverable_id}/final", None),
    ]


def _lectures_de_livrable(projet_id: str, deliverable_id: str):
    base = f"/v1/projects/{projet_id}/deliverables"
    return [
        ("liste", base),
        ("detail", f"{base}/{deliverable_id}"),
        ("telechargement", f"{base}/{deliverable_id}/download"),
        ("dossier", f"{base}/{deliverable_id}/review-bundle"),
    ]


def _appeler(client, methode, chemin, corps, entetes):
    if methode == "get":
        return client.get(chemin, headers=entetes)
    return client.post(chemin, json=corps, headers=entetes)


# ===========================================================================
# PREUVE 1 — UN « viewer » NE CRÉE, NE RÉVISE NI NE SOUMET
# ===========================================================================
def test_un_viewer_ne_mute_rien_et_le_refus_le_dit(
        client, jeton, projet, calcul_strict, brouillon):
    """LECTURE SEULEMENT, ET LE REFUS NOMME LE RÔLE.

    Le ``viewer`` était bloqué par accident — par la clause ``with check``
    d'une politique RLS écrite pour décider autre chose. Un blocage
    accidentel se perd à la première réécriture de cette politique, et son
    message ne dit pas ce qu'il faudrait pour agir.
    """
    avant_lignes = _lignes_de_livrable()
    avant_transitions = _transitions()
    avant_objets = _objets_du_magasin()
    etat_avant = _etat(brouillon["deliverable_id"])

    for quoi, methode, chemin, corps in _mutations_de_livrable(
            projet["project_id"], brouillon["deliverable_id"], calcul_strict):
        r = _appeler(client, methode, chemin, corps,
                     _entete(jeton(ACTEUR_W)))
        assert r.status_code in (401, 403, 422), (quoi, r.status_code, r.text)
        assert "viewer" in json.dumps(r.json()), (
            f"{quoi}: le refus ne nomme pas le role — {r.text}")

    # RIEN N'A BOUGE: ni ligne, ni transition, ni etat, ni objet.
    assert _lignes_de_livrable() == avant_lignes
    assert _transitions() == avant_transitions
    assert _etat(brouillon["deliverable_id"]) == etat_avant
    assert _objets_du_magasin() == avant_objets, (
        "une tentative refusee a depose un objet dans le magasin")


def test_un_viewer_lit(client, jeton, projet, brouillon):
    """LA LECTURE, ELLE, RESTE OUVERTE À TOUT MEMBRE ACTIF."""
    for quoi, chemin in _lectures_de_livrable(projet["project_id"],
                                              brouillon["deliverable_id"]):
        r = client.get(chemin, headers=_entete(jeton(ACTEUR_W)))
        assert r.status_code == 200, (quoi, r.status_code, r.text)


# ===========================================================================
# PREUVE 2 — UN MEMBRE DÉSACTIVÉ N'A AUCUN ACCÈS MÉTIER
# ===========================================================================
def test_un_membre_desactive_ne_voit_meme_plus_ses_projets(
        client, jeton, projet):
    """UN ACCÈS RÉVOQUÉ EST RÉVOQUÉ, Y COMPRIS EN LECTURE.

    ``is_active`` existe depuis 0009 et n'était lu que par la primitive
    d'attestation. Partout ailleurs — appartenance, écriture, liste des
    projets — un ancien collaborateur restait un membre à part entière.

    LA LIGNE D'ADHÉSION SURVIT, et c'est voulu : une note de dix ans doit
    rester lisible et nommer son signataire. Ce qui disparaît, c'est l'accès.
    """
    r = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_D)))
    assert r.status_code == 200, r.text
    assert all(p["project_id"] != projet["project_id"]
               for p in r.json()["projects"]), (
        "un membre desactive voit encore les projets de l'organisation")


def test_un_membre_desactive_ne_lit_ni_ne_mute_aucun_livrable(
        client, jeton, projet, calcul_strict, brouillon):
    """AUCUNE DES DIX ROUTES, NI EN LECTURE NI EN ÉCRITURE."""
    avant_lignes = _lignes_de_livrable()
    avant_objets = _objets_du_magasin()
    etat_avant = _etat(brouillon["deliverable_id"])

    for quoi, chemin in _lectures_de_livrable(projet["project_id"],
                                              brouillon["deliverable_id"]):
        r = client.get(chemin, headers=_entete(jeton(ACTEUR_D)))
        assert r.status_code in (403, 422), (quoi, r.status_code, r.text)

    for quoi, methode, chemin, corps in _mutations_de_livrable(
            projet["project_id"], brouillon["deliverable_id"], calcul_strict):
        r = _appeler(client, methode, chemin, corps,
                     _entete(jeton(ACTEUR_D)))
        assert r.status_code in (403, 422), (quoi, r.status_code, r.text)

    assert _lignes_de_livrable() == avant_lignes
    assert _etat(brouillon["deliverable_id"]) == etat_avant
    assert _objets_du_magasin() == avant_objets


def test_un_membre_desactive_ne_calcule_ni_ne_cree_de_projet(
        client, jeton, projet):
    """LE CHEMIN DE TRAVAIL AUSSI. Un accès révoqué n'écrit plus rien."""
    avant = _observer("select count(*) from calculations")[0][0]
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json={"element": "P-REVOQUE", "strict_ndp": False,
              "section": {"b": {"value": 300.0, "unit": "mm"},
                          "h": {"value": 500.0, "unit": "mm"},
                          "d": {"value": 450.0, "unit": "mm"}},
              "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
              "M_Ed": {"value": 180.0, "unit": "kN*m"}},
        headers=_entete(jeton(ACTEUR_D)))
    assert r.status_code in (403, 422), r.text
    assert _observer("select count(*) from calculations")[0][0] == avant

    r = client.post("/v1/projects",
                    json={"name": "FICTIF Revoque", "country": "BE",
                          "ndp_as_of": "2024-01-15",
                          "organization_id": ORG_A},
                    headers=_entete(jeton(ACTEUR_D)))
    assert r.status_code in (403, 422), r.text


# ===========================================================================
# PREUVE 3 — UN SIMPLE « engineer » N'ÉMET PAS
# ===========================================================================
def test_un_simple_engineer_n_emet_pas_un_livrable_atteste(
        client, jeton, projet, en_relecture):
    """ÉMETTRE, C'EST METTRE EN CIRCULATION, ET CELA SUIT L'ATTESTATION.

    ``project_deliverable_finalize`` ne contrôlait AUCUN rôle : n'importe quel
    membre pouvant écrire pouvait publier le document qu'un autre venait
    d'attester. La séparation entre celui qui rédige et celui qui répond du
    calcul disparaissait à la dernière étape.
    """
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{en_relecture['deliverable_id']}")
    r = client.post(f"{base}/validation",
                    json={"statement": "FICTIF — relu et approuve."},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "validated"

    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code in (403, 422), (
        f"un engineer a emis un livrable atteste: {r.status_code} {r.text}")
    assert "engineer" in json.dumps(r.json())
    assert _etat(en_relecture["deliverable_id"]) == "validated"

    # ET LE VALIDATEUR, LUI, EMET.
    r = client.post(f"{base}/final", headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "final"


def test_un_validateur_ne_cree_ni_ne_soumet(
        client, jeton, projet, calcul_strict, brouillon):
    """LA SÉPARATION JOUE DANS LES DEUX SENS.

    Celui qui répond du calcul ne le rédige pas : c'est ce qui donne un sens à
    « relu ». ``project_actor_can_write`` rangeait pourtant
    ``validating_engineer`` avec les rédacteurs, et ce cas ferme l'écart.
    """
    base = f"/v1/projects/{projet['project_id']}/deliverables"
    avant = _lignes_de_livrable()

    r = client.post(base, json={"calculation_id": calcul_strict},
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code in (403, 422), r.text
    assert _lignes_de_livrable() == avant

    r = client.post(f"{base}/{brouillon['deliverable_id']}/review",
                    headers=_entete(jeton(ACTEUR_V)))
    assert r.status_code in (403, 422), r.text
    assert _etat(brouillon["deliverable_id"]) == "draft"


# ===========================================================================
# PREUVE 4 — UNE TENTATIVE REFUSÉE NE DÉPOSE AUCUN OBJET
# ===========================================================================
def test_une_tentative_refusee_ne_laisse_aucun_objet_orphelin(
        client, jeton, projet, calcul_strict):
    """L'ORDRE DES GESTES DÉCIDE DE CE QUI RESTE APRÈS UN REFUS.

    La route composait le document, déposait ses octets, PUIS appelait la
    primitive — qui refusait. Le magasin gardait un objet que plus aucune
    ligne ne référençait, et qu'aucune réconciliation ne saurait rattacher à
    quoi que ce soit.

    UN PRÉCONTRÔLE D'AUTORISATION AVANT LE DÉPÔT EST LA SEULE RÉPONSE. Il ne
    remplace pas le contrôle final — la primitive le rejoue, et c'est elle la
    frontière — mais il évite d'écrire pour rien.
    """
    avant = _objets_du_magasin()
    for acteur, role in ((ACTEUR_W, "viewer"), (ACTEUR_D, "revoque"),
                         (ACTEUR_B, "autre organisation")):
        r = client.post(f"/v1/projects/{projet['project_id']}/deliverables",
                        json={"calculation_id": calcul_strict},
                        headers=_entete(jeton(acteur)))
        assert r.status_code in (403, 422), (role, r.status_code, r.text)
        assert _objets_du_magasin() == avant, (
            f"la tentative de « {role} » a depose un objet avant son refus")


# ===========================================================================
# LA FRONTIÈRE EST DANS POSTGRESQL, PAS DANS FASTAPI
# ===========================================================================
def test_les_primitives_refusent_elles_memes_hors_de_toute_route(
        projet, calcul_strict, brouillon):
    """UNE RÈGLE QUI NE VIT QUE DANS L'API N'EXISTE PAS POUR QUI ATTEINT LA BASE.

    Ces appels n'empruntent aucune route : ils exécutent les primitives
    directement, sous le login de service et l'acteur posé. C'est le chemin
    qu'emprunterait quelqu'un ayant obtenu la DSN, et c'est celui qui doit
    tenir.
    """
    pid, did = projet["project_id"], brouillon["deliverable_id"]

    # LE VIEWER NE REDIGE PAS.
    refus = _refus_de_la_primitive(
        "select project_deliverable_create(%s::uuid, %s::uuid,"
        " 'calculation_note_html'::deliverable_kind, %s, %s, %s, %s, %s,"
        " %s::bigint, null, null)",
        (pid, calcul_strict, "FICTIF.html", "text/html", "local",
         "o/p/" + "c" * 64 + ".html", "c" * 64, 10),
        acteur=ACTEUR_W)
    assert "viewer" in refus or "redig" in refus, refus

    # LE MEMBRE REVOQUE N'ATTEINT MEME PLUS LE LIVRABLE.
    refus = _refus_de_la_primitive(
        "select project_deliverable_transition("
        "%s::uuid, %s::uuid, 'review'::deliverable_state, null)",
        (pid, did), acteur=ACTEUR_D)
    assert "revoqu" in refus or "introuvable" in refus, refus

    # ET L'ENGINEER N'EMET PAS.
    refus = _refus_de_la_primitive(
        "select project_deliverable_finalize(%s::uuid, %s::uuid)",
        (pid, did), acteur=ACTEUR_A)
    assert "engineer" in refus or "emission" in refus or "relecture" in refus, refus


def test_une_mutation_refusee_ne_repond_jamais_deux_cents(
        client, jeton, projet, brouillon):
    """UN REFUS QUI SE PRÉSENTE COMME UN SUCCÈS EST PIRE QU'UN REFUS.

    Les politiques RLS filtrent la ligne par leur clause ``using`` :
    l'``update`` touche alors ZÉRO ligne, **sans erreur**, et la primitive
    rendait quand même l'état visé. Le client apprenait que sa soumission
    avait abouti, et rien n'avait changé.
    """
    base = (f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{brouillon['deliverable_id']}")
    for acteur, role in ((ACTEUR_W, "viewer"), (ACTEUR_D, "revoque")):
        r = client.post(f"{base}/review", headers=_entete(jeton(acteur)))
        assert r.status_code != 200, (
            f"« {role} » a obtenu 200 sur une soumission refusee: {r.text}")
    assert _etat(brouillon["deliverable_id"]) == "draft"


def test_le_decor_est_bien_celui_qu_on_croit():
    """SANS CE CAS, LES REFUS CI-DESSUS POURRAIENT ÊTRE VIDES DE SENS.

    Un décor où personne n'aurait le rôle attendu rendrait tous les refus
    triviaux — et le module passerait au vert en n'éprouvant rien.
    """
    lignes = _observer(
        "select user_id::text, role::text, is_active from organization_members "
        " where org_id = %s order by user_id", (ORG_A,))
    par_acteur = {u: (r, a) for u, r, a in lignes}
    assert par_acteur[ACTEUR_A] == ("engineer", True)
    assert par_acteur[ACTEUR_V] == ("validating_engineer", True)
    assert par_acteur[ACTEUR_W] == ("viewer", True)
    assert par_acteur[ACTEUR_D] == ("validating_engineer", False)
    assert par_acteur[ACTEUR_N] == ("validating_engineer", True)
    assert ACTEUR_B not in par_acteur
    assert MAGASIN and os.path.isdir(MAGASIN)
