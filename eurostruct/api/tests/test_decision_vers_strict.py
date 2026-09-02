"""De la décision consommée jusqu'au calcul strict, par les routes publiques.

CE QUE CE MODULE ÉPROUVE, ET QU'AUCUN AUTRE N'ÉPROUVE
-------------------------------------------------------
``test_e2e_postgres.py`` prouve que le quatre-yeux fonctionne : proposer,
refuser l'auto-approbation, approuver, consommer une fois. Il s'arrête là.
``test_passerelle.py`` prouve que la passerelle sait lire des confirmations et
ouvrir le portillon — mais il les lui **fournit** par un provider fictif.

Entre les deux, il manquait le fil : *une décision consommée produit-elle une
confirmation que le provider PostgreSQL relit ?* Les deux chemins étaient
disjoints, et aucun test ne pouvait le voir parce qu'aucun ne les traversait
tous les deux.

**AUCUN PROVIDER FICTIF ICI.** Le provider est celui de production, sur la base
jetable ; les jetons sont signés ; les routes sont publiques. La seule chose
qui ne soit pas de production est l'origine des clés RSA.

Lancé par ``db/test/decision_vers_strict.sh``, qui pose le décor et fournit les
DSN par l'environnement — jamais en argument, donc jamais visible dans ``ps``.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_E2E_ACTEUR_A", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_E2E_ACTEUR_B", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_A and ACTEUR_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/decision_vers_strict.sh."),
    ),
]

ISSUER = "https://fictif.decision.test/auth/v1"
AUDIENCE = "authenticated"
KID = "decision-1"
PAYS = "BE"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def application(cle):
    """L'application DE PRODUCTION. Seul le trousseau est local."""
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    trousseau = TrousseauJwks("https://fictif.invalid/jwks",
                              lecteur=lambda _u: {"keys": [jwk]})
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer=ISSUER, audience=AUDIENCE,
                                 algorithmes=("RS256",), tolerance_horloge_s=0)
    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn=DSN)))
    app.state.authentificateur = AuthentificateurSupabase(reglages_auth,
                                                          trousseau=trousseau)
    app.state.fabrique_connexion = FabriqueConnexionPostgres(ReglagesBase(dsn=DSN))
    return app


@pytest.fixture(scope="module")
def client(application):
    from fastapi.testclient import TestClient

    return TestClient(application)


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str) -> str:
        maintenant = int(time.time())
        import jwt as pyjwt

        return pyjwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + 3600},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


# ------------------------------------------------------------------ le calcul
def _requete_stricte() -> dict:
    return {
        "project_id": "FICTIF-DEC", "element": "P1", "country": PAYS,
        "strict_ndp": True,
        "M_Ed": {"value": 150, "unit": "kN*m"},
        "section": {"b": {"value": 300, "unit": "mm"},
                    "h": {"value": 500, "unit": "mm"},
                    "d": {"value": 450, "unit": "mm"}},
        "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
    }


def _blocages(client) -> list[str]:
    """Les clés que le calcul strict refuse, telles que l'API les rend."""
    r = client.post("/v1/calculations/ec2/beam-flexure", json=_requete_stricte())
    if r.status_code == 200:
        return []
    assert r.status_code == 422, r.text
    # LE CORPS EST L'`EngineErrorDTO` LUI-MEME, pas un `detail` qui l'enveloppe:
    # `reponse_de_refus` le rend tel quel, et son champ `detail` est une PHRASE.
    corps = r.json()
    preflight = corps.get("preflight") or {}
    return [b["key"] for b in preflight.get("blocking", [])]


def _parametre(cle: str):
    """La fiche du registre pour cette clé. On ne recopie rien à la main."""
    from eurostruct_engine.ndp import load_parameter_set

    jeu = load_parameter_set(PAYS, strict=True)
    p = jeu.find(cle)
    assert p is not None, f"{cle} absent du registre"
    return p


# ------------------------------------------------------- le dossier de revue
#
# CONSTRUIT PAR LES FONCTIONS CANONIQUES DU MOTEUR, jamais a la main. Les
# payloads doivent etre EXACTEMENT ce que `digest_of` produit: la projection
# reconstruit la pile et le dossier depuis la base et les confronte a leurs
# empreintes. Un JSON equivalent mais autrement serialise ne se rehacherait pas
# a la meme valeur.
#
# TOUT EST FICTIF SAUF LA VALEUR ET SA PROVENANCE, qui viennent du registre:
# la passerelle les compare, et les inventer ferait echouer le rapprochement —
# c'est precisement la garantie qu'on veut.
def dossier_pour(p) -> dict:
    from eurostruct_engine.ndp.canonical import (
        CANONICALIZATION_VERSION,
        digest_of,
        evidence_digest,
    )
    from eurostruct_engine.ndp.dossier import effet_normatif
    from eurostruct_engine.ndp.confirmation import (
        EvidenceItem,
        NormativeStack,
        NormativeStackComponent,
        required_sources,
    )

    assert p.source_doc_id, (
        f"{p.key} n'a pas d'empreinte de document deposee: aucune "
        "confirmation ne peut y etre rattachee")

    spec = digest_of({
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": p.key,
        "rule_type": "scalar",
        "output_unit": p.unit,
        "value_provenance": p.value_provenance.value,
        "scalar_value": p.parameter_value,
        "inputs": [], "domain": [], "expression_sources": [],
        "normative_authority": {
            "country_code": p.country_code,
            "reference": p.national_annex_reference,
            "edition": p.edition,
            "clause": p.clause,
            "effect": effet_normatif(p),
            "document_digest": p.source_doc_id,
        },
    })
    # L'EMPREINTE D'IMPLEMENTATION N'EST PLUS FABRIQUEE ICI. Elle se derive du
    # chemin de code declare qui lit et applique la regle: un dossier de test
    # qui en inventerait une serait refuse par la passerelle, et il aurait
    # raison de l'etre.
    from eurostruct_engine.ndp.implementation import empreinte_implementation
    impl = empreinte_implementation(p.key)
    pile = NormativeStack.of(
        country_code=p.country_code, standard_family=p.standard_family,
        part=p.part,
        components=(NormativeStackComponent(
            "annexe", p.national_annex_reference, p.edition, 1,
            p.source_doc_id),),
    )
    items = tuple(
        EvidenceItem(
            document_digest=s.document_digest, document_role=s.role,
            reference=s.reference, edition=s.edition or p.edition,
            clause=s.clause, page_printed=p.source_page or 1,
            quote=f"FICTIF — citation relevee pour {p.key}.",
            page_pdf=None,
        )
        for s in required_sources(spec)
    )
    preuve = evidence_digest(items)

    return {
        "rule_id": p.key,
        "statement": f"FICTIF — dossier de revue de {p.key}.",
        "digest_algorithm": "sha256",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "normative_spec_payload": spec.canonical_payload,
        "implementation_payload": impl.canonical_payload,
        "evidence_payload": preuve.canonical_payload,
        "stack_payload": pile.digest.canonical_payload,
    }


def proposition_pour(p) -> dict:
    return {
        "subject_kind": "ndp_parameter",
        "subject_id": p.key,
        "org_id": None,
        "country_code": p.country_code,
        "standard_family": p.standard_family,
        "part": p.part,
        "edition": p.edition,
        "permission": "can_validate_normative_reference",
        "reason": f"FICTIF revue de {p.key}",
        "review_package": dossier_pour(p),
    }


# ---------------------------------------------------------------- le parcours
def test_le_calcul_strict_refuse_et_nomme_ses_blocages(client):
    """Le point de départ, et il est mesuré, pas supposé."""
    blocages = _blocages(client)
    assert len(blocages) == 8, (
        f"{len(blocages)} blocage(s) au lieu de 8: {blocages}")


def test_une_decision_consommee_debloque_le_parametre_qu_elle_vise(client, jeton):
    """LE FIL QUI MANQUAIT, ÉPROUVÉ PAR LES ROUTES PUBLIQUES.

    A propose le dossier exact d'un paramètre, ne peut pas s'approuver, B
    approuve, la décision se consomme — et le calcul strict doit alors cesser
    de bloquer **sur cette clé-là**, et sur elle seule.

    Aujourd'hui ce cas est ROUGE : ``normative_decision_consume()`` change
    l'état de la décision et écrit l'audit, mais ne produit **aucun effet
    normatif**. Le provider ne relit donc rien, et le blocage demeure.
    """
    avant = _blocages(client)
    assert avant, "aucun blocage au depart: le cas ne prouverait rien"
    cle_visee = avant[0]
    p = _parametre(cle_visee)

    corps = proposition_pour(p)

    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]

    # A ne peut pas s'approuver.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text

    # B approuve.
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 204, r.text

    # Consommation.
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 200, r.text
    assert r.json()["consumed"] is True

    # ET LE CALCUL STRICT DOIT CESSER DE BLOQUER SUR CETTE CLE.
    apres = _blocages(client)
    assert cle_visee not in apres, (
        f"« {cle_visee} » bloque encore apres une decision CONSOMMEE. La "
        "decision a change d'etat sans produire d'effet normatif: aucune "
        "confirmation n'a ete creee, et le provider ne relit rien.")
    assert set(apres) == set(avant) - {cle_visee}, (
        "la consommation a debloque autre chose que le parametre vise: "
        f"avant {sorted(avant)}, apres {sorted(apres)}")


def test_une_consommation_cree_une_trace_normative_durable(client, jeton):
    """LA MOITIÉ QUE LE CODE DE RETOUR NE DIT PAS.

    Un 200 sur la consommation ne prouve pas qu'un effet a été produit — c'est
    exactement la leçon de ``autocommit=True``. On regarde la table depuis une
    AUTRE connexion.
    """
    import psycopg2

    avant = _blocages(client)
    assert avant
    cle_visee = avant[-1]
    p = _parametre(cle_visee)

    corps = proposition_pour(p)
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]
    client.post(f"/v1/authority/decisions/{decision_id}/approval",
                headers=_entete(jeton(ACTEUR_B)))
    client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                headers=_entete(jeton(ACTEUR_B)))

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(
                "select count(*) from normative_rule_confirmations "
                " where rule_id = %s", (cle_visee,))
            combien = curseur.fetchone()[0]
    finally:
        connexion.close()

    assert combien >= 2, (
        f"{combien} confirmation(s) pour « {cle_visee} » apres une decision "
        "consommee. Le quatre-yeux exige DEUX regards, et la consommation "
        "doit les produire de facon durable — sinon la decision n'a produit "
        "aucun effet normatif.")


def test_le_referentiel_versionne_reste_a_zero_sur_zero_vingt_neuf():
    """LE DÉCOR EST JETABLE, LE DÉPÔT NE BOUGE PAS.

    Rien de ce parcours n'écrit dans les fichiers du registre. Un `confirmed`
    y resterait, et le mode strict s'ouvrirait pour tout le monde.
    """
    from eurostruct_engine.ndp import available_countries, load_parameter_set

    for pays in available_countries():
        jeu = load_parameter_set(pays, strict=True)
        # SIM118 est un faux positif ici: `ParameterSet` n'est pas un dict et
        # n'expose pas `__iter__` — retirer `.keys()` casserait la boucle.
        utilisables = [k for k in jeu.keys()  # noqa: SIM118
                       if (p := jeu.find(k)) is not None
                       and p.usable_in_strict_mode]
        assert utilisables == [], f"{pays}: {utilisables}"


def test_aucun_corps_ne_peut_nommer_un_verificateur(client, jeton):
    """Le client ne fournit ni ``verifier_id``, ni proposant, ni approbateur."""
    corps = {
        "subject_kind": "ndp_parameter",
        "subject_id": "EN 1992-1-1:alpha_cc",
        "org_id": None, "country_code": PAYS,
        "standard_family": "EN 1992", "part": "1-1", "edition": "2010",
        "permission": "can_validate_normative_reference",
        "reason": "FICTIF",
        "verifier_id": str(uuid.uuid4()),
    }
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text


# ===========================================================================
# LES HUIT, PUIS LE CALCUL QUI ABOUTIT
# ===========================================================================
def _cycle(client, jeton, p, *, approbateur=None, consommer=True) -> str:
    """Un cycle complet A/B pour un parametre. Rend l'identifiant."""
    r = client.post("/v1/authority/decisions", json=proposition_pour(p),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(approbateur or ACTEUR_B)))
    assert r.status_code == 204, r.text
    if consommer:
        r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                        headers=_entete(jeton(ACTEUR_B)))
        assert r.status_code == 200, r.text
    return decision_id


# ===========================================================================
# LES CAS NEGATIFS — AUCUN NE CREE DE CONFIRMATION
# ===========================================================================
def _confirmations(rule_id: str) -> int:
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(
                "select count(*) from normative_rule_confirmations "
                " where rule_id = %s", (rule_id,))
            return curseur.fetchone()[0]
    finally:
        connexion.close()


def _un_parametre_neuf(client):
    """Une cle encore bloquee, pour que le cas parte d'un etat connu."""
    blocages = _blocages(client)
    assert blocages, "plus aucun blocage: les cas negatifs ne prouveraient rien"
    return _parametre(blocages[0])


def test_une_proposition_seule_ne_confirme_rien(client, jeton):
    p = _un_parametre_neuf(client)
    avant = _confirmations(p.key)
    r = client.post("/v1/authority/decisions", json=proposition_pour(p),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    assert _confirmations(p.key) == avant
    assert p.key in _blocages(client)


def test_une_approbation_non_consommee_ne_confirme_rien(client, jeton):
    p = _un_parametre_neuf(client)
    avant = _confirmations(p.key)
    _cycle(client, jeton, p, consommer=False)
    assert _confirmations(p.key) == avant
    assert p.key in _blocages(client)


def test_une_auto_approbation_ne_confirme_rien(client, jeton):
    p = _un_parametre_neuf(client)
    avant = _confirmations(p.key)
    r = client.post("/v1/authority/decisions", json=proposition_pour(p),
                    headers=_entete(jeton(ACTEUR_A)))
    decision_id = r.json()["decision_id"]
    r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 422, r.text
    assert _confirmations(p.key) == avant


def test_un_rejeu_de_consommation_ne_cree_pas_un_troisieme_regard(client, jeton):
    p = _un_parametre_neuf(client)
    decision_id = _cycle(client, jeton, p)
    apres_un = _confirmations(p.key)
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 422, r.text
    assert _confirmations(p.key) == apres_un, (
        "le rejeu a produit une attestation supplementaire")


@pytest.mark.parametrize("nom,ecart", [
    ("valeur", {"scalar_value": 999.0}),
    ("provenance", {"value_provenance": "eurocode_recommended"}),
    ("unite", {"output_unit": "FICTIF-unite"}),
])
def test_un_dossier_qui_ne_correspond_pas_au_registre_ne_debloque_pas(
        client, jeton, nom, ecart):
    """LE DOSSIER PEUT ETRE SIGNE DEUX FOIS ET NE RIEN DEBLOQUER.

    Les deux signatures sont authentiques et la decision est consommee: la
    base a bien produit son effet. Mais la passerelle confronte le dossier au
    REGISTRE, et un dossier qui parle d'un autre nombre ne confirme pas
    celui-la.
    """
    import json as _json

    p = _un_parametre_neuf(client)
    corps = proposition_pour(p)
    spec = _json.loads(corps["review_package"]["normative_spec_payload"])
    spec.update(ecart)
    from eurostruct_engine.ndp.canonical import digest_of

    corps["review_package"]["normative_spec_payload"] = \
        digest_of(spec).canonical_payload

    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]
    client.post(f"/v1/authority/decisions/{decision_id}/approval",
                headers=_entete(jeton(ACTEUR_B)))
    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 200, r.text

    assert p.key in _blocages(client), (
        f"un ecart de {nom} a quand meme debloque le parametre")


@pytest.mark.parametrize("nom,ecart", [
    ("pays", {"country_code": "FR"}),
    ("edition", {"edition": "FICTIF-autre-edition"}),
])
def test_une_portee_qui_ne_correspond_pas_est_refusee(client, jeton, nom, ecart):
    """La portee de la decision doit etre couverte par une habilitation."""
    p = _un_parametre_neuf(client)
    corps = proposition_pour(p)
    corps.update(ecart)
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, (
        f"une portee au mauvais {nom} a ete acceptee: {r.text}")


def test_un_dossier_absent_est_refuse_a_la_proposition(client, jeton):
    """Une decision « ndp_parameter » sans dossier ne pourrait rien produire.

    On la refuse LA OU L'AUTEUR PEUT ENCORE CORRIGER, pas a la consommation
    d'une decision deja approuvee par deux personnes.
    """
    p = _un_parametre_neuf(client)
    corps = proposition_pour(p)
    del corps["review_package"]
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert "dossier" in r.text.lower()


def test_un_dossier_dont_la_citation_est_retouchee_est_refuse(client, jeton):
    """La citation est scellee par son empreinte, et le scelle est verifie."""
    import json as _json

    p = _un_parametre_neuf(client)
    corps = proposition_pour(p)
    preuve = _json.loads(corps["review_package"]["evidence_payload"])
    preuve["items"][0]["quote"] = "FICTIF — citation retouchee apres coup."
    corps["review_package"]["evidence_payload"] = _json.dumps(
        preuve, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text


# ------------------------------------------- le dossier vient DU SERVEUR
#
# LE NAVIGATEUR NE CONSTRUIT AUCUNE EMPREINTE NORMATIVE. Il nomme le
# parametre du plan de charge et fournit la matiere humaine — le texte releve
# dans l'annexe publiee. Le serveur canonicalise, hache, et rend le dossier
# exact a proposer. Ces cas eprouvent ce chemin-la, celui de l'interface.
def _brouillon(p, statement="FICTIF — dossier compose par le serveur.") -> dict:
    return {
        "country_code": p.country_code,
        "rule_id": p.key,
        "statement": statement,
        "citations": [{
            "document_digest": p.source_doc_id,
            "quote": f"FICTIF — citation relevee pour {p.key}.",
            "page_printed": p.source_page or 1,
        }],
    }


def test_le_serveur_compose_le_dossier_et_rend_ses_empreintes(client, jeton):
    """Le point d'entree de l'ecran d'autorite: composer, pas fabriquer."""
    p = _un_parametre_neuf(client)
    r = client.post("/v1/authority/review-packages", json=_brouillon(p),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    corps = r.json()

    # LES QUATRE EMPREINTES SONT RENDUES, ET LE CLIENT N'EN A ENVOYE AUCUNE.
    assert sorted(corps["digests"]) == [
        "evidence_digest", "implementation_digest",
        "normative_spec_digest", "stack_digest"]
    assert all(len(e) == 64 for e in corps["digests"].values())

    # ET LE RESUME PORTE CE QU'UN INGENIEUR DOIT LIRE AVANT D'APPROUVER —
    # depuis le REGISTRE, jamais depuis l'ecran.
    resume = corps["summary"]
    assert resume["value"] == p.parameter_value
    assert resume["unit"] == p.unit
    assert resume["value_provenance"] == p.value_provenance.value
    assert resume["national_annex_reference"] == p.national_annex_reference
    assert resume["edition"] == p.edition
    assert resume["clause"] == p.clause


def test_le_dossier_compose_par_le_serveur_debloque_le_parametre(client, jeton):
    """LE PARCOURS DE L'INTERFACE, DE BOUT EN BOUT.

    Composer, proposer ce dossier-la sans y toucher, A refusee, B approuve,
    consommer — et le blocage disparait. C'est le meme fil que plus haut, mais
    parti du dossier que le SERVEUR a compose, comme l'ecran le fait.
    """
    p = _un_parametre_neuf(client)
    r = client.post("/v1/authority/review-packages", json=_brouillon(p),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    paquet = r.json()["package"]

    corps = proposition_pour(p)
    corps["review_package"] = paquet
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]

    for acteur, attendu in ((ACTEUR_A, 422), (ACTEUR_B, 204)):
        r = client.post(f"/v1/authority/decisions/{decision_id}/approval",
                        headers=_entete(jeton(acteur)))
        assert r.status_code == attendu, r.text

    r = client.post(f"/v1/authority/decisions/{decision_id}/consumption",
                    headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 200, r.text
    assert p.key not in _blocages(client)


def test_b_relit_le_dossier_gele_avant_d_approuver(client, jeton):
    """SANS CETTE LECTURE, « B A APPROUVE » VEUT DIRE « B A CLIQUE ».

    B n'a que l'identifiant: A s'est deconnecte et son jeton est parti avec
    lui. La relecture rend le dossier tel que PostgreSQL le conserve, et les
    empreintes RECALCULEES sur ce contenu — pas reprises d'un champ stocke a
    cote, qui s'accorderait avec lui par construction.
    """
    p = _un_parametre_neuf(client)
    r = client.post("/v1/authority/review-packages", json=_brouillon(p),
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 200, r.text
    compose = r.json()

    corps = proposition_pour(p)
    corps["review_package"] = compose["package"]
    r = client.post("/v1/authority/decisions", json=corps,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 201, r.text
    decision_id = r.json()["decision_id"]

    # B RELIT, SOUS SA PROPRE IDENTITE.
    r = client.get(f"/v1/authority/decisions/{decision_id}",
                   headers=_entete(jeton(ACTEUR_B)))
    assert r.status_code == 200, r.text
    relu = r.json()

    assert relu["state"] == "PENDING"
    assert relu["subject_id"] == p.key
    assert relu["country_code"] == p.country_code
    assert relu["edition"] == p.edition
    # OCTET POUR OCTET: ce que B lit est ce que A a propose.
    assert relu["package"] == compose["package"]
    assert relu["digests"] == compose["digests"]
    # ET AUCUN ACTEUR N'EST RENDU.
    assert "proposer_id" not in relu and "approver_id" not in relu


def test_la_relecture_exige_une_identite(client):
    """Un dossier nomme un document sous licence: ce n'est pas public."""
    r = client.get("/v1/authority/decisions/"
                   "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401, r.text


def test_le_serveur_refuse_de_composer_un_dossier_incomplet(client, jeton):
    """Sans citation correspondante, aucune empreinte de preuve n'est produite.

    Une couverture documentaire non verifiee produirait une empreinte
    parfaitement valide, et parfaitement fausse.
    """
    p = _un_parametre_neuf(client)
    brouillon = _brouillon(p)
    brouillon["citations"][0]["document_digest"] = "ff" * 32
    r = client.post("/v1/authority/review-packages", json=brouillon,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 422, r.text
    assert "citation" in r.text.lower()


def test_le_serveur_refuse_de_composer_un_parametre_absent(client, jeton):
    """On ne compose pas un dossier pour ce que le registre ne porte pas."""
    p = _un_parametre_neuf(client)
    brouillon = _brouillon(p)
    brouillon["rule_id"] = "EN 1992-1-1:parametre_qui_n_existe_pas"
    r = client.post("/v1/authority/review-packages", json=brouillon,
                    headers=_entete(jeton(ACTEUR_A)))
    assert r.status_code == 404, r.text


# ===========================================================================
# EN DERNIER: LES HUIT, PUIS LE CALCUL QUI ABOUTIT
# ===========================================================================
#
# CE CAS DEBLOQUE TOUT, DONC IL PASSE APRES LES AUTRES. Les cas negatifs ont
# besoin d'au moins une cle encore bloquee pour prouver qu'ils ne debloquent
# rien; place avant eux, il leur retirait leur sujet et ils echouaient sur
# « plus aucun blocage » — un rouge honnete, mais qui parlait de l'ordre des
# cas et non du produit.
def test_les_huit_parametres_puis_le_calcul_strict_aboutit(client, jeton):
    """LA DEFINITION DE TERMINE, EXECUTEE.

    Chaque cycle retire UNE cle des blocages, mecaniquement. Apres les huit,
    le calcul strict rend 200 et `strict_ndp_satisfied` vaut true.

    Le decor est jetable: rien de ceci ne touche le registre versionne, qui
    reste a 0 sur 29 — un cas voisin le verifie.
    """
    restants = _blocages(client)
    assert restants, "aucun blocage: le cas ne prouverait rien"

    while restants:
        avant = len(restants)
        cible = restants[0]
        _cycle(client, jeton, _parametre(cible))
        restants = _blocages(client)
        assert cible not in restants, f"« {cible} » bloque encore"
        assert len(restants) == avant - 1, (
            f"un cycle sur « {cible} » a change {avant - len(restants)} "
            "blocage(s): la superposition n'est pas etroite")

    r = client.post("/v1/calculations/ec2/beam-flexure", json=_requete_stricte())
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["strict_ndp_satisfied"] is True
    assert corps["exploratory"] is False
    assert corps["result"]["As_required"]["value"] > 0
