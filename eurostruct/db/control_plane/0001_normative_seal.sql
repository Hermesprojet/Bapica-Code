-- =====================================================================
-- EUROSTRUCT — LE SCEAU NORMATIF (phase 0) — esc-normative-seal/1
-- =====================================================================
-- CE FICHIER EST APPLIQUE PAR LE PLAN DE CONTROLE, PAS PAR LE MIGRATEUR.
-- C'est toute sa raison d'etre.
--
-- IL N'EST PAS DANS `db/migrations/`, ET C'EST STRUCTUREL (6.3b6d)
-- ----------------------------------------------------------------
-- Il s'appelait `db/migrations/0000_sceau_normatif.sql`. Tout outil de
-- migration du commerce, tout script de deploiement, toute boucle
-- `for f in migrations/*.sql` l'appliquait donc SOUS LE MIGRATEUR — c'est-a-dire
-- posait la racine de confiance a la portee de celui qu'elle doit contenir.
--
-- Ce qui l'en empechait etait une ligne de bash, repetee dans chaque appelant:
--
--     [[ "$(basename "$f")" == 0000_* ]] && continue
--
-- Cinq appelants la portaient. `role_prerequisites.sh` l'avait deja oubliee, et
-- appliquait le repertoire entier sous un acteur unique. Une frontiere de
-- confiance qui depend de la vigilance de chaque appelant n'est pas une
-- frontiere: c'est une convention.
--
-- `db/migrations/` ne contient donc plus que ce que le MIGRATEUR applique.
-- Ce fichier vit dans `db/control_plane/`, et rien n'a plus a l'ignorer.
--
-- POURQUOI IL EXISTE (6.3b6c)
-- ----------------------------
-- La phase 1 exige que le migrateur puisse ENDOSSER les roles d'autorite:
-- PostgreSQL n'accepte « ALTER FUNCTION ... OWNER TO r » que si le
-- proprietaire courant peut faire « SET ROLE r ». C'est une contrainte du
-- moteur, pas un choix.
--
-- Tant que la racine de confiance appartenait a un role emprunte par le
-- migrateur, elle etait donc a sa portee. CONTRE-EXEMPLE MESURE sur fc13990,
-- pendant PENDING, par un migrateur non superutilisateur:
--
--     set role eurostruct_normative_activator;   -- accorde par la phase 1
--     insert into normative_activation (activated_by, topology_digest)
--     values (session_user, repeat('0', 64));
--     -> normative_activation_state() = ACTIVE
--
-- Le sous-systeme passait ACTIF sans finalisation, sans manifeste, sans
-- restitution — et acceptait ensuite une ecriture normative, parce que les
-- declencheurs de la phase 1 ne regardent que l'ETAT, et que l'etat venait
-- d'etre fabrique. `assert_normative_topology()` refusait ensuite: trop tard.
--
-- DEUX CORRECTIFS ONT ETE ESSAYES ET NE TIENNENT PAS
-- ---------------------------------------------------
--   * un declencheur exigeant `current_user = eurostruct_normative_activator`:
--     apres `SET ROLE`, la condition est EXACTEMENT satisfaite;
--   * un declencheur exigeant `session_user = <le plan de controle>`:
--     `SET ROLE` ne change pas `session_user` — mais l'attaquant est devenu
--     PROPRIETAIRE de la table, et un proprietaire retire le declencheur.
--
-- La racine ne peut donc pas etre une CONDITION verifiee a l'ecriture. Elle
-- doit etre une PROPRIETE: des objets que le migrateur ne possede pas et dont
-- il ne peut pas devenir membre du proprietaire.
--
-- CE QUE CE FICHIER POSE
-- -----------------------
-- Le plan de controle cree ici, et possede par `eurostruct_normative_activator`
-- qu'il ne pretera JAMAIS au migrateur:
--
--   * les quatre tables de confiance — plan de controle, activation,
--     parametres approuves, intention de finalisation;
--   * les fonctions qui les lisent et les ecrivent;
--   * `assert_normative_topology()`, que la phase 1 et la readiness appellent;
--   * `normative_finalize_deployment()`, entree ORCHESTRATRICE de la phase 2 —
--     et non son entree UNIQUE: `normative_prepare_activation()` et
--     `normative_record_activation()` restent executables par
--     `eurostruct_deployment`, parce qu'une transaction ne peut pas etre a la
--     fois l'activateur et le donneur (mesure PostgreSQL 16, voir
--     docs/schema/MODELE_DE_MENACE_NORMATIF.md). Elles portent exactement les
--     memes contraintes, et le chemin compose n'atteint aucun etat que
--     l'orchestrateur n'atteigne — verifie par db/test/seal_contract.sh, K2.
--
-- La phase 1 (0010) n'emprunte plus que `eurostruct_normative_writer` et
-- `eurostruct_normative_bootstrap`, et refuse de s'appliquer si ce sceau
-- n'est pas la.
--
-- PREREQUIS DE DEPLOIEMENT
-- -------------------------
-- Le plan de controle doit avoir CREATE sur la base et sur le schema `public`:
-- il cree ici des tables et des fonctions. Voir docs/DEPLOIEMENT_PREREQUIS.md.
--
-- MODELE DE MENACE: voir docs/schema/MODELE_DE_MENACE_NORMATIF.md. En resume,
-- le migrateur est fiable pour appliquer un schema et pour rien d'autre; le
-- superutilisateur est hors modele.
-- =====================================================================

begin;

-- =====================================================================
-- LA GARDE DE REEXECUTION (6.3b6d)
-- =====================================================================
-- CE QUE FAISAIT CE FICHIER RELANCE A L'IDENTIQUE, avant ce bloc:
--
--     ERROR: relation "normative_control_plane" already exists
--
-- Une erreur brute de PostgreSQL, ligne 241 — donc APRES que les blocs
-- precedents ont deja agi: roles crees ou constates, activateur emprunte,
-- CREATE accorde sur `public`. La transaction les annule, mais l'exploitant
-- n'apprend rien: ce message ne dit ni que le sceau est deja pose, ni qu'il
-- l'est dans la bonne version, ni qu'il est complet.
--
-- LA REEXECUTION EST UN FAIT D'EXPLOITATION, pas une hypothese d'ecole: un
-- deploiement interrompu, un pipeline rejoue, un operateur qui doute. Elle doit
-- avoir une semantique DECIDEE, la meme a chaque fois.
--
-- QUATRE ISSUES, ET AUCUNE AUTRE:
--
--   * rien n'est pose            -> installation, ce fichier s'applique;
--   * le sceau est la, MEME VERSION  -> SEAL_ALREADY_INSTALLED, aucune mutation;
--   * le sceau est la, AUTRE VERSION -> SEAL_VERSION_MISMATCH;
--   * le sceau est INCOMPLET         -> SEAL_PARTIAL, fail-closed.
--
-- POURQUOI UN REFUS ET NON UN SUCCES IDEMPOTENT. Les deux etaient acceptables.
-- Un fichier qui, selon l'etat de la base, INSTALLE UNE RACINE DE CONFIANCE ou
-- NE FAIT RIEN — en sortant 0 dans les deux cas — est precisement le genre
-- d'outil qui laisse une erreur passer inapercue. Le refus est nomme, porte un
-- SQLSTATE dedie, et n'a mute rien du tout: il est verifiable.
--
-- LE CODE EST LISIBLE PAR LA MACHINE. `ES001`/`ES002`/`ES003` permettent a un
-- orchestrateur de brancher sur le SQLSTATE, jamais sur le texte du message —
-- un texte se reformule, un code non.
--
-- POURQUOI LE COMPTE ET NON `IF NOT EXISTS`. « Aucun IF NOT EXISTS ne doit
-- accepter silencieusement un objet divergent »: `create table if not exists`
-- passerait sur une table qui porte le bon NOM et une tout autre structure.
-- Ici on compte les cinq objets de la racine, et TOUT ce qui n'est ni 0 ni 5
-- est un refus.
do $$
declare
  attendue constant text := 'esc-normative-seal/1';
  objets   constant text[] := array['normative_control_plane',
                                    'normative_activation',
                                    'normative_approved_settings',
                                    'normative_finalization_intent',
                                    'normative_seal_metadata'];
  presents int;
  version_posee text;
  manquants text;
begin
  select count(*) into presents
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind = 'r' and c.relname = any (objets);

  if presents = 0 then
    return;                                     -- installation neuve
  end if;

  if presents <> array_length(objets, 1) then
    select string_agg(o, ', ' order by o) into manquants
      from unnest(objets) o
     where not exists (select 1 from pg_class c
                         join pg_namespace n on n.oid = c.relnamespace
                        where n.nspname = 'public' and c.relname = o);
    raise exception
      'SEAL_PARTIAL: le sceau normatif est INCOMPLET — % objet(s) sur %, il '
      'manque: %. Une racine a moitie posee ne se repare pas en relancant ce '
      'fichier: on ne saurait plus quelle version elle porte, ni qui l''a '
      'posee. Detruisez la base et redeployez-la depuis la phase 0, ou '
      'restaurez-la avant l''interruption.',
      presents, array_length(objets, 1), manquants
      using errcode = 'ES003';
  end if;

  -- LES CINQ SONT LA. La version est lisible: `normative_seal_metadata` est
  -- scellee en ECRITURE, pas en lecture — c'est une declaration d'audit sur le
  -- deploiement, faite pour etre lue par la readiness et par cette garde.
  select seal_version into version_posee
    from normative_seal_metadata order by installed_at desc, seal_version desc
   limit 1;

  if version_posee is distinct from attendue then
    raise exception
      'SEAL_VERSION_MISMATCH: cette base porte le sceau « % » et ce fichier '
      'pose « % ». Un sceau ne se remplace pas en le reappliquant: seule une '
      'MISE A NIVEAU, appliquee par le poseur enregistre, peut le faire '
      'evoluer. Voir docs/DEPLOIEMENT_PREREQUIS.md, section « Faire evoluer le '
      'sceau ».', coalesce(version_posee, 'INCONNU'), attendue
      using errcode = 'ES002';
  end if;

  raise exception
    'SEAL_ALREADY_INSTALLED: le sceau « % » est deja pose sur cette base, et '
    'rien n''a ete modifie. Ce n''est pas une erreur de deploiement: c''est le '
    'resultat normal d''une phase 0 rejouee. Passez a la phase 1.', attendue
    using errcode = 'ES001';
end
$$;


-- ---------------------------------------------------------------------
-- LES SIX ROLES CANONIQUES, CREES PAR LE PLAN DE CONTROLE
-- ---------------------------------------------------------------------
-- Ils peuvent PREEXISTER — provisionnes a la main, ou par une execution
-- anterieure. Ce qui compte n'est pas qui les a crees mais qui detient
-- l'ADMIN residuel, et le controle de topologie s'en charge.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'normative_backend') then
    create role normative_backend;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'normative_governance') then
    create role normative_governance;
  end if;
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_normative_writer') then
    create role eurostruct_normative_writer nologin;
  end if;
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_normative_bootstrap') then
    create role eurostruct_normative_bootstrap nologin;
  end if;
  -- 6.3b6b. TROISIEME ROLE D'AUTORITE: l'ACTIVATEUR.
  --
  -- Il POSSEDE les deux tables de confiance — plan de controle et activation —
  -- et il est le seul a pouvoir y ecrire, depuis une fonction SECURITY
  -- DEFINER. Sans lui, ces tables appartenaient au MIGRATEUR: contre-exemple
  -- mesure, le proprietaire s'inserait lui-meme comme plan de controle et
  -- activait le sous-systeme avec un digest fabrique, sans aucune
  -- verification. `FORCE ROW LEVEL SECURITY` ne suffit pas seul: le
  -- proprietaire peut toujours le retirer.
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_normative_activator') then
    create role eurostruct_normative_activator nologin;
  end if;
  -- ROLE DE DEPLOIEMENT, 6.3b5. Identifiable et distinct des roles
  -- d'autorite: c'est LUI qui recoit EXECUTE sur l'amorcage, et le
  -- deploiement s'y rattache explicitement. Voir le bloc d'ACL plus bas.
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_deployment') then
    create role eurostruct_deployment nologin;
  end if;
  -- SEPTIEME ROLE, 6.3c: LE BACKEND D'AUTORITE.
  --
  -- IL EST CREE ICI ET NON PAR LA MIGRATION, ET C'EST UN CORRECTIF, PAS UN
  -- RANGEMENT. La migration 0013 le creait; or `CREATE ROLE` par un role
  -- CREATEROLE donne au createur l'ADMIN OPTION sur le role cree. Le
  -- MIGRATEUR se retrouvait donc capable d'enroler qui il voulait dans le
  -- role qui detient INSERT sur les tables d'autorite — y compris lui-meme.
  --
  -- Mesure sur une base deployee: les membres reels de
  -- `eurostruct_authority_backend` etaient « le migrateur », alors que la
  -- declaration nommait le login de service. Un GRANT emis par le migrateur
  -- vers un login ordinaire aboutissait, et conferait `INSERT` sur
  -- `normative_authorisation_grants`.
  --
  -- C'est exactement la contenance que 6.3b6c avait fermee, rouverte par la
  -- porte d'a cote. Le plan de controle le cree, donc lui seul en detient
  -- l'ADMIN.
  if not exists (select 1 from pg_roles
                  where rolname = 'eurostruct_authority_backend') then
    create role eurostruct_authority_backend nologin;
  end if;
end
$$;


-- ---------------------------------------------------------------------
-- L'EMPRUNT DE L'ACTIVATEUR — pris ici, rendu ici
-- ---------------------------------------------------------------------
-- Le plan de controle doit pouvoir faire « ALTER ... OWNER TO
-- eurostruct_normative_activator », ce qui exige qu'il puisse endosser ce
-- role. Or PostgreSQL 16 ne lui donne, en le creant, qu'un ADMIN residuel
-- SANS l'option SET (fait F1, mesure: admin=t, inherit=f, set=f).
--
-- Il se l'accorde donc — il en a l'ADMIN OPTION — et le REND a la fin de ce
-- fichier. Le rendre est possible parce qu'il est LUI-MEME le donneur de cet
-- octroi (fait F3): un role ne peut pas revoquer une appartenance qu'un autre
-- lui a donnee (fait F2), mais il revoque toujours la sienne.
--
-- CE QUI RESTE APRES: l'ADMIN residuel, et lui seul. C'est exactement
-- l'exemption que `assert_normative_topology()` tolere pour le plan de
-- controle fige — jamais SET, jamais USAGE.
do $$
begin
  if not pg_has_role(current_user, 'eurostruct_normative_activator', 'SET') then
    execute format('grant eurostruct_normative_activator to %I with set true, inherit true',
                   current_user);
  end if;
end
$$;

-- CREATE sur `public` est necessaire au nouveau proprietaire d'une fonction.
-- Il est retire a la fin, comme le fait deja la phase 1 pour les deux autres
-- roles d'autorite: un droit accorde pour une operation ponctuelle et laisse
-- en place est un droit qu'on a cesse de justifier.
grant usage, create on schema public to eurostruct_normative_activator;


-- =====================================================================
-- L'IDENTITE DU SCEAU (6.3b6d) — version, poseur, niveau d'assurance
-- =====================================================================
-- CE QUE LA PHASE 1 VERIFIAIT AVANT: quatre noms de tables, un proprietaire et
-- FORCE RLS. Cela ne dit pas QUELLE racine est en place. Une phase 0 d'une
-- version anterieure — ou quatre tables fabriquees portant les bons noms —
-- passait le controle a l'identique.
--
-- TROIS FAITS SONT INSCRITS ICI, ET AUCUN N'EST DERIVABLE AUTREMENT:
--
--   * LA VERSION. Sans elle, aucune evolution de ces 2000 lignes ne peut etre
--     distinguee d'une autre, et la phase 1 ne peut pas exiger de compatibilite.
--   * LE POSEUR, par OID ET par nom. C'est lui, et lui seul, qui pourra
--     finaliser (voir la finalisation) et faire evoluer le sceau: il detient
--     l'ADMIN residuel sur l'activateur, donc la seule capacite de le
--     re-emprunter. Sans cette inscription, le plan de controle se transferait
--     par un simple GRANT — contre-exemple mesure, cf. db/test/seal_contract.sh.
--   * LE NIVEAU D'ASSURANCE. Une phase 0 superutilisateur emettait un NOTICE,
--     qui disparaissait avec la console. Deux bases identiques par ailleurs
--     etaient indiscernables le lendemain.
--
-- APPEND-ONLY, UNE LIGNE PAR GENERATION DE SCEAU — et non un singleton fige.
-- C'est ce qui rend une MISE A NIVEAU possible sans jamais reecrire l'histoire:
-- la version 1 reste inscrite, la version 2 s'ajoute, et le sceau courant est
-- la derniere ligne. Un singleton immuable aurait rendu toute evolution de ces
-- 2000 lignes impossible autrement qu'a la main, hors versionnement.
--
-- SCELLEE EN ECRITURE, PAS EN LECTURE. Le contenu n'est pas un secret: une
-- version, un nom de role, un horodatage, un niveau d'assurance. Ce qui doit
-- etre impossible, c'est de l'ECRIRE — et c'est ce que la RLS forcee, le
-- declencheur et l'absence de politique d'ecriture pour quiconque garantissent.
-- La readiness, l'audit et la garde de reexecution doivent pouvoir la LIRE.
create table normative_seal_metadata (
  seal_version    text        primary key,
  installer_oid   oid         not null,
  installer_name  text        not null,
  installed_at    timestamptz not null default now(),
  assurance_level text        not null
    check (assurance_level in ('CONTAINED_NON_SUPERUSER',
                               'UNCONTAINED_SUPERUSER'))
);

-- LA LIGNE EST ECRITE AVANT LE DECLENCHEUR ET AVANT LE TRANSFERT DE PROPRIETE.
-- C'est l'ordre le plus simple qui soit sur: tant que la table appartient au
-- poseur, il y ecrit; des la ligne suivante, plus personne ne le peut.
--
-- L'IDENTITE INSCRITE EST `current_user`, ET NON `session_user`. C'est
-- `current_user` qui s'emprunte l'activateur quelques lignes plus haut, qui
-- conservera l'ADMIN residuel, et que la finalisation derivera comme donneur
-- des emprunts. Inscrire l'identite de connexion designerait un role qui, apres
-- un `SET ROLE`, n'est pas celui qui detient quoi que ce soit.
--
-- LE NIVEAU D'ASSURANCE REGARDE LES DEUX. Un superutilisateur qui fait
-- `set role plan_de_controle` presente un `current_user` non privilegie — et
-- peut faire `reset role` a la ligne suivante. Le sceau ne le contient donc
-- pas davantage, et le dire autrement serait faux.
insert into normative_seal_metadata
  (seal_version, installer_oid, installer_name, assurance_level)
select 'esc-normative-seal/1',
       c.oid, c.rolname,
       case when c.rolsuper or s.rolsuper then 'UNCONTAINED_SUPERUSER'
            else 'CONTAINED_NON_SUPERUSER' end
  from pg_roles c, pg_roles s
 where c.rolname = current_user and s.rolname = session_user;

-- IMMUABLE ET APPEND-ONLY. Une generation inscrite ne se reecrit pas: c'est
-- l'audit de ce qui a ete pose, et il ne sert a rien s'il peut etre corrige
-- apres coup.
create or replace function forbid_seal_metadata_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'normative_seal_metadata est append-only: une generation de sceau inscrite '
    'ne peut etre ni modifiee ni supprimee. Corriger l''audit de ce qui a ete '
    'pose reviendrait a ne rien auditer.'
    using errcode = 'restrict_violation';
end;
$$;
create trigger normative_seal_metadata_is_append_only
  before update or delete or truncate on normative_seal_metadata
  for each statement execute function forbid_seal_metadata_mutation();

alter table normative_seal_metadata owner to eurostruct_normative_activator;
revoke all on normative_seal_metadata from public;
grant select, insert on normative_seal_metadata to eurostruct_normative_activator;
alter table normative_seal_metadata enable row level security;
alter table normative_seal_metadata force row level security;

-- LA LECTURE EST NOMMEE, L'ECRITURE N'EST OUVERTE A PERSONNE.
--
-- ELLE A D'ABORD ETE ACCORDEE A `PUBLIC` (6.3b6d), au motif que la garde de
-- reexecution s'execute sous un poseur dont le nom n'est pas connu a l'avance.
-- C'etait une facilite, et elle avait un cout: dans un schema `public` expose
-- par PostgREST — la forme Supabase —, un utilisateur ANONYME lisait le nom du
-- role d'installation, son OID, l'horodatage et le niveau d'assurance. Ces
-- informations ne sont pas secretes pour la gouvernance; elles n'ont aucune
-- raison d'etre servies a `anon`.
--
-- TROIS LECTEURS NOMMES, ET AUCUN AUTRE:
--
--   * `eurostruct_deployment` — la readiness et l'orchestrateur;
--   * `normative_governance`  — l'audit, comme pour les autres tables de
--     confiance;
--   * LE POSEUR LUI-MEME, accorde dynamiquement ci-dessous: c'est lui, et lui
--     seul, que la garde de reexecution fera revenir.
--
-- LA PHASE 1 NE LIT PLUS LA TABLE. Elle passe par `normative_seal_version()`,
-- devenue SECURITY DEFINER et accordee aux deux roles que le migrateur
-- EMPRUNTE — meme mecanisme que `normative_declared_setting`, et pour la meme
-- raison: le nom du migrateur n'est pas connu du sceau.
--
-- AUCUNE POLITIQUE D'ECRITURE N'EST CREEE, PAS MEME POUR L'ACTIVATEUR. La RLS
-- forcee sans politique d'insertion ferme la table a tout le monde une fois
-- l'installation faite — y compris au proprietaire, y compris a un futur
-- porteur de l'activateur. Une mise a niveau devra donc passer par une
-- politique posee explicitement par le fichier de mise a niveau lui-meme,
-- sous l'ADMIN residuel du poseur enregistre: c'est un evenement, pas un droit
-- permanent.
grant select on normative_seal_metadata to eurostruct_deployment;
grant select on normative_seal_metadata to normative_governance;
do $$
begin
  execute format('grant select on normative_seal_metadata to %I', current_user);
end
$$;
-- LA POLITIQUE RESTE OUVERTE A `public`, ET CE N'EST PAS UNE CONTRADICTION:
-- une politique RLS ne DONNE aucun droit, elle filtre ceux qui existent. Le
-- privilege de table, lui, n'est accorde qu'aux trois roles ci-dessus. Ecrire
-- la politique pour chacun d'eux obligerait a en creer une de plus a chaque
-- lecteur legitime, sans rien changer a ce qui est lisible.
create policy normative_seal_metadata_lecture on normative_seal_metadata
  for select to public using (true);

-- LA VERSION ET LE NIVEAU, LUS. Deux fonctions de confort pour la readiness et
-- l'audit, qui demandent un fait plutot qu'une table.
--
-- ELLES NE SONT PAS ACCORDEES A PUBLIC, ET LA TABLE L'EST. Ce n'est pas une
-- incoherence: `db/test/05_normative_confirmation.sql` pose une regle de
-- securite GENERALE sur les fonctions normatives — aucune n'est executable par
-- PUBLIC, pour qu'aucune ne le devienne par accident le jour ou elle passera
-- SECURITY DEFINER. La regle a d'ailleurs attrape ces deux fonctions des leur
-- ecriture, ce qui est exactement son office.
--
-- La garde de reexecution et la phase 1 n'en ont pas besoin: elles s'executent
-- sous des roles de connexion choisis par le deploiement, dont le nom n'est
-- connu de personne a l'avance, et lisent donc la TABLE directement.
--
-- NI A `normative_governance`, POUR LA MEME RAISON QUE `topology_digest` en
-- 6.3b6c: c'est un role APPLICATIF, et une seconde regle de 05 interdit qu'un
-- role applicatif detienne EXECUTE sur une fonction normative. Elle a attrape
-- ce grant a l'ecriture, comme la premiere. La gouvernance lit la TABLE, qui
-- est publique en lecture — elle n'a besoin d'aucune fonction pour cela.
create or replace function normative_seal_version() returns text
language sql stable
security definer
set search_path = public, pg_temp
as $$
  select seal_version from normative_seal_metadata
   order by installed_at desc, seal_version desc limit 1;
$$;
alter function normative_seal_version() owner to eurostruct_normative_activator;
revoke all on function normative_seal_version() from public;
grant execute on function normative_seal_version() to eurostruct_deployment;
-- LES DEUX ROLES QUE LA PHASE 1 EMPRUNTE. C'est par eux que le migrateur — dont
-- le nom n'est pas connu du sceau — lit la version pour verifier qu'il peut
-- s'appliquer. Meme mecanisme que `normative_declared_setting`.
grant execute on function normative_seal_version() to eurostruct_normative_writer;
grant execute on function normative_seal_version() to eurostruct_normative_bootstrap;
-- ET LE POSEUR, POUR LA MEME RAISON QUE LA TABLE — mais un fait de plus le
-- rend NECESSAIRE, et non seulement coherent.
--
-- FAIT MESURE (PG16): quand le poseur du sceau EST le migrateur — la forme
-- greenfield — l'octroi des emprunts a lui-meme ECHOUE:
--
--   ERROR: ADMIN option cannot be granted back to your own grantor
--
-- Il reste alors sur la seule appartenance que PostgreSQL donne au CREATEUR
-- d'un role: `grantor=postgres, admin=t, inherit=f, set=f` (fait F1). Il
-- detient donc l'ADMIN sur les deux roles d'autorite, et n'HERITE d'aucun de
-- leurs droits — `pg_has_role(migrateur, writer, 'USAGE')` rend `f`. Sans ce
-- grant, la phase 1 greenfield echouait sur
-- « permission denied for function normative_seal_version », un refus qui ne
-- protege rien: la version du sceau n'est pas un secret vis-a-vis du role qui
-- vient de le poser.
do $$
begin
  execute format('grant execute on function normative_seal_version() to %I',
                 current_user);
end
$$;

comment on function normative_seal_version is
  'Version du sceau normatif en place, ou NULL si aucun sceau. La derniere '
  'generation inscrite fait foi.';

create or replace function normative_seal_assurance() returns text
language sql stable
security definer
set search_path = public, pg_temp
as $$
  select assurance_level from normative_seal_metadata
   order by installed_at asc, seal_version asc limit 1;
$$;
alter function normative_seal_assurance() owner to eurostruct_normative_activator;
revoke all on function normative_seal_assurance() from public;
grant execute on function normative_seal_assurance() to eurostruct_deployment;

-- LE NIVEAU D'ASSURANCE EST CELUI DE LA PREMIERE GENERATION, et c'est
-- deliberement l'inverse de la version. Le niveau qualifie l'INSTALLATION: si
-- la racine a ete posee par un superutilisateur, aucune mise a niveau
-- ulterieure ne peut effacer le fait qu'elle l'a ete. Prendre la derniere
-- generation permettrait de « laver » une base en lui appliquant une mise a
-- niveau depuis un role contenu.
comment on function normative_seal_assurance is
  'Niveau d''assurance du deploiement: CONTAINED_NON_SUPERUSER quand la phase 0 '
  'a ete posee par un role non superutilisateur — la forme qui obtient les '
  'garanties du modele de menace —, UNCONTAINED_SUPERUSER sinon. Celui de la '
  'PREMIERE generation: une mise a niveau ne lave pas une installation.';


-- ---------------------------------------------------------------------
-- LA READINESS — un etat LISIBLE, et son motif (6.3b6d, point 5)
-- ---------------------------------------------------------------------
-- `assert_normative_topology()` rend void et leve. C'est ce qu'il faut pour
-- BLOQUER, et c'est inutilisable pour RENDRE COMPTE: un appelant qui veut
-- ecrire une trace n'a que « ca a explose » ou « ca n'a pas explose ».
--
-- Cette fonction rend l'etat complet en une ligne, motif compris. Ce qu'elle
-- ne fait pas: decider. `strict` est une decision du branchement, comme le dit
-- deja `engine/.../confirmation.py`. Elle fournit de quoi decider, et le
-- deploiement — `tools/deploy_eurostruct.sh` — decide.
--
-- LE NIVEAU D'ASSURANCE Y FIGURE, ET C'EST TOUT L'OBJET. Il ne vivait que dans
-- un NOTICE de la phase 0, c'est-a-dire nulle part le lendemain. Deux bases
-- identiques par ailleurs — l'une scellee par un role contenu, l'autre par un
-- superutilisateur — etaient indiscernables.
create or replace function normative_deployment_readiness()
returns table (etat text, sceau text, assurance text,
               plan_de_controle text, topologie text, motif text)
language plpgsql
stable
set search_path = public, pg_temp
as $$
declare
  a text;
begin
  etat  := normative_activation_state();
  sceau := (select seal_version from normative_seal_metadata
             order by installed_at desc, seal_version desc limit 1);
  a     := (select assurance_level from normative_seal_metadata
             order by installed_at asc, seal_version asc limit 1);
  assurance := a;
  plan_de_controle := coalesce(normative_control_plane(), 'AUCUN');

  begin
    perform assert_normative_topology();
    topologie := 'CONFORME';
  exception when others then
    topologie := 'REFUSEE';
    motif := sqlerrm;
  end;

  -- LE MOTIF DIT POURQUOI, MEME QUAND TOUT VA BIEN. Un champ vide se lit
  -- « rien a signaler » ou « on n'a pas regarde », et rien ne les distingue.
  if motif is null then
    if a = 'UNCONTAINED_SUPERUSER' then
      motif := 'la phase 0 a ete posee par un superutilisateur: le sceau est '
            || 'en place mais ne contient pas celui qui l''a pose. Deploiement '
            || 'AUTO-HEBERGE, explicitement degrade — il n''offre PAS '
            || 'l''assurance de la forme contenue.';
    elsif etat = 'ACTIVE' then
      motif := 'deploiement contenu et finalise: aucun des deux acteurs n''est '
            || 'superutilisateur, la racine est hors de portee du migrateur.';
    else
      motif := 'phase 1 appliquee, finalisation non faite: le sous-systeme '
            || 'n''engage rien tant qu''il est PENDING.';
    end if;
  end if;
  return next;
end;
$$;

comment on function normative_deployment_readiness is
  'Etat de deploiement LISIBLE: etat, version du sceau, niveau d''assurance, '
  'plan de controle fige, verdict de topologie et motif. Ne decide rien — '
  'CONTAINED_NON_SUPERUSER peut porter un mode strict, UNCONTAINED_SUPERUSER '
  'ne le peut pas et ne doit jamais etre presente comme equivalent.';

revoke all on function normative_deployment_readiness() from public;
grant execute on function normative_deployment_readiness() to eurostruct_deployment;


-- =====================================================================
-- PARAMETRES DE DEPLOIEMENT — LUS DANS LE CATALOGUE, PAS DANS LA SESSION
-- =====================================================================
-- 6.3b6a. `current_setting('eurostruct.x', true)` rend la valeur EFFECTIVE de
-- la session: n'importe quel role peut la remplacer par un simple
--
--     SET eurostruct.approved_service_logins = 'moi';
--
-- et faire ainsi passer au vert un controle de readiness qui devait le
-- refuser. Trois declarations etaient dans ce cas — approved_service_logins,
-- token_roles, approved_deployment_roles — et elles decident toutes de
-- refus de topologie.
--
-- La valeur est donc lue dans `pg_db_role_setting`, c'est-a-dire ce que le
-- DEPLOIEMENT a pose par `ALTER DATABASE ... SET`. Un `SET` de session n'y
-- figure pas et ne peut donc plus rien changer. `setrole = 0` exclut en outre
-- les reglages poses pour un role particulier, qui rouvriraient la meme porte
-- par un autre chemin.
create or replace function normative_declared_setting(p_nom text)
returns text
language sql
stable
set search_path = public, pg_temp
as $$
  select coalesce(
    (select split_part(o, '=', 2)
       from pg_db_role_setting s
       cross join unnest(s.setconfig) as o
      where s.setdatabase = (select oid from pg_database
                              where datname = current_database())
        and s.setrole = 0
        and split_part(o, '=', 1) = p_nom
      limit 1),
    '');
$$;

comment on function normative_declared_setting is
  'Valeur DECLAREE par le deploiement (ALTER DATABASE ... SET), lue dans '
  'pg_db_role_setting. N''utilise jamais current_setting(), qu''un simple '
  'SET de session suffirait a forger.';

revoke all on function normative_declared_setting(text) from public;
-- LES DEUX ROLES EMPRUNTES PAR LA PHASE 1 (6.3b6c).
--
-- La phase 1 lit les declarations — son bloc de prerequis en depend — et
-- appelle `assert_normative_topology()` en cloture. Elle s'execute sous le
-- migrateur, qui n'est pas nomme ici et ne peut donc pas etre cite. Le droit
-- est accorde aux deux roles qu'il EMPRUNTE le temps de la migration, et que
-- la phase 2 lui reprend: sa lecture s'eteint avec l'emprunt.
grant execute on function normative_declared_setting(text)
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;
-- L'ACTIVATEUR l'appelle depuis `normative_effective_setting`, qui est
-- SECURITY DEFINER et lui appartient: sans ce droit, la lecture des valeurs
-- declarees echouerait a l'interieur meme du chemin de finalisation.
grant execute on function normative_declared_setting(text)
  to eurostruct_normative_activator;
-- =====================================================================
-- PLAN DE CONTROLE — singleton immuable, derive du GRANTOR
-- =====================================================================
-- Le plan de controle est le seul role autorise a conserver l'ADMIN residuel
-- sur les roles d'autorite. Son identite ne peut donc pas venir d'un
-- parametre: elle serait declarable par celui-la meme qu'on controle.
--
-- Elle est DERIVEE d'un fait de catalogue: le GRANTOR de l'octroi temporaire
-- que le migrateur recoit pour transferer la propriete des fonctions. Ce
-- grantor est, par construction, le role qui a precree les roles d'autorite —
-- c'est-a-dire le plan de controle. Personne ne peut le reecrire: PostgreSQL
-- l'inscrit lui-meme dans `pg_auth_members`.
--
-- Il est ensuite FIGE dans ce singleton, parce que le grantor disparait avec
-- l'octroi: la finalisation revoque l'appartenance temporaire, et la trace
-- s'efface. Ce qui est fige ici est ce qui a ete constate au moment ou c'etait
-- observable.
-- L'IDENTITE EST UN OID **ET** UN NOM (6.3b6b, point 3).
--
-- CONTRE-EXEMPLE MESURE (db/test/finalisation_contract.sh): la table ne
-- stockait que `role_name`, et l'exemption d'ADMIN residuel — la SEULE du
-- modele — etait accordee par NOM. Un nom d'exploitation n'est pas un secret:
-- il se libere et se reprend. Apres retrait du role approuve et reprise de son
-- nom par un role neuf, la topologie ACCEPTAIT le substitut, qui heritait de
-- l'exemption sans avoir jamais rien approuve.
--
-- Les deux sont donc stockes, et les DEUX sont verifies:
--   * l'OID seul laisserait passer un renommage — l'exemption suivrait un role
--     qui ne porte plus le nom approuve, et l'audit deviendrait illisible;
--   * le NOM seul laisse passer la substitution, mesuree ci-dessus.
create table normative_control_plane (
  singleton boolean primary key default true
            constraint control_plane_is_singular check (singleton),
  role_oid  oid  not null,
  role_name text not null,
  -- QUI a installe, et QUAND. `session_user`: `current_user` vaut le role
  -- d'autorite dans une fonction SECURITY DEFINER et ne nomme personne.
  recorded_by text not null,
  recorded_at timestamptz not null default now(),

  constraint control_plane_names_a_role check (btrim(role_name) <> ''),
  constraint control_plane_names_an_installer check (btrim(recorded_by) <> '')
);

comment on table normative_control_plane is
  'Identite du plan de controle, DERIVEE du grantor de l''octroi temporaire '
  'et figee ici — le grantor disparait avec l''octroi. Exactement une ligne, '
  'immuable: la reecrire reviendrait a se designer soi-meme.';

-- IMMUABLE. Sans cela, le detenteur de l'ADMIN residuel n'aurait qu'a se
-- reecrire dans cette table pour devenir « le plan de controle approuve ».
create or replace function forbid_control_plane_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'le plan de controle est fige a l''installation: le reecrire reviendrait '
    'a se designer soi-meme comme approuve. Operation: %.', tg_op
    using errcode = 'restrict_violation';
end;
$$;

create trigger normative_control_plane_is_immutable
  before update or delete on normative_control_plane
  for each row execute function forbid_control_plane_mutation();

-- PROPRIETE ET FORCE ROW LEVEL SECURITY (6.3b6b).
--
-- CONTRE-EXEMPLE MESURE sur c1f02a6: la table appartenait au role qui exerce
-- la migration, RLS etait « enable » et non « force », et le proprietaire est
-- exempte des policies. Trois lignes de SQL suffisaient donc:
--
--   insert into normative_control_plane (role_name, recorded_by)
--   values ('FICTIF_je_me_designe', session_user);
--   -> ECRITURE DIRECTE ACCEPTEE: plan de controle = FICTIF_je_me_designe
--
-- Le migrateur se designait plan de controle, et s'exemptait ainsi du refus
-- d'ADMIN residuel qu'il etait censé subir.
--
-- `FORCE` seul n'aurait pas suffi: le PROPRIETAIRE peut toujours faire
-- `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` ou `DROP POLICY`. Il faut donc
-- les deux — forcer la RLS ET deplacer la propriete hors de portee.
alter table normative_control_plane owner to eurostruct_normative_activator;
-- LES DROITS DE L'ACTIVATEUR SONT ECRITS, PAS SUPPOSES.
--
-- Le proprietaire d'une table a ses droits par defaut tant que l'ACL n'est pas
-- materialisee. Elle l'est des le premier `grant`/`revoke` — et le role qui
-- l'execute est inscrit comme donneur. Mesure: sur l'une des deux tables l'ACL
-- s'est materialisee au nom du MIGRATEUR (« b1mig=arwdDxt/b1mig »), qui
-- exercait la migration en heritant de l'activateur, si bien que
-- `has_table_privilege('eurostruct_normative_activator', ..., 'SELECT')`
-- rendait FAUX — et la fonction SECURITY DEFINER echouait sur
-- « permission denied for table ». Une propriete supposee ne se voit pas
-- quand elle manque.
-- `select, insert` ET NON `all` (6.3b6b, point 6). La table est immuable par
-- declencheur; l'ACL et les policies le disent maintenant aussi. Trois moyens
-- concordants valent mieux qu'un seul, et un `grant all` sur une table
-- append-only est une contradiction que rien ne rattrape si le declencheur
-- vient a manquer.
grant select, insert on normative_control_plane to eurostruct_normative_activator;
alter table normative_control_plane enable row level security;
alter table normative_control_plane force row level security;
revoke all on normative_control_plane from public;

-- Aucune lecture applicative directe. La gouvernance lit, pour l'audit.
grant select on normative_control_plane to normative_governance;
create policy normative_control_plane_gov_read on normative_control_plane
  for select to normative_governance using (true);

-- L'ACTIVATEUR lit et ecrit — et lui seul. Il est NOLOGIN et n'a aucun
-- membre: `current_user` ne peut valoir ce nom que depuis l'interieur d'une
-- fonction SECURITY DEFINER qu'il possede. C'est le meme mecanisme d'origine
-- non forgeable que pour le writer, applique a l'ecriture de confiance.
create policy normative_control_plane_lecture on normative_control_plane
  for select to eurostruct_normative_activator using (true);
create policy normative_control_plane_ecriture on normative_control_plane
  for insert to eurostruct_normative_activator with check (true);

-- L'identite, LUE. Rend NULL si rien n'a ete fige: aucun role n'est alors
-- exempte, ce qui est le comportement fail-closed voulu.
-- SECURITY DEFINER, POSSEDEE PAR L'ACTIVATEUR (6.3b6b). Depuis que la table
-- est en `FORCE ROW LEVEL SECURITY` et appartient a l'activateur, elle n'est
-- lisible que par lui et par la gouvernance. Or cette fonction est appelee par
-- `assert_normative_topology()`, que le deploiement et la readiness exercent
-- sous d'autres roles. Elle LIT — elle n'ecrit rien — et ne rend qu'un nom.
create or replace function normative_control_plane() returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select role_name from normative_control_plane limit 1;
$$;
alter function normative_control_plane() owner to eurostruct_normative_activator;

comment on function normative_control_plane is
  'Le plan de controle fige a l''installation, ou NULL. NULL n''exempte '
  'personne: sans plan de controle constate, tout ADMIN residuel est refuse.';

revoke all on function normative_control_plane() from public;
grant execute on function normative_control_plane()
  to eurostruct_normative_activator;
grant execute on function normative_control_plane() to eurostruct_deployment;
grant execute on function normative_control_plane()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- L'AUTRE MOITIE DE L'IDENTITE. Rend NULL si rien n'a ete fige — meme
-- comportement fail-closed que le nom: sans plan de controle constate, aucun
-- role n'est exempte.
create or replace function normative_control_plane_oid() returns oid
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select role_oid from normative_control_plane limit 1;
$$;
alter function normative_control_plane_oid()
  owner to eurostruct_normative_activator;

comment on function normative_control_plane_oid is
  'L''OID du plan de controle fige a l''installation, ou NULL. Un nom se '
  'libere et se reprend; un OID non. Les deux sont verifies ensemble.';

revoke all on function normative_control_plane_oid() from public;
grant execute on function normative_control_plane_oid()
  to eurostruct_normative_activator;
grant execute on function normative_control_plane_oid() to eurostruct_deployment;
grant execute on function normative_control_plane_oid()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- =====================================================================
-- ETAT D'ACTIVATION DU SOUS-SYSTEME NORMATIF (6.3b6a)
-- =====================================================================
-- Le deploiement se fait en DEUX PHASES: installation, puis finalisation.
-- Entre les deux, le sous-systeme existe mais n'engage RIEN — aucune
-- confirmation normative, aucun mode strict, aucun etat « strict-ready ».
--
-- ABSENCE DE LIGNE = PENDING. C'est la propriete la plus importante de cette
-- table, et la raison de sa forme: un etat qui devrait etre POSE pour bloquer
-- se trahit au premier oubli — table vide apres restauration, migration
-- interrompue, base clonee sans ses donnees. Ici, tout ce qui n'a pas ete
-- explicitement active est PENDING.
--
-- On ne stocke donc jamais « PENDING »: la table ne contient QUE l'activation.
create table normative_activation (
  -- Une seule ligne possible, jamais deux etats concurrents.
  singleton boolean primary key default true
            constraint activation_is_singular check (singleton),

  activated_at   timestamptz not null default now(),
  -- QUI a active. `session_user`: `current_user` vaut le role d'autorite a
  -- l'interieur d'une fonction SECURITY DEFINER et ne nomme personne.
  activated_by   text not null,
  -- La topologie constatee au moment de l'activation, pour l'audit: on doit
  -- pouvoir dire plus tard SUR QUOI l'activation a porte.
  topology_digest text not null,

  constraint activation_names_someone check (btrim(activated_by) <> '')
);

comment on table normative_activation is
  'Activation du sous-systeme normatif. L''ABSENCE de ligne vaut PENDING: '
  'aucun etat a poser pour bloquer, donc aucun oubli possible. Ne contient '
  'jamais l''etat PENDING lui-meme.';

-- LA TABLE N'EST LUE PAR AUCUN ROLE APPLICATIF (6.3b6a, correctif #6).
--
-- La version precedente accordait `select` sur `normative_activation` a
-- `authenticated`. C'etait plus que l'etat: la ligne porte QUI a active, QUAND,
-- et le digest de la topologie constatee — c'est-a-dire de l'audit de
-- deploiement, expose a tout porteur de jeton. « Savoir que le sous-systeme
-- n'est pas actif n'est pas un secret » justifiait l'etat, pas la ligne.
--
-- Ce qui est expose est donc UNE SEULE COLONNE CALCULEE, par une vue minimale.
-- La vue est `security_invoker = false` — ecrit explicitement, et non laisse au
-- defaut: la lecture de la table sous-jacente est alors controlee au nom du
-- PROPRIETAIRE de la vue, si bien que l'appelant n'a besoin d'aucun droit sur
-- la table. Rien d'autre ne franchit la frontiere.
-- MEME TRAITEMENT QUE LE PLAN DE CONTROLE, et pour la meme raison mesuree:
-- le proprietaire inserait directement
--
--   insert into normative_activation (activated_by, topology_digest)
--   values (session_user, 'FICTIF-digest-sans-verification');
--   -> ECRITURE DIRECTE ACCEPTEE: etat = ACTIVE
--
-- c'est-a-dire qu'il activait le sous-systeme normatif sans qu'aucune
-- topologie ne soit verifiee et avec un digest invente.
alter table normative_activation owner to eurostruct_normative_activator;
-- LES DROITS DE L'ACTIVATEUR SONT ECRITS, PAS SUPPOSES.
--
-- Le proprietaire d'une table a ses droits par defaut tant que l'ACL n'est pas
-- materialisee. Elle l'est des le premier `grant`/`revoke` — et le role qui
-- l'execute est inscrit comme donneur. Mesure: sur l'une des deux tables l'ACL
-- s'est materialisee au nom du MIGRATEUR (« b1mig=arwdDxt/b1mig »), qui
-- exercait la migration en heritant de l'activateur, si bien que
-- `has_table_privilege('eurostruct_normative_activator', ..., 'SELECT')`
-- rendait FAUX — et la fonction SECURITY DEFINER echouait sur
-- « permission denied for table ». Une propriete supposee ne se voit pas
-- quand elle manque.
-- APPEND-ONLY, ET PAR TROIS MOYENS (6.3b6b, point 6).
--
-- CONTRE-EXEMPLE MESURE: `normative_control_plane` et
-- `normative_approved_settings` portaient chacune un declencheur qui refuse
-- UPDATE et DELETE. `normative_activation` n'en avait aucun — alors qu'elle
-- porte le fait le plus engageant des trois: l'EXISTENCE de la ligne EST
-- l'etat ACTIVE. Detruire la ligne ramenait le sous-systeme en PENDING sans
-- aucune trace, et `normative_record_activation` — qui ne refuse que si la
-- ligne existe — acceptait alors de reactiver. L'audit de deploiement etait
-- reecriturable.
--
--   1. le DECLENCHEUR, qui s'applique meme au proprietaire;
--   2. l'ACL, reduite a `select, insert` — plus de `grant all`;
--   3. les POLICIES, separees: `for select` et `for insert`, jamais `for all`.
--      Une policy `for all` couvre UPDATE et DELETE au meme titre qu'INSERT.
grant select, insert on normative_activation to eurostruct_normative_activator;
alter table normative_activation enable row level security;
alter table normative_activation force row level security;
revoke all on normative_activation from public;
-- La gouvernance, elle, lit la ligne entiere: c'est son objet meme (audit du
-- deploiement). Aucun autre role, applicatif ou de service, ne l'atteint.
grant select on normative_activation to normative_governance;
create policy normative_activation_gov_read on normative_activation
  for select to normative_governance using (true);
create policy normative_activation_lecture on normative_activation
  for select to eurostruct_normative_activator using (true);
create policy normative_activation_ecriture on normative_activation
  for insert to eurostruct_normative_activator with check (true);

create or replace function forbid_activation_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'l''activation est append-only: la modifier ou la detruire ramenerait le '
    'sous-systeme en PENDING sans trace, et rouvrirait une seconde activation '
    'qui reecrirait l''audit de deploiement. Operation: %.', tg_op
    using errcode = 'restrict_violation';
end;
$$;

create trigger normative_activation_is_append_only
  before update or delete on normative_activation
  for each row execute function forbid_activation_mutation();


-- L'etat, LU et jamais fourni. Aucun booleen client n'entre ici. Passe par la
-- vue, et non par la table: une fonction SQL ordinaire lit au nom de son
-- APPELANT, si bien qu'un acces direct a `normative_activation` echouerait
-- pour `authenticated` — et l'y autoriser reviendrait a defaire ce qui precede.
-- SECURITY DEFINER, POSSEDEE PAR L'ACTIVATEUR, et LISANT LA TABLE.
--
-- Elle passait par la vue `normative_activation_status`; depuis que la table
-- est en FORCE RLS, c'est la fonction qui porte le franchissement, et la vue
-- qui s'appuie sur elle. Un seul mecanisme, dans un seul sens.
create or replace function normative_activation_state() returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select case when exists (select 1 from normative_activation)
              then 'ACTIVE' else 'PENDING' end;
$$;
alter function normative_activation_state() owner to eurostruct_normative_activator;

-- LA VUE EST MINCE, LA FONCTION PORTE LA FRONTIERE (6.3b6b).
--
-- `security_invoker = true`: la vue n'est plus qu'un nom. C'est
-- `normative_activation_state()` — SECURITY DEFINER, possedee par
-- l'activateur — qui franchit la RLS forcee, et elle ne rend que deux valeurs
-- possibles.
--
-- L'inverse aurait fait dependre la lecture du PROPRIETAIRE DE LA VUE, c'est-
-- a-dire du role qui a exerce la migration — un role dont le nom n'est pas
-- connu a l'ecriture et qui, depuis que la table appartient a l'activateur,
-- n'a plus aucun droit dessus.
create view normative_activation_status
  with (security_invoker = true)
  as select normative_activation_state() as state;

comment on view normative_activation_status is
  'Etat d''activation, et rien d''autre. La vue est mince et invoker; la '
  'frontiere est portee par normative_activation_state(), SECURITY DEFINER '
  'possedee par l''activateur. Aucun role applicatif n''a de droit sur la '
  'table elle-meme.';

revoke all on normative_activation_status from public;
grant select on normative_activation_status
  to authenticated, normative_backend, normative_governance;

comment on function normative_activation_state is
  'ACTIVE si et seulement si la table porte sa ligne; PENDING sinon. '
  'L''appelant ne fournit rien: l''etat est constate, jamais declare.';

revoke all on function normative_activation_state() from public;
grant execute on function normative_activation_state()
  to eurostruct_normative_activator;
grant execute on function normative_activation_state()
  to normative_backend, normative_governance, authenticated;
-- La finalisation (phase 2) lit l'etat avant d'agir, et elle est exercee par
-- un detenteur du role de deploiement. Sans ce droit, elle echoue des sa
-- premiere ligne — verifie.
grant execute on function normative_activation_state()
  to eurostruct_deployment;
grant execute on function normative_activation_state()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;


-- ---------------------------------------------------------------------
-- EN PENDING, AUCUNE ECRITURE NORMATIVE (6.3b6b, point 5)
-- ---------------------------------------------------------------------
-- CE DECLENCHEUR ETAIT DEJA INVOQUE — mais il n'existait pas.
--
-- Le bloc A de `assert_normative_topology()` n'est dur qu'en ACTIVE, et le
-- commentaire qui justifie cet assouplissement disait, en toutes lettres:
--
--   « En PENDING, AUCUNE confirmation normative n'est possible — les
--     declencheurs la refusent — donc rien n'est engage. »
--
-- CONTRE-EXEMPLE MESURE (db/test/finalisation_contract.sh): les CINQ ecritures
-- normatives — l'amorcage et les quatre tables append-only — etaient acceptees
-- en PENDING. Aucun declencheur ne les refusait. L'assouplissement du bloc A
-- reposait donc sur une propriete qui n'existait pas: pendant toute la phase 1,
-- le migrateur detient SET sur les roles d'autorite ET peut ecrire des
-- confirmations normatives — c'est-a-dire engager une juridiction avec une
-- origine forgee.
--
-- SECURITY DEFINER, POSSEDEE PAR L'ACTIVATEUR: le declencheur s'execute sous
-- le role qui ECRIT, et ce role n'a aucun droit sur `normative_activation`.
-- Sans cela le refus serait « permission denied for function
-- normative_activation_state », c'est-a-dire un refus pour le mauvais motif —
-- et un motif qui disparaitrait le jour ou le droit serait accorde.
create or replace function forbid_normative_write_while_pending() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if normative_activation_state() <> 'ACTIVE' then
    raise exception
      'ecriture normative refusee: le deploiement n''est pas finalise '
      '(etat PENDING). Tant que la phase 2 n''a pas eu lieu, le migrateur '
      'detient encore les roles d''autorite empruntes et pourrait donc forger '
      'l''origine de cette ecriture. Table: %.', tg_table_name
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;
alter function forbid_normative_write_while_pending()
  owner to eurostruct_normative_activator;

comment on function forbid_normative_write_while_pending is
  'Refuse toute ecriture normative tant que le deploiement n''est pas '
  'finalise. C''est ce declencheur que le bloc A de la topologie invoque '
  'pour n''etre dur qu''en ACTIVE: sans lui, l''assouplissement ne reposait '
  'sur rien.';

-- PUBLIC N'A PAS EXECUTE DESSUS. Une fonction SECURITY DEFINER laissee
-- executable par PUBLIC offre les droits de son proprietaire — ici
-- l''activateur, seul role autorise a ecrire dans les tables de confiance — a
-- n'importe qui. Un declencheur n'a pas besoin de ce droit pour se declencher:
-- PostgreSQL ne verifie pas EXECUTE a l'appel d'une fonction de declencheur.
--
-- Defaut mesure par `05_normative_confirmation.sql`, qui porte deja cette
-- garantie et l'a refusee des la premiere execution.
revoke all on function forbid_normative_write_while_pending() from public;
-- ET AUX DEUX ROLES EMPRUNTES: `CREATE TRIGGER` exige EXECUTE sur la fonction
-- de declenchement, et c'est la phase 1 qui pose ces quatre declencheurs sur
-- ses propres tables. Le droit n'est verifie qu'a la CREATION du declencheur:
-- une fois pose, il se declenche sans que personne ait besoin de ce droit —
-- y compris apres que la phase 2 a repris l'emprunt.
grant execute on function forbid_normative_write_while_pending()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- AUCUNE policy d'ecriture, et aucun privilege INSERT/UPDATE/DELETE accorde:
-- l'activation ne passe que par la fonction de finalisation (6.3b6b), qui
-- verifie la topologie AVANT d'ecrire. Une activation posee a la main serait
-- une activation non verifiee.


-- =====================================================================
-- CONTROLE DE TOPOLOGIE DES ROLES — reexecutable (6.3b6 #5)
-- =====================================================================
-- POURQUOI UNE FONCTION, ET NON UN BLOC DE MIGRATION.
--
-- Les invariants de topologie etaient verifies UNE FOIS, au moment de la
-- migration. Cela ne dit rien de l'etat six mois plus tard, quand quelqu'un
-- aura accorde un role « juste pour debloquer un incident ». Or ces
-- invariants sont exactement ce sur quoi repose la preuve d'origine: si un
-- role applicatif devient membre d'un role d'autorite en production, toute la
-- chaine normative devient decorative — et rien ne le signalerait.
--
-- La fonction est donc appelee par la migration en cloture, ET destinee au
-- controle de readiness / au demarrage de l'application. Le meme code, aux
-- deux moments, sans risque de divergence entre eux.
--
-- Elle ne modifie RIEN: elle constate. Une fonction de controle qui repare
-- masquerait le fait qu'il y avait quelque chose a reparer.
--
-- MODELE DE MENACE. Les superutilisateurs sont hors perimetre: ils satisfont
-- `pg_has_role` pour tout role et peuvent desactiver les declencheurs. Les
-- roles applicatifs, eux, sont contenus.
create or replace function assert_normative_topology() returns void
language plpgsql
stable
set search_path = public, pg_temp
as $$
declare
  r record;
  autorites text[] := array['eurostruct_normative_writer',
                            'eurostruct_normative_bootstrap',
                            'eurostruct_normative_activator'];
  services  text[] := array['normative_backend', 'normative_governance',
                            'eurostruct_authority_backend'];
  note text;
begin
  -- ------------------------------------------------------------------
  -- A. Roles d'AUTORITE: aucun membre, jamais, et pas de connexion.
  -- ------------------------------------------------------------------
  -- CE BLOC NE S'APPLIQUE DUREMENT QU'EN ETAT « ACTIVE » (6.3b6b).
  --
  -- En PENDING, le deploiement n'est pas termine: le migrateur DETIENT encore
  -- l'appartenance empruntee pour transferer la propriete des fonctions, et il
  -- ne peut pas la rendre lui-meme (fait F2, mesure). Exiger l'invariant final
  -- a ce moment-la revenait a exiger l'impossible, et c'est exactement ce que
  -- faisait la version precedente: la migration se refusait elle-meme.
  --
  -- Ce n'est pas un assouplissement de la garantie, c'est sa mise a sa place.
  -- En PENDING, AUCUNE confirmation normative n'est possible — les
  -- declencheurs la refusent — donc rien n'est engage. L'invariant devient dur
  -- au moment ou il protege quelque chose: a l'activation, et pour toujours
  -- ensuite.
  if normative_activation_state() = 'ACTIVE' then
  -- LES TROIS CAPACITES, directes ET transitives (6.3b6a).
  --
  -- Une version precedente s'arretait a SET et USAGE, au motif que l'ADMIN
  -- residuel « ne permet pas d'agir ». C'etait faux: son detenteur se
  -- reaccorde SET quand il veut. Le pouvoir n'etait pas retire, il etait
  -- range a un pas de distance — et `pg_has_role` ne le montrait meme pas
  -- (MEMBER=true, USAGE=false, mesure).
  --
  -- SEUL LE PLAN DE CONTROLE peut conserver l'ADMIN residuel, et il doit
  -- etre DECLARE. PostgreSQL accorde cet ADMIN au createur du role: il existe
  -- forcement quelque part, et le nier rendrait la topologie irrealisable.
  -- Ce qu'on exige est qu'il soit chez UN SEUL role, nomme, et hors de portee
  -- des roles applicatifs.
  -- LES PRIMITIVES DE POSTGRESQL 16, et non une recursion maison.
  --
  -- Une version precedente calculait la portee par fermeture recursive sur
  -- `pg_auth_members`. C'etait reinventer ce que le moteur expose deja, avec
  -- le risque propre a toute reimplementation: diverger en silence de la
  -- semantique de reference. Verifie sur six formes de graphe — direct, deux
  -- sauts, ADMIN seul, INHERIT seul, ADMIN detenu par un intermediaire, et
  -- diamant — les trois primitives donnent le meme resultat que la recursion,
  -- et elles font autorite.
  --
  --   'SET'                       droit d'endosser (SET ROLE)
  --   'USAGE'                     heritage des droits
  --   'MEMBER WITH ADMIN OPTION'  droit de re-accorder le role
  --
  -- Les trois sont TRANSITIVES par construction.
  for r in
    select a.rolname as cible, m.rolname as porteur, m.oid as porteur_oid,
           m.rolcanlogin as connectable,
           pg_has_role(m.rolname, a.rolname, 'SET') as par_set,
           pg_has_role(m.rolname, a.rolname, 'USAGE') as par_usage,
           pg_has_role(m.rolname, a.rolname, 'MEMBER WITH ADMIN OPTION') as par_admin
      from pg_roles a
      cross join pg_roles m
     where a.rolname = any (autorites)
       and m.oid <> a.oid
       and not m.rolsuper
       and (pg_has_role(m.rolname, a.rolname, 'SET')
            or pg_has_role(m.rolname, a.rolname, 'USAGE')
            or pg_has_role(m.rolname, a.rolname, 'MEMBER WITH ADMIN OPTION'))
       -- `coalesce(..., false)` N'EST PAS DECORATIF.
       --
       -- `normative_control_plane()` rend NULL tant qu'aucun plan n'a ete fige.
       -- Sans coalesce, `m.rolname = NULL` vaut NULL, la conjonction vaut NULL,
       -- `not NULL` vaut NULL — et une clause WHERE qui vaut NULL EXCLUT la
       -- ligne. L'absence de plan de controle aurait donc exempte TOUT LE
       -- MONDE, exactement l'inverse du fail-closed annonce. Defaut mesure:
       -- sous un migrateur non superutilisateur, la migration passait au vert
       -- avec deux ADMIN residuels non declares.
       and not coalesce(
         -- Le plan de controle, et LUI SEUL, peut garder l'ADMIN residuel —
         -- mais jamais SET ni USAGE. Son identite ne vient PAS d'un parametre
         -- de session: voir `normative_control_plane()`.
         --
         -- PAR OID **ET** PAR NOM (6.3b6b, point 3). Le nom seul ne suffit
         -- pas: contre-exemple mesure, apres retrait du role approuve et
         -- reprise de son nom par un role neuf, l'exemption suivait le NOM et
         -- le substitut en heritait sans avoir jamais rien approuve.
         m.oid = normative_control_plane_oid()
         and m.rolname = normative_control_plane()
         and pg_has_role(m.rolname, a.rolname, 'MEMBER WITH ADMIN OPTION')
         and not pg_has_role(m.rolname, a.rolname, 'SET')
         and not pg_has_role(m.rolname, a.rolname, 'USAGE'),
         false)
  loop
    -- LE DIAGNOSTIC DOIT NOMMER LA SUBSTITUTION QUAND C'EN EST UNE (6.3b6b,
    -- point 3). Sans cette precision, le refus disait « seul le plan de
    -- controle fige (ici: X) peut conserver un ADMIN residuel » a propos d'un
    -- role qui S'APPELLE X — un message qui se contredit lui-meme et qui
    -- envoie chercher la panne ailleurs.
    note := '';
    if r.porteur = normative_control_plane()
       and r.porteur_oid is distinct from normative_control_plane_oid() then
      note := format(
        ' CE ROLE PORTE LE NOM DU PLAN DE CONTROLE APPROUVE SANS ETRE LUI: '
        'approuve = oid %s, present sous ce nom = oid %s. Le nom a ete repris '
        'par un autre role; l''exemption d''ADMIN residuel ne se transmet pas '
        'avec l''etiquette.',
        coalesce(normative_control_plane_oid()::text, 'AUCUN'), r.porteur_oid);
    end if;
    raise exception
      'topologie: « % » atteint « % » (set=%, usage=%, admin=%; connectable: '
      '%). Aucun role applicatif ne doit pouvoir endosser, heriter NI '
      'readministrer un role d''autorite — l''ADMIN suffit a se reaccorder '
      'le reste. Seul le plan de controle fige a l''installation (ici: %) '
      'peut conserver un ADMIN residuel.%',
      r.porteur, r.cible, r.par_set, r.par_usage, r.par_admin, r.connectable,
      coalesce(normative_control_plane(), 'AUCUN'), note
      using errcode = 'insufficient_privilege';
  end loop;

  -- EXACTEMENT UN PLAN DE CONTROLE (6.3b6a, correctif #4).
  --
  -- Le singleton garantit qu'une seule ligne est ENREGISTRABLE; il ne garantit
  -- pas qu'une seule soit EFFECTIVE. Si deux roles distincts detiennent
  -- l'ADMIN residuel et que l'un d'eux est le plan de controle, la boucle
  -- ci-dessus refuse bien l'autre — mais si le plan fige a disparu du
  -- catalogue, ou n'a jamais rien detenu, la table designe un role qui
  -- n'exerce rien et l'exemption ne correspond a aucun fait.
  -- PAR LA FONCTION, PAS PAR LA TABLE (6.3b6b).
  --
  -- `assert_normative_topology()` est SECURITY INVOKER: elle s'execute sous le
  -- role qui la demande — la finalisation, la readiness, le deploiement. Or la
  -- table est desormais en FORCE RLS et n'appartient qu'a l'activateur: une
  -- lecture directe echoue avec « permission denied for table ». Mesure: la
  -- seconde finalisation, celle qui teste l'idempotence, echouait la.
  --
  -- `normative_control_plane()` est SECURITY DEFINER et ne rend qu'un nom.
  if normative_control_plane() is not null then
    declare
      plan_nom text := normative_control_plane();
      plan_oid oid := normative_control_plane_oid();
      porte int;
    begin
      -- L'OID D'ABORD: c'est lui l'identite. Un role detruit emporte son OID,
      -- et son nom redevient libre.
      if not exists (select 1 from pg_roles where oid = plan_oid) then
        -- RESTAURATION INTER-CLUSTER — le cas le plus probable de ce refus.
        --
        -- L'identite du plan de controle porte un OID PostgreSQL. Un
        -- `pg_dump`/restore vers un AUTRE cluster ne le preserve pas: les
        -- roles y sont recrees avec de nouveaux OID, et la ligne figee designe
        -- alors un role qui n'existe plus.
        --
        -- LE REFUS EST LE COMPORTEMENT ATTENDU, et il est fail-closed: une
        -- base restauree ailleurs n'a pas herite de l'approbation qui avait
        -- eu lieu sur le cluster d'origine.
        --
        -- LE DIAGNOSTIC NE PROMET PLUS DE REPRISE (6.3b6d, point 6). Il disait
        -- « cette base doit etre refinalisee sur place par son propre plan de
        -- controle ». CETTE OPERATION N'EXISTE PAS, et ne peut pas exister
        -- sans rouvrir ce que la racine ferme:
        --
        --   * `normative_control_plane` est un singleton IMMUABLE;
        --   * `normative_activation` est APPEND-ONLY;
        --   * `normative_record_activation()` refuse des que l'etat est ACTIVE;
        --   * aucun role ne peut endosser l'activateur apres la phase 0.
        --
        -- Mesure sur une restauration reelle entre deux clusters
        -- (db/test/cross_cluster_restore.sh): la consigne executee rend
        -- MANIFEST_MISMATCH, et vider la table d'activation est refuse meme au
        -- PROPRIETAIRE de la base restauree. Un refus fail-closed qui envoie
        -- l'exploitant executer une procedure inexistante ne protege pas mieux
        -- qu'un refus muet: il fait perdre du temps et suggere une issue.
        --
        -- LA RESTAURATION INTER-CLUSTER N'EST DONC PAS PRISE EN CHARGE. La
        -- base restauree reste fail-closed, definitivement. Le chemin supporte
        -- vers un autre cluster est un DEPLOIEMENT NEUF — phases 0, 1 et 2 —
        -- suivi d'une reprise des donnees metier; il ne transporte pas
        -- l'approbation, parce qu'une approbation vaut pour le cluster ou elle
        -- a eu lieu.
        --
        -- L'OID N'EST DELIBEREMENT PAS REINSCRIPTIBLE. Le rendre modifiable
        -- « pour reparer une restauration » rouvrirait exactement la
        -- substitution que 6.3b6b a fermee: il suffirait de dire que le bon
        -- OID est celui qu'on veut. Voir
        -- docs/schema/MODELE_DE_MENACE_NORMATIF.md.
        raise exception
          'topologie: le plan de controle approuve (oid %, « % ») n''existe '
          'plus dans le catalogue. Si un role porte encore ce nom, ce n''est '
          'pas celui qui a ete approuve: l''exemption d''ADMIN residuel ne '
          'peut pas lui etre transmise avec l''etiquette. '
          'CAS COURANT: RESTAURATION INTER-CLUSTER — les OID ne survivent pas '
          'a un pg_dump/restore vers un autre cluster. Cette restauration '
          'N''EST PAS PRISE EN CHARGE: la base reste fail-closed, et il '
          'n''existe aucune procedure pour la reprendre en l''etat. Deployez '
          'une base NEUVE sur ce cluster (phases 0, 1, 2) et reprenez-y les '
          'donnees metier. L''OID fige n''est pas reinscriptible, et ne doit '
          'pas l''etre.',
          plan_oid, plan_nom using errcode = 'insufficient_privilege';
      end if;
      -- PUIS LE NOM, AU MEME OID. Un renommage laisserait l'audit designer un
      -- role introuvable sous son nom fige, et libererait ce nom pour un
      -- autre — c'est exactement la substitution mesuree en 6.3b6b.
      if not exists (select 1 from pg_roles
                      where oid = plan_oid and rolname = plan_nom) then
        raise exception
          'topologie: le plan de controle approuve (oid %) portait le nom '
          '« % » et porte maintenant « % ». L''identite approuvee et '
          'l''etiquette approuvee ne designent plus le meme role.',
          plan_oid, plan_nom,
          (select rolname from pg_roles where oid = plan_oid)
          using errcode = 'insufficient_privilege';
      end if;
      select count(*) into porte from pg_roles a
       where a.rolname = any (autorites)
         and pg_has_role(plan_nom, a.rolname, 'MEMBER WITH ADMIN OPTION');
      if porte = 0 then
        raise exception
          'topologie: le plan de controle fige « % » ne detient l''ADMIN sur '
          'aucun role d''autorite. Ou bien il a ete retire — et l''exemption '
          'ne protege plus rien — ou bien il n''a jamais ete le plan de '
          'controle reel.', plan_nom using errcode = 'insufficient_privilege';
      end if;
    end;
  end if;

  end if;   -- fin du bloc A, dur en ACTIVE seulement

  -- Les attributs des roles d'autorite, eux, sont exiges dans LES DEUX etats:
  -- ils ne dependent d'aucun emprunt et rien ne justifie de les relacher.
  for r in select rolname as cible from pg_roles
            where rolname = any (autorites)
              and (rolcanlogin or rolsuper or rolbypassrls
                   or rolcreaterole or rolcreatedb)
  loop
    raise exception
      'topologie: le role d''autorite « % » est connectable ou privilegie. '
      'Il doit etre NOLOGIN et sans aucun attribut.', r.cible
      using errcode = 'insufficient_privilege';
  end loop;

  -- ------------------------------------------------------------------
  -- B. Roles de SERVICE. Des membres sont legitimes — l'application les
  --    endosse — mais trois formes ne le sont pas.
  -- ------------------------------------------------------------------
  -- B1. Le service lui-meme connectable. 6.3b6 #4: un role de service est
  --     ENDOSSE, il ne se connecte pas. Connectable, il devient une porte
  --     d'entree directe sur les droits d'ecriture normatifs, sans passer par
  --     l'authentificateur ni par aucun jeton.
  for r in select rolname as cible from pg_roles
            where rolname = any (services) and rolcanlogin
  loop
    raise exception
      'topologie: le role de service « % » est CONNECTABLE. Il doit etre '
      'endosse (SET ROLE) par un authentificateur, jamais offrir une '
      'connexion directe.', r.cible
      using errcode = 'insufficient_privilege';
  end loop;

  -- B2. Le service lui-meme privilegie, ou atteint par un role privilegie.
  --     Un role qui contourne deja la RLS ne doit pas en plus heriter des
  --     droits d'ecriture normatifs. Aucune approbation ne rend cela
  --     acceptable.
  for r in select rolname as cible from pg_roles
            where rolname = any (services)
              and (rolsuper or rolbypassrls or rolcreaterole or rolcreatedb)
  loop
    raise exception
      'topologie: le role de service « % » porte un attribut privilegie.',
      r.cible using errcode = 'insufficient_privilege';
  end loop;

  for r in
    select sv.rolname as cible, p.rolname as porteur,
           p.rolbypassrls, p.rolcreaterole, p.rolcreatedb
      from pg_roles sv cross join pg_roles p
     where sv.rolname = any (services)
       and p.oid <> sv.oid
       and not p.rolsuper
       and (p.rolbypassrls or p.rolcreaterole or p.rolcreatedb)
       -- SET et USAGE sont refuses DANS LES DEUX ETATS: ce sont les capacites
       -- qui font perdre au cloisonnement toute realite.
       --
       -- L'ADMIN residuel, lui, n'est examine qu'en ACTIVE. En PENDING le plan
       -- de controle n'est pas encore fige — c'est la finalisation qui le
       -- constate — donc aucune exemption ne peut s'appliquer, et l'exiger
       -- reviendrait a refuser le provisionnement legitime que PostgreSQL
       -- impose (fait F1). Mesure: la migration se refusait a « le role
       -- privilegie b1ctl atteint le service normative_backend », alors que
       -- b1ctl est precisement celui qui a provisionne.
       and (pg_has_role(p.rolname, sv.rolname, 'SET')
            or pg_has_role(p.rolname, sv.rolname, 'USAGE')
            or (normative_activation_state() = 'ACTIVE'
                and pg_has_role(p.rolname, sv.rolname, 'MEMBER WITH ADMIN OPTION')))
       -- MEME EXEMPTION QUE POUR LES ROLES D'AUTORITE, et pour la meme raison
       -- mesuree: le plan de controle qui a PROVISIONNE les roles de service
       -- en detient un ADMIN residuel irrevocable (fait F1). Il est tolere
       -- pour LUI SEUL, et jamais avec SET ni USAGE.
       -- PAR OID **ET** PAR NOM (6.3b6c). Cette exemption ne comparait que le
       -- nom. Le controle global de coherence du plan attrape aujourd'hui une
       -- substitution — mais une exemption qui n'est sure que grace a un AUTRE
       -- controle n'est pas sure: elle le devient le jour ou l'autre bouge.
       and not coalesce(
         p.oid = normative_control_plane_oid()
         and p.rolname = normative_control_plane()
         and not pg_has_role(p.rolname, sv.rolname, 'SET')
         and not pg_has_role(p.rolname, sv.rolname, 'USAGE'),
         false)
  loop
    raise exception
      'topologie: le role privilegie « % » atteint le service « % » '
      '(bypassrls=%, createrole=%, createdb=%).',
      r.porteur, r.cible, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb
      using errcode = 'insufficient_privilege';
  end loop;

  -- B3. Atteint par un role CONNECTABLE non approuve. Legitime en
  --     deploiement (`authenticator` endosse `service_role`), donc
  --     fail-closed avec declaration explicite.
  for r in
    select sv.rolname as cible, c.rolname as porteur
      from pg_roles sv cross join pg_roles c
     where sv.rolname = any (services)
       and c.oid <> sv.oid
       and not c.rolsuper
       and c.rolcanlogin
       and (pg_has_role(c.rolname, sv.rolname, 'SET')
            or pg_has_role(c.rolname, sv.rolname, 'USAGE')
            or (normative_activation_state() = 'ACTIVE'
                and pg_has_role(c.rolname, sv.rolname, 'MEMBER WITH ADMIN OPTION')))
       -- LE PLAN DE CONTROLE FIGE, ET LUI SEUL, peut conserver l'ADMIN
       -- residuel que PostgreSQL lui a donne en creant ces roles (fait F1) —
       -- jamais SET ni USAGE. Sans cette exemption, la forme Supabase etait
       -- refusee a la finalisation meme: le provisionneur y est connectable
       -- par construction.
       -- PAR OID **ET** PAR NOM (6.3b6c), comme ci-dessus.
       and not coalesce(
         c.oid = normative_control_plane_oid()
         and c.rolname = normative_control_plane()
         and not pg_has_role(c.rolname, sv.rolname, 'SET')
         and not pg_has_role(c.rolname, sv.rolname, 'USAGE'),
         false)
       and c.rolname <> all (string_to_array(
             btrim(coalesce(normative_effective_setting('eurostruct.approved_service_logins'), '')), ','))
  loop
    raise exception
      'topologie: le role connectable « % » atteint le service « % » sans '
      'approbation. Declarer si voulu: ALTER DATABASE ... SET '
      'eurostruct.approved_service_logins = ''...''.', r.porteur, r.cible
      using errcode = 'insufficient_privilege';
  end loop;

  -- B4. Atteint par un PORTEUR DE JETON. Non derivable du catalogue: quels
  --     roles un JWT endosse est une convention de deploiement, declaree.
  for r in
    select sv.rolname as cible, j.rolname as porteur
      from pg_roles sv
      cross join unnest(string_to_array(
        coalesce(nullif(normative_effective_setting('eurostruct.token_roles'), ''),
                 'authenticated,anon'), ',')) as t(nom)
      join pg_roles j on j.rolname = btrim(t.nom)
     where sv.rolname = any (services)
       and not j.rolsuper
       and (pg_has_role(j.rolname, sv.rolname, 'SET')
            or pg_has_role(j.rolname, sv.rolname, 'USAGE')
            or (normative_activation_state() = 'ACTIVE'
                and pg_has_role(j.rolname, sv.rolname, 'MEMBER WITH ADMIN OPTION')))
  loop
    raise exception
      'topologie: le porteur de jeton « % » atteint le service « % ».',
      r.porteur, r.cible using errcode = 'insufficient_privilege';
  end loop;

  -- ------------------------------------------------------------------
  -- C. Role de DEPLOIEMENT (6.3b6 #4). Il ouvre la chaine de confiance:
  --    c'est peu, mais c'est irreversible, et il ne doit rien etre d'autre.
  -- ------------------------------------------------------------------
  for r in select rolname as cible from pg_roles
            where rolname = 'eurostruct_deployment'
              and (rolcanlogin or rolsuper or rolbypassrls
                   or rolcreaterole or rolcreatedb)
  loop
    raise exception
      'topologie: « eurostruct_deployment » est connectable ou privilegie. '
      'Il doit etre NOLOGIN et sans attribut: on s''y rattache, on ne s''y '
      'connecte pas.'
      using errcode = 'insufficient_privilege';
  end loop;

  -- Il n'est membre d'aucune autorite: ouvrir la chaine et forger une preuve
  -- restent deux pouvoirs distincts.
  for r in select a.rolname as cible from pg_roles a
            where a.rolname = any (autorites)
              and (pg_has_role('eurostruct_deployment', a.rolname, 'SET')
                   or pg_has_role('eurostruct_deployment', a.rolname, 'USAGE')
                   or (normative_activation_state() = 'ACTIVE'
                       and pg_has_role('eurostruct_deployment', a.rolname,
                                       'MEMBER WITH ADMIN OPTION')))
  loop
    raise exception
      'topologie: « eurostruct_deployment » est membre de « % ». Ouvrir la '
      'chaine de confiance et fabriquer une trace normative sont deux '
      'pouvoirs qui ne doivent pas se rejoindre.', r.cible
      using errcode = 'insufficient_privilege';
  end loop;

  -- Et ses DETENTEURS sont declares. Un role applicatif qui l'obtiendrait
  -- pourrait amorcer la chaine — une seule fois, mais en s'y designant
  -- lui-meme. Meme mecanisme que les services: fail-closed et declare.
  for r in
    select d.rolname as porteur
      from pg_roles d
     where d.oid <> (select oid from pg_roles where rolname = 'eurostruct_deployment')
       and not d.rolsuper
       and (pg_has_role(d.rolname, 'eurostruct_deployment', 'SET')
            or pg_has_role(d.rolname, 'eurostruct_deployment', 'USAGE')
            or (normative_activation_state() = 'ACTIVE'
                and pg_has_role(d.rolname, 'eurostruct_deployment', 'MEMBER WITH ADMIN OPTION')))
       and d.rolname <> all (string_to_array(
             btrim(coalesce(normative_effective_setting('eurostruct.approved_deployment_roles'), '')), ','))
  loop
    raise exception
      'topologie: « % » detient eurostruct_deployment sans approbation. '
      'Declarer le role de deploiement: ALTER DATABASE ... SET '
      'eurostruct.approved_deployment_roles = ''%%''.', r.porteur
      using errcode = 'insufficient_privilege';
  end loop;
end;
$$;

comment on function assert_normative_topology is
  'Constate les invariants de topologie des roles normatifs. Appelee par la '
  'migration en cloture ET destinee a la readiness: une verification faite '
  'une seule fois ne dit rien de l''etat six mois plus tard. Ne modifie rien.';

revoke all on function assert_normative_topology() from public;
-- Appelee par la finalisation (SECURITY INVOKER, exercee par le donneur) et
-- destinee a la readiness du deploiement.
grant execute on function assert_normative_topology()
  to eurostruct_deployment;
grant execute on function assert_normative_topology()
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;
-- ET A L'ACTIVATEUR: `normative_record_activation` est SECURITY DEFINER et lui
-- appartient; c'est donc SOUS SON NOM que la topologie est verifiee juste
-- avant l'ecriture. Sans ce droit, la finalisation echoue a l'avant-derniere
-- ligne — apres avoir revoque les emprunts. La transaction annule tout, mais
-- le deploiement se retrouve sans diagnostic utile.
grant execute on function assert_normative_topology()
  to eurostruct_normative_activator;

-- =====================================================================
-- PHASE 2 — FINALISATION, EXERCEE PAR LE DONNEUR (6.3b6b)
-- =====================================================================
-- POURQUOI UNE PHASE 2 EXISTE.
--
-- La migration emprunte l'appartenance aux roles d'autorite le temps de leur
-- transferer la propriete des fonctions et des tables de confiance —
-- PostgreSQL l'exige. Elle ne peut PAS la rendre: un role ne revoque jamais sa
-- propre appartenance quand le donneur est un autre role (fait F2, mesure dans
-- db/test/two_phase_deployment.sh). Or dans tout deploiement sain, le donneur
-- EST un autre role.
--
-- La restitution appartient donc au DONNEUR, et c'est ce que fait cette
-- fonction. Elle est SECURITY INVOKER — deliberement: c'est le donneur qui
-- doit executer les `REVOKE`, et personne d'autre ne le peut.
--
-- ATOMIQUE. Une fonction PL/pgSQL s'execute dans la transaction de l'appelant:
-- toute exception levee ici annule TOUT — revocations comprises. Il n'existe
-- pas d'etat intermediaire ou l'emprunt serait rendu sans que l'activation
-- soit inscrite, ni l'inverse.

-- ---------------------------------------------------------------------
-- LES PARAMETRES APPROUVES SONT CONSTATES PUIS FIGES
-- ---------------------------------------------------------------------
-- CONTRE-EXEMPLE: `normative_declared_setting()` lit `pg_db_role_setting`,
-- c'est-a-dire ce que `ALTER DATABASE ... SET` a pose. Cela ferme le `SET` de
-- session, mais pas le PROPRIETAIRE DE LA BASE — qui est le migrateur. Il
-- pouvait donc s'auto-approuver:
--
--   ALTER DATABASE ma_base SET eurostruct.approved_service_logins = 'moi';
--
-- et faire passer au vert un refus de topologie qui le visait.
--
-- A la finalisation, le plan de controle CONSTATE les trois declarations et
-- les FIGE ici. Ensuite, la topologie lit cette table et plus le catalogue de
-- la base: un `ALTER DATABASE` ulterieur ne change plus rien.
create table normative_approved_settings (
  nom   text primary key,
  valeur text not null,
  fige_par text not null,
  fige_le  timestamptz not null default now(),
  constraint approved_setting_nom_connu
    check (nom in ('eurostruct.approved_service_logins',
                   'eurostruct.token_roles',
                   'eurostruct.approved_deployment_roles'))
);

comment on table normative_approved_settings is
  'Les trois declarations de deploiement, CONSTATEES au moment de la '
  'finalisation puis figees. Apres activation, la topologie les lit ici et '
  'non dans pg_db_role_setting: le proprietaire de la base ne peut plus '
  's''auto-approuver par ALTER DATABASE.';

create or replace function forbid_approved_settings_mutation() returns trigger
language plpgsql as $$
begin
  raise exception
    'les parametres approuves sont figes a la finalisation: les reecrire '
    'reviendrait a s''auto-approuver apres coup. Operation: %.', tg_op
    using errcode = 'restrict_violation';
end;
$$;

create trigger normative_approved_settings_are_immutable
  before update or delete on normative_approved_settings
  for each row execute function forbid_approved_settings_mutation();

alter table normative_approved_settings owner to eurostruct_normative_activator;
-- `select, insert` ET NON `all` (6.3b6b, point 6): meme raison que pour les
-- deux autres tables de confiance.
grant select, insert on normative_approved_settings
  to eurostruct_normative_activator;
alter table normative_approved_settings enable row level security;
alter table normative_approved_settings force row level security;
revoke all on normative_approved_settings from public;
grant select on normative_approved_settings to normative_governance;
create policy normative_approved_settings_gov_read on normative_approved_settings
  for select to normative_governance using (true);
create policy normative_approved_settings_lecture on normative_approved_settings
  for select to eurostruct_normative_activator using (true);
create policy normative_approved_settings_ecriture on normative_approved_settings
  for insert to eurostruct_normative_activator with check (true);

-- La valeur EFFECTIVE: figee si elle l'est, declaree sinon.
create or replace function normative_effective_setting(p_nom text) returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select coalesce(
    (select valeur from normative_approved_settings where nom = p_nom),
    normative_declared_setting(p_nom));
$$;
alter function normative_effective_setting(text)
  owner to eurostruct_normative_activator;

comment on function normative_effective_setting is
  'La valeur figee si la finalisation l''a constatee, la valeur declaree par '
  'ALTER DATABASE sinon. Apres activation, un ALTER DATABASE ne change plus '
  'rien: le proprietaire de la base ne peut pas s''auto-approuver.';

revoke all on function normative_effective_setting(text) from public;
grant execute on function normative_effective_setting(text)
  to eurostruct_normative_activator;
grant execute on function normative_effective_setting(text)
  to eurostruct_deployment;
grant execute on function normative_effective_setting(text)
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- ---------------------------------------------------------------------
-- LE MANIFESTE — ce que le plan de controle declare avoir revu
-- ---------------------------------------------------------------------
-- CONTRE-EXEMPLE MESURE (db/test/finalisation_contract.sh, point 1): la
-- finalisation figeait la valeur COURANTE des trois `ALTER DATABASE ... SET`.
-- Le plan de controle ne presentait RIEN — il ne disait pas ce qu'il avait
-- revu — donc rien n'etait compare, et « approuve » ne signifiait que
-- « courant au moment ou la fonction a tourne ». Mesure:
--
--     revu par le plan de controle : « authenticated »
--     fige comme approuve          : « authenticated,anon,FICTIF_ajoute »
--
-- QUI PEUT CHANGER CES VALEURS — mesure, PostgreSQL 16: le proprietaire non
-- superutilisateur de la base ne le peut PAS par defaut (« permission denied
-- to set parameter »), mais le peut des qu'il detient `GRANT SET ON PARAMETER`
-- — ce qu'un installeur qui pose lui-meme ses declarations doit avoir. Et le
-- defaut ne depend de toute facon pas de QUI change: sans manifeste, aucun
-- changement survenu entre la revue et la finalisation n'etait detectable.
--
-- LE MANIFESTE EST UN DIGEST, PAS UNE COPIE. Le plan de controle le lit au
-- moment de la revue, le note, et le represente a la finalisation. S'il ne
-- correspond plus, la finalisation refuse — sans avoir rien ecrit.
create or replace function normative_settings_manifest() returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select encode(sha256(convert_to(
           string_agg(n || '=' || normative_declared_setting(n), E'\n' order by n),
           'UTF8')), 'hex')
    from unnest(array['eurostruct.approved_deployment_roles',
                      'eurostruct.approved_service_logins',
                      'eurostruct.token_roles']) as t(n);
$$;
alter function normative_settings_manifest()
  owner to eurostruct_normative_activator;

comment on function normative_settings_manifest is
  'Digest des trois declarations DECLAREES, dans un ordre canonique. Le plan '
  'de controle le lit a la revue et le represente a la finalisation: tout '
  'changement intervenu entre les deux fait refuser, avant toute ecriture.';

-- LE MANIFESTE **APPROUVE**, calcule sur ce qui a ete FIGE (6.3b6c).
--
-- `normative_settings_manifest()` digere les valeurs DECLAREES; celle-ci
-- digere les valeurs GELEES. Les deux coincident sur une base saine, et
-- divergent des qu'une declaration a change apres l'activation — ce qui est
-- precisement ce qu'on veut pouvoir constater.
--
-- Elle sert a l'idempotence: une seconde finalisation n'est acceptee que si
-- l'appelant presente le manifeste qui a ete approuve. CONTRE-EXEMPLE MESURE:
-- en etat ACTIVE, un manifeste autre, vide ou mal forme rendait
-- « ACTIVE (deja finalise) ». Un script de deploiement pointe sur la mauvaise
-- base, ou portant une configuration ancienne, recevait un succes.
--
-- L'ORDRE CANONIQUE EST LE MEME que celui du manifeste declare — tri par nom —
-- sans quoi les deux digests ne seraient pas comparables.
create or replace function normative_approved_manifest() returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select encode(sha256(convert_to(
           string_agg(nom || '=' || valeur, E'\n' order by nom), 'UTF8')), 'hex')
    from normative_approved_settings;
$$;
alter function normative_approved_manifest()
  owner to eurostruct_normative_activator;

comment on function normative_approved_manifest is
  'Digest des trois declarations FIGEES a la finalisation. Une seconde '
  'finalisation doit presenter exactement celui-ci: sinon le script vise une '
  'autre base, ou porte une configuration qui n''est pas celle qui a ete '
  'approuvee.';

revoke all on function normative_approved_manifest() from public;
grant execute on function normative_approved_manifest()
  to eurostruct_normative_activator;
grant execute on function normative_approved_manifest() to eurostruct_deployment;

revoke all on function normative_settings_manifest() from public;
grant execute on function normative_settings_manifest()
  to eurostruct_normative_activator;
-- ET RIEN DE PLUS. `normative_governance` en avait recu EXECUTE, au motif que
-- l'audit peut vouloir recalculer le manifeste. La garantie de
-- `05_normative_confirmation.sql` l'a refuse, et elle a raison: la gouvernance
-- est un role APPLICATIF, et le manifeste est l'entree du chemin de
-- finalisation. Elle lit `normative_approved_settings`, ce qui lui suffit pour
-- savoir ce qui a ete approuve.
grant execute on function normative_settings_manifest() to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- L'INTENTION DE FINALISATION — l'identite derivee pendant qu'elle est encore
-- observable
-- ---------------------------------------------------------------------
-- LE PROBLEME QUE CETTE TABLE RESOUT. La phase 2 doit inscrire QUI a migre et
-- QUI a approuve. Mais elle commence par REVOQUER les emprunts — c'est-a-dire
-- par detruire la preuve. Au moment de l'ecriture, `pg_auth_members` ne
-- contient plus rien: l'identite du migrateur n'est plus derivable.
--
-- La version precedente reglait cela en la faisant PASSER EN ARGUMENT. Mesure
-- (point 2): un detenteur d'`eurostruct_deployment` appelait directement
-- `normative_record_activation('<lui-meme>', 'normative_governance')` et le
-- sous-systeme passait ACTIVE, avec un audit nommant un migrateur qui n'avait
-- jamais migre — sans derivation du donneur, sans verification que l'appelant
-- etait le donneur, sans aucune revocation.
--
-- Ici, l'identite est DERIVEE DU CATALOGUE pendant qu'elle est encore visible,
-- puis figee. Ce qui traverse la revocation est une ligne ecrite par une
-- fonction qui n'a rien recu de l'appelant, et non un texte qu'il a choisi.
create table normative_finalization_intent (
  singleton boolean primary key default true
            constraint finalization_intent_is_singular check (singleton),
  -- PAR OID **ET** PAR NOM, des deux cotes: un OID seul laisse passer un
  -- renommage, un nom seul laisse passer une substitution.
  migrateur_oid oid  not null,
  migrateur_nom text not null,
  donneur_oid   oid  not null,
  donneur_nom   text not null,
  manifeste     text not null,
  -- LA TRANSACTION QUI A PREPARE (6.3b6c). C'est elle qui rend les helpers
  -- non composables: `normative_record_activation()` exige la MEME. Un
  -- appelant ne peut pas forger un identifiant de transaction — le serveur
  -- l'attribue —, et ce n'est ni un GUC ni un marqueur de session.
  --
  -- CONTRE-EXEMPLE MESURE (parcours B): preparer, revoquer a la main, puis
  -- appeler l'ecriture de confiance suffisait a obtenir ACTIVE en trois
  -- transactions distinctes, sans le finaliseur, sans le verrou, sans
  -- atomicite.
  prepare_txid  bigint not null default txid_current(),
  -- LES TROIS VALEURS CONSTATEES, portees jusqu'a l'ecriture. Elles sont lues
  -- UNE FOIS, digerees, et figees telles quelles: relire les declarations
  -- entre la comparaison et le gel rouvrirait la fenetre que le manifeste
  -- existe pour fermer.
  valeurs       text[] not null,
  prepare_par   text not null,
  prepare_le    timestamptz not null default now(),

  constraint finalization_intent_has_three_values
    check (array_length(valeurs, 1) = 3),

  constraint finalization_intent_names_a_migrator
    check (btrim(migrateur_nom) <> ''),
  constraint finalization_intent_names_a_donor
    check (btrim(donneur_nom) <> ''),
  constraint finalization_intent_separates_roles
    check (migrateur_oid <> donneur_oid and migrateur_nom <> donneur_nom)
);

comment on table normative_finalization_intent is
  'Identites DERIVEES du catalogue avant la revocation, et le manifeste '
  'approuve. Existe parce que la phase 2 detruit la preuve qu''elle doit '
  'inscrire: sans cette ligne, l''identite du migrateur devrait etre fournie '
  'par l''appelant — et l''etait, ce qui rendait l''activation forgeable.';

-- REECRITURE INTERDITE, RAMASSAGE AUTORISE (6.3b6c).
--
-- Une intention preparee puis VALIDEE seule ne peut plus servir: l'ecriture de
-- confiance exige la meme transaction, et celle-la est close. La laisser
-- bloquer a jamais le deploiement serait un fail-closed qui ne protege rien —
-- personne ne peut s'en servir. Elle est donc SUPPRIMABLE, et seulement elle:
--
--   * UPDATE: toujours refuse. Reecrire reviendrait a designer apres coup un
--     autre migrateur ou un autre donneur que ceux derives du catalogue.
--   * DELETE d'une intention de la transaction COURANTE: refuse aussi — c'est
--     la seule qui pourrait encore servir.
--   * DELETE d'une intention d'une AUTRE transaction: accepte. C'est du
--     ramassage, pas une reecriture.
create or replace function forbid_finalization_intent_mutation() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' and old.prepare_txid <> txid_current() then
    return old;
  end if;
  raise exception
    'l''intention de finalisation est figee: la reecrire reviendrait a '
    'designer apres coup un autre migrateur ou un autre donneur que ceux '
    'derives du catalogue. Seule une intention d''une transaction close — '
    'donc inutilisable — peut etre ramassee. Operation: %.', tg_op
    using errcode = 'restrict_violation';
end;
$$;

create trigger normative_finalization_intent_is_immutable
  before update or delete on normative_finalization_intent
  for each row execute function forbid_finalization_intent_mutation();

alter table normative_finalization_intent
  owner to eurostruct_normative_activator;
-- DELETE COMPRIS: le ramassage d'une intention de transaction close en a
-- besoin. Le declencheur ci-dessus refuse tout le reste — c'est lui qui
-- distingue « ramasser » de « reecrire », pas l'ACL.
grant select, insert, delete on normative_finalization_intent
  to eurostruct_normative_activator;
alter table normative_finalization_intent enable row level security;
alter table normative_finalization_intent force row level security;
revoke all on normative_finalization_intent from public;
grant select on normative_finalization_intent to normative_governance;
create policy normative_finalization_intent_gov_read
  on normative_finalization_intent
  for select to normative_governance using (true);
create policy normative_finalization_intent_lecture
  on normative_finalization_intent
  for select to eurostruct_normative_activator using (true);
create policy normative_finalization_intent_ecriture
  on normative_finalization_intent
  for insert to eurostruct_normative_activator with check (true);
create policy normative_finalization_intent_ramassage
  on normative_finalization_intent
  for delete to eurostruct_normative_activator using (true);

-- LE NOM DU MIGRATEUR, RELU. La revocation doit etre executee par le DONNEUR
-- (fait F2/F3: `REVOKE` par un autre role emet un avertissement et ne retire
-- rien), donc en contexte INVOKER — qui n'a aucun droit sur la table. Cette
-- fonction rend le nom, et rien d'autre. Elle ne prend aucun argument: il n'y
-- a rien a lui faire dire.
create or replace function normative_pending_migrator() returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select migrateur_nom from normative_finalization_intent limit 1;
$$;
alter function normative_pending_migrator()
  owner to eurostruct_normative_activator;

revoke all on function normative_pending_migrator() from public;
grant execute on function normative_pending_migrator()
  to eurostruct_normative_activator;
grant execute on function normative_pending_migrator() to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- PREPARATION — deriver, comparer, figer. Avant toute revocation.
-- ---------------------------------------------------------------------
-- ELLE NE RECOIT QUE LE MANIFESTE. Aucune identite ne lui est fournie: le
-- donneur et le migrateur sont derives de `pg_auth_members`, c'est-a-dire de
-- ce que PostgreSQL a inscrit lui-meme et que personne ne peut reecrire.
create or replace function normative_prepare_activation(p_manifeste text)
returns text
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  -- DEUX ROLES, ET NON TROIS (6.3b6c). `eurostruct_normative_activator`
  -- n'est plus jamais prete au migrateur: il possede la racine de confiance,
  -- posee par la phase 0. Il n'y a donc rien a en deriver, rien a en revoquer,
  -- et le migrateur n'a jamais pu l'endosser.
  --
  -- `assert_normative_topology()`, elle, continue d'examiner LES TROIS: le
  -- fait que l'activateur ne soit plus emprunte ne dispense pas de verifier
  -- que personne ne l'atteint.
  autorites text[] := array['eurostruct_normative_writer',
                            'eurostruct_normative_bootstrap'];
  noms text[] := array['eurostruct.approved_deployment_roles',
                       'eurostruct.approved_service_logins',
                       'eurostruct.token_roles'];
  valeurs text[] := array[]::text[];
  r text;
  reglage text;
  n int;
  d_oid oid := null; d_nom text := null;
  m_oid oid := null; m_nom text := null;
  o oid; nm text; mo oid; mn text;
  courant text;
  deja normative_finalization_intent%rowtype;
begin
  if p_manifeste is null or btrim(p_manifeste) = '' then
    raise exception
      'aucun manifeste presente. La finalisation exige que le plan de '
      'controle declare CE QU''IL A REVU: lisez normative_settings_manifest() '
      'au moment de la revue, et representez-le ici. Figer la valeur courante '
      'sans rien comparer ne prouve aucune approbation.'
      using errcode = 'invalid_parameter_value';
  end if;

  if exists (select 1 from normative_activation) then
    raise exception
      'le sous-systeme est deja ACTIF: il n''y a plus rien a preparer.'
      using errcode = 'restrict_violation';
  end if;

  -- LE VERROU DE FINALISATION DOIT DEJA ETRE DETENU (6.3b6c).
  --
  -- Il est pris par `normative_finalize_deployment()`, et par lui seul. Exiger
  -- ici qu'il soit DETENU PAR LA TRANSACTION COURANTE ferme l'appel direct:
  -- un appelant qui le prendrait lui-meme puis composerait les etapes ferait,
  -- par construction, ce que fait le finaliseur — dans UNE transaction, sous
  -- le meme verrou. Ce qui est ferme, c'est la composition EN PLUSIEURS
  -- transactions, qui contournait a la fois le verrou et l'atomicite.
  --
  -- `pg_locks` est lu par le serveur, pas declare par l'appelant.
  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction. La '
      'preparation n''est pas une operation autonome: elle fait partie de '
      'normative_finalize_deployment(), qui prend ce verrou et enchaine '
      'preparation, revocations et activation sans relacher la transaction.'
      using errcode = 'insufficient_privilege';
  end if;

  -- UNE INTENTION D'UNE AUTRE TRANSACTION EST MORTE: elle est ramassee.
  --
  -- L'ecriture de confiance exige la MEME transaction que la preparation. Une
  -- intention validee seule ne peut donc plus servir a rien — mais elle
  -- bloquerait le singleton a jamais. La ramasser n'est pas la reecrire: le
  -- declencheur d'immuabilite refuse toujours l'UPDATE, et refuse le DELETE
  -- d'une intention de la transaction courante.
  --
  -- CONTRE-EXEMPLE FERME (parcours A): la version precedente comparait le
  -- manifeste presente a celui DEJA ENREGISTRE, sans jamais relire les
  -- declarations. Une preparation validee, un `ALTER DATABASE`, puis une
  -- finalisation avec le manifeste d'origine: tout concordait, sauf la
  -- realite — fige « authenticated », declare
  -- « authenticated,anon,FICTIF_apres_prepare ». On ne compare plus le
  -- manifeste a lui-meme: on rederive tout, a chaque fois.
  delete from normative_finalization_intent
   where prepare_txid <> txid_current();

  select * into deja from normative_finalization_intent;
  if found then
    -- Meme transaction: la preparation a deja eu lieu dans ce finaliseur.
    if deja.manifeste <> p_manifeste then
      raise exception
        'deux manifestes differents dans la meme finalisation.'
        using errcode = 'invalid_parameter_value';
    end if;
    return deja.manifeste;
  end if;

  -- ------------------------------------------------------------------
  -- LE DONNEUR ET LE MIGRATEUR, DERIVES — par OID et par nom, et les memes
  -- pour les trois roles d'autorite.
  -- ------------------------------------------------------------------
  -- L'EMPRUNT SE RECONNAIT A SES OPTIONS, PAS A SON DONNEUR.
  --
  -- PostgreSQL accorde au CREATEUR d'un role une appartenance dont le grantor
  -- est `postgres` — fait F1, remesure ici: `admin=t, inherit=f, set=f`.
  -- L'emprunt de phase 1, lui, doit porter SET (ou INHERIT): sans lui le
  -- migrateur ne pourrait pas transferer la propriete des fonctions.
  --
  -- Une premiere version filtrait sur `not g.rolsuper`, c'est-a-dire sur
  -- l'identite du donneur. C'etait confondre deux choses: dans un
  -- provisionnement par superutilisateur — forme legitime en auto-heberge —
  -- l'octroi explicite vient AUSSI de `postgres`, et la derivation ne trouvait
  -- plus rien. Le deploiement devenait infinalisable pour une raison qui
  -- n'avait aucun rapport avec la securite.
  --
  -- `m.set_option or m.inherit_option`, lu sur la LIGNE DU CATALOGUE et non
  -- par `pg_has_role` — qui est transitif et compterait des roles atteints par
  -- une chaine, alors qu'on cherche l'octroi direct.
  foreach r in array autorites loop
    select count(*) into n
      from pg_auth_members m
      join pg_roles a on a.oid = m.roleid
      join pg_roles p on p.oid = m.member
     where a.rolname = r and not p.rolsuper
       and (m.set_option or m.inherit_option);
    if n <> 1 then
      raise exception
        'le role d''autorite « % » porte % emprunt(s) utilisable(s) par un '
        'role non superutilisateur, il en faut exactement 1. Soit la phase 1 '
        'n''est pas terminee, soit les emprunts ont deja ete restitues, soit '
        'plusieurs roles ont emprunte — et une seule operation ne pourrait '
        'pas tous les restituer.', r, n
        using errcode = 'invalid_parameter_value';
    end if;

    select g.oid, g.rolname, p.oid, p.rolname into o, nm, mo, mn
      from pg_auth_members m
      join pg_roles a on a.oid = m.roleid
      join pg_roles p on p.oid = m.member
      join pg_roles g on g.oid = m.grantor
     where a.rolname = r and not p.rolsuper
       and (m.set_option or m.inherit_option);

    if d_oid is null then
      d_oid := o; d_nom := nm; m_oid := mo; m_nom := mn;
    elsif d_oid <> o or d_nom <> nm or m_oid <> mo or m_nom <> mn then
      raise exception
        'les emprunts ne designent pas les memes roles: « % » -> « % » pour '
        'un role d''autorite, « % » -> « % » pour « % ».',
        d_nom, m_nom, nm, mn, r
        using errcode = 'insufficient_privilege';
    end if;
  end loop;

  -- LE PLAN DE CONTROLE NE PEUT PAS ETRE LE MIGRATEUR. Verifie sur l'OID ET
  -- sur le nom: en greenfield, le migrateur cree lui-meme les roles d'autorite
  -- et se les accorde, si bien que donneur et migrateur sont le meme role.
  if d_oid = m_oid or d_nom = m_nom then
    raise exception
      'le plan de controle derive est le migrateur lui-meme (« % »). '
      'La finalisation exige deux roles DISTINCTS: celui qui applique les '
      'migrations et celui qui approuve. Sinon le migrateur conserve l''ADMIN '
      'residuel en etant son propre plan de controle, et peut se reaccorder '
      'SET quand il veut — la separation serait nominale. Provisionnez les '
      'roles d''autorite depuis un role distinct, puis relancez.', m_nom
      using errcode = 'insufficient_privilege';
  end if;

  -- ------------------------------------------------------------------
  -- LE DONNEUR DOIT ETRE CELUI QUI A POSE LE SCEAU (6.3b6d, point 3)
  -- ------------------------------------------------------------------
  -- L'identite du plan de controle etait DERIVEE du grantor des emprunts, et
  -- de rien d'autre. Le sceau, lui, n'enregistrait pas son poseur. Le plan de
  -- controle se transferait donc par un simple GRANT, en silence.
  --
  -- CONTRE-EXEMPLE MESURE (db/test/seal_contract.sh, scenario J), dans la
  -- forme que ce fichier documente lui-meme (« Ils peuvent PREEXISTER »):
  --
  --   * les six roles sont crees par l'administrateur;
  --   * A recoit l'ADMIN sur l'activateur et applique la phase 0;
  --   * l'administrateur retire a A son ADMIN residuel — operation legitime,
  --     et possible parce que A n'est pas le createur des roles (fait F3);
  --   * B recoit writer/bootstrap, prete au migrateur, finalise.
  --
  -- Resultat: ACTIVE, plan de controle fige = B. Le sceau de A finalise par B,
  -- sans qu'aucun evenement ne soit inscrit nulle part.
  --
  -- UNE PREMIERE LECTURE CROYAIT LE CAS DEJA FERME. Sans effacer A, la
  -- topologie refuse — parce que A garde un ADMIN residuel et que deux plans
  -- de controle sont interdits. Mais c'est un refus obtenu par une AUTRE
  -- barriere, qui disparait des que A est efface. Une garantie qui ne tient
  -- que grace a un effet de bord n'est pas une garantie.
  --
  -- PAR OID **ET** PAR NOM. Le nom seul suivrait une reprise d'etiquette;
  -- l'OID seul suivrait un renommage. Les deux, jamais l'un sans l'autre.
  --
  -- LA DELEGATION N'EST PAS INTERDITE PAR PRINCIPE — elle est interdite
  -- SILENCIEUSE. Transferer le plan de controle devra etre un evenement
  -- explicite, inscrit et audite. Aucun tel evenement n'existe aujourd'hui, et
  -- ce refus dit ou il devra s'inscrire quand il existera.
  declare
    p_oid oid; p_nom text; p_assurance text;
  begin
    select installer_oid, installer_name, assurance_level
      into p_oid, p_nom, p_assurance
      from normative_seal_metadata
     order by installed_at asc, seal_version asc limit 1;

    if p_oid is null then
      raise exception
        'le sceau n''enregistre aucun poseur: la finalisation ne peut pas '
        'verifier que celui qui approuve est celui qui a pose la racine.'
        using errcode = 'insufficient_privilege';
    end if;

    if d_oid <> p_oid or d_nom <> p_nom then
      -- UN SCEAU POSE PAR UN SUPERUTILISATEUR NE PORTE PAS CETTE LIAISON, et
      -- ce n'est pas une indulgence: c'est une CONSEQUENCE MESUREE de
      -- PostgreSQL 16. Un `GRANT role TO membre` execute par un
      -- superutilisateur est enregistre au nom du superutilisateur
      -- D'AMORCAGE — `postgres`, oid 10 —, jamais du role qui l'a execute:
      --
      --   set role t_sup;  grant t_r to t_m;   -- t_sup EST superutilisateur
      --   -> grantor enregistre: postgres (oid 10)
      --   set role t_ns;   grant t_r to t_m;   -- t_ns ne l'est pas
      --   -> grantor enregistre: t_ns
      --
      -- Le donneur DERIVE d'une phase 1 pretee par un superutilisateur est
      -- donc toujours `postgres`, et jamais le poseur. Exiger l'egalite
      -- rendrait le deploiement auto-heberge INFINALISABLE — pour une raison
      -- de comptabilite des octrois, sans rapport avec la securite.
      --
      -- ET LA GARANTIE N'EST PAS PERDUE POUR AUTANT, parce qu'elle n'existait
      -- pas: un superutilisateur peut de toute facon endosser n'importe qui,
      -- reecrire n'importe quelle table et desactiver n'importe quel
      -- declencheur. La base le DIT — `assurance_level` vaut
      -- UNCONTAINED_SUPERUSER, il est persiste, lisible par la readiness, et
      -- `tools/deploy_eurostruct.sh` le refuse en mode strict.
      if p_assurance = 'UNCONTAINED_SUPERUSER' then
        raise notice
          'la liaison poseur/finaliseur ne s''applique pas: le sceau a ete '
          'pose par un SUPERUTILISATEUR (« % »), et PostgreSQL attribue ses '
          'octrois au superutilisateur d''amorcage. Deploiement AUTO-HEBERGE, '
          'explicitement degrade.', p_nom;
      else
        raise exception
          'SEAL_INSTALLER_MISMATCH: le sceau a ete pose par « % » (oid %), et '
          'la finalisation est exercee au nom de « % » (oid %). Le plan de '
          'controle d''une base est celui qui a pose sa racine de confiance: '
          'il ne se transfere pas par un GRANT. Si une delegation est voulue, '
          'elle doit etre un evenement explicite et audite — il n''en existe '
          'aucun aujourd''hui. Finalisez depuis « % », ou redeployez la base '
          'depuis la phase 0.', p_nom, p_oid, d_nom, d_oid, p_nom
          using errcode = 'insufficient_privilege';
      end if;
    end if;
  end;

  -- LE DONNEUR DOIT DETENIR L'ADMIN SUR LES TROIS: c'est ce qui lui permettra
  -- de revoquer (fait F3), et c'est ce qui justifiera son exemption d'ADMIN
  -- residuel une fois le sous-systeme ACTIVE.
  select count(*) into n from unnest(autorites) a(r)
   where pg_has_role(d_nom, a.r, 'MEMBER WITH ADMIN OPTION');
  -- LE COMPTE EST DERIVE DU TABLEAU, PAS ECRIT EN DUR (6.3b6c). Quand
  -- l'activateur a quitte la liste des roles empruntes, ce « 3 » fige a fait
  -- refuser une finalisation parfaitement saine — « ne detient l'ADMIN que sur
  -- 2 role(s) sur 3 » — pour une raison qui n'existait plus.
  if n <> array_length(autorites, 1) then
    raise exception
      'le donneur derive « % » ne detient l''ADMIN que sur % role(s) '
      'sur % empruntes: il ne pourrait pas restituer tous les emprunts.',
      d_nom, n, array_length(autorites, 1) using errcode = 'insufficient_privilege';
  end if;

  -- ET L'APPELANT DOIT ETRE CE DONNEUR — ou pouvoir l'endosser. C'est lui, et
  -- lui seul, dont les `REVOKE` auront un effet.
  if session_user <> d_nom and not pg_has_role(session_user, d_nom, 'SET') then
    raise exception
      'la finalisation doit etre exercee par le DONNEUR des emprunts, « % ». '
      'Elle est demandee par « % », qui ne peut pas l''endosser: ses REVOKE '
      'seraient sans effet — PostgreSQL emettrait un avertissement et les '
      'appartenances survivraient.', d_nom, session_user
      using errcode = 'insufficient_privilege';
  end if;

  -- ------------------------------------------------------------------
  -- LE MANIFESTE, COMPARE ATOMIQUEMENT AUX VALEURS QUI SERONT FIGEES
  -- ------------------------------------------------------------------
  -- LES TROIS VALEURS SONT LUES UNE SEULE FOIS, dans `valeurs`. Le digest est
  -- calcule SUR CE TABLEAU, et c'est CE MEME TABLEAU qui est fige. Relire les
  -- declarations entre la comparaison et le gel rouvrirait exactement la
  -- fenetre que ce controle existe pour fermer.
  foreach reglage in array noms loop
    valeurs := valeurs || normative_declared_setting(reglage);
  end loop;

  select encode(sha256(convert_to(
           string_agg(noms[i] || '=' || valeurs[i], E'\n' order by i), 'UTF8')),
         'hex')
    into courant
    from generate_subscripts(noms, 1) as i;

  if courant is distinct from p_manifeste then
    raise exception
      'le manifeste presente ne correspond pas aux declarations reellement '
      'posees: approbation « % », constate « % ». Une declaration a change '
      'entre la revue et la finalisation. Figer une valeur ne prouve pas '
      'qu''elle a ete approuvee: reexaminez, puis representez le manifeste.',
      p_manifeste, courant
      using errcode = 'invalid_parameter_value';
  end if;

  -- LA PREPARATION N'ECRIT PLUS QUE L'INTENTION (6.3b6c).
  --
  -- Elle figeait ici le plan de controle et les trois declarations. Ces deux
  -- tables sont des singletons append-only: une preparation validee SEULE les
  -- consommait, et le deploiement devenait definitivement infinalisable — un
  -- fail-closed qui ne protegeait rien, puisque l'intention correspondante
  -- etait de toute facon inutilisable.
  --
  -- Le gel a donc migre dans `normative_record_activation()`, qui s'execute
  -- dans la MEME transaction et juste avant l'activation. Les valeurs
  -- constatees ici voyagent avec l'intention: c'est le meme tableau qui a ete
  -- digere et qui sera fige.
  insert into normative_finalization_intent
    (migrateur_oid, migrateur_nom, donneur_oid, donneur_nom, manifeste,
     valeurs, prepare_par)
  values (m_oid, m_nom, d_oid, d_nom, courant, valeurs, session_user);

  return courant;
end;
$$;
alter function normative_prepare_activation(text)
  owner to eurostruct_normative_activator;

comment on function normative_prepare_activation is
  'Derive du catalogue le donneur et le migrateur — par OID et par nom —, '
  'compare le manifeste presente aux declarations reellement posees, puis '
  'fige le plan de controle, les declarations et l''intention. N''ecrit rien '
  'si le manifeste ne correspond pas. Ne recoit aucune identite.';

revoke all on function normative_prepare_activation(text) from public;
grant execute on function normative_prepare_activation(text)
  to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- CONTRAT DU topology_digest — UNE PHOTOGRAPHIE, PAS UN CONTROLE
-- ---------------------------------------------------------------------
-- LE CONTRAT EST TRANCHE ICI, parce qu'il ne l'etait pas et que les deux
-- lectures possibles ne demandent pas le meme travail.
--
--   * CE QU'IL EST: une PHOTOGRAPHIE d'audit. Il fige, au moment de
--     l'activation, qui atteignait quoi parmi les six roles canoniques, avec
--     l'identite du plan de controle, celle du migrateur et le manifeste
--     approuve. Il repond a « sur quoi l'activation a-t-elle porte ? ».
--
--   * CE QU'IL N'EST PAS: un detecteur de derive. Rien ne le recalcule pour le
--     comparer, et rien ne le fera: une dérive qui reste dans les regles doit
--     pouvoir avoir lieu — accorder `normative_backend` a un role de service
--     nouvellement declare, par exemple — sans qu'un digest fige la refuse.
--
-- CE QUI BLOQUE LES DERIVES INTERDITES, ce sont les invariants de
-- `assert_normative_topology()`, appelee par la readiness. Le digest et elle
-- ne font pas le meme travail, et confondre les deux ferait croire a une
-- protection qui n'existe pas.
--
-- La fonction ci-dessous existe pour rendre la distinction OBSERVABLE: un
-- auditeur refait la photo et la compare a celle qui a ete inscrite. Si elles
-- different, la topologie a change depuis l'activation — ce qui est une
-- information, pas un verdict.
create or replace function normative_topology_digest(
  p_plan_oid oid, p_plan_nom text,
  p_migrateur_oid oid, p_migrateur_nom text,
  p_manifeste text
) returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select encode(sha256(convert_to(
           'plan=' || p_plan_oid::text || ':' || p_plan_nom || E'\n'
           || 'migrateur=' || p_migrateur_oid::text || ':' || p_migrateur_nom || E'\n'
           || 'manifeste=' || p_manifeste || E'\n'
           || coalesce(string_agg(ligne, E'\n' order by ligne), ''), 'UTF8')),
         'hex')
    from (
      select a.rolname || '|' || m.rolname || '|'
             || pg_has_role(m.rolname, a.rolname, 'SET')::text || '|'
             || pg_has_role(m.rolname, a.rolname, 'USAGE')::text || '|'
             || pg_has_role(m.rolname, a.rolname, 'MEMBER WITH ADMIN OPTION')::text
             as ligne
        from pg_roles a
        cross join pg_roles m
       where a.rolname in ('eurostruct_normative_writer',
                           'eurostruct_normative_bootstrap',
                           'eurostruct_normative_activator',
                           'normative_backend', 'normative_governance',
                           'eurostruct_deployment')
         and m.oid <> a.oid
         and not m.rolsuper
         and (pg_has_role(m.rolname, a.rolname, 'SET')
              or pg_has_role(m.rolname, a.rolname, 'USAGE')
              or pg_has_role(m.rolname, a.rolname, 'MEMBER WITH ADMIN OPTION'))
    ) t;
$$;
alter function normative_topology_digest(oid, text, oid, text, text)
  owner to eurostruct_normative_activator;

comment on function normative_topology_digest is
  'Refait la PHOTOGRAPHIE de topologie inscrite a l''activation. Sert a '
  'l''audit — comparer avec normative_activation.topology_digest — jamais a '
  'refuser: les refus appartiennent a assert_normative_topology().';

revoke all on function normative_topology_digest(oid, text, oid, text, text)
  from public;
grant execute on function normative_topology_digest(oid, text, oid, text, text)
  to eurostruct_normative_activator;
-- AU DEPLOIEMENT SEUL. `normative_governance` l'avait recu, au motif que
-- l'audit peut vouloir refaire la photo — et la garantie generale de
-- `05_normative_confirmation.sql` l'a refuse: c'est un role APPLICATIF, et
-- aucune fonction sensible ne doit lui etre appelable. La gouvernance lit
-- `normative_activation`, ou le digest inscrit figure deja.
grant execute on function normative_topology_digest(oid, text, oid, text, text)
  to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- L'ECRITURE DE CONFIANCE — sans argument, donc sans rien a lui faire dire
-- ---------------------------------------------------------------------
-- ELLE NE PREND AUCUN ARGUMENT (6.3b6b, point 2). Tout ce qu'elle inscrit est
-- relu de ce que la preparation a derive, ou reconstate dans le catalogue.
-- Appelee directement, elle ne peut donc rien affirmer que l'etat ne porte
-- deja: sans intention preparee, elle refuse; avec une intention preparee mais
-- sans revocation, elle refuse aussi.
--
-- L'ancienne signature `(text, text)` est DETRUITE et non simplement
-- remplacee: `create or replace` en aurait fait une surcharge, et la porte
-- serait restee ouverte a cote de la nouvelle.
drop function if exists normative_record_activation(text, text);

create or replace function normative_record_activation() returns text
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  -- DEUX ROLES, ET NON TROIS (6.3b6c). `eurostruct_normative_activator`
  -- n'est plus jamais prete au migrateur: il possede la racine de confiance,
  -- posee par la phase 0. Il n'y a donc rien a en deriver, rien a en revoquer,
  -- et le migrateur n'a jamais pu l'endosser.
  --
  -- `assert_normative_topology()`, elle, continue d'examiner LES TROIS: le
  -- fait que l'activateur ne soit plus emprunte ne dispense pas de verifier
  -- que personne ne l'atteint.
  autorites text[] := array['eurostruct_normative_writer',
                            'eurostruct_normative_bootstrap'];
  intention normative_finalization_intent%rowtype;
  plan_oid oid;
  plan_nom text;
  n int;
  digest text;
begin
  if exists (select 1 from normative_activation) then
    raise exception
      'le sous-systeme est deja ACTIF: une seconde activation reecrirait '
      'l''audit de deploiement.'
      using errcode = 'restrict_violation';
  end if;

  -- LE VERROU DE FINALISATION, DETENU PAR CETTE TRANSACTION (6.3b6c).
  -- Meme exigence que la preparation, et pour la meme raison.
  if not exists (
    select 1 from pg_locks
     where locktype = 'advisory'
       and pid = pg_backend_pid()
       and granted
       and ((classid::bigint << 32) | objid::bigint)
           = hashtext('eurostruct.normative_finalisation')::bigint
  ) then
    raise exception
      'le verrou de finalisation n''est pas detenu par cette transaction: '
      'l''activation ne s''inscrit que depuis normative_finalize_deployment().'
      using errcode = 'insufficient_privilege';
  end if;

  select * into intention from normative_finalization_intent;
  if not found then
    raise exception
      'aucune intention de finalisation preparee. L''activation ne peut pas '
      'etre inscrite tant que l''identite du donneur et celle du migrateur '
      'n''ont pas ete DERIVEES du catalogue — ce qui n''est possible qu''avant '
      'la revocation des emprunts. Passez par normative_finalize_deployment().'
      using errcode = 'insufficient_privilege';
  end if;

  -- LA MEME TRANSACTION QUE LA PREPARATION (6.3b6c).
  --
  -- C'est ce qui rend les trois fonctions non composables. CONTRE-EXEMPLE
  -- MESURE (parcours B): preparer, valider, revoquer les emprunts a la main
  -- comme le ferait le finaliseur, puis appeler cette fonction — le
  -- sous-systeme passait ACTIVE en trois transactions, sans le verrou et sans
  -- qu'aucune etape ne puisse annuler les autres.
  --
  -- L'identifiant de transaction est attribue par le serveur. Ce n'est ni un
  -- GUC, ni un marqueur fourni par la session: l'appelant ne peut pas le
  -- choisir, et il change des qu'il valide.
  if intention.prepare_txid <> txid_current() then
    raise exception
      'l''intention de finalisation a ete preparee dans une AUTRE transaction '
      '(% au lieu de %). Preparation, revocations et activation doivent tenir '
      'dans une seule transaction: sinon aucune ne peut annuler les autres, '
      'et l''etat intermediaire — emprunts rendus sans activation, ou '
      'l''inverse — devient atteignable.',
      intention.prepare_txid, txid_current()
      using errcode = 'insufficient_privilege';
  end if;

  -- LE PLAN DE CONTROLE ET LES DECLARATIONS SONT FIGES ICI, dans la meme
  -- transaction que l'activation, a partir de ce que la preparation a derive
  -- et constate. Les figer plus tot rendait une preparation validee seule
  -- definitivement bloquante.
  plan_oid := intention.donneur_oid;
  plan_nom := intention.donneur_nom;
  insert into normative_control_plane (role_oid, role_name, recorded_by)
  values (plan_oid, plan_nom, session_user);

  for n in 1 .. 3 loop
    insert into normative_approved_settings (nom, valeur, fige_par)
    values ((array['eurostruct.approved_deployment_roles',
                   'eurostruct.approved_service_logins',
                   'eurostruct.token_roles'])[n],
            intention.valeurs[n], session_user);
  end loop;
  if not exists (select 1 from pg_roles
                  where oid = plan_oid and rolname = plan_nom) then
    raise exception
      'le plan de controle (oid %, « % ») ne designe plus un role portant ce '
      'nom: il a ete renomme, detruit, ou son nom a ete repris par un autre '
      'role.', plan_oid, plan_nom using errcode = 'insufficient_privilege';
  end if;

  select count(*) into n from unnest(autorites) a(r)
   where pg_has_role(plan_nom, a.r, 'MEMBER WITH ADMIN OPTION');
  if n <> array_length(autorites, 1) then
    raise exception
      'le plan de controle « % » ne detient l''ADMIN que sur % role(s) '
      'd''autorite sur %.', plan_nom, n, array_length(autorites, 1)
      using errcode = 'insufficient_privilege';
  end if;

  -- LE MIGRATEUR NE DOIT PLUS RIEN DETENIR. C'est la propriete que la
  -- finalisation achete, et elle est constatee ICI, juste avant d'ecrire.
  select count(*) into n from unnest(autorites) a(r)
   where pg_has_role(intention.migrateur_nom, a.r, 'SET')
      or pg_has_role(intention.migrateur_nom, a.r, 'USAGE')
      or pg_has_role(intention.migrateur_nom, a.r, 'MEMBER WITH ADMIN OPTION');
  if n <> 0 then
    raise exception
      'le migrateur « % » detient encore % capacite(s) sur les roles '
      'd''autorite: les emprunts n''ont pas ete restitues. L''activer '
      'maintenant graverait une topologie que la readiness refusera des la '
      'premiere verification.', intention.migrateur_nom, n
      using errcode = 'insufficient_privilege';
  end if;

  -- LE DIGEST EST CALCULE PAR LE SERVEUR, jamais fourni, et il PORTE
  -- L'IDENTITE DU PLAN DE CONTROLE (6.3b6b, point 3). Sans elle, l'audit ne
  -- permettait pas de constater apres coup qu'un autre role avait pris le nom
  -- approuve — la substitution etait indetectable.
  --
  -- LE CALCUL EST DANS `normative_topology_digest()`, pour qu'un auditeur
  -- puisse REFAIRE LA PHOTO et la comparer a celle qui a ete inscrite. Voir
  -- « CONTRAT DU topology_digest » plus haut: c'est une photographie, pas un
  -- controle — le refus, lui, vient de `assert_normative_topology()`.
  digest := normative_topology_digest(plan_oid, plan_nom,
                                      intention.migrateur_oid,
                                      intention.migrateur_nom,
                                      intention.manifeste);

  insert into normative_activation (activated_by, topology_digest)
  values (session_user, digest);

  -- ET LA TOPOLOGIE, EN DERNIER, DANS L'ETAT « ACTIVE ». Si elle refuse, tout
  -- ce qui precede est annule: la transaction entiere part.
  perform assert_normative_topology();

  return digest;
end;
$$;
alter function normative_record_activation()
  owner to eurostruct_normative_activator;

comment on function normative_record_activation is
  'Inscrit l''activation a partir de ce que la preparation a DERIVE et de ce '
  'que le catalogue porte encore. Ne prend aucun argument: il n''y a rien a '
  'lui faire dire. Refuse sans intention preparee, et refuse si le migrateur '
  'detient encore quoi que ce soit. Calcule le digest cote serveur, identite '
  'du plan de controle comprise.';

revoke all on function normative_record_activation() from public;
grant execute on function normative_record_activation()
  to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- L'IDEMPOTENCE N'EST PAS UN BLANC-SEING (6.3b6c)
-- ---------------------------------------------------------------------
-- En etat ACTIVE, la finalisation rendait « ACTIVE (deja finalise) » SANS
-- regarder le manifeste presente. Mesure: un manifeste autre, vide ou mal
-- forme recevait le meme succes. Un script de deploiement pointe sur la
-- mauvaise base, ou portant une configuration ancienne, ne pouvait pas s'en
-- apercevoir.
--
-- LES DEUX BRANCHES ACTIVE l'appellent — celle d'avant le verrou et celle
-- d'apres. Une seule des deux protegee laisserait passer exactement le cas
-- qu'on veut fermer: deux deploiements concurrents dont l'un porte la mauvaise
-- configuration.
create or replace function normative_exiger_manifeste_approuve(p_manifeste text)
returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare approuve text;
begin
  approuve := normative_approved_manifest();
  if p_manifeste is null or btrim(p_manifeste) = '' then
    raise exception
      'MANIFEST_MISMATCH: aucun manifeste presente alors que le sous-systeme '
      'est deja ACTIF. Le manifeste approuve est « % ».', approuve
      using errcode = 'invalid_parameter_value';
  end if;
  if p_manifeste is distinct from approuve then
    raise exception
      'MANIFEST_MISMATCH: le manifeste presente « % » n''est pas celui qui a '
      'ete approuve sur cette base (« % »). Soit ce script vise une autre '
      'base, soit il porte une configuration qui n''a jamais ete approuvee '
      'ici. L''activation deja faite n''est pas une raison de repondre '
      'succes.', p_manifeste, approuve
      using errcode = 'invalid_parameter_value';
  end if;
end;
$$;
alter function normative_exiger_manifeste_approuve(text)
  owner to eurostruct_normative_activator;

revoke all on function normative_exiger_manifeste_approuve(text) from public;
grant execute on function normative_exiger_manifeste_approuve(text)
  to eurostruct_normative_activator;
grant execute on function normative_exiger_manifeste_approuve(text)
  to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- LA FINALISATION — exercee par le donneur, serialisee, en une transaction
-- ---------------------------------------------------------------------
-- La signature change: elle ne recoit plus le nom du migrateur — qui est
-- derive — mais LE MANIFESTE des declarations approuvees. L'ancienne
-- signature est detruite: `create or replace` refuserait de renommer un
-- parametre, et la laisser vivre a cote rouvrirait le contournement.
drop function if exists normative_finalize_deployment(text);

create or replace function normative_finalize_deployment(p_manifeste text)
returns text
language plpgsql
set search_path = public, pg_temp
as $$
declare
  -- DEUX ROLES, ET NON TROIS (6.3b6c). `eurostruct_normative_activator`
  -- n'est plus jamais prete au migrateur: il possede la racine de confiance,
  -- posee par la phase 0. Il n'y a donc rien a en deriver, rien a en revoquer,
  -- et le migrateur n'a jamais pu l'endosser.
  --
  -- `assert_normative_topology()`, elle, continue d'examiner LES TROIS: le
  -- fait que l'activateur ne soit plus emprunte ne dispense pas de verifier
  -- que personne ne l'atteint.
  autorites text[] := array['eurostruct_normative_writer',
                            'eurostruct_normative_bootstrap'];
  r text;
  migrateur text;
  n int;
begin
  -- IDEMPOTENCE, avant meme le verrou: une finalisation deja faite ne doit ni
  -- attendre ni echouer bruyamment.
  if normative_activation_state() = 'ACTIVE' then
    perform normative_exiger_manifeste_approuve(p_manifeste);
    perform assert_normative_topology();
    return 'ACTIVE (deja finalise)';
  end if;

  -- ------------------------------------------------------------------
  -- SERIALISATION (6.3b6b, point 4)
  -- ------------------------------------------------------------------
  -- CONTRE-EXEMPLE MESURE: deux finalisations concurrentes, recouvrement
  -- constate. Les deux lisaient PENDING, les deux revoquaient, et le perdant
  -- obtenait « ERROR: le sous-systeme est deja ACTIF » — une erreur brute la
  -- ou le contrat exige un resultat idempotent.
  --
  -- VERROU CONSULTATIF **TRANSACTIONNEL**: rendu au commit comme au rollback.
  -- Un verrou de session survivrait a l'echec et bloquerait toute reprise.
  perform pg_advisory_xact_lock(hashtext('eurostruct.normative_finalisation'));

  -- RELECTURE APRES LE VERROU, et c'est tout l'objet du verrou. En READ
  -- COMMITTED, chaque instruction d'une fonction VOLATILE prend un nouvel
  -- instantane: le perdant voit donc ici ce que le gagnant a valide pendant
  -- qu'il attendait, et rend le meme resultat que s'il etait arrive apres.
  if normative_activation_state() = 'ACTIVE' then
    perform normative_exiger_manifeste_approuve(p_manifeste);
    perform assert_normative_topology();
    return 'ACTIVE (deja finalise)';
  end if;

  -- PREPARER AVANT DE REVOQUER. La preparation derive les identites pendant
  -- qu'elles sont encore dans le catalogue, compare le manifeste et fige. Elle
  -- verifie aussi que c'est bien le donneur qui demande.
  perform normative_prepare_activation(p_manifeste);

  migrateur := normative_pending_migrator();
  if migrateur is null then
    raise exception
      'la preparation n''a laisse aucune intention: rien a revoquer.'
      using errcode = 'insufficient_privilege';
  end if;

  -- SEUL LE DONNEUR PEUT REVOQUER. Ce n'est pas une regle du produit, c'est
  -- PostgreSQL (fait F2, mesure): `REVOKE` execute par un autre role emet un
  -- avertissement et ne retire rien. La preparation a deja refuse si
  -- l'appelant n'est pas le donneur — ces `REVOKE` ont donc un effet.
  --
  -- ATOMIQUE. Une fonction PL/pgSQL s'execute dans la transaction de
  -- l'appelant: toute exception levee ici annule TOUT — revocations, plan de
  -- controle fige, declarations gelees, intention. Il n'existe pas d'etat
  -- intermediaire ou l'emprunt serait rendu sans que l'activation soit
  -- inscrite, ni l'inverse.
  foreach r in array autorites loop
    execute format('revoke %I from %I', r, migrateur);
  end loop;

  -- CONSTATE, et non suppose: les revocations ont-elles pris ?
  select count(*) into n from unnest(autorites) a(r)
   where pg_has_role(migrateur, a.r, 'SET')
      or pg_has_role(migrateur, a.r, 'USAGE')
      or pg_has_role(migrateur, a.r, 'MEMBER WITH ADMIN OPTION');
  if n <> 0 then
    raise exception
      'apres revocation, « % » conserve % capacite(s) sur les roles '
      'd''autorite. La transaction est annulee: mieux vaut une phase 1 non '
      'finalisee qu''une activation qui ment.', migrateur, n
      using errcode = 'insufficient_privilege';
  end if;

  return normative_record_activation();
end;
$$;

comment on function normative_finalize_deployment is
  'Phase 2, exercee par le DONNEUR des emprunts et serialisee par un verrou '
  'consultatif transactionnel. Recoit le MANIFESTE approuve, jamais une '
  'identite: le donneur et le migrateur sont derives du catalogue avant la '
  'revocation. Prepare, revoque, constate, inscrit. Toute exception annule '
  'l''ensemble; une seconde execution rend « ACTIVE (deja finalise) ».';

revoke all on function normative_finalize_deployment(text) from public;
grant execute on function normative_finalize_deployment(text)
  to eurostruct_deployment;


-- ---------------------------------------------------------------------
-- LE SCEAU EST REFERME
-- ---------------------------------------------------------------------
-- CREATE sur `public` ne sert plus: les objets sont crees et transferes.
revoke create on schema public from eurostruct_normative_activator;

-- ET L'EMPRUNT EST RENDU. A partir d'ici, plus personne ne peut endosser
-- l'activateur: il est NOLOGIN, sans membre, et le seul chemin vers les
-- tables de confiance passe par les fonctions SECURITY DEFINER qu'il possede.
--
-- CONSTATE, ET NON SUPPOSE. Un `REVOKE` sans effet emet un simple
-- avertissement: si la restitution echouait en silence, le plan de controle
-- garderait la capacite d'ecrire directement dans la racine, et ce fichier
-- aurait pose une porte au lieu d'un sceau.
do $$
declare n int;
begin
  execute format('revoke eurostruct_normative_activator from %I', current_user);

  -- UN SUPERUTILISATEUR N'EST PAS CONTENU PAR CE SCEAU, ET ON LE DIT.
  --
  -- `pg_has_role(superutilisateur, ..., 'SET')` rend TRUE quoi qu'il arrive:
  -- il n'y a aucun octroi a revoquer, et le constat ci-dessous ne pourrait
  -- jamais reussir. Un deploiement ou l'administrateur pose lui-meme le sceau
  -- est legitime — c'est la forme auto-hebergee — mais il n'obtient pas la
  -- garantie que la forme Supabase obtient. Le modele de menace l'ecrit:
  -- le superutilisateur est hors modele.
  --
  -- EXEMPTER SANS LE DIRE aurait ete pire que ne pas verifier: le fichier
  -- aurait annonce un sceau ferme la ou il ne l'est pas.
  if (select bool_or(rolsuper) from pg_roles
       where rolname in (current_user, session_user)) then
    -- LE NOTICE RESTE, MAIS IL N'EST PLUS LA SEULE TRACE (6.3b6d). Le niveau
    -- est inscrit dans `normative_seal_metadata`, ou la readiness le lit. Un
    -- NOTICE ne survit pas au pipeline qui l'a affiche.
    raise notice
      'phase 0 appliquee par un SUPERUTILISATEUR (%): le sceau est pose, mais '
      'il ne contient pas celui qui l''a pose — aucun sceau ne le peut. '
      'Niveau d''assurance inscrit: UNCONTAINED_SUPERUSER. Voir '
      'docs/schema/MODELE_DE_MENACE_NORMATIF.md.', current_user;
    return;
  end if;

  select count(*) into n
    from pg_roles a
   where a.rolname = 'eurostruct_normative_activator'
     and (pg_has_role(current_user, a.rolname, 'SET')
          or pg_has_role(current_user, a.rolname, 'USAGE'));
  if n <> 0 then
    raise exception
      'le sceau n''a pas pu etre referme: « % » conserve SET ou USAGE sur '
      'eurostruct_normative_activator. La racine de confiance serait a sa '
      'portee, et la phase 0 aurait pose une porte au lieu d''un sceau.',
      current_user using errcode = 'insufficient_privilege';
  end if;
end
$$;

-- LE SCEAU, CONSTATE. Les CINQ tables de confiance existent, appartiennent
-- a l'activateur, et leur RLS est FORCEE — le proprietaire lui-meme y est
-- soumis. C'est ce que la phase 1 verifiera avant de s'appliquer.
--
-- `normative_seal_metadata` EN FAIT PARTIE (6.3b6d): sans elle, un sceau
-- installe serait indistinguable d'un sceau partiel, et la garde de
-- reexecution ne pourrait pas trancher.
do $$
declare manquantes text;
begin
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
      'le sceau est incomplet: % ne sont pas possedees par l''activateur avec '
      'RLS forcee.', manquantes using errcode = 'insufficient_privilege';
  end if;
end
$$;

-- ET L'IDENTITE DU SCEAU EST CONSTATEE AUSSI. La ligne a-t-elle bien ete
-- ecrite ? Sans ce controle, une base ou l'insertion aurait echoue en silence
-- — un `select` sans ligne n'est pas une erreur — sortirait de la phase 0 avec
-- une racine complete et sans identite, c'est-a-dire infinalisable pour une
-- raison qu'aucun message n'expliquerait.
do $$
declare v text; a text; qui text;
begin
  select seal_version, assurance_level, installer_name
    into v, a, qui from normative_seal_metadata;
  if v is null then
    raise exception
      'le sceau a ete pose sans identite: normative_seal_metadata est vide. '
      'La base serait complete et infinalisable.'
      using errcode = 'insufficient_privilege';
  end if;
  raise notice 'sceau « % » pose par « % » — assurance: %', v, qui, a;
end
$$;


-- ---------------------------------------------------------------------
-- LE CONTEXTE D'EXECUTION DES CINQ GARDES POSEES ICI
-- ---------------------------------------------------------------------
-- CE QUI A ETE MESURE, ET QUI JUSTIFIE CES CINQ LIGNES.
--
-- Une fonction declencheur SANS `search_path` epingle s'execute avec le chemin
-- de CELUI QUI DECLENCHE l'ecriture. Experience faite le 28/08 sur base
-- jetable, sur la forme exacte d'une de ces gardes:
--
--   * sans manipulation, la garde REFUSE — « le calcul est fige »;
--   * apres `create temporary table validations (...)` dans la meme session,
--     la meme commande passe: `UPDATE 1`.
--
-- `pg_temp` est consulte EN PREMIER pour les relations quand il n'est pas
-- nomme explicitement, et `TEMP` est accorde a PUBLIC par defaut — mesure sur
-- la base deployee: `datacl = {=Tc/<migrateur>, ...}`. N'importe quel role
-- capable de se connecter peut donc creer la relation qui masque celle que la
-- garde interroge.
--
-- LES CINQ GARDES CI-DESSOUS N'INTERROGENT AUCUNE RELATION: leur corps ne
-- contient qu'un `raise exception`, et pour l'une d'elles un `txid_current()`.
-- Le vecteur `pg_temp` n'a donc rien a masquer chez elles. Mais un SECOND
-- vecteur existe: un schema nomme EXPLICITEMENT avant `pg_catalog` peut
-- masquer une fonction integree — mesure: `txid_current()` a rendu 1 au lieu
-- de l'identifiant reel. Ce vecteur exige `CREATE` sur la base, qu'AUCUN role
-- d'autorite ne detient (mesure: `has_database_privilege(..., 'CREATE') = f`
-- pour les sept roles canoniques).
--
-- On epingle quand meme. Un contexte d'execution qui depend de deux mesures
-- favorables n'est pas une garantie: c'est une coincidence qu'on documente.
--
-- `pg_temp` EST NOMME EXPLICITEMENT, ET EN DERNIER. C'est contre-intuitif et
-- c'est mesure: OMETTRE `pg_temp` NE LE FERME PAS, il est alors consulte EN
-- PREMIER pour les relations. Table mesuree le 28/08 sur la garde reelle:
--
--   search_path = pg_catalog, public            -> UPDATE 1   (contourne)
--   search_path = pg_catalog, public, pg_temp   -> REFUSE     (la garde tient)
--   search_path = pg_temp, pg_catalog, public   -> UPDATE 1   (contourne)
--
-- Seule la troisieme position ferme le vecteur. Une premiere version de ce
-- correctif ecrivait « pg_catalog, public » en croyant fermer par omission:
-- elle ne fermait rien.
alter function forbid_seal_metadata_mutation()      set search_path = pg_catalog, public, pg_temp;
alter function forbid_activation_mutation()         set search_path = pg_catalog, public, pg_temp;
alter function forbid_approved_settings_mutation()  set search_path = pg_catalog, public, pg_temp;
alter function forbid_control_plane_mutation()      set search_path = pg_catalog, public, pg_temp;
alter function forbid_finalization_intent_mutation() set search_path = pg_catalog, public, pg_temp;

commit;
