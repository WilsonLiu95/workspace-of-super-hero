# Co-Worker 工作空间（模板）

一个**个人协作工作空间**模板：把多来源的原始资料归档进来，让 AI Agent（Claude Code / Codex 等）帮你整理、合成、产出交付物。**这不是一个写代码的项目**——没有 build/test，"工作"指的是收资料、做研究、写东西、配图、发布。

## 心智模型

```
sources/  ──加工──▶  deliverables/
原始数据             交付物（飞书文档 / 本地文档 / 线上 HTML）
   ▲                     │
   └──── workstreams/ ◀──┘   (进行中的草稿/合成)
```

## 目录

- **`sources/`** — 原始数据，按来源分类：`feishu/`（多租户单聊·群聊·文档）、`getnote/`（得到/Get笔记）、`wechat/`、`mp/`（公众号）、`social/`、`knowledge/`、`inbox/`（临时中转）。只读为主。
- **`deliverables/`** — 产出：`feishu/`（回写飞书）、`local/`（本地终稿）、`web/`（线上 HTML）。
- **`workstreams/`** — 进行中的主题工作台。
- **`assets/`** — 图片等素材。
- **`scripts/`** — 自动化脚本（拉取各来源、生图），Claude / Codex / 定时器同源复用。

## 双 Agent

`scripts/` 是单一实现层。Claude 读 `.claude/skills/`，Codex 读 [`AGENTS.md`](./AGENTS.md)，定时器调 `scripts/pull-all.sh`——三方调用同一批脚本，不分叉。

## 怎么用

1. 读 [`CLAUDE.md`](./CLAUDE.md) —— 给 AI Agent 看的完整约定（来源/交付物的 frontmatter、外部 Agent 写入契约、发布流程等）。
2. 把资料放进 `sources/` 对应来源目录，或接一个外部 Agent 自动写入（契约见 [`AGENTS.md`](./AGENTS.md)）。
3. 让 Agent 基于这些来源产出交付物到 `deliverables/`。

## 采用本模板（Make it yours）

- 删掉所有 `_example-*` 示例。
- 在 `sources/feishu/` 下建你自己的真实租户目录。
- 配置 `CLAUDE.md` §6 的 Web 发布命令（本模板不绑定任何托管账号）。
- 留意隐私：`.gitignore` 默认**不跟踪** `sources/` 里的真实数据，只跟踪结构与示例。
