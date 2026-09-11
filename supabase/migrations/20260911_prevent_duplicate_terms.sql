-- Run after schema.sql and seed.sql. Existing duplicate entries are preserved.
begin;
create or replace function private.term_key(value text) returns text
language sql immutable strict set search_path = '' as $$
  select btrim(regexp_replace(lower(normalize(value, NFKC)), '[[:space:]]+', ' ', 'g'));
$$;
revoke all on function private.term_key(text) from public, anon, authenticated;

-- A persistent counter provides row locking for concurrent inserts/renames.
-- Counts above one are allowed only for duplicates that predate this migration.
create table if not exists private.entry_term_counts (
  term_key text primary key,
  entry_count integer not null check (entry_count >= 0)
);
revoke all on private.entry_term_counts from public, anon, authenticated;
lock table public.entries in share row exclusive mode;
truncate private.entry_term_counts;
insert into private.entry_term_counts
select private.term_key(term), count(*) from public.entries group by 1;

create or replace function private.check_unique_term() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  old_key text;
  new_key text;
begin
  if TG_OP <> 'INSERT' then old_key := private.term_key(old.term); end if;
  if TG_OP <> 'DELETE' then new_key := private.term_key(new.term); end if;
  if TG_OP = 'UPDATE' and old_key = new_key then return new; end if;

  if TG_OP <> 'DELETE' then
    insert into private.entry_term_counts (term_key, entry_count)
    values (new_key, 1)
    on conflict (term_key) do update set entry_count = 1
      where private.entry_term_counts.entry_count = 0;
    if not found then
      raise exception 'This vocabulary term already exists'
        using errcode = '23505', constraint = 'entries_term_unique';
    end if;
  end if;
  if TG_OP <> 'INSERT' then
    update private.entry_term_counts set entry_count = entry_count - 1
    where term_key = old_key;
  end if;
  return null;
end;
$$;
revoke all on function private.check_unique_term() from public, anon, authenticated;
drop trigger if exists check_unique_term on public.entries;
-- AFTER ensures an idempotent seed's ON CONFLICT DO NOTHING does not count.
create trigger check_unique_term after insert or update of term or delete
on public.entries for each row execute function private.check_unique_term();
commit;
