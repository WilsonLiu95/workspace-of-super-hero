# sources/dingtalk/ — 钉钉来源

钉钉归档（`dingtalk` 技能）的落盘区。**只读 / 仅追加**，勿改写删除。

> 钉钉**不开放历史聊天记录 API**：这里只会有通讯录与文档/知识库/钉盘，**没有聊天记录**。

结构：

```text
sources/dingtalk/<租户>/contacts/YYYY-MM-DD_contacts.md
sources/dingtalk/<租户>/docs/YYYY-MM-DD_*.md
```

frontmatter：

```yaml
---
source: dingtalk
tenant: <租户>
channel: 通讯录 | <文档/知识库名>
type: contacts | doc
captured: YYYY-MM-DD
---
```

拉取：`bash .claude/skills/dingtalk/scripts/pull-dingtalk.sh`（需 `.env.local` 配 `DINGTALK_APP_KEY/SECRET`，且管理员已授权）。
多租户：`TENANT=<租户> bash .claude/skills/dingtalk/scripts/pull-dingtalk.sh`（叠加 `.env.<租户>.local`）。
