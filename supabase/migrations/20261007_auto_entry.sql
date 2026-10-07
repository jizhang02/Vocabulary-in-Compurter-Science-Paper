-- Run as postgres after 20260911_prevent_duplicate_terms.sql.
-- Scheduling is installed separately so this logic can be tested without pg_cron.
begin;
create table if not exists private.auto_entry_state (
  singleton boolean primary key default true check (singleton),
  last_change_at timestamptz not null default now(),
  last_auto_at timestamptz,
  last_check_at timestamptz,
  last_result text
);
insert into private.auto_entry_state(singleton) values(true) on conflict do nothing;
create table if not exists private.auto_entry_queue (
  term text primary key,
  meaning text not null,
  pos text not null check(pos in ('verb','noun','adjective-adverb','phrase')),
  domains text[] not null default array['通用'],
  consumed_at timestamptz,
  result text
);
revoke all on private.auto_entry_state, private.auto_entry_queue from public, anon, authenticated;

create or replace function private.track_entry_change() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Only our trusted automated INSERT is excluded; edits/deletes still count.
  if TG_OP = 'INSERT' then
    if auth.uid() is null and new.provenance = 'paperlex:auto-entry:v1' then return null; end if;
  end if;
  update private.auto_entry_state set last_change_at = clock_timestamp() where singleton;
  return null;
end;
$$;
revoke all on function private.track_entry_change() from public, anon, authenticated;
drop trigger if exists track_entry_change on public.entries;
create trigger track_entry_change after insert or update or delete on public.entries
for each row execute function private.track_entry_change();

create or replace function private.publish_idle_entry() returns text
language plpgsql security definer set search_path = '' as $$
declare
  activity private.auto_entry_state%rowtype;
  candidate private.auto_entry_queue%rowtype;
  checked_at timestamptz := clock_timestamp();
  outcome text := 'queue_empty';
begin
  -- Serialize with both user writes and other workers before checking activity.
  lock table public.entries in share row exclusive mode;
  select * into strict activity from private.auto_entry_state where singleton for update;
  checked_at := clock_timestamp();
  if greatest(activity.last_change_at, activity.last_auto_at) >= checked_at - interval '6 days' then
    outcome := 'not_due';
  else
    for candidate in select * from private.auto_entry_queue where consumed_at is null order by term for update loop
      begin
        insert into public.entries(term,meaning,pos,domains,owner_id,author_name,source,provenance)
        values(candidate.term,candidate.meaning,candidate.pos,candidate.domains,null,
          'PaperLex 系统','系统自动添加；释义为本站编写，非论文引文。','paperlex:auto-entry:v1');
        update private.auto_entry_queue set consumed_at = checked_at, result = 'published' where term = candidate.term;
        update private.auto_entry_state set last_auto_at = checked_at where singleton;
        outcome := 'published';
        exit;
      exception when unique_violation then
        update private.auto_entry_queue set consumed_at = checked_at, result = 'duplicate_skipped' where term = candidate.term;
      end;
    end loop;
  end if;
  update private.auto_entry_state set last_check_at = checked_at, last_result = outcome where singleton;
  return outcome;
end;
$$;
revoke all on function private.publish_idle_entry() from public, anon, authenticated;

-- Locally authored definitions; no invented paper examples or references.
insert into private.auto_entry_queue(term,meaning,pos,domains) values
('gradient accumulation','梯度累积：累积多个小批次的梯度，再执行一次参数更新。','noun',array['机器学习']),
('concept drift','概念漂移：数据与目标之间的统计关系随时间发生变化。','noun',array['机器学习']),
('data leakage','数据泄漏：训练或模型选择过程中使用了实际预测时不可获得的信息。','noun',array['机器学习']),
('catastrophic forgetting','灾难性遗忘：模型学习新任务后，在先前任务上的能力明显下降。','noun',array['机器学习']),
('ablation study','消融研究：移除或替换模型组件，以评估其对结果的影响。','noun',array['机器学习']),
('out-of-distribution detection','分布外检测：识别与模型训练数据分布明显不同的输入。','noun',array['机器学习']),
('calibration error','校准误差：模型预测置信度与实际正确率之间的差异。','noun',array['机器学习']),
('idempotency','幂等性：重复执行同一操作与执行一次产生相同的结果。','noun',array['通用']),
('optimistic concurrency control','乐观并发控制：提交修改时检查版本或状态变化，以检测并发冲突。','noun',array['通用']),
('exponential backoff','指数退避：操作失败后，以逐步增大的等待间隔重试。','noun',array['通用'])
on conflict (term) do nothing;
commit;
