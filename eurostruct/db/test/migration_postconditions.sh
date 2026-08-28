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
  m0014-verte m0014-privilege-sans-effet m0014-appel-neutralise m0014-atomicite \
  derive-proprietaire derive-public-execute derive-search-path \
  derive-trigger-desactive derive-policy-absente derive-policy-mauvais-role \
  derive-ecriture-directe derive-force-rls derive-revoke-sans-effet \
  derive-schema-create \
  acl-nulle-fonction-appelable acl-revoquee-effective \
  acl-explicite-sans-public acl-fonction-declencheur \
  derive-declencheur-search-path

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
-- LE MIGRATEUR RECOIT AUSSI `CREATE ... WITH GRANT OPTION`, et ce n'est pas
-- un detail de decor: c'est la forme dans laquelle le defaut de revocation
-- existait. Sans elle, ce harnais eprouverait une surface ou le REVOKE marche
-- de toute facon, et ne dirait rien du chemin reel.
grant create on schema public to "$MIG", "$CTL" with grant option;
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
  local temoin="$5" temoin_desc="$6" pt="$7"
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
      rouge "m$court-verte" "$pt. la migration passe mais $temoin_desc manque."
    fi
  else
    rouge "m$court-verte" "$pt. la migration est refusee sur une base correcte:"
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
    rouge "m$court-privilege-sans-effet" "$pt. une commande de privilege sans effet"
    detail "a PASSE: la postcondition ne voit pas le catalogue."
    ATOMICITE_APPLICABLE=0
  else
    sortie="$ESC_MIGRATION_SORTIE"
    if grep -qF "$ident" <<<"$sortie"; then
      sur "m$court-privilege-sans-effet" "la commande sans effet est refusee,"
      detail "et le refus nomme l'invariant « $ident »."
      ATOMICITE_APPLICABLE=1
    else
      rouge "m$court-privilege-sans-effet" "$pt. refusee, mais SANS nommer"
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
      rouge "m$court-atomicite" "$pt. une ligne de registre subsiste pour une"
      detail "migration refusee ($lignes ligne(s)): un redeploiement la sauterait."
    elif [[ "$vu" == "t" ]]; then
      rouge "m$court-atomicite" "$pt. $temoin_desc est en place apres un REFUS:"
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
        rouge "m$court-atomicite" "$pt. la migration intacte ne se reapplique pas"
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
    rouge "m$court-appel-neutralise" "$pt. l'appel retire, la migration echoue"
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
  "assert_authority_surface_hardened()" "Y1"

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
  "normative_grant_descendants()" "Y2"

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
  "normative_authority_decisions" "Y3"

# ==========================================================================
# LES DERIVES D'APRES-DEPLOIEMENT — une autre question, et il faut le dire
# ==========================================================================
# CE QUI PRECEDE ETABLIT QUE LA MIGRATION SE VERIFIE ELLE-MEME. Cela ne dit
# rien de ce qui arrive APRES: un declencheur desactive a la main, une policy
# supprimee, un search_path relache. La migration a deja tourne; elle ne peut
# rien voir.
#
# ICI, L'ASSERTION EST DONC APPELEE DIRECTEMENT, ET C'EST ASSUME. La question
# posee n'est plus « le produit l'execute-t-il ? » — elle a sa reponse plus
# haut — mais « detecte-t-elle la derive, et la NOMME-t-elle ? ». C'est la
# question qu'un controle de readiness pose sur une base en service.
#
# CHAQUE DERIVE EST DEFAITE ENSUITE, et le vert doit revenir. Sans ce retour,
# un refus pourrait n'etre qu'une base cassee.
if ! decor_poser; then
  for v in derive-proprietaire derive-public-execute derive-search-path \
           derive-trigger-desactive derive-policy-absente \
           derive-policy-mauvais-role derive-ecriture-directe \
           derive-force-rls derive-revoke-sans-effet; do
    troue "$v" "decor impossible"
  done
else
  DERIVE_PRETE=1
  for f in "$DB_DIR"/migrations/*.sql; do
    esc_appliquer_migration "$f" mig >/dev/null 2>&1 || {
      echoue "decor des derives: $(basename "$f") a echoue"; DERIVE_PRETE=0; break; }
  done

  # eprouver_derive <verdict> <identifiant> <assertion> <sql-derive> <sql-retour>
  eprouver_derive() {
    local v="$1" ident="$2" assertion="$3" derive="$4" retour="$5" pt="$6"
    local avant apres pendant
    if [[ "$DERIVE_PRETE" -ne 1 ]]; then
      troue "$v" "le decor des derives n'a pas ete pose"; return
    fi
    avant="$(admb -tAc "select $assertion" 2>&1)"
    if grep -qiE "ERROR|ERREUR" <<<"$avant"; then
      troue "$v" "l'assertion refuse DEJA avant la derive: rien n'est eprouve"
      detail "$(head -c 120 <<<"$avant")"
      return
    fi
    if ! admb -q -v ON_ERROR_STOP=1 -c "$derive" >/dev/null 2>&1; then
      troue "$v" "la derive n'a pas pu etre posee: scenario non joue"
      return
    fi
    pendant="$(admb -tAc "select $assertion" 2>&1)"
    admb -q -c "$retour" >/dev/null 2>&1
    apres="$(admb -tAc "select $assertion" 2>&1)"
    if ! grep -qF "$ident" <<<"$pendant"; then
      rouge "$v" "$pt. la derive n'est PAS detectee, ou pas nommee « $ident »:"
      detail "$(head -c 150 <<<"$pendant")"
    elif grep -qiE "ERROR|ERREUR" <<<"$apres"; then
      rouge "$v" "$pt. apres retour en arriere l'assertion refuse toujours:"
      detail "le refus ci-dessus ne prouve donc rien. $(head -c 110 <<<"$apres")"
    else
      sur "$v" "detectee et nommee « $ident »; le retour rend le vert."
    fi
  }

  echo "      -- les neuf derives"

  # L'ASSERTION AGREGEE, ET NON LA LOCALE DE 0012 — mesure a l'appui.
  # `assert_0012_lineage_surface()` decrit l'etat A LA FIN DE 0012, ou
  # `normative_grant_is_effective` n'est pas encore accordee au backend
  # d'autorite; sur une base COMPLETEMENT deployee elle refuse donc a juste
  # titre, et ne peut pas servir de detecteur de derive. C'est precisement le
  # role de l'agregee.
  eprouver_derive derive-proprietaire "AUTHORITY_COMPOSITION_OWNER_MISMATCH" \
    "assert_authority_composition()" \
    "alter function normative_grant_descendants(uuid) owner to \"$MIG\"" \
    "alter function normative_grant_descendants(uuid) owner to eurostruct_normative_writer" "Y4"

  eprouver_derive derive-public-execute "AUTHORITY_0014_PUBLIC_EXECUTE" \
    "assert_0014_decisions_surface()" \
    "grant execute on function normative_decision_consume(uuid) to public" \
    "revoke execute on function normative_decision_consume(uuid) from public" "Y5"

  eprouver_derive derive-search-path "AUTHORITY_0014_SEARCH_PATH_UNPINNED" \
    "assert_0014_decisions_surface()" \
    "alter function normative_decision_propose(text, text, uuid, country_code,
       text, text, text, normative_permission, text) reset search_path" \
    "alter function normative_decision_propose(text, text, uuid, country_code,
       text, text, text, normative_permission, text) set search_path = public, pg_temp" "Y6"

  eprouver_derive derive-trigger-desactive "AUTHORITY_0014_TRIGGER_NOT_ENABLED" \
    "assert_0014_decisions_surface()" \
    "alter table normative_authority_decisions
       disable trigger normative_decisions_are_not_deletable" \
    "alter table normative_authority_decisions
       enable trigger normative_decisions_are_not_deletable" "Y7"

  eprouver_derive derive-policy-absente "AUTHORITY_0014_POLICY_MISMATCH" \
    "assert_0014_decisions_surface()" \
    "drop policy decisions_governance_read on normative_authority_decisions" \
    "create policy decisions_governance_read on normative_authority_decisions
       for select to normative_governance using (true)" "Y8"

  # LE MAUVAIS ROLE DANS UNE POLICY EST LE PIRE DES TROIS: la policy EXISTE,
  # elle est permissive, elle porte le bon nom et la bonne commande. Seul le
  # role change — et sous FORCE RLS, celui qui n'est plus nomme lit ZERO LIGNE
  # au lieu de recevoir une erreur.
  eprouver_derive derive-policy-mauvais-role "AUTHORITY_0014_POLICY_MISMATCH" \
    "assert_0014_decisions_surface()" \
    "drop policy decisions_governance_read on normative_authority_decisions;
     create policy decisions_governance_read on normative_authority_decisions
       for select to normative_backend using (true)" \
    "drop policy decisions_governance_read on normative_authority_decisions;
     create policy decisions_governance_read on normative_authority_decisions
       for select to normative_governance using (true)" "Y9"

  eprouver_derive derive-ecriture-directe "AUTHORITY_0014_DIRECT_WRITE_GRANTED" \
    "assert_0014_decisions_surface()" \
    "grant insert on normative_authority_decisions to normative_governance" \
    "revoke insert on normative_authority_decisions from normative_governance" "Y10"

  eprouver_derive derive-force-rls "AUTHORITY_0014_FORCE_RLS_DISABLED" \
    "assert_0014_decisions_surface()" \
    "alter table normative_authority_decisions no force row level security" \
    "alter table normative_authority_decisions force row level security" "Y11"

  # LE PRIVILEGE QUI A REELLEMENT TRAINE. Ce n'est pas une derive imaginee:
  # jusqu'a ce lot, `eurostruct_normative_writer` — proprietaire de toutes les
  # tables d'autorite — conservait CREATE sur `public` pour toute la vie de la
  # base, parce qu'un REVOKE emis par un non-donneur ne fait rien et ne le dit
  # pas. On le repose ici a la main, et l'assertion agregee doit le voir.
  eprouver_derive derive-schema-create \
    "AUTHORITY_COMPOSITION_SCHEMA_CREATE_RETAINED" \
    "assert_authority_composition()" \
    "grant create on schema public to eurostruct_normative_writer" \
    "revoke create on schema public from eurostruct_normative_writer" "Y13"

  # ========================================================================
  # LA SEMANTIQUE DE L'ACL `NULL`, MESUREE PAR CATEGORIE D'OBJET
  # ========================================================================
  # UNE ACL ABSENTE N'EST PAS UNE ABSENCE DE PRIVILEGE, et confondre les deux
  # est l'erreur la plus facile a commettre ici — parce qu'elle est SANS
  # CONSEQUENCE pour trois categories sur six.
  #
  # Mesure sur PostgreSQL 16 (sonde dediee, appels reels sous un role
  # ordinaire):
  #
  #   acldefault('f', owner) = {=X/owner, owner=X/owner}   <- `=X` EST PUBLIC
  #   fonction ordinaire, proacl NULL  -> select f() rend 1
  #   fonction SECURITY DEFINER, NULL  -> select f() rend 2, sous l'owner
  #   fonction trigger, NULL           -> privilege PRESENT, invocation
  #                                       refusee (SQLSTATE 0A000)
  #   table    (r) NULL -> {owner=arwdDxt/owner}   PUBLIC: rien
  #   sequence (S) NULL -> {owner=U/owner}         PUBLIC: rien
  #   schema   (n) NULL -> {owner=UC/owner}        PUBLIC: rien
  #
  # Les quatre controles ci-dessous fixent cette semantique dans la suite,
  # pour qu'un changement de version ou de convention la fasse rougir plutot
  # que de la faire glisser.
  echo "      -- la semantique de l'ACL NULL, par categorie"

  # 1. FONCTION PRIVILEGIEE CREEE SANS `REVOKE`: proacl NULL, PUBLIC execute
  #    REELLEMENT, et la postcondition doit rougir.
  ACL_N_AVANT="$(q "select coalesce(proacl::text,'NULL') from pg_proc p
                      join pg_namespace n on n.oid=p.pronamespace
                     where n.nspname='public' and p.proname='normative_decision_consume'")"
  admb -q -c "alter function normative_decision_consume(uuid) owner to eurostruct_normative_writer;
              revoke all on function normative_decision_consume(uuid) from public;
              grant execute on function normative_decision_consume(uuid)
                to eurostruct_normative_writer, eurostruct_authority_backend;" \
    >/dev/null 2>&1
  # On REMET l'etat « jamais revoque » en supprimant l'ACL: c'est exactement
  # ce que produit un CREATE FUNCTION sans REVOKE.
  admb -q -c "update pg_proc set proacl = null
               where proname = 'normative_decision_consume'
                 and pronamespace = 'public'::regnamespace" >/dev/null 2>&1
  ACL_N="$(q "select coalesce(proacl::text,'NULL') from pg_proc p
                join pg_namespace n on n.oid=p.pronamespace
               where n.nspname='public' and p.proname='normative_decision_consume'")"
  ACL_N_PUB="$(q "select has_function_privilege('public','normative_decision_consume(uuid)','EXECUTE')::text")"
  ACL_N_VU="$(admb -tAc "select assert_0014_decisions_surface()" 2>&1)"
  admb -q -c "revoke all on function normative_decision_consume(uuid) from public;
              grant execute on function normative_decision_consume(uuid)
                to eurostruct_normative_writer, eurostruct_authority_backend;" \
    >/dev/null 2>&1
  ACL_N_APRES="$(admb -tAc "select assert_0014_decisions_surface()" 2>&1)"
  detail "proacl remis a NULL: « $ACL_N » ; PUBLIC EXECUTE effectif: $ACL_N_PUB"
  detail "refus: $(head -c 90 <<<"$ACL_N_VU" | tr '\n' ' ')"
  if [[ "$ACL_N" != "NULL" ]]; then
    troue acl-nulle-fonction-appelable "l'ACL n'a pas pu etre remise a NULL:"
    detail "le scenario n'a pas ete pose (vu « $ACL_N »)."
  elif [[ "$ACL_N_PUB" != "true" ]]; then
    rouge acl-nulle-fonction-appelable "AC1. une ACL NULL ne donne PAS EXECUTE"
    detail "a PUBLIC sur ce serveur: la premisse des assertions est fausse,"
    detail "et il faut refaire la mesure avant de conclure quoi que ce soit."
  elif ! grep -q "AUTHORITY_0014_PUBLIC_EXECUTE" <<<"$ACL_N_VU"; then
    rouge acl-nulle-fonction-appelable "AC1. PUBLIC execute reellement, et la"
    detail "postcondition ne le voit pas: $(head -c 120 <<<"$ACL_N_VU")"
  elif grep -qiE "ERROR|ERREUR" <<<"$ACL_N_APRES"; then
    rouge acl-nulle-fonction-appelable "AC1. apres restauration de l'ACL, la"
    detail "postcondition refuse toujours: $(head -c 100 <<<"$ACL_N_APRES")"
  else
    sur acl-nulle-fonction-appelable "une ACL NULL laisse PUBLIC EXECUTE, la"
    detail "postcondition le voit, et la restauration rend le vert."
  fi

  # 2. `REVOKE EXECUTE FROM PUBLIC` REELLEMENT APPLIQUE: privilege effectif
  #    absent, postcondition verte. C'est le pendant positif du precedent:
  #    sans lui, une assertion qui refuse TOUT serait aussi « verte » en 1.
  ACL_R_PUB="$(q "select has_function_privilege('public','normative_decision_consume(uuid)','EXECUTE')::text")"
  ACL_R_ACL="$(q "select coalesce(proacl::text,'NULL') from pg_proc p
                    join pg_namespace n on n.oid=p.pronamespace
                   where n.nspname='public' and p.proname='normative_decision_consume'")"
  ACL_R_VU="$(admb -tAc "select assert_0014_decisions_surface()" 2>&1)"
  detail "apres REVOKE: proacl « $(head -c 60 <<<"$ACL_R_ACL") »"
  detail "PUBLIC EXECUTE effectif: $ACL_R_PUB"
  if [[ "$ACL_R_ACL" == "NULL" ]]; then
    troue acl-revoquee-effective "l'ACL est restee NULL: le REVOKE n'a pas ete"
    detail "applique, et le scenario n'eprouve rien."
  elif [[ "$ACL_R_PUB" != "false" ]]; then
    rouge acl-revoquee-effective "AC2. PUBLIC conserve EXECUTE apres un REVOKE"
    detail "reellement applique: $ACL_R_ACL"
  elif grep -qiE "ERROR|ERREUR" <<<"$ACL_R_VU"; then
    rouge acl-revoquee-effective "AC2. la postcondition refuse alors que le"
    detail "privilege effectif est absent: $(head -c 110 <<<"$ACL_R_VU")"
  else
    sur acl-revoquee-effective "un REVOKE applique retire le privilege EFFECTIF,"
    detail "l'ACL devient explicite, et la postcondition passe."
  fi

  # 3. ACL EXPLICITE SANS `PUBLIC`: comportement mesure, et AUCUNE exception
  #    liee a `array[]::aclitem[]`. C'est le piege qui avait fait lever
  #    « ACL arrays must be one-dimensional » en posant un coalesce defensif.
  ACL_V_EXPL="$(q "select coalesce(array_length(proacl,1)::text,'0') from pg_proc p
                     join pg_namespace n on n.oid=p.pronamespace
                    where n.nspname='public' and p.proname='normative_decision_consume'")"
  ACL_V_NUL="$(admb -tAc "select count(*) from aclexplode(null::aclitem[])" 2>&1 | tr -d ' ')"
  ACL_V_VIDE="$(admb -tAc "select count(*) from aclexplode(array[]::aclitem[])" 2>&1)"
  ACL_V_VU="$(admb -tAc "select assert_authority_composition()" 2>&1)"
  detail "entrees d'ACL explicites: $ACL_V_EXPL ; aclexplode(NULL) rend: $ACL_V_NUL ligne(s)"
  detail "aclexplode(array vide): $(head -c 60 <<<"$ACL_V_VIDE" | tr '\n' ' ')"
  if [[ "$ACL_V_NUL" != "0" ]]; then
    rouge acl-explicite-sans-public "AC3. aclexplode(NULL) ne rend pas zero"
    detail "ligne ($ACL_V_NUL): la lecture des ACL repose sur une premisse fausse."
  elif ! grep -qi "one-dimensional" <<<"$ACL_V_VIDE"; then
    troue acl-explicite-sans-public "aclexplode(array vide) n'a pas leve"
    detail "« one-dimensional »: le piege mesure n'existe pas ici, et le"
    detail "controle n'etablit donc pas ce qu'il annonce."
  elif grep -qiE "ERROR|ERREUR" <<<"$ACL_V_VU"; then
    rouge acl-explicite-sans-public "AC3. l'agregee refuse sur une ACL explicite"
    detail "sans PUBLIC: $(head -c 110 <<<"$ACL_V_VU")"
  else
    sur acl-explicite-sans-public "une ACL explicite sans PUBLIC passe, et les"
    detail "deux formes limites sont mesurees: aclexplode(NULL) rend zero"
    detail "ligne, aclexplode(array vide) LEVE. Le coalesce « defensif » vers"
    detail "un tableau vide etait donc la panne, pas la protection."
  fi

  # 4. FONCTION DECLENCHEUR: l'invocation directe est refusee par PostgreSQL,
  #    mais owner, SECURITY DEFINER et search_path restent verifies. Ne pas
  #    confondre « on ne peut pas l'appeler » et « elle est inoffensive »:
  #    elle s'execute a chaque ecriture, avec le search_path de l'ecrivain.
  TRG_PUB="$(q "select has_function_privilege('public','forbid_decision_delete()','EXECUTE')::text")"
  TRG_APPEL="$(admb -tAc "select forbid_decision_delete()" 2>&1 | head -1)"
  TRG_OWNER="$(q "select pg_get_userbyid(proowner) from pg_proc p
                    join pg_namespace n on n.oid=p.pronamespace
                   where n.nspname='public' and p.proname='forbid_decision_delete'")"
  TRG_CFG="$(q "select coalesce(array_to_string(proconfig,','),'(aucun)') from pg_proc p
                  join pg_namespace n on n.oid=p.pronamespace
                 where n.nspname='public' and p.proname='forbid_decision_delete'")"
  detail "PUBLIC EXECUTE sur la fonction declencheur: $TRG_PUB"
  detail "appel direct: $(head -c 70 <<<"$TRG_APPEL" | tr '\n' ' ')"
  detail "owner: $TRG_OWNER ; proconfig: $TRG_CFG"
  if ! grep -qi "can only be called as triggers" <<<"$TRG_APPEL"; then
    rouge acl-fonction-declencheur "AC4. l'invocation directe n'est PAS refusee"
    detail "par PostgreSQL: $(head -c 110 <<<"$TRG_APPEL")"
  elif [[ "$TRG_OWNER" != "eurostruct_normative_writer" ]]; then
    rouge acl-fonction-declencheur "AC4. la fonction declencheur appartient a"
    detail "« $TRG_OWNER »: l'impossibilite de l'appeler ne la rend pas"
    detail "inoffensive — elle s'execute a chaque ecriture."
  elif [[ "$TRG_CFG" != *search_path* ]]; then
    rouge acl-fonction-declencheur "AC4. la fonction declencheur n'a pas de"
    detail "search_path fixe: elle herite de celui de l'ecrivain."
  else
    sur acl-fonction-declencheur "l'invocation directe est refusee (0A000), et"
    detail "owner et search_path sont NEANMOINS verifies."
    detail "PUBLIC EXECUTE vaut ici $TRG_PUB parce que l'ACL est EXPLICITE."
    detail "Sur une fonction declencheur a ACL NULL il vaudrait « true » —"
    detail "mesure faite — sans etre pour autant une capacite: l'agregee"
    detail "l'exempte donc du controle PUBLIC, et d'AUCUN autre."
  fi

  # LA COUVERTURE DE L'AGREGEE SUR LES FONCTIONS DECLENCHEUR.
  #
  # Le controle precedent interroge la fonction declencheur DIRECTEMENT. Il
  # etablit donc son etat, et rien sur ce que l'assertion en fait — mesure a
  # l'appui: exclure les declencheurs du balayage de l'agregee a SURVECU a la
  # mutation, parce qu'aucun controle ne passait par elle.
  #
  # Une fonction declencheur ne s'appelle pas, mais elle S'EXECUTE a chaque
  # ecriture, avec le search_path de l'ecrivain. Relacher le sien est donc une
  # ouverture reelle, et c'est l'agregee qui doit la nommer.
  eprouver_derive derive-declencheur-search-path \
    "AUTHORITY_COMPOSITION_SEARCH_PATH_UNPINNED" \
    "assert_authority_composition()" \
    "alter function forbid_decision_delete() reset search_path" \
    "alter function forbid_decision_delete() set search_path = public, pg_temp" \
    "AC5"

  # ------------------------------------------------------------------------
  # LE PIEGE D'ORIGINE, JOUE POUR DE VRAI: un REVOKE emis par un role qui n'a
  # pas le droit de le faire. PostgreSQL emet un WARNING, ne fait RIEN, et
  # rend le code 0. C'est ce silence qui a rendu toutes les postconditions
  # ci-dessus necessaires; il est ici constate, pas suppose.
  echo "      -- derive-revoke-sans-effet: le WARNING qui ne fait rien"
  if [[ "$DERIVE_PRETE" -ne 1 ]]; then
    troue derive-revoke-sans-effet "decor des derives non pose"
  else
    admb -q -c "grant execute on function normative_decision_consume(uuid) to public" \
      >/dev/null 2>&1
    AV="$(q "select count(*) from aclexplode((select proacl from pg_proc p
              join pg_namespace n on n.oid=p.pronamespace
              where n.nspname='public' and p.proname='normative_decision_consume')) a
             where a.grantee = 0 and a.privilege_type='EXECUTE'")"
    # Le service n'est NI proprietaire NI porteur du droit: son REVOKE ne peut
    # rien faire — et PostgreSQL ne le lui dira pas autrement que par un
    # WARNING.
    SORTIE_RV="$(PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -v ON_ERROR_STOP=1 \
      -d "$BASE" -c "revoke execute on function normative_decision_consume(uuid) from public" 2>&1)"
    CODE_RV=$?
    AP="$(q "select count(*) from aclexplode((select proacl from pg_proc p
              join pg_namespace n on n.oid=p.pronamespace
              where n.nspname='public' and p.proname='normative_decision_consume')) a
             where a.grantee = 0 and a.privilege_type='EXECUTE'")"
    VU="$(admb -tAc "select assert_0014_decisions_surface()" 2>&1)"
    admb -q -c "revoke execute on function normative_decision_consume(uuid) from public" \
      >/dev/null 2>&1
    detail "PUBLIC avant le REVOKE: $AV ; apres: $AP ; code psql: $CODE_RV"
    detail "$(head -c 120 <<<"$SORTIE_RV" | tr '\n' ' ')"
    if [[ "$AV" != "1" ]]; then
      troue derive-revoke-sans-effet "PUBLIC n'a pas recu le droit: scenario non pose"
    elif [[ "$AP" != "1" ]]; then
      rouge derive-revoke-sans-effet "Y12. le REVOKE d'un non-ayant-droit a PRIS:"
      detail "le piege n'existe pas sur ce cluster, et les postconditions"
      detail "reposent sur une premisse fausse."
    elif [[ "$CODE_RV" -ne 0 ]]; then
      troue derive-revoke-sans-effet "psql a rendu $CODE_RV: ce n'est pas le"
      detail "silence attendu, le scenario mesure autre chose."
    elif grep -qF "AUTHORITY_0014_PUBLIC_EXECUTE" <<<"$VU"; then
      sur derive-revoke-sans-effet "le REVOKE d'un non-ayant-droit ne fait RIEN,"
      detail "psql rend 0, et seule la postcondition voit que PUBLIC execute"
      detail "encore. C'est tout le motif de ce lot, mesure sur pieces."
    else
      rouge derive-revoke-sans-effet "Y12. la postcondition ne voit pas le PUBLIC"
      detail "restant: $(head -c 120 <<<"$VU")"
    fi
  fi
  decor_deposer
fi

# ==========================================================================
verdicts_verifier || true
verdicts_resume "6.3c — postconditions de migration"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Les postconditions sont ATTEINTES par le chemin produit, et elles refusent."
  exit 0
fi
exit 1
