#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6b: LE CONTRAT DE FINALISATION
#
#   finalisation_contract.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# La phase 2 fait passer le sous-systeme de PENDING a ACTIVE. C'est le moment
# ou tout devient engageant: apres elle, des confirmations normatives peuvent
# etre ecrites, et elles engagent toutes les etudes d'une juridiction.
#
# Ce fichier ne verifie pas que la finalisation MARCHE — `two_phase_deployment.sh`
# s'en charge. Il verifie qu'elle ne peut pas etre CONTOURNEE, et il le fait en
# essayant de la contourner, huit fois.
#
# LES HUIT
# ---------
#   1. Approbation des parametres   le migrateur change une declaration APRES
#                                   la revue; la finalisation la fige quand meme
#   2. Appel direct                 `normative_record_activation` appelee sans
#                                   passer par la finalisation, avec un faux
#                                   nom de migrateur
#   3. Identite du plan de controle  seul le NOM est fige; un role substitue
#                                   sous ce nom herite de l'exemption
#   4. Finalisations concurrentes   deux connexions reelles; le perdant doit
#                                   obtenir ACTIVE, pas une erreur
#   5. Ecritures en PENDING         les quatre ecritures normatives doivent
#                                   etre refusees AU MOTIF DE L'ETAT
#   6. Immuabilite de l'activation  append-only: ni UPDATE ni DELETE
#   7. Activator dans les harnais   le jeu canonique passe de cinq a six
#   8. Separation plan/migrateur    sur decor VIERGE: deux roles -> accepte,
#                                   un seul role -> refuse pour ce motif
#
# CHAQUE SCENARIO POSE SON PROPRE DECOR, ET LE DEPOSE.
# Les roles d'autorite sont GLOBAUX au cluster: deux decors ne peuvent pas
# coexister. Chaque scenario cree donc ses roles et sa base, puis les detruit —
# ce qui rend chaque contre-exemple independant de l'ordre, et un rouge
# imputable a lui seul.
#
# Toutes les identites sont FICTIVES. Aucune confirmation normative reelle
# n'est creee: les seules ecritures tentees le sont pour PROUVER qu'elles sont
# refusees.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(dirname "$HERE")"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
# LE SEUL CHEMIN QUI SAIT APPLIQUER UNE MIGRATION (6.3b6e): les harnais
# l'empruntent AUSSI, sans quoi ils testeraient un chemin que la
# production n'emprunte pas.
# shellcheck source=../apply_migration.sh
source "$HERE/../apply_migration.sh"

PREFIXE="${1:?usage: finalisation_contract.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "finalisation_contract.sh" || exit 2
harnais_verrou_prendre  "finalisation_contract.sh" || exit $?
exiger_cluster_jetable  "finalisation_contract.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"

# LES SIX ROLES CANONIQUES — activator COMPRIS.
#
# C'est le point 7 lui-meme, applique a ce fichier: un jeu de cinq laissait
# `eurostruct_normative_activator` derriere lui a chaque execution. Mesure sur
# ce cluster avant d'ecrire ce commentaire: le role etait present, residu d'une
# execution anterieure, et aucune postcondition ne l'avait vu.
CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)

# `anon` et `authenticated` sont crees par `00_supabase_stub.sql`, qui est
# applique dans chaque decor. Ils sont GLOBAUX comme les autres et doivent donc
# etre rendus eux aussi — sans quoi la postcondition « aucun role residuel »
# est fausse. Mesure: ils survivaient a chaque execution.
STUB_ROLES=(anon authenticated)

exiger_roles_absents "finalisation_contract.sh" "${CANONIQUES[@]}" || exit 2

KO=0; ROUGES=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
rouge()  { echo "      ROUGE ATTENDU (a fermer): $*"; ROUGES=$((ROUGES + 1)); }

adm() { psql -X -q -d postgres "$@"; }

# --------------------------------------------------------------------------
# LE DECOR, POSE ET DEPOSE PAR SCENARIO
# --------------------------------------------------------------------------
# `decor_poser <suffixe> <mode>`
#   mode = separe      le plan de controle provisionne les roles d'autorite,
#                      le migrateur applique les migrations. C'est le modele
#                      de deploiement documente.
#   mode = greenfield  un seul role privilegie existe: il provisionne ET
#                      migre. C'est le cas que le point 8 doit voir refuser.
#
# Rend 0 si la phase 1 s'est terminee en PENDING; 1 sinon (et le motif est
# imprime). Positionne MIG, CTL, BASE.
MIG=""; CTL=""; BASE=""; MIG_MDP=""; CTL_MDP=""
mig()    { PGUSER="$MIG" PGPASSWORD="$MIG_MDP" psql -X -q -d "$BASE" "$@"; }
ctl()    { PGUSER="$CTL" PGPASSWORD="$CTL_MDP" psql -X -q -d "$BASE" "$@"; }
ctl_pg() { PGUSER="$CTL" PGPASSWORD="$CTL_MDP" psql -X -q -d postgres "$@"; }
admb()   { psql -X -q -d "$BASE" "$@"; }

decor_poser() {
  local suffixe="$1" mode="$2" f sortie provisionneur
  # LE TEARDOWN EST ARME AVANT LA PREMIERE CREATION. Mesure faite sur
  # `authority_closure.sh`: les chemins de refus ci-dessous rendaient 1 sans
  # rien defaire, un seul refus laissait les roles canoniques dans le cluster,
  # et TOUS les decors suivants echouaient en « phase 0 refusee ».
  esc_decor_ouvrir "$suffixe" decor_deposer || { echoue "decor: armement refuse"; return 1; }

  MIG="${PREFIXE}_m${suffixe}_${JETON}"; MIG_MDP="FICTIF-fc-mig-$suffixe-$JETON"
  CTL="${PREFIXE}_c${suffixe}_${JETON}"; CTL_MDP="FICTIF-fc-ctl-$suffixe-$JETON"
  BASE="${PREFIXE}_d${suffixe}_${JETON}"

  creer_role "$MIG" "login password '$MIG_MDP' createrole createdb" \
    || { echoue "decor $suffixe: creation du migrateur impossible"; esc_decor_abandonner; return 1; }
  if [[ "$mode" == "separe" ]]; then
    creer_role "$CTL" "login password '$CTL_MDP' createrole" \
      || { echoue "decor $suffixe: creation du plan de controle impossible"; esc_decor_abandonner; return 1; }
    provisionneur=ctl_pg
    # L'administrateur doit pouvoir rendre la main sur les roles que le plan de
    # controle aura crees, pour le nettoyage.
    adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  else
    # GREENFIELD: le migrateur est seul. Il n'y a pas de plan de controle.
    CTL="$MIG"; CTL_MDP="$MIG_MDP"
    provisionneur=mig_pg
    adm -c "grant \"$MIG\" to ${PGUSER:-postgres};" >/dev/null 2>&1
  fi

  creer_base "$BASE" "owner \"$MIG\"" \
    || { echoue "decor $suffixe: creation de la base impossible"; esc_decor_abandonner; return 1; }
  registre_base "$BASE"

  admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
-- LE PROVISIONNEUR APPLIQUE LA PHASE 0: il cree des tables et des fonctions
-- dans « public », et les transfere a l'activateur. D'ou CREATE avec GRANT
-- OPTION. Prerequis de deploiement — voir docs/DEPLOIEMENT_PREREQUIS.md.
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL

  # PHASE 0 — LE SCEAU (6.3b6c). C'est elle qui cree les six roles canoniques
  # ET la racine de confiance, sous le PROVISIONNEUR. En mode « separe » c'est
  # le plan de controle; en greenfield, le migrateur lui-meme — et c'est
  # precisement ce que le point 8b existe pour voir refuser a la finalisation.
  local phase0
  case "$provisionneur" in
    ctl_pg) phase0=ctl ;;
    *)      phase0=mig ;;
  esac
  if ! sortie=$($phase0 -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
    echoue "decor $suffixe: phase 0 refusee:"
    esc_diag_rapporter "decor $suffixe / phase 0 (sceau)" "$sortie"
    esc_decor_abandonner; return 1
  fi
  adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
  # L'EMPRUNT: DEUX ROLES. L'activateur n'est plus jamais prete.
  $provisionneur -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
  adm -c "alter database \"$BASE\"
            set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
  # DECLARATION LEGITIME, posee par le deploiement. Elle sert de valeur « revue
  # par le plan de controle » au point 1: sans elle, la comparaison opposerait
  # une valeur vide a une valeur injectee, ce qui montrerait le meme defaut
  # mais moins clairement.
  adm -c "alter database \"$BASE\"
            set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1

  # PHASE 1 — par le migrateur, sans 0000 qui appartient a la phase 0.
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      sortie="$ESC_MIGRATION_SORTIE"
      echoue "decor $suffixe: phase 1 refusee sur $(basename "$f"):"
      esc_diag_rapporter "decor $suffixe / phase 1 / $(basename "$f")" "$sortie"
      esc_decor_abandonner; return 1
    fi
  done

  local etat
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "PENDING" ]]; then
    echoue "decor $suffixe: phase 1 ne se termine pas en PENDING (obtenu: $etat)"
    esc_decor_abandonner; return 1
  fi
  return 0
}
mig_pg() { PGUSER="$MIG" PGPASSWORD="$MIG_MDP" psql -X -q -d postgres "$@"; }

# `decor_deposer` rend le jeu canonique au cluster. Les roles d'autorite sont
# globaux: sans cela, le scenario suivant se refuserait sur `exiger_roles_absents`.
decor_deposer() {
  local r ko=0
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || { NETTOYAGE_KO=1; ko=1; }
  for r in "${CANONIQUES[@]}" "${STUB_ROLES[@]}"; do
    adm -c "drop owned by \"$r\";"      >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1 || ko=1
  done
  for r in "$MIG" "$CTL"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"      >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1 || ko=1
  done
  # REND SON CODE. `esc_decor_fermer` le lit: un teardown qui echoue en
  # silence est la meme faute qu'un teardown absent. Seul le `drop role` fait
  # foi — `drop owned by` echoue normalement sur un role canonique jamais cree.
  return $ko
}

NETTOYAGE_KO=0
TOUS_ROLES=()
sortie_propre() {
  local r
  decor_deposer
  # CHEMINS DE SORTIE 3 ET 5 (erreur shell, echec dans le teardown): un decor
  # peut etre encore arme ici. `esc_decor_fermer` est idempotent — s'il a deja
  # ete appele il ne refait rien; sinon c'est LUI qui rend le decor.
  esc_decor_fermer
  (( ESC_DECOR_TEARDOWN_KO == 0 )) || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${STUB_ROLES[@]}"; do registre_role "$r"; done
  for r in "${TOUS_ROLES[@]}"; do registre_role "$r"; done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "finalisation_contract.sh" \
    "${CANONIQUES[@]}" "${STUB_ROLES[@]}" "${TOUS_ROLES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
# ET SUR SIGNAL: sans cela, TERM ou Ctrl-C tuent bash avant le piege ci-dessus
# et le decor global reste derriere (voir harnais_piege_signaux).
harnais_piege_signaux

# Chaque decor pose ajoute ses deux roles a la liste des noms dont l'absence
# sera exigee en sortie — par NOM EXACT, jamais par motif.
suivre_decor() { TOUS_ROLES+=("$MIG"); [[ "$CTL" != "$MIG" ]] && TOUS_ROLES+=("$CTL"); return 0; }

echo "    contrat de finalisation: huit tentatives de contournement"

# ==========================================================================
# DECOR 1 — reste en PENDING.  Points 5 et 6.
# ==========================================================================
if ! decor_poser 1 separe; then
  echoue "le decor 1 n'a pas pu etre pose: les points 5 et 6 ne sont pas evalues"
else
suivre_decor
echo "      ok: decor 1 — phase 1 appliquee par « $MIG », etat PENDING"

# --------------------------------------------------------------------------
# 5. AUCUNE ECRITURE NORMATIVE EN PENDING
# --------------------------------------------------------------------------
# Tant que le deploiement n'est pas finalise, RIEN ne doit pouvoir engager une
# juridiction. C'est ce que 0010 AFFIRME deja, en toutes lettres, a l'appui de
# l'assouplissement du bloc A de la topologie:
#
#   « En PENDING, AUCUNE confirmation normative n'est possible — les
#     declencheurs la refusent — donc rien n'est engage. »
#
# Les cinq ecritures sont donc tentees, par les chemins qui existent
# reellement, pour verifier que cette phrase est vraie.
admb >/dev/null 2>&1 <<'SQL'
insert into auth.users (id, email) values
  ('a0000000-0000-0000-0000-000000000001', 'FICTIF-fc-1@eurostruct.test'),
  ('a0000000-0000-0000-0000-000000000002', 'FICTIF-fc-2@eurostruct.test')
on conflict do nothing;
SQL

PENDING_OUVERT=0
DETAIL_A="refus sans mention de l etat"
# a) l'amorcage, qui est la porte d'entree de toute la chaine
SORTIE=$(ctl -tAc "select bootstrap_normative_administrator(
           'a0000000-0000-0000-0000-000000000001', 'FICTIF Racine',
           'FICTIF — amorcage tente en PENDING.')" 2>&1)
if ! grep -qiE "PENDING|pas actif|non active" <<<"$SORTIE"; then
  PENDING_OUVERT=$((PENDING_OUVERT + 1))
  DETAIL_A="$(head -1 <<<"$SORTIE" | cut -c1-120)"
fi

# b), c), d), e) les ecritures directes sur les quatre tables append-only.
#
# Un refus de FORME (colonne obligatoire, droit manquant) ne prouve rien: il
# tomberait aussi bien en ACTIVE. On veut un refus qui NOMME l'etat — c'est la
# seule preuve que l'ecriture est refusee PARCE QUE le deploiement n'est pas
# finalise. Tout autre refus est compte comme « non prouve ».
DETAIL_T=""
for t in normative_authorisation_grants normative_authorisation_revocations \
         normative_rule_confirmations normative_rule_confirmation_revocations; do
  S=$(admb -c "insert into $t default values;" 2>&1)
  if ! grep -qiE "PENDING|pas actif|non active" <<<"$S"; then
    PENDING_OUVERT=$((PENDING_OUVERT + 1))
    [[ -n "$DETAIL_T" ]] || DETAIL_T="$t: $(grep -m1 -iE 'ERROR|ERREUR' <<<"$S" | cut -c1-110)"
  fi
done

if [[ "$PENDING_OUVERT" != "0" ]]; then
  rouge "5. $PENDING_OUVERT ecriture(s) normative(s) sur 5 ne sont pas refusees"
  rouge "   AU MOTIF DE L'ETAT PENDING. Or 0010 affirme que « les declencheurs"
  rouge "   la refusent » — et s'appuie sur cette phrase pour n'exiger le bloc A"
  rouge "   de la topologie qu'en ACTIVE. Amorcage: $DETAIL_A"
  [[ -n "$DETAIL_T" ]] && rouge "   $DETAIL_T"
else
  echo "      ok: 5. les cinq ecritures normatives sont refusees en PENDING"
fi

# --------------------------------------------------------------------------
# 6. L'ACTIVATION EST APPEND-ONLY
# --------------------------------------------------------------------------
# `normative_control_plane` et `normative_approved_settings` portent chacune un
# declencheur `before update or delete` qui refuse. `normative_activation` n'en
# a pas — alors qu'elle porte le fait le plus engageant des trois: l'existence
# de la ligne EST l'etat ACTIVE.
#
# Consequence: qui peut ecrire au nom de l'activateur peut DETRUIRE la ligne,
# ce qui ramene le sous-systeme en PENDING sans aucune trace, puis le
# reactiver — `normative_record_activation` ne refuse que si la ligne EXISTE.
# L'audit de deploiement devient reecriturable.
#
# La verification porte sur le CATALOGUE: c'est la structure qui manque, et un
# refus obtenu par manque de droits ne prouverait pas qu'elle est la.
TRIG_ACT=$(admb -tAc "select count(*) from pg_trigger t
                       join pg_class c on c.oid = t.tgrelid
                      where c.relname = 'normative_activation'
                        and not t.tgisinternal" 2>&1)
TRIG_PLAN=$(admb -tAc "select count(*) from pg_trigger t
                        join pg_class c on c.oid = t.tgrelid
                       where c.relname = 'normative_control_plane'
                         and not t.tgisinternal" 2>&1)
POL_ACT=$(admb -tAc "select string_agg(polcmd::text, ',' order by polcmd::text)
                       from pg_policy p join pg_class c on c.oid = p.polrelid
                      where c.relname = 'normative_activation'" 2>&1)
APPEND_OUVERT=0
[[ "$TRIG_ACT" == "0" ]] && APPEND_OUVERT=1
# `polcmd = '*'` signifie FOR ALL: la policy de l'activateur autorise UPDATE et
# DELETE au meme titre que INSERT.
grep -q '\*' <<<"$POL_ACT" && APPEND_OUVERT=$((APPEND_OUVERT + 1))

if [[ "$APPEND_OUVERT" != "0" ]]; then
  rouge "6. « normative_activation » n'est PAS append-only:"
  rouge "   declencheurs non internes: $TRIG_ACT (le plan de controle en a $TRIG_PLAN)"
  rouge "   commandes couvertes par les policies: $POL_ACT (« * » = FOR ALL)"
  rouge "   Detruire la ligne ramene en PENDING sans trace, et la reactivation"
  rouge "   redevient possible: l'audit de deploiement est reecriturable."
else
  echo "      ok: 6. l'activation est append-only (declencheur + policies)"
fi

esc_decor_fermer
fi

# ==========================================================================
# DECOR 2 — point 2: l'appel direct de l'ecriture de confiance.
# ==========================================================================
# `normative_record_activation` est SECURITY DEFINER, possedee par
# l'activateur, et `execute` est accorde a `eurostruct_deployment` — que le
# plan de controle detient. Elle prend le nom du migrateur EN ARGUMENT.
#
# Si elle aboutit avec un nom qui n'est pas celui du vrai migrateur, alors la
# finalisation entiere devient facultative: revocations, verification du
# donneur, separation des roles, tout est saute — et le vrai migrateur
# conserve ses emprunts pendant que le sous-systeme passe ACTIVE.
#
# LE FAUX NOM EST UN ROLE QUI EXISTE ET NE DETIENT RIEN. Un nom inexistant
# ferait echouer `pg_has_role` sur « role does not exist », ce qui ne prouverait
# rien: le refus viendrait du catalogue, pas du contrat.
#
# LES EMPRUNTS SONT D'ABORD RENDUS A LA MAIN, PAR LE DONNEUR. Ce n'est pas une
# facilite de test: c'est exactement ce que la phase 2 execute (fait F3, seul le
# donneur peut revoquer), et un operateur peut l'ecrire lui-meme. Sans cela le
# refus viendrait de la topologie — c'est-a-dire de l'ETAT DU CLUSTER, pas
# d'une regle — et ne prouverait rien sur le contrat. Mesure sur ce meme
# fichier avant correction: le refus obtenu etait « topologie: le migrateur
# atteint eurostruct_normative_writer », un accident de decor.
if ! decor_poser 2 separe; then
  echoue "le decor 2 n'a pas pu etre pose: le point 2 n'est pas evalue"
else
suivre_decor
DEUX=0
# 2a. AUCUNE IDENTITE A FOURNIR. L'ancienne signature `(text, text)` prenait le
#     plan de controle et le migrateur en arguments. Elle ne doit plus exister:
#     `create or replace` en aurait fait une surcharge vivante a cote de la
#     nouvelle, et la porte serait restee ouverte.
SURCHARGE=$(admb -tAc "select count(*) from pg_proc
                        where proname = 'normative_record_activation'
                          and pronargs > 0" 2>&1)
[[ "$SURCHARGE" == "0" ]] || { rouge "2a. l'ecriture de confiance accepte encore"
                               rouge "    $SURCHARGE signature(s) a arguments: l'identite"
                               rouge "    de l'installateur reste fournie par l'appelant."
                               DEUX=1; }

# 2b. SANS PREPARATION, RIEN. Appelee directement, sans que la phase 2 ait
#     derive quoi que ce soit du catalogue, l'ecriture de confiance doit
#     refuser — et le dire.
# Depuis 6.3b6c, le refus arrive encore plus tot: l'ecriture de confiance exige
# que le VERROU de finalisation soit detenu par la transaction courante, et
# seul `normative_finalize_deployment()` le prend. « Pas de preparation » et
# « pas de verrou » sont deux refus du meme contrat, et le second est le plus
# fort — il ferme la composition, pas seulement l'ordre des etapes.
SANS_PREP=$(ctl -tAc "select normative_record_activation()" 2>&1)
grep -qiE "intention|preparation|prepar|verrou de finalisation" <<<"$SANS_PREP" \
  || { rouge "2b. l'appel direct sans preparation n'est pas refuse pour ce motif:"
       rouge "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$SANS_PREP" | cut -c1-140)"; DEUX=1; }

# 2c. AVEC PREPARATION MAIS SANS RESTITUTION, RIEN NON PLUS. C'est la propriete
#     que 0010 revendiquait deja — « ce qui la protege n'est pas le chemin
#     d'appel, c'est l'ETAT qu'elle exige » — et qui etait fausse. On la
#     verifie: on prepare pour de bon, puis on saute la revocation.
MANIFESTE=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
PREP=$(ctl -v esc_v="$MANIFESTE" -tAc "select normative_prepare_activation(:'esc_v')" 2>&1)
if grep -qiE "verrou de finalisation|n'est pas une operation autonome" <<<"$PREP"; then
  # LA PREPARATION ISOLEE N'EXISTE PLUS (6.3b6c). Elle exige le verrou de
  # finalisation, que seul le finaliseur prend: il n'y a plus d'etat
  # intermediaire a laisser trainer, et donc plus de saut d'etape possible.
  # C'est une fermeture plus forte que celle que ce point cherchait.
  echo "      ok: 2c. la preparation isolee est refusee — pas de verrou, donc"
  echo "             pas d'etat intermediaire a exploiter"
elif ! grep -qE '^[0-9a-f]{64}$' <<<"$PREP"; then
  echoue "2c. la preparation isolee est refusee, mais pas au motif du verrou:"
  echoue "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$PREP" | cut -c1-140)"
else
  SAUT=$(ctl -tAc "select normative_record_activation()" 2>&1)
  grep -qiE "detient encore|n'ont pas ete restitues|verrou de finalisation" <<<"$SAUT" \
    || { rouge "2c. l'ecriture de confiance accepte alors que le migrateur detient"
         rouge "    encore ses emprunts: $(grep -m1 -iE 'ERROR|ERREUR' <<<"$SAUT" | cut -c1-120)"
         DEUX=1; }
fi

ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT" == "ACTIVE" ]]; then
  AUDIT=$(admb -tAc "select activated_by || ' | ' || left(topology_digest, 12)
                       from normative_activation" 2>&1)
  rouge "2. L'APPEL DIRECT A ACTIVE LE SOUS-SYSTEME en sautant la finalisation."
  rouge "   audit inscrit: $AUDIT"
elif [[ $DEUX -eq 0 ]]; then
  echo "      ok: 2. l'ecriture de confiance ne recoit aucune identite, refuse"
  echo "             sans preparation, et refuse sans restitution"
fi
esc_decor_fermer
fi

# ==========================================================================
# DECOR 3 — point 1: figer n'est pas approuver.
# ==========================================================================
# La finalisation fige la valeur COURANTE des trois `ALTER DATABASE ... SET`.
# Or ces valeurs sont posees par le proprietaire de la base — le migrateur. Il
# peut donc les changer ENTRE la revue du plan de controle et la finalisation,
# et la finalisation gravera la valeur changee comme « approuvee ».
#
# Le plan de controle ne presente RIEN: il ne dit pas ce qu'il a revu. Rien
# n'est donc compare, et « approuve » ne veut dire que « courant a l'instant
# ou la fonction a tourne ».
#
# QUI PEUT POSER CES DECLARATIONS — mesure, PostgreSQL 16:
#   * proprietaire non superutilisateur de la base, sans autre droit
#         -> ERROR: permission denied to set parameter "eurostruct.token_roles"
#   * apres `GRANT SET ON PARAMETER ... TO <role>`   -> accepte
#   * `SET` de session, par n'importe qui           -> accepte, mais invisible
#     de `pg_db_role_setting`, donc sans effet ici (deja ferme en 6.3b6a)
#
# Le decor accorde donc explicitement `SET ON PARAMETER` au migrateur. Ce n'est
# pas une facilite: un installeur qui pose lui-meme ses trois declarations —
# la forme la plus naturelle d'un script de deploiement — doit le detenir. Le
# modele ne l'interdit nulle part, et la finalisation ne le regarde pas.
#
# Le defaut ne depend d'ailleurs pas de QUI change la valeur: le plan de
# controle ne presente aucun manifeste, donc AUCUN changement survenu entre la
# revue et la finalisation ne peut etre detecte, par qui que ce soit.
if ! decor_poser 3 separe; then
  echoue "le decor 3 n'a pas pu etre pose: le point 1 n'est pas evalue"
else
suivre_decor
adm -c "grant set on parameter \"eurostruct.token_roles\" to \"$MIG\";" >/dev/null 2>&1
# LA DECLARATION EST LUE DANS LE CATALOGUE, PAS PAR LA FONCTION.
# `normative_declared_setting()` n'est executable que par l'activateur: la lire
# sous le plan de controle rendrait « permission denied » AVANT et APRES, donc
# deux valeurs egales — et le scenario se serait cru non reproductible alors
# que le changement avait bien eu lieu (mesure).
lire_declaration() {
  adm -tAc "select coalesce((select split_part(o, '=', 2)
              from pg_db_role_setting s cross join unnest(s.setconfig) as o
             where s.setdatabase = (select oid from pg_database where datname = '$BASE')
               and s.setrole = 0
               and split_part(o, '=', 1) = 'eurostruct.token_roles' limit 1), '')" 2>&1
}
AVANT_REVUE=$(lire_declaration)
# LA REVUE. Le plan de controle lit le manifeste des declarations et le note.
MANIFESTE_REVU=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
# LE MIGRATEUR CHANGE LA DECLARATION APRES LA REVUE.
CHANGEMENT=$(mig_pg -c "alter database \"$BASE\"
                          set eurostruct.token_roles =
                              'authenticated,anon,FICTIF_ajoute_apres_revue';" 2>&1)
APRES=$(lire_declaration)

if [[ "$AVANT_REVUE" == "$APRES" ]]; then
  echoue "1. la declaration n'a pas pu etre modifiee par le migrateur:"
  echoue "   $(head -1 <<<"$CHANGEMENT" | cut -c1-140)"
  echoue "   Le scenario ne reproduit pas le contre-exemple vise."
else
  # LA FINALISATION EST DEMANDEE AVEC LE MANIFESTE REVU, et non avec l'etat
  # courant: c'est exactement ce qu'un plan de controle honnete presente.
  SORTIE=$(ctl -v esc_v="$MANIFESTE_REVU" -tAc "select normative_finalize_deployment(:'esc_v')" 2>&1)
  ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)
  # La valeur FIGEE est lue dans la table, sous un role qui contourne la RLS.
  FIGE=$(admb -tAc "select valeur from normative_approved_settings
                     where nom = 'eurostruct.token_roles'" 2>&1)
  if grep -qiE "manifeste|approbation|digest attendu|ne correspond|non approuve" <<<"$SORTIE"; then
    # ET RIEN N'A ETE ECRIT: un refus qui laisserait le plan de controle ou les
    # declarations figes aurait consomme le singleton, et la finalisation
    # correcte serait devenue impossible.
    ECRIT=$(admb -tAc "select (select count(*) from normative_control_plane)
                            + (select count(*) from normative_approved_settings)
                            + (select count(*) from normative_finalization_intent)" 2>&1)
    if [[ "$ECRIT" == "0" ]]; then
      echo "      ok: 1. finalisation refusee — declaration modifiee apres revue,"
      echo "             et rien n'a ete fige"
    else
      rouge "1. la finalisation refuse, mais a deja fige $ECRIT ligne(s) de"
      rouge "   confiance: le singleton est consomme et une finalisation"
      rouge "   correcte deviendrait impossible."
    fi
  elif [[ "$ETAT" == "ACTIVE" ]]; then
    rouge "1. LA FINALISATION A FIGE UNE DECLARATION MODIFIEE APRES REVUE."
    rouge "   revu par le plan de controle : « $AVANT_REVUE »"
    rouge "   fige comme approuve          : « $FIGE »"
    rouge "   Le plan de controle n'a rien presente, donc rien n'a ete compare:"
    rouge "   « approuve » ne signifie que « courant au moment de l'appel »."
  else
    rouge "1. finalisation refusee, mais pas au motif de l'approbation:"
    rouge "   $(grep -m1 -iE 'ERROR|ERREUR' <<<"$SORTIE" | cut -c1-140)"
  fi
fi
esc_decor_fermer
fi

# ==========================================================================
# DECOR 4 — point 4 (finalisations concurrentes) puis point 3 (identite).
# ==========================================================================
# Le point 4 laisse le sous-systeme ACTIVE: le point 3, qui porte sur ce qui a
# ete FIGE, s'exerce ensuite sur ce meme decor.
if ! decor_poser 4 separe; then
  echoue "le decor 4 n'a pas pu etre pose: les points 4 et 3 ne sont pas evalues"
else
suivre_decor

# --------------------------------------------------------------------------
# 4. DEUX FINALISATIONS CONCURRENTES, PAR DEUX CONNEXIONS REELLES
# --------------------------------------------------------------------------
# `normative_finalize_deployment` ne prend aucun verrou. Deux appels simultanes
# lisent tous deux PENDING, revoquent tous deux, et tentent tous deux
# d'inserer. Ce que le contrat exige: UNE SEULE transition, et pour l'autre un
# resultat IDEMPOTENT — « ACTIVE » — et non une erreur brute.
#
# Deux vraies connexions, et un recouvrement force: A tient sa transaction
# ouverte pendant que B entre. Pas de sequence deguisee en concurrence.
MANIFESTE=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
SORTIE_A="$(mktemp -p "${TMPDIR:-/tmp}" fc4a.XXXXXX)"
SORTIE_B="$(mktemp -p "${TMPDIR:-/tmp}" fc4b.XXXXXX)"
(
  PGUSER="$CTL" PGPASSWORD="$CTL_MDP" psql -X -v esc_v="$MANIFESTE" -q -d "$BASE" -tA >"$SORTIE_A" 2>&1 <<SQL
begin;
select 'A:' || normative_finalize_deployment(:'esc_v');
select pg_sleep(3);
commit;
SQL
) &
PID_A=$!
# A DOIT ETRE ENTREE DANS LA FINALISATION AVANT QUE B COMMENCE.
#
# Attendre `xact_start is not null` ne suffit pas: c'est vrai des le `begin`,
# et B pouvait alors entrer avant que A ait rien fait. On attend donc que A
# soit dans son `pg_sleep` — c'est-a-dire APRES avoir execute la finalisation
# et AVANT d'avoir valide. C'est la seule fenetre ou la concurrence porte sur
# quelque chose.
DANS_LA_FENETRE=0
for _ in $(seq 1 200); do
  if [[ "$(adm -tAc "select count(*) from pg_stat_activity
                      where datname = '$BASE' and usename = '$CTL'
                        and xact_start is not null
                        and query like '%pg_sleep%'")" == "1" ]]; then
    DANS_LA_FENETRE=1; break
  fi
  kill -0 "$PID_A" 2>/dev/null || break
  sleep 0.05
done
(
  PGUSER="$CTL" PGPASSWORD="$CTL_MDP" psql -X -v esc_v="$MANIFESTE" -q -d "$BASE" -tA >"$SORTIE_B" 2>&1 <<SQL
begin;
select 'B:' || normative_finalize_deployment(:'esc_v');
commit;
SQL
) &
PID_B=$!
# ET LES DEUX TRANSACTIONS DOIVENT AVOIR ETE OUVERTES EN MEME TEMPS. Sans ce
# constat, une execution SEQUENTIELLE — B apres le commit de A — passerait pour
# une concurrence et rendrait un vert qui ne prouve rien.
RECOUVREMENT=0
for _ in $(seq 1 200); do
  if [[ "$(adm -tAc "select count(*) from pg_stat_activity
                      where datname = '$BASE' and usename = '$CTL'
                        and xact_start is not null")" -ge 2 ]]; then
    RECOUVREMENT=1; break
  fi
  kill -0 "$PID_B" 2>/dev/null || break
  sleep 0.05
done
wait $PID_A; wait $PID_B
# LA LIGNE QUI COMPTE EST L'ERREUR, pas les avertissements qui la precedent.
# Un `REVOKE` sans effet emet un WARNING par role, et ces trois lignes
# occupaient tout l'extrait — masquant le diagnostic reel.
resume() {
  local f="$1" r
  r=$(grep -m1 -E '^(ERROR|ERREUR|FATAL)' "$f")
  [[ -n "$r" ]] || r=$(grep -m1 -E '^[AB]:' "$f")
  [[ -n "$r" ]] || r=$(tr '\n' ' ' <"$f")
  cut -c1-170 <<<"$r"
}
RES_A="$(resume "$SORTIE_A")"
RES_B="$(resume "$SORTIE_B")"
B_BRUT="$(tr '\n' ' ' <"$SORTIE_B")"
rm -f "$SORTIE_A" "$SORTIE_B"
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)

if [[ "$DANS_LA_FENETRE" != "1" || "$RECOUVREMENT" != "1" ]]; then
  echoue "4. le recouvrement n'est pas etabli (A dans la fenetre: $DANS_LA_FENETRE,"
  echoue "   deux transactions ouvertes ensemble: $RECOUVREMENT). Une execution"
  echoue "   sequentielle passerait pour une concurrence: le scenario ne"
  echoue "   prouverait rien. A: $RES_A | B: $RES_B"
elif [[ "$ETAT" != "ACTIVE" ]]; then
  rouge "4. apres deux finalisations concurrentes, l'etat n'est pas ACTIVE:"
  rouge "   etat = $ETAT | A: $RES_A | B: $RES_B"
elif grep -qE "B:ACTIVE" <<<"$B_BRUT"; then
  echo "      ok: 4. recouvrement constate; une seule transition, l'autre obtient"
  echo "             un resultat idempotent — A: $RES_A / B: $RES_B"
else
  rouge "4. LE PERDANT N'OBTIENT PAS UN RESULTAT IDEMPOTENT."
  rouge "   gagnant : $RES_A"
  rouge "   perdant : $RES_B"
  rouge "   Le contrat exige que le second attende puis constate ACTIVE."
  rouge "   Aucun verrou ne serialise la transition: les deux appels lisent"
  rouge "   PENDING, revoquent, et se disputent l'insertion."
fi

# --------------------------------------------------------------------------
# 3. L'IDENTITE DU PLAN DE CONTROLE N'EST QU'UN NOM
# --------------------------------------------------------------------------
# `normative_control_plane` ne stocke que `role_name`. Le digest d'audit ne
# contient ni ce nom ni l'OID. Or l'exemption d'ADMIN residuel — la seule
# exemption du modele — est accordee PAR NOM.
#
# Un nom n'est pas une identite: il se libere et se reprend. Apres substitution,
# `normative_control_plane()` designe un role qui n'a jamais rien approuve, et
# la topologie l'accepte parce qu'il porte le bon libelle.
if [[ "$(ctl -tAc "select normative_activation_state()" 2>&1)" != "ACTIVE" ]]; then
  echoue "3. le sous-systeme n'est pas ACTIVE: le point 3 porte sur ce qui a"
  echoue "   ete fige, il n'est pas evaluable ici."
else
  COL=$(admb -tAc "select count(*) from information_schema.columns
                    where table_name = 'normative_control_plane'
                      and column_name = 'role_oid'" 2>&1)
  PLAN_AVANT=$(ctl -tAc "select normative_control_plane()" 2>&1)
  OID_AVANT=$(adm -tAc "select oid from pg_roles where rolname = '$PLAN_AVANT'" 2>&1)

  # LA SUBSTITUTION — mise en scene d'un DECOMMISSIONNEMENT, la forme la plus
  # banale du probleme: le role qui a approuve est retire du service, et son
  # nom — un nom d'exploitation, pas un secret — est repris plus tard.
  #
  #   1. le plan approuve est renomme et perd toutes ses appartenances: il
  #      n'exerce plus rien, comme un role reellement retire;
  #   2. un role NEUF est cree sous le nom approuve et recoit l'ADMIN residuel
  #      exactement dans sa forme canonique (admin=t, set=f, usage=f — mesure
  #      PostgreSQL 16 de `with admin option, set false, inherit false`).
  #
  # L'operation demande un administrateur. C'est le point, et non une faiblesse
  # du scenario: l'enregistrement de confiance doit permettre de CONSTATER la
  # substitution apres coup, quel que soit celui qui l'opere. Il ne le permet
  # pas — il ne contient qu'un nom.
  SUBST="${PREFIXE}_x4_${JETON}"
  SUBST_MDP="FICTIF-substitut-$JETON"
  TOUS_ROLES+=("$SUBST")
  adm -c "alter role \"$PLAN_AVANT\" rename to \"$SUBST\";" >/dev/null 2>&1
  # RETIRE DU SERVICE, ENTIEREMENT. Les six appartenances ET les attributs
  # privileges: sans cela, l'ancien plan reste CREATEROLE et garde l'ADMIN
  # residuel sur les roles de SERVICE qu'il a crees (fait F1), et le bloc B de
  # la topologie refuserait a cause de LUI — un refus qui ne dirait rien de la
  # substitution (mesure: « le role privilegie « ..._x4_... » atteint le
  # service « normative_backend » »).
  adm -c "revoke ${CANONIQUES[0]}, ${CANONIQUES[1]}, ${CANONIQUES[2]},
                 ${CANONIQUES[3]}, ${CANONIQUES[4]}, ${CANONIQUES[5]}
          from \"$SUBST\";" >/dev/null 2>&1
  adm -c "alter role \"$SUBST\" nologin nocreaterole nocreatedb;" >/dev/null 2>&1
  adm -c "create role \"$PLAN_AVANT\" login password '$SUBST_MDP';" >/dev/null 2>&1
  TOUS_ROLES+=("$PLAN_AVANT")
  adm -c "grant eurostruct_normative_writer, eurostruct_normative_bootstrap,
                eurostruct_normative_activator to \"$PLAN_AVANT\"
          with admin option, set false, inherit false;" >/dev/null 2>&1
  adm -c "grant eurostruct_deployment to \"$PLAN_AVANT\";" >/dev/null 2>&1
  OID_APRES=$(adm -tAc "select oid from pg_roles where rolname = '$PLAN_AVANT'" 2>&1)
  ANCIEN_TIENT=$(adm -tAc "select count(*) from unnest(array[
                      '${CANONIQUES[0]}','${CANONIQUES[1]}','${CANONIQUES[2]}',
                      '${CANONIQUES[3]}','${CANONIQUES[4]}','${CANONIQUES[5]}']) a(r)
                   where pg_has_role('$SUBST', a.r, 'SET')
                      or pg_has_role('$SUBST', a.r, 'USAGE')
                      or pg_has_role('$SUBST', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
  TOPO=$(PGUSER="$PLAN_AVANT" PGPASSWORD="$SUBST_MDP" \
         psql -X -q -d "$BASE" -tAc "select assert_normative_topology()" 2>&1)

  if [[ "$ANCIEN_TIENT" != "0" ]]; then
    echoue "3. le plan approuve conserve $ANCIEN_TIENT capacite(s) apres retrait:"
    echoue "   un refus de topologie viendrait de LUI et non de la substitution."
  elif [[ "$COL" != "0" ]] && grep -qiE "oid|substitu|identite" <<<"$TOPO"; then
    echo "      ok: 3. le plan de controle est identifie par oid ET par nom"
  elif grep -qiE "ERROR|ERREUR" <<<"$TOPO"; then
    rouge "3. la topologie refuse, mais pas au motif de l'identite substituee:"
    rouge "   $(grep -m1 -iE 'ERROR|ERREUR' <<<"$TOPO" | cut -c1-140)"
    rouge "   colonne role_oid dans normative_control_plane : $COL"
  else
    rouge "3. LE PLAN DE CONTROLE N'EST IDENTIFIE QUE PAR SON NOM."
    rouge "   colonne role_oid dans normative_control_plane : $COL"
    rouge "   oid approuve a la finalisation                : $OID_AVANT"
    rouge "   oid portant ce nom maintenant                 : $OID_APRES"
    rouge "   LA TOPOLOGIE ACCEPTE le role substitue: un role cree APRES"
    rouge "   l'activation herite de l'exemption d'ADMIN residuel — la seule du"
    rouge "   modele — sans avoir jamais rien approuve."
    rouge "   Le digest d'audit ne porte ni le nom ni l'oid du plan: rien ne"
    rouge "   permet de constater la substitution apres coup."
  fi
fi
esc_decor_fermer
fi

# ==========================================================================
# DECOR 5 — point 8a: deux roles distincts, sur decor ENTIEREMENT VIERGE.
# ==========================================================================
# Le scenario normal doit ABOUTIR, et le prouver sur un decor qui ne doit rien
# a l'ordre d'execution: roles canoniques absents au depart, base neuve,
# provisionnement par le plan de controle, migration par le migrateur.
if ! decor_poser 5 separe; then
  echoue "le decor 5 n'a pas pu etre pose: le point 8a n'est pas evalue"
else
suivre_decor
MANIFESTE=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
SORTIE=$(ctl -v esc_v="$MANIFESTE" -tAc "select normative_finalize_deployment(:'esc_v')" 2>&1)
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)
RESTE=$(adm -tAc "select count(*) from unnest(array['eurostruct_normative_writer',
                    'eurostruct_normative_bootstrap','eurostruct_normative_activator']) a(r)
                   where pg_has_role('$MIG', a.r, 'SET')
                      or pg_has_role('$MIG', a.r, 'USAGE')
                      or pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
if [[ "$ETAT" == "ACTIVE" && "$RESTE" == "0" ]]; then
  echo "      ok: 8a. decor vierge, deux roles distincts — finalisation acceptee"
else
  rouge "8a. sur decor VIERGE, la finalisation par deux roles distincts n'aboutit"
  rouge "    pas: etat = $ETAT, capacites residuelles du migrateur = $RESTE"
  rouge "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$SORTIE" | cut -c1-140)"
fi
esc_decor_fermer
fi

# ==========================================================================
# DECOR 6 — point 8b: un seul role, sur decor ENTIEREMENT VIERGE.
# ==========================================================================
# Greenfield: le migrateur cree lui-meme les roles d'autorite, PostgreSQL lui
# en donne l'ADMIN residuel (fait F1), et il serait donc son propre plan de
# controle. La finalisation doit refuser POUR CE MOTIF — nomme —, pas pour un
# autre.
if ! decor_poser 6 greenfield; then
  echoue "le decor 6 n'a pas pu etre pose: le point 8b n'est pas evalue"
else
suivre_decor
MANIFESTE=$(mig -tAc "select normative_settings_manifest()" 2>&1)
SORTIE=$(mig -v esc_v="$MANIFESTE" -tAc "select normative_finalize_deployment(:'esc_v')" 2>&1)
ETAT=$(mig -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT" == "ACTIVE" ]]; then
  rouge "8b. UN SEUL ROLE A PU FINALISER: le migrateur est son propre plan de"
  rouge "    controle, garde l'ADMIN residuel par exemption, et peut se"
  rouge "    reaccorder SET quand il veut. La separation est nominale."
elif grep -qiE "deux roles DISTINCTS|le meme role|plan de controle derive" <<<"$SORTIE"; then
  echo "      ok: 8b. decor vierge, role unique — refus au motif de la separation"
else
  rouge "8b. le refus n'est pas motive par la separation plan/migrateur:"
  rouge "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$SORTIE" | cut -c1-160)"
fi
esc_decor_fermer
fi

# ==========================================================================
# 7. LE ROLE ACTIVATOR DANS LES HARNAIS — cinq temoins doivent devenir six
# ==========================================================================
# `eurostruct_normative_activator` est un role canonique depuis 6.3b6b: les
# migrations le CREENT, il est GLOBAL au cluster, et il survit a la destruction
# de la base. Les listes canoniques des harnais en comptent cinq.
#
# Consequence mesuree sur ce cluster avant l'ecriture de ce fichier: le role
# etait present en residu d'une execution anterieure, et aucune postcondition
# ne l'avait signale. Un jeu canonique incomplet rend « aucun role residuel »
# faux, et rend `exiger_roles_absents` aveugle a un decor deja pollue.
#
# Cette verification porte sur le DEPOT: elle ne depend d'aucune base.
MANQUANTS=()
for f in run.sh harness_safety_selftest.sh nonsuperuser_install.sh \
         role_prerequisites.sh two_phase_deployment.sh; do
  awk '/^(CANONIQUES|AUTORITES)=/,/\)|"$/' "$HERE/$f" \
    | grep -q 'eurostruct_normative_activator' || MANQUANTS+=("$f")
done
# `harness_safety_selftest.sh` compte ses temoins: cinq roles canoniques poses,
# cinq attendus intacts. Avec six roles, le compte doit etre six.
TEMOINS_CINQ=0
grep -qE '\[\[ "\$n" == "5" \]\]' "$HERE/harness_safety_selftest.sh" && TEMOINS_CINQ=1

if [[ ${#MANQUANTS[@]} -eq 0 && $TEMOINS_CINQ -eq 0 ]]; then
  echo "      ok: 7. les six roles canoniques sont declares dans les harnais"
else
  rouge "7. LE JEU CANONIQUE DES HARNAIS EST INCOMPLET."
  [[ ${#MANQUANTS[@]} -gt 0 ]] && \
    rouge "   « eurostruct_normative_activator » absent de: ${MANQUANTS[*]}"
  [[ $TEMOINS_CINQ -eq 1 ]] && \
    rouge "   harness_safety_selftest.sh attend encore 5 temoins, pas 6"
  rouge "   Un role canonique non declare survit a chaque execution sans etre"
  rouge "   vu par aucune postcondition, et rend « aucun role residuel » faux."
fi

echo ""
echo "================================================="
if [[ $KO -eq 0 && $ROUGES -eq 0 ]]; then
  echo " Contrat de finalisation: aucun contournement."
  echo "================================================="
  exit 0
fi
echo " Contrat de finalisation:"
echo "   $KO ecart(s) de decor"
echo "   $ROUGES contournement(s) ouvert(s), a fermer"
echo "================================================="
exit 1
