# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **本仓库不是软件工程项目。** 这里没有 build / lint / test，没有要编译运行的程序。
> 它是一个**个人 Co-Worker（协作伙伴）工作空间** —— 用来收集、整理、合成多来源资料，并产出交付物。
> 你在这里扮演的是"同事/助理"，而不是"程序员"。常见动作是：归档资料、检索、合成、写作、配图、发布。

---

## 1. 这是什么

一个**按来源归档原始数据 → 加工 → 产出交付物**的个人工作空间。数据流：

```
sources/        deliverables/
原始数据   ──加工合成──▶   交付物
(按来源分类)              (飞书文档 / 本地文档 / 线上 HTML)
        ▲                       │
        └──── workstreams/ ◀────┘
        (进行中的工作台：草稿、计划、合成中间产物)
```

- **`sources/`** 装各种来源的**原始数据**：飞书（多租户的单聊/群聊/文档）、得到/Get笔记、微信、公众号、其他社媒、个人知识库，以及临时丢东西的 `inbox/`。可由你手动放入，也可由 `scripts/pull-*` 或**外部 Agent**（如接到飞书里的 Codex）主动写入。
- **`deliverables/`** 装你/Agent **产出的成果**：要回写飞书的文档、本地终稿、要发布到线上的 HTML。
- **`workstreams/`** 是**进行中的工作台**：某个主题/任务的草稿、提纲、合成中间产物，定稿后再落到 `deliverables/`。
- **`assets/`** 存图片等**素材**，被交付物引用。
- **`scripts/`** 是**单一实现层**：拉取/生图等自动化脚本，Claude 技能、Codex（`AGENTS.md`）、定时器都调它（见 §8）。

## 2. 顶层结构

| 目录 | 用途 | 读写 |
| --- | --- | --- |
| `sources/` | 原始数据，按来源分类（feishu / getnote / wechat / mp / social / knowledge / inbox） | **只读为主 / 仅追加**，勿改写删除 |
| `deliverables/` | 交付物（feishu / local / web） | 产出区 |
| `workstreams/` | 进行中的主题工作台 | 草稿区 |
| `assets/` | 图片等素材 | 按需 |
| `scripts/` | 自动化与可复用脚本（agent 无关，单一实现） | 见 `scripts/README.md` |

每个目录下都有 `README.md` 说明该区约定，先读它再动手。

## 3. 黄金法则

1. **来源只读、仅追加。** 不要改写或删除 `sources/` 里的原始数据；要加工就读出来、写进 `deliverables/` 或 `workstreams/`。原始数据是事实底稿，必须可追溯。
2. **每个文件带 frontmatter。** 来源文件和交付物都用 YAML frontmatter 标注元数据（见 §4），让任何 Agent 不读全文也能判断它是什么、来自哪、是否新鲜。
3. **交付物要溯源。** 每个交付物在 frontmatter 的 `sources:` 里列出它引用的来源文件路径，形成回链。读者/未来的你能顺藤摸瓜回到底稿。
4. **inbox 三步走：** 看 → 归类 → 落到正确的来源文件夹（并补全 frontmatter）。`inbox/` 不是长期存放地，是中转站。
5. **先看 README。** 动某个区之前先读该区 `README.md`；它定义了命名与字段约定。

## 4. frontmatter 约定（核心契约）

**来源文件**（`sources/**/*.md`）：

```yaml
---
source: feishu          # feishu | dingtalk | tencent-meeting | getnote | wechat | mp | social | blog | knowledge | inbox
tenant: <租户名>         # 多租户来源（飞书/钉钉）需要；其余可省略
channel: <会话/群/作者>  # 单聊对象、群名、公众号名、作者等
type: dm                # dm | group | doc | article | note | contacts | meeting
captured: 2026-06-14    # 采集日期 YYYY-MM-DD
---
```

**交付物**（`deliverables/**`）：

```yaml
---
title: <标题>
status: draft           # draft | review | final | published
destination: local      # feishu | local | web
sources:                # 溯源回链：用到的来源文件路径
  - sources/feishu/<租户>/dm/2026-06-14_xxx.md
created: 2026-06-14
published_url:          # 仅 web/已发布时填写
---
```

文件命名统一 `YYYY-MM-DD_<slug>.md`（飞书文档、知识库笔记等"无明确日期"的可用主题 slug）。

## 5. sources/ — 来源约定要点

- **飞书是租户优先**：`sources/feishu/<租户>/{dm,groups,docs}/`。先按租户隔离，再分单聊/群聊/文档。
- **外部 Agent 写入契约**（例如接到飞书里的 Codex）：
  - 落盘路径：`sources/feishu/<租户>/<dm|groups|docs>/`
  - 文件名：`YYYY-MM-DD_<slug>.md`
  - 必须带 §4 的来源 frontmatter
  - 这份契约在根目录 `AGENTS.md` 里也有一份，便于非 Claude 的 Agent 读到同样的规则。
- 其余来源（wechat / mp / social / knowledge）单层即可，元数据靠 frontmatter 区分。详见各自 `README.md`。

## 6. deliverables/ — 交付物去向

| 去向 | 目录 | 怎么落地 |
| --- | --- | --- |
| 飞书文档 | `deliverables/feishu/` | 本地写好 Markdown，再通过你的飞书集成/外部 Agent 回写到飞书（本仓库不含飞书本地工具） |
| 本地文档 | `deliverables/local/` | 终稿直接存这里，即最终产物 |
| 线上 HTML | `deliverables/web/` | 产出**自包含**的 HTML，再发布到你自选的静态托管 |

**Web 发布（采用者自配）：** 本模板不绑定任何托管账号。选一个静态托管（Vercel / Netlify / Cloudflare Pages / GitHub Pages / 对象存储 COS·OSS·S3 / 或 rsync 到自己的服务器），把你的**发布命令**填到下面这一行，之后 Agent 就照此发布：

```
# TODO(adopter): 在此填写你的发布命令，例如
#   vercel deploy deliverables/web/<name> --prod
#   或  rsync -av deliverables/web/<name>/ user@host:/var/www/<name>/
发布命令：<未配置>
```

发布成功后，把可访问链接回填到该交付物 frontmatter 的 `published_url`。

## 7. 常用操作（非代码）

- **拉取来源**：`scripts/pull-all.sh`（或 `pull-feishu`/`pull-getnote`/`pull-wechat`）把已脚本化来源拉进 `sources/`（见 §8、`pull-sources` 技能）。公众号和小宇宙目前走链接/RSS/导出归档规则。
- **归档 inbox**：读 `sources/inbox/` 里的新文件 → 判断来源 → 移动到对应来源目录 → 补 frontmatter。
- **起草交付物**：依据 `sources:` 选定的底稿，在 `workstreams/<主题>/` 里打草稿；定稿移到 `deliverables/<去向>/`。
- **配图**：用内置 `ai-image` 技能（`scripts/generate-image.py`）为交付物生成插图，存到 `assets/` 再引用（需配置 key，见 §8）。
- **回写飞书 / 发布 web**：飞书用 `feishu-cli` 回写并回填 `published_url`；web 见 §6 用你自配的发布命令。

## 8. 内置技能与脚本（三 Agent 同源 · 带版本 · 可分发）

**三 Agent 同源**：实现的真正逻辑在 `scripts/` 与各 skill 自带的 `scripts/`；三个 Agent 都**调同一批脚本**，不分叉——
- **Claude** 读 `.claude/skills/`（自动发现，标准 Agent Skill 格式）；
- **Codex** 读根 `AGENTS.md`；
- **腾讯 CodeBuddy** 在没有 `CODEBUDDY.md` 时**自动加载 `AGENTS.md`**（故无需重复维护），skill 可经 `skills/install.sh --codebuddy` 镜像到 `.codebuddy/skills/`。

每个 `SKILL.md` 的 frontmatter 带 `version`（语义化版本）。两个**交互式按需**技能（`wechat-exporter` 公众号、`xiaoyuzhou` 小宇宙）需扫码登录，不纳入每日 `pull-all`。**均不含任何密钥/账号**，采用者自带凭证（统一放仓库根 `.env.local`，见 `.env.example`）。

| 技能 | 实现脚本 | 采用者需配置 |
| --- | --- | --- |
| `setup`（首次引导/体检） | `scripts/setup.sh`（status/init/doctor/set） | 无；带你勾选并打通各集成 |
| `pull-sources` | `scripts/pull-all.sh` | 见下各来源（`PULL_SOURCES` 可纳入新源） |
| `feishu-cli`（飞书·多租户） | `scripts/pull-feishu.sh` + `lark-cli` + `feishu-add-tenant.sh` | `npm i -g @larksuite/cli`；每租户 `scripts/feishu-add-tenant.sh <名>`；`FEISHU_TENANTS` |
| `dingtalk`（钉钉·通讯录/文档） | 技能内 `pull-dingtalk.sh` + `dingtalk_client.py`（仅标准库） | `DINGTALK_APP_KEY` / `DINGTALK_APP_SECRET`；管理员授读权限（**无聊天记录 API**） |
| `tencent-meeting`（腾讯会议·录制/纪要/转写） | 技能内 `pull-tencent-meeting.sh` + `tmeeting_client.py`（标准库） | 企业版自建应用 AKSK：`TENCENT_MEETING_*`（APP_ID/SDK_ID/SECRET_ID/SECRET_KEY/OPERATOR_ID） |
| `get-biji`（得到/Get笔记） | `scripts/pull-getnote.sh` + `scripts/lib/get_biji.py` | `GET_BIJI_API_KEY` / `GET_BIJI_CLIENT_ID`（可选 `GET_BIJI_DEFAULT_TOPIC_ID`） |
| `wechat-chatlog`（微信聊天） | `scripts/pull-wechat.sh` + `chatlog` | 装 `chatlog`，跑 `chatlog server` |
| `wechat-exporter`（微信公众号·扫码） | 技能内 `scripts/`（登录公众平台）→ `sources/mp/` | `pip install requests openpyxl`；交互式 |
| `xiaoyuzhou`（小宇宙播客·扫码） | 技能内 `xiaoyuzhou.py`（登录）→ `sources/social/` | `pip install requests qrcode pillow`；`XIAOYUZHOU_OUTPUT_DIR` |
| `blog`（博客/RSS） | 技能内 `pull-blog.sh` + `blog_client.py`（标准库可跑） | `BLOG_FEEDS`（无需凭证；可选 `pip install feedparser trafilatura markdownify`） |
| `ai-image` | `scripts/generate-image.py` | `AIPROXY_API_KEY` / `AIPROXY_BASE_URL` |

**多租户**：飞书走 `lark-cli profile` + `FEISHU_TENANTS`（每租户一个 profile）；其它"凭证在 .env"的来源（钉钉/腾讯会议/得到/生图）把另一套写到 `.env.<租户>.local`，运行时 `TENANT=<租户> <脚本>` 在默认 `.env.local` 之上叠加。

**版本与分发**：`skills/registry.json` 是清单，`skills/install.sh` 是一行安装器——在任意目标仓库
`curl -fsSL https://raw.githubusercontent.com/WilsonLiu95/workspace-of-super-hero/main/skills/install.sh | bash -s -- install <skill>[@版本] [--codex --codebuddy]`。
版本按 `<skill>-v<版本>` 的 git tag 冻结；不带 `@版本` 拉 main 最新。维护/发布流程见 `skills/README.md`。

**首次配置**：新机器导入后 → `bash scripts/setup.sh doctor` 体检，或在 Agent 里说「帮我配置工作区」走 `setup` 引导（勾选集成→逐项填 `.env.local`→体检）。

**定时**：把 `scripts/pull-all.sh` 挂到 Codex `automation.toml` / Claude `/schedule` / 本地 `cron`，示例见 `scripts/README.md`。当前未绑定触发器。

## 9. 让它成为你的（Make it yours）

本仓库是**可分享的模板**。采用后按此清单改造：

1. 删除所有示例：`_example-*`（包括 `sources/feishu/_example-tenant/`、各 `_example-*.md`、`deliverables/**/_example-*`、`workstreams/_example-workstream/`）。
2. 在 `sources/feishu/` 下按你的真实**租户**建目录。
3. 接入你自己的数据源/外部 Agent（飞书 Codex、导出脚本等），让它们按 §5 契约写入。
4. 配置 §6 的 **Web 发布命令**。
5. `cp .env.example .env.local` 填入各来源凭证（§8）；飞书另需 `lark-cli auth login`、微信另需 `chatlog server`。
6. 如需每日自动拉取，把 `scripts/pull-all.sh` 挂到定时器（见 `scripts/README.md`）。

## 10. 敏感与隐私（重要）

- `sources/` 含**私密聊天/文档**。本模板的 `.gitignore` **默认忽略 `sources/` 下的真实数据**（只跟踪目录结构、README 和 `_example-*` 示例），避免你误把隐私提交进 git。
- 如确需版本化真实来源数据：自行放开 `.gitignore`，且**远端仓库必须设为私有**。
- 未经明确意图，**不要**把原始来源内容贴给外部服务/公开链接。发布 web 交付物前确认其中不含私密信息。

## 11. 环境能力（因人而异）

- **随模板自带（见 §8）**：`setup` / `pull-sources` / `feishu-cli` / `dingtalk` / `tencent-meeting` / `get-biji` / `wechat-chatlog` / `wechat-exporter` / `xiaoyuzhou` / `blog` / `ai-image` 十一个技能 + `scripts/` + `skills/`（清单与一行安装器），随仓库分享，三 Agent（Claude/Codex/CodeBuddy）通用。但都需采用者**自带凭证/工具**（飞书/钉钉/腾讯会议应用、Biji key、chatlog、公众号/小宇宙扫码登录、生图 key；博客无需凭证）才能真正调用。
- **不随模板、需你环境另配**：特定静态托管账号（CloudBase/Vercel/…）、`chatlog`/`lark-cli`/CodeBuddy CLI 等二进制的安装。用之前先确认在你的环境可用；不可用就走手动/导出路径。
- **首次导入**：先跑 `bash scripts/setup.sh doctor` 看缺什么，或在 Agent 里说「帮我配置工作区」走 `setup` 引导。
