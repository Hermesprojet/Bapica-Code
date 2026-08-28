#!/usr/bin/env bash
#
# EUROSTRUCT — LE CONTRAT DU PROVIDER, SUR UNE BASE DEPLOYEE
#
#   db/test/provider_contract.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER FAIT, ET CE QU'IL NE FAIT PAS
# ------------------------------------------------
# Il POSE le decor — sceau, migrations, finalisation, identites metier — puis
# passe la main a `provider_contract.py`, qui eprouve le contrat du
# `PostgresConfirmationProvider` contre ce serveur.
#
# IL NE PROUVE AUCUNE AUTHENTIFICATION REELLE. L'authentificateur du test est
# FICTIF et le dit dans son nom. Ce qui est etabli, c'est le CONTRAT
# d'integration: le provider refuse sans authentificateur, pose l'identite que
# celui-ci rend, et la retire — commit, rollback ou exception. Tant qu'aucun
# verificateur de jeton concret n'existe dans ce depot, le sous-systeme reste
# BLOCKED_BY_REAL_AUTH.
#
# SANS PILOTE POSTGRESQL, IL REND 4 — NON EXECUTE. C'est la convention de
# cette suite: une surface qu'on n'a pas pu exercer n'est pas une surface qui
# a tenu, et elle ne doit pas passer pour verte.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: provider_contract.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "provider_contract.sh" || exit 2
harnais_verrou_prendre  "provider_contract.sh" || exit $?
exiger_cluster_jetable  "provider_contract.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "provider_contract.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mv_${JETON}"; CTL="${PREFIXE}_cv_${JETON}"
SVC="${PREFIXE}_sv_${JETON}"; BASE="${PREFIXE}_dv_${JETON}"
MDP="FICTIF-pv-${JETON}"
MANDAT="11111111-4444-4444-4444-444444444401:FICTIF-EMPREINTE-PROVIDER-${JETON}"
# Deux identites metier FICTIVES: A propose, B approuve. Elles ne sont jamais
# passees en parametre au provider — c'est tout l'objet du contrat.
ACTEUR_A="22222222-4444-4444-4444-4444444444a1"
ACTEUR_B="33333333-4444-4444-4444-4444444444b1"
# La racine qui habilite A et B. Le mandat d'amorcage la nomme: c'est ce qui
# distingue « la premiere autorite est MANDATEE » de « elle s'est choisie ».
RACINE_ID="11111111-4444-4444-4444-444444444401"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

NETTOYAGE_KO=0
sortie_propre() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "provider_contract.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

# LE PILOTE EST VERIFIE AVANT DE POSER QUOI QUE CE SOIT. Poser un decor
# complet pour decouvrir ensuite qu'on ne peut pas s'en servir gaspille une
# minute et brouille le diagnostic.
if ! python3 -c "import psycopg2" >/dev/null 2>&1; then
  echo "NON EXECUTE: provider_contract.sh — aucun pilote PostgreSQL." >&2
  echo "       `python3 -c 'import psycopg2'` echoue. Les proprietes SQL du" >&2
  echo "       provider (SET LOCAL, non-fuite de pool) ne peuvent pas etre" >&2
  echo "       eprouvees, et une surface non executee n'est pas verte." >&2
  echo "       Installer: pip install psycopg2-binary" >&2
  exit 4
fi

echo "    6.3c: le contrat du provider, sur une base deployee"

creer_role "$MIG" "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL" "login password '$MDP' createrole"          || exit 1
creer_role "$SVC" "login password '$MDP'"                     || exit 1
adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
creer_base "$BASE" "owner \"$MIG\"" || exit 1
registre_base "$BASE"

admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL

if ! SORTIE=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
  echo "      ECHEC: phase 0: $(grep -m1 ERROR <<<"$SORTIE" | cut -c1-160)" >&2
  exit 1
fi
adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1

for f in "$DB_DIR"/migrations/*.sql; do
  if ! esc_appliquer_migration "$f" mig; then
    echo "      ECHEC: $(basename "$f"):" >&2
    grep -m1 ERROR <<<"$ESC_MIGRATION_SORTIE" | cut -c1-180 >&2
    # L'IDENTIFIANT D'INVARIANT SURVIT A LA TRONCATURE.
    # Mesure: `cut -c1-200` coupait juste avant
    # `AUTHORITY_*`, et deux mutations ont ete comptees
    # SURVIVED faute que le nom atteigne le lecteur.
    grep -oE "AUTHORITY_[A-Z0-9_]+" <<<"$ESC_MIGRATION_SORTIE" | sort -u | head -4 \
      | sed 's/^/              invariant: /' >&2
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment('$M')" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ECHEC: la base n'est pas ACTIVE ($ETAT)" >&2
  exit 1
fi

# LE LOGIN DE SERVICE RECOIT LE ROLE D'EXECUTION, par le plan de controle qui
# seul en detient l'ADMIN — c'est ce que fait un deploiement reel.
ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_B')
on conflict do nothing;
SQL

# LA CHAINE D'AUTORITE: la racine est AMORCEE sous mandat, puis elle habilite
# A et B sur la MEME portee. Deux principals distincts, chacun avec sa propre
# source — c'est le contrat du quatre-yeux, et le provider doit l'honorer sans
# jamais recevoir leur identite en parametre.
ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine provider')" \
  >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: aucune racine amorcee; les primitives ne peuvent rien faire." >&2
  exit 1
fi
octroyer() {   # octroyer <beneficiaire> <motif>
  PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -tAc \
    "set eurostruct.actor_id = '$RACINE_ID';
     insert into normative_authorisation_grants
       (grantee_id, grantee_name, permission, country_code, standard_family,
        part, edition, reason, parent_grant_id)
     values ('$1', 'FICTIF $1', 'can_validate_normative_reference', 'BE',
             'EN 1992', '1-1', '2004', '$2', '$GR')" -d "$BASE" >/dev/null 2>&1
  q "select id from normative_authorisation_grants where reason = '$2'"
}
GA="$(octroyer "$ACTEUR_A" 'FICTIF autorite de A (provider)')"
GB="$(octroyer "$ACTEUR_B" 'FICTIF autorite de B (provider)')"
if [[ ! "$GA" =~ ^[0-9a-f-]{36}$ || ! "$GB" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: les habilitations de A et B n'ont pas ete creees." >&2
  echo "             A=$GA B=$GB" >&2
  exit 1
fi

# LE CONTRAT LUI-MEME. Il rend 4 si le pilote manque — deja verifie plus haut,
# mais la double garde ne coute rien et le script Python est aussi lancable
# seul.
PGHOST="${PGHOST:-/var/run/postgresql}" \
  python3 "$HERE/provider_contract.py" "$BASE" "$SVC" "$MDP" \
          "$ACTEUR_A" "$ACTEUR_B" "$GA" "$GB"
CODE=$?

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Le contrat du provider tient. L'authentification"
  echo " elle-meme reste BLOCKED_BY_REAL_AUTH."
  echo "================================================="
fi
exit $CODE
