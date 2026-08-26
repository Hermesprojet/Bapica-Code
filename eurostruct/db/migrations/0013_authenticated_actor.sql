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
create policy auth_contract_bootstrap_read on normative_authentication_contract
  for select to eurostruct_normative_bootstrap using (true);
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
do $$
begin
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_authority_backend') then
    create role eurostruct_authority_backend nologin;
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
-- F. LE PRIVILEGE D'ECRITURE PASSE AU BACKEND AUTHENTIFIE
-- ---------------------------------------------------------------------
-- C'EST LA DEFENSE STRUCTURELLE, et le reste n'en est que la lisibilite. Un
-- role applicatif qui falsifie le GUC n'atteint plus la table: il n'a plus
-- INSERT. Aucun message d'erreur n'a besoin d'etre convaincant — l'ordre est
-- refuse par le moteur, avant tout declencheur.
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
