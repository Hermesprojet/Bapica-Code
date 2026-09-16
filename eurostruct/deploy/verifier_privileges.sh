#!/usr/bin/env bash
#
# EUROSTRUCT — LES PRIVILEGES REELLEMENT NECESSAIRES, CONSTATES EN LECTURE SEULE
#
#   ESC_PLAN_URL=... ESC_MIGRATOR_URL=... EUROSTRUCT_DATABASE_URL=... \
#   deploy/verifier_privileges.sh
#
# POURQUOI CE SCRIPT EXISTE
# --------------------------
# Les harnais du depot creent leur migrateur avec `createrole createdb` et un
# superutilisateur a portee de main. Une base HEBERGEE ne donne ni l'un ni
# l'autre au role applicatif — et ne le doit pas. Ce script dit, pour chacun
# des trois acteurs, ce que le produit EXIGE de lui (d'apres ce que
# `deploy/initialiser.sh` accorde, ce que `tools/deploy_eurostruct.sh`
# verifie avant de muter, et ce que les migrations lisent), et ce qui est
# CONSTATE sur la base visee. Il ne transpose pas les exigences des harnais
# jetables: `createrole` sur le migrateur, par exemple, n'est pas requis.
#
# IL NE MUTE RIEN. Uniquement des `select` sur le catalogue. Il peut donc
# tourner sur une base en service, avant tout deploiement.
#
# AUCUN SECRET DANS `argv`. Les DSN sont decoupees en variables libpq dans un
# sous-shell; aucune n'est affichee.
#
# CODES: 0 tout ce qui est requis est constate; 1 au moins un requis manque;
#        2 une URL est inexploitable; 4 une URL manque.
set -uo pipefail
set +x

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
    [[ -z "$l" || "$l" =~ ^export\ PG(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]] || return 2
  done <<<"$decoupe"
  ( eval "$decoupe"; unset PGSERVICE PGSERVICEFILE PGHOSTADDR PGPASSFILE PGOPTIONS; "$@" )
}
sql() { avec_url "$1" psql -X -q -tA -v ON_ERROR_STOP=1 -c "$2" 2>/dev/null | tr -d ' \r'; }

for v in ESC_PLAN_URL ESC_MIGRATOR_URL EUROSTRUCT_DATABASE_URL; do
  [[ -n "${!v:-}" ]] || { echo "NON EXECUTE: $v manque." >&2; exit 4; }
done

KO=0
ligne() {   # ligne <acteur> <verification> <requis|souhaite|interdit> <constate:oui|non|?>
  local verdict="ok"
  case "$3:$4" in
    requis:oui|interdit:non|souhaite:*) verdict="ok" ;;
    requis:non|interdit:oui) verdict="MANQUE"; KO=1 ;;
    *) verdict="?"; KO=1 ;;
  esac
  [[ "$3" == "souhaite" && "$4" == "non" ]] && verdict="absent (souhaite)"
  printf '  %-10s %-58s %-9s %-4s %s\n' "$1" "$2" "$3" "$4" "$verdict"
}
# `t`/`f` quand psql rend un booleen nu, `true`/`false` apres `::text` ou dans
# une concatenation — les deux formes arrivent ici.
b() { case "$1" in t|true) echo oui ;; f|false) echo non ;; *) echo "?" ;; esac; }

printf '  %-10s %-58s %-9s %-4s %s\n' ACTEUR VERIFICATION EXIGENCE ETAT VERDICT
printf '  %-10s %-58s %-9s %-4s %s\n' ---------- ---------------------------------------------------------- --------- ---- -------

# --- LE PLAN DE CONTROLE ------------------------------------------------------
# Ce que la commande officielle verifie ou exige (etapes 1, 2b, 3, 7): un role
# NON superutilisateur, CREATE sur `public` AVEC GRANT OPTION (le sceau y
# cree ses tables, et le plan retransmet ce droit a l'activateur), USAGE sur
# `auth`, CREATEROLE (les six roles canoniques, s'ils n'existent pas encore),
# puis `eurostruct_deployment` — apres la phase 0 seulement. CREATE sur la
# BASE ne lui sert a rien: la phase 0 ne cree aucun schema, et c'est ce que
# `deploy/initialiser.sh` provisionne — au migrateur seul.
A=plan
if ! sql ESC_PLAN_URL "select 1" >/dev/null; then echo "  $A: connexion refusee" >&2; exit 2; fi
r="$(sql ESC_PLAN_URL "select rolsuper||','||rolcreaterole||','||rolbypassrls from pg_roles where rolname=current_user")"
ligne $A "n'est pas superutilisateur" interdit "$(b "${r%%,*}")"
r2="${r#*,}"; ligne $A "CREATEROLE (creer les six roles canoniques a la phase 0)" requis "$(b "${r2%%,*}")"
ligne $A "n'a pas BYPASSRLS" interdit "$(b "${r##*,}")"
printf '  %-10s %-58s %-9s %-4s %s\n' $A "CREATE sur la base (la phase 0 ne cree aucun schema)" "-" "$(b "$(sql ESC_PLAN_URL "select has_database_privilege(current_user, current_database(), 'CREATE')")")" "sans objet"
ligne $A "CREATE sur le schema public, WITH GRANT OPTION" requis "$(b "$(sql ESC_PLAN_URL "select has_schema_privilege(current_user, 'public', 'CREATE WITH GRANT OPTION')")")"
ligne $A "USAGE sur le schema auth" requis "$(b "$(sql ESC_PLAN_URL "select case when to_regnamespace('auth') is null then 'f' else has_schema_privilege(current_user,'auth','USAGE')::text end")")"
dep="$(sql ESC_PLAN_URL "select case when to_regrole('eurostruct_deployment') is null then 'absent' else pg_has_role(current_user,'eurostruct_deployment','USAGE')::text end")"
case "$dep" in
  absent) ligne $A "eurostruct_deployment (n'existe qu'apres la phase 0)" souhaite "non" ;;
  *) ligne $A "membre de eurostruct_deployment (phase 2)" requis "$(b "$dep")" ;;
esac
ligne $A "figure dans eurostruct.approved_deployment_roles" requis "$(b "$(sql ESC_PLAN_URL "select (current_user = any(string_to_array(current_setting('eurostruct.approved_deployment_roles', true), ',')))::text")")"

# --- LE MIGRATEUR -------------------------------------------------------------
# Ce que `initialiser.sh` lui accorde et que les migrations consomment: la
# PROPRIETE de la base (c'est elle qui donne CREATE sur `public` depuis
# PostgreSQL 15), CREATE sur la base, USAGE sur `auth` avec grant option,
# SELECT/INSERT/REFERENCES sur auth.users avec grant option, EXECUTE sur
# auth.uid() avec grant option. NI createrole NI createdb ne sont requis:
# les harnais les posent par commodite, le produit ne les lit pas.
A=migrateur
if ! sql ESC_MIGRATOR_URL "select 1" >/dev/null; then echo "  $A: connexion refusee" >&2; exit 2; fi
r="$(sql ESC_MIGRATOR_URL "select rolsuper||','||rolbypassrls from pg_roles where rolname=current_user")"
ligne $A "n'est pas superutilisateur" interdit "$(b "${r%%,*}")"
ligne $A "n'a pas BYPASSRLS" interdit "$(b "${r##*,}")"
ligne $A "proprietaire de la base (CREATE sur public en decoule)" requis "$(b "$(sql ESC_MIGRATOR_URL "select (pg_get_userbyid(datdba) = current_user)::text from pg_database where datname = current_database()")")"
ligne $A "CREATE sur la base" requis "$(b "$(sql ESC_MIGRATOR_URL "select has_database_privilege(current_user, current_database(), 'CREATE')")")"
ligne $A "USAGE sur auth, WITH GRANT OPTION" requis "$(b "$(sql ESC_MIGRATOR_URL "select case when to_regnamespace('auth') is null then 'f' else has_schema_privilege(current_user,'auth','USAGE WITH GRANT OPTION')::text end")")"
ligne $A "SELECT, INSERT, REFERENCES sur auth.users, WITH GRANT OPTION" requis "$(b "$(sql ESC_MIGRATOR_URL "select case when to_regclass('auth.users') is null then 'f' else (has_table_privilege(current_user,'auth.users','SELECT WITH GRANT OPTION') and has_table_privilege(current_user,'auth.users','INSERT WITH GRANT OPTION') and has_table_privilege(current_user,'auth.users','REFERENCES WITH GRANT OPTION'))::text end")")"
ligne $A "EXECUTE sur auth.uid(), WITH GRANT OPTION" requis "$(b "$(sql ESC_MIGRATOR_URL "select case when to_regproc('auth.uid') is null then 'f' else has_function_privilege(current_user,'auth.uid()','EXECUTE WITH GRANT OPTION')::text end")")"
ligne $A "figure dans eurostruct.approved_deployment_roles" requis "$(b "$(sql ESC_MIGRATOR_URL "select (current_user = any(string_to_array(current_setting('eurostruct.approved_deployment_roles', true), ',')))::text")")"
r="$(sql ESC_MIGRATOR_URL "select rolcreaterole||','||rolcreatedb from pg_roles where rolname=current_user")"
printf '  %-10s %-58s %-9s %-4s %s\n' $A "createrole / createdb (les harnais les posent; le produit ne les lit pas)" "-" "$(b "${r%%,*}")/$(b "${r##*,}")" "sans objet"

# --- LE LOGIN APPLICATIF ------------------------------------------------------
# Ce que l'API presente a chaque requete. Il n'a besoin d'AUCUN privilege de
# table: il n'atteint que les primitives SECURITY DEFINER par sa qualite de
# membre de `eurostruct_authority_backend`, et il doit etre nomme dans deux
# reglages de base. Tout privilege global sur lui est un defaut.
A=applicatif
if ! sql EUROSTRUCT_DATABASE_URL "select 1" >/dev/null; then echo "  $A: connexion refusee" >&2; exit 2; fi
r="$(sql EUROSTRUCT_DATABASE_URL "select rolsuper||','||rolcreaterole||','||rolcreatedb||','||rolbypassrls from pg_roles where rolname=current_user")"
IFS=',' read -r s cr cd br <<<"$r"
ligne $A "n'est pas superutilisateur (sinon RLS est decorative)" interdit "$(b "$s")"
ligne $A "n'a pas CREATEROLE" interdit "$(b "$cr")"
ligne $A "n'a pas CREATEDB" interdit "$(b "$cd")"
ligne $A "n'a pas BYPASSRLS" interdit "$(b "$br")"
ab="$(sql EUROSTRUCT_DATABASE_URL "select case when to_regrole('eurostruct_authority_backend') is null then 'absent' else pg_has_role(current_user,'eurostruct_authority_backend','MEMBER')::text end")"
case "$ab" in
  absent) ligne $A "membre de eurostruct_authority_backend (apres deploiement)" souhaite "non" ;;
  *) ligne $A "membre de eurostruct_authority_backend" requis "$(b "$ab")" ;;
esac
ligne $A "figure dans eurostruct.approved_service_logins" requis "$(b "$(sql EUROSTRUCT_DATABASE_URL "select (current_user = any(string_to_array(current_setting('eurostruct.approved_service_logins', true), ',')))::text")")"
ligne $A "figure dans eurostruct.authority_backend_logins" requis "$(b "$(sql EUROSTRUCT_DATABASE_URL "select (current_user = any(string_to_array(current_setting('eurostruct.authority_backend_logins', true), ',')))::text")")"

echo
if ((KO)); then
  echo "  Au moins une exigence n'est pas constatee. Rien n'a ete modifie."
  exit 1
fi
echo "  Tout ce que le produit exige de ces trois acteurs est constate. Rien n'a ete modifie."
exit 0
