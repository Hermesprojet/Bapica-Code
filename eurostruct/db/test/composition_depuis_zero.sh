#!/usr/bin/env bash
#
# EUROSTRUCT — LA COMPOSITION DOIT DEMARRER DEPUIS UN VOLUME VIDE
#
#   db/test/composition_depuis_zero.sh
#
# CE QUE CETTE PREUVE ETABLIT
# ----------------------------
# `docker compose config` dit que le fichier est bien forme. Il ne dit RIEN de
# ce qui se passe au demarrage. Cette preuve part d'un volume PostgreSQL vide
# et exige que la pile serve reellement:
#
#   1. les migrations sont appliquees;
#   2. les roles applicatifs existent;
#   3. l'API est connectee par un login DEDIE, non-superutilisateur;
#   4. /health repond;
#   5. /ready est vert avec l'emetteur local deterministe;
#   6. le parcours d'autorite s'execute reellement.
#
# AUJOURD'HUI ELLE DOIT ECHOUER: `compose.yaml` demarre une image PostgreSQL
# vierge, sans migration, sans role de service et sans racine amorcee. L'API
# se connecte avec `POSTGRES_USER`, qui est le superutilisateur de l'image.
#
# AUCUN SECRET N'EST ECRIT ICI. Le fichier d'environnement est genere dans un
# repertoire temporaire, avec des valeurs FICTIVES, et detruit a la sortie.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$(dirname "$HERE")")/eurostruct"
[[ -f "$RACINE/compose.yaml" ]] || RACINE="$(dirname "$(dirname "$HERE")")"

PROJET="esc-preuve-b"
TMP="$(mktemp -d)"
ENVF="$TMP/preuve.env"

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

nettoyer() {
  # `-v` DETRUIT LE VOLUME: la preuve suivante doit repartir de zero, sinon
  # elle ne prouve plus « depuis un volume vide » mais « depuis ce qui restait ».
  docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" \
    down -v --remove-orphans >/dev/null 2>&1
  rm -rf "$TMP"
}
trap nettoyer EXIT

command -v docker >/dev/null 2>&1 || {
  echo "NON EXECUTE: docker absent." >&2; exit 4; }
docker info >/dev/null 2>&1 || {
  echo "NON EXECUTE: le demon docker ne repond pas." >&2; exit 4; }

# ---------------------------------------------------------------------------
# L'EMETTEUR LOCAL, hors composition: le navigateur et l'API doivent le
# joindre, et il n'a rien a faire dans une image de production.
# ---------------------------------------------------------------------------
PORT_AUTH="${EUROSTRUCT_PREUVE_PORT_AUTH:-54331}"
PORT_API="${EUROSTRUCT_PREUVE_PORT_API:-8021}"
PORT_WEB="${EUROSTRUCT_PREUVE_PORT_WEB:-3021}"
ACTEUR_A="22222222-7777-7777-7777-7777777700a1"
ACTEUR_B="33333333-7777-7777-7777-7777777700b1"
RACINE_ID="11111111-7777-7777-7777-777777770001"

for duo in "$PORT_AUTH:emetteur" "$PORT_API:API" "$PORT_WEB:interface"; do
  P="${duo%%:*}"
  if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$P" 2>/dev/null; then
    echo "      ECHEC: le port $P (${duo##*:}) repond deja." >&2
    exit 2
  fi
done

command -v node >/dev/null 2>&1 || {
  echo "NON EXECUTE: node absent." >&2; exit 4; }

# L'HOTE VU DEPUIS UN CONTENEUR. L'API tourne dans la composition et doit
# joindre l'emetteur qui, lui, tourne sur l'hote.
#
# `host.docker.internal` N'EST PAS UNIVERSEL, et le supposer a coute une
# execution: sur un moteur Linux sans `extra_hosts: host-gateway`, ce nom ne
# resout pas, le JWKS est injoignable, `/ready` reste rouge et la proposition
# rend 401. On lit donc l'adresse de la passerelle du pont Docker — ce que le
# conteneur atteint reellement — et on se rabat sur le nom seulement si le
# moteur ne la donne pas.
HOTE_DEPUIS_CONTENEUR="$(docker network inspect bridge \
  -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null)"
if [[ ! "$HOTE_DEPUIS_CONTENEUR" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
  HOTE_DEPUIS_CONTENEUR="host.docker.internal"
fi

# L'EMETTEUR ECOUTE SUR LA PASSERELLE DU PONT, pas seulement sur la boucle
# locale: sinon aucun conteneur ne le joint. Une interface precise, jamais
# `0.0.0.0` — qui exposerait aussi les interfaces externes de la machine.
EUROSTRUCT_SUPABASE_LOCAL_BIND="$HOTE_DEPUIS_CONTENEUR" \
EUROSTRUCT_SUPABASE_LOCAL_PORT="$PORT_AUTH" \
EUROSTRUCT_SUPABASE_LOCAL_ISSUER="http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/auth/v1" \
EUROSTRUCT_E2E_COMPTES="a@fictif.invalid:FICTIF-A:$ACTEUR_A:3600:oui,b@fictif.invalid:FICTIF-B:$ACTEUR_B:3600:oui" \
  node "$RACINE/web/e2e/supabase_local.mjs" >"$TMP/auth.log" 2>&1 &
PID_AUTH=$!
trap 'kill "$PID_AUTH" 2>/dev/null; nettoyer' EXIT

for _ in $(seq 1 40); do
  curl -fsS --max-time 2 "http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/jwks" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS --max-time 2 "http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/jwks" >/dev/null 2>&1 || {
  echo "      ECHEC: l'emetteur local n'a pas demarre." >&2
  sed -n '1,15p' "$TMP/auth.log" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# LE FICHIER D'ENVIRONNEMENT — FICTIF, TEMPORAIRE, JAMAIS VERSIONNE
# ---------------------------------------------------------------------------
JETON="$(tr -dc 'a-f0-9' </dev/urandom | head -c 12)"
cat > "$ENVF" <<FIN
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
EUROSTRUCT_BOOTSTRAP_MANDATE=$RACINE_ID:FICTIF-EMPREINTE-PREUVE-B-$JETON
EUROSTRUCT_BOOTSTRAP_ACTOR=$RACINE_ID
EUROSTRUCT_BOOTSTRAP_NAME=FICTIF racine (preuve B)
EUROSTRUCT_BOOTSTRAP_REASON=FICTIF amorcage de la preuve B
EUROSTRUCT_SUPABASE_JWKS_URL=http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/jwks
EUROSTRUCT_SUPABASE_ISSUER=http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/auth/v1
EUROSTRUCT_SUPABASE_AUDIENCE=authenticated
EUROSTRUCT_JWT_ALGORITHMS=RS256
EUROSTRUCT_PUBLIC_API_URL=http://127.0.0.1:$PORT_API
EUROSTRUCT_PUBLIC_SUPABASE_URL=http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH
EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY=FICTIF-ANON-$JETON
EUROSTRUCT_CORS_ORIGINS=http://localhost:$PORT_WEB,http://127.0.0.1:$PORT_WEB
API_PORT=$PORT_API
WEB_PORT=$PORT_WEB
FIN

dc() { docker compose -p "$PROJET" --env-file "$ENVF" -f "$RACINE/compose.yaml" "$@"; }

echo "    la composition demarre-t-elle depuis un volume VIDE ?"

# Un volume residuel d'une execution precedente ferait passer la preuve pour
# de mauvaises raisons.
dc down -v --remove-orphans >/dev/null 2>&1

# `--build` PAR DEFAUT, SAUF QUAND LES IMAGES VIENNENT D'ETRE CONSTRUITES.
#
# Le job CI construit les deux images EXPLICITEMENT, comme une etape a part
# entiere dont l'echec doit se lire pour ce qu'il est. Les reconstruire ici
# rejouerait le meme travail et rendrait « la composition ne monte pas »
# indiscernable de « l'image ne se construit pas ». `EUROSTRUCT_PREUVE_SANS_BUILD`
# dit donc: les images sont deja la, monte-les.
CONSTRUIRE=(--build)
if [[ "${EUROSTRUCT_PREUVE_SANS_BUILD:-non}" == "oui" ]]; then
  CONSTRUIRE=()
  echo "    (images deja construites: --build saute)"
fi

if ! dc up "${CONSTRUIRE[@]}" --wait --wait-timeout 420 >"$TMP/up.log" 2>&1; then
  echoue "la composition n'est pas montee."
  tail -n 25 "$TMP/up.log" >&2
  # LE JOURNAL DE L'INITIALISATION, PARCE QUE C'EST LA QUE CA CASSE.
  #
  # `up --wait` rend « service init didn't complete successfully: exit 1 » et
  # rien d'autre: le diagnostic reel — quel role, quelle migration, quelle
  # postcondition — est dans le conteneur, que le piege de sortie detruit.
  # Sans cette capture, chaque echec obligeait a rejouer a la main.
  echo "" >&2
  echo "      --- journal du service init ---" >&2
  dc logs --no-color init 2>&1 | tail -n 40 >&2
  echo "" >&2
  dc ps >&2 2>/dev/null
  exit 1
fi

psql_admin() {   # psql dans le conteneur de base, en superutilisateur
  dc exec -T db psql -X -q -tA -U "$(grep '^POSTGRES_USER=' "$ENVF" | cut -d= -f2)" \
     -d "$(grep '^POSTGRES_DB=' "$ENVF" | cut -d= -f2)" -c "$1" 2>/dev/null | tr -d ' '
}

# --- 1. LES MIGRATIONS SONT APPLIQUEES -------------------------------------
ETAT="$(psql_admin "select normative_activation_state()")"
if [[ "$ETAT" != "ACTIVE" ]]; then
  echoue "la base n'est pas ACTIVE (etat: « ${ETAT:-aucun} »). Les migrations"
  echoue "  n'ont pas ete appliquees: l'image PostgreSQL demarre vierge."
fi

# --- 2. LES ROLES APPLICATIFS EXISTENT -------------------------------------
MANQUANTS="$(psql_admin "
  select coalesce(string_agg(r, ', '), '') from unnest(array[
    'eurostruct_normative_writer','eurostruct_authority_backend',
    'normative_backend','normative_governance']) r
   where not exists (select 1 from pg_roles where rolname = r)")"
[[ -z "$MANQUANTS" ]] || echoue "roles applicatifs absents: $MANQUANTS"

# --- 3. L'API SE CONNECTE PAR UN LOGIN DEDIE, NON-SUPERUTILISATEUR ---------
APP="$(grep '^EUROSTRUCT_APP_DB_USER=' "$ENVF" | cut -d= -f2)"
SUPER="$(grep '^POSTGRES_USER=' "$ENVF" | cut -d= -f2)"
EXISTE="$(psql_admin "select count(*) from pg_roles where rolname = '$APP'")"
if [[ "$EXISTE" != "1" ]]; then
  echoue "le login applicatif « $APP » n'existe pas: l'API se connecte donc"
  echoue "  avec « $SUPER », le superutilisateur de l'image."
else
  EST_SUPER="$(psql_admin "select rolsuper from pg_roles where rolname = '$APP'")"
  [[ "$EST_SUPER" == "f" ]] || echoue "le login applicatif est superutilisateur."
fi

DSN_UTILISEE="$(dc exec -T api sh -c 'printenv EUROSTRUCT_DATABASE_URL' 2>/dev/null)"
if grep -q "$SUPER" <<<"$DSN_UTILISEE"; then
  echoue "l'API utilise le superutilisateur dans sa chaine de connexion."
fi

# --- 4. ET 5. /health ET /ready --------------------------------------------
SANTE="$(curl -fsS --max-time 10 "http://127.0.0.1:$PORT_API/health" 2>&1)"
grep -q '"status":"ok"' <<<"$SANTE" || echoue "/health ne repond pas ok: $SANTE"

PRET="$(curl -sS --max-time 20 "http://127.0.0.1:$PORT_API/ready" 2>&1)"
if ! grep -q '"ready":true' <<<"$PRET"; then
  echoue "/ready n'est pas vert: $(cut -c1-400 <<<"$PRET")"
fi
grep -q 'SUPABASE_UNVERIFIED' <<<"$PRET" \
  || echoue "/ready ne porte plus SUPABASE_UNVERIFIED."

# --- 6. LE PARCOURS D'AUTORITE S'EXECUTE REELLEMENT -------------------------
jeton_de() {   # jeton_de <courriel> <mot de passe>
  curl -fsS --max-time 10 \
    -X POST "http://$HOTE_DEPUIS_CONTENEUR:$PORT_AUTH/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null
}
JA="$(jeton_de a@fictif.invalid FICTIF-A)"
JB="$(jeton_de b@fictif.invalid FICTIF-B)"
if [[ -z "$JA" || -z "$JB" ]]; then
  echoue "l'emetteur local n'a pas delivre les deux jetons."
else
  # LES DEUX HABILITATIONS, DEPUIS LA RACINE QUE L'INITIALISATION A AMORCEE.
  #
  # Elles ne sont PAS posees par l'initialisation: habiliter une personne est
  # une decision, et la racine amorcee est justement celle qui la prend. Ici
  # c'est le decor de la preuve qui l'exerce, sous l'identite de la racine.
  APP_DB="$(grep '^EUROSTRUCT_APP_DB_USER=' "$ENVF" | cut -d= -f2)"
  APP_MDP="$(grep '^EUROSTRUCT_APP_DB_PASSWORD=' "$ENVF" | cut -d= -f2)"
  BASE_DB="$(grep '^POSTGRES_DB=' "$ENVF" | cut -d= -f2)"
  # L'EDITION VIENT DU REGISTRE, jamais d'une constante: une portee sur une
  # edition qui n'existe pas ferait refuser la proposition avant d'atteindre
  # ce que cette preuve veut eprouver.
  EDITION_BE="$(cd "$RACINE" && python3 - <<'FINPY' 2>/dev/null
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
editions = {jeu.find(k).edition for k in jeu.keys()}
print(sorted(editions)[0] if len(editions) == 1 else "")
FINPY
)"
  GR="$(dc exec -T -e PGPASSWORD="$APP_MDP" db psql -X -q -tA -U "$APP_DB" \
          -d "$BASE_DB" -c "select id from normative_authorisation_grants
                             where origin = 'bootstrap' limit 1" 2>/dev/null \
        | tr -d ' \r')"
  if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
    echoue "aucune racine d'autorite amorcee: le parcours ne peut rien exercer."
  elif [[ -z "$EDITION_BE" ]]; then
    echoue "edition du registre belge illisible: la portee serait devinee."
  else
    for duo in "$ACTEUR_A:A" "$ACTEUR_B:B"; do
      # LES DEUX ACTEURS EXISTENT D'ABORD DANS `auth.users`, ET C'EST LE
      # SUPERUTILISATEUR QUI LES Y MET. En production, c'est Supabase qui
      # peuple cette table; le login applicatif n'y a AUCUN droit, et c'est
      # voulu — il ne doit pas pouvoir se fabriquer un utilisateur.
      psql_admin "insert into auth.users (id) values ('${duo%%:*}')
                    on conflict do nothing" >/dev/null
      dc exec -T -e PGPASSWORD="$APP_MDP" db psql -X -q -tA -U "$APP_DB" \
        -d "$BASE_DB" -c "
          set eurostruct.actor_id = '$RACINE_ID';
          insert into normative_authorisation_grants
            (grantee_id, grantee_name, permission, country_code,
             standard_family, part, edition, reason, parent_grant_id)
          values ('${duo%%:*}', 'FICTIF ${duo##*:}',
                  'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
                  \$\$$EDITION_BE\$\$, 'FICTIF autorite ${duo##*:} (preuve B)',
                  '$GR');" >"$TMP/grant.log" 2>&1
      if grep -qiE "ERROR|FATAL" "$TMP/grant.log"; then
        echoue "l'habilitation de ${duo##*:} n'a pas ete creee:"
        echoue "  $(grep -m1 -iE 'ERROR|FATAL' "$TMP/grant.log" | cut -c1-220)"
      fi
    done

    # LE PARCOURS COMPLET, PAR LES ROUTES PUBLIQUES DE LA COMPOSITION.
    #
    # La version precedente proposait une portee inventee sans dossier et
    # acceptait 201 OU 422: elle etablissait « la pile repond », pas « la pile
    # sert ». Ici chaque etape a un code attendu, et le dossier est celui que
    # le SERVEUR compose depuis son propre registre.
    CLE="$(curl -fsS --max-time 15 "http://127.0.0.1:$PORT_API/v1/ndp/BE/parameters" \
           2>/dev/null | python3 -c '
import json,sys
p = json.load(sys.stdin)["parameters"]
c = [x for x in p if not x["usable_in_strict_mode"] and x.get("source_doc_id")]
print(c[0]["key"] if c else "")' 2>/dev/null)"
    if [[ -z "$CLE" ]]; then
      echoue "le plan de charge ne rend aucun parametre a confirmer."
    else
      DOC="$(curl -fsS --max-time 15 "http://127.0.0.1:$PORT_API/v1/ndp/BE/parameters" \
             2>/dev/null | python3 -c "
import json,sys
for x in json.load(sys.stdin)['parameters']:
    if x['key'] == '$CLE':
        print(x['source_doc_id'], x.get('source_page') or 1)" 2>/dev/null)"
      DIGEST="${DOC%% *}"; FOLIO="${DOC##* }"
      BROUILLON="$(python3 -c "
import json
print(json.dumps({
  'country_code': 'BE', 'rule_id': '$CLE',
  'statement': 'FICTIF — releve pour la preuve B.',
  'implementation_note': 'FICTIF — implementation de test',
  'effect': 'FICTIF — fixe la valeur nationale',
  'citations': [{'document_digest': '$DIGEST',
                 'quote': 'FICTIF — citation relevee.',
                 'page_printed': int('$FOLIO')}]}))")"
      CODE="$(curl -sS -o "$TMP/dossier.json" -w '%{http_code}' --max-time 20 \
              -X POST "http://127.0.0.1:$PORT_API/v1/authority/review-packages" \
              -H "Authorization: Bearer $JA" -H 'Content-Type: application/json' \
              -d "$BROUILLON" 2>/dev/null)"
      if [[ "$CODE" != "200" ]]; then
        echoue "la composition du dossier rend $CODE (attendu 200)."
        echoue "  $(cut -c1-300 <"$TMP/dossier.json")"
      else
        PROPOSITION="$(python3 -c "
import json
d = json.load(open('$TMP/dossier.json'))
print(json.dumps({
  'subject_kind': 'ndp_parameter', 'subject_id': '$CLE', 'org_id': None,
  'country_code': 'BE', 'standard_family': 'EN 1992', 'part': '1-1',
  'edition': '''$EDITION_BE''',
  'permission': 'can_validate_normative_reference',
  'reason': 'FICTIF preuve B', 'review_package': d['package']}))")"
        CODE="$(curl -sS -o "$TMP/prop.json" -w '%{http_code}' --max-time 20 \
                -X POST "http://127.0.0.1:$PORT_API/v1/authority/decisions" \
                -H "Authorization: Bearer $JA" -H 'Content-Type: application/json' \
                -d "$PROPOSITION" 2>/dev/null)"
        if [[ "$CODE" != "201" ]]; then
          echoue "la proposition rend $CODE (attendu 201)."
          echoue "  $(cut -c1-300 <"$TMP/prop.json")"
        else
          DEC="$(python3 -c "import json;print(json.load(open('$TMP/prop.json'))['decision_id'])")"
          # B RELIT LE DOSSIER GELE, PUIS APPROUVE, PUIS CONSOMME.
          for etape in "GET:/v1/authority/decisions/$DEC:200:$JB" \
                       "POST:/v1/authority/decisions/$DEC/approval:204:$JA" \
                       "POST:/v1/authority/decisions/$DEC/approval:204:$JB" \
                       "POST:/v1/authority/decisions/$DEC/consumption:200:$JB"; do
            M="${etape%%:*}"; RESTE="${etape#*:}"
            CHEMIN="${RESTE%%:*}"; RESTE="${RESTE#*:}"
            ATTENDU="${RESTE%%:*}"; JETON="${RESTE#*:}"
            # L'AUTO-APPROBATION PAR A DOIT ETRE REFUSEE: on attend 422 la, et
            # 204 pour B. Le tableau porte 204 pour les deux; on corrige ici
            # plutot que d'ecrire deux boucles.
            [[ "$JETON" == "$JA" && "$CHEMIN" == *"/approval" ]] && ATTENDU=422
            OBTENU="$(curl -sS -o "$TMP/etape.json" -w '%{http_code}' --max-time 20 \
                      -X "$M" "http://127.0.0.1:$PORT_API$CHEMIN" \
                      -H "Authorization: Bearer $JETON" 2>/dev/null)"
            if [[ "$OBTENU" != "$ATTENDU" ]]; then
              echoue "$M $CHEMIN rend $OBTENU (attendu $ATTENDU)."
              echoue "  $(cut -c1-250 <"$TMP/etape.json")"
            fi
          done
        fi
      fi
    fi
  fi
fi

# --- 7. UN SECOND DEMARRAGE SUR LE MEME VOLUME ------------------------------
dc stop >/dev/null 2>&1
if ! dc up "${CONSTRUIRE[@]}" --wait --wait-timeout 300 >"$TMP/up2.log" 2>&1; then
  echoue "le SECOND demarrage sur le meme volume echoue: l'initialisation"
  echoue "  n'est pas idempotente."
  tail -n 20 "$TMP/up2.log" >&2
  echo "" >&2
  echo "      --- journal du service init (second demarrage) ---" >&2
  dc logs --no-color init 2>&1 | tail -n 40 >&2
fi

if [[ $KO -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " La composition sert depuis un volume vide, et"
  echo " redemarre sur le meme volume sans rejouer."
  echo "================================================="
fi
exit $KO
