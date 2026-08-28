-- =====================================================================
-- 0011 — DURCISSEMENT DES PRIMITIVES D'AUTORITE (6.3c)
-- =====================================================================
--
-- CE QUE CETTE MIGRATION FERME, ET POURQUOI ELLE EXISTE
-- ------------------------------------------------------
-- 6.3b6c a etabli que le MIGRATEUR est contenu: il ne peut plus produire
-- ACTIVE, ni ecrire une confirmation, ni effacer une preuve. La mesure de
-- 6.3c ajoute un fait que 6.3b6c n'avait pas releve:
--
--     SIX fonctions du sous-systeme normatif restent la propriete du
--     MIGRATEUR, alors que la migration transfere celle des autres.
--
-- Ce ne sont pas des fonctions anodines. `resolve_normative_authorisation()`
-- decide quelle habilitation couvre une portee; `normative_grant_is_active()`
-- decide si un pouvoir a ete retire. Elles sont appelees DEPUIS des fonctions
-- SECURITY DEFINER appartenant a `eurostruct_normative_writer`: leur
-- proprietaire peut donc les remplacer par `CREATE OR REPLACE` et changer, de
-- l'interieur, ce que le definisseur croit calculer.
--
-- Le proprietaire d'une fonction n'a pas besoin d'EXECUTE pour la reecrire.
-- Une ACL parfaite ne protege donc rien contre lui. C'est du CODE PRIVILEGIE
-- DETENU PAR UN ROLE QUI N'EST PAS UNE AUTORITE — et c'est exactement ce que
-- le modele de menace refuse.
--
-- SIX AUTRES FONCTIONS, hors du sous-systeme normatif, sont SECURITY DEFINER
-- et n'ont JAMAIS ete retirees a PUBLIC:
--
--     public.is_org_member, public.has_org_role, public.can_write,
--     check_validator_is_authorised, open_retention_period,
--     log_deliverable_transition
--
-- `EXECUTE` sur une fonction est accorde a PUBLIC PAR DEFAUT. Les six etaient
-- donc appelables par n'importe quel role, y compris `anon`. Trois d'entre
-- elles decident d'une appartenance ou d'une habilitation.
--
-- CE QUE CETTE MIGRATION NE FAIT PAS
-- -----------------------------------
-- Elle ne touche NI la frontiere d'authentification, NI l'amorcage, NI la
-- filiation des delegations. Ce sont trois sujets distincts, et les melanger
-- rendrait impossible de dire lequel a ferme quoi. Elle ne fait que du
-- durcissement de surface SQL: proprietaire, ACL, `search_path`.
--
-- ORDRE DES OPERATIONS. Le transfert de propriete exige d'etre membre du role
-- cible. La phase 1 s'execute sous le migrateur, qui detient l'appartenance
-- EMPRUNTEE a `eurostruct_normative_writer` — la meme que 0010 utilise deja
-- pour transferer la propriete des tables. La phase 2 la lui reprend.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. LE DROIT DE CREATE, REPRIS POUR LA DUREE DES TRANSFERTS SEULEMENT
-- ---------------------------------------------------------------------
-- PostgreSQL exige que le NOUVEAU proprietaire d'une fonction ait CREATE sur
-- le schema qui la porte. 0010 accordait ce droit aux roles d'autorite le
-- temps de ses propres transferts, puis le retirait — en le justifiant: « une
-- permission accordee pour une operation ponctuelle et laissee en place est
-- une permission qu'on a cesse de justifier ».
--
-- Cette migration transfere a son tour, et doit donc reprendre le droit. Elle
-- le rend a la fin, dans le meme mouvement. Ne pas le faire laisserait les
-- roles d'autorite capables de CREER des objets dans `public` — un pouvoir
-- qu'ils n'ont aucune raison d'avoir en regime etabli, et que le controle de
-- topologie ne surveille pas.
--
-- MESURE: sans ce bloc, cette migration se refuse elle-meme sur
-- « permission denied for schema public » des le premier ALTER FUNCTION.
-- ---------------------------------------------------------------------
-- UNE SEULE TRANSACTION, ET UNE INSCRIPTION AU REGISTRE
-- ---------------------------------------------------------------------
-- MESURE DU 26/08, roundtrip sur base ephemere: 10 migrations sur 14 etaient
-- constatees « deja appliquee » au second passage, et CES QUATRE etaient
-- REJOUEES. Elles n'appelaient pas `normative_migration_applied()`, donc le
-- registre n'en gardait aucune trace. Deux consequences, l'une et l'autre
-- serieuses:
--
--   * tout deploiement ulterieur les rejoue. Ce ne sont pas des scripts
--     idempotents par construction: elles transferent des proprietes, posent
--     des policies et retirent des droits;
--   * la protection « on ne peut pas les appliquer hors du runner » disparait.
--     C'est la substitution de `:'esc_migration_id'` qui la porte: sans elle,
--     `psql -f` les avale sans rien exiger.
--
-- Et sans `begin`/`commit`, une erreur au milieu du fichier laissait la moitie
-- des changements en place — les dix migrations precedentes s'en gardent
-- toutes.
begin;

grant create on schema public
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- ---------------------------------------------------------------------
-- A. LES SIX FONCTIONS DU SOUS-SYSTEME NORMATIF
-- ---------------------------------------------------------------------
-- `search_path` FIXE sur chacune. Sans lui, un appelant qui positionne son
-- propre `search_path` peut faire resoudre un nom d'objet vers un schema qu'il
-- controle. Les fonctions SECURITY DEFINER de 0010 le posaient deja; ces
-- six-la, non — et elles sont dans la meme chaine d'appel.
--
-- `pg_temp` EST EN DERNIER, et ce n'est pas un detail de style: un schema
-- temporaire est inscriptible par la session, et le placer en tete
-- permettrait de masquer un objet du schema public par un homonyme.

alter function resolve_normative_authorisation(
    uuid, normative_permission, country_code, text, text, text)
  set search_path = public, pg_temp;
alter function resolve_normative_authorisation(
    uuid, normative_permission, country_code, text, text, text)
  owner to eurostruct_normative_writer;

alter function normative_grant_is_active(uuid) set search_path = public, pg_temp;
alter function normative_grant_is_active(uuid) owner to eurostruct_normative_writer;

alter function normative_authorisation_snapshot(normative_authorisation_grants)
  set search_path = public, pg_temp;
alter function normative_authorisation_snapshot(normative_authorisation_grants)
  owner to eurostruct_normative_writer;

alter function assert_digest_integrity(text, text, text, text)
  set search_path = public, pg_temp;
alter function assert_digest_integrity(text, text, text, text)
  owner to eurostruct_normative_writer;

-- LES DEUX FONCTIONS DE DECLENCHEUR DU NAMESPACE D'AUDIT.
--
-- Elles gardent la reserve « seul `log_normative_event()` produit des
-- evenements `normative.*` ». Une fonction de declencheur n'exige pas
-- d'EXECUTE de la part de celui qui declenche le DML — PostgreSQL ne le
-- verifie pas — mais son PROPRIETAIRE peut la reecrire, et c'est la tout le
-- sujet: laisser la garde de l'audit entre les mains du migrateur revenait a
-- lui laisser la possibilite de la desarmer.
alter function reserve_normative_audit_namespace()
  set search_path = public, pg_temp;
alter function reserve_normative_audit_namespace()
  owner to eurostruct_normative_writer;

alter function forbid_normative_audit_mutation()
  set search_path = public, pg_temp;
alter function forbid_normative_audit_mutation()
  owner to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- B. LES SIX FONCTIONS SECURITY DEFINER RESTEES OUVERTES A PUBLIC
-- ---------------------------------------------------------------------
-- `REVOKE ALL FROM PUBLIC` d'abord, puis des `GRANT` NOMMES. L'ordre compte:
-- l'inverse laisserait une fenetre pendant laquelle PUBLIC conserve le droit.
--
-- CE QUI A DICTE LA LISTE DES BENEFICIAIRES. Les trois helpers de `0002_rls`
-- sont appeles DANS des policies RLS qui n'ont pas de clause `TO` — elles
-- s'appliquent donc a tous les roles. L'expression d'une policy est evaluee
-- avec les droits du role QUI INTERROGE, et non du proprietaire de la table:
-- chaque role susceptible de lire une table multi-tenant a donc besoin
-- d'EXECUTE. Les retirer a PUBLIC sans les rendre aux roles applicatifs
-- casserait toute lecture — c'est un durcissement qui doit rester deployable.
--
-- `anon` y figure a dessein: s'il interroge une table portant l'une de ces
-- policies, il lui faut le droit d'evaluer l'expression. Le lui refuser
-- produirait « permission denied for function » au lieu du zero ligne attendu
-- — un refus au mauvais endroit, qui masquerait le comportement RLS reel.
-- La fonction, elle, ne rend vrai que sur une appartenance effective.

revoke all on function public.is_org_member(uuid) from public;
grant execute on function public.is_org_member(uuid)
  to authenticated, anon, normative_backend, normative_governance;

revoke all on function public.has_org_role(uuid, org_role[]) from public;
grant execute on function public.has_org_role(uuid, org_role[])
  to authenticated, anon, normative_backend, normative_governance;

revoke all on function public.can_write(uuid) from public;
grant execute on function public.can_write(uuid)
  to authenticated, anon, normative_backend, normative_governance;

-- LES TROIS AUTRES SONT DES FONCTIONS DE DECLENCHEUR. Aucun role n'a besoin
-- d'EXECUTE pour qu'un declencheur les appelle: le retrait a PUBLIC est donc
-- SANS EFFET SUR LE FONCTIONNEMENT, et il ferme l'appel direct — qui, lui,
-- n'a aucune raison d'exister. `check_validator_is_authorised()` decide si un
-- ingenieur peut signer: la laisser appelable par `anon` n'apportait rien et
-- exposait une surface de plus.
revoke all on function check_validator_is_authorised() from public;
revoke all on function open_retention_period()          from public;
revoke all on function log_deliverable_transition()     from public;


-- ---------------------------------------------------------------------
-- C. LE CONTROLE QUI REFUSE UNE DERIVE — et non un simple commentaire
-- ---------------------------------------------------------------------
-- Un durcissement qui n'est verifie par rien se defait au premier
-- `CREATE OR REPLACE` distrait, et personne ne s'en apercoit. La fonction
-- ci-dessous ENUMERE l'etat attendu et LEVE si la base s'en ecarte. Elle est
-- appelee par les harnais, et elle peut l'etre par un auditeur.
--
-- ELLE NE REND PAS UN BOOLEEN. Un booleen se lit « faux » et se range; une
-- exception nomme l'objet, le defaut et le role fautif. La difference se
-- mesure le jour ou le controle rougit sur une base qu'on ne connait pas.
-- SECURITY DEFINER, ET C'EST INDISPENSABLE. Sans cela, l'appelant devrait
-- endosser un role d'autorite pour la lancer — or aucun role ne le peut, et
-- c'est precisement ce que le durcissement garantit. Un controle qui exige,
-- pour s'executer, la capacite qu'il verifie absente n'est pas appelable.
-- Mesure: le harnais recevait « permission denied to set role
-- eurostruct_normative_writer » et lisait ce refus comme une derive.
--
-- Elle ne lit que des catalogues et n'ecrit rien: le definisseur n'ouvre donc
-- aucune surface d'ecriture.
create or replace function assert_authority_surface_hardened() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  r record;
  ecarts text[] := array[]::text[];
  -- Les fonctions qui doivent appartenir a une AUTORITE, jamais au migrateur
  -- ni a un role applicatif.
  attendues text[] := array[
    'resolve_normative_authorisation', 'normative_grant_is_active',
    'normative_authorisation_snapshot', 'assert_digest_integrity',
    'reserve_normative_audit_namespace', 'forbid_normative_audit_mutation',
    'consume_normative_authorisation', 'log_normative_event',
    'check_normative_grant', 'check_normative_grant_revocation',
    'check_normative_confirmation', 'check_normative_confirmation_revocation',
    'bootstrap_normative_administrator'];
  autorites text[] := array['eurostruct_normative_writer',
                            'eurostruct_normative_bootstrap',
                            'eurostruct_normative_activator'];
begin
  for r in
    select p.proname,
           pg_get_userbyid(p.proowner) as proprietaire,
           p.proconfig,
           has_function_privilege('public', p.oid, 'EXECUTE') as ouverte
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname = any(attendues)
  loop
    if not (r.proprietaire = any(autorites)) then
      ecarts := ecarts || format(
        '%s appartient a « %s », qui n''est pas un role d''autorite',
        r.proname, r.proprietaire);
    end if;
    -- `proconfig` porte les `SET` attaches a la fonction. Absent = la fonction
    -- herite du `search_path` de l'appelant, qui peut donc la detourner.
    if r.proconfig is null
       or not exists (select 1 from unnest(r.proconfig) c
                       where c like 'search\_path=%') then
      ecarts := ecarts || format('%s n''a pas de search_path fixe', r.proname);
    end if;
    if r.ouverte then
      ecarts := ecarts || format('%s est EXECUTABLE PAR PUBLIC', r.proname);
    end if;
  end loop;

  -- LES SIX SECURITY DEFINER HORS DU SOUS-SYSTEME NORMATIF: on n'exige pas
  -- qu'elles changent de proprietaire — elles servent le multi-tenant et non
  -- l'autorite normative — mais PUBLIC ne doit plus les atteindre.
  for r in
    select p.proname, has_function_privilege('public', p.oid, 'EXECUTE') as ouverte
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.prosecdef
       and p.proname in ('is_org_member', 'has_org_role', 'can_write',
                         'check_validator_is_authorised',
                         'open_retention_period', 'log_deliverable_transition')
  loop
    if r.ouverte then
      ecarts := ecarts || format(
        '%s est SECURITY DEFINER et EXECUTABLE PAR PUBLIC', r.proname);
    end if;
  end loop;

  if array_length(ecarts, 1) > 0 then
    -- UN IDENTIFIANT D'INVARIANT STABLE, ET NON UNE PHRASE.
    --
    -- Un test qui reconnait une mise a mort sur « surface d'autorite non
    -- durcie » reconnait une PHRASE: elle se reformule, se traduit, se
    -- reindente, et le test cesse alors de distinguer un refus attendu d'une
    -- panne quelconque — sans rien dire. Le prefixe ci-dessous est un
    -- CONTRAT: il ne change pas quand le texte change.
    raise exception
      'AUTHORITY_0011_SURFACE_NOT_HARDENED: surface d''autorite non durcie: %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_authority_surface_hardened()
  owner to eurostruct_normative_writer;
revoke all on function assert_authority_surface_hardened() from public;
grant execute on function assert_authority_surface_hardened()
  to eurostruct_normative_writer, eurostruct_deployment;

comment on function assert_authority_surface_hardened is
  'Refuse une base dont la surface d''autorite a derive: fonction revenue a '
  'un proprietaire non-autorite, search_path perdu, ou EXECUTE rendu a '
  'PUBLIC. Leve en nommant chaque ecart; ne rend jamais un booleen, qui se '
  'lirait et se rangerait.';


-- ---------------------------------------------------------------------
-- LE DROIT DE CREATE REPART, comme il etait venu
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- LE DROIT DE CREATE REPART — ET IL FAUT LE VERIFIER, PAS L'ESPERER
-- ---------------------------------------------------------------------
-- UN `REVOKE` SUR `public` N'EST PAS UNE COMMANDE, C'EST UN VOEU.
--
-- Fait mesure sur PostgreSQL 16, dans la forme de deploiement ou le migrateur
-- possede la base ET detient un `CREATE ... WITH GRANT OPTION` explicite:
--
--   * un octroi fait PAR LE PROPRIETAIRE de la base est enregistre au nom de
--     `pg_database_owner`, et non au nom du role;
--   * `REVOKE create on schema public FROM eurostruct_normative_writer` emis
--     par ce meme role ne retire RIEN — pas d'erreur, pas meme un WARNING
--     visible, et `ON_ERROR_STOP=1` ne s'arrete pas;
--   * consequence mesuree: apres `0010`, `eurostruct_normative_writer` — le
--     proprietaire de TOUTES les tables d'autorite — conservait `CREATE` sur
--     `public` pour toute la vie de la base. Personne ne le voyait, parce que
--     personne ne verifiait le RESULTAT de la revocation.
--
-- ON REVOQUE DONC SOUS LE DONNEUR REEL, celui que le catalogue nomme. C'est
-- la seule forme qui prend, et elle ne suppose rien de la forme du
-- deploiement.
--
-- `GRANTED BY` NE SUFFIT PAS: PostgreSQL 16 rend « grantor must be current
-- user ». Il faut donc ENDOSSER le donneur — ce que le proprietaire de la
-- base peut faire pour `pg_database_owner`, dont il est membre. `SET LOCAL`
-- meurt avec la transaction, comme partout ailleurs dans ce schema.
do $$
declare
  donneur text;
  appelant text := current_user;
begin
  for donneur in
    select distinct pg_get_userbyid(a.grantor)
      from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public'
       and a.privilege_type = 'CREATE'
       -- TOUS LES ROLES D'AUTORITE, ET PAS SEULEMENT LES DEUX QUE CETTE
       -- MIGRATION A ELLE-MEME SERVIS. Mesure: l'ACTIVATEUR conservait lui
       -- aussi CREATE — le sceau le lui accorde en phase 0 et croit le
       -- retirer a la fin, avec la meme revocation inefficace. Une migration
       -- qui s'appelle « durcissement de la surface » ne peut pas laisser
       -- l'ecart chez le voisin en disant qu'il n'est pas a elle.
       and a.grantee in ('eurostruct_normative_writer'::regrole::oid,
                         'eurostruct_normative_bootstrap'::regrole::oid,
                         'eurostruct_normative_activator'::regrole::oid,
                         'eurostruct_authority_backend'::regrole::oid,
                         'normative_backend'::regrole::oid,
                         'normative_governance'::regrole::oid)
  loop
    -- ON N'AVALE PAS L'ECHEC. Si le donneur n'est pas endossable, la
    -- migration doit le dire: le privilege resterait, et c'est precisement
    -- ce que personne ne voyait avant.
    execute format('set local role %I', donneur);
    execute 'revoke create on schema public from '
            'eurostruct_normative_writer, eurostruct_normative_bootstrap, '
            'eurostruct_normative_activator, eurostruct_authority_backend, '
            'normative_backend, normative_governance';
    execute format('set local role %I', appelant);
  end loop;
end
$$;

-- ---------------------------------------------------------------------
-- POSTCONDITION DE 0011 — appelee par la MIGRATION, pas par un harnais
-- ---------------------------------------------------------------------
-- UNE ASSERTION QUE SEULS LES TESTS APPELLENT NE PROTEGE RIEN.
-- `assert_authority_surface_hardened()` existait depuis le premier jet de
-- cette migration et AUCUN chemin produit ne l'executait: seul
-- `authority_sql_hardening.sh` l'invoquait, c'est-a-dire quelqu'un qui pense
-- a lancer la suite. Un deploiement reel ne la rencontrait jamais.
--
-- CE QUE CELA COUTAIT, MESURE CINQ FOIS DANS CE JALON: PostgreSQL 16
-- n'echoue pas sur un GRANT ou un REVOKE emis sans le droit requis — il emet
-- un WARNING et ne fait rien — et `psql -v ON_ERROR_STOP=1` ne s'arrete pas
-- sur un WARNING. Chacun des treize GRANT/REVOKE ci-dessus pouvait donc
-- n'avoir aucun effet, et la migration se terminer « avec succes » en
-- laissant la surface exactement dans l'etat qu'elle pretendait durcir.
--
-- SA PLACE EST ICI, ET PAS AILLEURS: apres TOUS les changements de
-- catalogue — transferts de propriete, revocations, octrois, retrait de
-- CREATE — et AVANT l'inscription au registre. Une migration refusee ne doit
-- pas laisser de ligne disant qu'elle a ete appliquee.
select assert_authority_surface_hardened();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
