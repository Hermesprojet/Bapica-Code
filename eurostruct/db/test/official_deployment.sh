#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6d: LA COMMANDE OFFICIELLE DE DEPLOIEMENT, EXERCEE
#
#   official_deployment.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `tools/deploy_eurostruct.sh` est le chemin officiel de deploiement. Un chemin
# officiel qui n'est jamais execute est une documentation deguisee en outil: il
# derive du produit sans que rien ne le signale, et se decouvre le jour du
# premier deploiement reel.
#
# CE QUI EST EXERCE
# ------------------
#   N1. le deploiement complet, par la commande officielle, exit 0
#   N2. les postconditions qu'elle annonce sont vraies APRES coup
#   N3. la RELANCE est sure — le cas de la connexion ambigue
#   N4. le mode STRICT refuse deux acteurs identiques
#   N5. le mode STRICT refuse un sceau pose par un superutilisateur,
#       et `--auto-heberge` l'accepte en le disant degrade
#   N6. la commande ne contient AUCUNE destruction
#
# CE QU'IL NE FAIT PAS: il ne fabrique pas le decor a la place de l'exploitant.
# Creer les roles, la base et poser les declarations sont des gestes
# d'exploitation, hors du perimetre de la commande — qui n'a donc pas a savoir
# les faire, et surtout pas a savoir les defaire.
#
# Toutes les identites sont FICTIVES. Aucune confirmation normative n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
COMMANDE="$RACINE/tools/deploy_eurostruct.sh"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

PREFIXE="${1:?usage: official_deployment.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "official_deployment.sh" || exit 2
exiger_cluster_jetable  "official_deployment.sh" || exit 2
harnais_verrou_prendre  "official_deployment.sh" || exit $?
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment)
exiger_roles_absents "official_deployment.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
adm() { psql -X -q -d postgres "$@"; }

[[ -x "$COMMANDE" ]] || { echo "      ECHEC: $COMMANDE introuvable ou non executable" >&2
                          harnais_verrou_rendre; exit 2; }

# LA COMMANDE OFFICIELLE PARLE EN URL, DONC EN TCP. Un `postgresql://` porte un
# HOTE, pas un repertoire de socket: ce harnais se connecte donc a
# `localhost:$PGPORT`, meme quand le reste de la suite passe par la socket unix.
#
# SI LE SERVEUR N'ECOUTE PAS EN TCP, ce harnais rend 4 — NON EXECUTE — au lieu
# d'echouer sur « connection refused », un diagnostic qui designerait la
# commande alors que c'est la configuration du cluster qui est en cause. Une
# surface qu'on n'a pas pu exercer n'est pas une surface qui a tenu.
if ! PGHOST=localhost PGPORT="${PGPORT:-5432}" psql -X -q -tAc "select 1" \
        -d postgres >/dev/null 2>&1; then
  echo "NON EXECUTE: le cluster n'accepte pas de connexion TCP sur" >&2
  echo "       localhost:${PGPORT:-5432}. La commande officielle de deploiement" >&2
  echo "       recoit deux URL: elle ne peut pas viser une socket unix." >&2
  harnais_verrou_rendre
  exit 4
fi

# --------------------------------------------------------------------------
# LE DECOR — CE QUE FAIT L'EXPLOITANT, ET QUE LA COMMANDE NE FAIT PAS
# --------------------------------------------------------------------------
MIG=""; CTL=""; BASE=""; MDP=""
admb() { psql -X -q -d "$BASE" "$@"; }

decor_poser() {
  local s="$1"
  MIG="${PREFIXE}_m${s}_${JETON}"
  CTL="${PREFIXE}_c${s}_${JETON}"
  BASE="${PREFIXE}_d${s}_${JETON}"
  MDP="FICTIF-od-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" || return 1
  creer_role "$CTL" "login password '$MDP' createrole"          || return 1
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  creer_base "$BASE" "owner \"$MIG\"" || return 1
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
  # LE ROLE DE DEPLOIEMENT: la commande exerce la phase 2, il lui faut donc
  # `eurostruct_deployment`. Il n'existe qu'apres la phase 0 — que la commande
  # applique elle-meme. L'octroi se fait donc APRES son premier appel, ce qui
  # est le vrai enchainement d'exploitation et non un artefact de test.
  return 0
}

decor_deposer() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}

# `deployer <mode>` — appelle la COMMANDE OFFICIELLE, jamais psql directement.
# Les identifiants passent par l'environnement du seul appel concerne: le
# script lui-meme n'en met aucun dans `argv`, et ce harnais non plus.
SORTIE_CMD=""
deployer() {
  local port="${PGPORT:-5432}"
  SORTIE_CMD=$(
    ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:$port/$BASE?sslmode=disable" \
    ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:$port/$BASE?sslmode=disable" \
    bash "$COMMANDE" "$@" 2>&1
  )
  return $?
}

NETTOYAGE_KO=0
TOUS_ROLES=()
suivre_decor() { TOUS_ROLES+=("$MIG" "$CTL"); }
sortie_propre() {
  local r
  decor_deposer
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}"; do
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "official_deployment.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    commande officielle de deploiement"

# ==========================================================================
# N6. LA COMMANDE NE DETRUIT RIEN — controle statique, avant de l'executer
# ==========================================================================
# Un outil de deploiement qui sait detruire une base est un outil qui la
# detruira, un jour, sur la mauvaise. Le controle porte sur les lignes de CODE:
# ce fichier decrit ces gestes dans son en-tete pour dire qu'il ne les fait pas.
DESTRUCTIONS=$(grep -nE '^[^#]*\b(drop[[:space:]]+(database|role|owned)|reassign[[:space:]]+owned)\b' \
                 "$COMMANDE" | head -5)
if [[ -z "$DESTRUCTIONS" ]]; then
  echo "      ok: N6. la commande ne contient aucune destruction"
else
  echoue "N6. la commande officielle contient des gestes destructeurs:"
  sed 's/^/              /' <<<"$DESTRUCTIONS" >&2
fi

# ==========================================================================
# N4. DEUX ACTEURS IDENTIQUES: refus en mode strict
# ==========================================================================
# Le refus doit tomber AVANT d'appliquer quoi que ce soit. La finalisation le
# refuserait de toute facon, mais apres un schema entier — et l'exploitant
# aurait une base a moitie deployee pour l'apprendre.
if ! decor_poser n4; then
  echoue "le decor N4 n'a pas pu etre pose"
else
suivre_decor
SORTIE_N4=$(
  ESC_PLAN_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  bash "$COMMANDE" 2>&1
)
CODE_N4=$?
RESTE_N4=$(admb -tAc "select count(*) from pg_class where relname = 'normative_control_plane'" 2>&1)
if [[ $CODE_N4 -ne 0 ]] && grep -qF "meme role" <<<"$SORTIE_N4" && [[ "$RESTE_N4" == "0" ]]; then
  echo "      ok: N4. deux acteurs identiques: refus avant toute application"
else
  echoue "N4. la commande a accepte deux acteurs identiques (code $CODE_N4,"
  echoue "    objets normatifs crees: $RESTE_N4)"
  grep -m2 -E "ECHEC|ok:" <<<"$SORTIE_N4" | sed 's/^/              /' >&2
fi
decor_deposer
fi

# ==========================================================================
# N1 + N2. LE DEPLOIEMENT COMPLET, ET SES POSTCONDITIONS
# ==========================================================================
if ! decor_poser n1; then
  echoue "le decor N1 n'a pas pu etre pose"
else
suivre_decor
# LA PHASE 0 CREE `eurostruct_deployment`; l'exploitant l'accorde ensuite au
# plan de controle. La commande est donc appelee DEUX FOIS dans le vrai
# enchainement: une premiere qui pose le sceau et s'arrete faute de droit sur
# la phase 2, puis l'octroi, puis la seconde qui va au bout.
#
# CE N'EST PAS UN ARTEFACT DE TEST. C'est l'ordre reel: `eurostruct_deployment`
# n'existe pas avant la phase 0, donc personne ne peut le detenir avant.
deployer >/dev/null 2>&1
adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1

if deployer; then
  echo "      ok: N1. le deploiement complet aboutit (exit 0)"

  # --- N2. LES POSTCONDITIONS, CONSTATEES PAR NOUS, PAS PAR ELLE ----------
  # Ce que la commande AFFICHE ne prouve rien: c'est elle qui l'ecrit. Ce qui
  # compte est l'etat de la base apres son passage, lu ici.
  ETAT=$(admb -tAc "select normative_activation_state()" 2>&1)
  RESIDU=$(admb -tAc "
    select count(*) from unnest(array['eurostruct_normative_writer',
                                      'eurostruct_normative_bootstrap',
                                      'eurostruct_normative_activator']) a(r)
     where pg_has_role('$MIG', a.r, 'SET') or pg_has_role('$MIG', a.r, 'USAGE')
        or pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
  PLAN_FIGE=$(admb -tAc "select role_name from normative_control_plane" 2>&1)
  ASSUR=$(admb -tAc "select assurance_level from normative_seal_metadata" 2>&1)

  [[ "$ETAT" == "ACTIVE" ]] \
    || echoue "N2. etat attendu ACTIVE, obtenu « $ETAT »"
  [[ "$RESIDU" == "0" ]] \
    || echoue "N2. le migrateur conserve $RESIDU capacite(s) sur les autorites"
  [[ "$PLAN_FIGE" == "$CTL" ]] \
    || echoue "N2. plan de controle fige « $PLAN_FIGE », attendu « $CTL »"
  [[ "$ASSUR" == "CONTAINED_NON_SUPERUSER" ]] \
    || echoue "N2. assurance « $ASSUR », attendue CONTAINED_NON_SUPERUSER"
  [[ $KO -eq 0 ]] && echo "      ok: N2. ACTIVE, 0 residu, plan « $CTL », assurance contenue"

  # --- N3. LA RELANCE EST SURE -------------------------------------------
  # LE CAS REEL: `psql` echoue sur une coupure, l'exploitant ne sait pas si la
  # transaction a ete validee, il relance. Ce qui doit se produire: rien de
  # nouveau, et surtout AUCUN emprunt reaccorde sur une base en service.
  if deployer; then
    RESIDU2=$(admb -tAc "
      select count(*) from unnest(array['eurostruct_normative_writer',
                                        'eurostruct_normative_bootstrap']) a(r)
       where pg_has_role('$MIG', a.r, 'SET') or pg_has_role('$MIG', a.r, 'USAGE')
          or pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
    ETAT2=$(admb -tAc "select normative_activation_state()" 2>&1)
    if [[ "$RESIDU2" == "0" && "$ETAT2" == "ACTIVE" ]]; then
      echo "      ok: N3. la relance sur une base finalisee ne reaccorde rien"
    else
      echoue "N3. la relance a laisse $RESIDU2 emprunt(s) et l'etat « $ETAT2 »"
    fi
  else
    echoue "N3. la relance sur une base deja finalisee a echoue:"
    grep -m3 -E "ECHEC" <<<"$SORTIE_CMD" | sed 's/^/              /' >&2
  fi
else
  echoue "N1. le deploiement complet a echoue:"
  tail -14 <<<"$SORTIE_CMD" | sed 's/^/              /' >&2
fi
decor_deposer
fi

# ==========================================================================
# N5. SCEAU SUPERUTILISATEUR: refus strict, acceptation degradee et DITE
# ==========================================================================
# UN SUPERUTILISATEUR DEDIE, ET NON `postgres`. Deux raisons, la seconde
# decisive:
#
#   * on n'emprunte pas les identifiants de l'administrateur du cluster pour un
#     test — ils ne sont pas a nous;
#   * `postgres` n'a pas necessairement de mot de passe, et la commande se
#     connecte en TCP. Premiere ecriture de ce scenario: « password
#     authentication failed for user postgres » — un echec de plomberie
#     presente comme un echec de securite.
if ! decor_poser n5; then
  echoue "le decor N5 n'a pas pu etre pose"
else
suivre_decor
SUP="${PREFIXE}_sn5_${JETON}"
if ! creer_role "$SUP" "login superuser password '$MDP'"; then
  echoue "N5. le superutilisateur du scenario n'a pas pu etre cree"
else
TOUS_ROLES+=("$SUP")
admb -v ON_ERROR_STOP=1 -c "grant create on schema public to \"$SUP\" with grant option;" \
  >/dev/null 2>&1
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG,$SUP';" >/dev/null 2>&1

# LA PHASE 0 EST POSEE PAR LE SUPERUTILISATEUR — forme auto-hebergee, legitime.
PGUSER="$SUP" PGPASSWORD="$MDP" psql -X -q -h localhost -p "${PGPORT:-5432}" -d "$BASE" \
  -v ON_ERROR_STOP=1 -f "$DB_DIR/control_plane/0001_normative_seal.sql" >/dev/null 2>&1
adm -c "grant eurostruct_deployment to \"$SUP\" with inherit true;" >/dev/null 2>&1

NIVEAU_N5=$(admb -tAc "select assurance_level from normative_seal_metadata" 2>&1)
if [[ "$NIVEAU_N5" != "UNCONTAINED_SUPERUSER" ]]; then
  echoue "N5. le sceau pose par un superutilisateur porte « $NIVEAU_N5 »;"
  echoue "    le scenario ne peut pas etre evalue"
else
# LE PLAN DE CONTROLE EST LE POSEUR, dans les deux appels. Une premiere version
# appelait la commande au nom d'un AUTRE role: elle refusait bien, mais sur
# SEAL_INSTALLER_MISMATCH — un refus correct, obtenu par une autre barriere, qui
# n'aurait rien dit du niveau d'assurance.
appel_n5() {
  ESC_PLAN_URL="postgresql://$SUP:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  bash "$COMMANDE" "$@" 2>&1
}

SORTIE_N5A=$(appel_n5); CODE_N5A=$?
ETAT_N5A=$(admb -tAc "select normative_activation_state()" 2>&1)
if [[ $CODE_N5A -ne 0 ]] && grep -qF "UNCONTAINED_SUPERUSER" <<<"$SORTIE_N5A" \
   && [[ "$ETAT_N5A" == "PENDING" ]]; then
  echo "      ok: N5. le mode strict refuse un sceau superutilisateur"
else
  echoue "N5. le mode strict n'a pas refuse sur l'assurance (code $CODE_N5A,"
  echoue "    etat « $ETAT_N5A »)"
  grep -m3 -E "ECHEC|AVERTISSEMENT" <<<"$SORTIE_N5A" | sed 's/^/              /' >&2
fi

# ET `--auto-heberge` L'ACCEPTE — en le DISANT. Sans cette moitie, « strict »
# ne serait qu'un refus systematique, et le produit resterait indeployable en
# auto-heberge.
SORTIE_N5B=$(appel_n5 --auto-heberge); CODE_N5B=$?
ETAT_N5B=$(admb -tAc "select normative_activation_state()" 2>&1)
if [[ $CODE_N5B -eq 0 && "$ETAT_N5B" == "ACTIVE" ]] \
   && grep -qi "degrade" <<<"$SORTIE_N5B"; then
  echo "      ok: N5. --auto-heberge aboutit, et annonce le mode degrade"
else
  echoue "N5. --auto-heberge: code $CODE_N5B, etat « $ETAT_N5B »"
  tail -8 <<<"$SORTIE_N5B" | sed 's/^/              /' >&2
fi
fi
fi
decor_deposer
fi

echo ""
echo "================================================="
if [[ $KO -eq 0 ]]; then
  echo " Commande officielle de deploiement verifiee."
  echo "================================================="
  exit 0
fi
echo " Commande officielle de deploiement: AU MOINS UN ECART."
echo "================================================="
exit 1
