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

- **`sources/`** 装各种来源的**原始数据**：飞书（多租户的单聊/群聊/文档）、微信、公众号、其他社媒、个人知识库，以及临时丢东西的 `inbox/`。这些可能由你手动放入，也可能由**外部 Agent 主动写入**（例如一个接到飞书里的 Codex/机器人）。
- **`deliverables/`** 装你/Agent **产出的成果**：要回写飞书的文档、本地终稿、要发布到线上的 HTML。
- **`workstreams/`** 是**进行中的工作台**：某个主题/任务的草稿、提纲、合成中间产物，定稿后再落到 `deliverables/`。
- **`assets/`** 存图片等**素材**，被交付物引用。

## 2. 顶层结构

| 目录 | 用途 | 读写 |
| --- | --- | --- |
| `sources/` | 原始数据，按来源分类 | **只读为主 / 仅追加**，勿改写删除 |
| `deliverables/` | 交付物（feishu / local / web） | 产出区 |
| `workstreams/` | 进行中的主题工作台 | 草稿区 |
| `assets/` | 图片等素材 | 按需 |

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
source: feishu          # feishu | wechat | mp | social | knowledge | inbox
tenant: <租户名>         # 仅 feishu 等多租户来源需要；其余可省略
channel: <会话/群/作者>  # 单聊对象、群名、公众号名、作者等
type: dm                # dm | group | doc | article | note
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

- **归档 inbox**：读 `sources/inbox/` 里的新文件 → 判断来源 → 移动到对应来源目录 → 补 frontmatter。
- **起草交付物**：依据 `sources:` 选定的底稿，在 `workstreams/<主题>/` 里打草稿；定稿移到 `deliverables/<去向>/`。
- **配图（可选）**：若你的环境配置了生图技能/工具，可用它为交付物生成插图，存到 `assets/`，在文档里引用。**本模板不假设它存在。**
- **发布 web**：见 §6，用你自配的发布命令。

## 8. 让它成为你的（Make it yours）

本仓库是**可分享的模板**。采用后按此清单改造：

1. 删除所有示例：`_example-*`（包括 `sources/feishu/_example-tenant/`、各 `_example-*.md`、`deliverables/**/_example-*`、`workstreams/_example-workstream/`）。
2. 在 `sources/feishu/` 下按你的真实**租户**建目录。
3. 接入你自己的数据源/外部 Agent（飞书 Codex、导出脚本等），让它们按 §5 契约写入。
4. 配置 §6 的 **Web 发布命令**。
5. 如有需要，把你环境里的技能/连接器（生图、飞书/微信 MCP 等）记到这里。

## 9. 敏感与隐私（重要）

- `sources/` 含**私密聊天/文档**。本模板的 `.gitignore` **默认忽略 `sources/` 下的真实数据**（只跟踪目录结构、README 和 `_example-*` 示例），避免你误把隐私提交进 git。
- 如确需版本化真实来源数据：自行放开 `.gitignore`，且**远端仓库必须设为私有**。
- 未经明确意图，**不要**把原始来源内容贴给外部服务/公开链接。发布 web 交付物前确认其中不含私密信息。

## 10. 环境能力（因人而异，不保证存在）

下列能力取决于**采用者各自的环境**，本模板不内置、不假设：飞书/Lark 或微信的连接器/MCP、生图技能、特定静态托管账号。用之前先确认它在你的环境里可用；不可用就走手动/导出路径。
