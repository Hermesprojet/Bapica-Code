#!/usr/bin/env bash
#
# EUROSTRUCT — UN LIVRABLE SURVIT-IL A LA PERTE DES DEUX MOITIES ?
#
#   db/test/sauvegarde_restauration.sh <prefixe-de-base-jetable>
#
# LA QUESTION QUE PERSONNE NE POSAIT
# ------------------------------------
# `stockage_s3.sh` etablit que les octets survivent a un REDEMARRAGE. C'est
# beaucoup moins que ce dont une retention decennale a besoin: un redemarrage
# ne perd rien. Une panne de disque, une suppression accidentelle, une region
# qui brule — voila ce contre quoi une sauvegarde existe, et rien dans ce
# depot ne montrait qu'on sait revenir de la.
#
# UN LIVRABLE VIT DANS DEUX SYSTEMES, ET C'EST TOUT LE PIEGE
# ------------------------------------------------------------
# La LIGNE est dans PostgreSQL: son empreinte, sa taille, son etat, son
# attestation, sa filiation. Les OCTETS sont dans le magasin objet. Sauvegarder
# l'un sans l'autre ne donne pas une demi-sauvegarde: cela donne une base qui
# promet des documents introuvables, ou un compartiment d'objets que plus rien
# ne sait nommer.
#
# C'est le genre d'erreur qu'on ne decouvre qu'au moment ou l'on en a besoin.
#
# LES HUIT ETAPES, DANS CET ORDRE
# ---------------------------------
#   1. UN VOLUME NEUF et un MinIO qui s'y adosse.
#   2. LE COMPARTIMENT, cree par notre propre signature SigV4.
#   3. LE DEPOT d'un livrable par les routes reelles, depuis un calcul strict.
#   4. LA SAUVEGARDE DES DEUX MOITIES — `pg_dump -Fc` de la base, et les objets
#      tires du compartiment PAR LE CLIENT DU PRODUIT. Ce que le produit sait
#      enumerer et lire est exactement ce qu'un exploitant peut sauvegarder.
#   5. LA DESTRUCTION TOTALE — la base est SUPPRIMEE, le conteneur et le volume
#      DETRUITS. On constate qu'il ne reste rien: sans ce constat, l'etape 7
#      pourrait reussir en lisant ce qui n'a jamais disparu.
#   6. LA RESTAURATION DES DEUX MOITIES — base recreee et `pg_restore`, volume
#      neuf, MinIO neuf, compartiment recree, objets redeposes.
#   7. LES MEMES OCTETS, PAR LA ROUTE REELLE — meme empreinte, meme taille,
#      meme nom de fichier, et le cloisonnement inter-organisations tient
#      encore. Ce sont les memes cas que la relecture apres redemarrage: ce qui
#      change n'est pas ce qu'on verifie, c'est ce qu'on a detruit avant.
#   8. LA MOITIE SEULE NE SUFFIT PAS — les objets sont detruits une seconde
#      fois, la base restant intacte. Le telechargement doit ECHOUER, et le
#      rapprochement doit nommer la cle manquante comme `absent`.
#
#      SANS CETTE ETAPE, LE HARNAIS SERAIT UN PIEGE. Un exploitant qui ne
#      sauvegarde que PostgreSQL verrait un dump qui se restaure parfaitement,
#      une base saine, des lignes completes — et decouvrirait au premier
#      telechargement que les documents n'existent plus.
#
# CE QUI EST ETABLI, ET CE QUI NE L'EST PAS
# -------------------------------------------
# ETABLI: qu'un livrable depose par le produit se retrouve, a l'octet pres,
# apres destruction complete des deux systemes, en ne se servant que de
# `pg_dump`/`pg_restore` et du client S3 du produit.
#
# NON ETABLI: une procedure d'exploitation. Ceci est un HARNAIS, pas un plan de
# reprise: pas de sauvegarde continue, pas de journal de transactions, pas de
# point de reprise dans le temps, pas de site distant, pas de chiffrement des
# sauvegardes, et aucune mesure de duree sur un volume reel. Ce qu'il etablit
# est que la MATIERE necessaire a une restauration est accessible et suffit.
#
# LA RESTAURATION EST DANS LE MEME CLUSTER, ET C'EST DELIBERE. Le refus d'une
# restauration INTER-CLUSTER est le sujet de `cross_cluster_restore.sh`, et il
# est voulu. Ici on eprouve le cas d'exploitation courant: on a perdu les
# donnees, pas la machine.
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

PREFIXE="${1:?usage: sauvegarde_restauration.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "sauvegarde_restauration.sh" || exit 2
harnais_verrou_prendre  "sauvegarde_restauration.sh" || exit $?
exiger_cluster_jetable  "sauvegarde_restauration.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
exiger_roles_absents "sauvegarde_restauration.sh" \
  "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

MIG="${PREFIXE}_mt_${JETON}"; CTL="${PREFIXE}_ct_${JETON}"
SVC="${PREFIXE}_st_${JETON}"; BASE="${PREFIXE}_dt_${JETON}"
MDP="FICTIF-sr-${JETON}"
MANDAT="11111111-9999-9999-9999-999999999901:FICTIF-EMPREINTE-SR-${JETON}"
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
CONTENEUR="esc-sr-${JETON}"
VOLUME="esc-sr-${JETON}"
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
PORT_S3="${EUROSTRUCT_SR_PORT_HARNAIS:-9188}"
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
  harnais_postcondition_nettoyage "sauvegarde_restauration.sh" \
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
  echo "NON EXECUTE: sauvegarde_restauration.sh — dependance(s) absente(s):$MANQUANTS" >&2
  echo "       Installer: pip install -e eurostruct/api" >&2
  exit 4
fi
command -v docker >/dev/null 2>&1 || {
  echo "NON EXECUTE: sauvegarde_restauration.sh — docker absent." >&2
  echo "       Le magasin objet doit etre REEL: ni faux client, ni" >&2
  echo "       repertoire deguise en compartiment." >&2
  exit 4; }
docker info >/dev/null 2>&1 || {
  echo "NON EXECUTE: sauvegarde_restauration.sh — le demon docker ne repond pas." >&2
  exit 4; }

echo "    tranche applicative: sauvegarde et restauration des DEUX moities"

TMP="$(mktemp -d "/tmp/esc-sr-${JETON}-XXXXXX")" || {
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
echo "      1/8 volume neuf, MinIO en ecoute sur 127.0.0.1:$PORT_S3"

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
echo "      2/8 compartiment « $COMPARTIMENT » cree par le client du produit"

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
export EUROSTRUCT_BUILD_SHA="FICTIF-build-sr-${JETON}"
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
echo "      3/8 $NB_LIGNES livrable(s) deposes, objet present sur le volume"

# ===========================================================================
# ETAPE 4 — LA SAUVEGARDE DES DEUX MOITIES
# ===========================================================================
# LE PROCESSUS D'API EST DEJA DETRUIT: `pytest` a rendu la main, et avec lui
# l'interpreteur, les connexions PostgreSQL, le client S3 et tout cache en
# memoire. On sauvegarde un systeme au repos, pas un systeme qu'on observe.
SAUVEGARDE="$TMP/sauvegarde"
mkdir -p "$SAUVEGARDE/objets"

# LA MOITIE POSTGRESQL. `-Fc` — format personnalise — parce que c'est celui
# que `pg_restore` sait rejouer dans une base recreee, avec les proprietaires,
# les privileges et les fonctions SECURITY DEFINER.
if ! pg_dump -Fc -d "$BASE" -f "$SAUVEGARDE/base.dump" 2>"$TMP/pg_dump.err"; then
  echo "      ECHEC: pg_dump n'a pas abouti." >&2
  sed 's/^/             /' "$TMP/pg_dump.err" >&2
  exit 1
fi
TAILLE_DUMP=$(wc -c < "$SAUVEGARDE/base.dump" | tr -d ' ')
if [[ "${TAILLE_DUMP:-0}" -lt 1000 ]]; then
  echo "      ECHEC: le dump ne pese que $TAILLE_DUMP octets." >&2
  exit 1
fi

# LA MOITIE MAGASIN, PAR LE CLIENT DU PRODUIT.
#
# ON N'UTILISE NI `mc mirror` NI LA REPLICATION DU FOURNISSEUR, et pas par
# purisme: ce qui nous interesse est de savoir si CE QUE LE PRODUIT SAIT
# ENUMERER ET LIRE suffit a reconstituer le magasin. Si notre propre client ne
# peut pas parcourir le compartiment, aucun exploitant ne peut ecrire une
# procedure de sauvegarde a partir de ce que le produit expose.
if ! python3 - "$SAUVEGARDE/objets" >/dev/null <<'FINPY'
import hashlib, json, os, sys
from pathlib import Path
from eurostruct_api.s3 import ClientS3, ReglagesS3

destination = Path(sys.argv[1])
client = ClientS3(ReglagesS3(
    endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"],
    region=os.environ["EUROSTRUCT_S3_REGION"],
    bucket=os.environ["EUROSTRUCT_S3_BUCKET"],
    access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
    secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
    prefixe=os.environ["EUROSTRUCT_S3_PREFIX"],
))

inventaire = []
objets = client.enumerer()
if not objets:
    print("le compartiment est vide: il n'y a rien a sauvegarder",
          file=sys.stderr)
    raise SystemExit(1)

for chemin, taille in objets:
    octets = client.lire(chemin)
    if len(octets) != taille:
        print(f"{chemin}: {len(octets)} octets lus, {taille} annonces",
              file=sys.stderr)
        raise SystemExit(1)
    # LE NOM DE FICHIER DE SAUVEGARDE EST L'EMPREINTE DU CHEMIN, PAS LE CHEMIN.
    # Un chemin porte des barres obliques; le recreer en arborescence sur le
    # disque de sauvegarde n'apporte rien et invite aux surprises. L'inventaire
    # garde la correspondance.
    nom = hashlib.sha256(chemin.encode("utf-8")).hexdigest()
    (destination / nom).write_bytes(octets)
    inventaire.append({"chemin": chemin, "fichier": nom,
                       "taille": len(octets),
                       "sha256": hashlib.sha256(octets).hexdigest()})

(destination.parent / "inventaire.json").write_text(
    json.dumps(inventaire, indent=2), encoding="utf-8")
print(len(inventaire))
FINPY
then
  echo "      ECHEC: les objets n'ont pas pu etre sauvegardes." >&2
  exit 1
fi
NB_OBJETS=$(python3 -c "
import json
print(len(json.load(open('$SAUVEGARDE/inventaire.json'))))
")
echo "      4/8 sauvegarde: dump de $TAILLE_DUMP octets, $NB_OBJETS objet(s)"

# ===========================================================================
# ETAPE 5 — LA DESTRUCTION TOTALE
# ===========================================================================
# SANS CE CONSTAT, L'ETAPE 7 NE PROUVERAIT RIEN. Une relecture qui reussit
# parce que rien n'a jamais disparu est une relecture qui ment.
adm -c "select pg_terminate_backend(pid) from pg_stat_activity
         where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
if ! adm -c "drop database \"$BASE\";" >/dev/null 2>&1; then
  echo "      ECHEC: la base $BASE n'a pas pu etre supprimee." >&2
  exit 1
fi
if [[ "$(adm -tAc "select count(*) from pg_database where datname = '$BASE';" | tr -d ' ')" != "0" ]]; then
  echo "      ECHEC: la base $BASE existe encore." >&2
  exit 1
fi

docker rm -f "$CONTENEUR" >/dev/null 2>&1 || {
  echo "      ECHEC: le conteneur n'a pas ete detruit." >&2; exit 1; }
CONTENEUR_CREE=0
docker volume rm "$VOLUME" >/dev/null 2>&1 || {
  echo "      ECHEC: le volume n'a pas ete detruit." >&2; exit 1; }
VOLUME_CREE=0
if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -qx "$VOLUME"; then
  echo "      ECHEC: le volume survit a sa propre destruction." >&2
  exit 1
fi
echo "      5/8 base SUPPRIMEE, conteneur et volume DETRUITS — il ne reste rien"

# ===========================================================================
# ETAPE 6 — LA RESTAURATION DES DEUX MOITIES
# ===========================================================================
if ! adm -c "create database \"$BASE\" owner \"$MIG\";" >/dev/null 2>&1; then
  echo "      ECHEC: la base n'a pas pu etre recreee." >&2
  exit 1
fi
registre_base "$BASE"

# `pg_restore` PARLE SUR LA SORTIE D'ERREUR MEME QUAND IL REUSSIT. On branche
# sur son CODE DE SORTIE, jamais sur la presence de texte.
if ! pg_restore -d "$BASE" "$SAUVEGARDE/base.dump" 2>"$TMP/pg_restore.err"; then
  echo "      ECHEC: pg_restore n'a pas abouti." >&2
  tail -20 "$TMP/pg_restore.err" | sed 's/^/             /' >&2
  exit 1
fi

NB_RESTAURE="$(q "select count(*) from deliverables;")"
if [[ "${NB_RESTAURE:-0}" != "$NB_LIGNES" ]]; then
  echo "      ECHEC: $NB_RESTAURE livrable(s) apres restauration," >&2
  echo "             $NB_LIGNES avant." >&2
  exit 1
fi

# LE MAGASIN, RECONSTITUE SUR UN VOLUME NEUF.
docker volume create "$VOLUME" >/dev/null 2>&1 || {
  echo "      ECHEC: volume de restauration non cree." >&2; exit 1; }
VOLUME_CREE=1
docker run -d --name "$CONTENEUR" \
  --env-file "$ENVF" \
  -v "$VOLUME:/data" \
  -p "127.0.0.1:$PORT_S3:9000" \
  "$IMAGE_MINIO" server /data >/dev/null 2>&1 || {
    echo "      ECHEC: MinIO de restauration n'a pas demarre." >&2; exit 1; }
CONTENEUR_CREE=1
if ! attendre_minio 60; then
  echo "      ECHEC: MinIO de restauration n'a pas repondu." >&2
  exit 1
fi

# LE COMPARTIMENT EST RECREE PUIS REMPLI — PAR LE CLIENT DU PRODUIT, ENCORE.
# `deposer` verifie qu'il n'ecrase pas un objet divergent; sur un compartiment
# neuf il n'y a rien a ecraser, et c'est bien ce qu'on veut constater.
if ! python3 - "$SAUVEGARDE" >/dev/null <<'FINPY'
import json, sys
import os
from pathlib import Path
from eurostruct_api.s3 import ClientS3, ReglagesS3

source = Path(sys.argv[1])
client = ClientS3(ReglagesS3(
    endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"],
    region=os.environ["EUROSTRUCT_S3_REGION"],
    bucket=os.environ["EUROSTRUCT_S3_BUCKET"],
    access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
    secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
    prefixe=os.environ["EUROSTRUCT_S3_PREFIX"],
))
client.creer_compartiment()

inventaire = json.loads((source / "inventaire.json").read_text(encoding="utf-8"))
for entree in inventaire:
    octets = (source / "objets" / entree["fichier"]).read_bytes()
    client.deposer(entree["chemin"], octets, "text/html; charset=utf-8")

# ON RELIT CE QU'ON VIENT DE DEPOSER. Une restauration qu'on ne relit pas est
# une restauration qu'on espere.
for entree in inventaire:
    relus = client.lire(entree["chemin"])
    if len(relus) != entree["taille"]:
        print(f"{entree['chemin']}: taille restauree incorrecte",
              file=sys.stderr)
        raise SystemExit(1)
print(len(inventaire))
FINPY
then
  echo "      ECHEC: les objets n'ont pas pu etre restaures." >&2
  exit 1
fi
echo "      6/8 base restauree ($NB_RESTAURE livrable(s)), $NB_OBJETS objet(s) redeposes"

# ===========================================================================
# ETAPE 7 — LES MEMES OCTETS, PAR LA ROUTE REELLE
# ===========================================================================
# CE SONT EXACTEMENT LES CAS DE LA RELECTURE APRES REDEMARRAGE. Ce qui change
# n'est pas ce qu'on verifie, c'est ce qu'on a detruit avant de le verifier.
python3 -m pytest "${CIBLE_PYTEST}::TestApresRedemarrage" \
        -p no:cacheprovider --no-header -q
CODE=$?
if [[ $CODE -ne 0 ]]; then
  echo "      ECHEC: apres restauration, la relecture n'aboutit pas." >&2
  exit $CODE
fi

# ET LE CONSTAT EXTERNE: les octets sont sur le NOUVEAU volume, celui qui vient
# d'etre cree. On copie l'objet hors du produit et on y cherche les octets.
if ! SORTIE_CONSTAT="$(constater_octets_sur_le_volume restauration 2>&1)"; then
  echo "      ECHEC: le contenu n'est pas sur le volume restaure." >&2
  echo "$SORTIE_CONSTAT" | sed 's/^/             /' >&2
  exit 1
fi
echo "      7/8 memes octets, meme empreinte ($SHA_DEPOSE), par la route reelle"

# ===========================================================================
# ETAPE 8 — LA MOITIE SEULE NE SUFFIT PAS
# ===========================================================================
# UN EXPLOITANT QUI NE SAUVEGARDE QUE POSTGRESQL VERRAIT UN DUMP PARFAIT.
# Il se restaure, la base est saine, les lignes sont completes, l'attestation
# est la, l'empreinte est la. Et pas un document n'est telechargeable.
#
# On detruit donc les objets une seconde fois, EN LAISSANT LA BASE INTACTE, et
# on exige que le produit le dise — au lieu de servir un vide.
docker rm -f "$CONTENEUR" >/dev/null 2>&1 || {
  echo "      ECHEC: le conteneur n'a pas ete detruit (etape 8)." >&2; exit 1; }
CONTENEUR_CREE=0
docker volume rm "$VOLUME" >/dev/null 2>&1 || {
  echo "      ECHEC: le volume n'a pas ete detruit (etape 8)." >&2; exit 1; }
VOLUME_CREE=0

docker volume create "$VOLUME" >/dev/null 2>&1 || exit 1
VOLUME_CREE=1
docker run -d --name "$CONTENEUR" --env-file "$ENVF" \
  -v "$VOLUME:/data" -p "127.0.0.1:$PORT_S3:9000" \
  "$IMAGE_MINIO" server /data >/dev/null 2>&1 || exit 1
CONTENEUR_CREE=1
attendre_minio 60 || { echo "      ECHEC: MinIO vide n'a pas repondu." >&2; exit 1; }

# LE COMPARTIMENT EXISTE ET IL EST VIDE. C'est le pire cas, pas le plus
# confortable: un compartiment ABSENT ferait echouer la configuration, ce qui
# se remarque. Un compartiment vide ressemble a un systeme en bon etat.
if ! python3 - <<'FINPY'
import os
from eurostruct_api.s3 import ClientS3, ReglagesS3

client = ClientS3(ReglagesS3(
    endpoint=os.environ["EUROSTRUCT_S3_ENDPOINT"],
    region=os.environ["EUROSTRUCT_S3_REGION"],
    bucket=os.environ["EUROSTRUCT_S3_BUCKET"],
    access_key_id=os.environ["EUROSTRUCT_S3_ACCESS_KEY_ID"],
    secret_access_key=os.environ["EUROSTRUCT_S3_SECRET_ACCESS_KEY"],
    prefixe=os.environ["EUROSTRUCT_S3_PREFIX"],
))
client.creer_compartiment()
assert client.enumerer() == [], "le compartiment devait etre vide"
FINPY
then
  echo "      ECHEC: le compartiment vide n'a pas ete recree." >&2
  exit 1
fi

# LE RAPPROCHEMENT DOIT NOMMER CE QUI MANQUE. C'est precisement le verdict
# `absent`: une ligne qui promet un document que le magasin n'a pas.
SORTIE_MOITIE="$(EUROSTRUCT_RECONCILIATION_DSN="$EUROSTRUCT_E2E_DSN_OBS" \
                 python3 -m eurostruct_api.reconciliation --json 2>&1)"
CODE_MOITIE=$?
if [[ $CODE_MOITIE -ne 1 ]]; then
  echo "      ECHEC: le rapprochement devait rendre 1 sur une base restauree" >&2
  echo "             sans ses objets, il a rendu $CODE_MOITIE." >&2
  echo "$SORTIE_MOITIE" | sed 's/^/             /' >&2
  exit 1
fi
if ! printf '%s' "$SORTIE_MOITIE" | python3 -c '
import json, sys
rapport = json.load(sys.stdin)
absents = rapport["comptes"]["absent"]
assert absents >= 1, "aucune ligne declaree absente: %d" % absents
assert rapport["comptes"]["orphelin"] == 0, "un compartiment vide na pas dorphelin"
constats = [c for c in rapport["constats"] if c["verdict"] == "absent"]
assert all(c["deliverable_id"] for c in constats), "un absent sans livrable nomme"
assert any("503" in c["detail"] for c in constats), "le detail nannonce pas le 503"
'; then
  echo "      ECHEC: le rapprochement ne nomme pas les lignes devenues" >&2
  echo "             sans objet." >&2
  echo "$SORTIE_MOITIE" | sed 's/^/             /' >&2
  exit 1
fi

# ET LE PRODUIT LUI-MEME REFUSE, PAR LA ROUTE. Le rapprochement est un outil
# d'exploitation; ce qu'un utilisateur rencontre, c'est le telechargement.
#
# UN ECHEC NE SUFFIT PAS: IL FAUT LE BON ECHEC. « `pytest` a rendu non-zero »
# serait vrai aussi d'un nodeid mal ecrit, d'un import casse ou d'un decor
# absent — et ce harnais annoncerait alors « le produit refuse » sans avoir
# rien exerce. On exige que le cas ait REELLEMENT tourne, et qu'il ait echoue
# en rencontrant un objet manquant, pas autre chose.
CAS_TELECHARGEMENT="${CIBLE_PYTEST}::TestApresRedemarrage"
CAS_TELECHARGEMENT+="::test_les_memes_octets_reviennent_avec_la_meme_empreinte"
python3 -m pytest "$CAS_TELECHARGEMENT" \
        -p no:cacheprovider --no-header -q >"$TMP/moitie.log" 2>&1
CODE_ROUTE=$?
if [[ $CODE_ROUTE -eq 0 ]]; then
  echo "      ECHEC: le telechargement a REUSSI alors que le magasin est vide." >&2
  echo "             Un document introuvable a ete servi comme s'il existait." >&2
  exit 1
fi

# ON BRANCHE SUR LE CODE DE SORTIE DE `pytest`, PAS SUR SON TEXTE.
# Son contrat est explicite: 1 = des cas ont tourne et ont echoue; 2 =
# interrompu; 4 = erreur d'usage; 5 = AUCUN cas collecte. Exiger exactement 1
# distingue « le produit a refuse » de « le nodeid etait faux » — ce que « la
# commande a rendu non-zero » ne distingue pas, et ce qu'une recherche de
# phrase dans la sortie distingue mal.
if [[ $CODE_ROUTE -ne 1 ]]; then
  echo "      ECHEC: le cas de telechargement n'a pas tourne (pytest a rendu" >&2
  echo "             $CODE_ROUTE; 5 = aucun cas collecte, 4 = erreur d'usage)." >&2
  echo "             Un harnais qui prend une erreur de collecte pour un refus" >&2
  echo "             du produit n'eprouve rien." >&2
  tail -15 "$TMP/moitie.log" | sed 's/^/             /' >&2
  exit 1
fi
# LE MOTIF DU REFUS. La route doit dire qu'elle ne peut pas servir — et
# surtout pas rendre 200 avec un corps vide.
if ! grep -qiE "503|ObjetIntrouvable|magasin" "$TMP/moitie.log"; then
  echo "      ECHEC: le cas a echoue, mais pas pour un objet manquant." >&2
  tail -15 "$TMP/moitie.log" | sed 's/^/             /' >&2
  exit 1
fi

echo "      8/8 la base seule ne suffit pas: le rapprochement dit « absent »,"
echo "          et le telechargement refuse au lieu de servir un vide"

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

echo ""
echo "================================================="
echo " Un livrable depose par les routes, sauvegarde,"
echo " puis retrouve a l'octet pres apres DESTRUCTION"
echo " de la base ET du volume."
echo ""
echo " Et la moitie seule ne suffit pas: une base"
echo " restauree sans ses objets ne sert rien — elle"
echo " le DIT, au lieu de le taire."
echo ""
echo " Ceci est un HARNAIS, pas un plan de reprise."
echo " Ni sauvegarde continue, ni point de reprise dans"
echo " le temps, ni site distant, ni chiffrement des"
echo " sauvegardes n'ont ete eprouves ici."
echo "================================================="
exit 0
