-- =====================================================================
-- EUROSTRUCT — 0029: une proposition peut venir de la geometrie du dessin
--
-- Ce que ces tests protegent: la methode `geometrie` est ADMISE, et elle
-- n'admet RIEN DE PLUS que les autres. Une portee mesuree entre deux appuis
-- doit porter un texte (la derivation), une page, une POSITION (calques,
-- poignees, coordonnees), une confiance dans [0, 1[ et une version — et elle
-- se decide par le meme circuit, sous un nom.
--
-- Suppose 01_guarantees.sql et 06_documents_extractions.sql appliques
-- (l'organisation A, son projet, et le document FICTIF d0c0…0001 existent).
-- Toutes les donnees sont FICTIVES.
-- =====================================================================

\set ON_ERROR_STOP on

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

-- Une proposition GEOMETRIQUE conforme: pas de boite de page, une position.
create or replace function pg_temp.esc_geometrie(
  p_position text default $p$'{"source": "geometry", "space": "modelspace",
    "drawing_units": "cm", "span": {"from": "column:A1", "to": "column:B1"},
    "entities": [{"handle": "5C", "layer": "COFFRAGE"}]}'$p$,
  p_bbox text default 'null',
  p_method text default '''geometrie''',
  p_raw text default $r$'P1 — travee 1/2: C1 · A1 -> C1 · B1, entre-axes 600 cm'$r$,
  p_confidence text default '0.6',
  p_kind text default '''beam_span''')
returns text language sql as $$
  select format(
    'insert into extractions (org_id, project_id, document_id, kind, '
    'proposed_value, status, page, bbox, position, confidence, model_name, '
    'raw_text, method, element_label) values ('
    '''aaaaaaaa-0000-0000-0000-000000000001'', '
    '''cccccccc-0000-0000-0000-000000000001'', '
    '''d0c00000-0000-0000-0000-000000000001'', %s, '
    '''{"value": 600, "unit": "cm"}''::jsonb, ''proposed'', 1, %s, %s::jsonb, '
    '%s, ''FICTIF-extracteur/0'', %s, %s, ''P1'') returning id',
    p_kind, p_bbox, p_position, p_confidence, p_raw, p_method);
$$;


-- ---------------------------------------------------------------------
-- 60. La methode `geometrie` est admise, avec une position et sans boite
-- ---------------------------------------------------------------------
do $$
declare
  ident uuid;
begin
  execute pg_temp.esc_geometrie() into ident;
  if ident is null then
    raise exception 'ECHEC: une portee geometrique conforme a ete refusee';
  end if;
  execute pg_temp.esc_geometrie(p_kind => '''beam_clear_span''') into ident;
  execute pg_temp.esc_geometrie(p_kind => '''cantilever_length''') into ident;
end;
$$;


-- ---------------------------------------------------------------------
-- 61. Et rien de plus que les autres methodes
-- ---------------------------------------------------------------------
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_position => 'null'),
  '23514', 'une proposition geometrique sans position ni boite');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_position => $p$'["5C", "6D"]'$p$),
  '23514', 'une position qui n''est pas un objet');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_raw => $r$'   '$r$),
  '23514', 'une proposition geometrique sans derivation ecrite');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_confidence => '1.0'),
  '23514', 'une mesure geometrique presentee comme certaine');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_method => '''geometry'''),
  '23514', 'une methode hors vocabulaire (geometry n''est pas geometrie)');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_method => 'null'),
  '23514', 'une methode nulle (piege du nul)');
select pg_temp.esc_doit_refuser(
  pg_temp.esc_geometrie(p_kind => '''Beam Span'''),
  '23514', 'une categorie hors vocabulaire');


-- ---------------------------------------------------------------------
-- 62. La decision suit le meme circuit
-- ---------------------------------------------------------------------
do $$
declare
  ident uuid;
begin
  execute pg_temp.esc_geometrie(p_kind => '''grid_spacing''') into ident;
  -- UNE CONFIRMATION SANS ACTEUR NI DATE est refusee, quelle que soit la
  -- methode qui a propose.
  begin
    update extractions set status = 'confirmed',
           final_value = proposed_value where id = ident;
    raise exception 'ACCEPTE A TORT: une confirmation geometrique sans acteur';
  exception when check_violation then
    null;
  end;
  update extractions
     set status = 'confirmed', final_value = proposed_value,
         confirmed_by = '11111111-1111-1111-1111-111111111111',
         confirmed_at = now(), confirmed_by_name = 'FICTIF Ing. A'
   where id = ident;
  -- UNE DECISION EST DEFINITIVE, ET LA PROVENANCE NE CHANGE JAMAIS — methode
  -- comprise. Le declencheur de 0028 refuse par `restrict_violation`.
  perform pg_temp.esc_doit_refuser(
    format('update extractions set method = %L where id = %L', 'dxf', ident),
    '23001', 'une methode reecrite apres coup');
  perform pg_temp.esc_doit_refuser(
    format('update extractions set status = %L where id = %L', 'rejected', ident),
    '23001', 'une decision geometrique reprise');
end;
$$;


-- ---------------------------------------------------------------------
-- 63. La contrainte garde son caractere `not valid`, et ses exigences
-- ---------------------------------------------------------------------
do $$
declare
  definition text;
  valide boolean;
begin
  select pg_get_constraintdef(c.oid), c.convalidated into definition, valide
    from pg_constraint c
   where c.conrelid = 'public.extractions'::regclass
     and c.conname = 'extraction_is_traced';
  if valide then
    raise exception 'ECHEC: extraction_is_traced est devenue validee';
  end if;
  if position('geometrie' in definition) = 0
     or position('texte_natif' in definition) = 0
     or position('ocr' in definition) = 0
     or position('dxf' in definition) = 0
     or position('vision' in definition) = 0 then
    raise exception 'ECHEC: les cinq methodes ne sont pas toutes admises: %',
      definition;
  end if;
end;
$$;

\echo ''
\echo '================================================='
\echo ' Propositions geometriques tracees verifiees.'
\echo '================================================='
