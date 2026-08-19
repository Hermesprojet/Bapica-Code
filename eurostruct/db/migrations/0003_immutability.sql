-- =====================================================================
-- EUROSTRUCT — immuabilite et conservation decennale
--
-- Cahier des charges section 9:
--
--   "Conservation des donnees 10 ans minimum (decennale) : projets,
--    hypotheses, versions de moteur, livrables signes, immuables et
--    horodates."
--
-- Ce qui suit rend cette exigence structurelle plutot qu'applicative. Une
-- signature, un livrable final et le calcul qui les sous-tend ne peuvent plus
-- etre modifies ni supprimes une fois emis: une correction se fait en emettant
-- un nouvel indice, jamais en reecrivant l'ancien.
--
-- Consequence assumee: un livrable final errone reste en base. C'est le
-- comportement attendu d'un dossier d'ouvrage.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Une signature ne se modifie pas
-- ---------------------------------------------------------------------
-- UNE SEULE TRANSACTION, comme toutes les autres migrations (6.3b6e).
-- Ce fichier n'en avait pas: une erreur au milieu le laissait
-- PARTIELLEMENT applique, et aucun registre ne peut rattraper cela
-- parce que l'unite d'application n'existe pas.
begin;

create or replace function forbid_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'La table % est immuable (conservation decennale, section 9 du cahier des '
    'charges). Emettre un nouvel indice au lieu de modifier %.',
    tg_table_name, tg_op
    using errcode = 'restrict_violation';
end;
$$;

create trigger validations_are_immutable
  before update or delete on validations
  for each row execute function forbid_mutation();


-- ---------------------------------------------------------------------
-- Un livrable final est fige
-- ---------------------------------------------------------------------
create or replace function forbid_final_deliverable_mutation() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    if old.is_final then
      raise exception
        'Le livrable final % (%) ne peut pas etre supprime: conservation '
        'decennale. Emettre un nouvel indice.', old.filename, old.id
        using errcode = 'restrict_violation';
    end if;
    return old;
  end if;

  if old.is_final then
    raise exception
      'Le livrable final % (%) est fige. Emettre un nouvel indice au lieu de '
      'le modifier.', old.filename, old.id
      using errcode = 'restrict_violation';
  end if;

  -- Passage a 'final': la validation doit exister et porter sur le meme calcul.
  if new.is_final and not old.is_final then
    if not exists (
      select 1 from validations v
      where v.id = new.validation_id
        and v.calculation_id = new.calculation_id
    ) then
      raise exception
        'Livrable final refuse: la validation % ne porte pas sur le calcul %.',
        new.validation_id, new.calculation_id
        using errcode = 'restrict_violation';
    end if;
  end if;

  return new;
end;
$$;

create trigger deliverables_final_is_immutable
  before update or delete on deliverables
  for each row execute function forbid_final_deliverable_mutation();


-- ---------------------------------------------------------------------
-- Un calcul valide est fige, ainsi que ses resultats
-- ---------------------------------------------------------------------
-- Deux fonctions plutot qu'une: PL/pgSQL resout les champs d'un record a la
-- compilation, y compris dans une branche CASE non prise. Une fonction unique
-- referencant a la fois `new.id` et `new.calculation_id` echouerait donc sur
-- la table qui n'a pas l'autre colonne.
create or replace function forbid_validated_calculation_mutation() returns trigger
language plpgsql as $$
declare
  target uuid := coalesce(new.id, old.id);
begin
  if exists (select 1 from validations v where v.calculation_id = target) then
    raise exception
      'Le calcul % a ete valide et signe: ses donnees sont figees. Relancer un '
      'nouveau calcul plutot que de modifier celui-ci.', target
      using errcode = 'restrict_violation';
  end if;
  return coalesce(new, old);
end;
$$;

create or replace function forbid_validated_child_mutation() returns trigger
language plpgsql as $$
declare
  target uuid := coalesce(new.calculation_id, old.calculation_id);
begin
  if exists (select 1 from validations v where v.calculation_id = target) then
    raise exception
      'Le calcul % a ete valide et signe: ses resultats sont figes. Relancer un '
      'nouveau calcul plutot que de modifier ceux-ci.', target
      using errcode = 'restrict_violation';
  end if;
  return coalesce(new, old);
end;
$$;

create trigger calculations_validated_are_immutable
  before update or delete on calculations
  for each row execute function forbid_validated_calculation_mutation();

create trigger results_validated_are_immutable
  before update or delete on results
  for each row execute function forbid_validated_child_mutation();


-- ---------------------------------------------------------------------
-- Le validateur doit etre habilite au moment de la signature
--
-- La contrainte CHECK de 0001 verifie le role stocke dans la ligne; ce trigger
-- verifie qu'il correspond bien a l'appartenance reelle, et fige le nom et le
-- numero d'inscription tels qu'ils sont a cet instant.
-- ---------------------------------------------------------------------
create or replace function check_validator_is_authorised() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  member_role org_role;
  member_pro  text;
begin
  select m.role, m.professional_id
    into member_role, member_pro
  from organization_members m
  where m.org_id = new.org_id
    and m.user_id = new.validated_by;

  if member_role is null then
    raise exception
      'Le validateur % n''appartient pas a l''organisation %.',
      new.validated_by, new.org_id
      using errcode = 'insufficient_privilege';
  end if;

  if member_role <> 'validating_engineer' then
    raise exception
      'Seul un utilisateur ayant le role "validating_engineer" peut valider un '
      'livrable (section 9). Role effectif: %.', member_role
      using errcode = 'insufficient_privilege';
  end if;

  new.validator_role := member_role;
  new.professional_id := coalesce(new.professional_id, member_pro);
  return new;
end;
$$;

create trigger validations_check_validator
  before insert on validations
  for each row execute function check_validator_is_authorised();


-- ---------------------------------------------------------------------
-- Ouverture de la periode de conservation a la premiere signature
-- ---------------------------------------------------------------------
create or replace function open_retention_period() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  update projects
     set retention_until = greatest(
           coalesce(retention_until, date '0001-01-01'),
           (new.signed_at + interval '10 years')::date
         )
   where id = new.project_id;
  return new;
end;
$$;

create trigger validations_open_retention
  after insert on validations
  for each row execute function open_retention_period();


-- ---------------------------------------------------------------------
-- Interdiction de purger un projet encore sous conservation
-- ---------------------------------------------------------------------
create or replace function forbid_purge_within_retention() returns trigger
language plpgsql as $$
begin
  if old.retention_until is not null and old.retention_until > current_date then
    raise exception
      'Le projet "%" est sous conservation decennale jusqu''au %. Suppression '
      'interdite; utiliser l''archivage (archived_at).',
      old.name, old.retention_until
      using errcode = 'restrict_violation';
  end if;
  return old;
end;
$$;

create trigger projects_retention_guard
  before delete on projects
  for each row execute function forbid_purge_within_retention();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
