-- 0027 — L'HISTORIQUE DIT CE QUI EST UNE VARIANTE, ET DE QUOI
--
-- LE DEFAUT QUE CETTE MIGRATION FERME
-- -------------------------------------
-- Depuis le lot precedent, une etude peut etre une VARIANTE d'une autre: la
-- requete gelee porte `derived_from_calculation_id`, la relecture le rend, et
-- la synthese affiche « Variante de l'etude … » avec un bouton vers l'origine.
--
-- L'HISTORIQUE, LUI, NE LE DISAIT PAS. `project_calculation_list` rendait un
-- repere, un etat, un mode, un taux, un moteur: deux lignes « P1 abouti
-- exploratoire » se suivaient sans qu'on sache laquelle est l'etude initiale
-- et laquelle en derive, ni combien de variantes une etude a engendrees. Il
-- fallait rouvrir chaque ligne pour le savoir — et l'historique est
-- precisement l'ecran ou l'on choisit SANS rouvrir.
--
-- CE QUE CETTE MIGRATION AJOUTE, ET RIEN DE PLUS
-- ------------------------------------------------
-- Deux colonnes a la liste, lues et comptees, jamais recomposees:
--
--   derived_from_calculation_id   l'origine, telle que la requete gelee la
--                                 nomme — nulle pour une etude initiale;
--   variant_count                 le nombre d'etudes du MEME projet qui
--                                 nomment cette ligne comme origine.
--
-- Ajouter une colonne a un `returns table` impose un `drop`, donc une reprise
-- de la propriete et des droits (section 2), et la meme postcondition qu'en
-- 0018 (section 4). Aucune table ne change, aucune politique, aucun role:
-- c'est une migration ADDITIVE sur une primitive de lecture.
--
-- POURQUOI LE COMPTE EST FAIT ICI ET PAS A L'ECRAN
-- --------------------------------------------------
-- L'ecran pourrait compter les lignes qui nomment une origine. Il ne verrait
-- que les lignes qu'il a recues — et l'historique d'un projet est deja
-- complet, donc il le pourrait aujourd'hui. Mais le jour ou la liste sera
-- paginee, le compte fait a l'ecran deviendra faux en silence. Le serveur
-- compte sur la table entiere du projet, et le contrat le dit.

begin;

-- LE DROIT DE CREER, POUR LA DUREE DE CETTE TRANSACTION SEULEMENT. Mesure en
-- 0020 et repris en 0024 et 0025: `alter function ... owner to` exige que le
-- nouveau proprietaire detienne CREATE sur le schema. Il est repris en
-- section 3, et la postcondition de 0018 continue de le verifier a chaque
-- deploiement.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LA LISTE DES CALCULS D'UN PROJET, AVEC LA FILIATION
-- ---------------------------------------------------------------------
-- Le corps est celui de 0018 §5.4, plus deux colonnes. La garde d'acces est
-- identique: l'appelant doit appartenir a une organisation du projet.
drop function if exists project_calculation_list(uuid);
create function project_calculation_list(p_project_id uuid)
returns table (
  calculation_id uuid,
  status         calculation_status,
  strict_ndp     boolean,
  engine_version text,
  inputs_hash    text,
  element        text,
  max_utilisation double precision,
  created_at     timestamptz,
  derived_from_calculation_id uuid,
  variant_count  integer)
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
           c.created_at,
           -- LA FILIATION EST LUE DANS LA REQUETE GELEE, jamais recomposee.
           -- La route a verifie l'origine avant d'ecrire; on ne convertit
           -- neanmoins que ce qui a la forme d'un uuid, pour qu'une charge
           -- ancienne ou etrangere ne fasse pas echouer TOUTE la liste.
           case
             when (c.request->>'derived_from_calculation_id')
                  ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
             then (c.request->>'derived_from_calculation_id')::uuid
           end,
           -- LES VARIANTES SONT DANS LE MEME PROJET: la route refuse une
           -- origine d'un autre dossier. Le compte se restreint donc au projet,
           -- et ne peut pas croiser deux bureaux.
           (select count(*)::integer from calculations v
             where v.project_id = c.project_id
               and lower(v.request->>'derived_from_calculation_id') = c.id::text)
      from calculations c
      join engine_versions e on e.id = c.engine_version_id
     where c.project_id = p_project_id
     order by c.created_at desc, c.id;
end;
$$;


-- ---------------------------------------------------------------------
-- 2. PROPRIETE ET ACCES
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0018 §6: proprietaire commun des primitives SECURITY
-- DEFINER, ACL fermee puis rouverte au seul role d'execution du backend.
do $$
declare
  f text := 'project_calculation_list(uuid)';
begin
  execute format('alter function %s owner to eurostruct_normative_writer', f);
  execute format('revoke all on function %s from public', f);
  execute format('grant execute on function %s to eurostruct_authority_backend', f);
end
$$;


-- ---------------------------------------------------------------------
-- 3. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
revoke create on schema public from eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 4. CE QUE CETTE MIGRATION DOIT AVOIR OBTENU
-- ---------------------------------------------------------------------
do $$
declare
  proprio  text;
  chemin   text;
  securite boolean;
  pub      boolean;
  rendu    text;
begin
  select pg_get_userbyid(p.proowner), p.prosecdef,
         array_to_string(p.proconfig, ','),
         has_function_privilege('public', p.oid, 'EXECUTE'),
         pg_get_function_result(p.oid)
    into proprio, securite, chemin, pub, rendu
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public'
     and p.proname = 'project_calculation_list';

  if proprio is null then
    raise exception
      'ATELIER_0027_PRIMITIVE_ABSENTE: project_calculation_list n''existe pas '
      'apres la migration. L''historique de chaque projet serait vide.';
  end if;
  if proprio <> 'eurostruct_normative_writer' then
    raise exception
      'ATELIER_0027_PROPRIETAIRE: la primitive appartient a « % ». Elle doit '
      'appartenir au migrateur endosse, sans quoi son SECURITY DEFINER '
      'endosse quelqu''un d''autre.', proprio;
  end if;
  if not securite then
    raise exception
      'ATELIER_0027_SANS_DEFINER: la primitive n''est pas SECURITY DEFINER: '
      'le backend authentifie ne lit pas `calculations` directement.';
  end if;
  if chemin is null or position('search_path=public, pg_temp' in chemin) = 0 then
    raise exception
      'ATELIER_0027_SEARCH_PATH_NON_EPINGLE: proconfig vaut « % ». Un '
      'SECURITY DEFINER sans search_path epingle est detournable.',
      coalesce(chemin, '(nul)');
  end if;
  if pub then
    raise exception
      'ATELIER_0027_PUBLIC_EXECUTE: PUBLIC peut executer la primitive. '
      'L''historique d''un projet serait lisible par tout role connecte.';
  end if;

  -- LE CONTRAT RENDU PORTE LES DEUX COLONNES, AU BON TYPE. Une recreation
  -- qui les aurait oubliees, ou mal typees, passerait les tests nominaux
  -- jusqu'a ce que l'API lise une colonne absente.
  if position('derived_from_calculation_id uuid' in rendu) = 0
     or position('variant_count integer' in rendu) = 0 then
    raise exception
      'ATELIER_0027_CONTRAT_INCOMPLET: la liste rend « % ». Elle doit porter '
      'derived_from_calculation_id uuid et variant_count integer.', rendu;
  end if;

  -- LES HUIT COLONNES DE 0018 SONT TOUJOURS LA, dans le meme ordre: l'API
  -- les lit par nom, un autre client pourrait les lire par position.
  if position('calculation_id uuid, status calculation_status, strict_ndp boolean, '
              'engine_version text, inputs_hash text, element text, '
              'max_utilisation double precision, created_at timestamp with time zone, '
              'derived_from_calculation_id uuid, variant_count integer' in rendu) = 0 then
    raise exception
      'ATELIER_0027_ORDRE_DES_COLONNES: la liste rend « % ». Les huit colonnes '
      'de 0018 precedent les deux nouvelles, dans l''ordre de 0018.', rendu;
  end if;
end;
$$;

-- LA COMPOSITION N'A PAS BOUGE: la primitive garde son nom, et le manifeste
-- d'autorite n'a rien a decouvrir de plus. On le REVERIFIE quand meme.
do $$
begin
  perform assert_authority_composition();
end;
$$;

-- LES PRIMITIVES DE L'ATELIER SONT TOUTES LA: un drop sans create laisserait
-- le produit sans historique et sans message.
do $$
begin
  if (select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace
       where n.nspname = 'public'
         and p.proname like 'project\_%') < 8 then
    raise exception
      'ATELIER_0027_COMPOSITION: les primitives de l''atelier ne sont pas '
      'toutes presentes apres la recreation de project_calculation_list.';
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
