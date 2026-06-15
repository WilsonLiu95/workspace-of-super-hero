# sources/tencent-meeting/ — 腾讯会议来源

腾讯会议归档（`tencent-meeting` 技能）的落盘区：录制信息、AI 纪要、智能转写、会议摘要。**只读 / 仅追加**。

结构：`sources/tencent-meeting/YYYY-MM-DD_<会议主题>.md`（同主题多场录制会带 record_file_id 末 8 位区分）。

frontmatter：

```yaml
---
source: tencent-meeting
channel: <会议主题>
type: meeting
captured: YYYY-MM-DD
meeting_id: <会议ID>
record_file_id: <录制文件ID>
---
```

拉取：`bash .claude/skills/tencent-meeting/scripts/pull-tencent-meeting.sh`（需企业版/商业版自建应用 AKSK，见 `.env.example`）。
注意：纪要/转写下载地址约 5 分钟过期，脚本会即时抓取。
