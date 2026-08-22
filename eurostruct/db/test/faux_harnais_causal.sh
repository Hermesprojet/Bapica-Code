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
# Initialise AVANT toute trap: `set -u` refuserait une variable non definie
# si le signal arrivait avant le lancement du fils d'arriere-plan.
DORT=""

# marq <evenement> [<prerequis>]
# CHAQUE PRODUCTEUR VERIFIE SON PREDECESSEUR: la chaine causale n'est pas
# seulement constatee apres coup par le parent, elle est EXIGEE a l'emission.
# LE PREDECESSEUR EST VALIDE SUR SON CONTENU, PAS SUR SON EXISTENCE.
# Un repertoire cree par `mkdir` sans `meta` — ou avec un `meta` tronque —
# signifie « evenement interrompu »: la chaine doit s'arreter la, et
# l'evenement suivant ne doit JAMAIS etre emis. Se contenter de tester le
# repertoire aurait valide une chaine dont un maillon n'a jamais abouti.
predecesseur_valide() {
  local pre="$1" m="$MARQ/$pre/meta"
  [[ -d "$MARQ/$pre" ]] || { echo "PREREQUIS_ABSENT=$pre" >>"$MARQ/.erreurs"; return 1; }
  [[ -f "$m" ]] || { echo "PREREQUIS_SANS_META=$pre" >>"$MARQ/.erreurs"; return 1; }
  local ev pid pgid sc
  ev="$(sed -n 's/^EVENT=//p' "$m")"; pid="$(sed -n 's/^PID=//p' "$m")"
  pgid="$(sed -n 's/^PGID=//p' "$m")"; sc="$(sed -n 's/^SCENARIO=//p' "$m")"
  [[ "$ev" == "$pre" ]] || { echo "PREREQUIS_EVENEMENT=$pre vs $ev" >>"$MARQ/.erreurs"; return 1; }
  [[ "$sc" == "$SCEN" ]] || { echo "PREREQUIS_SCENARIO=$pre $sc" >>"$MARQ/.erreurs"; return 1; }
  [[ "$pid" =~ ^[0-9]+$ && "$pgid" =~ ^[0-9]+$ ]] \
    || { echo "PREREQUIS_TRONQUE=$pre" >>"$MARQ/.erreurs"; return 1; }
  return 0
}

marq() {
  local ev="$1" pre="${2:-}"
  if [[ -n "$pre" ]] && ! predecesseur_valide "$pre"; then
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
  # Contre-exemple: rend le predecesseur INCOMPLET (repertoire sans `meta`).
  [[ -n "${ESC_META_TRONQUE:-}" ]] && rm -f "$MARQ/HARNESS_TRAP_ENTERED/meta"
  marq HARNESS_CLEANUP_STARTED HARNESS_TRAP_ENTERED
  # La duplication demandee: la SECONDE emission doit echouer.
  if [[ -n "${ESC_DOUBLE:-}" ]]; then
    marq HARNESS_CLEANUP_STARTED HARNESS_TRAP_ENTERED \
      && echo "DOUBLON_NON_DETECTE=HARNESS_CLEANUP_STARTED" >>"$MARQ/.erreurs"
  fi
  # LE FILS D'ARRIERE-PLAN EST TUE ET MOISSONNE AVANT DE SORTIR.
  [[ -n "$DORT" ]] && { kill "$DORT" 2>/dev/null; wait "$DORT" 2>/dev/null; }
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

# ==========================================================================
# LA PORTE DE VIVACITE — UN DOUBLE DE HARNAIS HONORE LE CONTRAT DU HARNAIS
# ==========================================================================
# CE FICHIER EST UN DOUBLE, PAS UN DECOR. Le wrapper ne publie plus son
# marqueur sur une simple photographie: il ATTEND la preuve que le harnais est
# tenu — un document `GATE_ARMED` — ou la mort de ce harnais. Un double qui
# reste vivant sans jamais armer ne remplit AUCUNE des deux conditions, et le
# wrapper l'attend indefiniment.
#
# Mesure: apres le passage a la barriere de vivacite, L1 n'expirait plus a
# cause d'un pipe retenu mais parce que le marqueur n'etait JAMAIS publie —
# « delai depasse en attendant: le marqueur du wrapper (L1) », 300 s. Le
# protocole faisait exactement ce qu'on lui demande; c'est le double qui avait
# cesse de ressembler a ce qu'il double.
#
# INERTE SANS `ESC_HARNAIS_PORTE`, comme le crochet du vrai harnais: ce fichier
# se comporte alors comme avant et reste utilisable seul.
if [[ -n "${ESC_HARNAIS_PORTE:-}" ]]; then
  porte_refus() { echo "PORTE=$1" >>"$MARQ/.erreurs"; exit 4; }
  [[ -p "$ESC_HARNAIS_PORTE" ]]     || porte_refus "pas une FIFO: $ESC_HARNAIS_PORTE"
  [[ -n "${ESC_HARNAIS_ETAT:-}" ]]  || porte_refus "chemin d etat absent"
  [[ -n "${ESC_HARNAIS_JETON:-}" ]] || porte_refus "jeton absent"

  # OUVRIR AVANT DE PUBLIER: l'etat publie doit decrire ce qui est VRAI a cet
  # instant. Publier d'abord affirmerait un blocage que rien n'etablit encore.
  exec {FD_PORTE}<"$ESC_HARNAIS_PORTE" || porte_refus "ouverture impossible"
  { echo "FORMAT=esc-harness-gate/1"
    echo "SCENARIO=${ESC_HARNAIS_SCENARIO:-}"
    echo "TOKEN=$ESC_HARNAIS_JETON"
    echo "PID=$$"
    echo "PGID=$PGID"
    echo "STATE=GATE_ARMED"
  } >"$ESC_HARNAIS_ETAT.tmp"
  # Publication exclusive par lien dur: une seconde publication est une erreur
  # observable, jamais un ecrasement muet.
  ln "$ESC_HARNAIS_ETAT.tmp" "$ESC_HARNAIS_ETAT" 2>/dev/null \
    || porte_refus "GATE_ARMED deja publie"
  rm -f "$ESC_HARNAIS_ETAT.tmp"

  # LA PORTE REMPLACE LE SOMMEIL, elle ne s'y ajoute pas. Un `sleep 600` a cote
  # laisserait une fin nominale ATTEIGNABLE, et « le harnais ne peut pas finir
  # avant le signal » redeviendrait une course gagnee au lieu d'une garantie.
  # `read -r -u` rend la main a la trap immediatement sur signal — meme mesure
  # que le `wait` qu'il remplace: 0 s.
  read -r -u "$FD_PORTE"
  echo "PORTE_RENDUE_SANS_SIGNAL=$?" >>"$MARQ/.erreurs"
  exit 4
fi

# `wait` sur un sommeil en arriere-plan: la trap peut alors s'executer tout de
# suite, contrairement a un `sleep` au premier plan qui devrait finir d'abord.
# SES SORTIES VONT A /dev/null, ET IL EST MOISSONNE. Mesure: sans cela, ce
# `sleep` heritait des pipes du `Popen`, survivait a la sortie de la trap en
# orphelin (PPID=1), et `communicate()` n'atteignait jamais EOF — la matrice
# restait vivante, le resultat n'etait jamais publie, et L1 expirait a 300 s.
# C'est le meme defaut que celui du temoin, chez un autre acteur.
sleep 600 >/dev/null 2>&1 </dev/null &
DORT=$!
wait "$DORT" 2>/dev/null
exit 0
