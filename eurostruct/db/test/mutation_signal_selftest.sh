#!/usr/bin/env bash
#
# EUROSTRUCT — LA MATRICE DOIT MOURIR PROPREMENT
#
#   mutation_signal_selftest.sh
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `mutation_matrix.py` est l'INSTRUMENT qui fournit la preuve de cloture d'un
# jalon. Un defaut connu dans l'instrument rend sa preuve irrecevable — quelle
# que soit la qualite de ce qu'il mesure.
#
# LE DEFAUT, MESURE ET NON SUPPOSE. Le gestionnaire de signal appelait
# `nettoyer_espace()` en PREMIER: `ESPACE` passait a `None` et le worktree
# disparaissait, PUIS la levee declenchait le `finally: restaurer(fichier)`
# d'`essayer()`, qui ecrivait dans « None/tools/deploy_eurostruct.sh ».
# Resultat constate sur 6075b1b, deux fois — une fois subie a 00:17 UTC quand
# le conteneur s'est arrete, une fois provoquee deliberement:
#
#     SystemExit: 143
#     ...
#     FileNotFoundError: [Errno 2] No such file or directory:
#       'None/tools/deploy_eurostruct.sh'
#
# Trois consequences, et la deuxieme est la pire:
#   - un traceback la ou on attend un compte rendu;
#   - AUCUN verdict: 42 controles rendus n'etaient nulle part comptes, et les
#     21 suivants nulle part signales comme non commences;
#   - le code de sortie n'etait meme plus 143, l'exception non rattrapee le
#     ramenant a 1 — un arret par signal devenait indiscernable d'un echec.
#
# CE QUI EST EXIGE ICI
# ---------------------
#   1. code de sortie exactement 143;
#   2. un verdict partiel imprime, qui distingue termines / interrompu /
#      non commences;
#   3. le verdict nomme le controle actif, le fichier mute, le signal et le SHA;
#   4. aucun traceback, aucun « FileNotFoundError », aucun chemin « None/ »;
#   5. le fichier du DEPOT PRINCIPAL est inchange;
#   6. le worktree est retire;
#   7. aucun enfant du harnais ne survit.
#
# LE SIGNAL EST ENVOYE PENDANT `lancer()`, PAS PENDANT LA PAUSE. C'est la
# fenetre ou le `finally: restaurer()` s'execute, donc la seule qui exerce le
# defaut. Un test qui signalerait pendant la pause resterait vert contre le
# code fautif, et ne prouverait rien.
#
# SIGKILL N'EST PAS COUVERT, ET NE PEUT PAS L'ETRE: il n'est pas interceptable.
# Aucun verdict ne peut etre exige apres un SIGKILL. Ce que
# `mutation_isolation_selftest.sh` continue d'etablir dans ce cas, c'est que le
# DEPOT PRINCIPAL n'est pas modifie — la seule garantie qui survive a un arret
# non negociable.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(dirname "$(dirname "$HERE")")"          # « .../eurostruct »
# LA RACINE EST DEMANDEE A GIT, PAS COMPTEE EN `dirname`. Un `dirname` de trop
# ou de moins donne un chemin plausible qui ne designe rien — mesure: la
# premiere version cherchait la matrice dans « eurostruct/db/db/test ».
RACINE="$(git -C "$PROJET" rev-parse --show-toplevel)"
SOUS="$(realpath --relative-to="$RACINE" "$PROJET")"   # « eurostruct »
MATRICE="$PROJET/db/test/mutation_matrix.py"

KO=0
ok()     { echo "      ok: $*"; }
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
detail() { echo "                $*"; }

echo "    la matrice meurt proprement sur SIGTERM"

[[ -f "$MATRICE" ]] || { echoue "matrice introuvable: $MATRICE"; exit 2; }

# Le controle exerce: n'importe lequel convient, on attend l'enfant. « W1 »
# tourne sur `seal_contract.sh`, court et deja utilise par l'auto-test
# d'isolation.
FILTRE_CAS="W1"
TRACE="$(mktemp)"; SORTIE="$(mktemp)"
ESPACE_DEPOT=""; MPID=""; ENFANTS=""

menage() {
  # SIGTERM D'ABORD, SIGKILL SEULEMENT SI ELLE S'ACCROCHE. Un `kill -KILL`
  # immediat empeche la matrice de retirer son propre worktree, et ce test
  # s'arrete parfois AVANT d'avoir lu la trace — donc sans connaitre le chemin
  # a nettoyer lui-meme. Mesure: deux `esc-mutations-*` sont restes enregistres
  # apres deux arrets premature de ce test.
  if [[ -n "$MPID" ]] && kill -0 "$MPID" 2>/dev/null; then
    kill -TERM "$MPID" 2>/dev/null
    for _ in $(seq 1 100); do kill -0 "$MPID" 2>/dev/null || break; sleep 0.1; done
    kill -KILL "$MPID" 2>/dev/null
  fi
  [[ -n "$ESPACE_DEPOT" && -d "$ESPACE_DEPOT" ]] && {
    git -C "$RACINE" worktree remove --force "$ESPACE_DEPOT" 2>/dev/null
    rm -rf "$ESPACE_DEPOT"
    git -C "$RACINE" worktree prune 2>/dev/null
  }
  rm -f "$TRACE" "$SORTIE"
}
trap menage EXIT

# --------------------------------------------------------------------------
# 1. LA MATRICE, FILTREE SUR UN CONTROLE, AVEC SA TRACE
# --------------------------------------------------------------------------
(
  cd "$RACINE/$SOUS" || exit 2
  ESC_MUTATION_TRACE="$TRACE" \
  EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
    exec python3 "$MATRICE" "$FILTRE_CAS"
) >"$SORTIE" 2>&1 &
MPID=$!

attendre() {   # attendre() <description> <commande-test> <deciseconds>
  local quoi="$1" test="$2" max="$3" n=0
  while ! eval "$test"; do
    kill -0 "$MPID" 2>/dev/null || { echoue "la matrice est morte avant: $quoi"
                                     detail "$(head -3 "$SORTIE")"; return 1; }
    sleep 0.1; n=$((n + 1))
    if (( n >= max )); then echoue "delai depasse en attendant: $quoi"; return 1; fi
  done
  # LE `return 0` EXPLICITE N'EST PAS DECORATIF. Une boucle `while` rend le
  # statut de la DERNIERE commande de son corps: avec « (( n >= max )) && ... »
  # en derniere position, l'attente REUSSIE rendait 1 — parce que la borne
  # n'etait pas atteinte. Le test s'arretait donc sur une attente satisfaite,
  # sans message. Mesure: la trace etait ecrite, et l'appelant lisait un echec.
  return 0
}

# 2. LA MUTATION EST REELLEMENT POSEE — la trace le prouve, pas un `sleep`.
attendre "la mutation posee" '[[ -s "$TRACE" ]]' 3000 || exit 1
IFS=$'\t' read -r CAS_NOM CAS_FIC CAS_SOMME _ESPACE ESPACE_DEPOT <"$TRACE"
ok "mutation posee: $CAS_NOM sur $CAS_FIC"

# L'EMPREINTE DU FICHIER DANS LE DEPOT PRINCIPAL, PRISE MAINTENANT.
AVANT="$(sha256sum "$RACINE/$SOUS/$CAS_FIC" | cut -d' ' -f1)"
[[ "$AVANT" != "$CAS_SOMME" ]] \
  && ok "le depot principal differe deja de la version mutee (attendu)" \
  || echoue "le depot principal porte l'empreinte MUTEE: l'isolation a cede"

# 3. LE HARNAIS TOURNE — c'est la fenetre ou `finally: restaurer()` s'execute.
attendre "le harnais lance par la matrice" '[[ -n "$(pgrep -P "$MPID" 2>/dev/null)" ]]' 3000 || exit 1
ENFANTS="$(pgrep -P "$MPID" 2>/dev/null | tr '\n' ' ')"
ok "harnais en cours (PID ${ENFANTS% })"

# --------------------------------------------------------------------------
# 4. SIGTERM, PUIS LE VERDICT
# --------------------------------------------------------------------------
kill -TERM "$MPID"
CODE=0; wait "$MPID" 2>/dev/null || CODE=$?
MPID=""

# 143 EXACTEMENT. 1 signifierait qu'une exception a echappe et masque le signal.
if [[ "$CODE" -eq 143 ]]; then
  ok "code de sortie 143 (128 + SIGTERM)"
else
  echoue "code de sortie $CODE, attendu 143"
  detail "une exception echappee ramene le code a 1 et masque le signal"
fi

if grep -qE '^MUTATIONS: definis [0-9]+ \| termines [0-9]+ \| interrompu 1 \| non commences [0-9]+ \| perimes [0-9]+ \| creux [0-9]+ \| code 143$' "$SORTIE"; then
  ok "verdict partiel imprime, avec ses colonnes"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE")"
else
  echoue "aucun verdict partiel conforme"
  detail "$(grep -m1 '^MUTATIONS:' "$SORTIE" || echo '(aucune ligne MUTATIONS:)')"
fi

manque=()
grep -q "controle actif : $CAS_NOM"  "$SORTIE" || manque+=("controle actif")
grep -q "fichier mute   : $CAS_FIC"  "$SORTIE" || manque+=("fichier mute")
grep -q "signal recu    : SIGTERM"   "$SORTIE" || manque+=("signal recu")
grep -qE "SHA teste      : [0-9a-f]{40}" "$SORTIE" || manque+=("SHA teste")
if [[ ${#manque[@]} -eq 0 ]]; then
  ok "le verdict nomme le controle, le fichier, le signal et le SHA"
else
  echoue "le verdict ne nomme pas: ${manque[*]}"
fi

if grep -qE 'Traceback|FileNotFoundError|None/' "$SORTIE"; then
  echoue "un traceback ou un chemin « None/ » subsiste"
  detail "$(grep -m2 -E 'Traceback|FileNotFoundError|None/' "$SORTIE")"
else
  ok "aucun traceback, aucun « FileNotFoundError », aucun chemin « None/ »"
fi

# --------------------------------------------------------------------------
# 5. CE QUI RESTE DERRIERE
# --------------------------------------------------------------------------
APRES="$(sha256sum "$RACINE/$SOUS/$CAS_FIC" | cut -d' ' -f1)"
[[ "$APRES" == "$AVANT" ]] \
  && ok "le fichier du depot principal est inchange" \
  || echoue "le fichier du depot principal a change: $AVANT -> $APRES"

if [[ -n "$ESPACE_DEPOT" ]] && git -C "$RACINE" worktree list --porcelain \
     | grep -q "^worktree $ESPACE_DEPOT$"; then
  echoue "le worktree $ESPACE_DEPOT est encore enregistre"
elif [[ -d "$ESPACE_DEPOT" ]]; then
  echoue "le repertoire $ESPACE_DEPOT est encore sur disque"
else
  ok "le worktree est retire, une fois, et son repertoire avec"
  ESPACE_DEPOT=""
fi

survivants=""
for p in $ENFANTS; do kill -0 "$p" 2>/dev/null && survivants="$survivants $p"; done
[[ -z "$survivants" ]] \
  && ok "aucun enfant du harnais ne survit" \
  || echoue "enfants orphelins:$survivants"

echo
[[ $KO -eq 0 ]] \
  && echo "    La matrice rend un verdict meme interrompue." \
  || echo "    La matrice ne meurt pas proprement." >&2
exit $KO
