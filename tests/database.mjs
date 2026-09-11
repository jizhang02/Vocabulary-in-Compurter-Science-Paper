// npm install --no-save @electric-sql/pglite, then node tests/database.mjs.
// Optional argument: path to a separately downloaded PGlite entry module.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const { PGlite } = await import(process.argv[2] ? pathToFileURL(resolve(process.argv[2])).href : '@electric-sql/pglite');
const db = new PGlite();
try {
  // Minimal Supabase auth contract; real roles/RLS/triggers execute in Postgres.
  await db.exec(`
    create role anon; create role authenticated;
    create schema auth;
    create table auth.users(id uuid primary key);
    create function auth.jwt() returns jsonb language sql stable as
      $$ select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb $$;
    create function auth.uid() returns uuid language sql stable as
      $$ select (auth.jwt()->>'sub')::uuid $$;
    grant usage on schema auth to anon,authenticated;
    grant execute on all functions in schema auth to anon,authenticated;
  `);
  await db.exec(await readFile(new URL('../supabase/schema.sql',import.meta.url),'utf8'));
  await db.exec(await readFile(new URL('../supabase/seed.sql',import.meta.url),'utf8'));
  await db.exec(await readFile(new URL('../supabase/seed.sql',import.meta.url),'utf8'));
  const {rows} = await db.query('select count(*)::int as count from public.entries');
  if (rows[0].count !== 701) throw new Error(`Expected 701 seed rows, got ${rows[0].count}`);
  await db.exec(await readFile(new URL('../supabase/verify_permissions.sql',import.meta.url),'utf8'));
  const migration = await readFile(new URL('../supabase/migrations/20260911_prevent_duplicate_terms.sql',import.meta.url),'utf8');
  await db.exec(migration);
  await db.exec(migration);
  await db.exec(await readFile(new URL('../supabase/seed.sql',import.meta.url),'utf8'));
  await db.exec(`
    begin;
    insert into public.entries(term,meaning,pos) values ('Unique Test Phrase','test','phrase');
    do $$ begin
      begin
        insert into public.entries(term,meaning,pos) values ('  UNIQUE   TEST PHRASE  ','duplicate','phrase');
        raise exception 'Duplicate insert was accepted';
      exception when unique_violation then null; end;
      begin
        insert into public.entries(term,meaning,pos) values ('discern','legacy duplicate','verb');
        raise exception 'Legacy duplicate insert was accepted';
      exception when unique_violation then null; end;
    end $$;
    insert into public.entries(term,meaning,pos) values ('Different Test Phrase','test','phrase');
    do $$ begin
      begin
        update public.entries set term = 'unique test phrase' where term = 'Different Test Phrase';
        raise exception 'Duplicate rename was accepted';
      exception when unique_violation then null; end;
    end $$;
    update public.entries set meaning = 'edited' where term = 'discern';
    delete from public.entries where term = 'Unique Test Phrase';
    update public.entries set term = 'Unique Test Phrase' where term = 'Different Test Phrase';
    insert into public.entries(term,meaning,pos) values ('Different Test Phrase','reuse old name','phrase');
    do $$ begin
      if exists (
        select 1 from private.entry_term_counts c
        where c.entry_count <> (select count(*) from public.entries e where private.term_key(e.term) = c.term_key)
      ) then raise exception 'Term counts are inconsistent'; end if;
    end $$;
    rollback;
  `);
  console.log('PASS: duplicate insert/rename rejection, legacy preservation, deletion/name reuse, migration and seed idempotence.');
  console.log('PASS: schema, idempotent seed, public reads, owner edits, stranger denial, admin edits/deletes, immutable ownership, no self promotion, stale revisions, audit history.');
} finally { await db.close(); }
