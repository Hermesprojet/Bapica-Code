#!/usr/bin/env bash
#
# EUROSTRUCT — sonde de compatibilite du plan de controle
#              INTRUSIVE MAIS REVERSIBLE — STAGING UNIQUEMENT
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
# INTRUSIVE MAIS REVERSIBLE — a n'executer que sur un STAGING
# ------------------------------------------------------------
# La formulation precedente, « non destructive », etait trop confortable:
# cette sonde CREE et DETRUIT des roles. Elle ne touche ni au schema, ni aux
# donnees, ni a un role preexistant, et tout ce qu'elle cree elle le retire —
# mais elle ecrit dans le catalogue partage de l'instance. C'est intrusif, et
# ce doit etre dit ainsi.
#
# Les roles portent un suffixe ALEATOIRE propre a l'execution: deux sondes
# simultanees ne se croisent pas, et aucune ne peut detruire les roles d'une
# autre. Elle ne supprime JAMAIS un nom fixe. Si le nettoyage laisse quoi que
# ce soit, elle ECHOUE (code 3).
#
# CONSENTEMENT EXPLICITE REQUIS: sans EUROSTRUCT_PROBE_TARGET=staging, elle
# n'ouvre aucune connexion.
#
# CODES DE SORTIE
#   0  les quatre capacites sont confirmees
#   1  au moins une capacite manque
#   2  INCONCLUSIVE — rien n'a pu etre etabli (consentement, URL, connexion,
#      superutilisateur)
#   3  residu: des roles de sonde subsistent
set -euo pipefail

# --------------------------------------------------------------------------
# 0. CONSENTEMENT, avant tout acces reseau.
# --------------------------------------------------------------------------
if [[ "${EUROSTRUCT_PROBE_TARGET:-}" != "staging" ]]; then
  echo "REFUS: cette sonde cree et detruit des roles sur l'instance cible." >&2
  echo "       Elle n'est pas destinee a une base de production." >&2
  echo "       Pour l'autoriser: EUROSTRUCT_PROBE_TARGET=staging" >&2
  exit 2
fi

: "${DATABASE_URL:?DATABASE_URL doit etre fournie par la configuration}"

# --------------------------------------------------------------------------
# 1. Connexion SANS SECRET DANS LES ARGUMENTS DE PROCESSUS.
#
# `psql "$DATABASE_URL"` place le mot de passe dans argv, donc dans `ps` pour
# tout utilisateur de la machine. L'URL est donc decomposee en variables
# d'environnement libpq, et psql est invoque sans aucun argument de connexion.
#
# La sortie est CAPTUREE ET VERIFIEE avant tout `eval`. La version precedente
# faisait `eval "$(python ...)"` directement: une URL invalide produisait une
# sortie VIDE, `eval` ne faisait rien, aucune variable n'etait posee — et psql
# se rabattait sur les PG* ambiantes, donc potentiellement sur une AUTRE BASE
# que celle qu'on croyait sonder. Un echec de parsing doit arreter le script
# avant le premier appel a psql, pas le rediriger en silence.
# --------------------------------------------------------------------------
ERRPY="$(mktemp)"
if ! CONN="$(DATABASE_URL="$DATABASE_URL" python3 - 2>"$ERRPY" <<'FINPARSE'
import os, sys, shlex
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["DATABASE_URL"])
if u.scheme not in ("postgres", "postgresql"):
    sys.stderr.write("schema attendu postgres:// ou postgresql://\n"); sys.exit(2)
if not u.hostname:
    sys.stderr.write("hote absent de l'URL\n"); sys.exit(2)
if not u.username:
    sys.stderr.write("utilisateur absent de l'URL\n"); sys.exit(2)
base = unquote(u.path.lstrip("/"))
if not base:
    sys.stderr.write("nom de base absent de l'URL\n"); sys.exit(2)
q = parse_qs(u.query)
champs = {
    "PGHOST": u.hostname,
    "PGPORT": str(u.port or 5432),
    "PGUSER": unquote(u.username),
    "PGPASSWORD": unquote(u.password or ""),
    "PGDATABASE": base,
    "PGSSLMODE": q.get("sslmode", ["prefer"])[0],
}
for k, v in champs.items():
    print(f"export {k}={shlex.quote(v)}")
FINPARSE
)"; then
  echo "INCONCLUSIVE: DATABASE_URL inexploitable." >&2
  sed 's/^/   /' "$ERRPY" >&2
  rm -f "$ERRPY"
  exit 2
fi
rm -f "$ERRPY"

# La sortie doit avoir EXACTEMENT la forme attendue: on n'evalue pas du texte
# dont on n'a pas verifie la nature.
while IFS= read -r ligne; do
  [[ -n "$ligne" ]] || continue
  if ! [[ "$ligne" =~ ^export\ PG(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]]; then
    echo "INCONCLUSIVE: sortie de decoupage inattendue, evaluation refusee." >&2
    exit 2
  fi
done <<<"$CONN"

# AUCUN REPLI POSSIBLE. Les PG* ambiantes — et les redirections par service ou
# fichier de mots de passe — sont effacees AVANT d'appliquer celles de l'URL.
# Sans cela, une variable heritee de l'environnement pouvait designer une base
# differente de celle qu'on croit sonder.
unset PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE PGSSLMODE \
      PGSERVICE PGSERVICEFILE PGPASSFILE PGREQUIRESSL PGCHANNELBINDING
eval "$CONN"

for v in PGHOST PGUSER PGDATABASE; do
  if [[ -z "${!v:-}" ]]; then
    echo "INCONCLUSIVE: $v vide apres decoupage de l'URL." >&2
    exit 2
  fi
done

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
  # SIX octets pour DOUZE caracteres hexadecimaux. La version precedente en
  # lisait douze, produisait vingt-quatre caracteres, et la validation qui
  # suit refusait systematiquement: le repli sans openssl n'aurait jamais
  # fonctionne.
  JETON="$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
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
  # HOOK DE TEST, et rien d'autre. `supabase_probe_selftest.sh` s'en sert pour
  # exercer le chemin « nettoyage en echec -> code 3 », qu'aucune manipulation
  # externe ne peut declencher de facon deterministe: les noms sont aleatoires
  # et connus de la seule execution en cours. Sans valeur en production.
  if [[ "${EUROSTRUCT_PROBE_SKIP_CLEANUP:-}" == "1" ]]; then
    echo "  (nettoyage volontairement saute: hook de test)" >&2
    RESIDU=1
    return
  fi
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

# Rien de ce qui identifie precisement la cible ou son operateur n'est
# imprime: ni l'URL, ni le secret, ni l'utilisateur complet. Le compte rendu
# d'une sonde finit dans un journal de CI, un ticket, une capture d'ecran.
# Seuls l'hote et la base — assainis — suffisent a savoir OU l'on a sonde.
masquer() {
  local v="$1"
  if [[ ${#v} -le 2 ]]; then printf '%s' '***'
  else printf '%s***' "${v:0:2}"; fi
}
HOTE_SUR="$(masquer "$PGHOST")"
BASE_SURE="$(masquer "$PGDATABASE")"
echo " cible: hote $HOTE_SUR   base $BASE_SURE   PostgreSQL: $VERSION"
echo " plan de controle: $(masquer "$U")   superutilisateur: $SUPER   createrole: $CREATEROLE"
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
  oui "3. octroi au migrateur, donneur = le plan de controle (admin/set: ${DONNEUR#*/})"
else
  non "3. donneur inattendu: ${DONNEUR:+$(masquer "${DONNEUR%%/*}")/${DONNEUR#*/}}${DONNEUR:-aucun octroi}" \
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
