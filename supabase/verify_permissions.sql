-- Integration test for an isolated/local Supabase project after schema.sql.
-- Runs inside a rolled-back transaction, including synthetic auth users.
begin;
insert into auth.users(id) values
 ('00000000-0000-0000-0000-000000000001'),
 ('00000000-0000-0000-0000-000000000002'),
 ('00000000-0000-0000-0000-000000000003');
insert into private.admins values ('00000000-0000-0000-0000-000000000003');

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}',true);
insert into public.entries(term,meaning,pos) values ('permission-test','权限测试','noun');
update public.entries set meaning='作者可编辑' where term='permission-test';
do $$ begin
  if not exists(select 1 from public.entries where term='permission-test' and meaning='作者可编辑' and revision=2) then
    raise exception 'Owner update failed';
  end if;
  begin
    update public.entries set owner_id='00000000-0000-0000-0000-000000000002' where term='permission-test';
    raise exception 'Ownership mutation was allowed';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into private.admins values ('00000000-0000-0000-0000-000000000001');
    raise exception 'Self promotion was allowed';
  exception when insufficient_privilege then null;
  end;
end $$;

select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000002","role":"authenticated"}',true);
do $$ declare affected integer; begin
  update public.entries set meaning='禁止修改' where term='permission-test';
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Other user update allowed'; end if;
  delete from public.entries where term='permission-test';
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Other user delete allowed'; end if;
  if public.is_admin() then raise exception 'Other user is admin'; end if;
end $$;

set local role anon;
select set_config('request.jwt.claims','{"role":"anon"}',true);
do $$ begin
  if not exists(select 1 from public.entries where term='permission-test') then raise exception 'Public read failed'; end if;
  begin
    insert into public.entries(term,meaning,pos) values ('anonymous-write','禁止','noun');
    raise exception 'Anonymous insert allowed';
  exception when insufficient_privilege then null;
  end;
end $$;

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000003","role":"authenticated"}',true);
do $$ declare affected integer; begin
  if not public.is_admin() then raise exception 'Admin recognition failed'; end if;
  update public.entries set meaning='管理员可编辑' where term='permission-test';
  get diagnostics affected = row_count;
  if affected <> 1 then raise exception 'Admin edit failed'; end if;
  update public.entries set meaning='过期修改' where term='permission-test' and revision=2;
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Stale revision accepted'; end if;
  delete from public.entries where term='permission-test';
  get diagnostics affected = row_count;
  if affected <> 1 then raise exception 'Admin delete failed'; end if;
end $$;
reset role;
do $$ begin
  if (select count(*) from private.entry_history where old_row->>'term'='permission-test' or new_row->>'term'='permission-test') <> 4 then
    raise exception 'Audit trail incomplete';
  end if;
end $$;
rollback;
