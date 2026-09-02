-- 0026 — LE RAPPROCHEMENT LIT, ET LE DROIT LE DIT
--
-- CE QUE CETTE MIGRATION FERME
-- ------------------------------
-- `api/src/eurostruct_api/reconciliation.py` confronte les lignes de
-- `deliverables` aux objets du magasin. Il pose `set transaction read only`,
-- et PostgreSQL refuse alors toute ecriture pour la duree de la transaction.
-- C'est reel — mais c'est le PROGRAMME qui le demande.
--
-- La difference compte: ce reglage protege contre un defaut de ce fichier-la,
-- pas contre un autre programme qui se connecterait avec le meme compte, ni
-- contre une version future du meme fichier ou la ligne aurait disparu. Un
-- droit, lui, ne se demande pas: il est absent, et rien ne peut le rendre
-- present depuis la session.
--
-- `eurostruct_reconciliation` est cree NOLOGIN par le plan de controle. Cette
-- migration lui donne EXACTEMENT ce que le rapprochement lit, et rien de plus.
--
-- CE QU'IL VOIT, ET C'EST TRANSVERSAL — IL FAUT LE DIRE
-- ------------------------------------------------------
-- Le rapprochement traverse TOUTES les organisations: c'est sa raison d'etre,
-- puisqu'il compare l'ensemble du magasin a l'ensemble des lignes. Le porteur
-- de ce role voit donc, pour chaque livrable de chaque bureau d'etudes:
--
--   * l'identifiant du livrable, de son organisation et de son projet;
--   * le magasin, le CHEMIN de stockage, l'empreinte SHA-256 et la taille.
--
-- Il ne voit NI le nom du fichier, NI le genre du document, NI l'identite du
-- validateur, NI l'attestation, NI aucun resultat de calcul. Le chemin derive
-- de l'empreinte (`docs/STOCKAGE.md` §4) et ne porte aucun nom choisi par un
-- humain; il revele l'existence d'un livrable, pas son contenu.
--
-- C'est neanmoins une vue transverse, et l'acces a ce compte doit etre traite
-- comme tel: il appartient a l'exploitation, jamais a l'application.
--
-- CE QU'IL NE PEUT PAS
-- ---------------------
-- Ecrire quoi que ce soit, appeler la moindre primitive metier, administrer,
-- valider, lire une autre table. Les tests negatifs de
-- `db/test/reconciliation_role.sh` le mesurent sur `insert`, `update`,
-- `delete`, `truncate` et sur l'appel des fonctions d'autorite.

begin;

-- LE ROLE DOIT EXISTER, ET CETTE MIGRATION NE LE CREE PAS.
--
-- Meme frontiere qu'en 0013 pour `eurostruct_authority_backend`: creer un
-- role ici donnerait au migrateur le pouvoir d'en creer, et ce pouvoir est
-- precisement ce que la separation des plans lui refuse.
do $$
begin
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_reconciliation') then
    raise exception
      'le role « eurostruct_reconciliation » est absent. Il est cree par la '
      'PHASE 0 (control_plane/0001_normative_seal.sql). Le creer ici '
      'donnerait au migrateur le droit de creer des roles.';
  end if;
end
$$;

-- IL DOIT ETRE NOLOGIN ET SANS AUCUN ATTRIBUT. Un role de lecture porteur de
-- `bypassrls` verrait a travers les politiques; porteur de `createrole`, il
-- se donnerait ce qu'on lui refuse ici.
do $$
declare
  r record;
begin
  select rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb,
         rolreplication
    into r
    from pg_roles where rolname = 'eurostruct_reconciliation';

  if r.rolcanlogin or r.rolsuper or r.rolbypassrls or r.rolcreaterole
     or r.rolcreatedb or r.rolreplication then
    raise exception
      'RECONCILIATION_0026_ROLE_TROP_PUISSANT: eurostruct_reconciliation '
      'porte un attribut (login=%, super=%, bypassrls=%, createrole=%, '
      'createdb=%, replication=%). On s''y rattache, on ne s''y connecte '
      'pas, et il ne voit rien a travers les politiques.',
      r.rolcanlogin, r.rolsuper, r.rolbypassrls, r.rolcreaterole,
      r.rolcreatedb, r.rolreplication;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 1. EXACTEMENT LES SIX COLONNES QUE LE RAPPROCHEMENT LIT
-- ---------------------------------------------------------------------
-- `grant select (colonnes)` ET NON `grant select` SUR LA TABLE. Le second
-- donnerait aussi le nom du fichier, le genre, l'attestation et l'identite du
-- validateur — c'est-a-dire, pour toutes les organisations, qui a signe quoi.
-- Le rapprochement n'en a aucun besoin: il compare des chemins et des
-- empreintes.
grant usage on schema public to eurostruct_reconciliation;
grant select (id, org_id, project_id, storage_backend, storage_path,
              sha256, size_bytes)
  on deliverables to eurostruct_reconciliation;

-- LES POLITIQUES NE LE LAISSERAIENT RIEN VOIR, ET C'EST LE PROBLEME INVERSE.
--
-- `deliverables` est en RLS forcee et ses politiques visent des acteurs
-- applicatifs. Un role d'exploitation qui n'est membre d'aucune organisation
-- lirait ZERO ligne — un rapprochement qui ne voit rien conclut « tout est
-- orphelin », ce qui serait faux et dangereux.
--
-- On lui ouvre donc UNE politique de LECTURE SEULE, nommee, qui ne rend vrai
-- que pour ce role-la. Elle ne porte aucune clause `with check`: il n'y a
-- aucune ecriture a autoriser.
drop policy if exists deliverables_reconciliation_read on deliverables;
create policy deliverables_reconciliation_read on deliverables
  for select to eurostruct_reconciliation
  using (true);


-- ---------------------------------------------------------------------
-- 2. CE QUI LUI EST EXPLICITEMENT REFUSE
-- ---------------------------------------------------------------------
-- LES REVOCATIONS SONT ECRITES, PAS SUPPOSEES. PostgreSQL n'accorde rien par
-- defaut a un role nouveau — sauf `EXECUTE` a `PUBLIC` sur les fonctions, dont
-- ce role herite comme tout le monde. Les primitives metier ont deja vu leur
-- droit `PUBLIC` revoque (0023, 0025); ce bloc constate qu'aucune ne lui est
-- ouverte, plutot que d'en faire l'hypothese.
--
-- LE CONTROLE PORTE SUR LES OCTROIS **DIRECTS**, PAS SUR LE PRIVILEGE EFFECTIF.
--
-- `has_function_privilege` rend vrai des qu'un droit existe, y compris herite
-- de PUBLIC. Or « PUBLIC ne doit pas executer les primitives » est un fait
-- que le PLAN DE CONTROLE possede deja, avec son propre point de mise a mort
-- nomme. Le reprendre ici a fait fumer les deux detecteurs pour un seul
-- incendie: la mutation W1 — « les metadonnees du sceau redeviennent
-- publiques » — a bascule de `killed_runtime` a `killed_install_assertion`,
-- et le harnais de terminaison sur signal, qui a besoin que W1 vive jusqu'au
-- runtime, est tombe. Mesure: W1 tue en runtime a c9688b8, tue a
-- l'installation apres l'ajout de ce bloc.
--
-- CHAQUE CONTROLE POSSEDE UN FAIT, ET UN SEUL. Celui-ci possede « la
-- migration 0026 n'a rien octroye a ce role au-dela des colonnes »; le sceau
-- possede « PUBLIC n'execute pas les primitives ». `aclexplode` ne montre que
-- les octrois nommes: PUBLIC y apparait avec un `grantee` nul, qu'on ecarte.
do $$
declare
  ouvertes text;
begin
  select string_agg(p.proname, ', ' order by p.proname) into ouvertes
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
   where n.nspname = 'public'
     and p.proname like any (array['project\_%', 'organization\_%',
                                   'normative\_%'])
     and a.privilege_type = 'EXECUTE'
     and a.grantee <> 0
     and pg_get_userbyid(a.grantee) = 'eurostruct_reconciliation';

  if ouvertes is not null then
    raise exception
      'RECONCILIATION_0026_PRIMITIVES_OCTROYEES: cette migration a octroye '
      'l''execution de % au role de rapprochement. Un outil de constat qui '
      'peut appeler une primitive metier n''est plus un outil de constat.',
      ouvertes;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- 3. CE QUE CETTE MIGRATION DOIT AVOIR OBTENU
-- ---------------------------------------------------------------------
-- TOUS LES CONTROLES CI-DESSOUS PORTENT SUR LES OCTROIS **DIRECTS**, jamais
-- sur le privilege effectif. Meme raison qu'en section 2: `has_*_privilege`
-- rend vrai des qu'un droit existe, y compris herite de PUBLIC — et « PUBLIC
-- n'a rien » est un fait que d'autres controles possedent deja, avec leurs
-- propres points de mise a mort nommes.
--
-- CE QUE CETTE MIGRATION POSSEDE: « elle n'a rien octroye a ce role au-dela
-- des sept colonnes ». Ce que le role peut REELLEMENT faire, une fois tous
-- les plans empiles, est mesure contre un serveur vivant par
-- `db/test/reconciliation_role.sh` — preuve plus forte qu'une postcondition,
-- et qui n'appartient pas ici.
do $$
declare
  lues     text;
  ecritures text;
  tables   text;
begin
  -- LES COLONNES OCTROYEES SONT EXACTEMENT CELLES QU'ON A VOULUES.
  select string_agg(distinct a.attname, ',' order by a.attname) into lues
    from pg_attribute a
    cross join lateral aclexplode(a.attacl) acl
   where a.attrelid = 'public.deliverables'::regclass
     and a.attnum > 0 and not a.attisdropped
     and acl.privilege_type = 'SELECT'
     and acl.grantee <> 0
     and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation';

  if lues is distinct from
     'id,org_id,project_id,sha256,size_bytes,storage_backend,storage_path' then
    raise exception
      'RECONCILIATION_0026_COLONNES: cette migration a octroye « % ». Elle '
      'doit octroyer les six colonnes du rapprochement et l''identifiant, ni '
      'plus ni moins.', coalesce(lues, '(aucune)');
  end if;

  -- AUCUNE ECRITURE OCTROYEE, NULLE PART.
  select string_agg(format('%s:%s', c.relname, acl.privilege_type), ', '
                    order by c.relname, acl.privilege_type)
    into ecritures
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    cross join lateral aclexplode(c.relacl) acl
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and acl.privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
     and acl.grantee <> 0
     and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation';

  if ecritures is not null then
    raise exception
      'RECONCILIATION_0026_ECRITURE_OCTROYEE: cette migration a octroye: %. '
      'Le rapprochement ne modifie rien, et le droit doit le dire.', ecritures;
  end if;

  -- AUCUNE AUTRE TABLE, ET AUCUN DROIT DE TABLE ENTIERE SUR CELLE-CI.
  --
  -- Un `grant select` sur la table donnerait aussi le nom du fichier,
  -- l'attestation et l'identite du validateur: c'est precisement ce que
  -- l'octroi par colonnes evite, et il faut le constater.
  select string_agg(distinct c.relname, ', ' order by c.relname) into tables
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    cross join lateral aclexplode(c.relacl) acl
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and acl.grantee <> 0
     and pg_get_userbyid(acl.grantee) = 'eurostruct_reconciliation';

  if tables is not null then
    raise exception
      'RECONCILIATION_0026_SURFACE_TROP_LARGE: cette migration a octroye un '
      'droit de TABLE ENTIERE sur %. Le rapprochement lit des colonnes '
      'nommees, pas des tables.', tables;
  end if;
end
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
