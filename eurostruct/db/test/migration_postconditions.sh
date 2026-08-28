#!/usr/bin/env bash
#
# EUROSTRUCT — LES POSTCONDITIONS DE MIGRATION SONT-ELLES ATTEINTES ?
#
#   db/test/migration_postconditions.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `0011`, `0012` et `0014` posent chacune une postcondition qui confronte le
# CATALOGUE a ce que la migration a demande. Trois questions se posent, et
# elles ne se deduisent pas l'une de l'autre:
#
#   1. sur une base correcte, la migration passe-t-elle ?
#   2. si une commande de privilege est rendue SANS EFFET, la postcondition
#      refuse-t-elle — et la migration entiere avec elle ?
#   3. si l'APPEL a la postcondition est retire, la meme base fautive
#      passe-t-elle ? Sans cette troisieme observation, la deuxieme ne dit pas
#      d'ou vient le refus.
#
# POURQUOI CE HARNAIS N'APPELLE JAMAIS L'ASSERTION LUI-MEME. Un test qui fait
# `select assert_...()` prouve que la FONCTION refuse; il ne prouve pas que le
# PRODUIT l'execute. C'est exactement la situation qui a ete mesuree avant ce
# lot: `assert_authority_surface_hardened()` existait, refusait correctement,
# et aucun chemin de migration ne l'appelait — seul un harnais le faisait.
# Ici, TOUT passe par `esc_appliquer_migration`, le chemin reel.
#
# LE PIEGE QUI JUSTIFIE TOUT CECI, MESURE CINQ FOIS DANS CE JALON:
# PostgreSQL 16 n'echoue pas sur un GRANT ou un REVOKE emis sans le droit
# requis. Il emet un WARNING et ne fait rien. `psql -v ON_ERROR_STOP=1` ne
# s'arrete pas sur un WARNING. Une migration peut donc se terminer « avec
# succes » en laissant la surface exactement dans l'etat qu'elle pretendait
# corriger.
#
# ATOMICITE. Chaque refus est suivi d'un constat: aucune ligne de registre
# pour la migration fautive, aucun objet a demi pose, et la migration INTACTE
# s'applique proprement ensuite. Une migration qui echoue en laissant une
# moitie derriere elle est pire qu'une migration qui echoue.
#
# Aucune identite reelle, aucun secret, base jetable verifiee avant ecriture.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: migration_postconditions.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "migration_postconditions.sh" || exit 2
harnais_verrou_prendre  "migration_postconditions.sh" || exit $?
exiger_cluster_jetable  "migration_postconditions.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "migration_postconditions.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  m0011-verte m0011-privilege-sans-effet m0011-appel-neutralise m0011-atomicite \
  m0012-verte m0012-privilege-sans-effet m0012-appel-neutralise m0012-atomicite \
  m0014-verte m0014-privilege-sans-effet m0014-appel-neutralise m0014-atomicite

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }
rouge()  { verdict "$1" ROUGE "${@:2}"; }
sur()    { verdict "$1" SUR   "${@:2}"; }
troue()  { verdict "$1" NON_PARCOURU "${@:2}"; }

MIG="${PREFIXE}_mp_${JETON}"; CTL="${PREFIXE}_cp_${JETON}"
SVC="${PREFIXE}_sp_${JETON}"; BASE="${PREFIXE}_dp_${JETON}"
MDP="FICTIF-mp-${JETON}"
MANDAT="00000000-0000-0000-0000-000000000000:FICTIF-EMPREINTE-POSTCOND-${JETON}"
TMP="$(mktemp -d)"

adm()  { psql -X -q -d postgres "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

NETTOYAGE_KO=0
sortie_propre() {
  local r
  rm -rf "$TMP"
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
  harnais_postcondition_nettoyage "migration_postconditions.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: les postconditions de migration sont-elles ATTEINTES ?"

# ==========================================================================
# LE DECOR — un par scenario, car chacun doit repartir d'une base neuve
# ==========================================================================
decor_poser() {
  local sortie
  creer_role "$MIG" "login password '$MDP' createrole createdb" || return 1
  creer_role "$CTL" "login password '$MDP' createrole"          || return 1
  creer_role "$SVC" "login password '$MDP'"                     || return 1
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  creer_base "$BASE" "owner \"$MIG\"" || return 1
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
  if ! sortie=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
    echoue "decor: phase 0 refusee: $(grep -m1 ERROR <<<"$sortie" | cut -c1-160)"
    return 1
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
  adm -c "alter database \"$BASE\"
            set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1
  return 0
}

decor_deposer() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  adm -c "drop database if exists \"$BASE\";" >/dev/null 2>&1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC"; do
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}

# appliquer_jusqu_a <nom-de-fichier-exclu> — applique tout ce qui precede
appliquer_jusqu_a() {
  local borne="$1" f
  for f in "$DB_DIR"/migrations/*.sql; do
    [[ "$(basename "$f")" == "$borne" ]] && return 0
    esc_appliquer_migration "$f" mig >/dev/null 2>&1 || {
      echoue "decor: $(basename "$f") a echoue avant d'atteindre $borne"
      return 1; }
  done
  return 0
}

# LE FICHIER MUTE GARDE SON NOM DE BASE. `esc_appliquer_migration` derive
# l'identifiant du registre de `basename`: un nom different ferait une AUTRE
# migration, et le controle « aucune ligne de registre » ne dirait plus rien.
copie_mutee() {  # copie_mutee <fichier> <vieux> <neuf> -> chemin de la copie
  local src="$1" vieux="$2" neuf="$3" dst="$TMP/$(basename "$1")"
  python3 - "$src" "$dst" "$vieux" "$neuf" <<'PY'
import sys
src, dst, vieux, neuf = sys.argv[1:5]
t = open(src).read()
n = t.count(vieux)
if n != 1:
    sys.stderr.write(f"MOTIF_NON_UNIQUE {n}\n")
    sys.exit(1)
open(dst, "w").write(t.replace(vieux, neuf))
PY
  [[ $? -eq 0 ]] || return 1
  printf '%s\n' "$dst"
}

# ==========================================================================
# LE SCENARIO, JOUE TROIS FOIS — 0011, 0012, 0014
# ==========================================================================
# eprouver <migration> <identifiant-attendu> <motif-privilege> <motif-appel>
#          <temoin-sql> <description-du-temoin>
#
# `temoin-sql` doit rendre « t » quand la migration a REELLEMENT pose ce
# qu'elle promet. Il sert deux fois: apres un refus il doit rendre « f »
# (rien de partiel), apres la reapplication propre il doit rendre « t ».
eprouver() {
  local fichier="$1" ident="$2" mot_priv="$3" mot_appel="$4"
  local temoin="$5" temoin_desc="$6"
  local base_nom; base_nom="$(basename "$fichier")"
  local court="${base_nom:0:4}"
  local mute mute2 sortie lignes vu

  echo "      -- $base_nom"

  # ---------------------------------------------------------------- (1) VERTE
  if ! decor_poser; then troue "m$court-verte" "decor impossible"; return; fi
  if ! appliquer_jusqu_a "$base_nom"; then
    troue "m$court-verte" "les migrations anterieures n'ont pas abouti"
    decor_deposer; return
  fi
  if esc_appliquer_migration "$fichier" mig >/dev/null 2>&1; then
    vu="$(q "$temoin")"
    if [[ "$vu" == "t" ]]; then
      sur "m$court-verte" "sur un catalogue correct, la migration passe et"
      detail "$temoin_desc est en place."
    else
      rouge "m$court-verte" "la migration passe mais $temoin_desc manque."
    fi
  else
    rouge "m$court-verte" "la migration est refusee sur une base correcte:"
    detail "$(grep -m1 -oiE 'ERROR[^|]{0,120}' <<<"$ESC_MIGRATION_SORTIE")"
  fi
  decor_deposer

  # -------------------------------------- (2) PRIVILEGE RENDU SANS EFFET
  # C'est la forme EXACTE du piege PostgreSQL: la commande est emise, elle
  # n'a aucun effet, et rien ne s'arrete. On la remplace donc par un
  # commentaire — c'est ce qu'un WARNING sans effet produit dans le catalogue.
  if ! decor_poser; then troue "m$court-privilege-sans-effet" "decor impossible"; return; fi
  if ! appliquer_jusqu_a "$base_nom"; then
    troue "m$court-privilege-sans-effet" "migrations anterieures KO"
    decor_deposer; return
  fi
  if ! mute="$(copie_mutee "$fichier" "$mot_priv" "-- commande sans effet (WARNING PostgreSQL)")"; then
    troue "m$court-privilege-sans-effet" "le motif de privilege n'est pas unique"
    detail "le scenario n'a pas pu etre pose; rien n'a ete eprouve."
    decor_deposer; return
  fi
  if esc_appliquer_migration "$mute" mig >/dev/null 2>&1; then
    rouge "m$court-privilege-sans-effet" "une commande de privilege sans effet"
    detail "a PASSE: la postcondition ne voit pas le catalogue."
    ATOMICITE_APPLICABLE=0
  else
    sortie="$ESC_MIGRATION_SORTIE"
    if grep -qF "$ident" <<<"$sortie"; then
      sur "m$court-privilege-sans-effet" "la commande sans effet est refusee,"
      detail "et le refus nomme l'invariant « $ident »."
      ATOMICITE_APPLICABLE=1
    else
      rouge "m$court-privilege-sans-effet" "refusee, mais SANS nommer"
      detail "« $ident »: un refus etranger ne prouve pas la postcondition."
      detail "$(grep -m1 -oiE 'ERROR[^|]{0,110}' <<<"$sortie")"
      ATOMICITE_APPLICABLE=0
    fi
  fi

  # ------------------------------------------------------- (2 bis) ATOMICITE
  if [[ "${ATOMICITE_APPLICABLE:-0}" -eq 1 ]]; then
    lignes="$(q "select count(*) from normative_migration_ledger
                  where migration_id = '$base_nom'")"
    vu="$(q "$temoin")"
    if [[ "$lignes" != "0" ]]; then
      rouge "m$court-atomicite" "une ligne de registre subsiste pour une"
      detail "migration refusee ($lignes ligne(s)): un redeploiement la sauterait."
    elif [[ "$vu" == "t" ]]; then
      rouge "m$court-atomicite" "$temoin_desc est en place apres un REFUS:"
      detail "la transaction n'a pas ete annulee entierement."
    else
      # LA REAPPLICATION PROPRE FAIT PARTIE DE L'ATOMICITE. Une base qu'un
      # refus laisse inutilisable n'est pas « protegee », elle est cassee.
      if esc_appliquer_migration "$fichier" mig >/dev/null 2>&1 \
         && [[ "$(q "$temoin")" == "t" ]] \
         && [[ "$(q "select count(*) from normative_migration_ledger
                      where migration_id = '$base_nom'")" == "1" ]]; then
        sur "m$court-atomicite" "apres le refus: aucune ligne de registre,"
        detail "aucun objet a demi pose, et le fichier INTACT s'applique"
        detail "proprement ensuite."
      else
        rouge "m$court-atomicite" "la migration intacte ne se reapplique pas"
        detail "apres un refus: la base reste inutilisable."
      fi
    fi
  else
    troue "m$court-atomicite" "aucun refus exploitable a examiner."
  fi
  decor_deposer

  # ------------------------------------------ (3) L'APPEL EST NEUTRALISE
  # MEME CATALOGUE FAUTIF, APPEL RETIRE. Si la migration passe alors, c'est
  # bien l'APPEL — et non un autre mecanisme — qui produisait le refus.
  if ! decor_poser; then troue "m$court-appel-neutralise" "decor impossible"; return; fi
  if ! appliquer_jusqu_a "$base_nom"; then
    troue "m$court-appel-neutralise" "migrations anterieures KO"
    decor_deposer; return
  fi
  mute2="$TMP/appel_$(basename "$fichier")"
  python3 - "$fichier" "$mute2" "$mot_priv" "$mot_appel" <<'PY'
import sys
src, dst, priv, appel = sys.argv[1:5]
t = open(src).read()
if t.count(priv) != 1 or t.count(appel) != 1:
    sys.exit(1)
t = t.replace(priv, "-- commande sans effet (WARNING PostgreSQL)")
t = t.replace(appel, "-- appel de postcondition retire par le harnais")
open(dst, "w").write(t)
PY
  if [[ $? -ne 0 ]]; then
    troue "m$court-appel-neutralise" "motifs non uniques: scenario non pose"
    decor_deposer; return
  fi
  # LE NOM DE BASE CHANGE ICI, ET C'EST VOULU: cette copie ne doit pas
  # partager l'identifiant de registre de la migration reelle.
  if esc_appliquer_migration "$mute2" mig >/dev/null 2>&1; then
    sur "m$court-appel-neutralise" "l'appel retire, le MEME catalogue fautif"
    detail "passe: c'est bien l'appel a la postcondition qui refusait, et"
    detail "non un mecanisme voisin."
  else
    rouge "m$court-appel-neutralise" "l'appel retire, la migration echoue"
    detail "quand meme: le refus mesure en (2) ne vient pas de la"
    detail "postcondition. $(grep -m1 -oiE 'ERROR[^|]{0,100}' <<<"$ESC_MIGRATION_SORTIE")"
  fi
  decor_deposer
}

# --------------------------------------------------------------------------
# 0011 — le privilege neutralise est le REVOKE qui retire `is_org_member`
# a PUBLIC. C'est l'une des six SECURITY DEFINER que la postcondition
# surveille: laissee ouverte, n'importe qui interroge l'appartenance a une
# organisation. Temoin: la fonction d'assertion elle-meme est posee.
# --------------------------------------------------------------------------
eprouver "$DB_DIR/migrations/0011_authority_hardening.sql" \
  "AUTHORITY_0011_SURFACE_NOT_HARDENED" \
  "revoke all on function public.is_org_member(uuid) from public;" \
  "select assert_authority_surface_hardened();" \
  "select (select count(*) = 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
            where n.nspname='public' and p.proname='assert_authority_surface_hardened')" \
  "assert_authority_surface_hardened()"

# --------------------------------------------------------------------------
# 0012 — le privilege neutralise est le REVOKE de PUBLIC sur la filiation.
# Temoin: la fonction de descendance existe.
# --------------------------------------------------------------------------
eprouver "$DB_DIR/migrations/0012_delegation_lineage.sql" \
  "AUTHORITY_0012_PUBLIC_EXECUTE" \
  "revoke all on function normative_grant_descendants(uuid) from public;" \
  "select assert_0012_lineage_surface();" \
  "select (select count(*) = 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
            where n.nspname='public' and p.proname='normative_grant_descendants')" \
  "normative_grant_descendants()"

# --------------------------------------------------------------------------
# 0014 — le privilege neutralise est le REVOKE de PUBLIC sur la consommation.
# Temoin: la table des decisions existe.
# --------------------------------------------------------------------------
eprouver "$DB_DIR/migrations/0014_four_eyes_decisions.sql" \
  "AUTHORITY_0014_PUBLIC_EXECUTE" \
  "revoke all on function normative_decision_consume(uuid) from public;" \
  "select assert_0014_decisions_surface();
select assert_authority_composition();" \
  "select (select count(*) = 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='public' and c.relname='normative_authority_decisions')" \
  "normative_authority_decisions"

# ==========================================================================
verdicts_verifier || true
verdicts_resume "6.3c — postconditions de migration"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Les postconditions sont ATTEINTES par le chemin produit, et elles refusent."
  exit 0
fi
exit 1
