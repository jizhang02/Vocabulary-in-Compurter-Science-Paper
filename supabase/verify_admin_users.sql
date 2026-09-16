-- Run only in an isolated test project. All changes roll back.
begin;
insert into auth.users(id,raw_user_meta_data,created_at) values
 ('00000000-0000-0000-0000-000000000001','{"user_name":"Alice"}','2026-09-01T10:00:00Z'),
 ('00000000-0000-0000-0000-000000000002','{}','2026-09-02T10:00:00Z'),
 ('00000000-0000-0000-0000-000000000003','{"preferred_username":"Admin"}','2026-09-03T10:00:00Z');
insert into private.admins values ('00000000-0000-0000-0000-000000000003');
insert into public.entries(term,meaning,pos,owner_id) values ('directory-test','test','noun','00000000-0000-0000-0000-000000000001');
set local role anon;
select set_config('request.jwt.claims','{}',true);
do $$ begin
  begin
    perform * from public.admin_list_users();
    raise exception 'Anonymous directory access allowed';
  exception when insufficient_privilege then null; end;
end $$;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001","user_metadata":{"is_admin":true}}',true);
do $$ begin
  begin
    perform * from public.admin_list_users();
    raise exception 'Non-admin directory access allowed';
  exception when insufficient_privilege then null; end;
  begin
    perform * from auth.users;
    raise exception 'Direct auth table access allowed';
  exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000003"}',true);
do $$ begin
  if not exists(select 1 from public.admin_list_users() where username='Alice' and registered_at='2026-09-01T10:00:00Z' and entry_count=1) then raise exception 'Registration data incorrect'; end if;
  if not exists(select 1 from public.admin_list_users() where user_id='00000000-0000-0000-0000-000000000002' and username='未设置用户名' and entry_count=0) then raise exception 'Zero-entry user missing'; end if;
  if exists(select 1 from public.admin_list_users('00000000-0000-0000-0000-000000000002') where user_id <= '00000000-0000-0000-0000-000000000002') then raise exception 'Pagination boundary incorrect'; end if;
end $$;
reset role;
delete from private.admins where user_id='00000000-0000-0000-0000-000000000003';
set local role authenticated;
do $$ begin
  begin
    perform * from public.admin_list_users();
    raise exception 'Revoked admin directory access allowed';
  exception when insufficient_privilege then null; end;
end $$;
rollback;
