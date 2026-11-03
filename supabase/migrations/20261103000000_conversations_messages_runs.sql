-- Relay history, one row owner per Clerk user.
-- Clerk's native Supabase integration puts the Clerk user id in the JWT "sub" claim, so every table keys on
-- auth.jwt()->>'sub' and defaults user_id to it. There is no Supabase Auth user and no service-role access.

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null default (auth.jwt() ->> 'sub'),
  title text,
  status text not null default 'regular' check (status in ('regular', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_user_updated_idx on public.conversations (user_id, updated_at desc);

-- One row per assistant-ui / AI SDK UI message. `message` holds the message without its id: role, parts and metadata.
create table public.messages (
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  id text not null,
  user_id text not null default (auth.jwt() ->> 'sub'),
  parent_id text,
  format text not null default 'ai-sdk/v6',
  message jsonb not null,
  created_at timestamptz not null default now(),
  primary key (conversation_id, id)
);
create index messages_conversation_created_idx on public.messages (conversation_id, created_at);

-- One row per agent run. `id` is the Python backend's run id. conversation_id and message_id link the run to the
-- reply that shows it, and stay null for a run whose chat was deleted.
create table public.runs (
  id text primary key,
  user_id text not null default (auth.jwt() ->> 'sub'),
  conversation_id uuid references public.conversations (id) on delete set null,
  message_id text,
  prompt text not null,
  agent text not null,
  model text not null,
  preference text check (preference in ('cheap', 'balanced', 'fast', 'accurate')),
  status text not null default 'running' check (status in ('running', 'passed', 'failed', 'stopped', 'error')),
  cost_usd numeric,
  wall_s numeric,
  routing jsonb,
  verdict boolean,
  rerun_of text,
  artifact jsonb,
  -- Object names under <user_id>/<run id>/ in the private "artifacts" bucket, for the files and the page images.
  files text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index runs_user_created_idx on public.runs (user_id, created_at desc);
create index runs_conversation_idx on public.runs (conversation_id);

-- A new message bumps its conversation to the top of the sidebar. Runs as the caller, so RLS still applies.
create function public.touch_conversation() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  update public.conversations set updated_at = now() where id = new.conversation_id;
  return new;
end;
$$;
create trigger messages_touch_conversation after insert on public.messages
  for each row execute function public.touch_conversation();

create function public.set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
create trigger conversations_set_updated_at before update on public.conversations
  for each row execute function public.set_updated_at();
create trigger runs_set_updated_at before update on public.runs
  for each row execute function public.set_updated_at();

alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.runs enable row level security;

-- Only signed-in Clerk users (the "authenticated" role claim) reach these tables; anon gets nothing.
create policy "own conversations" on public.conversations
  for all to authenticated
  using (user_id = (select auth.jwt() ->> 'sub'))
  with check (user_id = (select auth.jwt() ->> 'sub'));

-- A message also has to sit in one of the caller's conversations, so a user cannot write into another chat.
create policy "own messages" on public.messages
  for all to authenticated
  using (user_id = (select auth.jwt() ->> 'sub'))
  with check (
    user_id = (select auth.jwt() ->> 'sub')
    and exists (
      select 1 from public.conversations c
      where c.id = conversation_id and c.user_id = (select auth.jwt() ->> 'sub')
    )
  );

create policy "own runs" on public.runs
  for all to authenticated
  using (user_id = (select auth.jwt() ->> 'sub'))
  with check (
    user_id = (select auth.jwt() ->> 'sub')
    and (
      conversation_id is null
      or exists (
        select 1 from public.conversations c
        where c.id = conversation_id and c.user_id = (select auth.jwt() ->> 'sub')
      )
    )
  );

grant select, insert, update, delete on public.conversations, public.messages, public.runs to authenticated;
