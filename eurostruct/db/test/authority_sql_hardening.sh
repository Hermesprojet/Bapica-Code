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
  manifeste-egale-realite manifeste-derive-proprietaire \
  manifeste-non-declaree manifeste-public-vs-temoin \
  manifeste-refuse-vraiment \
  declencheurs-epingles declencheur-pg-temp-ferme \
  auto-enrolement-guc auto-enrolement-role migrateur-non-membre \
  appartenance-declaree policy-suit-privilege surface-du-backend

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
      esc_diag_rapporter "decor / phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
      return 1
    fi
  done
  m=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
  sortie=$(ctl -tAc "select normative_finalize_deployment($(esc_litteral "$m"))" 2>&1)
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "ACTIVE" ]]; then
    echoue "decor: finalisation -> $etat"
    esc_diag_rapporter "decor / finalisation" "$sortie"
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
            'check_normative_confirmation_revocation',
            'normative_grant_is_effective','normative_grant_descendants',
            'check_normative_grant_lineage',
            'normative_authenticated_actor','normative_authenticated_actor_or_null',
            'normative_authentication_configured','normative_bootstrap_mandate',
            'normative_constater_authentification',
            'assert_authority_backend_membership',
            'assert_authority_surface_hardened',
            'normative_decision_propose','normative_decision_approve',
            'normative_decision_consume','normative_lock_grant_chains',
            'check_normative_decision_transition','forbid_decision_delete'"
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
echo "      -- execute-direct: le role applicatif ORDINAIRE atteint-il une primitive ?"
# QUI EST « LE ROLE APPLICATIF » ICI. Le decor pose DEUX logins applicatifs, et
# les confondre a deja produit une mesure fausse: `$SVC` est membre de
# `eurostruct_authority_backend` (ligne 175) — c'est le BACKEND AUTHENTIFIE, et
# il DOIT atteindre les trois primitives de decision, sans quoi le chemin
# nominal n'existe pas. `$ORD` n'est membre que de `normative_backend`: c'est
# ce dont dispose un attaquant qui tient une connexion applicative.
#
# Ce controle mesure donc `$ORD` et `normative_backend`, qui doivent atteindre
# ZERO. La surface legitime du backend est mesuree separement, et bornee.
N="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname in ($PRIMITIVES)
          and has_function_privilege('$ORD', p.oid, 'EXECUTE')")"
NB="$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
         where n.nspname = 'public' and p.proname in ($PRIMITIVES)
           and has_function_privilege('normative_backend', p.oid, 'EXECUTE')")"
ATTEINTES="$(q "select coalesce(string_agg(distinct p.proname, ', '), '(aucune)')
                  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                 where n.nspname='public' and p.proname in ($PRIMITIVES)
                   and has_function_privilege('$ORD', p.oid, 'EXECUTE')")"
detail "atteintes par le role ordinaire « $ORD »: $N ($ATTEINTES)"
detail "atteintes par normative_backend: $NB"
# `bootstrap_normative_administrator` est accordee a `eurostruct_deployment`
# A DESSEIN (6.3b5): c'est le chemin de deploiement. Elle n'est PAS accordee
# aux roles applicatifs, et c'est cela qu'on verifie ici.
if [[ "$N" == "0" && "$NB" == "0" ]]; then
  sur execute-direct "aucune primitive n'est executable par le role applicatif"
  detail "ordinaire ni par normative_backend."
  detail "non-vacuite: eurostruct_deployment, lui, en atteint"
  detail "$(q "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
               where n.nspname='public' and p.proname in ($PRIMITIVES)
                 and has_function_privilege('eurostruct_deployment', p.oid,'EXECUTE')") — la surface n'est donc pas vide."
else
  rouge execute-direct "le role applicatif ordinaire atteint des primitives"
  detail "(ord=$N: $ATTEINTES ; normative_backend=$NB)."
fi

echo "      -- surface-du-backend: ce que le backend authentifie atteint, et rien de plus"
# UNE SURFACE OUVERTE SE MESURE PAR SON CONTENU, PAS PAR SON EXISTENCE. Le
# backend authentifie doit atteindre EXACTEMENT les fonctions declarees
# ci-dessous. Compter « au moins trois » laisserait un GRANT de plus passer
# sans que rien ne le dise — c'est precisement ainsi qu'une porte s'ajoute.
#
# LE CHEMIN NORMATIF — sept fonctions: les trois primitives de decision, la
# RELECTURE du dossier gele, les deux derivations d'acteur, et la lecture
# d'efficacite. `normative_decision_review` a ete ajoutee par 0017 et declaree
# ici: sans elle, le second ingenieur approuve un identifiant et non un
# contenu, son navigateur n'ayant jamais vu le dossier. Elle ne rend aucun
# acteur, et le quatre-yeux reste garanti par la contrainte de table.
#
# LE CHEMIN DE TRAVAIL — cinq primitives, ajoutees par 0018 et declarees de
# meme: lister et creer un projet, enregistrer un calcul, relire l'historique,
# rouvrir un calcul. Le MEME backend les execute, parce que c'est le meme
# service qui presente le meme jeton verifie. Ce controle a refuse des leur
# ajout, avec le message exact:
#
#   ROUGE: la surface du backend authentifie a change.
#
# Il fait exactement ce pour quoi il existe: une porte de plus ne s'ouvre pas
# en silence. C'est la declaration qui manquait, pas la garde qui exagerait.
#
# CE QUE LES CINQ N'OUVRENT PAS. Aucune ne touche
# `normative_authorisation_grants` ni `normative_authority_decisions`: elles
# ecrivent `projects`, `calculations`, `results` et `verifications`, sous les
# politiques RLS de 0018 et sous l'acteur derive de la session.
#
# LE CHEMIN DES LIVRABLES — sept primitives, ajoutees par 0020 et declarees de
# meme: creer un brouillon depuis un calcul gele, lister, relire avec son
# historique, soumettre a la relecture ou revenir au brouillon, attester,
# emettre, et rendre l'emplacement des octets. Elles rendent ATTEIGNABLE la
# machine a etats que 0005 et 0009 avaient construite sans porte.
#
# LE CHEMIN D'ENTREE — huit primitives, ajoutees par 0024 et declarees de
# meme: fonder son bureau, lister ses bureaux, emettre / accepter / revoquer /
# lister une invitation, lister et administrer les membres. Elles ferment un
# cul-de-sac mesure: un compte authentifie sans ligne dans
# `organization_members` arrivait devant un ecran vide et ne pouvait rien
# faire — jamais. La seule facon d'exister dans l'application etait un
# `insert` fait a la main par le proprietaire de la base.
#
# CE QUE LES HUIT N'OUVRENT PAS. Aucune n'ecrit dans `deliverables`,
# `validations` ni le registre normatif. Un `validating_engineer` cree par une
# invitation porte un role d'ORGANISATION — qui atteste dans ce bureau — et
# aucune habilitation NORMATIVE: celle-la se prend par le quatre-yeux.
#
# ET LES FONCTIONS INTERNES — `project_backend_actor`,
# `project_actor_is_member`, `project_actor_can_write`,
# `project_annexe_en_vigueur` (0018), `project_calculation_is_publishable`
# (0020), `project_exiger_capacite`, `project_actor_peut_rediger`,
# `project_actor_peut_valider` (0023) — n'apparaissent PAS dans cette liste, et
# c'est voulu: elles ne sont accordees qu'au proprietaire des primitives. Leur
# absence est elle-meme une mesure, pas un oubli.
#
# SANS ESPACES: `q()` normalise en retirant les blancs, et comparer une chaine
# espacee a une chaine compactee produisait un rouge sur deux ensembles
# IDENTIQUES — un faux rouge est aussi trompeur qu'un faux vert.
#
# L'ORDRE EST CELUI DE `order by p.proname`, et non celui du recit ci-dessus:
# la comparaison porte sur la chaine entiere.
ATTENDUES="normative_authenticated_actor,normative_authenticated_actor_or_null,normative_decision_approve,normative_decision_consume,normative_decision_propose,normative_decision_review,normative_grant_is_effective,organization_bootstrap,organization_invitation_accept,organization_invitation_create,organization_invitation_list,organization_invitation_revoke,organization_member_list,organization_member_update,project_calculation_list,project_calculation_read,project_calculation_record,project_deliverable_bytes,project_deliverable_create,project_deliverable_finalize,project_deliverable_issue_attestation,project_deliverable_list,project_deliverable_read,project_deliverable_transition,project_deliverable_validate,project_workspace_create,project_workspace_list,project_workspace_organisations"
OUVERTES="$(q "select coalesce(string_agg(distinct p.proname, ', '
                                 order by p.proname), '(aucune)')
                 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                where n.nspname = 'public'
                  and has_function_privilege('eurostruct_authority_backend',
                                             p.oid, 'EXECUTE')
                  and not has_function_privilege('public', p.oid, 'EXECUTE')")"
detail "atteintes par eurostruct_authority_backend: $OUVERTES"
if [[ "$OUVERTES" == "$ATTENDUES" ]]; then
  sur surface-du-backend "le backend authentifie atteint exactement les"
  detail "vingt-huit fonctions declarees — sept sur le chemin normatif (trois"
  detail "primitives de decision, la relecture du dossier gele, deux"
  detail "derivations d'acteur, la lecture d'efficacite), cinq sur le chemin de"
  detail "travail (projets, calcul, historique, reouverture), huit sur celui"
  detail "des livrables (brouillon, liste, relecture, transition, attestation,"
  detail "emission, document emis, octets) et huit sur celui de l'entree"
  detail "(fonder, lister ses"
  detail "bureaux, emettre / accepter / revoquer / lister une invitation,"
  detail "lister et administrer les membres). Ni plus, ni moins."
elif [[ "$OUVERTES" == "(aucune)" ]]; then
  rouge surface-du-backend "le backend authentifie n'atteint RIEN: le chemin"
  detail "nominal du quatre-yeux n'existe pas."
else
  rouge surface-du-backend "la surface du backend authentifie a change."
  detail "attendu: $ATTENDUES"
  detail "mesure : $OUVERTES"
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

# --------------------------------------------------------------------------
# LE MANIFESTE — quatre controles, dont trois par FALSIFICATION
# --------------------------------------------------------------------------
# CE QUE `assert_authority_manifest()` APPORTE que l'agregee n'a pas.
# `assert_authority_composition()` balaie `pg_proc` EN FILTRANT PAR LE
# PROPRIETAIRE ATTENDU: une fonction dont le proprietaire derive SORT du
# balayage, et l'assertion devient aveugle a la derive qu'elle existe pour
# detecter. Le manifeste decouvre par un critere orthogonal — le vocabulaire —
# et compare les deux ensembles dans les DEUX SENS.
#
# Les trois falsifications ci-dessous sont posees puis DEFAITES sur la base du
# decor. Elles ne prouvent rien sur le produit livre; elles prouvent que le
# controle qui, lui, porte sur le produit, sait rougir.
echo "      -- manifeste-egale-realite: le manifeste decrit-il la base deployee ?"
R="$(ctl -tAc "select assert_authority_manifest()" 2>&1)"
if grep -qiE 'ERROR|ERREUR' <<<"$R"; then
  if grep -qi 'does not exist' <<<"$R"; then
    troue manifeste-egale-realite "la fonction n'existe pas: le controle n'est pas pose."
  else
    rouge manifeste-egale-realite "MF1. le manifeste ne decrit PAS la base deployee:"
    grep -m4 -oiE 'AUTHORITY_MANIFEST_[A-Z_]+[^|]{0,110}' <<<"$R" \
      | sed 's/^/                  /'
  fi
else
  sur manifeste-egale-realite "manifeste == realite sur la base telle que deployee."
fi

echo "      -- manifeste-refuse-vraiment: l'assertion LEVE-t-elle, ou se contente-t-elle de compter ?"
# LE TEMOIN PROPRE DE MF1, ET POURQUOI IL FALLAIT L'ECRIRE.
#
# La campagne des 103 a laisse MF1 survivre. MF1 neutralise le `raise` final de
# `assert_authority_manifest()`: l'assertion compte encore les ecarts, mais ne
# refuse plus. Les trois autres controles du manifeste rougissaient bien — ils
# constatent « l'assertion ne s'est pas plainte » — mais ils rougissaient sous
# les identifiants MF2, MF3 et MF4. MF1 n'avait pas de temoin portant son nom,
# et un temoin implicite ne vaut pas un temoin.
#
# CELUI-CI NE MESURE QU'UNE CHOSE: face a un ecart REEL, l'assertion doit
# LEVER. Pas signaler, pas journaliser: lever. C'est exactement la garantie que
# MF1 retire, et rien d'autre ne la porte.
if ! admb -q -c "alter function normative_decision_approve(uuid)
                  owner to eurostruct_normative_activator" >/dev/null 2>&1; then
  troue manifeste-refuse-vraiment "l'ecart n'a pas pu etre pose."
else
  # LA SORTIE N'EST PAS LE CRITERE: LE CODE DE RETOUR L'EST. Une assertion qui
  # ne leve plus rend 0 en silence, et son absence de message ressemble a un
  # succes. On interroge donc psql avec ON_ERROR_STOP et on lit son code.
  MF1_CODE=0
  ctl -q -v ON_ERROR_STOP=1 -c "select assert_authority_manifest()" >/dev/null 2>&1 \
    || MF1_CODE=$?
  admb -q -c "alter function normative_decision_approve(uuid)
               owner to eurostruct_normative_writer" >/dev/null 2>&1
  # NON-VACUITE: sur une base CONFORME, la meme assertion doit rendre 0.
  # Sans cela, un refus permanent — pour n'importe quelle raison — passerait
  # pour la preuve que l'assertion leve sur ecart.
  MF1_SAIN=0
  ctl -q -v ON_ERROR_STOP=1 -c "select assert_authority_manifest()" >/dev/null 2>&1 \
    || MF1_SAIN=$?
  if [[ "$MF1_SAIN" != "0" ]]; then
    troue manifeste-refuse-vraiment \
      "l'assertion refuse aussi une base CONFORME (code $MF1_SAIN): le"
    detail "controle ne distinguerait pas un refus d'un dysfonctionnement."
  elif [[ "$MF1_CODE" == "0" ]]; then
    rouge manifeste-refuse-vraiment \
      "MF1. face a une derive REELLE, l'assertion n'a pas leve (code 0):"
    detail "elle compte des ecarts et les garde pour elle. Une assertion qui"
    detail "ne refuse pas est un journal, pas une garantie."
  else
    sur manifeste-refuse-vraiment \
      "face a une derive reelle l'assertion LEVE (code $MF1_CODE), et rend 0"
    detail "sur une base conforme."
  fi
fi

echo "      -- manifeste-derive-proprietaire: une derive de proprietaire est-elle VUE ?"
# C'EST LE CAS QUE L'AGREGEE NE PEUT PAS VOIR. En changeant le proprietaire, la
# fonction sort du balayage de `assert_authority_composition()` — qui filtre
# justement par proprietaire attendu — et son silence ne veut plus rien dire.
# LA DERIVE EST POSEE PAR LE SUPERUTILISATEUR SUR LA BASE DU DECOR, et c'est
# la seule facon honnete. Mesure: le plan de controle ne PEUT PAS changer le
# proprietaire d'une fonction qu'il ne possede pas — c'est le confinement qui
# marche — et le controle se rendait NON_PARCOURU, un trou, pas un vert.
# Le superutilisateur est hors modele de menace: on ne lui demande pas de
# prouver une capacite, on l'utilise pour FABRIQUER l'etat derive.
if ! admb -q -c "alter function normative_decision_approve(uuid)
                  owner to eurostruct_normative_activator" >/dev/null 2>&1; then
  troue manifeste-derive-proprietaire "la derive n'a pas pu etre posee."
else
  R="$(ctl -tAc "select assert_authority_manifest()" 2>&1)"
  A="$(ctl -tAc "select assert_authority_composition()" 2>&1)"
  admb -q -c "alter function normative_decision_approve(uuid)
               owner to eurostruct_normative_writer" >/dev/null 2>&1
  if grep -q 'AUTHORITY_MANIFEST_OWNER' <<<"$R"; then
    if grep -qiE 'ERROR|ERREUR' <<<"$A"; then
      sur manifeste-derive-proprietaire \
        "la derive de proprietaire est vue par le manifeste ET par l'agregee."
    else
      sur manifeste-derive-proprietaire \
        "la derive de proprietaire est vue par le manifeste; l'agregee ne la"
      detail "voit pas — c'est exactement l'angle mort que le manifeste ferme."
    fi
  else
    rouge manifeste-derive-proprietaire \
      "MF2. une derive de proprietaire n'est vue par AUCUNE des deux assertions."
  fi
fi

echo "      -- manifeste-non-declaree: une fonction ajoutee au perimetre est-elle VUE ?"
if ! admb -q -c "create function normative_intruse_du_harnais() returns int
                  language sql as 'select 1'" >/dev/null 2>&1; then
  troue manifeste-non-declaree "l'intruse n'a pas pu etre creee."
else
  R="$(ctl -tAc "select assert_authority_manifest()" 2>&1)"
  admb -q -c "drop function if exists normative_intruse_du_harnais()" >/dev/null 2>&1
  if grep -q 'AUTHORITY_MANIFEST_UNDECLARED' <<<"$R"; then
    sur manifeste-non-declaree \
      "une fonction du perimetre non declaree au manifeste est signalee."
  else
    rouge manifeste-non-declaree \
      "MF3. une fonction ajoutee au perimetre passe inapercue: le sens"
    detail "realite -> manifeste ne porte rien."
  fi
fi

echo "      -- manifeste-public-vs-temoin: PUBLIC est-il lu par l'ACL, pas par un temoin ?"
# LA DIRECTION DU FAUX POSITIF. Mesure sur PG16: un role ORDINAIRE peut detenir
# EXECUTE sur une fonction ou PUBLIC ne l'a PAS. Prendre un role temoin pour
# temoigner de PUBLIC rapporterait donc une ouverture qui n'existe pas.
if ! admb -q -c "grant execute on function normative_decision_approve(uuid)
                  to normative_backend" >/dev/null 2>&1; then
  troue manifeste-public-vs-temoin "l'octroi au temoin n'a pas pu etre pose."
else
  R="$(ctl -tAc "select assert_authority_manifest()" 2>&1)"
  admb -q -c "revoke execute on function normative_decision_approve(uuid)
               from normative_backend" >/dev/null 2>&1
  if grep -q 'AUTHORITY_MANIFEST_PUBLIC_EXECUTE' <<<"$R"; then
    rouge manifeste-public-vs-temoin \
      "MF4. un role ORDINAIRE est rapporte comme PUBLIC: la semantique ACL"
    detail "grantee public n'est pas celle qui est lue."
  elif grep -q 'AUTHORITY_MANIFEST_ACL_WIDER' <<<"$R"; then
    sur manifeste-public-vs-temoin \
      "un role ordinaire est rapporte ACL_WIDER, jamais PUBLIC."
  else
    rouge manifeste-public-vs-temoin \
      "MF4. un octroi a un role ordinaire n'est vu ni comme elargissement ni"
    detail "autrement: le controle ne porte rien."
  fi
fi

# --------------------------------------------------------------------------
# LE CONTEXTE D'EXECUTION DES DECLENCHEURS — deux controles
# --------------------------------------------------------------------------
# CE QUI A ETE MESURE, ET QUI A CHANGE LE CORRECTIF EN COURS DE ROUTE.
#
# Une fonction declencheur sans `search_path` epingle s'execute avec le chemin
# de CELUI QUI DECLENCHE l'ecriture. Sur la forme exacte de
# `forbid_validated_calculation_mutation`, base jetable, 28/08:
#
#   sans manipulation                                -> la garde REFUSE
#   apres `create temporary table validations (...)` -> « UPDATE 1 »
#
# La garde d'immuabilite decennale etait donc contournable par toute session
# capable de creer une table temporaire — c'est-a-dire toutes, `TEMP` etant
# accorde a PUBLIC par defaut.
#
# ET LE PREMIER CORRECTIF NE FERMAIT RIEN. Ecrire `set search_path =
# pg_catalog, public` en croyant fermer par OMISSION de `pg_temp` laisse
# celui-ci consulte EN PREMIER pour les relations. Table mesuree:
#
#   pg_catalog, public            -> UPDATE 1   (contourne)
#   pg_catalog, public, pg_temp   -> REFUSE     (la garde tient)
#   pg_temp, pg_catalog, public   -> UPDATE 1   (contourne)
#
# Seule la troisieme position ferme le vecteur. Le controle ci-dessous exige
# donc la POSITION, pas la seule presence d'un `search_path`.
echo "      -- declencheurs-epingles: chaque garde a-t-elle un chemin, et pg_temp en dernier ?"
NON_EPINGLES=$(ctl -tAc "
  select coalesce(string_agg(p.oid::regprocedure::text, ', '), '')
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.prorettype = 'trigger'::regtype
     and (p.proname like 'forbid\_%' or p.proname like 'check\_normative\_%'
       or p.proname like 'normative\_%')
     and (p.proconfig is null
          or not exists (select 1 from unnest(p.proconfig) c
                          where c like 'search\_path=%'))" 2>&1)
MAL_PLACES=$(ctl -tAc "
  select coalesce(string_agg(p.oid::regprocedure::text || ' [' || c || ']', ', '), '')
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace,
         lateral unnest(p.proconfig) c
   where n.nspname = 'public' and p.prorettype = 'trigger'::regtype
     and (p.proname like 'forbid\_%' or p.proname like 'check\_normative\_%'
       or p.proname like 'normative\_%')
     and c like 'search\_path=%'
     and c not like '%pg\_temp'" 2>&1)
if [[ -n "$NON_EPINGLES" ]]; then
  rouge declencheurs-epingles "TP1. des gardes s'executent avec le chemin de l'appelant:"
  detail "$NON_EPINGLES"
elif [[ -n "$MAL_PLACES" ]]; then
  rouge declencheurs-epingles "TP1. des gardes ne terminent pas leur chemin par pg_temp:"
  detail "$MAL_PLACES"
  detail "Omettre pg_temp ne le ferme pas: il est alors consulte EN PREMIER."
else
  sur declencheurs-epingles \
    "toutes les gardes ont un chemin epingle terminant par pg_temp."
fi

echo "      -- declencheur-pg-temp-ferme: le masquage par pg_temp est-il REELLEMENT ferme ?"
# ON EPROUVE LE MECANISME, PAS SA DECLARATION. Un `proconfig` correct ne prouve
# pas que PostgreSQL se comporte comme on le croit — et cette croyance a ete
# fausse DEUX FOIS en ecrivant ce controle:
#
#   1. « omettre pg_temp le ferme » — faux: omis, il est consulte EN PREMIER;
#   2. un premier decor rendait `old` depuis un BEFORE UPDATE, ce qui ANNULE
#      l'ecriture quoi que la garde decide: la ligne restait inchangee et le
#      controle concluait « la garde tient » pour les cinq variantes, y compris
#      la fonction nue. Le verdict portait sur un fait que rien ne produisait.
#
# Table finale, mesuree sur decor verifie, verdict = VALEUR ECRITE:
#
#   aucun search_path              -> CONTOURNEE
#   public, pg_temp                -> tient
#   pg_catalog, public, pg_temp    -> tient
#   pg_catalog, public             -> CONTOURNEE
#   pg_temp, pg_catalog, public    -> CONTOURNEE
#
# Le decor est autonome — deux tables, deux gardes — pour que le controle
# mesure la SEMANTIQUE du serveur et non l'etat du produit.
TP_ERR=$(admb -q -v ON_ERROR_STOP=1 2>&1 <<'SQL'
create table tp_preuves (cible uuid);
create table tp_objets  (id uuid primary key, val int);
create function tp_garde_nue() returns trigger language plpgsql as $$
begin
  if exists (select 1 from tp_preuves p where p.cible = old.id) then
    raise exception 'TP: fige' using errcode = 'restrict_violation';
  end if;
  return new;
end; $$;
create function tp_garde_epinglee() returns trigger language plpgsql
  set search_path = pg_catalog, public, pg_temp as $$
begin
  if exists (select 1 from tp_preuves p where p.cible = old.id) then
    raise exception 'TP: fige' using errcode = 'restrict_violation';
  end if;
  return new;
end; $$;
insert into tp_objets  values ('11111111-1111-1111-1111-111111111111', 1);
insert into tp_preuves values ('11111111-1111-1111-1111-111111111111');
SQL
)
if [[ -n "$TP_ERR" ]]; then
  troue declencheur-pg-temp-ferme "le decor du controle n'a pas pu etre pose:"
  detail "${TP_ERR:0:120}"
else
  tp_tenter() {   # tp_tenter <fonction> <valeur> -> imprime la valeur ecrite
    # `create trigger <nom> BEFORE ... ON <table>`, et non « ON ... BEFORE ».
    # Mesure: la forme inverse est refusee, le declencheur n'existe pas, et les
    # deux variantes rendent alors « contournee » — un rouge fabrique par une
    # faute de syntaxe du controle lui-meme. On VERIFIE donc sa presence.
    admb -q -c "create trigger tp before update on tp_objets for each row
                  execute function $1()" >/dev/null 2>&1
    if [[ "$(admb -tAc "select count(*) from pg_trigger
                         where tgname='tp' and not tgisinternal")" != "1" ]]; then
      echo "DECLENCHEUR-ABSENT"; return 0
    fi
    admb -q >/dev/null 2>&1 <<SQL
create temporary table tp_preuves (cible uuid);
update tp_objets set val = $2;
SQL
    admb -q -c "drop trigger tp on tp_objets" >/dev/null 2>&1
    # LE VERDICT EST LA VALEUR ECRITE. psql poursuit apres une erreur dans un
    # heredoc: la derniere ligne de sortie ne dit rien de ce qui a eu lieu.
    admb -tAc "select val from tp_objets"
  }
  admb -q -c "update tp_objets set val = 1" >/dev/null 2>&1
  TP_NUE=$(tp_tenter tp_garde_nue 2)
  admb -q -c "update tp_objets set val = 1" >/dev/null 2>&1
  TP_EPI=$(tp_tenter tp_garde_epinglee 3)
  if [[ "$TP_NUE" == "DECLENCHEUR-ABSENT" || "$TP_EPI" == "DECLENCHEUR-ABSENT" ]]; then
    troue declencheur-pg-temp-ferme \
      "le declencheur du decor n'a pas pu etre pose: le controle ne mesure rien."
  elif [[ "$TP_NUE" != "2" ]]; then
    troue declencheur-pg-temp-ferme \
      "le vecteur pg_temp ne se reproduit pas sur ce serveur (garde nue:"
    detail "valeur $TP_NUE, attendu 2). Le controle ne mesurerait rien."
  elif [[ "$TP_EPI" != "1" ]]; then
    rouge declencheur-pg-temp-ferme \
      "TP2. la garde EPINGLEE est contournee par pg_temp (valeur $TP_EPI):"
    detail "le chemin ne ferme pas ce qu'il pretend fermer."
  else
    sur declencheur-pg-temp-ferme \
      "garde nue contournee (valeur $TP_NUE), garde epinglee refuse — le"
    detail "vecteur est ferme par la POSITION de pg_temp, et c'est mesure."
  fi
  admb -q >/dev/null 2>&1 <<'SQL'
drop function if exists tp_garde_nue(); drop function if exists tp_garde_epinglee();
drop table if exists tp_objets; drop table if exists tp_preuves;
SQL
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

echo "      -- policy-suit-privilege: un droit sans policy est un mensonge"
# CE QUE CE CONTROLE MESURE, ET POURQUOI IL EXISTE.
#
# Mesure du 26/08: 0013 avait deplace INSERT de `normative_backend` vers
# `eurostruct_authority_backend` sur QUATRE tables, et n'avait fait suivre la
# policy que sur la premiere. Les trois autres restaient `to normative_backend`.
# Sous FORCE ROW LEVEL SECURITY, le backend authentifie detenait donc le
# privilege sans aucune policy qui le nomme:
#   * en INSERT, chaque ligne etait refusee — le chemin de revocation et le
#     chemin de confirmation etaient morts POUR TOUT LE MONDE;
#   * en SELECT, la table repond ZERO LIGNE au lieu d'une erreur, et
#     `normative_grant_is_effective()` — qui est `language sql`, donc DROITS DE
#     L'APPELANT — declarait EFFICACE une habilitation revoquee.
#
# `has_table_privilege` repond « oui » dans les deux cas. C'est exactement ce
# qui rend l'ecart invisible: le catalogue des droits est vert, la policy
# manque, et le systeme repond faux sans se plaindre.
CIBLES="$(q "select coalesce(string_agg(t, ', '), '(aucune)') from (
  select c.relname || '.' || x.priv as t
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
   cross join lateral (values ('SELECT','r'), ('INSERT','a')) as x(priv, cmd)
   where n.nspname = 'public' and c.relkind = 'r'
     and c.relrowsecurity and c.relforcerowsecurity
     and has_table_privilege('eurostruct_authority_backend', c.oid, x.priv)
     and not exists (
       select 1 from pg_policy p
        where p.polrelid = c.oid and p.polpermissive
          and p.polcmd in (x.cmd, '*')
          and (p.polroles = '{0}'::oid[]
               or exists (select 1 from unnest(p.polroles) as pr(oid)
                           where pg_has_role('eurostruct_authority_backend',
                                             pr.oid, 'USAGE'))))
   order by 1) s")"
COUVERTS="$(q "select count(*) from pg_policy p
                join pg_class c on c.oid = p.polrelid
               where p.polpermissive and p.polcmd in ('a','*')
                 and c.relname in ('normative_authorisation_grants',
                       'normative_authorisation_revocations',
                       'normative_rule_confirmations',
                       'normative_rule_confirmation_revocations')
                 and exists (select 1 from unnest(p.polroles) as pr(oid)
                              where pg_has_role('eurostruct_authority_backend',
                                                pr.oid, 'USAGE'))")"
detail "privileges sans policy: $CIBLES"
detail "tables d'ecriture normative couvertes par une policy INSERT: $COUVERTS/4"
if [[ "$CIBLES" != "(aucune)" ]]; then
  rouge policy-suit-privilege "le backend d'autorite detient des droits que"
  detail "AUCUNE policy ne nomme: $CIBLES."
  detail "Sous FORCE RLS un INSERT y est refuse et un SELECT y rend zero ligne."
elif [[ "$COUVERTS" != "4" ]]; then
  rouge policy-suit-privilege "les quatre ecritures normatives ne sont pas"
  detail "toutes couvertes par une policy INSERT nommant le backend d'autorite"
  detail "($COUVERTS/4): une porte du chemin nominal est murée."
else
  sur policy-suit-privilege "chaque privilege du backend d'autorite est"
  detail "accompagne d'une policy qui le nomme, et les quatre ecritures"
  detail "normatives sont ouvertes a ce seul role. Non-vacuite: le compte"
  detail "des tables couvertes est mesure, pas suppose."
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
