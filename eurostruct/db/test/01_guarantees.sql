-- =====================================================================
-- EUROSTRUCT — tests des garanties structurelles du schema
--
-- Verifie, contre une vraie base PostgreSQL, les proprietes que le cahier des
-- charges rend bloquantes:
--
--   1. Cloisonnement multi-tenant par RLS (sections 5.2 et 11).
--   2. Seul un "validating_engineer" peut signer (section 9).
--   3. Aucun livrable final sans validation nominative (section 9).
--   4. Une signature et un livrable final sont immuables (section 9).
--   5. Un projet sous conservation decennale ne peut pas etre purge.
--   6. Un NDP "na_confirmed" exige un verificateur nomme (interdictions 2 et 3).
--
-- Chaque test leve une exception s'il echoue. Le script sort en erreur au
-- premier probleme grace a ON_ERROR_STOP.
-- =====================================================================

\set ON_ERROR_STOP on

-- Les politiques ne s'appliquent qu'aux roles non superutilisateur.
grant usage on schema public, auth to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;

-- ---------------------------------------------------------------------
-- Jeu d'essai
-- ---------------------------------------------------------------------
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'alice@bureau-a.be'),
  ('22222222-2222-2222-2222-222222222222', 'bob@bureau-b.fr'),
  ('33333333-3333-3333-3333-333333333333', 'carla@bureau-a.be');

insert into organizations (id, name, country) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'Bureau A', 'BE'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'Bureau B', 'FR');

insert into organization_members (org_id, user_id, role, professional_id) values
  -- Alice est ingenieur simple: elle ne peut PAS signer.
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'engineer', null),
  -- Carla est habilitee a valider.
  ('aaaaaaaa-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333', 'validating_engineer', 'BE-ING-4471'),
  ('bbbbbbbb-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 'engineer', null);

insert into engine_versions (id, version, released_at)
values ('eeeeeeee-0000-0000-0000-000000000001', '0.1.0', now());

insert into national_annex_sets (id, country, region, version, published_at, description)
values ('dddddddd-0000-0000-0000-000000000001', 'BE', null, '0.1.0-draft', current_date, 'ANB — non verifie');

insert into projects (id, org_id, name, country, ndp_set_id, created_by) values
  ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
   'Immeuble R+2 Liege', 'BE', 'dddddddd-0000-0000-0000-000000000001',
   '11111111-1111-1111-1111-111111111111'),
  ('cccccccc-0000-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000002',
   'Hall Lyon', 'FR', 'dddddddd-0000-0000-0000-000000000001',
   '22222222-2222-2222-2222-222222222222');

insert into structural_models (id, org_id, project_id, created_by)
values ('55555555-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
        'cccccccc-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111');

insert into calculations (id, org_id, project_id, model_id, engine_version_id,
                          ndp_set_id, status, inputs_hash, requested_by)
values ('66666666-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001',
        'cccccccc-0000-0000-0000-000000000001', '55555555-0000-0000-0000-000000000001',
        'eeeeeeee-0000-0000-0000-000000000001', 'dddddddd-0000-0000-0000-000000000001',
        'succeeded', 'sha256:abc', '11111111-1111-1111-1111-111111111111');


-- ---------------------------------------------------------------------
-- 1. Cloisonnement multi-tenant
-- ---------------------------------------------------------------------
do $$
declare n integer;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);

  select count(*) into n from projects;
  if n <> 1 then
    raise exception 'RLS: Alice voit % projets, 1 attendu', n;
  end if;

  select count(*) into n from projects where name = 'Hall Lyon';
  if n <> 0 then
    raise exception 'RLS PERCEE: Alice voit le projet d''une autre organisation';
  end if;

  select count(*) into n from calculations;
  if n <> 1 then
    raise exception 'RLS: Alice voit % calculs, 1 attendu', n;
  end if;
end
$$;
reset role;

do $$
declare n integer;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
  select count(*) into n from projects;
  if n <> 1 then
    raise exception 'RLS: Bob voit % projets, 1 attendu', n;
  end if;
  select count(*) into n from projects where name = 'Immeuble R+2 Liege';
  if n <> 0 then
    raise exception 'RLS PERCEE: Bob voit le projet du Bureau A';
  end if;
end
$$;
reset role;

-- Un utilisateur sans appartenance ne voit rien.
do $$
declare n integer;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub', '99999999-9999-9999-9999-999999999999', true);
  select count(*) into n from projects;
  if n <> 0 then
    raise exception 'RLS PERCEE: un non-membre voit % projets', n;
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 2. Seul un validating_engineer peut signer
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
  begin
    insert into validations (org_id, project_id, calculation_id, validated_by,
                             validator_name, validator_role, statement,
                             engine_version, ndp_set_version, inputs_hash)
    values ('aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
            '66666666-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
            'Alice', 'validating_engineer', 'Je valide', '0.1.0', '0.1.0-draft', 'sha256:abc');
  exception when insufficient_privilege or others then
    ok := true;
  end;
  if not ok then
    raise exception 'Un ingenieur non habilite a pu signer une validation';
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 3. Une signature valide passe, et fige le role et le numero d'ordre
-- ---------------------------------------------------------------------
do $$
declare v record;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
  insert into validations (id, org_id, project_id, calculation_id, validated_by,
                           validator_name, validator_role, statement,
                           engine_version, ndp_set_version, inputs_hash)
  values ('77777777-0000-0000-0000-000000000001',
          'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
          '66666666-0000-0000-0000-000000000001', '33333333-3333-3333-3333-333333333333',
          'Carla Meunier', 'validating_engineer',
          'Note verifiee et approuvee.', '0.1.0', '0.1.0-draft', 'sha256:abc');
  reset role;

  select * into v from validations where id = '77777777-0000-0000-0000-000000000001';
  if v.professional_id is distinct from 'BE-ING-4471' then
    raise exception 'Le numero d''inscription n''a pas ete fige: %', v.professional_id;
  end if;
end
$$;
reset role;

-- La periode de conservation s'est ouverte a 10 ans.
do $$
declare r date;
begin
  select retention_until into r from projects
   where id = 'cccccccc-0000-0000-0000-000000000001';
  if r is null or r < (current_date + interval '9 years 11 months')::date then
    raise exception 'Conservation decennale non ouverte: retention_until = %', r;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 4. Aucun livrable final sans validation
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    insert into deliverables (org_id, project_id, calculation_id, kind, filename,
                              storage_path, sha256, size_bytes, is_final,
                              engine_version, generated_by)
    values ('aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
            '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note.pdf',
            's3://x', 'sha256:def', 1024, true, '0.1.0',
            '11111111-1111-1111-1111-111111111111');
  exception when check_violation then
    ok := true;
  end;
  if not ok then
    raise exception 'Un livrable final a pu etre cree sans validation nominative';
  end if;
end
$$;

-- Avec la validation, il passe.
insert into deliverables (id, org_id, project_id, calculation_id, kind, filename,
                          storage_path, sha256, size_bytes, is_final, validation_id,
                          engine_version, generated_by)
values ('88888888-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note-A.pdf',
        's3://note-A.pdf', 'sha256:def', 1024, true,
        '77777777-0000-0000-0000-000000000001', '0.1.0',
        '11111111-1111-1111-1111-111111111111');


-- ---------------------------------------------------------------------
-- 5. Immuabilite
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    update validations set statement = 'je retire ma signature'
     where id = '77777777-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'Une signature a pu etre modifiee'; end if;

  ok := false;
  begin
    delete from validations where id = '77777777-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'Une signature a pu etre supprimee'; end if;

  ok := false;
  begin
    update deliverables set filename = 'autre.pdf'
     where id = '88888888-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'Un livrable final a pu etre modifie'; end if;

  ok := false;
  begin
    delete from deliverables where id = '88888888-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'Un livrable final a pu etre supprime'; end if;

  ok := false;
  begin
    update calculations set inputs_hash = 'sha256:falsifie'
     where id = '66666666-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'Un calcul valide a pu etre modifie'; end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6. Conservation: purge interdite
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    delete from projects where id = 'cccccccc-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'Un projet sous conservation decennale a pu etre supprime';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 7. Un NDP declare conforme exige un verificateur nomme
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    insert into national_annex_parameters
      (set_id, key, value, status, standard, clause, description, source)
    values ('dddddddd-0000-0000-0000-000000000001', 'EC2.alpha_cc', 1.0,
            'na_confirmed', 'EN 1992-1-1', '§3.1.6(1)P', 'alpha_cc', 'ANB');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'Un NDP a pu etre declare conforme a l''AN sans verificateur';
  end if;
end
$$;

-- Avec verificateur et date, il passe.
insert into national_annex_parameters
  (set_id, key, value, status, standard, clause, description, source,
   confirmed_by, confirmed_at)
values ('dddddddd-0000-0000-0000-000000000001', 'EC2.alpha_cc', 1.0,
        'na_confirmed', 'EN 1992-1-1', '§3.1.6(1)P', 'alpha_cc',
        'NBN EN 1992-1-1 ANB', '33333333-3333-3333-3333-333333333333', now());

-- ---------------------------------------------------------------------
-- 8. Une extraction confirmee doit etre signee et porter sa valeur retenue
-- ---------------------------------------------------------------------
insert into documents (id, org_id, project_id, kind, filename, storage_path,
                       mime_type, size_bytes, sha256, uploaded_by)
values ('99999999-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'architect_drawing', 'plan.pdf', 's3://plan.pdf', 'application/pdf',
        2048, 'sha256:plan', '11111111-1111-1111-1111-111111111111');

do $$
declare ok boolean := false;
begin
  begin
    insert into extractions (org_id, project_id, document_id, kind,
                             proposed_value, status)
    values ('aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
            '99999999-0000-0000-0000-000000000001', 'slab_thickness',
            '{"value": 200, "unit": "mm"}'::jsonb, 'confirmed');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'Une extraction a pu etre confirmee sans confirmation humaine';
  end if;
end
$$;

\echo ''
\echo '================================================='
\echo ' Toutes les garanties du schema sont verifiees.'
\echo '================================================='

-- ---------------------------------------------------------------------
-- 9. Un jeu de NDP ne peut pas etre duplique, region NULL comprise
--
-- Regression: l'unicite par defaut de PostgreSQL traite deux NULL comme
-- distincts, ce qui laissait inserer plusieurs jeux ('BE', NULL, 'v') aux
-- valeurs potentiellement divergentes.
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    insert into national_annex_sets (country, region, version, published_at, description)
    values ('BE', null, '0.1.0-draft', current_date, 'doublon');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception 'Un jeu de NDP a pu etre duplique (region NULL)';
  end if;
end
$$;
