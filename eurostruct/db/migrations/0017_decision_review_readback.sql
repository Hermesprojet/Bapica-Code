-- 0017 — B RELIT LE DOSSIER GELE AVANT D'APPROUVER
--
-- CE QUI MANQUAIT
-- ----------------
-- 0016 fige le dossier de revue sur la decision: A et B approuvent des octets
-- identiques, et la consommation en tire l'effet normatif. Mais RIEN NE
-- PERMETTAIT A B DE LE LIRE.
--
-- Le parcours reel est celui de deux personnes: A propose, se deconnecte, B se
-- connecte sur sa propre session et reprend l'identifiant de decision. Le
-- navigateur de B n'a jamais vu le dossier — il n'a qu'un uuid. Sans une
-- lecture, « B a approuve » signifie « B a clique sur un numero », ce qui est
-- exactement le quatre-yeux decoratif que ce dispositif existe pour empecher.
--
-- POURQUOI UNE PRIMITIVE ET PAS UN SELECT
-- ----------------------------------------
-- `eurostruct_authority_backend` n'a AUCUN privilege de table sur
-- `normative_authority_decisions`, et c'est deliberé depuis 0014: tout passe
-- par des primitives SECURITY DEFINER, seule facon de garantir que l'acteur
-- est derive de la session et jamais fourni. Lui donner SELECT sur la table
-- ouvrirait aussi la lecture des colonnes d'audit — proposant, approbateur,
-- habilitations au moment de la signature — a un role qui n'en a pas besoin.
--
-- CE QUE LA LECTURE NE REND PAS
-- ------------------------------
-- Ni `proposer_id`, ni `approver_id`, ni les instantanés d'habilitation. B n'a
-- pas besoin de savoir QUI a propose pour juger DE QUOI il s'agit, et
-- PostgreSQL refuse de toute facon que l'approbateur soit le proposant — par
-- contrainte de table, pas par prudence de l'appelant. Rendre ces colonnes
-- transformerait une lecture de dossier en annuaire des acteurs habilites.

-- LA MIGRATION EST UNE TRANSACTION, ET ELLE S'INSCRIT AU REGISTRE.
--
-- CE QUI MANQUAIT, ET CE QUE CELA A COUTE. Sans le `begin;`/`commit;` et sans
-- l'appel final a `normative_migration_applied()`, cette migration
-- s'appliquait sans laisser aucune trace dans `normative_migration_ledger`.
-- Consequences mesurees sur une composition reelle: le second demarrage
-- rejouait tout, et la commande officielle refusait avec
-- ACTIVE_SCHEMA_UPGRADE_REQUIRED en annoncant que la base ACTIVE n'avait pas
-- des migrations qu'elle portait pourtant. Les harnais ne l'avaient pas vu
-- parce qu'ils partent toujours d'une base neuve et ne relisent pas le
-- registre ensuite.
begin;

grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LA LECTURE DU DOSSIER, SOUS IDENTITE AUTHENTIFIEE
-- ---------------------------------------------------------------------
create or replace function normative_decision_review(p_decision uuid)
returns table (decision_id     uuid,
               state           text,
               subject_kind    text,
               subject_id      text,
               org_id          uuid,
               country_code    country_code,
               standard_family text,
               part            text,
               edition         text,
               permission      normative_permission,
               reason          text,
               review_package  jsonb,
               proposed_at     timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  d normative_authority_decisions;
begin
  -- L'IDENTITE EST EXIGEE MEME POUR LIRE. Un dossier de revue nomme le
  -- document, la clause et le folio d'une annexe sous licence: ce n'est pas
  -- une donnee publique. `normative_authenticated_actor()` leve si aucune
  -- identite n'est posee dans la transaction — on ne la capture donc pas.
  perform normative_authenticated_actor();

  select * into d from normative_authority_decisions where id = p_decision;
  if not found then
    raise exception 'decision % introuvable', p_decision
      using errcode = 'foreign_key_violation';
  end if;

  return query select
    d.id, d.state::text, d.subject_kind, d.subject_id, d.org_id,
    d.country_code, d.standard_family, d.part, d.edition, d.permission,
    d.reason, d.review_package, d.proposed_at;
end;
$$;

comment on function normative_decision_review(uuid) is
  'Le dossier gele d''une decision, pour le SECOND regard. Sans cette '
  'lecture, B approuve un identifiant et non un contenu. Ne rend aucun '
  'acteur: le quatre-yeux est garanti par la contrainte de table.';


-- ---------------------------------------------------------------------
-- 2. ACL
-- ---------------------------------------------------------------------
revoke all on function normative_decision_review(uuid) from public;
alter function normative_decision_review(uuid)
  owner to eurostruct_normative_writer;
grant execute on function normative_decision_review(uuid)
  to eurostruct_authority_backend;


-- ---------------------------------------------------------------------
-- 3. LE MANIFESTE DECLARE LA PRIMITIVE AJOUTEE
-- ---------------------------------------------------------------------
-- `assert_authority_composition()` confronte la surface reelle a cette liste
-- NOMMEE. Une primitive ajoutee sans l'y declarer laisse la base en PENDING:
-- l'activation refuse, et elle a raison.
--
-- Republie en entier plutot que retouchee par un `update`: la liste EST la
-- declaration, et une declaration qui se modifie par morceaux ne se relit plus.
create or replace function normative_authority_manifest()
returns table (identite       text,
               proprietaire   text,
               secdef         boolean,
               chemin_epingle boolean,
               public_execute boolean,
               acl_execute    text)
language sql
immutable
set search_path = public, pg_temp
as $$
  values
    ('assert_0012_lineage_surface()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_0014_decisions_surface()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_backend_membership()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_composition()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_manifest()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_surface_hardened()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_digest_integrity(text,text,text,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('assert_normative_topology()', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('bootstrap_normative_administrator(uuid,text,text)', 'eurostruct_normative_bootstrap', true, true, false, 'eurostruct_deployment,eurostruct_normative_bootstrap'),
    ('check_normative_confirmation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_confirmation_revocation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_decision_transition()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant_lineage()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant_revocation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('consume_normative_authorisation(uuid,normative_permission,country_code,text,text,text)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('forbid_activation_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_annex_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_approved_settings_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_auth_contract_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_control_plane_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_decision_delete()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_final_deliverable_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_finalization_intent_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_migration_ledger_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_ndp_value_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_normative_audit_mutation()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_normative_write_while_pending()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('forbid_purge_within_retention()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_review_decision_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_seal_metadata_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_validated_calculation_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_validated_child_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_validated_deliverable_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_variant_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('normative_activation_state()', 'eurostruct_normative_activator', true, true, false, 'authenticated,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer,normative_backend,normative_governance'),
    ('normative_approved_manifest()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_authenticated_actor()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authenticated_actor_or_null()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authentication_configured()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_assert_review_package(jsonb,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_authorisation_snapshot(normative_authorisation_grants)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_authority_manifest()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_bootstrap_mandate()', 'eurostruct_normative_bootstrap', false, true, false, 'eurostruct_deployment,eurostruct_normative_bootstrap'),
    ('normative_confirmation_depuis_decision()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_constater_authentification()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_control_plane()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_control_plane_oid()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_decision_approve(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_consume(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_propose(text,text,uuid,country_code,text,text,text,normative_permission,text,jsonb)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_review(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_declared_setting(text)', '@PLAN', false, true, false, '@PLAN,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_deployment_readiness()', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment'),
    ('normative_effective_setting(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_emettre_confirmations(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_exiger_manifeste_approuve(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_finalize_deployment(text)', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment'),
    ('normative_grant_descendants(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_grant_is_active(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_grant_is_effective(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_lock_grant_chains(uuid[])', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_migration_applied(text,text)', '@MIGRATEUR', false, true, false, '@MIGRATEUR'),
    ('normative_migration_gate(text,text)', '@MIGRATEUR', false, true, false, '@MIGRATEUR'),
    ('normative_pending_migrator()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_prepare_activation(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_record_activation()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_seal_assurance()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_seal_version()', 'eurostruct_normative_activator', true, true, false, '@PLAN,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_settings_manifest()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_topology_digest(oid,text,oid,text,text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('resolve_normative_authorisation(uuid,normative_permission,country_code,text,text,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer')
$$;

alter function normative_authority_manifest() owner to eurostruct_normative_writer;
revoke all on function normative_authority_manifest() from public;
grant execute on function normative_authority_manifest()
  to eurostruct_normative_writer, eurostruct_deployment;


-- ---------------------------------------------------------------------
-- 4. POSTCONDITION — LA LECTURE EXISTE, ET ELLE EST DURCIE
-- ---------------------------------------------------------------------
-- La migration se verifie elle-meme. Une primitive posee sans SECURITY
-- DEFINER, sans chemin epingle ou executable par `public` serait une porte,
-- pas une lecture — et rien d'autre ne le dirait avant l'audit suivant.
do $$
declare
  p pg_proc;
begin
  select * into p from pg_proc
   where oid = 'normative_decision_review(uuid)'::regprocedure;
  if not p.prosecdef then
    raise exception
      'AUTHORITY_0017_REVIEW_NOT_SECDEF: normative_decision_review(uuid) '
      'n''est pas SECURITY DEFINER; l''acteur ne serait pas derive.'
      using errcode = 'insufficient_privilege';
  end if;
  if p.proconfig is null
     or not (p.proconfig @> array['search_path=public, pg_temp']) then
    raise exception
      'AUTHORITY_0017_REVIEW_SEARCH_PATH_UNPINNED: le chemin de recherche de '
      'normative_decision_review(uuid) n''est pas epingle.'
      using errcode = 'insufficient_privilege';
  end if;
  if exists (select 1 from aclexplode(p.proacl) a
              where a.grantee = 0 and a.privilege_type = 'EXECUTE') then
    raise exception
      'AUTHORITY_0017_REVIEW_PUBLIC_EXECUTE: normative_decision_review(uuid) '
      'est executable par public.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- ---------------------------------------------------------------------
-- 5. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0011 a 0016, et pour la meme raison mesuree: on endosse le
-- DONNEUR de l'octroi, et seulement s'il appartient a un ensemble admissible
-- explicite, confronte au catalogue et jamais dicte par lui. Un `revoke` nu
-- emis par un role qui n'est pas le donneur n'a aucun effet, sans erreur ni
-- avertissement.
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
        'AUTHORITY_0017_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
        'public n''est pas dans l''ensemble admissible {%}. La migration '
        'refuse de l''endosser: le catalogue ne choisit pas sous quelle '
        'identite elle s''execute.',
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
        'AUTHORITY_0017_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%). Le privilege CREATE resterait, et rien '
        'd''autre ne le dirait.', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;
end;
$$;

-- POSTCONDITION: le droit ne reste pas.
do $$
begin
  if exists (
    select 1 from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public' and a.privilege_type = 'CREATE'
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid) then
    raise exception
      'AUTHORITY_0017_SCHEMA_CREATE_STILL_GRANTED: CREATE sur public reste '
      'octroye a eurostruct_normative_writer apres la migration.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 6. ET LE MANIFESTE EST TENU
-- ---------------------------------------------------------------------
-- `assert_authority_composition()` est l'assertion agregee que l'activation
-- consulte. L'appeler ici fait echouer la MIGRATION plutot que l'activation,
-- quand la cause est encore sous les yeux.
--
-- APRES LA REVOCATION, ET C'EST MESURE. Placee avant, elle refusait sur
-- AUTHORITY_COMPOSITION_SCHEMA_CREATE_RETAINED: la composition inclut le fait
-- que le writer ne garde AUCUN droit de creer dans le schema, et ce droit est
-- justement encore ouvert tant que la section 5 n'a pas tourne. L'assertion
-- avait raison; c'est l'ordre qui etait faux.
do $$
begin
  perform assert_authority_composition();
end;
$$;


-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE L'EFFET.
--
-- Inscrite hors transaction, elle pourrait survivre a un echec — la base
-- annoncerait alors une migration qu'elle n'a pas. Inscrite dedans, les deux
-- tombent ensemble.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
