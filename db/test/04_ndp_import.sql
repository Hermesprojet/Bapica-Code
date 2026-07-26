-- =====================================================================
-- EUROSTRUCT — garanties du pipeline d'import documentaire
--
--   1. Un candidat d'extraction n'a aucun statut a prendre.
--   2. Une decision 'accepted' exige valeur, page et verificateur nomme.
--   3. Une decision signee est immuable.
--   4. Un parametre 'confirmed' exige source_doc_id ET source_page.
--   5. Le document source referencé doit avoir ete depose.
-- =====================================================================

\set ON_ERROR_STOP on

-- 1. La table des candidats ne comporte aucune colonne de statut.
do $$
declare n integer;
begin
  select count(*) into n from information_schema.columns
   where table_name = 'ndp_extraction_candidates'
     and column_name in ('validation_status', 'confirmed', 'verified_by');
  if n <> 0 then
    raise exception
      'un candidat d''extraction dispose d''une colonne de statut: il pourrait '
      'se declarer verifie sans relecture humaine';
  end if;
end
$$;

insert into ndp_source_documents
  (doc_id, filename, storage_path, country_code, standard_family, part,
   reference, publisher, edition, effective_from, language, page_count,
   deposited_by)
values ('sha256:testdoc', 'annexe-test.pdf', 's3://annexe-test.pdf', 'BE',
        'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'NBN', 'TEST-2026',
        date '2026-01-01', 'fr', 42, '33333333-3333-3333-3333-333333333333');

insert into ndp_extraction_candidates
  (id, candidate_id, document_id, parameter_name, page, snippet, raw_value,
   parsed_value, clause, confidence, extractor_version)
select 'bb000000-0000-0000-0000-000000000001', 'cand-001', d.id, 'alpha_cc',
       17, 'Clause 3.1.6(1)P ... 0,85 ...', '0,85', 0.85, '3.1.6(1)P',
       0.9, '0.1.0'
from ndp_source_documents d where d.doc_id = 'sha256:testdoc';

-- 2. Une acceptation sans valeur, sans page ou sans nom est refusee.
do $$
declare ok boolean;
begin
  foreach ok in array array[false, false, false] loop end loop;

  ok := false;
  begin
    insert into ndp_review_decisions
      (candidate_id, outcome, verified_by_name, verified_by, source_page)
    values ('bb000000-0000-0000-0000-000000000001', 'accepted', 'ing. C. Meunier',
            '33333333-3333-3333-3333-333333333333', 17);   -- sans final_value
  exception when check_violation then ok := true;
  end;
  if not ok then raise exception 'acceptation sans valeur admise'; end if;

  ok := false;
  begin
    insert into ndp_review_decisions
      (candidate_id, outcome, verified_by_name, verified_by, final_value)
    values ('bb000000-0000-0000-0000-000000000001', 'accepted', 'ing. C. Meunier',
            '33333333-3333-3333-3333-333333333333', 0.85);  -- sans source_page
  exception when check_violation then ok := true;
  end;
  if not ok then raise exception 'acceptation sans page source admise'; end if;

  ok := false;
  begin
    insert into ndp_review_decisions
      (candidate_id, outcome, verified_by_name, verified_by, final_value, source_page)
    values ('bb000000-0000-0000-0000-000000000001', 'accepted', '   ',
            '33333333-3333-3333-3333-333333333333', 0.85, 17);
  exception when check_violation then ok := true;
  end;
  if not ok then raise exception 'acceptation sans verificateur nomme admise'; end if;
end
$$;

-- Une decision complete passe.
insert into ndp_review_decisions
  (id, candidate_id, outcome, verified_by_name, verified_by, final_value,
   source_page, verified_at)
values ('cc000000-0000-0000-0000-000000000001',
        'bb000000-0000-0000-0000-000000000001', 'accepted',
        'ing. C. Meunier (BE-ING-4471)', '33333333-3333-3333-3333-333333333333',
        0.85, 17, now());

-- 3. Une decision signee est immuable.
do $$
declare ok boolean := false;
begin
  begin
    update ndp_review_decisions set final_value = 1.0
     where id = 'cc000000-0000-0000-0000-000000000001';
  exception when restrict_violation then ok := true;
  end;
  if not ok then raise exception 'une decision signee a pu etre modifiee'; end if;
end
$$;

-- 4. 'confirmed' sans source_doc_id / source_page est refuse.
do $$
declare ok boolean := false; annex uuid;
begin
  select id into annex from national_annexes
   where country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1';

  begin
    insert into national_annex_parameters
      (annex_id, country_code, standard_family, part, national_annex_reference,
       edition, effective_from, parameter_name, parameter_value, source_official,
       source_type, validation_status, verified_by, verified_at, clause, description)
    values (annex, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'ed-x',
            date '2027-01-01', 'test_sans_doc', 0.85, 'NBN', 'national_annex',
            'confirmed', '33333333-3333-3333-3333-333333333333', now(),
            '§3.1.6(1)P', 'test');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'un parametre confirme sans document source a ete admis';
  end if;
end
$$;

-- 5. Le document reference doit exister.
do $$
declare ok boolean := false; annex uuid;
begin
  select id into annex from national_annexes
   where country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1';
  begin
    insert into national_annex_parameters
      (annex_id, country_code, standard_family, part, national_annex_reference,
       edition, effective_from, parameter_name, parameter_value, source_official,
       source_type, validation_status, verified_by, verified_at, clause,
       description, source_doc_id, source_page)
    values (annex, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'ed-x',
            date '2027-01-01', 'test_doc_absent', 0.85, 'NBN', 'national_annex',
            'confirmed', '33333333-3333-3333-3333-333333333333', now(),
            '§3.1.6(1)P', 'test', 'sha256:jamais-depose', 17);
  exception when foreign_key_violation then ok := true;
  end;
  if not ok then
    raise exception 'un parametre confirme a pu referencer un document non depose';
  end if;
end
$$;

-- Avec le document depose, la chaine complete passe.
insert into national_annex_parameters
  (annex_id, country_code, standard_family, part, national_annex_reference,
   edition, effective_from, parameter_name, parameter_value, source_official,
   source_type, validation_status, verified_by, verified_at, clause,
   description, source_doc_id, source_page)
select a.id, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'TEST-2026',
       date '2027-01-01', 'test_chaine_complete', 0.85, 'NBN', 'national_annex',
       'confirmed', '33333333-3333-3333-3333-333333333333', now(),
       '§3.1.6(1)P', 'valeur relevee', 'sha256:testdoc', 17
from national_annexes a
where a.country_code = 'BE' and a.standard_family = 'EN 1992' and a.part = '1-1';

\echo ''
\echo '================================================='
\echo ' Import documentaire: chaine de provenance verifiee.'
\echo '================================================='
