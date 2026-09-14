-- 0019 — LE PROJET DETERMINE LE REFERENTIEL, ET LA BASE LE VERIFIE
--
-- CE QUI ETAIT FAUX, ET COMMENT ON L'A MESURE
-- --------------------------------------------
-- Un projet porte `country`, `region` et `ndp_as_of`: ensemble, ils designent
-- l'edition d'Annexe Nationale en vigueur, donc les VALEURS qui entrent dans
-- les formules. 0018 reprenait `ndp_as_of` du projet pour la colonne
-- `calculations.ndp_as_of` — et acceptait, dans `request`, n'importe quel
-- contexte. Mesure du jour, par le chemin produit:
--
--   projet:  country=BE  ndp_as_of=2024-01-15
--   corps:   country=FR  region=Ile-de-France  as_of=2030-01-01
--   reponse: 201
--     request.country            = FR
--     request.as_of              = 2030-01-01
--     calculations.ndp_as_of     = 2024-01-15   <- vient du PROJET
--     ndp_snapshot.country       = FR           <- vient du CORPS
--
-- La ligne enregistree se contredisait elle-meme. Le moteur avait applique le
-- referentiel FRANCAIS; la base affirmait une date BELGE. Deux verites dans
-- une seule transaction, dont une fausse — et c'est la ligne en base qu'un
-- audit lit des annees plus tard.
--
-- POURQUOI LA CORRECTION NE PEUT PAS RESTER DANS LA ROUTE
-- --------------------------------------------------------
-- Une route qui construit la requete depuis le projet ferme le trou pour
-- CETTE route. La suivante — un import par lot, une reprise, un second
-- adaptateur — rouvrira le meme, et rien ne le dira. Une frontiere qui
-- n'existe que dans un adaptateur HTTP n'est pas une frontiere: c'est une
-- convention.
--
-- `project_calculation_record` CONFRONTE DONC LA REQUETE AU PROJET. Quatre
-- champs — `project_id`, `country`, `region`, `as_of` — doivent dire ce que
-- le projet dit, sinon la transaction entiere tombe.
--
-- CE QUE CETTE MIGRATION AJOUTE ENCORE
-- -------------------------------------
-- `projects.region` existait depuis 0001 et AUCUNE primitive ne l'ecrivait ni
-- ne la lisait: l'ecran ne pouvait donc ni la saisir, ni la verifier. Une
-- colonne que le produit ne sait pas atteindre n'existe pas.
--
-- 0018 N'EST PAS MODIFIEE. Elle est inscrite au registre de migrations, et son
-- empreinte y est figee: la retoucher rendrait le registre menteur sur toute
-- base deja deployee. Les deux primitives concernees sont donc REMPLACEES ici,
-- au grand jour.

begin;

-- LE DROIT DE CREER, LE TEMPS DE CETTE MIGRATION. Meme raison qu'en 0018:
-- `alter function ... owner to` exige CREATE sur le schema, que la section
-- finale reprend ensuite sous le donneur endosse.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 0. L'IDENTITE DE CE QUI A TOURNE
-- ---------------------------------------------------------------------
-- `inputs_hash` EST L'EMPREINTE DE LA REQUETE, ET RIEN D'AUTRE. Le
-- commentaire de 0001 — « deux calculs de meme hash doivent produire le meme
-- resultat bit-a-bit » — n'est vrai que sous deux conditions que cette
-- empreinte ne porte pas: le meme CODE, et le meme REFERENTIEL. Une
-- confirmation arrivee entre deux calculs change la valeur d'un parametre
-- national, donc le resultat, pour une requete strictement identique.
--
-- `execution_identity` PORTE LES TROIS: requete canonique, instantane NDP
-- reellement utilise, et build. Deux exécutions de meme identite doivent
-- rendre le meme resultat; deux resultats differents sous la meme identite
-- sont un defaut, et celui-la merite qu'on le cherche.
--
-- `engine_build_sha` EST SUR LE CALCUL, PAS SUR LA VERSION, et c'est
-- necessaire: `engine_versions.version` est UNIQUE, si bien que deux builds
-- de « 0.3.0 » partagent une seule ligne. Le build est une propriete de
-- L'EXECUTION, pas de la version — et six commits successifs portent la meme
-- version, mesure. `engine_versions.git_sha` reste renseigne a la creation de
-- la ligne, comme repere du premier build vu.
alter table calculations
  add column if not exists execution_identity text,
  add column if not exists engine_build_sha   text;

comment on column calculations.execution_identity is
  'Empreinte canonique de (requete, instantane NDP, moteur, build). Deux '
  'executions de meme identite doivent rendre le meme resultat. Distincte '
  'd''`inputs_hash`, qui n''empreinte que la requete.';
comment on column calculations.engine_build_sha is
  'Le build EXACT qui a produit ce calcul, injecte par l''environnement. '
  '`engine_versions.version` etant unique, deux builds d''une meme version '
  'partagent une ligne: le build appartient donc a l''execution.';


-- ---------------------------------------------------------------------
-- 1. LA REGION ENTRE DANS LA CREATION ET DANS LA LECTURE
-- ---------------------------------------------------------------------
-- L'ANCIENNE SIGNATURE EST DEPOSEE, ET C'EST DELIBERE. Ajouter un parametre
-- avec valeur par defaut laisserait DEUX fonctions repondre au meme appel a
-- cinq arguments: PostgreSQL choisirait, et un appelant qui croit poser une
-- region pourrait atteindre celle qui l'ignore. Une seule signature existe.
drop function if exists project_workspace_create(text, text, country_code,
                                                 date, uuid);

create or replace function project_workspace_create(
  p_name      text,
  p_reference text,
  p_country   country_code,
  p_as_of     date,
  p_org_id    uuid default null,
  p_region    text default null)
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

  -- LA REGION EST NORMALISEE A `NULL` QUAND ELLE EST VIDE, et jamais a la
  -- chaine vide: `''` et `NULL` se compareraient differemment a la requete,
  -- et la postcondition de la section 2 refuserait des calculs corrects.
  insert into projects (org_id, name, reference, country, region, ndp_as_of,
                        created_by)
  values (org, btrim(p_name), nullif(btrim(coalesce(p_reference, '')), ''),
          p_country, nullif(btrim(coalesce(p_region, '')), ''), p_as_of,
          acteur)
  returning id into nouveau;

  insert into structural_models (org_id, project_id, created_by)
  values (org, nouveau, acteur);

  return nouveau;
end;
$$;


-- LA LECTURE REND LA REGION. Une valeur figee qu'on ne peut pas relire ne
-- verrouille rien: l'ecran ne saurait pas quoi afficher, ni sur quoi bloquer
-- ses champs.
-- L'ANCIENNE SIGNATURE A DOUZE ARGUMENTS EST DEPOSEE. Les deux nouveaux
-- parametres ont une valeur par defaut: sans ce `drop`, un appel a douze
-- arguments resoudrait vers CELLE QUI N'EXIGE PAS d'identite de build, et la
-- garde ci-dessus deviendrait contournable en omettant deux arguments.
drop function if exists project_calculation_record(
  uuid, calculation_status, text, boolean, text,
  jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb);

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
    select p.id, p.org_id, o.name, p.name, p.reference, p.country, p.region,
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


-- ---------------------------------------------------------------------
-- 2. LA POSTCONDITION: LE CONTEXTE NORMATIF NE PEUT PAS CONTREDIRE LE PROJET
-- ---------------------------------------------------------------------
-- QUATRE CHAMPS SONT CONFRONTES, ET PAS UN DE PLUS. `project_id`, `country`,
-- `region` et `as_of` sont exactement ce qui decide QUEL referentiel
-- s'applique. Le reste de la requete — la section, les materiaux, le moment —
-- est la matiere du calcul: elle change d'un calcul a l'autre par nature, et
-- la contraindre ici n'aurait aucun sens.
--
-- `IS DISTINCT FROM` PARTOUT, ET C'EST NECESSAIRE. La region est nullable des
-- deux cotes; `<>` rendrait NULL sur une comparaison impliquant NULL, donc
-- `not null` serait faux, donc le refus ne tomberait pas. Un projet sans
-- region accepterait alors n'importe quelle region.
--
-- LA REQUETE PEUT OMETTRE `region`, ET C'EST TRAITE COMME `NULL`: `->>` rend
-- NULL sur une cle absente comme sur un `null` JSON. Les deux disent la meme
-- chose — « pas de region » — et doivent se comparer de la meme facon.
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
  p_verifications  jsonb,
  p_execution_identity text default null,
  p_engine_build   text default null)
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
  pays     country_code;
  region   text;
  modele   uuid;
  moteur   uuid;
  calcul   uuid;
  resultat uuid;
  v        jsonb;
begin
  -- L'ORGANISATION SORT DU PROJET, ET LE PROJET DE L'APPARTENANCE. A aucun
  -- moment `org_id` ne traverse la frontiere depuis l'appelant.
  select p.org_id, p.ndp_as_of, p.country, p.region
    into org, as_of, pays, region
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

  if p_request is null then
    raise exception
      'les entrees sont absentes: un calcul qu''on ne peut pas rouvrir n''est '
      'pas un calcul enregistre.'
      using errcode = 'check_violation';
  end if;

  -- UN CALCUL PERSISTANT SANS IDENTITE DE BUILD EST REFUSE.
  --
  -- Il pretendrait designer le code qui l'a produit et ne saurait pas le
  -- nommer. « 0.3.0 » ne designe aucun build: six commits successifs la
  -- portent. Le calcul EXPLORATOIRE, lui, reste disponible — il ne pretend
  -- rien et ne survit a rien; c'est la persistance qui exige de pouvoir
  -- repondre, dix ans plus tard, a « quel code ? ».
  if coalesce(btrim(p_engine_build), '') = ''
     or coalesce(btrim(p_execution_identity), '') = '' then
    raise exception
      'identite d''execution absente: un calcul conserve doit designer le '
      'code exact qui l''a produit et le referentiel qu''il a applique. La '
      'version seule ne le fait pas. Injecter EUROSTRUCT_BUILD_SHA au '
      'demarrage; le calcul exploratoire reste disponible sans elle.'
      using errcode = 'check_violation';
  end if;

  -- LA POSTCONDITION. Elle ne repare rien et ne complete rien: elle REFUSE.
  -- Corriger la requete ici la ferait diverger de celle que le moteur a
  -- reellement utilisee, et l'enregistrement cesserait de dire ce qui s'est
  -- passe — ce qui est exactement le defaut qu'on ferme.
  if (p_request->>'project_id') is distinct from p_project_id::text then
    raise exception
      'contexte normatif refuse: la requete porte le projet « % » et '
      'l''enregistrement vise « % ». Une note ne peut pas nommer un autre '
      'dossier que celui ou elle est rangee.',
      coalesce(p_request->>'project_id', '(absent)'), p_project_id
      using errcode = 'check_violation';
  end if;
  if (p_request->>'country') is distinct from pays::text then
    raise exception
      'contexte normatif refuse: la requete applique le referentiel « % » et '
      'le projet est « % ». Le pays choisit l''Annexe Nationale, donc les '
      'valeurs qui entrent dans les formules.',
      coalesce(p_request->>'country', '(absent)'), pays
      using errcode = 'check_violation';
  end if;
  if (p_request->>'region') is distinct from region then
    raise exception
      'contexte normatif refuse: la requete porte la region « % » et le '
      'projet « % ». La region change les parametres nationaux la ou elle '
      'est regionalisee.',
      coalesce(p_request->>'region', '(aucune)'),
      coalesce(region, '(aucune)')
      using errcode = 'check_violation';
  end if;
  if (p_request->>'as_of') is distinct from as_of::text then
    raise exception
      'contexte normatif refuse: la requete est datee du « % » et le projet '
      'du « % ». La date resout l''edition en vigueur; deux dates dans un '
      'meme dossier citent deux annexes.',
      coalesce(p_request->>'as_of', '(absente)'), as_of
      using errcode = 'check_violation';
  end if;

  -- L'ETAT ET SON CONTENU DOIVENT SE CORRESPONDRE.
  --
  -- `succeeded` SANS RESULTAT EST UN MENSONGE D'HISTORIQUE: la ligne annonce
  -- un calcul abouti, la relecture rend un ecran vide, et personne ne sait
  -- lequel des deux croire. `refused` AVEC UN RESULTAT est pire: il presente
  -- comme conclu ce que le moteur a refuse de conclure.
  if p_status = 'succeeded' and p_result is null then
    raise exception
      'un calcul « succeeded » sans resultat n''a rien conclu. Enregistrer '
      'l''etat sans le contenu rendrait l''historique menteur exactement la '
      'ou il sert.'
      using errcode = 'check_violation';
  end if;
  if p_status = 'succeeded'
     and (p_verifications is null
          or jsonb_typeof(p_verifications) <> 'array'
          or jsonb_array_length(p_verifications) = 0) then
    raise exception
      'un calcul « succeeded » sans aucune verification ne dit pas s''il '
      'passe. Le cahier des charges interdit le simple « OK »: un taux de '
      'travail est exige, et il vient des verifications.'
      using errcode = 'check_violation';
  end if;
  -- LE JOURNAL EST UN OBJET, PAS UN TABLEAU, et la premiere redaction de
  -- cette garde l'ignorait: `JournalDTO` porte `title`, `steps` et `clauses`.
  -- Exiger `jsonb_typeof = 'array'` refusait donc TOUT calcul abouti — la
  -- garde tombait sur sa propre hypothese. Ce qui compte est qu'il y ait au
  -- moins une ETAPE: c'est elle qui rend un nombre cliquable.
  if p_status = 'succeeded'
     and (p_journal is null
          or jsonb_typeof(p_journal) <> 'object'
          or jsonb_typeof(p_journal->'steps') <> 'array'
          or jsonb_array_length(p_journal->'steps') = 0) then
    raise exception
      'un calcul « succeeded » sans etape de journal n''est pas relisible pas '
      'a pas. C''est le journal qui rend chaque nombre cliquable, et le '
      'cahier des charges l''exige (section 8.1).'
      using errcode = 'check_violation';
  end if;
  if p_status = 'refused' then
    if p_refusal is null then
      raise exception
        'un refus doit dire pourquoi. Enregistrer « refused » sans motif '
        'rendrait l''historique illisible exactement la ou il compte.'
        using errcode = 'check_violation';
    end if;
    if p_result is not null
       or (p_verifications is not null
           and jsonb_typeof(p_verifications) = 'array'
           and jsonb_array_length(p_verifications) > 0) then
      raise exception
        'un refus ne conclut rien: il ne peut porter ni resultat ni '
        'verification. Le moteur a refuse de calculer, et l''historique doit '
        'le dire sans nuance.'
        using errcode = 'check_violation';
    end if;
  end if;

  select id into modele from structural_models
   where project_id = p_project_id order by version, name limit 1;
  if modele is null then
    insert into structural_models (org_id, project_id, created_by)
    values (org, p_project_id, acteur) returning id into modele;
  end if;

  -- LA VERSION DU MOTEUR EST ENREGISTREE TELLE QU'ELLE EST, pas choisie dans
  -- une liste. Une version inconnue de `engine_versions` est une version qui
  -- n'a jamais tourne ici; l'inscrire est un constat.
  -- `git_sha` EST RENSEIGNE A LA CREATION DE LA LIGNE, comme repere du
  -- premier build vu pour cette version. Il n'est PAS mis a jour ensuite:
  -- ecraser ferait mentir toutes les lignes anterieures. Le build faisant foi
  -- est sur le calcul.
  select id into moteur from engine_versions where version = p_engine_version;
  if moteur is null then
    insert into engine_versions (version, released_at, git_sha)
    values (p_engine_version, now(), p_engine_build)
    on conflict (version) do nothing
    returning id into moteur;
    if moteur is null then
      select id into moteur from engine_versions where version = p_engine_version;
    end if;
  end if;

  insert into calculations (org_id, project_id, model_id, engine_version_id,
                            status, inputs_hash, strict_ndp, refusal,
                            progress_log, request, ndp_as_of, ndp_snapshot,
                            execution_identity, engine_build_sha,
                            requested_by, started_at, finished_at)
  values (org, p_project_id, modele, moteur, p_status, p_inputs_hash,
          coalesce(p_strict_ndp, true), p_refusal,
          coalesce(p_progress_log, '[]'::jsonb), p_request, as_of,
          coalesce(p_ndp_snapshot, '{}'::jsonb),
          btrim(p_execution_identity), btrim(p_engine_build),
          acteur, now(), now())
  returning id into calcul;

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


-- ---------------------------------------------------------------------
-- 2 bis. LA RELECTURE REND L'IDENTITE D'EXECUTION
-- ---------------------------------------------------------------------
-- Une identite enregistree qu'on ne peut pas relire ne prouve rien: la note
-- de calcul doit l'afficher, et un audit doit pouvoir la confronter.
drop function if exists project_calculation_read(uuid, uuid);

create or replace function project_calculation_read(
  p_project_id uuid, p_calculation_id uuid)
returns table (
  calculation_id uuid,
  status         calculation_status,
  strict_ndp     boolean,
  engine_version text,
  engine_build_sha text,
  execution_identity text,
  inputs_hash    text,
  request        jsonb,
  ndp_snapshot   jsonb,
  ndp_as_of      date,
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
    select c.id, c.status, c.strict_ndp, e.version, c.engine_build_sha,
           c.execution_identity, c.inputs_hash,
           c.request, c.ndp_snapshot, c.ndp_as_of, c.refusal, c.progress_log,
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
-- 3. PROPRIETE ET ACCES DES FONCTIONS REMPLACEES
-- ---------------------------------------------------------------------
-- `drop` PUIS `create` REPART DE `acldefault`: le proprietaire redevient le
-- migrateur et PUBLIC retrouve EXECUTE. Les reposer n'est pas une precaution,
-- c'est la condition pour que la surface reste celle que
-- `authority_sql_hardening.sh` a declaree.
do $$
declare
  f text;
begin
  foreach f in array array[
    'project_workspace_list()',
    'project_workspace_create(text, text, country_code, date, uuid, text)',
    'project_calculation_record(uuid, calculation_status, text, boolean, text,'
      || ' jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, text, text)',
    'project_calculation_read(uuid, uuid)']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 4. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0011 a 0018: on endosse le DONNEUR de l'octroi, et
-- seulement s'il appartient a un ensemble admissible explicite. Un `revoke`
-- nu emis par un role qui n'est pas le donneur n'a AUCUN effet — ni erreur,
-- ni avertissement, et le privilege reste.
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
        'ATELIER_0019_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'ATELIER_0019_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
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
      'ATELIER_0019_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public a la fin de 0019.';
  end if;
end;
$$;


-- ---------------------------------------------------------------------
-- 5. POSTCONDITIONS
-- ---------------------------------------------------------------------
do $$
begin
  perform assert_authority_composition();
end;
$$;


-- LES TROIS FONCTIONS REMPLACEES TIENNENT LE MEME CONTRAT QU'EN 0018, ET IL
-- N'EN RESTE QU'UNE DE CHAQUE.
--
-- POURQUOI COMPTER LES SIGNATURES. `drop function ... (ancienne signature)`
-- suivi d'un `create` a une NOUVELLE signature est exactement la manoeuvre qui
-- laisse deux fonctions homonymes quand le `drop` vise la mauvaise. PostgreSQL
-- choisirait alors par resolution de types, et un appelant qui croit poser une
-- region atteindrait celle qui l'ignore.
do $$
declare
  n_create int;
  n_list   int;
  n_record int;
  n_read   int;
  fautives text;
begin
  select count(*) into n_create from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'project_workspace_create';
  select count(*) into n_list from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'project_workspace_list';
  select count(*) into n_record from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'project_calculation_record';
  select count(*) into n_read from pg_proc p
    join pg_namespace ns on ns.oid = p.pronamespace
   where ns.nspname = 'public' and p.proname = 'project_calculation_read';
  -- `project_calculation_record` COMPTE DOUBLE ICI. Ses deux nouveaux
  -- parametres ont une valeur par defaut: si l'ancienne signature a douze
  -- arguments survivait, un appel a douze arguments resoudrait vers ELLE, et
  -- la garde d'identite de build deviendrait contournable en omettant deux
  -- arguments. C'est le genre de contournement qui ne laisse aucune trace.
  if n_create <> 1 or n_list <> 1 or n_record <> 1 or n_read <> 1 then
    raise exception
      'ATELIER_0019_SIGNATURES_MULTIPLES: create=%, list=%, record=%, read=%. '
      'Deux homonymes laisseraient PostgreSQL choisir, et un appelant '
      'atteindrait la mauvaise — y compris celle sans garde.',
      n_create, n_list, n_record, n_read;
  end if;

  select string_agg(f.identite, ', ') into fautives
    from (select p.oid::regprocedure::text as identite, p.prosecdef, p.proconfig,
                 has_function_privilege('public', p.oid, 'EXECUTE') as pub,
                 pg_get_userbyid(p.proowner) as proprio
            from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
           where ns.nspname = 'public'
             and p.proname in ('project_workspace_list',
                               'project_workspace_create',
                               'project_calculation_record',
                               'project_calculation_read')) f
   where not f.prosecdef
      or f.pub
      or f.proprio <> 'eurostruct_normative_writer'
      or coalesce(array_to_string(f.proconfig, ','), '') not like '%search_path%';
  if fautives is not null then
    raise exception
      'ATELIER_0019_COMPOSITION: % ne remplit pas le contrat attendu (SECURITY '
      'DEFINER, search_path epingle, proprietaire eurostruct_normative_writer, '
      'PUBLIC sans EXECUTE).', fautives;
  end if;
end;
$$;


select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
