-- =====================================================================
-- EUROSTRUCT — 6.3b3: la racine de confiance ne peut pas s'auto-proclamer
--
-- POURQUOI CE FICHIER EXISTE A PART.
--
-- Ce controle n'a de sens que sur une base VIERGE, ou aucun amorcage n'a
-- encore eu lieu. Joue apres 05, il passerait pour la mauvaise raison:
-- l'index partiel `normative_bootstrap_is_singular` refuserait la ligne
-- parce qu'une racine existe deja, et non parce que l'insertion brute est
-- interdite. Un test vert qui ne teste pas ce qu'il annonce est pire qu'un
-- test absent.
--
-- CONTRE-EXEMPLE VERIFIE ROUGE contre 6.3b2: sur une base vierge, avec
-- `SET ROLE authenticated` et AUCUN claim JWT, `auth.uid()` vaut NULL. La
-- branche « bootstrap » du declencheur etait alors empruntee telle quelle, et
-- une insertion directe portant `origin = 'bootstrap'` fabriquait la racine
-- de confiance. Le premier venu se declarait administrateur normatif de
-- toutes les juridictions.
--
-- MODELE DE MENACE. Vise les ROLES APPLICATIFS. Un superutilisateur peut
-- desactiver les declencheurs et n'est pas contenu par la base; c'est une
-- limite du support, pas un oubli.
--
-- Ce fichier ne cree AUCUNE donnee: chacune de ses insertions doit echouer, et
-- il le verifie a la fin.
-- =====================================================================

\set ON_ERROR_STOP on

-- Precondition: la base est reellement vierge. Sans elle, tout ce qui suit
-- pourrait reussir a cote du sujet.
do $$
declare n bigint;
begin
  select count(*) into n from normative_authorisation_grants;
  if n <> 0 then
    raise exception
      'base non vierge (% octroi(s)): ce controle exigerait alors la mauvaise '
      'preuve — l''index d''unicite au lieu de l''interdiction d''insertion', n;
  end if;
end
$$;

-- Les beneficiaires fictifs doivent EXISTER.
--
-- Sans eux, `grantee_id` viole la cle etrangere vers `auth.users` — et cette
-- violation arrive APRES la RLS mais AVANT le declencheur. Les controles 2 et
-- 3 ci-dessous passeraient donc tant que la RLS tient, et masqueraient
-- silencieusement la disparition de la garde du declencheur: verifie par
-- mutation, la garde retiree, la cle etrangere prenait le relais et le test
-- restait vert sur le mauvais motif.
insert into auth.users (id, email) values
  ('44444444-4444-4444-4444-444444444444', 'FICTIF-vierge-1@eurostruct.test'),
  ('55555555-5555-5555-5555-555555555555', 'FICTIF-vierge-2@eurostruct.test');


-- ---------------------------------------------------------------------
-- 1. Porteur de jeton, sans claim JWT: aucune insertion brute
-- ---------------------------------------------------------------------
do $$
declare ok boolean := false; sqlstate_vu text;
begin
  -- AUCUN `request.jwt.claim.sub`: c'est exactement la situation du
  -- contre-exemple. `auth.uid()` vaut NULL.
  perform set_config('request.jwt.claim.sub', '', true);

  -- Constate AVANT le changement de role: sur une base vierge, `authenticated`
  -- n'a pas meme USAGE sur le schema `auth` — c'est `01_guarantees.sql`, le
  -- harnais, qui le lui accorde, et il n'a pas tourne ici. La valeur de
  -- `auth.uid()` ne depend de toute facon pas du role: elle lit le GUC.
  if auth.uid() is not null then
    raise exception
      'auth.uid() n''est pas NULL sans claim: le contre-exemple vise n''est '
      'pas reproduit, et le test ne prouverait rien';
  end if;

  set local role authenticated;
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, origin, reason)
    values ('44444444-4444-4444-4444-444444444444',
            'FICTIF Racine Auto-Proclamee',
            'can_manage_normative_authorisations', 'bootstrap',
            'FICTIF — insertion brute empruntant la branche d''amorcage.');
  exception when others then
    ok := true; sqlstate_vu := sqlstate;
  end;

  if not ok then
    raise exception
      'une insertion brute en origin=bootstrap a fabrique la racine de '
      'confiance: le premier venu devient administrateur normatif de toutes '
      'les juridictions';
  end if;
  -- Le refus doit venir du PRIVILEGE, pas d'une contrainte de forme: si un
  -- jour l'INSERT etait rouvert, on veut que ce test le voie.
  if sqlstate_vu <> '42501' then
    raise exception
      'refus obtenu avec SQLSTATE % au lieu de 42501 (insufficient_privilege): '
      'la frontiere d''ecriture ne tient pas par l''ACL mais par accident',
      sqlstate_vu;
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 2. Meme sans claim, la branche bootstrap n'est pas ouverte au backend
-- ---------------------------------------------------------------------
-- Le role de service, lui, DETIENT l'INSERT. C'est donc sur lui que la
-- seconde ligne de defense se demontre: policy `with check (origin =
-- 'delegated')` d'un cote, declencheur de l'autre.
do $$
declare ok boolean := false;
begin
  set local role normative_backend;
  perform set_config('request.jwt.claim.sub', '', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, origin, reason)
    values ('44444444-4444-4444-4444-444444444444',
            'FICTIF Racine Par Le Service',
            'can_manage_normative_authorisations', 'bootstrap',
            'FICTIF — le service emprunte la branche d''amorcage.');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'le role de service a pu inserer un octroi d''origine « bootstrap »: '
      'la racine de confiance se fabriquerait sans passer par la fonction '
      'd''amorcage';
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 3. Avec un claim JWT, la branche bootstrap est refusee explicitement
-- ---------------------------------------------------------------------
-- L'autre moitie du contre-exemple: `auth.uid() IS NOT NULL` doit etre refuse
-- par le declencheur lui-meme, et pas seulement par l'ACL.
do $$
declare ok boolean := false;
begin
  set local role normative_backend;
  perform set_config('request.jwt.claim.sub',
                     '44444444-4444-4444-4444-444444444444', true);
  begin
    insert into normative_authorisation_grants
      (grantee_id, grantee_name, permission, origin, reason)
    values ('55555555-5555-5555-5555-555555555555', 'FICTIF Racine Signee',
            'can_manage_normative_authorisations', 'bootstrap',
            'FICTIF — amorcage depuis une session authentifiee.');
  exception when insufficient_privilege then ok := true;
  end;
  if not ok then
    raise exception
      'origin=bootstrap accepte depuis une session authentifiee';
  end if;
end
$$;
reset role;


-- ---------------------------------------------------------------------
-- 4. La fonction d'amorcage n'est executable par aucun role applicatif
-- ---------------------------------------------------------------------
do $$
declare r text;
begin
  foreach r in array array['authenticated', 'normative_backend',
                           'normative_governance', 'public'] loop
    if has_function_privilege(
         r, 'bootstrap_normative_administrator(uuid, text, text)', 'EXECUTE')
    then
      raise exception
        '% peut executer bootstrap_normative_administrator(): la racine de '
        'confiance serait ouverte depuis l''application', r;
    end if;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 5. L'ACL REELLE de la migration, hors de toute influence du harnais
-- ---------------------------------------------------------------------
-- Le controle qu'aucun autre fichier ne peut faire. `01_guarantees.sql`
-- accorde `select, insert, update, delete on all tables in schema public to
-- authenticated` pour les suites plus anciennes; `05` doit donc REVOQUER puis
-- retablir a la main ce que la migration installe, et cette liste ecrite a la
-- main peut deriver de la migration sans que rien ne le dise. Elle avait
-- d'ailleurs derive: elle rendait `insert` a `authenticated` longtemps apres
-- que la migration eut ferme l'ecriture.
--
-- Ici, aucun fichier de test n'a accorde quoi que ce soit. Ce qu'on lit est
-- exactement ce qu'un deploiement installe.
do $$
declare t text; r text;
begin
  foreach t in array array['normative_authorisation_grants',
                           'normative_authorisation_revocations',
                           'normative_rule_confirmations',
                           'normative_rule_confirmation_revocations'] loop
    -- Lecture: oui. Ecriture: non. Ni UPDATE, ni DELETE, ni TRUNCATE, pour
    -- personne d'applicatif.
    if not has_table_privilege('authenticated', t, 'SELECT') then
      raise exception
        'authenticated n''a pas SELECT sur %: le titulaire ne pourrait pas '
        'savoir ce qu''il a le droit de faire', t;
    end if;
    if has_table_privilege('authenticated', t, 'INSERT') then
      raise exception
        'authenticated detient INSERT sur % dans la migration elle-meme: '
        'l''ecriture brute contourne la validation du paquet cote moteur', t;
    end if;
    foreach r in array array['authenticated', 'normative_backend',
                             'normative_governance', 'public'] loop
      if has_table_privilege(r, t, 'UPDATE')
         or has_table_privilege(r, t, 'DELETE')
         or has_table_privilege(r, t, 'TRUNCATE') then
        raise exception '% detient UPDATE, DELETE ou TRUNCATE sur %', r, t;
      end if;
    end loop;
  end loop;

  -- La table d'activation, telle que la MIGRATION l'installe (6.3b6a):
  -- AUCUNE lecture brute pour les roles applicatifs, aucune ecriture pour
  -- personne. Constate ici, hors harnais.
  --
  -- 6.3b6a #6. La version precedente accordait `select` sur la TABLE a
  -- `authenticated`, et ce fichier le verifiait — il gravait donc le defaut.
  -- La ligne ne porte pas que l'etat: elle porte QUI a active, QUAND, et le
  -- digest de topologie constate au deploiement.
  foreach r in array array['authenticated', 'normative_backend', 'public'] loop
    if has_table_privilege(r, 'normative_activation', 'SELECT') then
      raise exception
        '% lit directement normative_activation: l''audit de deploiement '
        '(activated_by, activated_at, topology_digest) franchit la frontiere '
        'alors que seul l''etat devait la franchir', r;
    end if;
  end loop;
  -- La gouvernance, elle, lit la ligne entiere: c'est son objet.
  if not has_table_privilege('normative_governance', 'normative_activation',
                             'SELECT') then
    raise exception
      'normative_governance ne peut pas lire normative_activation: l''audit '
      'du deploiement ne serait consultable par personne';
  end if;

  foreach r in array array['authenticated', 'normative_backend',
                           'normative_governance', 'public'] loop
    if has_table_privilege(r, 'normative_activation', 'INSERT')
       or has_table_privilege(r, 'normative_activation', 'UPDATE')
       or has_table_privilege(r, 'normative_activation', 'DELETE') then
      raise exception
        '% peut ecrire dans normative_activation: le sous-systeme '
        's''activerait sans verification de topologie', r;
    end if;
  end loop;

  -- Ce qui EST expose: l'etat seul, par la vue minimale et par la fonction.
  -- Sans ce controle, la fermeture ci-dessus serait satisfaite par un
  -- sous-systeme devenu muet, et un client ne pourrait plus savoir qu'il lit
  -- des resultats pre-activation.
  if not has_table_privilege('authenticated', 'normative_activation_status',
                             'SELECT') then
    raise exception
      'authenticated ne peut pas lire l''etat d''activation: un client '
      'afficherait des resultats pre-activation sans le savoir';
  end if;
  if not has_function_privilege('authenticated', 'normative_activation_state()',
                                'EXECUTE') then
    raise exception
      'authenticated ne peut pas appeler normative_activation_state()';
  end if;
  -- Et la vue n'expose QUE l'etat: une colonne, nommee `state`. Un ajout de
  -- colonne rouvrirait silencieusement ce qu'on vient de fermer.
  if (select count(*) from information_schema.columns
       where table_schema = 'public'
         and table_name = 'normative_activation_status') <> 1
     or not exists (select 1 from information_schema.columns
                     where table_schema = 'public'
                       and table_name = 'normative_activation_status'
                       and column_name = 'state') then
    raise exception
      'normative_activation_status n''expose plus exactement la colonne '
      '« state »: la vue minimale a cesse d''etre minimale';
  end if;
  -- LA FRONTIERE EST PORTEE PAR LA FONCTION, PAS PAR LA VUE (6.3b6b).
  --
  -- Ce controle exigeait `security_invoker = false`, c'est-a-dire une lecture
  -- au nom du PROPRIETAIRE DE LA VUE. Depuis que `normative_activation` est en
  -- FORCE ROW LEVEL SECURITY et appartient a l'activateur, ce proprietaire est
  -- le role qui a exerce la migration — un role dont le nom n'est pas connu a
  -- l'ecriture et qui n'a plus aucun droit sur la table apres la phase 2. La
  -- vue est donc MINCE et invoker; c'est `normative_activation_state()`,
  -- SECURITY DEFINER possedee par l'activateur, qui franchit la frontiere, et
  -- elle ne rend que deux valeurs possibles.
  --
  -- Les deux moities sont exigees ensemble: une vue invoker SANS fonction
  -- definer derriere ne serait lisible par personne.
  if (select coalesce(
                (select option_value from pg_options_to_table(c.reloptions)
                  where option_name = 'security_invoker'), 'false')
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
       where n.nspname = 'public'
         and c.relname = 'normative_activation_status') not in ('true', 'on',
                                                                '1') then
    raise exception
      'normative_activation_status n''est pas en security_invoker: la lecture '
      'se ferait au nom du proprietaire de la VUE — le role de migration —, '
      'alors que la frontiere doit etre portee par normative_activation_state()';
  end if;
  if not exists (select 1 from pg_proc p
                   join pg_namespace n on n.oid = p.pronamespace
                   join pg_roles o on o.oid = p.proowner
                  where n.nspname = 'public'
                    and p.proname = 'normative_activation_state'
                    and p.prosecdef
                    and o.rolname = 'eurostruct_normative_activator') then
    raise exception
      'normative_activation_state() n''est pas SECURITY DEFINER possedee par '
      'eurostruct_normative_activator: rien ne franchit alors la RLS forcee, '
      'et la vue minimale ne serait lisible par personne';
  end if;

  -- LA NON-VACUITE: un chemin d'ecriture LEGITIME doit exister, sans quoi les
  -- refus ci-dessus seraient satisfaits par une base morte.
  --
  -- CE CHEMIN A CHANGE DE NOM EN 6.3c. C'etait `normative_backend`; depuis
  -- 0013 c'est `eurostruct_authority_backend`, et `normative_backend` n'a
  -- justement plus INSERT — c'est la frontiere que le jalon pose. Continuer a
  -- exiger l'ancien reviendrait a exiger que la frontiere ne soit pas posee.
  --
  -- ON EXIGE DONC LES DEUX MOITIES, et c'est plus fort qu'avant:
  --   * le backend d'autorite ecrit — le chemin nominal existe;
  --   * `normative_backend` n'ecrit PLUS — la frontiere tient.
  foreach t in array array['normative_authorisation_grants',
                           'normative_authorisation_revocations',
                           'normative_rule_confirmations',
                           'normative_rule_confirmation_revocations'] loop
    if not has_table_privilege('eurostruct_authority_backend', t, 'INSERT') then
      raise exception
        'eurostruct_authority_backend n''a pas INSERT sur %: aucune ecriture '
        'ne serait possible par aucun chemin, et les refus ci-dessus seraient '
        'satisfaits par une base morte', t;
    end if;
    if has_table_privilege('normative_backend', t, 'INSERT') then
      raise exception
        'normative_backend detient encore INSERT sur %: la frontiere posee '
        'par 0013 n''a pas pris, et un role applicatif ordinaire ecrirait '
        'toujours dans les tables d''autorite', t;
    end if;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 6. Rien n'a ete cree
-- ---------------------------------------------------------------------
-- La verification qui donne son sens aux quatre precedentes: aucun refus
-- n'a laisse de ligne derriere lui, et la base est encore vierge pour la
-- suite.
do $$
declare t text; n bigint;
begin
  foreach t in array array['normative_authorisation_grants',
                           'normative_authorisation_revocations',
                           'normative_rule_confirmations',
                           'normative_rule_confirmation_revocations'] loop
    execute format('select count(*) from %I', t) into n;
    if n <> 0 then
      raise exception
        'la table % porte % ligne(s) apres des insertions toutes refusees', t, n;
    end if;
  end loop;
end
$$;

\echo ''
\echo '================================================='
\echo ' Base vierge: la racine de confiance ne peut pas'
\echo ' s''auto-proclamer, verifie.'
\echo '================================================='
