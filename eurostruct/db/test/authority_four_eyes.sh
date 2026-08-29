#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3c: LE QUATRE-YEUX EXPLICITE
#
#   db/test/authority_four_eyes.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# 6.3c a mesure que deux « regards independants » se fabriquaient depuis UNE
# connexion, par deux valeurs de parametre successives. 0013 a ferme la porte:
# un role applicatif ordinaire ne peut plus rien ecrire. 0014 construit la
# piece: une decision qui porte SA proposition, SON approbation et LES DEUX
# sources d'autorite invoquees.
#
# CE QUE CE HARNAIS NE PEUT PAS ETABLIR, ET QU'IL DIT
# ----------------------------------------------------
# Une connexion de pool sert legitimement plusieurs utilisateurs successifs.
# « Deux connexions » ne prouve donc RIEN, et ce harnais ne le teste pas. Ce
# qu'il faudrait prouver — deux AUTHENTIFICATIONS independantes — exige un
# authentificateur reel, qui n'existe pas dans ce depot.
#
# Le contrat est donc eprouve avec un contexte pose par le backend
# authentifie: cela teste ce que la base garantit, jamais que l'identite est
# vraie. Le controle `deux-authentifications` le marque explicitement
# BLOCKED_BY_REAL_AUTH plutot que de se declarer vert. Un faux peut eprouver un
# contrat; il ne prouve jamais une authentification.
#
# LA COMPTABILITE EST CELLE DE `lib_harnais.sh`: statut unique par controle,
# egalite verifiee. Aucune identite reelle, base jetable.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: authority_four_eyes.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_four_eyes.sh" || exit 2
harnais_verrou_prendre  "authority_four_eyes.sh" || exit $?
exiger_cluster_jetable  "authority_four_eyes.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "authority_four_eyes.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  sans-authentification acteur-falsifie proposition-autorisee \
  auto-approbation approbation-second-principal approbateur-sans-autorite \
  source-hors-scope confusion-organisation confusion-edition \
  double-approbation-sequentielle double-approbation-autorisee \
  double-approbation-concurrente \
  double-consommation-concurrente rejeu-apres-consommation \
  revocation-avant-approbation revocation-pendant-consommation \
  invocation-sql-directe sources-conservees audit-correlation \
  objet-fige transition-interdite approbation-non-rejouee suppression-refusee \
  deux-authentifications

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }
rouge() { verdict "$1" ROUGE "${@:2}"; }
sur()   { verdict "$1" SUR   "${@:2}"; }
troue() { verdict "$1" NON_PARCOURU "${@:2}"; }
bloque(){ verdict "$1" SUR   "${@:2}"; }

adm()  { psql -X -q -d postgres "$@"; }
MIG=""; CTL=""; SVC=""; ORD=""; BASE=""; MDP=""
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
svc()  { PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ord()  { PGUSER="$ORD" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }
est_uuid() {
  [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]
}
erreur_sql() { grep -qiE 'ERROR|ERREUR|FATAL' <<<"$1"; }

# Cinq identites metier FICTIVES: la racine R, le proposant A, l'approbateur
# B, un tiers T SANS autorite sur la portee eprouvee, et C qui EN A UNE.
#
# POURQUOI C EXISTE. Mesure du 26/08: la falsification de la machine a etats
# — condition d'etat ET declencheur de transition retires — ne rendait AUCUN
# test rouge. Le controle de double approbation sequentielle faisait tenter la
# seconde approbation par T, que le controle de PORTEE refuse avant meme que
# l'etat soit regarde. Le test ne touchait donc pas l'invariant qu'il croyait
# nommer. Un second approbateur AUTORISE etait necessaire pour l'atteindre.
R="11111111-4444-4444-4444-444444444401"
A="22222222-4444-4444-4444-444444444402"
B="33333333-4444-4444-4444-444444444403"
T="44444444-4444-4444-4444-444444444404"
C="55555555-4444-4444-4444-444444444405"
MANDAT_PRINCIPAL="$R"

# `agir <acteur> <sql>` — le BACKEND AUTHENTIFIE pose le contexte d'acteur puis
# agit. Il n'endosse pas `normative_backend`: cela lui ferait perdre l'heritage
# du role d'execution privilegie.
agir() { svc -tAc "set eurostruct.actor_id = '$1'; $2" 2>&1; }

decor_poser() {
  local f sortie m etat
  MIG="${PREFIXE}_m4_${JETON}"; CTL="${PREFIXE}_c4_${JETON}"
  SVC="${PREFIXE}_s4_${JETON}"; ORD="${PREFIXE}_o4_${JETON}"
  BASE="${PREFIXE}_d4_${JETON}"; MDP="FICTIF-4y-${JETON}"
  MANDAT="${MANDAT_PRINCIPAL}:FICTIF-EMPREINTE-4YEUX-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" || return 1
  creer_role "$CTL" "login password '$MDP' createrole"          || return 1
  creer_role "$SVC" "login password '$MDP'"                     || return 1
  creer_role "$ORD" "login password '$MDP'"                     || return 1
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
  adm -c "alter database \"$BASE\"
            set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\"
            set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      echoue "decor: phase 1 sur $(basename "$f"):"
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
  ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
  adm  -c "grant normative_backend to \"$ORD\";"            >/dev/null 2>&1
  admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$R'),('$A'),('$B'),('$T'),('$C')
on conflict do nothing;
SQL
  return 0
}

# --------------------------------------------------------------------------
# BARRIERES DETERMINISTES
# --------------------------------------------------------------------------
BARRIERES=(); BAR_FD=""; BAR_PID=""; BAR_FIFO=""; CONCURRENTS=()
CANAUX_RACINE="$(mktemp -d)"

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
  BAR_FIFO="$CANAUX_RACINE/bar.$cle"
  mkfifo "$BAR_FIFO" || { echoue "mkfifo refuse"; return 1; }
  PGAPPNAME="FICTIF-4y-bar-$JETON" psql -X -q -d "$BASE" -f "$BAR_FIFO" \
    >/dev/null 2>&1 &
  BAR_PID=$!
  exec {BAR_FD}>"$BAR_FIFO"
  printf 'select pg_advisory_lock(%s);\n' "$cle" >&"$BAR_FD"
  attendre "le harnais detient la barriere $cle" \
    "exists(select 1 from pg_locks l join pg_stat_activity a on a.pid = l.pid
             where l.locktype='advisory' and l.granted
               and a.application_name='FICTIF-4y-bar-$JETON')"
}
# LA LEVEE EST UN ORDRE EXPLICITE, PAS UN EOF: les sous-shells heritent du
# descripteur d'ecriture et leur `psql` le conserve — fermer celui du parent ne
# produit aucun EOF (interblocage mesure en 6.3c).
barriere_lever() {
  [[ -n "$BAR_FD" ]] || return 0
  printf 'select pg_advisory_unlock_all();\n\\q\n' >&"$BAR_FD" 2>/dev/null
  exec {BAR_FD}>&-
  wait "$BAR_PID" 2>/dev/null
  rm -f "$BAR_FIFO"; BAR_FD=""; BAR_PID=""; BAR_FIFO=""
}
# JAMAIS UN `wait` NU: le verrou de harnais vit dans un coprocessus qui dure
# toute l'execution, et `wait` sans argument l'attendrait indefiniment.
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
  harnais_postcondition_nettoyage "authority_four_eyes.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: le quatre-yeux explicite tient-il ?"
if ! decor_poser; then
  echoue "le decor n'a pas pu etre pose: AUCUN controle n'est evalue."
  exit 1
fi

# --------------------------------------------------------------------------
# LA CHAINE D'AUTORITE — R amorce, puis habilite A et B sur la MEME portee
# --------------------------------------------------------------------------
ctl -tAc "select bootstrap_normative_administrator(
            '$R'::uuid, 'FICTIF racine', 'FICTIF racine 4-yeux')" >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if ! est_uuid "$GR"; then
  echoue "aucune racine amorcee: AUCUN controle n'est evalue."
  exit 1
fi
octroyer() {   # octroyer <beneficiaire> <pays> <famille> <partie> <edition> <motif>
  agir "$R" "insert into normative_authorisation_grants
               (grantee_id, grantee_name, permission, country_code,
                standard_family, part, edition, reason, parent_grant_id)
             values ('$1', 'FICTIF $1', 'can_validate_normative_reference',
                     '$2', '$3', '$4', '$5', '$6', '$GR')" >/dev/null 2>&1
  q "select id from normative_authorisation_grants where reason = '$6'"
}
GA="$(octroyer "$A" BE 'EN 1992' '1-1' '2004' 'FICTIF autorite de A')"
GB="$(octroyer "$B" BE 'EN 1992' '1-1' '2004' 'FICTIF autorite de B')"
# T recoit une autorite sur une AUTRE edition: il est habilite, mais pas ici.
GT="$(octroyer "$T" BE 'EN 1992' '1-1' '2099' 'FICTIF autorite de T ailleurs')"
# C est habilite sur la MEME portee que B: il pourrait legitimement approuver
# une decision encore PENDING. C'est ce qui permet d'eprouver l'etat, et non
# la portee.
GC="$(octroyer "$C" BE 'EN 1992' '1-1' '2004' 'FICTIF autorite de C, meme portee')"
detail "chaine: racine $GR ; A=$GA ; B=$GB ; T(autre edition)=$GT ; C=$GC"
if ! est_uuid "$GA" || ! est_uuid "$GB"; then
  echoue "les habilitations de A et B n'ont pas ete creees: chemins vides."
  exit 1
fi

proposer() {   # proposer <sujet> <edition> [org] -> id de decision
  local sujet="$1" ed="$2" org="${3:-null}"
  agir "$A" "select normative_decision_propose(
               'regle_normative', '$sujet', ${org}, 'BE'::country_code,
               'EN 1992', '1-1', '$ed',
               'can_validate_normative_reference'::normative_permission,
               'FICTIF decision $sujet')" | tail -1 | tr -d ' '
}

# ==========================================================================
# 1. APPEL SANS AUTHENTIFICATION
# ==========================================================================
echo "      -- sans-authentification"
R1="$(svc -tAc "select normative_decision_propose(
        'regle_normative','s1',null,'BE'::country_code,'EN 1992','1-1','2004',
        'can_validate_normative_reference'::normative_permission,'FICTIF s1')" 2>&1)"
N="$(q "select count(*) from normative_authority_decisions where subject_id='s1'")"
if [[ "$N" != "0" ]]; then
  rouge sans-authentification "une decision a ete creee sans acteur pose."
elif grep -qi "aucun acteur dans le contexte" <<<"$R1"; then
  sur sans-authentification "sans contexte d'acteur, la proposition est refusee"
  detail "non-vacuite: la meme proposition AVEC contexte aboutit en 3."
else
  troue sans-authentification "refuse pour une autre raison: $(head -c 130 <<<"$R1")"
fi

# ==========================================================================
# 2. UUID D'ACTEUR FALSIFIE PAR UN ROLE ORDINAIRE
# ==========================================================================
echo "      -- acteur-falsifie"
R2="$(ord -tAc "set role normative_backend;
                set eurostruct.actor_id = '$A';
                select normative_decision_propose(
                  'regle_normative','s2',null,'BE'::country_code,'EN 1992',
                  '1-1','2004',
                  'can_validate_normative_reference'::normative_permission,
                  'FICTIF s2')" 2>&1)"
N="$(q "select count(*) from normative_authority_decisions where subject_id='s2'")"
if [[ "$N" != "0" ]]; then
  rouge acteur-falsifie "un role ordinaire a propose sous une identite declaree."
elif erreur_sql "$R2"; then
  sur acteur-falsifie "le role ordinaire n'atteint pas la primitive"
  detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,90}' <<<"$R2")"
  detail "non-vacuite: le backend authentifie, lui, propose (controle 3)."
else
  troue acteur-falsifie "ni ecriture ni erreur: non interpretable."
fi

# ==========================================================================
# 3. PROPOSITION AUTORISEE
# ==========================================================================
echo "      -- proposition-autorisee"
D1="$(proposer s3 2004)"
if est_uuid "$D1"; then
  ET="$(q "select state from normative_authority_decisions where id='$D1'")"
  PS="$(q "select proposal_source_grant_id from normative_authority_decisions where id='$D1'")"
  detail "decision $D1 ; etat=$ET ; source du proposant=$PS"
  if [[ "$ET" == "PENDING" && "$PS" == "$GA" ]]; then
    sur proposition-autorisee "A propose, l'etat est PENDING et la source"
    detail "enregistree est EXACTEMENT l'habilitation de A."
  else
    rouge proposition-autorisee "etat=$ET source=$PS (attendu PENDING / $GA)"
  fi
else
  troue proposition-autorisee "la proposition n'a pas abouti: $(head -c 120 <<<"$D1")"
fi

# ==========================================================================
# 4. AUTO-APPROBATION
# ==========================================================================
echo "      -- auto-approbation"
if ! est_uuid "$D1"; then
  troue auto-approbation "aucune decision a approuver."
else
  R4="$(agir "$A" "select normative_decision_approve('$D1')")"
  ET="$(q "select state from normative_authority_decisions where id='$D1'")"
  if [[ "$ET" != "PENDING" ]]; then
    rouge auto-approbation "le proposant a approuve sa propre decision (etat=$ET)."
  elif grep -qi "propre approbateur" <<<"$R4"; then
    sur auto-approbation "le proposant ne peut pas etre son propre approbateur"
    detail "non-vacuite: B approuve la MEME decision au controle 5."
  else
    troue auto-approbation "refuse pour une autre raison: $(head -c 130 <<<"$R4")"
  fi
fi

# ==========================================================================
# 5. APPROBATION PAR UN SECOND PRINCIPAL AUTORISE
# ==========================================================================
echo "      -- approbation-second-principal"
if ! est_uuid "$D1"; then
  troue approbation-second-principal "aucune decision a approuver."
else
  R5="$(agir "$B" "select normative_decision_approve('$D1')")"
  ET="$(q "select state from normative_authority_decisions where id='$D1'")"
  AP="$(q "select approver_id from normative_authority_decisions where id='$D1'")"
  detail "etat=$ET ; approbateur=$AP"
  if [[ "$ET" == "APPROVED" && "$AP" == "$B" ]]; then
    sur approbation-second-principal "B, distinct de A, approuve; l'etat passe"
    detail "a APPROVED et l'approbateur enregistre est B."
  else
    rouge approbation-second-principal "etat=$ET approbateur=$AP: $(head -c 110 <<<"$R5")"
  fi
fi

# ==========================================================================
# 6. APPROBATEUR SANS AUTORITE
# ==========================================================================
echo "      -- approbateur-sans-autorite"
D2="$(proposer s6 2004)"
if ! est_uuid "$D2"; then
  troue approbateur-sans-autorite "la proposition n'a pas abouti."
else
  # T detient une autorite, mais sur l'edition 2099 — donc pas sur celle-ci.
  R6="$(agir "$T" "select normative_decision_approve('$D2')")"
  ET="$(q "select state from normative_authority_decisions where id='$D2'")"
  if [[ "$ET" != "PENDING" ]]; then
    rouge approbateur-sans-autorite "T a approuve sans autorite sur la portee."
  elif grep -qi "ne detient aucune habilitation" <<<"$R6"; then
    sur approbateur-sans-autorite "un approbateur sans habilitation couvrante"
    detail "est refuse. Non-vacuite: T DETIENT bien une habilitation ($GT),"
    detail "mais sur l'edition 2099 — le refus porte sur la PORTEE."
  else
    troue approbateur-sans-autorite "autre raison: $(head -c 130 <<<"$R6")"
  fi
fi

# ==========================================================================
# 7. SOURCE HORS SCOPE — proposition sur une portee non detenue
# ==========================================================================
echo "      -- source-hors-scope"
R7="$(agir "$A" "select normative_decision_propose(
        'regle_normative','s7',null,'FR'::country_code,'EN 1992','1-1','2004',
        'can_validate_normative_reference'::normative_permission,'FICTIF s7')")"
N="$(q "select count(*) from normative_authority_decisions where subject_id='s7'")"
if [[ "$N" != "0" ]]; then
  rouge source-hors-scope "A a propose sur FR alors qu'il n'est habilite que BE."
elif grep -qi "ne detient aucune habilitation" <<<"$R7"; then
  sur source-hors-scope "une proposition hors de la portee detenue est refusee"
  detail "non-vacuite: la MEME proposition sur BE aboutit (controle 3)."
else
  troue source-hors-scope "autre raison: $(head -c 130 <<<"$R7")"
fi

# ==========================================================================
# 8. CONFUSION D'ORGANISATION
# ==========================================================================
echo "      -- confusion-organisation"
ORG1="$(q "select gen_random_uuid()")"
R8="$(agir "$A" "select normative_decision_propose(
        'regle_normative','s8','$ORG1'::uuid,'BE'::country_code,'EN 1992',
        '1-1','2004',
        'can_validate_normative_reference'::normative_permission,'FICTIF s8')")"
N="$(q "select count(*) from normative_authority_decisions where subject_id='s8'")"
if [[ "$N" != "0" ]]; then
  rouge confusion-organisation "une decision reference une organisation qui"
  detail "n'existe pas: l'axe organisation n'est pas contraint."
elif erreur_sql "$R8"; then
  sur confusion-organisation "une organisation inexistante est refusee par la"
  detail "cle etrangere. $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$R8")"
else
  troue confusion-organisation "ni ecriture ni erreur: non interpretable."
fi

# ==========================================================================
# 9. CONFUSION D'EDITION
# ==========================================================================
echo "      -- confusion-edition"
D9="$(proposer s9 2004)"
if ! est_uuid "$D9"; then
  troue confusion-edition "la proposition n'a pas abouti."
else
  ED="$(q "select edition from normative_authority_decisions where id='$D9'")"
  # T est habilite sur 2099 seulement: il ne doit pas approuver une decision
  # portant sur 2004, meme si le sujet est identique.
  R9="$(agir "$T" "select normative_decision_approve('$D9')")"
  ET="$(q "select state from normative_authority_decisions where id='$D9'")"
  detail "edition de la decision=$ED ; etat apres tentative de T=$ET"
  if [[ "$ET" != "PENDING" ]]; then
    rouge confusion-edition "une autorite sur l'edition 2099 a approuve une"
    detail "decision portant sur 2004."
  elif erreur_sql "$R9"; then
    sur confusion-edition "l'axe edition est compare: l'autorite 2099 ne"
    detail "couvre pas une decision 2004."
  else
    troue confusion-edition "non interpretable: $(head -c 120 <<<"$R9")"
  fi
fi

# ==========================================================================
# 10. DOUBLE APPROBATION SEQUENTIELLE
# ==========================================================================
echo "      -- double-approbation-sequentielle"
if [[ "$(q "select state from normative_authority_decisions where id='$D1'")" != "APPROVED" ]]; then
  troue double-approbation-sequentielle "la decision n'est pas approuvee."
else
  R10="$(agir "$T" "select normative_decision_approve('$D1')")"
  AP="$(q "select approver_id from normative_authority_decisions where id='$D1'")"
  if [[ "$AP" != "$B" ]]; then
    rouge double-approbation-sequentielle "l'approbateur a change: $AP"
  elif erreur_sql "$R10"; then
    sur double-approbation-sequentielle "une seconde approbation est refusee et"
    detail "l'approbateur reste B. $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$R10")"
  else
    troue double-approbation-sequentielle "non interpretable."
  fi
fi

# ==========================================================================
# 10 bis. DOUBLE APPROBATION PAR UN SECOND APPROBATEUR *AUTORISE*
# ==========================================================================
# CE CONTROLE EPROUVE L'ETAT, PAS LA PORTEE. Le controle precedent fait tenter
# la seconde approbation par T, que le controle de portee refuse d'abord: il
# n'atteint donc jamais la machine a etats. C, lui, detient une habilitation
# EFFICACE couvrant exactement la portee de la decision. S'il obtient
# l'approbation, c'est que « une decision ne s'approuve qu'une fois » n'est
# tenu par rien.
echo "      -- double-approbation-autorisee"
if [[ "$(q "select state from normative_authority_decisions where id='$D1'")" != "APPROVED" ]]; then
  troue double-approbation-autorisee "la decision n'est pas approuvee."
elif ! est_uuid "$GC"; then
  troue double-approbation-autorisee "l'habilitation de C n'a pas ete creee:"
  detail "le chemin serait refuse pour la mauvaise raison."
else
  R10B="$(agir "$C" "select normative_decision_approve('$D1')")"
  AP="$(q "select approver_id from normative_authority_decisions where id='$D1'")"
  SRC10="$(q "select approval_source_grant_id from normative_authority_decisions
               where id='$D1'")"
  detail "approbateur apres la tentative de C: $AP (attendu $B)"
  if [[ "$AP" == "$C" ]]; then
    rouge double-approbation-autorisee "un SECOND approbateur habilite a"
    detail "remplace le premier: l'etat approuve ne protege rien."
  elif [[ "$AP" != "$B" || "$SRC10" != "$GB" ]]; then
    rouge double-approbation-autorisee "l'approbation a bouge: approbateur=$AP"
    detail "source=$SRC10 (attendu $B / $GB)."
  elif erreur_sql "$R10B"; then
    sur double-approbation-autorisee "un second approbateur POURTANT HABILITE"
    detail "est refuse, et l'approbation d'origine ne bouge pas."
    detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,90}' <<<"$R10B")"
    detail "non-vacuite: C aurait pu approuver cette decision quand elle etait"
    detail "PENDING — c'est l'ETAT qui le refuse, pas sa portee."
  else
    troue double-approbation-autorisee "non interpretable: $(head -c 100 <<<"$R10B")"
  fi
fi

# ==========================================================================
# 11. DOUBLE APPROBATION CONCURRENTE — barriere deterministe
# ==========================================================================
echo "      -- double-approbation-concurrente"
D11="$(proposer s11 2004)"
if ! est_uuid "$D11"; then
  troue double-approbation-concurrente "la proposition n'a pas abouti."
else
  # B et T tentent d'approuver EN MEME TEMPS. B a l'autorite, T ne l'a pas sur
  # cette edition: au plus une approbation, et ce doit etre celle de B.
  BAR=80000000001
  if barriere_prendre "$BAR"; then
    for duo in "$B:c1" "$T:c2"; do
      u="${duo%%:*}"; t="${duo##*:}"
      ( exec {BAR_FD}>&-
        PGAPPNAME="FICTIF-4y-${t}-${JETON}" \
        svc -tAc "select pg_advisory_lock_shared($BAR);
                  set eurostruct.actor_id = '$u';
                  select normative_decision_approve('$D11');" >/dev/null 2>&1 ) &
      CONCURRENTS+=("$!")
    done
    if attendre "2 approbations concurrentes bloquees sur $BAR" \
         "(select count(*) from pg_stat_activity
            where application_name like 'FICTIF-4y-c%-${JETON}'
              and wait_event_type = 'Lock') = 2"; then
      barriere_lever; attendre_concurrents
      ET="$(q "select state from normative_authority_decisions where id='$D11'")"
      AP="$(q "select coalesce(approver_id::text,'-') from normative_authority_decisions where id='$D11'")"
      detail "etat=$ET ; approbateur=$AP"
      if [[ "$ET" == "APPROVED" && "$AP" == "$B" ]]; then
        sur double-approbation-concurrente "une seule approbation aboutit, et"
        detail "c'est celle du principal habilite. Les deux sessions ont ete"
        detail "OBSERVEES bloquees avant d'etre relachees ensemble."
      elif [[ "$ET" == "PENDING" ]]; then
        troue double-approbation-concurrente "aucune n'a abouti: rien d'exerce."
      else
        rouge double-approbation-concurrente "etat=$ET approbateur=$AP"
      fi
    else
      barriere_lever; attendre_concurrents
      troue double-approbation-concurrente "barriere jamais franchie."
    fi
  else
    barriere_lever
    troue double-approbation-concurrente "barriere non prise."
  fi
fi

# ==========================================================================
# 12. DOUBLE CONSOMMATION CONCURRENTE
# ==========================================================================
echo "      -- double-consommation-concurrente"
if [[ "$(q "select state from normative_authority_decisions where id='$D11'")" != "APPROVED" ]]; then
  troue double-consommation-concurrente "aucune decision approuvee a consommer."
else
  BAR2=80000000002
  if barriere_prendre "$BAR2"; then
    for t in k1 k2; do
      ( exec {BAR_FD}>&-
        PGAPPNAME="FICTIF-4y-${t}-${JETON}" \
        svc -tAc "select pg_advisory_lock_shared($BAR2);
                  set eurostruct.actor_id = '$B';
                  select normative_decision_consume('$D11');" >/dev/null 2>&1 ) &
      CONCURRENTS+=("$!")
    done
    if attendre "2 consommations concurrentes bloquees sur $BAR2" \
         "(select count(*) from pg_stat_activity
            where application_name like 'FICTIF-4y-k%-${JETON}'
              and wait_event_type = 'Lock') = 2"; then
      barriere_lever; attendre_concurrents
      ET="$(q "select state from normative_authority_decisions where id='$D11'")"
      NC="$(q "select count(*) from audit_log
                where action='normative.decision.consumed'
                  and entity_id='$D11'")"
      detail "etat=$ET ; evenements de consommation: $NC"
      if [[ "$ET" == "CONSUMED" && "$NC" == "1" ]]; then
        sur double-consommation-concurrente "la consommation est unique et"
        detail "atomique: un seul evenement, malgre deux sessions relachees"
        detail "ensemble et OBSERVEES bloquees."
      elif [[ "$ET" != "CONSUMED" ]]; then
        troue double-consommation-concurrente "aucune n'a abouti (etat=$ET)."
      else
        rouge double-consommation-concurrente "$NC consommations pour une decision."
      fi
    else
      barriere_lever; attendre_concurrents
      troue double-consommation-concurrente "barriere jamais franchie."
    fi
  else
    barriere_lever
    troue double-consommation-concurrente "barriere non prise."
  fi
fi

# ==========================================================================
# 13. REJEU APRES CONSOMMATION
# ==========================================================================
echo "      -- rejeu-apres-consommation"
if [[ "$(q "select state from normative_authority_decisions where id='$D11'")" != "CONSUMED" ]]; then
  troue rejeu-apres-consommation "aucune decision consommee."
else
  R13="$(agir "$B" "select normative_decision_consume('$D11')")"
  NC="$(q "select count(*) from audit_log
            where action='normative.decision.consumed' and entity_id='$D11'")"
  if [[ "$NC" != "1" ]]; then
    rouge rejeu-apres-consommation "le rejeu a produit une seconde consommation."
  elif erreur_sql "$R13"; then
    sur rejeu-apres-consommation "le rejeu est refuse; aucune autorite n'est"
    detail "recreee. $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$R13")"
  else
    troue rejeu-apres-consommation "non interpretable."
  fi
fi

# ==========================================================================
# 14. REVOCATION ENTRE PROPOSITION ET APPROBATION
# ==========================================================================
echo "      -- revocation-avant-approbation"
GA2="$(octroyer "$A" BE 'EN 1993' '1-1' '2005' 'FICTIF autorite A revocable')"
GB2="$(octroyer "$B" BE 'EN 1993' '1-1' '2005' 'FICTIF autorite B revocable')"
if ! est_uuid "$GA2" || ! est_uuid "$GB2"; then
  troue revocation-avant-approbation "les habilitations n'ont pas ete creees."
else
  D14="$(agir "$A" "select normative_decision_propose(
           'regle_normative','s14',null,'BE'::country_code,'EN 1993','1-1',
           '2005','can_validate_normative_reference'::normative_permission,
           'FICTIF s14')" | tail -1 | tr -d ' ')"
  if ! est_uuid "$D14"; then
    troue revocation-avant-approbation "la proposition n'a pas abouti."
  else
    REVOUT="$(agir "$R" "insert into normative_authorisation_revocations
                           (grant_id, reason)
                         values ('$GA2', 'FICTIF revocation du proposant')")"
    REV="$(q "select count(*) from normative_authorisation_revocations where grant_id='$GA2'")"
    R14="$(agir "$B" "select normative_decision_approve('$D14')")"
    ET="$(q "select state from normative_authority_decisions where id='$D14'")"
    detail "revocation enregistree=$REV ; etat apres approbation=$ET"
    if [[ "$REV" != "1" ]]; then
      troue revocation-avant-approbation \
        "la revocation n'a pas abouti: $(tr '\n' ' ' <<<"$REVOUT" | head -c 160)"
    elif [[ "$ET" == "APPROVED" ]]; then
      rouge revocation-avant-approbation "une decision proposee sous une"
      detail "autorite depuis revoquee a ete approuvee."
    elif grep -qi "n'est plus efficace" <<<"$R14"; then
      sur revocation-avant-approbation "l'approbation est refusee quand"
      detail "l'habilitation du PROPOSANT a ete revoquee entre-temps."
    else
      troue revocation-avant-approbation "autre raison: $(head -c 120 <<<"$R14")"
    fi
  fi
fi

# ==========================================================================
# 15. REVOCATION PENDANT LA CONSOMMATION — barriere deterministe
# ==========================================================================
echo "      -- revocation-pendant-consommation"
GA3="$(octroyer "$A" BE 'EN 1994' '1-1' '2006' 'FICTIF autorite A course')"
GB3="$(octroyer "$B" BE 'EN 1994' '1-1' '2006' 'FICTIF autorite B course')"
D15=""
if est_uuid "$GA3" && est_uuid "$GB3"; then
  D15="$(agir "$A" "select normative_decision_propose(
           'regle_normative','s15',null,'BE'::country_code,'EN 1994','1-1',
           '2006','can_validate_normative_reference'::normative_permission,
           'FICTIF s15')" | tail -1 | tr -d ' ')"
  est_uuid "$D15" && agir "$B" "select normative_decision_approve('$D15')" >/dev/null 2>&1
fi
if ! est_uuid "$D15" \
   || [[ "$(q "select state from normative_authority_decisions where id='$D15'")" != "APPROVED" ]]; then
  troue revocation-pendant-consommation "aucune decision approuvee a eprouver."
else
  BAR3=80000000003
  APP_R="FICTIF-4y-rev-$JETON"; APP_C="FICTIF-4y-con-$JETON"; BLOQ=-1
  if barriere_prendre "$BAR3"; then
    # La revocation est PARQUEE, transaction ouverte et verrou de ligne en main.
    ( exec {BAR_FD}>&-
      PGAPPNAME="$APP_R" \
      svc -tAc "set eurostruct.actor_id = '$R';
                begin;
                insert into normative_authorisation_revocations (grant_id, reason)
                values ('$GB3', 'FICTIF revocation en vol');
                select pg_advisory_lock_shared($BAR3);
                commit;" >"/tmp/4y-rev-$JETON.log" 2>&1 ) &
    CONCURRENTS+=("$!")
    # LA SORTIE EST CONSERVEE, PAS JETEE. Quand la revocation echoue, elle ne
    # se pare jamais sur la barriere et le controle devient NON_PARCOURU sans
    # dire pourquoi: c'est ainsi qu'un refus RLS s'est cache une journee.
    if attendre "la revocation est EN VOL, parquee sur $BAR3" \
         "exists(select 1 from pg_stat_activity
                  where application_name='$APP_R' and wait_event_type='Lock')"; then
      ( exec {BAR_FD}>&-
        PGAPPNAME="$APP_C" \
        svc -tAc "set eurostruct.actor_id = '$B';
                  select normative_decision_consume('$D15');" >/dev/null 2>&1 ) &
      CONCURRENTS+=("$!")
      if attendre "la consommation est BLOQUEE par la revocation en vol" \
           "exists(select 1 from pg_stat_activity
                    where application_name='$APP_C' and wait_event_type='Lock')"; then
        BLOQ=1
      else
        BLOQ=0
      fi
    fi
    barriere_lever; attendre_concurrents
  else
    barriere_lever
  fi
  REV="$(q "select count(*) from normative_authorisation_revocations where grant_id='$GB3'")"
  ET="$(q "select state from normative_authority_decisions where id='$D15'")"
  detail "revocation validee=$REV ; etat=$ET ; consommation bloquee=$BLOQ"
  MOTIF="$(tr '\n' ' ' < "/tmp/4y-rev-$JETON.log" 2>/dev/null | head -c 160)"
  if [[ "$BLOQ" == "-1" ]]; then
    troue revocation-pendant-consommation \
      "la course n'a pas pu etre montee: ${MOTIF:-<aucune sortie>}"
  elif [[ "$REV" != "1" ]]; then
    troue revocation-pendant-consommation \
      "la revocation n'a pas abouti: ${MOTIF:-<aucune sortie>}"
  elif [[ "$BLOQ" == "0" ]]; then
    rouge revocation-pendant-consommation "la consommation n'a JAMAIS attendu la"
    detail "revocation en vol: aucune exclusion mutuelle."
  elif [[ "$ET" == "CONSUMED" ]]; then
    rouge revocation-pendant-consommation "la decision a ete consommee alors que"
    detail "l'habilitation de l'approbateur venait d'etre revoquee."
  else
    sur revocation-pendant-consommation "la consommation a ete OBSERVEE bloquee,"
    detail "puis refusee: une source devenue inefficace arrete l'effet."
  fi
  rm -f "/tmp/4y-rev-$JETON.log"
fi

# ==========================================================================
# 16. INVOCATION SQL DIRECTE
# ==========================================================================
echo "      -- invocation-sql-directe"
R16="$(ord -tAc "set role normative_backend;
                 insert into normative_authority_decisions
                   (subject_kind, subject_id, country_code, standard_family,
                    part, edition, permission, proposer_id,
                    proposal_source_grant_id, reason)
                 values ('regle_normative','s16','BE','EN 1992','1-1','2004',
                         'can_validate_normative_reference','$A','$GA',
                         'FICTIF direct')" 2>&1)"
N="$(q "select count(*) from normative_authority_decisions where subject_id='s16'")"
if [[ "$N" != "0" ]]; then
  rouge invocation-sql-directe "une decision a ete inseree en contournant les"
  detail "primitives: l'acteur n'est plus derive."
elif grep -qiE 'permission denied' <<<"$R16"; then
  sur invocation-sql-directe "l'insertion directe est refusee: aucun role"
  detail "applicatif n'a de privilege sur la table des decisions."
  detail "non-vacuite: les primitives, elles, y ecrivent (controle 3)."
else
  troue invocation-sql-directe "autre raison: $(head -c 120 <<<"$R16")"
fi

# ==========================================================================
# 17. LES DEUX SOURCES SONT CONSERVEES, EXACTEMENT
# ==========================================================================
echo "      -- sources-conservees"
if ! est_uuid "$D1"; then
  troue sources-conservees "aucune decision approuvee a examiner."
else
  PS="$(q "select proposal_source_grant_id from normative_authority_decisions where id='$D1'")"
  AS_="$(q "select approval_source_grant_id from normative_authority_decisions where id='$D1'")"
  detail "source du proposant=$PS (attendu $GA) ; de l'approbateur=$AS_ (attendu $GB)"
  if [[ "$PS" == "$GA" && "$AS_" == "$GB" ]]; then
    sur sources-conservees "les DEUX sources d'autorite sont conservees, et ce"
    detail "sont exactement celles invoquees. Savoir QUI a decide sans savoir"
    detail "AU TITRE DE QUOI ne serait pas opposable."
  else
    rouge sources-conservees "sources enregistrees incorrectes."
  fi
fi

# ==========================================================================
# 18. AUDIT ET CORRELATION
# ==========================================================================
echo "      -- audit-correlation"
if ! est_uuid "$D1"; then
  troue audit-correlation "aucune decision a tracer."
else
  CO="$(q "select correlation_id from normative_authority_decisions where id='$D1'")"
  NP="$(q "select count(*) from audit_log where action='normative.decision.proposed'
            and entity_id='$D1' and payload->>'correlation_id'='$CO'")"
  NA="$(q "select count(*) from audit_log where action='normative.decision.approved'
            and entity_id='$D1' and payload->>'correlation_id'='$CO'")"
  detail "correlation=$CO ; evenements proposed=$NP approved=$NA"
  if [[ "$NP" == "1" && "$NA" == "1" ]]; then
    sur audit-correlation "proposition et approbation sont tracees, et portent"
    detail "la MEME correlation que la decision."
  else
    rouge audit-correlation "les evenements ne correlent pas (proposed=$NP approved=$NA)."
  fi
fi

# ==========================================================================
# 19. LE SOCLE EST FIGE — objet, portee, proposant, source, correlation
# ==========================================================================
# CES QUATRE CONTROLES INTERROGENT LES DECLENCHEURS, PAS LES PRIVILEGES, et
# c'est pourquoi ils s'executent sous le SUPERUTILISATEUR. Le modele de
# menace place les superutilisateurs hors perimetre pour les PRIVILEGES: ils
# satisfont `pg_has_role` partout et contournent RLS. Un declencheur, lui,
# s'applique a eux — et c'est exactement la garantie qu'on veut isoler ici.
#
# CE QU'ILS AJOUTENT. `check_normative_decision_transition()` et
# `forbid_decision_delete()` existaient depuis le premier jet de 0014, et
# AUCUN controle ne les exercait: quinze scenarios passaient par les trois
# primitives, qui ne tentent jamais ce que les declencheurs refusent. Une
# garantie que rien n'exerce ne se distingue plus d'une garantie perdue.
echo "      -- objet-fige"
DF="$(proposer s19 2004)"
if ! est_uuid "$DF"; then
  troue objet-fige "aucune decision a eprouver: $(head -c 100 <<<"$DF")"
else
  # AVANT: la photographie complete du socle. On la reprend APRES les six
  # tentatives, et on exige l'egalite — un refus qui laisserait passer une
  # colonne serait un refus qui ne protege rien.
  SOCLE_AV="$(q "select subject_kind||'|'||subject_id||'|'||coalesce(org_id::text,'-')
                      ||'|'||country_code||'|'||standard_family||'|'||part
                      ||'|'||edition||'|'||proposer_id||'|'||proposal_source_grant_id
                      ||'|'||correlation_id||'|'||reason
                   from normative_authority_decisions where id='$DF'")"
  OF_REFUS=0; OF_PASSE=""
  for col in "subject_id = 's19-modifie'" \
             "org_id = gen_random_uuid()" \
             "edition = '2099'" \
             "country_code = 'FR'::country_code" \
             "proposer_id = '$B'" \
             "correlation_id = gen_random_uuid()"; do
    RO="$(admb -tAc "update normative_authority_decisions set $col
                      where id='$DF'" 2>&1)"
    if grep -q "figes a la creation" <<<"$RO"; then
      OF_REFUS=$((OF_REFUS + 1))
    else
      OF_PASSE="$OF_PASSE [$col -> $(head -c 60 <<<"$RO" | tr '\n' ' ')]"
    fi
  done
  SOCLE_AP="$(q "select subject_kind||'|'||subject_id||'|'||coalesce(org_id::text,'-')
                      ||'|'||country_code||'|'||standard_family||'|'||part
                      ||'|'||edition||'|'||proposer_id||'|'||proposal_source_grant_id
                      ||'|'||correlation_id||'|'||reason
                   from normative_authority_decisions where id='$DF'")"
  detail "six tentatives sur le socle, refusees: $OF_REFUS/6"
  if [[ $OF_REFUS -ne 6 ]]; then
    rouge objet-fige "X1. une colonne du socle a ete modifiable:$OF_PASSE"
  elif [[ "$SOCLE_AV" != "$SOCLE_AP" ]]; then
    rouge objet-fige "X1. le socle a change malgre les refus:"
    detail "avant « $SOCLE_AV »"
    detail "apres « $SOCLE_AP »"
  else
    sur objet-fige "objet, organisation, portee, edition, proposant, source et"
    detail "correlation sont figes — et le socle est identique apres les six"
    detail "tentatives. Le refus nomme la colonne, il ne dit pas seulement non."
  fi
fi

echo "      -- transition-interdite"
# LES DEUX SENS EXIGENT DEUX DECISIONS D'ETATS DIFFERENTS. Sans la CONSUMED,
# seule la moitie du cycle serait eprouvee — et « il ne remonte pas » est
# precisement la moitie qu'on ne peut pas deduire de l'autre.
if ! est_uuid "$DF" || ! est_uuid "${D11:-}"; then
  troue transition-interdite "il manque une decision PENDING ou CONSUMED:"
  detail "PENDING=${DF:-(aucune)} ; CONSUMED=${D11:-(aucune)}"
else
  ET_AV="$(q "select state from normative_authority_decisions where id='$DF'")"
  # PENDING -> CONSUMED saute l'approbation: c'est la forme qui produirait une
  # decision consommee que PERSONNE n'a approuvee.
  T1="$(admb -tAc "update normative_authority_decisions
                      set state='CONSUMED'::normative_decision_state,
                          approver_id='$B'::uuid,
                          approval_source_grant_id='$GB'::uuid,
                          approved_at=now(), consumed_at=now()
                    where id='$DF'" 2>&1)"
  # CONSUMED -> APPROVED remonterait le cycle: une decision deja produite
  # redeviendrait consommable.
  T2="$(admb -tAc "update normative_authority_decisions
                      set state='APPROVED'::normative_decision_state,
                          consumed_at=null
                    where id='$D11'" 2>&1)"
  ET_AP="$(q "select state from normative_authority_decisions where id='$DF'")"
  ET11="$(q "select state from normative_authority_decisions where id='$D11'")"
  detail "PENDING->CONSUMED: $(grep -m1 -oiE 'interdite|figes a la creation|ERROR[^|]{0,40}' <<<"$T1" | head -1)"
  detail "CONSUMED->APPROVED: $(grep -m1 -oiE 'interdite|figes a la creation|ERROR[^|]{0,40}' <<<"$T2" | head -1)"
  detail "etats apres: $DF=$ET_AP (avant $ET_AV) ; $D11=$ET11"
  if [[ "$ET_AP" != "PENDING" || "$ET11" != "CONSUMED" ]]; then
    rouge transition-interdite "X2. un etat a ete force: $DF=$ET_AP, $D11=$ET11"
  elif grep -q "interdite" <<<"$T1" && grep -q "interdite" <<<"$T2"; then
    sur transition-interdite "le cycle ne se saute pas et ne remonte pas: les"
    detail "deux transitions illegales sont refusees et nommees."
  else
    troue transition-interdite "refus non interpretables:"
    detail "$(head -c 100 <<<"$T1") / $(head -c 100 <<<"$T2")"
  fi
fi

echo "      -- approbation-non-rejouee"
if ! est_uuid "$D1"; then
  troue approbation-non-rejouee "aucune decision APPROVED a eprouver."
else
  AP_AV="$(q "select approver_id||'|'||approval_source_grant_id
                from normative_authority_decisions where id='$D1'")"
  RA="$(admb -tAc "update normative_authority_decisions
                      set state='CONSUMED'::normative_decision_state,
                          consumed_at=now(), approver_id='$C'::uuid
                    where id='$D1'" 2>&1)"
  AP_AP="$(q "select approver_id||'|'||approval_source_grant_id
                from normative_authority_decisions where id='$D1'")"
  ET1="$(q "select state from normative_authority_decisions where id='$D1'")"
  detail "tentative: $(grep -m1 -oiE 'ne modifie pas l.{0,3}approbation|ERROR[^|]{0,50}' <<<"$RA" | head -1)"
  detail "approbation avant « $AP_AV » ; apres « $AP_AP » ; etat=$ET1"
  if [[ "$AP_AV" != "$AP_AP" || "$ET1" == "CONSUMED" ]]; then
    rouge approbation-non-rejouee "X3. la consommation a pu reecrire l'approbation."
  elif grep -qi "ne modifie pas l" <<<"$RA"; then
    sur approbation-non-rejouee "la consommation ne reecrit pas l'approbation:"
    detail "changer d'approbateur en consommant est refuse, et nomme."
  else
    troue approbation-non-rejouee "refus non interpretable: $(head -c 110 <<<"$RA")"
  fi
fi

echo "      -- suppression-refusee"
if ! est_uuid "$DF"; then
  troue suppression-refusee "aucune decision a eprouver."
else
  NAV="$(q "select count(*) from normative_authority_decisions")"
  RD="$(admb -tAc "delete from normative_authority_decisions where id='$DF'" 2>&1)"
  NAP="$(q "select count(*) from normative_authority_decisions")"
  detail "lignes avant=$NAV apres=$NAP ; $(grep -m1 -oiE 'ne s.{0,3}efface pas|ERROR[^|]{0,50}' <<<"$RD" | head -1)"
  if [[ "$NAV" != "$NAP" ]]; then
    rouge suppression-refusee "X4. une decision a ete effacee: la preuve de ce qui"
    detail "a ete engage disparait avec elle."
  elif grep -qi "efface pas" <<<"$RD"; then
    sur suppression-refusee "une decision ne s'efface pas, meme par le"
    detail "superutilisateur: le declencheur s'applique a lui aussi."
  else
    troue suppression-refusee "refus non interpretable: $(head -c 110 <<<"$RD")"
  fi
fi

# ==========================================================================
# 20. DEUX AUTHENTIFICATIONS INDEPENDANTES — ce que le depot ne peut pas prouver
# ==========================================================================
# CE CONTROLE NE SE DECLARE PAS VERT PAR COMPLAISANCE, ET NE SE DECLARE PAS
# ROUGE NON PLUS. Tout ce qui precede a ete obtenu avec un contexte d'acteur
# POSE par le backend authentifie. Cela eprouve le CONTRAT — la base refuse
# bien deux fois le meme principal, exige deux sources, et les conserve — mais
# ne prouve pas que les deux identites correspondent a deux authentifications
# reelles: aucun verificateur de jeton n'existe dans ce depot.
#
# Une connexion de pool sert legitimement plusieurs utilisateurs successifs:
# compter des connexions ne prouverait rien de plus.
echo "      -- deux-authentifications"
CONF="$(q "select normative_authentication_configured()")"
LOGINS="$(q "select coalesce(valeur,'(vide)') from normative_authentication_contract
              where nom='eurostruct.authority_backend_logins'")"
detail "authentificateur declare: $CONF ($LOGINS)"
detail "BLOCKED_BY_REAL_AUTH — ce qui est eprouve ici est le CONTRAT: deux"
detail "principals distincts, deux sources couvrantes, conservees et"
detail "confrontees. Ce qui ne peut PAS l'etre, faute de verificateur de jeton"
detail "dans ce depot, c'est que ces deux identites proviennent de deux"
detail "authentifications REELLES et independantes."
if [[ "$CONF" == "t" ]]; then
  bloque deux-authentifications "le contrat est eprouve; l'authentification"
  detail "elle-meme reste BLOCKED_BY_REAL_AUTH et n'est pas revendiquee."
else
  troue deux-authentifications "aucun authentificateur declare: meme le contrat"
  detail "n'a pas pu etre eprouve."
fi

# ==========================================================================
verdicts_verifier || true
echo ""
echo "      barrieres (mecanisme deterministe, aucun sleep d'ordonnancement):"
if ((${#BARRIERES[@]} == 0)); then echo "                (aucune)"
else printf '                %s\n' "${BARRIERES[@]}"; fi
verdicts_resume "6.3c — quatre-yeux explicite"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Le quatre-yeux explicite tient (contrat; authentification BLOCKED_BY_REAL_AUTH)."
  exit 0
fi
exit 1
