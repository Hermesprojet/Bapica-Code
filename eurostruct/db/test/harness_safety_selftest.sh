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
# la met donc en echec DELIBEREMENT, cinq fois, avec un TEMOIN a chaque coup:
# un role portant exactement le nom canonique, cree avant, verifie apres.
#
# CE QUI EST EXERCE
# ------------------
#   1. la commande canonique SANS consentement -> refus, temoins intacts
#   2. avec consentement mais hote NON local    -> refus, temoins intacts
#   3. avec consentement mais cluster GERE      -> refus, temoins intacts
#   4. avec consentement mais base ETRANGERE    -> refus, temoins intacts
#   5. roles canoniques PREEXISTANTS            -> refus, temoins intacts
#   6. aucun secret dans argv                   -> controle statique
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
    adm -v ON_ERROR_STOP=1 -c "create role \"$r\" nologin;" >/dev/null || return 1
  done
  return 0
}
retirer_temoins() {
  local r
  for r in "${CANONIQUES[@]}"; do
    adm -c "drop owned by \"$r\";"      >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
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

nettoyer() {
  retirer_temoins
  adm -c "drop role if exists supabase_admin;"          >/dev/null 2>&1
  adm -c "drop database if exists base_etrangere_temoin;" >/dev/null 2>&1
}
trap nettoyer EXIT
nettoyer

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
adm -v ON_ERROR_STOP=1 -c "create role supabase_admin nologin;" >/dev/null
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
adm -c "drop role if exists supabase_admin;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# 4. CONSENTEMENT, MAIS BASE ETRANGERE
# --------------------------------------------------------------------------
# Un cluster qui porte autre chose que ces tests est partage avec autre chose,
# et ses roles globaux ne nous appartiennent pas.
adm -v ON_ERROR_STOP=1 -c "create database base_etrangere_temoin;" >/dev/null
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
adm -c "drop database if exists base_etrangere_temoin;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# 5. TOUT EST EN ORDRE, MAIS LES ROLES CANONIQUES EXISTENT DEJA
# --------------------------------------------------------------------------
# Le controle le plus important: consentement declare, cluster local, jetable
# et sans marqueur — et pourtant les roles canoniques sont la. Le harnais ne
# peut PAS savoir s'ils sont a lui. Il doit refuser, jamais « repartir
# propre ». C'est exactement le geste qui detruit une production.
(export EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole; deux_phases) \
  && CODE=0 || CODE=$?
if [[ "$CODE" == "0" ]]; then
  echoue "two_phase_deployment.sh s'est execute alors que les roles"
  echoue "  canoniques preexistaient: il les a donc detruits ou reutilises"
elif temoins_intacts; then
  echo "      ok: 5. roles canoniques preexistants — refus (code $CODE), intacts"
else
  echoue "5. LE HARNAIS A DETRUIT DES ROLES CANONIQUES QU'IL N'AVAIT PAS CREES"
fi

retirer_temoins

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
