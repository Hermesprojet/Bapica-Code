#!/usr/bin/env bash
#
# EUROSTRUCT — sonde de compatibilite, NON DESTRUCTIVE
#
#   supabase_probe.sh            # lit $DATABASE_URL
#   DATABASE_URL=postgres://... ./supabase_probe.sh
#
# A QUOI ELLE SERT
# ----------------
# Le deploiement en deux phases (6.3b6) repose sur QUATRE capacites du plan de
# controle. Elles sont vraies sur un PostgreSQL 16 ordinaire — mesurees — mais
# PERSONNE NE LES A ENCORE CONSTATEES sur une instance Supabase reelle. Tant
# que cette sonde n'a pas tourne sur un staging, la compatibilite reste
# SUPABASE_UNVERIFIED et ne doit etre affirmee nulle part.
#
#   1. le role courant peut CREER des roles (CREATEROLE);
#   2. il peut PRECREER un role d'autorite;
#   3. il peut ACCORDER ce role a un tiers en restant le DONNEUR;
#   4. il peut REVOQUER cet octroi integralement — zero ligne restante.
#
# La quatrieme est la seule qui rende la finalisation possible. Elle a ete
# mesuree ainsi sur PostgreSQL 16:
#
#   role d'autorite cree par le MIGRATEUR       -> donneur=postgres, NON revocable
#   role d'autorite cree par le PLAN DE CONTROLE -> donneur=plan,    revocable
#
# NON DESTRUCTIVE, et verifiable
# -------------------------------
# Elle ne touche NI au schema, NI aux donnees, NI aux roles existants. Elle
# cree trois roles jetables prefixes `escprobe_`, les detruit, et n'ecrit
# aucune ligne dans aucune table. Si elle est interrompue, le `trap` nettoie;
# si le nettoyage echoue, elle le DIT plutot que de laisser croire le
# contraire.
#
# Elle ne modifie pas non plus le mot de passe ni les attributs d'un role
# existant: tout ce qu'elle manipule, elle l'a cree.
set -euo pipefail

PREFIXE=escprobe
CTL="${PREFIXE}_controle"
MIG="${PREFIXE}_migrateur"
AUT="${PREFIXE}_autorite"
MDP="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')x9"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "usage: DATABASE_URL=postgres://... $0" >&2
  exit 2
fi
SANS_QUERY="${DATABASE_URL%%\?*}"; QUERY=""
[[ "$DATABASE_URL" == *\?* ]] && QUERY="?${DATABASE_URL#*\?}"
HOTE="$(sed -E 's|^[^:]+://||; s|^[^@]*@||; s|/.*$||' <<<"$SANS_QUERY")"
BASE="${SANS_QUERY##*/}"

PSQL=(psql "$DATABASE_URL" -X -q -tA)
OK=0; KO=0
oui() { printf '  ok    %s\n' "$1"; OK=$((OK+1)); }
non() { printf '  NON   %s\n' "$1"; [[ -n "${2:-}" ]] && printf '        %s\n' "$2"; KO=$((KO+1)); }

nettoyer() {
  local r
  # Ordre: les octrois d'abord, les roles ensuite.
  "${PSQL[@]}" -c "revoke $AUT from $MIG;" >/dev/null 2>&1 || true
  for r in "$MIG" "$AUT" "$CTL"; do
    "${PSQL[@]}" -c "drop role if exists $r;" >/dev/null 2>&1 || true
  done
  local restants
  restants=$("${PSQL[@]}" -c \
    "select count(*) from pg_roles where rolname like '${PREFIXE}\\_%';" \
    2>/dev/null || echo '?')
  if [[ "$restants" != "0" ]]; then
    echo "  ATTENTION: $restants role(s) « ${PREFIXE}_* » n'ont pas pu etre" >&2
    echo "             detruits. A retirer a la main." >&2
  fi
}
trap nettoyer EXIT
nettoyer

echo "=============================================================="
echo " EUROSTRUCT — sonde de compatibilite du plan de controle"
echo "=============================================================="
echo " base: $BASE   hote: $HOTE"
echo

# --- 0. Contexte ----------------------------------------------------------
INFO=$("${PSQL[@]}" -c "
  select current_user || '|' ||
         (select rolsuper::text from pg_roles where rolname = current_user) || '|' ||
         (select rolcreaterole::text from pg_roles where rolname = current_user) || '|' ||
         (select rolcreatedb::text from pg_roles where rolname = current_user) || '|' ||
         current_setting('server_version');")
IFS='|' read -r U SUPER CREATEROLE CREATEDB VERSION <<<"$INFO"
echo " role courant: $U   superutilisateur: $SUPER"
echo " createrole: $CREATEROLE   createdb: $CREATEDB   PostgreSQL: $VERSION"
echo

if [[ "$SUPER" == "true" ]]; then
  echo " NOTE: ce role est SUPERUTILISATEUR. La sonde passera forcement, et"
  echo "       ne dira donc rien de la cible reelle. Rejouer avec le role de"
  echo "       migration/plan de controle du deploiement."
  echo
fi

# --- 1. CREATEROLE --------------------------------------------------------
if [[ "$CREATEROLE" == "true" || "$SUPER" == "true" ]]; then
  oui "1. le role courant peut creer des roles"
else
  non "1. le role courant n'a pas CREATEROLE" \
      "sans lui, il ne peut pas tenir le plan de controle"
fi

# --- 2. Precreation d'un role d'autorite ---------------------------------
if "${PSQL[@]}" -c "create role $CTL nologin;" >/dev/null 2>&1 \
   && "${PSQL[@]}" -c "create role $AUT nologin;" >/dev/null 2>&1; then
  oui "2. precreation d'un role d'autorite (NOLOGIN)"
else
  non "2. precreation impossible" "le plan de controle ne peut pas preparer la topologie"
fi

# --- 3. Octroi, le plan de controle restant DONNEUR -----------------------
if "${PSQL[@]}" -c "create role $MIG nologin;" >/dev/null 2>&1 \
   && "${PSQL[@]}" -c "grant $AUT to $MIG with admin option;" >/dev/null 2>&1; then
  DONNEUR=$("${PSQL[@]}" -c "
    select g.rolname || '/' || am.admin_option || '/' || am.set_option
      from pg_auth_members am
      join pg_roles r on r.oid = am.roleid
      join pg_roles m on m.oid = am.member
      join pg_roles g on g.oid = am.grantor
     where r.rolname = '$AUT' and m.rolname = '$MIG';" 2>/dev/null || echo '')
  if [[ "$DONNEUR" == "$U/"* ]]; then
    oui "3. octroi au migrateur, donneur = $U ($DONNEUR)"
  else
    non "3. le donneur de l'octroi n'est pas le role courant: ${DONNEUR:-aucun}" \
        "la finalisation ne pourra pas revoquer cet octroi"
  fi
else
  non "3. octroi impossible"
fi

# --- 4. Revocation INTEGRALE — la capacite decisive -----------------------
"${PSQL[@]}" -c "revoke $AUT from $MIG;" >/dev/null 2>&1 || true
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
      "la finalisation fail-closed est IMPOSSIBLE sur cette instance:" \

  echo "        c'est le cas ou l'option 3 doit etre reexaminee." >&2
fi

echo
echo "--------------------------------------------------------------"
printf " capacites confirmees: %d   manquantes: %d\n" "$OK" "$KO"
if [[ $KO -eq 0 ]]; then
  echo " Le plan de controle peut precreer, octroyer et revoquer."
  echo " La compatibilite reste SUPABASE_UNVERIFIED tant que la suite"
  echo " complete n'a pas tourne sur cette instance — cette sonde ne"
  echo " couvre que les capacites de roles."
else
  echo " Au moins une capacite manque: le deploiement en deux phases ne"
  echo " tient pas en l'etat sur cette instance."
fi
echo "--------------------------------------------------------------"
exit $(( KO > 0 ? 1 : 0 ))
