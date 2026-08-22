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

# LE CONTROLE DE TACHES N'EST PAS POSE GLOBALEMENT, ET C'EST DELIBERE.
#
# SIGINT est indispensable a I: bash met SIGINT a SIG_IGN dans un job
# d'arriere-plan lance depuis un shell NON INTERACTIF sans `set -m`, et UN
# SIG_IGN HERITE NE PEUT PAS ETRE TRAPPE. Mesure:
#
#     sans job control :  SIGINT -> code 0    (le trap n'a jamais tourne)
#     avec set -m      :  SIGINT -> code 130  trap INT
#
# MAIS `set -m` EN TETE DE SCRIPT CHANGE LA SEMANTIQUE DE TOUS LES SCENARIOS:
# chaque job d'arriere-plan obtient alors son PROPRE groupe de processus, donc
# ce que `groupe_vivant` et les terminaisons par groupe observent n'est plus le
# meme. Une passe verte sous cette semantique n'etablit pas que A-H, J et K
# tiennent sous la leur. Le mode monitor est donc confine au SEUL scenario I,
# dans un SOUS-SHELL dedie: il disparait a la mort de ce sous-shell, y compris
# sur erreur ou signal — ce qu'un « set -m ... set +m » ne garantit pas.

echo "    la matrice meurt proprement sur signal"
[[ -f "$MATRICE" ]] || { echoue "matrice introuvable: $MATRICE"; exit 2; }

# UN JETON PAR EXECUTION. Il nomme les connexions de ce test et lui seul: sans
# lui, deux executions concurrentes — ou une session tierce quelconque — ne
# seraient pas distinguables des siennes.
JETON="$$-${RANDOM}${RANDOM}"
TRACE=""; SORTIE=""; TEMOIN=""; TEMOIN_DESC=""; ESPACE_DEPOT=""; MPID=""

# ==========================================================================
# CANAUX DU WRAPPER — LE NOM DOIT ETRE LIBRE, ET C'EST UN CONTRAT
# ==========================================================================
# Le wrapper publie son marqueur par LIEN DUR: `ln` refuse une cible qui
# existe, ce qui rend la publication EXCLUSIVE et transforme une seconde
# emission en violation observable au lieu d'un ecrasement muet.
#
# LA CONTREPARTIE EST UNE OBLIGATION POUR L'APPELANT, ET ELLE N'ETAIT NULLE
# PART ECRITE. `mktemp` CREE le fichier. Tous les canaux de ce test etaient
# donc deja occupes avant meme le lancement, et depuis le passage de `mv -f` a
# `ln` la publication echouait SYSTEMATIQUEMENT. Mesure, scenario A sur un
# cluster propre: le harnais atteint sa porte en 11 s, le wrapper ecrit
# « DOUBLON_READY » dans `<canal>.doublon`, le marqueur reste VIDE, et le
# parent attend ses 300 s avant de conclure « delai depasse ». Le protocole
# etait correct; l'appelant violait son contrat.
#
# `mktemp -u` seul rendrait un nom libre mais NON RESERVE: un tiers peut le
# prendre entre-temps. UN SEUL repertoire prive en 0700, cree ici, lui rend
# cette garantie: a l'interieur, nous sommes le seul processus qui puisse
# creer quoi que ce soit, donc un nom libre le reste.
#
# LE REPERTOIRE EST CREE DANS CE PROCESSUS, PAS DANS `canal_neuf`. La fonction
# est appelee en substitution de commande — donc dans un SOUS-SHELL — et tout
# ce qu'elle affecterait (un tableau de repertoires a nettoyer, un compteur)
# mourrait avec lui. Elle ne fait donc que rendre un nom.
CANAUX_RACINE="$(mktemp -d)"
chmod 0700 "$CANAUX_RACINE"
canal_neuf() {   # canal_neuf <nom> -> chemin LIBRE dans notre repertoire prive
  mktemp -u -p "$CANAUX_RACINE" "${1:-canal}.XXXXXXXX"
}
FUITE_CLIENT=""; FUITE_BACKEND=""; TIERS_CLIENT=""; TIERS_BACKEND=""
M_CLIENT=""; M_BACKEND=""; M_APP=""; M_C1=0; M_C2=0; B0_DIAG=""
DORMEUR=""
CLE1=0; CLE2=0; APP_FUITE=""; APP_TIERS=""
FUITE_START=""; FUITE_DATID=""; FUITE_USER=""
TIERS_START=""; TIERS_DATID=""; TIERS_USER=""
ID_PID=""; ID_START=""; ID_DATID=""; ID_USER=""

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
# MANIFESTES DE PROPRIETE — CE QUI APPARTIENT A UN SCENARIO
# ==========================================================================
# DEUX LECTURES IDENTIQUES PROUVENT LA STABILITE, PAS LA PROPRIETE. Mesure
# contre f14401e: un backend enregistre, detenant reellement son verrou, avec
# deux empreintes strictement identiques — la baseline etait ACCEPTEE. Elle
# appartenait pourtant a un scenario anterieur.
#
# Chaque scenario declare donc ce qu'il cree, et B0 n'est capturee qu'apres
# avoir exige que plus rien de A-D ne subsiste. Le verrou legitime de `run.sh`,
# qui ne figure dans AUCUN manifeste, reste accepte dans B0 comme dans B1.
MANIFESTES="$(mktemp -d)"

# CES QUATRE PRIMITIVES SONT PRIVEES. Elles portent le prefixe `_` et la
# barriere structurelle `exiger_creation_centralisee()` refuse leur emploi hors
# des helpers `session_*`. Un scenario ne peut donc plus « enregistrer a la
# main » ce qu'il vient de creer: c'est precisement ce couplage lache qui a
# laisse les deux ShareLock de C entrer dans la baseline de E.
_manifeste_ouvrir() {   # _manifeste_ouvrir <scenario>
  [[ -f "$MANIFESTES/$1" ]] && return 0        # idempotent: deux backends, un manifeste
  { echo "FORMAT=esc-scenario-manifest/1"; echo "SCENARIO=$1"; echo "JETON=$JETON"
    echo "ETAT=PREPARE"; } >"$MANIFESTES/$1.tmp"
  mv -f "$MANIFESTES/$1.tmp" "$MANIFESTES/$1"
  chmod 0600 "$MANIFESTES/$1"
}
_manifeste_backend() {  # _manifeste_backend <scenario> <pid> <app>
  local id
  id="$(lire_sql "select pid||'|'||backend_start||'|'||datid||'|'||usename||'|'||application_name
                    from pg_stat_activity where pid = $2")"
  [[ "$id" == ILLISIBLE* ]] && return 1
  grep -qxF "BACKEND=$id" "$MANIFESTES/$1" || echo "BACKEND=$id" >>"$MANIFESTES/$1"
  return 0
}
_manifeste_verrou() {   # _manifeste_verrou <scenario> <cle1> <cle2>
  grep -qxF "VERROU=$2|$3" "$MANIFESTES/$1" || echo "VERROU=$2|$3" >>"$MANIFESTES/$1"
}
# `sed -i` REPUBLIE LE FICHIER: le mode est retabli explicitement, sinon un
# manifeste parfaitement forme serait ensuite refuse en PERMISSIONS_INVALIDES.
_manifeste_etat() {     # _manifeste_etat <scenario> <ancien> <nouveau>
  sed -i "s/^ETAT=$2\$/ETAT=$3/" "$MANIFESTES/$1"
  chmod 0600 "$MANIFESTES/$1"
  [[ "$(sed -n 's/^ETAT=//p' "$MANIFESTES/$1")" == "$3" ]]
}

# Refuse B0 si un scenario anterieur possede encore quoi que ce soit.
# Fail-closed: manifeste absent alors que le scenario a tourne, incomplet, mal
# forme, ou encore ACTIF -> refus.
b0_contaminee() {
  B0_DIAG=""
  local f scen etat ligne pid
  for f in "$MANIFESTES"/*; do
    [[ -f "$f" ]] || continue
    scen="$(basename "$f")"
    lire_canal "$f" "esc-scenario-manifest/1" "$scen" "$JETON" || {
      B0_DIAG="manifeste $scen invalide ($CANAL_ETAT: $CANAL_DIAG)"; return 0; }
    etat="$(sed -n 's/^ETAT=//p' "$f")"
    # PREPARE et ACTIF font refuser. NETTOYE n'est PAS cru sur parole: les
    # identites enregistrees sont revalidees ci-dessous quoi qu'il annonce.
    # C'est exactement ce que le scenario M etablit en falsifiant l'etat.
    case "$etat" in
      NETTOYE) : ;;
      *) B0_DIAG="scenario $scen encore $etat"; return 0 ;;
    esac
    while IFS= read -r ligne; do
      pid="${ligne%%|*}"
      pid_valide "$pid" || continue
      # L'IDENTITE ENREGISTREE EST REVALIDEE DANS L'ETAT REEL, pas seulement le
      # `application_name`: PID, backend_start, base, role et nom applicatif.
      local vu
      vu="$(lire_sql "select pid||'|'||backend_start||'|'||datid||'|'||usename||'|'||application_name
                        from pg_stat_activity where pid = $pid")"
      [[ "$vu" == ILLISIBLE* ]] && { B0_DIAG="pg_stat_activity illisible"; return 0; }
      [[ "$vu" == "$ligne" ]] && { B0_DIAG="$scen possede encore le backend $pid"; return 0; }
    done < <(sed -n 's/^BACKEND=//p' "$f")
    while IFS='|' read -r c1 c2; do
      [[ "$c1" =~ ^[0-9]+$ ]] || continue
      local n
      n="$(lire_sql "select count(*) from pg_locks
                      where locktype='advisory' and classid=$c1 and objid=$c2")"
      [[ "$n" == ILLISIBLE* ]] && { B0_DIAG="pg_locks illisible"; return 0; }
      [[ "$n" != "0" ]] && { B0_DIAG="$scen detient encore le verrou ($c1,$c2)"; return 0; }
    done < <(sed -n 's/^VERROU=//p' "$f")
  done
  return 1
}

# --------------------------------------------------------------------------
# LA CREATION ET L'ENREGISTREMENT SONT LA MEME OPERATION
# --------------------------------------------------------------------------
# « Cela tiendra pour un futur scenario O » n'etait vrai que si l'on pensait a
# appeler `manifeste_*` a la main. C et E creaient leurs sessions directement
# puis les enregistraient ensuite: le prochain scenario qui creerait un backend
# sans y penser reintroduirait exactement le defaut qui a laisse les ShareLock
# de C entrer dans le B0 de E.
#
# `session_creer()` est donc le SEUL chemin. Il declare l'intention AVANT la
# creation, publie l'identite exacte obtenue, et ne rend la main qu'apres un
# manifeste valide. Le cycle est explicite:
#
#     PREPARE  intention declaree, ressource peut-etre deja creee
#     ACTIF    identite exacte publiee et verifiee
#     NETTOYE  absence REELLE du backend ET du verrou revalidee
#
# Un arret en PREPARE ou en ACTIF fait refuser B0. Et `NETTOYE` n'est jamais
# cru sur parole: `b0_contaminee()` revalide l'absence quoi qu'annonce le
# manifeste.
SESSION_BACKEND=""; SESSION_CLIENT=""
SESSION_START=""; SESSION_DATID=""; SESSION_USER=""; SESSION_DIAG=""

# 1. L'INTENTION, AVANT QUE QUOI QUE CE SOIT N'EXISTE.
session_declarer() {   # session_declarer <scenario> <cle1> <cle2>
  _manifeste_ouvrir "$1"                      # ETAT=PREPARE
  _manifeste_verrou "$1" "$2" "$3"
}

# 2. L'IDENTITE EXACTE OBTENUE, ET LE MANIFESTE RELU AVANT DE RENDRE LA MAIN.
# `_manifeste_backend` seul ne prouve rien: il ecrit. On relit donc le document
# par le MEME lecteur que `b0_contaminee` — version, jeton, scenario, unicite
# des champs, permissions — et l'on exige que la ligne publiee soit exactement
# celle du backend annonce. Un manifeste ecrit mais illisible vaut echec.
session_publier() {   # session_publier <scenario> <app> <pid> <cle1> <cle2>
  local scen="$1" app="$2" pid="$3" c1="$4" c2="$5"
  SESSION_DIAG=""
  if ! detient_verrou "$pid" "$app" "$c1" "$c2" ShareLock; then
    SESSION_DIAG="le backend $pid ne detient pas ($c1,$c2) en ShareLock accorde"; return 1
  fi
  _manifeste_backend "$scen" "$pid" "$app" \
    || { SESSION_DIAG="identite du backend $pid illisible"; return 1; }
  # Idempotent: le second backend d'un meme scenario trouve deja ACTIF.
  _manifeste_etat "$scen" PREPARE ACTIF
  if ! lire_canal "$MANIFESTES/$scen" "esc-scenario-manifest/1" "$scen" "$JETON"; then
    SESSION_DIAG="manifeste invalide apres publication ($CANAL_ETAT: $CANAL_DIAG)"; return 1
  fi
  if ! grep -q "^BACKEND=$pid|" "$MANIFESTES/$scen"; then
    SESSION_DIAG="le manifeste ne porte pas le backend $pid"; return 1
  fi
  if ! enregistrer_identite "$app"; then
    SESSION_DIAG="identite de « $app » non unique ou illisible"; return 1
  fi
  SESSION_BACKEND="$pid"; SESSION_START="$ID_START"
  SESSION_DATID="$ID_DATID"; SESSION_USER="$ID_USER"
  return 0
}

# 3. LE CHEMIN DIRECT — declaration, creation, attente de DETENTION, publication.
# C'est le SEUL endroit du mode principal ou une session porteuse de verrou est
# ouverte; la barriere structurelle le verifie sur le texte du fichier.
session_creer() {   # session_creer <scenario> <app> <cle1> <cle2>
  local scen="$1" app="$2" c1="$3" c2="$4" pid=""
  SESSION_BACKEND=""; SESSION_CLIENT=""; SESSION_DIAG=""
  session_declarer "$scen" "$c1" "$c2"
  # ESC-CREATION-DIRECTE-DEBUT: chemin unique du mode principal
  PGAPPNAME="$app" psql -X -qtA -d postgres -c \
    "select pg_advisory_lock_shared($c1,$c2); select pg_sleep(300);" >/dev/null 2>&1 &
  # ESC-CREATION-DIRECTE-FIN
  SESSION_CLIENT=$!
  echo "CLIENT=$SESSION_CLIENT" >>"$MANIFESTES/$scen"
  for _ in $(seq 1 600); do
    pid="$(lire_sql "select pid from pg_stat_activity where application_name='$app'" | head -1)"
    if pid_valide "${pid:-x}" && session_publier "$scen" "$app" "$pid" "$c1" "$c2"; then
      return 0
    fi
    kill -0 "$SESSION_CLIENT" 2>/dev/null || break
    sleep 0.1
  done
  # ECHEC D'ENREGISTREMENT: nettoyage exact, puis refus. La ressource ne doit
  # pas survivre a l'impossibilite de la nommer. Le manifeste RESTE en PREPARE:
  # si le nettoyage lui-meme echouait, la baseline suivante refuserait.
  [[ -z "$SESSION_DIAG" ]] && SESSION_DIAG="le backend de « $app » n'a jamais detenu ($c1,$c2)"
  if pid_valide "${pid:-x}"; then
    terminer_possede "$pid" "$app" "$c1" "$c2" ShareLock "$scen (enregistrement echoue)" \
      >/dev/null 2>&1
  fi
  [[ -n "$SESSION_CLIENT" ]] && { kill "$SESSION_CLIENT" 2>/dev/null
                                  wait "$SESSION_CLIENT" 2>/dev/null; }
  SESSION_CLIENT=""; SESSION_BACKEND=""
  return 1
}

# 4. `NETTOYE` N'EST PUBLIE QU'APRES REVALIDATION DE L'ABSENCE REELLE — celle du
# backend ET celle du verrou. Un manifeste qui l'annonce sans cette preuve est
# exactement le contre-exemple du scenario M.
session_fermer() {   # session_fermer <scenario> <pid> <app> <cle1> <cle2>
  local scen="$1" pid="$2" app="$3" c1="$4" c2="$5" rc
  SESSION_DIAG=""
  terminer_possede "$pid" "$app" "$c1" "$c2" ShareLock "$scen"; rc=$?
  (( rc == 2 || rc == 3 )) && { SESSION_DIAG="terminaison refusee ou impossible (code $rc)"
                                return 1; }
  session_liberer "$scen" "$c1" "$c2"
}

# 5. LA LIBERATION SANS TERMINAISON — le sous-mode de E a nettoye lui-meme; le
# parent ne publie `NETTOYE` que s'il RECONSTATE l'absence de tout ce que son
# propre manifeste declare. Il ne croit ni le sous-mode ni son propre etat.
session_liberer() {   # session_liberer <scenario> <cle1> <cle2>
  local scen="$1" c1="$2" c2="$3" ligne pid vu
  SESSION_DIAG=""
  while IFS= read -r ligne; do
    pid="${ligne%%|*}"; pid_valide "$pid" || continue
    vu="$(lire_sql "select coalesce(string_agg(pid||'|'||backend_start||'|'||datid||'|'||usename||'|'||application_name,';'),'')
                      from pg_stat_activity where pid = $pid")"
    [[ "$vu" == ILLISIBLE* ]] && { SESSION_DIAG="pg_stat_activity illisible"; return 1; }
    [[ "$vu" == *"$ligne"* ]] && { SESSION_DIAG="le backend $pid est encore la"; return 1; }
  done < <(sed -n 's/^BACKEND=//p' "$MANIFESTES/$scen")
  vu="$(lire_sql "select count(*) from pg_locks
                   where locktype='advisory' and classid=$c1 and objid=$c2")"
  [[ "$vu" == ILLISIBLE* ]] && { SESSION_DIAG="pg_locks illisible"; return 1; }
  [[ "$vu" == "0" ]] || { SESSION_DIAG="$vu verrou(s) ($c1,$c2) subsistent"; return 1; }
  _manifeste_etat "$scen" ACTIF NETTOYE || { SESSION_DIAG="etat non publie"; return 1; }
  return 0
}

# --------------------------------------------------------------------------
# LA BARRIERE STRUCTURELLE — le helper n'est unique que si le texte l'impose
# --------------------------------------------------------------------------
# « Passer par un helper » n'est pas une propriete d'execution: c'est une
# propriete du FICHIER. Un futur scenario O qui ouvrirait sa propre session
# porteuse de verrou, ou qui appellerait les primitives de manifeste a la main,
# ne serait rattrape par aucun test d'execution — il produirait simplement une
# passe verte et une baseline contaminee, comme C l'a fait.
#
# On inspecte donc le script lui-meme. Toute acquisition directe doit etre
# encadree par les deux balises ci-dessous, et les primitives de manifeste ne
# peuvent apparaitre que dans leur propre definition ou dans un `session_*`.
#
# LES MOTIFS SONT ASSEMBLES A L'EXECUTION, et c'est necessaire: ecrits en clair,
# le programme `awk` se trouverait lui-meme. La balise ouvrante presente dans sa
# propre regle aurait mis l'inspecteur « en zone autorisee » des sa premiere
# ligne, et l'inspection entiere serait devenue silencieuse — un controle vert
# qui n'inspecte rien, exactement ce que ce fichier existe pour interdire.
exiger_creation_centralisee() {
  local f="${BASH_SOURCE[0]}" hors_zone="" hors_helper="" l
  local motif="pg_advisory""_lock" prefixe="_manifeste""_"
  local ouvre="ESC-CREATION-DIRECTE""-DEBUT" ferme="ESC-CREATION-DIRECTE""-FIN"
  # LES BALISES SONT APPARIEES ET BORNEES. Mesure faite sur un contre-exemple:
  # un scenario qui pose la seule balise OUVRANTE et ne la ferme jamais rendait
  # l'inspection MUETTE pour tout le reste du fichier. Une derogation qu'il
  # suffit d'ouvrir pour desactiver le controle n'est pas une derogation.
  # Une zone non fermee, une balise fermante orpheline, une imbrication ou une
  # zone de plus de dix lignes sont donc elles-memes des anomalies.
  hors_zone="$(awk -v m="$motif" -v o="$ouvre" -v c="$ferme" '
    index($0, o) {
      if (dedans) printf "ligne %d: balise ouvrante dans une zone deja ouverte (ligne %d)\n", FNR, debut
      dedans = 1; debut = FNR; next
    }
    index($0, c) {
      if (!dedans) printf "ligne %d: balise fermante sans ouvrante\n", FNR
      else if (FNR - debut > 10) printf "ligne %d: zone derogatoire de %d lignes, maximum 10\n", FNR, FNR - debut
      dedans = 0; next
    }
    index($0, m) && !dedans { printf "ligne %d: %s\n", FNR, $0 }
    END { if (dedans) printf "ligne %d: zone derogatoire ouverte et JAMAIS fermee\n", debut }
  ' "$f")"
  # LA PORTEE EST SUIVIE, PAS DEDUITE DE LA DERNIERE DEFINITION VUE. Sans la
  # remise a zero sur `}`, du code de PREMIER NIVEAU place apres la definition
  # d'un `session_*` aurait herite de son nom et serait passe — c'est-a-dire
  # exactement le cas a attraper: un scenario O qui enregistre a la main.
  hors_helper="$(awk -v p="$prefixe" '
    /^[A-Za-z_][A-Za-z_0-9]*\(\)/ {
      fonction = $0; sub(/\(\).*/, "", fonction)
      unligne = ($0 ~ /}[[:space:]]*$/)          # definition tenant sur une ligne
    }
    index($0, p) && $0 !~ /^[[:space:]]*#/ {
      if (fonction !~ /^session_/ && index(fonction, p) != 1)
        printf "ligne %d, dans %s: %s\n", FNR,
               (fonction == "" ? "le corps principal" : fonction "()"), $0
    }
    /^}/      { fonction = "" }
    unligne   { fonction = ""; unligne = 0 }
  ' "$f")"
  if [[ -n "$hors_zone" ]]; then
    echoue "acquisition de verrou hors du chemin unique de creation:"
    while IFS= read -r l; do detail "$l"; done <<<"$hors_zone"
  fi
  if [[ -n "$hors_helper" ]]; then
    echoue "primitive de manifeste appelee hors des helpers session_*:"
    while IFS= read -r l; do detail "$l"; done <<<"$hors_helper"
  fi
  [[ -z "$hors_zone" && -z "$hors_helper" ]]
}

# CONTRE-EXEMPLE DELIBERE, RESERVE AU SCENARIO M. Il publie `NETTOYE` SANS
# aucune preuve d'absence — c'est le mensonge que `b0_contaminee()` doit
# refuser. Son nom dit ce qu'il fait: aucun scenario ne peut l'employer pour
# « terminer » proprement.
session_falsifier_nettoye() { _manifeste_etat "$1" ACTIF NETTOYE; }

# ==========================================================================
# CANAUX — UNE SEULE LOGIQUE DE VALIDATION, CINQ ETATS DISTINCTS
# ==========================================================================
# DEUX PARSEURS DIVERGENTS, C'EST DEUX SEMANTIQUES. Le canal de resultat et le
# fichier `.erreurs` etaient lus de deux facons differentes, et tous deux
# convertissaient l'invalide en succes. Mesure contre f14401e:
#
#   .erreurs absent  -> erreurs=[]         indistinguable de « zero erreur »
#   resultat vide    -> WRAPPER_RC=[]      aucun diagnostic
#   resultat tronque -> WRAPPER_RC=[]      malforme lu comme correct
#   duplique         -> .doublon ecrit, JAMAIS LU: la violation est enregistree,
#                       la barriere n'existe pas
#   permissions      -> mode 644 jamais verifie
#
# UN FICHIER ABSENT OU VIDE NE VAUT JAMAIS ZERO. Zero doit etre PUBLIE, dans un
# document versionne qui porte son propre compteur.
#
#   CANAL_ETAT: ABSENT | VIDE_OU_NON_VERSIONNE | TRONQUE_OU_MALFORME
#             | DUPLIQUE | VALIDE
CANAL_ETAT=""; CANAL_DIAG=""; CANAL_COUNT=""
lire_canal() {   # lire_canal <fichier> <format> <scenario> <jeton> [champ-obligatoire...]
  local f="$1" fmt="$2" scen="$3" jet="$4"; shift 4
  CANAL_ETAT=""; CANAL_DIAG=""; CANAL_COUNT=""
  # LA DUPLICATION EST BLOQUANTE MEME SI LE PREMIER DOCUMENT EST VALIDE.
  if [[ -f "$f.doublon" ]]; then
    CANAL_ETAT=DUPLIQUE
    CANAL_DIAG="publication concurrente: $(head -1 "$f.doublon")"
    return 1
  fi
  [[ -e "$f" ]] || { CANAL_ETAT=ABSENT; CANAL_DIAG="aucun document publie"; return 1; }
  [[ -f "$f" ]] || { CANAL_ETAT=TRONQUE_OU_MALFORME
                     CANAL_DIAG="n'est pas un fichier regulier"; return 1; }
  # LES PERMISSIONS SONT UNE DIMENSION ORTHOGONALE AU CONTENU. Un document
  # parfaitement forme peut etre publie avec des droits dangereux: classer cela
  # « TRONQUE_OU_MALFORME » etait un diagnostic faux, qui aurait envoye vers une
  # erreur de syntaxe inexistante.
  local mode; mode="$(stat -c %a "$f" 2>/dev/null)"
  if [[ "$mode" != "600" ]]; then
    CANAL_ETAT=PERMISSIONS_INVALIDES
    CANAL_DIAG="attendu 0600, observe 0$mode"
    return 1
  fi
  [[ -s "$f" ]] || { CANAL_ETAT=VIDE_OU_NON_VERSIONNE; CANAL_DIAG="document vide"; return 1; }
  local vu_fmt; vu_fmt="$(grep -c '^FORMAT=' "$f")"
  if [[ "$vu_fmt" != "1" ]]; then
    CANAL_ETAT=VIDE_OU_NON_VERSIONNE
    CANAL_DIAG="FORMAT absent ou repete ($vu_fmt fois)"
    return 1
  fi
  [[ "$(sed -n 's/^FORMAT=//p' "$f")" == "$fmt" ]] \
    || { CANAL_ETAT=VIDE_OU_NON_VERSIONNE
         CANAL_DIAG="version observee « $(sed -n 's/^FORMAT=//p' "$f") », attendue « $fmt »"
         return 1; }
  local champ n
  for champ in SCENARIO JETON ETAT "$@"; do
    n="$(grep -c "^$champ=" "$f")"
    [[ "$n" == "1" ]] || { CANAL_ETAT=TRONQUE_OU_MALFORME
                           CANAL_DIAG="champ $champ present $n fois"; return 1; }
  done
  [[ "$(sed -n 's/^SCENARIO=//p' "$f")" == "$scen" ]] \
    || { CANAL_ETAT=TRONQUE_OU_MALFORME; CANAL_DIAG="scenario inattendu"; return 1; }
  [[ "$(sed -n 's/^JETON=//p' "$f")" == "$jet" ]] \
    || { CANAL_ETAT=TRONQUE_OU_MALFORME; CANAL_DIAG="jeton inattendu"; return 1; }
  if grep -q '^COUNT=' "$f"; then
    CANAL_COUNT="$(sed -n 's/^COUNT=//p' "$f")"
    [[ "$CANAL_COUNT" =~ ^[0-9]+$ ]] \
      || { CANAL_ETAT=TRONQUE_OU_MALFORME
           CANAL_DIAG="COUNT non numerique: « $CANAL_COUNT »"; return 1; }
  fi
  CANAL_ETAT=VALIDE
  return 0
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
  # LA DECISION VIENT D'UN SEUL INSTANTANE SQL. Lire la presence, puis decider
  # dans une seconde requete, laissait une course de CLASSIFICATION: entre les
  # deux, le backend peut disparaitre, la requete conditionnelle ne trouve plus
  # rien, et « deja disparu » etait alors annonce « identite non concordante ».
  # Ce n'est plus un risque de tuer le mauvais backend — c'est un faux rouge,
  # et un faux rouge sur un refus d'identite est exactement le diagnostic qu'on
  # ne veut pas voir se declencher a tort.
  res="$(lire_sql "with cible as (
             select a.pid, a.application_name, a.datname
               from pg_stat_activity a where a.pid = $pid
           ), verrou as (
             select l.pid from pg_locks l join cible c on c.pid = l.pid
              where c.application_name = '$app'
                and c.datname = current_database()
                and l.locktype = 'advisory'
                and l.classid = $c1 and l.objid = $c2 and l.objsubid = 2
                and l.granted and l.mode = '$mode'
                and l.database = (select oid from pg_database
                                   where datname = current_database())
           )
           select case
             when not exists (select 1 from cible)  then 'DISPARU'
             when not exists (select 1 from verrou) then 'REFUS_IDENTITE'
             when (select pg_terminate_backend(pid) from verrou) then 'TERMINE'
             else 'ECHEC_TERMINAISON' end")"
  [[ "$res" == ILLISIBLE* ]] && { echoue "$quoi: terminaison illisible — ${res#*$'\t'}"
                                  return 3; }
  case "$res" in
    DISPARU)           return 1 ;;
    REFUS_IDENTITE)    return 2 ;;
    TERMINE)           : ;;
    *) echoue "$quoi: terminaison rendue « $res »"; return 3 ;;
  esac
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

# `application_name` EST UN IDENTIFIANT DE CORRELATION, PAS UNE AUTORITE.
#
# J'avais remplace « nettoyage par cles » par « nettoyage par jeton ». Plus
# etroit — mais toujours pas une identite: `application_name` est une valeur
# CHOISIE PAR LE CLIENT. N'importe quelle session peut adopter le meme jeton,
# et un PID peut etre reattribue apres la mort de son porteur.
#
# On enregistre donc, A LA CREATION, l'identite exacte du backend: PID,
# `backend_start`, `datid`, `usename`, `application_name`. Le nettoyage
# revalide LES CINQ dans une seule requete avant de terminer. Le jeton sert a
# RETROUVER les lignes candidates; il n'est jamais le seul predicat.
#
# `backend_start` est le discriminant qui compte: il separe un PID reutilise
# d'un PID d'origine, et un usurpateur du porteur legitime.
enregistrer_identite() {   # enregistrer_identite <app> -> ID_PID ID_START ID_DATID ID_USER
  local app="$1" ligne
  ID_PID=""; ID_START=""; ID_DATID=""; ID_USER=""
  ligne="$(lire_sql "select pid||'|'||backend_start||'|'||datid||'|'||usename
                       from pg_stat_activity
                      where application_name = '$app' and datname = current_database()")"
  [[ "$ligne" == ILLISIBLE* ]] && { CMP_DIAG="${ligne#*$'\t'}"; return 3; }
  [[ "$(grep -c . <<<"$ligne")" == "1" ]] || return 1
  IFS='|' read -r ID_PID ID_START ID_DATID ID_USER <<<"$ligne"
  pid_valide "${ID_PID:-x}" || return 1
  return 0
}

# Machine d'etat sur UN SEUL instantane, et sur l'identite COMPLETE.
#   0 TERMINE   1 DISPARU   2 REFUS_IDENTITE   3 ECHEC/ILLISIBLE
terminer_identite() {   # <pid> <start> <datid> <user> <app> <libelle>
  local pid="$1" start="$2" datid="$3" user="$4" app="$5" quoi="$6" res n=0 vu
  [[ -z "$pid" ]] && return 1
  pid_valide "$pid" || { echoue "$quoi: PID non numerique: « $pid »"; return 3; }
  res="$(lire_sql "with cible as (
             select pid from pg_stat_activity
              where pid = $pid
                and backend_start = '$start'::timestamptz
                and datid = $datid
                and usename = '$user'
                and application_name = '$app'
                and datname = current_database()
           ), present as (select 1 from pg_stat_activity where pid = $pid)
           select case
             when not exists (select 1 from present) then 'DISPARU'
             when not exists (select 1 from cible)   then 'REFUS_IDENTITE'
             when (select pg_terminate_backend(pid) from cible) then 'TERMINE'
             else 'ECHEC_TERMINAISON' end")"
  [[ "$res" == ILLISIBLE* ]] && { echoue "$quoi: terminaison illisible — ${res#*$'\t'}"
                                  return 3; }
  case "$res" in
    DISPARU)        return 1 ;;
    REFUS_IDENTITE) return 2 ;;
    TERMINE)        : ;;
    *) echoue "$quoi: terminaison rendue « $res »"; return 3 ;;
  esac
  while (( n++ < 150 )); do
    vu="$(lire_sql "select count(*) from pg_stat_activity where pid = $pid")"
    [[ "$vu" == ILLISIBLE* ]] && { echoue "$quoi: attente illisible"; return 3; }
    [[ "$vu" == "0" ]] && return 0
    sleep 0.1
  done
  echoue "$quoi: le backend $pid n'a pas disparu"; return 3
}

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
  if [[ -n "$FUITE_BACKEND" && -n "$FUITE_START" ]]; then
    terminer_identite "$FUITE_BACKEND" "$FUITE_START" "$FUITE_DATID" "$FUITE_USER" \
                      "$APP_FUITE" "menage (fuite)"
    rc=$?; (( rc == 2 || rc == 3 )) \
      && nettoyage_echoue "backend de C ($FUITE_BACKEND) non nettoye (code $rc)"
  fi
  if [[ -n "$TIERS_BACKEND" && -n "$TIERS_START" ]]; then
    terminer_identite "$TIERS_BACKEND" "$TIERS_START" "$TIERS_DATID" "$TIERS_USER" \
                      "$APP_TIERS" "menage (tiers)"
    rc=$?; (( rc == 2 || rc == 3 )) \
      && nettoyage_echoue "backend tiers ($TIERS_BACKEND) non nettoye (code $rc)"
  fi
  # LE TEMOIN DE M AUSSI. Il etait absent de ce nettoyage: interrompu pendant M,
  # le test laissait derriere lui un backend detenant (778899,112233) jusqu'a
  # l'expiration de son `pg_sleep`. Meme fonction, meme exigence d'identite.
  if [[ -n "$M_BACKEND" ]]; then
    terminer_possede "$M_BACKEND" "$M_APP" "$M_C1" "$M_C2" ShareLock "menage (temoin M)"
    rc=$?; (( rc == 2 || rc == 3 )) \
      && nettoyage_echoue "temoin de M ($M_BACKEND) non nettoye (code $rc)"
  fi
  if (( M_C1 != 0 )); then
    local resteM
    resteM="$(lire_sql "select count(*) from pg_locks
                         where locktype='advisory' and classid=$M_C1 and objid=$M_C2")"
    if [[ "$resteM" == ILLISIBLE* ]]; then
      nettoyage_echoue "verrou de M: lecture impossible — ${resteM#*$'\t'}"
    elif [[ "$resteM" != "0" ]]; then
      nettoyage_echoue "$resteM verrou(s) des cles de M ($M_C1,$M_C2) subsistent"
    fi
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
  # LE DORMEUR DU SOUS-MODE EST TUE ET MOISSONNE. `wait` rend la main des
  # que la trap s'execute, l'enfant TOUJOURS VIVANT: sans cela le `sleep`
  # survivait au sous-mode en orphelin.
  for c in "$FUITE_CLIENT" "$TIERS_CLIENT" "$M_CLIENT" "$DORMEUR"; do
    [[ -n "$c" ]] && { kill "$c" 2>/dev/null; wait "$c" 2>/dev/null; }
  done
  if [[ -n "$ESPACE_DEPOT" && -d "$ESPACE_DEPOT" ]]; then
    git -C "$RACINE" worktree remove --force "$ESPACE_DEPOT" 2>/dev/null
    rm -rf "$ESPACE_DEPOT"
    git -C "$RACINE" worktree prune 2>/dev/null
  fi
  rm -rf "$MANIFESTES"
  rm -f "$TRACE" "$SORTIE" "$TEMOIN" "$TEMOIN_DESC"
  # LE REPERTOIRE PRIVE DES CANAUX, ET LUI SEUL. Son chemin vient du `mktemp -d`
  # de CE processus: aucun nettoyage par motif, rien qui puisse viser autre
  # chose. Il emporte marqueurs, `.doublon` et `.terminal` d'un seul coup.
  [[ -n "${CANAUX_RACINE:-}" && -d "$CANAUX_RACINE" ]] && rm -rf "$CANAUX_RACINE"
  return 0
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
    # SANS EXCEPTION. La regle « si le code initial vaut zero » laissait un
    # nettoyage rouge pendant un SIGTERM conserver 143: l'appelant ne pouvait
    # plus distinguer « signal correctement nettoye » de « signal suivi d'un
    # nettoyage incomplet ». Le code initial est journalise, pas conserve.
    echo "    NETTOYAGE ROUGE — code initial $code, remplace par 9." >&2
    code=9
  fi
  exit "$code"
}
trap 'sortir $KO' EXIT
# Un signal doit passer par le meme chemin: sans trap TERM, bash meurt sans
# executer le trap EXIT, et rien n'est nettoye. LES DEUX SIGNAUX N'ONT PAS LE
# MEME CODE: SIGTERM vaut 15 donc 143, SIGINT vaut 2 donc 130. Les confondre
# annoncait un code qui n'etait pas celui du signal recu.
trap 'sortir 143' TERM
trap 'sortir 130' INT

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

# LE MARQUEUR EST UN PROTOCOLE VERSIONNE, LU STRICTEMENT. Tout champ absent,
# inconnu, duplique, non numerique, ou un etat hors des deux valeurs definies,
# produit un refus fail-closed. Un marqueur portant a la fois READY et FAILED
# est impossible par construction — `STATE` est unique — et un doublon est
# refuse.
MK_FORMAT=""; MK_STATE=""; MK_WRAP=""; MK_HARN=""; MK_WIT=""; MK_PGID=""; MK_DIAG=""
lire_marqueur() {
  local f="$1" k v dup
  MK_FORMAT=""; MK_STATE=""; MK_WRAP=""; MK_HARN=""; MK_WIT=""; MK_PGID=""; MK_DIAG=""
  MK_SCEN=""; MK_JETON=""; MK_WPGID=""; MK_HPGID=""; MK_TPGID=""; MK_GATE=""; MK_GATE_DIAG=""
  [[ -s "$f" ]] || { MK_DIAG="marqueur vide ou absent"; return 1; }
  dup="$(cut -d= -f1 "$f" | sort | uniq -d | tr '\n' ' ')"
  [[ -z "${dup// /}" ]] || { MK_DIAG="champ(s) duplique(s): $dup"; return 1; }
  while IFS='=' read -r k v; do
    case "$k" in
      FORMAT) MK_FORMAT="$v" ;;      STATE) MK_STATE="$v" ;;
      WRAPPER_PID) MK_WRAP="$v" ;;   HARNESS_PID) MK_HARN="$v" ;;
      WITNESS_PID) MK_WIT="$v" ;;    PGID) MK_PGID="$v" ;;
      SCENARIO) MK_SCEN="$v" ;;      TOKEN) MK_JETON="$v" ;;
      WRAPPER_PGID) MK_WPGID="$v" ;; HARNESS_PGID) MK_HPGID="$v" ;;
      WITNESS_PGID) MK_TPGID="$v" ;; HARNESS_GATE_STATE) MK_GATE="$v" ;;
      GATE) MK_GATE_DIAG="$v" ;;
      *) MK_DIAG="champ inconnu: ${k:-<vide>}"; return 1 ;;
    esac
  done < "$f"
  # LA VERSION EST EXIGEE, ET C'EST TOUT LE POINT DU PASSAGE EN /2. Le format /1
  # ne certifiait qu'une PHOTOGRAPHIE: trois processus vivants a l'instant de la
  # publication, sans aucune garantie de duree. Le /2 n'est publie qu'apres
  # preuve que le harnais est BLOQUE sur une porte que seul le signal ouvre.
  # Reutiliser /1 avec cette nouvelle semantique aurait rendu les deux
  # indistinguables — un lecteur ne saurait plus ce que « READY » lui promet.
  [[ "$MK_FORMAT" == "esc-mutation-marker/2" ]] \
    || { MK_DIAG="version inconnue: ${MK_FORMAT:-<absente>}"; return 1; }
  case "$MK_STATE" in READY|FAILED) : ;;
    *) MK_DIAG="etat invalide: ${MK_STATE:-<absent>}"; return 1 ;; esac
  # L'INVARIANT EST CONDITIONNEL, ET IL LE DOIT. « READY implique GATE_ARMED »
  # est la promesse du /2; « tout marqueur porte GATE_ARMED » n'en est pas une
  # et serait FAUSSE par construction: un wrapper qui constate que le harnais
  # a fini avant d'armer publie precisement FAILED sans etat de porte, et c'est
  # le comportement CORRECT — c'est meme ce que le scenario J exerce, avec un
  # harnais dont le seul travail est de sortir tout de suite.
  #
  # L'exigence inconditionnelle rendait donc rouge un refus conforme. Mesure:
  # « J: marqueur refuse: HARNESS_GATE_STATE=<absent> » sur un marqueur FAILED
  # parfaitement regulier.
  if [[ "$MK_STATE" == READY && "$MK_GATE" != GATE_ARMED ]]; then
    MK_DIAG="READY sans preuve de porte: HARNESS_GATE_STATE=${MK_GATE:-<absent>}"
    return 1
  fi
  for v in "$MK_WRAP" "$MK_HARN" "$MK_WIT" "$MK_PGID"; do
    pid_valide "${v:-x}" || { MK_DIAG="PID/PGID non numerique: ${v:-<absent>}"; return 1; }
  done
  [[ "$MK_WRAP" != "$MK_HARN" && "$MK_HARN" != "$MK_WIT" && "$MK_WRAP" != "$MK_WIT" ]] \
    || { MK_DIAG="PID non distincts: $MK_WRAP/$MK_HARN/$MK_WIT"; return 1; }
  return 0
}

# UNE ATTENTE QUI NE PEUT PAS CONCLURE TOT SUR UNE CAUSE CONNUE TRANSFORME UN
# DIAGNOSTIC EN DELAI. Le quatrieme parametre, optionnel, nomme une condition
# d'ABANDON: quand elle devient vraie, l'attente s'arrete immediatement et dit
# POURQUOI. Mesure de ce que coutait son absence: la publication du marqueur
# etait refusee des la premiere seconde — le canal existait deja — et le test
# attendait quand meme ses 300 secondes avant de rendre « delai depasse »,
# c'est-a-dire le seul message qui ne designe pas la cause.
attendre() {   # attendre <description> <commande-test> <deciseconds> [<abandon> <raison>]
  local quoi="$1" test="$2" max="$3" abandon="${4:-}" raison="${5:-}" n=0
  while ! eval "$test"; do
    kill -0 "$MPID" 2>/dev/null || { echoue "la matrice est morte avant: $quoi"
                                     detail "$(head -3 "$SORTIE")"; return 1; }
    if [[ -n "$abandon" ]] && eval "$abandon"; then
      echoue "abandon en attendant $quoi: ${raison:-cause non nommee}"
      return 1
    fi
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
  # PRISE DE TEST: les connexions s'ouvrent mais NE PRENNENT AUCUN VERROU. Les
  # PID seront numeriques et presents — exactement le cas ou l'ancienne boucle
  # publiait `READY` a tort.
  # LE SOUS-MODE N'EST PAS LE PROPRIETAIRE ENREGISTRE, ET C'EST TOUT LE SUJET.
  # Il est tue au moment precis ou il detient ses verrous; son propre registre
  # meurt avec lui. C'est le PARENT qui declare l'intention avant de le lancer
  # (`session_declarer`) puis publie les identites exactes rendues par le temoin
  # (`session_publier`). L'exception est donc bornee au bloc balise ci-dessous,
  # et la propriete « une ressource creee est une ressource enregistree » reste
  # vraie du cote ou elle doit l'etre: celui qui survit pour la nettoyer.
  # ESC-CREATION-DIRECTE-DEBUT
  SQL_VERROU="select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(300);"
  [[ -n "${ESC_ACQUISITION_IMPOSSIBLE:-}" ]] && SQL_VERROU="select pg_sleep(300);"
  PGAPPNAME="$APP_FUITE" psql -X -qtA -d postgres -c "$SQL_VERROU" >/dev/null 2>&1 &
  FUITE_CLIENT=$!
  PGAPPNAME="$APP_TIERS" psql -X -qtA -d postgres -c "$SQL_VERROU" >/dev/null 2>&1 &
  TIERS_CLIENT=$!
  # ESC-CREATION-DIRECTE-FIN
  # `READY` N'EST PUBLIE QUE SUR PREUVE, JAMAIS PAR ARRIVEE EN FIN DE BOUCLE.
  # La version precedente ecrivait le temoin apres 600 passages QUELS QUE
  # SOIENT les resultats: deux PID numeriques suffisaient, sans qu'aucun verrou
  # ait ete acquis. Le parent annoncait alors « sous-mode pret », signalait, et
  # constatait zero verrou residuel — un scenario vert qui n'avait rien exerce.
  # LE SOUS-MODE ENREGISTRE L'IDENTITE COMPLETE DE CE QU'IL CREE, et pas
  # seulement le PID. Sans `backend_start`, `datid` et `usename`, son propre
  # `menage()` sautait `terminer_identite` — il ne pouvait donc PAS nettoyer
  # ses backends, et laissait ses deux ShareLock derriere lui.
  #
  # Ce defaut etait invisible tant que la trap arrivait 300 secondes trop tard:
  # a cet instant les `pg_sleep(300)` avaient expire d'eux-memes, les verrous
  # etaient retombes seuls, et E annoncait « le trap doit tout rendre » alors
  # que le trap n'avait rien rendu du tout. Corriger le retard de la trap a
  # rendu la mesure possible: E, puis I, sont passes au rouge avec deux
  # backends survivants et deux verrous subsistants.
  PRET=0
  for _ in $(seq 1 600); do
    if enregistrer_identite "$APP_FUITE"; then
      FUITE_BACKEND="$ID_PID"; FUITE_START="$ID_START"
      FUITE_DATID="$ID_DATID"; FUITE_USER="$ID_USER"
    fi
    if enregistrer_identite "$APP_TIERS"; then
      TIERS_BACKEND="$ID_PID"; TIERS_START="$ID_START"
      TIERS_DATID="$ID_DATID"; TIERS_USER="$ID_USER"
    fi
    if pid_valide "${FUITE_BACKEND:-x}" && pid_valide "${TIERS_BACKEND:-x}" \
       && [[ -n "$FUITE_START" && -n "$TIERS_START" ]] \
       && [[ "$FUITE_BACKEND" != "$TIERS_BACKEND" ]] \
       && detient_verrou "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock \
       && detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock; then
      PRET=1; break
    fi
    sleep 0.1
  done
  if (( PRET != 1 )); then
    { echo "FAILED"
      echo "diag=acquisition non prouvee: fuite[$FUITE_BACKEND] tiers[$TIERS_BACKEND]"
    } >"${ESC_SIGNAL_TEMOIN:?}"
    sortir 4
  fi
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
  # Prise: le nettoyage du sous-mode sera rendu impossible AU MOMENT du signal.
  # Le code doit alors passer de 143 a 9, et non rester 143.
  [[ -n "${ESC_NETTOYAGE_CASSE_APRES:-}" ]] && export ESC_SQL_ILLISIBLE=1
  # UN `sleep` DE PREMIER PLAN DIFFERE LA TRAP. Bash n'execute pas de
  # gestionnaire tant qu'il attend une commande externe de premier plan.
  # Mesure, hors harnais, meme signal et meme code de sortie:
  #
  #     sleep 30              -> trap executee apres 30 s, code 143
  #     sleep 30 & wait $!    -> trap executee apres  0 s, code 143
  #
  # Le sous-mode recevait donc son SIGTERM et ne nettoyait que 300 secondes
  # plus tard. Les assertions restaient vraies — les verrous etaient encore
  # tenus — mais « le parent le signale a cet instant precis » decrivait
  # l'ENVOI du signal, jamais le moment du nettoyage; et E, H et I coutaient
  # cinq minutes chacun. `wait` est un builtin: la trap s'execute aussitot.
  sleep 300 & DORMEUR=$!
  wait "$DORMEUR"
  sortir 0
fi

# SOUS-MODE — LE NETTOYAGE ECHOUE, ET LE CODE DOIT LE DIRE
if [[ "${ESC_SIGNAL_SOUS_MODE:-}" == "nettoyage_casse" ]]; then
  CLE1="${ESC_SIGNAL_CLE1:?}"; CLE2="${ESC_SIGNAL_CLE2:?}"
  APP_FUITE="esc-fuite-$JETON"
  # ESC-CREATION-DIRECTE-DEBUT: sous-mode, meme raison que ci-dessus
  PGAPPNAME="$APP_FUITE" psql -X -qtA -d postgres -c \
    "select pg_advisory_lock_shared($CLE1,$CLE2); select pg_sleep(300);" >/dev/null 2>&1 &
  # ESC-CREATION-DIRECTE-FIN
  FUITE_CLIENT=$!
  PRET=0
  for _ in $(seq 1 600); do
    if enregistrer_identite "$APP_FUITE"; then
      FUITE_BACKEND="$ID_PID"; FUITE_START="$ID_START"
      FUITE_DATID="$ID_DATID"; FUITE_USER="$ID_USER"
    fi
    if pid_valide "${FUITE_BACKEND:-x}" && [[ -n "$FUITE_START" ]] \
       && detient_verrou "$FUITE_BACKEND" "$APP_FUITE" "$CLE1" "$CLE2" ShareLock; then
      PRET=1; break
    fi
    sleep 0.1
  done
  if (( PRET != 1 )); then
    { echo "FAILED"; echo "diag=acquisition non prouvee: [$FUITE_BACKEND]"; } \
      >"${ESC_SIGNAL_TEMOIN:?}"
    sortir 4
  fi
  { echo "FUITE_BACKEND=$FUITE_BACKEND"; echo "APP_FUITE=$APP_FUITE"; echo "READY"; } \
    >"${ESC_SIGNAL_TEMOIN:?}"
  # A partir d'ici le nettoyage ne pourra RIEN lire. Il doit rougir, et le code
  # de sortie doit passer de 0 a 9 — jamais rester 0.
  export ESC_SQL_ILLISIBLE=1
  sortir 0
fi

# ==========================================================================
# BARRIERE STRUCTURELLE — avant tout scenario, et hors des sous-modes
# ==========================================================================
# Elle ne mesure rien a l'execution: elle lit le fichier. C'est voulu. Aucune
# passe verte n'aurait revele qu'un futur scenario ouvre sa propre session
# porteuse de verrou sans l'enregistrer — le defaut ne se manifeste que plus
# tard, dans la baseline d'un AUTRE scenario, et sous forme d'un vert.
echo "      -- barriere: la creation de ressources est-elle centralisee ?"
if exiger_creation_centralisee; then
  ok "toute acquisition de verrou passe par session_creer, hors zones balisees"
  ok "les primitives de manifeste ne sont appelees que par les helpers session_*"
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

TEMOIN_DESC="$(canal_neuf temoin-A)"
# LES CANAUX DU WRAPPER SONT DESORMAIS ARMES EN PERMANENCE DANS A. Ils
# existaient et n'etaient poses que par `lancer_L`: le scenario A n'avait donc
# ni journal de `wait`, ni marqueurs causaux, ni resultat. Quand il a rougi en
# CI, il etait impossible de savoir si le harnais avait fini normalement ou
# avait ete tue — le trou d'observation etait dans le scenario, pas dans l'outil.
A_JETON="A-$JETON"
A_MARQ="$(mktemp -d)"; A_JOUR="$(mktemp)"; A_RESULTAT="$(mktemp -u)"
lancer_matrice W1 "ESC_MUTATION_TEMOIN=$TEMOIN_DESC" \
  "ESC_MUTATION_JETON=$A_JETON" "ESC_SCENARIO=A" \
  "ESC_MARQUEURS=$A_MARQ" "ESC_JOURNAL=$A_JOUR" "ESC_MUTATION_RESULTAT=$A_RESULTAT"
attendre "la mutation posee" '[[ -s "$TRACE" ]]' 3000 || exit 1
IFS=$'\t' read -r CAS_NOM CAS_FIC CAS_SOMME _ESPACE ESPACE_DEPOT <"$TRACE"
ok "mutation posee: $CAS_NOM sur $CAS_FIC"

AVANT="$(sha256sum "$PROJET/$CAS_FIC" | cut -d' ' -f1)"
[[ "$AVANT" != "$CAS_SOMME" ]] \
  && ok "le depot principal differe deja de la version mutee (attendu)" \
  || echoue "le depot principal porte l'empreinte MUTEE: l'isolation a cede"

# LE PID DU HARNAIS EST LU DANS LE MARQUEUR, PAS DECOUVERT PAR UNE COURSE.
# `pgrep -P "$MPID"` ne peut rien trouver des que le harnais a fini — et le
# temoin, qui retenait alors les pipes du `Popen`, faisait durer cette attente
# ses 300 secondes entieres. Le wrapper publie desormais les trois PID.
attendre "le marqueur du wrapper (READY)" '[[ -s "$TEMOIN_DESC" ]]' 3000 \
  '[[ -f "$TEMOIN_DESC.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
if ! lire_marqueur "$TEMOIN_DESC"; then
  echoue "marqueur du wrapper refuse: $MK_DIAG"; exit 1
fi
if [[ "$MK_STATE" != READY ]]; then
  echoue "le wrapper a publie $MK_STATE — scenario non exerce"; exit 1
fi
WRAP_PID="$MK_WRAP"; BASH_PID="$MK_HARN"; TEMOIN_PID="$MK_WIT"
ok "marqueur $MK_FORMAT, etat READY: wrapper $WRAP_PID, harnais $BASH_PID, temoin $TEMOIN_PID, PGID $MK_PGID"
# SECONDE BARRIERE, COTE CONSOMMATEUR. Le producteur a deja verifie; le parent
# refait les memes controles sur l'etat courant, avant d'envoyer le signal.
[[ "$MK_PGID" == "$WRAP_PID" ]] \
  && ok "le PGID publie est bien celui du wrapper" \
  || echoue "PGID publie $MK_PGID, wrapper $WRAP_PID"
[[ "$MK_SCEN" == "A" && "$MK_JETON" == "$A_JETON" ]] \
  && ok "marqueur du bon scenario et du bon jeton" \
  || echoue "READY_MALFORME: scenario « $MK_SCEN », jeton « $MK_JETON »"

# LA PREUVE DE BLOCAGE, LUE A LA SOURCE ET NON DEDUITE DU MARQUEUR. Le wrapper
# affirme `HARNESS_GATE_STATE=BLOCKED`; le parent relit le document que le
# HARNAIS a publie lui-meme, et compare les identites.
# Le document BLOCKED est publie par le HARNAIS dans le repertoire prive du
# wrapper, que celui-ci detruit en sortant. C'est le wrapper qui en fait la
# verification forte — PID, PGID, jeton et STATE compares un a un AVANT de
# publier READY — et qui en recopie le resultat dans le marqueur. Le parent
# revalide ici ce qui lui est accessible: l'etat de la porte et le PGID declare.
if [[ "$MK_GATE" != GATE_ARMED ]]; then
  echoue "HARNESS_BLOCKED_ABSENT: le wrapper a publie READY sans preuve de blocage"
  exit 1
fi
[[ "$MK_HPGID" == "$WRAP_PID" ]] \
  && ok "porte: le harnais bloque declare le PGID du wrapper" \
  || echoue "HARNESS_BLOCKED_IDENTITE_INVALIDE: PGID declare « $MK_HPGID »"
# LE HARNAIS DOIT ETRE ENCORE VIVANT. S'il a fini avant le signal, le scenario
# n'exerce rien — et c'est exactement ce que le defaut precedent masquait
# derriere une attente de 300 s.
if [[ -z "$(vivants "$BASH_PID")" ]]; then
  echoue "harnais termine avant le signal — scenario non exerce"
  exit 1
fi
CMDLINE="$(ps -o args= -p "$BASH_PID" 2>/dev/null)"
HARNAIS_NOM="$(awk '{print $2}' <<<"$CMDLINE")"
HARNAIS_PREFIXE="$(awk '{print $3}' <<<"$CMDLINE")"
ok "harnais « $HARNAIS_NOM $HARNAIS_PREFIXE » (PID $BASH_PID)"

# LA VERIFICATION STRUCTURELLE, ET C'EST ELLE QUI PORTE. Le harnais doit MENER
# SON PROPRE GROUPE: sans cela, « terminer tout ce que ce harnais a engendre »
# ne peut meme pas s'exprimer — on ne saurait pas quoi viser.
PGID_HARNAIS="$(ps -o pgid= -p "$BASH_PID" 2>/dev/null | tr -d ' ')"
PGID_TEMOIN2="$(ps -o pgid= -p "$TEMOIN_PID" 2>/dev/null | tr -d ' ')"
if [[ "$PGID_HARNAIS" == "$WRAP_PID" && "$PGID_TEMOIN2" == "$WRAP_PID" ]]; then
  ok "harnais et temoin sont dans le groupe du wrapper (PGID $WRAP_PID)"
else
  # NOMMER LA PERTE DE VIVACITE. Avec la porte, harnais et temoin ne PEUVENT
  # plus disparaitre avant le signal: si l'un manque, ce n'est plus une course
  # perdue mais une violation, et le diagnostic doit dire laquelle.
  if [[ -z "$PGID_HARNAIS" ]]; then
    echoue "LEASE_LOST_AFTER_READY: le harnais $BASH_PID a disparu apres READY"
  elif [[ -z "$PGID_TEMOIN2" ]]; then
    echoue "WITNESS_LOST_AFTER_READY: le temoin $TEMOIN_PID a disparu apres READY"
  else
    echoue "groupes incoherents: harnais[$PGID_HARNAIS] temoin[$PGID_TEMOIN2] wrapper[$WRAP_PID]"
  fi
  [[ -f "$TEMOIN_DESC.terminal" ]] && detail "terminal: $(tr '\n' ' ' <"$TEMOIN_DESC.terminal")"
fi

# LE TEMOIN, PAS UN `psql` DE PASSAGE. Attendre un descendant naturel ne
# marchait que par accident: `harnais_verrou_prendre()` ouvre un `coproc psql`
# de longue duree en execution AUTONOME, mais retourne sans coproc sous
# `run.sh`, ou le marqueur de reentrance dispense de prendre le verrou. Mesure:
# le test etait vert seul et rouge imbrique — « aucun descendant vivant observe
# en 60 s » — dans les DEUX modes de connexion, sans que la propriete testee
# ait change. Un descendant explicite, qui annonce lui-meme sa disponibilite,
# ne depend d'aucun ordonnancement.
# Il doit VRAIMENT etre dans le groupe du harnais — sinon le terminer par
# groupe ne prouverait rien de la descendance du harnais.
PETITS="$(vivants "$TEMOIN_PID $(descendants "$BASH_PID" | tr '\n' ' ')")"
[[ -n "$(vivants "$TEMOIN_PID")" ]] \
  && ok "descendance vivante a l'instant du signal: $PETITS" \
  || { echoue "WITNESS_LOST_AFTER_READY: le temoin $TEMOIN_PID n'est plus vivant avant le signal"
       [[ -f "$TEMOIN_DESC.terminal" ]] && detail "terminal: $(tr '\n' ' ' <"$TEMOIN_DESC.terminal")"
       exit 1; }

# ==========================================================================
# NON VACUITE DU DECOR — « zero residu » sur une scene vide n'est pas un succes
# ==========================================================================
# Le controle de residu, plus bas, exige qu'aucun role et aucune base au
# prefixe du harnais ne subsiste apres le signal. Cette exigence etait
# SATISFAITE PAR CONSTRUCTION si le harnais n'avait rien cree: un decor qui
# n'existe pas ne laisse pas de residu. La propriete voulue n'est pas
# « l'ensemble final est vide » mais « un ensemble NON VIDE a ete detruit ».
#
# La porte de vivacite rend cette photographie sure: elle est armee APRES
# `decor_poser i`, donc au moment ou nous lisons, le decor EXISTE forcement si
# le harnais s'est comporte comme annonce. Si la lecture le trouve vide, ce
# n'est plus une course perdue — c'est que la garantie de cleanup ne portait
# sur rien.
#
# Les NOMS sont retenus, pas seulement un compte: apres le signal on exige la
# disparition de CES objets-la, nommement. Un residu remplace par un homonyme
# cree entre-temps ne passerait pas pour un nettoyage.
DECOR_ROLES_AVANT="$(lire_sql "select coalesce(string_agg(rolname,',' order by rolname),'')
                                 from pg_roles
                                where rolname like '${HARNAIS_PREFIXE}\\_%'")"
DECOR_BASES_AVANT="$(lire_sql "select coalesce(string_agg(datname,',' order by datname),'')
                                 from pg_database
                                where datname like '${HARNAIS_PREFIXE}\\_%'")"
if [[ "$DECOR_ROLES_AVANT" == ILLISIBLE* || "$DECOR_BASES_AVANT" == ILLISIBLE* ]]; then
  echoue "NON VACUITE: impossible de photographier le decor avant le signal"
  detail "roles: ${DECOR_ROLES_AVANT#*$'\t'} | bases: ${DECOR_BASES_AVANT#*$'\t'}"
  exit 1
fi
if [[ -z "$DECOR_ROLES_AVANT" || -z "$DECOR_BASES_AVANT" ]]; then
  echoue "DECOR_ABSENT: le harnais a arme sa porte sans avoir pose de decor"
  detail "roles[$DECOR_ROLES_AVANT] bases[$DECOR_BASES_AVANT] au prefixe « $HARNAIS_PREFIXE »"
  detail "« aucun residu » ne serait alors qu'une scene vide, pas un nettoyage"
  exit 1
fi
ok "NON VACUITE: le decor EXISTE avant le signal — $(awk -F, '{print NF}' <<<"$DECOR_ROLES_AVANT") role(s), $(awk -F, '{print NF}' <<<"$DECOR_BASES_AVANT") base(s)"
detail "roles: $DECOR_ROLES_AVANT"
detail "bases: $DECOR_BASES_AVANT"

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

GROUPE="$(groupe_vivant "$WRAP_PID")"
[[ -z "${GROUPE// /}" ]] \
  && ok "le groupe du wrapper ne contient plus aucun processus vivant" \
  || { echoue "le groupe $WRAP_PID contient encore des processus vivants: $GROUPE"
       detail "$(ps -o pid=,stat=,args= -g "$WRAP_PID" 2>/dev/null | head -3)"; }

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
    # LE VERDICT NOMME CE QUI A ETE DETRUIT. Le compte vient de la photographie
    # prise AVANT le signal, qui a deja refuse le decor vide: cette ligne ne
    # peut donc plus s'imprimer sur une scene qui n'a jamais rien porte.
    ok "les $(awk -F, '{print NF}' <<<"$DECOR_ROLES_AVANT") role(s) et $(awk -F, '{print NF}' <<<"$DECOR_BASES_AVANT") base(s) du decor ont ete DETRUITS; aucun residu au prefixe « $HARNAIS_PREFIXE »"
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
#
# LA CREATION ET L'ENREGISTREMENT SONT UNE SEULE OPERATION. `session_creer` ne
# rend la main qu'apres avoir declare l'intention, constate la DETENTION exacte
# et relu un manifeste valide; il n'y a donc plus de fenetre pendant laquelle un
# backend de C existe sans etre enregistre.
if ! session_creer C "$APP_FUITE" "$CLE1" "$CLE2"; then
  echoue "C: la connexion porteuse n'est jamais apparue — scenario non exerce"
  detail "$SESSION_DIAG"
else
  FUITE_CLIENT="$SESSION_CLIENT"; FUITE_BACKEND="$SESSION_BACKEND"
  FUITE_START="$SESSION_START"; FUITE_DATID="$SESSION_DATID"; FUITE_USER="$SESSION_USER"
  {
    ok "verrou injecte pose: backend $FUITE_BACKEND, cles ($CLE1,$CLE2), objsubid 2"
    detail "manifeste C: ETAT=$(sed -n 's/^ETAT=//p' "$MANIFESTES/C"), backend enregistre a la creation"

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
    # MEME CHEMIN UNIQUE. Le second backend de C entre au manifeste par la meme
    # porte que le premier: c'est la seule facon que « le registre est complet »
    # ne dependre pas du soin de l'auteur.
    if ! session_creer C "$APP_TIERS" "$CLE1" "$CLE2"; then
      echoue "C: la session tierce ne detient pas le meme verrou — survie non exercee"
      detail "$SESSION_DIAG"
    else
      TIERS_CLIENT="$SESSION_CLIENT"; TIERS_BACKEND="$SESSION_BACKEND"
      TIERS_START="$SESSION_START"; TIERS_DATID="$SESSION_DATID"; TIERS_USER="$SESSION_USER"
    fi
    if [[ -z "$TIERS_BACKEND" ]]; then
      :
    elif [[ "$TIERS_BACKEND" == "$FUITE_BACKEND" ]]; then
      echoue "C: tiers et fuite partagent le meme PID ($TIERS_BACKEND)"
    else
      ok "session tierce DETENTRICE du meme verrou partage: backend $TIERS_BACKEND (ShareLock, accorde)"
      detail "manifeste C: $(grep -c '^BACKEND=' "$MANIFESTES/C") backend(s) enregistre(s) par le helper"

      # UN PID N'EST PAS UNE AUTORITE — et voici la preuve. Meme PID, MAUVAISE
      # identite: la terminaison doit REFUSER, et la session survivre avec son
      # verrou. Sans ce controle, « on ne termine que ce qu'on possede » ne
      # serait qu'une intention.
      terminer_identite "$TIERS_BACKEND" "$TIERS_START" "$TIERS_DATID" "$TIERS_USER" \
                        "$APP_TIERS-FAUX" "C (mauvaise identite)"
      rcf=$?
      if (( rcf == 2 )); then
        detient_verrou "$TIERS_BACKEND" "$APP_TIERS" "$CLE1" "$CLE2" ShareLock \
          && ok "identite non concordante: terminaison REFUSEE, backend et verrou intacts" \
          || echoue "C: la mauvaise identite a ete refusee mais le verrou a disparu"
      else
        echoue "C: une mauvaise identite rend $rcf, attendu 2 (refus)"
        (( rcf == 0 )) && detail "le PID seul a suffi a tuer: la propriete n'est pas verifiee"
      fi

      terminer_identite "$FUITE_BACKEND" "$FUITE_START" "$FUITE_DATID" "$FUITE_USER" \
                        "$APP_FUITE" "C"
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

      terminer_identite "$TIERS_BACKEND" "$TIERS_START" "$TIERS_DATID" "$TIERS_USER" \
                        "$APP_TIERS" "C (tiers)"
      (( $? == 0 )) && TIERS_BACKEND="" || echoue "C: le tiers n'a pas pu etre nettoye"
    fi

    kill "$FUITE_CLIENT" 2>/dev/null; wait "$FUITE_CLIENT" 2>/dev/null; FUITE_CLIENT=""
    [[ -n "$TIERS_CLIENT" ]] && { kill "$TIERS_CLIENT" 2>/dev/null
                                  wait "$TIERS_CLIENT" 2>/dev/null; TIERS_CLIENT=""; }

    # APRES NETTOYAGE, L'EGALITE EXACTE — code 0, rien d'autre. Sans cette
    # seconde moitie, un detecteur qui rougirait TOUJOURS passerait aussi.
    comparer_verrous "C (retour a l'etat initial)" "$VERROUS_AVANT_C"; rc=$?
    (( rc == 0 )) || echoue "C: apres nettoyage la comparaison rend $rc, attendu 0"

    # L'ETAT TERMINAL EST UNE CONCLUSION, PAS UNE DECLARATION. `session_liberer`
    # relit chaque identite enregistree dans `pg_stat_activity` et recompte les
    # verrous des deux cles: sans cette double absence, le manifeste reste ACTIF
    # et la baseline de E refusera — ce qui est le comportement voulu.
    if session_liberer C "$CLE1" "$CLE2"; then
      ok "C: manifeste NETTOYE apres revalidation de l'absence reelle (backends et verrou)"
    else
      echoue "C: le manifeste reste $(sed -n 's/^ETAT=//p' "$MANIFESTES/C") — $SESSION_DIAG"
    fi
  }
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
# BASELINE EXTERNE B0 — CAPTUREE AVANT DE LANCER QUOI QUE CE SOIT DE E, ET
# CONFIRMEE PAR DEUX LECTURES IDENTIQUES CONSECUTIVES.
#
# Mesure du defaut precedent: la baseline etait prise alors que les ShareLock
# du scenario PRECEDENT n'etaient pas encore retombes. Leur disparition —
# normale, c'est le nettoyage qui marche — etait ensuite lue « le scenario a
# libere un verrou qui ne lui appartenait pas ». Une photographie peut etre
# stable ET contenir des ressources qui ne sont pas exterieures au scenario.
#
# Aucun `sleep` fixe: on exige deux lectures EGALES, dans une attente bornee.
# LA CONVERGENCE EST ATTENDUE, PUIS EXIGEE. Le nettoyage d'un scenario est
# asynchrone: ses backends peuvent avoir disparu alors que ses verrous ne sont
# pas encore retombes. On laisse donc au registre le temps de se vider — de
# facon BORNEE — puis on refuse si quelque chose lui appartient encore.
for _ in $(seq 1 300); do b0_contaminee || break; sleep 0.1; done
if b0_contaminee; then
  echoue "E: BASELINE_CONTAMINEE — $B0_DIAG"
  detail "une baseline stable peut contenir des ressources qui ne sont pas exterieures"
else
  ok "E: aucun scenario anterieur ne possede plus de ressource"
fi
VERROUS_AVANT_E=""
b_prec="$(empreinte_verrous)"; b_stable=0
for _ in $(seq 1 300); do
  sleep 0.1
  b_cur="$(empreinte_verrous)"
  [[ "$b_cur" == ILLISIBLE* ]] && { echoue "E: baseline illisible"; break; }
  if [[ "$b_cur" == "$b_prec" ]]; then VERROUS_AVANT_E="$b_cur"; b_stable=1; break; fi
  b_prec="$b_cur"
done
if (( b_stable )); then
  nb0="$(grep -c . <<<"$VERROUS_AVANT_E")"; [[ -z "$VERROUS_AVANT_E" ]] && nb0=0
  ok "E: baseline externe B0 confirmee par deux lectures identiques ($nb0 verrou(s))"
else
  echoue "E: la baseline externe ne s'est pas stabilisee"
fi
# L'INTENTION EST DECLAREE AVANT QUE LE SOUS-MODE N'EXISTE. Le manifeste de E
# passe en PREPARE ici: si le sous-mode etait tue entre son acquisition et la
# publication des identites, E resterait en PREPARE et toute baseline ulterieure
# refuserait. L'ordre « creer puis enregistrer » laissait au contraire une
# fenetre pendant laquelle la ressource existait sans proprietaire declare.
session_declarer E "$E_CLE1" "$E_CLE2"
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
    # LE PARENT REVALIDE LUI-MEME, JUSTE AVANT LE SIGNAL. Il ne se fie pas au
    # temoin ecrit par le sous-mode: c'est l'etat du catalogue a cet instant qui
    # decide s'il y a bien quelque chose a nettoyer.
    # LA REVALIDATION ET L'ENREGISTREMENT SONT LA MEME OPERATION. `session_publier`
    # exige la DETENTION exacte avant d'inscrire quoi que ce soit, puis relit le
    # manifeste par le lecteur de `b0_contaminee`. Le parent ne se fie donc ni au
    # temoin ecrit par le sous-mode, ni a sa propre ecriture.
    revalide=1
    if [[ "$E_FB" == "$E_TB" ]]; then
      echoue "E: les deux PID publies sont identiques ($E_FB)"
    elif ! session_publier E "$E_AF" "$E_FB" "$E_CLE1" "$E_CLE2"; then
      echoue "E: le backend de fuite ne detient pas le verrou attendu — rien a nettoyer"
      detail "$SESSION_DIAG"
    elif ! session_publier E "$E_AT" "$E_TB" "$E_CLE1" "$E_CLE2"; then
      echoue "E: le backend tiers ne detient pas le verrou attendu — rien a nettoyer"
      detail "$SESSION_DIAG"
    else
      revalide=0
      ok "sous-mode pret et REVALIDE: $E_FB et $E_TB detiennent ($E_CLE1,$E_CLE2) en ShareLock accorde"
      detail "manifeste E: ETAT=$(sed -n 's/^ETAT=//p' "$MANIFESTES/E"), $(grep -c '^BACKEND=' "$MANIFESTES/E") backend(s)"
    fi
    kill -TERM "$EPID"
    E_CODE=0; wait "$EPID" 2>/dev/null || E_CODE=$?
    # UN CODE QUELCONQUE N'EST PAS UN SUCCES. « ok: sous-mode interrompu, code
    # $E_CODE » etait vert pour 0, 1, 9 comme 143 — le scenario n'imposait rien.
    case "$E_CODE" in
      143) ok "sous-mode interrompu: code 143 (SIGTERM rendu, nettoyage vert)" ;;
      9)   echoue "E: code 9 — le nettoyage du sous-mode a echoue" ;;
      0)   echoue "E: code 0 — le signal n'a pas ete reflete" ;;
      *)   echoue "E: code $E_CODE, attendu 143" ;;
    esac
    (( revalide == 0 )) || detail "les postconditions ci-dessous ne prouvent rien: rien n'avait ete acquis"

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
    # B1 doit egaler B0 EXACTEMENT: les verrous de E ne doivent apparaitre
    # dans aucun des deux, et le verrou legitime d'un appelant imbrique doit
    # apparaitre dans les deux.
    #
    # LE SOUS-MODE A NETTOYE; LE PARENT NE LE CROIT PAS SUR PAROLE. Il relit
    # chaque identite qu'il a lui-meme enregistree et recompte les verrous des
    # deux cles avant de publier `NETTOYE`.
    if session_liberer E "$E_CLE1" "$E_CLE2"; then
      ok "E: manifeste NETTOYE apres revalidation de l'absence reelle"
    else
      echoue "E: le manifeste reste $(sed -n 's/^ETAT=//p' "$MANIFESTES/E") — $SESSION_DIAG"
    fi
    comparer_verrous "E (B1 = B0)" "$VERROUS_AVANT_E"
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
# LE SOUS-MODE A-T-IL SEULEMENT EU UN VERROU A NETTOYER ? Sans cette preuve, F
# testerait le remplacement du code de sortie sur un nettoyage qui n'avait rien
# a rendre.
if ! grep -q READY "$TEMOIN_F" 2>/dev/null; then
  echoue "F: le sous-mode n'a pas annonce READY — scenario non exerce"
  detail "$(sed -n 's/^diag=//p' "$TEMOIN_F")"
elif [[ "$(lire_sql "select count(*) from pg_locks
                      where locktype='advisory' and classid=$F_CLE1 and objid=$F_CLE2
                        and granted and mode='ShareLock'")" != "1" ]]; then
  echoue "F: aucun verrou reel n'a survecu au nettoyage casse — rien n'etait a nettoyer"
elif (( F_CODE == 9 )); then
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
  enregistrer_identite "$F_AF" \
    && terminer_identite "$ID_PID" "$ID_START" "$ID_DATID" "$ID_USER" "$F_AF" "F (rattrapage)" >/dev/null
fi
reste="$(lire_sql "select count(*) from pg_locks
                    where locktype='advisory' and classid=$F_CLE1 and objid=$F_CLE2")"
[[ "$reste" == "0" ]] \
  && ok "le verrou laisse par le nettoyage casse a ete rendu" \
  || echoue "F: verrou residuel apres rattrapage ($reste)"
rm -f "$TEMOIN_F" "$TEMOIN_F.log"

# ==========================================================================
# G. ACQUISITION IMPOSSIBLE — pas de READY, et le parent le dit
# ==========================================================================
# Les connexions s'ouvrent, les PID sont numeriques et presents, mais AUCUN
# verrou n'est pris. C'est exactement le cas ou l'ancienne boucle publiait
# `READY` en arrivant au bout de ses 600 passages, et ou E passait au vert sans
# avoir rien exerce.
echo "      -- G. acquisition impossible: aucun READY, rouge explicite"
TEMOIN_G="$(mktemp)"
G_CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
G_CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
ESC_SIGNAL_SOUS_MODE=interruption_c ESC_SIGNAL_TEMOIN="$TEMOIN_G" \
  ESC_SIGNAL_CLE1="$G_CLE1" ESC_SIGNAL_CLE2="$G_CLE2" \
  ESC_ACQUISITION_IMPOSSIBLE=1 \
  bash "$HERE/$(basename "${BASH_SOURCE[0]}")" >/dev/null 2>&1 &
GPID=$!
G_CODE=0; wait "$GPID" 2>/dev/null || G_CODE=$?
if grep -q READY "$TEMOIN_G" 2>/dev/null; then
  echoue "G: READY publie alors qu'aucun verrou n'a ete acquis"
  detail "c'est le faux vert que E pouvait produire"
else
  ok "aucun READY publie sans acquisition prouvee"
fi
grep -q FAILED "$TEMOIN_G" 2>/dev/null \
  && ok "le sous-mode a publie FAILED avec son diagnostic" \
  || echoue "G: ni READY ni FAILED — le sous-mode n'a rien dit"
(( G_CODE == 4 )) \
  && ok "le sous-mode sort en 4 (scenario non exerce), et non 0" \
  || echoue "G: code $G_CODE, attendu 4"
rm -f "$TEMOIN_G"

# ==========================================================================
# H. INTERRUPTION + NETTOYAGE CASSE — 9, jamais 143
# ==========================================================================
echo "      -- H. signal puis nettoyage casse: 9, pas 143"
TEMOIN_H="$(mktemp)"
H_CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
H_CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
ESC_SIGNAL_SOUS_MODE=interruption_c ESC_SIGNAL_TEMOIN="$TEMOIN_H" \
  ESC_SIGNAL_CLE1="$H_CLE1" ESC_SIGNAL_CLE2="$H_CLE2" \
  ESC_NETTOYAGE_CASSE_APRES=1 \
  bash "$HERE/$(basename "${BASH_SOURCE[0]}")" >"$TEMOIN_H.log" 2>&1 &
HPID=$!
for _ in $(seq 1 900); do
  grep -qE 'READY|FAILED' "$TEMOIN_H" 2>/dev/null && break
  kill -0 "$HPID" 2>/dev/null || break
  sleep 0.1
done
if ! grep -q READY "$TEMOIN_H" 2>/dev/null; then
  echoue "H: le sous-mode n'a pas annonce READY — scenario non exerce"
  kill -KILL "$HPID" 2>/dev/null; wait "$HPID" 2>/dev/null
else
  kill -TERM "$HPID"
  H_CODE=0; wait "$HPID" 2>/dev/null || H_CODE=$?
  if (( H_CODE == 9 )); then
    ok "signal + nettoyage casse: code 9, et non 143"
    grep -q 'code initial 143' "$TEMOIN_H.log" \
      && ok "le code initial 143 est journalise dans le diagnostic" \
      || echoue "H: le code initial n'est pas journalise"
  else
    echoue "H: code $H_CODE, attendu 9 (le nettoyage rouge doit remplacer 143)"
  fi
  # Rattrapage par identite verifiee: le sous-mode n'a rien pu rendre.
  H_FB="$(sed -n 's/^FUITE_BACKEND=//p' "$TEMOIN_H")"
  H_TB="$(sed -n 's/^TIERS_BACKEND=//p' "$TEMOIN_H")"
  H_AF="$(sed -n 's/^APP_FUITE=//p' "$TEMOIN_H")"
  H_AT="$(sed -n 's/^APP_TIERS=//p' "$TEMOIN_H")"
  for duo in "$H_FB:$H_AF" "$H_TB:$H_AT"; do
    hp="${duo%%:*}"; ha="${duo##*:}"
    pid_valide "${hp:-x}" || continue
    enregistrer_identite "$ha" \
      && terminer_identite "$ID_PID" "$ID_START" "$ID_DATID" "$ID_USER" "$ha" "H" >/dev/null
  done
  reste="$(lire_sql "select count(*) from pg_locks
                      where locktype='advisory' and classid=$H_CLE1 and objid=$H_CLE2")"
  [[ "$reste" == "0" ]] \
    && ok "les verrous laisses par H ont ete rendus" \
    || echoue "H: verrou residuel apres rattrapage ($reste)"
fi
rm -f "$TEMOIN_H" "$TEMOIN_H.log"

# ==========================================================================
# I. SIGINT — 130, et non 143
# ==========================================================================
# Tant que ce chemin n'etait pas exerce, affirmer que SIGINT est correctement
# reflete etait une promesse sans preuve — et le trap unique lui donnait 143.
echo "      -- I. SIGINT: code 130"
# L'ETAT INITIAL EST MESURE, PAS SUPPOSE. En CI non interactif le mode monitor
# devrait etre absent, mais le test le CONSTATE au lieu de le presumer.
MONITOR_AVANT="$(set -o | awk '$1=="monitor"{print $2}')"
ok "mode monitor avant I: $MONITOR_AVANT"
TEMOIN_I="$(mktemp)"
I_CLE1=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
I_CLE2=$(( (RANDOM * 32768 + RANDOM) % 1000000000 + 1000 ))
I_RES="$(mktemp)"
(
  # LE SOUS-SHELL DEDIE: `monitor` vit et meurt avec lui.
  set -m
  dedans="$(set -o | awk '$1=="monitor"{print $2}')"
  echo "MONITOR_DEDANS=$dedans" >>"$I_RES"
  ESC_SIGNAL_SOUS_MODE=interruption_c ESC_SIGNAL_TEMOIN="$TEMOIN_I" \
    ESC_SIGNAL_CLE1="$I_CLE1" ESC_SIGNAL_CLE2="$I_CLE2" \
    bash "$HERE/$(basename "${BASH_SOURCE[0]}")" >/dev/null 2>&1 &
  IPID=$!
  echo "IPID=$IPID" >>"$I_RES"
  echo "IPGID=$(ps -o pgid= -p "$IPID" 2>/dev/null | tr -d ' ')" >>"$I_RES"
  pret=0
  for _ in $(seq 1 900); do
    grep -qE 'READY|FAILED' "$TEMOIN_I" 2>/dev/null && { pret=1; break; }
    kill -0 "$IPID" 2>/dev/null || break
    sleep 0.1
  done
  if (( pret == 0 )) || ! grep -q READY "$TEMOIN_I" 2>/dev/null; then
    echo "PRET=0" >>"$I_RES"; kill -KILL "$IPID" 2>/dev/null; wait "$IPID" 2>/dev/null
  else
    echo "PRET=1" >>"$I_RES"
    kill -INT "$IPID"
    c=0; wait "$IPID" 2>/dev/null || c=$?
    echo "I_CODE=$c" >>"$I_RES"
  fi
)
MONITOR_APRES="$(set -o | awk '$1=="monitor"{print $2}')"
I_MONDEDANS="$(sed -n 's/^MONITOR_DEDANS=//p' "$I_RES")"
I_CODE="$(sed -n 's/^I_CODE=//p' "$I_RES")"
I_PGID="$(sed -n 's/^IPGID=//p' "$I_RES")"
I_PID_SM="$(sed -n 's/^IPID=//p' "$I_RES")"

[[ "$I_MONDEDANS" == on ]] \
  && ok "le mode monitor est actif A L'INTERIEUR du sous-shell de I" \
  || echoue "I: monitor « $I_MONDEDANS » dans le sous-shell, attendu « on »"
[[ "$MONITOR_APRES" == "$MONITOR_AVANT" ]] \
  && ok "le mode monitor est restaure apres I ($MONITOR_APRES = etat initial)" \
  || echoue "I: monitor « $MONITOR_APRES » apres I, initialement « $MONITOR_AVANT »"

if [[ "$(sed -n 's/^PRET=//p' "$I_RES")" != "1" ]]; then
  echoue "I: le sous-mode n'a pas annonce READY — scenario non exerce"
else
  ok "sous-mode de I: pid $I_PID_SM, PGID vise $I_PGID"
  [[ "$I_CODE" == "130" ]] \
    && ok "SIGINT rendu en 130 (128 + 2), distinct du 143 de SIGTERM" \
    || echoue "I: code $I_CODE, attendu 130"
  [[ -z "$(vivants "$I_PID_SM")" ]] \
    && ok "aucun processus du sous-mode de I ne survit" \
    || echoue "I: le sous-mode $I_PID_SM survit"
  reste="$(lire_sql "select count(*) from pg_locks
                      where locktype='advisory' and classid=$I_CLE1 and objid=$I_CLE2")"
  [[ "$reste" == "0" ]] \
    && ok "SIGINT a rendu les verrous du sous-mode" \
    || echoue "I: $reste verrou(s) subsistent apres SIGINT"
fi
rm -f "$TEMOIN_I" "$I_RES"

# ==========================================================================
# J. HARNAIS QUI SORT IMMEDIATEMENT — le temoin ne doit rien retenir
# ==========================================================================
# LE DEFAUT QUI A RENDU LA CI ROUGE. Le temoin `sleep` heritait des deux pipes
# du `Popen`: des que le harnais finissait AVANT le signal, `communicate()`
# n'atteignait jamais EOF, la matrice restait vivante sans enfant direct, et
# l'attente cote test expirait apres ses 300 secondes. Mesure hors harnais:
#
#   CASSE   : temoin fd/1 = pipe:[2921774] — communicate() BLOQUE
#   CORRIGE : fd absents  — communicate() rendu en 0,9 s, code 7 du harnais
#
# Ce scenario le rejoue AVEC LA MATRICE, et il est court par construction.
echo "      -- J. harnais qui sort immediatement: ni blocage, ni orphelin"
# LE CONFINEMENT SE VERIFIE AUSSI ICI: J doit demarrer avec la semantique
# d'origine, et rien de I ne doit lui survivre.
MONITOR_J="$(set -o | awk '$1=="monitor"{print $2}')"
[[ "$MONITOR_J" == "$MONITOR_AVANT" ]] \
  && ok "au debut de J, le mode monitor vaut toujours « $MONITOR_J »" \
  || echoue "J: monitor « $MONITOR_J », initialement « $MONITOR_AVANT »"
if [[ -n "${I_PGID:-}" ]] && pid_valide "${I_PGID:-x}"; then
  [[ -z "$(groupe_vivant "$I_PGID")" ]] \
    && ok "aucun processus du groupe de I ($I_PGID) ne survit au debut de J" \
    || echoue "J: le groupe $I_PGID de I contient encore des processus vivants"
fi
TEMOIN_J="$(canal_neuf temoin-J)"; FAUX_HARNAIS="$(mktemp)"
printf '#!/usr/bin/env bash\nexit 7\n' >"$FAUX_HARNAIS"; chmod +x "$FAUX_HARNAIS"
J_T0=$(date +%s)
( cd "$PROJET" && ESC_MUTATION_TEMOIN="$TEMOIN_J" \
    ESC_MUTATION_HARNAIS_REMPLACE="$FAUX_HARNAIS" \
    EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
    timeout 120 python3 "$MATRICE" W1 ) >"$TEMOIN_J.log" 2>&1
J_CODE=$?; J_DUREE=$(( $(date +%s) - J_T0 ))
if (( J_DUREE >= 100 )); then
  echoue "J: la matrice a mis ${J_DUREE}s — le temoin retient encore les pipes"
  detail "c'est exactement le blocage de 300 s qui a rougi la CI"
else
  ok "la matrice rend la main en ${J_DUREE}s, sans attendre le temoin"
fi
if [[ -s "$TEMOIN_J" ]]; then
  if lire_marqueur "$TEMOIN_J"; then
    J_TEM="$MK_WIT"
    ok "marqueur $MK_FORMAT, etat $MK_STATE: wrapper $MK_WRAP, harnais $MK_HARN, temoin $J_TEM"
    [[ "$MK_STATE" == FAILED ]] \
      && ok "le producteur a REFUSE de dire READY sur un harnais deja mort" \
      || echoue "J: etat $MK_STATE alors que le harnais sort immediatement"
    [[ -z "$(vivants "$J_TEM")" ]] \
      && ok "le temoin a ete moissonne a la fin normale du harnais" \
      || { echoue "J: le temoin $J_TEM survit a la fin du harnais"
           detail "$(ps -o pid=,ppid=,args= -p "$J_TEM" 2>/dev/null)"; }
  else
    echoue "J: marqueur refuse: $MK_DIAG"
  fi
else
  echoue "J: aucun marqueur publie"
fi
# LE CONTROLE DE SECURITE NE PEUT PAS ETRE VERT: le harnais n'a rien exerce.
grep -q 'NON EXECUTE\|harnais a refuse' "$TEMOIN_J.log" \
  && ok "la matrice compte ce controle NON EXECUTE, jamais tue" \
  || detail "note: sortie de la matrice — $(grep -m1 -E '^  (ok|ECHEC|NON EXECUTE)' "$TEMOIN_J.log" || echo '(vide)')"
rm -f "$TEMOIN_J" "$TEMOIN_J.log" "$FAUX_HARNAIS"

# ==========================================================================
# K. USURPATION DU JETON — le nettoyage doit refuser, pas tuer largement
# ==========================================================================
# `application_name` est CHOISI PAR LE CLIENT. Une session tierce adopte donc
# volontairement le MEME jeton, avec un autre PID et un autre `backend_start`.
# Un nettoyage fonde sur le jeton seul la terminerait; celui-ci doit refuser.
echo "      -- K. usurpation du jeton: identite exacte, ou refus"
K_APP="esc-fuite-$JETON-K"
psql -X -qtA -d postgres -c "select pg_sleep(120);" >/dev/null 2>&1 &
K_LEGIT=$!
PGAPPNAME="$K_APP" psql -X -qtA -d postgres -c "select pg_sleep(120);" >/dev/null 2>&1 &
K_CLIENT=$!
for _ in $(seq 1 300); do enregistrer_identite "$K_APP" && break; sleep 0.1; done
K_PID="$ID_PID"; K_START="$ID_START"; K_DATID="$ID_DATID"; K_USER="$ID_USER"
if ! pid_valide "${K_PID:-x}"; then
  echoue "K: la session porteuse n'est jamais apparue — scenario non exerce"
else
  ok "session enregistree: pid $K_PID, backend_start $K_START, datid $K_DATID, role $K_USER"
  # L'USURPATEUR: meme jeton, autre PID, autre backend_start.
  PGAPPNAME="$K_APP" psql -X -qtA -d postgres -c "select pg_sleep(120);" >/dev/null 2>&1 &
  K_IMPOST=$!
  K_IPID=""
  for _ in $(seq 1 300); do
    K_IPID="$(lire_sql "select pid from pg_stat_activity
                         where application_name = '$K_APP' and pid <> $K_PID" | head -1)"
    pid_valide "${K_IPID:-x}" && break
    sleep 0.1
  done
  if ! pid_valide "${K_IPID:-x}"; then
    echoue "K: l'usurpateur n'est jamais apparu — survie non exercee"
  else
    ok "usurpateur du MEME jeton: pid $K_IPID (deux lignes portent « $K_APP »)"
    # Terminer l'identite ENREGISTREE ne doit toucher qu'elle.
    terminer_identite "$K_PID" "$K_START" "$K_DATID" "$K_USER" "$K_APP" "K"
    (( $? == 0 )) && ok "le backend enregistre a ete termine" \
                  || echoue "K: le backend enregistre n'a pas ete termine"
    vit="$(lire_sql "select count(*) from pg_stat_activity where pid = $K_IPID")"
    [[ "$vit" == "1" ]] \
      && ok "l'usurpateur du jeton a SURVECU: le jeton n'est pas une autorite" \
      || echoue "K: l'usurpateur a ete termine — nettoyage trop large"
    # Et une identite qui ne concorde pas d'UN SEUL attribut doit etre refusee.
    terminer_identite "$K_IPID" "$K_START" "$K_DATID" "$K_USER" "$K_APP" "K (start errone)"
    (( $? == 2 )) \
      && ok "un seul attribut different (backend_start) suffit a refuser" \
      || echoue "K: la terminaison n'a pas refuse sur un backend_start errone"
    enregistrer_identite "$K_APP" >/dev/null 2>&1
    pid_valide "${ID_PID:-x}" && terminer_identite "$ID_PID" "$ID_START" "$ID_DATID" \
      "$ID_USER" "$K_APP" "K (menage)" >/dev/null
    kill "$K_IMPOST" 2>/dev/null; wait "$K_IMPOST" 2>/dev/null
  fi
fi
kill "$K_CLIENT" "$K_LEGIT" 2>/dev/null; wait "$K_CLIENT" 2>/dev/null; wait "$K_LEGIT" 2>/dev/null
reste="$(lire_sql "select count(*) from pg_stat_activity where application_name = '$K_APP'")"
[[ "$reste" == "0" ]] && ok "aucune session « $K_APP » ne subsiste" \
                      || echoue "K: $reste session(s) subsistent"

# ==========================================================================
# L. ORDRE CAUSAL DU WRAPPER — prouve par marqueurs exclusifs, pas par horloge
# ==========================================================================
# « Le wrapper attend le harnais » etait une intention. Ce scenario etablit la
# CHAINE: le harnais entre dans sa trap, commence son nettoyage lent, le
# termine, sort; ALORS SEULEMENT le wrapper le moissonne, moissonne le temoin,
# et rend la main. Les marqueurs sont crees par `mkdir` — exclusif — donc une
# seconde emission est une erreur observable et non un ecrasement silencieux.
echo "      -- L. ordre causal du wrapper: chaine complete, une seule fois"
L_SCEN="L-$JETON"
FAUX="$PROJET/db/test/faux_harnais_causal.sh"
[[ -f "$FAUX" ]] || echoue "L: faux harnais introuvable: $FAUX"

L_JETON="jeton-$L_SCEN"
lancer_L() {   # lancer_L <marqueurs> <journal> <marqueur-wrapper> [VAR=val...]
  local marq="$1" jour="$2" temoin="$3"; shift 3
  ( cd "$PROJET" || exit 2
    export ESC_MUTATION_TRACE="$(mktemp)" ESC_MUTATION_TEMOIN="$temoin"
    export ESC_MUTATION_HARNAIS_REMPLACE="$FAUX"
    # LE JETON N'EST PAS DECORATIF ICI NON PLUS. Le wrapper compare le jeton
    # publie par la porte a `ESC_MUTATION_JETON`; sans lui les deux valent la
    # chaine vide et la comparaison ne verifie plus rien. Mesure de son
    # absence: le double refusait d'armer — « PORTE=jeton absent » — le
    # wrapper publiait FAILED, et les cinq scenarios L mesuraient un refus au
    # lieu de la chaine causale.
    export ESC_MUTATION_JETON="$L_JETON"
    export ESC_MARQUEURS="$marq" ESC_JOURNAL="$jour" ESC_SCENARIO="$L_SCEN"
    export ESC_MUTATION_RESULTAT="$L_RESULTAT"
    export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
    for kv in "$@"; do export "${kv?}"; done
    exec python3 "$MATRICE" W1 ) >/dev/null 2>&1 &
  MPID=$!
}

# UNE SEULE SOURCE DE VERITE POUR LES EVENEMENTS. Le total etait ecrit en dur
# (« == 7 ») independamment de la liste attendue: l'ajout de WRAPPER_WAITING a
# porte le scan global a 8 sans que la liste change, et la chaine a ete
# declaree incomplete alors qu'aucun evenement ne manquait —
# « manquants[] total=8 ». Le nombre attendu, les noms autorises et l'ordre
# causal derivent desormais tous du meme tableau.
#
# WRAPPER_WAITING est une PRECONDITION, pas un maillon causal du nettoyage: il
# est emis avant tout signal. Il est donc autorise mais exclu de la chaine.
CHAINE_CAUSALE=(HARNESS_TRAP_ENTERED HARNESS_CLEANUP_STARTED HARNESS_CLEANUP_DONE
                HARNESS_EXITING WRAPPER_REAPED_HARNESS WRAPPER_REAPED_WITNESS
                WRAPPER_EXITING)
CHAINE_PRECONDITIONS=(WRAPPER_WAITING)
CHAINE_DIAG=""
chaine_ok() {   # chaine_ok <repertoire-de-marqueurs>
  local m="$1" ev d base manquants=() inconnus=() sans_meta=()
  CHAINE_DIAG=""
  for ev in "${CHAINE_CAUSALE[@]}"; do
    [[ -d "$m/$ev" ]] || { manquants+=("$ev"); continue; }
    [[ -f "$m/$ev/meta" ]] || sans_meta+=("$ev")
  done
  # EVENEMENT INCONNU SUPPLEMENTAIRE: refuse separement d'un manquant.
  for d in "$m"/*/; do
    [[ -d "$d" ]] || continue
    base="$(basename "$d")"
    printf '%s\n' "${CHAINE_CAUSALE[@]}" "${CHAINE_PRECONDITIONS[@]}" \
      | grep -qx "$base" || inconnus+=("$base")
  done
  (( ${#manquants[@]} )) && CHAINE_DIAG="obligatoire(s) absent(s): ${manquants[*]}"
  (( ${#sans_meta[@]} )) && CHAINE_DIAG="$CHAINE_DIAG; sans meta: ${sans_meta[*]}"
  (( ${#inconnus[@]} ))  && CHAINE_DIAG="$CHAINE_DIAG; inconnu(s): ${inconnus[*]}"
  [[ -z "$CHAINE_DIAG" ]]
}

# --- L1: SIGTERM AU WRAPPER SEUL ------------------------------------------
# TOPOLOGIE, ECRITE ET DISTINCTE DE CELLE DE A.
#   A  signale la MATRICE; `_arreter_enfant()` relaie ensuite AU GROUPE, donc
#      le harnais recoit le signal directement et le `wait` du wrapper n'est
#      pas interrompu.
#   L1 signale LE WRAPPER SEUL, par son PID. La matrice reste vivante, le
#      harnais ne recoit rien du systeme: c'est le RELAIS du wrapper qui doit
#      l'atteindre, et son `wait` qui doit etre interrompu.
# La version precedente de L1 signalait la matrice tout en s'intitulant
# « wrapper seul »: elle exercait le meme chemin que A, et la reattente n'etait
# jamais eprouvee — « aucun retour de wait interrompu observe ».
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM"
attendre "le faux harnais pret (L1)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
L_HPID="$(awk '{print $2}' "$L_MARQ/.harnais")"
attendre "le marqueur du wrapper (L1)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
L_ETAT="$(sed -n 's/^STATE=//p' "$L_TEM")"
# L'ATTENTE DU WRAPPER EST ARMEE: sans ce marqueur, signaler trop tot ne
# produirait aucun retour interrompu et le chemin ne serait pas exerce.
attendre "l'attente du wrapper armee (L1)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
[[ -z "$(find "$L_MARQ" -mindepth 1 -maxdepth 1 -type d ! -name WRAPPER_WAITING)" ]] \
  && ok "L1: aucun marqueur de nettoyage avant le signal" \
  || echoue "L1: des marqueurs de nettoyage existent deja avant le signal"

if [[ "$L_ETAT" != READY ]] || ! pid_valide "${L_WPID:-x}" \
   || [[ -z "$(vivants "$L_WPID")" ]]; then
  echoue "L1: identite du wrapper invalide avant le signal (etat=$L_ETAT pid=$L_WPID)"
else
  ok "L1: wrapper $L_WPID revalide vivant, matrice $MPID laissee intacte"
  kill -TERM "$L_WPID"                    # LE WRAPPER SEUL, jamais la matrice
  L_T0=$SECONDS
  # LA MATRICE EST CONSTATEE VIVANTE ICI, PAS PLUS TARD, ET C'EST UNE ASSERTION.
  # Elle etait verifiee apres la publication du resultat — c'est-a-dire APRES le
  # `communicate()` qui la libere: la matrice avait alors parfaitement le droit
  # d'etre deja sortie, et le controle basculait sur un `detail` muet. Le test
  # restait vert en n'ayant rien etabli de ce qu'il annonce: « on signale le
  # wrapper SEUL ». Mesure: deux executions consecutives du meme fichier ont
  # rendu 115 puis 114 assertions, sans qu'aucune propriete ait change.
  #
  # A cet instant-ci la reponse est DETERMINEE: `communicate()` est bloque sur
  # les tubes du wrapper, qui vient tout juste de recevoir son signal et doit
  # encore attendre les trois secondes de nettoyage du harnais.
  [[ -n "$(vivants "$MPID")" ]] \
    && ok "L1: la matrice $MPID est vivante a l'instant du signal au wrapper" \
    || echoue "L1: la matrice n'est plus la a l'instant du signal — CHEMIN NON EXERCE"
  # LE RELAIS A-T-IL ATTEINT LE HARNAIS ? PROPRIETE NOMMEE, ET BORNEE COURT.
  # Dans cette topologie le harnais ne recoit rien du systeme: seul le relais
  # du wrapper peut le toucher. Mesure, campagne de mutations sur 28daf35 —
  # supprimer le relais ne se manifestait QUE par l'expiration de l'attente de
  # fin du wrapper: 300 secondes plus tard, sur un diagnostic qui dit « la fin
  # n'est pas venue » sans dire POURQUOI, et en avortant la passe avant L2.
  # Rouge n'est pas rouge SUR LA BONNE ASSERTION. Ce controle nomme la cause,
  # et il rougit en moins d'une seconde.
  if attendre "le relais jusqu'au harnais (L1)" \
       '[[ -f "$L_MARQ/HARNESS_TRAP_ENTERED/meta" ]]' 300; then
    ok "L1: le relais du wrapper a atteint le harnais (HARNESS_TRAP_ENTERED)"
  else
    detail "le harnais n'a jamais recu le signal: le relais du wrapper est en cause"
  fi
  attendre "la fin du wrapper (L1)" '[[ -f "$L_RESULTAT" ]]' 3000 || exit 1
  L_DUREE=$(( SECONDS - L_T0 ))
  L_WRC="$(sed -n 's/^WRAPPER_RC=//p' "$L_RESULTAT")"
  L_WAITS="$(sed -n 's/^WAITS=//p' "$L_RESULTAT")"
  [[ "$(sed -n 's/^FORMAT=//p' "$L_RESULTAT")" == "esc-wrapper-result/1" \
     && "$(sed -n 's/^SCENARIO=//p' "$L_RESULTAT")" == "$L_SCEN" ]] \
    && ok "L1: canal de resultat valide (format et scenario)" \
    || echoue "L1: canal de resultat invalide"
  [[ "$L_WRC" == "143" ]] \
    && ok "L1: WRAPPER_RC=143 (SIGTERM, nettoyage reussi)" \
    || echoue "L1: WRAPPER_RC=$L_WRC, attendu 143"
  (( L_DUREE >= 2 )) \
    && ok "L1: le wrapper a attendu le nettoyage lent (${L_DUREE}s)" \
    || detail "note: duree ${L_DUREE}s — la preuve principale reste causale"

  # LA PREUVE DECISIVE DU CHEMIN: un retour interrompu, PUIS un retour final.
  n_int="$(grep -o 'WAIT_[0-9]*=interrompu' <<<"$L_WAITS" | head -1 | tr -dc 0-9)"
  n_fin="$(grep -o 'WAIT_[0-9]*=final'      <<<"$L_WAITS" | head -1 | tr -dc 0-9)"
  if [[ -z "$n_int" ]]; then
    echoue "L1: aucun WAIT interrompu — CHEMIN NON EXERCE"
    detail "waits: $L_WAITS"
  elif [[ -z "$n_fin" ]] || (( n_fin <= n_int )); then
    echoue "L1: pas de WAIT final apres l'interrompu (int=$n_int fin=${n_fin:-aucun})"
  else
    ok "L1: reattente exercee — WAIT_$n_int interrompu, puis WAIT_$n_fin final"
    detail "waits: $L_WAITS"
  fi
  if chaine_ok "$L_MARQ"; then
    ok "L1: chaine causale complete (${#CHAINE_CAUSALE[@]} evenements), aucun inconnu"
  else
    echoue "L1: chaine invalide — $CHAINE_DIAG"
  fi
  [[ ! -s "$L_MARQ/.erreurs" ]] \
    && ok "L1: aucun doublon ni prerequis invalide" \
    || { echoue "L1: erreurs de marqueurs"; detail "$(tr '\n' ' ' <"$L_MARQ/.erreurs")"; }
  [[ -z "$(vivants "$L_HPID")" ]] \
    && ok "L1: le faux harnais est termine" || echoue "L1: le faux harnais survit"
fi
[[ -n "$MPID" ]] && { kill -TERM "$MPID" 2>/dev/null; wait "$MPID" 2>/dev/null; MPID=""; }
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT"

# --- L2: LE CODE DU HARNAIS L'EMPORTE, LU SUR LE CANAL DU WRAPPER ---------
# La version precedente lisait `wait "$MPID"` — le code de la MATRICE, qui sort
# en 143 par son propre `sortir()`. Elle ne pouvait donc ni confirmer ni
# infirmer la priorite des codes du wrapper: rouge d'oracle, pas de produit.
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM" "ESC_CODE_SORTIE=9"
attendre "le faux harnais pret (L2)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
attendre "le marqueur du wrapper (L2)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L2)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
if ! pid_valide "${L_WPID:-x}"; then
  echoue "L2: PID de wrapper invalide"
else
  kill -TERM "$L_WPID"
  attendre "la fin du wrapper (L2)" '[[ -f "$L_RESULTAT" ]]' 3000 || exit 1
  L_WRC="$(sed -n 's/^WRAPPER_RC=//p' "$L_RESULTAT")"
  L_MRC=0; [[ -n "$MPID" ]] && { kill -TERM "$MPID" 2>/dev/null
                                 wait "$MPID" 2>/dev/null || L_MRC=$?; MPID=""; }
  [[ "$L_WRC" == "9" ]] \
    && ok "L2: WRAPPER_RC=9 — le code du harnais l'emporte sur 128+signal" \
    || echoue "L2: WRAPPER_RC=$L_WRC, attendu 9 (143 masquerait l'echec de nettoyage)"
  detail "MATRIX_RC=$L_MRC, rapporte separement et jamais utilise comme preuve"
fi
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT"

# --- L3: duplication de marqueur refusee ---------------------------------
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM" "ESC_DOUBLE=1"
attendre "le faux harnais pret (L3)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
attendre "le marqueur du wrapper (L3)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L3)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
kill -TERM "$L_WPID"
attendre "la fin du wrapper (L3)" '[[ -f "$L_RESULTAT" ]]' 3000 || exit 1
[[ -n "$MPID" ]] && { kill -TERM "$MPID" 2>/dev/null; wait "$MPID" 2>/dev/null; MPID=""; }
if grep -q '^DOUBLON=HARNESS_CLEANUP_STARTED' "$L_MARQ/.erreurs" 2>/dev/null; then
  ok "L3: la SECONDE emission du meme evenement a ete REFUSEE"
elif grep -q 'DOUBLON_NON_DETECTE' "$L_MARQ/.erreurs" 2>/dev/null; then
  echoue "L3: la duplication a ete acceptee — le marqueur n'est pas exclusif"
else
  echoue "L3: aucune trace de la tentative de duplication"
fi
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT"

# --- L4: LA PUBLICATION DU RESULTAT EST EXCLUSIVE -------------------------
# `os.link` echoue si la cible existe, et c'est ce qui rend la publication
# exclusive. RIEN NE L'EXERCAIT: le canal etait toujours un `mktemp -u`, donc
# toujours absent, et remplacer le lien par un ecrasement n'aurait fait rougir
# aucune assertion. Une surface non executee n'est pas un verdict.
#
# On pose donc un document ANTERIEUR sur le canal et l'on exige trois choses:
# qu'il survive intact, qu'un `.doublon` signale le refus, et que le lecteur
# refuse ensuite le canal — meme si le document en place est parfaitement forme.
echo "      -- L4: publication du resultat exclusive, jamais un ecrasement"
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp)"                      # IL EXISTE DEJA — c'est le sujet
L_OCCUPANT="OCCUPANT-$JETON"
{ echo "FORMAT=esc-wrapper-result/1"; echo "SCENARIO=$L_OCCUPANT"
  echo "JETON=$JETON"; echo "ETAT=ANTERIEUR"; } >"$L_RESULTAT"
chmod 0600 "$L_RESULTAT"
L_AVANT="$(sha256sum "$L_RESULTAT" | cut -d' ' -f1)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM"
attendre "le faux harnais pret (L4)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
attendre "le marqueur du wrapper (L4)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L4)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
kill -TERM "$L_WPID"
if attendre "le refus de publication (L4)" '[[ -f "$L_RESULTAT.doublon" ]]' 3000; then
  ok "L4: la seconde publication est REFUSEE et signalee (.doublon)"
  detail "$(head -1 "$L_RESULTAT.doublon")"
else
  echoue "L4: aucun .doublon — la seconde publication a ete acceptee en silence"
fi
[[ -n "$MPID" ]] && { kill -TERM "$MPID" 2>/dev/null; wait "$MPID" 2>/dev/null; MPID=""; }
if [[ "$(sha256sum "$L_RESULTAT" | cut -d' ' -f1)" == "$L_AVANT" ]]; then
  ok "L4: le document anterieur est INTACT — aucun ecrasement silencieux"
else
  echoue "L4: le document anterieur a ete ecrase"
  detail "attendu sha256 $L_AVANT"
  detail "contenu observe: $(tr '\n' ' ' <"$L_RESULTAT")"
fi
lire_canal "$L_RESULTAT" "esc-wrapper-result/1" "$L_OCCUPANT" "$JETON"
[[ "$CANAL_ETAT" == DUPLIQUE ]] \
  && ok "L4: le lecteur refuse le canal (DUPLIQUE) malgre un document bien forme" \
  || { echoue "L4: le lecteur rend $CANAL_ETAT, attendu DUPLIQUE"; detail "$CANAL_DIAG"; }
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT" "$L_RESULTAT.doublon"

# --- L5: UN PREDECESSEUR INCOMPLET ARRETE LA CHAINE -----------------------
# « Un predecesseur causal n'est valide que si son evenement est complet »
# etait implemente — `ESC_META_TRONQUE` — et exerce par aucun scenario. Le
# repertoire de HARNESS_TRAP_ENTERED existe, son `meta` est retire: le maillon
# suivant ne doit JAMAIS etre emis, et l'erreur doit dire « sans meta », pas
# « absent ». Les deux diagnostics designent des defauts differents.
echo "      -- L5: predecesseur incomplet, la chaine s'arrete au maillon casse"
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM" "ESC_META_TRONQUE=1"
attendre "le faux harnais pret (L5)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
attendre "le marqueur du wrapper (L5)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L5)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
kill -TERM "$L_WPID"
attendre "la fin du wrapper (L5)" '[[ -f "$L_RESULTAT" ]]' 3000 || exit 1
[[ -n "$MPID" ]] && { kill -TERM "$MPID" 2>/dev/null; wait "$MPID" 2>/dev/null; MPID=""; }
if grep -qx 'PREREQUIS_SANS_META=HARNESS_TRAP_ENTERED' "$L_MARQ/.erreurs" 2>/dev/null; then
  ok "L5: le predecesseur incomplet est nomme « sans meta », et non « absent »"
else
  echoue "L5: aucun PREREQUIS_SANS_META — un maillon incomplet a ete accepte"
  detail "erreurs: $(tr '\n' ' ' <"$L_MARQ/.erreurs" 2>/dev/null || echo '(fichier absent)')"
fi
if [[ -d "$L_MARQ/HARNESS_CLEANUP_STARTED" ]]; then
  echoue "L5: l'evenement suivant a ete emis malgre un predecesseur incomplet"
else
  ok "L5: le maillon suivant n'a PAS ete emis — la chaine s'arrete au maillon casse"
fi
if chaine_ok "$L_MARQ"; then
  echoue "L5: la chaine est declaree complete alors qu'un maillon est casse"
else
  ok "L5: la chaine est refusee, et le diagnostic distingue les deux causes"
  detail "$CHAINE_DIAG"
fi
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT"

# --- L6: UN HARNAIS QUI REFUSE DE MOURIR, ET UNE SEULE AUTORITE DE DELAI ---
# CE QUI EST EPROUVE ICI. `_arreter_enfant()` est la SEULE autorite de delai du
# systeme: elle signale le GROUPE, attend sa patience, puis escalade en SIGKILL.
# Tant qu'aucun harnais ne lui resistait, cette escalade n'etait qu'une
# intention: le premier TERM suffisait toujours, et le chemin KILL n'etait
# jamais parcouru. Une branche non executee n'est pas une branche verte.
#
# LE TEST NE BORNE RIEN. Il ne pose ni `timeout`, ni compteur, ni plafond
# propre: il observe le temps que l'escalade met a conclure et exige qu'il
# corresponde a la patience declaree. Un test qui imposerait son propre delai
# deviendrait une SECONDE autorite, et l'on ne saurait plus laquelle a tranche.
#
# AUCUN SUCCES PAR EXPIRATION. Trois faits POSITIFS sont exiges, pas une
# absence: la duree encadre la patience de 20 s, le code publie est celui d'un
# SIGKILL, et la descendance profonde a disparu.
echo "      -- L6: harnais qui ignore TERM — l'escalade doit trancher"
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM" "ESC_IGNORE_TERM=1" "ESC_DESCENDANCE=1"
attendre "le faux harnais pret (L6)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
L6_HPID="$(awk '{print $2}' "$L_MARQ/.harnais")"
attendre "le marqueur du wrapper (L6)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L6_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L6)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
attendre "la descendance du harnais (L6)" \
  '[[ -s "$L_MARQ/.descendance" ]] && grep -q "^PETIT_FILS=" "$L_MARQ/.descendance"' 300 || exit 1
L6_ENF="$(sed -n 's/^ENFANT=//p' "$L_MARQ/.descendance" | head -1)"
L6_PF="$(sed -n 's/^PETIT_FILS=//p' "$L_MARQ/.descendance" | head -1)"

# NON VACUITE, AVANT DE SIGNALER: la chaine existe vraiment, sur quatre niveaux,
# et tout le monde est dans le groupe du wrapper.
L6_MANQUE=()
for p in "$L6_HPID" "$L6_ENF" "$L6_PF"; do
  pg="$(ps -o pgid= -p "${p:-0}" 2>/dev/null | tr -d ' ')"
  [[ "$pg" == "$L6_WPID" ]] || L6_MANQUE+=("${p:-?}[${pg:-mort}]")
done
if (( ${#L6_MANQUE[@]} )); then
  echoue "L6: chaine incomplete avant le signal: ${L6_MANQUE[*]} — CHEMIN NON EXERCE"
  exit 1
fi
ok "L6: NON VACUITE — wrapper $L6_WPID > harnais $L6_HPID > enfant $L6_ENF > petit-fils $L6_PF"
[[ "$(ps -o ppid= -p "$L6_PF" 2>/dev/null | tr -d ' ')" == "$L6_ENF" ]] \
  && ok "L6: le petit-fils est a DEUX niveaux sous le harnais" \
  || echoue "L6: le petit-fils n'est pas ou on l'attend"

# LE SIGNAL VA A LA MATRICE: c'est `_sur_signal` puis `_arreter_enfant()` qu'on
# veut exercer, pas le relais du wrapper (deja couvert par L1).
L6_T0=$SECONDS
kill -TERM "$MPID"
attendre "la fin de l'escalade (L6)" '[[ -f "$L_RESULTAT" ]]' 6000 || exit 1
L6_DUREE=$(( SECONDS - L6_T0 ))
L6_MRC=0; [[ -n "$MPID" ]] && { wait "$MPID" 2>/dev/null || L6_MRC=$?; MPID=""; }

# LA PATIENCE DECLAREE EST DE 20 s AVANT SIGKILL. En deca, l'escalade n'aurait
# pas attendu; tres au-dela, elle ne serait pas bornee. Les deux sont rouges.
if (( L6_DUREE >= 20 && L6_DUREE < 45 )); then
  ok "L6: l'escalade a conclu en ${L6_DUREE}s — patience de 20 s tenue PUIS depassee"
else
  echoue "L6: duree ${L6_DUREE}s hors de [20, 45): la patience declaree n'est pas celle observee"
fi
L6_WRC="$(sed -n 's/^WRAPPER_RC=//p' "$L_RESULTAT")"
[[ "$L6_WRC" == "-9" ]] \
  && ok "L6: WRAPPER_RC=-9 — preuve DIRECTE du SIGKILL, pas une deduction" \
  || echoue "L6: WRAPPER_RC=$L6_WRC, attendu -9 (SIGKILL)"
# LE HARNAIS N'A PAS NETTOYE, ET C'EST LA PREUVE QU'IL A BIEN IGNORE TERM.
# S'il etait entre dans sa trap, c'est que le TERM l'avait atteint, et
# l'escalade n'aurait rien eu a trancher.
[[ -d "$L_MARQ/HARNESS_TRAP_ENTERED" ]] \
  && echoue "L6: le harnais est entre dans sa trap — il n'a pas ignore TERM, rien n'est exerce" \
  || ok "L6: le harnais n'a jamais nettoye: il a bien ignore TERM jusqu'au bout"
L6_SURV=()
for p in "$L6_WPID" "$L6_HPID" "$L6_ENF" "$L6_PF"; do
  [[ -n "$(vivants "$p")" ]] && L6_SURV+=("$p")
done
(( ${#L6_SURV[@]} == 0 )) \
  && ok "L6: aucun des quatre ne survit — l'escalade atteint la descendance profonde" \
  || echoue "L6: survivants apres escalade: ${L6_SURV[*]}"
# LES ZOMBIES SONT ATTENDUS, ET C'EST LEUR PERSISTANCE QUI ROUGIT. Le harnais
# est tue par SIGKILL: il ne peut plus moissonner ses propres descendants, qui
# passent donc par un etat Z le temps d'etre reparentes puis recoltes. Mesure
# au premier essai, sans attente: « zombies: 10022 10023 » — un rouge sur un
# etat TRANSITOIRE, c'est-a-dire un faux rouge. L'attente est BORNEE, et le
# moissonneur est NOMME plutot que suppose.
L6_ZOMB=""
n=0; while (( ++n <= 300 )); do
  L6_ZOMB="$(ps -o pid=,stat= -p "$L6_WPID" -p "$L6_HPID" -p "$L6_ENF" -p "$L6_PF" 2>/dev/null \
               | awk '$2 ~ /^Z/ {print $1}' | tr '\n' ' ')"
  [[ -z "${L6_ZOMB// /}" ]] && break
  L6_PPID="$(ps -o ppid= -p "${L6_ZOMB%% *}" 2>/dev/null | tr -d ' ')"
  sleep 0.1
done
if [[ -z "${L6_ZOMB// /}" ]]; then
  ok "L6: aucun zombie persistant parmi les quatre (convergence bornee)"
  [[ -n "${L6_PPID:-}" ]] && detail "dernier PPID observe: $L6_PPID ($(ps -o comm= -p "${L6_PPID}" 2>/dev/null || echo 'disparu — reparente et moissonne'))"
else
  echoue "L6: zombies persistants apres 30 s: $L6_ZOMB — personne ne les moissonne"
  detail "dernier PPID observe: ${L6_PPID:-inconnu}"
fi
GROUPE6="$(groupe_vivant "$L6_WPID")"
[[ -z "${GROUPE6// /}" ]] \
  && ok "L6: le groupe $L6_WPID est vide" \
  || echoue "L6: le groupe $L6_WPID contient encore: $GROUPE6"
# LES FIFO SONT RENDUES MEME APRES SIGKILL, parce que c'est la MATRICE qui
# possede leur repertoire — un wrapper tue ne retire rien.
L6_FIFOS="$(find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'esc-barriere-*' 2>/dev/null | tr '\n' ' ')"
[[ -z "${L6_FIFOS// /}" ]] \
  && ok "L6: aucune FIFO residuelle — la matrice a rendu le repertoire de barriere" \
  || { echoue "L6: repertoire(s) de barriere subsistant(s): $L6_FIFOS"
       detail "un wrapper tue ne nettoie pas: le proprietaire doit etre la matrice"; }
detail "MATRIX_RC=$L6_MRC, rapporte separement et jamais utilise comme preuve"
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT"

# --- L7: LA FENETRE ENTRE LA FIN DU HARNAIS ET LA PUBLICATION DU RESULTAT --
# LA FENETRE. Une fois le harnais fini, la matrice a encore une sequence
# TERMINALE a executer: publier le code du wrapper, puis rendre le repertoire de
# barriere. C'est le SEUL endroit ou le code du wrapper soit observable — la
# matrice sort ensuite avec le sien.
#
# LE DEFAUT, MESURE AVANT CORRECTION. Un TERM recu dans cette fenetre
# declenchait `_sur_signal`, donc `Interruption`, et le canal n'etait JAMAIS
# ecrit. La matrice imprimait pourtant un verdict partiel parfaitement lisible:
# rien ne signalait la perte. Sonde dediee: « RESULTAT PERDU », code 143.
#
# ET UN MASQUE POSE TROP BAS NE SUFFISAIT PAS. Place juste avant l'ecriture, il
# laissait decouverte toute la portion qui le precede — meme mesure, meme perte.
# Ce qui doit etre insecable, c'est la sequence terminale ENTIERE.
#
# DEUX PROPRIETES, ET LA SECONDE EST CELLE QUI DISTINGUE BLOQUER D'IGNORER:
#   * le resultat EST publie malgre le signal;
#   * le signal N'EST PAS PERDU — il est delivre des le masque leve, et la
#     matrice sort en 143. Un `SIG_IGN` aurait publie le resultat ET avale
#     l'interruption, laissant la campagne continuer comme si de rien n'etait.
echo "      -- L7: signal entre la fin du harnais et la publication du resultat"
L_MARQ="$(mktemp -d)"; L_JOUR="$(mktemp)"; L_TEM="$(canal_neuf temoin-L)"
L_RESULTAT="$(mktemp -u)"; L7_FEN="$(canal_neuf fenetre-L7)"
lancer_L "$L_MARQ" "$L_JOUR" "$L_TEM" "ESC_LENTEUR=1" \
  "ESC_MUTATION_PAUSE_RESULTAT=30" "ESC_MUTATION_RESULTAT_TEMOIN=$L7_FEN"
attendre "le faux harnais pret (L7)" '[[ -s "$L_MARQ/.harnais" ]]' 3000 || exit 1
attendre "le marqueur du wrapper (L7)" '[[ -s "$L_TEM" ]]' 3000 \
  '[[ -f "$L_TEM.doublon" ]]' \
  "le wrapper a REFUSE de publier — le canal existait deja (voir <canal>.doublon); un canal doit etre un nom LIBRE" || exit 1
L7_WPID="$(sed -n 's/^WRAPPER_PID=//p' "$L_TEM")"
attendre "l'attente du wrapper armee (L7)" '[[ -f "$L_MARQ/WRAPPER_WAITING/meta" ]]' 3000 || exit 1
kill -TERM "$L7_WPID"                    # le harnais nettoie, puis sort
attendre "l'entree dans la fenetre terminale (L7)" '[[ -s "$L7_FEN" ]]' 3000 || exit 1
if [[ -f "$L_RESULTAT" ]]; then
  echoue "L7: le resultat est deja publie: la fenetre visee n'est pas celle-la"
else
  ok "L7: NON VACUITE — la matrice est DANS sa sequence terminale, resultat non encore publie"
fi
kill -TERM "$MPID"                       # LE SIGNAL TOMBE DANS LA FENETRE
L7_MRC=0; wait "$MPID" 2>/dev/null || L7_MRC=$?; MPID=""
if [[ -f "$L_RESULTAT" ]]; then
  ok "L7: le resultat est PUBLIE malgre le signal recu dans la fenetre"
  detail "WRAPPER_RC=$(sed -n 's/^WRAPPER_RC=//p' "$L_RESULTAT")"
else
  echoue "L7: RESULTAT PERDU — le signal a interrompu la sequence terminale"
fi
# BLOQUER N'EST PAS IGNORER. Si le signal avait ete ignore, la matrice serait
# sortie par son chemin normal et n'aurait pas rendu 143.
[[ "$L7_MRC" == "143" ]] \
  && ok "L7: la matrice rend 143 — le signal a ete DIFFERE, pas avale" \
  || echoue "L7: la matrice rend $L7_MRC, attendu 143: le signal a ete perdu"
rm -rf "$L_MARQ" "$L_JOUR" "$L_TEM" "$L_RESULTAT" "$L7_FEN"

# ==========================================================================
# M. BASELINE CONTAMINEE MAIS STABLE — refusee pour la bonne raison
# ==========================================================================
# FIXTURE PERMANENTE, pas un script de mesure jetable. Elle etablit la seule
# chose qui distingue « stable » de « exterieur au test »: une ressource
# parfaitement immobile, mais enregistree comme appartenant a un scenario
# anterieur, doit faire REFUSER la baseline.
echo "      -- M. baseline contaminee mais stable: refus par propriete"
M_APP="esc-m-$JETON"; M_C1=778899; M_C2=112233
if ! session_creer M "$M_APP" "$M_C1" "$M_C2"; then
  echoue "M: le temoin n'a pas pu etre cree — scenario non exerce"
  detail "$SESSION_DIAG"
else
  M_CLIENT="$SESSION_CLIENT"; M_BACKEND="$SESSION_BACKEND"
  # LE MENSONGE EST POSE ICI, ET IL EST DELIBERE. Le manifeste annonce
  # `NETTOYE` alors que le backend vit et que le verrou tient. C'est le seul
  # contre-exemple qui separe « etat terminal declare » de « absence reelle »:
  # si `b0_contaminee()` se contentait de lire l'etat, elle accepterait.
  session_falsifier_nettoye M
  ok "M: temoin enregistre au manifeste (backend $M_BACKEND, verrou $M_C1/$M_C2)"
  detail "manifeste M falsifie: ETAT=$(sed -n 's/^ETAT=//p' "$MANIFESTES/M") alors que la ressource vit"
  m_a="$(empreinte_verrous)"; sleep 0.6; m_b="$(empreinte_verrous)"
  [[ "$m_a" == "$m_b" ]] \
    && ok "M: la baseline est STABLE (deux lectures identiques)" \
    || echoue "M: baseline instable — le contre-exemple ne porte pas"
  if b0_contaminee; then
    ok "M: baseline REFUSEE malgre sa stabilite ET malgre l'etat NETTOYE — $B0_DIAG"
    grep -q "possede encore le backend $M_BACKEND" <<<"$B0_DIAG" \
      && ok "M: le refus nomme l'identite revalidee, pas l'etat declare" \
      || { echoue "M: le refus ne porte pas sur l'identite revalidee"
           detail "diagnostic obtenu: $B0_DIAG" ; }
  else
    echoue "M: baseline stable ACCEPTEE alors qu'elle appartient au scenario M"
    detail "un manifeste annoncant NETTOYE a ete cru sur parole"
  fi
  # NETTOYAGE EXACT, PAR LE MEME CHEMIN QUE LES AUTRES. `session_fermer` termine
  # l'identite possedee puis exige la double absence avant de publier `NETTOYE`
  # — cette fois la publication est meritee, et le manifeste RESTE en place:
  # c'est lui qui doit ensuite laisser passer la baseline.
  if session_fermer M "$M_BACKEND" "$M_APP" "$M_C1" "$M_C2"; then
    M_BACKEND=""
    ok "M: temoin nettoye, NETTOYE publie apres double absence constatee"
  else
    echoue "M: le temoin n'a pas pu etre nettoye — $SESSION_DIAG"
  fi
  kill "$M_CLIENT" 2>/dev/null; wait "$M_CLIENT" 2>/dev/null; M_CLIENT=""
  b0_contaminee \
    && echoue "M: la baseline reste refusee apres nettoyage — $B0_DIAG" \
    || ok "M: apres nettoyage, la baseline redevient acceptable (manifeste conserve)"
fi

# ==========================================================================
# N. LES CINQ ETATS DU CANAL — aucun invalide converti en succes
# ==========================================================================
echo "      -- N. canaux: cinq etats distincts, aucun converti en succes"
N_D="$(mktemp -d)"; N_F="$N_D/canal"
attendu() {   # attendu <libelle> <etat-attendu>
  local quoi="$1" att="$2"
  lire_canal "$N_F" "esc-erreurs/1" N "$JETON" COUNT
  [[ "$CANAL_ETAT" == "$att" ]] \
    && ok "N: $quoi -> $CANAL_ETAT" \
    || { echoue "N: $quoi -> $CANAL_ETAT, attendu $att"; detail "$CANAL_DIAG"; }
}
rm -f "$N_F" "$N_F.doublon";                                    attendu "canal absent" ABSENT
: >"$N_F"; chmod 0600 "$N_F";                                   attendu "canal vide" VIDE_OU_NON_VERSIONNE
printf 'FORMAT=esc-erreurs/9\n' >"$N_F"; chmod 0600 "$N_F";     attendu "version inconnue" VIDE_OU_NON_VERSIONNE
printf 'FORMAT=esc-erreurs/1\nSCENARIO=N\n' >"$N_F"; chmod 0600 "$N_F"
                                                                attendu "champs manquants" TRONQUE_OU_MALFORME
printf 'FORMAT=esc-erreurs/1\nSCENARIO=N\nJETON=%s\nETAT=OK\nCOUNT=zero\n' "$JETON" >"$N_F"
chmod 0600 "$N_F";                                              attendu "COUNT non numerique" TRONQUE_OU_MALFORME
printf 'FORMAT=esc-erreurs/1\nSCENARIO=N\nJETON=%s\nETAT=OK\nCOUNT=0\n' "$JETON" >"$N_F"
chmod 0644 "$N_F";                                              attendu "permissions 0644" PERMISSIONS_INVALIDES
grep -q "attendu 0600, observe 0644" <<<"$CANAL_DIAG" \
  && ok "N: le diagnostic nomme le mode attendu et le mode observe" \
  || echoue "N: diagnostic de permissions imprecis: $CANAL_DIAG"
chmod 0600 "$N_F"; : >"$N_F.doublon";                           attendu "publication dupliquee" DUPLIQUE
rm -f "$N_F.doublon"
attendu "document versionne, COUNT=0" VALIDE
[[ "$CANAL_COUNT" == "0" ]] \
  && ok "N: zero erreur est PUBLIE explicitement (COUNT=0), jamais deduit d'un fichier absent" \
  || echoue "N: COUNT lu « $CANAL_COUNT », attendu 0"
rm -rf "$N_D"


echo
[[ $KO -eq 0 ]] \
  && echo "    La matrice rend un verdict, et le test prouve ce qu'il affirme." \
  || echo "    La matrice ne meurt pas proprement." >&2
sortir $KO
