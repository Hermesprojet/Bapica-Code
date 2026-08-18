#!/usr/bin/env bash
#
# Apply the migrations to a scratch database and run the guarantee tests.
#
# Usage:
#   EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole ./db/test/run.sh
#
# La connexion vient de l'environnement (PG* ou DATABASE_URL, decoupee en
# variables libpq et jamais passee en argument). Le cluster doit etre JETABLE:
# cette suite cree et detruit des roles GLOBAUX.
#
# The tests assert the properties the cahier des charges makes blocking: RLS
# tenant isolation, the human validation gate, immutability of signed records,
# and the ten-year retention guard. Any failure exits non-zero.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
DB_NAME="${DB_NAME:-eurostruct_test}"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

# --------------------------------------------------------------------------
# SECURITE DU HARNAIS (6.3b6a)
# --------------------------------------------------------------------------
# LE SECRET NE PASSE PLUS PAR argv. Ce fichier faisait `psql "$DATABASE_URL"`,
# et reecrivait l'URL a la main pour chaque base (`url_pour_base`). Deux
# defauts dans le meme geste:
#
#   * le mot de passe etait lisible dans `ps` par tout processus de la machine;
#   * chaque reecriture d'URL etait une occasion de perdre l'hote ou les
#     identifiants — ce qui s'etait deja produit.
#
# Desormais la connexion vient de l'environnement et SEULE LA BASE change, par
# `-d`. Il n'y a plus d'URL a reecrire, donc plus rien a perdre.
harnais_connexion || exit 2

# CETTE SUITE CREE ET DETRUIT DES ROLES GLOBAUX (`normative_backend`,
# `eurostruct_normative_writer`, ...). Les roles appartiennent au CLUSTER, pas
# a une base: lancee sur un cluster partage, de staging ou de production, elle
# detruirait les vrais roles normatifs.
#
# Elle exige donc un cluster ENTIEREMENT JETABLE, prouve tel — declaration
# explicite ET constats. Sans preuve: refus, avant la premiere connexion utile.
# LE VERROU AVANT LA PORTE. La porte lit le CATALOGUE — roles de plateforme
# geree, bases etrangeres. Deux executions simultanees y voient les objets
# TRANSITOIRES l'une de l'autre et se refusent mutuellement pour un motif faux:
# mesure, une seconde execution rapportait « ce cluster porte supabase_admin »
# alors qu'il s'agissait du temoin momentane de la premiere. Le verrou, lui, ne
# detruit rien; le prendre d'abord rend la porte deterministe.
exiger_precontrole_local "db/test/run.sh" || exit 2
harnais_verrou_prendre "db/test/run.sh" || exit 3
exiger_cluster_jetable "db/test/run.sh" || exit 2

# LE VERROU, pour toute la duree de la suite. Deux executions simultanees
# constateraient toutes deux les roles canoniques absents, puis l'une
# detruirait ceux que l'autre vient de creer. Verrou deja detenu -> code 3, et
# AUCUN nettoyage: nettoyer ici emporterait les objets de l'autre execution.

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment)

# BLOQUANT, et place ICI: avant l'oracle, avant les migrations, avant tout
# test. Le rouge d'une sous-surface ne suffirait pas — `etape()` continue
# volontairement, et la suite irait creer puis detruire des roles qui ne lui
# appartiennent pas. C'est toute la commande qui doit s'arreter.
exiger_roles_absents "db/test/run.sh" "${CANONIQUES[@]}" || exit 2

# La base RECREEE, et non celle nommee dans la connexion. Les deux etaient
# confondues: le script effacait `eurostruct_test` puis appliquait les
# migrations dans la base de l'URL, qui n'etait jamais remise a zero. Une
# seconde execution echouait donc sur « type org_role already exists ».
adm()  { psql -X -q -d postgres "$@"; }
base() { psql -X -q -d "$DB_NAME" "$@"; }

# --------------------------------------------------------------------------
# UN ROUGE N'ARRETE PLUS LA SUITE.
#
# Jusqu'ici chaque etape sortait au premier echec. Consequence mesuree: le
# rouge de l'installation non superutilisateur empechait les etapes SUIVANTES
# — base vierge, contrat croise — de s'executer du tout, et le rapport ne
# disait pas si elles auraient passe. On ne peut pas distinguer « non
# executee » de « verte » si l'une se presente comme l'autre.
SURFACES_ROUGES=()
etape() {
  local nom="$1"; shift
  local code=0
  "$@" || code=$?
  [[ $code -eq 0 ]] || SURFACES_ROUGES+=("$nom")
  return 0
}

# --------------------------------------------------------------------------
# LES SURFACES QUI EXIGENT UN CLUSTER SANS ROLES NORMATIFS PASSENT EN PREMIER
# --------------------------------------------------------------------------
# `two_phase_deployment.sh` refuse si les roles canoniques preexistent — il ne
# detruit jamais ce qu'il n'a pas cree. Or la premiere migration appliquee plus
# bas les CREE, et ils survivent a la destruction de la base. Place apres, il
# refuserait systematiquement.
#
# L'ordre n'est donc pas cosmetique: il est impose par le fait que les roles
# sont globaux. Les deux surfaces nettoient derriere elles, par noms exacts.
# --------------------------------------------------------------------------
# LES ROLES CANONIQUES SONT RENDUS AU CLUSTER EN FIN DE SUITE
# --------------------------------------------------------------------------
# Les migrations les CREENT, et ils survivent a la destruction des bases: une
# seconde execution locale les retrouvait en place. Consequence mesuree:
# `two_phase_deployment.sh` et l'auto-test de securite refusaient — a juste
# titre, puisqu'ils exigent de ne rien detruire qu'ils n'aient cree — et la
# suite se declarait rouge pour une raison etrangere a ce qu'elle teste.
#
# On CONSTATE donc ici s'ils etaient absents avant de commencer. S'ils
# l'etaient, tout role canonique present a la fin a ete cree par cette
# execution, et elle le retire. Sinon on n'y touche pas: ils appartiennent a
# quelqu'un d'autre.
# --------------------------------------------------------------------------
# LE DECOR EST RENDU, ET LA RESTITUTION EST VERIFIEE
# --------------------------------------------------------------------------
# Les migrations CREENT les roles canoniques, et ils survivent a la destruction
# des bases. `exiger_roles_absents` vient d'etablir qu'aucun n'existait: tout
# role canonique present a la fin a donc ete cree par cette execution, et elle
# le retire.
#
# L'ordre compte. `DROP OWNED BY` ne voit que la base courante, et les roles
# d'autorite possedent des fonctions dans les bases de test: les bases partent
# d'abord, ce qui emporte ces objets, et les roles ensuite. L'ordre inverse
# echouait — et l'echec etait masque.
#
# CODE 3 SI LA POSTCONDITION ECHOUE. « Deux executions consecutives sans
# residu » etait une observation du rapport; c'est desormais une propriete
# controlee, base par base et role par role, par nom exact.
NETTOYAGE_KO=0
rendre_le_decor() {
  local r
  for r in "${CANONIQUES[@]}"; do registre_role "$r"; done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "db/test/run.sh" "${CANONIQUES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap rendre_le_decor EXIT

echo "==> oracle comportemental des primitives de portee"
etape "oracle de portee des roles" \
  "$HERE/role_reach_oracle.sh" "${DB_NAME}_oracle"

echo "==> deploiement en deux phases"
etape "deploiement en deux phases" \
  "$HERE/two_phase_deployment.sh" "${DB_NAME}_2p"

# --------------------------------------------------------------------------
# LES ETAPES QUI EXIGENT UN JEU CANONIQUE VIERGE PASSENT AVANT LA BASE
# PRINCIPALE
# --------------------------------------------------------------------------
# `role_prerequisites.sh` et `nonsuperuser_install.sh` exigent desormais, comme
# `two_phase_deployment.sh`, que les roles canoniques soient ABSENTS: c'est la
# seule facon pour eux de prouver que ce qu'ils detruisent leur appartient.
#
# Or la creation de la base principale APPLIQUE LES MIGRATIONS, donc cree ces
# roles, et ils survivent a la destruction de la base. Places apres, les deux
# etapes refuseraient systematiquement.
#
# L'ordre n'est donc pas cosmetique: il est impose par le fait que les roles
# sont globaux. Chacune de ces etapes rend le jeu canonique en sortant, et sa
# postcondition le verifie.
# --------------------------------------------------------------------------
ROLE_DB="${DB_NAME}_roles"
echo "==> prerequis de deploiement sur les roles"
registre_base "$ROLE_DB"
etape "prerequis de deploiement sur les roles" \
  "$HERE/role_prerequisites.sh" "$ROLE_DB"
adm -c "drop database if exists $ROLE_DB;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Installation sous un role de migration NON SUPERUTILISATEUR.
#
# Tout ce qui precede tourne sous `postgres`, superutilisateur — qui transfere
# la propriete d'une fonction sans etre membre de rien, contourne la RLS et
# detient EXECUTE implicitement. Rien de cela n'est vrai de la cible de
# production, et quatre obstacles reels n'apparaissaient qu'ici.
# --------------------------------------------------------------------------
NS_DB="${DB_NAME}_nonsuper"
echo "==> installation sous un role de migration non superutilisateur"
registre_base "$NS_DB"
etape "installation non superutilisateur" \
  "$HERE/nonsuperuser_install.sh" "$NS_DB"
adm -c "drop database if exists $NS_DB;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Oracle comportemental des primitives de portee (6.3b6a #3).
#
# `assert_normative_topology()` decide qui atteint un role d'autorite au moyen
# de `pg_has_role(..., 'SET' / 'USAGE' / 'MEMBER WITH ADMIN OPTION')`. Ce que
# ces primitives DISENT est ici confronte a ce qui se PASSE — vrai `SET ROLE`,
# vrai heritage, vrai `GRANT` a un tiers — sur six formes de graphe.

echo "==> recreating $DB_NAME"
adm -c "drop database if exists $DB_NAME;" >/dev/null
creer_base "$DB_NAME" >/dev/null

echo "==> applying schema"
for f in \
  "$HERE/00_supabase_stub.sql" \
  "$DB_DIR"/migrations/*.sql
do
  echo "    $(basename "$f")"
  base -v ON_ERROR_STOP=1 -f "$f"
done

echo "==> seeding national annexes"
base -v ON_ERROR_STOP=1 -f "$DB_DIR/seed/0001_ndp.sql"

echo "==> running guarantee tests"
for t in "$HERE"/0[1-9]_*.sql; do
  echo "    $(basename "$t")"
  base -v ON_ERROR_STOP=1 -f "$t"
done

# --------------------------------------------------------------------------
# Mise a niveau depuis une base DEJA INSTALLEE, et non depuis le vide.
#
# La boucle ci-dessus n'exerce qu'un seul chemin: installation complete d'un
# coup. Or une base de production part de l'etat ou elle est. Une migration
# qui ne passerait que sur une base vierge — parce qu'elle suppose un type
# absent, ou recree un objet deja present — echouerait au deploiement et
# nulle part ici.
#
# On rejoue donc l'histoire: 0001..0009 d'abord, la derniere migration
# ensuite, dans une base separee.
# --------------------------------------------------------------------------
UPGRADE_DB="${DB_NAME}_upgrade"
DERNIERE="$(ls "$DB_DIR"/migrations/*.sql | tail -1)"
PRECEDENTES=("$DB_DIR"/migrations/*.sql)
unset 'PRECEDENTES[${#PRECEDENTES[@]}-1]'

echo "==> upgrade path: $(basename "$DERNIERE") sur une base en 0009"
adm -c "drop database if exists $UPGRADE_DB;" >/dev/null
creer_base "$UPGRADE_DB" >/dev/null

UP=(psql -X -q -d "$UPGRADE_DB")

"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "${PRECEDENTES[@]}"; do
  "${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done
"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$DERNIERE"
"${UP[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/upgrade_check.sql"
adm -c "drop database if exists $UPGRADE_DB;" >/dev/null

# --------------------------------------------------------------------------
# Concurrence, sur DEUX CONNEXIONS REELLES.
#
# Les fichiers SQL ci-dessus tournent tous dans une seule session: ils ne
# peuvent pas exhiber une course. Or `IF EXISTS` suivi d'`INSERT` passe tous
# les tests monoconnexion et ne protege de rien.
#
# Base dediee et vierge: les scenarios courent la chaine de confiance depuis
# son ouverture, ce que la base des autres suites ne permet plus.
# --------------------------------------------------------------------------
CONC_DB="${DB_NAME}_conc"
echo "==> concurrence multi-connexion"
adm -c "drop database if exists $CONC_DB;" >/dev/null
creer_base "$CONC_DB" >/dev/null

CONC=(psql -X -q -d "$CONC_DB")
"${CONC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "$DB_DIR"/migrations/*.sql; do
  "${CONC[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done

# `set -e` termine le script AVANT la ligne suivante des que concurrency.sh
# sort non nul: `CONC_CODE` n'etait jamais lu, et la base de test restait
# derriere. La forme `|| CONC_CODE=$?` est la seule qui capture le code sans
# desarmer `set -e` pour le reste du fichier.
CONC_CODE=0
"$HERE/concurrency.sh" "$CONC_DB" || CONC_CODE=$?
adm -c "drop database if exists $CONC_DB;" >/dev/null
[[ $CONC_CODE -eq 0 ]] || exit $CONC_CODE

# --------------------------------------------------------------------------
# Base VIERGE: racine de confiance, puis contrat croise Python <-> SQL.
#
# Deux controles que la base des suites ci-dessus ne peut plus porter, pour la
# meme raison: elle a deja un administrateur amorce.
#
#  * `virgin_root.sql` doit constater qu'une insertion brute en
#    `origin='bootstrap'` est refusee PARCE QUE l'ecriture est fermee — pas
#    parce qu'une racine existe deja. Joue apres 05, il passerait pour la
#    mauvaise raison.
#  * `cross_contract.sh` ouvre lui-meme la chaine de confiance, comme en
#    deploiement, puis y pousse un vrai paquet produit par le moteur.
#
# `virgin_root.sql` ne cree rien — toutes ses insertions echouent, et il le
# verifie. La base est donc encore vierge pour le contrat croise.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Prerequis de deploiement sur les roles.
#
# S'evaluent PENDANT la migration: aucun fichier de db/test/ ne peut les
# observer, puisqu'ils ne tournent que sur une base ou la migration a deja
# reussi. Le script fabrique donc la configuration hostile AVANT d'appliquer
# les migrations, et exige un refus.
XC_DB="${DB_NAME}_contract"
echo "==> base vierge: racine de confiance et contrat croise"
adm -c "drop database if exists $XC_DB;" >/dev/null
creer_base "$XC_DB" >/dev/null

XC=(psql -X -q -d "$XC_DB")
"${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql"
for f in "$DB_DIR"/migrations/*.sql; do
  "${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$f"
done

etape "base vierge: racine de confiance" \
  "${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/virgin_root.sql"
etape "contrat croise moteur/base" \
  "$HERE/cross_contract.sh" "${XC[@]}"
adm -c "drop database if exists $XC_DB;" >/dev/null

echo ""
if [[ ${#SURFACES_ROUGES[@]} -eq 0 ]]; then
  echo "================================================="
  echo " Toutes les surfaces de db/test sont vertes."
  echo "================================================="
  exit 0
fi
echo "================================================="
echo " ${#SURFACES_ROUGES[@]} surface(s) ROUGE(S):"
for s_rouge in "${SURFACES_ROUGES[@]}"; do echo "   - $s_rouge"; done
echo "================================================="
exit 1
