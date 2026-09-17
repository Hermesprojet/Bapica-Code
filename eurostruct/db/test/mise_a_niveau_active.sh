#!/usr/bin/env bash
#
# EUROSTRUCT — METTRE A NIVEAU UNE INSTALLATION EN SERVICE, SANS PERDRE SON TRAVAIL
#
#   EUROSTRUCT_CLUSTER_JETABLE=oui-cluster-jetable-et-isole \
#   PGHOST=/var/run/postgresql PGUSER=postgres \
#   db/test/mise_a_niveau_active.sh
#
# CE QUE CE HARNAIS ETABLIT
# --------------------------
# Qu'une installation issue d'une VERSION ANTERIEURE, REELLEMENT PEUPLEE —
# projet, etude, variante, note PDF, plan DXF — recoit les migrations
# manquantes par la commande officielle, et que rien de ce qui a ete fait
# n'est perdu ni modifie.
#
# L'ANCIENNE VERSION EST UN VRAI ARBRE, pas une simulation: un worktree Git du
# commit designe par EUROSTRUCT_MAN_ANCIEN (defaut: da01259, la version livree
# avant la migration 0027). C'est SA commande de deploiement qui installe, et
# SON code produit qui peuple. La mise a niveau, elle, est celle du depot
# courant: c'est exactement le geste que fait un exploitant qui met a jour.
#
# LES DOUZE PAS
# --------------
#    0. prerequis (git, pg_dump/pg_restore, dependances du produit)
#    1. provisionnement — trois roles, un role de sauvegarde, la base, le
#       schema auth fictif, les declarations
#    2. installation de l'ANCIENNE version, par SA commande officielle
#    3. peuplement PAR LE PRODUIT ancien (projet, etude, variante, PDF, DXF)
#    4. sauvegarde: archive pg_dump -Fc + copie du magasin d'objets
#    5. diagnostic de mise a niveau — annonce, et RIEN de modifie
#    6. les refus: sans consentement, sans sauvegarde, application connectee
#    7. deux mises a niveau concurrentes: une seule applique
#    8. la mise a niveau, puis sa relance (idempotence)
#    9. restauration de la sauvegarde dans une base ISOLEE, et comparaison
#       ligne pour ligne des tables metier avec la base mise a niveau
#   10. interruption a une etape critique, sur la base restauree, puis reprise
#       et achevement
#   11. verification PAR LE PRODUIT NOUVEAU: memes identifiants, memes
#       relations, memes empreintes, memes octets
#
# CE QU'IL EXIGE, ET CE QU'IL DETRUIT. Un cluster PostgreSQL JETABLE prouve tel
# (db/test/lib_harnais.sh); git, pg_dump, pg_restore, et les dependances python
# du produit. Il ne detruit que ce qu'il a cree, nom par nom: ses roles, ses
# deux bases, son worktree, ses fichiers temporaires.
#
# CODES: 0 tout est tenu; 1 un pas a echoue; 2 refus (cluster non jetable);
#        4 non executable (prerequis absent).
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # eurostruct/db/test
RACINE="$(cd "$ICI/../.." && pwd)"                    # eurostruct/
DEPOT="$(dirname "$RACINE")"                          # la copie de travail git
# shellcheck source=lib_harnais.sh
source "$ICI/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$RACINE/db/apply_migration.sh" 2>/dev/null

harnais_piege_signaux 2>/dev/null || true
exiger_precontrole_local "mise_a_niveau_active.sh" || exit 2
harnais_verrou_prendre "mise_a_niveau_active.sh" || exit $?
exiger_cluster_jetable "mise_a_niveau_active.sh" || exit 2
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend eurostruct_reconciliation)
exiger_roles_absents "mise_a_niveau_active.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

ANCIEN="${EUROSTRUCT_MAN_ANCIEN:-da01259}"
for outil in git psql pg_dump pg_restore python3; do
  command -v "$outil" >/dev/null 2>&1 \
    || { echo "NON EXECUTE: $outil absent." >&2; exit 4; }
done
[[ -n "${EUROSTRUCT_VENV:-}" && -x "$EUROSTRUCT_VENV/bin/python3" ]] \
  && export PATH="$EUROSTRUCT_VENV/bin:$PATH"
python3 - <<'PY' 2>/dev/null || { echo "NON EXECUTE: dependances du produit absentes (fastapi, httpx, jwt, cryptography, psycopg2)." >&2; exit 4; }
import fastapi, jwt, psycopg2  # noqa: F401
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: F401
from fastapi.testclient import TestClient  # noqa: F401
PY
git -C "$DEPOT" rev-parse --verify "$ANCIEN^{commit}" >/dev/null 2>&1 \
  || { echo "NON EXECUTE: le commit « $ANCIEN » n'existe pas dans ce depot." >&2; exit 4; }

# ---------------------------------------------------------------------------
# LES NOMS — tous suffixes d'un jeton, donc detruisibles nom par nom
# ---------------------------------------------------------------------------
JETON="$(harnais_jeton)"
P="esc_man"
MIG="${P}_mg_${JETON}"; CTL="${P}_pl_${JETON}"; SVC="${P}_ap_${JETON}"; SAV="${P}_sv_${JETON}"
BASE="${P}_db_${JETON}"; BASE_R="${P}_rs_${JETON}"
MDP="FICTIF-man-${JETON}"
ACTEUR="44444444-8888-8888-8888-8888880000${JETON:0:2}"
RACINE_ID="55555555-8888-8888-8888-8888880000${JETON:0:2}"
MANDAT="$RACINE_ID:FICTIF-MANDAT-MAN-$JETON"
DOSSIER="$ICI/mise-a-niveau"
mkdir -p "$DOSSIER"; chmod 700 "$DOSSIER"
JOURNAL="$DOSSIER/mise-a-niveau-$(date -u +%Y%m%dT%H%M%SZ).log"
TMP="$(mktemp -d)"; chmod 700 "$TMP"
VIEUX="$TMP/ancien"
MAGASIN="$TMP/magasin"; mkdir -p "$MAGASIN"
MAGASIN_COPIE="$TMP/magasin-sauvegarde"
ARCHIVE="$TMP/$BASE.dump"
KO=0

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
ctl()  { PGPASSWORD="$MDP" psql -X -q -h 127.0.0.1 -U "$CTL" -d "${1:-$BASE}" "${@:2}"; }
DSN_APP="postgresql://$SVC:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE"
DSN_PLAN="postgresql://$CTL:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE"
DSN_MIG="postgresql://$MIG:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE"

NOMS=("0 prerequis" "1 provisionnement" "2 installation de l'ancienne version"
      "3 peuplement par le produit ancien" "4 sauvegarde (base et magasin)"
      "5 diagnostic sans modification" "6 refus: consentement, sauvegarde, ecritures"
      "7 refus de mise a niveau concurrente" "8 mise a niveau, puis relance"
      "9 restauration isolee et comparaison ligne pour ligne"
      "10 interruption a une etape critique, puis reprise"
      "11 verification par le produit nouveau")
ETATS=(); DETAILS=()
for _ in "${NOMS[@]}"; do ETATS+=("NON EXECUTE"); DETAILS+=("non tente"); done
poser()    { ETATS[$1]="$2"; DETAILS[$1]="$3"; }
execute()  { poser "$1" "EXECUTE" "$2"; }
# UN ECHEC SE DIT QUAND IL ARRIVE, pas seulement dans le bilan: un pas qui
# arrete le harnais avant le bilan ne laisserait aucune trace lisible.
echoue()   { poser "$1" "ECHOUE" "$2"; KO=1; echo "      ECHEC (${NOMS[$1]}): $2" >&2; }
non_exec() { poser "$1" "NON EXECUTE" "$2"; }

nettoyer() {
  echo ""
  echo "--- nettoyage: worktree, bases et roles crees ---"
  git -C "$DEPOT" worktree remove --force "$VIEUX" >/dev/null 2>&1 || true
  git -C "$DEPOT" worktree prune >/dev/null 2>&1 || true
  detruire_bases_creees
  detruire_roles_crees
  harnais_postcondition_nettoyage "mise_a_niveau_active.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"
  rm -rf "$TMP"
  harnais_verrou_rendre 2>/dev/null || true
}
trap nettoyer EXIT

echo "    mise a niveau d'une installation en service (cluster jetable, jeton $JETON)"
echo "    ancienne version: $ANCIEN | journal: $JOURNAL"

# ---------------------------------------------------------------------------
# 0. PREREQUIS
# ---------------------------------------------------------------------------
echo "==> 0. prerequis et worktree de l'ancienne version"
if git -C "$DEPOT" worktree add --detach "$VIEUX" "$ANCIEN" >"$TMP/worktree.log" 2>&1; then
  execute 0 "worktree $ANCIEN ($(git -C "$VIEUX" rev-parse --short HEAD))"
else
  echoue 0 "le worktree de « $ANCIEN » n'a pas pu etre cree: $(tail -1 "$TMP/worktree.log")"
  exit 1
fi
VIEUX_E="$VIEUX/eurostruct"
[[ -x "$VIEUX_E/tools/deploy_eurostruct.sh" ]] \
  || { echoue 0 "l'ancienne version ne porte pas tools/deploy_eurostruct.sh"; exit 1; }

# ---------------------------------------------------------------------------
# 1. PROVISIONNEMENT — ce qu'un exploitant pose, et rien de plus
# ---------------------------------------------------------------------------
echo "==> 1. provisionnement: roles, base, schema auth fictif, declarations"
{
  creer_role "$MIG" "login password '$MDP' createrole createdb" &&
  creer_role "$CTL" "login password '$MDP' createrole" &&
  creer_role "$SVC" "login password '$MDP'" &&
  creer_role "$SAV" "login password '$MDP' bypassrls" &&
  adm -c "grant pg_read_all_data to \"$SAV\";" >/dev/null 2>&1 &&
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1 &&
  creer_base "$BASE" "owner \"$MIG\"" &&
  creer_base "$BASE_R" "owner \"$MIG\""
} || { echoue 1 "creation des roles ou des bases"; exit 1; }
for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}"; do registre_role "$r"; done

declarations() {   # declarations <base> — les memes des deux cotes
  local b="$1"
  adm -c "alter database \"$b\" set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
  adm -c "alter database \"$b\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
  adm -c "alter database \"$b\" set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
  adm -c "alter database \"$b\" set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
  adm -c "alter database \"$b\" set eurostruct.bootstrap_mandate = '$MANDAT';" >/dev/null 2>&1
}
admb -v ON_ERROR_STOP=1 -f "$ICI/00_supabase_stub.sql" >/dev/null 2>&1 \
  || { echoue 1 "schema auth fictif"; exit 1; }
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL
declarations "$BASE"
admb -v ON_ERROR_STOP=1 -c "insert into auth.users (id) values
  ('$ACTEUR'::uuid), ('$RACINE_ID'::uuid) on conflict do nothing;" >/dev/null 2>&1 \
  || { echoue 1 "inscription des comptes dans auth.users"; exit 1; }
execute 1 "roles $CTL/$MIG/$SVC/$SAV, bases $BASE et $BASE_R, auth fictif, declarations"

# ---------------------------------------------------------------------------
# 2. L'ANCIENNE VERSION S'INSTALLE, PAR SA PROPRE COMMANDE
# ---------------------------------------------------------------------------
echo "==> 2. installation de l'ancienne version ($ANCIEN), par sa commande officielle"
if ESC_PLAN_URL="$DSN_PLAN" ESC_MIGRATOR_URL="$DSN_MIG" \
   bash "$VIEUX_E/tools/deploy_eurostruct.sh" --auto-heberge >"$TMP/install.log" 2>&1; then
  N_AVANT="$(psql -X -q -tA -d "$BASE" -c "select count(*) from normative_migration_ledger" 2>/dev/null | tr -d ' ')"
  D_AVANT="$(psql -X -q -tA -d "$BASE" -c "select max(migration_id) from normative_migration_ledger" 2>/dev/null | tr -d ' ')"
  psql -X -q -d "$BASE" -v ON_ERROR_STOP=1 -f "$VIEUX_E/db/seed/0001_ndp.sql" >"$TMP/seed.log" 2>&1 \
    || { echoue 2 "referentiel national: $(grep -m1 -i error "$TMP/seed.log" | cut -c1-120)"; exit 1; }
  ctl "$BASE" -v ON_ERROR_STOP=1 -c "grant eurostruct_authority_backend to \"$SVC\";" >"$TMP/admission.log" 2>&1
  [[ "$(psql -X -q -tA -d "$BASE" -c "select pg_has_role('$SVC','eurostruct_authority_backend','USAGE')::text")" == "true" ]] \
    || { echoue 2 "le login applicatif n'a pas ete admis: $(tail -2 "$TMP/admission.log" | tr '\n' ' ' | cut -c1-180)"; exit 1; }
  execute 2 "base ACTIVE, $N_AVANT migrations (derniere « $D_AVANT »), referentiel pose, login admis"
else
  echoue 2 "l'installation de l'ancienne version a echoue: $(grep -m1 -E 'ECHEC|ERROR' "$TMP/install.log" | cut -c1-140)"
  # LE JOURNAL EST IMPRIME ICI, ET PAS SEULEMENT ARCHIVE: un pas qui arrete le
  # harnais avant le bilan n'a laisse aucune trace lisible sans lui.
  sed -E "s/$MDP/<mdp>/g; s#postgres(ql)?://[^ ]*#<dsn>#g; s/^/      /" "$TMP/install.log" | tail -25 >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. LE PEUPLEMENT, PAR LE PRODUIT ANCIEN
# ---------------------------------------------------------------------------
echo "==> 3. peuplement par le produit ancien: projet, etude, variante, PDF, DXF"
ETAT_JSON="$TMP/etat.json"
if ESC_PEUPLE_DSN="dbname=$BASE user=$SVC password=$MDP host=127.0.0.1 port=${PGPORT:-5432}" \
   ESC_PEUPLE_ACTEUR="$ACTEUR" ESC_PEUPLE_JETON="$JETON" \
   EUROSTRUCT_STORAGE_BACKEND=local EUROSTRUCT_STORAGE_DIR="$MAGASIN" \
   EUROSTRUCT_BUILD_SHA="FICTIF-ancien-$JETON" \
   PYTHONPATH="$VIEUX_E/api/src:$VIEUX_E/engine/src" \
   python3 "$ICI/atelier_peupler.py" peupler "$ETAT_JSON" >"$TMP/peuple.log" 2>&1; then
  execute 3 "$(tail -1 "$TMP/peuple.log")"
else
  echoue 3 "le peuplement a echoue: $(tail -2 "$TMP/peuple.log" | tr '\n' ' ' | cut -c1-200)"
  sed -E "s/$MDP/<mdp>/g; s/^/      /" "$TMP/peuple.log" | tail -25 >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. LA SAUVEGARDE — celle que la mise a niveau exigera
# ---------------------------------------------------------------------------
echo "==> 4. sauvegarde: archive pg_dump -Fc de la base, copie du magasin d'objets"
if PGPASSWORD="$MDP" pg_dump -Fc -h 127.0.0.1 -U "$SAV" -d "$BASE" -f "$ARCHIVE" >"$TMP/dump.log" 2>&1 \
   && [[ -s "$ARCHIVE" ]] && cp -a "$MAGASIN" "$MAGASIN_COPIE"; then
  execute 4 "archive $(stat -c %s "$ARCHIVE") o, magasin $(find "$MAGASIN_COPIE" -type f | wc -l | tr -d ' ') objet(s)"
else
  echoue 4 "la sauvegarde a echoue: $(tail -1 "$TMP/dump.log")"
  exit 1
fi

# ---------------------------------------------------------------------------
# LA COMMANDE DE MISE A NIVEAU, TELLE QU'UN EXPLOITANT L'APPELLE
# ---------------------------------------------------------------------------
man() {   # man <base> [options...] — la commande du DEPOT COURANT
  local b="$1"; shift
  ESC_PLAN_URL="postgresql://$CTL:$MDP@127.0.0.1:${PGPORT:-5432}/$b" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@127.0.0.1:${PGPORT:-5432}/$b" \
  ESC_UPGRADE_CONSENTEMENT="${ESC_UPGRADE_CONSENTEMENT-oui-mettre-a-niveau-$b}" \
  ESC_UPGRADE_SAUVEGARDE="${ESC_UPGRADE_SAUVEGARDE-$ARCHIVE}" \
    bash "$RACINE/tools/deploy_eurostruct.sh" --auto-heberge "$@"
}
inscrites() { psql -X -q -tA -d "${1:-$BASE}" -c "select count(*) from normative_migration_ledger" 2>/dev/null | tr -d ' '; }

# ---------------------------------------------------------------------------
# 5. LE DIAGNOSTIC — il annonce, et ne modifie rien
# ---------------------------------------------------------------------------
echo "==> 5. diagnostic de mise a niveau (sans modification)"
N5="$(inscrites)"
if man "$BASE" --mettre-a-niveau --diagnostic >"$TMP/diag.log" 2>&1; then
  ok5=1
  grep -q "version presente : $N5 migration" "$TMP/diag.log" || { ok5=0; D5="l'annonce ne dit pas la version presente"; }
  grep -qE "a appliquer      : [1-9]" "$TMP/diag.log" || { ok5=0; D5="l'annonce ne liste aucune migration a appliquer"; }
  grep -q "RIEN N'A ETE MODIFIE" "$TMP/diag.log" || { ok5=0; D5="le diagnostic ne dit pas qu'il n'a rien modifie"; }
  [[ "$(inscrites)" == "$N5" ]] || { ok5=0; D5="le registre a change pendant un DIAGNOSTIC"; }
  if ((ok5)); then
    execute 5 "annonce $N5 -> $(grep -oE 'version cible    : [0-9]+' "$TMP/diag.log" | grep -oE '[0-9]+'), $(grep -cE '^ +[0-9]{4}_' "$TMP/diag.log") migration(s) nommee(s), registre inchange"
  else
    echoue 5 "$D5"
  fi
else
  echoue 5 "le diagnostic a rendu $? — $(grep -m1 -E 'MANQUE|ECHEC|REFUS' "$TMP/diag.log" | cut -c1-140)"
fi

# ---------------------------------------------------------------------------
# 6. LES REFUS — ce qui n'est pas etabli vaut non
# ---------------------------------------------------------------------------
echo "==> 6. refus: sans consentement, sans sauvegarde, application connectee"
N6="$(inscrites)"; ok6=1; D6=""
# LES AFFECTATIONS EN PREFIXE D'UNE FONCTION PERSISTENT DANS LE SHELL (POSIX,
# et bash s'y conforme): sans le sous-shell, « ESC_UPGRADE_CONSENTEMENT= man …»
# laisserait la variable VIDE pour tous les pas suivants, et la mise a niveau
# refuserait pour une raison qu'on aurait posee sans le vouloir.
( ESC_UPGRADE_CONSENTEMENT="" man "$BASE" --mettre-a-niveau ) >"$TMP/refus1.log" 2>&1
[[ $? -eq 2 ]] && grep -q "ESC_UPGRADE_CONSENTEMENT" "$TMP/refus1.log" \
  || { ok6=0; D6="sans consentement, la commande n'a pas refuse par 2"; }
( ESC_UPGRADE_SAUVEGARDE="" man "$BASE" --mettre-a-niveau ) >"$TMP/refus2.log" 2>&1
[[ $? -eq 2 ]] && grep -q "ESC_UPGRADE_SAUVEGARDE" "$TMP/refus2.log" \
  || { ok6=0; D6="${D6:+$D6; }sans sauvegarde, la commande n'a pas refuse par 2"; }
( ESC_UPGRADE_SAUVEGARDE="$TMP/peuple.log" man "$BASE" --mettre-a-niveau ) >"$TMP/refus3.log" 2>&1
[[ $? -eq 2 ]] && grep -q "n'est pas une archive pg_dump lisible" "$TMP/refus3.log" \
  || { ok6=0; D6="${D6:+$D6; }une archive qui n'en est pas une a ete acceptee"; }
# UNE SESSION APPLICATIVE OUVERTE: la mise a niveau refuse tant que
# l'application peut ecrire. La session est tenue par un co-processus psql.
coproc APPLI { PGPASSWORD="$MDP" psql -X -q -At -h 127.0.0.1 -U "$SVC" -d "$BASE" 2>&1; }
echo "select 1;" >&"${APPLI[1]}"; read -r -t 15 -u "${APPLI[0]}" _ || true
man "$BASE" --mettre-a-niveau >"$TMP/refus4.log" 2>&1
[[ $? -eq 2 ]] && grep -q "l'application ecrit encore" "$TMP/refus4.log" \
  || { ok6=0; D6="${D6:+$D6; }une session applicative ouverte n'a pas fait refuser"; }
eval "exec ${APPLI[1]}>&-" 2>/dev/null || true
wait "$APPLI_PID" 2>/dev/null || true
[[ "$(inscrites)" == "$N6" ]] || { ok6=0; D6="${D6:+$D6; }un refus a laisse le registre change"; }
if ((ok6)); then
  execute 6 "quatre refus (consentement, sauvegarde absente, archive invalide, ecritures en cours), registre inchange"
else
  echoue 6 "$D6"
fi

# ---------------------------------------------------------------------------
# 7. DEUX MISES A NIVEAU CONCURRENTES
# ---------------------------------------------------------------------------
echo "==> 7. deux mises a niveau simultanees: une seule applique"
( man "$BASE" --mettre-a-niveau >"$TMP/conc-a.log" 2>&1; echo $? >"$TMP/conc-a.rc" ) &
PID_A=$!
( sleep 0.2; man "$BASE" --mettre-a-niveau >"$TMP/conc-b.log" 2>&1; echo $? >"$TMP/conc-b.rc" ) &
PID_B=$!
wait "$PID_A" "$PID_B" 2>/dev/null
RC_A="$(cat "$TMP/conc-a.rc" 2>/dev/null)"; RC_B="$(cat "$TMP/conc-b.rc" 2>/dev/null)"
if { [[ "$RC_A" == "0" && "$RC_B" == "4" ]] || [[ "$RC_A" == "4" && "$RC_B" == "0" ]]; } \
   && grep -qh "DEPLOYMENT_ALREADY_RUNNING" "$TMP/conc-a.log" "$TMP/conc-b.log"; then
  execute 7 "codes $RC_A et $RC_B — l'une applique, l'autre refuse par DEPLOYMENT_ALREADY_RUNNING"
else
  echoue 7 "codes obtenus: $RC_A et $RC_B (attendu 0 et 4). $(grep -m1 -E 'ECHEC|REFUS|MANQUE' "$TMP/conc-a.log" "$TMP/conc-b.log" | cut -c1-140)"
fi

# ---------------------------------------------------------------------------
# 8. LA MISE A NIVEAU, PUIS SA RELANCE
# ---------------------------------------------------------------------------
echo "==> 8. etat apres mise a niveau, puis relance (idempotence)"
N8="$(inscrites)"
CIBLE="$(find "$RACINE/db/migrations" -maxdepth 1 -name '*.sql' | wc -l | tr -d ' ')"
ok8=1; D8=""
[[ "$N8" == "$CIBLE" ]] || { ok8=0; D8="le registre porte $N8 migrations, le depot en a $CIBLE"; }
[[ "$(psql -X -q -tA -d "$BASE" -c "select normative_activation_state()" 2>/dev/null | tr -d ' ')" == "ACTIVE" ]] \
  || { ok8=0; D8="${D8:+$D8; }la base n'est plus ACTIVE"; }
[[ "$(psql -X -q -tA -d "$BASE" -c "select pg_has_role('$SVC','eurostruct_authority_backend','USAGE')::text")" == "true" ]] \
  || { ok8=0; D8="${D8:+$D8; }le service n'a pas ete retabli: le login applicatif ne peut plus ecrire"; }
RESIDU="$(psql -X -q -tA -d "$BASE" -c "select count(*) from unnest(array['eurostruct_normative_writer','eurostruct_normative_bootstrap','eurostruct_normative_activator']) r where pg_has_role('$MIG', r, 'USAGE') or pg_has_role('$MIG', r, 'SET') or pg_has_role('$MIG', r, 'MEMBER WITH ADMIN OPTION')" 2>/dev/null | tr -d ' ')"
[[ "$RESIDU" == "0" ]] || { ok8=0; D8="${D8:+$D8; }le migrateur conserve $RESIDU capacite(s)"; }
man "$BASE" --mettre-a-niveau >"$TMP/relance.log" 2>&1
RC_REL=$?
[[ $RC_REL -eq 0 ]] && grep -q "Rien a faire" "$TMP/relance.log" \
  || { ok8=0; D8="${D8:+$D8; }la relance apres succes a rendu $RC_REL sans dire « Rien a faire »"; }
[[ "$(inscrites)" == "$N8" ]] || { ok8=0; D8="${D8:+$D8; }la relance a modifie le registre"; }
if ((ok8)); then
  execute 8 "$N_AVANT -> $N8 migrations, ACTIVE, service retabli, zero capacite residuelle, relance idempotente"
else
  echoue 8 "$D8"
fi

# ---------------------------------------------------------------------------
# 9. LA RESTAURATION ISOLEE, ET LA COMPARAISON LIGNE POUR LIGNE
# ---------------------------------------------------------------------------
# CE QUE LA COMPARAISON PROUVE. La base restauree porte les donnees AVANT la
# mise a niveau; la base mise a niveau, celles d'APRES. Une empreinte de
# TOUTES LES LIGNES, des deux cotes, dit si une valeur a bouge — ce qu'un
# compte de lignes ne verrait pas.
echo "==> 9. restauration de la sauvegarde dans une base isolee, puis comparaison"
TABLES=(organizations projects calculations results verifications deliverables
        national_annexes normative_authorisation_grants
        normative_authority_decisions normative_rule_confirmations)
# LA RESTAURATION EST LE GESTE DE L'ADMINISTRATEUR DU CLUSTER, et pas celui du
# produit: rendre a chaque objet son proprietaire — `eurostruct_normative_writer`
# pour les tables d'autorite — exige d'appartenir a ces roles. Sur un
# hebergement, c'est le compte du fournisseur qui le fait
# (docs/DEPLOIEMENT_BASE_HEBERGEE.md §4); ici, le superutilisateur du cluster
# jetable. `pg_restore` ecrit sur la sortie d'erreur meme quand il reussit.
if pg_restore -d "$BASE_R" "$ARCHIVE" >"$TMP/restore.log" 2>&1 || [[ -s "$TMP/restore.log" ]]; then
  N_R="$(inscrites "$BASE_R")"
  if [[ -z "$N_R" || "$N_R" == "0" ]]; then
    echoue 9 "la restauration n'a pas rendu une base exploitable (registre: ${N_R:-illisible}). $(grep -m1 -i error "$TMP/restore.log" | cut -c1-140)"
  else
    DIFF=""
    for t in "${TABLES[@]}"; do
      EUROSTRUCT_COMPARE_SOURCE_URL="postgresql://$SAV:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE_R" \
      EUROSTRUCT_COMPARE_COPIE_URL="postgresql://$SAV:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE" \
        bash "$ICI/comparer_contenu.sh" "$t" >"$TMP/cmp-$t.log" 2>&1 \
        || DIFF="$DIFF $t"
    done
    if [[ -z "$DIFF" ]]; then
      execute 9 "base restauree ($N_R migrations, avant la mise a niveau); ${#TABLES[@]} tables metier IDENTIQUES ligne pour ligne a la base mise a niveau"
    else
      echoue 9 "tables differentes apres la mise a niveau:$DIFF"
    fi
  fi
else
  echoue 9 "la restauration a echoue: $(tail -1 "$TMP/restore.log")"
fi

# ---------------------------------------------------------------------------
# 10. L'INTERRUPTION, SUR LA BASE RESTAUREE, PUIS LA REPRISE
# ---------------------------------------------------------------------------
# LA BASE RESTAUREE EST UNE INSTALLATION ANCIENNE, COMPLETE ET PEUPLEE: c'est
# donc le terrain exact d'une seconde mise a niveau — celle qu'on interrompt.
#
# LES DECLARATIONS NE SONT PAS DANS L'ARCHIVE. `ALTER DATABASE ... SET` vit
# dans le catalogue du CLUSTER, pas dans la base: `pg_dump` ne l'emporte pas.
# Une restauration doit donc les reposer, sinon le manifeste ne correspond plus
# a celui qui a ete approuve — et la mise a niveau refuse, a juste titre.
echo "==> 10. interruption a une etape critique, puis reprise (sur la base restauree)"
declarations "$BASE_R"
if ! man "$BASE_R" --mettre-a-niveau --diagnostic >"$TMP/diag-r.log" 2>&1; then
  non_exec 10 "la base restauree n'est pas en etat d'etre mise a niveau: $(grep -m1 'MANQUE' "$TMP/diag-r.log" | cut -c1-140)"
else
  setsid bash -c "ESC_PLAN_URL='postgresql://$CTL:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE_R' \
    ESC_MIGRATOR_URL='postgresql://$MIG:$MDP@127.0.0.1:${PGPORT:-5432}/$BASE_R' \
    ESC_UPGRADE_CONSENTEMENT='oui-mettre-a-niveau-$BASE_R' \
    ESC_UPGRADE_SAUVEGARDE='$ARCHIVE' \
    bash '$RACINE/tools/deploy_eurostruct.sh' --auto-heberge --mettre-a-niveau" \
    >"$TMP/interrompu.log" 2>&1 &
  PID_MAN=$!
  # LE POINT D'ARRET EST CRITIQUE, ET CHOISI: la barriere est posee, les
  # emprunts sont accordes, les migrations commencent. Un SIGKILL n'y declenche
  # aucun piege — c'est precisement ce que la reprise doit savoir refermer.
  TUE=0
  for _ in $(seq 1 120); do
    if grep -q "mise a niveau 3/5" "$TMP/interrompu.log" 2>/dev/null; then
      kill -9 -"$PID_MAN" 2>/dev/null && TUE=1
      break
    fi
    kill -0 "$PID_MAN" 2>/dev/null || break
    sleep 0.25
  done
  wait "$PID_MAN" 2>/dev/null
  if ((! TUE)); then
    non_exec 10 "la mise a niveau n'a pas pu etre interrompue a l'etape voulue (elle a fini avant)"
  else
    # LA FENETRE EST RESTEE OUVERTE: c'est ce que la reprise doit constater.
    CAP="$(psql -X -q -tA -d "$BASE_R" -c "select count(*) from unnest(array['eurostruct_normative_writer','eurostruct_normative_bootstrap']) r where pg_has_role('$MIG', r, 'USAGE')" 2>/dev/null | tr -d ' ')"
    BAR="$(psql -X -q -tA -d "$BASE_R" -c "select pg_has_role('$SVC','eurostruct_authority_backend','USAGE')::text" 2>/dev/null | tr -d ' ')"
    ok10=1; D10="fenetre laissee ouverte (emprunts: $CAP, ecriture applicative: $BAR)"
    [[ "$CAP" != "0" || "$BAR" == "false" ]] || { ok10=0; D10="l'interruption n'a laisse aucune trace de fenetre ouverte"; }
    if ((ok10)); then
      if man "$BASE_R" --reprendre-mise-a-niveau >"$TMP/reprise.log" 2>&1; then
        CAP2="$(psql -X -q -tA -d "$BASE_R" -c "select count(*) from unnest(array['eurostruct_normative_writer','eurostruct_normative_bootstrap']) r where pg_has_role('$MIG', r, 'USAGE')" 2>/dev/null | tr -d ' ')"
        BAR2="$(psql -X -q -tA -d "$BASE_R" -c "select pg_has_role('$SVC','eurostruct_authority_backend','USAGE')::text" 2>/dev/null | tr -d ' ')"
        [[ "$CAP2" == "0" ]] || { ok10=0; D10="apres reprise, le migrateur conserve $CAP2 emprunt(s)"; }
        [[ "$BAR2" == "true" ]] || { ok10=0; D10="${D10}; apres reprise, l'application ne peut toujours pas ecrire"; }
        if ((ok10)); then
          if man "$BASE_R" --mettre-a-niveau >"$TMP/apres-reprise.log" 2>&1; then
            [[ "$(inscrites "$BASE_R")" == "$CIBLE" ]] \
              && execute 10 "$D10; reprise: emprunts repris et ecriture rendue; relance: $(inscrites "$BASE_R")/$CIBLE migrations" \
              || echoue 10 "apres reprise et relance, le registre porte $(inscrites "$BASE_R") migrations au lieu de $CIBLE"
          else
            echoue 10 "la relance apres reprise a echoue: $(grep -m1 -E 'ECHEC|MANQUE' "$TMP/apres-reprise.log" | cut -c1-140)"
          fi
        else
          echoue 10 "$D10"
        fi
      else
        echoue 10 "la reprise a echoue: $(grep -m1 -E 'ECHEC|DEPLOYMENT_' "$TMP/reprise.log" | cut -c1-140)"
      fi
    else
      echoue 10 "$D10"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 11. LA VERIFICATION PAR LE PRODUIT NOUVEAU
# ---------------------------------------------------------------------------
echo "==> 11. verification par le produit NOUVEAU: identifiants, relations, empreintes, octets"
if ESC_PEUPLE_DSN="dbname=$BASE user=$SVC password=$MDP host=127.0.0.1 port=${PGPORT:-5432}" \
   ESC_PEUPLE_ACTEUR="$ACTEUR" \
   EUROSTRUCT_STORAGE_BACKEND=local EUROSTRUCT_STORAGE_DIR="$MAGASIN" \
   EUROSTRUCT_BUILD_SHA="FICTIF-nouveau-$JETON" \
   PYTHONPATH="$RACINE/api/src:$RACINE/engine/src" \
   python3 "$ICI/atelier_peupler.py" verifier "$ETAT_JSON" >"$TMP/verif.log" 2>&1; then
  execute 11 "$(tail -1 "$TMP/verif.log")"
else
  echoue 11 "$(tail -2 "$TMP/verif.log" | tr '\n' ' ' | cut -c1-220)"
fi

# ---------------------------------------------------------------------------
# LE BILAN
# ---------------------------------------------------------------------------
{
  echo ""
  echo "=================================================================="
  echo " MISE A NIVEAU D'UNE INSTALLATION EN SERVICE — bilan"
  echo " ancienne version: $ANCIEN | depot courant: $(git -C "$DEPOT" rev-parse --short HEAD 2>/dev/null)"
  for i in "${!NOMS[@]}"; do
    printf '  %-48s %-12s %s\n' "${NOMS[$i]}" "${ETATS[$i]}" "$(cut -c1-104 <<<"${DETAILS[$i]}")"
  done
  echo ""
  if (( KO )); then
    echo " VERDICT: ECHEC — au moins un pas a echoue (journal: $JOURNAL)."
  else
    echo " VERDICT: TENU — une installation anterieure, peuplee par le produit,"
    echo " recoit les migrations manquantes et conserve ses etudes, leurs"
    echo " variantes et leurs documents, octet pour octet. La fenetre se"
    echo " referme, la concurrence est refusee, l'interruption se reprend."
  fi
  echo "=================================================================="
} | tee -a "$JOURNAL"
for f in "$TMP"/*.log; do
  [[ -f "$f" ]] && { echo "--- $(basename "$f") ---"; sed -E "s/$MDP/<mdp>/g; s#postgres(ql)?://[^ ]*#<dsn>#g" "$f"; } >>"$JOURNAL"
done
exit $(( KO ))
