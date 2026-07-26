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

if [[ -n "${DATABASE_URL:-}" ]]; then
  PSQL_BASE=(psql "$DATABASE_URL")
  ADMIN=(psql "$DATABASE_URL")
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

echo "==> running guarantee tests"
"${PSQL_BASE[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/01_guarantees.sql"
