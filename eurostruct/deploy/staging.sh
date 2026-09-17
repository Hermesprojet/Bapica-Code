#!/usr/bin/env bash
#
# EUROSTRUCT — LA MISE A DISPOSITION SUR STAGING: base hebergee, authentification reelle
#
#   deploy/staging.sh prerequis     ce qu'il faut sur l'hote et dans deploy/staging.env — ne lance rien
#   deploy/staging.sh privileges    ce que les trois roles peuvent sur la base hebergee (lecture seule)
#   deploy/staging.sh migrer        sceau, migrations, referentiel national, admission du login, racine si mandat
#   deploy/staging.sh up            construit et demarre l'API, l'interface et le mandataire TLS (Caddy, deploy/Caddyfile)
#   deploy/staging.sh status        ce qui tourne; /ready local, puis les URL publiques: https, /ready, interface, CORS
#   deploy/staging.sh recette [diagnostic|executer]   la recette de bout en bout sur cette base
#   deploy/staging.sh journaux [service] [n]          les n dernieres lignes d'un service (api, web, mandataire)
#   deploy/staging.sh down          arrete l'API, l'interface et le mandataire; volumes (livrables, certificats) gardes
#
#   deploy/staging.sh diagnostic       ce qu'une mise a niveau ferait — ne modifie rien
#   deploy/staging.sh sauvegarder      pg_dump -Fc par la DSN d'administration declaree
#   deploy/staging.sh mettre-a-niveau  applique les migrations manquantes, en GARDANT les donnees
#   deploy/staging.sh reprendre        reprend une mise a niveau interrompue
#
# CE QUE CETTE COMMANDE ETABLIT, ET CE QU'ELLE N'ETABLIT PAS
# ------------------------------------------------------------
# Elle REUTILISE ce qui existe: `compose.yaml` et sa surcouche
# `compose.staging.yaml` pour les deux images, `tools/deploy_eurostruct.sh`
# et `db/seed/0001_ndp.sql` pour la base, `deploy/verifier_privileges.sh`
# pour les droits, `db/test/recette_supabase_staging.sh` pour la recette.
# Elle ne remplace aucun de ces chemins; elle les enchaine dans le bon ordre
# et refuse avant le premier pas qui manquerait de quelque chose.
#
# ELLE NE PROUVE RIEN SUR SUPABASE TANT QU'ELLE N'Y A PAS TOURNE. Ce qui a ete
# execute: la repetition locale (`deploy/staging_repetition.sh`) — la meme
# composition contre un PostgreSQL et un emetteur exterieurs a la
# composition. Voir docs/STAGING.md.
#
# CE QUI DISTINGUE CE FICHIER DE `demo.sh`
# -----------------------------------------
# `demo.sh` GENERE ses comptes, ses mots de passe et sa base: tout est de
# demonstration, et l'ecran le dit. Ici rien n'est genere: chaque valeur est
# une information externe que l'exploitant renseigne dans `deploy/staging.env`
# — trois DSN, un JWKS, une cle anonyme, deux URL publiques — et
# `EUROSTRUCT_ENVIRONNEMENT` reste VIDE.
#
# AUCUN SECRET DANS `argv`, AUCUN DANS CETTE SORTIE. Les DSN sont decoupees en
# variables libpq dans un sous-shell; les jetons passent par des fichiers en
# 0600; les diagnostics nomment des VARIABLES, jamais leurs valeurs.
set -uo pipefail
set +x

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
ENVF="${EUROSTRUCT_STAGING_ENV:-$ICI/staging.env}"
#: Le nom de la composition Docker. La repetition locale en prend un autre,
#: pour ne jamais toucher une composition de staging qui tournerait a cote.
PROJET="${EUROSTRUCT_STAGING_PROJET:-eurostruct-staging}"
COMPOSE_MIN="2.24"

refus() { echo "REFUS: $*" >&2; exit 2; }
dire()  { echo "--> $*"; }

dc() {
  docker compose -p "$PROJET" \
    -f "$RACINE/compose.yaml" -f "$RACINE/compose.staging.yaml" \
    --env-file "$ENVF" "$@"
}

# ---------------------------------------------------------------------------
# L'ENVIRONNEMENT — lu, jamais affiche
# ---------------------------------------------------------------------------
charger_env() {
  [[ -f "$ENVF" ]] || refus "$(basename "$ENVF") absent: copiez deploy/staging.env.example, remplissez-le (chmod 600), puis relancez."
  local droits
  droits="$(stat -c %a "$ENVF" 2>/dev/null || echo "?")"
  [[ "$droits" == "600" || "$droits" == "400" ]] \
    || echo "AVERTISSEMENT: $(basename "$ENVF") a les droits $droits; il porte des secrets: chmod 600." >&2
  # LE FICHIER EST LU PAR BASH ET PAR COMPOSE. Une valeur qui contient un
  # espace ou une parenthese doit etre entre guillemets doubles, sinon bash
  # s'arrete a cette ligne et tout ce qui suit reste vide — mesure a la
  # premiere repetition: EUROSTRUCT_STAGING_SANS_TLS, en derniere ligne,
  # n'etait jamais lue. On refuse plutot que de continuer a moitie charge.
  set -a
  if ! . "$ENVF"; then
    set +a
    refus "$(basename "$ENVF") n'est pas lisible par bash: mettez entre guillemets doubles les valeurs contenant des espaces ou des parentheses (voir deploy/staging.env.example)."
  fi
  set +a
  # L'ORIGINE CORS EST L'INTERFACE, PAR DEFAUT. Une seule, jamais `*`.
  export EUROSTRUCT_CORS_ORIGINS="${EUROSTRUCT_CORS_ORIGINS:-${EUROSTRUCT_PUBLIC_WEB_URL:-}}"
  # LE MANDATAIRE TLS DE LA COMPOSITION, sauf si l'hote a deja le sien. Le
  # profil vaut pour TOUTES les commandes compose de ce script: `up` le monte,
  # `down` l'arrete, `status` le liste.
  if mandataire_actif; then export COMPOSE_PROFILES="mandataire"; else unset COMPOSE_PROFILES; fi
}

mandataire_actif() { [[ "${EUROSTRUCT_MANDATAIRE:-oui}" != "non" ]]; }

hote_de() {   # hote_de <url> — le nom d'hote, sans port ni chemin
  URL="$1" python3 -c 'import os; from urllib.parse import urlsplit; print(urlsplit(os.environ["URL"]).hostname or "")' 2>/dev/null
}

# `curl_public <args...>`: curl vers une URL PUBLIQUE, avec ce que la repetition
# locale a besoin d'ajouter — l'autorite locale du mandataire (--cacert) et la
# resolution forcee des noms (--resolve) — et rien de plus sur un staging reel.
# JAMAIS -k: un certificat qui ne se verifie pas est un controle qui echoue.
curl_public() {
  local -a opts=()
  [[ -n "${EUROSTRUCT_STAGING_CA_BUNDLE:-}" && -f "${EUROSTRUCT_STAGING_CA_BUNDLE}" ]] \
    && opts+=(--cacert "$EUROSTRUCT_STAGING_CA_BUNDLE")
  if [[ -n "${EUROSTRUCT_STAGING_RESOLVE:-}" ]]; then
    local e
    for e in ${EUROSTRUCT_STAGING_RESOLVE//,/ }; do opts+=(--resolve "$e"); done
  fi
  curl "${opts[@]}" "$@"
}

# `avec_url <variable-d-url> <commande...>`: PGHOST, PGPORT, PGUSER, PGPASSWORD,
# PGDATABASE et PGSSLMODE poses depuis l'URL, dans un sous-shell.
avec_url() {
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
sql() {   # sql <variable-d-url> <requete> — une valeur, sans espaces
  avec_url "$1" psql -X -q -tA -v ON_ERROR_STOP=1 -c "$2" 2>/dev/null | tr -d ' \r'
}
champ_url() {   # champ_url <variable-d-url> <user|host|base|sslmode> — jamais le mot de passe
  URL="${!1}" python3 -c '
import os, sys
from urllib.parse import urlsplit, unquote, parse_qs
u = urlsplit(os.environ["URL"]); q = parse_qs(u.query)
print({"user": unquote(u.username or ""), "host": u.hostname or "", "base": unquote(u.path.lstrip("/")),
       "sslmode": q.get("sslmode", ["prefer"])[0]}[sys.argv[1]])' "$2" 2>/dev/null
}

# ---------------------------------------------------------------------------
# LES VERIFICATIONS — chacune nomme ce qui manque, aucune ne cite une valeur
# ---------------------------------------------------------------------------
KO=0
ligne() {   # ligne <ok|non|info> <quoi> [remede]
  case "$1" in
    ok)   printf '  ok      %s\n' "$2" ;;
    info) printf '  --      %s\n' "$2" ;;
    *)    KO=1; printf '  MANQUE  %s — %s\n' "$2" "${3:-}" ;;
  esac
}

version_compose() { docker compose version --short 2>/dev/null | sed -E 's/^v//; s/[^0-9.].*$//'; }
compose_suffisant() {
  local v="$1" maj min
  [[ "$v" =~ ^[0-9]+\.[0-9]+ ]] || return 1
  maj="${v%%.*}"; min="${v#*.}"; min="${min%%.*}"
  (( maj > ${COMPOSE_MIN%%.*} )) || (( maj == ${COMPOSE_MIN%%.*} && min >= ${COMPOSE_MIN#*.} ))
}

verifier_outils() {
  local v
  for outil in docker git curl python3 psql; do
    if command -v "$outil" >/dev/null 2>&1; then ligne ok "$outil"
    else ligne non "$outil" "absent sur l'hote. L'installer, puis relancer."; fi
  done
  if docker info >/dev/null 2>&1; then ligne ok "demon docker"
  else ligne non "demon docker" "ne repond pas. Demarrer Docker, puis relancer."; fi
  v="$(version_compose)"
  if [[ -n "$v" ]] && compose_suffisant "$v"; then ligne ok "docker compose $v (>= $COMPOSE_MIN)"
  else ligne non "docker compose ${v:-absent}" "la surcouche emploie « !override » (Compose $COMPOSE_MIN ou plus)."; fi
}

sans_tls() { [[ "${EUROSTRUCT_STAGING_SANS_TLS:-}" == "oui" ]]; }

verifier_env() {
  local v
  for v in ESC_PLAN_URL ESC_MIGRATOR_URL EUROSTRUCT_DATABASE_URL \
           EUROSTRUCT_SUPABASE_JWKS_URL EUROSTRUCT_SUPABASE_ISSUER \
           EUROSTRUCT_PUBLIC_API_URL EUROSTRUCT_PUBLIC_WEB_URL \
           EUROSTRUCT_PUBLIC_SUPABASE_URL EUROSTRUCT_PUBLIC_SUPABASE_ANON_KEY; do
    if [[ -n "${!v:-}" ]]; then ligne ok "$v renseignee"
    else ligne non "$v" "vide dans $(basename "$ENVF") (voir deploy/staging.env.example, ou elle vient)"; fi
  done

  # CE QUI EST DE DEMONSTRATION N'ENTRE PAS ICI.
  if [[ -z "${EUROSTRUCT_ENVIRONNEMENT:-}" ]]; then ligne ok "EUROSTRUCT_ENVIRONNEMENT vide (ce n'est pas une demonstration)"
  else ligne non "EUROSTRUCT_ENVIRONNEMENT" "vaut quelque chose; sur le staging elle reste VIDE (la surcouche la vide de toute facon)."; fi

  # LES TROIS DSN: trois ROLES distincts, et TLS.
  local up um ua
  up="$(champ_url ESC_PLAN_URL user)"; um="$(champ_url ESC_MIGRATOR_URL user)"; ua="$(champ_url EUROSTRUCT_DATABASE_URL user)"
  if [[ -n "$up" && -n "$um" && -n "$ua" ]]; then
    if [[ "$up" != "$um" && "$um" != "$ua" && "$up" != "$ua" ]]; then ligne ok "trois roles distincts (plan, migrateur, applicatif)"
    else ligne non "les trois DSN" "designent le meme role pour deux gestes: plan, migrateur et login applicatif sont trois roles (docs/DEPLOIEMENT_BASE_HEBERGEE.md §1)."; fi
  else
    ligne non "les trois DSN" "au moins une n'est pas une URL postgresql:// lisible (utilisateur, hote, base)."
  fi
  for v in ESC_PLAN_URL ESC_MIGRATOR_URL EUROSTRUCT_DATABASE_URL; do
    [[ -n "${!v:-}" ]] || continue
    local mode; mode="$(champ_url "$v" sslmode)"
    case "$mode" in
      require|verify-ca|verify-full) ligne ok "$v: sslmode=$mode" ;;
      *) if sans_tls; then ligne info "$v: sslmode=$mode admis (EUROSTRUCT_STAGING_SANS_TLS=oui, repetition locale)"
         else ligne non "$v" "sslmode=$mode: une base hebergee se joint en TLS (require, verify-ca ou verify-full)."; fi ;;
    esac
  done

  # LES URL PUBLIQUES: https, et pas la machine du visiteur.
  for v in EUROSTRUCT_PUBLIC_API_URL EUROSTRUCT_PUBLIC_WEB_URL EUROSTRUCT_PUBLIC_SUPABASE_URL EUROSTRUCT_SUPABASE_JWKS_URL EUROSTRUCT_SUPABASE_ISSUER; do
    [[ -n "${!v:-}" ]] || continue
    if [[ "${!v}" == https://* ]]; then ligne ok "$v en https"
    elif sans_tls; then ligne info "$v en clair admis (repetition locale)"
    else ligne non "$v" "n'est pas en https://. Le navigateur de l'utilisateur la joint; le mandataire TLS de l'hote la sert."; fi
    if [[ "${!v}" =~ ^https?://(localhost|127\.0\.0\.1)([:/]|$) ]] && ! sans_tls; then
      ligne non "$v" "designe localhost: ce serait la machine du VISITEUR, pas l'hote."
    fi
  done
  if [[ "${EUROSTRUCT_CORS_ORIGINS:-}" == *"*"* ]]; then ligne non "EUROSTRUCT_CORS_ORIGINS" "porte « * », que l'API refuse."; fi
  [[ -z "${EUROSTRUCT_PUBLIC_WEB_URL:-}" || "${EUROSTRUCT_CORS_ORIGINS:-}" == *"${EUROSTRUCT_PUBLIC_WEB_URL%/}"* ]] \
    && ligne ok "EUROSTRUCT_CORS_ORIGINS admet l'interface" \
    || ligne non "EUROSTRUCT_CORS_ORIGINS" "n'inclut pas EUROSTRUCT_PUBLIC_WEB_URL: le navigateur serait refuse par l'API."

  verifier_mandataire

  # LE STOCKAGE.
  case "${EUROSTRUCT_STORAGE_BACKEND:-local}" in
    local) ligne ok "livrables: volume ${PROJET}_livrables de l'hote (une instance d'API)" ;;
    s3) for v in EUROSTRUCT_S3_ENDPOINT EUROSTRUCT_S3_REGION EUROSTRUCT_S3_BUCKET EUROSTRUCT_S3_ACCESS_KEY_ID EUROSTRUCT_S3_SECRET_ACCESS_KEY; do
          [[ -n "${!v:-}" ]] && ligne ok "$v renseignee" || ligne non "$v" "vide alors que EUROSTRUCT_STORAGE_BACKEND=s3."; done ;;
    *) ligne non "EUROSTRUCT_STORAGE_BACKEND" "vaut autre chose que local ou s3; l'API la refuserait." ;;
  esac

  # LE JWKS: joint, lu, compare a l'algorithme declare. Public par nature.
  # LA LECTURE ET L'ANALYSE SONT DEUX PAS DISTINCTS: « injoignable » ne se dit
  # que si curl echoue. Mesure a la deuxieme repetition: l'analyse en une
  # ligne echouait (guillemets echappes dans une f-string) et le JWKS, bien
  # servi, etait declare injoignable.
  if [[ -n "${EUROSTRUCT_SUPABASE_JWKS_URL:-}" ]]; then
    local fichier lu
    fichier="$(mktemp)"
    if ! curl -fsS --max-time 10 -o "$fichier" "$EUROSTRUCT_SUPABASE_JWKS_URL" 2>/dev/null; then
      ligne non "JWKS" "injoignable depuis cet hote (EUROSTRUCT_SUPABASE_JWKS_URL). Verifier l'URL et la sortie reseau."
    else
      lu="$(JWKS_FICHIER="$fichier" ALGS="${EUROSTRUCT_JWT_ALGORITHMS:-RS256}" python3 - <<'PY' 2>/dev/null
import json, os
try:
    d = json.load(open(os.environ["JWKS_FICHIER"], encoding="utf-8"))
    cles = d.get("keys") or []
except Exception:
    print("illisible"); raise SystemExit(0)
familles = {"RSA": "RS", "EC": "ES"}
voulus = [a.strip() for a in os.environ["ALGS"].split(",") if a.strip()]
def compatible(k):
    if k.get("alg"):
        return k["alg"] in voulus
    prefixe = familles.get(k.get("kty", ""), "?")
    return any(v.startswith(prefixe) for v in voulus)
ok = [k for k in cles if compatible(k)]
kty = sorted({str(k.get("kty", "?")) for k in cles})
alg = sorted({str(k.get("alg")) for k in cles})
print(f"{len(cles)} cle(s), {len(ok)} compatible(s) avec {','.join(voulus)}; kty={kty} alg={alg}")
PY
)"
      if [[ -z "$lu" || "$lu" == illisible ]]; then ligne non "JWKS" "joint, mais ce n'est pas un JWKS JSON lisible."
      elif [[ "$lu" == *", 0 compatible"* ]]; then ligne non "JWKS" "$lu — aucune cle n'est du type declare dans EUROSTRUCT_JWT_ALGORITHMS (RS256 pour RSA, ES256 pour P-256; HS256 est refuse)."
      else ligne ok "JWKS joint: $lu"; fi
    fi
    rm -f "$fichier"
  fi
}

# LE MANDATAIRE TLS ET LES URL PUBLIQUES, tels que la composition les servira.
# Ce qui est controle ici ne demande AUCUNE connexion a la base ni au JWKS:
# la forme des deux URL, leur resolution DNS depuis cet hote, la ligne de
# certificat, et les ports 80/443 de l'hote.
verifier_mandataire() {
  local v
  if ! mandataire_actif; then
    ligne info "mandataire TLS: celui de l'hote (EUROSTRUCT_MANDATAIRE=non): il renvoie EUROSTRUCT_PUBLIC_WEB_URL vers 127.0.0.1:${WEB_PORT:-3000} et EUROSTRUCT_PUBLIC_API_URL vers 127.0.0.1:${API_PORT:-8000}"
    return 0
  fi
  if [[ -f "$RACINE/deploy/Caddyfile" ]]; then ligne ok "mandataire TLS: Caddy de la composition (deploy/Caddyfile)"
  else ligne non "deploy/Caddyfile" "absent du depot: le mandataire n'a pas de configuration."; fi
  case "${EUROSTRUCT_CADDY_TLS:-}" in
    "") ligne info "certificats: ACME sans courriel de contact (EUROSTRUCT_CADDY_TLS vide) — les ports 80 et 443 de cet hote doivent etre joignables d'Internet sous les deux noms publics" ;;
    "tls internal")
      if sans_tls; then ligne info "certificats: autorite locale de Caddy (repetition) — aucun navigateur ne lui fait confiance"
      else ligne non "EUROSTRUCT_CADDY_TLS" "vaut « tls internal »: un certificat d'autorite locale n'est pas presentable a un navigateur. Sur un staging reel: vide, ou « tls <courriel> »."; fi ;;
    tls\ *@*) ligne ok "certificats: ACME avec un courriel de contact" ;;
    *) ligne non "EUROSTRUCT_CADDY_TLS" "vaut autre chose que vide, « tls <courriel> » ou « tls internal » (voir deploy/Caddyfile)." ;;
  esac
  local hote_api hote_web
  for v in EUROSTRUCT_PUBLIC_API_URL EUROSTRUCT_PUBLIC_WEB_URL; do
    [[ -n "${!v:-}" ]] || continue
    if [[ "${!v}" =~ ^https?://[A-Za-z0-9.-]+$ ]]; then ligne ok "$v: un nom, sans port ni chemin (le mandataire sert 80 et 443)"
    else ligne non "$v" "porte un port, un chemin ou une barre finale: le mandataire de la composition sert chaque nom a la racine, sur 80 et 443."; fi
    local h; h="$(hote_de "${!v}")"
    if [[ -n "${EUROSTRUCT_STAGING_RESOLVE:-}" ]]; then
      [[ "$EUROSTRUCT_STAGING_RESOLVE" == *"$h:"* ]] && ligne info "$v: resolution forcee vers cet hote (EUROSTRUCT_STAGING_RESOLVE, repetition)" \
        || ligne non "$v" "n'est pas dans EUROSTRUCT_STAGING_RESOLVE alors que la resolution est forcee."
    elif getent ahosts "$h" >/dev/null 2>&1; then ligne ok "$v: le nom se resout depuis cet hote"
    else ligne non "$v" "le nom « $h » ne se resout pas depuis cet hote: creer l'enregistrement DNS (A/AAAA) vers l'adresse publique de cet hote; sans lui, ni certificat ACME, ni controle."; fi
  done
  hote_api="$(hote_de "${EUROSTRUCT_PUBLIC_API_URL:-}")"; hote_web="$(hote_de "${EUROSTRUCT_PUBLIC_WEB_URL:-}")"
  if [[ -n "$hote_api" && -n "$hote_web" ]]; then
    if [[ "$hote_api" != "$hote_web" ]]; then ligne ok "deux noms distincts pour l'API et l'interface"
    else ligne non "EUROSTRUCT_PUBLIC_API_URL / EUROSTRUCT_PUBLIC_WEB_URL" "designent le meme nom: le mandataire les sert comme deux sites (p. ex. api.<domaine> et <domaine>)."; fi
  fi
  case "${EUROSTRUCT_MANDATAIRE_ECOUTE:-}" in
    "") ligne ok "le mandataire ecoutera sur toutes les interfaces (80, 443)" ;;
    127.0.0.1:|localhost:) sans_tls && ligne info "le mandataire ecoutera sur la boucle locale seulement (repetition)" \
      || ligne non "EUROSTRUCT_MANDATAIRE_ECOUTE" "restreint le mandataire a la boucle locale: personne ne joindra le staging. Vide sur un staging reel." ;;
    *) ligne non "EUROSTRUCT_MANDATAIRE_ECOUTE" "vaut autre chose que vide ou « 127.0.0.1: »." ;;
  esac
  # LES PORTS 80 ET 443 DE L'HOTE: libres, ou deja tenus par CE mandataire.
  if command -v ss >/dev/null 2>&1; then
    local tenus; tenus="$(dc ps --status running -q mandataire 2>/dev/null | head -1)"
    if [[ -n "$tenus" ]]; then ligne info "ports 80 et 443: tenus par le mandataire de cette composition (deja en service)"
    else
      local p
      for p in 80 443; do
        if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$p$"; then
          ligne non "port $p de l'hote" "deja pris par un autre service; le mandataire ne pourra pas ecouter. Liberer le port, ou EUROSTRUCT_MANDATAIRE=non et faire renvoyer ce service vers les ports locaux."
        else ligne ok "port $p de l'hote libre"; fi
      done
    fi
  fi
}

cmd_prerequis() {
  echo "Prerequis de la mise a disposition sur staging:"
  verifier_outils
  if [[ -f "$ENVF" ]]; then charger_env; verifier_env
  else ligne non "$(basename "$ENVF")" "absent: cp deploy/staging.env.example deploy/staging.env; chmod 600; remplir."; fi
  if (( KO )); then
    echo "Au moins un prerequis manque (voir MANQUE). Rien n'a ete lance." >&2; exit 2
  fi
  echo "Tout est la. Suite: deploy/staging.sh privileges, puis migrer, puis up."
}

exiger_prerequis() {
  verifier_outils >/dev/null; charger_env; verifier_env >/dev/null
  (( KO )) && refus "un prerequis manque: « deploy/staging.sh prerequis » les liste."
  return 0
}

# ---------------------------------------------------------------------------
# LES COMMANDES
# ---------------------------------------------------------------------------
cmd_privileges() {
  exiger_prerequis
  dire "droits des trois roles sur la base hebergee (lecture seule)"
  ESC_PLAN_URL="$ESC_PLAN_URL" ESC_MIGRATOR_URL="$ESC_MIGRATOR_URL" \
  EUROSTRUCT_DATABASE_URL="$EUROSTRUCT_DATABASE_URL" \
    bash "$ICI/verifier_privileges.sh"
}

cmd_migrer() {
  exiger_prerequis
  [[ "${EUROSTRUCT_STAGING_CIBLE:-}" == "staging" ]] \
    || refus "« migrer » ECRIT sur la base hebergee (sceau, migrations, referentiel). Pour l'assumer: EUROSTRUCT_STAGING_CIBLE=staging deploy/staging.sh migrer"
  local TMP; TMP="$(mktemp -d)"; chmod 700 "$TMP"; trap 'rm -rf "$TMP"' EXIT
  local -a AUTO=(); sans_tls && AUTO=(--auto-heberge)
  local code=0

  echo "==> 1. sceau, migrations, activation — tools/deploy_eurostruct.sh"
  if ESC_PLAN_URL="$ESC_PLAN_URL" ESC_MIGRATOR_URL="$ESC_MIGRATOR_URL" \
     bash "$RACINE/tools/deploy_eurostruct.sh" "${AUTO[@]}" >"$TMP/deploi.log" 2>&1; then
    local etat; etat="$(sql ESC_PLAN_URL "select normative_activation_state()")"
    if [[ "$etat" == "ACTIVE" ]]; then dire "base ACTIVE"
    else echo "ECHEC: commande en 0 mais etat « ${etat:-illisible} »." >&2; code=1; fi
  else
    echo "ECHEC: deploy_eurostruct.sh a rendu $?: $(grep -m1 -oE 'DEPLOYMENT_[A-Z_]+|ACTIVE_SCHEMA_UPGRADE_REQUIRED|MIGRATION_[A-Z_]+' "$TMP/deploi.log" || echo 'voir le journal')" >&2
    sed -E 's#postgres(ql)?://[^ ]*#postgresql://<masquee>#g' "$TMP/deploi.log" | tail -15 | sed 's/^/      /' >&2
    exit 1
  fi

  echo "==> 2. referentiel des annexes nationales — db/seed/0001_ndp.sql, par le migrateur"
  if avec_url ESC_MIGRATOR_URL psql -X -q -v ON_ERROR_STOP=1 -f "$RACINE/db/seed/0001_ndp.sql" >"$TMP/seed.log" 2>&1; then
    dire "$(sql ESC_MIGRATOR_URL "select count(*) from national_annexes") annexe(s) au referentiel"
  else
    echo "ECHEC: le referentiel n'a pas pu etre pose: $(grep -m1 -i error "$TMP/seed.log" | cut -c1-120)" >&2; code=1
  fi

  echo "==> 3. admission du login applicatif dans eurostruct_authority_backend — par le plan de controle"
  local app; app="$(champ_url EUROSTRUCT_DATABASE_URL user)"
  if [[ "$app" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
    printf 'grant eurostruct_authority_backend to :"app";\n' \
      | avec_url ESC_PLAN_URL psql -X -q -v ON_ERROR_STOP=1 -v app="$app" >"$TMP/admission.log" 2>&1
    if [[ "$(sql ESC_PLAN_URL "select pg_has_role('$app','eurostruct_authority_backend','member')")" == "t" ]]; then
      dire "login applicatif admis"
    else echo "ECHEC: le login applicatif n'a pas pu etre admis: $(grep -m1 -iE 'ERROR|FATAL' "$TMP/admission.log" | cut -c1-120)" >&2; code=1; fi
  else
    echo "ECHEC: le login applicatif est illisible dans EUROSTRUCT_DATABASE_URL." >&2; code=1
  fi

  echo "==> 4. racine d'autorite — seulement si un mandat est declare"
  if [[ -n "${EUROSTRUCT_BOOTSTRAP_ACTOR:-}" && -n "${EUROSTRUCT_BOOTSTRAP_MANDATE:-}" ]]; then
    local base pose; base="$(champ_url ESC_MIGRATOR_URL base)"
    # LE MANDAT N'EST PAS POSE ICI: IL EST PROVISIONNE. `ALTER DATABASE … SET`
    # d'un parametre `eurostruct.*` est refuse a un non-superutilisateur —
    # « permission denied to set parameter », mesure a la quatrieme repetition
    # par le migrateur proprietaire de la base. C'est le compte administrateur
    # du fournisseur qui le pose (docs/DEPLOIEMENT_BASE_HEBERGEE.md §2); ici on
    # CONSTATE qu'il est pose et qu'il est CELUI de l'environnement.
    pose="$(sql ESC_PLAN_URL "select coalesce(current_setting('eurostruct.bootstrap_mandate', true), '')")"
    local existe; existe="$(sql ESC_MIGRATOR_URL "select count(*) from auth.users where id = '$EUROSTRUCT_BOOTSTRAP_ACTOR'::uuid")"
    if [[ "$pose" != "$EUROSTRUCT_BOOTSTRAP_MANDATE" ]]; then
      echo "NON EXECUTE: le mandat d'amorcage n'est pas pose sur la base « $base » (ou n'est pas celui de EUROSTRUCT_BOOTSTRAP_MANDATE). Avec le compte administrateur du fournisseur:" >&2
      echo "             ALTER DATABASE \"$base\" SET eurostruct.bootstrap_mandate = '<valeur de EUROSTRUCT_BOOTSTRAP_MANDATE>';" >&2
      echo "             puis relancez « migrer ». Rien d'autre n'est bloque par ce pas." >&2
      code=5
    elif [[ "$existe" != "1" ]]; then
      echo "NON EXECUTE: l'acteur du mandat n'existe pas dans auth.users. Creez ce compte dans Supabase Auth (Authentication > Users), reportez son uuid dans EUROSTRUCT_BOOTSTRAP_ACTOR, puis relancez « migrer »." >&2
      code=5
    else
      # LA PRIMITIVE DIT ELLE-MEME SI LA RACINE EXISTE DEJA. On ne compte pas
      # les habilitations par le plan de controle: sous RLS forcee il n'en
      # voit aucune, et un compte vide ou illisible se lisait « deja amorcee »
      # — mesure a la troisieme repetition, racine jamais posee.
      local sortie
      sortie="$(printf "select bootstrap_normative_administrator(:'acteur'::uuid, :'nom', :'motif');\n" \
        | avec_url ESC_PLAN_URL psql -X -q -tA -v ON_ERROR_STOP=1 -v acteur="$EUROSTRUCT_BOOTSTRAP_ACTOR" \
            -v nom="${EUROSTRUCT_BOOTSTRAP_NAME:-racine}" -v motif="${EUROSTRUCT_BOOTSTRAP_REASON:-amorcage du staging}" 2>&1)"
      if [[ "$sortie" =~ ^[0-9a-f-]{36}$ ]]; then
        dire "racine d'autorite amorcee (habilitation $sortie)"
      elif grep -q "existe deja" <<<"$sortie"; then
        dire "racine deja amorcee — rien a faire"
      else
        echo "ECHEC: l'amorcage a ete refuse (le mandat doit NOMMER l'acteur, et le plan de controle tenir eurostruct_deployment): $(grep -m1 -iE 'ERROR|FATAL|BOOTSTRAP' <<<"$sortie" | cut -c1-140)" >&2
        code=1
      fi
    fi
  else
    dire "aucun mandat declare: aucune racine amorcee (voulu — designer la premiere personne habilitee est une decision)"
  fi

  echo ""
  case "$code" in
    0) echo "Base prete. Suite: deploy/staging.sh up" ;;
    5) echo "Base prete, racine NON amorcee (voir ci-dessus). Suite: deploy/staging.sh up" ;;
    *) echo "Au moins un pas a ECHOUE (voir ci-dessus). Corriger, puis relancer « migrer »: chaque pas est idempotent." >&2 ;;
  esac
  exit "$code"
}

# ===========================================================================
# METTRE A JOUR UN STAGING QUI SERT DEJA
# ===========================================================================
# LA MEME IMPLEMENTATION QUE PARTOUT AILLEURS: `tools/deploy_eurostruct.sh
# --mettre-a-niveau`. Ce qui change ici, c'est ce que ce script peut faire
# AUTOUR — arreter l'API et l'interface de CETTE composition, puis les
# redemarrer et refaire les controles publics.
#
# LA BASE EST HEBERGEE, ET CE SCRIPT NE SAUVEGARDE PAS A LA PLACE DE
# L'EXPLOITANT. Sur `demo.sh`, la pile possede sa propre base et prend sa
# sauvegarde elle-meme; ici la base appartient a un fournisseur, l'acces
# d'administration n'est pas dans `staging.env`, et une commande qui
# pretendrait sauvegarder avec le migrateur produirait une archive
# PARTIELLE — RLS forcee, tables illisibles — qui se restaurerait sans rien
# dire. `ESC_UPGRADE_SAUVEGARDE` est donc exigee, et l'archive est inspectee
# par la commande officielle avant que la fenetre ne s'ouvre.
esc_man() {   # esc_man <arguments de tools/deploy_eurostruct.sh>
  local -a AUTO=(); sans_tls && AUTO=(--auto-heberge)
  ESC_PLAN_URL="$ESC_PLAN_URL" ESC_MIGRATOR_URL="$ESC_MIGRATOR_URL" \
    bash "$RACINE/tools/deploy_eurostruct.sh" "${AUTO[@]}" "$@"
}

cmd_diagnostic() {
  exiger_prerequis
  dire "diagnostic de mise a niveau — AUCUNE modification ne sera faite"
  esc_man --mettre-a-niveau --diagnostic
  local code=$?
  case $code in
    0) : ;;
    2) echo "" >&2
       echo "Au moins un prerequis manque (voir MANQUE). Rien n'a ete modifie." >&2
       echo "« deploy/staging.sh mettre-a-niveau » arrete l'API pour vous; la" >&2
       echo "sauvegarde, elle, reste votre geste: ESC_UPGRADE_SAUVEGARDE." >&2 ;;
    *) echo "" >&2; echo "Le diagnostic a rendu $code. Rien n'a ete modifie." >&2 ;;
  esac
  return $code
}

cmd_sauvegarder() {
  exiger_prerequis
  local base horo dest magique
  base="$(champ_url ESC_MIGRATOR_URL base)"
  if [[ -z "${EUROSTRUCT_SAUVEGARDE_URL:-}" ]]; then
    echo "REFUS: aucune DSN de sauvegarde declaree." >&2
    echo "       Une archive prise par le MIGRATEUR serait PARTIELLE: RLS est" >&2
    echo "       forcee sur les tables d'autorite, et ce qu'il ne lit pas" >&2
    echo "       n'entre pas dans le dump — sans que rien ne le signale." >&2
    echo "       Deux voies:" >&2
    echo "         1. declarez dans staging.env la DSN du compte" >&2
    echo "            d'administration du fournisseur:" >&2
    echo "              EUROSTRUCT_SAUVEGARDE_URL=postgresql://…" >&2
    echo "            puis relancez « deploy/staging.sh sauvegarder »;" >&2
    echo "         2. prenez la sauvegarde chez l'hebergeur, et declarez-la:" >&2
    echo "              ESC_UPGRADE_SAUVEGARDE=fournisseur:<ce qui a ete pris, quand>" >&2
    echo "       Voir docs/DEPLOIEMENT_BASE_HEBERGEE.md et docs/MISE_A_NIVEAU.md." >&2
    exit 2
  fi
  horo="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$ICI/sauvegardes/$horo"
  mkdir -p "$dest" || refus "impossible de creer « $dest »."
  chmod 700 "$ICI/sauvegardes" "$dest"
  dire "sauvegarde de « $base » par la DSN d'administration declaree"
  if ! avec_url EUROSTRUCT_SAUVEGARDE_URL pg_dump -Fc > "$dest/base.dump" 2>"$dest/.err"; then
    sed -n '1,5p' "$dest/.err" >&2; rm -rf "$dest"
    refus "la sauvegarde a echoue: rien n'a ete conserve."
  fi
  rm -f "$dest/.err"
  magique="$(head -c 5 "$dest/base.dump" 2>/dev/null)"
  [[ "$magique" == "PGDMP" ]] \
    || { rm -rf "$dest"; refus "l'archive produite n'est pas un « pg_dump -Fc »."; }
  chmod 600 "$dest/base.dump"

  # LE MAGASIN D'OBJETS, SEULEMENT S'IL EST SUR CET HOTE. En `s3`, les octets
  # sont chez un fournisseur et ce script n'a pas a pretendre les sauvegarder.
  if [[ "${EUROSTRUCT_STORAGE_BACKEND:-local}" == "local" ]]; then
    if dc run --rm --no-deps -T --user root --entrypoint tar api \
         -C /var/lib/eurostruct/livrables -cf - . > "$dest/livrables.tar" 2>/dev/null; then
      chmod 600 "$dest/livrables.tar"
      dire "livrables du volume local archives"
    else
      rm -f "$dest/livrables.tar"
      echo "AVERTISSEMENT: les livrables locaux n'ont pas pu etre archives." >&2
    fi
  else
    echo "NON COUVERT: EUROSTRUCT_STORAGE_BACKEND=${EUROSTRUCT_STORAGE_BACKEND}." >&2
    echo "             Les octets des PDF et des DXF sont dans le magasin objet" >&2
    echo "             du fournisseur: sauvegardez-le par ses moyens. Cette" >&2
    echo "             archive ne porte QUE la base." >&2
  fi
  echo ""
  echo "  sauvegarde: $dest/base.dump ($(stat -c %s "$dest/base.dump") o)"
  echo "  pour la mise a niveau: ESC_UPGRADE_SAUVEGARDE=$dest/base.dump"
  echo ""
}

cmd_mettre_a_niveau() {
  exiger_prerequis
  local base code
  base="$(champ_url ESC_MIGRATOR_URL base)"
  [[ "${EUROSTRUCT_STAGING_CIBLE:-}" == "staging" ]] \
    || refus "« mettre-a-niveau » APPLIQUE des migrations a la base hebergee « $base ».
       Pour l'assumer: EUROSTRUCT_STAGING_CIBLE=staging deploy/staging.sh mettre-a-niveau"
  [[ -n "${ESC_UPGRADE_SAUVEGARDE:-}" ]] \
    || refus "aucune sauvegarde declaree. Prenez-en une (« deploy/staging.sh sauvegarder »
       ou chez l'hebergeur), puis:
           ESC_UPGRADE_SAUVEGARDE=<archive pg_dump -Fc>   ou   fournisseur:<texte>"
  #: LE CONSENTEMENT NOMME LA BASE, et c'est la porte « CIBLE=staging » qui
  #: fait qu'il est donne: un consentement recopie d'un autre environnement ne
  #: correspondrait pas a ce nom-la.
  export ESC_UPGRADE_CONSENTEMENT="oui-mettre-a-niveau-$base"

  EUROSTRUCT_BUILD_SHA="$(identite_de_build)"; export EUROSTRUCT_BUILD_SHA
  dire "1/4 construction des images de la nouvelle version (le staging sert encore)"
  dc build || { echo "ECHEC: la construction s'est interrompue. RIEN n'a ete touche." >&2; exit 1; }

  dire "2/4 arret de l'API et de l'interface — les ecritures s'arretent ici"
  dc stop api web

  dire "3/4 mise a niveau de « $base », par la commande officielle"
  esc_man --mettre-a-niveau
  code=$?
  if [[ $code -ne 0 ]]; then
    echo "" >&2
    case $code in
      2) echo "ECHEC: prerequis refuses. RIEN N'A ETE MODIFIE; l'application repart." >&2
         dc up -d --wait --wait-timeout 600 api web >/dev/null 2>&1 ;;
      4) echo "ECHEC: une autre mise a niveau tient le verrou. RIEN N'A ETE MODIFIE." >&2 ;;
      *) echo "ECHEC: la mise a niveau s'est arretee (code $code) apres avoir ouvert sa" >&2
         echo "       fenetre. L'API et l'interface RESTENT ARRETEES." >&2
         echo "       Reprendre: deploy/staging.sh reprendre" >&2 ;;
    esac
    exit 1
  fi

  dire "4/4 redemarrage et controles publics"
  cmd_up
}

cmd_reprendre() {
  exiger_prerequis
  local code
  dire "reprise d'une mise a niveau interrompue"
  esc_man --reprendre-mise-a-niveau
  code=$?
  [[ $code -eq 0 ]] || { echo "" >&2
    echo "ECHEC: la reprise a rendu $code. L'API et l'interface restent arretees." >&2
    exit 1; }
  dire "la fenetre est refermee; redemarrage"
  cmd_up
}

identite_de_build() {
  local sha
  sha="$(git -C "$RACINE" rev-parse HEAD 2>/dev/null || true)"
  [[ -n "$sha" ]] || refus "aucun depot git lisible: sans identite de build, aucune etude ne peut etre enregistree."
  if ! git -C "$RACINE" diff --quiet 2>/dev/null; then
    # UN STAGING SERT UN COMMIT, PAS UN ARBRE MODIFIE: une etude conservee dix
    # ans doit designer un code qu'on peut retrouver.
    [[ "${EUROSTRUCT_STAGING_ARBRE_MODIFIE:-}" == "oui" ]] \
      || refus "l'arbre de travail est modifie. Commitez, ou assumez: EUROSTRUCT_STAGING_ARBRE_MODIFIE=oui (l'identite portera « -modifie »)."
    sha="${sha}-modifie"
  fi
  echo "$sha"
}

attendre() { local url="$1" n="$2"; for _ in $(seq 1 "$n"); do curl -fsS --max-time 2 -o /dev/null "$url" 2>/dev/null && return 0; sleep 1; done; return 1; }

cmd_up() {
  exiger_prerequis
  EUROSTRUCT_BUILD_SHA="$(identite_de_build)"; export EUROSTRUCT_BUILD_SHA
  dire "build: $EUROSTRUCT_BUILD_SHA"
  dire "construction des images api et web"
  if ! dc build; then
    echo "ECHEC: la construction des images s'est interrompue (reseau, proxy, disque). Relancez « deploy/staging.sh up »: elle reprend au dernier etage reussi." >&2
    exit 1
  fi
  dire "demarrage (l'API attend la base hebergee et le JWKS; les migrations ne sont PAS lancees ici)"
  if ! dc up -d --wait --wait-timeout 600; then
    echo "ECHEC: la composition n'est pas montee." >&2
    dc ps 2>&1 | sed 's/^/      /' >&2
    dc logs --no-color --tail 30 api 2>&1 | sed 's/^/      api | /' >&2
    echo "       Reprendre: « deploy/staging.sh journaux api », corriger, relancer « up »." >&2
    exit 1
  fi
  attendre "http://127.0.0.1:${API_PORT:-8000}/ready" 60 \
    || { echo "ECHEC: /ready ne passe pas au vert. Ce que l'API en dit:" >&2
         curl -sS "http://127.0.0.1:${API_PORT:-8000}/ready" 2>/dev/null | cut -c1-600 >&2
         echo "" >&2; echo "       Si « base » est rouge: « deploy/staging.sh migrer » n'a pas ete fait, ou la DSN est fausse." >&2; exit 1; }
  if mandataire_actif; then
    if [[ "${EUROSTRUCT_CADDY_TLS:-}" == "tls internal" && -n "${EUROSTRUCT_STAGING_CA_BUNDLE:-}" ]]; then
      # L'AUTORITE LOCALE DU MANDATAIRE, copiee pour les controles de CET hote
      # (repetition). Caddy la cree en delivrant son premier certificat: on
      # attend qu'elle existe plutot que de la declarer absente trop tot.
      local essai; for essai in $(seq 1 30); do
        dc cp mandataire:/data/caddy/pki/authorities/local/root.crt "$EUROSTRUCT_STAGING_CA_BUNDLE" >/dev/null 2>&1 && break
        sleep 1
      done
      [[ -s "$EUROSTRUCT_STAGING_CA_BUNDLE" ]] \
        && dire "autorite locale du mandataire copiee dans $(basename "$EUROSTRUCT_STAGING_CA_BUNDLE") (repetition: curl la verifie, aucun navigateur ne lui fait confiance)" \
        || echo "AVERTISSEMENT: l'autorite locale du mandataire n'a pas pu etre copiee; les controles des URL publiques echoueront sur le certificat." >&2
    fi
    dire "les URL publiques, par le mandataire (certificat verifie, jamais -k)"
    local u
    for u in "$EUROSTRUCT_PUBLIC_API_URL/ready" "$EUROSTRUCT_PUBLIC_WEB_URL/"; do
      if attendre_public "$u" 90; then dire "joint: $u"
      else
        echo "ECHEC: $u ne repond pas par le mandataire (90 s). Ce que le mandataire en dit:" >&2
        dc logs --no-color --tail 20 mandataire 2>&1 | sed 's/^/      mandataire | /' >&2
        echo "       ACME: les ports 80 et 443 doivent etre joignables d'Internet sous ce nom, et le DNS pointer vers cet hote. Reprendre: « deploy/staging.sh status »." >&2
        exit 1
      fi
    done
  fi
  echo ""
  echo "=================================================================="
  echo " EUROSTRUCT — STAGING, sur cet hote"
  echo "   API (boucle locale) : http://127.0.0.1:${API_PORT:-8000}/ready"
  echo "   interface (locale)  : http://127.0.0.1:${WEB_PORT:-3000}"
  echo "   URL publiques       : $EUROSTRUCT_PUBLIC_API_URL  et  $EUROSTRUCT_PUBLIC_WEB_URL"
  if mandataire_actif; then
  echo "                         (servies par le mandataire TLS de la composition, ports 80 et 443)"
  else
  echo "                         (servies par votre mandataire TLS -> ces deux ports locaux)"
  fi
  echo "   controle            : deploy/staging.sh status"
  echo "   recette             : deploy/staging.sh recette diagnostic"
  echo "=================================================================="
}

attendre_public() { local url="$1" n="$2"; for _ in $(seq 1 "$n"); do curl_public -fsS --max-time 5 -o /dev/null "$url" 2>/dev/null && return 0; sleep 1; done; return 1; }

# L'ETAT, ET LES CONTROLES DES URL PUBLIQUES — ceux qu'un navigateur ferait:
# /ready par le nom public en https, l'interface sans bandeau de demonstration,
# la reponse CORS de l'API a l'origine de l'interface, le certificat presente,
# la redirection http -> https. Chaque controle rate met le code de sortie a 1.
cmd_status() {
  charger_env
  dc ps
  echo ""
  echo "boucle locale:"
  curl -sS --max-time 5 "http://127.0.0.1:${API_PORT:-8000}/ready" 2>/dev/null \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
print("  ready:", d.get("ready"), "| environnement:", repr(d.get("environnement")))
for v in d.get("verifications", []):
    print("  %-22s %s" % (v["nom"], "ok" if v["ok"] else "NON"))' 2>/dev/null \
    || { echo "  l'API ne repond pas sur 127.0.0.1:${API_PORT:-8000}/ready."; KO=1; }
  if mandataire_actif; then echo "URL publiques (par le mandataire TLS de la composition):"
  else echo "URL publiques (par le mandataire TLS de l'hote):"; fi
  local TMP; TMP="$(mktemp -d)"; chmod 700 "$TMP"
  local api="${EUROSTRUCT_PUBLIC_API_URL%/}" web="${EUROSTRUCT_PUBLIC_WEB_URL%/}" code

  # 1. /ready par le nom public: 200, et un JSON qui dit ready.
  code="$(curl_public -sS -o "$TMP/ready.json" --max-time 15 -w '%{http_code}' "$api/ready" 2>"$TMP/ready.err" || echo "000")"
  if [[ "$code" == "200" ]] && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("ready") is True else 1)' "$TMP/ready.json" 2>/dev/null; then
    printf '  ok   %s -> 200, ready: True\n' "$api/ready"
  else
    printf '  NON  %s -> %s%s\n' "$api/ready" "$code" "$( [[ "$code" == "200" ]] && echo ", mais ready n'est pas True" )"; KO=1
    [[ -s "$TMP/ready.err" ]] && sed 's/^/       curl: /' "$TMP/ready.err" | head -2
  fi
  # 2. l'interface: 200, une page, sans le bandeau de demonstration.
  code="$(curl_public -sS -o "$TMP/web.html" --max-time 15 -w '%{http_code}' "$web/" 2>"$TMP/web.err" || echo "000")"
  if [[ "$code" == "200" ]] && grep -qi "<html" "$TMP/web.html" 2>/dev/null; then
    if grep -qi "environnement-demonstration" "$TMP/web.html"; then printf '  NON  %s -> 200, mais l'"'"'interface porte le bandeau de demonstration\n' "$web/"; KO=1
    else printf '  ok   %s -> 200, page servie, sans bandeau de demonstration\n' "$web/"; fi
  else
    printf '  NON  %s -> %s\n' "$web/" "$code"; KO=1
    [[ -s "$TMP/web.err" ]] && sed 's/^/       curl: /' "$TMP/web.err" | head -2
  fi
  # 3. CORS: l'API doit admettre l'origine de l'interface, sinon le navigateur
  #    est refuse a la premiere requete, et l'ecran reste vide sans dire pourquoi.
  local admis
  admis="$(curl_public -sS -o /dev/null --max-time 15 -X OPTIONS "$api/v1/projects" \
             -H "Origin: $web" -H 'Access-Control-Request-Method: POST' \
             -H 'Access-Control-Request-Headers: authorization,content-type' \
             -D - 2>/dev/null | tr -d '\r' | awk 'tolower($1)=="access-control-allow-origin:" {print $2}' | head -1)"
  if [[ "$admis" == "$web" ]]; then printf '  ok   CORS: l'"'"'API admet l'"'"'origine %s\n' "$web"
  else printf '  NON  CORS: l'"'"'API repond « %s » a l'"'"'origine %s (EUROSTRUCT_CORS_ORIGINS)\n' "${admis:-rien}" "$web"; KO=1; fi
  # 4. le certificat presente sur chaque nom, verifie par curl (et decrit si openssl est la).
  if [[ "$api" == https://* ]]; then
    local u
    for u in "$api" "$web"; do
      if curl_public -sS -o /dev/null --max-time 15 -w '%{certs}' "$u/" >"$TMP/certs.pem" 2>/dev/null && [[ -s "$TMP/certs.pem" ]]; then
        local desc; desc="$(openssl x509 -noout -issuer -enddate -in "$TMP/certs.pem" 2>/dev/null | tr '\n' ' ' | sed 's/issuer=//; s/notAfter=/expire le /')"
        printf '  ok   certificat verifie sur %s%s\n' "$(hote_de "$u")" "${desc:+ — $desc}"
      else
        printf '  NON  certificat non verifiable sur %s (autorite inconnue, nom absent du certificat, ou pas de TLS)\n' "$(hote_de "$u")"; KO=1
      fi
    done
    # 5. http -> https: le mandataire redirige, il ne sert rien en clair.
    if mandataire_actif; then
      local hweb; hweb="$(hote_de "$web")"
      code="$(curl_public -sS -o /dev/null --max-time 15 -w '%{http_code} %{redirect_url}' "http://$hweb/" 2>/dev/null || echo "000")"
      if [[ "$code" =~ ^30[178]\ https:// ]]; then printf '  ok   http://%s/ -> %s\n' "$hweb" "$code"
      else printf '  --   http://%s/ -> %s (pas de redirection vers https constatee depuis cet hote)\n' "$hweb" "${code:-000}"; fi
    fi
  fi
  rm -rf "$TMP"
  if (( KO )); then
    echo "Au moins un controle des URL publiques a echoue. Depuis cet hote: DNS (getent ahosts <nom>), pare-feu (80, 443), « deploy/staging.sh journaux mandataire »; puis verifier depuis un poste exterieur." >&2
    exit 1
  fi
  echo "Les URL publiques repondent comme un navigateur l'attend."
}

cmd_recette() {
  exiger_prerequis
  local mode="${1:-diagnostic}"
  case "$mode" in diagnostic|executer) ;; *) refus "usage: deploy/staging.sh recette [diagnostic|executer]" ;; esac
  local auto=""; sans_tls && auto="oui"
  EUROSTRUCT_RECETTE_CIBLE="${EUROSTRUCT_STAGING_CIBLE:-}" \
  EUROSTRUCT_RECETTE_TLS_AUTO_HEBERGE="$auto" \
    bash "$RACINE/db/test/recette_supabase_staging.sh" "$mode"
}

cmd_journaux() {
  charger_env
  local service="${1:-api}" n="${2:-100}"
  case "$service" in api|web|mandataire) ;; *) refus "service inconnu « $service » (api, web, mandataire)." ;; esac
  [[ "$n" =~ ^[0-9]+$ ]] || refus "nombre de lignes invalide « $n »."
  dc logs --no-color --tail "$n" "$service"
}

cmd_down() {
  charger_env
  dire "arret de l'API et de l'interface — le volume des livrables est GARDE"
  dc stop
}

case "${1:-}" in
  prerequis)       cmd_prerequis ;;
  privileges)      cmd_privileges ;;
  migrer)          cmd_migrer ;;
  up)              cmd_up ;;
  status)          cmd_status ;;
  recette)         cmd_recette "${2:-diagnostic}" ;;
  journaux)        cmd_journaux "${2:-}" "${3:-}" ;;
  down)            cmd_down ;;
  diagnostic)      cmd_diagnostic ;;
  sauvegarder)     cmd_sauvegarder ;;
  mettre-a-niveau) cmd_mettre_a_niveau ;;
  reprendre)       cmd_reprendre ;;
  *)
    sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2 ;;
esac
