#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b5: installation complete sous un role de migration
#                     NON SUPERUTILISATEUR
#
#   nonsuperuser_install.sh <nom-de-base-jetable>
#
# CE QUE CE TEST EXISTE POUR ATTRAPER
# ------------------------------------
# Toute la suite tournait jusqu'ici sous `postgres`, superutilisateur. Or un
# superutilisateur:
#
#   * satisfait `pg_has_role(...)` pour TOUT role, donc transfere la propriete
#     d'une fonction a n'importe qui sans etre membre de rien;
#   * contourne la RLS;
#   * detient EXECUTE implicitement sur toute fonction.
#
# Aucune de ces trois choses n'est vraie de la cible de production. Une
# migration peut donc passer mille fois en CI et echouer au premier
# deploiement reel — ce qui etait EXACTEMENT le cas: `ALTER FUNCTION ... OWNER
# TO eurostruct_normative_writer` exige d'etre membre de ce role, et rien dans
# la migration ne l'organisait.
#
# CE QUE CE TEST NE PROUVE PAS
# -----------------------------
# Il ne prouve PAS la compatibilite Supabase. Il reproduit le MODELE DE
# PRIVILEGES de Supabase — role de migration non superutilisateur dote de
# CREATEROLE et CREATEDB, roles `anon` / `authenticated` / `service_role`
# NOLOGIN endosses par un `authenticator` connectable, schema `auth` separe —
# sur un PostgreSQL 16 ordinaire. Ce qu'il ne reproduit pas: les extensions
# preinstallees de Supabase, ses politiques par defaut, son PgBouncer, ses
# `event triggers`, et le contenu reel de son schema `auth`.
#
# La compatibilite Supabase ne sera etablie que par une execution sur une
# instance de staging reelle. Tant que cette execution n'a pas eu lieu, elle
# ne doit pas etre annoncee. Ce fichier remplace « on suppose que ca marche »
# par « voici ce qui est reellement verifie, et voici ce qui ne l'est pas ».
#
# CE QUI EST JOUE
# ---------------
#   1. 0001 a 0010 appliquees par le role de migration non superutilisateur
#   2. l'amorcage, via l'ACL explicite (EXECUTE sur le role de deploiement)
#   3. un parcours complet: octroi -> confirmation -> revocation
#
# Toutes les identites sont FICTIVES. Aucune confirmation reelle n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
DB="${1:?usage: nonsuperuser_install.sh <nom-de-base-jetable>}"

if ! [[ "$DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ ]]; then
  echo "      ECHEC: nom de base « $DB » invalide" >&2
  exit 2
fi

# Roles du modele Supabase, recrees ici. `esc_migrator` tient le role de
# `postgres` chez Supabase: proprietaire du schema, CREATEROLE et CREATEDB,
# mais PAS superutilisateur et PAS bypassrls.
MIGRATEUR=esc_migrator
ROLES_SB="$MIGRATEUR esc_authenticator esc_service_role"
MDP='FICTIF-nonsuperuser'

if [[ -n "${DATABASE_URL:-}" ]]; then
  SANS_QUERY="${DATABASE_URL%%\?*}"; QUERY=""
  [[ "$DATABASE_URL" == *\?* ]] && QUERY="?${DATABASE_URL#*\?}"
  BASE_URL="${SANS_QUERY%/*}"
  ADMIN=(psql "$DATABASE_URL")
  # Le migrateur se connecte AVEC SON PROPRE ROLE, et non via SET ROLE: c'est
  # la seule facon d'exercer reellement une ACL. `SET ROLE` depuis une session
  # superutilisateur conserve `rolsuper` pour certains controles internes, et
  # aurait redonne au test le pouvoir qu'il cherche justement a retirer.
  HOTE="$(sed -E 's|^[^:]+://||; s|^[^@]*@||; s|/.*$||' <<<"$BASE_URL")"
  MIG=(psql "postgresql://$MIGRATEUR:$MDP@$HOTE/$DB?sslmode=disable")
  # L'admin, mais SUR LA BASE DE TRAVAIL. « ${ADMIN[@]} -d $DB » ne convient
  # pas: avec une URL en argument positionnel, un « -d » ulterieur remplace le
  # nom de base ET fait perdre l'hote et les identifiants de l'URL. La
  # connexion retombait alors sur une socket locale inexistante, et l'echec
  # « stub auth impossible » ne designait pas sa cause.
  ADMIN_DB=(psql "${BASE_URL}/${DB}${QUERY}")
else
  PGH="${PGHOST:-/tmp}"
  ADMIN=(psql -h "$PGH" -U "${PGUSER:-postgres}" -d postgres)
  ADMIN_DB=(psql -h "$PGH" -U "${PGUSER:-postgres}" -d "$DB")
  MIG=(psql -h "$PGH" -U "$MIGRATEUR" -d "$DB")
fi

KO=0
echoue() { echo "      ECHEC: $*"; KO=1; }

# Le migrateur se connecte avec SON mot de passe, jamais celui de
# l'environnement. En CI, `PGPASSWORD` porte celui de l'administrateur: il
# etait donc presente a l'authentification d'`esc_migrator` et refuse
# (« password authentication failed »). En local l'authentification est
# `trust`, si bien que la variable n'etait jamais lue et que le defaut restait
# invisible — la meme asymetrie CI/local que ce fichier existe pour reduire.
mig() { PGPASSWORD="$MDP" "${MIG[@]}" "$@"; }

nettoyer() {
  "${ADMIN[@]}" -q -c "drop database if exists $DB;" >/dev/null 2>&1
  for r in $ROLES_SB; do
    "${ADMIN[@]}" -q -c "reassign owned by $r to ${PGUSER:-postgres};" >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop owned by $r;" >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
}
trap nettoyer EXIT
nettoyer

echo "    installation sous un role de migration non superutilisateur"

# --------------------------------------------------------------------------
# 1. Le modele de privileges de la cible
# --------------------------------------------------------------------------
"${ADMIN[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role $MIGRATEUR login password '$MDP' createrole createdb;
create role esc_service_role nologin;
create role esc_authenticator login password '$MDP';
grant esc_service_role to esc_authenticator;
SQL
[[ $? -eq 0 ]] || { echoue "creation des roles du modele impossible"; exit 1; }

# La verification qui donne son sens a tout le reste: le migrateur n'est PAS
# superutilisateur. Sans elle, ce fichier pourrait tourner en superutilisateur
# et tout valider sans rien prouver.
ATTRS=$("${ADMIN[@]}" -X -q -tAc "
  select rolsuper::text || '/' || rolbypassrls::text || '/' ||
         rolcreaterole::text || '/' || rolcreatedb::text
    from pg_roles where rolname = '$MIGRATEUR'")
if [[ "$ATTRS" != "false/false/true/true" ]]; then
  echoue "le migrateur n'a pas le profil attendu (super/bypassrls/createrole/createdb = $ATTRS)"
  exit 1
fi
echo "      ok: migrateur non superutilisateur, sans bypassrls (createrole+createdb)"

# --------------------------------------------------------------------------
# 2. La base appartient au migrateur, comme en deploiement gere
# --------------------------------------------------------------------------
"${ADMIN[@]}" -q -v ON_ERROR_STOP=1 -c \
  "create database $DB owner $MIGRATEUR;" >/dev/null 2>&1 \
  || { echoue "creation de la base impossible"; exit 1; }

# Le stub `auth` est pose par l'admin puis DONNE au migrateur: chez Supabase
# le schema `auth` preexiste et n'appartient pas au role de migration.
"${ADMIN_DB[@]}" -q -v ON_ERROR_STOP=1 \
  -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1 \
  || { echoue "stub auth impossible"; exit 1; }
"${ADMIN_DB[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant usage on schema auth to $MIGRATEUR;
-- REFERENCES et pas seulement SELECT: le schema declare des cles etrangeres
-- vers auth.users, et PostgreSQL exige REFERENCES pour en creer une. C'est le
-- premier obstacle qu'un role non superutilisateur rencontre, et la CI
-- superutilisateur ne pouvait pas le voir. Chez Supabase le role de migration
-- detient bien ce droit — creer une FK vers auth.users y est l'usage courant.
-- WITH GRANT OPTION: la migration doit pouvoir RETRANSMETTRE ces droits aux
-- roles d'autorite. Sans le grant option, PostgreSQL n'echoue pas — il emet
-- un avertissement et n'accorde rien — et la chaine casse bien plus tard.
grant usage on schema auth to $MIGRATEUR with grant option;
grant select, insert, references on auth.users to $MIGRATEUR with grant option;
grant execute on function auth.uid() to $MIGRATEUR with grant option;
grant create on database $DB to $MIGRATEUR;
SQL

# DECLARATION DE DEPLOIEMENT. Le migrateur cree `eurostruct_deployment` et en
# devient donc detenteur; le controle de topologie l'exige declare. C'est une
# action du deploiement, pas une deduction de la migration.
"${ADMIN[@]}" -q -c   "alter database $DB set eurostruct.approved_deployment_roles = '$MIGRATEUR';"   >/dev/null 2>&1

# CHEMIN GREENFIELD, celui d'un deploiement reel.
#
# Les roles d'autorite ne doivent PAS preexister: la migration les cree, et
# PostgreSQL 16 donne alors au createur une appartenance dont IL est le
# donneur — donc qu'il peut retirer lui-meme en fin de migration.
#
# VERIFIE: une appartenance accordee par un TIERS ne peut PAS etre retiree par
# le migrateur, meme avec ADMIN OPTION. PostgreSQL emet « role X has not been
# granted membership in role Y by role X », repond « REVOKE ROLE » — et
# l'appartenance SURVIT. C'est pourquoi la migration REFUSE dans ce cas au
# lieu d'avertir, ce que le scenario dedie plus bas exerce.
liberer_autorites() {
  local r
  for r in eurostruct_normative_writer eurostruct_normative_bootstrap \
           eurostruct_deployment; do
    "${ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
}
liberer_autorites

# Un role ne se detruit pas tant qu'un objet lui appartient. Les bases de la
# SUITE en portent — elles sont jetables — mais « drop role » ne le dit qu'en
# detail, et le script s'arreterait sur un diagnostic qui ne designe pas
# l'action a faire. On libere donc les bases de test dependantes, et ELLES
# SEULES: le prefixe est verifie deux fois, aucune base etrangere n'est
# touchee.
DEPS=$("${ADMIN[@]}" -X -q -tAc "
  select distinct d.datname
    from pg_shdepend sd
    join pg_database d on d.oid = sd.dbid
    join pg_roles r on r.oid = sd.refobjid
   where r.rolname in ('eurostruct_normative_writer',
                       'eurostruct_normative_bootstrap',
                       'eurostruct_deployment')
     and d.datname like 'eurostruct%'" 2>/dev/null)
for base in $DEPS; do
  [[ "$base" =~ ^eurostruct[a-zA-Z0-9_]*$ ]] || continue
  "${ADMIN[@]}" -q -c "drop database if exists $base;" >/dev/null 2>&1
done
liberer_autorites

RESTE=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_roles
   where rolname in ('eurostruct_normative_writer',
                     'eurostruct_normative_bootstrap')")
if [[ "$RESTE" != "0" ]]; then
  echoue "les roles d'autorite preexistent et n'ont pas pu etre detruits:"
  echoue "  le chemin greenfield ne peut pas etre exerce"
  exit 1
fi

# --------------------------------------------------------------------------
# 3. Les migrations, appliquees PAR LE MIGRATEUR
# --------------------------------------------------------------------------
# La connexion du migrateur d'abord, et SEULE. Sans ce controle, un echec
# d'authentification se presentait comme « 0001_init.sql refusee sous un role
# non superutilisateur » — un diagnostic qui accuse la migration alors que le
# probleme est le raccordement du test.
if ! sonde=$(mig -X -q -tAc 'select current_user' 2>&1); then
  echoue "le migrateur ne peut pas se connecter:"
  sed 's/^/              /' <<<"$sonde" | head -2
  exit 1
fi
echo "      ok: le migrateur se connecte ($sonde)"


for f in "$DB_DIR"/migrations/*.sql; do
  if ! out=$(mig -v ON_ERROR_STOP=1 -q -f "$f" 2>&1); then
    echoue "$(basename "$f") refusee sous un role non superutilisateur:"
    grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$out" | sed 's/^/              /'
    exit 1
  fi
done
echo "      ok: 0001 a 0010 appliquees par un role non superutilisateur"

# L'emprunt d'autorite a bien ete RENDU. C'est la propriete que la migration
# promet, et elle ne vaut que constatee apres coup.
MEMBRES=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_roles autorite cross join pg_roles membre
   where autorite.rolname in ('eurostruct_normative_writer',
                              'eurostruct_normative_bootstrap')
     and membre.oid <> autorite.oid and not membre.rolsuper
     and pg_has_role(membre.rolname, autorite.rolname, 'MEMBER')")
if [[ "$MEMBRES" != "0" ]]; then
  echoue "$MEMBRES membre(s) non superutilisateur(s) des roles d'autorite"
  echoue "  subsistent APRES LA MIGRATION SEULE, avant tout nettoyage"
  echoue "  administrateur. La migration doit revoquer elle-meme ou refuser."
else
  echo "      ok: 0 membre d'autorite apres la migration seule"
fi

# --------------------------------------------------------------------------
# 4. L'amorcage, par l'ACL explicite
# --------------------------------------------------------------------------
# D'ABORD le refus: sans rattachement au role de deploiement, le migrateur ne
# peut pas amorcer. Sans cette moitie, l'ACL ne prouverait rien.
REFUS=$(mig -X -q -tAc "
  select bootstrap_normative_administrator(
    '11111111-1111-1111-1111-111111111111', 'FICTIF Racine',
    'FICTIF — amorcage sans rattachement.')" 2>&1)
if ! grep -q "permission denied\|droit refuse" <<<"$REFUS"; then
  echoue "l'amorcage a ete accepte SANS rattachement au role de deploiement"
  echo "              obtenu: $(head -1 <<<"$REFUS")"
else
  echo "      ok: amorcage refuse tant que le role de deploiement n'est pas accorde"
fi

"${ADMIN[@]}" -q -c "grant eurostruct_deployment to $MIGRATEUR;" >/dev/null 2>&1

AMORCAGE=$(mig -q -v ON_ERROR_STOP=1 2>&1 <<'SQL'
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'FICTIF-ns-admin@eurostruct.test'),
  ('22222222-2222-2222-2222-222222222222', 'FICTIF-ns-verif@eurostruct.test')
on conflict do nothing;
select bootstrap_normative_administrator(
  '11111111-1111-1111-1111-111111111111', 'FICTIF Racine Non-Super',
  'FICTIF — amorcage sous role de migration non superutilisateur.');
SQL
)
if grep -q "ERROR" <<<"$AMORCAGE"; then
  echoue "l'amorcage a echoue APRES rattachement au role de deploiement:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$AMORCAGE" | sed 's/^/              /'
else
  echo "      ok: amorcage reussi via eurostruct_deployment"
fi

# Et le role de deploiement n'a pas gagne l'autorite au passage.
if [[ "$("${ADMIN[@]}" -X -q -tAc "
      select (pg_has_role('eurostruct_deployment',
                          'eurostruct_normative_writer', 'MEMBER') or
              pg_has_role('eurostruct_deployment',
                          'eurostruct_normative_bootstrap', 'MEMBER'))::text")" \
     != "false" ]]; then
  echoue "eurostruct_deployment est membre d'un role d'autorite"
else
  echo "      ok: le role de deploiement n'est membre d'aucun role d'autorite"
fi

# --------------------------------------------------------------------------
# 5. Le parcours complet: octroi -> confirmation -> revocation
# --------------------------------------------------------------------------
# Sous le role de service, pas sous le migrateur: c'est le chemin d'ecriture
# reel. Le migrateur s'y rattache le temps du test, ce qu'un deploiement fait
# de toute facon pour son backend.
"${ADMIN[@]}" -q -c "grant normative_backend to $MIGRATEUR;" >/dev/null 2>&1
# `authenticated` sert au controle de RLS plus bas: le migrateur doit pouvoir
# l'endosser pour verifier ce que voit un porteur de jeton.
"${ADMIN[@]}" -q -c "grant authenticated to $MIGRATEUR;" >/dev/null 2>&1
# Et le role de service a besoin du schema `auth`: la verification d'une cle
# etrangere vers auth.users s'execute avec les droits de l'appelant sur le
# schema, meme si le declencheur normatif, lui, est SECURITY DEFINER.
"${ADMIN_DB[@]}" -q -c   "grant usage on schema auth to normative_backend, authenticated;
   grant select on auth.users to normative_backend, authenticated;"   >/dev/null 2>&1
"${ADMIN[@]}" -q -c \
  "alter database $DB set eurostruct.approved_service_logins = '$MIGRATEUR';" \
  >/dev/null 2>&1

PARCOURS=$(mig -X -q -tAc "
set role normative_backend;
select set_config('request.jwt.claim.sub',
                  '11111111-1111-1111-1111-111111111111', true);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   edition, reason)
values ('22222222-2222-2222-2222-222222222222', 'FICTIF Relecteur Non-Super',
        'can_validate_normative_reference', 'BE', 'EN 1992', '1-1', '2010',
        'FICTIF — habilitation du parcours non superutilisateur.');
select set_config('request.jwt.claim.sub',
                  '22222222-2222-2222-2222-222222222222', true);
insert into normative_rule_confirmations (
  country_code, standard_family, part, rule_id,
  stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
  digest_algorithm, canonicalization_version,
  normative_spec_payload, implementation_payload, evidence_payload,
  stack_payload, stack_snapshot, annex_edition, evidence_items, statement,
  verifier_id, verifier_name, verified_at, authorisation_grant_id,
  authorisation_scope, idempotency_key)
select 'BE', 'EN 1992', '1-1', 'test.nonsuperuser',
  encode(sha256(convert_to(pile, 'UTF8')), 'hex'),
  encode(sha256(convert_to(spec, 'UTF8')), 'hex'),
  encode(sha256(convert_to(impl, 'UTF8')), 'hex'),
  encode(sha256(convert_to(ev,   'UTF8')), 'hex'),
  'sha256', 'esc-canon/1', spec, impl, ev, pile, '{}'::jsonb, 'x',
  '[]'::jsonb, 'FICTIF — lecture sous role non superutilisateur.',
  '00000000-0000-0000-0000-000000000000', 'FICTIF', now(), null, '{}'::jsonb,
  'FICTIF-nonsuper-1'
from (select
  '{\"canonicalization_version\":\"esc-canon/1\",\"kind\":\"normative_spec\",\"rule_id\":\"test.nonsuperuser\"}' as spec,
  '{\"canonicalization_version\":\"esc-canon/1\",\"kind\":\"implementation\",\"rule_id\":\"test.nonsuperuser\"}' as impl,
  '{\"canonicalization_version\":\"esc-canon/1\",\"items\":[{\"clause\":\"c\",\"document_digest\":\"' || repeat('b',64) || '\",\"document_role\":\"annexe\",\"edition\":\"2010\",\"page_printed\":1,\"quote\":\"FICTIF\",\"quote_digest\":\"' || encode(sha256(convert_to('FICTIF','UTF8')),'hex') || '\",\"reference\":\"FICTIF ANB\"}],\"kind\":\"evidence\"}' as ev,
  '{\"components\":[{\"application_order\":2,\"document_digest\":\"' || repeat('b',64) || '\",\"edition\":\"2010\",\"reference\":\"FICTIF ANB\",\"role\":\"annexe\"}],\"country_code\":\"BE\",\"kind\":\"normative_stack\",\"part\":\"1-1\",\"schema_version\":\"esc-stack/1\",\"standard_family\":\"EN 1992\"}' as pile
) p;
select count(*) from normative_rule_confirmations
 where idempotency_key = 'FICTIF-nonsuper-1';
" 2>&1)

if [[ "$(tail -1 <<<"$PARCOURS")" != "1" ]]; then
  echoue "le parcours octroi -> confirmation a echoue:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$PARCOURS" | sed 's/^/              /'
else
  echo "      ok: octroi puis confirmation sous le role de service"
fi

# Revocation de la confirmation, par son auteur.
REVOC=$(mig -X -q -tAc "
set role normative_backend;
select set_config('request.jwt.claim.sub',
                  '22222222-2222-2222-2222-222222222222', true);
insert into normative_rule_confirmation_revocations (confirmation_id, reason)
select id, 'FICTIF — retrait de ma propre lecture.'
  from normative_rule_confirmations
 where idempotency_key = 'FICTIF-nonsuper-1';
select count(*) from normative_rule_confirmation_revocations;" 2>&1)

if [[ "$(tail -1 <<<"$REVOC")" != "1" ]]; then
  echoue "la revocation de confirmation a echoue:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$REVOC" | sed 's/^/              /'
else
  echo "      ok: revocation de la confirmation par son auteur"
fi

# Et la RLS s'applique reellement: sans bypassrls, un porteur de jeton tiers
# ne voit pas la confirmation d'autrui. Ce controle ne vaut QUE sous un role
# non superutilisateur — c'est tout l'objet de ce fichier.
VU=$(mig -X -q -tAc "
set role authenticated;
select set_config('request.jwt.claim.sub',
                  '11111111-1111-1111-1111-111111111111', true);
select count(*) from normative_rule_confirmations;" 2>&1 | tail -1)
if [[ "$VU" != "0" ]]; then
  echoue "RLS PERCEE hors superutilisateur: un tiers voit $VU confirmation(s)"
else
  echo "      ok: RLS effective sous un role sans bypassrls"
fi

echo ''
echo '================================================='
echo ' Installation non superutilisateur verifiee.'
echo '================================================='
exit $KO
