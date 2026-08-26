-- =====================================================================
-- 0014 — LE QUATRE-YEUX EXPLICITE: PROPOSITION, APPROBATION, CONSOMMATION
-- =====================================================================
--
-- CE QUI MANQUAIT, ET QUI EST POSE ICI
-- -------------------------------------
-- 6.3c a mesure que deux « regards independants » se fabriquaient depuis UNE
-- connexion, par deux valeurs de GUC successives. 0013 a ferme cela par la
-- frontiere: un role applicatif ordinaire ne peut plus rien ecrire, donc pas
-- deux fois.
--
-- Mais fermer la porte n'est pas construire la piece. Le decompte a quatre
-- yeux vivait dans le domaine Python — `independent_regards()`, sur des
-- `verifier_id` distincts — et nulle part dans le schema. Tant qu'aucune
-- structure ne le porte, « deux regards » reste une PROPRIETE DU CODE
-- APPELANT, pas une garantie de la base.
--
-- QUATRE-YEUX SIGNIFIE ICI DEUX PRINCIPALS AU TOTAL: un proposant A, puis un
-- approbateur B distinct. Pas trois. Le contrat metier existant ne demande pas
-- deux approbateurs EN PLUS du proposant, et en ajouter un silencieusement
-- changerait la regle sans que personne l'ait decide.
--
-- LE CYCLE EST MINIMAL: PENDING -> APPROVED -> CONSUMED.
-- Aucun etat de rejet ni d'expiration n'est ajoute: ils n'existent pas dans le
-- contrat metier ecrit, et un etat qu'aucune regle ne remplit est un etat que
-- personne ne saura interpreter dans dix ans.
--
-- POURQUOI CETTE TABLE EST MUTABLE ALORS QUE TOUTES LES AUTRES SONT EN AJOUT
-- SEUL. Une machine a etats a besoin de transitions. La reponse n'est pas de
-- renoncer a l'immuabilite mais de la deplacer: TOUT est immuable SAUF les
-- trois colonnes que la transition en cours a le droit de poser, et un
-- declencheur refuse toute autre modification. Une decision consommee ne
-- bouge plus jamais.
--
-- LE VERROUILLAGE EST `FOR NO KEY UPDATE`, ET C'EST DELIBERE. `FOR UPDATE`
-- prend un verrou qui entre en conflit avec les verifications de cle etrangere
-- que d'autres transactions font sur les lignes referencees — c'est le chemin
-- classique vers un interblocage quand plusieurs tables se referencent. Ces
-- transitions ne touchent AUCUNE colonne de cle: `FOR NO KEY UPDATE` est le
-- verrou exact, et il laisse passer les verifications de FK concurrentes.
--
-- L'ATOMICITE NE REPOSE PAS SUR LE VERROU SEUL. Chaque transition est un
-- `UPDATE ... WHERE id = ... AND state = <etat attendu>`: deux approbations
-- concurrentes voient la meme ligne, une seule trouve `state = 'PENDING'`, et
-- la seconde met a jour zero ligne. Le verrou serialise; c'est la CONDITION
-- SUR L'ETAT qui decide. Un verrou sans relecture ne fait qu'attendre.
-- =====================================================================

grant create on schema public
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- ---------------------------------------------------------------------
-- 1. L'ETAT, ET LA DECISION
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'normative_decision_state') then
    create type normative_decision_state as enum ('PENDING', 'APPROVED', 'CONSUMED');
  end if;
end;
$$;

create table if not exists normative_authority_decisions (
  id uuid primary key default gen_random_uuid(),

  -- L'OBJET. Il est decrit ENTIEREMENT ici et n'est jamais deduit: une
  -- decision qui ne dirait pas sur quoi elle porte ne pourrait pas etre
  -- confrontee a la portee des habilitations invoquees.
  subject_kind    text not null,
  subject_id      text not null,
  org_id          uuid references organizations(id) on delete restrict,
  country_code    country_code not null,
  standard_family text not null,
  part            text not null,
  edition         text not null,
  permission      normative_permission not null,

  state normative_decision_state not null default 'PENDING',

  -- LA PROPOSITION
  proposer_id              uuid not null references auth.users(id),
  proposal_source_grant_id uuid not null
                           references normative_authorisation_grants(id)
                           on delete restrict,
  proposed_at              timestamptz not null default now(),

  -- L'APPROBATION
  approver_id              uuid references auth.users(id),
  approval_source_grant_id uuid references normative_authorisation_grants(id)
                           on delete restrict,
  approved_at              timestamptz,

  -- LA CONSOMMATION
  consumed_at    timestamptz,
  correlation_id uuid not null default gen_random_uuid(),
  reason         text not null,

  -- DEUX PRINCIPALS DISTINCTS, IMPOSE PAR POSTGRESQL ET NON PAR PYTHON.
  -- C'est la difference entre « notre code appelant y veille » et « la base
  -- refuse ». Un `CHECK` s'evalue a chaque ecriture, quel que soit l'appelant,
  -- et survit a la reecriture du code appelant.
  constraint decision_two_distinct_principals
    check (approver_id is null or approver_id <> proposer_id),

  constraint decision_is_motivated check (btrim(reason) <> ''),

  -- LA FORME DE CHAQUE ETAT. Sans elle, `state` serait une etiquette qu'on
  -- pourrait poser sans remplir ce qu'elle annonce: « APPROVED » sans
  -- approbateur, « CONSUMED » sans date. L'etat et ses colonnes ne peuvent
  -- plus diverger.
  constraint decision_state_is_complete check (
    (state = 'PENDING'
       and approver_id is null and approval_source_grant_id is null
       and approved_at is null and consumed_at is null)
    or (state = 'APPROVED'
       and approver_id is not null and approval_source_grant_id is not null
       and approved_at is not null and consumed_at is null)
    or (state = 'CONSUMED'
       and approver_id is not null and approval_source_grant_id is not null
       and approved_at is not null and consumed_at is not null))
);

comment on table normative_authority_decisions is
  'Le quatre-yeux EXPLICITE: une proposition par un principal authentifie, une '
  'approbation par un second principal distinct, une consommation unique. Les '
  'DEUX sources d''autorite invoquees sont conservees — sans elles on saurait '
  'QUI a decide, jamais AU TITRE DE QUOI.';

comment on column normative_authority_decisions.proposal_source_grant_id is
  'L''habilitation PRECISE invoquee par le proposant. Une personne peut en '
  'detenir plusieurs, de portees differentes: nommer la personne ne dit pas '
  'sous quelle autorite elle a agi.';
comment on column normative_authority_decisions.approval_source_grant_id is
  'L''habilitation PRECISE invoquee par l''approbateur. Elle doit couvrir le '
  'MEME objet et la MEME portee que la decision — pas « une autorite », celle '
  'qui convient.';
comment on column normative_authority_decisions.correlation_id is
  'Relie la decision aux evenements d''audit qu''elle produit. Pose a la '
  'creation et jamais modifie: une correlation qui change ne correle rien.';

create index if not exists normative_decisions_state_idx
  on normative_authority_decisions (state)
  where state <> 'CONSUMED';


-- ---------------------------------------------------------------------
-- 2. L'IMMUABILITE SAUF TRANSITION LEGALE
-- ---------------------------------------------------------------------
-- CE DECLENCHEUR EST LE PENDANT DE `forbid_mutation()` POUR UNE TABLE QUI DOIT
-- BOUGER. Il n'autorise que deux transitions, et seulement les colonnes que
-- chacune a le droit de poser. Tout le reste — l'objet, la portee, le
-- proposant, sa source, la correlation — est fige des la creation.
create or replace function check_normative_decision_transition() returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  -- LE SOCLE NE BOUGE JAMAIS. On le verifie colonne par colonne plutot que
  -- par un `row(old.*) is distinct from row(new.*)`: la comparaison globale
  -- dirait « quelque chose a change » sans dire quoi, et un diagnostic qui ne
  -- nomme pas la colonne fait perdre l'heure qu'il devait faire gagner.
  if new.id              is distinct from old.id
     or new.subject_kind    is distinct from old.subject_kind
     or new.subject_id      is distinct from old.subject_id
     or new.org_id          is distinct from old.org_id
     or new.country_code    is distinct from old.country_code
     or new.standard_family is distinct from old.standard_family
     or new.part            is distinct from old.part
     or new.edition         is distinct from old.edition
     or new.permission      is distinct from old.permission
     or new.proposer_id     is distinct from old.proposer_id
     or new.proposal_source_grant_id is distinct from old.proposal_source_grant_id
     or new.proposed_at     is distinct from old.proposed_at
     or new.correlation_id  is distinct from old.correlation_id
     or new.reason          is distinct from old.reason then
    raise exception
      'decision %: son objet, sa portee, son proposant, sa source et sa '
      'correlation sont figes a la creation. Seul l''etat progresse.', old.id
      using errcode = 'insufficient_privilege';
  end if;

  if old.state = 'PENDING' and new.state = 'APPROVED' then
    return new;
  elsif old.state = 'APPROVED' and new.state = 'CONSUMED' then
    -- L'approbation ne se rejoue pas au moment de la consommation.
    if new.approver_id is distinct from old.approver_id
       or new.approval_source_grant_id is distinct from old.approval_source_grant_id
       or new.approved_at is distinct from old.approved_at then
      raise exception
        'decision %: la consommation ne modifie pas l''approbation.', old.id
        using errcode = 'insufficient_privilege';
    end if;
    return new;
  end if;

  raise exception
    'decision %: transition « % » -> « % » interdite. Le cycle est '
    'PENDING -> APPROVED -> CONSUMED, et il ne remonte pas.',
    old.id, old.state, new.state
    using errcode = 'check_violation';
end;
$$;

create trigger normative_decisions_transitions_are_checked
  before update on normative_authority_decisions
  for each row execute function check_normative_decision_transition();

create or replace function forbid_decision_delete() returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  raise exception
    'une decision d''autorite ne s''efface pas: elle explique ce qui a ete '
    'engage, et l''effacer effacerait la preuve de la decision.'
    using errcode = 'insufficient_privilege';
end;
$$;

create trigger normative_decisions_are_not_deletable
  before delete on normative_authority_decisions
  for each row execute function forbid_decision_delete();


-- ---------------------------------------------------------------------
-- 3. LES TROIS PRIMITIVES — l'acteur vient du contexte, jamais du parametre
-- ---------------------------------------------------------------------
-- AUCUNE NE RECOIT L'ACTEUR EN PARAMETRE. C'est la lecon de 6.3c: un UUID
-- recu est une donnee, jamais une preuve d'identite. `p_subject_*`,
-- `p_country`, `p_edition` sont des DONNEES — ce sur quoi porte la decision —
-- et n'ont aucune valeur probante; l'acteur, lui, est derive.

-- `normative_decision_propose` — A propose.
create or replace function normative_decision_propose(
  p_subject_kind text,
  p_subject_id   text,
  p_org_id       uuid,
  p_country      country_code,
  p_family       text,
  p_part         text,
  p_edition      text,
  p_permission   normative_permission,
  p_reason       text
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  source normative_authorisation_grants;
  nouvelle uuid;
begin
  acteur := normative_authenticated_actor();

  -- L'HABILITATION EST CONSOMMEE, PAS SEULEMENT RESOLUE: le motif
  -- « resoudre -> verrouiller la chaine -> relire » de 0012 s'applique ici
  -- comme partout ailleurs. Une proposition faite sous une habilitation qu'une
  -- autre transaction est en train de retirer ne doit pas exister.
  source := consume_normative_authorisation(
    acteur, p_permission, p_country, p_family, p_part, p_edition);
  if source.id is null then
    raise exception
      'proposition refusee: % ne detient aucune habilitation efficace « % » '
      'couvrant %/%/%/%.',
      acteur, p_permission, p_country, p_family, p_part, p_edition
      using errcode = 'insufficient_privilege';
  end if;

  insert into normative_authority_decisions
    (subject_kind, subject_id, org_id, country_code, standard_family, part,
     edition, permission, state, proposer_id, proposal_source_grant_id, reason)
  values
    (p_subject_kind, p_subject_id, p_org_id, p_country, p_family, p_part,
     p_edition, p_permission, 'PENDING', acteur, source.id, p_reason)
  returning id into nouvelle;

  perform log_normative_event(
    'normative.decision.proposed', 'normative_authority_decisions', nouvelle,
    jsonb_build_object('proposer_id', acteur,
                       'proposal_source_grant_id', source.id,
                       'subject_kind', p_subject_kind,
                       'subject_id', p_subject_id,
                       'scope', jsonb_build_object(
                         'country_code', p_country, 'standard_family', p_family,
                         'part', p_part, 'edition', p_edition),
                       'correlation_id',
                       (select correlation_id from normative_authority_decisions
                         where id = nouvelle)),
    acteur);
  return nouvelle;
end;
$$;

-- `normative_decision_approve` — B approuve. B n'est pas A.
create or replace function normative_decision_approve(p_decision uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  d normative_authority_decisions;
  source normative_authorisation_grants;
  n int;
begin
  acteur := normative_authenticated_actor();

  -- `FOR NO KEY UPDATE`: la transition ne touche aucune colonne de cle, et ce
  -- verrou n'entre pas en conflit avec les verifications de cle etrangere que
  -- d'autres transactions font sur `organizations` ou sur les octrois. Un
  -- `FOR UPDATE` ici rouvrirait l'interblocage deja rencontre ailleurs.
  select * into d from normative_authority_decisions
   where id = p_decision for no key update;
  if not found then
    raise exception 'decision % introuvable', p_decision
      using errcode = 'foreign_key_violation';
  end if;

  if d.state <> 'PENDING' then
    raise exception
      'decision %: elle est deja « % ». Une decision ne s''approuve qu''une '
      'fois.', d.id, d.state
      using errcode = 'unique_violation';
  end if;

  -- DEUX PRINCIPALS. Le refus est ici pour porter un message utile; la
  -- CONTRAINTE de table le refuserait de toute facon, et c'est elle qui fait
  -- la garantie — un message peut etre contourne en changeant d'appelant, une
  -- contrainte non.
  if acteur = d.proposer_id then
    raise exception
      'decision %: le proposant ne peut pas etre son propre approbateur. Deux '
      'regards exigent deux principals.', d.id
      using errcode = 'insufficient_privilege';
  end if;

  source := consume_normative_authorisation(
    acteur, d.permission, d.country_code, d.standard_family, d.part, d.edition);
  if source.id is null then
    raise exception
      'approbation refusee: % ne detient aucune habilitation efficace « % » '
      'couvrant %/%/%/%.',
      acteur, d.permission, d.country_code, d.standard_family, d.part, d.edition
      using errcode = 'insufficient_privilege';
  end if;

  -- LA SOURCE DU PROPOSANT DOIT ETRE ENCORE EFFICACE. Une proposition faite
  -- sous une autorite depuis revoquee n'est pas une proposition valide qu'un
  -- second regard viendrait completer: c'est une proposition sans autorite.
  if not normative_grant_is_effective(d.proposal_source_grant_id) then
    raise exception
      'approbation refusee: l''habilitation % invoquee par le proposant n''est '
      'plus efficace — elle-meme ou l''un de ses ancetres a ete revoque ou a '
      'expire depuis la proposition.', d.proposal_source_grant_id
      using errcode = 'insufficient_privilege';
  end if;

  -- LA TRANSITION EST CONDITIONNELLE SUR L'ETAT. C'est elle qui decide, pas le
  -- verrou: deux approbations concurrentes se serialisent sur le verrou, puis
  -- la seconde ne trouve plus « PENDING » et met a jour ZERO ligne.
  update normative_authority_decisions
     set state = 'APPROVED', approver_id = acteur,
         approval_source_grant_id = source.id, approved_at = now()
   where id = d.id and state = 'PENDING';
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception
      'decision %: approbation concurrente — l''etat a change entre la '
      'lecture et l''ecriture.', d.id
      using errcode = 'unique_violation';
  end if;

  perform log_normative_event(
    'normative.decision.approved', 'normative_authority_decisions', d.id,
    jsonb_build_object('approver_id', acteur,
                       'approval_source_grant_id', source.id,
                       'proposer_id', d.proposer_id,
                       'proposal_source_grant_id', d.proposal_source_grant_id,
                       'correlation_id', d.correlation_id),
    acteur);
end;
$$;

-- `normative_decision_consume` — la decision produit son effet, une fois.
create or replace function normative_decision_consume(p_decision uuid)
returns normative_authority_decisions
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  d normative_authority_decisions;
  n int;
begin
  acteur := normative_authenticated_actor();

  select * into d from normative_authority_decisions
   where id = p_decision for no key update;
  if not found then
    raise exception 'decision % introuvable', p_decision
      using errcode = 'foreign_key_violation';
  end if;

  if d.state <> 'APPROVED' then
    raise exception
      'decision %: elle est « % ». Seule une decision APPROUVEE se consomme, '
      'et elle ne se consomme qu''une fois.', d.id, d.state
      using errcode = 'unique_violation';
  end if;

  -- LES DEUX SOURCES DOIVENT ETRE ENCORE EFFICACES A LA CONSOMMATION.
  --
  -- C'est le choix par defaut, et il est explicite: tant qu'aucune definition
  -- metier contraire n'est ecrite, une decision ne produit son effet que si
  -- les deux autorites qui l'ont portee valent encore. L'inverse — « une fois
  -- approuvee, elle vaut pour toujours » — transformerait une approbation en
  -- droit acquis que la revocation ne rattraperait plus.
  if not normative_grant_is_effective(d.proposal_source_grant_id) then
    raise exception
      'consommation refusee: l''habilitation % du proposant n''est plus '
      'efficace.', d.proposal_source_grant_id
      using errcode = 'insufficient_privilege';
  end if;
  if not normative_grant_is_effective(d.approval_source_grant_id) then
    raise exception
      'consommation refusee: l''habilitation % de l''approbateur n''est plus '
      'efficace.', d.approval_source_grant_id
      using errcode = 'insufficient_privilege';
  end if;

  update normative_authority_decisions
     set state = 'CONSUMED', consumed_at = now()
   where id = d.id and state = 'APPROVED';
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception
      'decision %: consommation concurrente — l''etat a change entre la '
      'lecture et l''ecriture.', d.id
      using errcode = 'unique_violation';
  end if;

  perform log_normative_event(
    'normative.decision.consumed', 'normative_authority_decisions', d.id,
    jsonb_build_object('consumed_by', acteur,
                       'proposer_id', d.proposer_id,
                       'approver_id', d.approver_id,
                       'proposal_source_grant_id', d.proposal_source_grant_id,
                       'approval_source_grant_id', d.approval_source_grant_id,
                       'correlation_id', d.correlation_id),
    acteur);

  select * into d from normative_authority_decisions where id = p_decision;
  return d;
end;
$$;


-- ---------------------------------------------------------------------
-- 4. PROPRIETE, ACL, RLS
-- ---------------------------------------------------------------------
-- L'ORDRE EST IMPOSE, ET IL N'EST PAS INTUITIF. Le transfert de propriete se
-- fait SOUS LE MIGRATEUR, qui possede encore la table: emis apres `set role
-- eurostruct_normative_writer`, il echoue sur « must be owner of table » —
-- le writer n'est pas encore proprietaire, c'est justement ce qu'on lui donne.
-- Les policies, elles, exigent la propriete: elles viennent APRES, sous le
-- writer devenu proprietaire.
alter table normative_authority_decisions owner to eurostruct_normative_writer;

set role eurostruct_normative_writer;

alter table normative_authority_decisions enable row level security;
alter table normative_authority_decisions force row level security;

-- LE BACKEND D'AUTORITE NE RECOIT AUCUN PRIVILEGE DE TABLE. Tout passe par les
-- trois primitives, qui sont SECURITY DEFINER: c'est la seule facon de
-- garantir que l'acteur est derive et jamais fourni. Lui donner INSERT
-- rouvrirait exactement le chemin que 0013 a ferme.
create policy decisions_writer on normative_authority_decisions
  for all to eurostruct_normative_writer using (true) with check (true);
create policy decisions_governance_read on normative_authority_decisions
  for select to normative_governance using (true);

reset role;

grant select on normative_authority_decisions to normative_governance;

revoke all on function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission, text)
  from public;
revoke all on function normative_decision_approve(uuid) from public;
revoke all on function normative_decision_consume(uuid) from public;

alter function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission, text)
  owner to eurostruct_normative_writer;
alter function normative_decision_approve(uuid)
  owner to eurostruct_normative_writer;
alter function normative_decision_consume(uuid)
  owner to eurostruct_normative_writer;

grant execute on function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission, text)
  to eurostruct_authority_backend;
grant execute on function normative_decision_approve(uuid)
  to eurostruct_authority_backend;
grant execute on function normative_decision_consume(uuid)
  to eurostruct_authority_backend;


-- ---------------------------------------------------------------------
-- 5. LES ASSERTIONS POST-MIGRATION
-- ---------------------------------------------------------------------
-- UN `GRANT`, UN `REVOKE`, UN CHANGEMENT DE PROPRIETAIRE OU UNE POLICY PEUVENT
-- N'AVOIR AUCUN EFFET SANS LEVER D'ERREUR. PostgreSQL se contente d'un
-- WARNING quand l'emetteur n'a pas le droit. Ce piege s'est presente trois
-- fois dans ce jalon, et chaque fois il a laisse croire qu'une garde etait
-- posee alors qu'elle ne l'etait pas.
--
-- La migration verifie donc, dans les catalogues, que ce qu'elle a demande a
-- bien eu lieu — et refuse de se declarer appliquee sinon.
do $$
declare
  ecarts text[] := array[]::text[];
  o text;
begin
  select pg_get_userbyid(c.relowner) into o
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relname = 'normative_authority_decisions';
  if o <> 'eurostruct_normative_writer' then
    ecarts := ecarts || format(
      'la table des decisions appartient a « %s » et non a une autorite', o);
  end if;

  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                  where n.nspname = 'public'
                    and c.relname = 'normative_authority_decisions'
                    and c.relrowsecurity and c.relforcerowsecurity) then
    ecarts := ecarts || 'la table des decisions n''est pas en RLS forcee';
  end if;

  if has_table_privilege('eurostruct_authority_backend',
                         'normative_authority_decisions', 'INSERT')
     or has_table_privilege('normative_backend',
                            'normative_authority_decisions', 'INSERT') then
    ecarts := ecarts || 'un role applicatif detient INSERT sur les decisions: '
                        'les primitives ne sont plus le seul chemin';
  end if;

  if has_function_privilege('public', 'normative_decision_approve(uuid)', 'EXECUTE') then
    ecarts := ecarts || 'normative_decision_approve est executable par PUBLIC';
  end if;
  if not has_function_privilege('eurostruct_authority_backend',
                                'normative_decision_approve(uuid)', 'EXECUTE') then
    ecarts := ecarts || 'le backend authentifie n''atteint pas '
                        'normative_decision_approve: le chemin nominal est ferme';
  end if;

  if not exists (select 1 from pg_trigger t
                   join pg_class c on c.oid = t.tgrelid
                  where c.relname = 'normative_authority_decisions'
                    and t.tgname = 'normative_decisions_transitions_are_checked') then
    ecarts := ecarts || 'le declencheur de transition est absent';
  end if;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'migration 0014 non appliquee correctement: %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;


revoke create on schema public
  from eurostruct_normative_writer, eurostruct_normative_bootstrap;
