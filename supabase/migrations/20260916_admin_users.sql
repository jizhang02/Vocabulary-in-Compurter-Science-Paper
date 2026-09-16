-- Administrator-only registration directory. Safe to rerun on existing projects.
begin;
create or replace function public.admin_list_users(after_id uuid default null)
returns table(user_id uuid, username text, registered_at timestamptz, entry_count bigint)
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
      u.created_at,
      (select count(*) from public.entries e where e.owner_id = u.id)
    from auth.users u
    where after_id is null or u.id > after_id
    order by u.id limit 100;
end;
$$;
revoke all on function public.admin_list_users(uuid) from public, anon, authenticated;
grant execute on function public.admin_list_users(uuid) to authenticated;
commit;
