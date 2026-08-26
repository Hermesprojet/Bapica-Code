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
grant execute on function normative_grant_descendants(uuid)
  to eurostruct_normative_writer, normative_governance;

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
revoke create on schema public
  from eurostruct_normative_writer, eurostruct_normative_bootstrap;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
