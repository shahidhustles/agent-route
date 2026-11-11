-- Run after stubs.sql and the migrations. Every check raises on failure.
\set ON_ERROR_STOP on
create schema test_helpers;
grant usage on schema test_helpers to public;
create function test_helpers.as_user(uid text) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', uid, 'role', 'authenticated')::text, false);
end $$;
create function test_helpers.expect(label text, got bigint, want bigint) returns void language plpgsql as $$
begin
  if got is distinct from want then raise exception 'FAIL %: got %, want %', label, got, want; end if;
  raise notice 'ok   %', label;
end $$;
create function test_helpers.expect_denied(label text, stmt text) returns void language plpgsql as $$
begin
  begin execute stmt; exception when insufficient_privilege or check_violation then
    raise notice 'ok   % (denied)', label; return; end;
  raise exception 'FAIL %: statement was allowed', label;
end $$;


set role authenticated;
select test_helpers.as_user('user_alice');
insert into conversations (id, title) values ('00000000-0000-0000-0000-00000000000a', 'Alice chat');
insert into messages (conversation_id, id, message) values ('00000000-0000-0000-0000-00000000000a', 'm1', '{"role":"user","parts":[{"type":"text","text":"hi"}]}');
insert into runs (id, conversation_id, prompt, agent, model, status) values ('run-a', '00000000-0000-0000-0000-00000000000a', 'p', 'slides', 'm', 'running');
select test_helpers.expect('user_id defaults to the JWT sub', (select count(*) from conversations where user_id = 'user_alice'), 1);
select test_helpers.expect('the touch trigger runs under RLS', (select count(*) from conversations where updated_at >= created_at), 1);

select test_helpers.as_user('user_bob');
select test_helpers.expect('bob sees no conversations', (select count(*) from conversations), 0);
select test_helpers.expect('bob sees no messages', (select count(*) from messages), 0);
select test_helpers.expect('bob sees no runs', (select count(*) from runs), 0);
select test_helpers.expect_denied('bob cannot write into alices chat',
  $$insert into messages (conversation_id, id, message) values ('00000000-0000-0000-0000-00000000000a', 'm2', '{}')$$);
select test_helpers.expect_denied('bob cannot spoof user_id',
  $$insert into conversations (user_id, title) values ('user_alice', 'x')$$);
select test_helpers.expect_denied('bob cannot link a run to alices chat',
  $$insert into runs (id, conversation_id, prompt, agent, model) values ('run-b', '00000000-0000-0000-0000-00000000000a', 'p', 'a', 'm')$$);
update runs set verdict = true where id = 'run-a';
delete from conversations;
reset role;
select test_helpers.expect('bob changed and deleted nothing', (select count(*) from runs where verdict is null) + (select count(*) from conversations), 2);

set role authenticated;
select test_helpers.as_user('user_alice');
update runs set status = 'passed', verdict = true, cost_usd = 0.01 where id = 'run-a';
select test_helpers.expect('alice updates her run', (select count(*) from runs where verdict), 1);
delete from conversations;
select test_helpers.expect('deleting the chat cascades to messages', (select count(*) from messages), 0);
select test_helpers.expect('the run outlives its chat', (select count(*) from runs where conversation_id is null), 1);

-- anon and a token without the authenticated role get nothing.
reset role;
set role anon;
select test_helpers.expect_denied('anon cannot read conversations', 'select * from conversations');
reset role;

-- Storage: own folder only.
set role authenticated;
select test_helpers.as_user('user_alice');
insert into storage.objects (bucket_id, name) values ('artifacts', 'user_alice/run-a/deck.pptx');
select test_helpers.expect_denied('alice cannot write into bobs folder',
  $$insert into storage.objects (bucket_id, name) values ('artifacts', 'user_bob/run-b/deck.pptx')$$);
select test_helpers.expect_denied('no writing at the bucket root',
  $$insert into storage.objects (bucket_id, name) values ('artifacts', 'deck.pptx')$$);
select test_helpers.as_user('user_bob');
select test_helpers.expect('bob cannot list alices files', (select count(*) from storage.objects), 0);
delete from storage.objects;
update storage.objects set name = 'user_bob/x.pptx';
reset role;
select test_helpers.expect('bob changed no alice file', (select count(*) from storage.objects where name = 'user_alice/run-a/deck.pptx'), 1);
select test_helpers.expect('the bucket is private', (select count(*) from storage.buckets where id = 'artifacts' and not public), 1);
