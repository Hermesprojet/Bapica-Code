"""Le trousseau sous concurrence, sous panne, et sous sonde.

CE QUE CE MODULE ÉPROUVE, ET QUI NE L'ÉTAIT PAR RIEN
-----------------------------------------------------
``test_jwt_negatif.py`` éprouve les refus d'un jeton mal formé. Il appelle le
trousseau depuis un seul fil, avec un lecteur qui répond toujours. Quatre
propriétés lui échappent entièrement, et chacune correspondait à un défaut :

1. **le rechargement n'était pas atomique.** ``_rechargement_autorise()`` et
   ``_recharger()`` étaient deux opérations distinctes. Dix requêtes portant le
   même ``kid`` inconnu passaient toutes le portillon avant qu'aucune n'ait
   posé la date — et lançaient dix appels réseau. Le bornage « au plus un par
   fenêtre » ne bornait rien sous charge, c'est-à-dire précisément quand un
   attaquant s'en sert ;

2. **un cache périmé était accepté indéfiniment.** ``_chercher`` rendait la clé
   déjà connue quand le rechargement échouait, sans aucune borne. Une panne du
   JWKS de plusieurs jours laissait donc accepter des jetons signés par une
   clé que l'émetteur avait révoquée — le contraire de ce que la rotation sert
   à obtenir ;

3. **``/ready`` rechargeait à chaque sonde.** Une sonde toutes les cinq
   secondes faisait un appel sortant toutes les cinq secondes vers Supabase.
   C'est nous qui martelions notre propre émetteur ;

4. **rien ne permettait de purger.** Une clé compromise ne pouvait être
   chassée du cache qu'en redémarrant le processus.

CE QUE CES CAS N'INTRODUISENT PAS
----------------------------------
Aucun secret, aucune instance externe, aucun réseau. Le lecteur est une
fonction locale qui compte ses appels — c'est ce qui permet de mesurer le
bornage au lieu de le supposer.
"""
from __future__ import annotations

import json
import threading
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from eurostruct_api.auth import jwks as module_jwks
from eurostruct_api.auth.jwks import (
    AGE_MAX_CACHE_PERIME_S,
    CleInconnue,
    JwksIndisponible,
    TrousseauJwks,
)

KID = "essai-1"


@pytest.fixture(scope="module")
def document_jwks() -> dict:
    from jwt.algorithms import RSAAlgorithm

    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


class LecteurCompte:
    """Un lecteur qui compte ses appels, et peut tomber en panne à volonté."""

    def __init__(self, document: dict, *, lenteur_s: float = 0.0) -> None:
        self.document = document
        self.lenteur_s = lenteur_s
        self.appels = 0
        self.en_panne = False
        self._verrou = threading.Lock()

    def __call__(self, _url: str) -> dict:
        with self._verrou:
            self.appels += 1
        if self.lenteur_s:
            time.sleep(self.lenteur_s)
        if self.en_panne:
            raise JwksIndisponible("panne simulee")
        return self.document


# --------------------------------------------------------------- concurrence
def test_un_seul_appel_reseau_pour_dix_kid_inconnus_simultanes(document_jwks):
    """LA BARRIÈRE DE CONCURRENCE.

    Dix fils demandent le même ``kid`` inconnu **en même temps**. Le lecteur
    est lent à dessein : sans single-flight, les dix franchissent le portillon
    avant que le premier n'ait posé sa date, et le compteur monte à dix.

    C'est le scénario d'un attaquant qui envoie mille jetons forgés : il ne
    doit pas piloter nos requêtes sortantes depuis un en-tête non authentifié.
    """
    lecteur = LecteurCompte(document_jwks, lenteur_s=0.25)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()
    # LA FENETRE DOIT ETRE OUVERTE POUR QU'IL Y AIT QUELQUE CHOSE A BORNER.
    # Juste apres un prechargement, un `kid` inconnu ne declenche RIEN — le
    # bornage a sa valeur la plus stricte, et le cas ci-dessous le verifie
    # separement. Ici on veut mesurer la barriere de concurrence, donc on se
    # place la ou un rechargement est permis.
    trousseau.vieillir_pour_essai(module_jwks.DELAI_RECHARGEMENT_S + 1)
    depart = lecteur.appels

    barriere = threading.Barrier(10)
    resultats: list[str] = []
    verrou = threading.Lock()

    def demander() -> None:
        barriere.wait()
        try:
            trousseau.cle_pour("kid-que-personne-ne-publie")
        except CleInconnue:
            with verrou:
                resultats.append("refus")

    fils = [threading.Thread(target=demander) for _ in range(10)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=30)

    assert len(resultats) == 10, "un fil n'a pas recu de refus"
    assert lecteur.appels - depart == 1, (
        f"{lecteur.appels - depart} appels reseau pour dix « kid » inconnus "
        "simultanes: le rechargement n'est pas atomique, et le bornage ne "
        "borne rien sous charge — c'est-a-dire quand un attaquant s'en sert."
    )


def test_le_bornage_par_fenetre_est_conserve(document_jwks):
    """Un `kid` inconnu, mille fois de suite: un seul appel."""
    lecteur = LecteurCompte(document_jwks)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()
    trousseau.vieillir_pour_essai(module_jwks.DELAI_RECHARGEMENT_S + 1)
    depart = lecteur.appels

    for _ in range(1000):
        with pytest.raises(CleInconnue):
            trousseau.cle_pour("inconnu")

    assert lecteur.appels - depart == 1, (
        f"{lecteur.appels - depart} appels pour mille « kid » inconnus")


def test_juste_apres_un_chargement_un_kid_inconnu_ne_declenche_rien(
        document_jwks):
    """LE BORNAGE A SA VALEUR LA PLUS STRICTE.

    Le trousseau vient d'etre charge: il connait l'etat de l'emetteur a la
    seconde pres. Un `kid` qu'il n'y a pas trouve n'y est pas — le redemander
    tout de suite n'apprendrait rien, et offrirait a un attaquant un appel
    sortant par jeton forge.
    """
    lecteur = LecteurCompte(document_jwks)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()
    depart = lecteur.appels

    for _ in range(50):
        with pytest.raises(CleInconnue):
            trousseau.cle_pour("inconnu")

    assert lecteur.appels == depart, (
        f"{lecteur.appels - depart} appel(s) reseau juste apres un "
        "chargement: un jeton forge pilote nos requetes sortantes.")


# ------------------------------------------------------- cache et péremption
def test_une_panne_courte_laisse_servir_une_cle_connue(document_jwks):
    """La tolérance existe, et elle est délibérée.

    Un trousseau périmé mais connu vaut mieux qu'un refus général pendant une
    panne réseau brève : refuser tous les jetons ressemble à une attaque et
    coupe le service pour une cause qui n'est pas de notre côté.
    """
    lecteur = LecteurCompte(document_jwks)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()

    lecteur.en_panne = True
    trousseau.vieillir_pour_essai(module_jwks.DUREE_DE_VIE_S + 1)

    assert trousseau.cle_pour(KID) is not None, (
        "une panne breve fait deja refuser une cle parfaitement connue")


def test_au_dela_de_l_age_maximal_meme_une_cle_connue_est_refusee(document_jwks):
    """LA BORNE QUI MANQUAIT, ET CE QU'ELLE EMPÊCHE.

    Sans elle, une panne du JWKS de plusieurs jours laissait accepter
    indéfiniment des jetons signés par une clé que l'émetteur avait peut-être
    révoquée entre-temps. La tolérance devenait permanente, et la rotation ne
    servait plus à rien.

    Au-delà de ``AGE_MAX_CACHE_PERIME_S``, le refus est explicite : c'est un
    503 pour l'appelant, pas un 401 — nous ne savons plus, nous ne prétendons
    pas savoir.
    """
    lecteur = LecteurCompte(document_jwks)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()

    lecteur.en_panne = True
    trousseau.vieillir_pour_essai(AGE_MAX_CACHE_PERIME_S + 1)

    with pytest.raises(JwksIndisponible) as refus:
        trousseau.cle_pour(KID)
    assert "perime" in str(refus.value).lower()


def test_la_borne_est_plus_longue_que_la_duree_de_vie() -> None:
    """Sinon la tolérance n'existerait pas: elle serait née déjà expirée."""
    assert AGE_MAX_CACHE_PERIME_S > module_jwks.DUREE_DE_VIE_S


# ------------------------------------------------------------------ la purge
def test_la_purge_chasse_les_cles_du_cache(document_jwks):
    """Une clé compromise doit pouvoir partir sans redémarrer le processus."""
    lecteur = LecteurCompte(document_jwks)
    trousseau = TrousseauJwks("https://fictif.invalid/jwks", lecteur=lecteur)
    trousseau.precharger()
    assert trousseau.cle_pour(KID) is not None

    trousseau.purger()
    assert trousseau.etat()["cles"] == 0

    # Et la demande suivante RECHARGE, plutôt que de refuser: purger n'est pas
    # se condamner.
    depart = lecteur.appels
    assert trousseau.cle_pour(KID) is not None
    assert lecteur.appels - depart == 1


def test_la_purge_n_est_exposee_par_aucune_route() -> None:
    """AUCUN ENDPOINT PUBLIC NE PURGE.

    Une route de purge, même « interne », est un moyen offert au premier venu
    de vider notre cache puis de nous faire marteler l'émetteur. La primitive
    existe pour l'exploitation en processus; elle ne s'appelle pas par HTTP.
    """
    from eurostruct_api.app import creer_application
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase

    app = creer_application(Reglages(
        auth=ReglagesAuth(jwks_url="", issuer="", audience="",
                          algorithmes=("RS256",)),
        base=ReglagesBase(dsn="")))
    # ON REGARDE LA SURFACE PUBLIQUE, pas la structure interne du routeur:
    # « aucun endpoint » est une propriete du contrat servi, et c'est ce que
    # l'OpenAPI decrit.
    chemins = set(app.openapi().get("paths", {}))
    interdits = [c for c in chemins
                 if "purge" in c or "jwks" in c or "cache" in c or
                 "trousseau" in c]
    assert not interdits, f"routes exposant le trousseau: {interdits}"


# ------------------------------------------------------------------- /ready
def test_ready_ne_martele_pas_l_emetteur(document_jwks, monkeypatch):
    """CINQ SONDES RAPPROCHÉES, UN SEUL APPEL RÉSEAU.

    ``/ready`` appelait ``precharger()``, qui recharge inconditionnellement.
    Une sonde toutes les cinq secondes — la valeur par défaut de la plupart des
    orchestrateurs — faisait donc un appel sortant toutes les cinq secondes
    vers Supabase, pour une information qui ne change pas à ce rythme. C'est
    nous qui martelions notre propre émetteur.

    La sonde vérifie désormais que le cache est **frais**, et ne va sur le
    réseau que s'il ne l'est pas.
    """
    from fastapi.testclient import TestClient

    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase

    lecteur = LecteurCompte(document_jwks)
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer="https://fictif.invalid/auth/v1",
                                 audience="authenticated",
                                 algorithmes=("RS256",))
    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn="")))
    app.state.authentificateur = AuthentificateurSupabase(
        reglages_auth,
        trousseau=TrousseauJwks(reglages_auth.jwks_url, lecteur=lecteur),
    )

    client = TestClient(app)
    for _ in range(5):
        client.get("/ready")

    assert lecteur.appels == 1, (
        f"{lecteur.appels} appels reseau pour cinq sondes rapprochees: "
        "/ready martele l'emetteur.")


def test_supabase_unverified_survit_a_un_ready_VERT(document_jwks, monkeypatch):
    """``SUPABASE_UNVERIFIED`` EST UN FAIT SUR LA VALIDATION, PAS UN VERDICT.

    Une rédaction antérieure rendait ``notes: ["SUPABASE_UNVERIFIED"]``
    **seulement quand ``ready`` était faux**. La note disparaissait donc au
    moment précis où quelqu'un pourrait la lire comme une garantie : sur un
    ``/ready`` vert. Or un ``/ready`` vert prouve que *cette* configuration
    répond — un émetteur local, un JWKS de décor — et rien du tout sur une
    instance Supabase réelle.

    IL FALLAIT UN ``/ready`` VERT POUR L'ÉPROUVER, et c'est ce qui manquait :
    une première rédaction de ce cas se contentait d'une application sans base,
    donc d'un ``/ready`` en 503. La note y était présente **dans les deux
    rédactions du code**, et remettre le défaut ne faisait tomber aucun cas.
    On force donc les deux verdicts et on vérifie que la note ne bouge pas.
    """
    from fastapi.testclient import TestClient

    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from eurostruct_api.routes import sante as module_sante

    lecteur = LecteurCompte(document_jwks)
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer="https://fictif.invalid/auth/v1",
                                 audience="authenticated",
                                 algorithmes=("RS256",))
    app = creer_application(Reglages(
        auth=reglages_auth,
        # DSN FICTIVE ET JAMAIS OUVERTE: seule sa PRESENCE est lue ici, et la
        # verification du provider est remplacee juste en dessous. Aucune
        # connexion n'est tentee, aucun secret n'existe.
        base=ReglagesBase(dsn="dbname=fictif-jamais-ouverte")))
    app.state.authentificateur = AuthentificateurSupabase(
        reglages_auth,
        trousseau=TrousseauJwks(reglages_auth.jwks_url, lecteur=lecteur),
    )
    app.state.fabrique_connexion = lambda: None
    monkeypatch.setattr(
        module_sante, "_verifier_provider",
        lambda _etat: {"nom": "provider_constructible", "ok": True,
                       "detail": {"factory": "remplace pour ce cas"}})

    corps = TestClient(app).get("/ready").json()
    assert corps["ready"] is True, (
        f"le decor ne rend pas un /ready vert: {corps['verifications']}")
    assert "SUPABASE_UNVERIFIED" in corps["notes"], (
        "la note disparait sur un /ready VERT — c'est-a-dire la ou elle "
        "serait lue comme une garantie de compatibilite Supabase.")


def test_supabase_unverified_est_la_aussi_quand_ready_refuse(document_jwks):
    """Et elle ne dépend pas davantage d'un échec: elle est inconditionnelle."""
    from fastapi.testclient import TestClient

    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase

    lecteur = LecteurCompte(document_jwks)
    reglages_auth = ReglagesAuth(jwks_url="https://fictif.invalid/jwks",
                                 issuer="https://fictif.invalid/auth/v1",
                                 audience="authenticated",
                                 algorithmes=("RS256",))
    app = creer_application(Reglages(auth=reglages_auth,
                                     base=ReglagesBase(dsn="")))
    app.state.authentificateur = AuthentificateurSupabase(
        reglages_auth,
        trousseau=TrousseauJwks(reglages_auth.jwks_url, lecteur=lecteur),
    )

    reponse = TestClient(app).get("/ready")
    assert reponse.status_code == 503
    corps = reponse.json()
    assert "SUPABASE_UNVERIFIED" in corps["notes"]
    # Et le JWKS, lui, EST joignable: la note n'est pas un effet de bord d'un
    # echec de configuration.
    noms = {v["nom"]: v["ok"] for v in corps["verifications"]}
    assert noms["jwks_joignable"] is True
