#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6d: LA RESTAURATION INTER-CLUSTER, EXERCEE
#
#   cross_cluster_restore.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# Le modele de menace annonce, depuis 6.3b6c, que la restauration vers un autre
# cluster echoue en fail-closed. Cette annonce n'etait verifiee que par un
# `grep`: le scenario G de `authority_closure.sh` cherchait un marqueur dans le
# texte des migrations. Il constatait donc qu'une PHRASE existe — jamais qu'un
# COMPORTEMENT a lieu.
#
# Ce fichier fait la manipulation:
#
#   1. cluster A — un deploiement complet, finalise, ACTIVE;
#   2. `pg_dump` de cette base;
#   3. cluster B — un SECOND CLUSTER, cree par `initdb`, ou les roles sont
#      recrees et portent donc de NOUVEAUX OID;
#   4. `pg_restore` dans ce cluster;
#   5. interrogation de la topologie;
#   6. constat du refus, et de sa formulation.
#
# POURQUOI UN VRAI SECOND CLUSTER. Recreer les roles dans le cluster d'origine
# produirait la meme discontinuite d'OID et suffirait a faire rougir la
# topologie. Ce serait une simulation du MECANISME, pas de la SITUATION: rien
# n'y prouverait que le dump se restaure, que les fonctions SECURITY DEFINER
# retrouvent leurs proprietaires, ni que l'etat lu apres restauration est bien
# `ACTIVE`. Ce sont ces trois faits qui rendent le refus interessant — une base
# restauree a l'air parfaitement saine.
#
# CE QUI EST AUSSI VERIFIE, ET QUI COMPTE AUTANT: que le diagnostic ne promette
# pas une operation qui n'existe pas. Un refus qui envoie l'exploitant executer
# une procedure inexistante est un refus qui ment.
#
# Toutes les identites sont FICTIVES. Le cluster B est cree, utilise et detruit
# par ce script; il ne touche a aucune installation existante.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"

PREFIXE="${1:?usage: cross_cluster_restore.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "cross_cluster_restore.sh" || exit 2
exiger_cluster_jetable  "cross_cluster_restore.sh" || exit 2
harnais_verrou_prendre  "cross_cluster_restore.sh" || exit $?
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend
            eurostruct_reconciliation)

exiger_roles_absents "cross_cluster_restore.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

KO=0; ROUGES=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
rouge()  { echo "      ROUGE ATTENDU (a fermer): $*"; ROUGES=$((ROUGES + 1)); }
detail() { echo "                                $*"; }

adm() { psql -X -q -d postgres "$@"; }

# --------------------------------------------------------------------------
# OU EST LE SCEAU (voir seal_contract.sh pour le raisonnement)
# --------------------------------------------------------------------------
SCEAU="$HARNAIS_SCEAU"
[[ -f "$SCEAU" ]] || { echo "      ECHEC: le sceau est introuvable ($SCEAU)" >&2
                       harnais_verrou_rendre; exit 2; }

# --------------------------------------------------------------------------
# LE SECOND CLUSTER — OUTILLAGE
# --------------------------------------------------------------------------
# `initdb` n'est pas dans le paquet client. S'il manque, ce harnais NE PASSE
# PAS AU VERT: il rend 4 — NON EXECUTE — et le dit. Une surface qu'on n'a pas
# pu exercer n'est pas une surface qui a tenu.
BIN=""
for d in "$(pg_config --bindir 2>/dev/null)" /usr/lib/postgresql/*/bin \
         /usr/pgsql-*/bin /opt/homebrew/opt/postgresql@*/bin; do
  [[ -n "$d" && -x "$d/initdb" && -x "$d/pg_ctl" ]] && { BIN="$d"; break; }
done
if [[ -z "$BIN" ]] && command -v initdb >/dev/null 2>&1; then
  BIN="$(dirname "$(command -v initdb)")"
fi
if [[ -z "$BIN" ]]; then
  cat >&2 <<'EOF'
NON EXECUTE: `initdb` est introuvable — le paquet SERVEUR de PostgreSQL n'est
       pas installe sur cette machine, seul le client l'est.

       Ce harnais cree un SECOND CLUSTER pour exercer une restauration reelle.
       Sans `initdb`, il ne peut pas etre execute, et il refuse de rendre VERT
       une garantie qu'il n'a pas verifiee.

       Debian/Ubuntu:  apt-get install -y postgresql-16
EOF
  harnais_verrou_rendre
  exit 4
fi

# QUI FAIT TOURNER LE CLUSTER B. `initdb` et `postgres` refusent de s'executer
# sous root. Sous root on delegue a l'utilisateur `postgres`; sinon on reste
# soi-meme. Le superutilisateur d'amorcage du cluster B est, dans les deux cas,
# celui qui a lance `initdb`.
if [[ "$(id -u)" -eq 0 ]]; then
  if ! id postgres >/dev/null 2>&1; then
    echo "NON EXECUTE: execute sous root sans utilisateur « postgres » pour" >&2
    echo "       porter le second cluster." >&2
    harnais_verrou_rendre
    exit 4
  fi
  SOUS_B=(su postgres -c); B_SUPER=postgres
else
  SOUS_B=(bash -c); B_SUPER="$(id -un)"
fi
lancer_b() { "${SOUS_B[@]}" "$1"; }

# UN PORT LIBRE, constate et non suppose: 5433 peut etre pris par une autre
# installation, et le diagnostic serait alors incomprehensible.
PORT_B=0
for p in $(seq 5440 5460); do
  (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null || { PORT_B=$p; break; }
done
if [[ "$PORT_B" == "0" ]]; then
  echo "NON EXECUTE: aucun port libre entre 5440 et 5460 pour le cluster B." >&2
  harnais_verrou_rendre
  exit 4
fi

BDIR="$(mktemp -d "/tmp/${PREFIXE}_clusterB.XXXXXX")"
b() { psql -X -q -h "$BDIR" -p "$PORT_B" -U "$B_SUPER" "$@"; }

# --------------------------------------------------------------------------
# LE DECOR DU CLUSTER A
# --------------------------------------------------------------------------
MIG="${PREFIXE}_ma_${JETON}"
CTL="${PREFIXE}_ca_${JETON}"
BASE="${PREFIXE}_da_${JETON}"
MDP="FICTIF-xr-${JETON}"
mig()   { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()   { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb()  { psql -X -q -d "$BASE" "$@"; }

NETTOYAGE_KO=0
sortie_propre() {
  local r
  # LE CLUSTER B D'ABORD: il detient un `postgres` qui, laisse en vie,
  # survivrait au script et garderait son repertoire de donnees.
  lancer_b "'$BIN/pg_ctl' -D '$BDIR/data' -m immediate stop" >/dev/null 2>&1
  rm -rf "$BDIR"

  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL"; do
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "cross_cluster_restore.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    restauration inter-cluster: le refus a-t-il lieu, et que dit-il ?"

# ---- CLUSTER A: deploiement complet et finalise --------------------------
creer_role "$MIG" "login password '$MDP' createrole createdb" \
  || { echoue "creation du migrateur impossible"; exit 1; }
creer_role "$CTL" "login password '$MDP' createrole" \
  || { echoue "creation du plan de controle impossible"; exit 1; }
adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
creer_base "$BASE" "owner \"$MIG\"" || { echoue "creation de la base impossible"; exit 1; }
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
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1

if ! SORTIE=$(ctl -v ON_ERROR_STOP=1 -f "$SCEAU" 2>&1); then
  echoue "phase 0 refusee:"; esc_diag_rapporter "phase 0 (sceau)" "$SORTIE"; exit 1
fi
adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
for f in "$DB_DIR"/migrations/*.sql; do
  [[ "$f" == "$SCEAU" ]] && continue
  if ! esc_appliquer_migration "$f" mig; then
    SORTIE="$ESC_MIGRATION_SORTIE"
    echoue "phase 1 refusee sur $(basename "$f"):"
    esc_diag_rapporter "phase 1 / $(basename "$f")" "$SORTIE"
    exit 1
  fi
done
MANIF=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_finalize_deployment($(esc_litteral "$MANIF"))" >/dev/null 2>&1
ETAT_A=$(ctl -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT_A" != "ACTIVE" ]]; then
  echoue "le cluster A ne se termine pas en ACTIVE (obtenu: $ETAT_A)"; exit 1
fi
OID_A=$(admb -tAc "select role_oid from normative_control_plane" 2>&1)
echo "      ok: cluster A — ACTIVE, plan « $CTL » oid=$OID_A"

# ---- LE DUMP -------------------------------------------------------------
if ! pg_dump -d "$BASE" -Fc -f "$BDIR/dump.pgc" 2>"$BDIR/dump.err"; then
  echoue "pg_dump a echoue: $(head -1 "$BDIR/dump.err")"; exit 1
fi
echo "      ok: dump de $(stat -c %s "$BDIR/dump.pgc" 2>/dev/null || echo '?') octets"

# ---- CLUSTER B -----------------------------------------------------------
# Le repertoire doit appartenir a qui fait tourner le serveur, et le dump doit
# lui etre lisible.
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R postgres:postgres "$BDIR"; chmod 750 "$BDIR"
fi
chmod 644 "$BDIR/dump.pgc"
if ! lancer_b "'$BIN/initdb' -D '$BDIR/data' -A trust --no-sync -E UTF8" >"$BDIR/initdb.log" 2>&1; then
  echoue "initdb a echoue: $(tail -1 "$BDIR/initdb.log")"; exit 1
fi
if ! lancer_b "'$BIN/pg_ctl' -D '$BDIR/data' -l '$BDIR/pg.log' -w \
       -o \"-p $PORT_B -k '$BDIR' -c listen_addresses=''\" start" >"$BDIR/start.log" 2>&1; then
  echoue "le cluster B n'a pas demarre: $(tail -2 "$BDIR/pg.log" 2>/dev/null)"; exit 1
fi
echo "      ok: cluster B demarre (port $PORT_B, superutilisateur « $B_SUPER »)"

# LES ROLES SONT RECREES: nouveaux OID, exactement comme apres un
# `pg_dumpall --roles-only` rejoue sur un cluster neuf.
b -d postgres -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role normative_backend;
create role normative_governance;
create role eurostruct_normative_writer nologin;
create role eurostruct_normative_bootstrap nologin;
create role eurostruct_normative_activator nologin;
create role eurostruct_deployment nologin;
create role authenticated;
create role anon;
create role service_role;
create role supabase_auth_admin login password 'FICTIF-b-$JETON';
create role "$MIG" login password '$MDP' createrole createdb;
create role "$CTL" login password '$MDP' createrole;
grant eurostruct_deployment to "$CTL" with inherit true;
create database "$BASE" owner "$MIG";
SQL
if ! lancer_b "'$BIN/pg_restore' -h '$BDIR' -p $PORT_B -U '$B_SUPER' \
       -d '$BASE' '$BDIR/dump.pgc'" >"$BDIR/restore.log" 2>&1; then
  # pg_restore signale des avertissements sans etre en echec utile; on ne
  # s'arrete que si la base restauree est inexploitable.
  :
fi
RESTAURE=$(b -d "$BASE" -tAc "select count(*) from pg_class where relname = 'normative_control_plane'" 2>&1)
if [[ "$RESTAURE" != "1" ]]; then
  echoue "la restauration n'a pas produit de base exploitable"
  head -5 "$BDIR/restore.log" | sed 's/^/              /' >&2
  exit 1
fi
OID_B=$(b -d "$BASE" -tAc "select oid from pg_roles where rolname = '$CTL'" 2>&1)
OID_FIGE=$(b -d "$BASE" -tAc "select role_oid from normative_control_plane" 2>&1)
echo "      ok: base restauree — oid fige $OID_FIGE, role reel $OID_B"

# ==========================================================================
# L1. LA DISCONTINUITE D'OID EST BIEN CE QUI EST EXERCE
# ==========================================================================
# Sans ce constat, un refus obtenu pour une autre raison — un objet manquant,
# une fonction non restauree — passerait pour la preuve recherchee.
if [[ "$OID_FIGE" != "$OID_B" && "$OID_FIGE" == "$OID_A" ]]; then
  echo "      ok: L1. l'OID fige a survecu au dump, le role a change d'OID"
else
  echoue "L1. la situation exercee n'est pas celle qu'on croit"
  echoue "    (A=$OID_A, fige=$OID_FIGE, B=$OID_B)"
fi

# ==========================================================================
# L2. L'ETAT LU EST « ACTIVE » — LA BASE A L'AIR SAINE
# ==========================================================================
ETAT_B=$(b -d "$BASE" -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT_B" == "ACTIVE" ]]; then
  echo "      ok: L2. la base restauree se declare ACTIVE"
else
  echoue "L2. la base restauree ne lit pas son etat (obtenu: $(cut -c1-120 <<<"$ETAT_B"))"
fi

# ==========================================================================
# L3. LA TOPOLOGIE REFUSE, ET NOMME LA RESTAURATION
# ==========================================================================
TOPO_B=$(b -d "$BASE" -tAc "select assert_normative_topology()" 2>&1)
if grep -qF "RESTAURATION INTER-CLUSTER" <<<"$TOPO_B"; then
  echo "      ok: L3. la topologie refuse et nomme la restauration inter-cluster"
else
  rouge "L3. la restauration inter-cluster ne produit pas le refus attendu."
  detail "    Obtenu: $(cut -c1-200 <<<"$TOPO_B")"
fi

# ==========================================================================
# L4. LE DIAGNOSTIC NE PROMET PAS UNE OPERATION QUI N'EXISTE PAS
# ==========================================================================
# Le diagnostic dit aujourd'hui: « Cette base doit etre refinalisee sur place
# par son propre plan de controle ». On execute cette consigne, et on regarde.
#
# CE CONTROLE EST LE PLUS IMPORTANT DES QUATRE. Un refus fail-closed qui envoie
# l'exploitant executer une procedure inexistante ne protege pas mieux qu'un
# refus muet: il fait perdre du temps et suggere qu'une issue existe.
MANIF_B=$(b -d "$BASE" -tAc "select normative_settings_manifest()" 2>&1)
REFI=$(b -d "$BASE" -tAc "select normative_finalize_deployment($(esc_litteral "$MANIF_B"))" 2>&1)
PROMET=$(grep -oiE "refinalis[a-z]*( sur place)?" <<<"$TOPO_B" | head -1)
REUSSI=0
[[ "$(b -d "$BASE" -tAc "select assert_normative_topology()" 2>&1)" != *ERROR* ]] && REUSSI=1
if [[ -z "$PROMET" ]]; then
  echo "      ok: L4. le diagnostic ne promet aucune procedure de reprise"
elif [[ "$REUSSI" == "1" ]]; then
  echo "      ok: L4. le diagnostic promet « $PROMET », et l'operation aboutit"
else
  rouge "L4. le diagnostic promet « $PROMET », mais l'operation n'existe pas."
  detail "    normative_finalize_deployment() sur la base restauree rend:"
  detail "      $(grep -m1 -E 'ERROR|refus' <<<"$REFI" | cut -c1-170)"
  detail "    normative_control_plane est immuable, normative_activation est"
  detail "    append-only, et normative_record_activation() refuse en ACTIVE:"
  detail "    aucun chemin ne ramene cette base en PENDING. La consigne est"
  detail "    inexecutable — il faut la remplacer par ce qui est vrai."
fi

# ==========================================================================
# L5. AUCUN CHEMIN NE RAMENE LA BASE EN PENDING
# ==========================================================================
# C'est le fait sur lequel L4 s'appuie: il est constate, pas suppose. Le
# migrateur est ici le PROPRIETAIRE de la base restauree — la position la plus
# favorable qu'un role non superutilisateur puisse avoir.
RETOUR=$(PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -h "$BDIR" -p "$PORT_B" \
           -d "$BASE" -tAc "delete from normative_activation" 2>&1)
if grep -qE "ERROR|permission denied" <<<"$RETOUR"; then
  echo "      ok: L5. le retour en PENDING est refuse, meme au proprietaire"
else
  echoue "L5. la table d'activation a pu etre videe: $(cut -c1-140 <<<"$RETOUR")"
fi

echo ""
echo "================================================="
if [[ $KO -eq 0 && $ROUGES -eq 0 ]]; then
  echo " Restauration inter-cluster: exercee, refusee, et dite sans promesse."
  echo "================================================="
  exit 0
fi
echo " Restauration inter-cluster:"
echo "   $KO ecart(s) de decor"
echo "   $ROUGES ouverture(s) a fermer"
echo "================================================="
exit 1
