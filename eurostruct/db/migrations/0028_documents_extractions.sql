-- 0028 — UN PLAN DEPOSE DEVIENT DES PROPOSITIONS TRACEES, ET UNE PERSONNE
--        NOMMEE DECIDE
--
-- LE DEFAUT QUE CETTE MIGRATION FERME
-- -------------------------------------
-- `documents` et `extractions` existent depuis 0001, avec RLS forcee depuis
-- 0002, et n'ont jamais recu une ligne par le chemin produit: aucune
-- primitive ne les ecrit, aucun role du backend ne les lit. L'ingenieur
-- ressaisit donc a la main ce que ses plans disent deja.
--
-- 0001 posait UNE regle: une extraction `confirmed` ou `corrected` porte un
-- acteur, une date et une valeur retenue. Elle ne disait ni d'ou vient la
-- proposition (le texte lu, la page, la position), ni ce que devient une
-- decision une fois prise, ni qui a le droit de la prendre.
--
-- CE QUE CETTE MIGRATION AJOUTE
-- ------------------------------
--   1. la description des octets et le compte rendu d'analyse d'un document;
--   2. la tracabilite EXIGEE de chaque proposition: texte brut, page, boite
--      ou position, confiance strictement inferieure a 1, methode, version;
--   3. la coherence d'une decision, et son caractere DEFINITIF;
--   4. l'immuabilite de la provenance (proposition, texte, position);
--   5. la capacite `saisie`, au meme endroit que les quatre autres;
--   6. six primitives SECURITY DEFINER, accordees au seul backend authentifie;
--   7. la lecture, par le role de rapprochement, des colonnes qui designent
--      des octets — sans quoi chaque piece deposee serait un « orphelin ».
--
-- CE QU'ELLE NE FAIT PAS
-- -----------------------
-- Elle ne lit aucun document et ne propose aucune valeur: c'est le module
-- `eurostruct_extraction`, hors de la base et hors du moteur. Elle n'accorde
-- AUCUNE suppression: une proposition et sa decision restent la trace de ce
-- qui a ete lu et de qui l'a retenu.
--
-- LES CONTRAINTES SONT `not valid`, comme `storage_path_derives_from_sha` en
-- 0020: une ligne anterieure — s'il en existe — n'a pas ete ecrite sous ces
-- regles, et une migration qui echoue sur des donnees historiques bloque un
-- deploiement sans rien proteger. Elles s'appliquent a TOUTE ECRITURE
-- NOUVELLE, ce qui est exactement leur objet.
--
-- CHAQUE CONTRAINTE EST ENVELOPPEE DANS `coalesce(…, false)`. Une contrainte
-- `check` qui s'evalue a NULL PASSE: `method in (…)` avec une methode nulle,
-- ou `bbox[1] <= bbox[3]` sur une boite de quatre nuls, laisseraient entrer
-- exactement la ligne que la regle existe pour refuser.

begin;

-- LE DROIT DE CREER, POUR LA DUREE DE CETTE TRANSACTION SEULEMENT (0020,
-- 0024, 0025, 0027): `alter function ... owner to` exige que le nouveau
-- proprietaire detienne CREATE sur le schema. Repris en section 9.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LE DOCUMENT: SES OCTETS, ET CE QUE L'ANALYSE EN A LU
-- ---------------------------------------------------------------------
alter table documents
  add column if not exists storage_backend   text,
  add column if not exists format            text,
  add column if not exists analysis_status   text not null default 'en_attente',
  add column if not exists analysis_detail   text,
  add column if not exists analysis_report   jsonb,
  add column if not exists text_layer        boolean,
  add column if not exists extractor_version text,
  add column if not exists analysed_at       timestamptz;

comment on column documents.storage_backend is
  'Le magasin qui detient les octets (local, s3). Une ligne qui ne dit pas '
  'ou sont ses octets ne permet pas de les retrouver.';
comment on column documents.format is
  'Format constate par SIGNATURE des octets (pdf, dxf, dwg) — jamais par '
  'l''extension ni par le type annonce par le navigateur.';
comment on column documents.analysis_status is
  'en_attente: depose, pas encore analyse. analyse: lu. partiel: des pages '
  'n''ont pas ete lues (le compte rendu dit lesquelles et pourquoi). non_lu: '
  'conserve sans lecture (DWG sans conversion sous licence). echec: la '
  'lecture a echoue; une nouvelle analyse reste possible.';
comment on column documents.analysis_report is
  'Compte rendu par page: methode (texte natif, OCR), pages non lues et '
  'motif, version DWG. Fige des qu''une proposition existe.';

-- LES OCTETS SONT ADRESSES PAR LEUR CONTENU, comme ceux d'un livrable.
alter table documents
  add constraint document_bytes_are_addressed check (coalesce(
    sha256 ~ '^[0-9a-f]{64}$'
    and position(sha256 in storage_path) > 0
    and btrim(coalesce(storage_backend, '')) <> ''
    and btrim(coalesce(filename, '')) <> ''
    and btrim(coalesce(mime_type, '')) <> ''
    and size_bytes > 0
    -- La borne du magasin (`stockage.TAILLE_MAX`, 32 Mio): une ligne qui
    -- annoncerait plus decrirait des octets qu'aucun depot n'a pu ecrire.
    and size_bytes <= 33554432,
    false)) not valid,
  add constraint document_format_known check (coalesce(
    format in ('pdf', 'dxf', 'dwg'), false)) not valid;

-- LE STATUT D'ANALYSE est une colonne NOUVELLE a defaut renseigne: toutes les
-- lignes la satisfont deja, la contrainte peut donc etre validee d'emblee.
alter table documents
  add constraint document_analysis_status_known check (coalesce(
    analysis_status in ('en_attente', 'analyse', 'partiel', 'non_lu', 'echec'),
    false));


-- ---------------------------------------------------------------------
-- 2. LA PROPOSITION: CE QUI A ETE LU, OU, ET COMMENT
-- ---------------------------------------------------------------------
alter table extractions
  add column if not exists raw_text          text,
  add column if not exists element_label     text,
  add column if not exists position          jsonb,
  add column if not exists method            text,
  add column if not exists basis             jsonb,
  add column if not exists confirmed_by_name text,
  add column if not exists decision_note     text;

comment on column extractions.raw_text is
  'Le texte EXACT lu dans le document, d''ou la valeur proposee est tiree.';
comment on column extractions.element_label is
  'Le repere de l''element que la valeur decrit (P1, C3), quand le document '
  'le donne. Deux grandeurs lues ensemble (« P1 30x60 ») partagent ce repere.';
comment on column extractions.position is
  'Position dans le document quand une boite ne suffit pas, ou en plus '
  'd''elle: dimensions de la page, calque, poignee et point d''insertion DXF.';
comment on column extractions.method is
  'texte_natif, ocr, dxf ou vision. Une proposition ne dit jamais plus que '
  'ce que sa methode a pu lire.';
comment on column extractions.basis is
  'Comment la proposition a ete formee: regle appliquee, origine de l''unite '
  '(explicite, declaration, convention, absente).';
comment on column extractions.confirmed_by_name is
  'Le nom de la personne qui a decide, DERIVE de son adhesion au moment de '
  'la decision — jamais fourni par l''appelant.';
comment on column extractions.confirmed_by is
  'L''acteur qui a decide: confirmation, correction OU rejet.';

-- TOUT CE QUE L'EXIGENCE NOMME: document (cle etrangere existante), page,
-- boite ou position, confiance, texte brut — plus la methode et la version,
-- sans lesquelles on ne sait pas QUI a propose.
alter table extractions
  add constraint extraction_is_traced check (coalesce(
    btrim(coalesce(raw_text, '')) <> ''
    and page >= 1
    and (
      (array_length(bbox, 1) = 4
       and array_position(bbox, null) is null
       and bbox[1] <= bbox[3] and bbox[2] <= bbox[4])
      or jsonb_typeof(position) = 'object')
    -- STRICTEMENT INFERIEURE A 1: le score est indicatif (0001), et une
    -- certitude affichee inviterait a ne plus relire.
    and confidence >= 0 and confidence < 1
    and method in ('texte_natif', 'ocr', 'dxf', 'vision')
    and btrim(coalesce(model_name, '')) <> ''
    and kind ~ '^[a-z][a-z0-9_]{1,63}$',
    false)) not valid;

-- UNE GRANDEUR PAR LIGNE: `{"value": nombre|texte, "unit": texte|null}`, et
-- rien d'autre. Une forme libre laisserait une valeur sans unite passer pour
-- une valeur en millimetres.
alter table extractions
  add constraint extraction_value_shape check (coalesce(
    jsonb_typeof(proposed_value) = 'object'
    and proposed_value ? 'value' and proposed_value ? 'unit'
    and (proposed_value - 'value' - 'unit') = '{}'::jsonb
    and jsonb_typeof(proposed_value -> 'value') in ('number', 'string')
    and (jsonb_typeof(proposed_value -> 'value') <> 'string'
         or btrim(proposed_value ->> 'value') <> '')
    and jsonb_typeof(proposed_value -> 'unit') in ('string', 'null')
    and (jsonb_typeof(proposed_value -> 'unit') <> 'string'
         or btrim(proposed_value ->> 'unit') <> '')
    and (final_value is null or (
      jsonb_typeof(final_value) = 'object'
      and final_value ? 'value' and final_value ? 'unit'
      and (final_value - 'value' - 'unit') = '{}'::jsonb
      and jsonb_typeof(final_value -> 'value') in ('number', 'string')
      and (jsonb_typeof(final_value -> 'value') <> 'string'
           or btrim(final_value ->> 'value') <> '')
      and jsonb_typeof(final_value -> 'unit') in ('string', 'null')
      and (jsonb_typeof(final_value -> 'unit') <> 'string'
           or btrim(final_value ->> 'unit') <> ''))),
    false)) not valid;

-- UNE DECISION DIT CE QU'ELLE DIT, ET PORTE UN NOM.
--
--   proposed    aucune decision: ni valeur retenue, ni acteur, ni date;
--   confirmed   la valeur retenue EST la proposition;
--   corrected   la valeur retenue DIFFERE de la proposition — sinon c'est
--               une confirmation, et l'historique doit le dire;
--   rejected    aucune valeur retenue.
--
-- Toute decision — rejet compris — porte acteur, nom et date: un rejet
-- anonyme ne se relit pas mieux qu'une confirmation anonyme.
alter table extractions
  add constraint extraction_decision_coherent check (coalesce(
    case status
      when 'proposed' then final_value is null and confirmed_by is null
                           and confirmed_at is null
                           and confirmed_by_name is null
      when 'confirmed' then final_value = proposed_value
      when 'corrected' then final_value is not null
                            and final_value <> proposed_value
      when 'rejected'  then final_value is null
    end
    and (status = 'proposed'
         or (confirmed_by is not null and confirmed_at is not null
             and btrim(coalesce(confirmed_by_name, '')) <> '')),
    false)) not valid;


-- ---------------------------------------------------------------------
-- 3. CE QUI NE CHANGE JAMAIS
-- ---------------------------------------------------------------------
-- Les gardes ne sont pas SECURITY DEFINER: elles comparent OLD et NEW, et la
-- seule table qu'elles lisent (`extractions`, pour un document) l'est sous
-- l'identite et les politiques de l'appelant. Leur chemin est EPINGLE, pg_temp
-- en dernier — la regle que `authority_sql_hardening.sh` mesure pour les
-- gardes d'autorite (TP1), appliquee ici aussi.
create or replace function project_extraction_garde()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  -- UNE DECISION EST DEFINITIVE. Une valeur confirmee a tort se remplace dans
  -- l'etude par une saisie; la decision, elle, reste ce qui a ete decide.
  if old.status <> 'proposed' then
    raise exception
      'la proposition % a deja ete decidee (%), le % par %: une decision est '
      'definitive. Une valeur retenue a tort se remplace dans l''etude par '
      'une saisie; la trace de la decision reste.',
      old.id, old.status, to_char(old.confirmed_at, 'YYYY-MM-DD HH24:MI'),
      coalesce(old.confirmed_by_name, 'une personne non nommee')
      using errcode = 'restrict_violation';
  end if;

  -- LA PROVENANCE NE CHANGE JAMAIS: ce qui a ete lu, ou, par quoi.
  if new.id             is distinct from old.id
     or new.org_id      is distinct from old.org_id
     or new.project_id  is distinct from old.project_id
     or new.document_id is distinct from old.document_id
     or new.kind        is distinct from old.kind
     or new.proposed_value is distinct from old.proposed_value
     or new.page        is distinct from old.page
     or new.bbox        is distinct from old.bbox
     or new.position    is distinct from old.position
     or new.confidence  is distinct from old.confidence
     or new.model_name  is distinct from old.model_name
     or new.raw_text    is distinct from old.raw_text
     or new.element_label is distinct from old.element_label
     or new.method      is distinct from old.method
     or new.basis       is distinct from old.basis
     or new.created_at  is distinct from old.created_at then
    raise exception
      'la provenance d''une proposition ne change jamais (document, page, '
      'position, texte lu, valeur proposee, categorie, confiance, methode, '
      'version). Seule la decision s''y ajoute.'
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;

create trigger extractions_decision_definitive
  before update on extractions
  for each row execute function project_extraction_garde();

create or replace function project_document_garde()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  -- L'IDENTITE D'UN DOCUMENT DEPOSE: ses octets, ou ils sont, qui les a
  -- deposes. Une proposition cite ce document; le changer ferait citer a la
  -- proposition un document qu'elle n'a jamais lu.
  if new.id               is distinct from old.id
     or new.org_id        is distinct from old.org_id
     or new.project_id    is distinct from old.project_id
     or new.kind          is distinct from old.kind
     or new.filename      is distinct from old.filename
     or new.storage_backend is distinct from old.storage_backend
     or new.storage_path  is distinct from old.storage_path
     or new.mime_type     is distinct from old.mime_type
     or new.size_bytes    is distinct from old.size_bytes
     or new.sha256        is distinct from old.sha256
     or new.format        is distinct from old.format
     or new.uploaded_by   is distinct from old.uploaded_by
     or new.created_at    is distinct from old.created_at then
    raise exception
      'l''identite d''un document depose ne change jamais (octets, magasin, '
      'chemin, empreinte, format, nature, nom, deposant). Deposer un autre '
      'fichier cree un autre document.'
      using errcode = 'restrict_violation';
  end if;

  -- LE COMPTE RENDU D'ANALYSE EST FIGE DES QU'UNE PROPOSITION EXISTE. Une
  -- nouvelle analyse reste possible apres un echec ou un DWG non lu — tant
  -- que rien n'a ete propose, il n'y a rien a contredire.
  if (new.analysis_status    is distinct from old.analysis_status
      or new.analysis_detail is distinct from old.analysis_detail
      or new.analysis_report is distinct from old.analysis_report
      or new.page_count      is distinct from old.page_count
      or new.text_layer      is distinct from old.text_layer
      or new.extractor_version is distinct from old.extractor_version
      or new.analysed_at     is distinct from old.analysed_at)
     and exists (select 1 from extractions x where x.document_id = old.id) then
    raise exception
      'le document % porte deja des propositions: son compte rendu '
      'd''analyse est fige. Les propositions et leurs decisions restent la '
      'trace de ce qui a ete lu.', old.id
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;

create trigger documents_identite_figee
  before update on documents
  for each row execute function project_document_garde();


-- ---------------------------------------------------------------------
-- 4. LES PRIVILEGES DE TABLE, ET LES POLITIQUES QUI LES BORNENT
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0018 et 0020. AUCUN `delete`: le produit ne supprime ni
-- une piece deposee ni une proposition, et l'absence du droit le dit mieux
-- qu'une intention.
grant select, insert, update on documents to eurostruct_normative_writer;
grant select, insert, update on extractions to eurostruct_normative_writer;

-- LES POLITIQUES SONT NOMMEMENT ADRESSEES AU WRITER, comme en 0018: sans
-- clause `to`, elles viseraient PUBLIC, et toute session evaluant ces tables
-- devrait executer `project_actor_is_member()` sans en avoir le droit.
drop policy if exists documents_atelier_read on documents;
create policy documents_atelier_read on documents
  for select to eurostruct_normative_writer
  using (project_actor_is_member(org_id));
drop policy if exists documents_atelier_insert on documents;
create policy documents_atelier_insert on documents
  for insert to eurostruct_normative_writer
  with check (project_actor_can_write(org_id));
-- UPDATE EXIGE LES DEUX CLAUSES (0020): `with check` empeche de deplacer une
-- ligne vers une autre organisation en une seule instruction.
drop policy if exists documents_atelier_update on documents;
create policy documents_atelier_update on documents
  for update to eurostruct_normative_writer
  using (project_actor_can_write(org_id))
  with check (project_actor_can_write(org_id));

drop policy if exists extractions_atelier_read on extractions;
create policy extractions_atelier_read on extractions
  for select to eurostruct_normative_writer
  using (project_actor_is_member(org_id));
drop policy if exists extractions_atelier_insert on extractions;
create policy extractions_atelier_insert on extractions
  for insert to eurostruct_normative_writer
  with check (project_actor_can_write(org_id));
drop policy if exists extractions_atelier_update on extractions;
create policy extractions_atelier_update on extractions
  for update to eurostruct_normative_writer
  using (project_actor_can_write(org_id))
  with check (project_actor_can_write(org_id));


-- ---------------------------------------------------------------------
-- 5. LA CAPACITE `saisie`
-- ---------------------------------------------------------------------
-- Deposer une piece et decider d'une valeur extraite, c'est fournir les
-- ENTREES d'un calcul: la capacite suit donc `project_actor_can_write`, qui
-- garde `validating_engineer` pour les calculs (0023: « un ingenieur
-- validateur lance evidemment des calculs »). Un `viewer` lit, ne depose pas,
-- ne decide pas.
--
-- Le corps est celui de 0024, plus une branche. UNE SEULE FONCTION POUR TOUS
-- LES MESSAGES (0023): une cinquieme fonction poserait une question
-- legerement differente, et c'est la plus faible qui finirait par decider.
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
  select role, is_active, deactivated_at into m
    from organization_members
   where org_id = target_org
     and user_id = project_backend_actor();

  if not found then
    raise exception 'vous n''etes pas membre de cette organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  if not m.is_active then
    raise exception
      'votre acces a cette organisation a ete revoque le %. La ligne '
      'd''adhesion est conservee pour l''historique; elle n''ouvre plus rien.',
      coalesce(to_char(m.deactivated_at, 'YYYY-MM-DD'), 'une date inconnue')
      using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'lecture' then
    return m.role;
  end if;

  if p_capacite = 'redaction' then
    if m.role in ('owner', 'admin', 'engineer') then
      return m.role;
    end if;
    raise exception
      'le role « % » ne redige pas de livrable dans cette organisation.',
      m.role using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'validation' then
    if m.role = 'validating_engineer' then
      return m.role;
    end if;
    raise exception
      'le role « % » ne porte pas la validation technique dans cette '
      'organisation.', m.role using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'administration' then
    if m.role in ('owner', 'admin') then
      return m.role;
    end if;
    raise exception
      'le role « % » n''administre pas les membres de cette organisation.',
      m.role using errcode = 'insufficient_privilege';
  end if;

  -- SAISIE: deposer une piece du projet, decider d'une valeur extraite.
  if p_capacite = 'saisie' then
    if m.role in ('owner', 'admin', 'engineer', 'validating_engineer') then
      return m.role;
    end if;
    raise exception
      'le role « % » ne depose pas de piece et ne decide pas des valeurs '
      'extraites dans cette organisation. Ces gestes reviennent aux roles '
      'qui lancent un calcul: owner, admin, engineer, validating_engineer.',
      m.role using errcode = 'insufficient_privilege';
  end if;

  raise exception
    'ATELIER_0023_CAPACITE_INCONNUE: « % » n''est pas une capacite connue.',
    p_capacite using errcode = 'internal_error';
end;
$$;


-- ---------------------------------------------------------------------
-- 6. LES PRIMITIVES DU DOCUMENT
-- ---------------------------------------------------------------------

-- 6.1 INSCRIRE UN DOCUMENT DONT LES OCTETS SONT DEJA DEPOSES ET RELUS.
--
-- L'ORDRE EST CHEZ L'APPELANT, comme pour un livrable: deposer, relire,
-- verifier l'empreinte, PUIS inscrire. Une ligne ecrite avant le depot
-- promettrait un document introuvable.
--
-- IDEMPOTENTE PAR CONTENU. `unique (project_id, sha256)` existe depuis 0001:
-- deposer deux fois les memes octets dans un projet rend le document deja
-- inscrit, sans seconde ligne ni seconde analyse.
create or replace function project_document_register(
  p_project_id      uuid,
  p_kind            document_kind,
  p_filename        text,
  p_mime_type       text,
  p_format          text,
  p_storage_backend text,
  p_storage_path    text,
  p_sha256          text,
  p_size_bytes      bigint)
returns table (document_id uuid, already_present boolean)
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur   uuid := normative_authenticated_actor();
  org      uuid;
  existant uuid;
  nouveau  uuid;
begin
  -- L'ORGANISATION D'ABORD, LA CAPACITE ENSUITE (0023 §5.1).
  select p.org_id into org from projects p where p.id = p_project_id;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(org, 'saisie');

  -- LES NATURES QUE CE LOT SAIT RECEVOIR. Les autres valeurs de l'enumeration
  -- (photo, maquette IFC, rapport geotechnique, essai) attendent leur lecteur;
  -- les accepter ferait croire qu'elles sont lues.
  if p_kind not in ('architect_drawing', 'formwork_drawing', 'cctp', 'other') then
    raise exception
      'la nature « % » n''est pas recue par ce lot (plan d''architecte, plan '
      'de coffrage, cahier des charges, autre).', p_kind
      using errcode = 'check_violation';
  end if;

  if p_format is null or p_format not in ('pdf', 'dxf', 'dwg') then
    raise exception
      'le format « % » n''est pas pris en charge (pdf, dxf, dwg).',
      coalesce(p_format, '(absent)')
      using errcode = 'check_violation';
  end if;

  if coalesce(btrim(p_storage_backend), '') = ''
     or coalesce(btrim(p_storage_path), '') = ''
     or coalesce(btrim(p_filename), '') = ''
     or coalesce(btrim(p_mime_type), '') = ''
     or coalesce(p_size_bytes, 0) <= 0 then
    raise exception
      'description des octets incomplete (magasin, chemin, nom, type et '
      'taille sont tous requis). Un chemin qui ne permet pas de retrouver les '
      'octets n''est pas enregistre.'
      using errcode = 'check_violation';
  end if;

  if p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception
      'l''empreinte « % » n''est pas un sha256 hexadecimal minuscule.',
      coalesce(p_sha256, '(absente)')
      using errcode = 'check_violation';
  end if;

  select d.id into existant
    from documents d
   where d.project_id = p_project_id and d.sha256 = p_sha256;
  if existant is not null then
    return query select existant, true;
    return;
  end if;

  insert into documents (
    org_id, project_id, kind, filename, storage_path, mime_type, size_bytes,
    sha256, uploaded_by, storage_backend, format, analysis_status)
  values (
    org, p_project_id, p_kind, btrim(p_filename), btrim(p_storage_path),
    btrim(p_mime_type), p_size_bytes, p_sha256, acteur,
    btrim(p_storage_backend), p_format, 'en_attente')
  on conflict (project_id, sha256) do nothing
  returning id into nouveau;

  -- DEUX DEPOTS CONCURRENTS DES MEMES OCTETS: le second n'insere rien et
  -- relit la ligne du premier. Ni doublon, ni erreur d'unicite rendue a un
  -- utilisateur qui n'a rien fait de faux.
  if nouveau is null then
    select d.id into existant
      from documents d
     where d.project_id = p_project_id and d.sha256 = p_sha256;
    if existant is null then
      raise exception
        'ATELIER_0028_DOCUMENT_INVISIBLE: l''inscription n''a rien ecrit et '
        'aucun document de meme empreinte n''est lisible dans ce projet.'
        using errcode = 'insufficient_privilege';
    end if;
    return query select existant, true;
    return;
  end if;

  return query select nouveau, false;
end;
$$;


-- 6.2 ENREGISTRER L'ANALYSE ET TOUTES SES PROPOSITIONS, EN UNE TRANSACTION.
--
-- `createExtractionRecords()`, cote base. UN SEUL APPEL: enchainer un ordre
-- par proposition depuis Python laisserait, sur incident au milieu, un
-- document « analyse » avec la moitie de ce qu'il contient — et personne ne
-- saurait que l'autre moitie manque.
--
-- TOUTE PROPOSITION ENTRE `proposed`. La colonne n'est pas un parametre: il
-- n'existe aucun chemin par lequel une analyse confirmerait quoi que ce soit.
create or replace function project_document_record_analysis(
  p_document_id       uuid,
  p_status            text,
  p_detail            text,
  p_page_count        integer,
  p_text_layer        boolean,
  p_report            jsonb,
  p_extractor_version text,
  p_extractions       jsonb)
returns integer
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  -- L'IDENTITE EST EXIGEE MEME SI ELLE N'EST PAS ECRITE ICI: sans acteur
  -- authentifie, la primitive leve avant de lire quoi que ce soit.
  acteur  uuid := normative_authenticated_actor();
  d       record;
  e       jsonb;
  n       integer := 0;
  touches integer;
begin
  select doc.id, doc.org_id, doc.project_id into d
    from documents doc where doc.id = p_document_id;
  if not found then
    raise exception 'document introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(d.org_id, 'saisie');

  if p_status is null
     or p_status not in ('analyse', 'partiel', 'non_lu', 'echec') then
    raise exception
      'statut d''analyse « % » inconnu (analyse, partiel, non_lu, echec).',
      coalesce(p_status, '(absent)')
      using errcode = 'check_violation';
  end if;

  if coalesce(btrim(p_extractor_version), '') = '' then
    raise exception
      'une analyse sans version d''extracteur ne dit pas qui a lu.'
      using errcode = 'check_violation';
  end if;

  if p_extractions is null or jsonb_typeof(p_extractions) <> 'array' then
    raise exception
      'les propositions doivent former une liste (eventuellement vide).'
      using errcode = 'check_violation';
  end if;

  if p_status in ('non_lu', 'echec') and jsonb_array_length(p_extractions) > 0 then
    raise exception
      'un document « % » ne porte aucune proposition: ce qui n''a pas ete lu '
      'ne propose rien.', p_status
      using errcode = 'check_violation';
  end if;

  -- UNE NOUVELLE ANALYSE N'EST POSSIBLE QUE TANT QUE RIEN N'A ETE PROPOSE.
  if exists (select 1 from extractions x where x.document_id = p_document_id) then
    raise exception
      'ce document a deja ete analyse et porte des propositions. Les '
      'propositions et leurs decisions restent la trace de ce qui a ete lu: '
      'une seconde analyse les contredirait.'
      using errcode = 'restrict_violation';
  end if;

  update documents
     set analysis_status   = p_status,
         analysis_detail   = nullif(btrim(coalesce(p_detail, '')), ''),
         analysis_report   = p_report,
         page_count        = p_page_count,
         text_layer        = p_text_layer,
         extractor_version = btrim(p_extractor_version),
         analysed_at       = now()
   where id = p_document_id;
  get diagnostics touches = row_count;
  -- UNE ECRITURE QUE LA POLITIQUE FILTRE NE LEVE PAS: elle touche zero ligne
  -- (0023, defaut 3). On le constate au lieu d'annoncer une analyse que la
  -- base n'a pas enregistree.
  if touches <> 1 then
    raise exception
      'le compte rendu d''analyse n''a pas ete enregistre: votre acces ne '
      'permet pas cette ecriture.'
      using errcode = 'insufficient_privilege';
  end if;

  for e in select value from jsonb_array_elements(p_extractions) loop
    insert into extractions (
      org_id, project_id, document_id, kind, proposed_value, status, page,
      bbox, confidence, model_name, raw_text, element_label, position, method,
      basis)
    values (
      d.org_id, d.project_id, p_document_id, e ->> 'kind',
      e -> 'proposed_value', 'proposed', (e ->> 'page')::integer,
      case when jsonb_typeof(e -> 'bbox') = 'array'
           then array(select b::double precision
                        from jsonb_array_elements_text(e -> 'bbox') b)
      end,
      (e ->> 'confidence')::double precision,
      btrim(p_extractor_version),
      e ->> 'raw_text',
      nullif(btrim(coalesce(e ->> 'element_label', '')), ''),
      case when jsonb_typeof(e -> 'position') = 'object' then e -> 'position' end,
      e ->> 'method',
      case when jsonb_typeof(e -> 'basis') = 'object' then e -> 'basis' end);
    n := n + 1;
  end loop;

  return n;
end;
$$;


-- 6.3 LA LISTE DES DOCUMENTS D'UN PROJET, ET OU EN EST LEUR REVUE.
create or replace function project_document_list(p_project_id uuid)
returns table (
  document_id       uuid,
  kind              document_kind,
  filename          text,
  format            text,
  mime_type         text,
  size_bytes        bigint,
  sha256            text,
  page_count        integer,
  text_layer        boolean,
  analysis_status   text,
  analysis_detail   text,
  analysis_report   jsonb,
  extractor_version text,
  analysed_at       timestamptz,
  uploaded_by       uuid,
  uploaded_by_me    boolean,
  created_at        timestamptz,
  proposed_count    integer,
  confirmed_count   integer,
  corrected_count   integer,
  rejected_count    integer)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
  org    uuid;
begin
  select p.org_id into org from projects p where p.id = p_project_id;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(org, 'lecture');

  return query
    select d.id, d.kind, d.filename, d.format, d.mime_type, d.size_bytes,
           d.sha256, d.page_count, d.text_layer, d.analysis_status,
           d.analysis_detail, d.analysis_report, d.extractor_version,
           d.analysed_at, d.uploaded_by, d.uploaded_by = acteur, d.created_at,
           (select count(*)::integer from extractions x
             where x.document_id = d.id and x.status = 'proposed'),
           (select count(*)::integer from extractions x
             where x.document_id = d.id and x.status = 'confirmed'),
           (select count(*)::integer from extractions x
             where x.document_id = d.id and x.status = 'corrected'),
           (select count(*)::integer from extractions x
             where x.document_id = d.id and x.status = 'rejected')
      from documents d
     where d.project_id = p_project_id
     order by d.created_at desc, d.id;
end;
$$;


-- 6.4 OU SONT LES OCTETS D'UN DOCUMENT.
--
-- Le chemin ne traverse pas jusqu'a l'ecran (comme pour un livrable): il sert
-- au backend a servir le fichier, ou a le relire pour une nouvelle analyse.
create or replace function project_document_bytes(
  p_project_id uuid, p_document_id uuid)
returns table (
  storage_backend text,
  storage_path    text,
  sha256          text,
  size_bytes      bigint,
  filename        text,
  mime_type       text,
  format          text,
  kind            document_kind,
  analysis_status text)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  org uuid;
begin
  select p.org_id into org from projects p where p.id = p_project_id;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(org, 'lecture');

  return query
    select d.storage_backend, d.storage_path, d.sha256, d.size_bytes,
           d.filename, d.mime_type, d.format, d.kind, d.analysis_status
      from documents d
     where d.id = p_document_id and d.project_id = p_project_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 7. LES PRIMITIVES DE LA REVUE
-- ---------------------------------------------------------------------

-- 7.1 LES PROPOSITIONS: d'un projet, d'un document, ou d'une liste nommee.
--
-- La liste nommee sert au controle de provenance d'un calcul: l'API relit,
-- SOUS L'IDENTITE DE L'APPELANT, exactement les extractions que la requete
-- cite. Une extraction d'un autre projet n'y apparait pas — elle n'est donc
-- pas une provenance recevable.
create or replace function project_extraction_list(
  p_project_id  uuid,
  p_document_id uuid default null,
  p_ids         uuid[] default null)
returns table (
  extraction_id     uuid,
  document_id       uuid,
  document_filename text,
  document_sha256   text,
  kind              text,
  proposed_value    jsonb,
  final_value       jsonb,
  status            extraction_status,
  page              integer,
  bbox              double precision[],
  -- `position` NE PEUT PAS NOMMER UN PARAMETRE: c'est un mot-cle de la
  -- grammaire (`position(x in y)`), admis comme nom de colonne et refuse comme
  -- nom de fonction, de type ou de parametre — et les colonnes d'un
  -- `returns table` sont des parametres de sortie. La colonne de table garde
  -- son nom; la sortie l'expose sous celui-ci.
  doc_position      jsonb,
  confidence        double precision,
  method            text,
  model_name        text,
  raw_text          text,
  element_label     text,
  basis             jsonb,
  confirmed_by      uuid,
  confirmed_by_name text,
  confirmed_at      timestamptz,
  decision_note     text,
  created_at        timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  org uuid;
begin
  select p.org_id into org from projects p where p.id = p_project_id;
  if org is null then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(org, 'lecture');

  return query
    select x.id, x.document_id, d.filename, d.sha256, x.kind,
           x.proposed_value, x.final_value, x.status, x.page, x.bbox,
           x.position, x.confidence, x.method, x.model_name, x.raw_text,
           x.element_label, x.basis, x.confirmed_by, x.confirmed_by_name,
           x.confirmed_at, x.decision_note, x.created_at
      from extractions x
      join documents d on d.id = x.document_id
     where x.project_id = p_project_id
       and (p_document_id is null or x.document_id = p_document_id)
       and (p_ids is null or x.id = any (p_ids))
     -- L'ORDRE DE LECTURE: document, page, puis de haut en bas et de gauche
     -- a droite. Une revue qui suit le plan se fait sans chercher.
     order by d.created_at, x.document_id, x.page,
              coalesce(x.bbox[2], 0), coalesce(x.bbox[1], 0), x.kind, x.id;
end;
$$;


-- 7.2 DECIDER: CONFIRMER, CORRIGER, REJETER.
--
-- LE NOM VIENT DE L'ADHESION, ET S'IL MANQUE ON REFUSE — exactement comme
-- l'attestation (0020, 0023). Le prendre dans le corps laisserait decider
-- sous le nom qu'on choisit; substituer l'identifiant technique donnerait une
-- confirmation signee « 3f2a-… », qui ne nomme personne.
--
-- LA DATE EST CELLE DU SERVEUR (`now()`), jamais celle du navigateur.
create or replace function project_extraction_decide(
  p_project_id    uuid,
  p_extraction_id uuid,
  p_decision      text,
  p_final_value   jsonb default null,
  p_note          text default null)
returns table (
  extraction_id     uuid,
  status            extraction_status,
  final_value       jsonb,
  confirmed_by      uuid,
  confirmed_by_name text,
  confirmed_at      timestamptz,
  decision_note     text)
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur  uuid := normative_authenticated_actor();
  x       record;
  nom     text;
  nouveau extraction_status;
  retenue jsonb;
  touches integer;
begin
  select e.id, e.org_id, e.status, e.proposed_value, e.confirmed_at,
         e.confirmed_by_name
    into x
    from extractions e
   where e.id = p_extraction_id and e.project_id = p_project_id;
  if not found then
    raise exception 'proposition introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  perform project_exiger_capacite(x.org_id, 'saisie');

  select nullif(btrim(coalesce(m.display_name, '')), '') into nom
    from organization_members m
   where m.org_id = x.org_id and m.user_id = acteur;
  if nom is null then
    raise exception
      'aucun nom n''est enregistre pour votre adhesion. Une decision sur une '
      'valeur extraite porte le nom d''une personne: l''organisation doit '
      'renseigner ce nom avant que vous puissiez confirmer, corriger ou '
      'rejeter.'
      using errcode = 'check_violation';
  end if;

  if x.status <> 'proposed' then
    raise exception
      'cette proposition a deja ete decidee (%), le % par %: la decision est '
      'definitive.', x.status, to_char(x.confirmed_at, 'YYYY-MM-DD HH24:MI'),
      coalesce(x.confirmed_by_name, 'une personne non nommee')
      using errcode = 'restrict_violation';
  end if;

  if p_final_value is not null and not coalesce(
       jsonb_typeof(p_final_value) = 'object'
       and p_final_value ? 'value' and p_final_value ? 'unit'
       and (p_final_value - 'value' - 'unit') = '{}'::jsonb
       and jsonb_typeof(p_final_value -> 'value') in ('number', 'string')
       and (jsonb_typeof(p_final_value -> 'value') <> 'string'
            or btrim(p_final_value ->> 'value') <> '')
       and jsonb_typeof(p_final_value -> 'unit') in ('string', 'null')
       and (jsonb_typeof(p_final_value -> 'unit') <> 'string'
            or btrim(p_final_value ->> 'unit') <> ''),
       false) then
    raise exception
      'la valeur retenue doit avoir la forme {"value": nombre ou texte, '
      '"unit": texte ou null}, et rien d''autre.'
      using errcode = 'check_violation';
  end if;

  case p_decision
    when 'confirm' then
      if p_final_value is not null and p_final_value <> x.proposed_value then
        raise exception
          'confirmer retient la valeur proposee telle quelle. Pour retenir '
          'une autre valeur, corrigez.'
          using errcode = 'check_violation';
      end if;
      nouveau := 'confirmed';
      retenue := x.proposed_value;
    when 'correct' then
      if p_final_value is null then
        raise exception 'une correction porte la valeur retenue.'
          using errcode = 'check_violation';
      end if;
      if p_final_value = x.proposed_value then
        raise exception
          'la valeur corrigee est identique a la proposition: confirmez-la, '
          'pour que l''historique dise ce qui s''est passe.'
          using errcode = 'check_violation';
      end if;
      nouveau := 'corrected';
      retenue := p_final_value;
    when 'reject' then
      if p_final_value is not null then
        raise exception 'un rejet ne retient aucune valeur.'
          using errcode = 'check_violation';
      end if;
      nouveau := 'rejected';
      retenue := null;
    else
      raise exception
        'decision « % » inconnue (confirm, correct, reject).',
        coalesce(p_decision, '(absente)')
        using errcode = 'check_violation';
  end case;

  update extractions e
     set status            = nouveau,
         final_value       = retenue,
         confirmed_by      = acteur,
         confirmed_by_name = nom,
         confirmed_at      = now(),
         decision_note     = nullif(btrim(coalesce(p_note, '')), '')
   where e.id = p_extraction_id and e.status = 'proposed';
  get diagnostics touches = row_count;
  -- DEUX DECISIONS CONCURRENTES: la seconde attend le verrou de ligne, relit
  -- un statut qui n'est plus `proposed`, et ne touche rien. On le dit au lieu
  -- de rendre une decision qui n'a pas ete enregistree.
  if touches <> 1 then
    raise exception
      'la proposition n''a pas ete modifiee: elle a ete decidee entre-temps, '
      'ou votre acces ne permet pas cette ecriture.'
      using errcode = 'restrict_violation';
  end if;

  return query
    select e.id, e.status, e.final_value, e.confirmed_by,
           e.confirmed_by_name, e.confirmed_at, e.decision_note
      from extractions e
     where e.id = p_extraction_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 8. PROPRIETE ET ACCES
-- ---------------------------------------------------------------------
do $$
declare
  f text;
begin
  -- LES SIX PRIMITIVES: proprietaire commun, ACL fermee puis rouverte au seul
  -- role d'execution du backend (0018 §6).
  foreach f in array array[
    'project_document_register(uuid, document_kind, text, text, text, text,'
      || ' text, text, bigint)',
    'project_document_record_analysis(uuid, text, text, integer, boolean,'
      || ' jsonb, text, jsonb)',
    'project_document_list(uuid)',
    'project_document_bytes(uuid, uuid)',
    'project_extraction_list(uuid, uuid, uuid[])',
    'project_extraction_decide(uuid, uuid, text, jsonb, text)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;

  -- LES GARDES: meme proprietaire, aucun droit d'execution a accorder — un
  -- declencheur ne s'appelle pas, il se declenche.
  foreach f in array array['project_extraction_garde()',
                           'project_document_garde()']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
  end loop;

  -- `project_exiger_capacite` A ETE REMPLACEE: on repose proprietaire et ACL
  -- comme 0024, sans rien supposer de ce que `create or replace` conserve.
  -- Elle reste INTERNE.
  execute 'alter function project_exiger_capacite(uuid, text) '
          'owner to eurostruct_normative_writer';
  execute 'revoke all on function project_exiger_capacite(uuid, text) from public';
  execute 'grant execute on function project_exiger_capacite(uuid, text) '
          'to eurostruct_normative_writer';
end
$$;


-- ---------------------------------------------------------------------
-- 9. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
revoke create on schema public from eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 10. LE RAPPROCHEMENT VOIT AUSSI LES PIECES DEPOSEES
-- ---------------------------------------------------------------------
-- Les pieces deposees vivent dans le meme magasin que les livrables
-- (prefixe `pieces/`). Sans ces colonnes, `reconciliation.py` les declarerait
-- toutes orphelines — et un rapport plein de faux orphelins cache les vrais.
--
-- PAR COLONNES, COMME EN 0026: ni le nom du fichier, ni le deposant, ni le
-- compte rendu d'analyse. Le rapprochement constate des octets, il ne lit pas
-- les dossiers.
do $$
begin
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_reconciliation') then
    raise exception
      'le role « eurostruct_reconciliation » est absent. Il est cree par la '
      'PHASE 0 (control_plane/0001_normative_seal.sql). Le creer ici '
      'donnerait au migrateur le droit de creer des roles.';
  end if;
end
$$;

grant select (id, org_id, project_id, storage_backend, storage_path,
              sha256, size_bytes)
  on documents to eurostruct_reconciliation;

drop policy if exists documents_reconciliation_read on documents;
create policy documents_reconciliation_read on documents
  for select to eurostruct_reconciliation
  using (true);


-- ---------------------------------------------------------------------
-- 11. CE QUE CETTE MIGRATION DOIT AVOIR OBTENU
-- ---------------------------------------------------------------------
do $$
declare
  r        record;
  manquant text;
begin
  -- LES SIX PRIMITIVES: definies, SECURITY DEFINER, chemin epingle, au bon
  -- proprietaire, fermees a PUBLIC, ouvertes au backend.
  for r in
    select p.proname, pg_get_userbyid(p.proowner) as proprio, p.prosecdef,
           array_to_string(p.proconfig, ',') as chemin,
           has_function_privilege('public', p.oid, 'EXECUTE') as pub,
           has_function_privilege('eurostruct_authority_backend', p.oid,
                                  'EXECUTE') as backend
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname in ('project_document_register',
                         'project_document_record_analysis',
                         'project_document_list', 'project_document_bytes',
                         'project_extraction_list',
                         'project_extraction_decide')
  loop
    if r.proprio <> 'eurostruct_normative_writer' then
      raise exception
        'ATELIER_0028_PROPRIETAIRE: % appartient a « % ». Son SECURITY '
        'DEFINER endosserait quelqu''un d''autre.', r.proname, r.proprio;
    end if;
    if not r.prosecdef then
      raise exception
        'ATELIER_0028_SANS_DEFINER: % n''est pas SECURITY DEFINER: le backend '
        'authentifie ne lit pas ces tables directement.', r.proname;
    end if;
    if r.chemin is null or position('search_path=public, pg_temp' in r.chemin) = 0 then
      raise exception
        'ATELIER_0028_SEARCH_PATH_NON_EPINGLE: % porte « % ».',
        r.proname, coalesce(r.chemin, '(nul)');
    end if;
    if r.pub then
      raise exception
        'ATELIER_0028_PUBLIC_EXECUTE: PUBLIC peut executer %.', r.proname;
    end if;
    if not r.backend then
      raise exception
        'ATELIER_0028_BACKEND_SANS_ACCES: le backend authentifie n''execute '
        'pas %: la lecture des plans serait morte pour tout le monde.',
        r.proname;
    end if;
  end loop;

  select string_agg(attendue, ', ') into manquant
    from unnest(array['project_document_register',
                      'project_document_record_analysis',
                      'project_document_list', 'project_document_bytes',
                      'project_extraction_list',
                      'project_extraction_decide']) attendue
   where not exists (select 1 from pg_proc p
                       join pg_namespace n on n.oid = p.pronamespace
                      where n.nspname = 'public' and p.proname = attendue);
  if manquant is not null then
    raise exception 'ATELIER_0028_PRIMITIVE_ABSENTE: %.', manquant;
  end if;

  -- LES GARDES: posees, a chemin epingle terminant par pg_temp, non
  -- executables par PUBLIC.
  for r in
    select p.proname, array_to_string(p.proconfig, ',') as chemin,
           has_function_privilege('public', p.oid, 'EXECUTE') as pub
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname in ('project_extraction_garde', 'project_document_garde')
  loop
    if r.chemin is null or r.chemin not like '%search_path=public, pg_temp%' then
      raise exception
        'ATELIER_0028_GARDE_NON_EPINGLEE: % porte « % ».',
        r.proname, coalesce(r.chemin, '(nul)');
    end if;
    if r.pub then
      raise exception 'ATELIER_0028_GARDE_PUBLIQUE: PUBLIC peut executer %.',
        r.proname;
    end if;
  end loop;

  if (select count(*) from pg_trigger
       where tgname in ('extractions_decision_definitive',
                        'documents_identite_figee')
         and not tgisinternal and tgenabled = 'O') <> 2 then
    raise exception
      'ATELIER_0028_GARDES_ABSENTES: les deux declencheurs ne sont pas '
      'poses et actifs.';
  end if;

  -- LES CONTRAINTES SONT LA.
  select string_agg(attendue, ', ') into manquant
    from unnest(array['document_bytes_are_addressed', 'document_format_known',
                      'document_analysis_status_known',
                      'extraction_is_traced', 'extraction_value_shape',
                      'extraction_decision_coherent',
                      'confirmed_extraction_is_signed']) attendue
   where not exists (select 1 from pg_constraint c where c.conname = attendue);
  if manquant is not null then
    raise exception 'ATELIER_0028_CONTRAINTE_ABSENTE: %.', manquant;
  end if;

  -- AUCUNE SUPPRESSION ACCORDEE au proprietaire des primitives.
  if has_table_privilege('eurostruct_normative_writer', 'public.documents', 'DELETE')
     or has_table_privilege('eurostruct_normative_writer', 'public.extractions', 'DELETE') then
    raise exception
      'ATELIER_0028_SUPPRESSION_OCTROYEE: le proprietaire des primitives peut '
      'supprimer une piece ou une proposition.';
  end if;

  -- LA CAPACITE `saisie` EST CONNUE de la fonction qui porte les messages.
  if not exists (select 1 from pg_proc p
                   join pg_namespace n on n.oid = p.pronamespace
                  where n.nspname = 'public'
                    and p.proname = 'project_exiger_capacite'
                    and p.prosrc like '%''saisie''%') then
    raise exception
      'ATELIER_0028_CAPACITE_ABSENTE: project_exiger_capacite ne connait pas '
      '« saisie ».';
  end if;

  -- LE RAPPROCHEMENT LIT EXACTEMENT LES SEPT COLONNES, ET N'ECRIT RIEN.
  select string_agg(distinct a.attname, ',' order by a.attname) into manquant
    from pg_attribute a
    cross join lateral aclexplode(a.attacl) acl
   where a.attrelid = 'public.documents'::regclass
     and a.attnum > 0 and not a.attisdropped
     and acl.privilege_type = 'SELECT'
     and acl.grantee <> 0
     and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation';
  if manquant is distinct from
     'id,org_id,project_id,sha256,size_bytes,storage_backend,storage_path' then
    raise exception
      'ATELIER_0028_RAPPROCHEMENT_COLONNES: « % » octroyees sur documents.',
      coalesce(manquant, '(aucune)');
  end if;
  if exists (select 1 from pg_class c
               join pg_namespace n on n.oid = c.relnamespace
              cross join lateral aclexplode(c.relacl) acl
              where n.nspname = 'public' and c.relname = 'documents'
                and acl.grantee <> 0
                and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation') then
    raise exception
      'ATELIER_0028_RAPPROCHEMENT_TABLE_ENTIERE: un droit de table entiere a '
      'ete octroye sur documents au role de rapprochement.';
  end if;
end;
$$;

-- LA COMPOSITION D'AUTORITE N'A PAS BOUGE: aucun nom de cette migration
-- n'entre dans le vocabulaire que le manifeste de 0015 decouvre. On le
-- REVERIFIE quand meme.
do $$
begin
  perform assert_authority_composition();
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
