#!/usr/bin/env bash
#
# EUROSTRUCT — REPETITION LOCALE DE LA MISE A DISPOSITION SUR STAGING
#
#   EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
#   PGHOST=/var/run/postgresql PGUSER=postgres \
#   deploy/staging_repetition.sh
#
# CE QUE CE SCRIPT ETABLIT
# -------------------------
# Que `compose.staging.yaml` et `deploy/staging.sh` tiennent ENSEMBLE, dans
# l'ordre de la procedure de docs/STAGING.md, contre une base et un emetteur
# EXTERIEURS a la composition:
#
#   * un PostgreSQL local jetable, provisionne comme une base hebergee le
#     serait (docs/DEPLOIEMENT_BASE_HEBERGEE.md §2): trois roles non
#     superutilisateurs, schema `auth` fictif, aucun superutilisateur pendant
#     la procedure — et joint par les CONTENEURS a travers le pont Docker,
#     comme une base distante;
#   * l'emetteur de jetons des parcours navigateur (`web/e2e/supabase_local.mjs`)
#     lance sur l'hote, HORS de la composition, comme Supabase Auth le serait;
#   * le MANDATAIRE TLS de la composition (Caddy, deploy/Caddyfile) servant
#     TROIS noms publics — staging.localhost, api.staging.localhost et
#     auth.staging.localhost — en https sur 127.0.0.1:443, avec son autorite
#     locale (`tls internal`): les noms sont resolus vers la boucle locale par
#     `--resolve` et par les regles de resolution du navigateur, et le
#     certificat est VERIFIE contre cette autorite, jamais ignore.
#
# Puis: prerequis, privileges, migrer, up, status (les controles des URL
# publiques), un parcours PAR LES URL PUBLIQUES (bureau, projet, etude, note
# PDF telechargee et verifiee), un REDEMARRAGE (down, up, relecture de l'etude
# et de sa note a l'identique), la recette de bout en bout
# (`db/test/recette_supabase_staging.sh executer`), down. Chaque pas est note
# EXECUTE / ECHOUE / NON EXECUTE.
#
# ET UN NAVIGATEUR REEL, aux pas 8b et 9b: Chromium traverse le mandataire sous
# les noms publics, avec l'autorite locale APPROUVEE dans son magasin de
# certificats (certutil, base NSS d'un $HOME dedie) — jamais
# `ignoreHTTPSErrors`. Il fait le parcours du produit, puis le refait apres le
# redemarrage, et rapporte ce que `curl` ne peut pas dire: erreurs JavaScript,
# ressources qu'il n'a pas pu charger, contenu mixte, echanges interface/API et
# leurs codes, maintien de la session.
#
# CE QUE CELA N'ETABLIT PAS. Rien sur Supabase: ni ses roles, ni son JWKS, ni
# son reseau. `SUPABASE_UNVERIFIED` reste vrai. C'est la repetition de la
# procedure, pas la procedure.
#
# CE QU'IL EXIGE, ET CE QU'IL DETRUIT. Un cluster PostgreSQL JETABLE prouve
# tel (lib_harnais.sh), qui accepte les connexions TCP depuis les ponts Docker
# (`listen_addresses`, une ligne `pg_hba`); Docker, node, la venv de l'API;
# les ports 80 et 443 de la boucle locale, libres. Il ne detruit que ce qu'il
# a cree, nom par nom: ses bases, ses roles, sa composition
# (`eurostruct-staging-repetition`, volumes compris), son emetteur. Ses
# fichiers — env genere (0600), cle d'emetteur, autorite locale du
# mandataire, journaux — vont sous deploy/staging-repetition/, ignore par
# Git; l'env et l'autorite sont effaces a la sortie.
#
# CODES: 0 tout est tenu; 1 un pas a echoue; 2 refus (cluster non jetable,
# roles presents); 4 non executable (prerequis).
set -uo pipefail
set +x

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
# shellcheck source=../db/test/lib_harnais.sh
source "$RACINE/db/test/lib_harnais.sh"
harnais_piege_signaux 2>/dev/null || true

exiger_precontrole_local "staging_repetition.sh" || exit 2
harnais_verrou_prendre "staging_repetition.sh" || exit $?
exiger_cluster_jetable "staging_repetition.sh" || exit 2
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend eurostruct_reconciliation)
exiger_roles_absents "staging_repetition.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

for outil in docker node curl python3 psql pg_dump pg_restore git; do
  command -v "$outil" >/dev/null 2>&1 || { echo "NON EXECUTE: $outil absent." >&2; exit 4; }
done
[[ -n "${EUROSTRUCT_VENV:-}" && -x "$EUROSTRUCT_VENV/bin/python3" ]] \
  && export PATH="$EUROSTRUCT_VENV/bin:$PATH"
python3 -c "import eurostruct_api, uvicorn" 2>/dev/null \
  || { echo "NON EXECUTE: eurostruct_api ou uvicorn absent de python3 (EUROSTRUCT_VENV)." >&2; exit 4; }
docker info >/dev/null 2>&1 || { echo "NON EXECUTE: le demon docker ne repond pas." >&2; exit 4; }
# LE MANDATAIRE ECOUTE SUR 127.0.0.1:80 ET :443 — les ports d'un vrai staging,
# sur la boucle locale. Pris, il ne demarrerait pas, et « up » le dirait tard.
if command -v ss >/dev/null 2>&1; then
  for p in 80 443; do
    ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$p$" \
      && { echo "NON EXECUTE: le port $p de l'hote est deja pris; le mandataire de la repetition l'ecoute sur 127.0.0.1." >&2; exit 4; }
  done
fi

# ---------------------------------------------------------------------------
# LES NOMS — tous suffixes d'un jeton, donc detruisibles nom par nom
# ---------------------------------------------------------------------------
HOTE="${EUROSTRUCT_REPETITION_HOTE:-172.17.0.1}"   # l'hote, vu des conteneurs
PORT_API="${EUROSTRUCT_REPETITION_PORT_API:-8048}"
PORT_WEB="${EUROSTRUCT_REPETITION_PORT_WEB:-3048}"
PORT_AUTH="${EUROSTRUCT_REPETITION_PORT_AUTH:-54398}"
# LES NOMS PUBLICS, servis par le mandataire sur 127.0.0.1:443 et resolus
# par curl (--resolve) et par le navigateur (--host-resolver-rules): aucun DNS,
# aucun /etc/hosts touche.
NOM_WEB="staging.localhost"; NOM_API="api.staging.localhost"
URL_WEB="https://$NOM_WEB"; URL_API="https://$NOM_API"
# LE TROISIEME NOM: L'EMETTEUR DE JETONS, LUI AUSSI EN HTTPS.
#
# Il tourne HORS de la composition, sur l'hote, comme Supabase Auth le serait.
# Tant que le navigateur n'etait pas dans la boucle, son adresse en clair
# suffisait: `curl` s'en accommode. UN NAVIGATEUR, NON — une page servie en
# https qui va chercher son jeton en « http://127.0.0.1:… » fait du CONTENU
# MIXTE, et Chromium le bloque: la connexion echoue sans qu'aucune erreur
# n'apparaisse cote serveur. Le mandataire lui donne donc un nom et un
# certificat, comme aux deux autres. Sur un staging reel, Supabase est deja en
# https et ce troisieme site n'existe pas.
NOM_AUTH="auth.staging.localhost"; URL_AUTH="https://$NOM_AUTH"
RESOLUTION="$NOM_WEB:443:127.0.0.1,$NOM_API:443:127.0.0.1,$NOM_AUTH:443:127.0.0.1,$NOM_WEB:80:127.0.0.1,$NOM_API:80:127.0.0.1,$NOM_AUTH:80:127.0.0.1"
JETON="$(harnais_jeton)"
P="esc_rep"
MIG="${P}_mg_${JETON}"; CTL="${P}_pl_${JETON}"; SVC="${P}_ap_${JETON}"; SAV="${P}_sv_${JETON}"
BASE="${P}_db_${JETON}"; BASE_R="${P}_rs_${JETON}"
MDP="FICTIF-rep-${JETON}"
RACINE_ID="11111111-7777-7777-7777-7777770000${JETON:0:2}"
ACTEUR_A="22222222-7777-7777-7777-7777770000${JETON:0:2}"
ACTEUR_B="33333333-7777-7777-7777-7777770000${JETON:0:2}"
PROJET_COMPOSE="eurostruct-staging-repetition"
DOSSIER="$ICI/staging-repetition"
mkdir -p "$DOSSIER"; chmod 700 "$DOSSIER"
ENVR="$DOSSIER/staging.env"
CA="$DOSSIER/mandataire-ca-$JETON.crt"   # l'autorite locale du mandataire, copiee par « up »
CADDYFILE="$DOSSIER/Caddyfile-$JETON"    # celui du depot, plus le site de l'emetteur
NSS="$DOSSIER/nss-$JETON"                # le magasin de certificats du navigateur
ENVNAV="$DOSSIER/navigateur-$JETON.env"  # le compte d'essai, pour le parcours
SORTIE_NAV="$DOSSIER/navigateur-$JETON"  # captures et etat du parcours navigateur
JOURNAL="$DOSSIER/repetition-$(date -u +%Y%m%dT%H%M%SZ).log"
TMP="$(mktemp -d)"; chmod 700 "$TMP"
PID_AUTH=""
KO=0

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }

NOMS=("0 base joignable des conteneurs" "1 provisionnement (exploitant)"
      "2 emetteur exterieur" "3 staging.sh prerequis" "4 staging.sh privileges"
      "5 staging.sh migrer" "6 staging.sh up (mandataire TLS compris)" "7 staging.sh status (URL publiques)"
      "8 parcours par les URL publiques" "9 redemarrage: down, up, relecture"
      "10 recette de bout en bout" "11 staging.sh down"
      "8b parcours NAVIGATEUR par les URL publiques (Chromium, certificat verifie)"
      "9b parcours NAVIGATEUR apres redemarrage (session, relecture, octets)")
ETATS=(); DETAILS=()
for _ in "${NOMS[@]}"; do ETATS+=("NON EXECUTE"); DETAILS+=("non tente"); done
poser()    { ETATS[$1]="$2"; DETAILS[$1]="$3"; }
execute()  { poser "$1" "EXECUTE" "$2"; }
echoue()   { poser "$1" "ECHOUE" "$2"; KO=1; }
non_exec() { poser "$1" "NON EXECUTE" "$2"; }

staging() {   # staging <commande...> — deploy/staging.sh sur l'env de repetition
  EUROSTRUCT_STAGING_ENV="$ENVR" EUROSTRUCT_STAGING_PROJET="$PROJET_COMPOSE" \
  EUROSTRUCT_STAGING_CIBLE=staging \
  EUROSTRUCT_STAGING_ARBRE_MODIFIE="$( git -C "$RACINE" diff --quiet 2>/dev/null && echo "" || echo oui )" \
    bash "$ICI/staging.sh" "$@"
}

nettoyer() {
  echo ""
  echo "--- nettoyage: composition, emetteur, bases et roles crees ---"
  if [[ -f "$ENVR" ]]; then
    COMPOSE_PROFILES=mandataire docker compose -p "$PROJET_COMPOSE" \
      -f "$RACINE/compose.yaml" -f "$RACINE/compose.staging.yaml" \
      --env-file "$ENVR" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -f "$ENVR"
  fi
  rm -f "$CA" "$CADDYFILE"
  rm -rf "$NSS"
  [[ -n "$PID_AUTH" ]] && kill "$PID_AUTH" 2>/dev/null
  detruire_bases_creees
  detruire_roles_crees
  harnais_postcondition_nettoyage "staging_repetition.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"
  rm -rf "$TMP"
  harnais_verrou_rendre 2>/dev/null || true
}
trap nettoyer EXIT

echo "    repetition locale de la mise a disposition sur staging (cluster jetable, jeton $JETON)"
echo "    journal: $JOURNAL"

# ---------------------------------------------------------------------------
# 0. LA BASE DOIT ETRE JOIGNABLE DEPUIS UN CONTENEUR — comme une base distante
# ---------------------------------------------------------------------------
echo "==> 0. la base est-elle joignable des conteneurs ($HOTE:${PGPORT:-5432}) ?"
if docker run --rm postgres:16-bookworm pg_isready -h "$HOTE" -p "${PGPORT:-5432}" >"$TMP/isready.log" 2>&1; then
  execute 0 "pg_isready depuis un conteneur: $(tail -1 "$TMP/isready.log")"
else
  non_exec 0 "le cluster n'accepte pas les connexions depuis le pont Docker. Sur un cluster JETABLE: listen_addresses = '*' (postgresql.conf) et « host all all 172.16.0.0/12 scram-sha-256 » (pg_hba.conf), puis redemarrer."
  echo "NON EXECUTE: ${DETAILS[0]}" >&2
  exit 4
fi

# ---------------------------------------------------------------------------
# 1. CE QU'UN EXPLOITANT PROVISIONNE — et rien de plus (docs §2)
# ---------------------------------------------------------------------------
echo "==> 1. provisionnement: trois roles, la base, le schema auth fictif, les reglages"
{
  creer_role "$MIG" "login password '$MDP' createrole createdb" &&
  creer_role "$CTL" "login password '$MDP' createrole" &&
  creer_role "$SVC" "login password '$MDP'" &&
  # LE ROLE DE SAUVEGARDE DU FOURNISSEUR (BYPASSRLS): l'etape 6 de la recette.
  creer_role "$SAV" "login password '$MDP' bypassrls" &&
  adm -c "grant pg_read_all_data to \"$SAV\";" >/dev/null 2>&1 &&
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1 &&
  creer_base "$BASE" "owner \"$MIG\"" &&
  creer_base "$BASE_R" "owner \"$SAV\""
} || { echoue 1 "creation des roles ou des bases"; exit 1; }
for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do registre_role "$r"; done
admb -v ON_ERROR_STOP=1 -f "$RACINE/db/test/00_supabase_stub.sql" >/dev/null 2>&1 \
  || { echoue 1 "schema auth fictif"; exit 1; }
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL
adm -c "alter database \"$BASE\" set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
# LE MANDAT EST PROVISIONNE, PAR L'ADMINISTRATEUR: `ALTER DATABASE … SET` d'un
# parametre `eurostruct.*` est refuse a un non-superutilisateur (mesure a la
# quatrieme repetition, par le migrateur proprietaire). « staging.sh migrer »
# le CONSTATE et amorce la racine; il ne le pose pas.
MANDAT="$RACINE_ID:FICTIF-MANDAT-REP-$JETON"
adm -c "alter database \"$BASE\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1
# LES COMPTES EXISTENT DANS auth.users — c'est Supabase Auth qui les creerait.
admb -v ON_ERROR_STOP=1 -c "insert into auth.users (id) values
  ('$RACINE_ID'::uuid), ('$ACTEUR_A'::uuid), ('$ACTEUR_B'::uuid) on conflict do nothing;" >/dev/null 2>&1 \
  || { echoue 1 "inscription des comptes dans auth.users"; exit 1; }
# L'HOTE AUSSI DOIT JOINDRE LA BASE PAR L'ADRESSE DU PONT: la recette et le
# controle des privileges tournent sur l'hote avec la DSN des conteneurs.
# Mesure a la troisieme repetition: l'adresse SOURCE d'une connexion de
# l'hote vers 172.17.0.1 n'etait pas 172.17.0.1 mais celle de sa sortie
# reseau, sans entree pg_hba — et « connexion refusee » ne disait pas laquelle.
if ! PGPASSWORD="$MDP" psql -X -h "$HOTE" -p "${PGPORT:-5432}" -U "$SVC" -d "$BASE" -tAc "select 1" >"$TMP/hote.log" 2>&1; then
  source_ip="$(grep -oE 'host "[^"]+"' "$TMP/hote.log" | head -1 | tr -d '"' | cut -d' ' -f2)"
  non_exec 1 "l'hote ne joint pas la base par $HOTE comme le login applicatif (adresse source: ${source_ip:-inconnue}). Sur un cluster JETABLE, ajouter « host all all ${source_ip:-<adresse>}/32 scram-sha-256 » a pg_hba.conf et recharger."
  echo "NON EXECUTE: ${DETAILS[1]}" >&2
  exit 4
fi
execute 1 "roles $CTL, $MIG, $SVC, $SAV; bases $BASE, $BASE_R; auth fictif; trois comptes; base jointe de l'hote par $HOTE"

# ---------------------------------------------------------------------------
# 2. L'EMETTEUR DE JETONS, HORS DE LA COMPOSITION — comme Supabase Auth
# ---------------------------------------------------------------------------
echo "==> 2. emetteur de jetons sur l'hote (0.0.0.0:$PORT_AUTH), cle persistante"
EUROSTRUCT_SUPABASE_LOCAL_BIND=0.0.0.0 \
EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH" \
EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://127.0.0.1:$PORT_AUTH/auth/v1" \
EUROSTRUCT_SUPABASE_LOCAL_CLE_PEM="$DOSSIER/emetteur-repetition.pem" \
EUROSTRUCT_E2E_COMPTES="a@repetition.invalid:FICTIF-A-$JETON:$ACTEUR_A:7200:oui,b@repetition.invalid:FICTIF-B-$JETON:$ACTEUR_B:7200:oui" \
  node "$RACINE/web/e2e/supabase_local.mjs" >"$DOSSIER/emetteur.log" 2>&1 &
PID_AUTH=$!
for _ in $(seq 1 40); do
  curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT_AUTH/jwks" 2>/dev/null && break
  sleep 0.5
done
if curl -fsS --max-time 2 -o /dev/null "http://$HOTE:$PORT_AUTH/jwks" 2>/dev/null; then
  execute 2 "JWKS servi sur 127.0.0.1 et sur $HOTE (vu des conteneurs)"
else
  echoue 2 "l'emetteur n'a pas demarre, ou n'ecoute pas sur $HOTE"; exit 1
fi
jeton_pour() {   # jeton_pour <courriel> <mdp>
  printf '{"email":"%s","password":"%s"}' "$1" "$2" > "$TMP/cx.json"
  curl -fsS -X POST "http://127.0.0.1:$PORT_AUTH/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' -d @"$TMP/cx.json" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}
JETON_A="$(jeton_pour a@repetition.invalid "FICTIF-A-$JETON")"
JETON_B="$(jeton_pour b@repetition.invalid "FICTIF-B-$JETON")"
[[ -n "$JETON_A" && -n "$JETON_B" ]] || { echoue 2 "aucun jeton delivre"; exit 1; }

# ---------------------------------------------------------------------------
# 3. L'ENVIRONNEMENT DE STAGING — genere en 0600, comme l'exploitant le remplirait
# ---------------------------------------------------------------------------
umask 077
cat > "$ENVR" <<FIN
# REPETITION LOCALE — genere par deploy/staging_repetition.sh ($JETON). Efface a la sortie.
ESC_PLAN_URL=postgresql://$CTL:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE?sslmode=disable
ESC_MIGRATOR_URL=postgresql://$MIG:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE?sslmode=disable
EUROSTRUCT_DATABASE_URL=postgresql://$SVC:$MDP@$HOTE:${PGPORT:-5432}/$BASE?sslmode=disable
EUROSTRUCT_SUPABASE_JWKS_URL=http://$HOTE:$PORT_AUTH/jwks
EUROSTRUCT_SUPABASE_ISSUER=http://127.0.0.1:$PORT_AUTH/auth/v1
EUROSTRUCT_SUPABASE_AUDIENCE=authenticated
EUROSTRUCT_JWT_ALGORITHMS=RS256
EUROSTRUCT_PUBLIC_API_URL=$URL_API
EUROSTRUCT_PUBLIC_WEB_URL=$URL_WEB
EUROSTRUCT_PUBLIC_SUPABASE_URL=$URL_AUTH
EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY=repetition-sans-cle-anonyme
EUROSTRUCT_CORS_ORIGINS=$URL_WEB
EUROSTRUCT_MANDATAIRE=oui
EUROSTRUCT_CADDY_TLS="tls internal"
EUROSTRUCT_MANDATAIRE_ECOUTE=127.0.0.1:
API_PORT=$PORT_API
WEB_PORT=$PORT_WEB
EUROSTRUCT_STORAGE_BACKEND=local
EUROSTRUCT_S3_ENDPOINT=
EUROSTRUCT_S3_REGION=
EUROSTRUCT_S3_BUCKET=
EUROSTRUCT_S3_PREFIX=livrables
EUROSTRUCT_S3_PATH_STYLE=oui
EUROSTRUCT_S3_ACCESS_KEY_ID=
EUROSTRUCT_S3_SECRET_ACCESS_KEY=
EUROSTRUCT_S3_VERIFY_TLS=oui
EUROSTRUCT_S3_CA_BUNDLE=
EUROSTRUCT_S3_SSE=
EUROSTRUCT_S3_SSE_KMS_KEY_ID=
EUROSTRUCT_BOOTSTRAP_ACTOR=$RACINE_ID
EUROSTRUCT_BOOTSTRAP_MANDATE=$MANDAT
EUROSTRUCT_BOOTSTRAP_NAME="Racine de repetition (fictive)"
EUROSTRUCT_BOOTSTRAP_REASON="repetition locale de la mise a disposition"
EUROSTRUCT_STAGING_JETON_A=$JETON_A
EUROSTRUCT_STAGING_JETON_B=$JETON_B
EUROSTRUCT_RECETTE_JETONS_D_ESSAI=oui
EUROSTRUCT_STAGING_BACKUP_URL=postgresql://$SAV:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE?sslmode=disable
EUROSTRUCT_STAGING_RESTORE_URL=postgresql://$SAV:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE_R?sslmode=disable
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
EUROSTRUCT_PLAN_DB_USER=
EUROSTRUCT_PLAN_DB_PASSWORD=
EUROSTRUCT_MIGRATOR_DB_USER=
EUROSTRUCT_MIGRATOR_DB_PASSWORD=
EUROSTRUCT_APP_DB_USER=
EUROSTRUCT_APP_DB_PASSWORD=
EUROSTRUCT_LOCAL_AUTH_STUB=non
EUROSTRUCT_STAGING_SANS_TLS=oui
EUROSTRUCT_STAGING_RESOLVE=$RESOLUTION
EUROSTRUCT_STAGING_CA_BUNDLE=$CA
EUROSTRUCT_CADDYFILE=$CADDYFILE
FIN

# LE FICHIER DU MANDATAIRE: celui du DEPOT, mot pour mot, plus le site de
# l'emetteur. On ne le recopie pas a la main — on le concatene, pour qu'une
# modification de deploy/Caddyfile soit dans la repetition sans rien reporter.
{
  cat "$RACINE/deploy/Caddyfile"
  printf '\n# AJOUT DE LA REPETITION SEULEMENT: l emetteur de jetons, hors composition.\n'
  printf '%s {\n\ttls internal\n\treverse_proxy %s:%s\n}\n' "$URL_AUTH" "$HOTE" "$PORT_AUTH"
} > "$CADDYFILE"
chmod 600 "$CADDYFILE"
umask 022

# ---------------------------------------------------------------------------
# 3-7. LA PROCEDURE, DANS L'ORDRE DE docs/STAGING.md
# ---------------------------------------------------------------------------
pas() {   # pas <index> <libelle> <commande...> — journalise, note, ne cite aucun secret
  local i="$1" libelle="$2"; shift 2
  echo "==> $i. $libelle"
  if "$@" >"$TMP/pas-$i.log" 2>&1; then
    execute "$i" "code 0"
    return 0
  else
    local rc=$?
    echoue "$i" "code $rc — $(grep -m1 -E 'MANQUE|ECHEC|REFUS|ERROR|NON EXECUTE' "$TMP/pas-$i.log" | sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g' | cut -c1-140)"
    return $rc
  fi
}
# PAS DE TUBE ICI: un `{ ... } | tee` ferait tourner ces pas dans un
# sous-shell, et le tableau des resultats resterait vide dans le bilan —
# mesure a la premiere execution: sept pas joues, sept « non tente ».
pas 3 "staging.sh prerequis" staging prerequis
grep -q "MANQUE" "$TMP/pas-3.log" && echoue 3 "une exigence est signalee manquante sur un provisionnement conforme"
pas 4 "staging.sh privileges (lecture seule)" staging privileges
grep -q "MANQUE" "$TMP/pas-4.log" && echoue 4 "verifier_privileges.sh signale un manque sur un provisionnement conforme"
if pas 5 "staging.sh migrer (sceau, migrations, referentiel, admission, racine)" staging migrer; then
  n="$(psql -X -q -tA -d "$BASE" -c "select count(*) from normative_authorisation_grants where origin='bootstrap'" 2>/dev/null | tr -d ' ')"
  [[ "$n" == "1" ]] || echoue 5 "racine attendue amorcee (1), constatee: ${n:-illisible}"
  # LES HABILITATIONS D'ESSAI DE A ET B, deleguees depuis la racine. C'est un
  # geste de PROVISIONNEMENT du harnais — le meme que `demo.sh amorcer` — et
  # non un pas de la procedure: sur un staging reel, ce sont des personnes
  # habilitees par le circuit qui tiennent ces comptes. Sans lui, l'etape 3
  # de la recette (quatre yeux) refuse la proposition de A, a juste titre.
  echo "    habilitations d'essai de A et B (provisionnement du harnais, depuis la racine)"
  edition="$(python3 -c '
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
eds = {jeu.find(k).edition for k in jeu.keys()}
print(sorted(eds)[0] if len(eds) == 1 else "")' 2>/dev/null)"
  racine_grant="$(psql -X -q -tA -d "$BASE" -c "select id from normative_authorisation_grants where origin = 'bootstrap' limit 1" 2>/dev/null | tr -d ' ')"
  if [[ -z "$edition" || ! "$racine_grant" =~ ^[0-9a-f-]{36}$ ]]; then
    echoue 5 "habilitations d'essai: edition ou racine illisible"
  else
    for duo in "$ACTEUR_A:A" "$ACTEUR_B:B"; do
      PGPASSWORD="$MDP" psql -X -q -h 127.0.0.1 -p "${PGPORT:-5432}" -U "$SVC" -d "$BASE" \
        -v racine="$RACINE_ID" -v qui="${duo%%:*}" -v nom="Ingenieur d'essai ${duo##*:} (repetition)" \
        -v edition="$edition" -v parent="$racine_grant" >"$TMP/grant-${duo##*:}.log" 2>&1 <<'SQL'
select set_config('eurostruct.actor_id', :'racine', false);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   edition, reason, parent_grant_id)
select :'qui'::uuid, :'nom', 'can_validate_normative_reference', 'BE',
       'EN 1992', '1-1', :'edition',
       'habilitation d essai de la repetition locale', :'parent'::uuid
where not exists (
  select 1 from normative_authorisation_grants
   where grantee_id = :'qui'::uuid and permission = 'can_validate_normative_reference'
     and country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1'
     and edition = :'edition');
SQL
      grep -qiE "ERROR|FATAL" "$TMP/grant-${duo##*:}.log" \
        && echoue 5 "habilitation d'essai de ${duo##*:}: $(grep -m1 -iE 'ERROR|FATAL' "$TMP/grant-${duo##*:}.log" | cut -c1-120)"
    done
  fi
fi
pas 6 "staging.sh up (images api et web, mandataire TLS; base et JWKS exterieurs)" staging up
[[ -s "$CA" ]] || echoue 6 "l'autorite locale du mandataire n'a pas ete copiee ($(basename "$CA"))"
pas 7 "staging.sh status (controles des URL publiques, certificat verifie)" staging status
grep -q "ready: True" "$TMP/pas-7.log" || echoue 7 "/ready n'est pas vert sur la boucle locale"
grep -qE "^  ok   $URL_API/ready -> 200, ready: True" "$TMP/pas-7.log" || echoue 7 "l'URL publique de l'API ne repond pas 200 ready par le mandataire"
grep -qE "^  ok   $URL_WEB/ -> 200" "$TMP/pas-7.log" || echoue 7 "l'URL publique de l'interface ne repond pas 200 par le mandataire"
grep -qE "^  ok   CORS: " "$TMP/pas-7.log" || echoue 7 "l'API n'admet pas l'origine de l'interface (CORS)"
[[ "$(grep -cE "^  ok   certificat verifie sur " "$TMP/pas-7.log")" == "2" ]] || echoue 7 "le certificat n'est pas verifie sur les deux noms"

# ---------------------------------------------------------------------------
# 8. LE PARCOURS PAR LES URL PUBLIQUES — ce qu'un client fait, par le mandataire
# ---------------------------------------------------------------------------
echo "==> 8. parcours par les URL publiques ($URL_API): bureau, projet, etude, note PDF"
printf 'Authorization: Bearer %s\n' "$JETON_A" > "$TMP/entete"; chmod 600 "$TMP/entete"
# LE CERTIFICAT EST VERIFIE contre l'autorite locale copiee par « up »; les
# noms sont resolus vers la boucle locale. Jamais -k.
curl_pub() {
  curl --cacert "$CA" --resolve "$NOM_API:443:127.0.0.1" --resolve "$NOM_WEB:443:127.0.0.1" "$@"
}
api() {   # api <methode> <chemin> [fichier-corps] -> code; corps dans $TMP/reponse
  local -a opts=(-sS -o "$TMP/reponse" -w '%{http_code}' -X "$1" -H @"$TMP/entete"
                 -H 'Content-Type: application/json' --max-time 120)
  [[ -n "${3:-}" ]] && opts+=(-d @"$3")
  curl_pub "${opts[@]}" "$URL_API$2" 2>/dev/null
}
json() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))" "$TMP/reponse" "$1" 2>/dev/null; }
if [[ "${ETATS[6]}" != "EXECUTE" || ! -s "$CA" ]]; then
  non_exec 8 "la composition n'est pas montee, ou l'autorite du mandataire manque."
else
  ok8=1
  # /health ne doit PAS dire « demonstration »: c'est la difference avec demo.sh.
  env_api="$(curl_pub -fsS "$URL_API/health" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("environnement"))' 2>/dev/null)"
  [[ "$env_api" == "None" || -z "$env_api" ]] || { echoue 8 "/health annonce l'environnement « $env_api » alors que le staging n'est pas une demonstration"; ok8=0; }
  # L'interface ne porte pas le bandeau de demonstration.
  curl_pub -fsS "$URL_WEB/" 2>/dev/null | grep -qi "environnement-demonstration" \
    && { echoue 8 "l'interface porte le bandeau de demonstration"; ok8=0; }
  printf '{"name":"FICTIF Bureau de repetition %s","country":"BE","display_name":"Ingenieur A (repetition)","professional_id":null}' "$JETON" > "$TMP/org.json"
  code="$(api POST /v1/organizations "$TMP/org.json")"
  [[ "$code" == "201" ]] || { echoue 8 "fondation du bureau: $code $(cut -c1-120 "$TMP/reponse")"; ok8=0; }
  org="$(json 'd["organization_id"]')"
  printf '{"name":"FICTIF Repetition staging","reference":"REP-%s","country":"BE","region":null,"ndp_as_of":"%s","organization_id":"%s"}' "$JETON" "$(date -u +%Y-%m-%d)" "$org" > "$TMP/projet.json"
  code="$(api POST /v1/projects "$TMP/projet.json")"
  [[ "$code" == "201" ]] || { echoue 8 "creation du projet: $code $(cut -c1-120 "$TMP/reponse")"; ok8=0; }
  projet="$(json 'd["project_id"]')"
  cat > "$TMP/etude.json" <<'JSON'
{"element":"P1","strict_ndp":false,
 "geometry":{"b":{"value":300,"unit":"mm"},"h":{"value":600,"unit":"mm"},"d":{"value":550,"unit":"mm"},"l_eff":{"value":6000,"unit":"mm"}},
 "materials":{"concrete_grade":"C30/37","steel_grade":"B500B"},
 "M_Ed":{"value":250,"unit":"kN*m"},"V_Ed":{"value":300,"unit":"kN"},"M_char":{"value":180,"unit":"kN*m"},"M_qp":{"value":120,"unit":"kN*m"},
 "phi_creep":2.0,"exposure_class":"XC3","structural_system":"simply_supported","supports_brittle_partitions":false,
 "bars":{"count":4,"diameter":{"value":20,"unit":"mm"}},
 "links":{"legs":2,"diameter":{"value":10,"unit":"mm"},"spacing":{"value":150,"unit":"mm"}},
 "cot_theta":1.5,"cover":{"value":40,"unit":"mm"},"anchorage_available":{"value":800,"unit":"mm"}}
JSON
  code="$(api POST "/v1/projects/$projet/beam-verifications" "$TMP/etude.json")"
  [[ "$code" == "201" ]] || { echoue 8 "etude exploratoire: $code $(cut -c1-120 "$TMP/reponse")"; ok8=0; }
  calcul="$(json 'd["calculation_id"]')"; statut="$(json 'd["status"]')"
  [[ "$statut" == "passed" ]] || { echoue 8 "l'etude ne conclut pas: $statut"; ok8=0; }
  printf '{"calculation_id":"%s","format":"pdf"}' "$calcul" > "$TMP/liv.json"
  code="$(api POST "/v1/projects/$projet/deliverables" "$TMP/liv.json")"
  [[ "$code" == "201" ]] || { echoue 8 "note PDF: $code $(cut -c1-120 "$TMP/reponse")"; ok8=0; }
  liv="$(json 'd["deliverable_id"]')"; attendu="$(json 'd["sha256"]')"
  curl_pub -fsS -H @"$TMP/entete" -o "$TMP/note.pdf" "$URL_API/v1/projects/$projet/deliverables/$liv/download" 2>/dev/null
  recu="$(sha256sum "$TMP/note.pdf" 2>/dev/null | cut -d' ' -f1)"
  [[ -n "$attendu" && "$recu" == "$attendu" ]] || { echoue 8 "la note telechargee (${recu:0:12}) ne porte pas l'empreinte enregistree (${attendu:0:12})"; ok8=0; }
  head -c 5 "$TMP/note.pdf" 2>/dev/null | grep -q "%PDF-" || { echoue 8 "le telechargement n'est pas un PDF"; ok8=0; }
  # LE VOLUME PERSISTANT: l'objet est sur le volume nomme de la composition.
  n_obj="$(COMPOSE_PROFILES=mandataire docker compose -p "$PROJET_COMPOSE" -f "$RACINE/compose.yaml" -f "$RACINE/compose.staging.yaml" --env-file "$ENVR" \
            exec -T api sh -c 'find /var/lib/eurostruct/livrables -type f | wc -l' 2>/dev/null | tr -d ' \r')"
  [[ "${n_obj:-0}" -ge 1 ]] || { echoue 8 "aucun objet sur le volume livrables ($n_obj)"; ok8=0; }
  (( ok8 )) && execute 8 "bureau, projet, etude $calcul (passed), note PDF ${attendu:0:12} telechargee a l'identique par $NOM_API, $n_obj objet(s) sur le volume; /health sans « demonstration »"
fi


# ---------------------------------------------------------------------------
# LE PARCOURS NAVIGATEUR, PAR LES URL PUBLIQUES
# ---------------------------------------------------------------------------
# CE QUE `curl` NE PEUT PAS DIRE. Le pas 8 etablit que l'API et l'interface
# repondent par le mandataire, avec un certificat verifie. Il ne dit rien de ce
# qu'un NAVIGATEUR en fait: s'il execute la page sans erreur, s'il charge
# toutes ses ressources, s'il refuse une ressource en clair depuis une page
# chiffree, si la session tient d'un ecran a l'autre. C'est un parcours
# Chromium qui le dit, et c'est celui du produit — `web/e2e/parcours_demo.mjs`,
# pointe sur les noms publics.
#
# L'AUTORITE LOCALE EST APPROUVEE, JAMAIS IGNOREE. Chromium lit le magasin NSS
# de $HOME; on lui en donne un a nous, ou l'autorite du mandataire est
# INSTALLEE comme autorite de confiance. Le certificat est ensuite verifie
# comme n'importe quel autre — `ignoreHTTPSErrors` n'apparait nulle part, et
# un certificat qui ne se verifierait pas ferait echouer le parcours.
approuver_autorite() {
  command -v certutil >/dev/null 2>&1 || return 1
  [[ -s "$CA" ]] || return 1
  rm -rf "$NSS"; mkdir -p "$NSS/.pki/nssdb"
  certutil -d "sql:$NSS/.pki/nssdb" -N --empty-password >/dev/null 2>&1 || return 1
  certutil -d "sql:$NSS/.pki/nssdb" -A -t "C,," -n "eurostruct-repetition-$JETON" \
    -i "$CA" >/dev/null 2>&1 || return 1
  certutil -d "sql:$NSS/.pki/nssdb" -L 2>/dev/null | grep -q "eurostruct-repetition-$JETON"
}

parcours_navigateur() {   # parcours_navigateur <index> <mode> <libelle>
  # `local a=$1 b=$a` ne fait PAS ce qu'on croit: les locales sont declarees
  # avant que les affectations de la MEME ligne ne soient lues, et `$a` y vaut
  # celui de la portee englobante — inexistant ici, donc « unbound variable »
  # sous `set -u`. Mesure a la premiere execution.
  local index="$1" mode="$2" libelle="$3"
  # LE JOURNAL DU NAVIGATEUR SURVIT AU NETTOYAGE. Il porte le detail que le
  # bilan ne peut pas tenir sur une ligne: les echanges, les refus, les
  # ressources bloquees, les erreurs JavaScript, les empreintes des
  # livrables telecharges.
  mkdir -p "$SORTIE_NAV"
  local log="$SORTIE_NAV/pas-${index}-nav.log"
  if ! node "$RACINE/web/e2e/verifier_navigateur.mjs" >/dev/null 2>&1; then
    non_exec "$index" "Playwright ou Chromium absent sur cet hote."; return
  fi
  if ! approuver_autorite; then
    non_exec "$index" "l'autorite locale du mandataire n'a pas pu etre approuvee (certutil absent, ou autorite non copiee). Le parcours n'est PAS lance avec un certificat ignore."
    return
  fi
  umask 077
  cat > "$ENVNAV" <<FINNAV
EUROSTRUCT_DEMO_COMPTE_A=a@repetition.invalid
EUROSTRUCT_DEMO_MDP_A=FICTIF-A-$JETON
FINNAV
  umask 022
  if HOME="$NSS" \
     EUROSTRUCT_DEMO_ENV="$ENVNAV" \
     EUROSTRUCT_DEMO_WEB="$URL_WEB" \
     EUROSTRUCT_DEMO_API="$URL_API" \
     EUROSTRUCT_DEMO_BANDEAU=non \
     EUROSTRUCT_DEMO_RESOLVE="$RESOLUTION" \
     EUROSTRUCT_DEMO_PROJET="FICTIF Repetition staging" \
     EUROSTRUCT_DEMO_SORTIE="$SORTIE_NAV" \
       node "$RACINE/web/e2e/parcours_demo.mjs" "$mode" >"$log" 2>&1; then
    execute "$index" "$libelle — $(grep -m1 'echange(s) interface/API' "$log" | sed 's/^ *· *//')"
  else
    echoue "$index" "$(grep -m1 -E 'ECHEC|Error|erreur' "$log" | cut -c1-200)"
  fi
}

echo "==> 8b. parcours navigateur (Chromium) par $NOM_WEB, certificat verifie"
if [[ "${ETATS[8]}" != "EXECUTE" ]]; then
  non_exec 12 "le parcours du pas 8 n'a pas abouti: aucun projet a ouvrir."
else
  parcours_navigateur 12 creer "etude creee a l'ecran, note PDF et plan DXF telecharges par le navigateur"
fi

# ---------------------------------------------------------------------------
# 9. LE REDEMARRAGE — down, up, et l'etude est encore la, sa note aussi
# ---------------------------------------------------------------------------
# C'est la phrase « stockage persistant et redemarrage » mesuree: les
# conteneurs s'arretent, repartent sur les memes volumes, et l'etude se relit
# par l'URL publique avec la MEME empreinte; la note se retelecharge avec les
# MEMES octets; le mandataire ressert le meme nom avec un certificat verifie.
echo "==> 9. redemarrage: staging.sh down, staging.sh up, relecture par les URL publiques"
if [[ "${ETATS[8]}" != "EXECUTE" ]]; then
  non_exec 9 "le parcours du pas 8 n'a pas abouti: rien a relire."
else
  ok9=1
  empreinte_avant="$(curl_pub -fsS -H @"$TMP/entete" "$URL_API/v1/projects/$projet/beam-verifications/$calcul" 2>/dev/null \
                     | python3 -c 'import json,sys; print(json.load(sys.stdin)["calculation_fingerprint"])' 2>/dev/null)"
  [[ -n "$empreinte_avant" ]] || { echoue 9 "l'etude ne se relit pas avant le redemarrage"; ok9=0; }
  if (( ok9 )); then
    staging down >"$TMP/pas-9-down.log" 2>&1 || { echoue 9 "down: code $?"; ok9=0; }
  fi
  if (( ok9 )); then
    restants="$(COMPOSE_PROFILES=mandataire docker compose -p "$PROJET_COMPOSE" -f "$RACINE/compose.yaml" -f "$RACINE/compose.staging.yaml" --env-file "$ENVR" ps --status running -q 2>/dev/null | wc -l | tr -d ' ')"
    [[ "$restants" == "0" ]] || { echoue 9 "$restants conteneur(s) encore en marche apres down"; ok9=0; }
  fi
  if (( ok9 )); then
    staging up >"$TMP/pas-9-up.log" 2>&1 || { echoue 9 "up apres down: code $? — $(grep -m1 -E 'ECHEC|REFUS' "$TMP/pas-9-up.log" | cut -c1-120)"; ok9=0; }
  fi
  if (( ok9 )); then
    empreinte_apres="$(curl_pub -fsS -H @"$TMP/entete" "$URL_API/v1/projects/$projet/beam-verifications/$calcul" 2>/dev/null \
                       | python3 -c 'import json,sys; print(json.load(sys.stdin)["calculation_fingerprint"])' 2>/dev/null)"
    [[ -n "$empreinte_apres" && "$empreinte_apres" == "$empreinte_avant" ]] \
      || { echoue 9 "l'etude relue apres redemarrage n'a pas son empreinte (${empreinte_apres:0:12} / ${empreinte_avant:0:12})"; ok9=0; }
    curl_pub -fsS -H @"$TMP/entete" -o "$TMP/note-apres.pdf" "$URL_API/v1/projects/$projet/deliverables/$liv/download" 2>/dev/null
    recu_apres="$(sha256sum "$TMP/note-apres.pdf" 2>/dev/null | cut -d' ' -f1)"
    [[ "$recu_apres" == "$attendu" ]] || { echoue 9 "la note retelechargee apres redemarrage (${recu_apres:0:12}) n'a plus ses octets (${attendu:0:12})"; ok9=0; }
    code_web="$(curl_pub -sS -o /dev/null --max-time 15 -w '%{http_code}' "$URL_WEB/" 2>/dev/null || echo 000)"
    [[ "$code_web" == "200" ]] || { echoue 9 "l'interface ne repond plus 200 par le mandataire apres redemarrage ($code_web)"; ok9=0; }
  fi
  (( ok9 )) && execute 9 "down puis up: etude $calcul relue avec son empreinte, note PDF aux memes octets, interface servie par $NOM_WEB"
fi

echo "==> 9b. parcours navigateur apres redemarrage: session, relecture, memes octets"
if [[ "${ETATS[12]}" != "EXECUTE" || "${ETATS[9]}" != "EXECUTE" ]]; then
  non_exec 13 "le parcours navigateur initial ou le redemarrage n'a pas abouti."
else
  parcours_navigateur 13 retrouver "etude rouverte sans recalcul, livrables retelecharges aux memes octets"
fi

# ---------------------------------------------------------------------------
# 10. LA RECETTE DE BOUT EN BOUT — les sept etapes, sur cette base
# ---------------------------------------------------------------------------
echo "==> 10. recette de bout en bout (db/test/recette_supabase_staging.sh executer)"
if staging recette executer >"$TMP/pas-10.log" 2>&1; then
  execute 10 "sept etapes EXECUTEES (code 0)"
else
  rc=$?
  echoue 10 "code $rc: $(grep -E '^ *(ECHOUEE|NON EXECUTEE)' "$TMP/pas-10.log" | head -3 | sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g' | cut -c1-160 | tr '\n' ' ')"
fi
sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g' "$TMP/pas-10.log" | grep -E "^ *[0-9] |VERDICT|EXECUTEE|ECHOUEE|NON EXECUTEE" | head -20 | tee -a "$JOURNAL"

echo "==> 11. staging.sh down"
if staging down >"$TMP/pas-11.log" 2>&1; then execute 11 "conteneurs arretes, volumes gardes"
else echoue 11 "code $?"; fi

# ---------------------------------------------------------------------------
# LE BILAN
# ---------------------------------------------------------------------------
{
  echo ""
  echo "=================================================================="
  echo " REPETITION LOCALE DE LA MISE A DISPOSITION SUR STAGING — bilan"
  for i in "${!NOMS[@]}"; do
    printf '  %-38s %-12s %s\n' "${NOMS[$i]}" "${ETATS[$i]}" "$(cut -c1-110 <<<"${DETAILS[$i]}")"
  done
  echo ""
  if (( KO )); then echo " VERDICT: ECHEC — au moins un pas a echoue (journal: $JOURNAL)."
  else echo " VERDICT: TENU — la composition de staging (mandataire TLS compris), la commande de migration, le redemarrage et la recette tiennent ensemble contre une base et un emetteur exterieurs. Rien n'est etabli sur Supabase, ni sur un certificat public."
  fi
  echo "=================================================================="
} | tee -a "$JOURNAL"
# LES JOURNAUX DES PAS, masques, pour relecture.
for f in "$TMP"/pas-*.log; do
  [[ -f "$f" ]] && { echo "--- $(basename "$f") ---"; sed -E 's#postgres(ql)?://[^ ]*#<dsn>#g; s#Bearer [A-Za-z0-9._-]+#Bearer <jeton>#g' "$f"; } >>"$JOURNAL"
done
exit $(( KO ))
