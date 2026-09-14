#!/usr/bin/env bash
#
# EUROSTRUCT — LE LIVRABLE, DEPUIS UN VRAI NAVIGATEUR
#
#   db/test/parcours_livrable.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS ETABLIT, ET QUE `livrable_validation.sh` NE PEUT PAS
# ------------------------------------------------------------------------
# `livrable_validation.sh` prouve que les sept primitives et les huit routes
# tiennent sous identite verifiee, et que PostgreSQL cloisonne. Il construit
# ses en-tetes lui-meme: il ne dit RIEN de ce que l'ECRAN envoie, ni de ce
# qu'un ingenieur peut reellement faire avec sa souris.
#
# Ce harnais dresse donc la pile entiere et la pilote au clavier:
#
#   Chromium -> Next.js (build de production) -> uvicorn -> PostgreSQL
#                   |                                          |
#                   +-> emetteur GoTrue local                  +-> magasin
#                       (jetons RS256 fictifs)                     d'objets reel
#
# LES DOUZE FAITS
# ----------------
#   1. A se connecte;
#   2. il cree un projet BE / Wallonie / date de reference;
#   3. il enregistre un calcul STRICT qui aboutit;
#   4. il produit un brouillon de livrable depuis l'historique;
#   5. il le telecharge, et le hash des octets recus est celui enregistre;
#   6. apres RECHARGEMENT COMPLET, les memes donnees et les MEMES OCTETS;
#   7. il le soumet a la relecture — et son ecran n'offre AUCUN panneau
#      d'attestation, en disant pourquoi;
#   8. V, ingenieur validateur, atteste — son nom et son numero d'inscription
#      viennent de son adhesion, pas de l'ecran;
#   9. l'emission n'est possible qu'apres cette attestation;
#  10. un livrable emis ne se modifie plus;
#  11. une revision est creee, avec l'indice suivant;
#  12. B, de l'autre organisation, n'obtient ni lecture ni telechargement.
#
# ET LA SECONDE VERTICALE, SUR LE MEME DECOR
# --------------------------------------------
# `parcours_verification.mjs` eprouve la verification COMPLETE — cinq
# chapitres, sept etapes de saisie, note, plan et apercu. Il partage ce decor
# parce que le redresser a l'identique ferait deux decors a maintenir, dont un
# qu'on ne regarde pas. Son fait decisif est ailleurs que dans les fichiers
# produits: le corps de la requete de plan ne porte QUE l'identifiant du calcul
# et le format — aucun ferraillage ne part du navigateur, parce que la coupe
# est gelee avec l'etude.
#
# LE DECOR CONFIRME LES PARAMETRES AVANT DE CALCULER, ET C'EST UN DECOR.
# Une attestation ne peut porter que sur un calcul STRICT abouti, et le mode
# strict ne s'ouvre que par le quatre-yeux. Le harnais fait donc passer les
# confirmations par les ROUTES DU PRODUIT, avec les jetons reels de A et de V —
# exactement comme un bureau d'etudes le ferait. Ce n'est pas ce que ce
# parcours prouve; c'est ce qui le rend possible.
#
# LES COMPTES SONT EXPLICITEMENT FICTIFS ET VIVENT DANS UNE BASE JETABLE.
# Aucune attestation produite ici n'est une validation reelle. Le registre
# national reste a 0/29 et `SUPABASE_UNVERIFIED` reste vrai.
#
# ON OBSERVE CE QUI PART ET CE QUI REVIENT, pas l'etat de React. L'ecran peut
# afficher ce qu'il veut: ce qui compte est l'octet sur le reseau, le fichier
# sur le disque, et la ligne en base.
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

PREFIXE="${1:?usage: parcours_livrable.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "parcours_livrable.sh" || exit 2
harnais_verrou_prendre  "parcours_livrable.sh" || exit $?
exiger_cluster_jetable  "parcours_livrable.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)
exiger_roles_absents "parcours_livrable.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_ml_${JETON}"; CTL="${PREFIXE}_cl_${JETON}"
SVC="${PREFIXE}_sl_${JETON}"; BASE="${PREFIXE}_dl_${JETON}"
MDP="FICTIF-liw-${JETON}"
MANDAT="11111111-9999-9999-9999-999999999901:FICTIF-EMPREINTE-LIW-${JETON}"
#: TROIS IDENTITES, ET LA TROISIEME EST TOUT L'OBJET DE CE HARNAIS.
#:
#: A — ingenieur d'ORG_A: cree, calcule, produit le brouillon, soumet.
#: V — ingenieur VALIDATEUR d'ORG_A, nomme et inscrit: le seul qui atteste.
#: B — ingenieur d'ORG_B: l'ailleurs sans lequel l'isolation ne se prouve pas.
ACTEUR_A="22222222-9999-9999-9999-99999999aaa1"
ACTEUR_V="22222222-9999-9999-9999-99999999bbb1"
ACTEUR_B="33333333-9999-9999-9999-99999999fff1"
ORG_A="44444444-9999-9999-9999-9999999999c1"
ORG_B="55555555-9999-9999-9999-9999999999d1"
RACINE_ID="11111111-9999-9999-9999-999999999901"

# LES PORTS SONT DECALES DES PORTS DE DEVELOPPEMENT. Se lier a 3000 ou 8000
# ferait echouer le harnais quand un serveur de developpement tourne — ou pire,
# le ferait piloter CE serveur-la, avec un autre code que celui du depot.
PORT_AUTH="${EUROSTRUCT_E2E_PORT_AUTH_LIV:-54341}"
PORT_API="${EUROSTRUCT_E2E_PORT_API_LIV:-8021}"
PORT_WEB="${EUROSTRUCT_E2E_PORT_WEB_LIV:-3021}"

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
  harnais_postcondition_nettoyage "parcours_livrable.sh" \
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
  echo "NON EXECUTE: parcours_livrable.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Le parcours navigateur ne peut pas etre eprouve, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  exit 4
fi
if ! node "$RACINE/web/e2e/verifier_navigateur.mjs" >/dev/null 2>&1; then
  echo "NON EXECUTE: parcours_livrable.sh — Playwright ou Chromium absent." >&2
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

echo "    tranche applicative: le livrable, depuis un navigateur"

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

# LE DECOR METIER: deux organisations, trois adhesions, une annexe.
#
# IL EST POSE PAR LE PROPRIETAIRE DE LA BASE, PAS PAR LE PRODUIT. Creer une
# organisation, enroler ses membres et enregistrer leur nom releve de
# l'administration du compte; aucune route du produit ne le fait, et lui en
# donner une ici ferait passer pour eprouve un chemin qui n'existe pas.
#
# `display_name` ET `professional_id` SONT LE POINT. La primitive
# d'attestation les DERIVE de l'adhesion, jamais du corps HTTP: c'est ce qui
# rend impossible d'attester sous le nom de quelqu'un d'autre. Les poser ici,
# c'est poser ce que l'organisation sait de ses membres.
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values
  ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_V'),('$ACTEUR_B')
on conflict do nothing;
insert into organizations (id, name, country) values
  ('$ORG_A', 'FICTIF Bureau A', 'BE'),
  ('$ORG_B', 'FICTIF Bureau B', 'BE')
on conflict do nothing;
insert into organization_members
  (org_id, user_id, role, display_name, professional_id) values
  ('$ORG_A', '$ACTEUR_A', 'engineer',
   'FICTIF Ing. A', null),
  ('$ORG_A', '$ACTEUR_V', 'validating_engineer',
   'FICTIF Ing. V (compte de test)', 'FICTIF-ORDRE-0001'),
  ('$ORG_B', '$ACTEUR_B', 'engineer',
   'FICTIF Ing. B', null)
on conflict do nothing;
-- LE DOCUMENT, PAS SES VALEURS. Aucun parametre n'est insere, aucune valeur
-- normative n'est inventee. Sans cette ligne, la creation de projet
-- refuserait — et elle aurait raison: un projet citerait un referentiel
-- absent a sa date.
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL

# LE DECOR EST CONSTATE, PAS SUPPOSE.
NB_ORG=$(q "select count(*) from organizations")
NB_MEM=$(q "select count(*) from organization_members")
NB_VAL=$(q "select count(*) from organization_members
             where role = 'validating_engineer' and display_name is not null")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_ORG" != "2" || "$NB_MEM" != "3" || "$NB_VAL" != "1"
      || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor metier n'est pas pose." >&2
  echo "             org=$NB_ORG membres=$NB_MEM validateurs=$NB_VAL" >&2
  echo "             annexes_BE=$NB_ANX" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# LA RACINE D'AUTORITE ET LES DEUX HABILITATIONS DU QUATRE-YEUX.
#
# ELLES SONT UN PREALABLE, PAS L'OBJET DU PARCOURS. Une attestation ne peut
# porter que sur un calcul STRICT abouti; le mode strict ne s'ouvre que par le
# quatre-yeux; le quatre-yeux exige deux habilitations distinctes. A et V les
# recoivent donc ici, et le parcours navigateur fera passer les confirmations
# par les routes du produit avec leurs jetons reels.
#
# AUCUNE VALEUR NORMATIVE N'EST INVENTEE: les valeurs viennent du registre du
# moteur, ou elles sont marquees `pending_verification`. Ce qui est produit est
# une DECISION HUMAINE FICTIVE A DEUX REGARDS.
# ---------------------------------------------------------------------------
ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine livrable web')" \
  >/dev/null 2>&1
GR="$(q "select id from normative_authorisation_grants where origin='bootstrap' limit 1")"
if [[ ! "$GR" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: aucune racine amorcee." >&2
  exit 1
fi

EDITION_BE="$(python3 - <<'FINPY'
from eurostruct_engine.ndp import load_parameter_set
jeu = load_parameter_set("BE", strict=True)
editions = {jeu.find(k).edition for k in jeu.keys()}
if len(editions) != 1:
    raise SystemExit(f"editions multiples: {sorted(editions)}")
print(editions.pop())
FINPY
)"
if [[ -z "$EDITION_BE" ]]; then
  echo "      ECHEC: edition du registre belge illisible." >&2
  exit 1
fi

octroyer() {   # octroyer <beneficiaire> <motif>
  PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -tAc \
    "set eurostruct.actor_id = '$RACINE_ID';
     insert into normative_authorisation_grants
       (grantee_id, grantee_name, permission, country_code, standard_family,
        part, edition, reason, parent_grant_id)
     values ('$1', 'FICTIF $1', 'can_validate_normative_reference', 'BE',
             'EN 1992', '1-1', \$\$$EDITION_BE\$\$, '$2', '$GR')" \
    -d "$BASE" >/dev/null 2>&1
  q "select id from normative_authorisation_grants where reason = '$2'"
}
GA="$(octroyer "$ACTEUR_A" 'FICTIF autorite de A (livrable web)')"
GV="$(octroyer "$ACTEUR_V" 'FICTIF autorite de V (livrable web)')"
if [[ ! "$GA" =~ ^[0-9a-f-]{36}$ || ! "$GV" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: les habilitations du quatre-yeux n'ont pas ete creees." >&2
  echo "             A=$GA V=$GV" >&2
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
export EUROSTRUCT_E2E_COMPTES="a@fictif.invalid:FICTIF-A:$ACTEUR_A:3600:oui,v@fictif.invalid:FICTIF-V:$ACTEUR_V:3600:oui,b@fictif.invalid:FICTIF-B:$ACTEUR_B:3600:oui"
# L'IDENTITE DE BUILD DU HARNAIS.
#
# La persistance la REFUSE quand elle manque: un calcul conserve doit designer
# le code exact qui l'a produit, et « 0.3.0 » ne le fait pas. Le harnais en
# declare donc une, derivee du jeton de l'execution — deux executions du meme
# harnais sont deux builds distincts pour ce qui nous occupe, et c'est
# exactement ce que le cas « meme requete, autre build » exploite.
export EUROSTRUCT_BUILD_SHA="FICTIF-build-${JETON}"
export EUROSTRUCT_E2E_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_E2E_ACTEUR_V="$ACTEUR_V"
export EUROSTRUCT_E2E_ACTEUR_B="$ACTEUR_B"
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
  echo "NON EXECUTE: parcours_livrable.sh — web/node_modules absent." >&2
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
# 5. LES DEUX PARCOURS
# ---------------------------------------------------------------------------
# UN SEUL DECOR POUR DEUX VERTICALES, ET C'EST DELIBERE.
#
# Dresser la pile entiere — base, migrations, sceau, quatre-yeux, emetteur de
# jetons, API, build de production de l'interface — coute plusieurs minutes. La
# redresser a l'identique pour eprouver la verification complete donnerait un
# second harnais dont chaque ligne serait la copie d'une autre: deux decors a
# maintenir, et le jour ou l'un derive, c'est celui qu'on ne regarde pas.
#
# LES DEUX PARCOURS SONT INDEPENDANTS. Chacun cree SON projet et ne lit rien de
# ce que l'autre a ecrit; l'ordre ne les lie pas. Mais les DEUX doivent passer:
# le second ne rattrape pas le premier.
EUROSTRUCT_WEB="http://127.0.0.1:$PORT_WEB" \
EUROSTRUCT_API="http://127.0.0.1:$PORT_API" \
  node "$RACINE/web/e2e/parcours_livrable.mjs"
CODE=$?

# UN ECHEC DU PREMIER N'EMPECHE PAS D'EPROUVER LE SECOND, et c'est ce qui rend
# le diagnostic utile: savoir si UNE verticale est cassee ou LES DEUX separe un
# defaut d'ecran d'un decor qui n'a pas pris. Un « non execute » (4) est en
# revanche un arret — le navigateur manque, et le second n'irait pas plus loin.
if [[ $CODE -eq 0 || $CODE -eq 1 ]]; then
  echo ""
  EUROSTRUCT_WEB="http://127.0.0.1:$PORT_WEB" \
  EUROSTRUCT_API="http://127.0.0.1:$PORT_API" \
    node "$RACINE/web/e2e/parcours_verification.mjs"
  CODE_VC=$?
  [[ $CODE -eq 0 ]] && CODE=$CODE_VC
fi

# CE QUE LES SERVEURS ONT DIT PENDANT LE PARCOURS.
#
# Un parcours rouge se lit d'abord dans le navigateur — c'est ce que voit
# l'ingenieur — mais certaines pannes n'y laissent qu'un « Failed to fetch »
# qui ne nomme rien. Les journaux de l'API et de l'interface, eux, portent la
# trace exacte, et sans eux le diagnostic recommence a zero: on relance dix
# minutes de decor pour lire ce qu'on avait deja sous la main.
#
# ILS NE SORTENT QU'EN CAS D'ECHEC, et bornes: un parcours vert n'a rien a
# dire, et un journal entier noierait le verdict.
if [[ $CODE -ne 0 ]]; then
  for duo in "api:$TMP/api.log" "interface:$TMP/web.log"; do
    QUOI="${duo%%:*}"; FICHIER="${duo#*:}"
    [[ -s "$FICHIER" ]] || continue
    echo "" >&2
    echo "      --- $QUOI, 25 dernieres lignes ---" >&2
    tail -n 25 "$FICHIER" >&2
  done
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "==================================================="
  echo " Depuis le navigateur: un calcul strict enregistre,"
  echo " un brouillon dont les octets telecharges portent"
  echo " l'empreinte enregistree et la gardent apres F5,"
  echo " une attestation metier authentifiee dont le nom"
  echo " vient de l'adhesion, une emission qui l'exige, un"
  echo " livrable emis qui ne se modifie plus, un indice"
  echo " suivant, et une organisation voisine qui n'obtient"
  echo " rien."
  echo ""
  echo " Et la verticale complete: sept etapes qui disent"
  echo " ce qui manque, un refus strict qui nomme les"
  echo " parametres, cinq chapitres verifies, une note dont"
  echo " les octets portent l'empreinte enregistree, un plan"
  echo " produit SANS qu'aucun ferraillage ne parte du"
  echo " navigateur, et les memes octets apres F5."
  echo "==================================================="
fi
exit $CODE
