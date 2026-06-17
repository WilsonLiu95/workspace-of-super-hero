# sources/tencent-meeting/ — 腾讯会议来源（个人版）

腾讯会议归档（`tencent-meeting` 技能）的落盘区：录制信息、AI 智能纪要、逐字稿。**只读 / 仅追加**。

结构：`sources/tencent-meeting/YYYY-MM-DD_<会议主题>.md`（按 `meeting_id` 把同一会议的「云录制 / 文字转写」多条归并为一篇）。

frontmatter：

```yaml
---
source: tencent-meeting
edition: personal
channel: <会议主题>
type: meeting
captured: YYYY-MM-DD
meeting_id: <会议ID>
meeting_code: <会议号>
record_start: <录制开始时间>
---
```

## 怎么拉（仅个人版，零密钥）

官方 `tmeet` CLI 走 OAuth 登录，**无需任何 `.env` 凭证**：

```bash
npm i -g @tencentcloud/tmeet     # 安装官方 CLI
tmeet auth login                 # 扫码授权（凭据存 ~/.tmeet/，不进仓库）
bash skills/tencent-meeting/scripts/pull-tencent-meeting.sh   # 默认最近 30 天 → 本目录
```

脚本写入会议元信息、录制链接（`sharing_url`）、**AI 智能纪要**（正文内嵌）与逐字稿段落数。详见 `tencent-meeting` 技能。

> 企业版 AKSK REST API 路径已移除——本工作区只保留个人版。
