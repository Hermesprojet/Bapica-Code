#!/usr/bin/env bash
#
# LES CINQ COUCHES QUI SEPARENT LE MIGRATEUR DU PLAN DE CONTROLE
#
# CE QUE CE HARNAIS CORRIGE
# --------------------------
# La matrice du lot L4 exercait SEPT combinaisons de TROIS couches et
# concluait « l'etat n'atteint jamais ACTIVE ». Elle etait complete pour trois
# couches — et elle en a decouvert deux autres en chemin. Sept combinaisons de
# trois ne disent rien d'un systeme qui en a cinq: les deux couches ignorees
# encadraient les trois etudiees, si bien que chaque refus pouvait venir
# d'ailleurs que de la ou on le lisait.
#
# LES CINQ COUCHES, DANS L'ORDRE OU ELLES S'EXECUTENT
# ----------------------------------------------------
#   1. `assert_authority_backend_membership()`   0013, PHASE 1
#      « le login declare detient l'ADMIN OPTION sur le backend d'autorite »
#   2. exception procedurale de `normative_finalize_deployment`   sceau
#      « le plan de controle derive est le migrateur lui-meme »
#   3. contrainte `finalization_intent_separates_roles`           sceau
#   4. assertion de capacite residuelle                           sceau
#      « apres revocation, « % » conserve % capacite(s) »
#   5. `normative_record_activation()`, JUSTE AVANT D'ECRIRE      sceau
#      « le migrateur « % » detient encore % capacite(s) »
#
# L'ORDRE EST LE SUJET. Une couche anterieure NON neutralisee MASQUE toutes
# les suivantes: le refus vient d'elle, et l'attribuer a la couche etudiee
# serait une erreur de lecture — exactement le genre d'erreur qui a produit
# les onze survivants de `3d0acc2`. Ce harnais NOMME le masquage au lieu de
# le subir.
#
# CE QU'IL PROUVE POUR CHAQUE CAS
# --------------------------------
#   * la mutation demandee est REELLEMENT active (ancre trouvee, texte change);
#   * le decor atteint l'etape annoncee (phase 0, puis phase 1, puis
#     finalisation) — un refus precoce n'est jamais lu comme un refus tardif;
#   * l'etat final est MESURE, pas suppose;
#   * le refus est attribue a la couche EXACTE, par sa signature;
#   * si une couche anterieure non neutralisee a parle, le cas est marque
#     MASQUE et ne conclut rien sur la couche etudiee.
#
# LE CAS DECISIF est « 1+2+3+4+5 ». Si l'etat atteint ACTIVE, le
# contre-exemple complet est obtenu et la separation ne tient plus que par ces
# cinq couches. S'il refuse encore, une SIXIEME defense existe: ce harnais
# exige alors son chemin causal, et « encore refuse » ne vaut pas preuve.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$(dirname "$HERE")")"     # .../eurostruct
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

harnais_connexion || exit 2
exiger_precontrole_local "db/test/separation_layers.sh" || exit 2
exiger_cluster_jetable "db/test/separation_layers.sh" || exit 2

SCEAU_REL="db/control_plane/0001_normative_seal.sql"
M0013_REL="db/migrations/0013_authenticated_actor.sql"
TRAVAIL="${TMPDIR:-/tmp}/sep5_$$"
JETON="$(harnais_jeton)"
U="escsep_$JETON"        # le role CONFONDU: migrateur ET plan de controle
B="escsepb_$JETON"
MDP="FICTIF-sep5-$JETON"
CANON=(eurostruct_normative_writer eurostruct_normative_bootstrap
       eurostruct_normative_activator normative_backend normative_governance
       eurostruct_deployment eurostruct_authority_backend
       eurostruct_reconciliation
       anon authenticated service_role)
# UN CLUSTER SALE PRODUIT UN DIAGNOSTIC SANS RAPPORT, ET C'EST MESURE.
# Une base de diagnostic laissee derriere empeche `drop owned by` d'atteindre
# les objets qu'elle contient — cette commande ne porte que sur la base
# COURANTE. Les roles canoniques survivent alors, et la phase 0 refuse sur
# « permission denied to grant role eurostruct_normative_activator »: seize
# cas rougissent pour une cause etrangere a ce qu'ils mesurent.
#
# On REFUSE au lieu de nettoyer largement: ce harnais ne detruit que ce qu'il
# a cree.
exiger_roles_absents "db/test/separation_layers.sh" \
  eurostruct_normative_writer eurostruct_normative_bootstrap \
  eurostruct_normative_activator normative_backend normative_governance \
  eurostruct_deployment eurostruct_authority_backend \
  eurostruct_reconciliation || exit 2

KO=0
declare -A RESULTAT

echoue() { echo "ECHEC: $*" >&2; KO=1; }

# --------------------------------------------------------------------------
# LES CINQ PATCHS — ancres EXACTES, verifiees a l'application
# --------------------------------------------------------------------------
# LA COUCHE 1 N'EST PAS UNE GARDE, C'EST UNE FONCTION A PLUSIEURS BRANCHES.
# Premiere version de ce harnais: on neutralisait la branche H1 (ADMIN OPTION
# en ligne directe). La phase 1 refusait encore, avec une signature INCONNUE —
# H2, la fermeture TRANSITIVE, qui voit « peut ENROLER par une chaine
# d'appartenances, sans y figurer en ligne directe ». H3 en ajoute une
# troisieme. Neutraliser une branche ne neutralise pas la couche, et l'aurait
# fait passer pour une sixieme defense qui n'existe pas.
#
# On vise donc le POINT DE DECISION de la fonction, la ou les ecarts
# deviennent un refus. C'est cela, « neutraliser la couche 1 ».
patch_1() {  # appartenance backend, phase 1 — TOUTES branches
  _patch "$1/$M0013_REL" \
"  if array_length(ecarts, 1) > 0 then
    raise exception
      'frontiere d''autorite: appartenance non declaree — %'," \
"  if false then
    raise exception
      'frontiere d''autorite: appartenance non declaree — %',"
}
patch_2() {  # exception procedurale de la finalisation
  _patch "$1/$SCEAU_REL" \
"  if d_oid = m_oid or d_nom = m_nom then
    raise exception
      'le plan de controle derive est le migrateur lui-meme (« % »). '" \
"  if false then
    raise exception
      'le plan de controle derive est le migrateur lui-meme (« % »). '"
}
patch_3() {  # CHECK finalization_intent_separates_roles
  _patch "$1/$SCEAU_REL" \
"  constraint finalization_intent_separates_roles
    check (migrateur_oid <> donneur_oid and migrateur_nom <> donneur_nom)" \
"  constraint finalization_intent_separates_roles
    check (true)"
}
patch_4() {  # assertion de capacite residuelle
  _patch "$1/$SCEAU_REL" \
"  if n <> 0 then
    raise exception
      'apres revocation, « % » conserve % capacite(s) sur les roles '" \
"  if false then
    raise exception
      'apres revocation, « % » conserve % capacite(s) sur les roles '"
}
patch_5() {  # normative_record_activation, juste avant d'ecrire
  _patch "$1/$SCEAU_REL" \
"  if n <> 0 then
    raise exception
      'le migrateur « % » detient encore % capacite(s) sur les roles '" \
"  if false then
    raise exception
      'le migrateur « % » detient encore % capacite(s) sur les roles '"
}

# UNE MUTATION NON APPLIQUEE EST UNE MUTATION QUI MENT. Le patch verifie que
# l'ancre existe EXACTEMENT une fois et que le texte a change; sans quoi le
# cas mesurerait le systeme intact en croyant l'avoir affaibli.
_patch() {
  ESC_P_F="$1" ESC_P_A="$2" ESC_P_B="$3" python3 - <<'FINPY'
import os, pathlib, sys
p = pathlib.Path(os.environ["ESC_P_F"])
a, b = os.environ["ESC_P_A"], os.environ["ESC_P_B"]
t = p.read_text(encoding="utf-8")
if t.count(a) != 1:
    print(f"ancre absente ou ambigue ({t.count(a)}) dans {p.name}", file=sys.stderr)
    sys.exit(1)
n = t.replace(a, b)
if n == t:
    print("le texte n'a pas change", file=sys.stderr); sys.exit(1)
p.write_text(n, encoding="utf-8")
FINPY
}

# --------------------------------------------------------------------------
# SIGNATURES — a quelle couche appartient un refus
# --------------------------------------------------------------------------
# On lit la SIGNATURE du message, pas son rang: deux couches voisines rendent
# des messages differents, et c'est cela qui les distingue.
couche_du_refus() {   # couche_du_refus <texte>
  local t="$1"
  if   grep -qF "ADMIN OPTION sur le backend" <<<"$t"; then echo 1
  elif grep -qF "le plan de controle derive est le migrateur lui-meme" <<<"$t"; then echo 2
  elif grep -qF "finalization_intent_separates_roles" <<<"$t"; then echo 3
  elif grep -qF "conserve" <<<"$t" && grep -qF "capacite(s)" <<<"$t"; then echo 4
  elif grep -qF "detient encore" <<<"$t"; then echo 5
  elif [[ -z "$t" ]]; then echo 0
  else echo 9; fi
}

nettoyer_cluster() {
  # L'ORDRE COMPTE, ET IL EST MESURE: un role qui possede des objets dans une
  # base encore presente ne se supprime PAS, et l'echec est silencieux. La
  # base d'abord, les roles ensuite — sinon les roles canoniques survivent et
  # la phase 0 suivante refuse sur « permission denied to grant role
  # eurostruct_normative_activator », un diagnostic sans rapport avec la cause.
  psql -X -q -c "drop database if exists \"$B\"" >/dev/null 2>&1
  local r
  for r in "${CANON[@]}" "$U" "escsvc_$JETON"; do
    psql -X -q -c "drop owned by \"$r\"" >/dev/null 2>&1
    psql -X -q -c "drop role if exists \"$r\"" >/dev/null 2>&1
  done
}

# --------------------------------------------------------------------------
# UN CAS
# --------------------------------------------------------------------------
# Rend, dans RESULTAT[<libelle>], une ligne « <etat>|<couche>|<etape> ».
cas() {   # cas <libelle> <couches a neutraliser...>
  local libelle="$1"; shift
  local -a couches=("$@")
  local SVC="escsvc_$JETON"

  rm -rf "$TRAVAIL"; cp -r "$SRC" "$TRAVAIL" 2>/dev/null
  local c
  for c in "${couches[@]}"; do
    if ! "patch_$c" "$TRAVAIL" 2>/dev/null; then
      echoue "$libelle: la mutation de la couche $c n'a PAS ete appliquee"
      RESULTAT[$libelle]="MUTATION_INACTIVE|-|-"
      return 1
    fi
  done

  nettoyer_cluster
  if ! psql -X -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role "$U" login password '$MDP' createrole createdb;
create role "$SVC" login password '$MDP';
grant "$U" to current_user;
create database "$B" owner "$U";
SQL
  then
    echoue "$libelle: le decor n'a pas pu etre pose"
    RESULTAT[$libelle]="DECOR_REFUSE|-|creation"
    return 1
  fi

  u()  { PGUSER="$U" PGPASSWORD="$MDP" psql -X -q -d "$B" "$@"; }
  up() { PGUSER="$U" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }

  psql -X -q -d "$B" -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  psql -X -q -d "$B" >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$U" with grant option;
grant select, insert, references on auth.users to "$U" with grant option;
grant execute on function auth.uid() to "$U" with grant option;
grant create on database "$B" to "$U";
grant create on schema public to "$U" with grant option;
SQL

  # ETAPE « phase 0 »: le sceau, pose PAR LE MEME ROLE. C'est la confusion
  # recherchee: le migrateur est son propre plan de controle.
  local sortie
  if ! sortie=$(u -v ON_ERROR_STOP=1 -f "$TRAVAIL/$SCEAU_REL" 2>&1); then
    RESULTAT[$libelle]="REFUS|$(couche_du_refus "$sortie")|phase0"
    return 0
  fi

  psql -X -q -c "grant eurostruct_deployment to \"$U\" with inherit true" \
       -d postgres >/dev/null 2>&1
  up -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$U" with admin option;
grant eurostruct_normative_bootstrap to "$U" with admin option;
SQL
  # LE ROLE CONFONDU EST DECLARE BACKEND D'AUTORITE: c'est ce qui met la
  # couche 1 sur le chemin. Sans cela elle ne s'exprimerait jamais et l'on
  # croirait le systeme defendu par quatre couches.
  local g
  for g in "approved_deployment_roles = '$U'" "token_roles = 'authenticated'" \
           "approved_service_logins = '$SVC'" "authority_backend_logins = '$U'" \
           "bootstrap_mandate = 'b0000000-0000-0000-0000-0000000000b1:FICTIF'"; do
    psql -X -q -c "alter database \"$B\" set eurostruct.$g" -d postgres >/dev/null 2>&1
  done

  # ETAPE « phase 1 »: les migrations. La couche 1 s'exprime ICI.
  source "$TRAVAIL/db/apply_migration.sh"
  local f
  for f in "$TRAVAIL"/db/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" u; then
      RESULTAT[$libelle]="REFUS|$(couche_du_refus "$ESC_MIGRATION_SORTIE")|phase1"
      return 0
    fi
  done

  # ETAPE « finalisation »: les couches 2, 3, 4 puis 5.
  local M FIN ETAT
  M=$(PGUSER=$U PGPASSWORD=$MDP psql -X -tA -d "$B" \
        -c "select normative_settings_manifest()" 2>&1)
  FIN=$(PGUSER=$U PGPASSWORD=$MDP psql -X -tA -d "$B" \
        -c "select normative_finalize_deployment($(esc_litteral "$M"))" 2>&1)
  ETAT=$(PGUSER=$U PGPASSWORD=$MDP psql -X -tA -d "$B" \
        -c "select normative_activation_state()" 2>&1)
  if [[ "$ETAT" == "ACTIVE" ]]; then
    RESULTAT[$libelle]="ACTIVE|-|finalisation"
  else
    RESULTAT[$libelle]="$ETAT|$(couche_du_refus "$FIN")|finalisation"
  fi
  return 0
}

# --------------------------------------------------------------------------
# LES CAS
# --------------------------------------------------------------------------
echo "==> les cinq couches de separation migrateur / plan de controle"
echo "    decor CONFONDU: un seul role migre ET approuve; il est aussi"
echo "    declare backend d'autorite, ce qui met la couche 1 sur le chemin."
echo ""

cas "baseline"
for n in 1 2 3 4 5; do cas "seule-$n" "$n"; done
# CHAQUE COUCHE LAISSEE SEULE: on neutralise les QUATRE autres. C'est le seul
# montage ou le refus ne peut venir que de la couche etudiee.
cas "laissee-1" 2 3 4 5
cas "laissee-2" 1 3 4 5
cas "laissee-3" 1 2 4 5
cas "laissee-4" 1 2 3 5
cas "laissee-5" 1 2 3 4
# CUMUL DANS L'ORDRE D'EXECUTION.
cas "cumul-1"       1
cas "cumul-12"      1 2
cas "cumul-123"     1 2 3
cas "cumul-1234"    1 2 3 4
cas "cumul-12345"   1 2 3 4 5

nettoyer_cluster
rm -rf "$TRAVAIL"

# --------------------------------------------------------------------------
# LECTURE
# --------------------------------------------------------------------------
echo ""
printf '    %-14s %-10s %-14s %s\n' cas etat etape "refus attribue a"
printf '    %-14s %-10s %-14s %s\n' -------------- ---------- -------------- ----------------
for k in baseline seule-1 seule-2 seule-3 seule-4 seule-5 \
         laissee-1 laissee-2 laissee-3 laissee-4 laissee-5 \
         cumul-1 cumul-12 cumul-123 cumul-1234 cumul-12345; do
  IFS='|' read -r etat couche etape <<<"${RESULTAT[$k]:-ABSENT|-|-}"
  case "$couche" in
    0) motif="(aucun message)" ;;
    9) motif="INCONNU — a nommer" ;;
    -) motif="-" ;;
    *) motif="couche $couche" ;;
  esac
  printf '    %-14s %-10s %-14s %s\n' "$k" "$etat" "$etape" "$motif"
done

# --- ce que chaque cas devait etablir -------------------------------------
echo ""
attendu() {  # attendu <cas> <couche attendue> <commentaire>
  IFS='|' read -r _e c _s <<<"${RESULTAT[$1]:-|-|}"
  if [[ "$c" == "$2" ]]; then
    echo "      ok: $1 -> couche $2 (${3-})"
  else
    echoue "$1: refus attribue a la couche « $c », attendu « $2 » (${3-})"
  fi
}
attendu baseline    1 "intact: la premiere couche parle"
attendu laissee-1   1 "les quatre autres neutralisees"
attendu laissee-2   2 "seule la 2 subsiste"
attendu laissee-3   3 "seule la 3 subsiste"
attendu laissee-4   4 "seule la 4 subsiste"
attendu laissee-5   5 "seule la 5 subsiste"
attendu cumul-1     2 "la 1 retiree, la 2 prend le relais"
attendu cumul-12    3
attendu cumul-123   4
attendu cumul-1234  5

# LE MASQUAGE EST NOMME, PAS SUBI. Neutraliser la seule couche 3 ne dit RIEN
# sur la couche 3: la couche 1 refuse avant elle. Un harnais qui lirait ce
# refus comme « la 3 tient » se tromperait de garantie.
echo ""
for n in 2 3 4 5; do
  IFS='|' read -r _e c _s <<<"${RESULTAT[seule-$n]:-|-|}"
  if [[ "$c" == "1" ]]; then
    echo "      ok: seule-$n est MASQUE par la couche 1 — ne conclut rien sur $n"
  else
    echoue "seule-$n: attendu un masquage par la couche 1, obtenu « $c »"
  fi
done

# --- LE CAS DECISIF --------------------------------------------------------
echo ""
IFS='|' read -r ETAT_D COUCHE_D ETAPE_D <<<"${RESULTAT[cumul-12345]:-ABSENT|-|-}"
echo "    ================= CAS DECISIF: les cinq neutralisees ================="
if [[ "$ETAT_D" == "ACTIVE" ]]; then
  echo "    ACTIVE atteint: le CONTRE-EXEMPLE COMPLET est obtenu."
  echo "    La separation ne tient que par ces cinq couches, et elles sont"
  echo "    maintenant toutes nommees et falsifiables."
else
  echo "    etat « $ETAT_D » a l'etape « $ETAPE_D » — une SIXIEME defense existe."
  echo "    Elle est attribuee a: ${COUCHE_D}"
  echo "    « encore refuse » ne vaut pas preuve: le chemin causal est exige."
  if [[ "$COUCHE_D" == "9" || "$COUCHE_D" == "0" ]]; then
    echo "    SIGNATURE NON RECONNUE — c'est precisement la sixieme couche."
  fi
fi
echo "    ======================================================================"

echo ""
if (( KO )); then
  echo "================================================="
  echo " Couches de separation: AU MOINS UN CAS DEMENT"
  echo " la cartographie."
  echo "================================================="
  exit 1
fi
echo "================================================="
echo " Couches de separation: la cartographie a cinq"
echo " couches est verifiee, masquage compris."
echo "================================================="
exit 0
