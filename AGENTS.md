# AGENTS.md

本文件供 **Codex、腾讯 CodeBuddy 及其它非 Claude Agent** 读取——Codex 把 AGENTS.md 作为项目入口；
**CodeBuddy 在没有 `CODEBUDDY.md` 时会自动加载本文件**（所以无需再维护一份重复的契约）。
它和 Claude 的 `.claude/skills/` 指向**同一套实现**（`scripts/` 与各 skill 自带脚本）——实现单一、不分叉。
完整工作区约定见 [`CLAUDE.md`](./CLAUDE.md)。

## 这是什么

个人 Co-Worker 工作空间，不是代码仓库。数据流：
`sources/`（原始数据，按来源分类）→ 加工 → `deliverables/`（飞书文档 / 本地文档 / 线上 HTML）。

## 能力都在 scripts/（你直接跑）

| 你要做的事 | 跑这个 | 说明 |
| --- | --- | --- |
| 拉飞书会话/消息 | `scripts/pull-feishu.sh` | 需 `lark-cli` 已登录 |
| 拉得到/Get笔记 | `scripts/pull-getnote.sh` | Biji OpenAPI |
| 拉微信 | `scripts/pull-wechat.sh` | 需 `chatlog server` 在跑 |
| 一键拉全部 | `scripts/pull-all.sh` | 编排器，供定时器调用 |
| 生成图片 | `python3 scripts/generate-image.py "<prompt>" -o assets` | OpenAI 兼容生图 |
| 导出公众号文章 | `.claude/skills/wechat-exporter/scripts/`（扫码）→ `sources/mp/` | 交互式，需用户扫码 |
| 拉小宇宙播客 | `.claude/skills/xiaoyuzhou/xiaoyuzhou.py`（扫码）→ `sources/social/` | 交互式，需用户扫码 |
| 拉钉钉通讯录/文档 | `.claude/skills/dingtalk/scripts/pull-dingtalk.sh` | 自建企业内部应用；钉钉**无聊天记录 API** |
| 拉腾讯会议录制/纪要/转写 | `.claude/skills/tencent-meeting/scripts/pull-tencent-meeting.sh` | 企业版/商业版 AKSK |
| 拉博客/RSS | `.claude/skills/blog/scripts/pull-blog.sh` | 无需凭证；配 `BLOG_FEEDS` |
| 首次配置 / 体检 | `bash scripts/setup.sh doctor`（或 `init`/`status`/`set KEY VALUE`） | 引导打通各集成 |
| 装/更新 skill | `skills/install.sh install <name>[@版本]` | 从 Git 仓库一行装，版本按 git tag |

每个能力的详细说明（前置/参数/排错）见对应 `.claude/skills/<name>/SKILL.md`——
那是标准 Agent Skill 格式（`name`+`description`+正文），你可以直接读：
`feishu-cli` / `dingtalk` / `tencent-meeting` / `get-biji` / `wechat-chatlog` / `wechat-exporter` / `xiaoyuzhou` / `blog` / `ai-image` / `pull-sources` / `setup`。

> 公众号/小宇宙是**交互式扫码**技能：生成二维码 → 展示给用户 → 等用户扫码确认 → 再继续。
> 不要塞进无人值守的定时任务。

## 凭证

统一放仓库根 `.env.local`（见 `.env.example`，已被 `.gitignore` 忽略）。`scripts/*` 与各 skill 脚本会自动 `source` 它。
飞书凭证由 `lark-cli` 自管（`~/.lark-cli`）。**不要把任何 key 写进仓库。**

- **多租户**：飞书用 `lark-cli profile` + `.env.local` 里的 `FEISHU_TENANTS`（每租户一个 profile，`scripts/feishu-add-tenant.sh <名>` 加）；其它"凭证写在 .env"的来源（钉钉/腾讯会议/得到/生图）把另一套写到 `.env.<租户>.local`，运行时 `TENANT=<租户> <脚本>` 叠加。
- **首次配置**：`bash scripts/setup.sh doctor` 体检各集成，`init` 建 `.env.local`，`set KEY VALUE` 落盘。

## 你把拉来的数据写到哪（写入契约）

写入 `sources/`，**按来源分类**，只追加不改写：

| 来源 | 路径 |
| --- | --- |
| 飞书（多租户） | `sources/feishu/<租户>/<dm\|groups\|docs>/` |
| 钉钉（多租户，通讯录/文档；无聊天） | `sources/dingtalk/<租户>/<contacts\|docs>/` |
| 腾讯会议（录制/纪要/转写） | `sources/tencent-meeting/` |
| 得到/Get笔记 | `sources/getnote/` |
| 微信 | `sources/wechat/` |
| 公众号 / 其它社媒 / 博客 / 知识库 | `sources/{mp,social,blog,knowledge}/` |
| 不确定/临时 | `sources/inbox/`（之后归档） |

命名 `YYYY-MM-DD_<slug>.md`，并带 frontmatter：

```yaml
---
source: feishu          # feishu | dingtalk | tencent-meeting | getnote | wechat | mp | social | blog | knowledge | inbox
tenant: <租户名>         # 多租户来源（飞书/钉钉）必填
channel: <会话/群/作者>
type: dm                # dm | group | doc | note | article | contacts | meeting
captured: 2026-06-14
---
```

## 定时

`scripts/pull-all.sh` 可挂到 Codex `automation.toml`（cron 风格）、Claude `/schedule` 或本地 `cron`。
示例与 rrule 见 [`scripts/README.md`](./scripts/README.md) 的「定时触发」。当前未绑定任何触发器。

## 红线

- 只追加，不改写/删除 `sources/` 已有原始文件；不要碰 `deliverables/`（产出区）。
- `sources/` 含私密数据（默认不进 git）；不要外泄。
- 写操作（发飞书消息、建/改文档）前先 `--dry-run`。
