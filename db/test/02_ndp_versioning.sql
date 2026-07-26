-- =====================================================================
-- EUROSTRUCT — EPIC 1: garanties du referentiel normatif
--
-- Verifie contre une vraie base PostgreSQL les criteres d'acceptation des
-- tickets 1.1 et 1.2:
--
--   1. Impossible d'ecraser un parametre national sans nouvelle version.
--   2. Impossible de supprimer un parametre national.
--   3. Un parametre 'confirmed' exige un verificateur nomme, une date, et une
--      source de type 'national_annex' (pas la recommandation EN).
--   4. Une valeur confirmee ne peut pas etre declassee en place.
--   5. L'identite d'une annexe publiee est figee.
--   6. Deux editions homonymes ne peuvent pas coexister.
--   7. Le versionnement par periode de validite fonctionne: clore puis inserer.
--
-- Suppose le seed 0001_ndp.sql applique.
-- =====================================================================

\set ON_ERROR_STOP on

grant select, insert, update, delete on national_annexes, national_annex_parameters
  to authenticated;

-- ---------------------------------------------------------------------
-- Le seed est charge et honnetement etiquete
-- ---------------------------------------------------------------------
do $$
declare n integer; unverified integer;
begin
  select count(*) into n from national_annexes;
  if n <> 4 then
    raise exception 'attendu 4 annexes (BE/FR/ES/DE), trouve %', n;
  end if;

  select count(*) into n from national_annex_parameters;
  if n <> 88 then
    raise exception 'attendu 88 parametres (4 x 22), trouve %', n;
  end if;

  -- Aucun parametre ne pretend etre releve dans une annexe publiee.
  select count(*) into unverified
    from national_annex_parameters where validation_status <> 'pending_verification';
  if unverified <> 0 then
    raise exception
      '% parametre(s) ne sont pas en pending_verification alors qu''aucune '
      'annexe n''a encore ete relevee', unverified;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 1. Ecrasement d'une valeur interdit
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; target uuid;
begin
  select id into target from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'alpha_cc';

  begin
    update national_annex_parameters set parameter_value = 0.85 where id = target;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'une valeur nationale a pu etre ecrasee en place';
  end if;

  ok := false;
  begin
    update national_annex_parameters set clause = '§9.9.9' where id = target;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'la clause d''un parametre national a pu etre modifiee';
  end if;

  ok := false;
  begin
    update national_annex_parameters set edition = 'autre' where id = target;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'l''edition d''un parametre national a pu etre modifiee';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 2. Suppression interdite
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    delete from national_annex_parameters
     where country_code = 'BE' and parameter_name = 'alpha_cc';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'un parametre national a pu etre supprime';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 3. 'confirmed' exige un verificateur nomme, une date, et la bonne source
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; annex uuid;
begin
  select id into annex from national_annexes
   where country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1';

  -- sans verificateur
  begin
    insert into national_annex_parameters
      (annex_id, country_code, standard_family, part, national_annex_reference,
       edition, effective_from, parameter_name, parameter_value, source_official,
       source_type, validation_status, clause, description)
    values (annex, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'ed-test',
            date '2027-01-01', 'test_sans_verificateur', 1.0, 'NBN',
            'national_annex', 'confirmed', '§1', 'test');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'un parametre a pu etre declare confirme sans verificateur';
  end if;

  -- avec verificateur mais source = recommandation EN: une valeur relevee dans
  -- l'annexe ne peut pas venir de la Note de l'Eurocode
  ok := false;
  begin
    insert into national_annex_parameters
      (annex_id, country_code, standard_family, part, national_annex_reference,
       edition, effective_from, parameter_name, parameter_value, source_official,
       source_type, validation_status, verified_by, verified_at, clause, description)
    values (annex, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', 'ed-test',
            date '2027-01-01', 'test_mauvaise_source', 1.0, 'NBN',
            'en_recommended', 'confirmed',
            '33333333-3333-3333-3333-333333333333', now(), '§1', 'test');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un parametre confirme a pu declarer la recommandation EN comme source';
  end if;
end
$$;

-- Avec verificateur, date, source correcte ET provenance documentaire
-- (depuis 0006: une valeur opposable est rattachable a une page d'un fichier
-- dont on connait l'empreinte), l'insertion passe.
insert into ndp_source_documents
  (doc_id, filename, storage_path, country_code, standard_family, part,
   reference, publisher, edition, effective_from, language, page_count,
   deposited_by)
select 'sha256:epic1-test', 'annexe.pdf', 's3://annexe.pdf', 'BE', 'EN 1992',
       '1-1', 'NBN EN 1992-1-1 ANB', 'NBN', a.edition, date '2026-01-01',
       'fr', 40, '33333333-3333-3333-3333-333333333333'
from national_annexes a
where a.country_code = 'BE' and a.standard_family = 'EN 1992' and a.part = '1-1'
on conflict (doc_id) do nothing;

insert into national_annex_parameters
  (annex_id, country_code, standard_family, part, national_annex_reference,
   edition, effective_from, parameter_name, parameter_value, source_official,
   source_type, validation_status, verified_by, verified_at, clause, description,
   source_doc_id, source_page)
select a.id, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', a.edition,
       date '2027-01-01', 'test_confirme', 1.0, 'NBN',
       'national_annex', 'confirmed', '33333333-3333-3333-3333-333333333333',
       now(), '§3.1.6(1)P', 'parametre de test releve dans l''annexe',
       'sha256:epic1-test', 12
from national_annexes a
where a.country_code = 'BE' and a.standard_family = 'EN 1992' and a.part = '1-1';


-- ---------------------------------------------------------------------
-- 4. Une valeur confirmee ne se declasse pas en place
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    update national_annex_parameters
       set validation_status = 'pending_verification'
     where country_code = 'BE' and parameter_name = 'test_confirme';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'une valeur confirmee a pu etre declassee sans nouvelle version';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 5 et 6. Identite d'annexe figee, editions homonymes interdites
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; annex uuid; ed text;
begin
  select id, edition into annex, ed from national_annexes
   where country_code = 'BE' and standard_family = 'EN 1992' and part = '1-1';

  begin
    update national_annexes set reference = 'autre chose' where id = annex;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'la reference d''une annexe publiee a pu etre modifiee';
  end if;

  ok := false;
  begin
    insert into national_annexes
      (country_code, standard_family, part, reference, edition, effective_from,
       source_official)
    values ('BE', 'EN 1992', '1-1', 'doublon', ed, current_date, 'NBN');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception 'deux editions homonymes ont pu coexister';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 7. Le versionnement fonctionne: clore la periode, puis inserer la suivante
-- ---------------------------------------------------------------------
do $$
declare n integer;
begin
  -- Cloturer la version courante est autorise: c'est la seule ecriture en
  -- place permise, et elle ne change aucune valeur.
  update national_annex_parameters
     set effective_to = date '2028-01-01'
   where country_code = 'BE' and parameter_name = 'test_confirme';

  -- Puis inserer la nouvelle version, avec sa propre valeur et sa date.
  insert into national_annex_parameters
    (annex_id, country_code, standard_family, part, national_annex_reference,
     edition, effective_from, parameter_name, parameter_value, source_official,
     source_type, validation_status, verified_by, verified_at, clause, description,
     source_doc_id, source_page)
  select a.id, 'BE', 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', a.edition,
         date '2028-01-01', 'test_confirme', 0.85, 'NBN',
         'national_annex', 'confirmed', '33333333-3333-3333-3333-333333333333',
         now(), '§3.1.6(1)P', 'valeur revisee', 'sha256:epic1-test', 12
  from national_annexes a
  where a.country_code = 'BE' and a.standard_family = 'EN 1992' and a.part = '1-1';

  select count(*) into n from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'test_confirme';
  if n <> 2 then
    raise exception 'attendu 2 versions du parametre, trouve %', n;
  end if;

  -- Les deux versions ne se recouvrent pas: une seule est en vigueur a une
  -- date donnee.
  select count(*) into n from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'test_confirme'
     and effective_from <= date '2027-06-01'
     and (effective_to is null or effective_to > date '2027-06-01');
  if n <> 1 then
    raise exception
      'attendu 1 version en vigueur au 2027-06-01, trouve %', n;
  end if;
end
$$;


\echo ''
\echo '================================================='
\echo ' EPIC 1: referentiel normatif verifie.'
\echo '================================================='
