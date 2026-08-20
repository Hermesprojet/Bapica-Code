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
# DEUX SCENARIOS, DEUX FENETRES DISTINCTES
# -----------------------------------------
#   A. SIGNAL PENDANT UN HARNAIS, QUI A LUI-MEME UNE DESCENDANCE.
#      C'est la fenetre ou `finally: restaurer()` s'execute — la seule qui
#      exerce le defaut d'origine. Un test qui signalerait pendant la pause
#      resterait vert contre le code fautif et ne prouverait rien.
#      Elle etablit aussi que TOUTE LA DESCENDANCE meurt: terminer le seul Bash
#      laissait vivre `psql`, sous-shells et clusters temporaires, avec leurs
#      connexions et leurs verrous. « Aucun enfant ne survit » etait une
#      conclusion plus large que ce qui etait mesure.
#
#   B. SIGNAL ENTRE DEUX CONTROLES, quand plus rien n'est en vol.
#      La frontiere de capture n'entourait que l'appel a `essayer()`: une
#      `Interruption` levee apres « ACTIF = None », pendant le pre-vol, ou au
#      retour d'`essayer()`, s'echappait vers un arret SANS VERDICT. La branche
#      « aucun controle actif » etait ECRITE sans qu'aucun chemin ne garantisse
#      de l'atteindre. Un signal entre deux controles ne doit pas non plus
#      inventer un controle interrompu.
#
# SIGKILL N'EST PAS COUVERT, ET NE PEUT PAS L'ETRE: il n'est pas interceptable.
# Aucun verdict ne peut etre exige apres un SIGKILL. Ce que
# `mutation_isolation_selftest.sh` continue d'etablir dans ce cas, c'est que le
# DEPOT PRINCIPAL n'est pas modifie — la seule garantie qui survive a un arret
# non negociable.
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

TRACE=""; SORTIE=""; TEMOIN=""; ESPACE_DEPOT=""; MPID=""

menage() {
  # SIGTERM D'ABORD, SIGKILL SEULEMENT SI ELLE S'ACCROCHE. Un `kill -KILL`
  # immediat empeche la matrice de retirer son propre worktree, et ce test
  # s'arrete parfois AVANT d'avoir lu la trace — donc sans connaitre le chemin
  # a nettoyer lui-meme. Mesure: deux `esc-mutations-*` sont restes enregistres
  # apres deux arrets prematures de ce test.
  if [[ -n "$MPID" ]] && kill -0 "$MPID" 2>/dev/null; then
    kill -TERM "$MPID" 2>/dev/null
    for _ in $(seq 1 100); do kill -0 "$MPID" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$MPID" 2>/dev/null
  fi
  if [[ -n "$ESPACE_DEPOT" && -d "$ESPACE_DEPOT" ]]; then
    git -C "$RACINE" worktree remove --force "$ESPACE_DEPOT" 2>/dev/null
    rm -rf "$ESPACE_DEPOT"
    git -C "$RACINE" worktree prune 2>/dev/null
  fi
  rm -f "$TRACE" "$SORTIE" "$TEMOIN"
}
trap menage EXIT

# `descendants` REMONTE TOUT L'ARBRE, pas seulement le premier niveau. Le test
# concluait « aucun enfant ne survit » en n'ayant regarde que l'enfant DIRECT
# de la matrice — c'est-a-dire le Bash du harnais, jamais ce qu'il engendre.
descendants() {
  local p
  for p in $(pgrep -P "$1" 2>/dev/null); do echo "$p"; descendants "$p"; done
}

vivants() {   # vivants <liste de PID> -> ceux qui existent encore
  local p restants=""
  for p in $1; do kill -0 "$p" 2>/dev/null && restants="$restants $p"; done
  echo "${restants# }"
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
  # en derniere position, l'attente REUSSIE rendait 1 — parce que la borne
  # n'etait pas atteinte. Le test s'arretait donc sur une attente satisfaite,
  # sans message. Mesure: la trace etait ecrite, et l'appelant lisait un echec.
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
# A. SIGNAL PENDANT UN HARNAIS QUI A UNE DESCENDANCE
# ==========================================================================
echo "      -- A. pendant un harnais, avec sa descendance"
lancer_matrice W1

attendre "la mutation posee" '[[ -s "$TRACE" ]]' 3000 || exit 1
IFS=$'\t' read -r CAS_NOM CAS_FIC CAS_SOMME _ESPACE ESPACE_DEPOT <"$TRACE"
ok "mutation posee: $CAS_NOM sur $CAS_FIC"

AVANT="$(sha256sum "$PROJET/$CAS_FIC" | cut -d' ' -f1)"
[[ "$AVANT" != "$CAS_SOMME" ]] \
  && ok "le depot principal differe deja de la version mutee (attendu)" \
  || echoue "le depot principal porte l'empreinte MUTEE: l'isolation a cede"

# LE HARNAIS TOURNE, ET IL A LUI-MEME ENGENDRE QUELQUE CHOSE. Attendre le seul
# enfant direct ne suffirait pas: c'est la descendance qu'on veut voir mourir.
attendre "le harnais lance par la matrice" \
         '[[ -n "$(pgrep -P "$MPID" 2>/dev/null)" ]]' 3000 || exit 1
BASH_PID="$(pgrep -P "$MPID" 2>/dev/null | head -1)"
attendre "un descendant du harnais" \
         '[[ -n "$(descendants "$BASH_PID")" ]]' 3000 || exit 1

# Le harnais et son prefixe, lus sur SA propre ligne de commande.
CMDLINE="$(ps -o args= -p "$BASH_PID" 2>/dev/null)"
HARNAIS_NOM="$(awk '{print $2}' <<<"$CMDLINE")"
HARNAIS_PREFIXE="$(awk '{print $3}' <<<"$CMDLINE")"
ok "harnais « $HARNAIS_NOM $HARNAIS_PREFIXE » (PID $BASH_PID)"

# --- LA VERIFICATION STRUCTURELLE, ET C'EST ELLE QUI PORTE -----------------
# Le harnais doit MENER SON PROPRE GROUPE: son PGID doit valoir son PID. C'est
# la condition sans laquelle « terminer tout ce que ce harnais a engendre » ne
# peut pas meme s'exprimer — on ne saurait pas quoi viser. Sans
# `start_new_session=True` le harnais herite du groupe de la matrice, et le
# seul moyen de le nettoyer par groupe serait de se tuer soi-meme.
PGID_HARNAIS="$(ps -o pgid= -p "$BASH_PID" 2>/dev/null | tr -d ' ')"
[[ "$PGID_HARNAIS" == "$BASH_PID" ]] \
  && ok "le harnais mene son propre groupe (PGID $PGID_HARNAIS = PID)" \
  || echoue "le harnais partage le groupe $PGID_HARNAIS: sa descendance n'est pas delimitee"

# --- UN DESCENDANT REELLEMENT VIVANT AU MOMENT DU SIGNAL -------------------
# Le harnais engendre des `psql` de courte duree: un PID releve quelques
# centaines de millisecondes plus tot peut etre mort de sa belle mort, et « il
# n'est plus la » ne prouverait alors rien. On reessaie donc jusqu'a en tenir un
# qu'on vient de constater VIVANT, et c'est de celui-la seul qu'on exigera la
# disparition.
PETITS=""
for _ in $(seq 1 600); do
  PETITS="$(vivants "$(descendants "$BASH_PID" | tr '\n' ' ')")"
  [[ -n "$PETITS" ]] && break
  kill -0 "$MPID" 2>/dev/null || break
  sleep 0.1
done
if [[ -z "$PETITS" ]]; then
  echoue "aucun descendant vivant observe en 60 s: scenario non exerce"
  exit 1
fi
ok "descendance vivante a l'instant du signal: $PETITS"

kill -TERM "$MPID"
CODE=0; wait "$MPID" 2>/dev/null || CODE=$?
MPID=""

if [[ "$CODE" -eq 143 ]]; then
  ok "code de sortie 143 (128 + SIGTERM)"
else
  echoue "code de sortie $CODE, attendu 143"
  detail "une exception echappee ramene le code a 1 et masque le signal"
fi

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

# --- CE QUI RESTE DERRIERE -------------------------------------------------
APRES="$(sha256sum "$PROJET/$CAS_FIC" | cut -d' ' -f1)"
[[ "$APRES" == "$AVANT" ]] \
  && ok "le fichier du depot principal est inchange" \
  || echoue "le fichier du depot principal a change: $AVANT -> $APRES"

kill -0 "$BASH_PID" 2>/dev/null \
  && echoue "le Bash du harnais ($BASH_PID) survit" \
  || ok "le Bash du harnais est termine"

RESTANTS="$(vivants "$PETITS")"
[[ -z "$RESTANTS" ]] \
  && ok "aucun descendant du harnais ne survit (${PETITS% } verifies)" \
  || echoue "descendants orphelins: $RESTANTS"

# LE GROUPE ENTIER, PAS SEULEMENT LES PID QU'ON AVAIT RELEVES. `kill -0` sur un
# PGID negatif reussit tant qu'IL RESTE UN SEUL PROCESSUS dans le groupe: c'est
# la formulation exacte de « toute la descendance est terminee », y compris ce
# qui serait ne apres notre releve.
if kill -0 -"$BASH_PID" 2>/dev/null; then
  echoue "le groupe $BASH_PID contient encore des processus"
  detail "$(ps -o pid=,args= -g "$BASH_PID" 2>/dev/null | head -3)"
else
  ok "le groupe du harnais est vide: toute la descendance est terminee"
fi

ERRANTS="$(pgrep -f "$HARNAIS_NOM $HARNAIS_PREFIXE" 2>/dev/null | tr '\n' ' ')"
[[ -z "${ERRANTS// /}" ]] \
  && ok "aucun processus ne porte plus « $HARNAIS_NOM $HARNAIS_PREFIXE »" \
  || echoue "processus portant le harnais: $ERRANTS"

# NI VERROU, NI ROLE, NI BASE LAISSES PAR CETTE DESCENDANCE.
if command -v psql >/dev/null 2>&1; then
  reste_r="$(psql -X -tA -d postgres -c \
    "select coalesce(string_agg(rolname,','),'') from pg_roles
      where rolname like '${HARNAIS_PREFIXE}\\_%'" 2>/dev/null)"
  reste_b="$(psql -X -tA -d postgres -c \
    "select coalesce(string_agg(datname,','),'') from pg_database
      where datname like '${HARNAIS_PREFIXE}\\_%'" 2>/dev/null)"
  reste_v="$(psql -X -tA -d postgres -c \
    "select count(*) from pg_locks where locktype='advisory'" 2>/dev/null)"
  [[ -z "$reste_r" && -z "$reste_b" && "$reste_v" == "0" ]] \
    && ok "ni verrou, ni role, ni base laisses par le harnais" \
    || echoue "residu SQL — roles[$reste_r] bases[$reste_b] verrous[$reste_v]"
fi

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

[[ "$CODE" -eq 143 ]] \
  && ok "code de sortie 143" \
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

echo
[[ $KO -eq 0 ]] \
  && echo "    La matrice rend un verdict, interrompue pendant comme entre." \
  || echo "    La matrice ne meurt pas proprement." >&2
exit $KO
