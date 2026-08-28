#!/usr/bin/env python3
"""EUROSTRUCT — MATRICE DE MUTATION DU CONTRAT DE FINALISATION

    python3 db/test/mutation_matrix.py

CE QUE CE FICHIER EXISTE POUR ETABLIR
--------------------------------------
`finalisation_contract.sh` est vert. Un test vert ne prouve rien tant qu'on ne
l'a pas vu rougir: il peut etre vert parce que la garantie tient, ou vert parce
qu'il ne regarde rien. Ce fichier retire les garanties UNE PAR UNE et exige que
le contre-exemple correspondant rougisse.

IL NE TOUCHE PLUS L'ARBRE DE TRAVAIL, ET C'EST LA CORRECTION D'UN DEFAUT REEL.
Il mutait les fichiers du depot puis les restaurait par `git checkout --`. Deux
facons d'y perdre du travail, l'une et l'autre mesurees ou evidentes:

  * une modification creee APRES le demarrage etait ecrasee par la restauration
    — c'est arrive dans cette session, en silence, et le harnais suivant a
    teste le fichier de HEAD en annoncant le contraire;
  * une interruption entre la mutation et la restauration laissait un fichier
    MUTE dans le depot.

La matrice travaille desormais dans un `git worktree` TEMPORAIRE ET DETACHE.
Les mutations, les restaurations et les harnais s'y executent tous. Le depot
principal n'est jamais ecrit. Le nettoyage est porte par un `atexit` et par les
signaux; et si le repertoire temporaire disparait sans lui, il ne reste qu'une
entree de metadonnees que `git worktree prune` retire — aucun fichier suivi
n'est touche.

CE QUI EST JUGE EST CE QUE VOUS AVEZ SOUS LES YEUX. L'espace isole part de HEAD,
puis les fichiers modifies et non suivis du depot y sont RECOPIES. Sans cela la
matrice rendrait un verdict sur HEAD pendant qu'on corrige un fichier — le meme
defaut, deguise en securite. Ce qui a ete recopie est annonce au demarrage.

`db/test/mutation_isolation_selftest.sh` etablit les trois proprietes: une
modification temoin du depot survit, une interruption ne laisse rien de modifie,
et la mutation est bien appliquee dans l'espace isole.

DEUX POINTS SONT COUVERTS PAR DEUX GARANTIES INDEPENDANTES. Pour ceux-la,
retirer UNE SEULE garantie ne doit rien rougir — c'est la redondance voulue — et
retirer LES DEUX doit rougir. Les deux cas sont exerces.

La connexion vient de l'ENVIRONNEMENT, comme pour tous les harnais.
"""
import atexit
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# `.../eurostruct/db/test/mutation_matrix.py` -> `.../eurostruct`: TROIS
# remontees. Deux laissaient RACINE sur `.../db`, ou `git status -- db/...` ne
# designe rien: la garde d'arbre propre passait alors sans rien constater.
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
M = "db/migrations/0010_normative_confirmation.sql"
A13 = "db/migrations/0013_authenticated_actor.sql"
A14 = "db/migrations/0014_four_eyes_decisions.sql"
A11 = "db/migrations/0011_authority_hardening.sql"
A12 = "db/migrations/0012_delegation_lineage.sql"
S = "db/control_plane/0001_normative_seal.sql"
R = "db/test/run.sh"
H = "db/test/authority_closure.sh"
LIB = "db/test/lib_harnais.sh"
A15 = "db/migrations/0015_authority_manifest.sql"
CMD = "tools/deploy_eurostruct.sh"
# LES TROIS CIBLES DE 6.3b6e. Le registre vit dans la premiere migration,
# l'applicateur au-dessus d'elle, et `0002` sert de temoin au controle statique
# de transactionnalite. Les trois sont mutees, donc les trois entrent dans la
# garde d'arbre propre — un fichier mute sans y figurer serait restaure par
# `git checkout --` sans que la garde ait pu prevenir.
INIT = "db/migrations/0001_init.sql"
APP = "db/apply_migration.sh"
RLS = "db/migrations/0002_rls.sql"
SCRATCH = os.environ.get("TMPDIR", "/tmp")


def _git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd or DEPOT,
                          capture_output=True, text=True, errors="replace",
                          check=check)


DEPOT = _git("rev-parse", "--show-toplevel",
             cwd=RACINE).stdout.strip()          # racine du depot git
SOUS = os.path.relpath(RACINE, DEPOT)            # « eurostruct »
ESPACE_DEPOT = None                              # le worktree temporaire
ESPACE = None                                    # ...et son sous-repertoire
ORIGINAUX = {}                                   # texte d'avant mutation


def _ignorer_signaux():
    """Rend TERM, INT et HUP inoffensifs pour la suite de ce processus.

    UN SIGNAL QUI ARRIVE PENDANT UN NETTOYAGE LE COUPE EN DEUX. C'est le meme
    defaut que celui de `harnais_piege_signaux`, chez un autre acteur, et il
    etait MESURE: en signalant la matrice au moment precis ou elle publie son
    resultat et s'apprete a sortir — la fenetre exacte des scenarios L2 et L4 —
    le worktree survivait QUATRE FOIS SUR DIX.

    Le mecanisme: `_sur_signal` restait arme pendant `atexit`, donc le signal y
    relancait `Interruption`, et `nettoyer_espace` s'arretait entre le `git
    worktree remove` et le `rmtree`. `git worktree prune` d'une execution
    ULTERIEURE retirait ensuite l'entree de metadonnees — si bien que
    `git worktree list` redevenait propre et que le REPERTOIRE, lui, restait:
    une copie complete du depot par fuite, invisible a l'inspection habituelle.

    Cela ne cree aucune autorite de delai: SIGKILL n'est ni ignorable ni
    piegeable, et c'est lui qui borne un nettoyage reellement bloque.
    """
    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(s, signal.SIG_IGN)
        except (ValueError, OSError):
            pass


def nettoyer_espace():
    """Retire le worktree. Idempotent, et sans effet sur le depot principal.

    `git worktree remove` ne touche que le repertoire temporaire et l'entree
    de metadonnees qui le decrit. Si le repertoire a deja disparu — machine
    arretee, `/tmp` vide — il ne reste que cette entree, et `prune` la retire.
    Aucun fichier suivi n'est ecrit dans les deux cas.

    LES TROIS OPERATIONS SONT INSECABLES vis-a-vis des signaux: voir
    `_ignorer_signaux`. Sans cela le retrait s'interrompait en son milieu.
    """
    global ESPACE_DEPOT, ESPACE
    if ESPACE_DEPOT is None:
        return
    _ignorer_signaux()
    chemin, ESPACE_DEPOT, ESPACE = ESPACE_DEPOT, None, None
    _pause_sortie()
    _git("worktree", "remove", "--force", chemin, check=False)
    shutil.rmtree(chemin, ignore_errors=True)
    _git("worktree", "prune", check=False)


def _pause_sortie():
    """Crochet de test: une fenetre DETERMINISTE dans le retrait du worktree.

    LA REPETITION N'EST PAS LA PREUVE. Sans ce crochet, le seul moyen de viser
    l'instant ou la matrice retire son worktree serait de la signaler en
    rafale et de compter les fuites — un test qui echoue quatre fois sur dix
    n'etablit rien, et un test qui passe six fois sur dix encore moins.
    Ce crochet ouvre la fenetre et dit QUAND elle est ouverte; le contre-exemple
    y tombe a coup sur.

    Il est INERTE hors auto-test: sans `ESC_MUTATION_PAUSE_SORTIE`, pas une
    instruction ne s'execute. Meme forme que `ESC_MUTATION_PAUSE` et
    `ESC_MUTATION_PAUSE_ENTRE`, qui existent pour la meme raison.

      ESC_MUTATION_PAUSE_SORTIE   duree de la fenetre, en secondes
      ESC_MUTATION_SORTIE_TEMOIN  fichier ecrit A L'ENTREE de la fenetre
    """
    duree = float(os.environ.get("ESC_MUTATION_PAUSE_SORTIE", "0") or 0)
    if duree <= 0:
        return
    temoin = os.environ.get("ESC_MUTATION_SORTIE_TEMOIN")
    if temoin:
        with open(temoin, "w") as f:
            f.write(f"FORMAT=esc-sortie-fenetre/1\nPID={os.getpid()}\n")
    time.sleep(duree)


def _pause_resultat():
    """Crochet de test: la fenetre ENTRE la fin du harnais et la publication.

    Meme forme et meme raison que `_pause_sortie`: cette fenetre-ci est de
    quelques microsecondes, et la viser a l'aveugle reviendrait a compter des
    reussites au lieu d'etablir une propriete.

      ESC_MUTATION_PAUSE_RESULTAT   duree de la fenetre, en secondes
      ESC_MUTATION_RESULTAT_TEMOIN  fichier ecrit A L'ENTREE de la fenetre
    """
    duree = float(os.environ.get("ESC_MUTATION_PAUSE_RESULTAT", "0") or 0)
    if duree <= 0:
        return
    temoin = os.environ.get("ESC_MUTATION_RESULTAT_TEMOIN")
    if temoin:
        with open(temoin, "w") as f:
            f.write(f"FORMAT=esc-resultat-fenetre/1\nPID={os.getpid()}\n")
    time.sleep(duree)


class Interruption(Exception):
    """Un signal est arrive pendant un controle."""

    def __init__(self, numero):
        super().__init__(numero)
        self.numero = numero


ENFANT = None        # le harnais en cours d'execution, s'il y en a un
ACTIF = None         # (nom, fichier) du controle en vol


def _arreter_enfant():
    """Termine LE GROUPE du harnais, et l'attend. Pas seulement son Bash.

    Le harnais tient des connexions, des verrous consultatifs et parfois un
    second cluster. Sortir sans l'attendre le laisse courir sous PID 1, et le
    prochain lancement bute sur les roles qu'il n'a pas eu le temps de rendre.

    LE BASH DIRECT NE SUFFIT PAS. `p.terminate()` ne vise que l'enfant immediat;
    un `psql` en cours, un sous-shell, un second cluster temporaire — tout ce
    que le harnais a engendre — pouvait survivre a la mort de son parent. La
    conclusion « aucun enfant ne survit » etait donc plus large que ce qui
    etait reellement termine.

    `lancer()` demarre desormais le harnais dans SA PROPRE SESSION, ce qui fait
    de son PID son PGID: toute sa descendance herite de ce groupe, et le groupe
    delimite exactement l'arbre a nettoyer. C'est le seul role de
    `start_new_session` ici — delimiter, pas faire survivre.
    """
    global ENFANT
    p, ENFANT = ENFANT, None
    if p is None or p.poll() is not None:
        return
    for signum, patience in ((signal.SIGTERM, 20), (signal.SIGKILL, 10)):
        try:
            os.killpg(p.pid, signum)
        except (ProcessLookupError, PermissionError):
            break
        try:
            p.wait(timeout=patience)
            return
        except subprocess.TimeoutExpired:
            continue
    # Apres un SIGKILL au groupe il ne reste qu'a moissonner: l'attente finale
    # n'est plus bornee parce qu'elle ne peut plus durer.
    if p.poll() is None:
        p.wait()


def _sur_signal(numero, _cadre):
    """CE GESTIONNAIRE NE NETTOIE PLUS. Mesure, pas relecture.

    Il appelait `nettoyer_espace()` en PREMIER, ce qui mettait `ESPACE = None`
    et retirait le worktree — puis levait. La levee declenchait alors le
    `finally: restaurer(fichier)` d'`essayer()`, qui ecrivait dans
    « None/tools/deploy_eurostruct.sh »: FileNotFoundError, traceback, AUCUN
    verdict imprime, et un code de sortie qui n'etait meme plus 143.

    L'ordre correct est celui-ci — le nettoyage vient en DERNIER, une fois la
    mutation restauree et le decompte rendu:

        signal recu -> arret/attente de l'enfant -> restauration de la
        mutation active -> etat interrompu enregistre -> verdict partiel
        imprime -> retrait du worktree -> sortie 143

    LE PREMIER SIGNAL PRIS DESARME LES SUIVANTS. Toute cette sequence est
    longue: un second signal la relancerait depuis le debut ou l'arreterait en
    son milieu, et le verdict partiel — la seule raison d'etre de ce
    gestionnaire — ne serait pas imprime. Le parent garde son escalade en
    SIGKILL, qui ne peut ni etre ignore ni etre piege.
    """
    _ignorer_signaux()
    _arreter_enfant()
    raise Interruption(numero)


def preparer_espace():
    """Cree l'espace isole, et y recopie ce que l'arbre principal a de plus.

    LE POINT DE DEPART EST HEAD, pas l'arbre: un worktree ne peut pas partager
    les modifications non validees. On les RECOPIE donc, sans quoi la matrice
    jugerait HEAD en laissant croire qu'elle juge le fichier ouvert.
    """
    global ESPACE_DEPOT, ESPACE
    ESPACE_DEPOT = tempfile.mkdtemp(prefix="esc-mutations-", dir=SCRATCH)
    # `mkdtemp` a deja cree le repertoire; `worktree add` exige qu'il soit
    # absent ou vide — il l'est.
    _git("worktree", "add", "--detach", "--quiet", ESPACE_DEPOT, "HEAD")
    ESPACE = os.path.join(ESPACE_DEPOT, SOUS)
    atexit.register(nettoyer_espace)
    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, _sur_signal)

    recopies = []
    for ligne in _git("status", "--porcelain", "-z").stdout.split("\0"):
        if len(ligne) < 4:
            continue
        etat, chemin = ligne[:2], ligne[3:]
        # Les renommes portent « ancien -> nouveau »; on ne recopie que la
        # destination, seule presente dans l'arbre.
        if "R" in etat and " -> " in chemin:
            chemin = chemin.split(" -> ")[-1]
        source = os.path.join(DEPOT, chemin)
        cible = os.path.join(ESPACE_DEPOT, chemin)
        if etat == " D" or etat == "D ":
            if os.path.exists(cible):
                os.remove(cible)
                recopies.append(f"supprime {chemin}")
            continue
        if not os.path.isfile(source):
            continue
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        shutil.copy2(source, cible)
        recopies.append(chemin)
    return recopies


class MotifAbsent(Exception):
    """Le texte a muter n'existe plus dans le fichier vise.

    UN CONTROLE PERIME N'EST PAS UNE MUTATION TUEE — et il ne doit pas non
    plus emporter la campagne. `raise SystemExit` arretait tout net: mesure
    faite, la campagne complete s'est arretee au 45e controle sur un motif
    devenu introuvable, et n'a imprime AUCUNE ligne de verdict. Les 44
    controles deja passes n'etaient nulle part comptes, et les 19 suivants
    n'ont jamais ete tentes. Une campagne qui meurt sans decompte est pire
    qu'une campagne rouge: elle ne dit meme pas ce qu'elle a mesure.
    """


def muter(fichier, paires):
    chemin = f"{ESPACE}/{fichier}"
    s = open(chemin).read()
    for vieux, neuf in paires:
        if vieux not in s:
            raise MotifAbsent(f"{fichier}: {vieux.strip()[:70]!r}")
        s = s.replace(vieux, neuf, 1)
    # L'ORIGINAL N'EST ENREGISTRE QU'UNE FOIS LES PAIRES TOUTES TROUVEES: rien
    # n'a ete ecrit si l'une manque, donc rien n'est a restaurer.
    ORIGINAUX[fichier] = open(chemin).read()
    open(chemin, "w").write(s)


def restaurer(fichier):
    """Reecrit le texte d'avant mutation. GIT N'EST PLUS DANS CE CHEMIN.

    `git checkout --` restaurait vers HEAD: dans un espace ou l'on a recopie
    des modifications non validees, il les aurait effacees a la premiere
    mutation. Le texte exact d'avant est plus simple et plus juste.
    """
    texte = ORIGINAUX.pop(fichier, None)
    if texte is not None:
        open(f"{ESPACE}/{fichier}", "w").write(texte)


def lancer(harnais="db/test/finalisation_contract.sh", prefixe="mu"):
    env = dict(os.environ)
    env["TMPDIR"] = SCRATCH
    # LE CONSENTEMENT EST POSE ICI, EXPLICITEMENT. Sans lui les harnais
    # refusent — a juste titre — et la matrice conclurait sur des executions
    # qui n'ont pas eu lieu.
    env["EUROSTRUCT_CLUSTER_JETABLE"] = "oui-cluster-jetable-et-isole"
    # PRISE DE TEST: substitue le harnais. Elle sert au contre-exemple du
    # harnais qui sort IMMEDIATEMENT — precisement le cas ou le temoin retenait
    # les pipes. Inerte quand la variable est absente.
    remplacement = os.environ.get("ESC_MUTATION_HARNAIS_REMPLACE")
    # `Popen` PLUTOT QUE `run`, POUR QUE LE GESTIONNAIRE DE SIGNAL PUISSE
    # ATTEINDRE L'ENFANT. `subprocess.run` ne publie sa poignee nulle part: a
    # l'arrivee d'un signal, le harnais restait injoignable et ne pouvait etre
    # ni termine ni attendu.
    global ENFANT
    # `start_new_session=True` NE SERT PAS A LE FAIRE SURVIVRE — c'est l'inverse.
    # Il donne au harnais un groupe de processus a lui, dont son PID est le
    # meneur: toute sa descendance en herite, et `_arreter_enfant()` peut alors
    # viser LE GROUPE plutot que le seul Bash. Sans cela il n'existe aucune
    # facon sure de nommer « tout ce que ce harnais a engendre ».
    # PRISE DE TEST: UN DESCENDANT DELIBERE DANS LE GROUPE DU HARNAIS.
    #
    # Prouver que « toute la descendance est terminee » demande un descendant
    # dont on soit SUR qu'il vit au moment du signal. S'en remettre a ceux que
    # le harnais engendre de lui-meme ne marche que par accident: mesure,
    # `harnais_verrou_prendre()` ouvre un `coproc psql` de longue duree en
    # execution AUTONOME, mais retourne sans coproc quand le marqueur de
    # reentrance est present — c'est-a-dire sous `db/test/run.sh`. Le test
    # trouvait donc un descendant durable seul, et aucun imbrique: vert d'un
    # cote, rouge de l'autre, sans que la propriete ait change.
    #
    # LE TEMOIN N'HERITE PLUS DES PIPES, ET LE WRAPPER POSSEDE LES DEUX
    # PROCESSUS. Le modele precedent — temoin en arriere-plan, puis `exec` du
    # harnais — donnait au `sleep` les deux pipes de `Popen`. Reproduit hors
    # harnais, sans base, avec un harnais qui sort immediatement:
    #
    #   marqueur          : 5991 READY
    #   enfants directs   : AUCUN
    #   arbre du groupe   : 5991  PPID 1  PGID 5990  S  sleep 300
    #   temoin fd/1       : pipe:[2921774]
    #   temoin fd/2       : pipe:[2921775]
    #   communicate()     : BLOQUE (irait a 300 s)
    #
    # Des que le harnais finissait AVANT le signal, `communicate()` n'atteignait
    # jamais EOF: la matrice restait vivante SANS ENFANT DIRECT, et l'attente
    # « le harnais lance par la matrice » — un `pgrep -P` — expirait apres ses
    # 300 secondes exactes. C'est le surcout de ~5 min de l'etape 8 en CI, et un
    # defaut LATENT PARTOUT: en local le signal arrivait toujours a temps, le
    # groupe partait, le temoin mourait. Une course gagnee n'est pas une
    # garantie.
    #
    # Le wrapper ne fait plus `exec`: il reste MENEUR DU GROUPE, lance le temoin
    # sur /dev/null, lance le harnais comme enfant, publie ATOMIQUEMENT les
    # trois PID, attend le harnais, moissonne le temoin, et rend le code du
    # harnais. Meme mesure apres correction: marqueur « 5997 5999 5998 READY »,
    # groupe vide, fd du temoin absents, `communicate()` rendu en 0,9 s avec le
    # code 7 du harnais.
    argv = ["bash", remplacement or harnais, prefixe]
    temoin = os.environ.get("ESC_MUTATION_TEMOIN")
    barriere = None
    if temoin:
        env["ESC_TEMOIN"] = temoin
        # MARQUEUR VERSIONNE, ET LE PRODUCTEUR VERIFIE AVANT DE DIRE READY.
        # Deduire « PGID == PID du wrapper » de `start_new_session=True` n'est
        # pas une preuve: le wrapper OBSERVE son PGID et celui de ses deux
        # enfants, constate qu'ils vivent et ne sont pas zombies, que les trois
        # PID sont distincts, et que le temoin ne tient AUCUN pipe. Sans quoi
        # il publie FAILED — jamais READY par defaut.
        enveloppe = (
            'set -u\n'
            'umask 077\n'
            # LE REPERTOIRE PEUT ETRE FOURNI PAR LA MATRICE, ET C'EST CE QUI
            # PERMET DE LE RENDRE APRES UN SIGKILL. Le wrapper le retire en
            # sortant — mais un wrapper tue ne retire rien, et ses deux FIFO
            # restaient dans `TMPDIR` sans que personne ne puisse les nommer.
            # Le proprietaire du nettoyage doit etre un processus qui SURVIT a
            # celui qu'on tue. Le repli sur `mktemp -d` garde le wrapper
            # autonome: extrait seul par l'auto-test de protocole, il continue
            # de fonctionner, et son repertoire subsistant y est CLASSE.
            'BARRIERE="${ESC_BARRIERE:-$(mktemp -d)}"; chmod 0700 "$BARRIERE"\n'
            'mkfifo -m 0600 "$BARRIERE/harnais.fifo" "$BARRIERE/temoin.fifo"\n'
            'exec {FD_H}<>"$BARRIERE/harnais.fifo" '
            '{FD_T}<>"$BARRIERE/temoin.fifo"\n'
            'ETAT_HARNAIS="$BARRIERE/harnais.etat"\n'
            '( exec {FD_L}<"$BARRIERE/temoin.fifo"; read -r -u "$FD_L" ) '
            '{FD_H}>&- {FD_T}>&- >/dev/null 2>&1 </dev/null &\n'
            'TEMOIN=$!\n'
            'ESC_HARNAIS_PORTE="$BARRIERE/harnais.fifo" '
            'ESC_HARNAIS_ETAT="$ETAT_HARNAIS" '
            'ESC_HARNAIS_JETON="${ESC_MUTATION_JETON:-}" '
            'ESC_HARNAIS_SCENARIO="${ESC_SCENARIO:-}" '
            '"$@" {FD_H}>&- {FD_T}>&- &\n'
            'HARNAIS=$!\n'
            'PGID="$(ps -o pgid= -p $$ 2>/dev/null | tr -d \' \')"\n'
            'ETAT=READY\n'
            'GATE=ABSENT\n'
            # UNE SEULE AUTORITE DE DELAI, ET CE N'EST PAS LE WRAPPER. Il
            # attend des EVENEMENTS — la preuve de blocage, ou la mort du
            # harnais — et rien d'autre. Le parent possede le delai
            # d'obtention de READY; `_arreter_enfant()` possede l'escalade et
            # SIGKILL. Un compteur autonome ici aurait ete une SECONDE
            # horloge: regle a 30 s il concluait ABSENT sur un harnais
            # parfaitement vivant, et le porter a 600 s n'aurait fait que
            # rendre l'ordonnancement probable au lieu de le contraindre.
            'while :; do\n'
            '  [[ -s "$ETAT_HARNAIS" ]] && { GATE=PRESENT; break; }\n'
            '  kill -0 "$HARNAIS" 2>/dev/null '
            '|| { GATE=HARNAIS_TERMINE_AVANT_BLOCKED; break; }\n'
            '  sleep 0.05\n'
            'done\n'
            '[[ "$GATE" == PRESENT ]] || ETAT=FAILED\n'
            'GH=""; GP=""; GT=""; GS=""\n'
            'if [[ "$GATE" == PRESENT ]]; then\n'
            '  GH="$(sed -n \'s/^PID=//p\' "$ETAT_HARNAIS")"\n'
            '  GP="$(sed -n \'s/^PGID=//p\' "$ETAT_HARNAIS")"\n'
            '  GT="$(sed -n \'s/^TOKEN=//p\' "$ETAT_HARNAIS")"\n'
            '  GS="$(sed -n \'s/^STATE=//p\' "$ETAT_HARNAIS")"\n'
            '  [[ "$GH" == "$HARNAIS" && "$GP" == "$PGID" '
            '     && "$GT" == "${ESC_MUTATION_JETON:-}" && "$GS" == GATE_ARMED ]] '
            '     || ETAT=FAILED\n'
            'fi\n'
            'PGH="$(ps -o pgid= -p "$HARNAIS" 2>/dev/null | tr -d \' \')"\n'
            'PGT="$(ps -o pgid= -p "$TEMOIN" 2>/dev/null | tr -d \' \')"\n'
            'STH="$(ps -o stat= -p "$HARNAIS" 2>/dev/null | tr -d \' \')"\n'
            'STT="$(ps -o stat= -p "$TEMOIN" 2>/dev/null | tr -d \' \')"\n'
            '[[ "$$" != "$HARNAIS" && "$HARNAIS" != "$TEMOIN" '
            '&& "$$" != "$TEMOIN" ]] || ETAT=FAILED\n'
            '[[ -n "$PGID" && "$PGH" == "$PGID" && "$PGT" == "$PGID" ]] || ETAT=FAILED\n'
            '[[ -n "$STH" && "$STH" != Z* && -n "$STT" && "$STT" != Z* ]] || ETAT=FAILED\n'
            'for FD in 1 2; do\n'
            '  case "$(readlink /proc/$TEMOIN/fd/$FD 2>/dev/null)" in\n'
            '    pipe:*) ETAT=FAILED ;;\n'
            '  esac\n'
            'done\n'
            'PGT="$(ps -o pgid= -p "$TEMOIN" 2>/dev/null | tr -d \' \')"\n'
            '{ echo "FORMAT=esc-mutation-marker/2"\n'
            '  echo "SCENARIO=${ESC_SCENARIO:-}"\n'
            '  echo "TOKEN=${ESC_MUTATION_JETON:-}"\n'
            '  echo "STATE=$ETAT"\n'
            '  echo "WRAPPER_PID=$$"\n'
            '  echo "WRAPPER_PGID=$PGID"\n'
            '  echo "HARNESS_PID=$HARNAIS"\n'
            '  echo "HARNESS_PGID=$GP"\n'
            '  echo "WITNESS_PID=$TEMOIN"\n'
            '  echo "WITNESS_PGID=$PGT"\n'
            '  echo "PGID=$PGID"\n'
            '  echo "HARNESS_GATE_STATE=$GS"\n'
            '  echo "GATE=$GATE"\n'
            '} >"$ESC_TEMOIN.tmp"\n'
            # LE REFUS EST DIT, PAS SEULEMENT ENREGISTRE. `.doublon` etablit la
            # violation pour qui va le lire; il ne l'apprend a personne. Un
            # parent qui attend le marqueur ne voyait, lui, que du silence —
            # jusqu'a son propre delai. Mesure: un canal deja occupe (`mktemp`
            # CREE le fichier) faisait echouer la publication a la premiere
            # seconde et rendait « delai depasse » 300 s plus tard, c'est-a-dire
            # le seul message qui ne designe pas la cause. Le wrapper ecrit donc
            # aussi sur son erreur standard, que la matrice capture et rapporte.
            'ln "$ESC_TEMOIN.tmp" "$ESC_TEMOIN" 2>/dev/null '
            '|| { echo "DOUBLON_READY" >>"$ESC_TEMOIN.doublon"\n'
            '     echo "ESC-WRAPPER: publication du marqueur REFUSEE:'
            ' « $ESC_TEMOIN » existe deja." >&2\n'
            '     echo "ESC-WRAPPER: un canal doit etre un nom LIBRE"'
            ' >&2; }\n'
            'rm -f "$ESC_TEMOIN.tmp"\n'
            # LE WRAPPER RELAIE LE SIGNAL ET ATTEND LE HARNAIS. Sans cela il
            # mourait le premier — bash termine par defaut sur SIGTERM — et
            # `p.wait()`, qui attend le WRAPPER depuis qu'il ne fait plus
            # `exec`, rendait la main pendant que le harnais executait encore
            # ses trappes de nettoyage. Mesure, une fois le `set -m` global
            # retire de l'auto-test:
            #     ECHEC: le Bash du harnais (1486) survit
            #     ECHEC: le groupe 1484 contient encore des processus vivants
            # Le harnais a des trappes qui prennent du temps; il faut les lui
            # laisser, puis constater sa mort.
            # MARQUEUR CAUSAL EXCLUSIF. `mkdir` echoue si la cible existe:
            # c'est l'operation atomique qui rend une SECONDE emission
            # detectable. Un `mv -f` l'aurait ecrasee en silence, et
            # « une seule entree logique dans le nettoyage » aurait ete une
            # affirmation invérifiable.
            'marq() {\n'
            '  [[ -n "${ESC_MARQUEURS:-}" ]] || return 0\n'
            '  mkdir "$ESC_MARQUEURS/$1" 2>/dev/null || {\n'
            '    echo "DOUBLON=$1" >>"$ESC_MARQUEURS/.erreurs"; return 9; }\n'
            '  { echo "EVENT=$1"; echo "PID=$$"; echo "PGID=$PGID"\n'
            '    echo "SCENARIO=${ESC_SCENARIO:-?}"; } >"$ESC_MARQUEURS/$1/.m"\n'
            '  mv -f "$ESC_MARQUEURS/$1/.m" "$ESC_MARQUEURS/$1/meta"\n'
            '}\n'
            'journal() { [[ -n "${ESC_JOURNAL:-}" ]] && echo "$1" >>"$ESC_JOURNAL"; :; }\n'
            # LE PREMIER RETOUR DE `wait` N'EST PAS LA FIN DU HARNAIS. Bash rend
            # la main a `wait` des qu'une trap s'execute, l'enfant toujours
            # vivant. Le prendre pour une terminaison faisait moissonner et
            # sortir pendant que le harnais nettoyait encore. On REATTEND donc
            # tant que le PID reste un enfant non moissonne — critere qui ne
            # repose pas sur `kill -0` seul: une fois `wait` revenu avec le
            # VRAI code, l'enfant est moissonne et le PID n'existe plus.
            'attendre_harnais() {\n'
            '  local rc n=0\n'
            '  while :; do\n'
            '    wait "$HARNAIS"; rc=$?; n=$((n + 1))\n'
            '    if ! kill -0 "$HARNAIS" 2>/dev/null; then\n'
            '      journal "WAIT_$n=final:$rc"; CODE=$rc; return 0\n'
            '    fi\n'
            '    journal "WAIT_$n=interrompu:$rc (enfant non moissonne)"\n'
            '  done\n'
            '}\n'
            'moissonner_temoin() {\n'
            '  kill "$TEMOIN" 2>/dev/null; wait "$TEMOIN" 2>/dev/null\n'
            '  marq WRAPPER_REAPED_WITNESS\n'
            '}\n'
            # PRIORITE DES CODES, ECRITE ICI ET VERIFIEE PAR LE TEST.
            #   pas de signal                  -> code exact du harnais
            #   signal + nettoyage reussi      -> 128 + signal
            #   signal + echec de nettoyage    -> LE CODE DU HARNAIS (ex. 9)
            # Le code du harnais reste l'autorite des qu'il exprime un echec:
            # « le wrapper sort en 128+signal » masquait un nettoyage rate.
            'sortie_wrapper() {\n'
            '  marq WRAPPER_EXITING\n'
            '  if [[ -n "${SIGNAL_RECU:-}" ]]; then\n'
            '    if (( CODE == 0 || CODE == 128 + SIGNAL_RECU )); then\n'
            '      exit $((128 + SIGNAL_RECU))\n'
            '    fi\n'
            '    exit "$CODE"\n'
            '  fi\n'
            '  exit "$CODE"\n'
            '}\n'
            # LA TRAP EST DESARMEE AVANT LE RELAIS: un second signal ne doit pas
            # relancer un nettoyage concurrent. Le relais est donc au plus une
            # fois, que le signal ait vise le groupe entier ou le seul wrapper.
            # LA TRAP EST MINIMALE, ET C'EST CE QUI REND LE CHEMIN DETERMINISTE.
            # Elle desarme sa reentrance, memorise le signal, relaie UNE FOIS
            # au harnais, et RETOURNE. Elle n'attend pas, ne moissonne pas, ne
            # sort pas.
            #
            # La version precedente faisait tout le travail dans la trap et
            # sortait: le `wait` exterieur n'etait jamais repris, donc jamais
            # observe comme interrompu. `WAITS=WAIT_1=final:0` — la reattente
            # existait sans qu'aucun chemin ne la traverse, et la mutation
            # « premier wait pris pour la fin » n'aurait rien eu a rougir.
            #
            # En rendant la main, la trap laisse `attendre_harnais()` — SEUL
            # proprietaire du `wait` et de la moisson — constater son propre
            # `wait` interrompu, boucler, puis obtenir le vrai code.
            'relayer() {\n'
            '  trap - TERM INT\n'
            '  SIGNAL_RECU="$2"\n'
            '  kill -"$1" "$HARNAIS" 2>/dev/null\n'
            '}\n'
            'trap \'relayer TERM 15\' TERM\n'
            'trap \'relayer INT 2\' INT\n'
            # L'ATTENTE EST ANNONCEE. Sans ce marqueur, le test qui vise le
            # wrapper seul court apres une fenetre: signaler avant que le
            # `wait` soit arme ne produirait aucun retour interrompu, et le
            # chemin ne serait pas exerce.
            'marq WRAPPER_WAITING\n'
            'attendre_harnais\n'
            'if [[ -z "${SIGNAL_RECU:-}" && "$ETAT" == READY ]]; then\n'
            '  { echo "FORMAT=esc-mutation-terminal/1"\n'
            '    echo "SCENARIO=${ESC_SCENARIO:-}"\n'
            '    echo "TOKEN=${ESC_MUTATION_JETON:-}"\n'
            '    echo "STATE=FAILED_AFTER_READY"\n'
            '    echo "HARNESS_PID=$HARNAIS"\n'
            '    echo "HARNESS_RC=$CODE"\n'
            '  } >"$ESC_TEMOIN.terminal.tmp"\n'
            '  ln "$ESC_TEMOIN.terminal.tmp" "$ESC_TEMOIN.terminal" 2>/dev/null || :\n'
            '  rm -f "$ESC_TEMOIN.terminal.tmp"\n'
            'fi\n'
            'marq WRAPPER_REAPED_HARNESS\n'
            'moissonner_temoin\n'
            'exec {FD_H}>&- {FD_T}>&- 2>/dev/null || :\n'
            'rm -rf "$BARRIERE"\n'
            'sortie_wrapper\n'
        )
        argv = ["bash", "-c", enveloppe, "bash", *argv]
        # LA MATRICE POSSEDE LE REPERTOIRE DE BARRIERE, PAS LE WRAPPER. Elle
        # survit a l'escalade qui tue le wrapper, donc elle seule peut rendre
        # les FIFO dans tous les cas. Voir le commentaire dans l'enveloppe.
        barriere = tempfile.mkdtemp(prefix="esc-barriere-", dir=SCRATCH)
        env["ESC_BARRIERE"] = barriere
    # `errors="replace"` N'EST PAS DE LA COMPLAISANCE. Mesure du 28/08: un
    # harnais avait emis un octet UTF-8 orphelin — `cut -c` travaille en octets
    # sous `LC_CTYPE=POSIX` et avait coupe un tiret cadratin en deux — et
    # `communicate()` levait `UnicodeDecodeError`. La campagne mourait sans
    # rendre le moindre verdict: quatre-vingt-dix garanties perdues sur un
    # octet d'affichage. Le harnais a ete corrige a la source; ce filet est la
    # pour que la MESURE ne depende jamais de la propriete typographique de ce
    # qu'elle observe.
    p = subprocess.Popen(argv, cwd=ESPACE, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, errors="replace", start_new_session=True)
    ENFANT = p
    try:
        sortie, erreur = p.communicate()
    finally:
        ENFANT = None
        # CANAL DE RESULTAT TEST-ONLY. Le code du WRAPPER n'etait observable
        # nulle part: `essayer()` le consomme, et la matrice sort ensuite avec
        # SON propre code. Un test qui lisait `wait <matrice>` mesurait donc
        # 143 la ou le wrapper avait rendu 9 — il ne pouvait ni confirmer ni
        # infirmer la priorite des codes.
        #
        # Publie ICI, dans le `finally`: apres le vrai `p.wait()` de
        # `communicate()`, avant toute interpretation, et meme si le wrapper
        # rend un code non nul ou si une branche d'erreur survient.
        # LA SEQUENCE TERMINALE EST INSECABLE, ET LES SIGNAUX SONT BLOQUES —
        # PAS IGNORES. Un TERM recu entre la fin du harnais et le `os.link`
        # declenchait `_sur_signal`, donc `Interruption`, et le canal n'etait
        # JAMAIS ecrit: le code du wrapper — seul endroit ou il soit observable
        # — disparaissait, alors que la matrice imprimait par ailleurs un
        # verdict partiel parfaitement lisible. Mesure, fenetre ouverte par
        # `ESC_MUTATION_PAUSE_RESULTAT`: « RESULTAT PERDU », code matrice 143.
        #
        # LE MASQUE EST POSE EN TETE DU `finally`, pas juste avant l'ecriture.
        # Un masque pose plus bas laisse decouverte toute la portion qui le
        # precede — mesure: avec le crochet AVANT le masque, le resultat etait
        # perdu exactement comme sans masque. Ce qu'il faut rendre insecable,
        # c'est la sequence terminale entiere.
        #
        # `pthread_sigmask` BLOQUE, il n'ignore pas: le signal reste EN ATTENTE
        # et est delivre des le masque leve. L'interruption a donc bien lieu,
        # juste apres l'ecriture — aucune autorite de delai n'est gagnee ni
        # perdue, et la matrice reste tuable a tout instant par SIGKILL.
        # `SIG_IGN` aurait ete FAUX ici: le masque est pose au milieu d'une
        # campagne, et ignorer aurait rendu la matrice sourde pour tous les
        # controles suivants — le signal serait publie ET perdu.
        _sig = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
        try:
            _masque = signal.pthread_sigmask(signal.SIG_BLOCK, _sig)
        except (AttributeError, OSError):
            _masque = None
        try:
            _pause_resultat()
            _canal = os.environ.get("ESC_MUTATION_RESULTAT")
            if _canal:
                _j = os.environ.get("ESC_JOURNAL", "")
                _waits = ""
                if _j and os.path.exists(_j):
                    with open(_j) as _f:
                        _waits = ";".join(x.strip() for x in _f if x.strip())
                _tmp = _canal + ".tmp"
                with open(_tmp, "w") as _f:
                    _f.write(f"FORMAT=esc-wrapper-result/1\n"
                             f"SCENARIO={os.environ.get('ESC_SCENARIO', '?')}\n"
                             f"WRAPPER_PID={p.pid}\n"
                             f"WRAPPER_PGID={p.pid}\n"
                             f"WRAPPER_RC={p.returncode}\n"
                             f"TOKEN={os.environ.get('ESC_MUTATION_JETON', '')}\n"
                             f"WAITS={_waits}\n")
                # `os.link` echoue si la cible existe: la publication est
                # EXCLUSIVE, donc un second resultat est une erreur observable
                # et non un ecrasement silencieux.
                try:
                    os.link(_tmp, _canal)
                except FileExistsError:
                    with open(_canal + ".doublon", "a") as _f:
                        _f.write(f"DOUBLON rc={p.returncode}\n")
                finally:
                    os.unlink(_tmp)
            # LES FIFO SONT RENDUES ICI, ET C'EST LE SEUL ENDROIT OU CE SOIT
            # POSSIBLE DANS TOUS LES CAS. Le wrapper les retire quand il sort
            # normalement; quand l'escalade le tue par SIGKILL, il ne retire
            # rien. La matrice, elle, survit a cette escalade — c'est elle qui
            # la conduit.
            if barriere:
                shutil.rmtree(barriere, ignore_errors=True)
        finally:
            if _masque is not None:
                signal.pthread_sigmask(signal.SIG_SETMASK, _masque)
    return p.returncode, sortie + erreur


# ==========================================================================
# LES SEPT STATUTS TERMINAUX — un controle en rend EXACTEMENT un
# ==========================================================================
# La comptabilite precedente melangeait des choses de natures differentes sous
# « non execute »: une cible perimee, un harnais qui refuse de demarrer et un
# controle jamais atteint y tombaient ensemble. Or ces trois-la ne demandent
# pas le meme travail, et les confondre a deja laisse une campagne se declarer
# terminee alors qu'une garantie n'etait plus verifiee du tout.
#
#   KILLED_RUNTIME            la mutation a ete INSTALLEE, le chemin aval a ete
#                             parcouru, et le contre-exemple permanent a rougi.
#   KILLED_INSTALL_ASSERTION  la mutation n'a jamais pu etre installee: une
#                             postcondition de migration l'a refusee EN LA
#                             NOMMANT, et la transaction a ete annulee. C'est
#                             une mise a mort, et la plus precoce possible.
#   REDUNDANT_PROVEN          retirer UNE couche ne rougit pas — c'est voulu —
#                             ET un controle combine prouve que retirer TOUTES
#                             les couches rougit. Sans ce second controle, la
#                             « redondance » ne serait qu'un trou nomme.
#   SURVIVED                  la mutation a ete installee, le chemin parcouru,
#                             et RIEN n'a rougi. Le controle ne porte rien.
#   STALE                     la cible n'existe plus, ou existe en plusieurs
#                             exemplaires. On ne sait RIEN de la garantie.
#   INFRA_FAILURE             le harnais n'a pas tourne pour une raison
#                             etrangere au scenario.
#   NOT_RUN                   le controle n'a pas ete tente.
#
# UNE ERREUR ETRANGERE AU SCENARIO N'EST JAMAIS UNE MISE A MORT. C'est la
# raison d'etre de la separation entre INFRA_FAILURE et les deux KILLED_*.
KILLED_RUNTIME = "KILLED_RUNTIME"
KILLED_INSTALL_ASSERTION = "KILLED_INSTALL_ASSERTION"
REDUNDANT_PROVEN = "REDUNDANT_PROVEN"
SURVIVED = "SURVIVED"
STALE = "STALE"
INFRA_FAILURE = "INFRA_FAILURE"
NOT_RUN = "NOT_RUN"

TERMINAUX = (KILLED_RUNTIME, KILLED_INSTALL_ASSERTION, REDUNDANT_PROVEN,
             SURVIVED, STALE, INFRA_FAILURE, NOT_RUN)


def _cibles(fichier, paires):
    """Rend la liste [(fichier, paires), ...] d'un controle.

    Un controle mutait UN fichier. `B=` doit en muter DEUX: la propriete des
    tables vit dans 0010, et la postcondition qui refuse d'installer cette
    mutation vit dans 0013. Prouver que la defense d'EXECUTION existe exige de
    retirer les deux — sinon on ne mesure que la defense d'INSTALLATION, qui
    masque l'autre.

    Forme courte conservee: `fichier` est une chaine et `paires` la liste.
    Forme longue: `fichier` est une liste de couples `(fichier, paires)`, et
    `paires` vaut None.
    """
    if isinstance(fichier, str):
        return [(fichier, paires)]
    return list(fichier)


def _code(nom):
    """Le code court d'un controle: le premier mot de son nom (« C' », « T4' »)."""
    return nom.split()[0]


# LES MUTATIONS INTERCEPTEES A L'INSTALLATION, et le diagnostic EXACT attendu.
#
# Une mutation peut etre si profonde qu'une postcondition de migration la
# refuse avant que le moindre harnais tourne. C'est le resultat le PLUS FORT
# possible — rien ne s'installe —, et l'ancienne matrice n'avait pas de mot
# pour le dire: elle le comptait « creux », c'est-a-dire l'inverse de la
# verite. On exige donc le diagnostic NOMME, pas un echec quelconque.
INSTALL_ASSERTION = {
    "B": "PRECONDITION 0013: la table normative_authorisation_grants "
         "appartient a",
    # L'ASSERTION AGREGEE, AJOUTEE AU LOT PRECEDENT, INTERCEPTE DESORMAIS
    # DEUX MUTATIONS QUI ATTEIGNAIENT AUPARAVANT LA COUCHE D'EXECUTION.
    #
    # Elles ont ete comptees SURVIVED dans la campagne de `85e3aea`, et le
    # moteur avait raison de refuser de les dire tuees: rien ne lui disait
    # qu'un refus a l'installation valait mise a mort. Le diagnostic exact a
    # ete reproduit dans deux worktrees jetables, avec la preuve d'atomicite
    # (zero ligne de registre, aucune table posee).
    "B'": "AUTHORITY_COMPOSITION_FORCE_RLS_MISSING",
    "B=": "AUTHORITY_COMPOSITION_TABLE_OWNER_MISMATCH",
    # L'ENDOSSEMENT DU DONNEUR, ENFIN FALSIFIABLE. Il avait SURVECU deux
    # fois — mute dans 0012 puis dans 0011 — parce que `0011` revoquait
    # CREATE sans jamais verifier que la revocation avait pris: le seul
    # controle capable de le voir arrivait deux migrations plus tard, quand
    # une autre revocation, elle intacte, avait deja nettoye.
    "GR1": "AUTHORITY_0011_SCHEMA_CREATE_RETAINED",
}

# LES REDONDANCES VOULUES ET LEUR PREUVE COMBINEE.
#
# « retirer une couche ne rougit pas » n'est acceptable que si l'on montre par
# ailleurs que retirer TOUTES les couches rougit. Sans cela, « redondance
# voulue » est un nom poli pour « aucune des deux ne porte ». Le pre-vol exige
# que le controle combine soit DECLARE et RETENU dans la meme campagne.
COMBINEE = {
    "2":   "2b",
    "3":   "3b",
    "C":   "C+",
    "C'":  "C'+",
    "J'":  "J",
    "P2":  "P2b",
    "T4'": "T4",
}


def _tracer(nom, fichier):
    """Deux prises pour l'auto-test d'isolation, et rien d'autre.

    `ESC_MUTATION_TRACE` fait consigner, pour chaque mutation posee: le nom du
    cas, le fichier, l'empreinte du fichier MUTE et le chemin de l'espace
    isole. `ESC_MUTATION_PAUSE` retient la matrice ce nombre de secondes une
    fois la mutation ecrite.

    Sans elles, `mutation_isolation_selftest.sh` devrait courir apres une
    fenetre de quelques millisecondes pour constater qu'une mutation existe
    dans l'espace isole et pas dans le depot — un test qui echoue une fois sur
    dix n'etablit rien. La trace sert aussi hors test: elle dit ce qu'une
    execution a reellement mute.
    """
    chemin = os.environ.get("ESC_MUTATION_TRACE")
    if chemin:
        import hashlib
        with open(f"{ESPACE}/{fichier}", "rb") as f:
            somme = hashlib.sha256(f.read()).hexdigest()
        with open(chemin, "a") as f:
            # LA RACINE DU WORKTREE EST TRACEE A PART. `ESPACE` designe le
            # SOUS-REPERTOIRE du projet; `git worktree remove` n'accepte que la
            # racine, et un nettoyage vise sur `ESPACE` echouait donc en
            # silence — deux worktrees restaient enregistres.
            f.write(f"{nom}\t{fichier}\t{somme}\t{ESPACE}\t{ESPACE_DEPOT}\n")
            f.flush()
    pause = float(os.environ.get("ESC_MUTATION_PAUSE", "0") or 0)
    if pause:
        import time
        time.sleep(pause)


def essayer(nom, point, fichier, paires, redondant=False,
            harnais="db/test/finalisation_contract.sh", prefixe="mu"):
    """Rend UN statut terminal. Jamais deux, jamais aucun."""
    code_court = _code(nom)
    cibles = _cibles(fichier, paires)
    textes_avant = {}
    for f, _pr in cibles:
        try:
            textes_avant[f] = open(f"{ESPACE}/{f}").read()
        except OSError as e:
            print(f"  STALE {nom}\n        -> {f} illisible: {e}")
            return STALE
    posees = []
    try:
        for f, pr in cibles:
            muter(f, pr)
            posees.append(f)
    except MotifAbsent as motif:
        for f in posees:
            restaurer(f)
        print(f"  STALE {nom}\n        -> le texte a muter n'existe plus: {motif}")
        return STALE
    # LE PATCH A-T-IL REELLEMENT PRIS, DANS CHAQUE FICHIER ATTENDU ? Un
    # `replace` qui ne change rien ne leve pas: il rend le meme texte. Le
    # controle tournerait alors sur le CANDIDAT et se declarerait « survivant »
    # — un faux rouge qui coute une journee.
    inertes = [f for f, _ in cibles
               if open(f"{ESPACE}/{f}").read() == textes_avant[f]]
    if inertes:
        for f, _ in cibles:
            restaurer(f)
        print(f"  INFRA {nom}\n        -> le patch n'a rien change dans "
              f"{', '.join(inertes)}: la mutation n'a pas ete posee.")
        return INFRA_FAILURE
    try:
        for f, _ in cibles:
            _tracer(nom, f)
        code, sortie = lancer(harnais, prefixe)
    finally:
        for f, _ in cibles:
            restaurer(f)

    # LE HARNAIS N'A PAS TOURNE: aucune conclusion sur la garantie.
    #
    # Codes 2 (refus de garde), 3 (decor non rendu, verrou detenu) et 4
    # (surface non executable ici). Les compter « aucun rouge » a deja fait
    # declarer dix controles creux alors qu'aucun n'avait ete exerce.
    if code in (2, 3, 4):
        print(f"  INFRA {nom}\n        -> le harnais a refuse (code {code}), "
              f"aucune conclusion possible:")
        for ligne in sortie.splitlines()[:3]:
            if ligne.strip():
                print("        " + ligne.strip()[:120])
        return INFRA_FAILURE

    # MISE A MORT A L'INSTALLATION. On exige le diagnostic NOMME, sinon un
    # echec quelconque — un decor casse, un cluster occupe — passerait pour une
    # mise a mort. C'est exactement ce qu'INFRA_FAILURE existe pour separer.
    motif_install = INSTALL_ASSERTION.get(code_court)
    if motif_install:
        if motif_install in sortie:
            print(f"  ok    {nom}\n        -> INSTALLATION REFUSEE en nommant "
                  f"l'invariant (code {code})")
            return KILLED_INSTALL_ASSERTION
        print(f"  ECHEC {nom}\n        -> l'installation n'a PAS refuse en "
              f"nommant « {motif_install[:60]} » (code {code})")
        for ligne in sortie.splitlines():
            if re.match(r"^ *(ok|ROUGE|ECHEC)", ligne):
                print("        " + ligne.strip()[:140])
        return SURVIVED

    # Les points se subdivisent (« 2a. », « 8b. », « A1. »): un rouge sur une
    # sous-verification EST un rouge du point.
    base = re.match(r"[0-9A-Z]+", point).group(0)
    # Deux libelles cohabitent, et c'est voulu. Les harnais de 6.3c disent
    # « ROUGE: » tout court; les anterieurs gardent « ROUGE ATTENDU (a fermer) »
    # plutot que de subir un remplacement global.
    rougit = re.search(
        rf"^ *(ROUGE ATTENDU \(a fermer\)|ROUGE|ECHEC): {base}[0-9a-z]?\.",
        sortie, re.M) is not None
    if redondant:
        if code == 0:
            print(f"  ok    {nom}\n        -> reste vert: la seconde garantie "
                  f"couvre; « {COMBINEE.get(code_court, '?')} » prouve le combine")
            return REDUNDANT_PROVEN
        print(f"  note  {nom}\n        -> rougit (code {code}): la redondance "
              "n'en est pas une")
        return KILLED_RUNTIME
    if rougit:
        print(f"  ok    {nom}\n        -> le point {point} rougit (code {code})")
        return KILLED_RUNTIME
    print(f"  ECHEC {nom}\n        -> le point {point} reste VERT: le controle "
          "ne porte rien")
    for ligne in sortie.splitlines():
        if re.match(r"^ *(ok|ROUGE|ECHEC)", ligne):
            print("        " + ligne.strip())
    return SURVIVED


# --------------------------------------------------------------------------
# LE CONTRAT DE FINALISATION (6.3b6b) — les cibles ont demenage en phase 0
# --------------------------------------------------------------------------
# La racine de confiance est passee dans `db/control_plane/0001_normative_seal.sql` (6.3b6c, deplace en 6.3b6d).
# Une matrice qui continuait de muter `0010` ne trouvait plus ses motifs — et
# `muter()` le dit, au lieu de rendre un vert silencieux.
MUT_INTENT = ("""  select * into intention from normative_finalization_intent;
  if not found then""",
              """  select * into intention from normative_finalization_intent;
  if false then""")
MUT_TXID = ("  if intention.prepare_txid <> txid_current() then", "  if false then")
MUT_VERROU_RECORD = ("""  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction: '""",
                     """  if false then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction: '""")
MUT_VERROU_PREPARE = ("""  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction. La '""",
                      """  if false then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction. La '""")
MUT_GC_INTENTION = ("""  delete from normative_finalization_intent
   where prepare_txid <> txid_current();""",
                    """  -- ramassage retire par mutation""")
MUT_EXEMPTION = ("""         m.oid = normative_control_plane_oid()
         and m.rolname = normative_control_plane()""",
                 """         m.rolname = normative_control_plane()""")
MUT_COHERENCE = ("""      if not exists (select 1 from pg_roles
                      where oid = plan_oid and rolname = plan_nom) then""",
                 """      if false then""")

CAS = [
    ("1  le manifeste n'est plus compare", "1", S,
     [("  if courant is distinct from p_manifeste then", "  if false then")], False),
    ("2  un seul des trois refus d'ecriture directe", "2", S,
     [MUT_INTENT], True),
    ("2b LES TROIS refus d'ecriture directe", "2", S,
     [MUT_INTENT, MUT_TXID, MUT_VERROU_RECORD], False),
    ("3  un seul des deux controles d'identite du plan", "3", S,
     [MUT_EXEMPTION], True),
    ("3b LES DEUX controles d'identite du plan", "3", S,
     [MUT_EXEMPTION, MUT_COHERENCE], False),
    ("4  la finalisation n'est plus serialisee", "4", S,
     [("  perform pg_advisory_xact_lock(hashtext('eurostruct.normative_finalisation'));",
       "  -- verrou retire par mutation")], False),
    ("5  le declencheur PENDING passe apres les autres", "5", M,
     [("create trigger normative_activation_required_grants",
       "create trigger zz_activation_required_grants"),
      ("create trigger normative_activation_required_grant_revocations",
       "create trigger zz_activation_required_grant_revocations"),
      ("create trigger normative_activation_required_confirmations",
       "create trigger zz_activation_required_confirmations"),
      ("create trigger normative_activation_required_confirmation_revocations",
       "create trigger zz_activation_required_confirmation_revocations")], False),
    ("6  policy FOR ALL sur l'activation", "6", S,
     [("""create policy normative_activation_lecture on normative_activation
  for select to eurostruct_normative_activator using (true);
create policy normative_activation_ecriture on normative_activation
  for insert to eurostruct_normative_activator with check (true);""",
       """create policy normative_activation_activateur on normative_activation
  for all to eurostruct_normative_activator using (true) with check (true);""")], False),
    # LE TEXTE MUTE SUIT LE CODE, SINON LE CONTROLE MEURT EN SILENCE. Mesure
    # du 27/08: ce controle etait PERIME depuis que `eurostruct_authority_backend`
    # a rejoint le jeu canonique de `run.sh` — la matrice le comptait « non
    # execute », donc la garantie « l'activator doit figurer au jeu canonique »
    # n'etait plus verifiee par mutation, sans que rien ne rougisse.
    ("7  l'activator quitte le jeu canonique", "7", R,
     [("""CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment
            eurostruct_authority_backend)""",
       """CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment
            eurostruct_authority_backend)""")], False),
    ("8  la separation plan/migrateur est retiree", "8b", S,
     [("  if d_oid = m_oid or d_nom = m_nom then", "  if false then")], False),
]

# --------------------------------------------------------------------------
# LA FERMETURE DE L'AUTORITE (6.3b6c) — sept garanties, sept mutations
# --------------------------------------------------------------------------
CAS_AUTORITE = [
    # A — LE LEVIER EST LE DECOR, PAS LA MIGRATION. Ce qui garantit que le
    # migrateur n'atteint jamais l'activateur, c'est que personne ne le lui
    # prete: 0010 ne le demande plus, et le deploiement ne l'accorde plus.
    # Muter la liste d'emprunt de 0010 ferait seulement echouer la migration —
    # un refus, pas une mesure de A1. On simule donc un deploiement qui le
    # prete, et A1 doit le voir.
    ("A  le deploiement prete l'activateur au migrateur", "A1", H,
     [("""grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL""",
       """grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
grant eurostruct_normative_activator to "$MIG" with admin option;
SQL""")], False),
    ("B  les tables de preuve restent au migrateur", "B1", M,
     [("alter table normative_authorisation_grants          owner to eurostruct_normative_writer;",
       "-- transfert retire par mutation")], False),
    ("B' la RLS des tables de preuve n'est plus forcee", "B1", M,
     [("alter table normative_authorisation_grants          force row level security;",
       "-- FORCE retire par mutation")], False),
    # LES DEUX COUCHES DE « B », EPROUVEES SEPAREMENT.
    #
    # `B` ci-dessus ne peut PAS atteindre la defense d'execution: 0013 refuse
    # d'installer la mutation, en nommant l'invariant, et la transaction est
    # entierement annulee. C'est une mise a mort — la plus precoce possible —
    # et non un controle creux. Mesure du 27/08 sur base jetable: registre a
    # 12 lignes (0001 a 0012), aucune table, fonction ni policy de 0013.
    #
    # Reste a prouver que la defense d'EXECUTION existe elle aussi, et qu'elle
    # n'est pas seulement masquee par la precedente. `B=` neutralise donc la
    # postcondition de 0013 ET le `set role` de sa section F — le migrateur
    # possede les tables, il peut donc y poser les policies — de sorte que le
    # schema s'installe REELLEMENT avec des tables restees au migrateur. Le
    # chemin aval est alors parcouru, et B1 doit rougir.
    #
    # Mesure du 27/08: « ROUGE: B1. APRES ACTIVATION, le migrateur possede
    # encore: normative_authorisation_grants ».
    ("B= la propriete reste au migrateur, postcondition neutralisee", "B1",
     [(M, [("alter table normative_authorisation_grants          owner to eurostruct_normative_writer;",
            "-- transfert retire par mutation")]),
      (A13, [("    if o <> 'eurostruct_normative_writer' then",
              "    if false then"),
             ("""set role eurostruct_normative_writer;

revoke insert on normative_authorisation_grants          from normative_backend;""",
              """-- set role neutralise: le migrateur possede les tables

revoke insert on normative_authorisation_grants          from normative_backend;""")])],
     None, False),
    # LES DEUX COUCHES DE « B' » ET DE « B= », comme pour « B ».
    #
    # L'interception a l'installation est la mise a mort la plus precoce, et
    # elle est reelle. Mais elle MASQUE la couche d'execution: `B1` — « apres
    # activation, le migrateur ne possede plus les tables, RLS forcee » — ne
    # serait plus exerce par aucune mutation. On neutralise donc AUSSI la
    # branche de l'agregee qui intercepte, pour que le schema s'installe et
    # que le chemin aval soit parcouru.
    ("B'= la RLS n'est plus forcee, agregee neutralisee", "B1",
     [(M, [("alter table normative_authorisation_grants          force row level security;",
            "-- FORCE retire par mutation")]),
      (A14, [("""      if not (r.relrowsecurity and r.relforcerowsecurity) then
        ecarts := ecarts || format(
          'AUTHORITY_COMPOSITION_FORCE_RLS_MISSING: %s a rls=%s force=%s',
          nom, r.relrowsecurity, r.relforcerowsecurity);
      end if;""",
              "      null;  -- branche FORCE RLS neutralisee par mutation")])],
     None, False),
    ("B== la propriete reste au migrateur, agregee neutralisee aussi", "B1",
     [(M, [("alter table normative_authorisation_grants          owner to eurostruct_normative_writer;",
            "-- transfert retire par mutation")]),
      (A13, [("    if o <> 'eurostruct_normative_writer' then",
              "    if false then"),
             ("""set role eurostruct_normative_writer;

revoke insert on normative_authorisation_grants          from normative_backend;""",
              """-- set role neutralise: le migrateur possede les tables

revoke insert on normative_authorisation_grants          from normative_backend;""")]),
      (A14, [("""      if r.proprietaire <> 'eurostruct_normative_writer' then
        ecarts := ecarts || format(
          'AUTHORITY_COMPOSITION_TABLE_OWNER_MISMATCH: %s appartient a « %s »',
          nom, r.proprietaire);
      end if;""",
              "      null;  -- branche proprietaire neutralisee par mutation")])],
     None, False),
    ("C  un seul des deux refus de composition", "C2", S,
     [MUT_TXID], True),
    # TROIS garanties, pas deux: la preparation exige elle aussi le verrou, et
    # c'est elle qui refuse en premier dans ce parcours.
    ("C+ LES TROIS refus de composition", "C2", S,
     [MUT_TXID, MUT_VERROU_RECORD, MUT_VERROU_PREPARE], False),
    ("C' un seul des deux refus de preparation isolee", "C1", S,
     [MUT_VERROU_PREPARE], True),
    # TROIS ici aussi: le verrou de preparation, le ramassage de l'intention
    # morte, et la meme-transaction exigee par l'ecriture de confiance.
    ("C'+ verrou de preparation, rederivation ET meme transaction", "C1", S,
     [MUT_VERROU_PREPARE, MUT_GC_INTENTION, MUT_TXID], False),
    # DEUX SITES, DEUX GARANTIES — et l'ancien controle n'en mutait qu'UN.
    #
    # `normative_finalize_deployment` compare le manifeste a DEUX endroits, et
    # ils ne disent pas la meme chose: le premier est le chemin rapide
    # d'idempotence, AVANT le verrou; le second est la relecture APRES le
    # verrou, qui est tout l'objet du verrou — c'est ce que voit le perdant
    # d'une course. Les deux blocs sont textuellement IDENTIQUES.
    #
    # `muter()` remplace la PREMIERE occurrence. L'ancien controle « D »
    # neutralisait donc toujours le chemin rapide, et jamais la relecture: la
    # garantie du second site n'etait pas verifiee par mutation, et rien ne le
    # disait. Le pre-vol l'a nomme le 27/08 en refusant une cible AMBIGUE.
    #
    # Chaque site est desormais ancre par son commentaire, qui lui est propre.
    ("D  l'idempotence AVANT le verrou ne compare plus le manifeste", "D", S,
     [("""  -- IDEMPOTENCE, avant meme le verrou: une finalisation deja faite ne doit ni
  -- attendre ni echouer bruyamment.
  if normative_activation_state() = 'ACTIVE' then
    perform normative_exiger_manifeste_approuve(p_manifeste);""",
       """  -- IDEMPOTENCE, avant meme le verrou: une finalisation deja faite ne doit ni
  -- attendre ni echouer bruyamment.
  if normative_activation_state() = 'ACTIVE' then""")], False),
    ("D2 la relecture APRES le verrou ne compare plus le manifeste", "D", S,
     [("""  -- COMMITTED, chaque instruction d'une fonction VOLATILE prend un nouvel
  -- instantane: le perdant voit donc ici ce que le gagnant a valide pendant
  -- qu'il attendait, et rend le meme resultat que s'il etait arrive apres.
  if normative_activation_state() = 'ACTIVE' then
    perform normative_exiger_manifeste_approuve(p_manifeste);""",
       """  -- COMMITTED, chaque instruction d'une fonction VOLATILE prend un nouvel
  -- instantane: le perdant voit donc ici ce que le gagnant a valide pendant
  -- qu'il attendait, et rend le meme resultat que s'il etait arrive apres.
  if normative_activation_state() = 'ACTIVE' then""")], False),
    ("E  une exemption de service redevient nominale", "E", S,
     [("""         p.oid = normative_control_plane_oid()
         and p.rolname = normative_control_plane()""",
       """         p.rolname = normative_control_plane()""")], False),
    ("G  le diagnostic de restauration disparait", "G", S,
     [("-- RESTAURATION INTER-CLUSTER — le cas le plus probable de ce refus.",
       "-- Transport de base — le cas le plus probable de ce refus."),
      ("CAS COURANT: RESTAURATION INTER-CLUSTER", "CAS COURANT: transport de base")], False),

    # ----------------------------------------------------------------------
    # LE CYCLE DE VIE DU DECOR — trois mutations, trois couches distinctes
    # ----------------------------------------------------------------------
    # CE QUI EST EN JEU. Un refus a l'installation qui ne rend pas le decor
    # laisse les roles canoniques dans le cluster; tous les scenarios suivants
    # echouent alors en « phase 0 refusee », le harnais rend « rien d'evalue »,
    # et CETTE campagne lit ce silence comme un SURVIVANT. La contamination du
    # scenario suivant est une erreur d'infrastructure, jamais une mise a mort:
    # ces trois controles existent pour que la distinction reste verifiee.
    #
    # Le scenario H de `authority_closure.sh` est ce qui les tue. Mesure du
    # 28/08 sur base jetable, en retirant `esc_decor_abandonner` du refus de
    # phase 1: H3 rougit sur 12 residus — sept roles canoniques, trois roles de
    # harnais, une base, neuf appartenances.
    #
    # LE POINT EST CELUI QUE LE HARNAIS IMPRIME, pas un identifiant de mutation.
    # Premiere version: points « GC1 », « GC2 », « GC3 » — la campagne cherche
    # `ROUGE: <point>.` et le harnais ecrivait `ROUGE: H3-H8.`. Les trois ont
    # ete comptees SURVIVED alors que la sortie contenait le rouge. Les
    # etiquettes du harnais ET les points de la matrice ont ete alignes.
    #
    # GC2 VISE UN AUTRE POINT QUE GC1, et ce n'est pas un detail: le refus de
    # phase 0 et celui de phase 1 sont deux chemins distincts. GC2 survivait
    # aussi parce qu'aucun scenario ne provoquait jamais un refus du sceau.
    ("GC1 le refus de phase 1 ne rend plus le decor", "H3", H,
     [("""      esc_diag_rapporter "decor $s / phase 1 / $(basename "$f")" "$sortie"
      esc_decor_abandonner
      return 1""",
       """      esc_diag_rapporter "decor $s / phase 1 / $(basename "$f")" "$sortie"
      return 1""")], False),
    ("GC2 le refus de phase 0 ne rend plus le decor", "H6", H,
     [("""    esc_diag_rapporter "decor $s / phase 0 (sceau)" "$sortie"
    esc_decor_abandonner
    return 1""",
       """    esc_diag_rapporter "decor $s / phase 0 (sceau)" "$sortie"
    return 1""")], False),
    # LA COUCHE BIBLIOTHEQUE. `GC1` et `GC2` retirent l'APPEL; `GC3` vide la
    # fonction appelee. Les deux preuves sont distinctes: un harnais peut
    # appeler correctement un helper qui ne fait rien.
    ("GC3 esc_decor_abandonner ne ferme plus le decor", "H3", LIB,
     [("""esc_decor_abandonner() {
  local code="${1:-1}"
  esc_decor_fermer
  return "$code"
}""",
       """esc_decor_abandonner() {
  local code="${1:-1}"
  return "$code"
}""")], False),
]


# --------------------------------------------------------------------------
# L'INDUSTRIALISATION DU SCEAU (6.3b6d) — treize garanties, treize mutations
# --------------------------------------------------------------------------
# Elles portent sur trois harnais differents, et c'est le sujet: une garantie
# qui vit dans `0001_normative_seal.sql` mais n'est constatee que par
# `official_deployment.sh` ne serait pas couverte par une matrice qui ne
# lancerait qu'un seul harnais.
CAS_SCEAU = [
    ("I3  la garde de reexecution ne refuse plus", "I3", S,
     [("""  raise exception
    'SEAL_ALREADY_INSTALLED: le sceau « % » est deja pose sur cette base, et '""",
       """  return;
  raise exception
    'SEAL_ALREADY_INSTALLED: le sceau « % » est deja pose sur cette base, et '""")], False),
    ("I4  le controle de completude du sceau disparait", "I4", S,
     [("  if presents <> array_length(objets, 1) then", "  if false then")], False),
    ("I2  la phase 1 n'exige plus la version du sceau", "I2", M,
     [("  if not (posee = any (compatibles)) then", "  if false then")], False),
    ("J   la liaison poseur/finaliseur est retiree", "J", S,
     [("    if d_oid <> p_oid or d_nom <> p_nom then", "    if false then")], False),
    # REDONDANCE VOULUE: le nom seul et l'OID seul attrapent chacun le
    # contre-exemple J, ou les deux different. En retirer UN ne doit rien
    # rougir; c'est ce qui distingue une double verification d'un doublon.
    ("J'  une SEULE des deux moities de l'identite", "J", S,
     [("    if d_oid <> p_oid or d_nom <> p_nom then", "    if d_oid <> p_oid then")], True),
    ("M   le niveau d'assurance est toujours « contenu »", "M", S,
     [("""       case when c.rolsuper or s.rolsuper then 'UNCONTAINED_SUPERUSER'
            else 'CONTAINED_NON_SUPERUSER' end""",
       """       'CONTAINED_NON_SUPERUSER'""")], False),
    ("K1  une primitive mutante est ouverte a la gouvernance", "K1", S,
     [("""revoke all on function normative_prepare_activation(text) from public;""",
       """revoke all on function normative_prepare_activation(text) from public;
grant execute on function normative_prepare_activation(text) to normative_governance;""")], False),
]

CAS_RESTAURATION = [
    ("L3  le marqueur du diagnostic de restauration disparait", "L3", S,
     [("          'CAS COURANT: RESTAURATION INTER-CLUSTER — les OID ne survivent pas '",
       "          'CAS COURANT: transport de base — les OID ne survivent pas '")], False),
    ("L4  le diagnostic promet a nouveau une reprise", "L4", S,
     [("          'une base NEUVE sur ce cluster (phases 0, 1, 2) et reprenez-y les '",
       "          'refinalisee sur place. Deployez une base NEUVE et reprenez-y les '")], False),
]

CAS_COMMANDE = [
    ("N4  la commande accepte deux acteurs identiques", "N4", CMD,
     [('if [[ "$PLAN_USER" == "$MIG_USER" ]]; then', 'if false; then')], False),
    ("N5  le mode strict ne refuse plus l'assurance degradee", "N5", CMD,
     [("""  if ((STRICT)); then
    echec "niveau d'assurance « $SCEAU_ASSURANCE ».""",
       """  if false; then
    echec "niveau d'assurance « $SCEAU_ASSURANCE ».""")], False),
    ("N3  la relance reaccorde les emprunts sur une base ACTIVE", "N3", CMD,
     [('if [[ "$DEJA" == "ACTIVE" ]]; then', 'if false; then')], False),
    # N1 est couvert par tout ce qui precede: aucune de ces mutations ne peut
    # rougir si le deploiement complet ne tourne pas. Il n'a donc pas de
    # mutation propre, et le dire vaut mieux que d'en inventer une.
    #
    # N6 — « la commande ne contient aucune destruction » — n'en a pas non plus,
    # DELIBEREMENT: sa mutation consisterait a ECRIRE un `drop database` dans un
    # outil de deploiement, meme sur une branche morte. Le fichier est restaure
    # apres coup, mais une interruption au mauvais moment le laisserait en
    # place. Le risque n'est pas proportionne a ce que la mutation etablirait
    # d'un `grep`.
]

# --------------------------------------------------------------------------
# LA REPRISE SURE DE LA COMMANDE (6.3b6e) — treize mutations
# --------------------------------------------------------------------------
# Elles portent sur QUATRE fichiers: la commande, l'applicateur de migrations,
# le registre (dans `0001`) et une migration temoin. Ce n'est pas un accident
# de decoupage: la reprise n'est une garantie que si les quatre tiennent
# ENSEMBLE, et une matrice qui n'en muterait qu'un le laisserait croire.
#
# DEUX PAIRES DE REDONDANCE Y FIGURENT, et elles sont le sujet:
#   P2  — l'ADMIN preexistant ET l'octroi constate;
#   T4  — le portillon (hors transaction) ET le controle re-fait a l'ecriture.
# Pour chacune, retirer UNE garantie doit rester vert, et retirer LES DEUX doit
# rougir. C'est ce qui distingue une double verification d'un doublon.
#
# IL Y EN AVAIT UNE TROISIEME, ET ELLE N'EN ETAIT PAS UNE. La borne de longueur
# et l'interpolation sure etaient declarees redondantes pour R1: retirer les
# deux devait le faire rougir, et ne le faisait pas. La cause n'etait pas dans
# la commande mais dans le contre-exemple — son nom hostile depassait 63 octets,
# PostgreSQL le tronquait, et `verifier_identite` refusait AVANT l'etape 3, seul
# site d'injection. R1 passait sans jamais l'atteindre.
#
# Les deux garanties sont donc separees, et chacune a son contre-exemple:
# l'interpolation repond de R1, la borne repond de R2 — deux noms qui ne
# different qu'apres le 63e octet designent le meme role.
MUT_P2_ADMIN = ("""  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'MEMBER WITH ADMIN OPTION')::text" 2>/dev/null)" != "true" ]]; then""",
                """  if false; then""")
MUT_P2_CONSTAT = ("""  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'USAGE')::text" 2>/dev/null)" != "true" ]]; then""",
                  """  if false; then""")
MUT_R1_BORNE = ("  if [[ ${#valeur} -eq 0 || ${#valeur} -gt 63 ]]; then",
                "  if false; then")
# L'INTERPOLATION SURE, RETIREE. Le heredoc cite (`<<'SQL'`) devient non cite,
# et `:"m"` — que psql sait citer comme IDENTIFIANT — devient une substitution
# shell. C'est la forme exacte qui rendait la commande injectable avant 6.3b6e.
MUT_R1_INTERP = ("""SORTIE=$(plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" 2>&1 <<'SQL'
grant eurostruct_normative_writer    to :"m" with admin option;
grant eurostruct_normative_bootstrap to :"m" with admin option;
SQL
)""",
                 """SORTIE=$(plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG_USER" with admin option;
grant eurostruct_normative_bootstrap to "$MIG_USER" with admin option;
SQL
)""")
MUT_T4_PORTILLON = ("  return 'MISMATCH';", "  return 'DEJA';")
MUT_T4_ECRITURE = ("  if found and connu <> p_sum then", "  if false then")

CAS_REPRISE = [
    ("P2  l'ADMIN preexistant n'est plus exige", "P2", CMD,
     [MUT_P2_ADMIN], True),
    ("P2b l'ADMIN exige ET l'octroi constate", "P2", CMD,
     [MUT_P2_ADMIN, MUT_P2_CONSTAT], False),
    ("Q   la compensation ne se declenche plus", "Q1", CMD,
     [("  if [[ $EMPRUNTS_ACCORDES -eq 1 && $FINALISE -eq 0 ]]; then",
       "  if false; then")], False),
    # UNE CHAINE VIDE REDEVIENT UNE PREUVE D'ABSENCE. C'est exactement l'ancien
    # defaut: la question sans reponse et le migrateur sans capacite rendaient
    # la meme chose.
    ("Q7  une question sans reponse vaut « aucune capacite »", "Q7", CMD,
     [("  [[ $code -ne 0 ]] && return 1",
       '  [[ $code -ne 0 ]] && { CAPACITES=""; return 0; }')], False),
    ("Q6  la reprise explicite n'existe plus", "Q6", CMD,
     [("    --recover-pending) RECOVER=1 ;;\n", "")], False),
    # LA FERMETURE INDIRECTE. Sans le `\\if`, la transaction commet toujours:
    # la reprise se declare reussie alors qu'une voie indirecte subsiste, et
    # elle a en plus consomme les deux octrois qu'elle devait rendre.
    ("Q8  la voie indirecte n'est plus fermee", "Q8", CMD,
     [("\\if :esc_residu", "\\if false")], False),
    ("S3  le verrou n'est plus reconstate avant l'octroi", "S3", CMD,
     [("etape_mutante \"l'octroi des emprunts\"\n", "")], False),
    ("S4  le verrou n'est plus reconstate avant la reprise", "S4", CMD,
     [("  etape_mutante \"la revocation de reprise\"\n", "")], False),
    ("S2  le verrou n'est plus reconstate avant chaque etape", "S2", CMD,
     [('  etape_mutante "$(basename "$f")"\n', ""),
      ('etape_mutante "la finalisation"\n', "")], False),
    ("R1  l'interpolation sure du nom de migrateur", "R1", CMD,
     [MUT_R1_INTERP], False),
    ("R2  la borne de longueur des identifiants", "R2", CMD,
     [MUT_R1_BORNE], False),
    ("S1  le verrou de deploiement ne refuse plus", "S1", CMD,
     [('if [[ "$PRIS" != "true" ]]; then', "if false; then")], False),
    ("T1  le registre repond toujours « jamais appliquee »", "T1", APP,
     # LE MOTIF SUIT LE CODE, ET IL AVAIT CESSE DE LE SUIVRE. Il visait
     # « echo "$reponse" », forme abandonnee quand `esc_migration_etat()` est
     # passee aux variables globales pour ne plus perdre le diagnostic dans un
     # sous-shell. Le controle T1 etait donc INAPPLICABLE depuis ce changement:
     # la garantie « le registre ne repond pas toujours ABSENTE » n'avait plus
     # ete verifiee par mutation. Mesure, pas relecture — la campagne complete
     # s'est arretee dessus au 45e controle.
     [('    ABSENTE|DEJA|MISMATCH) rm -f "$errfic"; ESC_MIGRATION_GATE_STATE="$reponse" ;;',
       '    ABSENTE|DEJA|MISMATCH) rm -f "$errfic"; ESC_MIGRATION_GATE_STATE="ABSENTE" ;;')], False),
    # LA CLASSIFICATION STRICTE DE LA PREMIERE INTERROGATION, AUX DEUX ENDROITS
    # OU ELLE VIT. La mutation retablit l'ancien defaut: tout ce qui n'est ni
    # « t » ni « f » — sortie vide, connexion tombee — repasse pour benin.
    #
    # DEUX PAIRES, ET C'EST UNE MESURE. N'en retirer qu'une ne rougissait plus
    # rien depuis que `esc_verifier_historique` interroge `to_regclass` AVANT la
    # boucle: c'est elle qui attrapait la panne, et le contre-exemple restait
    # vert. Les deux gardes se suppleent — retirer les deux est la seule facon
    # de savoir si l'une d'elles porte quelque chose.
    ("T7  une interrogation en echec vaut « registre absent »", "T7", APP,
     [('''    *)
      ESC_MIGRATION_DIAG="$(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
      [[ -n "$ESC_MIGRATION_DIAG" ]] \\
        || ESC_MIGRATION_DIAG="reponse « ${presence:-<vide>} », attendu « t » ou « f »"''',
       '''    *)
      rm -f "$errfic"; echo "ABSENTE"; return 0
      ESC_MIGRATION_DIAG="$(grep -m2 -v '^[[:space:]]*$' "$errfic" | cut -c1-300)"
      [[ -n "$ESC_MIGRATION_DIAG" ]] \\
        || ESC_MIGRATION_DIAG="reponse « ${presence:-<vide>} », attendu « t » ou « f »"'''),
      ('''      ESC_HISTORIQUE_DIAG="MIGRATION_LEDGER_UNREADABLE: l'existence du registre n'a pas pu
       etre etablie avant de verifier l'historique.''',
       '''      rm -f "$errfic"; return 0
      ESC_HISTORIQUE_DIAG="MIGRATION_LEDGER_UNREADABLE: l'existence du registre n'a pas pu
       etre etablie avant de verifier l'historique.''')],
     False),
    # LE SOUS-SHELL, REMIS. `$( ... )` s'execute dans un sous-shell: la globale
    # que la fonction y pose meurt avec lui, et le rapport retombe sur
    # « <aucun> » a l'endroit ou l'exploitant a besoin de la cause.
    ("T17 le diagnostic du portillon repasse par un sous-shell", "T17", APP,
     [('''  esc_migration_etat "$fichier" "$@"
  etat="$ESC_MIGRATION_GATE_STATE"''',
       '''  etat="$( esc_migration_etat "$fichier" "$@"
             printf '%s' "$ESC_MIGRATION_GATE_STATE" )"''')], False),
    # LE RAPPROCHEMENT D'UNE BASE ACTIVE, EN DEUX MORCEAUX INDEPENDANTS: la
    # boucle des empreintes (T13, T15) et la verification d'historique (T14).
    ("T15 le rapprochement d'une base ACTIVE ne se fait plus", "T15", CMD,
     [('  ECART_ACTIVE=""\n  for f in "$MIGRATIONS_DIR"/*.sql; do',
       '  ECART_ACTIVE=""\n  for f in ; do')], False),
    ("T14 l'historique n'est plus verifie sur une base ACTIVE", "T14", CMD,
     [('  if ! esc_verifier_historique "$MIGRATIONS_DIR" mig; then\n'
       '    echec "$ESC_HISTORIQUE_DIAG"\n  fi',
       '  if false; then\n    echec "$ESC_HISTORIQUE_DIAG"\n  fi')], False),
    ("T8  le prefixe exact n'est plus exige", "T8", APP,
     [('    if [[ "${inscrites[$i]}" != "${locaux[$i]}" ]]; then',
       "    if false; then")], False),
    ("T12 l'identite du migrateur n'est plus exigee", "T12", APP,
     [('  if [[ -n "$applied_by" && "$applied_by" != "$moi" ]]; then',
       "  if false; then")], False),
    ("T4  le portillon ne signale plus la divergence", "T4", INIT,
     [MUT_T4_PORTILLON], False),
    ("T4' le controle re-fait a l'ecriture du registre", "T4", INIT,
     [MUT_T4_ECRITURE], True),
    ("T5  une migration perd sa transaction", "T5", RLS,
     [("begin;", "-- begin retire par mutation")], False),
    # UNE SEULE MUTATION POUR U1 ET U2, ET C'EST LE PROPOS. Brancher sur la
    # prose casse les deux a la fois: le message reformule n'est plus reconnu
    # (U1), et n'importe quel SQLSTATE portant le meme texte passe (U2). Les
    # deux contre-exemples sont donc exerces contre le MEME defaut, ce qui est
    # exactement ce qu'ils ont ete ecrits pour attraper.
    ("U1  le branchement suit la prose et non le SQLSTATE", "U1", CMD,
     [('sqlstate() { grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE"; }',
       'sqlstate() { case "$1" in\n'
       '  ES001) grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE" ;;\n'
       '  *) grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE" ;;\n'
       'esac; }')], False),
    ("U2  le meme branchement, vu par l'autre contre-exemple", "U2", CMD,
     [('sqlstate() { grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE"; }',
       'sqlstate() { case "$1" in\n'
       '  ES001) grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE" ;;\n'
       '  *) grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE" ;;\n'
       'esac; }')], False),
    ("V1  PGOPTIONS n'est plus efface", "V1", CMD,
     [("unset PGSERVICE PGSERVICEFILE PGPASSFILE PGOPTIONS PGDATABASE PGHOSTADDR \\",
       "unset PGSERVICE PGSERVICEFILE PGPASSFILE PGDATABASE PGHOSTADDR \\")], False),
    ("V2  la politique TLS stricte ne s'applique plus", "V2", CMD,
     [("if ((STRICT)) && ! cible_locale; then", "if false; then")], False),
    # V3 TIENT SUR DEUX GARANTIES QUI NE SE SUPPLEENT PAS: porter la CA depuis
    # l'URL, et verifier qu'elle existe. Retirer l'une OU l'autre doit rougir —
    # ce n'est pas une redondance, c'est une chaine.
    ("V3  la CA de l'URL n'est plus portee", "V3", CMD,
     # SECOND MOTIF PERIME, TROUVE PAR LE PRE-VOL ET NON PAR CHANCE. Il visait
     # la ligne terminee par « ), »; le decoupeur a depuis ferme sa boucle sur
     # cette meme ligne, qui finit maintenant par « )): ». Un caractere, et le
     # controle V3 ne s'appliquait plus. Il aurait arrete la campagne suivante
     # exactement comme T1 avait arrete celle-ci.
     [('             ("SSLROOTCERT", q.get("sslrootcert", [""])[0])):',
       '             ("SSLROOTCERT", "")):')], False),
    # LA VERIFICATION ENTIERE, ET NON UN DE SES DEUX TESTS. Mesure: neutraliser
    # le seul `-e` ne rougit rien — un fichier absent echoue AUSSI le `-r` qui
    # suit. Les deux tests se suppleent pour ce contre-exemple; c'est la
    # fonction qu'il faut retirer pour savoir si elle porte quelque chose.
    ("V3p la matiere TLS n'est plus verifiee du tout", "V3", CMD,
     [('  [[ -n "$chemin" ]] || return 0\n  [[ "$chemin" == "system" ]] && return 0',
       '  return 0')], False),
    ("V3b un parametre TLS inconnu est ignore", "V3b", CMD,
     [("if inconnus:", "if False:")], False),
    # LE CO-PROCESSUS DU VERROU EST UN PROCESSUS COMME LES AUTRES, et c'est
    # celui qu'on oublie: il ne passe ni par `plan()` ni par `mig()`.
    ("V4  le co-processus du verrou perd la CA du plan", "V4", CMD,
     [('                    "${PLAN_TLS[@]}" psql -X -q -At -d "$BASE" 2>&1; }',
       '                    psql -X -q -At -d "$BASE" 2>&1; }')], False),
    ("V5  sslcert et sslkey redeviennent « portes »", "V5", CMD,
     [('portes = ("sslmode", "sslrootcert")',
       'portes = ("sslmode", "sslrootcert", "sslcert", "sslkey")')], False),
]

# --------------------------------------------------------------------------
# LE MOINDRE PRIVILEGE DU SCEAU (6.3b6e, point 7) — une mutation
# --------------------------------------------------------------------------
CAS_ACL_SCEAU = [
    ("W1  les metadonnees du sceau redeviennent publiques", "W1", S,
     [("grant select on normative_seal_metadata to eurostruct_deployment;",
       "grant select on normative_seal_metadata to public;\n"
       "grant select on normative_seal_metadata to eurostruct_deployment;")], False),
]

BOUCLE_VIVACITE = (
    "            'while :; do\\n'\n"
    '            \'  [[ -s "$ETAT_HARNAIS" ]] && { GATE=PRESENT; break; }\\n\'\n'
    '            \'  kill -0 "$HARNAIS" 2>/dev/null \'\n'
    "            '|| { GATE=HARNAIS_TERMINE_AVANT_BLOCKED; break; }\\n'\n"
    "            '  sleep 0.05\\n'\n"
    "            'done\\n'\n"
)
VERIF_VIVACITE = (
    '            \'  [[ "$GH" == "$HARNAIS" && "$GP" == "$PGID" \'\n'
    '            \'     && "$GT" == "${ESC_MUTATION_JETON:-}" && "$GS" == GATE_ARMED ]] \'\n'
    "            '     || ETAT=FAILED\\n'\n"
)

# --------------------------------------------------------------------------
# LA BARRIERE DE VIVACITE (6.3b6e) — la neuvieme, et elle vise l'INSTRUMENT
# --------------------------------------------------------------------------
# LES HUIT AUTRES MUTATIONS VISENT LE PRODUIT. Celle-ci vise le wrapper que
# cette matrice pose elle-meme autour de chaque harnais — c'est-a-dire une
# piece de l'INSTRUMENT. Elle y a sa place pour la meme raison qu'un defaut
# connu dans l'instrument rend sa preuve irrecevable: si la barriere de
# vivacite pouvait disparaitre sans que rien ne rougisse, tous les verdicts
# rendus par cette matrice reposeraient sur un `READY` qui ne promet rien.
#
# CE QUE LA MUTATION RETIRE. Le wrapper cesse d'attendre la preuve que le
# harnais est TENU, et cesse de verifier l'identite de cette preuve: il publie
# `READY` sur une PHOTOGRAPHIE, exactement comme avant `ef90bb7`.
#
# POURQUOI CE HARNAIS-LA. `gate_protocol_selftest.sh` est la seule surface qui
# EXTRAIT ce wrapper de ce fichier et le met en echec — et il l'extrait de
# l'espace isole, donc de la version MUTEE. Il ne demande aucune base.
#
# LE POINT `B1` EST NOMME PAR LE HARNAIS LUI-MEME. Ses cas sont numerotes par
# CAS, pas par garantie; sans le verdict « ECHEC: B1. », six cas rougiraient
# sans qu'aucune ligne ne designe la garantie perdue, et la mutation serait
# comptee CREUSE alors qu'elle est parfaitement detectee.
CAS_BARRIERE = [
    ("B1  la barriere de vivacite est retiree du wrapper", "B1",
     "db/test/mutation_matrix.py",
     [(BOUCLE_VIVACITE, "            'GATE=PRESENT\\n'\n"),
      (VERIF_VIVACITE, "            '  :\\n'\n")], False),
]

# --------------------------------------------------------------------------
# UN FILTRE, POUR REJOUER CE QU'ON VIENT DE CORRIGER
# --------------------------------------------------------------------------
#   python3 db/test/mutation_matrix.py            les 48 controles
#   python3 db/test/mutation_matrix.py R1 R2 P2   ceux dont le nom commence
#                                                 par l'un de ces mots
#
# 48 controles, c'est autant d'executions completes de harnais: pres d'une
# heure et demie. Corriger un controle creux et revalider LUI SEUL demandait
# jusqu'ici de tout relancer, ou de commenter des lignes — c'est-a-dire de
# modifier le fichier qui juge.
#
# LE VERDICT FINAL LE DIT. Une execution filtree n'annonce jamais que les 48
# controles portent quelque chose: elle ne les a pas exerces, et un compte
# rendu partiel presente comme complet est exactement ce que ce projet refuse.
FILTRE = [a for a in sys.argv[1:] if not a.startswith("-")]


def retenu(cas):
    return not FILTRE or any(cas[0].split()[0] == f for f in FILTRE)


def lot(cas, **kw):
    gardes = [c for c in cas if retenu(c)]
    return [essayer(*c, **kw) for c in gardes]


# L'ESPACE ISOLE EST CREE ICI, AVANT TOUTE MUTATION.
#
# Il remplace `exiger_arbre_propre()`, qui etait DEFINIE ET JAMAIS APPELEE — sa
# docstring affirmait pourtant etre « la seule chose qui rend l'outil utilisable
# sans precaution particuliere ». Une garde non executee n'est pas une garde.
#
# Elle ne suffirait de toute facon pas: elle regarde l'arbre au DEMARRAGE, et
# n'empeche ni l'ecrasement d'une modification creee ensuite, ni le fichier
# mute laisse en place par une interruption. L'isolation ferme les deux.
RECOPIES = preparer_espace()

print("MUTATIONS — chaque garantie retiree doit rougir son contre-exemple")
print(f"         espace isole: worktree detache sur {_git('rev-parse', '--short', 'HEAD').stdout.strip()}")
if RECOPIES:
    print(f"         + {len(RECOPIES)} fichier(s) non valide(s) recopie(s) depuis l'arbre:")
    for chemin in RECOPIES[:12]:
        print(f"             {chemin}")
    if len(RECOPIES) > 12:
        print(f"             ... et {len(RECOPIES) - 12} autre(s)")
if FILTRE:
    print(f"         (filtre: {' '.join(FILTRE)} — execution PARTIELLE)")
# --------------------------------------------------------------------------
# LA POSTCONDITION D'APPARTENANCE (0013) — trois couches, trois mutations
# --------------------------------------------------------------------------
# CES TROIS GARANTIES ONT ETE AJOUTEES SANS FALSIFICATION, et c'est
# precisement ce que cette matrice existe pour empecher. Une postcondition
# ecrite le meme jour que le controle qui la mesure n'a jamais ete eprouvee
# CONTRE quoi que ce soit: rien ne dit que le vert vienne d'elle.
#
# Chaque couche est retiree SEPAREMENT. Les retirer ensemble dirait « l'une
# des trois porte quelque chose » — ce qui est vrai de n'importe quel triplet
# dont un membre travaille.
# --------------------------------------------------------------------------
# LES POSTCONDITIONS DE MIGRATION — l'appel, les branches, le diagnostic
# --------------------------------------------------------------------------
# CES GARANTIES VIENNENT D'ETRE AJOUTEES, ET C'EST EXACTEMENT LE MOMENT DE LES
# FALSIFIER. Une postcondition ecrite le meme jour que le controle qui la
# mesure n'a jamais ete eprouvee CONTRE quoi que ce soit.
#
# Quatre formes, et elles ne se recouvrent pas:
#   * l'APPEL produit est retire — l'assertion existe encore, et ne sert plus
#     a rien. C'est litteralement l'etat mesure AVANT ce lot;
#   * une BRANCHE de l'assertion est neutralisee — l'appel demeure, mais il ne
#     voit plus ce qu'il regardait;
#   * le DIAGNOSTIC est remplace par un identifiant etranger — le refus a bien
#     lieu, et plus personne ne peut le distinguer d'une panne quelconque;
#   * l'assertion est presente mais JAMAIS ATTEINTE — cas particulier du
#     premier, et le plus difficile a voir a la lecture.
CAS_POSTCONDITIONS_MIGRATION = [
    ("MC1 l'appel produit a la postcondition de 0011 est retire", "Y1", A11,
     [("select assert_authority_surface_hardened();",
       "-- appel retire par mutation")], False),
    ("MC2 l'appel produit a la postcondition de 0012 est retire", "Y2", A12,
     [("select assert_0012_lineage_surface();",
       "-- appel retire par mutation")], False),
    # LES DEUX APPELS DE 0014 ENSEMBLE, et c'est mesure: l'appel local seul
    # retire, l'assertion AGREGEE attrape le meme ecart et la migration echoue
    # toujours. Ne muter que le local mesurerait donc la defense en
    # profondeur, pas l'appel.
    ("MC3 les deux appels produits de 0014 sont retires", "Y3", A14,
     [("""select assert_0014_decisions_surface();
select assert_authority_composition();""",
       "-- appels retires par mutation")], False),
    # LA BRANCHE, ET NON L'APPEL. L'appel demeure; l'assertion ne regarde plus
    # PUBLIC. C'est la forme qui survit a une relecture rapide du diff.
    # MC4 ET AC1 NE VISENT PAS LA MEME DEFAILLANCE, et il a fallu la
    # reecriture du controle PUBLIC pour que la distinction devienne nette:
    #
    #   AC1  la CONDITION n'est plus evaluee — on ne regarde plus;
    #   MC4  la condition est evaluee, et l'ECART N'EST PAS ENREGISTRE — on
    #        regarde, on voit, et on se tait. C'est la forme qui survit le
    #        mieux a une relecture du diff.
    ("MC4 l'ecart PUBLIC EXECUTE de 0014 n'est plus enregistre", "Y5", A14,
     [("""      ecarts := ecarts || format(
        'AUTHORITY_0014_PUBLIC_EXECUTE: PUBLIC detient EXECUTE sur %s '
        '(proacl %s). Verifie par le privilege EFFECTIF, qui couvre le cas '
        'de l''ACL absente', nom,
        case when f_acl is null then 'NULL — droits par defaut, donc =X'
             else 'explicite' end);""",
       "      null;  -- ecart non enregistre par mutation")], False),
    ("MC5 la branche du declencheur desactive ne regarde plus tgenabled", "Y7",
     A14,
     [("""       and not t.tgisinternal and t.tgenabled = 'O')""",
       """       and not t.tgisinternal)""")], False),
    # LE POINT EST « Y9 », ET NON « Y8 » — MESURE. La mutation laisse la
    # branche EXIGER L'EXISTENCE de la policy: le controle « policy absente »
    # (Y8) reste donc rouge de lui-meme, et la mutation a SURVECU au premier
    # passage. Le seul controle qui la tue est « mauvais role » (Y9), ou la
    # policy existe et ou seul le role a change — exactement ce que la
    # mutation cesse de regarder.
    ("MC6 la branche des policies ne compare plus roles ni commande", "Y9", A14,
     [("""       and pol.polname = 'decisions_governance_read'
       and pol.polcmd = 'r' and pol.polpermissive
       and (select array_agg(rr.rolname::text order by rr.rolname) from pg_roles rr
             where rr.oid = any(pol.polroles))
           = array['normative_governance'])""",
       """       and pol.polname = 'decisions_governance_read')""")], False),
    # LE POINT FIXE NOMME de l'assertion agregee. Sans lui, le balayage est
    # defini par la propriete, donc aveugle a une derive de propriete.
    ("MC7 le point fixe nomme de l'agregee est retire", "Y4", A14,
     [("""             'normative_decision_consume', 'check_normative_decision_transition',
             'forbid_decision_delete', 'normative_authenticated_actor',
             'bootstrap_normative_administrator']) as attendue""",
       """             'normative_decision_consume']) as attendue
     where false""")], False),
    # LA REVOCATION DE `CREATE` SUR `public`, RENDUE INEFFICACE.
    #
    # Ce controle porte sur un DEFAUT REEL, mesure dans ce lot: un octroi fait
    # par le proprietaire de la base est enregistre au nom de
    # `pg_database_owner`, et un `REVOKE` emis sous l'identite propre du role
    # ne retire RIEN — sans erreur ni WARNING visible. La correction endosse
    # le donneur avant de revoquer. Retirer cet endossement remet exactement
    # le defaut d'origine, et la postcondition doit le voir.
    # L'ENDOSSEMENT DU DONNEUR EST RETIRE — et cette fois il est TUE.
    #
    # Provenance mesuree, endossement neutralise dans une copie jetable:
    #
    #   apres 0010 : pg_database_owner -> eurostruct_normative_writer
    #   apres 0011 : pg_database_owner -> eurostruct_normative_writer (RESTE)
    #
    # L'octroi est pose SOUS `pg_database_owner`; la revocation emise par un
    # role detenant un `CREATE ... WITH GRANT OPTION` explicite est resolue
    # sous CE role, qui n'a jamais rien accorde. PostgreSQL ne trouve rien a
    # retirer, et ne le dit pas.
    #
    # Le refus est desormais celui de `0011` elle-meme, avec son identifiant,
    # et sans aucune ligne de registre: KILLED_INSTALL_ASSERTION.
    ("GR1 l'endossement du donneur est retire de 0011", "Y1", A11,
     [("""      execute format('set local role %I', donneur);
      execute 'revoke create on schema public from '""",
       """      execute 'revoke create on schema public from '""")], False),

    # L'ACL `NULL` RELUE COMME UNE ABSENCE DE PRIVILEGE.
    #
    # C'est l'erreur que la mesure a rendue impossible a commettre par
    # inadvertance, et qu'il faut donc rendre impossible a commettre tout
    # court. `acldefault('f', owner)` vaut `{=X/owner, owner=X/owner}`:
    # l'entree `=X` EST PUBLIC. Interroger `aclexplode(proacl)` seul rend un
    # ensemble VIDE quand `proacl` est NULL — soit exactement la lecture
    # inverse de la verite.
    ("AC1 le privilege EFFECTIF de PUBLIC n'est plus interroge", "AC1", A14,
     [("""    if has_function_privilege('public', f_oid, 'EXECUTE') then""",
       """    if false then""")], False),
    # LA FONCTION DECLENCHEUR SORTIE DE TOUT CONTROLE PRIVILEGIE. Elle ne
    # s'appelle pas directement; elle s'execute a CHAQUE ECRITURE, avec le
    # search_path de l'ecrivain. L'exempter du controle PUBLIC est mesure et
    # justifie; l'exempter de tout ne l'est pas.
    ("AC3 la fonction declencheur sort du balayage prive", "AC5", A14,
     [("""     where n.nspname = 'public'
       and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer',
                                           'eurostruct_normative_bootstrap',
                                           'eurostruct_normative_activator')
  loop""",
       """     where n.nspname = 'public'
       and p.prorettype <> 'trigger'::regtype
       and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer',
                                           'eurostruct_normative_bootstrap',
                                           'eurostruct_normative_activator')
  loop""")], False),
    # LA BRANCHE QUI CONSTATE LE PRIVILEGE RESTANT, plutot que la commande
    # qui le retire — et il faut dire pourquoi.
    #
    # Le correctif de la revocation (endosser le donneur avant de revoquer)
    # n'est INDISPENSABLE que dans la forme ou l'octroi vient d'un autre role
    # que celui qui applique la migration. Mutee dans `0012` puis dans `0011`,
    # sa neutralisation a SURVECU deux fois: dans les decors disponibles au
    # moment ou ces migrations tournent, la revocation simple aboutit de toute
    # facon. Le correctif est prouve par MESURE — `two_phase_deployment.sh` et
    # `finalisation_contract.sh` etaient rouges, ils sont verts — et NON par
    # une mutation. C'est dit ici plutot que masque par un controle qui
    # viserait a cote.
    #
    # Ce qui EST falsifiable, c'est la branche qui CONSTATE le privilege
    # restant. Sans elle, le privilege revient sans que rien ne l'annonce.
    ("MC9 le CREATE restant sur public n'est plus constate", "Y13", A14,
     [("""    ecarts := ecarts || format(
      'AUTHORITY_COMPOSITION_SCHEMA_CREATE_RETAINED: le role d''autorite '
      '« %s » conserve CREATE sur le schema public (donneur: %s). Il peut y '
      'creer des objets pour toute la vie de la base',
      r.rolname, r.donneurs);""",
       "    null;  -- constat neutralise par mutation")], False),
    # LE DIAGNOSTIC REMPLACE PAR UN IDENTIFIANT ETRANGER. Le refus a bien lieu;
    # le controle ne peut plus le reconnaitre, et un refus qu'on ne reconnait
    # pas ne se distingue pas d'une panne.
    ("MC8 le diagnostic de 0011 devient un identifiant etranger", "Y1", A11,
     [("'AUTHORITY_0011_SURFACE_NOT_HARDENED: surface d''autorite non durcie: %',",
       "'ERREUR_QUELCONQUE: surface d''autorite non durcie: %',")], False),
]

CAS_POSTCONDITION = [
    # H1 lit les LIGNES de `pg_auth_members`. Sans elle, il ne reste que les
    # deux boucles `pg_has_role('USAGE'/'SET')` — et un membre declare-moins
    # avec USAGE y serait vu... mais un membre EN TROP avec USAGE l'est aussi.
    # On neutralise donc la branche qui NOMME le membre supplementaire.
    ("PM1 le membre supplementaire n'est plus nomme", "PC1", A13,
     [("""      ecarts := ecarts || format(
        'membre SUPPLEMENTAIRE « %s » (admin=%s, inherit=%s, set=%s): il '
        'n''est ni declare dans « eurostruct.authority_backend_logins », ni '
        'le residu d''ADMIN que PostgreSQL impose au createur du role',
        r.rolname, r.admin_option, r.inherit_option, r.set_option);""",
       "      null;  -- H1 neutralise par mutation")], False),
    # H2 est la seule couche transitive. Sans elle, un porteur d'ADMIN atteint
    # par une CHAINE ne figure dans aucune ligne directe et passe entierement.
    ("PM2 la chaine d'ADMIN n'est plus suivie", "PC2", A13,
     [("""       and pg_has_role(p.rolname, 'eurostruct_authority_backend',
                       'MEMBER WITH ADMIN OPTION')
       and p.rolname <> all (admins)""",
       "       and false  -- H2 neutralise par mutation")], False),
    # LA BRANCHE D'ADMIN DE H1, isolee elle aussi. Un porteur d'ADMIN en
    # LIGNE DIRECTE, sans INHERIT ni SET, n'est vu ni par les deux boucles
    # `pg_has_role('USAGE'/'SET')` — elles repondent « false » — ni par la
    # couche transitive, puisqu'il n'y a aucune chaine. C'est le chemin exact
    # par lequel la contenance s'etait rouverte.
    ("PM4 l'ADMIN en ligne directe n'est plus confronte au plan", "PC4", A13,
     [("""      if normative_activation_state() = 'ACTIVE'
         and not coalesce(r.membre_oid = normative_control_plane_oid()
                          and r.rolname = normative_control_plane(), false)
      then""",
       """      if false
      then""")], False),
    # H3 est le seul sens « declare mais absent », et il n'est exige qu'en
    # ACTIVE. Le neutraliser ne peut donc rien casser d'autre.
    ("PM3 la declaration decorative n'est plus vue", "PC3", A13,
     [("""  if normative_activation_state() = 'ACTIVE' then
    foreach une_declaration in array declares loop""",
       """  if false then
    foreach une_declaration in array declares loop""")], False),
]

# --------------------------------------------------------------------------
# LES DECLENCHEURS DE 0014 — le socle fige et l'effacement interdit
# --------------------------------------------------------------------------
# MEME RAISON: ils existaient depuis le premier jet de 0014 et n'etaient
# exerces par AUCUN controle jusqu'a ce lot. Les mesurer une fois ne dit pas
# qu'ils portent quelque chose; les retirer et voir rougir, si.
CAS_DECLENCHEURS_0014 = [
    ("DT1 le socle d'une decision n'est plus fige", "X1", A14,
     [("""    raise exception
      'decision %: son objet, sa portee, son proposant, sa source et sa '
      'correlation sont figes a la creation. Seul l''etat progresse.', old.id
      using errcode = 'insufficient_privilege';""",
       "    null;  -- garde du socle retiree par mutation")], False),
    ("DT2 une decision redevient effacable", "X4", A14,
     [("""  raise exception
    'une decision d''autorite ne s''efface pas: elle explique ce qui a ete '
    'engage, et l''effacer effacerait la preuve de la decision.'
    using errcode = 'insufficient_privilege';""",
       "  return old;  -- interdiction d'effacement retiree par mutation")],
     False),
]

# --------------------------------------------------------------------------
# LE MANIFESTE (L3) — quatre garanties, quatre mutations
# --------------------------------------------------------------------------
# CE QUI EST EN JEU. `assert_authority_composition()` balaie `pg_proc` EN
# FILTRANT PAR LE PROPRIETAIRE ATTENDU: une fonction dont le proprietaire
# derive SORT du balayage, et l'assertion devient aveugle a la derive qu'elle
# existe pour detecter. Mesure du 28/08 sur base jetable, en changeant le
# proprietaire de `normative_decision_approve(uuid)`: le manifeste le voit,
# l'agregee ne le voit pas.
#
# Chaque mutation retire UNE des quatre proprietes du manifeste.
CAS_MANIFESTE = [
    # MF3 — le sens realite -> manifeste. Sans lui, une fonction ajoutee au
    # perimetre sans etre declaree passe inapercue: le manifeste ne parle plus
    # que de ce qu'il connait deja.
    ("MF3 le sens realite -> manifeste disparait", "MF3", A15,
     [("""    if r.non_declaree then""",
       """    if false then""")], False),
    # MF2 — la decouverte se remet a filtrer par le proprietaire ATTENDU.
    # C'est le defaut d'origine, reintroduit tel quel.
    ("MF2 la decouverte filtre par le proprietaire attendu", "MF2", A15,
     [("""        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public'
         and (p.proname like 'normative\\_%' or p.proname like 'assert\\_%'""",
       """        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public'
         and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer',
                                             'eurostruct_normative_bootstrap',
                                             'eurostruct_normative_activator')
         and (p.proname like 'normative\\_%' or p.proname like 'assert\\_%'""")], False),
    # MF4 — PUBLIC lu par un role temoin au lieu du grantee 0. Mesure sur
    # PG16: un role ordinaire peut detenir EXECUTE la ou PUBLIC ne l'a pas;
    # le temoin rapporte alors une ouverture qui n'existe pas.
    ("MF4 PUBLIC est lu par un role temoin", "MF4", A15,
     [("""             exists (select 1
                       from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                      where a.grantee = 0 and a.privilege_type = 'EXECUTE')
               as public_acl,""",
       """             has_function_privilege('normative_backend', p.oid, 'EXECUTE')
               as public_acl,""")], False),
    # MF1 — l'assertion ne leve plus. Le manifeste devient un document.
    ("MF1 l'assertion ne refuse plus", "MF1", A15,
     [("""  if array_length(ecarts, 1) > 0 then
    raise exception""",
       """  if false then
    raise exception""")], False),
]


LOTS = [
    (CAS, {}),
    (CAS_MANIFESTE,
     dict(harnais="db/test/authority_sql_hardening.sh", prefixe="mf")),
    (CAS_AUTORITE, dict(harnais="db/test/authority_closure.sh", prefixe="mv")),
    (CAS_SCEAU, dict(harnais="db/test/seal_contract.sh", prefixe="ms")),
    (CAS_RESTAURATION,
     dict(harnais="db/test/cross_cluster_restore.sh", prefixe="mx")),
    (CAS_COMMANDE, dict(harnais="db/test/official_deployment.sh", prefixe="mo")),
    (CAS_REPRISE, dict(harnais="db/test/deploy_recovery.sh", prefixe="mp")),
    (CAS_ACL_SCEAU, dict(harnais="db/test/seal_contract.sh", prefixe="mw")),
    (CAS_BARRIERE,
     dict(harnais="db/test/gate_protocol_selftest.sh", prefixe="mb")),
    (CAS_POSTCONDITION,
     dict(harnais="db/test/authority_role_frontier.sh", prefixe="mr")),
    (CAS_DECLENCHEURS_0014,
     dict(harnais="db/test/authority_four_eyes.sh", prefixe="mq")),
    (CAS_POSTCONDITIONS_MIGRATION,
     dict(harnais="db/test/migration_postconditions.sh", prefixe="mn")),
]

TOTAL = sum(len(cas) for cas, _ in LOTS)

# --------------------------------------------------------------------------
# PRE-VOL — les motifs existent-ils encore, AVANT de lancer quoi que ce soit ?
# --------------------------------------------------------------------------
# Purement textuel, donc immediat. Sans lui, un controle perime se decouvre au
# moment ou son tour arrive: la campagne complete s'est arretee au 45e controle
# sur un motif introuvable, apres plus d'une heure, et les 19 restants n'ont
# jamais ete tentes. Le savoir coute deux secondes; l'ignorer coute la campagne.
#
# IL N'ARRETE RIEN. Il annonce, et laisse la campagne mesurer tout ce qui est
# encore mesurable: un controle perime ne doit pas priver les 63 autres de leur
# verdict.
def _doublons(lots):
    """Les identifiants portes par PLUS D'UN controle, sur la matrice ENTIERE.

    Deux controles portant le meme code rendraient DEUX verdicts sous UN nom.
    Le compte global n'y verrait rien — `defini == tente` tiendrait, puisque
    les deux sont bien tentes — mais le tableau par controle n'afficherait
    qu'une ligne, et c'est la ligne SURVIVANTE qui disparaitrait la moitie du
    temps. Un compte juste sur un tableau faux est pire qu'un compte faux:
    il rassure.

    Le controle porte sur TOUS les codes definis, pas seulement les retenus:
    un doublon hors filtre reste un doublon des que le filtre tombe, et la
    campagne complete n'a pas de filtre.
    """
    vus = {}
    for cas, _ in lots:
        for c in cas:
            vus.setdefault(_code(c[0]), []).append(c[0])
    return [
        f"identifiant EN DOUBLE « {cc} » — {len(noms)} controles le portent: "
        f"{', '.join(n[:40] for n in noms)}. Deux verdicts sous un nom font "
        "disparaitre une ligne du tableau"
        for cc, noms in sorted(vus.items()) if len(noms) > 1
    ]


def _prevol():
    """PROUVE ce qu'il avance, et INVALIDE la campagne avant tout lancement.

    L'ancien pre-vol se contentait de constater qu'un motif etait absent, puis
    laissait la campagne partir en comptant le controle « non execute ». Une
    garantie cessait donc d'etre verifiee sans que rien ne rougisse — c'est
    arrive au controle 7, et personne ne l'a vu pendant un passage complet.

    Sept preuves — six par controle retenu, une sur la matrice entiere:

      1. le fichier cible est lisible;
      2. chaque motif y figure EXACTEMENT une fois — zero est une cible
         disparue, deux est une cible ambigue, et une mutation ambigue ne dit
         pas ce qu'elle a mute;
      3. la mutation est DISTINCTE du candidat: `vieux != neuf`, sinon le
         controle tourne sur le code d'origine et se declare survivant;
      4. le harnais charge de la tuer existe et est executable;
      5. si le controle est declare redondant, son controle COMBINE est
         declare ET retenu dans cette campagne;
      6. si le controle est declare intercepte a l'installation, un diagnostic
         attendu est declare;
      7. aucun identifiant n'est porte par deux controles — sur la matrice
         ENTIERE, filtre ou non.

    Tout manquement est un STALE, et un seul STALE invalide la campagne.
    """
    stale = list(_doublons(LOTS))
    retenus = {_code(c[0]) for cas, _ in LOTS for c in cas if retenu(c)}
    for cas, kw in LOTS:
        for c in cas:
            if not retenu(c):
                continue
            nom, fichier, paires = c[0], c[2], c[3]
            red = len(c) >= 5 and c[4] is True
            cc = _code(nom)
            for f, pr in _cibles(fichier, paires):
                try:
                    src = open(f"{ESPACE}/{f}").read()
                except OSError as e:
                    stale.append(f"{nom} — {f} illisible: {e}")
                    continue
                for vieux, neuf_txt in pr:
                    n = src.count(vieux)
                    if n == 0:
                        stale.append(
                            f"{nom} — cible ABSENTE de {f}: "
                            f"{vieux.strip()[:70]!r}")
                    elif n > 1:
                        stale.append(
                            f"{nom} — cible AMBIGUE dans {f} ({n} occurrences): "
                            f"{vieux.strip()[:70]!r}")
                    if vieux == neuf_txt:
                        stale.append(
                            f"{nom} — mutation IDENTIQUE au candidat dans {f}: "
                            "elle ne muterait rien")
            h = kw.get("harnais", "db/test/finalisation_contract.sh")
            chemin_h = f"{ESPACE}/{h}"
            if not os.path.isfile(chemin_h):
                stale.append(f"{nom} — harnais absent: {h}")
            elif not os.access(chemin_h, os.X_OK):
                stale.append(f"{nom} — harnais non executable: {h}")
            if red:
                comb = COMBINEE.get(cc)
                if not comb:
                    stale.append(
                        f"{nom} — declare REDONDANT sans controle combine "
                        "declare: la redondance ne serait pas prouvee")
                elif comb not in retenus:
                    stale.append(
                        f"{nom} — son controle combine « {comb} » n'est pas "
                        "retenu dans cette campagne")
            if cc in INSTALL_ASSERTION and not INSTALL_ASSERTION[cc].strip():
                stale.append(f"{nom} — diagnostic d'installation vide")
    if stale:
        print()
        print(f"PRE-VOL: {len(stale)} controle(s) ne peuvent PAS etre exerces.")
        print("         La campagne est INVALIDE et n'est pas lancee: une cible")
        print("         absente ou ambigue ne dit rien de la garantie, et un")
        print("         controle qu'on ignore est une garantie qu'on abandonne.")
        for x in stale:
            print(f"           STALE  {x}")
        print()
    return stale


# LA BOUCLE EST APLATIE, ET C'EST CE QUI REND LE DECOMPTE PARTIEL POSSIBLE.
# `ETATS += lot(...)` n'ajoutait qu'a la FIN d'un lot: une interruption au
# milieu du lot de 31 controles jetait les resultats deja obtenus dans ce lot.
# Un controle rendu est un resultat acquis; il doit etre compte des qu'il est
# rendu.
#
# `PLAT` ET `PERIMES_PREVOL` SONT INITIALISES AVANT LA FRONTIERE: le verdict
# les lit, et une interruption survenue avant leur calcul ne doit pas se
# transformer en `NameError` — c'est-a-dire en arret sans verdict, le defaut
# meme qu'on ferme ici.
PLAT = []
PERIMES_PREVOL = []
ETATS = []
INTERRUPTION = None


def _entre_controles():
    """Crochet de test: une fenetre DETERMINISTE entre deux controles.

    Prouver qu'un signal recu entre deux controles produit bien un verdict
    « aucun controle actif » demanderait sinon de viser quelques microsecondes.
    Un test qui reussit une fois sur mille n'etablit rien.

    `ESC_MUTATION_ENTRE_TEMOIN` recoit une ligne des que la fenetre s'ouvre;
    `ESC_MUTATION_PAUSE_ENTRE` dit combien de secondes elle reste ouverte. Hors
    test, les deux sont absentes et cette fonction ne fait rien.
    """
    pause = float(os.environ.get("ESC_MUTATION_PAUSE_ENTRE", "0") or 0)
    if not pause:
        return
    temoin = os.environ.get("ESC_MUTATION_ENTRE_TEMOIN")
    if temoin:
        with open(temoin, "a") as f:
            f.write(f"ENTRE\t{len(ETATS)}\n")
            f.flush()
    time.sleep(pause)


# LA FRONTIERE DE CAPTURE ENTOURE TOUTE LA PHASE DE CAMPAGNE, pas chaque
# `essayer()`. Placee autour du seul appel, elle laissait quatre fenetres par
# lesquelles une `Interruption` s'echappait vers un arret SANS VERDICT:
#
#   - pendant le pre-vol;
#   - apres « ACTIF = None » et avant le `try` suivant;
#   - au retour d'`essayer()`, avant la remise a zero;
#   - dans la construction de la liste elle-meme.
#
# La branche « aucun controle actif » etait donc ECRITE sans qu'aucun chemin ne
# garantisse de l'atteindre. Le gestionnaire de signal se contente d'enregistrer
# et de lever; le verdict et le nettoyage restent produits ici, dans le chemin
# principal.
try:
    PERIMES_PREVOL = _prevol()
    PLAT = [(c, kw) for cas, kw in LOTS for c in cas if retenu(c)]
    # UN SEUL STALE ARRETE TOUT, ET AVANT LE PREMIER LANCEMENT. Laisser partir
    # une campagne dont un controle ne peut pas etre exerce, c'est produire un
    # compte rendu qui additionne des mesures et des absences de mesure.
    # PRE-VOL SEUL. La consigne peut etre « eprouve l'instrument, ne lance pas
    # encore la campagne »: sans ce mode il faudrait lancer 67 harnais pour
    # savoir si les 67 cibles tiennent encore.
    if "--prevol-seulement" in sys.argv:
        nettoyer_espace()
        if PERIMES_PREVOL:
            print(f"PRE-VOL: {len(PERIMES_PREVOL)} controle(s) STALE — "
                  "la campagne serait INVALIDE.")
            sys.exit(2)
        print(f"PRE-VOL: {len(PLAT)} controle(s) retenus, tous exercables.")
        print("         stale 0 | ambiguous 0 | missing_combined_control 0 "
              "| duplicate_id 0")
        print("         Aucun controle n'a ete lance (--prevol-seulement).")
        sys.exit(0)
    if PERIMES_PREVOL:
        nettoyer_espace()
        print(f"MUTATIONS: campagne INVALIDE — {len(PERIMES_PREVOL)} controle(s) "
              f"STALE au pre-vol, aucun controle n'a ete lance.")
        sys.exit(2)
    for _c, _kw in PLAT:
        ACTIF = (_c[0], _c[2])
        ETATS.append(essayer(*_c, **_kw))
        # ENTRE LES DEUX: plus aucun controle n'est en vol. Un signal recu ici
        # ne doit pas inventer un controle interrompu.
        ACTIF = None
        _entre_controles()
except Interruption as _sig:
    INTERRUPTION = _sig

# LE DECOMPTE SEPARE CE QUE LE VERDICT PRECEDENT CONFONDAIT.
#
# « au moins un controle ne porte rien » couvrait DEUX situations qui ne
# demandent pas le meme travail:
#
#   NON EXECUTE  le harnais a refuse de demarrer (codes 2, 3, 4). On ne sait
#                RIEN de la garantie: ni qu'elle porte, ni qu'elle est creuse.
#   CREUX        le harnais a tourne, la garantie a ete retiree, et le
#                contre-exemple est reste VERT. La, on sait: il ne porte rien.
#
# Les confondre, c'est laisser lire « 3 controles en echec » quand la verite
# est « 3 controles n'ont pas ete exerces » — le defaut meme que la matrice
# existe pour rendre impossible ailleurs. Le decompte les nomme donc a part,
# et « non executes » n'est jamais absorbe dans « executes ».
DEFINIS = TOTAL
TENTES = len(ETATS)                       # un statut terminal a ete rendu
KILLED_RT = ETATS.count(KILLED_RUNTIME)
KILLED_IA = ETATS.count(KILLED_INSTALL_ASSERTION)
REDONDANTS = ETATS.count(REDUNDANT_PROVEN)
SURVIVANTS = ETATS.count(SURVIVED)
STALES = ETATS.count(STALE)
INFRAS = ETATS.count(INFRA_FAILURE)
NON_LANCES = DEFINIS - TENTES             # jamais tentes: NOT_RUN

# LES INVARIANTS DE LA CAMPAGNE, ECRITS COMME DES EQUATIONS.
#
# Une campagne acceptable n'a pas « peu » de survivants ou « presque » aucun
# perime: elle en a ZERO, et le total se referme exactement. Ecrire les
# egalites plutot que des seuils rend impossible le compte rendu qui additionne
# des mesures et des absences de mesure.
INV = [
    ("defined == attempted", DEFINIS == TENTES),
    ("defined == killed_runtime + killed_install_assertion + "
     "redundant_proven + survived",
     DEFINIS == KILLED_RT + KILLED_IA + REDONDANTS + SURVIVANTS),
    ("survived == 0", SURVIVANTS == 0),
    ("stale == 0", STALES == 0),
    ("infra_failure == 0", INFRAS == 0),
    ("not_run == 0", NON_LANCES == 0),
]
INV_TENUS = all(ok for _, ok in INV)

# Anciens noms conserves pour le verdict d'interruption, qui les lit.
PERIMES = STALES
NON_EXECUTES = INFRAS + STALES + NON_LANCES
CREUX = SURVIVANTS
TUES = KILLED_RT + KILLED_IA
EXERCES = TENTES
EXECUTES = TENTES - INFRAS - STALES
NON_EXERCES = NON_LANCES

print()
# --------------------------------------------------------------------------
# CAMPAGNE INTERROMPUE — un verdict partiel, jamais un silence
# --------------------------------------------------------------------------
# Le controle en vol n'est ni tue, ni creux, ni refuse par le harnais: il est
# INTERROMPU, et les suivants ne sont pas « non executes » mais NON COMMENCES.
# Les confondre ferait lire un echec de garantie la ou il n'y a qu'une machine
# arretee.
if INTERRUPTION is not None:
    _n = INTERRUPTION.numero
    _nom_sig = signal.Signals(_n).name
    _termines = len(ETATS)
    _interrompu = 1 if ACTIF else 0
    _non_commences = len(PLAT) - _termines - _interrompu
    _ecartes = TOTAL - len(PLAT)
    print(f"MUTATIONS: definis {TOTAL} | termines {_termines} | "
          f"interrompu {_interrompu} | non commences {_non_commences + _ecartes} "
          f"| stale {ETATS.count(STALE)} | survived {ETATS.count(SURVIVED)} "
          f"| code {128 + _n}")
    if ACTIF:
        print(f"           controle actif : {ACTIF[0]}")
        print(f"           fichier mute   : {ACTIF[1]} (restaure)")
    else:
        print("           controle actif : aucun — le signal est arrive entre "
              "deux controles")
    print(f"           signal recu    : {_nom_sig} ({_n})")
    print(f"           SHA teste      : "
          f"{_git('rev-parse', 'HEAD').stdout.strip()}")
    if _ecartes:
        print(f"           dont ecartes par le filtre : {_ecartes}")
    print("           CAMPAGNE INTERROMPUE — ce compte rendu ne vaut PAS pour "
          "la matrice entiere.")
    # LE RETRAIT DU WORKTREE VIENT ICI, ET SEULEMENT ICI: apres la restauration
    # (faite par le `finally` d'`essayer()`) et apres le verdict.
    nettoyer_espace()
    sys.exit(128 + _n)

if FILTRE and EXERCES == 0:
    print(f"MUTATIONS: aucun controle ne correspond a « {' '.join(FILTRE)} ».")
    sys.exit(2)

CODE = 0 if (INV_TENUS and not FILTRE) else 1
print(f"MUTATIONS: defined {DEFINIS} | attempted {TENTES} | "
      f"killed_runtime {KILLED_RT} | killed_install_assertion {KILLED_IA} | "
      f"redundant_proven {REDONDANTS}")
print(f"           survived {SURVIVANTS} | stale {STALES} | "
      f"infra_failure {INFRAS} | not_run {NON_LANCES} | code {CODE}")
print()
print("           INVARIANTS DE CAMPAGNE:")
for _libelle, _ok in INV:
    print(f"             [{'ok' if _ok else 'NON'}] {_libelle}")

if FILTRE:
    print()
    print("           EXECUTION FILTREE: ce compte rendu ne vaut PAS pour la")
    print("           matrice entiere, et ne peut clore aucune campagne.")
elif INV_TENUS:
    print()
    print(f"           Les {DEFINIS} controles portent quelque chose, et le")
    print("           total se referme: aucun survivant, aucun perime, aucune")
    print("           erreur d'infrastructure, aucun controle non lance.")
else:
    print()
    print("           CAMPAGNE NON CONCLUANTE: au moins un invariant est faux.")
    if SURVIVANTS:
        print(f"           {SURVIVANTS} controle(s) SURVIVED: la garantie a ete")
        print("           retiree et rien n'a rougi — ceux-la ne portent rien.")
    if STALES:
        print(f"           {STALES} controle(s) STALE: cible absente ou ambigue.")
        print("           La garantie visee n'est plus verifiee par mutation —")
        print("           le controle doit etre remis en face du code, pas retire.")
    if INFRAS:
        print(f"           {INFRAS} controle(s) INFRA_FAILURE: le harnais n'a pas")
        print("           tourne. Ce n'est pas un echec de garantie, c'est une")
        print("           absence de mesure.")
    if NON_LANCES:
        print(f"           {NON_LANCES} controle(s) NOT_RUN.")
sys.exit(CODE)
