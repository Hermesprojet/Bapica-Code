#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3c: LA FILIATION DES DELEGATIONS ET LA REVOCATION TRANSITIVE
#
#   db/test/authority_delegation_lineage.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# 6.3c avait consigne une decision — revocation NON transitive — au motif
# qu'une cascade retroactive invaliderait des signatures regulieres au moment
# ou elles ont ete apposees. L'argument confondait deux choses:
#
#   * ce qui a ete SIGNE reste signe. C'est l'immuabilite des tables qui le
#     garantit, et 0012 n'y touche pas.
#   * ce qui reste UTILISABLE apres le retrait d'une autorite est une autre
#     question. « Tout ce qu'elle avait delegue » est indefendable: retirer son
#     habilitation a un administrateur en laissant vivre les pouvoirs qu'il a
#     distribues ne retire rien.
#
# 0012 pose donc `parent_grant_id`, `expires_at`, et une efficacite
# TRANSITIVE. Ce harnais l'eprouve, et eprouve aussi ce qu'elle N'AUTORISE PAS.
#
# CE QUI EST MESURE
#   A -> B -> C, et la revocation de A
#   les autorites INDEPENDANTES (aucune reaffectation implicite)
#   les cycles A -> B -> A
#   l'expiration, et l'expiration d'un ancetre
#   la delegation PENDANT une revocation, sur barriere deterministe
#   deux revocations concurrentes
#   l'amplification de portee et l'elargissement par NULL
#
# LA COMPTABILITE EST CELLE DE `lib_harnais.sh`. Aucune identite reelle, base
# jetable verifiee avant toute ecriture.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: authority_delegation_lineage.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_delegation_lineage.sh" || exit 2
harnais_verrou_prendre  "authority_delegation_lineage.sh" || exit $?
exiger_cluster_jetable  "authority_delegation_lineage.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "authority_delegation_lineage.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  parent-obligatoire parent-detenu portee-incluse elargissement-null \
  permission-non-elevee chaine-abc revocation-transitive \
  autorite-independante pas-de-reaffectation cycle-abа \
  expiration expiration-ancetre delegation-pendant-revocation \
  revocations-concurrentes descendance-visible

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
est_uuid() {
  [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]
}
erreur_sql() { grep -qiE 'ERROR|ERREUR|FATAL' <<<"$1"; }

A="aaaaaaaa-0000-0000-0000-00000000000a"
B="bbbbbbbb-0000-0000-0000-00000000000b"
C="cccccccc-0000-0000-0000-00000000000c"
D="dddddddd-0000-0000-0000-00000000000d"
# Le principal preautorise par le mandat: c'est A qui sera amorce.
MANDAT_PRINCIPAL="$A"

decor_poser() {
  local f sortie m etat
  MIG="${PREFIXE}_ml_${JETON}"; CTL="${PREFIXE}_cl_${JETON}"
  SVC="${PREFIXE}_sl_${JETON}"; BASE="${PREFIXE}_dl_${JETON}"
  ORD="${PREFIXE}_ol_${JETON}"
  # LE MANDAT D'AMORCAGE, FICTIF. Forme « <principal>:<empreinte> ». Il tient
  # lieu, pour le test, de la decision prise hors du systeme; aucun document
  # reel n'existe et aucun n'est invente — l'empreinte est litteralement
  # marquee FICTIF.
  MANDAT="${MANDAT_PRINCIPAL}:FICTIF-EMPREINTE-DE-MANDAT-${JETON}"
  MDP="FICTIF-ln-${JETON}"
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
    echoue "decor: phase 0: $(grep -m1 ERROR <<<"$sortie" | cut -c1-160)"; return 1
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
      echoue "decor: phase 1 sur $(basename "$f"):"
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

# --------------------------------------------------------------------------
# BARRIERES DETERMINISTES — memes pieces que `authority_root_of_trust.sh`
# --------------------------------------------------------------------------
BARRIERES=(); BAR_FD=""; BAR_PID=""; BAR_APP=""; BAR_FIFO=""
CANAUX_RACINE="$(mktemp -d)"
CONCURRENTS=()

attendre() {
  local quoi="$1" sql="$2" i n
  for ((i = 0; i < 600; i++)); do
    n=$(admb -tAc "select ($sql)::int" 2>/dev/null | tr -d ' ')
    if [[ "$n" == "1" ]]; then
      BARRIERES+=("ATTEINTE|$quoi|essai=$((i + 1))"); return 0
    fi
    sleep 0.1
  done
  BARRIERES+=("JAMAIS_ATTEINTE|$quoi|essais=600")
  echoue "barriere jamais atteinte: $quoi"
  return 1
}

barriere_prendre() {
  local cle="$1"
  BAR_APP="FICTIF-bar-${cle}-${JETON}"
  BAR_FIFO="$CANAUX_RACINE/bar.$cle"
  mkfifo "$BAR_FIFO" || { echoue "barriere $cle: mkfifo refuse"; return 1; }
  PGAPPNAME="$BAR_APP" psql -X -q -d "$BASE" -f "$BAR_FIFO" >/dev/null 2>&1 &
  BAR_PID=$!
  exec {BAR_FD}>"$BAR_FIFO"
  printf 'select pg_advisory_lock(%s);\n' "$cle" >&"$BAR_FD"
  attendre "le harnais detient la barriere $cle" \
    "exists(select 1 from pg_locks l join pg_stat_activity a on a.pid = l.pid
             where l.locktype = 'advisory' and l.granted
               and a.application_name = '$BAR_APP')"
}

# LA LEVEE EST UN ORDRE EXPLICITE, PAS UN EOF. `exec {BAR_FD}>` alloue un
# descripteur ordinaire que les sous-shells lances ensuite heritent et que leur
# `psql` conserve: fermer celui du parent ne produit aucun EOF, le porteur ne
# sort pas, et les concurrents attendent une liberation qui exige leur propre
# sortie. Interblocage mesure dans /proc sur `authority_root_of_trust.sh`.
barriere_lever() {
  [[ -n "$BAR_FD" ]] || return 0
  printf 'select pg_advisory_unlock_all();\n\\q\n' >&"$BAR_FD" 2>/dev/null
  exec {BAR_FD}>&-
  wait "$BAR_PID" 2>/dev/null
  rm -f "$BAR_FIFO"
  BAR_FD=""; BAR_PID=""; BAR_FIFO=""
}

# JAMAIS UN `wait` NU: `harnais_verrou_prendre` retient le verrou du harnais
# dans un coprocessus qui vit toute l'execution, et `wait` sans argument
# l'attendrait aussi — indefiniment.
attendre_concurrents() {
  local p
  for p in "${CONCURRENTS[@]}"; do wait "$p" 2>/dev/null; done
  CONCURRENTS=()
}

NETTOYAGE_KO=0
sortie_propre() {
  local r
  [[ -z "$BAR_FD" ]]  || exec {BAR_FD}>&-
  [[ -z "$BAR_PID" ]] || kill "$BAR_PID" 2>/dev/null
  rm -rf "$CANAUX_RACINE"
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
  harnais_postcondition_nettoyage "authority_delegation_lineage.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: la filiation des delegations tient-elle ?"
if ! decor_poser; then
  echoue "le decor n'a pas pu etre pose: AUCUN controle n'est evalue."
  exit 1
fi

# Quatre identites metier FICTIVES. A est la racine, B et C la chaine, D une
# autorite independante posee pour eprouver la non-reaffectation.
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$A'),('$B'),('$C'),('$D')
on conflict do nothing;
SQL

# `octroyer <acteur> <beneficiaire> <parent|NULL> <permission> <pays> <famille>
#           <partie> <edition> <motif> [expiration|NULL]`
# rend la sortie SQL; l'appelant decide de ce qu'elle vaut.
octroyer() {
  local acteur="$1" ben="$2" parent="$3" perm="$4" pays="$5" fam="$6"
  local part="$7" ed="$8" motif="$9" exp="${10:-NULL}"
  local p="null"; [[ "$parent" != "NULL" ]] && p="'$parent'"
  local e="null"; [[ "$exp"    != "NULL" ]] && e="$exp"
  local c="null"; [[ "$pays"   != "NULL" ]] && c="'$pays'"
  local ff="null"; [[ "$fam"   != "NULL" ]] && ff="'$fam'"
  local pp="null"; [[ "$part"  != "NULL" ]] && pp="'$part'"
  local ee="null"; [[ "$ed"    != "NULL" ]] && ee="'$ed'"
  svc -tAc "set eurostruct.actor_id = '$acteur';
            insert into normative_authorisation_grants
              (grantee_id, grantee_name, permission, country_code,
               standard_family, part, edition, reason, parent_grant_id,
               expires_at)
            values ('$ben', 'FICTIF $ben', '$perm', $c, $ff, $pp, $ee,
                    '$motif', $p, $e)" 2>&1
}
id_de() { q "select id from normative_authorisation_grants where reason = '$1'"; }
revoquer() {   # revoquer <acteur> <grant_id> <motif>
  svc -tAc "set eurostruct.actor_id = '$1';
            insert into normative_authorisation_revocations (grant_id, reason)
            values ('$2', '$3')" 2>&1
}

# --------------------------------------------------------------------------
# LA RACINE — amorcee par le deploiement, comme en production
# --------------------------------------------------------------------------
ctl -tAc "select bootstrap_normative_administrator(
            '$A'::uuid, 'FICTIF A', 'FICTIF racine de filiation')" >/dev/null 2>&1
RACINE="$(q "select id from normative_authorisation_grants
              where origin = 'bootstrap' limit 1")"
if ! est_uuid "$RACINE"; then
  echoue "aucune racine amorcee: AUCUN controle n'est evalue."
  exit 1
fi
detail "racine (A, portee generique): $RACINE"

# ==========================================================================
# 1. LE PARENT EST OBLIGATOIRE
# ==========================================================================
echo "      -- parent-obligatoire: une delegation sans parent est-elle refusee ?"
R="$(octroyer "$A" "$B" NULL can_manage_normative_authorisations \
      BE 'EN 1992' NULL NULL 'FICTIF sans parent')"
N="$(q "select count(*) from normative_authorisation_grants
         where reason = 'FICTIF sans parent'")"
if [[ "$N" != "0" ]]; then
  rouge parent-obligatoire "une delegation SANS parent a ete acceptee: la"
  detail "provenance n'est pas exigee, et « au titre de quoi » reste inconnu."
elif erreur_sql "$R"; then
  sur parent-obligatoire "delegation sans parent refusee"
  detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,100}' <<<"$R")"
else
  troue parent-obligatoire "ni ecriture ni erreur: non interpretable."
fi

# ==========================================================================
# 2. LE CONSENTANT DOIT DETENIR LE PARENT — et la chaine A -> B se pose
# ==========================================================================
echo "      -- parent-detenu: peut-on invoquer l'habilitation d'un autre ?"
# NON-VACUITE: A, qui DETIENT la racine, doit reussir. On pose la chaine ici.
octroyer "$A" "$B" "$RACINE" can_manage_normative_authorisations \
  BE 'EN 1992' NULL NULL 'FICTIF A vers B' >/dev/null 2>&1
AB="$(id_de 'FICTIF A vers B')"
if ! est_uuid "$AB"; then
  troue parent-detenu "A n'a pas pu deleguer a B: la chaine n'existe pas."
  detail "les controles suivants seront donc vides."
else
  detail "chaine A -> B posee: $AB (BE / EN 1992)"
  # C, qui ne detient PAS la racine, tente de l'invoquer.
  R="$(octroyer "$C" "$D" "$RACINE" can_manage_normative_authorisations \
        BE 'EN 1992' NULL NULL 'FICTIF parent vole')"
  N="$(q "select count(*) from normative_authorisation_grants
           where reason = 'FICTIF parent vole'")"
  if [[ "$N" != "0" ]]; then
    rouge parent-detenu "C a invoque l'habilitation de A pour deleguer."
  elif erreur_sql "$R"; then
    sur parent-detenu "invoquer l'habilitation d'un autre est refuse"
    detail "non-vacuite: A, qui la detient, vient de reussir ($AB)."
  else
    troue parent-detenu "ni ecriture ni erreur: non interpretable."
  fi
fi

# ==========================================================================
# 3. LA PORTEE DE L'ENFANT EST INCLUSE DANS CELLE DU PARENT
# ==========================================================================
echo "      -- portee-incluse: B peut-il deleguer hors de BE / EN 1992 ?"
if ! est_uuid "$AB"; then
  troue portee-incluse "chaine absente."
else
  R="$(octroyer "$B" "$C" "$AB" can_validate_normative_reference \
        FR 'EN 1992' '1-1' '2004' 'FICTIF hors portee')"
  N="$(q "select count(*) from normative_authorisation_grants
           where reason = 'FICTIF hors portee'")"
  if [[ "$N" != "0" ]]; then
    rouge portee-incluse "B, borne a BE, a delegue sur FR."
  elif erreur_sql "$R"; then
    sur portee-incluse "delegation hors portee du parent refusee"
    detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,100}' <<<"$R")"
  else
    troue portee-incluse "ni ecriture ni erreur: non interpretable."
  fi
fi

# ==========================================================================
# 4. UN AXE NULL CHEZ L'ENFANT N'ELARGIT PAS UN PARENT BORNE
# ==========================================================================
# C'est le piege discret: NULL vaut « toutes les valeurs ». Un enfant qui
# laisse `country_code` a NULL sous un parent borne a BE demanderait TOUS les
# pays. Le declencheur doit lire NULL comme un ELARGISSEMENT, pas comme une
# absence d'exigence.
echo "      -- elargissement-null: un axe NULL sous un parent borne ?"
if ! est_uuid "$AB"; then
  troue elargissement-null "chaine absente."
else
  R="$(octroyer "$B" "$C" "$AB" can_manage_normative_authorisations \
        NULL 'EN 1992' NULL NULL 'FICTIF elargissement null')"
  N="$(q "select count(*) from normative_authorisation_grants
           where reason = 'FICTIF elargissement null'")"
  if [[ "$N" != "0" ]]; then
    rouge elargissement-null "un axe NULL sous un parent borne a BE a ete"
    detail "accepte: la delegation couvre desormais TOUS les pays."
  elif erreur_sql "$R"; then
    sur elargissement-null "l'elargissement par NULL est refuse"
  else
    troue elargissement-null "ni ecriture ni erreur: non interpretable."
  fi
fi

# ==========================================================================
# 5. LA PERMISSION NE S'ELEVE PAS
# ==========================================================================
echo "      -- permission-non-elevee: un pouvoir de verification delegue-t-il ?"
if ! est_uuid "$AB"; then
  troue permission-non-elevee "chaine absente."
else
  octroyer "$B" "$C" "$AB" can_validate_normative_reference \
    BE 'EN 1992' '1-1' '2004' 'FICTIF verif de C' >/dev/null 2>&1
  VC="$(id_de 'FICTIF verif de C')"
  if ! est_uuid "$VC"; then
    troue permission-non-elevee "B n'a pas pu octroyer une verification a C."
  else
    R="$(octroyer "$C" "$D" "$VC" can_validate_normative_reference \
          BE 'EN 1992' '1-1' '2004' 'FICTIF elevation')"
    N="$(q "select count(*) from normative_authorisation_grants
             where reason = 'FICTIF elevation'")"
    if [[ "$N" != "0" ]]; then
      rouge permission-non-elevee "C a delegue au titre d'un pouvoir de"
      detail "VERIFICATION: un droit de signer fabrique un droit d'octroyer."
    elif erreur_sql "$R"; then
      sur permission-non-elevee "deleguer au titre d'une verification est refuse"
      detail "non-vacuite: le meme C detient bien $VC, qui est actif."
    else
      troue permission-non-elevee "ni ecriture ni erreur: non interpretable."
    fi
  fi
fi

# ==========================================================================
# 6-7. A -> B -> C, ET LA REVOCATION DE A
# ==========================================================================
echo "      -- chaine-abc / revocation-transitive"
BC=""
if ! est_uuid "$AB"; then
  troue chaine-abc "chaine A -> B absente."
  troue revocation-transitive "chaine absente."
else
  octroyer "$B" "$C" "$AB" can_manage_normative_authorisations \
    BE 'EN 1992' NULL NULL 'FICTIF B vers C' >/dev/null 2>&1
  BC="$(id_de 'FICTIF B vers C')"
  if ! est_uuid "$BC"; then
    troue chaine-abc "B n'a pas pu deleguer a C."
    troue revocation-transitive "chaine A -> B -> C incomplete."
  else
    EFF_AVANT="$(q "select normative_grant_is_effective('$BC')")"
    detail "chaine A -> B -> C posee; C efficace avant revocation: $EFF_AVANT"
    if [[ "$EFF_AVANT" != "t" ]]; then
      troue chaine-abc "C n'est pas efficace AVANT toute revocation."
      troue revocation-transitive "point de depart invalide."
    else
      sur chaine-abc "la chaine A -> B -> C se pose et C est efficace."
      # A revoque l'habilitation de B. C ne doit plus rien pouvoir.
      revoquer "$A" "$AB" 'FICTIF revocation de B' >/dev/null 2>&1
      REV="$(q "select count(*) from normative_authorisation_revocations
                 where grant_id = '$AB'")"
      EFF_APRES="$(q "select normative_grant_is_effective('$BC')")"
      detail "revocation de A->B enregistree: $REV ; C efficace apres: $EFF_APRES"
      if [[ "$REV" != "1" ]]; then
        troue revocation-transitive "la revocation de A->B n'a pas abouti."
      elif [[ "$EFF_APRES" == "t" ]]; then
        rouge revocation-transitive "C reste EFFICACE apres la revocation de"
        detail "l'habilitation de B: retirer une autorite ne retire pas ce"
        detail "qu'elle a delegue."
      else
        sur revocation-transitive "revoquer A->B eteint C (efficacite transitive)"
        detail "non-vacuite: C etait efficace avant ($EFF_AVANT), et la ligne"
        detail "de C existe toujours — seule son EFFICACITE tombe, pas la preuve."
      fi
    fi
  fi
fi

# ==========================================================================
# 8-9. AUTORITE INDEPENDANTE, ET AUCUNE REAFFECTATION IMPLICITE
# ==========================================================================
# A donne a C une habilitation INDEPENDANTE, de meme portee. Elle ne doit pas
# « rattraper » la chaine eteinte: une nouvelle chaine explicite, oui; une
# reaffectation silencieuse de l'ancienne, non — sinon la revocation se
# defairait toute seule.
echo "      -- autorite-independante / pas-de-reaffectation"
octroyer "$A" "$C" "$RACINE" can_manage_normative_authorisations \
  BE 'EN 1992' NULL NULL 'FICTIF A vers C direct' >/dev/null 2>&1
AC="$(id_de 'FICTIF A vers C direct')"
if ! est_uuid "$AC"; then
  troue autorite-independante "A n'a pas pu octroyer directement a C."
  troue pas-de-reaffectation "autorite independante absente."
else
  EFF_AC="$(q "select normative_grant_is_effective('$AC')")"
  detail "habilitation independante A -> C: $AC (efficace: $EFF_AC)"
  if [[ "$EFF_AC" == "t" ]]; then
    sur autorite-independante "une chaine EXPLICITE nouvelle est bien efficace."
  else
    rouge autorite-independante "une habilitation independante fraiche n'est pas"
    detail "efficace: la revocation d'une AUTRE chaine l'a emportee avec elle."
  fi
  if [[ -n "$BC" ]] && est_uuid "$BC"; then
    EFF_BC="$(q "select normative_grant_is_effective('$BC')")"
    PAR_BC="$(q "select coalesce(parent_grant_id::text,'-')
                   from normative_authorisation_grants where id = '$BC'")"
    detail "l'ancien B->C: efficace=$EFF_BC parent=$PAR_BC"
    if [[ "$EFF_BC" == "t" ]]; then
      rouge pas-de-reaffectation "l'octroi eteint est redevenu efficace: il a"
      detail "ete rattache implicitement a une autre habilitation couvrante."
    elif [[ "$PAR_BC" != "$AB" ]]; then
      rouge pas-de-reaffectation "le parent de l'octroi eteint a change:"
      detail "attendu $AB, trouve $PAR_BC."
    else
      sur pas-de-reaffectation "l'octroi eteint le reste, et son parent n'a pas"
      detail "bouge. Une autorite independante ne rattrape pas une chaine morte."
    fi
  else
    troue pas-de-reaffectation "aucun octroi eteint a observer."
  fi
fi

# ==========================================================================
# 10. LE « CYCLE » A -> B -> A
# ==========================================================================
# LE GRAPHE DE FILIATION EST UN DAG PAR CONSTRUCTION: `parent_grant_id` ne peut
# designer qu'une ligne DEJA existante, et aucun UPDATE n'est accorde. Ce qu'on
# eprouve ici n'est donc pas un cycle de filiation — il est impossible — mais
# le cycle de PERSONNES: C rend a A un pouvoir qu'il tient de A. Il ne doit
# creer aucun pouvoir supplementaire, et surtout pas survivre a la revocation
# de son propre ancetre.
echo "      -- cycle-abа: C rend a A un pouvoir qu'il tient de A"
if ! est_uuid "$AC"; then
  troue cycle-abа "aucune habilitation de C a invoquer."
else
  octroyer "$C" "$A" "$AC" can_validate_normative_reference \
    BE 'EN 1992' '1-1' '2010' 'FICTIF cycle vers A' >/dev/null 2>&1
  CA="$(id_de 'FICTIF cycle vers A')"
  if ! est_uuid "$CA"; then
    detail "C n'a pas pu octroyer a A — le cycle ne se forme pas."
    sur cycle-abа "le cycle de personnes ne se forme meme pas."
  else
    PROF="$(q "with recursive c as (
                 select id, parent_grant_id, 1 as n
                   from normative_authorisation_grants where id = '$CA'
                 union all
                 select p.id, p.parent_grant_id, c.n + 1
                   from normative_authorisation_grants p join c on p.id = c.parent_grant_id)
               select max(n) from c")"
    detail "octroi C -> A: $CA ; profondeur de chaine remontee: $PROF"
    # La remontee TERMINE (pas de boucle infinie) et la revocation de l'ancetre
    # doit l'eteindre malgre le retour a A.
    revoquer "$A" "$AC" 'FICTIF revocation ancetre du cycle' >/dev/null 2>&1
    EFF_CA="$(q "select normative_grant_is_effective('$CA')")"
    detail "apres revocation de l'ancetre $AC: efficace=$EFF_CA"
    if [[ "$EFF_CA" == "t" ]]; then
      rouge cycle-abа "l'octroi de retour survit a la revocation de son"
      detail "ancetre: le detour par A a fabrique un pouvoir autonome."
    else
      sur cycle-abа "la remontee termine (profondeur $PROF) et l'octroi de"
      detail "retour s'eteint avec son ancetre. Le detour ne cree rien."
    fi
  fi
fi

# ==========================================================================
# 11-12. EXPIRATION, ET EXPIRATION D'UN ANCETRE
# ==========================================================================
echo "      -- expiration / expiration-ancetre"
octroyer "$A" "$B" "$RACINE" can_manage_normative_authorisations \
  BE 'EN 1993' NULL NULL 'FICTIF A vers B temporaire' \
  "now() + interval '1 hour'" >/dev/null 2>&1
TMP="$(id_de 'FICTIF A vers B temporaire')"
if ! est_uuid "$TMP"; then
  troue expiration "l'habilitation a terme n'a pas ete creee."
  troue expiration-ancetre "habilitation a terme absente."
else
  # Un enfant SANS terme sous un parent a terme doit etre refuse.
  R="$(octroyer "$B" "$C" "$TMP" can_validate_normative_reference \
        BE 'EN 1993' '1-1' '2005' 'FICTIF enfant perpetuel')"
  NP="$(q "select count(*) from normative_authorisation_grants
            where reason = 'FICTIF enfant perpetuel'")"
  if [[ "$NP" != "0" ]]; then
    rouge expiration "un enfant SANS terme a ete accepte sous un parent qui en"
    detail "a un: une delegation perpetuelle nait d'un pouvoir temporaire."
  elif erreur_sql "$R"; then
    sur expiration "un enfant sans terme sous un parent a terme est refuse"
    detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,100}' <<<"$R")"
  else
    troue expiration "ni ecriture ni erreur: non interpretable."
  fi

  # UN ANCETRE EXPIRE ETEINT SA DESCENDANCE. On pose un parent DEJA expire —
  # pas d'attente, pas de `sleep`: l'horloge n'est pas un ordonnanceur.
  octroyer "$A" "$B" "$RACINE" can_manage_normative_authorisations \
    BE 'EN 1994' NULL NULL 'FICTIF A vers B expire' \
    "now() - interval '1 second'" >/dev/null 2>&1
  EXP="$(id_de 'FICTIF A vers B expire')"
  if ! est_uuid "$EXP"; then
    troue expiration-ancetre "l'habilitation expiree n'a pas ete creee."
  else
    EFF="$(q "select normative_grant_is_effective('$EXP')")"
    R="$(octroyer "$B" "$C" "$EXP" can_validate_normative_reference \
          BE 'EN 1994' '1-1' '2006' 'FICTIF sous ancetre expire')"
    NX="$(q "select count(*) from normative_authorisation_grants
              where reason = 'FICTIF sous ancetre expire'")"
    detail "habilitation expiree $EXP: efficace=$EFF ; delegation dessous: $NX"
    if [[ "$EFF" == "t" ]]; then
      rouge expiration-ancetre "une habilitation dont le terme est passe reste"
      detail "efficace: `expires_at` ne decide de rien."
    elif [[ "$NX" != "0" ]]; then
      rouge expiration-ancetre "une delegation a ete consentie au titre d'une"
      detail "habilitation EXPIREE."
    else
      sur expiration-ancetre "une habilitation expiree n'est plus efficace et"
      detail "ne delegue plus. Aucun sleep: le terme est pose dans le passe."
    fi
  fi
fi

# ==========================================================================
# 13. DELEGATION PENDANT UNE REVOCATION — barriere deterministe
# ==========================================================================
# La revocation est PARQUEE, transaction ouverte et verrou de ligne en main;
# on OBSERVE la delegation bloquee; puis on relache. La course est construite,
# pas esperee, et aucun `sleep` n'ordonne quoi que ce soit.
echo "      -- delegation-pendant-revocation (barriere deterministe)"
octroyer "$A" "$B" "$RACINE" can_manage_normative_authorisations \
  BE 'EN 1995' NULL NULL 'FICTIF course parent' >/dev/null 2>&1
CP="$(id_de 'FICTIF course parent')"
if ! est_uuid "$CP"; then
  troue delegation-pendant-revocation "le parent de course n'a pas ete cree."
else
  BAR=78000000001
  APP_R="FICTIF-lin-rev-${JETON}"; APP_D="FICTIF-lin-del-${JETON}"
  BLOQUEE=-1
  if barriere_prendre "$BAR"; then
    ( exec {BAR_FD}>&-
      PGAPPNAME="$APP_R" \
      svc -tAc "set eurostruct.actor_id = '$A';
                begin;
                insert into normative_authorisation_revocations (grant_id, reason)
                values ('$CP', 'FICTIF revocation en vol');
                select pg_advisory_lock_shared($BAR);
                commit;" >/dev/null 2>&1 ) &
    CONCURRENTS+=("$!")
    if attendre "la revocation est EN VOL, parquee sur $BAR" \
         "exists(select 1 from pg_stat_activity
                  where application_name = '$APP_R'
                    and wait_event_type = 'Lock')"; then
      ( exec {BAR_FD}>&-
        PGAPPNAME="$APP_D" \
        svc -tAc "set eurostruct.actor_id = '$B';
                  insert into normative_authorisation_grants
                    (grantee_id, grantee_name, permission, country_code,
                     standard_family, part, edition, reason, parent_grant_id)
                  values ('$C', 'FICTIF C', 'can_validate_normative_reference',
                          'BE', 'EN 1995', '1-1', '2007',
                          'FICTIF delegation en course', '$CP');" >/dev/null 2>&1 ) &
      CONCURRENTS+=("$!")
      if attendre "la delegation est BLOQUEE par la revocation en vol" \
           "exists(select 1 from pg_stat_activity
                    where application_name = '$APP_D'
                      and wait_event_type = 'Lock')"; then
        BLOQUEE=1
      else
        BLOQUEE=0
      fi
    fi
    barriere_lever
    attendre_concurrents
  else
    barriere_lever
  fi
  REV="$(q "select count(*) from normative_authorisation_revocations
             where grant_id = '$CP'")"
  DEL="$(q "select count(*) from normative_authorisation_grants
             where reason = 'FICTIF delegation en course'")"
  detail "revocation validee: $REV ; delegation aboutie: $DEL ; bloquee: $BLOQUEE"
  if [[ "$BLOQUEE" == "-1" ]]; then
    troue delegation-pendant-revocation "la course n'a pas pu etre montee."
  elif [[ "$REV" != "1" ]]; then
    troue delegation-pendant-revocation "la revocation n'a pas abouti: rien ne"
    detail "s'opposait a la delegation."
  elif [[ "$BLOQUEE" == "0" ]]; then
    rouge delegation-pendant-revocation "la delegation n'a JAMAIS attendu la"
    detail "revocation en vol: aucune exclusion mutuelle entre les deux chemins."
  elif [[ "$DEL" != "0" ]]; then
    rouge delegation-pendant-revocation "une delegation a ete consentie au titre"
    detail "d'une habilitation dont la revocation etait deja validee."
  else
    sur delegation-pendant-revocation "la delegation a ete OBSERVEE bloquee,"
    detail "puis refusee apres relecture sous verrou."
  fi
fi

# ==========================================================================
# 14. DEUX REVOCATIONS CONCURRENTES DU MEME OCTROI
# ==========================================================================
echo "      -- revocations-concurrentes (barriere par verrou partage)"
octroyer "$A" "$B" "$RACINE" can_manage_normative_authorisations \
  BE 'EN 1996' NULL NULL 'FICTIF double revocation' >/dev/null 2>&1
DR="$(id_de 'FICTIF double revocation')"
if ! est_uuid "$DR"; then
  troue revocations-concurrentes "l'octroi a revoquer n'a pas ete cree."
else
  BAR2=78000000002
  if barriere_prendre "$BAR2"; then
    for t in r1 r2; do
      ( exec {BAR_FD}>&-
        PGAPPNAME="FICTIF-lin-${t}-${JETON}" \
        svc -tAc "select pg_advisory_lock_shared($BAR2);
                  set eurostruct.actor_id = '$A';
                  insert into normative_authorisation_revocations
                    (grant_id, reason)
                  values ('$DR', 'FICTIF concurrente $t');" >/dev/null 2>&1 ) &
      CONCURRENTS+=("$!")
    done
    if attendre "2 revocations concurrentes bloquees sur $BAR2" \
         "(select count(*) from pg_stat_activity
            where application_name like 'FICTIF-lin-r%-${JETON}'
              and wait_event_type = 'Lock') = 2"; then
      barriere_lever; attendre_concurrents
      N="$(q "select count(*) from normative_authorisation_revocations
               where grant_id = '$DR'")"
      detail "revocations enregistrees pour un meme octroi: $N"
      if [[ "$N" == "1" ]]; then
        sur revocations-concurrentes "exactement une revocation aboutit"
        detail "(unique (grant_id)); les deux sessions ont ete OBSERVEES"
        detail "bloquees avant d'etre relachees ensemble."
      elif [[ "$N" == "0" ]]; then
        troue revocations-concurrentes "aucune n'a abouti: rien n'est exerce."
      else
        rouge revocations-concurrentes "$N revocations du meme octroi."
      fi
    else
      barriere_lever; attendre_concurrents
      troue revocations-concurrentes "barriere jamais franchie."
    fi
  else
    barriere_lever
    troue revocations-concurrentes "barriere non prise."
  fi
fi

# ==========================================================================
# 15. LA DESCENDANCE EST VISIBLE AVANT DE REVOQUER
# ==========================================================================
# « Que perd-on en revoquant ceci ? » doit etre repondable AVANT de le faire.
# C'est la contrepartie de la transitivite: sans elle, la cascade serait une
# surprise.
echo "      -- descendance-visible: peut-on lire ce qu'un octroi porte ?"
N="$(q "select count(*) from normative_grant_descendants('$RACINE')")"
TOTAL="$(q "select count(*) from normative_authorisation_grants
             where origin <> 'bootstrap'")"
detail "descendance de la racine: $N ; octrois delegues en base: $TOTAL"
if [[ "$N" == "0" && "$TOTAL" != "0" ]]; then
  rouge descendance-visible "la racine ne rapporte AUCUNE descendance alors que"
  detail "$TOTAL octrois delegues existent: la couverture est aveugle."
elif [[ "$TOTAL" == "0" ]]; then
  troue descendance-visible "aucun octroi delegue: le controle est vide."
elif [[ "$N" == "$TOTAL" ]]; then
  sur descendance-visible "la racine rapporte ses $N descendants, a toute"
  detail "profondeur. La question « que perd-on ? » est repondable avant."
else
  sur descendance-visible "la racine rapporte $N descendants sur $TOTAL octrois"
  detail "delegues — les autres relevent d'une autre racine ou n'en ont pas."
fi

# ==========================================================================
verdicts_verifier || true
echo ""
echo "      barrieres (mecanisme deterministe, aucun sleep d'ordonnancement):"
if ((${#BARRIERES[@]} == 0)); then echo "                (aucune)"
else printf '                %s\n' "${BARRIERES[@]}"; fi
verdicts_resume "6.3c — filiation des delegations"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " La filiation tient."
  exit 0
fi
exit 1
