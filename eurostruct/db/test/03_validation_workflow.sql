-- =====================================================================
-- EUROSTRUCT — EPIC 4: garanties du workflow de validation
--
-- TICKET 4.1, criteres d'acceptation:
--   1. is_final impossible sans validation nominative.
--   2. Une signature validee ne peut pas etre modifiee silencieusement.
--   3. La preuve de validation est conservee.
--
-- Plus le chemin lui-meme: draft -> review -> validated -> final, sans
-- raccourci ni retour apres signature.
--
-- Suppose 01_guarantees.sql applique (organisations, projet, calcul,
-- validation signee par Carla).
-- =====================================================================

\set ON_ERROR_STOP on

grant select, insert, update, delete on deliverable_state_transitions to authenticated;

-- ---------------------------------------------------------------------
-- 1. Un livrable nait en 'draft'
-- ---------------------------------------------------------------------
-- LES CHEMINS DE CE DECOR SONT ADRESSES PAR LEUR CONTENU, comme l'exige
-- `storage_path_derives_from_sha` (0020): un chemin qui ne contient pas
-- l'empreinte du document ne permet pas de retrouver ses octets.

insert into deliverables (id, org_id, project_id, calculation_id, kind, filename,
                          storage_path, sha256, size_bytes, engine_version,
                          generated_by)
values ('aa000000-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note-B.pdf',
        's3://sha256:b/note-B.pdf', 'sha256:b', 2048, '0.2.0',
        '11111111-1111-1111-1111-111111111111');

do $$
declare d record;
begin
  select * into d from deliverables where id = 'aa000000-0000-0000-0000-000000000001';
  if d.state <> 'draft' then
    raise exception 'un livrable devrait naitre en draft, etat = %', d.state;
  end if;
  if d.is_final then
    raise exception 'un brouillon ne peut pas etre marque final';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 2. Pas de raccourci: draft -> final est refuse
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    update deliverables
       set state = 'final', validation_id = '77777777-0000-0000-0000-000000000001'
     where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable a pu passer directement de draft a final';
  end if;
end
$$;

-- draft -> validated est aussi un raccourci
do $$
declare ok boolean := false;
begin
  begin
    update deliverables
       set state = 'validated', validation_id = '77777777-0000-0000-0000-000000000001'
     where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable a pu passer directement de draft a validated';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 3. Le chemin nominal
-- ---------------------------------------------------------------------
update deliverables set state = 'review',
       submitted_for_review_at = now(),
       submitted_by = '11111111-1111-1111-1111-111111111111'
 where id = 'aa000000-0000-0000-0000-000000000001';

-- Un refus en relecture ramene au brouillon: aucune signature n'est en jeu.
update deliverables set state = 'draft'
 where id = 'aa000000-0000-0000-0000-000000000001';
update deliverables set state = 'review'
 where id = 'aa000000-0000-0000-0000-000000000001';

-- 'validated' sans validation attachee: refuse. Le trigger de workflow
-- s'execute avant la contrainte CHECK et rend le message le plus utile;
-- accepter les deux codes evite un test qui depend de cet ordre.
do $$
declare ok boolean := false;
begin
  begin
    update deliverables set state = 'validated'
     where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation or check_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable a pu etre valide sans validation nominative';
  end if;
end
$$;

-- Avec la validation qui porte sur le bon calcul, la transition passe.
update deliverables
   set state = 'validated', validation_id = '77777777-0000-0000-0000-000000000001'
 where id = 'aa000000-0000-0000-0000-000000000001';

update deliverables set state = 'final'
 where id = 'aa000000-0000-0000-0000-000000000001';

do $$
declare d record;
begin
  select * into d from deliverables where id = 'aa000000-0000-0000-0000-000000000001';
  if not d.is_final then
    raise exception 'is_final devrait etre derive de state = final';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 4. Apres signature, plus de retour en arriere ni de modification
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    update deliverables set state = 'draft'
     where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable signe a pu revenir a l''etat brouillon';
  end if;

  ok := false;
  begin
    update deliverables set filename = 'autre.pdf'
     where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable signe a pu etre modifie';
  end if;

  ok := false;
  begin
    delete from deliverables where id = 'aa000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un livrable signe a pu etre supprime';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 5. Une validation d'un autre calcul est refusee
-- ---------------------------------------------------------------------
insert into calculations (id, org_id, project_id, model_id, engine_version_id,
                          ndp_as_of, status, inputs_hash, requested_by)
values ('66666666-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000001',
        'cccccccc-0000-0000-0000-000000000001', '55555555-0000-0000-0000-000000000001',
        'eeeeeeee-0000-0000-0000-000000000001', date '2026-07-26',
        'succeeded', 'sha256:xyz', '11111111-1111-1111-1111-111111111111');

insert into deliverables (id, org_id, project_id, calculation_id, kind, filename,
                          storage_path, sha256, size_bytes, engine_version,
                          generated_by)
values ('aa000000-0000-0000-0000-000000000002',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        '66666666-0000-0000-0000-000000000002', 'rebar_drawing_dxf', 'ferr.dxf',
        's3://sha256:c/ferr.dxf', 'sha256:c', 4096, '0.2.0',
        '11111111-1111-1111-1111-111111111111');

update deliverables set state = 'review'
 where id = 'aa000000-0000-0000-0000-000000000002';

do $$
declare ok boolean := false;
begin
  begin
    -- La validation 7777 porte sur le calcul 6666...0001, pas sur 0002.
    update deliverables
       set state = 'validated', validation_id = '77777777-0000-0000-0000-000000000001'
     where id = 'aa000000-0000-0000-0000-000000000002';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un livrable a pu etre valide par une signature portant sur un autre calcul';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6. Un indice doit succeder a celui qu'il remplace
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    insert into deliverables (org_id, project_id, calculation_id, kind, filename,
                              storage_path, sha256, size_bytes, engine_version,
                              generated_by, revision, supersedes_id)
    values ('aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
            '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note-C.pdf',
            's3://sha256:d/note-C.pdf', 'sha256:d', 2048, '0.2.0',
            '11111111-1111-1111-1111-111111111111',
            1, 'aa000000-0000-0000-0000-000000000001');
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un indice non superieur a pu remplacer un livrable';
  end if;
end
$$;

-- Un indice superieur passe: c'est le chemin de correction apres signature.
insert into deliverables (id, org_id, project_id, calculation_id, kind, filename,
                          storage_path, sha256, size_bytes, engine_version,
                          generated_by, revision, supersedes_id)
values ('aa000000-0000-0000-0000-000000000003',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note-C.pdf',
        's3://sha256:d/note-C.pdf', 'sha256:d', 2048, '0.2.0',
        '11111111-1111-1111-1111-111111111111',
        2, 'aa000000-0000-0000-0000-000000000001');


-- ---------------------------------------------------------------------
-- 7. Le parcours est historise
-- ---------------------------------------------------------------------
do $$
declare n integer; states text;
begin
  select count(*), string_agg(to_state::text, ' -> ' order by occurred_at, id)
    into n, states
    from deliverable_state_transitions
   where deliverable_id = 'aa000000-0000-0000-0000-000000000001';

  if n < 6 then
    raise exception 'parcours incomplet: % transitions enregistrees (%)', n, states;
  end if;
  if states not like '%validated -> final' then
    raise exception 'le parcours ne se termine pas par validated -> final: %', states;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 8. Qui a le droit de signer — validation METIER (niveau 2 sur 3)
--
-- La signature revient au bureau d'etudes qui realise l'etude. Aucun tiers
-- exterieur n'est requis. Mais le signataire doit etre membre ACTIF de
-- l'organisation du projet, et porter le role de validation technique.
-- ---------------------------------------------------------------------
do $$
declare ok boolean; org uuid; proj uuid; calc uuid; outsider uuid;
begin
  -- Un projet qui porte REELLEMENT un calcul: prendre le premier projet venu
  -- donnait un calculation_id null, et l'insertion echouait sur la contrainte
  -- de non-nullite au lieu du controle qu'on veut eprouver.
  select c.id, p.id, p.org_id into calc, proj, org
    from calculations c join projects p on p.id = c.project_id
   order by c.id limit 1;

  -- 8a. Un compte qui n'est membre de rien ne signe pas.
  outsider := '99999999-9999-9999-9999-999999999999';
  insert into auth.users (id, email) values (outsider, 'tiers@ailleurs.example')
    on conflict (id) do nothing;

  ok := false;
  begin
    insert into validations (org_id, project_id, calculation_id, validated_by,
                             validator_name, validator_role, statement,
                             engine_version, ndp_set_version, inputs_hash)
    values (org, proj, calc, outsider, 'Tiers Exterieur',
            'validating_engineer', 'Je valide', '0.3.0', '0.1.0-draft', 'sha256:x');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception 'un non-membre a pu signer une validation';
  end if;

  -- 8b. Un membre desactive ne signe plus, meme avec le bon role.
  insert into organization_members (org_id, user_id, role, is_active, deactivated_at)
  values (org, outsider, 'validating_engineer', false, now())
  on conflict (org_id, user_id) do update
    set role = 'validating_engineer', is_active = false, deactivated_at = now();

  ok := false;
  begin
    insert into validations (org_id, project_id, calculation_id, validated_by,
                             validator_name, validator_role, statement,
                             engine_version, ndp_set_version, inputs_hash)
    values (org, proj, calc, outsider, 'Ancien Collaborateur',
            'validating_engineer', 'Je valide', '0.3.0', '0.1.0-draft', 'sha256:x');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'un membre desactive a pu signer une validation';
  end if;

  -- 8c. Une raison sociale ne signe pas: il faut un nom de personne.
  update organization_members set is_active = true, deactivated_at = null
   where org_id = org and user_id = outsider;

  ok := false;
  begin
    insert into validations (org_id, project_id, calculation_id, validated_by,
                             validator_name, validator_role, statement,
                             engine_version, ndp_set_version, inputs_hash)
    values (org, proj, calc, outsider, '   ',
            'validating_engineer', 'Je valide', '0.3.0', '0.1.0-draft', 'sha256:x');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'une signature sans nom de personne a ete acceptee';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 9. Le role et le numero d'inscription sont DERIVES, jamais crus sur parole
-- ---------------------------------------------------------------------
-- Regression: une reecriture de check_validator_is_authorised() avait
-- supprime ces deux derivations sans que rien ne le signale, sinon ce test.
do $$
declare org uuid; proj uuid; calc uuid; signer uuid; v record;
begin
  -- Un projet qui porte REELLEMENT un calcul: prendre le premier projet venu
  -- donnait un calculation_id null, et l'insertion echouait sur la contrainte
  -- de non-nullite au lieu du controle qu'on veut eprouver.
  select c.id, p.id, p.org_id into calc, proj, org
    from calculations c join projects p on p.id = c.project_id
   order by c.id limit 1;
  signer := 'a1a1a1a1-0000-0000-0000-000000000009';

  insert into auth.users (id, email) values (signer, 'ing@bureau.example')
    on conflict (id) do nothing;
  insert into organization_members (org_id, user_id, role, professional_id)
  values (org, signer, 'validating_engineer', 'BE-ING-9099')
  on conflict (org_id, user_id) do update
    set role = 'validating_engineer', professional_id = 'BE-ING-9099';

  -- On MENT sur le role: la ligne doit etre corrigee depuis l'adhesion.
  insert into validations (id, org_id, project_id, calculation_id, validated_by,
                           validator_name, validator_role, statement,
                           engine_version, ndp_set_version, inputs_hash)
  values ('77777777-0000-0000-0000-000000000009', org, proj, calc, signer,
          'Ingenieur Du Bureau', 'viewer', 'Je valide',
          '0.3.0', '0.1.0-draft', 'sha256:y');

  select * into v from validations
   where id = '77777777-0000-0000-0000-000000000009';
  if v.validator_role <> 'validating_engineer' then
    raise exception 'validator_role n''a pas ete derive de l''adhesion: %',
      v.validator_role;
  end if;
  if v.professional_id is distinct from 'BE-ING-9099' then
    raise exception 'le numero d''inscription n''a pas ete fige: %',
      v.professional_id;
  end if;
end
$$;


\echo ''
\echo '================================================='
\echo ' EPIC 4: workflow de validation verifie.'
\echo '================================================='
