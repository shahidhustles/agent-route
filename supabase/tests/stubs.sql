-- Minimal stand-ins for the parts of Supabase the migrations touch. For local RLS tests only, never applied to a project.
create role anon nologin;
create role authenticated nologin;
create schema auth;
create function auth.jwt() returns jsonb language sql stable as
  $$ select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
grant usage on schema auth to anon, authenticated;
grant usage on schema public to anon, authenticated;
create schema storage;
create table storage.buckets (id text primary key, name text not null, public boolean not null default false);
create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets (id),
  name text,
  owner_id text
);
alter table storage.objects enable row level security;
create function storage.foldername(name text) returns text[] language plpgsql as
  $$ declare _parts text[]; begin select string_to_array(name, '/') into _parts; return _parts[1:array_length(_parts, 1) - 1]; end $$;
grant usage on schema storage to authenticated;
grant select, insert, update, delete on storage.objects to authenticated;
