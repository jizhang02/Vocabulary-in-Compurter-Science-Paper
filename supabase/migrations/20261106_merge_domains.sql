-- Run as postgres. Safe to repeat; preserves other domains and entry content.
begin;
create or replace function private.normalize_domains(items text[]) returns text[]
language sql immutable strict set search_path = '' as $$
  select coalesce(array_agg(label order by first_position), '{}'::text[])
  from (
    select case when item in ('机器学习','计算机视觉','自然语言处理')
      then '计算机科学' else item end as label, min(position) as first_position
    from unnest(items) with ordinality as source(item, position)
    group by 1
  ) normalized;
$$;
revoke all on function private.normalize_domains(text[]) from public, anon, authenticated;

-- Older clients and direct API writes must follow the same mapping.
create or replace function private.normalize_entry_domains() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.domains := private.normalize_domains(new.domains);
  return new;
end;
$$;
revoke all on function private.normalize_entry_domains() from public, anon, authenticated;
drop trigger if exists normalize_entry_domains on public.entries;
create trigger normalize_entry_domains before insert or update of domains on public.entries
for each row execute function private.normalize_entry_domains();

update public.entries set domains = private.normalize_domains(domains)
where domains && array['机器学习','计算机视觉','自然语言处理'];

-- The optional auto-entry feature may not have been installed yet.
do $$ begin
  if to_regclass('private.auto_entry_queue') is not null then
    update private.auto_entry_queue set domains = private.normalize_domains(domains)
    where domains && array['机器学习','计算机视觉','自然语言处理'];
    drop trigger if exists normalize_entry_domains on private.auto_entry_queue;
    create trigger normalize_entry_domains before insert or update of domains on private.auto_entry_queue
    for each row execute function private.normalize_entry_domains();
  end if;
end $$;
commit;
