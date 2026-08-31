#!/usr/bin/env bash
#
# EUROSTRUCT — ENTRER DANS L'APPLICATION QUAND ON N'Y EST PAS ENCORE
#
#   db/test/entree_application.sh <prefixe-de-base-jetable>
#
# LE DEFAUT PRODUIT QUE CE HARNAIS FERME
# ----------------------------------------
# Tout le produit suppose une ligne dans `organization_members`. Sans elle,
# `GET /v1/projects` rend une liste VIDE — pas une erreur, pas une
# explication, un ecran nu — et `POST /v1/projects` refuse. C'est correct, et
# c'est un cul-de-sac: AUCUNE ROUTE NE PERMETTAIT D'EN SORTIR.
#
# La seule facon d'exister dans l'application etait un `insert` fait a la main
# par le proprietaire de la base. Autrement dit: le produit n'avait pas de
# porte d'entree. Un compte tout neuf, parfaitement authentifie, arrivait
# devant un ecran vide et ne pouvait rien faire — jamais.
#
# CE QUE CE DECOR A DE PARTICULIER
# ----------------------------------
# IL NE POSE AUCUNE ORGANISATION, ET AUCUNE ADHESION. C'est le seul decor du
# depot qui parte de la, et c'est le seul qui puisse mesurer l'entree: un
# harnais qui pose d'avance les adhesions dont il a besoin ne peut pas
# constater qu'on ne sait pas les creer.
#
# Il pose une base DEPLOYEE et ACTIVE — migrations, roles, racine d'autorite —
# quatre identites dans `auth.users`, et une Annexe Nationale en vigueur sans
# laquelle la creation d'un projet refuserait pour une raison sans rapport.
#
# LES QUATRE IDENTITES
# ---------------------
#   F — la fondatrice: elle cree son organisation et en devient `owner`;
#   I — l'invitee: elle rejoint par une invitation, jamais autrement;
#   T — le tiers: authentifie, jamais invite. Il ne doit RIEN voir;
#   X — l'opportuniste: invitations revoquees, expirees, deja consommees.
#
# AUCUN DE CES COMPTES N'EST REEL, et aucune attestation produite ici n'est une
# validation. `SUPABASE_UNVERIFIED` reste vrai.
#
# SANS PILOTE NI FASTAPI, IL REND 4 — NON EXECUTE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: entree_application.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "entree_application.sh" || exit 2
harnais_verrou_prendre  "entree_application.sh" || exit $?
exiger_cluster_jetable  "entree_application.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "entree_application.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-entree-${JETON}"
MANDAT="11111111-6666-6666-6666-666666666601:FICTIF-EMPREINTE-ENTREE-${JETON}"
RACINE_ID="11111111-6666-6666-6666-666666666601"
ACTEUR_F="22222222-6666-6666-6666-66666666fff1"
ACTEUR_I="22222222-6666-6666-6666-66666666aaa1"
ACTEUR_T="22222222-6666-6666-6666-66666666bbb1"
ACTEUR_X="22222222-6666-6666-6666-66666666ccc1"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

MAGASIN=""
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
  harnais_postcondition_nettoyage "entree_application.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  if [[ -n "$MAGASIN" && -d "$MAGASIN" && "$MAGASIN" == /tmp/* ]]; then
    rm -rf -- "$MAGASIN" || NETTOYAGE_KO=1
  fi
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

MANQUANTS=""
python3 -c "import psycopg2" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS psycopg2"
python3 -c "import fastapi"  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS fastapi"
python3 -c "import jwt"      >/dev/null 2>&1 || MANQUANTS="$MANQUANTS pyjwt"
python3 -c "import eurostruct_api" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS eurostruct-api"
python3 -c "from fastapi.testclient import TestClient" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS httpx(TestClient)"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: entree_application.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi

echo "    tranche applicative: entrer dans l'application, et constituer son bureau"

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
    esc_diag_rapporter "migrations / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
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

# ---------------------------------------------------------------------
# LE DECOR, ET CE QU'IL NE POSE PAS.
#
# QUATRE IDENTITES, ZERO ORGANISATION, ZERO ADHESION. C'est tout l'objet de ce
# harnais: si le decor posait un bureau et ses membres, il ne resterait plus
# rien a prouver sur l'entree.
#
# UNE ANNEXE NATIONALE EN VIGUEUR, en revanche, est necessaire: sans elle la
# creation d'un projet refuserait pour une raison qui n'a rien a voir avec
# l'appartenance, et le parcours de la fondatrice serait vert — ou rouge —
# pour la mauvaise raison. Le decor pose le DOCUMENT, jamais ses valeurs.
# ---------------------------------------------------------------------
DECOR_SORTIE="$(admb -v ON_ERROR_STOP=1 2>&1 <<SQL
insert into auth.users (id) values
  ('$RACINE_ID'),('$ACTEUR_F'),('$ACTEUR_I'),('$ACTEUR_T'),('$ACTEUR_X')
on conflict do nothing;
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL
)"
if grep -q "ERROR" <<<"$DECOR_SORTIE"; then
  echo "      ECHEC: la pose du decor a ete refusee:" >&2
  grep -m3 "ERROR\|DETAIL\|LINE" <<<"$DECOR_SORTIE" | cut -c1-200 >&2
  exit 1
fi

NB_USR=$(q "select count(*) from auth.users")
NB_ORG=$(q "select count(*) from organizations")
NB_MEM=$(q "select count(*) from organization_members")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_USR" != "5" || "$NB_ORG" != "0" || "$NB_MEM" != "0"
      || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor n'est pas celui qu'on croit." >&2
  echo "             identites=$NB_USR organisations=$NB_ORG" >&2
  echo "             adhesions=$NB_MEM annexes_BE=$NB_ANX" >&2
  echo "             (organisations et adhesions doivent etre a ZERO: c'est" >&2
  echo "              tout l'objet de ce harnais.)" >&2
  exit 1
fi

# LA RACINE D'AUTORITE. Elle n'a rien a voir avec l'appartenance a une
# organisation — c'est la gouvernance NORMATIVE — mais le parcours complet de
# la fondatrice va jusqu'a un calcul, et le mode strict ne s'ouvre que par le
# quatre-yeux. On l'amorce donc ici; les habilitations, elles, sont prises par
# les routes du produit une fois l'organisation constituee.
ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine entree')" \
  >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: aucune racine amorcee." >&2
  exit 1
fi

MAGASIN="$(mktemp -d "/tmp/esc-entree-${JETON}-XXXXXX")" || {
  echo "      ECHEC: magasin d'objets non cree." >&2; exit 1; }

export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_BUILD_SHA="FICTIF-build-entree-${JETON}"
export EUROSTRUCT_STORAGE_DIR="$MAGASIN"
export EUROSTRUCT_ENTREE_RACINE="$RACINE_ID"
export EUROSTRUCT_ENTREE_ACTEUR_F="$ACTEUR_F"
export EUROSTRUCT_ENTREE_ACTEUR_I="$ACTEUR_I"
export EUROSTRUCT_ENTREE_ACTEUR_T="$ACTEUR_T"
export EUROSTRUCT_ENTREE_ACTEUR_X="$ACTEUR_X"

python3 -m pytest "$RACINE/api/tests/test_entree.py" \
        -p no:cacheprovider --no-header
CODE=$?
unset EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS EUROSTRUCT_STORAGE_DIR \
      EUROSTRUCT_ENTREE_RACINE EUROSTRUCT_ENTREE_ACTEUR_F \
      EUROSTRUCT_ENTREE_ACTEUR_I EUROSTRUCT_ENTREE_ACTEUR_T \
      EUROSTRUCT_ENTREE_ACTEUR_X

# LE CONSTAT FINAL EST FAIT ICI, HORS DU PROCESSUS DE TEST: la fondatrice
# a-t-elle REELLEMENT une organisation en base, et l'invitee une adhesion?
if [[ $CODE -eq 0 ]]; then
  NB_ORG=$(q "select count(*) from organizations")
  NB_OWN=$(q "select count(*) from organization_members
               where role = 'owner' and is_active")
  NB_INV=$(q "select count(*) from organization_invitations
               where accepted_at is not null")
  if [[ "$NB_ORG" == "0" ]]; then
    echo "      ECHEC: aucune organisation en base: l'entree n'a rien cree." >&2
    CODE=1
  elif [[ "$NB_OWN" == "0" ]]; then
    echo "      ECHEC: aucune organisation n'a de proprietaire actif." >&2
    CODE=1
  elif [[ "$NB_INV" == "0" ]]; then
    echo "      ECHEC: aucune invitation consommee: personne n'a rejoint." >&2
    CODE=1
  else
    echo "      $NB_ORG organisation(s), $NB_OWN proprietaire(s) actif(s), $NB_INV invitation(s) consommee(s)."
  fi
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Un compte tout neuf constitue son bureau,"
  echo " invite une collegue par un lien a usage unique,"
  echo " administre les roles sans jamais s'elever,"
  echo " et le dernier proprietaire actif ne disparait"
  echo " pas."
  echo "================================================="
fi
exit $CODE
