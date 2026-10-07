-- Run as postgres AFTER migrations/20261007_auto_entry.sql.
begin;
create extension if not exists pg_cron with schema pg_catalog;
-- A named schedule is updated on rerun, rather than duplicated.
select cron.schedule('paperlex-idle-entry', '17 * * * *',
  'select private.publish_idle_entry();');
commit;
