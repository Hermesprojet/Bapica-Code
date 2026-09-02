-- 0021 — L'ECRAN DOIT SAVOIR CE QU'IL A LE DROIT DE FAIRE
--
-- LE DEFAUT PRODUIT
-- ------------------
-- 0020 a ouvert le parcours de relecture: soumettre, renvoyer au brouillon,
-- attester, emettre. Trois de ces gestes sont reserves — attester exige le role
-- `validating_engineer`, et l'emission exige une attestation prealable — et
-- l'ecran n'a AUCUN moyen de le savoir. `project_workspace_list()` rend
-- l'organisation d'un projet et pas le role de l'appelant dedans.
--
-- LES DEUX MAUVAISES REPONSES, ET POURQUOI CE N'EN SONT PAS
-- ----------------------------------------------------------
-- 1. AFFICHER LE BOUTON A TOUT LE MONDE et laisser le serveur refuser. Un
--    dessinateur verrait « Attester le calcul », cliquerait, et recevrait un
--    refus. Ce n'est pas une interface: c'est un piege qui apprend a ignorer
--    les messages d'erreur.
-- 2. LE CACHER A TOUT LE MONDE sauf a une liste tenue dans le navigateur. Un
--    role cru depuis le client n'est pas un role: il suffit de le changer.
--
-- LA BONNE REPONSE EST QUE LE SERVEUR LE DISE. Le role est DERIVE de
-- `organization_members` sous l'identite du jeton, exactement comme la
-- primitive d'attestation le derive au moment d'agir. L'ecran s'en sert pour
-- MONTRER OU EXPLIQUER; la frontiere, elle, reste dans 0009 et 0020, et ne
-- bouge pas d'un pouce. Cacher un bouton n'a jamais protege quoi que ce soit —
-- ce que cette migration ameliore, c'est ce que l'utilisateur COMPREND.
--
-- CE QU'ELLE N'AJOUTE PAS
-- ------------------------
-- Aucune table, aucune primitive, aucun droit. Deux colonnes rendues par une
-- fonction qui existait deja, et qui lisait deja cette ligne d'adhesion pour
-- decider de la visibilite du projet.

begin;

grant create on schema public to eurostruct_normative_writer;

-- LA SIGNATURE NE CHANGE PAS, MAIS LE TYPE DE RETOUR SI. PostgreSQL refuse
-- « cannot change return type of existing function » sur un `create or
-- replace` qui ajoute une colonne a une table de retour: il faut supprimer
-- d'abord. Le `drop` repart de `acldefault` — proprietaire remis au migrateur,
-- PUBLIC retrouvant EXECUTE — et la section 2 repose les deux.
drop function if exists project_workspace_list();

create or replace function project_workspace_list()
returns table (
  project_id      uuid,
  org_id          uuid,
  org_name        text,
  name            text,
  reference       text,
  country         country_code,
  region          text,
  ndp_as_of       date,
  created_at      timestamptz,
  calculation_count bigint,
  -- LE ROLE DE L'APPELANT DANS L'ORGANISATION DE CE PROJET-LA.
  --
  -- PAR PROJET, PAS PAR SESSION: un ingenieur peut etre validateur dans un
  -- bureau et simple lecteur dans un autre. Une reponse globale serait fausse
  -- dans l'un des deux cas, et c'est celui-la qu'on n'aurait pas teste.
  member_role     org_role,
  -- ET SON NOM TEL QUE L'ORGANISATION L'ENREGISTRE. C'est celui qui figurera
  -- sur l'attestation; l'afficher AVANT permet de constater qu'il manque
  -- plutot que de le decouvrir au moment de signer.
  member_name     text,
  -- L'ADHESION EST-ELLE ACTIVE. Une adhesion revoquee laisse le projet
  -- visible — la trace des signatures passees doit rester lisible — et ferme
  -- toute action.
  member_active   boolean)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  return query
    select p.id, p.org_id, o.name, p.name, p.reference, p.country, p.region,
           p.ndp_as_of, p.created_at,
           (select count(*) from calculations c where c.project_id = p.id),
           m.role, m.display_name, m.is_active
      from projects p
      join organizations o on o.id = p.org_id
      -- `join` PLUTOT QUE `exists`, ET C'EST LE CHANGEMENT DE FOND. La
      -- version precedente ne faisait que tester l'existence de l'adhesion;
      -- il faut maintenant la LIRE. Le predicat de visibilite est identique —
      -- une adhesion, un projet — parce que `organization_members` porte une
      -- contrainte d'unicite sur (org_id, user_id): aucune ligne ne peut etre
      -- dupliquee par cette jointure.
      join organization_members m
        on m.org_id = p.org_id and m.user_id = acteur
     where p.archived_at is null
     order by p.created_at desc, p.id;
end;
$$;


-- ---------------------------------------------------------------------
-- 2. PROPRIETE ET ACCES DE LA FONCTION REMPLACEE
-- ---------------------------------------------------------------------
alter function project_workspace_list() owner to eurostruct_normative_writer;
revoke all on function project_workspace_list() from public;
grant execute on function project_workspace_list()
  to eurostruct_authority_backend;


-- ---------------------------------------------------------------------
-- 3. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
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
        'ATELIER_0021_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
        'public n''est pas dans l''ensemble admissible {%}.',
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
        'ATELIER_0021_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%).', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;
end;
$$;

do $$
begin
  if exists (
    select 1 from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public' and a.privilege_type = 'CREATE'
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid)
  then
    raise exception
      'ATELIER_0021_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public a la fin de 0021.';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 4. POSTCONDITIONS
-- ---------------------------------------------------------------------
do $$
begin
  perform assert_authority_composition();
end;
$$;

do $$
declare
  n int;
  colonnes int;
begin
  select count(*) into n from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'project_workspace_list';
  if n <> 1 then
    raise exception
      'ATELIER_0021_SIGNATURES_MULTIPLES: project_workspace_list existe en % '
      'exemplaire(s). Deux homonymes laisseraient PostgreSQL choisir, et '
      'l''ecran atteindrait celle qui ne rend pas le role.', n;
  end if;

  -- LA FONCTION REND-ELLE REELLEMENT LES TROIS COLONNES ATTENDUES?
  --
  -- Compter les arguments de sortie plutot que se fier au `create` qui vient
  -- de passer: un `drop` qui aurait echoue en silence laisserait l'ancienne
  -- definition en place, et l'ecran recevrait des projets sans role — donc
  -- n'afficherait jamais le panneau de validation, sans qu'aucune erreur ne
  -- soit levee nulle part.
  -- `CROSS JOIN LATERAL`, ET PAS UNE VIRGULE. Melanger un element de FROM
  -- separe par une virgule et un `join` explicite change la portee: le `join`
  -- se lie au dernier element, et `p` cesse d'etre visible dans son `on`.
  -- Mesure du jour: « invalid reference to FROM-clause entry for table "p" ».
  select count(*) into colonnes
    from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
    cross join lateral unnest(p.proargmodes, p.proargnames) as a(mode, nom)
   where ns.nspname = 'public' and p.proname = 'project_workspace_list'
     and a.mode = 't'
     and a.nom in ('member_role', 'member_name', 'member_active');
  if colonnes <> 3 then
    raise exception
      'ATELIER_0021_COLONNES_MANQUANTES: project_workspace_list rend % des '
      'trois colonnes d''adhesion. L''ecran ne saurait pas expliquer '
      'pourquoi la validation est fermee.', colonnes;
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
