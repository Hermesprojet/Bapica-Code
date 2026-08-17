#!/usr/bin/env bash
#
# Apply the migrations to a scratch database and run the guarantee tests.
#
# Usage:
#   ./db/test/run.sh                     # uses $DATABASE_URL, or a local socket
#   DATABASE_URL=postgres://... ./run.sh
#
# The tests assert the properties the cahier des charges makes blocking: RLS
# tenant isolation, the human validation gate, immutability of signed records,
# and the ten-year retention guard. Any failure exits non-zero.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
DB_NAME="${DB_NAME:-eurostruct_test}"

# Remplacer la base nommee dans une URL, en preservant une eventuelle chaine
# de requete (`?sslmode=require` est courant en deploiement gere).
url_pour_base() {
  local url="$1" base="$2" sans query=""
  sans="${url%%\?*}"
  [[ "$url" == *\?* ]] && query="?${url#*\?}"
  printf '%s/%s%s' "${sans%/*}" "$base" "$query"
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  ADMIN=(psql "$DATABASE_URL")
  # La base RECREEE, et non celle nommee dans l'URL. Les deux etaient
  # confondues: le script effacait `eurostruct_test` puis appliquait les
  # migrations dans la base de l'URL, qui n'etait jamais remise a zero. Une
  # seconde execution echouait donc sur « type org_role already exists ».
  # Invisible en CI, ou chaque execution part d'un conteneur neuf, et
  # bloquant partout ailleurs.
  PSQL_BASE=(psql "$(url_pour_base "$DATABASE_URL" "$DB_NAME")")
else
  HOST="${PGHOST:-/tmp}"
  USER="${PGUSER:-postgres}"
  PSQL_BASE=(psql -h "$HOST" -U "$USER" -d "$DB_NAME")
  ADMIN=(psql -h "$HOST" -U "$USER" -d postgres)
fi

echo "==> recreating $DB_NAME"
"${ADMIN[@]}" -q -c "drop database if exists $DB_NAME;" >/dev/null
"${ADMIN[@]}" -q -c "create database $DB_NAME;" >/dev/null

echo "==> applying schema"
for f in \
  "$HERE/00_supabase_stub.sql" \
  "$DB_DIR"/migrations/*.sql
do
  echo "    $(basename "$f")"
  "${PSQL_BASE[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done

echo "==> seeding national annexes"
"${PSQL_BASE[@]}" -v ON_ERROR_STOP=1 -q -f "$DB_DIR/seed/0001_ndp.sql"

echo "==> running guarantee tests"
for t in "$HERE"/0[1-9]_*.sql; do
  echo "    $(basename "$t")"
  "${PSQL_BASE[@]}" -v ON_ERROR_STOP=1 -q -f "$t"
done

# --------------------------------------------------------------------------
# Mise a niveau depuis une base DEJA INSTALLEE, et non depuis le vide.
#
# La boucle ci-dessus n'exerce qu'un seul chemin: installation complete d'un
# coup. Or une base de production part de l'etat ou elle est. Une migration
# qui ne passerait que sur une base vierge — parce qu'elle suppose un type
# absent, ou recree un objet deja present — echouerait au deploiement et
# nulle part ici.
#
# On rejoue donc l'histoire: 0001..0009 d'abord, la derniere migration
# ensuite, dans une base separee.
# --------------------------------------------------------------------------
UPGRADE_DB="${DB_NAME}_upgrade"
DERNIERE="$(ls "$DB_DIR"/migrations/*.sql | tail -1)"
PRECEDENTES=("$DB_DIR"/migrations/*.sql)
unset 'PRECEDENTES[${#PRECEDENTES[@]}-1]'

echo "==> upgrade path: $(basename "$DERNIERE") sur une base en 0009"
"${ADMIN[@]}" -q -c "drop database if exists $UPGRADE_DB;" >/dev/null
"${ADMIN[@]}" -q -c "create database $UPGRADE_DB;" >/dev/null

if [[ -n "${DATABASE_URL:-}" ]]; then
  UP=(psql "$(url_pour_base "$DATABASE_URL" "$UPGRADE_DB")")
else
  UP=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$UPGRADE_DB")
fi

"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "${PRECEDENTES[@]}"; do
  "${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done
"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$DERNIERE"
"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/upgrade_check.sql"
"${ADMIN[@]}" -q -c "drop database if exists $UPGRADE_DB;" >/dev/null

# --------------------------------------------------------------------------
# Concurrence, sur DEUX CONNEXIONS REELLES.
#
# Les fichiers SQL ci-dessus tournent tous dans une seule session: ils ne
# peuvent pas exhiber une course. Or `IF EXISTS` suivi d'`INSERT` passe tous
# les tests monoconnexion et ne protege de rien.
#
# Base dediee et vierge: les scenarios courent la chaine de confiance depuis
# son ouverture, ce que la base des autres suites ne permet plus.
# --------------------------------------------------------------------------
CONC_DB="${DB_NAME}_conc"
echo "==> concurrence multi-connexion"
"${ADMIN[@]}" -q -c "drop database if exists $CONC_DB;" >/dev/null
"${ADMIN[@]}" -q -c "create database $CONC_DB;" >/dev/null

if [[ -n "${DATABASE_URL:-}" ]]; then
  CONC=(psql "$(url_pour_base "$DATABASE_URL" "$CONC_DB")")
else
  CONC=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$CONC_DB")
fi
"${CONC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "$DB_DIR"/migrations/*.sql; do
  "${CONC[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done
"$HERE/concurrency.sh" "$CONC_DB"
CONC_CODE=$?
"${ADMIN[@]}" -q -c "drop database if exists $CONC_DB;" >/dev/null
[[ $CONC_CODE -eq 0 ]] || exit $CONC_CODE
