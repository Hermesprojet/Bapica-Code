#!/usr/bin/env bash
#
# EUROSTRUCT — L'ISOLATION DE LA MATRICE DE MUTATION, ETABLIE
#
#   db/test/mutation_isolation_selftest.sh
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `mutation_matrix.py` MUTE des fichiers du depot pour verifier que chaque
# garantie porte quelque chose. Tant qu'elle mutait l'arbre de travail reel et
# restaurait par `git checkout --`, elle pouvait:
#
#   * ECRASER une modification creee apres son demarrage — c'est arrive, en
#     silence, et le harnais suivant a teste le fichier de HEAD en annoncant le
#     contraire;
#   * laisser un fichier MUTE dans le depot si elle etait interrompue entre la
#     mutation et la restauration.
#
# Elle travaille desormais dans un `git worktree` temporaire et detache. CE
# FICHIER LE PROUVE, au lieu de le supposer:
#
#   1. une modification TEMOIN du depot principal survit a une execution;
#   2. une interruption NON INTERCEPTABLE (SIGKILL) ne laisse aucun fichier du
#      depot principal modifie;
#   3. la mutation est REELLEMENT appliquee, dans l'espace isole et nulle part
#      ailleurs.
#
# IL NE DEMANDE AUCUNE BASE. Les harnais que la matrice lance en ont besoin, pas
# l'isolation elle-meme: ce fichier tue la matrice avant qu'elle n'aboutisse.
# C'est ce qui lui permet d'etre dans la suite canonique — une garantie qui ne
# s'execute que sur le poste de celui qui y pense n'est pas une garantie.
#
# LE TEMOIN EST UN COMMENTAIRE, en fin de fichier, et il est retire par un
# `trap`. Si ce script meurt malgre tout, le temoin reste visible dans
# `git status` — genant, jamais destructeur.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
DEPOT="$(git -C "$RACINE" rev-parse --show-toplevel)"

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=$((KO + 1)); }
detail() { echo "                    $*"; }

echo "    isolation de la matrice de mutation"

# LE PORTEUR DU TEMOIN EST UNE CIBLE DE MUTATION, et c'est le point. Un temoin
# depose dans un fichier que la matrice ne touche jamais ne prouverait rien.
# `tools/deploy_eurostruct.sh` est precisement celui dont des corrections non
# validees ont ete effacees.
TEMOIN_REL="eurostruct/tools/deploy_eurostruct.sh"
TEMOIN="$DEPOT/$TEMOIN_REL"
MARQUE="# TEMOIN mutation_isolation_selftest $$ — retire par son trap"
TRACE="$(mktemp)"
SORTIE="$(mktemp)"
MATRICE_PID=""
POSE=0

nettoyer() {
  [[ -n "$MATRICE_PID" ]] && kill -KILL "$MATRICE_PID" 2>/dev/null
  # LE TEMOIN D'ABORD: c'est la seule ecriture de ce script dans le depot.
  if ((POSE)) && [[ -f "$TEMOIN" ]]; then
    # Retire la DERNIERE ligne si — et seulement si — c'est bien la marque.
    if [[ "$(tail -1 "$TEMOIN")" == "$MARQUE" ]]; then
      sed -i '$ d' "$TEMOIN"
    fi
  fi
  # Les worktrees laisses par une matrice tuee: leur repertoire et leur
  # entree de metadonnees. `prune` ne touche aucun fichier suivi.
  git -C "$DEPOT" worktree list --porcelain 2>/dev/null \
    | awk '/^worktree /{print $2}' \
    | while read -r w; do
        [[ "$w" == "$DEPOT" ]] && continue
        [[ "$w" == *esc-mutations-* ]] || continue
        git -C "$DEPOT" worktree remove --force "$w" >/dev/null 2>&1
        rm -rf "$w"
      done
  git -C "$DEPOT" worktree prune >/dev/null 2>&1
  rm -f "$TRACE" "$SORTIE"
}
trap nettoyer EXIT INT TERM HUP

# --------------------------------------------------------------------------
# L'ETAT DE DEPART — sans lui, aucune des trois proprietes n'est mesurable
# --------------------------------------------------------------------------
AVANT="$(git -C "$DEPOT" status --porcelain)"
if grep -qF "$MARQUE" "$TEMOIN" 2>/dev/null; then
  echoue "un temoin d'une execution precedente est deja present; abandon"
  exit 1
fi

printf '%s\n' "$MARQUE" >>"$TEMOIN"
POSE=1
TEMOIN_SOMME="$(sha256sum <"$TEMOIN" | cut -d' ' -f1)"

# --------------------------------------------------------------------------
# LA MATRICE, LANCEE PUIS TUEE
# --------------------------------------------------------------------------
# `W1` mute le fichier du sceau — une cible DIFFERENTE du porteur du temoin, de
# sorte que les deux proprietes ne se confondent pas. La pause retient la
# matrice une fois la mutation ecrite: sans elle, il faudrait courir apres une
# fenetre de quelques millisecondes.
#
# LE CONSENTEMENT DE CLUSTER JETABLE N'EST PAS POSE ICI, ET C'EST VOULU: la
# matrice est tuee avant d'avoir besoin d'une base. Ce script ne doit pouvoir
# detruire aucun role, sur aucun cluster.
ESC_MUTATION_TRACE="$TRACE" ESC_MUTATION_PAUSE=30 \
  python3 "$HERE/mutation_matrix.py" W1 >"$SORTIE" 2>&1 &
MATRICE_PID=$!

# Attendre la trace, sans jamais boucler indefiniment.
ATTENTE=0
while [[ ! -s "$TRACE" ]] && ((ATTENTE < 600)); do
  kill -0 "$MATRICE_PID" 2>/dev/null || break
  sleep 0.1; ATTENTE=$((ATTENTE + 1))
done

if [[ ! -s "$TRACE" ]]; then
  echoue "la matrice n'a pose aucune mutation en 60 s; les trois proprietes"
  echoue "      ne sont pas evaluees."
  detail "$(head -3 "$SORTIE")"
  exit 1
fi

IFS=$'\t' read -r _NOM MUTE_REL MUTE_SOMME ESPACE <"$TRACE"

# --- 3. LA MUTATION EST APPLIQUEE, DANS L'ESPACE ISOLE --------------------
if [[ ! -d "$ESPACE" ]]; then
  echoue "3. l'espace isole annonce ($ESPACE) n'existe pas"
elif [[ "$ESPACE" == "$RACINE" ]]; then
  echoue "3. l'espace isole EST le depot principal: rien n'est isole"
else
  SOMME_DEPOT="$(sha256sum <"$RACINE/$MUTE_REL" | cut -d' ' -f1)"
  if [[ "$MUTE_SOMME" == "$SOMME_DEPOT" ]]; then
    echoue "3. le fichier mute est identique dans l'espace et dans le depot:"
    echoue "   la mutation n'a pas ete appliquee, ou elle l'a ete au depot."
  else
    echo "      ok: 3. la mutation vit dans l'espace isole, pas dans le depot"
    detail "  $MUTE_REL: ${MUTE_SOMME:0:12} (isole) / ${SOMME_DEPOT:0:12} (depot)"
  fi
fi

# --- 2. UNE INTERRUPTION NON INTERCEPTABLE --------------------------------
# SIGKILL: aucun `trap`, aucun `atexit`, aucune restauration. C'est le pire cas,
# et c'est celui qui laissait un fichier mute dans le depot.
kill -KILL "$MATRICE_PID" 2>/dev/null
wait "$MATRICE_PID" 2>/dev/null
MATRICE_PID=""

APRES="$(git -C "$DEPOT" status --porcelain)"
ATTENDU="$(printf '%s\n' "$AVANT" | grep -v '^[[:space:]]*$'; echo " M $TEMOIN_REL")"
INATTENDU="$(comm -13 <(printf '%s\n' "$ATTENDU" | sort -u) \
                      <(printf '%s\n' "$APRES" | grep -v '^[[:space:]]*$' | sort -u))"
if [[ -n "$INATTENDU" ]]; then
  echoue "2. apres SIGKILL, le depot principal porte des modifications"
  echoue "   qu'il n'avait pas:"
  while IFS= read -r l; do detail "  $l"; done <<<"$INATTENDU"
else
  echo "      ok: 2. apres SIGKILL, aucun fichier du depot n'est modifie"
fi

# --- 1. LE TEMOIN A SURVECU -----------------------------------------------
if [[ ! -f "$TEMOIN" ]]; then
  echoue "1. le porteur du temoin a disparu"
elif [[ "$(sha256sum <"$TEMOIN" | cut -d' ' -f1)" != "$TEMOIN_SOMME" ]]; then
  echoue "1. le fichier temoin a ete reecrit par la matrice"
  detail "  attendu ${TEMOIN_SOMME:0:12}, obtenu $(sha256sum <"$TEMOIN" | cut -d' ' -f1 | cut -c1-12)"
elif [[ "$(tail -1 "$TEMOIN")" != "$MARQUE" ]]; then
  echoue "1. la modification temoin a disparu du depot principal"
else
  echo "      ok: 1. la modification temoin du depot est intacte"
fi

# --- LE NETTOYAGE NE TOUCHE PAS LE DEPOT ----------------------------------
# Apres un SIGKILL, le worktree survit: c'est attendu. Ce qui doit etre vrai,
# c'est que s'en debarrasser ne touche aucun fichier suivi.
AVANT_PRUNE="$(git -C "$DEPOT" status --porcelain | sort -u)"
git -C "$DEPOT" worktree prune >/dev/null 2>&1
if [[ "$(git -C "$DEPOT" status --porcelain | sort -u)" != "$AVANT_PRUNE" ]]; then
  echoue "4. `git worktree prune` a modifie l'etat du depot principal"
else
  echo "      ok: 4. se debarrasser du worktree ne touche aucun fichier suivi"
fi

echo ""
if [[ $KO -eq 0 ]]; then
  echo "    Isolation de la matrice etablie: le depot principal n'est jamais ecrit."
  exit 0
fi
echo "    Isolation de la matrice: $KO ecart(s)."
exit 1
