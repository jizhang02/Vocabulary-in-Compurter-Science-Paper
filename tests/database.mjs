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
  console.log('PASS: schema, idempotent seed, public reads, owner edits, stranger denial, admin edits/deletes, immutable ownership, no self promotion, stale revisions, audit history.');
} finally { await db.close(); }
