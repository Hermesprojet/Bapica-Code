#!/usr/bin/env bash
#
# EUROSTRUCT — LE PARCOURS D'AUTORITE, DEPUIS L'API HTTP
#
#   db/test/api_e2e.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS ETABLIT, ET EN QUOI IL DIFFERE DE `provider_contract.sh`
# ---------------------------------------------------------------------------
# `provider_contract.sh` eprouve le CONTRAT du provider, avec un
# authentificateur FICTIF: il prouve que le provider pose l'identite que
# l'authentificateur rend, sans jamais la recevoir en parametre.
#
# Celui-ci eprouve le chemin PRODUIT, de bout en bout:
#
#   jeton Bearer brut -> AuthentificateurSupabase (signature RSA reelle)
#   -> ContexteAuthentifie -> creer_provider_de_production -> transaction
#   -> SET LOCAL eurostruct.actor_id -> primitive -> commit -> contexte parti
#
# Les deux identites A et B sont portees par des JETONS SIGNES, pas par des
# chaines de caracteres passees a une fonction. C'est la difference entre
# « le provider honore le contrat » et « l'application authentifie ».
#
# POURQUOI UN HARNAIS DE PLUS PLUTOT QU'UN PARAMETRE DANS L'EXISTANT
# -------------------------------------------------------------------
# La campagne de mutations vise `provider_contract.sh` et `provider_contract.py`
# — sept controles, F1 a F6. Y ajouter un aiguillage pour lancer une AUTRE
# charge utile obligerait a rejouer ces sept controles a chaque retouche de
# l'API. Le decor est donc repose ici, et rien de ce que la campagne mesure
# n'est touche.
#
# SANS PILOTE NI FASTAPI, IL REND 4 — NON EXECUTE. Une surface qu'on n'a pas
# pu exercer n'est pas une surface qui a tenu.
#
# Aucune identite reelle, aucun secret, aucune instance Supabase. Les cles RSA
# sont generees dans le processus de test et meurent avec lui.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: api_e2e.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "api_e2e.sh" || exit 2
harnais_verrou_prendre  "api_e2e.sh" || exit $?
exiger_cluster_jetable  "api_e2e.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "api_e2e.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_ma_${JETON}"; CTL="${PREFIXE}_ca_${JETON}"
SVC="${PREFIXE}_sa_${JETON}"; BASE="${PREFIXE}_da_${JETON}"
MDP="FICTIF-api-${JETON}"
MANDAT="11111111-5555-5555-5555-555555555501:FICTIF-EMPREINTE-API-${JETON}"
ACTEUR_A="22222222-5555-5555-5555-5555555555a1"
ACTEUR_B="33333333-5555-5555-5555-5555555555b1"
RACINE_ID="11111111-5555-5555-5555-555555555501"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
# `mig` EST APPELE PAR SON NOM depuis `esc_appliquer_migration`, qui recoit
# « mig » en argument. L'oublier fait appliquer les migrations sous le mauvais
# role, et le registre devient illisible: MIGRATION_LEDGER_UNREADABLE.
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
  harnais_postcondition_nettoyage "api_e2e.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

# LES DEUX OUTILS SONT VERIFIES AVANT DE POSER QUOI QUE CE SOIT. Poser un
# decor complet pour decouvrir ensuite qu'on ne peut pas s'en servir gaspille
# une minute et brouille le diagnostic.
MANQUANTS=""
python3 -c "import psycopg2" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS psycopg2"
python3 -c "import fastapi"  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS fastapi"
python3 -c "import jwt"      >/dev/null 2>&1 || MANQUANTS="$MANQUANTS pyjwt"
python3 -c "import eurostruct_api" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS eurostruct-api"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: api_e2e.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Le parcours HTTP d'autorite ne peut pas etre eprouve, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi

echo "    tranche applicative: le parcours d'autorite, depuis l'API"

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
    esc_diag_rapporter "phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ECHEC: la base n'est pas ACTIVE ($ETAT)" >&2
  exit 1
fi

ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_B')
on conflict do nothing;
SQL

ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine api')" \
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
GA="$(octroyer "$ACTEUR_A" 'FICTIF autorite de A (api)')"
GB="$(octroyer "$ACTEUR_B" 'FICTIF autorite de B (api)')"
if [[ ! "$GA" =~ ^[0-9a-f-]{36}$ || ! "$GB" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: les habilitations de A et B n'ont pas ete creees." >&2
  echo "             A=$GA B=$GB" >&2
  exit 1
fi

# LE PARCOURS LUI-MEME. La DSN ne transite QUE par l'environnement du
# sous-processus: elle n'apparait ni en argument, ni dans un fichier, ni dans
# la sortie. `ps` ne la montrera pas.
export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
# UNE SECONDE DSN, D'OBSERVATION SEULEMENT. Le login de service n'a AUCUN
# privilege de table — tout passe par les trois primitives SECURITY DEFINER —
# et c'est exactement ce qu'on veut. Mais prouver qu'un jeton forge n'a RIEN
# ecrit demande de regarder la table, ce que le service ne peut pas faire.
# Cette DSN sert donc au constat, jamais au parcours: aucune route ne la voit.
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_E2E_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_E2E_ACTEUR_B="$ACTEUR_B"

python3 -m pytest "$RACINE/api/tests/test_e2e_postgres.py" -q \
        -p no:cacheprovider --no-header
CODE=$?
unset EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS \
      EUROSTRUCT_E2E_ACTEUR_A EUROSTRUCT_E2E_ACTEUR_B

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Le parcours d'autorite tient depuis l'API, avec"
  echo " deux identites cryptographiquement authentifiees."
  echo "================================================="
fi
exit $CODE
