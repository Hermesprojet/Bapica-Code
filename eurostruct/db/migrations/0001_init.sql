-- =====================================================================
-- EUROSTRUCT — schema initial
--
-- Cahier des charges section 14.1.
--
-- Principes structurants du modele:
--
--  1. Multi-tenant par organisation. Chaque table metier porte org_id et est
--     cloisonnee par RLS (voir 0002_rls.sql). Section 9, RGPD.
--
--  2. Tracabilite (section 8.1). Un resultat porte toujours: la version du
--     moteur, le jeu de NDP fige avec sa version et sa date, le hash des
--     entrees, et le journal de calcul complet (clause + formule + valeurs).
--
--  3. Rien n'entre dans un calcul sans confirmation humaine (section 3 et
--     interdiction 5). Les valeurs extraites d'un document vivent dans
--     `extractions` avec un statut; seules les lignes 'confirmed' peuvent
--     alimenter un modele.
--
--  4. Aucun livrable final sans validation nominative (section 9). Contrainte
--     structurelle: `deliverables.is_final` exige une ligne `validations`, et
--     un trigger verifie que le validateur a bien le role habilite.
--
--  5. Conservation 10 ans, immuabilite (section 9, responsabilite decennale).
--     Voir 0003_immutability.sql.
--
-- Convention: identifiants uuid, horodatages timestamptz en UTC, donnees
-- semi-structurees en jsonb valide par les schemas Pydantic cote applicatif.
-- =====================================================================

begin;

-- =====================================================================
-- LE REGISTRE DES MIGRATIONS (6.3b6e)
-- =====================================================================
-- CE QU'IL EXISTE POUR RENDRE POSSIBLE: relancer un deploiement interrompu.
--
-- Avant lui, la boucle de `tools/deploy_eurostruct.sh` recommencait toujours a
-- `0001` — et ces migrations ne sont pas idempotentes. Contre-exemples mesures
-- (db/test/deploy_recovery.sh, T1 a T3): interrompue apres 0001, apres 0005 ou
-- apres 0010, la relance echouait sur un objet deja existant. Rien ne savait ce
-- qui avait deja ete applique.
--
-- IL EST ECRIT PAR LA MIGRATION ELLE-MEME, DANS SA PROPRE TRANSACTION. C'est
-- la seule facon d'obtenir l'atomicite exigee: la ligne du registre et les
-- objets qu'elle atteste sont valides ensemble, ou pas du tout. Inscrire
-- depuis une transaction separee, apres coup, laisserait une fenetre ou la
-- migration est appliquee et non inscrite — c'est-a-dire exactement l'etat
-- qu'un registre existe pour supprimer.
--
-- IL APPARTIENT AU MIGRATEUR, et c'est voulu: ce n'est pas un objet de
-- confiance. Il n'atteste pas d'une approbation normative — il atteste de
-- quels FICHIERS DE SCHEMA ont ete appliques, ce qui est precisement le
-- perimetre pour lequel le migrateur est fiable. La racine de confiance, elle,
-- reste dans le sceau, hors de sa portee.
--
-- IL EST APPEND-ONLY. Une migration appliquee ne se « desapplique » pas: il n'y
-- a pas de `revert` dans ce modele, et il ne doit pas y en avoir — une base
-- normative en service ne revient pas en arriere sur un schema qui porte des
-- confirmations signees.
create table if not exists normative_migration_ledger (
  migration_id    text        primary key,
  checksum_sha256 text        not null check (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  applied_at      timestamptz not null default now(),
  applied_by      text        not null default session_user
);

create or replace function forbid_migration_ledger_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'normative_migration_ledger est append-only: une migration appliquee ne se '
    'retire pas. Il n''existe pas de « revert » dans ce modele, et une base '
    'normative en service ne revient pas en arriere sur un schema qui porte '
    'des confirmations signees.'
    using errcode = 'restrict_violation';
end;
$$;
drop trigger if exists normative_migration_ledger_is_append_only
  on normative_migration_ledger;
create trigger normative_migration_ledger_is_append_only
  before update or delete or truncate on normative_migration_ledger
  for each statement execute function forbid_migration_ledger_mutation();

-- `normative_migration_gate(id, sum)` — CE QUE LE RUNNER DEMANDE AVANT
-- D'APPLIQUER. Trois reponses, et aucune autre:
--
--   ABSENTE   -> jamais appliquee, il faut l'appliquer;
--   DEJA      -> meme identifiant, MEME empreinte: on saute;
--   MISMATCH  -> meme identifiant, AUTRE empreinte: on refuse.
--
-- LE TROISIEME CAS EST LE PLUS IMPORTANT. Une migration reecrite apres avoir
-- ete appliquee — un correctif pousse a chaud, un `git rebase` malheureux —
-- produit une base dont le schema ne correspond a aucun etat du depot. La
-- rejouer l'aggraverait; l'ignorer la masquerait.
create or replace function normative_migration_gate(p_id text, p_sum text)
returns text
language plpgsql
stable
set search_path = public, pg_temp
as $$
declare connu text;
begin
  select checksum_sha256 into connu
    from normative_migration_ledger where migration_id = p_id;
  if not found then
    return 'ABSENTE';
  end if;
  if connu = p_sum then
    return 'DEJA';
  end if;
  return 'MISMATCH';
end;
$$;

-- `normative_migration_applied(id, sum)` — LA DERNIERE LIGNE DE CHAQUE
-- MIGRATION, avant son `commit`.
--
-- Elle refait le controle du portillon, et ce n'est pas une redondance
-- decorative: le portillon est interroge par le RUNNER, hors transaction, et
-- un second deploiement pourrait s'intercaler entre la question et la reponse.
-- Ici, la verification et l'ecriture sont dans la meme transaction que la
-- migration.
create or replace function normative_migration_applied(p_id text, p_sum text)
returns void
language plpgsql
set search_path = public, pg_temp
as $$
declare connu text;
begin
  if p_id is null or btrim(p_id) = '' then
    raise exception 'aucun identifiant de migration presente.'
      using errcode = 'invalid_parameter_value';
  end if;
  if p_sum !~ '^[0-9a-f]{64}$' then
    raise exception
      'empreinte de migration invalide pour « % »: un sha256 hexadecimal de 64 '
      'caracteres est attendu, obtenu « % ».', p_id, p_sum
      using errcode = 'invalid_parameter_value';
  end if;

  select checksum_sha256 into connu
    from normative_migration_ledger where migration_id = p_id;

  if found and connu <> p_sum then
    raise exception
      'MIGRATION_CHECKSUM_MISMATCH: la migration « % » a deja ete appliquee '
      'avec l''empreinte %, et le fichier present porte %. Le schema de cette '
      'base ne correspond a aucun etat du depot. Ne rejouez pas: retrouvez la '
      'version qui a ete appliquee, ou ecrivez une NOUVELLE migration qui porte '
      'le correctif.', p_id, connu, p_sum
      using errcode = 'ES010';
  end if;

  if not found then
    insert into normative_migration_ledger (migration_id, checksum_sha256)
    values (p_id, p_sum);
  end if;
end;
$$;

-- AUCUNE DES DEUX N'EST EXECUTABLE PAR PUBLIC.
--
-- `db/test/05_normative_confirmation.sql` pose une regle GENERALE sur les
-- fonctions normatives: aucune n'est executable par PUBLIC, pour qu'aucune ne
-- le devienne par accident le jour ou elle passera SECURITY DEFINER. Elle a
-- attrape ces deux-la des leur ecriture, ce qui est exactement son office.
--
-- LE MIGRATEUR N'A BESOIN D'AUCUN OCTROI: il est le PROPRIETAIRE de ces
-- fonctions — c'est lui qui applique ce fichier — et un proprietaire detient
-- toujours EXECUTE. Le registre est son outil, pas celui de la base.
--
-- SI LE ROLE QUI MIGRE CHANGE, le nouveau devra recevoir EXECUTE explicitement.
-- L'applicateur le dit alors: « le registre n'a pas pu etre interroge ». C'est
-- un fail-closed volontaire — changer de migrateur est une decision de
-- deploiement, pas un detail qui doit passer inapercu.
revoke all on function normative_migration_gate(text, text) from public;
revoke all on function normative_migration_applied(text, text) from public;


create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Types enumeres
-- ---------------------------------------------------------------------
create type org_role as enum (
  'owner',
  'admin',
  'engineer',
  -- Seul ce role peut valider un livrable final (section 9).
  'validating_engineer',
  'viewer'
);

create type country_code as enum ('BE', 'FR', 'ES', 'DE');

create type structure_type as enum (
  'building', 'bridge', 'industrial_equipment', 'retaining_structure', 'other'
);

create type consequence_class as enum ('CC1', 'CC2', 'CC3');

create type design_situation as enum (
  'persistent', 'transient', 'accidental', 'seismic'
);

create type limit_state as enum ('ULS', 'SLS');

create type document_kind as enum (
  'architect_drawing', 'geotechnical_report', 'cctp', 'formwork_drawing',
  'photo', 'test_report', 'ifc_model', 'other'
);

create type extraction_status as enum (
  -- Proposition du service d'ingestion. N'entre PAS dans un calcul.
  'proposed',
  -- Confirmee par un humain: seul statut exploitable.
  'confirmed',
  'corrected',
  'rejected'
);

create type ndp_status as enum (
  'en_recommended',
  'na_confirmed',
  'na_pending_verification'
);

create type calculation_status as enum (
  'queued', 'running', 'succeeded', 'refused', 'failed'
);

create type check_status as enum ('pass', 'fail', 'not_applicable');

create type deliverable_kind as enum (
  'calculation_note_pdf', 'rebar_drawing_dxf', 'rebar_drawing_pdf',
  'connection_drawing_dxf', 'schedule_xlsx', 'quantities_xlsx', 'ifc_export',
  'model_json'
);

create type material_kind as enum (
  'concrete', 'reinforcement', 'structural_steel', 'timber', 'masonry', 'soil'
);

create type element_type as enum (
  'beam', 'column', 'slab', 'wall', 'footing', 'pile', 'brace', 'connection'
);

create type load_kind as enum (
  'self_weight', 'permanent', 'imposed', 'snow', 'wind', 'thermal',
  'accidental', 'seismic', 'execution', 'earth_pressure', 'water_pressure'
);


-- ---------------------------------------------------------------------
-- Tenancy
-- ---------------------------------------------------------------------
create table organizations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  country       country_code not null,
  -- Numero d'assurance RC professionnelle / decennale, exige a la mise en
  -- service dans les quatre marches (section 9).
  insurance_ref text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table organization_members (
  id              uuid primary key default gen_random_uuid(),
  org_id          uuid not null references organizations(id) on delete cascade,
  user_id         uuid not null references auth.users(id) on delete cascade,
  role            org_role not null default 'viewer',
  -- Numero d'inscription a l'ordre / la chambre professionnelle. Requis pour
  -- valider: Ordre des Architectes ou ingenieur agree (BE), OPQIBI/ordre (FR),
  -- Colegio (ES), Bauvorlageberechtigung / Prüfstatiker (DE).
  professional_id text,
  created_at      timestamptz not null default now(),
  unique (org_id, user_id)
);

create index on organization_members (user_id);


-- ---------------------------------------------------------------------
-- Referentiel global (non cloisonne: lecture pour tous, ecriture admin)
-- ---------------------------------------------------------------------
create table engine_versions (
  id            uuid primary key default gen_random_uuid(),
  version       text not null unique,          -- SemVer, ex. '0.1.0'
  released_at   timestamptz not null,
  git_sha       text,
  -- Note de release listant toute valeur numerique modifiee (section 8.2).
  release_notes text,
  -- Domaine de validation couvert par cette version, pour que l'app puisse
  -- refuser hors domaine (section 8.3).
  validated_scope jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

create table national_annex_sets (
  id           uuid primary key default gen_random_uuid(),
  country      country_code not null,
  region       text,
  version      text not null,
  published_at date not null,
  description  text not null,
  created_at   timestamptz not null default now(),

  -- NULLS NOT DISTINCT est indispensable ici: `region` est nullable pour les
  -- pays sans regionalisation des NDP, et l'unicite par defaut de PostgreSQL
  -- considere deux NULL comme differents. Sans cette clause, ('BE', NULL,
  -- '1.0') peut etre insere plusieurs fois, et un projet et son calcul
  -- pourraient referencer deux jeux homonymes aux valeurs divergentes.
  -- Requiert PostgreSQL 15 ou superieur.
  unique nulls not distinct (country, region, version)
);

create table national_annex_parameters (
  id              uuid primary key default gen_random_uuid(),
  set_id          uuid not null references national_annex_sets(id) on delete cascade,
  key             text not null,               -- ex. 'EC2.alpha_cc'
  value           double precision not null,
  unit            text not null default 'dimensionless',
  status          ndp_status not null,
  standard        text not null,               -- ex. 'EN 1992-1-1'
  clause          text not null,               -- ex. '§3.1.6(1)P'
  description     text not null,
  source          text not null,               -- ex. 'NBN EN 1992-1-1 ANB'
  en_recommended  double precision,
  confirmed_by    uuid references auth.users(id),
  confirmed_at    timestamptz,
  created_at      timestamptz not null default now(),
  unique (set_id, key),

  -- Interdictions 2 et 3: un parametre ne peut etre declare conforme a
  -- l'Annexe Nationale que si quelqu'un l'a releve et signe.
  constraint confirmed_ndp_needs_a_verifier check (
    status <> 'na_confirmed'
    or (confirmed_by is not null and confirmed_at is not null)
  )
);

create index on national_annex_parameters (set_id, key);


-- ---------------------------------------------------------------------
-- Projets
-- ---------------------------------------------------------------------
create table projects (
  id                        uuid primary key default gen_random_uuid(),
  org_id                    uuid not null references organizations(id) on delete cascade,
  name                      text not null,
  reference                 text,
  address                   text,
  country                   country_code not null,
  region                    text,
  structure_type            structure_type not null default 'building',
  consequence_class         consequence_class not null default 'CC2',
  -- Categorie d'importance sismique I a IV (EN 1998-1 §4.2.5).
  seismic_importance_class  text,
  -- Duree d'utilisation de projet, annees (EN 1990 Tab. 2.1).
  design_working_life_years integer not null default 50,
  -- Jeu de NDP fige au demarrage du projet (section 4.2).
  ndp_set_id                uuid not null references national_annex_sets(id),
  client_name               text,
  created_by                uuid not null references auth.users(id),
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now(),
  archived_at               timestamptz,
  -- Conservation decennale (section 9): date avant laquelle la purge est
  -- interdite. Renseignee a la premiere validation.
  retention_until           date
);

create index on projects (org_id);
create index on projects (org_id, created_at desc);


-- ---------------------------------------------------------------------
-- Documents et extraction assistee
-- ---------------------------------------------------------------------
create table documents (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references organizations(id) on delete cascade,
  project_id    uuid not null references projects(id) on delete cascade,
  kind          document_kind not null,
  filename      text not null,
  storage_path  text not null,                 -- objet S3 UE / Supabase Storage
  mime_type     text not null,
  size_bytes    bigint not null,
  -- Empreinte du fichier depose: garantit qu'un livrable renvoie bien au
  -- document source archive (section 9).
  sha256        text not null,
  page_count    integer,
  uploaded_by   uuid not null references auth.users(id),
  created_at    timestamptz not null default now(),
  unique (project_id, sha256)
);

create index on documents (project_id);

create table extractions (
  id             uuid primary key default gen_random_uuid(),
  org_id         uuid not null references organizations(id) on delete cascade,
  project_id     uuid not null references projects(id) on delete cascade,
  document_id    uuid not null references documents(id) on delete cascade,
  -- Ce que la proposition decrit: 'column_grid', 'slab_thickness',
  -- 'soil_layer', 'span', 'level', 'material', ...
  kind           text not null,
  -- Valeur proposee, structuree et validee cote applicatif par un schema
  -- Pydantic. Contient toujours l'unite: {"value": 550, "unit": "mm"}.
  proposed_value jsonb not null,
  -- Valeur retenue apres arbitrage humain. NULL tant que non confirmee.
  final_value    jsonb,
  status         extraction_status not null default 'proposed',
  -- Localisation dans le document source, pour afficher la valeur a cote de
  -- son extrait (section 6.3).
  page           integer,
  bbox           double precision[4],
  -- Score du modele d'extraction. Indicatif uniquement: il ne remplace pas la
  -- confirmation humaine et n'ouvre aucun chemin d'auto-acceptation.
  confidence     double precision,
  model_name     text,
  confirmed_by   uuid references auth.users(id),
  confirmed_at   timestamptz,
  created_at     timestamptz not null default now(),

  -- Interdiction 5: aucune cote extraite d'un plan sans confirmation humaine
  -- explicite. Une extraction exploitable porte forcement un nom et une date.
  constraint confirmed_extraction_is_signed check (
    status not in ('confirmed', 'corrected')
    or (confirmed_by is not null and confirmed_at is not null
        and final_value is not null)
  )
);

create index on extractions (project_id, status);
create index on extractions (document_id);


-- ---------------------------------------------------------------------
-- Modele structurel
-- ---------------------------------------------------------------------
create table structural_models (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations(id) on delete cascade,
  project_id  uuid not null references projects(id) on delete cascade,
  name        text not null default 'Modele principal',
  version     integer not null default 1,
  notes       text,
  created_by  uuid not null references auth.users(id),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (project_id, name, version)
);

create index on structural_models (project_id);

create table materials (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations(id) on delete cascade,
  model_id    uuid not null references structural_models(id) on delete cascade,
  kind        material_kind not null,
  grade       text not null,                   -- 'C30/37', 'B500B', 'S355', 'GL24h'
  -- Proprietes derivees ou saisies. Les proprietes normalisees sont recalculees
  -- par le moteur a partir de `grade`; ce champ sert aux cas non standard et
  -- aux donnees de sol.
  properties  jsonb not null default '{}'::jsonb,
  -- Origine de la valeur, incluant l'extraction confirmee dont elle vient.
  provenance  jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  unique (model_id, kind, grade)
);

create table elements (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references organizations(id) on delete cascade,
  model_id      uuid not null references structural_models(id) on delete cascade,
  mark          text not null,                 -- repere, ex. 'P1'
  type          element_type not null,
  -- Geometrie: noeuds, axes, longueur, orientation.
  geometry      jsonb not null,
  -- Section: {"shape":"rectangular","b":{"value":300,"unit":"mm"}, ...}
  section       jsonb not null default '{}'::jsonb,
  material_id   uuid references materials(id) on delete set null,
  -- Appuis et relachements (section 6.4).
  supports      jsonb not null default '{}'::jsonb,
  releases      jsonb not null default '{}'::jsonb,
  provenance    jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now(),
  unique (model_id, mark)
);

create index on elements (model_id);

create table loads (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references organizations(id) on delete cascade,
  model_id     uuid not null references structural_models(id) on delete cascade,
  element_id   uuid references elements(id) on delete cascade,
  kind         load_kind not null,
  -- Categorie d'exploitation A a K (EN 1991-1-1 Tab. 6.1).
  category     text,
  name         text not null,
  -- Valeur avec unite, et distribution (ponctuelle, uniforme, trapezoidale).
  value        jsonb not null,
  -- D'ou vient cette charge (section 6.5): saisie, calculee depuis la
  -- localisation (neige/vent), ou descendue d'un niveau superieur.
  provenance   jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);

create index on loads (model_id);
create index on loads (element_id);

create table load_combinations (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references organizations(id) on delete cascade,
  model_id     uuid not null references structural_models(id) on delete cascade,
  name         text not null,                  -- ex. 'ELU-STR 6.10b (1)'
  situation    design_situation not null,
  limit_state  limit_state not null,
  -- Expression EN 1990 appliquee: '6.10', '6.10a', '6.10b'.
  expression   text not null,
  -- Coefficients retenus par action: gamma_G, gamma_Q, psi_0/1/2, avec la
  -- reference du NDP dont chacun provient.
  factors      jsonb not null,
  is_envelope  boolean not null default false,
  created_at   timestamptz not null default now(),
  unique (model_id, name)
);

create index on load_combinations (model_id);


-- ---------------------------------------------------------------------
-- Calculs et resultats
-- ---------------------------------------------------------------------
create table calculations (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references organizations(id) on delete cascade,
  project_id         uuid not null references projects(id) on delete cascade,
  model_id           uuid not null references structural_models(id) on delete cascade,
  engine_version_id  uuid not null references engine_versions(id),
  -- Le jeu de NDP effectivement utilise, fige (section 4.2). Distinct de
  -- projects.ndp_set_id, qui peut evoluer: un calcul garde le sien.
  ndp_set_id         uuid not null references national_annex_sets(id),
  status             calculation_status not null default 'queued',
  -- Empreinte de la totalite des entrees. Deux calculs de meme hash doivent
  -- produire le meme resultat bit-a-bit (section 11).
  inputs_hash        text not null,
  -- Mode strict: refuse tout NDP non releve dans l'AN publiee. Obligatoire
  -- pour un livrable destine a etre signe.
  strict_ndp         boolean not null default true,
  -- Renseigne quand status = 'refused': pourquoi le moteur a refuse de
  -- conclure (section 8.3), jamais un resultat approche.
  refusal            jsonb,
  error_detail       text,
  progress_log       jsonb not null default '[]'::jsonb,
  requested_by       uuid not null references auth.users(id),
  started_at         timestamptz,
  finished_at        timestamptz,
  created_at         timestamptz not null default now(),

  constraint refused_calculation_states_why check (
    status <> 'refused' or refusal is not null
  )
);

create index on calculations (project_id, created_at desc);
create index on calculations (inputs_hash);

create table results (
  id             uuid primary key default gen_random_uuid(),
  org_id         uuid not null references organizations(id) on delete cascade,
  calculation_id uuid not null references calculations(id) on delete cascade,
  element_id     uuid references elements(id) on delete set null,
  combination_id uuid references load_combinations(id) on delete set null,
  -- Valeurs de sortie (As, x, z, M_Rd, ...), chacune avec son unite.
  payload        jsonb not null,
  -- Journal de calcul complet: pour chaque etape, symbole, description,
  -- formule symbolique, application numerique, valeur, clause citee et
  -- dependances. C'est ce qui rend chaque nombre cliquable (section 8.1).
  journal        jsonb not null,
  created_at     timestamptz not null default now()
);

create index on results (calculation_id);
create index on results (element_id);

create table verifications (
  id             uuid primary key default gen_random_uuid(),
  org_id         uuid not null references organizations(id) on delete cascade,
  result_id      uuid not null references results(id) on delete cascade,
  element_id     uuid references elements(id) on delete set null,
  name           text not null,                -- 'ELU — flexion simple'
  standard       text not null,                -- 'EN 1992-1-1'
  clause         text not null,                -- '§6.1'
  equation       text,
  -- Toujours renseigne: section 8.3 interdit un simple 'OK'.
  utilisation    double precision not null,
  status         check_status not null,
  acting         text not null,                -- valeur formatee avec unite
  resisting      text not null,
  detail         text,
  remedy         text,
  created_at     timestamptz not null default now()
);

create index on verifications (result_id);
create index on verifications (status, utilisation desc);


-- ---------------------------------------------------------------------
-- Validation humaine et livrables
-- ---------------------------------------------------------------------
create table validations (
  id                uuid primary key default gen_random_uuid(),
  org_id            uuid not null references organizations(id) on delete cascade,
  project_id        uuid not null references projects(id) on delete cascade,
  calculation_id    uuid not null references calculations(id) on delete cascade,
  validated_by      uuid not null references auth.users(id),
  -- Copie figee de l'inscription professionnelle au moment de la signature:
  -- elle doit rester lisible dix ans plus tard meme si le membre a quitte
  -- l'organisation.
  validator_name    text not null,
  validator_role    org_role not null,
  professional_id   text,
  -- Ce que le validateur atteste, horodate.
  statement         text not null,
  engine_version    text not null,
  ndp_set_version   text not null,
  inputs_hash       text not null,
  signed_at         timestamptz not null default now(),
  -- Reserves emises par le validateur, reprises dans la note de calcul.
  reservations      text,

  constraint only_a_validating_engineer_may_sign check (
    validator_role = 'validating_engineer'
  )
);

create index on validations (calculation_id);
create index on validations (project_id);

create table deliverables (
  id             uuid primary key default gen_random_uuid(),
  org_id         uuid not null references organizations(id) on delete cascade,
  project_id     uuid not null references projects(id) on delete cascade,
  calculation_id uuid not null references calculations(id) on delete cascade,
  kind           deliverable_kind not null,
  filename       text not null,
  storage_path   text not null,
  sha256         text not null,
  size_bytes     bigint not null,
  -- Un livrable 'final' est opposable. Il exige une validation nominative
  -- (section 9). Un livrable non final porte le filigrane 'projet'.
  is_final       boolean not null default false,
  validation_id  uuid references validations(id),
  engine_version text not null,
  generated_at   timestamptz not null default now(),
  generated_by   uuid not null references auth.users(id),

  -- Section 9: aucun livrable exportable en 'final' sans validation humaine
  -- nominative. La contrainte est structurelle, pas applicative.
  constraint final_deliverable_requires_validation check (
    is_final = false or validation_id is not null
  )
);

create index on deliverables (project_id, kind);
create index on deliverables (calculation_id);


-- ---------------------------------------------------------------------
-- Journal d'audit
-- ---------------------------------------------------------------------
create table audit_log (
  id          bigserial primary key,
  org_id      uuid references organizations(id) on delete set null,
  project_id  uuid references projects(id) on delete set null,
  user_id     uuid references auth.users(id),
  action      text not null,
  entity      text not null,
  entity_id   uuid,
  payload     jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index on audit_log (org_id, occurred_at desc);
create index on audit_log (entity, entity_id);


-- ---------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger organizations_updated_at before update on organizations
  for each row execute function set_updated_at();
create trigger projects_updated_at before update on projects
  for each row execute function set_updated_at();
create trigger structural_models_updated_at before update on structural_models
  for each row execute function set_updated_at();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
