"""L'interface doit pouvoir appeler l'API depuis un navigateur.

CE QUE CES CAS EXISTENT POUR EMPÊCHER, ET COMMENT ON L'A TROUVÉ
-----------------------------------------------------------------
Les autres suites passent par ``TestClient``, qui n'applique **aucune**
politique d'origine : elles ne peuvent pas voir un CORS manquant. En pilotant
l'écran dans un vrai Chromium, l'appel de ``:3000`` vers ``:8000`` ne partait
pas — le navigateur refusait, faute d'en-tête.

Un test qui ne peut pas échouer sur une propriété ne la protège pas. Ces cas
regardent l'en-tête de réponse, ce que ``TestClient`` sait faire.

CE QU'ILS VÉRIFIENT AUSSI, ET QUI COMPTE AUTANT
------------------------------------------------
Que le joker est **refusé**. Un ``*`` laisserait n'importe quelle page du web
appeler cette API depuis le navigateur d'un utilisateur — c'est la commodité
qu'on ajoute « pour déboguer » et qu'on oublie de retirer.
"""
from __future__ import annotations

import pytest

ORIGINE_LOCALE = "http://localhost:3000"


def test_origine_declaree_est_autorisee(client):
    r = client.post(
        "/v1/calculations/ec2/beam-flexure",
        headers={"Origin": ORIGINE_LOCALE},
        json={
            "project_id": "X", "country": "BE", "strict_ndp": False,
            "M_Ed": {"value": 150.0, "unit": "kN*m"},
            "section": {"b": {"value": 300.0, "unit": "mm"},
                        "h": {"value": 500.0, "unit": "mm"},
                        "d": {"value": 450.0, "unit": "mm"}},
            "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
        },
    )
    assert r.headers.get("access-control-allow-origin") == ORIGINE_LOCALE


def test_prevol_options_est_accepte(client):
    """Le pré-vol du navigateur, celui qui bloquait réellement."""
    r = client.options(
        "/v1/calculations/ec2/beam-flexure",
        headers={
            "Origin": ORIGINE_LOCALE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code in (200, 204), r.text
    assert r.headers.get("access-control-allow-origin") == ORIGINE_LOCALE


def test_origine_inconnue_n_est_pas_autorisee(client):
    r = client.get("/health", headers={"Origin": "https://site-tiers.example"})
    # La reponse arrive — CORS s'applique dans le NAVIGATEUR — mais sans
    # l'en-tete qui l'autoriserait, et c'est lui qui fait la difference.
    assert r.headers.get("access-control-allow-origin") != "https://site-tiers.example"


def test_le_joker_est_refuse_par_la_configuration():
    """``*`` n'est pas une origine, c'est l'absence de politique."""
    from eurostruct_api.config import ConfigurationInvalide, charger

    with pytest.raises(ConfigurationInvalide) as refus:
        charger({"EUROSTRUCT_CORS_ORIGINS": "http://localhost:3000,*"})
    assert "joker" in str(refus.value) or "*" in str(refus.value)


def test_origine_sans_schema_est_refusee():
    from eurostruct_api.config import ConfigurationInvalide, charger

    with pytest.raises(ConfigurationInvalide):
        charger({"EUROSTRUCT_CORS_ORIGINS": "localhost:3000"})


def test_les_identifiants_ne_sont_pas_autorises(client):
    """L'identité voyage dans un en-tête explicite, jamais dans un cookie.

    ``allow_credentials=False`` est ce qui rend la falsification de requête
    inter-site sans objet : le navigateur ne joindra jamais de cookie tout
    seul à ces appels.
    """
    r = client.options(
        "/v1/authority/decisions",
        headers={"Origin": ORIGINE_LOCALE,
                 "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization"},
    )
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_content_disposition_est_expose_au_navigateur(client):
    """UN EN-TETE NON EXPOSE EST INVISIBLE A `fetch`, ET LE CLIENT INVENTE.

    L'ecran lit `Content-Disposition` pour savoir sous quel nom enregistrer un
    livrable. `fetch` ne rend QUE les en-tetes declares dans
    `Access-Control-Expose-Headers`; les autres existent dans la reponse et
    restent illisibles depuis JavaScript.

    MESURE DU JOUR, DANS UN VRAI CHROMIUM: le navigateur proposait
    « livrable-<id>.html » pour une note PDF, parce que le client retombait
    sur son nom de secours. Le systeme de l'utilisateur aurait ouvert un PDF
    avec un lecteur HTML.

    LE DEFAUT EXISTAIT DEJA POUR LE HTML et personne ne pouvait le voir: le
    nom de secours finissait en `.html`, ce qui se trouvait etre juste. Il a
    fallu un second format pour que le mensonge devienne visible.
    """
    r = client.get("/health", headers={"Origin": ORIGINE_LOCALE})

    exposes = {c.strip().lower()
               for c in (r.headers.get("access-control-expose-headers") or "")
               .split(",") if c.strip()}
    assert "content-disposition" in exposes, (
        "sans cet en-tete expose, l'ecran ne peut pas lire le nom du fichier "
        f"et en invente un. Exposes: {sorted(exposes)}")


@pytest.mark.parametrize("entete", [
    "content-disposition",
    "x-eurostruct-rebar-rows",
    "x-eurostruct-correlation-id",
])
def test_les_en_tetes_que_l_ecran_lit_sont_tous_exposes(client, entete):
    """CHACUN EST LU PAR UN CHEMIN DE L'INTERFACE.

    Le nom du fichier, le nombre de lignes de ferraillage, et l'identifiant de
    correlation qu'un utilisateur doit pouvoir citer quand il signale une
    panne. Un en-tete que le produit envoie mais que le navigateur cache est
    un en-tete qui n'existe pas.
    """
    r = client.get("/health", headers={"Origin": ORIGINE_LOCALE})
    exposes = {c.strip().lower()
               for c in (r.headers.get("access-control-expose-headers") or "")
               .split(",") if c.strip()}
    assert entete in exposes
