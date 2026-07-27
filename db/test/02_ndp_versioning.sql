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
declare n integer; unverified integer; distinct_names integer;
begin
  select count(*) into n from national_annexes;
  if n <> 4 then
    raise exception 'attendu 4 annexes (BE/FR/ES/DE), trouve %', n;
  end if;

  -- Ce que ce compte protege n'est pas un nombre, c'est une symetrie: les
  -- quatre pays doivent porter EXACTEMENT le meme jeu de parametres. Un pays
  -- auquel il en manque un ne refuse pas de calculer — il tombe sur
  -- 'annexe incomplete' au moment du preflight, bien plus tard et pour une
  -- raison qui ne designe pas le seed. Un compte en dur, lui, se contente
  -- d'etre reecrit a chaque ajout et ne verifie plus rien.
  select count(*) into n from national_annex_parameters;
  if n < 4 then
    raise exception 'seed de parametres vide ou tronque: % lignes', n;
  end if;

  select count(distinct parameter_name) into distinct_names
    from national_annex_parameters;
  if n <> 4 * distinct_names then
    raise exception
      'asymetrie entre pays: % parametres pour % noms distincts sur 4 pays '
      '(attendu %)', n, distinct_names, 4 * distinct_names;
  end if;

  select count(*) into n
    from (
      select country_code, array_agg(parameter_name order by parameter_name) as names
        from national_annex_parameters
       group by country_code
    ) per_country
   where names <> (
     select array_agg(parameter_name order by parameter_name)
       from national_annex_parameters where country_code = 'BE'
   );
  if n <> 0 then
    raise exception
      '% pays ne portent pas le meme jeu de parametres que la Belgique', n;
  end if;

  -- Aucun parametre ne pretend etre releve dans une annexe publiee.
  -- 'not_representable' est admis: ce n'est pas une pretention de conformite,
  -- c'est la declaration qu'aucun scalaire ne convient (cot_theta_max belge).
  select count(*) into unverified
    from national_annex_parameters
   where validation_status not in ('pending_verification', 'not_representable');
  if unverified <> 0 then
    raise exception
      '% parametre(s) ne sont pas en pending_verification alors qu''aucune '
      'annexe n''a encore ete relevee', unverified;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 0. Un parametre sans valeur doit dire pourquoi, et reciproquement
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; target uuid;
begin
  select id into target from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'cot_theta_max';
  if target is null then
    raise exception 'cot_theta_max belge absent du seed';
  end if;

  -- L'annexe belge le fixe par une formule: aucune valeur n'est stockee.
  perform 1 from national_annex_parameters
   where id = target and parameter_value is null
     and validation_status = 'not_representable';
  if not found then
    raise exception
      'cot_theta_max belge porte une valeur scalaire alors que l''ANB '
      '§6.2.3(2) le fixe par une expression';
  end if;

  -- Et on ne peut pas creer un trou silencieux ailleurs.
  begin
    insert into national_annex_parameters (
      annex_id, country_code, standard_family, part, national_annex_reference,
      edition, effective_from, parameter_name, parameter_value, unit,
      source_official, source_type, validation_status, clause, description)
    select annex_id, country_code, standard_family, part,
           national_annex_reference, edition, effective_from,
           'parametre_sans_valeur', null, unit, source_official, source_type,
           'pending_verification', clause, description
      from national_annex_parameters where id = target;
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un parametre sans valeur a pu etre insere sans le statut '
      '''not_representable''';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 0 bis. Un parametre conditionnel porte ses branches, jamais un defaut
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; n integer; target uuid;
begin
  select id into target from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'alpha_cc';

  -- alpha_cc belge: 0,85 en flexion, 1,0 sinon, et AUCUNE valeur unique.
  perform 1 from national_annex_parameters
   where id = target and has_variants and parameter_value is null;
  if not found then
    raise exception
      'alpha_cc belge porte une valeur unique alors que l''ANB §3.1.6(1)P en '
      'donne deux selon la verification';
  end if;

  select count(*) into n from national_annex_parameter_variants
   where parameter_id = target;
  if n <> 2 then
    raise exception 'attendu 2 branches pour alpha_cc, trouve %', n;
  end if;

  perform 1 from national_annex_parameter_variants
   where parameter_id = target and condition = 'axial_and_bending' and value = 0.85;
  if not found then raise exception 'branche flexion absente ou <> 0,85'; end if;

  perform 1 from national_annex_parameter_variants
   where parameter_id = target and condition = 'other' and value = 1.0;
  if not found then raise exception 'branche « autres cas » absente ou <> 1,0'; end if;

  -- Une branche publiee ne se reecrit pas plus qu'une valeur.
  begin
    update national_annex_parameter_variants set value = 0.9
     where parameter_id = target and condition = 'other';
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'une branche de parametre national a pu etre ecrasee';
  end if;

  -- Et on ne peut pas porter a la fois des branches et une valeur unique.
  ok := false;
  begin
    insert into national_annex_parameters (
      annex_id, country_code, standard_family, part, national_annex_reference,
      edition, effective_from, parameter_name, parameter_value, unit,
      source_official, source_type, validation_status, clause, description,
      has_variants)
    select annex_id, country_code, standard_family, part,
           national_annex_reference, edition, effective_from,
           'parametre_avec_defaut_et_branches', 0.85, unit, source_official,
           source_type, 'pending_verification', clause, description, true
      from national_annex_parameters where id = target;
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un parametre a branches a pu porter aussi une valeur unique, qui '
      'servirait de defaut au premier appelant distrait';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 1. Ecrasement d'une valeur interdit
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; target uuid; current_value numeric;
begin
  -- La valeur d'essai est derivee de la valeur en base, jamais ecrite en dur:
  -- le declencheur ne se plaint qu'en cas de changement reel (is distinct
  -- from), donc un litteral egal au seed passerait sans rien prouver. C'est
  -- exactement ce qui est arrive quand alpha_cc belge est passe de 1,0 a 0,85.
  --
  -- Et le parametre d'essai doit porter une VALEUR SCALAIRE. alpha_cc servait
  -- ici jusqu'a ce qu'il devienne conditionnel: sa valeur est alors null,
  -- « null + 1 » vaut null, l'update redevient un no-op et le test echouait en
  -- annonçant qu'un ecrasement etait passe. Meme piege, deuxieme fois.
  select id, parameter_value into target, current_value
    from national_annex_parameters
   where country_code = 'BE' and parameter_name = 'As_min_coeff';
  if current_value is null then
    raise exception 'le parametre temoin doit porter une valeur scalaire';
  end if;

  begin
    update national_annex_parameters
       set parameter_value = current_value + 1 where id = target;
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
