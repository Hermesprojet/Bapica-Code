#!/usr/bin/env bash
#
# EUROSTRUCT — LA COMMANDE OFFICIELLE DE DEPLOIEMENT
#
#   tools/deploy_eurostruct.sh [--auto-heberge] [--dry-run]
#
# CE QUE CE FICHIER EXISTE POUR REMPLACER
# ----------------------------------------
# Le deploiement en trois phases n'existait que dans des HARNAIS DE TEST. Ceux-ci
# creent et detruisent des roles globaux, exigent un cluster jetable, et
# refusent de tourner ailleurs — a raison. Un exploitant qui voulait deployer
# n'avait donc que le runbook a recopier a la main, etape par etape, sans
# qu'aucune postcondition ne soit verifiee.
#
# Ce script est le chemin officiel. Il n'est PAS un harnais:
#
#   * il ne cree ni ne detruit AUCUN role, AUCUNE base;
#   * il ne contient ni `drop database`, ni `drop role`, ni `drop owned by`;
#   * il n'exige aucun cluster jetable — il est fait pour la production;
#   * il ne consomme aucun consentement de destruction.
#
# Ce qu'il fait: orchestrer les trois phases, dans l'ordre, avec les DEUX
# acteurs, et VERIFIER a la fin ce qu'il annonce.
#
# LES DIX ETAPES
# --------------
#    1. phase 0 — le sceau, par le plan de controle
#    2. verification du sceau et de sa VERSION
#    3. octroi TEMPORAIRE de writer/bootstrap au migrateur
#    4. phase 1 — les migrations, par le migrateur
#    5. constat PENDING
#    6. lecture du manifeste, et approbation explicite
#    7. phase 2 — finalisation par le plan de controle
#    8. constat ACTIVE
#    9. constat: zero capacite residuelle du migrateur
#   10. constat: le niveau d'assurance est persiste, et il est lisible
#
# AUCUN SECRET DANS `argv`
# -------------------------
# Les identifiants viennent de l'environnement, jamais de la ligne de commande:
# `argv` est lisible par tout processus de la machine (`ps`,
# `/proc/<pid>/cmdline`). Deux URL sont attendues, decoupees ici en variables
# libpq puis effacees:
#
#   ESC_PLAN_URL       postgres://plan:...@hote/base    le PLAN DE CONTROLE
#   ESC_MIGRATOR_URL   postgres://mig:...@hote/base     le MIGRATEUR
#
# Les deux doivent viser LA MEME BASE. Le script le verifie.
#
# REPRISE APRES UN RESULTAT DE CONNEXION AMBIGU
# ----------------------------------------------
# Si `psql` echoue sur une coupure reseau, on ne sait pas si la transaction a
# ete validee. RELANCER CE SCRIPT EST SUR, et c'est une propriete construite:
#
#   * la phase 0 refuse par SEAL_ALREADY_INSTALLED sans rien muter si le sceau
#     est deja pose dans la meme version — le script le traite comme un succes;
#   * la phase 1 est composee de migrations idempotentes;
#   * la phase 2 rend « ACTIVE (deja finalise) » si le manifeste presente est
#     bien celui qui a ete approuve, et REFUSE sinon (MANIFEST_MISMATCH).
#
# Ce qu'il ne faut PAS faire apres une coupure: rejouer une etape a la main, ou
# reaccorder les emprunts « pour etre sur ». Relancez ce script.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$HERE")"
SCEAU="$RACINE/db/control_plane/0001_normative_seal.sql"
MIGRATIONS_DIR="$RACINE/db/migrations"

STRICT=1
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --auto-heberge) STRICT=0 ;;
    --dry-run)      DRY_RUN=1 ;;
    -h|--help)
      sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "REFUS: option inconnue « $arg »." >&2
      echo "       Usage: deploy_eurostruct.sh [--auto-heberge] [--dry-run]" >&2
      exit 2 ;;
  esac
done

echec()  { echo "ECHEC: $*" >&2; exit 1; }
etape()  { echo; echo "== $*"; }
constat(){ echo "   ok: $*"; }

# --------------------------------------------------------------------------
# LES DEUX CONNEXIONS
# --------------------------------------------------------------------------
# Le decoupage est CAPTURE ET VERIFIE avant tout `eval`. Une URL invalide
# produirait une sortie vide, `eval` ne poserait rien, et `psql` se rabattrait
# sur les PG* ambiantes — donc potentiellement sur une AUTRE base que celle
# qu'on croit viser. Meme technique que `db/test/lib_harnais.sh`, ecrite ici
# parce que ce script ne doit RIEN partager avec les harnais de test.
decouper_url() {
  local nom_var="$1" url="$2" conn ligne errpy
  errpy="$(mktemp)"
  if ! conn="$(URL="$url" python3 - 2>"$errpy" <<'FINPARSE'
import os, sys, shlex
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["URL"])
if u.scheme not in ("postgres", "postgresql"):
    sys.stderr.write("schema attendu postgres:// ou postgresql://\n"); sys.exit(2)
for champ, val in (("hote", u.hostname), ("utilisateur", u.username)):
    if not val:
        sys.stderr.write(f"{champ} absent de l'URL\n"); sys.exit(2)
base = unquote(u.path.lstrip("/"))
if not base:
    sys.stderr.write("nom de base absent de l'URL\n"); sys.exit(2)
q = parse_qs(u.query)
for k, v in (("HOST", u.hostname), ("PORT", str(u.port or 5432)),
             ("USER", unquote(u.username)),
             ("PASSWORD", unquote(u.password or "")),
             ("DATABASE", base),
             ("SSLMODE", q.get("sslmode", ["prefer"])[0])):
    print(f"{k}={shlex.quote(v)}")
FINPARSE
  )"; then
    echo "REFUS: $nom_var inexploitable." >&2
    sed 's/^/       /' "$errpy" >&2
    rm -f "$errpy"
    return 2
  fi
  rm -f "$errpy"
  while IFS= read -r ligne; do
    [[ -n "$ligne" ]] || continue
    [[ "$ligne" =~ ^(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]] \
      || { echo "REFUS: sortie de decoupage inattendue pour $nom_var." >&2; return 2; }
    eval "${nom_var}_${ligne}"
  done <<<"$conn"
  return 0
}

[[ -n "${ESC_PLAN_URL:-}" ]]     || echec "ESC_PLAN_URL n'est pas definie (plan de controle)."
[[ -n "${ESC_MIGRATOR_URL:-}" ]] || echec "ESC_MIGRATOR_URL n'est pas definie (migrateur)."
decouper_url PLAN "$ESC_PLAN_URL"     || exit 2
decouper_url MIG  "$ESC_MIGRATOR_URL" || exit 2
# LES URL N'ONT PLUS DE RAISON D'EXISTER. Les garder exposerait le secret a
# tout sous-processus — y compris a un `psql` remplace sur le PATH.
unset ESC_PLAN_URL ESC_MIGRATOR_URL

[[ "$PLAN_DATABASE" == "$MIG_DATABASE" ]] \
  || echec "les deux URL ne visent pas la meme base ($PLAN_DATABASE / $MIG_DATABASE)."
[[ "$PLAN_HOST" == "$MIG_HOST" && "$PLAN_PORT" == "$MIG_PORT" ]] \
  || echec "les deux URL ne visent pas le meme serveur."
BASE="$PLAN_DATABASE"

# LES DEUX ACTEURS DOIVENT ETRE DISTINCTS, et c'est le sujet de tout
# l'edifice: si le migrateur est son propre plan de controle, il conserve
# l'ADMIN residuel par exemption et peut se reaccorder SET quand il veut. La
# separation serait nominale. La finalisation le refuse de toute facon; le dire
# ICI evite d'appliquer un schema entier avant de l'apprendre.
if [[ "$PLAN_USER" == "$MIG_USER" ]]; then
  echec "le plan de controle et le migrateur sont le meme role (« $PLAN_USER »).
       La finalisation exige deux roles DISTINCTS: celui qui applique les
       migrations et celui qui approuve. Provisionnez un second role."
fi

plan() { PGHOST="$PLAN_HOST" PGPORT="$PLAN_PORT" PGUSER="$PLAN_USER" \
         PGPASSWORD="$PLAN_PASSWORD" PGSSLMODE="$PLAN_SSLMODE" \
         psql -X -q -d "$BASE" "$@"; }
mig()  { PGHOST="$MIG_HOST" PGPORT="$MIG_PORT" PGUSER="$MIG_USER" \
         PGPASSWORD="$MIG_PASSWORD" PGSSLMODE="$MIG_SSLMODE" \
         psql -X -q -d "$BASE" "$@"; }

echo "EUROSTRUCT — deploiement de « $BASE » sur $PLAN_HOST:$PLAN_PORT"
echo "   plan de controle : $PLAN_USER"
echo "   migrateur        : $MIG_USER"
echo "   mode             : $( ((STRICT)) && echo 'STRICT' || echo 'AUTO-HEBERGE (degrade)')"
if ((DRY_RUN)); then
  echo
  echo "--dry-run: les connexions sont verifiees, RIEN n'est applique."
  plan -tAc "select 1" >/dev/null 2>&1 || echec "le plan de controle ne peut pas se connecter."
  mig  -tAc "select 1" >/dev/null 2>&1 || echec "le migrateur ne peut pas se connecter."
  constat "les deux acteurs se connectent a « $BASE »"
  exit 0
fi

[[ -f "$SCEAU" ]] || echec "le fichier de sceau est introuvable ($SCEAU)."

# --------------------------------------------------------------------------
# 1. PHASE 0 — LE SCEAU, PAR LE PLAN DE CONTROLE
# --------------------------------------------------------------------------
etape "1/10  phase 0 — le sceau, par « $PLAN_USER »"
SORTIE=$(plan -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1)
CODE=$?
if [[ $CODE -ne 0 ]]; then
  # SEAL_ALREADY_INSTALLED N'EST PAS UNE ERREUR DE DEPLOIEMENT. C'est le
  # resultat normal d'une phase 0 rejouee — apres une coupure reseau, par
  # exemple. Le branchement se fait sur le MARQUEUR, jamais sur le code de
  # sortie de psql, qui vaut 3 pour toute exception.
  if grep -qF "SEAL_ALREADY_INSTALLED" <<<"$SORTIE"; then
    constat "le sceau etait deja pose dans cette version — rien n'a ete modifie"
  elif grep -qF "SEAL_VERSION_MISMATCH" <<<"$SORTIE"; then
    echec "cette base porte un sceau d'une AUTRE version.
       $(grep -m1 -oE 'SEAL_VERSION_MISMATCH.{0,200}' <<<"$SORTIE")
       Un sceau ne se remplace pas: appliquez la mise a niveau prevue dans
       db/control_plane/, ou redeployez la base depuis une base neuve."
  elif grep -qF "SEAL_PARTIAL" <<<"$SORTIE"; then
    echec "le sceau de cette base est INCOMPLET — une phase 0 interrompue.
       $(grep -m1 -oE 'SEAL_PARTIAL.{0,200}' <<<"$SORTIE")
       Ce script ne repare pas une racine a moitie posee: on ne saurait plus
       quelle version elle porte. Repartez d'une base neuve."
  else
    echec "la phase 0 a ete refusee:
$(grep -m3 -E 'ERROR|FATAL|psql:' <<<"$SORTIE" | sed 's/^/       /')"
  fi
else
  constat "sceau pose"
fi

# --------------------------------------------------------------------------
# 2. LE SCEAU ET SA VERSION, CONSTATES
# --------------------------------------------------------------------------
etape "2/10  verification du sceau et de sa version"
LU=$(plan -tAc "select seal_version || '|' || installer_name || '|' || assurance_level
                  from normative_seal_metadata
                 order by installed_at asc, seal_version asc limit 1" 2>&1)
[[ "$LU" == *"|"* ]] || echec "le sceau ne declare ni version ni poseur: $LU"
SCEAU_VERSION="${LU%%|*}"; RESTE="${LU#*|}"
SCEAU_POSEUR="${RESTE%%|*}"; SCEAU_ASSURANCE="${RESTE#*|}"
constat "sceau « $SCEAU_VERSION », pose par « $SCEAU_POSEUR »"

# LE POSEUR DOIT ETRE CELUI QUI FINALISERA. La finalisation le refusera de
# toute facon (SEAL_INSTALLER_MISMATCH); le constater ici evite d'appliquer un
# schema entier avant de l'apprendre.
if [[ "$SCEAU_POSEUR" != "$PLAN_USER" ]]; then
  echec "le sceau de cette base a ete pose par « $SCEAU_POSEUR », et ce
       deploiement approuve au nom de « $PLAN_USER ». Le plan de controle
       d'une base est celui qui a pose sa racine: il ne se transfere pas.
       Deployez depuis « $SCEAU_POSEUR »."
fi

# LE NIVEAU D'ASSURANCE, TRANCHE ICI. En mode STRICT, un sceau pose par un
# superutilisateur est refuse: il n'offre pas les garanties du modele de
# menace, et le laisser passer en silence reviendrait a les annoncer.
if [[ "$SCEAU_ASSURANCE" != "CONTAINED_NON_SUPERUSER" ]]; then
  if ((STRICT)); then
    echec "niveau d'assurance « $SCEAU_ASSURANCE ».
       La phase 0 de cette base a ete posee par un SUPERUTILISATEUR: le sceau
       est en place, mais il ne contient pas celui qui l'a pose — aucun sceau
       ne le peut. Ce deploiement est legitime en auto-heberge, et il n'offre
       PAS l'assurance de la forme contenue.
       Pour l'accepter en connaissance de cause: --auto-heberge.
       Pour obtenir l'assurance: reposez la phase 0 depuis un role NON
       superutilisateur, sur une base neuve."
  fi
  echo "   AVERTISSEMENT: assurance « $SCEAU_ASSURANCE » — deploiement"
  echo "                  AUTO-HEBERGE, explicitement degrade."
else
  constat "assurance « $SCEAU_ASSURANCE »"
fi

# --------------------------------------------------------------------------
# LA BASE EST-ELLE DEJA FINALISEE ?
# --------------------------------------------------------------------------
# CE CONTROLE EST CE QUI REND LA RELANCE SURE, et son absence etait un vrai
# defaut de ce script: sur une base deja ACTIVE, l'etape 3 REACCORDAIT les
# emprunts au migrateur. La phase 1 refusait alors sur la topologie — le
# migrateur atteint un role d'autorite alors que le sous-systeme est ACTIF —
# et le diagnostic n'avait aucun rapport avec la cause. Pire: entre l'octroi et
# le refus, le migrateur detenait reellement ces roles sur une base en service.
#
# Une base ACTIVE ne recoit donc plus d'emprunt du tout: on saute directement
# aux constats.
DEJA=$(plan -tAc "select normative_activation_state()" 2>&1)
if [[ "$DEJA" == "ACTIVE" ]]; then
  echo
  echo "== la base est DEJA FINALISEE — aucun emprunt n'est reaccorde"
  echo "   Les etapes 3 a 7 sont sautees; les postconditions sont verifiees."
else
  if [[ "$DEJA" != "PENDING" ]]; then
    echec "etat de deploiement inattendu: « $DEJA »."
  fi

# --------------------------------------------------------------------------
# 3. LES EMPRUNTS, TEMPORAIRES
# --------------------------------------------------------------------------
# DEUX ROLES, ET NON TROIS: l'activateur n'est jamais prete — il possede la
# racine. Ces deux-la sont rendus par la phase 2, et c'est le but.
etape "3/10  octroi temporaire de writer/bootstrap a « $MIG_USER »"
SORTIE=$(plan -v ON_ERROR_STOP=1 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG_USER" with admin option;
grant eurostruct_normative_bootstrap to "$MIG_USER" with admin option;
SQL
) || echec "les emprunts n'ont pas pu etre accordes:
$(grep -m2 -E 'ERROR|FATAL' <<<"$SORTIE" | sed 's/^/       /')"
constat "emprunts accordes (ils seront rendus par la phase 2)"

# --------------------------------------------------------------------------
# 4. PHASE 1 — LES MIGRATIONS, PAR LE MIGRATEUR
# --------------------------------------------------------------------------
# LE REPERTOIRE ENTIER, SANS EXCEPTION. Depuis 6.3b6d, `db/migrations/` ne
# contient QUE ce que le migrateur applique: il n'y a plus rien a ignorer, et
# c'est ce qui rend cette boucle sure pour un outil quelconque.
etape "4/10  phase 1 — les migrations, par « $MIG_USER »"
for f in "$MIGRATIONS_DIR"/*.sql; do
  echo "   $(basename "$f")"
  SORTIE=$(mig -v ON_ERROR_STOP=1 -f "$f" 2>&1) \
    || echec "$(basename "$f") a ete refusee:
$(grep -m3 -E 'ERROR|FATAL|DETAIL' <<<"$SORTIE" | sed 's/^/       /')"
done
constat "phase 1 appliquee"

# --------------------------------------------------------------------------
# 5. CONSTAT: PENDING
# --------------------------------------------------------------------------
etape "5/10  constat de l'etat apres la phase 1"
ETAT=$(plan -tAc "select normative_activation_state()" 2>&1)
[[ "$ETAT" == "PENDING" ]] \
  || echec "la phase 1 ne se termine pas en PENDING (obtenu: $ETAT)."
constat "etat PENDING — le sous-systeme n'engage encore rien"

# --------------------------------------------------------------------------
# 6. LE MANIFESTE, LU ET APPROUVE
# --------------------------------------------------------------------------
# CE QUI EST APPROUVE EST CE QUI EST AFFICHE. Le manifeste est l'empreinte des
# TROIS declarations que la finalisation figera. Le lire ici, l'afficher, puis
# le representer a la finalisation est ce qui distingue une approbation d'un
# simple gel: si une declaration change entre les deux, la finalisation refuse.
etape "6/10  lecture du manifeste des declarations"
# LES DECLARATIONS SONT LUES DANS LE CATALOGUE, et non par
# `normative_declared_setting()`: cette fonction n'est accordee qu'aux deux
# roles empruntes et a l'activateur, jamais au plan de controle. Ce qui est
# affiche ici est exactement ce que `ALTER DATABASE ... SET` a pose — la meme
# source que celle sur laquelle le manifeste est calcule.
plan -tAc "
  select '   ' || d.nom || ' = ' || coalesce(
           (select split_part(s, '=', 2)
              from pg_db_role_setting r
              join pg_database b on b.oid = r.setdatabase
             cross join lateral unnest(r.setconfig) as u(s)
             where b.datname = current_database() and r.setrole = 0
               and split_part(s, '=', 1) = d.nom),
           '(non declaree)')
    from (values ('eurostruct.approved_deployment_roles'),
                 ('eurostruct.approved_service_logins'),
                 ('eurostruct.token_roles')) as d(nom)" 2>/dev/null || true
MANIFESTE=$(plan -tAc "select normative_settings_manifest()" 2>&1)
[[ "$MANIFESTE" =~ ^[0-9a-f]{64}$ ]] \
  || echec "le manifeste n'a pas pu etre lu: $MANIFESTE"
constat "manifeste $MANIFESTE"

# --------------------------------------------------------------------------
# 7-8. PHASE 2 — FINALISATION, PUIS CONSTAT
# --------------------------------------------------------------------------
etape "7/10  phase 2 — finalisation par « $PLAN_USER »"
SORTIE=$(plan -tAc "select normative_finalize_deployment('$MANIFESTE')" 2>&1)
if [[ $? -ne 0 ]] || grep -qE "^ERROR|^psql:" <<<"$SORTIE"; then
  echec "la finalisation a ete refusee:
$(grep -m3 -E 'ERROR|DETAIL' <<<"$SORTIE" | sed 's/^/       /')"
fi
constat "$(head -1 <<<"$SORTIE")"

fi   # fin du bloc « la base n'etait pas deja finalisee »

etape "8/10  constat de l'etat apres la phase 2"
ETAT=$(plan -tAc "select normative_activation_state()" 2>&1)
[[ "$ETAT" == "ACTIVE" ]] || echec "la phase 2 ne laisse pas la base ACTIVE (obtenu: $ETAT)."
constat "etat ACTIVE"

# --------------------------------------------------------------------------
# 9. POSTCONDITION: LE MIGRATEUR NE DETIENT PLUS RIEN
# --------------------------------------------------------------------------
# VERIFIEE, PAS AFFICHEE. C'est la propriete que la finalisation achete, et
# l'annoncer sans la constater serait exactement le defaut que tout ce jalon
# existe pour fermer. Les TROIS capacites, et les trois roles d'autorite.
etape "9/10  postcondition — capacites residuelles du migrateur"
RESIDU=$(plan -tAc "
  select coalesce(string_agg(a.r || ':' ||
           case when pg_has_role('$MIG_USER', a.r, 'SET') then 'SET ' else '' end ||
           case when pg_has_role('$MIG_USER', a.r, 'USAGE') then 'USAGE ' else '' end ||
           case when pg_has_role('$MIG_USER', a.r, 'MEMBER WITH ADMIN OPTION')
                then 'ADMIN' else '' end, '; '), '')
    from unnest(array['eurostruct_normative_writer',
                      'eurostruct_normative_bootstrap',
                      'eurostruct_normative_activator']) a(r)
   where pg_has_role('$MIG_USER', a.r, 'SET')
      or pg_has_role('$MIG_USER', a.r, 'USAGE')
      or pg_has_role('$MIG_USER', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
[[ -z "$RESIDU" ]] || echec "le migrateur « $MIG_USER » conserve des capacites: $RESIDU
       La base est ACTIVE, mais la separation n'est pas obtenue. N'exploitez
       pas ce deploiement en l'etat."
constat "zero capacite du migrateur sur les trois roles d'autorite"

# --------------------------------------------------------------------------
# 10. LA TRACE DE READINESS, AVEC SON NIVEAU ET SON MOTIF
# --------------------------------------------------------------------------
etape "10/10 readiness"
plan -tAc "select '   etat       : ' || etat
              || E'\n   sceau      : ' || sceau
              || E'\n   assurance  : ' || assurance
              || E'\n   plan       : ' || plan_de_controle
              || E'\n   topologie  : ' || topologie
              || E'\n   motif      : ' || motif
             from normative_deployment_readiness()" 2>&1
TOPO=$(plan -tAc "select topologie from normative_deployment_readiness()" 2>&1)
[[ "$TOPO" == "CONFORME" ]] || echec "la topologie de la base finalisee est REFUSEE.
       Voir le motif ci-dessus."
ASSURANCE=$(plan -tAc "select assurance from normative_deployment_readiness()" 2>&1)
[[ -n "$ASSURANCE" ]] || echec "le niveau d'assurance n'est pas persiste."

echo
echo "================================================="
if [[ "$ASSURANCE" == "CONTAINED_NON_SUPERUSER" ]]; then
  echo " « $BASE » deployee et finalisee — assurance CONTENUE."
else
  echo " « $BASE » deployee et finalisee — assurance $ASSURANCE."
  echo " Deploiement AUTO-HEBERGE, explicitement degrade: il n'offre pas"
  echo " l'assurance de la forme contenue. Ne le presentez pas comme tel."
fi
echo "================================================="
