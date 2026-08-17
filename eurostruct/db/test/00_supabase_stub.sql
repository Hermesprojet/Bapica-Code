-- Local stand-in for the parts of Supabase the migrations depend on.
--
-- Applied only when running the schema tests against a scratch PostgreSQL. It
-- is never applied to a real environment, where Supabase provides `auth.users`,
-- `auth.uid()` and the `authenticated` role itself.
--
-- `auth.uid()` here reads the same session setting PostgREST sets. Les
-- POLICIES exercees localement sont donc bien celles qui tourneront en
-- production — mais cela ne suffit pas a conclure a la compatibilite Supabase,
-- et l'ancienne redaction (« byte-identical to the ones that run in
-- production ») le laissait croire.
--
-- CE QUI EST VERIFIE, ET CE QUI NE L'EST PAS (6.3b5).
--
-- Verifie: le MODELE DE PRIVILEGES de la cible, par
-- `db/test/nonsuperuser_install.sh` — role de migration non superutilisateur,
-- sans bypassrls, schema `auth` qui ne lui appartient pas. Quatre obstacles
-- reels y ont ete trouves, qu'aucune execution superutilisateur ne pouvait
-- montrer.
--
-- NON verifie: les extensions preinstallees de Supabase, ses politiques par
-- defaut, PgBouncer, ses event triggers, et le contenu reel de son schema
-- `auth`. La compatibilite Supabase ne sera etablie que par une execution sur
-- une instance de staging reelle. Voir docs/DEPLOIEMENT_PREREQUIS.md.

create schema if not exists auth;

create table if not exists auth.users (
  id    uuid primary key default gen_random_uuid(),
  email text unique
);

create or replace function auth.uid() returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon;
  end if;
end
$$;
