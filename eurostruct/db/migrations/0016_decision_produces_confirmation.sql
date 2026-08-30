-- 0016 — UNE DECISION CONSOMMEE PRODUIT SON EFFET NORMATIF
--
-- CE QUI MANQUAIT
-- ----------------
-- `normative_decision_consume()` faisait passer la decision a CONSUMED et
-- ecrivait l'audit. Il n'inserait rien dans `normative_rule_confirmations`,
-- que le provider est seul a lire. Deux chemins existaient donc, disjoints:
--
--   navigateur -> proposer / approuver / consommer      (etat)
--   confirmations deja presentes -> passerelle -> strict (effet)
--
-- Aucun code ne reliait le premier au second. Mesure: apres un cycle complet
-- A/B consomme par les routes publiques, le calcul strict bloquait encore sur
-- le parametre vise, et la table portait zero confirmation.
--
-- CE QUE CETTE MIGRATION AJOUTE
-- ------------------------------
--   1. `review_package` sur la decision — LE DOSSIER, fige des la proposition;
--   2. `decision_id` sur la confirmation — le lien, avec sa cle etrangere;
--   3. la consommation produit DEUX attestations, une par regard, dans LA
--      MEME transaction que le passage a CONSUMED;
--   4. le declencheur de confirmation reconnait ce chemin, et n'y accepte
--      NI verificateur, NI contenu, NI habilitation fournis par un appelant:
--      les trois sont relus sur la decision.
--
-- AUCUNE VALEUR NORMATIVE N'EST CREEE ICI. Le dossier vient de l'appelant, il
-- est fige a la proposition, et les deux ingenieurs approuvent exactement ce
-- contenu-la. La base garantit qu'il ne change pas entre les deux regards.

-- ---------------------------------------------------------------------
-- LE DROIT DE CREER, RENDU PUIS REPRIS
-- ---------------------------------------------------------------------
-- Chaque migration de 0011 a 0015 rend `CREATE on schema public` au writer
-- pour la duree de son application, puis le reprend. Sans lui,
-- `alter function ... owner to eurostruct_normative_writer` echoue: changer
-- de proprietaire exige que le NOUVEAU proprietaire puisse creer dans le
-- schema. Mesure sur base jetable: « permission denied for schema public ».
--
-- Le droit est repris a la fin du fichier, par la meme revocation ENDOSSEE
-- que 0011 a 0015 — pas par un `revoke` nu, qui est un voeu et non une
-- commande: un REVOKE emis par un role qui n'est pas le DONNEUR n'a aucun
-- effet, sans erreur ni avertissement.
grant create on schema public to eurostruct_normative_writer;


-- ---------------------------------------------------------------------
-- 1. LE DOSSIER, PORTE PAR LA DECISION ET FIGE DES LA PROPOSITION
-- ---------------------------------------------------------------------
alter table normative_authority_decisions
  add column if not exists review_package jsonb;

comment on column normative_authority_decisions.review_package is
  'Le DOSSIER DE REVUE presente aux deux ingenieurs, fige a la proposition. '
  'A et B approuvent exactement ce contenu: sans lui, « B a approuve » ne '
  'dirait pas QUOI. Fige par check_normative_decision_transition().';

-- LE DOSSIER EST DANS LE SOCLE FIGE. Sans cette ligne, il aurait pu etre
-- remplace entre l'approbation de B et la consommation — B aurait approuve un
-- contenu et la base en aurait produit un autre.
create or replace function check_normative_decision_transition() returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if new.id              is distinct from old.id
     or new.subject_kind    is distinct from old.subject_kind
     or new.subject_id      is distinct from old.subject_id
     or new.org_id          is distinct from old.org_id
     or new.country_code    is distinct from old.country_code
     or new.standard_family is distinct from old.standard_family
     or new.part            is distinct from old.part
     or new.edition         is distinct from old.edition
     or new.permission      is distinct from old.permission
     or new.proposer_id     is distinct from old.proposer_id
     or new.proposal_source_grant_id is distinct from old.proposal_source_grant_id
     or new.proposed_at     is distinct from old.proposed_at
     or new.correlation_id  is distinct from old.correlation_id
     or new.reason          is distinct from old.reason
     -- LE DOSSIER AUSSI, et c'est le point de cette migration.
     or new.review_package  is distinct from old.review_package then
    raise exception
      'decision %: son objet, sa portee, son proposant, sa source, sa '
      'correlation et SON DOSSIER sont figes a la creation. Seul l''etat '
      'progresse.', old.id
      using errcode = 'insufficient_privilege';
  end if;

  if old.state = 'PENDING' and new.state = 'APPROVED' then
    return new;
  elsif old.state = 'APPROVED' and new.state = 'CONSUMED' then
    if new.approver_id is distinct from old.approver_id
       or new.approval_source_grant_id is distinct from old.approval_source_grant_id
       or new.approved_at is distinct from old.approved_at then
      raise exception
        'decision %: la consommation ne modifie pas l''approbation.', old.id
        using errcode = 'insufficient_privilege';
    end if;
    return new;
  end if;

  raise exception
    'decision %: transition « % » -> « % » interdite. Le cycle est '
    'PENDING -> APPROVED -> CONSUMED, et il ne remonte pas.',
    old.id, old.state, new.state
    using errcode = 'check_violation';
end;
$$;

-- ---------------------------------------------------------------------
-- 2. LE LIEN ENTRE L'EFFET ET LA DECISION QUI L'A PRODUIT
-- ---------------------------------------------------------------------
alter table normative_rule_confirmations
  add column if not exists decision_id uuid
    references normative_authority_decisions(id) on delete restrict;

comment on column normative_rule_confirmations.decision_id is
  'La decision d''autorite qui a produit cette attestation. NULL pour les '
  'attestations anterieures a 0016. Non nul, elle impose que le verificateur '
  'soit l''un des deux principals de la decision et que le contenu soit son '
  'dossier fige.';

-- IDEMPOTENCE IMPOSEE PAR LA BASE, PAS PAR L'APPELANT.
--
-- Au plus une attestation par (decision, verificateur): une seconde
-- consommation, un rejeu ou une insertion directe ne peuvent pas produire un
-- troisieme regard. Deux lignes au maximum, celles que la decision nomme.
create unique index if not exists normative_confirmation_par_decision
  on normative_rule_confirmations (decision_id, verifier_id)
  where decision_id is not null;

-- ---------------------------------------------------------------------
-- 3. LE DECLENCHEUR RECONNAIT LE CHEMIN DE LA DECISION
-- ---------------------------------------------------------------------
-- Il ne remplace pas les controles existants: il les PRECEDE d'un bloc qui,
-- quand `decision_id` est renseigne, relit tout sur la decision au lieu de
-- faire confiance a la ligne. `auth.uid()` ne decide plus qui a signe: la
-- decision le dit, et elle est immuable.
create or replace function normative_confirmation_depuis_decision()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  d normative_authority_decisions;
  source uuid;
begin
  if new.decision_id is null then
    return new;   -- chemin historique: le declencheur suivant s'en charge
  end if;

  -- LA DECISION FAIT FOI, ET ON LA VERROUILLE POUR LA LIRE.
  select * into d from normative_authority_decisions
   where id = new.decision_id for share;
  if not found then
    raise exception
      'confirmation refusee: la decision % n''existe pas.', new.decision_id
      using errcode = 'foreign_key_violation';
  end if;

  -- SEULE UNE DECISION CONSOMMEE PRODUIT UN EFFET. Une proposition seule, une
  -- approbation non consommee: aucune des deux n'ecrit ici.
  if d.state <> 'CONSUMED' then
    raise exception
      'confirmation refusee: la decision % est « % ». Seule une decision '
      'CONSOMMEE produit un effet normatif.', d.id, d.state
      using errcode = 'insufficient_privilege';
  end if;

  -- DEUX PRINCIPALS DISTINCTS, RELUS SUR LA DECISION.
  if d.approver_id is null or d.approver_id = d.proposer_id then
    raise exception
      'confirmation refusee: la decision % ne porte pas deux principals '
      'distincts.', d.id
      using errcode = 'check_violation';
  end if;

  -- LE VERIFICATEUR N'EST PAS FOURNI: il est l'un des deux, et rien d'autre.
  if new.verifier_id = d.proposer_id then
    source := d.proposal_source_grant_id;
  elsif new.verifier_id = d.approver_id then
    source := d.approval_source_grant_id;
  else
    raise exception
      'confirmation refusee: % n''est ni le proposant ni l''approbateur de la '
      'decision %.', new.verifier_id, d.id
      using errcode = 'insufficient_privilege';
  end if;

  -- LE CONTENU EST CELUI DU DOSSIER FIGE. Un appelant qui inserait
  -- directement ne pourrait donc que reproduire ce que le quatre-yeux a deja
  -- sanctionne — et l'index unique l'empeche de le faire deux fois.
  if d.review_package is null then
    raise exception
      'confirmation refusee: la decision % ne porte aucun dossier de revue. '
      'Deux ingenieurs ne peuvent pas avoir approuve un contenu absent.', d.id
      using errcode = 'check_violation';
  end if;
  if new.normative_spec_payload is distinct from (d.review_package ->> 'normative_spec_payload')
     or new.implementation_payload is distinct from (d.review_package ->> 'implementation_payload')
     or new.evidence_payload      is distinct from (d.review_package ->> 'evidence_payload')
     or new.stack_payload         is distinct from (d.review_package ->> 'stack_payload')
     or new.rule_id               is distinct from (d.review_package ->> 'rule_id')
     or new.statement             is distinct from (d.review_package ->> 'statement') then
    raise exception
      'confirmation refusee: le contenu presente n''est pas le dossier fige '
      'de la decision %. A et B ont approuve un autre contenu.', d.id
      using errcode = 'check_violation';
  end if;

  -- LA JURIDICTION VIENT DE LA DECISION, PAS DE LA LIGNE.
  new.country_code    := d.country_code;
  new.standard_family := d.standard_family;
  new.part            := d.part;

  -- L'HABILITATION EST CELLE QUE LA DECISION A ENREGISTREE, et elle doit
  -- encore etre efficace. `normative_decision_consume` l'a deja verifie sous
  -- verrou dans cette meme transaction; on le revérifie ici parce que ce
  -- declencheur doit tenir seul.
  if not normative_grant_is_effective(source) then
    raise exception
      'confirmation refusee: l''habilitation % n''est plus efficace.', source
      using errcode = 'insufficient_privilege';
  end if;
  new.authorisation_grant_id := source;
  -- LE NOM LISIBLE VIENT DE L'OCTROI, jamais d'une chaine recue: c'est lui que
  -- la note de calcul affiche, et l'octroi est immuable.
  select grantee_name into new.verifier_name
    from normative_authorisation_grants where id = source;
  new.authorisation_scope := jsonb_build_object(
    'country_code', d.country_code, 'standard_family', d.standard_family,
    'part', d.part, 'edition', d.edition, 'permission', d.permission,
    'decision_id', d.id);

  new.verified_at := now();
  new.created_at  := now();
  return new;
end;
$$;

comment on function normative_confirmation_depuis_decision() is
  'Chemin de la DECISION: verificateur, contenu et habilitation sont relus '
  'sur la decision consommee, jamais recus. Un appelant qui inserait '
  'directement ne pourrait que reproduire ce que le quatre-yeux a sanctionne, '
  'et l''index unique (decision_id, verifier_id) l''empeche de recommencer.';

-- IL PASSE AVANT `check_normative_confirmation`, dont il neutralise le
-- chemin `auth.uid()` en renseignant tout lui-meme. L'ordre alphabetique des
-- noms de declencheurs decide: `a_` precede `check_`.
drop trigger if exists a_confirmation_depuis_decision
  on normative_rule_confirmations;
create trigger a_confirmation_depuis_decision
  before insert on normative_rule_confirmations
  for each row when (new.decision_id is not null)
  execute function normative_confirmation_depuis_decision();

-- Et le declencheur historique NE S'APPLIQUE PLUS au chemin de la decision:
-- il resoudrait l'identite par `auth.uid()`, c'est-a-dire l'approbateur pour
-- les DEUX lignes, et consommerait une seconde fois les habilitations.
drop trigger if exists normative_confirmations_are_checked
  on normative_rule_confirmations;
create trigger normative_confirmations_are_checked
  before insert on normative_rule_confirmations
  for each row when (new.decision_id is null)
  execute function check_normative_confirmation();

-- ---------------------------------------------------------------------
-- 4. LA PROPOSITION PORTE LE DOSSIER
-- ---------------------------------------------------------------------
create or replace function normative_decision_propose(
  p_subject_kind text,
  p_subject_id   text,
  p_org_id       uuid,
  p_country      country_code,
  p_family       text,
  p_part         text,
  p_edition      text,
  p_permission   normative_permission,
  p_reason       text,
  p_review_package jsonb default null
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  source normative_authorisation_grants;
  nouvelle uuid;
begin
  acteur := normative_authenticated_actor();

  source := consume_normative_authorisation(
    acteur, p_permission, p_country, p_family, p_part, p_edition);
  if source.id is null then
    raise exception
      'proposition refusee: % ne detient aucune habilitation efficace « % » '
      'couvrant %/%/%/%.',
      acteur, p_permission, p_country, p_family, p_part, p_edition
      using errcode = 'insufficient_privilege';
  end if;

  -- UN DOSSIER DE PARAMETRE NATIONAL EST EXIGE, ET IL EST COMPLET OU REFUSE.
  -- Une decision « ndp_parameter » sans dossier ne pourrait produire aucun
  -- effet a la consommation: autant la refuser tout de suite, la ou l'auteur
  -- peut encore corriger.
  if p_subject_kind = 'ndp_parameter' then
    if p_review_package is null then
      raise exception
        'proposition refusee: un parametre national se propose avec son '
        'dossier de revue. Sans lui, « B a approuve » ne dit pas quoi.'
        using errcode = 'check_violation';
    end if;
    perform normative_assert_review_package(p_review_package, p_subject_id);
  end if;

  insert into normative_authority_decisions
    (subject_kind, subject_id, org_id, country_code, standard_family, part,
     edition, permission, state, proposer_id, proposal_source_grant_id, reason,
     review_package)
  values
    (p_subject_kind, p_subject_id, p_org_id, p_country, p_family, p_part,
     p_edition, p_permission, 'PENDING', acteur, source.id, p_reason,
     p_review_package)
  returning id into nouvelle;

  perform log_normative_event(
    'normative.decision.proposed', 'normative_authority_decisions', nouvelle,
    jsonb_build_object('proposer_id', acteur,
                       'proposal_source_grant_id', source.id,
                       'subject_kind', p_subject_kind,
                       'subject_id', p_subject_id,
                       'scope', jsonb_build_object(
                         'country_code', p_country, 'standard_family', p_family,
                         'part', p_part, 'edition', p_edition),
                       'correlation_id',
                       (select correlation_id from normative_authority_decisions
                         where id = nouvelle)),
    acteur);
  return nouvelle;
end;
$$;

-- Ce qu'un dossier doit porter pour qu'une consommation puisse en tirer un
-- effet. Verifie A LA PROPOSITION: decouvrir un dossier incomplet au moment de
-- consommer ferait echouer la consommation d'une decision deja approuvee.
create or replace function normative_assert_review_package(
  p_paquet jsonb, p_subject_id text)
returns void
language plpgsql
set search_path = public, pg_temp
as $$
declare
  manquant text;
  spec_json  jsonb;
  impl_json  jsonb;
  ev_json    jsonb;
  stack_json jsonb;
begin
  select string_agg(c, ', ' order by c) into manquant
    from unnest(array['rule_id', 'statement', 'normative_spec_payload',
                      'implementation_payload', 'evidence_payload',
                      'stack_payload', 'digest_algorithm',
                      'canonicalization_version']) c
   where p_paquet ->> c is null or btrim(p_paquet ->> c) = '';
  if manquant is not null then
    raise exception
      'dossier de revue incomplet: % manquant(s).', manquant
      using errcode = 'check_violation';
  end if;

  if p_paquet ->> 'rule_id' <> p_subject_id then
    raise exception
      'dossier de revue: il porte la regle « % » et la decision « % ».',
      p_paquet ->> 'rule_id', p_subject_id
      using errcode = 'check_violation';
  end if;

  -- LES QUATRE PAYLOADS SONT DU JSON, ET DISENT CE QU'ILS SONT.
  --
  -- Ces controles existent deja pour le chemin historique, dans
  -- `check_normative_confirmation`. Le chemin de la decision ne passe plus par
  -- lui: il faut donc les refaire ICI — a la proposition, la ou l'auteur peut
  -- encore corriger, plutot qu'a la consommation d'une decision deja
  -- approuvee par deux personnes.
  begin
    spec_json  := (p_paquet ->> 'normative_spec_payload')::jsonb;
    impl_json  := (p_paquet ->> 'implementation_payload')::jsonb;
    ev_json    := (p_paquet ->> 'evidence_payload')::jsonb;
    stack_json := (p_paquet ->> 'stack_payload')::jsonb;
  exception when others then
    raise exception
      'dossier de revue: un des quatre payloads n''est pas du JSON: %', sqlerrm
      using errcode = 'check_violation';
  end;

  if spec_json  ->> 'kind' <> 'normative_spec'
     or impl_json  ->> 'kind' <> 'implementation'
     or ev_json    ->> 'kind' <> 'evidence'
     or stack_json ->> 'kind' <> 'normative_stack' then
    raise exception
      'dossier de revue: les payloads ne decrivent pas ce qu''ils pretendent '
      '(spec=%, impl=%, preuve=%, pile=%).',
      spec_json ->> 'kind', impl_json ->> 'kind', ev_json ->> 'kind',
      stack_json ->> 'kind'
      using errcode = 'check_violation';
  end if;

  if spec_json ->> 'rule_id' is distinct from p_subject_id
     or impl_json ->> 'rule_id' is distinct from p_subject_id then
    raise exception
      'dossier de revue: la decision porte « % » et les payloads signent '
      '« % » et « % ».',
      p_subject_id, spec_json ->> 'rule_id', impl_json ->> 'rule_id'
      using errcode = 'check_violation';
  end if;

  if p_paquet ->> 'canonicalization_version' <> 'esc-canon/1'
     or stack_json ->> 'schema_version' <> 'esc-stack/1'
     or p_paquet ->> 'digest_algorithm' <> 'sha256' then
    raise exception
      'dossier de revue: methode inconnue (canon=%, pile=%, algo=%). La '
      'structure serait lue avec une grille qui n''est pas la sienne.',
      p_paquet ->> 'canonicalization_version', stack_json ->> 'schema_version',
      p_paquet ->> 'digest_algorithm'
      using errcode = 'check_violation';
  end if;

  -- LA PILE PORTE UNE ANNEXE. C'est d'elle qu'on tire l'edition attestee.
  if not exists (
    select 1 from jsonb_array_elements(stack_json -> 'components') c
     where c ->> 'role' = 'annexe') then
    raise exception
      'dossier de revue: la pile ne comporte aucun composant « annexe ». '
      'Impossible d''etablir sur quelle edition porte la confirmation.'
      using errcode = 'check_violation';
  end if;

  -- LE DOSSIER DE PREUVE EST COMPLET, ET CHAQUE CITATION EST SCELLEE.
  if ev_json -> 'items' is null
     or jsonb_typeof(ev_json -> 'items') <> 'array'
     or jsonb_array_length(ev_json -> 'items') = 0 then
    raise exception
      'dossier de revue: aucun element de preuve. Confirmer sans dire ce '
      'qu''on a lu n''est pas une lecture d''annexe.'
      using errcode = 'check_violation';
  end if;
  if exists (
    select 1 from jsonb_array_elements(ev_json -> 'items') e
     where jsonb_typeof(e) <> 'object'
        or e ->> 'document_digest' is null
        or e ->> 'document_role'   is null
        or e ->> 'reference'       is null
        or e ->> 'clause'          is null
        or e ->> 'quote'           is null
        or e ->> 'quote_digest'    is null
        or (e -> 'page_printed')   is null) then
    raise exception
      'dossier de revue: un element de preuve est incomplet.'
      using errcode = 'check_violation';
  end if;
  if exists (
    select 1 from jsonb_array_elements(ev_json -> 'items') e
     where e ->> 'quote_digest'
           <> encode(sha256(convert_to(e ->> 'quote', 'UTF8')), 'hex')) then
    raise exception
      'dossier de revue: le quote_digest d''un element ne resume pas sa '
      'citation.'
      using errcode = 'check_violation';
  end if;
end;
$$;

-- ---------------------------------------------------------------------
-- 5. LA CONSOMMATION PRODUIT L'EFFET, DANS LA MEME TRANSACTION
-- ---------------------------------------------------------------------
create or replace function normative_decision_consume(p_decision uuid)
returns normative_authority_decisions
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  acteur uuid;
  d normative_authority_decisions;
  n int;
  produites int := 0;
begin
  acteur := normative_authenticated_actor();

  select * into d from normative_authority_decisions
   where id = p_decision for no key update;
  if not found then
    raise exception 'decision % introuvable', p_decision
      using errcode = 'foreign_key_violation';
  end if;

  if d.state <> 'APPROVED' then
    raise exception
      'decision %: elle est « % ». Seule une decision APPROUVEE se consomme, '
      'et elle ne se consomme qu''une fois.', d.id, d.state
      using errcode = 'unique_violation';
  end if;

  perform normative_lock_grant_chains(
    d.proposal_source_grant_id, d.approval_source_grant_id);

  if not normative_grant_is_effective(d.proposal_source_grant_id) then
    raise exception
      'consommation refusee: l''habilitation % du proposant n''est plus '
      'efficace.', d.proposal_source_grant_id
      using errcode = 'insufficient_privilege';
  end if;
  if not normative_grant_is_effective(d.approval_source_grant_id) then
    raise exception
      'consommation refusee: l''habilitation % de l''approbateur n''est plus '
      'efficace.', d.approval_source_grant_id
      using errcode = 'insufficient_privilege';
  end if;

  -- L'ETAT D'ABORD: le declencheur de confirmation exige CONSUMED, et il a
  -- raison — c'est ce qui empeche une attestation de naitre d'une decision
  -- qui n'aurait pas franchi les controles ci-dessus.
  update normative_authority_decisions
     set state = 'CONSUMED', consumed_at = now()
   where id = d.id and state = 'APPROVED';
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception
      'decision %: consommation concurrente — l''etat a change entre la '
      'lecture et l''ecriture.', d.id
      using errcode = 'unique_violation';
  end if;

  -- L'EFFET NORMATIF. Deux attestations, une par regard, dans CETTE
  -- transaction. Si l'une echoue, le passage a CONSUMED est annule avec elle:
  -- une decision ne peut pas etre consommee sans avoir produit son effet.
  if d.subject_kind = 'ndp_parameter' then
    produites := normative_emettre_confirmations(d.id);
    if produites <> 2 then
      raise exception
        'decision %: % attestation(s) produite(s), 2 attendues. Le '
        'quatre-yeux exige deux regards, et la consommation doit les '
        'inscrire.', d.id, produites
        using errcode = 'check_violation';
    end if;
  end if;

  perform log_normative_event(
    'normative.decision.consumed', 'normative_authority_decisions', d.id,
    jsonb_build_object('consumed_by', acteur,
                       'proposer_id', d.proposer_id,
                       'approver_id', d.approver_id,
                       'proposal_source_grant_id', d.proposal_source_grant_id,
                       'approval_source_grant_id', d.approval_source_grant_id,
                       'confirmations_emises', produites,
                       'correlation_id', d.correlation_id),
    acteur);

  select * into d from normative_authority_decisions where id = p_decision;
  return d;
end;
$$;

-- Les deux attestations, ecrites depuis le dossier fige. Aucune valeur ne
-- vient de l'appelant: `emettre` ne prend qu'un identifiant de decision.
create or replace function normative_emettre_confirmations(p_decision uuid)
returns int
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  d normative_authority_decisions;
  paquet jsonb;
  qui uuid;
  n int;
  ecrites int := 0;
begin
  select * into d from normative_authority_decisions where id = p_decision;
  paquet := d.review_package;

  foreach qui in array array[d.proposer_id, d.approver_id] loop
    insert into normative_rule_confirmations (
      decision_id, country_code, standard_family, part, rule_id,
      stack_digest, normative_spec_digest, implementation_digest,
      evidence_digest, digest_algorithm, canonicalization_version,
      normative_spec_payload, implementation_payload, evidence_payload,
      stack_payload, stack_snapshot, annex_edition, evidence_items,
      statement, verifier_id, verifier_name, verified_at,
      authorisation_grant_id, authorisation_scope, idempotency_key)
    values (
      d.id, d.country_code, d.standard_family, d.part,
      paquet ->> 'rule_id',
      -- LES EMPREINTES SONT CALCULEES PAR LE SERVEUR sur les payloads figes.
      -- Les recevoir permettrait d'annoncer une empreinte qui ne resume pas
      -- ce qui est stocke.
      encode(sha256(convert_to(paquet ->> 'stack_payload', 'UTF8')), 'hex'),
      encode(sha256(convert_to(paquet ->> 'normative_spec_payload', 'UTF8')), 'hex'),
      encode(sha256(convert_to(paquet ->> 'implementation_payload', 'UTF8')), 'hex'),
      encode(sha256(convert_to(paquet ->> 'evidence_payload', 'UTF8')), 'hex'),
      paquet ->> 'digest_algorithm',
      paquet ->> 'canonicalization_version',
      paquet ->> 'normative_spec_payload',
      paquet ->> 'implementation_payload',
      paquet ->> 'evidence_payload',
      paquet ->> 'stack_payload',
      (paquet ->> 'stack_payload')::jsonb,
      coalesce((
        select c ->> 'edition'
          from jsonb_array_elements(
                 (paquet ->> 'stack_payload')::jsonb -> 'components') c
         where c ->> 'role' = 'annexe'
         order by (c ->> 'application_order')::int desc limit 1), d.edition),
      coalesce((paquet ->> 'evidence_payload')::jsonb -> 'items', '[]'::jsonb),
      paquet ->> 'statement',
      qui,
      -- Ecrase par le declencheur, qui le lit sur l'octroi immuable.
      'a determiner par le declencheur',
      now(),
      case when qui = d.proposer_id then d.proposal_source_grant_id
           else d.approval_source_grant_id end,
      '{}'::jsonb,
      format('decision:%s:%s', d.id, qui))
    on conflict do nothing;
    -- ON COMPTE CE QUI A ETE ECRIT, pas les tours de boucle. `on conflict do
    -- nothing` rend zero ligne quand l'attestation existe deja, et compter le
    -- tour ferait dire « deux regards produits » a une seconde consommation
    -- qui n'aurait rien produit.
    get diagnostics n = row_count;
    ecrites := ecrites + n;
  end loop;
  return ecrites;
end;
$$;

-- ---------------------------------------------------------------------
-- 5b. RLS — LE WRITER N'ECRIT QUE PAR LE CHEMIN DE LA DECISION
-- ---------------------------------------------------------------------
-- `normative_emettre_confirmations` est SECURITY DEFINER, donc `current_user`
-- y vaut `eurostruct_normative_writer`. La table porte FORCE ROW LEVEL
-- SECURITY: le proprietaire lui-meme est soumis aux policies, et il n'en avait
-- aucune en INSERT. Mesure: « new row violates row-level security policy for
-- table "normative_rule_confirmations" ».
--
-- LA POLICY EST LA PLUS ETROITE QUI PERMETTE L'EFFET: le writer ne peut
-- inserer QUE des attestations rattachees a une decision. Une attestation
-- libre — sans decision, donc sans quatre-yeux — lui reste impossible, et
-- c'est exactement la frontiere qu'on veut.
drop policy if exists normative_confirmations_writer_insert
  on normative_rule_confirmations;
create policy normative_confirmations_writer_insert
  on normative_rule_confirmations
  for insert to eurostruct_normative_writer
  with check (decision_id is not null);

-- ET LA LECTURE DE LA DECISION, dont le declencheur a besoin pour relire le
-- verificateur, le dossier et l'habilitation. Sans elle il ne verrait aucune
-- ligne — et « la decision n'existe pas » remplacerait « je n'ai pas le droit
-- de la lire », ce qui est le mode d'echec le plus trompeur de RLS.
drop policy if exists normative_decisions_writer_read
  on normative_authority_decisions;
create policy normative_decisions_writer_read
  on normative_authority_decisions
  for select to eurostruct_normative_writer using (true);


-- ---------------------------------------------------------------------
-- 6. ACL — PERSONNE NE PASSE A COTE DES PRIMITIVES
-- ---------------------------------------------------------------------
revoke all on function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission,
  text, jsonb) from public;
revoke all on function normative_emettre_confirmations(uuid) from public;
revoke all on function normative_assert_review_package(jsonb, text) from public;
revoke all on function normative_confirmation_depuis_decision() from public;

alter function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission,
  text, jsonb) owner to eurostruct_normative_writer;
alter function normative_emettre_confirmations(uuid)
  owner to eurostruct_normative_writer;
alter function normative_assert_review_package(jsonb, text)
  owner to eurostruct_normative_writer;
alter function normative_confirmation_depuis_decision()
  owner to eurostruct_normative_writer;

-- L'ANCIENNE SIGNATURE A NEUF ARGUMENTS DISPARAIT.
--
-- La laisser vivante offrirait un chemin qui propose SANS dossier, donc une
-- decision qu'on pourrait approuver et consommer sans produire d'effet — et
-- personne ne saurait laquelle des deux fonctions a ete appelee.
drop function if exists normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission, text);

grant execute on function normative_decision_propose(
  text, text, uuid, country_code, text, text, text, normative_permission,
  text, jsonb) to eurostruct_authority_backend;



-- ---------------------------------------------------------------------
-- 6b. LE MANIFESTE DECLARE LA SURFACE, DONC IL DECLARE CE QU'ON AJOUTE
-- ---------------------------------------------------------------------
-- `assert_authority_composition()` confronte la surface reelle a cette liste
-- NOMMEE. Trois primitives ajoutees et une signature changee sans l'y
-- declarer laissent la base en PENDING: l'activation refuse, et elle a
-- raison — une surface qui a bouge sans que personne l'ait declaree est
-- exactement ce que ce manifeste existe pour attraper.
--
-- Republie ici en entier plutot que retouche par un `update`: la liste EST la
-- declaration, et une declaration qui se modifie par morceaux ne se relit plus.
create or replace function normative_authority_manifest()
returns table (identite       text,
               proprietaire   text,
               secdef         boolean,
               chemin_epingle boolean,
               public_execute boolean,
               acl_execute    text)
language sql
immutable
set search_path = public, pg_temp
as $$
  values
    ('assert_0012_lineage_surface()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_0014_decisions_surface()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_backend_membership()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_composition()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_manifest()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_authority_surface_hardened()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('assert_digest_integrity(text,text,text,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('assert_normative_topology()', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('bootstrap_normative_administrator(uuid,text,text)', 'eurostruct_normative_bootstrap', true, true, false, 'eurostruct_deployment,eurostruct_normative_bootstrap'),
    ('check_normative_confirmation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_confirmation_revocation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_decision_transition()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant_lineage()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('check_normative_grant_revocation()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('consume_normative_authorisation(uuid,normative_permission,country_code,text,text,text)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('forbid_activation_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_annex_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_approved_settings_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_auth_contract_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_control_plane_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_decision_delete()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_final_deliverable_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_finalization_intent_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_migration_ledger_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_ndp_value_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_normative_audit_mutation()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('forbid_normative_write_while_pending()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('forbid_purge_within_retention()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_review_decision_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_seal_metadata_mutation()', '@PLAN', false, true, true, '@PLAN'),
    ('forbid_validated_calculation_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_validated_child_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_validated_deliverable_mutation()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('forbid_variant_rewrite()', '@MIGRATEUR', false, true, true, '@MIGRATEUR'),
    ('normative_activation_state()', 'eurostruct_normative_activator', true, true, false, 'authenticated,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer,normative_backend,normative_governance'),
    ('normative_approved_manifest()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_authenticated_actor()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authenticated_actor_or_null()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_authentication_configured()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_assert_review_package(jsonb,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_authorisation_snapshot(normative_authorisation_grants)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_authority_manifest()', 'eurostruct_normative_writer', false, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_bootstrap_mandate()', 'eurostruct_normative_bootstrap', false, true, false, 'eurostruct_deployment,eurostruct_normative_bootstrap'),
    ('normative_confirmation_depuis_decision()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_constater_authentification()', 'eurostruct_normative_writer', true, true, false, 'eurostruct_deployment,eurostruct_normative_writer'),
    ('normative_control_plane()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_control_plane_oid()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_decision_approve(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_consume(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_decision_propose(text,text,uuid,country_code,text,text,text,normative_permission,text,jsonb)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_authority_backend,eurostruct_normative_writer'),
    ('normative_declared_setting(text)', '@PLAN', false, true, false, '@PLAN,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_deployment_readiness()', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment'),
    ('normative_effective_setting(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_emettre_confirmations(uuid)', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_exiger_manifeste_approuve(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_finalize_deployment(text)', '@PLAN', false, true, false, '@PLAN,eurostruct_deployment'),
    ('normative_grant_descendants(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer'),
    ('normative_grant_is_active(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_grant_is_effective(uuid)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_authority_backend,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_lock_grant_chains(uuid[])', 'eurostruct_normative_writer', true, true, false, 'eurostruct_normative_writer'),
    ('normative_migration_applied(text,text)', '@MIGRATEUR', false, true, false, '@MIGRATEUR'),
    ('normative_migration_gate(text,text)', '@MIGRATEUR', false, true, false, '@MIGRATEUR'),
    ('normative_pending_migrator()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_prepare_activation(text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_record_activation()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_seal_assurance()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_seal_version()', 'eurostruct_normative_activator', true, true, false, '@PLAN,eurostruct_deployment,eurostruct_normative_activator,eurostruct_normative_bootstrap,eurostruct_normative_writer'),
    ('normative_settings_manifest()', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('normative_topology_digest(oid,text,oid,text,text)', 'eurostruct_normative_activator', true, true, false, 'eurostruct_deployment,eurostruct_normative_activator'),
    ('resolve_normative_authorisation(uuid,normative_permission,country_code,text,text,text)', 'eurostruct_normative_writer', false, true, false, 'eurostruct_normative_writer')
$$;

alter function normative_authority_manifest() owner to eurostruct_normative_writer;
revoke all on function normative_authority_manifest() from public;
grant execute on function normative_authority_manifest()
  to eurostruct_normative_writer, eurostruct_deployment;

-- ---------------------------------------------------------------------
-- 7. LE DROIT DE CREER EST REPRIS
-- ---------------------------------------------------------------------
-- Meme forme qu'en 0011 a 0015, et pour la meme raison mesuree: on endosse le
-- DONNEUR de l'octroi, et seulement s'il appartient a un ensemble admissible
-- explicite, confronte au catalogue et jamais dicte par lui.
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
        'AUTHORITY_0016_GRANTOR_NOT_ADMISSIBLE: le donneur « % » de CREATE sur '
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
        'AUTHORITY_0016_SCHEMA_CREATE_REVOKE_FAILED: la revocation sous le '
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
       and a.grantee = 'eurostruct_normative_writer'::regrole::oid) then
    raise exception
      'AUTHORITY_0016_SCHEMA_CREATE_STILL_GRANTED: CREATE sur public reste '
      'octroye a eurostruct_normative_writer apres la migration.'
      using errcode = 'insufficient_privilege';
  end if;
end;
$$;
