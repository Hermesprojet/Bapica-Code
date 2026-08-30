"""Le parcours de calcul, de bout en bout, et ses refus.

CE QUE LA PREMIÈRE EXÉCUTION A APPRIS, ET QUI CHANGE LE PARCOURS PRODUIT
-------------------------------------------------------------------------
En mode strict — le défaut — le moteur **refuse pour la Belgique**, et il a
raison : les huit paramètres nationaux requis sont au statut
``pending_verification``. Personne n'a relevé les valeurs dans la NBN EN
1992-1-1 ANB publiée. C'est l'interdiction n°3 du projet appliquée : *jamais
d'Eurocode sans son Annexe Nationale*.

Ce n'est donc pas un cas limite, c'est **le** parcours utilisateur
d'aujourd'hui : un ingénieur qui lance un calcul reçoit un 422 portant la
liste exacte des huit paramètres à faire relever. L'interface doit rendre
cette liste actionnable, pas l'afficher comme une panne.

Les tests ci-dessous fixent ce comportement dans les deux sens :

* strict -> refus **structuré et complet** (la liste entière, en une passe) ;
* non strict -> résultat **marqué non signable**.

Aucun paramètre national n'est confirmé ici. Confirmer un NDP pour faire
passer un test reviendrait à signer à la place de l'ingénieur.
"""
from __future__ import annotations

import pytest

REQUETE_TYPE = {
    "project_id": "DEMO-001",
    "element": "P1",
    "country": "BE",
    "strict_ndp": True,
    "M_Ed": {"value": 150.0, "unit": "kN*m"},
    "section": {
        "b": {"value": 300.0, "unit": "mm"},
        "h": {"value": 500.0, "unit": "mm"},
        "d": {"value": 450.0, "unit": "mm"},
    },
    "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
}


def test_health_ne_touche_a_rien(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_refuse_sans_base(client):
    """Sans base configurée, le service n'est pas prêt — et il le dit."""
    r = client.get("/ready")
    assert r.status_code == 503
    corps = r.json()
    assert corps["ready"] is False
    noms = {v["nom"]: v["ok"] for v in corps["verifications"]}
    assert noms["base_configuree"] is False
    assert noms["provider_constructible"] is False


def test_ready_ne_revele_aucun_secret(client):
    """Un diagnostic qui recopie une valeur pour dire qu'elle existe fuit."""
    texte = client.get("/ready").text.lower()
    for interdit in ("password", "postgres://", "postgresql://",
                     "secret", "bearer ", "eyj"):
        assert interdit not in texte, f"« {interdit} » apparait dans /ready"


def test_mode_strict_refuse_et_nomme_les_huit_parametres(client):
    """LE PARCOURS D'AUJOURD'HUI: un refus complet, pas un résultat.

    Le refus porte la liste ENTIÈRE des paramètres bloquants, pour que
    l'ingénieur les fasse relever en une passe et non un par un.
    """
    r = client.post("/v1/calculations/ec2/beam-flexure", json=REQUETE_TYPE)
    assert r.status_code == 422, r.text
    corps = r.json()
    assert corps["error"] == "national_annex_incomplete"
    # UN REFUS N'EST JAMAIS UN RESULTAT PARTIEL.
    assert "result" not in corps
    prevol = corps["preflight"]
    assert prevol["ok"] is False
    assert prevol["strict"] is True
    assert len(prevol["blocking"]) == len(prevol["required"]) > 0
    # Chaque bloquant est ACTIONNABLE: il nomme la clause et l'annexe.
    for bloquant in prevol["blocking"]:
        assert bloquant["clause"]
        assert bloquant["national_annex_reference"]
        assert bloquant["reason"] == "pending_verification"


def test_mode_non_strict_calcule_mais_marque_non_signable(client):
    """L'autre moitié du parcours: des nombres, et une mention qui les encadre."""
    from eurostruct_api.routes.calculs import MENTION_NON_SIGNABLE

    r = client.post("/v1/calculations/ec2/beam-flexure",
                    json=dict(REQUETE_TYPE, strict_ndp=False))
    assert r.status_code == 200, r.text
    corps = r.json()
    resultat = corps["result"]
    assert resultat["As_required"]["unit"] == "mm**2"
    assert resultat["As_required"]["value"] > 0
    assert resultat["M_Rd"]["value"] > 0
    assert resultat["utilisation"] > 0
    assert "verification" in corps and "journal" in corps
    # LA MENTION VOYAGE DANS LA REPONSE, pas seulement dans l'interface: une
    # note produite par un autre client doit la porter aussi.
    assert corps["signable"] is False
    assert corps["mention"] == MENTION_NON_SIGNABLE
    assert "exploratoire" in corps["avertissement"]


def test_strict_ndp_est_vrai_par_defaut(client):
    """La couche HTTP ne renverse jamais le mode strict en silence."""
    requete = {k: v for k, v in REQUETE_TYPE.items() if k != "strict_ndp"}
    r = client.post("/v1/calculations/ec2/beam-flexure", json=requete)
    assert r.status_code == 422
    assert r.json()["preflight"]["strict"] is True


def test_entree_incoherente_est_refusee(client):
    """``d`` plus grand que ``h`` est incohérent: refus, jamais un résultat."""
    requete = dict(REQUETE_TYPE, strict_ndp=False)
    requete["section"] = dict(REQUETE_TYPE["section"],
                              d={"value": 900.0, "unit": "mm"})
    r = client.post("/v1/calculations/ec2/beam-flexure", json=requete)
    assert r.status_code in (400, 422), r.text
    assert "result" not in r.json()


def test_unite_invalide_est_refusee(client):
    """Une unité de moment exprimée en millimètres n'est pas une longueur."""
    requete = dict(REQUETE_TYPE, strict_ndp=False)
    requete["M_Ed"] = {"value": 150.0, "unit": "mm"}
    r = client.post("/v1/calculations/ec2/beam-flexure", json=requete)
    assert r.status_code in (400, 422), r.text
    assert "result" not in r.json()


def test_dxf_est_servi_comme_un_fichier(client):
    """Le DXF est le corps de la réponse, pas un champ encodé dans un JSON."""
    r = client.post("/v1/calculations/ec2/beam-section.dxf", json={
        "project": "DEMO-001", "element": "P1",
        "b": 300.0, "h": 500.0, "cover": 30.0, "link_diameter": 8.0,
        "bottom": [{"count": 3, "diameter": 16.0, "mark": "A1"}],
        "top": [{"count": 2, "diameter": 12.0, "mark": "A2"}],
        "link_spacing": 200.0,
    })
    if r.status_code == 422:
        pytest.skip(f"le service de dessin refuse cette section: {r.text[:200]}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/vnd.dxf")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"  0\nSECTION") or b"SECTION" in r.content[:200]
    assert int(r.headers["X-Eurostruct-Rebar-Rows"]) >= 1


# ---------------------------------------------------------------------------
# La mention obligatoire — interdiction n° 8
# ---------------------------------------------------------------------------
CORPS_EXPLORATOIRE = {
    "project_id": "X", "country": "BE", "strict_ndp": False,
    "M_Ed": {"value": 150.0, "unit": "kN*m"},
    "section": {"b": {"value": 300.0, "unit": "mm"},
                "h": {"value": 500.0, "unit": "mm"},
                "d": {"value": 450.0, "unit": "mm"}},
    "materials": {"concrete_grade": "C25/30", "steel_grade": "B500B"},
}


def test_toute_reponse_porte_la_mention_de_validation(client):
    """Le DXF la portait, la reponse JSON non — et c'est elle qu'on met en note.

    Le jour ou des parametres nationaux seront confirmes, un calcul strict
    rendra un resultat: sans ce champ, chaque client devrait penser a ajouter
    la mention, et l'interdiction n° 8 serait respectee par habitude plutot
    que par construction.
    """
    from eurostruct_engine.legal import Language, notice

    corps = client.post("/v1/calculations/ec2/beam-flexure",
                        json=CORPS_EXPLORATOIRE).json()
    assert corps["notice"] == notice(Language.FR)
    assert "ingenieur habilite" in corps["notice"]


def test_la_mention_et_la_non_signabilite_sont_deux_choses(client):
    """« pas encore signe » n'est pas « pas signable ».

    Les fusionner ferait disparaitre l'une des deux: soit un calcul strict
    perdrait la mention de validation, soit un calcul exploratoire cesserait
    d'annoncer qu'il ne peut PAS etre signe.
    """
    corps = client.post("/v1/calculations/ec2/beam-flexure",
                        json=CORPS_EXPLORATOIRE).json()
    assert corps["notice"] != corps["mention"]
    assert corps["mention"] == "PROJET — NON SIGNABLE"
    assert corps["signable"] is False


# ---------------------------------------------------------------------------
# Interdiction n° 6 — hors du domaine de validation, un refus EXPLICITE
# ---------------------------------------------------------------------------
def _hors_domaine(client, **remplacements):
    requete = dict(REQUETE_TYPE, strict_ndp=False, **remplacements)
    return client.post("/v1/calculations/ec2/beam-flexure", json=requete)


def test_une_classe_de_beton_hors_domaine_est_refusee_en_nommant_le_domaine(client):
    """« C200/250 » n'existe pas. Le refus doit dire ce qui existe.

    Un 422 qui se contente de refuser laisse l'ingenieur deviner: c'est le
    genre de refus qui pousse a desactiver le controle plutot qu'a corriger
    l'entree.
    """
    r = _hors_domaine(client, materials={"concrete_grade": "C200/250",
                                         "steel_grade": "B500B"})
    assert r.status_code == 422, r.text
    assert "result" not in r.json()
    message = r.text
    assert "C200/250" in message
    # Le domaine est ENUMERE, pas seulement refuse.
    assert "C25/30" in message and "C12/15" in message


def test_une_nuance_d_acier_inconnue_est_refusee_en_nommant_le_domaine(client):
    r = _hors_domaine(client, materials={"concrete_grade": "C25/30",
                                         "steel_grade": "B9000"})
    assert r.status_code == 422, r.text
    assert "result" not in r.json()
    assert "B9000" in r.text and "B500B" in r.text


def test_un_moment_hors_du_domaine_de_ductilite_est_refuse(client):
    """Au-dela de mu_lim, la section n'est plus ductile.

    Le moteur ne doit pas rendre une section « qui passe » en sortant du
    domaine ou ses formules ont ete eprouvees — c'est exactement ce que
    l'interdiction n° 6 vise, et un resultat serait ici plus dangereux qu'une
    absence de resultat.
    """
    r = _hors_domaine(client, M_Ed={"value": 1e9, "unit": "kN*m"})
    assert r.status_code == 422, r.text
    assert "result" not in r.json()
    assert "mu_lim" in r.text or "ductilite" in r.text


def test_un_pays_hors_referentiel_est_refuse_par_le_contrat(client):
    """Le contrat n'accepte que les quatre pays traites.

    Le refus est celui de la VALIDATION de requete, pas du domaine: « votre
    JSON nomme un pays que ce moteur ne traite pas » n'est pas « l'Eurocode
    refuse ». Confondre les deux formes ferait lire un defaut de saisie comme
    un verdict normatif.
    """
    r = _hors_domaine(client, country="IT")
    assert r.status_code == 422, r.text
    assert "result" not in r.json()
    assert "IT" in r.text
