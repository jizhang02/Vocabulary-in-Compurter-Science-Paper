-- Isolated test database only. Synthetic users, entries and history roll back.
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
    perform public.recent_paper_sources();
    raise exception 'Visitor read source history';
  exception when insufficient_privilege then null; end;
end $$;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000002","is_anonymous":true}',true);
do $$ begin
  begin
    perform public.recent_paper_sources();
    raise exception 'Anonymous session read source history';
  exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001"}',true);
do $$ declare actual jsonb; before_invalid jsonb; begin
  if public.recent_paper_sources() <> '[]'::jsonb then raise exception 'New account has history'; end if;
  actual := public.recent_paper_sources('[
    {"source":"Paper A","source_venue":"Venue","source_date":"2025-06","source_url":"https://doi.org/a"},
    {"source":"Paper B","source_venue":"","source_date":"","source_url":""},
    {"source":"Paper A","source_venue":"Venue","source_date":"2025-06","source_url":"https://doi.org/a"}]');
  if jsonb_array_length(actual) <> 2 or actual->0->>'source' <> 'Paper A' then raise exception 'Import order or deduplication failed'; end if;
  before_invalid := actual;
  begin
    perform public.recent_paper_sources('{}');
    raise exception 'Non-array history accepted';
  exception when invalid_parameter_value then null; end;
  begin
    perform public.recent_paper_sources('[{},{},{},{}]');
    raise exception 'Oversized history accepted';
  exception when invalid_parameter_value then null; end;
  begin
    perform public.recent_paper_sources('[{"source":"Invalid","source_venue":"","source_date":"2026-99","source_url":""}]');
    raise exception 'Invalid date accepted';
  exception when invalid_parameter_value then null; end;
  begin
    perform public.recent_paper_sources('[{"source":"Invalid","source_venue":"","source_date":"","source_url":"javascript:alert(1)"}]');
    raise exception 'Unsafe link accepted';
  exception when invalid_parameter_value then null; end;
  if public.recent_paper_sources() <> before_invalid then raise exception 'Invalid import changed history'; end if;
  begin
    perform * from private.recent_paper_sources;
    raise exception 'Private history was readable';
  exception when insufficient_privilege then null; end;
  begin
    perform private.merge_paper_sources('00000000-0000-0000-0000-000000000002','[]',true);
    raise exception 'User forged another account history';
  exception when insufficient_privilege then null; end;
end $$;
insert into public.entries(term,meaning,pos,source) values ('history test C','meaning','noun','Paper C');
insert into public.entries(term,meaning,pos,source) values ('history test D','meaning','noun','Paper D');
do $$ declare actual jsonb; begin
  actual := public.recent_paper_sources();
  if jsonb_array_length(actual) <> 3 or actual->0->>'source' <> 'Paper D'
    or actual->1->>'source' <> 'Paper C' or actual->2->>'source' <> 'Paper A' then
    raise exception 'Successful saves did not preserve bounded recent order';
  end if;
  -- A stale device must not overwrite more recently saved cloud sources.
  if public.recent_paper_sources('[{"source":"Old device","source_venue":"","source_date":"","source_url":""}]') <> actual then
    raise exception 'Old local data replaced recent cloud data';
  end if;
  begin
    insert into public.entries(term,meaning,pos,source) values ('history invalid','meaning','invalid','Failed paper');
  exception when check_violation then null; end;
  if public.recent_paper_sources() <> actual then raise exception 'Failed save changed history'; end if;
end $$;
update public.entries set source='Paper C' where term='history test D';
insert into public.entries(term,meaning,pos) values ('history empty','meaning','noun');
do $$ declare actual jsonb; begin
  actual := public.recent_paper_sources();
  if actual->0->>'source' <> 'Paper C' or jsonb_array_length(actual) <> 3 then
    raise exception 'Repeat promotion, deduplication or blank-source handling failed';
  end if;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000002"}',true);
do $$ begin
  if public.recent_paper_sources() <> '[]'::jsonb then raise exception 'Another user saw history'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000003"}',true);
update public.entries set source='Admin paper' where term='history test C';
do $$ begin
  if public.recent_paper_sources()->0->>'source' <> 'Admin paper' then raise exception 'Admin save was not recorded for the acting account'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000001"}',true);
do $$ begin
  if public.recent_paper_sources()->0->>'source' = 'Admin paper' then raise exception 'Admin save changed the owner history'; end if;
end $$;
reset role;
delete from auth.users where id='00000000-0000-0000-0000-000000000002';
do $$ begin
  if exists(select 1 from private.recent_paper_sources where user_id='00000000-0000-0000-0000-000000000002') then raise exception 'Deleted account history retained'; end if;
end $$;
rollback;
