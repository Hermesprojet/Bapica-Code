-- =====================================================================
-- EUROSTRUCT — 0008: un parametre national peut dependre de la verification
--
-- NBN EN 1992-1-1 ANB §3.1.6(1)P:
--
--   « Pour les verifications a l'ELU de la resistance a l'effort normal, la
--     flexion simple ou composee, la valeur de alpha_cc vaut 0,85. Pour les
--     autres cas, alpha_cc vaut 1,0. »
--
-- Deux valeurs, et laquelle s'applique depend du calcul en cours. Stocker la
-- seule valeur de flexion se defendait tant que la flexion etait le seul
-- module; ca cesse de se defendre des qu'un module d'effort tranchant existe,
-- car l'effort tranchant est « les autres cas » et heriterait silencieusement
-- de 0,85 — soit 15 % d'erreur sur f_cd, dans le sens defavorable pour
-- l'ecrasement des bielles.
--
-- Un parametre a variantes ne porte PAS de parameter_value: une valeur unique
-- serait lue par tout appelant qui oublie de preciser le cas, ce que les
-- variantes existent precisement pour empecher.
-- =====================================================================

begin;

create table national_annex_parameter_variants (
  id            uuid primary key default gen_random_uuid(),
  parameter_id  uuid not null
                references national_annex_parameters(id) on delete restrict,

  -- Cle libre, definie par le parametre, comparee a l'identique. Pas un enum:
  -- chaque annexe decoupe ses cas a sa maniere, et inventer un vocabulaire
  -- commun imposerait une correspondance que personne n'a ecrite.
  condition     text not null,
  value         double precision not null,
  -- Ce que dit l'annexe pour cette branche, verbatim quand c'est possible.
  description   text not null,

  created_at    timestamptz not null default now(),

  unique (parameter_id, condition)
);

create index on national_annex_parameter_variants (parameter_id);

comment on table national_annex_parameter_variants is
  'Branches d''un parametre national dont la valeur depend de la verification '
  'effectuee. Le module de calcul doit nommer le cas; aucun defaut n''existe.';


-- ---------------------------------------------------------------------
-- Immuabilite: meme regime que les parametres eux-memes
-- ---------------------------------------------------------------------
create or replace function forbid_variant_rewrite() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception
      'La variante « % » du parametre % ne peut pas etre supprimee. Corriger '
      'une valeur nationale = clore le parametre et en inserer une version.',
      old.condition, old.parameter_id
      using errcode = 'restrict_violation';
  end if;
  raise exception
    'Ecrasement interdit sur la variante « % ». Une valeur nationale publiee '
    'ne se reecrit pas: creer une nouvelle version du parametre.',
    old.condition
    using errcode = 'restrict_violation';
end;
$$;

create trigger ndp_variants_are_append_only
  before update or delete on national_annex_parameter_variants
  for each row execute function forbid_variant_rewrite();


-- ---------------------------------------------------------------------
-- Un parametre a variantes n'a pas de valeur unique, et reciproquement
-- ---------------------------------------------------------------------
-- La contrainte 0007 imposait « valeur absente <=> not_representable ». Les
-- variantes ouvrent un troisieme cas legitime: absente PARCE QUE conditionnelle.
alter table national_annex_parameters
  drop constraint value_absent_iff_not_representable;

alter table national_annex_parameters
  add column has_variants boolean not null default false;

alter table national_annex_parameters
  add constraint value_absent_only_when_explained check (
    (parameter_value is null)
    = (validation_status = 'not_representable' or has_variants)
  );

-- Un parametre a variantes est representable, par cas: le statut
-- 'not_representable' est reserve a ce qu'aucun jeu de valeurs ne peut porter.
alter table national_annex_parameters
  add constraint variants_are_representable check (
    not (has_variants and validation_status = 'not_representable')
  );

comment on column national_annex_parameters.has_variants is
  'Vrai quand la valeur depend de la verification effectuee. parameter_value '
  'est alors null et les branches vivent dans '
  'national_annex_parameter_variants.';

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
