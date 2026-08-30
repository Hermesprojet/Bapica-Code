-- 0018 — L'ATELIER: DES PROJETS REELS, ET DES CALCULS QUI SURVIVENT AU F5
--
-- CE QUI MANQUAIT
-- ----------------
-- Tout le sous-systeme normatif existait — habilitations, quatre-yeux,
-- confirmations, effet sur le mode strict — et le produit, lui, envoyait
-- `project_id: "DEMO-001"` en dur. Un calcul lance depuis l'ecran vivait dans
-- la reponse HTTP et mourait avec elle: rechargement, plus rien. Les tables
-- `projects`, `calculations`, `results` et `verifications` etaient ecrites
-- depuis 0001 et n'avaient jamais recu une ligne par le chemin produit.
--
-- CE QUE CETTE MIGRATION AJOUTE, ET CE QU'ELLE N'AJOUTE PAS
-- ----------------------------------------------------------
-- Elle n'ajoute AUCUNE table. Les quatre existent, avec leur cloisonnement
-- `org_id`, leur RLS et leur `force row level security`. Elle ajoute:
--
--   * UNE colonne, `calculations.request`: les entrees exactes. `inputs_hash`
--     etait la depuis 0001 — une empreinte des entrees, sans les entrees. On
--     ne rouvre pas un calcul avec une empreinte. `projects.ndp_as_of` et
--     `calculations.ndp_snapshot` existaient deja depuis 0004, et ne sont pas
--     redoublees;
--   * `project_backend_actor()`, l'identite de l'atelier;
--   * des politiques RLS pour le seul role qui execute les primitives;
--   * cinq primitives SECURITY DEFINER, une par geste du parcours.
--
-- POURQUOI DES PRIMITIVES ET PAS DU SQL DEPUIS L'APPLICATION
-- ------------------------------------------------------------
-- La meme raison qu'a 0014 et 0017: `eurostruct_authority_backend` n'a aucun
-- privilege de table, et c'est la seule facon de garantir que l'acteur est
-- DERIVE de la session au lieu d'etre fourni. Une application qui ecrirait
-- `insert into projects (org_id, created_by) values ($1, $2)` croirait sur
-- parole les deux valeurs qui decident du cloisonnement.
--
-- AUCUN `org_id` NE VIENT DU CLIENT SANS CONTROLE. Quand l'appelant en nomme
-- un, il est confronte a `organization_members`; quand il n'en nomme pas, il
-- est DERIVE des appartenances. Dans les deux cas la reponse a « de quelle
-- organisation s'agit-il » sort de la base, jamais du corps de la requete.
--
-- L'ATOMICITE EST DANS LA PRIMITIVE, PAS DANS L'APPELANT
-- -------------------------------------------------------
-- `project_calculation_record()` ecrit le calcul, son resultat, son journal et
-- ses verifications en UNE instruction. Un appelant qui enchainerait quatre
-- ordres laisserait, sur incident reseau au troisieme, un calcul « reussi »
-- sans verifications — c'est-a-dire un calcul dont personne ne sait s'il
-- passe. Le cas est courant et silencieux: il ne se voit qu'a la relecture.
--
-- UN REFUS EST ENREGISTRE COMME REFUS
-- -------------------------------------
-- `status = 'refused'` avec `refusal` renseigne — la contrainte de 0001
-- l'exige deja. Le mode strict qui refuse faute de parametre confirme n'est
-- pas un echec technique: c'est une reponse du moteur, et l'historique doit
-- la porter telle quelle. L'ecraser en `failed`, ou pire l'omettre, ferait
-- disparaitre de l'historique exactement les calculs qu'un audit cherche.
--
-- CE QUE CETTE MIGRATION NE PRETEND PAS
-- ---------------------------------------
-- Rien ici ne rend un livrable signable. `validations` et `deliverables` ne
-- sont pas touchees: aucune primitive n'y ecrit, et aucun statut n'annonce
-- « final ». Un calcul enregistre est un calcul enregistre.

begin;

-- LE DROIT DE CREER, LE TEMPS DE CETTE MIGRATION.
--
-- `alter function ... owner to eurostruct_normative_writer` EXIGE que le
-- futur proprietaire ait CREATE sur le schema — sinon « permission denied for
-- schema public », mesure du jour. 0017 le lui a repris, et c'est voulu: un
-- role qui detient INSERT sur les tables d'autorite ne doit pas pouvoir creer
-- d'objets entre deux migrations. On le rouvre ici, et la section 7 le
-- reprend, sous le donneur endosse.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LA SEULE COLONNE QUI MANQUAIT POUR ROUVRIR
-- ---------------------------------------------------------------------
-- CE QUI EXISTE DEJA, ET QUI N'EST PAS REDOUBLE. La premiere redaction de
-- cette migration ajoutait `projects.reference_date` et
-- `calculations.ndp_state`. Les deux existaient sous d'autres noms depuis
-- 0004: `projects.ndp_as_of` — « date de reference du projet pour resoudre
-- l'edition d'Annexe Nationale en vigueur » — et `calculations.ndp_snapshot`
-- — « copie figee des parametres nationaux utilises ». Deux colonnes pour la
-- meme chose se contredisent au premier ecran qui lit la mauvaise.
--
-- `request` MANQUE VRAIMENT, ET `inputs_hash` NE LE REMPLACE PAS. Une
-- empreinte permet de dire « ce sont les memes entrees », jamais « voici les
-- entrees ». Rouvrir un calcul sauvegarde — le geste le plus frequent de
-- l'ingenieur — exige les entrees elles-memes.
alter table calculations add column if not exists request jsonb;

comment on column calculations.request is
  'Les entrees EXACTES recues par le moteur. `inputs_hash` en est l''empreinte '
  'et ne permet pas de rouvrir le calcul; `ndp_snapshot` porte l''etat du '
  'referentiel au moment du calcul, et `preflight` le rapport de prevol.';


-- ---------------------------------------------------------------------
-- 2. L'IDENTITE DE L'ATELIER
-- ---------------------------------------------------------------------
-- ELLE NE DEFINIT AUCUNE REGLE NOUVELLE, et c'est le point. Elle delegue a
-- `normative_authenticated_actor_or_null()`, qui exige que la SESSION atteigne
-- `eurostruct_authority_backend` avant de croire le moindre parametre de
-- session. Reecrire ce controle ici donnerait deux portes, dont la plus faible
-- finirait par decider.
--
-- ELLE NE LEVE PAS, contrairement a la variante normative. Une fonction qui
-- leve dans une expression de politique RLS ferait echouer en ERREUR toute
-- requete d'une session ordinaire, la ou RLS doit rendre ZERO LIGNE. Sur une
-- base sans backend declare, elle rend NULL — et aucune appartenance ne
-- correspond a NULL, donc rien n'est visible. Fail-closed, sans bruit.
create or replace function project_backend_actor() returns uuid
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
begin
  if not normative_authentication_configured() then
    return null;
  end if;
  return normative_authenticated_actor_or_null();
end;
$$;

alter function project_backend_actor() owner to eurostruct_normative_writer;
revoke all on function project_backend_actor() from public;
grant execute on function project_backend_actor()
  to eurostruct_normative_writer;

comment on function project_backend_actor is
  'L''acteur de l''atelier: celui que le backend authentifie a pose, et NULL '
  'partout ailleurs. Delegue le controle de session au sous-systeme normatif '
  'plutot que de le reecrire.';


-- LES APPARTENANCES, VUES DE L'ATELIER.
--
-- `is_org_member()` de 0002 lit `auth.uid()`, c'est-a-dire le GUC que Supabase
-- pose pour un acces direct depuis le navigateur. Notre backend n'emprunte pas
-- ce chemin: il verifie le JWT lui-meme puis pose `eurostruct.actor_id`. Les
-- deux coexistent, et aucune n'est reecrite.
create or replace function project_actor_is_member(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor());
$$;

create or replace function project_actor_can_write(target_org uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from organization_members m
     where m.org_id = target_org
       and m.user_id = project_backend_actor()
       and m.role = any(array['owner', 'admin', 'engineer',
                              'validating_engineer']::org_role[]));
$$;

alter function project_actor_is_member(uuid) owner to eurostruct_normative_writer;
alter function project_actor_can_write(uuid) owner to eurostruct_normative_writer;
revoke all on function project_actor_is_member(uuid) from public;
revoke all on function project_actor_can_write(uuid) from public;
grant execute on function project_actor_is_member(uuid),
                          project_actor_can_write(uuid)
  to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 3. LES PRIVILEGES DE TABLE, ET LES POLITIQUES QUI LES BORNENT
-- ---------------------------------------------------------------------
-- Le proprietaire des primitives doit pouvoir ecrire; RLS decide QUOI.
-- `force row level security` est actif sur ces tables depuis 0002, si bien que
-- meme le proprietaire de la table y est soumis: la frontiere est la politique,
-- pas la politesse de l'appelant.
grant select, insert on projects, structural_models, calculations,
                        results, verifications
  to eurostruct_normative_writer;
grant select on organizations, organization_members,
                national_annexes, engine_versions
  to eurostruct_normative_writer;
-- `engine_versions` recoit un enregistrement par version de moteur observee.
-- Sans INSERT, le premier calcul d'une version nouvelle echouerait sur une
-- cle etrangere — et le produit refuserait de sauvegarder un calcul juste.
grant insert on engine_versions to eurostruct_normative_writer;

-- LES POLITIQUES DE 0002 S'APPLIQUENT A `PUBLIC`, DONC AUSSI A CE ROLE-LA.
--
-- Mesure du jour: « permission denied for function can_write ». PostgreSQL
-- evalue TOUTES les politiques permissives applicables au role courant, et
-- celles de 0002 n'ont pas de clause `to` — elles visent donc PUBLIC. Le
-- writer, en les evaluant, appelle `can_write()` et `is_org_member()`, sur
-- lesquelles il n'a aucun droit: il recoit une ERREUR, la ou RLS devait
-- rendre des lignes.
--
-- ON LUI OUVRE DONC CES TROIS FONCTIONS, ET CELA N'ELARGIT RIEN. Elles lisent
-- `auth.uid()`, c'est-a-dire le GUC que Supabase pose pour un acces direct
-- depuis le navigateur. Notre backend ne le pose jamais: elles rendent `false`
-- pour lui, systematiquement. Ce qui le laisse passer, ce sont les politiques
-- ci-dessous, et elles seules — les politiques permissives se combinent par
-- OU, si bien qu'un `false` constant n'ouvre aucune ligne.
--
-- L'ALTERNATIVE — restreindre les politiques de 0002 a `authenticated` —
-- changerait le comportement d'un chemin que ce lot ne touche pas, pour
-- resoudre un probleme de droit d'execution.
grant execute on function public.is_org_member(uuid),
                          public.has_org_role(uuid, org_role[]),
                          public.can_write(uuid)
  to eurostruct_normative_writer;

-- LES POLITIQUES DE L'ATELIER SONT NOMMEMENT ADRESSEES A CE ROLE-LA.
--
-- Sans clause `to`, elles s'appliqueraient a PUBLIC: toute session evaluant
-- `projects` devrait alors executer `project_actor_is_member()`, sur laquelle
-- elle n'a aucun droit — exactement le defaut ci-dessus, en miroir. Les
-- politiques de 0002 continuent donc de servir les memes roles qu'avant, sans
-- une ligne de changement.
do $$
declare
  t text;
begin
  foreach t in array array['projects', 'structural_models', 'calculations',
                           'results', 'verifications']
  loop
    execute format($f$
      create policy %1$I_atelier_read on %1$I
        for select to eurostruct_normative_writer
        using (project_actor_is_member(org_id));
    $f$, t);

    execute format($f$
      create policy %1$I_atelier_insert on %1$I
        for insert to eurostruct_normative_writer
        with check (project_actor_can_write(org_id));
    $f$, t);
  end loop;
end
$$;

create policy organizations_atelier_read on organizations
  for select to eurostruct_normative_writer
  using (project_actor_is_member(id));

-- LE REGISTRE DES ANNEXES N'EST PAS UNE DONNEE DE LOCATAIRE, et 0004 le dit
-- deja: sa politique est `using (true)`, mais adressee a `authenticated` — le
-- role d'un acces direct depuis le navigateur. Sans politique pour le writer,
-- la table lui rend ZERO LIGNE sans erreur, et `project_annexe_en_vigueur()`
-- conclut « aucune annexe en vigueur » pour un pays parfaitement couvert.
-- Mesure du jour: toute creation de projet belge refusait.
--
-- « une annexe belge vaut pour toutes les etudes belges »: la meme raison qui
-- rend les confirmations lisibles sans identite.
create policy national_annexes_atelier_read on national_annexes
  for select to eurostruct_normative_writer using (true);

-- `engine_versions` — LECTURE ET INSCRIPTION, pour la meme raison.
--
-- Ce n'est pas non plus une donnee de locataire: c'est le registre des
-- versions de moteur qui ont tourne ici. Un calcul reference la sienne par
-- cle etrangere, si bien qu'un moteur dont la version n'est pas encore
-- inscrite rendrait toute sauvegarde impossible — mesure du jour: « new row
-- violates row-level security policy for table engine_versions ».
--
-- L'INSCRIPTION EST UN CONSTAT, PAS UNE DECLARATION: la version vient de
-- `eurostruct_engine.version`, c'est-a-dire du code qui vient de calculer.
-- Refuser le calcul faute de ligne perdrait le seul enregistrement qui dit
-- quel code a produit ces nombres.
create policy engine_versions_atelier_read on engine_versions
  for select to eurostruct_normative_writer using (true);
create policy engine_versions_atelier_insert on engine_versions
  for insert to eurostruct_normative_writer with check (true);

-- LA POLITIQUE SUR `organization_members` NE PEUT PAS APPELER
-- `project_actor_is_member()`, ET LA PREMIERE REDACTION LE FAISAIT.
--
-- Mesure du jour: « stack depth limit exceeded », avec cent trames de
-- `project_actor_is_member` dans la pile. La fonction interroge
-- `organization_members`; la politique de cette table l'appelait; PostgreSQL
-- reevalue la politique a chaque lecture, et la recursion ne s'arrete jamais.
--
-- LA FORME CORRECTE EST AUSSI LA PLUS ETROITE: l'atelier n'a besoin de voir
-- que les appartenances de l'acteur lui-meme. Le predicat ne consulte donc
-- aucune autre table, ce qui ferme la recursion par construction plutot que
-- par prudence — et refuse au passage l'annuaire des collegues, qu'un
-- `project_actor_is_member(org_id)` aurait ouvert en entier.
create policy members_atelier_read on organization_members
  for select to eurostruct_normative_writer
  using (user_id = project_backend_actor());


-- ---------------------------------------------------------------------
-- 4. LE REFERENTIEL APPLICABLE — RESOLU PAR LA DATE, PAS PAR L'INSTANT
-- ---------------------------------------------------------------------
-- Y A-T-IL UNE ANNEXE NATIONALE EN VIGUEUR pour ce pays a cette date? 0004 a
-- remplace le « jeu de parametres » unique de 0001 par un registre versionne:
-- un projet ne pointe plus vers un jeu, il porte une DATE, et le moteur
-- resout l'edition en vigueur norme par norme. Cette fonction ne resout donc
-- rien: elle repond a la seule question qui bloque la creation — le pays
-- est-il couvert a cette date.
--
-- ELLE REND `false` PLUTOT QUE DE CHOISIR L'EDITION LA PLUS PROCHE. Prendre
-- « celle d'a cote » inventerait un referentiel — interdiction n° 2. Et la
-- resolution elle-meme n'appartient pas a cette migration: elle est dans le
-- moteur, avec les statuts de validation qui vont avec.
create or replace function project_annexe_en_vigueur(
  p_country country_code, p_as_of date)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from national_annexes a
     where a.country_code = p_country
       and a.effective_from <= p_as_of
       and (a.effective_to is null or a.effective_to > p_as_of));
$$;

alter function project_annexe_en_vigueur(country_code, date)
  owner to eurostruct_normative_writer;
revoke all on function project_annexe_en_vigueur(country_code, date) from public;
grant execute on function project_annexe_en_vigueur(country_code, date)
  to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 5. LES CINQ PRIMITIVES DU PARCOURS
-- ---------------------------------------------------------------------

-- 5.1 — LES PROJETS DE MON ORGANISATION.
--
-- « Mon » se lit dans `organization_members`, pas dans un parametre. Une
-- signature qui prendrait `p_org_id` laisserait lister les projets d'autrui a
-- qui devine un uuid; RLS l'en empecherait, mais la signature elle-meme aurait
-- deja dit que la question se pose.
create or replace function project_workspace_list()
returns table (
  project_id      uuid,
  org_id          uuid,
  org_name        text,
  name            text,
  reference       text,
  country         country_code,
  ndp_as_of       date,
  created_at      timestamptz,
  calculation_count bigint)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  return query
    select p.id, p.org_id, o.name, p.name, p.reference, p.country,
           p.ndp_as_of, p.created_at,
           (select count(*) from calculations c where c.project_id = p.id)
      from projects p
      join organizations o on o.id = p.org_id
     where p.archived_at is null
       and exists (select 1 from organization_members m
                    where m.org_id = p.org_id and m.user_id = acteur)
     order by p.created_at desc, p.id;
end;
$$;


-- 5.2 — CREER UN PROJET.
--
-- `p_org_id` est FACULTATIF et jamais cru: fourni, il est confronte aux
-- appartenances; absent, il est derive — et s'il y a plusieurs organisations
-- possibles, on refuse en les nommant plutot que d'en choisir une.
create or replace function project_workspace_create(
  p_name      text,
  p_reference text,
  p_country   country_code,
  p_as_of     date,
  p_org_id    uuid default null)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur    uuid := normative_authenticated_actor();
  org       uuid;
  candidats int;
  nouveau   uuid;
begin
  if coalesce(btrim(p_name), '') = '' then
    raise exception 'un projet sans nom ne se retrouve pas: nommer le projet.'
      using errcode = 'check_violation';
  end if;
  if p_as_of is null then
    raise exception
      'date de reference absente. Elle resout l''edition d''Annexe Nationale '
      'en vigueur; sans elle le referentiel dependrait de la date '
      'd''execution du calcul.'
      using errcode = 'check_violation';
  end if;

  if p_org_id is not null then
    -- FOURNI: ON LE CONFRONTE. Le refus ne distingue pas « organisation
    -- inexistante » de « vous n'en etes pas membre »: la difference est un
    -- oracle d'existence pour qui essaie des uuid.
    if not exists (select 1 from organization_members m
                    where m.org_id = p_org_id and m.user_id = acteur
                      and m.role = any(array['owner','admin','engineer',
                                             'validating_engineer']::org_role[]))
    then
      raise exception
        'organisation refusee: aucune appartenance en ecriture ne relie cet '
        'acteur a l''organisation demandee.'
        using errcode = 'insufficient_privilege';
    end if;
    org := p_org_id;
  else
    -- DEUX ORDRES, ET PAS UN `min(org_id)`: PostgreSQL 16 n'a pas d'agregat
    -- `min` sur `uuid` (mesure: « function min(uuid) does not exist »). Et
    -- meme s'il en avait un, prendre le plus petit uuid reviendrait a choisir
    -- une organisation au hasard quand il y en a plusieurs — exactement ce que
    -- la branche suivante refuse de faire.
    select count(*) into candidats
      from organization_members m
     where m.user_id = acteur
       and m.role = any(array['owner','admin','engineer',
                              'validating_engineer']::org_role[]);
    if candidats = 1 then
      select m.org_id into org
        from organization_members m
       where m.user_id = acteur
         and m.role = any(array['owner','admin','engineer',
                                'validating_engineer']::org_role[]);
    end if;
    if candidats = 0 then
      raise exception
        'aucune organisation: cet acteur n''appartient a aucune organisation '
        'avec un role d''ecriture. Un projet appartient a une organisation, et '
        'on n''en cree pas une au passage.'
        using errcode = 'insufficient_privilege';
    elsif candidats > 1 then
      raise exception
        'organisation ambigue: cet acteur appartient a % organisations. '
        'Nommer celle du projet plutot que d''en choisir une a sa place.',
        candidats
        using errcode = 'check_violation';
    end if;
  end if;

  if not project_annexe_en_vigueur(p_country, p_as_of) then
    raise exception
      'aucune annexe nationale en vigueur pour % au %. Le projet ne peut pas '
      'etre cree: il citerait un referentiel qui n''existe pas a cette date.',
      p_country, p_as_of
      using errcode = 'check_violation';
  end if;

  insert into projects (org_id, name, reference, country, ndp_as_of,
                        created_by)
  values (org, btrim(p_name), nullif(btrim(coalesce(p_reference, '')), ''),
          p_country, p_as_of, acteur)
  returning id into nouveau;

  -- LE MODELE PAR DEFAUT NAIT AVEC LE PROJET. `calculations.model_id` est
  -- `not null` depuis 0001 — un calcul appartient a un modele, pas a un
  -- projet directement. Le creer ici plutot qu'a la premiere sauvegarde evite
  -- que deux calculs simultanes en creent deux.
  insert into structural_models (org_id, project_id, created_by)
  values (org, nouveau, acteur);

  return nouveau;
end;
$$;


-- 5.3 — ENREGISTRER UN CALCUL, ENTIEREMENT OU PAS DU TOUT.
--
-- UNE SEULE INSTRUCTION POUR LES QUATRE TABLES. Un appelant qui enchainerait
-- `insert into calculations`, puis `results`, puis `verifications` laisserait,
-- sur incident au troisieme, un calcul « reussi » sans verification — donc un
-- calcul dont personne ne sait s'il passe, et que l'historique presente comme
-- abouti.
--
-- LE REFUS EST UN ETAT, PAS UNE ABSENCE. `p_status = 'refused'` exige
-- `p_refusal`; la contrainte `refused_calculation_states_why` de 0001 le
-- verifie, et on ne la contourne pas en degradant le statut.
create or replace function project_calculation_record(
  p_project_id     uuid,
  p_status         calculation_status,
  p_inputs_hash    text,
  p_strict_ndp     boolean,
  p_engine_version text,
  p_request        jsonb,
  p_ndp_snapshot   jsonb,
  p_progress_log   jsonb,
  p_refusal        jsonb,
  p_result         jsonb,
  p_journal        jsonb,
  p_verifications  jsonb)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur   uuid := normative_authenticated_actor();
  org      uuid;
  as_of    date;
  modele   uuid;
  moteur   uuid;
  calcul   uuid;
  resultat uuid;
  v        jsonb;
begin
  -- L'ORGANISATION SORT DU PROJET, ET LE PROJET DE L'APPARTENANCE. A aucun
  -- moment `org_id` ne traverse la frontiere depuis l'appelant.
  --
  -- `ndp_as_of` EST REPRIS DU PROJET, jamais de l'appelant: c'est la date de
  -- reference figee a la creation, et un calcul qui la choisirait lui-meme
  -- pourrait resoudre une autre edition d'Annexe Nationale que le reste du
  -- dossier.
  select p.org_id, p.ndp_as_of into org, as_of
    from projects p
   where p.id = p_project_id
     and exists (select 1 from organization_members m
                  where m.org_id = p.org_id and m.user_id = acteur);
  if org is null then
    raise exception
      'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;
  if not project_actor_can_write(org) then
    raise exception
      'role insuffisant: lire un projet et y enregistrer un calcul ne sont '
      'pas le meme droit.'
      using errcode = 'insufficient_privilege';
  end if;

  if p_status = 'refused' and p_refusal is null then
    raise exception
      'un refus doit dire pourquoi. Enregistrer « refused » sans motif '
      'rendrait l''historique illisible exactement la ou il compte.'
      using errcode = 'check_violation';
  end if;
  if p_request is null then
    raise exception
      'les entrees sont absentes: un calcul qu''on ne peut pas rouvrir n''est '
      'pas un calcul enregistre.'
      using errcode = 'check_violation';
  end if;

  select id into modele from structural_models
   where project_id = p_project_id order by version, name limit 1;
  if modele is null then
    insert into structural_models (org_id, project_id, created_by)
    values (org, p_project_id, acteur) returning id into modele;
  end if;

  -- LA VERSION DU MOTEUR EST ENREGISTREE TELLE QU'ELLE EST, pas choisie dans
  -- une liste. Une version inconnue de `engine_versions` est une version qui
  -- n'a jamais tourne ici; l'inscrire est un constat, et refuser le calcul
  -- pour cela perdrait le seul enregistrement qui dit quel code a produit ces
  -- nombres.
  select id into moteur from engine_versions where version = p_engine_version;
  if moteur is null then
    insert into engine_versions (version, released_at)
    values (p_engine_version, now())
    on conflict (version) do nothing
    returning id into moteur;
    if moteur is null then
      select id into moteur from engine_versions where version = p_engine_version;
    end if;
  end if;

  insert into calculations (org_id, project_id, model_id, engine_version_id,
                            status, inputs_hash, strict_ndp, refusal,
                            progress_log, request, ndp_as_of, ndp_snapshot,
                            requested_by, started_at, finished_at)
  values (org, p_project_id, modele, moteur, p_status, p_inputs_hash,
          coalesce(p_strict_ndp, true), p_refusal,
          coalesce(p_progress_log, '[]'::jsonb), p_request, as_of,
          coalesce(p_ndp_snapshot, '{}'::jsonb),
          acteur, now(), now())
  returning id into calcul;

  -- UN REFUS N'A NI RESULTAT NI VERIFICATION, et c'est exact: le moteur n'a
  -- rien conclu. La ligne de calcul, elle, existe et porte son motif.
  if p_result is not null then
    insert into results (org_id, calculation_id, payload, journal)
    values (org, calcul, p_result, coalesce(p_journal, '[]'::jsonb))
    returning id into resultat;

    if p_verifications is not null
       and jsonb_typeof(p_verifications) = 'array' then
      for v in select * from jsonb_array_elements(p_verifications)
      loop
        insert into verifications (org_id, result_id, name, standard, clause,
                                   equation, utilisation, status, acting,
                                   resisting, detail, remedy)
        values (org, resultat,
                v->>'name', v->>'standard', v->>'clause', v->>'equation',
                (v->>'utilisation')::double precision,
                (v->>'status')::check_status,
                v->>'acting', v->>'resisting', v->>'detail', v->>'remedy');
      end loop;
    end if;
  end if;

  return calcul;
end;
$$;


-- 5.4 — L'HISTORIQUE D'UN PROJET.
create or replace function project_calculation_list(p_project_id uuid)
returns table (
  calculation_id uuid,
  status         calculation_status,
  strict_ndp     boolean,
  engine_version text,
  inputs_hash    text,
  element        text,
  max_utilisation double precision,
  created_at     timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  if not exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = p_project_id and m.user_id = acteur) then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  return query
    select c.id, c.status, c.strict_ndp, e.version, c.inputs_hash,
           c.request->>'element',
           (select max(v.utilisation) from results r
              join verifications v on v.result_id = r.id
             where r.calculation_id = c.id),
           c.created_at
      from calculations c
      join engine_versions e on e.id = c.engine_version_id
     where c.project_id = p_project_id
     order by c.created_at desc, c.id;
end;
$$;


-- 5.5 — ROUVRIR UN CALCUL: LES MEMES ENTREES, LES MEMES RESULTATS.
--
-- Les verifications sont agregees en JSON plutot que rendues en lignes
-- separees: une relecture qui exigerait deux appels pourrait rendre un
-- resultat et des verifications provenant de deux instants differents.
create or replace function project_calculation_read(
  p_project_id uuid, p_calculation_id uuid)
returns table (
  calculation_id uuid,
  status         calculation_status,
  strict_ndp     boolean,
  engine_version text,
  inputs_hash    text,
  request        jsonb,
  ndp_snapshot   jsonb,
  refusal        jsonb,
  progress_log   jsonb,
  result         jsonb,
  journal        jsonb,
  verifications  jsonb,
  created_at     timestamptz)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := normative_authenticated_actor();
begin
  if not exists (select 1 from projects p
                  join organization_members m on m.org_id = p.org_id
                 where p.id = p_project_id and m.user_id = acteur) then
    raise exception 'projet introuvable ou hors de vos organisations.'
      using errcode = 'insufficient_privilege';
  end if;

  return query
    select c.id, c.status, c.strict_ndp, e.version, c.inputs_hash,
           c.request, c.ndp_snapshot, c.refusal, c.progress_log,
           r.payload, r.journal,
           coalesce((select jsonb_agg(jsonb_build_object(
                       'name', v.name, 'standard', v.standard,
                       'clause', v.clause, 'equation', v.equation,
                       'utilisation', v.utilisation, 'status', v.status,
                       'acting', v.acting, 'resisting', v.resisting,
                       'detail', v.detail, 'remedy', v.remedy)
                       order by v.created_at, v.id)
                      from verifications v where v.result_id = r.id),
                    '[]'::jsonb),
           c.created_at
      from calculations c
      join engine_versions e on e.id = c.engine_version_id
      left join results r on r.calculation_id = c.id
     where c.id = p_calculation_id and c.project_id = p_project_id;
end;
$$;


-- ---------------------------------------------------------------------
-- 6. PROPRIETE ET ACCES
-- ---------------------------------------------------------------------
-- Le proprietaire est celui des autres primitives SECURITY DEFINER; l'ACL est
-- fermee puis rouverte au seul role d'execution du backend. `public` n'est
-- jamais laisse dedans: `acldefault` accorde EXECUTE a PUBLIC sur toute
-- fonction nouvelle, et ne pas le revoquer explicitement l'y laisserait.
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_workspace_list()',
    'project_workspace_create(text, text, country_code, date, uuid)',
    'project_calculation_record(uuid, calculation_status, text, boolean, text,'
      || ' jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb)',
    'project_calculation_list(uuid)',
    'project_calculation_read(uuid, uuid)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 7. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
-- MEME FORME QU'EN 0011 A 0017, ET POUR LA MEME RAISON MESUREE: on endosse le
-- DONNEUR de l'octroi, et seulement s'il appartient a un ensemble admissible
-- explicite, confronte au catalogue et jamais dicte par lui. Un `revoke` nu
-- emis par un role qui n'est pas le donneur n'a AUCUN effet — ni erreur, ni
-- avertissement, et le privilege reste.
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
        'ATELIER_0018_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'ATELIER_0018_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
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
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid)
  then
    raise exception
      'ATELIER_0018_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public a la fin de 0018. Un role qui detient INSERT sur les '
      'tables d''autorite ne doit pas pouvoir creer d''objets entre deux '
      'migrations.';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 8. POSTCONDITION: LA COMPOSITION N'A PAS BOUGE
-- ---------------------------------------------------------------------
-- Aucune fonction ajoutee ici ne porte un nom « normative », « assert »,
-- « check_normative » ou « forbid »: le manifeste d'autorite ne les decouvre
-- donc pas, et n'a pas a les declarer. On le REVERIFIE quand meme — c'est
-- exactement le genre d'hypothese qui devient fausse en silence le jour ou le
-- filtre de decouverte change.
do $$
begin
  perform assert_authority_composition();
end;
$$;


-- POSTCONDITION PROPRE A CETTE MIGRATION: les cinq primitives existent, sont
-- SECURITY DEFINER, epinglent leur `search_path`, et PUBLIC n'y a pas EXECUTE.
--
-- POURQUOI LA VERIFIER PLUTOT QUE LA SUPPOSER. La boucle de la section 6
-- construit ses ordres par `format`: une signature mal ecrite y leverait, mais
-- une signature qui resout vers une AUTRE fonction ne leverait pas — elle
-- deplacerait silencieusement le proprietaire et l'ACL d'autre chose.
do $$
declare
  manquantes text;
begin
  select string_agg(f.identite, ', ') into manquantes
    from (select p.oid::regprocedure::text as identite,
                 p.prosecdef, p.proconfig,
                 has_function_privilege('public', p.oid, 'EXECUTE') as pub,
                 pg_get_userbyid(p.proowner) as proprio
            from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public'
             and p.proname in ('project_workspace_list',
                               'project_workspace_create',
                               'project_calculation_record',
                               'project_calculation_list',
                               'project_calculation_read')) f
   where not f.prosecdef
      or f.pub
      or f.proprio <> 'eurostruct_normative_writer'
      or coalesce(array_to_string(f.proconfig, ','), '') not like '%search_path%';
  if manquantes is not null then
    raise exception
      'ATELIER_COMPOSITION: % ne remplit pas le contrat attendu (SECURITY '
      'DEFINER, search_path epingle, proprietaire eurostruct_normative_writer, '
      'PUBLIC sans EXECUTE).', manquantes;
  end if;

  if (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public'
         and p.proname like 'project\_%') < 8 then
    raise exception
      'ATELIER_COMPOSITION: les primitives de l''atelier ne sont pas toutes '
      'presentes. Une migration partiellement appliquee laisserait le produit '
      'sans parcours et sans message.';
  end if;
end;
$$;


-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE L'EFFET.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
