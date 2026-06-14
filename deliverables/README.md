# deliverables/ — 交付物

你/Agent 产出的成果。每个交付物**溯源**到它引用的来源文件。

## 三种去向

| 目录 | 去向 | 落地方式 |
| --- | --- | --- |
| `feishu/` | 回写飞书的文档 | 本地写好 Markdown，再经飞书集成/外部 Agent 回写飞书 |
| `local/` | 本地终稿 | 直接存这里即最终产物 |
| `web/` | 线上 HTML | 产出自包含 HTML，发布到自选静态托管（见 `web/README.md`） |

## frontmatter（必须）

```yaml
---
title: <标题>
status: draft           # draft | review | final | published
destination: local      # feishu | local | web
sources:                # 溯源回链：用到的来源文件路径
  - sources/feishu/<租户>/dm/2026-06-14_xxx.md
created: 2026-06-14
published_url:          # 仅 web/已发布时填写
---
```

> `_example-*` 为示例，采用后删除。
