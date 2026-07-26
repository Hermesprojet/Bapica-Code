-- =====================================================================
-- EUROSTRUCT — EPIC 1: referentiel normatif versionne
--
-- TICKET 1.1 — modele de donnees des parametres normatifs.
-- TICKET 1.2 — registre des Annexes Nationales par pays / norme / partie /
--              version.
--
-- Remplace les tables `national_annex_sets` et `national_annex_parameters` de
-- 0001, dont le modele etait trop plat: il ne distinguait ni la famille de
-- norme, ni la partie, ni l'edition, ni la periode de validite, et ne portait
-- pas la source officielle.
--
-- Choix structurants
-- ------------------
-- 1. Un parametre est identifie par (pays, famille, partie, nom) et VERSIONNE
--    par (edition, effective_from). Les enregistrements sont en ajout seul:
--    corriger une valeur, c'est clore l'ancienne avec effective_to et en
--    inserer une nouvelle. Aucune ecriture en place — critere d'acceptation
--    « impossible d'ecraser un parametre national sans nouvelle version ».
--
-- 2. Un projet ne pointe plus vers UN jeu de parametres: il porte une date de
--    reference, et le moteur resout l'edition en vigueur a cette date pour
--    chaque norme utilisee. Un projet peut ainsi mobiliser l'EC2, l'EC3 et
--    l'EC7 sans que le modele impose un jeu unique.
--
-- 3. Le calcul fige un instantane des parametres reellement consommes, pour
--    rester reproductible meme apres publication d'une nouvelle edition.
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- Depose de l'ancien modele
-- ---------------------------------------------------------------------
alter table projects      drop column if exists ndp_set_id;
alter table calculations  drop column if exists ndp_set_id;

drop table if exists national_annex_parameters;
drop table if exists national_annex_sets;

-- ---------------------------------------------------------------------
-- Statuts
-- ---------------------------------------------------------------------
drop type if exists ndp_status;

create type ndp_validation_status as enum (
  -- Valeur relevee dans l'Annexe Nationale publiee par un ingenieur nomme.
  -- Seul statut utilisable en mode strict.
  'confirmed',
  -- Valeur supposee, non encore verifiee. Bloquee en mode strict.
  'pending_verification',
  -- Valeur remplacee ou reconnue erronee. Refusee dans TOUS les modes.
  'deprecated'
);

create type ndp_source_type as enum (
  'national_annex',
  -- Valeur imprimee dans la Note de la clause de l'Eurocode lui-meme.
  'en_recommended',
  -- Reglementation nationale hors systeme Eurocode: CTE, Codigo Estructural,
  -- NCSE-02, MVV TB, DTU.
  'national_regulation'
);


-- ---------------------------------------------------------------------
-- Annexes Nationales
-- ---------------------------------------------------------------------
create table national_annexes (
  id                   uuid primary key default gen_random_uuid(),
  country_code         country_code not null,
  standard_family      text not null,          -- 'EN 1992'
  part                 text not null,          -- '1-1'
  reference            text not null,          -- 'NBN EN 1992-1-1 ANB'
  edition              text not null,
  effective_from       date not null,
  effective_to         date,
  source_official      text not null,          -- organisme emetteur
  source_url_or_doc_id text,
  notes                text,
  created_at           timestamptz not null default now(),

  -- NULLS NOT DISTINCT: sans cela deux editions homonymes coexisteraient.
  -- Requiert PostgreSQL >= 15.
  unique nulls not distinct (country_code, standard_family, part, edition),

  constraint validity_window_is_ordered check (
    effective_to is null or effective_to > effective_from
  )
);

create index on national_annexes (country_code, standard_family, part);
create index on national_annexes (effective_from, effective_to);

comment on table national_annexes is
  'Un document d''Annexe Nationale publie, a une edition donnee. Le moteur '
  'resout l''edition en vigueur a la date de reference du projet.';


-- ---------------------------------------------------------------------
-- Parametres nationaux
-- ---------------------------------------------------------------------
create table national_annex_parameters (
  id                   uuid primary key default gen_random_uuid(),
  annex_id             uuid not null references national_annexes(id) on delete restrict,

  country_code         country_code not null,
  standard_family      text not null,
  part                 text not null,
  national_annex_reference text not null,
  edition              text not null,
  effective_from       date not null,
  effective_to         date,

  parameter_name       text not null,          -- 'alpha_cc'
  parameter_value      double precision not null,
  unit                 text not null default 'dimensionless',

  source_official      text not null,
  source_url_or_doc_id text,
  source_type          ndp_source_type not null,
  validation_status    ndp_validation_status not null,
  verified_at          timestamptz,
  verified_by          uuid references auth.users(id),
  notes                text,

  -- Clause de l'Eurocode de base, pour la citation dans la note de calcul.
  clause               text not null,
  description          text not null,
  en_recommended       double precision,

  created_at           timestamptz not null default now(),
  created_by           uuid references auth.users(id),

  -- Une seule version d'un parametre peut demarrer a une date donnee.
  unique nulls not distinct
    (country_code, standard_family, part, parameter_name, effective_from),

  -- Interdictions 2 et 3: declarer une valeur conforme a l'Annexe Nationale
  -- exige de dire QUI l'a relevee et QUAND, et qu'elle vienne bien de
  -- l'annexe et non de la recommandation EN.
  constraint confirmed_ndp_is_signed check (
    validation_status <> 'confirmed'
    or (verified_by is not null
        and verified_at is not null
        and source_type = 'national_annex')
  ),

  constraint validity_window_is_ordered check (
    effective_to is null or effective_to > effective_from
  )
);

create index on national_annex_parameters (country_code, standard_family, part, parameter_name);
create index on national_annex_parameters (annex_id);
create index on national_annex_parameters (validation_status);

comment on table national_annex_parameters is
  'Parametres determines nationalement, en ajout seul. Corriger une valeur = '
  'clore la version courante (effective_to) et inserer une nouvelle ligne.';


-- ---------------------------------------------------------------------
-- Ajout seul: une valeur publiee ne se reecrit pas
-- ---------------------------------------------------------------------
create or replace function forbid_ndp_value_rewrite() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception
      'Le parametre national %.%:% ne peut pas etre supprime. Le clore avec '
      'effective_to et inserer la nouvelle version.',
      old.country_code, old.standard_family, old.parameter_name
      using errcode = 'restrict_violation';
  end if;

  -- Seule la cloture d'une periode de validite est autorisee en place, plus
  -- les champs de verification quand on confirme une valeur deja stockee.
  if new.parameter_value        is distinct from old.parameter_value
     or new.unit                is distinct from old.unit
     or new.parameter_name      is distinct from old.parameter_name
     or new.country_code        is distinct from old.country_code
     or new.standard_family     is distinct from old.standard_family
     or new.part                is distinct from old.part
     or new.edition             is distinct from old.edition
     or new.effective_from      is distinct from old.effective_from
     or new.clause              is distinct from old.clause
  then
    raise exception
      'Ecrasement interdit sur le parametre national %.%:%. Un changement de '
      'valeur exige une nouvelle version: clore la ligne courante avec '
      'effective_to, puis inserer la nouvelle valeur.',
      old.country_code, old.standard_family, old.parameter_name
      using errcode = 'restrict_violation';
  end if;

  -- Une valeur deja confirmee ne redevient pas provisoire sans nouvelle
  -- version: la signature de l'ingenieur qui l'a relevee resterait attachee.
  if old.validation_status = 'confirmed'
     and new.validation_status <> 'confirmed'
  then
    raise exception
      'Le parametre %.%:% est confirme (releve par % le %). Le declasser exige '
      'une nouvelle version, pas une modification en place.',
      old.country_code, old.standard_family, old.parameter_name,
      old.verified_by, old.verified_at
      using errcode = 'restrict_violation';
  end if;

  return new;
end;
$$;

create trigger ndp_parameters_are_append_only
  before update or delete on national_annex_parameters
  for each row execute function forbid_ndp_value_rewrite();


-- Une annexe referencee par des parametres ne se reecrit pas non plus.
create or replace function forbid_annex_rewrite() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    if exists (select 1 from national_annex_parameters p where p.annex_id = old.id) then
      raise exception
        'L''annexe % (%) porte des parametres et ne peut pas etre supprimee.',
        old.reference, old.edition
        using errcode = 'restrict_violation';
    end if;
    return old;
  end if;

  if new.reference   is distinct from old.reference
     or new.edition  is distinct from old.edition
     or new.country_code is distinct from old.country_code
     or new.standard_family is distinct from old.standard_family
     or new.part is distinct from old.part
  then
    raise exception
      'L''identite de l''annexe % (%) est figee. Enregistrer une nouvelle '
      'edition plutot que de modifier celle-ci.', old.reference, old.edition
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;

create trigger annexes_identity_is_frozen
  before update or delete on national_annexes
  for each row execute function forbid_annex_rewrite();


-- ---------------------------------------------------------------------
-- Rattachement des projets et des calculs
-- ---------------------------------------------------------------------
-- Un projet porte une date de reference; le moteur resout l'edition en
-- vigueur a cette date, norme par norme.
alter table projects
  add column if not exists ndp_as_of date not null default current_date;

comment on column projects.ndp_as_of is
  'Date de reference du projet pour resoudre l''edition d''Annexe Nationale en '
  'vigueur. Figee a la creation pour que le calcul reste reproductible.';

alter table calculations
  add column if not exists ndp_as_of date not null default current_date,
  -- Instantane des parametres reellement consommes: le calcul reste
  -- reproductible meme apres publication d'une nouvelle edition.
  add column if not exists ndp_snapshot jsonb not null default '{}'::jsonb,
  -- Rapport de prevol (TICKET 1.3), conserve y compris quand il bloque.
  add column if not exists preflight jsonb;

comment on column calculations.ndp_snapshot is
  'Copie figee des parametres nationaux utilises, avec leur edition, leur '
  'statut de validation et leur source.';


-- ---------------------------------------------------------------------
-- RLS: referentiel global, lecture pour tout utilisateur authentifie
-- ---------------------------------------------------------------------
alter table national_annexes            enable row level security;
alter table national_annex_parameters   enable row level security;

create policy national_annexes_read on national_annexes
  for select to authenticated using (true);

create policy ndp_parameters_read on national_annex_parameters
  for select to authenticated using (true);

commit;
