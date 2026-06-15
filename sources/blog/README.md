# sources/blog/ — 博客 / RSS 来源

博客归档（`blog` 技能）的落盘区。**只读 / 仅追加**，按原文 url 去重。

结构：`sources/blog/YYYY-MM-DD_<slug>.md`

frontmatter：

```yaml
---
source: blog
channel: <站点 / 作者>
type: article
captured: YYYY-MM-DD
url: <原文链接>
published: <发布时间>
---
```

拉取：在 `.env.local` 配 `BLOG_FEEDS`（逗号分隔 feed 或主页 URL，主页会自动发现 feed），然后
`bash .claude/skills/blog/scripts/pull-blog.sh`。无需任何凭证；装上 `feedparser/trafilatura/markdownify` 抽正文更好（不装也能跑）。
