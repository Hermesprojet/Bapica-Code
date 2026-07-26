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
insert into deliverables (id, org_id, project_id, calculation_id, kind, filename,
                          storage_path, sha256, size_bytes, engine_version,
                          generated_by)
values ('aa000000-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        '66666666-0000-0000-0000-000000000001', 'calculation_note_pdf', 'note-B.pdf',
        's3://note-B.pdf', 'sha256:b', 2048, '0.2.0',
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
        's3://ferr.dxf', 'sha256:c', 4096, '0.2.0',
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
            's3://note-C.pdf', 'sha256:d', 2048, '0.2.0',
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
        's3://note-C.pdf', 'sha256:d', 2048, '0.2.0',
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


\echo ''
\echo '================================================='
\echo ' EPIC 4: workflow de validation verifie.'
\echo '================================================='
