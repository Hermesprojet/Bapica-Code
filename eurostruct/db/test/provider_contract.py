#!/usr/bin/env python3
"""EUROSTRUCT — LE CONTRAT DU PostgresConfirmationProvider, SUR UN VRAI POSTGRESQL

    python3 db/test/provider_contract.py <base> <login-service> <mdp> <A> <B> <decision-scope...>

CE QUE CE FICHIER EXISTE POUR ETABLIR
--------------------------------------
Le provider promet une frontiere d'identite. Trois de ses promesses ne se
verifient QUE contre un vrai serveur, parce qu'elles portent sur la semantique
de PostgreSQL et non sur du code Python:

  * `SET LOCAL` meurt avec la transaction — commit, rollback ET exception;
  * une connexion rendue puis reprise ne porte plus l'identite precedente;
  * les primitives derivent l'acteur du contexte, jamais d'un parametre.

LES AUTRES PROMESSES SONT PUREMENT STRUCTURELLES et se verifient sans base:
aucune signature publique ne recoit `actor`, `proposer` ni `approver`; le
contexte n'est pas constructible par l'appelant; un provider sans
authentificateur refuse AVANT d'ouvrir la moindre requete. Elles sont
eprouvees ici aussi, parce qu'un contrat coupe en deux se verifie a moitie.

CE QUI N'EST PAS PROUVE ICI, ET NE PEUT PAS L'ETRE. L'authentificateur employe
est FICTIF. Il etablit le CONTRAT d'integration — le provider refuse sans lui,
pose l'identite qu'il rend, et la retire — mais il ne prouve aucune
authentification reelle. Tant qu'aucun verificateur de jeton concret n'existe
dans ce depot, le sous-systeme reste BLOCKED_BY_REAL_AUTH, et ce fichier ne
pretend pas le contraire.
"""
from __future__ import annotations

import inspect
import os
import sys
import uuid

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "engine", "src"))
# Le repertoire des harnais, pour `canal_lecture` — le protocole du canal
# est defini une seule fois, et les deux bouts s'y referent.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# LE PILOTE MANQUANT NE DOIT PAS TOUT ETEINDRE.
#
# Une premiere version sortait ici en code 4 des l'import manque. Les
# proprietes STRUCTURELLES, celles de la FACTORY et la BARRIERE d'architecture
# n'ont pourtant besoin ni de pilote ni de base: les eteindre avec le reste
# transformait « je ne peux pas mesurer le SQL » en « je ne mesure rien », et
# un pilote absent devenait un laissez-passer pour la couche Python.
#
# Le refus est donc DIFFERE: les proprietes sans base s'executent, puis le
# script rend 4 si le SQL n'a pas pu l'etre. Une surface non executee n'est
# toujours PAS une surface verte.
PILOTE_PRESENT = True
try:
    import psycopg2  # noqa: F401
except ImportError:  # pragma: no cover
    PILOTE_PRESENT = False

import canal_lecture  # noqa: E402
from eurostruct_engine.ndp import postgres_provider as pp  # noqa: E402

ECHECS: list[str] = []
SURS: list[str] = []


#: Points qui ont ROUGI. `conclure()` s'en sert pour savoir s'il doit rendre
#: un SUR pour le point attendu.
POINTS_ROUGES: list[str] = []

# LES POINTS QUE CE HARNAIS SAIT EMETTRE. Le pre-vol s'en sert pour refuser,
# AVANT toute execution, un controle dont le point n'est emis par personne.
# Emettre un point absent d'ici imprime une faute: voir `canal_lecture.emettre`.
canal_lecture.declarer_points(
    "A1", "A2", "A3", "A4", "A5",
    "B1", "B2", "B3", "B4", "B5", "B6", "B6bis", "B7",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11",
    "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10",
)


def verifier(point: str, nom: str, condition: bool, detail: str = "") -> None:
    """Rend un verdict pour un POINT DECLARE.

    LE POINT EST UN ARGUMENT, PAS LE PREMIER JETON DU TEXTE. Il l'etait: le
    traducteur relisait « ROUGE: PR. D5. ... » pour retrouver « D5 ». Le
    harnais connait son point; le lui faire redecouvrir dans sa propre prose
    est le mecanisme meme qu'on supprime.

    La sortie humaine ne change pas — la ligne imprimee est celle d'avant.
    """
    etiquette = f"{point}. {nom}"
    if condition:
        SURS.append(etiquette)
        print(f"      ok: {etiquette}")
    else:
        ECHECS.append(etiquette)
        POINTS_ROUGES.append(point)
        print(f"      ROUGE: PR. {etiquette}")
        if detail:
            print(f"             {detail}")
        canal_lecture.emettre(point, "ROUGE", nature="contrat_du_provider",
                              detail=detail or nom)


def non_parcouru(point: str, nom: str, detail: str) -> None:
    """Un chemin non atteint n'est pas un chemin sain — il n'est pas mesure."""
    etiquette = f"{point}. {nom}"
    ECHECS.append(etiquette)
    POINTS_ROUGES.append(point)
    print(f"      NON PARCOURU: {etiquette}", file=sys.stderr)
    print(f"             {detail}", file=sys.stderr)
    canal_lecture.emettre(point, "NON_PARCOURU",
                          nature="chemin_non_atteint", detail=detail)


# ---------------------------------------------------------------------------
# L'AUTHENTIFICATEUR FICTIF — il porte FICTIF dans son nom, et il le dit
# ---------------------------------------------------------------------------
class AuthentificateurFictif:
    """Rend l'identite qu'on lui a confiee. C'est un decor, pas une preuve."""

    def __init__(self, identite: str) -> None:
        self._identite = identite

    @property
    def identite_de_l_authentificateur(self) -> str:
        return "FICTIF-authentificateur-de-test"

    @property
    def est_fictif(self) -> bool:
        return True

    def authentifier(self, preuve):
        if preuve != "preuve-valide":
            raise pp.AuthentificationRequise(
                "FICTIF: preuve refusee — l'authentificateur ne rend jamais "
                "un contexte par defaut.")
        return pp.creer_contexte(self._identite,
                                 "FICTIF-authentificateur-de-test")


class ConnexionEspionne:
    """Une connexion qui ne se connecte a rien et NOTE ce qu'on lui demande.

    Elle sert a une seule question, qu'une vraie connexion ne peut pas poser:
    un provider sans authentificateur refuse-t-il AVANT d'emettre la moindre
    requete ? Avec une vraie connexion, on ne verrait que le refus.
    """

    def __init__(self) -> None:
        self.requetes: list[str] = []

    def cursor(self):
        conn = self

        class C:
            def execute(self, requete, parametres=None):
                conn.requetes.append(requete)

            def fetchall(self):
                return []

            def fetchone(self):
                return None

            def close(self):
                pass

        return C()

    def commit(self):
        self.requetes.append("COMMIT")

    def rollback(self):
        self.requetes.append("ROLLBACK")


# ---------------------------------------------------------------------------
# D. LA FACTORY DE PRODUCTION — sept refus, une seule issue
# ---------------------------------------------------------------------------
def proprietes_factory() -> None:
    """Eprouve `creer_provider_de_production`, sans pilote ni base.

    AUCUN CONSOMMATEUR PRODUIT N'EXISTE — mesure sur le depot entier. Ces
    proprietes ne prouvent donc pas qu'une route est sure: elles prouvent que
    la SEULE composition offerte est fail-closed, pour que le jour ou une route
    existera, le chemin sur soit deja le seul praticable.
    """
    from eurostruct_engine.ndp.provider_factory import (
        ConfigurationProviderInvalide,
        PiloteIndisponible,
        creer_provider_de_production,
    )
    from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise

    class AuthReel:
        identite_de_l_authentificateur = "FICTIF-mais-declare-reel"
        est_fictif = False
        def authentifier(self, preuve):  # noqa: D102
            raise AssertionError("jamais appele par la factory")

    class AuthFictif(AuthReel):
        est_fictif = True

    class ConnexionMuette:
        def cursor(self): raise AssertionError("jamais appele")
        def commit(self): raise AssertionError("jamais appele")
        def rollback(self): raise AssertionError("jamais appele")

    def attendre(point, nom, exception_attendue, appel):
        try:
            appel()
        except exception_attendue:
            verifier(point, nom, True)
        except Exception as e:  # noqa: BLE001
            verifier(point, nom, False,
                     f"levee inattendue: {type(e).__name__}: {e}")
        else:
            verifier(point, nom, False,
                     "aucun refus: la factory a rendu un provider")

    # D1. AUCUNE FABRIQUE DE CONNEXION -> refus, pas d'ouverture implicite.
    attendre("D1", "sans fabrique de connexion, refus",
             ConfigurationProviderInvalide,
             lambda: creer_provider_de_production(
                 fabrique_de_connexion=None, authentificateur=AuthReel()))

    # D2. AUCUN AUTHENTIFICATEUR -> refus AVANT toute connexion.
    attendre("D2", "sans authentificateur, refus",
             AuthentificationRequise,
             lambda: creer_provider_de_production(
                 fabrique_de_connexion=lambda: ConnexionMuette(),
                 authentificateur=None))

    # D3. AUTHENTIFICATEUR FICTIF -> REFUSE. Le type de l'exception n'est PAS
    #     le critere, et c'est une correction mesuree: la premiere version
    #     exigeait `ConfigurationProviderInvalide`, si bien qu'en retirant la
    #     verification precoce le controle rougissait — non parce que le
    #     fictif passait, mais parce que le CROCHET l'avait refuse avec une
    #     autre exception. Un controle qui rougit quand la garantie tient
    #     encore mesure la forme du refus, pas le refus.
    try:
        creer_provider_de_production(
            fabrique_de_connexion=lambda: ConnexionMuette(),
            authentificateur=AuthFictif())
        verifier("D3", "un authentificateur fictif est refuse", False,
                 "il a ete ACCEPTE: un provider fictif serait utilisable")
    except Exception:
        verifier("D3", "un authentificateur fictif est refuse", True)

    # D4. PILOTE ABSENT -> refus, JAMAIS un repli memoire.
    def fabrique_qui_echoue():
        raise ImportError("no module named 'psycopg2'")
    attendre("D4", "un pilote absent est un refus, pas un repli",
             PiloteIndisponible,
             lambda: creer_provider_de_production(
                 fabrique_de_connexion=fabrique_qui_echoue,
                 authentificateur=AuthReel()))

    # D5. CONNEXION NON CONFORME -> refus.
    attendre("D5", "une connexion non conforme est refusee",
             PiloteIndisponible,
             lambda: creer_provider_de_production(
                 fabrique_de_connexion=lambda: object(),
                 authentificateur=AuthReel()))

    # D6. APPEL POSITIONNEL -> impossible. Inverser connexion et
    #     authentificateur placerait l'authentification du mauvais cote.
    try:
        creer_provider_de_production(ConnexionMuette(), AuthReel())  # type: ignore[misc]
        verifier("D6", "l'appel positionnel est refuse", False, "il a ete accepte")
    except TypeError:
        verifier("D6", "l'appel positionnel est refuse", True)
    except Exception as e:  # noqa: BLE001
        verifier("D6", "l'appel positionnel est refuse", False, f"{type(e).__name__}")

    # D7. LE CHEMIN NOMINAL REND UN PROVIDER, et il a traverse le crochet.
    try:
        p = creer_provider_de_production(
            fabrique_de_connexion=lambda: ConnexionMuette(),
            authentificateur=AuthReel())
        verifier("D7", "le chemin nominal rend un provider non fictif",
                 p.is_fictional is False, f"is_fictional={p.is_fictional}")
    except Exception as e:  # noqa: BLE001
        verifier("D7", "le chemin nominal rend un provider non fictif", False,
                 f"{type(e).__name__}: {e}")


def main() -> int:
    if len(sys.argv) < 8:
        print("usage: provider_contract.py <base> <login> <mdp> <A> <B> "
              "<grant-A> <grant-B>", file=sys.stderr)
        return 2
    base, login, mdp, acteur_a, acteur_b, grant_a, grant_b = sys.argv[1:8]

    print("    6.3c: le contrat du PostgresConfirmationProvider")

    # ----------------------------------------------------------------------
    # A. LES PROPRIETES STRUCTURELLES — aucune base requise
    # ----------------------------------------------------------------------
    # A1. AUCUNE SIGNATURE PUBLIQUE NE RECOIT L'ACTEUR.
    #     C'est la lecon de 6.3c ecrite en assertion: un UUID recu est une
    #     donnee, jamais une preuve d'identite. Le controle porte sur TOUTES
    #     les methodes publiques, pour qu'une methode ajoutee demain soit
    #     couverte sans que personne y pense.
    interdits = {"actor", "actor_id", "proposer", "proposer_id",
                 "approver", "approver_id", "principal", "user_id"}
    fautives = []
    for nom, membre in inspect.getmembers(pp.PostgresConfirmationProvider):
        if nom.startswith("_") or not callable(membre):
            continue
        try:
            params = set(inspect.signature(membre).parameters)
        except (TypeError, ValueError):
            continue
        if params & interdits:
            fautives.append(f"{nom}({', '.join(sorted(params & interdits))})")
    verifier("A1", "aucune methode publique ne recoit l'acteur",
             not fautives, f"fautives: {fautives}")

    # A2. LE CONTEXTE N'EST PAS CONSTRUCTIBLE PAR L'APPELANT.
    try:
        pp.ContexteAuthentifie(actor_id="intrus", emis_par="moi-meme")
        verifier("A2", "le contexte refuse d'etre fabrique par l'appelant",
                 False, "il a ete construit")
    except pp.AuthentificationRequise:
        verifier("A2", "le contexte refuse d'etre fabrique par l'appelant", True)

    # A3. SANS AUTHENTIFICATEUR: REFUS AVANT TOUTE REQUETE.
    espion = ConnexionEspionne()
    try:
        pp.PostgresConfirmationProvider(connexion=espion,
                                        authentificateur=None)
        verifier("A3", "provider sans authentificateur refuse", False,
                 "il a ete construit")
    except pp.AuthentificationRequise:
        verifier("A3", "provider sans authentificateur refuse "
                 "AVANT toute requete", not espion.requetes,
                 f"requetes emises: {espion.requetes}")

    # A4. UNE PREUVE REFUSEE N'OUVRE RIEN.
    espion2 = ConnexionEspionne()
    prov_espion = pp.PostgresConfirmationProvider(
        connexion=espion2, authentificateur=AuthentificateurFictif(acteur_a))
    try:
        prov_espion.approuver_decision("preuve-invalide",
                                       decision_id=str(uuid.uuid4()))
        verifier("A4", "une preuve refusee n'ouvre aucune transaction", False,
                 "l'appel a abouti")
    except pp.AuthentificationRequise:
        verifier("A4", "une preuve refusee n'ouvre aucune transaction",
                 not espion2.requetes,
                 f"requetes emises: {espion2.requetes}")

    # A5. UN PROVIDER BRANCHE SUR UN AUTHENTIFICATEUR FICTIF EST FICTIF.
    from eurostruct_engine.ndp.confirmation import (
        assert_provider_is_usable_in_production,
    )
    try:
        assert_provider_is_usable_in_production(prov_espion)
        verifier("A5", "un provider a authentificateur fictif est refuse "
                 "en production", False, "il a ete accepte")
    except Exception:
        verifier("A5", "un provider a authentificateur fictif est refuse "
                 "en production", True)

    # LA FACTORY, ICI: elle n'a besoin NI de pilote NI de base, et doit donc
    # etre eprouvee avant le bloc SQL — sinon une machine sans psycopg2 la
    # laisserait entierement non exercee.
    proprietes_factory()

    # LA BARRIERE D'ARCHITECTURE, sur l'arbre produit reel.
    import subprocess
    racine_moteur = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "engine", "src", "eurostruct_engine")
    # TOUS LES SOUS-PROCESSUS DE CE HARNAIS SONT DU DECOR. On les exerce pour
    # observer leur code de retour; le verdict est rendu ICI, par `verifier`.
    # Sans `env_decor`, `sans_pilote.py` relance ce fichier meme, qui herite du
    # canal et emet un SECOND verdict terminal. Voir `canal_lecture.env_decor`.
    DECOR = canal_lecture.env_decor()
    bar = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "barriere_provider.py"), racine_moteur],
        capture_output=True, text=True, errors="replace", env=DECOR)
    verifier("D8", "aucun module produit ne contourne la factory",
             bar.returncode == 0,
             (bar.stdout + bar.stderr).strip()[:200])

    # D9 ET D10 NE S'EXECUTENT PAS SOUS EUX-MEMES. `sans_pilote.py` relance ce
    # harnais dans un environnement sans pilote; sans ce garde, D10 le
    # relancerait a son tour, sans fin.
    #
    # LE GARDE NE REND PAS LA MAIN, IL SAUTE DEUX CONTROLES. Une premiere
    # version faisait `return 4 if not PILOTE_PRESENT else 0` ici meme: elle
    # court-circuitait la ligne que la mutation F6 vise, et le temoin devenait
    # aveugle — il rendait 4 par MON garde, jamais par celui qu'on eprouve.
    imbrique = bool(os.environ.get("ESC_SANS_PILOTE_IMBRIQUE"))

    if imbrique:
        pass       # D9 et D10 sautes: on eprouve le RESTE du harnais
    else:
        # D9. LA BARRIERE EST-ELLE MISE EN DIFFICULTE ?
        #
        # `D8` la lance sur l'arbre PRODUIT, qui est conforme: elle n'y rencontre
        # ni alias trompeur ni repertoire vide. La campagne des 103 a laisse
        # survivre F4 et F5 pour cette raison exacte — retirer le suivi des alias
        # ne changeait rien a ce que D8 observait. On lui fabrique donc des arbres
        # REELLEMENT non conformes, un par manquement, plus un conforme qui passe.
        ici = os.path.dirname(os.path.abspath(__file__))
        fix = subprocess.run(
            [sys.executable, os.path.join(ici, "fixtures_barriere.py"),
             os.path.join(ici, "barriere_provider.py")],
            capture_output=True, text=True, errors="replace", env=DECOR)
        verifier("D9", "la barriere juge correctement dix arbres fabriques",
                 fix.returncode == 0,
                 (fix.stdout + fix.stderr).strip()[-220:])

        # D10. L'ABSENCE DE PILOTE EST-ELLE REELLEMENT EPROUVEE ?
        #
        # F6 a survecu parce que le pilote est INSTALLE ici: la mutation y est
        # inerte. On fabrique l'absence dans un sous-processus isole — sans rien
        # desinstaller d'un environnement partage — et on exige un refus nomme.
        sp = subprocess.run(
            [sys.executable, os.path.join(ici, "sans_pilote.py"),
             os.path.join(os.path.dirname(os.path.dirname(ici)), "engine", "src")],
            capture_output=True, text=True, errors="replace", env=DECOR)
        verifier("D10", "sans pilote, la factory refuse (et le refus est nomme)",
                 sp.returncode == 0,
                 (sp.stdout + sp.stderr).strip()[-220:])

    # ----------------------------------------------------------------------
    # B. LES PROPRIETES SQL — un vrai serveur, une vraie transaction
    # ----------------------------------------------------------------------
    if not PILOTE_PRESENT:
        print("NON EXECUTE: aucun pilote PostgreSQL (psycopg2) n'est installe.",
              file=sys.stderr)
        print("       Les proprietes structurelles, la factory et la barriere",
              file=sys.stderr)
        print("       ont ete eprouvees; les proprietes SQL ne l'ont pas ete.",
              file=sys.stderr)
        print("       Une surface non executee n'est PAS verte: code 4.",
              file=sys.stderr)
        return 4
    hote = os.environ.get("PGHOST", "/var/run/postgresql")
    cx = psycopg2.connect(dbname=base, user=login, password=mdp, host=hote)
    cx.autocommit = False

    # UNE SECONDE CONNEXION, EN LECTURE SEULE, ET IL FAUT DIRE POURQUOI.
    #
    # Le login de service n'a AUCUN privilege de table sur
    # `normative_authority_decisions` — c'est deliberé: tout passe par les
    # trois primitives SECURITY DEFINER, et lui donner SELECT rouvrirait le
    # chemin que 0013 ferme. Mesure a l'appui: la premiere version de ce test
    # lisait la table sous le service et recevait « permission denied ».
    #
    # L'OBSERVATEUR NE FAIT QUE LIRE, et jamais sous une identite d'acteur. Il
    # constate ce que les primitives ont ecrit; il n'ecrit rien lui-meme, et
    # aucun controle ne dependrait de lui pour reussir.
    obs = psycopg2.connect(dbname=base, user=os.environ.get("PGUSER", "postgres"),
                           host=hote)
    obs.autocommit = True

    def observer(requete, parametres):
        c = obs.cursor()
        try:
            c.execute(requete, parametres)
            return c.fetchone()
        finally:
            c.close()

    try:
        prov = pp.PostgresConfirmationProvider(
            connexion=cx, authentificateur=AuthentificateurFictif(acteur_a))

        # B1. HORS TRANSACTION, AUCUNE IDENTITE.
        cx.rollback()
        verifier("B1", "avant tout travail, aucune identite en session",
                 prov.acteur_courant() == "",
                 f"vu: {prov.acteur_courant()!r}")

        # B2. DANS L'UNITE, L'IDENTITE EST POSEE — et c'est bien celle que
        #     l'authentificateur a rendue, pas un parametre d'appel.
        vu_dedans = {}
        with prov._unite("preuve-valide") as u:
            u.executer("select current_setting('eurostruct.actor_id', true)")
            vu_dedans["valeur"] = u.curseur.fetchone()[0]
        verifier("B2", "dans l'unite de travail, l'identite authentifiee est posee",
                 vu_dedans.get("valeur") == acteur_a,
                 f"vu: {vu_dedans.get('valeur')!r}, attendu {acteur_a!r}")

        # B3. APRES COMMIT: PLUS RIEN. C'est `SET LOCAL` qui le garantit, et
        #     non un `reset` applicatif — la difference compte le jour ou
        #     quelqu'un remplace set_config(..., true) par (..., false).
        verifier("B3", "apres COMMIT, l'identite a disparu de la session",
                 prov.acteur_courant() == "",
                 f"vu: {prov.acteur_courant()!r}")

        # B4. APRES ROLLBACK: PLUS RIEN NON PLUS.
        try:
            with prov._unite("preuve-valide") as u:
                u.executer("select 1")
                raise RuntimeError("interruption volontaire")
        except RuntimeError:
            pass
        verifier("B4", "apres une EXCEPTION, l'identite a disparu",
                 prov.acteur_courant() == "",
                 f"vu: {prov.acteur_courant()!r}")

        # B5. APRES UNE ERREUR SQL: PLUS RIEN. Le chemin est different — c'est
        #     PostgreSQL qui avorte la transaction, pas Python.
        try:
            with prov._unite("preuve-valide") as u:
                u.executer("select 1 / 0")
        except Exception:
            pass
        cx.rollback()
        verifier("B5", "apres une ERREUR SQL, l'identite a disparu",
                 prov.acteur_courant() == "",
                 f"vu: {prov.acteur_courant()!r}")

        # B6. REPRISE DE CONNEXION: LE LOCATAIRE SUIVANT N'HERITE DE RIEN.
        #     C'est la propriete qui distingue `SET LOCAL` de `SET`, et c'est
        #     celle qui, absente, laisserait un locataire agir sous l'identite
        #     du precedent.
        prov_b = pp.PostgresConfirmationProvider(
            connexion=cx, authentificateur=AuthentificateurFictif(acteur_b))
        vu_b = {}
        with prov_b._unite("preuve-valide") as u:
            u.executer("select current_setting('eurostruct.actor_id', true)")
            vu_b["valeur"] = u.curseur.fetchone()[0]
        verifier("B6", "la connexion reprise porte la NOUVELLE identite, "
                 "et elle seule",
                 vu_b.get("valeur") == acteur_b,
                 f"vu: {vu_b.get('valeur')!r}, attendu {acteur_b!r}")
        verifier("B6", "bis. et rien ne subsiste apres",
                 prov.acteur_courant() == "",
                 f"vu: {prov.acteur_courant()!r}")

        # B7. `SET LOCAL` ET NON `SET`: la preuve directe. On pose l'identite
        #     dans une transaction, on la valide, et on regarde. Un `SET` de
        #     session aurait survecu.
        cur = cx.cursor()
        cur.execute("begin")
        cur.execute("select set_config('eurostruct.actor_id', %s, true)",
                    (acteur_a,))
        cx.commit()
        reste = prov.acteur_courant()
        cur.close()
        verifier("B7", "set_config(..., true) ne survit pas au COMMIT",
                 reste == "", f"vu: {reste!r}")

        # ------------------------------------------------------------------
        # C. LES TROIS PRIMITIVES, SOUS L'IDENTITE AUTHENTIFIEE
        # ------------------------------------------------------------------
        # C'est ici que la frontiere sert a quelque chose. Jusqu'a present on
        # a montre qu'une identite est posee et retiree; reste a montrer que
        # ce sont bien LES PRIMITIVES qui l'utilisent — et qu'aucune d'elles
        # ne l'a recue en parametre.
        prov_a = pp.PostgresConfirmationProvider(
            connexion=cx, authentificateur=AuthentificateurFictif(acteur_a))
        prov_b = pp.PostgresConfirmationProvider(
            connexion=cx, authentificateur=AuthentificateurFictif(acteur_b))

        decision = prov_a.proposer_decision(
            "preuve-valide", subject_kind="regle_normative",
            subject_id="FICTIF-provider-1", org_id=None, country_code="BE",
            standard_family="EN 1992", part="1-1", edition="2004",
            permission="can_validate_normative_reference",
            reason="FICTIF decision par le provider")
        verifier("C1", "A propose sans jamais nommer A",
                 bool(decision), f"decision rendue: {decision!r}")

        ligne = observer(
            "select proposer_id::text, proposal_source_grant_id::text, "
            "state::text, correlation_id::text "
            "from normative_authority_decisions where id = %s", (decision,))
        verifier("C2", "le proposant enregistre est l'identite AUTHENTIFIEE",
                 ligne is not None and ligne[0] == acteur_a,
                 f"vu: {ligne[0] if ligne else None!r}, attendu {acteur_a!r}")
        verifier("C3", "la source d'autorite du proposant est conservee",
                 ligne is not None and ligne[1] == grant_a,
                 f"vu: {ligne[1] if ligne else None!r}, attendu {grant_a!r}")
        correlation = ligne[3] if ligne else None
        verifier("C4", "une correlation est posee des la proposition",
                 bool(correlation), f"vu: {correlation!r}")

        # C5. L'AUTO-APPROBATION EST REFUSEE PAR POSTGRESQL, et non par le
        #     provider. Le provider ne verifie rien: il pose l'identite. La
        #     contrainte de table fait le reste, et elle survit a la
        #     reecriture du code appelant.
        try:
            prov_a.approuver_decision("preuve-valide", decision_id=decision)
            verifier("C5", "le proposant ne peut pas s'approuver lui-meme",
                     False, "l'approbation a abouti")
        except Exception as e:  # noqa: BLE001
            verifier("C5", "le proposant ne peut pas s'approuver lui-meme",
                     "principal" in str(e).lower()
                     or "proposant" in str(e).lower(),
                     f"refus obtenu, mais pour une autre raison: {e}")
        cx.rollback()

        # C6. B APPROUVE. Deux principals distincts, chacun avec sa source.
        prov_b.approuver_decision("preuve-valide", decision_id=decision)
        l2 = observer(
            "select approver_id::text, approval_source_grant_id::text, "
            "state::text, correlation_id::text "
            "from normative_authority_decisions where id = %s", (decision,))
        verifier("C6", "l'approbateur enregistre est la SECONDE identite",
                 l2 is not None and l2[0] == acteur_b and l2[2] == "APPROVED",
                 f"vu: {l2!r}")
        verifier("C7", "la source d'autorite de l'approbateur est conservee",
                 l2 is not None and l2[1] == grant_b,
                 f"vu: {l2[1] if l2 else None!r}, attendu {grant_b!r}")
        verifier("C8", "la correlation n'a pas change entre les deux etapes",
                 l2 is not None and l2[3] == correlation,
                 f"avant {correlation!r}, apres {l2[3] if l2 else None!r}")

        # C9. LA CONSOMMATION, UNE FOIS. La seconde doit etre refusee.
        prov_b.consommer_decision("preuve-valide", decision_id=decision)
        etat = observer("select state::text from normative_authority_decisions "
                        "where id = %s", (decision,))
        verifier("C9", "la decision est CONSUMED", etat and etat[0] == "CONSUMED",
                 f"vu: {etat!r}")
        try:
            prov_b.consommer_decision("preuve-valide", decision_id=decision)
            verifier("C10", "une seconde consommation est refusee", False,
                     "elle a abouti")
        except Exception:  # noqa: BLE001
            verifier("C10", "une seconde consommation est refusee", True)
        cx.rollback()

        # C11. APRES TOUT CELA, LA SESSION NE PORTE PLUS AUCUNE IDENTITE.
        verifier("C11", "apres les trois primitives, la session est vide",
                 prov_a.acteur_courant() == "",
                 f"vu: {prov_a.acteur_courant()!r}")

    finally:
        for connexion in (cx, obs):
            try:
                connexion.rollback()
                connexion.close()
            except Exception:  # noqa: BLE001
                pass

    print()
    print(f"      surs {len(SURS)} / echecs {len(ECHECS)}")
    if ECHECS:
        print(f"      CONTRAT DU PROVIDER: {len(ECHECS)} propriete(s) en echec:")
        for e in ECHECS:
            print(f"        - {e}")
        return 1
    print("      Le contrat du provider tient (authentificateur FICTIF: "
          "BLOCKED_BY_REAL_AUTH).")
    return 0


def _principal() -> int:
    """Enveloppe `main()` et CONCLUT le canal, quoi qu'il arrive.

    Un point qui passe doit produire un SUR. Sans lui, le lanceur lirait
    NOT_RUN — « pas mesure » — la ou il faut lire SURVIVED — « la garantie a
    ete retiree et rien n'a rougi ».
    """
    try:
        return main()
    finally:
        canal_lecture.conclure(POINTS_ROUGES)


if __name__ == "__main__":
    sys.exit(_principal())
