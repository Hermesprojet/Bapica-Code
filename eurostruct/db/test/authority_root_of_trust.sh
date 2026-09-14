#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3c: LA RACINE DE CONFIANCE DES AUTORITES, MISE A L'EPREUVE
#
#   db/test/authority_root_of_trust.sh <prefixe-de-base-jetable>
#
# CE FICHIER EST UN LOT DE ROUGES. Il est ecrit AVANT toute correction, et il
# DOIT rougir. Un jalon qui commencerait par le correctif ne saurait pas ce
# qu'il a reellement ferme.
#
# CE QU'IL VISE
# --------------
# Tout le modele d'autorite normative derive l'identite de l'acteur d'UN SEUL
# point:
#
#     create function auth.uid() returns uuid as $$
#       select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
#     $$;
#
# `check_normative_grant()` fait `new.granted_by := auth.uid()`,
# `check_normative_grant_revocation()` fait `new.revoked_by := auth.uid()`,
# `check_normative_confirmation()` fait `new.verifier_id := auth.uid()`, et le
# decompte a quatre yeux compte des `verifier_id` DISTINCTS. Les quatre sont
# corrects — A CONDITION que `auth.uid()` dise la verite.
#
# Or `request.jwt.claim.sub` est un parametre de configuration APPLICATIF. En
# PostgreSQL, un GUC a nom qualifie est positionnable par TOUT role, par un
# simple `SET`. Aucun droit n'est requis. `auth.uid()` ne PROUVE donc rien: il
# RAPPORTE ce que la session a declare.
#
# CE QUE CE FICHIER N'EST PAS. Il n'est pas une critique de PostgREST, qui
# positionne ce GUC apres verification d'un JWT et fait donc son travail. Il
# etablit que la garantie repose ENTIEREMENT sur une propriete absente de la
# base — que seul le verificateur de jeton detienne la connexion — et que rien
# dans le schema ne la defend ni meme ne la declare.
#
# TROIS VERDICTS, ET LEUR SENS EXACT
# -----------------------------------
#   ROUGE   l'attaque a ABOUTI. L'invariant vise n'est pas defendu.
#   SUR     l'attaque a ete REFUSEE, et le refus est attribue a la protection
#           qu'on croyait presente — jamais a une autre.
#   ECHEC   le chemin d'attaque n'a pas ete ATTEINT: decor casse, refus pour
#           une raison etrangere, barriere jamais franchie. Un scenario non
#           parcouru n'est ni un rouge ni une assurance. C'est un trou.
#
# La distinction SUR / ECHEC est la lecon de 6.3b6e: UNE SURFACE NON EXECUTEE
# N'EST PAS UN VERDICT. Chaque « sur » ci-dessous porte donc sa preuve de
# NON-VACUITE — la demonstration que l'attaque est bien allee jusqu'au point
# ou la protection l'a arretee.
#
# LES ROUGES SONT COMPTES ET LE HARNAIS SORT EN 1. Meme convention que
# `authority_closure.sh`: « ROUGE ATTENDU (a fermer) » n'est pas un
# avertissement, c'est un echec qui attend son correctif.
#
# AUCUNE IDENTITE REELLE. Tous les UUID, noms et motifs sont FICTIFS, et la
# base est jetable: `exiger_cluster_jetable` le verifie avant toute ecriture.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): le harnais
# l'emprunte AUSSI, sans quoi il testerait un chemin que la production
# n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: authority_root_of_trust.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_root_of_trust.sh" || exit 2
harnais_verrou_prendre  "authority_root_of_trust.sh" || exit $?
exiger_cluster_jetable  "authority_root_of_trust.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)
exiger_roles_absents "authority_root_of_trust.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

# --------------------------------------------------------------------------
# LA COMPTABILITE DES VERDICTS — celle de `lib_harnais.sh`, et pas une copie
# --------------------------------------------------------------------------
# CE QUI A ETE MESURE ET QUI EST CORRIGE ICI. La premiere version comptait des
# APPELS, pas des attaques: l'attaque 10 bouclait sur `update` puis `delete` et
# emettait DEUX verdicts. Quatorze attaques rendaient donc « 4 rouges et
# 11 sures » — quinze. L'arithmetique le disait a chaque execution.
#
# UN COMPTEUR QUI PEUT MENTIR SUR SON PROPRE TOTAL N'ATTESTE RIEN DU PRODUIT.
# Le registre vit donc dans `lib_harnais.sh`, partage: un harnais ecrit demain
# ne peut pas redemarrer la meme derive dans son coin. Voir l'en-tete de la
# section « LA COMPTABILITE DES VERDICTS » de la bibliotheque pour les regles
# exactes — declaration prealable, statut unique, egalite verifiee.
ATTAQUES_DEFINIES=(1 2 3 4 5 6 7 8 9 10 11 12 13 14)
verdicts_declarer "${ATTAQUES_DEFINIES[@]}"

# LES POINTS QUE CE HARNAIS SAIT EMETTRE — ECRITS EN TOUTES LETTRES.
#
# La liste double `ATTAQUES_DEFINIES`, et c'est deliberе: le pre-vol lit ce
# fichier SANS l'executer, et ne verrait dans `"${ATTAQUES_DEFINIES[@]}"` que
# le texte d'une expansion. Une declaration que le pre-vol ne peut pas lire
# n'est pas une declaration — mesure du 29/08 sur
# `authority_role_frontier.sh`, ou la premiere redaction a fait refuser quatre
# controles. Le controle ci-dessous interdit aux deux listes de diverger.
esc_points_declares 1 2 3 4 5 6 7 8 9 10 11 12 13 14

if [[ "${ATTAQUES_DEFINIES[*]}" != "$(echo $ESC_POINTS_DECLARES)" ]]; then
  echo "REFUS: ATTAQUES_DEFINIES et esc_points_declares divergent." >&2
  echo "       attaques: ${ATTAQUES_DEFINIES[*]}" >&2
  echo "       declares:$ESC_POINTS_DECLARES" >&2
  exit 2
fi

KO=0
# Raccourcis lisibles sur les sites d'appel: l'identifiant de l'attaque est le
# nombre en tete du texte, ce qui evite de le repeter et donc de le desaccorder.
#
# ET C'EST AUSSI LE POINT DE CONTROLE. Le harnais le connait deja; il n'a pas
# a le faire redecouvrir dans sa propre prose par un traducteur.
rouge()        { verdict "${1%%.*}" ROUGE        "$@"
                 esc_point_rouge "${1%%.*}" nature=racine_atteinte \
                   detail="$*"; }
sur()          { verdict "${1%%.*}" SUR          "$@"; }
non_parcouru() { verdict "${1%%.*}" NON_PARCOURU "$@"; KO=1
                 esc_point_troue "${1%%.*}" "$*"; }
# `echoue` reste pour les fautes de DECOR, qui ne sont le verdict d'aucune
# attaque: un decor casse n'est pas un chemin non parcouru, c'est un harnais
# qui n'a pas pu commencer.
echoue()  { echo "      ECHEC: $*" >&2; KO=1; }
detail()  { echo "                $*"; }

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

# Trois identites metier. Elles n'ont AUCUN pouvoir en elles-memes: ce sont des
# lignes dans `auth.users`, c'est-a-dire exactement ce dont un attaquant
# dispose — des UUID.
RACINE="11111111-1111-1111-1111-111111111111"
COMPLICE="22222222-2222-2222-2222-222222222222"
TIERS="33333333-3333-3333-3333-333333333333"
# LE PRINCIPAL PREAUTORISE PAR LE MANDAT D'AMORCAGE. Depuis 0013, `p_grantee`
# n'est plus un choix: la primitive le confronte au mandat DECLARE. Le decor
# doit donc le declarer avant la phase 1, et c'est celui-la qui sera amorce.
MANDAT_PRINCIPAL="$RACINE"

# --------------------------------------------------------------------------
# LE DECOR — meme forme que `authority_closure.sh`, mene jusqu'a ACTIVE
# --------------------------------------------------------------------------
# Il faut ACTIVE et non PENDING: en PENDING toute ecriture normative est
# refusee par les declencheurs `normative_activation_required_*`, et les
# attaques porteraient alors sur un systeme ferme pour une raison etrangere a
# ce qu'on mesure. UN ROUGE OBTENU PAR LE MAUVAIS REFUS N'EST PAS UN ROUGE, et
# un « sur » obtenu ainsi est pire: il rassure a tort.
#
# LES SUFFIXES SONT EN MINUSCULES. PostgreSQL replie les identifiants non
# quotes; un suffixe majuscule produit un role introuvable a la connexion et un
# diagnostic sans rapport avec la cause (mesure en 6.3b6c).
decor_poser() {
  local s="$1" f sortie
  MIG="${PREFIXE}_m${s}_${JETON}"; CTL="${PREFIXE}_c${s}_${JETON}"
  SVC="${PREFIXE}_s${s}_${JETON}"; BASE="${PREFIXE}_d${s}_${JETON}"
  ORD="${PREFIXE}_o${s}_${JETON}"
  # LE MANDAT D'AMORCAGE, FICTIF. Forme « <principal>:<empreinte> ». Il tient
  # lieu, pour le test, de la decision prise hors du systeme; aucun document
  # reel n'existe et aucun n'est invente — l'empreinte est litteralement
  # marquee FICTIF.
  MANDAT="${MANDAT_PRINCIPAL}:FICTIF-EMPREINTE-DE-MANDAT-${JETON}"
  MDP="FICTIF-rt-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" \
    || { echoue "decor: creation du migrateur impossible"; return 1; }
  creer_role "$CTL" "login password '$MDP' createrole" \
    || { echoue "decor: creation du plan de controle impossible"; return 1; }
  creer_role "$SVC" "login password '$MDP'" \
    || { echoue "decor: creation du role de service impossible"; return 1; }
  creer_role "$ORD" "login password '$MDP'" \
    || { echoue "decor: creation du role applicatif ordinaire"; return 1; }
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  creer_base "$BASE" "owner \"$MIG\"" \
    || { echoue "decor: creation de la base impossible"; return 1; }
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

  # PHASE 0 — LE SCEAU, pose par le plan de controle (6.3b6c / 6.3b6d).
  if ! sortie=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
    echoue "decor: phase 0 refusee:"
    esc_diag_rapporter "decor / phase 0 (sceau)" "$sortie"
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

  # PHASE 1 — par le migrateur.
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      echoue "decor: phase 1 refusee sur $(basename "$f"):"
      esc_diag_rapporter "decor / phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
      return 1
    fi
  done

  # PHASE 2 — la finalisation, par le plan de controle.
  local m etat
  m=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
  sortie=$(ctl -tAc "select normative_finalize_deployment($(esc_litteral "$m"))" 2>&1)
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "ACTIVE" ]]; then
    echoue "decor: la finalisation n'aboutit pas a ACTIVE (obtenu: $etat)"
    esc_diag_rapporter "decor / finalisation" "$sortie"
    return 1
  fi

  # LE ROLE DE SERVICE RECOIT `normative_backend`. Ce n'est PAS un
  # affaiblissement pose pour les besoins du test: c'est la derive AUTORISEE
  # que le sceau documente explicitement (« accorder normative_backend a un
  # role de service nouvellement declare »), et c'est la seule facon dont un
  # backend applicatif reel atteint les tables normatives. Sans elle, les
  # attaques 4 a 14 se refuseraient toutes sur « permission denied to set
  # role », donc AVANT d'atteindre le moindre invariant d'autorite: onze faux
  # « surs » d'affilee.
  # LE BACKEND AUTHENTIFIE recoit le role d'EXECUTION privilegie; le role
  # ORDINAIRE ne recoit que `normative_backend`, qui depuis 0013 n'a plus
  # INSERT sur les tables d'autorite. C'est la separation que 6.3c pose.
  # PAR LE PLAN DE CONTROLE, qui detient l'ADMIN depuis que la phase 0 cree
  # le role. En superutilisateur, on masquerait le fait qu'il en est capable —
  # et c'est precisement ce que le controle « migrateur-non-membre » oppose.
  ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$SVC\";" >/dev/null 2>&1
  adm -c "grant normative_backend to \"$ORD\";" >/dev/null 2>&1
  if [[ "$(svc -tAc "select pg_has_role(session_user,
             'eurostruct_authority_backend', 'USAGE')" 2>&1 \
           | tail -1 | tr -d ' ')" != "t" ]]; then
    echoue "decor: le backend de service n'atteint pas le role d'execution"
    detail "privilegie: toutes les ecritures d'autorite seraient refusees pour"
    detail "une raison etrangere a ce qui est mesure."
    return 1
  fi
  if [[ "$(ord -tAc "select pg_has_role(session_user,
             'eurostruct_authority_backend', 'USAGE')" 2>&1 \
           | tail -1 | tr -d ' ')" != "f" ]]; then
    echoue "decor: le role applicatif ORDINAIRE atteint le role d'execution"
    detail "privilegie: la separation que 6.3c pose n'existe pas, et les"
    detail "attaques d'identite mesureraient la mauvaise session."
    return 1
  fi
  return 0
}

# --------------------------------------------------------------------------
# BARRIERES DETERMINISTES — aucune course prouvee par une temporisation
# --------------------------------------------------------------------------
# CE QU'UN PREMIER JET DE CE FICHIER FAISAIT, ET POURQUOI C'ETAIT FAUX:
#
#     admb -tAc "select pg_advisory_lock($BAR)" &   # puis wait
#
# Un verrou consultatif de SESSION meurt avec la session. `psql` rendait la
# main aussitot, le verrou tombait avant meme que les concurrents existent, et
# les deux partaient sans barriere. Le test n'aurait pas rougi a tort — il
# aurait mesure une course QUI N'A PAS EU LIEU, et conclu « sur ».
#
# LA FORME CORRECTE tient en trois pieces:
#
#   1. UN PORTEUR QUI DURE. `psql -f <tube>`: tant que le tube reste ouvert en
#      ecriture, la session vit, donc le verrou EXCLUSIF tient.
#   2. DES CONCURRENTS EN PARTAGE. `pg_advisory_lock_shared` bloque tant que
#      l'exclusif est detenu, et TOUS les partages sont accordes ENSEMBLE a sa
#      liberation. Un exclusif cote concurrents les serialiserait — la course
#      n'aurait toujours pas lieu.
#   3. UNE CONDITION OBSERVEE. On ne relache pas « au bout d'un moment »: on
#      relache quand `pg_stat_activity` montre les N concurrents REELLEMENT
#      bloques. Si cela n'arrive pas, la barriere ECHOUE bruyamment.
#
# Les `sleep 0.1` de `attendre` sont un PAS DE SCRUTATION, pas un
# ordonnancement: au bout du delai maximal une barriere prononce un echec la ou
# une temporisation continuait en silence.
#
# ---------------------------------------------------------------------------
# LA LEVEE NE PASSE PAS PAR LA FERMETURE DU TUBE. C'est un INTERBLOCAGE
# MESURE sur ce fichier, pas une precaution theorique.
#
# Un second jet levait la barriere en fermant le descripteur d'ecriture, pour
# donner EOF a `psql`. Or `exec {BAR_FD}>` alloue un descripteur ORDINAIRE, que
# les sous-shells lances ENSUITE heritent — et que `psql`, une fois execute,
# detient encore. Releve dans /proc pendant le blocage:
#
#     pid=20073 fd=4  flags:0100000   psql -f <tube>      (lecture)
#     pid=20080 fd=10 flags:0100001   sous-shell concurrent
#     pid=20081 fd=10 flags:0100001   sous-shell concurrent
#     pid=20082 fd=10 flags:0100001   psql du concurrent 1
#     pid=20084 fd=10 flags:0100001   psql du concurrent 2
#
# Quatre ecrivains survivants: fermer celui du parent ne produit AUCUN EOF. Le
# porteur ne sort pas, le verrou exclusif tient, les concurrents l'attendent, et
# ils attendent une liberation qui exige leur propre sortie. Attente circulaire,
# fabriquee par le harnais lui-meme.
#
# LA LEVEE EST DONC UN ORDRE EXPLICITE — `pg_advisory_unlock_all()` puis `\q` —
# envoye DANS le tube. Elle ne depend plus de qui d'autre le tient ouvert. Les
# sous-shells ferment en outre le descripteur herite: la fuite disparait a la
# source, et un futur retour a une levee par EOF ne reveillerait pas le meme
# interblocage.
# ---------------------------------------------------------------------------
BARRIERES=()
BAR_FD=""; BAR_PID=""; BAR_APP=""; BAR_FIFO=""
CANAUX_RACINE="$(mktemp -d)"

attendre() {                # attendre <description> <predicat-sql>
  local quoi="$1" sql="$2" i n
  for ((i = 0; i < 600; i++)); do   # 60 s au plus, jamais un succes muet
    n=$(admb -tAc "select ($sql)::int" 2>/dev/null | tr -d ' ')
    if [[ "$n" == "1" ]]; then
      BARRIERES+=("ATTEINTE|$quoi|essai=$((i + 1))")
      return 0
    fi
    sleep 0.1
  done
  BARRIERES+=("JAMAIS_ATTEINTE|$quoi|essais=600")
  echoue "barriere jamais atteinte: $quoi"
  return 1
}

barriere_prendre() {        # barriere_prendre <cle>
  local cle="$1"
  BAR_APP="FICTIF-bar-${cle}-${JETON}"
  BAR_FIFO="$CANAUX_RACINE/bar.$cle"
  mkfifo "$BAR_FIFO" || { echoue "barriere $cle: mkfifo refuse"; return 1; }
  PGAPPNAME="$BAR_APP" psql -X -q -d "$BASE" -f "$BAR_FIFO" >/dev/null 2>&1 &
  BAR_PID=$!
  # `psql` BLOQUE dans open() du tube tant qu'aucun ecrivain n'existe (fait
  # mesure en 6.3b6e: etat S, wchan=wait_for_partner). L'ouverture ci-dessous
  # est donc elle-meme un rendez-vous, pas une esperance.
  exec {BAR_FD}>"$BAR_FIFO"
  printf 'select pg_advisory_lock(%s);\n' "$cle" >&"$BAR_FD"
  attendre "le harnais detient la barriere $cle" \
    "exists(select 1 from pg_locks l join pg_stat_activity a on a.pid = l.pid
             where l.locktype = 'advisory' and l.granted
               and a.application_name = '$BAR_APP')"
}

barriere_attendre_concurrents() {   # <nombre> <motif-application_name>
  attendre "$1 concurrent(s) « $2 » bloque(s) sur la barriere" \
    "(select count(*) from pg_stat_activity
       where application_name like '$2' and wait_event_type = 'Lock') = $1"
}

# `attendre_concurrents_termines` — JAMAIS un `wait` NU.
#
# Second interblocage mesure sur ce fichier. `harnais_verrou_prendre` retient le
# verrou du harnais dans un COPROCESSUS qui vit toute l'execution
# (`coproc HARNAIS_VERROU { psql ...; }`, lib_harnais.sh:604). Un `wait` sans
# argument attend TOUS les travaux d'arriere-plan, celui-la compris: il ne rend
# donc jamais la main. Releve: la barriere etait correctement levee, les deux
# concurrents avaient fini, et le script restait bloque en `wait4()` sur le
# porteur du verrou.
#
# On n'attend donc que les PID qu'on a soi-meme lances.
CONCURRENTS=()
attendre_concurrents_termines() {
  local p
  for p in "${CONCURRENTS[@]}"; do wait "$p" 2>/dev/null; done
  CONCURRENTS=()
}

barriere_lever() {
  [[ -n "$BAR_FD" ]] || return 0
  # ORDRE EXPLICITE, pas EOF — voir l'interblocage mesure ci-dessus.
  printf 'select pg_advisory_unlock_all();\n\\q\n' >&"$BAR_FD" 2>/dev/null
  exec {BAR_FD}>&-
  wait "$BAR_PID" 2>/dev/null
  rm -f "$BAR_FIFO"
  BAR_FD=""; BAR_PID=""; BAR_FIFO=""
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
  harnais_postcondition_nettoyage "authority_root_of_trust.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" "$ORD" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    6.3c: la racine de confiance des autorites tient-elle ?"

if ! decor_poser a; then
  echoue "le decor n'a pas pu etre pose: AUCUNE attaque n'est evaluee."
  exit 1
fi

admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$RACINE'), ('$COMPLICE'), ('$TIERS')
on conflict do nothing;
SQL

# DEUX CHEMINS, ET LA DIFFERENCE EST TOUT LE SUJET DE 6.3c.
#
# `sql_svc` — le BACKEND AUTHENTIFIE. Il herite de
# `eurostruct_authority_backend`, seul role a detenir INSERT sur les tables
# d'autorite depuis 0013. Il ne fait PAS `set role normative_backend`: cela
# lui ferait perdre precisement le privilege qu'on veut exercer.
sql_svc() { svc -tAc "$1" 2>&1; }
# `sql_ord` — un role applicatif ORDINAIRE. C'est ce dont dispose un attaquant
# qui tient une connexion applicative: il peut poser tous les parametres de
# session qu'il veut, il n'a plus INSERT.
sql_ord() { ord -tAc "set role normative_backend; $1" 2>&1; }
est_uuid() {
  [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]
}
erreur_sql()     { grep -qiE 'ERROR|ERREUR|FATAL' <<<"$1"; }
# Le refus porte-t-il sur l'ACL, et non sur autre chose ? Sans cette
# distinction, un refus du a un decor casse se lirait comme une protection.
refus_de_droit() { grep -qiE 'permission denied|droit refuse|insufficient' <<<"$1"; }

# ==========================================================================
# 0. LA MATRICE DES PERMISSIONS, MESUREE — pas decrite
# ==========================================================================
# Elle est produite ICI, par le harnais, sur la base reellement deployee. Une
# matrice recopiee a la main dans un rapport n'est qu'une affirmation de plus.
echo "      -- 0. matrice des permissions observee"
detail "fonction | svc | backend | deploy | proprietaire | secdef"
admb -tA -F' | ' -v svc="$SVC" <<'SQL' 2>&1 | sed 's/^/                /'
select p.proname,
       has_function_privilege(:'svc',                  p.oid, 'EXECUTE'),
       has_function_privilege('normative_backend',     p.oid, 'EXECUTE'),
       has_function_privilege('eurostruct_deployment', p.oid, 'EXECUTE'),
       pg_get_userbyid(p.proowner),
       p.prosecdef
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'public'
   and p.proname in ('bootstrap_normative_administrator',
                     'log_normative_event',
                     'resolve_normative_authorisation',
                     'consume_normative_authorisation',
                     'normative_finalize_deployment')
 order by p.proname;
SQL
# LES PRIVILEGES DE TABLE, MESURES AUSSI — et pas seulement ceux des fonctions.
#
# POURQUOI CETTE LIGNE EXISTE. Une campagne de falsification a neutralise
# l'immuabilite en ajoutant `grant update, delete ... to normative_backend` a la
# fin de la migration. Le GRANT n'a RIEN accorde: a cet endroit du fichier la
# table appartient deja a `eurostruct_normative_writer`, et PostgreSQL repond a
# un GRANT sans droit par un WARNING, jamais par une erreur. La neutralisation
# a donc echoue en silence, le test 10 est reste « sur », et cela se lisait
# « la garde tient » alors que la garde n'avait pas ete touchee.
#
# C'est le meme faux vert que ce harnais traque, applique a la falsification
# elle-meme: une neutralisation non verifiee ne prouve rien. Les privilege sont
# donc AFFICHES a chaque execution — un volet de falsification qui ne les voit
# pas changer sait qu'il n'a rien neutralise.
detail "privileges de table de « normative_backend » sur les octrois:"
admb -tA -F' | ' <<'SQL' 2>&1 | sed 's/^/                /'
select 'select=' || has_table_privilege('normative_backend',
          'normative_authorisation_grants', 'SELECT')::text
    || ' insert=' || has_table_privilege('normative_backend',
          'normative_authorisation_grants', 'INSERT')::text
    || ' update=' || has_table_privilege('normative_backend',
          'normative_authorisation_grants', 'UPDATE')::text
    || ' delete=' || has_table_privilege('normative_backend',
          'normative_authorisation_grants', 'DELETE')::text
    || ' | proprietaire=' || pg_get_userbyid(c.relowner)
    || ' rls=' || c.relrowsecurity::text
    || ' force=' || c.relforcerowsecurity::text
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relname = 'normative_authorisation_grants';
SQL

# ==========================================================================
# 1. AUTO-AMORCAGE — l'identite TECHNIQUE se convertit en autorite METIER
# ==========================================================================
# L'ACL est correcte, et ce n'est pas le sujet: seul `eurostruct_deployment`
# peut appeler la primitive. LE DEFAUT EST QUE `p_grantee` EST LIBRE. Cette
# identite technique — celle qui applique un schema — choisit seule qui devient
# la premiere autorite NORMATIVE, et rien ne relie ce choix a une decision
# tracee hors du systeme.
echo "      -- 1. auto-amorcage: l'identite technique choisit-elle l'autorite ?"
#
# CE QUE CETTE ATTAQUE MESURAIT AVANT 0013, ET CE QU'ELLE MESURE MAINTENANT.
#
# Avant: `p_grantee` etait LIBRE. Un membre de `eurostruct_deployment` nommait
# qui il voulait premiere autorite normative, et l'attaque aboutissait — rouge.
#
# Apres 0013, `p_grantee` n'est plus un choix mais une ASSERTION confrontee au
# MANDAT declare. Le declenchement par le deploiement reste normal — c'est son
# travail — donc « l'amorcage a abouti » n'est plus en soi un defaut.
#
# L'INVARIANT I-1 SE REFORMULE DONC, et c'est le point delicat: ce qu'on refuse
# n'est pas l'amorcage, c'est qu'une identite TECHNIQUE en choisisse le
# beneficiaire. Le rouge est donc « un amorcage a abouti pour un beneficiaire
# QUE LE MANDAT NE DESIGNE PAS ». Le decor declare un mandat FICTIF sur
# « $MANDAT_PRINCIPAL »; l'attaque demande ce meme principal, et le verdict
# porte sur la CONFRONTATION, pas sur le succes.
#
# Le contrat complet de l'amorcage — absence de mandat, beneficiaire different,
# rejeu, concurrence, appel par un role ordinaire — est eprouve par
# `authority_bootstrap_contract.sh`, qui pose deux decors dont un SANS mandat.
R1="$(ctl -tAc "select bootstrap_normative_administrator(
        '$RACINE'::uuid, 'FICTIF racine', 'FICTIF amorcage mandate')" 2>&1)"
D1="$(tail -1 <<<"$R1" | tr -d ' ')"
MANDATE_EN_BASE="$(admb -tAc "select count(*) from normative_bootstrap_mandate_use" \
                   2>&1 | tr -d ' ')"
BENEF="$(admb -tAc "select grantee_id from normative_authorisation_grants
                     where origin = 'bootstrap' limit 1" 2>&1 | tr -d ' ')"
detail "1. amorcage: $D1 ; consommations de mandat: $MANDATE_EN_BASE"
detail "1. beneficiaire amorce: $BENEF ; principal mandate: $MANDAT_PRINCIPAL"
if est_uuid "$D1" && [[ "$BENEF" != "$MANDAT_PRINCIPAL" ]]; then
  rouge "1. un amorcage a abouti pour « $BENEF », que le mandat ne designe"
  detail "pas ($MANDAT_PRINCIPAL). Une racine de confiance TECHNIQUE se"
  detail "convertit en autorite PROFESSIONNELLE par le choix d'un parametre."
elif est_uuid "$D1" && [[ "$MANDATE_EN_BASE" == "1" ]]; then
  sur "1. l'amorcage n'aboutit qu'au principal DESIGNE PAR LE MANDAT, et"
  detail "consomme celui-ci. Le deploiement EXECUTE une decision prise"
  detail "ailleurs; il ne la prend pas."
  detail "non-vacuite: un beneficiaire different est refuse — mesure par"
  detail "authority_bootstrap_contract.sh, qui pose aussi un decor SANS mandat."
elif est_uuid "$D1"; then
  non_parcouru "1. amorcage abouti mais sans consommation de mandat"
  detail "($MANDATE_EN_BASE): l'etat n'est pas interpretable."
else
  sur "1. l'amorcage a ete refuse: $(head -c 160 <<<"$R1")"
fi

# ==========================================================================
# 2. AMORCAGE PAR UN ACTEUR NON AUTORISE
# ==========================================================================
echo "      -- 2. amorcage par un role sans eurostruct_deployment"
R2="$(sql_ord "select bootstrap_normative_administrator(
        '$TIERS'::uuid, 'FICTIF tiers', 'FICTIF non autorise')")"
if est_uuid "$(tail -1 <<<"$R2" | tr -d ' ')"; then
  rouge "2. un role SANS eurostruct_deployment a pu amorcer la racine."
elif refus_de_droit "$R2"; then
  sur "2. refuse par l'ACL d'execution (REVOKE ALL FROM PUBLIC + GRANT cible)"
  detail "non-vacuite: le MEME appel aboutit sous « $CTL » (attaque 1)."
else
  non_parcouru "2. refuse, mais pour une raison ETRANGERE a l'ACL — le chemin"
  detail "d'attaque n'a donc pas ete atteint: $(head -c 140 <<<"$R2")"
fi

# ==========================================================================
# 3. DEUX AMORCAGES CONCURRENTS — barriere deterministe, aucun `sleep`
# ==========================================================================
echo "      -- 3. deux amorcages concurrents (barriere par verrou partage)"
BAR1=77000000001
S1="$(mktemp -p "$CANAUX_RACINE")"; S2="$(mktemp -p "$CANAUX_RACINE")"
if barriere_prendre "$BAR1"; then
  for cible in "$COMPLICE:$S1:x1" "$TIERS:$S2:x2"; do
    u="${cible%%:*}"; reste="${cible#*:}"; f="${reste%%:*}"; tag="${reste##*:}"
    ( exec {BAR_FD}>&-        # ne pas retenir le tube de la barriere
      PGAPPNAME="FICTIF-c3-${tag}-${JETON}" \
      ctl -tAc "select pg_advisory_lock_shared($BAR1);
                select bootstrap_normative_administrator(
                  '$u'::uuid, 'FICTIF concurrent', 'FICTIF course');" \
        >"$f" 2>&1 ) &
    CONCURRENTS+=("$!")
  done
  if barriere_attendre_concurrents 2 "FICTIF-c3-%-${JETON}"; then
    barriere_lever
    attendre_concurrents_termines
    N3=0
    for f in "$S1" "$S2"; do
      est_uuid "$(tail -1 "$f" | tr -d ' ')" && N3=$((N3 + 1))
    done
    # NON-VACUITE. « 0 abouti » ne prouve pas l'unicite: il prouve que la
    # course n'a rien exerce. Le decompte total d'amorcages tranche.
    NB="$(admb -tAc "select count(*) from normative_authorisation_grants
                      where origin = 'bootstrap'" 2>&1 | tr -d ' ')"
    detail "3. concurrents aboutis: $N3 ; total origin='bootstrap' en base: $NB"
    if (( N3 >= 2 )); then
      rouge "3. $N3 amorcages concurrents ont abouti: la racine est dedoublee."
    elif [[ "$NB" == "1" ]]; then
      sur "3. l'unicite de l'amorcage tient sous concurrence reelle"
      detail "non-vacuite: les deux sessions ont ete OBSERVEES bloquees sur la"
      detail "barriere avant d'etre relachees ensemble."
    else
      non_parcouru "3. etat d'amorcage inattendu (total=$NB): verdict non concluant"
    fi
  else
    barriere_lever; attendre_concurrents_termines
    non_parcouru "3. la barriere n'a jamais ete franchie: aucune course."
  fi
else
  barriere_lever
  non_parcouru "3. la barriere n'a pas pu etre prise: aucune course."
fi

# L'ETAT DE REFERENCE pour la suite: un administrateur EXISTE.
ADMIN_ID="$(admb -tAc "select grantee_id from normative_authorisation_grants
                        where origin = 'bootstrap' order by granted_at limit 1" \
            2>&1 | tr -d ' ')"
if ! est_uuid "$ADMIN_ID"; then
  echoue "aucun administrateur amorce: les attaques 4 a 14 ne sont PAS evaluees."
  exit 1
fi
detail "administrateur normatif en place: $ADMIN_ID"

# L'OCTROI RACINE, ET NON PLUS SEULEMENT SON TITULAIRE. Depuis 0012, une
# delegation doit nommer l'habilitation PRECISE au titre de laquelle elle est
# consentie: « qui » a consenti ne dit pas « au titre de quoi ». Toutes les
# attaques qui deleguent le fournissent donc, faute de quoi elles se
# refuseraient sur l'absence de provenance — un refus etranger a ce qu'elles
# mesurent, et sept d'entre elles se sont effectivement declarees NON
# PARCOURUES lors du premier passage sous 0012.
GRANT_RACINE="$(admb -tAc "select id from normative_authorisation_grants
                            where origin = 'bootstrap' order by granted_at limit 1" \
                2>&1 | tr -d ' ')"
detail "octroi racine invoque par les delegations: $GRANT_RACINE"

# --------------------------------------------------------------------------
# LA CHAINE DE DELEGATION, posee explicitement et VERIFIEE
# --------------------------------------------------------------------------
# RACINE (portee generique, heritee de l'amorcage) delegue a COMPLICE une
# administration BORNEE a BE / EN 1992. Sans ce maillon:
#
#   * l'attaque 6 ne pourrait pas produire une SECONDE paternite, faute d'un
#     second acteur habilite — et se lirait « deja sur » alors que le refus
#     porterait sur la portee, pas sur l'identite;
#   * l'attaque 7 n'aurait aucune portee a amplifier;
#   * l'attaque 8 n'aurait aucune autorite a revoquer.
#
# Ces trois chemins etaient effectivement vides a la premiere execution. Le
# maillon est donc pose ICI, et son succes est une PRECONDITION verifiee: s'il
# echoue, les attaques concernees se declarent non parcourues au lieu de se
# declarer sures.
CHAINE_OK=0
GRANT_COMPLICE=""; GRANT_ED13=""; GRANT_C14=""
sql_svc "         set eurostruct.actor_id = '$ADMIN_ID';
         insert into normative_authorisation_grants
           (grantee_id, grantee_name, permission, country_code,
            standard_family, part, edition, reason, parent_grant_id)
         values ('$COMPLICE', 'FICTIF complice',
                 'can_manage_normative_authorisations',
                 'BE', 'EN 1992', null, null,
                 'FICTIF delegation bornee BE/EN 1992', '$GRANT_RACINE')" >/dev/null 2>&1
if [[ "$(admb -tAc "select count(*) from normative_authorisation_grants
                     where grantee_id = '$COMPLICE'
                       and permission = 'can_manage_normative_authorisations'" \
         2>&1 | tr -d ' ')" == "1" ]]; then
  CHAINE_OK=1
  GRANT_COMPLICE="$(admb -tAc "select id from normative_authorisation_grants
                                where reason = 'FICTIF delegation bornee BE/EN 1992'" \
                    2>&1 | tr -d ' ')"
  detail "chaine posee: $ADMIN_ID (generique) -> $COMPLICE (BE / EN 1992)"
  detail "habilitation de COMPLICE invoquee par 6, 7 et 8: $GRANT_COMPLICE"
else
  echoue "la delegation bornee vers « $COMPLICE » n'a pas ete creee:"
  detail "les attaques 6, 7 et 8 ne seront pas parcourues."
fi

# ==========================================================================
# 4. FALSIFICATION DE L'IDENTITE — le coeur du jalon
# ==========================================================================
# Le role de service ne fait ici RIEN d'autre que ce que tout code tenant la
# connexion peut faire: un `SET` sur un GUC a nom qualifie. Aucun droit n'est
# requis, et aucun n'est verifie.
#
# ON NE MESURE PAS `select auth.uid()`. Une premiere version le faisait et
# concluait « deja sur » sur:
#
#     ERROR: permission denied for schema auth
#
# C'ETAIT UN FAUX VERT, et le plus instructif du lot. `normative_backend` n'a
# pas USAGE sur le schema `auth`, donc il ne peut pas APPELER `auth.uid()`
# lui-meme — mais les declencheurs, eux, l'appellent, en SECURITY DEFINER sous
# un proprietaire qui a ce droit. Le refus mesurait l'ACL d'un schema, pas la
# solidite de l'identite. Preuve directe: l'attaque 5, au meme instant,
# recevait « 2222... ne peut pas s'octroyer » — le declencheur avait donc bien
# LU la valeur posee par la session.
#
# ON MESURE DONC L'EFFET, sur le chemin reel: une ecriture d'autorite, puis la
# valeur que le SERVEUR a inscrite dans `granted_by`.
echo "      -- 4. falsification de l'identite par un role ORDINAIRE"
R4="$(sql_ord "set eurostruct.actor_id = '$ADMIN_ID';
               insert into normative_authorisation_grants
                 (grantee_id, grantee_name, permission, country_code,
                  standard_family, part, edition, reason, parent_grant_id)
               values ('$TIERS', 'FICTIF cible 4',
                       'can_validate_normative_reference',
                       'BE', 'EN 1990', '1-1', '2002',
                       'FICTIF identite declaree', '$GRANT_RACINE')")"
G4="$(admb -tAc "select granted_by from normative_authorisation_grants
                  where reason = 'FICTIF identite declaree'" 2>&1 | tr -d ' ')"
if [[ "$G4" == "$ADMIN_ID" ]]; then
  rouge "4. le serveur a inscrit granted_by = « $ADMIN_ID » alors que la"
  detail "session n'a fourni que « SET eurostruct.actor_id ». L'identite est"
  detail "DECLAREE par la session, jamais prouvee, et tout le modele en derive:"
  detail "granted_by, revoked_by, verifier_id, et le decompte a quatre yeux."
  detail "INVARIANT ATTENDU (I-2): l'acteur provient d'un contexte que"
  detail "l'appelant ordinaire ne peut pas substituer."
elif [[ -n "$G4" ]]; then
  non_parcouru "4. granted_by inattendu (« $G4 »): resultat non interpretable."
else
  sur "4. un role applicatif ORDINAIRE qui declare une identite n'ecrit rien."
  detail "non-vacuite: la chaine de delegation, elle, a bien ete posee plus"
  detail "haut par le BACKEND AUTHENTIFIE, avec le meme acteur declare. Ce"
  detail "n'est donc pas la valeur qui est refusee, c'est la SESSION."
  detail "$(head -c 160 <<<"$R4")"
fi

# ==========================================================================
# 5. ACTOR == GRANTEE — l'auto-attribution
# ==========================================================================
echo "      -- 5. auto-attribution (acteur == beneficiaire)"
R5="$(sql_svc "               set eurostruct.actor_id = '$ADMIN_ID';
               insert into normative_authorisation_grants
                 (grantee_id, grantee_name, permission, country_code,
                  standard_family, part, edition, reason, parent_grant_id)
               values ('$ADMIN_ID', 'FICTIF auto',
                       'can_validate_normative_reference',
                       'BE', 'EN 1992', '1-1', '2004',
                       'FICTIF auto-attribution', '$GRANT_RACINE')")"
if grep -qi 'auto-attribution refusee' <<<"$R5"; then
  sur "5. auto-attribution refusee par check_normative_grant()"
  detail "non-vacuite: le MEME insert vers un AUTRE beneficiaire est exerce"
  detail "en 6 et ne rencontre pas ce refus."
elif erreur_sql "$R5"; then
  non_parcouru "5. refuse, mais PAS pour auto-attribution — chemin non atteint:"
  detail "$(head -c 200 <<<"$R5")"
else
  rouge "5. auto-attribution ACCEPTEE: un titulaire etend son propre pouvoir."
fi

# ==========================================================================
# 6. QUATRE-YEUX REDUITS A UN SEUL PRINCIPAL — le coeur de Q1
# ==========================================================================
# Le decompte se fait en `verifier_id` DISTINCTS, et `verifier_id` derive
# d'`auth.uid()`. UNE SEULE CONNEXION peut donc fabriquer deux « regards
# independants » en changeant de GUC entre les deux ecritures.
# CE QUI EST MESURE: deux ecritures d'autorite, dans UNE SEULE session, dont
# le serveur attribue la PATERNITE a deux principals DIFFERENTS — parce que la
# session a change de GUC entre les deux. C'est la premisse exacte du
# quatre-yeux: `independent_regards()` (confirmation.py) rend
# `frozenset(c.verifier_id ...)`, et `verifier_id` est derive d'`auth.uid()`
# par `check_normative_confirmation()` exactement comme `granted_by` l'est par
# `check_normative_grant()`. Deux `granted_by` distincts depuis une connexion
# demontrent donc la fabrication de deux « regards » sans deux personnes.
#
# On mesure sur les octrois et non sur les confirmations parce qu'une
# confirmation exige quatre payloads canoniques et leurs empreintes: le
# montage ne changerait pas la conclusion, il ajouterait seulement une
# machinerie ou l'erreur pourrait se cacher.
echo "      -- 6. deux paternites « independantes » depuis UNE connexion"
if [[ $CHAINE_OK -eq 0 ]]; then
  non_parcouru "6. la chaine de delegation manque: chemin non parcouru."
else
R6="$(sql_ord "set eurostruct.actor_id = '$ADMIN_ID';
               insert into normative_authorisation_grants
                 (grantee_id, grantee_name, permission, country_code,
                  standard_family, part, edition, reason, parent_grant_id)
               values ('$TIERS', 'FICTIF regard 1',
                       'can_validate_normative_reference',
                       'BE', 'EN 1992', '1-1', '2004', 'FICTIF regard 1', '$GRANT_RACINE');
               set eurostruct.actor_id = '$COMPLICE';
               insert into normative_authorisation_grants
                 (grantee_id, grantee_name, permission, country_code,
                  standard_family, part, edition, reason, parent_grant_id)
               values ('$TIERS', 'FICTIF regard 2',
                       'can_validate_normative_reference',
                       'BE', 'EN 1992', '1-1', '2005', 'FICTIF regard 2', '$GRANT_COMPLICE')")"
N6="$(admb -tAc "select count(distinct granted_by)
                   from normative_authorisation_grants
                  where reason in ('FICTIF regard 1', 'FICTIF regard 2')" \
      2>&1 | tr -d ' ')"
P6="$(admb -tAc "select coalesce(string_agg(distinct granted_by::text, ','), '-')
                   from normative_authorisation_grants
                  where reason in ('FICTIF regard 1', 'FICTIF regard 2')" \
      2>&1 | tr -d ' ')"
detail "6. paternites inscrites par le serveur: $P6"
if [[ "$N6" == "2" ]]; then
  rouge "6. deux paternites DISTINCTES ont ete inscrites depuis UNE SEULE"
  detail "connexion, par deux valeurs de GUC successives. Le decompte a quatre"
  detail "yeux compte des identifiants distincts derives de la meme source:"
  detail "deux ecritures du meme porteur de connexion suffisent a le remplir."
  detail "INVARIANT ATTENDU (I-3): deux regards exigent deux principals"
  detail "AUTHENTIFIES distincts, pas deux valeurs declarees."
elif [[ "$N6" == "0" ]]; then
  # AUCUNE ECRITURE N'A ABOUTI. Avant 0013 cela aurait ete un trou; ici c'est
  # la garantie elle-meme, a condition que la SESSION AUTORISEE, elle, ecrive.
  # C'est ce que le controle positif ci-dessous etablit — sans lui, un decor
  # casse se lirait comme une protection.
  TEMOIN6="$(sql_svc "set eurostruct.actor_id = '$ADMIN_ID';
                      insert into normative_authorisation_grants
                        (grantee_id, grantee_name, permission, country_code,
                         standard_family, part, edition, reason,
                         parent_grant_id)
                      values ('$TIERS', 'FICTIF temoin 6',
                              'can_validate_normative_reference',
                              'BE', 'EN 1992', '1-1', '2099',
                              'FICTIF temoin identite', '$GRANT_RACINE')")"
  NT6="$(admb -tAc "select count(*) from normative_authorisation_grants
                     where reason = 'FICTIF temoin identite'" 2>&1 | tr -d ' ')"
  detail "6. controle positif — la meme ecriture par le backend authentifie: $NT6"
  if [[ "$NT6" == "1" ]]; then
    sur "6. deux identites declarees depuis UNE connexion ORDINAIRE ne"
    detail "produisent AUCUNE paternite: le role applicatif n'a plus INSERT."
    detail "non-vacuite: la meme ecriture aboutit depuis le backend authentifie."
  else
    non_parcouru "6. ni l'attaque ni le controle positif n'ecrivent: le decor"
    detail "est en ecart, et le refus ne prouve rien. $(head -c 120 <<<"$TEMOIN6")"
  fi
else
  sur "6. le systeme n'a pas accepte deux paternites ainsi ($N6 distincte(s))"
  detail "$(head -c 180 <<<"$R6")"
fi
fi

# ==========================================================================
# 7. DELEGATION AU-DELA DU SCOPE DU GRANTOR
# ==========================================================================
# NON-VACUITE PREALABLE: « $COMPLICE » doit reellement detenir BE, et
# reellement ne pas detenir FR. Sans cette verification, un refus sur FR
# pourrait n'etre qu'un refus general de deleguer.
# LA NON-VACUITE EST UN CONTROLE POSITIF, pas une deduction. Avant de conclure
# qu'un refus sur FR protege la portee, on verifie que le MEME acteur, par le
# MEME chemin, REUSSIT sur BE. Sans cela, un refus general de deleguer se
# lirait comme un controle d'inclusion de portee.
echo "      -- 7. delegation hors du scope detenu par le grantor"
if [[ $CHAINE_OK -eq 0 ]]; then
  non_parcouru "7. la chaine de delegation manque: chemin non parcouru."
else
sql_svc "         set eurostruct.actor_id = '$COMPLICE';
         insert into normative_authorisation_grants
           (grantee_id, grantee_name, permission, country_code,
            standard_family, part, edition, reason, parent_grant_id)
         values ('$TIERS', 'FICTIF temoin BE',
                 'can_validate_normative_reference',
                 'BE', 'EN 1992', '1-1', '2006', 'FICTIF temoin de portee', '$GRANT_COMPLICE')" \
  >/dev/null 2>&1
TEMOIN7="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where reason = 'FICTIF temoin de portee'" 2>&1 | tr -d ' ')"
detail "7. controle positif — « $COMPLICE » delegue sur BE: $TEMOIN7 octroi"
if [[ "$TEMOIN7" != "1" ]]; then
  non_parcouru "7. le grantor ne parvient meme pas a deleguer DANS sa portee:"
  detail "un refus sur FR ne prouverait donc rien. Chemin non parcouru."
else
  R7="$(sql_svc "                 set eurostruct.actor_id = '$COMPLICE';
                 insert into normative_authorisation_grants
                   (grantee_id, grantee_name, permission, country_code,
                    standard_family, part, edition, reason, parent_grant_id)
                 values ('$TIERS', 'FICTIF hors scope',
                         'can_validate_normative_reference',
                         'FR', 'EN 1992', '1-1', '2004',
                         'FICTIF amplification', '$GRANT_COMPLICE')")"
  N7="$(admb -tAc "select count(*) from normative_authorisation_grants
                    where country_code = 'FR' and granted_by = '$COMPLICE'" \
        2>&1 | tr -d ' ')"
  if [[ "$N7" != "0" ]]; then
    rouge "7. « $COMPLICE », habilite sur BE / EN 1992, a delegue sur FR."
    detail "INVARIANT ATTENDU (I-5): granted_scope inclus dans grantor_scope."
  elif erreur_sql "$R7"; then
    sur "7. delegation hors scope refusee, alors que la meme delegation DANS"
    detail "la portee vient d'aboutir (controle positif ci-dessus)."
    detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,120}' <<<"$R7")"
  else
    non_parcouru "7. ni ecriture ni erreur: resultat non interpretable."
  fi
fi
fi

# ==========================================================================
# 8. DELEGATION APRES REVOCATION
# ==========================================================================
echo "      -- 8. delegation par une autorite deja revoquee"
# C'EST L'OCTROI D'ADMINISTRATION DE COMPLICE QU'ON RETIRE — celui qui lui
# donne le pouvoir de deleguer. Retirer un octroi de VERIFICATION ne dirait
# rien de sa capacite a deleguer, et le test aurait mesure autre chose.
GID="$(admb -tAc "select id from normative_authorisation_grants
                   where grantee_id = '$COMPLICE'
                     and permission = 'can_manage_normative_authorisations'
                   limit 1" 2>&1 | tr -d ' ')"
if ! est_uuid "$GID"; then
  non_parcouru "8. aucun octroi a revoquer: le chemin n'est pas exerce."
else
  REV8="$(sql_svc "                   set eurostruct.actor_id = '$ADMIN_ID';
                   insert into normative_authorisation_revocations
                     (grant_id, reason)
                   values ('$GID', 'FICTIF revocation')")"
  EST_REV="$(admb -tAc "select count(*) from normative_authorisation_revocations
                         where grant_id = '$GID'" 2>&1 | tr -d ' ')"
  if [[ "$EST_REV" != "1" ]]; then
    non_parcouru "8. la revocation prealable a echoue — chemin non atteint:"
    detail "$(head -c 180 <<<"$REV8")"
  else
    R8="$(sql_svc "                   set eurostruct.actor_id = '$COMPLICE';
                   insert into normative_authorisation_grants
                     (grantee_id, grantee_name, permission, country_code,
                      standard_family, part, edition, reason, parent_grant_id)
                   values ('$TIERS', 'FICTIF post-revocation',
                           'can_validate_normative_reference',
                           'BE', 'EN 1992', '1-1', '2004',
                           'FICTIF apres revocation', '$GRANT_COMPLICE')")"
    N8="$(admb -tAc "select count(*) from normative_authorisation_grants
                      where reason = 'FICTIF apres revocation'" 2>&1 | tr -d ' ')"
    if [[ "$N8" != "0" ]]; then
      rouge "8. une autorite REVOQUEE a delegue: la revocation ne ferme pas"
      detail "le pouvoir qu'elle pretend retirer."
    elif erreur_sql "$R8"; then
      sur "8. delegation post-revocation refusee"
      detail "non-vacuite: l'octroi $GID porte bien une revocation."
    else
      non_parcouru "8. ni ecriture ni erreur: resultat non interpretable."
    fi
  fi
fi

# ==========================================================================
# 9. INVOCATION DIRECTE D'UNE PRIMITIVE PRIVILEGIEE
# ==========================================================================
# `log_normative_event()` est SECURITY DEFINER et appartient a
# `eurostruct_normative_writer`: c'est le SEUL producteur autorise d'evenements
# « normative.* ». Si le role applicatif l'appelle, il FORGE une preuve.
echo "      -- 9. invocation directe de log_normative_event par le role applicatif"
R9="$(sql_svc "               select log_normative_event('normative.FICTIF.forge',
                 'normative_authorisation_grants', gen_random_uuid(),
                 '{}'::jsonb, null)")"
N9="$(admb -tAc "select count(*) from audit_log
                  where action = 'normative.FICTIF.forge'" 2>&1 | tr -d ' ')"
if [[ "$N9" != "0" ]]; then
  rouge "9. le role applicatif a INSCRIT un evenement « normative.* »:"
  detail "une preuve d'audit est FORGEABLE par le porteur de la connexion."
elif refus_de_droit "$R9"; then
  sur "9. la primitive privilegiee refuse l'appel direct (ACL d'execution)"
elif erreur_sql "$R9"; then
  sur "9. l'appel direct est refuse: $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,90}' <<<"$R9")"
else
  non_parcouru "9. appel sans erreur ET sans trace: resultat non interpretable."
fi

# ==========================================================================
# 10. ECRITURE DIRECTE SUR L'HISTORIQUE D'AUTORITE
# ==========================================================================
echo "      -- 10. UPDATE / DELETE directs sur les octrois"
#
# UN SEUL VERDICT POUR DEUX SOUS-OBSERVATIONS. La premiere version bouclait sur
# les deux ordres et emettait un verdict par tour: quatorze attaques rendaient
# quinze verdicts, et « 4 rouges + 11 sures » n'additionnait pas a 14.
#
# LES DEUX ORDRES SONT SANS CLAUSE `WHERE`, ET C'EST LE POINT DELICAT.
#
# Une version intermediaire visait une ligne precise — `where id = '...'` — pour
# isoler l'immuabilite de la cle etrangere. Elle a produit un refus, donc un
# « sur », et la falsification n'arrivait pas a le rendre rouge meme apres avoir
# leve le privilege, la RLS ET le declencheur. La matrice mesuree a tranche:
#
#     select=false insert=true update=true delete=true
#
# `normative_backend` n'a pas SELECT sur cette table. Or un `UPDATE ... WHERE`
# doit LIRE la colonne du predicat: le « permission denied » venait du SELECT
# implicite, pas de la garde d'immuabilite. Le test aurait continue de passer
# au vert si UPDATE avait ete accorde par megarde — il ne mesurait pas ce qu'il
# annoncait.
#
# Sans `WHERE`, l'ordre n'exige QUE le privilege d'ecriture. Un refus atteste
# alors exactement ce qu'on veut atteste: le role applicatif ne peut ni
# reecrire ni effacer l'historique d'autorite.
AVANT10="$(admb -tAc "select count(*) from normative_authorisation_grants" \
           2>&1 | tr -d ' ')"
RU="$(sql_svc "               update normative_authorisation_grants
                  set reason = 'FICTIF reecrit'")"
EFFET_U="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where reason = 'FICTIF reecrit'" 2>&1 | tr -d ' ')"
RD="$(sql_svc "               delete from normative_authorisation_grants")"
RESTE_D="$(admb -tAc "select count(*) from normative_authorisation_grants" \
           2>&1 | tr -d ' ')"

classer10() {              # classer10 <sortie> <effet: oui|non>
  if [[ "$2" == "oui" ]]; then echo REECRIT
  elif refus_de_droit "$1" || erreur_sql "$1"; then echo REFUS
  else echo SANS_EFFET; fi
}
[[ "$EFFET_U" == "0" ]] && EU=non || EU=oui
[[ "$RESTE_D" == "$AVANT10" ]] && ED=non || ED=oui
CU="$(classer10 "$RU" "$EU")"
CD="$(classer10 "$RD" "$ED")"
detail "10. update -> $CU ($EFFET_U reecrite(s)) ; delete -> $CD ($AVANT10 -> $RESTE_D)"

if [[ "$CU" == "REECRIT" || "$CD" == "REECRIT" ]]; then
  rouge "10. l'historique d'autorite n'est pas immuable pour le role"
  detail "applicatif (update=$CU, delete=$CD)."
elif [[ "$CU" == "SANS_EFFET" || "$CD" == "SANS_EFFET" ]]; then
  # SANS ERREUR ET SANS EFFET: signature d'une RLS qui filtre a zero ligne.
  # L'ordre a ete ACCEPTE; seule l'absence de ligne visible l'a rendu
  # inoffensif. Le lire comme un refus serait le faux vert que ce harnais
  # existe pour eviter.
  non_parcouru "10. ordre ACCEPTE sans erreur et sans effet visible"
  detail "(update=$CU, delete=$CD): probable filtrage RLS a zero ligne, et"
  detail "non un refus. La garde d'immuabilite n'a pas ete atteinte."
else
  sur "10. UPDATE et DELETE refuses au role applicatif, SANS clause WHERE"
  detail "— donc sur le seul privilege d'ecriture, et non sur un SELECT"
  detail "implicite. Non-vacuite: la matrice mesuree en 0 affiche les"
  detail "privileges reels de « normative_backend » sur cette table."
  detail "update: $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$RU")"
  detail "delete: $(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,80}' <<<"$RD")"
fi

# ==========================================================================
# 11. REJEU D'UNE DECISION
# ==========================================================================
echo "      -- 11. rejeu d'un octroi identique"
SQL11="set eurostruct.actor_id = '$ADMIN_ID';
       insert into normative_authorisation_grants
         (grantee_id, grantee_name, permission, country_code, standard_family,
          part, edition, reason, parent_grant_id)
       values ('$TIERS', 'FICTIF rejeu', 'can_validate_normative_reference',
               'BE', 'EN 1997', '1-1', '2004', 'FICTIF rejeu',
               '$GRANT_RACINE')"
P11="$(sql_svc "$SQL11")"
R11="$(sql_svc "$SQL11")"
N11="$(admb -tAc "select count(*) from normative_authorisation_grants
                   where standard_family = 'EN 1997' and reason = 'FICTIF rejeu'" \
       2>&1 | tr -d ' ')"
detail "11. octrois identiques presents apres deux envois: $N11"
if [[ "$N11" == "0" ]] || erreur_sql "$P11"; then
  non_parcouru "11. le PREMIER envoi n'a rien cree — le rejeu n'est pas exerce:"
  detail "$(head -c 180 <<<"$P11")"
elif [[ "$N11" -ge 2 ]]; then
  rouge "11. le meme octroi existe $N11 fois: aucune cle d'idempotence ne"
  detail "protege la table des octrois, et rien ne distingue un rejeu"
  detail "accidentel d'une seconde decision deliberee."
elif erreur_sql "$R11"; then
  sur "11. le rejeu d'un octroi identique est refuse"
  detail "non-vacuite: le premier envoi, lui, a bien cree une ligne."
else
  sur "11. le rejeu n'a pas duplique l'octroi ($N11 ligne(s))"
fi

# ==========================================================================
# 12. DOUBLE APPROBATION CONCURRENTE — barriere deterministe
# ==========================================================================
echo "      -- 12. deux approbations concurrentes (barriere par verrou partage)"
BAR2=77000000002
A1="$(mktemp -p "$CANAUX_RACINE")"; A2="$(mktemp -p "$CANAUX_RACINE")"
if barriere_prendre "$BAR2"; then
  for cible in "$COMPLICE:$A1:y1" "$TIERS:$A2:y2"; do
    u="${cible%%:*}"; reste="${cible#*:}"; f="${reste%%:*}"; tag="${reste##*:}"
    ( exec {BAR_FD}>&-
      PGAPPNAME="FICTIF-c12-${tag}-${JETON}" \
      ord -tAc "select pg_advisory_lock_shared($BAR2);
                set role normative_backend;
                set eurostruct.actor_id = '$ADMIN_ID';
                insert into normative_authorisation_grants
                  (grantee_id, grantee_name, permission, country_code,
                   standard_family, part, edition, reason, parent_grant_id)
                values ('$u', 'FICTIF concurrent',
                        'can_validate_normative_reference',
                        'BE', 'EN 1993', '1-1', '2005',
                        'FICTIF approbation concurrente', '$GRANT_RACINE');" >"$f" 2>&1 ) &
    CONCURRENTS+=("$!")
  done
  if barriere_attendre_concurrents 2 "FICTIF-c12-%-${JETON}"; then
    barriere_lever
    attendre_concurrents_termines
    N12="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where standard_family = 'EN 1993'" 2>&1 | tr -d ' ')"
    detail "12. octrois concurrents aboutis: $N12 (barriere $BAR2, aucun sleep)"
    if [[ "$N12" == "2" ]]; then
      rouge "12. deux approbations concurrentes ont abouti sous UNE SEULE"
      detail "identite declaree: la concurrence ne cree pas deux regards"
      detail "independants, elle en DUPLIQUE un."
    elif [[ "$N12" == "0" ]]; then
      sur "12. deux sessions ORDINAIRES concurrentes, relachees ensemble,"
      detail "n'ont produit aucune approbation: la concurrence ne contourne"
      detail "pas la frontiere. Non-vacuite: les deux ont ete OBSERVEES"
      detail "bloquees sur la barriere, donc elles ont bien atteint la base."
    else
      sur "12. la concurrence n'a produit qu'une approbation ($N12)"
    fi
  else
    barriere_lever; attendre_concurrents_termines
    non_parcouru "12. la barriere n'a jamais ete franchie: aucune course."
  fi
else
  barriere_lever
  non_parcouru "12. la barriere n'a pas pu etre prise: aucune course."
fi

# ==========================================================================
# 13. CONFUSION DE PORTEE — meme personne, autre edition
# ==========================================================================
echo "      -- 13. confusion de portee (meme personne, autre edition)"
#
# POURQUOI CETTE ATTAQUE A ETE REECRITE. La premiere version appelait
# `resolve_normative_authorisation()` directement et lisait le refus comme une
# protection de portee. Or la migration ne l'accorde qu'a
# `eurostruct_normative_writer` (0010, « grant execute on function
# resolve_normative_authorisation ... to eurostruct_normative_writer »), un
# role NOLOGIN dont personne n'est membre. Le role applicatif recevait donc
# « permission denied for function », et le verdict « deja sur » ne parlait pas
# de portee du tout. Troisieme faux vert du meme genre: mesurer une ACL en
# croyant mesurer un invariant.
#
# LE CHEMIN ATTEIGNABLE est l'insertion d'octroi: `check_normative_grant()`
# resout la portee de l'ACTEUR contre celle de l'octroi demande. Pour eprouver
# l'axe « edition », il faut donc un acteur dont la portee FIXE une edition —
# sans quoi son NULL vaudrait « toutes » et l'axe ne serait jamais compare.
PORTEUR13="$TIERS"
sql_svc "         set eurostruct.actor_id = '$ADMIN_ID';
         insert into normative_authorisation_grants
           (grantee_id, grantee_name, permission, country_code,
            standard_family, part, edition, reason, parent_grant_id)
         values ('$PORTEUR13', 'FICTIF admin edition 2004',
                 'can_manage_normative_authorisations',
                 'BE', 'EN 1998', '1-1', '2004',
                 'FICTIF administration bornee a une edition', '$GRANT_RACINE')" >/dev/null 2>&1
ADM13="$(admb -tAc "select count(*) from normative_authorisation_grants
                     where reason = 'FICTIF administration bornee a une edition'" \
         2>&1 | tr -d ' ')"
GRANT_ED13="$(admb -tAc "select id from normative_authorisation_grants
                          where reason = 'FICTIF administration bornee a une edition'" \
              2>&1 | tr -d ' ')"
if [[ "$ADM13" != "1" ]]; then
  non_parcouru "13. l'administration bornee a une edition n'a pas ete creee:"
  detail "l'axe « edition » ne peut pas etre eprouve. Chemin non parcouru."
else
  # CONTROLE POSITIF: dans l'edition detenue, la delegation doit passer.
  sql_svc "           set eurostruct.actor_id = '$PORTEUR13';
           insert into normative_authorisation_grants
             (grantee_id, grantee_name, permission, country_code,
              standard_family, part, edition, reason, parent_grant_id)
           values ('$COMPLICE', 'FICTIF temoin edition',
                   'can_validate_normative_reference',
                   'BE', 'EN 1998', '1-1', '2004',
                   'FICTIF temoin edition detenue', '$GRANT_ED13')" >/dev/null 2>&1
  TEM13="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where reason = 'FICTIF temoin edition detenue'" \
           2>&1 | tr -d ' ')"
  detail "13. controle positif — delegation dans l'edition 2004: $TEM13 octroi"
  if [[ "$TEM13" != "1" ]]; then
    non_parcouru "13. l'acteur ne delegue meme pas dans SON edition: un refus sur"
    detail "une autre edition ne prouverait rien. Chemin non parcouru."
  else
    R13="$(sql_svc "                    set eurostruct.actor_id = '$PORTEUR13';
                    insert into normative_authorisation_grants
                      (grantee_id, grantee_name, permission, country_code,
                       standard_family, part, edition, reason, parent_grant_id)
                    values ('$COMPLICE', 'FICTIF autre edition',
                            'can_validate_normative_reference',
                            'BE', 'EN 1998', '1-1', '2099',
                            'FICTIF edition non detenue', '$GRANT_ED13')")"
    N13="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where reason = 'FICTIF edition non detenue'" \
           2>&1 | tr -d ' ')"
    if [[ "$N13" != "0" ]]; then
      rouge "13. un acteur habilite sur l'edition 2004 SEULEMENT a delegue sur"
      detail "l'edition 2099: l'axe « edition » n'entre pas dans la comparaison"
      detail "de portee. INVARIANT ATTENDU (I-6): la portee se compare sur les"
      detail "QUATRE axes, pays / famille / partie / edition."
    elif erreur_sql "$R13"; then
      sur "13. la delegation sur une edition non detenue est refusee, alors"
      detail "que la meme delegation dans l'edition detenue vient d'aboutir."
      detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,110}' <<<"$R13")"
    else
      non_parcouru "13. ni ecriture ni erreur: resultat non interpretable."
    fi
  fi
fi

# ==========================================================================
# 14. CONSOMMATION PENDANT LA REVOCATION — TOCTOU
# ==========================================================================
echo "      -- 14. consommation d'une autorite pendant sa revocation"
#
# POURQUOI CETTE ATTAQUE A ETE ENTIEREMENT REECRITE. La premiere version
# appelait `consume_normative_authorisation()` directement et concluait
# « deja sur » sur:
#
#     ERROR: permission denied for function consume_normative_authorisation
#
# La matrice mesuree en 0 le disait pourtant: svc=f, backend=f. Le role
# applicatif n'a PAS ce droit — le refus mesurait donc une ACL, pas une
# serialisation, et le verdict affirmait une propriete que rien n'avait
# exercee. Faux vert.
#
# LA CONSOMMATION SE FAIT PAR LE CHEMIN REELLEMENT ATTEIGNABLE: une insertion
# d'octroi, dont le declencheur `check_normative_grant()` appelle
# `consume_normative_authorisation()` pour le compte de l'appelant.
#
# ET LA COURSE EST CONSTRUITE, PAS ESPEREE. Deux barrieres, aucun `sleep`:
#
#   1. A revoque l'habilitation de TIERS puis se PARQUE, transaction ouverte,
#      sur une barriere du harnais. Elle detient donc le verrou consultatif
#      EXCLUSIF de la ligne d'octroi, et elle ne le lachera pas avant qu'on le
#      decide.
#   2. On ATTEND de voir A parquee. Ce n'est pas une esperance: c'est une
#      condition lue dans `pg_stat_activity`.
#   3. B tente alors de consommer la MEME habilitation. Le verrou PARTAGE que
#      prend `consume_normative_authorisation()` doit la faire attendre.
#   4. On ATTEND de voir B bloquee. SI B NE BLOQUE JAMAIS, l'exclusion mutuelle
#      n'existe pas et la fenetre TOCTOU est ouverte: c'est le rouge.
#   5. On leve la barriere. A valide. B repart, RELIT sous verrou, et doit
#      trouver l'habilitation revoquee. Si B aboutit malgre tout, elle s'est
#      servie d'un pouvoir retire: c'est l'autre rouge.
#
# Aucun horodatage n'est compare: `now()` vaut l'heure de DEBUT de transaction
# en PostgreSQL, si bien que deux transactions concurrentes peuvent porter des
# estampilles qui contredisent leur ordre de validation. Un oracle fonde sur
# elles aurait eu l'air rigoureux et n'aurait rien prouve.
#
# PRECONDITION: une habilitation d'administration FRAICHE pour TIERS. Celle de
# COMPLICE a deja ete revoquee en 8, et `unique (grant_id)` interdit de la
# revoquer deux fois.
GID14=""
sql_svc "         set eurostruct.actor_id = '$ADMIN_ID';
         insert into normative_authorisation_grants
           (grantee_id, grantee_name, permission, country_code,
            standard_family, part, edition, reason, parent_grant_id)
         values ('$TIERS', 'FICTIF tiers admin',
                 'can_manage_normative_authorisations',
                 'BE', 'EN 1999', null, null,
                 'FICTIF habilitation pour la course 14', '$GRANT_RACINE')" >/dev/null 2>&1
GID14="$(admb -tAc "select id from normative_authorisation_grants
                     where reason = 'FICTIF habilitation pour la course 14'" \
         2>&1 | tr -d ' ')"
GRANT_C14="$GID14"
if ! est_uuid "$GID14"; then
  non_parcouru "14. l'habilitation de course n'a pas ete creee: chemin non parcouru."
else
  BAR4=77000000004
  C1="$(mktemp -p "$CANAUX_RACINE")"; C2="$(mktemp -p "$CANAUX_RACINE")"
  APP_A="FICTIF-c14a-${JETON}"; APP_B="FICTIF-c14b-${JETON}"
  BLOQUEE=-1
  if barriere_prendre "$BAR4"; then
    # A — revoque, puis se parque SANS avoir valide, verrou de ligne en main.
    ( exec {BAR_FD}>&-
      PGAPPNAME="$APP_A" \
      svc -tAc "set eurostruct.actor_id = '$ADMIN_ID';
                begin;
                insert into normative_authorisation_revocations
                  (grant_id, reason)
                values ('$GID14', 'FICTIF revocation en vol');
                select pg_advisory_lock_shared($BAR4);
                commit;" >"$C1" 2>&1 ) &
    CONCURRENTS+=("$!")
    if attendre "la revocation est EN VOL, parquee sur la barriere $BAR4" \
         "exists(select 1 from pg_stat_activity
                  where application_name = '$APP_A'
                    and wait_event_type = 'Lock')"; then
      # B — consomme la MEME habilitation par le chemin atteignable.
      ( exec {BAR_FD}>&-
        PGAPPNAME="$APP_B" \
        svc -tAc "set eurostruct.actor_id = '$TIERS';
                  insert into normative_authorisation_grants
                    (grantee_id, grantee_name, permission, country_code,
                     standard_family, part, edition, reason, parent_grant_id)
                  values ('$COMPLICE', 'FICTIF cible 14',
                          'can_validate_normative_reference',
                          'BE', 'EN 1999', '1-1', '2007',
                          'FICTIF usage pendant revocation', '$GRANT_C14');" >"$C2" 2>&1 ) &
      CONCURRENTS+=("$!")
      if attendre "la consommation est BLOQUEE par la revocation en vol" \
           "exists(select 1 from pg_stat_activity
                    where application_name = '$APP_B'
                      and wait_event_type = 'Lock')"; then
        BLOQUEE=1
      else
        BLOQUEE=0
      fi
    fi
    barriere_lever                 # A valide, B repart
    attendre_concurrents_termines
  else
    barriere_lever
  fi

  REV14="$(admb -tAc "select count(*) from normative_authorisation_revocations
                       where grant_id = '$GID14'" 2>&1 | tr -d ' ')"
  USG14="$(admb -tAc "select count(*) from normative_authorisation_grants
                       where reason = 'FICTIF usage pendant revocation'" \
           2>&1 | tr -d ' ')"
  detail "14. revocation validee: $REV14 ; consommation aboutie: $USG14 ; B bloquee: $BLOQUEE"
  if [[ "$BLOQUEE" == "-1" ]]; then
    non_parcouru "14. la course n'a pas pu etre montee: chemin non parcouru."
  elif [[ "$REV14" != "1" ]]; then
    non_parcouru "14. la revocation n'a pas abouti — rien ne s'opposait a la"
    detail "consommation: $(head -c 140 "$C1")"
  elif [[ "$BLOQUEE" == "0" ]]; then
    rouge "14. la consommation n'a JAMAIS attendu la revocation en vol:"
    detail "aucune exclusion mutuelle entre les deux chemins, donc une"
    detail "habilitation peut etre lue active alors qu'elle est en train"
    detail "d'etre retiree. INVARIANT ATTENDU (I-8)."
  elif [[ "$USG14" != "0" ]]; then
    rouge "14. la consommation a ABOUTI apres une revocation validee: la"
    detail "relecture sous verrou n'a pas vu le retrait. Un pouvoir retire"
    detail "a produit un octroi."
  else
    sur "14. B a ete OBSERVEE bloquee par la revocation en vol, puis refusee"
    detail "apres relecture sous verrou. Les deux chemins s'excluent, et"
    detail "l'issue correspond a l'ordre seriel « revoquer puis refuser »."
    detail "$(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,110}' "$C2")"
  fi
fi

# ==========================================================================
# LE COMPTE RENDU — et la verification de sa propre arithmetique
# ==========================================================================
verdicts_verifier || true

echo ""
echo "      barrieres (mecanisme deterministe, aucun sleep d'ordonnancement):"
if ((${#BARRIERES[@]} == 0)); then
  echo "                (aucune)"
else
  printf '                %s\n' "${BARRIERES[@]}"
fi

verdicts_resume "6.3c — racine de confiance des autorites"

# LE CANAL EST CONCLU AVANT LES DEUX SORTIES, ET NON DANS L'UNE D'ELLES.
# Un point qui PASSE doit produire un SUR, et un point seulement troue son
# NON_PARCOURU: sans cela le lanceur lirait NOT_RUN — « pas mesure » — la ou
# il faut lire SURVIVED — « la garantie a ete retiree et rien n'a rougi ».
esc_conclure

if [[ $KO -eq 0 && $VERDICTS_KO -eq 0 && $VERDICTS_ROUGES -eq 0 \
      && $VERDICTS_NON_PARCOURUS -eq 0 ]]; then
  echo " Aucune ouverture: la racine de confiance tient."
  exit 0
fi
exit 1
