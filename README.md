# PaperLex · 论文词汇共建

从阅读中来，到研究中去。面向计算机科学、医学与交叉领域的中英双语词汇库。

由 Markdown 摘录升级为可部署到 GitHub Pages 的响应式网页，保留 [V2 原始词表](docs/glossary_v2.md) 和 [旧词表](docs/glossary.md)。

## 当前版本

- **701 个词条、31 个真实例句**；清理空词条及 `sentence.` 占位例句。
- 搜索英文、中文释义、例句、来源和标签；按词性、多个专业领域、例句完整度及“我的贡献”交叉筛选。
- 卡片 / 列表、字母 / 最近更新排序、分页、随机词条、手机适配。
- GitHub 和邮箱验证码登录；作者管理自己的条目，管理员管理全部条目。
- 数据库行级权限、不可由客户端修改的作者归属、编辑版本冲突检查、私有修改历史。
- 可选 spaCy 离线工具：输出词性、词形和候选名词短语，供人工审核。

**部署状态：本地代码已准备好，尚未连接云项目或公开发布。** `docs/config.js` 为空时使用仓库词表，只读访问可独立运行。连接 Supabase 后，以云数据库为唯一社区数据源。

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

预期网址为 `https://jizhang02.github.io/Vocabulary-in-Compurter-Science-Paper/`，需发布后才可访问。

| 访问者 | 浏览 / 搜索 | 添加 | 修改 / 删除自己的词 | 修改 / 删除他人的词 |
| --- | --- | --- | --- | --- |
| 未登录 | ✓ | — | — | — |
| 登录用户 | ✓ | ✓ | ✓ | — |
| 管理员 | ✓ | ✓ | ✓ | ✓ |

原始词条 `owner_id` 留空，由管理员管理。管理员身份由私有表中的 Auth 用户 UUID 决定，不依据前端昵称或邮箱字符串。

## spaCy：辅助整理，不自动发布

输入论文例句 / 摘要 → 词性与词形 → 候选短语 → 人工确认 → 网页添加。

```bash
# 建议在 Python 3.11 / 3.12 独立环境中运行
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-nlp.txt
python -m spacy download en_core_web_sm
python scripts/suggest_tags.py --text "We delineate the left atrium in magnetic resonance images." --output suggestions.json
```

`--input abstract.txt` 支持 UTF-8 文件。词性依赖上下文；名词短语候选不等于经验证的专业术语。工具不翻译、不自动赋予专业领域标签、不写入数据库。当前网页没有在线 spaCy 按钮，GitHub Pages 不运行 Python。后续可独立部署受限 Python API，让用户确认建议后保存。医学术语需单独评估领域语料与模型。参见 [spaCy 官方功能说明](https://spacy.io/usage/linguistic-features)。

## 数据维护

```bash
python scripts/migrate_glossary.py
python -m unittest discover -s tests -v
```

迁移生成 `docs/data/vocabulary.json` 和 `supabase/seed.sql`。保留原始词性、行号、同形词及不同释义。少量领域标签来自脚本内的明确词项映射，其余标为“未分类”；原始拼写、词性、译文与引文未逐条校订。V1 留作历史资料，不与 V2 合并。

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

已通过：迁移检查、Edge 桌面/手机浏览检查、模拟 SDK 的登录和 CRUD 界面测试、PGlite PostgreSQL 中的真实 RLS 与审计测试。`supabase/verify_permissions.sql` 可在隔离 Supabase 测试项目中验证，事务最终回滚。**真实 OAuth、邮件发送与线上 RLS 尚需配置后联调；spaCy 模型未在本机安装验证。**

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
scripts/               Markdown 迁移、spaCy 建议工具
tests/                 数据、浏览器和数据库测试
```

项目发起者：Jing Zhang · [GitHub](https://github.com/jizhang02)
