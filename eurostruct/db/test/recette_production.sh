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
# ELLE EXIGE UN CONTEXTE DE BUILD GIT-ONLY, ET LE REFUSE AUTREMENT
# ------------------------------------------------------------------
# Les images se construisent avec `context: .` — le repertoire sur le disque.
# La recette refuse donc de demarrer si quoi que ce soit y traine qui ne soit
# pas dans le commit: fichier suivi modifie, changement indexe, ou fichier non
# versionne. Voir la section « LE CONTEXTE DE BUILD EST L'ARBRE COMMITE ».
#
#   git worktree add --detach <chemin> <sha>   # la forme attendue
#
# SANS DOCKER, SANS NAVIGATEUR OU SANS NODE, ELLE REND 4 — NON EXECUTEE.
# AVEC UN CONTEXTE SALE, ELLE REND 2 — REFUSEE.
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
# LE CONTEXTE DE BUILD EST L'ARBRE COMMITE, ET RIEN D'AUTRE
#
# CE QUI ETAIT AFFIRME SANS ETRE GARANTI
# ---------------------------------------
# Les trois images se construisent avec `context: .` — le repertoire present
# SUR LE DISQUE, pas un instantane Git. Cette recette calculait un suffixe
# « -modifie » et continuait: elle DISAIT qu'un fichier avait bougé, puis le
# construisait quand meme. Le rapport, lui, affirmait « images construites
# depuis les seuls fichiers versionnes » — ce qui n'etait vrai que par hasard,
# quand l'arbre se trouvait propre.
#
# Un fichier source modifie, indexe ou non versionne entrait donc dans l'image
# sans qu'aucune ligne ne le dise, et la recette prouvait alors quelque chose
# a propos d'un code qui n'existe nulle part.
#
# CE QUI EST GARANTI MAINTENANT: QUATRE FAITS, OU RIEN
# -----------------------------------------------------
#   HEAD identique      — le SHA construit est celui du commit courant;
#   index propre        — rien de mis en scene et non commite;
#   arbre propre        — aucun fichier suivi modifie;
#   aucun fichier source non versionne dans le contexte.
#
# LE QUATRIEME EST LE PLUS FORT, ET IL EST DELIBEREMENT PLUS LARGE QUE
# `.dockerignore`. On refuse TOUT fichier que Git ne suit pas — y compris ceux
# qu'il ignore. Autrement il faudrait reimplementer les motifs de
# `.dockerignore` en bash pour savoir lesquels entreraient, et une divergence
# entre les deux fichiers d'exclusion redeviendrait invisible. Exiger un
# repertoire ou Git connait TOUT ferme la question sans l'interpreter: le
# contexte est alors, litteralement, l'arbre commite.
#
# CE QUE CELA IMPOSE A L'OPERATEUR: un worktree detache et propre du SHA a
# recetter. C'est aussi ce qu'exige la campagne finale.
#
#   git worktree add --detach <chemin> <sha>
#
# L'IDENTITE DE BUILD EST ALORS LE SHA NU. `EUROSTRUCT_BUILD_SHA` designe le
# code exact qui a produit un calcul conserve: la persistance refuse un calcul
# qui n'en porte pas — mesure du 02/09, chaque `POST /beam-verifications`
# rendait 503 sans elle — et un suffixe « -modifie » n'a plus lieu d'exister
# puisqu'un arbre modifie n'arrive plus jusqu'ici.
# ---------------------------------------------------------------------------
BUILD_SHA="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || true)"
if [[ -z "$BUILD_SHA" ]]; then
  echo "NON EXECUTE: aucun depot lisible, donc aucune identite de build." >&2
  echo "       La recette ne peut rien enregistrer, et n'inventera pas une" >&2
  echo "       identite qui ressemblerait a une reponse." >&2
  exit 4
fi

# `--ignored=matching` fait ressortir AUSSI les fichiers ignores: c'est
# exactement ce qu'on veut refuser. `-uall` descend dans les repertoires
# plutot que de resumer « dossier/ », pour pouvoir NOMMER le fichier fautif.
#
# `-- .` BORNE LE CONSTAT AU CONTEXTE DE BUILD, et c'est necessaire dans les
# deux sens: le depot porte aussi `bapica/`, qui n'entre dans aucune image —
# le salir ne doit pas bloquer la recette — et un cache a la RACINE du depot
# (`.ruff_cache/`) n'est pas davantage dans le contexte. Sans cette borne, la
# garde refuserait pour des fichiers qui ne peuvent pas atteindre une couche.
contexte_git_only() {
  git -C "$RACINE" status --porcelain --untracked-files=all \
      --ignored=matching -- .
}

RESIDU="$(contexte_git_only)"
if [[ -n "$RESIDU" ]]; then
  echo "      ECHEC: le contexte de build n'est pas l'arbre commite." >&2
  echo "" >&2
  echo "      Les images se construisent depuis le repertoire present sur le" >&2
  echo "      disque. Ce qui suit y entrerait sans etre dans le commit" >&2
  echo "      $BUILD_SHA — la recette prouverait alors quelque chose a" >&2
  echo "      propos d'un code qui n'existe nulle part:" >&2
  echo "" >&2
  sed -n '1,20p' <<<"$RESIDU" | sed 's/^/        /' >&2
  [[ "$(wc -l <<<"$RESIDU")" -gt 20 ]] && echo "        ..." >&2
  echo "" >&2
  echo "      Recettez depuis un worktree detache et propre:" >&2
  echo "        git worktree add --detach <chemin> $BUILD_SHA" >&2
  exit 2
fi

echo "    build: $BUILD_SHA"
echo "    contexte Git-only, avant construction:"
echo "      HEAD identique                                    oui ($BUILD_SHA)"
echo "      index propre                                      oui"
echo "      arbre propre                                      oui"
echo "      aucun fichier source non versionne dans le contexte  oui"

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
# CINQ LIGNES, DEUX OBJETS: c'est le fait qu'on veut voir cote a cote.
#
# Cinq gestes enregistres — DEUX demandes de la note, dont une par un processus
# neuf apres redemarrage, et TROIS demandes du meme plan, dont une apres
# redemarrage — et deux fichiers seulement, parce que les deux notes portent le
# meme contenu, les trois plans aussi, et que le chemin derive du contenu.
#
# C'EST LE COUPLE QUI PROUVE, PAS L'UN DES DEUX. Cinq lignes avec trois objets
# dirait qu'une composition a divergé; deux objets avec quatre lignes dirait
# qu'un geste n'a pas eu lieu.
#
# Un sixieme geste, le plan force sur une etude en echec, n'a laisse ni ligne
# ni octet: le refus precede la composition.
[[ "$NB_LIGNES" == "5" ]] \
  || echoue "$NB_LIGNES ligne(s) de livrable au lieu de 5."

# ---------------------------------------------------------------------------
# 8. LE CONTEXTE, RECONSTATE APRES COUP
#
# LE CONSTAT D'AVANT NE VAUT QUE POUR L'INSTANT OU IL A ETE FAIT. Entre-temps
# la recette a construit trois images, monte cinq services et pilote un
# navigateur: un `npm install`, un cache ecrit dans l'arbre ou un
# `git checkout` concurrent auraient sali le contexte SANS que rien ne le dise,
# et le verdict porterait alors sur un arbre qui n'est plus celui qu'on a
# construit.
#
# ON REVERIFIE DONC LES QUATRE MEMES FAITS, dont le premier: le SHA n'a pas
# bouge sous nos pieds.
# ---------------------------------------------------------------------------
SHA_APRES="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || true)"
RESIDU_APRES="$(contexte_git_only)"

echo ""
echo "    contexte Git-only, apres la recette:"
if [[ "$SHA_APRES" == "$BUILD_SHA" ]]; then
  echo "      HEAD identique                                    oui ($SHA_APRES)"
else
  echo "      HEAD identique                                    NON" >&2
  echoue "HEAD a change pendant la recette: $BUILD_SHA -> ${SHA_APRES:-?}."
fi
if [[ -z "$RESIDU_APRES" ]]; then
  echo "      index propre                                      oui"
  echo "      arbre propre                                      oui"
  echo "      aucun fichier source non versionne dans le contexte  oui"
else
  echo "      index/arbre/non versionne                         NON" >&2
  echoue "le contexte a ete sali pendant la recette:"
  sed -n '1,10p' <<<"$RESIDU_APRES" | sed 's/^/        /' >&2
fi

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
echo " Le contexte de build etait l'arbre commite, et il"
echo " l'est reste: rien de modifie, d'indexe ni de non"
echo " versionne n'a pu entrer dans une image."
echo ""
echo " Le calcul, ses quatre empreintes et son instantane"
echo " normatif sont inchanges. La note ET le plan sont"
echo " RECOMPOSES par un processus neuf, aux memes octets:"
echo " cinq lignes de livrable pour deux objets physiques."
echo " Ce n'est donc pas la persistance qui est eprouvee"
echo " ici, c'est la composition."
echo "==================================================="
