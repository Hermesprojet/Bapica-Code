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
CLE1=0; CLE2=0

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
terminer_backend() {   # terminer_backend <pid> <libelle>
  local pid="$1" quoi="$2" n=0
  [[ -z "$pid" ]] && return 0
  psql -X -qtA -d postgres -c "select pg_terminate_backend($pid)" >/dev/null 2>&1
  while (( n++ < 150 )); do
    local reste
    reste="$(psql -X -qtA -d postgres -c \
      "select count(*) from pg_stat_activity where pid = $pid" 2>/dev/null)"
    [[ "$reste" == "0" ]] && return 0
    sleep 0.1
  done
  echoue "$quoi: le backend $pid n'a pas disparu apres terminaison"
  return 1
}

menage() {
  if [[ -n "$MPID" ]] && kill -0 "$MPID" 2>/dev/null; then
    kill -TERM "$MPID" 2>/dev/null
    for _ in $(seq 1 100); do kill -0 "$MPID" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$MPID" 2>/dev/null
  fi
  # Les backends d'abord — y compris si un signal arrive entre l'acquisition du
  # verrou et le nettoyage normal.
  [[ -n "$FUITE_BACKEND" ]] && terminer_backend "$FUITE_BACKEND" "menage (fuite)" >/dev/null 2>&1
  [[ -n "$TIERS_BACKEND" ]] && terminer_backend "$TIERS_BACKEND" "menage (tiers)" >/dev/null 2>&1
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
trap menage EXIT

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
APP_FUITE="esc-fuite-$JETON"
APP_TIERS="esc-tiers-$JETON"
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
  possede="$(lire_sql "select count(*) from pg_locks
     where locktype='advisory' and pid = $FUITE_BACKEND
       and classid = $CLE1 and objid = $CLE2 and objsubid = 2
       and database = (select oid from pg_database where datname = current_database())")"
  for _ in $(seq 1 300); do
    [[ "$possede" == "1" ]] && break
    sleep 0.1
    possede="$(lire_sql "select count(*) from pg_locks
       where locktype='advisory' and pid = $FUITE_BACKEND
         and classid = $CLE1 and objid = $CLE2 and objsubid = 2
         and database = (select oid from pg_database where datname = current_database())")"
  done
  if [[ "$possede" != "1" ]]; then
    echoue "C: le backend $FUITE_BACKEND ne detient pas le verrou attendu ($possede)"
  else
    ok "verrou injecte pose: backend $FUITE_BACKEND, cles ($CLE1,$CLE2), objsubid 2"

    # LA COMPARAISON DOIT RENDRE EXACTEMENT 10 — « verrou supplementaire ».
    # Ni 11, ni 12, ni 20/21: une panne d'observation ne doit pas etre lue
    # comme une fuite correctement detectee.
    comparer_verrous "C" "$VERROUS_AVANT_C" muet; rc=$?
    if (( rc == 10 )); then
      if [[ "$(grep -c . <<<"$CMP_APPARUS")" == "1" ]] \
         && grep -q "|$FUITE_BACKEND|$CLE1|$CLE2|2|" <<<"$CMP_APPARUS"; then
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
    if [[ -z "$TIERS_BACKEND" ]]; then
      echoue "C: la session tierce n'est jamais apparue — la survie n'est pas exercee"
    else
      ok "session tierce sur les MEMES cles: backend $TIERS_BACKEND"
      terminer_backend "$FUITE_BACKEND" "C" && FUITE_BACKEND=""
      vit="$(lire_sql "select count(*) from pg_stat_activity where pid = $TIERS_BACKEND")"
      if [[ "$vit" == ILLISIBLE* ]]; then
        echoue "C: impossible de verifier la survie du tiers — ${vit#*$'\t'}"
      elif [[ "$vit" == "1" ]]; then
        ok "la session tierce a SURVECU au nettoyage de C"
      else
        echoue "C: la session tierce a ete terminee — nettoyage par cles, pas par propriete"
      fi
      terminer_backend "$TIERS_BACKEND" "C (tiers)" && TIERS_BACKEND=""
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

echo
[[ $KO -eq 0 ]] \
  && echo "    La matrice rend un verdict, et le test prouve ce qu'il affirme." \
  || echo "    La matrice ne meurt pas proprement." >&2
exit $KO
