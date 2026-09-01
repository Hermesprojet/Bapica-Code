#!/usr/bin/env bash
#
# EUROSTRUCT — ENTRER DANS L'APPLICATION, DEPUIS UN VRAI NAVIGATEUR
#
#   db/test/parcours_entree.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS ETABLIT, ET QUE `entree_application.sh` NE PEUT PAS
# -----------------------------------------------------------------------
# `entree_application.sh` prouve que les huit primitives et les huit routes
# tiennent sous identite verifiee, et que PostgreSQL cloisonne. Il construit
# ses en-tetes lui-meme: il ne dit RIEN de ce que l'ECRAN montre a quelqu'un
# qui arrive, ni de ce qu'il peut faire avec sa souris.
#
# Et c'est exactement la qu'etait le defaut: le produit REFUSAIT correctement,
# et n'offrait aucune porte. Un cul-de-sac ne se voit pas dans une suite d'API;
# il se voit sur un ecran.
#
# LE DECOR NE POSE AUCUNE ORGANISATION, ET C'EST TOUT L'OBJET. Trois identites
# dans `auth.users`, une Annexe Nationale, et rien d'autre. Le bureau, les
# adhesions et les invitations sont crees PAR L'ECRAN.
#
# LES QUATORZE FAITS
# -------------------
#   1. F se connecte, et son ecran dit qu'il n'appartient a aucun bureau —
#      avec exactement deux portes, pas un selecteur vide;
#   2. il cree son organisation depuis l'ecran, et en devient `owner`;
#   3. le meme geste repete ne fonde pas un second bureau;
#   4. il cree un projet — le geste meme qui refusait avant;
#   5. il emet une invitation `engineer`; le secret apparait a l'ecran, UNE
#      fois;
#   6. la liste des invitations ne porte ni le secret ni son empreinte;
#   7. apres un RECHARGEMENT COMPLET, le secret n'est plus nulle part — ni
#      dans la page, ni dans le stockage du navigateur;
#   8. I se connecte, voit les deux memes portes, colle le lien, et entre avec
#      le role que l'invitation portait;
#   9. le meme lien, presente une seconde fois par X, est refuse;
#  10. I, `engineer`, ne voit aucun panneau d'administration — et l'ecran dit
#      pourquoi, comme la route;
#  11. F produit un brouillon et le telecharge: le sha256 des octets RECUS PAR
#      LE NAVIGATEUR est celui que la base a enregistre;
#  12. F promeut I `validating_engineer`, et I le voit a sa reconnexion;
#  13. F desactive I: la ligne survit a l'ecran, et I ne voit plus le bureau;
#  14. F n'a aucun bouton sur sa propre ligne, et la route le refuse aussi —
#      pas plus qu'elle ne laisse disparaitre le dernier proprietaire actif.
#
# CE QUE CE PARCOURS N'EPROUVE PAS, ET QUI EST DIT
# -------------------------------------------------
# Le magasin OBJET. Il tourne sur le magasin local — meme code de route, meme
# verification d'empreinte — parce qu'un MinIO reel exige un demon Docker que
# ce harnais ne suppose pas. Le protocole S3 a son propre harnais,
# `db/test/stockage_s3.sh`, en huit etapes contre un serveur reel.
#
# Le calcul est EXPLORATOIRE: ouvrir le mode strict demande le quatre-yeux,
# eprouve par `parcours_entree.sh`. Le livrable produit porte donc
# « PROJET — NON SIGNABLE », et c'est vrai.
#
# LES COMPTES SONT EXPLICITEMENT FICTIFS ET VIVENT DANS UNE BASE JETABLE.
# Le registre national reste a 0/29 et `SUPABASE_UNVERIFIED` reste vrai.
#
# SANS NAVIGATEUR NI DEPENDANCE, IL REND 4 — NON EXECUTE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: parcours_entree.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "parcours_entree.sh" || exit 2
harnais_verrou_prendre  "parcours_entree.sh" || exit $?
exiger_cluster_jetable  "parcours_entree.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)
exiger_roles_absents "parcours_entree.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_me_${JETON}"; CTL="${PREFIXE}_ce_${JETON}"
SVC="${PREFIXE}_se_${JETON}"; BASE="${PREFIXE}_de_${JETON}"
MDP="FICTIF-enw-${JETON}"
MANDAT="11111111-6666-6666-6666-666666666601:FICTIF-EMPREINTE-ENW-${JETON}"
#: TROIS IDENTITES, ET AUCUNE N'APPARTIENT A QUOI QUE CE SOIT AU DEPART.
#:
#: F — la fondatrice: elle cree son bureau depuis l'ecran, et en devient owner.
#: I — l'invitee: elle rejoint par un lien, jamais autrement.
#: X — l'opportuniste: il essaie le lien deja consomme.
ACTEUR_F="22222222-6666-6666-6666-66666666fff1"
ACTEUR_I="22222222-6666-6666-6666-66666666aaa1"
ACTEUR_X="22222222-6666-6666-6666-66666666ccc1"
RACINE_ID="11111111-6666-6666-6666-666666666601"

# LES PORTS SONT DECALES DES PORTS DE DEVELOPPEMENT. Se lier a 3000 ou 8000
# ferait echouer le harnais quand un serveur de developpement tourne — ou pire,
# le ferait piloter CE serveur-la, avec un autre code que celui du depot.
PORT_AUTH="${EUROSTRUCT_E2E_PORT_AUTH_ENT:-54351}"
PORT_API="${EUROSTRUCT_E2E_PORT_API_ENT:-8031}"
PORT_WEB="${EUROSTRUCT_E2E_PORT_WEB_ENT:-3031}"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

# LES PID SONT CAPTURES AU LANCEMENT, ET C'EST LA SEULE FACON CORRECTE.
# `pkill -f` reconnait sa propre ligne de commande et tue le shell qui
# l'invoque — mesure, et coute une session entiere. On tue donc par PID exact,
# et les enfants par PID DU PERE (`pkill -P`), qui ne compare aucun motif.
PID_AUTH=""; PID_API=""; PID_WEB=""
TMP="$(mktemp -d)"
#: LE MAGASIN D'OBJETS, CREE PAR CE HARNAIS. `mktemp -d` en prouve la
#: creation: sa destruction ne repose sur aucun motif large.
#: IL EST DISTINCT DE `$TMP`, qui porte les journaux: le repertoire de
#: telechargement de Chromium y ecrit aussi, et melanger les deux rendrait le
#: comptage des objets faux.
MAGASIN="$(mktemp -d)"

# TUER LE PERE NE SUFFIT PAS, ET CA A COUTE UN DIAGNOSTIC ENTIER.
#
# `( cd … && npx next start ) &` fait de `$!` le PID du SOUS-SHELL. Le tuer
# laisse `npm exec` -> `sh -c` -> `next-server` vivants, reparentes a init, et
# TOUJOURS EN ECOUTE. L'execution suivante ne pouvait alors pas se lier au
# port: elle pilotait le serveur PRECEDENT, qui servait un build perime.
# Symptome observe: un chunk 500/404 et un ecran sans bouton, quinze secondes
# plus tard un delai qui parlait de Playwright et jamais de la cause.
tuer_arbre() {   # tuer_arbre <pid>
  local p="$1" i
  [[ -n "$p" ]] || return 0
  pkill -TERM -P "$p" 2>/dev/null
  kill -TERM "$p" 2>/dev/null
  for ((i = 0; i < 20; i++)); do
    kill -0 "$p" 2>/dev/null || break
    sleep 0.25
  done
  pkill -KILL -P "$p" 2>/dev/null
  kill -KILL "$p" 2>/dev/null
  return 0
}

NETTOYAGE_KO=0
sortie_propre() {
  local r p
  for p in "$PID_WEB" "$PID_API" "$PID_AUTH"; do
    tuer_arbre "$p"
  done
  rm -rf "$TMP"
  [[ -n "$MAGASIN" && -d "$MAGASIN" ]] && rm -rf -- "$MAGASIN"
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "parcours_entree.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

# ---------------------------------------------------------------------------
# LES OUTILS SONT VERIFIES AVANT DE POSER QUOI QUE CE SOIT. Poser un decor
# complet pour decouvrir ensuite qu'on ne peut pas s'en servir gaspille une
# minute et brouille le diagnostic.
# ---------------------------------------------------------------------------
MANQUANTS=""
python3 -c "import psycopg2"  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS psycopg2"
python3 -c "import uvicorn"   >/dev/null 2>&1 || MANQUANTS="$MANQUANTS uvicorn"
python3 -c "import jwt"       >/dev/null 2>&1 || MANQUANTS="$MANQUANTS pyjwt"
python3 -c "import eurostruct_api" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS eurostruct-api"
command -v node >/dev/null 2>&1 || MANQUANTS="$MANQUANTS node"
command -v npm  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS npm"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: parcours_entree.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Le parcours navigateur ne peut pas etre eprouve, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  exit 4
fi
if ! node "$RACINE/web/e2e/verifier_navigateur.mjs" >/dev/null 2>&1; then
  echo "NON EXECUTE: parcours_entree.sh — Playwright ou Chromium absent." >&2
  exit 4
fi

# AUCUN DES TROIS PORTS NE DOIT DEJA REPONDRE.
#
# S'il repond, c'est un autre processus — un serveur de developpement, ou le
# residu d'une execution precedente. On ne peut alors pas se lier au port, et
# le parcours pilote CE serveur-la: un autre code que celui du depot, un verdict
# qui ne dit rien du candidat. Un refus ici vaut mieux qu'un vert menteur.
for duo in "$PORT_AUTH:emetteur local" "$PORT_API:API" "$PORT_WEB:interface"; do
  PORT="${duo%%:*}"; QUOI="${duo##*:}"
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT" 2>/dev/null; then
    echo "      ECHEC: le port $PORT ($QUOI) repond deja." >&2
    echo "             Un parcours lance maintenant piloterait CE serveur, pas" >&2
    echo "             celui construit depuis le depot. Arretez-le, ou posez" >&2
    echo "             EUROSTRUCT_E2E_PORT_{AUTH,API,WEB}." >&2
    exit 2
  fi
done

echo "    tranche applicative: entrer dans l'application, par un navigateur"

# ---------------------------------------------------------------------------
# 1. LA BASE
# ---------------------------------------------------------------------------
creer_role "$MIG" "login password '$MDP' createrole createdb" || exit 1
creer_role "$CTL" "login password '$MDP' createrole"          || exit 1
creer_role "$SVC" "login password '$MDP'"                     || exit 1
adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
creer_base "$BASE" "owner \"$MIG\"" || exit 1
registre_base "$BASE"

admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL

if ! SORTIE=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
  echo "      ECHEC: phase 0: $(grep -m1 ERROR <<<"$SORTIE" | cut -c1-160)" >&2
  exit 1
fi
adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1

for f in "$DB_DIR"/migrations/*.sql; do
  if ! esc_appliquer_migration "$f" mig; then
    echo "      ECHEC: $(basename "$f"):" >&2
    esc_diag_rapporter "phase 1 / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ECHEC: la base n'est pas ACTIVE ($ETAT)" >&2
  exit 1
fi

ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1

# LE DECOR: TROIS IDENTITES, ZERO ORGANISATION, ZERO ADHESION.
#
# C'EST TOUT L'OBJET DE CE HARNAIS. Les autres parcours posent d'avance les
# bureaux et les adhesions dont ils ont besoin; aucun ne pouvait donc constater
# qu'on ne savait pas les creer depuis l'ecran. Ici, le bureau, les adhesions
# et les invitations sont crees PAR L'INTERFACE, avec une souris.
#
# L'ANNEXE NATIONALE, EN REVANCHE, EST NECESSAIRE: sans elle la creation d'un
# projet refuserait pour une raison sans rapport avec l'appartenance, et le
# fait n. 4 serait rouge — ou vert — pour la mauvaise raison. Le decor pose le
# DOCUMENT, jamais ses valeurs.
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values
  ('$RACINE_ID'),('$ACTEUR_F'),('$ACTEUR_I'),('$ACTEUR_X')
on conflict do nothing;
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL

# LE DECOR EST CONSTATE, PAS SUPPOSE — et ce qu'on constate ici est surtout
# une ABSENCE: si une organisation existait deja, le parcours serait vert sans
# rien prouver.
NB_USR=$(q "select count(*) from auth.users")
NB_ORG=$(q "select count(*) from organizations")
NB_MEM=$(q "select count(*) from organization_members")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_USR" != "4" || "$NB_ORG" != "0" || "$NB_MEM" != "0"
      || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor n'est pas celui qu'on croit." >&2
  echo "             identites=$NB_USR organisations=$NB_ORG" >&2
  echo "             adhesions=$NB_MEM annexes_BE=$NB_ANX" >&2
  echo "             (organisations et adhesions doivent etre a ZERO.)" >&2
  exit 1
fi

# LA RACINE D'AUTORITE EST AMORCEE, ET ELLE NE SERT PAS ICI.
#
# Le calcul de ce parcours est EXPLORATOIRE: ouvrir le mode strict demande le
# quatre-yeux, eprouve par `parcours_livrable.sh`. On amorce quand meme la
# racine parce qu'une base ACTIVE sans racine refuse toute route d'autorite, et
# que l'ecran en interroge une au chargement — un 503 la ferait crier dans la
# console, et le parcours accuserait l'interface.
ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine entree web')" \
  >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: aucune racine amorcee." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. L'EMETTEUR LOCAL
# ---------------------------------------------------------------------------
# DEUX COMPTES, UN PAR ORGANISATION. C'est le minimum pour eprouver
# l'isolation: un seul acteur ne peut pas prouver qu'il est empeche d'aller
# ailleurs, faute d'un ailleurs. Les comptes a jeton court du parcours
# d'autorite n'ont pas d'objet ici — ce parcours-la eprouve la session, celui-ci
# eprouve le travail.
export EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH"
export EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://127.0.0.1:$PORT_AUTH/auth/v1"
export EUROSTRUCT_E2E_COMPTES="f@fictif.invalid:FICTIF-F:$ACTEUR_F:3600:oui,i@fictif.invalid:FICTIF-I:$ACTEUR_I:3600:oui,x@fictif.invalid:FICTIF-X:$ACTEUR_X:3600:oui"
# L'IDENTITE DE BUILD DU HARNAIS.
#
# La persistance la REFUSE quand elle manque: un calcul conserve doit designer
# le code exact qui l'a produit, et « 0.3.0 » ne le fait pas. Le harnais en
# declare donc une, derivee du jeton de l'execution — deux executions du meme
# harnais sont deux builds distincts pour ce qui nous occupe, et c'est
# exactement ce que le cas « meme requete, autre build » exploite.
export EUROSTRUCT_BUILD_SHA="FICTIF-build-${JETON}"
export EUROSTRUCT_E2E_ACTEUR_F="$ACTEUR_F"
export EUROSTRUCT_E2E_ACTEUR_I="$ACTEUR_I"
export EUROSTRUCT_E2E_ACTEUR_X="$ACTEUR_X"
# LE MAGASIN D'OBJETS DU SERVICE. Sans lui, la creation d'un livrable refuse
# par un 503 qui nomme la variable — ce qui est le comportement juste, et l'un
# des cas du harnais applicatif. Ici, on veut le parcours nominal.
export EUROSTRUCT_STORAGE_DIR="$MAGASIN"
# LE REPERTOIRE OU CHROMIUM DEPOSE CE QU'IL TELECHARGE. Distinct du magasin:
# le parcours compare les octets RECUS a ceux ECRITS, et les confondre ferait
# comparer un fichier avec lui-meme.
export EUROSTRUCT_E2E_TELECHARGEMENTS="$TMP/telechargements"
mkdir -p "$EUROSTRUCT_E2E_TELECHARGEMENTS"

node "$RACINE/web/e2e/supabase_local.mjs" >"$TMP/auth.log" 2>&1 &
PID_AUTH=$!
attendre_url() {   # attendre_url <url> <secondes> <pid>
  local i
  for ((i = 0; i < $2 * 2; i++)); do
    kill -0 "$3" 2>/dev/null || return 1
    curl -fsS --max-time 2 "$1" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}
if ! attendre_url "http://127.0.0.1:$PORT_AUTH/jwks" 20 "$PID_AUTH"; then
  echo "      ECHEC: l'emetteur local n'a pas demarre." >&2
  sed -n '1,20p' "$TMP/auth.log" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. L'API
# ---------------------------------------------------------------------------
# LA DSN NE TRANSITE QUE PAR L'ENVIRONNEMENT du sous-processus: ni argument, ni
# fichier, ni sortie. `ps` ne la montrera pas.
API_ENV=(
  "EUROSTRUCT_DATABASE_URL=dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
  "EUROSTRUCT_SUPABASE_JWKS_URL=http://127.0.0.1:$PORT_AUTH/jwks"
  "EUROSTRUCT_SUPABASE_ISSUER=http://127.0.0.1:$PORT_AUTH/auth/v1"
  "EUROSTRUCT_SUPABASE_AUDIENCE=authenticated"
  "EUROSTRUCT_JWT_ALGORITHMS=RS256"
  "EUROSTRUCT_JWT_LEEWAY_S=0"
  "EUROSTRUCT_CORS_ORIGINS=http://localhost:$PORT_WEB,http://127.0.0.1:$PORT_WEB"
)
env "${API_ENV[@]}" python3 -m uvicorn eurostruct_api.app:app \
    --host 127.0.0.1 --port "$PORT_API" --log-level warning \
    >"$TMP/api.log" 2>&1 &
PID_API=$!
if ! attendre_url "http://127.0.0.1:$PORT_API/health" 40 "$PID_API"; then
  echo "      ECHEC: l'API n'a pas demarre sur le port $PORT_API." >&2
  sed -n '1,30p' "$TMP/api.log" >&2
  exit 1
fi
# `/ready` DOIT ETRE VERT AVANT DE PILOTER L'ECRAN. Sans lui, un parcours rouge
# ne distinguerait pas « l'interface n'envoie pas le jeton » de « la base n'est
# pas la ».
PRET=$(curl -fsS --max-time 10 "http://127.0.0.1:$PORT_API/ready" 2>&1)
if ! grep -q '"ready":true' <<<"$PRET"; then
  echo "      ECHEC: /ready n'est pas vert; le decor n'est pas utilisable." >&2
  echo "             $(cut -c1-300 <<<"$PRET")" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. L'INTERFACE, EN BUILD DE PRODUCTION
# ---------------------------------------------------------------------------
# PAS `next dev`. Le mode developpement recompile a la volee et sert parfois un
# module perime; on a deja perdu une heure sur un `.next` obsolete qui envoyait
# l'ancienne charge utile. Un build fige est ce qu'on veut eprouver.
if [[ ! -d "$RACINE/web/node_modules" ]]; then
  echo "NON EXECUTE: parcours_entree.sh — web/node_modules absent." >&2
  echo "       Installer: cd eurostruct/web && npm ci" >&2
  exit 4
fi
# LES VARIABLES DE RUNTIME, PAS LES `NEXT_PUBLIC_*`.
#
# C'est le chemin de production: le layout — un composant serveur — les lit a
# chaque requete et les depose dans la page. Les `NEXT_PUBLIC_*` seraient
# inlinees dans le bundle au build, et le parcours n'eprouverait alors pas le
# chemin que l'image utilisera.
WEB_ENV=(
  "EUROSTRUCT_API_URL=http://127.0.0.1:$PORT_API"
  "EUROSTRUCT_SUPABASE_URL=http://127.0.0.1:$PORT_AUTH"
  # FICTIVE, ET ELLE N'A PAS A ETRE AUTRE CHOSE. La cle anonyme de GoTrue
  # n'est pas un secret: elle designe le projet, elle n'autorise rien.
  "EUROSTRUCT_SUPABASE_ANON_KEY=FICTIF-ANON-$JETON"
)
# ON PART D'UN `.next` VIDE. Un build incremental par-dessus les artefacts
# d'une execution precedente laisse un manifeste qui reference des chunks
# disparus: la page se charge a moitie, aucun bouton n'apparait, et l'echec
# ressemble a un defaut de l'interface.
rm -rf "$RACINE/web/.next"
if ! (cd "$RACINE/web" && env "${WEB_ENV[@]}" npm run build >"$TMP/build.log" 2>&1); then
  echo "      ECHEC: le build de production de l'interface a echoue." >&2
  tail -n 30 "$TMP/build.log" >&2
  exit 1
fi
# `exec` REMPLACE LE SOUS-SHELL par node: `$!` designe alors le serveur
# lui-meme, et non un pere qu'on tuerait en laissant l'enfant en ecoute.
(cd "$RACINE/web" && exec env "${WEB_ENV[@]}" \
   node node_modules/next/dist/bin/next start -p "$PORT_WEB" \
   >"$TMP/web.log" 2>&1) &
PID_WEB=$!
if ! attendre_url "http://127.0.0.1:$PORT_WEB" 60 "$PID_WEB"; then
  echo "      ECHEC: l'interface n'a pas demarre sur le port $PORT_WEB." >&2
  sed -n '1,30p' "$TMP/web.log" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. LE PARCOURS
# ---------------------------------------------------------------------------
EUROSTRUCT_WEB="http://127.0.0.1:$PORT_WEB" \
EUROSTRUCT_API="http://127.0.0.1:$PORT_API" \
  node "$RACINE/web/e2e/parcours_entree.mjs"
CODE=$?

if [[ $CODE -eq 0 ]]; then
  # LE CONSTAT FINAL EST FAIT ICI, HORS DU NAVIGATEUR: le bureau existe-t-il
  # REELLEMENT en base, et l'invitation a-t-elle ete consommee UNE fois?
  NB_ORG=$(q "select count(*) from organizations")
  NB_OWN=$(q "select count(*) from organization_members
               where role = 'owner' and is_active")
  NB_INV=$(q "select count(*) from organization_invitations
               where accepted_at is not null")
  NB_REV=$(q "select count(*) from organization_members where not is_active")
  if [[ "$NB_ORG" != "1" || "$NB_OWN" != "1" || "$NB_INV" != "1"
        || "$NB_REV" != "1" ]]; then
    echo "      ECHEC: la base ne porte pas ce que l'ecran a annonce." >&2
    echo "             organisations=$NB_ORG (attendu 1)" >&2
    echo "             proprietaires actifs=$NB_OWN (attendu 1)" >&2
    echo "             invitations consommees=$NB_INV (attendu 1)" >&2
    echo "             adhesions revoquees=$NB_REV (attendu 1)" >&2
    CODE=1
  else
    echo "      1 bureau, 1 proprietaire actif, 1 invitation consommee, 1 acces revoque."
  fi
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "==================================================="
  echo " Depuis le navigateur: un compte tout neuf arrive"
  echo " devant deux portes et non un ecran vide, fonde son"
  echo " bureau, en devient proprietaire, cree le projet qui"
  echo " refusait avant, invite par un lien dont le secret"
  echo " n'apparait qu'une fois et ne survit a rien, voit"
  echo " son invitee entrer avec le role prevu, la promeut,"
  echo " la desactive sans effacer sa ligne — et ne peut ni"
  echo " se modifier lui-meme, ni disparaitre en tant que"
  echo " dernier proprietaire actif."
  echo "==================================================="
fi
exit $CODE
