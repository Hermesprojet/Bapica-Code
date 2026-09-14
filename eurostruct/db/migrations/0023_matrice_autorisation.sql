-- 0023 — QUI A LE DROIT DE FAIRE QUOI, ET LA BASE LE SAIT
--
-- LA MATRICE, EN UN SEUL ENDROIT
-- --------------------------------
--   membre actif `viewer`                  lecture seulement
--   membre actif `owner`/`admin`/`engineer` redaction: brouillon, revision,
--                                           soumission a la relecture
--   membre actif `validating_engineer`      validation: retour motive,
--                                           attestation, emission
--   membre DESACTIVE                        aucun acces metier, pas meme en
--                                           lecture
--   autre organisation                      rien d'exploitable
--
-- LES CINQ DEFAUTS QU'ELLE FERME, TOUS MESURES SUR LE CHEMIN PRODUIT
-- --------------------------------------------------------------------
-- 1. `is_active` N'ETAIT LU NULLE PART sauf dans la primitive d'attestation.
--    Ni `project_actor_is_member`, ni `project_actor_can_write`, ni
--    `project_workspace_list`, ni aucune primitive de livrable ne le
--    regardaient. Un acces revoque gardait la lecture ET l'ecriture. La
--    colonne existe depuis 0009 et sa raison d'etre y est ecrite: « un acces
--    revoque ne peut plus engager le bureau d'etudes ». Elle ne le pouvait
--    que sur une seule route.
--
-- 2. UN SIMPLE `engineer` POUVAIT EMETTRE un livrable deja atteste:
--    `project_deliverable_finalize` ne controlait aucun role. La separation
--    entre celui qui redige et celui qui repond du calcul disparaissait a la
--    derniere etape, celle qui met le document en circulation.
--
-- 3. UNE MUTATION REFUSEE REPONDAIT 200. Les politiques RLS filtrent la ligne
--    par leur clause `using`: l'`update` touche alors ZERO ligne, SANS erreur,
--    et la primitive rendait quand meme l'etat vise. Un refus qui se presente
--    comme un succes est pire qu'un refus — le client range son document
--    comme soumis, et il ne l'est pas.
--
-- 4. LE `viewer` N'ETAIT BLOQUE QUE PAR ACCIDENT, par la clause `with check`
--    d'une politique ecrite pour decider autre chose. Un blocage accidentel
--    se perd a la premiere reecriture de cette politique, et son message ne
--    dit pas ce qu'il faudrait pour agir.
--
-- 5. `validating_engineer` ETAIT RANGE AVEC LES REDACTEURS par
--    `project_actor_can_write`. Celui qui repond du calcul ne le redige pas:
--    c'est ce qui donne un sens a « relu ».
--
-- CE QUI EST VOLONTAIREMENT CONSERVE
-- ------------------------------------
-- `project_actor_can_write` garde `validating_engineer` pour les PROJETS et
-- les CALCULS. Un ingenieur validateur lance evidemment des calculs; ce qu'il
-- ne fait pas, c'est rediger le livrable qu'il attestera. La separation porte
-- sur le DOCUMENT, pas sur le travail.
--
-- ET CE QUI N'EST PAS RELACHE
-- -----------------------------
-- La ligne d'adhesion desactivee SURVIT — une note de dix ans doit rester
-- lisible et nommer son signataire (0009). Ce qui disparait, c'est l'acces.

begin;

grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LA CAPACITE EXIGEE, ET LE REFUS QUI DIT POURQUOI
-- ---------------------------------------------------------------------
-- UNE SEULE FONCTION POUR TOUS LES MESSAGES. Six primitives qui poseraient
-- chacune leur question poseraient six questions legerement differentes, et
-- c'est la plus faible qui finirait par decider. Celle-ci leve; les predicats
-- booleens plus bas, eux, rendent `false`, parce qu'une fonction qui leve dans
-- une expression de politique RLS ferait echouer en ERREUR une requete qui
-- doit rendre zero ligne.
create or replace function project_exiger_capacite(
  target_org uuid, p_capacite text)
returns org_role
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  m record;
begin
  select * into m from organization_members
   where org_id = target_org and user_id = project_backend_actor();

  if not found then
    raise exception
      'vous n''etes pas membre de cette organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  -- L'ACCES REVOQUE EST REFUSE AVANT LE ROLE, et l'ordre compte: dire « le
  -- role viewer ne redige pas » a quelqu'un dont l'acces est coupe l'enverrait
  -- demander un changement de role qui ne servirait a rien.
  if not m.is_active then
    raise exception
      'votre acces a cette organisation a ete revoque le %: il n''ouvre plus '
      'aucun geste, pas meme la lecture. La ligne d''adhesion est conservee '
      'pour que les documents deja signes restent lisibles.',
      coalesce(m.deactivated_at::date::text, 'une date non enregistree')
      using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'lecture' then
    return m.role;
  end if;

  if p_capacite = 'redaction' then
    if m.role = any (array['owner', 'admin', 'engineer']::org_role[]) then
      return m.role;
    end if;
    raise exception
      'le role « % » ne redige pas de livrable. La creation d''un brouillon, '
      'sa revision et sa soumission a la relecture reviennent aux roles '
      'owner, admin et engineer.', m.role
      using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'validation' then
    if m.role = 'validating_engineer' then
      return m.role;
    end if;
    raise exception
      'le role « % » ne porte pas la validation technique. Le retour motive '
      'au brouillon, l''attestation et l''emission reviennent a l''ingenieur '
      'qui repond de l''etude, porteur du role validating_engineer.', m.role
      using errcode = 'insufficient_privilege';
  end if;

  -- UNE CAPACITE INCONNUE EST UN DEFAUT DE PROGRAMMATION, PAS UN REFUS METIER.
  -- La confondre avec un refus laisserait une faute de frappe ouvrir la porte.
  raise exception
    'ATELIER_0023_CAPACITE_INCONNUE: « % » n''est pas une capacite declaree '
    '(lecture, redaction, validation).', p_capacite;
end;
$$;


-- ---------------------------------------------------------------------
-- 2. LES PREDICATS DES POLITIQUES, ET `is_active` DANS CHACUN
-- ---------------------------------------------------------------------
-- `create or replace` A LA MEME SIGNATURE: proprietaire et ACL sont conserves,
-- il n'y a donc rien a reposer. Un `drop` suivi d'un `create` repartirait de
-- `acldefault` et rouvrirait PUBLIC.
create or replace function project_actor_is_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor()
       and m.is_active);
$$;

create or replace function project_actor_can_write(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor()
       and m.is_active
       and m.role = any(array['owner', 'admin', 'engineer',
                              'validating_engineer']::org_role[]));
$$;

-- REDIGER UN LIVRABLE N'EST PAS ECRIRE UN CALCUL, et les deux predicats
-- different exactement d'un role.
create or replace function project_actor_peut_rediger(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor()
       and m.is_active
       and m.role = any(array['owner', 'admin', 'engineer']::org_role[]));
$$;

create or replace function project_actor_peut_valider(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor()
       and m.is_active
       and m.role = 'validating_engineer');
$$;


-- ---------------------------------------------------------------------
-- 3. LES POLITIQUES DU LIVRABLE SUIVENT LA MATRICE
-- ---------------------------------------------------------------------
-- L'INSERTION EST RESERVEE AUX REDACTEURS. 0020 la donnait a
-- `project_actor_can_write`, qui inclut le validateur: l'ecart se refermait
-- par accident et le message n'expliquait rien.
drop policy if exists deliverables_atelier_insert on deliverables;
create policy deliverables_atelier_insert on deliverables
  for insert to eurostruct_normative_writer
  with check (project_actor_peut_rediger(org_id));

-- L'UPDATE COUVRE LES DEUX CAPACITES, ET LA PRIMITIVE TRANCHE ENTRE ELLES.
-- Une politique ne sait pas quelle transition est demandee; elle borne
-- l'ensemble des acteurs, et `project_deliverable_transition` decide lequel
-- peut faire quoi. Deux frontieres, la plus fine dans la primitive.
drop policy if exists deliverables_atelier_update on deliverables;
create policy deliverables_atelier_update on deliverables
  for update to eurostruct_normative_writer
  using (project_actor_peut_rediger(org_id)
         or project_actor_peut_valider(org_id))
  with check (project_actor_peut_rediger(org_id)
              or project_actor_peut_valider(org_id));

-- L'ATTESTATION EST ECRITE PAR LE VALIDATEUR, ET PAR LUI SEUL.
drop policy if exists validations_atelier_insert on validations;
create policy validations_atelier_insert on validations
  for insert to eurostruct_normative_writer
  with check (project_actor_peut_valider(org_id));


-- ---------------------------------------------------------------------
-- 4. LA LISTE DES PROJETS N'EST PLUS CELLE D'UN ANCIEN MEMBRE
-- ---------------------------------------------------------------------
-- LA POLITIQUE DE `projects` LA FERME DEJA, maintenant que
-- `project_actor_is_member` lit `is_active`. On l'ecrit quand meme ICI, dans
-- la jointure, parce que cette fonction LIT `organization_members` pour en
-- rendre le role: sans le predicat explicite, elle rendrait `member_role` et
-- `member_active` d'une adhesion revoquee si la politique venait a changer.
-- Deux endroits disent la meme chose, et aucun ne peut la dire seul.
drop function if exists project_workspace_list();

create or replace function project_workspace_list()
returns table (
  project_id      uuid,
  org_id          uuid,
  org_name        text,
  name            text,
  reference       text,
  country         country_code,
  region          text,
  ndp_as_of       date,
  created_at      timestamptz,
  calculation_count bigint,
  member_role     org_role,
  member_name     text,
  member_active   boolean)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  return query
    select p.id, p.org_id, o.name, p.name, p.reference, p.country, p.region,
           p.ndp_as_of, p.created_at,
           (select count(*) from calculations c where c.project_id = p.id),
           m.role, m.display_name, m.is_active
      from projects p
      join organizations o on o.id = p.org_id
      join organization_members m
        on m.org_id = p.org_id and m.user_id = acteur and m.is_active
     where p.archived_at is null
     order by p.created_at desc, p.id;
end;
$$;


-- ---------------------------------------------------------------------
-- 5. LES PRIMITIVES DE LIVRABLE EXIGENT LEUR CAPACITE, ET CONSTATENT LEUR EFFET
-- ---------------------------------------------------------------------

-- 5.1 CREER UN BROUILLON — capacite `redaction`
drop function if exists project_deliverable_create(
  uuid, uuid, deliverable_kind, text, text, text, text, text, bigint, text, uuid);

create or replace function project_deliverable_create(
  p_project_id      uuid,
  p_calculation_id  uuid,
  p_kind            deliverable_kind,
  p_filename        text,
  p_media_type      text,
  p_storage_backend text,
  p_storage_path    text,
  p_sha256          text,
  p_size_bytes      bigint,
  p_watermark       text default null,
  p_supersedes_id   uuid default null)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur   uuid := normative_authenticated_actor();
  org      uuid;
  c        record;
  indice   integer := 1;
  livrable uuid;
begin
  -- L'ORGANISATION D'ABORD, LA CAPACITE ENSUITE. Sans le projet on ne sait pas
  -- DANS QUELLE organisation la capacite doit etre exigee, et un membre de
  -- l'organisation voisine ne doit rien apprendre de plus que « introuvable ».
  select p.org_id into org from projects p where p.id = p_project_id;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(org, 'redaction');

  select cl.id, cl.execution_identity, cl.engine_build_sha, cl.inputs_hash,
         cl.ndp_as_of, e.version as engine_version
    into c
    from calculations cl
    join engine_versions e on e.id = cl.engine_version_id
   where cl.id = p_calculation_id and cl.project_id = p_project_id;
  if not found then
    raise exception
      'le calcul % n''appartient pas au projet %.',
      p_calculation_id, p_project_id
      using errcode = 'insufficient_privilege';
  end if;

  perform project_calculation_is_publishable(p_calculation_id);

  if coalesce(btrim(p_storage_backend), '') = ''
     or coalesce(btrim(p_storage_path), '') = ''
     or coalesce(btrim(p_sha256), '') = ''
     or coalesce(btrim(p_filename), '') = ''
     or coalesce(btrim(p_media_type), '') = ''
     or coalesce(p_size_bytes, 0) <= 0 then
    raise exception
      'description des octets incomplete (magasin, chemin, empreinte, nom, '
      'type et taille sont tous requis). Un chemin qui ne permet pas de '
      'retrouver les octets n''est pas enregistre.'
      using errcode = 'check_violation';
  end if;

  if p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception
      'l''empreinte « % » n''est pas un sha256 hexadecimal minuscule.', p_sha256
      using errcode = 'check_violation';
  end if;

  if p_supersedes_id is not null then
    select d.revision + 1 into indice
      from deliverables d
     where d.id = p_supersedes_id and d.project_id = p_project_id;
    if indice is null then
      raise exception
        'le livrable remplace % n''appartient pas au projet %.',
        p_supersedes_id, p_project_id
        using errcode = 'insufficient_privilege';
    end if;
  end if;

  insert into deliverables (
    org_id, project_id, calculation_id, kind, filename, media_type,
    storage_backend, storage_path, sha256, size_bytes, watermark,
    engine_version, engine_build_sha, execution_identity, inputs_hash,
    ndp_as_of, state, revision, supersedes_id, generated_by)
  values (
    org, p_project_id, p_calculation_id, p_kind, btrim(p_filename),
    btrim(p_media_type), btrim(p_storage_backend), btrim(p_storage_path),
    p_sha256, p_size_bytes, p_watermark,
    c.engine_version, c.engine_build_sha, c.execution_identity, c.inputs_hash,
    c.ndp_as_of, 'draft', indice, p_supersedes_id, acteur)
  returning id into livrable;

  return livrable;
end;
$$;


-- 5.2 SOUMETTRE, OU RENVOYER AU BROUILLON — deux capacites distinctes
--
-- SOUMETTRE EST UN GESTE DE REDACTEUR: on presente son travail. RENVOYER est
-- un geste de RELECTEUR: on refuse ce qu'on vient de lire, avec un motif. Les
-- confondre laisserait le redacteur se renvoyer sa propre piece en inventant
-- le reproche.
drop function if exists project_deliverable_transition(
  uuid, uuid, deliverable_state, text);

create or replace function project_deliverable_transition(
  p_project_id     uuid,
  p_deliverable_id uuid,
  p_to_state       deliverable_state,
  p_reason         text default null)
returns deliverable_state
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur  uuid := normative_authenticated_actor();
  d       record;
  touches integer;
begin
  select dl.* into d
    from deliverables dl
   where dl.id = p_deliverable_id and dl.project_id = p_project_id;
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  if p_to_state not in ('draft', 'review') then
    raise exception
      'cette primitive ne conduit qu''a « draft » ou « review ». La validation '
      'et l''emission ont leur propre porte, avec leurs propres controles.'
      using errcode = 'insufficient_privilege';
  end if;

  -- LA CAPACITE DEPEND DU SENS DE LA TRANSITION.
  if p_to_state = 'review' then
    perform project_exiger_capacite(d.org_id, 'redaction');
  else
    perform project_exiger_capacite(d.org_id, 'validation');
  end if;

  if p_to_state = d.state then
    raise exception
      'le livrable est deja dans l''etat « % »: il n''y a rien a faire, et '
      'l''enregistrer comme une transition ecrirait un motif que l''historique '
      'ne porterait pas.', d.state
      using errcode = 'restrict_violation';
  end if;

  if p_to_state = 'draft' and coalesce(btrim(p_reason), '') = '' then
    raise exception
      'un retour au brouillon exige un motif: celui qui reprend le document '
      'doit savoir ce qui lui est reproche.'
      using errcode = 'check_violation';
  end if;

  update deliverables
     set state = p_to_state,
         last_reason = nullif(btrim(coalesce(p_reason, '')), ''),
         submitted_for_review_at =
           case when p_to_state = 'review' then now()
                else submitted_for_review_at end,
         submitted_by =
           case when p_to_state = 'review' then acteur else submitted_by end
   where id = p_deliverable_id;

  -- ZERO LIGNE TOUCHEE N'EST PAS UN SUCCES.
  --
  -- MESURE DU JOUR: une politique RLS filtre la ligne par sa clause `using`,
  -- l'`update` ne touche RIEN, PostgreSQL ne leve pas, et cette fonction
  -- rendait quand meme l'etat vise. Le client apprenait que sa soumission
  -- avait abouti. Les controles ci-dessus rendent ce cas improbable; ce
  -- constat le rend impossible.
  get diagnostics touches = row_count;
  if touches <> 1 then
    raise exception
      'ATELIER_0023_TRANSITION_SANS_EFFET: la transition vers « % » n''a '
      'touche aucune ligne. Un refus ne doit pas se presenter comme un '
      'succes.', p_to_state
      using errcode = 'insufficient_privilege';
  end if;

  return p_to_state;
end;
$$;


-- 5.3 L'ATTESTATION — capacite `validation`, et le nom vient de l'adhesion
drop function if exists project_deliverable_validate(uuid, uuid, text, text);

create or replace function project_deliverable_validate(
  p_project_id     uuid,
  p_deliverable_id uuid,
  p_statement      text,
  p_reservations   text default null)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur     uuid := normative_authenticated_actor();
  d          record;
  c          record;
  membre     record;
  nom        text;
  validation uuid;
  touches    integer;
begin
  select dl.* into d
    from deliverables dl
   where dl.id = p_deliverable_id and dl.project_id = p_project_id;
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- LA CAPACITE D'ABORD: membre, actif, porteur du role de validation. Les
  -- trois messages sont ceux de `project_exiger_capacite`, ecrits une fois.
  perform project_exiger_capacite(d.org_id, 'validation');

  select m.* into membre from organization_members m
   where m.org_id = d.org_id and m.user_id = acteur;

  -- LE NOM VIENT DE L'ADHESION, ET S'IL MANQUE ON REFUSE. Substituer
  -- l'identifiant technique donnerait une attestation signee « 3f2a-… », qui
  -- ne nomme personne tout en ayant l'air complete.
  nom := nullif(btrim(coalesce(membre.display_name, '')), '');
  if nom is null then
    raise exception
      'aucun nom n''est enregistre pour votre adhesion. Une attestation porte '
      'le nom d''une personne: l''organisation doit renseigner ce nom avant '
      'que la validation soit possible.'
      using errcode = 'check_violation';
  end if;

  if coalesce(btrim(p_statement), '') = '' then
    raise exception
      'l''attestation est vide. Le validateur doit ecrire ce qu''il atteste.'
      using errcode = 'check_violation';
  end if;

  if d.state <> 'review' then
    raise exception
      'le livrable est dans l''etat « % »: seule une piece EN RELECTURE peut '
      'etre validee.', d.state
      using errcode = 'restrict_violation';
  end if;

  perform project_calculation_is_publishable(d.calculation_id);

  select cl.strict_ndp, cl.inputs_hash, cl.execution_identity,
         cl.engine_build_sha, cl.ndp_snapshot, e.version as engine_version
    into c
    from calculations cl
    join engine_versions e on e.id = cl.engine_version_id
   where cl.id = d.calculation_id;

  if not c.strict_ndp then
    raise exception
      'ce calcul a ete mene en mode non strict: il a pu employer des '
      'parametres nationaux non confirmes. Un tel calcul reste exploratoire '
      'et ne peut pas etre atteste. Relancer en mode strict, apres '
      'confirmation des parametres requis.'
      using errcode = 'check_violation';
  end if;

  if d.execution_identity is distinct from c.execution_identity
     or d.engine_build_sha is distinct from c.engine_build_sha
     or d.inputs_hash is distinct from c.inputs_hash then
    raise exception
      'le contexte fige du livrable ne correspond plus a celui du calcul. '
      'L''attestation porterait sur deux choses differentes.'
      using errcode = 'check_violation';
  end if;

  insert into validations (
    org_id, project_id, calculation_id, validated_by, validator_name,
    validator_role, professional_id, statement, reservations,
    engine_version, ndp_set_version, inputs_hash,
    execution_identity, engine_build_sha, deliverable_sha256)
  values (
    d.org_id, p_project_id, d.calculation_id, acteur, nom,
    membre.role, membre.professional_id, btrim(p_statement),
    nullif(btrim(coalesce(p_reservations, '')), ''),
    c.engine_version,
    coalesce(nullif(btrim(coalesce(c.ndp_snapshot->>'version', '')), ''),
             'ndp_snapshot:sha256:' || encode(sha256(convert_to(
               coalesce(c.ndp_snapshot, '{}'::jsonb)::text, 'UTF8')), 'hex')),
    c.inputs_hash, c.execution_identity, c.engine_build_sha, d.sha256)
  returning id into validation;

  update deliverables
     set state = 'validated', validation_id = validation, last_reason = null
   where id = p_deliverable_id;

  get diagnostics touches = row_count;
  if touches <> 1 then
    raise exception
      'ATELIER_0023_VALIDATION_SANS_EFFET: l''attestation a ete ecrite sans '
      'que le livrable ne bascule. La transaction est annulee: une '
      'attestation orpheline ne porte sur rien.'
      using errcode = 'insufficient_privilege';
  end if;

  if not exists (select 1 from projects p
                  where p.id = p_project_id and p.retention_until is not null) then
    raise exception
      'ATELIER_0020_RETENTION_NON_OUVERTE: l''attestation a ete enregistree '
      'sans que la conservation decennale du projet ne s''ouvre. La '
      'transaction est annulee: une signature sans conservation ne vaut rien.'
      using errcode = 'check_violation';
  end if;

  return validation;
end;
$$;


-- 5.4 L'EMISSION — capacite `validation`
drop function if exists project_deliverable_finalize(uuid, uuid);

create or replace function project_deliverable_finalize(
  p_project_id uuid, p_deliverable_id uuid)
returns deliverable_state
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  d       record;
  touches integer;
begin
  select dl.* into d
    from deliverables dl
   where dl.id = p_deliverable_id and dl.project_id = p_project_id;
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- EMETTRE EST LE GESTE QUI MET LE DOCUMENT EN CIRCULATION, et il revient a
  -- celui qui en repond. 0020 ne controlait aucun role ici: n'importe quel
  -- membre pouvant ecrire publiait le document qu'un autre venait d'attester.
  perform project_exiger_capacite(d.org_id, 'validation');

  if d.state <> 'validated' then
    raise exception
      'le livrable est dans l''etat « % »: l''emission exige une attestation '
      'nominative prealable. Aucun document n''est emis sans qu''un ingenieur '
      'habilite ait repondu du calcul.', d.state
      using errcode = 'restrict_violation';
  end if;

  if d.validation_id is null then
    raise exception
      'aucune attestation n''est attachee a ce livrable.'
      using errcode = 'restrict_violation';
  end if;

  update deliverables set state = 'final' where id = p_deliverable_id;

  get diagnostics touches = row_count;
  if touches <> 1 then
    raise exception
      'ATELIER_0023_EMISSION_SANS_EFFET: l''emission n''a touche aucune '
      'ligne. Un refus ne doit pas se presenter comme un succes.'
      using errcode = 'insufficient_privilege';
  end if;

  return 'final'::deliverable_state;
end;
$$;


-- ---------------------------------------------------------------------
-- 6. PROPRIETE, ACCES, ET REPRISE DU DROIT DE CREER
-- ---------------------------------------------------------------------
-- LES QUATRE PRIMITIVES REMPLACEES REPARTENT DE `acldefault` apres leur
-- `drop`: le proprietaire redevient le migrateur et PUBLIC retrouve EXECUTE.
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_workspace_list()',
    'project_deliverable_create(uuid, uuid, deliverable_kind, text, text,'
      || ' text, text, text, bigint, text, uuid)',
    'project_deliverable_transition(uuid, uuid, deliverable_state, text)',
    'project_deliverable_validate(uuid, uuid, text, text)',
    'project_deliverable_finalize(uuid, uuid)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;
end
$$;

-- LES TROIS FONCTIONS INTERNES NE SONT PAS ACCORDEES AU BACKEND. Elles ne
-- correspondent a aucun geste du parcours: leur absence de la surface declaree
-- est elle-meme une mesure.
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_exiger_capacite(uuid, text)',
    'project_actor_peut_rediger(uuid)',
    'project_actor_peut_valider(uuid)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_normative_writer', f);
  end loop;
end
$$;

do $$
declare
  donneur text;
  appelant text := current_user;
  admissibles text[] := array[
    'pg_database_owner',
    current_user,
    pg_get_userbyid((select datdba from pg_database
                      where datname = current_database()))];
begin
  for donneur in
    select distinct pg_get_userbyid(a.grantor)
      from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public'
       and a.privilege_type = 'CREATE'
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid
  loop
    if not (donneur = any (admissibles)) then
      raise exception
        'ATELIER_0023_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
        'public n''est pas dans l''ensemble admissible {%}.',
        donneur, array_to_string(admissibles, ', ')
        using errcode = 'insufficient_privilege';
    end if;
    begin
      execute format('set local role %I', donneur);
      execute 'revoke create on schema public from eurostruct_normative_writer';
      execute format('set local role %I', appelant);
    exception when others then
      execute format('set local role %I', appelant);
      raise exception
        'ATELIER_0023_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%).', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;
end;
$$;

do $$
begin
  if exists (
    select 1 from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public' and a.privilege_type = 'CREATE'
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid)
  then
    raise exception
      'ATELIER_0023_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public a la fin de 0023.';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 7. POSTCONDITIONS
-- ---------------------------------------------------------------------
do $$
begin
  perform assert_authority_composition();
end;
$$;

-- `is_active` EST LU PAR LES QUATRE PREDICATS, ET LE CONTROLE PORTE SUR LE
-- CORPS. Une postcondition qui appellerait les fonctions avec un acteur
-- fabrique ne prouverait rien: sans session de backend, `project_backend_actor`
-- rend NULL et tous rendent `false` — un vert qui ne mesure rien.
do $$
declare
  nom text;
  corps text;
  fautives text := '';
begin
  foreach nom in array array['project_actor_is_member',
                             'project_actor_can_write',
                             'project_actor_peut_rediger',
                             'project_actor_peut_valider',
                             'project_workspace_list',
                             'project_exiger_capacite']
  loop
    -- ON PASSE PAR L'OID, PAS PAR UNE SIGNATURE RECONSTRUITE.
    --
    -- MESURE DU JOUR: `pg_get_function_identity_arguments()` rend les NOMS
    -- des arguments avec leurs types — « p_a uuid, p_b text » — et
    -- `to_regprocedure()` n'attend que les types. Il refuse alors sur
    -- « syntax error at or near "uuid" », a une etape ou plus rien ne
    -- rappelle qu'on lui a passe une chaine reconstruite. L'OID, lui, ne se
    -- reconstruit pas.
    select pg_get_functiondef(p.oid) into corps
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;
    if corps is null then
      raise exception
        'ATELIER_0023_FONCTION_ABSENTE: % n''existe pas apres 0023.', nom;
    end if;
    if position('is_active' in corps) = 0 then
      fautives := fautives || nom || ' ';
    end if;
  end loop;

  if fautives <> '' then
    raise exception
      'ATELIER_0023_IS_ACTIVE_IGNORE: % ne lit/lisent pas is_active. Un acces '
      'revoque garderait la lecture ET l''ecriture — le defaut exact que '
      'cette migration ferme.', fautives;
  end if;
end;
$$;

-- LES QUATRE PRIMITIVES EXIGENT UNE CAPACITE, ET CONSTATENT LEUR EFFET.
do $$
declare
  nom text;
  corps text;
  sans_capacite text := '';
  sans_constat text := '';
begin
  foreach nom in array array['project_deliverable_create',
                             'project_deliverable_transition',
                             'project_deliverable_validate',
                             'project_deliverable_finalize']
  loop
    -- PAR L'OID, POUR LA MEME RAISON QUE LE BLOC PRECEDENT.
    select pg_get_functiondef(p.oid) into corps
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;
    if corps is null then
      raise exception
        'ATELIER_0023_PRIMITIVE_ABSENTE: % n''existe pas apres 0023.', nom;
    end if;

    if position('project_exiger_capacite' in corps) = 0 then
      sans_capacite := sans_capacite || nom || ' ';
    end if;
    -- LA CREATION N'A RIEN A CONSTATER: son `insert ... returning` leve si la
    -- politique refuse. Les TROIS AUTRES font un `update`, qui peut ne
    -- toucher aucune ligne sans lever.
    if nom <> 'project_deliverable_create'
       and position('row_count' in corps) = 0 then
      sans_constat := sans_constat || nom || ' ';
    end if;
  end loop;

  if sans_capacite <> '' then
    raise exception
      'ATELIER_0023_CAPACITE_NON_EXIGEE: % n''exige/exigent aucune capacite. '
      'L''appartenance seule laisserait un viewer rediger et un engineer '
      'emettre.', sans_capacite;
  end if;
  if sans_constat <> '' then
    raise exception
      'ATELIER_0023_EFFET_NON_CONSTATE: % ne constate/constatent pas '
      'row_count. Une politique RLS filtre la ligne, l''update ne touche rien '
      'sans lever, et le refus se presente comme un succes.', sans_constat;
  end if;
end;
$$;

-- LES POLITIQUES DU LIVRABLE SUIVENT LA MATRICE, ET PAS `can_write`.
do $$
declare
  insertion text;
  ecriture text;
  attestation text;
begin
  select pg_get_expr(polwithcheck, polrelid) into insertion
    from pg_policy where polname = 'deliverables_atelier_insert';
  select pg_get_expr(polqual, polrelid) into ecriture
    from pg_policy where polname = 'deliverables_atelier_update';
  select pg_get_expr(polwithcheck, polrelid) into attestation
    from pg_policy where polname = 'validations_atelier_insert';

  if insertion is null or position('peut_rediger' in insertion) = 0
     or position('can_write' in insertion) > 0 then
    raise exception
      'ATELIER_0023_INSERTION_HORS_MATRICE: la politique d''insertion des '
      'livrables vaut « % ». Elle doit viser les redacteurs, pas l''ensemble '
      'plus large de can_write.', coalesce(insertion, '(absente)');
  end if;
  if ecriture is null or position('peut_valider' in ecriture) = 0 then
    raise exception
      'ATELIER_0023_ECRITURE_HORS_MATRICE: la politique de modification des '
      'livrables vaut « % »: le validateur ne pourrait ni renvoyer au '
      'brouillon, ni attester, ni emettre.', coalesce(ecriture, '(absente)');
  end if;
  if attestation is null or position('peut_valider' in attestation) = 0 then
    raise exception
      'ATELIER_0023_ATTESTATION_HORS_MATRICE: la politique d''insertion des '
      'attestations vaut « % ».', coalesce(attestation, '(absente)');
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
