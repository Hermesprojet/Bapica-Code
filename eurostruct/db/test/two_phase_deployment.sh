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
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"

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
exiger_precontrole_local "two_phase_deployment.sh" || exit 2
harnais_verrou_prendre "two_phase_deployment.sh" || exit $?   # 2 = parametre invalide, 3 = verrou detenu
exiger_cluster_jetable "two_phase_deployment.sh" || exit 2


# Un jeton par execution pour les roles JETABLES. Les roles canoniques, eux,
# portent des noms imposes par la migration: ils ne peuvent pas etre suffixes,
# et c'est precisement pourquoi les barrieres ci-dessus existent.
JETON="$(harnais_jeton)"
MIGRATEUR="${PREFIXE}_mig_${JETON}"; MIG_MDP="FICTIF-2p-mig-$JETON"
PLAN="${PREFIXE}_ctl_${JETON}";      PLAN_MDP="FICTIF-2p-ctl-$JETON"

AUTORITES=(eurostruct_normative_writer eurostruct_normative_bootstrap
           eurostruct_normative_activator)
# LE SEPTIEME ROLE CANONIQUE. `eurostruct_authority_backend` est cree par la
# PHASE 0 depuis 6.3c: il doit donc etre exige absent AVANT, enregistre pour
# le demontage, et detruit APRES, exactement comme les six autres. Mesure du
# 26/08: il ne l'etait pas ici, et il survivait a ce harnais — les sept suites
# suivantes de `run.sh` refusaient alors de demarrer sur « ces roles existent
# deja ». Un role oublie dans une liste de demontage n'est pas un detail: il
# arrete tout ce qui vient apres.
SERVICES=(normative_backend normative_governance
          eurostruct_authority_backend)
DEPLOIEMENT=eurostruct_deployment
CANONIQUES=("${AUTORITES[@]}" "${SERVICES[@]}" "$DEPLOIEMENT")

exiger_roles_absents "two_phase_deployment.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

PROPRIETAIRE="${PGUSER:-postgres}"
BASE_A="${PREFIXE}_a_${JETON}"
BASE_B="${PREFIXE}_b_${JETON}"
BASE_C="${PREFIXE}_c_${JETON}"
# Inscrites des maintenant: la postcondition doit les couvrir meme si l'une
# n'a pas pu etre creee — c'est justement le cas ou l'on veut le constater.
registre_base "$BASE_A"; registre_base "$BASE_B"; registre_base "$BASE_C"
# Nommes des maintenant: le trap de sortie et la postcondition y font
# reference, et ils doivent etre definis meme si la creation echoue.
# LES IDENTIFIANTS SONT TOUJOURS QUOTES DANS LE SQL.
#
# CONTRE-EXEMPLE MESURE, et il ne se voyait qu'avec un prefixe MAJUSCULE:
# `create role $F1` sans guillemets fait replier le nom par PostgreSQL, si bien
# que `ccA_f1_...` etait cree sous le nom `cca_f1_...`. Le registre et les
# oracles, eux, cherchaient la casse d'origine: la membership n'etait pas
# trouvee (« F1 a change: aucune ligne »), et le nettoyage par nom exact ne
# supprimait rien — deux roles residuels apres chaque concurrence.
#
# Le scenario 7 emploie `concA`/`concB`; c'est lui qui l'a fait apparaitre,
# alors que toutes les executions en minuscules restaient vertes.
F1="${PREFIXE}_f1_${JETON}"
F3="${PREFIXE}_f3_${JETON}"

# PLUS DE « ATTENDU-ROUGE ». Les configurations B et C etaient declarees
# rouges-par-construction en 6.3b6a: la restitution des emprunts etait
# impossible (fait F2) et rien ne figeait le plan de controle. La phase 2
# existe depuis 6.3b6b, et les deux configurations doivent donc aller
# JUSQU'A ACTIVE. Un verdict qui tolere un rouge nomme ne peut pas distinguer
# « la fonctionnalite manque » de « la fonctionnalite est cassee ».
ECHECS=0
echoue() { echo "      ECHEC: $*" >&2; ECHECS=$((ECHECS + 1)); }

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
  # Les bases D'ABORD: `DROP OWNED BY` ne voit que la base courante, et les
  # roles d'autorite possedent des fonctions dans ces bases. Les detruire
  # ensuite echouait, et l'echec etait masque.
  for b in "$BASE_A" "$BASE_B" "$BASE_C"; do
    adm -c "select pg_terminate_backend(pid) from pg_stat_activity
             where datname = '$b' and pid <> pg_backend_pid();" >/dev/null 2>&1
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
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do
    adm -c "drop owned by \"$r\";"      >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done

  detruire_roles_crees
}
# POSTCONDITION VERIFIEE, et le verrou rendu. « Sans residu » cesse d'etre une
# observation pour devenir une propriete controlee, base par base et role par
# role, par nom exact. Code 3 si elle echoue: l'execution suivante partirait
# d'un etat qu'elle croirait propre.
NETTOYAGE_KO=0
sortie_propre() {
  raz
  local r
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do registre_role "$r"; done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "two_phase_deployment.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" \
    "$MIGRATEUR" "$PLAN" "$F1" "$F3" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

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
# INSCRITS DES LA CREATION, ET NON A LA SUPPRESSION.
#
# F1 et F3 etaient crees ici et detruits une trentaine de lignes plus bas, hors
# de tout registre. Toute interruption entre les deux — `kill`, timeout,
# `set -e` sur un appel intermediaire, plantage du cluster — les laissait
# derriere, et la postcondition ne les couvrait pas: elle ne connaissait que le
# registre. L'inscription suit donc IMMEDIATEMENT la creation reussie.
if mig postgres -q -v ON_ERROR_STOP=1 -c "create role \"$F1\" nologin;" >/dev/null 2>&1; then
  registre_role "$F1"
fi
LU=$(adm -tAc "
  select g.rolname || '/' || m.admin_option || '/' || m.set_option
    from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
    join pg_roles g on g.oid = m.grantor
   where a.rolname = '$F1' and p.rolname = '$MIGRATEUR'")
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
mig postgres -q -c "revoke \"$F1\" from \"$MIGRATEUR\";" >/dev/null 2>&1
mig postgres -q -c "revoke \"$F1\" from \"$MIGRATEUR\" granted by \"$PROPRIETAIRE\";" >/dev/null 2>&1
SURVIT=$(adm -tAc "
  select count(*) from pg_auth_members m
    join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
   where a.rolname = '$F1' and p.rolname = '$MIGRATEUR'")
if [[ "$SURVIT" == "1" ]]; then
  echo "      ok: F2 — l'appartenance survit aux deux tentatives de revocation"
else
  echoue "F2 a change: le migrateur a pu revoquer une appartenance qu'il n'a"
  echoue "  pas donnee. La restitution par la migration redevient possible, et"
  echoue "  le decoupage en deux phases doit etre reexamine."
fi

# F3 — le donneur revoque ce qu'il a donne.
if adm -v ON_ERROR_STOP=1 -c "create role \"$F3\" nologin;" >/dev/null 2>&1; then
  registre_role "$F3"
fi
adm -c "grant \"$F3\" to \"$MIGRATEUR\";" >/dev/null 2>&1
adm -c "revoke \"$F3\" from \"$MIGRATEUR\";" >/dev/null 2>&1
if [[ "$(adm -tAc "
      select count(*) from pg_auth_members m
        join pg_roles a on a.oid = m.roleid join pg_roles p on p.oid = m.member
       where a.rolname = '$F3' and p.rolname = '$MIGRATEUR'")" == "0" ]]; then
  echo "      ok: F3 — le donneur revoque ce qu'il a donne"
else
  echoue "F3 a change: le donneur ne peut plus revoquer son propre octroi."
fi

# --------------------------------------------------------------------------
# Application des migrations sous le migrateur. DIAG porte le premier
# diagnostic, tronque: on veut le motif, pas le fichier entier.
# --------------------------------------------------------------------------
DIAG=""
# `appliquer <base> [roles-de-deploiement-approuves]`
#
# LA DECLARATION EST POSEE ICI, APRES LA CREATION DE LA BASE. Elle l'etait
# avant l'appel, donc avant que la base existe: l'`ALTER DATABASE` echouait en
# silence et la configuration C se refusait sur « detient eurostruct_deployment
# sans approbation » — un motif exact, mais provoque par le harnais.
# `appliquer <base> <acteur-phase-0> [roles-de-deploiement-approuves]`
#
# L'ACTEUR DE LA PHASE 0 EST UN PARAMETRE (6.3b6c), et c'est la variable de ces
# trois configurations. La phase 0 pose la RACINE DE CONFIANCE: qui l'applique
# devient le seul a pouvoir approuver, et le migrateur ne doit jamais etre ce
# role-la — sauf en A, ou l'on veut precisement voir la finalisation refuser.
#
#   A  greenfield          le migrateur applique tout: phase 0 et phase 1
#   B  superutilisateur    l'administrateur pose le sceau
#   C  plan non superuser  la forme Supabase
appliquer() {
  local base="$1" acteur="$2" approuves="${3:-}" out f
  adm -v ON_ERROR_STOP=1 \
    -c "create database \"$base\" owner \"$MIGRATEUR\";" >/dev/null || return 2
  if [[ -n "$approuves" ]]; then
    adm -v ON_ERROR_STOP=1 -c "alter database \"$base\"
      set eurostruct.approved_deployment_roles = '$approuves';" >/dev/null || return 2
  fi
  admin_db "$base" -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admin_db "$base" >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIGRATEUR" with grant option;
grant select, insert, references on auth.users to "$MIGRATEUR" with grant option;
grant execute on function auth.uid() to "$MIGRATEUR" with grant option;
grant create on database $base to "$MIGRATEUR";
-- L'acteur de la phase 0 cree des objets dans `public` et les transfere a
-- l'activateur: CREATE avec GRANT OPTION. Les deux acteurs possibles le
-- recoivent, l'administrateur l'a deja.
grant create on schema public to "$MIGRATEUR", "$PLAN" with grant option;
grant usage on schema auth to "$PLAN";
SQL
  # PHASE 0 — LE SCEAU.
  if ! out=$($acteur "$base" -q -v ON_ERROR_STOP=1 \
               -f "$HARNAIS_SCEAU" 2>&1); then
    DIAG="phase 0: $(grep -m1 -E 'ERROR|FATAL' <<<"$out" | cut -c1-300)"
    return 1
  fi
  # L'EMPRUNT EST ACCORDE PAR L'ACTEUR DE LA PHASE 0, et donc apres elle: les
  # roles d'autorite n'existaient pas avant. C'est lui le DONNEUR (fait F3), et
  # c'est ce que la finalisation derivera du catalogue.
  $acteur "$base" -q >/dev/null 2>&1 <<SQL
grant ${AUTORITES[0]} to "$MIGRATEUR" with admin option;
grant ${AUTORITES[1]} to "$MIGRATEUR" with admin option;
SQL
  local r
  for r in "${CANONIQUES[@]}"; do registre_role "$r"; done

  # PHASE 1 — par le migrateur, 0000 exclu.
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig "$base" -q; then
      out="$ESC_MIGRATION_SORTIE"
      DIAG="$(grep -m1 -E 'ERROR|FATAL' <<<"$out" | cut -c1-320)"
      return 1
    fi
  done
  DIAG=""; return 0
}

# ==========================================================================
# A — GREENFIELD, LE MIGRATEUR SEUL
# ==========================================================================
# CE QUI EST ATTENDU DE A A CHANGE AVEC 6.3b6b, ET LE MOTIF EST LE SUJET.
#
# La phase 1 S'INSTALLE desormais: depuis que les prerequis portent sur SET et
# USAGE et non sur MEMBER, l'ADMIN residuel que PostgreSQL donne au createur
# (F1: admin=t, set=f, inherit=f) ne suffit plus a refuser — et il ne le doit
# pas, puisqu'en PENDING aucune ecriture normative n'est possible.
#
# C'est la FINALISATION qui refuse, et pour le seul motif qui vaille ici: le
# migrateur serait son propre plan de controle. Un deploiement greenfield reste
# donc inexploitable, mais il est refuse au moment ou le refus protege quelque
# chose, avec un diagnostic qui dit quoi faire.
if ! appliquer "$BASE_A" mig "$MIGRATEUR"; then
  echoue "A: la phase 1 doit s'installer (aucune ecriture normative n'est"
  echoue "  possible en PENDING). Refus obtenu:"
  echo "              $DIAG" >&2
else
  ETAT=$(admin_db "$BASE_A" -tAc 'select normative_activation_state()' 2>&1)
  # Le migrateur a l'ADMIN sur le role de deploiement qu'il vient de creer: il
  # peut donc se l'accorder pour de bon, ce qu'un installeur greenfield ferait.
  mig postgres -q -c "grant $DEPLOIEMENT to \"$MIGRATEUR\" with inherit true;" \
    >/dev/null 2>&1
  MANIF=$(mig "$BASE_A" -q -tAc 'select normative_settings_manifest()' 2>&1)
  FIN=$(mig "$BASE_A" -q -tAc "select normative_finalize_deployment('$MANIF')" 2>&1)
  APRES=$(admin_db "$BASE_A" -tAc 'select normative_activation_state()' 2>&1)
  if [[ "$ETAT" != "PENDING" ]]; then
    echoue "A: la phase 1 ne se termine pas en PENDING (obtenu: $ETAT)."
  elif [[ "$APRES" == "ACTIVE" ]]; then
    echoue "A: UN SEUL ROLE A PU FINALISER. Le migrateur est son propre plan de"
    echoue "  controle, garde l'ADMIN residuel par exemption, et peut donc se"
    echoue "  reaccorder SET quand il veut: la separation est nominale."
  elif grep -qE "deux roles DISTINCTS|plan de controle derive est le migrateur" <<<"$FIN"; then
    echo "      ok: A phase 1 installee (PENDING), finalisation REFUSEE — le"
    echo "             migrateur serait son propre plan de controle"
  else
    echoue "A: la finalisation refuse, mais pas au motif de la separation:"
    esc_diag_rapporter "A / finalisation" "$FIN"
  fi
fi
raz; creer_acteurs || { echoue "recreation des acteurs impossible"; exit 1; }

# ==========================================================================
# B — PROVISIONNEMENT PAR UN SUPERUTILISATEUR
# ==========================================================================
# Le superutilisateur cree TOUS les roles: par F1 c'est LUI qui garde l'ADMIN
# residuel, et le controle de topologie l'ignore — les superutilisateurs sont
# hors modele de menace, explicitement et depuis l'origine.
# LES ROLES CANONIQUES SONT CREES PAR LA PHASE 0 (6.3b6c), sous l'acteur qui
# pose le sceau — ici l'administrateur. Ils sont inscrits au registre apres
# coup: un role cree sans etre inscrit ne serait jamais nettoye.
# L'emprunt est accorde par `appliquer`, juste apres la phase 0: les roles
# d'autorite n'existent pas avant elle.
if appliquer "$BASE_B" admin_db "$MIGRATEUR,$PROPRIETAIRE"; then
  # PHASE 1 TERMINEE: l'etat doit etre PENDING, et rien ne doit encore engager.
  ETAT=$(admin_db "$BASE_B" -tAc 'select normative_activation_state()' 2>&1)
  if [[ "$ETAT" != "PENDING" ]]; then
    echoue "B: la phase 1 ne se termine pas en PENDING (obtenu: $ETAT)."
  else
    # PHASE 2, exercee par le DONNEUR — ici le superutilisateur qui a
    # provisionne. Il presente le MANIFESTE des declarations qu'il a revues.
    MANIF=$(admin_db "$BASE_B" -tAc 'select normative_settings_manifest()' 2>&1)
    FIN=$(admin_db "$BASE_B" -tAc "select normative_finalize_deployment('$MANIF')" 2>&1)
    ETAT=$(admin_db "$BASE_B" -tAc 'select normative_activation_state()' 2>&1)
    CAP=$(adm -tAc "
      select count(*) from pg_roles a
       where a.rolname = any (array['${AUTORITES[0]}','${AUTORITES[1]}','${AUTORITES[2]}'])
         and (pg_has_role('$MIGRATEUR', a.rolname, 'SET')
              or pg_has_role('$MIGRATEUR', a.rolname, 'USAGE')
              or pg_has_role('$MIGRATEUR', a.rolname, 'MEMBER WITH ADMIN OPTION'))")
    if [[ "$ETAT" != "ACTIVE" ]]; then
      echoue "B: la finalisation n'a pas abouti (etat $ETAT):"
      esc_diag_rapporter "B / finalisation" "$FIN"
    elif [[ "$CAP" != "0" ]]; then
      echoue "B activee mais le migrateur conserve $CAP capacite(s) sur les"
      echoue "  roles d'autorite: il peut encore forger une origine normative."
    # PAR LE DONNEUR, PAS PAR LE MIGRATEUR. Apres la finalisation le migrateur
    # n'a plus aucun droit sur les fonctions de confiance — c'est le but — et
    # la verification echouerait sur « permission denied », un faux rouge.
    elif ! TOPO=$(admin_db "$BASE_B" -tAc 'select assert_normative_topology()' 2>&1); then
      echoue "B activee mais topologie refusee: $(head -1 <<<"$TOPO")"
    else
      # IDEMPOTENCE: une seconde finalisation constate, elle ne reecrit pas.
      FIN2=$(admin_db "$BASE_B" -tAc "select normative_finalize_deployment('$MANIF')" 2>&1)
      if grep -q 'deja finalise' <<<"$FIN2"; then
        echo "      ok: B PENDING -> ACTIVE par le donneur, migrateur sans capacite,"
        echo "             seconde finalisation idempotente"
      else
        echoue "B: la seconde finalisation ne constate pas l'etat: $(head -1 <<<"$FIN2")"
      fi
    fi
  fi
else
  echoue "B refusee, alors que la phase 1 doit s'installer:"
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
# LES ROLES SONT CREES PAR LA PHASE 0, sous le PLAN DE CONTROLE — c'est la
# variable de cette configuration, et c'est `appliquer` qui l'exerce.
# Le role de deploiement lui est accorde APRES, puisqu'il n'existe pas avant.
# La declaration est posee par `appliquer`, apres la creation de la base.

if appliquer "$BASE_C" plan "$MIGRATEUR,$PLAN"; then
  adm -c "grant $DEPLOIEMENT to \"$PLAN\" with inherit true;" >/dev/null 2>&1
  # LE DONNEUR EST CONSTATE APRES LA PHASE 0: l'emprunt n'existe pas avant
  # elle, et le lire trop tot rendait « aucun » — un ecart imputable au
  # harnais, pas a la configuration.
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
  ETAT=$(admin_db "$BASE_C" -tAc 'select normative_activation_state()' 2>&1)
  if [[ "$ETAT" != "PENDING" ]]; then
    echoue "C: la phase 1 ne se termine pas en PENDING (obtenu: $ETAT)."
  else
    # PHASE 2 PAR LE PLAN DE CONTROLE, qui est le donneur (F3) — et le seul a
    # pouvoir revoquer. Il presente le manifeste des declarations revues.
    MANIF=$(plan "$BASE_C" -q -tAc 'select normative_settings_manifest()' 2>&1)
    FIN=$(plan "$BASE_C" -q -tAc "select normative_finalize_deployment('$MANIF')" 2>&1)
    ETAT=$(plan "$BASE_C" -q -tAc 'select normative_activation_state()' 2>&1)
    FIGE=$(plan "$BASE_C" -q -tAc 'select normative_control_plane()' 2>&1)
    FIGE_OID=$(plan "$BASE_C" -q -tAc 'select normative_control_plane_oid()' 2>&1)
    OID_PLAN=$(adm -tAc "select oid from pg_roles where rolname = '$PLAN'")
    CAP=$(adm -tAc "
      select count(*) from pg_roles a
       where a.rolname = any (array['${AUTORITES[0]}','${AUTORITES[1]}','${AUTORITES[2]}'])
         and (pg_has_role('$MIGRATEUR', a.rolname, 'SET')
              or pg_has_role('$MIGRATEUR', a.rolname, 'USAGE')
              or pg_has_role('$MIGRATEUR', a.rolname, 'MEMBER WITH ADMIN OPTION'))")
    if [[ "$ETAT" != "ACTIVE" ]]; then
      echoue "C: la finalisation par « $PLAN » n'a pas abouti (etat $ETAT):"
      esc_diag_rapporter "C / finalisation" "$FIN"
    elif [[ "$CAP" != "0" ]]; then
      echoue "C activee mais le migrateur conserve $CAP capacite(s)."
    elif [[ "$FIGE" != "$PLAN" || "$FIGE_OID" != "$OID_PLAN" ]]; then
      echoue "C activee, mais le plan de controle fige est « ${FIGE:-NULL} »"
      echoue "  (oid ${FIGE_OID:-NULL}) et non « $PLAN » (oid $OID_PLAN):"
      echoue "  l'exemption d'ADMIN residuel ne designe pas le role qui le"
      echoue "  detient reellement."
    elif ! TOPO=$(plan "$BASE_C" -q -tAc 'select assert_normative_topology()' 2>&1); then
      echoue "C activee mais topologie refusee: $(head -1 <<<"$TOPO")"
    else
      # L'ADMIN RESIDUEL DU PLAN EST BIEN LA, et c'est lui qui est exempte:
      # sans ce constat, « topologie acceptee » pourrait signifier « le plan
      # ne detient plus rien », c'est-a-dire un autre scenario.
      RES=$(adm -tAc "
        select count(*) from pg_roles a
         where a.rolname = any (array['${AUTORITES[0]}','${AUTORITES[1]}','${AUTORITES[2]}'])
           and pg_has_role('$PLAN', a.rolname, 'MEMBER WITH ADMIN OPTION')")
      if [[ "$RES" == "3" ]]; then
        echo "      ok: C PENDING -> ACTIVE par « $PLAN » (oid $OID_PLAN), ADMIN"
        echo "             residuel conserve sur 3 roles et exempte, migrateur nu"
      else
        echoue "C: le plan de controle ne detient l'ADMIN residuel que sur $RES"
        echoue "  role(s) d'autorite sur 3: la configuration Supabase n'est pas"
        echoue "  celle qui est testee."
      fi
    fi
  fi
else
  echoue "C refusee, alors que la phase 1 doit s'installer:"
  echo "              $DIAG" >&2
fi

echo ""
echo "================================================="
if [[ $ECHECS -eq 0 ]]; then
  echo " Deploiement en deux phases verifie: A refusee, B et C menees"
  echo " jusqu'a ACTIVE."
  echo "================================================="
  exit 0
fi
echo " Deploiement en deux phases: $ECHECS ecart(s)"
echo "================================================="
exit 1
