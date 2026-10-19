-- Account-scoped recent paper sources. Safe to rerun on an existing project.
begin;
create table if not exists private.recent_paper_sources (
  user_id uuid primary key references auth.users(id) on delete cascade,
  sources jsonb not null default '[]'::jsonb
    check (jsonb_typeof(sources) = 'array' and jsonb_array_length(sources) <= 3)
);
alter table private.recent_paper_sources enable row level security;
revoke all on private.recent_paper_sources from public, anon, authenticated;

create or replace function private.clean_paper_source(item jsonb) returns jsonb
language plpgsql immutable set search_path = '' as $$
declare result jsonb; field text;
begin
  if jsonb_typeof(item) is distinct from 'object' then
    raise exception 'Invalid paper source' using errcode = '22023';
  end if;
  foreach field in array array['source','source_venue','source_date','source_url'] loop
    if jsonb_typeof(item -> field) is distinct from 'string' then
      raise exception 'Invalid paper source field' using errcode = '22023';
    end if;
  end loop;
  result := jsonb_build_object(
    'source', btrim(item->>'source'), 'source_venue', btrim(item->>'source_venue'),
    'source_date', btrim(item->>'source_date'), 'source_url', btrim(item->>'source_url'));
  if length(result->>'source') > 1000 or length(result->>'source_venue') > 200
    or length(result->>'source_url') > 2000
    or (result->>'source_date' <> '' and result->>'source_date' !~ '^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$')
    or (result->>'source_url' <> '' and result->>'source_url' !~ '^https?://') then
    raise exception 'Invalid paper source value' using errcode = '22023';
  end if;
  return result;
end;
$$;
revoke all on function private.clean_paper_source(jsonb) from public, anon, authenticated;

-- All updates lock one row per account. Merging an older browser history never
-- replaces newer cloud history; entry saves explicitly promote their source.
create or replace function private.merge_paper_sources(actor uuid, incoming jsonb, promote boolean)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare existing jsonb; candidates jsonb; result jsonb := '[]'::jsonb; item jsonb;
begin
  if actor is null or jsonb_typeof(incoming) is distinct from 'array' then
    raise exception 'Invalid source history' using errcode = '22023';
  end if;
  if jsonb_array_length(incoming) > 3 then
    raise exception 'At most three paper sources are allowed' using errcode = '22023';
  end if;
  -- Validate everything before limiting the result, including older imports.
  select coalesce(jsonb_agg(private.clean_paper_source(value) order by position), '[]'::jsonb)
    into incoming from jsonb_array_elements(incoming) with ordinality as items(value, position);
  insert into private.recent_paper_sources(user_id) values(actor) on conflict do nothing;
  select sources into existing from private.recent_paper_sources where user_id = actor for update;
  candidates := case when promote then incoming || existing else existing || incoming end;
  for item in select value from jsonb_array_elements(candidates) loop
    if item <> '{"source":"","source_venue":"","source_date":"","source_url":""}'::jsonb
      and not result @> jsonb_build_array(item) then
      result := result || jsonb_build_array(item);
    end if;
    exit when jsonb_array_length(result) = 3;
  end loop;
  update private.recent_paper_sources set sources = result where user_id = actor;
  return result;
end;
$$;
revoke all on function private.merge_paper_sources(uuid,jsonb,boolean) from public, anon, authenticated;

create or replace function public.recent_paper_sources(local_sources jsonb default '[]'::jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare actor uuid := auth.uid();
begin
  if actor is null or coalesce((auth.jwt()->>'is_anonymous')::boolean, false) then
    raise exception 'Sign in required' using errcode = '42501';
  end if;
  return private.merge_paper_sources(actor, local_sources, false);
end;
$$;
revoke all on function public.recent_paper_sources(jsonb) from public, anon, authenticated;
grant execute on function public.recent_paper_sources(jsonb) to authenticated;

create or replace function private.record_paper_source() returns trigger
language plpgsql security definer set search_path = '' as $$
declare actor uuid := auth.uid();
begin
  if actor is not null and not coalesce((auth.jwt()->>'is_anonymous')::boolean, false) then
    perform private.merge_paper_sources(actor, jsonb_build_array(jsonb_build_object(
      'source',new.source, 'source_venue',new.source_venue,
      'source_date',new.source_date, 'source_url',new.source_url)), true);
  end if;
  return null;
end;
$$;
revoke all on function private.record_paper_source() from public, anon, authenticated;
drop trigger if exists record_paper_source on public.entries;
create trigger record_paper_source after insert or update on public.entries
  for each row execute function private.record_paper_source();
commit;
