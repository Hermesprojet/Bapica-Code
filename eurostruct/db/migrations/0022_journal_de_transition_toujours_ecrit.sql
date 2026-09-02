-- 0022 — LE JOURNAL D'UNE TRANSITION SUIT LE LIVRABLE, TOUJOURS
--
-- LE DEFAUT, ET IL EST DE 0020
-- -----------------------------
-- 0020 a donne `log_deliverable_transition()` au proprietaire de l'atelier,
-- pour qu'il puisse appeler `project_backend_actor()` — sans quoi le premier
-- livrable du chemin produit echouait sur « permission denied for function ».
-- C'etait juste, et cela a ferme un autre chemin.
--
-- Le declencheur s'execute desormais sous `eurostruct_normative_writer`, qui
-- n'est PAS le proprietaire de `deliverable_state_transitions`: les politiques
-- RLS s'appliquent donc a lui. Celle de 0020 exigeait
-- `project_actor_is_member(org_id)`. Or ce predicat lit
-- `project_backend_actor()`, c'est-a-dire l'acteur pose par le backend
-- authentifie — et il n'y en a AUCUN quand un livrable est ecrit directement
-- en SQL, par le proprietaire de la base.
--
-- Mesure du jour, sur la suite des garanties structurelles:
--
--   ERROR: new row violates row-level security policy for table
--          "deliverable_state_transitions"
--   CONTEXT: PL/pgSQL function log_deliverable_transition() line 4
--
-- L'ecriture du livrable passait, celle de son journal non.
--
-- POURQUOI `true` EST LA BONNE REPONSE, ET PAS UN RELACHEMENT
-- ------------------------------------------------------------
-- LE JOURNAL EST UNE OBLIGATION, PAS UNE DECISION DE LOCATAIRE. `org_id` n'y
-- est pas fourni par un appelant: il est COPIE de la ligne `deliverables` que
-- le declencheur vient de voir passer — une ligne dont l'insertion a deja ete
-- autorisee par la politique de SA table, qui exige l'appartenance. Reposer la
-- question sur le journal n'ajoute aucune garantie: elle ne peut que la
-- refuser la ou l'ecriture, elle, a ete permise.
--
-- ET LE PIRE DES DEUX MONDES SERAIT DE LA GARDER. Un livrable ecrit sans son
-- historique est strictement moins sur qu'un livrable dont l'historique est
-- ecrit sans acteur nomme: dans le premier cas on ne sait pas QUAND il a
-- change d'etat, dans le seond on ne sait pas QUI — et le second se lit sur la
-- ligne, `actor_id` etant NULL.
--
-- LA LECTURE, ELLE, RESTE CLOISONNEE. C'est elle qui porte la
-- confidentialite: `transitions_atelier_read` continue d'exiger
-- l'appartenance, et n'est pas touchee.
--
-- QUI PEUT ECRIRE DANS CE JOURNAL, AU BOUT DU COMPTE
-- ----------------------------------------------------
-- La politique vise NOMMEMENT `eurostruct_normative_writer`. Ce role n'est
-- atteignable par personne: il n'a aucun `login`, et le backend authentifie
-- n'a aucun privilege de table. Ce qui s'execute sous lui, ce sont les
-- fonctions SECURITY DEFINER dont il est proprietaire — les primitives de
-- l'atelier et ce declencheur. `true` signifie donc exactement « le
-- declencheur peut journaliser », et rien d'autre.

begin;

drop policy if exists transitions_atelier_insert on deliverable_state_transitions;

create policy transitions_atelier_insert on deliverable_state_transitions
  for insert to eurostruct_normative_writer
  with check (true);

comment on table deliverable_state_transitions is
  'Le parcours de relecture d''un livrable, horodate. L''ECRITURE suit le '
  'livrable — elle est une obligation du declencheur, jamais une decision de '
  'locataire — et la LECTURE reste cloisonnee par l''appartenance.';


-- ---------------------------------------------------------------------
-- POSTCONDITIONS
-- ---------------------------------------------------------------------
do $$
begin
  perform assert_authority_composition();
end;
$$;

-- LES DEUX POLITIQUES EXISTENT, ET ELLES NE DISENT PAS LA MEME CHOSE.
--
-- Le controle porte sur leur EXPRESSION, pas sur leur existence: une lecture
-- ouverte a `true` serait exactement le relachement que cette migration ne
-- fait pas, et rien d'autre ne le dirait.
do $$
declare
  lecture text;
  ecriture text;
begin
  select pg_get_expr(p.polqual, p.polrelid) into lecture
    from pg_policy p
   where p.polrelid = 'deliverable_state_transitions'::regclass
     and p.polname = 'transitions_atelier_read';
  select pg_get_expr(p.polwithcheck, p.polrelid) into ecriture
    from pg_policy p
   where p.polrelid = 'deliverable_state_transitions'::regclass
     and p.polname = 'transitions_atelier_insert';

  if lecture is null or position('project_actor_is_member' in lecture) = 0 then
    raise exception
      'ATELIER_0022_LECTURE_NON_CLOISONNEE: la politique de lecture du journal '
      'n''exige plus l''appartenance (« % »). C''est elle qui porte la '
      'confidentialite.', coalesce(lecture, '(absente)');
  end if;

  if ecriture is distinct from 'true' then
    raise exception
      'ATELIER_0022_ECRITURE_CONDITIONNELLE: la politique d''ecriture du '
      'journal vaut « % ». Un livrable ecrit sans son historique est '
      'strictement moins sur qu''un historique sans acteur nomme.',
      coalesce(ecriture, '(absente)');
  end if;
end;
$$;

-- ET LE DECLENCHEUR APPARTIENT TOUJOURS AU PROPRIETAIRE DE L'ATELIER.
--
-- Sans cela la politique ci-dessus ne viserait pas le role qui execute, et le
-- premier livrable du chemin produit echouerait de nouveau sur
-- « permission denied for function project_backend_actor ».
do $$
declare
  proprietaire text;
begin
  select pg_get_userbyid(p.proowner) into proprietaire
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'log_deliverable_transition';
  if proprietaire is distinct from 'eurostruct_normative_writer' then
    raise exception
      'ATELIER_0022_JOURNAL_MAL_POSSEDE: log_deliverable_transition() '
      'appartient a « % »: la politique d''ecriture ne le vise pas.',
      proprietaire;
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
