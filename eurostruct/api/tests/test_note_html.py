"""La note HTML sort des données gelées, et de rien d'autre.

CE QU'UNE NOTE DOIT POUVOIR SUPPORTER
--------------------------------------
Elle est envoyée par courriel, archivée dix ans au titre de la décennale, et
rouverte par quelqu'un qui n'a ni le serveur, ni le réseau, ni le même moteur.
Trois propriétés en découlent, et ce fichier les éprouve :

1. **elle ne recalcule rien** — les nombres viennent de la base ;
2. **elle est autonome** — aucun script, aucune ressource externe ;
3. **elle n'affirme jamais plus qu'elle ne sait** — pas de « final », la
   mention obligatoire partout, le filigrane quand le calcul est exploratoire.

Et deux propriétés de frontière : l'isolation inter-organisations est celle de
la réouverture, et un calcul sans résultat n'a pas de note.

Lancé par ``db/test/atelier_projet.sh``.
"""
from __future__ import annotations

import json
import os
import re
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

DSN = os.environ.get("EUROSTRUCT_E2E_DSN", "")
ACTEUR_A = os.environ.get("EUROSTRUCT_ATELIER_ACTEUR_A", "")
ACTEUR_B = os.environ.get("EUROSTRUCT_ATELIER_ACTEUR_B", "")

DECOR_PRESENT = bool(DSN and ACTEUR_A and ACTEUR_B)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not DECOR_PRESENT,
        reason="decor absent: ce module se lance par db/test/atelier_projet.sh.",
    ),
]

ISSUER = "https://fictif.atelier.test/auth/v1"
AUDIENCE = "authenticated"
KID = "atelier-1"

PAYS = "BE"
REGION = "Wallonie"
DATE_REF = "2024-01-15"

#: UN NOM DE PROJET QUI ESSAIE D'ETRE DU CODE. Une note se transmet: un nom
#: saisi par un humain et rendu tel quel deviendrait executable chez le
#: destinataire.
NOM_HOSTILE = 'FICTIF <script>alert("xss")</script> & "guillemets"'


@pytest.fixture(scope="module")
def cle():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def client(cle):
    from eurostruct_api.app import creer_application
    from eurostruct_api.auth.jwks import TrousseauJwks
    from eurostruct_api.auth.supabase import AuthentificateurSupabase
    from eurostruct_api.base import FabriqueConnexionPostgres
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from fastapi.testclient import TestClient
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(cle.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    ra = ReglagesAuth(jwks_url="https://fictif.invalid/jwks", issuer=ISSUER,
                      audience=AUDIENCE, algorithmes=("RS256",),
                      tolerance_horloge_s=0)
    app = creer_application(Reglages(auth=ra, base=ReglagesBase(dsn=DSN)))
    app.state.authentificateur = AuthentificateurSupabase(
        ra, trousseau=TrousseauJwks("https://fictif.invalid/jwks",
                                    lecteur=lambda _u: {"keys": [jwk]}))
    app.state.fabrique_connexion = FabriqueConnexionPostgres(ReglagesBase(dsn=DSN))
    return TestClient(app)


@pytest.fixture(scope="module")
def jeton(cle):
    def _jeton(sub: str) -> str:
        maintenant = int(time.time())
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": sub,
             "iat": maintenant - 5, "nbf": maintenant - 5,
             "exp": maintenant + 3600},
            cle, algorithm="RS256", headers={"kid": KID})

    return _jeton


def _entete(j: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {j}"}


def _corps(strict: bool = False) -> dict:
    return {
        "element": "P1", "strict_ndp": strict,
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 500.0, "unit": "mm"},
                    "d": {"value": 450.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 180.0, "unit": "kN*m"},
    }


@pytest.fixture(scope="module")
def dossier(client, jeton):
    """Un projet et un calcul abouti. Le décor de tous les cas positifs."""
    r = client.post("/v1/projects", headers=_entete(jeton(ACTEUR_A)),
                    json={"name": NOM_HOSTILE, "reference": "FICTIF-NOTE-01",
                          "country": PAYS, "region": REGION,
                          "ndp_as_of": DATE_REF})
    assert r.status_code == 201, r.text
    projet = r.json()

    c = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_corps(), headers=_entete(jeton(ACTEUR_A)))
    assert c.status_code == 201, c.text
    return projet, c.json()


def _note(client, jeton, projet_id: str, calcul_id: str, acteur: str = ACTEUR_A):
    return client.get(
        f"/v1/projects/{projet_id}/calculations/{calcul_id}/note.html",
        headers=_entete(jeton(acteur)))


# ===========================================================================
# 1. LE DOCUMENT EST AUTONOME
# ===========================================================================
def test_la_note_ne_contient_ni_script_ni_ressource_externe(client, jeton,
                                                            dossier):
    """CE QUI REND LA NOTE ARCHIVABLE.

    Un ``<script>`` la rendrait exécutable chez le destinataire ; une police
    ou une feuille distante la rendrait dépendante d'un serveur qui n'existera
    peut-être plus dans dix ans — et signalerait à ce serveur qu'on relit ce
    dossier.
    """
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    html = r.text

    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
    for motif in ("<link", "<iframe", "<object", "<embed", "srcset="):
        assert motif not in html.lower(), f"la note contient « {motif} »"
    # AUCUNE ADRESSE SORTANTE, sous aucune forme.
    assert not re.search(r"""(?i)(src|href)\s*=\s*["']?\s*(https?:)?//""", html)
    assert "@import" not in html
    assert "url(" not in html


def test_la_note_echappe_ce_qui_vient_d_un_humain(client, jeton, dossier):
    """Le nom du projet contient du HTML. Il doit s'afficher, pas s'exécuter."""
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"])
    assert r.status_code == 200, r.text
    assert "<script>alert" not in r.text
    assert "&lt;script&gt;" in r.text, (
        "le nom hostile n'apparait pas echappe: soit il a ete filtre en "
        "silence — et la note ne dit plus le nom du projet — soit il est "
        "passe tel quel.")
    assert "&amp;" in r.text and "&quot;" in r.text


def test_l_en_tete_interdit_l_execution_aussi(client, jeton, dossier):
    """LA POLITIQUE DOUBLE LE RENDU, elle ne le remplace pas.

    ``rendre_note`` n'émet aucun script ; l'en-tête garantit qu'un script
    introduit demain resterait inerte chez un client qui l'honore.
    """
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"])
    csp = r.headers.get("content-security-policy", "")
    assert "script-src 'none'" in csp
    assert "default-src 'none'" in csp
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "attachment" in r.headers.get("content-disposition", "")


# ===========================================================================
# 2. ELLE NE RECALCULE RIEN
# ===========================================================================
def test_la_note_affiche_les_nombres_enregistres(client, jeton, dossier):
    """CHAQUE NOMBRE VIENT DE LA BASE.

    On compare le taux de travail maximal du document à celui que l'API a
    rendu à la sauvegarde. Un écart signifierait qu'un calcul a eu lieu quelque
    part dans le chemin d'affichage — et c'est ce chiffre-là qu'un ingénieur
    lit en premier.
    """
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"])
    assert r.status_code == 200, r.text

    rapport = (calcul["result"] or {}).get("verification") or {}
    attendu = f"{float(rapport['max_utilisation']) * 100:.1f}".replace(".", ",")
    assert f"{attendu}&nbsp;%" in r.text, (
        f"le taux maximal enregistre ({attendu} %) n'apparait pas tel quel "
        "dans la note.")

    resultat = (calcul["result"] or {}).get("result") or {}
    as_requis = f"{float(resultat['As_required']['value']):.0f}"
    assert as_requis in r.text


def test_la_note_porte_le_contexte_le_moteur_et_les_empreintes(client, jeton,
                                                               dossier):
    """LA SECTION QUI REND LA NOTE VERIFIABLE.

    Sans elle, le document affirme des nombres sans dire quel code les a
    produits ni sous quel référentiel — et « 0.3.0 » ne désigne aucun code.
    """
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"])
    html = r.text

    # Le contexte du PROJET, pas celui du jour.
    assert PAYS in html
    assert REGION in html
    assert DATE_REF in html
    assert "FICTIF-NOTE-01" in html

    # Le moteur, exactement.
    assert calcul["engine_version"] in html
    assert calcul["engine_build_sha"] in html
    assert calcul["inputs_hash"] in html
    assert calcul["execution_identity"] in html

    # L'element et le journal.
    assert "P1" in html
    assert "Journal de calcul" in html


# ===========================================================================
# 3. ELLE N'AFFIRME JAMAIS PLUS QU'ELLE NE SAIT
# ===========================================================================
def test_la_note_porte_la_mention_obligatoire_et_le_filigrane(client, jeton,
                                                              dossier):
    """DEUX MENTIONS QUI NE DISENT PAS LA MEME CHOSE.

    ``notice`` — « doit être vérifié et signé » — est vraie de toute note.
    Le filigrane « PROJET — NON SIGNABLE » est conditionnel et bien plus
    fort : des paramètres non confirmés ont pu servir.
    """
    projet, calcul = dossier
    html = _note(client, jeton, projet["project_id"],
                 calcul["calculation_id"]).text

    assert "PROJET — NON SIGNABLE" in html, (
        "ce calcul est exploratoire et la note ne le dit pas.")
    assert "ing" in html.lower() and "sign" in html.lower(), (
        "la mention obligatoire de validation humaine est absente.")
    # ET AUCUNE PROMESSE DE FINALITE. Une note sans ligne de validation
    # nominative ne peut pas se dire finale, et le mot ne doit pas y apparaitre
    # comme un etat du document.
    assert "livrable final" in html, (
        "la note ne dit pas explicitement qu'elle n'est pas un livrable final.")
    assert not re.search(r"(?i)\b(document|note)\s+final\b", html)
    assert "validation nominative" in html


# ===========================================================================
# 4. LES DEUX FRONTIERES
# ===========================================================================
def test_une_autre_organisation_n_obtient_pas_la_note(client, jeton, dossier):
    """L'ISOLATION EST CELLE DE LA REOUVERTURE, parce que c'est le meme chemin."""
    projet, calcul = dossier
    r = _note(client, jeton, projet["project_id"], calcul["calculation_id"],
              acteur=ACTEUR_B)
    assert r.status_code == 422, r.text
    # LE REFUS NE DIT PAS CE QU'IL CACHE.
    assert NOM_HOSTILE not in r.text
    assert calcul["inputs_hash"] not in r.text


def test_sans_identite_la_note_n_est_pas_servie(client, dossier):
    """Un dossier nomme un client et des nombres: ce n'est pas public."""
    projet, calcul = dossier
    r = client.get(f"/v1/projects/{projet['project_id']}/calculations/"
                   f"{calcul['calculation_id']}/note.html")
    assert r.status_code == 401, r.text


def test_un_calcul_refuse_n_a_pas_de_note(client, jeton):
    """RENDRE UN DOCUMENT VIDE FERAIT PASSER UN REFUS POUR UNE NOTE.

    Le motif du refus est dans l'historique et à la réouverture — c'est là
    qu'un audit le cherche. Une note vide, elle, se transmet et se classe.
    """
    r = client.post("/v1/projects", headers=_entete(jeton(ACTEUR_A)),
                    json={"name": "FICTIF — note refusee", "country": PAYS,
                          "region": REGION, "ndp_as_of": DATE_REF})
    assert r.status_code == 201, r.text
    projet = r.json()

    # STRICT: aucun parametre belge n'est confirme sur cette base, le moteur
    # refuse, et le refus est enregistre.
    c = client.post(
        f"/v1/projects/{projet['project_id']}/calculations/ec2/beam-flexure",
        json=_corps(strict=True), headers=_entete(jeton(ACTEUR_A)))
    assert c.status_code == 422, c.text

    h = client.get(f"/v1/projects/{projet['project_id']}/calculations",
                   headers=_entete(jeton(ACTEUR_A)))
    lignes = h.json()["calculations"]
    assert len(lignes) == 1 and lignes[0]["status"] == "refused"

    note = _note(client, jeton, projet["project_id"],
                 lignes[0]["calculation_id"])
    assert note.status_code == 422, note.text
    assert "refus" in note.text.lower()
