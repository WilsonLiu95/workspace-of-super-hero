---
name: blog
description: 拉取个人博客 / RSS / Atom 订阅源的文章，抽取正文转 Markdown 并归档进 sources/blog/。触发场景：「拉博客」「订阅这个博客」「同步 RSS」「把这个站点的文章存下来」「归档某博客的文章」「RSS feed」「Atom feed」「subscribe blog」「pull blog」。给主页 URL 会自动发现 feed；无需任何凭证。实现是自包含脚本 scripts/pull-blog.sh + scripts/blog_client.py（标准库即可跑，装上 feedparser/trafilatura/markdownify 效果更好）。
version: 0.1.0
updated: "2026-06-15"
---

# blog — 博客 / RSS 归档

把个人博客、RSS/Atom 订阅源的文章拉回 `sources/blog/`：自动发现 feed → 解析条目 → **重新抓原文抽正文**（feed 常只给摘要）→ 转 Markdown → 带 frontmatter 落盘、按 url 去重、仅追加。

> 自包含技能：逻辑全在本技能 `scripts/` 内，不依赖仓库顶层 `scripts/lib/`，复制到任何仓库都能跑。**无需凭证。**

## 何时使用

- 用户给一个博客**主页**（如 `https://example.com`）或 **feed URL**（如 `.../feed`、`.../atom.xml`），要把文章归档成素材。
- 用户说「订阅/同步这个 RSS」「把这个博客最近的文章拉下来」「归档某作者的博客」。
- 想批量收集多个博客作为后续合成/写作的底稿。

**不要用**：要拉的是微信公众号（用 `wechat-exporter`）、小宇宙播客（用 `xiaoyuzhou`）、得到笔记（用 `get-biji`）、飞书/微信聊天（各自技能）。本技能只管开放的博客/RSS。

## 前置（凭证与依赖）

- **凭证**：无。完全靠公开 feed/网页，不需要任何 key/登录。
- **运行时**：`python3`（标准库即可跑出文件）。
- **可选增强**（强烈建议装，效果显著更好；缺了会自动降级并在 stderr 提示）：

  ```bash
  pip install feedparser trafilatura markdownify
  ```

  - `feedparser` —— 更健壮的 RSS/Atom 解析（缺则用标准库 `xml.etree`）。
  - `trafilatura` —— 正文抽取并直出 Markdown（缺则用 `markdownify` 或标准库轻量剥标签兜底，质量明显更低）。
  - `markdownify` —— html→Markdown 兜底。

  脚本启动会在 stderr 打印当前运行模式；降级时会原样给出上面的 `pip install` 提示。

## 用法

配置写在仓库根 `.env.local`（已被 `.gitignore` 忽略）：

```bash
# 逗号分隔：可混填 feed URL 和站点主页 URL（主页会自动发现 feed）
BLOG_FEEDS="https://example.com/feed,https://someone.dev,https://blog.foo/atom.xml"
BLOG_MAX_POSTS=20          # 每个 feed 最多归档多少篇（默认 20）
BLOG_SINCE_DAYS=           # 跳过早于 N 天的条目（默认空 = 不限制；无可解析日期的条目一律保留）
```

跑：

```bash
skills/blog/scripts/pull-blog.sh                  # 读 .env.local 的 BLOG_FEEDS
skills/blog/scripts/pull-blog.sh https://x.com/feed  # 直接传 URL，覆盖 BLOG_FEEDS
skills/blog/scripts/pull-blog.sh https://someone.dev # 传主页，自动发现 feed
TENANT=foo skills/blog/scripts/pull-blog.sh         # 额外叠加 .env.foo.local
skills/blog/scripts/pull-blog.sh --dry-run https://x.com/feed  # 只演练不写盘
```

**自动发现 feed**：传主页 URL 时，脚本先抓 HTML 找 `<link rel="alternate" type="application/rss+xml|atom+xml">`；找不到再探测常见路径 `/feed`、`/rss.xml`、`/atom.xml`、`/index.xml`、`/feed.xml`、`/rss`、`/atom`。

## 落盘约定

每篇文章写到 `sources/blog/<YYYY-MM-DD>_<slug>.md`，frontmatter：

```yaml
---
source: blog
channel: <站点标题或作者>
type: article
captured: 2026-06-15        # 采集日期
url: https://example.com/posts/xxx
published: 2026-06-10       # 文章发布日期（解析得到则填）
author: <作者，若有>
---
```

- **按 url 去重**：写入前一次性扫描 `sources/blog/` 下已有文件 frontmatter 里的 `url:`，命中即跳过。
- **仅追加**：同名目标文件已存在不覆盖（撞名时追加短哈希；再撞则跳过）。
- slug 保留中文，替换 `/ \ : * ? " < > |` 与空白为 `-`，截断约 60 字符。
- `sources/` 默认不进 git（见根 `.gitignore`），归档内容留在本地。

## 中文平台 feed 可得性

- **个人博客 / Hexo / Hugo / WordPress / Ghost** 多自带 RSS/Atom（常在 `/feed`、`/atom.xml`、`/index.xml`），直接传主页即可被自动发现。
- **知乎专栏 / 语雀 / 微信公众号** 等通常不直接暴露公开 RSS：需借助 **RSSHub**（`https://docs.rsshub.app`）生成对应 feed，再把生成的 feed URL 填进 `BLOG_FEEDS`。
- 部分站点有反爬或登录墙：正文抽取可能失败，此时脚本会退回 feed 摘要，并在 frontmatter 保留 `url` 可溯源。

## 红线

- **只读公开内容**：不绕过付费墙/登录墙，不抓明确禁止抓取的源。
- **来源仅追加**：不改写/删除 `sources/blog/` 既有文件。
- **诚实标注质量**：降级模式（无 trafilatura/feedparser）抽取质量较低，正文可能仅为摘要——脚本会在 stderr 明确告知，frontmatter 始终留 `url` 以便回看原文。
- **不含任何凭证**：本技能不读写任何 key；若某源需要鉴权，应由用户自行用 RSSHub 等生成可公开访问的 feed。
