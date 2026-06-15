# Workspace of Super Hero

一个给**超级个体**使用的个人 Co-Worker 工作空间模板：把多来源的原始资料归档进来，让 AI Agent（Claude Code / Codex / 腾讯 CodeBuddy 等）帮你整理、合成、产出交付物。**这不是一个写代码的项目**——没有 build/test，"工作"指的是收资料、做研究、写东西、配图、发布。

## 心智模型

```
sources/  ──加工──▶  deliverables/
原始数据             交付物（飞书文档 / 本地文档 / 线上 HTML）
   ▲                     │
   └──── workstreams/ ◀──┘   (进行中的草稿/合成)
```

## 目录

- **`sources/`** — 原始数据，按来源分类：`feishu/`（多租户单聊·群聊·文档）、`dingtalk/`（钉钉通讯录/文档）、`tencent-meeting/`（腾讯会议录制/纪要/转写）、`getnote/`（得到/Get笔记）、`wechat/`、`mp/`（公众号）、`social/`（含小宇宙等社媒/播客）、`blog/`（博客/RSS）、`knowledge/`、`inbox/`（临时中转）。只读为主。
- **`deliverables/`** — 产出：`feishu/`（回写飞书）、`local/`（本地终稿）、`web/`（线上 HTML）。
- **`workstreams/`** — 进行中的主题工作台。
- **`assets/`** — 图片等素材。
- **`scripts/`** — 自动化脚本（拉取各来源、生图、首次引导），三 Agent / 定时器同源复用。
- **`skills/`** — Skill 分发中枢：`registry.json` 清单 + `install.sh` 一行安装器（带版本）。

## 三 Agent 同源

`scripts/` 与各 skill 自带脚本是单一实现层。**Claude** 读 `.claude/skills/`，**Codex** 读 [`AGENTS.md`](./AGENTS.md)，**腾讯 CodeBuddy** 无 `CODEBUDDY.md` 时自动读 `AGENTS.md`（skill 可 `--codebuddy` 镜像到 `.codebuddy/skills/`），定时器调 `scripts/pull-all.sh`——都调同一批脚本，不分叉。

## 怎么用

1. **首次配置**：`bash scripts/setup.sh doctor` 体检，或在 Agent 里说「**帮我配置工作区**」走引导（勾选要打通的集成→逐项填 `.env.local`→体检）。
2. 读 [`CLAUDE.md`](./CLAUDE.md) —— 给 AI Agent 看的完整约定（frontmatter、写入契约、版本/分发、发布流程等）。
3. 把资料放进 `sources/` 对应来源目录，或让对应 skill 自动拉取（飞书/钉钉/腾讯会议/公众号/小宇宙/博客/得到）。
4. 让 Agent 基于这些来源产出交付物到 `deliverables/`。

## 装 / 更新一个 Skill（一行）

```bash
# 在任意目标仓库根目录
curl -fsSL https://raw.githubusercontent.com/WilsonLiu95/workspace-of-super-hero/main/skills/install.sh | bash -s -- install dingtalk
# 看清单 / 装指定版本 / 同时给 Codex+CodeBuddy
curl -fsSL .../skills/install.sh | bash -s -- list
curl -fsSL .../skills/install.sh | bash -s -- install tencent-meeting@0.1.0 --codex --codebuddy
```

维护与发版（打 `<skill>-v<版本>` tag）见 [`skills/README.md`](./skills/README.md)。

## 采用本模板（Make it yours）

- `cp .env.example .env.local`，或直接 `bash scripts/setup.sh init && bash scripts/setup.sh doctor` 起步。
- 删掉所有 `_example-*` 示例。
- 在 `sources/feishu/` 下建你自己的真实租户目录（`scripts/feishu-add-tenant.sh <名>`）。
- 配置 `CLAUDE.md` §6 的 Web 发布命令（本模板不绑定任何托管账号）。
- 留意隐私：`.gitignore` 默认**不跟踪** `sources/` 里的真实数据（也忽略 `.env.local` / `.env.*.local` / `.codebuddy/`），只跟踪结构与示例。
