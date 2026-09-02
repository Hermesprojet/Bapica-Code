"""Entrer dans l'application quand on n'y est pas encore.

LE DÉFAUT QUE CE MODULE MESURE
-------------------------------
Tout le produit suppose une ligne dans ``organization_members``. Sans elle :

* ``GET /v1/projects`` rend une liste **vide** — pas une erreur, pas une
  explication, un écran nu ;
* ``POST /v1/projects`` refuse — « vous n'etes pas membre de cette
  organisation » ;
* et **aucune route ne permet d'en sortir**. Pas de création
  d'organisation, pas d'invitation, pas d'administration des membres.

La seule façon d'exister dans l'application était un ``insert`` fait à la main
par le propriétaire de la base. Autrement dit : le produit n'avait pas de
porte d'entrée. Un compte tout neuf, parfaitement authentifié, arrivait devant
un écran vide et ne pouvait rien faire — jamais.

CE QUE LE DÉCOR A DE PARTICULIER
---------------------------------
``db/test/entree_application.sh`` pose une base **sans aucune organisation**.
C'est le seul décor du dépôt qui parte de là, et c'est le seul qui puisse
mesurer l'entrée : un harnais qui pose d'avance les adhésions dont il a besoin
ne peut pas constater qu'on ne sait pas les créer.

LES QUATRE IDENTITÉS, ET CE QUE CHACUNE ÉPROUVE
-------------------------------------------------
* ``F`` — la fondatrice : elle crée son organisation et en devient ``owner`` ;
* ``I`` — l'invitée : elle rejoint par une invitation, jamais autrement ;
* ``T`` — le tiers : authentifié, jamais invité. Il ne doit **rien** voir, et
  aucune de ses tentatives ne doit lui apprendre ce qui existe ;
* ``X`` — l'opportuniste : il essaie les invitations révoquées, expirées,
  déjà consommées, et celles d'une autre organisation.

Aucun de ces comptes n'est réel. Aucune attestation produite ici n'est une
validation. ``SUPABASE_UNVERIFIED`` reste vrai.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
DSN_OBS = os.environ.get("EUROSTRUCT_E2E_DSN_OBS", "")
ACTEUR_F = os.environ.get("EUROSTRUCT_ENTREE_ACTEUR_F", "")
ACTEUR_I = os.environ.get("EUROSTRUCT_ENTREE_ACTEUR_I", "")
ACTEUR_T = os.environ.get("EUROSTRUCT_ENTREE_ACTEUR_T", "")
ACTEUR_X = os.environ.get("EUROSTRUCT_ENTREE_ACTEUR_X", "")
MAGASIN = os.environ.get("EUROSTRUCT_STORAGE_DIR", "")

DECOR_PRESENT = bool(DSN and DSN_OBS and ACTEUR_F and ACTEUR_I
                     and ACTEUR_T and ACTEUR_X)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason=("decor absent: ce module se lance par "
                "db/test/entree_application.sh, qui pose une base deployee "
                "SANS AUCUNE ORGANISATION et fournit les DSN par "
                "l'environnement."),
    ),
]

ISSUER = "https://fictif.entree.test/auth/v1"
AUDIENCE = "authenticated"
KID = "entree-1"
PAYS = "BE"


# --------------------------------------------------------------------- décor
@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _construire_application(cle):
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
def client(cle):
    from fastapi.testclient import TestClient

    return TestClient(_construire_application(cle))


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str, *, duree: int = 3600) -> str:
        maintenant = int(time.time())
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + duree},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


def _observer(requete: str, parametres: tuple = ()):
    """Une lecture directe, hors du produit. Pour CONSTATER, jamais pour agir."""
    import psycopg2

    connexion = psycopg2.connect(DSN_OBS)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute(requete, parametres)
            return curseur.fetchall()
    finally:
        connexion.close()


def _fonction_existe(nom: str) -> bool:
    lignes = _observer(
        "select count(*) from pg_proc p join pg_namespace n "
        "  on n.oid = p.pronamespace "
        " where n.nspname = 'public' and p.proname = %s", (nom,))
    return lignes[0][0] > 0


# ===========================================================================
# 1 — LE CUL-DE-SAC: CE QUE VOIT UN COMPTE TOUT NEUF
# ===========================================================================
def test_un_compte_authentifie_sans_organisation_ne_voit_rien(client, jeton):
    """UNE LISTE VIDE, PAS UNE ERREUR. C'est bien pire qu'un refus.

    Un refus s'explique. Un écran vide ressemble à un produit qui marche et
    qui n'a rien à montrer, et laisse son utilisateur chercher ce qu'il a mal
    fait.
    """
    r = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 200, r.text
    assert r.json()["projects"] == []


def test_sans_organisation_la_creation_de_projet_refuse(client, jeton):
    """LE CUL-DE-SAC, MESURÉ. Le refus est juste ; c'est la suite qui manquait.

    « Vous n'êtes pas membre de cette organisation » est exactement ce que la
    matrice d'autorisation doit dire. Le défaut n'est pas ce refus : c'est
    qu'aucune route ne permettait d'en sortir.
    """
    avant = _observer("select count(*) from projects")[0][0]
    r = client.post("/v1/projects",
                    json={"name": "FICTIF Premier projet", "country": PAYS,
                          "ndp_as_of": "2024-01-15"},
                    headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 422, r.text
    # LE MESSAGE NOMME LE CUL-DE-SAC, et c'est ce qui le rend mesurable:
    # « aucune organisation: cet acteur n'appartient a aucune organisation avec
    # un role d'ecriture ». Il dit ce qui manque; il ne disait pas encore
    # comment y remedier.
    assert "aucune organisation" in json.dumps(r.json()).lower()
    assert _observer("select count(*) from projects")[0][0] == avant


def test_la_base_ne_porte_aucune_organisation_au_depart(client, jeton):
    """LE DÉCOR EST BIEN CELUI QU'ON CROIT.

    Sans ce constat, tous les cas de ce module pourraient être verts pour la
    mauvaise raison : une organisation posée d'avance rendrait l'entrée
    inutile à prouver.
    """
    assert _observer("select count(*) from organizations")[0][0] == 0
    assert _observer("select count(*) from organization_members")[0][0] == 0




# ===========================================================================
# 2 — LA PORTE: FONDER SON BUREAU
# ===========================================================================
@pytest.fixture(scope="module")
def bureau(client, jeton) -> dict:
    """Le bureau de F. Fondé UNE fois, par la route réelle."""
    r = client.post("/v1/organizations",
                    json={"name": "FICTIF Bureau de la fondatrice",
                          "country": PAYS,
                          "display_name": "FICTIF Ing. F",
                          "professional_id": "FICTIF-ORDRE-ENTREE-1"},
                    headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 201, r.text
    return r.json()


def test_fonder_cree_l_organisation_ET_son_proprietaire(client, jeton, bureau):
    """ATOMIQUE, ET LES DEUX LIGNES LE PROUVENT.

    Une organisation sans propriétaire serait un bureau que personne ne peut
    administrer, et il faudrait un ``insert`` à la main pour l'en sortir : le
    cul-de-sac de départ, un cran plus loin.
    """
    assert bureau["member_role"] == "owner"
    assert bureau["name"] == "FICTIF Bureau de la fondatrice"

    lignes = _observer(
        "select o.created_by, m.user_id, m.role, m.is_active, m.display_name, "
        "       m.professional_id "
        "  from organizations o "
        "  join organization_members m on m.org_id = o.id "
        " where o.id = %s", (bureau["organization_id"],))
    assert len(lignes) == 1, "l'organisation n'a pas exactement un membre"
    cree_par, membre, role, actif, nom, ordre = lignes[0]
    assert str(cree_par) == ACTEUR_F, "le fondateur n'est pas l'acteur du jeton"
    assert str(membre) == ACTEUR_F
    assert role == "owner"
    assert actif is True
    assert nom == "FICTIF Ing. F"
    assert ordre == "FICTIF-ORDRE-ENTREE-1"


def test_le_fondateur_vient_du_jeton_pas_du_corps(client, jeton):
    """AUCUN CHAMP NE DÉSIGNE LE FONDATEUR, et en inventer un est refusé.

    Le contrat est ``Strict`` : un champ inconnu ne passe pas. Sans cela, il
    suffirait de mentir dans le corps pour fonder un bureau au nom d'un autre
    — et l'appartenance ne serait plus qu'une affirmation.
    """
    for champ in ("created_by", "user_id", "owner_id", "actor_id"):
        r = client.post("/v1/organizations",
                        json={"name": f"FICTIF Usurpation {champ}",
                              "country": PAYS, champ: ACTEUR_T},
                        headers=_entete(jeton(ACTEUR_F)))
        assert r.status_code == 422, (champ, r.status_code, r.text)
    assert _observer(
        "select count(*) from organizations where name like 'FICTIF Usurpation%%'"
    )[0][0] == 0


def test_un_double_clic_ne_fonde_pas_deux_bureaux(client, jeton):
    """LE MÊME NOM, DEUX FOIS, PAR LA MÊME PERSONNE: un seul bureau.

    Deux bureaux jumeaux laisseraient leur fondateur devant deux entrées dont
    il ne saurait pas laquelle est la sienne, et l'une resterait orpheline
    pour toujours.
    """
    corps = {"name": "FICTIF Bureau du double-clic", "country": PAYS}
    premier = client.post("/v1/organizations", json=corps,
                          headers=_entete(jeton(ACTEUR_F)))
    second = client.post("/v1/organizations", json=corps,
                         headers=_entete(jeton(ACTEUR_F)))
    assert premier.status_code == 201, premier.text
    assert second.status_code == 201, second.text
    assert premier.json()["organization_id"] == second.json()["organization_id"]
    assert _observer(
        "select count(*) from organizations where name = %s",
        ("FICTIF Bureau du double-clic",))[0][0] == 1


def test_deux_personnes_peuvent_fonder_le_meme_nom(client, jeton):
    """LA CONTRAINTE EST ``(fondateur, nom)``, PAS ``nom`` SEUL.

    Deux bureaux différents peuvent légitimement s'appeler « Études
    Structures » ; interdire cela ferait dépendre l'inscription du hasard de
    l'ordre d'arrivée.
    """
    corps = {"name": "FICTIF Etudes Structures", "country": PAYS}
    a = client.post("/v1/organizations", json=corps,
                    headers=_entete(jeton(ACTEUR_F)))
    b = client.post("/v1/organizations", json=corps,
                    headers=_entete(jeton(ACTEUR_X)))
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["organization_id"] != b.json()["organization_id"]


def test_une_fois_le_bureau_fonde_le_projet_passe(client, jeton, bureau):
    """LE CUL-DE-SAC EST FERMÉ, ET LA MESURE EST LE MÊME APPEL QU'AVANT.

    Le même ``POST /v1/projects`` qui refusait pour ``T`` aboutit pour ``F``,
    et la seule différence entre les deux est la porte d'entrée que ce lot
    ajoute.
    """
    r = client.post("/v1/projects",
                    json={"name": "FICTIF Premier projet du bureau",
                          "country": PAYS, "ndp_as_of": "2024-01-15",
                          "organization_id": bureau["organization_id"]},
                    headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 201, r.text
    assert r.json()["organization_id"] == bureau["organization_id"]
    assert r.json()["member_role"] == "owner"


def test_le_tiers_ne_voit_toujours_aucun_bureau(client, jeton, bureau):
    """L'AILLEURS SANS LEQUEL LE CLOISONNEMENT NE SE PROUVE PAS."""
    r = client.get("/v1/organizations", headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 200, r.text
    assert r.json() == []

    r = client.get("/v1/projects", headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 200, r.text
    assert r.json()["projects"] == []


# ===========================================================================
# 3 — L'INVITATION
# ===========================================================================
def _inviter(client, jeton, bureau, *, role="engineer", acteur=None,
             **extra) -> dict:
    r = client.post(
        f"/v1/organizations/{bureau['organization_id']}/invitations",
        json={"role": role, **extra},
        headers=_entete(jeton(acteur or ACTEUR_F)))
    assert r.status_code == 201, r.text
    return r.json()


def test_le_secret_n_est_pas_en_base_et_n_y_entre_jamais(client, jeton, bureau):
    """LA BASE NE CONNAÎT QUE ``sha256(jeton)``.

    Une fuite de sauvegarde, un journal trop bavard ou une lecture
    accidentelle ne rendent aucun lien utilisable — parce que la base ne
    détient pas ce qu'il faudrait pour cela.
    """
    emise = _inviter(client, jeton, bureau, label="FICTIF pour l'invitee")
    secret = emise["token"]
    assert len(secret) >= 32, "le secret est trop court pour etre imprevisible"

    empreinte = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    lignes = _observer(
        "select token_sha256 from organization_invitations where id = %s",
        (emise["invitation_id"],))
    assert lignes[0][0] == empreinte

    # LE SECRET N'EST DANS AUCUNE COLONNE DE LA LIGNE. On lit la ligne
    # ENTIERE, convertie en texte, et on y cherche le secret.
    entiere = _observer(
        "select organization_invitations::text from organization_invitations "
        " where id = %s", (emise["invitation_id"],))[0][0]
    assert secret not in entiere, (
        "le secret figure dans la ligne: la base detient de quoi rejouer le "
        "lien.")


def test_deux_invitations_ne_partagent_jamais_un_secret(client, jeton, bureau):
    """L'ENTROPIE, MESURÉE PLUTÔT QUE PROMISE."""
    secrets_vus = {_inviter(client, jeton, bureau)["token"] for _ in range(8)}
    assert len(secrets_vus) == 8


def test_la_liste_des_invitations_ne_rend_ni_secret_ni_empreinte(
        client, jeton, bureau):
    """L'EMPREINTE SUFFIRAIT à reconnaître un lien intercepté ailleurs.

    Elle n'aide en rien l'écran, et la publier annulerait une partie de ce que
    le stockage par empreinte protège.
    """
    emise = _inviter(client, jeton, bureau, label="FICTIF a ne pas divulguer")
    empreinte = hashlib.sha256(emise["token"].encode("utf-8")).hexdigest()

    r = client.get(f"/v1/organizations/{bureau['organization_id']}/invitations",
                   headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    corps = r.text
    assert emise["token"] not in corps
    assert empreinte not in corps

    vues = [i for i in r.json()["invitations"]
            if i["invitation_id"] == emise["invitation_id"]]
    assert len(vues) == 1
    assert vues[0]["state"] == "pending"


def test_l_invitation_est_a_usage_unique(client, jeton, bureau):
    """CONSOMMÉE UNE FOIS, ELLE NE SERT PLUS — même au même destinataire."""
    emise = _inviter(client, jeton, bureau, role="engineer")

    r = client.post("/v1/invitations/accept", json={"token": emise["token"]},
                    headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 200, r.text
    assert r.json()["organization_id"] == bureau["organization_id"]
    assert r.json()["member_role"] == "engineer"

    r = client.post("/v1/invitations/accept", json={"token": emise["token"]},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 422, r.text
    assert "inconnue, expiree, revoquee ou deja utilisee" in r.text

    # X N'EST PAS ENTRE. La ligne d'adhesion n'existe pas.
    assert _observer(
        "select count(*) from organization_members "
        " where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_X))[0][0] == 0


def test_une_invitation_revoquee_ne_sert_plus(client, jeton, bureau):
    emise = _inviter(client, jeton, bureau, role="viewer")
    r = client.delete(
        f"/v1/organizations/{bureau['organization_id']}/invitations/"
        f"{emise['invitation_id']}",
        headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 204, r.text

    r = client.post("/v1/invitations/accept", json={"token": emise["token"]},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 422, r.text
    assert _observer(
        "select count(*) from organization_members "
        " where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_X))[0][0] == 0


def test_une_invitation_expiree_ne_sert_plus(client, jeton, bureau):
    """L'EXPIRATION EST VÉRIFIÉE PAR LA BASE, pas par l'écran.

    Le décor vieillit la ligne directement — c'est un constat, pas un geste du
    produit : aucune route ne permet de faire expirer une invitation, et c'est
    correct.
    """
    import psycopg2

    emise = _inviter(client, jeton, bureau, role="viewer")
    connexion = psycopg2.connect(DSN_OBS)
    try:
        with connexion, connexion.cursor() as curseur:
            curseur.execute(
                "update organization_invitations "
                "   set created_at = now() - interval '30 days', "
                "       expires_at = now() - interval '1 hour' "
                " where id = %s", (emise["invitation_id"],))
    finally:
        connexion.close()

    r = client.post("/v1/invitations/accept", json={"token": emise["token"]},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 422, r.text
    assert "inconnue, expiree, revoquee ou deja utilisee" in r.text


def test_un_lien_invente_est_refuse_comme_les_autres(client, jeton):
    """LE MÊME REFUS DANS LES QUATRE CAS.

    Distinguer « ce lien n'existe pas » de « ce lien a expiré » apprendrait à
    qui essaie des liens au hasard quand il a visé juste.
    """
    r = client.post("/v1/invitations/accept",
                    json={"token": "FICTIF-lien-invente-au-hasard"},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 422, r.text
    assert "inconnue, expiree, revoquee ou deja utilisee" in r.text


def test_une_invitation_ne_s_accepte_pas_sans_jeton(client, jeton, bureau):
    """LE LIEN SEUL NE SUFFIT PAS.

    Une adhésion créée sans identité ne désignerait personne, et le premier
    passant entrerait dans le bureau.
    """
    emise = _inviter(client, jeton, bureau, role="viewer")
    r = client.post("/v1/invitations/accept", json={"token": emise["token"]})
    assert r.status_code == 401, r.text
    assert _observer(
        "select count(*) from organization_invitations "
        " where id = %s and accepted_at is not null",
        (emise["invitation_id"],))[0][0] == 0


def test_le_nom_professionnel_vient_de_l_invitation_pas_de_l_invite(
        client, jeton, bureau):
    """QUELQU'UN QUI CHOISIRAIT SON NOM POURRAIT SIGNER SOUS CELUI D'UN AUTRE.

    C'est exactement ce que 0009 et 0020 ferment en dérivant ce nom de
    l'adhésion. L'invitation le porte ; le corps de l'acceptation n'a aucun
    champ pour lui, et en inventer un est refusé.
    """
    emise = _inviter(client, jeton, bureau, role="validating_engineer",
                     display_name="FICTIF Ing. Validateur",
                     professional_id="FICTIF-ORDRE-ENTREE-9")

    r = client.post("/v1/invitations/accept",
                    json={"token": emise["token"],
                          "display_name": "FICTIF Quelqu'un d'autre"},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 422, ("un champ invente a ete accepte", r.text)

    r = client.post("/v1/invitations/accept", json={"token": emise["token"]},
                    headers=_entete(jeton(ACTEUR_X)))
    assert r.status_code == 200, r.text
    lignes = _observer(
        "select display_name, professional_id from organization_members "
        " where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_X))
    assert lignes[0] == ("FICTIF Ing. Validateur", "FICTIF-ORDRE-ENTREE-9")


def test_un_tiers_n_emet_aucune_invitation(client, jeton, bureau):
    """L'ÉMISSION EST UNE CAPACITÉ D'ADMINISTRATION, et T n'est même pas membre."""
    avant = _observer("select count(*) from organization_invitations")[0][0]
    r = client.post(
        f"/v1/organizations/{bureau['organization_id']}/invitations",
        json={"role": "owner"}, headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 422, r.text
    assert "membre" in r.text.lower()
    assert _observer(
        "select count(*) from organization_invitations")[0][0] == avant


def test_un_engineer_n_emet_aucune_invitation(client, jeton, bureau):
    """PORTER LE TRAVAIL N'EST PAS ADMINISTRER LE BUREAU.

    ``I`` est ``engineer`` dans ce bureau depuis le cas d'usage unique. Elle y
    calcule et y rédige ; elle ne décide pas qui entre.
    """
    avant = _observer("select count(*) from organization_invitations")[0][0]
    r = client.post(
        f"/v1/organizations/{bureau['organization_id']}/invitations",
        json={"role": "viewer"}, headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 422, r.text
    assert "n'administre pas" in r.text.lower()
    assert _observer(
        "select count(*) from organization_invitations")[0][0] == avant


# ===========================================================================
# 4 — L'ADMINISTRATION DES MEMBRES
# ===========================================================================
def test_le_proprietaire_voit_son_equipe(client, jeton, bureau):
    r = client.get(f"/v1/organizations/{bureau['organization_id']}/members",
                   headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    par_acteur = {m["user_id"]: m for m in r.json()["members"]}
    assert par_acteur[ACTEUR_F]["role"] == "owner"
    assert par_acteur[ACTEUR_F]["is_me"] is True
    assert par_acteur[ACTEUR_I]["role"] == "engineer"
    assert par_acteur[ACTEUR_I]["is_me"] is False
    assert ACTEUR_T not in par_acteur


def test_un_engineer_ne_voit_pas_l_annuaire(client, jeton, bureau):
    """LISTER LES MEMBRES EST UNE CAPACITÉ D'ADMINISTRATION."""
    r = client.get(f"/v1/organizations/{bureau['organization_id']}/members",
                   headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 422, r.text
    assert "n'administre pas" in r.text.lower()


def test_un_tiers_ne_voit_pas_l_annuaire_d_un_bureau_voisin(
        client, jeton, bureau):
    """ET LE REFUS NE LUI APPREND PAS SI CE BUREAU EXISTE."""
    r = client.get(f"/v1/organizations/{bureau['organization_id']}/members",
                   headers=_entete(jeton(ACTEUR_T)))
    assert r.status_code == 422, r.text
    assert "membre" in r.text.lower()

    inexistant = str(uuid.uuid4())
    autre = client.get(f"/v1/organizations/{inexistant}/members",
                       headers=_entete(jeton(ACTEUR_T)))
    assert autre.status_code == 422
    assert autre.json()["detail"]["detail"] == r.json()["detail"]["detail"], (
        "le refus distingue un bureau existant d'un bureau imaginaire.")


def test_on_ne_modifie_pas_sa_propre_adhesion(client, jeton, bureau):
    """SE PROMOUVOIR ET SE DONNER LE RÔLE QUI VALIDE SON PROPRE TRAVAIL

    sont le même geste vu de deux côtés. Aucun des deux ne passe.
    """
    for tentative in ({"role": "validating_engineer"}, {"is_active": False}):
        r = client.patch(
            f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_F}",
            json=tentative, headers=_entete(jeton(ACTEUR_F)))
        assert r.status_code == 422, (tentative, r.text)
        assert "sa propre adhesion" in r.text.lower()

    assert _observer(
        "select role, is_active from organization_members "
        " where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_F))[0] == ("owner", True)


def test_le_proprietaire_change_le_role_d_un_collegue(client, jeton, bureau):
    r = client.patch(
        f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_I}",
        json={"role": "validating_engineer"},
        headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "validating_engineer"

    r = client.patch(
        f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_I}",
        json={"role": "engineer"}, headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "engineer"


def test_desactiver_puis_reactiver_conserve_la_ligne(client, jeton, bureau):
    """LA LIGNE SURVIT, L'ACCÈS NON.

    Une note de dix ans doit rester lisible et nommer son signataire (0009).
    Ce qui disparaît en désactivant, c'est l'accès, pas la trace.
    """
    base = f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_I}"

    r = client.patch(base, json={"is_active": False},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    ligne = _observer(
        "select is_active, deactivated_at is not null, display_name "
        "  from organization_members where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_I))[0]
    assert ligne[0] is False and ligne[1] is True

    # L'ACCES EST REELLEMENT PARTI: elle ne voit plus le bureau.
    r = client.get("/v1/organizations", headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 200, r.text
    assert all(o["organization_id"] != bureau["organization_id"]
               for o in r.json())

    r = client.patch(base, json={"is_active": True},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True
    assert _observer(
        "select deactivated_at from organization_members "
        " where org_id = %s and user_id = %s",
        (bureau["organization_id"], ACTEUR_I))[0][0] is None


def test_le_dernier_proprietaire_actif_ne_disparait_pas(client, jeton, bureau):
    """NI PAR CHANGEMENT DE RÔLE, NI PAR DÉSACTIVATION.

    Un bureau sans propriétaire actif n'a plus personne pour administrer ses
    membres, et il faudrait un ``insert`` à la main pour l'en sortir — le
    cul-de-sac de départ, un cran plus loin.
    """
    # On promeut I proprietaire, puis on retrograde F: c'est permis, il reste
    # un proprietaire actif.
    base_i = f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_I}"
    base_f = f"/v1/organizations/{bureau['organization_id']}/members/{ACTEUR_F}"

    r = client.patch(base_i, json={"role": "owner"},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text

    # I, proprietaire, ne peut pas retirer le dernier proprietaire... mais il
    # y en a deux: elle peut retrograder F.
    r = client.patch(base_f, json={"role": "engineer"},
                     headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 200, r.text

    # DESORMAIS I EST SEULE PROPRIETAIRE. F ne peut plus rien administrer, et
    # I ne peut pas se retirer elle-meme (sa propre adhesion).
    r = client.patch(base_i, json={"role": "engineer"},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 422, r.text
    assert "n'administre pas" in r.text.lower()

    # On remet F proprietaire, puis on tente de retirer I: refuse tant que F
    # n'est pas actif proprietaire... F l'est de nouveau, donc c'est permis.
    r = client.patch(base_f, json={"role": "owner"},
                     headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 200, r.text
    r = client.patch(base_i, json={"role": "engineer"},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text

    # ET MAINTENANT, LE CAS DECISIF: F est seul proprietaire actif. On promeut
    # I administratrice, et elle tente de retirer F.
    r = client.patch(base_i, json={"role": "admin"},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    r = client.patch(base_f, json={"is_active": False},
                     headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 422, r.text
    # UN ADMIN NE TOUCHE PAS UN OWNER: c'est ce refus-la qui tombe en premier,
    # et il est plus etroit que celui du dernier proprietaire.
    assert "owner" in r.text.lower()

    assert _observer(
        "select count(*) from organization_members "
        " where org_id = %s and role = 'owner' and is_active",
        (bureau["organization_id"],))[0][0] >= 1


def test_un_admin_ne_donne_pas_plus_que_son_pouvoir(client, jeton, bureau):
    """IL N'INVITE PAS UN ``owner``, ET N'EN CRÉE PAS UN.

    Sans cette règle, un administrateur se fabriquerait un complice
    propriétaire et deviendrait propriétaire par la bande.
    """
    org = bureau["organization_id"]

    # I est administratrice depuis le cas precedent.
    r = client.post(f"/v1/organizations/{org}/invitations",
                    json={"role": "owner"}, headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 422, r.text
    assert "owner" in r.text.lower()

    # Elle invite en revanche un engineer sans difficulte.
    r = client.post(f"/v1/organizations/{org}/invitations",
                    json={"role": "engineer"},
                    headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 201, r.text

    # ET ELLE NE PROMEUT PERSONNE PROPRIETAIRE. X est validating_engineer dans
    # ce bureau depuis le cas du nom professionnel.
    r = client.patch(f"/v1/organizations/{org}/members/{ACTEUR_X}",
                     json={"role": "owner"}, headers=_entete(jeton(ACTEUR_I)))
    assert r.status_code == 422, r.text
    assert "owner" in r.text.lower()
    assert _observer(
        "select role from organization_members "
        " where org_id = %s and user_id = %s", (org, ACTEUR_X)
    )[0][0] == "validating_engineer"


def test_un_role_inconnu_est_refuse(client, jeton, bureau):
    org = bureau["organization_id"]
    r = client.post(f"/v1/organizations/{org}/invitations",
                    json={"role": "superviseur"},
                    headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 422, r.text
    assert "role connu" in r.text.lower()


def test_les_noms_ne_s_effacent_pas_par_un_formulaire_partiel(
        client, jeton, bureau):
    """``update_names`` DOIT ÊTRE DEMANDÉ.

    Sans lui, envoyer ``role`` seul remettrait à zéro le nom sous lequel
    quelqu'un a signé — et une note de dix ans le nommerait « null ».
    """
    org = bureau["organization_id"]
    base = f"/v1/organizations/{org}/members/{ACTEUR_X}"

    r = client.patch(base, json={"role": "viewer"},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert _observer(
        "select display_name from organization_members "
        " where org_id = %s and user_id = %s", (org, ACTEUR_X)
    )[0][0] == "FICTIF Ing. Validateur"

    r = client.patch(base, json={"display_name": "FICTIF Ing. Renomme",
                                 "professional_id": "FICTIF-ORDRE-ENTREE-9b",
                                 "update_names": True},
                     headers=_entete(jeton(ACTEUR_F)))
    assert r.status_code == 200, r.text
    assert _observer(
        "select display_name, professional_id from organization_members "
        " where org_id = %s and user_id = %s", (org, ACTEUR_X)
    )[0] == ("FICTIF Ing. Renomme", "FICTIF-ORDRE-ENTREE-9b")


def test_les_primitives_refusent_elles_memes_hors_de_toute_route(bureau):
    """LA FRONTIÈRE EST DANS POSTGRESQL, pas dans FastAPI.

    Un attaquant qui atteindrait la base ne passerait pas par les routes. On
    appelle donc les primitives DIRECTEMENT, sous l'identité d'un tiers, et
    l'on exige les mêmes refus.
    """
    import psycopg2

    org = bureau["organization_id"]
    tentatives = [
        ("select organization_member_list(%s::uuid)", (org,), ACTEUR_T,
         "membre"),
        (("select organization_invitation_create("
          "%s::uuid, 'owner'::org_role, %s, null, null, null, "
          "interval '1 day')"), (org, "a" * 64), ACTEUR_T, "membre"),
        (("select organization_member_update(%s::uuid, %s::uuid, "
          "'owner'::org_role, null, null, null, false)"),
         (org, ACTEUR_F), ACTEUR_T, "membre"),
    ]
    for sql, parametres, acteur, attendu in tentatives:
        cx = psycopg2.connect(DSN)
        try:
            cur = cx.cursor()
            cur.execute("begin")
            cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                        (acteur,))
            with pytest.raises(psycopg2.Error) as refus:
                cur.execute(sql, parametres)
            assert attendu in str(refus.value).lower(), (sql, str(refus.value))
        finally:
            cx.rollback()
            cx.close()


def test_le_backend_n_atteint_aucune_de_ces_tables_directement():
    """LA PROPRIÉTÉ EXACTE DONT DÉPEND LA BORNE D'ANNUAIRE.

    ``members_atelier_annuaire`` ouvre les lignes d'une organisation désignée
    par un réglage de transaction. Cela ne devient une **porte** que si un
    rôle peut à la fois poser ce réglage et lire la table. Le backend
    authentifié n'a aucun privilège de table : sa lecture est refusée par
    l'ACL, avant même que RLS ne soit consulté.

    Si ce cas devient rouge, le mécanisme est cassé — pas seulement le test.
    """
    for table in ("organization_members", "organization_invitations",
                  "organizations"):
        for droit in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            accorde = _observer(
                "select has_table_privilege("
                "  'eurostruct_authority_backend', %s, %s)",
                (table, droit))[0][0]
            assert accorde is False, (table, droit)
