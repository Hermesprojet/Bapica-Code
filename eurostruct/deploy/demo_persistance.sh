#!/usr/bin/env bash
#
# EUROSTRUCT — L'ENVIRONNEMENT DE DEMONSTRATION SURVIT A UN REDEMARRAGE
#
#   deploy/demo_persistance.sh
#
# CE QUE CE SCRIPT ETABLIT
# -------------------------
# La phrase de `docs/ESSAYER.md` — « je cree une etude, je ferme le navigateur,
# je redemarre les services et je retrouve mon travail » — est mesuree ici,
# dans cet ordre, sur l'environnement que `deploy/demo.sh` monte:
#
#   1. `demo.sh up`                          la pile sert, le projet belge existe
#   2. `parcours_demo.mjs creer`             une etude, sa note PDF, son plan DXF
#   3. `demo.sh down`                        les conteneurs s'arretent — le
#                                            navigateur est deja ferme
#   4. `demo.sh up`                          ils redemarrent sur les memes volumes
#   5. `parcours_demo.mjs retrouver`         l'etude est dans l'historique, relue
#                                            par l'API, et ses deux livrables
#                                            portent encore leurs empreintes
#
# IL NE DETRUIT RIEN. Ce n'est pas un harnais: il laisse l'environnement
# debout a la fin, avec l'etude dedans. C'est `demo.sh reset` qui detruit,
# avec consentement.
#
# CODES: 0 le parcours complet tient; 1 une etape a echoue; 4 non executable.
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"

command -v node >/dev/null 2>&1 || { echo "NON EXECUTE: node absent." >&2; exit 4; }
node "$RACINE/web/e2e/verifier_navigateur.mjs" >/dev/null 2>&1 \
  || { echo "NON EXECUTE: Playwright ou Chromium absent." >&2; exit 4; }

etape() { echo ""; echo "==> $*"; }

etape "1/5 demo.sh up"
"$ICI/demo.sh" up || exit 1

etape "2/5 creer une etude, sa note PDF et son plan DXF"
node "$RACINE/web/e2e/parcours_demo.mjs" creer || exit 1

etape "3/5 demo.sh down — le navigateur est ferme, les services s'arretent"
"$ICI/demo.sh" down || exit 1

etape "4/5 demo.sh up — memes volumes"
"$ICI/demo.sh" up || exit 1

etape "5/5 retrouver l'etude"
node "$RACINE/web/e2e/parcours_demo.mjs" retrouver || exit 1

echo ""
echo "=================================================================="
echo " L'etude, sa note PDF et son plan DXF ont survecu a l'arret et au"
echo " redemarrage des services. L'environnement est laisse debout."
echo "=================================================================="
