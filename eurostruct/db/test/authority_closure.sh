#!/usr/bin/env bash
#
# EUROSTRUCT — 6.3b6c: LA FERMETURE DE L'AUTORITE
#
#   authority_closure.sh <prefixe-de-base-jetable>
#
# CE QUE CE FICHIER EXISTE POUR ETABLIR
# --------------------------------------
# `finalisation_contract.sh` prouve que la PHASE 2 ne peut pas etre contournee.
# Il ne dit rien de ce qui se passe A COTE d'elle: pendant la phase 1, et apres
# l'activation, par un chemin qui ne passe jamais par la finalisation.
#
# Ce fichier pose la question qu'une CI verte ne peut pas trancher: le migrateur
# est-il CONTENU ? Il est reponse par l'experience, sept fois.
#
# LE MODELE DE MENACE, explicite
# -------------------------------
#   * les roles APPLICATIFS (`authenticated`, `normative_backend`, ...) ne sont
#     pas fiables;
#   * le MIGRATEUR n'est pas fiable POUR L'APPROBATION NORMATIVE. Il est fiable
#     pour appliquer un schema — c'est son role — et pour rien d'autre;
#   * le PLAN DE CONTROLE est fiable: c'est lui qui approuve;
#   * le SUPERUTILISATEUR est hors modele. Il peut tout, et pretendre le
#     contenir donnerait une fausse assurance.
#
# La question de ce fichier est donc: le migrateur, non fiable pour approuver,
# peut-il neanmoins produire ACTIVE, ecrire une confirmation, ou effacer une
# preuve ? La reponse mesuree sur fc13990 est OUI aux trois.
#
# CE QUI EST EXERCE
# ------------------
#   A. PENDING — le migrateur ENDOSSE l'activateur et active lui-meme
#   B. ACTIVE  — le migrateur POSSEDE les tables et efface une preuve
#   C. les helpers publics se COMPOSENT en plusieurs transactions
#   D. l'idempotence accepte N'IMPORTE QUEL manifeste
#   E. les exemptions de service comparent le NOM SEUL
#   F. le contrat du `topology_digest` n'est pas tranche
#   G. la restauration inter-cluster n'a aucun diagnostic
#
# Toutes les identites sont FICTIVES. Aucune confirmation normative reelle
# n'est creee: celles qui le sont servent a prouver qu'on peut les DETRUIRE.
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

PREFIXE="${1:?usage: authority_closure.sh <prefixe-de-base-jetable>}"

harnais_connexion || exit 2
exiger_precontrole_local "authority_closure.sh" || exit 2
harnais_verrou_prendre  "authority_closure.sh" || exit $?
exiger_cluster_jetable  "authority_closure.sh" || exit 2
harnais_valider_identifiant "prefixe" "$PREFIXE" || exit 2

JETON="$(harnais_jeton)"

CANONIQUES=(eurostruct_normative_writer eurostruct_normative_bootstrap
            eurostruct_normative_activator normative_backend
            normative_governance eurostruct_deployment
            eurostruct_authority_backend)
AUTORITES=(eurostruct_normative_writer eurostruct_normative_bootstrap
           eurostruct_normative_activator)

exiger_roles_absents "authority_closure.sh" "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" || exit 2

KO=0; ROUGES=0
echoue() { echo "      ECHEC: $*" >&2; KO=1; }
rouge()  { echo "      ROUGE: $*"; ROUGES=$((ROUGES + 1)); }

adm() { psql -X -q -d postgres "$@"; }

# --------------------------------------------------------------------------
# LE DECOR
# --------------------------------------------------------------------------
# Trois acteurs, aucun superutilisateur — la forme Supabase:
#   <p>_m<s>  migrateur       proprietaire de la base, CREATEROLE, CREATEDB
#   <p>_c<s>  plan de controle provisionne les roles d'autorite, finalise
#   <p>_s<s>  role de service  ecrit les confirmations, declare approuve
MIG=""; CTL=""; SVC=""; BASE=""; MDP=""
mig()  { PGUSER="$MIG" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctl()  { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
svc()  { PGUSER="$SVC" PGPASSWORD="$MDP" psql -X -q -d "$BASE" "$@"; }
ctlp() { PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -d postgres "$@"; }
admb() { psql -X -q -d "$BASE" "$@"; }

# LES SUFFIXES SONT EN MINUSCULES, et ce n'est pas un detail de style.
# PostgreSQL replie les identifiants non quotes: `create role pAmig` cree
# `pamig`, et une connexion `PGUSER=pAmig` echoue alors sur « role does not
# exist ». Mesure faite en ecrivant ce fichier: la phase 1 se refusait sur
# « role eurostruct_deployment does not exist », un diagnostic qui n'avait
# aucun rapport avec la cause.
decor_poser() {
  local s="$1" f sortie
  MIG="${PREFIXE}_m${s}_${JETON}"
  CTL="${PREFIXE}_c${s}_${JETON}"
  SVC="${PREFIXE}_s${s}_${JETON}"
  BASE="${PREFIXE}_d${s}_${JETON}"
  MDP="FICTIF-ac-${s}-${JETON}"

  creer_role "$MIG" "login password '$MDP' createrole createdb" \
    || { echoue "decor $s: creation du migrateur impossible"; return 1; }
  creer_role "$CTL" "login password '$MDP' createrole" \
    || { echoue "decor $s: creation du plan de controle impossible"; return 1; }
  creer_role "$SVC" "login password '$MDP'" \
    || { echoue "decor $s: creation du role de service impossible"; return 1; }
  adm -c "grant \"$CTL\" to ${PGUSER:-postgres};" >/dev/null 2>&1

  creer_base "$BASE" "owner \"$MIG\"" \
    || { echoue "decor $s: creation de la base impossible"; return 1; }
  registre_base "$BASE"

  admb -v ON_ERROR_STOP=1 -f "$HERE/00_supabase_stub.sql" >/dev/null 2>&1
  admb >/dev/null 2>&1 <<SQL
grant usage on schema auth to "$MIG" with grant option;
grant select, insert, references on auth.users to "$MIG" with grant option;
grant execute on function auth.uid() to "$MIG" with grant option;
grant create on database "$BASE" to "$MIG";
-- LE PLAN DE CONTROLE CREE LES OBJETS DE LA PHASE 0. Il lui faut donc CREATE
-- sur `public`, et l'option de le retransmettre a l'activateur qui deviendra
-- proprietaire de ces objets. C'est un prerequis de deploiement, pose par la
-- plateforme — voir docs/DEPLOIEMENT_PREREQUIS.md.
grant create on schema public to "$CTL" with grant option;
grant usage on schema auth to "$CTL";
SQL

  # PHASE 0 — LE SCEAU, POSE PAR LE PLAN DE CONTROLE.
  # C'est elle qui cree les six roles canoniques ET la racine de confiance.
  # Le migrateur n'y participe pas: c'est tout l'objet de 6.3b6c.
  if ! sortie=$(ctl -v ON_ERROR_STOP=1 -f "$HARNAIS_SCEAU" 2>&1); then
    echoue "decor $s: phase 0 refusee:"
    grep -m1 ERROR <<<"$sortie" | cut -c1-200 | sed 's/^/              /' >&2
    return 1
  fi
  adm -c "grant eurostruct_deployment to \"$CTL\" with inherit true;" >/dev/null 2>&1
  # L'EMPRUNT: DEUX ROLES, jamais l'activateur. Accorde par le plan de
  # controle, qui est donc le donneur (fait F3) et le seul a pouvoir revoquer.
  ctlp -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
grant eurostruct_normative_writer    to "$MIG" with admin option;
grant eurostruct_normative_bootstrap to "$MIG" with admin option;
SQL
  # LES TROIS DECLARATIONS, POSEES AVANT LA FINALISATION qui les fige.
  adm -c "alter database \"$BASE\"
            set eurostruct.approved_deployment_roles = '$MIG,$CTL';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\" set eurostruct.token_roles = 'authenticated';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\"
            set eurostruct.approved_service_logins = '$SVC';" >/dev/null 2>&1
  # LES DEUX DE 6.3c, ICI AUSSI. Sans elles le sous-systeme d'autorite reste
  # ferme — c'est le fail-closed voulu — et le decor B ne peut fabriquer
  # aucune preuve VRAIE a detruire.
  adm -c "alter database \"$BASE\"
            set eurostruct.authority_backend_logins = '$SVC';" >/dev/null 2>&1
  adm -c "alter database \"$BASE\"
            set eurostruct.bootstrap_mandate =
              'b0000000-0000-0000-0000-0000000000b1:FICTIF-EMPREINTE-CLOSURE';" \
    >/dev/null 2>&1

  # PHASE 1 — par le migrateur, et sans 0000 qui appartient a la phase 0.
  for f in "$DB_DIR"/migrations/*.sql; do
    if ! esc_appliquer_migration "$f" mig; then
      sortie="$ESC_MIGRATION_SORTIE"
      echoue "decor $s: phase 1 refusee sur $(basename "$f"):"
      grep -m1 ERROR <<<"$sortie" | cut -c1-200 | sed 's/^/              /' >&2
      return 1
    fi
  done
  local etat
  etat=$(ctl -tAc "select normative_activation_state()" 2>&1)
  if [[ "$etat" != "PENDING" ]]; then
    echoue "decor $s: phase 1 ne se termine pas en PENDING (obtenu: $etat)"
    return 1
  fi
  return 0
}

# `decor_finaliser` — phase 2 par le plan de controle. Rend 1 si elle echoue.
decor_finaliser() {
  local m sortie
  m=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
  sortie=$(ctl -tAc "select normative_finalize_deployment('$m')" 2>&1)
  if [[ "$(ctl -tAc "select normative_activation_state()" 2>&1)" != "ACTIVE" ]]; then
    echoue "la finalisation a echoue: $(grep -m1 -iE 'ERROR|ERREUR' <<<"$sortie" | cut -c1-160)"
    return 1
  fi
  return 0
}

decor_deposer() {
  local r
  adm -c "select pg_terminate_backend(pid) from pg_stat_activity
           where datname = '$BASE' and pid <> pg_backend_pid();" >/dev/null 2>&1
  detruire_bases_creees || NETTOYAGE_KO=1
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "$MIG" "$CTL" "$SVC"; do
    [[ -n "$r" ]] || continue
    adm -c "drop owned by \"$r\";"       >/dev/null 2>&1
    adm -c "drop role if exists \"$r\";" >/dev/null 2>&1
  done
}

NETTOYAGE_KO=0
TOUS_ROLES=()
suivre_decor() { TOUS_ROLES+=("$MIG" "$CTL" "$SVC"); }
sortie_propre() {
  local r
  decor_deposer
  for r in "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}"; do
    registre_role "$r"
  done
  detruire_roles_crees || NETTOYAGE_KO=1
  harnais_postcondition_nettoyage "authority_closure.sh" \
    "${CANONIQUES[@]}" "${HARNAIS_ROLES_STUB[@]}" "${TOUS_ROLES[@]}" || NETTOYAGE_KO=1
  harnais_verrou_rendre
  [[ $NETTOYAGE_KO -eq 0 ]] || exit 3
}
trap sortie_propre EXIT
harnais_piege_signaux

echo "    fermeture de l'autorite: le migrateur est-il contenu ?"

# ==========================================================================
# A. PENDING — LE MIGRATEUR ENDOSSE L'ACTIVATEUR
# ==========================================================================
# Pendant la phase 1, le migrateur DOIT pouvoir endosser les roles d'autorite:
# c'est ainsi qu'il transfere la propriete des fonctions, et c'est ce que
# `normative_prepare_activation()` cherche ensuite dans `pg_auth_members`.
#
# Or `normative_activation` appartient a `eurostruct_normative_activator`, et
# sa policy d'ecriture autorise CE ROLE. Un `SET ROLE` suffit donc a devenir
# l'auteur legitime de l'ecriture la plus engageante du systeme.
#
# LE CORRECTIF NE PEUT PAS ETRE UN DECLENCHEUR VERIFIANT
# `current_user = activator`: apres `SET ROLE`, cette condition est exactement
# satisfaite. C'est la RACINE qui doit etre hors de portee, pas la condition.
if ! decor_poser a; then
  echoue "le decor A n'a pas pu etre pose: le scenario A n'est pas evalue"
else
suivre_decor
echo "      ok: decor A — phase 1 appliquee par « $MIG », etat PENDING"

# --- A1. la portee, constatee ---------------------------------------------
PORTEE=$(mig -tAc "select pg_has_role(current_user,'eurostruct_normative_activator','SET')::text
                       || '/' || pg_has_role(current_user,'eurostruct_normative_activator','USAGE')::text" 2>&1)
A_OUVERT=0
if [[ "$PORTEE" == "false/false" ]]; then
  echo "      ok: A1. le migrateur n'atteint pas l'activateur (SET/USAGE = $PORTEE)"
else
  rouge "A1. le migrateur atteint l'activateur pendant PENDING (SET/USAGE = $PORTEE)."
  rouge "    La phase 1 en a besoin pour transferer la propriete des fonctions;"
  rouge "    la question n'est donc pas de le lui retirer, mais que la racine de"
  rouge "    confiance ne soit pas ce role-la."
  A_OUVERT=1
fi

# --- A2. ecriture directe dans les quatre tables de confiance --------------
# `set local role` dans une transaction: on veut savoir si l'ECRITURE passe,
# pas laisser le decor dans un etat endosse.
ECRITES=""
for t in normative_control_plane normative_approved_settings normative_finalization_intent; do
  case "$t" in
    normative_control_plane)
      COLS="(role_oid, role_name, recorded_by)"
      VALS="(0, 'FICTIF_plan_forge', session_user)" ;;
    normative_approved_settings)
      COLS="(nom, valeur, fige_par)"
      VALS="('eurostruct.token_roles', 'FICTIF_forge', session_user)" ;;
    normative_finalization_intent)
      COLS="(migrateur_oid, migrateur_nom, donneur_oid, donneur_nom, manifeste, prepare_par)"
      VALS="(1, 'FICTIF_mig', 2, 'FICTIF_plan', 'FICTIF', session_user)" ;;
  esac
  S=$(mig -tAc "begin; set local role eurostruct_normative_activator;
                insert into $t $COLS values $VALS; commit;" 2>&1)
  grep -qiE "ERROR|ERREUR" <<<"$S" || ECRITES="${ECRITES:+$ECRITES, }$t"
done
if [[ -z "$ECRITES" ]]; then
  echo "      ok: A2. aucune ecriture directe dans les tables de confiance"
else
  rouge "A2. le migrateur ECRIT directement, apres SET ROLE, dans: $ECRITES"
  A_OUVERT=1
fi

# --- A3. la fausse activation ---------------------------------------------
FAUSSE=$(mig -tAc "begin; set local role eurostruct_normative_activator;
                   insert into normative_activation (activated_by, topology_digest)
                   values (session_user, repeat('0', 64)); commit;" 2>&1)
ETAT=$(mig -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ok: A3. la fausse activation est refusee (etat: $ETAT)"
else
  rouge "A3. UNE FAUSSE LIGNE D'ACTIVATION FAIT PASSER L'ETAT A « ACTIVE »."
  rouge "    Aucune finalisation n'a eu lieu, aucun manifeste n'a ete presente,"
  rouge "    aucun emprunt n'a ete restitue, et le digest est invente."
  A_OUVERT=1

  # --- A4. une ecriture normative devient possible -------------------------
  admb >/dev/null 2>&1 <<'SQL'
insert into auth.users (id, email) values
  ('a0000000-0000-0000-0000-0000000000a1', 'FICTIF-ac-a1@eurostruct.test')
on conflict do nothing;
SQL
  AMORCE=$(mig -tAc "select bootstrap_normative_administrator(
             'a0000000-0000-0000-0000-0000000000a1', 'FICTIF Racine',
             'FICTIF — amorcage apres fausse activation.')" 2>&1)
  if grep -qE '^[0-9a-f-]{36}$' <<<"$(tail -1 <<<"$AMORCE")"; then
    rouge "A4. UNE ECRITURE NORMATIVE EST ACCEPTEE sans finalisation: l'amorcage"
    rouge "    a inscrit l'octroi $(tail -1 <<<"$AMORCE")."
    rouge "    Les quatre declencheurs de 6.3b6b ne regardent que l'ETAT, et"
    rouge "    l'etat vient d'etre fabrique."
  else
    echo "      ok: A4. l'ecriture normative reste refusee malgre l'etat force"
  fi

  # --- A5. la topologie refuse, mais apres ---------------------------------
  TOPO=$(mig -tAc "select assert_normative_topology()" 2>&1)
  LIGNES=$(admb -tAc "select (select count(*) from normative_activation)::text || '/' ||
                             (select count(*) from normative_authorisation_grants)::text" 2>&1)
  if grep -qiE "ERROR|ERREUR" <<<"$TOPO"; then
    rouge "A5. assert_normative_topology() refuse — MAIS TROP TARD: l'etat est"
    rouge "    deja ACTIVE et les ecritures sont deja la (activation/octrois = $LIGNES)."
    rouge "    Un controle qu'il faut penser a appeler ne ferme rien."
  fi
fi
[[ $A_OUVERT -eq 0 ]] && echo "      ok: A. le migrateur est contenu pendant PENDING"
decor_deposer
fi

# ==========================================================================
# B. ACTIVE — LE MIGRATEUR POSSEDE LES TABLES DE PREUVE
# ==========================================================================
# La phase 2 revoque les emprunts du migrateur. Elle ne change RIEN a la
# PROPRIETE: les quatre tables evenementielles sont creees par lui et le
# restent. Le proprietaire d'une table peut desactiver ses declencheurs et,
# sans `FORCE ROW LEVEL SECURITY`, contourner sa RLS.
if ! decor_poser b; then
  echoue "le decor B n'a pas pu etre pose: le scenario B n'est pas evalue"
elif ! decor_finaliser; then
  echoue "le decor B n'a pas pu etre finalise: le scenario B n'est pas evalue"
  suivre_decor; decor_deposer
else
suivre_decor
RESTE=$(adm -tAc "select count(*) from unnest(array['${AUTORITES[0]}','${AUTORITES[1]}','${AUTORITES[2]}']) a(r)
                   where pg_has_role('$MIG', a.r, 'SET')
                      or pg_has_role('$MIG', a.r, 'USAGE')
                      or pg_has_role('$MIG', a.r, 'MEMBER WITH ADMIN OPTION')" 2>&1)
echo "      ok: decor B — ACTIVE, capacites residuelles du migrateur: $RESTE"

# --- B1. proprietaires et RLS forcee, lus dans le catalogue ---------------
B_OUVERT=0
POSSEDEES=$(admb -tAc "select coalesce(string_agg(c.relname, ', ' order by c.relname), '')
                         from pg_class c join pg_roles o on o.oid = c.relowner
                        where o.rolname = '$MIG'
                          and c.relname in ('normative_authorisation_grants',
                                            'normative_authorisation_revocations',
                                            'normative_rule_confirmations',
                                            'normative_rule_confirmation_revocations')" 2>&1)
SANS_FORCE=$(admb -tAc "select coalesce(string_agg(relname, ', ' order by relname), '')
                          from pg_class
                         where relname in ('normative_authorisation_grants',
                                           'normative_authorisation_revocations',
                                           'normative_rule_confirmations',
                                           'normative_rule_confirmation_revocations')
                           and relrowsecurity and not relforcerowsecurity" 2>&1)
if [[ -n "$POSSEDEES" ]]; then
  rouge "B1. APRES ACTIVATION, le migrateur possede encore: $POSSEDEES"
  B_OUVERT=1
fi
if [[ -n "$SANS_FORCE" ]]; then
  rouge "B1. RLS non FORCEE (le proprietaire la contourne) sur: $SANS_FORCE"
  B_OUVERT=1
fi
[[ $B_OUVERT -eq 0 ]] && echo "      ok: B1. aucune table normative ne reste au migrateur, RLS forcee"

# --- la fixture LEGITIME, par le parcours reel ----------------------------
# Elle est ecrite AVANT toute desactivation: une preuve forgee ne prouverait
# rien, c'est une preuve VRAIE qu'on doit pouvoir detruire.
adm -c "grant normative_backend to \"$SVC\";" >/dev/null 2>&1
# ET LE ROLE D'EXECUTION PRIVILEGIE: depuis 0013, `normative_backend` n'a plus
# INSERT sur les tables d'autorite. Par le plan de controle, qui a cree le role
# en phase 0 et en detient donc seul l'ADMIN.
ctlp -c "grant eurostruct_authority_backend to \"$SVC\";" >/dev/null 2>&1
admb -c "grant usage on schema auth to normative_backend;
         grant select on auth.users to normative_backend;" >/dev/null 2>&1
admb >/dev/null 2>&1 <<'SQL'
insert into auth.users (id, email) values
  ('b0000000-0000-0000-0000-0000000000b1', 'FICTIF-ac-b1@eurostruct.test'),
  ('b0000000-0000-0000-0000-0000000000b2', 'FICTIF-ac-b2@eurostruct.test')
on conflict do nothing;
SQL
ctl -tAc "select bootstrap_normative_administrator(
  'b0000000-0000-0000-0000-0000000000b1', 'FICTIF Racine',
  'FICTIF — amorcage legitime du decor B.')" >/dev/null 2>&1
# `begin` + `set local role` + `set_config(..., true)`: le reglage est local a
# la TRANSACTION. En instructions separees, il disparait avant l'insertion et
# le declencheur refuse « aucune identite authentifiee » (mesure).
svc -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL'
begin;
-- PAS DE `set local role normative_backend`: l'endosser FERAIT PERDRE
-- l'heritage d'`eurostruct_authority_backend`, donc le droit d'ecrire.
select set_config('request.jwt.claim.sub','b0000000-0000-0000-0000-0000000000b1',true);
select set_config('eurostruct.actor_id','b0000000-0000-0000-0000-0000000000b1',true);
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part, edition, reason,
   parent_grant_id)
values ('b0000000-0000-0000-0000-0000000000b2','FICTIF Relecteur',
        'can_validate_normative_reference','BE','EN 1992','1-1','2010',
        'FICTIF — habilitation legitime du decor B.',
        (select id from normative_authorisation_grants where origin = 'bootstrap'));
commit;
SQL
svc -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL'
begin;
select set_config('request.jwt.claim.sub','b0000000-0000-0000-0000-0000000000b2',true);
select set_config('eurostruct.actor_id','b0000000-0000-0000-0000-0000000000b2',true);
insert into normative_rule_confirmations (
  country_code, standard_family, part, rule_id,
  stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
  digest_algorithm, canonicalization_version,
  normative_spec_payload, implementation_payload, evidence_payload,
  stack_payload, stack_snapshot, annex_edition, evidence_items, statement,
  verifier_id, verifier_name, verified_at, authorisation_grant_id,
  authorisation_scope, idempotency_key)
select 'BE', 'EN 1992', '1-1', 'test.fermeture',
  encode(sha256(convert_to(pile,'UTF8')),'hex'), encode(sha256(convert_to(spec,'UTF8')),'hex'),
  encode(sha256(convert_to(impl,'UTF8')),'hex'), encode(sha256(convert_to(ev,'UTF8')),'hex'),
  'sha256','esc-canon/1', spec, impl, ev, pile, '{}'::jsonb, 'x',
  '[]'::jsonb, 'FICTIF — confirmation LEGITIME.',
  'b0000000-0000-0000-0000-0000000000b2','FICTIF Relecteur', now(), null,
  '{}'::jsonb, 'FICTIF-ac-legit-1'
from (select
  '{"canonicalization_version":"esc-canon/1","kind":"normative_spec","rule_id":"test.fermeture"}' as spec,
  '{"canonicalization_version":"esc-canon/1","kind":"implementation","rule_id":"test.fermeture"}' as impl,
  '{"canonicalization_version":"esc-canon/1","items":[{"clause":"c","document_digest":"' || repeat('b',64) || '","document_role":"annexe","edition":"2010","page_printed":1,"quote":"FICTIF","quote_digest":"' || encode(sha256(convert_to('FICTIF','UTF8')),'hex') || '","reference":"FICTIF ANB"}],"kind":"evidence"}' as ev,
  '{"components":[{"application_order":2,"document_digest":"' || repeat('b',64) || '","edition":"2010","reference":"FICTIF ANB","role":"annexe"}],"country_code":"BE","kind":"normative_stack","part":"1-1","schema_version":"esc-stack/1","standard_family":"EN 1992"}' as pile
) p;
commit;
SQL
LEGIT=$(admb -tAc "select count(*) from normative_rule_confirmations
                    where rule_id = 'test.fermeture'" 2>&1)
if [[ "$LEGIT" != "1" ]]; then
  echoue "B: la confirmation legitime n'a pas pu etre creee ($LEGIT): le scenario"
  echoue "   ne prouverait rien — il n'y aurait aucune preuve a detruire."
else
  # --- B2. la preuve resiste a une suppression directe --------------------
  # DEUX REFUS SONT ACCEPTABLES, ET LEUR ORDRE DIT LA FORCE DU MODELE:
  #   * « permission denied » — le migrateur n'atteint meme plus la table.
  #     C'est le refus FORT, celui que la propriete transferee procure;
  #   * « immuable » — il l'atteint, mais le declencheur de conservation
  #     decennale refuse. C'est le refus qui existait avant 6.3b6c.
  # Ce qui serait rouge, c'est l'ABSENCE de refus.
  REFUS=$(mig -c "delete from normative_rule_confirmations
                   where rule_id = 'test.fermeture';" 2>&1)
  if ! grep -qiE "immuable|permission denied|droit refuse" <<<"$REFUS"; then
    echoue "B2. la suppression directe n'a ete refusee par rien:"
    echoue "    $(head -1 <<<"$REFUS" | cut -c1-140)"
  else
    grep -qi "permission denied" <<<"$REFUS" \
      && echo "      ok: B2. le migrateur n'atteint plus la table (permission denied)" \
      || echo "      ok: B2. la suppression directe est refusee (immuabilite)"
    # --- B3. le proprietaire desactive les declencheurs -------------------
    DESACT=$(mig -c "alter table normative_rule_confirmations
                       disable trigger user;" 2>&1)
    ACTIFS=$(admb -tAc "select count(*) filter (where t.tgenabled <> 'D')::text || '/' ||
                               count(*)::text
                          from pg_trigger t join pg_class c on c.oid = t.tgrelid
                         where not t.tgisinternal
                           and c.relname = 'normative_rule_confirmations'" 2>&1)
    if grep -qiE "ERROR|ERREUR" <<<"$DESACT"; then
      echo "      ok: B3. le migrateur ne peut pas desactiver les declencheurs"
      echo "             ($(grep -m1 -iE 'ERROR|ERREUR' <<<"$DESACT" | cut -c1-90 | sed 's/^ERROR:  //'))"
    else
      rouge "B3. LE MIGRATEUR A DESACTIVE LES DECLENCHEURS (actifs: $ACTIFS)."
      rouge "    Ses capacites normatives valent pourtant $RESTE: la revocation"
      rouge "    de la phase 2 n'achete rien contre le PROPRIETAIRE."
      B_OUVERT=1

      # --- B4. reecriture d'une preuve ------------------------------------
      AVANT=$(admb -tAc "select left(evidence_digest, 12)
                           from normative_rule_confirmations
                          where rule_id = 'test.fermeture'" 2>&1)
      mig -c "update normative_rule_confirmations
                 set statement = 'FICTIF — REECRIT par le migrateur',
                     evidence_digest = repeat('0', 64)
               where rule_id = 'test.fermeture';" >/dev/null 2>&1
      APRES=$(admb -tAc "select left(evidence_digest, 12)
                           from normative_rule_confirmations
                          where rule_id = 'test.fermeture'" 2>&1)
      [[ "$AVANT" != "$APRES" ]] && \
        rouge "B4. LA PREUVE A ETE REECRITE: evidence_digest $AVANT -> $APRES."

      # --- B5. suppression, sans audit ------------------------------------
      AUD_AV=$(admb -tAc "select count(*) from audit_log
                           where action like 'normative.%'" 2>&1)
      mig -c "delete from normative_rule_confirmations
               where rule_id = 'test.fermeture';" >/dev/null 2>&1
      AUD_AP=$(admb -tAc "select count(*) from audit_log
                           where action like 'normative.%'" 2>&1)
      RESTANT=$(admb -tAc "select count(*) from normative_rule_confirmations
                            where rule_id = 'test.fermeture'" 2>&1)
      if [[ "$RESTANT" == "0" ]]; then
        rouge "B5. LA PREUVE A ETE SUPPRIMEE (lignes restantes: $RESTANT), et"
        rouge "    l'audit normatif n'a pas bouge ($AUD_AV -> $AUD_AP)."
        rouge "    La conservation decennale ne tient pas contre le proprietaire."
      fi
    fi
  fi
fi
decor_deposer
fi

# ==========================================================================
# C. LES HELPERS PUBLICS SE COMPOSENT
# ==========================================================================
# `normative_prepare_activation`, `normative_record_activation` et
# `normative_finalize_deployment` sont toutes exposees a `eurostruct_deployment`.
# 6.3b6b a verifie qu'aucune ne suffit SEULE. Reste ce qu'elles font ENSEMBLE,
# en plusieurs transactions.

# --- C1. PARCOURS A: le manifeste perime ----------------------------------
# La branche « deja prepare » de `normative_prepare_activation` compare le
# manifeste presente a celui DEJA ENREGISTRE. Elle ne relit pas les
# declarations courantes. Une preparation validee, puis un changement, puis une
# finalisation avec le manifeste d'origine: tout concorde, sauf la realite.
if ! decor_poser c; then
  echoue "le decor C1 n'a pas pu etre pose"
else
suivre_decor
M1=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
PREP=$(ctl -tAc "select normative_prepare_activation('$M1')" 2>&1)
adm -c "alter database \"$BASE\"
          set eurostruct.token_roles = 'authenticated,anon,FICTIF_apres_prepare';" >/dev/null 2>&1
M2=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
SORTIE=$(ctl -tAc "select normative_finalize_deployment('$M1')" 2>&1)
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)
FIGE=$(admb -tAc "select valeur from normative_approved_settings
                   where nom = 'eurostruct.token_roles'" 2>&1)
DECLARE=$(adm -tAc "select split_part(o, '=', 2)
                      from pg_db_role_setting s cross join unnest(s.setconfig) as o
                     where s.setdatabase = (select oid from pg_database where datname = '$BASE')
                       and s.setrole = 0
                       and split_part(o, '=', 1) = 'eurostruct.token_roles'" 2>&1)
# LA COMPOSITION EST FERMEE DES SA PREMIERE ETAPE, et c'est plus fort que ce
# que ce scenario cherchait. Une preparation isolee est refusee: elle exige le
# verrou de finalisation, que seul `normative_finalize_deployment()` prend. Il
# n'y a donc plus de preparation validee a laisser perimer.
#
# Le refus doit NOMMER son motif. Un refus accidentel — droit manquant, table
# absente — laisserait croire la porte fermee alors qu'elle aurait seulement
# change de serrure.
if grep -qiE "verrou de finalisation|n'est pas une operation autonome" <<<"$PREP"; then
  echo "      ok: C1. la preparation isolee est refusee — le verrou de"
  echo "             finalisation n'est pas detenu, donc rien ne peut perimer"
elif ! grep -qE '^[0-9a-f]{64}$' <<<"$PREP"; then
  echoue "C1. la preparation isolee est refusee, mais pas au motif du verrou:"
  echoue "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$PREP" | cut -c1-150)"
elif [[ "$M1" == "$M2" ]]; then
  echoue "C1. la declaration n'a pas change: le scenario ne reproduit rien"
elif [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ok: C1. finalisation refusee sur une preparation perimee"
  echo "             ($(grep -m1 -iE 'ERROR|ERREUR' <<<"$SORTIE" | cut -c1-100))"
else
  rouge "C1. PARCOURS A — LA FINALISATION ABOUTIT SUR UNE PREPARATION PERIMEE."
  rouge "    fige comme approuve  : « $FIGE »"
  rouge "    reellement declare   : « $DECLARE »"
  rouge "    La branche « deja prepare » ne relit jamais les declarations: le"
  rouge "    manifeste est compare a lui-meme, pas au monde."
fi
decor_deposer
fi

# --- C2. PARCOURS B: l'activation hors finaliseur --------------------------
# Preparer, revoquer a la main comme le ferait le finaliseur, puis appeler
# l'ecriture de confiance. Chaque etape est legitime prise seule; leur
# composition contourne le verrou et l'atomicite.
if ! decor_poser e; then
  echoue "le decor C2 n'a pas pu etre pose"
else
suivre_decor
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
ctl -tAc "select normative_prepare_activation('$M')" >/dev/null 2>&1
ctlp -c "revoke ${AUTORITES[0]}, ${AUTORITES[1]}, ${AUTORITES[2]}
         from \"$MIG\";" >/dev/null 2>&1
SORTIE=$(ctl -tAc "select normative_record_activation()" 2>&1)
ETAT=$(ctl -tAc "select normative_activation_state()" 2>&1)
if [[ "$ETAT" != "ACTIVE" ]]; then
  echo "      ok: C2. l'activation hors finaliseur est refusee"
  echo "             ($(grep -m1 -iE 'ERROR|ERREUR' <<<"$SORTIE" | cut -c1-100))"
else
  rouge "C2. PARCOURS B — ACTIVE OBTENU SANS LE FINALISEUR, en trois"
  rouge "    transactions distinctes: prepare, revocations a la main, puis"
  rouge "    record. Le verrou de finalisation n'a jamais ete pris et"
  rouge "    l'ensemble n'a jamais ete atomique."
fi
decor_deposer
fi

# ==========================================================================
# D. L'IDEMPOTENCE ACCEPTE N'IMPORTE QUEL MANIFESTE
# ==========================================================================
# En etat ACTIVE, `normative_finalize_deployment` rend « ACTIVE (deja
# finalise) » SANS regarder `p_manifeste`. Un script de deploiement pointe sur
# la mauvaise base, ou portant une configuration ancienne, recoit donc un
# succes — pour la seule raison que cette base est deja active.
if ! decor_poser f; then
  echoue "le decor D n'a pas pu etre pose"
elif ! decor_finaliser; then
  echoue "le decor D n'a pas pu etre finalise"
  suivre_decor; decor_deposer
else
suivre_decor
M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
MEME=$(ctl -tAc "select normative_finalize_deployment('$M')" 2>&1)
D_OUVERT=0
grep -q "deja finalise" <<<"$MEME" \
  || { echoue "D. le meme manifeste n'est plus idempotent: $(head -1 <<<"$MEME")"; }
for cas in "AUTRE:$(printf '0%.0s' $(seq 1 64))" "VIDE:" "MAL FORME:pas-un-digest"; do
  nom="${cas%%:*}"; val="${cas#*:}"
  S=$(ctl -tAc "select normative_finalize_deployment('$val')" 2>&1)
  if grep -qiE "MANIFEST_MISMATCH|ne correspond|manifeste" <<<"$S"; then
    echo "      ok: D. manifeste « $nom » refuse apres activation"
  else
    rouge "D. manifeste « $nom » ACCEPTE apres activation: « $(head -1 <<<"$S" | cut -c1-60) »"
    D_OUVERT=1
  fi
done
[[ $D_OUVERT -eq 0 ]] && echo "      ok: D. l'idempotence exige le bon manifeste"
decor_deposer
fi

# ==========================================================================
# D2. LA RELECTURE APRES LE VERROU — ce que voit le PERDANT d'une course
# ==========================================================================
# CE SCENARIO EXISTE PARCE QU'UN TROU DE TEST A ETE MESURE, PAS SUPPOSE.
#
# `normative_finalize_deployment` compare le manifeste a DEUX endroits, et les
# deux blocs sont textuellement identiques:
#
#   1. le chemin rapide d'IDEMPOTENCE, AVANT le verrou — atteint quand la base
#      est deja ACTIVE au moment de l'appel. C'est ce que la section D
#      ci-dessus eprouve, sequentiellement;
#   2. la RELECTURE APRES le verrou — « tout l'objet du verrou », dit le code.
#      Elle n'est atteinte que par le PERDANT d'une course: il entre alors que
#      la base est PENDING, attend derriere le verrou, et decouvre en le
#      recevant que la base est devenue ACTIVE.
#
# Aucun test n'atteignait le second chemin: la matrice de mutation, dont la
# cible etait ambigue, mutait toujours le premier. En neutralisant le second
# separement, elle a montre que RIEN ne rougissait. Ce n'est PAS un defaut du
# candidat — la garde post-verrou est bien presente et fonctionne; c'est un
# defaut de COUVERTURE, et il se ferme ici.
#
# LA CAUSALITE EST CONSTATEE, JAMAIS ESPEREE. Aucun `sleep` ne sert de
# synchronisation: A retient sa transaction jusqu'a AVOIR VU B bloquee sur un
# verrou, et c'est cette observation qui autorise le commit.
echo "      -- D2. la relecture apres le verrou (course sur manifeste)"

# La fonction d'attente vit dans la base du decor: elle purge l'instantane de
# `pg_stat_activity`, sans quoi une session en transaction relit indefiniment
# l'etat d'avant le blocage qu'elle attend.
d2_outils() {
  admb -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL'
create or replace function t_attendre_bloquee(
  p_app text, p_secondes numeric default 60
) returns void language plpgsql as $fn$
declare fin timestamptz := clock_timestamp() + (p_secondes || ' s')::interval;
begin
  loop
    perform pg_stat_clear_snapshot();
    if exists (select 1 from pg_stat_activity
                where application_name = p_app and wait_event_type = 'Lock') then
      return;
    end if;
    if clock_timestamp() > fin then
      raise exception 'barriere: % ne s''est jamais bloquee', p_app;
    end if;
  end loop;
end $fn$;
SQL
}

# d2_course <manifeste-du-perdant> <etiquette>
# Rend, sur stdout: "<code-perdant>|<sortie-perdant>"
d2_course() {
  local mb="$1" etq="$2" appa appb ma
  appa="FICTIF-d2-A-$$-$etq"; appb="FICTIF-d2-B-$$-$etq"
  ma=$(ctl -tAc "select normative_settings_manifest()" 2>&1 | tr -d ' ')
  [[ -n "$mb" ]] || mb="$ma"
  cat > "$TMP_D2/a.sql" <<SQL
begin;
select normative_finalize_deployment('$ma');
select t_attendre_bloquee('$appb');
commit;
SQL
  cat > "$TMP_D2/b.sql" <<SQL
begin;
select normative_finalize_deployment('$mb');
commit;
SQL
  PGAPPNAME="$appa" PGUSER="$CTL" PGPASSWORD="$MDP"     psql -X -q -v ON_ERROR_STOP=1 -d "$BASE" -f "$TMP_D2/a.sql"     >"$TMP_D2/a.log" 2>&1 &
  local pa=$!
  # A DETIENT LE VERROU AVANT QUE B PARTE. Sans cette attente, B pourrait
  # gagner la course, prendre le verrou en premier, et le scenario mesurerait
  # l'inverse de ce qu'il annonce.
  d2_attendre "$appa" "detient" || { wait $pa; return 1; }
  # `ON_ERROR_STOP` EST INDISPENSABLE ICI, et son absence a produit un FAUX
  # ROUGE — mesure du 27/08. Le script du perdant est
  # « begin; select ...; commit; »: sans cette option psql poursuit apres
  # l'erreur, le `commit` final reussit (il annule), et psql sort avec le
  # code 0. Le scenario concluait que le perdant avait ete ACCEPTE avec un
  # manifeste different, alors que la garde post-verrou l'avait refuse par
  # MANIFEST_MISMATCH. Un test qui juge sur le code de sortie d'un script SQL
  # non arrete a l'erreur ne mesure pas ce qu'il croit mesurer.
  PGAPPNAME="$appb" PGUSER="$CTL" PGPASSWORD="$MDP" psql -X -q -v ON_ERROR_STOP=1 -d "$BASE" -f "$TMP_D2/b.sql" >"$TMP_D2/b.log" 2>&1 &
  local pb=$!
  wait $pa; local ca=$?
  wait $pb; local cb=$?
  D2_CODE_A=$ca; D2_CODE_B=$cb
  D2_SORTIE_B="$(cat "$TMP_D2/b.log" 2>/dev/null)"
  return 0
}

d2_attendre() {  # d2_attendre <app> <detient|bloquee>
  local app="$1" quoi="$2" i pred
  if [[ "$quoi" == "detient" ]]; then
    pred="exists(select 1 from pg_locks l join pg_stat_activity a on a.pid = l.pid
                  where l.locktype='advisory' and l.granted
                    and a.application_name='$app')"
  else
    pred="exists(select 1 from pg_stat_activity
                  where application_name='$app' and wait_event_type='Lock')"
  fi
  for ((i = 0; i < 600; i++)); do
    [[ "$(admb -tAc "select pg_stat_clear_snapshot(); select $pred" 2>/dev/null           | tail -1 | tr -d ' ')" == "t" ]] && return 0
  done
  echoue "D2. la session $app n'a jamais ete observee « $quoi »"
  return 1
}

TMP_D2="$(mktemp -d)"
if ! decor_poser g2; then
  echoue "le decor D2 n'a pas pu etre pose"
else
  suivre_decor
  d2_outils
  # --- le PERDANT presente un manifeste DIFFERENT: il doit etre refuse -----
  if d2_course "$(printf '0%.0s' $(seq 1 64))" "diff"; then
    ETAT_D2=$(ctl -tAc "select normative_activation_state()" 2>&1 | tr -d ' ')
    if [[ "$D2_CODE_A" -ne 0 ]]; then
      echoue "D2. le gagnant n'a pas finalise (code $D2_CODE_A): scenario non evalue"
    elif [[ "$ETAT_D2" != "ACTIVE" ]]; then
      echoue "D2. la base n'est pas ACTIVE apres le gagnant (« $ETAT_D2 »)"
    elif grep -qiE "MANIFEST_MISMATCH|ne correspond|manifeste" <<<"$D2_SORTIE_B"; then
      echo "      ok: D2. le perdant, debloque apres le commit du gagnant,"
      echo "             relit ACTIVE et REFUSE son manifeste different"
      echo "             ($(grep -m1 -oiE '(ERROR|ERREUR)[^|]{0,90}' <<<"$D2_SORTIE_B" | cut -c1-90))"
    elif [[ "$D2_CODE_B" -eq 0 ]]; then
      rouge "D2. le PERDANT a obtenu un succes avec un manifeste DIFFERENT:"
      rouge "    la relecture apres le verrou n'a pas compare le manifeste."
      rouge "    sortie du perdant: $(tr '\n' ' ' <<<"$D2_SORTIE_B" | cut -c1-200)"
    else
      echoue "D2. le perdant a echoue pour une AUTRE raison que le manifeste:"
      echoue "    $(grep -m1 -iE 'ERROR|ERREUR' <<<"$D2_SORTIE_B" | cut -c1-140)"
    fi
    # L'ETAT PERSISTANT EST CELUI DU GAGNANT, et rien d'autre.
    MOK=$(ctl -tAc "select normative_finalize_deployment(
            normative_settings_manifest())" 2>&1)
    grep -q "deja finalise" <<<"$MOK"       || echoue "D2. l'etat persistant n'est plus celui du gagnant: $(head -1 <<<"$MOK")"
  fi
  decor_deposer
fi

# --- LE JUMEAU POSITIF: meme manifeste, resultat idempotent ---------------
# Sans lui, la garde serait satisfaite par un systeme qui refuse TOUTE
# finalisation concurrente — et le refus ci-dessus ne dirait plus rien.
if ! decor_poser g3; then
  echoue "le decor D2+ n'a pas pu etre pose"
else
  suivre_decor
  d2_outils
  if d2_course "" "meme"; then
    if [[ "$D2_CODE_A" -ne 0 ]]; then
      echoue "D2+. le gagnant n'a pas finalise (code $D2_CODE_A)"
    elif [[ "$D2_CODE_B" -ne 0 ]]; then
      rouge "D2+. le perdant a ete REFUSE alors qu'il presentait le MEME"
      rouge "     manifeste: la course rend la finalisation non idempotente."
      rouge "     $(grep -m1 -iE 'ERROR|ERREUR' <<<"$D2_SORTIE_B" | cut -c1-120)"
    elif grep -q "deja finalise" "$TMP_D2/b.log"; then
      echo "      ok: D2+. le perdant, avec le MEME manifeste, obtient le"
      echo "              resultat idempotent apres le verrou"
    else
      echoue "D2+. le perdant a reussi sans annoncer l'idempotence:"
      echoue "     $(head -1 "$TMP_D2/b.log" | cut -c1-120)"
    fi
  fi
  decor_deposer
fi
rm -rf "$TMP_D2"

# ==========================================================================
# E. LES EXEMPTIONS DE SERVICE COMPARENT LE NOM SEUL
# ==========================================================================
# Le bloc des roles d'AUTORITE compare `m.oid` ET `m.rolname`. Les deux
# exemptions des roles de SERVICE ne comparent que le nom. Le controle global
# de coherence du plan attrape aujourd'hui une substitution — mais une
# exemption qui n'est sure que grace a un AUTRE controle n'est pas sure.
# Verification statique: c'est une propriete du texte, pas d'une base.
# LES DEUX FICHIERS DE MIGRATION SONT LUS. La racine de confiance a demenage
# en phase 0 (6.3b6c): un motif qui ne regardait que 0010 est passe au VERT du
# jour au lendemain sans que rien ne soit corrige — le controle avait perdu son
# sujet, pas trouve sa reponse.
MIGRATIONS=("$HARNAIS_SCEAU"
            "$DB_DIR/migrations/0010_normative_confirmation.sql")
NOM_SEUL=$(grep -nE "^\s+(p|c)\.rolname = normative_control_plane\(\)" \
             "${MIGRATIONS[@]}" | sed 's#.*/##' | tr '\n' ' ')
if [[ -z "$NOM_SEUL" ]]; then
  echo "      ok: E. toutes les exemptions comparent l'oid ET le nom"
else
  rouge "E. exemptions comparant le NOM SEUL, lignes: $NOM_SEUL"
  rouge "   « oid et nom partout » est annonce mais n'est vrai que du bloc des"
  rouge "   roles d'autorite."
fi

# ==========================================================================
# F. LE CONTRAT DU `topology_digest`
# ==========================================================================
# Le digest est calcule et inscrit a l'activation. Rien ne le recalcule pour le
# comparer — et c'est un CHOIX, qui doit etre ecrit: une derive qui reste dans
# les regles doit pouvoir avoir lieu sans qu'un digest fige la refuse.
#
# Ce qui est exige ici n'est donc pas une comparaison, mais que le contrat soit
# TRANCHE ET LISIBLE aux deux endroits ou on le cherchera, et que la
# distinction entre « photographie » et « controle » soit OBSERVABLE.
MARQUEUR_F="CONTRAT DU topology_digest"
F_SQL=$(grep -lF "$MARQUEUR_F" "${MIGRATIONS[@]}" 2>/dev/null | sed 's#.*/##' | tr '\n' ' ')
F_DOC=$(grep -rlF "$MARQUEUR_F" "$DB_DIR/../docs" 2>/dev/null | head -1)
F_OUVERT=0
if [[ -z "$F_SQL" || -z "$F_DOC" ]]; then
  rouge "F. le contrat du topology_digest n'est pas ecrit"
  rouge "   (migration: ${F_SQL:-ABSENT}; documentation: ${F_DOC:-ABSENTE})."
  rouge "   Tant qu'il ne l'est pas, « il bloque la derive » et « il documente"
  rouge "   l'activation » restent tous deux defendables — et l'un des deux est"
  rouge "   faux."
  F_OUVERT=1
fi

# LA DISTINCTION, RENDUE OBSERVABLE. Une modification de topologie AUTORISEE —
# accorder un role de service a un login declare approuve — doit:
#   * changer la PHOTOGRAPHIE (sinon elle ne photographie rien);
#   * ne PAS faire refuser `assert_normative_topology()` (sinon ce n'est pas
#     une derive autorisee).
if ! decor_poser g; then
  echoue "le decor F n'a pas pu etre pose"
elif ! decor_finaliser; then
  echoue "le decor F n'a pas pu etre finalise"
  suivre_decor; decor_deposer
else
suivre_decor
INSCRIT=$(admb -tAc "select topology_digest from normative_activation" 2>&1)
photo() {
  admb -tAc "select normative_topology_digest(
               (select role_oid from normative_control_plane),
               (select role_name from normative_control_plane),
               (select migrateur_oid from normative_finalization_intent),
               (select migrateur_nom from normative_finalization_intent),
               (select manifeste from normative_finalization_intent))" 2>&1
}
AVANT_F=$(photo)
# Modification AUTORISEE: `$SVC` est declare dans `approved_service_logins`,
# fige a la finalisation. Lui accorder le role de service est exactement ce
# qu'un deploiement fait.
adm -c "grant normative_backend to \"$SVC\";" >/dev/null 2>&1
APRES_F=$(photo)
TOPO_F=$(ctl -tAc "select assert_normative_topology()" 2>&1)
if [[ "$INSCRIT" != "$AVANT_F" ]]; then
  echoue "F. la photo refaite ne retrouve pas celle inscrite a l'activation:"
  echoue "   inscrite $(cut -c1-12 <<<"$INSCRIT") / refaite $(cut -c1-12 <<<"$AVANT_F")"
elif [[ "$AVANT_F" == "$APRES_F" ]]; then
  rouge "F. une modification de topologie ne change pas la photographie:"
  rouge "   elle ne photographie donc pas la topologie."
  F_OUVERT=1
elif grep -qiE "ERROR|ERREUR" <<<"$TOPO_F"; then
  rouge "F. une modification AUTORISEE fait refuser la topologie:"
  rouge "   $(grep -m1 -iE 'ERROR|ERREUR' <<<"$TOPO_F" | cut -c1-140)"
  F_OUVERT=1
elif [[ $F_OUVERT -eq 0 ]]; then
  echo "      ok: F. photographie d'audit, contrat ecrit ($(basename "$F_DOC")):"
  echo "             une derive autorisee change la photo ($(cut -c1-12 <<<"$AVANT_F")"
  echo "             -> $(cut -c1-12 <<<"$APRES_F")) sans faire refuser la topologie"
fi
decor_deposer
fi

# ==========================================================================
# G. RESTAURATION INTER-CLUSTER
# ==========================================================================
# L'identite du plan porte un OID PostgreSQL. Un `pg_dump`/restore vers un
# autre cluster ne le preserve pas: la base restauree designerait un OID qui
# n'a plus de sens. Le comportement attendu est un refus explicite, pas une
# acceptation silencieuse ni un OID qu'on pourrait reecrire.
#
# LE MOTIF EST EXACT, ET C'EST DELIBERE. Une premiere version cherchait
# « restaur|pg_dump » n'importe ou: elle a rendu VERT en trouvant « table vide
# apres restauration » dans un commentaire sans rapport et le mot
# « restauration » dans un document d'empreintes. Un controle qu'un mot de
# vocabulaire suffit a satisfaire ne controle rien.
MARQUEUR="RESTAURATION INTER-CLUSTER"
# LE MARQUEUR DOIT ETRE DANS LE MESSAGE, PAS DANS UN COMMENTAIRE (6.3b6d).
#
# Le controle cherchait le marqueur N'IMPORTE OU dans le fichier. 6.3b6d a
# ajoute deux commentaires qui le contiennent — dont un qui explique justement
# pourquoi le diagnostic ne promet plus de reprise. La mutation qui retire le
# marqueur du message laissait donc ces commentaires, et le controle restait
# VERT: mesure, `mutation_matrix.py` a declare le controle G creux.
#
# C'est le meme defaut qu'en 6.3b6c — « un controle qu'un mot de vocabulaire
# suffit a satisfaire ne controle rien » — reintroduit par notre propre prose.
# Ce qui est exige est que le REFUS le nomme: les lignes de commentaire SQL ne
# comptent pas.
DIAG_SQL=$(grep -nF "$MARQUEUR" "${MIGRATIONS[@]}" 2>/dev/null \
             | grep -vE '^[^:]+:[0-9]+:[[:space:]]*--' \
             | sed 's#:[0-9]*:.*##; s#.*/##' | sort -u | tr '\n' ' ')
DOC_MD=$(grep -rlF "$MARQUEUR" "$DB_DIR/../docs" 2>/dev/null | head -1)
if [[ -n "$DIAG_SQL" && -n "$DOC_MD" ]]; then
  echo "      ok: G. la restauration inter-cluster a un diagnostic et une"
  echo "             documentation ($(basename "$DOC_MD"))"
else
  rouge "G. la restauration inter-cluster n'est ni diagnostiquee ni documentee"
  rouge "   (diagnostic dans 0010: ${DIAG_SQL:-ABSENT}; documentation: ${DOC_MD:-ABSENTE})."
  rouge "   L'identite du plan porte un OID PostgreSQL, qu'un pg_dump/restore"
  rouge "   vers un autre cluster ne preserve pas. Le comportement attendu est"
  rouge "   un refus qui se lit — jamais une acceptation silencieuse, et jamais"
  rouge "   un OID qu'on pourrait reecrire pour « reparer »."
fi

echo ""
echo "================================================="
if [[ $KO -eq 0 && $ROUGES -eq 0 ]]; then
  echo " Fermeture de l'autorite: le migrateur est contenu."
  echo "================================================="
  exit 0
fi
echo " Fermeture de l'autorite:"
echo "   $KO ecart(s) de decor"
echo "   $ROUGES ouverture(s) a fermer"
echo "================================================="
exit 1
