-- Isolated database test; all synthetic users and timestamps roll back.
begin;
insert into auth.users(id) values
 ('00000000-0000-0000-0000-000000000001'),
 ('00000000-0000-0000-0000-000000000002'),
 ('00000000-0000-0000-0000-000000000003');
insert into private.admins values ('00000000-0000-0000-0000-000000000003');
set local role anon;
select set_config('request.jwt.claims','{}',true);
do $$ begin
  begin
    perform public.record_activity();
    raise exception 'Visitor recorded activity';
  exception when insufficient_privilege then null; end;
end $$;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000002","is_anonymous":true}',true);
do $$ begin
  begin
    perform public.record_activity();
    raise exception 'Anonymous user recorded activity';
  exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001"}',true);
select public.record_activity();
do $$ begin
  begin
    perform * from private.user_activity;
    raise exception 'User read private activity';
  exception when insufficient_privilege then null; end;
  begin
    insert into private.user_activity(user_id) values ('00000000-0000-0000-0000-000000000002');
    raise exception 'User forged activity';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ begin
  if not exists(select 1 from private.user_activity where user_id='00000000-0000-0000-0000-000000000001' and last_seen_at=now()) then raise exception 'Server timestamp not recorded'; end if;
  if exists(select 1 from private.user_activity where user_id='00000000-0000-0000-0000-000000000002') then raise exception 'Wrong user activity recorded'; end if;
end $$;
update private.user_activity set last_seen_at=now()-interval '30 seconds';
set local role authenticated;
select public.record_activity();
reset role;
do $$ begin
  if not exists(select 1 from private.user_activity where last_seen_at=now()-interval '30 seconds') then raise exception 'Activity throttle failed'; end if;
end $$;
update private.user_activity set last_seen_at=now()-interval '2 minutes';
set local role authenticated;
select public.record_activity();
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000003"}',true);
do $$ begin
  if not exists(select 1 from public.admin_list_users() where user_id='00000000-0000-0000-0000-000000000001' and last_seen_at=now()) then raise exception 'Admin last seen missing'; end if;
  if not exists(select 1 from public.admin_list_users() where user_id='00000000-0000-0000-0000-000000000002' and last_seen_at is null) then raise exception 'Unseen timestamp fabricated'; end if;
end $$;
rollback;
