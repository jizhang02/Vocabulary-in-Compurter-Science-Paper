# PaperLex · 论文词汇共建

从阅读中来，到研究中去。面向计算机科学、医学与交叉领域的中英双语词汇库。

由 Markdown 摘录升级为可部署到 GitHub Pages 的响应式网页，保留 [V2 原始词表](docs/glossary_v2.md) 和 [旧词表](docs/glossary.md)。

## 当前版本

- **701 个词条、701 个带例句词条**；清理空词条及 `sentence.` 占位例句。
- 搜索英文、中文释义、例句、来源和标签；按词性、多个专业领域、例句完整度及“我的创建”交叉筛选。
- 卡片 / 列表、字母 / 最近更新排序、分页、随机词条、手机适配。
- GitHub 和邮箱验证码登录；作者管理自己的条目，管理员管理全部条目。
- 数据库行级权限、不可由客户端修改的作者归属、编辑版本冲突检查、私有修改历史。

**部署方式：GitHub Pages 发布 `master` 分支的 `/docs` 目录；社区数据库尚待配置。** `docs/config.js` 为空时使用仓库词表，只读访问可独立运行。连接 Supabase 后，以云数据库为唯一社区数据源。

## 本地预览

在仓库根目录运行，然后访问 <http://127.0.0.1:8765/>：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs
# 本机若 python 指向 WindowsApps，可使用：
& C:\Users\Jing\miniconda3\python.exe -m http.server 8765 --bind 127.0.0.1 --directory docs
```

不需要 Node.js 或前端构建。请通过 HTTP 服务访问，直接双击 HTML 会阻止模块及 JSON 加载。

## 上线与权限

按 [部署指南](docs/DEPLOYMENT.md) 配置 GitHub Pages、Supabase、GitHub OAuth、邮箱验证码及管理员。

网站地址：[PaperLex](https://jizhang02.github.io/Vocabulary-in-Compurter-Science-Paper/)。登录及创建、修改、删除须完成下面的 Supabase 配置。

| 访问者 | 浏览 / 搜索 | 添加 | 修改 / 删除自己的词 | 修改 / 删除他人的词 |
| --- | --- | --- | --- | --- |
| 未登录 | ✓ | — | — | — |
| 登录用户 | ✓ | ✓ | ✓ | — |
| 管理员 | ✓ | ✓ | ✓ | ✓ |

原始词条 `owner_id` 留空，由管理员管理。管理员身份由私有表中的 Auth 用户 UUID 决定，不依据前端昵称或邮箱字符串。

## 数据维护

```bash
python scripts/migrate_glossary.py
python -m unittest discover -s tests -v
```

迁移生成 `docs/data/vocabulary.json` 和 `supabase/seed.sql`。保留原始词性、行号、同形词及不同释义。全部 701 条已补齐领域，结果存于 `data/domain_annotations.json`；使用“通用”及六个专业领域，多标签可交叉检索。详见 [分类说明](docs/CLASSIFICATION.md)；原始拼写、词性、译文与引文未逐条校订。V1 留作历史资料，不与 V2 合并。

种子 ID 取决于原始行号和列位置，初始化后不要移动 V2 原始行再导入。重跑相同种子不覆盖社区编辑，**但会恢复已删除的种子条目**，因此仅用于初始化，不用于日常同步。社区修改保存在数据库，不会自动提交回 GitHub。

## 验证

```bash
pip install playwright
# 使用本机已安装的 Microsoft Edge
python tests/browser_smoke.py
python tests/browser_community.py
# 数据库测试需要 Node.js
npm install --no-save @electric-sql/pglite
node tests/database.mjs
```

已通过：迁移检查、Edge 桌面/手机浏览检查、模拟 SDK 的登录和 CRUD 界面测试、PGlite PostgreSQL 中的真实 RLS 与审计测试。`supabase/verify_permissions.sql` 可在隔离 Supabase 测试项目中验证，事务最终回滚。**真实 OAuth、邮件发送与线上 RLS 尚需配置后联调。**

## 结构

```text
docs/                  GitHub Pages 发布目录
  index.html           主页与表单
  styles.css           响应式样式
  app.js / lib.js       界面、检索和 Supabase 集成
  config.js            仅放公开连接信息
  data/vocabulary.json 原始静态快照
  DEPLOYMENT.md        部署步骤
supabase/              schema、种子、权限测试
scripts/               Markdown 迁移与数据整理
tests/                 数据、浏览器和数据库测试
```

项目发起者：Jing Zhang · [GitHub](https://github.com/jizhang02)

## 例句与出处（2026-09-09）

全部 **701 个词条**均有例句：**686 条论文原句或短摘录**，来自 **641 篇文献**；另 **15 条自拟例句**明确标注“AI 辅助编写，非论文原文”。自拟条目没有虚构的论文标题、期刊或论文链接，其日期为编写日期。

卡片展示例句、期刊/会议和日期；点击可查看论文标题、原文位置与链接。搜索支持这些字段。优先使用 ICML、CVPR、ICCV、AISTATS、TACL、Computational Linguistics、TPAMI、Medical Image Analysis、Nature、Science、Cell、Nature Medicine、PNAS 等来源，少数罕见表达采用其他正式期刊。不把所有来源统一称作“顶级”，不将预印本或 workshop 标为主会。

来源通过 PMLR 官方论文元数据、Europe PMC 摘要及出版方页面检索。先检查目标词实际出现，再筛除缩写同形词、明显错义匹配及不完整的片段。每篇来源累计最多摘录 25 个英文词；多词条共享同一短句时不重复扩展引用。长句以省略号标明摘录范围，点击链接可读上下文。日期保留真实精度；期刊优先采用明确的在线发表日期，未提供时只记录年份。会议日期采用论文集的出版日期或明确的会议月份，不猜测月日。

`data/example_annotations.json` 保存例句与出处；`data/example_evidence.json` 保存匹配写法、核查链接、核查日期和例句摘要值。执行 `python scripts/migrate_glossary.py` 会重新应用覆盖层并生成静态词库和 SQL 种子，不会丢失补充内容。原始 Markdown 和词条 ID 保留。

少量原词条存在拼写、词性和释义问题。本次保留原条目，在来源说明中标注规范写法，例如 `propell → propel`、`jusity → justify`、`from...perspecitve → from … perspective`。`herein this work` 和 `presumably speaking` 使用更自然的表达示例。例句及初始释义仍可由读者进一步校订。

已有 Supabase 数据库先运行 `supabase/migrations/20260909_example_sources.sql` 添加字段；新数据库使用 `schema.sql` 和 `seed.sql`。种子脚本不会覆盖现有社区编辑。此次更新的是本地静态快照和新安装种子，未修改任何云端数据库。
