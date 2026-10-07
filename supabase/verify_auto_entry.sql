-- Run only in an isolated test database after the auto-entry migration.
-- All test changes roll back. Cron itself is not exercised here.
begin;
delete from private.auto_entry_queue;
insert into private.auto_entry_queue(term,meaning,pos) values
('zzz automated test one','测试','noun'),('zzz automated test two','测试','noun');
do $$ begin
  if private.publish_idle_entry() <> 'not_due' then raise exception 'Published before six days'; end if;
end $$;
update private.auto_entry_state set last_change_at = clock_timestamp() - interval '6 days 1 second', last_auto_at = null;
do $$ begin
  if private.publish_idle_entry() <> 'published' then raise exception 'Idle publication failed'; end if;
  if (select count(*) from public.entries where term like 'zzz automated test%') <> 1 then raise exception 'Expected exactly one entry'; end if;
  if private.publish_idle_entry() <> 'not_due' then raise exception 'Repeated publication'; end if;
end $$;
-- Editing and deleting a system entry also reset the timer.
update private.auto_entry_state set last_change_at = clock_timestamp() - interval '7 days', last_auto_at = null;
update public.entries set meaning = '修改' where term = 'zzz automated test one';
do $$ begin
  if private.publish_idle_entry() <> 'not_due' then raise exception 'Update did not reset activity'; end if;
end $$;
update private.auto_entry_state set last_change_at = clock_timestamp() - interval '7 days';
delete from public.entries where term = 'zzz automated test one';
do $$ begin
  if private.publish_idle_entry() <> 'not_due' then raise exception 'Delete did not reset activity'; end if;
end $$;
insert into public.entries(term,meaning,pos) values('zzz automated test two','已有词条','noun');
do $$ begin
  if private.publish_idle_entry() <> 'not_due' then raise exception 'Insert did not reset activity'; end if;
end $$;
update private.auto_entry_state set last_change_at = clock_timestamp() - interval '7 days';
do $$ begin
  if private.publish_idle_entry() <> 'queue_empty' then raise exception 'Duplicate not skipped'; end if;
  if not exists(select 1 from private.auto_entry_queue where term = 'zzz automated test two' and result = 'duplicate_skipped') then raise exception 'Duplicate not recorded'; end if;
  if private.publish_idle_entry() <> 'queue_empty' then raise exception 'Empty queue handling failed'; end if;
end $$;
set local role authenticated;
do $$ begin
  begin
    perform private.publish_idle_entry();
    raise exception 'Client executed publisher';
  exception when insufficient_privilege then null; end;
  begin
    perform * from private.auto_entry_queue;
    raise exception 'Client read private queue';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
set local role anon;
do $$ begin
  begin
    perform private.publish_idle_entry();
    raise exception 'Visitor executed publisher';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
rollback;
