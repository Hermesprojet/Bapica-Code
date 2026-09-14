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

  # COLLECTES: ce que pytest voit. Distinct de ce qu'il execute — une erreur
  # de collecte, un skip de module ou un -k feraient diverger les deux, et
  # c'est precisement l'ecart qu'un compte rendu doit montrer.
  local collectes
  collectes=$( (cd "$dir" && python -m pytest --collect-only -q 2>/dev/null) \
    | awk -F': ' '/^tests\/.*: [0-9]+$/{s+=$2} END{print s+0}')

  # EXECUTES / REUSSIS / IGNORES / ECHOUES: lus dans le rapport JUnit, pas
  # dans la sortie texte. Le pyproject porte deja « addopts = -q », donc un
  # second -q en ligne de commande donne -qq et SUPPRIME la ligne de resume:
  # compter sur elle etait fragile, et elle n'existait pas ici.
  local xml; xml="$(mktemp)"
  local sortie code
  sortie=$( (cd "$dir" && python -m pytest --junit-xml="$xml" 2>&1) ); code=$?

  local ex fa er sk ok
  read -r ex fa er sk <<<"$(python - "$xml" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot()
    s = r if r.tag == "testsuite" else r.find("testsuite")
    print(s.get("tests", 0), s.get("failures", 0), s.get("errors", 0), s.get("skipped", 0))
except Exception:
    print(0, 0, 0, 0)
PY
)"
  rm -f "$xml"
  ok=$(( ex - fa - er - sk ))
  local detail="collectes ${collectes} | executes ${ex} | reussis ${ok} | ignores ${sk} | echoues $(( fa + er ))"

  if [[ $code -eq 0 ]]; then
    NOMS+=("$nom"); ETATS+=("VERT"); DETAILS+=("$detail")
  else
    NOMS+=("$nom"); ETATS+=("ROUGE"); DETAILS+=("$detail")
    echo "$sortie" | grep -E '^(FAILED|ERROR)' | sed 's/^/    /'
    EXIT=1
  fi

  # Collectes et executes doivent coincider. Sinon des tests ont disparu
  # entre la collecte et l'execution, ce qu'aucun « tous verts » ne doit
  # masquer.
  if [[ "$collectes" -ne "$ex" ]]; then
    echo "    ATTENTION: ${collectes} collectes mais ${ex} executes"
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

# LA COUCHE HTTP. Ses cas ne touchent ni base ni reseau: refus 422, refus de
# jeton, rotation JWKS. Le parcours d'autorite complet, lui, exige un vrai
# PostgreSQL et vit dans `db/test/api_e2e.sh` — il est lance par la suite SQL.
echo "--> API"
run_pytest "API" "$HERE/api"

# --------------------------------------------------------------------------
# Garanties SQL. Sans serveur joignable, la surface est declaree NON EXECUTEE
# — jamais passee sous silence. C'est la moitie du travail de ce script.
# --------------------------------------------------------------------------
echo "--> garanties SQL"
# La joignabilite se constate SANS mettre l'URL en argv: `harnais_connexion`
# la decoupe en variables libpq dans un sous-shell, et `psql` n'y prend aucun
# argument de connexion.
db_joignable() (
  # shellcheck source=db/test/lib_harnais.sh
  source "$HERE/db/test/lib_harnais.sh"
  harnais_connexion >/dev/null 2>&1 || return 1
  psql -X -q -c 'select 1' >/dev/null 2>&1
)

# --------------------------------------------------------------------------
# SECURITE DES HARNAIS — surface a part, et evaluee AVANT les garanties SQL.
#
# Les harnais creent et detruisent des ROLES GLOBAUX. Avant de leur laisser
# toucher un cluster, on exige la preuve que leurs barrieres refusent: sans
# consentement, hors boucle locale, sur une plateforme geree, sur un cluster
# partage, et devant des roles canoniques qu'ils n'ont pas crees.
#
# Elle est evaluee ICI et non depuis `db/test/run.sh`: l'auto-test INVOQUE la
# commande canonique pour la mettre en echec, et l'appeler depuis elle
# creerait une recursion dont la terminaison dependrait justement des
# barrieres qu'il teste.
if ! command -v psql >/dev/null 2>&1; then
  NOMS+=("securite des harnais"); ETATS+=("NON EXECUTEE"); DETAILS+=("psql absent")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
elif ! db_joignable; then
  NOMS+=("securite des harnais"); ETATS+=("NON EXECUTEE")
  DETAILS+=("aucun PostgreSQL joignable")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
else
  code_sec=0
  sortie_sec=$("$HERE/db/test/harness_safety_selftest.sh" 2>&1) || code_sec=$?
  if [[ $code_sec -eq 0 ]]; then
    barrieres=$(echo "$sortie_sec" | grep -cE '^      ok: [0-9]+\.')
    NOMS+=("securite des harnais"); ETATS+=("VERT")
    DETAILS+=("$barrieres barriere(s) mise(s) en echec, toutes ont refuse")
  elif [[ $code_sec -eq 3 ]]; then
    # La securite n'a pas ete JUGEE. NON EXECUTEE, jamais VERT — une surface
    # qu'on n'a pas pu evaluer ne doit pas ressembler a une surface qui a
    # passe. Et distincte du ROUGE: « une barriere cede » et « le decor
    # manque » sont deux nouvelles differentes, que confondre ferait chercher
    # une faille inexistante.
    #
    # LE MOTIF EST LU DANS LA SORTIE, et non deduit du seul code. Les deux
    # causes rendent 3, et annoncer « roles residuels » quand c'est le verrou
    # enverrait nettoyer un cluster qui n'a rien a se reprocher — mesure faite
    # sur deux executions concurrentes.
    NOMS+=("securite des harnais"); ETATS+=("NON EXECUTEE")
    if grep -qi "verrou de harnais est deja detenu" <<<"$sortie_sec"; then
      DETAILS+=("verrou detenu par une autre execution: relancer ensuite")
    else
      DETAILS+=("roles canoniques residuels: nettoyer le cluster puis relancer")
    fi
    echo "$sortie_sec" | tail -6 | sed 's/^/    /'
    EXIT=1
  else
    NOMS+=("securite des harnais"); ETATS+=("ROUGE")
    DETAILS+=("une barriere cede: voir sortie ci-dessus")
    echo "$sortie_sec" | tail -20 | sed 's/^/    /'
    EXIT=1
  fi
fi

if ! command -v psql >/dev/null 2>&1; then
  NOMS+=("garanties SQL"); ETATS+=("NON EXECUTEE"); DETAILS+=("psql absent")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
elif ! db_joignable; then
  NOMS+=("garanties SQL"); ETATS+=("NON EXECUTEE")
  DETAILS+=("aucun PostgreSQL joignable (DATABASE_URL ou PGHOST)")
  [[ $REQUIRE_DB -eq 1 ]] && EXIT=1
else
  code_sql=0
  sortie=$("$HERE/db/test/run.sh" 2>&1) || code_sql=$?
  if [[ $code_sql -eq 3 ]]; then
    # Verrou detenu, ou decor non rendu: la surface n'a pas ete JUGEE. La
    # declarer ROUGE ferait chercher une regression la ou il n'y a qu'une
    # execution concurrente.
    NOMS+=("garanties SQL"); ETATS+=("NON EXECUTEE")
    if grep -qi "verrou de harnais est deja detenu" <<<"$sortie"; then
      DETAILS+=("verrou detenu par une autre execution: relancer ensuite")
    else
      DETAILS+=("decor non rendu: voir sortie ci-dessus")
    fi
    echo "$sortie" | tail -12 | sed 's/^/    /'
    EXIT=1
  elif [[ $code_sql -eq 0 ]]; then
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
# Coherence: les controles PROPRES au workflow EUROSTRUCT.
#
# POURQUOI CETTE SURFACE EXISTE.
#
# Ce script promettait qu'une surface non executee serait aussi visible qu'une
# surface en echec. La promesse etait tenue pour les trois surfaces qu'il
# CONNAISSAIT — et le workflow `EUROSTRUCT` en portait six autres qu'il ne
# connaissait pas. Resultat: le seed NDP a diverge de son generateur pendant
# six jalons, la CI etait rouge en continu, et ce script a repondu « COMPLET »
# a chaque fois. La panne exacte que le fichier dit combattre, a l'etage
# au-dessus.
#
# Ces controles ne dupliquent pas les suites pytest ci-dessus: ils comparent
# des ARTEFACTS COMMITTES a ce que leur generateur produit aujourd'hui. Un
# fichier genere qu'on oublie de regenerer est invisible pour un test unitaire
# — c'est le depot qui ment, pas le code.
# --------------------------------------------------------------------------
echo "--> coherence des artefacts generes"
COH_DETAIL=()
COH_ROUGE=0

coherence() {
  local nom="$1"; shift
  if sortie=$("$@" 2>&1); then
    COH_DETAIL+=("$nom: ok")
  else
    COH_DETAIL+=("$nom: ECHEC")
    echo "    $nom:"
    echo "$sortie" | tail -6 | sed 's/^/      /'
    COH_ROUGE=1
  fi
}

# 1. Le seed NDP est-il celui que produit son generateur ?
seed_a_jour() {
  local tmp; tmp="$(mktemp)"
  python "$HERE/db/seed/generate_ndp_seed.py" > "$tmp" 2>/dev/null || {
    rm -f "$tmp"; echo "le generateur de seed a echoue"; return 1; }
  if ! diff -q "$tmp" "$HERE/db/seed/0001_ndp.sql" >/dev/null; then
    echo "db/seed/0001_ndp.sql diverge de generate_ndp_seed.py:"
    diff "$HERE/db/seed/0001_ndp.sql" "$tmp" | head -4
    rm -f "$tmp"; return 1
  fi
  rm -f "$tmp"
}
coherence "seed NDP" seed_a_jour

# 2. Le contrat TypeScript est-il celui que produisent les modeles Pydantic ?
contrat_a_jour() {
  (cd "$HERE/engine" && python scripts/export_contracts.py >/dev/null 2>&1) || {
    echo "export_contracts.py a echoue"; return 1; }
  git -C "$HERE" diff --quiet -- packages/contracts || {
    echo "packages/contracts diverge des modeles Pydantic"
    git -C "$HERE" diff --stat -- packages/contracts; return 1; }
}
coherence "contrat TypeScript" contrat_a_jour

# 3. L'arbre de dependances du moteur reste-t-il dans son allowlist ?
coherence "dependances du moteur" \
  bash -c "cd '$HERE/engine' && python scripts/audit_engine_dependencies.py"

# 4. Un avertissement dans un moteur de calcul est un defaut, pas du bruit.
coherence "moteur sans avertissement" \
  bash -c "cd '$HERE/engine' && python -m pytest tests/ -q -W error"

if [[ $COH_ROUGE -eq 0 ]]; then
  NOMS+=("coherence"); ETATS+=("VERT")
else
  NOMS+=("coherence"); ETATS+=("ROUGE"); EXIT=1
fi
detail_coherence=""
for d in "${COH_DETAIL[@]}"; do
  detail_coherence+="${detail_coherence:+, }$d"
done
DETAILS+=("$detail_coherence")

# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------
echo
echo "=============================================================="
LARGEUR=0
for i in "${!NOMS[@]}"; do
  [[ ${#NOMS[$i]} -gt $LARGEUR ]] && LARGEUR=${#NOMS[$i]}
done
printf " %-*s %-14s %s\n" "$LARGEUR" "SURFACE" "ETAT" "DETAIL"
echo "--------------------------------------------------------------"
NON_EXEC=0
for i in "${!NOMS[@]}"; do
  printf " %-*s %-14s %s\n" "$LARGEUR" "${NOMS[$i]}" "${ETATS[$i]}" "${DETAILS[$i]}"
  [[ "${ETATS[$i]}" == "NON EXECUTEE" || "${ETATS[$i]}" == "ABSENT" ]] && NON_EXEC=1
done
echo "=============================================================="

# Avec --require-db, seul COMPLET peut reussir. La garde est ECRITE ICI
# plutot que deduite des branches ci-dessus: une propriete du contrat ne doit
# pas dependre du fait qu'aucune branche future ne l'oubliera.
if [[ $REQUIRE_DB -eq 1 && $NON_EXEC -eq 1 ]]; then
  EXIT=1
fi

if [[ $EXIT -ne 0 ]]; then
  echo " VERDICT: ECHEC"
elif [[ $NON_EXEC -eq 1 ]]; then
  # Vert partiel n'est PAS vert. Le dire ici evite qu'un compte rendu
  # transforme « deux surfaces sur trois » en « tous verts ».
  echo " VERDICT: PARTIEL — toutes les surfaces n'ont pas ete executees."
  echo "          Ne pas rapporter « tous verts » sur cette base."
else
  # Le compte est DERIVE, jamais ecrit en dur: « les trois surfaces » est
  # reste affiche alors qu'il y en avait quatre, et un rapport qui se trompe
  # sur ce qu'il a couvert est precisement ce que ce script combat.
  echo " VERDICT: COMPLET — les ${#NOMS[@]} surfaces ont tourne, toutes vertes."
fi
echo

exit $EXIT
