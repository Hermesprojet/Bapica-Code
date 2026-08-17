#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b4: prerequis de deploiement sur les roles
#
#   role_prerequisites.sh <nom-de-base-jetable>
#
# POURQUOI UN SCRIPT, ET PAS UN FICHIER SQL DE PLUS.
#
# Ces prerequis s'evaluent PENDANT la migration. Un fichier de `db/test/` ne
# tourne qu'apres, sur une base ou la migration a deja reussi: il ne peut par
# construction pas observer un refus. Il faut donc fabriquer la configuration
# hostile AVANT d'appliquer les migrations, et constater qu'elles refusent.
#
# CE QUI EST TESTE, ET POURQUOI C'EST LA QUE TOUT REPOSE.
#
# `current_user` est la preuve d'origine de toute la chaine normative: la
# reserve du namespace d'audit et la branche d'amorcage l'acceptent parce que
# seul l'interieur d'une fonction SECURITY DEFINER peut le faire valoir un
# role d'autorite. Cette preuve tient a UNE condition: que personne ne puisse
# prendre ces roles. Un seul membre, et tout l'edifice devient decoratif.
#
# CONTRE-EXEMPLES VERIFIES ROUGES contre 6.3b3, dont la version precedente
# joignait `pg_auth_members` une seule fois — appartenance DIRECTE — et
# comparait a une LISTE FERMEE DE NOMS. Les cinq configurations ci-dessous
# etaient toutes ACCEPTEES; elles sont toutes refusees depuis.
#
# MODELE DE MENACE. Les superutilisateurs sont exclus des controles: ils
# satisfont `pg_has_role` pour tout role, peuvent desactiver les declencheurs
# et ne sont pas un adversaire que la base contient. Les roles applicatifs,
# eux, sont contenus.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
DB="${1:?usage: role_prerequisites.sh <nom-de-base-jetable>}"

ROLES_FICTIFS="fictif_login_a fictif_b fictif_c fictif_relais"

if [[ -n "${DATABASE_URL:-}" ]]; then
  SANS_QUERY="${DATABASE_URL%%\?*}"; QUERY=""
  [[ "$DATABASE_URL" == *\?* ]] && QUERY="?${DATABASE_URL#*\?}"
  PSQL_DB=(psql "${SANS_QUERY%/*}/$DB$QUERY")
  PSQL_ADMIN=(psql "$DATABASE_URL")
else
  PSQL_DB=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$DB")
  PSQL_ADMIN=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d postgres)
fi

nettoyer() {
  "${PSQL_ADMIN[@]}" -q -c "drop database if exists $DB;" >/dev/null 2>&1
  for r in $ROLES_FICTIFS; do
    "${PSQL_ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
  # Le scenario D altere un role d'autorite: le rendre a son etat.
  "${PSQL_ADMIN[@]}" -q -c \
    "alter role eurostruct_normative_writer nologin;" >/dev/null 2>&1
  # Le scenario E greffe un relais sur `authenticated`.
  "${PSQL_ADMIN[@]}" -q -c \
    "revoke fictif_relais from authenticated;" >/dev/null 2>&1
}
trap nettoyer EXIT
nettoyer

KO=0

# Un scenario: fabriquer la configuration hostile, appliquer les migrations,
# exiger un refus PORTANT SUR LE BON MOTIF. Un refus pour une autre raison
# serait un test vert sur un sujet different.
scenario() {
  local nom="$1" sql="$2" attendu="$3"
  nettoyer
  "${PSQL_ADMIN[@]}" -q -c "create database $DB;" >/dev/null

  # Environnement GERE: les roles PREEXISTENT a la migration, avec des
  # attributs et des appartenances qu'elle n'a pas choisis. C'est exactement
  # la situation que ce prerequis existe pour couvrir — sur une base ou la
  # migration cree elle-meme des roles neufs, il n'y aurait rien a verifier.
  "${PSQL_DB[@]}" -q >/dev/null 2>&1 <<'SQL'
do $$
declare r text;
begin
  foreach r in array array['eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap',
                           'normative_backend', 'normative_governance',
                           'authenticated', 'anon'] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
  end loop;
end $$;
SQL
  "${PSQL_ADMIN[@]}" -q -c "$sql" >/dev/null 2>&1

  local err="" out=""
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" \
    >/dev/null 2>&1
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! out=$("${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$f" 2>&1); then
      err=$(grep -m1 -oE "prerequis non tenu: .{0,120}" <<<"$out")
      break
    fi
  done

  if [[ -z "$err" ]]; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              la migration ACCEPTE cette configuration\n'
    KO=1; return
  fi
  if ! grep -q "$attendu" <<<"$err"; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              refus obtenu, mais hors sujet\n'
    printf '              attendu ~ /%s/\n' "$attendu"
    printf '              obtenu:   %s\n' "$err"
    KO=1; return
  fi
  printf '      ok: %s\n' "$nom"
}

echo "    prerequis de deploiement sur les roles"

scenario "role LOGIN arbitraire, membre direct du writer" \
  "create role fictif_login_a login password 'FICTIF';
   grant eurostruct_normative_writer to fictif_login_a;" \
  "fictif_login_a.*membre de"

scenario "role NOLOGIN, membre direct du bootstrap" \
  "create role fictif_b nologin;
   grant eurostruct_normative_bootstrap to fictif_b;" \
  "fictif_b.*membre de"

# Sur les roles d'AUTORITE, aucune violation PUREMENT transitive n'existe: la
# regle interdit TOUT membre, donc la chaine est coupee a son premier maillon.
# C'est une propriete du controle, pas une lacune du test — et le dire evite
# de croire que la transitivite est prouvee ici. Elle l'est au scenario
# suivant.
scenario "chaine a deux sauts vers le writer, coupee au premier maillon" \
  "create role fictif_relais nologin;
   grant eurostruct_normative_writer to fictif_relais;
   create role fictif_c login password 'FICTIF';
   grant fictif_relais to fictif_c;" \
  "membre de « eurostruct_normative_writer »"

# LA transitivite, prouvee la ou des membres sont LEGITIMES: un role de
# service a vocation a etre endosse par l'application. Ici `authenticated`
# n'est membre que de `fictif_relais`, qui n'est nomme dans aucune liste: une
# jointure directe sur pg_auth_members ne verrait rien.
scenario "transitive reelle: authenticated -> relais -> normative_backend" \
  "create role fictif_relais nologin;
   grant normative_backend to fictif_relais;
   grant fictif_relais to authenticated;" \
  "authenticated.*atteint le role de service"

scenario "role d'autorite rendu connectable" \
  "alter role eurostruct_normative_writer login password 'FICTIF';" \
  "peut se connecter"

# La moitie POSITIVE: sans configuration hostile, la migration passe. Sans
# elle, les cinq refus ci-dessus seraient satisfaits par une migration qui
# refuse toujours.
nettoyer
"${PSQL_ADMIN[@]}" -q -c "create database $DB;" >/dev/null
"${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
SAIN=0
for f in "$DB_DIR"/migrations/*.sql; do
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null 2>&1 || SAIN=1
done
if [[ $SAIN -ne 0 ]]; then
  echo "      ECHEC   configuration SAINE refusee: le controle refuse tout"
  KO=1
else
  echo "      ok: une configuration saine reste acceptee"
fi

echo ''
echo '================================================='
echo ' Prerequis de deploiement sur les roles verifies.'
echo '================================================='
exit $KO
