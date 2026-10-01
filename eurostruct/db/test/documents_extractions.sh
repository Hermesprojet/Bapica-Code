#!/usr/bin/env bash
#
# EUROSTRUCT — UN PLAN DEPOSE, DES VALEURS PROPOSEES, UNE PERSONNE QUI DECIDE,
#              UN CALCUL QUI NE CROIT QUE LA DECISION ENREGISTREE
#
#   db/test/documents_extractions.sh <prefixe-de-base-jetable>
#
# CE QUE CE HARNAIS ETABLIT, DEPUIS LES ROUTES HTTP, CONTRE UN POSTGRESQL REEL
# ---------------------------------------------------------------------------
#   1. un PDF depose est conserve (octets relus, empreinte), inscrit, analyse,
#      et ses valeurs proposees — toutes « proposed », toutes tracees;
#   2. les memes octets ne font pas un second document; un format inconnu,
#      un lecteur, une autre organisation ne deposent rien — et rien n'est
#      ecrit dans le magasin;
#   3. un DWG est conserve, non lu, et peut etre analyse a nouveau; un
#      document qui porte des propositions, non;
#   4. confirmer, corriger, rejeter: le nom vient de l'adhesion, la date du
#      serveur, la decision est definitive; sans nom, pas de decision;
#   5. le preremplissage rend les seules valeurs DECIDEES, dans l'unite du
#      champ, avec leur provenance;
#   6. un calcul n'accepte une provenance que si elle designe une decision de
#      CE projet, de la bonne categorie et de la MEME valeur — et il la
#      reecrit depuis la base; sinon 422, et aucune ligne n'est ecrite;
#   7. le rapprochement voit les pieces deposees: aucun orphelin, aucun absent;
#   8. un DXF qui n'ecrit aucune portee donne son modele structurel (0029:
#      propositions « geometrie » admises); une portee mesuree sur le dessin,
#      decidee, entre dans le calcul avec sa provenance.
#
# CINQ IDENTITES, CHACUNE POUR UN REFUS PRECIS: A ingenieur nomme, V
# validateur nomme, W lecteur, N ingenieur SANS nom enregistre, B ingenieur
# d'une autre organisation. Toutes FICTIVES; les cles RSA naissent et meurent
# dans le processus de test. Aucun plan reel: les documents sont fabriques par
# les tests du module d'extraction.
#
# SANS PILOTE, FASTAPI OU MODULE D'EXTRACTION, IL REND 4 — NON EXECUTE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: documents_extractions.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "documents_extractions.sh" || exit 2
harnais_verrou_prendre  "documents_extractions.sh" || exit $?
exiger_cluster_jetable  "documents_extractions.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)
exiger_roles_absents "documents_extractions.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-documents-${JETON}"
MANDAT="11111111-9999-9999-9999-999999999901:FICTIF-EMPREINTE-DOCUMENTS-${JETON}"
RACINE_ID="11111111-9999-9999-9999-999999999901"
ACTEUR_A="22222222-9999-9999-9999-99999999aaa1"
ACTEUR_V="22222222-9999-9999-9999-99999999bbb1"
ACTEUR_W="22222222-9999-9999-9999-99999999ccc1"
ACTEUR_N="22222222-9999-9999-9999-99999999eee1"
ACTEUR_B="33333333-9999-9999-9999-99999999fff1"
ORG_A="44444444-9999-9999-9999-9999999999c1"
ORG_B="55555555-9999-9999-9999-9999999999e1"

#: LE MAGASIN D'OBJETS DU HARNAIS, cree par `mktemp -d`: un objet dont le
#: harnais PROUVE la creation, detruit a la sortie et par lui seul.
MAGASIN=""

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
  harnais_postcondition_nettoyage "documents_extractions.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  # LE REPERTOIRE CREE PAR CE HARNAIS, ET LUI SEUL.
  if [[ -n "$MAGASIN" && -d "$MAGASIN" && "$MAGASIN" == /tmp/* ]]; then
    rm -rf -- "$MAGASIN" || NETTOYAGE_KO=1
  fi
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
python3 -c "import eurostruct_extraction" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS eurostruct-extraction"
python3 -c "from fastapi.testclient import TestClient" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS httpx(TestClient)"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: documents_extractions.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       La lecture des plans ne peut pas etre eprouvee, et une" >&2
  echo "       surface non executee n'est pas verte." >&2
  echo "       Installer: pip install -e eurostruct/extraction -e eurostruct/api" >&2
  exit 4
fi

echo "    lecture des plans: depot, analyse, revue, decision, report, calcul"

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
# LE DECOR METIER: deux organisations disjointes, cinq membres, un jeu
# d'annexes nationales publie.
#
# IL EST POSE PAR LE PROPRIETAIRE DE LA BASE, PAS PAR LE PRODUIT. Creer une
# organisation et enroler ses membres releve de l'administration du compte;
# aucune route du produit ne le fait, et lui en donner une ici ferait passer
# pour eprouve un chemin qui n'existe pas.
# ---------------------------------------------------------------------
DECOR_SORTIE="$(admb -v ON_ERROR_STOP=1 2>&1 <<SQL
insert into auth.users (id) values ('$RACINE_ID'), ('$ACTEUR_A'), ('$ACTEUR_V'),
  ('$ACTEUR_W'), ('$ACTEUR_N'), ('$ACTEUR_B')
on conflict do nothing;
insert into organizations (id, name, country) values
  ('$ORG_A', 'FICTIF Bureau A', 'BE'),
  ('$ORG_B', 'FICTIF Bureau B', 'BE')
on conflict do nothing;
-- LE NOM EST POSE PAR L'ORGANISATION; la primitive de decision le DERIVE
-- d'ici et n'en accepte aucun du corps HTTP. N n'en a pas: c'est le cas
-- eprouve.
insert into organization_members (org_id, user_id, role, display_name) values
  ('$ORG_A', '$ACTEUR_A', 'engineer', 'FICTIF Ing. A'),
  ('$ORG_A', '$ACTEUR_V', 'validating_engineer', 'FICTIF Ing. V'),
  ('$ORG_A', '$ACTEUR_W', 'viewer', 'FICTIF Lecteur W'),
  ('$ORG_A', '$ACTEUR_N', 'engineer', null),
  ('$ORG_B', '$ACTEUR_B', 'engineer', 'FICTIF Ing. B')
on conflict do nothing;
-- UNE ANNEXE NATIONALE EN VIGUEUR, sans quoi la creation de projet refuse. Le
-- decor pose le DOCUMENT, jamais ses valeurs: aucun parametre n'est insere.
insert into national_annexes (country_code, standard_family, part, reference,
                              edition, effective_from, source_official)
values ('BE', 'EN 1992', '1-1', 'FICTIF NBN EN 1992-1-1 ANB',
        'FICTIF — edition de decor', date '2010-08-01',
        'FICTIF — organisme de decor')
on conflict do nothing;
SQL
)"
if grep -q "ERROR" <<<"$DECOR_SORTIE"; then
  echo "      ECHEC: la pose du decor metier a ete refusee:" >&2
  grep -m3 "ERROR\|DETAIL" <<<"$DECOR_SORTIE" | cut -c1-200 >&2
  exit 1
fi

# LE DECOR EST CONSTATE, PAS SUPPOSE.
NB_MEM=$(q "select count(*) from organization_members")
NB_NOM=$(q "select count(*) from organization_members where display_name is not null")
NB_ANX=$(q "select count(*) from national_annexes where country_code = 'BE'")
if [[ "$NB_MEM" != "5" || "$NB_NOM" != "4" || "$NB_ANX" == "0" ]]; then
  echo "      ECHEC: le decor metier n'est pas pose (membres=$NB_MEM nommes=$NB_NOM annexes_BE=$NB_ANX)." >&2
  exit 1
fi

MAGASIN="$(mktemp -d "/tmp/esc-pieces-${JETON}-XXXXXX")" || {
  echo "      ECHEC: magasin d'objets non cree." >&2; exit 1; }

# LES DSN NE TRANSITENT QUE PAR L'ENVIRONNEMENT DU SOUS-PROCESSUS: ni argument,
# ni fichier, ni sortie. La seconde sert au CONSTAT (le login de service n'a
# aucun privilege de table), jamais au parcours.
export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_BUILD_SHA="FICTIF-build-${JETON}"
export EUROSTRUCT_STORAGE_DIR="$MAGASIN"
export EUROSTRUCT_DOCUMENTS_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_DOCUMENTS_ACTEUR_V="$ACTEUR_V"
export EUROSTRUCT_DOCUMENTS_ACTEUR_W="$ACTEUR_W"
export EUROSTRUCT_DOCUMENTS_ACTEUR_N="$ACTEUR_N"
export EUROSTRUCT_DOCUMENTS_ACTEUR_B="$ACTEUR_B"

python3 -m pytest "$RACINE/api/tests/test_documents_postgres.py" \
        -p no:cacheprovider --no-header
CODE=$?
unset EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS EUROSTRUCT_STORAGE_DIR \
      EUROSTRUCT_DOCUMENTS_ACTEUR_A EUROSTRUCT_DOCUMENTS_ACTEUR_V \
      EUROSTRUCT_DOCUMENTS_ACTEUR_W EUROSTRUCT_DOCUMENTS_ACTEUR_N \
      EUROSTRUCT_DOCUMENTS_ACTEUR_B

# LE MAGASIN, CONSTATE HORS DU PROCESSUS DE TEST: autant de fichiers sous
# pieces/ que d'empreintes distinctes inscrites, et rien d'autre. Un depot
# refuse (format, role, organisation) n'a laisse aucun octet.
if [[ $CODE -eq 0 ]]; then
  NB_FICHIERS=$(find "$MAGASIN" -type f -path '*/pieces/*' 2>/dev/null | wc -l)
  NB_AUTRES=$(find "$MAGASIN" -type f ! -path '*/pieces/*' 2>/dev/null | wc -l)
  NB_EMPREINTES=$(q "select count(distinct storage_path) from documents")
  if [[ "$NB_FICHIERS" != "$NB_EMPREINTES" || "$NB_AUTRES" != "0" ]]; then
    echo "      ECHEC: le magasin ne correspond pas aux pieces inscrites." >&2
    echo "             fichiers pieces=$NB_FICHIERS autres=$NB_AUTRES chemins inscrits=$NB_EMPREINTES" >&2
    CODE=1
  else
    echo "      $NB_FICHIERS piece(s) sur disque, autant de chemins inscrits."
  fi
fi

if [[ $CODE -eq 0 ]]; then
  echo ""
  echo "================================================="
  echo " Un plan depose, des valeurs proposees et tracees,"
  echo " une personne nommee qui decide, et un calcul qui"
  echo " ne croit que la decision enregistree."
  echo "================================================="
fi
exit $CODE
