# sources/ — 原始数据（按来源分类）

这里存放各种来源的**原始数据**。规则：**只读为主、仅追加**；要加工就读出来写到 `deliverables/` 或 `workstreams/`，不要改写或删除底稿。

## 子目录

| 目录 | 来源 | 说明 |
| --- | --- | --- |
| `feishu/` | 飞书 | **租户优先**：`feishu/<租户>/{dm,groups,docs}/` |
| `wechat/` | 微信 | 单聊/群聊记录 |
| `mp/` | 公众号 | 文章、推文 |
| `social/` | 其他社媒/播客 | 微博/小红书/X/小宇宙等的帖子、收藏、播客单集 |
| `knowledge/` | 个人知识库 | 笔记、剪藏、长期资料 |
| `inbox/` | 临时中转 | 来源/分类不明的，先丢这里待归档 |

## 每个文件的 frontmatter（必须）

```yaml
---
source: feishu          # feishu | wechat | mp | social | knowledge | inbox
tenant: <租户名>         # 多租户来源（飞书）必填，其余可省
channel: <会话/群/作者>
type: dm                # dm | group | doc | article | note
captured: 2026-06-14    # 采集日期
---
```

文件命名：`YYYY-MM-DD_<slug>.md`（知识库等无明确日期的可用主题 slug）。

> 示例文件均以 `_example-` 开头（飞书示例在 `_example-tenant/` 内）。采用本模板后删除所有 `_example-*` 即可。
