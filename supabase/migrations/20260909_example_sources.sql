-- Existing databases: run once before deploying the new form.
begin;
alter table public.entries add column if not exists source_venue text not null default '' check(length(source_venue) <= 200);
alter table public.entries add column if not exists source_date text not null default '' check(source_date = '' or source_date ~ '^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$');
alter table public.entries add column if not exists source_location text not null default '' check(length(source_location) <= 300);
grant insert (source_venue,source_date,source_location), update (source_venue,source_date,source_location) on public.entries to authenticated;
commit;
