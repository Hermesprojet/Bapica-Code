#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b3: contrat croise Python <-> PostgreSQL.
#
#   cross_contract.sh <psql-args...>
#
# Un VRAI paquet de revue, produit par `eurostruct_engine.ndp.canonical`, est
# insere dans PostgreSQL, relu depuis PostgreSQL, puis RECONSTRUIT en objets
# du domaine. Toute divergence echoue.
#
# Ce que ce script ferme, et qu'aucune fixture ne pouvait fermer: les payloads
# canoniques des garanties SQL sont ecrits a la main. Ils ressemblent a ce que
# le moteur produit. Le jour ou la canonicalisation changera d'un caractere,
# ces fixtures passeront encore et la base acceptera un format que plus
# personne ne produit. Voir l'en-tete de `cross_contract.py`.
#
# Le transport est `psql`: le moteur n'importe aucun pilote de base, et une
# garantie du projet l'exige explicitement.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(dirname "$(dirname "$HERE")")"

# Le moteur a des dependances (pint). Un `python3` nu les aurait rarement, et
# l'echec serait lu comme une divergence de contrat alors que c'est un
# interpreteur mal choisi. Meme resolution que run_tests.sh.
PY="${EUROSTRUCT_PYTHON:-}"
if [[ -z "$PY" ]]; then
  VENV="${EUROSTRUCT_VENV:-$(dirname "$PROJET")/.venv-eurostruct}"
  if [[ -x "$VENV/bin/python" ]]; then
    PY="$VENV/bin/python"
  else
    PY=python3
  fi
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PSQL=("$@")
if [[ ${#PSQL[@]} -eq 0 ]]; then
  echo "usage: cross_contract.sh <psql-args...>" >&2
  exit 2
fi

echo "    contrat croise Python <-> PostgreSQL"

# --------------------------------------------------------------------------
# 0. Le moteur doit etre importable. ECHEC EXPLICITE, jamais un saut.
#
# Une surface non executee doit etre aussi visible qu'une surface en echec:
# c'est la propriete que `run_tests.sh` existe pour garantir, et un `skip`
# silencieux ici la trahirait a l'endroit precis ou elle compte. Le diagnostic
# est nomme, parce que la panne reelle — un job CI sans etape Python — se lit
# autrement comme un `ModuleNotFoundError` sans rapport apparent.
# --------------------------------------------------------------------------
if ! "$PY" -c 'import sys, pathlib
sys.path.insert(0, str(pathlib.Path("'"$PROJET"'") / "engine" / "src"))
import eurostruct_engine.ndp.canonical' 2>/dev/null; then
  echo "      ECHEC: le moteur n'est pas importable par $PY." >&2
  echo "      Le contrat croise fait PRODUIRE le paquet par le moteur: sans" >&2
  echo "      lui il n'y a rien a inserer, et le sauter reviendrait a ne plus" >&2
  echo "      verifier que la base accepte ce que le moteur produit." >&2
  echo "      Installer le moteur (pip install -e engine) ou pointer" >&2
  echo "      EUROSTRUCT_PYTHON sur un interpreteur qui l'a." >&2
  exit 1
fi

# --------------------------------------------------------------------------
# 1. Python produit le paquet. Aucun octet n'est retape ensuite.
# --------------------------------------------------------------------------
"$PY" "$HERE/cross_contract.py" emit > "$TMP/paquet.json"

# --------------------------------------------------------------------------
# 2. PostgreSQL l'accepte, et DERIVE ses colonnes.
#
# Le paquet transite par une variable psql, citee par `:'paquet'`: psql en
# fabrique un litteral correctement echappe. Le shell ne touche a rien.
# --------------------------------------------------------------------------
"${PSQL[@]}" -v ON_ERROR_STOP=1 -q \
  -v paquet="$(cat "$TMP/paquet.json")" \
  -f "$HERE/cross_contract_insert.sql"

# --------------------------------------------------------------------------
# 3. Relecture. Format tuples-only, non aligne: la sortie est le JSON, rien
#    d'autre.
# --------------------------------------------------------------------------
"${PSQL[@]}" -X -q -At -v ON_ERROR_STOP=1 -c "
  select jsonb_pretty(jsonb_build_object(
    'country_code', c.country_code,
    'standard_family', c.standard_family,
    'part', c.part,
    'rule_id', c.rule_id,
    'digest_algorithm', c.digest_algorithm,
    'canonicalization_version', c.canonicalization_version,
    'stack_digest', c.stack_digest,
    'normative_spec_digest', c.normative_spec_digest,
    'implementation_digest', c.implementation_digest,
    'evidence_digest', c.evidence_digest,
    'stack_payload', c.stack_payload,
    'normative_spec_payload', c.normative_spec_payload,
    'implementation_payload', c.implementation_payload,
    'evidence_payload', c.evidence_payload,
    'stack_snapshot', c.stack_snapshot,
    'evidence_items', c.evidence_items,
    'annex_edition', c.annex_edition
  ))
  from normative_rule_confirmations c
  where c.idempotency_key = 'FICTIF-contrat-croise-1';
" > "$TMP/relu.json"

if [[ ! -s "$TMP/relu.json" ]]; then
  echo "      ECHEC: aucune ligne relue — l'insertion n'a rien laisse" >&2
  exit 1
fi

# --------------------------------------------------------------------------
# 4. Python reconstruit, et exige l'identite.
# --------------------------------------------------------------------------
"$PY" "$HERE/cross_contract.py" verify "$TMP/paquet.json" "$TMP/relu.json"

# Encadre de fin, dans la forme que `run_tests.sh` compte: une surface qui
# tourne sans etre comptee est une couverture partielle invisible, et c'est
# exactement ce que ce rapport existe pour empecher.
echo ''
echo '================================================='
echo ' Contrat croise Python <-> PostgreSQL verifie.'
echo '================================================='
