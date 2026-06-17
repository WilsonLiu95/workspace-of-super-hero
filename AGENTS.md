# AGENTS.md

本文件供 **Codex、腾讯 WorkBuddy 及其它非 Claude Agent** 读取——Codex 把 AGENTS.md 作为项目入口；
**WorkBuddy 在没有 `WORKBUDDY.md` 时会自动加载本文件**（所以无需再维护一份重复的契约）。
Skill 真源统一在根 `skills/`；Claude 的 `.claude/skills` 与 Codex 的 `.agents/skills` 都是指向 `../skills` 的软链接。
它们共同调用**同一套实现**（`scripts/` 与各 skill 自带脚本）——实现单一、不分叉。
完整工作区约定见 [`CLAUDE.md`](./CLAUDE.md)。

> **交流语言：中文。** 与用户对话、进度说明、总结、解释一律用中文；代码、命令、路径、frontmatter 字段名等技术性内容保持原样。

## 这是什么

个人 Co-Worker 工作空间，不是代码仓库。数据流：
`sources/`（原始数据，按来源分类）→ 加工 → `deliverables/`（飞书文档 / 本地文档 / 线上 HTML）。

## 能力都在 scripts/（你直接跑）

| 你要做的事 | 跑这个 | 说明 |
| --- | --- | --- |
| 拉飞书会话/消息 | `scripts/pull-feishu.sh` | 需 `lark-cli` 已登录 |
| 拉得到/Get笔记 | `scripts/pull-getnote.sh` | Biji OpenAPI |
| 拉微信 | `scripts/pull-wechat.sh` | 暂停默认配置；需要时手动恢复，需 `chatlog server` |
| 一键拉全部 | `scripts/pull-all.sh` | 编排器，供定时器调用 |
| 生成图片 | `python3 scripts/generate-image.py "<prompt>" -o assets` | OpenAI 兼容生图 |
| 导出公众号文章 | `skills/wechat-exporter/scripts/`（扫码）→ `sources/mp/` | 交互式，需用户扫码 |
| 拉小宇宙播客 | `skills/xiaoyuzhou/xiaoyuzhou.py`（扫码）→ `sources/social/` | 交互式，需用户扫码 |
| 拉钉钉通讯录/文档 | `skills/dingtalk/scripts/pull-dingtalk.sh` | 自建企业内部应用；钉钉**无聊天记录 API** |
| 拉腾讯会议录制/纪要/逐字稿（个人版） | `skills/tencent-meeting/scripts/pull-tencent-meeting.sh`（官方 `tmeet` CLI，OAuth） | 先 `tmeet auth login` 扫码登录；零密钥 |
| 拉博客/RSS | `skills/blog/scripts/pull-blog.sh` | 无需凭证；配 `BLOG_FEEDS` |
| 托管网页到云电脑 | `skills/cloud-computer/scripts/cloud-computer.sh --dry-run deploy-static <目录> <域名>` | 需 SSH；云电脑需 Docker/Compose；DNS 用户自配 |
| 首次配置 / 体检 | `bash scripts/setup.sh wizard`（或 `doctor`/`init`/`status`/`set KEY VALUE`） | 一键引导打通各集成 |
| 装/更新 skill | `skills/install.sh install <name>[@版本]` | 从 Git 仓库一行装，版本按 git tag |
| 检查 skill 同步 | `skills/install.sh check-sync` | 校验软链接、registry、frontmatter 版本 |

每个能力的详细说明（前置/参数/排错）见对应 `skills/<name>/SKILL.md`——
那是标准 Agent Skill 格式（`name`+`description`+正文），你可以直接读：
`feishu-cli` / `dingtalk` / `tencent-meeting` / `get-biji` / `wechat-chatlog` / `wechat-exporter` / `xiaoyuzhou` / `blog` / `ai-image` / `cloud-computer` / `pull-sources` / `setup`。

> 微信 chatlog 暂不纳入默认配置/定时；需要恢复时手动设 `PULL_SOURCES` 加 `wechat`。
> 公众号/小宇宙是**交互式扫码**技能：生成二维码 → 展示给用户 → 等用户扫码确认 → 再继续。
> 不要塞进无人值守的定时任务。

## 凭证

统一放仓库根 `.env.local`（见 `.env.example`，已被 `.gitignore` 忽略）。`scripts/*` 与各 skill 脚本会自动 `source` 它。
飞书凭证由 `lark-cli` 自管（`~/.lark-cli`）。**不要把任何 key 写进仓库。**

- **多租户**：飞书用 `lark-cli profile` + `.env.local` 里的 `FEISHU_TENANTS`（每租户一个 profile，`scripts/feishu-add-tenant.sh <名>` 加）；其它"凭证写在 .env"的来源（钉钉/腾讯会议/得到/生图/云电脑）把另一套写到 `.env.<租户>.local`，运行时 `TENANT=<租户> <脚本>` 叠加。
- **首次配置**：`bash scripts/setup.sh wizard` 一键引导（初始化→体检→缺项指引→可交互写 `.env.local`）；`doctor` 只体检，`init` 只建 `.env.local`，`set KEY VALUE` 只落盘单项。

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
