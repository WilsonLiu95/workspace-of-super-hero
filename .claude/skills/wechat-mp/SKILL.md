---
name: wechat-mp
description: 归档微信公众号文章到本工作区。触发场景：「拉微信公众号」「保存公众号文章」「同步公众号历史文章」「归档订阅号推文」「微信公众平台素材」「mp.weixin.qq.com 链接」。适用于用户提供公众号文章链接、HTML/PDF/Markdown 导出、微信公众平台导出或明确授权的数据源；原始内容写入 sources/mp/ 或不确定时 sources/inbox/。
---

# 微信公众号归档

把微信公众号文章、推文、素材导出和用户提供的公众号链接归档到 `sources/mp/`。这不是微信聊天记录；聊天记录使用 `wechat-chatlog`。

## 数据来源

- 优先使用用户提供的 `mp.weixin.qq.com` 链接、HTML/PDF/Markdown 导出、剪藏文件或微信公众平台导出。
- 若用户是公众号所有者，可使用其授权导出的素材或后台数据；凭证、cookie、token 不写入仓库。
- 不要绕过登录、付费、转载限制或平台访问控制。无法公开访问时，要求用户提供导出文件或明确授权方式。
- 批量历史文章抓取前，先确认范围、账号、时间窗口和频率。

## 落盘规则

优先写入：

```text
sources/mp/YYYY-MM-DD_<title-slug>.md
```

frontmatter 必须包含：

```yaml
---
source: mp
channel: <公众号名>
type: article
captured: YYYY-MM-DD
url: <原始链接>
---
```

若公众号名、标题、发布时间或来源不确定，写入 `sources/inbox/YYYY-MM-DD_mp_<slug>.md`，并在正文顶部标注待确认项。

## 内容格式

正文以保留原始资料为主：

- 标题、公众号名、作者、发布时间、原始 URL。
- 原文 Markdown/HTML 转写内容，尽量保留小标题、列表、引用和图片链接。
- 图片可以保留远程链接或本地附件路径；不要把大批二进制附件塞进 git。
- 如果用户要求摘要或提炼观点，把整理内容放在原文之后，并标注为 Agent 整理。

## 红线

- 只追加新归档文件，不修改或删除 `sources/` 已有原始文件。
- 不提交真实公众号后台导出、cookie、token、私密素材包。
- 不把公众号内容写到 `deliverables/`，除非用户明确要求制作交付物。
