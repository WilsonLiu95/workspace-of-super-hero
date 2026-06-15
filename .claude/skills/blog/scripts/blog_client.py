#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blog_client.py —— 博客 / RSS 归档客户端。

设计：stdlib-first，可选依赖增强。
  - 优先用（若 importable）：
      feedparser    —— 解析 RSS/Atom（更健壮）
      trafilatura   —— 正文抽取并直出 markdown
      markdownify   —— html→markdown 兜底
  - 缺这些时纯标准库降级运行：
      xml.etree.ElementTree 解析 RSS <item> / Atom <entry>
      轻量 stdlib 抽正文（去 script/style，剥标签，或退回 feed 摘要）—— 明显更低质，但保证能跑出文件。

凭证：无需任何凭证。配置来自环境变量（由 pull-blog.sh 从 .env.local 注入）或 CLI 参数。
  BLOG_FEEDS       逗号分隔的 feed URL 或站点主页 URL（主页会自动发现 feed）
  BLOG_MAX_POSTS   每个 feed 最多归档多少篇（默认 20）
  BLOG_SINCE_DAYS  跳过早于 N 天的条目（默认空 = 不限制）
CLI 参数里直接给出的 feed URL 覆盖 BLOG_FEEDS。

落盘：sources/blog/<YYYY-MM-DD>_<slug>.md，带 frontmatter。
  按 url 去重：写入前扫描 sources/blog/ 下已有文件的 frontmatter，命中则跳过。
  仅追加：同名目标文件已存在也跳过，不覆盖。
"""

import os
import re
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# 可选依赖探测（缺了就降级，不报错）
# ---------------------------------------------------------------------------
try:
    import feedparser  # type: ignore
    HAVE_FEEDPARSER = True
except Exception:
    HAVE_FEEDPARSER = False

try:
    import trafilatura  # type: ignore
    HAVE_TRAFILATURA = True
except Exception:
    HAVE_TRAFILATURA = False

try:
    from markdownify import markdownify as _md  # type: ignore
    HAVE_MARKDOWNIFY = True
except Exception:
    HAVE_MARKDOWNIFY = False

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 主页发现不到 <link> 时，挨个探测的常见 feed 路径
COMMON_FEED_PATHS = ["/feed", "/rss.xml", "/atom.xml", "/index.xml",
                     "/feed.xml", "/rss", "/atom", "/feed/", "/rss/"]


def log(msg):
    """统一往 stderr 打日志，保持和其它脚本一致的前缀风格。"""
    print(f"[blog] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def http_get(url, timeout=30):
    """拉一个 URL，返回 (text, final_url, content_type)；失败返回 (None, url, '')。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            final = r.geturl() or url
            ctype = (r.headers.get("Content-Type") or "").lower()
            # 优先按响应声明的编码解码，退回 utf-8 忽略错误
            charset = ""
            m = re.search(r"charset=([\w\-]+)", ctype)
            if m:
                charset = m.group(1)
            if not charset:
                m2 = re.search(br'charset=["\']?([\w\-]+)', raw[:2048], re.I)
                if m2:
                    charset = m2.group(1).decode("ascii", "ignore")
            for enc in (charset, "utf-8", "gbk", "latin-1"):
                if not enc:
                    continue
                try:
                    return raw.decode(enc), final, ctype
                except Exception:
                    continue
            return raw.decode("utf-8", "ignore"), final, ctype
    except Exception as e:
        log(f"GET 失败 {url} —— {e}")
        return None, url, ""


# ---------------------------------------------------------------------------
# Feed 发现
# ---------------------------------------------------------------------------
def looks_like_feed(text, ctype):
    """粗判一段内容是不是 feed（XML RSS/Atom 或 JSON Feed）。"""
    if not text:
        return False
    if "xml" in ctype or "rss" in ctype or "atom" in ctype or "json" in ctype:
        head = text.lstrip()[:400].lower()
        if "<rss" in head or "<feed" in head or '"version"' in head and "jsonfeed" in head:
            return True
    head = text.lstrip()[:400].lower()
    top2k = text[:2000].lower()
    # 要求出现真正的 feed 根元素 <rss>/<feed>，不再把任何含 <channel>/<entry> 的 XML 误判为 feed。
    return ("<rss" in head) or ("<feed" in head) or ("<?xml" in head and ("<rss" in top2k or "<feed" in top2k))


def discover_feed(url):
    """
    给一个 URL：
      - 若本身就是 feed，直接返回 (feed_text, url)
      - 否则当作主页：解析 <link rel=alternate ...> 找 feed；找不到就探测常见路径。
    返回 (feed_text, feed_url) 或 (None, None)。
    """
    text, final, ctype = http_get(url)
    if text is None:
        return None, None
    if looks_like_feed(text, ctype):
        return text, final

    # 从 HTML <head> 找 <link rel="alternate" type="application/rss+xml|atom+xml" href=...>
    candidates = []
    for m in re.finditer(r"<link\b[^>]*>", text, re.I):
        tag = m.group(0)
        if "alternate" not in tag.lower():
            continue
        tlow = tag.lower()
        if ("application/rss+xml" in tlow or "application/atom+xml" in tlow
                or "application/feed+json" in tlow or "application/json" in tlow):
            hm = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
            if hm:
                candidates.append(urllib.parse.urljoin(final, hm.group(1).strip()))

    for c in candidates:
        ftext, _, fctype = http_get(c)   # 只取一次（原来误取了两次，多打一倍请求）
        if ftext and looks_like_feed(ftext, fctype):
            log(f"发现 feed（来自 <link>）：{c}")
            return ftext, c

    # 探测常见路径
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(final))
    for path in COMMON_FEED_PATHS:
        probe = base + path
        ptext, _, pctype = http_get(probe)
        if ptext and looks_like_feed(ptext, pctype):
            log(f"发现 feed（探测路径）：{probe}")
            return ptext, probe

    log(f"未能从 {url} 发现任何 feed（已试 <link> 与常见路径）。")
    return None, None


# ---------------------------------------------------------------------------
# Feed 解析 —— 统一产出 [{title, link, published(datetime|None), summary}]
# ---------------------------------------------------------------------------
def parse_feed(feed_text, feed_url):
    """优先 feedparser，否则 stdlib ElementTree。返回 (site_title, entries)。"""
    if HAVE_FEEDPARSER:
        return _parse_with_feedparser(feed_text, feed_url)
    return _parse_with_etree(feed_text, feed_url)


def _to_dt(*vals):
    """把各种日期串尽量解析成 datetime（带 tz 时转 naive UTC）；都失败返回 None。"""
    for v in vals:
        if not v:
            continue
        if isinstance(v, time.struct_time):
            try:
                return datetime.datetime.fromtimestamp(time.mktime(v))
            except Exception:
                continue
        s = str(v).strip()
        # RFC 822（RSS pubDate）
        try:
            dt = parsedate_to_datetime(s)
            if dt:
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            pass
        # ISO 8601（Atom）
        iso = s.replace("Z", "+00:00")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(iso, fmt)
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except Exception:
                continue
    return None


def _parse_with_feedparser(feed_text, feed_url):
    d = feedparser.parse(feed_text)
    site_title = ""
    try:
        site_title = (d.feed.get("title") or "").strip()
    except Exception:
        site_title = ""
    entries = []
    for e in getattr(d, "entries", []):
        link = e.get("link") or ""
        if not link:
            # Atom 有时把链接放在 links 列表里
            for l in e.get("links", []) or []:
                if l.get("rel") in (None, "alternate") and l.get("href"):
                    link = l["href"]
                    break
        title = (e.get("title") or "").strip()
        summary = e.get("summary") or e.get("description") or ""
        # 正文可能在 content 里
        if e.get("content"):
            try:
                summary = e["content"][0].get("value") or summary
            except Exception:
                pass
        pub = _to_dt(e.get("published_parsed"), e.get("updated_parsed"),
                     e.get("published"), e.get("updated"))
        author = ""
        try:
            author = (e.get("author") or "").strip()
        except Exception:
            author = ""
        entries.append({"title": title, "link": link, "published": pub,
                        "summary": summary, "author": author})
    return site_title, entries


def _localname(tag):
    """去掉命名空间，取本地标签名。"""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _findtext_local(elem, names):
    """在子元素里按本地名（忽略命名空间）找文本。"""
    want = set(names)
    for child in elem.iter():
        if _localname(child.tag) in want and (child.text and child.text.strip()):
            return child.text.strip()
    return ""


def _parse_with_etree(feed_text, feed_url):
    """纯标准库解析 RSS <item> 与 Atom <entry>，处理命名空间。"""
    try:
        # http_get 已把字节解码成 str。若仍带着原始的 <?xml ... encoding="gbk"?> 声明喂给 ET，
        # 会报 "multi-byte encodings are not supported"（中文 WordPress/博客常见 GBK/GB2312 声明）。
        # 解法：去掉声明里的 encoding 属性，直接按 str 解析。
        cleaned = re.sub(r'(<\?xml[^>]*?)\s+encoding\s*=\s*["\'][^"\']*["\']',
                         r'\1', feed_text, count=1, flags=re.I)
        root = ET.fromstring(cleaned)
    except Exception as e:
        log(f"XML 解析失败：{e}")
        return "", []

    entries = []
    site_title = ""

    # 站点标题：RSS 在 channel/title；Atom 在 feed/title
    for child in root.iter():
        if _localname(child.tag) == "title" and child.text and child.text.strip():
            site_title = child.text.strip()
            break

    # 收集所有 item / entry
    items = [el for el in root.iter() if _localname(el.tag) in ("item", "entry")]
    for it in items:
        title = ""
        link = ""
        summary = ""
        author = ""
        pubraw = ""

        for ch in list(it):
            ln = _localname(ch.tag)
            if ln == "title" and not title:
                title = (ch.text or "").strip()
            elif ln == "link":
                # RSS：link 文本即 URL；Atom：href 属性
                href = ch.get("href")
                rel = ch.get("rel")
                if href:
                    if rel in (None, "", "alternate") or not link:
                        link = href.strip()
                elif ch.text and ch.text.strip():
                    link = ch.text.strip()
            elif ln in ("pubDate", "published", "updated", "date") and not pubraw:
                pubraw = (ch.text or "").strip()
            elif ln in ("description", "summary") and not summary:
                summary = ch.text or ""
            elif ln in ("encoded", "content"):
                # content:encoded（RSS 全文）或 Atom content
                val = ch.text or ""
                if val and len(val) > len(summary):
                    summary = val
            elif ln in ("creator", "author") and not author:
                # dc:creator 文本，或 Atom author/name
                if ch.text and ch.text.strip():
                    author = ch.text.strip()
                else:
                    author = _findtext_local(ch, ["name"])

        pub = _to_dt(pubraw)
        if title or link:
            entries.append({"title": title, "link": link, "published": pub,
                            "summary": summary, "author": author})
    return site_title, entries


# ---------------------------------------------------------------------------
# 正文抽取 → markdown
# ---------------------------------------------------------------------------
def extract_article_markdown(article_url, fallback_summary=""):
    """
    重新抓文章 URL 抽正文（feed 常只给摘要）。
    优先 trafilatura（直出 markdown）→ markdownify（html→md）→ stdlib 轻量剥标签 → feed 摘要。
    返回 markdown 字符串（可能为空）。
    """
    html = None
    if article_url:
        html = http_get(article_url)[0]

    # 1) trafilatura：直接抽正文并输出 markdown
    if HAVE_TRAFILATURA and html:
        try:
            md = trafilatura.extract(html, output_format="markdown",
                                     include_links=True, include_images=False,
                                     favor_recall=True)
            if md and md.strip():
                return md.strip()
        except Exception as e:
            log(f"trafilatura 抽取失败，降级：{e}")

    # 2) markdownify：先粗暴框定正文区，再转 markdown
    if HAVE_MARKDOWNIFY and html:
        try:
            body_html = _rough_main_html(html)
            md = _md(body_html, heading_style="ATX")
            md = re.sub(r"\n{3,}", "\n\n", md).strip()
            if md:
                return md
        except Exception as e:
            log(f"markdownify 抽取失败，降级：{e}")

    # 3) stdlib 轻量抽取：剥 script/style/标签 → 纯文本
    if html:
        txt = _stdlib_html_to_text(html)
        if txt and len(txt) > 200:
            return txt

    # 4) 最后退回 feed 摘要（可能是 HTML，做一次降级清洗）
    if fallback_summary:
        if HAVE_MARKDOWNIFY:
            try:
                return re.sub(r"\n{3,}", "\n\n", _md(fallback_summary, heading_style="ATX")).strip()
            except Exception:
                pass
        return _stdlib_html_to_text(fallback_summary)
    return ""


def _rough_main_html(html):
    """粗略框定正文容器：优先 <article>，否则 <main>，否则去掉明显非正文区的 <body>。"""
    m = re.search(r"<article\b[^>]*>(.*?)</article>", html, re.I | re.S)
    if m:
        return m.group(1)
    m = re.search(r"<main\b[^>]*>(.*?)</main>", html, re.I | re.S)
    if m:
        return m.group(1)
    body = re.search(r"<body\b[^>]*>(.*?)</body>", html, re.I | re.S)
    chunk = body.group(1) if body else html
    # 去掉常见噪声块
    chunk = re.sub(r"<(script|style|nav|header|footer|aside|form)\b[^>]*>.*?</\1>",
                   "", chunk, flags=re.I | re.S)
    return chunk


def _stdlib_html_to_text(html):
    """纯标准库 html → 纯文本：去 script/style/注释，块级标签换行，剥标签，反转义实体。"""
    import html as _htmllib
    s = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    s = re.sub(r"<(script|style|nav|header|footer|aside|form)\b[^>]*>.*?</\1>",
               "", s, flags=re.I | re.S)
    # 块级元素转换行
    s = re.sub(r"</(p|div|h[1-6]|li|br|tr|section|article)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)            # 剥掉剩余标签
    s = _htmllib.unescape(s)                 # 反转义 &amp; 等
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------
def slugify(text):
    """安全文件名片段：保留中文，替换 / \\ : * ? \" < > | 和空白为 -，截断 ~60 字符。"""
    s = text or "post"
    s = re.sub(r'[/\\:*?"<>|]+', "-", s)
    s = re.sub(r"\s+", "-", s)
    s = s.strip("-")
    s = s[:60].strip("-")
    return s or "post"


def yaml_escape(val):
    """frontmatter 值简易转义：含特殊字符时用双引号包裹。"""
    v = ("" if val is None else str(val)).replace("\n", " ").strip()
    if v == "":
        return '""'
    if re.search(r'[:#\[\]{}",&*!|>%@`]', v) or v[0] in "-?" or v != v.strip():
        return '"' + v.replace('"', '\\"') + '"'
    return v


def existing_urls(dest_dir):
    """扫描 sources/blog/ 已有文件的 frontmatter，收集所有 url 进 set（去重用）。"""
    urls = set()
    if not os.path.isdir(dest_dir):
        return urls
    for name in os.listdir(dest_dir):
        if not name.endswith(".md"):
            continue
        path = os.path.join(dest_dir, name)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(4096)
        except Exception:
            continue
        # 仅在 frontmatter 区域里找 url:
        if head.startswith("---"):
            end = head.find("\n---", 3)
            block = head[:end] if end != -1 else head
        else:
            block = head
        m = re.search(r"^url:\s*(.+?)\s*$", block, re.M)
        if m:
            u = m.group(1).strip().strip('"').strip("'")
            if u:
                urls.add(u)
    return urls


def write_entry(dest_dir, today, channel, entry, body_md, dry_run=False):
    """写一篇文章到 sources/blog/<today>_<slug>.md（仅追加：已存在则跳过）。返回写入路径或 None。"""
    title = entry.get("title") or "untitled"
    url = entry.get("link") or ""
    pub = entry.get("published")
    pub_str = pub.strftime("%Y-%m-%d") if isinstance(pub, datetime.datetime) else ""

    slug = slugify(title)
    fname = f"{today}_{slug}.md"
    path = os.path.join(dest_dir, fname)

    # 仅追加：同名文件已存在则换一个带短哈希的名字，避免覆盖也避免撞名
    if os.path.exists(path):
        import hashlib
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:6]
        path = os.path.join(dest_dir, f"{today}_{slug}_{h}.md")
        if os.path.exists(path):
            log(f"跳过（目标已存在，仅追加）：{path}")
            return None

    fm_lines = [
        "---",
        "source: blog",
        f"channel: {yaml_escape(channel or 'blog')}",
        "type: article",
        f"captured: {today}",
        f"url: {yaml_escape(url)}",
        f"published: {yaml_escape(pub_str)}",
    ]
    if entry.get("author"):
        fm_lines.append(f"author: {yaml_escape(entry['author'])}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines)

    content = f"{fm}\n\n# {title}\n\n{body_md}\n"

    if dry_run:
        log(f"[dry-run] 将写入 {path}（{len(content)} 字节）")
        return path

    os.makedirs(dest_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"写入 {path}")
    return path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def resolve_feeds(argv_feeds):
    """CLI 参数优先；否则读 BLOG_FEEDS（逗号分隔）。返回 URL 列表。"""
    if argv_feeds:
        return [u.strip() for u in argv_feeds if u.strip()]
    raw = os.environ.get("BLOG_FEEDS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]


def main():
    # 启动即声明运行模式（哪些增强可用 / 是否降级）
    mode_bits = []
    mode_bits.append("feedparser" if HAVE_FEEDPARSER else "stdlib-xml")
    if HAVE_TRAFILATURA:
        mode_bits.append("trafilatura")
    elif HAVE_MARKDOWNIFY:
        mode_bits.append("markdownify")
    else:
        mode_bits.append("stdlib-extract")
    log(f"运行模式：{' + '.join(mode_bits)}")
    if not (HAVE_FEEDPARSER and HAVE_TRAFILATURA):
        log("提示：处于降级模式（正文/解析质量较低）。安装可选依赖以提升效果：")
        log("  pip install feedparser trafilatura markdownify")

    # 参数：所有非选项 argv 视为 feed/主页 URL
    argv_feeds = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv[1:]

    feeds = resolve_feeds(argv_feeds)
    if not feeds:
        log("没有任何 feed。请在 .env.local 设置 BLOG_FEEDS，或把 feed/主页 URL 作为参数传入。")
        return 2

    max_posts = int(os.environ.get("BLOG_MAX_POSTS", "20") or "20")
    since_days_raw = os.environ.get("BLOG_SINCE_DAYS", "").strip()
    since_days = int(since_days_raw) if since_days_raw.isdigit() else None
    cutoff = None
    if since_days is not None:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=since_days)

    # 落盘目录：脚本在 .claude/skills/blog/scripts/ → 仓库根上溯 4 层 → sources/blog
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.environ.get("WORKSPACE_ROOT") or os.path.abspath(
        os.path.join(here, "..", "..", "..", ".."))
    dest_dir = os.path.join(repo_root, "sources", "blog")
    log(f"落盘目录：{dest_dir}")

    seen_urls = existing_urls(dest_dir)
    log(f"已有 {len(seen_urls)} 条 url 记录（用于去重）。")

    total_written = 0
    for url in feeds:
        log(f"处理来源：{url}")
        feed_text, feed_url = discover_feed(url)
        if not feed_text:
            log(f"跳过（无 feed）：{url}")
            continue

        site_title, entries = parse_feed(feed_text, feed_url or url)
        log(f"feed《{site_title or '?'}》解析到 {len(entries)} 条；最多归档 {max_posts} 条。")

        written_for_feed = 0
        for entry in entries:
            if written_for_feed >= max_posts:
                break

            link = entry.get("link") or ""
            if not link:
                log("跳过（无链接）的一条。")
                continue

            # since-days 过滤
            pub = entry.get("published")
            if cutoff and isinstance(pub, datetime.datetime) and pub < cutoff:
                continue

            # url 去重
            if link in seen_urls:
                continue

            body_md = extract_article_markdown(link, entry.get("summary") or "")
            if not body_md:
                log(f"正文为空，仍记录元数据：{link}")
                body_md = "*（未能抽取正文，仅保留元数据。）*"

            path = write_entry(dest_dir, _today(), site_title or entry.get("author") or "blog",
                               entry, body_md, dry_run=dry_run)
            if path:
                seen_urls.add(link)
                written_for_feed += 1
                total_written += 1
            # 轻微限速，避免对同站点过快请求
            time.sleep(0.3)

        log(f"该来源写入 {written_for_feed} 篇。")

    log(f"完成：共写入 {total_written} 篇 → {dest_dir}/")
    return 0


def _today():
    return datetime.date.today().strftime("%Y-%m-%d")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("已中断。")
        sys.exit(130)
