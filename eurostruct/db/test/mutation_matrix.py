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
S = "db/control_plane/0001_normative_seal.sql"
R = "db/test/run.sh"
H = "db/test/authority_closure.sh"
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
                          capture_output=True, text=True, check=check)


DEPOT = _git("rev-parse", "--show-toplevel",
             cwd=RACINE).stdout.strip()          # racine du depot git
SOUS = os.path.relpath(RACINE, DEPOT)            # « eurostruct »
ESPACE_DEPOT = None                              # le worktree temporaire
ESPACE = None                                    # ...et son sous-repertoire
ORIGINAUX = {}                                   # texte d'avant mutation


def nettoyer_espace():
    """Retire le worktree. Idempotent, et sans effet sur le depot principal.

    `git worktree remove` ne touche que le repertoire temporaire et l'entree
    de metadonnees qui le decrit. Si le repertoire a deja disparu — machine
    arretee, `/tmp` vide — il ne reste que cette entree, et `prune` la retire.
    Aucun fichier suivi n'est ecrit dans les deux cas.
    """
    global ESPACE_DEPOT, ESPACE
    if ESPACE_DEPOT is None:
        return
    chemin, ESPACE_DEPOT, ESPACE = ESPACE_DEPOT, None, None
    _git("worktree", "remove", "--force", chemin, check=False)
    shutil.rmtree(chemin, ignore_errors=True)
    _git("worktree", "prune", check=False)


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
    """
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
    if temoin:
        env["ESC_TEMOIN"] = temoin
        enveloppe = (
            'set -u\n'
            '( exec sleep 300 ) >/dev/null 2>&1 </dev/null &\n'
            'TEMOIN=$!\n'
            '"$@" &\n'
            'HARNAIS=$!\n'
            "printf '%s %s %s READY\\n' \"$$\" \"$HARNAIS\" \"$TEMOIN\""
            ' >"$ESC_TEMOIN.tmp"\n'
            'mv -f "$ESC_TEMOIN.tmp" "$ESC_TEMOIN"\n'
            'wait "$HARNAIS"; CODE=$?\n'
            'kill "$TEMOIN" 2>/dev/null; wait "$TEMOIN" 2>/dev/null\n'
            'exit "$CODE"\n'
        )
        argv = ["bash", "-c", enveloppe, "bash", *argv]
    p = subprocess.Popen(argv, cwd=ESPACE, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, start_new_session=True)
    ENFANT = p
    try:
        sortie, erreur = p.communicate()
    finally:
        ENFANT = None
    return p.returncode, sortie + erreur


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
    try:
        muter(fichier, paires)
    except MotifAbsent as motif:
        print(f"  PERIME {nom}\n        -> le texte a muter n'existe plus: {motif}\n"
              "        Le controle ne peut pas etre applique: il ne prouve RIEN "
              "sur la garantie.")
        return "perime"
    # LE `try` COMMENCE DES QUE LE FICHIER EST MUTE. `_tracer()` etait au
    # dehors, et il retient la matrice quand `ESC_MUTATION_PAUSE` est pose: un
    # signal arrive pendant cette pause laissait la mutation en place sans
    # jamais passer par `restaurer()`.
    try:
        _tracer(nom, fichier)
        code, sortie = lancer(harnais, prefixe)
    finally:
        restaurer(fichier)
    # Les points 2 et 8 se subdivisent (« 2a. », « 2b. », « 8b. »): un rouge sur
    # une sous-verification EST un rouge du point. Une expression qui exigeait
    # « 2. » exactement a fait passer pour hollow un controle qui avait
    # parfaitement detecte la mutation.
    # UNE SURFACE NON EXECUTEE N'EST PAS UN VERDICT (6.3b6c).
    #
    # Les codes 2 (refus de garde) et 3 (decor non rendu, verrou detenu)
    # signifient que le harnais N'A PAS TOURNE. La version precedente les
    # comptait comme « aucun rouge » et concluait « le controle ne porte
    # rien » — mesure: lancee sans `EUROSTRUCT_CLUSTER_JETABLE`, la matrice a
    # declare les DIX controles creux alors qu'aucun n'avait ete exerce.
    # LE CODE 4 EST LUI AUSSI UN NON-VERDICT (6.3b6d). Il signifie « surface
    # non executable ici » — pas de second cluster, pas d'ecoute TCP. Absent de
    # cette liste, il tombait dans la branche normale et faisait conclure « le
    # controle ne porte rien »: mesure, les trois mutations de
    # `official_deployment.sh` ont ete declarees creuses alors que le harnais
    # n'avait pas demarre. C'est exactement le defaut que les codes 2 et 3
    # avaient deja produit en 6.3b6c, reintroduit par un code de plus.
    if code in (2, 3, 4):
        print(f"  NON EXECUTE {nom}\n        -> le harnais a refuse (code {code}), "
              f"aucune conclusion possible:")
        for ligne in sortie.splitlines()[:3]:
            if ligne.strip():
                print("        " + ligne.strip()[:120])
        return "non_execute"
    # Les points se subdivisent (« 2a. », « 8b. », « A1. »): un rouge sur une
    # sous-verification EST un rouge du point.
    base = re.match(r"[0-9A-Z]+", point).group(0)
    rougit = re.search(rf"^ *(ROUGE ATTENDU \(a fermer\)|ECHEC): {base}[0-9a-z]?\.",
                       sortie, re.M) is not None
    if redondant:
        if code == 0:
            print(f"  ok    {nom}\n        -> reste vert: la seconde garantie couvre (redondance voulue)")
            return "redondant"
        print(f"  note  {nom}\n        -> rougit (code {code}): la redondance n'en est pas une")
        return "tue"
    if rougit:
        print(f"  ok    {nom}\n        -> le point {point} rougit (code {code})")
        return "tue"
    print(f"  ECHEC {nom}\n        -> le point {point} reste VERT: le controle ne porte rien")
    for ligne in sortie.splitlines():
        if re.match(r"^ *(ok|ROUGE|ECHEC)", ligne):
            print("        " + ligne.strip())
    return "creux"


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
    ("7  l'activator quitte le jeu canonique", "7", R,
     [("""CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment)""",
       """CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment)""")], False),
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
    ("D  l'idempotence ne compare plus le manifeste", "D", S,
     [("    perform normative_exiger_manifeste_approuve(p_manifeste);\n    perform assert_normative_topology();\n    return 'ACTIVE (deja finalise)';",
       "    perform assert_normative_topology();\n    return 'ACTIVE (deja finalise)';")], False),
    ("E  une exemption de service redevient nominale", "E", S,
     [("""         p.oid = normative_control_plane_oid()
         and p.rolname = normative_control_plane()""",
       """         p.rolname = normative_control_plane()""")], False),
    ("G  le diagnostic de restauration disparait", "G", S,
     [("-- RESTAURATION INTER-CLUSTER — le cas le plus probable de ce refus.",
       "-- Transport de base — le cas le plus probable de ce refus."),
      ("CAS COURANT: RESTAURATION INTER-CLUSTER", "CAS COURANT: transport de base")], False),
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
LOTS = [
    (CAS, {}),
    (CAS_AUTORITE, dict(harnais="db/test/authority_closure.sh", prefixe="mv")),
    (CAS_SCEAU, dict(harnais="db/test/seal_contract.sh", prefixe="ms")),
    (CAS_RESTAURATION,
     dict(harnais="db/test/cross_cluster_restore.sh", prefixe="mx")),
    (CAS_COMMANDE, dict(harnais="db/test/official_deployment.sh", prefixe="mo")),
    (CAS_REPRISE, dict(harnais="db/test/deploy_recovery.sh", prefixe="mp")),
    (CAS_ACL_SCEAU, dict(harnais="db/test/seal_contract.sh", prefixe="mw")),
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
def _prevol():
    perimes = []
    for cas, _ in LOTS:
        for c in cas:
            if not retenu(c):
                continue
            nom, fichier, paires = c[0], c[2], c[3]
            try:
                src = open(f"{ESPACE}/{fichier}").read()
            except OSError as e:
                perimes.append(f"{nom} — {fichier} illisible: {e}")
                continue
            for vieux, _n in paires:
                if vieux not in src:
                    perimes.append(f"{nom} — {fichier}: {vieux.strip()[:70]!r}")
    if perimes:
        print()
        print(f"PRE-VOL: {len(perimes)} controle(s) visent un texte qui n'existe "
              "plus.")
        print("         Ils seront comptes NON EXECUTES, jamais tues:")
        for p in perimes:
            print(f"           {p}")
        print()
    return perimes


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
PERIMES = ETATS.count("perime")
NON_EXECUTES = ETATS.count("non_execute") + PERIMES
CREUX = ETATS.count("creux")
REDONDANTS = ETATS.count("redondant")
TUES = ETATS.count("tue")
EXERCES = len(ETATS)                      # retenus par le filtre
EXECUTES = EXERCES - NON_EXECUTES         # qui ont rendu un verdict
NON_EXERCES = DEFINIS - EXERCES           # ecartes par le filtre

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
          f"| perimes {ETATS.count('perime')} | creux {ETATS.count('creux')} "
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

CODE = 1 if (CREUX or NON_EXECUTES) else 0
print(f"MUTATIONS: definis {DEFINIS} | executes {EXECUTES} | "
      f"non executes {NON_EXECUTES + NON_EXERCES} | echecs inexpliques {CREUX} "
      f"| code {CODE}")
print(f"           dont tues {TUES}, redondants voulus {REDONDANTS}"
      + (f", ecartes par le filtre {NON_EXERCES}" if NON_EXERCES else "")
      + (f", refuses par le harnais {NON_EXECUTES - PERIMES}"
         if NON_EXECUTES - PERIMES else "")
      + (f", PERIMES {PERIMES}" if PERIMES else ""))

if PERIMES:
    print(f"           {PERIMES} controle(s) PERIMES: le texte a muter n'existe "
          "plus.\n           La garantie visee n'est plus verifiee par mutation — "
          "le controle\n           doit etre remis en face du code, pas retire.")
if NON_EXECUTES - PERIMES:
    print(f"           {NON_EXECUTES - PERIMES} controle(s) N'ONT PAS ETE EXERCES: "
          "le harnais a refuse.\n           Ce n'est pas un echec de garantie — "
          "c'est une absence de mesure.")
if CREUX:
    print(f"           {CREUX} controle(s) ont tourne SANS rougir: ceux-la ne "
          "portent rien.")
if NON_EXERCES:
    # UNE EXECUTION FILTREE NE REND PAS LE VERDICT COMPLET. Elle dit ce qu'elle
    # a exerce, et combien elle a laisse de cote.
    print(f"           execution PARTIELLE (filtre): {NON_EXERCES} controle(s) "
          "non exerces.\n           Ce compte rendu ne vaut PAS pour la matrice "
          "entiere.")
elif CODE == 0:
    print(f"           les {DEFINIS} controles portent quelque chose.")
sys.exit(CODE)
