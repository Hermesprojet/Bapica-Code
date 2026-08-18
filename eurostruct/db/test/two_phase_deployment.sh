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
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

PREFIXE="${1:?usage: two_phase_deployment.sh <prefixe-de-base-jetable>}"
if ! [[ "$PREFIXE" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,40}$ ]]; then
  echo "      ECHEC: prefixe « $PREFIXE » invalide" >&2
  exit 2
fi

# --------------------------------------------------------------------------
# SECURITE DU HARNAIS — avant toute connexion, avant tout DROP
# --------------------------------------------------------------------------
# CE FICHIER CREE ET DETRUIT DES ROLES GLOBAUX. Les roles ne sont pas confines
# a une base: `eurostruct_normative_writer`, `normative_backend` et les autres
# appartiennent au CLUSTER. La version precedente les detruisait par
# `drop owned by ... cascade` puis `drop role`, sans aucune precondition, en se
# connectant a `$DATABASE_URL` si elle etait posee.
#
# Lance par inadvertance avec l'URL d'un staging — ou d'une production — ce
# script aurait donc detruit les vrais roles normatifs et, par CASCADE, les
# objets qui en dependent. Rien ne s'y opposait.
#
# Trois barrieres, cumulatives:
#   1. la connexion ne prend plus de secret en argv;
#   2. le cluster doit etre PROUVE jetable et isole — declaration explicite ET
#      constats (boucle locale, aucun marqueur de plateforme geree, aucune base
#      etrangere, superutilisateur);
#   3. les roles canoniques doivent etre ABSENTS: ce script ne detruit jamais
#      ce qu'il n'a pas cree.
harnais_connexion || exit 2
exiger_cluster_jetable "two_phase_deployment.sh" || exit 2

# Un jeton par execution pour les roles JETABLES. Les roles canoniques, eux,
# portent des noms imposes par la migration: ils ne peuvent pas etre suffixes,
# et c'est precisement pourquoi les barrieres ci-dessus existent.
JETON="$(harnais_jeton)"
MIGRATEUR="${PREFIXE}_mig_${JETON}"; MIG_MDP="FICTIF-2p-mig-$JETON"
PLAN="${PREFIXE}_ctl_${JETON}";      PLAN_MDP="FICTIF-2p-ctl-$JETON"

AUTORITES=(eurostruct_normative_writer eurostruct_normative_bootstrap)
SERVICES=(normative_backend normative_governance)
DEPLOIEMENT=eurostruct_deployment
CANONIQUES=("${AUTORITES[@]}" "${SERVICES[@]}" "$DEPLOIEMENT")

exiger_roles_absents "two_phase_deployment.sh" "${CANONIQUES[@]}" || exit 2

PROPRIETAIRE="${PGUSER:-postgres}"
BASE_A="${PREFIXE}_a_${JETON}"
BASE_B="${PREFIXE}_b_${JETON}"
BASE_C="${PREFIXE}_c_${JETON}"

ECHECS=0; ROUGES_ATTENDUS=0
echoue() { echo "      ECHEC: $*" >&2; ECHECS=$((ECHECS + 1)); }
attendu_rouge() { echo "      ATTENDU-ROUGE (6.3b6b): $*"; }

# Toutes les connexions viennent de l'ENVIRONNEMENT: ni URL, ni mot de passe
# dans argv. Seule la base change, par `-d`.
adm()      { psql -X -q -d postgres "$@"; }
admin_db() { local b="$1"; shift; psql -X -q -d "$b" "$@"; }
mig()  { local b="$1"; shift; PGUSER="$MIGRATEUR" PGPASSWORD="$MIG_MDP"  psql -X -d "$b" "$@"; }
plan() { local b="$1"; shift; PGUSER="$PLAN"      PGPASSWORD="$PLAN_MDP" psql -X -d "$b" "$@"; }

# --------------------------------------------------------------------------
# Remise a zero ENTRE CONFIGURATIONS — par noms exacts, jamais par motif
# --------------------------------------------------------------------------
# Les roles sont globaux et survivent aux bases: sans cette remise a zero, une
# configuration heriterait des roles de la precedente et ne testerait plus la
# variable qu'elle isole. Ne sont detruits que les roles inscrits au registre,
# c'est-a-dire ceux que CETTE execution a crees.
raz() {
  local b r
  for b in "$BASE_A" "$BASE_B" "$BASE_C"; do
    adm -c "drop database if exists \"$b\";" >/dev/null 2>&1
  done

  # LES ROLES CANONIQUES CREES PAR LA MIGRATION ELLE-MEME.
  #
  # En configuration A, personne ne les pre-cree: c'est `0010` qui les cree,
  # sous le migrateur. Ils n'etaient donc inscrits a aucun registre, et
  # survivaient a `raz` — apres quoi `drop role` sur le migrateur ECHOUAIT,
  # PostgreSQL refusant de detruire un role dont d'autres octrois dependent.
  # La configuration suivante retrouvait alors le migrateur en place et
  # s'ouvrait sur « role already exists ».
  #
  # Les detruire ici est legitime, et la legitimite est PROUVEE, pas supposee:
  # `exiger_roles_absents` a constate au demarrage qu'AUCUN d'eux n'existait.
  # Tout role canonique present maintenant a donc ete cree par cette execution.
  # C'est la seule justification acceptable pour toucher a un nom global.
  for r in "${CANONIQUES[@]}"; do
    adm -c "drop owned by \"$r\";"      >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done

  detruire_roles_crees
}
trap raz EXIT

# Les deux roles jetables, recrees a chaque configuration.
creer_acteurs() {
  creer_role "$MIGRATEUR" "login password '$MIG_MDP' createrole createdb" || return 1
  creer_role "$PLAN"      "login password '$PLAN_MDP' createrole"         || return 1
  return 0
}
creer_acteurs || { echoue "creation des acteurs impossible"; exit 1; }

echo "    deploiement en deux phases: qui cree, qui accorde, qui revoque"

# --------------------------------------------------------------------------
# ORACLES — les trois faits de PostgreSQL 16, MESURES et non supposes
# --------------------------------------------------------------------------
# Toute l'architecture en depend. S'ils changent — nouvelle version majeure,
# fournisseur qui patche — ce n'est pas une bonne nouvelle a ignorer: c'est un
# reexamen a ouvrir, et il vaut mieux l'apprendre ici qu'en production.
# F1 — le createur recoit une appartenance donnee par le superutilisateur.
mig postgres -q -c "create role ${PREFIXE}_f1_${JETON} nologin;" >/dev/null 2>&1
LU=$(adm -tAc "
  select g.rolname || '/' || m.admin_option || '/' || m.set_option
    from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
    join pg_roles g on g.oid = m.grantor
   where a.rolname = '${PREFIXE}_f1_${JETON}' and p.rolname = '$MIGRATEUR'")
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
mig postgres -q -c "revoke ${PREFIXE}_f1_${JETON} from \"$MIGRATEUR\";" >/dev/null 2>&1
mig postgres -q -c "revoke ${PREFIXE}_f1_${JETON} from \"$MIGRATEUR\" granted by $PROPRIETAIRE;" >/dev/null 2>&1
SURVIT=$(adm -tAc "
  select count(*) from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
   where a.rolname = '${PREFIXE}_f1_${JETON}' and p.rolname = '$MIGRATEUR'")
if [[ "$SURVIT" == "1" ]]; then
  echo "      ok: F2 — l'appartenance survit aux deux tentatives de revocation"
else
  echoue "F2 a change: le migrateur a pu revoquer une appartenance qu'il n'a"
  echoue "  pas donnee. La restitution par la migration redevient possible, et"
  echoue "  le decoupage en deux phases doit etre reexamine."
fi

# F3 — le donneur revoque ce qu'il a donne.
adm -c "create role ${PREFIXE}_f3_${JETON} nologin;" >/dev/null 2>&1
adm -c "grant ${PREFIXE}_f3_${JETON} to \"$MIGRATEUR\";" >/dev/null 2>&1
adm -c "revoke ${PREFIXE}_f3_${JETON} from \"$MIGRATEUR\";" >/dev/null 2>&1
if [[ "$(adm -tAc "
      select count(*) from pg_auth_members m
        join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
       where a.rolname = '${PREFIXE}_f3_${JETON}' and p.rolname = '$MIGRATEUR'")" == "0" ]]; then
  echo "      ok: F3 — le donneur revoque ce qu'il a donne"
else
  echoue "F3 a change: le donneur ne peut plus revoquer son propre octroi."
fi
adm -c "drop role if exists ${PREFIXE}_f1_${JETON};" >/dev/null 2>&1
adm -c "drop role if exists ${PREFIXE}_f3_${JETON};" >/dev/null 2>&1

# --------------------------------------------------------------------------
# Application des migrations sous le migrateur. DIAG porte le premier
# diagnostic, tronque: on veut le motif, pas le fichier entier.
# --------------------------------------------------------------------------
DIAG=""
appliquer() {
  local base="$1" out f
  adm -v ON_ERROR_STOP=1 \
    -c "create database \"$base\" owner \"$MIGRATEUR\";" >/dev/null || return 2
  admin_db "$base" -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admin_db "$base" >/dev/null 2>&1 <<SQL
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
if appliquer "$BASE_A"; then
  echoue "A: la migration s'est INSTALLEE alors que le migrateur, privilegie,"
  echoue "  est membre des roles de service qu'il vient de creer (F1). Il"
  echoue "  contourne la RLS et herite en plus des droits d'ecriture normatifs."
elif grep -qE "prerequis non tenu: le role privilegie .* atteint le role de service" <<<"$DIAG"; then
  echo "      ok: A refusee — le migrateur privilegie atteint un role de service"
else
  echoue "A refusee, mais pas sur le motif attendu:"
  echo "              $DIAG" >&2
fi
raz; creer_acteurs || { echoue "recreation des acteurs impossible"; exit 1; }

# ==========================================================================
# B — PROVISIONNEMENT PAR UN SUPERUTILISATEUR
# ==========================================================================
# Le superutilisateur cree TOUS les roles: par F1 c'est LUI qui garde l'ADMIN
# residuel, et le controle de topologie l'ignore — les superutilisateurs sont
# hors modele de menace, explicitement et depuis l'origine.
for r in "${CANONIQUES[@]}"; do
  creer_role "$r" nologin || { echoue "B: creation de $r impossible"; exit 1; }
done
# Le migrateur doit pouvoir transferer la propriete des fonctions: PostgreSQL
# l'exige membre des roles d'autorite. ADMIN OPTION pour que la migration
# puisse tenter la restitution — c'est precisement ce que F2 lui refuse.
adm -v ON_ERROR_STOP=1 >/dev/null <<SQL
grant ${AUTORITES[0]} to "$MIGRATEUR" with admin option;
grant ${AUTORITES[1]} to "$MIGRATEUR" with admin option;
SQL

if appliquer "$BASE_B"; then
  if TOPO=$(mig "$BASE_B" -q -tAc 'select assert_normative_topology()' 2>&1); then
    CAP=$(adm -tAc "
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
raz; creer_acteurs || { echoue "recreation des acteurs impossible"; exit 1; }

# ==========================================================================
# C — PROVISIONNEMENT PAR UN PLAN DE CONTROLE NON SUPERUTILISATEUR
# ==========================================================================
# La forme Supabase: le client ne dispose d'aucun superutilisateur. Par F1, le
# plan de controle garde un ADMIN residuel IRREVOCABLE sur tout ce qu'il cree.
# C'est la configuration que `normative_control_plane` existe pour rendre
# admissible — un seul ADMIN residuel, nomme, fige a l'installation.
adm -c "grant \"$PLAN\" to $PROPRIETAIRE;" >/dev/null 2>&1
# Ils sont crees PAR LE PLAN DE CONTROLE — c'est la variable de cette
# configuration — et non par l'administrateur. Ils sont donc inscrits au
# registre a la main: un role cree sans etre inscrit ne serait jamais nettoye.
plan postgres -q -v ON_ERROR_STOP=1 >/dev/null <<SQL
create role ${SERVICES[0]} nologin;
create role ${SERVICES[1]} nologin;
create role ${AUTORITES[0]} nologin;
create role ${AUTORITES[1]} nologin;
create role $DEPLOIEMENT nologin;
grant ${AUTORITES[0]} to "$MIGRATEUR" with admin option;
grant ${AUTORITES[1]} to "$MIGRATEUR" with admin option;
SQL
for r in "${CANONIQUES[@]}"; do registre_role "$r"; done

DONNEUR=$(adm -tAc "
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

if appliquer "$BASE_C"; then
  if TOPO=$(mig "$BASE_C" -q -tAc 'select assert_normative_topology()' 2>&1); then
    FIGE=$(mig "$BASE_C" -q -tAc 'select normative_control_plane()' 2>&1)
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
