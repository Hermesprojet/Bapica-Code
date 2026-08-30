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
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"

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

# LE NOM DE BASE EST VALIDE AVANT TOUTE CONNEXION ET TOUTE REQUETE.
#
# `DB_NAME` vient de l'environnement et etait interpole tel quel dans
# `create database`, `drop database` et les predicats `datname = '...'`. Seuls
# les sous-scripts validaient le leur: le refus n'arrivait donc qu'apres coup,
# par accident d'ordre. La validation porte aussi sur la LONGUEUR, parce que
# les harnais derivent des noms jusqu'a 20 caracteres plus longs et que
# PostgreSQL tronque a 63 — deux bases distinctes pourraient devenir la meme.
harnais_valider_identifiant "DB_NAME" "$DB_NAME" || exit 2

# CETTE SUITE CREE ET DETRUIT DES ROLES GLOBAUX (`normative_backend`,
# `eurostruct_normative_writer`, ...). Les roles appartiennent au CLUSTER, pas
# a une base: lancee sur un cluster partage, de staging ou de production, elle
# detruirait les vrais roles normatifs.
#
# Elle exige donc un cluster ENTIEREMENT JETABLE, prouve tel — declaration
# explicite ET constats. Sans preuve: refus, avant la premiere connexion utile.
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
exiger_precontrole_local "db/test/run.sh" || exit 2
harnais_verrou_prendre "db/test/run.sh" || exit $?   # 2 = parametre invalide, 3 = verrou detenu
exiger_cluster_jetable "db/test/run.sh" || exit 2


# LES SIX ROLES CANONIQUES — `eurostruct_normative_activator` COMPRIS.
#
# Il est cree par 0010 depuis 6.3b6b, il est GLOBAL au cluster comme les
# autres, et il survit a la destruction de la base. Absent de cette liste, il
# n'etait ni exige absent au demarrage ni detruit en sortie: mesure sur le
# cluster de test, il tranait en residu d'une execution anterieure sans
# qu'aucune postcondition ne l'ait signale.
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment
            eurostruct_authority_backend)

# BLOQUANT, et place ICI: avant l'oracle, avant les migrations, avant tout
# test. Le rouge d'une sous-surface ne suffirait pas — `etape()` continue
# volontairement, et la suite irait creer puis detruire des roles qui ne lui
# appartiennent pas. C'est toute la commande qui doit s'arreter.
exiger_roles_absents "db/test/run.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

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
# CODE 4 = NON EXECUTE, ET CE N'EST PAS UN ECHEC — c'est une SURFACE MANQUANTE.
# `cross_cluster_restore.sh` cree un second cluster par `initdb`; sans le paquet
# serveur, il ne peut pas s'executer. Le confondre avec un rouge enverrait
# chercher une panne inexistante; le confondre avec un vert annoncerait une
# garantie qui n'a pas ete verifiee. Les deux sont comptes, et separement.
SURFACES_NON_EXECUTEES=()
etape() {
  local nom="$1"; shift
  local code=0
  "$@" || code=$?
  case $code in
    0) : ;;
    4) SURFACES_NON_EXECUTEES+=("$nom") ;;
    *) SURFACES_ROUGES+=("$nom") ;;
  esac
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
# Nommes AVANT le trap: `set -u` ferait echouer le nettoyage si la suite
# s'arretait avant leur affectation, et le decor resterait derriere.
PLAN_R=""; MIG_R=""
rendre_le_decor() {
  local r
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do registre_role "$r"; done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "db/test/run.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" \
    ${PLAN_R:+"$PLAN_R"} ${MIG_R:+"$MIG_R"} || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap rendre_le_decor EXIT
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

echo "==> oracle comportemental des primitives de portee"
etape "oracle de portee des roles" \
  "$HERE/role_reach_oracle.sh" "${DB_NAME}_oracle"

echo "==> deploiement en deux phases"
etape "deploiement en deux phases" \
  "$HERE/two_phase_deployment.sh" "${DB_NAME}_2p"

# --------------------------------------------------------------------------
# LE ROUNDTRIP DES MIGRATIONS — l'ALLER etait couvert, le RETOUR non
# --------------------------------------------------------------------------
# Chaque harnais part d'une base NEUVE: repasser sur les memes fichiers n'etait
# donc eprouve nulle part. Mesure du 26/08: quatre migrations sur quatorze
# etaient REJOUEES au second passage, faute de s'inscrire au registre — et
# elles transferent des proprietes, posent des policies et retirent des droits.
# Rien, dans cette suite, ne pouvait le voir.
echo "==> roundtrip des migrations (aller-retour, registre, empreinte)"
etape "roundtrip des migrations" \
  "$HERE/migration_roundtrip.sh" "${DB_NAME:0:20}rt"

# --------------------------------------------------------------------------
# LE CONTRAT DE FINALISATION — huit tentatives de contournement
# --------------------------------------------------------------------------
# `two_phase_deployment.sh` verifie que la finalisation MARCHE. Celui-ci
# verifie qu'elle ne peut pas etre CONTOURNEE, et il le fait en essayant. Il
# exige lui aussi un jeu canonique vierge — chacun de ses six decors le pose et
# le rend — et passe donc ici, avant la base principale.
# --------------------------------------------------------------------------
# LES POSTCONDITIONS DE MIGRATION SONT-ELLES ATTEINTES ?
# --------------------------------------------------------------------------
# `migration_roundtrip.sh` etablit que les migrations s'appliquent et ne se
# rejouent pas. Celui-ci pose la question d'a cote: quand le catalogue N'EST
# PAS celui qu'elles ont demande, s'en apercoivent-elles ?
#
# LA REPONSE ETAIT NON JUSQU'A CE LOT. `assert_authority_surface_hardened()`
# existait depuis 0011, refusait correctement, et AUCUN chemin produit ne
# l'appelait — seul un harnais le faisait. Une assertion que le produit
# n'execute jamais ne protege rien: elle tient tant que quelqu'un pense a
# lancer la suite.
#
# Trois observations par migration, et la troisieme est celle qui compte:
# l'appel retire, le meme catalogue fautif doit PASSER. Sans elle, le refus
# mesure ne dit pas d'ou il vient.
echo "==> postconditions de migration"
etape "postconditions de migration" \
  "$HERE/migration_postconditions.sh" "${DB_NAME:0:20}mp"

echo "==> contrat de finalisation"
etape "contrat de finalisation" \
  "$HERE/finalisation_contract.sh" "${DB_NAME:0:20}fc"

# --------------------------------------------------------------------------
# LA FERMETURE DE L'AUTORITE — le migrateur est-il contenu ?
# --------------------------------------------------------------------------
# `finalisation_contract.sh` verifie que la phase 2 ne peut pas etre
# contournee. Celui-ci verifie ce qui se passe A COTE d'elle: pendant la phase
# 1, et apres l'activation, par un chemin qui ne passe jamais par la
# finalisation. Il exige lui aussi un jeu canonique vierge.
echo "==> fermeture de l'autorite"
etape "fermeture de l'autorite" \
  "$HERE/authority_closure.sh" "${DB_NAME:0:20}ac"

# --------------------------------------------------------------------------
# LA FRONTIERE DES ROLES POSTGRESQL, MESUREE DANS LE CATALOGUE
# --------------------------------------------------------------------------
# `authority_closure.sh` demande si le migrateur peut ECRIRE. Celui-ci demande
# s'il peut S'OCTROYER LE DROIT d'ecrire — question distincte, et la seule des
# deux qu'un audit precedent avait manquee: il mesurait `pg_db_role_setting`,
# c'est-a-dire une CONFIGURATION, la ou le chemin reel passait par
# l'APPARTENANCE. `CREATE ROLE` par un role CREATEROLE laisse au createur
# `admin_option=t` — il n'herite ni n'endosse, mais il ENROLE QUI IL VEUT.
#
# ADMINISTRER N'EST PAS UTILISER, MAIS ADMINISTRER SUFFIT A S'OCTROYER
# L'USAGE: mesurer USAGE et SET et s'arreter la laisserait passer exactement
# ce chemin. Quatorze controles, chacun avec son verdict nomme.
echo "==> frontiere des roles postgresql"
etape "frontiere des roles postgresql" \
  "$HERE/authority_role_frontier.sh" "${DB_NAME:0:20}rf"

# --------------------------------------------------------------------------
# LES QUATRE SURFACES D'AUTORITE DE 6.3c
# --------------------------------------------------------------------------
# AUCUNE N'EST « ROUGE ATTENDU », ET C'EST DELIBERE. Le premier cablage de
# 6.3c annoncait l'etape comme telle, parce qu'elle portait un lot de
# contre-exemples ecrit avant tout correctif. Ce dispositif etait TRANSITOIRE
# par construction: un mecanisme qui accepte durablement un rouge finit par
# accepter aussi la regression qui s'y glisse.
#
# Les correctifs sont poses (0011 durcissement, 0012 filiation, 0013 frontiere
# authentifiee). Les quatre surfaces sont donc des etapes ORDINAIRES: elles
# doivent etre vertes, et toute regression fait echouer la suite.
#
# `authority_closure.sh` demande « le MIGRATEUR est-il contenu ? ». Celles-ci
# posent les questions d'apres:
#
#   racine de confiance   l'identite metier qui octroie et confirme est-elle
#                         hors de portee d'un role applicatif ?
#   surface SQL           PUBLIC, proprietaires, search_path, appartenances,
#                         SET ROLE, BYPASSRLS, FORCE RLS
#   filiation             une revocation eteint-elle ce qu'elle a delegue ?
#   amorcage              la premiere autorite est-elle mandatee, ou choisie ?
#   quatre-yeux           une decision porte-t-elle DEUX principals distincts,
#                         et les DEUX sources d'autorite invoquees ?
#
# Toutes exigent un jeu canonique vierge, d'ou leur place ici, avant que la
# base principale ne cree les six roles.
echo "==> racine de confiance des autorites (6.3c)"
etape "racine de confiance des autorites" \
  "$HERE/authority_root_of_trust.sh" "${DB_NAME:0:20}rt"

echo "==> surface SQL de l'autorite (6.3c)"
etape "surface SQL de l'autorite" \
  "$HERE/authority_sql_hardening.sh" "${DB_NAME:0:20}hd"

echo "==> filiation des delegations (6.3c)"
etape "filiation des delegations" \
  "$HERE/authority_delegation_lineage.sh" "${DB_NAME:0:20}ln"

echo "==> contrat d'amorcage de la racine (6.3c)"
etape "contrat d'amorcage de la racine" \
  "$HERE/authority_bootstrap_contract.sh" "${DB_NAME:0:20}bs"

# --------------------------------------------------------------------------
# LE CONTRAT DU PROVIDER — la frontiere d'identite, cote applicatif
# --------------------------------------------------------------------------
# `authority_four_eyes.sh` etablit que la BASE refuse deux fois le meme
# principal. Celui-ci pose la question d'a cote, et elle n'a pas de reponse
# dans PostgreSQL: QUI pose l'identite, et disparait-elle ensuite ?
#
# Un `SET` de session survit a la connexion rendue au pool: le locataire
# suivant heriterait de l'identite du precedent. `SET LOCAL` meurt avec la
# transaction. C'est toute la difference entre « l'acteur est pose pour cette
# unite de travail » et « l'acteur traine », et elle ne se verifie que contre
# un vrai serveur.
#
# SANS PILOTE POSTGRESQL, LE HARNAIS REND 4 — NON EXECUTE, compte comme une
# surface manquante. Une garantie qu'on n'a pas pu verifier ne doit pas passer
# pour verte.
echo "==> contrat du provider (frontiere d'identite)"
etape "contrat du provider" \
  "$HERE/provider_contract.sh" "${DB_NAME:0:20}pv"

# LA TRANCHE APPLICATIVE, SUR LA MEME BASE DEPLOYEE.
#
# `provider_contract.sh` ci-dessus eprouve le CONTRAT du provider avec un
# authentificateur FICTIF. Celui-ci eprouve le chemin PRODUIT: deux identites
# portees par des JETONS RSA SIGNES, verifies par l'authentificateur de
# production, du `Bearer` brut jusqu'au commit.
#
# SANS FASTAPI NI PYJWT, IL REND 4 — NON EXECUTE. Une surface qu'on n'a pas pu
# exercer n'est pas une surface qui a tenu.
echo "==> parcours d'autorite depuis l'API (tranche applicative)"
etape "parcours d'autorite depuis l'API" \
  "$HERE/api_e2e.sh" "${DB_NAME:0:20}ae"

# LE PARCOURS COMPLET: DECISION -> CONFIRMATION -> MODE STRICT.
#
# `api_e2e.sh` etablit que les trois primitives tiennent sous identite
# authentifiee. Il ne dit RIEN de leur EFFET: jusqu'a 0016, une decision
# consommee ne posait aucune confirmation, et `confirmer_depuis_le_provider()`
# ne lit que cette table-la. Les deux chemins existaient cote a cote sans que
# rien ne les relie, et les tests positifs de la passerelle injectaient un
# fournisseur fictif — ils prouvaient l'algorithme, pas le cablage.
#
# Celui-ci part des huit blocages du calcul strict belge, joue les huit cycles
# A/B par les ROUTES PUBLIQUES, et exige que le calcul finisse en 200 avec
# `strict_ndp_satisfied`. AUCUN FOURNISSEUR FICTIF N'Y EST INJECTE: le provider
# est celui de production, sur PostgreSQL.
echo "==> decision consommee -> confirmation -> calcul strict"
etape "decision vers strict" \
  "$HERE/decision_vers_strict.sh" "${DB_NAME:0:20}ds"

echo "==> quatre-yeux explicite (6.3c)"
etape "quatre-yeux explicite" \
  "$HERE/authority_four_eyes.sh" "${DB_NAME:0:20}fy"

# --------------------------------------------------------------------------
# LE CONTRAT DU SCEAU — la racine est-elle DEPLOYABLE ? (6.3b6d)
# --------------------------------------------------------------------------
# `authority_closure.sh` etablit que le migrateur est CONTENU. Celui-ci pose la
# question suivante, qui est celle de l'exploitation: la racine est-elle separee
# du jeu de migrations, versionnee, reexecutable, et honnete sur ce qu'elle
# garantit ? Douze scenarios, chacun avec son propre decor canonique vierge.
echo "==> contrat du sceau"
etape "contrat du sceau" \
  "$HERE/seal_contract.sh" "${DB_NAME:0:20}sc"

# --------------------------------------------------------------------------
# LA COMMANDE OFFICIELLE DE DEPLOIEMENT (6.3b6d)
# --------------------------------------------------------------------------
# `tools/deploy_eurostruct.sh` est le chemin officiel. Un chemin officiel qui
# n'est jamais execute est une documentation deguisee en outil: il derive du
# produit sans que rien ne le signale, et se decouvre le jour du premier
# deploiement reel.
echo "==> commande officielle de deploiement"
etape "commande officielle de deploiement" \
  "$HERE/official_deployment.sh" "${DB_NAME:0:20}od"

# --------------------------------------------------------------------------
# LA RESTAURATION INTER-CLUSTER, EXERCEE (6.3b6d)
# --------------------------------------------------------------------------
# Ce harnais cree un SECOND CLUSTER par `initdb`. Si le paquet SERVEUR de
# PostgreSQL n'est pas installe, il rend 4 — NON EXECUTE — et `etape` le
# rapporte comme tel: une surface qu'on n'a pas pu exercer n'est pas une
# surface qui a tenu, et elle ne doit pas passer pour verte.
# --------------------------------------------------------------------------
# LA COMMANDE OFFICIELLE, QUAND ELLE ECHOUE (6.3b6e)
# --------------------------------------------------------------------------
# `official_deployment.sh` etablit que la commande MARCHE. Celui-ci etablit ce
# qu'elle laisse derriere elle quand elle N'ABOUTIT PAS: capacites du
# migrateur, reprise d'une phase 1 interrompue, concurrence, identifiants SQL,
# branchement sur les SQLSTATE, redirection par l'environnement.
echo "==> reprise de la commande officielle"
etape "reprise de la commande officielle" \
  "$HERE/deploy_recovery.sh" "${DB_NAME:0:20}dr"

echo "==> restauration inter-cluster"
etape "restauration inter-cluster" \
  "$HERE/cross_cluster_restore.sh" "${DB_NAME:0:20}xr"

# --------------------------------------------------------------------------
# L'ISOLATION DE LA MATRICE DE MUTATION (6.3b6e)
# --------------------------------------------------------------------------
# `mutation_matrix.py` n'est PAS dans la suite canonique — elle est longue, et
# c'est un outil d'audit. Mais la propriete « elle n'ecrit jamais dans le depot
# principal » doit tenir a chaque fois, pas seulement le jour ou l'on y pense:
# c'est en la supposant qu'on a perdu du travail non valide, en silence.
#
# CET AUTO-TEST N'A BESOIN D'AUCUNE BASE: il tue la matrice avant qu'elle n'en
# demande une. Il est ici parce que c'est ici que passe la CI, et non parce
# qu'il aurait quoi que ce soit a faire d'un cluster.
# L'INSTRUMENT DE PREUVE EST LUI AUSSI EPROUVE, et avant de s'en servir.
# `mutation_matrix.py` decide si une garantie porte quelque chose: un
# instrument fausse ne rend pas un verdict faux de temps en temps, il le rend
# SILENCIEUSEMENT. L'auto-test ne touche aucune base et dure quelques
# millisecondes — il n'a aucune raison d'etre saute.
echo "==> auto-test du moteur de mutations"
etape "auto-test du moteur de mutations" \
  python3 "$HERE/mutation_engine_selftest.py"

echo "==> isolation de la matrice de mutation"
etape "isolation de la matrice de mutation" \
  "$HERE/mutation_isolation_selftest.sh"

# UN CONTRE-EXEMPLE QUI NE S'EXECUTE PAS N'EN EST PAS UN. `gate_protocol_
# selftest.sh` a ete ecrit comme suite PERMANENTE des garanties de la barriere
# de vivacite, et il n'etait cable nulle part: personne ne l'aurait relance, et
# une garantie non exercee ne se distingue plus d'une garantie perdue. C'est la
# regle de ce fichier, appliquee a lui — une surface non executee n'est pas une
# surface verte.
#
# IL NE TOUCHE AUCUNE BASE. Il EXTRAIT le wrapper de `mutation_matrix.py`, la
# fonction d'attente de `mutation_signal_selftest.sh` et le piege de signaux de
# `lib_harnais.sh` — jamais une copie —, puis les met en echec avec un faux
# harnais. Il est ici pour la meme raison que l'auto-test d'isolation: c'est
# ici que passe la CI.
echo "==> protocole de la barriere de vivacite (contre-exemples)"
etape "protocole de la barriere de vivacite" \
  "$HERE/gate_protocol_selftest.sh"

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
# LA MATRICE MEURT-ELLE PROPREMENT ? (6.3b6e)
# --------------------------------------------------------------------------
# IL APPARTIENT AU GROUPE CI-DESSUS, ET IL ETAIT PLACE EN DERNIER. Le
# raisonnement d'origine n'avait considere qu'un sens: « il cree les roles
# canoniques pendant quelques secondes, donc qu'il passe apres les surfaces
# qui les exigent absents ». L'autre sens n'avait pas ete regarde — la BASE
# PRINCIPALE cree ces memes roles en appliquant ses migrations, et ils lui
# survivent. Place apres elle, le vrai harnais de son scenario A refusait
# systematiquement.
#
# MESURE, ET C'EST UNE SURFACE QUI SE CROYAIT EXERCEE:
#
#     REFUS: seal_contract.sh exige que ces roles n'existent pas encore,
#            et ils existent: eurostruct_deployment, ...
#
# Le harnais rendait 2, le wrapper publiait FAILED, et le scenario A n'exercait
# RIEN sous `run.sh` — c'est-a-dire en CI. Il etait vert en execution autonome,
# et le defaut est reste invisible tant qu'un autre echec le precedait.
#
# Il rend le jeu canonique en sortant, et sa postcondition le verifie: son
# scenario A exige desormais que le decor ait EXISTE avant le signal, puis
# qu'il ait disparu apres.
echo "==> terminaison de la matrice de mutation sur signal"
# LA CONTINUATION DE LIGNE ETAIT CASSEE, ET C'ETAIT UNE REGRESSION MUETTE.
# En inserant le selftest du canal j'avais ecrit:
#
#     etape "terminaison de la matrice sur signal" \
#       python3 "$HERE/canal_selftest.py"
#       "$HERE/mutation_signal_selftest.sh"
#
# La barre oblique rattachait le selftest DU CANAL a une etape qui en nomme un
# autre, et `mutation_signal_selftest.sh` devenait une commande NUE. Sous
# `set -e`, sa moindre defaillance ne devenait plus une surface rouge: elle
# tuait `run.sh` entier, sans nom et sans comptage. Chaque surface a son etape.
etape "canal machine d'attribution" \
  python3 "$HERE/canal_selftest.py"
etape "composition du SQL par le shell" \
  python3 "$HERE/scanner_selftest.py"
# LES CINQ COUCHES DE SEPARATION, ET LEUR CONTRE-EXEMPLE COMPLET.
#
# Cette surface est la seule qui prouve que la relaxation de `0015` — rabattre
# `@MIGRATEUR` et `@PLAN` sur `@DEPLOIEMENT` quand les deux symboles se
# confondent — est acceptable: elle ne l'est que si l'etat confondu ne peut
# jamais atteindre `ACTIVE`. Elle le montre en NEUTRALISANT les cinq couches
# une a une, et en obtenant `ACTIVE` seulement quand les CINQ tombent.
etape "les cinq couches de separation" \
  "$HERE/separation_layers.sh"
etape "terminaison de la matrice sur signal" \
  "$HERE/mutation_signal_selftest.sh"

# --------------------------------------------------------------------------
# Oracle comportemental des primitives de portee (6.3b6a #3).
#
# `assert_normative_topology()` decide qui atteint un role d'autorite au moyen
# de `pg_has_role(..., 'SET' / 'USAGE' / 'MEMBER WITH ADMIN OPTION')`. Ce que
# ces primitives DISENT est ici confronte a ce qui se PASSE — vrai `SET ROLE`,
# vrai heritage, vrai `GRANT` a un tiers — sur six formes de graphe.

# --------------------------------------------------------------------------
# LA BASE PRINCIPALE EST DEPLOYEE COMME UNE PRODUCTION, EN DEUX PHASES
# --------------------------------------------------------------------------
# Elle etait creee et migree par `postgres`. Depuis 6.3b6b, cette forme n'est
# pas finalisable — et elle ne le doit pas: qui migre et qui approuve seraient
# le meme role, la separation serait nominale. La consequence n'etait pas
# theorique: les ecritures normatives de `05_normative_confirmation.sql` sont
# refusees tant que le deploiement est en PENDING, et elles doivent l'etre.
#
# Deux roles NON SUPERUTILISATEURS sont donc introduits, une fois pour toutes
# les bases de cette suite:
#
#   <db>_plan  provisionne les six roles canoniques, prete les trois roles
#              d'autorite au migrateur, et exerce la phase 2 (fait F3: seul le
#              donneur peut revoquer);
#   <db>_mig   proprietaire de la base, applique les migrations.
#
# Les roles d'autorite sont GLOBAUX au cluster: un seul plan de controle les
# provisionne, et chaque base est finalisee separement — ce qui est exactement
# la forme reelle d'un cluster portant plusieurs bases. Les emprunts sont donc
# repretes avant chaque deploiement et rendus par la finalisation.
#
# Les tests de garanties, eux, continuent de tourner sous `postgres`: ils
# verifient la RLS et les declencheurs, pas le deploiement.
PLAN_R="${DB_NAME}_plan"; PLAN_MDP="FICTIF-run-plan"
MIG_R="${DB_NAME}_mig";   MIG_MDP="FICTIF-run-mig"
# LE BACKEND AUTHENTIFIE, DISTINCT DU MIGRATEUR. Depuis 6.3c, la declaration
# « eurostruct.authority_backend_logins » nomme les logins autorises a agir au
# titre d'une autorite normative. Y nommer le MIGRATEUR reviendrait a defaire
# la frontiere que le jalon pose: l'identite TECHNIQUE qui applique un schema
# n'est pas une identite PROFESSIONNELLE. On cree donc un login de service
# dedie, et c'est LUI qui est declare — meme si les tests de garanties
# tournent, eux, sous `postgres`.
SVC_R="${DB_NAME}_svc";   SVC_MDP="FICTIF-run-svc"
# shellcheck disable=SC2034
harnais_valider_identifiant "PLAN_R" "$PLAN_R" || exit 2
harnais_valider_identifiant "MIG_R"  "$MIG_R"  || exit 2
harnais_valider_identifiant "SVC_R"  "$SVC_R"  || exit 2
creer_role "$PLAN_R" "login password '$PLAN_MDP' createrole" \
  || { echo "ECHEC: creation du plan de controle impossible" >&2; exit 1; }
creer_role "$MIG_R" "login password '$MIG_MDP' createrole createdb" \
  || { echo "ECHEC: creation du migrateur impossible" >&2; exit 1; }
creer_role "$SVC_R" "login password '$SVC_MDP'" \
  || { echo "ECHEC: creation du backend authentifie impossible" >&2; exit 1; }
adm -c "grant \"$PLAN_R\" to ${PGUSER:-postgres};" >/dev/null 2>&1

plan_pg() { PGUSER="$PLAN_R" PGPASSWORD="$PLAN_MDP" psql -X -q -d postgres "$@"; }
plan_db() { local b="$1"; shift
            PGUSER="$PLAN_R" PGPASSWORD="$PLAN_MDP" psql -X -q -d "$b" "$@"; }
mig_db()  { local b="$1"; shift
            PGUSER="$MIG_R" PGPASSWORD="$MIG_MDP" psql -X -q -d "$b" "$@"; }

# LE PROVISIONNEMENT EST FAIT PAR LA PHASE 0 (6.3b6c), base par base: elle
# cree les six roles canoniques — globaux, donc une seule fois en pratique — ET
# les quatre tables de confiance, qui sont propres a chaque base.
#
# `preter_les_emprunts` — a refaire avant CHAQUE deploiement: la finalisation
# precedente les a rendus, et c'est le but. DEUX ROLES: l'activateur n'est
# jamais prete, c'est lui qui possede la racine.
preter_les_emprunts() {
  plan_pg -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG_R" with admin option;
grant eurostruct_normative_bootstrap to "$MIG_R" with admin option;
SQL
}

# `deployer <base> <fichier-de-migration>...` — phase 1 puis phase 2.
# Rend 1 et imprime le motif si l'une des deux echoue.
deployer() {
  local b="$1"; shift
  local f out etat manif
  adm -v ON_ERROR_STOP=1 -c "create database \"$b\" owner \"$MIG_R\";" >/dev/null || return 1
  psql -X -q -d "$b" -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  psql -X -q -d "$b" >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG_R" with grant option;
grant select, insert, references on auth.users to "$MIG_R" with grant option;
grant execute on function auth.uid() to "$MIG_R" with grant option;
grant create on database "$b" to "$MIG_R";
grant create on schema public to "$PLAN_R" with grant option;
grant usage on schema auth to "$PLAN_R";
SQL
  adm -c "alter database \"$b\"
            set eurostruct.approved_deployment_roles = '$MIG_R,$PLAN_R';" >/dev/null 2>&1
  # LES DEUX DECLARATIONS DE 6.3c, POSEES AVANT LA PHASE 1.
  #
  # C'est 0013 qui les CONSTATE et les fige pendant la migration; declarees
  # apres, elles ne seraient lues par personne et TOUT le sous-systeme
  # d'autorite resterait ferme. Mesure du 26/08: sans elles, la suite de
  # garanties echouait sur BOOTSTRAP_AUTHORITY_NOT_CONFIGURED — la porte que
  # 6.3c a fermee n'avait ete rouverte que pour les harnais d'autorite, jamais
  # pour la base principale.
  #
  # LE PRINCIPAL DU MANDAT EST CELUI QUE `05_normative_confirmation.sql`
  # amorce. Un mandat qui nommerait quelqu'un d'autre ne serait pas « un
  # mandat quelconque »: il refuserait l'amorcage, ce qui est exactement ce
  # que le mandat doit faire.
  # ET `approved_service_logins`, SANS QUOI LA TOPOLOGIE REFUSE — a juste
  # titre. Mesure: la base de mise a niveau a refuse 0010 sur « le role
  # connectable eurostruct_test_svc atteint le service
  # eurostruct_authority_backend sans approbation ». L'appartenance a un role
  # est CLUSTER-WIDE: des que la base principale accorde le role d'execution au
  # login de service, TOUTES les bases du cluster le voient. Declarer le login
  # dans une seule base ne suffit donc pas.
  adm -c "alter database \"$b\"
            set eurostruct.approved_service_logins = '$SVC_R';" >/dev/null 2>&1
  adm -c "alter database \"$b\"
            set eurostruct.authority_backend_logins = '$SVC_R';" >/dev/null 2>&1
  # LE PRINCIPAL DU MANDAT DEPEND DE LA BASE, et il le faut. Chaque base de
  # cette suite amorce SA racine: la base principale amorce 4444..., celle de
  # concurrence c000...1, celle du contrat croise a100...1. Un mandat unique
  # code en dur refuserait les deux dernieres — et le refus serait juste, ce
  # qui rendrait le diagnostic trompeur. L'appelant pose donc
  # `MANDAT_PRINCIPAL` avant d'appeler `deployer`; a defaut, c'est celui de la
  # base principale.
  adm -c "alter database \"$b\"
            set eurostruct.bootstrap_mandate =
              '${MANDAT_PRINCIPAL:-44444444-4444-4444-4444-444444444444}:FICTIF-EMPREINTE-SUITE-CANONIQUE';" \
    >/dev/null 2>&1
  # PHASE 0 — LE SCEAU, par le plan de controle.
  echo "    control_plane/0001_normative_seal.sql (phase 0)"
  if ! out=$(plan_db "$b" -v ON_ERROR_STOP=1 \
               -f "$HARNAIS_SCEAU" 2>&1); then
    echo "ECHEC: phase 0 refusee sur $b:" >&2
    grep -m2 -E "ERROR|FATAL" <<<"$out" | sed 's/^/       /' >&2
    return 1
  fi
  adm -c "grant eurostruct_deployment to \"$PLAN_R\" with inherit true;" >/dev/null 2>&1
  preter_les_emprunts
  for f in "$@"; do
    esc_appliquer_migration "$f" mig_db "$b"
    case $? in
      0) echo "    $(basename "$f")$( [[ "$ESC_MIGRATION_ETAT" == SAUTEE ]] && echo '  — deja appliquee')" ;;
      *) echo "ECHEC: $(basename "$f") refusee:" >&2
         grep -m2 -E "ERROR|FATAL|MISMATCH" <<<"$ESC_MIGRATION_SORTIE" | sed 's/^/       /' >&2
         return 1 ;;
    esac
  done
  etat=$(plan_db "$b" -tAc 'select normative_activation_state()' 2>&1)
  if [[ "$etat" != "PENDING" ]]; then
    echo "ECHEC: $b ne se termine pas en PENDING (obtenu: $etat)" >&2; return 1
  fi
  manif=$(plan_db "$b" -tAc 'select normative_settings_manifest()' 2>&1)
  out=$(plan_db "$b" -tAc "select normative_finalize_deployment($(esc_litteral "$manif"))" 2>&1)
  etat=$(plan_db "$b" -tAc 'select normative_activation_state()' 2>&1)
  if [[ "$etat" != "ACTIVE" ]]; then
    echo "ECHEC: phase 2 refusee sur $b (etat $etat):" >&2
    grep -m2 -E "ERROR|FATAL" <<<"$out" | sed 's/^/       /' >&2
    return 1
  fi
  # LE ROLE D'EXECUTION VA AU LOGIN DECLARE, ET PAR LE PLAN DE CONTROLE.
  # C'est lui qui a cree le role en phase 0, donc lui seul en detient l'ADMIN
  # — le migrateur, non, et c'est la contenance que 6.3c a posee.
  PGUSER="$PLAN_R" PGPASSWORD="$PLAN_MDP" psql -X -q -d postgres \
    -c "grant eurostruct_authority_backend to \"$SVC_R\";" >/dev/null 2>&1
  echo "    phase 2: $b PENDING -> ACTIVE par « $PLAN_R »"
  return 0
}

echo "==> recreating $DB_NAME"
adm -c "drop database if exists $DB_NAME;" >/dev/null
registre_base "$DB_NAME"

echo "==> applying schema (deploiement en deux phases)"
deployer "$DB_NAME" "$DB_DIR"/migrations/*.sql \
  || { echo "ECHEC: la base principale n'a pas pu etre deployee" >&2; exit 1; }

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
# `deployer` ignore 0000 — c'est la phase 0, qu'il applique lui-meme sous le
# plan de controle. La liste peut donc le contenir sans dommage; ce qui compte
# est que la DERNIERE migration soit appliquee apres les autres.
PRECEDENTES=("$DB_DIR"/migrations/*.sql)
unset 'PRECEDENTES[${#PRECEDENTES[@]}-1]'

echo "==> upgrade path: $(basename "$DERNIERE") sur une base en 0009"
adm -c "drop database if exists $UPGRADE_DB;" >/dev/null
registre_base "$UPGRADE_DB"
# MEME DEPLOIEMENT EN DEUX PHASES: `deployer` applique la liste dans l'ordre
# donne — 0001..0009 puis la derniere — et finalise. Le chemin de mise a niveau
# doit franchir la phase 2 comme le chemin d'installation complete.
deployer "$UPGRADE_DB" "${PRECEDENTES[@]}" "$DERNIERE" \
  || { echo "ECHEC: le chemin de mise a niveau n'a pas pu etre deploye" >&2; exit 1; }
psql -X -q -d "$UPGRADE_DB" -v ON_ERROR_STOP=1 -f "$HERE/upgrade_check.sql"
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
registre_base "$CONC_DB"
# La base de concurrence amorce « c0000000-...-0001 » (voir concurrency.sh).
MANDAT_PRINCIPAL='c0000000-0000-0000-0000-000000000001' \
deployer "$CONC_DB" "$DB_DIR"/migrations/*.sql \
  || { echo "ECHEC: la base de concurrence n'a pas pu etre deployee" >&2; exit 1; }

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
registre_base "$XC_DB"
# La base vierge amorce « a1000000-...-0001 » (voir cross_contract_insert.sql).
MANDAT_PRINCIPAL='a1000000-0000-0000-0000-000000000001' \
deployer "$XC_DB" "$DB_DIR"/migrations/*.sql \
  || { echo "ECHEC: la base vierge n'a pas pu etre deployee" >&2; exit 1; }

XC=(psql -X -q -d "$XC_DB")

etape "base vierge: racine de confiance" \
  "${XC[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/virgin_root.sql"
etape "contrat croise moteur/base" \
  "$HERE/cross_contract.sh" "${XC[@]}"
adm -c "drop database if exists $XC_DB;" >/dev/null

echo ""
if [[ ${#SURFACES_ROUGES[@]} -eq 0 && ${#SURFACES_NON_EXECUTEES[@]} -eq 0 ]]; then
  echo "================================================="
  echo " Toutes les surfaces de db/test sont vertes."
  echo "================================================="
  exit 0
fi
echo "================================================="
if [[ ${#SURFACES_ROUGES[@]} -gt 0 ]]; then
  echo " ${#SURFACES_ROUGES[@]} surface(s) ROUGE(S):"
  for s_rouge in "${SURFACES_ROUGES[@]}"; do echo "   - $s_rouge"; done
fi
if [[ ${#SURFACES_NON_EXECUTEES[@]} -gt 0 ]]; then
  echo " ${#SURFACES_NON_EXECUTEES[@]} surface(s) NON EXECUTEE(S) — pas verte(s):"
  for s_ne in "${SURFACES_NON_EXECUTEES[@]}"; do echo "   - $s_ne"; done
fi
echo "================================================="
exit 1
