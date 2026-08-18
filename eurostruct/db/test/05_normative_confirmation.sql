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
create or replace function t_paquet(
  p_rule           text default 'test.regle.fictive',
  p_country        country_code default 'BE',
  p_family         text default 'EN 1992',
  p_part           text default '1-1',
  p_edition_annexe text default '2010'
) returns jsonb
language sql immutable as $$
  -- Les QUATRE payloads canoniques d'un meme paquet de revue, de la forme
  -- exacte que produit `eurostruct_engine.ndp.canonical` (verifiee cote
  -- Python avant d'ecrire ces controles): chacun porte son `kind`, les trois
  -- qui en ont une portent la meme `canonicalization_version`, spec et
  -- implementation nomment la meme regle, et la pile nomme la juridiction.
  select jsonb_build_object(
    'spec', format(
      '{"canonicalization_version":"esc-canon/1","kind":"normative_spec","rule_id":"%s"}',
      p_rule),
    'impl', format(
      '{"canonicalization_version":"esc-canon/1","kind":"implementation","rule_id":"%s"}',
      p_rule),
    -- Le quote_digest doit REELLEMENT resumer la citation: le serveur le
    -- verifie, et une valeur inventee ferait passer le test pour une
    -- mauvaise raison.
    'ev', format(
      '{"canonicalization_version":"esc-canon/1","items":[{"clause":"§9.2.2(5)",'
      '"document_digest":"%s","document_role":"annexe","edition":"2010",'
      '"page_printed":15,"quote":"FICTIF — citation de test.",'
      '"reference":"FICTIF ANB","quote_digest":"%s"}],"kind":"evidence"}',
      repeat('b', 64),
      encode(sha256(convert_to('FICTIF — citation de test.', 'UTF8')), 'hex')),
    'stack', format(
      '{"components":[{"application_order":1,"document_digest":"%s",'
      '"edition":"2004","reference":"FICTIF EN 1992-1-1","role":"base"},'
      '{"application_order":2,"document_digest":"%s","edition":"%s",'
      '"reference":"FICTIF ANB","role":"annexe"}],"country_code":"%s",'
      '"kind":"normative_stack","part":"%s","schema_version":"esc-stack/1",'
      '"standard_family":"%s"}',
      repeat('a', 64), repeat('b', 64), p_edition_annexe, p_country, p_part,
      p_family)
  );
$$;


-- Fabrique de confirmations. Les empreintes sont calculees depuis les
-- payloads, si bien qu'un test qui reussit ne peut pas reussir grace a un
-- hash faux. Les parametres p_faux_* et p_pretend_* servent aux tests
-- negatifs: le serveur doit les ecraser ou les refuser.
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
  p_pretend_scope  jsonb default null,
  -- Substitutions APRES calcul des empreintes: c'est ce que la coherence
  -- atomique doit refuser.
  p_sub_stack_json jsonb default null,
  p_sub_items      jsonb default null,
  p_sub_rule_col   text default null,
  p_sub_country    country_code default null,
  p_echanger       boolean default false,
  -- Payloads remplaces AVANT calcul des empreintes: l'empreinte reste donc
  -- juste, et ce qui doit refuser est l'invariant STRUCTUREL, pas le controle
  -- d'integrite. Substituer apres coup ferait echouer le test une ligne trop
  -- tot, et l'invariant vise ne serait jamais atteint.
  p_ev_payload     text default null,
  p_stack_payload  text default null
) returns uuid
language plpgsql as $$
declare
  paq jsonb; spec text; impl text; ev text; pile text;
  nouvel_id uuid; h text;
begin
  paq  := t_paquet(p_rule, p_country, p_family, p_part, p_edition_annexe);
  spec := paq ->> 'spec';
  impl := paq ->> 'impl';
  ev   := coalesce(p_ev_payload, paq ->> 'ev');
  pile := coalesce(p_stack_payload, paq ->> 'stack');

  if p_echanger then
    -- Specification et implementation interverties: deux empreintes justes
    -- decrivant le mauvais objet.
    select impl, spec into spec, impl;
  end if;

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
    verifier_id, verifier_name, verified_at, created_at,
    authorisation_grant_id, authorisation_scope, idempotency_key
  ) values (
    coalesce(p_sub_country, p_country), p_family, p_part,
    coalesce(p_sub_rule_col, p_rule),
    encode(sha256(convert_to(pile, 'UTF8')), 'hex'),
    h,
    encode(sha256(convert_to(impl, 'UTF8')), 'hex'),
    encode(sha256(convert_to(ev, 'UTF8')), 'hex'),
    p_algo, 'esc-canon/1',
    spec, impl, ev, pile,
    -- Projections jsonb VOLONTAIREMENT divergentes par defaut: le serveur
    -- doit les recalculer depuis les payloads.
    coalesce(p_sub_stack_json, '{"substitue": "par le client"}'::jsonb),
    'EDITION-FOURNIE-PAR-LE-CLIENT',
    coalesce(p_sub_items, '[{"substitue": "par le client"}]'::jsonb),
    'FICTIF — j''ai lu l''annexe a la page indiquee.',
    coalesce(p_pretend_verif, '88888888-8888-8888-8888-888888888888'),
    'FICTIF NOM USURPE PAR LE CLIENT',
    coalesce(p_pretend_time, timestamptz '1999-01-01 00:00:00+00'),
    timestamptz '1999-01-01 00:00:00+00',
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
    'FICTIF Administrateur Racine',
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
   where action = 'normative.authorisation.bootstrap' and entity_id = g.id;
  if n <> 1 then
    raise exception 'audit d''amorcage absent (% lignes)', n;
  end if;

  -- 6.3b4 #6 — QUI a ouvert la racine de confiance.
  --
  -- `current_user` vaut TOUJOURS le role d'autorite a l'interieur d'une
  -- fonction SECURITY DEFINER: il prouve le chemin emprunte, il ne nomme
  -- personne. L'audit de l'evenement le plus sensible de toute la chaine
  -- etait donc anonyme. `session_user`, que SECURITY DEFINER ne modifie pas,
  -- nomme le role reellement connecte.
  declare charge jsonb;
  begin
    select payload into charge from audit_log
     where action = 'normative.authorisation.bootstrap' and entity_id = g.id;

    if charge ->> 'performed_by_session_user' is null then
      raise exception
        'l''audit d''amorcage ne porte pas session_user: on saurait que la '
        'racine a ete ouverte, jamais par qui';
    end if;
    if charge ->> 'performed_by_session_user' <> session_user then
      raise exception
        'session_user inscrit « % » alors que la session est « % »',
        charge ->> 'performed_by_session_user', session_user;
    end if;

    -- Et les deux doivent rester DISTINCTS dans leur role: current_user
    -- designe l'autorite, session_user l'appelant. Les confondre reviendrait
    -- a perdre l'un des deux.
    if charge ->> 'performed_by_db_user' <> 'eurostruct_normative_bootstrap' then
      raise exception
        'current_user inscrit « % »: la fonction d''amorcage ne s''execute '
        'pas sous le role d''autorite, et la branche bootstrap du '
        'declencheur ne prouverait rien',
        charge ->> 'performed_by_db_user';
    end if;
  end;
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
      '77777777-7777-7777-7777-777777777777', 'FICTIF Autre',
      'FICTIF — seconde tentative.');
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
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, reason)
  values ('9a000000-0000-0000-0000-000000000001',
          '55555555-5555-5555-5555-555555555555', 'FICTIF Relecteur Un',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
          'FICTIF — relecture EC2 belge partie 1-1');

  -- Portee restreinte a UNE edition: sert au test 9.
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, edition, reason)
  values ('9a000000-0000-0000-0000-000000000002',
          '66666666-6666-6666-6666-666666666666', 'FICTIF Relecteur Deux',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1', '2010',
          'FICTIF — relecture EC2 belge, edition 2010 uniquement');

  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, reason)
  values ('9a000000-0000-0000-0000-000000000003',
          '77777777-7777-7777-7777-777777777777', 'FICTIF Revocateur',
          'can_revoke_normative_confirmation', 'BE', 'EN 1992', '1-1',
          'FICTIF — retrait de confirmations EC2 belge');

  -- 23b. Audit d'octroi
  select count(*) into n from audit_log
   where action = 'normative.authorisation.granted';
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
      (grantee_id, grantee_name, permission, reason)
    values ('55555555-5555-5555-5555-555555555555', 'FICTIF Relecteur Un',
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
   where action = 'normative.confirmation.created' and entity_id = c.id;
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
   where action = 'normative.authorisation.revoked';
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
   where action = 'normative.confirmation.revoked' and entity_id = r.id;
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
-- 6.3b1 #1 — le nom lisible vient du SERVEUR, jamais du client
-- ---------------------------------------------------------------------
-- `verifier_id` impose ne suffisait pas: une note de calcul n'affiche que le
-- NOM. Un nom libre permettait de signer sous l'identite lisible d'un autre.
do $$
declare c record;
begin
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';

  if c.verifier_name = 'FICTIF NOM USURPE PAR LE CLIENT' then
    raise exception
      'le nom fourni par le client a survecu: on pourrait signer sous '
      'l''identite lisible d''un autre';
  end if;
  if c.verifier_name <> 'FICTIF Relecteur Un' then
    raise exception
      'nom serveur attendu « FICTIF Relecteur Un », obtenu « % »',
      c.verifier_name;
  end if;

  -- Coherence: le nom vient de l'octroi RETENU, lui-meme lie au verifier_id.
  if c.verifier_name <> (select grantee_name from normative_authorisation_grants
                          where id = c.authorisation_grant_id) then
    raise exception 'nom incoherent avec l''octroi resolu';
  end if;
  if c.verifier_id <> (select grantee_id from normative_authorisation_grants
                        where id = c.authorisation_grant_id) then
    raise exception 'l''octroi retenu n''est pas celui du signataire';
  end if;
end
$$;


-- Un changement de nom ulterieur n'altere aucune confirmation historique.
do $$
declare ancien text; apres text;
begin
  select verifier_name into ancien from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';

  -- Le nom se corrige par un NOUVEL octroi: l'octroi est immuable.
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_revocations (grant_id, reason)
  values ('9a000000-0000-0000-0000-000000000001',
          'FICTIF — correction du nom lisible.');
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, reason)
  values ('9a000000-0000-0000-0000-000000000004',
          '55555555-5555-5555-5555-555555555555',
          'FICTIF Relecteur Un (nom corrige)',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
          'FICTIF — nom corrige apres mariage.');

  select verifier_name into apres from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-1';
  if apres <> ancien then
    raise exception
      'une confirmation historique a change de nom: elle atteste ce qui a ete '
      'signe a l''epoque, pas l''etat civil d''aujourd''hui';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #7 — nouvel octroi apres revocation
-- ---------------------------------------------------------------------
-- Deja exerce ci-dessus (l'octroi ...0001 revoque puis ...0004 cree). On
-- verifie que le nouvel octroi est bien celui qui sert desormais.
do $$
declare c record;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  perform t_confirmer(p_rule => 'test.apres.nouvel.octroi',
                      p_idem => 'FICTIF-idem-nouvel-octroi');
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-idem-nouvel-octroi';
  if c.authorisation_grant_id <> '9a000000-0000-0000-0000-000000000004' then
    raise exception
      'le nouvel octroi n''a pas ete retenu: % utilise', c.authorisation_grant_id;
  end if;
  if c.verifier_name <> 'FICTIF Relecteur Un (nom corrige)' then
    raise exception 'le nom du nouvel octroi n''a pas ete repris: %',
      c.verifier_name;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #6 — deux octrois actifs de meme specificite
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);

  -- Portee RIGOUREUSEMENT identique: refuse a la source.
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, country_code, standard_family,
       part, reason)
    values ('55555555-5555-5555-5555-555555555555', 'FICTIF Relecteur Un',
            'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
            'FICTIF — doublon de portee identique');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'deux octrois actifs de portee identique acceptes: le snapshot d''audit '
      'deviendrait indeterminable';
  end if;

  -- Portees DIFFERENTES mais de meme specificite, toutes deux couvrantes:
  -- (BE, EN 1992, *, *) et (BE, *, 1-1, *). Aucune contrainte ne peut les
  -- refuser a l'insertion; c'est la resolution qui doit refuser.
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     reason)
  values ('9a000000-0000-0000-0000-0000000000a1',
          '77777777-7777-7777-7777-777777777777', 'FICTIF Revocateur',
          'can_manage_normative_authorisations', 'BE', 'EN 1992',
          'FICTIF — portee pays+norme');
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, part, reason)
  values ('9a000000-0000-0000-0000-0000000000a2',
          '77777777-7777-7777-7777-777777777777', 'FICTIF Revocateur',
          'can_manage_normative_authorisations', 'BE', '1-1',
          'FICTIF — portee pays+partie');

  ok := false;
  perform set_config('request.jwt.claim.sub',
                     '77777777-7777-7777-7777-777777777777', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, country_code, standard_family,
       part, reason)
    values ('88888888-8888-8888-8888-888888888888', 'FICTIF Inconnu',
            'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
            'FICTIF — octroi sous habilitation ambigue');
  exception when cardinality_violation then ok := true;
  end;
  if not ok then
    raise exception
      'une habilitation ambigue a ete tranchee en silence: le snapshot '
      'd''audit ne dirait pas sous quel octroi l''acteur a agi';
  end if;

  -- Lever l'ambiguite en revoquant l'un des deux: la resolution redevient
  -- possible, sans aucune colonne mutable.
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_revocations (grant_id, reason)
  values ('9a000000-0000-0000-0000-0000000000a2',
          'FICTIF — portee redondante retiree.');

  perform set_config('request.jwt.claim.sub',
                     '77777777-7777-7777-7777-777777777777', true);
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, reason)
  values ('9a000000-0000-0000-0000-0000000000a3',
          '88888888-8888-8888-8888-888888888888', 'FICTIF Inconnu',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1',
          'FICTIF — octroi apres levee de l''ambiguite');
end
$$;


-- Octroi general et octroi plus specifique: le specifique l'emporte, et le
-- snapshot nomme celui qui a REELLEMENT servi.
do $$
declare c record;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, edition, reason)
  values ('9a000000-0000-0000-0000-0000000000b1',
          '88888888-8888-8888-8888-888888888888', 'FICTIF Inconnu Specifique',
          'can_validate_normative_reference', 'BE', 'EN 1992', '1-1', '2010',
          'FICTIF — portee plus etroite, edition 2010');

  perform set_config('request.jwt.claim.sub',
                     '88888888-8888-8888-8888-888888888888', true);
  perform t_confirmer(p_rule => 'test.specificite', p_idem => 'FICTIF-spec');
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-spec';

  if c.authorisation_grant_id <> '9a000000-0000-0000-0000-0000000000b1' then
    raise exception
      'l''octroi le plus specifique devait etre retenu, % utilise',
      c.authorisation_grant_id;
  end if;
  if (c.authorisation_scope ->> 'edition') <> '2010' then
    raise exception
      'le snapshot ne decrit pas l''octroi reellement retenu: %',
      c.authorisation_scope;
  end if;
  if c.verifier_name <> 'FICTIF Inconnu Specifique' then
    raise exception 'le nom vient de l''octroi retenu, or: %', c.verifier_name;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #2 — re-signature apres revocation
-- ---------------------------------------------------------------------
-- L'unicite semantique interdisait cela, et c'etait faux: une revocation
-- motivee suivie d'une nouvelle revue est le parcours normal d'une
-- correction.
do $$
declare premiere uuid; seconde uuid; actives bigint;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  premiere := t_confirmer(p_rule => 'test.resignature', p_idem => 'FICTIF-rs-1');

  -- 2. Nouvelle cle AVANT revocation: acceptee (plus aucune unicite
  --    semantique), mais le domaine n'y verra toujours qu'UN regard.
  perform t_confirmer(p_rule => 'test.resignature', p_idem => 'FICTIF-rs-2');
  select count(distinct verifier_id) into actives
    from normative_rule_confirmations where rule_id = 'test.resignature';
  if actives <> 1 then
    raise exception
      'deux lignes du meme verificateur donnent % regards, 1 attendu', actives;
  end if;

  -- 3. Revocation de la premiere.
  insert into normative_rule_confirmation_revocations
    (confirmation_id, revoked_by, revoked_by_name, revoked_at,
     authorisation_scope, reason)
  values (premiere, '88888888-8888-8888-8888-888888888888', 'FICTIF Usurpe',
          timestamptz '1999-01-01', '{}'::jsonb,
          'FICTIF — clause mal lue, nouvelle revue engagee.');

  -- 4. Nouvelle confirmation du MEME sujet par le MEME verificateur.
  seconde := t_confirmer(p_rule => 'test.resignature', p_idem => 'FICTIF-rs-3');
  if seconde is null then
    raise exception 'la re-signature apres revocation a echoue';
  end if;

  -- 5. Seules les confirmations ACTIVES comptent.
  select active_independent_regards into actives
    from normative_rule_confirmation_status
   where rule_id = 'test.resignature';
  if actives <> 1 then
    raise exception
      'la vue de statut compte % regards actifs, 1 attendu', actives;
  end if;
  select count(*) into actives
    from normative_rule_confirmations c
   where c.rule_id = 'test.resignature'
     and not exists (select 1 from normative_rule_confirmation_revocations r
                      where r.confirmation_id = c.id);
  if actives <> 2 then
    raise exception
      '% attestations actives, 2 attendues (rs-2 et rs-3)', actives;
  end if;
end
$$;


-- 1. Double envoi avec la MEME cle d'idempotence: refuse.
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  begin
    perform t_confirmer(p_rule => 'test.resignature', p_idem => 'FICTIF-rs-3');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception 'une cle d''idempotence rejouee a cree une seconde ligne';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #3 — aucune immuabilite GLOBALE ajoutee a audit_log
-- ---------------------------------------------------------------------
-- La protection doit porter sur les seules lignes normatives. Rendre tout le
-- journal immuable fermerait sans preavis la retention, l'anonymisation et la
-- maintenance pour tous ses autres producteurs.
do $$
declare ordinaire bigint; normative bigint; ok boolean := false;
begin
  insert into audit_log (action, entity, entity_id, payload)
  values ('project.exported', 'projects', null, '{"fictif": true}'::jsonb)
  returning id into ordinaire;

  -- Une ligne NON normative reste modifiable et supprimable.
  update audit_log set payload = '{"fictif": true, "anonymise": true}'::jsonb
   where id = ordinaire;
  delete from audit_log where id = ordinaire;

  -- Une ligne normative, elle, est scellee.
  select id into normative from audit_log
   where action like 'normative.%' limit 1;
  if normative is null then
    raise exception 'aucune trace normative: le test ne verifie rien';
  end if;
  begin
    update audit_log set payload = '{}'::jsonb where id = normative;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'une trace normative a pu etre reecrite';
  end if;

  ok := false;
  begin
    delete from audit_log where id = normative;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception 'une trace normative a pu etre supprimee';
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #4 et #5 — moindre privilege sur les tables de gouvernance
-- ---------------------------------------------------------------------
-- 01_guarantees.sql accorde `select, insert, update, delete on all tables in
-- schema public to authenticated` pour les suites plus anciennes. Ce blanc-
-- seing du HARNAIS couvre aussi les tables normatives et masquerait
-- exactement ce qu'on veut mesurer. On retablit donc ici les privileges que
-- la migration installe reellement, avant de tester.
--
-- 6.3b3: SELECT SEUL. Cette liste portait encore `insert` — heritage de
-- l'epoque ou la frontiere d'ecriture n'etait pas tranchee. Elle CONTREDISAIT
-- desormais la migration, qui n'accorde que SELECT, et le harnais rendait
-- donc au porteur de jeton un droit que le deploiement lui refuse. Un test
-- qui se donne a lui-meme le privilege qu'il pretend mesurer ne mesure rien.
--
-- La verification hors harnais est dans `virgin_root.sql`, sur une base ou
-- 01_guarantees n'a jamais tourne: c'est elle qui constate l'ACL REELLE de la
-- migration, et elle seule peut attraper une derive entre les deux fichiers.
revoke all on normative_authorisation_grants          from authenticated;
revoke all on normative_authorisation_revocations     from authenticated;
revoke all on normative_rule_confirmations            from authenticated;
revoke all on normative_rule_confirmation_revocations from authenticated;
grant select on normative_authorisation_grants          to authenticated;
grant select on normative_authorisation_revocations     to authenticated;
grant select on normative_rule_confirmations            to authenticated;
grant select on normative_rule_confirmation_revocations to authenticated;

-- 6.3b6a. La table d'activation subit le meme blanc-seing du harnais: sans ce
-- retablissement, `authenticated` pourrait la LIRE et l'ECRIRE, et les
-- controles ci-dessous porteraient sur des permissions que la MIGRATION
-- n'accorde pas.
--
-- Correctif #6: la migration n'accorde plus AUCUN acces a la table — la ligne
-- porte l'audit de deploiement (qui, quand, quel digest de topologie). Ce qui
-- franchit la frontiere est l'ETAT SEUL, par la vue minimale et par la
-- fonction. La premiere ecriture de ce bloc rendait `select` sur la table, et
-- gravait donc dans le harnais le defaut que le correctif retire.
revoke all on normative_activation from authenticated;
revoke all on normative_activation_status from authenticated;
grant select on normative_activation_status to authenticated;

-- Le singleton du plan de controle subit le meme blanc-seing, et il est le
-- sujet le plus sensible de tous: qui peut y ecrire se designe lui-meme comme
-- « le plan approuve » et s'exempte du refus d'ADMIN residuel. La migration ne
-- l'ouvre a personne d'applicatif; le harnais ne doit pas le rouvrir.
revoke all on normative_control_plane from authenticated;

do $$
declare n bigint; total bigint;
begin
  select count(*) into total from normative_rule_confirmations;

  set local role authenticated;
  -- Un utilisateur ORDINAIRE, titulaire d'aucune habilitation.
  perform set_config('request.jwt.claim.sub',
                     '99999999-9999-9999-9999-999999999999', true);

  select count(*) into n from normative_authorisation_grants;
  if n <> 0 then
    raise exception
      'RLS PERCEE: un utilisateur ordinaire voit % octroi(s). Qui est '
      'habilite a quoi est de la gouvernance, pas du referentiel.', n;
  end if;
  select count(*) into n from normative_rule_confirmations;
  if n <> 0 then
    raise exception
      'RLS PERCEE: un utilisateur ordinaire voit % confirmation(s), avec '
      'noms, declarations et pages lues.', n;
  end if;
  select count(*) into n from normative_rule_confirmation_revocations;
  if n <> 0 then
    raise exception 'RLS PERCEE: % revocation(s) visibles', n;
  end if;

  -- La vue minimale, elle, lui est ouverte: c'est ce dont un calcul a besoin.
  select count(*) into n from normative_rule_confirmation_status;
  if n = 0 then
    raise exception
      'la vue de statut est vide pour un utilisateur authentifie: le calcul '
      'ne pourrait rien en tirer';
  end if;
end
$$;
reset role;

-- Le signataire voit SES propres lignes, et elles seules.
do $$
declare n bigint;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  select count(*) into n from normative_rule_confirmations;
  if n = 0 then
    raise exception 'un signataire ne voit meme pas ce qu''il a signe';
  end if;
  select count(*) into n from normative_rule_confirmations
   where verifier_id <> '55555555-5555-5555-5555-555555555555';
  if n <> 0 then
    raise exception 'RLS PERCEE: le signataire voit % ligne(s) d''autrui', n;
  end if;
  select count(*) into n from normative_authorisation_grants
   where grantee_id <> '55555555-5555-5555-5555-555555555555';
  if n <> 0 then
    raise exception 'RLS PERCEE: le signataire voit % octroi(s) d''autrui', n;
  end if;
end
$$;
reset role;

-- Le provider backend charge les confirmations, et rien de la gouvernance.
do $$
declare n bigint; total bigint;
begin
  select count(*) into total from normative_rule_confirmations;
  set local role normative_backend;
  select count(*) into n from normative_rule_confirmations;
  if n <> total then
    raise exception
      'le provider backend voit % confirmations sur %: il ne pourrait pas '
      'evaluer une regle', n, total;
  end if;
  select count(*) into n from normative_rule_confirmation_revocations;
  if n = 0 then
    raise exception
      'le provider backend ne voit aucune revocation: il compterait des '
      'regards deja retires';
  end if;
end
$$;
reset role;

do $$
declare ok boolean := false;
begin
  set local role normative_backend;
  begin
    perform count(*) from normative_authorisation_grants;
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'le provider backend accede a la gouvernance des habilitations, dont '
      'il n''a pas besoin';
  end if;
end
$$;
reset role;

-- La gouvernance voit tout, et c'est son role.
do $$
declare n bigint;
begin
  set local role normative_governance;
  select count(*) into n from normative_authorisation_grants;
  if n = 0 then
    raise exception 'la gouvernance ne voit aucun octroi';
  end if;
  select count(*) into n from normative_rule_confirmations;
  if n = 0 then
    raise exception 'la gouvernance ne voit aucune confirmation';
  end if;
end
$$;
reset role;

-- Aucune policy UPDATE ni DELETE: l'operation est refusee meme a la
-- gouvernance, qui n'a d'ailleurs pas le privilege de table.
do $$
declare
  t text;
  ok boolean;
begin
  foreach t in array array['normative_authorisation_grants',
                           'normative_rule_confirmations'] loop
    if exists (select 1 from pg_policies
                where schemaname = 'public' and tablename = t
                  and cmd in ('UPDATE', 'DELETE')) then
      raise exception 'une policy UPDATE/DELETE existe sur %', t;
    end if;
    if has_table_privilege('authenticated', t, 'UPDATE')
       or has_table_privilege('authenticated', t, 'DELETE') then
      raise exception 'authenticated detient UPDATE ou DELETE sur %', t;
    end if;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 6.3b1 #8 et #9 — securite des fonctions SECURITY DEFINER
-- ---------------------------------------------------------------------
do $$
declare f record; n bigint := 0;
begin
  for f in
    select p.oid, p.proname, p.prosecdef, p.proconfig
      from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
     where ns.nspname = 'public'
       and (p.proname like '%normative%' or p.proname = 'assert_digest_integrity')
  loop
    if f.prosecdef then
      n := n + 1;
      -- search_path fixe explicitement: sans cela, l'appelant choisirait les
      -- objets que la fonction resout, en s'executant avec les droits du
      -- proprietaire.
      if f.proconfig is null
         or not exists (select 1 from unnest(f.proconfig) c
                         where c like 'search_path=%') then
        raise exception
          'la fonction SECURITY DEFINER % n''a pas de search_path fixe',
          f.proname;
      end if;
      -- pg_temp doit venir en DERNIER, sinon une table temporaire de
      -- l'appelant masquerait une table de public.
      if exists (select 1 from unnest(f.proconfig) c
                  where c like 'search_path=%'
                    and c not like '%public%') then
        raise exception
          'le search_path de % ne nomme pas public explicitement', f.proname;
      end if;
      if exists (select 1 from unnest(f.proconfig) c
                  where c like 'search_path=pg_temp%') then
        raise exception
          'pg_temp precede public dans le search_path de %: une table '
          'temporaire de l''appelant masquerait une table du schema',
          f.proname;
      end if;
    end if;

    if has_function_privilege('public', f.oid, 'EXECUTE') then
      raise exception
        'PUBLIC detient EXECUTE sur %: une fonction SECURITY DEFINER '
        'offrirait alors les droits de son proprietaire a tout le monde',
        f.proname;
    end if;
  end loop;

  if n < 5 then
    raise exception
      'seulement % fonctions SECURITY DEFINER inspectees: le test ne couvre '
      'pas ce qu''il annonce', n;
  end if;
end
$$;


-- 6.3b3 #5 — les fonctions d'autorite appartiennent a des roles NOLOGIN
-- DEDIES, et c'est ce qui rend `current_user` significatif.
--
-- Comparer `current_user` au proprietaire de la BASE ne prouvait rien: dans
-- une fonction SECURITY DEFINER, current_user EST le proprietaire de la
-- fonction, donc la comparaison etait toujours vraie. Comparer a un role
-- dedie, NOLOGIN, dont personne n'est membre, prouve en revanche que l'appel
-- est passe par cette fonction — et par elle seule.
do $$
declare r record;
begin
  for r in
    select p.proname, p.prosecdef, pg_get_userbyid(p.proowner) as proprietaire
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname in ('bootstrap_normative_administrator',
                         'log_normative_event', 'check_normative_grant',
                         'check_normative_grant_revocation',
                         'check_normative_confirmation',
                         'check_normative_confirmation_revocation')
  loop
    if not r.prosecdef then
      raise exception '% n''est pas SECURITY DEFINER', r.proname;
    end if;
    if r.proprietaire not in ('eurostruct_normative_writer',
                              'eurostruct_normative_bootstrap') then
      raise exception
        '% appartient a « % »: son current_user ne prouve rien, car ce role '
        'n''est pas dedie', r.proname, r.proprietaire;
    end if;
    if (select rolcanlogin from pg_roles where rolname = r.proprietaire) then
      raise exception
        'le role d''autorite % est connectable: quelqu''un pourrait s''y '
        'authentifier et forger une origine', r.proprietaire;
    end if;
  end loop;
end
$$;


-- 6.3b3 #5 — EXECUTE refuse a TOUS les roles applicatifs, pas seulement a
-- PUBLIC. Les deux roles d'autorite en ont, et c'est le point: ils sont
-- NOLOGIN et personne n'en est membre.
-- La garantie est une FONCTION et non un bloc anonyme: le test de mutation
-- qui suit doit rejouer EXACTEMENT ce code, et non une seconde ecriture du
-- meme controle qui pourrait deriver de lui sans que rien ne le dise.
create function t_garantie_execute() returns void language plpgsql as $$
declare f record; role_nom text; exempte oid;
begin
  -- EXEMPTION IDENTIFIEE PAR SIGNATURE, et une seule (6.3b6a, correctif #7).
  --
  -- `normative_activation_state()` rend « PENDING » ou « ACTIVE » et rien
  -- d'autre. Ce n'est pas une fonction sensible: c'est l'inverse. Un client qui
  -- ignore que le sous-systeme n'est pas active afficherait des resultats
  -- pre-activation sans le savoir — exactement le genre de silence que ce
  -- projet refuse. La lecture de l'etat est donc ouverte, l'ECRITURE ne l'est
  -- pas: aucune policy d'ecriture n'existe sur `normative_activation`, et
  -- l'activation ne passe que par la finalisation, qui verifie la topologie
  -- avant d'ecrire.
  --
  -- POURQUOI L'OID ET NON `proname`. La version precedente exemptait par le
  -- NOM. PostgreSQL autorise les surcharges: `normative_activation_state(text)`
  -- ajoutee demain — n'importe quel corps, n'importe quels droits — aurait
  -- herite de l'exemption sans que personne ne l'ecrive. Une exception qui
  -- s'elargit toute seule n'est plus une exception. On resout donc UNE
  -- signature, une fois, et on compare des OID.
  exempte := to_regprocedure('public.normative_activation_state()');
  if exempte is null then
    raise exception
      'la signature exemptee public.normative_activation_state() n''existe '
      'pas: l''exemption porterait dans le vide et le controle ne dirait plus '
      'ce qu''il annonce';
  end if;

  for f in
    select p.oid, p.proname,
           pg_get_function_identity_arguments(p.oid) as args
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and (p.proname like '%normative%' or p.proname = 'assert_digest_integrity')
  loop
    if f.oid = exempte then
      continue;
    end if;

    foreach role_nom in array array['public', 'authenticated',
                                    'normative_backend',
                                    'normative_governance'] loop
      if has_function_privilege(role_nom, f.oid, 'EXECUTE') then
        raise exception
          'le role % detient EXECUTE sur %(%): une fonction sensible ne doit '
          'pas etre appelable par un role applicatif', role_nom, f.proname,
          f.args;
      end if;
    end loop;
  end loop;
end
$$;

select t_garantie_execute();


-- 6.3b6a #7 — TEST DE MUTATION DE L'EXEMPTION ELLE-MEME.
--
-- Le correctif precedent remplace `proname = 'normative_activation_state'` par
-- une comparaison d'OID. Rien, dans un test vert, ne distingue les deux
-- ecritures: la base ne porte aujourd'hui qu'une seule fonction de ce nom. Une
-- garantie qu'aucun etat du monde ne peut faire echouer ne garantit rien.
--
-- On fabrique donc l'etat qui les separe: une SURCHARGE, du meme nom, dotee de
-- droits qui devraient etre refuses. Sous l'ancienne ecriture elle etait
-- exemptee en silence; sous celle-ci elle doit etre VUE.
--
-- Le corps de la surcharge est deliberement inoffensif: ce qui est teste est
-- le mecanisme d'exemption, pas la fonction.
create function normative_activation_state(p_fictif text) returns text
language sql immutable as $$ select 'FICTIF'; $$;
grant execute on function normative_activation_state(text) to authenticated;

do $$
declare vu boolean := false; message text;
begin
  begin
    perform t_garantie_execute();
  exception when others then
    vu := true; message := sqlerrm;
  end;

  if not vu then
    raise exception
      'une surcharge public.normative_activation_state(text) executable par '
      'authenticated n''a pas ete vue: l''exemption porte sur le NOM et '
      's''elargit donc d''elle-meme a toute fonction future qui le reprend';
  end if;

  -- Et pour la BONNE raison: le refus doit nommer la surcharge, pas une autre
  -- fonction qui aurait par ailleurs derive.
  if message not like '%normative_activation_state(p_fictif text)%' then
    raise exception
      'la garantie a echoue, mais sur un autre sujet que la surcharge: %',
      message;
  end if;
end
$$;

drop function normative_activation_state(text);

-- Et l'etat rendu: la signature exemptee doit etre de nouveau seule, et la
-- garantie de nouveau verte. Sans ce retour, le fichier laisserait derriere lui
-- l'objet meme qu'il vient de declarer inacceptable.
do $$
declare n integer;
begin
  select count(*) into n
    from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'normative_activation_state';
  if n <> 1 then
    raise exception
      'apres le test de mutation, % fonction(s) normative_activation_state '
      'subsistent au lieu d''une seule', n;
  end if;
end
$$;

select t_garantie_execute();
drop function t_garantie_execute();


-- 6.3b3 #5 — le sens INVERSE des appartenances: aucun role applicatif ne doit
-- etre membre d'un role de service ou d'autorite, sans quoi il en heriterait
-- tous les droits et le cloisonnement serait nominal.
do $$
declare r record;
begin
  for r in
    select parent.rolname as service, enfant.rolname as membre
      from pg_auth_members m
      join pg_roles parent on parent.oid = m.roleid
      join pg_roles enfant on enfant.oid = m.member
     where parent.rolname in ('normative_backend', 'normative_governance',
                              'eurostruct_normative_writer',
                              'eurostruct_normative_bootstrap')
  loop
    if r.membre in ('authenticated', 'anon', 'public') then
      raise exception
        'le role applicatif % est membre de %: il en herite les droits',
        r.membre, r.service;
    end if;
  end loop;
end
$$;


-- 6.3b2 #5 — le schema resolu avant pg_temp n'est pas inscriptible par un
-- role non fiable. Sans cela, `search_path = public, pg_temp` ne protegerait
-- rien: il suffirait de creer un objet dans `public` pour detourner une
-- fonction SECURITY DEFINER.
do $$
declare role_nom text;
begin
  foreach role_nom in array array['authenticated', 'normative_backend',
                                  'normative_governance', 'public'] loop
    if has_schema_privilege(role_nom, 'public', 'CREATE') then
      raise exception
        'le role % peut creer des objets dans le schema public, qui precede '
        'pg_temp dans le search_path des fonctions SECURITY DEFINER',
        role_nom;
    end if;
  end loop;
end
$$;


-- 6.3b2 #5 — attributs des deux roles de service, s'ils preexistent.
do $$
declare r record;
begin
  for r in select rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
             from pg_roles
            where rolname in ('normative_backend', 'normative_governance')
  loop
    if r.rolsuper or r.rolbypassrls or r.rolcreaterole or r.rolcreatedb then
      raise exception
        'le role de service % porte un attribut privilegie '
        '(super=%, bypassrls=%, createrole=%, createdb=%): la RLS ne le '
        'contiendrait pas', r.rolname, r.rolsuper, r.rolbypassrls,
        r.rolcreaterole, r.rolcreatedb;
    end if;
    if exists (select 1 from pg_auth_members m
                join pg_roles parent on parent.oid = m.roleid
                join pg_roles enfant on enfant.oid = m.member
               where enfant.rolname = r.rolname
                 and (parent.rolsuper or parent.rolbypassrls)) then
      raise exception
        'le role de service % est membre d''un role privilegie', r.rolname;
    end if;
  end loop;
end
$$;


-- 6.3b2 #2 — volatilite declaree conforme au comportement reel.
do $$
declare v "char";
begin
  select provolatile into v from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'normative_authorisation_snapshot';
  if v = 'i' then
    raise exception
      'normative_authorisation_snapshot est declaree IMMUTABLE alors qu''elle '
      'appelle now(): le planificateur peut pre-evaluer et mettre en cache '
      'une valeur qui change';
  end if;
  if v not in ('s', 'v') then
    raise exception 'volatilite inattendue: %', v;
  end if;
end
$$;

-- L'amorcage est inaccessible a un utilisateur ordinaire.
do $$
declare ok boolean := false;
begin
  set local role authenticated;
  begin
    perform bootstrap_normative_administrator(
      '99999999-9999-9999-9999-999999999999', 'FICTIF Intrus',
      'FICTIF — tentative depuis un compte ordinaire.');
  exception
    when insufficient_privilege then ok := true;
    when others then ok := true;   -- refus de droit d'execution
  end;
  if not ok then
    raise exception 'un utilisateur ordinaire a pu appeler l''amorcage';
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 6.3b1 #10 — un seul amorcage, structurellement
-- ---------------------------------------------------------------------
-- Le verrou consultatif serialise deux appels concurrents; l'index partiel le
-- garantit meme si le verrou etait contourne. On teste la garantie
-- STRUCTURELLE, la seule qui ne depende d'aucun ordonnancement.
do $$
declare ok boolean := false;
begin
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, granted_by, origin, reason)
    values ('99999999-9999-9999-9999-999999999999', 'FICTIF Second Racine',
            'can_manage_normative_authorisations', null, 'bootstrap',
            'FICTIF — second amorcage insere directement');
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'une seconde racine de confiance a ete creee: deux administrateurs '
      'initiaux non lies l''un a l''autre';
  end if;
end
$$;


-- =====================================================================
-- 6.3b2 — coherence atomique du paquet
-- =====================================================================
-- Quatre empreintes individuellement justes ne font pas un sujet. Chacun de
-- ces cas a d'abord ete verifie ROUGE contre la version precedente: pile
-- substituee, spec/implementation interverties, rule_id de colonne different
-- du rule_id signe, et dossier de preuve sans rapport avec son payload.
do $$
declare ok boolean;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  -- Les projections jsonb sont DERIVEES des payloads: ce que le client met
  -- dans stack_snapshot et evidence_items est ecrase, pas cru.
  perform t_confirmer(p_rule => 'test.coherence', p_idem => 'FICTIF-coh-1');
  declare c record;
  begin
    select * into c from normative_rule_confirmations
     where idempotency_key = 'FICTIF-coh-1';
    if c.stack_snapshot ? 'substitue' then
      raise exception
        'la pile fournie par le client a survecu: elle pouvait differer de '
        'celle qui est hachee';
    end if;
    if c.stack_snapshot is distinct from c.stack_payload::jsonb then
      raise exception 'stack_snapshot ne derive pas de stack_payload';
    end if;
    if c.evidence_items is distinct from (c.evidence_payload::jsonb -> 'items') then
      raise exception
        'evidence_items ne derive pas de evidence_payload: le dossier stocke '
        'n''est pas celui qui est scelle';
    end if;
    if c.annex_edition <> '2010' then
      raise exception 'annex_edition non extraite de la pile signee: %',
        c.annex_edition;
    end if;
  end;

  -- Autre regle en colonne que celle signee par les payloads.
  ok := false;
  begin
    perform t_confirmer(p_rule => 'test.coherence',
                        p_sub_rule_col => 'test.REGLE.USURPEE',
                        p_idem => 'FICTIF-coh-regle');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'rule_id de colonne different du rule_id signe: ACCEPTE. La recherche '
      'et la signature designeraient deux regles';
  end if;

  -- Specification et implementation interverties.
  ok := false;
  begin
    perform t_confirmer(p_rule => 'test.coherence', p_echanger => true,
                        p_idem => 'FICTIF-coh-echange');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'spec et implementation interverties: ACCEPTEES. Deux empreintes justes '
      'decriraient le mauvais objet';
  end if;
end
$$;


-- Autre juridiction en colonne que celle de la pile signee.
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  begin
    perform t_confirmer(p_rule => 'test.coherence', p_sub_country => 'FR',
                        p_idem => 'FICTIF-coh-pays');
  exception
    when check_violation then ok := true;
    when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception 'juridiction de colonne differente de la pile signee: ACCEPTEE';
  end if;
end
$$;


-- Payload qui n'est pas du JSON, ou dont le `kind` ment.
do $$
declare ok boolean;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  ok := false;
  begin
    insert into normative_rule_confirmations (
      country_code, standard_family, part, rule_id,
      stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
      digest_algorithm, canonicalization_version,
      normative_spec_payload, implementation_payload, evidence_payload,
      stack_payload, stack_snapshot, annex_edition, evidence_items, statement,
      verifier_id, verifier_name, verified_at, authorisation_grant_id,
      authorisation_scope, idempotency_key)
    select 'BE', 'EN 1992', '1-1', 'test.coherence',
      c.stack_digest, c.normative_spec_digest, c.implementation_digest,
      c.evidence_digest, 'sha256', 'esc-canon/1',
      c.normative_spec_payload, c.implementation_payload, c.evidence_payload,
      -- pile REMPLACEE par le payload de preuve: hash faux ET kind faux
      c.evidence_payload, '{}'::jsonb, 'x', '[]'::jsonb, 'FICTIF',
      c.verifier_id, 'FICTIF', now(), c.authorisation_grant_id,
      '{}'::jsonb, 'FICTIF-coh-kind'
    from normative_rule_confirmations c
     where c.idempotency_key = 'FICTIF-coh-1';
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'un payload de pile remplace par un payload de preuve: ACCEPTE';
  end if;
end
$$;


-- =====================================================================
-- 6.3b2 — horodatages imposes par le serveur partout
-- =====================================================================
do $$
declare c record; g record; r record;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  perform t_confirmer(p_rule => 'test.horodatage', p_idem => 'FICTIF-hor-1');
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-hor-1';
  if c.verified_at < timestamptz '2000-01-01' then
    raise exception 'verified_at client (1999) a survecu: %', c.verified_at;
  end if;
  if c.created_at < timestamptz '2000-01-01' then
    raise exception 'created_at client (1999) a survecu: %', c.created_at;
  end if;

  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, standard_family,
     part, granted_at, reason)
  values ('9a000000-0000-0000-0000-0000000000c1',
          '66666666-6666-6666-6666-666666666666', 'FICTIF Relecteur Deux',
          'can_validate_normative_reference', 'BE', 'EN 1993', '1-1',
          timestamptz '1999-01-01', 'FICTIF — horodatage fourni par le client');
  select * into g from normative_authorisation_grants
   where id = '9a000000-0000-0000-0000-0000000000c1';
  if g.granted_at < timestamptz '2000-01-01' then
    raise exception 'granted_at client (1999) a survecu: %', g.granted_at;
  end if;

  insert into normative_authorisation_revocations
    (grant_id, revoked_by, revoked_at, reason)
  values ('9a000000-0000-0000-0000-0000000000c1',
          '88888888-8888-8888-8888-888888888888', timestamptz '1999-01-01',
          'FICTIF — horodatage et auteur fournis par le client');
  select * into r from normative_authorisation_revocations
   where grant_id = '9a000000-0000-0000-0000-0000000000c1';
  if r.revoked_at < timestamptz '2000-01-01' then
    raise exception 'revoked_at client (1999) a survecu: %', r.revoked_at;
  end if;
  if r.revoked_by <> '44444444-4444-4444-4444-444444444444' then
    raise exception 'revoked_by client a survecu: %', r.revoked_by;
  end if;
end
$$;


-- =====================================================================
-- 6.3b2 — le dernier administrateur ne peut pas etre retire
-- =====================================================================
-- Contre-exemple verifie ROUGE: on pouvait revoquer le dernier octroi actif
-- « can_manage_normative_authorisations », et l'index interdisant un second
-- amorcage rendait alors la gouvernance IRRECUPERABLE.
do $$
declare ok boolean := false; n bigint; dernier uuid;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);

  -- Ne laisser qu'UN seul administrateur actif.
  for dernier in
    select g.id from normative_authorisation_grants g
     where g.permission = 'can_manage_normative_authorisations'
       and normative_grant_is_active(g.id)
       and g.grantee_id <> '44444444-4444-4444-4444-444444444444'
  loop
    insert into normative_authorisation_revocations (grant_id, reason)
    values (dernier, 'FICTIF — concentration de l''administration.');
  end loop;

  select count(*), min(g.id::text)::uuid into n, dernier
    from normative_authorisation_grants g
   where g.permission = 'can_manage_normative_authorisations'
     and normative_grant_is_active(g.id);
  if n <> 1 then
    raise exception '% administrateurs actifs, 1 attendu pour ce test', n;
  end if;

  begin
    insert into normative_authorisation_revocations (grant_id, reason)
    values (dernier, 'FICTIF — retrait du dernier administrateur.');
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception
      'le dernier administrateur a pu etre retire: la gouvernance serait sans '
      'personne et l''amorcage ne peut pas etre rejoue';
  end if;

  -- Et la voie normale reste ouverte: octroyer a un autre, PUIS retirer.
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, reason)
  values ('9a000000-0000-0000-0000-0000000000d1',
          '77777777-7777-7777-7777-777777777777', 'FICTIF Revocateur',
          'can_manage_normative_authorisations',
          'FICTIF — releve de l''administration.');
  insert into normative_authorisation_revocations (grant_id, reason)
  values (dernier, 'FICTIF — passation effectuee.');

  select count(*) into n from normative_authorisation_grants g
   where g.permission = 'can_manage_normative_authorisations'
     and normative_grant_is_active(g.id);
  if n <> 1 then
    raise exception 'apres passation, % administrateurs actifs', n;
  end if;
end
$$;


-- =====================================================================
-- 6.3b4 — la couverture de portee, et non le simple decompte
-- =====================================================================
-- CONTRE-EXEMPLE VERIFIE ROUGE contre 6.3b3: la garde comptait les
-- administrateurs actifs restants et se satisfaisait d'UN SEUL. Avec un
-- administrateur GLOBAL A et un administrateur BELGE B, retirer A laissait
-- « un administrateur » — et la France, l'Espagne et l'Allemagne sans
-- personne. Le decompte ne mesurait pas la bonne chose.
do $$
declare ok boolean := false; a_id uuid; b_id uuid; autre uuid; n bigint;
begin
  perform set_config('request.jwt.claim.sub',
                     '77777777-7777-7777-7777-777777777777', true);

  -- A: administration GLOBALE (portee entierement NULL).
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, reason)
  values ('9a000000-0000-0000-0000-0000000000e1',
          '44444444-4444-4444-4444-444444444444', 'FICTIF Admin Global',
          'can_manage_normative_authorisations',
          'FICTIF — administration de toutes les juridictions.')
  returning id into a_id;

  -- B: administration BELGE uniquement.
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, reason)
  values ('9a000000-0000-0000-0000-0000000000e2',
          '55555555-5555-5555-5555-555555555555', 'FICTIF Admin Belge',
          'can_manage_normative_authorisations', 'BE',
          'FICTIF — administration de la seule Belgique.')
  returning id into b_id;

  -- Les sections precedentes ont laisse d'AUTRES administrateurs de portee
  -- GLOBALE actifs. L'un d'eux couvrirait A a juste titre, la garde laisserait
  -- passer, et le test conclurait a tort qu'elle ne protege rien. Verifie par
  -- sonde: sans ce nettoyage, l'etat au moment de la tentative etait
  -- « globaux=2, total=3 » et non « globaux=1, total=2 ».
  --
  -- A, de portee globale, les couvre tous: il peut donc les retirer.
  loop
    select g.id into autre from normative_authorisation_grants g
     where g.permission = 'can_manage_normative_authorisations'
       and g.id <> a_id and g.id <> b_id
       and normative_grant_is_active(g.id)
     limit 1;
    exit when autre is null;
    insert into normative_authorisation_revocations (grant_id, reason)
    values (autre, 'FICTIF — concentration sur A et B pour le test de portee.');
  end loop;

  -- Precondition sur la FORME, et non sur le nombre: A doit etre le SEUL
  -- administrateur de portee globale, et B doit exister a cote de lui.
  select count(*) into n from normative_authorisation_grants g
   where g.permission = 'can_manage_normative_authorisations'
     and normative_grant_is_active(g.id)
     and g.country_code is null and g.standard_family is null
     and g.part is null and g.edition is null;
  if n <> 1 then
    raise exception
      'precondition non tenue: % administrateur(s) de portee globale actifs, '
      '1 attendu. Un autre global couvrirait A, et la garde passerait a '
      'juste titre', n;
  end if;

  select count(*) into n from normative_authorisation_grants g
   where g.permission = 'can_manage_normative_authorisations'
     and normative_grant_is_active(g.id);
  if n <> 2 then
    raise exception
      'precondition non tenue: % administrateur(s) actif(s), 2 attendus '
      '(A global + B belge). Avec un seul, l''ancien decompte aurait refuse '
      'et le test ne distinguerait rien', n;
  end if;

  -- LE TEST. Retirer A: refus, car B ne couvre que la Belgique.
  --
  -- C'est A qui revoque, et il le faut: le resolveur exige de l'auteur d'une
  -- revocation une habilitation COUVRANT la portee visee. Le belge B ne
  -- l'aurait donc pas, et son refus viendrait du resolveur — jamais de la
  -- garde de couverture, qui ne serait alors jamais atteinte. Verifie: avec
  -- B en revocateur, le test passait au vert sur un autre motif.
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    insert into normative_authorisation_revocations (grant_id, reason)
    values (a_id, 'FICTIF — retrait de l''administrateur global.');
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception
      'l''administrateur GLOBAL a pu etre retire alors que le seul restant '
      'ne couvre que la Belgique: la France, l''Espagne et l''Allemagne '
      'seraient sans administrateur, et l''amorcage ne peut pas etre rejoue';
  end if;

  -- La reciproque doit rester possible: B est COUVERT par A (global), donc
  -- son retrait est legitime. Sans cette moitie, la garde serait satisfaite
  -- par un systeme qui refuse toute revocation.
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_revocations (grant_id, reason)
  values (b_id, 'FICTIF — retrait du belge, couvert par le global.');

  if normative_grant_is_active(b_id) then
    raise exception 'la revocation de l''administrateur belge n''a pas pris';
  end if;
  if not normative_grant_is_active(a_id) then
    raise exception 'l''administrateur global a disparu';
  end if;
end
$$;

-- Couverture PARTIELLE par plusieurs octrois: refusee elle aussi. Deux
-- administrateurs BE et FR ne remplacent pas un administrateur global — ils
-- ne couvrent ni l'Espagne ni l'Allemagne. La garde exige qu'UN SEUL octroi
-- contienne la portee retiree.
do $$
declare ok boolean := false;
begin
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  insert into normative_authorisation_grants
    (id, grantee_id, grantee_name, permission, country_code, reason)
  values ('9a000000-0000-0000-0000-0000000000e3',
          '55555555-5555-5555-5555-555555555555', 'FICTIF Admin Belge 2',
          'can_manage_normative_authorisations', 'BE',
          'FICTIF — administration belge.'),
         ('9a000000-0000-0000-0000-0000000000e4',
          '66666666-6666-6666-6666-666666666666', 'FICTIF Admin Francais',
          'can_manage_normative_authorisations', 'FR',
          'FICTIF — administration francaise.');

  -- La aussi, c'est le titulaire de la portee globale qui revoque: seul lui
  -- est habilite sur cette portee, et le refus attendu doit venir de la
  -- couverture, pas du resolveur.
  begin
    insert into normative_authorisation_revocations (grant_id, reason)
    values ('9a000000-0000-0000-0000-0000000000e1',
            'FICTIF — retrait du global avec BE et FR en place.');
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception
      'l''administrateur global a pu etre retire au motif que BE et FR '
      'existent: l''Espagne et l''Allemagne resteraient sans administrateur. '
      'Une union de portees ne couvre pas une portee globale';
  end if;
end
$$;


-- =====================================================================
-- 6.3b2 — le namespace « normative.* » du journal est reserve
-- =====================================================================
do $$
declare ok boolean; i bigint;
begin
  -- Insertion directe, meme en tant que superutilisateur: refusee.
  ok := false;
  begin
    insert into audit_log (action, entity, payload)
    values ('normative.confirmation.created', 'normative_rule_confirmations',
            '{"faux": true}'::jsonb);
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'une fausse trace normative a pu etre inseree directement: une preuve '
      'd''octroi ou de confirmation se fabriquerait a la main';
  end if;

  -- Bascule d'une action ordinaire vers le namespace: refusee.
  -- Contre-exemple verifie ROUGE: la ligne devenait normative, donc ensuite
  -- ineffacable. Empoisonnement a sens unique.
  insert into audit_log (action, entity, payload)
  values ('project.exported', 'projects', '{}'::jsonb) returning id into i;
  ok := false;
  begin
    update audit_log set action = 'normative.authorisation.granted' where id = i;
  exception when restrict_violation then ok := true;
  end;
  if not ok then
    raise exception
      'une ligne ordinaire est devenue une trace normative, desormais '
      'immuable';
  end if;
  delete from audit_log where id = i;

  -- log_normative_event refuse une action hors namespace.
  ok := false;
  begin
    perform log_normative_event('projet.exporte', 'projects', null,
                                '{}'::jsonb, null);
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception 'log_normative_event accepte une action hors namespace';
  end if;
end
$$;


-- =====================================================================
-- 6.3b6a/6.3b6b — l'activation, et ce qu'elle doit porter
-- =====================================================================
-- CE CONTROLE A CHANGE DE SUJET, PARCE QUE LA BASE A CHANGE D'ETAT.
--
-- Il exigeait « aucune ligne d'activation », au motif que l'activation n'est
-- jamais un effet de bord d'installation. C'etait vrai d'une base migree et
-- rien de plus — ce qu'etait la base principale jusqu'a 6.3b6b. Elle est
-- desormais DEPLOYEE EN DEUX PHASES par `run.sh`, comme une production: la
-- phase 2 a eu lieu, et exiger PENDING ici reviendrait a exiger que le
-- deploiement soit incomplet.
--
-- La propriete « la migration seule n'active pas » n'est pas perdue: elle est
-- constatee la ou elle se mesure, c'est-a-dire entre les deux phases —
-- `two_phase_deployment.sh` (configurations A, B, C) et
-- `finalisation_contract.sh` (six decors) exigent tous PENDING a la fin de la
-- phase 1, et l'un d'eux exige en outre que la finalisation soit REFUSEE quand
-- un seul role privilegie existe.
--
-- Ce qui est verifie ici, c'est ce qu'une activation doit PORTER.
do $$
declare
  n bigint;
  plan_nom text;
  plan_oid oid;
  mig_nom text;
begin
  select count(*) into n from normative_activation;
  if n <> 1 then
    raise exception
      'la base principale porte % ligne(s) d''activation, il en faut '
      'exactement 1: elle est deployee en deux phases par run.sh', n;
  end if;
  if normative_activation_state() <> 'ACTIVE' then
    raise exception
      'ligne presente et etat « % »: la presence de la ligne doit valoir '
      'ACTIVE', normative_activation_state();
  end if;

  -- L'IDENTITE DU PLAN DE CONTROLE EST COMPLETE, et elle designe le role
  -- qu'elle nomme. Un nom seul se libere et se reprend (6.3b6b, point 3).
  plan_nom := normative_control_plane();
  plan_oid := normative_control_plane_oid();
  if plan_nom is null or plan_oid is null then
    raise exception
      'le plan de controle est fige de facon incomplete (nom %, oid %)',
      coalesce(plan_nom, 'NULL'), coalesce(plan_oid::text, 'NULL');
  end if;
  if not exists (select 1 from pg_roles
                  where oid = plan_oid and rolname = plan_nom) then
    raise exception
      'le plan de controle fige (oid %, « % ») ne designe plus un role '
      'portant ce nom', plan_oid, plan_nom;
  end if;

  -- ET LE MIGRATEUR NE DETIENT PLUS RIEN. C'est ce que la phase 2 achete, et
  -- c'est la seule raison pour laquelle les ecritures normatives sont
  -- desormais ouvertes sur cette base.
  select migrateur_nom into mig_nom from normative_finalization_intent;
  if mig_nom is null then
    raise exception 'aucune intention de finalisation: l''activation ne dit '
                    'pas qui a migre';
  end if;
  if mig_nom = plan_nom then
    raise exception
      'le migrateur et le plan de controle sont le meme role (« % »): la '
      'separation serait nominale', mig_nom;
  end if;
  select count(*) into n from unnest(array['eurostruct_normative_writer',
                                           'eurostruct_normative_bootstrap',
                                           'eurostruct_normative_activator']) a(r)
   where pg_has_role(mig_nom, a.r, 'SET')
      or pg_has_role(mig_nom, a.r, 'USAGE')
      or pg_has_role(mig_nom, a.r, 'MEMBER WITH ADMIN OPTION');
  if n <> 0 then
    raise exception
      'le migrateur « % » conserve % capacite(s) sur les roles d''autorite '
      'APRES activation', mig_nom, n;
  end if;

  -- Et l'ecriture n'est ouverte a personne: l'activation ne passe que par la
  -- finalisation, qui verifie la topologie AVANT d'ecrire. Une activation
  -- posee a la main serait une activation non verifiee.
  declare r text;
  begin
    foreach r in array array['authenticated', 'normative_backend',
                             'normative_governance', 'public'] loop
      if has_table_privilege(r, 'normative_activation', 'INSERT')
         or has_table_privilege(r, 'normative_activation', 'UPDATE')
         or has_table_privilege(r, 'normative_activation', 'DELETE') then
        raise exception
          '% peut ecrire dans normative_activation: le sous-systeme '
          's''activerait sans qu''aucune topologie ne soit verifiee', r;
      end if;
    end loop;
  end;

  -- APPEND-ONLY, ET MEME POUR LE PROPRIETAIRE (6.3b6b, point 6): ni UPDATE ni
  -- DELETE, quel que soit le chemin. Le declencheur s'applique la ou l'ACL et
  -- les policies pourraient etre defaites par le proprietaire de la table.
  if not exists (select 1 from pg_trigger t
                   join pg_class c on c.oid = t.tgrelid
                  where c.relname = 'normative_activation'
                    and not t.tgisinternal
                    and t.tgtype & 28 <> 0) then
    raise exception
      'normative_activation ne porte aucun declencheur UPDATE/DELETE: '
      'detruire la ligne ramenerait le sous-systeme en PENDING sans trace, '
      'et une seconde activation reecrirait l''audit';
  end if;
  if exists (select 1 from pg_policy p join pg_class c on c.oid = p.polrelid
              where c.relname = 'normative_activation' and p.polcmd = '*') then
    raise exception
      'une policy FOR ALL couvre normative_activation: elle autorise UPDATE '
      'et DELETE au meme titre qu''INSERT';
  end if;
end
$$;


-- =====================================================================
-- 6.3b6a #6 — l'ETAT franchit la frontiere, la LIGNE ne la franchit pas
-- =====================================================================
-- La version precedente accordait `select` sur `normative_activation` a
-- `authenticated`. Ce n'est pas l'etat: c'est QUI a active, QUAND, et le
-- digest de topologie constate au deploiement — l'audit de deploiement, remis
-- a tout porteur de jeton. La lecture ouverte se justifiait pour « ACTIVE ou
-- PENDING », pas pour la ligne.
do $$
declare ok boolean := false; etat text;
begin
  set local role authenticated;

  -- Ce qui est REFUSE: la table.
  begin
    perform 1 from normative_activation;
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'authenticated lit directement normative_activation: activated_by, '
      'activated_at et topology_digest franchissent la frontiere alors que '
      'seul l''etat devait la franchir';
  end if;

  -- Ce qui est OUVERT: l'etat, par la vue minimale et par la fonction. Sans
  -- cette moitie, le refus ci-dessus serait satisfait par un sous-systeme
  -- devenu muet, et un client afficherait des resultats pre-activation sans
  -- pouvoir le savoir.
  -- ACTIVE, parce que `run.sh` deploie cette base en deux phases. Ce qui
  -- compte ici n'est pas la valeur mais le fait qu'elle FRANCHISSE la
  -- frontiere alors que la ligne, elle, vient d'etre refusee.
  select state into etat from normative_activation_status;
  if etat is distinct from 'ACTIVE' then
    raise exception
      'la vue rend « % » alors que la base est finalisee: ACTIVE attendu', etat;
  end if;
  if normative_activation_state() is distinct from 'ACTIVE' then
    raise exception 'normative_activation_state() ne rend pas ACTIVE';
  end if;
end
$$;
reset role;

-- Et la vue n'expose QUE l'etat. Une colonne ajoutee demain rouvrirait en
-- silence ce que le controle precedent vient de fermer.
do $$
declare cols text;
begin
  select string_agg(column_name, ',' order by ordinal_position) into cols
    from information_schema.columns
   where table_schema = 'public' and table_name = 'normative_activation_status';
  if cols is distinct from 'state' then
    raise exception
      'normative_activation_status expose « % » au lieu de la seule colonne '
      '« state »: la vue minimale a cesse d''etre minimale', cols;
  end if;
end
$$;


-- =====================================================================
-- 6.3b6a #5 — LES DECLARATIONS DE DEPLOIEMENT NE SONT PAS FORGEABLES
-- =====================================================================
-- Trois declarations decident de refus de topologie:
--
--     eurostruct.approved_service_logins
--     eurostruct.token_roles
--     eurostruct.approved_deployment_roles
--
-- Elles etaient lues par `current_setting('...', true)`, qui rend la valeur
-- EFFECTIVE de la session. N'importe quel role — y compris `authenticated` —
-- n'avait donc qu'a poser
--
--     SET eurostruct.approved_service_logins = 'moi';
--
-- pour faire passer au vert un controle de readiness qui devait refuser. Le
-- meme defaut, exactement, que le marqueur d'audit de 6.3b3: un parametre de
-- session est une declaration de l'appelant, jamais une preuve.
--
-- Elles sont desormais lues dans `pg_db_role_setting` — ce que le DEPLOIEMENT
-- a pose par `ALTER DATABASE ... SET`. Un `SET` de session n'y figure pas.
--
-- LE CONTRE-EXEMPLE EST JOUE DANS LA MEME TRANSACTION, et c'est sa forme la
-- plus forte: la valeur est posee PAR `authenticated`, puis lue par le role de
-- readiness sans que la session ait ete quittee. Si la lecture declaree
-- bougeait, elle bougerait ici.
do $$
declare n text; lu text;
begin
  foreach n in array array['eurostruct.approved_service_logins',
                           'eurostruct.token_roles',
                           'eurostruct.approved_deployment_roles'] loop
    -- Le role applicatif POSE la valeur, comme un attaquant le ferait.
    set local role authenticated;
    perform set_config(n, 'FICTIF_role_qui_se_declare', true);

    -- `current_setting` la voit — c'est bien la preuve que la session a ete
    -- modifiee, et donc que ce test exerce reellement le contre-exemple.
    if current_setting(n, true) is distinct from 'FICTIF_role_qui_se_declare' then
      raise exception
        'le SET de session sur % n''a pas pris: le contre-exemple vise n''est '
        'pas reproduit et ce controle ne prouverait rien', n;
    end if;

    -- La lecture est faite HORS du role applicatif: `normative_declared_setting`
    -- ne lui est pas executable — c'est meme l'un des points du correctif — et
    -- la readiness s'exerce sous le role de deploiement. Le parametre de
    -- session, lui, reste pose: la transaction n'a pas change.
    reset role;
    lu := normative_declared_setting(n);
    if lu = 'FICTIF_role_qui_se_declare' then
      raise exception
        'normative_declared_setting(%) rend la valeur posee par la SESSION: '
        'un role applicatif se declare lui-meme approuve et fait passer au '
        'vert un refus de topologie', n;
    end if;
  end loop;
end
$$;
reset role;

-- La fonction n'est appelable par aucun role applicatif — verifie par la
-- garantie generale `t_garantie_execute()` plus haut, qui couvre toute
-- fonction `%normative%` du schema public sauf la seule signature exemptee.
-- Rien n'est reecrit ici: une seconde liste divergerait de la premiere.


-- =====================================================================
-- 6.3b6a #4 — LE PLAN DE CONTROLE NE PEUT PAS SE DESIGNER LUI-MEME
-- =====================================================================
-- L'identite du plan de controle etait portee par `eurostruct.control_plane`,
-- un GUC de session: le role qu'il s'agissait de contenir pouvait le poser
-- lui-meme et s'exempter. Elle est desormais DERIVEE du `grantor` de l'octroi
-- temporaire — un fait que PostgreSQL inscrit seul dans `pg_auth_members` —
-- puis FIGEE dans un singleton immuable.
do $$
declare r text; ok boolean;
begin
  -- FIGE PAR LA PHASE 2, ET SEULEMENT PAR ELLE.
  --
  -- Ce controle exigeait l'inverse — « aucun plan de controle apres la seule
  -- migration » — parce que la base principale n'etait alors que migree. Elle
  -- est desormais deployee en deux phases par `run.sh`. La propriete « la
  -- migration seule ne fige rien » se mesure entre les deux phases, et
  -- `two_phase_deployment.sh` comme `finalisation_contract.sh` l'exigent.
  --
  -- Ce qui est verifie ici: l'identite figee est COMPLETE et designe le role
  -- qu'elle nomme. NULL n'exempterait personne — comportement fail-closed —
  -- mais un nom sans OID exempterait quiconque reprendrait ce nom.
  if normative_control_plane() is null or normative_control_plane_oid() is null then
    raise exception
      'le plan de controle n''est pas fige apres la phase 2 (nom %, oid %): '
      'l''exemption d''ADMIN residuel ne designerait aucun role',
      coalesce(normative_control_plane(), 'NULL'),
      coalesce(normative_control_plane_oid()::text, 'NULL');
  end if;

  -- Aucun role applicatif ne lit ni n'ecrit le singleton.
  foreach r in array array['public', 'authenticated', 'normative_backend'] loop
    if has_table_privilege(r, 'normative_control_plane', 'SELECT')
       or has_table_privilege(r, 'normative_control_plane', 'INSERT')
       or has_table_privilege(r, 'normative_control_plane', 'UPDATE')
       or has_table_privilege(r, 'normative_control_plane', 'DELETE') then
      raise exception
        '% atteint normative_control_plane: le detenteur de l''ADMIN residuel '
        'n''aurait qu''a s''y ecrire pour devenir « le plan approuve »', r;
    end if;
    if has_function_privilege(r, 'normative_control_plane()', 'EXECUTE') then
      raise exception '% peut executer normative_control_plane()', r;
    end if;
  end loop;
end
$$;

-- IMMUABLE, et verifie EN AGISSANT — pas seulement en lisant des ACL. Le
-- superutilisateur du harnais tient ici le role du pire cas: meme lui ne
-- reecrit pas la ligne.
--
-- LES TENTATIVES PORTENT SUR LA VRAIE LIGNE, celle que la phase 2 a figee.
-- La version precedente inserait un TEMOIN puis, pour le retirer, DESACTIVAIT
-- le declencheur d'immuabilite d'une table de confiance et vidait la table —
-- c'est-a-dire qu'elle executait, dans la suite de tests, exactement le geste
-- contre lequel cette table existe. Sur une base finalisee, elle aurait
-- efface le plan de controle approuve. Rien n'est plus insere, donc rien n'est
-- a retirer, et le declencheur n'est jamais desarme.
do $$
declare ok boolean; avant text; apres text;
begin
  select role_oid::text || '/' || role_name into avant from normative_control_plane;

  ok := false;
  begin
    update normative_control_plane set role_name = 'FICTIF_usurpateur';
  exception when others then ok := (sqlstate = '38000' or sqlstate = '2F004'
                                    or sqlerrm like '%fige a l''installation%');
  end;
  if not ok then
    raise exception
      'le plan de controle a ete REECRIT: le detenteur de l''ADMIN residuel '
      'se designe lui-meme comme approuve';
  end if;

  ok := false;
  begin
    delete from normative_control_plane;
  exception when others then ok := (sqlerrm like '%fige a l''installation%');
  end;
  if not ok then
    raise exception
      'le plan de controle a ete EFFACE: il suffirait de l''effacer puis de '
      'le reecrire a son nom';
  end if;

  -- Et une SECONDE ligne est impossible: « exactement un » se tient par la
  -- cle primaire, pas par convention.
  ok := false;
  begin
    insert into normative_control_plane (role_oid, role_name, recorded_by)
    values (0, 'FICTIF_second_plan', session_user);
  exception when unique_violation then ok := true;
  end;
  if not ok then
    raise exception
      'deux plans de controle coexistent: l''exemption d''ADMIN residuel ne '
      'designerait plus un role unique';
  end if;

  -- ET LA LIGNE APPROUVEE EST INTACTE. Les trois tentatives ci-dessus ont ete
  -- refusees; il reste a constater qu'aucune n'a laisse de trace, sans quoi
  -- « refuse » pourrait signifier « refuse apres avoir ecrit ».
  select role_oid::text || '/' || role_name into apres from normative_control_plane;
  if apres is distinct from avant then
    raise exception
      'le plan de controle a change pendant les tentatives: « % » -> « % »',
      avant, apres;
  end if;
end
$$;


-- =====================================================================
-- 6.3b3 — le marqueur d'origine n'est pas forgeable
-- =====================================================================
-- CONTRE-EXEMPLE VERIFIE ROUGE contre 6.3b2: la reserve du namespace lisait
-- un GUC pose par `set_config('eurostruct.normative_audit', 'on', true)`.
-- N'importe quel role autorise a ecrire un evenement ORDINAIRE posait le
-- marqueur lui-meme et fabriquait une trace « normative.* » — que le
-- declencheur d'immuabilite rendait ensuite ineffacable. Un parametre de
-- session est une declaration de l'appelant, jamais une preuve d'origine.
--
-- MODELE DE MENACE, explicite. Ces garanties visent les ROLES APPLICATIFS.
-- Un superutilisateur PostgreSQL peut desactiver les declencheurs, changer le
-- proprietaire d'une fonction ou ecrire directement dans les catalogues: il
-- n'est pas un adversaire que la base peut contenir, et pretendre le contraire
-- donnerait une fausse assurance. Ce qui est garanti ici: aucun role
-- applicatif — y compris un role dote de droits d'ecriture sur le journal —
-- ne peut fabriquer une trace normative.
--
-- Le role fictif ci-dessous EXISTE pour le test: il incarne le jour ou
-- quelqu'un ouvrira l'ecriture du journal pour une raison legitime et sans
-- rapport. La protection ne doit pas dependre du fait que ce jour n'est pas
-- arrive.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'fictif_journal_app') then
    create role fictif_journal_app nologin;
  end if;
end
$$;

grant insert, select on audit_log to fictif_journal_app;
grant usage on sequence audit_log_id_seq to fictif_journal_app;

-- Policy DELIBEREMENT permissive: `with check (true)`. Une policy qui
-- filtrerait elle-meme « normative.% » prouverait la policy, pas le
-- declencheur — et c'est le declencheur qui doit tenir.
create policy fictif_journal_ecriture_ordinaire on audit_log
  for insert to fictif_journal_app with check (true);

do $$
declare ok boolean;
begin
  set local role fictif_journal_app;

  -- 1. Le role ecrit REELLEMENT un evenement ordinaire. Sans cette moitie, le
  --    refus ci-dessous pourrait n'etre qu'une absence de privilege, et le
  --    test passerait pour une raison qui n'est pas celle qu'on croit.
  --
  --    Sans `returning`: la clause exige en plus la policy de LECTURE, et
  --    `audit_read` demande un org_id dont ce role n'est pas membre. Le
  --    constat que la ligne existe se fait donc apres `reset role`.
  insert into audit_log (action, entity, payload)
  values ('project.exported', 'projects', '{"FICTIF": "evenement ordinaire"}'::jsonb);

  -- 2. Le marqueur de l'ancienne version, pose par l'appelant lui-meme.
  perform set_config('eurostruct.normative_audit', 'on', true);
  ok := false;
  begin
    insert into audit_log (action, entity, payload)
    values ('normative.authorisation.granted', 'normative_authorisation_grants',
            '{"FICTIF": "octroi fabrique a la main"}'::jsonb);
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'marqueur d''audit forge par set_config: ACCEPTE. Un role applicatif '
      'fabriquerait la preuve d''un octroi qu''aucun administrateur n''a '
      'consenti, et elle serait ensuite immuable';
  end if;

  -- 3. Meme refus pour les autres actions du namespace: la reserve porte sur
  --    le prefixe, pas sur une liste d'actions qu'on oublierait d'etendre.
  ok := false;
  begin
    insert into audit_log (action, entity, payload)
    values ('normative.confirmation.created', 'normative_rule_confirmations',
            '{"FICTIF": true}'::jsonb);
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception 'trace « normative.confirmation.created » fabriquee';
  end if;

  -- 4. Et le role ne peut pas EMPRUNTER l'autorite: c'est ce qui rend
  --    `current_user` non forgeable. Si l'appartenance existait, tout le
  --    raisonnement tomberait.
  if pg_has_role('fictif_journal_app', 'eurostruct_normative_writer', 'usage')
  then
    raise exception
      'un role applicatif est membre de eurostruct_normative_writer: il '
      'pourrait prendre l''autorite et le marqueur redeviendrait forgeable';
  end if;
end
$$;
reset role;

-- La moitie positive du controle: l'evenement ORDINAIRE est bien passe, et
-- aucune trace normative n'a ete fabriquee. Sans ce constat, les refus
-- ci-dessus seraient satisfaits par un role qui ne peut rien ecrire du tout.
do $$
declare n bigint;
begin
  select count(*) into n from audit_log
   where action = 'project.exported'
     and payload = '{"FICTIF": "evenement ordinaire"}'::jsonb;
  if n <> 1 then
    raise exception
      'le role applicatif fictif n''a ecrit aucun evenement ordinaire (% '
      'ligne(s)): les refus obtenus ne prouvent alors qu''une absence de '
      'privilege', n;
  end if;

  select count(*) into n from audit_log
   where action like 'normative.%' and payload ? 'FICTIF';
  if n <> 0 then
    raise exception '% trace(s) normative(s) fabriquee(s) par un role applicatif', n;
  end if;
end
$$;

-- Nettoyage: le role est un objet de CLUSTER, pas de base. Le laisser
-- derriere ferait echouer la creation a l'execution suivante — et un test
-- non rejouable ne protege rien.
delete from audit_log
 where action = 'project.exported'
   and payload = '{"FICTIF": "evenement ordinaire"}'::jsonb;
drop policy fictif_journal_ecriture_ordinaire on audit_log;
revoke all on audit_log from fictif_journal_app;
revoke all on sequence audit_log_id_seq from fictif_journal_app;
drop role fictif_journal_app;

-- Aucun role applicatif ne detient l'autorite, et aucun n'en est membre.
do $$
declare r text;
begin
  foreach r in array array['authenticated', 'normative_backend',
                           'normative_governance'] loop
    if pg_has_role(r, 'eurostruct_normative_writer', 'usage')
       or pg_has_role(r, 'eurostruct_normative_bootstrap', 'usage') then
      raise exception '% est membre d''un role d''autorite normative', r;
    end if;
  end loop;

  -- Les roles d'autorite sont NOLOGIN et sans droit de connexion: personne ne
  -- s'y authentifie, personne ne les prend.
  foreach r in array array['eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap'] loop
    if exists (select 1 from pg_roles
                where rolname = r and (rolcanlogin or rolsuper)) then
      raise exception
        '% peut se connecter ou est superutilisateur: current_user cesserait '
        'd''etre une preuve d''origine', r;
    end if;
  end loop;
end
$$;


-- =====================================================================
-- 6.3b3 — invariants structurels du dossier de preuve
-- =====================================================================
-- CONTRE-EXEMPLE VERIFIE ROUGE contre 6.3b2: `items: [1]`, un
-- `schema_version` de pile inconnu et un `quote_digest` absent etaient tous
-- ACCEPTES. Une empreinte juste sur une structure absurde reste une empreinte
-- juste: elle scelle le vide.
--
-- Les payloads sont substitues AVANT le calcul des empreintes, donc chaque
-- refus ci-dessous vient de l'invariant vise et non du controle d'integrite.
do $$
declare ok boolean; cas record;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  for cas in
    select * from (values
      -- `items: [1]`: un entier n'est pas un element de preuve.
      ('element scalaire',
       '{"canonicalization_version":"esc-canon/1","items":[1],"kind":"evidence"}'),
      -- Element objet mais VIDE.
      ('element sans aucune cle',
       '{"canonicalization_version":"esc-canon/1","items":[{}],"kind":"evidence"}'),
      -- Toutes les cles sauf `quote_digest`: la citation n'est plus scellee.
      ('quote_digest absent',
       '{"canonicalization_version":"esc-canon/1","items":[{"clause":"§9.2.2(5)",'
       '"document_digest":"' || repeat('b', 64) || '","document_role":"annexe",'
       '"edition":"2010","page_printed":15,"quote":"FICTIF — citation.",'
       '"reference":"FICTIF ANB"}],"kind":"evidence"}'),
      -- Folio absent: on ne saurait pas quelle page rouvrir.
      ('page_printed absent',
       '{"canonicalization_version":"esc-canon/1","items":[{"clause":"§9.2.2(5)",'
       '"document_digest":"' || repeat('b', 64) || '","document_role":"annexe",'
       '"edition":"2010","quote":"FICTIF — citation.","quote_digest":"'
       || encode(sha256(convert_to('FICTIF — citation.', 'UTF8')), 'hex')
       || '","reference":"FICTIF ANB"}],"kind":"evidence"}'),
      -- quote_digest PRESENT mais faux: texte retouche sans recalcul.
      ('quote_digest ne resume pas la citation',
       '{"canonicalization_version":"esc-canon/1","items":[{"clause":"§9.2.2(5)",'
       '"document_digest":"' || repeat('b', 64) || '","document_role":"annexe",'
       '"edition":"2010","page_printed":15,"quote":"FICTIF — citation RETOUCHEE.",'
       '"quote_digest":"'
       || encode(sha256(convert_to('FICTIF — citation.', 'UTF8')), 'hex')
       || '","reference":"FICTIF ANB"}],"kind":"evidence"}'),
      -- Liste vide: confirmer sans rien avoir lu.
      ('aucun element',
       '{"canonicalization_version":"esc-canon/1","items":[],"kind":"evidence"}'),
      -- `items` n'est meme pas un tableau.
      ('items n''est pas un tableau',
       '{"canonicalization_version":"esc-canon/1","items":{"a":1},"kind":"evidence"}')
    ) as v(nom, payload)
  loop
    ok := false;
    begin
      perform t_confirmer(p_rule => 'test.structure',
                          p_ev_payload => cas.payload,
                          p_idem => 'FICTIF-struct-' || cas.nom);
    exception when check_violation then ok := true;
    end;
    if not ok then
      raise exception
        'dossier de preuve accepte alors que: %. Une empreinte juste sur une '
        'structure absurde scelle le vide.', cas.nom;
    end if;
  end loop;
end
$$;

-- Version de schema de pile inconnue, et version de canonicalisation
-- inconnue. La grille de lecture de la pile sert a extraire l'edition
-- d'annexe dont depend le controle de portee: la lire avec la mauvaise
-- grille donnerait une portee fausse sans rien signaler.
do $$
declare ok boolean; pile text;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);

  pile := replace(t_paquet('test.structure') ->> 'stack',
                  '"schema_version":"esc-stack/1"',
                  '"schema_version":"esc-stack/999"');
  if pile = (t_paquet('test.structure') ->> 'stack') then
    raise exception 'la substitution de schema_version n''a rien remplace';
  end if;

  ok := false;
  begin
    perform t_confirmer(p_rule => 'test.structure', p_stack_payload => pile,
                        p_idem => 'FICTIF-struct-schema');
  exception when check_violation then ok := true;
  end;
  if not ok then
    raise exception
      'schema_version de pile inconnu: ACCEPTE. L''edition d''annexe serait '
      'extraite avec une grille qui n''est pas la sienne';
  end if;
end
$$;

-- Le chemin NORMAL reste ouvert: sans ces substitutions, la meme regle passe.
-- Sans cette moitie, les sept refus ci-dessus seraient satisfaits par un
-- serveur qui refuse tout.
do $$
declare c record;
begin
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  perform t_confirmer(p_rule => 'test.structure', p_idem => 'FICTIF-struct-ok');
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-struct-ok';
  if c.id is null then
    raise exception
      'le dossier de preuve BIEN FORME est lui aussi refuse: les invariants '
      'structurels ne discriminent rien';
  end if;
  if jsonb_array_length(c.evidence_items) <> 1 then
    raise exception 'evidence_items derive: % element(s)',
      jsonb_array_length(c.evidence_items);
  end if;
end
$$;


-- =====================================================================
-- 6.3b3 — frontiere d'ecriture: l'insertion brute est revoquee
-- =====================================================================
-- La question restait indecise: un utilisateur authentifie pouvait-il inserer
-- lui-meme dans les quatre tables, en s'en remettant aux declencheurs? La
-- reponse retenue est NON. Les declencheurs restent la deuxieme ligne, mais
-- la premiere est l'ACL: `authenticated` n'a aucun INSERT, et l'ecriture
-- passe par le role de service.
do $$
declare t text; ok boolean;
begin
  foreach t in array array['normative_authorisation_grants',
                           'normative_authorisation_revocations',
                           'normative_rule_confirmations',
                           'normative_rule_confirmation_revocations'] loop
    if has_table_privilege('authenticated', t, 'INSERT') then
      raise exception
        'authenticated detient INSERT sur %: la frontiere d''ecriture passe '
        'par le role de service, pas par le porteur de jeton', t;
    end if;
    -- Et il n'obtient pas ce droit par appartenance a un role qui l'a.
    if pg_has_role('authenticated', 'normative_backend', 'usage') then
      raise exception
        'authenticated est membre de normative_backend: la revocation de '
        'l''insertion brute serait contournee par heritage';
    end if;
  end loop;
end
$$;

-- Et l'ACL est constatee A L'EXECUTION, pas seulement dans le catalogue.
do $$
declare ok boolean := false;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, reason)
    values ('66666666-6666-6666-6666-666666666666', 'FICTIF Auto-octroi',
            'can_validate_normative_reference',
            'FICTIF — insertion brute par un porteur de jeton.');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'un utilisateur authentifie a insere directement un octroi normatif';
  end if;
end
$$;
reset role;


-- =====================================================================
-- 6.3b2 — RLS complementaire
-- =====================================================================
-- Le signataire doit voir qu'un TIERS a revoque sa confirmation. Ne montrer
-- une revocation qu'a son auteur laissait un relecteur decouvrir la
-- disparition de son regard sans savoir ni par qui ni pourquoi.
do $$
declare n bigint;
begin
  set local role authenticated;
  perform set_config('request.jwt.claim.sub',
                     '55555555-5555-5555-5555-555555555555', true);
  select count(*) into n
    from normative_rule_confirmation_revocations r
    join normative_rule_confirmations c on c.id = r.confirmation_id
   where c.verifier_id = '55555555-5555-5555-5555-555555555555'
     and r.revoked_by <> '55555555-5555-5555-5555-555555555555';
  if n = 0 then
    raise exception
      'le signataire ne voit aucune revocation de SES confirmations par un '
      'tiers: son regard disparaitrait du decompte sans explication';
  end if;
end
$$;
reset role;

-- Aucun UPDATE ni DELETE, sur les QUATRE tables et pour TOUS les roles.
do $$
declare t text; role_nom text;
begin
  foreach t in array array['normative_authorisation_grants',
                           'normative_authorisation_revocations',
                           'normative_rule_confirmations',
                           'normative_rule_confirmation_revocations'] loop
    if exists (select 1 from pg_policies
                where schemaname = 'public' and tablename = t
                  and cmd in ('UPDATE', 'DELETE')) then
      raise exception 'une policy UPDATE/DELETE existe sur %', t;
    end if;
    foreach role_nom in array array['authenticated', 'normative_backend',
                                    'normative_governance', 'public'] loop
      if has_table_privilege(role_nom, t, 'UPDATE')
         or has_table_privilege(role_nom, t, 'DELETE')
         or has_table_privilege(role_nom, t, 'TRUNCATE') then
        raise exception '% detient UPDATE, DELETE ou TRUNCATE sur %',
          role_nom, t;
      end if;
    end loop;
  end loop;
end
$$;


drop function t_confirmer(text, country_code, text, text, text, text, text,
                          boolean, uuid, timestamptz, uuid, jsonb,
                          jsonb, jsonb, text, country_code, boolean,
                          text, text);
drop function t_paquet(text, country_code, text, text, text);

\echo ''
\echo '================================================='
\echo ' Confirmation normative: autorisations, immuabilite et'
\echo ' integrite des empreintes verifiees.'
\echo '================================================='
