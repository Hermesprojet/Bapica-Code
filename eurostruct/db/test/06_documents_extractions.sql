-- =====================================================================
-- EUROSTRUCT — 0028: garanties des pieces deposees et des propositions
--
-- Ce que ces tests protegent: une valeur lue sur un plan n'entre dans une
-- etude qu'apres une decision humaine NOMMEE, et rien de ce qui a ete lu
-- — texte, page, position, proposition — ne peut etre reecrit ensuite.
--
-- Ils s'executent sous le proprietaire de la base: la RLS ne les concerne
-- pas, les contraintes et les declencheurs si. C'est le but: ces regles
-- tiennent QUEL QUE SOIT l'appelant, y compris celui qui contourne les
-- politiques. Le chemin des primitives, sous identite authentifiee, est
-- eprouve par `documents_extractions.sh`.
--
-- Toutes les donnees sont FICTIVES. Suppose 01_guarantees.sql applique
-- (Alice, Carla, l'organisation A et son projet existent).
-- =====================================================================

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------
-- Decor: un document conforme, et une fonction d'essai qui attend un refus
-- ---------------------------------------------------------------------
insert into documents (id, org_id, project_id, kind, filename, storage_path,
                       mime_type, size_bytes, sha256, uploaded_by,
                       storage_backend, format)
values ('d0c00000-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'architect_drawing', 'FICTIF-plan-niveau-1.pdf',
        'pieces/a/c/' || repeat('b2', 32) || '.pdf', 'application/pdf',
        4096, repeat('b2', 32), '11111111-1111-1111-1111-111111111111',
        'local', 'pdf');

-- `esc_doit_refuser(sql, sqlstate, motif)`: l'instruction DOIT echouer, et
-- sur CE code. Un refus pour une autre raison n'est pas le refus teste — il
-- ferait passer pour tenue une regle qui ne l'est peut-etre pas.
create or replace function pg_temp.esc_doit_refuser(
  p_sql text, p_etat text, p_motif text)
returns void language plpgsql as $$
declare
  etat text;
begin
  begin
    execute p_sql;
  exception when others then
    get stacked diagnostics etat = returned_sqlstate;
    if etat <> p_etat then
      raise exception 'REFUS POUR UNE AUTRE RAISON (% au lieu de %): %',
        etat, p_etat, p_motif;
    end if;
    return;
  end;
  raise exception 'ACCEPTE A TORT: %', p_motif;
end;
$$;

-- Une proposition conforme, dont chaque test retire ou fausse UN element.
create or replace function pg_temp.esc_proposition(
  p_page text default '1',
  p_bbox text default 'array[10,20,60,30]::double precision[]',
  p_position text default 'null',
  p_confidence text default '0.8',
  p_method text default '''texte_natif''',
  p_raw text default '''P1 30x60''',
  p_valeur text default '''{"value": 30, "unit": "cm"}''',
  p_statut text default '''proposed''',
  p_kind text default '''beam_width''')
returns text language sql as $$
  select format(
    'insert into extractions (org_id, project_id, document_id, kind, '
    'proposed_value, status, page, bbox, position, confidence, model_name, '
    'raw_text, method, element_label) values ('
    '''aaaaaaaa-0000-0000-0000-000000000001'', '
    '''cccccccc-0000-0000-0000-000000000001'', '
    '''d0c00000-0000-0000-0000-000000000001'', %s, %s::jsonb, %s, %s, %s, '
    '%s::jsonb, %s, ''FICTIF-extracteur/0'', %s, %s, ''P1'')',
    p_kind, p_valeur, p_statut, p_page, p_bbox, p_position, p_confidence,
    p_raw, p_method);
$$;


-- ---------------------------------------------------------------------
-- 40. Le document est adresse par son contenu
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(
  $q$insert into documents (org_id, project_id, kind, filename, storage_path,
       mime_type, size_bytes, sha256, uploaded_by, storage_backend, format)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001', 'other', 'x.pdf', 's3://x.pdf',
       'application/pdf', 10, 'sha256:x',
       '11111111-1111-1111-1111-111111111111', 'local', 'pdf')$q$,
  '23514', 'une empreinte qui n''est pas un sha256');

select pg_temp.esc_doit_refuser(
  format($q$insert into documents (org_id, project_id, kind, filename,
       storage_path, mime_type, size_bytes, sha256, uploaded_by,
       storage_backend, format)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001', 'other', 'x.pdf',
       'pieces/ailleurs.pdf', 'application/pdf', 10, %L,
       '11111111-1111-1111-1111-111111111111', 'local', 'pdf')$q$,
     repeat('c3', 32)),
  '23514', 'un chemin qui ne derive pas de l''empreinte');

select pg_temp.esc_doit_refuser(
  format($q$insert into documents (org_id, project_id, kind, filename,
       storage_path, mime_type, size_bytes, sha256, uploaded_by,
       storage_backend, format)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001', 'other', 'x.docx', %L,
       'application/msword', 10, %L,
       '11111111-1111-1111-1111-111111111111', 'local', 'docx')$q$,
     'pieces/' || repeat('c4', 32) || '.docx', repeat('c4', 32)),
  '23514', 'un format qui n''est ni pdf, ni dxf, ni dwg');

select pg_temp.esc_doit_refuser(
  format($q$insert into documents (org_id, project_id, kind, filename,
       storage_path, mime_type, size_bytes, sha256, uploaded_by,
       storage_backend, format)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001', 'other', 'x.pdf', %L,
       'application/pdf', 33554433, %L,
       '11111111-1111-1111-1111-111111111111', 'local', 'pdf')$q$,
     'pieces/' || repeat('c5', 32) || '.pdf', repeat('c5', 32)),
  '23514', 'une taille au-dela de la borne du magasin');

select pg_temp.esc_doit_refuser(
  format($q$insert into documents (org_id, project_id, kind, filename,
       storage_path, mime_type, size_bytes, sha256, uploaded_by,
       storage_backend, format)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001', 'other', 'x.pdf', %L,
       'application/pdf', 10, %L,
       '11111111-1111-1111-1111-111111111111', null, 'pdf')$q$,
     'pieces/' || repeat('c6', 32) || '.pdf', repeat('c6', 32)),
  '23514', 'un document qui ne dit pas quel magasin detient ses octets');

select pg_temp.esc_doit_refuser(
  $q$update documents set analysis_status = 'lu_a_moitie'
      where id = 'd0c00000-0000-0000-0000-000000000001'$q$,
  '23514', 'un statut d''analyse inconnu');


-- ---------------------------------------------------------------------
-- 41. Une proposition porte tout ce qui permet de la retrouver
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_raw => 'null'),
  '23514', 'une proposition sans texte brut');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_raw => ''' '''),
  '23514', 'une proposition au texte brut blanc');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_page => 'null'),
  '23514', 'une proposition sans page');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_page => '0'),
  '23514', 'une page zero');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_bbox => 'null'),
  '23514', 'ni boite ni position');
-- LE PIEGE DU NUL: quatre coordonnees nulles rendent chaque comparaison
-- NULL, et une contrainte qui s'evalue a NULL PASSE. `coalesce(…, false)`
-- existe pour cette ligne-la.
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(
    p_bbox => 'array[null,null,null,null]::double precision[]'),
  '23514', 'une boite de quatre nuls sans position');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_bbox => 'array[60,20,10,30]::double precision[]'),
  '23514', 'une boite dont x0 depasse x1');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_bbox => 'array[10,20,60]::double precision[]'),
  '23514', 'une boite a trois coordonnees');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_confidence => '1.0'),
  '23514', 'une confiance de 1: une certitude affichee');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_confidence => '-0.1'),
  '23514', 'une confiance negative');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_confidence => 'null'),
  '23514', 'une proposition sans confiance');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_method => 'null'),
  '23514', 'une proposition sans methode (piege du nul)');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_method => '''devine'''),
  '23514', 'une methode inconnue');
select pg_temp.esc_doit_refuser(pg_temp.esc_proposition(p_kind => '''Beam Width'''),
  '23514', 'une categorie hors vocabulaire');

-- LA FORME DE LA VALEUR: {value, unit}, et rien d'autre.
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_valeur => '''{"value": 30}'''),
  '23514', 'une valeur sans unite declaree (meme nulle)');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_valeur => '''{"value": 30, "unit": "cm", "x": 1}'''),
  '23514', 'une cle de plus que value et unit');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_valeur => '''{"value": {"a": 1}, "unit": "cm"}'''),
  '23514', 'une valeur qui n''est ni un nombre ni un texte');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_valeur => '''{"value": " ", "unit": null}'''),
  '23514', 'un texte blanc');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_proposition(p_valeur => '''{"value": 30, "unit": ""}'''),
  '23514', 'une unite vide au lieu de null');

-- DEUX FORMES CONFORMES: une boite (PDF), une position seule (DXF).
insert into extractions (id, org_id, project_id, document_id, kind,
                         proposed_value, status, page, bbox, position,
                         confidence, model_name, raw_text, method,
                         element_label)
values ('e0c00000-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'd0c00000-0000-0000-0000-000000000001', 'beam_width',
        '{"value": 30, "unit": "cm"}', 'proposed', 1,
        array[10, 20, 60, 30]::double precision[], null, 0.8,
        'FICTIF-extracteur/0', 'P1 30x60', 'texte_natif', 'P1'),
       ('e0c00000-0000-0000-0000-000000000002',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'd0c00000-0000-0000-0000-000000000001', 'concrete_class',
        '{"value": "C30/37", "unit": null}', 'proposed', 1, null,
        '{"space": "modelspace", "layer": "TEXTE", "handle": "2A"}',
        0.9, 'FICTIF-extracteur/0', 'Beton C30/37', 'dxf', null),
       ('e0c00000-0000-0000-0000-000000000003',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'd0c00000-0000-0000-0000-000000000001', 'beam_depth',
        '{"value": 60, "unit": "cm"}', 'proposed', 1,
        array[10, 20, 60, 30]::double precision[], null, 0.8,
        'FICTIF-extracteur/0', 'P1 30x60', 'texte_natif', 'P1'),
       ('e0c00000-0000-0000-0000-000000000004',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'd0c00000-0000-0000-0000-000000000001', 'load_value',
        '{"value": 2.5, "unit": "kN/m^2"}', 'proposed', 2,
        array[100, 200, 160, 210]::double precision[], null, 0.7,
        'FICTIF-extracteur/0', 'Q = 2,5 kN/m2', 'texte_natif', null);


-- ---------------------------------------------------------------------
-- 42. Une decision dit ce qu'elle dit, et porte un nom
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(
  $q$insert into extractions (org_id, project_id, document_id, kind,
       proposed_value, final_value, status, page, bbox, confidence, model_name,
       raw_text, method, confirmed_by, confirmed_at, confirmed_by_name)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001',
       'd0c00000-0000-0000-0000-000000000001', 'beam_width',
       '{"value": 30, "unit": "cm"}', '{"value": 35, "unit": "cm"}',
       'confirmed', 1, array[1,2,3,4]::double precision[], 0.5, 'FICTIF/0',
       'P1 30x60', 'texte_natif', '11111111-1111-1111-1111-111111111111',
       now(), 'FICTIF Alice')$q$,
  '23514', 'une confirmation dont la valeur retenue n''est pas la proposee');

select pg_temp.esc_doit_refuser(
  $q$insert into extractions (org_id, project_id, document_id, kind,
       proposed_value, final_value, status, page, bbox, confidence, model_name,
       raw_text, method, confirmed_by, confirmed_at, confirmed_by_name)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001',
       'd0c00000-0000-0000-0000-000000000001', 'beam_width',
       '{"value": 30, "unit": "cm"}', '{"value": 30.0, "unit": "cm"}',
       'corrected', 1, array[1,2,3,4]::double precision[], 0.5, 'FICTIF/0',
       'P1 30x60', 'texte_natif', '11111111-1111-1111-1111-111111111111',
       now(), 'FICTIF Alice')$q$,
  '23514', 'une correction identique a la proposition (30 = 30,0)');

select pg_temp.esc_doit_refuser(
  $q$insert into extractions (org_id, project_id, document_id, kind,
       proposed_value, final_value, status, page, bbox, confidence, model_name,
       raw_text, method, confirmed_by, confirmed_at, confirmed_by_name)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001',
       'd0c00000-0000-0000-0000-000000000001', 'beam_width',
       '{"value": 30, "unit": "cm"}', '{"value": 30, "unit": "cm"}',
       'rejected', 1, array[1,2,3,4]::double precision[], 0.5, 'FICTIF/0',
       'P1 30x60', 'texte_natif', '11111111-1111-1111-1111-111111111111',
       now(), 'FICTIF Alice')$q$,
  '23514', 'un rejet qui retient une valeur');

select pg_temp.esc_doit_refuser(
  $q$insert into extractions (org_id, project_id, document_id, kind,
       proposed_value, final_value, status, page, bbox, confidence, model_name,
       raw_text, method, confirmed_by, confirmed_at)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001',
       'd0c00000-0000-0000-0000-000000000001', 'beam_width',
       '{"value": 30, "unit": "cm"}', '{"value": 30, "unit": "cm"}',
       'confirmed', 1, array[1,2,3,4]::double precision[], 0.5, 'FICTIF/0',
       'P1 30x60', 'texte_natif', '11111111-1111-1111-1111-111111111111',
       now())$q$,
  '23514', 'une confirmation sans nom de personne');

select pg_temp.esc_doit_refuser(
  $q$insert into extractions (org_id, project_id, document_id, kind,
       proposed_value, status, page, bbox, confidence, model_name,
       raw_text, method)
     values ('aaaaaaaa-0000-0000-0000-000000000001',
       'cccccccc-0000-0000-0000-000000000001',
       'd0c00000-0000-0000-0000-000000000001', 'beam_width',
       '{"value": 30, "unit": "cm"}', 'rejected', 1,
       array[1,2,3,4]::double precision[], 0.5, 'FICTIF/0', 'P1 30x60',
       'texte_natif')$q$,
  '23514', 'un rejet anonyme');

select pg_temp.esc_doit_refuser(
  $q$update extractions
        set confirmed_by = '11111111-1111-1111-1111-111111111111'
      where id = 'e0c00000-0000-0000-0000-000000000003'$q$,
  '23514', 'une proposition qui porterait un decideur sans decision');

-- LE CHEMIN NOMINAL: une confirmation signee, nommee, datee.
update extractions
   set status = 'confirmed',
       final_value = proposed_value,
       confirmed_by = '11111111-1111-1111-1111-111111111111',
       confirmed_by_name = 'FICTIF Alice',
       confirmed_at = now()
 where id = 'e0c00000-0000-0000-0000-000000000001';

-- UNE CORRECTION: la valeur retenue differe, elle porte la meme signature.
update extractions
   set status = 'corrected',
       final_value = '{"value": 650, "unit": "mm"}',
       confirmed_by = '33333333-3333-3333-3333-333333333333',
       confirmed_by_name = 'FICTIF Carla',
       confirmed_at = now(),
       decision_note = 'FICTIF: hauteur lue sur la coupe A-A'
 where id = 'e0c00000-0000-0000-0000-000000000003';


-- ---------------------------------------------------------------------
-- 43. Une decision est definitive; la provenance ne change jamais
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(
  $q$update extractions set status = 'rejected', final_value = null
      where id = 'e0c00000-0000-0000-0000-000000000001'$q$,
  '23001', 'revenir sur une confirmation');

select pg_temp.esc_doit_refuser(
  $q$update extractions set final_value = '{"value": 700, "unit": "mm"}'
      where id = 'e0c00000-0000-0000-0000-000000000003'$q$,
  '23001', 'retoucher une valeur corrigee');

select pg_temp.esc_doit_refuser(
  $q$update extractions set raw_text = 'P1 35x60'
      where id = 'e0c00000-0000-0000-0000-000000000002'$q$,
  '23001', 'reecrire le texte lu d''une proposition en attente');

select pg_temp.esc_doit_refuser(
  $q$update extractions set proposed_value = '{"value": "C35/45", "unit": null}'
      where id = 'e0c00000-0000-0000-0000-000000000002'$q$,
  '23001', 'reecrire la valeur proposee');

select pg_temp.esc_doit_refuser(
  $q$update extractions set page = 2
      where id = 'e0c00000-0000-0000-0000-000000000002'$q$,
  '23001', 'deplacer une proposition dans le document');

select pg_temp.esc_doit_refuser(
  $q$update extractions set confidence = 0.99
      where id = 'e0c00000-0000-0000-0000-000000000002'$q$,
  '23001', 'rehausser apres coup la confiance d''une proposition');

select pg_temp.esc_doit_refuser(
  $q$update extractions set document_id = '99999999-0000-0000-0000-000000000001'
      where id = 'e0c00000-0000-0000-0000-000000000002'$q$,
  '23001', 'rattacher une proposition a un autre document');


-- ---------------------------------------------------------------------
-- 44. L'identite d'un document ne change pas; son analyse se fige
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(
  format($q$update documents set sha256 = %L, storage_path = %L
      where id = 'd0c00000-0000-0000-0000-000000000001'$q$,
    repeat('d7', 32), 'pieces/' || repeat('d7', 32) || '.pdf'),
  '23001', 'changer les octets d''un document deja cite');

select pg_temp.esc_doit_refuser(
  $q$update documents set filename = 'autre.pdf'
      where id = 'd0c00000-0000-0000-0000-000000000001'$q$,
  '23001', 'renommer un document deja depose');

select pg_temp.esc_doit_refuser(
  $q$update documents set uploaded_by = '33333333-3333-3333-3333-333333333333'
      where id = 'd0c00000-0000-0000-0000-000000000001'$q$,
  '23001', 'changer le deposant');

select pg_temp.esc_doit_refuser(
  $q$update documents set analysis_status = 'echec', analysis_detail = 'x'
      where id = 'd0c00000-0000-0000-0000-000000000001'$q$,
  '23001', 'reecrire l''analyse d''un document qui porte des propositions');

-- UN DOCUMENT SANS PROPOSITION PEUT ETRE ANALYSE A NOUVEAU (echec, DWG non lu).
insert into documents (id, org_id, project_id, kind, filename, storage_path,
                       mime_type, size_bytes, sha256, uploaded_by,
                       storage_backend, format, analysis_status,
                       analysis_detail)
values ('d0c00000-0000-0000-0000-000000000002',
        'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000001',
        'architect_drawing', 'FICTIF-plan.dwg',
        'pieces/a/c/' || repeat('e8', 32) || '.dwg', 'image/vnd.dwg',
        2048, repeat('e8', 32), '11111111-1111-1111-1111-111111111111',
        'local', 'dwg', 'non_lu', 'FICTIF: DWG conserve, non lu');
update documents
   set analysis_status = 'analyse', analysis_detail = null,
       extractor_version = 'FICTIF-extracteur/1', analysed_at = now()
 where id = 'd0c00000-0000-0000-0000-000000000002';

do $$
begin
  if (select analysis_status from documents
       where id = 'd0c00000-0000-0000-0000-000000000002') <> 'analyse' then
    raise exception 'une nouvelle analyse d''un document sans proposition a ete refusee';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 45. Le produit ne supprime rien; le rapprochement lit des octets
-- ---------------------------------------------------------------------
do $$
declare
  lues text;
begin
  if has_table_privilege('eurostruct_normative_writer', 'public.documents', 'DELETE')
     or has_table_privilege('eurostruct_normative_writer', 'public.extractions', 'DELETE')
  then
    raise exception 'le proprietaire des primitives peut supprimer une piece ou une proposition';
  end if;

  if not has_table_privilege('eurostruct_normative_writer', 'public.extractions', 'UPDATE')
     or not has_table_privilege('eurostruct_normative_writer', 'public.documents', 'INSERT') then
    raise exception 'le proprietaire des primitives ne peut pas ecrire ce que les primitives ecrivent';
  end if;

  select string_agg(distinct a.attname, ',' order by a.attname) into lues
    from pg_attribute a
    cross join lateral aclexplode(a.attacl) acl
   where a.attrelid = 'public.documents'::regclass
     and a.attnum > 0 and not a.attisdropped
     and acl.privilege_type = 'SELECT'
     and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation';
  if lues is distinct from
     'id,org_id,project_id,sha256,size_bytes,storage_backend,storage_path' then
    raise exception 'le rapprochement lit « % » sur documents', coalesce(lues, '(rien)');
  end if;

  if has_table_privilege('eurostruct_reconciliation', 'public.extractions', 'SELECT') then
    raise exception 'le rapprochement lit les propositions: il n''en a aucun usage';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 46. Six primitives, au seul backend authentifie
-- ---------------------------------------------------------------------
do $$
declare
  r record;
  n integer := 0;
begin
  for r in
    select p.oid::regprocedure::text as nom,
           has_function_privilege('public', p.oid, 'EXECUTE') as pub,
           has_function_privilege('eurostruct_authority_backend', p.oid, 'EXECUTE') as backend,
           p.prosecdef
      from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
     where ns.nspname = 'public'
       and p.proname in ('project_document_register',
                         'project_document_record_analysis',
                         'project_document_list', 'project_document_bytes',
                         'project_extraction_list', 'project_extraction_decide')
  loop
    n := n + 1;
    if r.pub then raise exception 'PUBLIC execute %', r.nom; end if;
    if not r.backend then raise exception 'le backend n''execute pas %', r.nom; end if;
    if not r.prosecdef then raise exception '% n''est pas SECURITY DEFINER', r.nom; end if;
  end loop;
  if n <> 6 then
    raise exception 'six primitives attendues, % trouvees', n;
  end if;

  -- LES GARDES NE SONT PAS DES PRIMITIVES: personne ne les appelle.
  if has_function_privilege('eurostruct_authority_backend',
                            'project_extraction_garde()', 'EXECUTE')
     or has_function_privilege('public', 'project_document_garde()', 'EXECUTE') then
    raise exception 'une garde de 0028 est executable hors declencheur';
  end if;
end
$$;


\echo ''
\echo '================================================='
\echo ' Pieces deposees et propositions tracees verifiees.'
\echo '================================================='
