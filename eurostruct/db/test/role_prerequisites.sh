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
#
# CE QUE CE FICHIER NE PROUVE PAS, ET NE PROUVAIT DEJA PAS (6.3b6d)
# ------------------------------------------------------------------
# Ses boucles appliquaient `migrations/*.sql` — sceau compris — SOUS UN ACTEUR
# UNIQUE. Il n'a donc jamais rien etabli sur la SEPARATION entre le plan de
# controle et le migrateur, et il ne faut pas le lire ainsi: cette separation
# est etablie par `nonsuperuser_install.sh`, `two_phase_deployment.sh`,
# `authority_closure.sh` et `seal_contract.sh`.
#
# Ce qu'il etablit — et c'est ce pour quoi il existe — est TOPOLOGIQUE: la
# phase 1 refuse-t-elle une configuration de roles hostile, et accepte-t-elle
# une configuration saine ?
#
# Il construit desormais le meme deploiement a DEUX ACTEURS que les autres:
# phase 0 par le plan de controle, phase 1 par le migrateur. Non pour prouver
# la separation, mais parce qu'exercer un refus dans une configuration que le
# produit ne connait pas ne prouve rien sur le produit.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"
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

# LES DEUX ACTEURS DU DEPLOIEMENT (6.3b6d) portent eux aussi des noms fixes, et
# passent donc par la meme discipline: absence prouvee au demarrage, puis
# destruction par nom exact.
ROLES_FICTIFS="fictif_login_a fictif_b fictif_c fictif_relais
               fictif_plan fictif_migrateur"
PLAN=fictif_plan
MIGR=fictif_migrateur
MDP_ACTEURS='FICTIF-role-prereq'

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
            eurostruct_normative_activator
            normative_backend normative_governance eurostruct_deployment"

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
# UN SEUL CHEMIN, ET L'ORDRE EST LA GARANTIE.
#
# Ce fichier en avait deux: `exiger_roles_absents` s'executait AVANT meme
# `harnais_connexion` — donc avant tout precontrole — et deux blocs successifs
# prenaient le verrou puis la porte. Un ordre qui existe en double n'est plus
# un ordre: le lecteur ne sait pas lequel fait foi, et le premier appel decide.
#
#   1. decodage local de la connexion, sans reseau
#   2. precontrole du consentement et de l'hote, sans reseau
#   3. validation des parametres et des noms
#   4. prise ou verification du verrou
#   5. controle du catalogue
#   6. verification de l'absence des roles
#   7. seulement ensuite, creation ou destruction
exiger_precontrole_local "role_prerequisites.sh" || exit 2
harnais_valider_identifiant "nom de base" "$DB" || exit 2
harnais_verrou_prendre  "role_prerequisites.sh" || exit $?   # 2 = parametre invalide, 3 = verrou detenu
exiger_cluster_jetable  "role_prerequisites.sh" || exit 2
# shellcheck disable=SC2086
exiger_roles_absents "role_prerequisites.sh" $ROLES_FICTIFS $CANONIQUES \
  "${HARNAIS_ROLES_STUB[@]}" || exit 2

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

PSQL_DB=(psql -X -q -d "$DB")
PSQL_ADMIN=(psql -X -q -d postgres)

# --------------------------------------------------------------------------
# LE DEPLOIEMENT A DEUX ACTEURS (6.3b6d)
# --------------------------------------------------------------------------
# `poser_la_base` construit une base PENDANTE dans la forme reelle: phase 0 par
# le plan de controle, emprunts pretes au migrateur. `appliquer_phase_1` fait
# ensuite ce que le migrateur fait, et c'est LA que les prerequis se refusent.
#
# Les roles canoniques sont pre-crees par l'administrateur dans chaque scenario
# — c'est la forme « environnement gere » que ce fichier existe pour couvrir.
# Les emprunts viennent donc de l'administrateur et non du plan de controle:
# ces scenarios ne FINALISENT jamais, si bien que la derivation du donneur n'y
# joue aucun role. Ecrire le contraire donnerait a ce fichier l'air de prouver
# une separation qu'il ne prouve pas.
psql_plan() { PGUSER="$PLAN" PGPASSWORD="$MDP_ACTEURS" psql -X -q -d "$DB" "$@"; }
psql_mig()  { PGUSER="$MIGR" PGPASSWORD="$MDP_ACTEURS" psql -X -q -d "$DB" "$@"; }

poser_la_base() {
  "${PSQL_ADMIN[@]}" -q -c "create role $PLAN login password '$MDP_ACTEURS' createrole;" >/dev/null 2>&1
  "${PSQL_ADMIN[@]}" -q -c "create role $MIGR login password '$MDP_ACTEURS' createrole createdb;" >/dev/null 2>&1
  "${PSQL_ADMIN[@]}" -q -c "create database $DB owner \"$MIGR\";" >/dev/null
  "${PSQL_DB[@]}" -v ON_ERROR_STOP=1 -q -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  "${PSQL_DB[@]}" -q >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIGR" with grant option;
grant select, insert, references on auth.users to "$MIGR" with grant option;
grant execute on function auth.uid() to "$MIGR" with grant option;
grant create on database "$DB" to "$MIGR";
grant create on schema public to "$PLAN" with grant option;
grant usage on schema auth to "$PLAN";
SQL
  # LES DEUX ACTEURS SONT DECLARES. `eurostruct_deployment` ouvre la chaine de
  # confiance: la topologie exige que ses detenteurs soient nommes par le
  # deploiement. Sans cette declaration, les deux scenarios POSITIFS echouaient
  # sur « fictif_plan detient eurostruct_deployment sans avoir ete declare » —
  # un refus exact, mais sur un sujet que ce fichier ne traite pas.
  "${PSQL_ADMIN[@]}" -q -c \
    "alter database $DB set eurostruct.approved_deployment_roles = '$MIGR,$PLAN';" \
    >/dev/null 2>&1
}

# `phase_0` — le sceau, pose par le plan de controle. Rend 1 et laisse la
# sortie dans `PHASE0_OUT` si elle refuse: un decor qui ne se pose pas ne doit
# pas etre confondu avec un prerequis qui refuse.
PHASE0_OUT=""
phase_0() {
  if ! PHASE0_OUT=$(psql_plan -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
    return 1
  fi
  # LES EMPRUNTS, par l'administrateur qui a cree les roles canoniques. Sans
  # eux la phase 1 ne peut pas transferer la propriete de ses fonctions, et
  # echouerait sur un motif etranger a ce qui est teste.
  "${PSQL_ADMIN[@]}" -q >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIGR" with admin option;
grant eurostruct_normative_bootstrap to "$MIGR" with admin option;
grant eurostruct_deployment to "$PLAN" with inherit true;
SQL
  return 0
}

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
  for r in $ROLES_FICTIFS $CANONIQUES "${HARNAIS_ROLES_STUB[@]}"; do
    "${PSQL_ADMIN[@]}" -q -c "drop owned by \"$r\";" >/dev/null 2>&1
    "${PSQL_ADMIN[@]}" -q -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
  # La restitution est VERIFIEE, base et roles, par noms exacts. Sans cela,
  # « sans residu » resterait une affirmation.
  # shellcheck disable=SC2086
  harnais_postcondition_nettoyage "role_prerequisites.sh" $ROLES_FICTIFS $CANONIQUES \
    "${HARNAIS_ROLES_STUB[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ "${NETTOYAGE_KO:-0}" -eq 0 ]] || exit 3
}
NETTOYAGE_KO=0
registre_base "$DB"
trap nettoyer EXIT
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

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
preexister_les_roles() {
  # Environnement GERE: les roles PREEXISTENT a la migration, avec des
  # attributs et des appartenances qu'elle n'a pas choisis. C'est exactement
  # la situation que ce prerequis existe pour couvrir — sur une base ou la
  # migration cree elle-meme des roles neufs, il n'y aurait rien a verifier.
  "${PSQL_ADMIN[@]}" -q >/dev/null 2>&1 <<'SQL'
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
}

scenario() {
  local nom="$1" sql="$2" attendu="$3"
  nettoyer
  preexister_les_roles
  poser_la_base
  if ! phase_0; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              la phase 0 a refuse: le scenario n%s\n' "'est pas evalue"
    grep -m1 ERROR <<<"$PHASE0_OUT" | cut -c1-160 | sed 's/^/              /'
    KO=1; return
  fi
  # LA CONFIGURATION HOSTILE EST POSEE ENTRE LES DEUX PHASES. La poser avant la
  # phase 0 ferait refuser le decor lui-meme dans certains cas — un role
  # d'autorite rendu connectable, par exemple — et le refus obtenu ne serait
  # plus celui de la phase 1.
  "${PSQL_ADMIN[@]}" -q -c "$sql" >/dev/null 2>&1

  local err="" out=""
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" psql_mig; then
      out="$ESC_MIGRATION_SORTIE"
      err=$(grep -m1 -oE "prerequis non tenu: .{0,120}" <<<"$out")
      break
    fi
  done

  if [[ -z "$err" ]]; then
    printf '      ECHEC   %s\n' "$nom"
    printf '              la migration ACCEPTE cette configuration\n'
    KO=1; return
  fi
  # `grep -E`: les motifs portent des alternatives. En expression rationnelle
  # BASIQUE — le defaut de `grep` — « (a|b) » ne designe pas une alternative
  # mais la chaine litterale, si bien qu'un refus correct etait annonce « hors
  # sujet ». Le motif dit ce qu'il a l'air de dire.
  if ! grep -qE "$attendu" <<<"$err"; then
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
  "fictif_login_a.*(membre de|peut endosser ou heriter de)"

scenario "role NOLOGIN, membre direct du bootstrap" \
  "create role fictif_b nologin;
   grant eurostruct_normative_bootstrap to fictif_b;" \
  "fictif_b.*(membre de|peut endosser ou heriter de)"

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
  "(membre de|peut endosser ou heriter de) « eurostruct_normative_writer »"

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
preexister_les_roles
poser_la_base
phase_0 || { echo "      ECHEC   la phase 0 a refuse: le cas APPROUVE n'est pas evalue"; KO=1; }
"${PSQL_ADMIN[@]}" -q -c "create role fictif_login_a login password 'FICTIF';
                          grant normative_backend to fictif_login_a;"   >/dev/null 2>&1
"${PSQL_ADMIN[@]}" -q -c   "alter database $DB set eurostruct.approved_service_logins = 'fictif_login_a';"   >/dev/null 2>&1
APPROUVE=0
APPROUVE_OUT=""
for f in "$DB_DIR"/migrations/*.sql; do
  esc_appliquer_migration "$f" psql_mig || { APPROUVE=1; APPROUVE_OUT="$ESC_MIGRATION_SORTIE"; break; }
done
if [[ $APPROUVE -ne 0 ]]; then
  grep -m1 -E "ERROR|FATAL" <<<"$APPROUVE_OUT" | cut -c1-160 | sed 's/^/              /'
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
poser_la_base
SAIN=0
SAIN_OUT=""
phase_0 || { SAIN=1; SAIN_OUT="$PHASE0_OUT"; }
if [[ $SAIN -eq 0 ]]; then
  for f in "$DB_DIR"/migrations/*.sql; do
    esc_appliquer_migration "$f" psql_mig || { SAIN=1; SAIN_OUT="$ESC_MIGRATION_SORTIE"; break; }
  done
fi
if [[ $SAIN -ne 0 ]]; then
  echo "      ECHEC   configuration SAINE refusee: le controle refuse tout"
  grep -m1 -E "ERROR|FATAL" <<<"$SAIN_OUT" | cut -c1-160 | sed 's/^/              /'
  KO=1
else
  echo "      ok: une configuration saine reste acceptee"
fi

# LE VERDICT DOIT DIRE CE QUE LE CODE DE SORTIE DIT.
#
# Ce bloc annoncait « verifies » sans condition, y compris en sortant avec 1.
# Un compte rendu lu sans le code de sortie — c'est-a-dire la plupart du
# temps — annoncait donc vert une surface rouge.
echo ''
echo '================================================='
if [[ $KO -eq 0 ]]; then
  echo ' Prerequis de deploiement sur les roles verifies.'
else
  echo ' Prerequis de deploiement sur les roles: AU MOINS UN ECART.'
fi
echo '================================================='
exit $KO
