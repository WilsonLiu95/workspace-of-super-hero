---
name: xiaoyuzhou-podcast
description: 归档小宇宙播客内容到本工作区。触发场景：「拉小宇宙」「同步小宇宙播客」「保存播客单集」「抓 episode shownotes」「归档播客订阅/节目/单集链接」「小宇宙 RSS」。适用于用户提供小宇宙单集/节目链接、RSS、导出文件或明确授权的数据源；原始内容写入 sources/social/ 或不确定时 sources/inbox/。
---

# 小宇宙播客归档

把小宇宙播客节目、单集、shownotes、链接和用户提供的导出内容归档到 `sources/`。不要假设存在稳定官方 API；优先使用用户提供的 URL、RSS、导出文件或已配置脚本。

## 数据来源

- 先检查用户是否提供了单集 URL、节目 URL、RSS feed、HTML/Markdown 导出或本地文件。
- 若没有明确来源，先问用户要链接、RSS 或导出文件；不要凭关键词全网抓取。
- 可以使用公开网页/RSS 中可见的元数据和 shownotes。不要绕过登录、付费、访问控制或反爬限制。
- 不要下载音频文件，除非用户明确要求且确认版权/存储成本。

## 落盘规则

优先写入：

```text
sources/social/YYYY-MM-DD_xiaoyuzhou_<slug>.md
```

frontmatter 必须包含：

```yaml
---
source: social
channel: 小宇宙/<播客名>
type: note
captured: YYYY-MM-DD
platform: xiaoyuzhou
url: <原始链接>
---
```

若节目名、发布时间、作者或来源可信度不确定，写入 `sources/inbox/YYYY-MM-DD_xiaoyuzhou_<slug>.md`，并在正文顶部标注待确认项。

## 内容格式

正文尽量保留原始信息，而不是直接总结替代原文：

- 标题、播客名、主播/嘉宾、发布时间、时长。
- 原始链接、RSS 链接或导出文件路径。
- shownotes、章节、引用链接、推荐书影音等原始条目。
- 如果用户要求总结，把总结放在原始信息之后，并明确标注为 Agent 整理。

## 红线

- 只追加新归档文件，不修改或删除 `sources/` 已有原始文件。
- 不把私密订阅、账号 token、cookie、导出包上传或写入 git。
- 需要登录态、批量抓取或第三方工具时，先说明方案和风险，再等用户确认。
