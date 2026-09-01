"""La verification complete d'une poutre, par HTTP et jusqu'en base.

CE QUE CE FICHIER EXISTE POUR ATTRAPER
---------------------------------------
`engine/tests/test_verification_poutre.py` prouve que l'orchestrateur derive
correctement les cinq sections d'une entree gelee. Il ne dit RIEN de la
frontiere HTTP: ce qu'un client peut envoyer, ce que le serveur refuse de
recevoir, et ce que PostgreSQL garde apres un redemarrage.

Or c'est la que se logent les defauts les plus couteux. Un champ CALCULE
accepte du corps — `status`, `may_be_finalised`, `inputs_hash`, l'entraxe —
laisserait un client decider de sa propre conformite. Un contexte normatif lu
dans le corps laisserait une etude belge se declarer francaise. Un provider
nomme par le corps laisserait choisir qui atteste.

LA REGLE, EN UNE PHRASE: le corps porte ce que l'ingenieur SAIT, jamais ce que
le serveur CALCULE ni ce que le projet FIXE.

CE QUI RESTE VRAI DE LA FRANCE
-------------------------------
Quatre sections evaluables, ELS `not_evaluated`, raison `not_representable`,
et aucune substitution scalaire. Ce module le verifie a la frontiere HTTP,
comme le moteur le verifie chez lui.

AUCUNE ETUDE PRODUITE ICI N'EST UNE VERIFICATION REELLE. Les comptes sont
fictifs, le registre reste a 0/29, et la base est detruite a la fin du harnais.
"""
# LES FIXTURES SONT INJECTEES PAR PYTEST, PAS APPELEES. Elles sont donc
# importees puis « redefinies » comme parametres de chaque test: c'est
# l'idiome, et les modules voisins portent la meme exemption.
# ruff: noqa: F811

from __future__ import annotations

import pytest

from .test_livrables import (  # noqa: F401 — fixtures partagees, decor commun
    ACTEUR_A,
    ACTEUR_B,
    ACTEUR_V,
    DECOR_PRESENT,
    _entete,
    _observer,
    cle,
    client,
    client_neuf,
    jeton,
    projet,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/livrable_validation.sh, qui pose la base deployee, "
                "les adhesions et la racine d'autorite."),
    ),
]


@pytest.fixture(scope="module")
def projet_fr(client, jeton) -> dict:
    """UN PROJET FRANCAIS, POUR CONSTATER — PAS POUR CONTOURNER.

    La France est le seul pays du referentiel livre dont un parametre est
    `not_representable`: son NA rend k3 fonction de l'enrobage. Ce projet sert
    a verifier que le produit le DIT honnetement a la frontiere HTTP. Aucune
    valeur n'est substituee pour le rendre calculable.
    """
    r = client.post(
        "/v1/projects",
        json={"name": "FICTIF Halle FR", "reference": "FICTIF-VC-FR",
              "country": "FR", "region": "Ile-de-France",
              # LA DATE EST CELLE D'UNE ANNEXE FRANCAISE EN VIGUEUR. Mesure du
              # 01/09: 2024-01-15 n'en a aucune, et le projet etait refuse
              # avant meme d'atteindre le sujet du test.
              "ndp_as_of": "2026-01-01"},
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Le corps de reference
# ---------------------------------------------------------------------------
def _corps(**remplace):
    """L'etude belge de reference, telle qu'un client l'envoie.

    Elle ne porte NI pays, NI region, NI date normative: les trois sont figes
    sur le projet. Elle ne porte AUCUNE grandeur derivee.
    """
    base = {
        "element": "P1",
        "strict_ndp": False,
        "geometry": {
            "b": {"value": 300, "unit": "mm"},
            "h": {"value": 600, "unit": "mm"},
            "d": {"value": 550, "unit": "mm"},
            "l_eff": {"value": 6000, "unit": "mm"},
        },
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"},
        "V_Ed": {"value": 300, "unit": "kN"},
        "M_char": {"value": 180, "unit": "kN*m"},
        "M_qp": {"value": 120, "unit": "kN*m"},
        "phi_creep": 2.0,
        "exposure_class": "XC3",
        "structural_system": "simply_supported",
        "supports_brittle_partitions": False,
        "bars": {"count": 4, "diameter": {"value": 20, "unit": "mm"}},
        "links": {"legs": 2, "diameter": {"value": 10, "unit": "mm"},
                  "spacing": {"value": 150, "unit": "mm"}},
        "cot_theta": 1.5,
        "cover": {"value": 40, "unit": "mm"},
        "anchorage_available": {"value": 800, "unit": "mm"},
    }
    base.update(remplace)
    return base


def _url(projet):
    return f"/v1/projects/{projet['project_id']}/beam-verifications"


def _verifier(client, jeton, projet, acteur=None, **remplace):
    return client.post(_url(projet), json=_corps(**remplace),
                       headers=_entete(jeton(acteur or ACTEUR_A)))


# ---------------------------------------------------------------------------
# 1. LE CORPS N'ACCEPTE AUCUN CHAMP CALCULE
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("champ,valeur", [
    ("status", "passed"),
    ("may_be_finalised", True),
    ("preflight_ready", True),
    ("engineering_inputs_hash", "0" * 64),
    ("ndp_snapshot_id", "0" * 64),
    ("calculation_fingerprint", "0" * 64),
    ("execution_identity", "0" * 64),
    ("provider_identity", "moi-meme"),
    ("is_exploratory", False),
    # Les grandeurs DERIVEES: deux sources pour un meme fait divergent un jour.
    ("A_s", {"value": 1257, "unit": "mm**2"}),
    ("A_sw", {"value": 157, "unit": "mm**2"}),
    ("bar_spacing", {"value": 60, "unit": "mm"}),
    # Le contexte normatif est fige sur le PROJET.
    ("country", "FR"),
    ("region", "Bretagne"),
    ("ndp_as_of", "2030-01-01"),
])
def test_un_champ_calcule_dans_le_corps_est_refuse(
        client, jeton, projet, champ, valeur) -> None:
    """UN CLIENT NE DECIDE PAS DE SA PROPRE CONFORMITE.

    `status` ou `may_be_finalised` acceptes du corps laisseraient un appelant
    se declarer conforme. `inputs_hash` accepte laisserait enregistrer
    l'empreinte d'entrees qu'on n'a pas recues. `A_s` accepte a cote des barres
    donnerait DEUX sources pour une meme aire — et le jour ou elles divergent,
    le produit dessine autre chose que ce qu'il a calcule.

    Ces champs ne sont pas « ignores »: ils sont REFUSES, pour que le client
    sache que sa valeur n'a aucun effet plutot que de le croire.
    """
    r = _verifier(client, jeton, projet, **{champ: valeur})
    assert r.status_code == 422, (
        f"le champ calcule « {champ} » a ete accepte: {r.status_code}")


def test_le_corps_de_reference_est_accepte(client, jeton, projet) -> None:
    """Le pendant positif: sans champ interdit, la requete passe."""
    r = _verifier(client, jeton, projet)
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 2. LE CONTEXTE NORMATIF EST GELE AVEC LES ENTREES
# ---------------------------------------------------------------------------
def test_le_contexte_normatif_est_gele_et_entre_dans_l_empreinte(
        client, jeton, projet) -> None:
    corps = _verifier(client, jeton, projet).json()
    assert corps["country"] == projet["country"]
    assert corps["ndp_as_of"] == projet["ndp_as_of"]
    assert corps["strict_ndp"] is False
    assert len(corps["engineering_inputs_hash"]) == 64
    assert len(corps["ndp_snapshot_id"]) == 64
    assert len(corps["calculation_fingerprint"]) == 64

    #: LE PAYS VIT SUR LE PROJET, la date normative sur le calcul. Les deux
    #: sont figes: c'est la jointure qui prouve qu'ils s'accordent.
    ligne = _observer(
        "select c.strict_ndp, p.country::text, p.region, c.ndp_as_of::text, "
        "       c.inputs_hash, c.request->>'country', c.request->>'as_of' "
        "  from calculations c join projects p on p.id = c.project_id "
        " where c.id = %s", (corps["calculation_id"],))[0]
    assert ligne[0] is False
    assert ligne[1] == projet["country"]
    assert ligne[3] == projet["ndp_as_of"]
    #: LA COLONNE SQL PROMET LA TOTALITE DES ENTREES: elle porte donc
    #: l'empreinte COMPLETE, pas la seule technique. Deux etudes identiques
    #: sous des annexes differentes ne la partagent pas.
    assert ligne[4] == corps["calculation_fingerprint"]
    assert ligne[4] != corps["engineering_inputs_hash"]
    #: ET LA CHARGE GELEE PORTE LE MEME CONTEXTE. Une requete enregistree qui
    #: se contredirait est exactement ce que 0019 refuse.
    assert ligne[5] == projet["country"]
    assert ligne[6] == projet["ndp_as_of"]


# ---------------------------------------------------------------------------
# 3. LE MODE STRICT SANS CONFIRMATIONS: ZERO CALCUL, ZERO LIGNE
# ---------------------------------------------------------------------------
def test_strict_sans_confirmations_refuse_avec_tous_les_bloquants(
        client, jeton, projet) -> None:
    """LE REFUS EST COMPLET, PAS SEQUENTIEL.

    Un ingenieur qui corrige un parametre pour se voir refuser sur le suivant,
    puis le suivant, ne sait jamais ou il en est. La reponse porte donc TOUS
    les bloquants, avec pour chacun le module qui le reclame.
    """
    r = _verifier(client, jeton, projet, strict_ndp=True)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    bloquants = detail.get("blocking") or []
    assert bloquants, "un refus strict doit nommer ce qui bloque"
    for b in bloquants:
        assert b["module"] in {"flexure", "shear", "anchorage",
                               "serviceability", "deflection"}
        assert b["parameter"] and b["reason"] and b["annex"]


def test_un_refus_strict_n_ecrit_aucune_ligne_de_calcul(
        client, jeton, projet) -> None:
    """ZERO ECRITURE. Pas de calcul partiel, pas de resultat, pas de livrable.

    Le refus vient AVANT le moteur: le preflight parle d'abord. Il n'y a donc
    rien a enregistrer — pas meme un refus — parce qu'aucun calcul n'a ete
    tente.
    """
    avant = _observer(
        "select count(*) from calculations where project_id = %s",
        (projet["project_id"],))[0][0]
    r = _verifier(client, jeton, projet, strict_ndp=True)
    assert r.status_code == 422
    apres = _observer(
        "select count(*) from calculations where project_id = %s",
        (projet["project_id"],))[0][0]
    assert apres == avant, "un refus strict a laisse une ligne derriere lui"


def test_un_refus_moteur_n_ecrit_aucune_etude_partielle(
        client, jeton, projet) -> None:
    """Une saisie incoherente est refusee, pas conservee en « incomplete »."""
    avant = _observer(
        "select count(*) from calculations where project_id = %s",
        (projet["project_id"],))[0][0]
    r = _verifier(client, jeton, projet,
                  M_char={"value": 100, "unit": "kN*m"},
                  M_qp={"value": 120, "unit": "kN*m"})
    assert r.status_code == 422, r.text
    apres = _observer(
        "select count(*) from calculations where project_id = %s",
        (projet["project_id"],))[0][0]
    assert apres == avant


# ---------------------------------------------------------------------------
# 4. L'ETUDE EXPLORATOIRE: ENREGISTREE, ROUVRABLE, JAMAIS FINALISABLE
# ---------------------------------------------------------------------------
def test_l_etude_exploratoire_belge_est_complete_et_persistee(
        client, jeton, projet) -> None:
    """BE_EXPLORATORY_FIVE_SECTIONS_EXECUTABLE, par HTTP."""
    corps = _verifier(client, jeton, projet).json()
    assert corps["status"] == "passed"
    assert [s["key"] for s in corps["sections"]] == [
        "flexure", "shear", "anchorage", "serviceability", "deflection"]
    for s in corps["sections"]:
        assert s["status"] == "passed", f"{s['key']}: {s}"


def test_l_etude_exploratoire_porte_la_mention_non_signable(
        client, jeton, projet) -> None:
    corps = _verifier(client, jeton, projet).json()
    assert corps["is_exploratory"] is True
    assert corps["may_be_finalised"] is False
    assert corps["mention"] == "PROJET — NON SIGNABLE"


def test_l_etude_exploratoire_se_rouvre_a_l_identique(
        client, jeton, projet) -> None:
    """F5: ce qui revient ne peut venir que de la base."""
    cree = _verifier(client, jeton, projet).json()
    relu = client.get(f"{_url(projet)}/{cree['calculation_id']}",
                      headers=_entete(jeton(ACTEUR_A)))
    assert relu.status_code == 200, relu.text
    revu = relu.json()
    assert revu["engineering_inputs_hash"] == cree["engineering_inputs_hash"]
    assert revu["ndp_snapshot_id"] == cree["ndp_snapshot_id"]
    assert revu["calculation_fingerprint"] == cree["calculation_fingerprint"]
    assert [(s["key"], s["status"], s["utilisation"])
            for s in revu["sections"]] == [
        (s["key"], s["status"], s["utilisation"]) for s in cree["sections"]]


def test_les_etudes_survivent_a_un_redemarrage_de_l_api(
        client, client_neuf, jeton, projet) -> None:
    """Un processus neuf, sans cache: la base est la seule source."""
    cree = _verifier(client, jeton, projet).json()
    relu = client_neuf.get(f"{_url(projet)}/{cree['calculation_id']}",
                           headers=_entete(jeton(ACTEUR_A)))
    assert relu.status_code == 200, relu.text
    assert relu.json()["calculation_fingerprint"] == cree["calculation_fingerprint"]


def test_une_etude_exploratoire_ne_peut_pas_etre_attestee(
        client, jeton, projet) -> None:
    """L'INTERDICTION EST DANS POSTGRESQL, PAS DANS LE BOUTON.

    ON NE PASSE PAS PAR L'ECRAN: on appelle la route de validation sous
    l'identite du validateur, qui a la capacite de valider. Le refus ne peut
    donc venir NI du role, NI d'un bouton absent — seulement de l'etat du
    calcul, constate par `project_deliverable_validate` (0023).

    Un ecran qui cacherait le bouton ne prouverait rien: un client qui appelle
    l'API directement ne voit aucun bouton.
    """
    cree = _verifier(client, jeton, projet).json()
    base_p = f"/v1/projects/{projet['project_id']}/deliverables"

    #: LE BROUILLON EST PERMIS, ET IL PORTE LE FILIGRANE. Une etude
    #: exploratoire se conserve et se relit; c'est l'ATTESTATION qui est
    #: interdite, pas la trace.
    r = client.post(base_p, json={"calculation_id": cree["calculation_id"]},
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    livrable = r.json()
    assert livrable["watermark"] == "PROJET — NON SIGNABLE"

    client.post(f"{base_p}/{livrable['deliverable_id']}/review",
                headers=_entete(jeton(ACTEUR_A)))
    refus = client.post(
        f"{base_p}/{livrable['deliverable_id']}/validation",
        json={"statement": "FICTIF — attestation de test", "reservations": ""},
        headers=_entete(jeton(ACTEUR_V)))
    assert refus.status_code == 422, refus.text
    assert "strict" in refus.text.lower() or "exploratoire" in refus.text.lower()


# ---------------------------------------------------------------------------
# 5. LES ETUDES NON VERTES SE CONSERVENT SANS DEVENIR FINALES
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("libelle,remplace,attendu", [
    ("ferraillage insuffisant",
     {"bars": {"count": 3, "diameter": {"value": 16, "unit": "mm"}}},
     "failed"),
    ("dispense non acquise",
     {"geometry": {"b": {"value": 300, "unit": "mm"},
                   "h": {"value": 600, "unit": "mm"},
                   "d": {"value": 550, "unit": "mm"},
                   "l_eff": {"value": 12000, "unit": "mm"}}},
     "incomplete"),
])
def test_une_etude_non_verte_est_conservee_mais_pas_finale(
        client, jeton, projet, libelle, remplace, attendu) -> None:
    r = _verifier(client, jeton, projet, **remplace)
    assert r.status_code == 201, r.text
    corps = r.json()
    assert corps["status"] == attendu, libelle
    assert corps["may_be_finalised"] is False

    #: CONSERVEE POUR DIAGNOSTIC: la ligne existe et se relit.
    relu = client.get(f"{_url(projet)}/{corps['calculation_id']}",
                      headers=_entete(jeton(ACTEUR_A)))
    assert relu.status_code == 200

    #: MAIS PAS `succeeded` EN BASE, donc pas publiable: c'est la garde
    #: existante `project_calculation_is_publishable` qui le dit.
    etat = _observer("select status::text from calculations where id = %s",
                     (corps["calculation_id"],))[0][0]
    assert etat != "succeeded", (
        f"une etude « {attendu} » enregistree « succeeded » deviendrait "
        "publiable")


# ---------------------------------------------------------------------------
# 6. LA FRANCE RESTE HONNETE
# ---------------------------------------------------------------------------
def test_la_france_rend_quatre_sections_et_un_els_non_evalue(
        client, jeton, projet_fr) -> None:
    """FR_EXPLORATORY_SLS_NOT_EVALUATED_FORMULA_MODEL_GAP, par HTTP."""
    r = client.post(_url(projet_fr), json=_corps(),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    corps = r.json()
    els = next(s for s in corps["sections"] if s["key"] == "serviceability")
    assert els["status"] == "not_evaluated"
    assert els["utilisation"] is None
    assert "representable" in (els["reason"] or "")
    evaluees = [s for s in corps["sections"] if s["status"] != "not_evaluated"]
    assert len(evaluees) == 4
    assert corps["status"] == "incomplete"
    assert corps["may_be_finalised"] is False


# ---------------------------------------------------------------------------
# 7. ISOLATION, EMPREINTES, IDEMPOTENCE
# ---------------------------------------------------------------------------
def test_une_autre_organisation_n_obtient_aucune_lecture(
        client, jeton, projet) -> None:
    cree = _verifier(client, jeton, projet).json()
    r = client.get(f"{_url(projet)}/{cree['calculation_id']}",
                   headers=_entete(jeton(ACTEUR_B)))
    #: LE CODE EST CELUI QUE LE PRODUIT EMPLOIE DEJA POUR UN REFUS D'ATELIER,
    #: et il ne distingue pas « absent » de « interdit »: c'est voulu, un code
    #: qui les separerait dirait a un tiers que le dossier EXISTE. Ce que ce
    #: test exige, c'est qu'AUCUNE donnee ne filtre.
    assert r.status_code in (403, 404, 422), r.status_code
    for secret in (cree["engineering_inputs_hash"], cree["ndp_snapshot_id"],
                   cree["calculation_fingerprint"]):
        assert secret not in r.text


def test_changer_le_referentiel_change_l_empreinte(
        client, jeton, projet, projet_fr) -> None:
    """Les memes nombres sous un autre referentiel ne sont pas la meme etude."""
    be = _verifier(client, jeton, projet).json()
    fr = client.post(_url(projet_fr), json=_corps(),
                     headers=_entete(jeton(ACTEUR_A))).json()
    assert be["engineering_inputs_hash"] == fr["engineering_inputs_hash"], (
        "les nombres saisis sont identiques")
    assert be["ndp_snapshot_id"] != fr["ndp_snapshot_id"]
    assert be["calculation_fingerprint"] != fr["calculation_fingerprint"]


def test_deux_requetes_identiques_sont_une_repetition_deterministe(
        client, jeton, projet) -> None:
    """CE N'EST PAS DE L'IDEMPOTENCE, ET LE MOT COMPTE.

    Deux etudes identiques donnent la MEME empreinte — c'est le DETERMINISME —
    et deux LIGNES distinctes: l'historique du projet garde chaque tentative,
    parce qu'un ingenieur qui relance veut voir qu'il a relance.

    Appeler cela « idempotent » serait faux: une operation idempotente rendrait
    la MEME ressource, pas une seconde. Le produit n'offre aujourd'hui aucune
    cle d'idempotence; le jour ou il en offrira une, le contrat sera « meme cle
    et meme corps -> meme reponse et meme calcul; meme cle et corps different
    -> 409 ». Rien de tout cela n'existe encore, et ce test ne le suppose pas.
    """
    a = _verifier(client, jeton, projet).json()
    b = _verifier(client, jeton, projet).json()
    assert a["calculation_fingerprint"] == b["calculation_fingerprint"]
    assert a["calculation_id"] != b["calculation_id"]


# ---------------------------------------------------------------------------
# 8. L'ANCIEN PARCOURS DE FLEXION SIMPLE EST INTACT
# ---------------------------------------------------------------------------
def test_l_ancien_endpoint_de_flexion_rend_les_memes_octets(
        client, jeton, projet) -> None:
    """AUCUNE REGRESSION: le contrat precedent est conserve bit-a-bit."""
    corps = {
        "element": "P1", "strict_ndp": False,
        "section": {"b": {"value": 300, "unit": "mm"},
                    "h": {"value": 600, "unit": "mm"},
                    "d": {"value": 550, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"},
    }
    url = f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure"
    a = client.post(url, json=corps, headers=_entete(jeton(ACTEUR_A)))
    b = client.post(url, json=corps, headers=_entete(jeton(ACTEUR_A)))
    assert a.status_code == 201, a.text
    assert b.status_code == 201
    ja, jb = a.json(), b.json()
    assert ja["inputs_hash"] == jb["inputs_hash"]
    assert ja["status"] == "succeeded"


# ---------------------------------------------------------------------------
# 9. UNE SEULE IDENTITE D'EXECUTION, DE BOUT EN BOUT
# ---------------------------------------------------------------------------
def test_l_identite_d_execution_est_la_meme_partout(
        client, jeton, projet) -> None:
    """UNE VALEUR, CINQ ENDROITS.

    Elle etait calculee une premiere fois avec `ndp=None` et passee au moteur,
    puis RECALCULEE avec l'instantane normatif pour la persistance. L'etude en
    portait une, la base une autre — et une note qui cite la premiere ne se
    rattache a aucune ligne.
    """
    corps = _verifier(client, jeton, projet).json()
    identite = corps["execution_identity"]
    assert len(identite) == 64

    #: EN BASE, DANS LA COLONNE ET DANS LE PAYLOAD.
    ligne = _observer(
        "select c.execution_identity, "
        "       r.payload->'result'->>'execution_identity' "
        "  from calculations c "
        "  join results r on r.calculation_id = c.id "
        " where c.id = %s", (corps["calculation_id"],))[0]
    assert ligne[0] == identite, "la colonne porte une autre identite"
    assert ligne[1] == identite, "le payload porte une autre identite"

    #: ET A LA RELECTURE.
    relu = client.get(f"{_url(projet)}/{corps['calculation_id']}",
                      headers=_entete(jeton(ACTEUR_A))).json()
    assert relu["execution_identity"] == identite


def test_l_identite_change_avec_le_referentiel(
        client, jeton, projet, projet_fr) -> None:
    """Meme requete, meme build, deux annexes: deux identites."""
    be = _verifier(client, jeton, projet).json()
    fr = client.post(_url(projet_fr), json=_corps(),
                     headers=_entete(jeton(ACTEUR_A))).json()
    assert be["execution_identity"] != fr["execution_identity"]
