#!/usr/bin/env bash
#
# EUROSTRUCT — auto-tests de `supabase_probe.sh`
#
#   PGHOST=... PGUSER=... PGPASSWORD=... ./supabase_probe_selftest.sh
#
# POURQUOI UNE SONDE A BESOIN DE SES PROPRES TESTS
# ------------------------------------------------
# Elle est destinee a tourner sur l'instance d'un client, une seule fois, sous
# le regard de quelqu'un qui ne lira pas son code. Ses modes de panne comptent
# donc autant que son chemin nominal — et deux d'entre eux etaient reels:
# elle detruisait des roles a noms fixes, et elle se rabattait silencieusement
# sur les variables PG* ambiantes quand l'URL etait invalide.
#
# Ces auto-tests s'executent contre le PostgreSQL LOCAL de la suite. Ils ne
# touchent aucune instance distante.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SONDE="$HERE/supabase_probe.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PGH="${PGHOST:-127.0.0.1}"
PGU="${PGUSER:-postgres}"
PGP="${PGPASSWORD:-postgres}"
PORT="${PGPORT:-5432}"
CP=selftest_cp                 # plan de controle non superutilisateur
CP_MDP=selftestx

KO=0
ok()  { printf '      ok: %s\n' "$1"; }
non() { printf '      ECHEC: %s\n' "$1"; [[ -n "${2:-}" ]] && printf '             %s\n' "$2"; KO=1; }

adm() { PGPASSWORD="$PGP" psql -h "$PGH" -p "$PORT" -U "$PGU" -d postgres -X -q -tA "$@"; }

echo "    auto-tests de la sonde de compatibilite"

if ! adm -c 'select 1' >/dev/null 2>&1; then
  echo "      ECHEC: PostgreSQL local injoignable — aucun auto-test execute" >&2
  exit 2
fi

adm -c "drop role if exists $CP;" >/dev/null 2>&1 || true
adm -c "create role $CP login password '$CP_MDP' createrole;" >/dev/null
URL_OK="postgres://$CP:$CP_MDP@$PGH:$PORT/postgres"
nettoyer_cp() { adm -c "drop role if exists $CP;" >/dev/null 2>&1 || true; }
trap 'nettoyer_cp; rm -rf "$TMP"' EXIT

roles_sonde() { adm -c "select count(*) from pg_roles where rolname like 'escprobe%';"; }

# --------------------------------------------------------------------------
# 1. URL INVALIDE avec des PG* ambiantes: aucun appel reseau.
#
# Le piege que ce test ferme: si le decoupage echoue sans arreter le script,
# psql se rabat sur les PG* de l'environnement — donc sur une AUTRE base que
# celle qu'on croyait sonder, avec le droit d'y creer des roles.
# --------------------------------------------------------------------------
AVANT="$(roles_sonde)"
set +e
SORTIE=$(EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="ceci-n-est-pas-une-url" \
         PGHOST="$PGH" PGPORT="$PORT" PGUSER="$PGU" PGPASSWORD="$PGP" \
         PGDATABASE=postgres "$SONDE" 2>&1)
CODE=$?
set -e
APRES="$(roles_sonde)"
if [[ $CODE -ne 2 ]]; then
  non "URL invalide: code $CODE au lieu de 2" "$(head -1 <<<"$SORTIE")"
elif [[ "$AVANT" != "$APRES" ]]; then
  non "URL invalide: des roles de sonde ont ete crees ($AVANT -> $APRES)" \
      "le script s'est connecte malgre une URL inexploitable"
elif ! grep -q "INCONCLUSIVE" <<<"$SORTIE"; then
  non "URL invalide: verdict autre qu'INCONCLUSIVE"
else
  ok "URL invalide + PG* ambiantes: arret avant toute connexion (code 2)"
fi

# --------------------------------------------------------------------------
# 2. OPENSSL ABSENT: le repli aleatoire doit produire un jeton VALIDE.
#
# Le repli lisait douze octets et produisait vingt-quatre caracteres, la ou la
# validation en exige douze: sans openssl, la sonde refusait de demarrer.
# On reconstruit un PATH qui ne contient PAS openssl.
# --------------------------------------------------------------------------
BIN="$TMP/bin"; mkdir -p "$BIN"
for outil in bash psql python3 mktemp head od tr sed grep cat rm printf env; do
  chemin="$(command -v "$outil" 2>/dev/null || true)"
  [[ -n "$chemin" ]] && ln -sf "$chemin" "$BIN/$outil"
done
if command -v openssl >/dev/null 2>&1 && [[ -e "$BIN/openssl" ]]; then
  non "l'auto-test n'a pas su retirer openssl du PATH"
else
  set +e
  SORTIE=$(PATH="$BIN" EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" \
           "$SONDE" 2>&1)
  CODE=$?
  set -e
  if grep -q "aleatoire indisponible" <<<"$SORTIE"; then
    non "sans openssl: le repli aleatoire a ete refuse" \
        "six octets doivent donner douze caracteres hexadecimaux"
  elif [[ $CODE -ne 0 ]]; then
    non "sans openssl: code $CODE au lieu de 0" "$(grep -m1 -E 'NON|INCONCLUSIVE' <<<"$SORTIE" || true)"
  else
    ok "sans openssl: jeton valide, sonde complete (code 0)"
  fi
fi

# --------------------------------------------------------------------------
# 3. CONSENTEMENT ABSENT: arret avant connexion.
# --------------------------------------------------------------------------
AVANT="$(roles_sonde)"
set +e
SORTIE=$(DATABASE_URL="$URL_OK" "$SONDE" 2>&1); CODE=$?
set -e
APRES="$(roles_sonde)"
if [[ $CODE -ne 2 ]]; then
  non "sans consentement: code $CODE au lieu de 2"
elif [[ "$AVANT" != "$APRES" ]]; then
  non "sans consentement: des roles ont ete crees"
elif ! grep -q "REFUS" <<<"$SORTIE"; then
  non "sans consentement: le refus n'est pas annonce"
else
  ok "sans EUROSTRUCT_PROBE_TARGET=staging: arret avant connexion (code 2)"
fi

# --------------------------------------------------------------------------
# 4. NETTOYAGE EN ECHEC: code 3, et le residu est NOMME.
# --------------------------------------------------------------------------
set +e
SORTIE=$(EUROSTRUCT_PROBE_TARGET=staging EUROSTRUCT_PROBE_SKIP_CLEANUP=1 \
         DATABASE_URL="$URL_OK" "$SONDE" 2>&1)
CODE=$?
set -e
if [[ $CODE -ne 3 ]]; then
  non "nettoyage en echec: code $CODE au lieu de 3"
else
  ok "nettoyage en echec: code 3"
fi
# Et on retire nous-memes ce que le hook a laisse: un auto-test ne laisse pas
# de trace derriere lui.
RESTES=$(adm -c "select string_agg(rolname, ' ') from pg_roles where rolname like 'escprobe%';")
for r in $RESTES; do adm -c "drop role if exists \"$r\";" >/dev/null 2>&1 || true; done

# --------------------------------------------------------------------------
# 5. DEUX EXECUTIONS SIMULTANEES: zero residu, aucune collision.
# --------------------------------------------------------------------------
set +e
EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" "$SONDE" >"$TMP/a.log" 2>&1 & PA=$!
EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" "$SONDE" >"$TMP/b.log" 2>&1 & PB=$!
wait $PA; CA=$?
wait $PB; CB=$?
set -e
JA=$(grep -oE 'jeton [0-9a-f]{12}' "$TMP/a.log" | head -1 || true)
JB=$(grep -oE 'jeton [0-9a-f]{12}' "$TMP/b.log" | head -1 || true)
RESTE="$(roles_sonde)"
if [[ $CA -ne 0 || $CB -ne 0 ]]; then
  non "deux executions simultanees: codes $CA / $CB"
elif [[ -z "$JA" || "$JA" == "$JB" ]]; then
  non "deux executions simultanees: jetons non distincts ($JA / $JB)"
elif [[ "$RESTE" != "0" ]]; then
  non "deux executions simultanees: $RESTE role(s) residuel(s)"
else
  ok "deux executions simultanees: jetons distincts, zero residu"
fi

echo ''
echo '================================================='
echo ' Auto-tests de la sonde de compatibilite verifies.'
echo '================================================='
exit $KO
