-- Private bucket for run outputs (.pptx, .docx, .xlsx, .html) and their page images.
-- Object names are <clerk user id>/<run id>/<file>, so the first folder is the owner.
insert into storage.buckets (id, name, public)
values ('artifacts', 'artifacts', false)
on conflict (id) do update set public = false;

create policy "own artifacts read" on storage.objects
  for select to authenticated
  using (bucket_id = 'artifacts' and (storage.foldername(name))[1] = (select auth.jwt() ->> 'sub'));

create policy "own artifacts insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'artifacts' and (storage.foldername(name))[1] = (select auth.jwt() ->> 'sub'));

create policy "own artifacts update" on storage.objects
  for update to authenticated
  using (bucket_id = 'artifacts' and (storage.foldername(name))[1] = (select auth.jwt() ->> 'sub'))
  with check (bucket_id = 'artifacts' and (storage.foldername(name))[1] = (select auth.jwt() ->> 'sub'));

create policy "own artifacts delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'artifacts' and (storage.foldername(name))[1] = (select auth.jwt() ->> 'sub'));
