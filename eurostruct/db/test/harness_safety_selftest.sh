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
#   8. cle de verrou non numerique              -> refus, aucune injection SQL
#   9. marqueur de reentrance forge             -> refus, pas de contournement
#  10. hote distant sans consentement           -> refus SANS aucune connexion
#  11. VRAIE cle detenue + commande canonique   -> code 3, temoins intacts
#  12. cle empoisonnee AVEC marqueur            -> refus, aucune injection
#  13. nom de base malveillant ou trop long     -> refus avant tout psql
#  14. interruption entre creation et nettoyage -> zero role residuel
#  15. faux psql, sans consentement / hote refuse -> 0 appel a psql
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
# TROIS ETAPES, DANS CET ORDRE, ET L'ORDRE EST LE SUJET.
#
#   1. PRECONTROLE SANS RESEAU — intention declaree et hote de boucle locale,
#      lus dans l'environnement. Aucun octet ne part. Mesure: sans lui, une
#      `DATABASE_URL` distante faisait PARTIR une connexion — et des
#      identifiants avec elle — avant le moindre refus.
#   2. LE VERROU. Il se connecte, mais ne detruit rien. Le prendre avant la
#      porte rend celle-ci deterministe: sinon deux executions simultanees
#      voient les objets TRANSITOIRES l'une de l'autre et se refusent sur un
#      motif faux (« ce cluster porte supabase_admin », mesure).
#   3. LA PORTE CATALOGUE — marqueurs de plateforme geree, bases etrangeres,
#      superutilisateur.
exiger_precontrole_local "harness_safety_selftest.sh" || exit 2
harnais_verrou_prendre "harness_safety_selftest.sh" || exit $?   # 2 = parametre invalide, 3 = verrou detenu
exiger_cluster_jetable "harness_safety_selftest.sh" || exit 2


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
# CE QU'ON EXIGE DU GAGNANT, ET PAS SEULEMENT DU PERDANT.
#
# La version precedente comptait « exactement une bloquee » et s'arretait la.
# Elle ne disait rien de l'autre: une execution qui aurait plante au demarrage
# aurait produit le meme comptage, et le scenario serait passe au vert en
# n'ayant rien exerce du tout.
#
# ETAT ATTENDU DU GAGNANT, dans la phase rouge 6.3b6b: code 1, et sa sortie
# doit porter le marqueur `ATTENDU-ROUGE (6.3b6b)` — preuve qu'il est alle
# jusqu'aux configurations B et C, et n'a pas echoue en chemin.
#
# QUAND 6.3b6b SERA VERT: remplacer `GAGNANT_ATTENDU=1` par `0` et retirer
# l'exigence du marqueur. C'est ecrit ici pour que le changement soit un geste,
# pas une enquete.
GAGNANT_ATTENDU=1

CODES=("$CODE_A" "$CODE_B"); SORTIES=("$SORTIE_A" "$SORTIE_B")
IDX_PERDANT=-1; IDX_GAGNANT=-1
for i in 0 1; do
  if [[ "${CODES[$i]}" == "3" ]]; then IDX_PERDANT=$i; else IDX_GAGNANT=$i; fi
done

if [[ "$IDX_PERDANT" -lt 0 ]]; then
  echoue "7. LES DEUX EXECUTIONS CONCURRENTES ONT ETE ADMISES (codes $CODE_A/$CODE_B):"
  echoue "  chacune peut detruire les roles globaux que l'autre vient de creer."
elif [[ "$IDX_GAGNANT" -lt 0 ]]; then
  echoue "7. les deux executions ont ete bloquees (codes $CODE_A/$CODE_B):"
  echoue "  le verrou n'a ete pris par personne, ou n'a pas ete rendu."
elif ! grep -qi "verrou de harnais est deja detenu" "${SORTIES[$IDX_PERDANT]}"; then
  echoue "7. le perdant a rendu 3, mais sans nommer le verrou:"
  grep -m2 -iE 'REFUS|NON EXECUTE' "${SORTIES[$IDX_PERDANT]}" | sed 's/^/              /' >&2
elif [[ "${CODES[$IDX_GAGNANT]}" != "$GAGNANT_ATTENDU" ]]; then
  echoue "7. le gagnant a rendu ${CODES[$IDX_GAGNANT]} au lieu de $GAGNANT_ATTENDU:"
  echoue "  il n'a pas atteint l'etat attendu de la phase rouge 6.3b6b, et le"
  echoue "  scenario n'a donc rien exerce de ce qu'il annonce."
  grep -m2 -iE 'ECHEC|ERROR' "${SORTIES[$IDX_GAGNANT]}" | sed 's/^/              /' >&2
elif ! grep -q "ATTENDU-ROUGE (6.3b6b)" "${SORTIES[$IDX_GAGNANT]}"; then
  echoue "7. le gagnant a rendu $GAGNANT_ATTENDU mais sans atteindre"
  echoue "  « ATTENDU-ROUGE (6.3b6b) »: il a echoue avant les configurations"
  echoue "  B et C, et le code attendu a ete obtenu pour une autre raison."
else
  echo "      ok: 7. concurrence — perdant 3 (verrou), gagnant $GAGNANT_ATTENDU (ATTENDU-ROUGE atteint)"
fi
# AUCUN RESIDU, apres une concurrence reelle. Le nettoyage du gagnant et
# l'abstention du perdant doivent laisser le cluster tel qu'il etait.
RESIDU=$(adm -tAc "
  select coalesce(string_agg(x, ', '), '') from (
    select datname as x from pg_database where datname like 'conc%'
    union all
    select rolname from pg_roles where rolname like 'conc%'
  ) t")
if [[ -n "$RESIDU" ]]; then
  echoue "7. residus apres concurrence: $RESIDU"
fi
rm -f "$SORTIE_A" "$SORTIE_B" "$SORTIE_A.code" "$SORTIE_B.code"

# --------------------------------------------------------------------------
# 8. LA CLE DE VERROU EST INTERPOLEE DANS DU SQL — elle doit etre validee
# --------------------------------------------------------------------------
# CONTRE-EXEMPLE MESURE sur la version precedente: avec
#
#   EUROSTRUCT_HARNAIS_VERROU_CLE="1); create role X nologin; \
#                                   select pg_try_advisory_lock(1"
#
# le co-processus EXECUTAIT le `create role` — verifie, le role existait apres
# coup — et le harnais annoncait par-dessus « verrou deja detenu », donc un
# etat de verrou faux. Une variable d'environnement devenait un canal
# d'execution SQL arbitraire sous le role administrateur du cluster.
TEMOIN_INJ="temoin_injection_$(harnais_jeton)"
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_CLE="1); create role $TEMOIN_INJ nologin; select pg_try_advisory_lock(1"
 unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 canonique) && CODE=0 || CODE=$?
INJECTE=$(adm -tAc "select count(*) from pg_roles where rolname = '$TEMOIN_INJ'")
if [[ "$INJECTE" != "0" ]]; then
  echoue "8. LA CLE DE VERROU EST UN CANAL D'EXECUTION SQL: le role"
  echoue "  « $TEMOIN_INJ » a ete cree par interpolation."
  # Cree par l'injection, donc a nous: on le retire pour ne pas laisser
  # derriere nous l'objet meme qu'on vient de declarer inacceptable.
  adm -c "drop role if exists \"$TEMOIN_INJ\";" >/dev/null 2>&1
elif [[ "$CODE" == "0" ]]; then
  echoue "8. la commande canonique a accepte une cle de verrou non numerique"
else
  echo "      ok: 8. cle de verrou non numerique — refus (code $CODE), aucune injection"
fi

# --------------------------------------------------------------------------
# 9. LE MARQUEUR DE REENTRANCE NE DOIT PAS SUFFIRE A CONTOURNER LE VERROU
# --------------------------------------------------------------------------
# CONTRE-EXEMPLE MESURE: pendant que le parent detient le verrou,
#
#   EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE=999999 ./two_phase_deployment.sh x
#
# etait ADMIS — « tenu=0 » — et repartait detruire des roles globaux en
# parallele. Une variable d'environnement desactivait le verrou.
#
# Le parent detient ICI le verrou reel. Un enfant qui presente un marqueur
# ARBITRAIRE ne doit pas passer: le marqueur porte desormais le PID du backend
# detenteur, et ce PID est confronte a `pg_locks`.
# LE CODE EXIGE EST 3, ET LUI SEUL.
#
# Une premiere ecriture se contentait de « code non nul ». Verifie par
# mutation: en remettant la version qui croit le marqueur sur parole, l'enfant
# etait ADMIS et rendait 1 — le verdict normal de `two_phase_deployment.sh`,
# rouges attendus compris — et le controle passait au vert en annoncant
# « refus (code 1) ». Il constatait un echec quelconque, pas le refus du
# verrou. Un test qui accepte n'importe quel rouge ne distingue plus l'echec
# qu'il vise de celui qu'il ignore.
SORTIE_9="$(mktemp)"
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE=999999
 timeout 120 "$HERE/two_phase_deployment.sh" forge >"$SORTIE_9" 2>&1) && CODE=0 || CODE=$?
if [[ "$CODE" != "3" ]]; then
  echoue "9. UN MARQUEUR DE REENTRANCE FORGE A CONTOURNE LE VERROU"
  echoue "  (code $CODE au lieu de 3): l'enfant a travaille en parallele du"
  echoue "  parent, et peut detruire les roles globaux que celui-ci utilise."
elif ! grep -qi "verrou de harnais est deja detenu" "$SORTIE_9"; then
  echoue "9. code 3 obtenu, mais le diagnostic ne nomme pas le verrou:"
  grep -m2 -iE 'REFUS|NON EXECUTE' "$SORTIE_9" | sed 's/^/              /' >&2
else
  echo "      ok: 9. marqueur de reentrance forge — refus du verrou (code 3)"
fi
rm -f "$SORTIE_9"

# --------------------------------------------------------------------------
# 10. AUCUNE CONNEXION AVANT LE PRECONTROLE
# --------------------------------------------------------------------------
# CONTRE-EXEMPLE MESURE: avec une `DATABASE_URL` pointant un hote quelconque et
# AUCUN consentement pose, un ecouteur local recevait « CONNEXION RECUE ». Le
# verrou et la porte se connectent tous deux, et precedaient tout controle
# d'intention et d'hote. Presenter des identifiants a une machine qu'on va
# refuser est deja un defaut: le secret a quitte le processus.
PORT_TEMOIN=$(( 5600 + RANDOM % 300 ))
ECOUTE="$(mktemp)"
python3 - "$PORT_TEMOIN" >"$ECOUTE" 2>&1 <<'PYECOUTE' &
import socket, sys
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1]))); s.listen(1); s.settimeout(12)
    c, a = s.accept(); print("CONNEXION"); c.close()
except Exception:
    print("AUCUNE")
PYECOUTE
PID_ECOUTE=$!
sleep 1
# Ni consentement, ni jeton de proprietaire: le refus doit tomber sur
# l'intention, avant le moindre paquet.
(unset EUROSTRUCT_CLUSTER_JETABLE EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 export DATABASE_URL="postgres://u:FICTIF-motdepasse@127.0.0.1:$PORT_TEMOIN/db"
 canonique) && CODE=0 || CODE=$?
kill "$PID_ECOUTE" 2>/dev/null; wait "$PID_ECOUTE" 2>/dev/null
VU="$(cat "$ECOUTE" 2>/dev/null)"; rm -f "$ECOUTE"
if [[ "$CODE" == "0" ]]; then
  echoue "10. la commande canonique s'est executee sans consentement"
elif [[ "$VU" == "CONNEXION" ]]; then
  echoue "10. UNE CONNEXION A ETE OUVERTE avant tout precontrole: des"
  echoue "  identifiants ont ete presentes a un hote que l'on refuse ensuite."
else
  echo "      ok: 10. refus (code $CODE) SANS aucune connexion ouverte"
fi

# --------------------------------------------------------------------------
# 11. LA VRAIE CLE EXCLUT, ET LE PERDANT NE NETTOIE RIEN
# --------------------------------------------------------------------------
# Le scenario 7 fait s'affronter deux enfants sur une cle PROPRE: il prouve
# qu'une cle exclut, pas que LA cle du harnais exclut. Et il ne dit rien de ce
# que fait le perdant — or « refuser » et « refuser sans rien detruire » sont
# deux proprietes distinctes, et c'est la seconde qui protege.
#
# Ici: le parent detient la VRAIE cle, l'enfant est la COMMANDE CANONIQUE sans
# marqueur, et des temoins portant les noms canoniques sont poses avant.
poser_temoins || echoue "11. pose des temoins impossible"
(unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 canonique) && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "11. LA COMMANDE CANONIQUE S'EST EXECUTEE alors que le verrou reel"
  echoue "  etait detenu: deux executions peuvent se croiser."
elif [[ "$CODE" != "3" ]]; then
  echoue "11. refus obtenu avec le code $CODE au lieu de 3 (NON EXECUTE):"
  echoue "  un verrou detenu n'est pas une regression, et ne doit pas en"
  echoue "  prendre l'apparence."
elif ! temoins_intacts; then
  echoue "11. LE PERDANT A NETTOYE: des temoins ont disparu. Un nettoyage par"
  echoue "  l'execution refusee emporte les objets de celle qui travaille."
else
  echo "      ok: 11. vraie cle — refus (code 3), 5 temoins intacts, aucun nettoyage"
fi
retirer_temoins


# --------------------------------------------------------------------------
# 12. LA CLE EST VALIDEE AVANT LA PREMIERE REQUETE, MARQUEUR PRESENT
# --------------------------------------------------------------------------
# Le scenario 8 empoisonne la cle sans marqueur de reentrance: le refus tombe
# alors avant la requete de reentrance, qui n'est pas atteinte. AVEC un
# marqueur, cette requete-la interpole la cle — et c'est par elle que
# l'injection passait.
#
# CONTRE-EXEMPLE MESURE: `harnais_valider_cle` etait appelee APRES le bloc de
# reentrance. Le `create role` injecte s'executait, et le refus « cle de verrou
# invalide » tombait ensuite. Valider apres avoir tire, c'est valider pour la
# forme.
TEMOIN_INJ2="temoin_reentrance_$(harnais_jeton)"
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE=1
 export EUROSTRUCT_HARNAIS_VERROU_CLE="0 ; create role $TEMOIN_INJ2 nologin ; select 0"
 deux_phases) && CODE=0 || CODE=$?
INJ2=$(adm -tAc "select count(*) from pg_roles where rolname = '$TEMOIN_INJ2'")
if [[ "$INJ2" != "0" ]]; then
  echoue "12. LA REQUETE DE REENTRANCE EST UN CANAL D'INJECTION: le role"
  echoue "  « $TEMOIN_INJ2 » a ete cree avant toute validation."
  adm -c "drop role if exists \"$TEMOIN_INJ2\";" >/dev/null 2>&1
elif [[ "$CODE" == "0" ]]; then
  echoue "12. la cle empoisonnee a ete acceptee malgre le marqueur"
else
  echo "      ok: 12. cle empoisonnee + marqueur — refus (code $CODE), aucune injection"
fi

# Et le marqueur invalide est REFUSE, pas assaini. « 99abc9 » ne doit pas
# devenir « 999 »: transformer une entree refusable en entree acceptable, c'est
# deviner l'intention plutot que la verifier.
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE="99abc9"
 deux_phases) && CODE=0 || CODE=$?
if [[ "$CODE" == "2" ]]; then
  echo "      ok: 12b. marqueur non numerique — refuse (code 2), non assaini"
else
  echoue "12b. un marqueur non numerique n'a pas ete refuse (code $CODE):"
  echoue "  il a ete assaini, donc devine."
fi

# --------------------------------------------------------------------------
# 13. UN NOM DE BASE MALVEILLANT EST REFUSE AVANT TOUT psql
# --------------------------------------------------------------------------
# `DB_NAME` vient de l'environnement et etait interpole tel quel. La longueur
# compte autant que la forme: les harnais derivent des noms jusqu'a 20
# caracteres plus longs, et PostgreSQL TRONQUE a 63 — deux bases distinctes
# pourraient devenir la meme, et un harnais detruire les objets de l'autre.
TEMOIN_DB="temoin_dbname_$(harnais_jeton)"
SORTIE_13="$(mktemp)"
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export DB_NAME="x\"; create role $TEMOIN_DB nologin; --"
 timeout 120 "$HERE/run.sh" >"$SORTIE_13" 2>&1) && CODE=0 || CODE=$?
INJ3=$(adm -tAc "select count(*) from pg_roles where rolname = '$TEMOIN_DB'")
# LE REFUS DOIT VENIR DE `run.sh` LUI-MEME.
#
# Verifie par mutation: en retirant `harnais_valider_identifiant` de `run.sh`,
# ce controle restait VERT — parce que les SOUS-SCRIPTS refusaient ensuite, avec
# les codes 3 et 1. Il constatait « quelqu'un a refuse », pas « la commande
# canonique valide son propre parametre ». Un refus obtenu par ricochet
# disparait des qu'on reordonne les etapes.
#
# On exige donc le code 2 ET un diagnostic qui nomme `DB_NAME` — celui que
# seul `run.sh` produit; les sous-scripts, eux, parlent de « nom de base » avec
# leur suffixe (`_oracle`, `_2p`).
if [[ "$INJ3" != "0" ]]; then
  echoue "13. UN NOM DE BASE A INJECTE DU SQL: « $TEMOIN_DB » a ete cree."
  adm -c "drop role if exists \"$TEMOIN_DB\";" >/dev/null 2>&1
elif [[ "$CODE" != "2" ]]; then
  echoue "13. refus obtenu avec le code $CODE au lieu de 2: la commande"
  echoue "  canonique n'a pas valide son propre parametre, un sous-script a"
  echoue "  refuse par ricochet."
elif ! grep -q "DB_NAME" "$SORTIE_13"; then
  echoue "13. code 2 obtenu, mais le diagnostic ne nomme pas DB_NAME:"
  grep -m2 -i "REFUS" "$SORTIE_13" | sed 's/^/              /' >&2
else
  echo "      ok: 13. nom de base malveillant — run.sh refuse (code 2), aucune injection"
fi
rm -f "$SORTIE_13"

# La longueur, separement: un nom conforme mais trop long doit etre refuse.
SORTIE_13B="$(mktemp)"
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 export DB_NAME="b$(printf 'a%.0s' $(seq 1 60))"
 timeout 120 "$HERE/run.sh" >"$SORTIE_13B" 2>&1) && CODE=0 || CODE=$?
if [[ "$CODE" != "2" ]]; then
  echoue "13b. refus obtenu avec le code $CODE au lieu de 2: la longueur n'est"
  echoue "  pas controlee par la commande canonique. Les noms derives"
  echoue "  depasseraient 63 et PostgreSQL les tronquerait en silence."
elif ! grep -q "au-dela de" "$SORTIE_13B"; then
  echoue "13b. code 2 obtenu, mais pas sur le motif de longueur:"
  grep -m2 -i "REFUS" "$SORTIE_13B" | sed 's/^/              /' >&2
else
  echo "      ok: 13b. nom de base trop long — run.sh refuse (code 2)"
fi
rm -f "$SORTIE_13B"

# --------------------------------------------------------------------------
# 14. INTERRUPTION ENTRE CREATION ET NETTOYAGE — zero role residuel
# --------------------------------------------------------------------------
# Les roles temporaires F1 et F3 de `two_phase_deployment.sh` etaient crees
# puis detruits une trentaine de lignes plus bas, hors de tout registre. Toute
# interruption entre les deux les laissait derriere, et la postcondition ne les
# couvrait pas — elle ne connaissait que le registre.
#
# On interrompt donc POUR DE VRAI, a un instant ou F1 et F3 existent, et on
# exige qu'il ne reste rien. Le piege de sortie est le seul filet: c'est
# exactement ce qu'on teste.
# DETERMINISTE, ET NON « on attend six secondes ».
#
# La premiere ecriture faisait `sleep 6` puis `kill`, puis constatait l'absence
# de residu. Elle serait passee au VERT si le processus s'etait deja termine de
# lui-meme avant le `kill`: on aurait alors constate un nettoyage NORMAL, pas
# un nettoyage APRES INTERRUPTION, et le scenario aurait prouve le contraire de
# ce qu'il annonce. Un test dont le sujet depend d'une course n'est pas un test.
#
# On exige donc, AVANT d'envoyer TERM, deux faits constates:
#   * le processus est encore vivant;
#   * F1 ET F3 existent — c'est-a-dire qu'on interrompt bien DANS la fenetre
#     entre creation et nettoyage.
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
 unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
 export EUROSTRUCT_HARNAIS_VERROU_CLE=$(( 7314159 + 2 + RANDOM ))
 "$HERE/two_phase_deployment.sh" interr >/dev/null 2>&1) &
PID_INT=$!

# Attente ACTIVE et bornee: on scrute l'apparition de F1 et F3.
FENETRE=0
for _ in $(seq 1 200); do
  kill -0 "$PID_INT" 2>/dev/null || break     # le processus est mort: fenetre ratee
  if [[ "$(adm -tAc "select count(*) from pg_roles
                      where rolname like 'interr%_f1_%'
                         or rolname like 'interr%_f3_%'")" == "2" ]]; then
    FENETRE=1; break
  fi
  sleep 0.2
done

if [[ "$FENETRE" != "1" ]]; then
  # NON CONCLUANT, et dit comme tel: ni vert ni rouge de securite. Le scenario
  # n'a pas pu se placer dans la fenetre qu'il vise.
  echoue "14. la fenetre entre creation et nettoyage n'a pas ete atteinte:"
  echoue "  F1 et F3 n'ont pas ete observes ensemble pendant que le processus"
  echoue "  vivait. Le scenario n'a rien exerce."
  kill -TERM "$PID_INT" 2>/dev/null; wait "$PID_INT" 2>/dev/null
elif ! kill -0 "$PID_INT" 2>/dev/null; then
  echoue "14. le processus s'est termine avant l'interruption: ce qui suivrait"
  echoue "  constaterait un nettoyage NORMAL, pas un nettoyage apres coupure."
else
  # Les deux faits sont etablis: on coupe.
  kill -TERM "$PID_INT" 2>/dev/null
  wait "$PID_INT" 2>/dev/null
  # Le piege de sortie s'execute dans le processus interrompu; on lui laisse le
  # temps de rendre la main, en scrutant plutot qu'en dormant au hasard.
  APRES="?"
  for _ in $(seq 1 50); do
    APRES=$(adm -tAc "select coalesce(string_agg(rolname, ', '), '')
                        from pg_roles where rolname like 'interr%'")
    [[ -z "$APRES" ]] && break
    sleep 0.2
  done
  if [[ -n "$APRES" ]]; then
    echoue "14. APRES INTERRUPTION, des roles subsistent: $APRES"
    for r in ${APRES//,/ }; do adm -c "drop role if exists \"${r// /}\";" >/dev/null 2>&1; done
  else
    echo "      ok: 14. interruption DANS la fenetre (F1+F3 vus, processus vivant) — zero residu"
  fi
fi

# --------------------------------------------------------------------------
# 15. FAUX psql — LE COMPTEUR D'APPELS DOIT RESTER STRICTEMENT A ZERO
# --------------------------------------------------------------------------
# Les scenarios 2 et 10 constatent qu'aucune CONNEXION n'aboutit. Ils ne
# disent rien d'un `psql` qui serait lance et echouerait: le processus aurait
# quand meme ete cree, avec `PGPASSWORD` dans son environnement.
#
# On substitue donc un faux `psql` qui ne fait qu'INCREMENTER UN COMPTEUR. Sans
# consentement, ou avec un hote refuse, il ne doit jamais etre appele — pas une
# fois. C'est la formulation la plus stricte de « aucun octet ne part », et la
# seule qui ne depende pas de la reussite d'une connexion.
FAUX="$(mktemp -d)"
cat > "$FAUX/psql" <<'FINFAUX'
#!/usr/bin/env bash
echo "appel" >> "$COMPTEUR_PSQL"
exit 0
FINFAUX
chmod +x "$FAUX/psql"

for cas in "sans consentement" "hote refuse"; do
  COMPTEUR="$(mktemp)"; : > "$COMPTEUR"
  if [[ "$cas" == "sans consentement" ]]; then
    (unset EUROSTRUCT_CLUSTER_JETABLE EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
     export COMPTEUR_PSQL="$COMPTEUR" PATH="$FAUX:$PATH"
     timeout 60 "$HERE/role_prerequisites.sh" temoin_faux_psql >/dev/null 2>&1) \
      && CODE=0 || CODE=$?
  else
    (unset EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE
     export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole
     export PGHOST=192.0.2.1
     export COMPTEUR_PSQL="$COMPTEUR" PATH="$FAUX:$PATH"
     timeout 60 "$HERE/role_prerequisites.sh" temoin_faux_psql >/dev/null 2>&1) \
      && CODE=0 || CODE=$?
  fi
  APPELS=$(wc -l < "$COMPTEUR" | tr -d ' ')
  rm -f "$COMPTEUR"
  if [[ "$CODE" == "0" ]]; then
    echoue "15. « $cas »: le harnais s'est execute au lieu de refuser"
  elif [[ "$APPELS" != "0" ]]; then
    echoue "15. « $cas »: $APPELS appel(s) a psql AVANT le refus. Un processus"
    echoue "  a ete cree, avec PGPASSWORD dans son environnement."
  else
    echo "      ok: 15. « $cas » — refus (code $CODE), 0 appel a psql"
  fi
done
rm -rf "$FAUX"

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
