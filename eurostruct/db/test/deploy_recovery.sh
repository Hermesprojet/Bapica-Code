#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6e: LA COMMANDE OFFICIELLE, QUAND ELLE ECHOUE
#
#   deploy_recovery.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `official_deployment.sh` etablit que la commande MARCHE. Celui-ci pose la
# question qui compte en exploitation: que laisse-t-elle derriere elle quand
# elle N'ABOUTIT PAS ?
#
# Un outil de deploiement passe l'essentiel de sa vie a reussir. Ce qui decide
# de sa qualite, ce sont les fois ou il echoue: une migration refusee, une
# coupure reseau, un `Ctrl-C`. A ces moments-la, il a deja accorde au migrateur
# la capacite d'endosser les roles d'autorite — et s'il part sans la reprendre,
# la base reste dans un etat que tout le jalon 6.3b6c existait pour rendre
# impossible.
#
# CE QUI EST EXERCE
# ------------------
#   P. LE PARCOURS GREENFIELD — la commande aboutit-elle par un chemin complet
#      et nomme, ou par un premier echec qu'on ignore ?
#   Q. LA COMPENSATION — apres un echec, que detient encore le migrateur ?
#   R. LES IDENTIFIANTS — un nom de role venu d'une URL est-il du SQL ?
#   S. LA CONCURRENCE — deux commandes peuvent-elles s'intercaler ?
#   T. LA REPRISE — une phase 1 interrompue se relance-t-elle ?
#   U. LE SQLSTATE — la commande branche-t-elle sur le code ou sur la prose ?
#   V. LA CONNEXION — l'environnement peut-il rediriger la cible ?
#
# COMMENT L'ECHEC EST INJECTE, ET POURQUOI AINSI
# -----------------------------------------------
# Le harnais construit une COPIE OCTET POUR OCTET de la commande, dans une
# arborescence temporaire portant ses propres migrations. La commande calcule
# ses chemins depuis sa propre position (`RACINE=$(dirname $(dirname $0))`):
# la copie lit donc les migrations de la copie, et le depot n'est jamais
# modifie. L'empreinte de la copie est comparee a l'original avant chaque
# scenario — sans quoi on testerait autre chose que la commande officielle.
#
# Toutes les identites sont FICTIVES. Aucune confirmation normative n'est creee.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
RACINE="$(dirname "$DB_DIR")"
COMMANDE="$RACINE/tools/deploy_eurostruct.sh"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"

PREFIXE="${1:?usage: deploy_recovery.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "deploy_recovery.sh" || exit 2
exiger_cluster_jetable  "deploy_recovery.sh" || exit 2
harnais_verrou_prendre  "deploy_recovery.sh" || exit $?
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

# --------------------------------------------------------------------------
# LES LEURRES SONT ECRITS, PAS EXECUTES — barriere sur le corps des heredocs
# --------------------------------------------------------------------------
# CE QU'ELLE EMPECHE, ET IL A FALLU UNE EXECUTION REELLE POUR LE VOIR. Les
# leurres sont produits par des heredocs NON CITES: `$vrai`, `$BASE` et `$motif`
# doivent y etre resolus a la generation, c'est leur raison d'etre. Mais un
# ACCENT GRAVE dans ce corps ouvre alors une substitution de commande, et le
# shell du HARNAIS execute le mot — y compris dans ce qui n'est qu'un
# commentaire destine au leurre.
#
# Mesure faite: deux lignes de commentaire portant \`-d "$BASE"\` et
# \`pg_locks\` faisaient executer trois commandes par leurre construit. Le
# commentaire arrivait mutile dans le leurre, et « command not found » tombait
# sur la sortie d'erreur du harnais — a l'endroit exact ou une VRAIE panne de
# leurre se serait affichee. Un bruit permanent qui rend une panne reelle
# indiscernable est un defaut de harnais, pas une coquetterie.
#
# La barriere lit LA SOURCE DU HARNAIS LUI-MEME et refuse de demarrer si un
# corps de leurre contient un accent grave ou un « $( » non echappes. Elle vaut
# pour les cinq leurres actuels et pour ceux qu'on ecrira ensuite.
exiger_leurres_inertes() {
  local rapport
  rapport="$(python3 - "${BASH_SOURCE[0]}" <<'FININERTE'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read().split("\n")
faits, dedans = [], False
for n, l in enumerate(src, 1):
    if not dedans:
        if re.search(r'<<LEURREFIN\s*$', l):
            dedans = True
        continue
    if l.strip() == "LEURREFIN":
        dedans = False
        continue
    if re.search(r'(?<!\\)`', l) or re.search(r'(?<!\\)\$\(', l):
        faits.append(f"{n}: {l.strip()[:88]}")
print("\n".join(faits))
FININERTE
  )" || { echo "REFUS: l'inspection des leurres n'a pas pu s'executer." >&2; return 2; }
  [[ -z "$rapport" ]] && return 0
  {
    echo "REFUS: un corps de leurre contient une substitution de commande."
    echo "       Ces heredocs ne sont PAS cites: le shell du harnais executerait"
    echo "       ces mots a la generation, mutilerait le leurre, et polluerait la"
    echo "       sortie d'erreur ou se lisent les vraies pannes de leurre."
    echo
    echo "       Echappez l'accent grave (\\\`) ou le \\\$( :"
    sed 's/^/         /' <<<"$rapport"
  } >&2
  return 2
}
exiger_leurres_inertes || exit 2

JETON="$(harnais_jeton)"
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
AUTORITES=(eurostruct_normative_writer eurostruct_normative_bootstrap
           eurostruct_normative_activator)
exiger_roles_absents "deploy_recovery.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

KO=0; ROUGES=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
rouge()  { echo "      ROUGE ATTENDU (a fermer): $*"; ROUGES=$((ROUGES + 1)); }
detail() { echo "                                $*"; }

adm() { psql -X -q -d postgres "$@"; }

[[ -x "$COMMANDE" ]] || { echo "      ECHEC: $COMMANDE introuvable" >&2
                          harnais_verrou_rendre; exit 2; }

# LA COMMANDE PARLE EN URL, DONC EN TCP (meme raison que official_deployment.sh).
if ! harnais_tcp_joignable; then
  echo "NON EXECUTE: le cluster n'accepte pas de connexion TCP sur" >&2
  echo "       localhost:${PGPORT:-5432}." >&2
  harnais_verrou_rendre
  exit 4
fi

# --------------------------------------------------------------------------
# L'ARBORESCENCE DE TRAVAIL — une copie fidele, des migrations controlees
# --------------------------------------------------------------------------
COPIE="$(mktemp -d "/tmp/${PREFIXE}_deploiement.XXXXXX")"
mkdir -p "$COPIE/tools" "$COPIE/db/control_plane" "$COPIE/db/migrations"
cp "$COMMANDE" "$COPIE/tools/"
cp "$DB_DIR/control_plane/"*.sql "$COPIE/db/control_plane/"
# L'APPLICATEUR PART AVEC ELLE. La commande le charge depuis SA propre racine
# (`$RACINE/db/apply_migration.sh`): sans cette copie, le `source` echouait en
# silence — `set -uo pipefail` sans `-e` ne stoppe pas — et chaque migration
# rendait « command not found » avec un message d'echec VIDE. Defaut mesure.
cp "$DB_DIR/apply_migration.sh" "$COPIE/db/"
COMMANDE_COPIE="$COPIE/tools/$(basename "$COMMANDE")"

# LES EMPREINTES, CONSTATEES. Un harnais qui testerait une copie divergente ne
# dirait rien de la commande officielle — et le dirait avec assurance.
for paire in "$COMMANDE:$COMMANDE_COPIE" \
             "$DB_DIR/apply_migration.sh:$COPIE/db/apply_migration.sh"; do
  if [[ "$(sha256sum <"${paire%%:*}" | cut -d' ' -f1)" \
     != "$(sha256sum <"${paire##*:}" | cut -d' ' -f1)" ]]; then
    echoue "la copie de $(basename "${paire%%:*}") differe de l'original"
    harnais_verrou_rendre; exit 2
  fi
done

# `migrations_copiees [casse] [position]` — repose le jeu de migrations de la
# copie.
#
#   casse    vide      -> jeu sain
#            « avant » -> un fichier fautif qui s'applique EN PREMIER
#            <nom>     -> ce fichier est sabote
#            « apres » -> une migration supplementaire retire, APRES la phase 1,
#                         le droit de lire le manifeste
#
#   position « dans »  (defaut) -> l'echec tombe DANS la transaction: la
#                         migration n'est pas inscrite au registre;
#            « apres_commit » -> l'echec tombe APRES le `commit`: la migration
#                         EST inscrite, et le runner voit pourtant un echec.
#                         C'est la coupure reseau apres le commit serveur mais
#                         avant que le client ait recu le resultat.
#
# LA POSITION N'EST PAS UN DETAIL. Premiere ecriture: l'instruction fautive
# etait ajoutee a la FIN du fichier, donc apres son `commit`. La migration
# etait donc VALIDEE, ligne de registre comprise, et la relance rendait
# MIGRATION_CHECKSUM_MISMATCH — un refus exact, mais sur un sujet que T1 a T3
# ne traitent pas. Le contre-exemple mesurait autre chose que ce qu'il annonce.
migrations_copiees() {
  local casse="${1:-}" position="${2:-dans}"
  rm -f "$COPIE/db/migrations/"*.sql
  cp "$DB_DIR/migrations/"*.sql "$COPIE/db/migrations/"
  case "$casse" in
    "") : ;;
    avant)
      # Trie AVANT 0001: il echoue donc avant la premiere vraie migration.
      cat >"$COPIE/db/migrations/0000_echec_injecte.sql" <<'SQL'
-- FICTIF — echec injecte par db/test/deploy_recovery.sh.
begin;
do $$ begin raise exception 'ECHEC INJECTE avant la premiere migration'; end $$;
commit;
SQL
      ;;
    apres)
      # Trie APRES 0010. Elle REUSSIT, et retire au role de deploiement le
      # droit de lire le manifeste: l'echec tombe donc a l'etape 6, entre la
      # derniere migration et la finalisation. C'est un echec DETERMINISTE au
      # bon endroit — une course sur un signal ne l'aurait pas ete.
      cat >"$COPIE/db/migrations/0011_echec_injecte_apres.sql" <<'SQL'
-- FICTIF — echec injecte par db/test/deploy_recovery.sh, APRES la phase 1.
begin;
revoke execute on function normative_settings_manifest() from eurostruct_deployment;
commit;
SQL
      ;;
    *)
      local cible="$COPIE/db/migrations/$casse"
      local faute
      faute=$(printf 'do $$ begin raise exception %s; end $$;' \
                "'ECHEC INJECTE dans $casse'")
      if [[ "$position" == "apres_commit" ]]; then
        # LE FICHIER DOIT ETRE IDENTIQUE DANS LES DEUX PASSAGES, sans quoi la
        # relance rendrait MIGRATION_CHECKSUM_MISMATCH — un refus exact, sur un
        # sujet que T6 ne traite pas. Premiere ecriture, mesuree: l'instruction
        # etait ajoutee au premier passage et retiree au second, et T6 rougissait
        # sur le checksum au lieu de la reprise.
        #
        # L'ECHEC NE SE PRODUIT DONC QU'UNE FOIS, et sans que le texte change:
        # il est conditionne a l'absence de la migration SUIVANTE dans le
        # registre. Au premier passage elle n'y est pas — l'echec tombe, apres
        # que celle-ci a ete validee. Au second, le fichier est SAUTE et n'est
        # meme pas lu.
        local suivante
        suivante=$(cd "$COPIE/db/migrations" && ls *.sql | awk -v c="$casse" '$0>c' | head -1)
        cat >>"$cible" <<SQLT6

-- FICTIF — coupure simulee APRES le commit serveur (db/test/deploy_recovery.sh).
do \$\$
begin
  if not exists (select 1 from normative_migration_ledger
                  where migration_id = '$suivante') then
    raise exception 'ECHEC INJECTE apres le commit de $casse';
  end if;
end
\$\$;
SQLT6
      else
        # DANS la transaction: juste avant l'inscription au registre, donc
        # avant le `commit`. Rien n'est valide.
        python3 - "$cible" "$faute" <<'FINPY'
import sys, pathlib
cible, faute = pathlib.Path(sys.argv[1]), sys.argv[2]
s = cible.read_text()
marque = "select normative_migration_applied("
i = s.index(marque)
# On remonte au debut de la ligne de commentaire qui precede l'appel.
cible.write_text(s[:i] + faute + "\n" + s[i:])
FINPY
      fi
      ;;
  esac
}

# --------------------------------------------------------------------------
# LE DECOR
# --------------------------------------------------------------------------
MIG=""; CTL=""; BASE=""; MDP=""
admb() { psql -X -q -d "$BASE" "$@"; }

decor_poser() {
  local s="$1"
  MIG="${PREFIXE}_m${s}_${JETON}"
  CTL="${PREFIXE}_c${s}_${JETON}"
  BASE="${PREFIXE}_d${s}_${JETON}"
  MDP="FICTIF-dr-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" || return 1
  creer_role "$CTL" "login password '$MDP' createrole"          || return 1
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  creer_base "$BASE" "owner \"$MIG\"" || return 1
  registre_base "$BASE"

  admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL
  adm -c "alter database \"$BASE\"
            set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
  return 0
}

decor_deposer() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}

SORTIE_CMD=""
# `appeler [options]` — la COPIE de la commande officielle, jamais psql.
appeler() {
  SORTIE_CMD=$(
    ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    bash "$COMMANDE_COPIE" "$@" 2>&1
  )
  return $?
}

# `capacites_du_migrateur` — les TROIS capacites sur les TROIS roles
# d'autorite. Vide = le migrateur ne detient rien.
capacites_du_migrateur() {
  adm -tAc "
    select coalesce(string_agg(a.r || '(' ||
        case when pg_has_role('$MIG', a.r, 'SET') then 'SET ' else '' end ||
        case when pg_has_role('$MIG', a.r, 'USAGE') then 'USAGE ' else '' end ||
        case when pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')
             then 'ADMIN' else '' end || ')', ' '), '')
      from unnest(array['${AUTORITES[0]}','${AUTORITES[1]}','${AUTORITES[2]}']) a(r)
     where pg_has_role('$MIG', a.r, 'SET')
        or pg_has_role('$MIG', a.r, 'USAGE')
        or pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1
}

# `etat_normatif` — ce que la base engage, en une ligne.
etat_normatif() {
  admb -tAc "
    select coalesce((select normative_activation_state()), 'SANS SCEAU')
        || ' activations=' || (select count(*) from normative_activation)
        || ' plans=' || (select count(*) from normative_control_plane)" 2>&1 \
  || echo "illisible"
}

NETTOYAGE_KO=0
TOUS_ROLES=()
suivre_decor() { TOUS_ROLES+=("$MIG" "$CTL"); }
sortie_propre() {
  local r
  decor_deposer
  rm -rf "$COPIE"
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}"; do
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "deploy_recovery.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    la commande officielle, quand elle echoue"

# ==========================================================================
# P. LE PARCOURS GREENFIELD
# ==========================================================================
# La commande s'annonce en DIX ETAPES. Sur une base neuve, elle n'en franchit
# pas trois: `eurostruct_deployment` n'existe qu'apres la phase 0, personne ne
# le detient donc au premier appel, et l'etape 2 s'arrete.
#
# Le harnais `official_deployment.sh` decrit ce parcours sans le nommer:
#
#     deployer >/dev/null 2>&1        # premier appel, echec ignore
#     adm -c "grant eurostruct_deployment to ..."
#     deployer                        # second appel
#
# UN ECHEC UTILISE COMME MECANISME DE PROGRESSION N'EN EST PAS UN. Ce que la
# commande doit offrir est soit un appel unique qui aboutit, soit DEUX MODES
# EXPLICITEMENT NOMMES, avec leurs etats et leurs codes de sortie.

# --- P1. un seul appel sur une base neuve ---------------------------------
if ! decor_poser p1; then
  echoue "le decor P1 n'a pas pu etre pose"
else
suivre_decor
migrations_copiees
appeler; CODE_P1=$?
ETAT_P1=$(admb -tAc "select normative_activation_state()" 2>&1)
if [[ $CODE_P1 -eq 0 && "$ETAT_P1" == "ACTIVE" ]]; then
  echo "      ok: P1. un seul appel sur une base neuve atteint ACTIVE"
else
  rouge "P1. un seul appel n'atteint pas ACTIVE (code $CODE_P1, etat « $(cut -c1-60 <<<"$ETAT_P1")… »)."
  detail "    Derniere etape franchie:"
  detail "      $(grep -E '^== ' <<<"$SORTIE_CMD" | tail -1)"
  detail "      $(grep -m1 -E '^ECHEC' <<<"$SORTIE_CMD" | cut -c1-130)"
  detail "    La commande s'annonce en dix etapes et s'arrete a la deuxieme."
fi

# --- P1b. le plan PEUT s'accorder le role de deploiement -------------------
# Le correctif recommande n'est possible que si la capacite existe. Elle
# existe: PostgreSQL 16 donne au CREATEUR d'un role un ADMIN residuel (fait
# F1), et c'est le plan de controle qui cree les six roles en phase 0. Ce
# constat est ecrit pour que le jour ou il cesserait d'etre vrai, on le sache.
CAP_P1=$(adm -tAc "select 'set=' || pg_has_role('$CTL','eurostruct_deployment','SET')
                       || ' usage=' || pg_has_role('$CTL','eurostruct_deployment','USAGE')
                       || ' admin=' || pg_has_role('$CTL','eurostruct_deployment','MEMBER WITH ADMIN OPTION')" 2>&1)
if [[ "$CAP_P1" == *"admin=t"* ]]; then
  echo "      ok: P1b. apres la phase 0, le plan detient l'ADMIN sur"
  echo "             eurostruct_deployment ($CAP_P1) — il peut se l'accorder"
else
  echoue "P1b. le plan ne detient pas l'ADMIN sur eurostruct_deployment ($CAP_P1);"
  echoue "     le correctif recommande du point 1 ne serait pas applicable"
fi
decor_deposer
fi

# --- P2. roles preexistants sans capacite pour le plan --------------------
# Forme documentee: les six roles PREEXISTENT, provisionnes par un tiers. Le
# plan de controle n'a alors aucun ADMIN residuel, et ne peut pas s'accorder
# `eurostruct_deployment`. Ce qui est exige n'est pas qu'il y arrive: c'est un
# REFUS DE PREREQUIS NOMME, tombant AVANT que writer/bootstrap ne soient
# pretes au migrateur.
if ! decor_poser p2; then
  echoue "le decor P2 n'a pas pu etre pose"
else
suivre_decor
adm -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
create role normative_backend;
create role normative_governance;
create role eurostruct_normative_writer nologin;
create role eurostruct_normative_bootstrap nologin;
create role eurostruct_normative_activator nologin;
create role eurostruct_deployment nologin;
-- Le plan recoit STRICTEMENT de quoi poser le sceau, et rien sur le role de
-- deploiement.
grant eurostruct_normative_activator to "$CTL" with admin option, set false, inherit false;
grant eurostruct_normative_writer    to "$CTL" with admin option, set false, inherit false;
grant eurostruct_normative_bootstrap to "$CTL" with admin option, set false, inherit false;
SQL
migrations_copiees
appeler; CODE_P2=$?
CAP_P2=$(capacites_du_migrateur)
# CE QUI EST EXIGE, ET POURQUOI C'EST ECRIT AINSI (6.3b6e).
#
# La premiere version demandait « code non nul ET la sortie contient
# "prerequis" ou "eurostruct_deployment" ET aucune capacite ». Elle etait
# HOLLOW, et la matrice de mutation l'a montre: retirer LES DEUX garanties de
# l'etape 2b la laissait verte. La raison est que `eurostruct_deployment`
# apparait dans un message de REUSSITE de cette etape —
# « ok: eurostruct_deployment accorde a ... » —, si bien que n'importe quel
# echec SURVENU PLUS LOIN satisfaisait le motif. Mesure: la commande mutee
# tombait sur « permission denied for function normative_activation_state »,
# trois etapes apres, et P2 l'acceptait.
#
# Trois exigences la remplacent, et chacune ferme une moitie du defaut:
#
#   1. LE CODE 3, et non « non nul ». Un prerequis non tenu se distingue d'une
#      panne; le texte ne sert qu'a l'affichage.
#   2. LE REFUS TOMBE AVANT L'OCTROI. Le constat de reussite de l'etape 2b ne
#      doit PAS figurer dans la sortie: s'il y est, l'octroi a eu lieu et le
#      refus vient d'ailleurs.
#   3. AUCUNE CAPACITE, inchange.
if [[ $CODE_P2 -eq 3 ]] \
   && grep -qF "DEPLOYMENT_PRECONDITION_FAILED" <<<"$SORTIE_CMD" \
   && ! grep -qF "eurostruct_deployment accorde" <<<"$SORTIE_CMD" \
   && [[ -z "$CAP_P2" ]]; then
  echo "      ok: P2. prerequis manquant: refus code 3 avant tout octroi"
else
  rouge "P2. roles preexistants sans capacite sur eurostruct_deployment:"
  detail "    code $CODE_P2 (3 attendu), capacites du migrateur: « ${CAP_P2:-aucune} »"
  detail "      $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_CMD" | cut -c1-130)"
  if grep -qF "eurostruct_deployment accorde" <<<"$SORTIE_CMD"; then
    detail "    L'ETAPE 2b A REUSSI: le refus observe vient d'AILLEURS, plus loin."
  fi
  detail "    Le refus doit porter le code 3, et tomber AVANT que"
  detail "    writer/bootstrap ne soient pretes au migrateur."
fi
decor_deposer
fi

# ==========================================================================
# Q. LA COMPENSATION — ce que la commande laisse derriere elle
# ==========================================================================
# A l'etape 3, la commande accorde au migrateur writer et bootstrap AVEC ADMIN
# OPTION. Il n'existe ensuite aucun piege de sortie. Si une migration echoue,
# si la lecture du manifeste echoue, si l'operateur interrompt — le script part
# en laissant le migrateur capable d'endosser ET de readministrer les roles
# d'autorite.
#
# CE N'EST PAS UNE IMPERFECTION D'ERGONOMIE. C'est exactement l'etat que
# 6.3b6c existait pour rendre impossible, reintroduit par l'outil cense
# l'installer.
#
# `q_verifier <nom> <code> <capacites>` — le meme constat pour les trois
# scenarios: zero capacite, PENDING, aucune activation, aucun plan fige.
q_verifier() {
  local nom="$1" code="$2" cap="$3" etat
  etat=$(etat_normatif)
  if [[ -z "$cap" && "$etat" == "PENDING activations=0 plans=0" ]]; then
    echo "      ok: $nom. apres l'echec: aucune capacite, $etat"
    return 0
  fi
  rouge "$nom. apres l'echec (code $code), le migrateur detient encore:"
  detail "    ${cap:-aucune capacite}"
  detail "    etat de la base: $etat"
  detail "    La commande a accorde ces roles a l'etape 3 et est partie sans"
  detail "    les reprendre. Le migrateur peut endosser et readministrer les"
  detail "    roles d'autorite sur une base en cours de deploiement."
  return 1
}

# `q_amorcer` — pose le decor, et RIEN DE PLUS.
#
# LA VERSION ROUGE APPELAIT LA COMMANDE UNE PREMIERE FOIS puis accordait
# `eurostruct_deployment` de l'exterieur: c'etait le parcours reel tant que la
# commande ne savait pas s'accorder ce role (defaut P1). Depuis qu'elle le
# fait, un premier appel DEPLOIERAIT ENTIEREMENT la base — les scenarios Q
# n'atteindraient plus jamais l'octroi qu'ils testent, et seraient verts pour
# la mauvaise raison.
q_amorcer() {
  local s="$1"
  decor_poser "$s" || return 1
  suivre_decor
  return 0
}

# --- Q1. echec AVANT la premiere migration --------------------------------
if ! q_amorcer q1; then
  echoue "le decor Q1 n'a pas pu etre pose"
else
migrations_copiees avant
appeler; CODE_Q1=$?
q_verifier "Q1" "$CODE_Q1" "$(capacites_du_migrateur)"
decor_deposer
fi

# --- Q2. echec AU MILIEU de la phase 1 ------------------------------------
if ! q_amorcer q2; then
  echoue "le decor Q2 n'a pas pu etre pose"
else
migrations_copiees 0005_validation_workflow.sql
appeler; CODE_Q2=$?
q_verifier "Q2" "$CODE_Q2" "$(capacites_du_migrateur)"
decor_deposer
fi

# --- Q3. echec APRES la derniere migration, avant la finalisation ---------
# UNE PREMIERE ECRITURE COURAIT APRES UN SIGNAL: elle attendait que la commande
# annonce l'etape 6, puis l'interrompait. La fenetre entre l'etape 6 et la fin
# vaut quelques millisecondes: la commande avait DEJA FINI, la base etait
# ACTIVE, et le scenario rougissait en annoncant une compensation manquante
# qu'il n'avait pas exercee. Un contre-exemple qui ne tient pas sa fenetre ne
# dit rien de ce qu'il nomme.
#
# L'echec est donc pose DANS LA BASE: une derniere migration retire au role de
# deploiement le droit de lire le manifeste. Elle reussit; l'etape 6 echoue.
if ! q_amorcer q3; then
  echoue "le decor Q3 n'a pas pu etre pose"
else
migrations_copiees apres
appeler; CODE_Q3=$?
q_verifier "Q3" "$CODE_Q3" "$(capacites_du_migrateur)"
decor_deposer
fi

# --- Q5. INTERRUPTION PAR SIGNAL pendant la phase 1 -----------------------
# LE CHEMIN QU'UN PIEGE `EXIT` SEUL NE COUVRE PAS. Sur TERM, INT ou HUP, bash
# meurt avant d'executer son piege de sortie si le signal n'est pas intercepte
# — defaut mesure en 6.3b6c, et la raison d'etre de `harnais_piege_signaux`.
# La commande officielle doit tenir la meme discipline: c'est le cas de
# l'operateur qui fait `Ctrl-C`, et du pipeline qu'on annule.
#
# LA FENETRE EST ICI CONFORTABLE: la phase 1 dure plusieurs secondes. On attend
# qu'une migration du milieu soit annoncee, puis on interrompt.
if ! q_amorcer q5; then
  echoue "le decor Q5 n'a pas pu etre pose"
else
migrations_copiees
JOURNAL="$COPIE/q5.log"
: >"$JOURNAL"
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$JOURNAL" 2>&1
) &
PID_Q5=$!
# `exec`: le sous-shell est REMPLACE par bash, si bien que `$PID_Q5` designe la
# commande elle-meme. Sans lui, on interromprait un sous-shell et la commande
# orpheline continuerait — defaut mesure en 6.3b6c, scenario 14.
ATTENTE=0
while [[ $ATTENTE -lt 600 ]]; do
  grep -q "0005_" "$JOURNAL" 2>/dev/null && break
  kill -0 "$PID_Q5" 2>/dev/null || break
  sleep 0.2
  ATTENTE=$((ATTENTE + 1))
done
if grep -q "0005_" "$JOURNAL" 2>/dev/null && kill -0 "$PID_Q5" 2>/dev/null; then
  kill -TERM "$PID_Q5" 2>/dev/null
  wait "$PID_Q5" 2>/dev/null; CODE_Q5=$?
  sleep 2   # le piege, s'il existe, a besoin d'un instant pour revoquer
  ETAT_Q5=$(etat_normatif)
  if [[ "$ETAT_Q5" == "ACTIVE"* ]]; then
    echoue "Q5. la commande a eu le temps d'aboutir: la fenetre n'a pas tenu"
  else
    q_verifier "Q5" "$CODE_Q5" "$(capacites_du_migrateur)"
  fi
else
  wait "$PID_Q5" 2>/dev/null
  echoue "Q5. la phase 1 n'a pas ete interrompue a temps; scenario non evalue"
  tail -3 "$JOURNAL" | sed 's/^/              /' >&2
fi
decor_deposer
fi

# --- Q6. UN ARRET NON INTERCEPTABLE ---------------------------------------
# LES PIEGES NE COUVRENT PAS TOUT. `TERM`, `INT` et `HUP` s'interceptent;
# `SIGKILL`, un crash du shell, une panne machine ou un conteneur supprime ne
# declenchent RIEN. La base reste alors PENDING avec les emprunts accordes, et
# aucun code n'a jamais tourne pour les reprendre.
#
# CE QUI EST EXIGE N'EST PAS QUE LA COMMANDE SURVIVE — elle ne le peut pas.
# C'est que:
#
#   1. l'etat laisse soit exactement celui-la, et pas un ACTIVE a moitie;
#   2. une RELANCE ORDINAIRE reste fail-closed — elle ne doit pas reprendre en
#      silence des appartenances qu'elle n'a pas accordees;
#   3. une reprise existe, EXPLICITE, et ne revoque qu'apres avoir tout prouve.
if ! q_amorcer q6; then
  echoue "le decor Q6 n'a pas pu etre pose"
else
migrations_copiees
JOURNAL_Q6="$COPIE/q6.log"
: >"$JOURNAL_Q6"
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$JOURNAL_Q6" 2>&1
) &
PID_Q6=$!
ATTENTE=0
while [[ $ATTENTE -lt 600 ]]; do
  grep -q "0005_" "$JOURNAL_Q6" 2>/dev/null && break
  kill -0 "$PID_Q6" 2>/dev/null || break
  sleep 0.2
  ATTENTE=$((ATTENTE + 1))
done
if ! grep -q "0005_" "$JOURNAL_Q6" 2>/dev/null || ! kill -0 "$PID_Q6" 2>/dev/null; then
  wait "$PID_Q6" 2>/dev/null
  echoue "Q6. la phase 1 n'a pas ete atteinte a temps; scenario non evalue"
  tail -3 "$JOURNAL_Q6" | sed 's/^/              /' >&2
else
  # AUCUN PIEGE NE VA S'EXECUTER. C'est le propos.
  kill -KILL "$PID_Q6" 2>/dev/null
  wait "$PID_Q6" 2>/dev/null
  sleep 1
  ETAT_Q6=$(etat_normatif)
  CAP_Q6=$(adm -tA -v m="$MIG" <<'SQL'
select coalesce(string_agg(a.r, ' '), '') from unnest(array[
  'eurostruct_normative_writer','eurostruct_normative_bootstrap']) a(r)
 where pg_has_role(:'m', a.r, 'SET') or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
  )
  if [[ "$ETAT_Q6" == "ACTIVE"* ]]; then
    echoue "Q6. la commande a eu le temps d'aboutir: la fenetre n'a pas tenu"
  elif [[ -z "$CAP_Q6" ]]; then
    echoue "Q6. apres SIGKILL, le migrateur ne detient rien: le scenario n'a"
    echoue "    pas capture la fenetre ou les emprunts sont accordes."
  else
    # 2. LA RELANCE ORDINAIRE RESTE FAIL-CLOSED.
    appeler; CODE_Q6R=$?
    if [[ $CODE_Q6R -ne 3 ]] \
       || ! grep -qF "DEPLOYMENT_PRECONDITION_FAILED" <<<"$SORTIE_CMD"; then
      rouge "Q6. apres un SIGKILL, la relance ordinaire ne refuse pas."
      detail "    code $CODE_Q6R (3 attendu); « $MIG » detenait: $CAP_Q6"
      detail "    Une commande qui reprend des appartenances qu'elle n'a pas"
      detail "    accordees revoque ce qu'un tiers a peut-etre pose."
    else
      # 3. LA REPRISE EXPLICITE.
      appeler --recover-pending; CODE_Q6V=$?
      CAP_Q6B=$(adm -tA -v m="$MIG" <<'SQL'
select coalesce(string_agg(a.r, ' '), '') from unnest(array[
  'eurostruct_normative_writer','eurostruct_normative_bootstrap']) a(r)
 where pg_has_role(:'m', a.r, 'SET') or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
      )
      if [[ $CODE_Q6V -ne 0 || -n "$CAP_Q6B" ]]; then
        rouge "Q6. la reprise explicite n'a pas rendu la base a zero capacite."
        detail "    code $CODE_Q6V; reste: « ${CAP_Q6B:-aucune} »"
        detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_CMD" | cut -c1-140)"
      else
        # ...ET UN DEPLOIEMENT NORMAL DOIT ENSUITE ABOUTIR.
        appeler; CODE_Q6F=$?
        ETAT_Q6F=$(admb -tAc "select normative_activation_state()" 2>&1)
        if [[ $CODE_Q6F -eq 0 && "$ETAT_Q6F" == "ACTIVE" ]]; then
          echo "      ok: Q6. SIGKILL: relance refusee, reprise explicite, puis ACTIVE"
        else
          rouge "Q6. apres la reprise, un deploiement normal n'aboutit pas."
          detail "    code $CODE_Q6F, etat « $ETAT_Q6F »"
          detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_CMD" | cut -c1-140)"
        fi
      fi
    fi
  fi
fi
decor_deposer
fi

# --- Q8. LA VOIE INDIRECTE VERS WRITER OU BOOTSTRAP -----------------------
# Les conditions de `--recover-pending` etablissent que le migrateur porte
# EXACTEMENT deux appartenances DIRECTES, donnees par nous, et qu'il n'atteint
# pas l'activateur. Elles ne disent rien d'un role INTERMEDIAIRE: le migrateur
# peut etre membre d'un role qui, lui, est membre de writer. Revoquer les deux
# octrois directs ne le ramene alors pas a zero.
#
# CE QUI EST EXIGE N'EST PAS SEULEMENT LE REFUS: c'est que la base ne soit PAS
# MODIFIEE. Une reprise qui revoque, decouvre le residu, puis laisse la base
# sans ses deux octrois aurait detruit ce qu'elle etait censee reprendre — et
# le prochain appel ne saurait plus quoi rendre.
if ! q_amorcer q8; then
  echoue "le decor Q8 n'a pas pu etre pose"
else
migrations_copiees
JOURNAL_Q8="$COPIE/q8.log"
: >"$JOURNAL_Q8"
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$JOURNAL_Q8" 2>&1
) &
PID_Q8=$!
ATTENTE=0
while [[ $ATTENTE -lt 600 ]]; do
  grep -q "0005_" "$JOURNAL_Q8" 2>/dev/null && break
  kill -0 "$PID_Q8" 2>/dev/null || break
  sleep 0.2; ATTENTE=$((ATTENTE + 1))
done
INTERM_Q8=""
if ! grep -q "0005_" "$JOURNAL_Q8" 2>/dev/null || ! kill -0 "$PID_Q8" 2>/dev/null; then
  wait "$PID_Q8" 2>/dev/null
  echoue "Q8. la phase 1 n'a pas ete atteinte a temps; scenario non evalue"
else
  kill -KILL "$PID_Q8" 2>/dev/null
  wait "$PID_Q8" 2>/dev/null
  sleep 1
  # LE ROLE INTERMEDIAIRE, pose par un TIERS (l'administrateur): la reprise ne
  # l'a pas accorde, et n'a donc aucun titre a le defaire.
  INTERM_Q8="${PREFIXE:0:8}_int_${JETON:0:6}"
  adm -v ON_ERROR_STOP=1 -v i="$INTERM_Q8" -v m="$MIG" >/dev/null 2>&1 <<'SQL'
create role :"i" nologin;
grant eurostruct_normative_writer to :"i";
grant :"i" to :"m" with inherit true;
SQL
  DIRECTS_AVANT=$(adm -tA -v m="$MIG" <<'SQL'
select count(*) from pg_auth_members am
  join pg_roles r on r.oid = am.roleid
  join pg_roles mm on mm.oid = am.member
 where mm.rolname = :'m'
   and r.rolname in ('eurostruct_normative_writer','eurostruct_normative_bootstrap');
SQL
  )
  appeler --recover-pending; CODE_Q8=$?
  DIRECTS_APRES=$(adm -tA -v m="$MIG" <<'SQL'
select count(*) from pg_auth_members am
  join pg_roles r on r.oid = am.roleid
  join pg_roles mm on mm.oid = am.member
 where mm.rolname = :'m'
   and r.rolname in ('eurostruct_normative_writer','eurostruct_normative_bootstrap');
SQL
  )
  if [[ "$DIRECTS_AVANT" != "2" ]]; then
    echoue "Q8. le decor ne porte pas les deux octrois directs ($DIRECTS_AVANT);"
    echoue "    le scenario ne dit rien."
  elif [[ $CODE_Q8 -eq 0 ]]; then
    rouge "Q8. la reprise se declare reussie malgre une voie indirecte."
    detail "    « $MIG » atteint writer par « $INTERM_Q8 »."
  elif ! grep -qF "RECOVERY_RESIDUAL_ACCESS" <<<"$SORTIE_CMD"; then
    rouge "Q8. la voie indirecte n'est pas nommee."
    detail "    code $CODE_Q8; $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_CMD" | cut -c1-130)"
  elif [[ "$DIRECTS_APRES" != "2" ]]; then
    rouge "Q8. le refus a laisse la base MODIFIEE."
    detail "    $DIRECTS_AVANT octroi(s) direct(s) avant, $DIRECTS_APRES apres."
    detail "    Un refus ambigu doit laisser intacts les deux octrois initiaux:"
    detail "    sinon le prochain appel ne sait plus quoi rendre."
  else
    echo "      ok: Q8. voie indirecte: refus nomme, les deux octrois intacts"
  fi
fi
[[ -n "$INTERM_Q8" ]] && adm -v n="$INTERM_Q8" >/dev/null 2>&1 <<'SQL'
drop owned by :"n";
drop role if exists :"n";
SQL
decor_deposer
fi

# --- S3 et S4. LE VERROU EST RECONSTATE AVANT CHAQUE MUTATION -------------
# S2 etablit le cas de la phase 1. Ces deux-ci ferment les deux autres moments
# ou une session morte serait la plus couteuse:
#
#   S3 — juste avant l'OCTROI des emprunts: aucun octroi ne doit avoir lieu;
#   S4 — juste avant le REVOKE de reprise: la reprise refuse sans modifier.
#
# LE LEURRE TUE LE BACKEND DU VERROU au lieu de simuler une panne reseau: le
# verrou disparait reellement, et c'est bien `pg_locks` qui doit le dire.
s_verrou_perdu() {
  local nom="$1" mode="$2" avant apres code
  q_amorcer "${nom,,}" || { echoue "le decor $nom n'a pas pu etre pose"; return 1; }
  migrations_copiees
  local leurre="$COPIE/leurre_${nom,,}"
  mkdir -p "$leurre"
  local vrai; vrai="$(command -v psql)"
  # LE DECLENCHEUR DOIT PRECEDER LE RECONSTAT, PAS LA MUTATION.
  #
  # Premiere ecriture: il visait l'instruction mutante elle-meme. Le reconstat
  # du verrou avait alors deja eu lieu, l'octroi passait, et c'est la
  # COMPENSATION qui le reprenait ensuite — S3 se declarait vert « 0 -> 0 » en
  # ayant mesure la compensation, et non la prevention.
  #
  # On tue donc a l'instruction QUI PRECEDE le reconstat:
  #   octroi  -> la lecture de `normative_activation_state()`, passee en « -c »;
  #   reprise -> la requete des constats, un heredoc qui porte « MEMBRE ».
  local motif="normative_activation_state"
  [[ "$mode" == "reprise" ]] && motif="MEMBRE"
  cat >"$leurre/psql" <<LEURREFIN
#!/usr/bin/env bash
# FAUX psql — scenario $nom. Il tue le backend du verrou juste AVANT la
# mutation visee, puis laisse passer l'appel: c'est donc le reconstat du
# verrou, et lui seul, qui doit arreter la commande.
#
# IL SE DECIDE SUR ARGV AVANT DE LIRE L'ENTREE: le co-processus du verrou ne
# porte pas de « -v » et ne doit jamais etre bloque.
DIRECT=1
for a in "\$@"; do
  case "\$a" in -c|--command*|-f|--file*) DIRECT=1; break ;; -v) DIRECT=0 ;; esac
done
# LE MOTIF EST CHERCHE D'ABORD DANS ARGV: un appel en « -c » y porte son SQL et
# ne lit pas l'entree. Sans cela, un declencheur pose sur un « -c » serait
# inatteignable.
if [[ "\$*" == *"$motif"* ]] && [[ ! -f "$COPIE/${nom,,}_tue" ]]; then
  ESC_TUER=1
fi
if (( DIRECT )) && [[ -z "\${ESC_TUER:-}" ]]; then exec "$vrai" "\$@"; fi
if [[ -z "\${ESC_TUER:-}" ]]; then
  CORPS="\$(cat)"
  [[ "\$CORPS" == *"$motif"* ]] && ESC_TUER=1
fi
if [[ -n "\${ESC_TUER:-}" ]] && [[ ! -f "$COPIE/${nom,,}_tue" ]]; then
  # IL TUE AVEC LES IDENTIFIANTS QU'IL A DEJA, ET N'INVENTE AUCUNE CONNEXION
  # ADMINISTRATEUR.
  #
  # DEFAUT MESURE, ET IL A FALLU LA CI POUR LE VOIR. La version precedente
  # ecrivait PGHOST="\${PGHOST:-...}" PGUSER="\${PGUSER:-postgres}" dans un
  # heredoc NON CITE: les deux substitutions etaient donc evaluees A LA
  # GENERATION, dans le shell du harnais, et gravees en dur — sans mot de passe,
  # qu'elles esperaient heriter.
  #
  #   sur socket -> « postgres » en authentification PEER: aucun mot de passe
  #                 requis, le kill passait, S3/S4 verts;
  #   en TCP     -> « postgres » avec le mot de passe du PLAN DE CONTROLE herite
  #                 de la commande: « password authentication failed for user
  #                 "postgres" ». Le backend du verrou n'etait jamais tue, et
  #                 S3/S4 ne mesuraient rien.
  #
  # AUCUN ADMINISTRATEUR N'EST NECESSAIRE: le co-processus du verrou tourne sous
  # le plan de controle, et un role peut terminer SES PROPRES backends. Le
  # leurre est justement invoque sur une connexion du plan — il lui suffit de ne
  # RIEN surcharger. C'est aussi ce qui evite d'ecrire un mot de passe
  # administrateur dans un fichier temporaire.
  #
  # \`-d "\$BASE"\` et non \`-d postgres\`: c'est la base que ce role joint a coup
  # sur, et \`pg_locks\` est global au cluster.
  #
  # LES ACCENTS GRAVES SONT ECHAPPES, ET CE N'EST PAS COSMETIQUE. Ce heredoc
  # n'est PAS cite: un accent grave y ouvre une substitution de commande, a la
  # GENERATION. Ecrits nus, ces trois mots etaient EXECUTES par le shell du
  # harnais — « -d: command not found », trois fois par leurre — et le
  # commentaire arrivait mutile dans le leurre (« # et non : c'est la base »).
  # Le bruit tombait sur la sortie d'erreur du harnais, la ou une VRAIE panne du
  # leurre se serait affichee: indiscernables.
  : >"$COPIE/${nom,,}_tue"
  "$vrai" -X -q -tA -d "$BASE" -c "
      select pg_terminate_backend(pid) from pg_locks
       where locktype='advisory' and granted and objsubid=2
         and classid = (hashtext('eurostruct.deploiement')::bigint & 4294967295)::oid
         and objid   = (hashtext('$BASE')::bigint & 4294967295)::oid" \\
    >"$COPIE/${nom,,}_kill.log" 2>&1
  # LE RESULTAT N'EST PLUS JETE. Le marqueur etait pose AVANT la tentative et
  # son issue ignoree: « le backend a ete tue » ne prouvait que « le leurre
  # s'est declenche ». Une ligne « t » atteste une terminaison REELLE.
  grep -qx 't' "$COPIE/${nom,,}_kill.log" || : >"$COPIE/${nom,,}_rate"
fi
# L'APPEL PASSE ENSUITE NORMALEMENT: c'est le reconstat du verrou, et lui seul,
# qui doit arreter la commande — pas une erreur de cet appel-ci.
if (( DIRECT )); then exec "$vrai" "\$@"; fi
printf '%s\n' "\${CORPS:-\$(cat)}" | "$vrai" "\$@"
LEURREFIN
  chmod +x "$leurre/psql"
  rm -f "$COPIE/${nom,,}_tue" "$COPIE/${nom,,}_rate" "$COPIE/${nom,,}_kill.log"

  if [[ "$mode" == "reprise" ]]; then
    # Amener la base a PENDING avec les deux emprunts, comme apres un SIGKILL.
    local jr="$COPIE/${nom,,}.log"; : >"$jr"
    (
      ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
      ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
      exec bash "$COMMANDE_COPIE" >"$jr" 2>&1
    ) &
    local pid=$!
    local att=0
    while [[ $att -lt 600 ]]; do
      grep -q "0005_" "$jr" 2>/dev/null && break
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.2; att=$((att + 1))
    done
    kill -KILL "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 1
  fi

  avant=$(adm -tA -v m="$MIG" <<'SQL'
select count(*) from pg_auth_members am
  join pg_roles r on r.oid = am.roleid join pg_roles mm on mm.oid = am.member
 where mm.rolname = :'m'
   and r.rolname in ('eurostruct_normative_writer','eurostruct_normative_bootstrap');
SQL
  )
  if [[ "$mode" == "reprise" ]]; then
    PATH="$leurre:$PATH" appeler --recover-pending; code=$?
  else
    PATH="$leurre:$PATH" appeler; code=$?
  fi
  apres=$(adm -tA -v m="$MIG" <<'SQL'
select count(*) from pg_auth_members am
  join pg_roles r on r.oid = am.roleid join pg_roles mm on mm.oid = am.member
 where mm.rolname = :'m'
   and r.rolname in ('eurostruct_normative_writer','eurostruct_normative_bootstrap');
SQL
  )
  # DEUX FAITS DISTINCTS, ET LES CONFONDRE A RENDU S3/S4 CREUX EN TCP: que le
  # leurre se soit DECLENCHE, et que le backend soit REELLEMENT mort. Le second
  # seul autorise a conclure.
  if [[ ! -f "$COPIE/${nom,,}_tue" ]]; then
    echoue "$nom. le leurre ne s'est pas declenche; scenario non evalue"
  elif [[ -f "$COPIE/${nom,,}_rate" ]]; then
    echoue "$nom. le leurre s'est declenche mais n'a termine AUCUN backend;"
    echoue "     le verrou n'a donc pas ete perdu, et rien n'est mesure."
    detail "    $(head -2 "$COPIE/${nom,,}_kill.log" 2>/dev/null | tr '\n' ' ' | cut -c1-160)"
  elif [[ "$apres" != "$avant" ]]; then
    rouge "$nom. la mutation a eu lieu malgre la perte du verrou."
    detail "    $avant octroi(s) direct(s) avant, $apres apres (code $code)"
  elif grep -qF "emprunts accordes" <<<"$SORTIE_CMD"; then
    rouge "$nom. les emprunts ont ete accordes malgre la perte du verrou."
    detail "    Les reprendre ensuite par compensation n'est pas la meme chose"
    detail "    que ne pas les avoir accordes."
  elif [[ $code -ne 8 ]] || ! grep -qF "DEPLOYMENT_LOCK_LOST" <<<"$SORTIE_CMD"; then
    rouge "$nom. la perte du verrou n'est ni detectee ni nommee."
    detail "    code $code (8 attendu)"
    detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_CMD" | cut -c1-140)"
  else
    echo "      ok: $nom. verrou perdu: arret nomme, aucune mutation ($avant -> $apres)"
  fi
  decor_deposer
  return 0
}

s_verrou_perdu S3 octroi
s_verrou_perdu S4 reprise

# --- Q4. apres une finalisation REUSSIE, rien a compenser ------------------
# La moitie positive. Sans elle, « la compensation revoque » serait satisfait
# par une compensation qui revoque TOUJOURS — y compris apres une phase 2 qui
# a deja rendu les emprunts, ou apres avoir refuse pour une raison qui n'a rien
# a voir. Une compensation qui se declenche toujours n'est pas une
# compensation, c'est un effet de bord.
if ! q_amorcer q4; then
  echoue "le decor Q4 n'a pas pu etre pose"
else
migrations_copiees
appeler; CODE_Q4=$?
ETAT_Q4=$(etat_normatif)
CAP_Q4=$(capacites_du_migrateur)
if [[ $CODE_Q4 -eq 0 && -z "$CAP_Q4" ]] \
   && [[ "$ETAT_Q4" == "ACTIVE activations=1 plans=1" ]] \
   && ! grep -qF "DEPLOYMENT_CLEANUP_FAILED" <<<"$SORTIE_CMD"; then
  echo "      ok: Q4. finalisation reussie: $ETAT_Q4, aucune capacite"
else
  rouge "Q4. le parcours nominal ne se termine pas proprement."
  detail "    code $CODE_Q4, etat « $ETAT_Q4 », capacites « ${CAP_Q4:-aucune} »"
  detail "      $(grep -m1 -E '^ECHEC|CLEANUP' <<<"$SORTIE_CMD" | cut -c1-130)"
fi
decor_deposer
fi

# ==========================================================================
# R. LES IDENTIFIANTS SQL
# ==========================================================================
# `MIG_USER` vient de l'URL et est interpole tel quel:
#
#     grant eurostruct_normative_writer to "$MIG_USER" with admin option;
#     pg_has_role('$MIG_USER', a.r, 'SET')
#
# Une double quote dans le nom du role ferme l'identifiant et laisse la suite
# s'executer AVEC LES PRIVILEGES DU PLAN DE CONTROLE — qui porte CREATEROLE.
#
# QUE L'URL VIENNE DE L'EXPLOITANT NE SUPPRIME PAS LE RISQUE: le migrateur est
# precisement l'acteur que le modele cherche a contenir, et son nom est ce que
# l'exploitant recopie d'un fichier de configuration qu'il n'a pas ecrit.
#
# LE PREFIXE DOIT EXISTER, et c'est ce qui donne sa portee a l'injection.
# Premiere ecriture, mesuree: sans role portant le prefixe tronque,
# `grant ... to "prefixe";` echoue, `ON_ERROR_STOP` arrete psql, et
# l'instruction injectee ne s'execute jamais. Le contre-exemple etait vert par
# accident de nommage.
#
# CE HARNAIS N'INTERPOLE PAS LE NOM HOSTILE NON PLUS. Il le pose et le retire
# par `:"n"`, la forme sure — `creer_role` et `detruire_roles_crees` de la
# bibliotheque interpolent, et se seraient injectes eux-memes. Mesure faite en
# ecrivant ce scenario: le role temoin a ete cree par la commande de MESURE
# avant que la commande officielle ne soit appelee.
R_PREFIXE=""; R_HOSTILE=""; R_TEMOIN=""
r_nettoyer() {
  [[ -n "$R_HOSTILE" ]] && adm -v n="$R_HOSTILE" >/dev/null 2>&1 <<'SQL'
drop owned by :"n";
drop role if exists :"n";
SQL
  local x
  for x in "$R_PREFIXE" "$R_TEMOIN"; do
    [[ -n "$x" ]] || continue
    adm -c "drop owned by \"$x\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$x\";" >/dev/null 2>&1
  done
}

if ! decor_poser r1; then
  echoue "le decor R1 n'a pas pu etre pose"
else
suivre_decor
# LE NOM HOSTILE DOIT TENIR DANS 63 OCTETS, ET C'EST LA CORRECTION D'UN DEFAUT
# MESURE (6.3b6e).
#
# La premiere ecriture composait un nom de 67 octets. PostgreSQL TRONQUE les
# identifiants a 63: le role etait cree sous un nom tronque, l'URL portait le
# nom entier, et `verifier_identite` — ajoutee au commit 5 de ce jalon —
# comparait `session_user` (63 octets, rendu par le serveur) au nom attendu
# (67 octets, cote shell). La commande refusait DONC AVANT l'etape 3, seul
# endroit ou le nom du migrateur entre dans du SQL comme IDENTIFIANT.
#
# Le contre-exemple restait vert sans jamais atteindre le site d'injection: la
# matrice de mutation l'a montre en retirant LES DEUX garanties de R1 sans
# rien faire rougir. Il etait rouge en 5bdd3ca, et l'est devenu hollow en
# a347dcb — sans qu'aucune de ces deux executions ne le signale.
#
# Le jeton est donc raccourci, et la longueur VERIFIEE ci-dessous.
# LE PREFIXE EST TRONQUE, ET C'EST NECESSAIRE. `run.sh` appelle ce harnais avec
# « eurostruct_testdr »: le nom hostile repassait alors a 67 octets, et la garde
# ci-dessous refusait le scenario — verte en execution isolee, rouge dans la
# suite. Le budget est de 63 octets pour 17 de charge utile
# (`";create role ` + `;--`), soit 46 pour les deux noms.
R_JETON="${JETON:0:6}"
R_PREFIXE="${PREFIXE:0:8}_i${R_JETON}"
R_TEMOIN="${PREFIXE:0:8}_t${R_JETON}"
R_HOSTILE="$R_PREFIXE\";create role $R_TEMOIN;--"
adm -c "create role \"$R_PREFIXE\" nologin;" >/dev/null 2>&1
adm -v ON_ERROR_STOP=1 -v n="$R_HOSTILE" -v mdp="$MDP" >/dev/null 2>&1 <<'SQL'
create role :"n" login password :'mdp' createrole createdb;
SQL
if [[ ${#R_HOSTILE} -gt 63 ]]; then
  echoue "R1. le nom hostile fait ${#R_HOSTILE} octets: PostgreSQL le tronquerait"
  echoue "    a 63, et la commande refuserait sur l'identite AVANT l'etape 3."
  echoue "    Le scenario ne dirait rien de l'injection. Raccourcissez le prefixe."
elif [[ "$(adm -tAc "select count(*) from pg_roles where rolname = '$R_TEMOIN'")" != "0" ]]; then
  echoue "R1. le temoin existe avant l'essai: le scenario ne dirait rien"
else
  # L'URL porte le nom hostile PERCENT-ENCODE. Le decoupeur de la commande le
  # desencode, et c'est ce nom-la qui arrive dans le SQL.
  R_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$R_HOSTILE")
  SORTIE_R=$(
    ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    ESC_MIGRATOR_URL="postgresql://$R_ENC:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    bash "$COMMANDE_COPIE" 2>&1
  ); CODE_R=$?
  CREE=$(adm -tAc "select count(*) from pg_roles where rolname = '$R_TEMOIN'")
  # LE SITE D'INJECTION DOIT AVOIR ETE ATTEINT. C'est la moitie qui manquait:
  # « le temoin n'existe pas » ne prouve rien si la commande a renonce avant
  # l'etape 3, ou le nom du migrateur entre dans du SQL comme identifiant.
  #
  # ET NON PLUS « la commande a echoue ». Un nom hostile est, une fois cite,
  # UN NOM: le deploiement va jusqu'au bout, et c'est le resultat correct.
  # Exiger un echec revenait a exiger que la commande refuse un role legitime
  # parce que son nom contient des caracteres deplaisants.
  if ! grep -qF "3/10" <<<"$SORTIE_R"; then
    echoue "R1. la commande n'a pas atteint l'etape 3 (code $CODE_R): le site"
    echoue "    d'injection n'a pas ete exerce, le scenario ne dit rien."
    detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_R" | cut -c1-140)"
  elif [[ "$CREE" == "0" ]]; then
    echo "      ok: R1. le nom hostile atteint l'etape 3 et n'y execute rien"
  else
    rouge "R1. un nom de role venu de l'URL est execute comme du SQL."
    detail "    role temoin cree: $CREE (1 = injection reussie), code $CODE_R"
    detail "    nom employe: ${R_HOSTILE:0:70}"
    detail "    L'instruction s'execute avec les privileges du PLAN DE CONTROLE,"
    detail "    qui porte CREATEROLE."
  fi
fi
r_nettoyer
decor_deposer
fi

# --- R2. DEUX NOMS QUI N'EN FONT QU'UN -----------------------------------
# CE SCENARIO EXISTE PARCE QUE R1 L'EXERCAIT PAR ACCIDENT (6.3b6e).
#
# La borne de 63 octets de `borner_identifiant` etait, sans que ce soit ecrit
# nulle part, ce qui faisait passer R1: son nom hostile depassait la borne. En
# raccourcissant ce nom, R1 mesure enfin l'interpolation — et la borne se
# retrouvait sans contre-exemple. Elle en a un ici, et il porte sur ce que la
# borne protege vraiment.
#
# LE DANGER N'EST PAS LA LONGUEUR. C'est que PostgreSQL TRONQUE a 63 octets:
# deux noms qui ne different qu'apres le 63e octet designent LE MEME role. Le
# controle « plan et migrateur sont distincts » compare deux CHAINES SHELL,
# qui, elles, different. Sans la borne, la commande deploierait donc avec un
# seul role jouant les deux acteurs — exactement ce que le modele de menace
# interdit — et le compte rendu afficherait deux noms.
R2_BASE=""
if ! decor_poser r2; then
  echoue "le decor R2 n'a pas pu etre pose"
else
suivre_decor
# 63 octets EXACTEMENT, puis deux suffixes qui tombent au-dela.
R2_BASE="${PREFIXE}_r2_${JETON}"
while [[ ${#R2_BASE} -lt 63 ]]; do R2_BASE="${R2_BASE}z"; done
R2_BASE="${R2_BASE:0:63}"
R2_PLAN="${R2_BASE}AAA"
R2_MIG="${R2_BASE}BBB"
adm -v ON_ERROR_STOP=1 -v n="$R2_BASE" -v mdp="$MDP" >/dev/null 2>&1 <<'SQL'
create role :"n" login password :'mdp' createrole createdb;
SQL
R2_MEME=$(adm -tA -v a="$R2_PLAN" -v b="$R2_MIG" <<'SQL'
select (:'a'::name = :'b'::name)::text;
SQL
)
if [[ "$R2_MEME" != "true" ]]; then
  echoue "R2. les deux noms ne se confondent pas cote serveur ($R2_MEME);"
  echoue "    le scenario ne dirait rien de la troncature."
else
  SORTIE_R2=$(
    ESC_PLAN_URL="postgresql://$R2_PLAN:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    ESC_MIGRATOR_URL="postgresql://$R2_MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
    bash "$COMMANDE_COPIE" 2>&1
  ); CODE_R2=$?
  if [[ $CODE_R2 -ne 0 ]] \
     && grep -qF "DEPLOYMENT_IDENTIFIER_REJECTED" <<<"$SORTIE_R2" \
     && ! grep -qF "1/10" <<<"$SORTIE_R2"; then
    echo "      ok: R2. deux noms confondus par la troncature sont refuses"
  else
    rouge "R2. deux noms qui designent le MEME role passent pour deux acteurs."
    detail "    code $CODE_R2; « ${R2_PLAN:0:20}...AAA » et « ...BBB » valent"
    detail "    tous deux « ${R2_BASE:0:24}... » une fois tronques a 63 octets."
    detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' <<<"$SORTIE_R2" | cut -c1-140)"
    if grep -qF "1/10" <<<"$SORTIE_R2"; then
      detail "    LA PHASE 0 A DEMARRE: le refus, s'il a eu lieu, est venu trop tard."
    fi
  fi
fi
[[ -n "$R2_BASE" ]] && adm -v n="$R2_BASE" >/dev/null 2>&1 <<'SQL'
drop owned by :"n";
drop role if exists :"n";
SQL
decor_deposer
fi

# --- Q7. LA COMPENSATION NE DOIT PAS SE DECLARER REUSSIE SANS PREUVE ------
# `sortie_compensee` faisait:
#
#     reste=$(revoquer_les_emprunts)
#     if [[ -n "$reste" ]]; then ... echec ... else "aucune capacite" ; fi
#
# Deux fautes qui se composent: le statut du `REVOKE` etait ignore, et la
# verification qui suit lisait `pg_has_role(...)` avec `2>/dev/null`. Si la
# connexion du plan tombe, LES DEUX ne produisent rien — et la chaine vide
# passait pour « aucune capacite residuelle ». La commande annoncait donc une
# base propre au moment precis ou elle ne l'est pas.
#
# LE LEURRE FAIT TOMBER LA CONNEXION JUSTE AVANT LE `REVOKE`, et l'y laisse:
# c'est la panne reseau au pire moment. Un observateur ADMINISTRATEUR, qui ne
# passe pas par le leurre, constate ensuite que les octrois subsistent.
if ! q_amorcer q7; then
  echoue "le decor Q7 n'a pas pu etre pose"
else
migrations_copiees 0006_ndp_import.sql        # force la compensation
LEURRE_Q7="$COPIE/leurre_q7"
mkdir -p "$LEURRE_Q7"
VRAI_PSQL_Q7="$(command -v psql)"
cat >"$LEURRE_Q7/psql" <<LEURREFIN
#!/usr/bin/env bash
# FAUX psql — scenario Q7. Coupe a partir du REVOKE de compensation, inclus.
#
# IL NE LIT L'ENTREE QUE POUR LES APPELS QUI PORTENT « -v ». Le REVOKE de
# compensation et la verification qui suit en portent un (« -v m= »); le
# CO-PROCESSUS DU VERROU, lui, n'en a pas — et son entree reste ouverte toute
# la duree de la commande. Un « cat » inconditionnel s'y bloquait: mesure, la
# commande mourait sur « aucune reponse du verrou en 30 s », bien avant
# d'accorder quoi que ce soit, et le scenario n'exercait rien.
DIRECT=1
for a in "\$@"; do
  case "\$a" in -c|--command*|-f|--file*) DIRECT=1; break ;; -v) DIRECT=0 ;; esac
done
if (( DIRECT )); then exec "$VRAI_PSQL_Q7" "\$@"; fi
CORPS="\$(cat)"
if [[ "\$CORPS" == *"revoke eurostruct_normative_writer"* ]]; then
  : >"$COPIE/q7_coupe"
fi
if [[ -f "$COPIE/q7_coupe" ]]; then
  echo "psql: error: connexion perdue (leurre Q7)" >&2
  exit 2
fi
printf '%s\n' "\$CORPS" | "$VRAI_PSQL_Q7" "\$@"
LEURREFIN
chmod +x "$LEURRE_Q7/psql"
rm -f "$COPIE/q7_coupe"
PATH="$LEURRE_Q7:$PATH" appeler; CODE_Q7=$?
# L'OBSERVATEUR EXTERNE. Il se connecte par le socket administrateur, sans
# passer par le leurre: c'est lui qui dit la verite sur l'etat des octrois.
CAP_Q7=$(adm -tA -v m="$MIG" <<'SQL'
select coalesce(string_agg(a.r, ' '), '') from unnest(array[
  'eurostruct_normative_writer','eurostruct_normative_bootstrap']) a(r)
 where pg_has_role(:'m', a.r, 'SET') or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
)
if [[ -z "$CAP_Q7" ]]; then
  echoue "Q7. le leurre n'a pas empeche la revocation: les octrois ont ete"
  echoue "    repris malgre la coupure, le scenario ne dit rien."
elif grep -qF "aucune capacite residuelle" <<<"$SORTIE_CMD"; then
  rouge "Q7. la commande annonce une base propre alors qu'elle ne l'est pas."
  detail "    « $MIG » detient encore: $CAP_Q7"
  detail "    code $CODE_Q7"
  detail "    Le REVOKE et la verification ont TOUS DEUX echoue sur la meme"
  detail "    connexion perdue; la chaine vide a ete lue comme une absence."
elif [[ $CODE_Q7 -ne 5 && $CODE_Q7 -ne 7 ]]; then
  rouge "Q7. le nettoyage non verifie ne porte pas de code de sortie dedie."
  detail "    code $CODE_Q7 (5 = repris impossible, 7 = non verifiable)"
  detail "    « $MIG » detient encore: $CAP_Q7"
elif ! grep -qE "DEPLOYMENT_CLEANUP_(FAILED|UNVERIFIED)" <<<"$SORTIE_CMD"; then
  rouge "Q7. aucun jeton ne nomme l'etat du nettoyage."
  detail "    code $CODE_Q7; « $MIG » detient encore: $CAP_Q7"
else
  echo "      ok: Q7. nettoyage non verifiable: refus nomme, code $CODE_Q7"
fi
rm -f "$COPIE/q7_coupe"
decor_deposer
fi

# ==========================================================================
# S. LA CONCURRENCE
# ==========================================================================
# Le verrou consultatif protege la FINALISATION, et elle seule. La phase 0, les
# octrois, les migrations et la lecture du manifeste ne sont pas serialises:
# deux commandes officielles lancees ensemble sur la meme base intercalent
# leurs etapes et appliquent deux fois des migrations qui ne sont pas
# idempotentes.
if ! q_amorcer s1; then
  echoue "le decor S1 n'a pas pu etre pose"
else
migrations_copiees
SA="$COPIE/s_a.log"; SB="$COPIE/s_b.log"
: >"$SA"; : >"$SB"
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$SA" 2>&1
) & PID_A=$!
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$SB" 2>&1
) & PID_B=$!
wait "$PID_A"; CODE_A=$?
wait "$PID_B"; CODE_B=$?
CAP_S=$(capacites_du_migrateur)
ETAT_S=$(etat_normatif)
REFUSES=0
grep -qF "DEPLOYMENT_ALREADY_RUNNING" "$SA" && REFUSES=$((REFUSES + 1))
grep -qF "DEPLOYMENT_ALREADY_RUNNING" "$SB" && REFUSES=$((REFUSES + 1))
ABOUTIS=0
[[ $CODE_A -eq 0 ]] && ABOUTIS=$((ABOUTIS + 1))
[[ $CODE_B -eq 0 ]] && ABOUTIS=$((ABOUTIS + 1))
if [[ $ABOUTIS -eq 1 && $REFUSES -eq 1 && -z "$CAP_S" ]] \
   && [[ "$ETAT_S" == "ACTIVE activations=1 plans=1" ]]; then
  echo "      ok: S1. une seule commande poursuit, l'autre est refusee"
else
  rouge "S1. rien ne serialise deux commandes concurrentes."
  detail "    codes: $CODE_A / $CODE_B — aboutissent: $ABOUTIS, refus nommes: $REFUSES"
  detail "    etat: $ETAT_S, capacites residuelles: « ${CAP_S:-aucune} »"
  detail "    $(grep -m1 -E '^ECHEC' "$SA" | cut -c1-120)"
  detail "    $(grep -m1 -E '^ECHEC' "$SB" | cut -c1-120)"
  detail "    CE QUI EST CONSTATE ICI est l'absence d'un REFUS NOMME: la"
  detail "    perdante echoue sur ce qu'elle rencontre, pas sur le fait qu'une"
  detail "    autre execution est en cours. L'entrelacement lui-meme depend de"
  detail "    l'ordonnancement et ne se constate pas a chaque passage — raison"
  detail "    de plus pour exiger un verrou plutot que de compter dessus."
  detail "    Le verrou existant ne couvre que la finalisation: la phase 0, les"
  detail "    octrois, les migrations et le manifeste restent hors de lui."
fi
decor_deposer
fi

# --- S2. LA SESSION DU VERROU MEURT PENDANT LA PHASE 1 --------------------
# `VERROU_TENU=1` est une variable de shell. Elle dit qu'on a REUSSI a prendre
# le verrou, jamais qu'on le detient ENCORE. Une session peut etre terminee par
# `pg_terminate_backend`, coupee par un pooler, ou perdue avec le serveur — et
# le verrou consultatif meurt avec elle, sans que rien ne le signale au shell.
#
# UNE AUTRE COMMANDE PEUT ALORS DEMARRER. Celle qui poursuit en se fiant a sa
# variable applique des migrations, puis finalise, pendant qu'une seconde fait
# de meme: exactement ce que le verrou existait pour empecher.
#
# ON TUE LE BACKEND QUI PORTE LE VERROU, et lui seul: les connexions du plan et
# du migrateur restent vivantes. La compensation doit donc pouvoir s'executer
# ET etre constatee — c'est ce qui distingue ce scenario de Q7.
if ! q_amorcer s2; then
  echoue "le decor S2 n'a pas pu etre pose"
else
migrations_copiees
JOURNAL_S2="$COPIE/s2.log"
: >"$JOURNAL_S2"
(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  exec bash "$COMMANDE_COPIE" >"$JOURNAL_S2" 2>&1
) &
PID_S2=$!
ATTENTE=0
while [[ $ATTENTE -lt 600 ]]; do
  grep -q "0003_" "$JOURNAL_S2" 2>/dev/null && break
  kill -0 "$PID_S2" 2>/dev/null || break
  sleep 0.2
  ATTENTE=$((ATTENTE + 1))
done
# LA CLE EST CELLE DE LA COMMANDE, recalculee ici depuis le NOM de la base:
# cette connexion-ci est sur `postgres`, pas sur la base visee.
TUES_S2=$(adm -tA -v b="$BASE" <<'SQL'
select count(*) from (
  select pg_terminate_backend(pid) from pg_locks
   where locktype = 'advisory' and granted and objsubid = 2
     and classid = (hashtext('eurostruct.deploiement')::bigint & 4294967295)::oid
     and objid   = (hashtext(:'b')::bigint & 4294967295)::oid
) t;
SQL
)
wait "$PID_S2" 2>/dev/null; CODE_S2=$?
ETAT_S2=$(admb -tAc "select normative_activation_state()" 2>&1)
CAP_S2=$(adm -tA -v m="$MIG" <<'SQL'
select coalesce(string_agg(a.r, ' '), '') from unnest(array[
  'eurostruct_normative_writer','eurostruct_normative_bootstrap']) a(r)
 where pg_has_role(:'m', a.r, 'SET') or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
)
if [[ "$TUES_S2" != "1" ]]; then
  echoue "S2. la session du verrou n'a pas ete trouvee ($TUES_S2 tuee(s));"
  echoue "    le scenario ne dit rien de sa disparition."
elif [[ "$ETAT_S2" == "ACTIVE" ]]; then
  rouge "S2. la commande a finalise apres avoir perdu son verrou."
  detail "    code $CODE_S2 — elle s'est fiee a VERROU_TENU=1."
elif [[ $CODE_S2 -ne 8 ]] || ! grep -qF "DEPLOYMENT_LOCK_LOST" <<<"$(cat "$JOURNAL_S2")"; then
  rouge "S2. la perte du verrou n'est ni detectee ni nommee."
  detail "    code $CODE_S2 (8 attendu), etat « $ETAT_S2 »"
  detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_)' "$JOURNAL_S2" | cut -c1-140)"
elif [[ -n "$CAP_S2" ]]; then
  rouge "S2. le verrou perdu est detecte, mais les emprunts restent."
  detail "    « $MIG » detient encore: $CAP_S2"
else
  echo "      ok: S2. verrou perdu: arret nomme avant l'etape suivante, emprunts repris"
fi
decor_deposer
fi

# ==========================================================================
# T. LA REPRISE D'UNE PHASE 1 INTERROMPUE
# ==========================================================================
# La commande annonce que la relancer est sur. Ce n'est etabli que pour une
# base DEJA ACTIVE — cas ou elle saute les etapes 3 a 7. Une phase 1
# interrompue au milieu n'est pas couverte, et la boucle recommence toujours a
# `0001`: or ces migrations ne sont pas idempotentes.
#
# `t_reprise <nom> <migration-fautive>` — applique jusqu'au point choisi,
# echoue, puis RELANCE avec un jeu de migrations sain. Ce que la relance doit
# faire: reprendre ou. Ce qu'elle fait: tout recommencer.
t_reprise() {
  local nom="$1" fautive="$2" code sortie
  q_amorcer "${nom,,}" || { echoue "le decor $nom n'a pas pu etre pose"; return 1; }
  migrations_copiees "$fautive"
  appeler >/dev/null 2>&1
  # LE JEU SAIN, comme apres un correctif ou une reprise de reseau.
  migrations_copiees
  appeler; code=$?
  sortie="$SORTIE_CMD"
  if [[ $code -eq 0 && "$(admb -tAc 'select normative_activation_state()' 2>&1)" == "ACTIVE" ]]; then
    echo "      ok: $nom. la relance apres interruption reprend et aboutit"
  else
    rouge "$nom. la relance apres interruption ne reprend pas (code $code)."
    detail "    $(grep -m1 -E 'ERROR|already exists|ECHEC' <<<"$sortie" | cut -c1-140)"
    detail "    La boucle recommence a 0001, et ces migrations ne sont pas"
    detail "    idempotentes: rien ne sait ce qui a deja ete applique."
  fi
  decor_deposer
  return 0
}

t_reprise "T1" 0002_rls.sql
t_reprise "T2" 0006_ndp_import.sql
t_reprise "T3" 0010_normative_confirmation.sql

# --- T6. coupure APRES le commit serveur, avant la reponse au client -------
# LE CAS QUE L'EXPLOITANT NE PEUT PAS DISTINGUER. La migration a ete VALIDEE —
# ligne de registre comprise — mais le client n'a pas recu le resultat: pour
# lui, elle a echoue. La relance doit la SAUTER, pas la rejouer.
#
# C'est exactement ce que le registre existe pour trancher, et c'est le seul
# scenario ou « appliquee » et « sautee » ne se confondent pas.
if ! q_amorcer t6; then
  echoue "le decor T6 n'a pas pu etre pose"
else
migrations_copiees 0006_ndp_import.sql apres_commit
appeler >/dev/null 2>&1
INSCRITE=$(admb -tAc "select count(*) from normative_migration_ledger
                       where migration_id = '0006_ndp_import.sql'" 2>&1)
# LE JEU N'EST PAS REPOSE, ET C'EST TOUT LE SUJET. Reposer le jeu sain
# changerait le contenu de 0006 entre les deux passages, et la relance rendrait
# MIGRATION_CHECKSUM_MISMATCH — le refus de T4, pas la reprise de T6. Ici le
# fichier est IDENTIQUE: seul son etat dans le registre a change.
appeler; CODE_T6=$?
ETAT_T6=$(admb -tAc "select normative_activation_state()" 2>&1)
if [[ "$INSCRITE" != "1" ]]; then
  echoue "T6. la migration n'a pas ete inscrite malgre son commit ($INSCRITE);"
  echoue "    le scenario ne dirait rien de la coupure qu'il vise"
elif [[ $CODE_T6 -eq 0 && "$ETAT_T6" == "ACTIVE" ]]; then
  echo "      ok: T6. une migration validee mais non confirmee au client est sautee"
else
  rouge "T6. la relance rejoue une migration deja validee (code $CODE_T6)."
  detail "    $(grep -m1 -E 'ERROR|already exists|ECHEC' <<<"$SORTIE_CMD" | cut -c1-140)"
fi
decor_deposer
fi

# --- T4. une migration MODIFIEE apres application -------------------------
# Le contrat demande `MIGRATION_CHECKSUM_MISMATCH`. Aujourd'hui rien n'inscrit
# ce qui a ete applique: une migration reecrite apres coup n'est ni detectee ni
# refusee — elle est simplement rejouee.
if ! q_amorcer t4; then
  echoue "le decor T4 n'a pas pu etre pose"
else
migrations_copiees 0006_ndp_import.sql
appeler >/dev/null 2>&1
# 0002 A DEJA ETE APPLIQUEE. On la modifie — c'est le geste qu'un correctif
# applique a chaud produit — puis on relance.
migrations_copiees
printf '\n-- FICTIF: modification posterieure a l application\ncomment on schema public is %s;\n' \
  "'FICTIF-modifiee'" >>"$COPIE/db/migrations/0002_rls.sql"
appeler; CODE_T4=$?
if grep -qF "MIGRATION_CHECKSUM_MISMATCH" <<<"$SORTIE_CMD"; then
  echo "      ok: T4. une migration modifiee apres application est refusee"
else
  rouge "T4. une migration modifiee apres application n'est pas detectee."
  detail "    code $CODE_T4; obtenu: $(grep -m1 -E 'ERROR|ECHEC' <<<"$SORTIE_CMD" | cut -c1-130)"
  detail "    Rien n'inscrit ce qui a ete applique, ni avec quelle empreinte."
fi
decor_deposer
fi

# --- T7. LE PORTILLON NE DOIT PAS PRENDRE UNE PANNE POUR UNE ABSENCE ------
# `esc_migration_etat` demandait `to_regclass('public.normative_migration_ledger')
# is null` puis testait `!= "f"`. Une sortie VIDE — connexion tombee, droit
# manquant, proxy qui coupe — n'est pas « f », et valait donc ABSENTE: le
# registre etait repute inexistant, et la migration REJOUEE sur une base qui la
# portait deja. Le commentaire du second aller-retour affirmait pourtant
# l'inverse: « une reponse illisible n'est pas une absence ».
#
# LE CONTRE-EXEMPLE FAIT ECHOUER LA SEULE PREMIERE INTERROGATION. Un faux
# `psql`, place devant le vrai dans le PATH, refuse le premier `to_regclass` et
# laisse passer tout le reste — c'est le comportement d'un proxy qui recycle une
# connexion, pas d'une base en panne. La base porte deja les dix migrations.
#
# CE QUI EST OBSERVE N'EST PAS « la commande a echoue »: elle echoue dans les
# deux mondes. C'est qu'AUCUN SQL DE MIGRATION n'a ete execute. Le faux `psql`
# journalise chacun de ses appels; un `-f .../0001_init.sql` dans ce journal
# prouve que le portillon a conclu ABSENTE et a rejoue.
if ! q_amorcer t7; then
  echoue "le decor T7 n'a pas pu etre pose"
else
# LA BASE DOIT ETRE « PENDING » AVEC UN REGISTRE PARTIEL, et c'est le coeur du
# scenario. Premiere ecriture: la base etait menee jusqu'a ACTIVE. La commande
# saute alors les etapes 3 a 7 — elle n'interroge JAMAIS le portillon —, le
# leurre ne se declenchait pas, et le contre-exemple ne mesurait rien.
migrations_copiees 0006_ndp_import.sql
appeler >/dev/null 2>&1                    # echoue en 0006: 0001-0005 inscrites
ETAT_T7A=$(admb -tAc "select normative_activation_state()" 2>&1)
INSCRITES_T7=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
migrations_copiees                          # le jeu sain, comme apres correctif
LEURRE="$COPIE/leurre"
mkdir -p "$LEURRE"
JOURNAL_T7="$COPIE/psql_appels.log"
VRAI_PSQL="$(command -v psql)"
cat >"$LEURRE/psql" <<LEURREFIN
#!/usr/bin/env bash
# FAUX psql — db/test/deploy_recovery.sh, scenario T7.
# Refuse la PREMIERE interrogation du registre, puis se comporte normalement.
#
# IL SE DECIDE SUR ARGV, ET NE LIT L'ENTREE QU'ENSUITE. Deux ecritures
# precedentes lisaient l'entree d'abord, et le contre-exemple se declarait vert
# sans rien avoir exerce:
#
#   * un \`cat\` inconditionnel bloquait les appels en \`-c\`/\`-f\`, qui ne
#     consomment pas d'entree;
#   * meme filtre, il bloquait le CO-PROCESSUS DU VERROU, dont l'entree reste
#     ouverte pour toute la duree de la commande — « aucune reponse du verrou de
#     deploiement en 30 s », mesure faite.
#
# La premiere interrogation du registre est le SEUL appel qui porte \`-tA\` sans
# \`-v\`: le portillon passe \`-v id=\` et \`-v sum=\`, et le verrou \`-At\`.
printf '%s\n' "ARGV: \$*" >>"$JOURNAL_T7"
DIRECT=0
for a in "\$@"; do
  case "\$a" in
    -c|--command*|-f|--file*|-v) DIRECT=1 ;;
  esac
done
SONDE=0
for a in "\$@"; do [[ "\$a" == "-tA" ]] && SONDE=1; done
if (( DIRECT )) || (( ! SONDE )); then
  exec "$VRAI_PSQL" "\$@"
fi
CORPS="\$(cat)"
if [[ "\$CORPS" == *to_regclass*normative_migration_ledger* ]] \\
   && [[ ! -f "$COPIE/leurre_deja" ]]; then
  : >"$COPIE/leurre_deja"
  echo "psql: error: connexion perdue (leurre T7)" >&2
  exit 2
fi
printf '%s\n' "\$CORPS" | "$VRAI_PSQL" "\$@"
LEURREFIN
chmod +x "$LEURRE/psql"
: >"$JOURNAL_T7"
rm -f "$COPIE/leurre_deja"
PATH="$LEURRE:$PATH" appeler; CODE_T7=$?
REJOUEE_T7="$(grep -oE -- '-f [^ ]*migrations/[0-9]+[^ ]*' "$JOURNAL_T7" 2>/dev/null \
              | head -3 | tr '\n' ' ')"
DECLENCHE_T7=$([[ -f "$COPIE/leurre_deja" ]] && echo oui || echo non)
APRES_T7=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
if [[ "$ETAT_T7A" != "PENDING" || "$INSCRITES_T7" != "5" ]]; then
  echoue "T7. le decor n'est pas dans l'etat attendu (etat « $ETAT_T7A »,"
  echoue "    $INSCRITES_T7 migration(s) inscrite(s) au lieu de 5)"
elif [[ "$DECLENCHE_T7" != "oui" ]]; then
  echoue "T7. le leurre ne s'est pas declenche: le portillon n'a pas ete"
  echoue "    interroge, et le scenario ne dit rien."
elif [[ -z "$REJOUEE_T7" && $CODE_T7 -ne 0 && "$APRES_T7" == "5" ]]; then
  echo "      ok: T7. une interrogation en echec ne vaut pas « registre absent »"
else
  rouge "T7. une panne du portillon est prise pour une absence de registre."
  detail "    code $CODE_T7; SQL de migration execute: « ${REJOUEE_T7:-aucun} »"
  detail "    registre: $INSCRITES_T7 ligne(s) avant, $APRES_T7 apres"
  detail "    La base portait deja cinq migrations. Une reponse vide au premier"
  detail "    « to_regclass » ne doit jamais valoir ABSENTE: elle fait rejouer"
  detail "    une migration deja appliquee."
fi
rm -f "$COPIE/leurre_deja"
decor_deposer
fi

# --- T8 a T11. L'INTEGRITE DE L'HISTOIRE, PAS CELLE D'UN FICHIER ----------
# L'empreinte compare un fichier ENCORE PRESENT a ce qui est inscrit. Elle ne
# voit donc pas:
#
#   * une migration appliquee puis SUPPRIMEE — le runner ne la demande plus;
#   * un RENOMMAGE — pour le registre, c'est une disparition;
#   * une migration INSEREE AVANT la derniere appliquee — elle s'appliquera
#     apres des migrations qui la suivent, sur un schema qu'elle n'attend pas.
#
# Et elle ne doit PAS refuser le geste normal: ajouter une migration en
# SUFFIXE. Les quatre cas sont exerces, le dernier etant le cas positif — sans
# lui, un controle qui refuserait tout passerait pour correct.
#
# LA BASE EST LAISSEE « PENDING » AVEC CINQ MIGRATIONS INSCRITES. Sur une base
# ACTIVE, la commande saute les etapes 3 a 7: le cas positif ne prouverait rien,
# puisque aucune migration ne serait appliquee.
t_historique() {
  local nom="$1" geste="$2" code
  local M5="0005_validation_workflow.sql"
  q_amorcer "${nom,,}" || { echoue "le decor $nom n'a pas pu etre pose"; return 1; }
  migrations_copiees 0006_ndp_import.sql
  appeler >/dev/null 2>&1
  local etat inscrites
  etat=$(admb -tAc "select normative_activation_state()" 2>&1)
  inscrites=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
  if [[ "$etat" != "PENDING" || "$inscrites" != "5" ]]; then
    echoue "$nom. le decor n'est pas dans l'etat attendu (« $etat », $inscrites"
    echoue "    migration(s) inscrite(s) au lieu de 5)"
    decor_deposer; return 1
  fi

  migrations_copiees
  case "$geste" in
    supprime) rm -f "$COPIE/db/migrations/$M5" ;;
    renomme)  mv "$COPIE/db/migrations/$M5" \
                 "$COPIE/db/migrations/0005_renommee_apres_coup.sql" ;;
    # Trie entre `0004_ndp_versioning.sql` et `0005_...`: elle s'intercale donc
    # DANS le prefixe deja applique.
    insere)   printf 'begin;\nselect 1;\ncommit;\n' \
                >"$COPIE/db/migrations/0004_zz_insertion.sql" ;;
    # LE NUMERO EST 9999, ET CE N'EST PAS COSMETIQUE. Le fichier s'appelait
    # « 0011_... » et TRIAIT donc AVANT `0011_authority_hardening.sql`: ce
    # n'etait plus un suffixe mais une INSERTION dans le prefixe deja
    # applique, exactement le geste que T10 verifie etre refuse. Le scenario
    # mesurait donc l'inverse de ce qu'il annonce des que 0011 a existe.
    suffixe)  cat >"$COPIE/db/migrations/9999_ajout_legitime.sql" <<'SQL'
-- FICTIF — ajout EN SUFFIXE, le geste normal. Il doit etre accepte.
begin;
comment on schema public is 'ajout legitime en suffixe (harnais)';
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');
commit;
SQL
              ;;
  esac

  appeler; code=$?
  local apres etat_fin
  apres=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
  etat_fin=$(admb -tAc "select normative_activation_state()" 2>&1)

  if [[ "$geste" == "suffixe" ]]; then
    if [[ $code -eq 0 && "$etat_fin" == "ACTIVE" \
          && "$apres" == "$((MIGRATIONS_ATTENDUES + 1))" ]]; then
      echo "      ok: $nom. une migration ajoutee en suffixe est appliquee"
    else
      rouge "$nom. un ajout LEGITIME en suffixe est refuse."
      detail "    code $code, etat « $etat_fin », $apres ligne(s) au registre"
      detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_|MIGRATION_)' <<<"$SORTIE_CMD" | cut -c1-140)"
      detail "    Un controle qui refuse aussi le geste normal n'est pas un"
      detail "    controle: c'est un blocage."
    fi
  elif [[ $code -ne 0 ]] \
       && grep -qF "MIGRATION_HISTORY_DIVERGENCE" <<<"$SORTIE_CMD" \
       && [[ "$apres" == "5" ]]; then
    echo "      ok: $nom. l'ecart d'historique est refuse avant toute mutation"
  else
    rouge "$nom. un historique divergent ($geste) n'est pas detecte."
    detail "    code $code, $apres ligne(s) au registre (5 attendues)"
    detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_|MIGRATION_)' <<<"$SORTIE_CMD" | cut -c1-140)"
    detail "    L'empreinte ne protege qu'un fichier PRESENT: une migration"
    detail "    appliquee puis supprimee, renommee, ou doublee par une insertion"
    detail "    retroactive lui echappe entierement."
  fi
  decor_deposer
  return 0
}

# --- T17. LE DIAGNOSTIC DU PORTILLON DOIT REVENIR AU RAPPORT --------------
# `esc_appliquer_migration` appelait:
#
#     etat="$(esc_migration_etat "$fichier" "$@")"
#
# Une substitution de commande s'execute dans un SOUS-SHELL. `esc_migration_etat`
# y pose bien `ESC_MIGRATION_DIAG`, mais l'affectation meurt avec le sous-shell:
# l'appelant lit une variable restee vide, et le rapport affiche « <aucun> » a
# l'endroit meme ou l'exploitant a besoin de la cause.
#
# LE LEURRE NE COUPE QUE LA SECONDE INTERROGATION, et c'est ce qui distingue ce
# scenario de T7. La premiere est celle de `esc_verifier_historique`, qui est
# appelee DIRECTEMENT et propage donc son diagnostic sans probleme; la seconde
# est celle du portillon, dans le sous-shell. Couper la premiere ne dirait rien
# du defaut vise.
if ! q_amorcer t17; then
  echoue "le decor T17 n'a pas pu etre pose"
else
migrations_copiees 0006_ndp_import.sql
appeler >/dev/null 2>&1                       # PENDING, 0001-0005 inscrites
ETAT_T17=$(admb -tAc "select normative_activation_state()" 2>&1)
migrations_copiees
LEURRE_T17="$COPIE/leurre_t17"
mkdir -p "$LEURRE_T17"
JOURNAL_T17="$COPIE/psql_t17.log"
VRAI_PSQL_T17="$(command -v psql)"
COMPTEUR_T17="$COPIE/t17_compteur"
: >"$COMPTEUR_T17"
cat >"$LEURRE_T17/psql" <<LEURREFIN
#!/usr/bin/env bash
# FAUX psql — scenario T17. Il se decide sur ARGV avant de lire l'entree: le
# co-processus du verrou ne porte pas de « -tA » et ne doit jamais etre bloque.
printf '%s\n' "ARGV: \$*" >>"$JOURNAL_T17"
DIRECT=0
for a in "\$@"; do
  case "\$a" in -c|--command*|-f|--file*|-v) DIRECT=1 ;; esac
done
SONDE=0
for a in "\$@"; do [[ "\$a" == "-tA" ]] && SONDE=1; done
if (( DIRECT )) || (( ! SONDE )); then exec "$VRAI_PSQL_T17" "\$@"; fi
CORPS="\$(cat)"
if [[ "\$CORPS" == *to_regclass*normative_migration_ledger* ]]; then
  echo x >>"$COMPTEUR_T17"
  if [[ \$(wc -l <"$COMPTEUR_T17") -ge 2 ]]; then
    echo "FICTIF_T17_DIAGNOSTIC_RESEAU" >&2
    exit 2
  fi
fi
printf '%s\n' "\$CORPS" | "$VRAI_PSQL_T17" "\$@"
LEURREFIN
chmod +x "$LEURRE_T17/psql"
: >"$JOURNAL_T17"
PATH="$LEURRE_T17:$PATH" appeler; CODE_T17=$?
REJOUEE_T17="$(grep -oE -- '-f [^ ]*migrations/[0-9]+[^ ]*' "$JOURNAL_T17" 2>/dev/null | head -1)"
if [[ "$ETAT_T17" != "PENDING" ]]; then
  echoue "T17. le decor n'est pas PENDING (« $ETAT_T17 »); scenario non evalue"
elif [[ $(wc -l <"$COMPTEUR_T17") -lt 2 ]]; then
  echoue "T17. le portillon n'a pas ete interroge une seconde fois; le"
  echoue "     scenario ne dit rien du sous-shell."
elif [[ -n "$REJOUEE_T17" ]]; then
  rouge "T17. une migration a ete rejouee malgre le refus: $REJOUEE_T17"
elif ! grep -qF "FICTIF_T17_DIAGNOSTIC_RESEAU" <<<"$SORTIE_CMD"; then
  rouge "T17. le diagnostic reel du portillon ne revient pas au rapport."
  detail "    code $CODE_T17; « FICTIF_T17_DIAGNOSTIC_RESEAU » absent de la sortie"
  detail "    $(grep -m1 -F "aucun" <<<"$SORTIE_CMD" | cut -c1-120)"
  detail "    L'etat est bien INDETERMINE, mais la cause est perdue: elle a ete"
  detail "    ecrite dans le SOUS-SHELL d'une substitution de commande."
elif grep -qF "<aucun>" <<<"$SORTIE_CMD"; then
  rouge "T17. le rapport porte « <aucun> » alors qu'un diagnostic existait."
else
  echo "      ok: T17. le diagnostic reel du portillon revient au rapport"
fi
decor_deposer
fi

# --- T13 a T16. UNE BASE ACTIVE EST AUSSI RAPPROCHEE DU DEPOT -------------
# T8 a T12 laissent la base PENDING, parce qu'une base ACTIVE SAUTE les etapes
# 3 a 7. Ce raccourci sautait aussi tout controle du registre: la commande
# annoncait une relance reussie sans jamais regarder si le depot et la base
# disent encore la meme chose.
#
# CE JALON NE MET PAS A NIVEAU UNE BASE EN SERVICE. Ce qui est exige ici est
# borne, et entierement EN LECTURE:
#
#   T13 empreinte divergente          -> MIGRATION_CHECKSUM_MISMATCH
#   T14 migration supprimee/renommee  -> MIGRATION_HISTORY_DIVERGENCE
#   T15 migration ajoutee en suffixe  -> ACTIVE_SCHEMA_UPGRADE_REQUIRED, code 9
#   T16 depot identique au registre   -> relance idempotente, code 0
#
# T16 EST LE CAS POSITIF, et il n'est pas decoratif: sans lui, un controle qui
# refuserait toute relance sur une base ACTIVE passerait pour correct.
# LE NOMBRE DE MIGRATIONS SE COMPTE, IL NE S'ECRIT PAS EN DUR.
#
# Ces quatre scenarios exigeaient « dix inscrites ». Le chiffre etait juste par
# accident: 0011 a 0014 ne s'inscrivaient PAS au registre — c'etait le defaut
# corrige dans ce meme lot — et le decompte n'a bouge qu'une fois qu'elles ont
# commence a s'y inscrire. Un attendu code en dur transforme une correction en
# regression apparente, et se serait re-perime a la migration suivante.
MIGRATIONS_ATTENDUES="$(ls "$DB_DIR"/migrations/*.sql | wc -l | tr -d ' ')"

t_active() {
  local nom="$1" geste="$2" code
  local M5="0005_validation_workflow.sql"
  q_amorcer "${nom,,}" || { echoue "le decor $nom n'a pas pu etre pose"; return 1; }
  migrations_copiees
  appeler >/dev/null 2>&1
  local etat inscrites
  etat=$(admb -tAc "select normative_activation_state()" 2>&1)
  inscrites=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
  if [[ "$etat" != "ACTIVE" || "$inscrites" != "$MIGRATIONS_ATTENDUES" ]]; then
    echoue "$nom. le decor n'est pas ACTIVE avec $MIGRATIONS_ATTENDUES migrations (« $etat »,"
    echoue "    $inscrites inscrite(s)); scenario non evalue"
    decor_deposer; return 1
  fi

  case "$geste" in
    empreinte) printf '\n-- FICTIF: reecriture posterieure\n' \
                 >>"$COPIE/db/migrations/$M5" ;;
    disparue)  mv "$COPIE/db/migrations/$M5" \
                  "$COPIE/db/migrations/0005_renommee_active.sql" ;;
    suffixe)   cat >"$COPIE/db/migrations/0011_ajout_sur_active.sql" <<'SQL'
-- FICTIF — migration ajoutee alors que la base est deja ACTIVE.
begin;
comment on schema public is 'ajout sur base active (harnais)';
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');
commit;
SQL
               ;;
    identique) : ;;
  esac

  appeler; code=$?
  local apres
  apres=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)

  case "$geste" in
    identique)
      if [[ $code -eq 0 && "$apres" == "$MIGRATIONS_ATTENDUES" ]]; then
        echo "      ok: $nom. depot identique: la relance idempotente est permise"
      else
        rouge "$nom. une relance sur une base ACTIVE intacte est refusee."
        detail "    code $code, $apres ligne(s) au registre"
        detail "    $(grep -m1 -E '^(ECHEC|ACTIVE_|MIGRATION_)' <<<"$SORTIE_CMD" | cut -c1-140)"
      fi ;;
    suffixe)
      if [[ $code -eq 9 ]] \
         && grep -qF "ACTIVE_SCHEMA_UPGRADE_REQUIRED" <<<"$SORTIE_CMD" \
         && [[ "$apres" == "$MIGRATIONS_ATTENDUES" ]]; then
        echo "      ok: $nom. migration en suffixe sur ACTIVE: refus nomme, zero mutation"
      else
        rouge "$nom. une migration ajoutee sur une base ACTIVE n'est pas nommee."
        detail "    code $code (9 attendu), $apres ligne(s) au registre (10 attendues)"
        detail "    $(grep -m1 -E '^(ECHEC|ACTIVE_|MIGRATION_)' <<<"$SORTIE_CMD" | cut -c1-140)"
        detail "    Sans ce refus, la commande annonce une relance reussie et"
        detail "    ignore silencieusement une migration du depot."
      fi ;;
    *)
      local jeton="MIGRATION_CHECKSUM_MISMATCH"
      [[ "$geste" == "disparue" ]] && jeton="MIGRATION_HISTORY_DIVERGENCE"
      if [[ $code -ne 0 ]] && grep -qF "$jeton" <<<"$SORTIE_CMD" \
         && [[ "$apres" == "$MIGRATIONS_ATTENDUES" ]]; then
        echo "      ok: $nom. divergence detectee sur une base ACTIVE ($jeton)"
      else
        rouge "$nom. une base ACTIVE divergente du depot n'est pas detectee."
        detail "    code $code, $apres ligne(s) au registre; « $jeton » attendu"
        detail "    $(grep -m1 -E '^(ECHEC|ACTIVE_|MIGRATION_)' <<<"$SORTIE_CMD" | cut -c1-140)"
      fi ;;
  esac
  decor_deposer
  return 0
}

t_active T13 empreinte
t_active T14 disparue
t_active T15 suffixe
t_active T16 identique

t_historique T8  supprime
t_historique T9  renomme
t_historique T10 insere
t_historique T11 suffixe

# --- T12. UNE BASE GARDE SON MIGRATEUR ------------------------------------
# Les fonctions du registre sont SECURITY INVOKER et lisent
# `normative_migration_ledger`. Le diagnostic conseillait pourtant, en cas
# d'echec d'interrogation, un simple:
#
#     GRANT EXECUTE ON FUNCTION normative_migration_gate(...) TO <nouveau>;
#
# Ce conseil est incomplet — il manque la TABLE — et surtout il improvise une
# delegation: le nouveau role ne devient pas proprietaire des objets deja crees,
# et rien n'auditerait le changement. La regle de ce jalon est donc l'identite
# STABLE, et le refus est nomme.
if ! q_amorcer t12; then
  echoue "le decor T12 n'a pas pu etre pose"
else
migrations_copiees 0006_ndp_import.sql
appeler >/dev/null 2>&1                       # PENDING, 0001-0005 inscrites
ETAT_T12=$(admb -tAc "select normative_activation_state()" 2>&1)
MIG2="${MIG:0:56}_b"
adm -v ON_ERROR_STOP=1 -v n="$MIG2" -v mdp="$MDP" >/dev/null 2>&1 <<'SQL'
create role :"n" login password :'mdp' createrole createdb;
SQL
admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG2" with grant option;
grant select, insert, references on auth.users to "$MIG2" with grant option;
grant execute on function auth.uid() to "$MIG2" with grant option;
grant create on database "$BASE" to "$MIG2";
SQL
adm -c "alter database \"$BASE\"
          set eurostruct.approved_deployment_roles = '$MIG2,$CTL';" >/dev/null 2>&1
migrations_copiees
SORTIE_T12=$(
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG2:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  bash "$COMMANDE_COPIE" 2>&1
); CODE_T12=$?
APRES_T12=$(admb -tAc "select count(*) from normative_migration_ledger" 2>&1)
CAP_T12=$(adm -tA -v m="$MIG2" <<'SQL'
select coalesce(string_agg(a.r, ' '), '') from unnest(array[
  'eurostruct_normative_writer','eurostruct_normative_bootstrap',
  'eurostruct_normative_activator']) a(r)
 where pg_has_role(:'m', a.r, 'SET') or pg_has_role(:'m', a.r, 'USAGE')
    or pg_has_role(:'m', a.r, 'MEMBER WITH ADMIN OPTION');
SQL
)
if [[ "$ETAT_T12" != "PENDING" ]]; then
  echoue "T12. le decor n'est pas PENDING (« $ETAT_T12 »); scenario non evalue"
elif [[ $CODE_T12 -ne 0 ]] \
     && grep -qF "MIGRATOR_IDENTITY_MISMATCH" <<<"$SORTIE_T12" \
     && [[ "$APRES_T12" == "5" && -z "$CAP_T12" ]]; then
  echo "      ok: T12. un second migrateur est refuse, et rien ne lui reste"
else
  rouge "T12. une base accepte d'etre migree par un AUTRE role."
  detail "    code $CODE_T12, $APRES_T12 ligne(s) au registre (5 attendues)"
  detail "    capacites residuelles du second migrateur: « ${CAP_T12:-aucune} »"
  detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_|MIGRAT)' <<<"$SORTIE_T12" | cut -c1-140)"
fi
# LA BASE D'ABORD, LE ROLE ENSUITE. Le second migrateur possede des objets DANS
# la base d'essai; tant qu'elle existe, `drop role` echoue — silencieusement,
# `2>/dev/null` aidant — et le role survit a chaque execution. Mesure: vingt
# roles « *_b » retrouves sur le cluster, et un harnais suivant qui refuse de
# demarrer parce qu'il trouve des objets etrangers.
decor_deposer
[[ -n "${MIG2:-}" ]] && adm -v n="$MIG2" >/dev/null 2>&1 <<'SQL'
drop owned by :"n";
drop role if exists :"n";
SQL
MIG2=""
fi

# --- T5. le contrat de transactionnalite est UNIFORME ---------------------
# CONTROLE STATIQUE, et il porte sur une propriete du jeu, pas d'un fichier:
# `0001`, `0002` et `0003` n'ont ni `BEGIN` ni `COMMIT`, les sept suivantes en
# ont. Une erreur au milieu d'une des trois premieres laisse donc un fichier
# PARTIELLEMENT applique — et aucun registre ne pourrait rattraper cela, parce
# que l'unite d'application n'existe pas.
#
# Ce qui est exige n'est pas une forme plutot que l'autre: c'est qu'il n'y en
# ait qu'UNE.
AVEC=(); SANS=()
for f in "$DB_DIR"/migrations/*.sql; do
  if grep -qi '^begin;' "$f" && grep -qi '^commit;' "$f"; then
    AVEC+=("$(basename "$f")")
  else
    SANS+=("$(basename "$f")")
  fi
done
if [[ ${#AVEC[@]} -eq 0 || ${#SANS[@]} -eq 0 ]]; then
  echo "      ok: T5. le jeu de migrations a un contrat de transactionnalite unique"
else
  rouge "T5. deux contrats de transactionnalite coexistent dans db/migrations/."
  detail "    avec BEGIN/COMMIT (${#AVEC[@]}): ${AVEC[*]}"
  detail "    sans (${#SANS[@]}): ${SANS[*]}"
  detail "    Une erreur au milieu d'une migration sans transaction laisse un"
  detail "    fichier partiellement applique: aucun registre ne rattrape cela,"
  detail "    parce que l'unite d'application n'existe pas."
fi

# ==========================================================================
# U. LE BRANCHEMENT SE FAIT SUR LE SQLSTATE, PAS SUR LA PROSE
# ==========================================================================
# Le sceau porte des SQLSTATE dedies depuis 6.3b6d — ES001, ES002, ES003 — et
# leur commentaire dit qu'ils existent « pour que l'orchestrateur branche sur le
# CODE, jamais sur le texte ». La commande cherchait pourtant
# `grep SEAL_ALREADY_INSTALLED`, c'est-a-dire du texte humain.
#
# DEUX EPREUVES SYMETRIQUES, et il faut les deux:
#
#   U1. le TEXTE change, le CODE reste  -> le comportement ne bouge pas;
#   U2. le TEXTE reste, le CODE change  -> le refus n'est PAS reconnu.
#
# La premiere seule serait satisfaite par un `grep` sur une portion de message
# qu'on n'aurait pas touchee; la seconde seule, par un branchement qui ne
# reconnaitrait plus rien du tout.
if ! q_amorcer u1; then
  echoue "le decor U n'a pas pu etre pose"
else
migrations_copiees
appeler >/dev/null 2>&1        # la base est deployee et ACTIVE
SCEAU_COPIE="$COPIE/db/control_plane/$(basename "$HARNAIS_SCEAU")"

# --- U1. le texte change, le code reste -----------------------------------
sed -i "s/SEAL_ALREADY_INSTALLED: le sceau/FICTIF_AUTRE_TEXTE: le sceau/" "$SCEAU_COPIE"
appeler; CODE_U1=$?
ETAT_U1=$(admb -tAc "select normative_activation_state()" 2>&1)
if [[ $CODE_U1 -eq 0 && "$ETAT_U1" == "ACTIVE" ]]; then
  echo "      ok: U1. le texte du message change, le comportement ne bouge pas"
else
  rouge "U1. reformuler le message change le comportement (code $CODE_U1)."
  detail "    $(grep -m1 -E '^ECHEC' <<<"$SORTIE_CMD" | cut -c1-140)"
  detail "    La commande branche donc sur la prose, pas sur le SQLSTATE."
fi

# --- U2. le texte reste, le code change -----------------------------------
cp "$DB_DIR/control_plane/$(basename "$HARNAIS_SCEAU")" "$SCEAU_COPIE"
python3 - "$SCEAU_COPIE" <<'FINPY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
i = s.index("SEAL_ALREADY_INSTALLED")
j = s.index("using errcode = 'ES001';", i)
p.write_text(s[:j] + "using errcode = 'ES099';" + s[j + len("using errcode = 'ES001';"):])
FINPY
appeler; CODE_U2=$?
if [[ $CODE_U2 -ne 0 ]]; then
  echo "      ok: U2. le meme texte sous un autre SQLSTATE n'est pas accepte"
else
  rouge "U2. un refus portant un AUTRE SQLSTATE est accepte comme ES001."
  detail "    Le branchement suit le texte: n'importe quel message contenant"
  detail "    « SEAL_ALREADY_INSTALLED » ferait passer la commande."
fi
cp "$DB_DIR/control_plane/$(basename "$HARNAIS_SCEAU")" "$SCEAU_COPIE"
decor_deposer
fi

# ==========================================================================
# V. L'ENVIRONNEMENT NE REDIRIGE PAS LA CIBLE
# ==========================================================================
# libpq lit une douzaine de variables. `PGOPTIONS` injecte des parametres de
# session — `role` compris —, `PGSERVICE` fait resoudre la connexion par un
# fichier, `PGHOSTADDR` remplace l'adresse en laissant `PGHOST` intact dans les
# messages. Un deploiement peut donc viser une base et en atteindre une autre,
# et le compte rendu affichera la premiere.
if ! q_amorcer v1; then
  echoue "le decor V n'a pas pu etre pose"
else
migrations_copiees
# `PGOPTIONS` demande un `SET role` a la connexion. Si la commande le laissait
# passer, `current_user` ne serait plus celui qu'elle annonce — et les
# `pg_has_role(...)` de ses postconditions porteraient sur un autre role.
SORTIE_V=$(
  PGOPTIONS="-c role=$MIG" \
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable" \
  bash "$COMMANDE_COPIE" 2>&1
); CODE_V=$?
ETAT_V=$(admb -tAc "select normative_activation_state()" 2>&1)
PLAN_V=$(admb -tAc "select role_name from normative_control_plane" 2>&1)
if [[ $CODE_V -eq 0 && "$ETAT_V" == "ACTIVE" && "$PLAN_V" == "$CTL" ]]; then
  echo "      ok: V1. PGOPTIONS ne redirige pas l'identite du plan de controle"
else
  rouge "V1. l'environnement a influence la connexion (code $CODE_V)."
  detail "    etat « $ETAT_V », plan fige « $PLAN_V », attendu « $CTL »"
  detail "    $(grep -m1 -E '^ECHEC' <<<"$SORTIE_V" | cut -c1-140)"
fi
decor_deposer
fi

# --- V2. mode strict, cible distante, TLS insuffisant ---------------------
# `127.0.0.2` est joignable mais n'est pas la boucle locale reconnue par la
# commande: la politique TLS s'y applique donc, et `sslmode=disable` doit etre
# refuse AVANT toute connexion. Aucun decor n'est necessaire — c'est le
# propos: le refus tombe sans qu'un octet parte.
SORTIE_V2=$(
  ESC_PLAN_URL="postgresql://p:x@127.0.0.2:5432/b?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://m:x@127.0.0.2:5432/b?sslmode=disable" \
  bash "$COMMANDE_COPIE" 2>&1
); CODE_V2=$?
SORTIE_V2H=$(
  ESC_PLAN_URL="postgresql://p:x@127.0.0.2:5432/b?sslmode=disable" \
  ESC_MIGRATOR_URL="postgresql://m:x@127.0.0.2:5432/b?sslmode=disable" \
  bash "$COMMANDE_COPIE" --auto-heberge 2>&1
); CODE_V2H=$?
if [[ $CODE_V2 -ne 0 ]] && grep -qiE "sslmode|TLS" <<<"$SORTIE_V2" \
   && ! grep -qiE "sslmode=disable\.$" <<<"$SORTIE_V2H"; then
  echo "      ok: V2. mode strict: une cible distante en clair est refusee"
else
  rouge "V2. le mode strict accepte une cible distante sans TLS verifiable."
  detail "    strict: code $CODE_V2 — $(grep -m1 ECHEC <<<"$SORTIE_V2" | cut -c1-110)"
  detail "    --auto-heberge: code $CODE_V2H"
fi

# --- V3. LA MATIERE TLS DE L'URL EST-ELLE PORTEE ? ------------------------
# LE MODE STRICT EXIGE `verify-ca` OU `verify-full` VERS UNE CIBLE DISTANTE
# (V2). Ces deux modes n'ont de sens qu'avec une AUTORITE DE CERTIFICATION: sans
# elle, libpq echoue a la negociation. Or:
#
#   * `PGSSLROOTCERT` est EFFACEE par l'hygiene d'environnement de la commande —
#     a juste titre, une variable ambiante ne doit pas decider de la cible;
#   * le decoupeur d'URL ne lisait que `sslmode`, et laissait tomber
#     `sslrootcert` EN SILENCE.
#
# L'exploitant n'avait donc aucun moyen de designer sa CA: la commande exigeait
# `verify-full` tout en rendant impossible de le satisfaire autrement qu'avec
# le magasin par defaut de libpq (`~/.postgresql/root.crt`). Une exigence qu'on
# ne peut pas satisfaire n'est pas une exigence, c'est une impasse.
#
# CE SCENARIO NE DEPEND PAS DU SERVEUR, ET C'EST DELIBERE. libpq ne lit le
# fichier de CA qu'APRES que le serveur a accepte la negociation SSL: une
# assertion sur son message d'erreur passerait ici (ou `ssl = on`) et echouerait
# en CI, ou l'image `postgres:16` demarre sans SSL. Ce qui est exige est donc un
# controle que la commande fait ELLE-MEME, avant toute connexion: la matiere TLS
# nommee dans l'URL doit exister et etre lisible, sinon refus nomme.
VR_CA="/nonexistent/esc-ca-$JETON.crt"
SORTIE_VR=$(
  ESC_PLAN_URL="postgresql://p:x@127.0.0.2:5432/b?sslmode=verify-full&sslrootcert=$VR_CA" \
  ESC_MIGRATOR_URL="postgresql://m:x@127.0.0.2:5432/b?sslmode=verify-full&sslrootcert=$VR_CA" \
  bash "$COMMANDE_COPIE" 2>&1
); CODE_VR=$?
if [[ $CODE_VR -ne 0 ]] \
   && grep -qF "DEPLOYMENT_TLS_MATERIAL_MISSING" <<<"$SORTIE_VR" \
   && grep -qF "$VR_CA" <<<"$SORTIE_VR"; then
  echo "      ok: V3. la CA nommee dans l'URL est portee, et verifiee"
else
  rouge "V3. la matiere TLS nommee dans l'URL n'est pas portee."
  detail "    code $CODE_VR; la CA demandee etait « $VR_CA »"
  detail "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_|REFUS)' <<<"$SORTIE_VR" | cut -c1-140)"
  detail "    Le mode strict exige verify-ca/verify-full, et rien ne permet de"
  detail "    designer l'autorite: PGSSLROOTCERT est effacee, et le decoupeur"
  detail "    d'URL ignore sslrootcert. L'exigence est insatisfiable."
fi

# --- V3b. UN PARAMETRE TLS NON PORTE NE DOIT PAS ETRE IGNORE --------------
# Accepter puis jeter en silence est la meme faute, en pire: l'exploitant croit
# avoir configure quelque chose. Ce qui n'est pas porte doit etre REFUSE.
SORTIE_VRB=$(
  ESC_PLAN_URL="postgresql://p:x@127.0.0.2:5432/b?sslmode=require&sslcompression=1" \
  ESC_MIGRATOR_URL="postgresql://m:x@127.0.0.2:5432/b?sslmode=require&sslcompression=1" \
  bash "$COMMANDE_COPIE" --auto-heberge 2>&1
); CODE_VRB=$?
if [[ $CODE_VRB -ne 0 ]] && grep -qF "sslcompression" <<<"$SORTIE_VRB"; then
  echo "      ok: V3b. un parametre TLS non porte est refuse, et nomme"
else
  rouge "V3b. un parametre TLS inconnu est ignore en silence."
  detail "    code $CODE_VRB; « sslcompression » n'apparait pas dans le refus."
fi

# --- V4. LA CA EST PORTEE, DECODEE, ROUTEE, ET N'EST PAS CELLE DE L'AIR ---
# V3 etablit qu'une CA introuvable est REFUSEE. Celui-ci etablit ce qui arrive
# quand elle est VALIDE: qui la recoit, et avec quelle valeur.
#
# `sslmode=disable` SUR LA BOUCLE LOCALE, ET C'EST DELIBERE. Ce qui est mesure
# est le TRANSPORT de la valeur jusqu'a chaque processus, pas la negociation
# TLS: en `verify-full` les connexions echoueraient — l'image `postgres:16` de
# la CI demarre sans SSL — et le co-processus du verrou ne serait jamais
# atteint. libpq ignore `PGSSLROOTCERT` sous `disable`; le leurre, lui, la voit.
#
# LE CHEMIN CONTIENT UN ESPACE et est percent-encode dans l'URL: un decoupage
# qui oublierait de decoder rendrait « /tmp/esc%20ca.crt ».
if ! q_amorcer v4; then
  echoue "le decor V4 n'a pas pu etre pose"
else
migrations_copiees
CA_PLAN="$COPIE/ca du plan.crt"
CA_MIG="$COPIE/ca du migrateur.crt"
printf 'FICTIF CA PLAN\n'      >"$CA_PLAN"
printf 'FICTIF CA MIGRATEUR\n' >"$CA_MIG"
CA_HOSTILE="$COPIE/ca hostile ambiante.crt"
printf 'FICTIF CA HOSTILE\n' >"$CA_HOSTILE"
LEURRE_V4="$COPIE/leurre_v4"; mkdir -p "$LEURRE_V4"
JOURNAL_V4="$COPIE/v4.log"; : >"$JOURNAL_V4"
VRAI_V4="$(command -v psql)"
cat >"$LEURRE_V4/psql" <<LEURREFIN
#!/usr/bin/env bash
# FAUX psql — scenario V4. Il note QUI se connecte et avec QUELLE CA, puis
# passe la main. Il ne lit JAMAIS l'entree: le co-processus du verrou la garde
# ouverte, et c'est justement lui qu'on veut observer.
printf 'ROLE=%s CA=%s ARGV=%s\n' "\${PGUSER:-?}" "\${PGSSLROOTCERT:-<absente>}" "\$*" \\
  >>"$JOURNAL_V4"
exec "$VRAI_V4" "\$@"
LEURREFIN
chmod +x "$LEURRE_V4/psql"
CA_PLAN_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$CA_PLAN")
CA_MIG_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$CA_MIG")
SORTIE_V4=$(
  PATH="$LEURRE_V4:$PATH" \
  PGSSLROOTCERT="$CA_HOSTILE" \
  ESC_PLAN_URL="postgresql://$CTL:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable&sslrootcert=$CA_PLAN_ENC" \
  ESC_MIGRATOR_URL="postgresql://$MIG:$MDP@localhost:${PGPORT:-5432}/$BASE?sslmode=disable&sslrootcert=$CA_MIG_ENC" \
  bash "$COMMANDE_COPIE" 2>&1
); CODE_V4=$?
ETAT_V4=$(admb -tAc "select normative_activation_state()" 2>&1)
# Le co-processus du verrou est le seul appel du plan qui porte « -At ».
# LE CHEMIN CONTIENT DES ESPACES — c'est le propos de ce scenario —, donc on
# decoupe sur les DELIMITEURS et non sur « le prochain espace ». Premiere
# ecriture: `CA=\([^ ]*\)` s'arretait au premier espace et rendait « .../ca »,
# ce qui faisait rougir V4 sur une valeur pourtant correctement transmise.
CA_VERROU=$(grep -m1 -F -- "-At" "$JOURNAL_V4" | sed 's/.*CA=//; s/ ARGV=.*//')
MAUVAISES=$(grep -c "ROLE=$CTL CA=$CA_MIG\b" "$JOURNAL_V4")
MAUVAISES=$((MAUVAISES + $(grep -c "ROLE=$MIG CA=$CA_PLAN\b" "$JOURNAL_V4")))
if [[ $CODE_V4 -ne 0 || "$ETAT_V4" != "ACTIVE" ]]; then
  echoue "V4. le deploiement n'a pas abouti (code $CODE_V4, « $ETAT_V4 »);"
  echoue "    $(grep -m1 -E '^(ECHEC|DEPLOYMENT_|REFUS)' <<<"$SORTIE_V4" | cut -c1-120)"
elif grep -qF "$CA_HOSTILE" "$JOURNAL_V4"; then
  rouge "V4. la CA ambiante (PGSSLROOTCERT) atteint un processus psql."
  detail "    $(grep -m1 -F "$CA_HOSTILE" "$JOURNAL_V4" | cut -c1-140)"
elif ! grep -q "ROLE=$CTL CA=$CA_PLAN\b" "$JOURNAL_V4"; then
  rouge "V4. le plan de controle ne recoit pas la CA de SON URL."
  detail "    attendu « $CA_PLAN »"
  detail "    $(grep -m1 "ROLE=$CTL" "$JOURNAL_V4" | cut -c1-140)"
elif ! grep -q "ROLE=$MIG CA=$CA_MIG\b" "$JOURNAL_V4"; then
  rouge "V4. le migrateur ne recoit pas la CA de SON URL."
  detail "    attendu « $CA_MIG »"
elif [[ "$MAUVAISES" != "0" ]]; then
  rouge "V4. une CA a ete routee vers le mauvais acteur ($MAUVAISES fois)."
elif [[ "$CA_VERROU" != "$CA_PLAN" ]]; then
  rouge "V4. le co-processus du verrou ne recoit pas la CA du plan."
  detail "    obtenu « ${CA_VERROU:-<aucune>} », attendu « $CA_PLAN »"
elif grep -qF "$MDP" "$JOURNAL_V4" || grep -qF "postgresql://" "$JOURNAL_V4"; then
  rouge "V4. un secret ou une URL complete apparait dans argv."
  detail "    $(grep -m1 -F "$MDP" "$JOURNAL_V4" | cut -c1-100)"
elif grep -qF "$MDP" <<<"$SORTIE_V4"; then
  rouge "V4. le mot de passe apparait dans le compte rendu de la commande."
else
  echo "      ok: V4. CA decodee, routee par acteur, verrou compris; rien dans argv"
fi
decor_deposer
fi

# --- V5. `sslcert` ET `sslkey` NE SONT PAS PORTES, ET LE DISENT ------------
# Ils l'ont ete un temps, sans qu'aucun test ne les exerce. Annoncer un support
# non mesure est la meme faute qu'ignorer un parametre en silence — elle se
# decouvre seulement plus tard.
for PARAM_V5 in sslcert sslkey sslcompression; do
  SORTIE_V5=$(
    ESC_PLAN_URL="postgresql://p:x@127.0.0.2:5432/b?sslmode=require&$PARAM_V5=/tmp/x" \
    ESC_MIGRATOR_URL="postgresql://m:x@127.0.0.2:5432/b?sslmode=require&$PARAM_V5=/tmp/x" \
    bash "$COMMANDE_COPIE" --auto-heberge 2>&1
  ); CODE_V5=$?
  if [[ $CODE_V5 -ne 0 ]] && grep -qF "$PARAM_V5" <<<"$SORTIE_V5" \
     && ! grep -qF "1/10" <<<"$SORTIE_V5"; then
    echo "      ok: V5. « $PARAM_V5 » est refuse avant toute connexion, et nomme"
  else
    rouge "V5. « $PARAM_V5 » n'est pas refuse avant connexion."
    detail "    code $CODE_V5; $(grep -m1 -E '^(REFUS|ECHEC)' <<<"$SORTIE_V5" | cut -c1-120)"
  fi
done

echo ""
echo "================================================="
if [[ $KO -eq 0 && $ROUGES -eq 0 ]]; then
  echo " La commande officielle ne laisse rien derriere elle."
  echo "================================================="
  exit 0
fi
echo " Reprise de la commande officielle:"
echo "   $KO ecart(s) de decor"
echo "   $ROUGES ouverture(s) a fermer"
echo "================================================="
exit 1
