-- =====================================================================
-- EUROSTRUCT — 0010: confirmation normative, append-only
--
-- Ce que cette migration ajoute: la persistance de la validation NORMATIVE
-- (niveau 1 sur 3), celle qui atteste qu'une personne a lu une annexe
-- nationale et reconnait que la regle transcrite dit bien ce que le document
-- dit.
--
-- Elle n'a rien a voir avec la validation METIER de 0009. La difference n'est
-- pas de degre: une signature de projet engage UNE etude et UN bureau
-- d'etudes; une confirmation du referentiel engage TOUTES les etudes de la
-- juridiction, sur tous les locataires, d'un seul coup. Le garde-fou est donc
-- plus etroit, pas plus large — et surtout separe: aucune table ici ne porte
-- de project_id ni d'org_id, et un test le verifie.
--
-- Tout est EVENEMENTIEL et immuable
-- ----------------------------------
-- Un octroi, une confirmation, une revocation sont des evenements. Aucune
-- colonne `is_active`, `is_revoked`, `revoked_at` ou `revoked_by` ne vient se
-- poser sur la ligne d'origine: l'etat actif se CALCULE en confrontant
-- l'evenement d'origine et l'eventuel evenement de retrait.
--
-- La raison n'est pas doctrinale. Un booleen mute rend indistinguables
-- « jamais revoque » et « revoque puis remis », et c'est exactement la
-- question qu'un audit pose dix ans plus tard.
--
-- Ce que le client ne fournit jamais
-- -----------------------------------
-- L'identite du signataire, l'horodatage et le snapshot d'autorisation sont
-- ECRITS PAR LE SERVEUR. Le precedent est 0009 (`validator_role` et
-- `professional_id` derives de l'adhesion, jamais crus sur parole), et son
-- avertissement vaut ici: un tableau fourni par l'acteur et verifie pour sa
-- seule presence laisse cet acteur se declarer lui-meme autorise.
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- Les trois permissions, distinctes et sans implication mutuelle
-- ---------------------------------------------------------------------
-- Aucune n'entraine les autres. C'est la propriete centrale de ce modele:
-- celui qui distribue les habilitations n'est pas celui qui lit les annexes,
-- et celui qui lit les annexes n'est pas celui qui retire la lecture d'un
-- autre. Les confondre ferait d'un administrateur le validateur de tout le
-- referentiel.
create type normative_permission as enum (
  'can_manage_normative_authorisations',
  'can_validate_normative_reference',
  'can_revoke_normative_confirmation'
);

comment on type normative_permission is
  'Trois pouvoirs disjoints. Aucun n''implique un autre: un administrateur '
  'des habilitations ne confirme aucune regle et ne revoque aucune '
  'confirmation, sauf a detenir explicitement le droit correspondant.';


-- ---------------------------------------------------------------------
-- L'origine d'un octroi
-- ---------------------------------------------------------------------
create type normative_grant_origin as enum ('bootstrap', 'delegated');


-- ---------------------------------------------------------------------
-- 1. Octrois d'autorisation — evenements immuables
-- ---------------------------------------------------------------------
create table normative_authorisation_grants (
  id             uuid primary key default gen_random_uuid(),
  grantee_id     uuid not null references auth.users(id),
  -- Le nom LISIBLE du titulaire, fige par celui qui octroie. C'est la source
  -- d'autorite du `verifier_name` d'une confirmation: laisser le client le
  -- fournir permettrait de signer sous l'identite lisible d'un autre, et
  -- `verifier_id` impose par le serveur ne s'en apercevrait pas — la note de
  -- calcul, elle, n'affiche que le nom.
  --
  -- Fige et immuable: un changement de nom se fait par un NOUVEL octroi, si
  -- bien que les confirmations deja signees gardent le nom d'alors.
  grantee_name   text not null,
  permission     normative_permission not null,

  -- Portee. NULL sur un axe = « toutes les valeurs de cet axe ». Autorise
  -- pour l'administration, INTERDIT pour la verification normative: voir la
  -- contrainte verification_scope_is_explicit ci-dessous.
  country_code    country_code,
  standard_family text,
  part            text,
  edition         text,

  -- NULL uniquement pour l'amorcage: a ce moment aucun administrateur
  -- n'existe encore, donc personne ne peut octroyer. C'est l'autorite de
  -- deploiement qui agit, et elle n'a pas de ligne dans auth.users.
  granted_by     uuid references auth.users(id),
  granted_at     timestamptz not null default now(),
  origin         normative_grant_origin not null default 'delegated',
  reason         text not null,

  constraint grant_is_motivated check (btrim(reason) <> ''),
  constraint grant_names_a_person check (btrim(grantee_name) <> ''),

  constraint bootstrap_has_no_grantor check (
    (origin = 'bootstrap') = (granted_by is null)
  ),

  -- « Evite une autorisation globale implicite pour un verificateur
  -- normatif »: un relecteur habilite sur l'EC2 belge ne l'est pas sur l'EC8
  -- espagnol, et un NULL laisse a l'insertion le rendrait habilite partout
  -- sans que personne ne l'ait decide.
  constraint verification_scope_is_explicit check (
    permission <> 'can_validate_normative_reference'
    or (country_code is not null
        and standard_family is not null
        and part is not null)
  ),

  -- L'amorcage ne cree QUE de l'administration. Ecrit ici plutot que dans la
  -- seule fonction: une contrainte de table survit a une reecriture de
  -- fonction, pas l'inverse.
  constraint bootstrap_grants_administration_only check (
    origin <> 'bootstrap'
    or permission = 'can_manage_normative_authorisations'
  )
);

-- Au plus UN octroi d'amorcage, jamais deux, quoi qu'il arrive ensuite. Un
-- index partiel sur une constante: la garantie ne depend d'aucune fonction,
-- d'aucun verrou et d'aucune revocation. Deux appels concurrents a
-- bootstrap_normative_administrator() en verront donc un echouer, meme si le
-- controle d'existence les laissait passer tous les deux.
--
-- Il n'empeche PAS un nouvel octroi apres revocation: ceux-la sont
-- 'delegated'.
create unique index normative_bootstrap_is_singular
  on normative_authorisation_grants ((true)) where origin = 'bootstrap';

create index on normative_authorisation_grants (grantee_id, permission);
create index on normative_authorisation_grants
  (permission, country_code, standard_family, part);

comment on table normative_authorisation_grants is
  'Octroi d''un pouvoir normatif, sur une portee explicite. Evenement '
  'immuable: se retirer se fait par une ligne de '
  'normative_authorisation_revocations, jamais par une colonne mutee.';


-- ---------------------------------------------------------------------
-- 2. Revocations d'autorisation — evenements immuables
-- ---------------------------------------------------------------------
create table normative_authorisation_revocations (
  id         uuid primary key default gen_random_uuid(),
  grant_id   uuid not null unique
             references normative_authorisation_grants(id) on delete restrict,
  revoked_by uuid not null references auth.users(id),
  revoked_at timestamptz not null default now(),
  reason     text not null,

  constraint revocation_is_motivated check (btrim(reason) <> '')
);

comment on table normative_authorisation_revocations is
  'Retrait d''un octroi. `unique (grant_id)`: un octroi se retire une fois. '
  '`on delete restrict`: l''octroi retire RESTE en base, lisible — c''est ce '
  'qui rend une signature ancienne encore explicable.';


-- ---------------------------------------------------------------------
-- 3. Confirmations normatives — evenements immuables
-- ---------------------------------------------------------------------
create table normative_rule_confirmations (
  id uuid primary key default gen_random_uuid(),

  -- --- le sujet: ConfirmationSubjectKey COMPLET -----------------------
  -- Les huit composantes du modele de domaine (jalon 6.3a1). Une cle
  -- incomplete laisserait deux verificateurs « s'accorder » sur deux choses
  -- differentes.
  country_code            country_code not null,
  standard_family         text not null,
  part                    text not null,
  rule_id                 text not null,
  stack_digest            text not null,
  normative_spec_digest   text not null,
  implementation_digest   text not null,
  evidence_digest         text not null,

  -- --- de quoi relire l'empreinte dans dix ans -------------------------
  -- Un hash seul ne dit pas ce qui a ete signe. Le payload canonique est donc
  -- conserve a cote, avec l'algorithme et la version de canonicalisation qui
  -- l'ont produit.
  digest_algorithm         text not null,
  canonicalization_version text not null,
  normative_spec_payload   text not null,
  implementation_payload   text not null,
  evidence_payload         text not null,
  stack_payload            text not null,

  -- --- la pile attestee, structuree ------------------------------------
  stack_snapshot jsonb not null,
  -- Extraite du snapshot PAR LE SERVEUR: c'est elle que la portee de
  -- l'habilitation compare, elle ne peut donc pas venir du client.
  annex_edition  text not null,

  -- --- ce qui a ete lu, et ce qu'il en dit ------------------------------
  evidence_items jsonb not null,
  statement      text not null,

  -- --- qui, quand: ECRITS PAR LE SERVEUR --------------------------------
  verifier_id   uuid not null references auth.users(id),
  verifier_name text not null,
  verified_at   timestamptz not null,

  -- --- snapshot d'autorisation: ECRIT PAR LE SERVEUR --------------------
  -- Preuve d'audit resolue au moment de la signature, jamais un controle
  -- d'acces fourni par l'appelant.
  authorisation_grant_id uuid not null
                         references normative_authorisation_grants(id),
  authorisation_scope    jsonb not null,

  -- --- technique, et strictement technique ------------------------------
  -- Empeche qu'un envoi rejoue cree deux lignes. Ne participe JAMAIS au
  -- decompte a quatre yeux, qui se fait en verifier_id distincts.
  idempotency_key text not null,

  created_at timestamptz not null default now(),

  constraint confirmation_is_stated check (btrim(statement) <> ''),
  constraint confirmation_names_a_person check (btrim(verifier_name) <> ''),
  constraint confirmation_has_evidence check (jsonb_array_length(evidence_items) > 0),
  constraint idempotency_key_is_unique unique (idempotency_key)
);

-- AUCUN index d'unicite semantique sur (sujet, verificateur).
--
-- Il en existait un, et il etait faux: il interdisait a un relecteur de
-- re-signer un sujet apres que sa premiere attestation eut ete revoquee. Or
-- une revocation motivee suivie d'une nouvelle revue est exactement le
-- parcours normal d'une correction — l'interdire obligeait a changer de
-- relecteur pour corriger une erreur.
--
-- Deux attestations actives d'un meme verificateur ne comptent de toute facon
-- que pour UN regard: le decompte se fait en verifier_id distincts, dans le
-- domaine (independent_regards). Une unicite technique n'a pas a trancher une
-- question semantique.
--
-- Restent: la cle primaire, et l'unicite de la cle d'idempotence.
create index on normative_rule_confirmations (rule_id, country_code);
create index on normative_rule_confirmations (verifier_id);

comment on table normative_rule_confirmations is
  'Validation NORMATIVE (niveau 1 sur 3). Ni project_id ni org_id: la lecture '
  'de NBN EN 1992-1-1 ANB est vraie pour tous les projets belges ou pour '
  'aucun. Un rattachement client ferait glisser une lecture d''annexe vers un '
  'engagement professionnel sur une etude.';

comment on column normative_rule_confirmations.idempotency_key is
  'Deduplication TECHNIQUE d''un envoi rejoue. Ne dit rien du nombre de '
  'regards: deux envois d''une meme lecture ne font pas deux relecteurs.';


-- ---------------------------------------------------------------------
-- 4. Revocations de confirmation — evenements immuables
-- ---------------------------------------------------------------------
create table normative_rule_confirmation_revocations (
  id              uuid primary key default gen_random_uuid(),
  confirmation_id uuid not null unique
                  references normative_rule_confirmations(id) on delete restrict,
  revoked_by      uuid not null references auth.users(id),
  revoked_by_name text not null,
  revoked_at      timestamptz not null,

  -- NULL quand le verificateur retire SA PROPRE confirmation: il n'a besoin
  -- d'aucune habilitation pour cela. Renseigne sinon, et resolu par le
  -- serveur comme pour une confirmation.
  authorisation_grant_id uuid references normative_authorisation_grants(id),
  authorisation_scope    jsonb not null,

  reason text not null,

  constraint confirmation_revocation_is_motivated check (btrim(reason) <> ''),
  constraint confirmation_revocation_names_a_person check (
    btrim(revoked_by_name) <> ''
  )
);

comment on table normative_rule_confirmation_revocations is
  'Retrait d''une confirmation. Ne modifie jamais la confirmation: elle reste '
  'lisible, comme un livrable final errone le reste (0003). On n''exige ni '
  'pages lues ni citation — revoquer n''est pas relire l''annexe — mais un '
  'motif, sans quoi un retrait ne se distingue pas d''une fausse manoeuvre.';


-- =====================================================================
-- Fonctions serveur
-- =====================================================================

-- ---------------------------------------------------------------------
-- L'etat actif se CALCULE, il ne se lit pas sur une colonne
-- ---------------------------------------------------------------------
create or replace function normative_grant_is_active(p_grant_id uuid)
returns boolean
language sql
stable
as $$
  select not exists (
    select 1 from normative_authorisation_revocations r
     where r.grant_id = p_grant_id
  );
$$;

comment on function normative_grant_is_active is
  'Aucune colonne is_active n''existe: elle rendrait indistinguables « jamais '
  'revoque » et « revoque puis remis ».';


-- ---------------------------------------------------------------------
-- Resolution d'une habilitation sur une portee EXACTE
-- ---------------------------------------------------------------------
-- Un axe NULL dans l'octroi vaut « toutes les valeurs de cet axe ». Un axe
-- renseigne doit correspondre exactement. La verification normative ne peut
-- pas avoir country/family/part a NULL (contrainte de table), donc le
-- caractere generique ne beneficie qu'a l'administration.
--
-- DETERMINISME. « Le plus specifique » ne suffit pas: deux octrois peuvent
-- avoir la MEME specificite sans avoir la meme portee — par exemple
-- (BE, EN 1992, *, *) et (BE, *, 1-1, *) face a une cible BE/EN 1992/1-1.
-- Les departager par une date d'octroi ou un identifiant reviendrait a faire
-- dependre le snapshot d'audit d'un detail que personne n'a decide.
--
-- On REFUSE donc l'ambiguite plutot que de la trancher en silence. Le message
-- nomme les octrois en cause: la correction est de revoquer celui qui ne doit
-- plus s'appliquer, pas de deviner.
create or replace function resolve_normative_authorisation(
  p_user       uuid,
  p_permission normative_permission,
  p_country    country_code,
  p_family     text,
  p_part       text,
  p_edition    text
) returns normative_authorisation_grants
language plpgsql
stable
as $$
declare
  retenu normative_authorisation_grants;
  candidats bigint;
  noms text;
begin
  with eligibles as (
    select g.*,
           (g.country_code    is not null)::int
         + (g.standard_family is not null)::int
         + (g.part            is not null)::int
         + (g.edition         is not null)::int as specificite
      from normative_authorisation_grants g
     where g.grantee_id = p_user
       and g.permission = p_permission
       and (g.country_code    is null or g.country_code    = p_country)
       and (g.standard_family is null or g.standard_family = p_family)
       and (g.part            is null or g.part            = p_part)
       and (g.edition         is null or g.edition         = p_edition)
       and normative_grant_is_active(g.id)
  ), meilleurs as (
    select * from eligibles
     where specificite = (select max(specificite) from eligibles)
  )
  select count(*), string_agg(id::text, ', ' order by id)
    into candidats, noms
    from meilleurs;

  if candidats = 0 then
    return null;
  end if;

  if candidats > 1 then
    raise exception
      'autorisation ambigue: % octrois actifs de meme specificite couvrent '
      '%/%/% edition % pour %. Octrois en cause: %. Revoquer celui qui ne '
      'doit plus s''appliquer plutot que de laisser le serveur choisir.',
      candidats, p_country, p_family, p_part, coalesce(p_edition, '*'),
      p_user, noms
      using errcode = 'cardinality_violation';
  end if;

  select g.* into retenu
    from normative_authorisation_grants g
   where g.grantee_id = p_user
     and g.permission = p_permission
     and (g.country_code    is null or g.country_code    = p_country)
     and (g.standard_family is null or g.standard_family = p_family)
     and (g.part            is null or g.part            = p_part)
     and (g.edition         is null or g.edition         = p_edition)
     and normative_grant_is_active(g.id)
   order by (g.country_code    is not null)::int
          + (g.standard_family is not null)::int
          + (g.part            is not null)::int
          + (g.edition         is not null)::int desc
   limit 1;
  return retenu;
end;
$$;


-- ---------------------------------------------------------------------
-- Le snapshot d'audit, ecrit par le serveur et par lui seul
-- ---------------------------------------------------------------------
create or replace function normative_authorisation_snapshot(
  g normative_authorisation_grants
) returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'grant_id',        g.id,
    'permission',      g.permission,
    'country_code',    g.country_code,
    'standard_family', g.standard_family,
    'part',            g.part,
    'edition',         g.edition,
    'granted_by',      g.granted_by,
    'granted_at',      g.granted_at,
    'origin',          g.origin,
    'resolved_at',     now()
  );
$$;


-- ---------------------------------------------------------------------
-- Integrite d'un digest: verifiee, jamais crue sur parole
-- ---------------------------------------------------------------------
-- On ne reimplemente PAS la canonicalisation en SQL — elle vit en Python et
-- la dupliquer creerait deux verites qui divergeraient. On verifie seulement
-- que le hash annonce est bien celui du payload deja canonique.
create or replace function assert_digest_integrity(
  p_label     text,
  p_algorithm text,
  p_payload   text,
  p_digest    text
) returns void
language plpgsql
immutable
as $$
declare
  reel text;
begin
  if p_algorithm <> 'sha256' then
    raise exception
      'algorithme de hachage « % » inconnu pour %. Accepter sans controle '
      'ferait dependre la garantie du nom donne a l''algorithme.',
      p_algorithm, p_label
      using errcode = 'check_violation';
  end if;

  reel := encode(sha256(convert_to(p_payload, 'UTF8')), 'hex');
  if reel <> p_digest then
    raise exception
      'empreinte % incorrecte: % annoncee, % calculee sur le payload porte. '
      'Une ligne immuable ecrite avec un faux hash reste fausse.',
      p_label, left(p_digest, 16), left(reel, 16)
      using errcode = 'check_violation';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- Journalisation: on REUTILISE audit_log (0001), pas une seconde table
-- ---------------------------------------------------------------------
create or replace function log_normative_event(
  p_action text, p_entity text, p_entity_id uuid, p_payload jsonb,
  p_user uuid
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  -- org_id et project_id restent NULL: un evenement normatif n'appartient a
  -- aucun client. C'est la raison pour laquelle audit_log les declare
  -- nullables.
  insert into audit_log (user_id, action, entity, entity_id, payload)
  values (p_user, p_action, p_entity, p_entity_id, p_payload);
end;
$$;


-- =====================================================================
-- Amorcage: la racine de confiance
-- =====================================================================
-- Reservee au proprietaire de la base ou a l'autorite de deploiement. Elle ne
-- cree QUE de l'administration, jamais un droit de verification: sans quoi la
-- premiere personne installee pourrait confirmer seule tout le referentiel
-- d'une juridiction.
create or replace function bootstrap_normative_administrator(
  p_grantee      uuid,
  p_grantee_name text,
  p_reason       text
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  nouvel_id uuid;
  proprietaire text;
begin
  -- Deux appels concurrents doivent en voir un seul aboutir. Le verrou
  -- serialise le controle d'existence ci-dessous; l'index partiel
  -- normative_bootstrap_is_singular le garantit structurellement meme si le
  -- verrou etait contourne. Deux garde-fous, deux portees.
  perform pg_advisory_xact_lock(hashtext('eurostruct.normative.bootstrap'));

  select pg_get_userbyid(datdba) into proprietaire
    from pg_database where datname = current_database();

  if current_user <> proprietaire then
    raise exception
      'l''amorcage normatif est reserve au proprietaire de la base (%). '
      'Utilisateur courant: %.', proprietaire, current_user
      using errcode = 'insufficient_privilege';
  end if;

  if exists (
    select 1 from normative_authorisation_grants g
     where g.permission = 'can_manage_normative_authorisations'
       and normative_grant_is_active(g.id)
  ) then
    raise exception
      'un administrateur normatif existe deja: l''amorcage ne sert qu''a '
      'ouvrir la chaine, pas a la contourner. Passer par un octroi ordinaire.'
      using errcode = 'unique_violation';
  end if;

  if btrim(coalesce(p_reason, '')) = '' then
    raise exception 'l''amorcage doit etre motive.'
      using errcode = 'check_violation';
  end if;
  if btrim(coalesce(p_grantee_name, '')) = '' then
    raise exception
      'l''amorcage doit nommer une personne: c''est de ce nom que toute la '
      'chaine de delegation heritera sa lisibilite.'
      using errcode = 'check_violation';
  end if;

  insert into normative_authorisation_grants
    (grantee_id, grantee_name, permission, granted_by, origin, reason)
  values
    (p_grantee, p_grantee_name, 'can_manage_normative_authorisations', null,
     'bootstrap', p_reason)
  returning id into nouvel_id;

  perform log_normative_event(
    'normative.authorisation.bootstrap',
    'normative_authorisation_grants',
    nouvel_id,
    jsonb_build_object('grantee_id', p_grantee, 'origin', 'bootstrap',
                       'reason', p_reason,
                       'performed_by_db_user', current_user),
    null
  );

  return nouvel_id;
end;
$$;

revoke all on function bootstrap_normative_administrator(uuid, text, text)
  from public;

comment on function bootstrap_normative_administrator is
  'Ouvre la chaine de confiance UNE FOIS. Refuse si un administrateur actif '
  'existe deja, n''accorde jamais can_validate_normative_reference, et '
  'produit une trace d''audit immuable d''origine « bootstrap ».';


-- =====================================================================
-- Controles a l'insertion
-- =====================================================================

-- ---------------------------------------------------------------------
-- Octroi d'autorisation
-- ---------------------------------------------------------------------
create or replace function check_normative_grant() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
  habilitation normative_authorisation_grants;
begin
  -- L'amorcage passe par sa fonction dediee, qui pose origin='bootstrap'.
  -- Toute autre insertion est une DELEGATION, et le trigger l'impose plutot
  -- que de faire confiance a la colonne recue.
  if new.origin = 'bootstrap' then
    -- Seule la fonction d'amorcage, SECURITY DEFINER, arrive ici sans acteur
    -- authentifie. Une insertion directe se declarant « bootstrap » depuis
    -- une session authentifiee est un contournement.
    if acteur is not null then
      raise exception
        'origin « bootstrap » refuse depuis une session authentifiee: '
        'l''amorcage passe par bootstrap_normative_administrator().'
        using errcode = 'insufficient_privilege';
    end if;
    return new;
  end if;

  new.origin := 'delegated';

  if acteur is null then
    raise exception
      'aucune identite authentifiee: un octroi normatif engage celui qui le '
      'consent, il ne peut pas etre anonyme.'
      using errcode = 'insufficient_privilege';
  end if;
  new.granted_by := acteur;

  -- « L'administrateur initial ne peut pas s'accorder lui-meme le droit de
  -- verifier une regle. » Generalise a toute permission: quelqu'un qui
  -- s'octroie quoi que ce soit se place hors de la chaine de delegation, et
  -- c'est precisement ce que la racine de confiance existe pour empecher.
  if new.grantee_id = acteur then
    raise exception
      'auto-attribution refusee: % ne peut pas s''octroyer « % ». Un pouvoir '
      'normatif se recoit d''un tiers habilite.', acteur, new.permission
      using errcode = 'insufficient_privilege';
  end if;

  -- Deux octrois ACTIFS de portee rigoureusement identique rendraient la
  -- resolution ambigue. On refuse a la source plutot que de laisser
  -- l'ambiguite apparaitre a la premiere confirmation, quand plus personne ne
  -- fera le lien avec l'octroi de trop.
  --
  -- La comparaison passe par IS NOT DISTINCT FROM: deux NULL designent la
  -- meme portee « tous », alors que `=` les dirait differents.
  if exists (
    select 1 from normative_authorisation_grants g
     where g.grantee_id = new.grantee_id
       and g.permission = new.permission
       and g.country_code    is not distinct from new.country_code
       and g.standard_family is not distinct from new.standard_family
       and g.part            is not distinct from new.part
       and g.edition         is not distinct from new.edition
       and normative_grant_is_active(g.id)
  ) then
    raise exception
      'un octroi actif de meme portee existe deja pour % (%). Le revoquer '
      'd''abord si la portee doit changer: deux octrois identiques actifs '
      'rendraient le snapshot d''audit indeterminable.',
      new.grantee_id, new.permission
      using errcode = 'unique_violation';
  end if;

  habilitation := resolve_normative_authorisation(
    acteur, 'can_manage_normative_authorisations',
    new.country_code, new.standard_family, new.part, new.edition
  );

  if habilitation.id is null then
    raise exception
      'octroi refuse: % ne detient pas « can_manage_normative_authorisations » '
      'couvrant la portee %/%/%/%.',
      acteur, coalesce(new.country_code::text, '*'),
      coalesce(new.standard_family, '*'), coalesce(new.part, '*'),
      coalesce(new.edition, '*')
      using errcode = 'insufficient_privilege';
  end if;

  perform log_normative_event(
    'normative.authorisation.granted',
    'normative_authorisation_grants',
    new.id,
    jsonb_build_object(
      'grantee_id', new.grantee_id, 'permission', new.permission,
      'country_code', new.country_code, 'standard_family', new.standard_family,
      'part', new.part, 'edition', new.edition,
      'granted_under', normative_authorisation_snapshot(habilitation)
    ),
    acteur
  );
  return new;
end;
$$;

create trigger normative_grants_are_checked
  before insert on normative_authorisation_grants
  for each row execute function check_normative_grant();


-- ---------------------------------------------------------------------
-- Revocation d'autorisation
-- ---------------------------------------------------------------------
create or replace function check_normative_grant_revocation() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
  cible  normative_authorisation_grants;
  habilitation normative_authorisation_grants;
begin
  if acteur is null then
    raise exception 'aucune identite authentifiee.'
      using errcode = 'insufficient_privilege';
  end if;
  new.revoked_by := acteur;
  new.revoked_at := now();

  select * into cible from normative_authorisation_grants
   where id = new.grant_id;
  if not found then
    raise exception 'octroi % introuvable', new.grant_id
      using errcode = 'foreign_key_violation';
  end if;

  habilitation := resolve_normative_authorisation(
    acteur, 'can_manage_normative_authorisations',
    cible.country_code, cible.standard_family, cible.part, cible.edition
  );
  if habilitation.id is null then
    raise exception
      'revocation refusee: % ne detient pas « can_manage_normative_'
      'authorisations » couvrant la portee de l''octroi %.', acteur, cible.id
      using errcode = 'insufficient_privilege';
  end if;

  perform log_normative_event(
    'normative.authorisation.revoked',
    'normative_authorisation_revocations',
    new.id,
    jsonb_build_object('grant_id', new.grant_id, 'reason', new.reason,
                       'revoked_under',
                       normative_authorisation_snapshot(habilitation)),
    acteur
  );
  return new;
end;
$$;

create trigger normative_grant_revocations_are_checked
  before insert on normative_authorisation_revocations
  for each row execute function check_normative_grant_revocation();


-- ---------------------------------------------------------------------
-- Confirmation normative
-- ---------------------------------------------------------------------
create or replace function check_normative_confirmation() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
  habilitation normative_authorisation_grants;
  edition_annexe text;
begin
  -- 1. L'identite vient du contexte authentifie, jamais de la charge utile.
  if acteur is null then
    raise exception
      'aucune identite authentifiee: une lecture d''annexe se signe. Un '
      'identifiant technique ne repond de rien.'
      using errcode = 'insufficient_privilege';
  end if;
  new.verifier_id := acteur;

  -- 2. L'horodatage est produit par le serveur.
  new.verified_at := now();

  -- 3. Integrite des quatre empreintes. On ne recanonicalise rien: on verifie
  --    que le hash annonce est celui du payload deja canonique.
  perform assert_digest_integrity('normative_spec', new.digest_algorithm,
                                  new.normative_spec_payload,
                                  new.normative_spec_digest);
  perform assert_digest_integrity('implementation', new.digest_algorithm,
                                  new.implementation_payload,
                                  new.implementation_digest);
  perform assert_digest_integrity('evidence', new.digest_algorithm,
                                  new.evidence_payload, new.evidence_digest);
  perform assert_digest_integrity('stack', new.digest_algorithm,
                                  new.stack_payload, new.stack_digest);

  -- 4. L'edition de l'annexe est EXTRAITE du snapshot de pile par le serveur:
  --    c'est elle que la portee de l'habilitation compare, elle ne peut donc
  --    pas etre fournie par celui qu'on controle.
  select c ->> 'edition' into edition_annexe
    from jsonb_array_elements(new.stack_snapshot -> 'components') c
   where c ->> 'role' = 'annexe'
   order by (c ->> 'application_order')::int desc
   limit 1;

  if edition_annexe is null then
    raise exception
      'la pile attestee ne comporte aucun composant de role « annexe »: '
      'impossible d''etablir sur quelle edition d''annexe nationale porte '
      'cette confirmation, donc impossible d''en verifier la portee.'
      using errcode = 'check_violation';
  end if;
  new.annex_edition := edition_annexe;

  -- 5. L'habilitation est RESOLUE cote serveur, sur la portee exacte.
  habilitation := resolve_normative_authorisation(
    acteur, 'can_validate_normative_reference',
    new.country_code, new.standard_family, new.part, edition_annexe
  );
  if habilitation.id is null then
    raise exception
      'confirmation refusee: % ne detient pas « can_validate_normative_'
      'reference » couvrant %/%/% edition %. Une valeur nationale erronee se '
      'propage a TOUTES les etudes de la juridiction: l''habilitation est '
      'nominative et de portee explicite.',
      acteur, new.country_code, new.standard_family, new.part, edition_annexe
      using errcode = 'insufficient_privilege';
  end if;

  -- 6. Le snapshot d'autorisation est ECRIT ICI. Le client ne le fournit pas
  --    et ne peut pas le falsifier: quoi qu'il ait mis dans ces colonnes,
  --    elles sont ecrasees.
  new.authorisation_grant_id := habilitation.id;
  new.authorisation_scope := normative_authorisation_snapshot(habilitation);

  -- 7. Le NOM LISIBLE vient de l'octroi, pas du client. `verifier_id` impose
  --    par le serveur ne suffisait pas: la note de calcul n'affiche que le
  --    nom, et un nom libre permettait de signer sous l'identite lisible d'un
  --    autre. L'octroi etant immuable, un changement de nom ulterieur
  --    n'altere aucune confirmation deja signee.
  new.verifier_name := habilitation.grantee_name;

  perform log_normative_event(
    'normative.confirmation.created',
    'normative_rule_confirmations',
    new.id,
    jsonb_build_object(
      'rule_id', new.rule_id, 'country_code', new.country_code,
      'standard_family', new.standard_family, 'part', new.part,
      'annex_edition', edition_annexe,
      'normative_spec_digest', new.normative_spec_digest,
      'implementation_digest', new.implementation_digest,
      'evidence_digest', new.evidence_digest,
      'stack_digest', new.stack_digest,
      'authorisation', new.authorisation_scope
    ),
    acteur
  );
  return new;
end;
$$;

create trigger normative_confirmations_are_checked
  before insert on normative_rule_confirmations
  for each row execute function check_normative_confirmation();


-- ---------------------------------------------------------------------
-- Revocation d'une confirmation
-- ---------------------------------------------------------------------
create or replace function check_normative_confirmation_revocation()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
  c normative_rule_confirmations;
  habilitation normative_authorisation_grants;
begin
  if acteur is null then
    raise exception 'aucune identite authentifiee.'
      using errcode = 'insufficient_privilege';
  end if;
  new.revoked_by := acteur;
  new.revoked_at := now();

  select * into c from normative_rule_confirmations
   where id = new.confirmation_id;
  if not found then
    raise exception 'confirmation % introuvable', new.confirmation_id
      using errcode = 'foreign_key_violation';
  end if;

  if acteur = c.verifier_id then
    -- Retirer SA PROPRE lecture ne demande aucune habilitation: c'est la
    -- correction d'un acte personnel, pas un pouvoir sur autrui.
    new.authorisation_grant_id := null;
    new.authorisation_scope := jsonb_build_object(
      'self_revocation', true, 'verifier_id', c.verifier_id,
      'resolved_at', now()
    );
    -- Le nom deja fige sur la confirmation retiree: c'est la meme personne.
    new.revoked_by_name := c.verifier_name;
  else
    -- Sur la lecture d'un AUTRE, il faut le droit dedie. « can_manage_
    -- normative_authorisations » ne le donne pas: distribuer des
    -- habilitations et defaire le travail d'un relecteur sont deux pouvoirs
    -- differents, et les confondre ferait de l'administrateur l'arbitre du
    -- referentiel.
    habilitation := resolve_normative_authorisation(
      acteur, 'can_revoke_normative_confirmation',
      c.country_code, c.standard_family, c.part, c.annex_edition
    );
    if habilitation.id is null then
      raise exception
        'revocation refusee: % n''est pas l''auteur de la confirmation % et '
        'ne detient pas « can_revoke_normative_confirmation » couvrant '
        '%/%/% edition %.',
        acteur, c.id, c.country_code, c.standard_family, c.part,
        c.annex_edition
        using errcode = 'insufficient_privilege';
    end if;
    new.authorisation_grant_id := habilitation.id;
    new.authorisation_scope := normative_authorisation_snapshot(habilitation);
    new.revoked_by_name := habilitation.grantee_name;
  end if;

  perform log_normative_event(
    'normative.confirmation.revoked',
    'normative_rule_confirmation_revocations',
    new.id,
    jsonb_build_object('confirmation_id', new.confirmation_id,
                       'reason', new.reason,
                       'authorisation', new.authorisation_scope),
    acteur
  );
  return new;
end;
$$;

create trigger normative_confirmation_revocations_are_checked
  before insert on normative_rule_confirmation_revocations
  for each row execute function check_normative_confirmation_revocation();


-- =====================================================================
-- Immuabilite: le mecanisme de 0003, sans en inventer un second
-- =====================================================================
create trigger normative_grants_are_immutable
  before update or delete on normative_authorisation_grants
  for each row execute function forbid_mutation();

create trigger normative_grant_revocations_are_immutable
  before update or delete on normative_authorisation_revocations
  for each row execute function forbid_mutation();

create trigger normative_confirmations_are_immutable
  before update or delete on normative_rule_confirmations
  for each row execute function forbid_mutation();

create trigger normative_confirmation_revocations_are_immutable
  before update or delete on normative_rule_confirmation_revocations
  for each row execute function forbid_mutation();

-- Le journal d'audit: protection LIMITEE aux evenements normatifs.
--
-- Une version precedente rendait `audit_log` immuable EN ENTIER. C'etait un
-- changement transversal sur une table existante, non demande, et qui aurait
-- ferme sans preavis la retention, l'anonymisation et la maintenance du
-- journal pour tous ses autres producteurs.
--
-- Les quatre tables evenementielles ci-dessus constituent deja la preuve
-- principale. Ce declencheur ne protege donc que les lignes normatives, et
-- laisse le reste du journal exactement comme il etait. La politique globale
-- du journal, si elle doit changer, releve d'un jalon qui lui est consacre.
create or replace function forbid_normative_audit_mutation() returns trigger
language plpgsql as $$
begin
  if coalesce(old.action, '') like 'normative.%' then
    raise exception
      'la trace normative % (%) est immuable: elle atteste qui a octroye, '
      'confirme ou revoque. Les autres lignes du journal ne sont pas '
      'concernees par cette regle.', old.action, old.id
      using errcode = 'restrict_violation';
  end if;
  return coalesce(new, old);
end;
$$;

create trigger audit_log_normative_entries_are_immutable
  before update or delete on audit_log
  for each row execute function forbid_normative_audit_mutation();


-- =====================================================================
-- RLS: moindre privilege, et une vue minimale pour le calcul
-- =====================================================================
-- Une version precedente ouvrait ces quatre tables en lecture a TOUT
-- utilisateur authentifie, par analogie avec le referentiel global de 0002.
-- L'analogie etait fausse: `national_annex_parameters` contient des valeurs
-- normatives, ces tables-ci contiennent de la GOUVERNANCE — qui est habilite
-- a quoi, qui a signe quoi, sous quel nom, avec quelle declaration
-- personnelle et quelles pages lues.
--
-- Matrice appliquee:
--
--   ressource                        | ecriture                | lecture
--   ---------------------------------+-------------------------+---------------------------
--   octrois d'autorisation           | insert controle par     | gouvernance
--                                    | trigger (detenteur de   | + le titulaire, sur SES
--                                    | can_manage_...)         |   propres octrois
--   revocations d'autorisation       | idem                    | idem
--   confirmations completes          | insert controle par     | gouvernance + provider
--                                    | trigger (detenteur de   | backend + le signataire,
--                                    | can_validate_...)       |   sur SES propres lignes
--   revocations de confirmation      | idem                    | idem
--   statut normatif pour le calcul   | aucune ecriture directe | vue minimale, sans aucune
--                                    | (vue)                   |   donnee personnelle
--
-- Par defaut: refus. Aucune policy UPDATE ni DELETE n'existe, et aucun droit
-- UPDATE/DELETE n'est accorde: l'operation est refusee par la RLS pour les
-- chemins qui la respectent, et par les declencheurs d'immuabilite pour ceux
-- qui la contournent.
--
-- Le titulaire voit SES propres octrois: sans cela il ne peut pas savoir ce
-- qu'il a le droit de faire, et le refus qu'il rencontrerait serait
-- inexplicable pour lui.

-- Deux roles de service. Crees ici s'ils manquent, comme le stub local cree
-- `authenticated`: un deploiement gere les fournit deja.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'normative_backend') then
    create role normative_backend;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'normative_governance') then
    create role normative_governance;
  end if;
end
$$;

comment on type normative_grant_origin is
  'bootstrap = ouverture de la chaine par l''autorite de deploiement; '
  'delegated = octroi consenti par un detenteur de '
  'can_manage_normative_authorisations.';

alter table normative_authorisation_grants        enable row level security;
alter table normative_authorisation_revocations   enable row level security;
alter table normative_rule_confirmations          enable row level security;
alter table normative_rule_confirmation_revocations enable row level security;

-- --- privileges de table -----------------------------------------------
-- Rien pour PUBLIC. `authenticated` peut inserer (les triggers gouvernent) et
-- lire ses propres lignes; la lecture large appartient aux roles de service.
revoke all on normative_authorisation_grants          from public;
revoke all on normative_authorisation_revocations     from public;
revoke all on normative_rule_confirmations            from public;
revoke all on normative_rule_confirmation_revocations from public;

grant insert, select on normative_authorisation_grants          to authenticated;
grant insert, select on normative_authorisation_revocations     to authenticated;
grant insert, select on normative_rule_confirmations            to authenticated;
grant insert, select on normative_rule_confirmation_revocations to authenticated;

grant select on normative_authorisation_grants          to normative_governance;
grant select on normative_authorisation_revocations     to normative_governance;
grant select on normative_rule_confirmations            to normative_governance;
grant select on normative_rule_confirmation_revocations to normative_governance;

-- Le provider backend lit ce dont l'evaluation a besoin, et rien de la
-- gouvernance des habilitations.
grant select on normative_rule_confirmations            to normative_backend;
grant select on normative_rule_confirmation_revocations to normative_backend;

-- --- policies ------------------------------------------------------------
create policy normative_grants_own_read on normative_authorisation_grants
  for select to authenticated using (grantee_id = auth.uid());
create policy normative_grants_governance_read on normative_authorisation_grants
  for select to normative_governance using (true);
create policy normative_grants_insert on normative_authorisation_grants
  for insert to authenticated with check (true);

create policy normative_grant_revocations_own_read
  on normative_authorisation_revocations
  for select to authenticated using (
    exists (select 1 from normative_authorisation_grants g
             where g.id = grant_id and g.grantee_id = auth.uid())
  );
create policy normative_grant_revocations_governance_read
  on normative_authorisation_revocations
  for select to normative_governance using (true);
create policy normative_grant_revocations_insert
  on normative_authorisation_revocations
  for insert to authenticated with check (true);

create policy normative_confirmations_own_read on normative_rule_confirmations
  for select to authenticated using (verifier_id = auth.uid());
create policy normative_confirmations_backend_read on normative_rule_confirmations
  for select to normative_backend using (true);
create policy normative_confirmations_governance_read
  on normative_rule_confirmations
  for select to normative_governance using (true);
create policy normative_confirmations_insert on normative_rule_confirmations
  for insert to authenticated with check (true);

create policy normative_confirmation_revocations_own_read
  on normative_rule_confirmation_revocations
  for select to authenticated using (revoked_by = auth.uid());
create policy normative_confirmation_revocations_backend_read
  on normative_rule_confirmation_revocations
  for select to normative_backend using (true);
create policy normative_confirmation_revocations_governance_read
  on normative_rule_confirmation_revocations
  for select to normative_governance using (true);
create policy normative_confirmation_revocations_insert
  on normative_rule_confirmation_revocations
  for insert to authenticated with check (true);


-- ---------------------------------------------------------------------
-- La vue minimale: ce dont un calcul a besoin, et rien de plus
-- ---------------------------------------------------------------------
-- Aucune donnee personnelle: ni nom, ni identifiant de verificateur, ni
-- declaration, ni pages lues, ni portee d'habilitation. Seulement le sujet et
-- le NOMBRE de regards independants actifs.
--
-- `security_invoker = false` (defaut en PG16) est ici DELIBERE: la vue
-- s'execute avec les droits de son proprietaire et ne se heurte donc pas a la
-- RLS des tables sous-jacentes. C'est ce qui permet d'ouvrir le strict
-- necessaire sans ouvrir les tables completes.
create view normative_rule_confirmation_status as
  select c.country_code,
         c.standard_family,
         c.part,
         c.rule_id,
         c.stack_digest,
         c.normative_spec_digest,
         c.implementation_digest,
         c.evidence_digest,
         c.annex_edition,
         count(distinct c.verifier_id) as active_independent_regards
    from normative_rule_confirmations c
   where not exists (
           select 1 from normative_rule_confirmation_revocations r
            where r.confirmation_id = c.id
         )
   group by c.country_code, c.standard_family, c.part, c.rule_id,
            c.stack_digest, c.normative_spec_digest, c.implementation_digest,
            c.evidence_digest, c.annex_edition;

revoke all on normative_rule_confirmation_status from public;
grant select on normative_rule_confirmation_status
  to authenticated, normative_backend, normative_governance;

comment on view normative_rule_confirmation_status is
  'Statut normatif necessaire au calcul, sans aucune donnee personnelle. '
  'Ouvrir les tables completes exposerait noms, declarations et pages lues; '
  'la provenance detaillee, si elle doit etre affichee un jour, passera par '
  'une vue dediee dont le contenu personnel aura ete decide explicitement.';


-- =====================================================================
-- Fonctions SECURITY DEFINER: aucun droit pour PUBLIC
-- =====================================================================
-- Une fonction SECURITY DEFINER s'execute avec les droits de son
-- proprietaire. Laisser EXECUTE a PUBLIC reviendrait a offrir ces droits a
-- tout le monde. Les fonctions de declencheur n'ont besoin d'aucun EXECUTE
-- pour etre appelees par leur trigger: le revocation est donc sans effet de
-- bord.
--
-- `search_path` est fixe explicitement sur chacune (public, pg_temp, dans cet
-- ordre): pg_temp en DERNIER, si bien qu'une table temporaire creee par
-- l'appelant ne peut pas masquer une table de `public`.
revoke all on function log_normative_event(text, text, uuid, jsonb, uuid)
  from public;
revoke all on function check_normative_grant() from public;
revoke all on function check_normative_grant_revocation() from public;
revoke all on function check_normative_confirmation() from public;
revoke all on function check_normative_confirmation_revocation() from public;
revoke all on function forbid_normative_audit_mutation() from public;

-- Les auxiliaires ne sont pas SECURITY DEFINER, mais ils LISENT la
-- gouvernance: `resolve_normative_authorisation` dirait a n'importe qui de
-- quelles habilitations dispose n'importe qui d'autre. La RLS ne protege pas
-- une fonction, seulement une table.
revoke all on function resolve_normative_authorisation(
  uuid, normative_permission, country_code, text, text, text) from public;
revoke all on function normative_grant_is_active(uuid) from public;
revoke all on function normative_authorisation_snapshot(
  normative_authorisation_grants) from public;
revoke all on function assert_digest_integrity(text, text, text, text)
  from public;

commit;
