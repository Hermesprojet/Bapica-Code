-- =====================================================================
-- 0012 — FILIATION DES DELEGATIONS ET REVOCATION TRANSITIVE (6.3c)
-- =====================================================================
--
-- CE QUI EST ABANDONNE ICI, ET POURQUOI
-- --------------------------------------
-- 6.3c avait consigne une decision: revocation NON TRANSITIVE, au motif qu'une
-- cascade retroactive invaliderait des signatures regulieres au moment ou elles
-- ont ete apposees. L'argument etait juste sur la CONSERVATION DES PREUVES, et
-- faux sur le POUVOIR.
--
-- Il confondait deux choses que la retention decennale ne confond pas:
--
--   * ce qui a ete SIGNE reste signe, lisible et explicable — c'est deja
--     garanti par l'immuabilite des tables, et rien ici n'y touche;
--   * ce qui reste UTILISABLE apres le retrait d'une autorite est une autre
--     question, et la reponse « tout ce qu'elle avait delegue » est
--     indefendable. Retirer son habilitation a un administrateur en laissant
--     vivre les pouvoirs qu'il a distribues ne retire rien du tout.
--
-- Et la contrepartie promise — une « vue de couverture » qui enumere la
-- descendance a traiter — n'etait pas implementable: aucune colonne ne reliait
-- un octroi a celui sous lequel il avait ete consenti. `granted_by` nomme la
-- PERSONNE, pas l'OCTROI. Une personne peut detenir plusieurs habilitations de
-- portees differentes; savoir « qui » a consenti ne dit pas « au titre de
-- quoi ». La provenance manquait, et sans elle la non-transitivite n'etait pas
-- un choix mais une impossibilite deguisee en decision.
--
-- CE QUE CETTE MIGRATION POSE
-- ----------------------------
--   1. `parent_grant_id` — la provenance EXPLICITE. Tout octroi delegue
--      reference l'habilitation precise au titre de laquelle il a ete consenti.
--   2. `expires_at` — une duree, bornee par celle du parent.
--   3. `normative_grant_is_effective()` — un octroi n'est efficace que si LUI
--      et TOUS SES ANCETRES sont non revoques et non expires.
--   4. Le consentant doit DETENIR le parent qu'il invoque, et la portee de
--      l'enfant doit etre incluse dans celle du parent sur les quatre axes.
--
-- LES CYCLES SONT STRUCTURELLEMENT IMPOSSIBLES, et cela merite d'etre dit
-- plutot que teste dans le vide: `parent_grant_id` ne peut designer qu'une
-- ligne DEJA EXISTANTE, et ces tables sont en ajout seul — aucun `UPDATE` n'est
-- accorde a quiconque. Le graphe de filiation est donc un DAG par
-- construction. Ce qui reste possible, et qui n'est pas un cycle, c'est que
-- A delegue a B puis B delegue a A: deux octrois distincts, chacun evalue
-- contre SA propre chaine. Aucun pouvoir supplementaire n'en nait, et un test
-- l'etablit plutot que de le supposer.
--
-- COMPATIBILITE AVEC L'EXISTANT. Les octrois deja en base n'ont pas de parent.
-- La colonne est donc NULLABLE, et la contrainte ne porte que sur les LIGNES
-- NOUVELLES: un `check` valide a l'insertion aurait refuse la migration
-- elle-meme sur toute base portant deja des donnees. La regle est donc dans le
-- declencheur, qui ne voit que les nouvelles lignes — et `NOT VALID` n'aurait
-- rien apporte de plus qu'une contrainte qu'on n'ose pas valider.
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
-- 1. LA PROVENANCE ET LA DUREE
-- ---------------------------------------------------------------------
alter table normative_authorisation_grants
  add column if not exists parent_grant_id uuid
    references normative_authorisation_grants(id) on delete restrict,
  add column if not exists expires_at timestamptz;

comment on column normative_authorisation_grants.parent_grant_id is
  'L''habilitation PRECISE au titre de laquelle cet octroi a ete consenti. '
  'NULL pour une racine (origin = bootstrap) et pour les octrois anterieurs a '
  '0012. `granted_by` nomme la personne; celle-ci nomme le POUVOIR — une '
  'personne peut en detenir plusieurs, de portees differentes.';

comment on column normative_authorisation_grants.expires_at is
  'Fin de validite. NULL = sans terme. Un enfant ne peut pas depasser le terme '
  'de son parent: une delegation ne cree pas de duree que le delegant n''avait '
  'pas.';

-- L'index sert la remontee de chaine de `normative_grant_is_effective` et la
-- descente de `normative_grant_descendants`. Sans lui, chaque resolution
-- d'habilitation balaierait la table entiere par niveau de profondeur.
create index if not exists normative_grants_parent_idx
  on normative_authorisation_grants (parent_grant_id)
  where parent_grant_id is not null;


-- ---------------------------------------------------------------------
-- 2. L'EFFICACITE — transitive, et non plus locale
-- ---------------------------------------------------------------------
-- `normative_grant_is_active()` reste ce qu'elle etait: « cet octroi porte-t-il
-- une revocation ? ». Elle sert les messages et l'audit, ou l'on veut savoir ce
-- qui a ete fait a CET octroi. Elle ne decide plus de rien.
--
-- `normative_grant_is_effective()` decide. Elle remonte la chaine de filiation
-- et refuse des qu'un ancetre est revoque ou expire. C'est la difference entre
-- « on ne lui a rien retire » et « il peut encore s'en servir ».
create or replace function normative_grant_is_effective(p_grant_id uuid)
returns boolean
language sql
stable
set search_path = public, pg_temp
as $$
  with recursive chaine as (
    select g.id, g.parent_grant_id, g.expires_at
      from normative_authorisation_grants g
     where g.id = p_grant_id
    union all
    -- REMONTEE, pas descente: on cherche les ancetres. La recursion termine
    -- parce que `parent_grant_id` ne designe que des lignes anterieures et que
    -- ces tables n'acceptent aucun UPDATE — le graphe est un DAG.
    select a.id, a.parent_grant_id, a.expires_at
      from normative_authorisation_grants a
      join chaine c on a.id = c.parent_grant_id
  )
  select exists (select 1 from chaine)
     and not exists (
       select 1 from chaine c
        where exists (select 1 from normative_authorisation_revocations r
                       where r.grant_id = c.id)
           or (c.expires_at is not null and c.expires_at <= now()));
$$;

alter function normative_grant_is_effective(uuid)
  owner to eurostruct_normative_writer;
revoke all on function normative_grant_is_effective(uuid) from public;
grant execute on function normative_grant_is_effective(uuid)
  to eurostruct_normative_writer, eurostruct_normative_bootstrap;

comment on function normative_grant_is_effective is
  'Un octroi est EFFICACE si lui et TOUS ses ancetres sont non revoques et non '
  'expires. Revoquer une habilitation eteint donc ce qu''elle a delegue. Les '
  'lignes deja signees, elles, restent intactes: l''immuabilite des tables ne '
  'depend pas de cette fonction.';


-- La descendance ENCORE EFFICACE d'un octroi. Elle rend la question « que
-- perd-on en revoquant ceci ? » repondable AVANT de le faire — c'est la « vue
-- de couverture » que 6.3c promettait sans pouvoir la construire.
create or replace function normative_grant_descendants(p_grant_id uuid)
returns setof normative_authorisation_grants
language sql
stable
set search_path = public, pg_temp
as $$
  with recursive descendance as (
    select g.* from normative_authorisation_grants g
     where g.parent_grant_id = p_grant_id
    union all
    select g.* from normative_authorisation_grants g
      join descendance d on g.parent_grant_id = d.id
  )
  select * from descendance;
$$;

alter function normative_grant_descendants(uuid)
  owner to eurostruct_normative_writer;
revoke all on function normative_grant_descendants(uuid) from public;
-- PAS A `normative_governance`, ET C'EST UNE CORRECTION MESUREE.
--
-- Une garantie posee bien avant 6.3c interdit a `public`, `authenticated`,
-- `normative_backend` ET `normative_governance` d'executer QUELQUE fonction
-- « normative » que ce soit — `05_normative_confirmation.sql` la verifie sur
-- toutes les fonctions dont le nom contient « normative ». La premiere
-- ecriture de 0012 accordait celle-ci a la gouvernance « parce que c'est une
-- question de gouvernance », et faisait donc echouer cette garantie.
--
-- La gouvernance n'en a pas besoin: elle detient deja SELECT sur les octrois
-- et peut calculer la descendance elle-meme. Accorder une fonction du
-- sous-systeme d'autorite a un role applicatif pour lui epargner une requete
-- est exactement ce que la garantie existe pour empecher.
grant execute on function normative_grant_descendants(uuid)
  to eurostruct_normative_writer;

comment on function normative_grant_descendants is
  'Tout ce qui a ete delegue SOUS cet octroi, a toute profondeur. Repond a '
  '« que perd-on en revoquant ceci ? » avant de le revoquer.';


-- ---------------------------------------------------------------------
-- 3. LA REGLE DE FILIATION, DANS LE DECLENCHEUR D'OCTROI
-- ---------------------------------------------------------------------
-- Elle s'insere entre l'auto-attribution (deja refusee) et la consommation de
-- l'habilitation du consentant. Elle ne remplace pas cette consommation: elle
-- la PRECISE. Avant 0012, le consentant devait detenir « une » habilitation
-- couvrant la portee; desormais il doit nommer LAQUELLE, et c'est celle-la qui
-- borne la portee et la duree de l'enfant.
create or replace function check_normative_grant_lineage() returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := auth.uid();
  parent normative_authorisation_grants;
begin
  -- L'AMORCAGE EST UNE RACINE. Il n'a pas de parent, et exiger qu'il en ait un
  -- rendrait la chaine impossible a ouvrir.
  if new.origin = 'bootstrap' then
    if new.parent_grant_id is not null then
      raise exception
        'un amorcage est une RACINE: il ne peut pas referencer un parent.'
        using errcode = 'check_violation';
    end if;
    return new;
  end if;

  if new.parent_grant_id is null then
    raise exception
      'octroi refuse: toute delegation doit nommer l''habilitation au titre '
      'de laquelle elle est consentie (parent_grant_id). « Qui » a consenti '
      'ne dit pas « au titre de quoi »: un consentant peut detenir plusieurs '
      'habilitations de portees differentes.'
      using errcode = 'not_null_violation';
  end if;

  select * into parent from normative_authorisation_grants
   where id = new.parent_grant_id;
  if not found then
    raise exception 'habilitation parente % introuvable', new.parent_grant_id
      using errcode = 'foreign_key_violation';
  end if;

  -- LE CONSENTANT DOIT DETENIR LE PARENT. Sans ce controle, n'importe qui
  -- pourrait invoquer l'habilitation d'un autre pour lui faire porter une
  -- delegation qu'il n'a pas consentie.
  if parent.grantee_id is distinct from acteur then
    raise exception
      'octroi refuse: l''habilitation % appartient a %, pas a %. On ne delegue '
      'que ce que l''on detient.',
      parent.id, coalesce(parent.grantee_id::text, '(racine)'), acteur
      using errcode = 'insufficient_privilege';
  end if;

  -- LE PARENT DOIT ETRE EFFICACE, chaine comprise. Un parent dont l'ancetre a
  -- ete revoque ne delegue plus rien: c'est tout l'objet de 0012.
  if not normative_grant_is_effective(parent.id) then
    raise exception
      'octroi refuse: l''habilitation % n''est plus efficace — elle-meme ou '
      'l''un de ses ancetres a ete revoque ou a expire.', parent.id
      using errcode = 'insufficient_privilege';
  end if;

  -- LA PERMISSION NE S'ELEVE PAS. Un pouvoir de verification ne fabrique pas
  -- un pouvoir d'administration.
  if parent.permission <> 'can_manage_normative_authorisations' then
    raise exception
      'octroi refuse: l''habilitation % porte « % », qui ne permet pas de '
      'deleguer. Seule « can_manage_normative_authorisations » le permet.',
      parent.id, parent.permission
      using errcode = 'insufficient_privilege';
  end if;

  -- LA PORTEE DE L'ENFANT EST INCLUSE DANS CELLE DU PARENT, SUR LES QUATRE
  -- AXES. Un axe NULL chez le parent vaut « toutes les valeurs »; un axe NULL
  -- chez l'enfant alors que le parent est borne serait un ELARGISSEMENT, et
  -- c'est ce que la seconde moitie de chaque condition refuse.
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
      'celle de l''habilitation % (%/%/%/%). Une delegation ne cree pas de '
      'portee que le delegant n''avait pas.',
      coalesce(new.country_code::text, '*'), coalesce(new.standard_family, '*'),
      coalesce(new.part, '*'), coalesce(new.edition, '*'), parent.id,
      coalesce(parent.country_code::text, '*'),
      coalesce(parent.standard_family, '*'),
      coalesce(parent.part, '*'), coalesce(parent.edition, '*')
      using errcode = 'insufficient_privilege';
  end if;

  -- LA DUREE NE DEPASSE PAS CELLE DU PARENT. Un parent sans terme n'en impose
  -- aucun; un parent avec terme le transmet comme plafond. Un enfant SANS
  -- terme sous un parent qui en a un serait une delegation perpetuelle issue
  -- d'un pouvoir temporaire: on la refuse plutot que de la tronquer en
  -- silence, parce que tronquer changerait ce que le consentant croit signer.
  if parent.expires_at is not null
     and (new.expires_at is null or new.expires_at > parent.expires_at) then
    raise exception
      'octroi refuse: l''habilitation % expire le %, la delegation demandee '
      '%. Une delegation ne cree pas de duree que le delegant n''avait pas.',
      parent.id, parent.expires_at,
      coalesce(new.expires_at::text, 'jamais')
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;

alter function check_normative_grant_lineage()
  owner to eurostruct_normative_writer;
revoke all on function check_normative_grant_lineage() from public;

-- L'ORDRE DES DECLENCHEURS EST ALPHABETIQUE EN POSTGRESQL, et il compte:
-- `normative_grants_are_checked` (0010) pose `new.granted_by := auth.uid()` et
-- refuse l'auto-attribution. Le nom ci-dessous le suit alphabetiquement, si
-- bien que la filiation s'evalue APRES que l'acteur a ete etabli — sans quoi
-- elle comparerait le parent a une valeur que l'appelant aurait fournie.
create trigger normative_grants_lineage_is_checked
  before insert on normative_authorisation_grants
  for each row execute function check_normative_grant_lineage();


-- ---------------------------------------------------------------------
-- 4. LA RESOLUTION LIT DESORMAIS L'EFFICACITE
-- ---------------------------------------------------------------------
-- MEME CORPS QUE 0010, un seul mot change: `normative_grant_is_active` devient
-- `normative_grant_is_effective`. C'est ce mot qui rend la revocation
-- transitive — le reste du modele n'avait pas besoin de bouger, et le faire
-- bouger aurait rendu la revue impossible.
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
set search_path = public, pg_temp
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
       and normative_grant_is_effective(g.id)
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
      'autorisation ambigue: % octrois efficaces de meme specificite couvrent '
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
     and normative_grant_is_effective(g.id)
   order by (g.country_code    is not null)::int
          + (g.standard_family is not null)::int
          + (g.part            is not null)::int
          + (g.edition         is not null)::int desc
   limit 1;
  return retenu;
end;
$$;

alter function resolve_normative_authorisation(
    uuid, normative_permission, country_code, text, text, text)
  owner to eurostruct_normative_writer;


-- LA CONSOMMATION RELIT L'EFFICACITE, elle aussi. Sans ce changement, une
-- revocation d'ancetre survenue pendant l'operation resterait invisible: le
-- verrou aurait servi a attendre, pas a decider.
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
  a uuid;
begin
  habilitation := resolve_normative_authorisation(
    p_actor, p_permission, p_country, p_family, p_part, p_edition
  );
  if habilitation.id is null then
    return habilitation;
  end if;

  -- VERROU PARTAGE SUR TOUTE LA CHAINE, et non sur le seul octroi retenu. Une
  -- revocation vise un ANCETRE aussi bien que l'octroi lui-meme; ne verrouiller
  -- que le dernier maillon laisserait la revocation d'un ancetre se glisser
  -- entre la resolution et l'ecriture. L'ordre de prise est celui des
  -- identifiants, pour que deux consommations concurrentes ne s'interbloquent
  -- pas en prenant les memes verrous dans deux ordres differents.
  for a in
    with recursive chaine as (
      select g.id, g.parent_grant_id from normative_authorisation_grants g
       where g.id = habilitation.id
      union all
      select p.id, p.parent_grant_id from normative_authorisation_grants p
        join chaine c on p.id = c.parent_grant_id
    )
    select id from chaine order by id
  loop
    perform pg_advisory_xact_lock_shared(
      hashtext('eurostruct.normative.grantrow:' || a::text));
  end loop;

  if not normative_grant_is_effective(habilitation.id) then
    raise exception
      'operation refusee: l''habilitation % n''etait plus efficace au moment '
      'de s''en servir — elle-meme ou l''un de ses ancetres a ete revoque ou '
      'a expire pendant l''operation.', habilitation.id
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
  'Resout une habilitation, verrouille TOUTE SA CHAINE en partage jusqu''au '
  'commit, et revalide son efficacite transitive. Le verrou seul n''est pas '
  'une garantie: c''est la relecture qui suit qui en fait une.';


-- ---------------------------------------------------------------------
-- LE DROIT DE CREATE REPART, comme il etait venu
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- POSTCONDITION DE 0012 — le catalogue, lu, et non les commandes, supposees
-- ---------------------------------------------------------------------
-- POURQUOI ELLE EXISTE. PostgreSQL 16 n'echoue pas sur un GRANT ou un REVOKE
-- emis sans le droit requis: il emet un WARNING et ne fait rien. `psql -v
-- ON_ERROR_STOP=1` ne s'arrete pas sur un WARNING. Chacun des huit
-- GRANT/REVOKE de cette migration pouvait donc etre sans effet, et la
-- migration se terminer « avec succes » en laissant la surface ouverte.
--
-- ELLE LIT `pg_proc.proacl`, PAS `has_function_privilege()`. Le proprietaire
-- d'une fonction repond « oui » a `has_function_privilege` meme quand AUCUN
-- octroi n'a ete pose — la propriete suffit. Poser la question ainsi rendrait
-- donc « tout va bien » sur une surface ou rien n'a ete accorde ni revoque.
-- Les ACL et les lignes de catalogue, elles, disent ce qui EST.
--
-- ELLE DECRIT L'ETAT A LA FIN DE 0012, ET PAS L'ETAT FINAL. `0013` ajoutera
-- `eurostruct_authority_backend` sur `normative_grant_is_effective`. Une
-- postcondition par migration decrit CE QUE SA MIGRATION A FAIT; anticiper la
-- suivante la ferait echouer sur une base correcte, et masquerait ensuite
-- l'octroi qu'elle etait censee surveiller.
--
-- CHAQUE ECART PORTE UN IDENTIFIANT STABLE. Un test qui reconnait une mise a
-- mort sur une phrase reconnait une phrase: elle se reformule, et le test
-- cesse de distinguer un refus attendu d'une panne quelconque.
create or replace function assert_0012_lineage_surface() returns void
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  r record;
  ecarts text[] := array[]::text[];
  -- LE NOM SUFFIT A DESIGNER, ET IL EN DIT PLUS QU'UNE SIGNATURE.
  --
  -- Une premiere version comparait `pg_get_function_identity_arguments()` a
  -- une signature ecrite a la main. Elle rendait « fonction absente » pour
  -- QUATRE fonctions bien presentes: cette primitive rend les NOMS des
  -- parametres (« p_grant_id uuid »), pas seulement leurs types. Un
  -- diagnostic faux sur une base correcte est pire qu'aucun diagnostic.
  --
  -- On exige donc EXACTEMENT UNE fonction de ce nom dans `public`. C'est plus
  -- simple, et plus strict: une surcharge introduite par ailleurs — qui
  -- porterait ses propres ACL, invisibles a un controle vise sur une seule
  -- signature — devient un ecart nomme.
  attendus text[][] := array[
    -- fonction                         | secdef | roles EXECUTE
    ['normative_grant_is_effective',    'false',
     'eurostruct_normative_writer,eurostruct_normative_bootstrap'],
    ['normative_grant_descendants',     'false',
     'eurostruct_normative_writer'],
    ['check_normative_grant_lineage',   'true',
     'eurostruct_normative_writer'],
    ['resolve_normative_authorisation', 'false',
     'eurostruct_normative_writer'],
    ['consume_normative_authorisation', 'true',
     'eurostruct_normative_writer']
  ];
  i int; n_match int;
  nom text; secdef_attendu boolean; roles_attendus text[];
  f_oid oid; f_owner text; f_secdef boolean; f_cfg text[]; f_acl aclitem[];
  reels text[];
begin
  for i in 1 .. array_length(attendus, 1) loop
    nom := attendus[i][1];
    secdef_attendu := attendus[i][2]::boolean;
    roles_attendus := string_to_array(attendus[i][3], ',');

    select count(*) into n_match
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;

    if n_match = 0 then
      ecarts := ecarts || format(
        'AUTHORITY_0012_FUNCTION_MISSING: %s est absente du schema public',
        nom);
      continue;
    elsif n_match > 1 then
      ecarts := ecarts || format(
        'AUTHORITY_0012_FUNCTION_AMBIGUOUS: %s existe en %s exemplaires dans '
        'public; chacun porte ses propres ACL et ce controle n''en verrait '
        'qu''un', nom, n_match);
      continue;
    end if;

    select p.oid, pg_get_userbyid(p.proowner), p.prosecdef, p.proconfig, p.proacl
      into f_oid, f_owner, f_secdef, f_cfg, f_acl
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom;

    if f_owner <> 'eurostruct_normative_writer' then
      ecarts := ecarts || format(
        'AUTHORITY_0012_OWNER_MISMATCH: %s appartient a « %s », attendu '
        '« eurostruct_normative_writer »', nom, f_owner);
    end if;

    if f_secdef is distinct from secdef_attendu then
      ecarts := ecarts || format(
        'AUTHORITY_0012_SECURITY_DEFINER_MISMATCH: %s a prosecdef=%s, '
        'attendu %s', nom, f_secdef, secdef_attendu);
    end if;

    -- `search_path` FIXE. Absent, la fonction herite de celui de l'appelant,
    -- qui peut alors la detourner vers ses propres objets.
    if f_cfg is null
       or not exists (select 1 from unnest(f_cfg) c where c like 'search\_path=%')
    then
      ecarts := ecarts || format(
        'AUTHORITY_0012_SEARCH_PATH_UNPINNED: %s n''a pas de search_path fixe '
        'dans proconfig', nom);
    end if;

    -- `proacl` NULL signifie « droits par defaut »: PUBLIC execute. Un
    -- `revoke ... from public` sans effet laisse exactement cet etat.
    if f_acl is null then
      ecarts := ecarts || format(
        'AUTHORITY_0012_PUBLIC_EXECUTE: %s a proacl NULL — les droits par '
        'defaut s''appliquent, donc PUBLIC execute. Le REVOKE n''a pas pris',
        nom);
      continue;
    end if;

    if exists (select 1 from aclexplode(f_acl) a
                where a.grantee = 0 and a.privilege_type = 'EXECUTE') then
      ecarts := ecarts || format(
        'AUTHORITY_0012_PUBLIC_EXECUTE: %s accorde EXECUTE a PUBLIC', nom);
    end if;

    select coalesce(array_agg(g.rolname::text order by g.rolname), array[]::text[])
      into reels
      from aclexplode(f_acl) a
      join pg_roles g on g.oid = a.grantee
     where a.privilege_type = 'EXECUTE';

    -- EGALITE EXACTE, dans les deux sens. Un role en trop est une surface
    -- ouverte; un role en moins est un octroi qui n'a pas pris.
    if reels <> (select array_agg(x order by x) from unnest(roles_attendus) x) then
      ecarts := ecarts || format(
        'AUTHORITY_0012_EXECUTE_ACL_MISMATCH: %s accorde EXECUTE a {%s}, '
        'attendu {%s}', nom, array_to_string(reels, ','),
        array_to_string(roles_attendus, ','));
    end if;
  end loop;

  -- LE DECLENCHEUR DE FILIATION, PRESENT **ET** ACTIVE. `ALTER TABLE ...
  -- DISABLE TRIGGER` laisse la ligne dans `pg_trigger` avec `tgenabled='D'`:
  -- chercher seulement l'existence declarerait vert un declencheur eteint.
  if not exists (
    select 1 from pg_trigger t join pg_class c on c.oid = t.tgrelid
     where c.relname = 'normative_authorisation_grants'
       and t.tgname = 'normative_grants_lineage_is_checked'
       and not t.tgisinternal and t.tgenabled = 'O')
  then
    ecarts := ecarts || 'AUTHORITY_0012_TRIGGER_NOT_ENABLED: '
      'normative_grants_lineage_is_checked est absent ou desactive sur '
      'normative_authorisation_grants';
  end if;

  -- LA FILIATION EST UNE CLE ETRANGERE **VALIDEE**. `NOT VALID` laisserait
  -- passer les lignes deja presentes, et la colonne ne garantirait plus rien
  -- du passe qu'elle est censee decrire.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'normative_authorisation_grants'::regclass
       and conname = 'normative_authorisation_grants_parent_grant_id_fkey'
       and contype = 'f' and convalidated)
  then
    ecarts := ecarts || 'AUTHORITY_0012_FOREIGN_KEY_MISSING: '
      'la cle etrangere parent_grant_id est absente ou non validee';
  end if;

  -- LE DROIT DE CREATE EST REPARTI. Il a ete accorde en tete de migration
  -- pour poser des fonctions; le laisser serait laisser au writer de quoi
  -- fabriquer un objet dans `public` apres coup.
  for r in
    select unnest(array['eurostruct_normative_writer',
                        'eurostruct_normative_bootstrap']) as rolname
  loop
    if exists (select 1 from pg_namespace n, aclexplode(n.nspacl) a
                where n.nspname = 'public'
                  and a.grantee = r.rolname::regrole::oid
                  and a.privilege_type = 'CREATE') then
      ecarts := ecarts || format(
        'AUTHORITY_0012_SCHEMA_CREATE_RETAINED: « %s » conserve CREATE sur le '
        'schema public', r.rolname);
    end if;
  end loop;

  if array_length(ecarts, 1) > 0 then
    raise exception
      'AUTHORITY_0012_POSTCONDITION_FAILED: la surface posee par 0012 n''est '
      'pas celle qui a ete demandee — %',
      array_to_string(ecarts, E'\n  - ')
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

alter function assert_0012_lineage_surface()
  owner to eurostruct_normative_writer;
revoke all on function assert_0012_lineage_surface() from public;
grant execute on function assert_0012_lineage_surface()
  to eurostruct_normative_writer, eurostruct_deployment;

comment on function assert_0012_lineage_surface is
  'Postcondition de 0012: confronte le CATALOGUE a ce que la migration a '
  'demande. Lit proacl et pg_trigger, jamais has_function_privilege() seul — '
  'la propriete rendrait la reponse trompeuse. Chaque ecart porte un '
  'identifiant stable AUTHORITY_0012_*.';


revoke create on schema public
  from eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- LA POSTCONDITION EST APPELEE PAR LA MIGRATION, apres TOUS les changements
-- de catalogue et AVANT l'inscription au registre. Une migration refusee ne
-- doit laisser aucune ligne disant qu'elle a ete appliquee.
select assert_0012_lineage_surface();

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
