---
name: tencent-meeting
description: 把腾讯会议（个人版）的录制、AI 智能纪要、逐字稿归档进 sources/tencent-meeting/。触发场景：「拉腾讯会议录制」「同步腾讯会议纪要」「导出会议转写/逐字稿」「腾讯会议 AI 纪要」「会议录制存下来」「tencent meeting」「tmeet」。用腾讯官方 tmeet CLI（OAuth 扫码登录、零密钥）；实现是自包含脚本 scripts/pull-tencent-meeting.sh。
version: 0.3.0
updated: "2026-06-17"
---

# 腾讯会议（个人版 · 录制 / AI 智能纪要 / 逐字稿）

用腾讯官方 **`tmeet` CLI**（OAuth 扫码登录，**零密钥**）把时间窗内的会议录制连同 **AI 智能纪要 / 逐字稿** 归档到 `sources/tencent-meeting/`。

> 本技能只支持**个人版**。个人版没有企业自建应用 AKSK，OAuth 登录一次即可，最省事。
> （企业版 AKSK REST API 路径已移除——本工作区只保留个人版。）

## 何时使用

- 「把最近的腾讯会议录制和纪要拉下来」「同步会议纪要」「导出某次会议的逐字稿」。
- 需要把会议内容当作来源底稿，供后续合成会议纪要、复盘、知识库归档。
- 只想看录像、不需要归档的场景不必用本技能。

## 前置（一次性，零密钥）

```bash
npm i -g @tencentcloud/tmeet     # 官方 CLI（npm 包 @tencentcloud/tmeet）
tmeet auth login                 # 浏览器 OAuth 授权（凭据存 ~/.tmeet/，不进仓库）
tmeet auth status                # 确认已登录
```

- 凭据由 tmeet 自管（`~/.tmeet/`，仓库外）；**不需要**任何 `.env` 密钥。
- token 有效期约 2 小时、refresh token 约 30 天，过期重跑 `tmeet auth login` 即可。
- 依赖：`tmeet`、`python3`。

## 用法

```bash
bash skills/tencent-meeting/scripts/pull-tencent-meeting.sh            # 默认最近 30 天
TMEET_SINCE_DAYS=14 bash skills/tencent-meeting/scripts/pull-tencent-meeting.sh
TENANT=lumi bash skills/tencent-meeting/scripts/pull-tencent-meeting.sh # 多账号：叠加 .env.lumi.local
```

脚本流程：

1. `tmeet record list --start … --end …` —— 按时间窗列录制（每条含 `meeting_id`、`subject`、`record_files[]`、`sharing_url`）。
2. 按 `meeting_id` 把「云录制 / 文字转写」多条**归并为一篇**。
3. `tmeet record smart-minutes --record-file-id <id>` —— 取 **AI 智能纪要**（摘要 + 分节 + 待办@人），正文内嵌进 markdown。
4. `tmeet record transcript-paragraphs --record-file-id <id>` —— 逐字稿**段落数**（该接口只返回时间轴、不含正文；正文按需用同命令获取）。

## 落盘约定

- 路径：`sources/tencent-meeting/<YYYY-MM-DD>_<主题>.md`（日期取录制开始时间）。
- frontmatter：

```yaml
---
source: tencent-meeting
edition: personal
channel: <会议主题>
type: meeting
captured: 2026-06-17
meeting_id: <会议ID>
meeting_code: <会议号>
record_start: 2026-06-17T10:00:00+08:00
---
```

- 正文：会议元信息 + 录制文件（含 `sharing_url`）+ 「AI 智能纪要」（内嵌正文）+ 「逐字稿」（段落数与获取方式）。
- **仅追加**：目标文件已存在则跳过，绝不覆盖。运行时 `mkdir -p`。

## 红线

- **来源只读、仅追加**：只写 `sources/tencent-meeting/`，不改写/删除已有底稿。
- **会议内容可能私密**：落在 `sources/`（默认不进 git），不要外泄给外部服务/公开链接。
- **登录态在仓库外**：`~/.tmeet/`，不要把 token 复制进仓库。
- **诚实的局限**：只能看到当前登录账号自己的录制；`smart-minutes` 仅在该录制开通了 AI 纪要时有正文。
