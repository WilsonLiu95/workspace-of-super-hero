---
name: tencent-meeting
description: 把腾讯会议的录制、AI 纪要、智能转写、会议摘要归档进 sources/tencent-meeting/。触发场景：「拉腾讯会议录制」「同步腾讯会议纪要」「导出会议转写/逐字稿」「腾讯会议 AI 纪要」「会议录制存下来」「tencent meeting」「腾讯会议 API」。实现是自包含脚本 scripts/pull-tencent-meeting.sh + scripts/tmeeting_client.py（标准库，零 pip）。需企业版/商业版「自建应用」AKSK 凭证。
version: 0.1.0
updated: "2026-06-15"
---

# 腾讯会议（录制 / AI 纪要 / 转写）

用腾讯会议企业版 REST API，把时间窗内可见的会议录制连同 **AI 纪要 / 智能转写 / 会议摘要 / 结构化逐字稿** 归档到 `sources/tencent-meeting/`。纯标准库实现，零 pip 依赖。

## 何时使用

- 「把最近的腾讯会议录制和纪要拉下来」「同步会议转写」「导出某次会议的逐字稿」。
- 需要把会议内容当作来源底稿，供后续合成会议纪要、复盘、知识库归档。
- 不适用：个人版腾讯会议（无自建应用 API）；只想看录像不需要归档的场景。

## 前置（凭证与依赖）

依赖：`python3`、`git`、`bash`（无需 pip 安装）。

凭证统一放仓库根 `.env.local`（已被 `.gitignore` 忽略），来自腾讯会议**企业版/商业版「自建应用（REST API）」**：

```bash
TENCENT_MEETING_APP_ID=            # AppId        必需
TENCENT_MEETING_SDK_ID=            # SdkId        必需
TENCENT_MEETING_SECRET_ID=         # SecretId     必需
TENCENT_MEETING_SECRET_KEY=        # SecretKey    必需
TENCENT_MEETING_OPERATOR_ID=       # 操作者 ID    必需（会议创建者，或持企业录制管理权限者）
TENCENT_MEETING_OPERATOR_ID_TYPE=1 # 可选，默认 1（1=userid）
TENCENT_MEETING_SINCE_DAYS=7       # 可选，最近 N 天，默认 7，硬上限 31
```

- **API host**：`https://api.meeting.qq.com`（注意不是 `qcloud`）。
- **operator 权限**：操作者必须是该会议的**创建者**，或持有企业「**录制管理**」权限；否则列不到他人录制。
- **2026-01-16 之后新建的应用**：除 AKSK 签名外还需额外携带 `STS-Token` 请求头（签发方式见腾讯会议 AKSK 鉴权文档）。本脚本默认不带该头，老应用可直接用；若你的应用是该日期后新建且报鉴权错误，需自行补 STS-Token（见「红线」）。

## 用法

```bash
# 一键归档：读 .env.local → 列录制 → 取地址/AI纪要/转写 → 写 sources/tencent-meeting/<date>_<主题>.md
bash .claude/skills/tencent-meeting/scripts/pull-tencent-meeting.sh

# 多租户：在 .env.local 之上叠加 .env.<租户>.local 的凭证
TENANT=lumi bash .claude/skills/tencent-meeting/scripts/pull-tencent-meeting.sh

# 调时间窗（最近 14 天，硬上限 31）
TENCENT_MEETING_SINCE_DAYS=14 bash .claude/skills/tencent-meeting/scripts/pull-tencent-meeting.sh
```

归档三步流程（脚本内部自动完成）：

1. `GET /v1/records` —— 按时间窗分页列录制（每场含 `meeting_id`、`subject`、`record_files[]`）。
2. `GET /v1/addresses/{record_file_id}` —— 取在线观看/下载/音频地址（约 **5 分钟**有效），及 AI 资源数组：`meeting_summary` / `ai_meeting_transcripts` / `ai_minutes` / `ai_topic_minutes` / `ai_speaker_minutes` / `ai_ds_minutes`。文本型（txt/htm）正文**立即抓取**内嵌进 markdown；pdf/docx 仅记录链接。
3. `GET /v1/records/transcripts/details` —— 结构化逐字稿（段落/句子，带发言人），可用则一并写入。

> 签名为腾讯会议 AKSK（TC3 风格 HMAC-SHA256，但**双重编码**：先 hex 再 base64），每次请求重新生成 nonce/时间戳/签名；签名 uri 含 query 且与实际请求顺序一致。细节见 `scripts/tmeeting_client.py` 注释。

## 落盘约定

- 路径：`sources/tencent-meeting/<YYYY-MM-DD>_<主题>.md`（日期取录制开始时间；同会议多段录制时文件名追加 `record_file_id` 末段防覆盖）。
- frontmatter：

```yaml
---
source: tencent-meeting
channel: <会议主题>
type: meeting
captured: 2026-06-15
meeting_id: <会议ID>
record_file_id: <录制文件ID>
record_start: 2026-06-15 10:00:00   # 有则填
record_end: 2026-06-15 11:00:00     # 有则填
---
```

- 正文：会议元信息 + 临时地址（注明 5 分钟有效）+ 「AI 纪要/转写/摘要」各小节（文本型内嵌正文）+ 「结构化逐字稿」。
- **仅追加**：目标文件已存在则跳过，绝不覆盖。运行时 `mkdir -p`。

## 红线

- **来源只读、仅追加**：只写 `sources/tencent-meeting/`，不改写/删除已有底稿。
- **凭证不入库**：只从 `.env.local` / `.env.<租户>.local` 读，绝不硬编码或提交密钥。
- **下载地址 5 分钟即失效**：脚本对文本型立即抓取；若正文显示「地址已过期」，重跑即可重新签发。pdf/docx 不内嵌正文，仅留链接。
- **诚实的局限**：
  - 个人版无此 API；operator 无录制管理权限时只能看到自己创建的会议。
  - 2026-01-16 后新建的应用需 STS-Token，本脚本未实现该头；遇鉴权错误请补签（或改用更早创建的应用）。
  - AI 资源数组字段名/文件类型以腾讯当前版本为准，脚本做了防御式解析；若字段对不上按 `tmeeting_client.py` 里 `AI_ARRAY_KEYS` 注释微调。
  - 会议内容可能私密：落在 `sources/`（默认不进 git），不要外泄给外部服务/公开链接。
