-- User directory with server-recorded last activity. Safe to rerun.
-- Works whether or not the earlier admin directory migration was applied.
begin;
create table if not exists private.user_activity (
  user_id uuid primary key references auth.users(id) on delete cascade,
  last_seen_at timestamptz not null default now()
);
alter table private.user_activity enable row level security;
revoke all on private.user_activity from public, anon, authenticated;

create or replace function public.record_activity() returns void
language plpgsql security definer set search_path = '' as $$
declare actor uuid := auth.uid();
begin
  if actor is null or coalesce((auth.jwt()->>'is_anonymous')::boolean, false) then
    raise exception 'Sign in required' using errcode = '42501';
  end if;
  insert into private.user_activity as activity(user_id,last_seen_at)
    values(actor,now())
    on conflict (user_id) do update set last_seen_at = excluded.last_seen_at
    where activity.last_seen_at <= now() - interval '1 minute';
end;
$$;
revoke all on function public.record_activity() from public, anon, authenticated;
grant execute on function public.record_activity() to authenticated;

-- PostgreSQL requires recreation when a function's result columns change.
drop function if exists public.admin_list_users(uuid);
create function public.admin_list_users(after_id uuid default null)
returns table(user_id uuid, username text, registered_at timestamptz, last_seen_at timestamptz, entry_count bigint)
language plpgsql stable security definer set search_path = '' as $$
begin
  if not coalesce(public.is_admin(), false) then
    raise exception 'Administrator access required' using errcode = '42501';
  end if;
  return query
    select u.id,
      coalesce(nullif(btrim(u.raw_user_meta_data->>'user_name'), ''),
               nullif(btrim(u.raw_user_meta_data->>'preferred_username'), ''),
               nullif(btrim(u.raw_user_meta_data->>'name'), ''), '未设置用户名'),
      u.created_at, a.last_seen_at,
      (select count(*) from public.entries e where e.owner_id = u.id)
    from auth.users u
    left join private.user_activity a on a.user_id = u.id
    where after_id is null or u.id > after_id
    order by u.id limit 100;
end;
$$;
revoke all on function public.admin_list_users(uuid) from public, anon, authenticated;
grant execute on function public.admin_list_users(uuid) to authenticated;
commit;
