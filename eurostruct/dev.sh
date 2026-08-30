#!/usr/bin/env bash
#
# EUROSTRUCT — DEMARRER LA TRANCHE APPLICATIVE LOCALE, EN UNE COMMANDE
#
#   eurostruct/dev.sh [--build]
#
# Demarre l'API (port 8000) et l'interface (port 3000), attend qu'elles
# repondent vraiment, et rend la main. Ctrl-C arrete les deux.
#
# POURQUOI UN SCRIPT PLUTOT QU'UN PARAGRAPHE DE README
# -----------------------------------------------------
# Un paragraphe se lit, se recopie de travers, et derive. Une commande
# s'execute. Celle-ci fait la seule chose qu'un README ne peut pas faire:
# VERIFIER que les deux services repondent avant de dire qu'ils tournent.
#
# CE QU'IL NE FAIT PAS
# ---------------------
# Il n'invente aucune configuration. Sans `.env`, l'API demarre, `/health`
# repond, et `/ready` explique ce qui manque — c'est le comportement voulu:
# on veut pouvoir demarrer pour LIRE pourquoi on ne peut pas servir.
#
# Il ne cree ni base, ni role, ni secret.
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
PORT_API="${EUROSTRUCT_PORT_API:-8000}"
PORT_WEB="${EUROSTRUCT_PORT_WEB:-3000}"
MODE_BUILD=0
[[ "${1:-}" == "--build" ]] && MODE_BUILD=1

PIDS=()
arreter() {
  echo ""
  echo "--> arret"
  for p in "${PIDS[@]:-}"; do
    [[ -n "$p" ]] && kill "$p" 2>/dev/null
  done
  wait 2>/dev/null
  exit 0
}
trap arreter INT TERM

# --------------------------------------------------------------------------
# 1. L'ENVIRONNEMENT — lu, jamais devine
# --------------------------------------------------------------------------
if [[ -f "$RACINE/.env" ]]; then
  echo "--> .env charge"
  set -a; . "$RACINE/.env"; set +a
else
  echo "--> pas de .env: l'API demarrera, et /ready dira ce qui manque."
  echo "    (cp eurostruct/api/.env.example .env)"
fi

# --------------------------------------------------------------------------
# 2. LES DEUX OUTILS SONT VERIFIES AVANT DE DEMARRER QUOI QUE CE SOIT
# --------------------------------------------------------------------------
PYTHON="${EUROSTRUCT_PYTHON:-python3}"
if ! "$PYTHON" -c "import eurostruct_api" >/dev/null 2>&1; then
  echo "REFUS: le paquet eurostruct-api n'est pas installe pour « $PYTHON »." >&2
  echo "       pip install -e eurostruct/engine -e eurostruct/api" >&2
  exit 2
fi
if [[ ! -d "$ICI/web/node_modules" ]]; then
  echo "REFUS: les dependances de l'interface manquent." >&2
  echo "       (cd eurostruct/web && npm install)" >&2
  exit 2
fi

# --------------------------------------------------------------------------
# 3. L'API
# --------------------------------------------------------------------------
echo "--> API sur http://127.0.0.1:$PORT_API"
"$PYTHON" -m uvicorn eurostruct_api.app:app \
  --host 127.0.0.1 --port "$PORT_API" &
PIDS+=($!)

# ON ATTEND QU'ELLE REPONDE, PAS QU'ELLE DEMARRE. Un processus lance n'est
# pas un service disponible, et annoncer l'un pour l'autre fait chercher la
# panne du mauvais cote.
for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT_API/health" && break
  sleep 0.5
done
if ! curl -sf -o /dev/null "http://127.0.0.1:$PORT_API/health"; then
  echo "REFUS: l'API n'a pas repondu sur /health." >&2
  arreter
fi
echo "    /health repond."

# LE DIAGNOSTIC DE PRET EST AFFICHE, PAS EXIGE. Sans base ni Supabase, la
# tranche de CALCUL fonctionne — le moteur est deterministe et ne consulte
# aucune donnee d'autorite. Ce sont les DECISIONS qui exigent une identite.
if curl -sf -o /dev/null "http://127.0.0.1:$PORT_API/ready"; then
  echo "    /ready vert: les decisions d'autorite sont servies."
else
  echo "    /ready rouge: le CALCUL fonctionne, les DECISIONS d'autorite non."
  echo "                  (detail: curl -s localhost:$PORT_API/ready)"
fi

# --------------------------------------------------------------------------
# 4. L'INTERFACE
# --------------------------------------------------------------------------
cd "$ICI/web" || exit 2
# L'ADRESSE EST DECLAREE, PLUS DEDUITE D'UN REPLI. `lib/configuration.ts`
# repliait sur `http://127.0.0.1:8000` quand rien n'etait configure: une image
# deployee sans `EUROSTRUCT_API_URL` appelait alors le port 8000 du poste de
# l'UTILISATEUR, ce qui echoue chez lui, reussit chez un developpeur qui a une
# API locale, et n'apparait dans aucun journal serveur. Le repli est parti;
# ce script dit donc ce qu'il fait tourner.
export EUROSTRUCT_API_URL="http://127.0.0.1:$PORT_API"
if (( MODE_BUILD )); then
  echo "--> build de l'interface"
  npm run build >/dev/null || { echo "REFUS: le build a echoue." >&2; arreter; }
  npm run start -- --port "$PORT_WEB" &
else
  npm run dev -- --port "$PORT_WEB" &
fi
PIDS+=($!)

for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT_WEB" && break
  sleep 0.5
done
if ! curl -sf -o /dev/null "http://127.0.0.1:$PORT_WEB"; then
  echo "REFUS: l'interface n'a pas repondu." >&2
  arreter
fi

echo ""
echo "================================================="
echo " interface : http://localhost:$PORT_WEB"
echo " API       : http://localhost:$PORT_API/docs"
echo " Ctrl-C pour arreter les deux."
echo "================================================="
wait
