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


# ---------------------------------------------------------------------------
# 10. LA NOTE A CINQ CHAPITRES
# ---------------------------------------------------------------------------
def _note(client, jeton, projet, calcul_id, acteur=None):
    return client.get(
        f"/v1/projects/{projet['project_id']}/calculations/{calcul_id}/note.html",
        headers=_entete(jeton(acteur or ACTEUR_A)))


def test_la_note_porte_les_cinq_chapitres_dans_l_ordre(
        client, jeton, projet) -> None:
    """L'ORDRE EST FIXE: un lecteur qui compare deux dossiers en depend."""
    cree = _verifier(client, jeton, projet).json()
    r = _note(client, jeton, projet, cree["calculation_id"])
    assert r.status_code == 200, r.text
    html = r.text

    #: LES APOSTROPHES SONT ECHAPPEES, et c'est correct: « l'ELU » sort
    #: « l&#x27;ELU ». C'est au test de se conformer au document, pas
    #: l'inverse — desechapper le rendu pour le tester reviendrait a tester
    #: autre chose que ce qu'un navigateur affiche.
    from html import escape

    titres = ["Flexion simple a l'ELU", "Effort tranchant a l'ELU",
              "Ancrages et recouvrements", "Etats limites de service",
              "Limitation des fleches"]
    positions = []
    for index, titre in enumerate(titres, start=1):
        marqueur = f"{index}. {escape(titre, quote=True)}"
        assert marqueur in html, f"chapitre absent: {marqueur}"
        positions.append(html.index(marqueur))
    assert positions == sorted(positions), "les chapitres ne sont pas en ordre"


def test_la_note_n_imprime_que_des_valeurs_venues_des_journaux(
        client, jeton, projet) -> None:
    """INTERDICTION N.1, RENDUE VERIFIABLE.

    On collecte toutes les valeurs que les journaux persistes portent, puis on
    verifie que chaque cellule numerique de la note figure dans cet ensemble —
    ou parmi les taux d'utilisation, eux aussi calcules par le moteur. Un
    renderer qui calculerait quoi que ce soit produirait une chaine absente des
    deux.
    """
    import re

    cree = _verifier(client, jeton, projet).json()
    html = _note(client, jeton, projet, cree["calculation_id"]).text

    brut = _observer("select journal from results where calculation_id = %s",
                     (cree["calculation_id"],))[0][0]
    legitimes = set()
    for bloc in (brut or {}).get("sections", []):
        for etape in ((bloc.get("journal") or {}).get("steps") or []):
            if etape.get("formatted"):
                legitimes.add(etape["formatted"])
    assert legitimes, "aucun journal persiste: le test ne prouverait rien"

    taux = {f"{s['utilisation']:.3f}" for s in cree["sections"]
            if s["utilisation"] is not None}
    imprimees = set(re.findall(r'<td class="nombre">([^<]+)</td>', html))
    inexpliquees = imprimees - legitimes - taux - {"—"}
    assert not inexpliquees, (
        f"la note imprime des valeurs qu'aucun journal ne porte: "
        f"{sorted(inexpliquees)[:5]}")


def test_la_note_exploratoire_porte_la_mention_en_tete_et_en_pied(
        client, jeton, projet) -> None:
    cree = _verifier(client, jeton, projet).json()
    html = _note(client, jeton, projet, cree["calculation_id"]).text
    assert html.count("PROJET — NON SIGNABLE") >= 2, (
        "la mention doit encadrer le document: un lecteur presse lit l'une "
        "ou l'autre extremite, jamais les deux")


def test_la_note_imprime_le_contexte_normatif_et_l_identite_de_la_base(
        client, jeton, projet) -> None:
    cree = _verifier(client, jeton, projet).json()
    html = _note(client, jeton, projet, cree["calculation_id"]).text
    identite = _observer(
        "select execution_identity from calculations where id = %s",
        (cree["calculation_id"],))[0][0]
    assert identite in html, "l'identite imprimee n'est pas celle de la base"
    for attendu in (cree["ndp_snapshot_id"], cree["calculation_fingerprint"],
                    cree["engineering_inputs_hash"]):
        assert attendu in html


def test_une_section_non_evaluee_dit_pourquoi_sans_inventer(
        client, jeton, projet_fr) -> None:
    cree = client.post(_url(projet_fr), json=_corps(),
                       headers=_entete(jeton(ACTEUR_A))).json()
    html = _note(client, jeton, projet_fr, cree["calculation_id"]).text
    assert "Non évalué" in html
    assert "n'a pas pu être exécutée" in html
    assert "ne vaut pas conformité" in html


def test_une_dispense_non_acquise_n_est_pas_affichee_comme_non_conforme(
        client, jeton, projet) -> None:
    """L'ORANGE N'EST NI LE VERT NI LE ROUGE, et c'est tout l'interet."""
    cree = _verifier(client, jeton, projet, geometry={
        "b": {"value": 300, "unit": "mm"}, "h": {"value": 600, "unit": "mm"},
        "d": {"value": 550, "unit": "mm"},
        "l_eff": {"value": 12000, "unit": "mm"}}).json()
    html = _note(client, jeton, projet, cree["calculation_id"]).text
    #: DEUX TEXTES COEXISTENT, ET C'EST VOULU: la banniere de la note (avec
    #: accents) et le remede que le MOTEUR a pose sur la section (sans
    #: accents, comme tout le moteur). Les confondre ferait tester la
    #: presence d'une phrase qui n'existe nulle part.
    assert "Analyse complémentaire requise" in html
    assert "calcul explicite de la flèche requis" in html      # banniere
    assert "calcul explicite de la fleche requis" in html      # remede moteur
    assert "un échec de la poutre" in html
    assert cree["status"] == "incomplete"


def test_une_section_rouge_affiche_son_taux_et_son_remede(
        client, jeton, projet) -> None:
    cree = _verifier(client, jeton, projet,
                     bars={"count": 3,
                           "diameter": {"value": 16, "unit": "mm"}}).json()
    html = _note(client, jeton, projet, cree["calculation_id"]).text
    assert "NON CONFORME" in html
    assert "Action" in html
    flexion = next(s for s in cree["sections"] if s["key"] == "flexure")
    assert f"{flexion['utilisation']:.3f}" in html


def test_la_note_ne_reexecute_pas_le_moteur(client, jeton, projet) -> None:
    """DEUX LECTURES RENDENT LES MEMES OCTETS.

    Une note qui relancerait le moteur donnerait les nombres d'aujourd'hui
    sous la date d'hier — et rien ne le signalerait au lecteur.
    """
    cree = _verifier(client, jeton, projet).json()
    a = _note(client, jeton, projet, cree["calculation_id"]).text
    b = _note(client, jeton, projet, cree["calculation_id"]).text
    assert a == b


def test_l_ancienne_note_de_flexion_reste_une_note_de_flexion(
        client, jeton, projet) -> None:
    """AUCUNE REGRESSION: le composeur se choisit sur la structure."""
    corps = {
        "element": "P1", "strict_ndp": False,
        "section": {"b": {"value": 300, "unit": "mm"},
                    "h": {"value": 600, "unit": "mm"},
                    "d": {"value": 550, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250, "unit": "kN*m"},
    }
    r = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=corps, headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    html = _note(client, jeton, projet, r.json()["calculation_id"]).text
    assert "Vérification ELU en flexion simple" in html
    assert "Ancrages et recouvrements" not in html


# ---------------------------------------------------------------------------
# 11. LE BROUILLON PDF DE L'ETUDE COMPLETE
# ---------------------------------------------------------------------------
def _brouillon_pdf_de(client, jeton, projet, calcul_id):
    return client.post(
        f"/v1/projects/{projet['project_id']}/deliverables",
        json={"calculation_id": calcul_id, "format": "pdf"},
        headers=_entete(jeton(ACTEUR_A)))


def test_le_brouillon_pdf_de_l_etude_complete_est_produit_et_filigrane(
        client, jeton, projet) -> None:
    cree = _verifier(client, jeton, projet).json()
    r = _brouillon_pdf_de(client, jeton, projet, cree["calculation_id"])
    assert r.status_code == 201, r.text
    livrable = r.json()
    assert livrable["kind"] == "calculation_note_pdf"
    assert livrable["watermark"] == "PROJET — NON SIGNABLE"
    assert livrable["size_bytes"] > 0


def test_le_pdf_de_l_etude_complete_porte_les_cinq_chapitres(
        client, jeton, projet) -> None:
    """LE LECTEUR EST UN TIERS: `pypdf`, pas notre propre ecrivain."""
    cree = _verifier(client, jeton, projet).json()
    livrable = _brouillon_pdf_de(
        client, jeton, projet, cree["calculation_id"]).json()
    octets = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{livrable['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A))).content
    assert octets.startswith(b"%PDF-")

    pypdf = pytest.importorskip("pypdf")
    import io

    lu = pypdf.PdfReader(io.BytesIO(octets))
    texte = " ".join("\n".join(
        (p.extract_text() or "") for p in lu.pages).split())
    for chapitre in ("Flexion simple", "Effort tranchant", "Ancrages",
                     "Etats limites de service", "Limitation des fleches"):
        assert chapitre in texte, f"chapitre absent du PDF: {chapitre}"
    #: LA MENTION EST SUR LE DOCUMENT, pas seulement dans les metadonnees.
    assert "NON SIGNABLE" in texte


def test_les_octets_du_pdf_sont_deterministes(client, jeton, projet) -> None:
    """AUCUNE HORLOGE: deux compositions du meme dossier, memes octets.

    L'adressage par contenu l'exige — deux depots du meme document doivent
    tomber sur le meme chemin, sinon le magasin se remplit de doublons que
    rien ne distingue.
    """
    import hashlib

    cree = _verifier(client, jeton, projet).json()
    empreintes = set()
    for _ in range(2):
        r = _brouillon_pdf_de(client, jeton, projet, cree["calculation_id"])
        assert r.status_code == 201, r.text
        octets = client.get(
            f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{r.json()['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A))).content
        empreintes.add(hashlib.sha256(octets).hexdigest())
    assert len(empreintes) == 1, (
        "deux compositions du meme dossier ont rendu des octets differents")


# ---------------------------------------------------------------------------
# 12. LE PLAN VIENT DE L'ETUDE, PAS D'UNE RESAISIE
# ---------------------------------------------------------------------------
def _dxf_de(client, jeton, projet, calcul_id):
    return client.post(
        f"/v1/projects/{projet['project_id']}/deliverables",
        json={"calculation_id": calcul_id, "format": "dxf"},
        headers=_entete(jeton(ACTEUR_A)))


def test_le_dxf_se_produit_sans_ressaisir_le_ferraillage(
        client, jeton, projet) -> None:
    """L'ETUDE PORTE DEJA SES BARRES ET SES CADRES.

    La flexion seule ne connait pas le CHOIX du ferraillage — `As_required`
    dit combien d'acier il faut, jamais comment le disposer — et le navigateur
    devait donc l'envoyer. Une etude a cinq sections l'a deja recu et gele.
    Le redemander serait une SECONDE SOURCE, et le jour ou elle diverge, le
    plan montrerait autre chose que ce qui a ete verifie.
    """
    cree = _verifier(client, jeton, projet).json()
    r = _dxf_de(client, jeton, projet, cree["calculation_id"])
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "rebar_drawing_dxf"


def test_le_dxf_dessine_exactement_la_section_calculee(
        client, jeton, projet) -> None:
    """AUCUNE AIRE D'ACIER NE VIENT DU NAVIGATEUR."""
    cree = _verifier(client, jeton, projet).json()
    livrable = _dxf_de(client, jeton, projet, cree["calculation_id"]).json()
    octets = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{livrable['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A))).content.decode("utf-8")

    #: LES QUATRE BARRES DE 20 SONT DANS LA NOMENCLATURE, et l'entraxe derive
    #: du meme modele que celui qui a servi a l'ELS.
    assert "4" in octets and "20" in octets
    coupe = _observer(
        "select payload->'result'->'drawing_spec' from results "
        " where calculation_id = %s", (cree["calculation_id"],))[0][0]
    assert coupe["b"] == 300.0
    assert coupe["cover"] == 40.0
    assert coupe["link_diameter"] == 10.0
    assert coupe["link_spacing"] == 150.0
    assert coupe["bottom"][0]["count"] == 4
    assert coupe["bottom"][0]["diameter"] == 20.0
    assert coupe["exposure_class"] == "XC3"


def test_changer_les_barres_change_les_octets_du_plan(
        client, jeton, projet) -> None:
    """LE PLAN SUIT L'ETUDE, ET NE SE CONTENTE PAS DE LUI RESSEMBLER.

    Un dessin qui viendrait d'un gabarit — meme section, memes barres
    dessinees quelles que soient les entrees — passerait tous les controles de
    forme. Trois etudes qui different par le ferraillage doivent donner trois
    fichiers differents, sans quoi rien ne prouve que le plan lit l'etude.
    """
    import hashlib

    def _octets(**remplace):
        c = _verifier(client, jeton, projet, **remplace).json()
        assert c["status"] == "passed", c
        liv = _dxf_de(client, jeton, projet, c["calculation_id"])
        assert liv.status_code == 201, liv.text
        return hashlib.sha256(client.get(
            f"/v1/projects/{projet['project_id']}/deliverables/"
            f"{liv.json()['deliverable_id']}/download",
            headers=_entete(jeton(ACTEUR_A))).content).hexdigest()

    a = _octets()
    b = _octets(bars={"count": 5, "diameter": {"value": 20, "unit": "mm"}})
    #: DES CADRES PLUS FORTS: l'etude passe toujours, et la coupe change —
    #: le lit de barres se decale de l'epaisseur du cadre.
    c = _octets(links={"legs": 2, "diameter": {"value": 12, "unit": "mm"},
                       "spacing": {"value": 150, "unit": "mm"}})
    assert len({a, b, c}) == 3, (
        "changer les barres ou les cadres doit changer les octets du plan")


@pytest.fixture()
def projet_neuf(client, jeton) -> dict:
    """Un projet belge NEUF, dont le prefixe de magasin n'a jamais rien recu.

    Le chemin d'un livrable derive de son CONTENU: deux depots des memes
    octets ecrivent au meme endroit. Un orphelin qui reprendrait le chemin
    d'un document deja depose serait invisible a un comptage de fichiers —
    non pas parce qu'il n'existe pas, mais parce qu'on ne saurait pas le voir.
    """
    r = client.post(
        "/v1/projects",
        json={"name": "FICTIF Halle ORPH", "reference": "FICTIF-VC-ORPH",
              "country": "BE", "region": "Wallonie",
              "ndp_as_of": "2024-01-15"},
        headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    return r.json()


def test_une_etude_en_echec_n_a_pas_de_plan_et_ne_laisse_pas_d_octets(
        client, jeton, projet_neuf) -> None:
    """UNE POUTRE QUI NE VERIFIE PAS N'A PAS DE PLAN, ET LE REFUS EST A L'HEURE.

    Le fichier ne porte aucun verdict: un DXF de section echouee ressemble
    trait pour trait a un DXF de section conforme, et c'est l'atelier qui le
    lira. Le refus est donc juste — mais `project_calculation_is_publishable`
    ne le prononce qu'a l'ENREGISTREMENT, c'est-a-dire APRES le depot.

    Or la politique du magasin (`docs/STOCKAGE.md` §5) interdit toute
    suppression par le produit: un objet depose puis abandonne est DEFINITIF.
    Le meme soin que `_creer` prend deja pour l'autorisation et pour
    `supersedes_id` est du a ce refus-ci.
    """
    from .test_livrables import _objets_du_magasin

    prefixe = f"{projet_neuf['organization_id']}/" \
              f"{projet_neuf['project_id']}/"
    assert not _objets_du_magasin(prefixe), (
        "le decor est cense partir d'un prefixe vide")
    avant = _observer("select count(*) from deliverables")[0][0]

    faible = _verifier(
        client, jeton, projet_neuf,
        links={"legs": 2, "diameter": {"value": 6, "unit": "mm"},
               "spacing": {"value": 300, "unit": "mm"}}).json()
    assert faible["status"] == "failed", faible

    r = _dxf_de(client, jeton, projet_neuf, faible["calculation_id"])
    assert r.status_code == 422, r.text
    assert "ne conclut pas" in r.text
    assert _observer("select count(*) from deliverables")[0][0] == avant, (
        "aucune ligne ne doit naitre d'un refus")

    apparus = _objets_du_magasin(prefixe)
    assert not apparus, (
        "LE REFUS A LAISSE DES OCTETS DERRIERE LUI. Objets deposes puis "
        f"abandonnes sous « {prefixe} »: {sorted(apparus)}. Aucune ligne de "
        "`deliverables` ne les reference, et la politique du magasin interdit "
        "de les supprimer: ils sont definitifs."
    )


def test_l_apercu_svg_et_le_dxf_viennent_du_meme_modele(
        client, jeton, projet) -> None:
    """L'APERCU MONTRE LA COUPE GELEE, SANS FERRAILLAGE RESAISI NON PLUS.

    `format` nomme le DOCUMENT vise — le plan de ferraillage — pas le codage
    de l'image: l'apercu du plan est du SVG, parce qu'un navigateur ne lit pas
    le DXF. Il appelle le meme `_modele_du_dessin` que le fichier, et c'est ce
    qui interdit qu'il montre autre chose que ce qui sera telecharge.
    """
    cree = _verifier(client, jeton, projet).json()
    apercu = client.post(
        f"/v1/projects/{projet['project_id']}/deliverables/preview",
        json={"calculation_id": cree["calculation_id"], "format": "dxf"},
        headers=_entete(jeton(ACTEUR_A)))
    assert apercu.status_code == 200, apercu.text
    assert apercu.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in apercu.text
    #: L'APERCU N'EST PAS CONTRACTUEL, ET IL LE DIT.
    assert "APERCU NON CONTRACTUEL" in apercu.text
    #: LES BARRES DE L'ETUDE SONT DANS L'IMAGE, sans qu'aucune n'ait ete
    #: renvoyee par le navigateur: le repere « A1 » vient de la coupe gelee.
    assert "A1" in apercu.text


def test_le_plan_survit_au_redemarrage_et_ne_relance_pas_le_moteur(
        client, client_neuf, jeton, projet) -> None:
    """Un processus neuf produit le MEME plan depuis la base seule."""
    import hashlib

    cree = _verifier(client, jeton, projet).json()
    a = _dxf_de(client, jeton, projet, cree["calculation_id"]).json()
    octets_a = client.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{a['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A))).content

    b = client_neuf.post(
        f"/v1/projects/{projet['project_id']}/deliverables",
        json={"calculation_id": cree["calculation_id"], "format": "dxf"},
        headers=_entete(jeton(ACTEUR_A)))
    assert b.status_code == 201, b.text
    octets_b = client_neuf.get(
        f"/v1/projects/{projet['project_id']}/deliverables/"
        f"{b.json()['deliverable_id']}/download",
        headers=_entete(jeton(ACTEUR_A))).content
    assert (hashlib.sha256(octets_a).hexdigest()
            == hashlib.sha256(octets_b).hexdigest())


def test_deux_demandes_du_meme_plan_ne_font_qu_un_objet(
        client, jeton, projet_neuf) -> None:
    """L'ADRESSAGE PAR CONTENU N'EST PAS UNE FIGURE DE STYLE.

    Redemander le meme plan doit REUTILISER l'objet deja depose, pas en ecrire
    un second a cote. Les deux demandes produisent bien deux LIGNES — ce sont
    deux gestes distincts, horodates et attribues — mais un seul FICHIER: le
    chemin derive du SHA-256, et deux contenus identiques ont le meme chemin.

    CE CONTROLE N'AVAIT AUCUN SENS AVANT LE 02/09. Le DXF n'etait pas
    deterministe entre processus, et deux rendus du meme dessin pouvaient
    donner deux empreintes — donc deux chemins, donc deux objets, dans un
    magasin qui ne supprime jamais. Voir
    `engine/tests/test_dxf_determinisme.py` et `docs/TICKET_DXF_DETERMINISME.md`.
    """
    from .test_livrables import _objets_du_magasin

    prefixe = f"{projet_neuf['organization_id']}/" \
              f"{projet_neuf['project_id']}/"
    assert not _objets_du_magasin(prefixe)

    cree = _verifier(client, jeton, projet_neuf).json()
    assert cree["status"] == "passed", cree

    premier = _dxf_de(client, jeton, projet_neuf, cree["calculation_id"])
    second = _dxf_de(client, jeton, projet_neuf, cree["calculation_id"])
    assert premier.status_code == 201, premier.text
    assert second.status_code == 201, second.text

    #: DEUX LIGNES, DEUX IDENTIFIANTS: chaque demande est un geste enregistre.
    assert (premier.json()["deliverable_id"]
            != second.json()["deliverable_id"])
    #: UNE SEULE EMPREINTE, donc un seul chemin.
    assert premier.json()["sha256"] == second.json()["sha256"]

    objets = _objets_du_magasin(prefixe)
    assert len(objets) == 1, (
        "deux demandes du meme plan ont ecrit "
        f"{len(objets)} objets: {sorted(objets)}. Le magasin ne supprime "
        "jamais: chaque doublon est definitif.")
    assert next(iter(objets)).endswith(f"{premier.json()['sha256']}.dxf")
