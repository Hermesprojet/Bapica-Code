#!/usr/bin/env bash
#
# EUROSTRUCT — LA RECETTE, SUR LA PILE DE PRODUCTION, AVEC REDEMARRAGE
#
#   db/test/recette_production.sh
#
# CE QUE CETTE RECETTE ETABLIT, ET QU'AUCUN AUTRE HARNAIS N'ETABLIT
# ------------------------------------------------------------------
# `parcours_livrable.sh` monte la pile A LA MAIN: uvicorn sur l'hote, un
# magasin qui est un repertoire, une base posee par le harnais. Il prouve ce
# que fait l'ECRAN.
#
# `composition_depuis_zero.sh` monte la COMPOSITION depuis un volume vide et
# prouve qu'elle DEMARRE: migrations, roles, /health, /ready, un parcours
# d'autorite.
#
# Celle-ci fait tourner la VERTICALE METIER sur cette composition — images
# construites depuis les seuls fichiers versionnes, PostgreSQL et MinIO en
# conteneurs, `next build` puis `next start` — et ajoute le seul geste
# qu'aucun des deux ne fait:
#
#     ON ARRETE L'API ET L'INTERFACE, ON LES REDEMARRE, ET ON RELIT.
#
# CE QUI DOIT SURVIVRE AU REDEMARRAGE, ET CE QUI NE LE DOIT PAS
# --------------------------------------------------------------
# Survivent: le calcul, son identifiant, ses quatre empreintes, l'instantane
# normatif, les lignes de livrable, les octets dans le magasin, et l'empreinte
# de ces octets.
#
# Ne survit pas: la session. Aucun jeton n'est persiste, et l'ingenieur se
# reconnecte — c'est le contrat, et la seconde phase le vit.
#
# ISOLEE, ET ELLE NE TOUCHE RIEN D'AUTRE
# ----------------------------------------
# Le nom de projet Compose porte un jeton aleatoire, si bien que les volumes
# et le reseau lui appartiennent et ne peuvent pas se confondre avec ceux d'une
# autre execution ni d'un environnement de travail. Le nettoyage ne detruit que
# CE projet-la.
#
# AUCUN SECRET N'EST ECRIT DANS LE DEPOT. Le fichier d'environnement est
# genere dans un repertoire temporaire, avec des valeurs FICTIVES, et detruit
# a la sortie.
#
# SANS DOCKER, SANS NAVIGATEUR OU SANS NODE, ELLE REND 4 — NON EXECUTEE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$(dirname "$HERE")")/eurostruct"
[[ -f "$RACINE/compose.yaml" ]] || RACINE="$(dirname "$(dirname "$HERE")")"

JETON="$(tr -dc 'a-f0-9' </dev/urandom | head -c 10)"
PROJET="esc-recette-$JETON"
TMP="$(mktemp -d)"
ENVF="$TMP/recette.env"
ETAT="$TMP/etat.json"

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

PID_AUTH=""
nettoyer() {
  [[ -n "$PID_AUTH" ]] && kill "$PID_AUTH" 2>/dev/null
  # `-v` NE DETRUIT QUE LES VOLUMES DE CE PROJET, dont le nom porte le jeton.
  docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" \
    down -v --remove-orphans >/dev/null 2>&1
  rm -rf "$TMP"
}
trap nettoyer EXIT

command -v docker >/dev/null 2>&1 || {
  echo "NON EXECUTE: docker absent." >&2; exit 4; }
docker info >/dev/null 2>&1 || {
  echo "NON EXECUTE: le demon docker ne repond pas." >&2; exit 4; }
command -v node >/dev/null 2>&1 || {
  echo "NON EXECUTE: node absent." >&2; exit 4; }
node "$RACINE/web/e2e/verifier_navigateur.mjs" >/dev/null 2>&1 || {
  echo "NON EXECUTE: Playwright ou Chromium absent." >&2; exit 4; }

PORT_AUTH="${EUROSTRUCT_RECETTE_PORT_AUTH:-54341}"
PORT_API="${EUROSTRUCT_RECETTE_PORT_API:-8031}"
PORT_WEB="${EUROSTRUCT_RECETTE_PORT_WEB:-3031}"
ACTEUR_A="22222222-9999-9999-9999-9999990000a1"
RACINE_ID="11111111-9999-9999-9999-999999000001"
ORG_A="44444444-9999-9999-9999-9999990000c1"

# AUCUN DES TROIS PORTS NE DOIT DEJA REPONDRE. S'il repond, la recette
# piloterait un autre serveur que celui qu'elle vient de construire.
for duo in "$PORT_AUTH:emetteur" "$PORT_API:API" "$PORT_WEB:interface"; do
  P="${duo%%:*}"
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$P" 2>/dev/null; then
    echo "      ECHEC: le port $P (${duo##*:}) repond deja." >&2
    exit 2
  fi
done

echo "    recette de production: la verticale entiere, puis un redemarrage"

# ---------------------------------------------------------------------------
# L'HOTE VU DEPUIS UN CONTENEUR
# ---------------------------------------------------------------------------
HOTE="$(docker network inspect bridge \
  -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null)"
[[ "$HOTE" =~ ^[0-9]+(\.[0-9]+){3}$ ]] || HOTE="host.docker.internal"

EUROSTRUCT_SUPABASE_LOCAL_BIND="$HOTE" \
EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH" \
EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://$HOTE:$PORT_AUTH/auth/v1" \
EUROSTRUCT_E2E_COMPTES="a@fictif.invalid:FICTIF-A:$ACTEUR_A:7200:oui" \
  node "$RACINE/web/e2e/supabase_local.mjs" >"$TMP/auth.log" 2>&1 &
PID_AUTH=$!

for _ in $(seq 1 40); do
  curl -fsS --max-time 2 "http://$HOTE:$PORT_AUTH/jwks" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS --max-time 2 "http://$HOTE:$PORT_AUTH/jwks" >/dev/null 2>&1 || {
  echo "      ECHEC: l'emetteur local n'a pas demarre." >&2
  sed -n '1,15p' "$TMP/auth.log" >&2; exit 1; }

# ---------------------------------------------------------------------------
# L'IDENTITE DE BUILD, DERIVEE DE L'ARBRE QU'ON RECETTE
#
# LA PERSISTANCE LA REFUSE QUAND ELLE MANQUE, et c'est le comportement voulu:
# un calcul conserve doit designer le CODE EXACT qui l'a produit, et la version
# seule ne le fait pas — six commits successifs portent la meme. Mesure du
# 02/09, premiere execution de cette recette: sans elle, chaque
# `POST /beam-verifications` rendait 503 et la recette n'avait rien a mesurer.
#
# UN ARBRE MODIFIE N'EST PAS SON DERNIER COMMIT: le suffixe le dit, plutot que
# de laisser croire qu'un calcul enregistre correspond au code pousse. C'est la
# meme regle que `dev.sh`, et elle vaut ici pour la meme raison.
# ---------------------------------------------------------------------------
BUILD_SHA="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || true)"
if [[ -n "$BUILD_SHA" ]] && ! git -C "$RACINE" diff --quiet 2>/dev/null; then
  BUILD_SHA="${BUILD_SHA}-modifie"
fi
if [[ -z "$BUILD_SHA" ]]; then
  echo "NON EXECUTE: aucun depot lisible, donc aucune identite de build." >&2
  echo "       La recette ne peut rien enregistrer, et n'inventera pas une" >&2
  echo "       identite qui ressemblerait a une reponse." >&2
  exit 4
fi
echo "    build: $BUILD_SHA"

# ---------------------------------------------------------------------------
# L'ENVIRONNEMENT — FICTIF, TEMPORAIRE, JAMAIS VERSIONNE
# ---------------------------------------------------------------------------
cat > "$ENVF" <<FIN
EUROSTRUCT_BUILD_SHA=$BUILD_SHA
POSTGRES_USER=eurostruct_super_$JETON
POSTGRES_PASSWORD=FICTIF-super-$JETON
POSTGRES_DB=eurostruct
EUROSTRUCT_PLAN_DB_USER=eurostruct_plan_$JETON
EUROSTRUCT_PLAN_DB_PASSWORD=FICTIF-plan-$JETON
EUROSTRUCT_MIGRATOR_DB_USER=eurostruct_mig_$JETON
EUROSTRUCT_MIGRATOR_DB_PASSWORD=FICTIF-mig-$JETON
EUROSTRUCT_APP_DB_USER=eurostruct_app_$JETON
EUROSTRUCT_APP_DB_PASSWORD=FICTIF-app-$JETON
EUROSTRUCT_LOCAL_AUTH_STUB=oui
EUROSTRUCT_BOOTSTRAP_MANDATE=$RACINE_ID:FICTIF-EMPREINTE-RECETTE-$JETON
EUROSTRUCT_BOOTSTRAP_ACTOR=$RACINE_ID
EUROSTRUCT_BOOTSTRAP_NAME=FICTIF racine (recette)
EUROSTRUCT_BOOTSTRAP_REASON=FICTIF amorcage de la recette
EUROSTRUCT_SUPABASE_JWKS_URL=http://$HOTE:$PORT_AUTH/jwks
EUROSTRUCT_SUPABASE_ISSUER=http://$HOTE:$PORT_AUTH/auth/v1
EUROSTRUCT_SUPABASE_AUDIENCE=authenticated
EUROSTRUCT_JWT_ALGORITHMS=RS256
EUROSTRUCT_PUBLIC_API_URL=http://127.0.0.1:$PORT_API
EUROSTRUCT_PUBLIC_SUPABASE_URL=http://$HOTE:$PORT_AUTH
EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY=FICTIF-ANON-$JETON
EUROSTRUCT_CORS_ORIGINS=http://localhost:$PORT_WEB,http://127.0.0.1:$PORT_WEB
API_PORT=$PORT_API
WEB_PORT=$PORT_WEB
EUROSTRUCT_STORAGE_BACKEND=s3
EUROSTRUCT_S3_ENDPOINT=http://objets:9000
EUROSTRUCT_S3_REGION=us-east-1
EUROSTRUCT_S3_BUCKET=eurostruct-livrables
EUROSTRUCT_S3_PREFIX=livrables
EUROSTRUCT_S3_PATH_STYLE=oui
EUROSTRUCT_S3_ACCESS_KEY_ID=FICTIFMINIO$JETON
EUROSTRUCT_S3_SECRET_ACCESS_KEY=FICTIFSECRET-$JETON-0123456789
EUROSTRUCT_S3_VERIFY_TLS=oui
FIN

dc() { docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" "$@"; }
SUPER="eurostruct_super_$JETON"
BASE_DB="eurostruct"

# LE SUPERUTILISATEUR NE SERT QU'A CONSTATER, JAMAIS A AGIR EN LIEU ET PLACE
# DU PRODUIT. Le decor metier et les comptages passent par lui parce qu'ils
# sont HORS produit; tout ce que la recette EPROUVE passe par les routes, sous
# l'identite authentifiee de l'ingenieur.
psql_super() {
  dc exec -T db psql -X -q -tA -U "$SUPER" -d "$BASE_DB" -c "$1" 2>&1
}

# ---------------------------------------------------------------------------
# 1. LA PILE MONTE — IMAGES CONSTRUITES DEPUIS LES FICHIERS VERSIONNES
# ---------------------------------------------------------------------------
echo "    construction des images et demarrage (cela prend quelques minutes)"

# LE PROXY DE L'ENVIRONNEMENT EST TRANSMIS AU BUILD, S'IL Y EN A UN.
#
# `HTTPS_PROXY` et `NO_PROXY` sont des arguments de build PREDEFINIS de Docker:
# ils n'exigent aucun `ARG` dans le Dockerfile, et les Dockerfiles du depot
# n'en portent donc pas. Sans cette transmission, un environnement dont la
# sortie passe par un proxy — une integration continue d'entreprise, ce bac a
# sable — echoue a `pip install` sur un message de reseau qui ne dit pas
# pourquoi.
#
# CE N'EST PAS UNE CONFIGURATION DU PRODUIT. Rien n'est ecrit dans l'image: un
# argument de build predefini ne survit pas a la couche qui l'utilise.
PROCURATION=()
if [[ -n "${HTTPS_PROXY:-}" ]]; then
  PROCURATION=(--build-arg "HTTPS_PROXY=$HTTPS_PROXY"
               --build-arg "NO_PROXY=${NO_PROXY:-}")
  echo "    (le proxy de l'environnement est transmis au build)"
fi

if ! dc build "${PROCURATION[@]}" >"$TMP/build.log" 2>&1; then
  echoue "la construction des images a echoue."
  tail -n 30 "$TMP/build.log" >&2
  exit 1
fi

if ! dc up --wait --wait-timeout 900 >"$TMP/up.log" 2>&1; then
  echoue "la composition n'est pas montee."
  tail -n 25 "$TMP/up.log" >&2
  echo "      --- journal du service init ---" >&2
  dc logs --no-color init 2>&1 | tail -n 30 >&2
  dc ps >&2 2>/dev/null
  exit 1
fi

ETAT_BASE="$(psql_super "select normative_activation_state()" | tr -d ' \r')"
[[ "$ETAT_BASE" == "ACTIVE" ]] \
  || echoue "la base n'est pas ACTIVE (« $ETAT_BASE »)."

SANTE="$(curl -fsS --max-time 15 "http://127.0.0.1:$PORT_API/health" 2>&1)"
grep -q '"status":"ok"' <<<"$SANTE" || echoue "/health: $SANTE"
PRET="$(curl -sS --max-time 25 "http://127.0.0.1:$PORT_API/ready" 2>&1)"
grep -q '"ready":true' <<<"$PRET" \
  || echoue "/ready n'est pas vert: $(cut -c1-300 <<<"$PRET")"

for _ in $(seq 1 60); do
  curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$PORT_WEB" && break
  sleep 1
done
curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$PORT_WEB" \
  || echoue "l'interface ne repond pas sur le port $PORT_WEB."

[[ $KO -eq 0 ]] || exit 1

# ---------------------------------------------------------------------------
# 2. LE DECOR METIER — POSE PAR LE PROPRIETAIRE, PAS PAR LE PRODUIT
#
# Creer une organisation et enroler ses membres releve de l'administration du
# compte; aucune route du produit ne le fait, et lui en donner une ici ferait
# passer pour eprouve un chemin qui n'existe pas.
#
# AUCUNE VALEUR NORMATIVE N'EST INSEREE. Seul le DOCUMENT est declare — sans
# lui, la creation de projet refuserait, et elle aurait raison: un projet
# citerait un referentiel absent a sa date.
# ---------------------------------------------------------------------------
DECOR="$(psql_super "
insert into auth.users (id) values ('$ACTEUR_A') on conflict do nothing;
insert into organizations (id, name, country)
  values ('$ORG_A', 'FICTIF Bureau de recette', 'BE') on conflict do nothing;
insert into organization_members (org_id, user_id, role, display_name)
  values ('$ORG_A', '$ACTEUR_A', 'engineer', 'FICTIF Ing. A')
  on conflict do nothing;
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
  values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
          'FICTIF — edition de recette', date '2010-08-01',
          'FICTIF — organisme de recette')
  on conflict do nothing;")"
if grep -qiE "ERROR|FATAL" <<<"$DECOR"; then
  echoue "le decor metier n'est pas pose: $(grep -m1 -iE 'ERROR|FATAL' <<<"$DECOR" | cut -c1-200)"
  exit 1
fi

NB_MEM="$(psql_super "select count(*) from organization_members" | tr -d ' \r')"
NB_ANX="$(psql_super "select count(*) from national_annexes
                       where country_code = 'BE'" | tr -d ' \r')"
[[ "$NB_MEM" == "1" && "$NB_ANX" != "0" ]] \
  || { echoue "decor incomplet: membres=$NB_MEM annexes=$NB_ANX"; exit 1; }

# ---------------------------------------------------------------------------
# 3. PHASE « AVANT » — LA VERTICALE, DU PROJET AU PLAN
# ---------------------------------------------------------------------------
export EUROSTRUCT_WEB="http://127.0.0.1:$PORT_WEB"
export EUROSTRUCT_API="http://127.0.0.1:$PORT_API"
export EUROSTRUCT_RECETTE_ETAT="$ETAT"
export EUROSTRUCT_E2E_TELECHARGEMENTS="$TMP/telechargements"
mkdir -p "$EUROSTRUCT_E2E_TELECHARGEMENTS"

echo ""
EUROSTRUCT_RECETTE_PHASE=avant node "$RACINE/web/e2e/recette_production.mjs"
CODE_AVANT=$?
[[ $CODE_AVANT -eq 0 ]] || KO=1

# ---------------------------------------------------------------------------
# 4. LE COMPTE DES OBJETS, AVANT REDEMARRAGE
#
# ON REGARDE LE MAGASIN, PAS LA BASE. Toute la question est de savoir si les
# deux disent la meme chose; les interroger par le meme chemin ne prouverait
# rien.
# ---------------------------------------------------------------------------
compter_objets() {
  dc run --rm --entrypoint sh objets-init -c \
    'mc ls --recursive "esc/${EUROSTRUCT_S3_BUCKET:-eurostruct-livrables}" 2>/dev/null | wc -l' \
    2>/dev/null | tr -d ' \r\n'
}
OBJETS_AVANT="$(compter_objets)"

# TROIS LIGNES DE LIVRABLE, DEUX OBJETS. La note PDF en fait un; les deux
# demandes du plan partagent le leur, puisque le chemin derive du SHA-256 et
# que deux rendus du meme dessin ont la meme empreinte. La generation refusee
# — un plan sur une etude en echec — n'en fait aucun.
if [[ "$OBJETS_AVANT" != "2" ]]; then
  echoue "le magasin porte $OBJETS_AVANT objet(s) au lieu de 2."
  echoue "  Trois demandes ont abouti (1 note + 2 plans identiques) et une a"
  echoue "  ete refusee: deux objets, ou un orphelin s'est glisse."
fi

# ---------------------------------------------------------------------------
# 5. L'ARRET ET LE REDEMARRAGE — LE GESTE QUE PERSONNE D'AUTRE NE FAIT
#
# `stop` PUIS `start`, PAS `restart`: on veut que les processus MEURENT, pas
# qu'ils soient signales. Un `restart` qui echouerait a tuer laisserait le
# meme interprete Python servir la seconde phase, et le determinisme
# inter-processus ne serait pas eprouve du tout.
# ---------------------------------------------------------------------------
echo ""
echo "    arret de l'API et de l'interface"
dc stop api web >"$TMP/stop.log" 2>&1 || echoue "l'arret a echoue."

for duo in "$PORT_API:API" "$PORT_WEB:interface"; do
  P="${duo%%:*}"
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$P" 2>/dev/null; then
    echoue "le port $P (${duo##*:}) repond encore apres l'arret."
  fi
done

echo "    redemarrage"
dc start api web >"$TMP/start.log" 2>&1 || echoue "le redemarrage a echoue."

PRET=""
for _ in $(seq 1 60); do
  PRET="$(curl -sS --max-time 5 "http://127.0.0.1:$PORT_API/ready" 2>&1)"
  grep -q '"ready":true' <<<"$PRET" && break
  sleep 1
done
grep -q '"ready":true' <<<"$PRET" \
  || echoue "/ready n'est pas revenu au vert: $(cut -c1-300 <<<"$PRET")"

# `2>/dev/null` SUR L'ATTENTE, PAS SUR LE VERDICT. Pendant qu'un service
# revient, `curl` ecrit « Connection reset by peer » a chaque tentative: ce
# bruit-la n'apprend rien et brouille la lecture du rapport. L'echec final,
# lui, reste visible.
for _ in $(seq 1 60); do
  curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$PORT_WEB" 2>/dev/null \
    && break
  sleep 1
done
curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$PORT_WEB" \
  || echoue "l'interface n'est pas revenue."

# ---------------------------------------------------------------------------
# 6. PHASE « APRES » — RELECTURE ET RE-TELECHARGEMENT
# ---------------------------------------------------------------------------
echo ""
EUROSTRUCT_RECETTE_PHASE=apres node "$RACINE/web/e2e/recette_production.mjs"
CODE_APRES=$?
[[ $CODE_APRES -eq 0 ]] || KO=1

# ---------------------------------------------------------------------------
# 7. LE COMPTE DES OBJETS, APRES — IL NE DOIT PAS AVOIR BOUGE
#
# La troisieme demande du plan, faite apres redemarrage, doit retomber sur le
# MEME objet. S'il y en a trois, un processus neuf a produit d'autres octets:
# le determinisme inter-processus est casse, et le magasin — qui ne supprime
# jamais — gardera les deux versions pour toujours.
# ---------------------------------------------------------------------------
OBJETS_APRES="$(compter_objets)"
if [[ "$OBJETS_APRES" != "2" ]]; then
  echoue "le magasin porte $OBJETS_APRES objet(s) apres redemarrage (2 avant)."
  echoue "  Une troisieme demande du meme plan a donc ecrit d'autres octets."
fi

# LE COMPTE DES LIGNES SE LIT EN SUPERUTILISATEUR, et c'est la seule facon.
#
# `deliverables` porte une RLS `FORCE`: le login applicatif ne voit que ce que
# son acteur courant lui donne le droit de voir, et un `psql` sans
# `eurostruct.actor_id` ne voit RIEN. Mesure du 02/09: la ligne s'affichait
# vide, ce qui ressemblait a une base vide alors que le magasin portait bien
# ses deux objets. Le superutilisateur, lui, n'est pas soumis a la RLS — c'est
# precisement pourquoi le produit ne s'en sert jamais, et pourquoi un CONSTAT
# hors produit peut s'en servir.
NB_LIGNES="$(psql_super "select count(*) from deliverables" | tr -d ' \r')"

echo ""
echo "    magasin: $OBJETS_AVANT objet(s) avant, $OBJETS_APRES apres"
echo "    base:    $NB_LIGNES ligne(s) de livrable"
# QUATRE LIGNES, DEUX OBJETS: c'est le fait qu'on veut voir cote a cote.
#
# Quatre gestes enregistres — la note, puis TROIS demandes du meme plan, dont
# une apres redemarrage — et deux fichiers seulement, parce que les trois plans
# portent le meme contenu et que le chemin derive du contenu. Un cinquieme
# geste, le plan force sur une etude en echec, n'a laisse ni ligne ni octet.
[[ "$NB_LIGNES" == "4" ]] \
  || echoue "$NB_LIGNES ligne(s) de livrable au lieu de 4."

if [[ $KO -ne 0 ]]; then
  echo ""
  echo "      --- api, 20 dernieres lignes ---" >&2
  dc logs --no-color --tail 20 api >&2 2>/dev/null
  echo "      --- web, 20 dernieres lignes ---" >&2
  dc logs --no-color --tail 20 web >&2 2>/dev/null
  exit 1
fi

echo ""
echo "==================================================="
echo " Recette de production: la verticale entiere sur la"
echo " composition — images construites depuis les seuls"
echo " fichiers versionnes, next build puis next start —"
echo " puis l'API et l'interface arretees et redemarrees."
echo ""
echo " Le calcul, ses quatre empreintes et son instantane"
echo " normatif sont inchanges; le PDF et le DXF portent"
echo " les memes octets; une troisieme demande du plan"
echo " retombe sur le meme objet; et le magasin n'a pas"
echo " grossi d'un seul fichier."
echo "==================================================="
