-- 0029 — UNE PROPOSITION PEUT VENIR DE LA GEOMETRIE DU DESSIN
--
-- LE DEFAUT QUE CETTE MIGRATION FERME
-- -------------------------------------
-- Depuis 0028, une proposition dit COMMENT elle a ete lue: `texte_natif`
-- (couche texte d'un PDF), `ocr`, `dxf` (un texte ou une cote du dessin),
-- `vision`. Aucune de ces methodes ne decrit une portee MESUREE entre deux
-- appuis reconnus dans les traits d'un DXF: aucun texte ne l'ecrit, aucune
-- cote ne la porte forcement. L'enregistrer sous `dxf` la ferait passer pour
-- lue, ce qu'elle n'est pas; la refuser obligerait l'ingenieur a ressaisir
-- ce que le dessin montre.
--
-- CE QUE CETTE MIGRATION CHANGE, ET RIEN DE PLUS
-- ------------------------------------------------
-- Une methode de plus, `geometrie`, dans la contrainte de tracabilite de
-- 0028. La contrainte est REMPLACEE A L'IDENTIQUE — memes exigences: texte
-- brut, page, boite OU position, confiance dans [0, 1[, version, categorie
-- au vocabulaire — et reste `not valid`, comme l'originale. Une proposition
-- geometrique n'a pas de boite de page: elle porte une POSITION (calques,
-- poignees, coordonnees du dessin), que la contrainte exige deja.
--
-- RIEN D'AUTRE NE CHANGE. Aucune table, aucune primitive, aucun role, aucune
-- politique. Une proposition geometrique entre `proposed` comme les autres,
-- se decide par la meme primitive, sous le meme nom, et se controle au calcul
-- par la meme egalite exacte. Les categories nouvelles (portee libre,
-- console) sont deja admises par l'expression `^[a-z][a-z0-9_]{1,63}$`; le
-- modele structurel reconstruit voyage dans `analysis_report`, deja `jsonb`
-- et deja fige des qu'une proposition existe (0028).
--
-- 0028 N'EST PAS MODIFIEE: une migration appliquee est une histoire, et la
-- corriger en place ferait diverger les bases deja deployees de celles qui
-- le seront.

begin;

alter table extractions drop constraint if exists extraction_is_traced;

-- CHAQUE CONTRAINTE RESTE ENVELOPPEE DANS `coalesce(…, false)` (0028): une
-- methode nulle evaluerait `method in (…)` a NULL, et NULL passe un `check`.
alter table extractions
  add constraint extraction_is_traced check (coalesce(
    btrim(coalesce(raw_text, '')) <> ''
    and page >= 1
    and (
      (array_length(bbox, 1) = 4
       and array_position(bbox, null) is null
       and bbox[1] <= bbox[3] and bbox[2] <= bbox[4])
      or jsonb_typeof(position) = 'object')
    and confidence >= 0 and confidence < 1
    and method in ('texte_natif', 'ocr', 'dxf', 'vision', 'geometrie')
    and btrim(coalesce(model_name, '')) <> ''
    and kind ~ '^[a-z][a-z0-9_]{1,63}$',
    false)) not valid;

comment on column extractions.method is
  'texte_natif, ocr, dxf, vision ou geometrie. Une proposition ne dit jamais '
  'plus que ce que sa methode a pu lire; geometrie: mesuree sur les traits '
  'd''un DXF (appuis reconnus, entre-axes, nu a nu), position = calques, '
  'poignees et coordonnees du dessin.';


-- ---------------------------------------------------------------------
-- CE QUE CETTE MIGRATION DOIT AVOIR OBTENU
-- ---------------------------------------------------------------------
do $$
declare
  definition text;
  valide     boolean;
begin
  select pg_get_constraintdef(c.oid), c.convalidated
    into definition, valide
    from pg_constraint c
   where c.conrelid = 'public.extractions'::regclass
     and c.conname = 'extraction_is_traced';
  if definition is null then
    raise exception
      'EXTRACTION_0029_TRACABILITE_ABSENTE: la contrainte de tracabilite a '
      'disparu: plus rien n''exigerait le texte lu, la page ni la position.';
  end if;
  -- LES CINQ METHODES, ET LES EXIGENCES DE 0028 — toutes, pas seulement la
  -- nouvelle. Un remplacement qui en perdrait une ouvrirait la table.
  if position('geometrie' in definition) = 0
     or position('texte_natif' in definition) = 0
     or position('vision' in definition) = 0
     or position('raw_text' in definition) = 0
     or position('bbox' in definition) = 0
     or position('jsonb_typeof' in definition) = 0
     or position('confidence < ' in definition) = 0
     or position('model_name' in definition) = 0
     or position('COALESCE' in upper(definition)) = 0 then
    raise exception
      'EXTRACTION_0029_TRACABILITE_INCOMPLETE: la contrainte ne porte pas '
      'toutes les exigences de 0028 plus la methode geometrie: %', definition;
  end if;
  if valide then
    raise exception
      'EXTRACTION_0029_VALIDATION_INATTENDUE: la contrainte de 0028 est '
      '« not valid » (lignes anterieures ecrites sous d''autres regles); la '
      'remplacer ne doit pas changer ce choix sans le dire.';
  end if;
end;
$$;

-- LA COMPOSITION N'A PAS BOUGE: aucune primitive n'est touchee. On le
-- REVERIFIE quand meme, comme a chaque migration.
do $$
begin
  perform assert_authority_composition();
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
