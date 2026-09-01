#!/usr/bin/env bash
# ==========================================================================
# UN ROLE OUBLIE DANS UNE LISTE DE DEMONTAGE ARRETE TOUT CE QUI VIENT APRES
# ==========================================================================
#
# CE QUE CE HARNAIS FERME, ET POURQUOI IL EXISTE
# ----------------------------------------------
# Les roles canoniques sont des objets de CLUSTER: ils survivent a la
# destruction de la base. Un harnais qui en cree un sans le rendre le laisse
# derriere lui, et l'etape suivante — qui exige a juste titre de partir d'un
# cluster vierge — REFUSE de demarrer. La suite entiere s'arrete alors sur un
# role, pas sur un defaut du produit.
#
# LA SCENE S'EST JOUEE DEUX FOIS, A L'IDENTIQUE:
#
#   26/08  `eurostruct_authority_backend` est ajoute a la phase 0.
#          `nonsuperuser_install.sh` le cree et ne le rend pas. Sept suites
#          refusent de demarrer. Correction a la main, et un commentaire est
#          ecrit dans ce fichier: « Un role oublie dans une liste de
#          demontage n'est pas un detail: il arrete tout ce qui vient apres. »
#
#   01/09  `eurostruct_reconciliation` est ajoute a la phase 0. Vingt-neuf
#          harnais sont mis a jour en cherchant le texte
#          `eurostruct_authority_backend)`. Quatre fichiers ecrivent la liste
#          autrement et passent au travers. Deux surfaces deviennent rouges,
#          VERTES en isole — le diagnostic coute deux campagnes completes.
#
# La lecon etait donc ECRITE, et elle n'a pas suffi. Un commentaire ne
# s'execute pas. Ce fichier la rend structurelle: la liste attendue se DERIVE
# du sceau, elle ne se maintient plus a la main. Ajoutez un role au plan de
# controle sans l'ajouter aux harnais, et cette surface rougit AVANT que la
# campagne ne parte — au lieu de rougir ailleurs, deux heures plus tard, sur
# un symptome qui ne nomme pas sa cause.
#
# L'INVARIANT, EN UNE PHRASE
# ---------------------------
# Tout harnais qui appelle `exiger_roles_absents` declare par la meme occasion
# qu'il part d'un jeu canonique vierge et qu'il le rendra. Il doit donc NOMMER
# chacun des roles que le plan de controle cree. Mesure du 01/09: trente-deux
# harnais sur trente-trois satisfaisaient deja cette regle. Elle ne durcit
# rien; elle constate ce que le depot fait deja, et empeche la trente-troisieme
# regression.
#
# CE QUE CE HARNAIS NE FAIT PAS
# ------------------------------
# Il ne touche NI base NI cluster: c'est une lecture de fichiers. Il est donc
# le seul du repertoire a pouvoir tourner sans PostgreSQL, et `run.sh` le place
# en tete pour cette raison — un jeu de listes incoherent est connu avant que
# la premiere base ne soit creee.
# ==========================================================================
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/../.." && pwd)"
SCEAU="$RACINE/db/control_plane/0001_normative_seal.sql"

echec=0
echoue() { echo "      ECHEC: $*" >&2; echec=1; }

echo "    demontage canonique: les listes se derivent du sceau"

# --------------------------------------------------------------------------
# 1. LA SOURCE DE VERITE EST LE SCEAU, PAS UNE LISTE RECOPIEE ICI
# --------------------------------------------------------------------------
# Une liste ecrite dans ce fichier serait une TROISIEME copie a maintenir, et
# elle se desynchroniserait exactement comme les deux autres. On lit donc les
# `create role` du plan de controle. Si le sceau change, ce harnais change avec
# lui, sans intervention.
[[ -f "$SCEAU" ]] || { echo "      ECHEC: sceau introuvable: $SCEAU" >&2; exit 1; }

mapfile -t ROLES < <(
  grep -oE '^[[:space:]]*create role [a-z_][a-z0-9_]*' "$SCEAU" \
    | awk '{print $3}' | sort -u)

if [[ ${#ROLES[@]} -eq 0 ]]; then
  echo "      ECHEC: aucun « create role » lu dans le sceau." >&2
  echo "             Le motif de lecture ne correspond plus au fichier:" >&2
  echo "             ce harnais deviendrait vert en ne verifiant RIEN." >&2
  exit 1
fi
echo "      ok: ${#ROLES[@]} roles canoniques lus dans le sceau: ${ROLES[*]}"

# --------------------------------------------------------------------------
# 2. LE GARDE-FOU DU GARDE-FOU
# --------------------------------------------------------------------------
# Un harnais qui ne trouve aucun sujet a examiner passe. C'est la panne la plus
# sournoise d'un controle statique: le motif casse, la surface reste verte, et
# la garantie a disparu sans bruit. On exige donc un plancher.
# DEUX FICHIERS SONT EXCLUS, ET POUR DES RAISONS DIFFERENTES:
#
#   `lib_harnais.sh`         DEFINIT `exiger_roles_absents`; il ne l'appelle
#                            pas, et ne cree aucun role.
#   `demontage_canonique.sh` C'EST CE FICHIER. Il contient le motif parce
#                            qu'il le CHERCHE. Sans cette exclusion il se
#                            designe lui-meme et rougit toujours — mesure
#                            faite: la premiere execution s'est accusee.
mapfile -t HARNAIS < <(
  grep -rl 'exiger_roles_absents ' "$ICI"/*.sh 2>/dev/null \
    | grep -vE '/(lib_harnais|demontage_canonique)\.sh$' | sort)

if [[ ${#HARNAIS[@]} -lt 20 ]]; then
  echo "      ECHEC: ${#HARNAIS[@]} harnais appelants trouves, moins que les" >&2
  echo "             vingt attendus. Le motif de recherche est casse: ce" >&2
  echo "             controle ne verifie plus ce qu'il annonce." >&2
  exit 1
fi
echo "      ok: ${#HARNAIS[@]} harnais appellent exiger_roles_absents"

# --------------------------------------------------------------------------
# 3. CHAQUE APPELANT NOMME CHAQUE ROLE
# --------------------------------------------------------------------------
# On verifie la PRESENCE DU NOM dans le fichier, pas la valeur passee a
# l'appel: les listes sont construites par concatenation de variables shell
# (`$ROLES_SB $CANONIQUES $SERVICES`), qu'aucune analyse statique ne resout
# honnetement. Le nom litteral, lui, est la — ou il ne l'est pas, et c'est
# exactement le defaut qu'on cherche.
#
# LES COMMENTAIRES SONT RETIRES AVANT LA RECHERCHE, ET C'EST LE POINT.
#
# Premiere redaction: `grep` sur le fichier entier. La falsification l'a prise
# en defaut sur-le-champ — on retire `eurostruct_reconciliation` de la ligne
# `SERVICES` de `nonsuperuser_install.sh`, et le controle reste VERT, parce que
# le COMMENTAIRE qui explique la correction nomme le role dix lignes plus haut.
# Un controle que sa propre prose satisfait ne controle rien: il aurait laisse
# passer exactement la regression qu'il existe pour attraper.
#
# On cherche donc dans le CODE seul. `sed 's/#.*$//'` est grossier — il coupe
# aussi un `#` a l'interieur d'une chaine — mais il ne peut se tromper que dans
# le sens SUR: un nom ainsi perdu produit un ROUGE a examiner, jamais un vert
# silencieux. Mesure du 01/09: les trente-deux appelants passent sans qu'aucun
# ne depende d'un `#` dans une chaine.
for f in "${HARNAIS[@]}"; do
  code="$(sed 's/#.*$//' "$f")"
  manquants=()
  for r in "${ROLES[@]}"; do
    grep -qF -- "$r" <<<"$code" || manquants+=("$r")
  done
  if [[ ${#manquants[@]} -gt 0 ]]; then
    echoue "$(basename "$f") ne nomme pas: ${manquants[*]}"
    echo "             Ce harnais declare partir d'un jeu canonique vierge," >&2
    echo "             mais ne rendra pas ce(s) role(s): ils survivront, et" >&2
    echo "             toutes les etapes suivantes refuseront de demarrer." >&2
  fi
done

if [[ $echec -eq 0 ]]; then
  echo "      ok: chaque appelant nomme les ${#ROLES[@]} roles du sceau"
  echo
  echo "================================================="
  echo " Demontage canonique: aucune liste ne s'est"
  echo " desynchronisee du plan de controle."
  echo "================================================="
  exit 0
fi

echo >&2
echo "=================================================" >&2
echo " Demontage canonique: ROUGE." >&2
echo "=================================================" >&2
exit 1
