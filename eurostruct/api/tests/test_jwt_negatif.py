"""Tout ce qu'un jeton peut avoir de faux, et le refus correspondant.

CE QUE CES CAS ÉPROUVENT
-------------------------
L'authentificateur **de production** — pas un double. Seule l'origine du
trousseau JWKS est locale, injectée par un paramètre prévu pour cela ; la
vérification de signature, elle, est bien celle qui tournera en production.

Aucun cas ne rend ``est_fictif = False`` sur un objet de test pour satisfaire
la factory : le seul objet qui répond ``False`` est
``AuthentificateurSupabase``, et il le justifie en vérifiant réellement une
signature.

L'ORDRE DES VÉRIFICATIONS COMPTE
---------------------------------
``pyjwt`` valide la signature **avant** les revendications. Un jeton signé
par une clé étrangère est donc refusé sans que sa charge utile ait été crue —
c'est ce que prouve ``test_jeton_signe_par_une_cle_etrangere``, dont la charge
est par ailleurs parfaitement bien formée.
"""
from __future__ import annotations

import time

import jwt
import pytest
from eurostruct_engine.ndp.postgres_provider import (
    AuthentificationRequise,
    ContexteAuthentifie,
)

from .conftest import AUDIENCE, ISSUER, KID, KID_AUTRE


# --------------------------------------------------------------- le cas positif
def test_jeton_valide_donne_une_identite(authentificateur, forger):
    """Le seul cas qui doit réussir, et il produit un contexte scellé."""
    contexte = authentificateur.authentifier(
        forger(sub="aaaaaaaa-1111-1111-1111-111111111111"))
    assert isinstance(contexte, ContexteAuthentifie)
    assert contexte.actor_id == "aaaaaaaa-1111-1111-1111-111111111111"
    assert contexte.emis_par == f"supabase:{ISSUER}"


def test_le_prefixe_bearer_est_tolere(authentificateur, forger):
    """Par commodité d'appel. Un schéma inconnu, lui, reste refusé."""
    contexte = authentificateur.authentifier("Bearer " + forger())
    assert contexte.actor_id


def test_authentificateur_reel_n_est_pas_fictif(authentificateur):
    """C'est ce qui l'autorise à passer la factory de production."""
    assert authentificateur.est_fictif is False
    assert "supabase:" in authentificateur.identite_de_l_authentificateur


# ------------------------------------------------------------- les refus, un a un
def test_jeton_absent(authentificateur):
    for vide in (None, "", "   ", 42, b"jeton"):
        with pytest.raises(AuthentificationRequise):
            authentificateur.authentifier(vide)


def test_jeton_mal_forme(authentificateur):
    with pytest.raises(AuthentificationRequise):
        authentificateur.authentifier("pas-un-jwt")


def test_signature_falsifiee(authentificateur, forger):
    """Un caractère changé dans la signature suffit."""
    jeton = forger()
    corps, _, signature = jeton.rpartition(".")
    altere = corps + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(AuthentificationRequise):
        authentificateur.authentifier(altere)


def test_jeton_signe_par_une_cle_etrangere(authentificateur, forger,
                                           paire_rsa_etrangere):
    """Bien formé, bien daté, bonne audience — et signé par un inconnu.

    Le ``kid`` annoncé est celui de NOTRE trousseau : l'attaquant prétend
    avoir signé avec une clé qu'il ne possède pas. La signature ne vérifie
    pas, et rien de la charge utile n'est cru.
    """
    jeton = forger(cle=paire_rsa_etrangere["privee"], kid=KID)
    with pytest.raises(AuthentificationRequise):
        authentificateur.authentifier(jeton)


def test_kid_inconnu(authentificateur, forger):
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(forger(kid=KID_AUTRE))
    assert "cle de signature inconnue" in str(refus.value)


def test_kid_absent(authentificateur, paire_rsa):
    """Choisir une clé « probable » reviendrait à deviner qui a signé."""
    jeton = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": "x",
                        "exp": int(time.time()) + 60},
                       paire_rsa["privee"], algorithm="RS256")
    with pytest.raises(AuthentificationRequise):
        authentificateur.authentifier(jeton)


def test_jeton_expire(authentificateur, forger):
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(forger(exp_dans_s=-1))
    assert "expire" in str(refus.value)


def test_jeton_pas_encore_valide(authentificateur, forger):
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(forger(nbf_dans_s=3600))
    assert "nbf" in str(refus.value)


def test_mauvaise_audience(authentificateur, forger):
    """Un jeton légitime destiné à une AUTRE application."""
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(forger(aud="une-autre-application"))
    assert "audience" in str(refus.value)


def test_mauvais_issuer(authentificateur, forger):
    """Un autre projet Supabase, correctement signé — par lui."""
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(
            forger(iss="https://autre-projet.supabase.test/auth/v1"))
    assert "issuer" in str(refus.value)


def test_sub_absent(authentificateur, forger):
    with pytest.raises(AuthentificationRequise):
        authentificateur.authentifier(forger(sub=None))


def test_sub_vide(authentificateur, forger):
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(forger(sub="   "))
    assert "sub" in str(refus.value)


def test_algorithme_none_refuse(authentificateur, paire_rsa):
    """``alg: none`` n'est pas une signature faible: ce n'est pas une signature."""
    entete = jwt.utils.base64url_encode(b'{"alg":"none","kid":"cle-de-test-1"}')
    charge = jwt.utils.base64url_encode(
        b'{"iss":"x","aud":"y","sub":"z","exp":9999999999}')
    jeton = f"{entete.decode()}.{charge.decode()}."
    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(jeton)
    assert "algorithme" in str(refus.value).lower()


def test_substitution_hs256_refusee(authentificateur, paire_rsa):
    """LA FAUTE CLASSIQUE, ET ELLE EST FERMÉE DEUX FOIS.

    L'attaquant prend la clé PUBLIQUE — que le JWKS publie — et signe en
    ``HS256``, où la même valeur sert à signer et à vérifier. Si le serveur
    acceptait ``HS256``, il validerait le jeton avec sa propre clé publique.

    Ici l'algorithme est refusé avant même d'atteindre ``jwt.decode``, et la
    configuration n'aurait de toute façon pas laissé ``HS256`` entrer dans la
    liste blanche.
    """
    import base64
    import hashlib
    import hmac
    import json

    from cryptography.hazmat.primitives import serialization

    pem = paire_rsa["publique"].public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # LE JETON EST FORGE A LA MAIN, ET C'EST NECESSAIRE. `jwt.encode` REFUSE
    # d'utiliser une cle asymetrique comme secret HMAC — PyJWT ferme deja la
    # porte cote emission. Un attaquant n'utilise pas notre bibliotheque: on
    # fabrique donc le jeton octet par octet, pour eprouver NOTRE refus a nous
    # plutot que celui de PyJWT.
    def _b64(donnees: bytes) -> str:
        return base64.urlsafe_b64encode(donnees).rstrip(b"=").decode()

    entete = _b64(json.dumps({"alg": "HS256", "kid": KID}).encode())
    charge = _b64(json.dumps({"iss": ISSUER, "aud": AUDIENCE,
                              "sub": "attaquant",
                              "exp": int(time.time()) + 3600}).encode())
    signature = _b64(hmac.new(pem, f"{entete}.{charge}".encode(),
                              hashlib.sha256).digest())
    jeton = f"{entete}.{charge}.{signature}"

    with pytest.raises(AuthentificationRequise) as refus:
        authentificateur.authentifier(jeton)
    assert "algorithme" in str(refus.value).lower()


def test_configuration_refuse_hs256(reglages_auth):
    """Et la liste blanche elle-même n'accepte pas d'algorithme symétrique."""
    from eurostruct_api.config import ConfigurationInvalide, charger

    with pytest.raises(ConfigurationInvalide) as refus:
        charger({"EUROSTRUCT_JWT_ALGORITHMS": "HS256"})
    assert "asymetriques" in str(refus.value)


# ------------------------------------------------------- rotation du trousseau
def test_rotation_des_cles(paire_rsa, paire_rsa_etrangere, reglages_auth):
    """Une clé qui apparaît APRÈS le premier chargement doit être acceptée.

    Sans rechargement, un trousseau figé au démarrage refuserait au bout de
    quelques semaines tous les jetons légitimes — et la panne ressemblerait à
    une attaque.
    """
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from .conftest import _jwk_de

    etat = {"keys": [_jwk_de(paire_rsa["publique"], KID)]}
    trousseau = TrousseauJwks("https://fictif.invalid/jwks",
                              lecteur=lambda _u: etat)
    auth = AuthentificateurSupabase(reglages_auth, trousseau=trousseau)

    # La nouvelle cle n'est pas encore publiee: refus.
    nouveau = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "s",
         "exp": int(time.time()) + 3600},
        paire_rsa_etrangere["privee"], algorithm="RS256",
        headers={"kid": KID_AUTRE})
    with pytest.raises(AuthentificationRequise):
        auth.authentifier(nouveau)

    # Supabase fait tourner ses cles; le trousseau publie les deux.
    etat["keys"] = [_jwk_de(paire_rsa["publique"], KID),
                    _jwk_de(paire_rsa_etrangere["publique"], KID_AUTRE)]
    # Le rechargement est BORNE dans le temps: on remet le compteur a zero
    # pour eprouver la rotation elle-meme, pas le delai.
    trousseau._dernier_rechargement = 0.0
    assert auth.authentifier(nouveau).actor_id == "s"


def test_kid_inconnu_ne_declenche_qu_un_appel_reseau(paire_rsa, reglages_auth):
    """UN KID INCONNU EST CE QU'UN ATTAQUANT ENVOIE.

    S'il déclenchait un appel réseau à chaque fois, le premier venu piloterait
    nos requêtes sortantes depuis un en-tête non authentifié. Mille jetons
    forgés doivent provoquer **au plus un** rechargement.
    """
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from .conftest import _jwk_de

    document = {"keys": [_jwk_de(paire_rsa["publique"], KID)]}
    trousseau = TrousseauJwks("https://fictif.invalid/jwks",
                              lecteur=lambda _u: document)
    auth = AuthentificateurSupabase(reglages_auth, trousseau=trousseau)
    trousseau.precharger()
    appels_apres_prechargement = trousseau.appels_reseau

    for _ in range(50):
        with pytest.raises(AuthentificationRequise):
            auth.authentifier(jwt.encode(
                {"iss": ISSUER, "aud": AUDIENCE, "sub": "s",
                 "exp": int(time.time()) + 60},
                paire_rsa["privee"], algorithm="RS256",
                headers={"kid": "kid-inconnu"}))

    supplementaires = trousseau.appels_reseau - appels_apres_prechargement
    assert supplementaires <= 1, (
        f"{supplementaires} appels reseau pour 50 jetons forges: un en-tete "
        "non authentifie pilote nos requetes sortantes")


def test_jwks_injoignable_est_un_refus(reglages_auth, forger):
    """Une panne réseau ne devient pas une porte ouverte.

    LE JETON DOIT ETRE BIEN FORME, sinon on n'éprouve rien. Première
    rédaction : ``authentifier("a.b.c")``. Le refus tombait — mais à la
    lecture de l'en-tête, bien avant toute recherche de clé. Le cas passait
    au vert sans jamais atteindre le JWKS qu'il prétendait éprouver.
    """
    from eurostruct_api.auth.jwks import JwksIndisponible, TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase

    def _casse(_url):
        raise JwksIndisponible("JWKS injoignable: simulation")

    auth = AuthentificateurSupabase(
        reglages_auth,
        trousseau=TrousseauJwks("https://fictif.invalid/jwks", lecteur=_casse))
    with pytest.raises(AuthentificationRequise) as refus:
        auth.authentifier(forger())          # en-tete valide, kid connu
    message = str(refus.value)
    assert "verifier la signature" in message
    assert "refus" in message.lower()


def test_authentificateur_non_configure_refuse(reglages_auth):
    """Sans issuer, audience ou JWKS, l'objet ne se construit pas."""
    from dataclasses import replace

    from eurostruct_api.auth.supabase import AuthentificateurSupabase

    for champ in ("jwks_url", "issuer", "audience"):
        with pytest.raises(AuthentificationRequise):
            AuthentificateurSupabase(replace(reglages_auth, **{champ: ""}))


# ------------------------------------------------- la frontiere du contexte
def test_contexte_ne_se_fabrique_pas_de_l_exterieur():
    """La garde de 6.3c: une donnée présentée comme une preuve est refusée."""
    with pytest.raises(AuthentificationRequise):
        ContexteAuthentifie(actor_id="je-suis-qui-je-veux", emis_par="moi")
