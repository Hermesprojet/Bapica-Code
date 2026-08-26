-- =====================================================================
-- 0013 — FRONTIERE D'AUTHENTIFICATION FAIL-CLOSED, ET AMORCAGE MANDATE
-- =====================================================================
--
-- CE QUE 6.3c A MESURE, ET QUE CETTE MIGRATION FERME
-- ---------------------------------------------------
-- Quatre ouvertures sur quatorze attaques, et elles se ramenaient a deux
-- causes:
--
--   I-1  l'identite de DEPLOIEMENT choisit librement le premier administrateur
--        normatif: `p_grantee` est un parametre, et rien ne relie ce choix a
--        une decision tracee hors du systeme (attaque 1).
--
--   I-2  `auth.uid()` lit `request.jwt.claim.sub`, un parametre de
--        configuration a nom qualifie que TOUT role peut poser par un simple
--        `SET`. Le serveur inscrit dans `granted_by` la valeur que la session
--        a DECLAREE (attaque 4). Deux valeurs successives depuis UNE connexion
--        fabriquent deux « paternites » distinctes, ce qui est exactement la
--        premisse du decompte a quatre yeux (attaques 6 et 12).
--
-- CE QU'IL NE FAUT PAS FAIRE, ET POURQUOI
-- ----------------------------------------
-- Durcir le GUC ne sert a rien. Qu'il s'appelle `request.jwt.claim.sub` ou
-- `app.actor_id`, un parametre de session reste positionnable par quiconque
-- tient la connexion. Le renommer, le prefixer, le verifier « mieux »: aucune
-- de ces mesures ne change le fait qu'il est DECLARE.
--
-- LA SEULE DEFENSE STRUCTURELLE est que le role SQL ordinaire N'ATTEIGNE PAS
-- la primitive, meme apres avoir falsifie le GUC. C'est un probleme de
-- PRIVILEGE, pas de format de valeur.
--
-- LA FRONTIERE POSEE ICI
-- -----------------------
--   1. `eurostruct_authority_backend` — role d'execution privilegie, NOLOGIN,
--      SEUL a detenir INSERT sur les tables d'autorite. Les roles applicatifs
--      le perdent.
--   2. Il n'est detenu que par les logins DECLARES par le deploiement, dans
--      `eurostruct.authority_backend_logins`, lue par `normative_declared_setting`
--      — c'est-a-dire dans `pg_db_role_setting`, et JAMAIS par
--      `current_setting()` qu'un `SET` de session suffirait a forger.
--   3. `normative_authenticated_actor()` — l'acteur, lu depuis le contexte de
--      session, mais SEULEMENT si la session atteint effectivement le role
--      d'autorite. Un role ordinaire qui pose le GUC obtient
--      `insufficient_privilege`, pas une identite.
--   4. FAIL-CLOSED. Sans authentificateur DECLARE, aucune operation d'autorite
--      n'est possible: la fonction leve `BLOCKED_BY_REAL_AUTH`. Le produit ne
--      simule pas une authentification qu'il n'a pas.
--
-- CE QUI RESTE HORS DE PORTEE, ET QUI EST DIT PLUTOT QUE MASQUE
-- --------------------------------------------------------------
-- Ceci ne fabrique PAS une authentification. Aucun verificateur de jeton
-- n'existe dans ce depot. Ce qui est pose est une FRONTIERE INJECTABLE: le
-- backend authentifie est declare, il est le seul a pouvoir agir, et tant
-- qu'aucun ne l'est, rien ne peut agir. La garantie « c'est bien CETTE
-- personne » reste `BLOCKED_BY_REAL_AUTH` — et le schema le DIT desormais, au
-- lieu de laisser croire que `auth.uid()` l'etablissait.
-- =====================================================================

grant create on schema public
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- ---------------------------------------------------------------------
-- A. LE CONTRAT D'AUTHENTIFICATION, DECLARE ET GELE
-- ---------------------------------------------------------------------
-- MEME PRINCIPE QUE LE SCEAU, ET POUR LA MEME RAISON. `normative_declared_setting`
-- lit `pg_db_role_setting`: la valeur vient d'un `ALTER DATABASE ... SET`, que
-- seul le proprietaire de la base peut emettre, et qu'aucun `SET` de session
-- ne peut couvrir. C'est la seule source « externe » dont dispose une base
-- PostgreSQL sans sortir d'elle-meme.
--
-- POURQUOI UNE TABLE A COTE PLUTOT QUE LES TROIS DECLARATIONS DU SCEAU. Le
-- sceau fige exactement trois noms, cables dans son manifeste, dans sa
-- contrainte `check` et dans une boucle `for n in 1 .. 3`. Y ajouter deux
-- entrees changerait le digest d'activation de toute base existante et
-- toucherait un composant clos en 6.3b6d — pour un gain nul: le principe se
-- reproduit ici a l'identique, sans rien deplacer.
create table if not exists normative_authentication_contract (
  nom      text primary key,
  valeur   text not null,
  constate_par text not null,
  constate_le  timestamptz not null default now(),
  constraint auth_contract_nom_connu
    check (nom in ('eurostruct.authority_backend_logins',
                   'eurostruct.bootstrap_mandate'))
);

comment on table normative_authentication_contract is
  'Les deux declarations d''authentification, CONSTATEES au deploiement puis '
  'figees. Apres constat, le code les lit ICI et non dans pg_db_role_setting: '
  'le proprietaire de la base ne peut plus se re-declarer authentificateur '
  'par un ALTER DATABASE tardif.';

-- PROPRIETAIRE ET POLICIES, ET NON PAS SEULEMENT « FORCE RLS ».
--
-- MESURE: sans ce bloc, 0013 se refuse elle-meme sur « permission denied for
-- table normative_authentication_contract » a son propre constat. La table
-- naissait propriete du MIGRATEUR, et `FORCE ROW LEVEL SECURITY` s'applique
-- AUSSI au proprietaire — c'est tout son interet. Sans policy, plus personne
-- n'ecrit, pas meme la fonction SECURITY DEFINER censee la remplir.
--
-- `FORCE` sans policy n'est pas « tres ferme »: c'est ferme a tout le monde,
-- y compris a soi-meme.
alter table normative_authentication_contract
  owner to eurostruct_normative_writer;
alter table normative_authentication_contract enable row level security;
alter table normative_authentication_contract force row level security;

create policy auth_contract_writer on normative_authentication_contract
  for all to eurostruct_normative_writer using (true) with check (true);
-- L'AMORCAGE LIT LE MANDAT: `normative_bootstrap_mandate()` lui appartient.
-- UNE POLICY NE REMPLACE PAS UN PRIVILEGE. Les deux sont necessaires et ne
-- disent pas la meme chose: le privilege ouvre la table, la policy filtre les
-- lignes. Mesure: sans le GRANT, l'amorcage recevait « permission denied for
-- table normative_authentication_contract » — une erreur de PRIVILEGE — alors
-- que la policy etait bien posee.
grant select on normative_authentication_contract
  to eurostruct_normative_bootstrap;
create policy auth_contract_bootstrap_read on normative_authentication_contract
  for select to eurostruct_normative_bootstrap using (true);
grant select on normative_authentication_contract to normative_governance;
create policy auth_contract_governance_read on normative_authentication_contract
  for select to normative_governance using (true);

create or replace function forbid_auth_contract_mutation() returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  raise exception
    'le contrat d''authentification est fige: une declaration constatee ne se '
    'modifie ni ne s''efface. Redeployer sur une base neuve.'
    using errcode = 'insufficient_privilege';
end;
$$;

create trigger auth_contract_is_immutable
  before update or delete on normative_authentication_contract
  for each row execute function forbid_auth_contract_mutation();


-- ---------------------------------------------------------------------
-- B. LE ROLE D'EXECUTION PRIVILEGIE
-- ---------------------------------------------------------------------
-- IL EST CREE ICI ET NON DANS LE SCEAU, et c'est un choix qu'il faut assumer:
-- le sceau cree les SIX roles canoniques que `assert_normative_topology()`
-- surveille, et y ajouter un septieme changerait le digest de topologie de
-- toute base deja activee. Celui-ci n'est pas un role d'AUTORITE — il ne
-- possede rien, ne signe rien, et n'apparait dans aucune chaine de delegation.
-- C'est un role d'EXECUTION: il porte le droit d'ECRIRE, rien d'autre.
--
-- Il est NOLOGIN: personne ne s'y connecte. Il s'obtient par appartenance, et
-- seulement pour les logins declares au point A.
-- IL N'EST PLUS CREE ICI, ET C'EST LE CORRECTIF D'UN DEFAUT MESURE.
--
-- Une premiere version le creait depuis cette migration. Or `CREATE ROLE` par
-- un role CREATEROLE confere au createur l'ADMIN OPTION sur le role cree: le
-- MIGRATEUR devenait donc capable d'enroler qui il voulait dans le role qui
-- detient INSERT sur les tables d'autorite — y compris lui-meme.
--
-- Sonde sur une base deployee, avant correction:
--
--   membres reels de eurostruct_authority_backend : <le migrateur>
--   declaration figee                             : <le login de service>
--   GRANT par le migrateur vers un login ordinaire: ABOUTIT
--   INSERT du login ordinaire sur les octrois     : t
--
-- C'est la contenance que 6.3b6c avait fermee, rouverte par la porte d'a
-- cote. Le role est desormais cree par le PLAN DE CONTROLE, en phase 0, comme
-- les six roles canoniques. Cette migration se contente d'exiger sa presence:
-- l'absence signale un sceau trop ancien, et un deploiement muet vaut mieux
-- qu'un deploiement qui recree le trou.
do $$
begin
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_authority_backend') then
    raise exception
      'le role « eurostruct_authority_backend » est absent. Il est cree par la '
      'PHASE 0 (control_plane/0001_normative_seal.sql). Le creer ici donnerait '
      'au migrateur l''ADMIN sur le role qui detient INSERT sur les tables '
      'd''autorite: appliquer un sceau a jour avant cette migration.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- C. L'ACTEUR AUTHENTIFIE — et le refus quand rien ne l'authentifie
-- ---------------------------------------------------------------------
-- ELLE NE REMPLACE PAS `auth.uid()` PAR UN AUTRE GUC. Elle ajoute la seule
-- chose qui manquait: la verification que la SESSION a le droit d'affirmer une
-- identite. Le GUC reste le transport — il n'y en a pas d'autre en SQL — mais
-- il n'est plus cru de la part de n'importe qui.
--
-- TROIS REFUS DISTINCTS, et ils ne disent pas la meme chose:
--   * pas d'authentificateur declare  -> BLOCKED_BY_REAL_AUTH, le deploiement
--     est incomplet;
--   * session non habilitee a affirmer -> insufficient_privilege, l'appelant
--     n'est pas le backend authentifie;
--   * aucun acteur dans le contexte    -> insufficient_privilege, le backend
--     n'a pas authentifie avant d'agir.
-- Les fondre en un seul message ferait perdre a l'exploitant la seule
-- information qui distingue « mal deploye » de « mal appele ».
create or replace function normative_authentication_configured() returns boolean
language sql
stable
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from normative_authentication_contract
     where nom = 'eurostruct.authority_backend_logins'
       and btrim(valeur) <> '');
$$;

alter function normative_authentication_configured()
  owner to eurostruct_normative_writer;
revoke all on function normative_authentication_configured() from public;
grant execute on function normative_authentication_configured()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap,
     normative_governance;

create or replace function normative_authenticated_actor() returns uuid
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  brut text;
  acteur uuid;
begin
  if not normative_authentication_configured() then
    raise exception
      'BLOCKED_BY_REAL_AUTH: aucun backend authentifie n''est declare pour '
      'cette base. Aucune operation d''autorite normative n''est possible tant '
      'que « eurostruct.authority_backend_logins » n''a pas ete declaree et '
      'constatee. Le produit ne simule pas une authentification qu''il n''a '
      'pas.'
      using errcode = 'insufficient_privilege';
  end if;

  -- LA SESSION DOIT ATTEINDRE LE ROLE D'EXECUTION PRIVILEGIE. `session_user`
  -- et non `current_user`: cette fonction est SECURITY DEFINER, `current_user`
  -- y vaut donc son proprietaire quel que soit l'appelant, et le tester
  -- reviendrait a se demander a soi-meme si l'on est soi-meme.
  if not pg_has_role(session_user, 'eurostruct_authority_backend', 'USAGE') then
    raise exception
      'identite refusee: la session « % » n''est pas le backend authentifie. '
      'Poser un parametre de session ne fait pas une identite — il faut '
      'detenir le role d''execution privilegie, et il n''est accorde qu''aux '
      'logins declares.', session_user
      using errcode = 'insufficient_privilege';
  end if;

  brut := nullif(btrim(coalesce(
            current_setting('eurostruct.actor_id', true), '')), '');
  if brut is null then
    raise exception
      'aucun acteur dans le contexte: le backend authentifie doit poser '
      '« SET LOCAL eurostruct.actor_id » APRES avoir authentifie, et avant '
      'toute operation d''autorite.'
      using errcode = 'insufficient_privilege';
  end if;

  begin
    acteur := brut::uuid;
  exception when others then
    raise exception 'contexte d''acteur illisible: « % » n''est pas un uuid.',
      left(brut, 64)
      using errcode = 'insufficient_privilege';
  end;
  return acteur;
end;
$$;

alter function normative_authenticated_actor()
  owner to eurostruct_normative_writer;
revoke all on function normative_authenticated_actor() from public;
grant execute on function normative_authenticated_actor()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

comment on function normative_authenticated_actor is
  'L''acteur, lu dans le contexte de session MAIS seulement si la session '
  'atteint le role d''execution privilegie. Un role ordinaire qui pose le GUC '
  'obtient un refus, pas une identite. Sans authentificateur declare: '
  'BLOCKED_BY_REAL_AUTH.';

-- `normative_authenticated_actor_or_null()` — LA MEME CHOSE, SANS LEVER quand
-- il n'y a simplement pas d'acteur.
--
-- POURQUOI ELLE EXISTE, ET CE QU'ELLE EVITE. Les declencheurs de 0010 lisent
-- l'acteur dans leur bloc `DECLARE`, c'est-a-dire AVANT toute branche — donc
-- avant meme de savoir s'il s'agit d'un amorcage. Or l'amorcage s'execute sous
-- le plan de controle, qui n'est PAS le backend authentifie et n'a aucune
-- raison de l'etre: ouvrir la racine n'est pas une operation applicative.
-- Avec la variante levante, `bootstrap_normative_administrator()` se serait
-- refusee elle-meme.
--
-- ELLE CONSERVE LA DISTINCTION QUI COMPTE. Un deploiement sans
-- authentificateur reste une erreur de DEPLOIEMENT, et se signale comme telle:
-- `BLOCKED_BY_REAL_AUTH` est leve dans les deux variantes. Ce qui devient
-- NULL, c'est seulement « cette session-ci ne porte pas d'acteur » — et chaque
-- declencheur formule alors son propre refus, avec ses termes a lui.
create or replace function normative_authenticated_actor_or_null() returns uuid
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  brut text;
begin
  if not normative_authentication_configured() then
    raise exception
      'BLOCKED_BY_REAL_AUTH: aucun backend authentifie n''est declare pour '
      'cette base. Aucune operation d''autorite normative n''est possible.'
      using errcode = 'insufficient_privilege';
  end if;
  if not pg_has_role(session_user, 'eurostruct_authority_backend', 'USAGE') then
    return null;
  end if;
  brut := nullif(btrim(coalesce(
            current_setting('eurostruct.actor_id', true), '')), '');
  if brut is null then
    return null;
  end if;
  begin
    return brut::uuid;
  exception when others then
    return null;
  end;
end;
$$;

alter function normative_authenticated_actor_or_null()
  owner to eurostruct_normative_writer;
revoke all on function normative_authenticated_actor_or_null() from public;
grant execute on function normative_authenticated_actor_or_null()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap,
     eurostruct_authority_backend;

comment on function normative_authenticated_actor_or_null is
  'Comme normative_authenticated_actor(), mais rend NULL au lieu de lever '
  'quand la session ne porte pas d''acteur. Un deploiement sans '
  'authentificateur leve toujours: c''est une erreur de deploiement, pas une '
  'absence d''acteur.';



-- ---------------------------------------------------------------------
-- D. LE MANDAT D'AMORCAGE — consomme une fois, jamais rejoue
-- ---------------------------------------------------------------------
-- `p_grantee` cesse d'etre un choix. Il doit CORRESPONDRE au principal
-- preautorise par le mandat declare. Le detenteur de `eurostruct_deployment`
-- peut toujours declencher l'amorcage — c'est son travail — mais il ne choisit
-- plus QUI devient autorite: il execute une decision prise ailleurs.
--
-- SANS MANDAT DECLARE, L'AMORCAGE REFUSE. C'est le cas de ce depot: aucune
-- source externe de mandat n'y existe, et en inventer une serait exactement
-- ce qu'il ne faut pas faire.
create table if not exists normative_bootstrap_mandate_use (
  mandate_digest text primary key,
  grantee_id     uuid not null,
  grant_id       uuid not null references normative_authorisation_grants(id)
                 on delete restrict,
  consumed_by    text not null,
  consumed_at    timestamptz not null default now()
);

comment on table normative_bootstrap_mandate_use is
  'La CONSOMMATION du mandat d''amorcage. Cle primaire sur l''empreinte du '
  'mandat: un mandat ne se consomme qu''une fois, et le rejeu se heurte a la '
  'cle, pas a un controle applicatif qu''une course pourrait contourner.';

alter table normative_bootstrap_mandate_use
  owner to eurostruct_normative_bootstrap;
alter table normative_bootstrap_mandate_use enable row level security;
alter table normative_bootstrap_mandate_use force row level security;

create policy mandate_use_bootstrap on normative_bootstrap_mandate_use
  for all to eurostruct_normative_bootstrap using (true) with check (true);
grant select on normative_bootstrap_mandate_use to normative_governance;
create policy mandate_use_governance_read on normative_bootstrap_mandate_use
  for select to normative_governance using (true);

create trigger bootstrap_mandate_use_is_immutable
  before update or delete on normative_bootstrap_mandate_use
  for each row execute function forbid_auth_contract_mutation();

-- Le mandat declare a la forme « <uuid-du-principal>:<empreinte-du-document> ».
-- L'empreinte n'est pas verifiee par la base — elle ne peut pas l'etre, le
-- document vit hors du systeme — mais elle est INSCRITE, et c'est ce qui rend
-- la decision opposable: on peut confronter le mandat produit a l'empreinte
-- qui a servi.
create or replace function normative_bootstrap_mandate()
returns table (principal uuid, empreinte text)
language plpgsql
stable
set search_path = public, pg_temp
as $$
declare
  brut text;
begin
  select valeur into brut from normative_authentication_contract
   where nom = 'eurostruct.bootstrap_mandate';
  if brut is null or btrim(brut) = '' then
    raise exception
      'BOOTSTRAP_AUTHORITY_NOT_CONFIGURED: aucun mandat d''amorcage n''est '
      'declare pour cette base. L''amorcage nomme la premiere autorite '
      'normative — une responsabilite PROFESSIONNELLE — et il ne peut pas '
      'etre decide par l''identite TECHNIQUE qui applique un schema. Declarer '
      '« eurostruct.bootstrap_mandate » sous la forme '
      '« <uuid-du-principal>:<empreinte-du-mandat> ».'
      using errcode = 'insufficient_privilege';
  end if;
  if split_part(brut, ':', 1) = '' or split_part(brut, ':', 2) = '' then
    raise exception
      'BOOTSTRAP_AUTHORITY_NOT_CONFIGURED: le mandat declare est illisible. '
      'Forme attendue « <uuid-du-principal>:<empreinte-du-mandat> ».'
      using errcode = 'insufficient_privilege';
  end if;
  return query select split_part(brut, ':', 1)::uuid,
                      split_part(brut, ':', 2);
end;
$$;

alter function normative_bootstrap_mandate()
  owner to eurostruct_normative_bootstrap;
revoke all on function normative_bootstrap_mandate() from public;
grant execute on function normative_bootstrap_mandate()
  to eurostruct_normative_bootstrap, eurostruct_deployment,
     normative_governance;


-- L'AMORCAGE, REECRIT. Meme signature — les appelants existants n'ont pas a
-- changer — mais `p_grantee` n'est plus un choix: c'est une ASSERTION que la
-- fonction confronte au mandat. Fournir un autre principal est refuse.
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
  m_principal uuid;
  m_empreinte text;
begin
  -- LE VERROU D'ABORD, comme avant: il serialise le controle d'existence.
  perform pg_advisory_xact_lock(hashtext('eurostruct.normative.administration'));

  -- LE MANDAT ENSUITE. Il leve BOOTSTRAP_AUTHORITY_NOT_CONFIGURED si rien
  -- n'est declare — donc AVANT toute ecriture, et sur une base ou aucun mandat
  -- n'existe l'amorcage est simplement impossible.
  select principal, empreinte into m_principal, m_empreinte
    from normative_bootstrap_mandate();

  if p_grantee is distinct from m_principal then
    raise exception
      'amorcage refuse: le mandat preautorise « % », et « % » a ete demande. '
      'L''identite de deploiement EXECUTE un mandat, elle ne choisit pas qui '
      'devient autorite normative.', m_principal, p_grantee
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

  -- LA CONSOMMATION, PAR CLE PRIMAIRE. Un rejeu se heurte a la contrainte
  -- d'unicite, et non a un controle applicatif qu'une course pourrait
  -- traverser. Deux amorcages concurrents portant le meme mandat: l'un des
  -- deux recoit une violation d'unicite, et c'est structurel.
  insert into normative_bootstrap_mandate_use
    (mandate_digest, grantee_id, grant_id, consumed_by)
  values (m_empreinte, p_grantee, nouvel_id, session_user);

  perform log_normative_event(
    'normative.authorisation.bootstrap',
    'normative_authorisation_grants',
    nouvel_id,
    jsonb_build_object('grantee_id', p_grantee, 'origin', 'bootstrap',
                       'reason', p_reason,
                       'mandate_digest', m_empreinte,
                       'performed_by_db_user', current_user,
                       'performed_by_session_user', session_user),
    null
  );
  return nouvel_id;
end;
$$;

alter function bootstrap_normative_administrator(uuid, text, text)
  owner to eurostruct_normative_bootstrap;
revoke all on function bootstrap_normative_administrator(uuid, text, text)
  from public;
grant execute on function bootstrap_normative_administrator(uuid, text, text)
  to eurostruct_deployment;

comment on function bootstrap_normative_administrator is
  'Ouvre la chaine de confiance en EXECUTANT un mandat declare hors du '
  'systeme. `p_grantee` n''est pas un choix mais une assertion confrontee au '
  'mandat. Sans mandat: BOOTSTRAP_AUTHORITY_NOT_CONFIGURED. Le mandat se '
  'consomme une fois — cle primaire, pas controle applicatif.';


-- ---------------------------------------------------------------------
-- E. LES DECLENCHEURS DERIVENT L'ACTEUR DU CONTEXTE AUTHENTIFIE
-- ---------------------------------------------------------------------
-- UN SEUL POINT CHANGE dans chacun: `auth.uid()` devient
-- `normative_authenticated_actor()`. Le reste du corps est celui de 0010 et
-- 0012, mot pour mot — parce qu'une revue qui doit relire trois cents lignes
-- pour trouver le mot qui a bouge ne trouve rien.
create or replace function check_normative_grant_lineage() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  parent normative_authorisation_grants;
begin
  if new.origin = 'bootstrap' then
    if new.parent_grant_id is not null then
      raise exception
        'un amorcage est une RACINE: il ne peut pas referencer un parent.'
        using errcode = 'check_violation';
    end if;
    return new;
  end if;

  acteur := normative_authenticated_actor();

  if new.parent_grant_id is null then
    raise exception
      'octroi refuse: toute delegation doit nommer l''habilitation au titre '
      'de laquelle elle est consentie (parent_grant_id).'
      using errcode = 'not_null_violation';
  end if;

  select * into parent from normative_authorisation_grants
   where id = new.parent_grant_id;
  if not found then
    raise exception 'habilitation parente % introuvable', new.parent_grant_id
      using errcode = 'foreign_key_violation';
  end if;

  if parent.grantee_id is distinct from acteur then
    raise exception
      'octroi refuse: l''habilitation % appartient a %, pas a %. On ne delegue '
      'que ce que l''on detient.',
      parent.id, coalesce(parent.grantee_id::text, '(racine)'), acteur
      using errcode = 'insufficient_privilege';
  end if;

  if not normative_grant_is_effective(parent.id) then
    raise exception
      'octroi refuse: l''habilitation % n''est plus efficace — elle-meme ou '
      'l''un de ses ancetres a ete revoque ou a expire.', parent.id
      using errcode = 'insufficient_privilege';
  end if;

  if parent.permission <> 'can_manage_normative_authorisations' then
    raise exception
      'octroi refuse: l''habilitation % porte « % », qui ne permet pas de '
      'deleguer.', parent.id, parent.permission
      using errcode = 'insufficient_privilege';
  end if;

  if (parent.country_code    is not null
      and new.country_code    is distinct from parent.country_code)
     or (parent.standard_family is not null
      and new.standard_family is distinct from parent.standard_family)
     or (parent.part            is not null
      and new.part            is distinct from parent.part)
     or (parent.edition         is not null
      and new.edition         is distinct from parent.edition) then
    raise exception
      'octroi refuse: la portee demandee %/%/%/% n''est pas incluse dans '
      'celle de l''habilitation % (%/%/%/%).',
      coalesce(new.country_code::text, '*'), coalesce(new.standard_family, '*'),
      coalesce(new.part, '*'), coalesce(new.edition, '*'), parent.id,
      coalesce(parent.country_code::text, '*'),
      coalesce(parent.standard_family, '*'),
      coalesce(parent.part, '*'), coalesce(parent.edition, '*')
      using errcode = 'insufficient_privilege';
  end if;

  if parent.expires_at is not null
     and (new.expires_at is null or new.expires_at > parent.expires_at) then
    raise exception
      'octroi refuse: l''habilitation % expire le %, la delegation demandee %.',
      parent.id, parent.expires_at, coalesce(new.expires_at::text, 'jamais')
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;

alter function check_normative_grant_lineage()
  owner to eurostruct_normative_writer;
revoke all on function check_normative_grant_lineage() from public;


-- ---------------------------------------------------------------------
-- E-bis. LES QUATRE DECLENCHEURS RESTANTS DERIVENT L'ACTEUR DU CONTEXTE
-- ---------------------------------------------------------------------
-- MESURE: la premiere version de 0013 n'avait converti que le declencheur de
-- FILIATION. Les quatre autres continuaient d'appeler `auth.uid()`, et le
-- premier octroi delegue se refusait sur « aucune identite authentifiee » —
-- non pas parce que la garantie tenait, mais parce que le harnais posait
-- desormais son acteur dans `eurostruct.actor_id` pendant que le declencheur
-- lisait encore `request.jwt.claim.sub`. Deux moities d'un meme changement,
-- dont une seule avait ete faite.
--
-- LES CORPS SONT CEUX DE 0010, MOT POUR MOT, A UNE EXPRESSION PRES:
-- `auth.uid()` devient `normative_authenticated_actor()`. Rien d'autre n'a
-- bouge, et c'est deliberé: une revue qui doit relire trois cents lignes pour
-- trouver le mot qui a change ne trouve rien.
--
-- CE QUE LE CHANGEMENT FAIT, EXACTEMENT. Avant, l'acteur etait ce que la
-- session DECLARAIT. Maintenant, il n'est lu que si la session atteint le role
-- d'execution privilegie — et sans authentificateur declare, la fonction leve
-- BLOCKED_BY_REAL_AUTH avant meme de regarder la valeur.
--
-- `auth.uid()` N'EST PAS REDEFINIE, et ce n'est pas un oubli: elle sert aussi
-- les policies RLS multi-tenant de 0002, ou l'utilisateur EST un utilisateur
-- applicatif ordinaire. La detourner ferait dependre toute lecture de tenant
-- du role d'autorite normative.

create or replace function check_normative_grant() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor_or_null();
  habilitation normative_authorisation_grants;
begin
  -- L'amorcage passe par sa fonction dediee, qui pose origin='bootstrap'.
  -- Toute autre insertion est une DELEGATION, et le trigger l'impose plutot
  -- que de faire confiance a la colonne recue.
  if new.origin = 'bootstrap' then
    -- Ce qui interdit REELLEMENT une insertion brute en « bootstrap », c'est
    -- la policy RLS: seul `eurostruct_normative_bootstrap` a le droit
    -- d'inserer une ligne dont l'origine est « bootstrap », et le backend a
    -- un `with check (origin = 'delegated')`. Une policy s'evalue contre le
    -- role reel: elle n'est pas contournable par un appelant.
    --
    -- Le controle ci-dessous est la seconde ligne. `normative_authenticated_actor() IS NULL` seul
    -- ne suffisait pas — contre-exemple verifie sur base vierge, avec
    -- SET ROLE authenticated et aucun claim JWT: la branche etait empruntee
    -- et la racine de confiance s'auto-proclamait.
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
  new.granted_at := now();

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

  -- CONCURRENCE. `IF EXISTS` puis `INSERT` ne protege de rien: deux
  -- transactions concurrentes lisent chacune « aucun doublon » avant que
  -- l'autre ne valide, et toutes deux inserent. On serialise donc sur la
  -- PORTEE, par un verrou consultatif transactionnel: deux insertions de meme
  -- (titulaire, permission) s'attendent, et la seconde voit la premiere.
  --
  -- Un verrou plutot qu'un index unique partiel: l'unicite devrait porter sur
  -- « actif », qui se calcule depuis une autre table et ne peut donc pas
  -- entrer dans un index. Et une colonne `is_active` est precisement ce que ce
  -- modele refuse.
  perform pg_advisory_xact_lock(
    hashtext('eurostruct.normative.grant:' || new.grantee_id::text
             || ':' || new.permission::text));

  -- Et le verrou COMMUN des que l'ensemble des administrateurs est en jeu:
  -- octroyer une administration doit se serialiser avec les revocations, sans
  -- quoi « octroyer a B puis retirer a A » pourrait se croiser avec « retirer
  -- a B ».
  if new.permission = 'can_manage_normative_authorisations' then
    perform pg_advisory_xact_lock(
      hashtext('eurostruct.normative.administration'));
  end if;

  -- Deux octrois ACTIFS de portee rigoureusement identique rendraient la
  -- resolution ambigue. On refuse a la source plutot que de laisser
  -- l'ambiguite apparaitre a la premiere confirmation, quand plus personne ne
  -- fera le lien avec l'octroi de trop.
  --
  -- La comparaison passe par IS NOT DISTINCT FROM: deux NULL designent la
  -- meme portee « tous », alors que `=` les dirait differents.
  -- `is_effective` ET NON `is_active`, ET C'EST UN DEFAUT QUE 0012 AVAIT
  -- LAISSE. Le controle de doublon refuse « un octroi actif de meme portee
  -- existe deja ». Avec la seule notion LOCALE (`is_active` = « aucune
  -- revocation ne vise CETTE ligne »), un octroi devenu INEFFICACE parce qu'un
  -- ancetre a ete revoque continuait de bloquer un nouvel octroi de meme
  -- portee. Mesure: apres avoir revoque A->B, A ne pouvait plus octroyer
  -- directement a C ce que B lui avait octroye — la revocation eteignait le
  -- pouvoir ET interdisait de le reconstituer par une chaine explicite.
  --
  -- C'est bien un doublon d'octrois UTILISABLES que l'on refuse, pas un
  -- doublon de lignes: deux octrois efficaces de portee identique rendraient
  -- la resolution ambigue, un octroi eteint ne rend rien ambigu.
  if exists (
    select 1 from normative_authorisation_grants g
     where g.grantee_id = new.grantee_id
       and g.permission = new.permission
       and g.country_code    is not distinct from new.country_code
       and g.standard_family is not distinct from new.standard_family
       and g.part            is not distinct from new.part
       and g.edition         is not distinct from new.edition
       and normative_grant_is_effective(g.id)
  ) then
    raise exception
      'un octroi EFFICACE de meme portee existe deja pour % (%). Le revoquer '
      'd''abord si la portee doit changer: deux octrois identiques actifs '
      'rendraient le snapshot d''audit indeterminable.',
      new.grantee_id, new.permission
      using errcode = 'unique_violation';
  end if;

  habilitation := consume_normative_authorisation(
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

create or replace function check_normative_grant_revocation() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor_or_null();
  cible  normative_authorisation_grants;
  habilitation normative_authorisation_grants;
begin
  if acteur is null then
    raise exception 'aucune identite authentifiee.'
      using errcode = 'insufficient_privilege';
  end if;
  new.revoked_by := acteur;
  new.revoked_at := now();

  -- CONCURRENCE, deux portees.
  --
  -- 1) Le verrou COMMUN de l'administration, pris AVANT de lire l'ensemble
  --    actif. Sans lui, deux revocations concurrentes visant deux octrois
  --    differents voient chacune l'autre administrateur actif et passent
  --    toutes deux: contre-exemple verifie, zero administrateur restant.
  perform pg_advisory_xact_lock(hashtext('eurostruct.normative.administration'));

  -- 2) On verrouille la LIGNE de l'octroi. Une confirmation en vol
  -- prend un FOR SHARE sur cette meme ligne (voir check_normative_confirmation):
  -- les deux ne peuvent donc pas s'ignorer, et le resultat correspond
  -- toujours a un ordre seriel explicable — soit la confirmation passe puis
  -- l'habilitation est retiree, soit elle est retiree puis la confirmation
  -- est refusee. Jamais une confirmation autorisee par un etat intermediaire.
  -- Verrou EXCLUSIF consultatif sur l'octroi vise, et non `FOR UPDATE`:
  -- PostgreSQL exige le privilege UPDATE pour un verrou de ligne, et ces
  -- tables n'accordent JAMAIS UPDATE — c'est le fondement de leur
  -- immuabilite. La confirmation en vol tient le verrou partage
  -- correspondant, si bien que les deux ne peuvent pas s'ignorer.
  perform pg_advisory_xact_lock(
    hashtext('eurostruct.normative.grantrow:' || new.grant_id::text));

  select * into cible from normative_authorisation_grants
   where id = new.grant_id;
  if not found then
    raise exception 'octroi % introuvable', new.grant_id
      using errcode = 'foreign_key_violation';
  end if;

  habilitation := consume_normative_authorisation(
    acteur, 'can_manage_normative_authorisations',
    cible.country_code, cible.standard_family, cible.part, cible.edition
  );
  if habilitation.id is null then
    raise exception
      'revocation refusee: % ne detient pas « can_manage_normative_'
      'authorisations » couvrant la portee de l''octroi %.', acteur, cible.id
      using errcode = 'insufficient_privilege';
  end if;

  -- DERNIER ADMINISTRATEUR. Retirer le dernier octroi actif
  -- « can_manage_normative_authorisations » laisserait la gouvernance sans
  -- personne, et l'index qui interdit un second amorcage la rendrait
  -- IRRECUPERABLE: plus aucun octroi possible, et pas de reouverture de la
  -- chaine. Le contre-exemple a ete verifie avant d'ecrire cette garde.
  --
  -- On refuse donc. Une procedure « bris de glace », reservee au deploiement
  -- et auditee, releve d'une decision distincte: elle sera proposee avant
  -- d'etre implementee, plutot qu'introduite ici par commodite.
  if cible.permission = 'can_manage_normative_authorisations' then
    -- 6.3b4 #4 — COUVERTURE DE PORTEE, et non plus simple decompte.
    --
    -- La garde comptait les administrateurs restants et se satisfaisait d'un
    -- seul. Elle laissait donc passer le cas qui compte reellement:
    --
    --   A administre TOUTES les juridictions (portee entierement NULL)
    --   B administre la seule Belgique      (country_code = 'BE')
    --   -> retirer A laisse « un administrateur », et plus personne pour la
    --      France, l'Espagne ni l'Allemagne.
    --
    -- Le decompte n'etait pas trop faible, il mesurait la mauvaise chose. Ce
    -- qui doit rester apres un retrait, ce n'est pas UN administrateur, c'est
    -- UNE COUVERTURE: un octroi actif dont la portee contient celle du retire.
    --
    -- Un NULL sur un axe signifie « toutes les valeurs de cet axe ». G couvre
    -- H si, sur chacun des quatre axes, G est NULL (donc universel) ou egal a
    -- H. La portee globale n'est donc couverte que par une autre portee
    -- globale — ce qui est exactement le sens voulu.
    --
    -- La couverture n'est PAS exigee union-de-plusieurs-octrois: deux
    -- administrateurs BE et FR ne remplacent pas un administrateur global,
    -- parce qu'ils ne couvrent ni l'Espagne ni l'Allemagne, et parce qu'une
    -- union de portees serait indecidable des qu'un axe est continu. Un seul
    -- octroi doit contenir la portee retiree.
    if not exists (
      select 1 from normative_authorisation_grants g
       where g.permission = 'can_manage_normative_authorisations'
         and g.id <> cible.id
         and normative_grant_is_active(g.id)
         and (g.country_code    is null or g.country_code    = cible.country_code)
         and (g.standard_family is null or g.standard_family = cible.standard_family)
         and (g.part            is null or g.part            = cible.part)
         and (g.edition         is null or g.edition         = cible.edition)
    ) then
      raise exception
        'revocation refusee: aucun autre octroi actif de '
        '« can_manage_normative_authorisations » ne couvre la portee de % '
        '(%/%/%/%). Le retirer laisserait cette portee sans administrateur, '
        'et l''amorcage ne peut pas etre rejoue. Octroyer d''abord une '
        'administration couvrant AU MOINS cette portee.',
        cible.id,
        coalesce(cible.country_code::text, '*'),
        coalesce(cible.standard_family, '*'),
        coalesce(cible.part, '*'),
        coalesce(cible.edition, '*')
        using errcode = 'restrict_violation';
    end if;
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

create or replace function check_normative_confirmation() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor_or_null();
  habilitation normative_authorisation_grants;
  edition_annexe text;
  spec_json  jsonb;
  impl_json  jsonb;
  ev_json    jsonb;
  stack_json jsonb;
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
  new.created_at := now();

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

  -- 4. COHERENCE ATOMIQUE du paquet.
  --
  --    Quatre empreintes individuellement justes ne font pas un sujet. Rien
  --    n'obligeait `stack_snapshot` a correspondre a `stack_payload`, ni
  --    `evidence_items` a `evidence_payload`, ni les colonnes de juridiction
  --    au contenu signe. On pouvait donc hacher un paquet et en stocker un
  --    autre: pile substituee, spec et implementation interverties, rule_id
  --    de colonne different du rule_id signe — les trois etaient acceptes.
  --
  --    Le principe retenu: les PAYLOADS font foi, parce que ce sont eux qui
  --    sont haches. Les colonnes jsonb en sont DERIVEES par le serveur, et
  --    les colonnes de recherche sont VERIFIEES contre eux. Rien ne peut plus
  --    diverger, faute d'avoir deux sources.
  begin
    spec_json  := new.normative_spec_payload::jsonb;
    impl_json  := new.implementation_payload::jsonb;
    ev_json    := new.evidence_payload::jsonb;
    stack_json := new.stack_payload::jsonb;
  exception when others then
    raise exception
      'un des quatre payloads canoniques n''est pas du JSON: %', sqlerrm
      using errcode = 'check_violation';
  end;

  if spec_json  ->> 'kind' <> 'normative_spec'
     or impl_json  ->> 'kind' <> 'implementation'
     or ev_json    ->> 'kind' <> 'evidence'
     or stack_json ->> 'kind' <> 'normative_stack' then
    raise exception
      'les payloads ne decrivent pas ce qu''ils pretendent: spec=%, impl=%, '
      'preuve=%, pile=%. Intervertir specification et implementation laissait '
      'deux empreintes justes decrire le mauvais objet.',
      spec_json ->> 'kind', impl_json ->> 'kind', ev_json ->> 'kind',
      stack_json ->> 'kind'
      using errcode = 'check_violation';
  end if;

  -- Meme methode de canonicalisation pour les trois payloads qui la portent.
  -- La pile n'en a pas: elle porte un `schema_version` qui lui est propre.
  if spec_json ->> 'canonicalization_version' is distinct from
       new.canonicalization_version
     or impl_json ->> 'canonicalization_version' is distinct from
       new.canonicalization_version
     or ev_json ->> 'canonicalization_version' is distinct from
       new.canonicalization_version then
    raise exception
      'les payloads n''ont pas tous ete produits par la methode annoncee (%): '
      'spec=%, impl=%, preuve=%.',
      new.canonicalization_version,
      spec_json ->> 'canonicalization_version',
      impl_json ->> 'canonicalization_version',
      ev_json ->> 'canonicalization_version'
      using errcode = 'check_violation';
  end if;

  -- La regle nommee par la colonne est celle que les deux payloads signent.
  if spec_json ->> 'rule_id' is distinct from new.rule_id
     or impl_json ->> 'rule_id' is distinct from new.rule_id then
    raise exception
      'la colonne rule_id dit « % » alors que les payloads signent « % » et '
      '« % ». La recherche et la signature designeraient deux regles.',
      new.rule_id, spec_json ->> 'rule_id', impl_json ->> 'rule_id'
      using errcode = 'check_violation';
  end if;

  -- La juridiction nommee par les colonnes est celle de la pile signee.
  if stack_json ->> 'country_code' is distinct from new.country_code::text
     or stack_json ->> 'standard_family' is distinct from new.standard_family
     or stack_json ->> 'part' is distinct from new.part then
    raise exception
      'les colonnes disent %/%/% et la pile signee %/%/%.',
      new.country_code, new.standard_family, new.part,
      stack_json ->> 'country_code', stack_json ->> 'standard_family',
      stack_json ->> 'part'
      using errcode = 'check_violation';
  end if;

  -- Les projections jsonb sont DERIVEES, jamais recues. Ce que l'appelant
  -- avait mis dans ces colonnes est ecrase.
  new.stack_snapshot := stack_json;
  new.evidence_items := ev_json -> 'items';

  if new.evidence_items is null
     or jsonb_typeof(new.evidence_items) <> 'array'
     or jsonb_array_length(new.evidence_items) = 0 then
    raise exception
      'le payload de preuve ne porte aucun element: confirmer sans dire ce '
      'qu''on a lu n''est pas une lecture d''annexe.'
      using errcode = 'check_violation';
  end if;

  -- Ce que SQL PEUT verifier d'un element de preuve. Il ne sait pas juger si
  -- la citation est la bonne — c'est le travail du verificateur, et celui du
  -- backend qui construit le paquet. Il sait en revanche refuser un element
  -- qui n'est pas un element: `items: [1]` etait accepte.
  if exists (
    select 1 from jsonb_array_elements(new.evidence_items) e
     where jsonb_typeof(e) <> 'object'
        or e ->> 'document_digest' is null
        or e ->> 'document_role'   is null
        or e ->> 'reference'       is null
        or e ->> 'clause'          is null
        or e ->> 'quote'           is null
        or e ->> 'quote_digest'    is null
        or (e -> 'page_printed') is null
  ) then
    raise exception
      'un element de preuve est incomplet ou n''est pas un objet. Un dossier '
      'de revue nomme, pour chaque source, le document, son role, la clause, '
      'le folio et la citation.'
      using errcode = 'check_violation';
  end if;

  -- La citation est scellee par sa propre empreinte: retoucher le texte sans
  -- recalculer l'empreinte est detectable, et c'est verifiable ici sans rien
  -- recanonicaliser.
  if exists (
    select 1 from jsonb_array_elements(new.evidence_items) e
     where e ->> 'quote_digest'
           <> encode(sha256(convert_to(e ->> 'quote', 'UTF8')), 'hex')
  ) then
    raise exception
      'le quote_digest d''un element de preuve ne resume pas sa citation.'
      using errcode = 'check_violation';
  end if;

  -- Versions connues. Une pile en `schema_version` inconnue serait lue avec
  -- une grille qui n'est pas la sienne — et c'est cette grille qui sert a
  -- extraire l'edition d'annexe dont depend le controle de portee.
  if stack_json ->> 'schema_version' <> 'esc-stack/1' then
    raise exception
      'schema_version de pile inconnu: %. La structure serait interpretee '
      'avec une grille qui n''est pas la sienne.',
      stack_json ->> 'schema_version'
      using errcode = 'check_violation';
  end if;
  if new.canonicalization_version <> 'esc-canon/1' then
    raise exception
      'version de canonicalisation inconnue: %.', new.canonicalization_version
      using errcode = 'check_violation';
  end if;

  -- 4b. L'edition de l'annexe est EXTRAITE de la pile SIGNEE par le serveur:
  --     c'est elle que la portee de l'habilitation compare, elle ne peut donc
  --     pas etre fournie par celui qu'on controle.
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
  habilitation := consume_normative_authorisation(
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
  -- Verrou et revalidation: dans consume_normative_authorisation().

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

create or replace function check_normative_confirmation_revocation()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor_or_null();
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
    habilitation := consume_normative_authorisation(
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

alter function check_normative_grant()                     owner to eurostruct_normative_writer;
alter function check_normative_grant_revocation()          owner to eurostruct_normative_writer;
alter function check_normative_confirmation()              owner to eurostruct_normative_writer;
alter function check_normative_confirmation_revocation()   owner to eurostruct_normative_writer;
revoke all on function check_normative_grant()                   from public;
revoke all on function check_normative_grant_revocation()        from public;
revoke all on function check_normative_confirmation()            from public;
revoke all on function check_normative_confirmation_revocation() from public;


-- ---------------------------------------------------------------------
-- F. LE PRIVILEGE D'ECRITURE PASSE AU BACKEND AUTHENTIFIE
-- ---------------------------------------------------------------------
-- C'EST LA DEFENSE STRUCTURELLE, et le reste n'en est que la lisibilite. Un
-- role applicatif qui falsifie le GUC n'atteint plus la table: il n'a plus
-- INSERT. Aucun message d'erreur n'a besoin d'etre convaincant — l'ordre est
-- refuse par le moteur, avant tout declencheur.
-- SOUS LE PROPRIETAIRE, ET C'EST LE MEME PIEGE POUR LA TROISIEME FOIS.
--
-- Depuis 0010, ces quatre tables appartiennent a `eurostruct_normative_writer`.
-- `GRANT` et `REVOKE` exigent d'etre le proprietaire — et quand on ne l'est
-- pas, PostgreSQL emet un WARNING, PAS une erreur: la migration passe, et
-- rien n'a change.
--
-- MESURE: sans ce `set role`, les revocations ci-dessous ne retiraient RIEN.
-- `normative_backend` conservait INSERT, et les attaques 4 et 6 du harnais
-- restaient ROUGES — non pas parce que la frontiere etait mal concue, mais
-- parce qu'elle n'avait jamais ete posee. Le meme piege avait deja fait
-- echouer en silence une neutralisation de falsification, et avait deja
-- refuse une migration sur « permission denied for schema public ».
--
-- Le sceau le documente depuis 6.3b6d: « GRANT n'echoue pas quand celui qui
-- l'execute n'a pas le GRANT OPTION ». Il fallait le lire une fois de plus.
set role eurostruct_normative_writer;

revoke insert on normative_authorisation_grants          from normative_backend;
revoke insert on normative_authorisation_revocations     from normative_backend;
revoke insert on normative_rule_confirmations            from normative_backend;
revoke insert on normative_rule_confirmation_revocations from normative_backend;

grant insert on normative_authorisation_grants          to eurostruct_authority_backend;
grant insert on normative_authorisation_revocations     to eurostruct_authority_backend;
grant insert on normative_rule_confirmations            to eurostruct_authority_backend;
grant insert on normative_rule_confirmation_revocations to eurostruct_authority_backend;
grant select on normative_authorisation_grants          to eurostruct_authority_backend;
grant select on normative_authorisation_revocations     to eurostruct_authority_backend;
grant select on normative_rule_confirmations            to eurostruct_authority_backend;
grant select on normative_rule_confirmation_revocations to eurostruct_authority_backend;
grant execute on function normative_authenticated_actor()
  to eurostruct_authority_backend;
grant execute on function normative_grant_is_effective(uuid)
  to eurostruct_authority_backend;

-- LES POLICIES SUIVENT LE PRIVILEGE. Une policy `to normative_backend` sur une
-- table dont ce role n'a plus INSERT ne sert plus a rien; la laisser
-- entretiendrait l'idee qu'il peut encore ecrire.
drop policy if exists normative_grants_insert on normative_authorisation_grants;
create policy normative_grants_insert on normative_authorisation_grants
  for insert to eurostruct_authority_backend with check (origin = 'delegated');
create policy normative_grants_backend_read on normative_authorisation_grants
  for select to eurostruct_authority_backend using (true);

reset role;

-- ET ON VERIFIE QUE LE RETRAIT A PRIS. Un WARNING ne s'arrete pas; une
-- assertion, si. C'est la seule facon de distinguer « revoque » de « on a
-- demande a revoquer ».
do $$
begin
  if has_table_privilege('normative_backend',
                         'normative_authorisation_grants', 'INSERT') then
    raise exception
      'la frontiere d''autorite n''a PAS ete posee: « normative_backend » '
      'conserve INSERT sur normative_authorisation_grants. Un GRANT ou un '
      'REVOKE emis sans droit se contente d''un WARNING — la migration serait '
      'passee en laissant la porte ouverte.'
      using errcode = 'insufficient_privilege';
  end if;
  if not has_table_privilege('eurostruct_authority_backend',
                             'normative_authorisation_grants', 'INSERT') then
    raise exception
      'le backend authentifie n''a PAS recu INSERT: le sous-systeme serait '
      'ferme a tout le monde, y compris au chemin nominal.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- F-bis. LA DECLARATION EST CONFRONTEE AUX MEMBRES REELS
-- ---------------------------------------------------------------------
-- SANS CE CONTROLE, LA DECLARATION EST DECORATIVE. Mesure avant correction:
-- la liste declaree nommait le login de service, et le membre reel etait le
-- migrateur. Personne ne comparait les deux — le produit lisait la
-- declaration pour decider s'il etait « configure », puis laissait
-- l'appartenance decider de qui agit reellement.
--
-- Deux choses distinctes, qu'il ne faut pas confondre:
--   * `normative_authentication_configured()` repond « un authentificateur
--     est-il DECLARE ? » — c'est la question du fail-closed;
--   * la fonction ci-dessous repond « les membres du role d'execution
--     sont-ils EXACTEMENT ceux qui ont ete declares ? » — c'est la question
--     de la frontiere.
--
-- ELLE NE REND PAS UN BOOLEEN: elle nomme l'ecart. Un booleen se lit « faux »
-- et se range; « le migrateur est membre alors qu'il n'est pas declare » se
-- corrige.
create or replace function assert_authority_backend_membership() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  declares text[];
  r record;
  ecarts text[] := array[]::text[];
begin
  select coalesce(
           string_to_array(
             btrim((select valeur from normative_authentication_contract
                     where nom = 'eurostruct.authority_backend_logins')), ','),
           array[]::text[])
    into declares;

  if declares = array[]::text[] then
    -- Rien de declare: le sous-systeme est ferme de toute facon
    -- (`normative_authenticated_actor()` leve BLOCKED_BY_REAL_AUTH). Mais un
    -- membre present alors que RIEN n'est declare est une anomalie, pas un
    -- etat ferme: on le dit.
    for r in select m.rolname
               from pg_roles m
              where not m.rolsuper
                and m.rolname <> 'eurostruct_authority_backend'
                and (pg_has_role(m.rolname, 'eurostruct_authority_backend', 'USAGE')
                     or pg_has_role(m.rolname, 'eurostruct_authority_backend', 'SET'))
    loop
      ecarts := ecarts || format(
        '« %s » ATTEINT le backend d''autorite (usage ou SET) alors '
        'qu''AUCUN authentificateur n''est declare', r.rolname);
    end loop;
  else
    -- ADMINISTRER N'EST PAS UTILISER, ET LA DIFFERENCE EST TOUT LE SUJET.
    --
    -- Mesure sur PostgreSQL 16: `CREATE ROLE` par un role CREATEROLE cree une
    -- appartenance avec `admin_option = t`, mais `inherit_option = f` et
    -- `set_option = f`:
    --
    --   pg_has_role(createur, cible, 'USAGE')  -> f
    --   pg_has_role(createur, cible, 'SET')    -> f
    --   pg_has_role(createur, cible, 'MEMBER') -> t
    --
    -- Le plan de controle, qui cree le role en phase 0, en est donc membre au
    -- sens du catalogue — et ne peut ni en heriter les privileges ni l'endosser.
    -- C'est exactement ce qu'il faut: il doit pouvoir l'ACCORDER aux logins
    -- declares, il n'a aucune raison d'ECRIRE sur les tables d'autorite.
    --
    -- Une premiere version comptait les lignes de `pg_auth_members` et
    -- declarait donc le plan de controle en ecart. Elle confondait « peut
    -- administrer » et « peut agir ». Ce qui doit etre refuse, c'est l'USAGE
    -- non declare — pas l'administration.
    for r in select m.rolname
               from pg_roles m
              where not m.rolsuper
                and m.rolname <> 'eurostruct_authority_backend'
                and (pg_has_role(m.rolname, 'eurostruct_authority_backend', 'USAGE')
                     or pg_has_role(m.rolname, 'eurostruct_authority_backend', 'SET'))
                and not (btrim(m.rolname) = any (
                          select btrim(x) from unnest(declares) as x))
    loop
      ecarts := ecarts || format(
        '« %s » ATTEINT le backend d''autorite (usage ou SET) sans etre '
        'declare',
        r.rolname);
    end loop;
  end if;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'frontiere d''autorite: appartenance non declaree — %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_authority_backend_membership()
  owner to eurostruct_normative_writer;
revoke all on function assert_authority_backend_membership() from public;
grant execute on function assert_authority_backend_membership()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap,
     normative_governance, eurostruct_deployment;

comment on function assert_authority_backend_membership is
  'Confronte les MEMBRES reels du backend d''autorite a la liste DECLAREE. '
  'Sans elle la declaration est decorative: le produit lisait la declaration '
  'pour se dire configure, et laissait l''appartenance decider de qui agit.';


-- ---------------------------------------------------------------------
-- G. LE CONSTAT DES DECLARATIONS — pose par le deploiement, une fois
-- ---------------------------------------------------------------------
-- Elle CONSTATE ce que `pg_db_role_setting` porte, et le fige. Appelee deux
-- fois, la seconde ne change rien: la cle primaire refuse, et le declencheur
-- d'immuabilite refuserait un UPDATE. Le deploiement ne peut pas se
-- re-declarer authentificateur apres coup.
create or replace function normative_constater_authentification() returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  n text;
  v text;
begin
  foreach n in array array['eurostruct.authority_backend_logins',
                           'eurostruct.bootstrap_mandate'] loop
    v := btrim(coalesce(normative_declared_setting(n), ''));
    if v <> '' and not exists (select 1 from normative_authentication_contract
                                where nom = n) then
      insert into normative_authentication_contract (nom, valeur, constate_par)
      values (n, v, session_user);
    end if;
  end loop;
end;
$$;

alter function normative_constater_authentification()
  owner to eurostruct_normative_writer;
-- Elle lit `pg_db_role_setting` par `normative_declared_setting`, dont
-- l'EXECUTE est deja accorde au writer par le sceau.
revoke all on function normative_constater_authentification() from public;
grant execute on function normative_constater_authentification()
  to eurostruct_deployment;

comment on function normative_constater_authentification is
  'Constate les declarations d''authentification et les FIGE. Idempotente par '
  'la cle primaire: un second appel ne remplace rien.';

-- LE CONSTAT A LIEU PENDANT LA MIGRATION. Si rien n'est declare, la table
-- reste vide et tout le sous-systeme d'autorite est FERME — c'est l'etat
-- attendu sur une base ou aucun authentificateur n'existe.
select normative_constater_authentification();


revoke create on schema public
  from eurostruct_normative_writer, eurostruct_normative_bootstrap;
