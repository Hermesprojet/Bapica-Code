#!/usr/bin/env bash
#
# EUROSTRUCT — LES OCTETS D'UN LIVRABLE DANS UN MAGASIN OBJET REEL
#
#   db/test/stockage_s3.sh <prefixe-de-base-jetable>
#
# LE DEFAUT PRODUIT QUE CE HARNAIS FERME
# ----------------------------------------
# Les livrables n'existaient que sur le DISQUE LOCAL du conteneur d'API. Un
# volume nomme repoussait le probleme d'un cran; il ne le fermait pas. Deux
# instances d'API derriere un repartiteur ne partagent pas ce disque: la
# moitie des telechargements aurait rendu 503 sur des livrables parfaitement
# enregistres. Et un document conserve dix ans au titre de la responsabilite
# decennale ne peut pas dependre d'un disque de machine.
#
# LES DIX ETAPES, DANS CET ORDRE
# --------------------------------
#   1. UN VOLUME NEUF — cree par ce harnais, et constate vide.
#   2. LE COMPARTIMENT — cree par NOTRE PROPRE CLIENT S3, pas par un outil
#      tiers: c'est le code du produit qui doit savoir parler ce protocole.
#   3. LE DEPOT — par les routes reelles du produit, depuis un calcul strict.
#   4. L'ARRET ET LE REDEMARRAGE — le processus d'API est DETRUIT, et le
#      conteneur MinIO redemarre. Plus une connexion, plus un cache.
#   5. LE TELECHARGEMENT — dans un processus NEUF, qui ne cree rien.
#   6. L'EMPREINTE — celle des octets servis, comparee a celle enregistree
#      avant le redemarrage.
#   7. LE REFUS INTER-ORGANISATIONS — le temoin lit l'objet dans le
#      compartiment, et le membre du bureau voisin est refuse. C'est ce qui
#      distingue « on ne vous le donne pas » de « il n'y est pas ».
#   8. L'ENUMERATION — `ListObjectsV2`, paginee et signee, contre le vrai
#      serveur. Le prefixe declare est retire des chemins rendus: sans cela,
#      un rapprochement declarerait tout le compartiment orphelin des qu'un
#      prefixe est configure — c'est-a-dire en production.
#   9. LE RAPPROCHEMENT — la base et le compartiment s'accordent; puis un
#      orphelin est INJECTE, l'outil le nomme, et l'objet est TOUJOURS LA.
#      Un rapprochement qui ne verrait jamais rien serait vert lui aussi.
#  10. LA DESTRUCTION — conteneur et volume, tous deux crees ici, et rien
#      d'autre. Aucun nettoyage par motif large.
#
# CE QUI EST ETABLI, ET CE QUI NE L'EST PAS
# -------------------------------------------
# ETABLI: le protocole S3 tel que MinIO l'implemente — signature SigV4,
# depot, relecture, flux, taille, idempotence, refus d'ecrasement divergent.
#
# NON ETABLI: AWS S3, Supabase Storage, ou tout autre fournisseur. Aucun n'a
# ete joint depuis ce depot. `SUPABASE_UNVERIFIED` reste vrai.
#
# AUCUN SECRET REEL N'EST UTILISE. Les identifiants sont FICTIFS, generes pour
# cette execution, et meurent avec le conteneur.
#
# SANS DOCKER, SANS PILOTE OU SANS FASTAPI, IL REND 4 — NON EXECUTE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
HARNAIS_SCEAU="$DB_DIR/control_plane/0001_normative_seal.sql"

# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# shellcheck source=../apply_migration.sh
source "$DB_DIR/apply_migration.sh"

PREFIXE="${1:?usage: stockage_s3.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "stockage_s3.sh" || exit 2
harnais_verrou_prendre  "stockage_s3.sh" || exit $?
exiger_cluster_jetable  "stockage_s3.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "stockage_s3.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-s3-${JETON}"
MANDAT="11111111-9999-9999-9999-999999999901:FICTIF-EMPREINTE-S3-${JETON}"
RACINE_ID="11111111-9999-9999-9999-999999999901"
ACTEUR_A="22222222-9999-9999-9999-99999999aaa1"
ACTEUR_V="22222222-9999-9999-9999-99999999bbb1"
ACTEUR_W="22222222-9999-9999-9999-99999999ccc1"
ACTEUR_D="22222222-9999-9999-9999-99999999ddd1"
ACTEUR_N="22222222-9999-9999-9999-99999999eee1"
ACTEUR_B="33333333-9999-9999-9999-99999999fff1"
ORG_A="44444444-9999-9999-9999-9999999999c1"
ORG_B="55555555-9999-9999-9999-9999999999e1"

#: LE MAGASIN OBJET DU HARNAIS. Conteneur, volume et port sont derives du
#: jeton: deux executions concurrentes ne se marchent pas dessus, et chaque
#: objet detruit a la sortie est un objet dont ce harnais PROUVE la creation.
CONTENEUR="esc-s3-${JETON}"
VOLUME="esc-s3-${JETON}"
COMPARTIMENT="esc-livrables-${JETON}"
PREFIXE_S3="livrables"
#: DES IDENTIFIANTS FICTIFS, JAMAIS DES SECRETS REELS. Ils naissent ici et
#: meurent avec le conteneur; aucun n'est ecrit dans le depot, et aucun ne
#: passe par `argv` d'un programme observable — ils voyagent par
#: l'environnement, et le conteneur les recoit par `--env-file`.
CLE_S3="FICTIFMINIO${JETON^^}"
SECRET_S3="FICTIFSECRET${JETON^^}0123456789"
#: LE PORT. Choisi haut, et VERIFIE LIBRE plus bas: supposer un port libre est
#: la facon la plus sure de joindre le service de quelqu'un d'autre.
PORT_S3="${EUROSTRUCT_S3_PORT_HARNAIS:-9187}"
#: L'IMAGE EST EPINGLEE, ET C'EST LA MEME QUE CELLE DE `compose.yaml`. Avec
#: `latest`, le magasin change d'une execution a l'autre sans qu'un seul
#: fichier du depot ne bouge: un harnais qui verdit ou rougit selon le jour
#: n'etablit rien. La variable existe pour eprouver une autre version
#: DELIBEREMENT, pas pour deriver.
IMAGE_MINIO="${EUROSTRUCT_MINIO_IMAGE:-minio/minio:RELEASE.2025-09-07T16-13-09Z}"

adm()  { psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
q()    { admb -tAc "$1" 2>&1 | tr -d ' '; }

TMP=""
CONTENEUR_CREE=0
VOLUME_CREE=0
NETTOYAGE_KO=0

sortie_propre() {
  local r
  # ETAPE 8 — LA DESTRUCTION, ET SEULEMENT DE CE QUI A ETE CREE ICI.
  if [[ $CONTENEUR_CREE -eq 1 ]]; then
    docker rm -f "$CONTENEUR" >/dev/null 2>&1 || NETTOYAGE_KO=1
  fi
  if [[ $VOLUME_CREE -eq 1 ]]; then
    # LE VOLUME EMPORTE LES OBJETS. C'est le seul chemin de suppression du
    # magasin dans tout ce depot: le client S3 du produit n'a AUCUNE methode
    # de suppression, et ce n'est pas un oubli (voir docs/STOCKAGE.md).
    docker volume rm "$VOLUME" >/dev/null 2>&1 || NETTOYAGE_KO=1
  fi
  if [[ $CONTENEUR_CREE -eq 1 ]] && docker ps -a --format '{{.Names}}' 2>/dev/null \
       | grep -qx "$CONTENEUR"; then
    echo "      ECHEC: le conteneur $CONTENEUR survit au harnais." >&2
    NETTOYAGE_KO=1
  fi
  if [[ $VOLUME_CREE -eq 1 ]] && docker volume ls --format '{{.Name}}' 2>/dev/null \
       | grep -qx "$VOLUME"; then
    echo "      ECHEC: le volume $VOLUME survit au harnais." >&2
    NETTOYAGE_KO=1
  fi

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
  harnais_postcondition_nettoyage "stockage_s3.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC" \
    || NETTOYAGE_KO=1
  if [[ -n "$TMP" && -d "$TMP" && "$TMP" == /tmp/* ]]; then
    rm -rf -- "$TMP" || NETTOYAGE_KO=1
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
python3 -c "from fastapi.testclient import TestClient" >/dev/null 2>&1 \
  || MANQUANTS="$MANQUANTS httpx(TestClient)"
if [[ -n "$MANQUANTS" ]]; then
  echo "NON EXECUTE: stockage_s3.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi
command -v docker >/dev/null 2>&1 || {
  echo "NON EXECUTE: stockage_s3.sh — docker absent." >&2
  echo "       Le magasin objet doit etre REEL: ni faux client, ni" >&2
  echo "       repertoire deguise en compartiment." >&2
  exit 4; }
docker info >/dev/null 2>&1 || {
  echo "NON EXECUTE: stockage_s3.sh — le demon docker ne repond pas." >&2
  exit 4; }

echo "    tranche applicative: le magasin objet — depot, redemarrage, relecture"

TMP="$(mktemp -d "/tmp/esc-s3-${JETON}-XXXXXX")" || {
  echo "      ECHEC: repertoire de travail non cree." >&2; exit 1; }
ETAT="$TMP/etat.json"
: > "$ETAT"
#: LES OCTETS EXACTS SERVIS PAR LA ROUTE, ecrits par la phase 1 et relus par le
#: harnais. Ils ne quittent pas le repertoire jetable.
DOCUMENT="$TMP/document-servi.bin"
: > "$DOCUMENT"
#: LE DISQUE TEMOIN. Vide, et il doit le RESTER: c'est la preuve qu'aucun
#: repli silencieux du magasin objet vers le disque local n'a lieu.
DISQUE_TEMOIN="$TMP/disque-temoin"
mkdir -p "$DISQUE_TEMOIN"

# ===========================================================================
# ETAPE 1 — UN VOLUME NEUF, ET UN SERVEUR QUI S'Y ADOSSE
# ===========================================================================
if curl -fsS --max-time 2 -o /dev/null "http://127.0.0.1:$PORT_S3/minio/health/live" 2>/dev/null; then
  echo "      ECHEC: le port $PORT_S3 repond deja; on ne s'y branche pas." >&2
  exit 2
fi
if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -qx "$VOLUME"; then
  echo "      ECHEC: le volume $VOLUME existe deja: il ne serait pas neuf." >&2
  exit 2
fi
docker volume create "$VOLUME" >/dev/null 2>&1 || {
  echo "      ECHEC: volume $VOLUME non cree." >&2; exit 1; }
VOLUME_CREE=1

#: LES IDENTIFIANTS PASSENT PAR UN FICHIER D'ENVIRONNEMENT, PAS PAR `argv`.
#: `docker run -e CLE=valeur` inscrit la valeur dans la ligne de commande, que
#: tout le monde lit dans `ps`. Le fichier est en 0600, dans un repertoire
#: jetable, et il part avec lui.
ENVF="$TMP/minio.env"
: > "$ENVF"
chmod 600 "$ENVF"
cat > "$ENVF" <<ENVEOF
MINIO_ROOT_USER=$CLE_S3
MINIO_ROOT_PASSWORD=$SECRET_S3
ENVEOF

docker run -d --name "$CONTENEUR" \
  --env-file "$ENVF" \
  -v "$VOLUME:/data" \
  -p "127.0.0.1:$PORT_S3:9000" \
  "$IMAGE_MINIO" server /data >/dev/null 2>&1 || {
    echo "      ECHEC: MinIO n'a pas demarre." >&2
    echo "             (image absente? 'docker pull $IMAGE_MINIO')" >&2
    exit 1; }
CONTENEUR_CREE=1

attendre_minio() {   # attendre_minio <secondes>
  local reste="$1"
  while (( reste > 0 )); do
    if curl -fsS --max-time 2 -o /dev/null \
         "http://127.0.0.1:$PORT_S3/minio/health/live" 2>/dev/null; then
      return 0
    fi
    # LA SONDE EST UNE INTERROGATION DU SERVICE, jamais une recherche de
    # processus par motif: `pgrep -f` attrape le harnais lui-meme.
    sleep 1
    reste=$(( reste - 1 ))
  done
  return 1
}
if ! attendre_minio 60; then
  echo "      ECHEC: MinIO n'a pas repondu sur 127.0.0.1:$PORT_S3." >&2
  docker logs "$CONTENEUR" 2>&1 | tail -5 >&2
  exit 1
fi

# LE VOLUME EST NEUF, ET ON LE CONSTATE. MinIO pose son propre `.minio.sys`;
# tout le reste doit etre absent, et c'est ce qui rend l'etape 2 signifiante.
RESIDUS="$(docker exec "$CONTENEUR" sh -c \
  'ls -A /data 2>/dev/null | grep -v "^\.minio\.sys$" | head -5' 2>/dev/null)"
if [[ -n "$RESIDUS" ]]; then
  echo "      ECHEC: le volume n'est pas neuf; il porte deja: $RESIDUS" >&2
  exit 1
fi
echo "      1/10 volume neuf, MinIO en ecoute sur 127.0.0.1:$PORT_S3"

# ===========================================================================
# ETAPE 2 — LE COMPARTIMENT, CREE PAR LE CLIENT S3 DU PRODUIT
# ===========================================================================
# ON N'UTILISE NI `mc`, NI `aws`, NI `boto3`. Si notre propre signature SigV4
# ne sait pas creer un compartiment, elle ne saura pas y deposer un livrable —
# et un outil tiers qui reussit la ou notre code echoue ne prouve rien de
# notre code.
export EUROSTRUCT_S3_ENDPOINT="http://127.0.0.1:$PORT_S3"
export EUROSTRUCT_S3_REGION="us-east-1"
export EUROSTRUCT_S3_BUCKET="$COMPARTIMENT"
export EUROSTRUCT_S3_ACCESS_KEY_ID="$CLE_S3"
export EUROSTRUCT_S3_SECRET_ACCESS_KEY="$SECRET_S3"
export EUROSTRUCT_S3_PREFIX="$PREFIXE_S3"
export EUROSTRUCT_S3_PATH_STYLE="oui"

if ! python3 - <<'FINPY'
import os, sys
from eurostruct_api.s3 import ClientS3, ReglagesS3

client = ClientS3(ReglagesS3(
    endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"],
    region=os.environ["EUROSTRUCT_S3_REGION"],
    bucket=os.environ["EUROSTRUCT_S3_BUCKET"],
    access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
    secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
    prefixe=os.environ["EUROSTRUCT_S3_PREFIX"],
))
try:
    client.creer_compartiment()
except Exception as cause:            # noqa: BLE001 — le harnais rapporte
    # LE MESSAGE NE PORTE NI CLE NI SECRET: `S3Refuse` est construite pour
    # cela, et un `print` de l'exception ne doit pas le defaire.
    print(f"creation refusee: {cause}", file=sys.stderr)
    raise SystemExit(1)
FINPY
then
  echo "      ECHEC: le compartiment n'a pas ete cree par notre client S3." >&2
  exit 1
fi

# LE CONSTAT EST FAIT DE L'EXTERIEUR, sur le volume. Une reponse 200 dit ce
# que le serveur repond; le repertoire dit ce qui existe.
if ! docker exec "$CONTENEUR" test -d "/data/$COMPARTIMENT" 2>/dev/null; then
  echo "      ECHEC: /data/$COMPARTIMENT n'existe pas sur le volume." >&2
  exit 1
fi
echo "      2/10 compartiment « $COMPARTIMENT » cree par le client du produit"

# ===========================================================================
# LE DECOR: base deployee, six adhesions, racine d'autorite, quatre-yeux.
# ===========================================================================
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
    esc_diag_rapporter "decor / $(basename "$f")" "$ESC_MIGRATION_SORTIE"
    exit 1
  fi
done
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$M"))" >/dev/null 2>&1
ETAT_BASE=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
if [[ "$ETAT_BASE" != "ACTIVE" ]]; then
  echo "      ECHEC: la base n'est pas ACTIVE ($ETAT_BASE)" >&2
  exit 1
fi
ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1

DECOR_SORTIE="$(admb -v ON_ERROR_STOP=1 2>&1 <<SQL
insert into auth.users (id) values
  ('$RACINE_ID'),('$ACTEUR_A'),('$ACTEUR_V'),('$ACTEUR_W'),
  ('$ACTEUR_D'),('$ACTEUR_N'),('$ACTEUR_B')
on conflict do nothing;
insert into organizations (id, name, country) values
  ('$ORG_A', 'FICTIF Bureau S3 A', 'BE'),
  ('$ORG_B', 'FICTIF Bureau S3 B', 'BE')
on conflict do nothing;
insert into organization_members
  (org_id, user_id, role, display_name, professional_id) values
  ('$ORG_A', '$ACTEUR_A', 'engineer', 'FICTIF Ing. A', null),
  ('$ORG_A', '$ACTEUR_V', 'validating_engineer',
   'FICTIF Ing. V (compte de test)', 'FICTIF-ORDRE-S3-1'),
  ('$ORG_A', '$ACTEUR_W', 'viewer', 'FICTIF Lecteur W', null),
  ('$ORG_A', '$ACTEUR_D', 'validating_engineer',
   'FICTIF Ing. D (revoque)', 'FICTIF-ORDRE-S3-2'),
  ('$ORG_A', '$ACTEUR_N', 'validating_engineer', null, 'FICTIF-ORDRE-S3-3'),
  ('$ORG_B', '$ACTEUR_B', 'engineer', 'FICTIF Ing. B', null)
on conflict do nothing;
update organization_members
   set is_active = false, deactivated_at = now() - interval '1 day'
 where org_id = '$ORG_A' and user_id = '$ACTEUR_D';
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
  grep -m3 "ERROR\|DETAIL\|LINE" <<<"$DECOR_SORTIE" | cut -c1-200 >&2
  exit 1
fi
NB_MEM=$(q "select count(*) from organization_members")
if [[ "$NB_MEM" != "6" ]]; then
  echo "      ECHEC: le decor metier n'est pas pose (membres=$NB_MEM)." >&2
  exit 1
fi

ctl -tAc "select bootstrap_normative_administrator(
            '$RACINE_ID'::uuid, 'FICTIF racine', 'FICTIF racine s3')" \
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
             'EN 1992', '1-1', \$\$$EDITION_BE\$\$, '$2', '$GR')" -d "$BASE" >/dev/null 2>&1
  q "select id from normative_authorisation_grants where reason = '$2'"
}
GA="$(octroyer "$ACTEUR_A" 'FICTIF autorite de A (s3)')"
GV="$(octroyer "$ACTEUR_V" 'FICTIF autorite de V (s3)')"
if [[ ! "$GA" =~ ^[0-9a-f-]{36}$ || ! "$GV" =~ ^[0-9a-f-]{36}$ ]]; then
  echo "      ECHEC: les habilitations du quatre-yeux n'ont pas ete creees." >&2
  exit 1
fi

# ===========================================================================
# ETAPE 3 — LE DEPOT, PAR LES ROUTES REELLES
# ===========================================================================
# `EUROSTRUCT_STORAGE_BACKEND=s3` ET `EUROSTRUCT_STORAGE_DIR` POINTE SUR UN
# REPERTOIRE VIDE. Les deux ensemble, et c'est deliberé: si le produit
# retombait sur le disque local, un fichier y apparaitrait, et les cas le
# constatent. Un repertoire ABSENT ne prouverait rien — il ferait echouer le
# repli au lieu de le reveler.
export EUROSTRUCT_STORAGE_BACKEND="s3"
export EUROSTRUCT_STORAGE_DIR="$DISQUE_TEMOIN"
export EUROSTRUCT_S3_ETAT="$ETAT"
export EUROSTRUCT_S3_DOCUMENT="$DOCUMENT"
export EUROSTRUCT_E2E_DSN="dbname=$BASE user=$SVC password=$MDP host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_E2E_DSN_OBS="dbname=$BASE host=${PGHOST:-/var/run/postgresql}"
export EUROSTRUCT_BUILD_SHA="FICTIF-build-s3-${JETON}"
export EUROSTRUCT_LIVRABLE_ACTEUR_A="$ACTEUR_A"
export EUROSTRUCT_LIVRABLE_ACTEUR_V="$ACTEUR_V"
export EUROSTRUCT_LIVRABLE_ACTEUR_W="$ACTEUR_W"
export EUROSTRUCT_LIVRABLE_ACTEUR_D="$ACTEUR_D"
export EUROSTRUCT_LIVRABLE_ACTEUR_N="$ACTEUR_N"
export EUROSTRUCT_LIVRABLE_ACTEUR_B="$ACTEUR_B"
export EUROSTRUCT_LIVRABLE_ORG_A="$ORG_A"
export EUROSTRUCT_LIVRABLE_ORG_B="$ORG_B"

CIBLE_PYTEST="$RACINE/api/tests/test_stockage_s3.py"
python3 -m pytest "${CIBLE_PYTEST}::TestAvantRedemarrage" \
        -p no:cacheprovider --no-header -q
CODE=$?
if [[ $CODE -ne 0 ]]; then
  echo "      ECHEC: la phase de depot n'a pas abouti." >&2
  exit $CODE
fi

# LE CONSTAT EXTERNE: les octets sont-ils SUR LE VOLUME? On lit ce que la
# phase 1 a transmis, et on regarde le systeme de fichiers de MinIO — pas la
# reponse du serveur, pas notre propre client.
champ_etat() {   # champ_etat <nom>
  python3 -c 'import json,os,sys; sys.stdout.write(
      str(json.load(open(os.environ["EUROSTRUCT_S3_ETAT"]))[sys.argv[1]]))' "$1" \
    2>/dev/null
}
CHEMIN_OBJET="$(champ_etat storage_path)"
SHA_DEPOSE="$(champ_etat sha256)"
if [[ -z "$CHEMIN_OBJET" || ! "$SHA_DEPOSE" =~ ^[0-9a-f]{64}$ ]]; then
  echo "      ECHEC: la phase de depot n'a transmis ni chemin ni empreinte." >&2
  exit 1
fi
CHEMIN_VOLUME="/data/$COMPARTIMENT/$PREFIXE_S3/$CHEMIN_OBJET"

#: LE CONSTAT PASSE PAR `docker cp`, PAS PAR `docker exec`. L'image MinIO est
#: minimale: elle n'a ni `grep`, ni `sha256sum`, ni `find`. Supposer qu'un
#: conteneur porte les outils dont on a besoin est une facon sure de rendre un
#: harnais rouge pour une raison qui n'a rien a voir avec le produit.
constater_octets_sur_le_volume() {   # constater_octets_sur_le_volume <etape>
  local etape="$1" copie="$TMP/constat-$1"
  rm -rf -- "$copie"
  mkdir -p "$copie" || return 1
  if ! docker cp "$CONTENEUR:$CHEMIN_VOLUME" "$copie/objet" >/dev/null 2>&1; then
    echo "      ECHEC ($etape): rien a copier depuis $CHEMIN_VOLUME." >&2
    echo "             La ligne en base promettrait un document introuvable." >&2
    return 1
  fi
  #: LA RECHERCHE EST FAITE SUR LES OCTETS EXACTS QUE LA ROUTE A SERVIS, pas
  #: sur un extrait: MinIO ecrit un petit objet A L'INTERIEUR de `xl.meta` et
  #: un gros dans un `part.1`, et une inclusion litterale couvre les deux sans
  #: rien savoir de son format.
  python3 - "$copie" "$DOCUMENT" "$SHA_DEPOSE" <<'FINPY'
import hashlib, pathlib, sys

copie, document, attendue = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
octets = document.read_bytes()
reelle = hashlib.sha256(octets).hexdigest()
if reelle != attendue:
    print(f"les octets servis par la route hachent en {reelle}, "
          f"la base enregistre {attendue}.", file=sys.stderr)
    raise SystemExit(1)
for fichier in sorted(p for p in copie.rglob("*") if p.is_file()):
    if octets in fichier.read_bytes():
        print(f"{len(octets)} octets retrouves verbatim dans "
              f"{fichier.relative_to(copie)}")
        raise SystemExit(0)
print("les octets du document ne sont dans aucun fichier de l'objet copie.",
      file=sys.stderr)
raise SystemExit(1)
FINPY
}
if ! SORTIE_CONSTAT="$(constater_octets_sur_le_volume depot 2>&1)"; then
  echo "      ECHEC: les octets du document ne sont pas sur le volume." >&2
  echo "$SORTIE_CONSTAT" | sed 's/^/             /' >&2
  exit 1
fi
NB_LIGNES=$(q "select count(*) from deliverables")
NB_S3=$(q "select count(*) from deliverables where storage_backend = 's3'")
if [[ "$NB_LIGNES" == "0" || "$NB_LIGNES" != "$NB_S3" ]]; then
  echo "      ECHEC: $NB_LIGNES livrable(s), dont $NB_S3 dans le magasin objet." >&2
  exit 1
fi
# LE DISQUE LOCAL EST RESTE VIDE. Le constat est fait ICI AUSSI, hors du
# processus de test: un test qui verifie son propre repli par la meme
# abstraction que le produit ne regarde pas le systeme de fichiers.
NB_DISQUE=$(find "$DISQUE_TEMOIN" -type f 2>/dev/null | wc -l)
if [[ "$NB_DISQUE" -ne 0 ]]; then
  echo "      ECHEC: $NB_DISQUE fichier(s) sur le disque local alors que le" >&2
  echo "             magasin declare est objet: repli silencieux." >&2
  exit 1
fi
echo "      3/10 $NB_LIGNES livrable(s) deposes, objet present sur le volume"

# ===========================================================================
# ETAPE 4 — L'ARRET ET LE REDEMARRAGE
# ===========================================================================
# LE PROCESSUS D'API EST DEJA DETRUIT: `pytest` a rendu la main, et avec lui
# l'interpreteur, les connexions PostgreSQL, le client S3 et tout cache en
# memoire. C'est un arret franc, pas un rechargement a chaud.
#
# ET MinIO REDEMARRE AUSSI. Le volume est ce qui persiste, pas le processus:
# si les octets ne vivaient que dans la memoire du serveur, l'etape 5 serait
# rouge — et c'est exactement ce qu'un magasin simule aurait laisse passer.
docker restart "$CONTENEUR" >/dev/null 2>&1 || {
  echo "      ECHEC: MinIO n'a pas redemarre." >&2; exit 1; }
if ! attendre_minio 60; then
  echo "      ECHEC: MinIO n'a pas repondu apres redemarrage." >&2
  exit 1
fi
echo "      4/10 API arretee (processus detruit), MinIO redemarre"

# ===========================================================================
# ETAPES 5, 6 ET 7 — RELECTURE, EMPREINTE, CLOISONNEMENT
# ===========================================================================
python3 -m pytest "${CIBLE_PYTEST}::TestApresRedemarrage" \
        -p no:cacheprovider --no-header -q
CODE=$?
if [[ $CODE -ne 0 ]]; then
  echo "      ECHEC: la phase de relecture n'a pas abouti." >&2
  exit $CODE
fi

# ET LE CONSTAT EXTERNE, UNE SECONDE FOIS: le contenu est encore sur le volume
# APRES le redemarrage du serveur. Ni le produit ni le processus de test
# n'interviennent — on copie l'objet et on cherche les octets dedans.
if ! SORTIE_CONSTAT="$(constater_octets_sur_le_volume relecture 2>&1)"; then
  echo "      ECHEC: le contenu a disparu du volume apres redemarrage." >&2
  echo "$SORTIE_CONSTAT" | sed 's/^/             /' >&2
  exit 1
fi
echo "      5/10 memes octets servis apres redemarrage"
echo "      6/10 empreinte des octets servis = empreinte en base ($SHA_DEPOSE)"
echo "      7/10 le bureau voisin est refuse sur un objet pourtant present"
echo "      8/10 l'enumeration voit l'objet, prefixe declare retire"

# LE PROGRAMME LUI-MEME, PAS SEULEMENT SA FONCTION.
#
# Les cas ci-dessus appellent `rapprocher()`. Ils ne disent RIEN de la
# commande: ni qu'elle sait lire son DSN, ni qu'elle construit le magasin
# depuis l'environnement, ni surtout que son CODE DE SORTIE distingue « tout
# s'accorde » de « des ecarts existent ». Une supervision qui branche sur ce
# code merite mieux qu'une promesse.
#
# ON ATTEND 1, PAS 0: la phase precedente a injecte un orphelin, et le decor
# en portait deja un. Exiger 0 ici obligerait a nettoyer le magasin pour faire
# passer le harnais — c'est-a-dire a effacer exactement ce qu'on veut voir.
SORTIE_RAPPRO="$(EUROSTRUCT_RECONCILIATION_DSN="$EUROSTRUCT_E2E_DSN_OBS" \
                 python3 -m eurostruct_api.reconciliation --empreintes --json \
                 2>&1)"
CODE_RAPPRO=$?
if [[ $CODE_RAPPRO -ne 1 ]]; then
  echo "      ECHEC: le rapprochement devait rendre 1 (des orphelins" >&2
  echo "             existent), il a rendu $CODE_RAPPRO." >&2
  echo "$SORTIE_RAPPRO" | sed 's/^/             /' >&2
  exit 1
fi
if ! printf '%s' "$SORTIE_RAPPRO" | python3 -c '
import json, sys
rapport = json.load(sys.stdin)
comptes = rapport["comptes"]
absents = comptes["absent"]
divergents = comptes["divergent"]
assert absents == 0, "absent=%d" % absents
assert divergents == 0, "divergent=%d" % divergents
assert comptes["orphelin"] >= 1, "aucun orphelin nomme"
assert comptes["intact"] >= 1, "aucun livrable intact"
assert rapport["empreintes_verifiees"] is True
# LES CONSTATS `intact` NE SONT PAS RENDUS: un rapport de supervision qui
# listerait tout ce qui va bien serait illisible des le premier millier.
assert all(c["verdict"] != "intact" for c in rapport["constats"])
'; then
  echo "      ECHEC: le rapport JSON du rapprochement ne tient pas." >&2
  echo "$SORTIE_RAPPRO" | sed 's/^/             /' >&2
  exit 1
fi

echo "      9/10 rapprochement: aucun absent, aucun divergent, le livrable"
echo "           intact; un orphelin injecte est nomme, il est toujours la,"
echo "           et la commande rend 1 comme une supervision l'attend"

unset EUROSTRUCT_S3_ENDPOINT EUROSTRUCT_S3_REGION EUROSTRUCT_S3_BUCKET \
      EUROSTRUCT_S3_ACCESS_KEY_ID EUROSTRUCT_S3_SECRET_ACCESS_KEY \
      EUROSTRUCT_S3_PREFIX EUROSTRUCT_S3_PATH_STYLE EUROSTRUCT_S3_ETAT \
      EUROSTRUCT_S3_DOCUMENT \
      EUROSTRUCT_STORAGE_BACKEND EUROSTRUCT_STORAGE_DIR \
      EUROSTRUCT_E2E_DSN EUROSTRUCT_E2E_DSN_OBS \
      EUROSTRUCT_LIVRABLE_ACTEUR_A EUROSTRUCT_LIVRABLE_ACTEUR_V \
      EUROSTRUCT_LIVRABLE_ACTEUR_W EUROSTRUCT_LIVRABLE_ACTEUR_D \
      EUROSTRUCT_LIVRABLE_ACTEUR_N EUROSTRUCT_LIVRABLE_ACTEUR_B \
      EUROSTRUCT_LIVRABLE_ORG_A EUROSTRUCT_LIVRABLE_ORG_B

echo "      10/10 destruction du conteneur et du volume (a la sortie)"
echo ""
echo "================================================="
echo " Un volume neuf, un compartiment cree par notre"
echo " propre signature, un livrable depose par les"
echo " routes, une API detruite, un serveur redemarre,"
echo " et les memes octets — a l'octet pres."
echo ""
echo " Cela etablit le PROTOCOLE S3 tel que MinIO"
echo " l'implemente. Ni AWS, ni Supabase Storage n'ont"
echo " ete joints: SUPABASE_UNVERIFIED reste vrai."
echo "================================================="
exit 0
