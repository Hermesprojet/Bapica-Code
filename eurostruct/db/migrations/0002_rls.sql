-- =====================================================================
-- EUROSTRUCT — cloisonnement multi-tenant par Row Level Security
--
-- Cahier des charges sections 5.2 et 9 (RGPD, cloisonnement multi-tenant par
-- RLS, teste).
--
-- Regle: aucune table metier n'est lisible sans appartenance a l'organisation
-- proprietaire. Le referentiel global (versions du moteur, jeux de NDP) est
-- lisible par tout utilisateur authentifie mais ecrit uniquement par le
-- service.
--
-- Les fonctions d'appartenance sont SECURITY DEFINER et fixent search_path,
-- pour que les politiques ne dependent pas du chemin de recherche de
-- l'appelant.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Fonctions d'appartenance
-- ---------------------------------------------------------------------
create or replace function public.is_org_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from organization_members m
    where m.org_id = target_org
      and m.user_id = auth.uid()
  );
$$;

create or replace function public.has_org_role(target_org uuid, allowed org_role[])
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from organization_members m
    where m.org_id = target_org
      and m.user_id = auth.uid()
      and m.role = any(allowed)
  );
$$;

-- Roles autorises a modifier le contenu d'un projet.
create or replace function public.can_write(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select public.has_org_role(
    target_org,
    array['owner', 'admin', 'engineer', 'validating_engineer']::org_role[]
  );
$$;


-- ---------------------------------------------------------------------
-- Activation
-- ---------------------------------------------------------------------
alter table organizations            enable row level security;
alter table organization_members     enable row level security;
alter table projects                 enable row level security;
alter table documents                enable row level security;
alter table extractions              enable row level security;
alter table structural_models        enable row level security;
alter table materials                enable row level security;
alter table elements                 enable row level security;
alter table loads                    enable row level security;
alter table load_combinations        enable row level security;
alter table calculations             enable row level security;
alter table results                  enable row level security;
alter table verifications            enable row level security;
alter table validations              enable row level security;
alter table deliverables             enable row level security;
alter table audit_log                enable row level security;
alter table engine_versions          enable row level security;
alter table national_annex_sets      enable row level security;
alter table national_annex_parameters enable row level security;

-- Les politiques s'appliquent aussi au proprietaire des tables: sans cela, le
-- role applicatif pourrait contourner le cloisonnement.
alter table organizations            force row level security;
alter table projects                 force row level security;
alter table documents                force row level security;
alter table extractions              force row level security;
alter table structural_models        force row level security;
alter table materials                force row level security;
alter table elements                 force row level security;
alter table loads                    force row level security;
alter table load_combinations        force row level security;
alter table calculations             force row level security;
alter table results                  force row level security;
alter table verifications            force row level security;
alter table validations              force row level security;
alter table deliverables             force row level security;


-- ---------------------------------------------------------------------
-- Organisations et membres
-- ---------------------------------------------------------------------
create policy org_read on organizations
  for select using (public.is_org_member(id));

create policy org_update on organizations
  for update using (public.has_org_role(id, array['owner', 'admin']::org_role[]))
  with check    (public.has_org_role(id, array['owner', 'admin']::org_role[]));

create policy members_read on organization_members
  for select using (public.is_org_member(org_id));

create policy members_write on organization_members
  for all using (public.has_org_role(org_id, array['owner', 'admin']::org_role[]))
  with check    (public.has_org_role(org_id, array['owner', 'admin']::org_role[]));


-- ---------------------------------------------------------------------
-- Tables metier cloisonnees par org_id
--
-- Genere en boucle: chaque table recoit exactement la meme paire de
-- politiques, ce qui evite qu'une table ajoutee plus tard herite d'une regle
-- differente par inadvertance.
-- ---------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'projects', 'documents', 'extractions', 'structural_models', 'materials',
    'elements', 'loads', 'load_combinations', 'calculations', 'results',
    'verifications', 'deliverables'
  ]
  loop
    execute format($f$
      create policy %1$I_read on %1$I
        for select using (public.is_org_member(org_id));
    $f$, t);

    execute format($f$
      create policy %1$I_write on %1$I
        for all using (public.can_write(org_id))
        with check    (public.can_write(org_id));
    $f$, t);
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- Validations: lisibles par l'organisation, signables par le seul role
-- habilite (section 9). L'absence de politique UPDATE/DELETE est
-- deliberee: une signature ne se modifie pas.
-- ---------------------------------------------------------------------
create policy validations_read on validations
  for select using (public.is_org_member(org_id));

create policy validations_sign on validations
  for insert
  with check (
    public.has_org_role(org_id, array['validating_engineer']::org_role[])
    and validated_by = auth.uid()
  );


-- ---------------------------------------------------------------------
-- Audit: lecture par l'organisation, ecriture par le service uniquement.
-- ---------------------------------------------------------------------
create policy audit_read on audit_log
  for select using (org_id is not null and public.is_org_member(org_id));


-- ---------------------------------------------------------------------
-- Referentiel global: lecture pour tout utilisateur authentifie.
-- L'ecriture passe par le role de service, qui contourne la RLS.
-- ---------------------------------------------------------------------
create policy engine_versions_read on engine_versions
  for select to authenticated using (true);

create policy ndp_sets_read on national_annex_sets
  for select to authenticated using (true);

create policy ndp_parameters_read on national_annex_parameters
  for select to authenticated using (true);
