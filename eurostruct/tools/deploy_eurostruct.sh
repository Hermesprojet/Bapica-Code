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
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e).
#
# L'ABSENCE DE CE FICHIER EST UN REFUS, pas un avertissement. Avec
# `set -uo pipefail` mais sans `-e`, un `source` qui echoue ne stoppe rien: le
# script poursuivait avec `esc_appliquer_migration` indefinie, chaque migration
# rendait « command not found » sur un code non nul, et le message d'echec
# etait VIDE. Defaut mesure en cablant ce fichier.
# shellcheck source=../db/apply_migration.sh
source "$RACINE/db/apply_migration.sh" 2>/dev/null
if ! declare -F esc_appliquer_migration >/dev/null; then
  echo "ECHEC: db/apply_migration.sh est introuvable ou illisible" >&2
  echo "       ($RACINE/db/apply_migration.sh). Sans lui, cette commande ne" >&2
  echo "       sait pas appliquer une migration ni consulter le registre." >&2
  exit 2
fi

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

# ==========================================================================
# HYGIENE DE CONNEXION — les PG* ambiantes ne decident de rien
# ==========================================================================
# libpq lit une douzaine de variables d'environnement. Certaines REDIRIGENT la
# connexion sans apparaitre dans l'URL: `PGSERVICE` et `PGSERVICEFILE` la font
# resoudre par un fichier de service, `PGHOSTADDR` remplace l'adresse tout en
# laissant `PGHOST` intact dans les messages, `PGPASSFILE` fournit un mot de
# passe, `PGOPTIONS` injecte des parametres de session — `search_path` compris.
#
# Un deploiement qui croit viser une base peut donc en atteindre une autre, et
# le compte rendu affichera la premiere. SEULS les parametres derives des deux
# URL decident: les autres sont EFFACES ici, avant la premiere connexion.
unset PGSERVICE PGSERVICEFILE PGPASSFILE PGOPTIONS PGDATABASE PGHOSTADDR \
      PGREQUIRESSL PGCHANNELBINDING PGSSLROOTCERT PGSSLCERT PGSSLKEY \
      PGHOST PGPORT PGUSER PGPASSWORD PGSSLMODE

echec()  { echo "ECHEC: $*" >&2; exit 1; }

# UN PREREQUIS NON TENU N'EST PAS UNE PANNE, ET SE DISTINGUE PAR UN CODE.
#
# Mesure (6.3b6e): le contre-exemple P2 acceptait n'importe quel echec dont la
# sortie contenait « prerequis » ou « eurostruct_deployment ». Or la chaine
# `eurostruct_deployment` figure dans un message de REUSSITE de l'etape 2b
# (« ok: eurostruct_deployment accorde a ... »). Retirer les deux garanties que
# P2 etait cense exercer le laissait donc vert: la commande echouait trois
# etapes plus loin, sur « permission denied for function
# normative_activation_state », et le mot cherche etait deja la. Le
# contre-exemple ne regardait pas OU le refus tombait.
#
# Ce que l'exploitant doit corriger — un droit a demander a un tiers — n'est pas
# ce qu'un incident demande. Le code 3 le dit, et le jeton le nomme; le texte ne
# sert qu'a l'affichage.
echec_prerequis() {
  echo "DEPLOYMENT_PRECONDITION_FAILED: $*" >&2
  exit 3
}
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

# ==========================================================================
# LES NOMS DE ROLES NE SONT JAMAIS INTERPOLES DANS DU SQL
# ==========================================================================
# `MIG_USER` vient de l'URL et etait ecrit tel quel dans
# `grant ... to "$MIG_USER"` et `pg_has_role('$MIG_USER', ...)`. Contre-exemple
# MESURE (db/test/deploy_recovery.sh, R1): un nom de la forme
#
#     <prefixe-existant>"; create role <temoin> nologin; --
#
# fermait l'identifiant et faisait executer l'instruction AVEC LES PRIVILEGES
# DU PLAN DE CONTROLE, qui porte CREATEROLE. Le role temoin etait cree.
#
# QUE L'URL VIENNE DE L'EXPLOITANT NE SUPPRIME PAS LE RISQUE: le migrateur est
# precisement l'acteur que le modele cherche a contenir, et son nom est ce que
# l'exploitant recopie d'une configuration qu'il n'a pas ecrite.
#
# DEUX MESURES, ET LES DEUX SONT NECESSAIRES:
#
#   1. TOUT SQL PASSE PAR LES FORMES SURES de psql — `:"nom"` pour un
#      identifiant, `:'texte'` pour un litteral. Elles citent et echappent cote
#      client, et ne peuvent pas etre sorties de leur contexte.
#      `psql -c` NE LES DEVELOPPE PAS (mesure): tout passe donc par un heredoc.
#
#   2. UNE BORNE, fail-closed. Un nom de plus de 63 octets est TRONQUE par
#      PostgreSQL — deux roles distincts pourraient devenir le meme — et un nom
#      portant un octet nul ou un saut de ligne n'a aucune raison d'exister.
#      Ce n'est pas la protection principale, c'est la ceinture.
borner_identifiant() {
  local quoi="$1" valeur="$2"
  if [[ ${#valeur} -eq 0 || ${#valeur} -gt 63 ]]; then
    echec "DEPLOYMENT_IDENTIFIER_REJECTED: le nom du $quoi fait ${#valeur}
       caracteres. PostgreSQL tronque les identifiants a 63 octets: deux noms
       qui ne different qu'au-dela du 63e octet designent LE MEME role, et le
       plan de controle deviendrait son propre migrateur sans que rien ne le
       montre — les deux CHAINES, elles, restent distinctes.
       Le jeton est la pour qu'un orchestrateur branche sur lui, et non sur ce
       texte."
  fi
  # PAS DE TEST SUR L'OCTET NUL, ET C'EST DELIBERE. `$'\0'` vaut la chaine
  # VIDE dans un motif bash: `*$'\0'*` devient `**`, qui accepte TOUT. Ecrit
  # ainsi, le controle refusait le premier nom venu — mesure: « le nom du plan
  # de controle contient un saut de ligne ou un octet nul » sur un role
  # parfaitement ordinaire. Une variable shell ne peut de toute facon pas
  # porter d'octet nul: la valeur serait tronquee bien avant d'arriver ici.
  if [[ "$valeur" == *$'\n'* || "$valeur" == *$'\r'* ]]; then
    echec "le nom du $quoi contient un saut de ligne."
  fi
}
borner_identifiant "plan de controle" "$PLAN_USER"
borner_identifiant "migrateur"        "$MIG_USER"
borner_identifiant "base"             "$BASE"

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

# ==========================================================================
# LA POLITIQUE TLS, EN MODE STRICT
# ==========================================================================
# `sslmode=disable`, `allow` et `prefer` acceptent une connexion EN CLAIR, et
# `require` chiffre sans verifier a qui l'on parle. Vers une cible distante,
# cela expose le mot de passe du plan de controle et laisse la porte ouverte a
# un interlocuteur substitue — c'est-a-dire a un « deploiement » qui scelle une
# base qui n'est pas la votre.
#
# UNE CIBLE DE BOUCLE LOCALE EST TRAITEE A PART, et ce n'est pas une
# complaisance: le trafic ne quitte pas la machine, et exiger un certificat
# verifiable de `localhost` rendrait la CI et tout poste de developpement
# indeployables sans rien protoger de plus.
cible_locale() {
  case "$PLAN_HOST" in
    localhost|127.0.0.1|::1|/*) return 0 ;;
    *) return 1 ;;
  esac
}
if ((STRICT)) && ! cible_locale; then
  case "$PLAN_SSLMODE" in
    verify-full|verify-ca) : ;;
    *)
      echec "cible distante « $PLAN_HOST » avec sslmode=$PLAN_SSLMODE.
       En mode strict, une connexion distante exige « verify-full » — ou au
       minimum « verify-ca » — et la chaine de confiance correspondante
       (PGSSLROOTCERT, ou le magasin du systeme).
         * disable / allow / prefer acceptent une connexion EN CLAIR: le mot de
           passe du plan de controle passerait en clair sur le reseau;
         * require chiffre sans verifier a QUI l'on parle: un interlocuteur
           substitue scellerait une base qui n'est pas la votre.
       Corrigez les deux URL, ou assumez explicitement: --auto-heberge." ;;
  esac
  [[ "$MIG_SSLMODE" == "$PLAN_SSLMODE" ]] \
    || echec "les deux URL n'ont pas la meme politique TLS
       (plan: $PLAN_SSLMODE, migrateur: $MIG_SSLMODE)."
  constat "TLS: $PLAN_SSLMODE vers « $PLAN_HOST »"
fi

# ==========================================================================
# LES IDENTITES OBTENUES, ET NON CELLES DEMANDEES
# ==========================================================================
# Comparer les chaines contenues dans les URL ne dit rien de la connexion
# reellement etablie: un fichier de service, un `PGHOSTADDR`, un
# `user=` dans `PGOPTIONS` ou un mappage `pg_ident` peuvent livrer une AUTRE
# identite ou une AUTRE base. Les variables ambiantes sont effacees plus haut;
# ce bloc constate le resultat plutot que de le supposer.
#
# `session_user` ET `current_user`: le premier est l'identite de connexion, le
# second peut differer apres un `SET ROLE` — pose par `PGOPTIONS`, ou par un
# `ALTER ROLE ... SET role`. Les deux doivent etre celle qu'on croit.
verifier_identite() {
  local role_attendu="$1" quoi="$2"; shift 2
  local obtenu
  obtenu=$("$@" -tA 2>/dev/null <<'SQL'
select session_user || '|' || current_user || '|' || current_database();
SQL
  )
  [[ -n "$obtenu" ]] || echec "le $quoi ne peut pas se connecter a « $BASE »."
  local su="${obtenu%%|*}" reste="${obtenu#*|}"
  local cu="${reste%%|*}" db="${reste##*|}"
  [[ "$su" == "$role_attendu" && "$cu" == "$role_attendu" ]] \
    || echec "le $quoi devait etre « $role_attendu »; la connexion obtenue est
       session_user=« $su », current_user=« $cu ». Une redirection est en jeu
       (fichier de service, pg_ident, PGOPTIONS, ALTER ROLE ... SET role)."
  [[ "$db" == "$BASE" ]] \
    || echec "le $quoi vise « $BASE » mais la connexion obtenue porte « $db »."
}
verifier_identite "$PLAN_USER" "plan de controle" plan
verifier_identite "$MIG_USER"  "migrateur"        mig
constat "identites constatees: « $PLAN_USER » et « $MIG_USER » sur « $BASE »"

[[ -f "$SCEAU" ]] || echec "le fichier de sceau est introuvable ($SCEAU)."

# ==========================================================================
# LE VERROU DE DEPLOIEMENT — tenu du debut a la fin
# ==========================================================================
# Le verrou consultatif de `normative_finalize_deployment()` protege la PHASE 2,
# et elle seule. La phase 0, les octrois, les migrations et la lecture du
# manifeste ne l'etaient pas: deux commandes lancees ensemble sur la meme base
# pouvaient intercaler leurs etapes et appliquer deux fois des migrations qui ne
# sont pas idempotentes.
#
# LA CLE EST CONSTANTE ET NON INTERPOLABLE. Les deux moities sont calculees PAR
# LE SERVEUR: un libelle fixe, et le nom de la base courante. Rien de ce que
# l'appelant fournit n'entre dans la cle — sans quoi deux invocations visant la
# meme base pourraient choisir deux verrous differents.
#
# LA BASE FAIT PARTIE DE LA CLE, et c'est necessaire: les verrous consultatifs
# sont globaux au cluster. Sans elle, deployer la base B attendrait la fin du
# deploiement de la base A, sur un cluster qui en porte plusieurs.
#
# IL EXIGE UNE CONNEXION PERSISTANTE. Un verrou de session vit dans sa session:
# le co-processus `psql` ci-dessous la tient ouverte pour toute la duree de la
# commande. DERRIERE PGBOUNCER EN MODE TRANSACTION, cela ne fonctionne pas —
# la session change a chaque transaction. Voir docs/DEPLOIEMENT_PREREQUIS.md.
VERROU_TENU=0
coproc VERROU { PGHOST="$PLAN_HOST" PGPORT="$PLAN_PORT" PGUSER="$PLAN_USER" \
                PGPASSWORD="$PLAN_PASSWORD" PGSSLMODE="$PLAN_SSLMODE" \
                psql -X -q -At -d "$BASE" 2>&1; }
if [[ -z "${VERROU_PID:-}" ]]; then
  echec "la session du verrou de deploiement n'a pas pu etre ouverte."
fi
echo "select pg_try_advisory_lock(hashtext('eurostruct.deploiement'),
                                  hashtext(current_database()))::text;" >&"${VERROU[1]}"
if ! read -r -t 30 -u "${VERROU[0]}" PRIS; then
  echec "aucune reponse du verrou de deploiement en 30 s."
fi
if [[ "$PRIS" != "true" ]]; then
  cat >&2 <<EOF
DEPLOYMENT_ALREADY_RUNNING: un autre deploiement de « $BASE » est en cours.

       Deux commandes simultanees appliqueraient deux fois des migrations qui
       ne sont pas idempotentes. Celle-ci s'arrete SANS RIEN MODIFIER.

       Relancez quand l'autre execution est terminee.
EOF
  exit 4
fi
VERROU_TENU=1

# --------------------------------------------------------------------------
# LA COMPENSATION — ce que la commande reprend si elle n'aboutit pas
# --------------------------------------------------------------------------
# A l'etape 3, la commande accorde au migrateur writer et bootstrap AVEC ADMIN
# OPTION. Sans ce piege, toute erreur ensuite — une migration refusee, une
# lecture de manifeste impossible, un `Ctrl-C` — laissait le migrateur capable
# d'ENDOSSER et de READMINISTRER les roles d'autorite sur une base en cours de
# deploiement. Contre-exemples mesures: db/test/deploy_recovery.sh, Q1 a Q5.
#
# ELLE NE REVOQUE QUE CE QU'ELLE A ACCORDE. C'est la raison de la precondition
# « zero capacite avant octroi »: si le migrateur detenait deja une
# appartenance, la reprendre ici detruirait un octroi que quelqu'un d'autre a
# pose, pour une raison qu'on ignore.
#
# ELLE NE SE DECLENCHE PAS APRES UNE FINALISATION REUSSIE: la phase 2 a deja
# revoque, et le piege ne fait alors que constater.
EMPRUNTS_ACCORDES=0
FINALISE=0
NETTOYAGE_ECHOUE=0

capacites_du_migrateur() {
  plan -tA -v m="$MIG_USER" 2>/dev/null <<'SQL'
select coalesce(string_agg(a.r || '(' ||
    case when pg_has_role(:'m', a.r, 'SET') then 'SET ' else '' end ||
    case when pg_has_role(:'m', a.r, 'USAGE') then 'USAGE ' else '' end ||
    case when pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION')
         then 'ADMIN' else '' end || ')', ' '), '')
  from unnest(array['eurostruct_normative_writer',
                    'eurostruct_normative_bootstrap',
                    'eurostruct_normative_activator']) a(r)
 where pg_has_role(:'m', a.r, 'SET')
    or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
}

revoquer_les_emprunts() {
  plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" >/dev/null 2>&1 <<'SQL'
revoke eurostruct_normative_writer    from :"m";
revoke eurostruct_normative_bootstrap from :"m";
SQL
  capacites_du_migrateur
}

sortie_compensee() {
  local code=$?
  local reste
  trap - EXIT
  if [[ $EMPRUNTS_ACCORDES -eq 1 && $FINALISE -eq 0 ]]; then
    echo
    echo "== compensation — les emprunts accordes a l'etape 3 sont repris"
    reste=$(revoquer_les_emprunts)
    if [[ -n "$reste" ]]; then
      NETTOYAGE_ECHOUE=1
      cat >&2 <<EOF
DEPLOYMENT_CLEANUP_FAILED: les emprunts n'ont PAS pu etre repris.

       « $MIG_USER » conserve: $reste

       La base n'est pas finalisee ET le migrateur reste capable d'endosser ou
       de readministrer les roles d'autorite. N'EXPLOITEZ PAS CETTE BASE en
       l'etat. Revoquez a la main, depuis « $PLAN_USER »:

           REVOKE eurostruct_normative_writer, eurostruct_normative_bootstrap
             FROM <migrateur>;
EOF
    else
      echo "   ok: aucune capacite residuelle du migrateur"
    fi
  fi
  if [[ $VERROU_TENU -eq 1 && -n "${VERROU_PID:-}" ]]; then
    # Fermer l'entree du co-processus termine `psql`, donc la session, donc le
    # verrou. Aucun `pg_advisory_unlock` explicite: on veut que la liberation
    # tienne aussi quand le script meurt sans passer par ici.
    #
    # LE DESCRIPTEUR EST FERME PAR SON NUMERO, via `eval`. Bash n'accepte la
    # forme `exec {nom}>&-` qu'avec un nom SIMPLE: avec un indice de tableau,
    # le mot est pris pour un nom de COMMANDE, et `exec` remplace alors le
    # shell — qui meurt sur-le-champ, sans un mot. Defaut mesure en 6.3b6a.
    eval "exec ${VERROU[1]}>&-" 2>/dev/null || true
    wait "$VERROU_PID" 2>/dev/null || true
    VERROU_TENU=0
  fi
  [[ $NETTOYAGE_ECHOUE -eq 1 ]] && exit 5
  exit $code
}
trap sortie_compensee EXIT
# ET SUR SIGNAL. Sans cela, TERM, INT ou HUP tuent bash AVANT le piege de
# sortie: le migrateur garderait ses emprunts, et le verrou serait relache par
# la mort de la session sans que rien ne soit repris. Mesure: 6.3b6e, Q5.
trap 'echo; echo "== interruption (TERM) — compensation"; exit 130' TERM
trap 'echo; echo "== interruption (INT) — compensation";  exit 130' INT
trap 'echo; echo "== interruption (HUP) — compensation";  exit 130' HUP

# --------------------------------------------------------------------------
# 1. PHASE 0 — LE SCEAU, PAR LE PLAN DE CONTROLE
# --------------------------------------------------------------------------
etape "1/10  phase 0 — le sceau, par « $PLAN_USER »"
# `VERBOSITY=verbose` FAIT PREFIXER LE SQLSTATE AU MESSAGE:
#
#     ERROR:  ES001: le sceau « ... » est deja pose ...
#
# C'est ce qui permet de brancher sur le CODE. Le fichier du sceau porte des
# SQLSTATE dedies depuis 6.3b6d, mais cette commande branchait encore sur le
# TEXTE — `grep SEAL_ALREADY_INSTALLED` —, c'est-a-dire sur de la prose. Un
# message se reformule, se traduit, se raccourcit; un code non.
SORTIE=$(plan -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -f "$SCEAU" 2>&1)
CODE=$?
# LE MOTIF N'EST PAS ANCRE EN DEBUT DE LIGNE, et c'est necessaire: quand psql
# lit un FICHIER (`-f`), il prefixe ses diagnostics par
# `psql:<fichier>:<ligne>: `. Ancre sur `^ERROR:`, le controle ne trouvait
# jamais rien — mesure: la relance de la phase 0 tombait dans la branche
# generique « la phase 0 a ete refusee » au lieu d'etre reconnue comme
# SEAL_ALREADY_INSTALLED, et cinq scenarios de reprise rougissaient.
sqlstate() { grep -qE "(^|: )ERROR:  $1:" <<<"$SORTIE"; }
if [[ $CODE -ne 0 ]]; then
  # ES001 N'EST PAS UNE ERREUR DE DEPLOIEMENT. C'est le resultat normal d'une
  # phase 0 rejouee — apres une coupure reseau, par exemple. Le branchement ne
  # se fait pas sur le code de sortie de psql, qui vaut 3 pour toute exception.
  if sqlstate ES001; then
    constat "le sceau etait deja pose dans cette version — rien n'a ete modifie"
  elif sqlstate ES002; then
    echec "cette base porte un sceau d'une AUTRE version.
       $(grep -m1 -oE 'SEAL_VERSION_MISMATCH.{0,200}' <<<"$SORTIE")
       Un sceau ne se remplace pas: appliquez la mise a niveau prevue dans
       db/control_plane/, ou redeployez la base depuis une base neuve."
  elif sqlstate ES003; then
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
# --------------------------------------------------------------------------
# 2b. LE ROLE DE DEPLOIEMENT — constate, et accorde si besoin
# --------------------------------------------------------------------------
# `eurostruct_deployment` n'existe qu'APRES la phase 0: personne ne peut le
# detenir avant le premier appel de cette commande. Sans ce bloc, la commande
# s'arretait ici sur « permission denied for function
# normative_activation_state » — une erreur brute, presentee comme un « etat de
# deploiement inattendu ».
#
# LE PARCOURS REEL ETAIT DONC: appeler, ignorer l'echec, accorder le role a la
# main, rappeler. Le harnais le decrivait sans le nommer. UN ECHEC UTILISE
# COMME MECANISME DE PROGRESSION N'EN EST PAS UN.
#
# LA CAPACITE EXISTE, et c'est ce qui rend ce bloc possible: PostgreSQL 16
# donne au CREATEUR d'un role un ADMIN residuel (fait F1), et c'est le plan de
# controle qui cree les six roles en phase 0. Il peut donc se l'accorder.
#
# SI LES ROLES PREEXISTENT et que personne ne lui a donne cet ADMIN, le refus
# tombe ICI — nomme, et AVANT que writer/bootstrap ne soient pretes au
# migrateur.
etape "2b/10 le role de deploiement"
if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'USAGE')::text" 2>/dev/null)" == "true" ]]; then
  constat "« $PLAN_USER » detient deja eurostruct_deployment"
else
  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'MEMBER WITH ADMIN OPTION')::text" 2>/dev/null)" != "true" ]]; then
    echec_prerequis "« $PLAN_USER » ne detient ni eurostruct_deployment
       ni l'ADMIN OPTION qui lui permettrait de se l'accorder.
       C'est le cas quand les six roles canoniques PREEXISTENT, provisionnes
       par un tiers. Faites accorder, par leur createur:

           GRANT eurostruct_deployment TO \"$PLAN_USER\" WITH ADMIN OPTION;

       Aucun emprunt n'a ete accorde au migrateur."
  fi
  plan -v ON_ERROR_STOP=1 -v p="$PLAN_USER" >/dev/null 2>&1 <<'SQL'
grant eurostruct_deployment to :"p" with inherit true;
SQL
  # CONSTATE, ET NON SUPPOSE. Un `GRANT` sans effet emet un simple
  # avertissement: sans ce controle, la commande poursuivrait et echouerait
  # trois etapes plus loin, sur un diagnostic sans rapport.
  if [[ "$(plan -tAc "select pg_has_role(current_user, 'eurostruct_deployment', 'USAGE')::text" 2>/dev/null)" != "true" ]]; then
    echec_prerequis "l'octroi de eurostruct_deployment a « $PLAN_USER » n'a
       pas pris. Aucun emprunt n'a ete accorde au migrateur."
  fi
  constat "eurostruct_deployment accorde a « $PLAN_USER »"
fi

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
# LA PRECONDITION: LE MIGRATEUR NE DETIENT RIEN.
#
# Elle n'est pas decorative — c'est ELLE qui autorise la compensation a
# revoquer. Sans elle, un migrateur deja membre verrait son appartenance
# DETRUITE par le piege de sortie, alors que quelqu'un d'autre l'avait posee
# pour une raison qu'on ignore. On ne reprend que ce qu'on a donne.
DEJA_DETENU=$(capacites_du_migrateur)
if [[ -n "$DEJA_DETENU" ]]; then
  echec_prerequis "« $MIG_USER » detient deja des capacites sur les
       roles d'autorite: $DEJA_DETENU
       Cette commande n'accorde des emprunts que si elle peut les reprendre, et
       elle ne reprend que ce qu'elle a donne. Revoquez ces appartenances —
       depuis le role qui les a accordees — puis relancez.
       Aucun emprunt supplementaire n'a ete accorde."
fi

etape "3/10  octroi temporaire de writer/bootstrap a « $MIG_USER »"
SORTIE=$(plan -v ON_ERROR_STOP=1 -v m="$MIG_USER" 2>&1 <<'SQL'
grant eurostruct_normative_writer    to :"m" with admin option;
grant eurostruct_normative_bootstrap to :"m" with admin option;
SQL
) || echec "les emprunts n'ont pas pu etre accordes:
$(grep -m2 -E 'ERROR|FATAL' <<<"$SORTIE" | sed 's/^/       /')"
# A PARTIR D'ICI, TOUTE SORTIE PASSE PAR LA COMPENSATION.
EMPRUNTS_ACCORDES=1
constat "emprunts accordes (ils seront rendus par la phase 2)"

# --------------------------------------------------------------------------
# 4. PHASE 1 — LES MIGRATIONS, PAR LE MIGRATEUR
# --------------------------------------------------------------------------
# LE REPERTOIRE ENTIER, SANS EXCEPTION. Depuis 6.3b6d, `db/migrations/` ne
# contient QUE ce que le migrateur applique: il n'y a plus rien a ignorer, et
# c'est ce qui rend cette boucle sure pour un outil quelconque.
etape "4/10  phase 1 — les migrations, par « $MIG_USER »"
APPLIQUEES=0; SAUTEES=0
for f in "$MIGRATIONS_DIR"/*.sql; do
  esc_appliquer_migration "$f" mig
  case $? in
    0) if [[ "$ESC_MIGRATION_ETAT" == "SAUTEE" ]]; then
         SAUTEES=$((SAUTEES + 1)); echo "   $(basename "$f")  — deja appliquee"
       else
         APPLIQUEES=$((APPLIQUEES + 1)); echo "   $(basename "$f")"
       fi ;;
    6) echec "$ESC_MIGRATION_SORTIE" ;;
    # LE MOTIF EST REPRIS TEL QUEL QUAND IL N'Y A PAS DE LIGNE `ERROR`.
    # Un filtre sur ERROR/FATAL/DETAIL rendait un message VIDE quand l'echec
    # venait de l'applicateur lui-meme — registre injoignable, par exemple —
    # et l'exploitant lisait « 0001 a ete refusee: » suivi de rien.
    *) echec "$(basename "$f") a ete refusee:
$( { grep -m3 -E 'ERROR|FATAL|DETAIL' <<<"$ESC_MIGRATION_SORTIE" \
       || grep -m3 -v '^[[:space:]]*$' <<<"$ESC_MIGRATION_SORTIE"; } | sed 's/^/       /')" ;;
  esac
done
constat "phase 1: $APPLIQUEES appliquee(s), $SAUTEES deja inscrite(s)"

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
plan -tA 2>/dev/null <<'SQL' || true
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
               ('eurostruct.token_roles')) as d(nom);
SQL
MANIFESTE=$(plan -tAc "select normative_settings_manifest()" 2>&1)
[[ "$MANIFESTE" =~ ^[0-9a-f]{64}$ ]] \
  || echec "le manifeste n'a pas pu etre lu: $MANIFESTE"
constat "manifeste $MANIFESTE"

# --------------------------------------------------------------------------
# 7-8. PHASE 2 — FINALISATION, PUIS CONSTAT
# --------------------------------------------------------------------------
etape "7/10  phase 2 — finalisation par « $PLAN_USER »"
SORTIE=$(plan -tA -v man="$MANIFESTE" 2>&1 <<'SQL'
select normative_finalize_deployment(:'man');
SQL
)
if [[ $? -ne 0 ]] || grep -qE "^ERROR|^psql:" <<<"$SORTIE"; then
  echec "la finalisation a ete refusee:
$(grep -m3 -E 'ERROR|DETAIL' <<<"$SORTIE" | sed 's/^/       /')"
fi
constat "$(head -1 <<<"$SORTIE")"

fi   # fin du bloc « la base n'etait pas deja finalisee »

etape "8/10  constat de l'etat apres la phase 2"
ETAT=$(plan -tAc "select normative_activation_state()" 2>&1)
[[ "$ETAT" == "ACTIVE" ]] || echec "la phase 2 ne laisse pas la base ACTIVE (obtenu: $ETAT)."
# LA PHASE 2 A REVOQUE LES EMPRUNTS ELLE-MEME: la compensation n'a plus rien a
# reprendre, et se declencher ici reviendrait a revoquer deux fois — donc a
# emettre un avertissement PostgreSQL sur une base parfaitement saine.
FINALISE=1
constat "etat ACTIVE"

# --------------------------------------------------------------------------
# 9. POSTCONDITION: LE MIGRATEUR NE DETIENT PLUS RIEN
# --------------------------------------------------------------------------
# VERIFIEE, PAS AFFICHEE. C'est la propriete que la finalisation achete, et
# l'annoncer sans la constater serait exactement le defaut que tout ce jalon
# existe pour fermer. Les TROIS capacites, et les trois roles d'autorite.
etape "9/10  postcondition — capacites residuelles du migrateur"
RESIDU=$(capacites_du_migrateur)
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
