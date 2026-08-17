#!/usr/bin/env bash
#
# EUROSTRUCT — garanties de concurrence, sur DEUX CONNEXIONS REELLES.
#
# Pourquoi un script shell et non un fichier SQL: une session psql est une
# seule connexion, et deux blocs `do $$` successifs s'executent l'un apres
# l'autre. Or ce qu'on veut mesurer n'apparait QUE si deux transactions se
# recouvrent dans le temps. `IF EXISTS` suivi d'`INSERT` passe tous les tests
# monoconnexion du monde et ne protege de rien: deux transactions lisent
# chacune « aucun doublon » avant que l'autre ne valide.
#
# Chaque scenario ouvre deux psql concurrents, force le recouvrement par un
# pg_sleep, et verifie que le resultat correspond a un ordre seriel
# EXPLICABLE — jamais a un etat intermediaire.
#
# S'execute sur sa PROPRE base, vierge: les scenarios courent la chaine de
# confiance depuis son ouverture, ce qui serait impossible sur la base des
# autres suites, ou l'amorcage a deja eu lieu.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_NAME="${1:?base de travail attendue en premier argument}"

# Repertoire propre a cette execution. Des noms fixes dans /tmp se
# contaminent des que deux suites tournent en meme temps — et c'est
# precisement ce qu'une suite de concurrence risque de faire.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Verdict par CODE D'ERREUR attendu, jamais par duree.
#
# Une temporisation prouve mal: sur une machine chargee, un seuil de 800 ms
# devient un faux vert ou un faux rouge selon l'humeur de l'ordonnanceur. On
# donne donc a la transaction bloquee un `lock_timeout` court, et on exige
# l'erreur 55P03 (lock_not_available). Le resultat est binaire: soit elle a
# ete bloquee, soit elle ne l'a pas ete.
ERR_VERROU='55P03'
# Avec `\set VERBOSITY verbose`, psql imprime « ERROR:  55P03: ... ». C'est
# de la que le code est lu — et non d'un champ « SQLSTATE: », qui n'apparait
# pas dans ce format.
code_sqlstate() {
  sed -nE 's/^.*ERROR:[[:space:]]+([0-9A-Z]{5}):.*$/\1/p' "$1" | head -1
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  SANS_QUERY="${DATABASE_URL%%\?*}"
  QUERY=""
  [[ "$DATABASE_URL" == *\?* ]] && QUERY="?${DATABASE_URL#*\?}"
  PSQL=(psql "${SANS_QUERY%/*}/$DB_NAME$QUERY")
else
  PSQL=(psql -h "${PGHOST:-/tmp}" -U "${PGUSER:-postgres}" -d "$DB_NAME")
fi

R1='c0000000-0000-0000-0000-000000000001'   # candidat racine 1
R2='c0000000-0000-0000-0000-000000000002'   # candidat racine 2
VERIF='c0000000-0000-0000-0000-00000000000f'
ECHECS=0
echoue() { echo "      ECHEC: $*"; ECHECS=$((ECHECS + 1)); }

# --------------------------------------------------------------------------
# Acteurs fictifs, et une fabrique de confirmation coherente.
# --------------------------------------------------------------------------
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id, email) values
  ('$R1',    'FICTIF-conc-racine-1@eurostruct.test'),
  ('$R2',    'FICTIF-conc-racine-2@eurostruct.test'),
  ('$VERIF', 'FICTIF-conc-relecteur@eurostruct.test')
on conflict do nothing;

create or replace function t_conc_confirmer(p_rule text, p_idem text)
returns uuid language plpgsql as \$fn\$
declare spec text; impl text; ev text; pile text; n uuid;
begin
  spec := format('{"canonicalization_version":"esc-canon/1",'
                 '"kind":"normative_spec","rule_id":"%s"}', p_rule);
  impl := format('{"canonicalization_version":"esc-canon/1",'
                 '"kind":"implementation","rule_id":"%s"}', p_rule);
  ev   := format('{"canonicalization_version":"esc-canon/1","items":'
                 '[{"clause":"c","document_digest":"%s","document_role":"annexe",'
                 '"edition":"2010","page_printed":1,"quote":"FICTIF",'
                 '"reference":"FICTIF ANB","quote_digest":"%s"}],"kind":"evidence"}',
                 repeat('b', 64),
                 encode(sha256(convert_to('FICTIF', 'UTF8')), 'hex'));
  pile := format('{"components":[{"application_order":2,"document_digest":"%s",'
                 '"edition":"2010","reference":"FICTIF ANB","role":"annexe"}],'
                 '"country_code":"BE","kind":"normative_stack","part":"1-1",'
                 '"schema_version":"esc-stack/1","standard_family":"EN 1992"}',
                 repeat('b', 64));
  insert into normative_rule_confirmations (
    country_code, standard_family, part, rule_id,
    stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
    digest_algorithm, canonicalization_version,
    normative_spec_payload, implementation_payload, evidence_payload,
    stack_payload, stack_snapshot, annex_edition, evidence_items, statement,
    verifier_id, verifier_name, verified_at, authorisation_grant_id,
    authorisation_scope, idempotency_key)
  values ('BE', 'EN 1992', '1-1', p_rule,
    encode(sha256(convert_to(pile, 'UTF8')), 'hex'),
    encode(sha256(convert_to(spec, 'UTF8')), 'hex'),
    encode(sha256(convert_to(impl, 'UTF8')), 'hex'),
    encode(sha256(convert_to(ev,   'UTF8')), 'hex'),
    'sha256', 'esc-canon/1', spec, impl, ev, pile, '{}'::jsonb, 'x',
    '[]'::jsonb, 'FICTIF — lecture de test.',
    '$VERIF', 'FICTIF', now(), null, '{}'::jsonb, p_idem)
  returning id into n;
  return n;
end \$fn\$;
SQL
[[ $? -eq 0 ]] || { echo "      ECHEC: preparation impossible"; exit 1; }

# --------------------------------------------------------------------------
# 1. Deux amorcages concurrents — la chaine ne s'ouvre qu'une fois
# --------------------------------------------------------------------------
echo "    scenario 1: deux amorcages concurrents"
for n in 1 2; do
  eval "cible=\$R$n"
  cat > "$TMP/conc_boot_$n.sql" <<SQL
begin;
select pg_sleep(0.$n);
select bootstrap_normative_administrator(
  '$cible', 'FICTIF Racine $n', 'FICTIF — amorcage concurrent $n');
commit;
SQL
done
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f $TMP/conc_boot_1.sql >$TMP/boot1.log 2>&1 & B1=$!
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f $TMP/conc_boot_2.sql >$TMP/boot2.log 2>&1 & B2=$!
wait $B1; CB1=$?
wait $B2; CB2=$?
BOOTS=$("${PSQL[@]}" -X -q -tAc \
  "select count(*) from normative_authorisation_grants where origin='bootstrap'")
if [[ "$BOOTS" != "1" ]]; then
  echoue "$BOOTS octrois d'amorcage apres la course, 1 attendu"
elif [[ $CB1 -eq 0 && $CB2 -eq 0 ]]; then
  echoue "les deux amorcages ont reussi: deux racines de confiance"
else
  echo "      ok: une seule racine, l'autre transaction refusee"
fi

ADMIN=$("${PSQL[@]}" -X -q -tAc \
  "select grantee_id from normative_authorisation_grants where origin='bootstrap'")
[[ -n "$ADMIN" ]] || { echo "      ECHEC: aucun administrateur amorce"; exit 1; }

# --------------------------------------------------------------------------
# 2. Deux octrois ACTIFS identiques, inseres simultanement
#
# Le verrou consultatif de portee doit en serialiser un derriere l'autre; le
# second voit alors le premier et refuse. Sans verrou, les deux passent et la
# resolution d'habilitation devient ambigue pour toujours.
# --------------------------------------------------------------------------
echo "    scenario 2: deux octrois identiques concurrents"
# Le pg_sleep vient APRES l'insertion, jamais avant. C'est tout le test:
# A insere puis retient sa transaction ouverte, et B insere pendant ce temps.
# Avec le sleep AVANT, B validait avant que A ne commence et A voyait
# simplement la ligne de B — le scenario passait sans jamais rien recouvrir,
# verrou ou pas. Verifie: en retirant le verrou, cette version echoue et
# l'ancienne passait.
for lettre in A B; do
  delai=$([[ "$lettre" == "A" ]] && echo 1.5 || echo 0)
  cat > "$TMP/conc_$lettre.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
set local lock_timeout = '$([[ "$lettre" == "B" ]] && echo 600ms || echo 30s)';
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   reason)
values ('$VERIF', 'FICTIF Relecteur', 'can_validate_normative_reference',
        'BE', 'EN 1992', '1-1', 'FICTIF — course $lettre');
select pg_sleep($delai);
commit;
SQL
done
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_A.sql" >"$TMP/conc_a.log" 2>&1 & PA=$!
sleep 0.3
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_B.sql" >"$TMP/conc_b.log" 2>&1 & PB=$!
wait $PA; CA=$?
wait $PB; CB=$?
SQLSTATE_B="$(code_sqlstate "$TMP/conc_b.log")"
ACTIFS=$("${PSQL[@]}" -X -q -tAc "
  select count(*) from normative_authorisation_grants g
   where g.grantee_id='$VERIF'
     and g.permission='can_validate_normative_reference'
     and normative_grant_is_active(g.id)")
if [[ "$ACTIFS" != "1" ]]; then
  echoue "$ACTIFS octrois actifs identiques apres la course, 1 attendu"
  grep -oE 'ERROR:.*' "$TMP/conc_a.log" "$TMP/conc_b.log" | head -2 | sed 's/^/        /'
elif [[ $CA -eq 0 && $CB -eq 0 ]]; then
  echoue "les deux transactions ont reussi alors qu'une seule le devait"
elif [[ "$SQLSTATE_B" != "$ERR_VERROU" ]]; then
  echoue "B a echoue en $SQLSTATE_B et non $ERR_VERROU: elle n'a pas ete"
  echoue "  bloquee par le verrou de portee, elle a echoue pour autre chose"
else
  echo "      ok: un octroi actif; B bloquee puis expiree ($ERR_VERROU)"
fi

# --------------------------------------------------------------------------
# 3. Confirmation contre revocation concurrente de l'habilitation
#
# Les deux ordres seriels sont acceptables; l'etat intermediaire ne l'est pas.
# --------------------------------------------------------------------------
echo "    scenario 3a: revocation bloquee par une confirmation en vol"
GRANT_ID=$("${PSQL[@]}" -X -q -tAc "
  select g.id from normative_authorisation_grants g
   where g.grantee_id='$VERIF'
     and g.permission='can_validate_normative_reference'
     and normative_grant_is_active(g.id) limit 1")

# La confirmation insere D'ABORD puis retient sa transaction: la revocation
# qui arrive pendant cette fenetre doit se heurter au verrou et EXPIRER. Le
# verdict est le code 55P03, pas une duree.
cat > "$TMP/conc_conf.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$VERIF', true);
select t_conc_confirmer('test.concurrence', 'FICTIF-conc-1');
select pg_sleep(3);
commit;
SQL
cat > "$TMP/conc_revoc.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
set local lock_timeout = '600ms';
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_ID', 'FICTIF — retrait pendant une confirmation en vol.');
commit;
SQL
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_conf.sql" >"$TMP/conc_conf.log" 2>&1 & PC=$!
sleep 0.3
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_revoc.sql" >"$TMP/conc_revoc.log" 2>&1
CR=$?
SQLSTATE_R="$(code_sqlstate "$TMP/conc_revoc.log")"
wait $PC; CC=$?

CONFIRMEE=$("${PSQL[@]}" -X -q -tAc "
  select count(*) from normative_rule_confirmations
   where idempotency_key='FICTIF-conc-1'")
if [[ "$CONFIRMEE" != "1" || $CC -ne 0 ]]; then
  echoue "la confirmation en vol n'a pas abouti (code $CC)"
  grep -oE 'ERROR:.*' "$TMP/conc_conf.log" | head -1 | sed 's/^/        /'
elif [[ "$SQLSTATE_R" != "$ERR_VERROU" ]]; then
  echoue "la revocation a rendu « ${SQLSTATE_R:-succes} » et non $ERR_VERROU:"
  echoue "  elle s'est intercalee au lieu d'attendre la confirmation en vol"
else
  echo "      ok: la revocation a ete bloquee puis a expire ($ERR_VERROU)"
fi

# ------------------------------------------------------------------------
# 3b. L'ordre INVERSE: la revocation tient le verrou, la confirmation suit.
#     Apres attente, la confirmation doit etre REFUSEE — l'habilitation
#     n'existe plus.
# ------------------------------------------------------------------------
echo "    scenario 3b: confirmation apres une revocation deja engagee"
cat > "$TMP/conc_revoc2.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_ID', 'FICTIF — retrait engage avant la confirmation.');
select pg_sleep(2);
commit;
SQL
cat > "$TMP/conc_conf2.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$VERIF', true);
select t_conc_confirmer('test.concurrence', 'FICTIF-conc-2');
commit;
SQL
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_revoc2.sql" >"$TMP/r2.log" 2>&1 & PR2=$!
sleep 0.3
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_conf2.sql" >"$TMP/c2.log" 2>&1
CC2=$?
wait $PR2; CR2=$?

APRES=$("${PSQL[@]}" -X -q -tAc "
  select count(*) from normative_rule_confirmations
   where idempotency_key='FICTIF-conc-2'")
if [[ $CR2 -ne 0 ]]; then
  echoue "la revocation n'a pas abouti (code $CR2)"
elif [[ "$APRES" != "0" || $CC2 -eq 0 ]]; then
  echoue "la confirmation a ete acceptee alors que l'habilitation etait"
  echoue "  deja en cours de retrait: etat intermediaire"
else
  echo "      ok: apres attente, la confirmation est refusee"
fi

# Invariant, quelle qu'ait ete l'issue de chaque course.
INCOHERENTES=$("${PSQL[@]}" -X -q -tAc "
  select count(*)
    from normative_rule_confirmations c
    join normative_authorisation_revocations r
      on r.grant_id = c.authorisation_grant_id
   where r.revoked_at < c.verified_at")
if [[ "$INCOHERENTES" != "0" ]]; then
  echoue "$INCOHERENTES confirmation(s) autorisee(s) par un octroi deja retire"
else
  echo "      ok: aucune confirmation autorisee par un octroi deja retire"
fi

# ------------------------------------------------------------------------
# 4. Le DERNIER administrateur, sous course croisee.
#
#    A revoque l'octroi de B pendant que B revoque celui de A. Chacune voit
#    l'autre encore active. Contre-exemple verifie avant correction: les deux
#    validaient et il ne restait ZERO administrateur, l'amorcage ne pouvant
#    plus etre rejoue. Le verrou COMMUN de l'administration doit desormais les
#    serialiser.
# ------------------------------------------------------------------------
echo "    scenario 4: A revoque B pendant que B revoque A"
ADMIN_B='c0000000-0000-0000-0000-0000000000ab'
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id, email)
values ('$ADMIN_B', 'FICTIF-conc-admin-b@eurostruct.test') on conflict do nothing;
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
insert into normative_authorisation_grants
  (id, grantee_id, grantee_name, permission, reason)
values ('c0000000-0000-0000-0000-0000000000bb', '$ADMIN_B', 'FICTIF Admin B',
        'can_manage_normative_authorisations', 'FICTIF — second administrateur');
commit;
SQL
GRANT_A=$("${PSQL[@]}" -X -q -tAc "
  select id from normative_authorisation_grants
   where grantee_id='$ADMIN' and permission='can_manage_normative_authorisations'")
GRANT_B='c0000000-0000-0000-0000-0000000000bb'

for cote in A B; do
  if [[ "$cote" == "A" ]]; then acteur="$ADMIN"; cible="$GRANT_B"; else acteur="$ADMIN_B"; cible="$GRANT_A"; fi
  cat > "$TMP/dern_$cote.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$acteur', true);
select pg_sleep(0.4);
insert into normative_authorisation_revocations (grant_id, reason)
values ('$cible', 'FICTIF — course croisee $cote');
commit;
SQL
done
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/dern_A.sql" >"$TMP/dA.log" 2>&1 & DA=$!
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/dern_B.sql" >"$TMP/dB.log" 2>&1 & DB=$!
wait $DA; CDA=$?
wait $DB; CDB=$?

RESTANTS=$("${PSQL[@]}" -X -q -tAc "
  select count(*) from normative_authorisation_grants g
   where g.permission='can_manage_normative_authorisations'
     and normative_grant_is_active(g.id)")
REUSSIES=0
[[ $CDA -eq 0 ]] && REUSSIES=$((REUSSIES + 1))
[[ $CDB -eq 0 ]] && REUSSIES=$((REUSSIES + 1))

if [[ "$RESTANTS" == "0" ]]; then
  echoue "zero administrateur actif: la gouvernance est perdue et l'amorcage"
  echoue "  ne peut plus etre rejoue"
elif [[ "$REUSSIES" != "1" ]]; then
  echoue "$REUSSIES revocations reussies, exactement 1 attendue"
else
  echo "      ok: une seule revocation, $RESTANTS administrateur(s) actif(s)"
fi

echo
if [[ $ECHECS -eq 0 ]]; then
  echo "================================================="
  echo " Concurrence multi-connexion verifiee."
  echo "================================================="
  exit 0
fi
echo " $ECHECS scenario(s) de concurrence en echec."
exit 1
