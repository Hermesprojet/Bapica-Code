-- =====================================================================
-- 0015 — LE MANIFESTE DE LA SURFACE D'AUTORITE
-- =====================================================================
--
-- CE QUI MANQUAIT, ET QUI EST POSE ICI
-- -------------------------------------
-- `assert_authority_composition()` balaie `pg_proc` EN FILTRANT PAR LE
-- PROPRIETAIRE ATTENDU:
--
--     where n.nspname = 'public'
--       and pg_get_userbyid(p.proowner) in ('eurostruct_normative_writer', ...)
--
-- Une fonction dont le proprietaire DERIVE sort du balayage. L'assertion ne la
-- voit plus, donc ne peut pas signaler la derive qu'elle existe pour detecter.
-- La liste nommee de treize primitives, ajoutee au jalon precedent, compense
-- partiellement: elle couvre treize objets, pas la surface.
--
-- L'EGALITE MANIFESTE/REALITE corrige cela a la racine:
--
--   * le MANIFESTE declare ce qui doit exister, et avec quelles proprietes;
--   * la REALITE est decouverte par un critere ORTHOGONAL aux proprietes
--     verifiees. Jamais par le proprietaire attendu, jamais par le
--     `SECURITY DEFINER` attendu, jamais par l'ACL attendue, jamais par la
--     propriete precisement controlee;
--   * l'egalite est exigee DANS LES DEUX SENS.
--
-- Le critere de decouverte est: schema `public`, plus le VOCABULAIRE de la
-- surface normative. Il ne regarde AUCUN champ verifie — c'est ce qui permet a
-- une derive de proprietaire de rester visible au lieu de faire disparaitre
-- l'objet du balayage.
--
-- L'IDENTITE EST QUALIFIEE PAR LA SIGNATURE
-- ------------------------------------------
-- `p.oid::regprocedure`, jamais `proname`. Mesure sur PG16: deux fonctions
-- peuvent partager `proname` et ne differer que par leurs arguments
-- (`f(integer)` et `f(text)`); chacune porte ses PROPRES ACL, son propre
-- proprietaire et son propre `prosecdef`. Comparer par nom confondrait deux
-- surfaces distinctes, et le manifeste ne saurait pas laquelle il decrit.
--
-- PUBLIC EST IDENTIFIE PAR LA SEMANTIQUE ACL, PAS PAR UN ROLE TEMOIN
-- -------------------------------------------------------------------
-- Mesure sur PG16, trois fonctions construites pour la question:
--
--   fonction     proacl                                  grantee=0  has_priv  temoin
--   f_defaut     NULL                                        1         t        t
--   f_definer    {postgres=X/postgres,temoin=X/postgres}     0         f        t
--   f_revoquee   {postgres=X/postgres}                       0         f        f
--
-- La ligne decisive est `f_definer`: un ROLE ORDINAIRE pris comme temoin
-- detient EXECUTE alors que PUBLIC ne l'a PAS. Choisir un role ordinaire pour
-- temoigner de PUBLIC produit donc un FAUX POSITIF. On lit le grantee public
-- par son OID — `aclexplode(...) where grantee = 0`, qui est la semantique
-- exacte — et on recoupe avec `has_function_privilege('public', ...)`. Deux
-- lectures independantes qui doivent concorder; leur desaccord est lui-meme un
-- constat, pas un detail a arbitrer.
--
-- `acldefault('f', proowner)` EST NECESSAIRE: `proacl` NULL ne veut pas dire
-- « aucun droit », il veut dire « les droits par defaut », et ceux-ci
-- CONTIENNENT `=X/owner`, c'est-a-dire EXECUTE POUR PUBLIC. Mesure: sans ce
-- `coalesce`, dix-sept fonctions a `proacl` NULL seraient lues « PUBLIC n'a
-- rien » alors que PUBLIC a tout.
--
-- LES PROPRIETAIRES DEPENDANTS DU DEPLOIEMENT SONT SYMBOLIQUES
-- --------------------------------------------------------------
-- Le migrateur et le plan de controle portent des noms choisis par
-- l'installation. Les figer dans le manifeste rendrait celui-ci faux sur toute
-- autre base. Ils sont donc ecrits `@MIGRATEUR` et `@PLAN`, et RESOLUS a
-- l'execution depuis `normative_finalization_intent.migrateur_nom` et
-- `normative_control_plane()` — les deux sources que la finalisation a figees.
--
-- CE QUE CE MANIFESTE N'EST PAS
-- ------------------------------
-- Ce n'est pas une benediction. C'est une PHOTOGRAPHIE, prise sur une base
-- installee le 28/08 et relue classe par classe contre l'intention des
-- migrations. Sa valeur est qu'a partir de maintenant, toute derive se voit.
--
-- ET IL Y A UN ECART CONNU, INSCRIT PLUTOT QUE MASQUE. Seize fonctions
-- declencheur anterieures a 6.3c — les `forbid_*` appartenant au migrateur ou
-- au plan de controle — n'ont PAS de `search_path` epingle, et PUBLIC detient
-- EXECUTE sur elles par l'ACL par defaut. Deux faits mesures les rendent moins
-- graves qu'ils n'en ont l'air, sans les rendre nuls:
--
--   * elles ne sont PAS `SECURITY DEFINER`: elles s'executent avec les droits
--     de l'appelant, pas ceux du proprietaire;
--   * un EXECUTE sur une fonction declencheur n'est pas une capacite —
--     l'invocation directe est refusee par SQLSTATE 0A000, « trigger functions
--     can only be called as triggers ».
--
-- Elles sont donc inscrites au manifeste AVEC leur etat reel, pour que cet
-- etat soit VU et qu'un changement se remarque. Les durcir releve d'un jalon
-- qui gouverne ces migrations-la; 6.3c ne les a ni creees ni durcies, et
-- elargir son perimetre en douce fabriquerait un rouge qui n'apprend rien.
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- LE DROIT DE CREER, RENDU PUIS REPRIS
-- ---------------------------------------------------------------------
-- `0011` a `0014` retirent CREATE sur `public` a tous les roles d'autorite, et
-- la retirent VRAIMENT — c'est l'objet de leur revocation endossee. Un
-- `alter function ... owner to eurostruct_normative_writer` exige que le
-- NOUVEAU proprietaire puisse creer dans le schema: sans ce droit, PostgreSQL
-- refuse par « permission denied for schema public ». Mesure faite en
-- appliquant cette migration pour la premiere fois.
--
-- Le droit est donc rendu ici et REPRIS a la fin du fichier, par la meme
-- revocation endossee et verifiee que 0014 — pas par un `revoke` nu, qui est
-- un voeu et non une commande.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- LE MANIFESTE — ce qui DOIT exister, et avec quelles proprietes
-- ---------------------------------------------------------------------
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
    ('forbid_activation_mutation()', '@PLAN', false, false, true, '@PLAN'),
    ('forbid_annex_rewrite()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_approved_settings_mutation()', '@PLAN', false, false, true, '@PLAN'),
    ('forbid_auth_contract_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_control_plane_mutation()', '@PLAN', false, false, true, '@PLAN'),
    ('forbid_decision_delete()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_final_deliverable_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_finalization_intent_mutation()', '@PLAN', false, false, true, '@PLAN'),
    ('forbid_migration_ledger_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_ndp_value_rewrite()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_normative_audit_mutation()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_normative_write_while_pending()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('forbid_purge_within_retention()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_review_decision_rewrite()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_seal_metadata_mutation()', '@PLAN', false, false, true, '@PLAN'),
    ('forbid_validated_calculation_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_validated_child_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_validated_deliverable_mutation()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('forbid_variant_rewrite()', '@MIGRATEUR', false, false, true, '@MIGRATEUR'),
    ('normative_activation_state()', 'eurostruct_normative_activator', true, true, false, 'authenticated,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer,normative_backend,normative_governance'),
    ('normative_approved_manifest()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_authenticated_actor()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authenticated_actor_or_null()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authentication_configured()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authorisation_snapshot(normative_authorisation_grants)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_authority_manifest()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_bootstrap_mandate()', 'eurostruct_normative_bootstrap', false, true, false, 'eurostruct_deployment,eurostruct_normative_bootstrap'),
    ('normative_constater_authentification()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_control_plane()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_control_plane_oid()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_decision_approve(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_consume(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_propose(text,text,uuid,country_code,text,text,text,normative_permission,text)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_declared_setting(text)', '@PLAN', false, true, false, '@PLAN,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_deployment_readiness()', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment'),
    ('normative_effective_setting(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
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

comment on function normative_authority_manifest is
  'Le manifeste de la surface normative: ce qui doit exister, et avec quelles '
  'proprietes. Les proprietaires dependants du deploiement sont symboliques '
  '(@MIGRATEUR, @PLAN) et resolus a l''execution. Photographie prise le '
  '28/08 et relue classe par classe contre l''intention des migrations.';


-- ---------------------------------------------------------------------
-- L'ASSERTION — egalite dans les DEUX SENS
-- ---------------------------------------------------------------------
create or replace function assert_authority_manifest() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  ecarts text[] := array[]::text[];
  r record;
  v_mig  text;
  v_plan text;
  n_manif int;
begin
  -- LES DEUX SYMBOLES, RESOLUS DEPUIS LE CATALOGUE.
  --
  -- PAS DEPUIS `normative_finalization_intent`: cette table est remplie par la
  -- FINALISATION, qui vient APRES la phase 1. Mesure faite en appliquant cette
  -- migration: « permission denied for table normative_finalization_intent »,
  -- et de toute facon la ligne n'existe pas encore. Une assertion qui ne peut
  -- pas s'executer au moment ou sa migration la pose ne protege rien.
  --
  -- PAS DEPUIS UN GUC NON PLUS. `eurostruct.approved_deployment_roles` porte
  -- les deux noms, mais c'est une valeur posee par le deploiement: s'en servir
  -- reviendrait a laisser le deploiement decrire la surface qu'on verifie.
  --
  -- Le proprietaire de la BASE est le migrateur — c'est la forme de
  -- deploiement que ce schema installe.
  v_mig := pg_get_userbyid((select datdba from pg_database
                             where datname = current_database()));

  -- LE PLAN DE CONTROLE NE VIENT PAS DE `normative_control_plane()` NON PLUS.
  -- Mesure: en phase 1, cette fonction rend NULL — la table qu'elle lit est
  -- remplie par la FINALISATION, qui vient apres. On resout donc le symbole
  -- par le proprietaire d'un objet que le SCEAU a cree en phase 0, et que
  -- seul le plan de controle peut avoir pose.
  select pg_get_userbyid(p.proowner) into v_plan
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'normative_finalize_deployment';

  -- L'ANGLE MORT EST NOMME, PAS TU. Resoudre un symbole par le proprietaire
  -- d'un objet rend CET objet-la insensible a une derive de propriete: le
  -- symbole suivrait la derive au lieu de la signaler. Deux garde-fous:
  --
  --   * les deux symboles doivent etre DISTINCTS et non nuls. Un plan de
  --     controle qui serait devenu le migrateur est precisement la confusion
  --     que la separation des phases existe pour empecher;
  --   * quand `normative_control_plane()` rend une valeur — c'est-a-dire
  --     apres la finalisation — elle doit CONCORDER avec le symbole resolu.
  --     La ou une seconde source existe, elle est exigee.
  if v_mig is null or v_plan is null then
    raise exception
      'AUTHORITY_MANIFEST_UNRESOLVED: le migrateur (%) ou le plan de controle '
      '(%) n''a pas pu etre resolu; le manifeste ne peut pas etre confronte.',
      coalesce(v_mig, 'NULL'), coalesce(v_plan, 'NULL')
      using errcode = 'insufficient_privilege';
  end if;
  if v_mig = v_plan then
    raise exception
      'AUTHORITY_MANIFEST_SYMBOLS_COLLIDE: le migrateur et le plan de controle '
      'se resolvent tous deux en « % ». Le manifeste ne pourrait plus '
      'distinguer les deux surfaces.', v_mig
      using errcode = 'insufficient_privilege';
  end if;
  declare
    v_plan2 text;
  begin
    begin
      v_plan2 := normative_control_plane();
    exception when others then
      v_plan2 := null;
    end;
    if v_plan2 is not null and v_plan2 <> v_plan then
      raise exception
        'AUTHORITY_MANIFEST_PLAN_DISAGREE: le plan de controle resolu par le '
        'catalogue est « % » et celui inscrit a la finalisation est « % ».',
        v_plan, v_plan2
        using errcode = 'insufficient_privilege';
    end if;
  end;
  -- LA REALITE ET LE MANIFESTE, CONFRONTES EN UNE SEULE JOINTURE EXTERNE
  -- COMPLETE. C'est l'egalite dans les deux sens, ecrite comme telle: une
  -- entree sans reel est une absence, un reel sans entree est un objet non
  -- declare, et les lignes appariees se comparent champ a champ.
  --
  -- LE `where` DE LA DECOUVERTE NE MENTIONNE NI LE PROPRIETAIRE, NI
  -- `prosecdef`, NI L'ACL, NI LE `search_path`. C'est la condition pour qu'une
  -- derive de l'un d'eux reste VISIBLE au lieu de faire sortir l'objet du
  -- balayage — le defaut exact de `assert_authority_composition()`, qui filtre
  -- par proprietaire attendu et devient donc aveugle a la derive de propriete.
  --
  -- Pas de table temporaire: une fonction `stable` ne peut pas en creer
  -- (« CREATE TABLE is not allowed in a non-volatile function », mesure), et
  -- rendre l'assertion volatile pour contourner serait payer la rigueur d'un
  -- diagnostic avec la rigueur d'une declaration.
  for r in
    with reel as (
      select p.oid::regprocedure::text as identite,
             case pg_get_userbyid(p.proowner) when v_mig  then '@MIGRATEUR'
                                              when v_plan then '@PLAN'
                                              else pg_get_userbyid(p.proowner) end
               as proprietaire,
             p.prosecdef as secdef,
             (p.proconfig is not null and exists (
                select 1 from unnest(p.proconfig) c where c like 'search\_path=%'))
               as chemin_epingle,
             -- PUBLIC PAR LA SEMANTIQUE ACL: le grantee public est l'OID 0.
             exists (select 1
                       from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                      where a.grantee = 0 and a.privilege_type = 'EXECUTE')
               as public_acl,
             -- LA SECONDE LECTURE, INDEPENDANTE.
             has_function_privilege('public', p.oid, 'EXECUTE') as public_has,
             coalesce((select string_agg(g, ',' order by g) from (
                         select distinct case pg_get_userbyid(a.grantee)
                                  when v_mig then '@MIGRATEUR'
                                  when v_plan then '@PLAN'
                                  else pg_get_userbyid(a.grantee) end as g
                           from aclexplode(coalesce(p.proacl,
                                                    acldefault('f', p.proowner))) a
                          where a.privilege_type = 'EXECUTE'
                            and a.grantee <> 0) q), '') as acl_execute
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public'
         and (p.proname like 'normative\_%' or p.proname like 'assert\_%'
           or p.proname like 'check\_normative\_%' or p.proname like 'forbid\_%'
           or p.proname in ('resolve_normative_authorisation',
                            'consume_normative_authorisation',
                            'bootstrap_normative_administrator'))
    )
    select coalesce(m.identite, e.identite) as identite,
           (m.identite is null) as non_declaree,
           (e.identite is null) as absente,
           m.proprietaire as m_owner,   e.proprietaire as r_owner,
           m.secdef       as m_secdef,  e.secdef       as r_secdef,
           m.chemin_epingle as m_path,  e.chemin_epingle as r_path,
           m.public_execute as m_public, e.public_acl  as r_public,
           e.public_has   as r_public_has,
           m.acl_execute  as m_acl,     e.acl_execute  as r_acl
      from normative_authority_manifest() m
      full outer join reel e on e.identite = m.identite
  loop
    if r.absente then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_MISSING: %s est declaree au manifeste et absente '
        'du schema', r.identite);
      continue;
    end if;
    if r.non_declaree then
      -- SANS CETTE MOITIE, une fonction ajoutee au perimetre sans etre
      -- declaree passerait inapercue: le manifeste ne parlerait que de ce
      -- qu'il connait deja, ce qui est exactement l'angle mort qu'on ferme.
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_UNDECLARED: %s existe dans le perimetre normatif '
        '(proprietaire « %s ») et n''est declaree nulle part',
        r.identite, r.r_owner);
      continue;
    end if;

    -- LES DEUX LECTURES DE PUBLIC DOIVENT CONCORDER. Un desaccord ne
    -- s'arbitre pas: il se signale. Il voudrait dire que l'une des deux
    -- semantiques a change sous nos pieds, et aucune des deux ne pourrait
    -- plus servir de reference.
    if r.r_public is distinct from r.r_public_has then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_ACL_DISAGREE: %s — aclexplode(grantee=0) dit %s et '
        'has_function_privilege(''public'') dit %s',
        r.identite, r.r_public, r.r_public_has);
    end if;
    if r.r_owner is distinct from r.m_owner then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_OWNER: %s appartient a « %s », le manifeste declare '
        '« %s »', r.identite, r.r_owner, r.m_owner);
    end if;
    if r.r_secdef is distinct from r.m_secdef then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_SECDEF: %s a prosecdef=%s, le manifeste declare %s',
        r.identite, r.r_secdef, r.m_secdef);
    end if;
    if r.r_path is distinct from r.m_path then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_SEARCH_PATH: %s a search_path epingle=%s, le '
        'manifeste declare %s', r.identite, r.r_path, r.m_path);
    end if;
    if r.r_public is distinct from r.m_public then
      ecarts := ecarts || format(
        'AUTHORITY_MANIFEST_PUBLIC_EXECUTE: %s donne EXECUTE a PUBLIC=%s, le '
        'manifeste declare %s', r.identite, r.r_public, r.m_public);
    end if;
    -- L'ACL EST COMPAREE DANS LES DEUX SENS, et le diagnostic DIT lequel.
    -- « differente » ne suffit pas: elargie et retrecie n'ont pas la meme
    -- gravite, et les confondre ferait chercher au mauvais endroit.
    if r.r_acl is distinct from r.m_acl then
      declare
        reels  text[] := string_to_array(coalesce(nullif(r.r_acl, ''), '@VIDE'), ',');
        prevus text[] := string_to_array(coalesce(nullif(r.m_acl, ''), '@VIDE'), ',');
        en_trop text[]; manquants text[];
      begin
        select array_agg(x) into en_trop
          from unnest(reels) x where not (x = any (prevus));
        select array_agg(x) into manquants
          from unnest(prevus) x where not (x = any (reels));
        if en_trop is not null then
          ecarts := ecarts || format(
            'AUTHORITY_MANIFEST_ACL_WIDER: %s accorde EXECUTE a %s, absent du '
            'manifeste', r.identite, array_to_string(en_trop, ', '));
        end if;
        if manquants is not null then
          ecarts := ecarts || format(
            'AUTHORITY_MANIFEST_ACL_NARROWER: %s n''accorde plus EXECUTE a %s, '
            'declare au manifeste', r.identite, array_to_string(manquants, ', '));
        end if;
      end;
    end if;
  end loop;

  -- LE CARDINAL, DIT SEPAREMENT. Deux ensembles peuvent avoir la meme taille
  -- et differer: il ne sert pas de preuve, seulement de diagnostic.
  select count(*) into n_manif from normative_authority_manifest();

  if array_length(ecarts, 1) > 0 then
    raise exception
      -- `raise` UTILISE « % », PAS « %s ». Mesure: le diagnostic sortait
      -- « 2s ecart(s) ... (67s entrees) » et la liste elle-meme disparaissait,
      -- avalee par un placeholder mal forme. C'est `format()` qui prend « %s »;
      -- les deux cohabitent dans ce fichier et ne s'ecrivent pas pareil.
      'AUTHORITY_MANIFEST_MISMATCH: % ecart(s) entre le manifeste (% entrees) '
      'et la realite:%',
      array_length(ecarts, 1), n_manif,
      chr(10) || array_to_string(ecarts, chr(10))
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_authority_manifest() owner to eurostruct_normative_writer;
revoke all on function assert_authority_manifest() from public;
grant execute on function assert_authority_manifest()
  to eurostruct_normative_writer, eurostruct_deployment;

comment on function assert_authority_manifest is
  'Egalite MANIFESTE/REALITE, dans les deux sens. La realite est decouverte '
  'par un critere orthogonal aux champs verifies — jamais par le proprietaire, '
  'le SECURITY DEFINER, l''ACL ou la propriete attendus — sans quoi une derive '
  'de l''un d''eux ferait sortir l''objet du balayage au lieu d''etre vue. '
  'PUBLIC est lu par la semantique ACL du grantee 0, recoupee par '
  'has_function_privilege, jamais par un role temoin.';


-- ---------------------------------------------------------------------
-- LE DROIT DE CREATE REPART — ET C'EST VERIFIE, PAS ESPERE
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0011 a 0014, et pour la meme raison mesuree: un `REVOKE`
-- emis par un role qui n'est pas le DONNEUR de l'octroi n'a aucun effet, sans
-- erreur ni avertissement bloquant. On endosse donc le donneur — et seulement
-- s'il appartient a un ensemble admissible EXPLICITE, confronte au catalogue
-- et jamais dicte par lui.
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
        'AUTHORITY_0015_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'AUTHORITY_0015_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%). Le privilege CREATE resterait, et rien '
        'd''autre ne le dirait.', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;

  if current_user <> appelant then
    raise exception
      'AUTHORITY_0015_ROLE_NOT_RESTORED: la migration s''execute encore sous '
      '« % » au lieu de « % » apres la revocation.', current_user, appelant
      using errcode = 'insufficient_privilege';
  end if;

  -- LA REVOCATION EST CONSTATEE. C'est la lecon de `0011`: une revocation qui
  -- ne verifie pas son propre effet laisse le privilege en place, et la seule
  -- assertion capable de le voir arrive deux migrations plus tard.
  if exists (select 1
               from pg_namespace n, aclexplode(n.nspacl) a
              where n.nspname = 'public'
                and a.privilege_type = 'CREATE'
                and a.grantee = 'eurostruct_normative_writer'::regrole::oid)
  then
    raise exception
      'AUTHORITY_0015_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer '
      'conserve CREATE sur public apres la revocation; donneur(s) restant(s): %',
      (select string_agg(distinct pg_get_userbyid(a.grantor), ', ')
         from pg_namespace n, aclexplode(n.nspacl) a
        where n.nspname = 'public' and a.privilege_type = 'CREATE'
          and a.grantee = 'eurostruct_normative_writer'::regrole::oid)
      using errcode = 'insufficient_privilege';
  end if;
end
$$;


-- L'ASSERTION EST APPELEE PAR LA MIGRATION ELLE-MEME, avant l'inscription au
-- registre et dans la meme transaction: une surface qui ne correspond pas a
-- son manifeste ne doit laisser aucune ligne disant que 0015 a ete appliquee.
--
-- ET L'AGREGEE AUSSI: elle voit l'etat FINAL, celui que 0015 vient de
-- modifier en creant deux fonctions de plus dans le perimetre.
select assert_authority_manifest();
select assert_authority_composition();

select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
