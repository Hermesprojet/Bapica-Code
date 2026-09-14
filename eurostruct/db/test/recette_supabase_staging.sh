#!/usr/bin/env bash
#
# EUROSTRUCT — PREFLIGHT DE LA RECETTE SUR UN STAGING SUPABASE
#
#   db/test/recette_supabase_staging.sh
#
# CE QUE CE SCRIPT FAIT, ET POURQUOI IL NE FAIT QUE CELA
# -------------------------------------------------------
# La recette sur Supabase reel comporte sept etapes. Aucune n'a jamais tourne:
# `SUPABASE_UNVERIFIED` est vrai, et le restera tant qu'une instance reelle
# n'aura pas ete traversee de bout en bout.
#
# Ce script ne la simule pas. Il repond a la seule question utile tant que
# l'acces manque: **laquelle des sept etapes serait executable maintenant, et
# quel acces precis bloque les autres**. Un compte rendu qui dit « il manque
# les acces Supabase » ne permet a personne d'agir; celui-ci nomme la variable,
# ce qu'elle designe, qui peut la fournir, et l'etape qu'elle debloque.
#
# Quand les acces sont la, il enchaine les sept etapes.
#
# IL NE LIT AUCUN SECRET, ET N'EN AFFICHE AUCUN
# -----------------------------------------------
# Il regarde si une variable est DEFINIE. Jamais ce qu'elle contient. Aucune
# valeur, aucun fragment, aucune URL de connexion ne passe par sa sortie ni par
# `argv` — voir `est_defini`, qui teste l'existence et rien d'autre.
#
# IL N'ECRIT RIEN TANT QUE LE CONSENTEMENT N'EST PAS DONNE
# ---------------------------------------------------------
# Les etapes 1 a 7 sont INTRUSIVES sur l'instance visee: elles creent des
# roles, posent des migrations, inscrivent des decisions. Sans
# EUROSTRUCT_RECETTE_CIBLE=staging, le script s'arrete au diagnostic et ne
# joint rien.
#
# CODES DE SORTIE
# ----------------
#   0  les sept etapes sont executables (ou ont ete executees, selon le mode)
#   2  REFUSEE — consentement absent alors que les acces sont la
#   4  NON EXECUTEE — au moins un acces manque; ils sont listes
set -uo pipefail

MODE="${1:-diagnostic}"

# ---------------------------------------------------------------------------
# Le seul primitif qui touche a l'environnement: « definie ou non ».
# ---------------------------------------------------------------------------
est_defini() { [[ -n "${!1:-}" ]]; }

MANQUANTS=()
LIGNES=()

# `exige <variable> <ce que c'est> <qui peut le fournir>`
exige() {
  local var="$1" quoi="$2" qui="$3"
  if est_defini "$var"; then
    LIGNES+=("      [ok]      $var — defini")
    return 0
  fi
  LIGNES+=("      [MANQUE]  $var — $quoi (a fournir par: $qui)")
  MANQUANTS+=("$var")
  return 1
}

titre() { LIGNES+=("" "  $*"); }

echo "EUROSTRUCT — preflight de la recette sur staging Supabase"
echo "  mode: $MODE"
echo

# ===========================================================================
# ETAPE 0 — LE PLAN DE CONTROLE. Tout le reste en depend.
# ===========================================================================
titre "0. Plan de controle — db/test/supabase_probe.sh"
LIGNES+=("      Mesure les QUATRE capacites dont depend le deploiement en deux"
         "      phases: CREATEROLE, precreation d'un role d'autorite, octroi en"
         "      restant le DONNEUR, et revocation integrale. Sur PostgreSQL 16"
         "      elles passent; personne ne les a constatees sur Supabase.")
exige EUROSTRUCT_PROBE_DATABASE_URL \
  "DSN du role de plan de controle sur le staging" \
  "l'exploitant de l'instance, par la configuration de secrets"
exige EUROSTRUCT_PROBE_TARGET \
  "consentement explicite « staging » exige par la sonde" \
  "l'operateur qui lance la recette"

# ===========================================================================
# ETAPE 1 — MIGRATIONS ET ROLES
# ===========================================================================
titre "1. Migrations et roles"
LIGNES+=("      CE QUI BLOQUE N'EST PAS UN SECRET, C'EST UN DROIT. Les harnais"
         "      du depot (parcours_authentifie.sh, decision_vers_strict.sh,"
         "      parcours_livrable.sh, sauvegarde_restauration.sh) creent leur"
         "      propre role migrateur avec « createrole createdb ». Un projet"
         "      Supabase ne donne pas ces droits au role applicatif: repointer"
         "      ces scripts vers le staging ne suffira pas, et c'est l'etape 0"
         "      qui dira si le plan de controle peut les obtenir.")
exige EUROSTRUCT_STAGING_MIGRATION_DSN \
  "DSN du role qui pose les migrations sur le staging" \
  "l'exploitant, apres que l'etape 0 a etabli qu'il peut exister"

# ===========================================================================
# ETAPE 2 — AUTHENTIFICATION
# ===========================================================================
titre "2. Authentification — jetons GoTrue verifies par JWKS"
LIGNES+=("      L'API verifie la SIGNATURE, l'emetteur, l'audience et"
         "      l'expiration. Le decor local (web/e2e/supabase_local.mjs)"
         "      prouve le comportement de notre code face a un emetteur"
         "      conforme; il ne prouve rien sur celui de Supabase.")
exige EUROSTRUCT_SUPABASE_JWKS_URL \
  "URL du jeu de cles publiques du projet" \
  "publique — visible dans les reglages du projet Supabase"
exige EUROSTRUCT_SUPABASE_ISSUER \
  "emetteur attendu dans le jeton" \
  "publique — reglages du projet"
exige EUROSTRUCT_SUPABASE_AUDIENCE \
  "audience attendue dans le jeton" \
  "publique — vaut « authenticated » sur un projet standard"

# ===========================================================================
# ETAPE 3 — LES DEUX INGENIEURS
# ===========================================================================
titre "3. Confirmations a quatre yeux — DEUX comptes distincts"
LIGNES+=("      PostgreSQL refuse par contrainte de table que l'approbateur"
         "      soit le proposant (decision_two_distinct_principals). Deux"
         "      comptes sont donc necessaires, et il faut pouvoir ouvrir une"
         "      session avec CHACUN."
         ""
         "      CE N'EST PAS UN ACCES QUE CE DEPOT PEUT FABRIQUER. Creer ici"
         "      deux identites de complaisance rendrait la recette verte et ne"
         "      prouverait rien: le dispositif existe pour qu'une valeur"
         "      nationale porte le nom de deux personnes.")
exige EUROSTRUCT_STAGING_COMPTE_A \
  "identifiant de session du premier ingenieur (proposant)" \
  "l'ingenieur lui-meme, sur le staging"
exige EUROSTRUCT_STAGING_COMPTE_B \
  "identifiant de session du SECOND ingenieur (approbateur)" \
  "le second ingenieur lui-meme — personne d'autre"

# ===========================================================================
# ETAPE 4 — L'ETUDE STRICTE BELGE
# ===========================================================================
titre "4. Etude stricte belge — les dix-neuf parametres"
LIGNES+=("      N'exige aucun acces de plus: elle depend du resultat des"
         "      etapes 1 a 3. Tant que les dix-neuf ne sont pas consommes sur"
         "      l'instance, le mode strict refuse — et c'est le comportement"
         "      attendu, pas une panne.")

# ===========================================================================
# ETAPE 5 — LE MAGASIN
# ===========================================================================
titre "5. Livrables PDF et DXF — le magasin d'objets"
exige EUROSTRUCT_STORAGE_BACKEND \
  "« s3 » pour viser un magasin objet, « fs » pour un repertoire" \
  "l'exploitant"
exige EUROSTRUCT_S3_ENDPOINT \
  "point d'entree du magasin (Supabase Storage expose une API S3)" \
  "publique — reglages Storage du projet"
exige EUROSTRUCT_S3_BUCKET \
  "seau ou sont ecrits les livrables" \
  "l'exploitant"
exige EUROSTRUCT_S3_ACCESS_KEY_ID \
  "identifiant d'acces au magasin" \
  "l'exploitant, par la configuration de secrets"
exige EUROSTRUCT_S3_SECRET_ACCESS_KEY \
  "secret d'acces au magasin" \
  "l'exploitant, par la configuration de secrets"

# ===========================================================================
# ETAPE 6 — SAUVEGARDE
# ===========================================================================
titre "6. Sauvegarde et restauration"
LIGNES+=("      UNE DECISION RESTE A PRENDRE, ET ELLE N'EST PAS TECHNIQUE."
         "      sauvegarde_restauration.sh restaure DANS LE MEME CLUSTER. Sur"
         "      un staging Supabase, cela veut dire ecrire une base restauree"
         "      a cote de la base de travail. Qui l'autorise, et ou elle"
         "      atterrit, se decide avant de lancer quoi que ce soit.")
exige EUROSTRUCT_STAGING_RESTORE_DSN \
  "DSN de la cible de restauration, distincte de la base de travail" \
  "l'exploitant, apres arbitrage sur l'emplacement"

# ===========================================================================
# ETAPE 7 — RELECTURE APRES REDEMARRAGE
# ===========================================================================
titre "7. Relecture apres redemarrage"
LIGNES+=("      N'exige aucun acces de plus. Ce qui doit survivre: le calcul,"
         "      son identifiant, ses quatre empreintes, l'instantane normatif,"
         "      les lignes de livrable et les octets du magasin. Ce qui ne doit"
         "      PAS survivre: la session.")

# ===========================================================================
# LE COMPTE RENDU
# ===========================================================================
printf '%s\n' "${LIGNES[@]}"
echo

if ((${#MANQUANTS[@]} > 0)); then
  echo "  NON EXECUTEE — ${#MANQUANTS[@]} acces manquant(s):"
  printf '    - %s\n' "${MANQUANTS[@]}"
  echo
  echo "  SUPABASE_UNVERIFIED reste vrai. Aucune compatibilite Supabase ne"
  echo "  doit etre affirmee, dans le depot comme ailleurs, tant que les sept"
  echo "  etapes n'ont pas ete traversees sur une instance reelle."
  exit 4
fi

if [[ "${EUROSTRUCT_RECETTE_CIBLE:-}" != "staging" ]]; then
  echo "  REFUSEE — les acces sont la, le consentement non."
  echo "  Les sept etapes ECRIVENT sur l'instance visee: roles, migrations,"
  echo "  decisions, objets. Relancer avec EUROSTRUCT_RECETTE_CIBLE=staging."
  exit 2
fi

echo "  Les sept etapes sont executables. Enchainement:"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KO=0
etape() {
  local nom="$1"; shift
  echo "    -> $nom"
  if "$@"; then echo "       ok"; else echo "       ECHEC"; KO=1; fi
}
etape "0. plan de controle" env \
  DATABASE_URL="$EUROSTRUCT_PROBE_DATABASE_URL" \
  EUROSTRUCT_PROBE_TARGET="$EUROSTRUCT_PROBE_TARGET" \
  "$HERE/supabase_probe.sh"
((KO)) && { echo "  Le plan de controle a refuse: les six etapes suivantes"
            echo "  n'ont pas de sens sans lui."; exit 1; }

echo "    Les etapes 1 a 7 s'enchainent depuis les harnais existants, une fois"
echo "    l'etape 0 verte. Voir docs/RECETTE_SUPABASE.md pour l'ordre et ce"
echo "    que chacune doit etablir."
exit "$KO"
