#!/usr/bin/env bash
#
# EUROSTRUCT — LA RECETTE SUR UNE BASE HEBERGEE (STAGING SUPABASE)
#
#   db/test/recette_supabase_staging.sh diagnostic     # lecture seule, defaut
#   EUROSTRUCT_RECETTE_CIBLE=staging \
#   db/test/recette_supabase_staging.sh executer       # les sept etapes
#
# SEPT ETAPES, ET CHACUNE REND UN RESULTAT DISTINCT
# --------------------------------------------------
#   EXECUTEE      l'etape a tourne et ce qu'elle devait etablir est etabli
#   ECHOUEE       l'etape a tourne et ne l'a pas etabli — la raison est nommee
#   NON EXECUTEE  l'etape n'a pas tourne: un acces manque, une etape amont a
#                 echoue, ou le mode est le diagnostic — la raison est nommee
#
# Un compte rendu qui confondrait les deux dernieres ferait passer « personne
# n'a essaye » pour « ca marche ». Le code de sortie les separe aussi:
#
#   0  les sept etapes EXECUTEES                (mode executer)
#      ou: tous les acces sont la, rien manque  (mode diagnostic)
#   1  au moins une etape ECHOUEE
#   2  REFUSEE — mode executer sans EUROSTRUCT_RECETTE_CIBLE=staging
#   4  NON EXECUTEE — un acces manque pour l'etape 0, ou en diagnostic il en
#      manque au moins un; ils sont listes
#   5  PARTIELLE — aucune etape n'a echoue, mais au moins une n'a pas tourne
#
# LE DIAGNOSTIC NE MUTE RIEN, MEME AVEC TOUS LES ACCES
# -----------------------------------------------------
# Il ouvre des connexions pour LIRE: les attributs du role connecte, l'etat
# d'activation, le JWKS. Il n'appelle ni la sonde (qui cree des roles), ni la
# commande de deploiement autrement qu'en `--dry-run`, ni aucune route qui
# ecrit. `recette_supabase_staging_selftest.sh` le mesure: un instantane du
# catalogue avant et apres, identiques.
#
# CE QUE CHAQUE ETAPE EXIGE DEPEND DU SCENARIO
# ---------------------------------------------
# Un stockage local ne reclame aucun secret S3. Une base sans cible de
# restauration ne bloque pas les six autres etapes. Les variables sont celles
# que le produit lit lui-meme — `ESC_PLAN_URL` et `ESC_MIGRATOR_URL` pour la
# commande de deploiement, `EUROSTRUCT_DATABASE_URL` et `EUROSTRUCT_SUPABASE_*`
# pour l'API — sans couche de traduction. Voir docs/DEPLOIEMENT_BASE_HEBERGEE.md
# pour la liste, et pour ce qui est secret, public, ou un choix.
#
# AUCUN SECRET DANS `argv`, AUCUN DANS CETTE SORTIE. Les DSN sont decoupees en
# variables libpq dans un sous-shell; les jetons passent par un fichier
# d'en-tete en 0600 (`curl -H @fichier`); les corps JSON par `-d @fichier`.
#
# CE QUE LA RECETTE LAISSE SUR LE STAGING: une organisation et un projet
# « Recette technique », une etude exploratoire, deux livrables, et — si les
# jetons sont ceux de comptes d'ESSAI — UNE decision consommee sur UN
# parametre. Elle ne detruit rien: un staging garde ses traces, c'est a cela
# qu'il sert.
set -uo pipefail
set +x

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$(dirname "$HERE")")"
MODE="${1:-diagnostic}"
case "$MODE" in diagnostic|executer) ;; *)
  echo "usage: recette_supabase_staging.sh [diagnostic|executer]" >&2; exit 2 ;;
esac
EXECUTER=0; [[ "$MODE" == "executer" ]] && EXECUTER=1

PORT_API="${EUROSTRUCT_RECETTE_PORT_API:-8047}"
TMP="$(mktemp -d)"; chmod 700 "$TMP"
PID_API=""
nettoyer() { [[ -n "$PID_API" ]] && kill "$PID_API" 2>/dev/null; rm -rf "$TMP"; }
trap nettoyer EXIT

# ---------------------------------------------------------------------------
# LE TABLEAU DES RESULTATS
# ---------------------------------------------------------------------------
NOMS=("0 plan de controle" "1 migrations" "2 authentification"
      "3 confirmations a quatre yeux" "4 etude belge (stricte, exploratoire)"
      "5 livrables PDF et DXF" "6 sauvegarde et restauration"
      "7 relecture apres redemarrage")
ETATS=(); DETAILS=()
for _ in "${NOMS[@]}"; do ETATS+=("NON EXECUTEE"); DETAILS+=("non tentee"); done
poser() { ETATS[$1]="$2"; DETAILS[$1]="$3"; }
executee() { poser "$1" "EXECUTEE" "$2"; }
echouee()  { poser "$1" "ECHOUEE" "$2"; }
non_exec() { poser "$1" "NON EXECUTEE" "$2"; }

est_defini() { [[ -n "${!1:-}" ]]; }
MANQUANTS=()
exige() {   # exige <variable> <ce que c'est>
  est_defini "$1" && return 0
  MANQUANTS+=("$1 — $2"); return 1
}

# ---------------------------------------------------------------------------
# LES DSN, DECOUPEES DANS UN SOUS-SHELL — JAMAIS EN ARGUMENT
# ---------------------------------------------------------------------------
# `avec_url <variable-d-url> <commande...>`: execute la commande avec PGHOST,
# PGPORT, PGUSER, PGPASSWORD, PGDATABASE et PGSSLMODE poses depuis l'URL.
avec_url() {
  local var="$1"; shift
  local decoupe
  decoupe="$(URL="${!var}" python3 - <<'PY'
import os, shlex, sys
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["URL"])
if u.scheme not in ("postgres", "postgresql") or not u.hostname or not u.username:
    sys.exit(2)
q = parse_qs(u.query)
for k, v in {"PGHOST": u.hostname, "PGPORT": str(u.port or 5432),
             "PGUSER": unquote(u.username), "PGPASSWORD": unquote(u.password or ""),
             "PGDATABASE": unquote(u.path.lstrip("/")),
             "PGSSLMODE": q.get("sslmode", ["prefer"])[0]}.items():
    print(f"export {k}={shlex.quote(v)}")
PY
)" || return 2
  while IFS= read -r l; do
    [[ -z "$l" || "$l" =~ ^export\ PG(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]] \
      || return 2
  done <<<"$decoupe"
  ( eval "$decoupe"; unset PGSERVICE PGSERVICEFILE PGHOSTADDR PGPASSFILE PGOPTIONS
    "$@" )
}
sql() {   # sql <variable-d-url> <requete>  — une valeur, sans espaces
  avec_url "$1" psql -X -q -tA -v ON_ERROR_STOP=1 -c "$2" 2>/dev/null | tr -d ' \r'
}

# ---------------------------------------------------------------------------
# LES APPELS A L'API LOCALE, JETON PAR FICHIER
# ---------------------------------------------------------------------------
entete_pour() {   # entete_pour <A|B> — ecrit $TMP/entete_<X>
  local var="EUROSTRUCT_STAGING_JETON_$1"
  printf 'Authorization: Bearer %s\n' "${!var}" > "$TMP/entete_$1"
  chmod 600 "$TMP/entete_$1"
}
api() {           # api <A|B|-> <methode> <chemin> [fichier-corps] -> code; corps dans $TMP/reponse
  local qui="$1" methode="$2" chemin="$3" corps="${4:-}"
  local -a opts=(-sS -o "$TMP/reponse" -w '%{http_code}' -X "$methode"
                 -H 'Content-Type: application/json' --max-time 120)
  [[ "$qui" != "-" ]] && opts+=(-H @"$TMP/entete_$qui")
  [[ -n "$corps" ]] && opts+=(-d @"$corps")
  curl "${opts[@]}" "http://127.0.0.1:${PORT_API}${chemin}" 2>/dev/null
}
json() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))" "$TMP/reponse" "$1" 2>/dev/null; }

# ===========================================================================
# CE QUE CHAQUE ETAPE EXIGE — VERIFIE D'ABORD, ET PAR SCENARIO
# ===========================================================================
exige ESC_PLAN_URL "DSN du plan de controle (secret)"
exige ESC_MIGRATOR_URL "DSN du migrateur (secret)"
ETAPE0_OK=$?; [[ ${#MANQUANTS[@]} -eq 0 ]] && ETAPE0_OK=0 || ETAPE0_OK=1

exige EUROSTRUCT_DATABASE_URL "DSN du login applicatif (secret)"
exige EUROSTRUCT_SUPABASE_JWKS_URL "URL du JWKS (publique)"
exige EUROSTRUCT_SUPABASE_ISSUER "emetteur attendu, iss (publique)"
: "${EUROSTRUCT_SUPABASE_AUDIENCE:=authenticated}"

STOCKAGE="${EUROSTRUCT_STORAGE_BACKEND:-local}"
case "$STOCKAGE" in
  local) : "${EUROSTRUCT_STORAGE_DIR:=$TMP/livrables}"; mkdir -p "$EUROSTRUCT_STORAGE_DIR" ;;
  s3)
    exige EUROSTRUCT_S3_ENDPOINT "point d'entree du magasin (publique)"
    exige EUROSTRUCT_S3_BUCKET "compartiment (choix)"
    exige EUROSTRUCT_S3_ACCESS_KEY_ID "identifiant d'acces S3 (secret)"
    exige EUROSTRUCT_S3_SECRET_ACCESS_KEY "secret d'acces S3 (secret)" ;;
  *) echo "REFUS: EUROSTRUCT_STORAGE_BACKEND=$STOCKAGE inconnu (local|s3)." >&2; exit 2 ;;
esac

JETONS=1
est_defini EUROSTRUCT_STAGING_JETON_A || JETONS=0
est_defini EUROSTRUCT_STAGING_JETON_B || JETONS=0
ESSAI="${EUROSTRUCT_RECETTE_JETONS_D_ESSAI:-}"
RESTAURATION=0; est_defini EUROSTRUCT_STAGING_RESTORE_URL && RESTAURATION=1
# LE ROLE QUI SAUVEGARDE. Par defaut le migrateur — qui ne voit PAS les
# tables sous RLS forcee, et l'etape 6 le dira. Un role dote de BYPASSRLS par
# le fournisseur se declare ici.
SAUVEGARDE_URL="${EUROSTRUCT_STAGING_BACKUP_URL:-${ESC_MIGRATOR_URL:-}}"
AUTO=(); [[ "${EUROSTRUCT_RECETTE_TLS_AUTO_HEBERGE:-}" == "oui" ]] && AUTO=(--auto-heberge)

echo "EUROSTRUCT — recette sur base hebergee, mode: $MODE"
echo "  stockage: $STOCKAGE | jetons A et B: $([[ $JETONS -eq 1 ]] && echo presents || echo absents)" \
     "| cible de restauration: $([[ $RESTAURATION -eq 1 ]] && echo presente || echo absente)"
echo

rendre_tableau() {
  echo
  printf '  %-40s %-13s %s\n' "ETAPE" "RESULTAT" "DETAIL"
  printf '  %-40s %-13s %s\n' "----------------------------------------" "-------------" "------"
  local i
  for i in "${!NOMS[@]}"; do
    printf '  %-40s %-13s %s\n' "${NOMS[$i]}" "${ETATS[$i]}" "${DETAILS[$i]}"
  done
  echo
}
verdict() {
  rendre_tableau
  local i echoues=0 non=0
  for i in "${!ETATS[@]}"; do
    [[ "${ETATS[$i]}" == "ECHOUEE" ]] && ((echoues++))
    [[ "${ETATS[$i]}" == "NON EXECUTEE" ]] && ((non++))
  done
  echo "  SUPABASE_UNVERIFIED reste vrai tant que les sept etapes n'ont pas ete"
  echo "  EXECUTEES sur une instance reelle, et que ce compte rendu n'est pas au depot."
  if ((echoues > 0)); then echo "  VERDICT: ECHEC ($echoues etape(s) echouee(s))"; exit 1; fi
  if ((non > 0));     then echo "  VERDICT: PARTIELLE ($non etape(s) non executee(s))"; exit 5; fi
  echo "  VERDICT: COMPLETE — les sept etapes ont tourne, toutes etablies."; exit 0
}

# ===========================================================================
# MODE DIAGNOSTIC — LECTURE SEULE, ET RIEN D'AUTRE
# ===========================================================================
if ((EXECUTER == 0)); then
  if ((ETAPE0_OK != 0)); then
    non_exec 0 "acces manquant(s): ${MANQUANTS[*]}"
  else
    attr="$(sql ESC_PLAN_URL "select rolsuper||'/'||rolcreaterole||'/'||rolcreatedb||'/'||rolbypassrls
                               from pg_roles where rolname = current_user")"
    if [[ -n "$attr" ]]; then
      non_exec 0 "diagnostic: plan connecte; super/createrole/createdb/bypassrls=$attr. La sonde (creation et destruction de roles) ne tourne qu'en mode executer."
    else
      echouee 0 "le plan de controle ne se connecte pas (lecture seule)."
    fi
    if bash "$RACINE/tools/deploy_eurostruct.sh" --dry-run "${AUTO[@]}" >"$TMP/dry.log" 2>&1; then
      etat="$(sql ESC_PLAN_URL "select case when to_regproc('normative_activation_state') is null then 'aucun sceau' else normative_activation_state() end")"
      non_exec 1 "diagnostic: --dry-run ok (les deux acteurs se connectent); etat: ${etat:-illisible}. Rien n'est applique en diagnostic."
    else
      echouee 1 "--dry-run refuse: $(grep -m1 -E 'ECHEC|REFUS|DEPLOYMENT_' "$TMP/dry.log" | cut -c1-140)"
    fi
  fi
  if est_defini EUROSTRUCT_SUPABASE_JWKS_URL; then
    n="$(curl -fsS --max-time 10 "$EUROSTRUCT_SUPABASE_JWKS_URL" 2>/dev/null \
         | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("keys",[])))' 2>/dev/null)"
    if [[ -n "$n" && "$n" != "0" ]]; then
      non_exec 2 "diagnostic: JWKS joignable, $n cle(s). L'API n'est demarree qu'en mode executer."
    else
      echouee 2 "le JWKS ne repond pas ou ne porte aucune cle."
    fi
  fi
  ((JETONS)) || non_exec 3 "jetons EUROSTRUCT_STAGING_JETON_A et _B absents (comptes d'essai distincts)."
  ((JETONS)) && [[ "$ESSAI" != "oui" ]] && non_exec 3 "jetons presents; EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui requis: cette etape CONSOMME une decision sur un parametre."
  ((JETONS)) && [[ "$ESSAI" == "oui" ]] && non_exec 3 "diagnostic: executable (jetons presents, declares d'essai)."
  ((JETONS)) && non_exec 4 "diagnostic: executable." || non_exec 4 "jeton A absent."
  ((JETONS)) && non_exec 5 "diagnostic: executable (stockage $STOCKAGE)." || non_exec 5 "jeton A absent."
  ((RESTAURATION)) && non_exec 6 "diagnostic: executable." || non_exec 6 "EUROSTRUCT_STAGING_RESTORE_URL absente (cible de restauration distincte)."
  ((JETONS)) && non_exec 7 "diagnostic: executable." || non_exec 7 "jeton A absent."
  rendre_tableau
  if ((${#MANQUANTS[@]} > 0)) || ((JETONS == 0)) || ((RESTAURATION == 0)); then
    echo "  NON EXECUTEE — il manque, pour que les sept etapes puissent tourner:"
    for m in "${MANQUANTS[@]}"; do echo "    - $m"; done
    ((JETONS)) || echo "    - EUROSTRUCT_STAGING_JETON_A / _B — jetons d'acces de DEUX comptes d'essai distincts (secrets, courte duree)"
    ((JETONS)) && [[ "$ESSAI" != "oui" ]] && echo "    - EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui — les jetons appartiennent a des comptes d'essai"
    ((RESTAURATION)) || echo "    - EUROSTRUCT_STAGING_RESTORE_URL — DSN d'une base VIDE, distincte, pour la restauration (secret)"
    echo "  Aucune mutation: le diagnostic n'ecrit rien."
    exit 4
  fi
  echo "  Tous les acces sont la. Le diagnostic n'a rien ecrit."
  echo "  Pour executer: EUROSTRUCT_RECETTE_CIBLE=staging $0 executer"
  exit 0
fi

# ===========================================================================
# MODE EXECUTER — CONSENTEMENT D'ABORD
# ===========================================================================
if [[ "${EUROSTRUCT_RECETTE_CIBLE:-}" != "staging" ]]; then
  echo "  REFUSEE — les sept etapes ECRIVENT sur l'instance visee (roles de sonde," >&2
  echo "  sceau et migrations, organisation, etude, livrables, une decision)." >&2
  echo "  Relancer avec EUROSTRUCT_RECETTE_CIBLE=staging. Rien n'a ete touche." >&2
  exit 2
fi
if ((ETAPE0_OK != 0)); then
  non_exec 0 "acces manquant(s): ${MANQUANTS[*]}"
  rendre_tableau; echo "  NON EXECUTEE — sans plan de controle, rien ne peut tourner."; exit 4
fi

# --- 0. LE PLAN DE CONTROLE ------------------------------------------------
echo "==> 0. plan de controle — db/test/supabase_probe.sh"
if DATABASE_URL="$ESC_PLAN_URL" EUROSTRUCT_PROBE_TARGET=staging \
   bash "$HERE/supabase_probe.sh" >"$TMP/sonde.log" 2>&1; then
  executee 0 "les quatre capacites du plan de controle sont confirmees."
else
  rc=$?
  case $rc in
    1) echouee 0 "une capacite manque: $(grep -m1 -iE 'manque|MISSING|non ' "$TMP/sonde.log" | cut -c1-120)" ;;
    3) echouee 0 "des roles de sonde subsistent (code 3): a nettoyer avant de continuer." ;;
    *) echouee 0 "sonde inconclusive (code $rc): $(grep -m1 -E 'INCONCLUSIVE|REFUS' "$TMP/sonde.log" | cut -c1-120)" ;;
  esac
fi

# --- 1. MIGRATIONS — LA COMMANDE OFFICIELLE -------------------------------
echo "==> 1. migrations — tools/deploy_eurostruct.sh"
if [[ "${ETATS[0]}" != "EXECUTEE" ]]; then
  non_exec 1 "l'etape 0 n'est pas etablie."
elif bash "$RACINE/tools/deploy_eurostruct.sh" "${AUTO[@]}" >"$TMP/deploi.log" 2>&1; then
  etat="$(sql ESC_PLAN_URL "select normative_activation_state()")"
  if [[ "$etat" != "ACTIVE" ]]; then
    echouee 1 "commande en 0 mais etat « ${etat:-illisible} »."
  # LE REFERENTIEL DES ANNEXES FAIT PARTIE DU DEPLOIEMENT. Sans lui, la base
  # est ACTIVE et aucun projet ne peut etre cree: « aucune annexe nationale
  # en vigueur ». Le seed est idempotent (`on conflict do nothing`) et
  # s'applique par le MIGRATEUR, proprietaire des tables — comme
  # `deploy/initialiser.sh` le fait pour la composition.
  elif ! avec_url ESC_MIGRATOR_URL psql -X -q -v ON_ERROR_STOP=1 \
         -f "$RACINE/db/seed/0001_ndp.sql" >"$TMP/seed.log" 2>&1; then
    echouee 1 "base ACTIVE, mais le referentiel des annexes (db/seed/0001_ndp.sql) n'a pas pu etre pose: $(grep -m1 -i error "$TMP/seed.log" | cut -c1-120)"
  else
    n="$(sql ESC_MIGRATOR_URL "select count(*) from national_annexes")"
    # LE LOGIN APPLICATIF ENTRE DANS LE BACKEND D'AUTORITE, PAR LE PLAN DE
    # CONTROLE — le geste que `deploy/initialiser.sh` fait a l'etape 5. Sans
    # lui, `/ready` est vert et chaque primitive refuse « cette operation
    # n'est pas permise a l'identite presentee »: mesure par l'auto-test.
    APP_USER="$(URL="$EUROSTRUCT_DATABASE_URL" python3 -c 'import os; from urllib.parse import urlsplit, unquote; print(unquote(urlsplit(os.environ["URL"]).username or ""))' 2>/dev/null)"
    if [[ ! "$APP_USER" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
      echouee 1 "base ACTIVE, $n annexe(s); mais le login applicatif est illisible dans EUROSTRUCT_DATABASE_URL."
    else
      # PAR L'ENTREE STANDARD, PAS PAR `-c`: psql n'interpole pas `:"app"`
      # dans une commande passee en argument — mesure par l'auto-test, ou
      # l'octroi echouait en silence sur une erreur de syntaxe.
      printf 'grant eurostruct_authority_backend to :"app";\n' \
        | avec_url ESC_PLAN_URL psql -X -q -v ON_ERROR_STOP=1 -v app="$APP_USER" \
            >"$TMP/admission.log" 2>&1
      if [[ "$(sql ESC_PLAN_URL "select pg_has_role('$APP_USER','eurostruct_authority_backend','member')")" == "t" ]]; then
        executee 1 "base ACTIVE; referentiel: $n annexe(s); « $APP_USER » admis dans eurostruct_authority_backend."
      else
        echouee 1 "base ACTIVE, $n annexe(s); mais « $APP_USER » n'a pas pu etre admis dans eurostruct_authority_backend (le plan de controle doit pouvoir l'accorder): $(grep -m1 -iE 'ERROR|FATAL' "$TMP/admission.log" | cut -c1-120)"
      fi
    fi
  fi
else
  rc=$?
  echouee 1 "deploy_eurostruct.sh a rendu $rc: $(grep -m1 -oE 'DEPLOYMENT_[A-Z_]+|ACTIVE_SCHEMA_UPGRADE_REQUIRED|MIGRATION_[A-Z_]+' "$TMP/deploi.log" || echo 'voir le journal')"
fi

# --- 2. AUTHENTIFICATION — L'API DEMARREE ICI, CONTRE LE STAGING -----------
echo "==> 2. authentification — l'API locale contre la base hebergee, /ready"
BUILD_SHA="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || echo "")"
demarrer_api() {
  env EUROSTRUCT_DATABASE_URL="$EUROSTRUCT_DATABASE_URL" \
      EUROSTRUCT_SUPABASE_JWKS_URL="$EUROSTRUCT_SUPABASE_JWKS_URL" \
      EUROSTRUCT_SUPABASE_ISSUER="$EUROSTRUCT_SUPABASE_ISSUER" \
      EUROSTRUCT_SUPABASE_AUDIENCE="$EUROSTRUCT_SUPABASE_AUDIENCE" \
      EUROSTRUCT_JWT_ALGORITHMS="${EUROSTRUCT_JWT_ALGORITHMS:-RS256}" \
      EUROSTRUCT_STORAGE_BACKEND="$STOCKAGE" \
      EUROSTRUCT_STORAGE_DIR="${EUROSTRUCT_STORAGE_DIR:-}" \
      EUROSTRUCT_BUILD_SHA="$BUILD_SHA" \
      python3 -m uvicorn eurostruct_api.app:app --host 127.0.0.1 --port "$PORT_API" \
        --log-level warning >"$TMP/api.log" 2>&1 &
  PID_API=$!
  local i
  for ((i = 0; i < 80; i++)); do
    kill -0 "$PID_API" 2>/dev/null || return 1
    curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT_API/health" 2>/dev/null && return 0
    sleep 0.5
  done
  return 1
}
if [[ "${ETATS[1]}" != "EXECUTEE" ]]; then
  non_exec 2 "l'etape 1 n'est pas etablie."
elif [[ ${#MANQUANTS[@]} -gt 0 ]]; then
  non_exec 2 "acces manquant(s): ${MANQUANTS[*]}"
elif ! demarrer_api; then
  echouee 2 "l'API n'a pas demarre sur le port $PORT_API: $(grep -m1 -iE 'error|refus' "$TMP/api.log" | cut -c1-120)"
else
  curl -sS --max-time 30 -o "$TMP/reponse" "http://127.0.0.1:$PORT_API/ready" 2>/dev/null
  if [[ "$(json 'd["ready"]')" == "True" ]]; then
    executee 2 "/ready vert: JWKS joignable, base ouverte, provider constructible."
  else
    echouee 2 "/ready rouge: $(json '",".join(v["nom"] for v in d["verifications"] if not v["ok"])')"
  fi
fi

# --- 3. LE QUATRE-YEUX, SUR UN PARAMETRE, AVEC DEUX COMPTES D'ESSAI --------
echo "==> 3. confirmations a quatre yeux — un parametre, comptes d'essai"
if [[ "${ETATS[2]}" != "EXECUTEE" ]]; then
  non_exec 3 "l'etape 2 n'est pas etablie."
elif ((JETONS == 0)); then
  non_exec 3 "jetons EUROSTRUCT_STAGING_JETON_A et _B absents."
elif [[ "$ESSAI" != "oui" ]]; then
  non_exec 3 "EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui requis: cette etape consomme une decision reelle sur le staging."
else
  entete_pour A; entete_pour B
  code="$(api - GET /v1/ndp/BE/parameters)"
  CLE="$(json '[p for p in d["parameters"] if not p["usable_in_strict_mode"] and p.get("source_doc_id")][0]["key"]')"
  DOC="$(json '[p for p in d["parameters"] if p["key"]=="'"$CLE"'"][0]["source_doc_id"]')"
  FOLIO="$(json '[p for p in d["parameters"] if p["key"]=="'"$CLE"'"][0].get("source_page") or 1')"
  EDITION="$(json '[p for p in d["parameters"] if p["key"]=="'"$CLE"'"][0]["edition"]')"
  FAMILLE="$(json '[p for p in d["parameters"] if p["key"]=="'"$CLE"'"][0]["standard_family"]')"
  PART="$(json '[p for p in d["parameters"] if p["key"]=="'"$CLE"'"][0]["part"]')"
  if [[ -z "$CLE" || -z "$DOC" ]]; then
    echouee 3 "aucun parametre belge a confirmer (code $code)."
  else
    python3 -c 'import json,sys; print(json.dumps({"country_code":"BE","rule_id":sys.argv[1],"statement":"ESSAI TECHNIQUE — recette staging, comptes d essai; aucune approbation reelle","citations":[{"document_digest":sys.argv[2],"quote":"ESSAI TECHNIQUE — citation de recette","page_printed":int(sys.argv[3])}]}))' \
      "$CLE" "$DOC" "$FOLIO" > "$TMP/brouillon.json"
    code="$(api A POST /v1/authority/review-packages "$TMP/brouillon.json")"
    if [[ "$code" != "200" ]]; then
      echouee 3 "composition du dossier: $code $(cut -c1-140 "$TMP/reponse")"
    else
      python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
print(json.dumps({"subject_kind":"ndp_parameter","subject_id":sys.argv[2],"org_id":None,"country_code":"BE",
  "standard_family":sys.argv[3],"part":sys.argv[4],"edition":sys.argv[5],
  "permission":"can_validate_normative_reference",
  "reason":"ESSAI TECHNIQUE — recette staging, comptes d essai; aucune approbation reelle",
  "review_package":d["package"]}))' "$TMP/reponse" "$CLE" "$FAMILLE" "$PART" "$EDITION" > "$TMP/proposition.json"
      code="$(api A POST /v1/authority/decisions "$TMP/proposition.json")"
      DECISION="$(json 'd["decision_id"]')"
      if [[ "$code" != "201" || -z "$DECISION" ]]; then
        echouee 3 "proposition par A: $code $(cut -c1-140 "$TMP/reponse")"
      else
        auto="$(api A POST "/v1/authority/decisions/$DECISION/approval")"
        relu="$(api B GET "/v1/authority/decisions/$DECISION")"
        appr="$(api B POST "/v1/authority/decisions/$DECISION/approval")"
        cons="$(api B POST "/v1/authority/decisions/$DECISION/consumption")"
        if [[ "$auto" == "422" && "$relu" == "200" && "$appr" == "204" && "$cons" == "200" ]]; then
          executee 3 "$CLE: A propose, A ne s'approuve pas (422), B relit, approuve et consomme. Decision d'ESSAI."
        else
          echouee 3 "auto-approbation $auto (422 attendu), relecture $relu, approbation $appr, consommation $cons."
        fi
      fi
    fi
  fi
fi

# --- 4. L'ETUDE BELGE — STRICTE (refus ou aboutissement coherent), PUIS EXPLORATOIRE
echo "==> 4. etude belge — stricte puis exploratoire, sur un projet de recette"
CALCUL=""; PROJET=""
if [[ "${ETATS[2]}" != "EXECUTEE" ]]; then
  non_exec 4 "l'etape 2 n'est pas etablie."
elif ! est_defini EUROSTRUCT_STAGING_JETON_A; then
  non_exec 4 "jeton A absent."
else
  entete_pour A
  python3 -c 'import json; print(json.dumps({"name":"Recette technique — bureau d essai","country":"BE","display_name":"Ingenieur d essai A","professional_id":None}))' > "$TMP/org.json"
  code="$(api A POST /v1/organizations "$TMP/org.json")"; ORG="$(json 'd["organization_id"]')"
  code2="$(api A GET /v1/projects)"
  PROJET="$(json '([p for p in d["projects"] if p["name"]=="Recette technique — poutre belge"] or [{"project_id":""}])[0]["project_id"]')"
  if [[ -z "$PROJET" && -n "$ORG" ]]; then
    python3 -c 'import json,sys; print(json.dumps({"name":"Recette technique — poutre belge","reference":"RECETTE-BE","country":"BE","region":None,"ndp_as_of":sys.argv[1],"organization_id":sys.argv[2]}))' \
      "$(date -u +%Y-%m-%d)" "$ORG" > "$TMP/projet.json"
    code3="$(api A POST /v1/projects "$TMP/projet.json")"; PROJET="$(json 'd["project_id"]')"
  fi
  if [[ -z "$PROJET" ]]; then
    echouee 4 "ni bureau ni projet de recette (org $code, liste $code2)."
  else
    api - GET /v1/ndp/BE/couverture >/dev/null; UTIL="$(json 'd["utilisables"]')"; REQ="$(json 'd["total_requis"]')"
    corps_etude() { python3 -c 'import json,sys; print(json.dumps({"element":"P1","strict_ndp":sys.argv[1]=="oui","geometry":{"b":{"value":300,"unit":"mm"},"h":{"value":600,"unit":"mm"},"d":{"value":550,"unit":"mm"},"l_eff":{"value":6000,"unit":"mm"}},"materials":{"concrete_grade":"C30/37","steel_grade":"B500B"},"M_Ed":{"value":250,"unit":"kN*m"},"V_Ed":{"value":300,"unit":"kN"},"M_char":{"value":180,"unit":"kN*m"},"M_qp":{"value":120,"unit":"kN*m"},"phi_creep":2.0,"exposure_class":"XC3","structural_system":"simply_supported","supports_brittle_partitions":False,"bars":{"count":4,"diameter":{"value":20,"unit":"mm"}},"links":{"legs":2,"diameter":{"value":10,"unit":"mm"},"spacing":{"value":150,"unit":"mm"}},"cot_theta":1.5,"cover":{"value":40,"unit":"mm"},"anchorage_available":{"value":800,"unit":"mm"}}))' "$1"; }
    corps_etude oui > "$TMP/stricte.json"; corps_etude non > "$TMP/explo.json"
    strict="$(api A POST "/v1/projects/$PROJET/beam-verifications" "$TMP/stricte.json")"
    attendu=422; [[ "$UTIL" == "$REQ" ]] && attendu=201
    detail_strict="strict $strict (attendu $attendu, utilisables $UTIL/$REQ)"
    explo="$(api A POST "/v1/projects/$PROJET/beam-verifications" "$TMP/explo.json")"
    CALCUL="$(json 'd["calculation_id"]')"; STATUT="$(json 'd["status"]')"; EMPREINTE="$(json 'd["calculation_fingerprint"]')"
    if [[ "$strict" == "$attendu" && "$explo" == "201" && "$STATUT" == "passed" ]]; then
      executee 4 "$detail_strict; exploratoire 201 passed ($CALCUL)."
    else
      echouee 4 "$detail_strict; exploratoire $explo statut ${STATUT:-?}."
    fi
  fi
fi

# --- 5. PDF ET DXF — CREES, TELECHARGES, EMPREINTES CONCORDANTES -----------
echo "==> 5. livrables PDF et DXF (stockage $STOCKAGE)"
if [[ "${ETATS[4]}" != "EXECUTEE" ]]; then
  non_exec 5 "l'etape 4 n'est pas etablie."
else
  ok=1; detail=""
  for fmt in pdf dxf; do
    python3 -c 'import json,sys; print(json.dumps({"calculation_id":sys.argv[1],"format":sys.argv[2]}))' "$CALCUL" "$fmt" > "$TMP/liv.json"
    code="$(api A POST "/v1/projects/$PROJET/deliverables" "$TMP/liv.json")"
    ID="$(json 'd["deliverable_id"]')"; SHA="$(json 'd["sha256"]')"
    curl -sS -o "$TMP/recu.$fmt" -H @"$TMP/entete_A" --max-time 120 \
      "http://127.0.0.1:$PORT_API/v1/projects/$PROJET/deliverables/$ID/download" 2>/dev/null
    recu="$(sha256sum < "$TMP/recu.$fmt" | cut -d' ' -f1)"
    if [[ "$code" == "201" && -n "$SHA" && "$recu" == "$SHA" ]]; then
      detail+="$fmt $(wc -c < "$TMP/recu.$fmt") o ok; "
    else
      ok=0; detail+="$fmt: creation $code, empreinte recue ${recu:0:8} vs ${SHA:0:8}; "
    fi
  done
  ((ok)) && executee 5 "$detail" || echouee 5 "$detail"
fi

# --- 6. SAUVEGARDE ET RESTAURATION — PAR LE ROLE DE SAUVEGARDE, VERS UNE BASE VIDE
echo "==> 6. sauvegarde (pg_dump), restauration (base vide distincte), contenu compare"
# CE QUE L'ETAPE ETABLIT, ET PAR QUI. Les tables de l'atelier sont sous RLS
# FORCEE (0002): le role qui restaure — proprietaire de la copie, avec
# `--no-owner` — n'y voit que ce que les politiques lui montrent, c'est-a-dire
# rien. Un `count(*)` de sa part rendait « 1 avant, 0 apres » sur une
# restauration CORRECTE (mesure par l'auto-test), et un compte de lignes —
# fut-il exact — ne dirait rien d'une VALEUR alteree a nombre de lignes egal.
#
# La preuve est donc une comparaison de CONTENU, table par table, entre la
# source et la copie: `db/test/comparer_contenu.sh` calcule pour chacune une
# empreinte de toutes ses lignes, ordonnees, sous des reglages de session
# fixes, et exige d'etre lu par un role qui contourne RLS des deux cotes —
# sinon il refuse, plutot que de comparer deux vues partielles. Les politiques
# du produit restent posees sur la copie; c'est le LECTEUR qui est privilegie,
# par attribut, comme le role de sauvegarde l'est a la source.
#
# SANS CE LECTEUR, L'ETAPE EST NON EXECUTEE, ET LE DIT: la sauvegarde est
# faite, la restauration et la verification ne sont pas tentees — restaurer
# une copie qu'on ne peut pas relire ne prouverait rien. Le verdict est alors
# PARTIELLE, jamais COMPLETE.
TABLES_ESSENTIELLES=(organizations projects calculations results deliverables
                     national_annexes normative_authorisation_grants
                     normative_authority_decisions normative_rule_confirmations)
compter_archive() {   # compter_archive <table> — lignes de la table dans l'archive
  pg_restore -a -t "$1" -f - "$TMP/base.dump" 2>/dev/null \
    | awk '/^COPY /{d=1; next} /^\\\.$/{d=0} d{n++} END{print n+0}'
}
if ((RESTAURATION == 0)); then
  non_exec 6 "EUROSTRUCT_STAGING_RESTORE_URL absente."
elif [[ "${ETATS[1]}" != "EXECUTEE" ]]; then
  non_exec 6 "l'etape 1 n'est pas etablie."
else
  vide="$(sql EUROSTRUCT_STAGING_RESTORE_URL "select count(*) from pg_tables where schemaname='public'")"
  if [[ "$vide" != "0" ]]; then
    echouee 6 "la cible de restauration n'est pas vide ($vide table(s) dans public): on ne restaure pas par-dessus."
  elif ! avec_url SAUVEGARDE_URL pg_dump -Fc -f "$TMP/base.dump" 2>"$TMP/dump.err"; then
    # LES TABLES DE CONFIANCE SONT SOUS RLS FORCEE: leur proprietaire meme y
    # est soumis, et `pg_dump` REFUSE plutot que de rendre une sauvegarde
    # partielle. Sur une base hebergee, seul un role que le fournisseur dote
    # de BYPASSRLS peut sauvegarder — c'est le sien, et il se nomme ici par
    # EUROSTRUCT_STAGING_BACKUP_URL. Sans lui, la sauvegarde COMPLETE est celle
    # du fournisseur, pas la notre.
    #
    # LE LIBELLE EST FIXE. Une redaction anterieure composait « le role de
    # sauvegarde » avec `${VAR:-le migrateur}` — qui, la variable etant
    # definie, DEVELOPPAIT LA DSN ENTIERE, mot de passe compris, dans cette
    # ligne. Aucune valeur de variable n'entre dans un message de cette
    # recette; l'auto-test le balaie.
    echouee 6 "pg_dump par le role de sauvegarde (EUROSTRUCT_STAGING_BACKUP_URL, ou a defaut le migrateur) a echoue: $(grep -m1 -iE 'row-level|permission|error|refus' "$TMP/dump.err" | sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g; s#user "[^"]*"#user "<masque>"#g' | cut -c1-120). Sur une base hebergee, la sauvegarde complete est celle du fournisseur (role BYPASSRLS)."
  else
    TAILLE_DUMP="$(wc -c < "$TMP/base.dump")"
    RESTAURATEUR="$(sql EUROSTRUCT_STAGING_RESTORE_URL "select current_user")"
    CONTOURNE="$(sql EUROSTRUCT_STAGING_RESTORE_URL "select (rolbypassrls or rolsuper) from pg_roles where rolname = current_user")"
    if [[ "$CONTOURNE" != "t" ]]; then
      non_exec 6 "sauvegarde faite ($TAILLE_DUMP o; archive: calculations $(compter_archive calculations), deliverables $(compter_archive deliverables)); restauration et verification NON tentees: le role de restauration « ${RESTAURATEUR:-illisible} » ne contourne pas RLS (BYPASSRLS) et ne pourrait pas relire exactement ce qu'il restaure sous les politiques du produit. Fournir, en EUROSTRUCT_STAGING_RESTORE_URL, le role du fournisseur sur une base vide."
    elif ! avec_url EUROSTRUCT_STAGING_RESTORE_URL sh -c 'pg_restore --no-owner --no-privileges -d "$PGDATABASE" "$1"' _ "$TMP/base.dump" 2>"$TMP/restore.err"; then
      echouee 6 "pg_restore a echoue: $(grep -m1 -i error "$TMP/restore.err" | sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g' | cut -c1-120)"
    else
      EUROSTRUCT_COMPARE_SOURCE_URL="$SAUVEGARDE_URL" \
      EUROSTRUCT_COMPARE_COPIE_URL="$EUROSTRUCT_STAGING_RESTORE_URL" \
        bash "$HERE/comparer_contenu.sh" "${TABLES_ESSENTIELLES[@]}" >"$TMP/contenu.out" 2>&1; rc=$?
      TOTAL="$(grep -m1 -oE '^TOTAL [0-9]+' "$TMP/contenu.out" | cut -d' ' -f2)"
      case "$rc" in
        0)
          if [[ "${TOTAL:-0}" -gt 0 ]]; then
            executee 6 "dump $TAILLE_DUMP o; restauree; contenu IDENTIQUE, table par table, par empreinte de toutes les lignes ($TOTAL ligne(s) sur ${#TABLES_ESSENTIELLES[@]} tables): $(grep -E '^  ' "$TMP/contenu.out" | awk '{printf "%s %s; ", $1, $2}')"
          else
            echouee 6 "contenu identique mais VIDE (aucune ligne dans les ${#TABLES_ESSENTIELLES[@]} tables essentielles): rien n'est prouve."
          fi ;;
        1) echouee 6 "le contenu restaure DIFFERE de la source: $(grep -E 'DIFFERENT' "$TMP/contenu.out" | awk '{printf "%s (source %s l., copie %s l.); ", $1, $2, $3}')" ;;
        *) echouee 6 "comparaison de contenu impossible (code $rc): $(grep -m1 -E 'REFUS|ERREUR|NON EXECUTE' "$TMP/contenu.out" | cut -c1-140)" ;;
      esac
    fi
  fi
fi

# --- 7. RELECTURE APRES REDEMARRAGE DE L'API -------------------------------
echo "==> 7. redemarrage de l'API, relecture de l'etude"
if [[ "${ETATS[4]}" != "EXECUTEE" ]]; then
  non_exec 7 "l'etape 4 n'est pas etablie."
else
  kill "$PID_API" 2>/dev/null; wait "$PID_API" 2>/dev/null; PID_API=""
  if ! demarrer_api; then
    echouee 7 "l'API n'a pas redemarre."
  else
    code="$(api A GET "/v1/projects/$PROJET/beam-verifications/$CALCUL")"
    relu="$(json 'd["calculation_fingerprint"]')"
    [[ "$code" == "200" && "$relu" == "$EMPREINTE" ]] \
      && executee 7 "etude relue apres redemarrage, meme empreinte de calcul." \
      || echouee 7 "relecture $code, empreinte ${relu:0:12} vs ${EMPREINTE:0:12}."
  fi
fi

verdict
