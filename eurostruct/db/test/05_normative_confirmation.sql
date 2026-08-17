-- =====================================================================
-- EUROSTRUCT — 0010: garanties de la confirmation normative
--
-- Ce que ces tests protegent, et pourquoi c'est plus etroit que 0009:
-- une signature de projet engage UNE etude; une confirmation du referentiel
-- engage TOUTES les etudes de la juridiction, sur tous les locataires, d'un
-- seul coup.
--
-- Toutes les identites sont FICTIVES et portent « FICTIF » en toutes lettres.
-- Aucune confirmation reelle n'est creee: les regles confirmees ici sont des
-- identifiants de test, jamais celles du referentiel belge.
--
-- Suppose 01_guarantees.sql applique (alice, bob, carla existent).
-- =====================================================================

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------
-- 24. PostgreSQL 16
-- ---------------------------------------------------------------------
do $$
begin
  if current_setting('server_version_num')::int < 160000 then
    raise exception
      'ces garanties ciblent PostgreSQL 16 (version courante: %)',
      current_setting('server_version');
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 3. La migration ne cree AUCUNE donnee reelle
-- ---------------------------------------------------------------------
-- Verifie AVANT toute insertion de test: une migration qui installerait un
-- administrateur ou un vercateur cablerait une racine de confiance que
-- personne n'aurait decidee.
do $$
declare n bigint;
begin
  select count(*) into n from normative_authorisation_grants;
  if n <> 0 then
    raise exception 'la migration a cree % octroi(s)', n;
  end if;
  select count(*) into n from normative_authorisation_revocations;
  if n <> 0 then
    raise exception 'la migration a cree % revocation(s) d''octroi', n;
  end if;
  select count(*) into n from normative_rule_confirmations;
  if n <> 0 then
    raise exception 'la migration a cree % confirmation(s)', n;
  end if;
  select count(*) into n from normative_rule_confirmation_revocations;
  if n <> 0 then
    raise exception 'la migration a cree % revocation(s) de confirmation', n;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 22. Aucune colonne project_id ni org_id
-- ---------------------------------------------------------------------
-- Structurel, et non « on n'en a pas mis »: un rattachement client ferait
-- glisser une lecture d'annexe vers un engagement professionnel sur une etude.
do $$
declare fautive text;
begin
  select format('%s.%s', table_name, column_name) into fautive
    from information_schema.columns
   where table_schema = 'public'
     and table_name in ('normative_authorisation_grants',
                        'normative_authorisation_revocations',
                        'normative_rule_confirmations',
                        'normative_rule_confirmation_revocations')
     and column_name in ('project_id', 'org_id', 'organization_id',
                         'tenant_id', 'client_id')
   limit 1;
  if fautive is not null then
    raise exception
      'colonne de rattachement client trouvee: %. La lecture d''une annexe '
      'est vraie pour tous les projets de la juridiction ou pour aucun.',
      fautive;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- Aucune colonne d'etat mutee sur la ligne d'origine
-- ---------------------------------------------------------------------
do $$
declare fautive text;
begin
  select format('%s.%s', table_name, column_name) into fautive
    from information_schema.columns
   where table_schema = 'public'
     and table_name in ('normative_authorisation_grants',
                        'normative_rule_confirmations')
     and column_name in ('is_active', 'is_revoked', 'revoked_at', 'revoked_by',
                         'active', 'status')
   limit 1;
  if fautive is not null then
    raise exception
      'colonne d''etat mutable trouvee: %. Un booleen mute rend '
      'indistinguables « jamais revoque » et « revoque puis remis ».', fautive;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- Acteurs fictifs
-- ---------------------------------------------------------------------
insert into auth.users (id, email) values
  ('44444444-4444-4444-4444-444444444444', 'FICTIF-admin@eurostruct.test'),
  ('55555555-5555-5555-5555-555555555555', 'FICTIF-verif-1@eurostruct.test'),
  ('66666666-6666-6666-6666-666666666666', 'FICTIF-verif-2@eurostruct.test'),
  ('77777777-7777-7777-7777-777777777777', 'FICTIF-revoc@eurostruct.test'),
  ('88888888-8888-8888-8888-888888888888', 'FICTIF-inconnu@eurostruct.test');


-- ---------------------------------------------------------------------
-- Fabrique de confirmations: payloads et empreintes COHERENTS par defaut
-- ---------------------------------------------------------------------
-- Les empreintes sont calculees depuis les payloads, si bien qu'un test qui
-- reussit ne peut pas reussir grace a un hash faux. Les parametres p_faux_*
-- servent uniquement aux tests negatifs.
create or replace function t_confirmer(
  p_rule           text default 'test.regle.fictive',
  p_country        country_code default 'BE',
  p_family         text default 'EN 1992',
  p_part           text default '1-1',
  p_edition_annexe text default '2010',
  p_idem           text default null,
  p_algo           text default 'sha256',
  p_faux_digest    boolean default false,
  p_pretend_verif  uuid default null,
  p_pretend_time   timestamptz default null,
  p_pretend_grant  uuid default null,
  p_pretend_scope  jsonb default null
) returns uuid
language plpgsql as $$
declare
  spec text; impl text; ev text; pile text;
  snapshot jsonb;
  nouvel_id uuid;
  h text;
begin
  spec := format('{"kind":"normative_spec","rule_id":"%s"}', p_rule);
  impl := format('{"kind":"implementation","rule_id":"%s"}', p_rule);
  -- La cle d'idempotence n'entre PAS dans le dossier de preuve: deux envois
  -- d'une meme lecture doivent produire le MEME sujet, sans quoi le test du
  -- decompte a quatre yeux ne verifierait rien.
  ev   := format('{"kind":"evidence","rule_id":"%s"}', p_rule);
  snapshot := jsonb_build_object(
    'schema_version', 'esc-stack/1',
    'country_code', p_country, 'standard_family', p_family, 'part', p_part,
    'components', jsonb_build_array(
      jsonb_build_object('role', 'base', 'reference', 'FICTIF EN 1992-1-1',
                         'edition', '2004', 'application_order', 1,
                         'document_digest', repeat('a', 64)),
      jsonb_build_object('role', 'annexe', 'reference', 'FICTIF ANB',
                         'edition', p_edition_annexe, 'application_order', 2,
                         'document_digest', repeat('b', 64))));
  pile := snapshot::text;
  h := encode(sha256(convert_to(spec, 'UTF8')), 'hex');
  if p_faux_digest then
    h := repeat('0', 64);
  end if;

  insert into normative_rule_confirmations (
    country_code, standard_family, part, rule_id,
    stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
    digest_algorithm, canonicalization_version,
    normative_spec_payload, implementation_payload, evidence_payload,
    stack_payload, stack_snapshot, annex_edition,
    evidence_items, statement,
    verifier_id, verifier_name, verified_at,
    authorisation_grant_id, authorisation_scope, idempotency_key
  ) values (
    p_country, p_family, p_part, p_rule,
    encode(sha256(convert_to(pile, 'UTF8')), 'hex'),
    h,
    encode(sha256(convert_to(impl, 'UTF8')), 'hex'),
    encode(sha256(convert_to(ev, 'UTF8')), 'hex'),
    p_algo, 'esc-canon/1',
    spec, impl, ev, pile, snapshot,
    -- Valeur volontairement fausse: le serveur doit l'ecraser depuis la pile.
    'EDITION-FOURNIE-PAR-LE-CLIENT',
    jsonb_build_array(jsonb_build_object(
      'document_digest', repeat('b', 64), 'document_role', 'annexe',
      'clause', '§9.2.2(5)', 'page_printed', 15,
      'quote', 'FICTIF — citation de test, sans valeur normative.')),
    'FICTIF — j''ai lu l''annexe a la page indiquee.',
    -- Identite, horodatage et snapshot PRETENDUS: le serveur doit les ecraser.
    coalesce(p_pretend_verif, '88888888-8888-8888-8888-888888888888'),
    'FICTIF Relecteur',
    coalesce(p_pretend_time, timestamptz '1999-01-01 00:00:00+00'),
    p_pretend_grant,
    coalesce(p_pretend_scope, '{"falsifie": true}'::jsonb),
    coalesce(p_idem, gen_random_uuid()::text)
  ) returning id into nouvel_id;
  return nouvel_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 4. Amorcage initial reussi
-- ---------------------------------------------------------------------
do $$
declare g record; n bigint;
begin
  perform bootstrap_normative_administrator(
    '44444444-4444-4444-4444-444444444444',
    'FICTIF — amorcage de la chaine de confiance normative.');

  select * into g from normative_authorisation_grants
   where grantee_id = '44444444-4444-4444-4444-444444444444';
  if g.permission <> 'can_manage_normative_authorisations' then
    raise exception 'l''amorcage a accorde « % »', g.permission;
  end if;
  if g.origin <> 'bootstrap' then
    raise exception 'origine attendue bootstrap, obtenue %', g.origin;
  end if;
  if g.granted_by is not null then
    raise exception
      'l''amorcage ne doit avoir aucun octroyant: aucun administrateur '
      'n''existe encore a ce moment';
  end if;

  -- 23a. Audit d'amorcage
  select count(*) into n from audit_log
   where action = 'normative_authorisation.bootstrap' and entity_id = g.id;
  if n <> 1 then
    raise exception 'audit d''amorcage absent (% lignes)', n;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 5. Un second amorcage est refuse
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  begin
    perform bootstrap_normative_administrator(
      '77777777-7777-7777-7777-777777777777', 'FICTIF — seconde tentative.');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un second amorcage a reussi: la racine de confiance serait '
      'reouvrable a volonte';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6. L'administrateur ne peut pas s'accorder le droit de verifier
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, permission, country_code, standard_family, part, reason)
    values ('44444444-4444-4444-4444-444444444444',
            'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
            'FICTIF — auto-attribution');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'auto-attribution acceptee: l''administrateur initial pourrait '
      'confirmer seul tout le referentiel d''une juridiction';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 7. L'administrateur ne peut pas confirmer sans droit distinct
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    perform t_confirmer(p_idem => 'FICTIF-admin-tente');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'l''administrateur a confirme une regle: gerer les habilitations et '
      'lire une annexe seraient alors le meme pouvoir';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- Octrois: l'administrateur habilite deux verificateurs et un revocateur
-- ---------------------------------------------------------------------
do $$
declare n bigint;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);

  insert into normative_authorisation_grants
    (id, grantee_id, permission, country_code, standard_family, part, reason)
  values ('9a000000-0000-0000-0000-000000000001',
          '55555555-5555-5555-5555-555555555555',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
          'FICTIF — relecture EC2 belge partie 1-1');

  -- Portee restreinte a UNE edition: sert au test 9.
  insert into normative_authorisation_grants
    (id, grantee_id, permission, country_code, standard_family, part, edition,
     reason)
  values ('9a000000-0000-0000-0000-000000000002',
          '66666666-6666-6666-6666-666666666666',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1', '2010',
          'FICTIF — relecture EC2 belge, edition 2010 uniquement');

  insert into normative_authorisation_grants
    (id, grantee_id, permission, country_code, standard_family, part, reason)
  values ('9a000000-0000-0000-0000-000000000003',
          '77777777-7777-7777-7777-777777777777',
          'can_revoke_normative_confirmation', 'BE', 'EN 1992', '1-1',
          'FICTIF — retrait de confirmations EC2 belge');

  -- 23b. Audit d'octroi
  select count(*) into n from audit_log
   where action = 'normative_authorisation.granted';
  if n <> 3 then
    raise exception 'audit d''octroi: 3 attendus, % trouves', n;
  end if;
end
$$;

-- Un octroi de verification sans portee explicite est refuse par la table.
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, permission, reason)
    values ('55555555-5555-5555-5555-555555555555',
            'can_validate_normative_reference', 'FICTIF — portee absente');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un droit de verification global implicite a ete accepte: un relecteur '
      'habilite sur l''EC2 belge le serait sur l''EC8 espagnol';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 8. Confirmation dans le perimetre exact
-- 11. Identite et horodatage imposes par le serveur
-- 12. Snapshot d'autorisation impose par le serveur
-- 13. Falsification du snapshot ecrasee
-- ---------------------------------------------------------------------
do $$
declare c record; avant timestamptz; n bigint;
begin
  avant := now();
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  -- La fabrique PRETEND etre quelqu'un d'autre, a une autre date, sous une
  -- autre habilitation. Le serveur doit tout ecraser.
  perform t_confirmer(
    p_idem => 'FICTIF-idem-1',
    p_pretend_verif => '88888888-8888-8888-8888-888888888888',
    p_pretend_time  => timestamptz '1999-01-01 00:00:00+00',
    p_pretend_grant => '9a000000-0000-0000-0000-000000000003',
    p_pretend_scope => '{"permission":"tout","falsifie":true}'::jsonb);

  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';

  if c.verifier_id <> '55555555-5555-5555-5555-555555555555' then
    raise exception
      'identite non imposee par le serveur: % stockee alors que la session '
      'etait celle du verificateur 1', c.verifier_id;
  end if;
  if c.verified_at < avant then
    raise exception
      'horodatage non impose par le serveur: % stocke, or l''insertion est '
      'posterieure a %', c.verified_at, avant;
  end if;
  if c.authorisation_grant_id <> '9a000000-0000-0000-0000-000000000001' then
    raise exception
      'snapshot d''autorisation non resolu par le serveur: % stocke',
      c.authorisation_grant_id;
  end if;
  if c.authorisation_scope ? 'falsifie' then
    raise exception
      'le snapshot fourni par le client a survecu: un acteur pourrait se '
      'declarer lui-meme autorise';
  end if;
  if c.authorisation_scope ->> 'permission'
     <> 'can_validate_normative_reference' then
    raise exception 'snapshot incoherent: %', c.authorisation_scope;
  end if;
  -- L'edition est extraite de la pile, pas recue du client.
  if c.annex_edition <> '2010' then
    raise exception
      'edition d''annexe non extraite de la pile: % stockee', c.annex_edition;
  end if;

  -- 23c. Audit de confirmation
  select count(*) into n from audit_log
   where action = 'normative_confirmation.created' and entity_id = c.id;
  if n <> 1 then
    raise exception 'audit de confirmation absent (% lignes)', n;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 9. Refus hors pays, norme, partie ou edition
-- ---------------------------------------------------------------------
do $$
declare ok boolean;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  -- Autre pays
  ok := false;
  begin
    perform t_confirmer(p_country => 'FR', p_idem => 'FICTIF-hors-pays');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then raise exception 'confirmation acceptee hors du pays habilite'; end if;

  -- Autre famille de norme
  ok := false;
  begin
    perform t_confirmer(p_family => 'EN 1993', p_idem => 'FICTIF-hors-norme');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then raise exception 'confirmation acceptee hors de la norme habilitee'; end if;

  -- Autre partie
  ok := false;
  begin
    perform t_confirmer(p_part => '1-2', p_idem => 'FICTIF-hors-partie');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then raise exception 'confirmation acceptee hors de la partie habilitee'; end if;

  -- Autre edition, pour le verificateur dont l'octroi est limite a 2010
  perform set_config('request.jwt.claim.sub',
                     '66666666-6666-6666-6666-666666666666', true);
  ok := false;
  begin
    perform t_confirmer(p_edition_annexe => '2018',
                        p_idem => 'FICTIF-hors-edition');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'confirmation acceptee sur l''edition 2018 alors que l''habilitation '
      'porte sur 2010: une relecture de 2010 ne dit rien de 2018';
  end if;

  -- ... et la meme personne, sur SON edition, est acceptee.
  perform t_confirmer(p_edition_annexe => '2010', p_idem => 'FICTIF-idem-2');
end
$$;


-- ---------------------------------------------------------------------
-- 14. Digest incorrect refuse
-- 15. Algorithme inconnu refuse
-- ---------------------------------------------------------------------
do $$
declare ok boolean;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  ok := false;
  begin
    perform t_confirmer(p_faux_digest => true, p_idem => 'FICTIF-faux-hash');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un digest ne resumant pas son payload a ete accepte: une ligne '
      'immuable ecrite avec un faux hash reste fausse';
  end if;

  ok := false;
  begin
    perform t_confirmer(p_algo => 'md5', p_idem => 'FICTIF-md5');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'un algorithme inconnu a ete accepte: la garantie dependrait du nom '
      'donne a l''algorithme';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 21. Idempotence technique
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  begin
    perform t_confirmer(p_idem => 'FICTIF-idem-1', p_rule => 'test.autre.regle');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception 'une cle d''idempotence rejouee a cree une seconde ligne';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 10. Refus apres revocation de l'autorisation
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; n bigint;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_revocations (grant_id, reason)
  values ('9a000000-0000-0000-0000-000000000002',
          'FICTIF — fin de mission du relecteur 2.');

  -- 23d. Audit de revocation d'octroi
  select count(*) into n from audit_log
   where action = 'normative_authorisation.revoked';
  if n <> 1 then
    raise exception 'audit de revocation d''octroi absent (% lignes)', n;
  end if;

  -- L'octroi retire N'A PAS ete modifie: il reste lisible tel qu'il etait.
  perform 1 from normative_authorisation_grants
   where id = '9a000000-0000-0000-0000-000000000002';
  if not found then
    raise exception 'l''octroi revoque a disparu: la trace serait perdue';
  end if;
  if normative_grant_is_active('9a000000-0000-0000-0000-000000000002') then
    raise exception 'l''octroi revoque est encore actif';
  end if;

  perform set_config('request.jwt.claim.sub',
                     '66666666-6666-6666-6666-666666666666', true);
  begin
    perform t_confirmer(p_idem => 'FICTIF-apres-revocation');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'confirmation acceptee apres revocation de l''habilitation';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 18. Revocation d'autrui refusee sans droit dedie
-- ---------------------------------------------------------------------
do $$
declare cible uuid; ok boolean;
begin
  select id into cible from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';

  -- L'administrateur des habilitations n'a PAS ce pouvoir. C'est le coeur de
  -- la separation: distribuer des habilitations et defaire le travail d'un
  -- relecteur sont deux choses.
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  ok := false;
  begin
    insert into normative_rule_confirmation_revocations
      (confirmation_id, revoked_by, revoked_by_name, revoked_at,
       authorisation_scope, reason)
    values (cible, '44444444-4444-4444-4444-444444444444', 'FICTIF Admin',
            now(), '{}'::jsonb, 'FICTIF — tentative administrative.');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'l''administrateur a revoque la confirmation d''un autre sans detenir '
      '« can_revoke_normative_confirmation »';
  end if;

  -- Un autre verificateur non plus.
  perform set_config('request.jwt.claim.sub',
                     '66666666-6666-6666-6666-666666666666', true);
  ok := false;
  begin
    insert into normative_rule_confirmation_revocations
      (confirmation_id, revoked_by, revoked_by_name, revoked_at,
       authorisation_scope, reason)
    values (cible, '66666666-6666-6666-6666-666666666666', 'FICTIF Verif 2',
            now(), '{}'::jsonb, 'FICTIF — tentative entre pairs.');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'un verificateur a revoque la confirmation d''un autre sans droit dedie';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 17. Auto-revocation motivee
-- ---------------------------------------------------------------------
do $$
declare cible uuid; r record; ok boolean := false; n bigint;
begin
  perform set_config('request.jwt.claim.sub',
                     '66666666-6666-6666-6666-666666666666', true);
  select id into cible from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-2';

  -- Sans motif: refuse.
  begin
    insert into normative_rule_confirmation_revocations
      (confirmation_id, revoked_by, revoked_by_name, revoked_at,
       authorisation_scope, reason)
    values (cible, '66666666-6666-6666-6666-666666666666', 'FICTIF Verif 2',
            now(), '{}'::jsonb, '   ');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'revocation sans motif acceptee: elle ne se distinguerait pas d''une '
      'fausse manoeuvre';
  end if;

  -- Avec motif: acceptee, meme sans aucune habilitation de revocation.
  insert into normative_rule_confirmation_revocations
    (confirmation_id, revoked_by, revoked_by_name, revoked_at,
     authorisation_scope, reason)
  values (cible, '88888888-8888-8888-8888-888888888888', 'FICTIF Verif 2',
          timestamptz '1999-01-01', '{"falsifie": true}'::jsonb,
          'FICTIF — relecture ulterieure: page erronee.');

  select * into r from normative_rule_confirmation_revocations
   where confirmation_id = cible;
  if r.revoked_by <> '66666666-6666-6666-6666-666666666666' then
    raise exception 'auteur de la revocation non impose par le serveur: %',
      r.revoked_by;
  end if;
  if r.revoked_at < timestamptz '2000-01-01' then
    raise exception 'horodatage de revocation non impose par le serveur: %',
      r.revoked_at;
  end if;
  if r.authorisation_grant_id is not null then
    raise exception
      'une auto-revocation ne doit consommer aucune habilitation, or % est '
      'referencee', r.authorisation_grant_id;
  end if;
  if not (r.authorisation_scope ? 'self_revocation') then
    raise exception 'snapshot d''auto-revocation absent: %',
      r.authorisation_scope;
  end if;

  -- La confirmation revoquee reste lisible, a l'identique.
  perform 1 from normative_rule_confirmations where id = cible;
  if not found then
    raise exception 'la confirmation revoquee a disparu';
  end if;

  select count(*) into n from audit_log
   where action = 'normative_confirmation.revoked' and entity_id = r.id;
  if n <> 1 then
    raise exception 'audit de revocation de confirmation absent';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 19. Revocation d'autrui autorisee avec le droit dedie
-- 20. Seconde revocation refusee
-- ---------------------------------------------------------------------
do $$
declare cible uuid; r record; ok boolean := false;
begin
  select id into cible from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';

  perform set_config('request.jwt.claim.sub',
                     '77777777-7777-7777-7777-777777777777', true);
  insert into normative_rule_confirmation_revocations
    (confirmation_id, revoked_by, revoked_by_name, revoked_at,
     authorisation_scope, reason)
  values (cible, '88888888-8888-8888-8888-888888888888', 'FICTIF Revocateur',
          now(), '{}'::jsonb, 'FICTIF — clause mal transcrite.');

  select * into r from normative_rule_confirmation_revocations
   where confirmation_id = cible;
  if r.authorisation_grant_id <> '9a000000-0000-0000-0000-000000000003' then
    raise exception
      'la revocation d''autrui doit consommer l''habilitation dediee, or % '
      'est referencee', r.authorisation_grant_id;
  end if;

  -- Une seconde revocation de la meme confirmation est refusee.
  begin
    insert into normative_rule_confirmation_revocations
      (confirmation_id, revoked_by, revoked_by_name, revoked_at,
       authorisation_scope, reason)
    values (cible, '77777777-7777-7777-7777-777777777777', 'FICTIF Revocateur',
            now(), '{}'::jsonb, 'FICTIF — seconde tentative.');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'une confirmation a recu deux revocations: laquelle ferait foi ?';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 16. UPDATE et DELETE refuses sur tous les evenements
-- ---------------------------------------------------------------------
do $$
declare
  t text;
  ok boolean;
  tables text[] := array[
    'normative_authorisation_grants',
    'normative_authorisation_revocations',
    'normative_rule_confirmations',
    'normative_rule_confirmation_revocations',
    'audit_log'
  ];
begin
  foreach t in array tables loop
    ok := false;
    begin
      execute format('update %I set id = id', t);
    exception
      when restrict_violation then ok := true;
      when others then
        -- Les colonnes different d'une table a l'autre; seul le refus compte.
        if sqlstate = '0A000' or sqlerrm like '%immuable%' then
          ok := true;
        else
          raise;
        end if;
    end;
    if not ok then
      raise exception 'UPDATE accepte sur %', t;
    end if;

    ok := false;
    begin
      execute format('delete from %I', t);
    exception when restrict_violation then ok := true;
    end;
    if not ok then
      raise exception 'DELETE accepte sur %', t;
    end if;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- Le decompte a quatre yeux ne connait pas la cle d'idempotence
-- ---------------------------------------------------------------------
-- Deux verificateurs DISTINCTS sur le meme sujet: deux regards. La cle
-- technique n'entre pas dans l'index d'unicite du sujet, et le meme
-- verificateur ne peut pas signer deux fois le meme sujet.
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  perform t_confirmer(p_rule => 'test.quatre.yeux', p_idem => 'FICTIF-4y-a');
  begin
    -- Meme personne, meme sujet, autre cle d'idempotence: refuse.
    perform t_confirmer(p_rule => 'test.quatre.yeux', p_idem => 'FICTIF-4y-b');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'le meme verificateur a signe deux fois le meme sujet: le controle a '
      'quatre yeux serait contournable par un simple second envoi';
  end if;
end
$$;


drop function t_confirmer(text, country_code, text, text, text, text, text,
                          boolean, uuid, timestamptz, uuid, jsonb);

\echo ''
\echo '================================================='
\echo ' Confirmation normative: autorisations, immuabilite et'
\echo ' integrite des empreintes verifiees.'
\echo '================================================='
