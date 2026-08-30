#!/usr/bin/env bash
#
# EUROSTRUCT — LA COMPOSITION DOIT DEMARRER DEPUIS UN VOLUME VIDE
#
#   db/test/composition_depuis_zero.sh
#
# CE QUE CETTE PREUVE ETABLIT
# ----------------------------
# `docker compose config` dit que le fichier est bien forme. Il ne dit RIEN de
# ce qui se passe au demarrage. Cette preuve part d'un volume PostgreSQL vide
# et exige que la pile serve reellement:
#
#   1. les migrations sont appliquees;
#   2. les roles applicatifs existent;
#   3. l'API est connectee par un login DEDIE, non-superutilisateur;
#   4. /health repond;
#   5. /ready est vert avec l'emetteur local deterministe;
#   6. le parcours d'autorite s'execute reellement.
#
# AUJOURD'HUI ELLE DOIT ECHOUER: `compose.yaml` demarre une image PostgreSQL
# vierge, sans migration, sans role de service et sans racine amorcee. L'API
# se connecte avec `POSTGRES_USER`, qui est le superutilisateur de l'image.
#
# AUCUN SECRET N'EST ECRIT ICI. Le fichier d'environnement est genere dans un
# repertoire temporaire, avec des valeurs FICTIVES, et detruit a la sortie.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$(dirname "$HERE")")/eurostruct"
[[ -f "$RACINE/compose.yaml" ]] || RACINE="$(dirname "$(dirname "$HERE")")"

PROJET="esc-preuve-b"
TMP="$(mktemp -d)"
ENVF="$TMP/preuve.env"

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

nettoyer() {
  # `-v` DETRUIT LE VOLUME: la preuve suivante doit repartir de zero, sinon
  # elle ne prouve plus « depuis un volume vide » mais « depuis ce qui restait ».
  docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" \
    down -v --remove-orphans >/dev/null 2>&1
  rm -rf "$TMP"
}
trap nettoyer EXIT

command -v docker >/dev/null 2>&1 || {
  echo "NON EXECUTE: docker absent." >&2; exit 4; }
docker info >/dev/null 2>&1 || {
  echo "NON EXECUTE: le demon docker ne repond pas." >&2; exit 4; }

# ---------------------------------------------------------------------------
# L'EMETTEUR LOCAL, hors composition: le navigateur et l'API doivent le
# joindre, et il n'a rien a faire dans une image de production.
# ---------------------------------------------------------------------------
PORT_AUTH="${EUROSTRUCT_PREUVE_PORT_AUTH:-54331}"
PORT_API="${EUROSTRUCT_PREUVE_PORT_API:-8021}"
PORT_WEB="${EUROSTRUCT_PREUVE_PORT_WEB:-3021}"
ACTEUR_A="22222222-7777-7777-7777-7777777700a1"
ACTEUR_B="33333333-7777-7777-7777-7777777700b1"

for duo in "$PORT_AUTH:emetteur" "$PORT_API:API" "$PORT_WEB:interface"; do
  P="${duo%%:*}"
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$P" 2>/dev/null; then
    echo "      ECHEC: le port $P (${duo##*:}) repond deja." >&2
    exit 2
  fi
done

command -v node >/dev/null 2>&1 || {
  echo "NON EXECUTE: node absent." >&2; exit 4; }

# L'HOTE VU DEPUIS UN CONTENEUR. L'API tourne dans la composition et doit
# joindre l'emetteur qui, lui, tourne sur l'hote.
HOTE_DEPUIS_CONTENEUR="host.docker.internal"

EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH" \
EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://127.0.0.1:$PORT_AUTH/auth/v1" \
EUROSTRUCT_E2E_COMPTES="a@fictif.invalid:FICTIF-A:$ACTEUR_A:3600:oui,b@fictif.invalid:FICTIF-B:$ACTEUR_B:3600:oui" \
  node "$RACINE/web/e2e/supabase_local.mjs" >"$TMP/auth.log" 2>&1 &
PID_AUTH=$!
trap 'kill "$PID_AUTH" 2>/dev/null; nettoyer' EXIT

for _ in $(seq 1 40); do
  curl -fsS --max-time 2 "http://127.0.0.1:$PORT_AUTH/jwks" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS --max-time 2 "http://127.0.0.1:$PORT_AUTH/jwks" >/dev/null 2>&1 || {
  echo "      ECHEC: l'emetteur local n'a pas demarre." >&2
  sed -n '1,15p' "$TMP/auth.log" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# LE FICHIER D'ENVIRONNEMENT — FICTIF, TEMPORAIRE, JAMAIS VERSIONNE
# ---------------------------------------------------------------------------
JETON="$(tr -dc 'a-f0-9' </dev/urandom | head -c 12)"
cat > "$ENVF" <<FIN
POSTGRES_USER=eurostruct_super_$JETON
POSTGRES_PASSWORD=FICTIF-super-$JETON
POSTGRES_DB=eurostruct
EUROSTRUCT_APP_DB_USER=eurostruct_app_$JETON
EUROSTRUCT_APP_DB_PASSWORD=FICTIF-app-$JETON
EUROSTRUCT_SUPABASE_JWKS_URL=http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/jwks
EUROSTRUCT_SUPABASE_ISSUER=http://127.0.0.1:$PORT_AUTH/auth/v1
EUROSTRUCT_SUPABASE_AUDIENCE=authenticated
EUROSTRUCT_JWT_ALGORITHMS=RS256
EUROSTRUCT_PUBLIC_API_URL=http://127.0.0.1:$PORT_API
EUROSTRUCT_PUBLIC_SUPABASE_URL=http://127.0.0.1:$PORT_AUTH
EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY=FICTIF-ANON-$JETON
EUROSTRUCT_CORS_ORIGINS=http://localhost:$PORT_WEB,http://127.0.0.1:$PORT_WEB
API_PORT=$PORT_API
WEB_PORT=$PORT_WEB
FIN

dc() { docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" "$@"; }

echo "    la composition demarre-t-elle depuis un volume VIDE ?"

# Un volume residuel d'une execution precedente ferait passer la preuve pour
# de mauvaises raisons.
dc down -v --remove-orphans >/dev/null 2>&1

if ! dc up --build --wait --wait-timeout 420 >"$TMP/up.log" 2>&1; then
  echoue "la composition n'est pas montee."
  tail -n 25 "$TMP/up.log" >&2
  echo "" >&2
  dc ps >&2 2>/dev/null
  exit 1
fi

psql_admin() {   # psql dans le conteneur de base, en superutilisateur
  dc exec -T db psql -X -q -tA -U "$(grep '^POSTGRES_USER=' "$ENVF" | cut -d= -f2)" \
     -d "$(grep '^POSTGRES_DB=' "$ENVF" | cut -d= -f2)" -c "$1" 2>/dev/null | tr -d ' '
}

# --- 1. LES MIGRATIONS SONT APPLIQUEES -------------------------------------
ETAT="$(psql_admin "select normative_activation_state()")"
if [[ "$ETAT" != "ACTIVE" ]]; then
  echoue "la base n'est pas ACTIVE (etat: « ${ETAT:-aucun} »). Les migrations"
  echoue "  n'ont pas ete appliquees: l'image PostgreSQL demarre vierge."
fi

# --- 2. LES ROLES APPLICATIFS EXISTENT -------------------------------------
MANQUANTS="$(psql_admin "
  select coalesce(string_agg(r, ', '), '') from unnest(array[
    'eurostruct_normative_writer','eurostruct_authority_backend',
    'normative_backend','normative_governance']) r
   where not exists (select 1 from pg_roles where rolname = r)")"
[[ -z "$MANQUANTS" ]] || echoue "roles applicatifs absents: $MANQUANTS"

# --- 3. L'API SE CONNECTE PAR UN LOGIN DEDIE, NON-SUPERUTILISATEUR ---------
APP="$(grep '^EUROSTRUCT_APP_DB_USER=' "$ENVF" | cut -d= -f2)"
SUPER="$(grep '^POSTGRES_USER=' "$ENVF" | cut -d= -f2)"
EXISTE="$(psql_admin "select count(*) from pg_roles where rolname = '$APP'")"
if [[ "$EXISTE" != "1" ]]; then
  echoue "le login applicatif « $APP » n'existe pas: l'API se connecte donc"
  echoue "  avec « $SUPER », le superutilisateur de l'image."
else
  EST_SUPER="$(psql_admin "select rolsuper from pg_roles where rolname = '$APP'")"
  [[ "$EST_SUPER" == "f" ]] || echoue "le login applicatif est superutilisateur."
fi

DSN_UTILISEE="$(dc exec -T api sh -c 'printenv EUROSTRUCT_DATABASE_URL' 2>/dev/null)"
if grep -q "$SUPER" <<<"$DSN_UTILISEE"; then
  echoue "l'API utilise le superutilisateur dans sa chaine de connexion."
fi

# --- 4. ET 5. /health ET /ready --------------------------------------------
SANTE="$(curl -fsS --max-time 10 "http://127.0.0.1:$PORT_API/health" 2>&1)"
grep -q '"status":"ok"' <<<"$SANTE" || echoue "/health ne repond pas ok: $SANTE"

PRET="$(curl -sS --max-time 20 "http://127.0.0.1:$PORT_API/ready" 2>&1)"
if ! grep -q '"ready":true' <<<"$PRET"; then
  echoue "/ready n'est pas vert: $(cut -c1-400 <<<"$PRET")"
fi
grep -q 'SUPABASE_UNVERIFIED' <<<"$PRET" \
  || echoue "/ready ne porte plus SUPABASE_UNVERIFIED."

# --- 6. LE PARCOURS D'AUTORITE S'EXECUTE REELLEMENT -------------------------
jeton_de() {   # jeton_de <courriel> <mot de passe>
  curl -fsS --max-time 10 \
    -X POST "http://127.0.0.1:$PORT_AUTH/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null
}
JA="$(jeton_de a@fictif.invalid FICTIF-A)"
JB="$(jeton_de b@fictif.invalid FICTIF-B)"
if [[ -z "$JA" || -z "$JB" ]]; then
  echoue "l'emetteur local n'a pas delivre les deux jetons."
else
  CORPS='{"subject_kind":"ndp_parameter","subject_id":"EN 1992-1-1:alpha_cc",
          "org_id":null,"country_code":"BE","standard_family":"EN 1992",
          "part":"1-1","edition":"FICTIF","permission":
          "can_validate_normative_reference","reason":"FICTIF preuve B"}'
  CODE="$(curl -sS -o "$TMP/prop.json" -w '%{http_code}' --max-time 15 \
          -X POST "http://127.0.0.1:$PORT_API/v1/authority/decisions" \
          -H "Authorization: Bearer $JA" -H 'Content-Type: application/json' \
          -d "$CORPS" 2>/dev/null)"
  # 201 (accepte) ou 422 (refus METIER, donc la chaine a fonctionne) sont deux
  # reponses d'un service qui SERT. 500 et 503 disent que la pile ne sert pas.
  case "$CODE" in
    201|422) ;;
    *) echoue "la proposition rend $CODE: la chaine d'autorite ne sert pas."
       echoue "  $(cut -c1-300 <"$TMP/prop.json")" ;;
  esac
fi

# --- 7. UN SECOND DEMARRAGE SUR LE MEME VOLUME ------------------------------
dc stop >/dev/null 2>&1
if ! dc up --wait --wait-timeout 300 >"$TMP/up2.log" 2>&1; then
  echoue "le SECOND demarrage sur le meme volume echoue: l'initialisation"
  echoue "  n'est pas idempotente."
  tail -n 20 "$TMP/up2.log" >&2
fi

if [[ $KO -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " La composition sert depuis un volume vide, et"
  echo " redemarre sur le meme volume sans rejouer."
  echo "================================================="
fi
exit $KO
