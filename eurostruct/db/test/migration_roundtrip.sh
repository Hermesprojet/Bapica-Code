#!/usr/bin/env bash
#
# EUROSTRUCT — LE ROUNDTRIP DES MIGRATIONS
#
#   db/test/migration_roundtrip.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR, ET POURQUOI IL A ETE ECRIT
# ------------------------------------------------------------------
# Les harnais d'autorite appliquent deja le sceau puis les migrations sur une
# base jetable: L'ALLER est donc couvert, et bien couvert. Ce qui ne l'etait
# nulle part, c'est LE RETOUR — repasser sur les memes fichiers doit constater
# « deja appliquee » pour CHACUN, et ne rien rejouer.
#
# CE N'EST PAS UNE PRECAUTION THEORIQUE. Mesure du 26/08 sur ce meme scenario:
# 10 migrations sur 14 etaient constatees deja appliquees, et QUATRE etaient
# REJOUEES — `0011` a `0014`, qui n'appelaient pas
# `normative_migration_applied()`. Deux consequences, l'une et l'autre
# serieuses:
#
#   * tout deploiement ulterieur les rejouait. Ce ne sont pas des scripts
#     idempotents par construction: elles transferent des proprietes, posent
#     des policies, retirent des droits;
#   * la protection « on ne peut pas les appliquer hors du runner » tombait.
#     C'est la substitution de `:'esc_migration_id'` qui la porte: sans elle,
#     un `psql -f` les avale sans rien exiger.
#
# Rien, dans la suite, ne le voyait: chaque harnais part d'une base NEUVE.
#
# L'EMPREINTE DU SCHEMA EST PRISE DES DEUX COTES. Un « deja appliquee » qui
# aurait tout de meme mute quelque chose ne se verrait pas dans le decompte; il
# se voit dans l'empreinte. Elle couvre les tables (proprietaire, RLS, RLS
# forcee), les fonctions (proprietaire, SECURITY DEFINER, search_path), les
# policies et les ACL de table.
#
# LES CASTS `::text` SONT INDISPENSABLES. `relkind` et `polcmd` sont de type
# `"char"`, et `text || "char"` est AMBIGU: l'empreinte revenait vide, donc
# EGALE a elle-meme, et le controle se declarait satisfait sans rien avoir
# compare. Une empreinte vide est le pire des verdicts: elle passe toujours.
#
# La base, les roles et les objets sont crees ici et supprimes ici. Aucun
# nettoyage par motif large: on ne detruit que ce que ce script a cree.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: migration_roundtrip.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "migration_roundtrip.sh" || exit 2
harnais_verrou_prendre  "migration_roundtrip.sh" || exit $?
exiger_cluster_jetable  "migration_roundtrip.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "migration_roundtrip.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer aller retour empreinte registre-complet

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }
rouge()  { verdict "$1" ROUGE "${@:2}"; }
sur()    { verdict "$1" SUR   "${@:2}"; }
troue()  { verdict "$1" NON_PARCOURU "${@:2}"; }

MIG="${PREFIXE}_mr_${JETON}"; CTL="${PREFIXE}_cr_${JETON}"
SVC="${PREFIXE}_sr_${JETON}"; BASE="${PREFIXE}_dr_${JETON}"
MDP="FICTIF-rt-${JETON}"
# LE MANDAT D'AMORCAGE, FICTIF. Ce harnais n'amorce rien: il est declare
# uniquement pour que 0013 le constate, comme sur une base reelle.
MANDAT="00000000-0000-0000-0000-000000000000:FICTIF-EMPREINTE-ROUNDTRIP-${JETON}"

adm()  { psql -X -q -d postgres "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }

empreinte() {
  admb -tA <<'SQL'
select coalesce(md5(string_agg(l, E'\n' order by l)), '(vide)') from (
  select 'T:' || c.relname || ':' || c.relkind::text || ':' ||
         pg_get_userbyid(c.relowner) || ':' ||
         c.relrowsecurity::text || ':' || c.relforcerowsecurity::text as l
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r','v','m')
  union all
  select 'F:' || p.proname || ':' || pg_get_userbyid(p.proowner) || ':' ||
         p.prosecdef::text || ':' ||
         coalesce(array_to_string(p.proconfig, ','), '')
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public'
  union all
  select 'P:' || c.relname || ':' || pol.polname || ':' || pol.polcmd::text
    from pg_policy pol join pg_class c on c.oid = pol.polrelid
  union all
  select 'G:' || c.relname || ':' ||
         coalesce(array_to_string(c.relacl, '|'), '')
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind = 'r'
) s
SQL
}

decor_poser() {
  local sortie m etat
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
    echoue "decor: phase 0: $(grep -m1 ERROR <<<"$sortie" | cut -c1-160)"
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

# LE DEMONTAGE, COMME DANS LES AUTRES HARNAIS DE CETTE SUITE. Sans lui la base
# survit au harnais, et le suivant refuse de demarrer sur « des bases
# etrangeres a ces tests » — mesure faite, en une seule execution.
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
  harnais_postcondition_nettoyage "migration_roundtrip.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

if ! decor_poser; then
  echoue "le decor n'a pas pu etre pose: AUCUN controle n'est evalue."
  troue aller           "decor absent."
  troue retour          "decor absent."
  troue empreinte       "decor absent."
  troue registre-complet "decor absent."
  verdicts_verifier || true
  verdicts_resume "roundtrip des migrations"
  exit 1
fi

# ---------------------------------------------------------------- ALLER
echo "      -- aller: les migrations s'appliquent sur une base neuve"
FICHIERS=("$DB_DIR"/migrations/*.sql)
N=0; ALLER_OK=1; MOTIF=""
for f in "${FICHIERS[@]}"; do
  if ! esc_appliquer_migration "$f" mig; then
    ALLER_OK=0
    MOTIF="$(basename "$f"): $(grep -m1 ERROR <<<"$ESC_MIGRATION_SORTIE" | cut -c1-140)"
    break
  fi
  N=$((N + 1))
done
detail "migrations du depot: ${#FICHIERS[@]} ; appliquees: $N"
if [[ "$ALLER_OK" != "1" ]]; then
  rouge aller "une migration a ete refusee sur une base neuve."
  detail "$MOTIF"
  troue retour           "l'aller n'a pas abouti."
  troue empreinte        "l'aller n'a pas abouti."
  troue registre-complet "l'aller n'a pas abouti."
  verdicts_verifier || true
  verdicts_resume "roundtrip des migrations"
  exit 1
fi

M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -v esc_v="$M" -tAc "select normative_finalize_deployment(:'esc_v')" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
detail "activation: $ETAT"
if [[ "$ETAT" != "ACTIVE" ]]; then
  rouge aller "la base n'atteint pas ACTIVE apres les migrations ($ETAT)."
else
  sur aller "les $N migrations du depot s'appliquent et la base atteint ACTIVE."
fi

# ------------------------------------------------------- REGISTRE COMPLET
echo "      -- registre-complet: chaque migration s'y est inscrite"
INSCRITES="$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1 | tr -d ' ')"
detail "inscrites au registre: $INSCRITES ; migrations du depot: ${#FICHIERS[@]}"
if [[ "$INSCRITES" == "${#FICHIERS[@]}" ]]; then
  sur registre-complet "les ${#FICHIERS[@]} migrations sont inscrites au registre."
  detail "non-vacuite: le compte vient de la table, pas d'un litteral."
else
  rouge registre-complet "le registre ne porte que $INSCRITES des"
  detail "${#FICHIERS[@]} migrations du depot. Celles qui manquent seront"
  detail "REJOUEES au prochain deploiement, et sont applicables hors du runner."
  ABSENTES="$(admb -tAc "select coalesce(string_agg(f, ', '), '(aucune)')
    from unnest(array[$(printf "'%s'," "${FICHIERS[@]##*/}" | sed 's/,$//')]) as f
   where f not in (select migration_id from normative_migration_ledger)" 2>&1)"
  detail "absentes: $(head -c 200 <<<"$ABSENTES")"
fi

E1="$(empreinte | tr -d ' ')"
detail "empreinte apres l'aller: ${E1:0:16}"

# ---------------------------------------------------------------- RETOUR
echo "      -- retour: repasser sur les memes fichiers ne rejoue rien"
REJOUEES=0; CONSTATEES=0; REFUSEES=0; QUOI=""
for f in "${FICHIERS[@]}"; do
  esc_appliquer_migration "$f" mig >/dev/null 2>&1 || REFUSEES=$((REFUSEES + 1))
  if grep -qi "deja appliquee" <<<"$ESC_MIGRATION_SORTIE"; then
    CONSTATEES=$((CONSTATEES + 1))
  else
    REJOUEES=$((REJOUEES + 1))
    QUOI="$QUOI $(basename "$f")"
  fi
done
detail "constatees deja appliquees: $CONSTATEES ; rejouees: $REJOUEES ; refusees: $REFUSEES"
if [[ "$REJOUEES" == "0" && "$REFUSEES" == "0" \
      && "$CONSTATEES" == "${#FICHIERS[@]}" ]]; then
  sur retour "aucune migration n'est rejouee au second passage."
else
  rouge retour "$REJOUEES migration(s) rejouee(s), $REFUSEES refusee(s)."
  [[ -n "$QUOI" ]] && detail "rejouees:$QUOI"
fi

# ------------------------------------------------------------- EMPREINTE
echo "      -- empreinte: le schema n'a pas bouge entre les deux passages"
E2="$(empreinte | tr -d ' ')"
detail "apres l'aller: ${E1:0:16} ; apres le retour: ${E2:0:16}"
if [[ -z "$E1" || "$E1" == "(vide)" ]]; then
  troue empreinte "l'empreinte du schema est vide: elle serait egale a"
  detail "elle-meme quoi qu'il arrive, et ne comparerait rien."
elif [[ "$E1" == "$E2" ]]; then
  sur empreinte "tables, fonctions, policies et ACL sont identiques."
  detail "non-vacuite: l'empreinte est non vide et couvre proprietaire,"
  detail "RLS forcee, SECURITY DEFINER, search_path et ACL."
else
  rouge empreinte "le schema a change au second passage alors qu'aucune"
  detail "migration n'aurait du s'executer."
fi

# ==========================================================================
verdicts_verifier || true
verdicts_resume "roundtrip des migrations"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Le jeu de migrations fait l'aller-retour sans rien rejouer."
  exit 0
fi
exit 1
