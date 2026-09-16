#!/usr/bin/env bash
#
# EUROSTRUCT — LE CONTENU D'UNE COPIE EST-IL CELUI DE LA SOURCE ? EXACTEMENT.
#
#   EUROSTRUCT_COMPARE_SOURCE_URL='postgresql://...' \
#   EUROSTRUCT_COMPARE_COPIE_URL='postgresql://...' \
#   db/test/comparer_contenu.sh table [table ...]
#
# CE QUE CE SCRIPT COMPARE
# -------------------------
# Pour chaque table, une EMPREINTE DE TOUTES SES LIGNES: chaque ligne rendue
# en texte, les lignes triees, le tout hache. Deux tables de meme contenu ont
# la meme empreinte; une VALEUR modifiee dans une ligne — a nombre de lignes
# egal — en change une. C'est ce qu'un compte de lignes, exact ou estime, ne
# peut pas voir.
#
# LE TEXTE D'UNE LIGNE DEPEND DE LA SESSION: fuseau horaire, style de date,
# chiffres des flottants, codage des octets. Les quatre sont FIXES dans la
# meme requete, des deux cotes, sinon deux sessions honnetes rendraient deux
# empreintes pour un meme contenu.
#
# LE LECTEUR DOIT CONTOURNER RLS, DES DEUX COTES, ET C'EST VERIFIE. Les tables
# de l'atelier sont sous RLS forcee: un role soumis aux politiques ne verrait
# qu'une partie des lignes — souvent aucune — et la comparaison de deux vues
# partielles pourrait dire « identique » de deux bases qui ne le sont pas. Le
# script REFUSE (code 2) plutot que de comparer sans voir. Les politiques,
# elles, restent posees: c'est le lecteur qui est privilegie, par attribut.
#
# AUCUN SECRET DANS `argv` NI DANS LA SORTIE. Les DSN sont lues dans deux
# variables, decoupees en variables libpq dans un sous-shell, jamais affichees.
#
# CODES: 0 toutes les tables identiques; 1 au moins une differe; 2 lecture
#        impossible (role soumis a RLS, table absente, connexion refusee);
#        4 variable ou table manquante en argument.
set -uo pipefail
set +x

avec_url() {   # avec_url <variable-d-url> <commande...>
  local var="$1"; shift
  local decoupe
  decoupe="$(URL="${!var}" python3 - <<'PY'
import os, shlex, sys
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["URL"])
if u.scheme not in ("postgres", "postgresql") or not u.hostname or not u.username:
    sys.exit(2)
q = parse_qs(u.query)
for k, v in {"PGHOST": u.hostname, "PGPORT": str(u.port or 5432),
             "PGUSER": unquote(u.username), "PGPASSWORD": unquote(u.password or ""),
             "PGDATABASE": unquote(u.path.lstrip("/")),
             "PGSSLMODE": q.get("sslmode", ["prefer"])[0]}.items():
    print(f"export {k}={shlex.quote(v)}")
PY
)" || return 2
  while IFS= read -r l; do
    [[ -z "$l" || "$l" =~ ^export\ PG(HOST|PORT|USER|PASSWORD|DATABASE|SSLMODE)= ]] \
      || return 2
  done <<<"$decoupe"
  ( eval "$decoupe"; unset PGSERVICE PGSERVICEFILE PGHOSTADDR PGPASSFILE PGOPTIONS
    "$@" )
}
sql() {   # sql <variable-d-url> <requete> — la derniere valeur, sans espaces
  avec_url "$1" psql -X -q -tA -v ON_ERROR_STOP=1 -c "$2" 2>/dev/null | tr -d ' \r'
}

for v in EUROSTRUCT_COMPARE_SOURCE_URL EUROSTRUCT_COMPARE_COPIE_URL; do
  [[ -n "${!v:-}" ]] || { echo "NON EXECUTE: $v manque." >&2; exit 4; }
done
(($# > 0)) || { echo "NON EXECUTE: aucune table a comparer." >&2; exit 4; }
for t in "$@"; do
  [[ "$t" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || { echo "NON EXECUTE: nom de table refuse." >&2; exit 4; }
done

# LE LECTEUR CONTOURNE-T-IL RLS ? Constate sur chaque cote avant de lire quoi
# que ce soit. `rolsuper` compte: un superutilisateur n'est jamais soumis.
for cote in SOURCE COPIE; do
  var="EUROSTRUCT_COMPARE_${cote}_URL"
  qui="$(sql "$var" "select current_user")"
  [[ -n "$qui" ]] || { echo "REFUS: connexion impossible cote ${cote,,}." >&2; exit 2; }
  contourne="$(sql "$var" "select (rolbypassrls or rolsuper) from pg_roles where rolname = current_user")"
  if [[ "$contourne" != "t" ]]; then
    echo "REFUS: cote ${cote,,}, le role « $qui » ne contourne pas RLS (ni BYPASSRLS ni" >&2
    echo "       superutilisateur): il ne verrait qu'une partie des lignes, et comparer" >&2
    echo "       deux vues partielles ne prouverait rien." >&2
    exit 2
  fi
done

# L'EMPREINTE D'UNE TABLE: « <lignes>:<md5> », ou « <lignes>:- » si elle est
# vide. Les reglages de session sont poses dans la MEME chaine de commande:
# psql rend le resultat du dernier ordre, et les SET l'ont precede dans la
# meme transaction.
empreinte() {   # empreinte <variable-d-url> <table>
  sql "$1" "set timezone to 'UTC'; set datestyle to 'ISO, YMD';
            set extra_float_digits to 3; set bytea_output to 'hex';
            set intervalstyle to 'postgres';
            select count(*) || ':' || coalesce(md5(string_agg(t::text, E'\n' order by t::text)), '-')
              from $2 t" | tr -d '\n'
}

printf '  %-34s %8s %8s  %s\n' TABLE SOURCE COPIE VERDICT
KO=0; TOTAL=0
for t in "$@"; do
  s="$(empreinte EUROSTRUCT_COMPARE_SOURCE_URL "$t")"
  c="$(empreinte EUROSTRUCT_COMPARE_COPIE_URL "$t")"
  if [[ ! "$s" =~ ^[0-9]+:([0-9a-f]{32}|-)$ || ! "$c" =~ ^[0-9]+:([0-9a-f]{32}|-)$ ]]; then
    printf '  %-34s %8s %8s  %s\n' "$t" "?" "?" "ERREUR: table illisible d'un cote (absente, ou lecture refusee)"
    exit 2
  fi
  ns="${s%%:*}"; hs="${s#*:}"
  nc="${c%%:*}"; hc="${c#*:}"
  TOTAL=$((TOTAL + ns))
  if [[ "$s" == "$c" ]]; then
    printf '  %-34s %8s %8s  identique (%s)\n' "$t" "$ns" "$nc" "${hs:0:12}"
  else
    KO=1
    printf '  %-34s %8s %8s  DIFFERENT (source %s, copie %s)\n' "$t" "$ns" "$nc" "${hs:0:12}" "${hc:0:12}"
  fi
done
echo "TOTAL $TOTAL"
if ((KO)); then
  echo "  Au moins une table restauree ne porte pas le contenu de la source."
  exit 1
fi
echo "  Contenu identique, table par table, sur $TOTAL ligne(s) au total."
exit 0
