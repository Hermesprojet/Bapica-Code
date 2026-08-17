#!/usr/bin/env bash
#
# EUROSTRUCT — sonde de compatibilite du plan de controle, NON DESTRUCTIVE
#
#   DATABASE_URL=postgres://... ./supabase_probe.sh
#
# A EXECUTER DEPUIS UN ENVIRONNEMENT SECURISE, avec le secret fourni par la
# configuration. Ne jamais coller d'URL ni de mot de passe dans un echange.
#
# A QUOI ELLE SERT
# ----------------
# Le deploiement en deux phases repose sur QUATRE capacites du role connecte,
# qui tient le PLAN DE CONTROLE. Elles sont mesurees sur PostgreSQL 16, mais
# personne ne les a constatees sur une instance Supabase reelle: tant que
# cette sonde n'a pas tourne sur un staging, la compatibilite reste
# SUPABASE_UNVERIFIED et ne doit etre affirmee nulle part.
#
#   1. CREATEROLE;
#   2. precreation d'un role d'autorite;
#   3. octroi a un tiers en restant le DONNEUR de l'octroi;
#   4. revocation integrale de cet octroi — zero ligne restante.
#
# La quatrieme est la seule qui rende la finalisation possible, et elle
# depend de QUI a cree le role. Mesure sur PostgreSQL 16:
#
#   autorite creee par le MIGRATEUR        -> donneur=postgres, NON revocable
#   autorite creee par le PLAN DE CONTROLE -> donneur=plan,     revocable
#
# MODELE, EXPLICITE
# -----------------
# LE ROLE CONNECTE EST LE PLAN DE CONTROLE. Il n'y a pas de troisieme role:
# une version precedente creait un `escprobe_controle` qu'elle n'utilisait
# jamais — les octrois partaient du role connecte — et le compte rendu
# laissait croire le contraire.
#
# NON DESTRUCTIVE, et verifiable
# -------------------------------
# Elle ne touche NI au schema, NI aux donnees, NI a un role preexistant. Les
# deux roles qu'elle cree portent un suffixe ALEATOIRE propre a l'execution:
# deux sondes simultanees ne se croisent pas, et aucune ne peut detruire les
# roles d'une autre. Elle ne supprime JAMAIS un nom fixe — une version
# precedente commencait par « drop role escprobe_* », ce qui aurait efface
# les roles d'une sonde concurrente, voire d'un tiers homonyme.
#
# Si le nettoyage laisse quoi que ce soit, la sonde ECHOUE: un residu sur une
# instance cliente n'est pas un detail cosmetique.
#
# CODES DE SORTIE
#   0  les quatre capacites sont confirmees
#   1  au moins une capacite manque
#   2  INCONCLUSIVE — rien n'a pu etre etabli (superutilisateur, connexion)
#   3  residu: des roles de sonde subsistent
set -euo pipefail

# --------------------------------------------------------------------------
# Connexion SANS SECRET DANS LES ARGUMENTS DE PROCESSUS.
#
# `psql "$DATABASE_URL"` place le mot de passe dans argv, donc dans `ps` pour
# tout utilisateur de la machine. L'URL est donc decomposee en variables
# d'environnement liblibpq, et psql est invoque sans aucun argument de
# connexion. Le decoupage se fait en Python, qui lit l'URL depuis
# l'ENVIRONNEMENT et non depuis sa ligne de commande.
# --------------------------------------------------------------------------
: "${DATABASE_URL:?DATABASE_URL doit etre fournie par la configuration}"

eval "$(DATABASE_URL="$DATABASE_URL" python3 - <<'PY'
import os, sys, shlex
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["DATABASE_URL"])
if u.scheme not in ("postgres", "postgresql"):
    sys.stderr.write("DATABASE_URL: schema attendu postgres://\n"); sys.exit(2)
champs = {
    "PGHOST": u.hostname or "",
    "PGPORT": str(u.port or 5432),
    "PGUSER": unquote(u.username or ""),
    "PGPASSWORD": unquote(u.password or ""),
    "PGDATABASE": unquote(u.path.lstrip("/")) or "postgres",
}
q = parse_qs(u.query)
if "sslmode" in q:
    champs["PGSSLMODE"] = q["sslmode"][0]
for k, v in champs.items():
    if v != "":
        print(f"export {k}={shlex.quote(v)}")
PY
)"

# Delais: une sonde ne doit jamais rester pendue sur une instance distante.
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
export PGOPTIONS="${PGOPTIONS:-} -c statement_timeout=15s -c lock_timeout=5s -c idle_in_transaction_session_timeout=15s"

# Aucun argument de connexion: tout vient de l'environnement.
PSQL=(psql -X -q -tA -v ON_ERROR_STOP=1)

# --------------------------------------------------------------------------
# Noms UNIQUES et IMPREVISIBLES, propres a cette execution.
# --------------------------------------------------------------------------
if command -v openssl >/dev/null 2>&1; then
  JETON="$(openssl rand -hex 6)"
else
  JETON="$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
[[ "$JETON" =~ ^[0-9a-f]{12}$ ]] || { echo "aleatoire indisponible" >&2; exit 2; }

AUT="escprobe_a_${JETON}"      # role d'autorite fictif
MIG="escprobe_m_${JETON}"      # migrateur fictif
CREES=()                       # ce que CETTE execution a cree, et rien d'autre

OK=0; KO=0
oui() { printf '  ok    %s\n' "$1"; OK=$((OK+1)); }
non() { printf '  NON   %s\n' "$1"; [[ -n "${2:-}" ]] && printf '        %s\n' "$2"; KO=$((KO+1)); }

RESIDU=0
nettoyer() {
  local r
  # L'octroi d'abord, les roles ensuite — et UNIQUEMENT ceux de cette
  # execution. Aucun nom fixe n'est jamais detruit.
  "${PSQL[@]}" -c "revoke \"$AUT\" from \"$MIG\";" >/dev/null 2>&1 || true
  for r in "${CREES[@]:-}"; do
    [[ -n "$r" ]] || continue
    "${PSQL[@]}" -c "drop role if exists \"$r\";" >/dev/null 2>&1 || true
  done
  # RIEN CREE, RIEN A NETTOYER. Sans cette garde, une connexion refusee — ou
  # tout arret avant la premiere creation — annoncait un « residu » alors
  # qu'aucun role n'avait jamais existe: un diagnostic faux, et un code de
  # sortie qui accusait la mauvaise chose.
  if [[ ${#CREES[@]} -eq 0 ]]; then
    return
  fi

  # Et on CONSTATE. Un residu sur une instance cliente doit faire echouer la
  # sonde, pas partir dans un avertissement que personne ne lit.
  local restants
  restants=$("${PSQL[@]}" -c \
    "select count(*) from pg_roles where rolname like 'escprobe\\_%\\_${JETON}';" \
    2>/dev/null || echo '?')
  if [[ "$restants" == "?" ]]; then
    echo "  RESIDU INDETERMINE: la base n'a pas repondu au controle final." >&2
    echo "          Verifier a la main les roles portant le jeton $JETON." >&2
    RESIDU=1
  elif [[ "$restants" != "0" ]]; then
    echo "  RESIDU: $restants role(s) de cette sonde subsistent (jeton $JETON)." >&2
    echo "          A retirer: drop role ...; puis relancer." >&2
    RESIDU=1
  fi
}
trap 'nettoyer; [[ $RESIDU -eq 0 ]] || exit 3' EXIT

echo "=============================================================="
echo " EUROSTRUCT — sonde du plan de controle   (jeton $JETON)"
echo "=============================================================="

# --- 0. Contexte, et refus d'un verdict qui ne prouverait rien ------------
if ! INFO=$("${PSQL[@]}" -c "
  select current_user || '|' ||
         (select rolsuper::text from pg_roles where rolname = current_user) || '|' ||
         (select rolcreaterole::text from pg_roles where rolname = current_user) || '|' ||
         current_setting('server_version');" 2>&1); then
  echo " INCONCLUSIVE: connexion impossible." >&2
  printf '   %s\n' "$INFO" >&2
  exit 2
fi
IFS='|' read -r U SUPER CREATEROLE VERSION <<<"$INFO"
echo " plan de controle: $U    PostgreSQL: $VERSION"
echo " superutilisateur: $SUPER    createrole: $CREATEROLE"
echo

if [[ "$SUPER" == "true" ]]; then
  echo " INCONCLUSIVE — le role connecte est SUPERUTILISATEUR."
  echo
  echo " Les quatre capacites passeraient forcement, et ne diraient rien de"
  echo " la cible: un superutilisateur satisfait pg_has_role pour tout role"
  echo " et revoque n'importe quel octroi. Rejouer avec le role de plan de"
  echo " controle du deploiement, qui n'est pas superutilisateur."
  exit 2
fi

# --- 1. CREATEROLE --------------------------------------------------------
if [[ "$CREATEROLE" == "true" ]]; then
  oui "1. CREATEROLE"
else
  non "1. pas de CREATEROLE" "le role connecte ne peut pas tenir le plan de controle"
fi

# --- 2. Precreation d'un role d'autorite ---------------------------------
if "${PSQL[@]}" -c "create role \"$AUT\" nologin;" >/dev/null 2>&1; then
  CREES+=("$AUT"); oui "2. precreation d'un role d'autorite (NOLOGIN)"
else
  non "2. precreation impossible" "le plan de controle ne peut pas preparer la topologie"
fi

# --- 3. Octroi, le plan de controle restant DONNEUR -----------------------
DONNEUR=""
if "${PSQL[@]}" -c "create role \"$MIG\" nologin;" >/dev/null 2>&1; then
  CREES+=("$MIG")
  if "${PSQL[@]}" -c "grant \"$AUT\" to \"$MIG\" with admin option;" >/dev/null 2>&1; then
    DONNEUR=$("${PSQL[@]}" -c "
      select g.rolname || '/' || am.admin_option || '/' || am.set_option
        from pg_auth_members am
        join pg_roles r on r.oid = am.roleid
        join pg_roles m on m.oid = am.member
        join pg_roles g on g.oid = am.grantor
       where r.rolname = '$AUT' and m.rolname = '$MIG';" 2>/dev/null || echo '')
  fi
fi
if [[ "$DONNEUR" == "$U/"* ]]; then
  oui "3. octroi au migrateur, donneur = $U ($DONNEUR)"
else
  non "3. donneur inattendu: ${DONNEUR:-aucun octroi}" \
      "la finalisation ne pourrait pas revoquer cet octroi"
fi

# --- 4. Revocation INTEGRALE — la capacite decisive -----------------------
"${PSQL[@]}" -c "revoke \"$AUT\" from \"$MIG\";" >/dev/null 2>&1 || true
RESTE=$("${PSQL[@]}" -c "
  select (select count(*) from pg_auth_members am
            join pg_roles r on r.oid = am.roleid
            join pg_roles m on m.oid = am.member
           where r.rolname = '$AUT' and m.rolname = '$MIG')::text || '/' ||
         pg_has_role('$MIG', '$AUT', 'MEMBER')::text || '/' ||
         pg_has_role('$MIG', '$AUT', 'USAGE')::text;" 2>/dev/null || echo '?/?/?')
if [[ "$RESTE" == "0/false/false" ]]; then
  oui "4. revocation integrale: zero ligne, ni MEMBER ni USAGE"
else
  non "4. revocation INCOMPLETE (lignes/MEMBER/USAGE = $RESTE)" \
      "la finalisation fail-closed est impossible: reexaminer l'option 3"
fi

echo
echo "--------------------------------------------------------------"
printf " confirmees: %d   manquantes: %d\n" "$OK" "$KO"
if [[ $KO -eq 0 ]]; then
  echo " Le plan de controle peut precreer, octroyer et revoquer."
  echo " La compatibilite reste SUPABASE_UNVERIFIED: cette sonde ne couvre"
  echo " que les capacites de roles, pas la suite complete."
else
  echo " Le deploiement en deux phases ne tient pas sur cette instance."
fi
echo "--------------------------------------------------------------"
exit $(( KO > 0 ? 1 : 0 ))
