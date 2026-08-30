#!/usr/bin/env bash
#
# EUROSTRUCT — L'ATELIER: UN PROJET REEL, UN CALCUL QUI SURVIT AU RECHARGEMENT
#
#   db/test/atelier_projet.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS ETABLIT
# --------------------------
# Le parcours PRODUIT, depuis les routes HTTP, contre un PostgreSQL reel:
#
#   1. un utilisateur connecte voit les projets de SON organisation;
#   2. il cree un projet (nom, reference, pays, date de reference);
#   3. il le selectionne;
#   4. il lance un calcul de flexion;
#   5. requete exacte, statut, version moteur, etat NDP, journal, resultats et
#      verifications sont enregistres ATOMIQUEMENT;
#   6. apres relecture complete, l'historique reapparait;
#   7. le calcul sauvegarde se rouvre avec les MEMES entrees et resultats.
#
# ET LA PROPRIETE QUI COMPTE AUTANT QUE LES SEPT: une autre organisation ne
# lit ni ne modifie ce projet. Le decor pose donc DEUX organisations disjointes
# et deux identites, chacune avec son jeton signe.
#
# EN QUOI IL DIFFERE DE `api_e2e.sh`
# ------------------------------------
# `api_e2e.sh` eprouve le chemin d'AUTORITE — proposer, approuver, consommer.
# Celui-ci eprouve le chemin de TRAVAIL — projets, calculs, historique. Les
# deux partagent l'authentification et la pose du decor, et rien d'autre: y
# ajouter un aiguillage obligerait a rejouer les controles d'autorite a chaque
# retouche de l'atelier.
#
# SANS PILOTE NI FASTAPI, IL REND 4 — NON EXECUTE. Une surface qu'on n'a pas pu
# exercer n'est pas une surface qui a tenu.
#
# Aucune identite reelle, aucun secret, aucune instance Supabase. Les cles RSA
# sont generees dans le processus de test et meurent avec lui.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: atelier_projet.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "atelier_projet.sh" || exit 2
harnais_verrou_prendre  "atelier_projet.sh" || exit $?
exiger_cluster_jetable  "atelier_projet.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "atelier_projet.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-atelier-${JETON}"
MANDAT="11111111-7777-7777-7777-777777777701:FICTIF-EMPREINTE-ATELIER-${JETON}"
RACINE_ID="11111111-7777-7777-7777-777777777701"
#: DEUX IDENTITES, DEUX ORGANISATIONS. C'est la seule facon d'eprouver
#: l'isolation: un seul acteur ne peut pas prouver qu'il est empeche d'aller
#: ailleurs, faute d'un ailleurs.
ACTEUR_A="22222222-7777-7777-7777-7777777777a1"
ACTEUR_B="33333333-7777-7777-7777-7777777777b1"
ORG_A="44444444-7777-7777-7777-7777777777c1"
ORG_B="55555555-7777-7777-7777-7777777777d1"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

NETTOYAGE_KO=0
sortie_propre() {
  local r
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
  harnais_postcondition_nettoyage "atelier_projet.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

MANQUANTS=""
python3 -c "import psycopg2" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS psycopg2"
python3 -c "import fastapi"  >/dev/null 2>&1 || MANQUANTS="$MANQUANTS fastapi"
python3 -c "import jwt"      >/dev/null 2>&1 || MANQUANTS="$MANQUANTS pyjwt"
python3 -c "import eurostruct_api" >/dev/null 2>&1 || MANQUANTS="$MANQUANTS eurostruct-api"
python3 -c "from fastapi.testclient import TestClient" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS httpx(TestClient)"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: atelier_projet.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Le parcours de travail ne peut pas etre eprouve, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi

echo "    tranche applicative: l'atelier — projets, calculs, historique"

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

# ---------------------------------------------------------------------
# LE DECOR METIER: deux organisations disjointes, deux membres, un jeu
# d'annexes nationales publie.
#
# IL EST POSE PAR LE PROPRIETAIRE DE LA BASE, PAS PAR LE PRODUIT. Creer une
# organisation et enroler ses membres releve de l'administration du compte;
# aucune route du produit ne le fait, et lui en donner une ici ferait passer
# pour eprouve un chemin qui n'existe pas.
# ---------------------------------------------------------------------
admb -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id) values ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_B')
on conflict do nothing;
insert into organizations (id, name, country) values
  ('$ORG_A', 'FICTIF Bureau A', 'BE'),
  ('$ORG_B', 'FICTIF Bureau B', 'BE')
on conflict do nothing;
insert into organization_members (org_id, user_id, role) values
  ('$ORG_A', '$ACTEUR_A', 'engineer'),
  ('$ORG_B', '$ACTEUR_B', 'engineer')
on conflict do nothing;
-- UNE ANNEXE NATIONALE EN VIGUEUR, sans quoi la creation de projet refuse —
-- et elle a raison de refuser: un projet citerait un referentiel qui n'existe
-- pas a sa date de reference. Le decor pose donc le DOCUMENT, pas ses valeurs:
-- aucun parametre n'est insere, aucune valeur normative n'est inventee, et le
-- mode strict continue de refuser faute de confirmation.
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL

# LE DECOR EST CONSTATE, PAS SUPPOSE. Les heredocs ci-dessus sont muets par
# construction (`>/dev/null 2>&1`): une insertion refusee ne se verrait qu'a
# la premiere assertion du parcours, sous la forme d'un echec fonctionnel sans
# rapport avec sa cause. Mesure du jour: « aucune annexe nationale en vigueur »
# sur toute creation de projet, pour un decor qu'on croyait pose.
NB_ORG=$(q "select count(*) from organizations")
NB_MEM=$(q "select count(*) from organization_members")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_ORG" != "2" || "$NB_MEM" != "2" || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor metier n'est pas pose." >&2
  echo "             organisations=$NB_ORG membres=$NB_MEM annexes_BE=$NB_ANX" >&2
  exit 1
fi

# LE PARCOURS LUI-MEME. La DSN ne transite QUE par l'environnement du
# sous-processus: elle n'apparait ni en argument, ni dans un fichier, ni dans
# la sortie. `ps` ne la montrera pas.
export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
# UNE SECONDE DSN, D'OBSERVATION SEULEMENT. Le login de service n'a aucun
# privilege de table: prouver qu'une transaction interrompue n'a RIEN laisse
# demande de regarder les tables, ce que le service ne peut pas faire. Cette
# DSN sert au constat, jamais au parcours: aucune route ne la voit.
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_ATELIER_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_ATELIER_ACTEUR_B="$ACTEUR_B"
export EUROSTRUCT_ATELIER_ORG_A="$ORG_A"
export EUROSTRUCT_ATELIER_ORG_B="$ORG_B"

python3 -m pytest "$RACINE/api/tests/test_atelier_postgres.py" -q \
        -p no:cacheprovider --no-header
CODE=$?
unset EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS \
      EUROSTRUCT_ATELIER_ACTEUR_A EUROSTRUCT_ATELIER_ACTEUR_B \
      EUROSTRUCT_ATELIER_ORG_A EUROSTRUCT_ATELIER_ORG_B

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Un projet reel, un calcul enregistre atomiquement,"
  echo " un historique qui survit, et une organisation"
  echo " voisine qui ne voit rien."
  echo "================================================="
fi
exit $CODE
