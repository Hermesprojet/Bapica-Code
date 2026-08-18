#!/usr/bin/env bash
#
# EUROSTRUCT — auto-tests de `supabase_probe.sh`
#
#   PGHOST=127.0.0.1 PGUSER=postgres PGPASSWORD=... ./supabase_probe_selftest.sh
#
# POURQUOI UNE SONDE A BESOIN DE SES PROPRES TESTS
# ------------------------------------------------
# Elle tournera sur l'instance d'un client, une fois, sous le regard de
# quelqu'un qui ne lira pas son code. Ses modes de panne comptent donc autant
# que son chemin nominal.
#
# CE FICHIER A DEJA ETE FAUTIF, ET DEUX FOIS DE LA MEME FACON
# ------------------------------------------------------------
# La version precedente reintroduisait exactement ce qu'on venait de retirer
# de la sonde:
#
#   * `drop role if exists selftest_cp` — un NOM FIXE. Deux auto-tests
#     simultanes se detruisaient l'un l'autre, et un homonyme tiers etait
#     efface;
#   * `... where rolname like 'escprobe%'` suivi d'un DROP par ligne — une
#     destruction pilotee par JOKER, qui emportait les roles des executions
#     concurrentes de la sonde elle-meme.
#
# REGLES QUE CE FICHIER S'IMPOSE DESORMAIS
#
#   1. tout role cree porte un suffixe aleatoire propre a l'execution;
#   2. AUCUN `DROP` n'est jamais construit depuis un `LIKE`. Les seuls noms
#      detruits sont ceux, exacts, que cette execution connait;
#   3. la verification d'absence de residu porte sur ces memes noms exacts;
#   4. l'auto-test refuse de tourner hors boucle locale, sauf consentement
#      explicite designant une base jetable.
#
# Ces auto-tests s'executent contre le PostgreSQL LOCAL de la suite. Ils ne
# touchent aucune instance distante.
set -euo pipefail
set +x

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SONDE="$HERE/supabase_probe.sh"
TMP="$(mktemp -d)"

PGH="${PGHOST:-127.0.0.1}"
PGU="${PGUSER:-postgres}"
PGP="${PGPASSWORD:-postgres}"
PORT="${PGPORT:-5432}"
BASE="${PGDATABASE:-postgres}"

# --------------------------------------------------------------------------
# 4. BOUCLE LOCALE EXIGEE.
#
# Ces auto-tests creent des roles et exercent volontairement un chemin qui en
# LAISSE derriere lui. Sur une instance partagee, c'est inacceptable. Le seul
# echappatoire est explicite et nomme la base jetable visee.
# --------------------------------------------------------------------------
case "$PGH" in
  127.0.0.1|::1|localhost|/*) LOCAL=1 ;;
  *) LOCAL=0 ;;
esac
if [[ $LOCAL -eq 0 ]]; then
  if [[ "${EUROSTRUCT_SELFTEST_DISPOSABLE_DB:-}" != "$BASE" ]]; then
    echo "      REFUS: auto-tests hors boucle locale (hote non local)." >&2
    echo "             Ils creent des roles et en laissent volontairement." >&2
    echo "             Pour forcer sur une base JETABLE:" >&2
    echo "             EUROSTRUCT_SELFTEST_DISPOSABLE_DB=<nom-de-la-base>" >&2
    exit 2
  fi
fi

# --------------------------------------------------------------------------
# 1. Nom ALEATOIRE pour le plan de controle de l'auto-test.
# --------------------------------------------------------------------------
if command -v openssl >/dev/null 2>&1; then
  SJETON="$(openssl rand -hex 6)"
else
  SJETON="$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
[[ "$SJETON" =~ ^[0-9a-f]{12}$ ]] || { echo "aleatoire indisponible" >&2; exit 2; }
CP="selftest_cp_${SJETON}"
CP_MDP="s${SJETON}x"

KO=0
ok()  { printf '      ok: %s\n' "$1"; }
non() { printf '      ECHEC: %s\n' "$1"; [[ -n "${2:-}" ]] && printf '             %s\n' "$2"; KO=1; }

# 5. ON_ERROR_STOP: un ordre refuse ne doit pas passer pour execute.
adm() {
  PGPASSWORD="$PGP" psql -h "$PGH" -p "$PORT" -U "$PGU" -d "$BASE" \
    -X -q -tA -v ON_ERROR_STOP=1 "$@"
}

# 2 et 3. Destruction par NOM EXACT uniquement. Aucun joker, jamais.
detruire_exact() {
  local r
  for r in "$@"; do
    [[ "$r" =~ ^(selftest_cp|escprobe_[am])_[0-9a-f]{12}$ ]] || {
      echo "      REFUS INTERNE: nom hors forme attendue: $r" >&2
      KO=1; continue
    }
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1 || true
  done
}
existe_exact() {                     # existe_exact <nom> ... -> nombre presents
  local r n=0
  for r in "$@"; do
    [[ -n "$r" ]] || continue
    if [[ "$(adm -c "select count(*) from pg_roles where rolname = '$r';")" != "0" ]]; then
      n=$((n+1))
    fi
  done
  printf '%s' "$n"
}
# Les deux noms qu'une execution de la sonde a pu creer, deduits de SON jeton.
noms_de_jeton() { printf 'escprobe_a_%s escprobe_m_%s' "$1" "$1"; }
jeton_de() { grep -oE 'jeton [0-9a-f]{12}' "$1" | head -1 | awk '{print $2}'; }

nettoyer_final() { detruire_exact "$CP"; rm -rf "$TMP"; }
trap nettoyer_final EXIT

echo "    auto-tests de la sonde de compatibilite"

if ! adm -c 'select 1' >/dev/null 2>&1; then
  echo "      ECHEC: PostgreSQL local injoignable — aucun auto-test execute" >&2
  exit 2
fi

adm -c "create role \"$CP\" login password '$CP_MDP' createrole;" >/dev/null
URL_OK="postgres://$CP:$CP_MDP@$PGH:$PORT/$BASE"

# --------------------------------------------------------------------------
# 7. SENTINELLE: un faux `psql` en tete de PATH.
#
# Prouver « aucun appel reseau » en constatant qu'aucun role n'a ete cree est
# une preuve INDIRECTE: elle ne distingue pas « n'a pas essaye » de « a essaye
# et echoue ». La sentinelle tranche — si elle est invoquee, elle laisse une
# trace, et le test echoue.
# --------------------------------------------------------------------------
SENTINELLE="$TMP/sentinelle"; mkdir -p "$SENTINELLE"
cat > "$SENTINELLE/psql" <<'FINSENT'
#!/usr/bin/env bash
echo "psql invoque" >> "$SENTINELLE_TRACE"
exit 42
FINSENT
chmod +x "$SENTINELLE/psql"

# --------------------------------------------------------------------------
# Test 1 — URL INVALIDE avec des PG* ambiantes: AUCUN appel a psql.
# --------------------------------------------------------------------------
TRACE="$TMP/trace1"; : > "$TRACE"
set +e
SORTIE=$(PATH="$SENTINELLE:$PATH" SENTINELLE_TRACE="$TRACE" \
         EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="ceci-n-est-pas-une-url" \
         PGHOST="$PGH" PGPORT="$PORT" PGUSER="$PGU" PGPASSWORD="$PGP" \
         PGDATABASE="$BASE" "$SONDE" 2>&1)
CODE=$?
set -e
if [[ -s "$TRACE" ]]; then
  non "URL invalide: psql a ete invoque" "$(head -1 "$TRACE")"
elif [[ $CODE -ne 2 ]]; then
  non "URL invalide: code $CODE au lieu de 2" "$(head -1 <<<"$SORTIE")"
elif ! grep -q "INCONCLUSIVE" <<<"$SORTIE"; then
  non "URL invalide: verdict autre qu'INCONCLUSIVE"
else
  ok "URL invalide + PG* ambiantes: psql jamais invoque (sentinelle), code 2"
fi

# --------------------------------------------------------------------------
# Test 2 — CONSENTEMENT ABSENT: arret avant toute invocation de psql.
# --------------------------------------------------------------------------
TRACE="$TMP/trace2"; : > "$TRACE"
set +e
SORTIE=$(PATH="$SENTINELLE:$PATH" SENTINELLE_TRACE="$TRACE" \
         DATABASE_URL="$URL_OK" "$SONDE" 2>&1); CODE=$?
set -e
if [[ -s "$TRACE" ]]; then
  non "sans consentement: psql a ete invoque"
elif [[ $CODE -ne 2 ]]; then
  non "sans consentement: code $CODE au lieu de 2"
elif ! grep -q "REFUS" <<<"$SORTIE"; then
  non "sans consentement: le refus n'est pas annonce"
else
  ok "sans EUROSTRUCT_PROBE_TARGET: psql jamais invoque, code 2"
fi

# --------------------------------------------------------------------------
# Test 3 — mode auto-test REFUSE hors boucle locale.
# --------------------------------------------------------------------------
TRACE="$TMP/trace3"; : > "$TRACE"
set +e
SORTIE=$(EUROSTRUCT_PROBE_TARGET=selftest-local \
         DATABASE_URL="postgres://u:p@db.exemple.invalide:5432/x" \
         "$SONDE" 2>&1); CODE=$?
set -e
if [[ $CODE -ne 2 ]] || ! grep -q "boucle locale" <<<"$SORTIE"; then
  non "mode selftest-local accepte un hote distant (code $CODE)" \
      "le hook de nettoyage serait emportable sur une instance reelle"
else
  ok "mode selftest-local refuse un hote non local (code 2)"
fi

# --------------------------------------------------------------------------
# Test 4 — OPENSSL ABSENT: le repli aleatoire produit un jeton VALIDE.
# --------------------------------------------------------------------------
BIN="$TMP/bin"; mkdir -p "$BIN"
for outil in bash psql python3 mktemp head od tr sed grep cat rm printf env awk; do
  chemin="$(command -v "$outil" 2>/dev/null || true)"
  [[ -n "$chemin" ]] && ln -sf "$chemin" "$BIN/$outil"
done
if [[ -e "$BIN/openssl" ]]; then
  non "l'auto-test n'a pas su retirer openssl du PATH"
else
  set +e
  PATH="$BIN" EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" \
    "$SONDE" >"$TMP/s4.log" 2>&1
  CODE=$?
  set -e
  T4="$(jeton_de "$TMP/s4.log")"
  if grep -q "aleatoire indisponible" "$TMP/s4.log"; then
    non "sans openssl: le repli aleatoire a ete refuse" \
        "six octets doivent donner douze caracteres hexadecimaux"
  elif [[ $CODE -ne 0 ]]; then
    non "sans openssl: code $CODE au lieu de 0"
  elif [[ -n "$T4" && "$(existe_exact $(noms_de_jeton "$T4"))" != "0" ]]; then
    non "sans openssl: roles residuels pour le jeton $T4"
  else
    ok "sans openssl: jeton valide, sonde complete (code 0)"
  fi
fi

# --------------------------------------------------------------------------
# Test 5 — NETTOYAGE EN ECHEC: code 3, en mode auto-test LOCAL uniquement.
# --------------------------------------------------------------------------
if [[ $LOCAL -eq 1 ]]; then
  set +e
  EUROSTRUCT_PROBE_TARGET=selftest-local EUROSTRUCT_PROBE_SKIP_CLEANUP=1 \
    DATABASE_URL="$URL_OK" "$SONDE" >"$TMP/s5.log" 2>&1
  CODE=$?
  set -e
  T5="$(jeton_de "$TMP/s5.log")"
  if [[ $CODE -ne 3 ]]; then
    non "nettoyage en echec: code $CODE au lieu de 3"
  else
    ok "nettoyage en echec: code 3"
  fi
  # Et on retire nous-memes, PAR NOM EXACT, ce que le hook a laisse.
  if [[ -n "$T5" ]]; then
    detruire_exact $(noms_de_jeton "$T5")
    [[ "$(existe_exact $(noms_de_jeton "$T5"))" == "0" ]] \
      || non "les roles du jeton $T5 n'ont pas pu etre retires"
  fi
else
  ok "nettoyage en echec: non exerce (hote non local, hook inactivable)"
fi

# --------------------------------------------------------------------------
# Test 6 — DEUX EXECUTIONS SIMULTANEES: jetons distincts, zero residu.
#
# La verification porte sur les DEUX PAIRES DE NOMS EXACTS de ces deux
# executions, jamais sur un joker: un `LIKE 'escprobe%'` compterait aussi les
# roles d'une sonde tierce, et ferait echouer ce test pour une raison
# etrangere — ou pire, inviterait a les detruire.
# --------------------------------------------------------------------------
set +e
EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" "$SONDE" >"$TMP/a.log" 2>&1 & PA=$!
EUROSTRUCT_PROBE_TARGET=staging DATABASE_URL="$URL_OK" "$SONDE" >"$TMP/b.log" 2>&1 & PB=$!
wait $PA; CA=$?
wait $PB; CB=$?
set -e
JA="$(jeton_de "$TMP/a.log")"; JB="$(jeton_de "$TMP/b.log")"
if [[ $CA -ne 0 || $CB -ne 0 ]]; then
  non "deux executions simultanees: codes $CA / $CB"
elif [[ -z "$JA" || -z "$JB" || "$JA" == "$JB" ]]; then
  non "deux executions simultanees: jetons non distincts ($JA / $JB)"
elif [[ "$(existe_exact $(noms_de_jeton "$JA") $(noms_de_jeton "$JB"))" != "0" ]]; then
  non "deux executions simultanees: roles residuels sur les jetons $JA / $JB"
else
  ok "deux executions simultanees: jetons distincts, zero residu (noms exacts)"
fi

echo ''
echo '================================================='
echo ' Auto-tests de la sonde de compatibilite verifies.'
echo '================================================='
exit $KO
