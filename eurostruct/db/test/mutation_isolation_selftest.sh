#!/usr/bin/env bash
#
# EUROSTRUCT — L'ISOLATION DE LA MATRICE DE MUTATION, ETABLIE
#
#   db/test/mutation_isolation_selftest.sh
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `mutation_matrix.py` MUTE des fichiers pour verifier que chaque garantie porte
# quelque chose. Tant qu'elle mutait l'arbre de travail reel et restaurait par
# `git checkout --`, elle pouvait ecraser une modification creee apres son
# demarrage — c'est arrive, en silence — ou laisser un fichier MUTE dans le
# depot si elle etait interrompue.
#
# Elle travaille desormais dans un `git worktree` temporaire et detache. CE
# FICHIER LE PROUVE, au lieu de le supposer:
#
#   1. une modification TEMOIN survit a une execution de la matrice;
#   2. une interruption NON INTERCEPTABLE (SIGKILL) ne laisse rien de modifie;
#   3. la mutation est REELLEMENT appliquee, dans l'espace isole et nulle part
#      ailleurs;
#   4. se debarrasser du worktree ne touche aucun fichier suivi;
#   5. le nettoyage de CE fichier ne touche QUE ce qu'il a cree — le worktree
#      d'une matrice concurrente survit intact, mutation comprise.
#
# CE SCRIPT NE TOUCHE PAS LA VRAIE BRANCHE, ET C'EST LA CORRECTION D'UN DEFAUT.
# Il ecrivait son temoin dans `tools/deploy_eurostruct.sh` du depot principal,
# et le retirait par un `trap`. Un `SIGKILL` de CE script laissait donc le depot
# modifie — exactement le defaut qu'il denonce chez la matrice.
#
# Il cree desormais son PROPRE worktree jetable, le traite comme son « depot
# principal », et y depose son temoin. Meme tue brutalement, la branche reelle
# est intacte: il n'y a jamais rien ecrit.
#
# ET IL NE NETTOIE QUE SES PROPRES CHEMINS. Il retirait tout worktree dont le
# chemin contenait « esc-mutations- », ce qui emportait celui d'une matrice
# concurrente legitime — la meme famille de defaut qu'un nettoyage par prefixe.
#
# IL NE DEMANDE AUCUNE BASE: il tue la matrice avant qu'elle n'en ait besoin.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
DEPOT="$(git -C "$RACINE" rev-parse --show-toplevel)"
SOUS="$(basename "$RACINE")"
SCRATCH="${TMPDIR:-/tmp}"

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=$((KO + 1)); }
detail() { echo "                    $*"; }

echo "    isolation de la matrice de mutation"

# CHAQUE EXECUTION A SON IDENTIFIANT, et ne connait que ses propres chemins.
JETON="$(od -An -N6 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
[[ -n "$JETON" ]] || JETON="$$-$(date +%s)"
ESSAI=""          # le worktree qui sert de « depot principal » a ce test
MATRICE_PID=""
MATRICE_ESPACE=""  # la RACINE du worktree cree par la matrice de ce test
MATRICE_SOUS=""    # ...et son sous-repertoire de projet
CONC_PID=""
CONC_ESPACE=""     # la racine de celui de la matrice CONCURRENTE
CONC_SOUS=""
TRACE="$(mktemp)"
TRACE_CONC="$(mktemp)"
SORTIE="$(mktemp)"
SORTIE_CONC="$(mktemp)"

# `retirer_worktree <chemin>` — un chemin EXACT, jamais un motif.
retirer_worktree() {
  local w="$1"
  [[ -n "$w" && "$w" != "$DEPOT" ]] || return 0
  git -C "$DEPOT" worktree remove --force "$w" >/dev/null 2>&1
  rm -rf "$w"
}

nettoyer() {
  [[ -n "$MATRICE_PID" ]] && kill -KILL "$MATRICE_PID" 2>/dev/null
  [[ -n "$CONC_PID" ]]    && kill -KILL "$CONC_PID"    2>/dev/null
  retirer_worktree "$MATRICE_ESPACE"
  retirer_worktree "$CONC_ESPACE"
  retirer_worktree "$ESSAI"
  git -C "$DEPOT" worktree prune >/dev/null 2>&1
  rm -f "$TRACE" "$TRACE_CONC" "$SORTIE" "$SORTIE_CONC"
}
trap nettoyer EXIT INT TERM HUP

AVANT="$(git -C "$DEPOT" status --porcelain | sort -u)"
# LES WORKTREES PRESENTS AU DEPART. Ce test doit n'en AJOUTER aucun; il n'a pas
# a repondre de ceux qu'il a trouves — en compter le total ferait echouer ce
# fichier a cause d'une matrice tuee la veille, ce qui n'est pas son sujet.
WT_AVANT="$(git -C "$DEPOT" worktree list --porcelain | awk '/^worktree /{print $2}' | sort -u)"

# --------------------------------------------------------------------------
# LE « DEPOT PRINCIPAL » DE CE TEST — un worktree jetable
# --------------------------------------------------------------------------
ESSAI="$SCRATCH/esc-selftest-$JETON"
if ! git -C "$DEPOT" worktree add --detach --quiet "$ESSAI" HEAD 2>"$SORTIE"; then
  echoue "le worktree d'essai n'a pas pu etre cree"
  detail "$(head -2 "$SORTIE")"
  exit 1
fi
# LES MODIFICATIONS NON VALIDEES Y SONT RECOPIEES: sans elles, ce test
# exercerait la matrice de HEAD pendant qu'on corrige la matrice ouverte.
while IFS= read -r ligne; do
  [[ ${#ligne} -gt 3 ]] || continue
  chemin="${ligne:3}"
  [[ "$chemin" == *" -> "* ]] && chemin="${chemin##* -> }"
  [[ -f "$DEPOT/$chemin" ]] || continue
  mkdir -p "$(dirname "$ESSAI/$chemin")"
  cp -p "$DEPOT/$chemin" "$ESSAI/$chemin"
done < <(git -C "$DEPOT" status --porcelain)

TEMOIN_REL="$SOUS/tools/deploy_eurostruct.sh"
TEMOIN="$ESSAI/$TEMOIN_REL"
MARQUE="# TEMOIN mutation_isolation_selftest $JETON"
printf '%s\n' "$MARQUE" >>"$TEMOIN"
TEMOIN_SOMME="$(sha256sum <"$TEMOIN" | cut -d' ' -f1)"
ETAT_ESSAI_AVANT="$(git -C "$ESSAI" status --porcelain | sort -u)"

# --------------------------------------------------------------------------
# UNE MATRICE CONCURRENTE, QUI DOIT SURVIVRE AU NETTOYAGE DE CELLE-CI
# --------------------------------------------------------------------------
# Elle est lancee depuis le DEPOT REEL, comme le ferait quelqu'un d'autre au
# meme moment. Ce test ne doit pas la connaitre autrement que par sa trace.
ESC_MUTATION_TRACE="$TRACE_CONC" ESC_MUTATION_PAUSE=90 \
  python3 "$RACINE/db/test/mutation_matrix.py" W1 >"$SORTIE_CONC" 2>&1 &
CONC_PID=$!

# --------------------------------------------------------------------------
# LA MATRICE DE CE TEST, LANCEE DEPUIS LE WORKTREE D'ESSAI, PUIS TUEE
# --------------------------------------------------------------------------
ESC_MUTATION_TRACE="$TRACE" ESC_MUTATION_PAUSE=90 \
  python3 "$ESSAI/$SOUS/db/test/mutation_matrix.py" W1 >"$SORTIE" 2>&1 &
MATRICE_PID=$!

attendre_trace() {
  local f="$1" pid="$2" n=0
  while [[ ! -s "$f" ]] && ((n < 900)); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1; n=$((n + 1))
  done
  [[ -s "$f" ]]
}

if ! attendre_trace "$TRACE" "$MATRICE_PID" || ! attendre_trace "$TRACE_CONC" "$CONC_PID"; then
  echoue "une matrice n'a pose aucune mutation en 90 s; rien n'est evalue."
  detail "$(head -2 "$SORTIE")"
  detail "$(head -2 "$SORTIE_CONC")"
  exit 1
fi
IFS=$'\t' read -r _N MUTE_REL MUTE_SOMME MATRICE_SOUS MATRICE_ESPACE <"$TRACE"
IFS=$'\t' read -r _N2 CONC_REL CONC_SOMME CONC_SOUS CONC_ESPACE <"$TRACE_CONC"

# --- 3. LA MUTATION VIT DANS L'ESPACE ISOLE -------------------------------
if [[ ! -d "$MATRICE_ESPACE" ]]; then
  echoue "3. l'espace isole annonce ($MATRICE_ESPACE) n'existe pas"
elif [[ "$MATRICE_SOUS" == "$ESSAI/$SOUS" || "$MATRICE_SOUS" == "$RACINE" ]]; then
  echoue "3. l'espace isole EST l'arbre de depart: rien n'est isole"
else
  SOMME_ESSAI="$(sha256sum <"$ESSAI/$SOUS/$MUTE_REL" | cut -d' ' -f1)"
  if [[ "$MUTE_SOMME" == "$SOMME_ESSAI" ]]; then
    echoue "3. le fichier mute est identique dans l'espace et dans l'arbre de depart"
  else
    echo "      ok: 3. la mutation vit dans l'espace isole, pas dans l'arbre"
    detail "  $MUTE_REL: ${MUTE_SOMME:0:12} (isole) / ${SOMME_ESSAI:0:12} (depart)"
  fi
fi

# --- 2. UNE INTERRUPTION NON INTERCEPTABLE --------------------------------
kill -KILL "$MATRICE_PID" 2>/dev/null
wait "$MATRICE_PID" 2>/dev/null
MATRICE_PID=""
APRES_ESSAI="$(git -C "$ESSAI" status --porcelain | sort -u)"
if [[ "$APRES_ESSAI" != "$ETAT_ESSAI_AVANT" ]]; then
  echoue "2. apres SIGKILL, l'arbre de depart porte des modifications nouvelles:"
  while IFS= read -r l; do detail "  $l"; done \
    < <(comm -13 <(printf '%s\n' "$ETAT_ESSAI_AVANT") <(printf '%s\n' "$APRES_ESSAI"))
else
  echo "      ok: 2. apres SIGKILL, aucun fichier de l'arbre n'est modifie"
fi

# --- 1. LE TEMOIN A SURVECU -----------------------------------------------
if [[ "$(sha256sum <"$TEMOIN" 2>/dev/null | cut -d' ' -f1)" != "$TEMOIN_SOMME" ]]; then
  echoue "1. le fichier temoin a ete reecrit par la matrice"
elif [[ "$(tail -1 "$TEMOIN")" != "$MARQUE" ]]; then
  echoue "1. la modification temoin a disparu"
else
  echo "      ok: 1. la modification temoin est intacte"
fi

# --- 5. LE NETTOYAGE NE TOUCHE QUE SES PROPRES CHEMINS --------------------
# On nettoie CE QU'ON A CREE, puis on constate que la matrice concurrente est
# intacte: son worktree existe encore, et sa mutation y est toujours lisible.
retirer_worktree "$MATRICE_ESPACE"; MATRICE_ESPACE=""
if [[ ! -d "$CONC_ESPACE" ]]; then
  echoue "5. le nettoyage a emporte le worktree d'une matrice concurrente"
  detail "  $CONC_ESPACE"
elif [[ "$(sha256sum <"$CONC_SOUS/$CONC_REL" 2>/dev/null | cut -d' ' -f1)" != "$CONC_SOMME" ]]; then
  echoue "5. le worktree concurrent survit, mais sa mutation a ete alteree"
else
  echo "      ok: 5. le worktree d'une matrice concurrente est intact"
fi

# --- 4. SE DEBARRASSER DES WORKTREES NE TOUCHE AUCUN FICHIER SUIVI --------
kill -KILL "$CONC_PID" 2>/dev/null; wait "$CONC_PID" 2>/dev/null; CONC_PID=""
retirer_worktree "$CONC_ESPACE"; CONC_ESPACE=""
retirer_worktree "$ESSAI";       ESSAI=""
git -C "$DEPOT" worktree prune >/dev/null 2>&1
APRES="$(git -C "$DEPOT" status --porcelain | sort -u)"
WT_APRES="$(git -C "$DEPOT" worktree list --porcelain | awk '/^worktree /{print $2}' | sort -u)"
RESTANTS="$(comm -13 <(printf '%s\n' "$WT_AVANT") <(printf '%s\n' "$WT_APRES") | wc -l)"
if [[ "$APRES" != "$AVANT" ]]; then
  echoue "4. le depot principal a change au cours de ce test:"
  while IFS= read -r l; do detail "  $l"; done \
    < <(comm -13 <(printf '%s\n' "$AVANT") <(printf '%s\n' "$APRES"))
elif [[ "$RESTANTS" != "0" ]]; then
  echoue "4. $RESTANTS worktree(s) AJOUTE(S) et non retire(s):"
  while IFS= read -r l; do detail "  $l"; done \
    < <(comm -13 <(printf '%s\n' "$WT_AVANT") <(printf '%s\n' "$WT_APRES"))
else
  echo "      ok: 4. aucun residu, et le depot principal n'a pas bouge"
fi

echo ""
if [[ $KO -eq 0 ]]; then
  echo "    Isolation de la matrice etablie: le depot principal n'est jamais ecrit."
  exit 0
fi
echo "    Isolation de la matrice: $KO ecart(s)."
exit 1
