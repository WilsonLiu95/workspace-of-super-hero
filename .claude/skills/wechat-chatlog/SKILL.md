---
name: wechat-chatlog
description: 把微信聊天记录拉进 sources/wechat/，用 chatlog（本地 HTTP 服务暴露微信记录，微信无官方 API）。触发场景：「拉微信聊天」「同步微信记录」「把微信某人/某群的对话存下来」「chatlog」。实现是共享脚本 scripts/pull-wechat.sh。需先按 chatlog 文档完成 key/decrypt 并运行 chatlog server。
---

# 微信 (chatlog)

微信没有官方 API。用 [`chatlog`](https://github.com/sjzar/chatlog) 在本地解密并通过 HTTP 服务暴露聊天记录，本工作区据此归档到 `sources/wechat/`。

## 前置（一次性，按 chatlog 文档）

1. 保持微信在本机登录。
2. `chatlog key` / `chatlog decrypt` 获取并解密数据库。
3. `chatlog server` 启动本地 HTTP 服务（默认 `http://127.0.0.1:5030`）。

## 归档

```bash
scripts/pull-wechat.sh        # 读 .env.local → 查 chatlog HTTP API → 写 sources/wechat/<date>_<会话>.md
```

环境变量（在 `.env.local`）：`CHATLOG_BASE_URL`（默认 `http://127.0.0.1:5030`）、`WECHAT_SINCE_DAYS`（默认 1）、`WECHAT_MAX_SESSIONS`（默认 50）。

## 注意

- 连不上服务 → 脚本会提示先跑 `chatlog server`。
- 微信记录高度私密：落在 `sources/`（默认不进 git，见根 `.gitignore`），不要外泄。
- chatlog 的 HTTP API 字段/路径以其当前版本为准；`scripts/pull-wechat.sh` 做了防御式解析，若字段对不上按脚本注释微调。
- 该脚本只调本地 HTTP API、不含任何凭证，可被 Codex / 定时器复用。

> 区分：「微信读书」笔记是另一个来源（你另有 weread 工具），不在此技能范围。
