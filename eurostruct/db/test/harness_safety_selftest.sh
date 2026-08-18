#!/usr/bin/env bash
#
# EUROSTRUCT — PREUVE QUE LES HARNAIS NE PEUVENT PAS DETRUIRE UN CLUSTER TIERS
#
#   harness_safety_selftest.sh
#
# CE QUE CE FICHIER EXISTE POUR PROUVER
# --------------------------------------
# Les harnais de `db/test/` creent et detruisent des ROLES GLOBAUX
# (`eurostruct_normative_writer`, `normative_backend`, ...). Les roles
# appartiennent au CLUSTER, pas a une base: lances sur le mauvais cluster, ils
# detruiraient les vrais roles normatifs — et, avec le `CASCADE` qui figurait
# dans `two_phase_deployment.sh`, les objets qui en dependent.
#
# Une barriere qu'on n'a jamais vue refuser n'est pas une barriere. Ce fichier
# la met donc en echec DELIBEREMENT, avec un TEMOIN a chaque coup: un role
# portant exactement le nom canonique, cree avant, verifie apres.
#
# CE FICHIER EST SOUMIS AUX MEMES GARDES QUE CEUX QU'IL TESTE: il appelle
# `exiger_cluster_jetable` et prend le verrou avant toute lecture destructive.
# Il ne detruit que les objets dont il a CONSTATE la creation — un nom fixe
# supprime « au cas ou » detruirait precisement ce que ce fichier protege.
#
# CE QUI EST EXERCE
# ------------------
#   1. la commande canonique SANS consentement -> refus, temoins intacts
#   2. avec consentement mais hote NON local    -> refus, temoins intacts
#   3. avec consentement mais cluster GERE      -> refus, temoins intacts
#   4. avec consentement mais base ETRANGERE    -> refus, temoins intacts
#   5. roles canoniques PREEXISTANTS            -> refus, temoins intacts
#   6. aucun secret dans argv                   -> controle statique
#   7. DEUX EXECUTIONS CONCURRENTES             -> une admise, une NON EXECUTEE
#
# CE QUE CE FICHIER NE PROUVE PAS
# --------------------------------
# Qu'aucun autre chemin ne puisse detruire ces roles. Un `psql` a la main le
# peut, et c'est hors du modele de menace: on vise l'operateur distrait, la
# variable heritee, la commande copiee — pas l'operateur decide.
#
# IL DOIT ETRE EXECUTE SUR LE CLUSTER JETABLE, comme le reste de la suite: il
# cree et detruit ses propres temoins.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

harnais_connexion || exit 2

# LA GARDE S'APPLIQUE A CE FICHIER AUSSI (correctif #1).
#
# Il n'appelait que `harnais_connexion`, puis creait et detruisait des roles
# GLOBAUX portant les noms canoniques. Le fichier qui PROUVE que les harnais
# refusent un cluster tiers etait donc lui-meme le seul a ne pas le verifier.
# Un garde-fou exempte de son propre garde-fou n'en est pas un.
# LE VERROU AVANT LA PORTE. La porte lit le CATALOGUE — roles de plateforme
# geree, bases etrangeres. Deux executions simultanees y voient les objets
# TRANSITOIRES l'une de l'autre et se refusent mutuellement pour un motif faux:
# mesure, une seconde execution rapportait « ce cluster porte supabase_admin »
# alors qu'il s'agissait du temoin momentane de la premiere. Le verrou, lui, ne
# detruit rien; le prendre d'abord rend la porte deterministe.
harnais_verrou_prendre "harness_safety_selftest.sh" || exit 3
exiger_cluster_jetable "harness_safety_selftest.sh" || exit 2

# Le verrou, comme les autres. Il est pris ICI et transmis aux enfants par
# `EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE`: sans quoi la commande canonique
# invoquee plus bas refuserait sur le verrou, et les scenarios prouveraient
# le mauvais refus.

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment)

adm() { psql -X -q -d postgres "$@"; }

# Le cluster doit etre PROPRE avant de commencer: si les roles canoniques
# existaient deja, les temoins seraient indistinguables d'un residu et les
# cinq controles passeraient sans rien prouver.
PRESENTS=$(adm -tAc "
  select count(*) from pg_roles
   where rolname = any (array['${CANONIQUES[0]}','${CANONIQUES[1]}',
                              '${CANONIQUES[2]}','${CANONIQUES[3]}',
                              '${CANONIQUES[4]}'])")
if [[ "$PRESENTS" != "0" ]]; then
  echo "      NON EXECUTE: $PRESENTS role(s) canonique(s) preexistent. Les" >&2
  echo "              temoins ne seraient pas distinguables d'un residu, et" >&2
  echo "              ce fichier ne prouverait rien." >&2
  echo "              Nettoyez le cluster, puis relancez." >&2
  # CODE 3, distinct du rouge. « Une barriere cede » et « le decor manque »
  # sont deux nouvelles differentes, et les confondre ferait chercher une
  # faille de securite la ou il n'y a qu'un residu d'execution precedente.
  exit 3
fi

# --------------------------------------------------------------------------
# LES TEMOINS: des roles portant EXACTEMENT les noms canoniques.
# --------------------------------------------------------------------------
# Ils tiennent le role des VRAIS roles normatifs d'un cluster partage. Si un
# harnais les detruit, il aurait detruit ceux d'une production.
poser_temoins() {
  local r
  for r in "${CANONIQUES[@]}"; do
    creer_temoin_nomme role "$r" || return 1
  done
  return 0
}
retirer_temoins() {
  local r
  for r in "${CANONIQUES[@]}"; do
    detruire_temoin_nomme role "$r" || true
  done
}
temoins_intacts() {
  local n
  n=$(adm -tAc "
    select count(*) from pg_roles
     where rolname = any (array['${CANONIQUES[0]}','${CANONIQUES[1]}',
                                '${CANONIQUES[2]}','${CANONIQUES[3]}',
                                '${CANONIQUES[4]}'])")
  [[ "$n" == "5" ]]
}

# NE DETRUIRE QUE CE DONT LA CREATION A REUSSI (correctif #1).
#
# Le nettoyage commencait par `drop role if exists supabase_admin` et
# `drop database if exists base_etrangere_temoin`, des noms FIXES, avant meme
# de savoir s'ils avaient ete crees ici. Sur un cluster ou un `supabase_admin`
# preexistait — precisement le cluster que ce fichier existe pour proteger — il
# l'aurait detruit. Le fichier qui verifie qu'on ne detruit rien detruisait.
#
# Chaque creation est donc CONSTATEE, et seule une creation constatee autorise
# la destruction correspondante.
CREES=()
creer_temoin_nomme() {
  local quoi="$1" nom="$2"
  case "$quoi" in
    role) adm -v ON_ERROR_STOP=1 -c "create role \"$nom\" nologin;" >/dev/null || return 1 ;;
    base) adm -v ON_ERROR_STOP=1 -c "create database \"$nom\";"     >/dev/null || return 1 ;;
    *) return 1 ;;
  esac
  CREES+=("$quoi:$nom")
  return 0
}
detruire_temoin_nomme() {
  local quoi="$1" nom="$2" i
  # La destruction n'est permise que si la creation figure au registre.
  for i in "${!CREES[@]}"; do
    if [[ "${CREES[$i]}" == "$quoi:$nom" ]]; then
      case "$quoi" in
        role) adm -c "drop owned by \"$nom\";" >/dev/null 2>&1
              adm -c "drop role if exists \"$nom\";" >/dev/null 2>&1 ;;
        base) adm -c "drop database if exists \"$nom\";" >/dev/null 2>&1 ;;
      esac
      unset 'CREES[i]'
      return 0
    fi
  done
  return 1
}

nettoyer() {
  local e quoi nom
  # A l'envers, et uniquement le registre.
  for (( i=${#CREES[@]}-1 ; i>=0 ; i-- )); do
    e="${CREES[i]:-}"; [[ -n "$e" ]] || continue
    quoi="${e%%:*}"; nom="${e#*:}"
    detruire_temoin_nomme "$quoi" "$nom"
  done
  harnais_verrou_rendre
}
trap nettoyer EXIT

echo "    securite des harnais: la commande canonique ne detruit rien"

# `run.sh` est LA COMMANDE CANONIQUE. On l'invoque telle qu'un operateur la
# taperait, et on exige qu'elle refuse AVANT toute destruction.
#
# `timeout` parce qu'un refus doit etre immediat: si un jour la porte cessait
# de fermer, on ne veut pas que ce fichier laisse la suite entiere s'executer
# et detruire les temoins pendant qu'il attend.
canonique() { timeout 120 "$HERE/run.sh" >/dev/null 2>&1; }
deux_phases() { timeout 120 "$HERE/two_phase_deployment.sh" selftest >/dev/null 2>&1; }

# --------------------------------------------------------------------------
# 1. SANS CONSENTEMENT — le cas de loin le plus probable
# --------------------------------------------------------------------------
poser_temoins || { echoue "pose des temoins impossible"; exit 1; }
(unset EUROSTRUCT_CLUSTER_JETABLE; canonique) && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "la commande canonique s'est executee SANS consentement declare"
elif temoins_intacts; then
  echo "      ok: 1. sans consentement — refus (code $CODE), 5 temoins intacts"
else
  echoue "1. sans consentement: le refus a quand meme detruit des temoins"
fi

# --------------------------------------------------------------------------
# 2. CONSENTEMENT, MAIS HOTE NON LOCAL
# --------------------------------------------------------------------------
# La declaration ne doit pas pouvoir emporter le harnais sur un hote distant.
# `192.0.2.1` est reserve a la documentation (RFC 5737): il ne designe aucune
# machine reelle, et aucune connexion n'en sortira.
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export PGHOST=192.0.2.1 PGCONNECT_TIMEOUT=2
 canonique) && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "la commande canonique a accepte un hote non local"
elif temoins_intacts; then
  echo "      ok: 2. hote non local — refus (code $CODE), 5 temoins intacts"
else
  echoue "2. hote non local: des temoins ont ete detruits"
fi

# --------------------------------------------------------------------------
# 3. CONSENTEMENT, MAIS MARQUEUR DE PLATEFORME GEREE
# --------------------------------------------------------------------------
# Le cas Supabase, simule par le role qui en est la signature. La declaration
# est presente et l'hote est local: seul le constat de catalogue peut refuser.
creer_temoin_nomme role supabase_admin \
  || { echoue "3. impossible de creer le marqueur: scenario non joue"; }
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole; canonique) \
  && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "la commande canonique s'est executee sur un cluster portant"
  echoue "  « supabase_admin »: elle aurait tourne sur Supabase"
elif temoins_intacts; then
  echo "      ok: 3. marqueur Supabase — refus (code $CODE), 5 temoins intacts"
else
  echoue "3. marqueur Supabase: des temoins ont ete detruits"
fi
detruire_temoin_nomme role supabase_admin || true

# --------------------------------------------------------------------------
# 4. CONSENTEMENT, MAIS BASE ETRANGERE
# --------------------------------------------------------------------------
# Un cluster qui porte autre chose que ces tests est partage avec autre chose,
# et ses roles globaux ne nous appartiennent pas.
creer_temoin_nomme base base_etrangere_temoin \
  || { echoue "4. impossible de creer la base etrangere: scenario non joue"; }
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole; canonique) \
  && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "la commande canonique s'est executee sur un cluster portant une"
  echoue "  base etrangere: il sert a autre chose qu'a ces tests"
elif temoins_intacts; then
  echo "      ok: 4. base etrangere — refus (code $CODE), 5 temoins intacts"
else
  echoue "4. base etrangere: des temoins ont ete detruits"
fi
detruire_temoin_nomme base base_etrangere_temoin || true

# --------------------------------------------------------------------------
# 5. TOUT EST EN ORDRE, MAIS LES ROLES CANONIQUES EXISTENT DEJA
# --------------------------------------------------------------------------
# Le controle le plus important: consentement declare, cluster local, jetable
# et sans marqueur — et pourtant les roles canoniques sont la. Le harnais ne
# peut PAS savoir s'ils sont a lui. Il doit refuser, jamais « repartir
# propre ». C'est exactement le geste qui detruit une production.
#
# C'EST LA COMMANDE CANONIQUE QUI EST EXERCEE (correctif #2). La version
# precedente appelait `two_phase_deployment.sh`: elle prouvait qu'UNE
# sous-surface refuse, pas que la commande qu'un operateur tape s'arrete. Or le
# rouge d'une sous-surface ne suffit pas — `etape()` continue volontairement, et
# la suite serait allee creer puis detruire des roles qui ne lui appartiennent
# pas. `run.sh` porte donc desormais un `exiger_roles_absents` BLOQUANT, place
# avant l'oracle, avant les migrations, avant tout test.
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole; canonique) \
  && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "LA COMMANDE CANONIQUE s'est executee alors que les roles canoniques"
  echoue "  preexistaient: elle les a donc detruits ou reutilises"
elif temoins_intacts; then
  echo "      ok: 5. roles canoniques preexistants — run.sh refuse (code $CODE), intacts"
else
  echoue "5. LA COMMANDE CANONIQUE A DETRUIT DES ROLES QU'ELLE N'AVAIT PAS CREES"
fi

retirer_temoins

# --------------------------------------------------------------------------
# 7. DEUX EXECUTIONS REELLEMENT CONCURRENTES
# --------------------------------------------------------------------------
# LA COURSE QUE CE SCENARIO FERME. `exiger_roles_absents` constate que les
# roles canoniques n'existent pas, et le harnais en deduit que tout role
# canonique present a la fin est a lui. Deux executions simultanees peuvent
# faire ce constat TOUTES LES DEUX, puis l'une detruire les roles que l'autre
# vient de creer — pendant qu'elle s'en sert.
#
# Le verrou consultatif de session ferme cette fenetre. On l'exerce pour de
# vrai: deux processus lances ensemble, sans jeton de proprietaire, donc en
# contention reelle.
#
# LE PARENT GARDE LE VERROU REEL. Une premiere version le relachait le temps
# du scenario — et ouvrait ainsi, pendant une trentaine de secondes, la fenetre
# meme que ce scenario existe pour fermer. Mesure: lancees ensemble, deux
# suites canoniques s'y engouffraient, et la seconde rapportait « ce cluster
# porte supabase_admin » en voyant le temoin momentane de la premiere.
#
# Les deux enfants s'affrontent donc sur une CLE PROPRE au scenario, tandis que
# le parent conserve la vraie. La contention mesuree est reelle; l'exclusion
# vis-a-vis des autres arbres d'execution n'est jamais relachee.
CLE_TEST=$(( 7314159 + 1 + RANDOM ))
SORTIE_A="$(mktemp)"; SORTIE_B="$(mktemp)"
(unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_CLE="$CLE_TEST"
 "$HERE/two_phase_deployment.sh" concA >"$SORTIE_A" 2>&1; echo $? >"$SORTIE_A.code") &
PID_A=$!
(unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_CLE="$CLE_TEST"
 "$HERE/two_phase_deployment.sh" concB >"$SORTIE_B" 2>&1; echo $? >"$SORTIE_B.code") &
PID_B=$!
wait "$PID_A" "$PID_B" 2>/dev/null
CODE_A="$(cat "$SORTIE_A.code" 2>/dev/null || echo 99)"
CODE_B="$(cat "$SORTIE_B.code" 2>/dev/null || echo 99)"

# EXACTEMENT UNE des deux doit avoir ete admise. L'autre doit rendre 3 —
# NON EXECUTE — et n'avoir rien nettoye.
BLOQUEES=0
[[ "$CODE_A" == "3" ]] && BLOQUEES=$((BLOQUEES + 1))
[[ "$CODE_B" == "3" ]] && BLOQUEES=$((BLOQUEES + 1))
if [[ "$BLOQUEES" == "1" ]]; then
  # Et pour la BONNE raison: le diagnostic doit nommer le verrou, pas un autre
  # refus qui rendrait le meme code.
  if grep -qi "verrou de harnais est deja detenu" "$SORTIE_A" "$SORTIE_B"; then
    echo "      ok: 7. deux executions concurrentes — une admise, une NON EXECUTEE (3)"
  else
    echoue "7. une execution a rendu 3, mais sans nommer le verrou:"
    grep -m2 -iE 'REFUS|NON EXECUTE' "$SORTIE_A" "$SORTIE_B" | sed 's/^/              /' >&2
  fi
elif [[ "$BLOQUEES" == "0" ]]; then
  echoue "7. LES DEUX EXECUTIONS CONCURRENTES ONT ETE ADMISES (codes $CODE_A/$CODE_B):"
  echoue "  chacune peut detruire les roles globaux que l'autre vient de creer."
else
  echoue "7. les deux executions ont ete bloquees (codes $CODE_A/$CODE_B):"
  echoue "  le verrou n'a ete pris par personne, ou n'a pas ete rendu."
fi
rm -f "$SORTIE_A" "$SORTIE_B" "$SORTIE_A.code" "$SORTIE_B.code"

# --------------------------------------------------------------------------
# 6. AUCUN SECRET DANS argv — controle statique
# --------------------------------------------------------------------------
# `argv` est lisible par tout processus de la machine. Un mot de passe passe a
# `psql` en argument fuit sans qu'aucune etape ne le mentionne. Le controle est
# statique parce que le defaut est syntaxique: il se voit dans le texte, et le
# voir dans `ps` supposerait de gagner une course.
#
# `supabase_probe.sh` est exclu: il decoupe deja l'URL en variables libpq, et
# son auto-test verifie ce point separement.
# La sortie de `grep -n` a la forme « fichier:ligne:contenu ». Filtrer les
# commentaires par `^\s*#` ne marchait donc pas: le `#` n'est jamais en debut de
# ligne DE LA SORTIE. Les quatre seuls resultats etaient des commentaires
# expliquant le defaut corrige, et ce controle se declarait rouge sur eux.
FAUTIFS=$(grep -nE 'psql[[:space:]]+"\$(DATABASE_URL|\{DATABASE_URL)|psql[[:space:]]+"postgres(ql)?://|psql[[:space:]]+"\$\(url_pour_base' \
  "$HERE"/*.sh 2>/dev/null \
  | grep -v 'supabase_probe' \
  | awk -F: '{ ligne = $0; sub(/^[^:]*:[0-9]+:/, "", ligne)
               if (ligne !~ /^[[:space:]]*#/) print }')
if [[ -n "$FAUTIFS" ]]; then
  echoue "un secret de connexion transite par argv:"
  sed 's/^/              /' <<<"$FAUTIFS" >&2
else
  echo "      ok: 6. aucune URL de connexion en argument de psql"
fi

echo ""
if [[ $KO -eq 0 ]]; then
  echo "================================================="
  echo " Securite des harnais: la commande canonique ne"
  echo " peut detruire aucun role d'un cluster tiers."
  echo "================================================="
  exit 0
fi
echo "================================================="
echo " Securite des harnais: AU MOINS UNE BARRIERE CEDE."
echo "================================================="
exit 1
