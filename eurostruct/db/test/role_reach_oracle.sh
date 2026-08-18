#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6a: ORACLE COMPORTEMENTAL DES PRIMITIVES DE PORTEE
#
#   role_reach_oracle.sh <nom-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `assert_normative_topology()` decide qui atteint un role d'autorite au moyen
# de trois primitives de PostgreSQL 16:
#
#     pg_has_role(porteur, cible, 'SET')                       endosser
#     pg_has_role(porteur, cible, 'USAGE')                     heriter
#     pg_has_role(porteur, cible, 'MEMBER WITH ADMIN OPTION')  readministrer
#
# Une version precedente calculait la meme chose par une fermeture recursive
# maison sur `pg_auth_members`. Elle a ete retiree — reimplementer la semantique
# du moteur, c'est se donner le droit d'en diverger en silence.
#
# Mais remplacer une formule par une autre ne prouve rien: deux ecritures
# fausses de la meme facon concordent parfaitement. Ce fichier confronte donc
# le DIAGNOSTIC a ce qui se PASSE REELLEMENT, sur une vraie connexion:
#
#   * SET    -> `SET ROLE cible` doit reussir si et seulement si SET est vrai;
#   * USAGE  -> un privilege detenu par la SEULE cible doit etre utilisable,
#               SANS `SET ROLE`, si et seulement si USAGE est vrai;
#   * ADMIN  -> `GRANT cible TO tiers` doit aboutir — et la ligne exister — si
#               et seulement si ADMIN est vrai.
#
# LES SIX FORMES DE GRAPHE
# -------------------------
#   1. direct                 porteur -> cible
#   2. deux sauts             porteur -> relais -> cible
#   3. ADMIN seul             admin sans set ni inherit
#   4. INHERIT seul           inherit sans set
#   5. ADMIN intermediaire    l'ADMIN est detenu par le relais, pas par le
#                             porteur
#   6. diamant                deux chemins disjoints vers la meme cible
#
# Aucune de ces formes n'est theorique: 3 et 5 sont exactement ce que
# PostgreSQL 16 fabrique tout seul quand un role en cree un autre, et 6 est ce
# qu'un deploiement produit des qu'il ajoute un chemin « juste pour debloquer
# un incident ».
#
# Toutes les identites sont FICTIVES.
set -uo pipefail

DB="${1:?usage: role_reach_oracle.sh <nom-de-base-jetable>}"
if ! [[ "$DB" =~ ^[a-zA-Z_][a-zA-Z0-9_]{0,62}$ ]]; then
  echo "      ECHEC: nom de base « $DB » invalide" >&2
  exit 2
fi

MDP='FICTIF-oracle'
PREFIXE=oracle_

if [[ -n "${DATABASE_URL:-}" ]]; then
  SANS_QUERY="${DATABASE_URL%%\?*}"
  BASE_URL="${SANS_QUERY%/*}"
  ADMIN=(psql "$DATABASE_URL")
  ADMIN_DB=(psql "${BASE_URL}/${DB}")
  HOTE="$(sed -E 's|^[^:]+://||; s|^[^@]*@||; s|/.*$||' <<<"$BASE_URL")"
else
  # Une socket unix ne permet pas l'authentification par mot de passe telle
  # qu'elle est configuree ici; les porteurs se connectent donc par TCP.
  ADMIN=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d postgres)
  ADMIN_DB=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$DB")
  HOTE=127.0.0.1
fi

KO=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }

# Connexion SOUS LE PORTEUR, et non `SET ROLE` depuis une session
# superutilisateur: c'est la seule facon d'exercer reellement la portee. Une
# session superutilisateur qui prend un role conserve des pouvoirs internes et
# aurait rendu tous les oracles vrais.
sous() {
  local role="$1"; shift
  PGPASSWORD="$MDP" psql -X -q -h "$HOTE" -U "$role" -d "$DB" "$@"
}

ROLES=()
nettoyer() {
  "${ADMIN[@]}" -X -q -c "drop database if exists $DB;" >/dev/null 2>&1
  local r
  for r in $("${ADMIN[@]}" -X -q -tAc \
      "select rolname from pg_roles where rolname like '${PREFIXE}%'" 2>/dev/null); do
    # Forme verifiee AVANT toute destruction: le motif vient du catalogue, mais
    # il ne doit pouvoir designer que des roles de ce fichier.
    [[ "$r" =~ ^oracle_[a-z0-9_]{1,40}$ ]] || continue
    "${ADMIN[@]}" -X -q -c "drop owned by \"$r\";" >/dev/null 2>&1
    "${ADMIN[@]}" -X -q -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}
trap nettoyer EXIT
nettoyer

"${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 -c "create database $DB;" >/dev/null || {
  echoue "creation de la base impossible"; exit 1; }

echo "    oracle comportemental des primitives de portee"

# --------------------------------------------------------------------------
# LE SUJET DE L'ORACLE « USAGE »
# --------------------------------------------------------------------------
# Un privilege que SEULE la cible detient. S'il devient utilisable par le
# porteur sans `SET ROLE`, c'est qu'il a herite — et rien d'autre ne peut
# l'expliquer.
"${ADMIN_DB[@]}" -X -q -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
create table t_oracle_prive (n int);
insert into t_oracle_prive values (1);
revoke all on t_oracle_prive from public;
SQL

# --------------------------------------------------------------------------
# Un cas = une forme de graphe, un porteur, une cible, et le triplet attendu
# --------------------------------------------------------------------------
# Le triplet attendu est ECRIT A LA MAIN, a partir de la semantique
# documentee — jamais recopie de `pg_has_role`, ce qui ferait comparer la
# fonction a elle-meme.
#
#   forme|porteur|cible|set_attendu|usage_attendu|admin_attendu|construction SQL
CAS=()
# Les triplets REELLEMENT observes, remplis par la boucle.
OBSERVES=()

CAS+=("direct|d_p|d_c|t|t|f|
  grant ${PREFIXE}d_c to ${PREFIXE}d_p;")

CAS+=("deux sauts|x_p|x_c|t|t|f|
  grant ${PREFIXE}x_r to ${PREFIXE}x_p;
  grant ${PREFIXE}x_c to ${PREFIXE}x_r;")

CAS+=("ADMIN seul|a_p|a_c|f|f|t|
  grant ${PREFIXE}a_c to ${PREFIXE}a_p with admin true, inherit false, set false;")

CAS+=("INHERIT seul|i_p|i_c|f|t|f|
  grant ${PREFIXE}i_c to ${PREFIXE}i_p with inherit true, set false;")

# L'ADMIN est chez le RELAIS. Le porteur ne l'atteint que s'il peut endosser ou
# heriter du relais — ici il herite, donc il obtient l'ADMIN transitivement.
CAS+=("ADMIN intermediaire|m_p|m_c|f|f|t|
  grant ${PREFIXE}m_r to ${PREFIXE}m_p;
  grant ${PREFIXE}m_c to ${PREFIXE}m_r with admin true, inherit false, set false;")

# Diamant: une branche n'apporte que l'heritage, l'autre que l'ADMIN. La
# reunion des deux doit etre observee — c'est le cas qu'une recursion mal
# ecrite manque, en s'arretant au premier chemin trouve.
CAS+=("diamant|g_p|g_c|f|t|t|
  grant ${PREFIXE}g_r1 to ${PREFIXE}g_p;
  grant ${PREFIXE}g_r2 to ${PREFIXE}g_p;
  grant ${PREFIXE}g_c to ${PREFIXE}g_r1 with inherit true, set false;
  grant ${PREFIXE}g_c to ${PREFIXE}g_r2 with admin true, inherit false, set false;")

# Le TEMOIN NEGATIF. Sans lui, un oracle qui rendrait « vrai » partout
# passerait les six formes: il faut au moins une paire dont on exige que TOUT
# soit faux.
CAS+=("aucun chemin|n_p|n_c|f|f|f|
  select 1;")

for entree in "${CAS[@]}"; do
  # `read` s'arrete a la premiere fin de ligne: le SQL de construction, ecrit
  # sur plusieurs lignes pour rester lisible, arrivait donc VIDE. Aucun graphe
  # n'etait construit, les sept cas rendaient « fff », et six d'entre eux
  # echouaient — pour la mauvaise raison. Les sauts de ligne sont replies ici.
  IFS='|' read -r forme porteur cible att_set att_usage att_admin sql \
    <<<"${entree//$'\n'/ }"

  # Les roles de la forme: le porteur se connecte, les autres non. Les relais
  # sont deduits du SQL de construction — aucune liste a tenir a jour.
  RELAIS=$(grep -oE "${PREFIXE}[a-z0-9_]+" <<<"$sql" | sort -u)
  "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 -c \
    "create role \"${PREFIXE}${porteur}\" login password '$MDP';" >/dev/null
  "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 -c \
    "create role \"${PREFIXE}tiers_${porteur}\" nologin;" >/dev/null
  for r in $RELAIS; do
    [[ "$r" == "${PREFIXE}${porteur}" ]] && continue
    "${ADMIN[@]}" -X -q -c "create role \"$r\" nologin;" >/dev/null 2>&1
  done
  "${ADMIN[@]}" -X -q -c "create role \"${PREFIXE}${cible}\" nologin;" >/dev/null 2>&1
  "${ADMIN_DB[@]}" -X -q -c \
    "grant select on t_oracle_prive to \"${PREFIXE}${cible}\";" >/dev/null
  "${ADMIN[@]}" -X -q -v ON_ERROR_STOP=1 -c "$sql" >/dev/null || {
    echoue "$forme: construction du graphe impossible"; continue; }
  # Le porteur doit pouvoir se connecter A LA BASE, sinon les trois oracles
  # echoueraient tous pour la meme raison etrangere au sujet.
  "${ADMIN[@]}" -X -q -c \
    "grant connect on database $DB to \"${PREFIXE}${porteur}\";" >/dev/null

  # --- LE DIAGNOSTIC, tel que la migration le calcule ---------------------
  DIAG=$("${ADMIN_DB[@]}" -X -q -tAc "
    select pg_has_role('${PREFIXE}${porteur}', '${PREFIXE}${cible}', 'SET')::text
        || '|' ||
           pg_has_role('${PREFIXE}${porteur}', '${PREFIXE}${cible}', 'USAGE')::text
        || '|' ||
           pg_has_role('${PREFIXE}${porteur}', '${PREFIXE}${cible}',
                       'MEMBER WITH ADMIN OPTION')::text")
  IFS='|' read -r vu_set vu_usage vu_admin <<<"$DIAG"
  vu_set=${vu_set:0:1}; vu_usage=${vu_usage:0:1}; vu_admin=${vu_admin:0:1}

  ATTENDU="$att_set$att_usage$att_admin"
  OBTENU="$vu_set$vu_usage$vu_admin"
  if [[ "$OBTENU" != "$ATTENDU" ]]; then
    echoue "$forme: diagnostic attendu set/usage/admin=$ATTENDU, obtenu $OBTENU"
    continue
  fi

  # --- ORACLE 1: SET ROLE, pour de vrai ----------------------------------
  if sous "${PREFIXE}${porteur}" -c "set role \"${PREFIXE}${cible}\"" >/dev/null 2>&1
  then reel_set=t; else reel_set=f; fi

  # --- ORACLE 2: l'heritage, sans SET ROLE -------------------------------
  # Le privilege est detenu par la SEULE cible. Le lire sans l'endosser ne peut
  # venir que de l'heritage.
  if sous "${PREFIXE}${porteur}" -c 'select n from t_oracle_prive' >/dev/null 2>&1
  then reel_usage=t; else reel_usage=f; fi

  # --- ORACLE 3: GRANT cible TO tiers, pour de vrai -----------------------
  # PostgreSQL n'echoue pas toujours: sans droit il peut emettre un simple
  # avertissement. On ne lit donc PAS le code de sortie — on regarde si la
  # ligne existe.
  sous "${PREFIXE}${porteur}" -c \
    "grant \"${PREFIXE}${cible}\" to \"${PREFIXE}tiers_${porteur}\"" >/dev/null 2>&1
  LIGNE=$("${ADMIN[@]}" -X -q -tAc "
    select count(*) from pg_auth_members m
      join pg_roles a on a.oid = m.roleid
      join pg_roles p on p.oid = m.member
     where a.rolname = '${PREFIXE}${cible}'
       and p.rolname = '${PREFIXE}tiers_${porteur}'")
  if [[ "$LIGNE" == "0" ]]; then reel_admin=f; else reel_admin=t; fi

  REEL="$reel_set$reel_usage$reel_admin"
  if [[ "$REEL" != "$OBTENU" ]]; then
    echoue "$forme: le diagnostic dit $OBTENU, le comportement reel est $REEL"
    echoue "  (SET ROLE / heritage sans SET ROLE / GRANT a un tiers)"
    continue
  fi
  OBSERVES+=("$OBTENU")
  echo "      ok: $forme — diagnostic $OBTENU confirme par le comportement reel"
done

# --------------------------------------------------------------------------
# CE QUE LES SIX FORMES NE DISENT PAS, ET QU'IL FAUT DIRE
# --------------------------------------------------------------------------
# Les oracles ci-dessus confirment le diagnostic. Ils ne prouvent pas que les
# formes couvrent quelque chose: si toutes rendaient le meme triplet, la suite
# serait verte sans rien discriminer.
#
# Les triplets sont donc ceux REELLEMENT OBSERVES, accumules dans la boucle.
# Une premiere version les recopiait a la main dans un `printf` — un controle
# qui ne pouvait pas echouer, puisqu'il ne lisait rien de ce qui s'etait passe.
# C'est precisement la forme de test que ce projet refuse ailleurs.
DISTINCTS=$(printf '%s\n' "${OBSERVES[@]}" | sort -u | wc -l)
if [[ "${#OBSERVES[@]}" -ne "${#CAS[@]}" ]]; then
  echoue "seuls ${#OBSERVES[@]} cas sur ${#CAS[@]} ont produit un triplet:"
  echoue "  les autres se sont arretes avant l'observation."
fi
# Chacune des trois primitives doit apparaitre vraie AU MOINS UNE FOIS et
# fausse au moins une fois: sans cela, une primitive constamment ignoree
# passerait la suite sans jamais etre exercee.
for i in 0 1 2; do
  nom=(SET USAGE ADMIN); vus=""
  for t in "${OBSERVES[@]}"; do vus="$vus${t:$i:1}"; done
  [[ "$vus" == *t* ]] || echoue "la primitive ${nom[$i]} n'est jamais vraie: non exercee"
  [[ "$vus" == *f* ]] || echoue "la primitive ${nom[$i]} n'est jamais fausse: non discriminante"
done
if [[ "$DISTINCTS" -lt 4 ]]; then
  echoue "les formes de graphe ne produisent que $DISTINCTS triplet(s) distinct(s):"
  echoue "  la suite ne discrimine pas les trois primitives."
fi

echo ""
if [[ $KO -eq 0 ]]; then
  echo "================================================="
  echo " Portee des roles: diagnostic et comportement"
  echo " reel concordent sur six formes de graphe."
  echo "================================================="
  exit 0
fi
echo "================================================="
echo " Oracle de portee: au moins un ecart constate."
echo "================================================="
exit 1
