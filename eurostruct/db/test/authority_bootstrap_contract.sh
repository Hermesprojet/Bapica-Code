#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3c: LE CONTRAT D'AMORCAGE DE LA RACINE
#
#   db/test/authority_bootstrap_contract.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# L'attaque 1 de `authority_root_of_trust.sh` a mesure ceci: un membre de
# `eurostruct_deployment` nommait le premier administrateur normatif en
# choisissant librement `p_grantee`. Une identite TECHNIQUE — celle qui
# applique un schema — se convertissait en autorite PROFESSIONNELLE par le seul
# choix d'un parametre.
#
# 0013 le ferme: `p_grantee` n'est plus un choix mais une ASSERTION, confrontee
# a un MANDAT declare hors du systeme. Le detenteur de `eurostruct_deployment`
# declenche toujours l'amorcage — c'est son travail — mais il EXECUTE une
# decision prise ailleurs.
#
# DEUX DECORS, ET C'EST LE POINT DELICAT
# ---------------------------------------
#   * DECOR « SANS MANDAT » — aucun `eurostruct.bootstrap_mandate` declare.
#     C'est l'etat de ce depot: aucune source externe de mandat n'y existe.
#     L'amorcage doit refuser avec `BOOTSTRAP_AUTHORITY_NOT_CONFIGURED`, et ce
#     refus est la GARANTIE, pas un defaut de configuration du test.
#   * DECOR « AVEC MANDAT FICTIF » — un mandat est declare pour pouvoir
#     eprouver ce que le contrat autorise et ce qu'il refuse. Le mandat est
#     litteralement marque FICTIF: aucun document reel n'existe, et aucun n'est
#     invente.
#
# UN SEUL DES DEUX SUFFIRAIT A SE TROMPER. Sans le premier, on ne saurait pas
# que l'absence de mandat ferme reellement. Sans le second, tous les controles
# se refuseraient pour la meme raison et n'etabliraient rien d'autre.
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

PREFIXE="${1:?usage: authority_bootstrap_contract.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_bootstrap_contract.sh" || exit 2
harnais_verrou_prendre  "authority_bootstrap_contract.sh" || exit $?
exiger_cluster_jetable  "authority_bootstrap_contract.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "authority_bootstrap_contract.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

verdicts_declarer \
  sans-mandat mandat-respecte grantee-different acteur-non-preautorise \
  role-ordinaire concurrence-unique rejeu audit-du-mandat

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
ord()  { PGUSER="$ORD" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }
est_uuid() {
  [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]
}

MANDATE="11111111-2222-3333-4444-555555555555"
INTRUS="99999999-8888-7777-6666-555555555555"

# `decor_poser <suffixe> <mandat-ou-vide>`
decor_poser() {
  local s="$1" mandat="$2" f sortie m etat
  # LE TEARDOWN EST ARME AVANT LA PREMIERE CREATION. Mesure faite sur
  # `authority_closure.sh`: les chemins de refus ci-dessous rendaient 1 sans
  # rien defaire, un seul refus laissait les roles canoniques dans le cluster,
  # et TOUS les decors suivants echouaient en « phase 0 refusee ».
  esc_decor_ouvrir "$s" decor_deposer || { echoue "decor: armement refuse"; return 1; }

  MIG="${PREFIXE}_m${s}_${JETON}"; CTL="${PREFIXE}_c${s}_${JETON}"
  SVC="${PREFIXE}_s${s}_${JETON}"; ORD="${PREFIXE}_o${s}_${JETON}"
  BASE="${PREFIXE}_d${s}_${JETON}"; MDP="FICTIF-bs-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" || { esc_decor_abandonner; return 1; }
  creer_role "$CTL" "login password '$MDP' createrole"          || { esc_decor_abandonner; return 1; }
  creer_role "$SVC" "login password '$MDP'"                     || { esc_decor_abandonner; return 1; }
  creer_role "$ORD" "login password '$MDP'"                     || { esc_decor_abandonner; return 1; }
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  creer_base "$BASE" "owner \"$MIG\"" || { esc_decor_abandonner; return 1; }
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
    echoue "decor $s: phase 0: $(grep -m1 ERROR <<<"$sortie" | cut -c1-160)"
    esc_decor_abandonner; return 1
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
  # LE MANDAT — ou son ABSENCE, qui est le sujet du premier decor.
  if [[ -n "$mandat" ]]; then
    adm -c "alter database \"$BASE\"
              set eurostruct.bootstrap_mandate = '$mandat';" >/dev/null 2>&1
  fi
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      echoue "decor $s: phase 1 sur $(basename "$f"):"
      esc_diag_rapporter "decor $s / phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
      esc_decor_abandonner; return 1
    fi
  done
  m=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
  sortie=$(ctl -tAc "select normative_finalize_deployment($(esc_litteral "$m"))" 2>&1)
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "ACTIVE" ]]; then
    echoue "decor $s: finalisation -> $etat"
    esc_diag_rapporter "decor $s / finalisation" "$sortie"
    esc_decor_abandonner; return 1
  fi
  # PAR LE PLAN DE CONTROLE, qui detient l'ADMIN depuis que la phase 0 cree
  # le role. En superutilisateur, on masquerait le fait qu'il en est capable —
  # et c'est precisement ce que le controle « migrateur-non-membre » oppose.
  ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$ORD\";" >/dev/null 2>&1
  admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$MANDATE'), ('$INTRUS')
on conflict do nothing;
SQL
  return 0
}

decor_deposer() {
  local r ko=0
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || { NETTOYAGE_KO=1; ko=1; }
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1 || ko=1
    TOUS+=("$r")
  done
  # REND SON CODE. `esc_decor_fermer` le lit: un teardown qui echoue en
  # silence est la meme faute qu'un teardown absent. Seul le `drop role` fait
  # foi — `drop owned by` echoue normalement sur un role canonique jamais cree.
  return $ko
}

NETTOYAGE_KO=0
TOUS=()
CANAUX_RACINE="$(mktemp -d)"
BARRIERES=(); BAR_FD=""; BAR_PID=""; BAR_FIFO=""; CONCURRENTS=()

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
  PGAPPNAME="FICTIF-bs-bar-$JETON" psql -X -q -d "$BASE" -f "$BAR_FIFO" \
    >/dev/null 2>&1 &
  BAR_PID=$!
  exec {BAR_FD}>"$BAR_FIFO"
  printf 'select pg_advisory_lock(%s);\n' "$cle" >&"$BAR_FD"
  attendre "le harnais detient la barriere $cle" \
    "exists(select 1 from pg_locks l join pg_stat_activity a on a.pid = l.pid
             where l.locktype = 'advisory' and l.granted
               and a.application_name = 'FICTIF-bs-bar-$JETON')"
}
barriere_lever() {
  [[ -n "$BAR_FD" ]] || return 0
  printf 'select pg_advisory_unlock_all();\n\\q\n' >&"$BAR_FD" 2>/dev/null
  exec {BAR_FD}>&-
  wait "$BAR_PID" 2>/dev/null
  rm -f "$BAR_FIFO"; BAR_FD=""; BAR_PID=""; BAR_FIFO=""
}
attendre_concurrents() {
  local p
  for p in "${CONCURRENTS[@]}"; do wait "$p" 2>/dev/null; done
  CONCURRENTS=()
}

sortie_propre() {
  local r
  [[ -z "$BAR_FD" ]]  || exec {BAR_FD}>&-
  [[ -z "$BAR_PID" ]] || kill "$BAR_PID" 2>/dev/null
  rm -rf "$CANAUX_RACINE"
  decor_deposer
  # CHEMINS DE SORTIE 3 ET 5 (erreur shell, echec dans le teardown): un decor
  # peut etre encore arme ici. `esc_decor_fermer` est idempotent — s'il a deja
  # ete appele il ne refait rien; sinon c'est LUI qui rend le decor.
  esc_decor_fermer
  (( ESC_DECOR_TEARDOWN_KO == 0 )) || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS[@]}"; do
    [[ -n "$r" ]] && registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "authority_bootstrap_contract.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: le contrat d'amorcage de la racine"

# ==========================================================================
# DECOR A — AUCUN MANDAT DECLARE. C'est l'etat de ce depot.
# ==========================================================================
echo "      -- sans-mandat: l'amorcage refuse-t-il quand rien ne l'autorise ?"
if ! decor_poser a ""; then
  troue sans-mandat "le decor sans mandat n'a pas pu etre pose."
else
  R="$(ctl -tAc "select bootstrap_normative_administrator(
        '$MANDATE'::uuid, 'FICTIF principal', 'FICTIF sans mandat')" 2>&1)"
  N="$(q "select count(*) from normative_authorisation_grants
           where origin = 'bootstrap'")"
  detail "octrois d'amorcage crees: $N"
  if [[ "$N" != "0" ]]; then
    rouge sans-mandat "un amorcage a abouti SANS mandat declare: l'identite de"
    detail "deploiement nomme encore librement la premiere autorite."
  elif grep -q 'BOOTSTRAP_AUTHORITY_NOT_CONFIGURED' <<<"$R"; then
    sur sans-mandat "l'amorcage refuse explicitement:"
    detail "BOOTSTRAP_AUTHORITY_NOT_CONFIGURED — et c'est la garantie, pas un"
    detail "defaut de configuration. Aucun mandat externe n'existe dans ce"
    detail "depot, donc aucune racine ne peut y etre ouverte."
  else
    troue sans-mandat "refuse, mais SANS l'etat explicite attendu:"
    detail "$(head -c 180 <<<"$R")"
  fi
  esc_decor_fermer
fi

# ==========================================================================
# DECOR B — MANDAT FICTIF DECLARE
# ==========================================================================
EMPREINTE="FICTIF-EMPREINTE-MANDAT-$JETON"
if ! decor_poser b "$MANDATE:$EMPREINTE"; then
  echoue "le decor avec mandat n'a pas pu etre pose: les controles restants"
  detail "ne sont pas parcourus."
  for c in mandat-respecte grantee-different acteur-non-preautorise \
           role-ordinaire concurrence-unique rejeu audit-du-mandat; do
    troue "$c" "decor absent."
  done
else

# --- 1. UN BENEFICIAIRE DIFFERENT DU PRINCIPAL MANDATE --------------------
# On l'eprouve AVANT le cas nominal: apres un amorcage reussi, tout refus
# pourrait venir de « un administrateur existe deja » et non du mandat.
echo "      -- grantee-different: p_grantee != principal preautorise"
R="$(ctl -tAc "select bootstrap_normative_administrator(
      '$INTRUS'::uuid, 'FICTIF intrus', 'FICTIF mauvais beneficiaire')" 2>&1)"
N="$(q "select count(*) from normative_authorisation_grants
         where origin = 'bootstrap'")"
if [[ "$N" != "0" ]]; then
  rouge grantee-different "un amorcage a nomme « $INTRUS » alors que le mandat"
  detail "preautorise « $MANDATE »."
elif grep -qi 'le mandat preautorise' <<<"$R"; then
  sur grantee-different "le beneficiaire est confronte au mandat et refuse."
  detail "non-vacuite: le principal mandate, lui, aboutit ci-dessous."
else
  troue grantee-different "refuse pour une autre raison: $(head -c 150 <<<"$R")"
fi

# --- 2. APPEL PAR UN ROLE ORDINAIRE ---------------------------------------
echo "      -- role-ordinaire: la primitive est-elle appelable sans deploiement ?"
R="$(ord -tAc "set role normative_backend;
               select bootstrap_normative_administrator(
                 '$MANDATE'::uuid, 'FICTIF ordinaire', 'FICTIF direct')" 2>&1)"
N="$(q "select count(*) from normative_authorisation_grants
         where origin = 'bootstrap'")"
if [[ "$N" != "0" ]]; then
  rouge role-ordinaire "un role applicatif a amorce la racine."
elif grep -qiE 'permission denied' <<<"$R"; then
  sur role-ordinaire "l'ACL d'execution refuse l'appel direct."
  detail "non-vacuite: le plan de controle, membre de eurostruct_deployment,"
  detail "atteint bien la primitive — c'est lui qui recoit les refus METIER."
else
  troue role-ordinaire "refuse pour une raison etrangere a l'ACL:"
  detail "$(head -c 150 <<<"$R")"
fi

# --- 3. DEUX AMORCAGES CONCURRENTS DU PRINCIPAL MANDATE -------------------
# Barriere deterministe: les deux sessions sont OBSERVEES bloquees, puis
# relachees ensemble. Aucun `sleep` n'ordonne quoi que ce soit.
echo "      -- concurrence-unique: deux amorcages simultanes, un seul succes"
BAR=79000000001
S1="$(mktemp -p "$CANAUX_RACINE")"; S2="$(mktemp -p "$CANAUX_RACINE")"
if barriere_prendre "$BAR"; then
  for t in b1 b2; do
    f="$S1"; [[ "$t" == "b2" ]] && f="$S2"
    ( exec {BAR_FD}>&-
      PGAPPNAME="FICTIF-bsc-${t}-${JETON}" \
      ctl -tAc "select pg_advisory_lock_shared($BAR);
                select bootstrap_normative_administrator(
                  '$MANDATE'::uuid, 'FICTIF concurrent',
                  'FICTIF amorcage concurrent');" >"$f" 2>&1 ) &
    CONCURRENTS+=("$!")
  done
  if attendre "2 amorcages concurrents bloques sur $BAR" \
       "(select count(*) from pg_stat_activity
          where application_name like 'FICTIF-bsc-%-${JETON}'
            and wait_event_type = 'Lock') = 2"; then
    barriere_lever; attendre_concurrents
    NB="$(q "select count(*) from normative_authorisation_grants
              where origin = 'bootstrap'")"
    NU="$(q "select count(*) from normative_bootstrap_mandate_use")"
    OK=0
    for f in "$S1" "$S2"; do
      est_uuid "$(tail -1 "$f" | tr -d ' ')" && OK=$((OK + 1))
    done
    detail "aboutis: $OK ; octrois d'amorcage: $NB ; consommations: $NU"
    if [[ "$NB" == "1" && "$NU" == "1" && "$OK" == "1" ]]; then
      sur concurrence-unique "exactement un amorcage aboutit sous concurrence"
      detail "reelle, et le mandat n'est consomme qu'une fois. Les deux"
      detail "sessions ont ete OBSERVEES bloquees avant d'etre relachees."
    elif [[ "$NB" == "0" ]]; then
      troue concurrence-unique "aucun n'a abouti: la course n'a rien exerce."
      detail "$(head -c 150 "$S1")"
    else
      rouge concurrence-unique "amorcages=$NB consommations=$NU aboutis=$OK:"
      detail "l'unicite ne tient pas sous concurrence."
    fi
  else
    barriere_lever; attendre_concurrents
    troue concurrence-unique "barriere jamais franchie."
  fi
else
  barriere_lever
  troue concurrence-unique "barriere non prise."
fi

# --- 4. LE CAS NOMINAL, CONSTATE APRES COUP -------------------------------
echo "      -- mandat-respecte: le principal mandate est-il bien devenu autorite ?"
GID="$(q "select grantee_id from normative_authorisation_grants
           where origin = 'bootstrap' limit 1")"
if [[ "$GID" == "$MANDATE" ]]; then
  sur mandat-respecte "l'autorite amorcee est le principal du mandat, et lui"
  detail "seul: $GID"
elif [[ -z "$GID" ]]; then
  troue mandat-respecte "aucun amorcage n'a abouti: rien a constater."
else
  rouge mandat-respecte "l'autorite amorcee ($GID) n'est pas le principal"
  detail "mandate ($MANDATE)."
fi

# --- 5. REJEU APRES CONSOMMATION ------------------------------------------
echo "      -- rejeu: le mandat consomme peut-il resservir ?"
R="$(ctl -tAc "select bootstrap_normative_administrator(
      '$MANDATE'::uuid, 'FICTIF rejeu', 'FICTIF rejeu du mandat')" 2>&1)"
NB="$(q "select count(*) from normative_authorisation_grants
          where origin = 'bootstrap'")"
NU="$(q "select count(*) from normative_bootstrap_mandate_use")"
detail "apres rejeu — octrois: $NB ; consommations: $NU"
if [[ "$NB" != "1" || "$NU" != "1" ]]; then
  rouge rejeu "le rejeu a produit un second amorcage (octrois=$NB, uses=$NU)."
elif grep -qiE 'ERROR|ERREUR' <<<"$R"; then
  sur rejeu "le rejeu est refuse, et rien n'a ete cree."
  detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,100}' <<<"$R")"
else
  troue rejeu "ni ecriture ni erreur: non interpretable."
fi

# --- 6. ACTEUR AUTHENTIFIE MAIS NON PREAUTORISE ---------------------------
# Le backend authentifie N'EST PAS le deploiement. Il peut poser un contexte
# d'acteur, il n'a pas EXECUTE sur la primitive d'amorcage: nommer la premiere
# autorite n'est pas une operation applicative.
echo "      -- acteur-non-preautorise: le backend authentifie peut-il amorcer ?"
R="$(svc -tAc "set eurostruct.actor_id = '$MANDATE';
               select bootstrap_normative_administrator(
                 '$MANDATE'::uuid, 'FICTIF backend', 'FICTIF par le backend')" 2>&1)"
if grep -qiE 'permission denied' <<<"$R"; then
  sur acteur-non-preautorise "le backend authentifie n'atteint pas la primitive"
  detail "d'amorcage: authentifier un acteur ne donne pas le droit d'ouvrir la"
  detail "racine. Non-vacuite: ce meme backend ECRIT des octrois delegues."
elif grep -qiE 'ERROR|ERREUR' <<<"$R"; then
  sur acteur-non-preautorise "refuse: $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,90}' <<<"$R")"
else
  rouge acteur-non-preautorise "le backend authentifie a pu amorcer la racine."
fi

# --- 7. L'AUDIT PORTE L'EMPREINTE DU MANDAT -------------------------------
# Sans elle, la decision n'est pas opposable: on saurait qu'un amorcage a eu
# lieu, pas AU TITRE DE QUOI.
echo "      -- audit-du-mandat: l'empreinte du mandat est-elle inscrite ?"
NA="$(q "select count(*) from audit_log
          where action = 'normative.authorisation.bootstrap'
            and payload ->> 'mandate_digest' = '$EMPREINTE'")"
NS="$(q "select count(*) from audit_log
          where action = 'normative.authorisation.bootstrap'
            and coalesce(payload ->> 'performed_by_session_user', '') <> ''")"
detail "evenements d'amorcage portant l'empreinte: $NA ; avec session_user: $NS"
if [[ "$NA" == "1" && "$NS" == "1" ]]; then
  sur audit-du-mandat "l'evenement d'amorcage porte l'empreinte du mandat ET"
  detail "le role reellement connecte. La decision est opposable."
elif [[ "$NA" == "0" ]]; then
  rouge audit-du-mandat "aucun evenement d'amorcage ne porte l'empreinte du"
  detail "mandat: on sait qu'un amorcage a eu lieu, pas au titre de quoi."
else
  troue audit-du-mandat "empreinte=$NA session_user=$NS: non interpretable."
fi

fi

# ==========================================================================
verdicts_verifier || true
echo ""
echo "      barrieres (mecanisme deterministe, aucun sleep d'ordonnancement):"
if ((${#BARRIERES[@]} == 0)); then echo "                (aucune)"
else printf '                %s\n' "${BARRIERES[@]}"; fi
verdicts_resume "6.3c — contrat d'amorcage"
if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Le contrat d'amorcage tient."
  exit 0
fi
exit 1
