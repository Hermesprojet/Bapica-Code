#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b4: prerequis de deploiement sur les roles
#
#   role_prerequisites.sh <nom-de-base-jetable>
#
# POURQUOI UN SCRIPT, ET PAS UN FICHIER SQL DE PLUS.
#
# Ces prerequis s'evaluent PENDANT la migration. Un fichier de `db/test/` ne
# tourne qu'apres, sur une base ou la migration a deja reussi: il ne peut par
# construction pas observer un refus. Il faut donc fabriquer la configuration
# hostile AVANT d'appliquer les migrations, et constater qu'elles refusent.
#
# CE QUI EST TESTE, ET POURQUOI C'EST LA QUE TOUT REPOSE.
#
# `current_user` est la preuve d'origine de toute la chaine normative: la
# reserve du namespace d'audit et la branche d'amorcage l'acceptent parce que
# seul l'interieur d'une fonction SECURITY DEFINER peut le faire valoir un
# role d'autorite. Cette preuve tient a UNE condition: que personne ne puisse
# prendre ces roles. Un seul membre, et tout l'edifice devient decoratif.
#
# CONTRE-EXEMPLES VERIFIES ROUGES contre 6.3b3, dont la version precedente
# joignait `pg_auth_members` une seule fois — appartenance DIRECTE — et
# comparait a une LISTE FERMEE DE NOMS. Ces configurations etaient toutes
# ACCEPTEES; elles sont toutes refusees depuis.
#
# CE QUI RESTE NOMME, ET POURQUOI CE N'EST PAS UNE LISTE FERMEE (6.3b5).
#
# L'en-tete precedent laissait croire que plus aucun nom n'intervenait. C'etait
# faux pour les roles de SERVICE, dont le controle comparait encore a
# ('authenticated', 'anon') — et la contradiction etait visible a l'oeil nu
# entre deux blocs du meme fichier.
#
# La distinction est desormais explicite dans la migration, parce qu'elle est
# reelle:
#
#   * ce que le CATALOGUE sait — attributs privilegies, capacite a se
#     connecter, appartenance transitive — est verifie SANS nommer personne;
#   * ce qu'il ne peut PAS savoir — quels roles un JWT endosse — est DECLARE
#     par le deploiement (`eurostruct.token_roles`), avec la convention
#     Supabase pour defaut seulement.
#
# Un defaut n'est pas une liste fermee: il se remplace sans toucher au code, et
# la migration ne pretend pas deduire ce qu'elle ne peut pas deduire.
#
# MODELE DE MENACE. Les superutilisateurs sont exclus des controles: ils
# satisfont `pg_has_role` pour tout role, peuvent desactiver les declencheurs
# et ne sont pas un adversaire que la base contient. Les roles applicatifs,
# eux, sont contenus.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
DB_DIR="$(dirname "$HERE")"
DB="${1:?usage: role_prerequisites.sh <nom-de-base-jetable>}"

# L'identifiant est interpole dans « create database $DB » sans guillemets:
# il doit donc etre un identifiant SQL simple, et c'est verifie plutot que
# suppose. Le nom vient de run.sh aujourd'hui, mais un script appele a la main
# avec un nom fantaisiste executerait ce qu'il contient.
if ! [[ "$DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ ]]; then
  echo "      ECHEC: nom de base « $DB » invalide (identifiant SQL simple attendu)" >&2
  exit 2
fi

ROLES_FICTIFS="fictif_login_a fictif_b fictif_c fictif_relais"

# DETRUIRE PAR NOM N'EST LEGITIME QU'APRES AVOIR PROUVE L'ABSENCE.
#
# Cette liste servait aussi de liste de destruction: le nettoyage faisait
# `drop role if exists` sur chacun, qu'ils aient ete crees ici ou non. Sur un
# cluster ou un `fictif_b` appartenait a quelqu'un d'autre, il partait — et
# rien ne le signalait.
#
# On exige donc qu'aucun n'existe au demarrage. Tout role de cette liste
# present a la fin a alors ete cree par CETTE execution, et lui seul peut etre
# detruit. C'est la meme discipline que pour les roles canoniques, dont le nom
# est impose et ne peut pas etre suffixe d'un jeton.
CANONIQUES="eurostruct_normative_writer eurostruct_normative_bootstrap
            normative_backend normative_governance eurostruct_deployment"
# Ce fichier APPLIQUE LES MIGRATIONS: il cree donc aussi les roles canoniques,
# qui survivent a la destruction de sa base. Meme exigence, meme preuve.
# shellcheck disable=SC2086
exiger_roles_absents "role_prerequisites.sh" $ROLES_FICTIFS $CANONIQUES || exit 2

# La connexion vient de l'ENVIRONNEMENT, jamais d'argv (6.3b6a, securite des
# harnais). La version precedente reecrivait `$DATABASE_URL` a la main pour
# changer de base: le mot de passe se retrouvait dans `ps`, lisible par tout
# processus de la machine. Seule la base change desormais, par `-d`.
harnais_connexion || exit 2

# LA GARDE S'APPLIQUE ICI AUSSI. Ce script cree et supprime des roles GLOBAUX a
# noms fixes; il est appelable seul, et le fait que `run.sh` ait deja verifie
# le cluster ne le protege pas.
#
# ORDRE: precontrole SANS RESEAU d'abord (intention + boucle locale, lus dans
# l'environnement), verrou ensuite, porte catalogue enfin. Une version
# precedente se connectait avant tout controle: avec une `DATABASE_URL`
# distante, une connexion partait — et des identifiants avec elle — avant le
# moindre refus.
exiger_precontrole_local "role_prerequisites.sh" || exit 2
harnais_verrou_prendre  "role_prerequisites.sh" || exit 3
exiger_cluster_jetable  "role_prerequisites.sh" || exit 2

# LA GARDE S'APPLIQUE ICI AUSSI (correctif #5).
#
# Ce script cree et supprime des roles GLOBAUX a noms FIXES. Il est appelable
# seul, et `run.sh` ayant deja verifie le cluster ne le protege pas: un script
# sur dans un seul ordre d'appel n'est pas intrinsequement sur. La garde et le
# verrou sont donc pris ici, independamment de l'appelant — et sans cout quand
# l'appelant les detient deja (jeton de proprietaire transmis).
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
harnais_verrou_prendre "role_prerequisites.sh" || exit 3
exiger_cluster_jetable "role_prerequisites.sh" || exit 2

PSQL_DB=(psql -X -q -d "$DB")
PSQL_ADMIN=(psql -X -q -d postgres)

nettoyer() {
  # ORDRE. Defaire les GREFFES d'abord, detruire ensuite.
  #
  # La version precedente detruisait les roles fictifs PUIS tentait
  # « revoke fictif_relais from authenticated » — sur un role qui n'existait
  # deja plus. La revocation echouait donc silencieusement (2>&1 >/dev/null),
  # et si un jour PostgreSQL refuse de detruire un role encore greffe, le
  # nettoyage se serait bloque sans que rien ne le dise. Un nettoyage dont
  # l'ordre est faux ne se voit qu'au moment ou il compte.
  "${PSQL_ADMIN[@]}" -q -c "drop database if exists $DB;" >/dev/null 2>&1

  # 1. Les greffes sur des roles PERMANENTS, qui survivent a ce script.
  "${PSQL_ADMIN[@]}" -q -c \
    "revoke fictif_relais from authenticated;" >/dev/null 2>&1
  # 2. L'attribut altere par le scenario D, rendu a son etat.
  "${PSQL_ADMIN[@]}" -q -c \
    "alter role eurostruct_normative_writer nologin;" >/dev/null 2>&1
  # 3. Et seulement alors, les roles fictifs eux-memes — dont l'absence
  #    prealable a ete PROUVEE, si bien que ceux presents ici sont les notres.
  # La base D'ABORD: les roles canoniques y possedent des fonctions, et
  # `DROP OWNED BY` ne voit que la base courante.
  "${PSQL_ADMIN[@]}" -q -c "
    select pg_terminate_backend(pid) from pg_stat_activity
     where datname = '$DB' and pid <> pg_backend_pid();" >/dev/null 2>&1
  "${PSQL_ADMIN[@]}" -q -c "drop database if exists $DB;" >/dev/null 2>&1
  for r in $ROLES_FICTIFS $CANONIQUES; do
    "${PSQL_ADMIN[@]}" -q -c "drop owned by $r;" >/dev/null 2>&1
    "${PSQL_ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
  # La restitution est VERIFIEE, base et roles, par noms exacts. Sans cela,
  # « sans residu » resterait une affirmation.
  # shellcheck disable=SC2086
  harnais_postcondition_nettoyage "role_prerequisites.sh" $ROLES_FICTIFS $CANONIQUES \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ "${NETTOYAGE_KO:-0}" -eq 0 ]] || exit 3
}
NETTOYAGE_KO=0
registre_base "$DB"
trap nettoyer EXIT

# Le serveur doit repondre AVANT tout. Sans ce controle, une base injoignable
# faisait echouer chaque `psql`, `err` restait vide, et le script annoncait
# « la migration ACCEPTE cette configuration » — un diagnostic faux qui
# designe le mauvais coupable. Un test doit savoir distinguer « la garantie
# est absente » de « je n'ai pas pu regarder ».
if ! "${PSQL_ADMIN[@]}" -X -q -tAc 'select 1' >/dev/null 2>&1; then
  echo "      ECHEC: serveur PostgreSQL injoignable — aucun prerequis verifie" >&2
  exit 2
fi

nettoyer

KO=0

# Un scenario: fabriquer la configuration hostile, appliquer les migrations,
# exiger un refus PORTANT SUR LE BON MOTIF. Un refus pour une autre raison
# serait un test vert sur un sujet different.
scenario() {
  local nom="$1" sql="$2" attendu="$3"
  nettoyer
  "${PSQL_ADMIN[@]}" -q -c "create database $DB;" >/dev/null

  # Environnement GERE: les roles PREEXISTENT a la migration, avec des
  # attributs et des appartenances qu'elle n'a pas choisis. C'est exactement
  # la situation que ce prerequis existe pour couvrir — sur une base ou la
  # migration cree elle-meme des roles neufs, il n'y aurait rien a verifier.
  "${PSQL_DB[@]}" -q >/dev/null 2>&1 <<'SQL'
do $$
declare r text;
begin
  foreach r in array array['eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap',
                           'normative_backend', 'normative_governance',
                           'authenticated', 'anon'] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
  end loop;
end $$;
SQL
  "${PSQL_ADMIN[@]}" -q -c "$sql" >/dev/null 2>&1

  local err="" out=""
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" \
    >/dev/null 2>&1
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! out=$("${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$f" 2>&1); then
      err=$(grep -m1 -oE "prerequis non tenu: .{0,120}" <<<"$out")
      break
    fi
  done

  if [[ -z "$err" ]]; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              la migration ACCEPTE cette configuration\n'
    KO=1; return
  fi
  if ! grep -q "$attendu" <<<"$err"; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              refus obtenu, mais hors sujet\n'
    printf '              attendu ~ /%s/\n' "$attendu"
    printf '              obtenu:   %s\n' "$err"
    KO=1; return
  fi
  printf '      ok: %s\n' "$nom"
}

echo "    prerequis de deploiement sur les roles"

scenario "role LOGIN arbitraire, membre direct du writer" \
  "create role fictif_login_a login password 'FICTIF';
   grant eurostruct_normative_writer to fictif_login_a;" \
  "fictif_login_a.*membre de"

scenario "role NOLOGIN, membre direct du bootstrap" \
  "create role fictif_b nologin;
   grant eurostruct_normative_bootstrap to fictif_b;" \
  "fictif_b.*membre de"

# Sur les roles d'AUTORITE, aucune violation PUREMENT transitive n'existe: la
# regle interdit TOUT membre, donc la chaine est coupee a son premier maillon.
# C'est une propriete du controle, pas une lacune du test — et le dire evite
# de croire que la transitivite est prouvee ici. Elle l'est au scenario
# suivant.
scenario "chaine a deux sauts vers le writer, coupee au premier maillon" \
  "create role fictif_relais nologin;
   grant eurostruct_normative_writer to fictif_relais;
   create role fictif_c login password 'FICTIF';
   grant fictif_relais to fictif_c;" \
  "membre de « eurostruct_normative_writer »"

# LA transitivite, prouvee la ou des membres sont LEGITIMES: un role de
# service a vocation a etre endosse par l'application. Ici le porteur de jeton
# n'est membre que de `fictif_relais`, qui n'est nomme nulle part: une jointure
# directe sur pg_auth_members ne verrait rien. Le porteur, lui, est DECLARE
# (`eurostruct.token_roles`, defaut « authenticated,anon »), parce qu'aucune
# requete sur le catalogue ne peut deviner quel role un JWT endosse.
scenario "transitive reelle: porteur de jeton -> relais -> normative_backend" \
  "create role fictif_relais nologin;
   grant normative_backend to fictif_relais;
   grant fictif_relais to authenticated;" \
  "authenticated.*atteint le role de service"

# ---------------------------------------------------------------------
# 6.3b5 #3 — roles de service PREEXISTANTS, connectables ou privilegies
# ---------------------------------------------------------------------
# Un environnement gere peut livrer `normative_backend` deja peuple, deja
# connectable, ou rattache a un role qui porte CREATEROLE. Rien dans la
# migration ne l'avait envisage: elle ne regardait que les porteurs de jeton.
#
# FAIL-CLOSED. Un role connectable qui atteint un role de service est refuse
# TANT QU'IL N'EST PAS APPROUVE. Un role PRIVILEGIE qui l'atteint est refuse
# SANS RECOURS: il contourne deja la RLS, et lui ajouter les droits d'ecriture
# normatifs rendrait le cloisonnement doublement nominal.
scenario "role connectable atteignant normative_backend, non approuve" \
  "create role fictif_login_a login password 'FICTIF';
   grant normative_backend to fictif_login_a;" \
  "fictif_login_a.*sans avoir ete approuve"

scenario "connectable atteignant un service par TRANSITIVITE, non approuve" \
  "create role fictif_relais nologin;
   grant normative_governance to fictif_relais;
   create role fictif_c login password 'FICTIF';
   grant fictif_relais to fictif_c;" \
  "fictif_c.*sans avoir ete approuve"

scenario "role PRIVILEGIE (createrole) atteignant normative_backend" \
  "create role fictif_b nologin createrole;
   grant normative_backend to fictif_b;" \
  "fictif_b.*atteint le role de service"

scenario "role PRIVILEGIE (bypassrls) atteignant normative_backend" \
  "create role fictif_b nologin bypassrls;
   grant normative_backend to fictif_b;" \
  "fictif_b.*atteint le role de service"

scenario "role d'autorite rendu connectable" \
  "alter role eurostruct_normative_writer login password 'FICTIF';" \
  "peut se connecter"

# LA MOITIE POSITIVE DE L'APPROBATION. Le meme role connectable, DECLARE
# cette fois, doit passer — sinon « fail-closed » ne serait qu'un refus
# systematique deguise, et le produit resterait indeployable.
#
# L'approbation est posee sur la BASE (ALTER DATABASE ... SET), donc lue par
# la migration qui s'y connecte. C'est la declaration de celui qui exerce les
# migrations, au moment ou il les exerce.
nettoyer
"${PSQL_ADMIN[@]}" -q -c "create database $DB;" >/dev/null
"${PSQL_DB[@]}" -q >/dev/null 2>&1 <<'SQL'
do $$
declare r text;
begin
  foreach r in array array['eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap',
                           'normative_backend', 'normative_governance',
                           'authenticated', 'anon'] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
  end loop;
end $$;
SQL
"${PSQL_ADMIN[@]}" -q -c "create role fictif_login_a login password 'FICTIF';
                          grant normative_backend to fictif_login_a;"   >/dev/null 2>&1
"${PSQL_ADMIN[@]}" -q -c   "alter database $DB set eurostruct.approved_service_logins = 'fictif_login_a';"   >/dev/null 2>&1
APPROUVE=0
"${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
for f in "$DB_DIR"/migrations/*.sql; do
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null 2>&1 || APPROUVE=1
done
if [[ $APPROUVE -ne 0 ]]; then
  echo "      ECHEC   role connectable APPROUVE refuse malgre la declaration"
  echo "              fail-closed degenererait en refus systematique"
  KO=1
else
  echo "      ok: un role connectable explicitement approuve est accepte"
fi

# La moitie POSITIVE: sans configuration hostile, la migration passe. Sans
# elle, les refus ci-dessus seraient satisfaits par une migration qui
# refuse toujours.
nettoyer
"${PSQL_ADMIN[@]}" -q -c "create database $DB;" >/dev/null
"${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
SAIN=0
for f in "$DB_DIR"/migrations/*.sql; do
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null 2>&1 || SAIN=1
done
if [[ $SAIN -ne 0 ]]; then
  echo "      ECHEC   configuration SAINE refusee: le controle refuse tout"
  KO=1
else
  echo "      ok: une configuration saine reste acceptee"
fi

echo ''
echo '================================================='
echo ' Prerequis de deploiement sur les roles verifies.'
echo '================================================='
exit $KO
