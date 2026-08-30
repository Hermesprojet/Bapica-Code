"""Ce qu'un refus d'autorité a le droit de dire, et ce qu'il ne doit jamais dire.

LE DÉFAUT, ET POURQUOI IL EST GRAVE
------------------------------------
Les trois routes d'autorité attrapaient ``Exception`` et la rendaient en
**422** avec ``str(cause)`` dans le corps. Le raisonnement était « un refus SQL
reste un refus » — vrai pour ``ConfirmationDomainError``, faux pour tout le
reste.

``psycopg2.OperationalError`` porte la chaîne de connexion. ``UndefinedTable``
porte le nom de la table et le fragment de requête. Un pilote qui échoue à se
connecter met le **mot de passe** dans son message quand la DSN en contient un.
Tout cela partait au client, en 422, c'est-à-dire sous un code qui dit « votre
demande est refusée » — donc lisible par n'importe quel appelant authentifié,
et souvent recopié tel quel dans une interface ou un ticket.

DEUX FAUTES, PAS UNE
---------------------
1. **la fuite** : le message interne traverse la frontière ;
2. **le code** : un défaut de notre côté se présente comme une décision
   d'ingénierie. Un 422 se range dans « l'utilisateur a mal demandé » ; il ne
   déclenche aucune alerte, et le défaut dure.

CE QUE CES CAS N'UTILISENT PAS
-------------------------------
Aucune base, aucune connexion, aucun secret. La DSN et le mot de passe sont des
chaînes fictives, inventées ici, et l'exception est injectée dans le provider —
c'est exactement ce que ferait un pilote en panne.
"""
from __future__ import annotations

import json

import pytest

#: DES CHAÎNES FICTIVES, ET RECONNAISSABLES. Elles n'ouvrent rien, ne
#: correspondent à aucun compte, et n'existent que pour être cherchées dans la
#: réponse. Si l'une d'elles apparaît quelque part, c'est une fuite.
MOT_DE_PASSE_FICTIF = "FICTIF-mdp-ne-doit-jamais-sortir-8f3a"
DSN_FICTIVE = (
    f"postgresql://eurostruct_service:{MOT_DE_PASSE_FICTIF}"
    "@db.interne.invalid:5432/eurostruct_prod"
)
TABLE_INTERNE = "normative_authorisation_grants"


class PanneDePilote(RuntimeError):
    """Ce qu'un pilote PostgreSQL lève réellement quand il ne peut pas ouvrir.

    Le message reproduit la forme de ``psycopg2.OperationalError`` : la
    connexion complète, mot de passe compris.
    """

    def __init__(self) -> None:
        super().__init__(
            f'connection to server failed: FATAL: password authentication '
            f'failed for user "eurostruct_service"\n'
            f'connection string: "{DSN_FICTIVE}"\n'
            f'while executing: select * from {TABLE_INTERNE} where id = $1'
        )


class ProviderQuiTombe:
    """Un provider dont chaque primitive lève la panne de pilote."""

    def proposer_decision(self, *_a, **_k):
        raise PanneDePilote()

    def approuver_decision(self, *_a, **_k):
        raise PanneDePilote()

    def consommer_decision(self, *_a, **_k):
        raise PanneDePilote()


class OuvertQuiTombe:
    """Ce que ``ouvrir_provider`` rend, avec un provider en panne."""

    def __init__(self) -> None:
        self.provider = ProviderQuiTombe()
        self.ferme = 0

    def fermer(self) -> None:
        self.ferme += 1


@pytest.fixture
def application_en_panne():
    """L'application réelle, avec un provider qui tombe. Rien d'autre n'est
    substitué : les routes, les gestionnaires d'erreur et le contrat sont ceux
    de production."""
    from eurostruct_api.app import creer_application
    from eurostruct_api.config import Reglages, ReglagesAuth, ReglagesBase
    from eurostruct_api.dependances import jeton_porteur, ouvrir_provider

    app = creer_application(Reglages(
        auth=ReglagesAuth(jwks_url="", issuer="", audience="",
                          algorithmes=("RS256",)),
        base=ReglagesBase(dsn="")))

    ouvert = OuvertQuiTombe()
    app.dependency_overrides[ouvrir_provider] = lambda: ouvert
    # LE JETON EST REMPLACE PAR UNE CONSTANTE: ce module n'éprouve pas
    # l'authentification — `test_jwt_negatif.py` s'en charge — mais ce que
    # l'API dit APRES l'avoir acceptée.
    app.dependency_overrides[jeton_porteur] = lambda: "jeton-fictif-de-test"
    return app, ouvert


@pytest.fixture
def client(application_en_panne):
    from fastapi.testclient import TestClient

    app, _ = application_en_panne
    return TestClient(app, raise_server_exceptions=False)


PROPOSITION = {
    "subject_kind": "ndp_parameter",
    "subject_id": "EN 1992-1-1:alpha_cc",
    "org_id": None,
    "country_code": "BE",
    "standard_family": "EN 1992",
    "part": "1-1",
    "edition": "2004",
    "permission": "can_validate_normative_reference",
    "reason": "FICTIF",
}

APPELS = [
    ("proposition", "POST", "/v1/authority/decisions", PROPOSITION),
    ("approbation", "POST", "/v1/authority/decisions/d-1/approval", None),
    ("consommation", "POST", "/v1/authority/decisions/d-1/consumption", None),
]


def _appeler(client, methode: str, chemin: str, corps):
    return client.request(methode, chemin,
                          json=corps if corps is not None else None)


@pytest.mark.parametrize("nom,methode,chemin,corps", APPELS)
def test_une_panne_interne_ne_fuit_ni_dsn_ni_mot_de_passe(
        client, nom, methode, chemin, corps):
    """LE CAS CENTRAL. Ni le corps, ni les en-têtes, ni rien.

    On cherche le mot de passe, l'hôte, l'utilisateur, le nom de la base, la
    table et le fragment de requête. Chacun est une chose qu'un appelant n'a
    aucune raison d'apprendre en se voyant refuser une décision.
    """
    reponse = _appeler(client, methode, chemin, corps)

    tout = json.dumps(reponse.json()) + "\n" + json.dumps(dict(reponse.headers))
    for secret in (MOT_DE_PASSE_FICTIF, DSN_FICTIVE, "db.interne.invalid",
                   "eurostruct_service", "eurostruct_prod", TABLE_INTERNE,
                   "password authentication failed"):
        assert secret not in tout, (
            f"« {secret} » traverse la frontiere sur {nom}: "
            "un message interne est recopie dans la reponse")


@pytest.mark.parametrize("nom,methode,chemin,corps", APPELS)
def test_une_panne_interne_est_un_500_et_pas_un_422(
        client, nom, methode, chemin, corps):
    """LE CODE COMPTE AUTANT QUE LE CORPS.

    Un 422 range le défaut dans « l'utilisateur a mal demandé » : il ne
    déclenche aucune alerte, n'apparaît dans aucun tableau de bord d'erreurs, et
    le défaut dure. Une panne de pilote est de **notre** côté, et le code doit
    le dire.
    """
    reponse = _appeler(client, methode, chemin, corps)
    assert reponse.status_code == 500, (
        f"{nom} rend {reponse.status_code}: une panne interne se presente "
        "comme une decision d'ingenierie")
    assert reponse.json()["error"] == "internal_error"


@pytest.mark.parametrize("nom,methode,chemin,corps", APPELS)
def test_la_reponse_porte_un_identifiant_de_correlation(
        client, nom, methode, chemin, corps):
    """SANS SECRET, MAIS PAS SANS PRISE.

    Un 500 générique qui ne dit rien du tout est ininstrumentable : l'appelant
    signale « ça ne marche pas », et personne ne sait de quelle requête il
    parle. Un identifiant de corrélation relie la réponse au journal serveur —
    qui, lui, a le droit de tout savoir. Il ne révèle rien par lui-même.
    """
    reponse = _appeler(client, methode, chemin, corps)
    corps_json = reponse.json()
    correlation = corps_json.get("correlation_id")
    assert correlation, f"{nom}: aucun identifiant de correlation"
    assert len(correlation) >= 8
    assert reponse.headers.get("X-Eurostruct-Correlation-Id") == correlation


@pytest.mark.parametrize("nom,methode,chemin,corps", APPELS)
def test_la_connexion_est_fermee_meme_sur_une_panne(
        application_en_panne, nom, methode, chemin, corps):
    """UNE CONNEXION NON RENDUE EST UNE FUITE QUI TUE LE SERVICE.

    Elle ne se voit pas au premier appel : elle se voit au millième, quand le
    pool est vide et que tout refuse. Le chemin d'exception doit fermer comme
    le chemin nominal.
    """
    from fastapi.testclient import TestClient

    app, ouvert = application_en_panne
    client = TestClient(app, raise_server_exceptions=False)
    _appeler(client, methode, chemin, corps)
    assert ouvert.ferme == 1, (
        f"{nom}: la connexion n'a pas ete fermee sur le chemin d'exception")


def test_un_refus_du_domaine_reste_un_422_avec_son_message(application_en_panne):
    """ET ON NE JETTE PAS LE BÉBÉ AVEC L'EAU DU BAIN.

    ``ConfirmationDomainError`` est un refus **métier** : « vous ne pouvez pas
    approuver votre propre proposition ». Son message est écrit pour être lu,
    il ne contient rien d'interne, et il doit continuer à sortir en 422. Un
    correctif qui masquerait aussi celui-là rendrait le quatre-yeux
    incompréhensible pour l'ingénieur qui le rencontre.
    """
    from fastapi.testclient import TestClient

    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
    from eurostruct_api.dependances import ouvrir_provider

    message = ("le proposant ne peut pas approuver sa propre decision: "
               "deux principals distincts sont exiges.")

    class ProviderQuiRefuse:
        def proposer_decision(self, *_a, **_k):
            raise ConfirmationDomainError(message)

    class Ouvert:
        provider = ProviderQuiRefuse()

        def fermer(self) -> None:
            pass

    app, _ = application_en_panne
    app.dependency_overrides[ouvrir_provider] = lambda: Ouvert()
    reponse = TestClient(app, raise_server_exceptions=False).post(
        "/v1/authority/decisions", json=PROPOSITION)

    assert reponse.status_code == 422, reponse.text
    assert message in json.dumps(reponse.json())


def test_l_authentification_manquante_reste_un_401_avec_l_en_tete(
        application_en_panne):
    """Un 401 sans ``WWW-Authenticate`` ne dit pas au client quoi présenter."""
    from fastapi.testclient import TestClient

    from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
    from eurostruct_api.dependances import ouvrir_provider

    class ProviderSansIdentite:
        def proposer_decision(self, *_a, **_k):
            raise AuthentificationRequise("jeton refuse: signature invalide.")

    class Ouvert:
        provider = ProviderSansIdentite()

        def fermer(self) -> None:
            pass

    app, _ = application_en_panne
    app.dependency_overrides[ouvrir_provider] = lambda: Ouvert()
    reponse = TestClient(app, raise_server_exceptions=False).post(
        "/v1/authority/decisions", json=PROPOSITION)

    assert reponse.status_code == 401, reponse.text
    assert reponse.headers.get("WWW-Authenticate") == "Bearer"


def test_le_journal_serveur_porte_la_correlation_et_pas_le_secret(
        client, caplog):
    """LE JOURNAL A LE DROIT DE SAVOIR, MAIS PAS DE TOUT RECOPIER.

    Il lui faut de quoi retrouver la requête — la corrélation, le type de
    l'exception, la route. Il n'a pas besoin de la chaîne de connexion : un
    journal d'application se recopie dans des tickets, se transmet à des
    prestataires, et survit bien plus longtemps qu'une réponse HTTP.

    ``logger.exception`` écrirait la trace complète, message compris. On
    journalise donc le type et la corrélation, jamais le message brut.
    """
    import logging

    with caplog.at_level(logging.ERROR, logger="eurostruct.api"):
        reponse = client.post("/v1/authority/decisions", json=PROPOSITION)

    correlation = reponse.json()["correlation_id"]
    journal = "\n".join(
        r.getMessage() + (r.exc_text or "") for r in caplog.records)

    assert correlation in journal, (
        "le journal ne porte pas la correlation: la reponse et la trace ne "
        "peuvent pas etre rapprochees")
    assert "PanneDePilote" in journal, (
        "le journal ne nomme pas le type de l'exception")
    assert MOT_DE_PASSE_FICTIF not in journal, (
        "le mot de passe est ecrit dans le journal serveur")
    assert DSN_FICTIVE not in journal, (
        "la chaine de connexion complete est ecrite dans le journal serveur")


# ----------------------------------------------- le tri, a la frontiere du SQL
#
# LES DEUX ARRIVENT SOUS LA MEME FORME. PostgreSQL refuse deliberement (« le
# proposant ne peut pas approuver sa propre decision ») et PostgreSQL tombe en
# panne (« connection to server failed »): dans les deux cas le pilote leve une
# exception, et la couche HTTP ne voit que cela. Le tri se fait a la frontiere
# du SQL, sur le SQLSTATE que le serveur pose lui-meme.
#
# Ces cas n'ouvrent aucune connexion: ils fabriquent l'exception que psycopg2
# leverait, avec son `pgcode` et son `diag`.

class _Diag:
    def __init__(self, message_primary=None, constraint_name=None,
                 message_detail=None):
        self.message_primary = message_primary
        self.constraint_name = constraint_name
        self.message_detail = message_detail


class ErreurPilote(Exception):
    """La forme d'une `psycopg2.Error`: un `pgcode` et un `diag`."""

    def __init__(self, pgcode, *, message="", diag=None):
        super().__init__(message)
        self.pgcode = pgcode
        self.diag = diag or _Diag()


def _traduire(exception):
    """Passe l'exception par le tri et rend ce qui en sort."""
    from eurostruct_engine.ndp.postgres_provider import RefusSqlTraduits

    try:
        with RefusSqlTraduits():
            raise exception
    except Exception as sortie:   # noqa: BLE001 — c'est l'objet du cas
        return sortie


def test_un_raise_exception_de_nos_fonctions_devient_un_refus_metier():
    """P0001: le message vient d'un `raise exception` que NOUS avons ecrit."""
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    message = ("le proposant ne peut pas approuver sa propre decision: deux "
               "principals distincts sont exiges.")
    sortie = _traduire(ErreurPilote(
        "P0001",
        message=f"{message}\nCONTEXT: PL/pgSQL function normative_decision_approve",
        diag=_Diag(message_primary=message)))

    assert isinstance(sortie, ConfirmationDomainError)
    assert str(sortie) == message
    # LE `CONTEXT` NE SORT PAS: il nomme la fonction, donc notre schema.
    assert "PL/pgSQL" not in str(sortie)


def test_une_violation_de_contrainte_ne_nomme_que_la_regle():
    """Classe 23: on rend le nom de la CONTRAINTE, jamais la ligne fautive.

    ``str`` d'une erreur psycopg2 concatene le message et le ``DETAIL``, et le
    ``DETAIL`` d'une violation de contrainte contient **la ligne** — donnees
    comprises. Le recopier exporterait le contenu d'une table a l'appelant.
    """
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    sortie = _traduire(ErreurPilote(
        "23514",
        message=('new row for relation "normative_authority_decisions" '
                 'violates check constraint "decision_two_distinct_principals"\n'
                 'DETAIL:  Failing row contains (2f1c, ndp_parameter, '
                 'EN 1992-1-1:alpha_cc, 22222222-...).'),
        diag=_Diag(constraint_name="decision_two_distinct_principals")))

    assert isinstance(sortie, ConfirmationDomainError)
    texte = str(sortie)
    assert "decision_two_distinct_principals" in texte
    assert "Failing row" not in texte
    assert "normative_authority_decisions" not in texte
    assert "22222222" not in texte


def test_un_refus_de_privilege_ne_decrit_pas_le_schema():
    """42501: le message du serveur nomme l'objet et le role. Pas nous."""
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    sortie = _traduire(ErreurPilote(
        "42501",
        message=('permission denied for table normative_authorisation_grants',
                 ),
        diag=_Diag(message_primary="permission denied for table "
                                   "normative_authorisation_grants")))

    assert isinstance(sortie, ConfirmationDomainError)
    assert "normative_authorisation_grants" not in str(sortie)


def test_une_panne_de_connexion_n_est_PAS_traduite_en_refus():
    """LE CAS QUI COMPTE. Classe 08: la panne remonte telle quelle.

    La traduire en refus metier la ferait ressortir en 422 avec un message —
    et le message d'une `OperationalError` porte la chaine de connexion. Elle
    doit remonter intacte jusqu'au gestionnaire global, qui rend un 500 sans
    rien dans le corps.
    """
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    panne = ErreurPilote(
        "08006", message=f'connection failed: "{DSN_FICTIVE}"')
    sortie = _traduire(panne)
    assert sortie is panne, (
        "une panne de connexion a ete traduite en refus metier: son message, "
        "qui porte la DSN, ressortirait en 422")
    assert not isinstance(sortie, ConfirmationDomainError)


def test_une_table_absente_n_est_PAS_traduite_en_refus():
    """42P01: un defaut de deploiement, pas une decision d'ingenierie."""
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    manquante = ErreurPilote(
        "42P01", message=f'relation "{TABLE_INTERNE}" does not exist')
    assert not isinstance(_traduire(manquante), ConfirmationDomainError)


def test_une_exception_sans_pgcode_n_est_PAS_traduite():
    """Ce qui ne vient pas du serveur n'a pas de SQLSTATE, donc pas de sens."""
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError

    assert not isinstance(_traduire(PanneDePilote()), ConfirmationDomainError)
