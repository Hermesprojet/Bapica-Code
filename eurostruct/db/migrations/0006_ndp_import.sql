-- =====================================================================
-- EUROSTRUCT — pipeline d'import documentaire des Annexes Nationales
--
-- Ajoute au referentiel de 0004 la chaine de provenance documentaire:
--
--   ndp_source_documents      le PDF officiel depose, avec son empreinte
--   ndp_extraction_candidates les propositions lues dans ce document
--   ndp_review_decisions      la decision nominative prise sur chacune
--
-- Invariant impose par le schema, pas par le code applicatif:
--
--   Un parametre 'confirmed' doit porter source_doc_id ET source_page, et ces
--   deux valeurs doivent designer un document reellement depose. Autrement dit
--   une valeur opposable est toujours rattachable a une page d'un fichier dont
--   on connait l'empreinte.
--
-- Un candidat d'extraction n'a deliberement PAS de colonne de statut: il n'y a
-- aucun etat qu'il puisse prendre pour se declarer verifie. Seule une ligne de
-- ndp_review_decisions, signee et horodatee, ouvre la voie a 'confirmed'.
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- Documents officiels deposes
-- ---------------------------------------------------------------------
create table ndp_source_documents (
  id                uuid primary key default gen_random_uuid(),
  -- sha256 du fichier: un candidat ne peut pas etre rattache a un document
  -- silencieusement remplace.
  doc_id            text not null unique,
  filename          text not null,
  storage_path      text not null,
  country_code      country_code not null,
  standard_family   text not null,
  part              text not null,
  reference         text not null,
  publisher         text not null,
  -- Metadonnees DECLAREES par l'ingenieur qui depose, pas devinees du PDF.
  -- Une edition lue dans un en-tete est une supposition; une edition saisie
  -- par la personne qui tient le document est une affirmation dont elle repond.
  edition           text not null,
  effective_from    date not null,
  effective_to      date,
  language          text not null,
  page_count        integer not null,
  deposited_by      uuid not null references auth.users(id),
  deposited_at      timestamptz not null default now(),
  notes             text,

  unique nulls not distinct (country_code, standard_family, part, edition),
  constraint document_validity_is_ordered check (
    effective_to is null or effective_to > effective_from
  )
);

create index on ndp_source_documents (country_code, standard_family, part);

comment on table ndp_source_documents is
  'Documents officiels deposes (Annexes Nationales). Non redistribuables: le '
  'fichier reste dans le stockage de l''organisation qui detient la licence.';


-- ---------------------------------------------------------------------
-- Candidats d'extraction — des propositions, jamais des valeurs
-- ---------------------------------------------------------------------
create table ndp_extraction_candidates (
  id                uuid primary key default gen_random_uuid(),
  candidate_id      text not null,
  document_id       uuid not null references ndp_source_documents(id) on delete cascade,
  parameter_name    text not null,
  page              integer not null,
  snippet           text not null,
  raw_value         text,
  -- NULL quand l'extracteur a localise la clause sans pouvoir y lire un
  -- nombre. C'est une information utile pour le relecteur, jamais un trou a
  -- combler par une valeur par defaut.
  parsed_value      double precision,
  unit              text not null default 'dimensionless',
  clause            text,
  bbox              double precision[4],
  pattern_id        text,
  -- Score de l'extracteur. Indicatif: il ordonne la file de relecture et
  -- n'ouvre aucun chemin d'acceptation automatique.
  confidence        double precision not null default 0,
  extractor_version text not null,
  extracted_at      timestamptz not null default now(),

  unique (document_id, candidate_id),
  constraint confidence_is_a_ratio check (confidence >= 0 and confidence <= 1),
  constraint page_is_positive check (page >= 1)
);

create index on ndp_extraction_candidates (document_id, parameter_name);

comment on table ndp_extraction_candidates is
  'Propositions lues dans un document. Aucune colonne de statut: un candidat '
  'n''a aucun moyen de se declarer verifie.';


-- ---------------------------------------------------------------------
-- Decisions de relecture — le seul chemin vers 'confirmed'
-- ---------------------------------------------------------------------
create type ndp_review_outcome as enum (
  'accepted', 'corrected', 'rejected', 'deferred'
);

create table ndp_review_decisions (
  id            uuid primary key default gen_random_uuid(),
  candidate_id  uuid not null references ndp_extraction_candidates(id) on delete restrict,
  outcome       ndp_review_outcome not null,
  -- Nom de l'ingenieur, pas seulement son identifiant technique: c'est lui qui
  -- engage sa responsabilite, et le nom doit rester lisible dix ans plus tard.
  verified_by_name text not null,
  verified_by      uuid not null references auth.users(id),
  verified_at      timestamptz not null default now(),
  final_value      double precision,
  unit             text not null default 'dimensionless',
  -- La page que le relecteur a REELLEMENT lue, qui peut differer de celle que
  -- l'extracteur avait proposee.
  source_page      integer,
  notes            text,

  constraint accepted_decision_carries_its_evidence check (
    outcome not in ('accepted', 'corrected')
    or (final_value is not null
        and source_page is not null
        and length(btrim(verified_by_name)) > 0)
  )
);

create index on ndp_review_decisions (candidate_id);

-- Une decision signee ne se reecrit pas: se dedire = une nouvelle decision.
create or replace function forbid_review_decision_rewrite() returns trigger
language plpgsql as $$
begin
  raise exception
    'Une decision de relecture est immuable (signee par % le %). Enregistrer '
    'une nouvelle decision plutot que de modifier celle-ci.',
    old.verified_by_name, old.verified_at
    using errcode = 'restrict_violation';
end;
$$;

create trigger ndp_decisions_are_immutable
  before update or delete on ndp_review_decisions
  for each row execute function forbid_review_decision_rewrite();


-- ---------------------------------------------------------------------
-- Rattachement documentaire des parametres
-- ---------------------------------------------------------------------
alter table national_annex_parameters
  add column if not exists source_doc_id text,
  add column if not exists source_page integer;

comment on column national_annex_parameters.source_doc_id is
  'sha256 du document depose d''ou la valeur a ete relevee.';
comment on column national_annex_parameters.source_page is
  'Page de ce document, telle qu''imprimee, indiquee par le relecteur.';

-- Renforcement de la contrainte de 0004: une valeur opposable doit etre
-- rattachable a une page d'un fichier identifie.
alter table national_annex_parameters
  drop constraint if exists confirmed_ndp_is_signed;

alter table national_annex_parameters
  add constraint confirmed_ndp_is_signed check (
    validation_status <> 'confirmed'
    or (verified_by is not null
        and verified_at is not null
        and source_type = 'national_annex'
        and source_doc_id is not null
        and source_page is not null
        and source_page >= 1)
  );

-- Et le document referencé doit exister.
create or replace function check_ndp_source_document_exists() returns trigger
language plpgsql as $$
begin
  -- Quand source_doc_id est absent, c'est la contrainte CHECK
  -- confirmed_ndp_is_signed qui produit le bon diagnostic; ce trigger ne
  -- s'occupe que d'un identifiant renseigne mais inconnu.
  if new.validation_status = 'confirmed'
     and new.source_doc_id is not null
     and not exists (
       select 1 from ndp_source_documents d where d.doc_id = new.source_doc_id
     ) then
    raise exception
      'Le parametre %.%:% est declare confirme mais son document source (%) '
      'n''a pas ete depose. Deposer le document avant d''en importer les '
      'valeurs.',
      new.country_code, new.standard_family, new.parameter_name, new.source_doc_id
      using errcode = 'foreign_key_violation';
  end if;
  return new;
end;
$$;

create trigger ndp_confirmed_needs_its_document
  before insert or update on national_annex_parameters
  for each row execute function check_ndp_source_document_exists();


-- ---------------------------------------------------------------------
-- RLS: le referentiel est global en lecture; les documents deposes
-- appartiennent a l'organisation qui detient la licence.
-- ---------------------------------------------------------------------
alter table ndp_source_documents      enable row level security;
alter table ndp_extraction_candidates enable row level security;
alter table ndp_review_decisions      enable row level security;

create policy ndp_documents_read on ndp_source_documents
  for select to authenticated using (true);
create policy ndp_candidates_read on ndp_extraction_candidates
  for select to authenticated using (true);
create policy ndp_decisions_read on ndp_review_decisions
  for select to authenticated using (true);

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
