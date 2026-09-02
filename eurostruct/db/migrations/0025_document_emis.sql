-- 0025 — L'ATTESTATION VIVAIT DANS LA BASE, PAS DANS UN DOCUMENT
--
-- LE DEFAUT QUE CETTE MIGRATION FERME
-- -------------------------------------
-- Un ingenieur habilite atteste une note de calcul: son nom, son role, son
-- numero d'inscription, sa declaration, ses reserves et la date sont ecrits
-- dans `validations`. Le PDF, lui, ne change pas — et c'est heureux: le
-- modifier apres coup detruirait l'empreinte sur laquelle porte l'attestation.
--
-- Consequence: **le document qui circule ne porte pas l'attestation.** Le
-- bureau d'etudes transmet un PDF que rien ne distingue d'un brouillon, et
-- l'attestation reste dans une base que le destinataire ne voit pas. Pour lui,
-- l'etude n'a ete relue par personne.
--
-- CE QUE CETTE MIGRATION AJOUTE, ET RIEN DE PLUS
-- ------------------------------------------------
-- UNE seule primitive, `project_deliverable_issue_attestation`, et elle est
-- SPECIALISEE. Elle n'est pas une seconde fonction de creation de livrable:
-- elle ne sait produire qu'un `issued_calculation_note_pdf`, derive d'une
-- `calculation_note_pdf` VALIDEE du meme projet, et elle refuse tout le reste.
-- La surface du backend authentifie passe de 27 a 28 fonctions, sur decision
-- explicite, et pour ce geste-la uniquement.
--
-- POURQUOI ELLE APPARTIENT AU VALIDATEUR
-- ----------------------------------------
-- Emettre, c'est mettre le document en circulation, et c'est le geste de
-- celui qui repond du calcul. Faire fabriquer le document atteste par un
-- redacteur APRES l'emission aurait exige de rappeler quelqu'un d'autre pour
-- terminer un geste deja pose — et aurait ouvert une fenetre pendant laquelle
-- un livrable emis n'a pas d'attestation lisible.
--
-- L'ORIGINAL NE BOUGE PAS. Il passe de `validated` a `final`, ce que la
-- machine a etats de 0005 autorise, et ses octets restent identiques au bit
-- pres. L'attestation vit dans un SECOND document, qui le REFERENCE.
--
-- `derived_from_id` ET NON `supersedes_id`. Un indice qui remplace efface son
-- predecesseur du circuit; le document emis, lui, ne remplace rien: il derive
-- de l'original, qui reste la piece dont l'empreinte est attestee. Employer
-- `supersedes_id` aurait donne au dossier un sens faux, et la chaine de
-- revision de 0005 aurait exige un indice superieur sans qu'aucun indice
-- nouveau n'existe.
--
-- CE QU'ELLE NE FAIT PAS
-- ------------------------
-- Elle n'ecrit pas d'octets. Le PDF est compose et DEPOSE par l'application,
-- relu, et son empreinte verifiee AVANT que cette fonction soit appelee. Si
-- la transaction echoue ensuite, l'objet devient un orphelin detectable par le
-- scanner de `docs/STOCKAGE.md` §5 ter — cout accepte. L'inverse ne l'est pas:
-- la base ne doit jamais referencer un objet qui n'a pas ete ecrit puis relu.
--
-- CE N'EST PAS UNE SIGNATURE ELECTRONIQUE QUALIFIEE. C'est une attestation
-- metier authentifiee, et le document emis le dit en toutes lettres.

begin;

-- Le droit de creer, le temps de cette migration. Meme raison qu'en 0018 et
-- 0020: `alter function ... owner to` exige CREATE sur le schema.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LE GENRE, ET LE LIEN DE FILIATION
-- ---------------------------------------------------------------------
-- POSTGRESQL 12+ ACCEPTE CET ORDRE DANS UNE TRANSACTION, a la seule condition
-- que la valeur ne soit pas UTILISEE avant le commit. Tout ce qui suit la
-- designe donc par son texte (`kind::text = '...'`) et non par un litteral
-- d'enumeration: un litteral serait resolu a l'analyse, avant le commit, et
-- PostgreSQL le refuserait. Les corps de fonction, eux, ne sont que du texte
-- tant que personne ne les appelle.
alter type deliverable_kind add value if not exists 'issued_calculation_note_pdf';

alter table deliverables
  add column if not exists derived_from_id uuid references deliverables(id);

comment on column deliverables.derived_from_id is
  'Le livrable dont celui-ci DERIVE, sans le remplacer. Distinct de '
  'supersedes_id: un indice remplace, un document emis atteste. '
  'Le document emis reference ainsi la piece dont l''empreinte est attestee.';

-- UN SEUL DOCUMENT EMIS PAR ORIGINAL, ET C'EST LA BASE QUI LE TIENT.
--
-- Deux appels simultanes prendraient tous deux le verrou de la source l'un
-- apres l'autre; sans cet index, le second inserirait un doublon apres que le
-- premier a commite. Un controle applicatif ne suffit pas: entre le `select`
-- et l'`insert`, une autre transaction passe.
create unique index if not exists deliverables_un_seul_derive_par_source
  on deliverables (derived_from_id)
  where derived_from_id is not null;

-- UN DOCUMENT NE DERIVE PAS DE LUI-MEME.
do $$
begin
  if not exists (select 1 from pg_constraint
                  where conname = 'derive_de_un_autre_livrable') then
    alter table deliverables
      add constraint derive_de_un_autre_livrable
      check (derived_from_id is null or derived_from_id <> id);
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 2. LA POLITIQUE D'INSERTION S'OUVRE, ET SEULEMENT SUR CE GENRE
-- ---------------------------------------------------------------------
-- 0023 reserve l'insertion aux redacteurs, et c'est juste: un validateur n'a
-- pas a rediger. Mais le document emis EST insere par le validateur, dans le
-- meme geste que l'emission. L'ouverture est donc bornee au seul genre qu'il
-- peut produire — un validateur ne peut toujours pas creer un brouillon, une
-- note, ni un plan.
drop policy if exists deliverables_atelier_insert on deliverables;
create policy deliverables_atelier_insert on deliverables
  for insert to eurostruct_normative_writer
  with check (
    project_actor_peut_rediger(org_id)
    or (kind::text = 'issued_calculation_note_pdf'
        and project_actor_peut_valider(org_id))
  );


-- ---------------------------------------------------------------------
-- 3. LA FILIATION SE LIT — SANS ELLE, LE LIEN N'EXISTE QUE DANS LA TABLE
-- ---------------------------------------------------------------------
-- `project_deliverable_list` et `project_deliverable_read` sont RECREEES pour
-- rendre `derived_from_id`. Ajouter une colonne a un `returns table` impose un
-- `drop`, donc une reprise de la propriete et des droits en section 5.
drop function if exists project_deliverable_list(uuid);
create function project_deliverable_list(p_project_id uuid)
returns table (
  deliverable_id     uuid,
  calculation_id     uuid,
  kind               deliverable_kind,
  filename           text,
  media_type         text,
  sha256             text,
  size_bytes         bigint,
  state              deliverable_state,
  revision           integer,
  supersedes_id      uuid,
  derived_from_id    uuid,
  watermark          text,
  last_reason        text,
  engine_version     text,
  engine_build_sha   text,
  execution_identity text,
  validation_id      uuid,
  validator_name     text,
  validated_at       timestamptz,
  generated_at       timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  if not exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = p_project_id and m.user_id = acteur) then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  return query
    select d.id, d.calculation_id, d.kind, d.filename, d.media_type,
           d.sha256, d.size_bytes, d.state, d.revision, d.supersedes_id,
           d.derived_from_id,
           d.watermark, d.last_reason, d.engine_version, d.engine_build_sha,
           d.execution_identity, d.validation_id, v.validator_name, v.signed_at,
           d.generated_at
      from deliverables d
      left join validations v on v.id = d.validation_id
     where d.project_id = p_project_id
     order by d.generated_at desc, d.id;
end;
$$;

drop function if exists project_deliverable_read(uuid, uuid);
create function project_deliverable_read(
  p_project_id uuid, p_deliverable_id uuid)
returns table (
  deliverable_id     uuid,
  calculation_id     uuid,
  kind               deliverable_kind,
  filename           text,
  media_type         text,
  storage_backend    text,
  storage_path       text,
  sha256             text,
  size_bytes         bigint,
  state              deliverable_state,
  revision           integer,
  supersedes_id      uuid,
  derived_from_id    uuid,
  watermark          text,
  last_reason        text,
  engine_version     text,
  engine_build_sha   text,
  execution_identity text,
  inputs_hash        text,
  ndp_as_of          date,
  validation_id      uuid,
  validator_name     text,
  validator_role     org_role,
  professional_id    text,
  statement          text,
  reservations       text,
  signed_at          timestamptz,
  transitions        jsonb,
  generated_at       timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  if not exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = p_project_id and m.user_id = acteur) then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  return query
    select d.id, d.calculation_id, d.kind, d.filename, d.media_type,
           d.storage_backend, d.storage_path, d.sha256, d.size_bytes,
           d.state, d.revision, d.supersedes_id, d.derived_from_id,
           d.watermark, d.last_reason,
           d.engine_version, d.engine_build_sha, d.execution_identity,
           d.inputs_hash, d.ndp_as_of,
           d.validation_id, v.validator_name, v.validator_role,
           v.professional_id, v.statement, v.reservations, v.signed_at,
           coalesce((select jsonb_agg(jsonb_build_object(
                       'from_state', t.from_state, 'to_state', t.to_state,
                       'actor_id', t.actor_id, 'reason', t.reason,
                       'occurred_at', t.occurred_at)
                       order by t.occurred_at, t.id)
                      from deliverable_state_transitions t
                     where t.deliverable_id = d.id),
                    '[]'::jsonb),
           d.generated_at
      from deliverables d
      left join validations v on v.id = d.validation_id
     where d.id = p_deliverable_id and d.project_id = p_project_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 4. LA 28e PRIMITIVE — EMETTRE, ET ATTACHER L'ATTESTATION
-- ---------------------------------------------------------------------
-- TOUT SE FAIT DANS UNE SEULE TRANSACTION, et c'est la raison d'etre de cette
-- fonction. Un original passe a `final` sans document emis laisserait un
-- livrable en circulation dont l'attestation reste invisible; un document emis
-- sans original `final` attesterait une piece qui n'a pas ete emise. Les deux
-- moities n'ont de sens qu'ensemble.
create or replace function project_deliverable_issue_attestation(
  p_project_id      uuid,
  p_source_id       uuid,
  p_filename        text,
  p_media_type      text,
  p_storage_backend text,
  p_storage_path    text,
  p_sha256          text,
  p_size_bytes      bigint)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur  uuid := normative_authenticated_actor();
  d       record;
  v       record;
  deja    record;
  emis    uuid;
  touches integer;
begin
  -- LE VERROU AVANT TOUT LE RESTE. Deux emissions simultanees de la meme note
  -- se serialisent ici; la seconde verra l'etat que la premiere a laisse.
  select dl.* into d
    from deliverables dl
   where dl.id = p_source_id and dl.project_id = p_project_id
     for update;
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- LA CAPACITE D'ABORD, ET AVANT MEME DE DIRE SI L'ETAT CONVIENT. Un role
  -- insuffisant doit recevoir un refus de role, pas un diagnostic d'etat qui
  -- lui apprendrait ce qu'il n'a pas le droit de savoir.
  perform project_exiger_capacite(d.org_id, 'validation');

  -- IDEMPOTENCE — UNE REPONSE PERDUE NE DOIT PAS COUTER UN SECOND DOCUMENT.
  --
  -- Le PDF emis est compose depuis des donnees GELEES: deux tentatives
  -- produisent les memes octets, donc la meme empreinte. Si un document emis
  -- existe deja pour cette source et porte cette empreinte, on rend son
  -- identifiant. S'il en porte une AUTRE, quelque chose a change entre les
  -- deux tentatives et on refuse plutot que d'en avoir deux.
  select dl.* into deja
    from deliverables dl
   where dl.derived_from_id = p_source_id;
  if found then
    if deja.sha256 is distinct from p_sha256 then
      raise exception
        'un document emis existe deja pour ce livrable, avec une autre '
        'empreinte (%s enregistree). Deux attestations differentes de la meme '
        'piece ne peuvent pas coexister.', deja.sha256
        using errcode = 'unique_violation';
    end if;
    return deja.id;
  end if;

  -- LE GENRE DE LA SOURCE. Cette primitive n'est pas une fonction de creation
  -- de livrable: elle ne sait attester qu'une note de calcul en PDF.
  if d.kind::text <> 'calculation_note_pdf' then
    raise exception
      'le livrable est de genre « % »: seule une note de calcul en PDF donne '
      'lieu a un document emis. Le plan de ferraillage et la note HTML se '
      'transmettent tels quels.', d.kind
      using errcode = 'restrict_violation';
  end if;

  if d.state <> 'validated' then
    raise exception
      'le livrable est dans l''etat « % »: l''emission exige une attestation '
      'nominative prealable. Aucun document n''est emis sans qu''un ingenieur '
      'habilite ait repondu du calcul.', d.state
      using errcode = 'restrict_violation';
  end if;

  -- L'ATTESTATION DOIT EXISTER, ETRE NOMINATIVE, ET PORTER SUR CES OCTETS-LA.
  --
  -- `deliverable_sha256` est fige au moment de la signature. S'il ne
  -- correspond plus a l'empreinte du livrable, l'attestation porte sur
  -- d'autres octets que ceux qu'on s'apprete a emettre — et le document emis
  -- affirmerait une chose fausse.
  select va.* into v from validations va where va.id = d.validation_id;
  if not found then
    raise exception 'aucune attestation n''est attachee a ce livrable.'
      using errcode = 'restrict_violation';
  end if;
  if coalesce(btrim(v.validator_name), '') = '' then
    raise exception
      'l''attestation attachee ne nomme personne. Un document emis porte le '
      'nom d''une personne.'
      using errcode = 'check_violation';
  end if;
  if v.deliverable_sha256 is distinct from d.sha256 then
    raise exception
      'l''attestation porte sur l''empreinte % alors que le livrable porte %. '
      'Le document emis affirmerait une chose fausse.',
      coalesce(v.deliverable_sha256, '(absente)'), d.sha256
      using errcode = 'check_violation';
  end if;

  -- LES OCTETS DU DOCUMENT EMIS DOIVENT ETRE DECRITS ENTIEREMENT — meme
  -- exigence qu'a la creation d'un livrable, et pour la meme raison: une
  -- ligne qui ne permet pas de retrouver les octets ne vaut rien.
  if coalesce(btrim(p_storage_backend), '') = ''
     or coalesce(btrim(p_storage_path), '') = ''
     or coalesce(btrim(p_sha256), '') = ''
     or coalesce(btrim(p_filename), '') = ''
     or coalesce(btrim(p_media_type), '') = ''
     or coalesce(p_size_bytes, 0) <= 0 then
    raise exception
      'description des octets incomplete (magasin, chemin, empreinte, nom, '
      'type et taille sont tous requis).'
      using errcode = 'check_violation';
  end if;
  if p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception
      'l''empreinte « % » n''a pas la forme d''un SHA-256.', p_sha256
      using errcode = 'check_violation';
  end if;
  if p_sha256 = d.sha256 then
    raise exception
      'le document emis porte la meme empreinte que l''original: il n''en est '
      'donc pas distinct, et l''original ne doit jamais etre modifie.'
      using errcode = 'check_violation';
  end if;

  -- L'ORIGINAL PASSE A `final` PAR LA PRIMITIVE QUI SAIT LE FAIRE. La
  -- reecrire ici donnerait deux definitions de « emettre », qui divergeraient.
  perform project_deliverable_finalize(p_project_id, p_source_id);

  -- LE DOCUMENT EMIS NAIT `final`. Il ne traverse pas le parcours de
  -- relecture: il n'est pas une piece a relire, il EST le compte rendu d'une
  -- relecture deja faite. `is_final` est pose avec `state` parce que le
  -- declencheur de 0005 refuse une insertion ou les deux se contredisent.
  insert into deliverables (
    org_id, project_id, calculation_id, kind, filename, media_type,
    storage_backend, storage_path, sha256, size_bytes,
    state, is_final, validation_id, derived_from_id,
    engine_version, engine_build_sha, execution_identity, inputs_hash,
    ndp_as_of, generated_by)
  values (
    d.org_id, d.project_id, d.calculation_id,
    'issued_calculation_note_pdf'::deliverable_kind,
    btrim(p_filename), btrim(p_media_type),
    btrim(p_storage_backend), btrim(p_storage_path), p_sha256, p_size_bytes,
    'final'::deliverable_state, true, d.validation_id, d.id,
    d.engine_version, d.engine_build_sha, d.execution_identity, d.inputs_hash,
    d.ndp_as_of, acteur)
  returning id into emis;

  get diagnostics touches = row_count;
  if touches <> 1 or emis is null then
    raise exception
      'ATELIER_0025_EMISSION_SANS_DOCUMENT: l''original a ete emis sans que '
      'le document atteste ne soit ecrit. La transaction est annulee: un '
      'livrable en circulation sans attestation lisible est precisement le '
      'defaut que cette migration ferme.'
      using errcode = 'insufficient_privilege';
  end if;

  return emis;
end;
$$;


-- ---------------------------------------------------------------------
-- 5. PROPRIETE ET ACCES
-- ---------------------------------------------------------------------
-- Les deux fonctions RECREEES repartent de `acldefault` apres leur `drop`: le
-- proprietaire redevient le migrateur et PUBLIC retrouve EXECUTE. La nouvelle
-- primitive n'a jamais eu d'autre proprietaire, mais elle passe par le meme
-- traitement pour que rien ne depende de l'ordre.
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_deliverable_list(uuid)',
    'project_deliverable_read(uuid, uuid)',
    'project_deliverable_issue_attestation(uuid, uuid, text, text, text,'
      || ' text, text, bigint)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;
end
$$;

revoke create on schema public from eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 6. CE QUE CETTE MIGRATION DOIT AVOIR OBTENU
-- ---------------------------------------------------------------------
do $$
declare
  proprio  text;
  chemin   text;
  securite boolean;
  corps    text;
begin
  select pg_get_userbyid(p.proowner), p.prosecdef,
         array_to_string(p.proconfig, ','), p.prosrc
    into proprio, securite, chemin, corps
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public'
     and p.proname = 'project_deliverable_issue_attestation';

  if proprio is null then
    raise exception
      'ATELIER_0025_PRIMITIVE_ABSENTE: project_deliverable_issue_attestation '
      'n''existe pas apres la migration.';
  end if;
  if proprio <> 'eurostruct_normative_writer' then
    raise exception
      'ATELIER_0025_PROPRIETAIRE: la primitive appartient a « % ». Elle doit '
      'appartenir au migrateur endosse, sans quoi son SECURITY DEFINER '
      'endosse quelqu''un d''autre.', proprio;
  end if;
  if not securite then
    raise exception
      'ATELIER_0025_SANS_DEFINER: la primitive n''est pas SECURITY DEFINER: '
      'le backend authentifie n''a aucun droit sur `deliverables`.';
  end if;
  if chemin is null or position('search_path=public, pg_temp' in chemin) = 0 then
    raise exception
      'ATELIER_0025_SEARCH_PATH_NON_EPINGLE: proconfig vaut « % ». Un '
      'SECURITY DEFINER sans search_path epingle est detournable.',
      coalesce(chemin, '(nul)');
  end if;

  -- LES CONTROLES QUE LE CORPS DOIT PORTER. Ils sont cherches par leur nom
  -- plutot que deduits: une primitive d'emission qui perdrait l'un d'eux
  -- continuerait a passer les tests nominaux.
  if position('project_exiger_capacite' in corps) = 0 then
    raise exception
      'ATELIER_0025_CAPACITE_NON_EXIGEE: la primitive n''exige aucune '
      'capacite. L''appartenance seule laisserait un redacteur emettre.';
  end if;
  if position('deliverable_sha256' in corps) = 0 then
    raise exception
      'ATELIER_0025_EMPREINTE_NON_CONFRONTEE: la primitive ne confronte pas '
      'l''empreinte attestee a celle du livrable. Le document emis pourrait '
      'attester d''autres octets que ceux qui circulent.';
  end if;
  if position('for update' in corps) = 0 then
    raise exception
      'ATELIER_0025_SANS_VERROU: la primitive ne verrouille pas la source. '
      'Deux emissions simultanees ne se serialiseraient pas.';
  end if;
  if position('row_count' in corps) = 0 then
    raise exception
      'ATELIER_0025_EFFET_NON_CONSTATE: la primitive ne constate pas '
      'row_count. Une politique RLS filtre la ligne, l''insertion ne touche '
      'rien sans lever, et le refus se presente comme un succes.';
  end if;
end;
$$;

-- L'UNICITE DE LA FILIATION EST STRUCTURELLE, PAS APPLICATIVE.
do $$
begin
  if not exists (select 1 from pg_indexes
                  where schemaname = 'public'
                    and indexname = 'deliverables_un_seul_derive_par_source') then
    raise exception
      'ATELIER_0025_DOUBLON_POSSIBLE: l''index unique sur derived_from_id est '
      'absent. Deux emissions concurrentes pourraient ecrire deux documents '
      'emis pour la meme piece.';
  end if;
end;
$$;

-- LA POLITIQUE D'INSERTION S'EST OUVERTE, ET SEULEMENT SUR CE GENRE.
do $$
declare
  insertion text;
begin
  select pg_get_expr(polwithcheck, polrelid) into insertion
    from pg_policy where polname = 'deliverables_atelier_insert';

  if insertion is null or position('peut_rediger' in insertion) = 0 then
    raise exception
      'ATELIER_0025_INSERTION_HORS_MATRICE: la politique d''insertion des '
      'livrables vaut « % »: les redacteurs ne pourraient plus rien creer.',
      coalesce(insertion, '(absente)');
  end if;
  if position('issued_calculation_note_pdf' in insertion) = 0
     or position('peut_valider' in insertion) = 0 then
    raise exception
      'ATELIER_0025_EMISSION_IMPOSSIBLE: la politique d''insertion vaut « % ». '
      'Le validateur ne pourrait pas ecrire le document emis.',
      coalesce(insertion, '(absente)');
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
