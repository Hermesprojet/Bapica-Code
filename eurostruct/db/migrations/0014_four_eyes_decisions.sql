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

-- ---------------------------------------------------------------------
-- UNE SEULE TRANSACTION, ET UNE INSCRIPTION AU REGISTRE
-- ---------------------------------------------------------------------
-- MESURE DU 26/08, roundtrip sur base ephemere: 10 migrations sur 14 etaient
-- constatees « deja appliquee » au second passage, et CES QUATRE etaient
-- REJOUEES. Elles n'appelaient pas `normative_migration_applied()`, donc le
-- registre n'en gardait aucune trace. Deux consequences, l'une et l'autre
-- serieuses:
--
--   * tout deploiement ulterieur les rejoue. Ce ne sont pas des scripts
--     idempotents par construction: elles transferent des proprietes, posent
--     des policies et retirent des droits;
--   * la protection « on ne peut pas les appliquer hors du runner » disparait.
--     C'est la substitution de `:'esc_migration_id'` qui la porte: sans elle,
--     `psql -f` les avale sans rien exiger.
--
-- Et sans `begin`/`commit`, une erreur au milieu du fichier laissait la moitie
-- des changements en place — les dix migrations precedentes s'en gardent
-- toutes.
begin;

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

-- ---------------------------------------------------------------------
-- LE VERROU DE CHAINE, PARTAGE — sans lui, l'approbation et la consommation
-- IGNORENT une revocation en vol
-- ---------------------------------------------------------------------
-- MESURE AVANT CORRECTION. Le controle `revocation-pendant-consommation` a
-- ete observe ROUGE: une revocation parquee, transaction ouverte et verrou de
-- ligne en main, n'a JAMAIS bloque la consommation d'une decision qui reposait
-- sur l'habilitation en cours de retrait. La consommation relisait
-- `normative_grant_is_effective()` — qui ne prend AUCUN verrou et lit un
-- instantane ou la revocation non validee n'existe pas encore.
--
-- On pourrait plaider que l'ordre seriel « consommer puis revoquer » est
-- explicable. 0010 a explicitement refuse ce raisonnement pour les
-- confirmations: le declencheur de revocation prend un verrou consultatif
-- EXCLUSIF sur `grantrow:<octroi>` precisement pour qu'une ecriture normative
-- en vol ne puisse pas se glisser sous un etat intermediaire. Consommer une
-- decision est une ecriture normative de meme poids qu'une confirmation. Le
-- protocole doit donc etre le meme, sans quoi une porte reste ouverte a cote
-- d'une porte fermee.
--
-- L'ORDRE DE PRISE EST CELUI DES IDENTIFIANTS, sur l'UNION des chaines, pour
-- que deux consommations concurrentes ne prennent jamais les memes verrous
-- dans deux ordres differents. On ne prend que des verrous CONSULTATIFS: ces
-- tables n'accordent aucun UPDATE, donc aucun verrou de ligne n'y est
-- disponible — c'est le fondement de leur immuabilite, et la raison pour
-- laquelle 0010 avait deja fait ce choix. Aucun verrou de ligne n'est pris sur
-- `organizations`: le deadlock corrige anterieurement n'est pas reintroduit.
create or replace function normative_lock_grant_chains(variadic p_grants uuid[])
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  a uuid;
begin
  for a in
    with recursive chaine as (
      select g.id, g.parent_grant_id from normative_authorisation_grants g
       where g.id = any(p_grants)
      union all
      select p.id, p.parent_grant_id from normative_authorisation_grants p
        join chaine c on p.id = c.parent_grant_id
    )
    select distinct id from chaine order by 1
  loop
    perform pg_advisory_xact_lock_shared(
      hashtext('eurostruct.normative.grantrow:' || a::text));
  end loop;
end;
$$;

comment on function normative_lock_grant_chains is
  'Prend le verrou consultatif PARTAGE sur toute la chaine d''ascendance des '
  'octrois donnes, dans l''ordre des identifiants. C''est le pendant du verrou '
  'EXCLUSIF que prend le declencheur de revocation: les deux ne peuvent donc '
  'pas s''ignorer, et aucune decision ne se consomme sous une autorite qu''une '
  'transaction concurrente est en train de retirer.';


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
  --
  -- Le verrou de chaine est pris AVANT la relecture. `consume_normative_
  -- authorisation` a deja verrouille la chaine de L'APPROBATEUR; celle du
  -- PROPOSANT ne l'etait pas, et une revocation en vol y serait restee
  -- invisible. Ces verrous sont PARTAGES: deux approbations concurrentes ne
  -- s'interbloquent pas, et seule une revocation — qui prend l'exclusif —
  -- s'oppose a elles.
  perform normative_lock_grant_chains(d.proposal_source_grant_id);

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
  -- LE VERROU AVANT LA LECTURE, jamais apres. Relire l'efficacite sans verrou
  -- revient a lire un instantane d'ou une revocation en vol est absente.
  perform normative_lock_grant_chains(
    d.proposal_source_grant_id, d.approval_source_grant_id);

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
-- Le verrou de chaine est un AUXILIAIRE des primitives, jamais une porte:
-- PUBLIC n'en recoit rien et aucun role applicatif ne le recoit non plus. Il
-- n'est appele que depuis les primitives SECURITY DEFINER, sous le writer.
revoke all on function normative_lock_grant_chains(uuid[]) from public;
-- LES DEUX DECLENCHEURS AUSSI. Ils ne sont pas SECURITY DEFINER, mais la regle
-- posee en 0011 vaut pour eux comme pour les autres: une fonction que PUBLIC
-- peut executer et que le MIGRATEUR peut remplacer n'est pas une garde, c'est
-- une convention. Les laisser dehors aurait fait un trou dans l'enumeration
-- que le harnais confronte.
revoke all on function check_normative_decision_transition() from public;
revoke all on function forbid_decision_delete() from public;

alter function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission, text)
  owner to eurostruct_normative_writer;
alter function normative_decision_approve(uuid)
  owner to eurostruct_normative_writer;
alter function normative_decision_consume(uuid)
  owner to eurostruct_normative_writer;
alter function normative_lock_grant_chains(uuid[])
  owner to eurostruct_normative_writer;
alter function check_normative_decision_transition()
  owner to eurostruct_normative_writer;
alter function forbid_decision_delete()
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
-- CHAQUE LITTERAL EST TYPE `::text`, ET CE N'EST PAS UNE COQUETTERIE.
-- `text[] || 'litteral'` est AMBIGU: PostgreSQL essaie d'abord
-- `anyarray || anyarray` et tente de convertir le litteral non type en
-- tableau. Mesure: la falsification N1 a rendu PUBLIC executable sur
-- `normative_decision_approve`; l'assertion a bien detecte l'ecart, puis a
-- echoue sur « malformed array literal » au lieu de le NOMMER. Une garde qui
-- se declenche sans dire ce qui manque coute l'heure qu'elle devait faire
-- gagner. Les branches ecrites avec `format()` n'avaient pas le probleme:
-- `format()` rend un `text` deja type.
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
    ecarts := ecarts || 'la table des decisions n''est pas en RLS forcee'::text;
  end if;

  if has_table_privilege('eurostruct_authority_backend',
                         'normative_authority_decisions', 'INSERT')
     or has_table_privilege('normative_backend',
                            'normative_authority_decisions', 'INSERT') then
    ecarts := ecarts || ('un role applicatif detient INSERT sur les decisions: '
                         'les primitives ne sont plus le seul chemin')::text;
  end if;

  if has_function_privilege('public', 'normative_decision_approve(uuid)', 'EXECUTE') then
    ecarts := ecarts || 'normative_decision_approve est executable par PUBLIC'::text;
  end if;
  if not has_function_privilege('eurostruct_authority_backend',
                                'normative_decision_approve(uuid)', 'EXECUTE') then
    ecarts := ecarts || ('le backend authentifie n''atteint pas '
                         'normative_decision_approve: le chemin nominal est ferme')::text;
  end if;

  if not exists (select 1 from pg_trigger t
                   join pg_class c on c.oid = t.tgrelid
                  where c.relname = 'normative_authority_decisions'
                    and t.tgname = 'normative_decisions_transitions_are_checked') then
    ecarts := ecarts || 'le declencheur de transition est absent'::text;
  end if;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'migration 0014 non appliquee correctement: %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- POSTCONDITION DE 0014 — la surface des decisions, lue dans le catalogue
-- ---------------------------------------------------------------------
-- MEME RAISON QUE POUR 0012: PostgreSQL 16 n'echoue pas sur un GRANT ou un
-- REVOKE emis sans le droit requis, il emet un WARNING et ne fait rien. Les
-- douze commandes de privilege de cette migration pouvaient donc etre sans
-- effet, et la migration se declarer appliquee.
--
-- ELLE LIT LES ACL ET LES LIGNES DE CATALOGUE. `has_table_privilege()` seul
-- serait trompeur: le proprietaire repond « oui » sans qu'aucun octroi
-- n'existe, et une policy manquante ne se voit pas du tout dans une reponse
-- de privilege — sous FORCE RLS elle rend zero ligne, c'est-a-dire une
-- reponse, pas une erreur.
create or replace function assert_0014_decisions_surface() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  ecarts text[] := array[]::text[];
  attendus text[][] := array[
    -- fonction                            | secdef | roles EXECUTE
    ['normative_decision_propose',           'true',
     'eurostruct_authority_backend,eurostruct_normative_writer'],
    ['normative_decision_approve',           'true',
     'eurostruct_authority_backend,eurostruct_normative_writer'],
    ['normative_decision_consume',           'true',
     'eurostruct_authority_backend,eurostruct_normative_writer'],
    ['normative_lock_grant_chains',          'true',
     'eurostruct_normative_writer'],
    ['check_normative_decision_transition',  'false',
     'eurostruct_normative_writer'],
    ['forbid_decision_delete',               'false',
     'eurostruct_normative_writer']
  ];
  declencheurs text[] := array['normative_decisions_are_not_deletable',
                               'normative_decisions_transitions_are_checked'];
  contraintes text[] := array['decision_is_motivated',
                              'decision_state_is_complete',
                              'decision_two_distinct_principals'];
  i int; n_match int;
  nom text; secdef_attendu boolean; roles_attendus text[];
  f_oid oid; f_owner_oid oid;
  f_owner text; f_secdef boolean; f_cfg text[]; f_acl aclitem[];
  reels text[];
  t_owner text; t_rls boolean; t_force boolean; t_acl aclitem[];
  r record;
begin
  -- ---------------- A. LES SIX FONCTIONS ----------------
  for i in 1 .. array_length(attendus, 1) loop
    nom := attendus[i][1];
    secdef_attendu := attendus[i][2]::boolean;
    roles_attendus := string_to_array(attendus[i][3], ',');

    select count(*) into n_match
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;
    if n_match = 0 then
      ecarts := ecarts || format(
        'AUTHORITY_0014_FUNCTION_MISSING: %s est absente du schema public', nom);
      continue;
    elsif n_match > 1 then
      ecarts := ecarts || format(
        'AUTHORITY_0014_FUNCTION_AMBIGUOUS: %s existe en %s exemplaires; '
        'chacun porte ses propres ACL', nom, n_match);
      continue;
    end if;

    select p.oid, p.proowner, pg_get_userbyid(p.proowner), p.prosecdef,
           p.proconfig, p.proacl
      into f_oid, f_owner_oid, f_owner, f_secdef, f_cfg, f_acl
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;

    if f_owner <> 'eurostruct_normative_writer' then
      ecarts := ecarts || format(
        'AUTHORITY_0014_OWNER_MISMATCH: %s appartient a « %s », attendu '
        '« eurostruct_normative_writer »', nom, f_owner);
    end if;
    if f_secdef is distinct from secdef_attendu then
      ecarts := ecarts || format(
        'AUTHORITY_0014_SECURITY_DEFINER_MISMATCH: %s a prosecdef=%s, attendu %s',
        nom, f_secdef, secdef_attendu);
    end if;
    if f_cfg is null
       or not exists (select 1 from unnest(f_cfg) c where c like 'search\_path=%')
    then
      ecarts := ecarts || format(
        'AUTHORITY_0014_SEARCH_PATH_UNPINNED: %s n''a pas de search_path fixe', nom);
    end if;
    -- L'ACL `NULL` N'EST PAS « AUCUN PRIVILEGE », ET LA DIFFERENCE EST TOUT.
    --
    -- Mesure sur PostgreSQL 16, sonde dediee:
    --
    --   acldefault('f', owner) = {=X/owner, owner=X/owner}
    --
    -- L'entree `=X` EST `PUBLIC EXECUTE`. Une fonction dont `proacl` vaut
    -- NULL est donc executable par tout le monde — verifie en appelant
    -- reellement `select f_ordinaire()` sous un role ordinaire: elle rend 1.
    -- Pour une table, une sequence ou un schema, la valeur par defaut ne
    -- donne rien a PUBLIC; la meme lecture y serait sans consequence, et
    -- c'est precisement ce qui rend l'erreur facile a commettre.
    --
    -- ON N'INTERROGE DONC JAMAIS `aclexplode(proacl)` SEUL pour conclure que
    -- PUBLIC ne detient rien. Deux lectures, chacune a sa place:
    --
    --   * PUBLIC          -> `has_function_privilege('public', ...)`, qui est
    --                        le privilege EFFECTIF et couvre le cas NULL.
    --                        La propriete ne fausse pas la reponse: PUBLIC ne
    --                        possede rien;
    --   * roles nommes    -> les lignes d'ACL, avec les droits par defaut
    --                        DEVELOPPES par `acldefault`. `has_*_privilege`
    --                        y repondrait « oui » pour le proprietaire sans
    --                        qu'aucun octroi n'existe.
    if has_function_privilege('public', f_oid, 'EXECUTE') then
      ecarts := ecarts || format(
        'AUTHORITY_0014_PUBLIC_EXECUTE: PUBLIC detient EXECUTE sur %s '
        '(proacl %s). Verifie par le privilege EFFECTIF, qui couvre le cas '
        'de l''ACL absente', nom,
        case when f_acl is null then 'NULL — droits par defaut, donc =X'
             else 'explicite' end);
    end if;

    -- LE DEVELOPPEMENT PAR `acldefault` A ETE RETIRE, ET C'EST UNE MESURE.
    --
    -- Il y figurait pour qu'une ACL NULL ne se lise pas « aucun octroi ». Or
    -- sa neutralisation a SURVECU a la mutation, et l'examen dit pourquoi:
    -- avec le developpement, une ACL NULL rend {proprietaire}; sans lui, elle
    -- rend {}. Les DEUX different de l'ensemble attendu, donc les deux
    -- produisent le meme ecart. Le developpement ne changeait rien
    -- d'observable — et l'ecart PUBLIC, lui, est deja porte par le controle
    -- du privilege EFFECTIF juste au-dessus.
    --
    -- Garder du code qu'aucune mutation ne peut falsifier, c'est garder une
    -- garantie qu'on ne verifie plus. On le retire donc, et on ecrit
    -- pourquoi plutot que de le laisser rassurer.
    select coalesce(array_agg(g.rolname::text order by g.rolname), array[]::text[])
      into reels
      from aclexplode(f_acl) a
      join pg_roles g on g.oid = a.grantee
     where a.privilege_type = 'EXECUTE';
    if reels <> (select array_agg(x order by x) from unnest(roles_attendus) x) then
      ecarts := ecarts || format(
        'AUTHORITY_0014_EXECUTE_ACL_MISMATCH: %s accorde EXECUTE a {%s}, '
        'attendu {%s}', nom, array_to_string(reels, ','),
        array_to_string(roles_attendus, ','));
    end if;
  end loop;

  -- ---------------- B. LA TABLE DES DECISIONS ----------------
  select pg_get_userbyid(c.relowner), c.relrowsecurity, c.relforcerowsecurity,
         c.relacl
    into t_owner, t_rls, t_force, t_acl
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relname = 'normative_authority_decisions';

  if t_owner is null then
    ecarts := ecarts || 'AUTHORITY_0014_TABLE_MISSING: '
      'normative_authority_decisions est absente';
  else
    if t_owner <> 'eurostruct_normative_writer' then
      ecarts := ecarts || format(
        'AUTHORITY_0014_TABLE_OWNER_MISMATCH: la table appartient a « %s »',
        t_owner);
    end if;
    if not t_rls then
      ecarts := ecarts || 'AUTHORITY_0014_RLS_DISABLED: '
        'row level security n''est pas activee sur la table des decisions';
    end if;
    -- FORCE, ET PAS SEULEMENT ENABLE. Sans FORCE, le PROPRIETAIRE echappe aux
    -- policies — et le proprietaire est precisement le role sous lequel les
    -- primitives SECURITY DEFINER s'executent.
    if not t_force then
      ecarts := ecarts || 'AUTHORITY_0014_FORCE_RLS_DISABLED: '
        'FORCE ROW LEVEL SECURITY n''est pas posee: le proprietaire echappe '
        'aux policies, or c''est sous lui que tournent les primitives';
    end if;

    -- AUCUNE ECRITURE DIRECTE POUR UN ROLE ORDINAIRE. Tout passe par les
    -- trois primitives; un INSERT direct rouvrirait le chemin que 0013 ferme.
    for r in
      select g.rolname, string_agg(distinct a.privilege_type, ',' order by
                                   a.privilege_type) as privs
        from aclexplode(t_acl) a
        left join pg_roles g on g.oid = a.grantee
       where a.privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
         and coalesce(g.rolname, 'PUBLIC') <> 'eurostruct_normative_writer'
       group by g.rolname
    loop
      ecarts := ecarts || format(
        'AUTHORITY_0014_DIRECT_WRITE_GRANTED: « %s » detient {%s} en direct '
        'sur normative_authority_decisions; seules les trois primitives '
        'doivent ecrire', coalesce(r.rolname, 'PUBLIC'), r.privs);
    end loop;
  end if;

  -- ---------------- C. LES POLICIES, ROLES ET COMMANDES EXACTS -----------
  -- UNE POLICY MANQUANTE NE SE VOIT PAS DANS UN PRIVILEGE. Sous FORCE RLS,
  -- une table sans policy applicable rend ZERO LIGNE — une reponse, pas une
  -- erreur (fait mesure). C'est pourquoi elles sont verifiees ici, une a une,
  -- avec leur commande et leur role.
  if not exists (
    select 1 from pg_policy pol join pg_class c on c.oid = pol.polrelid
     where c.relname = 'normative_authority_decisions'
       and pol.polname = 'decisions_writer'
       and pol.polcmd = '*' and pol.polpermissive
       and (select array_agg(rr.rolname::text order by rr.rolname) from pg_roles rr
             where rr.oid = any(pol.polroles))
           = array['eurostruct_normative_writer'])
  then
    ecarts := ecarts || 'AUTHORITY_0014_POLICY_MISMATCH: '
      'decisions_writer absente, non permissive, d''une autre commande que ALL, '
      'ou portant d''autres roles que eurostruct_normative_writer';
  end if;
  if not exists (
    select 1 from pg_policy pol join pg_class c on c.oid = pol.polrelid
     where c.relname = 'normative_authority_decisions'
       and pol.polname = 'decisions_governance_read'
       and pol.polcmd = 'r' and pol.polpermissive
       and (select array_agg(rr.rolname::text order by rr.rolname) from pg_roles rr
             where rr.oid = any(pol.polroles))
           = array['normative_governance'])
  then
    ecarts := ecarts || 'AUTHORITY_0014_POLICY_MISMATCH: '
      'decisions_governance_read absente, non permissive, d''une autre '
      'commande que SELECT, ou portant d''autres roles que normative_governance';
  end if;

  -- ---------------- D. DECLENCHEURS PRESENTS **ET** ACTIVES ---------------
  foreach nom in array declencheurs loop
    if not exists (
      select 1 from pg_trigger t join pg_class c on c.oid = t.tgrelid
       where c.relname = 'normative_authority_decisions' and t.tgname = nom
         and not t.tgisinternal and t.tgenabled = 'O')
    then
      ecarts := ecarts || format(
        'AUTHORITY_0014_TRIGGER_NOT_ENABLED: %s est absent ou desactive '
        '(ALTER TABLE ... DISABLE TRIGGER laisse la ligne en place avec '
        'tgenabled <> ''O'')', nom);
    end if;
  end loop;

  -- ---------------- E. CONTRAINTES ET CLES ETRANGERES VALIDEES ------------
  foreach nom in array contraintes loop
    if not exists (
      select 1 from pg_constraint
       where conrelid = 'normative_authority_decisions'::regclass
         and conname = nom and contype = 'c' and convalidated)
    then
      ecarts := ecarts || format(
        'AUTHORITY_0014_CHECK_CONSTRAINT_MISSING: %s est absente ou non '
        'validee', nom);
    end if;
  end loop;
  -- CINQ CLES ETRANGERES, TOUTES VALIDEES. `NOT VALID` laisserait passer les
  -- lignes deja presentes: la contrainte cesserait de decrire le passe.
  if (select count(*) from pg_constraint
       where conrelid = 'normative_authority_decisions'::regclass
         and contype = 'f' and convalidated) <> 5 then
    ecarts := ecarts || format(
      'AUTHORITY_0014_FOREIGN_KEY_MISMATCH: %s cle(s) etrangere(s) validee(s), '
      '5 attendues (proposant, approbateur, deux sources, organisation)',
      (select count(*) from pg_constraint
        where conrelid = 'normative_authority_decisions'::regclass
          and contype = 'f' and convalidated));
  end if;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'AUTHORITY_0014_POSTCONDITION_FAILED: la surface posee par 0014 n''est '
      'pas celle qui a ete demandee — %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_0014_decisions_surface()
  owner to eurostruct_normative_writer;
revoke all on function assert_0014_decisions_surface() from public;
grant execute on function assert_0014_decisions_surface()
  to eurostruct_normative_writer, eurostruct_deployment;

comment on function assert_0014_decisions_surface is
  'Postcondition de 0014: fonctions, table, policies, declencheurs et '
  'contraintes lus dans le catalogue. Chaque ecart porte un identifiant '
  'stable AUTHORITY_0014_*.';


-- ---------------------------------------------------------------------
-- L'ASSERTION AGREGEE — les locales defendent chacune sa migration,
-- celle-ci defend leur COMPOSITION
-- ---------------------------------------------------------------------
-- CE QU'AUCUNE POSTCONDITION LOCALE NE PEUT VOIR. Chacune decrit l'etat a la
-- fin de SA migration, et doit s'y tenir: `0012` ne peut pas exiger l'octroi
-- que `0013` posera. Mais personne, alors, ne verifie l'etat FINAL — celui
-- sous lequel la base tournera. Une migration ulterieure qui elargit une ACL,
-- rend une fonction a PUBLIC ou relache un search_path passerait entre les
-- deux: sa propre postcondition ne connait pas les objets des autres, et
-- celles des autres ont deja tourne.
create or replace function assert_authority_composition() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  ecarts text[] := array[]::text[];
  r record;
  tables_autorite text[] := array[
    'normative_authorisation_grants', 'normative_authorisation_revocations',
    'normative_rule_confirmations', 'normative_rule_confirmation_revocations',
    'normative_authority_decisions'];
  nom text;
begin
  -- A. AUCUNE FONCTION DU SOUS-SYSTEME N'EST EXECUTABLE PAR PUBLIC, et
  --    aucune n'a perdu son search_path. Balayage, et non liste: une
  --    fonction ajoutee demain est couverte sans que personne y pense.
  -- LE PERIMETRE EST CELUI DE LA PROPRIETE, PAS CELUI DES NOMS.
  --
  -- Une premiere version balayait par prefixe (`normative_%`, `forbid_%`,
  -- ...). Elle attrapait dix-sept fonctions declencheur POSEES PAR DES
  -- MIGRATIONS ANTERIEURES a 6.3c, que ce jalon n'a ni creees ni durcies, et
  -- refusait donc une base correcte. Elargir le perimetre d'une assertion
  -- au-dela de ce que sa migration gouverne, c'est fabriquer un rouge qui
  -- n'apprend rien et qu'on finira par contourner.
  --
  -- La propriete est le bon critere: elle designe exactement la surface
  -- d'autorite, elle suit une fonction ajoutee demain sans qu'on y pense, et
  -- si un transfert de propriete echoue, c'est la postcondition LOCALE de la
  -- migration concernee qui le dit — pas celle-ci.
  for r in
    select p.proname, p.proacl is null as par_defaut,
           p.proconfig,
           p.prorettype = 'trigger'::regtype as est_declencheur,
           exists (select 1 from aclexplode(p.proacl) a
                    where a.grantee = 0 and a.privilege_type = 'EXECUTE') as publique
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer',
                                           'eurostruct_normative_bootstrap',
                                           'eurostruct_normative_activator')
  loop
    -- UN EXECUTE SUR UNE FONCTION DECLENCHEUR N'EST PAS UNE CAPACITE, et
    -- c'est mesure: `perform forbid_mutation()` rend
    -- « trigger functions can only be called as triggers » (SQLSTATE 0A000),
    -- quel que soit le droit detenu. Le compter comme une ouverture aurait
    -- produit treize rouges sans qu'aucun pouvoir n'existe derriere.
    -- Le `search_path`, lui, compte pour elles AUSSI: un declencheur
    -- s'execute avec le chemin de celui qui declenche l'ecriture.
    if (r.par_defaut or r.publique) and not r.est_declencheur then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_PUBLIC_EXECUTE: %s est executable par PUBLIC '
        '(%s)', r.proname,
        case when r.par_defaut then 'proacl NULL, droits par defaut'
             else 'entree PUBLIC dans proacl' end);
    end if;
    if r.proconfig is null
       or not exists (select 1 from unnest(r.proconfig) c where c like 'search\_path=%')
    then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_SEARCH_PATH_UNPINNED: %s n''a pas de '
        'search_path fixe', r.proname);
    end if;
  end loop;

  -- A-bis. LES PRIMITIVES NOMMEES APPARTIENNENT A UNE AUTORITE.
  --
  -- CE CONTROLE EXISTE PARCE QUE LE BALAYAGE CI-DESSUS EST DEFINI PAR LA
  -- PROPRIETE, et qu'un critere qui se definit par ce qu'il mesure ne mesure
  -- plus rien quand la chose bouge: une fonction dont le proprietaire derive
  -- SORT du balayage, en silence, et l'assertion continue de rendre vert.
  -- Defaut mesure en ecrivant le harnais de derive — `alter function ...
  -- owner to <migrateur>` ne produisait aucun ecart.
  --
  -- La liste est donc NOMMEE. Elle ne remplace pas le balayage: elle lui
  -- donne un point fixe.
  for r in
    select unnest(array[
             'resolve_normative_authorisation', 'consume_normative_authorisation',
             'normative_grant_is_effective', 'normative_grant_descendants',
             'check_normative_grant_lineage', 'normative_lock_grant_chains',
             'normative_decision_propose', 'normative_decision_approve',
             'normative_decision_consume', 'check_normative_decision_transition',
             'forbid_decision_delete', 'normative_authenticated_actor',
             'bootstrap_normative_administrator']) as attendue
  loop
    if not exists (
      select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public' and p.proname = r.attendue
         and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer',
                                             'eurostruct_normative_bootstrap',
                                             'eurostruct_normative_activator'))
    then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_OWNER_MISMATCH: %s est absente ou n''appartient '
        'plus a un role d''autorite (proprietaire actuel: %s)', r.attendue,
        coalesce((select pg_get_userbyid(p.proowner) from pg_proc p
                    join pg_namespace n on n.oid = p.pronamespace
                   where n.nspname = 'public' and p.proname = r.attendue
                   limit 1), 'AUCUN — fonction absente'));
    end if;
  end loop;

  -- B. LES CINQ TABLES D'AUTORITE: proprietaire, RLS, FORCE RLS.
  foreach nom in array tables_autorite loop
    if not exists (select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
                    where n.nspname='public' and c.relname=nom) then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_TABLE_MISSING: %s est absente', nom);
      continue;
    end if;
    for r in
      select pg_get_userbyid(c.relowner) as proprietaire,
             c.relrowsecurity, c.relforcerowsecurity
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
       where n.nspname = 'public' and c.relname = nom
    loop
      if r.proprietaire <> 'eurostruct_normative_writer' then
        ecarts := ecarts || format(
          'AUTHORITY_COMPOSITION_TABLE_OWNER_MISMATCH: %s appartient a « %s »',
          nom, r.proprietaire);
      end if;
      if not (r.relrowsecurity and r.relforcerowsecurity) then
        ecarts := ecarts || format(
          'AUTHORITY_COMPOSITION_FORCE_RLS_MISSING: %s a rls=%s force=%s',
          nom, r.relrowsecurity, r.relforcerowsecurity);
      end if;
    end loop;
  end loop;

  -- C. LES ROLES D'AUTORITE NE SE CONNECTENT PAS. Un role d'autorite
  --    connectable est un mot de passe de plus a perdre, et la separation
  --    entre « ce que le schema possede » et « qui se connecte » disparait.
  for r in
    select rolname, rolcanlogin from pg_roles
     where rolname in ('eurostruct_normative_writer',
                       'eurostruct_normative_bootstrap',
                       'eurostruct_normative_activator',
                       'eurostruct_authority_backend')
       and rolcanlogin
  loop
    ecarts := ecarts || format(
      'AUTHORITY_COMPOSITION_ROLE_CAN_LOGIN: le role d''autorite « %s » est '
      'connectable; il doit rester NOLOGIN', r.rolname);
  end loop;

  -- C-bis. AUCUN ROLE D'AUTORITE NE GARDE `CREATE` SUR `public`.
  --
  -- DEFAUT MESURE, ET INVISIBLE JUSQU'ICI. Un octroi fait par le proprietaire
  -- de la base est enregistre au nom de `pg_database_owner`; un `REVOKE` emis
  -- par ce meme role, mais sous sa propre identite, ne retire RIEN — sans
  -- erreur ni WARNING visible. Consequence: apres `0010`,
  -- `eurostruct_normative_writer`, proprietaire de TOUTES les tables
  -- d'autorite, conservait `CREATE` sur `public` pour toute la vie de la
  -- base. Personne ne le voyait, parce que personne ne verifiait le RESULTAT
  -- de la revocation.
  for r in
    select g.rolname,
           string_agg(distinct pg_get_userbyid(a.grantor), ', ') as donneurs
      from pg_namespace n, aclexplode(n.nspacl) a
      join pg_roles g on g.oid = a.grantee
     where n.nspname = 'public' and a.privilege_type = 'CREATE'
       and g.rolname in ('eurostruct_normative_writer',
                         'eurostruct_normative_bootstrap',
                         'eurostruct_normative_activator',
                         'eurostruct_authority_backend',
                         'normative_backend', 'normative_governance')
     group by g.rolname
  loop
    ecarts := ecarts || format(
      'AUTHORITY_COMPOSITION_SCHEMA_CREATE_RETAINED: le role d''autorite '
      '« %s » conserve CREATE sur le schema public (donneur: %s). Il peut y '
      'creer des objets pour toute la vie de la base',
      r.rolname, r.donneurs);
  end loop;

  -- D. LES ASSERTIONS ELLES-MEMES SONT SOUS CONTROLE. Une assertion qui
  --    subsiste apres la migration est du code privilegie: si PUBLIC pouvait
  --    l'executer, n'importe qui lirait la topologie d'autorite.
  for r in
    select p.proname,
           coalesce((select array_agg(g.rolname::text order by g.rolname)
                       from aclexplode(p.proacl) a
                       left join pg_roles g on g.oid = a.grantee
                      where a.privilege_type = 'EXECUTE'),
                    array[]::text[]) as porteurs,
           coalesce((select bool_or(a.grantee = 0)
                       from aclexplode(p.proacl) a
                      where a.privilege_type = 'EXECUTE'), false)
             or p.proacl is null as porteurs_publics
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname like 'assert\_%'
  loop
    -- LA LISTE DES ADMIS N'EST PAS ECRITE EN DUR, ET ELLE NE PEUT PAS L'ETRE.
    --
    -- `assert_normative_topology()` est appelee par la finalisation et par la
    -- readiness, qui s'executent sous le PLAN DE CONTROLE — dont le nom
    -- depend du deploiement et n'est pas connaissable a l'ecriture de cette
    -- migration. Une premiere version l'omettait et refusait donc une base
    -- correcte, en nommant un role de harnais comme s'il etait intrus.
    --
    -- La source est celle que le produit utilise deja pour cette question:
    -- `eurostruct.approved_deployment_roles`, declaree sur la base. Elle dit
    -- qui a le droit de deployer; qui deploie execute les assertions.
    -- PUBLIC, lui, n'y figure jamais — c'est ce que ce controle protege.
    if not (r.porteurs <@ (array['eurostruct_normative_writer',
                                 'eurostruct_normative_bootstrap',
                                 'eurostruct_normative_activator',
                                 'normative_governance',
                                 'eurostruct_deployment']
                           || (select coalesce(array_agg(btrim(x)), array[]::text[])
                                 from unnest(string_to_array(btrim(coalesce(
                                        normative_effective_setting(
                                          'eurostruct.approved_deployment_roles'),
                                        '')), ',')) x
                                where btrim(x) <> ''))) then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_ASSERTION_ACL_WIDENED: %s est executable par '
        '{%s}; seuls les roles d''autorite, la gouvernance, le deploiement et '
        'les roles declares dans eurostruct.approved_deployment_roles sont '
        'admis', r.proname, array_to_string(r.porteurs, ','));
    end if;
    -- PUBLIC EST REFUSE SEPAREMENT, et sans exception possible: une assertion
    -- lisible par tous expose la topologie d'autorite a qui la lit.
    if r.porteurs_publics then
      ecarts := ecarts || format(
        'AUTHORITY_COMPOSITION_ASSERTION_PUBLIC: %s est executable par PUBLIC',
        r.proname);
    end if;
  end loop;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'AUTHORITY_COMPOSITION_FAILED: la surface d''autorite COMPOSEE n''est '
      'pas celle qu''aucune migration prise isolement ne pouvait garantir — %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_authority_composition()
  owner to eurostruct_normative_writer;
revoke all on function assert_authority_composition() from public;
grant execute on function assert_authority_composition()
  to eurostruct_normative_writer, eurostruct_deployment;

comment on function assert_authority_composition is
  'Assertion AGREGEE de la surface d''autorite, posee apres 0014. Les '
  'postconditions locales defendent chacune sa migration et ne peuvent pas '
  'voir l''etat final; celle-ci defend leur composition. Balaye les fonctions '
  'plutot que de les lister: une fonction ajoutee demain est couverte.';


-- ---------------------------------------------------------------------
-- LE DROIT DE CREATE REPART — ET IL FAUT LE VERIFIER, PAS L'ESPERER
-- ---------------------------------------------------------------------
-- UN `REVOKE` SUR `public` N'EST PAS UNE COMMANDE, C'EST UN VOEU.
--
-- Fait mesure sur PostgreSQL 16, dans la forme de deploiement ou le migrateur
-- possede la base ET detient un `CREATE ... WITH GRANT OPTION` explicite:
--
--   * un octroi fait PAR LE PROPRIETAIRE de la base est enregistre au nom de
--     `pg_database_owner`, et non au nom du role;
--   * `REVOKE create on schema public FROM eurostruct_normative_writer` emis
--     par ce meme role ne retire RIEN — pas d'erreur, pas meme un WARNING
--     visible, et `ON_ERROR_STOP=1` ne s'arrete pas;
--   * consequence mesuree: apres `0010`, `eurostruct_normative_writer` — le
--     proprietaire de TOUTES les tables d'autorite — conservait `CREATE` sur
--     `public` pour toute la vie de la base. Personne ne le voyait, parce que
--     personne ne verifiait le RESULTAT de la revocation.
--
-- ON REVOQUE DONC SOUS LE DONNEUR REEL, celui que le catalogue nomme. C'est
-- la seule forme qui prend, et elle ne suppose rien de la forme du
-- deploiement.
--
-- `GRANTED BY` NE SUFFIT PAS: PostgreSQL 16 rend « grantor must be current
-- user ». Il faut donc ENDOSSER le donneur — ce que le proprietaire de la
-- base peut faire pour `pg_database_owner`, dont il est membre. `SET LOCAL`
-- meurt avec la transaction, comme partout ailleurs dans ce schema.
do $$
declare
  donneur text;
  appelant text := current_user;
  -- L'ENSEMBLE DES DONNEURS ADMISSIBLES EST EXPLICITE, ET CONFRONTE AU
  -- CATALOGUE — jamais l'inverse.
  --
  -- Endosser un role parce qu'il apparait dans `pg_auth_members.grantor`,
  -- c'est laisser le CATALOGUE choisir sous quelle identite la migration
  -- s'execute. Un octroi pose par un tiers suffirait alors a faire endosser
  -- ce tiers. Trois donneurs sont attendus ici, et aucun autre:
  --
  --   * `pg_database_owner`  — le proprietaire implicite de `public`;
  --   * l'appelant lui-meme  — ses propres octrois;
  --   * le proprietaire de la base, quand il differe de l'appelant.
  --
  -- Tout autre donneur ARRETE la migration. Ce n'est pas une precaution
  -- theorique: le privilege resterait, et c'est exactement ce que personne
  -- ne voyait avant que la postcondition n'existe.
  admissibles text[] := array[
    'pg_database_owner',
    current_user,
    pg_get_userbyid((select datdba from pg_database
                      where datname = current_database()))];
begin
  for donneur in
    select distinct pg_get_userbyid(a.grantor)
      from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public'
       and a.privilege_type = 'CREATE'
       -- TOUS LES ROLES D'AUTORITE, ET PAS SEULEMENT LES DEUX QUE CETTE
       -- MIGRATION A ELLE-MEME SERVIS. Mesure: l'ACTIVATEUR conservait lui
       -- aussi CREATE — le sceau le lui accorde en phase 0 et croit le
       -- retirer a la fin, avec la meme revocation inefficace.
       and a.grantee in ('eurostruct_normative_writer'::regrole::oid,
                         'eurostruct_normative_bootstrap'::regrole::oid,
                         'eurostruct_normative_activator'::regrole::oid,
                         'eurostruct_authority_backend'::regrole::oid,
                         'normative_backend'::regrole::oid,
                         'normative_governance'::regrole::oid)
  loop
    if not (donneur = any (admissibles)) then
      raise exception
        'AUTHORITY_0014_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
        'public n''est pas dans l''ensemble admissible {%}. La migration '
        'refuse de l''endosser: le catalogue ne choisit pas sous quelle '
        'identite elle s''execute.',
        donneur, array_to_string(admissibles, ', ')
        using errcode = 'insufficient_privilege';
    end if;
    -- `format('%I')` QUOTE L'IDENTIFIANT. Aucune concatenation libre: le nom
    -- vient du catalogue, et un nom de role peut contenir n'importe quoi.
    begin
      execute format('set local role %I', donneur);
      execute 'revoke create on schema public from '
              'eurostruct_normative_writer, eurostruct_normative_bootstrap, '
              'eurostruct_normative_activator, eurostruct_authority_backend, '
              'normative_backend, normative_governance';
      execute format('set local role %I', appelant);
    exception when others then
      -- LE ROLE EST RENDU SUR LE CHEMIN D'ERREUR AUSSI. Sans cela, la
      -- commande suivante s'executerait sous le role endosse — une fuite
      -- d'identite au milieu d'une migration.
      execute format('set local role %I', appelant);
      raise exception
        'AUTHORITY_0014_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%). Le privilege CREATE resterait, et rien '
        'd''autre ne le dirait.', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;

  -- LE RETOUR AU ROLE INITIAL EST CONSTATE, PAS SUPPOSE.
  if current_user <> appelant then
    raise exception
      'AUTHORITY_0014_ROLE_NOT_RESTORED: la migration s''execute encore sous '
      '« % » au lieu de « % » apres la revocation.', current_user, appelant
      using errcode = 'insufficient_privilege';
  end if;
end
$$;

-- LES DEUX POSTCONDITIONS, APPELEES PAR LA MIGRATION. Apres tous les
-- changements de catalogue, avant l'inscription au registre: une migration
-- refusee ne doit laisser aucune ligne disant qu'elle a ete appliquee.
select assert_0014_decisions_surface();
select assert_authority_composition();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
