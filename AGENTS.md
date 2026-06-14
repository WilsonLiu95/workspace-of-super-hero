# AGENTS.md

本文件供**非 Claude 的 Agent**（如接到飞书里的 Codex、各类机器人/脚本）读取。
完整约定见 [`CLAUDE.md`](./CLAUDE.md)；本文件只摘录你最需要遵守的**写入契约**。

## 这是什么

一个个人 Co-Worker 工作空间，不是代码仓库。数据流：
`sources/`（原始数据，按来源分类）→ 加工 → `deliverables/`（交付物）。

## 你把数据写到哪里

把抓取/同步来的原始数据写入 `sources/`，**按来源分类**：

| 来源 | 路径 |
| --- | --- |
| 飞书（多租户） | `sources/feishu/<租户>/<dm\|groups\|docs>/` |
| 微信 | `sources/wechat/` |
| 公众号 | `sources/mp/` |
| 其他社媒 | `sources/social/` |
| 个人知识库 | `sources/knowledge/` |
| 不确定/临时 | `sources/inbox/`（之后由人或 Agent 归档） |

## 命名与元数据（必须遵守）

- 文件名：`YYYY-MM-DD_<slug>.md`
- 每个文件以 YAML frontmatter 开头：

```yaml
---
source: feishu          # feishu | wechat | mp | social | knowledge | inbox
tenant: <租户名>         # 多租户来源（如飞书）必填，其余可省
channel: <会话/群/作者>
type: dm                # dm | group | doc | article | note
captured: 2026-06-14
---
```

## 红线

- **只追加，不改写。** 不要修改或删除 `sources/` 里已有的原始文件。
- **不要碰 `deliverables/`**（那是产出区）。
- 不确定来源/分类时，写进 `sources/inbox/` 即可。
- `sources/` 含私密数据；不要外泄。
