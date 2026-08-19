-- =====================================================================
-- EUROSTRUCT — 0009: qui a le droit de valider
--
-- La regle « ingenieur nomme » vise une validation humaine NOMINATIVE par le
-- bureau d'etudes qui utilise le logiciel — pas l'intervention d'un tiers
-- exterieur. Le logiciel ne remplace pas l'ingenieur; il lui donne quelque
-- chose a verifier et a signer.
--
-- Ce que 0001 posait deja: la table validations, la copie figee du nom et du
-- role, et la contrainte only_a_validating_engineer_may_sign.
--
-- Ce qui manquait, et c'est l'essentiel: RIEN ne verifiait que validated_by
-- soit reellement membre de l'organisation, ni qu'il y soit actif, ni que le
-- projet appartienne bien a cette organisation. validator_role etait une
-- simple copie declarative posee sur la ligne — une insertion pouvait
-- l'affirmer pour un compte qui n'etait membre de rien.
--
-- Trois validations distinctes, et cette migration ne concerne que la 2e:
--   1. NORMATIVE  — la valeur nationale est bien celle du pays (0004/0007).
--   2. METIER     — un ingenieur du bureau d'etudes repond du calcul (ici).
--   3. EMISSION   — le livrable passe a 'final' (0005).
-- =====================================================================

begin;

-- ---------------------------------------------------------------------
-- Une adhesion peut etre revoquee sans etre effacee
-- ---------------------------------------------------------------------
-- Effacer la ligne ferait disparaitre la trace des signatures passees. Un
-- ancien collaborateur doit rester lisible dans une note de dix ans, et ne
-- plus pouvoir signer aujourd'hui.
alter table organization_members
  add column is_active boolean not null default true;

alter table organization_members
  add column deactivated_at timestamptz;

alter table organization_members
  add constraint deactivation_is_dated check (
    is_active or deactivated_at is not null
  );

comment on column organization_members.is_active is
  'Faux quand l''acces est revoque. La ligne survit pour la tracabilite des '
  'signatures deja apposees, mais ne permet plus d''en apposer.';


-- ---------------------------------------------------------------------
-- Le signataire doit etre membre actif, habilite, de l'organisation du projet
-- ---------------------------------------------------------------------
-- ATTENTION: cette fonction EXISTE depuis 0003 et porte deja deux
-- comportements indispensables — elle derive validator_role du membre et fige
-- son numero d'inscription. La remplacer sans les reprendre les supprimait en
-- silence; c'est arrive une fois, et seule la suite de tests SQL l'a montre
-- (« Le numero d'inscription n'a pas ete fige »).
--
-- Elle est donc reecrite ICI EN ENTIER: les controles de 0003 d'abord, les
-- nouveaux ensuite. Le declencheur validations_check_validator de 0003 reste
-- le seul a l'appeler.
create or replace function check_validator_is_authorised() returns trigger
language plpgsql as $$
declare
  m record;
  proj_org uuid;
begin
  -- Le projet et la validation doivent relever de la meme organisation.
  select org_id into proj_org from projects where id = new.project_id;
  if proj_org is null then
    raise exception 'projet % introuvable', new.project_id
      using errcode = 'foreign_key_violation';
  end if;
  if proj_org <> new.org_id then
    raise exception
      'la validation est rattachee a l''organisation % alors que le projet '
      'releve de %. La validation revient au bureau d''etudes qui realise '
      'l''etude.', new.org_id, proj_org
      using errcode = 'check_violation';
  end if;

  select * into m from organization_members
   where org_id = new.org_id and user_id = new.validated_by;

  if not found then
    -- errcode conserve depuis 0003: la suite de tests s'appuie dessus.
    raise exception
      'le signataire % n''est pas membre de l''organisation %. Une signature '
      'engage le bureau d''etudes: elle ne peut venir que d''un de ses '
      'membres.', new.validated_by, new.org_id
      using errcode = 'insufficient_privilege';
  end if;

  if not m.is_active then
    raise exception
      'le compte du signataire % n''est plus actif dans l''organisation %. Un '
      'acces revoque ne peut plus engager le bureau d''etudes.',
      new.validated_by, new.org_id
      using errcode = 'check_violation';
  end if;

  if m.role <> 'validating_engineer' then
    raise exception
      'le role « % » ne porte pas la validation technique. L''organisation '
      'attribue le role « validating_engineer » a l''ingenieur qui repond de '
      'ses etudes.', m.role
      using errcode = 'insufficient_privilege';
  end if;

  -- Un nom de personne, pas une raison sociale: quelqu'un lit l'etude et en
  -- repond. Une entite juridique n'en lit aucune.
  if btrim(coalesce(new.validator_name, '')) = '' then
    raise exception
      'validator_name est vide. La signature doit porter le nom de la '
      'personne qui valide.'
      using errcode = 'check_violation';
  end if;

  -- Repris de 0003, et non negociable: le role et le numero d'inscription
  -- sont DERIVES de l'adhesion, jamais crus sur parole. Ils sont figes ici
  -- pour rester lisibles dix ans plus tard, meme si le membre a quitte
  -- l'organisation entre-temps.
  new.validator_role := m.role;
  new.professional_id := coalesce(new.professional_id, m.professional_id);
  return new;
end;
$$;

comment on function check_validator_is_authorised is
  'Validation METIER (niveau 2 sur 3): le signataire doit etre authentifie, '
  'membre ACTIF de l''organisation du projet, et porteur du role de '
  'validation technique. Aucun tiers exterieur n''est requis.';


-- Immuabilite d'une signature: deja garantie par 0003
-- (trigger validations_are_immutable sur forbid_mutation). Rien a ajouter ici;
-- un second declencheur sur le meme evenement ne renforcerait rien et
-- rendrait seulement l'ordre d'execution significatif.

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
