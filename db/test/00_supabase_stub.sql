-- Local stand-in for the parts of Supabase the migrations depend on.
--
-- Applied only when running the schema tests against a scratch PostgreSQL. It
-- is never applied to a real environment, where Supabase provides `auth.users`,
-- `auth.uid()` and the `authenticated` role itself.
--
-- `auth.uid()` here reads the same session setting PostgREST sets, so the RLS
-- policies exercised locally are byte-identical to the ones that run in
-- production.

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
