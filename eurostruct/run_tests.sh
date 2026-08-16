#!/usr/bin/env bash
#
# EUROSTRUCT — la commande de test canonique. LA seule dont un compte rendu
# doit provenir.
#
#   ./run_tests.sh              tout ce qui est lancable ici
#   ./run_tests.sh --require-db echoue si la base n'est pas joignable (CI)
#
# Pourquoi ce script existe
# --------------------------
# Le projet a TROIS surfaces de test, et le README les documentait separement:
#
#   1. moteur         engine/tests            pytest
#   2. importeur      tools/ndp_import/tests  pytest
#   3. garanties SQL  db/test/run.sh          contre un vrai PostgreSQL
#
# C'est exactement ainsi qu'un compte rendu « tous verts » a pu etre produit
# trois fois de suite alors qu'un test de l'IMPORTEUR etait rouge: le
# changement portait sur une donnee du MOTEUR, seule la suite moteur avait ete
# relancee, et le test rouge lisait le fichier de l'autre.
#
# La propriete que ce script garantit
# ------------------------------------
# Une surface NON EXECUTEE est aussi visible qu'une surface en echec. Le
# verdict final ne dit « COMPLET » que si les trois ont tourne. Une couverture
# partielle invisible est la panne que ce script existe pour rendre
# impossible — pas seulement les tests rouges.
#
# La CI appelle ce meme script, avec --require-db, pour que local et distant
# ne divergent pas.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRE_DB=0
[[ "${1:-}" == "--require-db" ]] && REQUIRE_DB=1

VENV="${EUROSTRUCT_VENV:-$(dirname "$HERE")/.venv-eurostruct}"
if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

declare -a NOMS=() ETATS=() DETAILS=()
EXIT=0

# --------------------------------------------------------------------------
# Une suite pytest: on veut le nombre de tests COLLECTES, pas un compte de
# « def test » — les tests parametres se dupliquent a l'execution, et compter
# les fonctions a deja produit un rapport faux (386 annonces contre 462).
# --------------------------------------------------------------------------
run_pytest() {
  local nom="$1" dir="$2"
  if [[ ! -d "$dir/tests" ]]; then
    NOMS+=("$nom"); ETATS+=("ABSENT"); DETAILS+=("pas de repertoire tests/")
    EXIT=1; return
  fi
  local collectes
  collectes=$( (cd "$dir" && python -m pytest --collect-only -q 2>/dev/null) \
    | awk -F': ' '/^tests\/.*: [0-9]+$/{s+=$2} END{print s+0}')
  local sortie
  sortie=$( (cd "$dir" && python -m pytest -q 2>&1) )
  local code=$?
  if [[ $code -eq 0 ]]; then
    NOMS+=("$nom"); ETATS+=("VERT"); DETAILS+=("$collectes tests collectes")
  else
    NOMS+=("$nom"); ETATS+=("ROUGE"); DETAILS+=("$collectes collectes — $(echo "$sortie" | grep -c '^FAILED') en echec")
    echo "$sortie" | grep -E '^(FAILED|ERROR)' | sed 's/^/    /'
    EXIT=1
  fi
}

echo "=============================================================="
echo " EUROSTRUCT — suite de tests canonique"
echo "=============================================================="

echo
echo "--> moteur"
run_pytest "moteur" "$HERE/engine"

echo "--> importeur"
run_pytest "importeur" "$HERE/tools/ndp_import"

# --------------------------------------------------------------------------
# Garanties SQL. Sans serveur joignable, la surface est declaree NON EXECUTEE
# — jamais passee sous silence. C'est la moitie du travail de ce script.
# --------------------------------------------------------------------------
echo "--> garanties SQL"
db_joignable() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    psql "$DATABASE_URL" -c 'select 1' >/dev/null 2>&1
  else
    pg_isready -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" >/dev/null 2>&1
  fi
}

if ! command -v psql >/dev/null 2>&1; then
  NOMS+=("garanties SQL"); ETATS+=("NON EXECUTEE"); DETAILS+=("psql absent")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
elif ! db_joignable; then
  NOMS+=("garanties SQL"); ETATS+=("NON EXECUTEE")
  DETAILS+=("aucun PostgreSQL joignable (DATABASE_URL ou PGHOST)")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
else
  if sortie=$("$HERE/db/test/run.sh" 2>&1); then
    # Chaque fichier SQL termine par un encadre « ... verifie(es) ». Compter
    # ces lignes plutot qu'un motif « ok/pass » que ce runner n'imprime pas:
    # un « 0 controles » a cote d'un VERT est le genre de detail qui ruine la
    # confiance dans un rapport.
    fichiers=$(echo "$sortie" | grep -cE '^ .*(verifie|verifiee|verifiees|verifies)\.$')
    NOMS+=("garanties SQL"); ETATS+=("VERT")
    DETAILS+=("$fichiers groupe(s) de garanties verifie(s)")
  else
    NOMS+=("garanties SQL"); ETATS+=("ROUGE"); DETAILS+=("voir sortie ci-dessus")
    echo "$sortie" | tail -20 | sed 's/^/    /'
    EXIT=1
  fi
fi

# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------
echo
echo "=============================================================="
printf " %-16s %-14s %s\n" "SURFACE" "ETAT" "DETAIL"
echo "--------------------------------------------------------------"
NON_EXEC=0
for i in "${!NOMS[@]}"; do
  printf " %-16s %-14s %s\n" "${NOMS[$i]}" "${ETATS[$i]}" "${DETAILS[$i]}"
  [[ "${ETATS[$i]}" == "NON EXECUTEE" || "${ETATS[$i]}" == "ABSENT" ]] && NON_EXEC=1
done
echo "=============================================================="

if [[ $EXIT -ne 0 ]]; then
  echo " VERDICT: ECHEC"
elif [[ $NON_EXEC -eq 1 ]]; then
  # Vert partiel n'est PAS vert. Le dire ici evite qu'un compte rendu
  # transforme « deux surfaces sur trois » en « tous verts ».
  echo " VERDICT: PARTIEL — toutes les surfaces n'ont pas ete executees."
  echo "          Ne pas rapporter « tous verts » sur cette base."
else
  echo " VERDICT: COMPLET — les trois surfaces ont tourne, toutes vertes."
fi
echo

exit $EXIT
