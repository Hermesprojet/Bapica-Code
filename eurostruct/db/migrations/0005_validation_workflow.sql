-- =====================================================================
-- EUROSTRUCT — EPIC 4: validation humaine et responsabilite
--
-- TICKET 4.1 — workflow draft -> review -> validated -> final, validateur
--              identifie, signature immuable.
--
-- 0001 posait deja la contrainte de fond: `is_final` exige une validation
-- nominative, et une signature ne se modifie pas. Ce qui manquait, c'est le
-- CHEMIN: rien n'empechait de passer directement de 'brouillon' a 'final', ni
-- de revenir en arriere apres signature en laissant la signature orpheline.
--
-- La machine a etats ci-dessous rend ces transitions impossibles plutot
-- qu'improbables. `is_final` devient derive de `state`, pour qu'il n'existe
-- pas deux verites sur le meme fait.
-- =====================================================================

begin;

create type deliverable_state as enum (
  -- En cours de production. Porte le filigrane « PROJET — NON VALIDE ».
  'draft',
  -- Soumis a relecture. Toujours non opposable.
  'review',
  -- Un ingenieur habilite a signe. La validation est attachee et figee.
  'validated',
  -- Emis. Opposable, immuable, conserve dix ans.
  'final'
);

alter table deliverables
  add column if not exists state deliverable_state not null default 'draft',
  add column if not exists submitted_for_review_at timestamptz,
  add column if not exists submitted_by uuid references auth.users(id),
  -- Indice du livrable. Corriger apres signature = emettre l'indice suivant.
  add column if not exists revision integer not null default 1,
  -- Livrable dont celui-ci est la revision, quand il en remplace un.
  add column if not exists supersedes_id uuid references deliverables(id);

comment on column deliverables.state is
  'Etat du workflow. is_final en est derive: ne jamais l''ecrire directement.';

-- Les livrables deja crees avant cette migration.
update deliverables set state = 'final' where is_final;

-- Un etat 'validated' ou 'final' exige la validation nominative.
alter table deliverables
  add constraint validated_state_requires_validation check (
    state not in ('validated', 'final') or validation_id is not null
  );


-- ---------------------------------------------------------------------
-- Machine a etats
-- ---------------------------------------------------------------------
create or replace function enforce_deliverable_workflow() returns trigger
language plpgsql as $$
declare
  allowed boolean := false;
begin
  -- is_final est derive de state. Une ecriture directe qui le contredit est
  -- refusee plutot que corrigee en silence: ramener un `is_final = true` a
  -- false donnerait a l'appelant l'illusion d'avoir emis un livrable opposable.
  -- On ne controle que les ecritures EXPLICITES: une transition d'etat qui ne
  -- touche pas is_final le derive normalement.
  if tg_op = 'INSERT' then
    if new.is_final <> (new.state = 'final') then
      raise exception
        'is_final est derive de state et ne s''ecrit pas directement '
        '(state = %, is_final = %). Faire progresser le livrable dans le '
        'workflow: draft -> review -> validated -> final.',
        new.state, new.is_final
        using errcode = 'restrict_violation';
    end if;
  elsif new.is_final is distinct from old.is_final
        and new.is_final <> (new.state = 'final') then
    raise exception
      'is_final ne s''ecrit pas directement: faire evoluer state (% -> %) et '
      'is_final en sera derive.', old.state, new.state
      using errcode = 'restrict_violation';
  end if;

  if tg_op = 'UPDATE' and new.state <> old.state then
    allowed := case
      when old.state = 'draft'     and new.state = 'review'    then true
      -- Refuse en relecture: retour au brouillon, aucune signature en jeu.
      when old.state = 'review'    and new.state = 'draft'     then true
      when old.state = 'review'    and new.state = 'validated' then true
      when old.state = 'validated' and new.state = 'final'     then true
      else false
    end;

    if not allowed then
      raise exception
        'Transition de livrable interdite: % -> %. Chemin autorise: draft -> '
        'review -> validated -> final (retour possible de review vers draft '
        'uniquement). Apres signature, corriger = emettre un nouvel indice.',
        old.state, new.state
        using errcode = 'restrict_violation';
    end if;
  end if;

  -- La validation doit exister ET porter sur le calcul du livrable.
  if new.state in ('validated', 'final')
     and (tg_op = 'INSERT' or new.state <> old.state) then
    if new.validation_id is null then
      raise exception
        'Passage a l''etat % refuse: aucune validation nominative attachee au '
        'livrable %. Un ingenieur habilite doit signer le calcul avant que le '
        'livrable puisse etre valide (section 9).', new.state, new.filename
        using errcode = 'restrict_violation';
    end if;
    if not exists (
      select 1 from validations v
       where v.id = new.validation_id
         and v.calculation_id = new.calculation_id
    ) then
      raise exception
        'La validation % ne porte pas sur le calcul % du livrable %.',
        new.validation_id, new.calculation_id, new.filename
        using errcode = 'restrict_violation';
    end if;
  end if;

  new.is_final := (new.state = 'final');
  return new;
end;
$$;

-- Avant le trigger d'immuabilite de 0003, pour que la transition legitime
-- validated -> final soit evaluee d'abord (les triggers BEFORE d'une meme
-- table s'executent par ordre alphabetique de nom).
create trigger deliverables_aa_workflow
  before insert or update on deliverables
  for each row execute function enforce_deliverable_workflow();


-- ---------------------------------------------------------------------
-- Un livrable signe ne se modifie plus: on emet l'indice suivant
-- ---------------------------------------------------------------------
create or replace function forbid_validated_deliverable_mutation() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    if old.state in ('validated', 'final') then
      raise exception
        'Le livrable % (etat %) porte une signature et ne peut pas etre '
        'supprime: conservation decennale.', old.filename, old.state
        using errcode = 'restrict_violation';
    end if;
    return old;
  end if;

  if old.state in ('validated', 'final') then
    -- Seule la transition validated -> final reste ouverte.
    if not (old.state = 'validated' and new.state = 'final') then
      raise exception
        'Le livrable % est signe (etat %). Emettre un nouvel indice plutot que '
        'de le modifier.', old.filename, old.state
        using errcode = 'restrict_violation';
    end if;
  end if;
  return new;
end;
$$;

-- Remplace le garde de 0003, qui ne connaissait que is_final.
drop trigger if exists deliverables_final_is_immutable on deliverables;
create trigger deliverables_zz_signed_is_immutable
  before update or delete on deliverables
  for each row execute function forbid_validated_deliverable_mutation();


-- ---------------------------------------------------------------------
-- Revision: un nouvel indice reference celui qu'il remplace
-- ---------------------------------------------------------------------
create or replace function check_revision_chain() returns trigger
language plpgsql as $$
declare
  prev record;
begin
  if new.supersedes_id is null then
    return new;
  end if;

  select * into prev from deliverables where id = new.supersedes_id;
  if prev is null then
    raise exception 'le livrable remplace % est introuvable', new.supersedes_id
      using errcode = 'foreign_key_violation';
  end if;
  if prev.project_id <> new.project_id then
    raise exception 'un indice ne peut remplacer un livrable d''un autre projet'
      using errcode = 'restrict_violation';
  end if;
  if new.revision <= prev.revision then
    raise exception
      'l''indice % doit etre superieur a celui du livrable remplace (%)',
      new.revision, prev.revision
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;

create trigger deliverables_ab_revision_chain
  before insert or update on deliverables
  for each row execute function check_revision_chain();


-- ---------------------------------------------------------------------
-- Tracabilite du parcours de validation
-- ---------------------------------------------------------------------
create table deliverable_state_transitions (
  id             bigserial primary key,
  org_id         uuid not null references organizations(id) on delete cascade,
  deliverable_id uuid not null references deliverables(id) on delete cascade,
  from_state     deliverable_state,
  to_state       deliverable_state not null,
  actor_id       uuid references auth.users(id),
  occurred_at    timestamptz not null default now()
);

create index on deliverable_state_transitions (deliverable_id, occurred_at);

alter table deliverable_state_transitions enable row level security;
create policy transitions_read on deliverable_state_transitions
  for select using (public.is_org_member(org_id));

create or replace function log_deliverable_transition() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if tg_op = 'INSERT' or new.state is distinct from old.state then
    insert into deliverable_state_transitions
      (org_id, deliverable_id, from_state, to_state, actor_id)
    values (
      new.org_id, new.id,
      case when tg_op = 'INSERT' then null else old.state end,
      new.state, auth.uid()
    );
  end if;
  return new;
end;
$$;

create trigger deliverables_log_transitions
  after insert or update on deliverables
  for each row execute function log_deliverable_transition();

commit;
