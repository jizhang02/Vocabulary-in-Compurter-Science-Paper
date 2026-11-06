# PaperLex 维护指南

## 数据来源与生成

| 内容 | 位置 | 更新方式 |
| --- | --- | --- |
| 初始词表 | `docs/glossary_v2.md` | 人工维护，原始行号参与词条 ID 生成 |
| 领域与例句补充 | `data/*_annotations.json` | 按词条 ID 修订 |
| 初始静态快照与种子 | `docs/data/vocabulary.json`、`supabase/seed.sql` | 运行迁移脚本生成 |
| 社区词库 | Supabase `public.entries` | 网站新增、修改和删除 |
| 社区 Markdown 备份 | [`backups/vocabulary.md`](../backups/vocabulary.md) | 每周自动导出 |

```bash
python scripts/migrate_glossary.py
```

脚本保留初始 701 条词汇的词性、不同释义与来源行号，并应用领域和例句补充。原始词项变化后需重新审阅分类。V1 仅作历史资料，不与 V2 合并。

**种子仅用于初始化**：重跑不会覆盖社区编辑，但会恢复已删除的初始条目。初始化后不要移动 V2 原始行；社区内容不会写回原始词表或静态 JSON。分类维护见[分类说明](CLASSIFICATION.md)，数据库升级见[部署指南](DEPLOYMENT.md#已有数据库升级)。

## 每周社区词库备份

`Backup vocabulary` 工作流每周一 UTC 06:17 导出公开词库并提交到默认分支，对应巴黎冬令时 07:17、夏令时 08:17。有变化才提交；已删除词条可从 Git 历史查询。

Markdown 按词性分组、按英文排序，包含释义、例句、出处、贡献者和记录信息，并自动统计词条总数及例句覆盖率。旧的计算机细分类别在导出时归入“计算机科学”，不写回数据库。该备份不含账号、私有历史和数据库结构，不能用于完整恢复 Supabase。

### 启用与手动运行

1. 将工作流和脚本推送到默认分支，启用 GitHub Actions，并允许工作流写入仓库内容。分支保护若禁止机器人直接推送，需先配置相应规则。
2. 在 **Actions → Backup vocabulary → Run workflow** 运行一次，确认备份提交成功。

脚本默认读取 `docs/config.js` 的公开连接信息，无需管理密钥。可选环境变量 `SUPABASE_URL`、`SUPABASE_PUBLISHABLE_KEY` 用于覆盖配置。本地运行：

```bash
python scripts/backup_vocabulary.py
```

导出使用 ID 游标分页并核对条数，随后再读取 ID / 修订版本，检查期间的增删改。请求失败、空词库或校验失败均保留原备份并报错，可重跑工作流。逐页读取仍不是数据库事务快照。

GitHub 定时任务可能延迟；公开仓库连续 60 天无活动时，定时工作流会被自动停用，需在 Actions 中重新启用。[GitHub 定时任务说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 验证

```bash
python -m unittest discover -s tests -v
pip install playwright
# 使用本机已安装的 Microsoft Edge
python tests/browser_smoke.py
python tests/browser_community.py
python tests/browser_activity.py
python tests/browser_source_history.py
# 数据库测试需要 Node.js
npm install --no-save @electric-sql/pglite
node tests/database.mjs
```

Python 检查词条、出处与备份；浏览器检查静态检索、模拟登录和编辑、用户活动及来源历史；PGlite 执行 PostgreSQL 权限、审计和迁移检查。`supabase/verify_*.sql` 仅供隔离测试库，不能替代真实 OAuth、线上 RLS 和定时任务验收。

## 例句与出处

初始静态词库的 701 条均有例句：686 条为论文原句或短摘录，来自 641 篇文献；15 条明确标注“AI 辅助编写，非论文原文”。这些历史统计不代表当前社区规模，最新导出数量见 Markdown 备份。

论文例句通过 PMLR 元数据、Europe PMC 摘要及出版方页面核对，排除错义和缩写同形词。每篇来源累计摘录最多 25 个英文词，共用短句不重复扩展引用；省略部分以省略号标明。日期保留原有精度，不猜测月日，不将预印本或 workshop 标为主会。自拟例句不虚构论文出处，日期为编写日期。

`data/example_annotations.json` 保存例句与出处；`data/example_evidence.json` 保存匹配写法、核查链接、日期和摘要值。重新生成不会丢失补充内容。

原始词条仍有待校订的拼写、词性与释义，例如 `propell → propel`、`jusity → justify`；目前保留原词项，在来源说明中记录规范写法。标签的语义限制见[分类说明](CLASSIFICATION.md#待校订内容)。
