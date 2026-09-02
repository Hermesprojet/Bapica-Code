#!/usr/bin/env bash
#
# EUROSTRUCT — INITIALISATION DE LA BASE, IDEMPOTENTE
#
# Exécutée par le service `init` de `compose.yaml`, avant l'API et avant
# l'interface. Elle sort en 0 quand la base SERT, et en non-zéro sinon : la
# composition n'ouvre alors rien du tout, ce qui est le comportement voulu —
# une API branchée sur une base non initialisée rend des 500 en boucle et
# ressemble à une panne applicative.
#
# CE QU'ELLE FAIT, DANS CET ORDRE
# --------------------------------
#   1. les rôles de déploiement et le login applicatif ;
#   2. les privilèges que les migrations exigent ;
#   3. les réglages de base que les migrations lisent ;
#   4. la COMMANDE OFFICIELLE de déploiement — sceau, migrations, activation ;
#   5. l'appartenance du login applicatif au backend d'autorité ;
#   6. l'amorçage de la racine d'autorité, si — et seulement si — un mandat
#      est déclaré ;
#   7. les postconditions : ACTIVE, rôles présents, login non-superutilisateur.
#
# ELLE NE DETRUIT RIEN. Aucun `drop database`, aucun `drop role`, aucun
# `drop owned by`. Ce n'est pas un harnais : relancée sur un volume qui porte
# déjà tout, elle constate et sort — c'est ce qui rend le second démarrage sûr.
#
# AUCUN SECRET DANS `argv`
# -------------------------
# Les mots de passe viennent de l'environnement et ne sont jamais passés en
# argument : `argv` est lisible par tout processus de la machine. Aucun n'est
# journalisé, et aucune DSN complète n'est affichée — les diagnostics nomment
# l'hôte, la base et le rôle, jamais la chaîne.
set -uo pipefail

echec() { echo "INIT: ECHEC — $*" >&2; exit 1; }
dire()  { echo "INIT: $*"; }

# ---------------------------------------------------------------------------
# CE QUE L'ENVIRONNEMENT DOIT PORTER
# ---------------------------------------------------------------------------
for v in POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB \
         EUROSTRUCT_DB_HOST \
         EUROSTRUCT_MIGRATOR_DB_USER EUROSTRUCT_MIGRATOR_DB_PASSWORD \
         EUROSTRUCT_PLAN_DB_USER EUROSTRUCT_PLAN_DB_PASSWORD \
         EUROSTRUCT_APP_DB_USER EUROSTRUCT_APP_DB_PASSWORD; do
  [[ -n "${!v:-}" ]] || echec "$v n'est pas definie."
done

HOTE="$EUROSTRUCT_DB_HOST"
PORT="${EUROSTRUCT_DB_PORT:-5432}"
BASE="$POSTGRES_DB"
MIG="$EUROSTRUCT_MIGRATOR_DB_USER"
CTL="$EUROSTRUCT_PLAN_DB_USER"
APP="$EUROSTRUCT_APP_DB_USER"

# UN NOM DE ROLE N'EST PAS UNE CHAINE LIBRE. Il finit dans un identifiant SQL;
# on le borne ici plutot que de compter sur la citation seule.
for duo in "migrateur:$MIG" "plan:$CTL" "applicatif:$APP"; do
  nom="${duo##*:}"
  [[ "$nom" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] \
    || echec "le login ${duo%%:*} « $nom » n'est pas un identifiant admissible."
done
if [[ "$APP" == "$POSTGRES_USER" ]]; then
  echec "EUROSTRUCT_APP_DB_USER vaut POSTGRES_USER. L'API se connecterait avec
       le SUPERUTILISATEUR de l'image, pour qui RLS ne s'applique pas et pour
       qui toute politique est decorative. Le login applicatif doit etre
       distinct, et non-superutilisateur."
fi

# ---------------------------------------------------------------------------
# LE SUPERUTILISATEUR DE L'IMAGE — le seul acteur qui puisse creer des roles
# ---------------------------------------------------------------------------
export PGHOST="$HOTE" PGPORT="$PORT" PGCONNECT_TIMEOUT=5
sup()  { PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" \
           psql -X -q -v ON_ERROR_STOP=1 -d postgres "$@"; }
supb() { PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" \
           psql -X -q -v ON_ERROR_STOP=1 -d "$BASE" "$@"; }
q()    { PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" \
           psql -X -q -tA -d "$BASE" -c "$1" 2>/dev/null | tr -d ' '; }

# `depends_on: service_healthy` couvre le cas ordinaire. Cette attente couvre
# le cas ou le conteneur est relance seul, sans que la sonde ait rejoue.
pret=0
for _ in $(seq 1 60); do
  if PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" \
       psql -X -q -tAc "select 1" -d postgres >/dev/null 2>&1; then
    pret=1; break
  fi
  sleep 1
done
[[ "$pret" -eq 1 ]] || echec "la base $BASE sur $HOTE:$PORT ne repond pas."

# ---------------------------------------------------------------------------
# 1. LES ROLES — CREES S'ILS MANQUENT, JAMAIS DETRUITS
# ---------------------------------------------------------------------------
# LE MOT DE PASSE PASSE PAR UNE VARIABLE psql (`:'...'`), citee cote client. Le
# concatener dans la chaine SQL laisserait une apostrophe dans un mot de passe
# casser la commande — ou pire, la prolonger.
creer_login() {   # creer_login <role> <variable-de-mot-de-passe> <attributs>
  local role="$1" mdp="$2" attrs="$3"
  PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -X -q -v ON_ERROR_STOP=1 -d postgres \
       -v role="$role" -v mdp="$mdp" -v attrs="$attrs" <<'FINSQL'
select format(
  case when exists (select 1 from pg_roles where rolname = :'role')
       then 'alter role %I with login password %L'
       else 'create role %I with login password %L ' || :'attrs'
  end, :'role', :'mdp') as ordre \gset
:ordre
FINSQL
}

creer_login "$MIG" "$EUROSTRUCT_MIGRATOR_DB_PASSWORD" "createrole createdb" \
  || echec "creation du role migrateur « $MIG »."
creer_login "$CTL" "$EUROSTRUCT_PLAN_DB_PASSWORD" "createrole" \
  || echec "creation du role de plan de controle « $CTL »."
# LE LOGIN APPLICATIF N'A NI `createrole` NI `createdb`. C'est celui que l'API
# presente a chaque requete: lui donner de quoi creer un role lui donnerait de
# quoi s'octroyer ce qu'il veut.
creer_login "$APP" "$EUROSTRUCT_APP_DB_PASSWORD" "" \
  || echec "creation du login applicatif « $APP »."

# LES DEUX ROLES SONT ENDOSSABLES PAR LE SUPERUTILISATEUR. Sans cela, `psql`
# ne peut pas prendre leur role, et `alter database ... owner to` refuse: on ne
# donne pas une base a un role dont on n'est pas membre.
sup -c "grant \"$CTL\" to \"$POSTGRES_USER\";" >/dev/null 2>&1
sup -c "grant \"$MIG\" to \"$POSTGRES_USER\";" >/dev/null 2>&1

# LA BASE APPARTIENT AU MIGRATEUR, ET C'EST CE QUI LUI DONNE `CREATE` SUR
# `public`.
#
# Mesure sur volume neuf: sans cela, `0001_init.sql` echouait des sa premiere
# instruction sur « permission denied for schema public ». Depuis PostgreSQL 15,
# `public` n'est plus ouvert a tous: il appartient a `pg_database_owner`, et
# seul le PROPRIETAIRE de la base y cree. L'image cree `POSTGRES_DB` au nom du
# superutilisateur; les harnais, eux, creaient la base « owner MIG » — la
# composition ne reproduisait donc pas la configuration que toutes les
# postconditions supposent.
#
# On ne remplace PAS cela par un `grant create on schema public to MIG`: le
# droit resterait apres le deploiement, alors que l'etape 9 de la commande
# officielle exige zero capacite residuelle du migrateur.
sup -c "alter database \"$BASE\" owner to \"$MIG\";" >/dev/null 2>&1
if [[ "$(q "select pg_get_userbyid(datdba) from pg_database
             where datname = '$BASE'")" != "$MIG" ]]; then
  echec "la base $BASE n'appartient pas au migrateur « $MIG ». Les migrations
       ne pourraient rien creer dans le schema public."
fi

# ---------------------------------------------------------------------------
# 2. LE SCHEMA D'AUTHENTIFICATION
# ---------------------------------------------------------------------------
# EN PRODUCTION C'EST SUPABASE QUI POSE `auth.users` ET `auth.uid()`. Ils ne
# sont pas de notre ressort, et ce script ne les fabrique pas — sauf demande
# EXPLICITE, pour une composition locale ou un runner, ou aucun Supabase ne
# tourne. Le rendre implicite reviendrait a poser en production une table
# `auth.users` vide que personne n'alimente.
if [[ "${EUROSTRUCT_LOCAL_AUTH_STUB:-non}" == "oui" ]]; then
  dire "schema auth LOCAL et FICTIF (EUROSTRUCT_LOCAL_AUTH_STUB=oui)."
  supb -f /opt/eurostruct/db/test/00_supabase_stub.sql >/dev/null 2>&1 \
    || echec "le schema auth local n'a pas pu etre pose."
fi
if [[ "$(q "select count(*) from pg_namespace where nspname = 'auth'")" != "1" ]]; then
  echec "le schema « auth » est absent de $BASE. En production, c'est Supabase
       qui le pose; en local, declarez EUROSTRUCT_LOCAL_AUTH_STUB=oui pour un
       schema FICTIF. Les migrations en dependent et refuseraient plus loin,
       avec un diagnostic moins clair."
fi

# ---------------------------------------------------------------------------
# 3. LES PRIVILEGES ET LES REGLAGES QUE LES MIGRATIONS LISENT
# ---------------------------------------------------------------------------
supb >/dev/null 2>&1 <<FINSQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
FINSQL

# CES REGLAGES SONT DES DECLARATIONS D'EXPLOITANT, PAS DES PREUVES. Ils disent
# quels roles sont admis a deployer et quels logins sont admis a servir; les
# migrations les confrontent ensuite au catalogue.
sup -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
sup -c "alter database \"$BASE\"
          set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
sup -c "alter database \"$BASE\"
          set eurostruct.approved_service_logins = '$APP';" >/dev/null 2>&1
sup -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$APP';" >/dev/null 2>&1
if [[ -n "${EUROSTRUCT_BOOTSTRAP_MANDATE:-}" ]]; then
  sup -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate =
            '$EUROSTRUCT_BOOTSTRAP_MANDATE';" >/dev/null 2>&1
fi

# ---------------------------------------------------------------------------
# 4. LA COMMANDE OFFICIELLE — sceau, migrations, finalisation
# ---------------------------------------------------------------------------
# ON NE REJOUE PAS LES TROIS PHASES A LA MAIN. `tools/deploy_eurostruct.sh` est
# le chemin officiel, il est eprouve par `official_deployment.sh`, et sa
# relance est SURE: la phase 0 refuse sans muter si le sceau est deja pose, la
# phase 1 saute ce que le registre declare applique, la phase 2 constate
# « deja finalise » si le manifeste presente est celui qui a ete approuve.
# C'est cela, et non une propriete des fichiers SQL, qui rend le second
# demarrage sur le meme volume sans danger.
#
# `--auto-heberge`: le plan de controle et le migrateur sont deux roles du
# meme cluster, pose par le meme operateur. La commande exige qu'on l'assume
# explicitement plutot que de le deviner.
dire "deploiement (sceau, migrations, activation)…"
SORTIE_DEPLOI="$(
  ESC_PLAN_URL="postgresql://$CTL:$EUROSTRUCT_PLAN_DB_PASSWORD@$HOTE:$PORT/$BASE?sslmode=${EUROSTRUCT_DB_SSLMODE:-disable}" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$EUROSTRUCT_MIGRATOR_DB_PASSWORD@$HOTE:$PORT/$BASE?sslmode=${EUROSTRUCT_DB_SSLMODE:-disable}" \
  bash /opt/eurostruct/tools/deploy_eurostruct.sh --auto-heberge 2>&1
)"
CODE_DEPLOI=$?
if [[ $CODE_DEPLOI -ne 0 ]]; then
  # LE MOT DE PASSE N'EST PAS DANS `argv`, ET IL NE DOIT PAS ETRE DANS LE
  # JOURNAL NON PLUS. On filtre toute chaine de connexion de la sortie avant
  # de l'afficher: une DSN dans les journaux d'un runner y reste.
  echo "$SORTIE_DEPLOI" | sed -E 's#postgres(ql)?://[^ ]*#postgresql://<masquee>#g' >&2
  echec "la commande officielle de deploiement a rendu $CODE_DEPLOI."
fi

# ---------------------------------------------------------------------------
# 5. LE LOGIN APPLICATIF ENTRE DANS LE BACKEND D'AUTORITE
# ---------------------------------------------------------------------------
# `eurostruct_authority_backend` n'a AUCUN privilege de table: il n'atteint que
# les primitives SECURITY DEFINER. C'est ce qui garantit que l'acteur est
# derive de la session et jamais fourni par l'appelant.
PLAN_PSQL() { PGUSER="$CTL" PGPASSWORD="$EUROSTRUCT_PLAN_DB_PASSWORD" \
                psql -X -q -d postgres "$@"; }
PLAN_PSQL -c "grant eurostruct_authority_backend to \"$APP\";" >/dev/null 2>&1
if [[ "$(q "select pg_has_role('$APP','eurostruct_authority_backend','member')")" != "t" ]]; then
  echec "le login applicatif « $APP » n'est pas membre de
       eurostruct_authority_backend. Les routes d'autorite rendraient 503 sans
       que rien ne dise pourquoi."
fi

# ---------------------------------------------------------------------------
# 6. LA RACINE D'AUTORITE — seulement si un mandat est declare
# ---------------------------------------------------------------------------
# SANS MANDAT, PAS D'AMORCAGE, ET C'EST LE COMPORTEMENT CORRECT. Amorcer une
# racine, c'est designer la personne qui pourra habiliter les autres: cela
# vient d'une decision prise HORS du systeme, pas d'un script qui s'execute au
# demarrage. Le mandat est la forme sous laquelle cette decision entre.
if [[ -n "${EUROSTRUCT_BOOTSTRAP_MANDATE:-}" && -n "${EUROSTRUCT_BOOTSTRAP_ACTOR:-}" ]]; then
  DEJA="$(q "select count(*) from normative_authorisation_grants
              where origin = 'bootstrap'")"
  if [[ "$DEJA" == "0" ]]; then
    dire "amorcage de la racine d'autorite (mandat declare)."
    supb -c "insert into auth.users (id)
             values ('$EUROSTRUCT_BOOTSTRAP_ACTOR')
             on conflict do nothing;" >/dev/null 2>&1
    PGUSER="$CTL" PGPASSWORD="$EUROSTRUCT_PLAN_DB_PASSWORD" \
      psql -X -q -tA -d "$BASE" \
        -c "select bootstrap_normative_administrator(
              '$EUROSTRUCT_BOOTSTRAP_ACTOR'::uuid,
              '${EUROSTRUCT_BOOTSTRAP_NAME:-racine}',
              '${EUROSTRUCT_BOOTSTRAP_REASON:-amorcage a l initialisation}')" \
        >/dev/null 2>&1
    if [[ "$(q "select count(*) from normative_authorisation_grants
                 where origin = 'bootstrap'")" == "0" ]]; then
      echec "l'amorcage n'a produit aucune habilitation. Le mandat declare ne
       correspond probablement pas a l'acteur presente: la primitive exige que
       le mandat NOMME le principal amorce."
    fi
  else
    dire "racine d'autorite deja amorcee — rien a faire."
  fi
else
  dire "aucun mandat d'amorcage declare: la racine d'autorite n'est PAS
      amorcee. Les primitives existent mais aucune habilitation n'est
      efficace, et toute proposition sera refusee. C'est voulu: designer la
      premiere personne habilitee est une decision, pas un demarrage."
fi

# ---------------------------------------------------------------------------
# 7. LES POSTCONDITIONS — ce qu'on annonce, on le constate
# ---------------------------------------------------------------------------
ETAT="$(q "select normative_activation_state()")"
[[ "$ETAT" == "ACTIVE" ]] \
  || echec "la base n'est pas ACTIVE apres initialisation (etat: « ${ETAT:-aucun} »)."

MANQUANTS="$(q "select coalesce(string_agg(r, ','), '') from unnest(array[
    'eurostruct_normative_writer','eurostruct_authority_backend',
    'normative_backend','normative_governance']) r
   where not exists (select 1 from pg_roles where rolname = r)")"
[[ -z "$MANQUANTS" ]] || echec "roles applicatifs absents: $MANQUANTS"

EST_SUPER="$(q "select rolsuper from pg_roles where rolname = '$APP'")"
[[ "$EST_SUPER" == "f" ]] \
  || echec "le login applicatif « $APP » est SUPERUTILISATEUR: RLS ne
       s'appliquerait pas a lui, et toute politique serait decorative."

dire "base $BASE ACTIVE; l'API se connectera comme « $APP » (non-superutilisateur)."
exit 0
