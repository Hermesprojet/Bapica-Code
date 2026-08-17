-- =====================================================================
-- EUROSTRUCT — 6.3b3: insertion du paquet REEL produit par Python
--
-- Le paquet arrive dans la variable psql `:paquet`, citee par `:'paquet'`.
-- AUCUN payload n'est retape ici: les quatre chaines canoniques et leurs
-- quatre empreintes sont prises telles quelles dans le JSON. C'est tout
-- l'interet — une fixture ecrite a la main ne peut pas prouver que la base
-- accepte ce que le moteur produit REELLEMENT.
--
-- Les colonnes derivees (`stack_snapshot`, `evidence_items`, `annex_edition`)
-- sont volontairement remplies de valeurs absurdes: le serveur doit les
-- ecraser, et `cross_contract.py` compare ce qu'il relit.
--
-- Identites FICTIVES. Aucune confirmation reelle n'est creee: la regle est
-- une vraie regle du referentiel belge, mais le verificateur, l'octroi et la
-- declaration sont de test.
-- =====================================================================

\set ON_ERROR_STOP on

-- La base doit etre vierge: la chaine de confiance est ouverte ICI, depuis
-- l'amorcage, exactement comme en deploiement.
do $$
declare n bigint;
begin
  select count(*) into n from normative_authorisation_grants;
  if n <> 0 then
    raise exception
      'base non vierge (% octroi(s)): ce controle ouvre lui-meme la chaine '
      'de confiance et ne peut pas repartir d''un etat inconnu', n;
  end if;
end
$$;

-- Le paquet arrive par une variable psql. Elle est interpolee ICI, au niveau
-- superieur: psql ne substitue PAS ses variables a l'interieur d'un bloc
-- dollar-quote, si bien qu'un `:'paquet'` ecrit dans le DO serait passe
-- litteralement a PL/pgSQL et provoquerait une erreur de syntaxe.
create temp table xc_paquet as select :'paquet'::jsonb as p;

do $$
declare n bigint;
begin
  select count(*) into n from xc_paquet where p is not null;
  if n <> 1 then
    raise exception 'le paquet emis par Python n''est pas arrive (% ligne)', n;
  end if;
end
$$;

insert into auth.users (id, email) values
  ('a1000000-0000-0000-0000-000000000001', 'FICTIF-xc-admin@eurostruct.test'),
  ('a1000000-0000-0000-0000-000000000002', 'FICTIF-xc-verif@eurostruct.test');

do $$
begin
  perform bootstrap_normative_administrator(
    'a1000000-0000-0000-0000-000000000001',
    'FICTIF Administrateur Contrat Croise',
    'FICTIF — ouverture de la chaine pour le controle de contrat croise.');
end
$$;

-- L'administrateur habilite un verificateur, sur la portee EXACTE que la
-- pile du paquet designera. Une portee plus large serait refusee par la
-- contrainte verification_scope_is_explicit.
do $$
begin
  perform set_config('request.jwt.claim.sub',
                     'a1000000-0000-0000-0000-000000000001', true);
  insert into normative_authorisation_grants
    (grantee_id, grantee_name, permission,
     country_code, standard_family, part, edition, reason)
  values ('a1000000-0000-0000-0000-000000000002',
          'FICTIF Verificateur Contrat Croise',
          'can_validate_normative_reference',
          'BE', 'EN 1992', '1-1', '2010',
          'FICTIF — habilitation pour le controle de contrat croise.');
end
$$;

-- L'insertion elle-meme, sous l'identite du verificateur habilite.
do $$
declare
  p jsonb;
begin
  select xc_paquet.p into p from xc_paquet;
  perform set_config('request.jwt.claim.sub',
                     'a1000000-0000-0000-0000-000000000002', true);

  insert into normative_rule_confirmations (
    country_code, standard_family, part, rule_id,
    stack_digest, normative_spec_digest, implementation_digest, evidence_digest,
    digest_algorithm, canonicalization_version,
    normative_spec_payload, implementation_payload, evidence_payload,
    stack_payload,
    -- Derivees par le serveur: ce qu'on met ici doit disparaitre.
    stack_snapshot, annex_edition, evidence_items,
    statement, verifier_id, verifier_name, verified_at,
    authorisation_grant_id, authorisation_scope, idempotency_key
  ) values (
    (p ->> 'country_code')::country_code,
    p ->> 'standard_family',
    p ->> 'part',
    p ->> 'rule_id',
    p ->> 'stack_digest',
    p ->> 'normative_spec_digest',
    p ->> 'implementation_digest',
    p ->> 'evidence_digest',
    p ->> 'digest_algorithm',
    p ->> 'canonicalization_version',
    p ->> 'normative_spec_payload',
    p ->> 'implementation_payload',
    p ->> 'evidence_payload',
    p ->> 'stack_payload',
    '{"derive": "par le client, doit etre ecrase"}'::jsonb,
    'EDITION-FOURNIE-PAR-LE-CLIENT',
    '[{"derive": "par le client, doit etre ecrase"}]'::jsonb,
    'FICTIF — j''ai ouvert l''annexe aux pages citees et la regle dit bien ceci.',
    '00000000-0000-0000-0000-000000000000',   -- ecrase par le serveur
    'FICTIF NOM USURPE',                      -- ecrase par le serveur
    timestamptz '1999-01-01 00:00:00+00',     -- ecrase par le serveur
    null, '{}'::jsonb,                        -- resolus par le serveur
    'FICTIF-contrat-croise-1'
  );
end
$$;

-- Le serveur a bien impose l'identite et l'horodatage: si ces colonnes
-- avaient survecu, la relecture comparerait un paquet que personne n'a signe.
do $$
declare c record;
begin
  select * into c from normative_rule_confirmations
   where idempotency_key = 'FICTIF-contrat-croise-1';
  if c.verifier_id <> 'a1000000-0000-0000-0000-000000000002' then
    raise exception 'verifier_id fourni par le client a survecu: %',
      c.verifier_id;
  end if;
  if c.verifier_name <> 'FICTIF Verificateur Contrat Croise' then
    raise exception 'verifier_name non repris de l''octroi: %', c.verifier_name;
  end if;
  if c.verified_at < timestamptz '2000-01-01' then
    raise exception 'verified_at client a survecu: %', c.verified_at;
  end if;
  if c.authorisation_grant_id is null then
    raise exception 'aucun octroi resolu par le serveur';
  end if;
end
$$;
