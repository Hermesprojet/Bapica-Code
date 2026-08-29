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

# SIX, et non cinq: `eurostruct_normative_activator` est canonique depuis
# 6.3b6b. Le nombre de temoins attendus intacts suit (voir `temoins_intacts`).
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment
            eurostruct_authority_backend)

adm() { psql -X -q -d postgres "$@"; }

# Le cluster doit etre PROPRE avant de commencer: si les roles canoniques
# existaient deja, les temoins seraient indistinguables d'un residu et les
# controles passeraient sans rien prouver.
#
# DERIVE DU TABLEAU, comme `temoins_intacts` et pour la meme raison: la liste
# enumeree a la main s'arretait a cinq indices et ignorait donc le sixieme role
# canonique — c'est-a-dire exactement le residu qu'elle existe pour detecter.
LISTE_CANONIQUES=""
for r in "${CANONIQUES[@]}"; do LISTE_CANONIQUES+="${LISTE_CANONIQUES:+,}'$r'"; done
PRESENTS=$(adm -tAc "select count(*) from pg_roles
                      where rolname in ($LISTE_CANONIQUES)")
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
# LA LISTE EST DERIVEE DU TABLEAU, ET LE COMPTE AUSSI.
#
# Cette fonction enumerait cinq indices a la main et comparait a un nombre
# ecrit en dur. Quand `eurostruct_normative_activator` a rejoint le jeu
# canonique, elle a continue a n'interroger que cinq noms tout en en attendant
# six: les QUINZE barrieres sont passees au rouge d'un coup, alors qu'aucune
# n'avait cede. Deriver les deux du meme tableau rend cette derive impossible.
temoins_intacts() {
  local n liste="" r
  for r in "${CANONIQUES[@]}"; do liste+="${liste:+,}'$r'"; done
  n=$(adm -tAc "select count(*) from pg_roles where rolname in ($liste)")
  [[ "$n" == "${#CANONIQUES[@]}" ]]
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
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

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
  echo "      ok: 1. sans consentement — refus (code $CODE), ${#CANONIQUES[@]} temoins intacts"
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
  echo "      ok: 2. hote non local — refus (code $CODE), ${#CANONIQUES[@]} temoins intacts"
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
  echo "      ok: 3. marqueur Supabase — refus (code $CODE), ${#CANONIQUES[@]} temoins intacts"
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
  echo "      ok: 4. base etrangere — refus (code $CODE), ${#CANONIQUES[@]} temoins intacts"
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
# ETAT ATTENDU DU GAGNANT: code 0, et sa sortie doit montrer qu'il est alle
# JUSQU'AU BOUT — configuration C menee de PENDING a ACTIVE. Le code seul ne
# suffirait pas: une execution qui sortirait 0 sans avoir rien exerce le
# donnerait aussi.
#
# 6.3b6b etant vert, `GAGNANT_ATTENDU` passe de 1 a 0 et le marqueur
# `ATTENDU-ROUGE (6.3b6b)` — qui prouvait l'inverse, a savoir que le gagnant
# avait bien atteint le rouge annonce — cede la place a la preuve positive.
# Le changement etait annonce ici comme un geste: il l'a ete.
GAGNANT_ATTENDU=0
PREUVE_GAGNANT="C PENDING -> ACTIVE"

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
elif ! grep -qF "$PREUVE_GAGNANT" "${SORTIES[$IDX_GAGNANT]}"; then
  echoue "7. le gagnant a rendu $GAGNANT_ATTENDU mais sa sortie ne montre pas"
  echoue "  « $PREUVE_GAGNANT »: il n'a pas mene la configuration C jusqu'a"
  echoue "  l'activation, et le code attendu a ete obtenu pour une autre raison."
else
  echo "      ok: 7. concurrence — perdant 3 (verrou), gagnant $GAGNANT_ATTENDU"
  echo "             (« $PREUVE_GAGNANT » atteint)"
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
  echo "      ok: 11. vraie cle — refus (code 3), ${#CANONIQUES[@]} temoins intacts, aucun nettoyage"
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
# LE SIGNAL DOIT ATTEINDRE LE SCRIPT, PAS UN INTERMEDIAIRE.
#
# La forme `( export ...; "$HERE/two_phase_deployment.sh" ... ) &` mettait un
# SOUS-SHELL entre `$!` et le script. `kill -TERM $PID_INT` tuait le
# sous-shell; le script, devenu orphelin, CONTINUAIT. Le scenario constatait
# alors « zero residu » — parce que le script n'avait pas encore cree ses roles
# — puis ceux-ci apparaissaient apres coup et faisaient refuser les executions
# suivantes. Mesure: `interr_mig_*`, `interr_ctl_*` et jusqu'a six roles
# canoniques restaient sur le cluster, et deux auto-tests consecutifs
# echouaient sur un decor qu'ils croyaient propre.
#
# `env` REMPLACE son propre processus par le script: `$!` est donc le PID du
# script lui-meme, et le signal l'atteint.
# `-u` AVANT les affectations: des qu'`env` rencontre un `NAME=VALUE`, tout ce
# qui suit est la COMMANDE. Ecrit apres, `-u` etait pris pour le programme a
# lancer, le processus mourait aussitot, et la fenetre n'etait jamais atteinte
# — un rouge « le scenario n'a rien exerce », honnete mais du au lanceur.
env -u EUROSTRUCT_HARNAIS_VERROU_PROPRIETAIRE \
    EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
    EUROSTRUCT_HARNAIS_VERROU_CLE=$(( 7314159 + 2 + RANDOM )) \
    "$HERE/two_phase_deployment.sh" interr >/dev/null 2>&1 &
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
  # LES ROLES CANONIQUES COMPTENT AUSSI, ET CE SONT EUX QUI FONT MAL.
  #
  # Ce constat ne regardait que `interr%`, c'est-a-dire le decor jetable. Or
  # `two_phase_deployment.sh` cree AUSSI les six roles canoniques — des noms
  # imposes, globaux au cluster —, et ce sont ceux-la qui font refuser toute
  # execution ulterieure. Les chercher est le seul moyen de distinguer « le
  # piege a tourne » de « le piege a tourne a moitie ».
  APRES="?"
  for _ in $(seq 1 50); do
    APRES=$(adm -tAc "select coalesce(string_agg(rolname, ', ' order by rolname), '')
                        from pg_roles
                       where rolname like 'interr%'
                          or rolname in ($LISTE_CANONIQUES)")
    [[ -z "$APRES" ]] && break
    sleep 0.2
  done
  # ET LA BASE, pour la meme raison: une base residuelle n'est pas moins un
  # residu qu'un role, et elle retient les roles qui la possedent.
  BASES_APRES=$(adm -tAc "select coalesce(string_agg(datname, ', '), '')
                            from pg_database where datname like 'interr%'")
  if [[ -n "$APRES" || -n "$BASES_APRES" ]]; then
    echoue "14. APRES INTERRUPTION, le decor subsiste:"
    [[ -n "$APRES" ]]       && echoue "  roles: $APRES"
    [[ -n "$BASES_APRES" ]] && echoue "  bases: $BASES_APRES"
    for b in ${BASES_APRES//,/ }; do adm -c "drop database if exists \"${b// /}\";" >/dev/null 2>&1; done
    for r in ${APRES//,/ }; do
      adm -c "drop owned by \"${r// /}\";" >/dev/null 2>&1
      adm -c "drop role if exists \"${r// /}\";" >/dev/null 2>&1
    done
  else
    echo "      ok: 14. interruption DANS la fenetre (F1+F3 vus, processus vivant) —"
    echo "             ni role jetable, ni role canonique, ni base residuels"
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

# --------------------------------------------------------------------------
# 16. LE DIAGNOSTIC NE TRONQUE PAS LA SOURCE DE VERITE
# --------------------------------------------------------------------------
# CE QUI EST MESURE ICI, ET POURQUOI CE CONTROLE EXISTE. Deux mutations (B'
# et B=) ont ete comptees SURVIVED lors de la campagne du 82: elles TUAIENT
# bien, a l'installation, mais l'identifiant `AUTHORITY_COMPOSITION_*` tombait
# au-dela du 200e caractere de la ligne ERROR et rien ne le rapportait.
#
# On fabrique donc une sortie ou l'identifiant est DELIBEREMENT place tres
# au-dela de la coupe d'affichage, et on exige qu'il atteigne quand meme le
# lecteur. Le controle est plus exigeant que le defaut d'origine: 500
# caracteres de bourrage, la ou la coupe etait a 200.
BOURRAGE="$(printf 'x%.0s' $(seq 1 500))"
FAUX_ERREUR="psql:0014_four_eyes_decisions.sql:812: ERROR:  $BOURRAGE AUTHORITY_COMPOSITION_FORCE_RLS_MISSING: la table normative_authority_decisions n'a pas FORCE ROW LEVEL SECURITY
CONTEXT:  PL/pgSQL function assert_authority_composition() line 214 at RAISE"
POSITION=$(awk -v s="$FAUX_ERREUR" 'BEGIN{ print index(s, "AUTHORITY_COMPOSITION_FORCE_RLS_MISSING") }')
# REDIRECTION, ET NON `$( ... )`. Mesure faite en ecrivant ce controle: la
# substitution de commande execute la fonction dans un SOUS-SHELL, et
# `ESC_DIAG_CAPTURE` — qui y est cree — ne revenait pas au parent. Le controle
# se declarait alors rouge sur « aucune capture », en accusant le helper d'un
# defaut qui etait dans sa propre mesure.
DIAG_SORTIE="$(mktemp "${TMPDIR:-/tmp}/esc_ct16_XXXXXX")"
esc_diag_rapporter "auto-test 16" "$FAUX_ERREUR" 2>"$DIAG_SORTIE"
DIAG_VU="$(cat "$DIAG_SORTIE")"
rm -f "$DIAG_SORTIE"
if (( POSITION <= 500 )); then
  echoue "16. l'auto-test est trop faible: l'identifiant est au caractere"
  echoue "    $POSITION, en deca des 500 exiges — il ne prouverait rien."
elif ! grep -q "invariant: AUTHORITY_COMPOSITION_FORCE_RLS_MISSING" <<<"$DIAG_VU"; then
  echoue "16. l'identifiant place au caractere $POSITION n'atteint PAS le"
  echoue "    lecteur. Un refus d'installation redeviendrait indiscernable"
  echoue "    d'une panne, et la mutation correspondante compterait SURVIVED."
  sed 's/^/              /' <<<"$DIAG_VU" >&2
elif [[ ! -f "${ESC_DIAG_CAPTURE:-/inexistant}" ]]; then
  echoue "16. aucune capture integrale n'existe: la source de verite n'est"
  echoue "    conservee nulle part."
elif ! grep -q "$BOURRAGE" "$ESC_DIAG_CAPTURE"; then
  echoue "16. la capture ne contient pas la sortie INTEGRALE."
else
  echo "      ok: 16. identifiant au caractere $POSITION — rapporte, et la"
  echo "             capture integrale conserve $(wc -c <"$ESC_DIAG_CAPTURE") octets"
fi

# --------------------------------------------------------------------------
# 18. LE DIAGNOSTIC N'EMET JAMAIS D'OCTET ORPHELIN
# --------------------------------------------------------------------------
# CE QUI A ETE MESURE, ET CE QUE CE CONTROLE EMPECHE DE REVENIR. Sous
# `LC_CTYPE=POSIX`, `cut -c` compte des OCTETS et non des caracteres. Une coupe
# tombant au milieu d'un tiret cadratin (« — », E2 80 94) laissait un `E2`
# orphelin dans la sortie du harnais; le lanceur de campagne, qui decode en
# UTF-8, mourait alors en `UnicodeDecodeError: invalid continuation byte`.
# Quatre-vingt-dix garanties perdues d'un coup — sans le moindre verdict — sur
# un octet d'AFFICHAGE.
#
# On place donc un caractere multi-octets exactement sur la coupe, et on exige
# que la sortie reste decodable. Le controle vaut aussi pour l'invariant: le
# nom doit toujours atteindre le lecteur.
# ON BALAIE LE VOISINAGE DE LA COUPE, on ne parie pas sur un decalage.
# Mesure faite en ecrivant ce controle: avec 195 caracteres de bourrage le
# tiret tombait APRES la coupe, la sortie restait valide, et le controle
# passait au vert meme en retirant la protection — il ne prouvait rien. Les
# valeurs qui font effectivement chevaucher la coupe sont 189 et 190; les
# balayer toutes rend le controle independant de mon arithmetique.
COUPE_KO=0; COUPE_TESTEES=0; COUPE_CHEVAUCHANTES=0
for n in 186 187 188 189 190 191 192 193; do
  COUPE_SORTIE="$(mktemp "${TMPDIR:-/tmp}/esc_ct18_XXXXXX")"
  BOURRAGE_N="$(printf 'x%.0s' $(seq 1 "$n")).0"
  BOURRAGE_N="${BOURRAGE_N%.0}"
  esc_diag_rapporter "auto-test 18 (bourrage $n)" \
    "ERROR:  $BOURRAGE_N — AUTHORITY_COUPE_MULTIOCTET: le tiret est sur la coupe" \
    2>"$COUPE_SORTIE"
  COUPE_TESTEES=$((COUPE_TESTEES + 1))
  # Le tiret chevauche-t-il la coupe ? On le constate sur la sortie NON
  # protegee, en comptant les octets: la reponse ne vient pas d'un calcul.
  if ! python3 -c 'import sys; open(sys.argv[1],"rb").read().decode("utf-8")' \
         "$COUPE_SORTIE" 2>/dev/null; then
    echoue "18. bourrage $n: la sortie du diagnostic n'est pas de l'UTF-8"
    echoue "    valide — un octet orphelin subsiste, et le lanceur de campagne"
    echoue "    mourrait dessus sans rendre le moindre verdict."
    COUPE_KO=1
  fi
  if ! grep -q "invariant: AUTHORITY_COUPE_MULTIOCTET" "$COUPE_SORTIE"; then
    echoue "18. bourrage $n: l'identifiant n'atteint pas le lecteur."
    COUPE_KO=1
  fi
  # Une coupe qui tombe pile sur le tiret perd le caractere entier: c'est la
  # signature du chevauchement, et elle doit exister pour au moins un `n` —
  # sinon le balayage passerait a cote du cas qu'il pretend couvrir.
  grep -q -- "—" "$COUPE_SORTIE" || COUPE_CHEVAUCHANTES=$((COUPE_CHEVAUCHANTES + 1))
  rm -f "$COUPE_SORTIE"
done
if (( COUPE_CHEVAUCHANTES == 0 )); then
  echoue "18. aucun des $COUPE_TESTEES bourrages ne fait chevaucher la coupe:"
  echoue "    le balayage n'exerce pas le cas qu'il annonce."
  COUPE_KO=1
fi
(( COUPE_KO )) || {
  echo "      ok: 18. $COUPE_TESTEES coupes autour de la frontiere, dont"
  echo "             $COUPE_CHEVAUCHANTES sur un caractere multi-octets — sortie"
  echo "             toujours decodable, identifiant toujours rapporte"
}

# --------------------------------------------------------------------------
# 17. LE TEARDOWN D'UN DECOR S'EXECUTE SUR LES CINQ CHEMINS DE SORTIE
# --------------------------------------------------------------------------
# CE QUI A ETE MESURE. `decor_poser` rendait 1 sur six chemins de refus sans
# jamais appeler `decor_deposer`. Le premier refus laissait les roles
# canoniques dans le cluster; tous les decors suivants echouaient en « phase 0
# refusee », et le harnais rendait « rien d'evalue » — ce qu'une campagne de
# mutation lit comme un SURVIVANT. La contamination du scenario suivant est
# une erreur d'infrastructure, jamais une mise a mort.
#
# LES CHEMINS SONT EXERCES DANS DES SOUS-PROCESSUS, chacun avec SON PROPRE
# piege: un seul processus ne peut pas mourir six fois. Le teardown ecrit un
# temoin sur disque — c'est le seul fait qui survive a un `exit`, a un signal,
# ou a un shell qui s'effondre.
#
# CE QUE LE TRAP DEDIE APPORTE, MESURE ET NON SUPPOSE. En ecrivant ce
# controle, la premiere version du chemin « interruption » restait verte quand
# on retirait le trap de `esc_decor_ouvrir`: bash execute le piege EXIT meme
# lorsqu'un signal fatal l'emporte, et c'est LUI qui rendait le decor. La
# table mesuree:
#
#                        trap dedie    pas de trap dedie
#     sans piege EXIT     temoin 1        temoin 0
#     avec piege EXIT     temoin 1        temoin 1
#
# Le trap dedie porte donc exactement un cas: celui ou aucun piege EXIT ne
# couvre le decor. Ce cas n'est pas theorique — bash n'a qu'UN seul piege
# EXIT, et tout scenario qui pose le sien efface silencieusement celui du
# harnais. Le chemin 6 l'exerce, et c'est lui qui rend le trap dedie
# falsifiable au lieu de decoratif.
#
# AUCUN OBJET POSTGRESQL ICI. Le contrat exerce est celui du cycle de vie, et
# il doit tenir meme quand la base n'est pas la cause.
TEMOINS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/esc_cycle_XXXXXX")"
chemin_de_sortie() {                 # chemin_de_sortie <nom> <corps-bash> [sans-exit]
  local nom="$1" corps="$2" sans_exit="${3:-}" pose_piege="trap sortie_globale EXIT" code=0
  [[ -n "$sans_exit" ]] && pose_piege=":"
  bash -c '
    set -uo pipefail
    source "'"$HERE"'/lib_harnais.sh"
    TEMOIN="'"$TEMOINS_DIR"'/'"$nom"'"
    teardown() { echo "rendu" >>"$TEMOIN"; return "${TEARDOWN_CODE:-0}"; }
    sortie_globale() { esc_decor_fermer; }
    '"$pose_piege"'
    esc_decor_ouvrir "'"$nom"'" teardown || exit 9
    '"$corps"'
  ' >/dev/null 2>"$TEMOINS_DIR/$nom.err" || code=$?
  echo "$code"
}

# 1. SUCCES — fermeture explicite, un seul teardown.
C1=$(chemin_de_sortie succes 'esc_decor_fermer; exit 0')
# 2. ERREUR SQL — la forme du refus d'installation: abandon puis code 1.
C2=$(chemin_de_sortie erreur_sql 'esc_decor_abandonner || exit 1')
# 3. ERREUR SHELL — commande inexistante, puis sortie par le trap EXIT.
C3=$(chemin_de_sortie erreur_shell 'commande_qui_nexiste_pas_du_tout; exit 127')
# 4. INTERRUPTION — le processus se tue lui-meme; seul le trap dedie peut
#    encore rendre le decor.
C4=$(chemin_de_sortie interruption 'kill -TERM $$; sleep 5; exit 0')
# 5. ECHEC DANS LE TEARDOWN LUI-MEME — il rend 1; le harnais doit le
#    SIGNALER et non l'avaler.
C5=$(chemin_de_sortie teardown_ko \
     'TEARDOWN_CODE=1; esc_decor_fermer
      (( ESC_DECOR_TEARDOWN_KO == 1 )) || exit 8
      exit 0')
# 6. INTERRUPTION SANS AUCUN PIEGE EXIT — le seul cas ou le trap dedie est
#    LOAD-BEARING. Sans lui, mesure faite: temoin 0.
C6=$(chemin_de_sortie interruption_seule 'kill -TERM $$; sleep 5; exit 0' sans-exit)
# 7. REFUS D'INSTALLATION SANS PIEGE EXIT — la forme EXACTE de `decor_poser`:
#    le chemin de refus doit se rendre LUI-MEME, sans compter sur la fin du
#    harnais. Mesure: avec un piege EXIT, un `esc_decor_abandonner` qui ne
#    ferme rien reste invisible — c'est ce masquage qui a laisse six chemins
#    de refus fuir pendant toute la campagne du 82.
C7=$(chemin_de_sortie erreur_sql_seule 'esc_decor_abandonner || exit 1' sans-exit)

CYCLE_KO=0
for cas in succes erreur_sql erreur_shell interruption teardown_ko \
           interruption_seule erreur_sql_seule; do
  n=$(wc -l <"$TEMOINS_DIR/$cas" 2>/dev/null || echo 0)
  if [[ "$n" == "0" ]]; then
    echoue "17. chemin « $cas »: le teardown ne s'est PAS execute."
    CYCLE_KO=1
  elif [[ "$n" != "1" ]]; then
    # L'idempotence compte autant que l'execution: un teardown joue deux fois
    # rapporterait des echecs de nettoyage imaginaires au second passage.
    echoue "17. chemin « $cas »: teardown execute $n fois, attendu 1."
    CYCLE_KO=1
  fi
  # « SIGNALE, JAMAIS AVALE » A UN REVERS: pas de plainte imaginaire non plus.
  # Mesure: en cassant l'idempotence, le second passage appelait une fonction
  # de teardown vidée et rapportait un echec de nettoyage qui n'existait pas.
  # Le temoin restait a 1 et le controle ne voyait rien.
  # `grep -c` IMPRIME DEJA « 0 » ET REND 1 quand il ne trouve rien: le
  # `|| echo 0` reflexe produisait « 0\n0 » et le controle se declarait rouge
  # sur sa propre mesure. Mesure faite en ecrivant ces lignes.
  plaintes=$(grep -c "ECHEC NETTOYAGE" "$TEMOINS_DIR/$cas.err" 2>/dev/null || true)
  [[ -n "$plaintes" ]] || plaintes=0
  attendu=0; [[ "$cas" == "teardown_ko" ]] && attendu=1
  if [[ "$plaintes" != "$attendu" ]]; then
    echoue "17. chemin « $cas »: $plaintes plainte(s) « ECHEC NETTOYAGE »,"
    echoue "    attendu $attendu."
    CYCLE_KO=1
  fi
done
# Les codes de sortie sont eux aussi le contrat: un refus qui rendrait 0
# laisserait le harnais croire que le decor est pose.
[[ "$C1" == "0"   ]] || { echoue "17. succes rend $C1, attendu 0"; CYCLE_KO=1; }
[[ "$C2" == "1"   ]] || { echoue "17. erreur SQL rend $C2, attendu 1"; CYCLE_KO=1; }
[[ "$C3" == "127" ]] || { echoue "17. erreur shell rend $C3, attendu 127"; CYCLE_KO=1; }
[[ "$C4" == "143" ]] || { echoue "17. interruption rend $C4, attendu 143 (TERM)"; CYCLE_KO=1; }
[[ "$C5" == "0"   ]] || { echoue "17. teardown en echec rend $C5, attendu 0 (signale, pas avale)"; CYCLE_KO=1; }
[[ "$C6" == "143" ]] || { echoue "17. interruption sans piege EXIT rend $C6, attendu 143"; CYCLE_KO=1; }
[[ "$C7" == "1"   ]] || { echoue "17. refus sans piege EXIT rend $C7, attendu 1"; CYCLE_KO=1; }
(( CYCLE_KO )) || echo "      ok: 17. sept chemins de sortie, sept teardowns, un chacun"
rm -rf "$TEMOINS_DIR"

# --------------------------------------------------------------------------
# 19. L'INSTRUMENT LUI-MEME — dix facons de mentir, dix refus
# --------------------------------------------------------------------------
# CE QUE CE CONTROLE EXISTE POUR EMPECHER. Quatre fautes d'instrument ont
# produit dans ce jalon des conclusions FAUSSES sur le produit — pas des tests
# rouges a tort, des tests VERTS a tort, ce qui est pire. Elles sont toutes
# reproduites ici, en petit, et l'instrument doit les refuser.
INST_BASE="esc_instr_$(harnais_jeton)"
INST_KO=0
inst_verdict() {   # inst_verdict <numero> <libelle> <ok|diagnostic>
  if [[ "$3" == "ok" ]]; then
    echo "      ok: 19.$1 $2"
  else
    echoue "19.$1 $2 — obtenu: $3"; INST_KO=1
  fi
}
if ! psql -X -q -d postgres -v ON_ERROR_STOP=1 \
       -c "create database \"$INST_BASE\"" >/dev/null 2>&1; then
  echoue "19. la base de l'auto-test d'instrument n'a pas pu etre creee."
  INST_KO=1
else
  registre_base "$INST_BASE"
  inst() { psql -X -q -d "$INST_BASE" "$@"; }
  inst -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL19'
create table t19 (id int);
create function f19() returns trigger language plpgsql as $$ begin return new; end $$;
SQL19

  # 19.1 DDL SYNTAXIQUEMENT INVALIDE -> rouge. Forme EXACTE de la faute
  #      mesuree: « create trigger <nom> ON <table> BEFORE ... », refusee par
  #      PostgreSQL et jusqu'ici envoyee vers /dev/null.
  if esc_sql inst "19.1 DDL invalide" >/dev/null 2>&1 <<'SQL19'
create trigger tr19 on t19 before insert for each row execute function f19();
SQL19
  then inst_verdict 1 "une DDL invalide fait rougir" "esc_sql a rendu 0"
  else inst_verdict 1 "une DDL invalide fait rougir" ok; fi

  # 19.2 DECLENCHEUR ABSENT -> constate AVANT le scenario, par le CATALOGUE.
  if esc_catalogue_exige inst "19.2 declencheur" \
       "select count(*) from pg_trigger where tgname='tr19' and not tgisinternal" 1 \
       >/dev/null 2>&1
  then inst_verdict 2 "un declencheur absent est constate" "la postcondition a passe"
  else inst_verdict 2 "un declencheur absent est constate" ok; fi

  # 19.3 ERREUR SQL SUIVIE D'UN SELECT REUSSI -> le lot reste rouge. Sans
  #      ON_ERROR_STOP, psql poursuit et la derniere ligne dit « tout va bien ».
  if esc_sql inst "19.3 erreur puis succes" >/dev/null 2>&1 <<'SQL19'
select 1 / 0;
select 'tout va bien';
SQL19
  then inst_verdict 3 "une erreur suivie d'un succes reste rouge" "esc_sql a rendu 0"
  else inst_verdict 3 "une erreur suivie d'un succes reste rouge" ok; fi

  # 19.4 PIPELINE MASQUANT UN CODE NON NUL.
  INST_P=0; ( set -o pipefail; false | tail -1 ) >/dev/null 2>&1 || INST_P=$?
  if (( INST_P != 0 )); then inst_verdict 4 "un pipeline ne masque pas le code amont" ok
  else inst_verdict 4 "un pipeline ne masque pas le code amont" "pipefail inoperant"; fi

  # 19.5 HEREDOC A SUBSTITUTION -> aucune execution shell dans un flux SQL.
  #      Mesure: « -- voir `whoami` » fait parvenir « -- voir root » a psql.
  #      LE VERDICT VIENT DU CODE DE RETOUR, PAS DE LA PROSE. Ce site lisait
  #      « sortie vide = conforme ». Le scanner imprime desormais une ligne de
  #      succes — et cette ligne aurait rendu 19.5 ROUGE alors que le scanner
  #      etait VERT. C'est la faute que le canal machine a corrigee ailleurs:
  #      la prose est pour l'humain, le code de retour porte le verdict.
  INST_HD_RC=0
  INST_HD="$(python3 "$HERE/verifier_heredocs.py" "$HERE" 2>&1)" || INST_HD_RC=$?
  #      19.5 INSPECTE LE CORPUS; 19.9 FALSIFIE L'INSTRUMENT. Les deux emettent
  #      sur le canal parce que leur DIVERGENCE est la preuve recherchee: un
  #      scanner aveugle laisse 19.5 vert — le corpus est propre, il n'y a rien
  #      a y voir — pendant que 19.9 rougit. Sans les deux traces, on ne
  #      pourrait pas montrer que le controle du corpus ne remplace pas le
  #      controle de l'instrument.
  if (( INST_HD_RC == 0 )); then
    inst_verdict 5 "aucune composition SQL dangereuse dans les harnais" ok
    esc_evt "19.5" SUR runtime nature=corpus_propre \
      detail="le balayage du corpus reel ne trouve rien"
  else
    inst_verdict 5 "aucune composition SQL dangereuse dans les harnais" \
      "rc=$INST_HD_RC $(tr '\n' ' ' <<<"$INST_HD")"
    esc_evt "19.5" ROUGE runtime nature=corpus_fautif \
      detail="rc=$INST_HD_RC"
  fi

  # 19.6 SORTIE MULTIOCTET -> capturee sans dommage, identifiant preserve.
  if esc_sql inst "19.6 multioctet" >/dev/null 2>&1 <<'SQL19'
do $$ begin raise exception 'AUTHORITY_ESSAI_UNICODE: — tirets et accents crees'; end $$;
SQL19
  then inst_verdict 6 "une sortie multioctet ne passe pas pour un succes" "code 0"
  elif printf '%s' "$ESC_SQL_SORTIE" \
       | python3 -c 'import sys; sys.stdin.buffer.read().decode("utf-8")' 2>/dev/null; then
    inst_verdict 6 "une sortie multioctet est capturee sans dommage" ok
  else
    inst_verdict 6 "une sortie multioctet est capturee sans dommage" "octets invalides"
  fi

  # 19.7 OBJET CREE SOUS UN MAUVAIS SCHEMA -> refus par le catalogue.
  inst -q -c "create schema s19" >/dev/null 2>&1
  inst -q -c "create table s19.t19bis (id int)" >/dev/null 2>&1
  if esc_catalogue_exige inst "19.7 schema" \
       "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
         where c.relname='t19bis' and n.nspname='public'" 1 >/dev/null 2>&1
  then inst_verdict 7 "un objet cree sous un mauvais schema est refuse" "la postcondition a passe"
  else inst_verdict 7 "un objet cree sous un mauvais schema est refuse" ok; fi

  # 19.8 NON-VACUITE: un effet observable IMPOSSIBLE doit etre detecte.
  #      « return old » depuis un BEFORE UPDATE annule l'ecriture: « la ligne
  #      n'a pas change » devient vrai quoi que la garde decide.
  inst -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL19'
create table t19b (id int primary key, val int);
insert into t19b values (1, 1);
create function f19b() returns trigger language plpgsql as $$ begin return old; end $$;
create trigger tr19b before update on t19b for each row execute function f19b();
SQL19
  inst -q -c "update t19b set val = 42" >/dev/null 2>&1
  INST_VAL="$(inst -tAc "select val from t19b" 2>/dev/null)"
  if [[ "$INST_VAL" == "1" ]]; then
    inst_verdict 8 "un effet observable impossible est detecte (return old)" ok
  else
    inst_verdict 8 "un effet observable impossible est detecte (return old)" \
      "la valeur a change ($INST_VAL): le piege ne se reproduit pas"
  fi

  # 19.9 LE SCANNER DE COMPOSITION SQL VOIT-IL ENCORE ?
  #
  # 19.5 fait tourner le scanner sur le CORPUS REEL — et le corpus est propre.
  # Un scanner affaibli y rendrait donc ZERO, et 19.5 resterait VERT. C'est
  # exactement la faute qui a produit les onze survivants de `3d0acc2`:
  # prouver une garantie avec l'exemple qu'elle couvre deja. Seuls des cas
  # FABRIQUES distinguent un scanner qui voit d'un scanner devenu aveugle,
  # et c'est ce que `scanner_selftest.py` fabrique.
  #      UN `rc == 0` NE SUFFIT PAS, ET C'EST LE POINT.
  #      Un selftest ampute — decor fabrique non cree, boucle videe — rendrait
  #      ZERO et passerait pour vert. On exige donc le COMPTE de cas
  #      reellement parcourus, publie par le selftest lui-meme. Un decor qui
  #      n'a pas ete parcouru ne peut pas conclure.
  INST_SC_CAS_ATTENDUS=12
  INST_SC_RC=0
  INST_SC="$(python3 "$HERE/scanner_selftest.py" 2>&1)" || INST_SC_RC=$?
  INST_SC_N="$(sed -n 's/^SCANNER_SELFTEST_CAS=\([0-9]\{1,\}\)$/\1/p' <<<"$INST_SC" | tail -1)"
  INST_SC_N="${INST_SC_N:-0}"
  if (( INST_SC_RC == 0 )) && (( INST_SC_N >= INST_SC_CAS_ATTENDUS )); then
    inst_verdict 9 "le scanner de composition SQL voit ses cas fabriques" ok
    esc_evt "19.9" SUR runtime nature=scanner_selftest \
      detail="$INST_SC_N cas fabriques parcourus"
  else
    if (( INST_SC_RC == 0 )); then
      INST_SC_MOTIF="decor fabrique non parcouru: $INST_SC_N cas sur $INST_SC_CAS_ATTENDUS"
    else
      INST_SC_MOTIF="rc=$INST_SC_RC $(tr '\n' ' ' <<<"$INST_SC")"
    fi
    inst_verdict 9 "le scanner de composition SQL voit ses cas fabriques" \
      "$INST_SC_MOTIF"
    esc_evt "19.9" ROUGE runtime nature=scanner_aveugle \
      detail="$INST_SC_MOTIF"
  fi

  # 19.10 L'AUTO-TEST DU CANAL NE LAISSE RIEN DERRIERE LUI.
  #
  # Mesure du 29/08, `TMPDIR` neuf: 108 fichiers `.jsonl` par execution — 27
  # par le chemin normal, 81 par les trois sous-processus des preuves
  # negatives. Un harnais qui salit son `TMPDIR` finit par masquer les
  # residus qui comptent: bases, roles, verrous.
  #
  # Le controle eprouve le chemin normal ET l'erreur controlee — c'est ce
  # second cas qui compte, un nettoyage place a la fin du chemin heureux ne
  # s'executant pas quand un cas leve.
  INST_PR_RC=0
  INST_PR="$(python3 "$HERE/canal_proprete.py" 2>&1)" || INST_PR_RC=$?
  if (( INST_PR_RC == 0 )); then
    inst_verdict 10 "l'auto-test du canal ne laisse aucun fichier temporaire" ok
    esc_evt "19.10" SUR runtime nature=canal_propre \
      detail="chemin normal et erreur controlee: TMPDIR vide"
  else
    inst_verdict 10 "l'auto-test du canal ne laisse aucun fichier temporaire" \
      "rc=$INST_PR_RC $(tr '\n' ' ' <<<"$INST_PR")"
    esc_evt "19.10" ROUGE runtime nature=canal_salissant \
      detail="rc=$INST_PR_RC"
  fi

  psql -X -q -d postgres -c "drop database if exists \"$INST_BASE\"" >/dev/null 2>&1
fi
(( INST_KO )) || echo "      ok: 19. l'instrument refuse les dix facons de mentir"

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
