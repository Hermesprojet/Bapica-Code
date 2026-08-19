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
-- Roles: deux roles de service, et DEUX ROLES D'AUTORITE non connectables
-- ---------------------------------------------------------------------
-- Les deux derniers ne servent qu'a POSSEDER une fonction SECURITY DEFINER.
-- C'est le mecanisme d'origine non forgeable de cette migration: a
-- l'interieur d'une fonction SECURITY DEFINER, `current_user` est le
-- proprietaire de la fonction. Un declencheur qui exige
-- `current_user = eurostruct_normative_writer` ne peut donc etre satisfait
-- QUE par un appel passe par cette fonction — et personne ne peut prendre ce
-- role, faute d'en etre membre.
--
-- Ce qui a ete essaye avant, et qui ne tenait pas: un parametre de session
-- (`set_config('eurostruct.normative_audit','on')`) pose comme preuve
-- d'origine. N'importe quel appelant peut le poser. Le contre-exemple a ete
-- verifie: une fausse trace normative forgee en trois lignes, et rendue
-- immuable dans la foulee.
--
-- MODELE DE MENACE. Ces garanties visent les ROLES APPLICATIFS. Un
-- superutilisateur PostgreSQL peut desactiver un declencheur, changer un
-- proprietaire ou modifier une fonction: il n'est pas un adversaire que la
-- base puisse contenir, et aucun test ne pretend le contraire.
do $$
declare manquantes text;
begin
  -- LE SCEAU DE LA PHASE 0 EST EXIGE (6.3b6c).
  --
  -- Ce bloc CREAIT les six roles canoniques. Il ne le fait plus: c'est la
  -- phase 0 — `db/control_plane/0001_normative_seal.sql`, appliquee par le
  -- qui les cree, avec les quatre tables de confiance et les fonctions qui
  -- les ecrivent.
  --
  -- POURQUOI CE FICHIER NE PEUT PLUS LES CREER. La phase 1 doit pouvoir
  -- endosser les roles qu'elle rend proprietaires de ses fonctions. Si elle
  -- creait aussi le proprietaire de la RACINE, elle pourrait l'endosser — et
  -- ecrire l'activation elle-meme. Contre-exemple mesure sur fc13990:
  -- `set role eurostruct_normative_activator` puis un `insert` suffisaient a
  -- rendre l'etat ACTIF sans finalisation.
  --
  -- REFUS PLUTOT QU'INSTALLATION PARTIELLE: une phase 1 appliquee sans sceau
  -- laisserait une base ou la racine n'appartient a personne.
  select coalesce(string_agg(t.nom, ', ' order by t.nom), '')
    into manquantes
    from unnest(array['normative_control_plane', 'normative_activation',
                      'normative_approved_settings',
                      'normative_finalization_intent',
                      'normative_seal_metadata']) as t(nom)
   where not exists (
     select 1 from pg_class c
       join pg_roles o on o.oid = c.relowner
      where c.relname = t.nom
        and o.rolname = 'eurostruct_normative_activator'
        and c.relrowsecurity and c.relforcerowsecurity);
  if manquantes <> '' then
    raise exception
      'le sceau normatif est absent ou incomplet (%). La phase 0 '
      '(db/control_plane/0001_normative_seal.sql) doit etre appliquee PAR LE '
      'PLAN DE CONTROLE avant cette migration: c''est elle qui pose la racine '
      'de confiance, hors de portee du role qui applique les migrations.',
      manquantes
      using errcode = 'insufficient_privilege';
  end if;
end
$$;

-- LA VERSION DU SCEAU EST EXIGEE, PAS SEULEMENT SA FORME (6.3b6d)
--
-- Le bloc ci-dessus verifie que cinq tables existent, appartiennent a
-- l'activateur et ont la RLS forcee. Cela ne dit pas QUELLE racine est en
-- place: une phase 0 d'une version anterieure presente exactement la meme
-- forme, et la phase 1 s'appliquerait dessus en supposant des fonctions et des
-- invariants qui n'y sont peut-etre pas.
--
-- LA LISTE EST EXPLICITE ET FERMEE. Une comparaison « superieure ou egale »
-- sur une chaine de version supposerait un ordre que rien ne garantit — et
-- accepterait, par construction, toutes les versions futures, c'est-a-dire
-- celles dont on ne sait rien. Ce qui est ecrit ici est ce qui a ete teste.
do $$
declare
  compatibles constant text[] := array['esc-normative-seal/1'];
  posee text;
begin
  select seal_version into posee
    from normative_seal_metadata
   order by installed_at desc, seal_version desc limit 1;

  if posee is null then
    raise exception
      'SEAL_VERSION_MISMATCH: le sceau ne declare aucune version. La racine '
      'est presente mais sans identite: elle ne peut pas etre reconnue.'
      using errcode = 'ES002';
  end if;

  if not (posee = any (compatibles)) then
    raise exception
      'SEAL_VERSION_MISMATCH: cette base porte le sceau « % »; cette migration '
      'exige l''une des versions suivantes: %. Mettez le sceau a niveau depuis '
      'db/control_plane/ avant d''appliquer la phase 1 — voir '
      'docs/DEPLOIEMENT_PREREQUIS.md, section « Faire evoluer le sceau ».',
      posee, array_to_string(compatibles, ', ')
      -- LE MEME CODE POUR LA MEME CLASSE D'ERREUR (6.3b6e). Ce refus retombait
      -- sur `insufficient_privilege`, generique, alors que la phase 0 emet
      -- ES002 pour exactement la meme situation: un orchestrateur ne pouvait
      -- pas brancher dessus.
      using errcode = 'ES002';
  end if;
end
$$;


-- PREREQUIS DE DEPLOIEMENT, verifie ici et non seulement dans les tests: ces
-- roles peuvent PREEXISTER dans un environnement gere, avec des attributs et
-- des appartenances que cette migration n'a pas choisis. Si l'un d'eux est
-- privilegie, ou si un role non fiable en est membre, toutes les garanties de
-- moindre privilege ci-dessous sont vides — mieux vaut refuser la migration
-- que l'appliquer sur une base ou elle ne protege rien.
do $$
declare r record;
begin
  for r in select rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
             from pg_roles
            where rolname in ('normative_backend', 'normative_governance',
                              'eurostruct_normative_writer',
                              'eurostruct_normative_bootstrap',
                              'eurostruct_normative_activator')
  loop
    if r.rolsuper or r.rolbypassrls or r.rolcreaterole or r.rolcreatedb then
      raise exception
        'prerequis non tenu: le role % porte un attribut privilegie '
        '(super=%, bypassrls=%, createrole=%, createdb=%). La RLS ne le '
        'contiendrait pas.', r.rolname, r.rolsuper, r.rolbypassrls,
        r.rolcreaterole, r.rolcreatedb;
    end if;
  end loop;

  -- Le sens INVERSE, celui qu'on oublie: un role non fiable membre d'un role
  -- de service en heriterait tous les droits.
  --
  -- CE CONTROLE A ETE REECRIT EN 6.3b4, et la version precedente etait
  -- doublement fausse. Elle joignait `pg_auth_members` UNE FOIS — donc
  -- l'appartenance DIRECTE seulement — et comparait a une LISTE FERMEE DE
  -- NOMS ('authenticated', 'anon', 'public'). Trois contre-exemples verifies
  -- passaient: un role LOGIN arbitraire membre direct du writer, un role
  -- membre direct du bootstrap, et une appartenance TRANSITIVE a deux sauts
  -- via un relais. Aucun n'etait nomme dans la liste, et le troisieme aurait
  -- echappe au controle meme s'il l'avait ete.
  --
  -- `pg_has_role(..., 'MEMBER')` regle les deux: il est transitif par
  -- construction, et il ne demande le nom d'aucun role tiers. 'MEMBER' et non
  -- 'USAGE': un membre NOINHERIT n'herite pas des droits, mais il peut
  -- toujours faire SET ROLE et les obtenir. C'est la meme prise.
  --
  -- LES ROLES D'AUTORITE N'ONT AUCUN MEMBRE. Pas « aucun membre non fiable »:
  -- aucun, jamais. Toute la reserve du namespace d'audit et toute la branche
  -- d'amorcage reposent sur le fait que `current_user` ne peut valoir ces
  -- noms que depuis l'interieur d'une fonction SECURITY DEFINER. Un seul
  -- membre, et `current_user` cesse d'etre une preuve d'origine.
  for r in
    select autorite.rolname as cible, membre.rolname as porteur,
           membre.rolcanlogin as connectable
      from pg_roles autorite
      cross join pg_roles membre
     where autorite.rolname in ('eurostruct_normative_writer',
                                'eurostruct_normative_bootstrap',
                                'eurostruct_normative_activator')
       and membre.oid <> autorite.oid
       -- Un superutilisateur satisfait pg_has_role pour tout role. Le modele
       -- de menace l'exclut explicitement: il peut desactiver les
       -- declencheurs, la base ne le contient pas. L'inclure ici ne
       -- protegerait rien et rendrait la migration inapplicable partout.
       and not membre.rolsuper
       -- Et le role qui EXERCE la migration, 6.3b5. Il doit etre membre le
       -- temps des transferts de propriete — PostgreSQL l'exige — et il rend
       -- cette appartenance avant la fin du fichier. L'exclure ici n'ouvre
       -- rien: la restitution est VERIFIEE en fin de migration, et c'est cette
       -- verification-la qui porte la garantie durable. Sans cette exception,
       -- la migration se refusait elle-meme des le second passage.
       and membre.rolname <> current_user
       -- SET OU USAGE, ET NON « MEMBER » (6.3b6b).
       --
       -- `MEMBER` est vrai des qu'une appartenance existe, ADMIN seul compris.
       -- Or PostgreSQL 16 DONNE d'office un ADMIN au createur d'un role (fait
       -- F1, mesure): dans la forme Supabase, le plan de controle qui
       -- provisionne les roles d'autorite en detient donc un, inevitablement
       -- et irrevocablement. Exiger ici son absence rendait la migration
       -- inapplicable — constate: « le role b1ctl est membre de
       -- eurostruct_normative_writer », alors que ce role est precisement
       -- celui qui a legitimement provisionne.
       --
       -- Ce qui est dangereux MAINTENANT, c'est d'ENDOSSER ou d'HERITER: les
       -- deux capacites qui font perdre a `current_user` sa valeur de preuve.
       -- L'ADMIN residuel, lui, est traite par `assert_normative_topology()`
       -- en etat ACTIVE, ou il n'est tolere que pour UN plan de controle
       -- nomme et fige.
       and (pg_has_role(membre.rolname, autorite.rolname, 'SET')
            or pg_has_role(membre.rolname, autorite.rolname, 'USAGE'))
  loop
    raise exception
      'prerequis non tenu: le role « % » peut endosser ou heriter de « % » '
      '(connectable: '
      '%). Les roles d''autorite ne doivent avoir AUCUN membre: leur seul '
      'role est de rendre `current_user` significatif a l''interieur des '
      'fonctions SECURITY DEFINER. Un membre peut faire SET ROLE et forger '
      'une origine normative.', r.porteur, r.cible, r.connectable;
  end loop;

  -- Les roles d'autorite ne se connectent pas non plus. Verifie ICI et pas
  -- seulement dans les tests: la migration peut s'appliquer sur une base ou
  -- ils preexistent avec LOGIN.
  for r in
    select rolname as porteur from pg_roles
     where rolname in ('eurostruct_normative_writer',
                       'eurostruct_normative_bootstrap',
                       'eurostruct_normative_activator')
       and rolcanlogin
  loop
    raise exception
      'prerequis non tenu: le role d''autorite « % » peut se connecter. '
      'Quelqu''un s''y authentifierait directement et `current_user` '
      'vaudrait ce nom hors de toute fonction controlee.', r.porteur;
  end loop;

  -- ROLES DE SERVICE. Eux ont vocation a etre endosses par l'application:
  -- exiger qu'ils n'aient aucun membre rendrait le deploiement impossible.
  -- Deux dangers distincts, et un seul est derivable du catalogue.
  --
  -- 6.3b5. La version precedente comparait a la liste fermee
  -- ('authenticated', 'anon') tout en pretendant, quelques lignes plus haut,
  -- ne nommer aucun role tiers. La contradiction etait reelle et elle est
  -- levee ici en separant ce que PostgreSQL SAIT de ce qu'il ne peut pas
  -- savoir.

  -- (a) ATTEINTE PRIVILEGIEE — entierement derivable du catalogue, donc
  --     aucune liste. Un role privilegie contourne de toute facon la RLS: s'il
  --     atteint en plus un role de service, le cloisonnement est doublement
  --     nominal. Aucune approbation ne peut rendre cela acceptable.
  for r in
    select service.rolname as cible, porteur.rolname as porteur,
           porteur.rolsuper, porteur.rolbypassrls,
           porteur.rolcreaterole, porteur.rolcreatedb
      from pg_roles service
      cross join pg_roles porteur
     where service.rolname in ('normative_backend', 'normative_governance')
       and porteur.oid <> service.oid
       and not porteur.rolsuper          -- hors modele de menace
       and (porteur.rolbypassrls or porteur.rolcreaterole or porteur.rolcreatedb)
       -- SET OU USAGE, ET NON « MEMBER ». PostgreSQL 16 donne d'office un
       -- ADMIN au createur d'un role (fait F1, mesure): le plan de controle
       -- qui provisionne en detient donc un sur les roles de service, sans
       -- pouvoir s'en defaire. Ce qui est dangereux est d'ENDOSSER ou
       -- d'HERITER; l'ADMIN residuel est traite en etat ACTIVE par
       -- `assert_normative_topology()`, ou il n'est tolere que pour le plan de
       -- controle fige.
       and (pg_has_role(porteur.rolname, service.rolname, 'SET')
            or pg_has_role(porteur.rolname, service.rolname, 'USAGE'))
  loop
    raise exception
      'prerequis non tenu: le role privilegie « % » atteint le role de '
      'service « % » (bypassrls=%, createrole=%, createdb=%). Un role qui '
      'contourne deja la RLS ne doit pas en plus heriter des droits '
      'd''ecriture normatifs.',
      r.porteur, r.cible, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb;
  end loop;

  -- (b) ATTEINTE PAR UN ROLE CONNECTABLE — derivable aussi, mais parfois
  --     LEGITIME: dans un deploiement Supabase, `authenticator` se connecte et
  --     endosse `service_role`, qui portera `normative_backend`. C'est le
  --     chemin normal, et l'interdire rendrait le produit indeployable.
  --
  --     FAIL-CLOSED: on refuse par defaut, et le deploiement DECLARE les roles
  --     connectables autorises. Une declaration absente refuse; elle n'est
  --     jamais deduite.
  --
  --     Pourquoi un parametre est acceptable ICI alors qu'il etait refuse pour
  --     le marqueur d'audit: celui-la etait lu A L'EXECUTION, par n'importe
  --     quelle session, et n'importe qui pouvait le poser. Celui-ci est lu
  --     PENDANT LA MIGRATION, et seul celui qui exerce les migrations peut la
  --     lancer. C'est sa declaration, pas celle d'un appelant quelconque.
  --
  --       ALTER DATABASE ma_base SET eurostruct.approved_service_logins
  --         = 'authenticator';
  for r in
    select service.rolname as cible, porteur.rolname as porteur
      from pg_roles service
      cross join pg_roles porteur
     where service.rolname in ('normative_backend', 'normative_governance')
       and porteur.oid <> service.oid
       and not porteur.rolsuper
       and porteur.rolcanlogin
       -- SET OU USAGE, ET NON « MEMBER ». PostgreSQL 16 donne d'office un
       -- ADMIN au createur d'un role (fait F1, mesure): le plan de controle
       -- qui provisionne en detient donc un sur les roles de service, sans
       -- pouvoir s'en defaire. Ce qui est dangereux est d'ENDOSSER ou
       -- d'HERITER; l'ADMIN residuel est traite en etat ACTIVE par
       -- `assert_normative_topology()`, ou il n'est tolere que pour le plan de
       -- controle fige.
       and (pg_has_role(porteur.rolname, service.rolname, 'SET')
            or pg_has_role(porteur.rolname, service.rolname, 'USAGE'))
       and porteur.rolname <> all (
             string_to_array(
               btrim(coalesce(
                 normative_declared_setting('eurostruct.approved_service_logins'),
                 '')),
               ','))
  loop
    raise exception
      'prerequis non tenu: le role connectable « % » atteint le role de '
      'service « % » sans avoir ete approuve. Si ce chemin est voulu, le '
      'declarer explicitement: ALTER DATABASE ... SET '
      'eurostruct.approved_service_logins = ''%%''. Une approbation absente '
      'refuse — elle n''est jamais deduite.', r.porteur, r.cible;
  end loop;

  -- (c) ATTEINTE PAR UN PORTEUR DE JETON — NON derivable du catalogue.
  --     Quels roles un JWT endosse est une convention de deploiement:
  --     PostgreSQL ne peut pas la connaitre, et pretendre la deduire serait
  --     une fausse garantie. Elle est donc DECLAREE, avec la convention
  --     Supabase pour defaut, et non gravee dans la migration.
  for r in
    select service.rolname as cible, jeton.rolname as porteur
      from pg_roles service
      cross join unnest(string_to_array(
        coalesce(nullif(normative_declared_setting('eurostruct.token_roles'), ''),
                 'authenticated,anon'), ',')) as t(nom)
      join pg_roles jeton on jeton.rolname = btrim(t.nom)
     where service.rolname in ('normative_backend', 'normative_governance')
       and not jeton.rolsuper
       and (pg_has_role(jeton.rolname, service.rolname, 'SET')
            or pg_has_role(jeton.rolname, service.rolname, 'USAGE'))
  loop
    raise exception
      'prerequis non tenu: le porteur de jeton « % » atteint le role de '
      'service « % ». Il en heriterait les droits d''ecriture, et le '
      'cloisonnement serait nominal.', r.porteur, r.cible;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- EMPRUNT TEMPORAIRE DE L'AUTORITE, le temps des transferts de propriete
-- ---------------------------------------------------------------------
-- 6.3b5. Ce bloc n'existait pas, et son absence rendait la migration
-- INAPPLICABLE par un role non superutilisateur — c'est-a-dire par la cible
-- de production reelle.
--
-- PostgreSQL exige, pour « ALTER FUNCTION ... OWNER TO r », que le
-- proprietaire courant soit MEMBRE de r. Un superutilisateur satisfait cette
-- condition partout et ne rencontre jamais l'obstacle; un role de migration
-- ordinaire s'y arrete net. La CI, superutilisateur, ne pouvait donc pas voir
-- le probleme — et c'est exactement ce que le test d'installation
-- non-superutilisateur existe pour attraper.
--
-- L'appartenance est prise ICI et RENDUE a la fin du fichier. Le prerequis
-- « les roles d'autorite n'ont aucun membre » est evalue AVANT ce bloc et
-- re-verifie APRES sa restitution, si bien que l'etat durable reste celui
-- qu'on garantit. Pendant la migration, c'est le role de migration qui
-- detient l'autorite — ce qui est vrai de toute facon: il vient d'ecrire les
-- fonctions.
-- PostgreSQL exige que le NOUVEAU PROPRIETAIRE d'une fonction ait CREATE sur
-- le schema qui la contient. Depuis PostgreSQL 15, le schema `public`
-- n'accorde plus CREATE a PUBLIC: les roles d'autorite ne l'ont donc pas, et
-- « ALTER FUNCTION ... OWNER TO » echoue avec « permission denied for schema
-- public ».
--
-- Un superutilisateur ne rencontre jamais ce controle. C'est le troisieme
-- obstacle qu'a revele l'installation non superutilisateur, apres REFERENCES
-- sur auth.users et l'ADMIN OPTION sur les roles d'autorite.
--
-- Le droit est sans portee pratique ici: ces roles sont NOLOGIN et n'ont aucun
-- membre, personne ne peut donc s'en servir pour creer quoi que ce soit.
-- L'ACTIVATEUR N'Y FIGURE PLUS (6.3b6c): il ne possede aucun objet cree par
-- cette migration. Ce qu'il possede est cree par la phase 0, sous le plan de
-- controle, et ce fichier n'a jamais a l'endosser.
grant usage, create on schema public
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- Ce qui a ete EMPRUNTE est note, pour ne rendre que cela. Un deploiement
-- peut avoir accorde l'appartenance lui-meme, avec ADMIN OPTION, parce que
-- les roles d'autorite preexistaient: la lui retirer sans l'avoir prise
-- casserait le passage suivant.
create temp table if not exists _esc_emprunt(role_name text) on commit preserve rows;

do $$
declare r text;
begin
  -- DEUX ROLES, ET NON TROIS (6.3b6c). L'emprunt de
  -- `eurostruct_normative_activator` est ce qui mettait la racine de confiance
  -- a portee du migrateur: il n'a plus lieu, et le role n'est plus jamais
  -- accorde a qui applique les migrations.
  foreach r in array array['eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap'] loop
    -- INCONDITIONNEL, et non « si pas deja membre ». En PostgreSQL 16, le
    -- role cree par un role CREATEROLE recoit une appartenance avec ADMIN
    -- OPTION mais SET FALSE: `pg_has_role(..., 'MEMBER')` est vrai, et
    -- pourtant « ALTER ... OWNER TO » echoue sur « must be able to SET ROLE ».
    -- Tester l'appartenance ne suffisait donc pas — il faut l'option SET, que
    -- ce GRANT pose explicitement.
    -- MAIS PAS SI L'OPTION SET EST DEJA LA (6.3b6b).
    --
    -- Quand le deploiement a provisionne correctement — le plan de controle a
    -- accorde « with admin option », donc avec SET —, ce GRANT ajoutait un
    -- SECOND octroi dont le DONNEUR est le migrateur lui-meme. Mesure: deux
    -- lignes par role d'autorite dans `pg_auth_members`, et la finalisation,
    -- exercee par le plan de controle, ne pouvait retirer que la sienne. La
    -- ligne auto-octroyee — porteuse de `set = true` — survivait, et le
    -- migrateur conservait la capacite qu'on croyait lui avoir retiree.
    if not pg_has_role(current_user, r, 'SET') then
      begin
        execute format('grant %I to %I with set true, inherit true', r, current_user);
        insert into _esc_emprunt(role_name) values (r);
      exception when insufficient_privilege then
        raise exception
          'le role de migration « % » ne peut pas emprunter « % ». Cela '
          'arrive quand les roles d''autorite PREEXISTENT, crees par un '
          'tiers: le migrateur n''en a alors pas l''ADMIN OPTION. Le '
          'deploiement doit le lui donner: GRANT % TO % WITH ADMIN OPTION.',
          current_user, r, r, current_user
          using errcode = 'insufficient_privilege';
      end;
    end if;
  end loop;
end
$$;






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


-- ---------------------------------------------------------------------
-- LES QUATRE ECRITURES NORMATIVES SONT FERMEES EN PENDING (6.3b6b, point 5)
-- ---------------------------------------------------------------------
-- Les quatre, et non trois: une habilitation accordee engage autant qu'une
-- confirmation, puisqu'elle autorise toutes les confirmations suivantes. Le
-- retrait aussi: retirer une confirmation change ce que le referentiel dit.
--
-- L'amorcage (`bootstrap_normative_administrator`) ecrit dans
-- `normative_authorisation_grants` et se trouve donc ferme par le meme
-- declencheur — c'est la cinquieme ecriture du contre-exemple, et elle est
-- fermee par la porte des quatre autres plutot que par une regle separee.
-- LE NOM DES DECLENCHEURS EST DELIBERE. PostgreSQL declenche les triggers
-- BEFORE ROW d'une meme table DANS L'ORDRE ALPHABETIQUE DE LEUR NOM. Le
-- prefixe `normative_activation_required_` les place donc avant
-- `normative_grants_are_checked` et ses equivalents.
--
-- CE N'EST PAS COSMETIQUE — mesure: sans ce prefixe, l'insertion etait bien
-- refusee, mais par le controle d'identite (« aucune identite authentifiee »).
-- Un refus qui ne nomme pas l'etat n'en est pas un: il disparaitrait des
-- qu'une identite authentifiee serait fournie, et l'ecriture normative
-- passerait alors en PENDING. L'etat du deploiement doit etre la PREMIERE
-- question posee, avant tout examen du contenu.
create trigger normative_activation_required_grants
  before insert on normative_authorisation_grants
  for each row execute function forbid_normative_write_while_pending();

create trigger normative_activation_required_grant_revocations
  before insert on normative_authorisation_revocations
  for each row execute function forbid_normative_write_while_pending();

create trigger normative_activation_required_confirmations
  before insert on normative_rule_confirmations
  for each row execute function forbid_normative_write_while_pending();

create trigger normative_activation_required_confirmation_revocations
  before insert on normative_rule_confirmation_revocations
  for each row execute function forbid_normative_write_while_pending();


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
-- CONSOMMER une habilitation: resoudre, verrouiller, revalider
-- ---------------------------------------------------------------------
-- 6.3b4 #3. Le motif « resoudre -> verrou partage -> revalider » n'existait
-- qu'a UN seul des quatre endroits qui consomment une habilitation. Audit du
-- code avant correction:
--
--   check_normative_grant                     verrou NON   revalidation NON
--   check_normative_grant_revocation          verrou NON   revalidation NON
--   check_normative_confirmation              verrou oui   revalidation oui
--   check_normative_confirmation_revocation   verrou NON   revalidation NON
--
-- Trois operations pouvaient donc etre autorisees par un octroi qu'une autre
-- transaction etait en train de retirer: octroyer une habilitation a un tiers,
-- en revoquer une, et retirer la confirmation d'un relecteur — cette derniere
-- etant precisement l'operation qu'on ne veut pas voir passer sur un pouvoir
-- deja retire.
--
-- La regle est desormais UNE FONCTION, et non une discipline a re-appliquer:
-- une consommation ecrite plus tard qui oublierait le verrou devrait pour cela
-- contourner explicitement cet appel.
--
-- POURQUOI RENDRE LE TUPLE PLUTOT QUE LEVER. L'absence d'habilitation n'est
-- pas une anomalie: c'est un refus ordinaire, et chaque operation le formule
-- avec ses propres termes — ce qui est refuse, sur quelle portee, et pourquoi
-- ce pouvoir-la ne se confond pas avec un autre. Fondre ces messages ici les
-- aurait tous appauvris. En revanche la REVOCATION EN VOL leve: elle n'est
-- pas un refus d'autorisation mais une course perdue, et le message doit le
-- dire.
create or replace function consume_normative_authorisation(
  p_actor      uuid,
  p_permission normative_permission,
  p_country    country_code,
  p_family     text,
  p_part       text,
  p_edition    text
) returns normative_authorisation_grants
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  habilitation normative_authorisation_grants;
begin
  habilitation := resolve_normative_authorisation(
    p_actor, p_permission, p_country, p_family, p_part, p_edition
  );

  if habilitation.id is null then
    return habilitation;      -- l'appelant formule son refus
  end if;

  -- Verrou PARTAGE sur l'octroi retenu, tenu jusqu'au commit: une revocation
  -- concurrente de cette habilitation devra attendre.
  --
  -- Un verrou consultatif, et non `SELECT ... FOR SHARE`: PostgreSQL exige le
  -- privilege UPDATE pour un verrou de ligne, et ces tables n'accordent JAMAIS
  -- UPDATE — c'est le fondement de leur immuabilite. Le verrou de ligne aurait
  -- donc oblige a ouvrir ce que la migration ferme.
  perform pg_advisory_xact_lock_shared(
    hashtext('eurostruct.normative.grantrow:' || habilitation.id::text));

  -- Et on RE-verifie apres avoir obtenu le verrou: si une revocation nous a
  -- precedes, elle est desormais visible. Sans cette relecture, le verrou ne
  -- servirait qu'a attendre, pas a decider.
  if not normative_grant_is_active(habilitation.id) then
    raise exception
      'operation refusee: l''habilitation % a ete revoquee pendant '
      'l''operation. Le pouvoir invoque n''existait plus au moment de '
      's''en servir.', habilitation.id
      using errcode = 'insufficient_privilege';
  end if;

  return habilitation;
end;
$$;

alter function consume_normative_authorisation(
    uuid, normative_permission, country_code, text, text, text)
  owner to eurostruct_normative_writer;
revoke all on function consume_normative_authorisation(
    uuid, normative_permission, country_code, text, text, text) from public;

comment on function consume_normative_authorisation is
  'Resout une habilitation, la verrouille en partage jusqu''au commit, et '
  'revalide qu''elle est active. TOUTE operation consommant une habilitation '
  'doit passer par ici: le verrou seul n''est pas une garantie, c''est la '
  'relecture qui suit qui en fait une.';


-- ---------------------------------------------------------------------
-- Le snapshot d'audit, ecrit par le serveur et par lui seul
-- ---------------------------------------------------------------------
-- STABLE, et non IMMUTABLE: elle appelle now(). Une fonction declaree
-- IMMUTABLE peut etre pre-evaluee et mise en cache par le planificateur; la
-- declarer ainsi alors qu'elle lit l'horloge est un mensonge au planificateur,
-- pas seulement une etiquette inexacte.
create or replace function normative_authorisation_snapshot(
  g normative_authorisation_grants
) returns jsonb
language sql
stable
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
  if p_action not like 'normative.%' then
    raise exception
      'action « % » hors du namespace normatif: cette fonction est le seul '
      'producteur autorise de « normative.* ».', p_action
      using errcode = 'check_violation';
  end if;

  -- Cette fonction est SECURITY DEFINER et appartient a
  -- `eurostruct_normative_writer`. `current_user` vaut donc ce role ICI, et
  -- nulle part ailleurs: c'est ce que le declencheur d'insertion verifie.
  --
  -- org_id et project_id restent NULL: un evenement normatif n'appartient a
  -- aucun client. C'est la raison pour laquelle audit_log les declare
  -- nullables.
  insert into audit_log (user_id, action, entity, entity_id, payload)
  values (p_user, p_action, p_entity, p_entity_id, p_payload);
end;
$$;

alter function log_normative_event(text, text, uuid, jsonb, uuid)
  owner to eurostruct_normative_writer;


-- =====================================================================
-- Amorcage: la racine de confiance
-- =====================================================================
-- Elle ne cree QUE de l'administration, jamais un droit de verification:
-- sans quoi la premiere personne installee pourrait confirmer seule tout le
-- referentiel d'une juridiction.
--
-- SECURITY DEFINER, possedee par `eurostruct_normative_bootstrap`.
--
-- Ce commentaire annoncait SECURITY INVOKER jusqu'en 6.3b4, alors que la
-- fonction etait DEFINER depuis 6.3b2. Il decrivait donc un raisonnement de
-- securite — « l'insertion s'execute avec les droits de l'appelant » — qui
-- n'etait plus celui du code, et un lecteur s'y serait fie. Une documentation
-- de securite fausse est une garantie fausse.
--
-- POURQUOI DEFINER. Le declencheur des octrois n'accepte `origin =
-- 'bootstrap'` que si `current_user` vaut le role d'autorite. Cela n'a de sens
-- que si la fonction s'execute SOUS ce role, donc en DEFINER, et si personne
-- ne peut prendre ce role — ce que les prerequis de deploiement verifient
-- desormais par `pg_has_role`, transitivement.
--
-- ROLE DE DEPLOIEMENT AUTORISE, ARRETE ICI.
--
-- La question restait ouverte depuis 6.3b1 (« le choix DEFINITIF reste
-- ouvert »). Elle est tranchee: l'amorcage est reserve au ROLE QUI EXERCE LES
-- MIGRATIONS, c'est-a-dire le proprietaire de la fonction —
-- `eurostruct_normative_bootstrap` — et aux superutilisateurs. EXECUTE est
-- retire a PUBLIC et accorde a AUCUN role applicatif, ce que `virgin_root.sql`
-- verifie.
--
-- Concretement, en deploiement: la migration est appliquee par le role
-- d'administration de la base (`postgres` chez la plupart des hebergeurs
-- geres, y compris Supabase), et c'est ce role qui appelle une fois
-- `bootstrap_normative_administrator()`. Aucun role de connexion applicative
-- ne le peut, ni ne doit le pouvoir.
--
-- L'appel est trace: `session_user` est inscrit dans l'audit d'amorcage a cote
-- de `current_user`. Les deux sont necessaires et disent des choses
-- differentes — `current_user` vaut toujours le role d'autorite a l'interieur
-- d'une fonction DEFINER, et ne designe donc PAS qui a appele. `session_user`,
-- lui, n'est pas modifie par SECURITY DEFINER et nomme le role reellement
-- connecte. Sans lui, l'audit de l'evenement le plus sensible de toute la
-- chaine — l'ouverture de la racine de confiance — ne disait pas qui l'avait
-- ouverte.
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
begin
  -- Deux appels concurrents doivent en voir un seul aboutir. Le verrou
  -- serialise le controle d'existence ci-dessous; l'index partiel
  -- normative_bootstrap_is_singular le garantit structurellement meme si le
  -- verrou etait contourne. Deux garde-fous, deux portees.
  -- Verrou COMMUN a toute operation touchant l'ensemble actif des
  -- administrateurs: amorcage, octroi d'une administration, revocation d'une
  -- administration. Un verrou par ligne ne suffisait pas — deux revocations
  -- visant deux octrois DIFFERENTS ne se croisent jamais, chacune voit
  -- l'autre administrateur encore actif, et les deux passent. Contre-exemple
  -- verifie: zero administrateur restant, gouvernance perdue.
  perform pg_advisory_xact_lock(hashtext('eurostruct.normative.administration'));

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
                       -- Vaut TOUJOURS le role d'autorite proprietaire de
                       -- cette fonction: utile pour prouver le chemin, inutile
                       -- pour savoir qui a appele.
                       'performed_by_db_user', current_user,
                       -- Le role REELLEMENT CONNECTE. SECURITY DEFINER ne le
                       -- modifie pas. C'est la seule trace de QUI a ouvert la
                       -- racine de confiance — l'evenement le plus sensible de
                       -- toute la chaine, et il etait jusqu'ici anonyme.
                       'performed_by_session_user', session_user),
    null
  );

  return nouvel_id;
end;
$$;

-- Possedee par le role d'autorite NOLOGIN: `current_user` vaut donc ce role
-- a l'interieur, et c'est ce que le declencheur des octrois exige pour
-- accepter `origin = 'bootstrap'`. Personne ne peut prendre ce role.
alter function bootstrap_normative_administrator(uuid, text, text)
  owner to eurostruct_normative_bootstrap;
revoke all on function bootstrap_normative_administrator(uuid, text, text)
  from public;

-- EXECUTE ACCORDE INTENTIONNELLEMENT, 6.3b5.
--
-- L'ACL precedente n'accordait EXECUTE a personne: seuls le proprietaire de
-- la fonction et un superutilisateur pouvaient amorcer. C'etait presente
-- comme « la position la plus restrictive possible », et c'en etait une —
-- mais elle rendait le produit INDEPLOYABLE sur une cible ou le role de
-- migration n'est pas superutilisateur, ce qui est le cas de toutes les
-- offres gerees, Supabase compris. Une restriction qui interdit l'usage
-- prevu n'est pas une garantie, c'est un defaut qui n'a pas encore ete
-- rencontre.
--
-- Le droit est donc accorde a un role NOMME, `eurostruct_deployment`, auquel
-- le deploiement rattache son role de migration:
--
--   GRANT eurostruct_deployment TO <role-de-migration>;
--
-- CE QUE CE ROLE N'EST PAS. Il n'est membre d'AUCUN role d'autorite, et les
-- prerequis ci-dessus le refuseraient s'il l'etait. Il peut donc OUVRIR la
-- chaine de confiance — une fois, l'index d'unicite y veille — sans pouvoir
-- pour autant fabriquer une trace normative ni emprunter la branche
-- « bootstrap » d'une insertion brute. Ouvrir la chaine et forger une preuve
-- restent deux pouvoirs distincts.
grant execute on function bootstrap_normative_administrator(uuid, text, text)
  to eurostruct_deployment;

-- `eurostruct_deployment`, en un paragraphe:
--
--   Role de deploiement. Recoit EXECUTE sur l'amorcage normatif, et rien
--   d'autre. A rattacher au role qui exerce les migrations:
--       GRANT eurostruct_deployment TO <role-de-migration>;
--   N'est membre d'aucun role d'autorite et ne doit jamais le devenir — les
--   prerequis ci-dessus refusent la migration si cela arrivait.
--
-- Ecrit ICI et non par « COMMENT ON ROLE »: commenter un role exige l'ADMIN
-- OPTION dessus, qu'un role de migration n'a pas quand les roles preexistent.
-- La migration echouait donc sur une ligne de DOCUMENTATION — quatrieme
-- obstacle revele par l'installation non superutilisateur. Un role est de
-- toute facon un objet de CLUSTER: le commenter depuis une migration de base
-- ecrirait dans un espace partage par toutes les bases de l'instance.

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
-- SECURITY DEFINER, possede par `eurostruct_normative_writer`.
--
-- Deux consequences voulues. D'abord le declencheur obtient les droits dont
-- il a besoin — lire les octrois, journaliser — sans qu'aucun role applicatif
-- ne recoive le moindre EXECUTE. Ensuite `current_user` y vaut le role
-- d'autorite, ce qui est exactement ce que la reserve du namespace d'audit
-- exige: seule une trace produite depuis ce chemin est acceptee.
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
    -- Ce qui interdit REELLEMENT une insertion brute en « bootstrap », c'est
    -- la policy RLS: seul `eurostruct_normative_bootstrap` a le droit
    -- d'inserer une ligne dont l'origine est « bootstrap », et le backend a
    -- un `with check (origin = 'delegated')`. Une policy s'evalue contre le
    -- role reel: elle n'est pas contournable par un appelant.
    --
    -- Le controle ci-dessous est la seconde ligne. `auth.uid() IS NULL` seul
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

create trigger normative_grants_are_checked
  before insert on normative_authorisation_grants
  for each row execute function check_normative_grant();


-- ---------------------------------------------------------------------
-- Revocation d'autorisation
-- ---------------------------------------------------------------------
-- SECURITY DEFINER, possede par `eurostruct_normative_writer`.
--
-- Deux consequences voulues. D'abord le declencheur obtient les droits dont
-- il a besoin — lire les octrois, journaliser — sans qu'aucun role applicatif
-- ne recoive le moindre EXECUTE. Ensuite `current_user` y vaut le role
-- d'autorite, ce qui est exactement ce que la reserve du namespace d'audit
-- exige: seule une trace produite depuis ce chemin est acceptee.
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

create trigger normative_grant_revocations_are_checked
  before insert on normative_authorisation_revocations
  for each row execute function check_normative_grant_revocation();


-- ---------------------------------------------------------------------
-- Confirmation normative
-- ---------------------------------------------------------------------
-- SECURITY DEFINER, possede par `eurostruct_normative_writer`.
--
-- Deux consequences voulues. D'abord le declencheur obtient les droits dont
-- il a besoin — lire les octrois, journaliser — sans qu'aucun role applicatif
-- ne recoive le moindre EXECUTE. Ensuite `current_user` y vaut le role
-- d'autorite, ce qui est exactement ce que la reserve du namespace d'audit
-- exige: seule une trace produite depuis ce chemin est acceptee.
create or replace function check_normative_confirmation() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
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

create trigger normative_confirmation_revocations_are_checked
  before insert on normative_rule_confirmation_revocations
  for each row execute function check_normative_confirmation_revocation();


-- Les quatre declencheurs appartiennent au role d'autorite. Place ICI, apres
-- leur creation: un ALTER ne peut pas preceder le CREATE.
alter function check_normative_grant() owner to eurostruct_normative_writer;
alter function check_normative_grant_revocation()
  owner to eurostruct_normative_writer;
alter function check_normative_confirmation()
  owner to eurostruct_normative_writer;
alter function check_normative_confirmation_revocation()
  owner to eurostruct_normative_writer;

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

  -- L'autre sens, et il etait ouvert: faire BASCULER une ligne ordinaire vers
  -- « normative.* » par un UPDATE fabriquait une trace normative, que le
  -- controle ci-dessus rendait aussitot ineffacable. Empoisonnement a sens
  -- unique.
  if tg_op = 'UPDATE' and coalesce(new.action, '') like 'normative.%' then
    raise exception
      'une ligne de journal ordinaire ne peut pas devenir une trace '
      'normative (« % »): ce namespace est produit par log_normative_event, '
      'et par elle seule.', new.action
      using errcode = 'restrict_violation';
  end if;
  return coalesce(new, old);
end;
$$;

-- Le namespace « normative.* » est RESERVE en insertion. La protection ne
-- pouvait pas reposer sur l'absence de policy INSERT sur audit_log: c'est une
-- protection de circonstance, qui disparaitrait le jour ou quelqu'un ouvrirait
-- l'ecriture du journal pour une autre raison.
create or replace function reserve_normative_audit_namespace() returns trigger
language plpgsql as $$
begin
  -- L'utilisateur EFFECTIF, et non un parametre de session. A l'interieur de
  -- log_normative_event() — SECURITY DEFINER appartenant au role ci-dessous —
  -- `current_user` vaut ce role; partout ailleurs il vaut l'appelant reel.
  -- Personne ne peut prendre ce role: il est NOLOGIN et personne n'en est
  -- membre.
  --
  -- La version precedente lisait un GUC pose par set_config(). Contre-exemple
  -- verifie: n'importe quel role autorise a ecrire un evenement ordinaire
  -- posait le marqueur lui-meme et fabriquait une trace normative, que le
  -- declencheur d'immuabilite rendait ensuite ineffacable.
  if new.action like 'normative.%'
     and current_user <> 'eurostruct_normative_writer' then
    raise exception
      'le namespace « normative.* » est reserve: la trace « % » doit etre '
      'produite par log_normative_event(), sans quoi une preuve d''octroi ou '
      'de confirmation se fabriquerait a la main. Utilisateur effectif: %.',
      new.action, current_user
      using errcode = 'insufficient_privilege';
  end if;
  return new;
end;
$$;

create policy audit_normative_write on audit_log
  for insert to eurostruct_normative_writer with check (action like 'normative.%');

create trigger audit_log_normative_namespace_is_reserved
  before insert on audit_log
  for each row execute function reserve_normative_audit_namespace();

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

-- FRONTIERE D'ECRITURE, tranchee: `authenticated` ne peut plus INSERER.
--
-- SQL ne reproduit pas tous les invariants de NormativeReviewPackage — il ne
-- sait pas verifier qu'un dossier couvre les sources declarees par la
-- specification, ni qu'un `RequiredSource` correspond a un `EvidenceItem`.
-- Tant que l'insertion brute restait ouverte, la phrase « la conformite est
-- garantie cote moteur » etait fausse: le chemin SQL contournait precisement
-- ce moteur. Contre-exemple verifie: `items: [1]`, `schema_version`
-- inconnue et `quote_digest` absent, acceptes.
--
-- Toute ecriture passe donc par `normative_backend`, qui construit et valide
-- le paquet en Python AVANT d'ecrire. Les controles SQL ci-dessous restent la
-- seconde ligne — ils attrapent ce qu'un backend fautif laisserait passer,
-- ils ne remplacent pas sa validation.
grant select on normative_authorisation_grants          to authenticated;
grant select on normative_authorisation_revocations     to authenticated;
grant select on normative_rule_confirmations            to authenticated;
grant select on normative_rule_confirmation_revocations to authenticated;

grant insert on normative_authorisation_grants          to normative_backend;
grant insert on normative_authorisation_revocations     to normative_backend;
grant insert on normative_rule_confirmations            to normative_backend;
grant insert on normative_rule_confirmation_revocations to normative_backend;

-- Le backend NE LIT PAS la gouvernance des habilitations. Il n'en a pas
-- besoin: la resolution se fait dans les declencheurs, qui s'executent sous
-- le role d'autorite. Lui ouvrir les octrois lui apprendrait qui est habilite
-- a quoi, sans qu'aucun de ses usages ne l'exige.

-- Le role d'autorite, qui possede les declencheurs et la journalisation: il
-- lit la gouvernance pour resoudre une habilitation, et ecrit le journal.
grant select on normative_authorisation_grants          to eurostruct_normative_writer;
grant select on normative_authorisation_revocations     to eurostruct_normative_writer;
grant select on normative_rule_confirmations            to eurostruct_normative_writer;
grant select on normative_rule_confirmation_revocations to eurostruct_normative_writer;
grant insert on audit_log to eurostruct_normative_writer;
-- `audit_log.id` est un bigserial: sans USAGE sur sa sequence, l'insertion
-- echoue apres avoir passe tous les controles.
grant usage on sequence audit_log_id_seq to eurostruct_normative_writer;

-- Le role d'amorcage n'ecrit qu'un octroi, et une seule fois.
grant select, insert on normative_authorisation_grants
  to eurostruct_normative_bootstrap;
grant select on normative_authorisation_revocations
  to eurostruct_normative_bootstrap;

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
create policy normative_grants_bootstrap_read on normative_authorisation_grants
  for select to eurostruct_normative_bootstrap using (true);
create policy normative_grants_writer_read on normative_authorisation_grants
  for select to eurostruct_normative_writer using (true);
-- L'origine est tranchee PAR LE ROLE, dans la policy: le backend ne peut
-- ecrire que des octrois delegues, et seul le role d'amorcage peut ecrire une
-- origine « bootstrap ». Un `WITH CHECK` s'evalue contre le role reel de la
-- session; aucun appelant ne peut s'en affranchir.
create policy normative_grants_insert on normative_authorisation_grants
  for insert to normative_backend with check (origin = 'delegated');
create policy normative_grants_bootstrap_insert on normative_authorisation_grants
  for insert to eurostruct_normative_bootstrap
  with check (origin = 'bootstrap');

create policy normative_grant_revocations_own_read
  on normative_authorisation_revocations
  for select to authenticated using (
    exists (select 1 from normative_authorisation_grants g
             where g.id = grant_id and g.grantee_id = auth.uid())
  );
create policy normative_grant_revocations_governance_read
  on normative_authorisation_revocations
  for select to normative_governance using (true);
create policy normative_grant_revocations_bootstrap_read
  on normative_authorisation_revocations
  for select to eurostruct_normative_bootstrap using (true);
create policy normative_grant_revocations_writer_read
  on normative_authorisation_revocations
  for select to eurostruct_normative_writer using (true);
create policy normative_grant_revocations_insert
  on normative_authorisation_revocations
  for insert to normative_backend with check (true);

create policy normative_confirmations_own_read on normative_rule_confirmations
  for select to authenticated using (verifier_id = auth.uid());
create policy normative_confirmations_backend_read on normative_rule_confirmations
  for select to normative_backend using (true);
create policy normative_confirmations_governance_read
  on normative_rule_confirmations
  for select to normative_governance using (true);
create policy normative_confirmations_writer_read on normative_rule_confirmations
  for select to eurostruct_normative_writer using (true);
create policy normative_confirmations_insert on normative_rule_confirmations
  for insert to normative_backend with check (true);

-- L'auteur de la revocation, ET le signataire dont la confirmation est
-- visee. Ne montrer une revocation qu'a son auteur laissait un relecteur
-- ignorer qu'un tiers avait retire SA lecture — il l'aurait appris en voyant
-- son regard disparaitre du decompte, sans savoir ni par qui ni pourquoi.
create policy normative_confirmation_revocations_own_read
  on normative_rule_confirmation_revocations
  for select to authenticated using (
    revoked_by = auth.uid()
    or exists (select 1 from normative_rule_confirmations c
                where c.id = confirmation_id and c.verifier_id = auth.uid())
  );
create policy normative_confirmation_revocations_backend_read
  on normative_rule_confirmation_revocations
  for select to normative_backend using (true);
create policy normative_confirmation_revocations_governance_read
  on normative_rule_confirmation_revocations
  for select to normative_governance using (true);
create policy normative_confirmation_revocations_insert
  on normative_rule_confirmation_revocations
  for insert to normative_backend with check (true);


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
revoke all on function reserve_normative_audit_namespace() from public;

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

-- Les deux roles d'autorite ont besoin des auxiliaires que les declencheurs
-- et l'amorcage appellent. Ils sont NOLOGIN et personne n'en est membre: leur
-- accorder EXECUTE n'ouvre rien a un role applicatif, et un test verifie que
-- `authenticated`, `normative_backend` et `normative_governance` n'en ont
-- aucun.
grant execute on function normative_grant_is_active(uuid)
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;
grant execute on function resolve_normative_authorisation(
  uuid, normative_permission, country_code, text, text, text)
  to eurostruct_normative_writer;
grant execute on function normative_authorisation_snapshot(
  normative_authorisation_grants) to eurostruct_normative_writer;
grant execute on function assert_digest_integrity(text, text, text, text)
  to eurostruct_normative_writer;
grant execute on function log_normative_event(text, text, uuid, jsonb, uuid)
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- `auth.uid()` est lue par les declencheurs, qui s'executent desormais sous le
-- role d'autorite. En deploiement Supabase le schema `auth` est deja lisible
-- par les roles de service; en local il faut l'ouvrir explicitement.
do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'auth') then
    execute 'grant usage on schema auth to eurostruct_normative_writer,
             eurostruct_normative_bootstrap';
    execute 'grant execute on function auth.uid() to
             eurostruct_normative_writer, eurostruct_normative_bootstrap';
    execute 'grant select on auth.users to eurostruct_normative_writer,
             eurostruct_normative_bootstrap';

    -- ET ON VERIFIE QUE C'EST PASSE.
    --
    -- « GRANT » n'echoue pas quand celui qui l'execute n'a pas le GRANT
    -- OPTION: il emet un WARNING et n'accorde RIEN. Sous superutilisateur la
    -- question ne se pose pas; sous un role de migration ordinaire, les trois
    -- lignes ci-dessus peuvent donc ne rien faire du tout — sans erreur, sans
    -- echec de migration, et la chaine normative se casse plus tard, a la
    -- premiere confirmation, sur un « permission denied for schema auth » que
    -- rien ne relie a sa cause. Verifie: c'est exactement ce qui se produisait.
    if not has_schema_privilege('eurostruct_normative_writer', 'auth', 'USAGE')
       or not has_table_privilege('eurostruct_normative_writer', 'auth.users',
                                  'SELECT') then
      raise exception
        'les roles d''autorite n''ont pas obtenu l''acces au schema « auth ». '
        'Le role de migration « % » ne detient pas le GRANT OPTION dessus, et '
        'PostgreSQL a emis un simple avertissement. Le deploiement doit '
        'accorder ces droits lui-meme, ou donner le GRANT OPTION: '
        'GRANT USAGE ON SCHEMA auth TO % WITH GRANT OPTION; '
        'GRANT SELECT ON auth.users TO % WITH GRANT OPTION;',
        current_user, current_user, current_user
        using errcode = 'insufficient_privilege';
    end if;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- LA RESTITUTION N'APPARTIENT PAS A LA MIGRATION (6.3b6b)
-- ---------------------------------------------------------------------
-- CE QUI ETAIT ECRIT ICI, ET POURQUOI C'ETAIT IMPOSSIBLE.
--
-- Un bloc « restitution inconditionnelle ou refus » tentait
--
--     revoke eurostruct_normative_writer from <migrateur>
--
-- puis refusait la migration si une appartenance UTILISABLE subsistait.
--
-- FAIT DE POSTGRESQL 16, MESURE (voir db/test/two_phase_deployment.sh, F2):
-- un role ne peut JAMAIS revoquer sa propre appartenance quand le donneur est
-- un autre role — ni directement, ni par « GRANTED BY ». `REVOKE` emet un
-- simple AVERTISSEMENT, repond « REVOKE ROLE », et la ligne survit.
--
-- Or, dans le seul deploiement sain, l'appartenance vient PRECISEMENT d'un
-- autre role: le plan de controle, ou le superutilisateur qui a provisionne.
-- Le bloc etait donc structurellement voue a refuser, et il refusait: la
-- migration ne pouvait pas s'appliquer sous un migrateur non superutilisateur
-- correctement provisionne.
--
-- LA RESTITUTION EST DONC EXERCEE PAR LE DONNEUR, EN PHASE 2, par
-- `normative_finalize_deployment()`. La phase 1 se termine en PENDING, avec
-- l'emprunt encore en place — ce qui est l'etat exact de la realite, et non
-- une approximation qu'on maquille.
--
-- La table temporaire d'emprunt disparait avec la session: la finalisation ne
-- s'en sert pas. Elle DERIVE ce qu'il y a a rendre du catalogue lui-meme —
-- `pg_auth_members` — qui est la seule source qui survive a la phase 1.
drop table if exists _esc_emprunt;


-- ---------------------------------------------------------------------
-- LES QUATRE TABLES DE PREUVE QUITTENT LE MIGRATEUR (6.3b6c)
-- ---------------------------------------------------------------------
-- CONTRE-EXEMPLE MESURE (db/test/authority_closure.sh, scenario B). Apres la
-- phase 2, sur une base ACTIVE ou le migrateur avait ZERO capacite sur les
-- roles d'autorite:
--
--     alter table normative_rule_confirmations disable trigger user;
--     -- 0/3 declencheurs actifs
--     update normative_rule_confirmations set evidence_digest = repeat('0',64);
--     -- d750927cef58 -> 000000000000
--     delete from normative_rule_confirmations where ...;
--     -- ligne supprimee, audit normatif inchange
--
-- La revocation des emprunts n'achete RIEN contre le PROPRIETAIRE: c'est un
-- pouvoir attache a la propriete, pas a une appartenance. Avec les
-- declencheurs desactives, la conservation decennale ne tient plus, et rien
-- n'en garde trace.
--
-- DEUX GESTES, DANS CET ORDRE, ET L'ORDRE EST LE SUJET.
--
--   1. `FORCE ROW LEVEL SECURITY` pendant qu'on est encore proprietaire. Sans
--      elle, le proprietaire — quel qu'il soit — contourne les policies.
--   2. `OWNER TO eurostruct_normative_writer`, qui est un role d'autorite:
--      NOLOGIN, sans membre, et que la phase 2 reprend au migrateur. Apres
--      elle, plus personne ne peut desactiver ces declencheurs.
--
-- POURQUOI LE WRITER ET NON L'ACTIVATEUR. Le transfert doit etre fait PAR le
-- migrateur — PostgreSQL exige que le proprietaire courant soit membre du
-- nouveau proprietaire — et le migrateur n'est jamais membre de l'activateur:
-- c'est precisement l'invariant que la phase 0 etablit. Le writer, lui, est
-- emprunte le temps de la phase 1 et rendu par la phase 2.
--
-- CONSEQUENCE ASSUMEE: une migration ULTERIEURE qui modifierait ces tables
-- devra emprunter le writer, comme celle-ci le fait. C'est le prix de ne plus
-- laisser au migrateur un pouvoir qu'il ne rend jamais.
--
-- Le writer conserve la lecture par ses policies `*_writer_read`, dont les
-- fonctions de controle SECURITY DEFINER qu'il possede ont besoin.
alter table normative_authorisation_grants          force row level security;
alter table normative_authorisation_revocations     force row level security;
alter table normative_rule_confirmations            force row level security;
alter table normative_rule_confirmation_revocations force row level security;

alter table normative_authorisation_grants          owner to eurostruct_normative_writer;
alter table normative_authorisation_revocations     owner to eurostruct_normative_writer;
alter table normative_rule_confirmations            owner to eurostruct_normative_writer;
alter table normative_rule_confirmation_revocations owner to eurostruct_normative_writer;

-- LA VUE SUIT SES TABLES, et ce n'est pas une coquetterie de coherence.
--
-- `normative_rule_confirmation_status` est en `security_invoker = false`: la
-- lecture des tables sous-jacentes est controlee au nom de SON PROPRIETAIRE,
-- ce qui est exactement ce qui dispense `authenticated` d'avoir des droits
-- dessus. Laissee au migrateur, elle perdait ses droits en meme temps que lui
-- — defaut mesure: « permission denied for table normative_rule_confirmations »
-- depuis la vue, alors que l'appelant etait superutilisateur.
--
-- Rendue au writer, elle lit par les policies `*_writer_read`, et la frontiere
-- qu'elle porte reste la meme.
alter view normative_rule_confirmation_status owner to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- CREATE sur `public` retire aux roles d'autorite
-- ---------------------------------------------------------------------
-- Il n'etait necessaire QUE pour les transferts de propriete ci-dessus:
-- PostgreSQL exige que le nouveau proprietaire d'une fonction ait CREATE sur
-- son schema. Les transferts sont faits, le droit ne sert plus, il part.
--
-- Une permission accordee pour une operation ponctuelle et laissee en place
-- est une permission qu'on a cessé de justifier.
revoke create on schema public
  from eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- ---------------------------------------------------------------------
-- CONTROLE DE TOPOLOGIE, en cloture
-- ---------------------------------------------------------------------
-- La meme fonction que la readiness appellera. Une verification faite
-- uniquement au moment de la migration ne dit rien de l'etat six mois plus
-- tard, quand quelqu'un aura accorde un role « juste pour debloquer ».
select assert_normative_topology();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
