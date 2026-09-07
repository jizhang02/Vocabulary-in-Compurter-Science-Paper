# PaperLex 部署指南

GitHub Pages 托管前端，Supabase 提供共享数据库与登录。GitHub Pages 是静态托管，不能直接保存社区投稿或运行 Python。[GitHub 官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

## 1. 本地预览

在仓库根目录运行 `python -m http.server 8765 --bind 127.0.0.1 --directory docs`，访问 `http://127.0.0.1:8765/`。未配置云项目时可以浏览原始词表，不能登录和编辑。

## 2. 数据库

1. 在 [Supabase](https://supabase.com/dashboard) 创建你自己管理的新项目。
2. 在 SQL Editor 运行 `supabase/schema.sql`。只在新项目初始化时执行一次。
3. 运行 `supabase/seed.sql` 导入 701 个原始词条。
4. 确认 `public.entries` 已启用 RLS，并存在四项策略，不要关闭 RLS。
5. 找到 Project URL 和 publishable key，填入 `docs/config.js`：

```js
window.VOCAB_CONFIG = {
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",
  supabasePublishableKey: "sb_publishable_...",
};
```

传统 `anon` key 也可使用。这是供浏览器公开访问的密钥，实际授权由数据库控制。**不要填写或提交 `service_role` key、`sb_secret_...`、数据库密码或 GitHub Client Secret。** [Supabase RLS 文档](https://supabase.com/docs/guides/database/postgres/row-level-security)

社区内容保存在数据库，不会自动回写 GitHub。请定期导出数据库备份；种子脚本仅用于初始化，重跑会恢复已删除的种子词条。

## 3. GitHub 与邮箱登录

在 Supabase Authentication → URL Configuration 设置：

- Site URL：`https://jizhang02.github.io/Vocabulary-in-Compurter-Science-Paper/`
- Redirect URLs：添加同一个完整地址，包括末尾 `/`。
- 本地开发另加 `http://127.0.0.1:8765/`。使用其他端口或路径时，添加对应实际地址。

### GitHub

1. GitHub Settings → Developer settings → OAuth Apps，创建 OAuth App。
2. Homepage URL 填 GitHub Pages 地址。
3. Authorization callback URL 填 **Supabase** 提供的 `https://YOUR-PROJECT.supabase.co/auth/v1/callback`，不是 Pages 地址。
4. Supabase Authentication → Sign In / Providers → GitHub，启用并填 Client ID 和 Client Secret。
5. Client Secret 只保存在 Supabase 后台。

网页使用 PKCE，会话回调返回项目主页。[GitHub 登录官方指南](https://supabase.com/docs/guides/auth/social-login/auth-github)

### 邮箱验证码

1. 启用 Email Provider，允许新用户注册，不需要开启匿名登录。
2. Authentication → Email Templates → Magic Link，将正文改为包含验证码：

```html
<h2>登录 PaperLex</h2>
<p>你的登录验证码是：{{ .Token }}</p>
<p>请在发起登录的网页输入验证码。如果不是你发起的请求，请忽略此邮件。</p>
```

3. 面向公众开放邮箱登录时，配置自己的 SMTP 服务并验证发送域名。Supabase 默认邮件服务用于测试，不应当作公众邮件交付服务。[SMTP 官方说明](https://supabase.com/docs/guides/auth/auth-smtp)
4. 在网页输入邮箱，收到邮件后输入验证码，不用创建网站密码。

`signInWithOtp` 默认发送 Magic Link，模板中的 `{{ .Token }}` 不能省略。[邮箱 OTP 官方指南](https://supabase.com/docs/guides/auth/auth-email-passwordless)

## 4. 你的管理员权限

先在网页用你的 GitHub 或邮箱登录一次，再从 Supabase Authentication → Users 复制该账号的 **UUID**。在 SQL Editor 执行：

```sql
insert into private.admins (user_id)
values ('替换成你登录账号的UUID')
on conflict do nothing;
```

刷新网页，右上角应显示“管理员 · 退出”。管理员列表不放到前端；昵称和显示邮箱不用于授权。

GitHub 与邮箱是否关联到同一用户，以 Users 中的 UUID 为准。如果形成两个账号，而你希望两个都能管理，分别核对身份后登记两个 UUID。邮箱用户公开署名默认为“社区读者”，不把邮箱写入公开词条。

## 5. 发布 GitHub Pages

将准备好的修改提交并推送到仓库发布分支，打开 Settings → Pages：

1. Source 选择 **Deploy from a branch**。
2. 选择实际存放代码的分支（如 `main` 或 `master`）。
3. Folder 选择 **`/docs`**，保存。
4. 等待部署完成，打开 Pages 页面给出的网址。

无需 Node 构建或自定义工作流；`docs/.nojekyll` 让静态资源直接发布。资源使用相对路径，兼容项目子路径。[GitHub 发布源配置](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## 6. 上线验收

用你的管理员账号及两个普通测试账号验证：

| 场景 | 预期 |
| --- | --- |
| 未登录访问、检索、打开词条 | 正常 |
| GitHub / 测试邮箱登录 | 成功；邮件收到验证码 |
| 用户 A 添加，刷新页面、另一浏览器查看 | 数据保留并公开可见 |
| 用户 B 查看 A 的词条 | 无编辑入口，直接 API 越权也被拒绝 |
| A 修改/删除自己的词 | 成功 |
| 管理员修改/删除他人的词及原始词 | 成功 |
| 两个标签页先后修改同一版本 | 后提交者看到版本冲突 |
| 退出登录 | 无编辑入口，“我的贡献”不可选 |

可在**隔离测试项目**执行 `supabase/verify_permissions.sql`，其中临时用户与修改最终回滚。不要将测试 UUID 替换成真实用户。

## 当前边界与维护

- 投稿立即公开，尚无审核队列、举报和贡献限流；社区扩大后优先添加这些治理功能。
- `private.entry_history` 保存增删改记录，仅管理后台可访问，可辅助人工恢复；不是完整备份的替代品。
- 原始词性、拼写和译文未逐条校订，大部分领域保持“未分类”。同形词可作为不同条目保留。
- 当前按 ID 分页读完整词库，再在浏览器搜索；避免接口单页上限截断。数万词规模建议升级数据库端检索分页。
- 没有实时推送，刷新页面获取他人更新；保存时有版本冲突检查。
- 网络故障时提示只读，并可能显示原始快照；快照不是最新社区数据，不与云词条混合。
- 浏览器 SDK 固定为 `2.57.4`，从 jsDelivr 加载。未配置云项目不请求 SDK；CDN 受限时可改为本地打包。
- spaCy 是离线工具，未接入公开网页；在线使用需独立部署 Python 服务、校验用户并限制请求。
- 费用、配额和邮件额度以服务控制台的实际方案为准。
