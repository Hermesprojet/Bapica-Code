#!/usr/bin/env bash
#
# EUROSTRUCT — FAUX HARNAIS A NETTOYAGE LENT ET TRACABLE
#
# Il n'existe que pour le scenario L de `mutation_signal_selftest.sh`. Un vrai
# harnais ne dit pas OU il en est de son nettoyage; celui-ci le dit, par des
# MARQUEURS EXCLUSIFS, afin qu'on puisse prouver un ORDRE plutot que de le
# deduire d'horloges murales.
#
# L'EXCLUSIVITE VIENT DE `mkdir`, ET C'EST LE POINT. Un marqueur publie par
# `mv -f` serait ecrase en silence a la seconde emission: « une seule entree
# logique dans le nettoyage » resterait alors invérifiable. `mkdir` echoue si
# la cible existe — la duplication devient donc une ERREUR observable.
#
#   ESC_MARQUEURS   repertoire des evenements (un sous-repertoire par evenement)
#   ESC_SCENARIO    identifiant unique du scenario, inscrit dans chaque marqueur
#   ESC_LENTEUR     duree du nettoyage simule, en secondes
#   ESC_DOUBLE      si pose, tente d'emettre DEUX FOIS le meme evenement
#   ESC_IGNORE_TERM si pose, ignore SIGTERM: le controleur doit escalader
#   ESC_CODE_SORTIE code metier a rendre apres nettoyage (defaut 0)
set -u

MARQ="${ESC_MARQUEURS:?ESC_MARQUEURS requis}"
SCEN="${ESC_SCENARIO:?ESC_SCENARIO requis}"
LENT="${ESC_LENTEUR:-3}"
CODE_SORTIE="${ESC_CODE_SORTIE:-0}"
PGID="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')"

# marq <evenement> [<prerequis>]
# CHAQUE PRODUCTEUR VERIFIE SON PREDECESSEUR: la chaine causale n'est pas
# seulement constatee apres coup par le parent, elle est EXIGEE a l'emission.
marq() {
  local ev="$1" pre="${2:-}"
  if [[ -n "$pre" && ! -f "$MARQ/$pre/meta" ]]; then
    echo "PREREQUIS_MANQUANT=$ev attendait $pre" >>"$MARQ/.erreurs"
    return 9
  fi
  if ! mkdir "$MARQ/$ev" 2>/dev/null; then
    echo "DOUBLON=$ev" >>"$MARQ/.erreurs"
    return 9
  fi
  { echo "EVENT=$ev"; echo "PID=$$"; echo "PGID=$PGID"; echo "SCENARIO=$SCEN"
  } >"$MARQ/$ev/.m"
  # Les metadonnees sont publiees par renommage: un repertoire SANS `meta`
  # signifie « evenement interrompu », et le parent doit le refuser.
  mv -f "$MARQ/$ev/.m" "$MARQ/$ev/meta"
}

# LE NETTOYAGE SE PROTEGE CONTRE UNE DOUBLE ENTREE. Les signaux POSIX peuvent
# etre repetes; sans ce garde-fou, deux trappes concurrentes emettraient deux
# fois les memes evenements et l'on ne saurait plus si le defaut vient du
# wrapper ou d'ici.
DEDANS=0
nettoyer() {
  local sig="$1"
  (( DEDANS )) && return
  DEDANS=1
  trap - TERM INT
  marq HARNESS_TRAP_ENTERED
  marq HARNESS_CLEANUP_STARTED HARNESS_TRAP_ENTERED
  # La duplication demandee: la SECONDE emission doit echouer.
  if [[ -n "${ESC_DOUBLE:-}" ]]; then
    marq HARNESS_CLEANUP_STARTED HARNESS_TRAP_ENTERED \
      && echo "DOUBLON_NON_DETECTE=HARNESS_CLEANUP_STARTED" >>"$MARQ/.erreurs"
  fi
  sleep "$LENT"                       # nettoyage lent, deliberement
  marq HARNESS_CLEANUP_DONE HARNESS_CLEANUP_STARTED
  marq HARNESS_EXITING HARNESS_CLEANUP_DONE
  exit "$CODE_SORTIE"
}

if [[ -n "${ESC_IGNORE_TERM:-}" ]]; then
  # Le harnais qui refuse de mourir: le controleur doit borner puis escalader.
  trap '' TERM
  trap 'nettoyer INT' INT
else
  trap 'nettoyer TERM' TERM
  trap 'nettoyer INT' INT
fi

echo "PRET $$ $PGID" >"$MARQ/.harnais"
# `wait` sur un sommeil en arriere-plan: la trap peut alors s'executer tout de
# suite, contrairement a un `sleep` au premier plan qui devrait finir d'abord.
sleep 600 &
DORT=$!
wait "$DORT" 2>/dev/null
exit 0
