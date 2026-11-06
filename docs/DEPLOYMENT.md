# PaperLex 部署指南

GitHub Pages 托管静态前端，Supabase 保存社区词条并提供登录。本地预览见 [README](../README.md)，数据生成与备份见[维护指南](MAINTENANCE.md)。

## 新项目初始化

在自己管理的 Supabase 项目中，以 postgres 身份通过 SQL Editor 依次执行：

1. `supabase/schema.sql`：创建词条、权限、用户目录及最近来源记录，仅新项目执行一次。
2. `supabase/seed.sql`：导入初始静态词库。
3. `supabase/migrations/20260911_prevent_duplicate_terms.sql`：启用词条防重。
4. `supabase/migrations/20261106_merge_domains.sql`：统一领域标签。若启用下文的自动补词，在其安装后再执行一次。

确认 `public.entries` 已启用 RLS，保留四项读写策略。将公开连接信息填入 `docs/config.js`：

```js
window.VOCAB_CONFIG = {
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",
  supabasePublishableKey: "sb_publishable_...",
};
```

传统 anon key 也可使用。**不要提交 service_role、sb_secret、数据库密码或 OAuth Client Secret**。浏览器公开密钥依赖数据库权限控制。[Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)

## GitHub 登录与管理员

1. 在 GitHub Settings → Developer settings → OAuth Apps 创建应用，Homepage URL 填网站地址，callback URL 填 Supabase 提供的 `https://YOUR-PROJECT.supabase.co/auth/v1/callback`。
2. 在 Supabase Authentication → Sign In / Providers → GitHub 启用登录，填写 Client ID 和 Client Secret。Secret 仅保存在 Supabase 后台。
3. 在 Supabase Authentication → URL Configuration 设置 Site URL 及 Redirect URLs，均使用完整网站地址并保留末尾 `/`。本地开发另外添加实际使用的地址，如 `http://127.0.0.1:8765/`。

本站地址为 `https://jizhang02.github.io/Vocabulary-in-Compurter-Science-Paper/`，前端使用 PKCE。[GitHub 登录指南](https://supabase.com/docs/guides/auth/social-login/auth-github)

管理员先在网站登录一次，再从 Supabase Authentication → Users 复制其 Auth UUID，执行：

```sql
insert into private.admins (user_id)
values ('替换成你登录账号的UUID')
on conflict do nothing;
```

刷新后显示“管理员 · 退出”。授权不依据昵称或邮箱；初始词条不归属普通用户，由管理员维护。

## 发布 GitHub Pages

推送前端修改后，在 Settings → Pages 选择 **Deploy from a branch → master → /docs**，等待部署完成并检查网站内容。项目使用相对资源路径，`docs/.nojekyll` 支持直接发布，无需前端构建。[GitHub 发布源配置](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

每周备份工作流的启用步骤见[每周社区词库备份](MAINTENANCE.md#每周社区词库备份)，它与 Pages 部署、数据库迁移分别运行。

## 已有数据库升级

仅执行尚未安装的功能迁移，无需重跑 schema 或种子：

| 功能 | SQL 文件 |
| --- | --- |
| 例句出处字段 | `supabase/migrations/20260909_example_sources.sql` |
| 新增与改名防重 | `supabase/migrations/20260911_prevent_duplicate_terms.sql` |
| 用户目录与在线记录 | `supabase/migrations/20260916_user_activity.sql` |
| 最近论文来源同步 | `supabase/migrations/20261019_recent_paper_sources.sql` |
| 领域标签合并 | `supabase/migrations/20261106_merge_domains.sql` |

上述迁移可重复执行。新版用户目录已包含旧版功能，不要在它之后重跑 `20260916_admin_users.sql`。真实数据库操作前请备份数据。

### 领域标签合并

合并迁移将“机器学习”“计算机视觉”“自然语言处理”转换为“计算机科学”，去重并保留其他标签及内容。它同时处理已有自动补词队列；若队列后来才安装，重跑本迁移以安装队列转换触发器。

数据库触发器会转换旧客户端或 API 提交的旧标签。已有词条的更新仍会记录修订、审计及编辑活动。新版前端兼容未迁移的旧标签，但页面显示已合并不等于云端存储已转换。

### 防重、用户目录与最近来源

- **防重**：忽略大小写、首尾空格、连续空格及全角形式。保留原有同名不同释义；同名条目全部删除或改名后，该名称才可重新新增。
- **用户目录**：仅管理员可查看注册时间、上次在线时间及贡献数量，并进入用户的词条列表。在线时间由服务器按可见页面访问记录，每分钟最多更新一次，不等于精确离线时间；未记录时显示“暂无记录”。
- **最近来源**：成功保存词条时，在同一事务内按操作者账号保留最近 3 组来源。打开表单会优先读取云端历史，再合并旧本机记录；同步失败时仍可使用本机历史。管理员修改他人词条时，来源记入管理员自己的历史。

用户活动和最近来源保存在私有表；客户端不能读取其他账号的来源历史，管理员也无该权限。Auth UUID 用于授权，显示时间按浏览器时区呈现。

## 全站闲置超过 6 天自动添加词条

任何用户成功新增、修改或删除词条都会重新计时；浏览与登录不计入。启用时从当前服务器时间开始计算，每天 UTC 08:17 检查，超过连续 6 × 24 小时无编辑时发布一条预备词汇。系统发布后重新计时，因此持续无人编辑时每超过 6 天最多发布一条。

在初始化并启用防重后，以 postgres 依次执行：

1. `supabase/migrations/20261007_auto_entry.sql`。
2. `supabase/migrations/20261106_merge_domains.sql`，确保新队列也转换旧标签。
3. `supabase/enable_auto_entry_cron.sql`，安装每日任务 `paperlex-idle-entry`。

脚本可重复执行，不重置计时、已消费词条或创建重复任务。初始队列有 10 个本站编写释义的真实术语，不附虚构论文或例句；系统词条由管理员维护。重复候选词会跳过，队列耗尽后停止。

查看状态与调度记录：

```sql
select * from private.auto_entry_state;
select * from private.auto_entry_queue order by term;
select jobid, schedule, active from cron.job where jobname = 'paperlex-idle-entry';
select * from cron.job_run_details
where jobid in (select jobid from cron.job where jobname = 'paperlex-idle-entry')
order by start_time desc limit 10;
```

`last_result` 的 `not_due` / `published` / `queue_empty` 分别表示未到期、已发布、队列为空；执行失败查看 Cron 日志。发布与消费在同一事务中完成，并与用户写入互斥。

补充候选词：

```sql
insert into private.auto_entry_queue(term,meaning,pos,domains)
values ('new technical term','经过检查的中文释义','noun',array['计算机科学'])
on conflict (term) do nothing;
```

停用任务（重跑调度脚本可恢复）：

```sql
select cron.unschedule('paperlex-idle-entry');
```

此功能不能保证避免免费项目暂停；暂停期间内部任务也会停止。[Supabase Cron 安装](https://supabase.com/docs/guides/cron/install) · [项目暂停说明](https://supabase.com/docs/guides/platform/free-project-pausing)

## 上线验收与运行边界

用管理员及两个普通测试账号检查：访客可读、GitHub 登录、跨浏览器保存与读取、用户只能修改自己的词、管理员可管理全部词、旧版本保存被拒绝，以及退出后不显示编辑入口。隔离测试与命令见[验证说明](MAINTENANCE.md#验证)；本地模拟测试不等于线上登录、RLS 或 Cron 已通过。

当前投稿立即公开，尚无审核队列或贡献限流。词库按 ID 分页读取后在浏览器检索，无实时推送；刷新可获取他人更新。云端连接失败时可能显示初始只读快照，不代表最新社区内容。数万词规模应改用服务端检索。

SDK 固定为 `2.57.4`，从 jsDelivr 加载；CDN 受限时可改为本地托管。私有审计历史仅供后台恢复参考，社区 Markdown 备份也不替代数据库完整备份。费用和配额以服务控制台为准。
