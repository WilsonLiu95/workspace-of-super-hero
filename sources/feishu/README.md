# sources/feishu/ — 飞书（租户优先）

飞书是多租户的，**先按租户隔离，再分会话类型**：

```
feishu/
└── <租户>/            # 一个飞书租户/组织一个目录
    ├── dm/            # 单聊： YYYY-MM-DD_<对方>.md
    ├── groups/        # 群聊： YYYY-MM-DD_<群名>.md
    └── docs/          # 飞书文档镜像： <主题>.md
```

## 外部 Agent 写入契约

接到飞书里的 Codex/机器人按此写入（与根目录 `AGENTS.md` 一致）：

- 路径：`sources/feishu/<租户>/<dm|groups|docs>/`
- 文件名：`YYYY-MM-DD_<slug>.md`
- frontmatter：

```yaml
---
source: feishu
tenant: <租户名>
channel: <对方/群名/文档标题>
type: dm                # dm | group | doc
captured: 2026-06-14
---
```

- **只追加，不改写**已有文件。

> `_example-tenant/` 是演示用的虚构租户，采用后删除。
