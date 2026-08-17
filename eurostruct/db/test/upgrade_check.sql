-- =====================================================================
-- EUROSTRUCT — controle de mise a niveau
--
-- Joue sur une base ou les migrations precedentes ont ete appliquees D'ABORD,
-- puis la derniere par-dessus. Ce chemin est distinct de l'installation
-- complete d'un coup, et c'est celui d'une base de production.
--
-- Ne cree aucune donnee: il verifie que le schema est en place et vide.
-- =====================================================================

\set ON_ERROR_STOP on

do $$
declare
  t text;
  attendues text[] := array[
    'normative_authorisation_grants',
    'normative_authorisation_revocations',
    'normative_rule_confirmations',
    'normative_rule_confirmation_revocations'
  ];
  n bigint;
begin
  foreach t in array attendues loop
    if to_regclass('public.' || t) is null then
      raise exception
        'la mise a niveau n''a pas cree la table %: la migration ne passe '
        'que sur une base vierge', t;
    end if;
    execute format('select count(*) from %I', t) into n;
    if n <> 0 then
      raise exception 'la mise a niveau a cree % ligne(s) dans %', n, t;
    end if;
  end loop;

  -- Les fonctions serveur doivent exister, sans quoi les controles
  -- d'autorisation ne s'appliqueraient pas.
  foreach t in array array[
    'bootstrap_normative_administrator',
    'check_normative_confirmation',
    'check_normative_grant',
    'resolve_normative_authorisation',
    'assert_digest_integrity',
    'normative_grant_is_active'
  ] loop
    if not exists (select 1 from pg_proc p
                    join pg_namespace ns on ns.oid = p.pronamespace
                   where ns.nspname = 'public' and p.proname = t) then
      raise exception 'fonction % absente apres mise a niveau', t;
    end if;
  end loop;

  -- La vue minimale de statut, seule surface ouverte au calcul.
  if to_regclass('public.normative_rule_confirmation_status') is null then
    raise exception 'la vue de statut est absente apres mise a niveau';
  end if;

  -- Et les declencheurs d'immuabilite, qui sont la moitie de la garantie.
  foreach t in array array[
    'normative_grants_are_immutable',
    'normative_confirmations_are_immutable',
    'normative_confirmation_revocations_are_immutable',
    'normative_grant_revocations_are_immutable',
    'audit_log_normative_entries_are_immutable'
  ] loop
    if not exists (select 1 from pg_trigger where tgname = t) then
      raise exception 'declencheur % absent apres mise a niveau', t;
    end if;
  end loop;
end
$$;

\echo ''
\echo '================================================='
\echo ' Mise a niveau depuis la migration precedente verifiee.'
\echo '================================================='
