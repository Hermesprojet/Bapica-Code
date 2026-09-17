#!/usr/bin/env bash
#
# EUROSTRUCT — L'ENVIRONNEMENT LOCAL DE DEMONSTRATION, ET IL EST DURABLE
#
#   deploy/demo.sh prerequis ce qu'il faut sur le poste, et ce qui manque
#   deploy/demo.sh up        demarre (construit au premier appel), amorce, sert
#   deploy/demo.sh down      arrete les conteneurs et GARDE les donnees
#   deploy/demo.sh status    ce qui tourne, et ce que /ready en dit
#   deploy/demo.sh comptes   les deux comptes d'essai, mot de passe compris
#   deploy/demo.sh journaux [service] [n]   les n dernieres lignes d'un service (api, web, db, init, demo-auth)
#
#   deploy/demo.sh sauvegarder        base + livrables, dans deploy/sauvegardes/
#   deploy/demo.sh diagnostic         ce qu'une mise a jour ferait — ne modifie rien
#   deploy/demo.sh mettre-a-jour      la nouvelle version, en GARDANT les etudes
#   deploy/demo.sh reprendre          reprend une mise a jour interrompue
#   deploy/demo.sh restaurer <dossier>  remet une sauvegarde en place
#   deploy/demo.sh reset     detruit les donnees — consentement explicite exige
#
# METTRE A JOUR N'EST PAS RECOMMENCER
# -------------------------------------
# `reset` DETRUIT: la base, les livrables, la cle de l'emetteur. C'est un geste
# volontaire, et il reste disponible pour repartir de zero. Il n'est PAS la
# facon de passer a une nouvelle version: une demonstration qu'on garde porte
# des etudes, des variantes, des PDF et des DXF qu'on veut retrouver.
#
# `mettre-a-jour` construit la nouvelle version pendant que l'ancienne sert
# encore, prend une sauvegarde, arrete les ecritures, ouvre la fenetre de mise
# a niveau de la base — la MEME que `tools/deploy_eurostruct.sh --mettre-a-niveau`,
# appelee par le service `init` — puis redemarre l'application. Les etudes et
# les livrables sont conserves; c'est `db/test/mise_a_niveau_active.sh` qui le
# mesure, ligne pour ligne et octet pour octet.
#
# CE QUE CETTE COMMANDE ETABLIT, ET QU'AUCUNE AUTRE N'ETABLISSAIT
# -----------------------------------------------------------------
# `dev.sh` demarre l'API et l'interface sans base ni compte: le calcul
# exploratoire y tourne, mais l'atelier — projets, etudes enregistrees, PDF et
# DXF conserves — exige une base et une identite, et l'ecran le disait sans
# offrir le moyen de les avoir. Les harnais (`composition_depuis_zero.sh`,
# `recette_production.sh`) montent bien la pile entiere, puis la DETRUISENT a
# la sortie: rien de ce qu'on y fait ne survit.
#
# Celle-ci monte la composition de reference — `compose.yaml`, sans
# modification — avec une surcouche qui lui donne ce qu'un poste n'a pas: un
# emetteur de jetons de demonstration. Et elle laisse tout en place. On cree
# une etude, on ferme le navigateur, on arrete les services, on les redemarre,
# et l'etude est la: c'est `deploy/demo_persistance.sh` qui le mesure.
#
# CE QUI EST DE DEMONSTRATION, ET CE QUI NE L'EST PAS
# -----------------------------------------------------
# Les COMPTES. Deux ingenieurs d'essai, A et B, dont le mot de passe et
# l'identifiant sont tires au hasard sur ce poste, une fois, et ne designent
# personne. Une decision d'autorite prise sous ces comptes eprouve le circuit
# a deux personnes; elle ne represente AUCUNE approbation humaine reelle d'un
# parametre national. L'API et l'interface le disent (bandeau
# « environnement de demonstration »).
#
# Tout le reste est le produit: memes images, memes migrations, memes
# politiques RLS, meme verification des jetons, memes refus.
#
# AUCUN SECRET DANS LE DEPOT, AUCUN DANS `argv`, AUCUN DANS CETTE SORTIE
# ------------------------------------------------------------------------
# `deploy/demo.env` est genere ici au premier appel, en 0600, et Git l'ignore.
# Les mots de passe passent par des fichiers ou par l'environnement, jamais
# par la ligne de commande — qui est lisible par tout processus du poste.
# Seul `demo.sh comptes` les affiche, sur demande.
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
ENVF="$ICI/demo.env"
PROJET="eurostruct-demo"
NOM_ORG="Bureau de démonstration"
NOM_PROJET="Démonstration — poutre belge"

refus() { echo "REFUS: $*" >&2; exit 2; }
dire()  { echo "--> $*"; }

dc() {
  docker compose -p "$PROJET" \
    -f "$RACINE/compose.yaml" -f "$RACINE/compose.demo.yaml" \
    --env-file "$ENVF" "$@"
}

# ---------------------------------------------------------------------------
# CE QU'IL FAUT SUR LE POSTE, VERIFIE AVANT DE TOUCHER A QUOI QUE CE SOIT
# ---------------------------------------------------------------------------
# CHAQUE PREREQUIS DIT CE QUI MANQUE ET CE QU'IL FAUT FAIRE. `demo.sh prerequis`
# les passe tous et rend un tableau; `up` refuse au premier manquant, avec la
# meme phrase. Un demarrage qui echoue trois etapes plus loin sur une version
# de Compose trop ancienne (« !override » exige 2.24) ou un port deja pris
# ferait chercher la panne dans la composition, ou elle n'est pas.
COMPOSE_MIN="2.24"

version_compose() {   # « 2.29.7 » — sans le « v », sans le reste
  docker compose version --short 2>/dev/null | sed -E 's/^v//; s/[^0-9.].*$//'
}
compose_suffisant() {   # compose_suffisant <version> — >= COMPOSE_MIN ?
  local v="$1" maj min
  [[ "$v" =~ ^[0-9]+\.[0-9]+ ]] || return 1
  maj="${v%%.*}"; min="${v#*.}"; min="${min%%.*}"
  (( maj > ${COMPOSE_MIN%%.*} )) \
    || (( maj == ${COMPOSE_MIN%%.*} && min >= ${COMPOSE_MIN#*.} ))
}
port_libre() {   # port_libre <port> — rien n'ecoute sur 127.0.0.1:<port>
  python3 - "$1" <<'PY'
import socket, sys
s = socket.socket(); s.settimeout(0.5)
sys.exit(1 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 0)
PY
}

# verifier_prerequis <exiger|tableau> — rend 0 si tout est la
verifier_prerequis() {
  local mode="$1" ko=0
  ligne() {   # ligne <ok|non> <quoi> <remede>
    if [[ "$1" == "ok" ]]; then
      [[ "$mode" == "tableau" ]] && printf '  ok      %s\n' "$2"
    else
      ko=1
      if [[ "$mode" == "tableau" ]]; then printf '  MANQUE  %s — %s\n' "$2" "$3"
      else refus "$2: $3"; fi
    fi
  }
  local v
  if command -v docker >/dev/null 2>&1; then ligne ok "docker"
  else ligne non "docker" "absent. Installer Docker (Desktop, ou le moteur seul) puis relancer."; fi
  local demon=1
  if docker info >/dev/null 2>&1; then ligne ok "demon docker"
  else demon=0; ligne non "demon docker" "ne repond pas. Demarrer Docker, puis relancer."; fi
  v="$(version_compose)"
  if [[ -n "$v" ]] && compose_suffisant "$v"; then ligne ok "docker compose $v (>= $COMPOSE_MIN)"
  else ligne non "docker compose ${v:-absent}" "la surcouche de demonstration emploie « !override », qui exige Compose $COMPOSE_MIN ou plus. Mettre Docker Compose a jour."; fi
  for outil in git curl python3; do
    if command -v "$outil" >/dev/null 2>&1; then ligne ok "$outil"
    else ligne non "$outil" "absent. L'installer, puis relancer."; fi
  done
  # LES PORTS: seulement si la composition n'est pas deja debout — ses propres
  # conteneurs les tiennent legitimement, et « up » sur une pile qui tourne
  # doit rester possible.
  local api="${API_PORT:-${EUROSTRUCT_DEMO_PORT_API:-8000}}" \
        web="${WEB_PORT:-${EUROSTRUCT_DEMO_PORT_WEB:-3000}}" \
        auth="${DEMO_AUTH_PORT:-${EUROSTRUCT_DEMO_PORT_AUTH:-54321}}"
  local debout=""
  [[ -f "$ENVF" ]] && debout="$(dc ps -q --status running 2>/dev/null | head -1)"
  if (( ! demon )); then
    # SANS DEMON, ON NE SAIT PAS QUI TIENT LES PORTS — peut-etre nos propres
    # conteneurs, encore vivants. Les declarer « pris » enverrait liberer un
    # port qu'on tient soi-meme. Mesure du 16/09 en simulant un demon arrete.
    [[ "$mode" == "tableau" ]] \
      && printf '  --      ports %s, %s, %s — non verifies tant que le demon docker ne repond pas\n' "$api" "$web" "$auth"
  elif [[ -n "$debout" ]]; then
    ligne ok "ports $api, $web, $auth (tenus par la composition, deja debout)"
  else
    for duo in "$api:API:EUROSTRUCT_DEMO_PORT_API" "$web:interface:EUROSTRUCT_DEMO_PORT_WEB" \
               "$auth:emetteur de demonstration:EUROSTRUCT_DEMO_PORT_AUTH"; do
      IFS=: read -r port quoi var <<<"$duo"
      if port_libre "$port"; then ligne ok "port $port libre ($quoi)"
      else ligne non "port $port ($quoi)" "deja pris sur ce poste. Liberer le port, ou choisir un autre avec $var=<port> AVANT le premier « up » (il est fige dans deploy/demo.env)."; fi
    done
  fi
  return $ko
}
exiger_outils() { verifier_prerequis exiger; }

# ---------------------------------------------------------------------------
# LE FICHIER D'ENVIRONNEMENT — GENERE UNE FOIS, JAMAIS RECOPIE D'UN GABARIT
# ---------------------------------------------------------------------------
# LES IDENTIFIANTS DES COMPTES SONT STABLES, ET C'EST CE QUI REND L'ENVIRONNEMENT
# DURABLE. Le `sub` d'un jeton est la cle de tout ce qu'une personne possede en
# base — bureau, projets, etudes. Un identifiant retire au hasard a chaque
# demarrage ferait perdre son travail a chacun.
aleatoire() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
uuid() {
  if command -v uuidgen >/dev/null 2>&1; then uuidgen | tr 'A-Z' 'a-z'
  elif [[ -r /proc/sys/kernel/random/uuid ]]; then cat /proc/sys/kernel/random/uuid
  else python3 -c 'import uuid; print(uuid.uuid4())'
  fi
}

generer_env() {
  local a_mdp b_mdp a_id b_id racine_id
  a_mdp="$(aleatoire 20)"; b_mdp="$(aleatoire 20)"
  a_id="$(uuid)"; b_id="$(uuid)"; racine_id="$(uuid)"
  umask 077
  cat > "$ENVF" <<FIN
# EUROSTRUCT — environnement de DEMONSTRATION, genere par deploy/demo.sh.
# Genere le $(date -u +%Y-%m-%dT%H:%M:%SZ) sur ce poste. Ignore par Git.
# Les valeurs ci-dessous ne designent personne et ne valent que sur ce poste.

# --- les deux comptes d'essai (emetteur de demonstration) --------------------
EUROSTRUCT_DEMO_COMPTE_A=ingenieur-a@demonstration.invalid
EUROSTRUCT_DEMO_MDP_A=$a_mdp
EUROSTRUCT_DEMO_ID_A=$a_id
EUROSTRUCT_DEMO_COMPTE_B=ingenieur-b@demonstration.invalid
EUROSTRUCT_DEMO_MDP_B=$b_mdp
EUROSTRUCT_DEMO_ID_B=$b_id
EUROSTRUCT_DEMO_COMPTES=ingenieur-a@demonstration.invalid:$a_mdp:$a_id:7200:oui,ingenieur-b@demonstration.invalid:$b_mdp:$b_id:7200:oui

# --- la racine d'autorite de demonstration ----------------------------------
# Le mandat nomme le principal amorce; sans lui aucune habilitation n'existe.
EUROSTRUCT_BOOTSTRAP_ACTOR=$racine_id
EUROSTRUCT_BOOTSTRAP_MANDATE=$racine_id:DEMONSTRATION-$(aleatoire 24)
EUROSTRUCT_BOOTSTRAP_NAME="Racine de demonstration"
EUROSTRUCT_BOOTSTRAP_REASON="amorcage de l environnement de demonstration"

# --- base de donnees (conteneur, port non publie) ---------------------------
POSTGRES_USER=eurostruct_super
POSTGRES_PASSWORD=$(aleatoire 28)
POSTGRES_DB=eurostruct
EUROSTRUCT_PLAN_DB_USER=eurostruct_plan
EUROSTRUCT_PLAN_DB_PASSWORD=$(aleatoire 28)
EUROSTRUCT_MIGRATOR_DB_USER=eurostruct_migrator
EUROSTRUCT_MIGRATOR_DB_PASSWORD=$(aleatoire 28)
EUROSTRUCT_APP_DB_USER=eurostruct_app
EUROSTRUCT_APP_DB_PASSWORD=$(aleatoire 28)
# Sans Supabase, le schema auth est FICTIF: la composition le pose.
EUROSTRUCT_LOCAL_AUTH_STUB=oui

# --- ports sur la boucle locale ---------------------------------------------
API_PORT=${EUROSTRUCT_DEMO_PORT_API:-8000}
WEB_PORT=${EUROSTRUCT_DEMO_PORT_WEB:-3000}
DEMO_AUTH_PORT=${EUROSTRUCT_DEMO_PORT_AUTH:-54321}
EUROSTRUCT_PUBLIC_API_URL=http://127.0.0.1:${EUROSTRUCT_DEMO_PORT_API:-8000}
EUROSTRUCT_CORS_ORIGINS=http://localhost:${EUROSTRUCT_DEMO_PORT_WEB:-3000},http://127.0.0.1:${EUROSTRUCT_DEMO_PORT_WEB:-3000}
# Renseignes par la surcouche compose.demo.yaml; presents ici pour que
# \`docker compose config\` ne signale aucune variable manquante.
EUROSTRUCT_SUPABASE_JWKS_URL=
EUROSTRUCT_SUPABASE_ISSUER=
EUROSTRUCT_PUBLIC_SUPABASE_URL=
EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY=

# --- livrables ---------------------------------------------------------------
# \`local\`: sur le volume nomme \`livrables\` de la composition, qui survit aux
# redemarrages. Aucun secret S3 n'est alors necessaire. Les deux valeurs
# ci-dessous ne servent QUE si vous passez a \`s3\` avec
# \`docker compose --profile objets\` (MinIO en conteneur); elles sont tirees
# au hasard pour que le magasin et l'API partagent les memes identifiants.
EUROSTRUCT_STORAGE_BACKEND=local
EUROSTRUCT_S3_ACCESS_KEY_ID=demo$(aleatoire 12)
EUROSTRUCT_S3_SECRET_ACCESS_KEY=$(aleatoire 40)
FIN
}

charger_env() {
  [[ -f "$ENVF" ]] || refus "deploy/demo.env absent: lancez « deploy/demo.sh up »."
  set -a; . "$ENVF"; set +a
}

# ---------------------------------------------------------------------------
# L'IDENTITE DE BUILD — celle de l'arbre present, dite telle qu'elle est
# ---------------------------------------------------------------------------
identite_de_build() {
  local sha
  sha="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || true)"
  [[ -n "$sha" ]] || refus "aucun depot git lisible: sans identite de build, \
aucune etude ne peut etre enregistree."
  if ! git -C "$RACINE" diff --quiet 2>/dev/null; then
    # UN ARBRE MODIFIE N'EST PAS SON DERNIER COMMIT, et l'etude conservee
    # portera le suffixe plutot qu'une identite qui ressemble a une reponse.
    sha="${sha}-modifie"
  fi
  echo "$sha"
}

# ---------------------------------------------------------------------------
# LES APPELS A L'API, SANS SECRET DANS `argv`
# ---------------------------------------------------------------------------
# Le corps JSON de la connexion et l'en-tete Authorization passent par des
# fichiers temporaires en 0600 (`-d @-` et `-H @fichier`): rien de tout cela
# n'apparait dans `ps`.
TMP=""
preparer_tmp() { TMP="$(mktemp -d)"; chmod 700 "$TMP"; }
nettoyer_tmp() { [[ -n "$TMP" ]] && rm -rf "$TMP"; }

jeton_pour() {   # jeton_pour <courriel> <variable-du-mot-de-passe>
  local courriel="$1" mdp="${!2}"
  python3 -c 'import json,sys; print(json.dumps({"email": sys.argv[1], "password": sys.stdin.read().rstrip("\n")}))' \
    "$courriel" <<<"$mdp" > "$TMP/connexion.json"
  curl -fsS -X POST \
    "http://127.0.0.1:${DEMO_AUTH_PORT}/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' -d @"$TMP/connexion.json" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}

api() {          # api <methode> <chemin> [fichier-corps]
  local methode="$1" chemin="$2" corps="${3:-}"
  local -a opts=(-sS -o "$TMP/reponse.json" -w '%{http_code}' -X "$methode"
                 -H @"$TMP/entete" -H 'Content-Type: application/json')
  [[ -n "$corps" ]] && opts+=(-d @"$corps")
  curl "${opts[@]}" "http://127.0.0.1:${API_PORT}${chemin}" 2>/dev/null
}

# ---------------------------------------------------------------------------
# L'AMORCAGE DE L'ESPACE DE TRAVAIL — IDEMPOTENT
# ---------------------------------------------------------------------------
# Il passe par les ROUTES DU PRODUIT, sous le jeton de A: le bureau et le
# projet naissent comme ils naitraient sous les doigts d'un ingenieur, avec
# les memes politiques. Fonder deux fois le meme bureau rend le meme bureau;
# le projet est cherche avant d'etre cree.
#
# Les deux habilitations normatives, elles, ne passent par aucune route: le
# produit n'expose pas la delegation, deliberement. Elles sont posees comme
# `composition_depuis_zero.sh` les pose — par le login applicatif, sous
# l'acteur racine, dans la base de la composition. C'est un geste de
# provisionnement de l'environnement de demonstration, et il n'a lieu qu'ici.
amorcer() {
  dire "amorcage de l'espace de travail"

  # 1. Les deux comptes existent dans `auth.users`. En production, c'est
  #    l'emetteur (GoTrue) qui peuple cette table; ici c'est le
  #    superutilisateur de la composition, et le login applicatif n'y a aucun
  #    droit — il ne doit pas pouvoir se fabriquer un utilisateur.
  dc exec -T db psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -v a="$EUROSTRUCT_DEMO_ID_A" -v b="$EUROSTRUCT_DEMO_ID_B" >/dev/null <<'SQL' \
     || refus "les comptes d'essai n'ont pas pu etre inscrits dans auth.users."
insert into auth.users (id) values (:'a'::uuid), (:'b'::uuid)
on conflict do nothing;
SQL

  # 2. Les deux habilitations, deleguees depuis la racine amorcee.
  local edition racine_grant
  edition="$(dc exec -T api python -c '
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
eds = {jeu.find(k).edition for k in jeu.keys()}
print(sorted(eds)[0] if len(eds) == 1 else "")' 2>/dev/null | tr -d '\r')"
  [[ -n "$edition" ]] || refus "edition du registre belge illisible."
  racine_grant="$(dc exec -T db psql -X -q -tA -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -c "select id from normative_authorisation_grants where origin='bootstrap' limit 1" \
     2>/dev/null | tr -d ' \r')"
  [[ "$racine_grant" =~ ^[0-9a-f-]{36}$ ]] \
    || refus "aucune racine d'autorite amorcee: l'initialisation n'a pas pose le mandat."

  local duo
  for duo in "$EUROSTRUCT_DEMO_ID_A:A" "$EUROSTRUCT_DEMO_ID_B:B"; do
    PGPASSWORD="$EUROSTRUCT_APP_DB_PASSWORD" \
    dc exec -T -e PGPASSWORD db psql -X -q -U "$EUROSTRUCT_APP_DB_USER" -d "$POSTGRES_DB" \
       -v racine="$EUROSTRUCT_BOOTSTRAP_ACTOR" -v qui="${duo%%:*}" \
       -v nom="Ingenieur d'essai ${duo##*:} (demonstration)" \
       -v edition="$edition" -v parent="$racine_grant" >"$TMP/grant.log" 2>&1 <<'SQL'
select set_config('eurostruct.actor_id', :'racine', false);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   edition, reason, parent_grant_id)
select :'qui'::uuid, :'nom', 'can_validate_normative_reference', 'BE',
       'EN 1992', '1-1', :'edition',
       'habilitation d essai de l environnement de demonstration', :'parent'::uuid
where not exists (
  select 1 from normative_authorisation_grants
   where grantee_id = :'qui'::uuid and permission = 'can_validate_normative_reference'
     and country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1'
     and edition = :'edition');
SQL
    if grep -qiE "ERROR|FATAL" "$TMP/grant.log"; then
      echo "      l'habilitation de ${duo##*:} n'a pas ete posee:" >&2
      grep -m1 -iE "ERROR|FATAL" "$TMP/grant.log" | cut -c1-200 | sed 's/^/      /' >&2
      exit 1
    fi
  done

  # 3. Le bureau et le projet, par les routes du produit, sous le jeton de A.
  local jeton code org_id projet_id
  jeton="$(jeton_pour "$EUROSTRUCT_DEMO_COMPTE_A" EUROSTRUCT_DEMO_MDP_A)"
  [[ -n "$jeton" ]] || refus "l'emetteur de demonstration n'a pas delivre de jeton pour A."
  printf 'Authorization: Bearer %s\n' "$jeton" > "$TMP/entete"

  python3 -c 'import json,sys; print(json.dumps({"name": sys.argv[1], "country": "BE", "display_name": "Ingénieur d'"'"'essai A", "professional_id": None}))' \
    "$NOM_ORG" > "$TMP/org.json"
  code="$(api POST /v1/organizations "$TMP/org.json")"
  [[ "$code" == "201" ]] || refus "la fondation du bureau a rendu $code: $(cut -c1-200 "$TMP/reponse.json")"
  org_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["organization_id"])' < "$TMP/reponse.json")"

  code="$(api GET /v1/projects)"
  [[ "$code" == "200" ]] || refus "la liste des projets a rendu $code."
  projet_id="$(python3 -c '
import json,sys
nom = sys.argv[1]
for p in json.load(sys.stdin)["projects"]:
    if p["name"] == nom: print(p["project_id"]); break' "$NOM_PROJET" < "$TMP/reponse.json")"
  if [[ -z "$projet_id" ]]; then
    python3 -c 'import json,sys; print(json.dumps({"name": sys.argv[1], "reference": "DEMO-BE-001", "country": "BE", "region": None, "ndp_as_of": sys.argv[2], "organization_id": sys.argv[3]}))' \
      "$NOM_PROJET" "$(date -u +%Y-%m-%d)" "$org_id" > "$TMP/projet.json"
    code="$(api POST /v1/projects "$TMP/projet.json")"
    [[ "$code" == "201" ]] || refus "la creation du projet a rendu $code: $(cut -c1-200 "$TMP/reponse.json")"
    projet_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["project_id"])' < "$TMP/reponse.json")"
    dire "projet « $NOM_PROJET » cree ($projet_id)"
  else
    dire "projet « $NOM_PROJET » deja present ($projet_id)"
  fi
  mkdir -p "$ICI/demo"
  printf '%s\n' "$projet_id" > "$ICI/demo/projet_id"
}

attendre() {     # attendre <url> <secondes> — rend 0 des que l'URL repond 2xx
  local url="$1" n="$2"
  for _ in $(seq 1 "$n"); do
    curl -fsS --max-time 2 -o /dev/null "$url" 2>/dev/null && return 0
    sleep 1
  done
  return 1
}

# ===========================================================================
# LES COMMANDES
# ===========================================================================
cmd_up() {
  # LES PORTS FIGES DANS deploy/demo.env SONT CEUX QU'ON VERIFIE: l'environnement
  # est charge AVANT les prerequis quand il existe, sinon les prerequis
  # liraient les valeurs par defaut d'un poste qui en a choisi d'autres.
  [[ -f "$ENVF" ]] && charger_env
  exiger_outils
  if [[ ! -f "$ENVF" ]]; then
    dire "premier demarrage: generation de deploy/demo.env (0600, ignore par Git)"
    generer_env
    charger_env
  fi
  EUROSTRUCT_BUILD_SHA="$(identite_de_build)"
  export EUROSTRUCT_BUILD_SHA
  dire "build: $EUROSTRUCT_BUILD_SHA"

  # LA CONSTRUCTION ET LE DEMARRAGE SONT DEUX PAS, ET CHACUN DIT COMMENT
  # REPRENDRE. Une construction coupee (reseau, proxy, Ctrl-C, disque plein)
  # n'est pas une composition qui ne monte pas: la premiere reprend au
  # dernier etage reussi, la seconde se lit dans le journal de
  # l'initialisation. Un seul « up --build » melangeait les deux dans un
  # meme echec, sans dire lequel.
  dire "composition: construction des images (le premier appel prend quelques minutes)"
  if ! dc build; then
    echo "" >&2
    echo "ECHEC: la construction des images s'est interrompue (reseau coupe, proxy," >&2
    echo "       Ctrl-C, disque plein: la cause est dans le journal ci-dessus)." >&2
    echo "       Reprendre: relancez « deploy/demo.sh up » — la construction repart" >&2
    echo "       du dernier etage reussi (cache Docker), rien n'est refait deux fois." >&2
    echo "       Si cela persiste: « docker system df » (espace), « docker info » (demon)." >&2
    exit 1
  fi

  dire "composition: demarrage et initialisation de la base (idempotente)"
  if ! dc up -d --wait --wait-timeout 900; then
    echo "" >&2
    # UNE MIGRATION DE PLUS DANS LE DEPOT, ET UNE BASE DEJA EN SERVICE. `up`
    # INSTALLE ET VERIFIE — elle n'ouvre aucune fenetre de migration sur une
    # base qui sert (ACTIVE_SCHEMA_UPGRADE_REQUIRED, code 9). Ce n'est pas une
    # panne: c'est le refus d'appliquer une migration par surprise a des
    # donnees qu'on n'a pas sauvegardees.
    #
    # LA REPRISE N'EST PLUS UN `reset`. Elle l'a ete, et c'etait le defaut:
    # « pour avoir la nouvelle version, jetez vos etudes ». La mise a jour
    # conserve la base et les livrables.
    local journal_init
    journal_init="$(dc logs --no-color --tail 60 init 2>&1)"
    if grep -q "ACTIVE_SCHEMA_UPGRADE_REQUIRED" <<<"$journal_init"; then
      echo "ECHEC: cette version du depot porte une migration que la base de demonstration" >&2
      echo "       existante n'a pas:" >&2
      grep -E '^\s+[0-9]{4}_[a-z0-9_]+\.sql' <<<"$journal_init" | sed 's/^ */         /' >&2
      echo "       RIEN N'A ETE APPLIQUE, et vos etudes sont intactes. Pour passer a" >&2
      echo "       cette version EN LES CONSERVANT:" >&2
      echo "         deploy/demo.sh diagnostic       ce qui serait fait, sans rien modifier" >&2
      echo "         deploy/demo.sh mettre-a-jour    sauvegarde, migration, redemarrage" >&2
      echo "       Pour repartir de zero a la place — vos etudes sont alors PERDUES:" >&2
      echo "         EUROSTRUCT_DEMO_RESET=oui-detruire-les-donnees-de-demonstration deploy/demo.sh reset" >&2
      echo "         deploy/demo.sh up" >&2
      exit 1
    fi
    echo "ECHEC: la composition n'est pas montee. Etat des conteneurs, puis derniers" >&2
    echo "       journaux de l'initialisation et de l'API:" >&2
    dc ps 2>&1 | sed 's/^/      /' >&2
    dc logs --no-color --tail 40 init 2>&1 | sed 's/^/      init | /' >&2
    dc logs --no-color --tail 20 api 2>&1 | sed 's/^/      api  | /' >&2
    echo "       Reprendre: corrigez la cause nommee ci-dessus, puis relancez" >&2
    echo "       « deploy/demo.sh up » — l'initialisation constate ce qui est deja fait." >&2
    echo "       Journaux complets: « deploy/demo.sh journaux init », « … journaux api »." >&2
    exit 1
  fi

  attendre "http://127.0.0.1:${API_PORT}/ready" 60 \
    || { echo "ECHEC: /ready ne passe pas au vert. Ce que l'API en dit:" >&2
         curl -sS "http://127.0.0.1:${API_PORT}/ready" 2>/dev/null | cut -c1-600 >&2
         echo "" >&2
         echo "       Reprendre: « deploy/demo.sh status » nomme la verification rouge;" >&2
         echo "       « deploy/demo.sh journaux api » porte la cause. Puis « deploy/demo.sh up »." >&2
         exit 1; }

  preparer_tmp; trap nettoyer_tmp EXIT
  amorcer

  echo ""
  echo "=================================================================="
  echo " EUROSTRUCT — environnement de DEMONSTRATION"
  echo ""
  echo "   interface : http://127.0.0.1:${WEB_PORT}"
  echo "   API       : http://127.0.0.1:${API_PORT}/ready"
  echo "   comptes   : $EUROSTRUCT_DEMO_COMPTE_A  et  $EUROSTRUCT_DEMO_COMPTE_B"
  echo "               (mots de passe: deploy/demo.sh comptes)"
  echo "   projet    : « $NOM_PROJET »"
  echo ""
  echo "   Les comptes sont des comptes d'ESSAI. Une decision prise sous eux"
  echo "   n'est pas une approbation reelle d'un parametre national."
  echo ""
  echo "   arreter en gardant tout : deploy/demo.sh down"
  echo "   tout detruire           : deploy/demo.sh reset"
  echo "=================================================================="
}

cmd_down() {
  exiger_outils; charger_env
  dire "arret des conteneurs — les volumes (base, livrables, cle) sont GARDES"
  dc stop
}

cmd_status() {
  exiger_outils; charger_env
  dc ps
  echo ""
  curl -sS --max-time 5 "http://127.0.0.1:${API_PORT}/ready" 2>/dev/null \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
print("ready:", d.get("ready"), "| environnement:", d.get("environnement"))
for v in d.get("verifications", []):
    print("  %-22s %s" % (v["nom"], "ok" if v["ok"] else "NON"))' \
    2>/dev/null || echo "l'API ne repond pas sur /ready."
}

cmd_comptes() {
  charger_env
  echo "Comptes d'ESSAI de l'environnement de demonstration (ce poste seulement):"
  echo "  A  $EUROSTRUCT_DEMO_COMPTE_A   $EUROSTRUCT_DEMO_MDP_A"
  echo "  B  $EUROSTRUCT_DEMO_COMPTE_B   $EUROSTRUCT_DEMO_MDP_B"
  echo "Ils ne designent personne. Une decision prise sous eux n'est pas une"
  echo "approbation reelle d'un parametre national."
}

cmd_reset() {
  exiger_outils; charger_env
  if [[ "${EUROSTRUCT_DEMO_RESET:-}" != "oui-detruire-les-donnees-de-demonstration" ]]; then
    echo "REFUS: cette commande DETRUIT la base, les livrables et la cle de" >&2
    echo "       l'emetteur de demonstration. Pour l'autoriser:" >&2
    echo "         EUROSTRUCT_DEMO_RESET=oui-detruire-les-donnees-de-demonstration \\" >&2
    echo "           deploy/demo.sh reset" >&2
    exit 2
  fi
  dire "destruction de la composition « $PROJET » et de ses volumes"
  dc down -v --remove-orphans
  rm -f "$ICI/demo/projet_id"
  dire "deploy/demo.env est conserve; supprimez-le pour regenerer des comptes."
}

# ===========================================================================
# GARDER SES ETUDES: SAUVEGARDER, METTRE A JOUR, REPRENDRE, RESTAURER
# ===========================================================================
# UNE SAUVEGARDE EN TROIS MORCEAUX, PARCE QU'UNE DEMONSTRATION VIT DANS TROIS
# ENDROITS:
#
#   globals.sql    les ROLES du cluster et leurs APPARTENANCES — ils sont hors
#                  de la base, et un `pg_dump` ne les porte pas. La restauration
#                  les rejoue pour rendre une appartenance qu'une fenetre
#                  interrompue aurait retiree. Pris avec --no-role-passwords:
#                  aucun mot de passe n'entre dans la sauvegarde, et ceux des
#                  trois logins sont reposes depuis deploy/demo.env au
#                  demarrage suivant. Ce fichier est aussi ce qu'il faudrait
#                  pour repartir d'une grappe vide — au prix nomme dans
#                  `cmd_restaurer`: des roles recrees sont d'AUTRES principaux.
#   base.dump      la base, au format « custom » — c'est l'archive que la mise
#                  a niveau inspecte avant d'ouvrir sa fenetre.
#   livrables.tar  les OCTETS des PDF et des DXF, sur le volume `livrables`.
#                  Une base sans eux promet des documents introuvables.
#
# AUCUN SECRET N'EST PASSE EN LIGNE DE COMMANDE. `pg_dump` et `pg_restore`
# tournent DANS un conteneur qui a deja ces valeurs dans son environnement, et
# les archives arrivent sur la sortie standard — donc dans des fichiers qui
# appartiennent a l'utilisateur, pas a root.
SAUV="$ICI/sauvegardes"
DERNIERE_SAUVEGARDE=""

# `sh -c` DANS LE CONTENEUR `init`: image postgres:16-bookworm, donc pg_dump,
# pg_restore et psql; aucun volume de donnees monte; et POSTGRES_USER,
# POSTGRES_PASSWORD, POSTGRES_DB, EUROSTRUCT_DB_HOST y sont deja declares par
# compose.yaml. Les guillemets SIMPLES sont essentiels: c'est le shell du
# CONTENEUR qui lit les variables, jamais celui du poste.
pg_dans_init() {   # pg_dans_init <script-sh> [options docker compose run]
  local script="$1"; shift
  dc run --rm --no-deps -T "$@" --entrypoint sh init -c "$script"
}

# L'IMAGE `init` DOIT ETRE CELLE DE L'ARBRE PRESENT, ET PAS CELLE D'AVANT.
# `docker compose run` ne reconstruit pas: il reprend l'image du projet, qui a
# ete construite par le `up` de l'ANCIENNE version. Un diagnostic ou une
# reprise lancee sans ce build annoncerait donc l'etat vu par l'ancien code —
# et, sur une version qui ne connait pas encore la mise a niveau, echouerait
# sur un mode inconnu.
construire_init() {
  dire "image d'initialisation: construction depuis l'arbre present"
  dc build init >/dev/null 2>&1 || dc build init || refus "l'image « init » ne se construit pas."
}

cmd_sauvegarder() {
  exiger_outils; charger_env
  local horo dest magique
  horo="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$SAUV/$horo"
  mkdir -p "$dest" || refus "impossible de creer « $dest »."
  chmod 700 "$SAUV" "$dest"

  dire "la base doit repondre pour etre sauvegardee"
  dc up -d --wait --wait-timeout 300 db >/dev/null 2>&1 \
    || { rm -rf "$dest"; refus "le service « db » ne demarre pas: rien n'a ete sauvegarde."; }

  dire "sauvegarde 1/3 — les roles du cluster (sans aucun mot de passe)"
  if ! pg_dans_init 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dumpall \
         -h "$EUROSTRUCT_DB_HOST" -U "$POSTGRES_USER" \
         --globals-only --no-role-passwords' > "$dest/globals.sql" 2>"$dest/.err"; then
    sed -n '1,5p' "$dest/.err" >&2; rm -rf "$dest"
    refus "la sauvegarde des roles a echoue: rien n'a ete conserve."
  fi
  [[ -s "$dest/globals.sql" ]] || { rm -rf "$dest"; refus "la sauvegarde des roles est vide."; }

  dire "sauvegarde 2/3 — la base « $POSTGRES_DB » (pg_dump -Fc)"
  if ! pg_dans_init 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
         -h "$EUROSTRUCT_DB_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
       > "$dest/base.dump" 2>"$dest/.err"; then
    sed -n '1,5p' "$dest/.err" >&2; rm -rf "$dest"
    refus "la sauvegarde de la base a echoue: rien n'a ete conserve."
  fi
  # UNE ARCHIVE « CUSTOM » COMMENCE PAR `PGDMP`. Le poste n'a pas forcement
  # `pg_restore` pour l'inspecter; ces cinq octets, eux, se lisent partout — et
  # ils separent une archive d'un message d'erreur capture par megarde.
  magique="$(head -c 5 "$dest/base.dump" 2>/dev/null)"
  [[ "$magique" == "PGDMP" ]] \
    || { rm -rf "$dest"; refus "l'archive produite n'est pas un « pg_dump -Fc »
       (debut: « ${magique:-vide} »). Rien n'a ete conserve."; }

  dire "sauvegarde 3/3 — les livrables (PDF, DXF) du volume « livrables »"
  if ! dc run --rm --no-deps -T --user root \
        --entrypoint tar api -C /var/lib/eurostruct/livrables -cf - . \
        > "$dest/livrables.tar" 2>"$dest/.err"; then
    sed -n '1,5p' "$dest/.err" >&2; rm -rf "$dest"
    refus "la sauvegarde des livrables a echoue: rien n'a ete conserve."
  fi
  rm -f "$dest/.err"
  chmod 600 "$dest"/*

  DERNIERE_SAUVEGARDE="$dest"
  echo ""
  echo "  sauvegarde: $dest"
  printf '    %-16s %s o\n' "globals.sql" "$(stat -c %s "$dest/globals.sql")"
  printf '    %-16s %s o\n' "base.dump" "$(stat -c %s "$dest/base.dump")"
  printf '    %-16s %s o, %s fichier(s)\n' "livrables.tar" \
    "$(stat -c %s "$dest/livrables.tar")" \
    "$(tar -tf "$dest/livrables.tar" 2>/dev/null | grep -v '/$' | wc -l | tr -d ' ')"
  echo "  restaurer: EUROSTRUCT_DEMO_RESTAURER=oui-remplacer-par-la-sauvegarde \\"
  echo "               deploy/demo.sh restaurer $dest"
  echo ""
}

cmd_diagnostic() {
  exiger_outils; charger_env
  dc up -d --wait --wait-timeout 300 db >/dev/null 2>&1 \
    || refus "le service « db » ne demarre pas."
  construire_init
  dire "diagnostic de mise a jour — rien ne sera modifie"
  dc run --rm --no-deps init diagnostic
  local code=$?
  case $code in
    0) : ;;
    2) echo "" >&2
       echo "Au moins un prerequis manque (voir MANQUE ci-dessus). Rien n'a ete" >&2
       echo "modifie. « deploy/demo.sh mettre-a-jour » les remplit pour vous:" >&2
       echo "elle arrete l'API et prend la sauvegarde avant d'ouvrir la fenetre." >&2 ;;
    *) echo "" >&2
       echo "Le diagnostic a rendu $code. Rien n'a ete modifie." >&2 ;;
  esac
  return $code
}

# LA MISE A JOUR, DANS L'ORDRE QUI MINIMISE LA COUPURE
# ------------------------------------------------------
# LA CONSTRUCTION D'ABORD, PENDANT QUE L'ANCIENNE VERSION SERT ENCORE. Une
# image qui se construit en huit minutes ne doit pas les passer avec
# l'application arretee. La sauvegarde ensuite, puis seulement l'arret des
# ecritures: la fenetre reelle tient entre l'etape 3 et l'etape 5.
cmd_mettre_a_jour() {
  exiger_outils; charger_env
  local code journal
  EUROSTRUCT_BUILD_SHA="$(identite_de_build)"
  export EUROSTRUCT_BUILD_SHA
  dire "build cible: $EUROSTRUCT_BUILD_SHA"

  dire "1/6 construction des images de la nouvelle version (l'application sert encore)"
  if ! dc build; then
    echo "ECHEC: la construction s'est interrompue. RIEN n'a ete touche: la" >&2
    echo "       demonstration tourne toujours dans sa version actuelle." >&2
    echo "       Reprendre: relancez « deploy/demo.sh mettre-a-jour »." >&2
    exit 1
  fi

  dire "2/6 sauvegarde AVANT toute modification"
  cmd_sauvegarder
  [[ -n "$DERNIERE_SAUVEGARDE" ]] || refus "aucune sauvegarde: la mise a jour n'ira pas plus loin."

  dire "3/6 arret de l'API et de l'interface — les ecritures s'arretent ici"
  dc stop api web

  dire "4/6 mise a niveau de la base, par la commande officielle de deploiement"
  dc run --rm --no-deps \
     -e ESC_UPGRADE_CONSENTEMENT="oui-mettre-a-niveau-$POSTGRES_DB" \
     -e ESC_UPGRADE_SAUVEGARDE=/sauvegarde/base.dump \
     -v "$DERNIERE_SAUVEGARDE:/sauvegarde:ro" \
     init mise-a-niveau
  code=$?
  if [[ $code -ne 0 ]]; then
    echo "" >&2
    case $code in
      2)
        # PREREQUIS REFUSES: la fenetre ne s'est pas ouverte, la base est
        # exactement dans l'etat ou elle etait. On redemarre l'application.
        echo "ECHEC: la mise a niveau a REFUSE d'ouvrir sa fenetre (prerequis)." >&2
        echo "       RIEN N'A ETE MODIFIE. L'application est redemarree dans sa" >&2
        echo "       version actuelle." >&2
        dc up -d --wait --wait-timeout 300 api web >/dev/null 2>&1
        echo "       Sauvegarde conservee: $DERNIERE_SAUVEGARDE" >&2 ;;
      4)
        echo "ECHEC: une autre mise a niveau tient deja le verrou de deploiement." >&2
        echo "       RIEN N'A ETE MODIFIE. Attendez qu'elle finisse." >&2 ;;
      *)
        # LA FENETRE A PU S'OUVRIR. On NE REDEMARRE PAS l'application: elle
        # ecrirait dans une base a moitie migree. La reprise est un geste
        # explicite, et elle referme ce qui est reste ouvert.
        echo "ECHEC: la mise a niveau s'est arretee (code $code) apres avoir ouvert" >&2
        echo "       sa fenetre. L'API et l'interface RESTENT ARRETEES: les laisser" >&2
        echo "       repartir les ferait ecrire dans une base a moitie migree." >&2
        echo "       Reprendre:  deploy/demo.sh reprendre" >&2
        echo "       Revenir en arriere:" >&2
        echo "         EUROSTRUCT_DEMO_RESTAURER=oui-remplacer-par-la-sauvegarde \\" >&2
        echo "           deploy/demo.sh restaurer $DERNIERE_SAUVEGARDE" >&2 ;;
    esac
    exit 1
  fi

  dire "5/6 redemarrage de l'application dans la nouvelle version"
  if ! dc up -d --wait --wait-timeout 900; then
    journal="$(dc logs --no-color --tail 40 api 2>&1)"
    echo "ECHEC: la base est a niveau, mais l'application ne repart pas." >&2
    sed 's/^/      api | /' <<<"$journal" >&2
    echo "       Sauvegarde: $DERNIERE_SAUVEGARDE" >&2
    exit 1
  fi
  attendre "http://127.0.0.1:${API_PORT}/ready" 90 \
    || { echo "ECHEC: /ready ne passe pas au vert apres la mise a jour." >&2
         curl -sS "http://127.0.0.1:${API_PORT}/ready" 2>/dev/null | cut -c1-600 >&2
         exit 1; }

  dire "6/6 controle: /ready au vert"
  echo ""
  echo "=================================================================="
  echo " MISE A JOUR FAITE — les etudes et les livrables sont conserves."
  echo ""
  echo "   interface : http://127.0.0.1:${WEB_PORT}"
  echo "   build     : $EUROSTRUCT_BUILD_SHA"
  echo "   sauvegarde: $DERNIERE_SAUVEGARDE"
  echo ""
  echo "   Vos etudes, variantes, PDF et DXF sont a leur place: rouvrez-les"
  echo "   depuis « Mes etudes ». Aucun recalcul n'a lieu."
  echo "=================================================================="
}

cmd_reprendre() {
  exiger_outils; charger_env
  local code
  dire "la base doit repondre pour qu'une fenetre puisse etre refermee"
  dc up -d --wait --wait-timeout 300 db >/dev/null 2>&1 \
    || refus "le service « db » ne demarre pas."
  construire_init
  dire "reprise de la mise a jour interrompue"
  dc run --rm --no-deps init reprendre
  code=$?
  if [[ $code -ne 0 ]]; then
    echo "" >&2
    echo "ECHEC: la reprise a rendu $code. L'API et l'interface restent arretees." >&2
    echo "       Le journal ci-dessus nomme ce qui n'a pas pu etre etabli." >&2
    exit 1
  fi
  dire "la fenetre est refermee; redemarrage de l'application"
  dc up -d --wait --wait-timeout 900 \
    || { echo "ECHEC: l'application ne repart pas. « deploy/demo.sh journaux api »." >&2; exit 1; }
  attendre "http://127.0.0.1:${API_PORT}/ready" 90 \
    || { echo "ECHEC: /ready ne passe pas au vert." >&2; exit 1; }
  dire "reprise terminee: /ready au vert, donnees conservees."
}

# LA RESTAURATION REMPLACE. Elle n'est pas une reparation en douceur: la base
# en place et les livrables en place sont remplaces par ceux de la sauvegarde.
# C'est pourquoi elle exige le meme genre de consentement explicite que `reset`.
#
# ELLE RESTE DANS LE MEME CLUSTER, ET CE N'EST PAS UN DETAIL D'IMPLEMENTATION.
# Premiere version, mesuree le 17/09: elle detruisait les volumes (`down -v`),
# repartait d'une grappe vide et y rejouait `globals.sql`. La base revenait
# entiere — memes etudes, memes livrables, memes proprietaires de tables — et
# la mise a niveau suivante REFUSAIT, a raison:
#
#   topologie: « eurostruct_plan » atteint « eurostruct_normative_activator »
#   (admin=t). CE ROLE PORTE LE NOM DU PLAN DE CONTROLE APPROUVE SANS ETRE LUI:
#   approuve = oid 16386, present sous ce nom = oid 16394.
#
# LE PLAN DE CONTROLE APPROUVE EST FIGE PAR SON OID, pas par son nom — un nom
# se reprend, une identite non. Des roles recrees dans une grappe neuve sont
# d'AUTRES principaux, meme sous les memes noms, et l'exemption d'ADMIN
# residuel ne leur est pas transmise. C'est exactement ce qu'on veut: une base
# restauree dans une grappe etrangere ne peut pas revendiquer en silence
# l'assurance de celle qui l'a produite.
#
# On remplace donc la BASE a l'interieur de la grappe qui l'a vue naitre, et
# les roles gardent leur identite. `globals.sql` reste dans la sauvegarde: il
# est rejoue ici pour rendre les APPARTENANCES, et il est ce qu'il faudrait
# pour repartir d'une grappe vide — en sachant ce que cela coute.
cmd_restaurer() {
  exiger_outils; charger_env
  local dossier="${1:-}" magique erreurs
  [[ -n "$dossier" ]] || refus "usage: deploy/demo.sh restaurer <dossier-de-sauvegarde>
       Les sauvegardes prises ici sont sous $SAUV/"
  dossier="${dossier%/}"
  [[ -d "$dossier" ]] || refus "« $dossier » n'est pas un dossier de sauvegarde."
  # UN CHEMIN RELATIF PASSE A `-v` N'EST PAS UN CHEMIN POUR DOCKER: c'est un
  # NOM DE VOLUME, et « deploy/sauvegardes/… » est refuse comme nom. Mesure le
  # 17/09: la restauration avait deja detruit les volumes quand l'erreur est
  # tombee. On resout ici, avant tout geste destructeur.
  dossier="$(cd "$dossier" && pwd)" || refus "« $dossier » n'est pas lisible."
  for f in globals.sql base.dump livrables.tar; do
    [[ -s "$dossier/$f" ]] \
      || refus "« $dossier/$f » est absent ou vide: cette sauvegarde est incomplete."
  done
  magique="$(head -c 5 "$dossier/base.dump")"
  [[ "$magique" == "PGDMP" ]] \
    || refus "« $dossier/base.dump » n'est pas une archive pg_dump -Fc."

  if [[ "${EUROSTRUCT_DEMO_RESTAURER:-}" != "oui-remplacer-par-la-sauvegarde" ]]; then
    echo "REFUS: restaurer REMPLACE la base et les livrables en place par ceux" >&2
    echo "       de « $dossier ». Ce qui a ete fait depuis cette sauvegarde est" >&2
    echo "       perdu. Pour l'autoriser:" >&2
    echo "         EUROSTRUCT_DEMO_RESTAURER=oui-remplacer-par-la-sauvegarde \\" >&2
    echo "           deploy/demo.sh restaurer $dossier" >&2
    exit 2
  fi

  dire "1/5 arret des ecrivains — la base, elle, reste debout"
  dc stop api web >/dev/null 2>&1
  dc up -d --wait --wait-timeout 300 db >/dev/null \
    || refus "le service « db » ne demarre pas: rien n'a ete remplace."

  # LES APPARTENANCES D'ABORD. Les roles sont deja la — c'est la meme grappe —
  # mais une appartenance a pu etre retiree depuis (une fenetre de mise a niveau
  # interrompue, par exemple). Les « already exists » sont donc attendus, et
  # c'est meme le cas normal.
  dire "2/5 remise des appartenances de la grappe (les roles y sont deja)"
  erreurs="$(pg_dans_init 'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -q \
               -h "$EUROSTRUCT_DB_HOST" -U "$POSTGRES_USER" -d postgres -f -' \
               < "$dossier/globals.sql" 2>&1 \
             | grep -v "already exists" | grep -E "ERROR|FATAL" | head -5)"
  [[ -z "$erreurs" ]] || { echo "$erreurs" >&2
    refus "la remise des appartenances a echoue. RIEN n'a ete remplace."; }

  # LA BASE EST REMPLACEE, PAS FUSIONNEE. `pg_restore` sur une base qui porte
  # deja le schema echouerait objet par objet et laisserait un melange des deux
  # versions — ce qui serait le pire resultat possible pour une restauration.
  dire "3/5 remplacement de la base « $POSTGRES_DB »"
  if ! pg_dans_init 'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -q -v ON_ERROR_STOP=1 \
         -h "$EUROSTRUCT_DB_HOST" -U "$POSTGRES_USER" -d postgres \
         -c "drop database if exists \"$POSTGRES_DB\"" \
         -c "create database \"$POSTGRES_DB\" owner \"$EUROSTRUCT_MIGRATOR_DB_USER\""'; then
    refus "la base n'a pas pu etre remplacee (une session y est-elle encore
       ouverte ?). Ce qui etait en place n'a PAS ete detruit si le « drop » a
       echoue; sinon, relancez cette meme commande."
  fi

  dire "4/5 restauration de la base et des livrables"
  if ! pg_dans_init 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
         -h "$EUROSTRUCT_DB_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
         --exit-on-error /sauvegarde/base.dump' -v "$dossier:/sauvegarde:ro"; then
    refus "la restauration de la base a echoue (voir ci-dessus). La base est
       vide: corrigez la cause, puis relancez la restauration."
  fi
  # LE MAGASIN AUSSI EST REMPLACE. Laisser les octets en place et deverser la
  # sauvegarde par-dessus donnerait une base qui connait N documents et un
  # magasin qui en porte N+3 — des orphelins que plus rien ne nomme.
  dc run --rm --no-deps -T --user root --entrypoint sh api -c \
     'find /var/lib/eurostruct/livrables -mindepth 1 -delete \
      && tar -C /var/lib/eurostruct/livrables -xf -' \
     < "$dossier/livrables.tar" \
    || refus "les livrables n'ont pas pu etre remis en place."

  # LA RESTAURATION EST FINIE ICI, ET ON LE DIT AVANT DE REDEMARRER. Ce qui
  # suit est un demarrage ordinaire, qui peut tres bien REFUSER: une sauvegarde
  # ANCIENNE remise sous un depot PLUS RECENT porte moins de migrations que
  # l'arbre present, et `up` sortira alors en ACTIVE_SCHEMA_UPGRADE_REQUIRED —
  # a raison. Presenter cela comme un echec de la restauration serait faux.
  echo ""
  echo "  base et livrables restaures depuis: $dossier"
  echo "  Si l'arbre present est PLUS RECENT que cette sauvegarde, le demarrage"
  echo "  qui suit le dira et « deploy/demo.sh mettre-a-jour » est l'etape"
  echo "  suivante — la restauration, elle, est faite."
  echo ""
  dire "5/5 redemarrage: l'initialisation constate ce qui est deja la"
  cmd_up
}

cmd_journaux() {   # journaux [service] [n]
  exiger_outils; charger_env
  local service="${1:-api}" n="${2:-100}"
  case "$service" in api|web|db|init|demo-auth|objets|objets-init) ;;
    *) refus "service inconnu « $service » (api, web, db, init, demo-auth)." ;; esac
  [[ "$n" =~ ^[0-9]+$ ]] || refus "nombre de lignes invalide « $n »."
  dc logs --no-color --tail "$n" "$service"
}

cmd_prerequis() {
  [[ -f "$ENVF" ]] && charger_env
  echo "Prerequis de l'environnement de demonstration sur ce poste:"
  if verifier_prerequis tableau; then
    echo "Tout est la: deploy/demo.sh up peut demarrer."
  else
    echo "Au moins un prerequis manque (voir MANQUE ci-dessus). Rien n'a ete lance." >&2
    exit 2
  fi
}

case "${1:-}" in
  up)             cmd_up ;;
  down)           cmd_down ;;
  status)         cmd_status ;;
  comptes)        cmd_comptes ;;
  reset)          cmd_reset ;;
  prerequis)      cmd_prerequis ;;
  journaux)       cmd_journaux "${2:-}" "${3:-}" ;;
  sauvegarder)    cmd_sauvegarder ;;
  diagnostic)     cmd_diagnostic ;;
  mettre-a-jour)  cmd_mettre_a_jour ;;
  reprendre)      cmd_reprendre ;;
  restaurer)      cmd_restaurer "${2:-}" ;;
  *)
    sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2 ;;
esac
