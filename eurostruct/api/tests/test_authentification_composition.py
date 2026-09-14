"""``POST /v1/authority/review-packages`` doit exiger un JWT VÉRIFIÉ.

LE DÉFAUT, ET CE QU'IL LAISSE SORTIR
-------------------------------------
La route déclare ``_jeton: str = Depends(jeton_porteur)``. ``jeton_porteur``
lit l'en-tête ``Authorization``, contrôle que le schéma est ``Bearer``, et rend
la chaîne qui suit. **Il ne vérifie rien d'autre** : ni signature, ni émetteur,
ni audience, ni expiration. Une dépendance qui s'arrête là ressemble à une
authentification et n'en est pas une — le refus qu'elle produit (en-tête
absent) est précisément celui qu'un attaquant ne rencontre jamais.

Ce que la route rend, elle, n'est pas anodin : le dossier de revue nomme la
**valeur** nationale, son unité, sa provenance, la référence exacte de
l'annexe, l'édition, la clause, le folio imprimé et l'empreinte du document
source. C'est le contenu d'une annexe **sous licence**, servi à qui écrit
``Authorization: Bearer x``.

CE QUE CES CAS ÉPROUVENT
-------------------------
L'authentificateur **de production** — ``AuthentificateurSupabase`` — pris sur
l'état de l'application, avec un trousseau JWKS local alimenté par une paire
RSA générée dans le processus de test (voir ``conftest``). La signature est
réellement vérifiée. Aucun secret réel, aucune base, aucune connexion.

CE QU'ILS ÉPROUVENT AUSSI, ET QU'ON OUBLIE FACILEMENT
------------------------------------------------------
Qu'aucune **transaction d'écriture** n'est ouverte pour autant. Composer un
dossier ne touche pas PostgreSQL : le registre est en mémoire. Brancher
``ouvrir_provider`` — qui, lui, ouvre une connexion — authentifierait
correctement et retiendrait une connexion du pool pour une lecture qui n'en a
pas besoin. Le cas ``test_...n_ouvre_aucune_connexion`` le verrouille.

Et que le validateur n'est pas **dupliqué** : la route doit passer par
l'authentificateur de l'état de l'application, pas par un second vérificateur.
Deux validateurs, c'est un de trop, et c'est toujours le plus faible qui finit
par décider.
"""
from __future__ import annotations

from .conftest import AUDIENCE, ISSUER

#: LE PARAMÈTRE COMPOSÉ. Belge, présent au registre, et confirmé par aucun
#: dispositif : c'est exactement celui qu'un écran d'autorité fait relire.
PAYS = "BE"
REGLE = "EN 1992-1-1:alpha_cc"

#: Ce qui ne doit JAMAIS sortir sans identité vérifiée. Ce sont les clés du
#: dossier composé — la valeur nationale et l'ancrage documentaire.
CHAMPS_SOUS_LICENCE = ("package", "digests", "summary")


def _brouillon() -> dict:
    """Le corps que l'écran envoie. Il ne porte aucune empreinte, ni acteur."""
    from eurostruct_engine.ndp import load_parameter_set

    p = load_parameter_set(PAYS, strict=False).find(REGLE)
    assert p is not None, "le decor suppose ce parametre au registre."
    return {
        "country_code": p.country_code,
        "rule_id": p.key,
        "statement": "FICTIF — releve dans l'annexe publiee.",
        "citations": [{
            "document_digest": p.source_doc_id,
            "quote": f"FICTIF — citation relevee pour {p.key}.",
            "page_printed": p.source_page or 1,
        }],
    }


def _composer(client, jeton: str | None):
    entetes = {} if jeton is None else {"Authorization": f"Bearer {jeton}"}
    return client.post("/v1/authority/review-packages", json=_brouillon(),
                       headers=entetes)


def _aucun_dossier(reponse) -> None:
    """Le refus ne doit rien laisser filtrer du dossier, même partiellement."""
    corps = reponse.json()
    for champ in CHAMPS_SOUS_LICENCE:
        assert champ not in corps, (
            f"la reponse de refus porte « {champ} »: le dossier est sorti "
            "quand meme.")
    # ET AUCUNE TRACE DE LA VALEUR NATIONALE, sous quelque forme que ce soit.
    assert "national_annex_reference" not in reponse.text
    assert "normative_spec_payload" not in reponse.text


# ===========================================================================
# 1. LE CAS QUI DOIT REUSSIR
# ===========================================================================
def test_un_jwt_valide_obtient_le_dossier(client, forger):
    """Le chemin légitime reste ouvert, et il rend bien le dossier complet."""
    r = _composer(client, forger())
    assert r.status_code == 200, r.text
    corps = r.json()
    assert sorted(corps["digests"]) == [
        "evidence_digest", "implementation_digest",
        "normative_spec_digest", "stack_digest"]
    assert corps["summary"]["national_annex_reference"]


# ===========================================================================
# 2. LE CAS DECISIF : UNE CHAINE QUELCONQUE
# ===========================================================================
def test_bearer_nimporte_quoi_n_obtient_aucun_dossier(client):
    """LE DÉFAUT, NOMMÉ.

    ROUGE AUJOURD'HUI : la route rend **200** et le dossier complet — valeur
    nationale, clause, folio, empreinte du document — à qui envoie une chaîne
    arbitraire. ``jeton_porteur`` a fait son travail (le schéma est ``Bearer``)
    et personne n'a vérifié le jeton.
    """
    r = _composer(client, "nimporte-quoi")
    assert r.status_code == 401, (
        "une chaine arbitraire obtient une reponse " f"{r.status_code}: "
        "la route n'authentifie personne.")
    assert r.headers.get("WWW-Authenticate") == "Bearer"
    _aucun_dossier(r)


# ===========================================================================
# 3. CHAQUE FAÇON D'AVOIR UN JETON FAUX
# ===========================================================================
def test_jeton_absent(client):
    r = _composer(client, None)
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_schema_inconnu(client, forger):
    """Un jeton parfaitement valide, présenté sous un schéma qu'on ne lit pas."""
    r = client.post("/v1/authority/review-packages", json=_brouillon(),
                    headers={"Authorization": f"Basic {forger()}"})
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_signature_invalide(client, forger):
    """Un caractère changé dans la signature. Le reste est irréprochable."""
    jeton = forger()
    corps, _, signature = jeton.rpartition(".")
    altere = corps + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    r = _composer(client, altere)
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_signe_par_une_cle_etrangere(client, forger, paire_rsa_etrangere):
    """Bien formé, bien daté, bonne audience — et signé par un inconnu.

    Le ``kid`` annoncé est celui de notre trousseau : celui qui forge prétend
    avoir signé avec une clé qu'il ne possède pas.
    """
    from .conftest import KID

    r = _composer(client, forger(cle=paire_rsa_etrangere["privee"], kid=KID))
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_mauvais_issuer(client, forger):
    """Un autre projet Supabase, correctement signé — par lui."""
    r = _composer(client, forger(iss="https://autre-projet.supabase.test/auth/v1"))
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_mauvaise_audience(client, forger):
    """Un jeton légitime destiné à une AUTRE application."""
    r = _composer(client, forger(aud="une-autre-application"))
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_jeton_expire(client, forger):
    r = _composer(client, forger(exp_dans_s=-1))
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


def test_sub_absent(client, forger):
    """Sans ``sub``, il n'y a personne derrière le jeton."""
    r = _composer(client, forger(sub=None))
    assert r.status_code == 401, r.text
    _aucun_dossier(r)


# ===========================================================================
# 4. SANS AUTHENTIFICATEUR, LE SERVICE N'EST PAS PRET — CE N'EST PAS UN 401
# ===========================================================================
def test_sans_authentificateur_le_service_repond_503(application, forger):
    """503, PAS 401 : ce n'est pas l'appelant qui est en faute.

    Et surtout **pas 200**. Un service mal configuré qui composerait quand
    même servirait le dossier à tout le monde — c'est le défaut d'aujourd'hui
    élevé à l'échelle du déploiement.
    """
    from fastapi.testclient import TestClient

    application.state.authentificateur = None
    with TestClient(application) as sans_auth:
        r = _composer(sans_auth, forger())
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["error"] == "service_non_pret"
    _aucun_dossier(r)


# ===========================================================================
# 5. LES DEUX CONTRAINTES DE MISE EN OEUVRE
# ===========================================================================
def test_la_composition_n_ouvre_aucune_connexion(application, forger):
    """AUTHENTIFIER N'EST PAS OUVRIR UNE TRANSACTION.

    Le correctif évident — brancher ``ouvrir_provider``, qui authentifie déjà —
    prendrait une connexion PostgreSQL par composition. Composer ne lit ni
    n'écrit en base : le registre est en mémoire. La connexion serait retenue
    pour rien, et ce genre de fuite ne se voit pas au premier appel.
    """
    from fastapi.testclient import TestClient

    appels: list[str] = []

    def _fabrique_qui_compte():
        appels.append("connexion")
        raise AssertionError(
            "la composition a demande une connexion PostgreSQL: elle ne lit "
            "ni n'ecrit en base, et la retenir prive le pool pour rien.")

    application.state.fabrique_connexion = _fabrique_qui_compte
    with TestClient(application) as avec_base:
        r = _composer(avec_base, forger())
    assert r.status_code == 200, r.text
    assert appels == [], f"{len(appels)} connexion(s) ouverte(s) pour composer."


def test_le_validateur_jwt_n_est_pas_duplique(application, forger):
    """La route doit passer par l'authentificateur DE L'APPLICATION.

    Un second vérificateur écrit sur place validerait peut-être aujourd'hui, et
    dériverait à la première correction apportée à l'autre. On le constate en
    comptant : l'authentificateur de l'état est appelé, et **exactement une
    fois** par requête.
    """
    from fastapi.testclient import TestClient

    vrai = application.state.authentificateur
    appels: list[str] = []

    class Compteur:
        est_fictif = vrai.est_fictif
        identite_de_l_authentificateur = vrai.identite_de_l_authentificateur

        def authentifier(self, jeton):
            appels.append(jeton)
            return vrai.authentifier(jeton)

    application.state.authentificateur = Compteur()
    with TestClient(application) as compte:
        r = _composer(compte, forger())
    assert r.status_code == 200, r.text
    assert len(appels) == 1, (
        f"{len(appels)} appel(s) a l'authentificateur de l'application: "
        "0 signifie un validateur duplique, plus de 1 une verification "
        "repetee par requete.")


# ===========================================================================
# 6. L'IDENTITE VERIFIEE NE CHANGE PAS CE QUI EST COMPOSE
# ===========================================================================
def test_le_dossier_ne_depend_pas_de_qui_le_demande(client, forger):
    """Le dossier sort du REGISTRE, pas du demandeur.

    Deux identités vérifiées différentes composant le même paramètre doivent
    obtenir la même spécification et la même empreinte d'implémentation. Si
    l'identité les déplaçait, l'attestation dirait « ce que A a vu » plutôt que
    « ce que la norme dit ».

    L'authentification qu'on vient d'ajouter est une **frontière**, pas une
    entrée : elle décide qui a le droit de demander, et rien de ce qui est
    rendu.
    """
    a = _composer(client, forger(sub="aaaaaaaa-1111-1111-1111-111111111111"))
    b = _composer(client, forger(sub="bbbbbbbb-2222-2222-2222-222222222222"))
    assert (a.status_code, b.status_code) == (200, 200), (a.text, b.text)

    for empreinte in ("normative_spec_digest", "implementation_digest",
                      "evidence_digest", "stack_digest"):
        assert a.json()["digests"][empreinte] == b.json()["digests"][empreinte], (
            f"« {empreinte} » depend de l'identite du demandeur.")
    assert a.json()["package"] == b.json()["package"]


# Le décor JWT est celui du `conftest` — il n'est pas recopié ici, et ces deux
# constantes en attestent : un second décor dériverait du premier, et les deux
# fichiers éprouveraient alors deux émetteurs en croyant parler du même.
assert ISSUER and AUDIENCE
