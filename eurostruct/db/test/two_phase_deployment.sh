#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6a: LE DEPLOIEMENT EN DEUX PHASES, ET CE QUI LE REND
#                      NECESSAIRE
#
#   two_phase_deployment.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# Que l'installation en UNE phase — un migrateur non superutilisateur qui fait
# tout — ne peut PAS aboutir a une topologie saine, et que ce qui en decide est
# QUI A CREE LES ROLES et QUI A ACCORDE LES APPARTENANCES.
#
# Ce n'etait, jusqu'ici, pas teste directement. La propriete se manifestait par
# la rupture indirecte de `nonsuperuser_install.sh`, qui teste tout autre
# chose: un lecteur voyait « l'installation non superutilisateur est rouge »
# sans pouvoir en deduire ce qui est en cause, et n'importe quelle autre
# regression de ce fichier aurait produit le meme symptome. Un rouge qui ne
# discrimine pas ne prouve rien.
#
# LES TROIS FAITS DE POSTGRESQL 16 QUI COMMANDENT TOUT
# -----------------------------------------------------
# MESURES sur l'instance, a chaque execution, par le bloc « oracles » ci-
# dessous. Ils ne sont pas supposes, et s'ils changent, ce fichier le dit.
#
#   F1. Quand un role en CREE un autre, PostgreSQL lui accorde d'office une
#       appartenance dont le DONNEUR est le superutilisateur d'amorcage
#       (grantor = postgres, admin = true, set = false).
#
#   F2. Un role ne peut JAMAIS revoquer sa propre appartenance quand le donneur
#       est un autre role — meme avec ADMIN OPTION, meme avec « GRANTED BY ».
#       `REVOKE` emet un simple AVERTISSEMENT et la ligne survit.
#
#   F3. Le DONNEUR, lui, revoque ce qu'il a donne.
#
# CE QU'ILS IMPLIQUENT, ET QUI N'AVAIT PAS ETE VU
# ------------------------------------------------
# La migration empruntait l'appartenance aux roles d'autorite le temps des
# transferts de propriete, puis pretendait la RENDRE elle-meme — « restitution
# inconditionnelle ou refus ». Par F2, c'est IMPOSSIBLE des lors que
# l'appartenance vient d'ailleurs que du migrateur lui-meme. La restitution
# n'appartient donc pas a la migration: elle appartient a une phase de
# FINALISATION, exercee par le donneur.
#
# C'est exactement le deploiement en deux phases, et c'est ce fichier qui en
# porte la demonstration.
#
# LES TROIS CONFIGURATIONS, une variable a la fois
# -------------------------------------------------
#   A. GREENFIELD, MIGRATEUR SEUL. Rien n'est prepare; la migration cree tous
#      les roles. Par F1 le migrateur — privilegie, CREATEROLE — devient membre
#      des roles de SERVICE.
#      ATTENDU: REFUS. Un role qui contourne la RLS ne doit pas heriter des
#      droits d'ecriture normatifs.
#
#   B. PROVISIONNEMENT PAR UN SUPERUTILISATEUR. Tous les roles preexistent,
#      crees par le superutilisateur; le migrateur recoit l'appartenance aux
#      deux roles d'autorite WITH ADMIN OPTION.
#      ATTENDU A TERME: installation, puis finalisation par le donneur.
#      ATTENDU AUJOURD'HUI: refus a la restitution (F2) — la migration ne peut
#      pas rendre ce qu'elle n'a pas donne.
#
#   C. PROVISIONNEMENT PAR UN PLAN DE CONTROLE NON SUPERUTILISATEUR — la forme
#      Supabase, ou le client n'a pas de superutilisateur. Par F1 le plan de
#      controle conserve un ADMIN residuel IRREVOCABLE sur tout ce qu'il a
#      cree, y compris les roles de service.
#      ATTENDU A TERME: installation, plan de controle FIGE depuis le donneur,
#      exemption d'un seul ADMIN residuel nomme.
#      ATTENDU AUJOURD'HUI: refus — rien n'ecrit encore dans
#      `normative_control_plane`.
#
# B et C sont donc ROUGES ICI, nommement, avec leur diagnostic. Ils deviendront
# verts sans que ce fichier soit reecrit: c'est l'objet de 6.3b6b.
#
# Toutes les identites sont FICTIVES. Aucune confirmation reelle n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
PREFIXE="${1:?usage: two_phase_deployment.sh <prefixe-de-base-jetable>}"

if ! [[ "$PREFIXE" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,40}$ ]]; then
  echo "      ECHEC: prefixe « $PREFIXE » invalide" >&2
  exit 2
fi

# Ces mots de passe ne servent qu'a des roles jetables, sur cette instance de
# test, et n'ouvrent rien d'autre. Ils ne transitent jamais par argv.
MIGRATEUR="${PREFIXE}_mig"; MIG_MDP='FICTIF-2p-mig'
PLAN="${PREFIXE}_ctl";      PLAN_MDP='FICTIF-2p-ctl'

AUTORITES=(eurostruct_normative_writer eurostruct_normative_bootstrap)
SERVICES=(normative_backend normative_governance)
DEPLOIEMENT=eurostruct_deployment

if [[ -n "${DATABASE_URL:-}" ]]; then
  SANS_QUERY="${DATABASE_URL%%\?*}"; BASE_URL="${SANS_QUERY%/*}"
  ADMIN=(psql "$DATABASE_URL")
  HOTE="$(sed -E 's|^[^:]+://||; s|^[^@]*@||; s|/.*$||' <<<"$BASE_URL")"
  admin_db() { local b="$1"; shift; psql "${BASE_URL}/${b}" "$@"; }
else
  ADMIN=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d postgres)
  HOTE=127.0.0.1
  admin_db() { local b="$1"; shift
    psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$b" "$@"; }
fi
PROPRIETAIRE="${PGUSER:-postgres}"

ECHECS=0; ROUGES_ATTENDUS=0
echoue() { echo "      ECHEC: $*" >&2; ECHECS=$((ECHECS + 1)); }
attendu_rouge() { echo "      ATTENDU-ROUGE (6.3b6b): $*"; }

mig()  { local b="$1"; shift; PGPASSWORD="$MIG_MDP"  psql -X -h "$HOTE" -U "$MIGRATEUR" -d "$b" "$@"; }
plan() { local b="$1"; shift; PGPASSWORD="$PLAN_MDP" psql -X -h "$HOTE" -U "$PLAN"      -d "$b" "$@"; }

# --------------------------------------------------------------------------
# Remise a zero. Les roles sont GLOBAUX a l'instance et survivent aux bases:
# sans ce nettoyage, une configuration heriterait des roles de la precedente et
# ne testerait plus la variable qu'elle isole.
# --------------------------------------------------------------------------
raz() {
  local b r
  for b in "${PREFIXE}_a" "${PREFIXE}_b" "${PREFIXE}_c"; do
    "${ADMIN[@]}" -X -q -c "drop database if exists $b;" >/dev/null 2>&1
  done
  for r in "${AUTORITES[@]}" "${SERVICES[@]}" "$DEPLOIEMENT" "$MIGRATEUR" "$PLAN"; do
    "${ADMIN[@]}" -X -q -c "drop owned by \"$r\" cascade;" >/dev/null 2>&1
    "${ADMIN[@]}" -X -q -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}
trap raz EXIT
raz

RESTE=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_roles
   where rolname in ('${AUTORITES[0]}','${AUTORITES[1]}',
                     '${SERVICES[0]}','${SERVICES[1]}','$DEPLOIEMENT')")
if [[ "$RESTE" != "0" ]]; then
  echo "      ECHEC: $RESTE role(s) normatif(s) preexistent et n'ont pas pu" >&2
  echo "              etre detruits: aucune configuration n'isolerait sa" >&2
  echo "              variable, et ce fichier ne prouverait rien." >&2
  exit 1
fi

echo "    deploiement en deux phases: qui cree, qui accorde, qui revoque"

# --------------------------------------------------------------------------
# ORACLES — les trois faits de PostgreSQL 16, MESURES et non supposes
# --------------------------------------------------------------------------
# Toute l'architecture en depend. S'ils changent — nouvelle version majeure,
# fournisseur qui patche — ce n'est pas une bonne nouvelle a ignorer: c'est un
# reexamen a ouvrir, et il vaut mieux l'apprendre ici qu'en production.
"${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role "$MIGRATEUR" login password '$MIG_MDP' createrole createdb;
create role "$PLAN"      login password '$PLAN_MDP' createrole;
SQL

# F1 — le createur recoit une appartenance donnee par le superutilisateur.
mig postgres -q -c "create role ${PREFIXE}_f1 nologin;" >/dev/null 2>&1
LU=$("${ADMIN[@]}" -X -q -tAc "
  select g.rolname || '/' || m.admin_option || '/' || m.set_option
    from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
    join pg_roles g on g.oid = m.grantor
   where a.rolname = '${PREFIXE}_f1' and p.rolname = '$MIGRATEUR'")
# `boolean || text` rend « true »/« false », et non « t »/« f » — ce que
# l'affichage tabulaire de psql donne. La premiere ecriture attendait la forme
# tabulaire et rapportait un changement de F1 qui n'avait pas eu lieu.
if [[ "$LU" == "$PROPRIETAIRE/true/false" ]]; then
  echo "      ok: F1 — le createur recoit admin=t set=f, donne par $PROPRIETAIRE"
else
  echoue "F1 a change: attendu « $PROPRIETAIRE/true/false », obtenu « ${LU:-aucune ligne} »."
  echoue "  Le fondement du deploiement en deux phases doit etre reexamine."
fi

# F2 — nul ne revoque sa propre appartenance donnee par un autre. Ni
# directement, ni par « GRANTED BY »: les deux sont exerces.
mig postgres -q -c "revoke ${PREFIXE}_f1 from \"$MIGRATEUR\";" >/dev/null 2>&1
mig postgres -q -c "revoke ${PREFIXE}_f1 from \"$MIGRATEUR\" granted by $PROPRIETAIRE;" >/dev/null 2>&1
SURVIT=$("${ADMIN[@]}" -X -q -tAc "
  select count(*) from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
   where a.rolname = '${PREFIXE}_f1' and p.rolname = '$MIGRATEUR'")
if [[ "$SURVIT" == "1" ]]; then
  echo "      ok: F2 — l'appartenance survit aux deux tentatives de revocation"
else
  echoue "F2 a change: le migrateur a pu revoquer une appartenance qu'il n'a"
  echoue "  pas donnee. La restitution par la migration redevient possible, et"
  echoue "  le decoupage en deux phases doit etre reexamine."
fi

# F3 — le donneur revoque ce qu'il a donne.
"${ADMIN[@]}" -X -q -c "create role ${PREFIXE}_f3 nologin;" >/dev/null 2>&1
"${ADMIN[@]}" -X -q -c "grant ${PREFIXE}_f3 to \"$MIGRATEUR\";" >/dev/null 2>&1
"${ADMIN[@]}" -X -q -c "revoke ${PREFIXE}_f3 from \"$MIGRATEUR\";" >/dev/null 2>&1
if [[ "$("${ADMIN[@]}" -X -q -tAc "
      select count(*) from pg_auth_members m
        join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
       where a.rolname = '${PREFIXE}_f3' and p.rolname = '$MIGRATEUR'")" == "0" ]]; then
  echo "      ok: F3 — le donneur revoque ce qu'il a donne"
else
  echoue "F3 a change: le donneur ne peut plus revoquer son propre octroi."
fi
"${ADMIN[@]}" -X -q -c "drop role if exists ${PREFIXE}_f1;" >/dev/null 2>&1
"${ADMIN[@]}" -X -q -c "drop role if exists ${PREFIXE}_f3;" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Application des migrations sous le migrateur. DIAG porte le premier
# diagnostic, tronque: on veut le motif, pas le fichier entier.
# --------------------------------------------------------------------------
DIAG=""
appliquer() {
  local base="$1" out f
  "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 \
    -c "create database $base owner \"$MIGRATEUR\";" >/dev/null || return 2
  admin_db "$base" -X -q -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admin_db "$base" -X -q >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIGRATEUR" with grant option;
grant select, insert, references on auth.users to "$MIGRATEUR" with grant option;
grant execute on function auth.uid() to "$MIGRATEUR" with grant option;
grant create on database $base to "$MIGRATEUR";
SQL
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! out=$(mig "$base" -q -v ON_ERROR_STOP=1 -f "$f" 2>&1); then
      DIAG="$(grep -m1 -E 'ERROR|FATAL' <<<"$out" | cut -c1-320)"
      return 1
    fi
  done
  DIAG=""; return 0
}

# ==========================================================================
# A — GREENFIELD, LE MIGRATEUR SEUL
# ==========================================================================
if appliquer "${PREFIXE}_a"; then
  echoue "A: la migration s'est INSTALLEE alors que le migrateur, privilegie,"
  echoue "  est membre des roles de service qu'il vient de creer (F1). Il"
  echoue "  contourne la RLS et herite en plus des droits d'ecriture normatifs."
elif grep -qE "prerequis non tenu: le role privilegie .* atteint le role de service" <<<"$DIAG"; then
  echo "      ok: A refusee — le migrateur privilegie atteint un role de service"
else
  echoue "A refusee, mais pas sur le motif attendu:"
  echo "              $DIAG" >&2
fi
raz; "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role "$MIGRATEUR" login password '$MIG_MDP' createrole createdb;
create role "$PLAN"      login password '$PLAN_MDP' createrole;
SQL

# ==========================================================================
# B — PROVISIONNEMENT PAR UN SUPERUTILISATEUR
# ==========================================================================
# Le superutilisateur cree TOUS les roles: par F1 c'est LUI qui garde l'ADMIN
# residuel, et le controle de topologie l'ignore — les superutilisateurs sont
# hors modele de menace, explicitement et depuis l'origine.
"${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role ${SERVICES[0]} nologin;
create role ${SERVICES[1]} nologin;
create role ${AUTORITES[0]} nologin;
create role ${AUTORITES[1]} nologin;
create role $DEPLOIEMENT nologin;
-- Le migrateur doit pouvoir transferer la propriete des fonctions: PostgreSQL
-- l'exige membre des roles d'autorite. ADMIN OPTION pour que la migration
-- puisse tenter la restitution — c'est precisement ce que F2 lui refuse.
grant ${AUTORITES[0]} to "$MIGRATEUR" with admin option;
grant ${AUTORITES[1]} to "$MIGRATEUR" with admin option;
SQL

if appliquer "${PREFIXE}_b"; then
  if TOPO=$(mig "${PREFIXE}_b" -q -tAc 'select assert_normative_topology()' 2>&1); then
    CAP=$("${ADMIN[@]}" -X -q -tAc "
      select count(*) from pg_roles a
       where a.rolname in ('${AUTORITES[0]}','${AUTORITES[1]}')
         and (pg_has_role('$MIGRATEUR', a.rolname, 'SET')
              or pg_has_role('$MIGRATEUR', a.rolname, 'USAGE')
              or pg_has_role('$MIGRATEUR', a.rolname, 'MEMBER WITH ADMIN OPTION'))")
    if [[ "$CAP" == "0" ]]; then
      echo "      ok: B installee, topologie acceptee, migrateur sans capacite"
    else
      echoue "B installee mais le migrateur conserve $CAP capacite(s) sur les"
      echoue "  roles d'autorite: il peut encore forger une origine normative."
    fi
  else
    echoue "B installee mais topologie refusee: $(head -1 <<<"$TOPO")"
  fi
# Le refus doit porter sur le SUJET: le migrateur, et un role d'autorite. Un
# motif fige ("appartenances UTILISABLES") designait un seul des blocs qui
# peuvent legitimement refuser, et le scenario passait au rouge imprevu des
# que l'autre parlait le premier.
elif grep -q "$MIGRATEUR" <<<"$DIAG" \
     && grep -qE "${AUTORITES[0]}|${AUTORITES[1]}" <<<"$DIAG"; then
  attendu_rouge "B refusee a la RESTITUTION, conformement a F2."
  attendu_rouge "  Le migrateur ne peut pas rendre une appartenance qu'il n'a"
  attendu_rouge "  pas donnee. La restitution appartient a la FINALISATION,"
  attendu_rouge "  exercee par le donneur — objet de 6.3b6b."
  attendu_rouge "  Diagnostic: $(cut -c1-150 <<<"$DIAG")"
  ROUGES_ATTENDUS=$((ROUGES_ATTENDUS + 1))
else
  echoue "B refusee pour un motif imprevu:"
  echo "              $DIAG" >&2
fi
raz; "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role "$MIGRATEUR" login password '$MIG_MDP' createrole createdb;
create role "$PLAN"      login password '$PLAN_MDP' createrole;
SQL

# ==========================================================================
# C — PROVISIONNEMENT PAR UN PLAN DE CONTROLE NON SUPERUTILISATEUR
# ==========================================================================
# La forme Supabase: le client ne dispose d'aucun superutilisateur. Par F1, le
# plan de controle garde un ADMIN residuel IRREVOCABLE sur tout ce qu'il cree.
# C'est la configuration que `normative_control_plane` existe pour rendre
# admissible — un seul ADMIN residuel, nomme, fige a l'installation.
"${ADMIN[@]}" -X -q -c "grant \"$PLAN\" to $PROPRIETAIRE;" >/dev/null 2>&1
plan postgres -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role ${SERVICES[0]} nologin;
create role ${SERVICES[1]} nologin;
create role ${AUTORITES[0]} nologin;
create role ${AUTORITES[1]} nologin;
create role $DEPLOIEMENT nologin;
grant ${AUTORITES[0]} to "$MIGRATEUR" with admin option;
grant ${AUTORITES[1]} to "$MIGRATEUR" with admin option;
SQL

DONNEUR=$("${ADMIN[@]}" -X -q -tAc "
  select g.rolname from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
    join pg_roles g on g.oid = m.grantor
   where a.rolname = '${AUTORITES[0]}' and p.rolname = '$MIGRATEUR' limit 1")
if [[ "$DONNEUR" == "$PLAN" ]]; then
  echo "      ok: C — le donneur de l'appartenance est le plan de controle"
else
  echoue "C: donneur attendu « $PLAN », obtenu « ${DONNEUR:-aucun} »: la"
  echoue "  configuration ne differe pas de B comme annonce."
fi

if appliquer "${PREFIXE}_c"; then
  if TOPO=$(mig "${PREFIXE}_c" -q -tAc 'select assert_normative_topology()' 2>&1); then
    FIGE=$(mig "${PREFIXE}_c" -q -tAc 'select normative_control_plane()' 2>&1)
    if [[ "$FIGE" == "$PLAN" ]]; then
      echo "      ok: C installee, plan de controle fige sur « $PLAN »"
    else
      echoue "C installee, topologie acceptee, mais le plan de controle fige"
      echoue "  est « ${FIGE:-NULL} » et non « $PLAN »: l'exemption d'ADMIN"
      echoue "  residuel ne designe pas le role qui le detient reellement."
    fi
  else
    echoue "C installee mais topologie refusee: $(head -1 <<<"$TOPO")"
  fi
elif grep -q "$PLAN" <<<"$DIAG" \
     && grep -qE "${AUTORITES[0]}|${AUTORITES[1]}" <<<"$DIAG"; then
  attendu_rouge "C refusee: rien n'inscrit encore le donneur « $PLAN » dans"
  attendu_rouge "  normative_control_plane, donc aucun ADMIN residuel n'est"
  attendu_rouge "  exempte. Le gel depuis le grantor est l'objet de 6.3b6b."
  attendu_rouge "  Diagnostic: $(cut -c1-150 <<<"$DIAG")"
  ROUGES_ATTENDUS=$((ROUGES_ATTENDUS + 1))
else
  echoue "C refusee pour un motif imprevu:"
  echo "              $DIAG" >&2
fi

echo ""
echo "================================================="
if [[ $ECHECS -eq 0 && $ROUGES_ATTENDUS -eq 0 ]]; then
  echo " Deploiement en deux phases verifie."
  echo "================================================="
  exit 0
fi
echo " Deploiement en deux phases:"
echo "   $ECHECS ecart(s) non prevu(s)"
echo "   $ROUGES_ATTENDUS rouge(s) ATTENDU(S), cible de 6.3b6b"
echo "================================================="
exit 1
