-- Isolated test database only; expects the fixtures in tests/database.mjs.
begin;
do $$ begin
  if not exists (
    select 1 from public.entries where term = 'Domain Merge Test'
      and domains = array['计算机科学','医学']
      and meaning = 'preserve meaning' and tags = array['preserve tag']
  ) then raise exception 'Existing entry merge lost labels or content'; end if;
  if not exists (
    select 1 from private.auto_entry_queue where term = 'gradient accumulation'
      and domains = array['计算机科学','数学']
  ) then raise exception 'Queue merge failed'; end if;
  if exists (
    select 1 from public.entries where domains && array['机器学习','计算机视觉','自然语言处理']
  ) then raise exception 'Legacy domains remain'; end if;
end $$;

insert into public.entries(term,meaning,pos,domains)
values ('Legacy Domain Write','test','noun',array['自然语言处理','数学','机器学习','计算机科学']);
update public.entries set domains = array['计算机视觉','医学','计算机视觉']
where term = 'Domain Merge Test';
insert into private.auto_entry_queue(term,meaning,pos,domains)
values ('Legacy Queue Write','test','noun',array['机器学习','数学','计算机科学']);
do $$ begin
  if not exists (select 1 from public.entries where term = 'Legacy Domain Write'
    and domains = array['计算机科学','数学']) then raise exception 'Legacy insert failed'; end if;
  if not exists (select 1 from public.entries where term = 'Domain Merge Test'
    and domains = array['计算机科学','医学']) then raise exception 'Legacy update failed'; end if;
  if not exists (select 1 from private.auto_entry_queue where term = 'Legacy Queue Write'
    and domains = array['计算机科学','数学']) then raise exception 'Legacy queue insert failed'; end if;
  if private.normalize_domains('{}'::text[]) <> '{}'::text[]
    then raise exception 'Empty domains changed'; end if;
  begin
    insert into public.entries(term,meaning,pos,domains)
    values ('Null Domain Write','test','noun',null);
    raise exception 'Null domains were silently accepted';
  exception when not_null_violation then null;
  end;
end $$;
rollback;
