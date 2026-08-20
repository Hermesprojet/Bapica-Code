#!/usr/bin/env bash
#
# EUROSTRUCT — LA MATRICE DOIT MOURIR PROPREMENT
#
#   mutation_signal_selftest.sh
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `mutation_matrix.py` est l'INSTRUMENT qui fournit la preuve de cloture d'un
# jalon. Un defaut connu dans l'instrument rend sa preuve irrecevable — quelle
# que soit la qualite de ce qu'il mesure.
#
# LE DEFAUT D'ORIGINE, MESURE ET NON SUPPOSE. Le gestionnaire de signal appelait
# `nettoyer_espace()` en PREMIER: `ESPACE` passait a `None` et le worktree
# disparaissait, PUIS la levee declenchait le `finally: restaurer(fichier)`
# d'`essayer()`, qui ecrivait dans « None/tools/deploy_eurostruct.sh ».
# Constate deux fois sur 6075b1b — une fois subi quand le conteneur s'est
# arrete au 43e controle sur 64, une fois provoque deliberement:
#
#     SystemExit: 143
#     ...
#     FileNotFoundError: [Errno 2] No such file or directory:
#       'None/tools/deploy_eurostruct.sh'
#
# Trois consequences, et la deuxieme est la pire: un traceback la ou on attend
# un compte rendu; AUCUN verdict, donc 42 controles rendus nulle part comptes;
# et un code de sortie ramene a 1 par l'exception non rattrapee, rendant un
# arret par signal indiscernable d'un echec de garantie.
#
# QUATRE SCENARIOS
# -----------------
#   A. SIGNAL PENDANT UN HARNAIS QUI A UNE DESCENDANCE. C'est la fenetre ou
#      `finally: restaurer()` s'execute — la seule qui exerce le defaut
#      d'origine. Elle etablit aussi que TOUTE LA DESCENDANCE meurt: terminer
#      le seul Bash laissait vivre `psql`, sous-shells et clusters temporaires.
#   B. SIGNAL ENTRE DEUX CONTROLES, quand plus rien n'est en vol. La frontiere
#      de capture n'entourait que l'appel a `essayer()`; une `Interruption`
#      levee ailleurs s'echappait vers un arret SANS VERDICT.
#   C. FUITE INJECTEE. Une comparaison qui n'a jamais vu de difference ne
#      prouve rien. On pose un verrou advisory supplementaire bien reel et on
#      exige que la comparaison le voie — puis qu'elle revienne a l'egalite.
#   D. OBSERVATION IMPOSSIBLE. Une lecture de `pg_locks` en echec ne doit
#      JAMAIS passer pour « fuite detectee » ni pour « aucun verrou ».
#
# SIGKILL N'EST PAS COUVERT, ET NE PEUT PAS L'ETRE: il n'est pas interceptable.
# Aucun verdict ne peut etre exige apres un SIGKILL. Ce que
# `mutation_isolation_selftest.sh` continue d'etablir dans ce cas, c'est que le
# DEPOT PRINCIPAL n'est pas modifie.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(dirname "$(dirname "$HERE")")"          # « .../eurostruct »
# LA RACINE EST DEMANDEE A GIT, PAS COMPTEE EN `dirname`. Un `dirname` de trop
# ou de moins donne un chemin plausible qui ne designe rien — mesure: la
# premiere version cherchait la matrice dans « eurostruct/db/db/test ».
RACINE="$(git -C "$PROJET" rev-parse --show-toplevel)"
MATRICE="$PROJET/db/test/mutation_matrix.py"

KO=0
ok()     { echo "      ok: $*"; }
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }

echo "    la matrice meurt proprement sur signal"
[[ -f "$MATRICE" ]] || { echoue "matrice introuvable: $MATRICE"; exit 2; }

# UN JETON PAR EXECUTION. Il nomme les connexions de ce test et lui seul: sans
# lui, deux executions concurrentes — ou une session tierce quelconque — ne
# seraient pas distinguables des siennes.
JETON="$$-${RANDOM}${RANDOM}"
TRACE=""; SORTIE=""; TEMOIN=""; TEMOIN_DESC=""; ESPACE_DEPOT=""; MPID=""
FUITE_CLIENT=""; FUITE_BACKEND=""; TIERS_CLIENT=""; TIERS_BACKEND=""
CLE1=0; CLE2=0; APP_FUITE=""; APP_TIERS=""

# ==========================================================================
# LECTURES SQL — FAIL-CLOSED, TOUJOURS
# ==========================================================================
# UNE LECTURE QUI ECHOUE N'EST PAS UN ENSEMBLE VIDE. Les substitutions de
# commande de la forme « $(psql ... 2>/dev/null) » rendent la chaine vide aussi
# bien quand il n'y a rien a voir que quand on n'a rien pu voir — et le script
# ne tourne pas sous `set -e`. Le test annoncait alors « aucun residu » sans
# avoir rien observe.
lire_sql() {
  local sortie code
  # PRISE DE TEST: rend toute lecture impossible. Elle sert au scenario F, qui
  # exerce un nettoyage EN ECHEC — un chemin qu'aucun test ne pouvait atteindre
  # autrement, et qui doit changer le verdict au lieu d'etre avale.
  if [[ -n "${ESC_SQL_ILLISIBLE:-}" ]]; then
    printf 'ILLISIBLE\t%s\n' "lecture rendue impossible (prise de test)"
    return 1
  fi
  sortie="$(psql -X -qtA -v ON_ERROR_STOP=1 -d postgres -c "$1" 2>&1)"
  code=$?
  if (( code != 0 )); then
    printf 'ILLISIBLE\t%s\n' "$(grep -m1 . <<<"$sortie")"
    return 1
  fi
  printf '%s\n' "$sortie"
  return 0
}

# L'empreinte ordonnee des verrous advisory. `ESC_VERROUS_ILLISIBLE` force une
# connexion injoignable: c'est la prise qui permet au scenario D d'exercer le
# chemin « observation impossible » sans casser quoi que ce soit.
empreinte_verrous() {
  local sortie code
  local req="select coalesce(database::text,'-')||'|'||pid||'|'||coalesce(classid::text,'-')
        ||'|'||coalesce(objid::text,'-')||'|'||coalesce(objsubid::text,'-')
        ||'|'||mode||'|'||granted
      from pg_locks where locktype='advisory' order by 1"
  if [[ -n "${ESC_VERROUS_ILLISIBLE:-}" ]]; then
    sortie="$(PGHOST=/var/empty-esc PGPORT=1 PGCONNECT_TIMEOUT=2 \
              psql -X -qtA -v ON_ERROR_STOP=1 -d postgres -c "$req" 2>&1)"
    code=$?
  else
    sortie="$(psql -X -qtA -v ON_ERROR_STOP=1 -d postgres -c "$req" 2>&1)"
    code=$?
  fi
  if (( code != 0 )); then
    printf 'ILLISIBLE\t%s\n' "$(grep -m1 . <<<"$sortie")"
    return 1
  fi
  printf '%s\n' "$sortie"
  return 0
}

# LES RESULTATS SONT TYPES, ET C'EST INDISPENSABLE. Rendre « 1 » aussi bien
# pour « verrou supplementaire » que pour « lecture impossible » laissait le
# scenario C lire une PANNE DE CONNEXION comme une fuite correctement detectee,
# et annoncer « ok: la comparaison rougit sur le verrou supplementaire » alors
# qu'aucun verrou n'avait ete observe.
#
#    0  ensembles identiques
#   10  verrou supplementaire
#   11  verrou initial disparu
#   12  les deux
#   20  etat AVANT illisible
#   21  etat APRES illisible
CMP_APPARUS=""; CMP_DISPARUS=""; CMP_DIAG=""
comparer_verrous() {   # comparer_verrous <scenario> <empreinte-avant> [muet]
  local quoi="$1" avant="$2" muet="${3:-}" apres n=0
  CMP_APPARUS=""; CMP_DISPARUS=""; CMP_DIAG=""
  if [[ "$avant" == ILLISIBLE* ]]; then
    CMP_DIAG="${avant#*$'\t'}"
    [[ -z "$muet" ]] && { echoue "$quoi: etat des verrous AVANT illisible — $CMP_DIAG"
                          detail "une lecture impossible n'est pas « aucun verrou »"; }
    return 20
  fi
  # Convergence bornee: la fermeture d'un backend est asynchrone, un verrou de
  # session tombe quelques instants apres la mort de sa connexion. Une VRAIE
  # fuite, elle, ne converge jamais.
  while :; do
    apres="$(empreinte_verrous)"
    if [[ "$apres" == ILLISIBLE* ]]; then
      CMP_DIAG="${apres#*$'\t'}"
      [[ -z "$muet" ]] && { echoue "$quoi: etat des verrous APRES illisible — $CMP_DIAG"
                            detail "une lecture impossible n'est pas « aucun verrou »"; }
      return 21
    fi
    [[ "$apres" == "$avant" ]] && break
    (( n++ >= 150 )) && break
    sleep 0.1
  done
  if [[ "$apres" == "$avant" ]]; then
    local combien; combien="$(grep -c . <<<"$avant")"; [[ -z "$avant" ]] && combien=0
    [[ -z "$muet" ]] && { ok "$quoi: les verrous advisory sont exactement ceux d'avant ($combien detenu(s))"
                          (( n > 0 )) && detail "convergence en $((n / 10)) s"; }
    return 0
  fi
  CMP_APPARUS="$(comm -13 <(sort <<<"$avant") <(sort <<<"$apres"))"
  CMP_DISPARUS="$(comm -23 <(sort <<<"$avant") <(sort <<<"$apres"))"
  local code=0
  [[ -n "$CMP_APPARUS"  ]] && code=$((code + 10))
  [[ -n "$CMP_DISPARUS" ]] && code=$((code + 1))
  (( code == 11 )) && code=11
  (( code == 10 + 1 )) && code=12
  if [[ -z "$muet" ]]; then
    [[ -n "$CMP_APPARUS" ]] && { echoue "$quoi: verrou advisory SUPPLEMENTAIRE"
                                 detail "apparu(s): $(tr '\n' ' ' <<<"$CMP_APPARUS")"; }
    [[ -n "$CMP_DISPARUS" ]] && { echoue "$quoi: verrou advisory INITIAL DISPARU"
                                  detail "disparu(s): $(tr '\n' ' ' <<<"$CMP_DISPARUS")"
                                  detail "le scenario a libere un verrou qui ne lui appartenait pas"; }
  fi
  return $code
}

# ==========================================================================
# NETTOYAGE — LE BACKEND, PAS SEULEMENT LE CLIENT
# ==========================================================================
# Tuer le `psql` client ne libere PAS le verrou: le backend, bloque dans
# `pg_sleep`, ne remarque la disparition de son client qu'en tentant de lui
# repondre, donc a la fin de la requete. Mesure faite — la comparaison de
# retour rougissait a tort.
#
# ON NE TERMINE QUE DES PID DONT LA PROPRIETE A ETE ETABLIE. Jamais un ensemble
# choisi par des cles: une collision, une execution concurrente ou une session
# tierce portant les memes cles serait terminee avec lui.
# UN PID N'EST PAS UNE AUTORITE. Il est reutilisable, et le noyau le reattribue
# librement des qu'un processus meurt. Verifier la propriete PUIS terminer en
# deux operations laisse une fenetre — etroite, mais reelle — ou le PID prouve
# n'est plus celui qu'on termine. Une fonction qui pretend « ne terminer que ce
# qu'elle possede » ne peut pas s'accommoder de cette fenetre.
#
# `pid_valide` refuse tout ce qui n'est pas une suite de chiffres AVANT toute
# interpolation SQL.
pid_valide() { [[ "$1" =~ ^[0-9]+$ ]]; }

# L'IDENTITE COMPLETE, ET NON LA SEULE PRESENCE D'UNE CONNEXION.
# `pg_stat_activity` peut montrer la session AVANT qu'elle ait acquis son
# verrou: annoncer « session tierce sur les MEMES cles » sur cette base
# affirmait une propriete non observee.
#
#   0  identite et verrou exacts, accorde
#   1  aucune ligne ne correspond
#   3  lecture impossible
detient_verrou() {   # detient_verrou <pid> <app> <cle1> <cle2> <mode>
  local pid="$1" app="$2" c1="$3" c2="$4" mode="$5" n
  pid_valide "$pid" || return 1
  n="$(lire_sql "select count(*) from pg_locks l
                   join pg_stat_activity a on a.pid = l.pid
                  where l.pid = $pid
                    and a.application_name = '$app'
                    and a.datname = current_database()
                    and l.locktype = 'advisory'
                    and l.classid = $c1 and l.objid = $c2 and l.objsubid = 2
                    and l.granted and l.mode = '$mode'
                    and l.database = (select oid from pg_database
                                       where datname = current_database())")"
  [[ "$n" == ILLISIBLE* ]] && { CMP_DIAG="${n#*$'\t'}"; return 3; }
  [[ "$n" == "1" ]] && return 0
  return 1
}

# TERMINAISON CONDITIONNELLE, FILTREE DANS LA MEME REQUETE. `pg_terminate_backend`
# n'est appele que si le catalogue contient ENCORE cette identite exacte et ce
# verrou exact, accorde. Il n'y a plus de fenetre entre la preuve et l'acte.
#
#   0  identite exacte, terminaison acceptee
#   1  backend deja disparu: le nettoyage est deja satisfait
#   2  backend present mais identite NON concordante: refus de tuer
#   3  lecture impossible ou terminaison rendue « false »: fail-closed
terminer_possede() {   # terminer_possede <pid> <app> <cle1> <cle2> <mode> <libelle>
  local pid="$1" app="$2" c1="$3" c2="$4" mode="$5" quoi="$6" n=0 vu res
  [[ -z "$pid" ]] && return 1
  if ! pid_valide "$pid"; then
    echoue "$quoi: PID non numerique refuse avant interpolation SQL: « $pid »"
    return 3
  fi
  vu="$(lire_sql "select count(*) from pg_stat_activity where pid = $pid")"
  [[ "$vu" == ILLISIBLE* ]] && { echoue "$quoi: pg_stat_activity illisible — ${vu#*$'\t'}"
                                 return 3; }
  [[ "$vu" == "0" ]] && return 1
  res="$(lire_sql "select coalesce((
             select pg_terminate_backend(l.pid)::text
               from pg_locks l join pg_stat_activity a on a.pid = l.pid
              where l.pid = $pid
                and a.application_name = '$app'
                and a.datname = current_database()
                and l.locktype = 'advisory'
                and l.classid = $c1 and l.objid = $c2 and l.objsubid = 2
                and l.granted and l.mode = '$mode'
                and l.database = (select oid from pg_database
                                   where datname = current_database())
             ), 'AUCUNE')")"
  [[ "$res" == ILLISIBLE* ]] && { echoue "$quoi: terminaison illisible — ${res#*$'\t'}"
                                  return 3; }
  [[ "$res" == "AUCUNE" ]] && return 2
  [[ "$res" != "true" ]] && { echoue "$quoi: pg_terminate_backend a rendu « $res »"
                              return 3; }
  while (( n++ < 150 )); do
    vu="$(lire_sql "select count(*) from pg_stat_activity where pid = $pid")"
    [[ "$vu" == ILLISIBLE* ]] && { echoue "$quoi: attente illisible — ${vu#*$'\t'}"
                                   return 3; }
    [[ "$vu" == "0" ]] && return 0
    sleep 0.1
  done
  echoue "$quoi: le backend $pid n'a pas disparu apres terminaison"
  return 3
}

NETTOYAGE_KO=0
nettoyage_echoue() { echo "      ECHEC (nettoyage): $*" >&2; NETTOYAGE_KO=1; }

menage() {
  if [[ -n "$MPID" ]] && kill -0 "$MPID" 2>/dev/null; then
    kill -TERM "$MPID" 2>/dev/null
    for _ in $(seq 1 100); do kill -0 "$MPID" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$MPID" 2>/dev/null
  fi
  # LES BACKENDS D'ABORD — y compris si un signal arrive entre l'acquisition du
  # verrou et le nettoyage normal. LA MEME FONCTION REVALIDEE, jamais le PID
  # seul, et SANS `>/dev/null`: un nettoyage dont on jette le diagnostic n'est
  # pas un nettoyage verifie.
  local rc
  if [[ -n "$FUITE_BACKEND" ]]; then
    terminer_possede "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock "menage (fuite)"
    rc=$?; (( rc == 2 || rc == 3 )) \
      && nettoyage_echoue "backend de C ($FUITE_BACKEND) non nettoye (code $rc)"
  fi
  if [[ -n "$TIERS_BACKEND" ]]; then
    terminer_possede "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock "menage (tiers)"
    rc=$?; (( rc == 2 || rc == 3 )) \
      && nettoyage_echoue "backend tiers ($TIERS_BACKEND) non nettoye (code $rc)"
  fi
  # AUCUN VERROU DES DEUX JETONS NE DOIT SUBSISTER.
  if (( CLE1 != 0 )); then
    local reste
    reste="$(lire_sql "select count(*) from pg_locks
                        where locktype='advisory' and classid=$CLE1 and objid=$CLE2")"
    if [[ "$reste" == ILLISIBLE* ]]; then
      nettoyage_echoue "verrous des scenarios: lecture impossible — ${reste#*$'"'"'\t'"'"'}"
    elif [[ "$reste" != "0" ]]; then
      nettoyage_echoue "$reste verrou(s) des cles ($CLE1,$CLE2) subsistent"
    fi
  fi
  for c in "$FUITE_CLIENT" "$TIERS_CLIENT"; do
    [[ -n "$c" ]] && { kill "$c" 2>/dev/null; wait "$c" 2>/dev/null; }
  done
  if [[ -n "$ESPACE_DEPOT" && -d "$ESPACE_DEPOT" ]]; then
    git -C "$RACINE" worktree remove --force "$ESPACE_DEPOT" 2>/dev/null
    rm -rf "$ESPACE_DEPOT"
    git -C "$RACINE" worktree prune 2>/dev/null
  fi
  rm -f "$TRACE" "$SORTIE" "$TEMOIN" "$TEMOIN_DESC"
}
# LE NETTOYAGE PEUT CHANGER LE VERDICT, et il ne le pouvait pas.
# `menage()` tournait dans un `trap EXIT` declenche par `exit $KO`: le code
# etait DEJA fige, et modifier `KO` ensuite n'avait aucun effet. Un nettoyage
# rouge passait donc inapercu. On capture le code, on desarme le trap, on
# nettoie, et on substitue un code dedie (9) si le nettoyage a echoue.
sortir() {
  local code="${1:-$KO}"
  trap - EXIT TERM INT
  menage
  if (( NETTOYAGE_KO )); then
    echo "    NETTOYAGE ROUGE — le verdict est remplace." >&2
    (( code == 0 )) && code=9
  fi
  exit "$code"
}
trap 'sortir $KO' EXIT
# Un signal doit passer par le meme chemin: sans trap TERM, bash meurt sans
# executer le trap EXIT, et rien n'est nettoye.
trap 'sortir 143' TERM INT

# ==========================================================================
# PROCESSUS
# ==========================================================================
# `descendants` REMONTE TOUT L'ARBRE, pas seulement le premier niveau. Le test
# concluait « aucun enfant ne survit » en n'ayant regarde que l'enfant DIRECT
# de la matrice — c'est-a-dire le Bash du harnais, jamais ce qu'il engendre.
descendants() {
  local p
  for p in $(pgrep -P "$1" 2>/dev/null); do echo "$p"; descendants "$p"; done
}

vivants() {   # vivants <liste de PID> -> ceux qui TOURNENT encore
  # UN ZOMBIE N'EST PAS UN SURVIVANT, et c'est ce qui a rendu la CI rouge.
  # Le processus est MORT: il ne detient plus rien et n'execute plus rien.
  # Mais `kill -0` REUSSIT sur un zombie, et `ps -g` le liste. Mesure, 4 fois
  # sur 4 en TCP: « le groupe contient encore des processus » alors qu'il ne
  # restait que « [bash] <defunct> » et « [psql] <defunct> ».
  local p etat restants=""
  for p in $1; do
    etat="$(ps -o stat= -p "$p" 2>/dev/null | tr -d ' ')"
    [[ -n "$etat" && "$etat" != Z* ]] && restants="$restants $p"
  done
  echo "${restants# }"
}

groupe_vivant() {
  ps -o pid=,stat= -g "$1" 2>/dev/null | awk '$2 !~ /^Z/ {print $1}' | tr '\n' ' '
}

attendre() {   # attendre <description> <commande-test> <deciseconds>
  local quoi="$1" test="$2" max="$3" n=0
  while ! eval "$test"; do
    kill -0 "$MPID" 2>/dev/null || { echoue "la matrice est morte avant: $quoi"
                                     detail "$(head -3 "$SORTIE")"; return 1; }
    sleep 0.1; n=$((n + 1))
    if (( n >= max )); then echoue "delai depasse en attendant: $quoi"; return 1; fi
  done
  # LE `return 0` EXPLICITE N'EST PAS DECORATIF. Une boucle `while` rend le
  # statut de la DERNIERE commande de son corps: avec « (( n >= max )) && ... »
  # en derniere position, l'attente REUSSIE rendait 1, et le test s'arretait
  # sans message sur une condition satisfaite.
  return 0
}

lancer_matrice() {   # lancer_matrice <filtre> [VAR=val ...]
  local filtre="$1"; shift
  TRACE="$(mktemp)"; SORTIE="$(mktemp)"
  (
    cd "$PROJET" || exit 2
    export ESC_MUTATION_TRACE="$TRACE"
    export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
    for kv in "$@"; do export "${kv?}"; done
    exec python3 "$MATRICE" "$filtre"
  ) >"$SORTIE" 2>&1 &
  MPID=$!
}

# ==========================================================================
# SOUS-MODE — CREER C ET LE TIERS, PUIS ATTENDRE LE SIGNAL
# ==========================================================================
# Le scenario E se relance lui-meme dans ce mode. Le sous-mode pose les deux
# verrous, ECRIT TOUT CE QU'IL A CREE dans son temoin, annonce READY, puis
# dort. Le parent le signale a cet instant precis: c'est la seule facon
# d'exercer reellement « un signal arrive entre l'acquisition du verrou et le
# nettoyage », au lieu de l'affirmer.
if [[ "${ESC_SIGNAL_SOUS_MODE:-}" == "interruption_c" ]]; then
  CLE1="${ESC_SIGNAL_CLE1:?}"; CLE2="${ESC_SIGNAL_CLE2:?}"
  APP_FUITE="esc-fuite-$JETON"; APP_TIERS="esc-tiers-$JETON"
  PGAPPNAME="$APP_FUITE" psql -X -qtA -d postgres -c \
    "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(300);" >/dev/null 2>&1 &
  FUITE_CLIENT=$!
  PGAPPNAME="$APP_TIERS" psql -X -qtA -d postgres -c \
    "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(300);" >/dev/null 2>&1 &
  TIERS_CLIENT=$!
  for _ in $(seq 1 600); do
    FUITE_BACKEND="$(lire_sql "select pid from pg_stat_activity
                                where application_name = '$APP_FUITE'" | head -1)"
    TIERS_BACKEND="$(lire_sql "select pid from pg_stat_activity
                                where application_name = '$APP_TIERS'" | head -1)"
    if pid_valide "${FUITE_BACKEND:-x}" && pid_valide "${TIERS_BACKEND:-x}" \
       && detient_verrou "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock \
       && detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock; then
      break
    fi
    sleep 0.1
  done
  {
    echo "FUITE_BACKEND=$FUITE_BACKEND"
    echo "TIERS_BACKEND=$TIERS_BACKEND"
    echo "FUITE_CLIENT=$FUITE_CLIENT"
    echo "TIERS_CLIENT=$TIERS_CLIENT"
    echo "APP_FUITE=$APP_FUITE"
    echo "APP_TIERS=$APP_TIERS"
    echo "CLE1=$CLE1"; echo "CLE2=$CLE2"
    echo "READY"
  } >"${ESC_SIGNAL_TEMOIN:?}"
  sleep 300
  sortir 0
fi

# SOUS-MODE — LE NETTOYAGE ECHOUE, ET LE CODE DOIT LE DIRE
if [[ "${ESC_SIGNAL_SOUS_MODE:-}" == "nettoyage_casse" ]]; then
  CLE1="${ESC_SIGNAL_CLE1:?}"; CLE2="${ESC_SIGNAL_CLE2:?}"
  APP_FUITE="esc-fuite-$JETON"
  PGAPPNAME="$APP_FUITE" psql -X -qtA -d postgres -c \
    "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(300);" >/dev/null 2>&1 &
  FUITE_CLIENT=$!
  for _ in $(seq 1 600); do
    FUITE_BACKEND="$(lire_sql "select pid from pg_stat_activity
                                where application_name = '$APP_FUITE'" | head -1)"
    pid_valide "${FUITE_BACKEND:-x}" \
      && detient_verrou "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock && break
    sleep 0.1
  done
  { echo "FUITE_BACKEND=$FUITE_BACKEND"; echo "APP_FUITE=$APP_FUITE"; echo "READY"; } \
    >"${ESC_SIGNAL_TEMOIN:?}"
  # A partir d'ici le nettoyage ne pourra RIEN lire. Il doit rougir, et le code
  # de sortie doit passer de 0 a 9 — jamais rester 0.
  export ESC_SQL_ILLISIBLE=1
  sortir 0
fi

# ==========================================================================
# A. SIGNAL PENDANT UN HARNAIS QUI A UNE DESCENDANCE
# ==========================================================================
echo "      -- A. pendant un harnais, avec sa descendance"
# L'ETAT DES VERROUS EST RELEVE AVANT, ET IL N'EST PAS SUPPOSE VIDE. Lance
# seul, ce test le trouvera vide; lance par `run.sh`, il y trouvera le verrou
# de session du parent. Les deux configurations sont legitimes, et c'est
# l'EGALITE avec cet etat de depart qui est exigee, pas sa valeur.
VERROUS_AVANT_A="$(empreinte_verrous)"
if [[ "$VERROUS_AVANT_A" == ILLISIBLE* ]]; then
  echoue "impossible de lire pg_locks au demarrage — ${VERROUS_AVANT_A#*$'\t'}"
  exit 1
fi
NB_AVANT="$(grep -c . <<<"$VERROUS_AVANT_A")"; [[ -z "$VERROUS_AVANT_A" ]] && NB_AVANT=0
if (( NB_AVANT == 0 )); then
  ok "configuration AUTONOME: aucun verrou advisory au depart"
else
  ok "configuration IMBRIQUEE: $NB_AVANT verrou(s) advisory detenu(s) par l'appelant"
  detail "$(tr '\n' ' ' <<<"$VERROUS_AVANT_A")"
fi

TEMOIN_DESC="$(mktemp)"
lancer_matrice W1 "ESC_MUTATION_TEMOIN=$TEMOIN_DESC"
attendre "la mutation posee" '[[ -s "$TRACE" ]]' 3000 || exit 1
IFS=$'\t' read -r CAS_NOM CAS_FIC CAS_SOMME _ESPACE ESPACE_DEPOT <"$TRACE"
ok "mutation posee: $CAS_NOM sur $CAS_FIC"

AVANT="$(sha256sum "$PROJET/$CAS_FIC" | cut -d' ' -f1)"
[[ "$AVANT" != "$CAS_SOMME" ]] \
  && ok "le depot principal differe deja de la version mutee (attendu)" \
  || echoue "le depot principal porte l'empreinte MUTEE: l'isolation a cede"

attendre "le harnais lance par la matrice" \
         '[[ -n "$(pgrep -P "$MPID" 2>/dev/null)" ]]' 3000 || exit 1
BASH_PID="$(pgrep -P "$MPID" 2>/dev/null | head -1)"
CMDLINE="$(ps -o args= -p "$BASH_PID" 2>/dev/null)"
HARNAIS_NOM="$(awk '{print $2}' <<<"$CMDLINE")"
HARNAIS_PREFIXE="$(awk '{print $3}' <<<"$CMDLINE")"
ok "harnais « $HARNAIS_NOM $HARNAIS_PREFIXE » (PID $BASH_PID)"

# LA VERIFICATION STRUCTURELLE, ET C'EST ELLE QUI PORTE. Le harnais doit MENER
# SON PROPRE GROUPE: sans cela, « terminer tout ce que ce harnais a engendre »
# ne peut meme pas s'exprimer — on ne saurait pas quoi viser.
PGID_HARNAIS="$(ps -o pgid= -p "$BASH_PID" 2>/dev/null | tr -d ' ')"
[[ "$PGID_HARNAIS" == "$BASH_PID" ]] \
  && ok "le harnais mene son propre groupe (PGID $PGID_HARNAIS = PID)" \
  || echoue "le harnais partage le groupe $PGID_HARNAIS: sa descendance n'est pas delimitee"

# LE TEMOIN, PAS UN `psql` DE PASSAGE. Attendre un descendant naturel ne
# marchait que par accident: `harnais_verrou_prendre()` ouvre un `coproc psql`
# de longue duree en execution AUTONOME, mais retourne sans coproc sous
# `run.sh`, ou le marqueur de reentrance dispense de prendre le verrou. Mesure:
# le test etait vert seul et rouge imbrique — « aucun descendant vivant observe
# en 60 s » — dans les DEUX modes de connexion, sans que la propriete testee
# ait change. Un descendant explicite, qui annonce lui-meme sa disponibilite,
# ne depend d'aucun ordonnancement.
attendre "le temoin descendant (READY)" '[[ -s "$TEMOIN_DESC" ]]' 3000 || exit 1
TEMOIN_PID="$(awk '{print $1}' "$TEMOIN_DESC")"
if [[ -z "$TEMOIN_PID" ]] || ! grep -q READY "$TEMOIN_DESC"; then
  echoue "le temoin n'a pas annonce READY: $(tr -d '\n' <"$TEMOIN_DESC")"
  exit 1
fi
ok "temoin descendant cree et READY (PID $TEMOIN_PID)"

# Il doit VRAIMENT etre dans le groupe du harnais — sinon le terminer par
# groupe ne prouverait rien de la descendance du harnais.
PGID_TEMOIN="$(ps -o pgid= -p "$TEMOIN_PID" 2>/dev/null | tr -d ' ')"
[[ "$PGID_TEMOIN" == "$BASH_PID" ]] \
  && ok "le temoin appartient au groupe du harnais (PGID $PGID_TEMOIN)" \
  || echoue "le temoin est dans le groupe $PGID_TEMOIN, pas $BASH_PID"

PETITS="$(vivants "$TEMOIN_PID $(descendants "$BASH_PID" | tr '\n' ' ')")"
[[ -n "$(vivants "$TEMOIN_PID")" ]] \
  && ok "descendance vivante a l'instant du signal: $PETITS" \
  || { echoue "le temoin $TEMOIN_PID n'est plus vivant avant le signal"; exit 1; }

kill -TERM "$MPID"
CODE=0; wait "$MPID" 2>/dev/null || CODE=$?
MPID=""

[[ "$CODE" -eq 143 ]] \
  && ok "code de sortie 143 (128 + SIGTERM)" \
  || { echoue "code de sortie $CODE, attendu 143"
       detail "une exception echappee ramene le code a 1 et masque le signal"; }

if grep -qE '^MUTATIONS: definis [0-9]+ \| termines [0-9]+ \| interrompu 1 \| non commences [0-9]+ \| perimes [0-9]+ \| creux [0-9]+ \| code 143$' "$SORTIE"; then
  ok "verdict partiel imprime, avec ses colonnes"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE")"
else
  echoue "aucun verdict partiel conforme"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE" || echo '(aucune ligne MUTATIONS:)')"
fi

manque=()
grep -q "controle actif : $CAS_NOM"  "$SORTIE" || manque+=("controle actif")
grep -q "fichier mute   : $CAS_FIC"  "$SORTIE" || manque+=("fichier mute")
grep -q "signal recu    : SIGTERM"   "$SORTIE" || manque+=("signal recu")
grep -qE "SHA teste      : [0-9a-f]{40}" "$SORTIE" || manque+=("SHA teste")
[[ ${#manque[@]} -eq 0 ]] \
  && ok "le verdict nomme le controle, le fichier, le signal et le SHA" \
  || echoue "le verdict ne nomme pas: ${manque[*]}"

grep -qE 'Traceback|FileNotFoundError|None/' "$SORTIE" \
  && { echoue "un traceback ou un chemin « None/ » subsiste"
       detail "$(grep -m2 -E 'Traceback|FileNotFoundError|None/' "$SORTIE")"; } \
  || ok "aucun traceback, aucun « FileNotFoundError », aucun chemin « None/ »"

APRES="$(sha256sum "$PROJET/$CAS_FIC" | cut -d' ' -f1)"
[[ "$APRES" == "$AVANT" ]] \
  && ok "le fichier du depot principal est inchange" \
  || echoue "le fichier du depot principal a change: $AVANT -> $APRES"

kill -0 "$BASH_PID" 2>/dev/null && [[ -n "$(vivants "$BASH_PID")" ]] \
  && echoue "le Bash du harnais ($BASH_PID) survit" \
  || ok "le Bash du harnais est termine"

[[ -z "$(vivants "$TEMOIN_PID")" ]] \
  && ok "le temoin descendant ($TEMOIN_PID) a ete termine avec le groupe" \
  || echoue "le temoin descendant $TEMOIN_PID SURVIT: la descendance n'est pas terminee"
RESTANTS="$(vivants "$PETITS")"
[[ -z "$RESTANTS" ]] \
  && ok "aucun descendant du harnais ne survit ($PETITS verifies)" \
  || echoue "descendants orphelins: $RESTANTS"

GROUPE="$(groupe_vivant "$BASH_PID")"
[[ -z "${GROUPE// /}" ]] \
  && ok "le groupe du harnais ne contient plus aucun processus vivant" \
  || { echoue "le groupe $BASH_PID contient encore des processus vivants: $GROUPE"
       detail "$(ps -o pid=,stat=,args= -g "$BASH_PID" 2>/dev/null | head -3)"; }

ERRANTS="$(vivants "$(pgrep -f "$HARNAIS_NOM $HARNAIS_PREFIXE" 2>/dev/null | tr '\n' ' ')")"
[[ -z "${ERRANTS// /}" ]] \
  && ok "aucun processus ne porte plus « $HARNAIS_NOM $HARNAIS_PREFIXE »" \
  || echoue "processus portant le harnais: $ERRANTS"

# ROLES ET BASES — au prefixe propre du harnais, et EN FAIL-CLOSED.
reste_r="$(lire_sql "select coalesce(string_agg(rolname,','),'') from pg_roles
                      where rolname like '${HARNAIS_PREFIXE}\\_%'")"
if [[ "$reste_r" == ILLISIBLE* ]]; then
  echoue "roles residuels: lecture impossible — ${reste_r#*$'\t'}"
  detail "une lecture impossible n'est pas « aucun residu »"
else
  reste_b="$(lire_sql "select coalesce(string_agg(datname,','),'') from pg_database
                        where datname like '${HARNAIS_PREFIXE}\\_%'")"
  if [[ "$reste_b" == ILLISIBLE* ]]; then
    echoue "bases residuelles: lecture impossible — ${reste_b#*$'\t'}"
    detail "une lecture impossible n'est pas « aucun residu »"
  elif [[ -z "$reste_r" && -z "$reste_b" ]]; then
    ok "ni role ni base au prefixe « $HARNAIS_PREFIXE » ne subsiste"
  else
    echoue "residu SQL — roles[$reste_r] bases[$reste_b]"
  fi
fi

comparer_verrous "A" "$VERROUS_AVANT_A"

if [[ -n "$ESPACE_DEPOT" ]] && git -C "$RACINE" worktree list --porcelain \
     | grep -q "^worktree $ESPACE_DEPOT$"; then
  echoue "le worktree $ESPACE_DEPOT est encore enregistre"
elif [[ -d "$ESPACE_DEPOT" ]]; then
  echoue "le repertoire $ESPACE_DEPOT est encore sur disque"
else
  ok "le worktree est retire, une fois, et son repertoire avec"
  ESPACE_DEPOT=""
fi

# ==========================================================================
# B. SIGNAL ENTRE DEUX CONTROLES — plus rien n'est en vol
# ==========================================================================
echo "      -- B. entre deux controles, aucun controle en vol"
rm -f "$TRACE" "$SORTIE"
VERROUS_AVANT_B="$(empreinte_verrous)"
TEMOIN="$(mktemp)"
# `ESC_MUTATION_PAUSE_ENTRE` ouvre une fenetre DETERMINISTE apres chaque
# controle rendu, et `ESC_MUTATION_ENTRE_TEMOIN` dit quand elle s'ouvre. Sans
# ces deux prises, il faudrait viser quelques microsecondes.
lancer_matrice 1 "ESC_MUTATION_PAUSE_ENTRE=60" "ESC_MUTATION_ENTRE_TEMOIN=$TEMOIN"

attendre "la mutation posee (controle 1)" '[[ -s "$TRACE" ]]' 3000 || exit 1
IFS=$'\t' read -r _N _F _S _E ESPACE_DEPOT <"$TRACE"
attendre "la fenetre entre deux controles" '[[ -s "$TEMOIN" ]]' 3000 || exit 1
ok "fenetre ouverte: $(tr '\t' ' ' <"$TEMOIN" | tr -d '\n') controle(s) rendu(s)"

kill -TERM "$MPID"
CODE=0; wait "$MPID" 2>/dev/null || CODE=$?
MPID=""

[[ "$CODE" -eq 143 ]] && ok "code de sortie 143" \
                      || echoue "code de sortie $CODE, attendu 143"

# UN SIGNAL ENTRE DEUX CONTROLES N'INVENTE PAS DE CONTROLE INTERROMPU.
if grep -qE '^MUTATIONS: definis 64 \| termines 1 \| interrompu 0 \| non commences 63 \| perimes 0 \| creux 0 \| code 143$' "$SORTIE"; then
  ok "verdict: 1 termine, 0 interrompu, 63 non commences"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE")"
else
  echoue "decompte inattendu entre deux controles"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE" || echo '(aucune ligne MUTATIONS:)')"
fi

grep -q "controle actif : aucun" "$SORTIE" \
  && ok "le verdict dit « aucun controle actif »" \
  || echoue "le verdict ne dit pas « aucun controle actif »"

grep -qE 'Traceback|FileNotFoundError|None/' "$SORTIE" \
  && { echoue "un traceback subsiste apres un signal entre deux controles"
       detail "$(grep -m2 -E 'Traceback|FileNotFoundError|None/' "$SORTIE")"; } \
  || ok "aucun traceback"

if [[ -n "$ESPACE_DEPOT" ]] && git -C "$RACINE" worktree list --porcelain \
     | grep -q "^worktree $ESPACE_DEPOT$"; then
  echoue "le worktree $ESPACE_DEPOT est encore enregistre"
else
  ok "aucun worktree residuel"
  ESPACE_DEPOT=""
fi

comparer_verrous "B" "$VERROUS_AVANT_B"

# ==========================================================================
# C. FUITE INJECTEE — la comparaison detecte-t-elle, ou approuve-t-elle ?
# ==========================================================================
# Les scenarios A et B sont verts quand rien ne fuit; encore faut-il etablir
# qu'ils rougiraient si quelque chose fuyait.
#
# LES CLES SONT PROPRES A L'EXECUTION, dans le domaine int4, et la connexion
# porte un `application_name` derive du jeton. On peut ainsi PROUVER quel
# backend nous appartient — au lieu de terminer tout ce qui porte les memes
# cles, ce qui tuerait une session tierce ou une execution concurrente.
echo "      -- C. fuite injectee: la comparaison doit la voir"
CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
APP_FUITE="esc-fuite-$JETON"; APP_TIERS="esc-tiers-$JETON"
VERROUS_AVANT_C="$(empreinte_verrous)"

# VERROU PARTAGE, ET C'EST DELIBERE: il permet a une session TIERCE de detenir
# les MEMES cles en meme temps. C'est la seule facon d'exercer reellement le
# defaut « selection par cles seules », qui les aurait terminees toutes les deux.
PGAPPNAME="$APP_FUITE" psql -X -qtA -d postgres -c \
  "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(120);" >/dev/null 2>&1 &
FUITE_CLIENT=$!

for _ in $(seq 1 300); do
  FUITE_BACKEND="$(psql -X -qtA -d postgres -c \
    "select pid from pg_stat_activity where application_name = '$APP_FUITE'" 2>/dev/null | head -1)"
  [[ -n "$FUITE_BACKEND" ]] && break
  kill -0 "$FUITE_CLIENT" 2>/dev/null || break
  sleep 0.1
done

if [[ -z "$FUITE_BACKEND" ]]; then
  echoue "C: la connexion porteuse n'est jamais apparue — scenario non exerce"
else
  # LA PROPRIETE EST PROUVEE AVANT DE TOUCHER A QUOI QUE CE SOIT: ce PID, ce
  # verrou, cette base, `objsubid = 2`.
  # LA DETENTION, PAS LA PRESENCE. Une ligne dans `pg_stat_activity` peut
  # preceder l'acquisition du verrou: annoncer la propriete sur cette base
  # affirmerait ce qui n'a pas ete observe.
  rcd=1
  for _ in $(seq 1 300); do
    detient_verrou "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock; rcd=$?
    (( rcd != 1 )) && break
    sleep 0.1
  done
  if (( rcd == 3 )); then
    echoue "C: detention du verrou de C illisible — $CMP_DIAG"
  elif (( rcd != 0 )); then
    echoue "C: le backend $FUITE_BACKEND ne detient pas le verrou attendu"
  else
    ok "verrou injecte pose: backend $FUITE_BACKEND, cles ($CLE1,$CLE2), objsubid 2"

    # LA COMPARAISON DOIT RENDRE EXACTEMENT 10 — « verrou supplementaire ».
    # Ni 11, ni 12, ni 20/21: une panne d'observation ne doit pas etre lue
    # comme une fuite correctement detectee.
    comparer_verrous "C" "$VERROUS_AVANT_C" muet; rc=$?
    if (( rc == 10 )); then
      if [[ "$(grep -c . <<<"$CMP_APPARUS")" == "1" ]] \
         && grep -q "|$FUITE_BACKEND|$CLE1|$CLE2|2|ShareLock|true$" <<<"$CMP_APPARUS"; then
        ok "la comparaison rend « verrou supplementaire » (10), sur le PID de C exactement"
        detail "$(tr '\n' ' ' <<<"$CMP_APPARUS")"
      else
        echoue "C: la difference ne correspond pas au verrou de C"
        detail "attendu le PID $FUITE_BACKEND et les cles ($CLE1,$CLE2)"
        detail "obtenu: $(tr '\n' ' ' <<<"$CMP_APPARUS")"
      fi
    else
      echoue "C: la comparaison rend $rc, attendu 10 (verrou supplementaire)"
      case $rc in
        0)  detail "elle a APPROUVE un verrou supplementaire: A et B ne prouvent rien" ;;
        20|21) detail "observation impossible — $CMP_DIAG" ;;
        *)  detail "apparus[$(tr '\n' ' ' <<<"$CMP_APPARUS")] disparus[$(tr '\n' ' ' <<<"$CMP_DISPARUS")]" ;;
      esac
    fi

    # --- LE TIERS: MEMES CLES, ET IL DOIT SURVIVRE ------------------------
    PGAPPNAME="$APP_TIERS" psql -X -qtA -d postgres -c \
      "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(120);" >/dev/null 2>&1 &
    TIERS_CLIENT=$!
    for _ in $(seq 1 300); do
      TIERS_BACKEND="$(psql -X -qtA -d postgres -c \
        "select pid from pg_stat_activity where application_name = '$APP_TIERS'" 2>/dev/null | head -1)"
      [[ -n "$TIERS_BACKEND" ]] && break
      kill -0 "$TIERS_CLIENT" 2>/dev/null || break
      sleep 0.1
    done
    rct=1
    if [[ -n "$TIERS_BACKEND" ]]; then
      for _ in $(seq 1 300); do
        detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock; rct=$?
        (( rct != 1 )) && break
        sleep 0.1
      done
    fi
    if [[ -z "$TIERS_BACKEND" ]] || (( rct != 0 )); then
      echoue "C: la session tierce ne detient pas le meme verrou — survie non exercee"
      (( rct == 3 )) && detail "lecture impossible: $CMP_DIAG"
    elif [[ "$TIERS_BACKEND" == "$FUITE_BACKEND" ]]; then
      echoue "C: tiers et fuite partagent le meme PID ($TIERS_BACKEND)"
    else
      ok "session tierce DETENTRICE du meme verrou partage: backend $TIERS_BACKEND (ShareLock, accorde)"

      # UN PID N'EST PAS UNE AUTORITE — et voici la preuve. Meme PID, MAUVAISE
      # identite: la terminaison doit REFUSER, et la session survivre avec son
      # verrou. Sans ce controle, « on ne termine que ce qu'on possede » ne
      # serait qu'une intention.
      terminer_possede "$TIERS_BACKEND" "$APP_TIERS-FAUX" "$CLE1" "$CLE2" ShareLock "C (mauvaise identite)"
      rcf=$?
      if (( rcf == 2 )); then
        detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock \
          && ok "identite non concordante: terminaison REFUSEE, backend et verrou intacts" \
          || echoue "C: la mauvaise identite a ete refusee mais le verrou a disparu"
      else
        echoue "C: une mauvaise identite rend $rcf, attendu 2 (refus)"
        (( rcf == 0 )) && detail "le PID seul a suffi a tuer: la propriete n'est pas verifiee"
      fi

      terminer_possede "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock "C"
      rcf=$?
      (( rcf == 0 )) && FUITE_BACKEND="" \
                     || echoue "C: la terminaison du backend de C rend $rcf, attendu 0"

      # DEUX PROPRIETES SEPAREES: le backend tiers existe encore, ET il detient
      # toujours exactement le meme verrou. « Il est vivant » ne prouve pas que
      # le nettoyage a laisse son verrou tranquille.
      vit="$(lire_sql "select count(*) from pg_stat_activity where pid = $TIERS_BACKEND")"
      if [[ "$vit" == ILLISIBLE* ]]; then
        echoue "C: survie du tiers illisible — ${vit#*$'\t'}"
      elif [[ "$vit" == "1" ]]; then
        ok "le backend tiers a SURVECU au nettoyage de C"
      else
        echoue "C: la session tierce a ete terminee — nettoyage par cles, pas par propriete"
      fi
      if detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock; then
        ok "le tiers detient TOUJOURS exactement le meme verrou partage, accorde"
      else
        echoue "C: le verrou du tiers a disparu pendant le nettoyage de C"
      fi

      terminer_possede "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock "C (tiers)"
      (( $? == 0 )) && TIERS_BACKEND="" || echoue "C: le tiers n'a pas pu etre nettoye"
    fi

    kill "$FUITE_CLIENT" 2>/dev/null; wait "$FUITE_CLIENT" 2>/dev/null; FUITE_CLIENT=""
    [[ -n "$TIERS_CLIENT" ]] && { kill "$TIERS_CLIENT" 2>/dev/null
                                  wait "$TIERS_CLIENT" 2>/dev/null; TIERS_CLIENT=""; }

    # APRES NETTOYAGE, L'EGALITE EXACTE — code 0, rien d'autre. Sans cette
    # seconde moitie, un detecteur qui rougirait TOUJOURS passerait aussi.
    comparer_verrous "C (retour a l'etat initial)" "$VERROUS_AVANT_C"; rc=$?
    (( rc == 0 )) || echoue "C: apres nettoyage la comparaison rend $rc, attendu 0"
  fi
fi

# ==========================================================================
# D. OBSERVATION IMPOSSIBLE — fail-closed, jamais « fuite detectee »
# ==========================================================================
# UNE PANNE DE LECTURE N'EST NI UNE FUITE NI UNE ABSENCE DE FUITE. Sans ce
# scenario, une connexion perdue au mauvais moment produisait « ok: la
# comparaison rougit sur le verrou supplementaire » alors qu'aucun verrou
# n'avait ete observe — le test se felicitait d'une panne.
echo "      -- D. observation impossible: fail-closed"
VERROUS_AVANT_D="$(empreinte_verrous)"
if [[ "$VERROUS_AVANT_D" == ILLISIBLE* ]]; then
  echoue "D: etat de depart deja illisible"
else
  ESC_VERROUS_ILLISIBLE=1 comparer_verrous "D" "$VERROUS_AVANT_D" muet; rc=$?
  if (( rc == 21 )); then
    ok "une lecture APRES impossible rend 21, et non 0 ni 10"
    detail "diagnostic conserve: $CMP_DIAG"
  else
    echoue "D: la comparaison rend $rc sur une lecture impossible, attendu 21"
    (( rc == 10 )) && detail "une panne d'observation a ete lue comme une fuite detectee"
    (( rc == 0 ))  && detail "une panne d'observation a ete lue comme « aucun verrou »"
  fi
  # ...et l'etat AVANT illisible se distingue de l'etat APRES illisible.
  comparer_verrous "D" "$(printf 'ILLISIBLE\tpanne simulee\n')" muet; rc=$?
  (( rc == 20 )) \
    && ok "un etat AVANT illisible rend 20, distinct du 21" \
    || echoue "D: etat AVANT illisible rend $rc, attendu 20"
fi

# ==========================================================================
# E. INTERRUPTION PENDANT C — le trap nettoie ce qu'il possede, et se mesure
# ==========================================================================
# « Y COMPRIS SI UN SIGNAL ARRIVE ENTRE L'ACQUISITION ET LE NETTOYAGE » etait
# une AFFIRMATION, pas une mesure. Ce scenario l'exerce: un sous-processus pose
# les deux verrous, annonce READY, et recoit SIGTERM a cet instant.
echo "      -- E. interruption pendant C: le trap doit tout rendre"
TEMOIN_E="$(mktemp)"
E_CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
E_CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
VERROUS_AVANT_E="$(empreinte_verrous)"
ESC_SIGNAL_SOUS_MODE=interruption_c ESC_SIGNAL_TEMOIN="$TEMOIN_E" \
  ESC_SIGNAL_CLE1="$E_CLE1" ESC_SIGNAL_CLE2="$E_CLE2" \
  bash "$HERE/$(basename "${BASH_SOURCE[0]}")" >/dev/null 2>&1 &
EPID=$!

pret=0
for _ in $(seq 1 900); do
  grep -q READY "$TEMOIN_E" 2>/dev/null && { pret=1; break; }
  kill -0 "$EPID" 2>/dev/null || break
  sleep 0.1
done
if (( pret == 0 )); then
  echoue "E: le sous-mode n'a jamais annonce READY"
  kill -KILL "$EPID" 2>/dev/null; wait "$EPID" 2>/dev/null
else
  E_FB="$(sed -n 's/^FUITE_BACKEND=//p' "$TEMOIN_E")"
  E_TB="$(sed -n 's/^TIERS_BACKEND=//p' "$TEMOIN_E")"
  E_FC="$(sed -n 's/^FUITE_CLIENT=//p'  "$TEMOIN_E")"
  E_TC="$(sed -n 's/^TIERS_CLIENT=//p'  "$TEMOIN_E")"
  E_AF="$(sed -n 's/^APP_FUITE=//p'     "$TEMOIN_E")"
  E_AT="$(sed -n 's/^APP_TIERS=//p'     "$TEMOIN_E")"
  if ! pid_valide "${E_FB:-x}" || ! pid_valide "${E_TB:-x}"; then
    echoue "E: le sous-mode n'a pas publie deux PID backend valides ($E_FB / $E_TB)"
  else
    ok "sous-mode pret: backends $E_FB (fuite) et $E_TB (tiers), cles ($E_CLE1,$E_CLE2)"
    kill -TERM "$EPID"
    E_CODE=0; wait "$EPID" 2>/dev/null || E_CODE=$?
    ok "sous-mode interrompu, code $E_CODE"

    # 1. AUCUN BACKEND PORTANT LES DEUX JETONS.
    reste="$(lire_sql "select coalesce(string_agg(pid::text,','),'') from pg_stat_activity
                        where application_name in ('$E_AF','$E_AT')")"
    if [[ "$reste" == ILLISIBLE* ]]; then
      echoue "E: pg_stat_activity illisible — ${reste#*$'\t'}"
    elif [[ -z "$reste" ]]; then
      ok "aucun backend ne porte plus les jetons du sous-mode"
    else
      echoue "E: backends survivants sous les jetons du sous-mode: $reste"
    fi

    # 2. AUCUN VERROU CORRESPONDANT.
    reste="$(lire_sql "select count(*) from pg_locks
                        where locktype='advisory' and classid=$E_CLE1 and objid=$E_CLE2")"
    if [[ "$reste" == ILLISIBLE* ]]; then
      echoue "E: pg_locks illisible — ${reste#*$'\t'}"
    elif [[ "$reste" == "0" ]]; then
      ok "aucun verrou des cles du sous-mode ne subsiste"
    else
      echoue "E: $reste verrou(s) des cles ($E_CLE1,$E_CLE2) subsistent"
    fi

    # 3. AUCUN CLIENT LOCAL VIVANT.
    survivants="$(vivants "$E_FC $E_TC $EPID")"
    [[ -z "$survivants" ]] \
      && ok "aucun client local du sous-mode ne survit" \
      || echoue "E: clients locaux survivants: $survivants"

    # 4. L'ETAT GLOBAL DES VERROUS EST REVENU A CELUI D'AVANT E.
    comparer_verrous "E" "$VERROUS_AVANT_E"
  fi
fi
rm -f "$TEMOIN_E"

# ==========================================================================
# F. NETTOYAGE EN ECHEC — le verdict doit changer, pas absorber
# ==========================================================================
echo "      -- F. nettoyage en echec: le code de sortie doit le refleter"
TEMOIN_F="$(mktemp)"
F_CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
F_CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
ESC_SIGNAL_SOUS_MODE=nettoyage_casse ESC_SIGNAL_TEMOIN="$TEMOIN_F" \
  ESC_SIGNAL_CLE1="$F_CLE1" ESC_SIGNAL_CLE2="$F_CLE2" \
  bash "$HERE/$(basename "${BASH_SOURCE[0]}")" >"$TEMOIN_F.log" 2>&1 &
FPID=$!
F_CODE=0; wait "$FPID" 2>/dev/null || F_CODE=$?
F_FB="$(sed -n 's/^FUITE_BACKEND=//p' "$TEMOIN_F")"
F_AF="$(sed -n 's/^APP_FUITE=//p' "$TEMOIN_F")"
if (( F_CODE == 9 )); then
  ok "un nettoyage en echec remplace le verdict: code 9, et non 0"
  grep -q 'ECHEC (nettoyage)' "$TEMOIN_F.log" \
    && ok "le premier diagnostic de nettoyage est conserve" \
    || echoue "F: aucun diagnostic « ECHEC (nettoyage) » n'a ete emis"
else
  echoue "F: code de sortie $F_CODE, attendu 9 (nettoyage rouge)"
  detail "un nettoyage dont l'echec n'atteint pas le code de sortie est invisible"
  detail "$(grep -m2 'ECHEC' "$TEMOIN_F.log" || echo '(aucun ECHEC)')"
fi
# C'EST NOUS QUI RENDONS CE QUE LE SOUS-MODE N'A PAS PU RENDRE — par identite
# verifiee, jamais par cles seules.
if pid_valide "${F_FB:-x}"; then
  terminer_possede "$F_FB" "$F_AF" "$F_CLE1" "$F_CLE2" ShareLock "F (rattrapage)" >/dev/null
fi
reste="$(lire_sql "select count(*) from pg_locks
                    where locktype='advisory' and classid=$F_CLE1 and objid=$F_CLE2")"
[[ "$reste" == "0" ]] \
  && ok "le verrou laisse par le nettoyage casse a ete rendu" \
  || echoue "F: verrou residuel apres rattrapage ($reste)"
rm -f "$TEMOIN_F" "$TEMOIN_F.log"

echo
[[ $KO -eq 0 ]] \
  && echo "    La matrice rend un verdict, et le test prouve ce qu'il affirme." \
  || echo "    La matrice ne meurt pas proprement." >&2
sortir $KO
