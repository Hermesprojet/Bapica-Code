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

-- La MEME personne ne signe pas deux fois le MEME sujet. Deux personnes le
-- peuvent: c'est tout l'objet du controle a quatre yeux, et c'est pourquoi
-- l'index porte sur le sujet ET le verificateur.
--
-- L'index ne connait pas les revocations. Une confirmation retiree conserve
-- donc sa place, et le meme verificateur ne peut pas re-signer le meme sujet
-- apres retrait. C'est voulu: re-signer apres un retrait motive demanderait
-- une decision explicite, pas un simple re-envoi.
create unique index normative_confirmation_one_per_verifier
  on normative_rule_confirmations
     (rule_id, country_code, standard_family, part, stack_digest,
      normative_spec_digest, implementation_digest, evidence_digest,
      verifier_id);

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
create or replace function resolve_normative_authorisation(
  p_user       uuid,
  p_permission normative_permission,
  p_country    country_code,
  p_family     text,
  p_part       text,
  p_edition    text
) returns normative_authorisation_grants
language sql
stable
as $$
  select g.*
    from normative_authorisation_grants g
   where g.grantee_id = p_user
     and g.permission = p_permission
     and (g.country_code    is null or g.country_code    = p_country)
     and (g.standard_family is null or g.standard_family = p_family)
     and (g.part            is null or g.part            = p_part)
     and (g.edition         is null or g.edition         = p_edition)
     and normative_grant_is_active(g.id)
   -- La plus SPECIFIQUE d'abord: si quelqu'un detient a la fois une portee
   -- large et une portee etroite, c'est la etroite qui doit apparaitre au
   -- snapshot d'audit — elle decrit mieux ce sur quoi il a agi.
   order by (g.country_code    is not null)::int
          + (g.standard_family is not null)::int
          + (g.part            is not null)::int
          + (g.edition         is not null)::int desc,
            g.granted_at desc
   limit 1;
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
  p_grantee uuid,
  p_reason  text
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  nouvel_id uuid;
  proprietaire text;
begin
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

  insert into normative_authorisation_grants
    (grantee_id, permission, granted_by, origin, reason)
  values
    (p_grantee, 'can_manage_normative_authorisations', null, 'bootstrap',
     p_reason)
  returning id into nouvel_id;

  perform log_normative_event(
    'normative_authorisation.bootstrap',
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

revoke all on function bootstrap_normative_administrator(uuid, text) from public;

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
    'normative_authorisation.granted',
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
    'normative_authorisation.revoked',
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

  perform log_normative_event(
    'normative_confirmation.created',
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
  end if;

  perform log_normative_event(
    'normative_confirmation.revoked',
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

-- Le journal d'audit lui-meme. Un journal reecrivable n'est pas un journal:
-- la trace d'amorcage et celle d'un octroi doivent survivre a celui qui les a
-- provoquees. Aucune migration n'ecrivait d'UPDATE ou de DELETE dessus.
create trigger audit_log_is_immutable
  before update or delete on audit_log
  for each row execute function forbid_mutation();


-- =====================================================================
-- RLS: referentiel global, comme national_annex_parameters (0002)
-- =====================================================================
alter table normative_authorisation_grants        enable row level security;
alter table normative_authorisation_revocations   enable row level security;
alter table normative_rule_confirmations          enable row level security;
alter table normative_rule_confirmation_revocations enable row level security;

-- Lecture pour tout utilisateur authentifie: qui a confirme quoi, et sous
-- quelle habilitation, doit etre verifiable par ceux qui s'appuient dessus.
create policy normative_grants_read on normative_authorisation_grants
  for select to authenticated using (true);
create policy normative_grant_revocations_read
  on normative_authorisation_revocations
  for select to authenticated using (true);
create policy normative_confirmations_read on normative_rule_confirmations
  for select to authenticated using (true);
create policy normative_confirmation_revocations_read
  on normative_rule_confirmation_revocations
  for select to authenticated using (true);

-- Ecriture: ouverte a l'utilisateur authentifie, et entierement gouvernee par
-- les triggers ci-dessus. Les triggers BEFORE INSERT s'executent quel que soit
-- le chemin d'acces — un acces direct a la table ne les contourne pas, la ou
-- une regle posee dans la seule couche applicative se contournerait.
create policy normative_grants_insert on normative_authorisation_grants
  for insert to authenticated with check (true);
create policy normative_grant_revocations_insert
  on normative_authorisation_revocations
  for insert to authenticated with check (true);
create policy normative_confirmations_insert on normative_rule_confirmations
  for insert to authenticated with check (true);
create policy normative_confirmation_revocations_insert
  on normative_rule_confirmation_revocations
  for insert to authenticated with check (true);

-- Aucune policy UPDATE ni DELETE n'est creee: absente, l'operation est
-- refusee par la RLS, et les declencheurs d'immuabilite la refusent aussi
-- pour les chemins qui contournent la RLS. Deux garde-fous, deux portees.

commit;
