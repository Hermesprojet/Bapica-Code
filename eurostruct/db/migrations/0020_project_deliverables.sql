-- 0020 — LES LIVRABLES DEVIENNENT ATTEIGNABLES
--
-- CE QUI EXISTAIT DEJA, ET QUI N'A JAMAIS SERVI
-- ----------------------------------------------
-- 0001 pose `validations` et `deliverables`. 0003 rend une signature immuable
-- et derive le role du signataire de son adhesion. 0005 construit la machine a
-- etats complete — draft, review, validated, final — avec ses transitions
-- interdites, sa chaine de revisions et son journal. 0009 exige que le
-- signataire soit membre ACTIF et porteur du role de validation.
--
-- Tout cela est ecrit, teste, et INATTEIGNABLE. `eurostruct_authority_backend`
-- n'a aucun privilege de table: il n'atteint que les fonctions qu'on lui
-- declare, et aucune ne touchait ces deux tables. Le workflow existait comme
-- un escalier dans un mur sans porte.
--
-- CE QUE CETTE MIGRATION AJOUTE
-- ------------------------------
--   * les colonnes qui ATTACHENT un livrable a des octets et a un calcul gele
--     — media_type, storage_backend, sha256 deja la, execution_identity,
--     engine_build_sha, inputs_hash, ndp_as_of, watermark;
--   * `deliverable_state_transitions.reason` et un acteur qui n'est plus NULL;
--   * `organization_members.display_name`, parce qu'une signature porte le nom
--     d'une personne et que ce nom doit sortir de l'adhesion, jamais du corps
--     de la requete;
--   * sept primitives SECURITY DEFINER, une par geste du parcours.
--
-- CE QU'ELLE NE PRETEND PAS
-- --------------------------
-- Elle n'invente AUCUNE signature electronique qualifiee. Ce qu'elle
-- enregistre est une ATTESTATION METIER AUTHENTIFIEE: un membre actif, nomme,
-- porteur du role de validation, atteste avoir relu ce calcul-la. C'est ce que
-- le produit fait; c'est donc ce qu'il dit, ici comme a l'ecran.
--
-- Elle ne rend rien signable non plus. Le registre national est a 0/29: aucun
-- parametre n'est confirme, donc aucun calcul strict n'aboutit, donc aucun
-- livrable n'atteint `validated` par le chemin produit tant que ce registre
-- n'a pas ete alimente. La machine est branchee; le combustible manque, et le
-- refus qui le dit est explicite.

begin;

-- Le droit de creer, le temps de cette migration. Meme raison qu'en 0018:
-- `alter function ... owner to` exige CREATE sur le schema. La section 6 le
-- reprend, sous le donneur endosse.
grant create on schema public to eurostruct_normative_writer;

-- LA NOTE HTML N'AVAIT PAS DE GENRE. `deliverable_kind` de 0001 enumere huit
-- natures de document, toutes attendues plus tard — PDF, DXF, IFC, tableur —
-- et aucune ne designe ce que le produit sait reellement produire aujourd'hui:
-- une note de calcul HTML autonome. Ranger celle-ci sous
-- `calculation_note_pdf` ferait mentir la colonne sur le format des octets.
--
-- POSTGRESQL 12+ ACCEPTE CET ORDRE DANS UNE TRANSACTION, a la seule condition
-- que la valeur ne soit pas UTILISEE avant le commit. Cette migration ne
-- l'utilise nulle part: les corps de fonction ne sont que du texte tant que
-- personne ne les appelle.
alter type deliverable_kind add value if not exists 'calculation_note_html';


-- ---------------------------------------------------------------------
-- 1. UN LIVRABLE EST UN FICHIER, PAS UNE LIGNE QUI EN PARLE
-- ---------------------------------------------------------------------
-- `deliverables` portait `storage_path`, `sha256` et `size_bytes` depuis 0001,
-- et rien ne les reliait a des octets reels. Une ligne pouvait nommer un
-- chemin vide, un chemin d'un autre fichier, ou un chemin qui n'a jamais
-- existe — la table etait aussi convaincante dans les trois cas.
--
-- LA CONTRAINTE CI-DESSOUS EST LA SEULE QUE LA BASE PUISSE TENIR SEULE.
-- PostgreSQL ne lit pas l'objet stocke: il ne peut pas verifier que les octets
-- existent, ni qu'ils ont ce hash. Ce qu'il PEUT garantir, c'est que le chemin
-- enregistre DERIVE du hash — donc qu'aucune ligne ne designe un emplacement
-- sans rapport avec le contenu qu'elle annonce. La verification des octets
-- eux-memes appartient a l'appelant, qui les relit avant d'appeler.
alter table deliverables
  add column if not exists media_type         text,
  add column if not exists storage_backend    text,
  -- LE CONTEXTE GELE, COPIE DU CALCUL. Il n'est pas redonde par plaisir: un
  -- livrable conserve dix ans doit rester lisible meme si le calcul source a
  -- ete purge, et surtout il doit pouvoir etre CONFRONTE au calcul. Deux
  -- copies qui divergent revelent une falsification; une seule ne revele rien.
  add column if not exists execution_identity text,
  add column if not exists engine_build_sha   text,
  add column if not exists inputs_hash        text,
  add column if not exists ndp_as_of          date,
  -- Le filigrane REELLEMENT appose sur les octets. Il n'est pas decoratif:
  -- c'est ce qui distingue un brouillon d'un document opposable, et il doit
  -- etre relisible sans rouvrir le fichier.
  add column if not exists watermark          text,
  -- LE MOTIF PORTE PAR LA DERNIERE TRANSITION. Le declencheur de journal ne
  -- recoit pas de parametre; cette colonne est le seul moyen de lui faire
  -- passer le motif d'un retour au brouillon, et elle sert aussi a l'ecran,
  -- qui doit montrer POURQUOI un livrable est revenu en arriere.
  add column if not exists last_reason        text;

comment on column deliverables.storage_backend is
  'Quel magasin detient les octets. Une ligne qui ne le dit pas ne permet pas '
  'de les retrouver: la primitive refuse de l''ecrire.';

comment on column deliverables.execution_identity is
  'Copie figee de calculations.execution_identity. Confrontable au calcul: '
  'deux copies qui divergent revelent une falsification.';

-- LE CHEMIN DOIT DERIVER DU HASH.
--
-- `not valid` parce que les lignes anterieures — s'il en existe — n'ont pas
-- ete ecrites sous cette regle, et qu'une migration qui echoue sur des donnees
-- historiques bloque un deploiement sans rien proteger. La contrainte
-- s'applique a TOUTE ECRITURE NOUVELLE, ce qui est exactement son objet.
alter table deliverables
  add constraint storage_path_derives_from_sha check (
    position(sha256 in storage_path) > 0
  ) not valid;

-- LE MOTIF D'UNE TRANSITION.
--
-- « Retour au brouillon » sans motif est une decision qu'on ne peut pas
-- relire. Le motif est exige par la primitive, pas par une contrainte de
-- colonne: une transition automatique (creation) n'en a pas, et une contrainte
-- `not null` obligerait a inventer un motif la ou il n'y en a pas.
alter table deliverable_state_transitions
  add column if not exists reason text;

-- LE NOM DE LA PERSONNE, ENREGISTRE PAR L'ORGANISATION.
--
-- `validations.validator_name` est `not null` depuis 0001 et 0009 refuse une
-- chaine vide — a juste titre: une signature porte le nom de quelqu'un qui a
-- lu l'etude. Restait a savoir D'OU vient ce nom. Du corps HTTP, il ne vaut
-- rien: l'appelant signerait sous le nom qu'il choisit. Il vient donc de
-- l'adhesion, que l'organisation controle.
alter table organization_members
  add column if not exists display_name text;

comment on column organization_members.display_name is
  'Le nom de la personne, tel que l''organisation l''enregistre. La primitive '
  'de validation le DERIVE d''ici et n''accepte aucun nom fourni par '
  'l''appelant.';

-- CE QU'UNE VALIDATION FIGE EN PLUS.
--
-- 0001 figeait `engine_version`, `ndp_set_version` et `inputs_hash`. Aucun des
-- trois ne designe le code exact: six commits successifs portent la meme
-- version. Une attestation qui ne peut pas nommer le build qu'elle a relu ne
-- permet pas, dix ans plus tard, de rejouer ce qui a ete atteste.
alter table validations
  add column if not exists execution_identity  text,
  add column if not exists engine_build_sha    text,
  -- L'empreinte des OCTETS relus. L'ingenieur n'atteste pas une ligne de
  -- table: il atteste un document. Si les octets changent, l'attestation ne
  -- porte plus sur eux, et cette colonne le rend demontrable.
  add column if not exists deliverable_sha256  text;


-- ---------------------------------------------------------------------
-- 2. LE JOURNAL SAIT QUI, ET POURQUOI
-- ---------------------------------------------------------------------
-- LE DEFAUT REEL: `log_deliverable_transition()` de 0005 ecrit
-- `actor_id = auth.uid()`. C'est le GUC que Supabase pose pour un acces direct
-- depuis le navigateur. Notre backend n'emprunte pas ce chemin — il verifie le
-- JWT lui-meme puis pose `eurostruct.actor_id`. Resultat: TOUTES les
-- transitions du chemin produit seraient journalisees avec `actor_id = NULL`.
-- Un historique de validation qui ne nomme personne est un historique qui ne
-- sert a rien.
--
-- `coalesce` DANS CET ORDRE, et il compte: `auth.uid()` d'abord, pour ne rien
-- changer au chemin Supabase direct; l'acteur de l'atelier ensuite, pour le
-- chemin qui existe reellement aujourd'hui.
create or replace function log_deliverable_transition() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if tg_op = 'INSERT' or new.state is distinct from old.state then
    insert into deliverable_state_transitions
      (org_id, deliverable_id, from_state, to_state, actor_id, reason)
    values (
      new.org_id, new.id,
      case when tg_op = 'INSERT' then null else old.state end,
      new.state,
      coalesce(auth.uid(), project_backend_actor()),
      new.last_reason
    );
  end if;
  return new;
end;
$$;

-- ET IL DOIT APPARTENIR AU PROPRIETAIRE DE L'ATELIER, SANS QUOI IL NE PEUT
-- PAS APPELER CE QU'IL VIENT D'APPRENDRE A APPELER.
--
-- MESURE DU JOUR, ET ELLE EST INSTRUCTIVE: « permission denied for function
-- project_backend_actor », leve depuis le corps du declencheur, au moment
-- d'inserer le PREMIER livrable. Une fonction SECURITY DEFINER s'execute sous
-- SON proprietaire — ici le role qui a joue 0005, c'est-a-dire le migrateur —
-- et 0018 n'a accorde `project_backend_actor()` qu'au proprietaire des
-- primitives. Le declencheur avait donc le droit d'ecrire et pas celui de
-- savoir qui ecrivait.
--
-- L'ALTERNATIVE — accorder `project_backend_actor()` au migrateur — elargirait
-- la surface d'un role qui n'en a aucun besoin en exploitation, pour resoudre
-- un probleme de propriete. On change le proprietaire.
alter function log_deliverable_transition() owner to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 3. LES PRIVILEGES DE TABLE, ET LES POLITIQUES QUI LES BORNENT
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0018. `force row level security` est actif sur
-- `deliverables` et `validations` depuis 0002: le proprietaire des primitives
-- y est soumis comme les autres, et la frontiere reste la politique.
grant select, insert, update on deliverables to eurostruct_normative_writer;
grant select, insert on validations to eurostruct_normative_writer;
grant select, insert on deliverable_state_transitions
  to eurostruct_normative_writer;
-- `bigserial` VEUT DIRE UNE SEQUENCE, ET UNE SEQUENCE A SES PROPRES DROITS.
-- Sans USAGE, l'INSERT echoue sur « permission denied for sequence », a une
-- etape ou plus rien ne rappelle qu'une cle primaire est un objet distinct.
grant usage on sequence deliverable_state_transitions_id_seq
  to eurostruct_normative_writer;

-- LES POLITIQUES SONT NOMMEMENT ADRESSEES AU WRITER. Sans clause `to`, elles
-- viseraient PUBLIC, et toute session evaluant ces tables devrait executer
-- `project_actor_is_member()` sans en avoir le droit — le defaut exact que
-- 0018 documente en miroir.
create policy deliverables_atelier_read on deliverables
  for select to eurostruct_normative_writer
  using (project_actor_is_member(org_id));
create policy deliverables_atelier_insert on deliverables
  for insert to eurostruct_normative_writer
  with check (project_actor_can_write(org_id));
-- UPDATE EXIGE LES DEUX CLAUSES. `using` decide quelles lignes sont
-- MODIFIABLES, `with check` a quoi elles ont le droit de ressembler apres. Une
-- politique sans `with check` laisserait deplacer une ligne vers une autre
-- organisation en une seule instruction.
create policy deliverables_atelier_update on deliverables
  for update to eurostruct_normative_writer
  using (project_actor_can_write(org_id))
  with check (project_actor_can_write(org_id));

create policy validations_atelier_read on validations
  for select to eurostruct_normative_writer
  using (project_actor_is_member(org_id));
create policy validations_atelier_insert on validations
  for insert to eurostruct_normative_writer
  with check (project_actor_can_write(org_id));

create policy transitions_atelier_read on deliverable_state_transitions
  for select to eurostruct_normative_writer
  using (project_actor_is_member(org_id));
create policy transitions_atelier_insert on deliverable_state_transitions
  for insert to eurostruct_normative_writer
  with check (project_actor_is_member(org_id));

-- LA CONSERVATION DECENNALE DOIT POUVOIR S'OUVRIR PAR LE CHEMIN PRODUIT.
--
-- `open_retention_period()` de 0003 est SECURITY DEFINER et s'execute donc
-- sous SON proprietaire — le role qui a joue 0003. Sur une installation ou ce
-- role n'est pas superutilisateur, `force row level security` s'applique a lui
-- aussi: l'UPDATE ne leve pas, il touche ZERO LIGNE. La conservation
-- n'ouvrirait jamais, et rien ne le dirait.
--
-- On donne donc au declencheur le proprietaire de l'atelier, et a l'atelier la
-- politique qui va avec. La primitive de validation constate ensuite que la
-- date est bien posee: la politique rend le geste possible, la postcondition
-- prouve qu'il a eu lieu.
alter function open_retention_period() owner to eurostruct_normative_writer;

grant update (retention_until) on projects to eurostruct_normative_writer;

create policy projects_atelier_retention on projects
  for update to eurostruct_normative_writer
  using (project_actor_can_write(org_id))
  with check (project_actor_can_write(org_id));


-- ---------------------------------------------------------------------
-- 4. CE QU'UN LIVRABLE PEUT ETRE TIRE D'UN CALCUL
-- ---------------------------------------------------------------------
-- Fonction interne, jamais accordee au backend: elle ne fait que reunir en un
-- endroit les deux questions que TOUTES les primitives doivent poser, pour
-- qu'aucune ne puisse les poser differemment.
--
-- ELLE LEVE PLUTOT QU'ELLE NE REND `false`. Un appelant qui recoit `false` doit
-- decider quoi en dire; six appelants prendront six decisions, dont une
-- laissera passer. Le message est ici, une fois.
create or replace function project_calculation_is_publishable(
  p_calculation_id uuid)
returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  c record;
begin
  select cl.status, cl.strict_ndp, cl.execution_identity, cl.engine_build_sha,
         exists (select 1 from results r where r.calculation_id = cl.id) as a_resultat
    into c
    from calculations cl where cl.id = p_calculation_id;

  if not found then
    raise exception 'calcul % introuvable', p_calculation_id
      using errcode = 'foreign_key_violation';
  end if;

  -- UN CALCUL REFUSE NE PRODUIT PAS DE DOCUMENT TROMPEUR. Le refus est une
  -- reponse du moteur et l'historique le porte; un livrable, lui, se lit comme
  -- une conclusion, et il n'y en a pas.
  if c.status <> 'succeeded' then
    raise exception
      'le calcul est dans l''etat « % »: il ne conclut pas, et un livrable se '
      'lirait comme une conclusion. Consulter le motif de refus dans '
      'l''historique.', c.status
      using errcode = 'check_violation';
  end if;

  if not c.a_resultat then
    raise exception
      'le calcul est marque « succeeded » sans resultat enregistre. Aucun '
      'document ne peut en etre tire.'
      using errcode = 'check_violation';
  end if;

  -- SANS IDENTITE D'EXECUTION, LE DOCUMENT NE PEUT PAS DIRE QUEL CODE L'A
  -- PRODUIT. 0019 refuse deja d'enregistrer un tel calcul; la garde est
  -- redoublee ici parce qu'une ligne anterieure a 0019 en est depourvue.
  if coalesce(btrim(c.execution_identity), '') = ''
     or coalesce(btrim(c.engine_build_sha), '') = '' then
    raise exception
      'le calcul ne porte pas d''identite d''execution verifiable: aucun '
      'livrable ne peut en etre tire.'
      using errcode = 'check_violation';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 5. LES SEPT GESTES DU PARCOURS
-- ---------------------------------------------------------------------

-- 5.1 CREER UN BROUILLON DEPUIS UN CALCUL GELE
--
-- AUCUN CONTEXTE N'EST ACCEPTE DE L'APPELANT. L'organisation sort du projet,
-- le projet est confronte aux appartenances, et le contexte normatif, la
-- version du moteur, le build et l'identite d'execution sont COPIES du calcul.
-- L'appelant ne fournit que ce qu'il est seul a savoir: la nature du document,
-- son nom, ses octets et leur empreinte.
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
  select p.org_id into org
    from projects p
    join organization_members m on m.org_id = p.org_id
   where p.id = p_project_id and m.user_id = acteur;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- LE CALCUL DOIT ETRE CELUI DU PROJET. Sans ce controle, un identifiant de
  -- calcul d'un autre projet — voire d'une autre organisation — produirait un
  -- livrable range sous ce projet-ci. RLS ne l'attraperait pas: la ligne
  -- inseree porte le bon `org_id`.
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

  -- LES OCTETS DOIVENT ETRE DECRITS ENTIEREMENT. Un `storage_path` sans
  -- magasin ne permet de retrouver aucun fichier; une taille nulle ou un hash
  -- absent rendent la ligne invérifiable. On refuse plutot que d'ecrire une
  -- ligne qui promet un document qu'on ne saura pas relire.
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

  -- L'EMPREINTE A UNE FORME. Une chaine quelconque passerait la contrainte de
  -- derivation du chemin — il suffirait de la coller dans le chemin — sans
  -- rien designer.
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


-- 5.2 LISTER LES LIVRABLES D'UN PROJET
create or replace function project_deliverable_list(p_project_id uuid)
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
           d.watermark, d.last_reason, d.engine_version, d.engine_build_sha,
           d.execution_identity, d.validation_id, v.validator_name, v.signed_at,
           d.generated_at
      from deliverables d
      left join validations v on v.id = d.validation_id
     where d.project_id = p_project_id
     order by d.generated_at desc, d.id;
end;
$$;


-- 5.3 RELIRE UN LIVRABLE, SON CONTEXTE ET SON HISTOIRE
--
-- L'HISTORIQUE EST RENDU PAR LA MEME PRIMITIVE, et ce n'est pas une commodite.
-- Deux appels separes pourraient tomber de part et d'autre d'une transition et
-- montrer un etat qui ne correspond pas a son journal.
create or replace function project_deliverable_read(
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
           d.state, d.revision, d.supersedes_id, d.watermark, d.last_reason,
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


-- 5.4 SOUMETTRE A LA RELECTURE, ET REVENIR AU BROUILLON
--
-- UNE SEULE PRIMITIVE POUR LES DEUX SENS. Elles partagent l'integralite de
-- leurs controles et ne different que par l'etat vise; deux fonctions
-- laisseraient l'une diverger de l'autre a la premiere correction.
--
-- LA MACHINE A ETATS N'EST PAS REECRITE ICI. Le declencheur de 0005 refuse
-- toute transition hors du chemin; cette primitive se contente de la demander,
-- et une transition interdite remonte SON message, pas un doublon local qui
-- pourrait diverger.
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
  acteur uuid := normative_authenticated_actor();
  d      record;
begin
  select dl.* into d
    from deliverables dl
    join projects p on p.id = dl.project_id
    join organization_members m on m.org_id = p.org_id
   where dl.id = p_deliverable_id and dl.project_id = p_project_id
     and m.user_id = acteur;
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- CETTE PRIMITIVE NE VALIDE NI N'EMET. `validated` exige une attestation
  -- nominative et `final` exige qu'elle existe deja: les deux ont leur propre
  -- porte, avec leurs propres controles d'habilitation. Les laisser passer ici
  -- ferait de cette fonction un contournement de ces portes.
  if p_to_state not in ('draft', 'review') then
    raise exception
      'cette primitive ne conduit qu''a « draft » ou « review ». La validation '
      'et l''emission ont leur propre porte, avec leurs propres controles.'
      using errcode = 'insufficient_privilege';
  end if;

  -- UNE TRANSITION QUI NE DEPLACE RIEN N'EST PAS UNE TRANSITION.
  --
  -- MESURE DU JOUR: un « retour au brouillon » demande sur un livrable DEJA au
  -- brouillon etait accepte. Le declencheur de 0005 ne controle que les
  -- changements d'etat (`new.state <> old.state`) — a juste titre, ce n'est pas
  -- son objet — si bien qu'aucune ligne de journal n'etait ecrite, mais que
  -- `last_reason` etait ecrase. L'ecran affichait donc un motif de refus sur
  -- une piece que personne n'avait refusee, et l'historique ne disait pas d'ou
  -- il venait.
  if p_to_state = d.state then
    raise exception
      'le livrable est deja dans l''etat « % »: il n''y a rien a faire, et '
      'l''enregistrer comme une transition ecrirait un motif que l''historique '
      'ne porterait pas.', d.state
      using errcode = 'restrict_violation';
  end if;

  -- UN RETOUR EN ARRIERE SANS MOTIF EST UNE DECISION QU'ON NE PEUT PAS RELIRE.
  -- Celui qui reprend le brouillon doit savoir ce qui a ete reproche.
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

  return p_to_state;
end;
$$;


-- 5.5 L'ATTESTATION METIER, ET LE PASSAGE A `validated`
--
-- CE QUE CETTE PRIMITIVE N'EST PAS: une signature electronique qualifiee. Elle
-- enregistre qu'un membre ACTIF, NOMME, porteur du role de validation, atteste
-- avoir relu CE calcul-la, avec ses entrees, son instantane normatif, son
-- identite d'execution, son build et l'empreinte des octets. C'est une
-- attestation metier authentifiee, et c'est le nom qu'elle porte a l'ecran.
--
-- L'APPELANT NE FOURNIT QUE SON TEXTE. Nom, role et numero d'inscription sont
-- DERIVES de l'adhesion — le declencheur de 0009 les ecrase de toute facon, et
-- les lui passer depuis le corps HTTP donnerait l'illusion qu'ils comptent.
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
begin
  select dl.* into d
    from deliverables dl
   where dl.id = p_deliverable_id and dl.project_id = p_project_id
     and exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = dl.project_id and m.user_id = acteur);
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  -- L'HABILITATION EST LUE ICI POUR RENDRE UN MESSAGE UTILISABLE. Le
  -- declencheur de 0009 refuserait de toute facon, et c'est lui la frontiere;
  -- mais « le role viewer ne porte pas la validation technique » se lit, alors
  -- qu'une violation de contrainte ne se lit pas.
  select m.* into membre
    from organization_members m
   where m.org_id = d.org_id and m.user_id = acteur;
  if not found then
    raise exception 'vous n''etes pas membre de l''organisation de ce projet.'
      using errcode = 'insufficient_privilege';
  end if;
  if not membre.is_active then
    raise exception
      'votre acces a cette organisation a ete revoque le %: il ne peut plus '
      'engager le bureau d''etudes.', membre.deactivated_at::date
      using errcode = 'check_violation';
  end if;
  if membre.role <> 'validating_engineer' then
    raise exception
      'le role « % » ne porte pas la validation technique. L''organisation '
      'attribue le role « validating_engineer » a l''ingenieur qui repond de '
      'ses etudes.', membre.role
      using errcode = 'insufficient_privilege';
  end if;

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

  -- UN CALCUL EXPLORATOIRE NE SE VALIDE PAS.
  --
  -- « Exploratoire » a un sens precis et verifiable ici: `strict_ndp = false`,
  -- c'est-a-dire un calcul que le moteur a mene EN UTILISANT des parametres
  -- nationaux non confirmes. En mode strict, le moteur refuse plutot que
  -- d'employer une valeur non tracee — un calcul strict abouti n'a donc employe
  -- que des valeurs confirmees. Attester le contraire ferait porter une
  -- signature humaine sur des nombres qu'aucune Annexe Nationale ne soutient.
  if not c.strict_ndp then
    raise exception
      'ce calcul a ete mene en mode non strict: il a pu employer des '
      'parametres nationaux non confirmes. Un tel calcul reste exploratoire '
      'et ne peut pas etre atteste. Relancer en mode strict, apres '
      'confirmation des parametres requis.'
      using errcode = 'check_violation';
  end if;

  -- LE LIVRABLE DOIT DECRIRE LE MEME CALCUL QUE CELUI QU'ON ATTESTE. Les
  -- colonnes du livrable sont des copies figees; si elles ont diverge du
  -- calcul, l'une des deux ment et on ne sait pas laquelle.
  if d.execution_identity is distinct from c.execution_identity
     or d.engine_build_sha is distinct from c.engine_build_sha
     or d.inputs_hash is distinct from c.inputs_hash then
    raise exception
      'le contexte fige du livrable ne correspond plus a celui du calcul. '
      'L''attestation porterait sur deux choses differentes.'
      using errcode = 'check_violation';
  end if;

  -- L'INSERTION DERIVE TOUT. `validator_role` et `professional_id` seront de
  -- toute facon ecrases par le declencheur de 0009; ils sont poses ici a leur
  -- valeur derivee pour que la ligne soit correcte meme lue hors declencheur.
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
    -- `ndp_set_version` EST `not null` DEPUIS 0001 ET DOIT DESIGNER QUELQUE
    -- CHOSE. Le registre versionne de 0004 ne pose pas de numero unique sur un
    -- instantane; a defaut, l'empreinte de l'instantane lui-meme le designe
    -- exactement, et deux instantanes differents ne peuvent pas la partager.
    -- `sha256()` est natif depuis PostgreSQL 11: aucune extension requise.
    coalesce(nullif(btrim(coalesce(c.ndp_snapshot->>'version', '')), ''),
             'ndp_snapshot:sha256:' || encode(sha256(convert_to(
               coalesce(c.ndp_snapshot, '{}'::jsonb)::text, 'UTF8')), 'hex')),
    c.inputs_hash, c.execution_identity, c.engine_build_sha, d.sha256)
  returning id into validation;

  update deliverables
     set state = 'validated', validation_id = validation, last_reason = null
   where id = p_deliverable_id;

  -- LA CONSERVATION DECENNALE DOIT AVOIR REELLEMENT OUVERT.
  --
  -- `validations_open_retention` de 0003 pose `projects.retention_until` par
  -- declencheur. Un UPDATE filtre par RLS ne leve PAS: il touche zero ligne,
  -- en silence. Le produit croirait la conservation ouverte alors qu'une purge
  -- resterait permise — exactement le genre de defaut qu'on ne decouvre qu'au
  -- moment ou la donnee manque. On le constate plutot que de le supposer.
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


-- 5.6 L'EMISSION
--
-- SEPAREE DE LA VALIDATION, ET DELIBEREMENT. Valider, c'est repondre du
-- calcul; emettre, c'est mettre le document en circulation. Les fondre ferait
-- de toute relecture une publication.
create or replace function project_deliverable_finalize(
  p_project_id uuid, p_deliverable_id uuid)
returns deliverable_state
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
  d      record;
begin
  select dl.* into d
    from deliverables dl
   where dl.id = p_deliverable_id and dl.project_id = p_project_id
     and exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = dl.project_id and m.user_id = acteur);
  if not found then
    raise exception 'livrable introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  if d.state <> 'validated' then
    raise exception
      'le livrable est dans l''etat « % »: l''emission exige une attestation '
      'nominative prealable. Aucun document n''est emis sans qu''un ingenieur '
      'habilite ait repondu du calcul.', d.state
      using errcode = 'restrict_violation';
  end if;

  -- LA CONTRAINTE DE 0001 ET LE DECLENCHEUR DE 0005 LE VERIFIENT AUSSI. Ce
  -- controle-ci ne les remplace pas: il rend le refus lisible avant qu'une
  -- violation de contrainte ne le rende obscur.
  if d.validation_id is null then
    raise exception
      'aucune attestation n''est attachee a ce livrable.'
      using errcode = 'restrict_violation';
  end if;

  update deliverables set state = 'final' where id = p_deliverable_id;
  return 'final'::deliverable_state;
end;
$$;


-- 5.7 LES OCTETS D'UN LIVRABLE, POUR LE TELECHARGEMENT
--
-- SEPAREE DE `read` PARCE QUE LES DEUX QUESTIONS SONT DIFFERENTES. Relire un
-- livrable est une consultation; en telecharger les octets suppose qu'on sache
-- OU ils sont, et cette reponse-la n'a aucune raison de traverser l'API vers
-- l'ecran. La primitive rend le chemin au backend, jamais au navigateur.
create or replace function project_deliverable_bytes(
  p_project_id uuid, p_deliverable_id uuid)
returns table (
  storage_backend text,
  storage_path    text,
  sha256          text,
  size_bytes      bigint,
  filename        text,
  media_type      text,
  state           deliverable_state,
  watermark       text)
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
    select d.storage_backend, d.storage_path, d.sha256, d.size_bytes,
           d.filename, d.media_type, d.state, d.watermark
      from deliverables d
     where d.id = p_deliverable_id and d.project_id = p_project_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 6. PROPRIETE, ACCES, ET REPRISE DU DROIT DE CREER
-- ---------------------------------------------------------------------
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_deliverable_create(uuid, uuid, deliverable_kind, text, text,'
      || ' text, text, text, bigint, text, uuid)',
    'project_deliverable_list(uuid)',
    'project_deliverable_read(uuid, uuid)',
    'project_deliverable_transition(uuid, uuid, deliverable_state, text)',
    'project_deliverable_validate(uuid, uuid, text, text)',
    'project_deliverable_finalize(uuid, uuid)',
    'project_deliverable_bytes(uuid, uuid)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;
end
$$;

-- LA FONCTION INTERNE N'EST PAS ACCORDEE AU BACKEND, et c'est voulu: elle ne
-- correspond a aucun geste du parcours. Son absence de la surface declaree est
-- elle-meme une mesure.
alter function project_calculation_is_publishable(uuid)
  owner to eurostruct_normative_writer;
revoke all on function project_calculation_is_publishable(uuid) from public;
grant execute on function project_calculation_is_publishable(uuid)
  to eurostruct_normative_writer;

-- Meme forme qu'en 0011 a 0019: on endosse le DONNEUR de l'octroi, et
-- seulement s'il appartient a un ensemble admissible explicite. Un `revoke` nu
-- emis par un role qui n'est pas le donneur n'a AUCUN effet — ni erreur, ni
-- avertissement, et le privilege reste.
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
        'ATELIER_0020_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'ATELIER_0020_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
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
      'ATELIER_0020_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public a la fin de 0020.';
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

-- LES SEPT PRIMITIVES EXISTENT, EN UN SEUL EXEMPLAIRE CHACUNE, SOUS LE BON
-- PROPRIETAIRE, AVEC UN `search_path` EPINGLE, ET PUBLIC N'Y ACCEDE PAS.
--
-- POURQUOI COMPTER LES SIGNATURES: `create or replace` a une signature voisine
-- laisse deux homonymes, PostgreSQL choisit par resolution de types, et un
-- appelant qui croit poser un motif atteint celle qui l'ignore.
do $$
declare
  attendues text[] := array[
    'project_deliverable_create', 'project_deliverable_list',
    'project_deliverable_read', 'project_deliverable_transition',
    'project_deliverable_validate', 'project_deliverable_finalize',
    'project_deliverable_bytes'];
  nom text;
  n int;
  fautives text;
begin
  foreach nom in array attendues loop
    select count(*) into n from pg_proc p
      join pg_namespace ns on ns.oid = p.pronamespace
     where ns.nspname = 'public' and p.proname = nom;
    if n <> 1 then
      raise exception
        'ATELIER_0020_SIGNATURES_MULTIPLES: % existe en % exemplaire(s). Deux '
        'homonymes laisseraient PostgreSQL choisir, et un appelant '
        'atteindrait la mauvaise.', nom, n;
    end if;
  end loop;

  select string_agg(p.proname || ' (' ||
           case when not p.prosecdef then 'pas SECURITY DEFINER'
                when p.proconfig is null
                  or not ('search_path=public, pg_temp' = any(p.proconfig))
                  then 'search_path non epingle'
                when pg_get_userbyid(p.proowner) <> 'eurostruct_normative_writer'
                  then 'proprietaire ' || pg_get_userbyid(p.proowner)
                else 'PUBLIC peut executer' end || ')', ', ')
    into fautives
    from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public'
     and p.proname = any(attendues)
     and (not p.prosecdef
          or p.proconfig is null
          or not ('search_path=public, pg_temp' = any(p.proconfig))
          or pg_get_userbyid(p.proowner) <> 'eurostruct_normative_writer'
          or has_function_privilege('public', p.oid, 'EXECUTE'));

  if fautives is not null then
    raise exception
      'ATELIER_0020_PRIMITIVES_NON_CONFORMES: %. Une primitive sans '
      'search_path epingle est detournable par un schema temporaire; une '
      'primitive ouverte a PUBLIC n''est pas une frontiere.', fautives;
  end if;
end;
$$;

-- LE JOURNAL DES TRANSITIONS NOMME DESORMAIS SON ACTEUR SUR LE CHEMIN PRODUIT.
--
-- Le controle porte sur le CODE de la fonction, pas sur une transition d'essai:
-- cette migration n'ecrit aucun livrable, et en creer un pour verifier le
-- journal laisserait une ligne fictive dans une base de production.
do $$
declare
  proprietaire text;
begin
  if position('project_backend_actor' in
              pg_get_functiondef('log_deliverable_transition'::regproc)) = 0
  then
    raise exception
      'ATELIER_0020_JOURNAL_SANS_ACTEUR: log_deliverable_transition() ne '
      'retombe pas sur l''acteur de l''atelier. Toutes les transitions du '
      'chemin produit seraient journalisees sans personne.';
  end if;

  -- ET IL DOIT AVOIR LE DROIT D'APPELER CE QU'IL APPELLE. Le controle porte
  -- sur le PROPRIETAIRE plutot que sur un privilege: une fonction SECURITY
  -- DEFINER s'execute sous le sien, et c'est de la que vient le droit.
  select pg_get_userbyid(p.proowner) into proprietaire
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'log_deliverable_transition';
  if proprietaire is distinct from 'eurostruct_normative_writer' then
    raise exception
      'ATELIER_0020_JOURNAL_MAL_POSSEDE: log_deliverable_transition() '
      'appartient a « % » et ne peut pas executer project_backend_actor(). '
      'Le premier livrable echouerait sur « permission denied ».',
      proprietaire;
  end if;

  -- ET LE DROIT D'ECRIRE LA LIGNE, SEQUENCE COMPRISE. Une cle primaire
  -- `bigserial` est un objet distinct avec ses propres privileges; l'oublier
  -- fait echouer l'INSERT a une etape ou plus rien ne le rappelle.
  if not has_table_privilege('eurostruct_normative_writer',
                             'deliverable_state_transitions', 'INSERT')
     or not has_sequence_privilege('eurostruct_normative_writer',
                                   'deliverable_state_transitions_id_seq',
                                   'USAGE') then
    raise exception
      'ATELIER_0020_JOURNAL_SANS_DROIT_D_ECRITURE: le proprietaire du '
      'declencheur ne peut pas ecrire dans deliverable_state_transitions.';
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
