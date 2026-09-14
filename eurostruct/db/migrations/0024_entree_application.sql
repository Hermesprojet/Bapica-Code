-- 0024 — ENTRER DANS L'APPLICATION QUAND ON N'Y EST PAS ENCORE
--
-- LE CUL-DE-SAC QUE CETTE MIGRATION FERME
-- -----------------------------------------
-- Tout le produit suppose une ligne dans `organization_members`. Sans elle,
-- `GET /v1/projects` rend une liste VIDE — pas une erreur, pas une
-- explication, un ecran nu — et la creation d'un projet refuse par « aucune
-- organisation: cet acteur n'appartient a aucune organisation avec un role
-- d'ecriture ». Ce refus est JUSTE. Ce qui manquait, c'est la suite: AUCUNE
-- ROUTE, AUCUNE PRIMITIVE ne permettait d'en sortir.
--
-- La seule facon d'exister dans l'application etait un `insert` fait a la main
-- par le proprietaire de la base. Autrement dit: le produit n'avait pas de
-- porte d'entree. Un compte tout neuf, parfaitement authentifie, arrivait
-- devant un ecran vide et ne pouvait rien faire — jamais.
--
-- LES TROIS GESTES QUE CETTE MIGRATION REND POSSIBLES
-- -----------------------------------------------------
--   1. AMORCER SON ORGANISATION — atomiquement: l'organisation et l'adhesion
--      `owner` naissent ensemble ou pas du tout. Une organisation sans
--      proprietaire serait un bureau que personne ne peut administrer, et il
--      faudrait un `insert` a la main pour l'en sortir: le meme cul-de-sac,
--      un cran plus loin.
--   2. INVITER — par un lien a forte entropie dont la base ne connait QUE
--      l'empreinte, a usage unique, revocable, expirant, lie a une
--      organisation ET a un role.
--   3. ADMINISTRER LES MEMBRES — role, etat, nom et identifiant
--      professionnels, sans jamais pouvoir s'elever soi-meme ni faire
--      disparaitre le dernier proprietaire actif.
--
-- L'ACTEUR VIENT DU JETON, JAMAIS DU CORPS
-- ------------------------------------------
-- `project_backend_actor()` derive l'identite de la session authentifiee. Pas
-- une seule de ces primitives n'accepte un `user_id` en parametre pour
-- designer QUI AGIT. Deux en acceptent un pour designer QUI SUBIT — modifier
-- l'adhesion d'un collegue — et les deux refusent que ce soit l'appelant.
--
-- CE QUE CETTE MIGRATION NE FAIT PAS
-- ------------------------------------
-- Elle ne rend rien signable. Elle ne touche ni `deliverables`, ni
-- `validations`, ni le registre normatif. Un `validating_engineer` cree ici
-- n'a aucune habilitation normative: celle-la se prend par le quatre-yeux, et
-- le registre national reste a 0/29.
--
-- ELLE N'ELARGIT AUCUN PRIVILEGE DU BACKEND. `eurostruct_authority_backend`
-- n'obtient que le droit d'EXECUTER les sept primitives declarees; il n'a
-- toujours aucun privilege sur aucune table, et la postcondition finale le
-- CONSTATE plutot que de le supposer.

begin;

grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. QUI FONDE, ET COMMENT ON EMPECHE UN DOUBLE-CLIC DE FONDER DEUX FOIS
-- ---------------------------------------------------------------------
-- `organizations` gagne `created_by`: sans lui, rien ne dit qui a fonde un
-- bureau, et surtout rien n'empeche deux soumissions concurrentes du meme
-- formulaire de creer deux organisations jumelles dont l'une restera
-- orpheline pour toujours.
--
-- LA CONTRAINTE EST `(created_by, lower(name))`, PAS `name` SEUL. Deux
-- bureaux differents peuvent legitimement s'appeler « Etudes Structures »;
-- une meme personne qui soumet deux fois le meme nom, non — c'est un
-- double-clic, pas une seconde intention.
alter table organizations
  add column if not exists created_by uuid references auth.users(id);

comment on column organizations.created_by is
  'Qui a fonde ce bureau. Derive du jeton par organization_bootstrap(), '
  'jamais fourni par le client. Sert aussi de cle d''idempotence avec le nom.';

create unique index if not exists organizations_fondateur_nom
  on organizations (created_by, lower(name))
  where created_by is not null;


-- ---------------------------------------------------------------------
-- 2. LES INVITATIONS — UNE EMPREINTE, PAS UN SECRET
-- ---------------------------------------------------------------------
-- LA BASE NE CONNAIT QUE `sha256(jeton)`. Une fuite de sauvegarde, une lecture
-- accidentelle, un journal trop bavard: aucun de ces incidents ne rend un
-- lien utilisable. Le secret n'existe qu'une fois, dans la reponse HTTP qui
-- l'a cree, et l'emetteur le transmet lui-meme.
--
-- AUCUNE ADRESSE ELECTRONIQUE N'EST STOCKEE, ET C'EST UNE DECISION.
-- Une invitation liee a une adresse ouvre l'enumeration: « invitez
-- untel@exemple.fr » repond differemment selon que le compte existe ou non, et
-- l'on apprend qui travaille ou. Ici l'invitation ne designe PERSONNE: elle
-- designe une organisation et un role, et le premier destinataire AUTHENTIFIE
-- qui presente le secret la consomme. `label` est un aide-memoire libre pour
-- l'emetteur; il n'entre dans aucune decision.
--
-- LE NOM ET L'IDENTIFIANT PROFESSIONNELS SONT POSES PAR L'EMETTEUR, jamais
-- par l'invite. Un `validating_engineer` qui choisirait lui-meme le nom sous
-- lequel il atteste pourrait signer sous celui d'un autre — c'est exactement
-- ce que 0009 et 0020 ferment en DERIVANT ces valeurs de l'adhesion.
create table if not exists organization_invitations (
  id              uuid primary key default gen_random_uuid(),
  org_id          uuid not null references organizations(id) on delete cascade,
  role            org_role not null,
  -- L'EMPREINTE SEULE. La contrainte de forme n'est pas cosmetique: elle
  -- refuse qu'un jour un secret en clair y soit ecrit par megarde.
  token_sha256    text not null unique
                    check (token_sha256 ~ '^[0-9a-f]{64}$'),
  label           text,
  display_name    text,
  professional_id text,
  created_by      uuid not null references auth.users(id),
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null,
  accepted_by     uuid references auth.users(id),
  accepted_at     timestamptz,
  revoked_by      uuid references auth.users(id),
  revoked_at      timestamptz,
  constraint invitation_expire_apres_creation check (expires_at > created_at),
  constraint invitation_acceptation_complete
    check ((accepted_by is null) = (accepted_at is null)),
  constraint invitation_revocation_complete
    check ((revoked_by is null) = (revoked_at is null)),
  -- USAGE UNIQUE ET ETAT UNIQUE: une invitation consommee ne peut plus etre
  -- revoquee, et une invitation revoquee ne peut plus etre consommee. Sans
  -- cette contrainte, l'ordre des deux operations deciderait du resultat.
  constraint invitation_un_seul_denouement
    check (not (accepted_at is not null and revoked_at is not null))
);

comment on table organization_invitations is
  'Un lien d''invitation. La base n''en connait que l''empreinte sha256: le '
  'secret n''existe qu''une fois, dans la reponse qui l''a cree. Aucune '
  'adresse electronique n''est stockee — une invitation liee a une adresse '
  'ouvre l''enumeration des comptes.';

create index if not exists organization_invitations_org
  on organization_invitations (org_id);

alter table organization_invitations enable row level security;
-- LES POLITIQUES S'APPLIQUENT AUSSI AU PROPRIETAIRE. Sans `force`, le role
-- qui possede la table lirait toutes les invitations de tous les bureaux.
alter table organization_invitations force row level security;


-- ---------------------------------------------------------------------
-- 3. LA CAPACITE D'ADMINISTRATION
-- ---------------------------------------------------------------------
-- `project_exiger_capacite` (0023) connaissait `lecture`, `redaction` et
-- `validation`. `administration` s'y ajoute: `owner` et `admin` uniquement,
-- membres ACTIFS. Un quatrieme message de refus au meme endroit que les trois
-- autres — plutot que quatre fonctions posant quatre questions legerement
-- differentes, dont la plus faible finirait par decider.
create or replace function project_exiger_capacite(
  target_org uuid, p_capacite text)
returns org_role
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  m record;
begin
  select role, is_active, deactivated_at into m
    from organization_members
   where org_id = target_org
     and user_id = project_backend_actor();

  if not found then
    raise exception 'vous n''etes pas membre de cette organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  if not m.is_active then
    raise exception
      'votre acces a cette organisation a ete revoque le %. La ligne '
      'd''adhesion est conservee pour l''historique; elle n''ouvre plus rien.',
      coalesce(to_char(m.deactivated_at, 'YYYY-MM-DD'), 'une date inconnue')
      using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'lecture' then
    return m.role;
  end if;

  if p_capacite = 'redaction' then
    if m.role in ('owner', 'admin', 'engineer') then
      return m.role;
    end if;
    raise exception
      'le role « % » ne redige pas de livrable dans cette organisation.',
      m.role using errcode = 'insufficient_privilege';
  end if;

  if p_capacite = 'validation' then
    if m.role = 'validating_engineer' then
      return m.role;
    end if;
    raise exception
      'le role « % » ne porte pas la validation technique dans cette '
      'organisation.', m.role using errcode = 'insufficient_privilege';
  end if;

  -- ADMINISTRATION: inviter, lister, changer un role, revoquer un acces.
  --
  -- `engineer` ET `validating_engineer` EN SONT EXCLUS, y compris le second.
  -- Porter la responsabilite technique d'un calcul et decider qui entre dans
  -- le bureau sont deux pouvoirs distincts; les confondre ferait du
  -- validateur l'administrateur de fait de sa propre supervision.
  if p_capacite = 'administration' then
    if m.role in ('owner', 'admin') then
      return m.role;
    end if;
    raise exception
      'le role « % » n''administre pas les membres de cette organisation.',
      m.role using errcode = 'insufficient_privilege';
  end if;

  raise exception
    'ATELIER_0023_CAPACITE_INCONNUE: « % » n''est pas une capacite connue.',
    p_capacite using errcode = 'internal_error';
end;
$$;


-- ---------------------------------------------------------------------
-- 4. L'ANNUAIRE, ET POURQUOI IL NE PASSE PAS PAR UNE POLITIQUE RECURSIVE
-- ---------------------------------------------------------------------
-- 0018 a mesure le probleme et l'a ecrit: une politique sur
-- `organization_members` qui interroge `organization_members` boucle — cent
-- trames dans la pile, « stack depth limit exceeded ». Sa politique de
-- lecture est donc volontairement la plus etroite possible:
-- `user_id = project_backend_actor()`. Elle ferme la recursion PAR
-- CONSTRUCTION, et refuse au passage l'annuaire des collegues.
--
-- L'ANNUAIRE EST POURTANT NECESSAIRE: un proprietaire qui ne voit pas son
-- equipe ne peut ni revoquer un acces, ni corriger un role.
--
-- LA POLITIQUE AJOUTEE N'INTERROGE AUCUNE TABLE. Elle compare l'`org_id` de
-- la ligne a un reglage de transaction que SEULE une primitive pose, et
-- seulement APRES avoir exige la capacite `administration` — laquelle lit,
-- elle, uniquement la ligne de l'appelant, ce que la politique etroite
-- autorise deja. Pas de recursion, et pas de question posee deux fois.
--
-- CE REGLAGE N'EST PAS UNE PREUVE DE CONFIANCE, ET LA DIFFERENCE EST TOUT.
-- L'autorisation est prise par `project_exiger_capacite`, qui lit la VRAIE
-- ligne d'adhesion. Le reglage ne fait que borner l'organisation dont les
-- lignes deviennent lisibles, le temps d'une transaction.
--
-- POUR QU'IL NE DEVIENNE JAMAIS UNE PORTE, IL FAUT QU'AUCUN ROLE NE PUISSE A
-- LA FOIS LE POSER ET LIRE LA TABLE. `eurostruct_authority_backend` n'a aucun
-- privilege sur `organization_members`: sa lecture est refusee par l'ACL,
-- avant meme que RLS ne soit consulte. La postcondition finale le CONSTATE —
-- c'est la propriete exacte dont depend ce mecanisme, et elle est mesuree, pas
-- supposee.
drop policy if exists members_atelier_annuaire on organization_members;
create policy members_atelier_annuaire on organization_members
  for select to eurostruct_normative_writer
  using (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid);

-- LES INVITATIONS SUIVENT LA MEME REGLE, avec la meme borne.
drop policy if exists invitations_atelier_read on organization_invitations;
create policy invitations_atelier_read on organization_invitations
  for select to eurostruct_normative_writer
  using (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid);

drop policy if exists invitations_atelier_write on organization_invitations;
create policy invitations_atelier_write on organization_invitations
  for all to eurostruct_normative_writer
  using (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid)
  with check (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid);

-- L'ACCEPTATION EST LE SEUL GESTE QUI TROUVE UNE INVITATION SANS SAVOIR DE
-- QUELLE ORGANISATION ELLE VIENT: le porteur du lien ne connait que le
-- secret. La primitive d'acceptation lit donc PAR EMPREINTE, et la politique
-- ci-dessus ne peut pas l'aider. Elle passe par une seconde politique, bornee
-- a l'empreinte exacte — jamais a une organisation, jamais a « tout ».
drop policy if exists invitations_atelier_par_empreinte on organization_invitations;
create policy invitations_atelier_par_empreinte on organization_invitations
  for all to eurostruct_normative_writer
  using (token_sha256 = nullif(
           current_setting('eurostruct.invitation_sha', true), ''))
  with check (token_sha256 = nullif(
           current_setting('eurostruct.invitation_sha', true), ''));

-- L'ECRITURE DES ADHESIONS. L'atelier ne pouvait pas en creer une seule: il
-- n'avait qu'une politique de LECTURE. La borne est la meme.
drop policy if exists members_atelier_ecriture on organization_members;
create policy members_atelier_ecriture on organization_members
  for all to eurostruct_normative_writer
  using (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid)
  with check (org_id = nullif(
           current_setting('eurostruct.annuaire_org', true), '')::uuid);

-- LA CREATION D'UNE ORGANISATION. `organizations_atelier_read` (0018) laisse
-- lire celles dont on est membre; il n'existait aucune politique d'insertion,
-- et c'est coherent: personne ne fondait rien.
drop policy if exists organizations_atelier_insert on organizations;
create policy organizations_atelier_insert on organizations
  for insert to eurostruct_normative_writer
  with check (created_by = project_backend_actor());


-- ---------------------------------------------------------------------
-- 5. AMORCER SON ORGANISATION — ATOMIQUEMENT
-- ---------------------------------------------------------------------
-- L'ORGANISATION ET SON PROPRIETAIRE NAISSENT ENSEMBLE. Une fonction est une
-- transaction: les deux `insert` reussissent ou aucun ne reste. Un appelant
-- qui enchainerait deux ordres laisserait, sur incident au second, une
-- organisation SANS proprietaire — un bureau que personne ne peut
-- administrer, et qu'il faudrait sortir de la par un `insert` a la main.
--
-- LE DOUBLE-CLIC NE FONDE PAS DEUX BUREAUX. Le verrou consultatif serialise
-- deux soumissions concurrentes du meme formulaire; l'index unique tranche le
-- cas ou la seconde arrive apres la premiere. Dans les deux cas la primitive
-- rend l'organisation DEJA CREEE au lieu d'en creer une jumelle: c'est ce que
-- l'utilisateur voulait, une fois.
create or replace function organization_bootstrap(
  p_name text, p_country country_code, p_display_name text default null,
  p_professional_id text default null)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := project_backend_actor();
  nom text := btrim(coalesce(p_name, ''));
  nouvelle uuid;
begin
  if acteur is null then
    raise exception
      'aucun acteur authentifie: on ne fonde pas une organisation au nom de '
      'personne.' using errcode = 'insufficient_privilege';
  end if;
  if nom = '' then
    raise exception
      'le nom de l''organisation est vide. Un bureau sans nom ne peut figurer '
      'sur aucune note de calcul.' using errcode = 'check_violation';
  end if;
  if length(nom) > 200 then
    raise exception 'le nom de l''organisation depasse 200 caracteres.'
      using errcode = 'check_violation';
  end if;

  -- LE VERROU EST DE TRANSACTION, ET PORTE SUR (ACTEUR, NOM). Deux appels
  -- concurrents du MEME acteur avec le MEME nom s'attendent; deux acteurs
  -- differents ne se genent pas.
  perform pg_advisory_xact_lock(hashtext(acteur::text || '|' || lower(nom)));

  select id into nouvelle
    from organizations
   where created_by = acteur and lower(name) = lower(nom);
  if found then
    -- IDEMPOTENT, ET DIT COMME TEL. Rendre l'existante est ce que l'appelant
    -- voulait; en creer une seconde lui donnerait deux bureaux dont il ne
    -- saurait pas lequel est le sien.
    return nouvelle;
  end if;

  -- L'IDENTIFIANT EST TIRE ICI, ET PAS PAR `returning`. CE N'EST PAS UN
  -- DETAIL DE STYLE, C'EST UNE MESURE.
  --
  -- `insert ... returning` applique les politiques de LECTURE a la ligne
  -- rendue. Celle d'`organizations` (0018) est
  -- `using (project_actor_is_member(id))`: a cet instant precis, l'adhesion
  -- `owner` n'existe pas encore — elle est creee deux lignes plus bas — donc
  -- le fondateur n'est pas membre, la lecture est refusee, et PostgreSQL rend
  -- « new row violates row-level security policy for table "organizations" ».
  -- Un message qui accuse l'ECRITURE alors que c'est la RELECTURE qui a
  -- echoue: on cherche la clause `with check` pendant que le probleme est
  -- dans la clause `using` d'une autre politique.
  --
  -- Mesure du jour, sur ce chemin exact: predicat d'insertion `true`,
  -- privilege `INSERT` accorde, politique permissive presente — et refus.
  -- Tirer l'identifiant supprime la relecture, donc la question.
  nouvelle := gen_random_uuid();
  insert into organizations (id, name, country, created_by)
  values (nouvelle, nom, p_country, acteur);

  -- LA BORNE DE L'ANNUAIRE EST POSEE ICI, sur l'organisation qu'on vient de
  -- creer et dont on est, par construction, le fondateur.
  perform set_config('eurostruct.annuaire_org', nouvelle::text, true);

  insert into organization_members
    (org_id, user_id, role, display_name, professional_id, is_active)
  values (nouvelle, acteur, 'owner',
          nullif(btrim(coalesce(p_display_name, '')), ''),
          nullif(btrim(coalesce(p_professional_id, '')), ''), true);

  perform set_config('eurostruct.annuaire_org', '', true);
  return nouvelle;
end;
$$;

comment on function organization_bootstrap is
  'Fonde une organisation et son proprietaire EN UNE transaction. L''acteur '
  'vient du jeton, jamais du corps. Un second appel du meme acteur avec le '
  'meme nom rend l''organisation deja creee.';


-- LES BUREAUX DE L'APPELANT, ET SON ROLE DANS CHACUN.
--
-- SEPAREE DE `project_workspace_list()` DELIBEREMENT. Un compte tout neuf a
-- zero projet ET zero organisation; un compte qui vient de fonder son bureau a
-- zero projet et UNE organisation. Les deux ecrans a montrer ne sont pas les
-- memes — « creez votre bureau » d'un cote, « creez votre premier projet » de
-- l'autre — et une seule liste vide ne permet pas de les distinguer.
--
-- ELLE N'A BESOIN D'AUCUNE BORNE D'ANNUAIRE: elle ne lit que les lignes de
-- l'appelant, ce que la politique etroite de 0018 autorise deja.
create or replace function project_workspace_organisations()
returns table (organization_id uuid, name text, country country_code,
               member_role org_role)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select o.id, o.name, o.country, m.role
    from organization_members m
    join organizations o on o.id = m.org_id
   where m.user_id = project_backend_actor()
     and m.is_active
   order by o.name;
$$;

comment on function project_workspace_organisations is
  'Les organisations OU L''APPELANT EST MEMBRE ACTIF, et son role dans '
  'chacune. Un membre desactive n''en voit aucune: sa ligne survit pour '
  'l''historique, elle n''ouvre plus rien.';


-- ---------------------------------------------------------------------
-- 6. INVITER
-- ---------------------------------------------------------------------
-- LE SECRET N'ARRIVE JAMAIS ICI. L'application tire une valeur a forte
-- entropie, en calcule le sha256, et n'envoie QUE l'empreinte. La base ne
-- peut donc pas fuiter ce qu'elle ne detient pas.
--
-- UN `admin` NE DONNE PAS PLUS QUE SON POUVOIR. Il invite `admin`, `engineer`,
-- `validating_engineer` ou `viewer`; il n'invite pas un `owner`. Sans cette
-- regle, un administrateur se fabriquerait un complice proprietaire et
-- deviendrait proprietaire par la bande.
create or replace function organization_invitation_create(
  p_org uuid, p_role org_role, p_token_sha text, p_label text default null,
  p_display_name text default null, p_professional_id text default null,
  p_ttl interval default interval '14 days')
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  mon_role org_role;
  acteur uuid := project_backend_actor();
  nouvelle uuid;
begin
  mon_role := project_exiger_capacite(p_org, 'administration');

  if p_token_sha !~ '^[0-9a-f]{64}$' then
    raise exception
      'l''empreinte de l''invitation n''est pas un sha256 hexadecimal '
      'minuscule. La base ne stocke QUE des empreintes: un secret en clair '
      'ici serait un secret publie.' using errcode = 'check_violation';
  end if;

  if mon_role = 'admin' and p_role = 'owner' then
    raise exception
      'un « admin » n''invite pas un « owner »: il donnerait plus que son '
      'propre pouvoir, et deviendrait proprietaire par la bande.'
      using errcode = 'insufficient_privilege';
  end if;

  if p_ttl <= interval '0' or p_ttl > interval '90 days' then
    raise exception
      'la duree de validite doit etre comprise entre zero et quatre-vingt-dix '
      'jours. Un lien qui n''expire jamais est un mot de passe permanent.'
      using errcode = 'check_violation';
  end if;

  -- MEME REGLE QU'A LA FONDATION: l'identifiant est tire ici. `returning`
  -- applique la politique de LECTURE a la ligne rendue, et une politique de
  -- lecture qui refuserait ferait accuser l'ecriture d'un refus qui n'est pas
  -- le sien.
  nouvelle := gen_random_uuid();
  perform set_config('eurostruct.annuaire_org', p_org::text, true);
  insert into organization_invitations
    (id, org_id, role, token_sha256, label, display_name, professional_id,
     created_by, expires_at)
  values (nouvelle, p_org, p_role, p_token_sha,
          nullif(btrim(coalesce(p_label, '')), ''),
          nullif(btrim(coalesce(p_display_name, '')), ''),
          nullif(btrim(coalesce(p_professional_id, '')), ''),
          acteur, now() + p_ttl);
  perform set_config('eurostruct.annuaire_org', '', true);

  return nouvelle;
end;
$$;

comment on function organization_invitation_create is
  'Emet une invitation. Recoit l''EMPREINTE du secret, jamais le secret. Un '
  'admin ne peut pas inviter un owner.';


-- L'ACCEPTATION. Le seul geste ou l'appelant ne sait pas d'avance de quelle
-- organisation il s'agit — c'est le secret qui le lui apprend.
--
-- LE DESTINATAIRE EST AUTHENTIFIE. Un lien seul ne suffit pas: il faut aussi
-- un jeton valide, faute de quoi l'adhesion ne designerait personne.
--
-- LE REFUS EST LE MEME DANS LES QUATRE CAS — inconnue, expiree, revoquee,
-- deja consommee. Distinguer « ce lien n'existe pas » de « ce lien a expire »
-- apprendrait a qui essaie des liens au hasard quand il a vise juste.
create or replace function organization_invitation_accept(p_token_sha text)
returns uuid
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := project_backend_actor();
  inv record;
  deja record;
begin
  if acteur is null then
    raise exception
      'aucun acteur authentifie: une invitation ne s''accepte pas anonymement.'
      using errcode = 'insufficient_privilege';
  end if;
  if p_token_sha !~ '^[0-9a-f]{64}$' then
    raise exception 'invitation inconnue, expiree, revoquee ou deja utilisee.'
      using errcode = 'insufficient_privilege';
  end if;

  perform set_config('eurostruct.invitation_sha', p_token_sha, true);

  select * into inv
    from organization_invitations
   where token_sha256 = p_token_sha
     for update;

  if not found
     or inv.accepted_at is not null
     or inv.revoked_at is not null
     or inv.expires_at <= now() then
    perform set_config('eurostruct.invitation_sha', '', true);
    raise exception 'invitation inconnue, expiree, revoquee ou deja utilisee.'
      using errcode = 'insufficient_privilege';
  end if;

  perform set_config('eurostruct.annuaire_org', inv.org_id::text, true);

  select * into deja
    from organization_members
   where org_id = inv.org_id and user_id = acteur;

  if found then
    -- DEJA MEMBRE. L'invitation est consommee — elle est a usage unique et
    -- elle a servi — mais le role N'EST PAS ECRASE: une invitation `viewer`
    -- presentee par un `owner` le retrograderait, et ce serait une elevation
    -- a l'envers tout aussi grave.
    update organization_invitations
       set accepted_by = acteur, accepted_at = now()
     where id = inv.id;
    perform set_config('eurostruct.annuaire_org', '', true);
    perform set_config('eurostruct.invitation_sha', '', true);
    return inv.org_id;
  end if;

  insert into organization_members
    (org_id, user_id, role, display_name, professional_id, is_active)
  values (inv.org_id, acteur, inv.role, inv.display_name,
          inv.professional_id, true);

  update organization_invitations
     set accepted_by = acteur, accepted_at = now()
   where id = inv.id;

  perform set_config('eurostruct.annuaire_org', '', true);
  perform set_config('eurostruct.invitation_sha', '', true);
  return inv.org_id;
end;
$$;

comment on function organization_invitation_accept is
  'Consomme une invitation par son EMPREINTE, sous identite authentifiee. '
  'Usage unique. Le nom et l''identifiant professionnels viennent de '
  'l''invitation — poses par l''organisation — jamais de l''invite.';


create or replace function organization_invitation_revoke(
  p_org uuid, p_invitation uuid)
returns boolean
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := project_backend_actor();
  touches integer;
begin
  perform project_exiger_capacite(p_org, 'administration');
  perform set_config('eurostruct.annuaire_org', p_org::text, true);

  update organization_invitations
     set revoked_by = acteur, revoked_at = now()
   where id = p_invitation
     and org_id = p_org
     and accepted_at is null
     and revoked_at is null;
  get diagnostics touches = row_count;

  perform set_config('eurostruct.annuaire_org', '', true);

  if touches <> 1 then
    -- LE REFUS NE DIT PAS LEQUEL DES TROIS CAS. Un message qui distinguerait
    -- « inconnue » de « deja consommee » renseignerait sur des invitations
    -- d'autres bureaux.
    raise exception
      'aucune invitation revocable sous cet identifiant: elle est inconnue, '
      'deja consommee ou deja revoquee.' using errcode = 'insufficient_privilege';
  end if;
  return true;
end;
$$;


-- LA LISTE. ELLE NE REND NI LE SECRET NI SON EMPREINTE — l'empreinte suffirait
-- a reconnaitre un lien intercepte ailleurs, et n'aide en rien l'ecran.
create or replace function organization_invitation_list(p_org uuid)
returns table (
  invitation_id uuid, role org_role, label text, display_name text,
  professional_id text, created_at timestamptz, expires_at timestamptz,
  accepted_at timestamptz, revoked_at timestamptz, state text)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
begin
  perform project_exiger_capacite(p_org, 'administration');
  perform set_config('eurostruct.annuaire_org', p_org::text, true);

  return query
    select i.id, i.role, i.label, i.display_name, i.professional_id,
           i.created_at, i.expires_at, i.accepted_at, i.revoked_at,
           case
             when i.accepted_at is not null then 'accepted'
             when i.revoked_at  is not null then 'revoked'
             when i.expires_at <= now()     then 'expired'
             else 'pending'
           end
      from organization_invitations i
     where i.org_id = p_org
     order by i.created_at desc;
end;
$$;


-- ---------------------------------------------------------------------
-- 7. ADMINISTRER LES MEMBRES
-- ---------------------------------------------------------------------
create or replace function organization_member_list(p_org uuid)
returns table (
  user_id uuid, role org_role, display_name text, professional_id text,
  is_active boolean, created_at timestamptz, deactivated_at timestamptz,
  is_me boolean)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid := project_backend_actor();
begin
  perform project_exiger_capacite(p_org, 'administration');
  perform set_config('eurostruct.annuaire_org', p_org::text, true);

  return query
    select m.user_id, m.role, m.display_name, m.professional_id, m.is_active,
           m.created_at, m.deactivated_at, (m.user_id = acteur)
      from organization_members m
     where m.org_id = p_org
     order by m.is_active desc, m.role, m.created_at;
end;
$$;


-- LES QUATRE REGLES QUI TIENNENT CETTE PRIMITIVE
-- ------------------------------------------------
--   1. PAS D'AUTO-ELEVATION — ni dans un sens ni dans l'autre: l'appelant ne
--      touche pas sa propre ligne. Se promouvoir `owner`, ou se donner
--      `validating_engineer` pour attester son propre travail, sont le meme
--      geste vu de deux cotes.
--   2. UN `admin` NE DONNE PAS PLUS QUE SON POUVOIR: il ne cree pas d'`owner`
--      et ne touche pas la ligne d'un `owner`.
--   3. LE DERNIER `owner` ACTIF NE DISPARAIT PAS. Ni par changement de role,
--      ni par desactivation. Un bureau sans proprietaire actif n'a plus
--      personne pour administrer ses membres, et il faudrait un `insert` a la
--      main pour l'en sortir — le cul-de-sac de depart, un cran plus loin.
--   4. `validating_engineer` NE S'AUTO-ATTRIBUE JAMAIS, corollaire de la 1.
create or replace function organization_member_update(
  p_org uuid, p_user uuid, p_role org_role default null,
  p_is_active boolean default null, p_display_name text default null,
  p_professional_id text default null, p_toucher_noms boolean default false)
returns boolean
language plpgsql
volatile
security definer
set search_path = public, pg_temp
as $$
declare
  mon_role org_role;
  acteur uuid := project_backend_actor();
  cible record;
  futur_role org_role;
  futur_actif boolean;
  owners_apres integer;
  touches integer;
begin
  mon_role := project_exiger_capacite(p_org, 'administration');

  if p_user = acteur then
    raise exception
      'on ne modifie pas sa propre adhesion. Se promouvoir, ou se donner le '
      'role qui valide son propre travail, sont le meme geste vu de deux '
      'cotes.' using errcode = 'insufficient_privilege';
  end if;

  perform set_config('eurostruct.annuaire_org', p_org::text, true);

  select * into cible
    from organization_members
   where org_id = p_org and user_id = p_user
     for update;
  if not found then
    perform set_config('eurostruct.annuaire_org', '', true);
    raise exception 'cette personne n''est pas membre de cette organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  futur_role  := coalesce(p_role, cible.role);
  futur_actif := coalesce(p_is_active, cible.is_active);

  if mon_role = 'admin' and (cible.role = 'owner' or futur_role = 'owner') then
    perform set_config('eurostruct.annuaire_org', '', true);
    raise exception
      'un « admin » ne cree ni ne modifie un « owner »: il donnerait plus que '
      'son propre pouvoir.' using errcode = 'insufficient_privilege';
  end if;

  -- LE DERNIER PROPRIETAIRE ACTIF. On compte ce que la table PORTERAIT apres
  -- le changement, pas ce qu'elle porte avant.
  select count(*) into owners_apres
    from organization_members m
   where m.org_id = p_org
     and m.role = 'owner' and m.is_active
     and m.user_id <> p_user;
  if futur_role = 'owner' and futur_actif then
    owners_apres := owners_apres + 1;
  end if;
  if owners_apres = 0 then
    perform set_config('eurostruct.annuaire_org', '', true);
    raise exception
      'cette modification laisserait l''organisation sans aucun proprietaire '
      'actif. Designer un autre proprietaire d''abord.'
      using errcode = 'insufficient_privilege';
  end if;

  update organization_members
     set role = futur_role,
         is_active = futur_actif,
         deactivated_at = case when futur_actif then null
                               else coalesce(deactivated_at, now()) end,
         display_name = case when p_toucher_noms
                             then nullif(btrim(coalesce(p_display_name, '')), '')
                             else display_name end,
         professional_id = case when p_toucher_noms
                                then nullif(btrim(coalesce(p_professional_id, '')), '')
                                else professional_id end
   where org_id = p_org and user_id = p_user;
  get diagnostics touches = row_count;

  perform set_config('eurostruct.annuaire_org', '', true);

  if touches <> 1 then
    raise exception
      'ATELIER_0024_MODIFICATION_SANS_EFFET: la mise a jour n''a touche % '
      'ligne(s). Un refus qui se presente comme un succes est pire qu''un '
      'refus.', touches using errcode = 'insufficient_privilege';
  end if;
  return true;
end;
$$;


-- ---------------------------------------------------------------------
-- 8. PROPRIETE ET ACCES
-- ---------------------------------------------------------------------
do $$
declare
  f text;
begin
  foreach f in array array[
    'organization_bootstrap(text, country_code, text, text)',
    'organization_invitation_create(uuid, org_role, text, text, text, text, interval)',
    'organization_invitation_accept(text)',
    'organization_invitation_revoke(uuid, uuid)',
    'organization_invitation_list(uuid)',
    'organization_member_list(uuid)',
    'organization_member_update(uuid, uuid, org_role, boolean, text, text, boolean)',
    'project_workspace_organisations()']
  loop
    execute format('alter function %s owner to eurostruct_normative_writer', f);
    execute format('revoke all on function %s from public', f);
    execute format('grant execute on function %s to eurostruct_authority_backend', f);
  end loop;

  -- `project_exiger_capacite` A ETE REMPLACEE: elle repart de `acldefault`.
  -- Elle reste INTERNE — aucun geste du parcours ne lui correspond.
  execute 'alter function project_exiger_capacite(uuid, text) '
          'owner to eurostruct_normative_writer';
  execute 'revoke all on function project_exiger_capacite(uuid, text) from public';
  execute 'grant execute on function project_exiger_capacite(uuid, text) '
          'to eurostruct_normative_writer';
end
$$;

-- LES TABLES QUE L'ATELIER ECRIT DESORMAIS.
grant select, insert, update on organization_invitations
  to eurostruct_normative_writer;
grant select, insert, update on organization_members
  to eurostruct_normative_writer;
grant insert on organizations to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 9. POSTCONDITIONS — CE DONT CE MECANISME DEPEND, MESURE ET NON SUPPOSE
-- ---------------------------------------------------------------------

-- LA PROPRIETE EXACTE DONT DEPEND LA BORNE D'ANNUAIRE.
--
-- La politique `members_atelier_annuaire` ouvre les lignes d'une organisation
-- designee par un reglage de transaction. Cela ne devient une PORTE que si un
-- role peut a la fois poser ce reglage et lire la table. Le backend
-- authentifie n'a aucun privilege de table — c'est le principe de 0018 — et
-- c'est CE fait, et lui seul, qui rend la borne sure.
--
-- SI CE CONTROLE DEVIENT ROUGE, LE MECANISME EST CASSE, pas seulement le test.
do $$
declare
  fautives text := '';
  t text;
begin
  foreach t in array array['organization_members', 'organization_invitations',
                           'organizations']
  loop
    if has_table_privilege('eurostruct_authority_backend', t, 'SELECT')
       or has_table_privilege('eurostruct_authority_backend', t, 'INSERT')
       or has_table_privilege('eurostruct_authority_backend', t, 'UPDATE')
       or has_table_privilege('eurostruct_authority_backend', t, 'DELETE') then
      fautives := fautives || t || ' ';
    end if;
  end loop;

  if fautives <> '' then
    raise exception
      'ATELIER_0024_BACKEND_ATTEINT_LES_TABLES: % . La borne d''annuaire est '
      'un reglage de transaction; elle n''est sure que parce qu''aucun role '
      'capable de la poser n''atteint ces tables. Ce privilege la transforme '
      'en porte ouverte sur l''annuaire de n''importe quelle organisation.',
      fautives using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- LES SEPT PRIMITIVES EXIGENT TOUTES UNE CAPACITE, OU DERIVENT L'ACTEUR.
--
-- Une primitive d'entree qui ne ferait ni l'un ni l'autre accepterait un
-- `org_id` sur parole — exactement ce que 0018 refuse pour les projets.
do $$
declare
  nom text;
  corps text;
  sans_garde text := '';
begin
  foreach nom in array array[
    'organization_bootstrap', 'organization_invitation_create',
    'organization_invitation_accept', 'organization_invitation_revoke',
    'organization_invitation_list', 'organization_member_list',
    'organization_member_update', 'project_workspace_organisations']
  loop
    select pg_get_functiondef(p.oid) into corps
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom
     limit 1;
    if corps is null then
      raise exception
        'ATELIER_0024_PRIMITIVE_ABSENTE: % n''existe pas.', nom
        using errcode = 'undefined_function';
    end if;
    if position('project_exiger_capacite' in corps) = 0
       and position('project_backend_actor' in corps) = 0 then
      sans_garde := sans_garde || nom || ' ';
    end if;
  end loop;

  if sans_garde <> '' then
    raise exception
      'ATELIER_0024_SANS_GARDE: % n''exige/exigent aucune capacite et ne '
      'derivent aucun acteur: elles croiraient leur appelant sur parole.',
      sans_garde using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- AUCUNE PRIMITIVE N'ACCEPTE L'IDENTITE DE CELUI QUI AGIT.
--
-- Deux en acceptent une pour designer QUI SUBIT (`organization_member_update`
-- et rien d'autre). Le reste derive l'acteur. Ce controle lit les NOMS des
-- arguments: un `p_actor`, un `p_acting_user` ou un `p_as` apparu un jour
-- signalerait que l'identite est redevenue un parametre.
do $$
declare
  nom text;
  arguments text;
  fautives text := '';
begin
  foreach nom in array array[
    'organization_bootstrap', 'organization_invitation_create',
    'organization_invitation_accept', 'organization_invitation_revoke',
    'organization_invitation_list', 'organization_member_list',
    'organization_member_update', 'project_workspace_organisations']
  loop
    select pg_get_function_arguments(p.oid) into arguments
      from pg_proc p join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = nom
     limit 1;
    if arguments ~* '(p_actor|p_acting|p_as_user|p_caller|p_on_behalf)' then
      fautives := fautives || nom || ' ';
    end if;
  end loop;

  if fautives <> '' then
    raise exception
      'ATELIER_0024_ACTEUR_EN_PARAMETRE: % accepte(nt) l''identite de celui '
      'qui agit. Elle vient du jeton, jamais du corps.', fautives
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- LA TABLE DES INVITATIONS NE PORTE AUCUNE COLONNE DE SECRET EN CLAIR, ET
-- AUCUNE ADRESSE.
do $$
declare
  fautives text := '';
  c text;
begin
  for c in
    select column_name from information_schema.columns
     where table_schema = 'public'
       and table_name = 'organization_invitations'
  loop
    if c ~* '(email|mail|token$|secret|password|adresse)' then
      fautives := fautives || c || ' ';
    end if;
  end loop;

  if fautives <> '' then
    raise exception
      'ATELIER_0024_INVITATION_TROP_BAVARDE: colonne(s) % . La base ne '
      'connait que l''empreinte du secret, et aucune adresse: une invitation '
      'liee a une adresse ouvre l''enumeration des comptes.', fautives
      using errcode = 'check_violation';
  end if;
end;
$$;

-- L'INVITATION EST A USAGE UNIQUE, EXPIRANTE ET REVOCABLE — PAR CONTRAINTE.
--
-- Les quatre contraintes valent mieux que quatre `if` dans la primitive: une
-- restauration, un import ou une migration future ne les contourne pas.
do $$
declare
  attendues text[] := array[
    'invitation_expire_apres_creation', 'invitation_acceptation_complete',
    'invitation_revocation_complete', 'invitation_un_seul_denouement'];
  manquantes text := '';
  c text;
begin
  foreach c in array attendues loop
    if not exists (select 1 from pg_constraint
                    where conname = c
                      and conrelid = 'organization_invitations'::regclass) then
      manquantes := manquantes || c || ' ';
    end if;
  end loop;

  if manquantes <> '' then
    raise exception
      'ATELIER_0024_CONTRAINTE_ABSENTE: % . Un lien d''invitation qui '
      'n''expire pas, ou qui peut etre a la fois consomme et revoque, n''est '
      'plus a usage unique.', manquantes using errcode = 'check_violation';
  end if;

  if not exists (select 1 from pg_constraint
                  where contype = 'u'
                    and conrelid = 'organization_invitations'::regclass) then
    raise exception
      'ATELIER_0024_EMPREINTE_NON_UNIQUE: deux invitations pourraient '
      'partager une empreinte.' using errcode = 'check_violation';
  end if;
end;
$$;

-- LE DOUBLE-CLIC NE FONDE PAS DEUX BUREAUX — PAR INDEX, pas par prudence.
do $$
begin
  if not exists (select 1 from pg_indexes
                  where schemaname = 'public'
                    and indexname = 'organizations_fondateur_nom') then
    raise exception
      'ATELIER_0024_IDEMPOTENCE_ABSENTE: sans index unique sur (fondateur, '
      'nom), deux soumissions concurrentes du meme formulaire creent deux '
      'organisations jumelles dont l''une restera orpheline.'
      using errcode = 'check_violation';
  end if;
end;
$$;

-- LES INVITATIONS SONT CLOISONNEES, ET `force` LE REND VRAI MEME POUR LE
-- PROPRIETAIRE DE LA TABLE.
do $$
begin
  if not exists (select 1 from pg_class
                  where relname = 'organization_invitations'
                    and relrowsecurity and relforcerowsecurity) then
    raise exception
      'ATELIER_0024_INVITATIONS_SANS_RLS: la table des invitations n''est pas '
      'cloisonnee, ou ne l''est pas pour son proprietaire.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- LE DROIT DE CREER DANS `public` NE RESTE PAS.
--
-- Cette migration l'a pris en tete de fichier pour poser une table, un index
-- et huit fonctions. Le garder ferait de `eurostruct_normative_writer` un role
-- capable d'ajouter n'importe quoi au schema APRES la finalisation — et le
-- controle de derive de 0011 le refuse, a juste titre:
-- `AUTHORITY_0011_SCHEMA_CREATE_RETAINED`. Mesure du jour: ce controle est
-- devenu ROUGE des l'application de 0024, exactement pour cette raison.
--
-- LA REVOCATION EST ENDOSSEE: on endosse le DONNEUR de l'octroi, jamais un
-- role choisi par la migration. Un `revoke` emis par quelqu'un d'autre que le
-- donneur ne retire rien, et ne dit pas qu'il n'a rien retire.
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
        'ATELIER_0024_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'ATELIER_0024_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
        'donneur « % » a echoue (%). Le privilege CREATE resterait, et rien '
        'd''autre ne le dirait.', donneur, sqlerrm
        using errcode = 'insufficient_privilege';
    end;
  end loop;
end;
$$;

-- POSTCONDITION: le droit ne reste pas. Constate, pas suppose.
do $$
begin
  if exists (
    select 1 from pg_namespace n, aclexplode(n.nspacl) a
     where n.nspname = 'public'
       and a.privilege_type = 'CREATE'
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid
  ) then
    raise exception
      'ATELIER_0024_SCHEMA_CREATE_RETAINED: eurostruct_normative_writer garde '
      'CREATE sur public apres cette migration.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
