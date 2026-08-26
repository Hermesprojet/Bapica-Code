#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3c: LA SURFACE SQL DE L'AUTORITE, MESUREE
#
#   db/test/authority_sql_hardening.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `authority_root_of_trust.sh` demande « l'identite metier est-elle
# authentifiee ? ». Celui-ci pose la question d'a cote, qui ne depend d'aucune
# identite: LA SURFACE SQL EST-ELLE FERMEE ?
#
# Une primitive d'autorite parfaitement ecrite ne protege rien si:
#   * PUBLIC peut l'executer — et `EXECUTE` est accorde a PUBLIC PAR DEFAUT;
#   * elle appartient au MIGRATEUR, qui peut la reecrire sans avoir besoin
#     d'`EXECUTE`: le proprietaire d'une fonction n'a pas a en demander le
#     droit d'usage pour en changer le corps;
#   * son `search_path` est celui de l'appelant, qui peut alors faire resoudre
#     un nom vers un schema qu'il controle;
#   * un role applicatif peut l'atteindre par `SET ROLE`, par appartenance
#     directe ou par heritage transitif;
#   * le proprietaire d'une table echappe a sa propre RLS faute de
#     `FORCE ROW LEVEL SECURITY`;
#   * un role porte `BYPASSRLS`.
#
# CE QUI A ETE MESURE AVANT CORRECTION (6.3c, sur d04abf0)
# ---------------------------------------------------------
#   * SIX fonctions du sous-systeme normatif appartenaient au MIGRATEUR:
#     resolve_normative_authorisation, normative_grant_is_active,
#     normative_authorisation_snapshot, assert_digest_integrity,
#     reserve_normative_audit_namespace, forbid_normative_audit_mutation.
#     Les deux premieres decident quelle habilitation couvre une portee et si
#     un pouvoir a ete retire.
#   * SIX fonctions SECURITY DEFINER n'avaient JAMAIS ete retirees a PUBLIC:
#     is_org_member, has_org_role, can_write, check_validator_is_authorised,
#     open_retention_period, log_deliverable_transition.
#
# LA COMPTABILITE EST CELLE DE `lib_harnais.sh`: chaque controle est declare
# d'avance, rend UN statut, et l'egalite est verifiee. Un harnais dont le total
# ne s'additionne pas n'atteste rien.
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

PREFIXE="${1:?usage: authority_sql_hardening.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_sql_hardening.sh" || exit 2
harnais_verrou_prendre  "authority_sql_hardening.sh" || exit $?
exiger_cluster_jetable  "authority_sql_hardening.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "authority_sql_hardening.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  public-execute definer-public proprietaires search-path \
  execute-direct insert update delete \
  appartenances set-role bypassrls proprietaire-rls force-rls \
  controle-de-derive \
  auto-enrolement-guc auto-enrolement-role migrateur-non-membre \
  appartenance-declaree

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }
rouge() { verdict "$1" ROUGE "${@:2}"; }
sur()   { verdict "$1" SUR   "${@:2}"; }
troue() { verdict "$1" NON_PARCOURU "${@:2}"; }

adm()  { psql -X -q -d postgres "$@"; }
MIG=""; CTL=""; SVC=""; ORD=""; BASE=""; MDP=""
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
svc()  { PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
# LE ROLE APPLICATIF ORDINAIRE — ce dont dispose un attaquant qui tient une
# connexion applicative, et rien de plus.
ord()  { PGUSER="$ORD" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

# --------------------------------------------------------------------------
# LE DECOR — meme forme que les autres harnais d'autorite, mene jusqu'a ACTIVE
# --------------------------------------------------------------------------
decor_poser() {
  local f sortie m etat
  MIG="${PREFIXE}_mh_${JETON}"; CTL="${PREFIXE}_ch_${JETON}"
  SVC="${PREFIXE}_sh_${JETON}"; BASE="${PREFIXE}_dh_${JETON}"
  ORD="${PREFIXE}_oh_${JETON}"
  # LE MANDAT D'AMORCAGE, FICTIF. Forme « <principal>:<empreinte> ». Il tient
  # lieu, pour le test, de la decision prise hors du systeme; aucun document
  # reel n'existe et aucun n'est invente — l'empreinte est litteralement
  # marquee FICTIF.
  MANDAT="00000000-0000-0000-0000-000000000000:FICTIF-EMPREINTE-DE-MANDAT-${JETON}"
  MDP="FICTIF-hd-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" || return 1
  creer_role "$CTL" "login password '$MDP' createrole"          || return 1
  creer_role "$SVC" "login password '$MDP'"                     || return 1
  creer_role "$ORD" "login password '$MDP'" \
    || { echoue "decor: creation du role applicatif ordinaire"; return 1; }
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
  # LES DEUX DECLARATIONS DE 6.3c, posees AVANT la phase 1: c'est 0013 qui les
  # CONSTATE et les fige pendant la migration. Declarees apres, elles seraient
  # lues par personne et tout le sous-systeme d'autorite resterait ferme.
  adm -c "alter database \"$BASE\"
            set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\"
            set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1

  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      echoue "decor: phase 1 refusee sur $(basename "$f"):"
      grep -m1 ERROR <<<"$ESC_MIGRATION_SORTIE" | cut -c1-200 \
        | sed 's/^/              /' >&2
      return 1
    fi
  done
  m=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
  sortie=$(ctl -tAc "select normative_finalize_deployment('$m')" 2>&1)
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "ACTIVE" ]]; then
    echoue "decor: finalisation -> $etat"
    grep -m1 -iE 'ERROR|ERREUR' <<<"$sortie" | cut -c1-200 \
      | sed 's/^/              /' >&2
    return 1
  fi
  # LE BACKEND AUTHENTIFIE recoit le role d'EXECUTION privilegie; le role
  # ORDINAIRE ne recoit que `normative_backend`, qui depuis 0013 n'a plus
  # INSERT sur les tables d'autorite. C'est la separation que 6.3c pose.
  # PAR LE PLAN DE CONTROLE, qui detient l'ADMIN depuis que la phase 0 cree
  # le role. En superutilisateur, on masquerait le fait qu'il en est capable —
  # et c'est precisement ce que le controle « migrateur-non-membre » oppose.
  ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$ORD\";" >/dev/null 2>&1
  return 0
}

NETTOYAGE_KO=0
sortie_propre() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "authority_sql_hardening.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: la surface SQL de l'autorite est-elle fermee ?"
if ! decor_poser; then
  echoue "le decor n'a pas pu etre pose: AUCUN controle n'est evalue."
  exit 1
fi

# Les primitives d'autorite, et les six SECURITY DEFINER du multi-tenant.
PRIMITIVES="'bootstrap_normative_administrator','consume_normative_authorisation',
            'resolve_normative_authorisation','normative_grant_is_active',
            'normative_authorisation_snapshot','assert_digest_integrity',
            'reserve_normative_audit_namespace','forbid_normative_audit_mutation',
            'log_normative_event','check_normative_grant',
            'check_normative_grant_revocation','check_normative_confirmation',
            'check_normative_confirmation_revocation'"
DEFINERS="'is_org_member','has_org_role','can_write',
          'check_validator_is_authorised','open_retention_period',
          'log_deliverable_transition'"
AUTORITES="'eurostruct_normative_writer','eurostruct_normative_bootstrap',
           'eurostruct_normative_activator'"

# ==========================================================================
# 1. PUBLIC — le droit accorde par defaut, et jamais retire
# ==========================================================================
echo "      -- public-execute: PUBLIC peut-il executer une primitive d'autorite ?"
N="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname in ($PRIMITIVES)
          and has_function_privilege('public', p.oid, 'EXECUTE')")"
TOT="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
          where n.nspname = 'public' and p.proname in ($PRIMITIVES)")"
detail "primitives d'autorite presentes: $TOT ; ouvertes a PUBLIC: $N"
if [[ "$TOT" == "0" ]]; then
  troue public-execute "aucune primitive trouvee: le controle ne porte sur rien."
elif [[ "$N" != "0" ]]; then
  rouge public-execute "$N primitive(s) d'autorite executable(s) par PUBLIC."
  admb -tA -F' | ' -c "select p.proname from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname in ($PRIMITIVES)
       and has_function_privilege('public', p.oid, 'EXECUTE')
     order by 1" 2>&1 | sed 's/^/                  /'
else
  sur public-execute "aucune des $TOT primitives d'autorite n'est ouverte a PUBLIC."
fi

# ==========================================================================
# 2. LES SECURITY DEFINER DU MULTI-TENANT
# ==========================================================================
echo "      -- definer-public: SECURITY DEFINER encore ouvertes a PUBLIC ?"
N="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.prosecdef and p.proname in ($DEFINERS)
          and has_function_privilege('public', p.oid, 'EXECUTE')")"
TOT="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
          where n.nspname = 'public' and p.prosecdef and p.proname in ($DEFINERS)")"
detail "SECURITY DEFINER multi-tenant: $TOT ; ouvertes a PUBLIC: $N"
if [[ "$TOT" == "0" ]]; then
  troue definer-public "aucune de ces fonctions n'existe: controle vide."
elif [[ "$N" != "0" ]]; then
  rouge definer-public "$N fonction(s) SECURITY DEFINER executable(s) par PUBLIC:"
  admb -tA -c "select p.proname from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.prosecdef and p.proname in ($DEFINERS)
       and has_function_privilege('public', p.oid, 'EXECUTE')
     order by 1" 2>&1 | sed 's/^/                  /'
else
  sur definer-public "les $TOT SECURITY DEFINER du multi-tenant sont fermees a PUBLIC."
fi

# ==========================================================================
# 3. PROPRIETAIRES — le migrateur detient-il du code privilegie ?
# ==========================================================================
# LE PROPRIETAIRE N'A PAS BESOIN D'`EXECUTE` POUR REECRIRE UNE FONCTION. Une
# ACL parfaite ne dit donc rien de lui, et c'est exactement ce que ce controle
# mesure: qui peut changer le corps de ce qui decide de l'autorite.
echo "      -- proprietaires: une primitive appartient-elle a un non-autorite ?"
TOT_P="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname in ($PRIMITIVES)")"
MAUVAIS="$(admb -tA -F'=' -c "select p.proname, pg_get_userbyid(p.proowner)
     from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ($PRIMITIVES)
      and pg_get_userbyid(p.proowner) not in ($AUTORITES)
    order by 1" 2>&1)"
if [[ -z "${MAUVAIS// /}" ]]; then
  sur proprietaires "toutes les primitives appartiennent a un role d'autorite."
  detail "non-vacuite: $TOT_P primitives examinees."
else
  rouge proprietaires "des primitives appartiennent a un role NON-AUTORITE:"
  sed 's/^/                  /' <<<"$MAUVAIS"
  detail "leur proprietaire peut les reecrire par CREATE OR REPLACE sans"
  detail "detenir le moindre EXECUTE."
fi

# ==========================================================================
# 4. SEARCH_PATH FIXE
# ==========================================================================
echo "      -- search-path: une primitive herite-t-elle du search_path appelant ?"
SANS="$(admb -tA -c "select p.proname from pg_proc p
     join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ($PRIMITIVES)
      and (p.proconfig is null
           or not exists (select 1 from unnest(p.proconfig) c
                           where c like 'search\\_path=%'))
    order by 1" 2>&1)"
if [[ -z "${SANS// /}" ]]; then
  sur search-path "toutes les primitives ont un search_path fixe."
else
  rouge search-path "des primitives heritent du search_path de l'appelant:"
  sed 's/^/                  /' <<<"$SANS"
fi

# ==========================================================================
# 5. EXECUTE DIRECT PAR LE ROLE APPLICATIF
# ==========================================================================
echo "      -- execute-direct: le role de service atteint-il une primitive ?"
N="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname in ($PRIMITIVES)
          and has_function_privilege('$SVC', p.oid, 'EXECUTE')")"
NB="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
         where n.nspname = 'public' and p.proname in ($PRIMITIVES)
           and has_function_privilege('normative_backend', p.oid, 'EXECUTE')")"
detail "atteintes par « $SVC »: $N ; par normative_backend: $NB"
# `bootstrap_normative_administrator` est accordee a `eurostruct_deployment`
# A DESSEIN (6.3b5): c'est le chemin de deploiement. Elle n'est PAS accordee
# aux roles applicatifs, et c'est cela qu'on verifie ici.
if [[ "$N" == "0" && "$NB" == "0" ]]; then
  sur execute-direct "aucune primitive n'est executable par le role applicatif."
  detail "non-vacuite: eurostruct_deployment, lui, en atteint"
  detail "$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
               where n.nspname='public' and p.proname in ($PRIMITIVES)
                 and has_function_privilege('eurostruct_deployment', p.oid,'EXECUTE')") — la surface n'est donc pas vide."
else
  rouge execute-direct "le role applicatif atteint des primitives (svc=$N, backend=$NB)."
fi

# ==========================================================================
# 6-8. INSERT, UPDATE, DELETE — separement, et sans clause WHERE
# ==========================================================================
# SANS `WHERE`, et ce n'est pas un raccourci: `normative_backend` n'a pas
# SELECT sur ces tables, et un `UPDATE ... WHERE` echouerait sur le SELECT
# implicite du predicat. Le refus mesurerait alors le droit de LIRE, pas celui
# d'ECRIRE — mesure faite, et c'est ainsi qu'un test d'immuabilite restait vert
# alors que la garde n'etait pas touchee.
for op in insert update delete; do
  echo "      -- $op: le role applicatif peut-il $op sur les octrois ?"
  case "$op" in
    insert) SQLOP="insert into normative_authorisation_grants
                     (grantee_id, grantee_name, permission, country_code,
                      standard_family, part, edition, reason)
                   values (gen_random_uuid(), 'FICTIF direct',
                           'can_validate_normative_reference',
                           'BE', 'EN 1992', '1-1', '2004', 'FICTIF durcissement')" ;;
    update) SQLOP="update normative_authorisation_grants set reason = 'FICTIF hd'" ;;
    delete) SQLOP="delete from normative_authorisation_grants" ;;
  esac
  R="$(ord -tAc "set role normative_backend; $SQLOP" 2>&1)"
  A="$(q "select has_table_privilege('normative_backend',
             'normative_authorisation_grants', '$op')")"
  detail "privilege declare: $op=$A"
  if grep -qiE 'permission denied' <<<"$R"; then
    if [[ "$A" == "f" ]]; then
      sur "$op" "« $op » refuse, et le privilege est effectivement absent."
    else
      troue "$op" "« $op » refuse alors que le privilege est present ($A):"
      detail "le refus vient d'ailleurs (SELECT implicite, RLS). Non concluant."
    fi
  elif grep -qiE 'ERROR|ERREUR' <<<"$R"; then
    sur "$op" "« $op » refuse: $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$R")"
  else
    # INSERT est le seul des trois qui DOIT reussir: c'est le chemin normal du
    # backend. Un refus y serait une regression, pas une garantie.
    if [[ "$op" == "insert" ]]; then
      sur insert "« insert » aboutit: le chemin nominal du backend est ouvert."
      detail "non-vacuite: update et delete, eux, sont refuses ci-dessous."
    else
      rouge "$op" "« $op » accepte sans erreur: l'historique est mutable."
    fi
  fi
done

# ==========================================================================
# 9. APPARTENANCES ET HERITAGE — direct ET transitif
# ==========================================================================
echo "      -- appartenances: un role applicatif atteint-il un role d'autorite ?"
MEMB="$(admb -tA -F' -> ' -c "
  select m.rolname, a.rolname
    from pg_roles a cross join pg_roles m
   where a.rolname in ($AUTORITES)
     and m.rolname in ('authenticated','anon','normative_backend',
                       'normative_governance','$SVC')
     and pg_has_role(m.rolname, a.rolname, 'USAGE')
   order by 1,2" 2>&1)"
if [[ -z "${MEMB// /}" ]]; then
  sur appartenances "aucun role applicatif n'atteint un role d'autorite (USAGE)."
  detail "non-vacuite: le migrateur, lui, en atteint $(q "select count(*) from pg_roles a
      where a.rolname in ($AUTORITES) and pg_has_role('$MIG', a.rolname, 'USAGE')") en phase 1."
else
  rouge appartenances "des roles applicatifs heritent d'un role d'autorite:"
  sed 's/^/                  /' <<<"$MEMB"
fi

# ==========================================================================
# 10. SET ROLE — la capacite, mesuree EN L'EXERCANT
# ==========================================================================
# `pg_has_role(..., 'SET')` dit ce que le catalogue pense. On l'ESSAIE aussi:
# un droit qui n'a jamais ete exerce est une affirmation, pas une mesure.
echo "      -- set-role: le role de service peut-il endosser une autorite ?"
ENDOSSE=""
for r in eurostruct_normative_writer eurostruct_normative_bootstrap \
         eurostruct_normative_activator; do
  OUT="$(ord -tAc "set role $r; select current_user" 2>&1 | tail -1 | tr -d ' ')"
  [[ "$OUT" == "$r" ]] && ENDOSSE="$ENDOSSE $r"
done
if [[ -z "${ENDOSSE// /}" ]]; then
  sur set-role "le role de service n'endosse aucun role d'autorite."
  detail "non-vacuite: il endosse bien normative_backend ->"
  detail "$(ord -tAc "set role normative_backend; select current_user" 2>&1 | tail -1)"
else
  rouge set-role "le role de service endosse:$ENDOSSE"
fi

# ==========================================================================
# 11. BYPASSRLS
# ==========================================================================
echo "      -- bypassrls: un role non-superutilisateur contourne-t-il la RLS ?"
BYP="$(admb -tA -c "select rolname from pg_roles
   where rolbypassrls and not rolsuper order by 1" 2>&1)"
if [[ -z "${BYP// /}" ]]; then
  sur bypassrls "aucun role non-superutilisateur ne porte BYPASSRLS."
else
  rouge bypassrls "des roles portent BYPASSRLS: $(tr '\n' ' ' <<<"$BYP")"
fi

# ==========================================================================
# 12-13. LE PROPRIETAIRE FACE A SA PROPRE RLS, ET FORCE ROW LEVEL SECURITY
# ==========================================================================
# Un proprietaire de table ECHAPPE a sa RLS tant que `FORCE ROW LEVEL SECURITY`
# n'est pas pose. Sur les tables d'autorite, cela signifierait que le
# proprietaire lit et ecrit sans policy — et le proprietaire est un role reel.
echo "      -- proprietaire-rls / force-rls: les tables d'autorite sont-elles forcees ?"
TABLES="'normative_authorisation_grants','normative_authorisation_revocations',
        'normative_rule_confirmations','normative_rule_confirmation_revocations'"
SANS_FORCE="$(admb -tA -c "select c.relname from pg_class c
   join pg_namespace n on n.oid = c.relnamespace
  where n.nspname='public' and c.relname in ($TABLES)
    and not c.relforcerowsecurity order by 1" 2>&1)"
SANS_RLS="$(admb -tA -c "select c.relname from pg_class c
   join pg_namespace n on n.oid = c.relnamespace
  where n.nspname='public' and c.relname in ($TABLES)
    and not c.relrowsecurity order by 1" 2>&1)"
if [[ -n "${SANS_RLS// /}" ]]; then
  rouge proprietaire-rls "des tables d'autorite n'ont pas de RLS: $(tr '\n' ' ' <<<"$SANS_RLS")"
else
  sur proprietaire-rls "les 4 tables d'autorite ont la RLS activee."
fi
if [[ -n "${SANS_FORCE// /}" ]]; then
  rouge force-rls "des tables d'autorite ne sont pas en FORCE: $(tr '\n' ' ' <<<"$SANS_FORCE")"
  detail "leur proprietaire lit et ecrit sans passer par une policy."
else
  sur force-rls "les 4 tables d'autorite sont en FORCE ROW LEVEL SECURITY."
fi

# ==========================================================================
# 14. LE CONTROLE DE DERIVE, EXERCE
# ==========================================================================
# `assert_authority_surface_hardened()` existe pour refuser une base derivee.
# UNE GARDE QUI N'EST JAMAIS APPELEE N'EN EST PAS UNE: on l'appelle.
echo "      -- controle-de-derive: assert_authority_surface_hardened() passe-t-elle ?"
# APPELEE SANS `SET ROLE`, et c'est le point: le plan de controle est membre
# de `eurostruct_deployment`, qui recoit EXECUTE. Exiger un endossement de role
# d'autorite reviendrait a exiger la capacite que le controle verifie absente.
R="$(ctl -tAc "select assert_authority_surface_hardened()" 2>&1)"
if grep -qiE 'ERROR|ERREUR' <<<"$R"; then
  if grep -qi 'does not exist' <<<"$R"; then
    troue controle-de-derive "la fonction n'existe pas: le controle n'est pas pose."
  else
    rouge controle-de-derive "le controle de derive REFUSE la base telle que deployee:"
    grep -m3 -oiE '(ERROR|ERREUR|DETAIL)[^|]{0,110}' <<<"$R" \
      | sed 's/^/                  /'
  fi
else
  sur controle-de-derive "le controle de derive accepte la base telle que deployee."
fi

# ==========================================================================
# 15-18. L'AUTO-ENROLEMENT — mesure, pas lecture
# ==========================================================================
# CE QUE CES QUATRE CONTROLES EXISTENT POUR EMPECHER. Une sonde a mesure, sur
# une base deployee, que le role qui detient INSERT sur les tables d'autorite
# avait pour MEMBRE REEL le migrateur, alors que la declaration nommait le
# login de service. Un GRANT emis par le migrateur vers un login ordinaire
# aboutissait, et conferait INSERT.
#
# La cause n'etait pas `pg_db_role_setting` — qui, lui, tient: un login
# ordinaire ne peut pas poser ces parametres, et `normative_declared_setting`
# filtre `setrole = 0`, donc ne lit QUE les reglages de base. La cause etait
# que la migration CREAIT le role, ce qui donne au createur l'ADMIN dessus.
#
# `pg_db_role_setting` peut transporter une CONFIGURATION. Il ne constitue
# jamais une AUTHENTIFICATION, et ces controles verifient les deux moities:
# qu'on ne peut pas s'y declarer, et que la declaration est confrontee aux
# appartenances reelles.

echo "      -- auto-enrolement-guc: un login ordinaire peut-il se declarer ?"
R="$(ord -tAc "alter role current_user
                 set eurostruct.authority_backend_logins = '$ORD'" 2>&1)"
N="$(q "select count(*) from pg_db_role_setting s join pg_roles r on r.oid = s.setrole
         where r.rolname = '$ORD'")"
# NON-VACUITE PAR RECONNEXION: `ord` ouvre une nouvelle connexion a chaque
# appel, donc la lecture ci-dessous est bien POST-RECONNEXION. Une
# auto-declaration qui ne prendrait effet qu'apres reconnexion serait vue.
LU="$(q "select normative_declared_setting('eurostruct.authority_backend_logins')")"
detail "ALTER ROLE CURRENT_USER SET -> $(head -c 70 <<<"$R" | tr '\n' ' ')"
detail "lignes pg_db_role_setting pour ce login: $N ; valeur lue par le produit: « $LU »"
if [[ "$N" != "0" ]] && [[ "$LU" == *"$ORD"* ]]; then
  rouge auto-enrolement-guc "un login ordinaire s'est declare authentificateur,"
  detail "et le produit LIT sa declaration apres reconnexion."
elif [[ "$N" != "0" ]]; then
  sur auto-enrolement-guc "l'auto-declaration est ECRITE mais jamais LUE:"
  detail "normative_declared_setting filtre setrole = 0, donc les seuls"
  detail "reglages de BASE. Valeur lue: « $LU »."
elif grep -qiE 'permission denied' <<<"$R"; then
  sur auto-enrolement-guc "l'auto-declaration est refusee a l'ecriture, et la"
  detail "valeur lue reste celle du deploiement: « $LU »."
else
  troue auto-enrolement-guc "ni ecriture ni refus explicite: non interpretable."
fi

echo "      -- auto-enrolement-role: le login ordinaire peut-il s'enroler ?"
R="$(ord -tAc "grant eurostruct_authority_backend to current_user" 2>&1)"
A="$(q "select pg_has_role('$ORD', 'eurostruct_authority_backend', 'USAGE')")"
detail "GRANT par lui-meme -> $(head -c 80 <<<"$R" | tr '\n' ' ') ; atteint: $A"
if [[ "$A" == "t" ]]; then
  rouge auto-enrolement-role "le login ordinaire atteint le backend d'autorite."
elif grep -qiE 'permission denied|must have admin' <<<"$R"; then
  sur auto-enrolement-role "un login ordinaire ne peut pas s'enroler."
  detail "non-vacuite: le backend de service declare, lui, l'atteint ->"
  detail "$(q "select pg_has_role('$SVC','eurostruct_authority_backend','USAGE')")"
else
  troue auto-enrolement-role "refuse pour une raison inattendue: $(head -c 80 <<<"$R")"
fi

echo "      -- migrateur-non-membre: le migrateur enrole-t-il qui il veut ?"
# LE COEUR DU DEFAUT MESURE. Le migrateur ne doit ni etre membre, ni pouvoir
# enroler: le role est cree par le PLAN DE CONTROLE en phase 0, precisement
# pour que le createur — donc le detenteur de l'ADMIN — ne soit pas lui.
MM="$(q "select pg_has_role('$MIG', 'eurostruct_authority_backend', 'USAGE')")"
R="$(mig -tAc "grant eurostruct_authority_backend to \"$ORD\"" 2>&1)"
A="$(q "select pg_has_role('$ORD', 'eurostruct_authority_backend', 'USAGE')")"
detail "migrateur membre: $MM ; GRANT par le migrateur -> $(head -c 70 <<<"$R" | tr '\n' ' ') ; enrole: $A"
if [[ "$MM" == "t" || "$A" == "t" ]]; then
  rouge migrateur-non-membre "le migrateur est membre du backend d'autorite ou"
  detail "peut y enroler un tiers. La contenance fermee en 6.3b6c est rouverte:"
  detail "il obtient INSERT sur les tables d'autorite par la porte d'a cote."
elif grep -qiE 'permission denied|must have admin' <<<"$R"; then
  sur migrateur-non-membre "le migrateur n'est pas membre et ne peut pas enroler."
  detail "non-vacuite: le plan de controle, qui a cree le role en phase 0, le"
  detail "peut — c'est lui qui detient l'ADMIN."
else
  troue migrateur-non-membre "resultat non interpretable: $(head -c 80 <<<"$R")"
fi

echo "      -- appartenance-declaree: les membres sont-ils ceux qu'on a declares ?"
R="$(ctl -tAc "select assert_authority_backend_membership()" 2>&1)"
# ON MESURE L'USAGE, PAS L'APPARTENANCE. Le plan de controle cree le role en
# phase 0 et en est donc membre au catalogue, avec `inherit=f set=f`: il peut
# l'ACCORDER, jamais l'utiliser. Compter les lignes de `pg_auth_members`
# confondrait « peut administrer » et « peut agir ».
MEMBRES="$(q "select coalesce(string_agg(m.rolname, ','), '(aucun)')
                from pg_roles m
               where not m.rolsuper
                 and m.rolname <> 'eurostruct_authority_backend'
                 and (pg_has_role(m.rolname,'eurostruct_authority_backend','USAGE')
                      or pg_has_role(m.rolname,'eurostruct_authority_backend','SET'))")"
ADMINS="$(q "select coalesce(string_agg(m.rolname, ','), '(aucun)')
               from pg_auth_members a
               join pg_roles rr on rr.oid = a.roleid
               join pg_roles m  on m.oid  = a.member
              where rr.rolname = 'eurostruct_authority_backend'
                and a.admin_option and not a.inherit_option and not a.set_option")"
DECL="$(q "select coalesce(valeur, '(vide)') from normative_authentication_contract
            where nom = 'eurostruct.authority_backend_logins'")"
detail "roles qui ATTEIGNENT le backend: $MEMBRES ; declaration figee: $DECL"
detail "administrateurs sans usage (legitime): $ADMINS"
if grep -qi 'does not exist' <<<"$R"; then
  troue appartenance-declaree "le controle n'existe pas: la declaration reste"
  detail "decorative."
elif grep -qiE 'ERROR|ERREUR' <<<"$R"; then
  rouge appartenance-declaree "des membres ne sont pas declares:"
  grep -m2 -oiE '(ERROR|ERREUR|DETAIL)[^|]{0,110}' <<<"$R" | sed 's/^/                  /'
else
  sur appartenance-declaree "les membres du backend d'autorite sont exactement"
  detail "ceux que le deploiement a declares. La declaration n'est pas"
  detail "decorative: elle est confrontee."
fi

# ==========================================================================
verdicts_verifier || true
verdicts_resume "6.3c — surface SQL de l'autorite"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " La surface SQL de l'autorite est fermee."
  exit 0
fi
exit 1
