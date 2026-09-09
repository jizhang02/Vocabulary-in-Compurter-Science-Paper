-- Run once in a NEW Supabase project's SQL editor, as postgres.
begin;
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table private.admins (
  user_id uuid primary key references auth.users(id) on delete cascade
);
revoke all on private.admins from public, anon, authenticated;

create function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists(select 1 from private.admins where user_id = (select auth.uid()));
$$;
revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to anon, authenticated;

create function private.valid_tags(items text[]) returns boolean
language sql immutable set search_path = '' as $$
  select cardinality(items) <= 12 and not exists (
    select 1 from unnest(items) item
    where item is null or length(btrim(item)) = 0 or length(item) > 40
  );
$$;

create table public.entries (
  id uuid primary key default gen_random_uuid(),
  term text not null check(length(btrim(term)) between 1 and 200),
  meaning text not null check(length(btrim(meaning)) between 1 and 1000),
  pos text not null check(pos in ('verb','noun','adjective-adverb','phrase')),
  domains text[] not null default '{}' check(private.valid_tags(domains)),
  tags text[] not null default '{}' check(private.valid_tags(tags)),
  example text not null default '' check(length(example) <= 5000),
  source text not null default '' check(length(source) <= 1000),
  source_venue text not null default '' check(length(source_venue) <= 200),
  source_date text not null default '' check(source_date = '' or source_date ~ '^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$'),
  source_location text not null default '' check(length(source_location) <= 300),
  source_url text not null default '' check(length(source_url) <= 2000 and (source_url = '' or source_url ~ '^https?://')),
  owner_id uuid references auth.users(id) on delete set null default auth.uid(),
  author_name text not null default '社区读者' check(length(btrim(author_name)) between 1 and 100),
  provenance text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  revision integer not null default 1
);
create index entries_owner_idx on public.entries(owner_id);
create index entries_updated_idx on public.entries(updated_at desc);
create index entries_domains_idx on public.entries using gin(domains);

create function private.guard_entry() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if TG_OP = 'UPDATE' then
    -- Ownership and provenance cannot be reassigned by a client, including admins.
    -- Trusted SQL maintenance (auth.uid() is null) can handle deleted users/imports.
    if auth.uid() is not null then
      new.id := old.id;
      new.owner_id := old.owner_id;
      new.author_name := old.author_name;
      new.provenance := old.provenance;
      new.created_at := old.created_at;
    end if;
    new.revision := old.revision + 1;
  else
    if auth.uid() is not null then
      new.owner_id := auth.uid();
      new.provenance := '';
    end if;
    new.created_at := now();
    new.revision := 1;
  end if;
  new.updated_at := now();
  return new;
end;
$$;
create trigger guard_entry before insert or update on public.entries
for each row execute function private.guard_entry();

-- Private change history for recovery/audit, never publicly readable.
create table private.entry_history (
  id bigint generated always as identity primary key,
  entry_id uuid not null,
  action text not null,
  actor_id uuid,
  changed_at timestamptz not null default now(),
  old_row jsonb,
  new_row jsonb
);
revoke all on private.entry_history from public, anon, authenticated;
create function private.audit_entry() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into private.entry_history(entry_id,action,actor_id,old_row,new_row)
  values(coalesce(new.id,old.id),TG_OP,auth.uid(),
    case when TG_OP = 'INSERT' then null else to_jsonb(old) end,
    case when TG_OP = 'DELETE' then null else to_jsonb(new) end);
  return null;
end;
$$;
create trigger audit_entry after insert or update or delete on public.entries
for each row execute function private.audit_entry();

alter table public.entries enable row level security;
revoke all on public.entries from public, anon, authenticated;
grant select on public.entries to anon, authenticated;
grant insert (term,meaning,pos,domains,tags,example,source,source_venue,source_date,source_location,source_url,owner_id,author_name)
  on public.entries to authenticated;
grant update (term,meaning,pos,domains,tags,example,source,source_venue,source_date,source_location,source_url)
  on public.entries to authenticated;
grant delete on public.entries to authenticated;

create policy "Public reading" on public.entries for select to anon, authenticated using (true);
create policy "Contributors insert their own entries" on public.entries for insert to authenticated
  with check(owner_id = (select auth.uid()) and not coalesce((auth.jwt()->>'is_anonymous')::boolean,false));
create policy "Authors and admins edit" on public.entries for update to authenticated
  using(owner_id = (select auth.uid()) or (select public.is_admin()))
  with check(owner_id = (select auth.uid()) or (select public.is_admin()));
create policy "Authors and admins delete" on public.entries for delete to authenticated
  using(owner_id = (select auth.uid()) or (select public.is_admin()));
commit;
