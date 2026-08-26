#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b5: installation complete sous un role de migration
#                     NON SUPERUTILISATEUR
#
#   nonsuperuser_install.sh <nom-de-base-jetable>
#
# CE QUE CE TEST EXISTE POUR ATTRAPER
# ------------------------------------
# Toute la suite tournait jusqu'ici sous `postgres`, superutilisateur. Or un
# superutilisateur:
#
#   * satisfait `pg_has_role(...)` pour TOUT role, donc transfere la propriete
#     d'une fonction a n'importe qui sans etre membre de rien;
#   * contourne la RLS;
#   * detient EXECUTE implicitement sur toute fonction.
#
# Aucune de ces trois choses n'est vraie de la cible de production. Une
# migration peut donc passer mille fois en CI et echouer au premier
# deploiement reel — ce qui etait EXACTEMENT le cas: `ALTER FUNCTION ... OWNER
# TO eurostruct_normative_writer` exige d'etre membre de ce role, et rien dans
# la migration ne l'organisait.
#
# CE QUE CE TEST NE PROUVE PAS
# -----------------------------
# Il ne prouve PAS la compatibilite Supabase. Il reproduit le MODELE DE
# PRIVILEGES de Supabase — role de migration non superutilisateur dote de
# CREATEROLE et CREATEDB, roles `anon` / `authenticated` / `service_role`
# NOLOGIN endosses par un `authenticator` connectable, schema `auth` separe —
# sur un PostgreSQL 16 ordinaire. Ce qu'il ne reproduit pas: les extensions
# preinstallees de Supabase, ses politiques par defaut, son PgBouncer, ses
# `event triggers`, et le contenu reel de son schema `auth`.
#
# La compatibilite Supabase ne sera etablie que par une execution sur une
# instance de staging reelle. Tant que cette execution n'a pas eu lieu, elle
# ne doit pas etre annoncee. Ce fichier remplace « on suppose que ca marche »
# par « voici ce qui est reellement verifie, et voici ce qui ne l'est pas ».
#
# CE QUI EST JOUE
# ---------------
#   1. 0001 a 0010 appliquees par le role de migration non superutilisateur
#   2. l'amorcage, via l'ACL explicite (EXECUTE sur le role de deploiement)
#   3. un parcours complet: octroi -> confirmation -> revocation
#
# Toutes les identites sont FICTIVES. Aucune confirmation reelle n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"
DB="${1:?usage: nonsuperuser_install.sh <nom-de-base-jetable>}"

if ! [[ "$DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ ]]; then
  echo "      ECHEC: nom de base « $DB » invalide" >&2
  exit 2
fi

# Roles du modele Supabase, recrees ici. `esc_migrator` tient le role de
# `postgres` chez Supabase: proprietaire du schema, CREATEROLE et CREATEDB,
# mais PAS superutilisateur et PAS bypassrls.
MIGRATEUR=esc_migrator
# LE PLAN DE CONTROLE, NON SUPERUTILISATEUR LUI AUSSI (6.3b6b).
#
# Ce fichier laissait la migration creer elle-meme les roles d'AUTORITE, sous
# le migrateur. Depuis la phase 2, cette forme n'est plus finalisable: par F1
# le migrateur serait son propre plan de controle, garderait l'ADMIN residuel
# par exemption, et pourrait donc se reaccorder SET quand il veut — la
# separation entre « qui migre » et « qui approuve » serait nominale.
#
# Le provisionnement passe donc a un SECOND role non superutilisateur. Ce
# n'est pas un recul sur le sujet du fichier: aucun des deux acteurs n'est
# superutilisateur, ce qui est exactement la forme Supabase. Le chemin
# greenfield, lui, reste exerce par `two_phase_deployment.sh` (configuration
# A), qui en fait son sujet au lieu d'en dependre.
PLAN=esc_control_plane
ROLES_SB="$MIGRATEUR $PLAN esc_authenticator esc_service_role"
CANONIQUES="eurostruct_normative_writer eurostruct_normative_bootstrap eurostruct_normative_activator eurostruct_deployment"
# LE SEPTIEME ROLE CANONIQUE. `eurostruct_authority_backend` est cree par la
# PHASE 0 depuis 6.3c: il doit donc etre exige absent AVANT, enregistre pour
# le demontage, et detruit APRES, exactement comme les six autres. Mesure du
# 26/08: il ne l'etait pas ici, et il survivait a ce harnais — les sept suites
# suivantes de `run.sh` refusaient alors de demarrer sur « ces roles existent
# deja ». Un role oublie dans une liste de demontage n'est pas un detail: il
# arrete tout ce qui vient apres.
SERVICES="normative_backend normative_governance eurostruct_authority_backend"
MDP='FICTIF-nonsuperuser'

# La connexion vient de l'ENVIRONNEMENT, jamais d'argv (6.3b6a, securite des
# harnais). La version precedente construisait
#
#     psql "postgresql://$MIGRATEUR:$MDP@$HOTE/$DB?sslmode=disable"
#
# — le mot de passe du migrateur, en clair, dans `argv`, donc lisible par tout
# processus de la machine. Elle reecrivait aussi `$DATABASE_URL` a la main pour
# changer de base, ce qui avait deja fait perdre l'hote et les identifiants une
# fois. Seule la base change desormais, par `-d`; le role et son mot de passe
# passent par l'environnement du seul appel concerne.
harnais_connexion || exit 2

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
exiger_precontrole_local "nonsuperuser_install.sh" || exit 2
harnais_verrou_prendre "nonsuperuser_install.sh" || exit $?   # 2 = parametre invalide, 3 = verrou detenu
exiger_cluster_jetable "nonsuperuser_install.sh" || exit 2

# DETRUIRE PAR NOM N'EST LEGITIME QU'APRES AVOIR PROUVE L'ABSENCE.
#
# `nettoyer()` faisait `drop owned by` puis `drop role if exists` sur trois
# noms FIXES du modele Supabase, et `liberer_autorites()` sur les trois roles
# canoniques — sans jamais verifier qu'ils venaient d'ici. Sur un cluster ou un
# `esc_service_role` appartenait a quelqu'un d'autre, il partait.
#
# On exige donc leur absence au demarrage. Tout role de ces listes present
# ensuite a ete cree par CETTE execution, et lui seul peut etre detruit.
# shellcheck disable=SC2086
exiger_roles_absents "nonsuperuser_install.sh" $ROLES_SB $CANONIQUES $SERVICES \
  "${HARNAIS_ROLES_STUB[@]}" || exit 2


ADMIN=(psql -X -q -d postgres)
ADMIN_DB=(psql -X -q -d "$DB")
MIG=(psql -X -d "$DB")

KO=0
echoue() { echo "      ECHEC: $*"; KO=1; }

# Le migrateur se connecte avec SON mot de passe, jamais celui de
# l'environnement. En CI, `PGPASSWORD` porte celui de l'administrateur: il
# etait donc presente a l'authentification d'`esc_migrator` et refuse
# (« password authentication failed »). En local l'authentification est
# `trust`, si bien que la variable n'etait jamais lue et que le defaut restait
# invisible — la meme asymetrie CI/local que ce fichier existe pour reduire.
mig() { PGUSER="$MIGRATEUR" PGPASSWORD="$MDP" "${MIG[@]}" "$@"; }

NETTOYAGE_KO=0
nettoyer() {
  # LA BASE D'ABORD: `DROP OWNED BY` ne voit que la base courante, et les roles
  # d'autorite possedent des fonctions dans celle-ci. L'ordre inverse echouait,
  # et l'echec etait masque.
  "${ADMIN[@]}" -q -c "
    select pg_terminate_backend(pid) from pg_stat_activity
     where datname = '$DB' and pid <> pg_backend_pid();" >/dev/null 2>&1
  "${ADMIN[@]}" -q -c "drop database if exists $DB;" >/dev/null 2>&1
  local r
  for r in $ROLES_SB $SERVICES; do
    "${ADMIN[@]}" -q -c "reassign owned by $r to ${PGUSER:-postgres};" >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop owned by $r;" >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
  liberer_autorites
  for r in "${HARNAIS_ROLES_STUB[@]}"; do
    "${ADMIN[@]}" -q -c "drop owned by \"$r\";"      >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
  # shellcheck disable=SC2086
  harnais_postcondition_nettoyage "nonsuperuser_install.sh" $ROLES_SB $CANONIQUES $SERVICES \
    "${HARNAIS_ROLES_STUB[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
registre_base "$DB"
trap nettoyer EXIT
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

echo "    installation sous un role de migration non superutilisateur"

# --------------------------------------------------------------------------
# 1. Le modele de privileges de la cible
# --------------------------------------------------------------------------
"${ADMIN[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role $MIGRATEUR login password '$MDP' createrole createdb;
-- LE PLAN DE CONTROLE: non superutilisateur lui aussi, CREATEROLE seulement.
-- Il provisionne les roles d'autorite et exercera la phase 2; il n'a besoin
-- ni de CREATEDB ni d'aucun autre attribut.
create role $PLAN login password '$MDP' createrole;
create role esc_service_role nologin;
create role esc_authenticator login password '$MDP';
grant esc_service_role to esc_authenticator;
SQL
[[ $? -eq 0 ]] || { echoue "creation des roles du modele impossible"; exit 1; }

# La verification qui donne son sens a tout le reste: le migrateur n'est PAS
# superutilisateur. Sans elle, ce fichier pourrait tourner en superutilisateur
# et tout valider sans rien prouver.
ATTRS=$("${ADMIN[@]}" -X -q -tAc "
  select rolsuper::text || '/' || rolbypassrls::text || '/' ||
         rolcreaterole::text || '/' || rolcreatedb::text
    from pg_roles where rolname = '$MIGRATEUR'")
if [[ "$ATTRS" != "false/false/true/true" ]]; then
  echoue "le migrateur n'a pas le profil attendu (super/bypassrls/createrole/createdb = $ATTRS)"
  exit 1
fi
echo "      ok: migrateur non superutilisateur, sans bypassrls (createrole+createdb)"

# ET LE PLAN DE CONTROLE NON PLUS. Si l'un des deux acteurs etait
# superutilisateur, ce fichier ne prouverait plus ce que son nom annonce.
ATTRS_PLAN=$("${ADMIN[@]}" -X -q -tAc "
  select rolsuper::text || '/' || rolbypassrls::text || '/' || rolcreaterole::text
    from pg_roles where rolname = '$PLAN'")
if [[ "$ATTRS_PLAN" != "false/false/true" ]]; then
  echoue "le plan de controle n'a pas le profil attendu (super/bypassrls/createrole = $ATTRS_PLAN)"
  exit 1
fi
echo "      ok: plan de controle non superutilisateur (createrole)"

# --------------------------------------------------------------------------
# 2. La base appartient au migrateur, comme en deploiement gere
# --------------------------------------------------------------------------
"${ADMIN[@]}" -q -v ON_ERROR_STOP=1 -c \
  "create database $DB owner $MIGRATEUR;" >/dev/null 2>&1 \
  || { echoue "creation de la base impossible"; exit 1; }

# Le stub `auth` est pose par l'admin puis DONNE au migrateur: chez Supabase
# le schema `auth` preexiste et n'appartient pas au role de migration.
"${ADMIN_DB[@]}" -q -v ON_ERROR_STOP=1 \
  -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1 \
  || { echoue "stub auth impossible"; exit 1; }
"${ADMIN_DB[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant usage on schema auth to $MIGRATEUR;
-- REFERENCES et pas seulement SELECT: le schema declare des cles etrangeres
-- vers auth.users, et PostgreSQL exige REFERENCES pour en creer une. C'est le
-- premier obstacle qu'un role non superutilisateur rencontre, et la CI
-- superutilisateur ne pouvait pas le voir. Chez Supabase le role de migration
-- detient bien ce droit — creer une FK vers auth.users y est l'usage courant.
-- WITH GRANT OPTION: la migration doit pouvoir RETRANSMETTRE ces droits aux
-- roles d'autorite. Sans le grant option, PostgreSQL n'echoue pas — il emet
-- un avertissement et n'accorde rien — et la chaine casse bien plus tard.
grant usage on schema auth to $MIGRATEUR with grant option;
grant select, insert, references on auth.users to $MIGRATEUR with grant option;
grant execute on function auth.uid() to $MIGRATEUR with grant option;
grant create on database $DB to $MIGRATEUR;
SQL

# LES DECLARATIONS DE DEPLOIEMENT, POSEES AVANT LA FINALISATION.
#
# La phase 2 les FIGE (`normative_approved_settings`), et la topologie les lit
# ensuite la et non plus dans le catalogue. Une declaration posee APRES
# l'activation n'a donc plus aucun effet — c'est le but, et c'est pourquoi
# `approved_service_logins` remonte ici depuis la section 5: le migrateur y
# recoit `normative_backend`, et sans declaration figee la topologie le
# refuserait a juste titre.
"${ADMIN[@]}" -q -c \
  "alter database $DB set eurostruct.approved_deployment_roles = '$MIGRATEUR,$PLAN';" \
  >/dev/null 2>&1
"${ADMIN[@]}" -q -c \
  "alter database $DB set eurostruct.approved_service_logins = '$MIGRATEUR';" \
  >/dev/null 2>&1

# PRECONDITION DE CE FICHIER, DESORMAIS DITE (6.3b6a).
#
# Ce test suppose que les ROLES DE SERVICE preexistent, crees par un
# superutilisateur. Il ne le declarait pas, et cette dependance etait
# satisfaite par accident: `run.sh` cree la base principale sous `postgres`
# AVANT d'arriver ici, ce qui cree `normative_backend` et
# `normative_governance` avec `postgres` pour createur.
#
# MESURE: execute seul sur une instance ou ces roles n'existent pas, ce fichier
# echoue des la premiere migration — le migrateur, CREATEROLE, devient membre
# des roles de service qu'il cree, et le prerequis « un role privilegie ne doit
# pas atteindre un role de service » refuse. « Installation non
# superutilisateur verifiee » etait donc vrai DANS L'ORDRE DE LA SUITE, et
# faux hors de lui. Une precondition tacite est une garantie qui n'en est pas
# une.
#
# Elle est donc CONSTATEE ici, et le chemin greenfield complet — celui ou rien
# ne preexiste — est exerce par `two_phase_deployment.sh`, qui en fait son
# sujet au lieu d'en dependre.
#
# Les roles d'AUTORITE, eux, ne doivent PAS preexister: la migration les cree.
# PostgreSQL 16 donne alors au createur une appartenance dont le donneur est le
# superutilisateur d'amorcage — appartenance que le migrateur ne peut PAS
# retirer lui-meme (« role X has not been granted membership in role Y by role
# X », reponse « REVOKE ROLE », et la ligne survit). C'est la raison d'etre de
# la phase de finalisation.
liberer_autorites() {
  local r
  # Legitime parce que `exiger_roles_absents` a PROUVE leur absence au
  # demarrage: ceux qui existent maintenant viennent de cette execution.
  for r in $CANONIQUES; do
    "${ADMIN[@]}" -q -c "drop owned by $r;" >/dev/null 2>&1
    "${ADMIN[@]}" -q -c "drop role if exists $r;" >/dev/null 2>&1
  done
}

# LE DECOR EST CONSTRUIT ICI, PLUS SUBI.
#
# Ce fichier supposait les ROLES DE SERVICE deja crees par un superutilisateur,
# et la supposition etait satisfaite par accident: `run.sh` creait la base
# principale — donc ces roles — a une etape anterieure. « Installation non
# superutilisateur verifiee » etait vrai DANS L'ORDRE DE LA SUITE, et faux hors
# de lui; execute seul sur une instance vierge, ce fichier echouait des la
# premiere migration.
#
# Depuis que les etapes exigeant un jeu canonique vierge passent en premier, la
# supposition n'est meme plus satisfaite par accident. Le decor est donc POSE
# ICI, par l'administrateur — ce qui est exactement le modele documente:
# provisionnement par un superutilisateur, migration par un non
# superutilisateur.
for r in $SERVICES; do
  "${ADMIN[@]}" -q -v ON_ERROR_STOP=1 -c "create role $r nologin;" >/dev/null 2>&1 \
    || { echoue "creation du role de service « $r » impossible"; exit 1; }
done
echo "      ok: decor — roles de service crees par l'administrateur"

# LE BLOC DE DESTRUCTION PAR MOTIF A ETE RETIRE.
#
# Il cherchait, via `pg_shdepend`, les bases dont les roles canoniques
# dependaient, filtrait sur `datname like 'eurostruct%'` et les DETRUISAIT.
# Un motif ne designe pas ce que cette execution a cree: il designe tout ce
# qui porte le prefixe — une base d'un collegue, d'un projet voisin, d'une
# execution concurrente.
#
# Il n'est plus necessaire: `exiger_roles_absents` ci-dessus garantit que les
# roles canoniques n'existent pas au demarrage, donc qu'aucune base ne depend
# d'eux, donc qu'il n'y a rien a liberer.

RESTE=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_roles
   where rolname in ('eurostruct_normative_writer',
                     'eurostruct_normative_bootstrap')")
if [[ "$RESTE" != "0" ]]; then
  echoue "les roles d'autorite preexistent et n'ont pas pu etre detruits:"
  echoue "  le decor de provisionnement ne peut pas etre pose"
  exit 1
fi

# LE PLAN DE CONTROLE PROVISIONNE LES ROLES D'AUTORITE.
#
# C'est lui, et lui seul, qui pourra revoquer les emprunts (fait F3): le
# donneur est inscrit par PostgreSQL dans `pg_auth_members` et personne ne
# peut le reecrire. Il conserve en echange un ADMIN residuel irrevocable
# (fait F1) — le seul que le modele tolere, et seulement une fois fige.
"${ADMIN[@]}" -q -v ON_ERROR_STOP=1 -c \
  "grant $PLAN to ${PGUSER:-postgres};" >/dev/null 2>&1
# LA PHASE 0 — LE SCEAU (6.3b6c). Ce n'est plus un `create role` a la main:
# c'est `db/control_plane/0001_normative_seal.sql`, applique PAR LE PLAN DE CONTROLE,
# les six roles canoniques ET la racine de confiance — les quatre tables que
# le migrateur ne doit jamais posseder ni pouvoir endosser.
"${ADMIN_DB[@]}" -q >/dev/null 2>&1 <<SQL
grant create on schema public to $PLAN with grant option;
grant usage on schema auth to $PLAN;
SQL
PLAN_DB0=(env PGUSER="$PLAN" PGPASSWORD="$MDP" psql -X -q -d "$DB")
if ! sortie=$("${PLAN_DB0[@]}" -v ON_ERROR_STOP=1 \
                -f "$HARNAIS_SCEAU" 2>&1); then
  echoue "la phase 0 a echoue sous « $PLAN »:"
  grep -m2 -E "ERROR|FATAL" <<<"$sortie" | sed 's/^/              /'
  exit 1
fi
# L'EMPRUNT: DEUX ROLES, jamais l'activateur.
PLAN_PSQL=(env PGUSER="$PLAN" PGPASSWORD="$MDP" psql -X -q -d postgres)
"${PLAN_PSQL[@]}" -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to $MIGRATEUR with admin option;
grant eurostruct_normative_bootstrap to $MIGRATEUR with admin option;
SQL
# LE CONTROLE PORTE SUR LES NOMS, PAS SUR UN COMPTE (6.3b6d).
#
# Il comparait a « 4 », ecrit en dur. L'arrivee de `normative_seal_metadata`
# — cinquieme table de confiance — a fait echouer ce controle sur « 5 tables
# sur 4 », alors que le sceau etait exactement ce qu'il devait etre. Un compte
# fige transforme toute evolution correcte en panne, et ne dit jamais QUOI
# manque.
PROVISION=$("${ADMIN_DB[@]}" -X -q -tAc "
  select coalesce(string_agg(t.nom, ', ' order by t.nom), '')
    from unnest(array['normative_control_plane','normative_activation',
                      'normative_approved_settings',
                      'normative_finalization_intent',
                      'normative_seal_metadata']) as t(nom)
   where not exists (
     select 1 from pg_class c join pg_roles o on o.oid = c.relowner
      where c.relname = t.nom
        and o.rolname = 'eurostruct_normative_activator'
        and c.relrowsecurity and c.relforcerowsecurity)")
if [[ -n "$PROVISION" ]]; then
  echoue "le sceau est incomplet: $PROVISION ne sont pas possedees par"
  echoue "l'activateur avec RLS forcee"
  exit 1
fi
# Il exercera la phase 2: il lui faut le role de deploiement, et il est
# declare ci-dessus dans `approved_deployment_roles`.
"${ADMIN[@]}" -q -c "grant eurostruct_deployment to $PLAN with inherit true;" \
  >/dev/null 2>&1
echo "      ok: phase 0 — sceau pose par « $PLAN », toutes les tables de confiance"

# --------------------------------------------------------------------------
# 3. Les migrations, appliquees PAR LE MIGRATEUR
# --------------------------------------------------------------------------
# La connexion du migrateur d'abord, et SEULE. Sans ce controle, un echec
# d'authentification se presentait comme « 0001_init.sql refusee sous un role
# non superutilisateur » — un diagnostic qui accuse la migration alors que le
# probleme est le raccordement du test.
if ! sonde=$(mig -X -q -tAc 'select current_user' 2>&1); then
  echoue "le migrateur ne peut pas se connecter:"
  sed 's/^/              /' <<<"$sonde" | head -2
  exit 1
fi
echo "      ok: le migrateur se connecte ($sonde)"


for f in "$DB_DIR"/migrations/*.sql; do
  if ! esc_appliquer_migration "$f" mig -q; then
    out="$ESC_MIGRATION_SORTIE"
    echoue "$(basename "$f") refusee sous un role non superutilisateur:"
    grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$out" | sed 's/^/              /'
    exit 1
  fi
done
echo "      ok: 0001 a 0010 appliquees par un role non superutilisateur"

# --------------------------------------------------------------------------
# 3bis. LA PHASE 2, exercee par le plan de controle
# --------------------------------------------------------------------------
# LA MIGRATION NE REND PLUS L'EMPRUNT, ET C'EST LE SUJET DE 6.3b6b.
#
# Ce bloc exigeait « 0 membre d'autorite apres la migration seule ». C'etait
# exiger l'impossible: par le fait F2 — mesure — un role ne peut PAS revoquer
# une appartenance qu'un autre lui a donnee, ni directement ni par
# « GRANTED BY ». La migration se refusait donc elle-meme, ou mentait.
#
# La restitution appartient au DONNEUR. Elle a lieu ici, en phase 2, et
# l'invariant est verifie APRES — la ou il peut etre vrai.
ETAT=$(mig -X -q -tAc 'select normative_activation_state()' 2>&1)
if [[ "$ETAT" != "PENDING" ]]; then
  echoue "la phase 1 ne se termine pas en PENDING (obtenu: $ETAT)"
  exit 1
fi
echo "      ok: phase 1 terminee, etat PENDING"

PLAN_DB=(env PGUSER="$PLAN" PGPASSWORD="$MDP" psql -X -q -d "$DB")
MANIF=$("${PLAN_DB[@]}" -tAc 'select normative_settings_manifest()' 2>&1)
FIN=$("${PLAN_DB[@]}" -tAc "select normative_finalize_deployment('$MANIF')" 2>&1)
ETAT=$("${PLAN_DB[@]}" -tAc 'select normative_activation_state()' 2>&1)
if [[ "$ETAT" != "ACTIVE" ]]; then
  echoue "la finalisation par « $PLAN » a echoue (etat $ETAT):"
  grep -m2 -E "ERROR|DETAIL|FATAL" <<<"$FIN" | sed 's/^/              /'
  exit 1
fi
echo "      ok: phase 2 par « $PLAN » — etat ACTIVE"

# L'EMPRUNT A BIEN ETE RENDU. La propriete que la phase 2 achete, constatee
# apres coup et non supposee. Les trois capacites, pas seulement MEMBER: un
# ADMIN residuel se reaccorde SET quand il veut.
MEMBRES=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_roles autorite
   where autorite.rolname in ('eurostruct_normative_writer',
                              'eurostruct_normative_bootstrap',
                              'eurostruct_normative_activator')
     and (pg_has_role('$MIGRATEUR', autorite.rolname, 'SET')
          or pg_has_role('$MIGRATEUR', autorite.rolname, 'USAGE')
          or pg_has_role('$MIGRATEUR', autorite.rolname, 'MEMBER WITH ADMIN OPTION'))")
if [[ "$MEMBRES" != "0" ]]; then
  echoue "le migrateur conserve $MEMBRES capacite(s) sur les roles d'autorite"
  echoue "  APRES la finalisation: il peut encore forger une origine normative."
else
  echo "      ok: 0 capacite du migrateur sur les roles d'autorite apres phase 2"
fi

# --------------------------------------------------------------------------
# 4. L'amorcage, par l'ACL explicite
# --------------------------------------------------------------------------
# D'ABORD le refus: sans rattachement au role de deploiement, le migrateur ne
# peut pas amorcer. Sans cette moitie, l'ACL ne prouverait rien.
REFUS=$(mig -X -q -tAc "
  select bootstrap_normative_administrator(
    '11111111-1111-1111-1111-111111111111', 'FICTIF Racine',
    'FICTIF — amorcage sans rattachement.')" 2>&1)
if ! grep -q "permission denied\|droit refuse" <<<"$REFUS"; then
  echoue "l'amorcage a ete accepte SANS rattachement au role de deploiement"
  echo "              obtenu: $(head -1 <<<"$REFUS")"
else
  echo "      ok: amorcage refuse tant que le role de deploiement n'est pas accorde"
fi

"${ADMIN[@]}" -q -c "grant eurostruct_deployment to $MIGRATEUR;" >/dev/null 2>&1

AMORCAGE=$(mig -q -v ON_ERROR_STOP=1 2>&1 <<'SQL'
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'FICTIF-ns-admin@eurostruct.test'),
  ('22222222-2222-2222-2222-222222222222', 'FICTIF-ns-verif@eurostruct.test')
on conflict do nothing;
select bootstrap_normative_administrator(
  '11111111-1111-1111-1111-111111111111', 'FICTIF Racine Non-Super',
  'FICTIF — amorcage sous role de migration non superutilisateur.');
SQL
)
if grep -q "ERROR" <<<"$AMORCAGE"; then
  echoue "l'amorcage a echoue APRES rattachement au role de deploiement:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$AMORCAGE" | sed 's/^/              /'
else
  echo "      ok: amorcage reussi via eurostruct_deployment"
fi

# Et le role de deploiement n'a pas gagne l'autorite au passage.
if [[ "$("${ADMIN[@]}" -X -q -tAc "
      select (pg_has_role('eurostruct_deployment',
                          'eurostruct_normative_writer', 'MEMBER') or
              pg_has_role('eurostruct_deployment',
                          'eurostruct_normative_bootstrap', 'MEMBER'))::text")" \
     != "false" ]]; then
  echoue "eurostruct_deployment est membre d'un role d'autorite"
else
  echo "      ok: le role de deploiement n'est membre d'aucun role d'autorite"
fi

# --------------------------------------------------------------------------
# 5. Le parcours complet: octroi -> confirmation -> revocation
# --------------------------------------------------------------------------
# Sous le role de service, pas sous le migrateur: c'est le chemin d'ecriture
# reel. Le migrateur s'y rattache le temps du test, ce qu'un deploiement fait
# de toute facon pour son backend.
"${ADMIN[@]}" -q -c "grant normative_backend to $MIGRATEUR;" >/dev/null 2>&1
# `authenticated` sert au controle de RLS plus bas: le migrateur doit pouvoir
# l'endosser pour verifier ce que voit un porteur de jeton.
"${ADMIN[@]}" -q -c "grant authenticated to $MIGRATEUR;" >/dev/null 2>&1
# Et le role de service a besoin du schema `auth`: la verification d'une cle
# etrangere vers auth.users s'execute avec les droits de l'appelant sur le
# schema, meme si le declencheur normatif, lui, est SECURITY DEFINER.
"${ADMIN_DB[@]}" -q -c   "grant usage on schema auth to normative_backend, authenticated;
   grant select on auth.users to normative_backend, authenticated;"   >/dev/null 2>&1
# `approved_service_logins` est declare AVANT la finalisation (section 2): pose
# ici, il serait sans effet — la topologie lit desormais la valeur FIGEE.

PARCOURS=$(mig -X -q -tAc "
set role normative_backend;
select set_config('request.jwt.claim.sub',
                  '11111111-1111-1111-1111-111111111111', true);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   edition, reason)
values ('22222222-2222-2222-2222-222222222222', 'FICTIF Relecteur Non-Super',
        'can_validate_normative_reference', 'BE', 'EN 1992', '1-1', '2010',
        'FICTIF — habilitation du parcours non superutilisateur.');
select set_config('request.jwt.claim.sub',
                  '22222222-2222-2222-2222-222222222222', true);
insert into normative_rule_confirmations (
  country_code, standard_family, part, rule_id,
  stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
  digest_algorithm, canonicalization_version,
  normative_spec_payload, implementation_payload, evidence_payload,
  stack_payload, stack_snapshot, annex_edition, evidence_items, statement,
  verifier_id, verifier_name, verified_at, authorisation_grant_id,
  authorisation_scope, idempotency_key)
select 'BE', 'EN 1992', '1-1', 'test.nonsuperuser',
  encode(sha256(convert_to(pile, 'UTF8')), 'hex'),
  encode(sha256(convert_to(spec, 'UTF8')), 'hex'),
  encode(sha256(convert_to(impl, 'UTF8')), 'hex'),
  encode(sha256(convert_to(ev,   'UTF8')), 'hex'),
  'sha256', 'esc-canon/1', spec, impl, ev, pile, '{}'::jsonb, 'x',
  '[]'::jsonb, 'FICTIF — lecture sous role non superutilisateur.',
  '00000000-0000-0000-0000-000000000000', 'FICTIF', now(), null, '{}'::jsonb,
  'FICTIF-nonsuper-1'
from (select
  '{\"canonicalization_version\":\"esc-canon/1\",\"kind\":\"normative_spec\",\"rule_id\":\"test.nonsuperuser\"}' as spec,
  '{\"canonicalization_version\":\"esc-canon/1\",\"kind\":\"implementation\",\"rule_id\":\"test.nonsuperuser\"}' as impl,
  '{\"canonicalization_version\":\"esc-canon/1\",\"items\":[{\"clause\":\"c\",\"document_digest\":\"' || repeat('b',64) || '\",\"document_role\":\"annexe\",\"edition\":\"2010\",\"page_printed\":1,\"quote\":\"FICTIF\",\"quote_digest\":\"' || encode(sha256(convert_to('FICTIF','UTF8')),'hex') || '\",\"reference\":\"FICTIF ANB\"}],\"kind\":\"evidence\"}' as ev,
  '{\"components\":[{\"application_order\":2,\"document_digest\":\"' || repeat('b',64) || '\",\"edition\":\"2010\",\"reference\":\"FICTIF ANB\",\"role\":\"annexe\"}],\"country_code\":\"BE\",\"kind\":\"normative_stack\",\"part\":\"1-1\",\"schema_version\":\"esc-stack/1\",\"standard_family\":\"EN 1992\"}' as pile
) p;
select count(*) from normative_rule_confirmations
 where idempotency_key = 'FICTIF-nonsuper-1';
" 2>&1)

if [[ "$(tail -1 <<<"$PARCOURS")" != "1" ]]; then
  echoue "le parcours octroi -> confirmation a echoue:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$PARCOURS" | sed 's/^/              /'
else
  echo "      ok: octroi puis confirmation sous le role de service"
fi

# Revocation de la confirmation, par son auteur.
REVOC=$(mig -X -q -tAc "
set role normative_backend;
select set_config('request.jwt.claim.sub',
                  '22222222-2222-2222-2222-222222222222', true);
insert into normative_rule_confirmation_revocations (confirmation_id, reason)
select id, 'FICTIF — retrait de ma propre lecture.'
  from normative_rule_confirmations
 where idempotency_key = 'FICTIF-nonsuper-1';
select count(*) from normative_rule_confirmation_revocations;" 2>&1)

if [[ "$(tail -1 <<<"$REVOC")" != "1" ]]; then
  echoue "la revocation de confirmation a echoue:"
  grep -m2 -E "ERROR|DETAIL|FATAL|psql: error" <<<"$REVOC" | sed 's/^/              /'
else
  echo "      ok: revocation de la confirmation par son auteur"
fi

# Et la RLS s'applique reellement: sans bypassrls, un porteur de jeton tiers
# ne voit pas la confirmation d'autrui. Ce controle ne vaut QUE sous un role
# non superutilisateur — c'est tout l'objet de ce fichier.
VU=$(mig -X -q -tAc "
set role authenticated;
select set_config('request.jwt.claim.sub',
                  '11111111-1111-1111-1111-111111111111', true);
select count(*) from normative_rule_confirmations;" 2>&1 | tail -1)
if [[ "$VU" != "0" ]]; then
  echoue "RLS PERCEE hors superutilisateur: un tiers voit $VU confirmation(s)"
else
  echo "      ok: RLS effective sous un role sans bypassrls"
fi

echo ''
echo '================================================='
echo ' Installation non superutilisateur verifiee.'
echo '================================================='
exit $KO
