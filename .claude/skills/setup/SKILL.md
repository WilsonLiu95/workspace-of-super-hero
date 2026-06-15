---
name: setup
description: 首次使用本工作区的「引导配置 / 体检」向导。触发场景：「帮我配置工作区」「第一次用这个仓库」「初始化」「配置集成/数据源」「打通飞书/钉钉/腾讯会议/公众号/小宇宙/博客/得到/生图」「检查我配好了没」「体检」「setup」「onboarding」「doctor」。带着用户勾选要打通的集成、逐项拿到凭证写进 .env.local、再体检每个集成是否就绪——目标是把"第一次导入这个仓库"的实施成本降到最低。
version: 0.1.0
updated: "2026-06-15"
---

# 首次配置向导（onboarding）

帮第一次用这个工作区的人，把要用的集成一个个打通。实现是 `scripts/setup.sh`（status / init / doctor / set），你（Agent）负责对话引导、拿凭证、调脚本落盘。

> **安全红线**：凭证只通过 `scripts/setup.sh set KEY VALUE` 写进 `.env.local`（已被 .gitignore 忽略）。
> 拿到 secret 后**不要**回显、不要写进任何会进 git 的文件、不要贴给外部服务。绝不 `git add .env.local`。

## 流程

### 1. 探测 + 初始化

```bash
bash scripts/setup.sh status     # 看是不是首次（有没有 .env.local、装了几个 skill）
bash scripts/setup.sh init       # 若无 .env.local，从 .env.example 生成一份（不覆盖已有）
```

### 2. 勾选要打通哪些集成

把下面这张清单给用户，问他**这次想配哪些**（可多选、可跳过、以后随时再来）。逐一确认，不要一次性逼问所有。

| 集成 | skill | 需要什么 | 凭证去哪拿 |
| --- | --- | --- | --- |
| 飞书（多租户） | `feishu-cli` | lark-cli + 每租户登录 | `npm i -g @larksuite/cli`，再 `scripts/feishu-add-tenant.sh <租户名>` |
| 钉钉（通讯录/文档） | `dingtalk` | `DINGTALK_APP_KEY` `DINGTALK_APP_SECRET` | 钉钉开放平台→企业内部应用；管理员授通讯录/文档读权限 |
| 腾讯会议（录制/纪要/转写） | `tencent-meeting` | `TENCENT_MEETING_APP_ID/SDK_ID/SECRET_ID/SECRET_KEY` + `OPERATOR_ID` | 用户中心→企业管理→高级→REST API（需企业版/商业版） |
| 得到 / Get笔记 | `get-biji` | `GET_BIJI_API_KEY`（+ `GET_BIJI_CLIENT_ID`） | Biji 开放平台 |
| 微信聊天 | `wechat-chatlog` | 本地 `chatlog` 服务 | 装 chatlog → `chatlog key/decrypt` → `chatlog server` |
| 公众号文章 | `wechat-exporter` | 运行时扫码登录 | 无 key，`pip install requests openpyxl` |
| 小宇宙播客 | `xiaoyuzhou` | 运行时扫码登录 | 无 key，凭据存 ~/.xiaoyuzhou/ |
| 博客 / RSS | `blog` | `BLOG_FEEDS`（feed/主页 URL） | 无凭证；可选 `pip install feedparser trafilatura markdownify` |
| AI 生图 | `ai-image` | `AIPROXY_API_KEY` `AIPROXY_BASE_URL` | 你的 aiproxy / OpenAI 兼容服务 |

### 3. 逐项配置（拿到值就落盘）

- **凭证型（钉钉/腾讯会议/得到/生图/博客）**：问用户要值 → 立刻写盘，例如：
  ```bash
  bash scripts/setup.sh set DINGTALK_APP_KEY    "<用户给的值>"
  bash scripts/setup.sh set DINGTALK_APP_SECRET "<用户给的值>"
  ```
  写完别回显值；告诉用户"已写入 .env.local"。
- **工具型（飞书/微信/公众号/小宇宙）**：给出要在他自己终端跑的命令（登录/起服务/扫码），这些交互式步骤让用户自己执行；你只负责给清晰步骤并在之后体检。
  - 飞书加租户：`scripts/feishu-add-tenant.sh <租户名>`（隐藏输入 secret，建 profile + 设备码登录 + 建目录），配完把租户名填进 `.env.local` 的 `FEISHU_TENANTS`。
- **多租户**：同一平台第二套凭证 → 写到 `.env.<租户>.local`，运行时 `TENANT=<租户> <拉取命令>` 叠加（飞书走 `FEISHU_TENANTS`）。

### 4. 体检 + 试跑

```bash
bash scripts/setup.sh doctor     # 逐集成报告：✅就绪 / ⚠️待办 / —可选
```

把 doctor 结果讲给用户听，对 ⚠️ 项给出下一步。配好后可挑一个试跑（如 `bash .claude/skills/blog/scripts/pull-blog.sh`、`scripts/pull-feishu.sh`），确认能落盘到 `sources/`。

## 何时用别的

- 用户只是要拉某个具体来源 → 直接用对应来源 skill，不必走整套向导。
- 用户要装/更新一个 skill → 见 `skills/README.md` 的一行安装器（`skills/install.sh`）。

## 红线

- 凭证只进 `.env.local` / `.env.<租户>.local`，永不进 git、永不回显、永不外发。
- 向导只配置、不删用户已有数据；`init` 不覆盖已存在的 `.env.local`。
