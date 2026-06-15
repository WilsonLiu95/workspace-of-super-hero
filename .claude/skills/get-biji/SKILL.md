---
name: get-biji
description: 拉取/查询「得到 / Get笔记 / Biji」笔记与知识库，并归档进 sources/getnote/。触发场景：「拉得到笔记」「同步 Get笔记」「查我的笔记/知识库」「回忆某条笔记」「基于得到笔记回答」「Biji」。实现是共享脚本 scripts/lib/get_biji.py（Biji OpenAPI 客户端）与 scripts/pull-getnote.sh。需 GET_BIJI_API_KEY（notes list 还需 GET_BIJI_CLIENT_ID，知识库可选 GET_BIJI_DEFAULT_TOPIC_ID）。
version: 0.1.0
updated: "2026-06-15"
---

# Get笔记 / 得到 / Biji

用 Biji OpenAPI 处理得到笔记：列笔记、知识库语义搜索、召回原文，并能批量归档进本工作区。

> 凭证统一走仓库根 `.env.local`（见 `.env.example`，已被 `.gitignore` 忽略）：
> `GET_BIJI_API_KEY` 必需；`notes list` 还需 `GET_BIJI_CLIENT_ID`；知识库接口可选 `GET_BIJI_DEFAULT_TOPIC_ID`。

## 两类用法

**A. 批量归档（自动化）** —— 拉笔记落到 `sources/getnote/`，供后续合成：

```bash
scripts/pull-getnote.sh            # 读 .env.local → 写 sources/getnote/<date>_<id>_<title>.md（带 frontmatter）
```

**B. 即时查询（交互）** —— 直接调客户端，按需回答：

```bash
# 列出笔记
python3 scripts/lib/get_biji.py notes list --since-id 0

# 知识库语义搜索（回答"我记过关于 X 的想法吗"）
python3 scripts/lib/get_biji.py knowledge search --question "用户分层" --topic-id "$GET_BIJI_DEFAULT_TOPIC_ID" --deep-seek

# 召回原始片段
python3 scripts/lib/get_biji.py knowledge recall --question "用户分层" --topic-id "$GET_BIJI_DEFAULT_TOPIC_ID" --top-k 3
```

## 结果处理

- 默认输出格式化 JSON；回答用户时先提炼结论，别倾倒整段 JSON。
- 401/403 → 优先检查 `GET_BIJI_API_KEY` / `GET_BIJI_CLIENT_ID`。
- 缺 `topic_id` → 用 `GET_BIJI_DEFAULT_TOPIC_ID`；还没有就告诉用户缺知识库 ID。

> 说明：`scripts/lib/get_biji.py` 只从环境变量读凭证，可直接被 Codex / 定时器复用。
