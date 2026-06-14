# scripts/ — 自动化与可复用脚本（单一实现，Claude / Codex / 定时器共用）

这里是**真正干活的逻辑**。Claude 的 `.claude/skills/` 和 Codex 的 `AGENTS.md` 都只是**薄入口**指向这里——实现单一、不分叉。这些脚本也直接供定时任务调用。

> 设计原则：拉取脚本只把**原始数据**轻量落到 `sources/<来源>/`（带 frontmatter），精细解析与合成交给 Agent。

## 脚本一览

| 脚本 | 作用 | 依赖工具 | 关键环境变量 |
| --- | --- | --- | --- |
| `pull-feishu.sh` | 飞书会话/消息 → `sources/feishu/<租户>/` | `lark-cli`（已登录） | `FEISHU_TENANT` `FEISHU_SINCE_DAYS` `FEISHU_MAX_CHATS` |
| `pull-getnote.sh` | 得到/Biji 笔记 → `sources/getnote/` | `python3` + `lib/get_biji.py` | `GET_BIJI_API_KEY` `GET_BIJI_CLIENT_ID` `GETNOTE_SINCE_ID` |
| `pull-wechat.sh` | 微信聊天 → `sources/wechat/` | `chatlog`（HTTP 服务） | `CHATLOG_BASE_URL` `WECHAT_SINCE_DAYS` |
| `pull-all.sh` | 编排上述全部，供定时器调用 | — | `PULL_SOURCES` |
| `generate-image.py` | OpenAI 兼容接口生图（见 ai-image 技能） | `python3` | `AIPROXY_API_KEY` `AIPROXY_BASE_URL` |
| `lib/common.sh` | 共享 bash 助手 | — | — |
| `lib/get_biji.py` | Biji OpenAPI 客户端（只读 env 凭证） | `python3` | 见上 |

各来源的前置安装/登录见对应技能：`.claude/skills/{feishu-cli,get-biji,wechat-chatlog,ai-image}/SKILL.md`。

## 凭证

**本模板不含任何 key/账号。** 三种方式提供凭证，按需选一：
1. 直接 `export`（适合手动跑）；
2. 写进仓库根 `.env.local`（**已被 `.gitignore` 忽略**）——`pull-*` 会自动 `source` 它，适合定时任务无人值守；
3. 工具自带的登录态（如 `lark-cli auth login` 存在 `~/.lark-cli`，与本仓库无关）。

## 手动跑

```bash
scripts/pull-getnote.sh                      # 单个来源
PULL_SOURCES="feishu getnote" scripts/pull-all.sh
scripts/pull-all.sh                          # 全部
```

## 定时触发（三选一，当前都未启用 —— 你说"先不绑定触发器"）

把 `pull-all.sh` 挂到任一调度器即可。三种方案：

### A. Codex 定时（automation.toml，cron 风格）
参考你已有的 `~/.codex/automations/getnote/automation.toml`，新建一条指向本仓库：

```toml
version = 1
id = "workspace-pull-all"
kind = "cron"
name = "每日拉取来源到 workspace"
prompt = "在仓库根运行 `scripts/pull-all.sh`，汇总各来源成败；失败保留现场并说明。"
status = "ACTIVE"
rrule = "FREQ=DAILY;BYHOUR=6;BYMINUTE=30;BYSECOND=0"
execution_environment = "local"
cwds = ["/path/to/workspace"]   # 改成本仓库绝对路径
```

### B. Claude Routines（云端定时 agent）
用 `/schedule` 创建每日例程，提示词同上（"在 workspace 根跑 scripts/pull-all.sh 并汇总"）。需联网且凭证在云端可用。

### C. 本地 cron / launchd（最简单、纯本地）
```cron
30 6 * * *  cd /path/to/workspace && /bin/bash scripts/pull-all.sh >> .tmp/pull.log 2>&1
```
（确保 `.env.local` 已配好凭证，定时任务才能无人值守拿到 key。）

## 双 Agent 复用

- **Claude**：自然语言触发 `.claude/skills/*` → 调用本目录脚本。
- **Codex**：读根 `AGENTS.md` → 同样调用本目录脚本。
- **定时器**：直接调 `pull-all.sh`。

三方同源，改逻辑只改 `scripts/`。
