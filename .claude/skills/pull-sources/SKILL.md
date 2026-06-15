---
name: pull-sources
description: 一键把各来源（飞书 / 得到Get笔记 / 微信）的最新内容拉回 sources/。触发场景：「拉一下所有来源」「同步今天的飞书和笔记」「更新原始数据」「跑一下 pull-all」「把数据拉回来」。实现是编排脚本 scripts/pull-all.sh，逐个调用 pull-feishu / pull-getnote / pull-wechat。
version: 0.1.0
updated: "2026-06-15"
---

# 拉取来源（编排）

把各来源最新内容拉进 `sources/`，供后续合成。单个来源失败不影响其它来源。

```bash
scripts/pull-all.sh                          # 拉全部
PULL_SOURCES="feishu getnote" scripts/pull-all.sh   # 只拉指定来源
scripts/pull-getnote.sh                      # 或单独跑某个
```

- 凭证来自仓库根 `.env.local`（见 `.env.example`）；脚本会自动 `source`。
- 各来源前置/工具见对应技能：`feishu-cli` / `get-biji` / `wechat-chatlog`。
- 拉完通常接「归档整理」：把 `sources/inbox/` 或新拉内容补全 frontmatter、归到正确目录（见 `sources/*/README.md`）。

## 定时跑

本身可直接被定时器调用（当前未绑定触发器）。三种挂法见 [`scripts/README.md`](../../../scripts/README.md) 的「定时触发」：Codex `automation.toml` / Claude `/schedule` / 本地 `cron`。

> 实现单一：本技能、Codex（`AGENTS.md`）、定时器都调同一个 `scripts/pull-all.sh`。
