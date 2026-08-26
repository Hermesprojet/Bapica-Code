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
# Chaque scenario ouvre deux psql concurrents, force le recouvrement par des
# BARRIERES sur conditions observables (voir plus bas), et verifie que le
# resultat correspond a un ordre seriel EXPLICABLE — jamais a un etat
# intermediaire.
#
# S'execute sur sa PROPRE base, vierge: les scenarios courent la chaine de
# confiance depuis son ouverture, ce qui serait impossible sur la base des
# autres suites, ou l'amorcage a deja eu lieu.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_harnais.sh
source "$HERE/lib_harnais.sh"
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
# Doublon de portee: le refus SEMANTIQUE d'une transaction qui a obtenu le
# verrou et constate qu'un octroi identique existe deja.
ERR_DOUBLON='23505'
# Avec `\set VERBOSITY verbose`, psql imprime « ERROR:  55P03: ... ». C'est
# de la que le code est lu — et non d'un champ « SQLSTATE: », qui n'apparait
# pas dans ce format.
code_sqlstate() {
  sed -nE 's/^.*ERROR:[[:space:]]+([0-9A-Z]{5}):.*$/\1/p' "$1" | head -1
}

# La connexion vient de l'ENVIRONNEMENT, jamais d'argv (6.3b6a, securite des
# harnais). La version precedente reecrivait `$DATABASE_URL` a la main pour
# changer de base: le mot de passe se retrouvait dans `ps`, lisible par tout
# processus de la machine. Seule la base change desormais, par `-d`.
harnais_connexion || exit 2
PSQL=(psql -X -q -d "$DB_NAME")

R1='c0000000-0000-0000-0000-000000000001'   # candidat racine 1
R2='c0000000-0000-0000-0000-000000000002'   # candidat racine 2
VERIF='c0000000-0000-0000-0000-00000000000f'
ECHECS=0

echoue() { echo "      ECHEC: $*"; ECHECS=$((ECHECS + 1)); }

# --------------------------------------------------------------------------
# BARRIERES (6.3b4 #7)
#
# Les scenarios ordonnaient leurs sessions par des temporisations: `sleep 0.3`
# dans le shell pour lancer B apres A, `pg_sleep(1.5)` dans A pour retenir sa
# transaction. Une temporisation n'ordonne rien — elle PARIE. Sur une machine
# chargee le pari est perdu, le recouvrement n'a pas lieu, et le scenario
# passe au vert sans avoir rien mis en concurrence. C'est le pire mode de
# panne d'un test de course: il ne devient pas rouge, il devient vide.
#
# Une barriere attend une CONDITION OBSERVABLE et echoue bruyamment si elle
# ne se produit pas. Les `sleep 0.1` ci-dessous sont un pas de scrutation, pas
# un ordonnancement: la difference est qu'au bout du delai maximal, une
# barriere signale un echec la ou une temporisation continuait en silence.
#
# Deux conditions suffisent a tout ordonner ici:
#   - « A a insere et retient »  -> pg_locks, verrou consultatif accorde
#   - « B est bloquee »          -> pg_stat_activity, wait_event_type = 'Lock'
# --------------------------------------------------------------------------
APP_A='FICTIF-conc-A'
APP_B='FICTIF-conc-B'

# L'ENREGISTREMENT EST PASSIF: RIEN N'EST ECRIT DANS LE CHEMIN DE SCRUTATION.
# La boucle ci-dessous est le coeur de la course observee; y ajouter un travail
# par tour deplacerait la fenetre que l'on cherche justement a mesurer. Deux
# scalaires sont poses AVANT et APRES la boucle, et l'etat des barrieres est
# RECONSTRUIT au moment du premier echec a partir d'eux.
BARRIERE_EN_COURS=""      # nom de la barriere franchie ou en attente
BARRIERE_RANG=0           # rang de scrutation atteint
BARRIERE_ETAT=""          # ATTEINTE | JAMAIS_ATTEINTE
BARRIERES=()              # historique, ecrit UNE FOIS par barriere, hors boucle

attendre() {                # attendre <description> <predicat-sql>
  local quoi="$1" sql="$2" i n
  BARRIERE_EN_COURS="$quoi"; BARRIERE_ETAT="EN_COURS"; BARRIERE_RANG=0
  for ((i = 0; i < 600; i++)); do      # 60 s au plus, jamais un succes muet
    n=$("${PSQL[@]}" -X -q -tAc "select ($sql)::int" 2>/dev/null)
    [[ "$n" == "1" ]] && break
    sleep 0.1
  done
  BARRIERE_RANG=$((i + 1))
  if (( i < 600 )); then
    BARRIERE_ETAT=ATTEINTE
    BARRIERES+=("ATTEINTE|$quoi|essai=$BARRIERE_RANG")
    return 0
  fi
  BARRIERE_ETAT=JAMAIS_ATTEINTE
  BARRIERES+=("JAMAIS_ATTEINTE|$quoi|essais=600")
  echoue "barriere jamais atteinte: $quoi"
  return 1
}

# La condition d'ORDRE la plus honnete n'est pas un rendez-vous ajoute pour le
# test: c'est l'ETAT DONT LE TEST DEPEND. Ici, « A a insere et retient encore
# le verrou de portee ». Attendre cela, plutot qu'un verrou de rendez-vous,
# supprime la question « le rendez-vous mesure-t-il bien ce qu'on croit ».
#
# Un premier essai utilisait un verrou consultatif dedie, pris puis relache
# par A autour de son insertion. Il etait relache en quelques millisecondes,
# avant meme la premiere scrutation du shell: la barriere a echoue — et c'est
# exactement ce qu'on attend d'une barriere, la ou une temporisation aurait
# continue sans rien signaler.
session_detient_verrou() {  # session_detient_verrou <application_name>
  attendre "la session $1 detient un verrou consultatif de transaction" \
    "exists(select 1 from pg_locks l
              join pg_stat_activity a on a.pid = l.pid
             where l.locktype = 'advisory' and l.granted
               and a.application_name = '$1')"
}

session_bloquee() {         # session_bloquee <application_name>
  attendre "la session $1 est bloquee sur un verrou" \
    "exists(select 1 from pg_stat_activity
             where application_name = '$1' and wait_event_type = 'Lock')"
}

# --------------------------------------------------------------------------
# Acteurs fictifs, et une fabrique de confirmation coherente.
# --------------------------------------------------------------------------
"${PSQL[@]}" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<SQL
insert into auth.users (id, email) values
  ('$R1',    'FICTIF-conc-racine-1@eurostruct.test'),
  ('$R2',    'FICTIF-conc-racine-2@eurostruct.test'),
  ('$VERIF', 'FICTIF-conc-relecteur@eurostruct.test')
on conflict do nothing;

-- Barriere cote SQL: une session qui tient sa transaction ouverte ne peut pas
-- sortir attendre dans le shell. Elle attend donc ICI, sur la meme condition
-- observable, et LEVE UNE EXCEPTION si l'autre session ne se bloque jamais —
-- la ou un pg_sleep serait sorti de l'attente en pretendant que tout va bien.
create or replace function t_attendre_bloquee(
  p_app text, p_secondes numeric default 60
) returns void language plpgsql as \$fn\$
declare fin timestamptz := clock_timestamp() + (p_secondes || ' s')::interval;
begin
  loop
    -- INDISPENSABLE. `pg_stat_activity` est mis en cache POUR LA DUREE DE LA
    -- TRANSACTION: sans cette purge, la session appelante relit indefiniment
    -- l'instantane pris a sa premiere lecture — donc un etat anterieur au
    -- blocage qu'elle attend. Verifie: la barriere expirait au bout de 60 s
    -- alors que l'autre session s'etait bel et bien bloquee, puis liberee,
    -- dans la premiere seconde. Une barriere aveugle est pire qu'une
    -- temporisation: elle a l'air rigoureuse.
    perform pg_stat_clear_snapshot();
    if exists (select 1 from pg_stat_activity
                where application_name = p_app
                  and wait_event_type = 'Lock') then
      return;
    end if;
    if clock_timestamp() > fin then
      raise exception
        'barriere jamais atteinte: la session « % » ne s''est jamais bloquee '
        'sur un verrou. Le recouvrement n''a pas eu lieu et le scenario ne '
        'testerait aucune concurrence.', p_app;
    end if;
    perform pg_sleep(0.05);   -- pas de scrutation, pas un ordonnancement
  end loop;
end \$fn\$;

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
# Le decalage se faisait par des pg_sleep de 0,1 et 0,2 seconde. Ici c'est la
# session 1 qui retient: elle amorce, puis attend d'avoir OBSERVE la session 2
# bloquee sur le verrou d'administration avant de valider. Le recouvrement est
# donc constate, pas espere.
cat > "$TMP/conc_boot_1.sql" <<SQL
begin;
select bootstrap_normative_administrator(
  '$R1', 'FICTIF Racine 1', 'FICTIF — amorcage concurrent 1');
select t_attendre_bloquee('$APP_B');
commit;
SQL
# LES DEUX CANDIDATS NOMMENT LE MEME PRINCIPAL, ET C'EST LA CORRECTION.
#
# Depuis 6.3c, l'amorcage exige un MANDAT preautorise: un second candidat
# portant un autre principal serait refuse par le mandat, AVANT tout verrou.
# La course serait alors gagnee par la declaration, pas par la serialisation —
# et ce fichier ne mesurerait plus rien de la concurrence. Les deux
# transactions nomment donc le principal mandate; ce qui les departage est la
# singularite de l'amorcage et le verrou d'administration, ce qu'on veut
# eprouver ici. Qu'un principal ETRANGER au mandat soit refuse est etabli
# ailleurs, sequentiellement.
cat > "$TMP/conc_boot_2.sql" <<SQL
begin;
select bootstrap_normative_administrator(
  '$R1', 'FICTIF Racine 2', 'FICTIF — amorcage concurrent 2');
commit;
SQL
PGAPPNAME="$APP_A" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f $TMP/conc_boot_1.sql \
  >$TMP/boot1.log 2>&1 & B1=$!
session_detient_verrou "$APP_A"      # la racine 1 est posee, et retenue
PGAPPNAME="$APP_B" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f $TMP/conc_boot_2.sql \
  >$TMP/boot2.log 2>&1 & B2=$!
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
# L'ORDRE EST IMPOSE PAR DES BARRIERES, plus par des temporisations.
#
# Ce qu'il faut obtenir: A insere, garde sa transaction ouverte, et B tente
# son insertion PENDANT ce temps. Trois rendez-vous, tous observables:
#
#   1. A prend la barriere de rendez-vous       (verrou consultatif)
#   2. le shell attend que A la DETIENNE, puis lance B  (pg_locks)
#   3. B se met en attente sur cette barriere; A l'insere, puis la leve
#   4. A attend que B soit REELLEMENT BLOQUEE sur le verrou de portee
#      (pg_stat_activity) avant de valider
#
# La version precedente pariait: `sleep 0.3` pour lancer B apres A, et
# `pg_sleep(1.5)` pour retenir A. Si B demarrait trop tard, A validait la
# premiere, B voyait simplement la ligne deja la, et le scenario passait sans
# avoir rien mis en concurrence — verrou ou pas.
cat > "$TMP/conc_A.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
set local lock_timeout = '30s';
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   reason)
values ('$VERIF', 'FICTIF Relecteur', 'can_validate_normative_reference',
        'BE', 'EN 1992', '1-1', 'FICTIF — course A');
-- A a ecrit et retient le verrou de portee jusqu'au commit: le shell le voit
-- dans pg_locks et lance B. A ne valide qu'une fois B REELLEMENT bloquee.
select t_attendre_bloquee('$APP_B');
commit;
SQL
cat > "$TMP/conc_B.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
-- B ATTEND, elle n'expire plus. Le blocage est desormais prouve par la
-- barriere de A — qui ne valide qu'apres avoir OBSERVE B bloquee — et non
-- par un abandon au bout d'un delai. B peut donc aller au bout et montrer
-- ce qu'elle DECIDE une fois le verrou obtenu, ce qui est plus fort.
set local lock_timeout = '30s';
insert into normative_authorisation_grants
  (grantee_id, grantee_name, permission, country_code, standard_family, part,
   reason)
values ('$VERIF', 'FICTIF Relecteur', 'can_validate_normative_reference',
        'BE', 'EN 1992', '1-1', 'FICTIF — course B');
commit;
SQL
PGAPPNAME="$APP_A" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_A.sql" \
  >"$TMP/conc_a.log" 2>&1 & PA=$!
session_detient_verrou "$APP_A"     # A a insere, et retient

PGAPPNAME="$APP_B" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_B.sql" \
  >"$TMP/conc_b.log" 2>&1 & PB=$!
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
elif [[ "$SQLSTATE_B" != "$ERR_DOUBLON" ]]; then
  echoue "B a echoue en $SQLSTATE_B et non $ERR_DOUBLON: elle n'a pas refuse"
  echoue "  sur le fond apres avoir obtenu le verrou"
else
  # Ce que ce vert affirme, en toutes lettres: B a ete OBSERVEE bloquee (la
  # barriere de A l'exige pour valider), puis, le verrou obtenu, elle a vu
  # l'octroi de A et l'a refuse comme doublon de portee. Ordre seriel complet.
  echo "      ok: un octroi actif; B bloquee, puis refus de portee ($ERR_DOUBLON)"
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
-- BARRIERE: retenir jusqu'a ce que la revocation soit REELLEMENT bloquee sur
-- le verrou partage. Une temporisation de trois secondes pariait: trop peu et la
-- revocation passait sans se heurter a rien, trop et le test s'allongeait
-- sans rien gagner. Ici la fenetre dure exactement le temps qu'il faut, et
-- l'absence de blocage devient un ECHEC au lieu d'un vert silencieux.
select t_attendre_bloquee('$APP_B');
commit;
SQL
cat > "$TMP/conc_revoc.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
-- Elle ATTEND: son blocage est prouve par la barriere de la confirmation,
-- qui ne valide qu'apres l'avoir OBSERVEE bloquee. Un lock_timeout court
-- reintroduirait une course entre la duree du blocage et le seuil choisi.
set local lock_timeout = '30s';
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_ID', 'FICTIF — retrait pendant une confirmation en vol.');
commit;
SQL
PGAPPNAME="$APP_A" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_conf.sql" \
  >"$TMP/conc_conf.log" 2>&1 & PC=$!
session_detient_verrou "$APP_A"      # la confirmation a insere, et retient
PGAPPNAME="$APP_B" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_revoc.sql" \
  >"$TMP/conc_revoc.log" 2>&1
CR=$?
SQLSTATE_R="$(code_sqlstate "$TMP/conc_revoc.log")"
wait $PC; CC=$?
ACTIF_APRES=$("${PSQL[@]}" -X -q -tAc "
  select normative_grant_is_active('$GRANT_ID')::int")

CONFIRMEE=$("${PSQL[@]}" -X -q -tAc "
  select count(*) from normative_rule_confirmations
   where idempotency_key='FICTIF-conc-1'")
if [[ "$CONFIRMEE" != "1" || $CC -ne 0 ]]; then
  echoue "la confirmation en vol n'a pas abouti (code $CC)"
  grep -oE 'ERROR:.*' "$TMP/conc_conf.log" | head -1 | sed 's/^/        /'
elif [[ $CR -ne 0 ]]; then
  echoue "la revocation a echoue (${SQLSTATE_R:-?}) au lieu d'attendre son tour"
elif [[ "$ACTIF_APRES" != "0" ]]; then
  echoue "l'octroi est encore actif apres une revocation reussie"
else
  # Ce que ce vert affirme: la revocation a ete OBSERVEE bloquee (la
  # confirmation ne valide qu'a cette condition), puis, le verrou libere,
  # elle a abouti. Ordre seriel: confirmation d'abord, retrait ensuite —
  # jamais l'etat intermediaire ou les deux se croisent.
  echo "      ok: revocation bloquee, puis aboutie apres la confirmation"
fi

# ------------------------------------------------------------------------
# 3b. L'ordre INVERSE: la revocation tient le verrou, la confirmation suit.
#     Apres attente, la confirmation doit etre REFUSEE — l'habilitation
#     n'existe plus.
# ------------------------------------------------------------------------
echo "    scenario 3b: confirmation apres une revocation deja engagee"
# Un octroi NEUF. Le scenario 3a revoque desormais reellement le sien — il
# n'expire plus, il attend son tour et aboutit — et rejouer 3b sur le meme
# octroi echouerait faute d'habilitation, pas faute de concurrence.
GRANT_ID=$("${PSQL[@]}" -X -q -tAc "
  select set_config('request.jwt.claim.sub', '$ADMIN', true);
  insert into normative_authorisation_grants
    (grantee_id, grantee_name, permission, country_code, standard_family,
     part, reason)
  values ('$VERIF', 'FICTIF Relecteur', 'can_validate_normative_reference',
          'BE', 'EN 1992', '1-1', 'FICTIF — octroi neuf pour le scenario 3b')
  returning id" | tail -1)
cat > "$TMP/conc_revoc2.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_ID', 'FICTIF — retrait engage avant la confirmation.');
-- BARRIERE plutot que deux secondes d'espoir: retenir exactement jusqu'a ce
-- que la confirmation se heurte au verrou.
select t_attendre_bloquee('$APP_B');
commit;
SQL
cat > "$TMP/conc_conf2.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$VERIF', true);
select t_conc_confirmer('test.concurrence', 'FICTIF-conc-2');
commit;
SQL
PGAPPNAME="$APP_A" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_revoc2.sql" \
  >"$TMP/r2.log" 2>&1 & PR2=$!
session_detient_verrou "$APP_A"      # la revocation est engagee, et retient
PGAPPNAME="$APP_B" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/conc_conf2.sql" \
  >"$TMP/c2.log" 2>&1
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

# Les deux cotes attendaient 0,4 s puis se lancaient, en esperant partir
# ensemble. Ici A revoque B, RETIENT jusqu'a voir B bloquee sur le verrou
# d'administration, puis valide. B reprend alors et doit se heurter a la
# garde: retirer A la laisserait sans administrateur couvrant sa portee.
cat > "$TMP/dern_A.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN', true);
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_B', 'FICTIF — course croisee A');
select t_attendre_bloquee('$APP_B');
commit;
SQL
cat > "$TMP/dern_B.sql" <<SQL
\set VERBOSITY verbose
begin;
select set_config('request.jwt.claim.sub', '$ADMIN_B', true);
insert into normative_authorisation_revocations (grant_id, reason)
values ('$GRANT_A', 'FICTIF — course croisee B');
commit;
SQL
PGAPPNAME="$APP_A" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/dern_A.sql" \
  >"$TMP/dA.log" 2>&1 & DA=$!
session_detient_verrou "$APP_A"      # A a engage son retrait, et retient
PGAPPNAME="$APP_B" "${PSQL[@]}" -q -v ON_ERROR_STOP=1 -f "$TMP/dern_B.sql" \
  >"$TMP/dB.log" 2>&1 & DB=$!
wait $DA; CDA=$?
wait $DB; CDB=$?
# LES DEUX CODES SONT RETENUS AVANT TOUTE ASSERTION: c'est la premiere chose
# qu'on veut savoir quand ce scenario rougit, et elle disparait sinon.
CODES_CONCURRENTS="A(pid $DA)=$CDA B(pid $DB)=$CDB"

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
