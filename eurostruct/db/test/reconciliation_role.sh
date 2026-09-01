#!/usr/bin/env bash
#
# EUROSTRUCT — LE ROLE DE RAPPROCHEMENT PEUT-IL ECRIRE ?
#
#   db/test/reconciliation_role.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS MESURE, ET POURQUOI IL EXISTE
# -------------------------------------------------
# `reconciliation.py` pose `set transaction read only` avant de lire. C'est
# reel — PostgreSQL refuse alors toute ecriture — mais c'est le PROGRAMME qui
# le demande. Cela protege contre un defaut de ce fichier-la; cela ne protege
# pas contre un autre programme qui se connecterait avec le meme compte, ni
# contre une version future du meme fichier ou la ligne aurait disparu.
#
# UN DROIT NE SE DEMANDE PAS. Il est absent, et rien dans la session ne peut le
# rendre present. Ce harnais mesure l'absence.
#
# LES NEUF CONTROLES
# --------------------
#   1. LE ROLE EST NOLOGIN. On ne s'y connecte pas: un compte LOGIN distinct,
#      fourni par l'infrastructure, s'y rattache.
#   2. IL N'A AUCUN ATTRIBUT — ni super, ni bypassrls, ni createrole, ni
#      createdb, ni replication. `bypassrls` en particulier lui ferait voir a
#      travers les politiques.
#   3. IL LIT LES LIVRABLES, et il en lit VRAIMENT — un role qui ne verrait
#      aucune ligne conclurait « tout est orphelin », ce qui serait faux et
#      dangereux.
#   4. IL NE LIT QUE LES SEPT COLONNES du rapprochement: ni le nom du fichier,
#      ni le genre, ni l'attestation, ni l'identite du validateur.
#   5. INSERT refuse.
#   6. UPDATE refuse.
#   7. DELETE refuse.
#   8. TRUNCATE refuse.
#   9. LES PRIMITIVES D'AUTORITE sont hors de portee — un outil de constat qui
#      peut appeler une primitive metier n'est plus un outil de constat.
#
# LE COMPTE DE CONNEXION EST FICTIF, cree ici et detruit a la sortie. Il ne
# porte AUCUN droit propre: tout ce qu'il peut, il le tient du role. C'est
# exactement la forme attendue en exploitation, ou l'infrastructure fournit le
# compte et ce depot fournit le role.
#
# SANS PILOTE POSTGRESQL, IL REND 4 — NON EXECUTE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: reconciliation_role.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "reconciliation_role.sh" || exit 2
harnais_verrou_prendre  "reconciliation_role.sh" || exit $?
exiger_cluster_jetable  "reconciliation_role.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)
exiger_roles_absents "reconciliation_role.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
#: LE COMPTE DE CONNEXION QUE L'INFRASTRUCTURE FOURNIRAIT. Fictif, sans aucun
#: droit propre: tout ce qu'il peut, il le tient du role auquel il se rattache.
LOG="${PREFIXE}_rc_${JETON}"
MDP="FICTIF-recon-${JETON}"
MANDAT="11111111-7777-7777-7777-777777777701:FICTIF-EMPREINTE-RECON-${JETON}"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
rec()  { PGUSER="$LOG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

NETTOYAGE_KO=0
sortie_propre() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$LOG"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "reconciliation_role.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$LOG" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

command -v psql >/dev/null 2>&1 || {
  echo "NON EXECUTE: reconciliation_role.sh — psql absent." >&2; exit 4; }

echo "    le role de rapprochement: il lit, et il ne peut rien d'autre"

CODE=0
ok()    { echo "      ok: $1"; }
rouge() { echo "      ECHEC: $1" >&2; CODE=1; }

creer_role "$MIG" "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL" "login password '$MDP' createrole"          || exit 1
creer_role "$SVC" "login password '$MDP'"                     || exit 1
creer_role "$LOG" "login password '$MDP'"                     || exit 1
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
    esc_diag_rapporter "decor / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1

# LE COMPTE DE CONNEXION SE RATTACHE AU ROLE, ET C'EST TOUT CE QU'IL RECOIT.
adm -c "grant connect on database \"$BASE\" to \"$LOG\";" >/dev/null 2>&1
adm -c "grant eurostruct_reconciliation to \"$LOG\";" >/dev/null 2>&1

# UNE LIGNE A LIRE. Sans elle, le controle 3 confondrait « ne voit rien » et
# « il n'y a rien a voir » — et c'est precisement la confusion la plus
# dangereuse pour un rapprochement.
DECOR=$(admb -v ON_ERROR_STOP=1 2>&1 <<SQL
insert into auth.users (id) values ('22222222-7777-7777-7777-77777777aaa1')
  on conflict do nothing;
insert into organizations (id, name, country)
  values ('44444444-7777-7777-7777-7777777777c1', 'FICTIF Bureau R', 'BE');
insert into projects (id, org_id, name, country, ndp_as_of, created_by)
  values ('66666666-7777-7777-7777-7777777777a1',
          '44444444-7777-7777-7777-7777777777c1', 'FICTIF Projet R', 'BE',
          '2024-01-15', '22222222-7777-7777-7777-77777777aaa1');
insert into engine_versions (id, version, released_at)
  values ('77777777-7777-7777-7777-777777777701', '0.0.0-FICTIF', now())
  on conflict do nothing;
insert into structural_models (id, org_id, project_id, name, created_by)
  values ('99999999-7777-7777-7777-777777777701',
          '44444444-7777-7777-7777-7777777777c1',
          '66666666-7777-7777-7777-7777777777a1', 'FICTIF',
          '22222222-7777-7777-7777-77777777aaa1');
insert into calculations (id, org_id, project_id, model_id, engine_version_id,
                          status, inputs_hash, requested_by)
  values ('aaaaaaaa-7777-7777-7777-777777777701',
          '44444444-7777-7777-7777-7777777777c1',
          '66666666-7777-7777-7777-7777777777a1',
          '99999999-7777-7777-7777-777777777701',
          '77777777-7777-7777-7777-777777777701',
          'succeeded', repeat('a', 64),
          '22222222-7777-7777-7777-77777777aaa1');
insert into deliverables (id, org_id, project_id, calculation_id, kind,
                          filename, media_type, storage_backend, storage_path,
                          sha256, size_bytes, engine_version, generated_by)
  values ('bbbbbbbb-7777-7777-7777-777777777701',
          '44444444-7777-7777-7777-7777777777c1',
          '66666666-7777-7777-7777-7777777777a1',
          'aaaaaaaa-7777-7777-7777-777777777701',
          'calculation_note_pdf', 'FICTIF.pdf', 'application/pdf', 'local',
          '44444444-7777-7777-7777-7777777777c1/66666666-7777-7777-7777-7777777777a1/'
            || repeat('b', 64) || '.pdf',
          repeat('b', 64), 1234, '0.0.0-FICTIF',
          '22222222-7777-7777-7777-77777777aaa1');
SQL
)
# UN AVERTISSEMENT N'EST PAS UNE ERREUR. On ne rougit que sur `ERROR`:
# traiter toute sortie comme un echec ferait tomber le harnais sur un
# `WARNING` sans consequence, et apprendrait a ignorer ses propres verdicts.
if grep -qi "^ERROR" <<<"$DECOR"; then
  echo "      ECHEC: le decor n'a pas ete pose:" >&2
  echo "$DECOR" | grep -i "^ERROR" | head -3 >&2
  exit 1
fi

# --- 1 et 2 : LE ROLE LUI-MEME -------------------------------------------
ATTRIBUTS=$(q "select rolcanlogin::text || ',' || rolsuper::text || ',' ||
                      rolbypassrls::text || ',' || rolcreaterole::text || ',' ||
                      rolcreatedb::text || ',' || rolreplication::text
                 from pg_roles where rolname = 'eurostruct_reconciliation'")
if [[ "$ATTRIBUTS" == "false,false,false,false,false,false" ]]; then
  ok "1-2. le role est NOLOGIN et sans aucun attribut"
else
  rouge "1-2. attributs du role: « $ATTRIBUTS » (login,super,bypassrls,createrole,createdb,replication)"
fi

# --- 3 : IL LIT, ET IL LIT VRAIMENT --------------------------------------
LUES=$(rec -tAc "select count(*) from deliverables" 2>&1 | tr -d ' ')
if [[ "$LUES" == "1" ]]; then
  ok "3. il lit les livrables — 1 ligne, celle du decor"
else
  rouge "3. lecture des livrables: « $LUES » au lieu de 1. Un rapprochement qui ne voit rien conclut « tout est orphelin »."
fi

# --- 4 : ET SEULEMENT LES COLONNES DU RAPPROCHEMENT ----------------------
for COLONNE in filename kind validation_id watermark media_type; do
  SORTIE=$(rec -tAc "select $COLONNE from deliverables limit 1" 2>&1)
  if grep -qi "permission denied\|droit refuse" <<<"$SORTIE"; then
    ok "4. « $COLONNE » est hors de portee"
  else
    rouge "4. « $COLONNE » est lisible: « $(cut -c1-90 <<<"$SORTIE") »"
  fi
done
for COLONNE in storage_path sha256 size_bytes org_id project_id storage_backend; do
  SORTIE=$(rec -tAc "select $COLONNE from deliverables limit 1" 2>&1)
  if grep -qi "permission denied\|droit refuse" <<<"$SORTIE"; then
    rouge "4. « $COLONNE » devrait etre lisible et ne l'est pas"
  fi
done
ok "4. les six colonnes du rapprochement sont lisibles"

# --- 5 a 8 : AUCUNE ECRITURE ---------------------------------------------
essai_refuse() {
  local nom="$1" sql="$2" sortie
  sortie=$(rec -tAc "$sql" 2>&1)
  if grep -qi "permission denied\|droit refuse\|must be owner" <<<"$sortie"; then
    ok "$nom refuse"
  else
    rouge "$nom N'A PAS ETE REFUSE: « $(cut -c1-110 <<<"$sortie") »"
  fi
}

essai_refuse "5. INSERT" \
  "insert into deliverables (id, org_id, project_id, calculation_id, kind,
     filename, media_type, storage_backend, storage_path, sha256, size_bytes,
     engine_version, generated_by)
   values (gen_random_uuid(), '44444444-7777-7777-7777-7777777777c1',
     '66666666-7777-7777-7777-7777777777a1',
     'aaaaaaaa-7777-7777-7777-777777777701', 'calculation_note_pdf',
     'FICTIF-INTRUS.pdf', 'application/pdf', 'local', 'x/' || repeat('c', 64),
     repeat('c', 64), 1, '0.0.0-FICTIF',
     '22222222-7777-7777-7777-77777777aaa1')"
essai_refuse "6. UPDATE" \
  "update deliverables set size_bytes = 0"
essai_refuse "7. DELETE" \
  "delete from deliverables"
essai_refuse "8. TRUNCATE" \
  "truncate deliverables"

# --- 9 : LES PRIMITIVES SONT HORS DE PORTEE ------------------------------
PORTEE=$(rec -tAc "select coalesce(string_agg(p.proname, ', '
                                    order by p.proname), '(aucune)')
                     from pg_proc p
                     join pg_namespace n on n.oid = p.pronamespace
                    where n.nspname = 'public'
                      and (p.proname like 'project\_%'
                           or p.proname like 'organization\_%'
                           or p.proname like 'normative\_%')
                      and has_function_privilege('eurostruct_reconciliation',
                                                 p.oid, 'EXECUTE')" 2>&1 | tr -d ' ')
if [[ "$PORTEE" == "(aucune)" ]]; then
  ok "9. aucune primitive metier n'est atteignable"
else
  rouge "9. primitives atteignables: $PORTEE"
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Le rapprochement lit les livrables et ne peut"
  echo " rien ecrire — le droit le dit, pas le programme."
  echo "================================================="
fi
exit $CODE
