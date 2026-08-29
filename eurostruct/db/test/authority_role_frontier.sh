#!/usr/bin/env bash
#
# EUROSTRUCT — LA FRONTIERE DES ROLES POSTGRESQL, FERMEE PAR MESURE
#
#   db/test/authority_role_frontier.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `eurostruct_authority_backend` est le SEUL role qui ecrit dans les tables
# d'autorite. Toute la frontiere posee par 6.3c tient a une question: le
# MIGRATEUR — l'identite technique qui applique un schema — peut-il, par un
# moyen ordinaire, atteindre ce role ou y enroler quelqu'un ?
#
# UN AUDIT PRECEDENT A REPONDU « NON » POUR LA MAUVAISE RAISON. Il mesurait
# `pg_db_role_setting`, c'est-a-dire une CONFIGURATION, et concluait que
# l'auto-enrolement etait ferme. Or le chemin reel n'etait pas la: il etait
# dans l'APPARTENANCE, et il s'est ouvert le jour ou une migration a cree le
# role — PostgreSQL donne l'ADMIN OPTION a qui cree.
#
# CE QU'IL FAUT DISTINGUER, ET QUE `pg_has_role` SEUL NE DIT PAS
# ---------------------------------------------------------------
# Sur PostgreSQL 16, une appartenance porte TROIS options independantes:
#
#   inherit_option  le membre herite des privileges sans rien demander;
#   set_option      le membre peut `SET ROLE` vers la cible;
#   admin_option    le membre peut ACCORDER la cible a un tiers.
#
# `CREATE ROLE` par un role CREATEROLE cree une appartenance
# `admin=t, inherit=f, set=f`: le createur ne peut ni heriter ni endosser —
# mais il peut ENROLER QUI IL VEUT. Mesurer USAGE et SET et s'arreter la
# laisserait donc passer exactement le chemin qui s'etait ouvert.
#
# ADMINISTRER N'EST PAS UTILISER, MAIS ADMINISTRER SUFFIT A S'OCTROYER
# L'USAGE. C'est la raison d'etre de ce harnais.
#
# `pg_db_role_setting` NE PEUT PAS ATTESTER. Une liste modifiable par
# l'entite qui demande l'acces n'est pas une allowlist de confiance: elle
# decrit une configuration, ou verifie a posteriori une appartenance creee par
# une autorite externe. Elle ne declenche jamais un GRANT.
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

PREFIXE="${1:?usage: authority_role_frontier.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_role_frontier.sh" || exit 2
harnais_verrou_prendre  "authority_role_frontier.sh" || exit $?
exiger_cluster_jetable  "authority_role_frontier.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "authority_role_frontier.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  matrice-avant matrice-apres \
  login-ordinaire migrateur-createur migrateur-sans-admin migrateur-createrole \
  role-deploiement proprietaire-base transitivite reconnexion \
  rejeu-des-migrations ecriture-reelle admin-option-borne \
  egalite-declaree-reelle \
  postcondition-membre-en-trop postcondition-admin-direct \
  postcondition-admin-en-chaine postcondition-declare-absent \
  graphe-cartographie admin-non-vacuite createrole-ne-reintegre-pas \
  plan-racine-externe


# ==========================================================================
# LE POINT DE CHAQUE VERDICT — DECLARE, ET NON RELU DANS LA PROSE
# ==========================================================================
# Meme forme que dans `migration_postconditions.sh`: le lanceur relisait la
# sortie pour y retrouver « PC1 » dans « ROUGE: PC1. un membre non declare... ».
# La prose destinee a l'humain decidait du verdict. Le harnais CONNAIT le point
# de chacun de ses verdicts.
#
# QUATRE VERDICTS SEULEMENT PORTENT UN POINT DU REGISTRE — les quatre
# postconditions, PC1 a PC4. Les dix-huit autres decrivent la frontiere elle-
# meme et ne sont vises par aucune mutation aujourd'hui; ils portent leur
# propre nom comme point. Ce n'est pas du remplissage: le jour ou une mutation
# les visera, le point existera deja et le pre-vol le trouvera.
#
# LA SORTIE HUMAINE NE CHANGE PAS. Les messages continuent d'ouvrir par
# « PC1. »; cette ligne n'a simplement plus autorite sur le verdict.
declare -A POINT_DE=(
  [postcondition-membre-en-trop]=PC1   [postcondition-admin-en-chaine]=PC2
  [postcondition-declare-absent]=PC3   [postcondition-admin-direct]=PC4
  [matrice-avant]=matrice-avant        [matrice-apres]=matrice-apres
  [login-ordinaire]=login-ordinaire    [migrateur-createur]=migrateur-createur
  [migrateur-sans-admin]=migrateur-sans-admin
  [migrateur-createrole]=migrateur-createrole
  [role-deploiement]=role-deploiement  [proprietaire-base]=proprietaire-base
  [transitivite]=transitivite          [reconnexion]=reconnexion
  [rejeu-des-migrations]=rejeu-des-migrations
  [ecriture-reelle]=ecriture-reelle    [admin-option-borne]=admin-option-borne
  [egalite-declaree-reelle]=egalite-declaree-reelle
  [graphe-cartographie]=graphe-cartographie
  [admin-non-vacuite]=admin-non-vacuite
  [createrole-ne-reintegre-pas]=createrole-ne-reintegre-pas
  [plan-racine-externe]=plan-racine-externe
)

# TOUT VERDICT DECLARE DOIT AVOIR SON POINT, ET RECIPROQUEMENT. Un verdict sans
# point emettrait pour un point vide: le lanceur lirait NOT_RUN sans que rien
# ne dise pourquoi. Une entree orpheline signale un verdict renomme dont la
# table garde l'ancien nom.
POINTS_MANQUANTS=""; POINTS_ORPHELINS=""
for _v in "${VERDICTS_DECLARES[@]}"; do
  [[ -n "${POINT_DE[$_v]:-}" ]] || POINTS_MANQUANTS="$POINTS_MANQUANTS $_v"
done
for _v in "${!POINT_DE[@]}"; do
  case " ${VERDICTS_DECLARES[*]} " in
    *" $_v "*) ;;
    *) POINTS_ORPHELINS="$POINTS_ORPHELINS $_v" ;;
  esac
done
if [[ -n "$POINTS_MANQUANTS$POINTS_ORPHELINS" ]]; then
  echo "REFUS: la table des points et les verdicts declares divergent." >&2
  [[ -z "$POINTS_MANQUANTS" ]] || \
    echo "       sans point (non attribuable):$POINTS_MANQUANTS" >&2
  [[ -z "$POINTS_ORPHELINS" ]] || \
    echo "       point sans verdict declare:$POINTS_ORPHELINS" >&2
  exit 2
fi
unset _v POINTS_MANQUANTS POINTS_ORPHELINS

# LES POINTS QUE CE HARNAIS SAIT EMETTRE — ECRITS EN TOUTES LETTRES.
#
# La premiere redaction disait `esc_points_declares "${POINT_DE[@]}"`. C'est
# correct a l'execution et ILLISIBLE POUR LE PRE-VOL, qui lit le fichier sans
# l'executer: il n'y voyait que le texte de l'expansion, ne trouvait aucun
# point, et a refuse les quatre controles PC — a juste titre. Une declaration
# que le pre-vol ne peut pas lire n'est pas une declaration.
esc_points_declares PC1 PC2 PC3 PC4 \
    matrice-avant matrice-apres login-ordinaire migrateur-createur \
    migrateur-sans-admin migrateur-createrole role-deploiement \
    proprietaire-base transitivite reconnexion rejeu-des-migrations \
    ecriture-reelle admin-option-borne egalite-declaree-reelle \
    graphe-cartographie admin-non-vacuite createrole-ne-reintegre-pas \
    plan-racine-externe

# ET LES DEUX LISTES NE PEUVENT PAS DIVERGER. Ecrire les points deux fois —
# une fois comme valeurs de `POINT_DE`, une fois pour le pre-vol — ouvre
# exactement le genre d'ecart que ce harnais existe pour interdire ailleurs.
POINTS_DIVERGENTS=""
for _v in "${POINT_DE[@]}"; do
  case "$ESC_POINTS_DECLARES" in
    *" $_v "*) ;;
    *) POINTS_DIVERGENTS="$POINTS_DIVERGENTS $_v" ;;
  esac
done
if [[ -n "$POINTS_DIVERGENTS" ]]; then
  echo "REFUS: point(s) de POINT_DE absents de esc_points_declares:" >&2
  echo "      $POINTS_DIVERGENTS" >&2
  exit 2
fi
unset _v POINTS_DIVERGENTS

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }
rouge()  { verdict "$1" ROUGE "${@:2}"
           esc_point_rouge "${POINT_DE[$1]}" nature=frontiere_ouverte \
             detail="$1: ${*:2}"; }
sur()    { verdict "$1" SUR   "${@:2}"; }
troue()  { verdict "$1" NON_PARCOURU "${@:2}"
           esc_point_troue "${POINT_DE[$1]}" "$1: ${*:2}"; }

MIG="${PREFIXE}_mf_${JETON}"; CTL="${PREFIXE}_cf_${JETON}"
SVC="${PREFIXE}_sf_${JETON}"; ORD="${PREFIXE}_of_${JETON}"
TIERS="${PREFIXE}_tf_${JETON}"; BASE="${PREFIXE}_df_${JETON}"
# Le pont de la chaine d'ADMIN. Il est nomme ICI et non a l'endroit ou il
# sert: un role cree en cours de route et detruit sur la meme ligne fuit des
# qu'un signal passe entre les deux.
PONT="${PREFIXE}_pf_${JETON}"
# UN SECOND LOGIN DECLARE, et un role a lui: `$TIERS` sert deja de cobaye aux
# controles qui doivent le voir REFUSE, et lui accorder le backend rendrait
# leur verdict faux. Deux roles distincts pour deux questions distinctes.
# Son nom trie AVANT celui du service (« _gf_ » < « _sf_ »), ce dont l'egalite
# declaree/reelle depend: elle compare une chaine declaree a un `string_agg`
# ordonne par nom.
DECL2="${PREFIXE}_gf_${JETON}"
MDP="FICTIF-rf-${JETON}"
MANDAT="00000000-0000-0000-0000-000000000000:FICTIF-EMPREINTE-FRONTIERE-${JETON}"

adm()   { psql -X -q -d postgres "$@"; }
admb()  { psql -X -q -d "$BASE" "$@"; }
mig()   { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
migp()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
ctl()   { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
ordp()  { PGUSER="$ORD" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
svcb()  { PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
q()     { admb -tAc "$1" 2>&1 | tr -d ' '; }

CIBLE=eurostruct_authority_backend
# `pg_has_role(...)::text` rend « true »/« false », PAS « t »/« f ». Comparer a
# « f/f/f » rendait tout rouge alors que rien n'etait ouvert — un faux rouge
# est aussi trompeur qu'un faux vert, et celui-ci a ete mesure.
FERME="false/false/false"

# La matrice, telle que PostgreSQL la porte: les trois options, pas une seule.
matrice() {
  admb -tA <<SQL
select coalesce(string_agg(l, E'\n' order by l), '(aucune appartenance)') from (
  select m.rolname || ' -> ' || r.rolname
         || '  admin=' || a.admin_option::text
         || ' inherit=' || a.inherit_option::text
         || ' set=' || a.set_option::text as l
    from pg_auth_members a
    join pg_roles r on r.oid = a.roleid
    join pg_roles m on m.oid = a.member
   where r.rolname = '$CIBLE'
) s
SQL
}

# `pg_has_role` resume ce que la matrice detaille: on garde les deux.
atteint() {  # atteint <role> -> "usage/set/member"
  q "select pg_has_role('$1','$CIBLE','USAGE')::text || '/'
         || pg_has_role('$1','$CIBLE','SET')::text || '/'
         || pg_has_role('$1','$CIBLE','MEMBER')::text"
}

# ADMIN OPTION SE LIT DANS `pg_auth_members`, PAS DANS `pg_has_role`.
a_admin() {  # a_admin <role> -> t|f
  q "select coalesce((select a.admin_option from pg_auth_members a
                        join pg_roles r on r.oid = a.roleid
                        join pg_roles m on m.oid = a.member
                       where r.rolname='$CIBLE' and m.rolname='$1'), false)::text"
}

NETTOYAGE_KO=0
sortie_propre() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" \
           "$MIG" "$CTL" "$SVC" "$ORD" "$TIERS" "$PONT" "$DECL2"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "authority_role_frontier.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" \
    "$MIG" "$CTL" "$SVC" "$ORD" "$TIERS" "$PONT" "$DECL2" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: le migrateur peut-il atteindre le backend d'autorite ?"

# --------------------------------------------------------------------------
# DECOR
# --------------------------------------------------------------------------
creer_role "$MIG"   "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL"   "login password '$MDP' createrole"          || exit 1
creer_role "$SVC"   "login password '$MDP'"                     || exit 1
creer_role "$ORD"   "login password '$MDP'"                     || exit 1
creer_role "$TIERS" "login password '$MDP'"                     || exit 1
creer_role "$DECL2" "login password '$MDP'"                     || exit 1
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

# ---------------------------------------------------- 1. LA MATRICE, AVANT
echo "      -- matrice-avant: l'etat des appartenances avant la phase 0"
AVANT="$(q "select count(*) from pg_roles where rolname = '$CIBLE'")"
detail "le role « $CIBLE » existe avant la phase 0: $AVANT (0 attendu)"
if [[ "$AVANT" == "0" ]]; then
  sur matrice-avant "le backend d'autorite n'existe pas avant le sceau:"
  detail "aucune appartenance ne peut donc preexister."
else
  rouge matrice-avant "le backend d'autorite existe deja avant la phase 0."
fi

if ! SORTIE=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
  echoue "phase 0 refusee: $(grep -m1 ERROR <<<"$SORTIE" | cut -c1-160)"
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
          set eurostruct.authority_backend_logins = '$DECL2,$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1

for f in "$DB_DIR"/migrations/*.sql; do
  if ! esc_appliquer_migration "$f" mig; then
    echoue "phase 1 refusee sur $(basename "$f"):"
    esc_diag_rapporter "phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
[[ "$ETAT" == "ACTIVE" ]] || { echoue "la base n'est pas ACTIVE ($ETAT)"; exit 1; }
# LE LOGIN DE SERVICE RECOIT LE ROLE D'EXECUTION, par le plan de controle qui
# seul en detient l'ADMIN — c'est ce que fait un deploiement reel. Sans cela,
# l'egalite « declare == reel » serait vraie par VACUITE: personne d'un cote,
# personne de l'autre.
ctlp -c "grant $CIBLE to \"$SVC\";" >/dev/null 2>&1
ctlp -c "grant $CIBLE to \"$DECL2\";" >/dev/null 2>&1

# ---------------------------------------------------- 2. LA MATRICE, APRES
echo "      -- matrice-apres: qui atteint le backend, et comment"
echo "$(matrice)" | sed 's/^/                /'
detail "migrateur   usage/set/member = $(atteint "$MIG")   admin=$(a_admin "$MIG")"
detail "plan        usage/set/member = $(atteint "$CTL")   admin=$(a_admin "$CTL")"
detail "service     usage/set/member = $(atteint "$SVC")   admin=$(a_admin "$SVC")"
detail "deploiement usage/set/member = $(atteint eurostruct_deployment)   admin=$(a_admin eurostruct_deployment)"
MIG_USAGE="$(atteint "$MIG")"
if [[ "$MIG_USAGE" == "$FERME" ]]; then
  sur matrice-apres "apres migration, le migrateur n'a NI usage, NI set,"
  detail "NI appartenance au backend d'autorite."
else
  rouge matrice-apres "le migrateur atteint le backend: $MIG_USAGE"
fi

# ------------------------------------------------- 3. LOGIN ORDINAIRE
echo "      -- login-ordinaire: un login sans droit peut-il s'enroler ?"
R="$(ordp -tAc "grant $CIBLE to current_user" 2>&1)"
A="$(atteint "$ORD")"
detail "tentative: $(head -c 90 <<<"$R" | tr '\n' ' ') ; apres: $A"
if [[ "$A" != "$FERME" ]]; then
  rouge login-ordinaire "un login ordinaire s'est enrole."
elif grep -qiE "permission denied|must have admin|droit" <<<"$R"; then
  sur login-ordinaire "un login ordinaire ne peut pas s'enroler."
else
  troue login-ordinaire "resultat non interpretable: $(head -c 80 <<<"$R")"
fi

# --------------------------------- 4. LE MIGRATEUR N'A PAS CREE LE ROLE
echo "      -- migrateur-createur: qui a cree le role detient l'ADMIN"
CREATEUR="$(q "select coalesce(string_agg(m.rolname, ','), '(personne)')
                 from pg_auth_members a
                 join pg_roles r on r.oid = a.roleid
                 join pg_roles m on m.oid = a.member
                where r.rolname = '$CIBLE' and a.admin_option")"
detail "detiennent l'ADMIN sur le backend: $CREATEUR"
if [[ "$CREATEUR" == "$CTL" ]]; then
  sur migrateur-createur "seul le plan de controle detient l'ADMIN: c'est lui"
  detail "qui cree le role en phase 0, et le migrateur n'y peut rien."
elif grep -q "$MIG" <<<"$CREATEUR"; then
  rouge migrateur-createur "le MIGRATEUR detient l'ADMIN sur le backend:"
  detail "il peut enroler qui il veut. C'est la contenance rouverte."
else
  troue migrateur-createur "detenteurs inattendus: $CREATEUR"
fi

# ------------------------------- 5. LE MIGRATEUR, AVEC SON SEUL CREATEROLE
echo "      -- migrateur-createrole: CREATEROLE suffit-il a rouvrir la porte ?"
R1="$(migp -tAc "grant $CIBLE to \"$MIG\"" 2>&1)"
R2="$(migp -tAc "grant $CIBLE to \"$TIERS\"" 2>&1)"
A1="$(atteint "$MIG")"; A2="$(atteint "$TIERS")"
detail "auto-enrolement: $(head -c 70 <<<"$R1" | tr '\n' ' ') -> $A1"
detail "enroler un tiers: $(head -c 70 <<<"$R2" | tr '\n' ' ') -> $A2"
if [[ "$A1" != "$FERME" || "$A2" != "$FERME" ]]; then
  rouge migrateur-createrole "CREATEROLE a suffi: le migrateur s'est enrole"
  detail "ou a enrole un tiers. Le point est BLOQUANT."
elif grep -qiE "permission denied|must have admin" <<<"$R1$R2"; then
  sur migrateur-createrole "CREATEROLE seul ne permet ni de s'enroler ni"
  detail "d'enroler un tiers: PostgreSQL 16 exige l'ADMIN OPTION, que seul"
  detail "le createur du role detient — et c'est le plan de controle."
else
  troue migrateur-createrole "non interpretable: $(head -c 70 <<<"$R1")"
fi

# --------------------------- 6. LE MIGRATEUR APRES RETRAIT DE SON ADMIN
# Il n'en a pas sur la cible; on eprouve la propriete SUR UN ROLE QU'IL A
# CREE, pour montrer que le retrait d'ADMIN ferme bien la porte — sinon ce
# controle serait satisfait par un migrateur qui n'a jamais rien pu faire.
echo "      -- migrateur-sans-admin: retirer l'ADMIN ferme-t-il la porte ?"
migp -tAc "create role ${MIG}_fils nologin" >/dev/null 2>&1
registre_role "${MIG}_fils"
AV="$(q "select coalesce((select a.admin_option from pg_auth_members a
            join pg_roles r on r.oid=a.roleid join pg_roles m on m.oid=a.member
           where r.rolname='${MIG}_fils' and m.rolname='$MIG'), false)::text")"
G1="$(migp -tAc "grant ${MIG}_fils to \"$TIERS\"" 2>&1)"
P1="$(q "select pg_has_role('$TIERS','${MIG}_fils','MEMBER')::text")"
# LE RETRAIT SE FAIT PAR LE GRANTOR, ET C'EST UNE MESURE, PAS UN DETAIL.
#
# Sur PostgreSQL 16, `REVOKE <role> FROM <membre>` emis par quelqu'un qui n'est
# PAS le grantor de cette appartenance emet un WARNING et NE FAIT RIEN:
#
#   WARNING: role "X" has not been granted membership in role "Y"
#            by role "postgres"
#   REVOKE ROLE
#
# ...et X reste membre. C'est la meme famille de piege que le GRANT sans
# droit, deja rencontree quatre fois dans ce jalon: une commande qui se
# contente d'un avertissement laisse croire qu'elle a agi. Une premiere
# version de ce controle revoquait sous `postgres`, l'appartenance survivait,
# et le controle concluait a tort que l'ADMIN ne gouvernait pas l'enrolement.
#
# L'appartenance du TIERS a ete creee par le MIGRATEUR: c'est donc lui qui la
# retire. Le retrait de l'ADMIN, lui, porte sur une appartenance dont le
# grantor est l'administrateur, et se fait sous `adm`.
migp -tAc "revoke ${MIG}_fils from \"$TIERS\"" >/dev/null 2>&1
adm -c "revoke admin option for ${MIG}_fils from \"$MIG\"" >/dev/null 2>&1
G2="$(migp -tAc "grant ${MIG}_fils to \"$TIERS\"" 2>&1)"
P2="$(q "select pg_has_role('$TIERS','${MIG}_fils','MEMBER')::text")"
detail "ADMIN a la creation: $AV ; enrolement avant retrait: $P1 ; apres: $P2"
if [[ "$AV" == "true" && "$P1" == "true" && "$P2" == "false" ]] \
   && grep -qiE "permission denied|must have admin" <<<"$G2"; then
  sur migrateur-sans-admin "l'ADMIN OPTION est bien ce qui autorise a enroler,"
  detail "et son retrait ferme la porte. Non-vacuite: avant le retrait, le"
  detail "meme GRANT reussissait."
else
  rouge migrateur-sans-admin "l'ADMIN OPTION ne gouverne pas l'enrolement"
  detail "comme attendu (avant=$P1 apres=$P2, $(head -c 60 <<<"$G2"))."
fi
adm -c "drop role if exists ${MIG}_fils" >/dev/null 2>&1

# ------------------------------------------------ 7. LE ROLE DE DEPLOIEMENT
echo "      -- role-deploiement: le deploiement atteint-il le backend ?"
AD="$(atteint eurostruct_deployment)"
ADM_D="$(a_admin eurostruct_deployment)"
detail "eurostruct_deployment: usage/set/member = $AD ; admin = $ADM_D"
if [[ "$AD" == "$FERME" && "$ADM_D" != "true" ]]; then
  sur role-deploiement "le role de deploiement n'atteint pas le backend"
  detail "d'autorite et ne peut y enroler personne."
else
  rouge role-deploiement "le role de deploiement atteint le backend ($AD,"
  detail "admin=$ADM_D): deployer donnerait le droit d'ecrire."
fi

# -------------------------------------------------- 8. PROPRIETAIRE DE BASE
echo "      -- proprietaire-base: posseder la base ouvre-t-il le role ?"
PROP="$(q "select pg_get_userbyid(datdba) from pg_database where datname='$BASE'")"
AP="$(atteint "$PROP")"
detail "proprietaire de la base: $PROP ; usage/set/member = $AP"
if [[ "$AP" == "$FERME" ]]; then
  sur proprietaire-base "posseder la base n'ouvre aucun acces au backend."
  detail "non-vacuite: le proprietaire est bien « $PROP », pas un tiers."
else
  rouge proprietaire-base "le proprietaire de la base atteint le backend: $AP"
fi

# ------------------------------------------------------- 9. TRANSITIVITE
# Le migrateur cree un role, se l'accorde, et on regarde si une chaine peut
# le mener au backend. C'est le chemin que `pg_has_role` couvre et qu'un
# simple examen de `pg_auth_members` raterait.
echo "      -- transitivite: une chaine d'appartenances mene-t-elle au backend ?"
migp -tAc "create role ${MIG}_pont nologin" >/dev/null 2>&1
registre_role "${MIG}_pont"
migp -tAc "grant ${MIG}_pont to \"$MIG\"" >/dev/null 2>&1
GP="$(migp -tAc "grant $CIBLE to ${MIG}_pont" 2>&1)"
AT="$(atteint "$MIG")"
detail "pont cree et accorde au migrateur ; greffe du backend sur le pont:"
detail "$(head -c 90 <<<"$GP" | tr '\n' ' ') ; migrateur -> $AT"
if [[ "$AT" == "$FERME" ]]; then
  sur transitivite "aucune chaine d'appartenances ne mene au backend: la"
  detail "greffe est refusee a la racine, faute d'ADMIN sur la cible."
else
  rouge transitivite "une chaine mene au backend: $AT"
fi
adm -c "drop role if exists ${MIG}_pont" >/dev/null 2>&1

# -------------------------------------------------------- 10. RECONNEXION
# Une appartenance acquise ne prend qu'a la session suivante: si un chemin
# existait, il pourrait n'apparaitre qu'apres reconnexion.
echo "      -- reconnexion: l'etat change-t-il apres une nouvelle session ?"
AR1="$(atteint "$MIG")"
AR2="$(migp -tAc "select pg_has_role(current_user,'$CIBLE','USAGE')::text ||'/'||
                         pg_has_role(current_user,'$CIBLE','SET')::text ||'/'||
                         pg_has_role(current_user,'$CIBLE','MEMBER')::text" 2>&1 | tr -d ' ')"
detail "vu par l'administrateur: $AR1 ; vu par le migrateur lui-meme: $AR2"
if [[ "$AR1" == "$FERME" && "$AR2" == "$FERME" ]]; then
  sur reconnexion "une session neuve du migrateur ne voit aucun acces."
else
  rouge reconnexion "l'acces apparait a la reconnexion: $AR1 / $AR2"
fi

# ------------------------------------- 11. REGLAGES PUIS REJEU DES MIGRATIONS
# `pg_db_role_setting` peut PORTER une configuration; il ne doit jamais
# DECLENCHER un GRANT. On declare le migrateur comme backend et on rejoue les
# migrations: rien ne doit lui etre accorde.
echo "      -- rejeu-des-migrations: un reglage se transforme-t-il en membership ?"
adm -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$SVC,$MIG';" >/dev/null 2>&1
for f in "$DB_DIR"/migrations/*.sql; do
  esc_appliquer_migration "$f" mig >/dev/null 2>&1
done
AJ="$(atteint "$MIG")"
detail "apres declaration du migrateur et rejeu: $AJ"
if [[ "$AJ" == "$FERME" ]]; then
  sur rejeu-des-migrations "declarer un login dans le reglage ne lui accorde"
  detail "RIEN: la configuration ne fabrique pas d'appartenance."
else
  rouge rejeu-des-migrations "un reglage s'est transforme en appartenance: $AJ"
fi
adm -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$DECL2,$SVC';" >/dev/null 2>&1

# --------------------------------------------------- 12. ECRITURE REELLE
# LA QUESTION FINALE N'EST PAS « EST-IL MEMBRE », C'EST « ECRIT-IL ». Tous
# les controles ci-dessus mesurent des catalogues; celui-ci mesure l'effet.
echo "      -- ecriture-reelle: le migrateur ecrit-il, apres toutes ses tentatives ?"
W="$(mig -tAc "insert into normative_authorisation_grants
                 (grantee_id, grantee_name, permission, country_code,
                  standard_family, part, reason)
               values (gen_random_uuid(), 'FICTIF frontiere',
                       'can_validate_normative_reference', 'BE', 'EN 1992',
                       '1-1', 'FICTIF tentative du migrateur')" 2>&1)"
N="$(q "select count(*) from normative_authorisation_grants
         where reason = 'FICTIF tentative du migrateur'")"
detail "insertion par le migrateur: $(head -c 90 <<<"$W" | tr '\n' ' ') ; lignes: $N"
if [[ "$N" != "0" ]]; then
  rouge ecriture-reelle "le migrateur a ECRIT dans les tables d'autorite."
elif grep -qiE "permission denied|policy|denied" <<<"$W"; then
  sur ecriture-reelle "le migrateur n'ecrit pas, et le refus est un refus de"
  detail "droit — pas une erreur de forme."
else
  troue ecriture-reelle "refus non interpretable: $(head -c 80 <<<"$W")"
fi

# ------------------------------------------------ 13. L'ADMIN EST BORNE
echo "      -- admin-option-borne: qui peut enroler, exactement ?"
ADMINS="$(q "select coalesce(string_agg(m.rolname, ','), '(personne)')
               from pg_auth_members a
               join pg_roles r on r.oid = a.roleid
               join pg_roles m on m.oid = a.member
              where r.rolname = '$CIBLE' and a.admin_option
                and not m.rolsuper")"
detail "detenteurs non superutilisateurs de l'ADMIN: $ADMINS"
if [[ "$ADMINS" == "$CTL" ]]; then
  sur admin-option-borne "un seul role non superutilisateur peut enroler: le"
  detail "plan de controle. L'absence d'INHERIT et de SET ne suffirait pas —"
  detail "c'est l'ADMIN qui gouverne l'enrolement, et il est borne."
else
  rouge admin-option-borne "l'ADMIN est detenu par: $ADMINS"
fi

# ------------------------ 14. EGALITE EXACTE ENTRE DECLARE ET REEL
echo "      -- egalite-declaree-reelle: ni membre en trop, ni membre en moins"
DECL="$(q "select coalesce(valeur,'') from normative_authentication_contract
            where nom = 'eurostruct.authority_backend_logins'")"
REEL="$(q "select coalesce(string_agg(m.rolname, ',' order by m.rolname), '')
             from pg_roles m
            where not m.rolsuper and m.rolname <> '$CIBLE'
              and (pg_has_role(m.rolname,'$CIBLE','USAGE')
                   or pg_has_role(m.rolname,'$CIBLE','SET'))")"
detail "declare (fige par 0013): « $DECL »"
detail "reel (usage ou set)     : « $REEL »"
R14="$(ctl -tAc "select assert_authority_backend_membership()" 2>&1)"
if [[ "$DECL" == "$REEL" ]] && ! grep -qiE "ERROR|ERREUR" <<<"$R14"; then
  sur egalite-declaree-reelle "l'ensemble reel est EXACTEMENT l'ensemble"
  detail "declare: aucun membre en trop, aucun en moins."
elif [[ "$DECL" != "$REEL" ]]; then
  rouge egalite-declaree-reelle "declare et reel different."
  detail "declare « $DECL » ; reel « $REEL »"
else
  rouge egalite-declaree-reelle "la postcondition refuse: $(head -c 120 <<<"$R14")"
fi

# ==========================================================================
# LA POSTCONDITION EST-ELLE AUTRE CHOSE QU'UN VERT PERMANENT ?
# ==========================================================================
# LES TROIS CONTROLES QUI SUIVENT NE MESURENT PAS LE PRODUIT, ILS MESURENT
# L'INSTRUMENT. `assert_authority_backend_membership()` vient de rendre un
# vert; une assertion qui rend toujours vert rend le meme vert. On lui
# presente donc, une par une, les trois formes qu'elle est censee refuser, et
# on exige d'elle un refus NOMME — puis on defait, et on exige le RETOUR au
# vert. Sans ce retour, le refus pourrait n'etre qu'une base cassee.
#
# AUCUNE DES TROIS N'EST HYPOTHETIQUE: la premiere est le defaut d'origine
# (le membre reel n'etait pas celui de la liste declaree), la deuxieme est le
# chemin que `pg_has_role('USAGE')` ne voit pas, la troisieme est la
# declaration devenue decorative.
postcondition() { ctl -tAc "select assert_authority_backend_membership()" 2>&1; }

echo "      -- postcondition-membre-en-trop: un membre non declare est-il vu ?"
ctlp -c "grant $CIBLE to \"$ORD\";" >/dev/null 2>&1
PT="$(postcondition)"
ctlp -c "revoke $CIBLE from \"$ORD\";" >/dev/null 2>&1
PT_APRES="$(postcondition)"
detail "avec « $ORD » enrole: $(head -c 100 <<<"$PT" | tr '\n' ' ')"
if ! grep -q "SUPPLEMENTAIRE" <<<"$PT"; then
  rouge postcondition-membre-en-trop "PC1. un membre non declare n'a PAS ete refuse:"
  detail "$(head -c 140 <<<"$PT")"
elif grep -qiE "ERROR|ERREUR" <<<"$PT_APRES"; then
  rouge postcondition-membre-en-trop "PC1. apres retrait, la postcondition refuse"
  detail "toujours: le refus ci-dessus ne prouve donc rien."
  detail "$(head -c 110 <<<"$PT_APRES")"
else
  sur postcondition-membre-en-trop "un membre non declare est refuse, nomme"
  detail "« membre SUPPLEMENTAIRE », et le retrait rend le vert."
fi

echo "      -- postcondition-admin-direct: l'ADMIN seul, en ligne directe"
# LA CONTRIBUTION PROPRE DE LA LECTURE LIGNE A LIGNE, isolee. Ce membre-ci
# detient l'ADMIN et RIEN d'autre: `pg_has_role('USAGE')` et `('SET')`
# repondent « false », donc les deux boucles anterieures ne le voient pas —
# et il n'y a aucune chaine, donc la couche transitive ne le voit pas non
# plus. Si ce cas passe, c'est exactement le chemin par lequel la contenance
# s'etait rouverte: administrer sans utiliser, puis s'octroyer l'usage.
ctlp -c "grant $CIBLE to \"$ORD\" with admin option, inherit false, set false;" \
  >/dev/null 2>&1
PA_VU="$(atteint "$ORD")"
PA_ADM="$(a_admin "$ORD")"
PA="$(postcondition)"
ctlp -c "revoke $CIBLE from \"$ORD\";" >/dev/null 2>&1
PA_APRES="$(postcondition)"
detail "« $ORD » usage/set/member=$PA_VU ; admin=$PA_ADM"
detail "refus: $(head -c 90 <<<"$PA" | tr '\n' ' ')"
if [[ "$PA_ADM" != "true" ]]; then
  troue postcondition-admin-direct "l'ADMIN n'a pas ete accorde: le scenario"
  detail "n'a pas ete pose, rien n'a ete eprouve."
elif ! grep -q "sans etre le plan de controle fige" <<<"$PA"; then
  rouge postcondition-admin-direct "PC4. un porteur d'ADMIN en ligne directe, sans"
  detail "INHERIT ni SET, n'a PAS ete refuse: $(head -c 130 <<<"$PA")"
elif grep -qiE "ERROR|ERREUR" <<<"$PA_APRES"; then
  rouge postcondition-admin-direct "PC4. apres retrait, la postcondition refuse"
  detail "toujours: $(head -c 110 <<<"$PA_APRES")"
else
  sur postcondition-admin-direct "l'ADMIN seul est refuse, et le diagnostic"
  detail "renvoie au plan de controle fige. usage/set le disaient absent."
fi

echo "      -- postcondition-admin-en-chaine: l'ADMIN transitif est-il vu ?"
# CE CONTROLE A ETE CORRIGE APRES MESURE, ET LA CORRECTION EST LE SUJET.
#
# Premiere version: on accordait le backend a un PONT « with admin option,
# inherit false, set false », et on constatait un refus. Le refus etait bien
# la — mais il venait de la lecture LIGNE A LIGNE, qui voit ce porteur
# directement. La couche TRANSITIVE n'etait pas atteinte, et une mutation qui
# la retire aurait survecu. Le nom du controle disait « en chaine »; le
# scenario ne posait aucune chaine.
#
# CE QUI FAIT UNE VRAIE CHAINE. Un chemin transitif exige un role R qui
# detient l'ADMIN en ligne directe, plus quelqu'un qui est membre de R. Or le
# seul detenteur legitime est le PLAN DE CONTROLE — celui que la lecture
# ligne a ligne EXEMPTE. Enroler un tiers dans le plan de controle lui donne
# donc l'ADMIN sur le backend SANS aucune ligne qui le nomme: c'est le seul
# cas que la couche transitive attrape et que l'autre laisse passer.
#
# C'est aussi une porte reelle: qui entre dans le plan de controle peut
# enroler qui il veut dans le role qui detient INSERT sur les tables
# d'autorite.
creer_role "$PONT" "nologin" >/dev/null 2>&1
adm -c "grant \"$CTL\" to \"$PONT\" with inherit true, set true;" >/dev/null 2>&1
PC_ATT="$(q "select pg_has_role('$PONT','$CIBLE','MEMBER WITH ADMIN OPTION')::text")"
PC_LIGNE="$(q "select count(*) from pg_auth_members a
                 join pg_roles r on r.oid = a.roleid
                 join pg_roles m on m.oid = a.member
                where r.rolname='$CIBLE' and m.rolname='$PONT'")"
PC="$(postcondition)"
adm -c "revoke \"$CTL\" from \"$PONT\";" >/dev/null 2>&1
PC_APRES="$(postcondition)"
detail "le pont atteint l'ADMIN transitivement: $PC_ATT ;"
detail "lignes de pg_auth_members qui le nomment sur le backend: $PC_LIGNE (0 attendu)"
detail "refus: $(head -c 90 <<<"$PC" | tr '\n' ' ')"
if [[ "$PC_ATT" != "true" || "$PC_LIGNE" != "0" ]]; then
  troue postcondition-admin-en-chaine "la chaine n'a pas ete posee comme"
  detail "annonce (transitif=$PC_ATT, lignes directes=$PC_LIGNE): rien n'a"
  detail "ete eprouve, et surtout pas la couche transitive."
elif ! grep -q "par une chaine" <<<"$PC"; then
  rouge postcondition-admin-en-chaine "PC2. un porteur d'ADMIN par CHAINE n'a PAS"
  detail "ete refuse par la couche transitive: $(head -c 140 <<<"$PC")"
elif grep -qiE "ERROR|ERREUR" <<<"$PC_APRES"; then
  rouge postcondition-admin-en-chaine "PC2. apres retrait, la postcondition refuse"
  detail "toujours: $(head -c 110 <<<"$PC_APRES")"
else
  sur postcondition-admin-en-chaine "un ADMIN atteint par une CHAINE est refuse,"
  detail "alors qu'AUCUNE ligne de pg_auth_members ne nomme ce role sur le"
  detail "backend. La lecture ligne a ligne ne pouvait pas le voir."
fi

echo "      -- postcondition-declare-absent: une declaration decorative est-elle vue ?"
# LE SENS INVERSE DE L'EGALITE: celui qui n'ouvre aucune porte, mais qui rend
# la configuration inintelligible — la liste nomme un acteur, le catalogue dit
# qu'il ne peut rien. La base est ACTIVE: c'est la que l'exigence a un sens.
#
# LA DECLARATION NE PEUT PAS ETRE MODIFIEE POUR POSER LE SCENARIO, et c'est
# une GARANTIE: `normative_authentication_contract` est figee a la migration
# par un declencheur d'immuabilite. Une premiere version de ce controle
# essayait d'y ajouter un nom, echouait, et rendait NON_PARCOURU — le
# scenario n'etait pas pose, donc rien n'etait eprouve.
#
# ON PREND DONC L'ECART PAR L'AUTRE BOUT: la declaration reste ce qu'elle est
# (deux logins, figes), et c'est L'APPARTENANCE qu'on retire. L'ecart est le
# meme — un declare qui n'atteint pas le backend — et il est atteignable.
ETAT_PD="$(q "select normative_activation_state()")"
DECL_PD="$(q "select coalesce(valeur,'') from normative_authentication_contract
               where nom = 'eurostruct.authority_backend_logins'")"
ctlp -c "revoke $CIBLE from \"$DECL2\";" >/dev/null 2>&1
PD_ATT="$(atteint "$DECL2")"
PD="$(postcondition)"
ctlp -c "grant $CIBLE to \"$DECL2\";" >/dev/null 2>&1
PD_APRES="$(postcondition)"
detail "etat: $ETAT_PD ; declare (fige): « $DECL_PD »"
detail "« $DECL2 » apres retrait de l'appartenance: $PD_ATT"
detail "refus: $(head -c 90 <<<"$PD" | tr '\n' ' ')"
if [[ "$ETAT_PD" != "ACTIVE" ]]; then
  troue postcondition-declare-absent "la base n'est pas ACTIVE: l'exigence ne"
  detail "s'applique pas, et le controle n'a rien parcouru."
elif [[ "$DECL_PD" != *"$DECL2"* ]]; then
  troue postcondition-declare-absent "« $DECL2 » n'est pas dans la declaration"
  detail "figee: le scenario n'a pas pu etre pose."
elif [[ "$PD_ATT" != "$FERME" ]]; then
  troue postcondition-declare-absent "le retrait de l'appartenance n'a pas pris"
  detail "($PD_ATT): l'ecart n'a donc jamais existe, rien n'a ete eprouve."
elif ! grep -q "DECLARE mais n" <<<"$PD"; then
  rouge postcondition-declare-absent "PC3. une declaration sans appartenance passe:"
  detail "$(head -c 140 <<<"$PD")"
elif grep -qiE "ERROR|ERREUR" <<<"$PD_APRES"; then
  rouge postcondition-declare-absent "PC3. apres remise de l'appartenance, la"
  detail "postcondition refuse toujours: $(head -c 100 <<<"$PD_APRES")"
else
  sur postcondition-declare-absent "un login declare qui n'atteint pas le"
  detail "backend est refuse quand la base est ACTIVE, et la remise de"
  detail "l'appartenance rend le vert."
fi

# ==========================================================================
# LE GRAPHE ADMIN, EN ENTIER — et ce que chaque arete confere REELLEMENT
# ==========================================================================
# CE QUI PRECEDE INTERROGE DES ROLES UN PAR UN. Une frontiere ne se lit pas
# role par role: elle se lit sur le GRAPHE. Une arete anodine — « X est membre
# de Y » — devient une capacite des que Y detient l'ADMIN sur le backend, et
# aucun controle vise sur X ne le voit.
#
# LA CARTOGRAPHIE PORTE LE DONNEUR. `pg_auth_members.grantor` decide qui peut
# REVOQUER: un octroi pose par A ne se retire que par A (fait mesure dans ce
# jalon, cinquieme forme du piege « WARNING sans effet »). Une carte qui
# l'omet ne permet pas de repondre a « comment defait-on ceci ? ».
echo "      -- graphe-cartographie: toutes les aretes, et leur portee reelle"
CARTE="$(admb -tA <<SQL
select coalesce(string_agg(l, E'\n' order by l), '(aucune arete)') from (
  select m.rolname || ' -> ' || r.rolname
         || ' | donneur=' || pg_get_userbyid(a.grantor)
         || ' | admin=' || a.admin_option::text
         || ' inherit=' || a.inherit_option::text
         || ' set=' || a.set_option::text
         || ' | atteint le backend: usage=' 
         || pg_has_role(m.rolname, '$CIBLE', 'USAGE')::text
         || ' set=' || pg_has_role(m.rolname, '$CIBLE', 'SET')::text
         || ' admin=' || pg_has_role(m.rolname, '$CIBLE',
                                     'MEMBER WITH ADMIN OPTION')::text as l
    from pg_auth_members a
    join pg_roles r on r.oid = a.roleid
    join pg_roles m on m.oid = a.member
   where not m.rolsuper
) s
SQL
)"
echo "$CARTE" | sed 's/^/                /'
# L'ENSEMBLE TRANSITIF EFFECTIF — celui qui compte, et non les lignes qui
# nomment directement le backend.
TRANSITIF="$(q "select coalesce(string_agg(p.rolname, ',' order by p.rolname), '(personne)')
                  from pg_roles p
                 where not p.rolsuper and p.rolname <> '$CIBLE'
                   and (pg_has_role(p.rolname,'$CIBLE','USAGE')
                        or pg_has_role(p.rolname,'$CIBLE','SET')
                        or pg_has_role(p.rolname,'$CIBLE','MEMBER WITH ADMIN OPTION'))")"
detail "ensemble TRANSITIF atteignant le backend: $TRANSITIF"
ATTENDU_TRANSITIF="$(printf '%s\n' "$CTL" "$DECL2" "$SVC" | sort | paste -sd, -)"
detail "attendu: le plan de controle (ADMIN residuel) + les logins declares"
detail "         soit « $ATTENDU_TRANSITIF »"
if [[ "$TRANSITIF" == "$ATTENDU_TRANSITIF" ]]; then
  sur graphe-cartographie "l'ensemble TRANSITIF est exactement le plan de"
  detail "controle et les logins declares. Aucune arete detournee, aucun"
  detail "chemin indirect."
else
  rouge graphe-cartographie "GC1. l'ensemble transitif differe de l'attendu:"
  detail "reel     « $TRANSITIF »"
  detail "attendu  « $ATTENDU_TRANSITIF »"
fi

# --------------------------------------------------------------------------
# LA NON-VACUITE DU GRAPHE: un vrai ADMIN enrole-t-il vraiment ?
# --------------------------------------------------------------------------
# SANS CE CONTROLE, TOUT CE QUI PRECEDE POURRAIT ETRE VERT SUR UNE SCENE OU
# L'ADMIN NE CONFERE RIEN. « Personne ne peut enroler » et « enroler est
# impossible ici » se ressemblent beaucoup dans un journal, et ne disent pas
# du tout la meme chose.
echo "      -- admin-non-vacuite: un detenteur d'ADMIN enrole-t-il un tiers ?"
NV1="$(ctlp -tAc "grant $CIBLE to \"$TIERS\"" 2>&1)"
NV_APRES="$(atteint "$TIERS")"
ctlp -c "revoke $CIBLE from \"$TIERS\";" >/dev/null 2>&1
NV_RETOUR="$(atteint "$TIERS")"
detail "le plan de controle enrole « $TIERS »: $(head -c 60 <<<"$NV1" | tr '\n' ' ')"
detail "apres l'octroi: $NV_APRES ; apres retrait: $NV_RETOUR"
if [[ "$NV_APRES" == "$FERME" ]]; then
  rouge admin-non-vacuite "AN1. le detenteur de l'ADMIN n'a PAS pu enroler:"
  detail "la scene ne confere aucun pouvoir, et tous les refus mesures"
  detail "ci-dessus sont donc sans valeur."
elif [[ "$NV_RETOUR" != "$FERME" ]]; then
  rouge admin-non-vacuite "AN1. le retrait n'a pas pris: $NV_RETOUR"
else
  sur admin-non-vacuite "l'ADMIN confere REELLEMENT le pouvoir d'enroler:"
  detail "le plan de controle enrole un tiers ($NV_APRES), et le retire."
  detail "Les refus mesures plus haut portent donc sur un pouvoir reel."
fi

# --------------------------------------------------------------------------
# CREATEROLE NE REINTEGRE PAS LE PLAN DE CONTROLE
# --------------------------------------------------------------------------
# LE CHEMIN LE PLUS TENTANT, ET LE PLUS DISCRET. Le migrateur a CREATEROLE. Il
# ne peut pas s'accorder le backend — mesure plus haut. Mais peut-il entrer
# dans le PLAN DE CONTROLE, qui detient l'ADMIN ? Et, a defaut, creer un role
# neuf et l'y faire entrer ? Les deux mettraient l'ADMIN a un pas.
echo "      -- createrole-ne-reintegre-pas: le migrateur peut-il rejoindre le plan ?"
CR1="$(migp -tAc "grant \"$CTL\" to \"$MIG\"" 2>&1)"
CR_A="$(q "select pg_has_role('$MIG','$CTL','MEMBER')::text")"
CR_FILS="${JETON}_cr"
migp -tAc "create role \"$CR_FILS\" nologin" >/dev/null 2>&1
CR2="$(migp -tAc "grant \"$CTL\" to \"$CR_FILS\"" 2>&1)"
CR_B="$(q "select coalesce((select pg_has_role('$CR_FILS','$CTL','MEMBER')), false)::text")"
CR_BACKEND="$(q "select coalesce((select pg_has_role('$CR_FILS','$CIBLE','MEMBER WITH ADMIN OPTION')), false)::text")"
migp -tAc "drop role \"$CR_FILS\"" >/dev/null 2>&1
detail "auto-entree dans le plan: $(head -c 60 <<<"$CR1" | tr '\n' ' ') -> membre=$CR_A"
detail "role neuf entre dans le plan: $(head -c 60 <<<"$CR2" | tr '\n' ' ') -> membre=$CR_B"
detail "ce role neuf atteint-il l'ADMIN du backend ? $CR_BACKEND"
if [[ "$CR_A" == "true" || "$CR_B" == "true" || "$CR_BACKEND" == "true" ]]; then
  rouge createrole-ne-reintegre-pas "CR1. CREATEROLE permet de rejoindre le"
  detail "plan de controle, donc d'atteindre l'ADMIN du backend a un pas."
  detail "LE POINT EST BLOQUANT: la racine cesse d'etre externe."
else
  sur createrole-ne-reintegre-pas "CREATEROLE ne suffit ni a rejoindre le plan"
  detail "de controle, ni a y faire entrer un role neuf: PostgreSQL 16 exige"
  detail "l'ADMIN sur le role accorde, et le migrateur ne l'a pas sur le plan."
fi

# --------------------------------------------------------------------------
# LE PLAN DE CONTROLE EST UNE RACINE TECHNIQUE EXTERNE
# --------------------------------------------------------------------------
# CE QU'IL FAUT ETABLIR: son identite ne se decide pas depuis l'interieur. Ni
# un reglage de base, ni un role applicatif, ni le migrateur ne peuvent la
# designer ou la deplacer. Elle est FIGEE a la finalisation, par OID ET par
# nom, et le constat en est immuable.
echo "      -- plan-racine-externe: qui a fige le plan, et peut-on le deplacer ?"
PLAN_NOM="$(q "select coalesce(normative_control_plane(), '(aucun)')")"
PLAN_OID="$(q "select coalesce(normative_control_plane_oid()::text, '(aucun)')")"
PLAN_ATTENDU_OID="$(q "select oid::text from pg_roles where rolname = '$CTL'")"
# Le migrateur essaie de deplacer la racine par le seul chemin qui existerait:
# ecrire dans la table qui la porte.
PR1="$(mig -tAc "update normative_control_plane set role_name = '$MIG'" 2>&1)"
PR2="$(mig -tAc "insert into normative_control_plane (role_name) values ('$MIG')" 2>&1)"
PLAN_APRES="$(q "select coalesce(normative_control_plane(), '(aucun)')")"
detail "plan fige: « $PLAN_NOM » (oid $PLAN_OID) ; oid du role CTL: $PLAN_ATTENDU_OID"
detail "tentative UPDATE par le migrateur: $(head -c 70 <<<"$PR1" | tr '\n' ' ')"
detail "tentative INSERT par le migrateur: $(head -c 70 <<<"$PR2" | tr '\n' ' ')"
if [[ "$PLAN_NOM" != "$CTL" || "$PLAN_OID" != "$PLAN_ATTENDU_OID" ]]; then
  rouge plan-racine-externe "PE1. le plan fige n'est pas le role qui a"
  detail "reellement pose le sceau: « $PLAN_NOM » (oid $PLAN_OID)."
elif [[ "$PLAN_APRES" != "$PLAN_NOM" ]]; then
  rouge plan-racine-externe "PE1. la racine a ete DEPLACEE par le migrateur:"
  detail "« $PLAN_NOM » -> « $PLAN_APRES »"
elif ! grep -qiE "denied|refus|interdit|immuable|ERROR" <<<"$PR1$PR2"; then
  troue plan-racine-externe "ni deplacement ni refus interpretable: le"
  detail "scenario n'a rien etabli."
else
  sur plan-racine-externe "la racine est figee par OID ET par nom sur le role"
  detail "qui a reellement pose le sceau, et le migrateur ne peut ni la"
  detail "deplacer ni en designer une autre."
fi

# ==========================================================================
verdicts_verifier || true
verdicts_resume "6.3c — frontiere des roles PostgreSQL"

# LE CANAL EST CONCLU AVANT LES DEUX SORTIES, ET NON DANS L'UNE D'ELLES.
# Un point qui PASSE doit produire un SUR, et un point seulement troue son
# NON_PARCOURU: sans cela le lanceur lirait NOT_RUN — « pas mesure » — la ou
# il faut lire SURVIVED — « la garantie a ete retiree et rien n'a rougi ».
esc_conclure

if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Le migrateur n'atteint le backend d'autorite par aucun chemin ordinaire."
  exit 0
fi
exit 1
