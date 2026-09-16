#!/usr/bin/env bash
#
# EUROSTRUCT — AUTO-TEST DE LA RECETTE SUR BASE HEBERGEE
#
#   PGHOST=/var/run/postgresql PGUSER=postgres \
#   EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
#   db/test/recette_supabase_staging_selftest.sh
#
# CE QUE CE FICHIER MESURE
# -------------------------
# La recette tournera sur l'instance de quelqu'un d'autre, une fois, sous le
# regard d'une personne qui ne lira pas son code. Ses deux promesses comptent
# donc autant que son chemin nominal:
#
#   1. LE DIAGNOSTIC NE MUTE RIEN, meme quand tous les acces sont la. Un
#      instantane du catalogue — roles, bases, objets de la base visee — est
#      pris avant et apres; il doit etre identique. Idem pour un `executer`
#      sans consentement.
#
#   2. CHAQUE ETAPE REND UN RESULTAT DISTINCT. Sans jetons, les etapes 0 a 2
#      sont EXECUTEES, 3 a 5 et 7 NON EXECUTEES avec leur raison, et le code
#      de sortie est 5 (PARTIELLE) — pas 0. Avec les jetons de deux comptes
#      d'essai, les sept sont EXECUTEES et le code est 0.
#
# LA BASE VISEE EST PROVISIONNEE COMME UN EXPLOITANT LE FERAIT sur une base
# hebergee — trois roles non superutilisateurs, la base, le schema auth, les
# droits et reglages de docs/DEPLOIEMENT_PREREQUIS.md §2 — puis la recette
# fait le reste: sonde, sceau, migrations, finalisation, API.
#
# Il tourne sur le cluster LOCAL et jetable de la campagne, jamais ailleurs.
set -uo pipefail
set +x

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$(dirname "$HERE")")"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
harnais_piege_signaux 2>/dev/null || true

exiger_precontrole_local "recette_supabase_staging_selftest.sh" || exit 2
harnais_verrou_prendre "recette_supabase_staging_selftest.sh" || exit $?
exiger_cluster_jetable "recette_supabase_staging_selftest.sh" || exit 2

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend eurostruct_reconciliation)
exiger_roles_absents "recette_supabase_staging_selftest.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

for outil in node curl python3 pg_dump pg_restore; do
  command -v "$outil" >/dev/null 2>&1 || { echo "NON EXECUTE: $outil absent." >&2; exit 4; }
done
[[ -n "${EUROSTRUCT_VENV:-}" && -x "$EUROSTRUCT_VENV/bin/python3" ]] \
  && export PATH="$EUROSTRUCT_VENV/bin:$PATH"
python3 -c "import eurostruct_api, uvicorn" 2>/dev/null \
  || { echo "NON EXECUTE: eurostruct_api ou uvicorn absent de python3." >&2; exit 4; }

JETON="$(harnais_jeton)"
P="esc_rst"
MIG="${P}_mg_${JETON}"; CTL="${P}_pl_${JETON}"; SVC="${P}_ap_${JETON}"
SAV="${P}_sv_${JETON}"
BASE="${P}_db_${JETON}"; BASE_R1="${P}_r1_${JETON}"; BASE_R2="${P}_r2_${JETON}"
MDP="FICTIF-rst-${JETON}"
RACINE_ID="11111111-5555-5555-5555-5555550000${JETON:0:2}"
ACTEUR_A="22222222-5555-5555-5555-5555550000${JETON:0:2}"
ACTEUR_B="33333333-5555-5555-5555-5555550000${JETON:0:2}"
PORT_AUTH="${EUROSTRUCT_RST_PORT_AUTH:-54347}"
PORT_API="${EUROSTRUCT_RST_PORT_API:-8047}"
TMP="$(mktemp -d)"; chmod 700 "$TMP"
PID_AUTH=""
KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>/dev/null | tr -d ' '; }

nettoyer() {
  [[ -n "$PID_AUTH" ]] && kill "$PID_AUTH" 2>/dev/null
  detruire_bases_creees
  detruire_roles_crees
  harnais_postcondition_nettoyage "recette_supabase_staging_selftest.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"
  rm -rf "$TMP"
  harnais_verrou_rendre 2>/dev/null || true
}
trap nettoyer EXIT

echo "    auto-test de la recette sur base hebergee (cluster local jetable)"

# ---------------------------------------------------------------------------
# 1. CE QU'UN EXPLOITANT PROVISIONNE — et rien de plus
# ---------------------------------------------------------------------------
creer_role "$MIG" "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL" "login password '$MDP' createrole"          || exit 1
creer_role "$SVC" "login password '$MDP'"                     || exit 1
# LE ROLE DE SAUVEGARDE DU FOURNISSEUR: il lit tout et n'est soumis a aucune
# politique. C'est lui, et lui seul, qui peut rendre une sauvegarde complete.
creer_role "$SAV" "login password '$MDP' bypassrls"           || exit 1
adm -c "grant pg_read_all_data to \"$SAV\";" >/dev/null 2>&1
adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do registre_role "$r"; done
creer_base "$BASE" "owner \"$MIG\""       || exit 1
creer_base "$BASE_R1" "owner \"$MIG\""    || exit 1
creer_base "$BASE_R2" "owner \"$MIG\""    || exit 1
admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL
adm -c "alter database \"$BASE\" set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$RACINE_ID:FICTIF-MANDAT-RST-$JETON';" >/dev/null 2>&1

url() { echo "postgresql://$1:$MDP@127.0.0.1:${PGPORT:-5432}/$2?sslmode=disable"; }

# --- P. CE QUE L'EXPLOITANT A PROVISIONNE SUFFIT-IL ? En lecture seule -------
echo "    P. verifier_privileges.sh sur ce que l'exploitant a provisionne"
env -i PATH="$PATH" HOME="$HOME" \
  ESC_PLAN_URL="$(url "$CTL" "$BASE")" ESC_MIGRATOR_URL="$(url "$MIG" "$BASE")" \
  EUROSTRUCT_DATABASE_URL="$(url "$SVC" "$BASE")" \
  bash "$RACINE/deploy/verifier_privileges.sh" >"$TMP/P.out" 2>&1; rc=$?
[[ $rc -eq 0 ]] || { echoue "P: verifier_privileges.sh a rendu $rc"; cat "$TMP/P.out" >&2; }
grep -q "MANQUE" "$TMP/P.out" && echoue "P: une exigence est signalee manquante sur un provisionnement conforme"

# ---------------------------------------------------------------------------
# 2. L'EMETTEUR DE JETONS D'ESSAI
# ---------------------------------------------------------------------------
EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH" \
EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://127.0.0.1:$PORT_AUTH/auth/v1" \
EUROSTRUCT_E2E_COMPTES="a@essai.invalid:FICTIF-A:$ACTEUR_A:3600:oui,b@essai.invalid:FICTIF-B:$ACTEUR_B:3600:oui" \
  node "$RACINE/web/e2e/supabase_local.mjs" >"$TMP/auth.log" 2>&1 &
PID_AUTH=$!
for _ in $(seq 1 40); do
  curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT_AUTH/jwks" 2>/dev/null && break
  sleep 0.5
done
curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT_AUTH/jwks" 2>/dev/null \
  || { echo "      ECHEC: l'emetteur d'essai n'a pas demarre." >&2; exit 1; }
jeton_pour() {   # jeton_pour <courriel> <mdp>
  printf '{"email":"%s","password":"%s"}' "$1" "$2" > "$TMP/cx.json"
  curl -fsS -X POST "http://127.0.0.1:$PORT_AUTH/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' -d @"$TMP/cx.json" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}
JETON_A="$(jeton_pour a@essai.invalid FICTIF-A)"
JETON_B="$(jeton_pour b@essai.invalid FICTIF-B)"
[[ -n "$JETON_A" && -n "$JETON_B" ]] || { echo "      ECHEC: pas de jetons d'essai." >&2; exit 1; }

# ---------------------------------------------------------------------------
# 3. L'INSTANTANE — ce qui doit rester identique quand rien ne doit muter
# ---------------------------------------------------------------------------
instantane() {
  {
    adm -tAc "select string_agg(rolname, ',' order by rolname) from pg_roles"
    adm -tAc "select string_agg(datname, ',' order by datname) from pg_database"
    admb -tAc "select coalesce(string_agg(n.nspname||'.'||c.relname||':'||c.relkind, ',' order by 1), '')
                 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                where n.nspname not in ('pg_catalog','information_schema','pg_toast')"
    admb -tAc "select count(*) from pg_proc where pronamespace = 'public'::regnamespace"
    admb -tAc "select coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) from pg_stat_user_tables"
  } 2>/dev/null | sha256sum | cut -d' ' -f1
}

RECETTE="$HERE/recette_supabase_staging.sh"
resultat_etape() {   # resultat_etape <fichier-sortie> <n>
  grep -E "^  $2 " "$1" | head -1 | cut -c44-56 | tr -d ' '
}
env_complet() {
  echo "ESC_PLAN_URL=$(url "$CTL" "$BASE")"
  echo "ESC_MIGRATOR_URL=$(url "$MIG" "$BASE")"
  echo "EUROSTRUCT_DATABASE_URL=$(url "$SVC" "$BASE")"
  echo "EUROSTRUCT_STAGING_BACKUP_URL=$(url "$SAV" "$BASE")"
  echo "EUROSTRUCT_SUPABASE_JWKS_URL=http://127.0.0.1:$PORT_AUTH/jwks"
  echo "EUROSTRUCT_SUPABASE_ISSUER=http://127.0.0.1:$PORT_AUTH/auth/v1"
  echo "EUROSTRUCT_SUPABASE_AUDIENCE=authenticated"
  echo "EUROSTRUCT_STORAGE_BACKEND=local"
  echo "EUROSTRUCT_STORAGE_DIR=$TMP/livrables"
  echo "EUROSTRUCT_RECETTE_TLS_AUTO_HEBERGE=oui"
  echo "EUROSTRUCT_RECETTE_PORT_API=$PORT_API"
}
# LA RECETTE EST LANCEE DANS UN ENVIRONNEMENT VIDE DE TOUT PG*: elle doit
# tenir avec ses seules URL, comme sur un poste d'exploitant.
lancer() {   # lancer <mode> <fichier-sortie> [VAR=val ...]
  local mode="$1" sortie="$2"; shift 2
  env -i PATH="$PATH" HOME="$HOME" "$@" bash "$RECETTE" "$mode" >"$sortie" 2>&1
}

# --- A. SANS AUCUN ACCES: 4, et les sept lignes NON EXECUTEES ---------------
echo "    A. sans acces"
lancer diagnostic "$TMP/A.out"; rc=$?
[[ $rc -eq 4 ]] || echoue "A: code $rc (4 attendu)"
for i in 0 1 2 3 4 5 6 7; do
  [[ "$(resultat_etape "$TMP/A.out" $i)" == "NONEXECUTEE" ]] \
    || echoue "A: etape $i « $(resultat_etape "$TMP/A.out" $i) » (NON EXECUTEE attendue)"
done

# --- B. DIAGNOSTIC AVEC TOUS LES ACCES: 0, ET AUCUNE MUTATION ----------------
echo "    B. diagnostic avec tous les acces — aucune mutation"
mapfile -t ENVC < <(env_complet)
AVANT="$(instantane)"
lancer diagnostic "$TMP/B.out" "${ENVC[@]}" \
  "EUROSTRUCT_STAGING_JETON_A=$JETON_A" "EUROSTRUCT_STAGING_JETON_B=$JETON_B" \
  "EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui" \
  "EUROSTRUCT_STAGING_RESTORE_URL=$(url "$MIG" "$BASE_R1")"; rc=$?
APRES="$(instantane)"
[[ $rc -eq 0 ]] || { echoue "B: code $rc (0 attendu)"; sed -n '1,40p' "$TMP/B.out" >&2; }
[[ "$AVANT" == "$APRES" ]] || echoue "B: le DIAGNOSTIC A MUTE la base ou le cluster (instantanes differents)"
grep -q "n'a rien ecrit" "$TMP/B.out" || echoue "B: la sortie ne dit pas qu'elle n'a rien ecrit"
[[ "$(q "select count(*) from pg_namespace where nspname='auth'")" == "1" ]] || echoue "B: le schema auth a disparu"
[[ "$(q "select count(*) from pg_class where relname='normative_migration_ledger'")" == "0" ]] \
  || echoue "B: le diagnostic a applique des migrations (registre present)"

# --- C. EXECUTER SANS CONSENTEMENT: 2, ET AUCUNE MUTATION --------------------
echo "    C. executer sans consentement — refus, aucune mutation"
AVANT="$(instantane)"
lancer executer "$TMP/C.out" "${ENVC[@]}" "EUROSTRUCT_STAGING_JETON_A=$JETON_A" \
  "EUROSTRUCT_STAGING_JETON_B=$JETON_B"; rc=$?
APRES="$(instantane)"
[[ $rc -eq 2 ]] || echoue "C: code $rc (2 attendu)"
[[ "$AVANT" == "$APRES" ]] || echoue "C: un executer SANS consentement a mute"

# --- D. EXECUTER, CONSENTI, SANS JETONS: PARTIELLE (5) -----------------------
echo "    D. executer sans jetons — 0, 1, 2 et 6 executees, le reste non, code 5"
lancer executer "$TMP/D.out" "${ENVC[@]}" "EUROSTRUCT_RECETTE_CIBLE=staging" \
  "EUROSTRUCT_STAGING_RESTORE_URL=$(url "$MIG" "$BASE_R1")"; rc=$?
[[ $rc -eq 5 ]] || { echoue "D: code $rc (5 attendu)"; sed -n '1,60p' "$TMP/D.out" >&2; }
for i in 0 1 2 6; do
  [[ "$(resultat_etape "$TMP/D.out" $i)" == "EXECUTEE" ]] \
    || echoue "D: etape $i « $(resultat_etape "$TMP/D.out" $i) » (EXECUTEE attendue)"
done
for i in 3 4 5 7; do
  [[ "$(resultat_etape "$TMP/D.out" $i)" == "NONEXECUTEE" ]] \
    || echoue "D: etape $i « $(resultat_etape "$TMP/D.out" $i) » (NON EXECUTEE attendue)"
done
grep -q "jeton" "$TMP/D.out" || echoue "D: les etapes non executees ne nomment pas le jeton manquant"
[[ "$(q "select normative_activation_state()")" == "ACTIVE" ]] || echoue "D: la base n'est pas ACTIVE apres l'etape 1"

# --- L'EXPLOITANT, APRES LE DEPLOIEMENT: racine, comptes d'essai, habilitations,
#     et le referentiel des annexes que la creation d'un projet exige ----------
echo "    (exploitant) racine d'autorite, comptes d'essai, habilitations, seed NDP"
# LES PRINCIPAUX EXISTENT DANS auth.users AVANT L'AMORCAGE: `grantee_id`
# reference `auth.users(id)`, et l'amorcage etait refuse par la cle
# etrangere tant que l'ordre etait inverse (mesure ici, second run).
admb -v ON_ERROR_STOP=1 -c "insert into auth.users (id) values ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_B') on conflict do nothing" >/dev/null 2>&1
PGUSER="$CTL" PGPASSWORD="$MDP" PGHOST=127.0.0.1 psql -X -q -tA -d "$BASE" \
  -c "select bootstrap_normative_administrator('$RACINE_ID'::uuid, 'FICTIF racine (rst)', 'FICTIF amorcage rst')" >"$TMP/amorcage.log" 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
[[ "$GR" =~ ^[0-9a-f-]{36}$ ]] \
  || echoue "aucune racine amorcee: $(grep -m1 -iE 'ERROR|FATAL' "$TMP/amorcage.log" | cut -c1-160)"
EDITION_BE="$(python3 -c '
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
eds = {jeu.find(k).edition for k in jeu.keys()}
print(sorted(eds)[0] if len(eds) == 1 else "")')"
for duo in "$ACTEUR_A:A" "$ACTEUR_B:B"; do
  PGUSER="$SVC" PGPASSWORD="$MDP" PGHOST=127.0.0.1 psql -X -q -d "$BASE" >"$TMP/grant.log" 2>&1 <<SQL
select set_config('eurostruct.actor_id', '$RACINE_ID', false);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part, edition, reason, parent_grant_id)
values ('${duo%%:*}', 'FICTIF ${duo##*:} (rst)', 'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
        \$\$$EDITION_BE\$\$, 'FICTIF habilitation ${duo##*:} (rst)', '$GR');
SQL
  grep -qiE "ERROR|FATAL" "$TMP/grant.log" && echoue "habilitation ${duo##*:}: $(grep -m1 -iE 'ERROR|FATAL' "$TMP/grant.log" | cut -c1-160)"
done
# LE REFERENTIEL DES ANNEXES EST POSE PAR LA RECETTE (etape 1), pas par
# l'exploitant: on le constate, on ne le refait pas.
[[ "$(q "select count(*) from national_annexes where country_code='BE'")" != "0" ]] \
  || echoue "aucune annexe belge apres l'etape 1: la creation de projet refuserait"

# --- E. EXECUTER AVEC LES JETONS D'ESSAI: LES SEPT ETAPES, CODE 0 ------------
echo "    E. executer avec deux comptes d'essai — les sept etapes"
lancer executer "$TMP/E.out" "${ENVC[@]}" "EUROSTRUCT_RECETTE_CIBLE=staging" \
  "EUROSTRUCT_STAGING_JETON_A=$JETON_A" "EUROSTRUCT_STAGING_JETON_B=$JETON_B" \
  "EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui" \
  "EUROSTRUCT_STAGING_RESTORE_URL=$(url "$MIG" "$BASE_R2")"; rc=$?
[[ $rc -eq 0 ]] || { echoue "E: code $rc (0 attendu)"; sed -n '1,80p' "$TMP/E.out" >&2; }
for i in 0 1 2 3 4 5 6 7; do
  [[ "$(resultat_etape "$TMP/E.out" $i)" == "EXECUTEE" ]] \
    || echoue "E: etape $i « $(resultat_etape "$TMP/E.out" $i) » (EXECUTEE attendue)"
done
grep -q "COMPLETE" "$TMP/E.out" || echoue "E: pas de verdict COMPLETE"
[[ "$(q "select count(*) from normative_authority_decisions where state='CONSUMED'")" == "1" ]] \
  || echoue "E: la decision d'essai n'est pas consommee en base"
[[ "$(q "select count(*) from calculations")" -ge 1 ]] || echoue "E: aucune etude enregistree"
[[ "$(q "select count(*) from deliverables")" -ge 2 ]] || echoue "E: moins de deux livrables"

if ((KO)); then
  echo "      NON: au moins un scenario est tombe (voir ci-dessus)." >&2
  exit 1
fi
echo "    ok: diagnostic sans mutation, refus sans consentement, PARTIELLE sans jetons, COMPLETE avec deux comptes d'essai."
exit 0
