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

# `set -e` termine le script AVANT la ligne suivante des que concurrency.sh
# sort non nul: `CONC_CODE` n'etait jamais lu, et la base de test restait
# derriere. La forme `|| CONC_CODE=$?` est la seule qui capture le code sans
# desarmer `set -e` pour le reste du fichier.
CONC_CODE=0
"$HERE/concurrency.sh" "$CONC_DB" || CONC_CODE=$?
"${ADMIN[@]}" -q -c "drop database if exists $CONC_DB;" >/dev/null
[[ $CONC_CODE -eq 0 ]] || exit $CONC_CODE

# --------------------------------------------------------------------------
# Base VIERGE: racine de confiance, puis contrat croise Python <-> SQL.
#
# Deux controles que la base des suites ci-dessus ne peut plus porter, pour la
# meme raison: elle a deja un administrateur amorce.
#
#  * `virgin_root.sql` doit constater qu'une insertion brute en
#    `origin='bootstrap'` est refusee PARCE QUE l'ecriture est fermee — pas
#    parce qu'une racine existe deja. Joue apres 05, il passerait pour la
#    mauvaise raison.
#  * `cross_contract.sh` ouvre lui-meme la chaine de confiance, comme en
#    deploiement, puis y pousse un vrai paquet produit par le moteur.
#
# `virgin_root.sql` ne cree rien — toutes ses insertions echouent, et il le
# verifie. La base est donc encore vierge pour le contrat croise.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Prerequis de deploiement sur les roles.
#
# S'evaluent PENDANT la migration: aucun fichier de db/test/ ne peut les
# observer, puisqu'ils ne tournent que sur une base ou la migration a deja
# reussi. Le script fabrique donc la configuration hostile AVANT d'appliquer
# les migrations, et exige un refus.
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# UN ROUGE N'ARRETE PLUS LA SUITE.
#
# Jusqu'ici chaque etape sortait au premier echec. Consequence mesuree: le
# rouge de l'installation non superutilisateur empechait les etapes SUIVANTES
# — base vierge, contrat croise — de s'executer du tout, et le rapport ne
# disait pas si elles auraient passe. On ne peut pas distinguer « non
# executee » de « verte » si l'une se presente comme l'autre.
#
# Les etapes s'executent donc toutes, chacune est comptee, et le code de sortie
# reste non nul des qu'une seule est rouge.
SURFACES_ROUGES=()
etape() {
  local nom="$1"; shift
  local code=0
  "$@" || code=$?
  [[ $code -eq 0 ]] || SURFACES_ROUGES+=("$nom")
  return 0
}

ROLE_DB="${DB_NAME}_roles"
echo "==> prerequis de deploiement sur les roles"
etape "prerequis de deploiement sur les roles" \
  "$HERE/role_prerequisites.sh" "$ROLE_DB"
"${ADMIN[@]}" -q -c "drop database if exists $ROLE_DB;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Installation sous un role de migration NON SUPERUTILISATEUR.
#
# Tout ce qui precede tourne sous `postgres`, superutilisateur — qui transfere
# la propriete d'une fonction sans etre membre de rien, contourne la RLS et
# detient EXECUTE implicitement. Rien de cela n'est vrai de la cible de
# production, et quatre obstacles reels n'apparaissaient qu'ici.
# --------------------------------------------------------------------------
NS_DB="${DB_NAME}_nonsuper"
echo "==> installation sous un role de migration non superutilisateur"
etape "installation non superutilisateur" \
  "$HERE/nonsuperuser_install.sh" "$NS_DB"
"${ADMIN[@]}" -q -c "drop database if exists $NS_DB;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Oracle comportemental des primitives de portee (6.3b6a #3).
#
# `assert_normative_topology()` decide qui atteint un role d'autorite au moyen
# de `pg_has_role(..., 'SET' / 'USAGE' / 'MEMBER WITH ADMIN OPTION')`. Ce que
# ces primitives DISENT est ici confronte a ce qui se PASSE — vrai `SET ROLE`,
# vrai heritage, vrai `GRANT` a un tiers — sur six formes de graphe.
# --------------------------------------------------------------------------
echo "==> oracle comportemental des primitives de portee"
etape "oracle de portee des roles" \
  "$HERE/role_reach_oracle.sh" "${DB_NAME}_oracle"

# --------------------------------------------------------------------------
# Deploiement en deux phases (6.3b6a #8).
#
# Ce que l'installation non superutilisateur ne pouvait montrer qu'indirectement:
# QUI cree les roles et QUI accorde les appartenances decide de tout. Trois
# configurations, une variable a la fois.
# --------------------------------------------------------------------------
echo "==> deploiement en deux phases"
etape "deploiement en deux phases" \
  "$HERE/two_phase_deployment.sh" "${DB_NAME}_2p"

XC_DB="${DB_NAME}_contract"
echo "==> base vierge: racine de confiance et contrat croise"
"${ADMIN[@]}" -q -c "drop database if exists $XC_DB;" >/dev/null
"${ADMIN[@]}" -q -c "create database $XC_DB;" >/dev/null

if [[ -n "${DATABASE_URL:-}" ]]; then
  XC=(psql "$(url_pour_base "$DATABASE_URL" "$XC_DB")")
else
  XC=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$XC_DB")
fi
"${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "$DB_DIR"/migrations/*.sql; do
  "${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done

etape "base vierge: racine de confiance" \
  "${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/virgin_root.sql"
etape "contrat croise moteur/base" \
  "$HERE/cross_contract.sh" "${XC[@]}"
"${ADMIN[@]}" -q -c "drop database if exists $XC_DB;" >/dev/null

echo ""
if [[ ${#SURFACES_ROUGES[@]} -eq 0 ]]; then
  echo "================================================="
  echo " Toutes les surfaces de db/test sont vertes."
  echo "================================================="
  exit 0
fi
echo "================================================="
echo " ${#SURFACES_ROUGES[@]} surface(s) ROUGE(S):"
for s_rouge in "${SURFACES_ROUGES[@]}"; do echo "   - $s_rouge"; done
echo "================================================="
exit 1
