#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯会议 REST API 归档客户端（标准库实现，零 pip 依赖）。

把企业版/商业版「自建应用」可见的会议录制，连同 AI 纪要 / 智能转写 / 摘要，
归档到 sources/tencent-meeting/<日期>_<主题>.md。

三步流程：
  1) GET /v1/records                       列录制（按时间窗分页）
  2) GET /v1/addresses/{record_file_id}    取下载地址 + AI 纪要/转写/摘要数组（地址约 5 分钟有效）
  3) GET /v1/records/transcripts/details   结构化逐字稿（可选，按段落/句子，带发言人）

签名：腾讯会议自建应用 AKSK 鉴权（TC3 风格 HMAC-SHA256，但「双重编码」：先 hex 再 base64）。
凭证全部来自环境变量（由 bash 包装脚本从 .env.local 注入），本文件不含任何密钥。

只读、仅追加：目标 markdown 已存在则跳过，绝不覆盖来源底稿。
"""

import base64
import hashlib
import hmac
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

API_HOST = "https://api.meeting.qq.com"  # 注意：是 api.meeting.qq.com，不是 qcloud


# ---------------------------------------------------------------------------
# 日志（统一走 stderr，stdout 留给可能的数据输出）
# ---------------------------------------------------------------------------
def log(msg):
    print("[tencent-meeting] {}".format(msg), file=sys.stderr)


def warn(msg):
    print("[tencent-meeting] WARN {}".format(msg), file=sys.stderr)


# ---------------------------------------------------------------------------
# 签名：TC3 风格 HMAC-SHA256，双重编码（hex → base64）。已验证，逐字使用。
# ---------------------------------------------------------------------------
def tc_sign(secret_id, secret_key, method, nonce, ts, uri, body=""):
    # 参与签名的 3 个请求头按字典序：X-TC-Key, X-TC-Nonce, X-TC-Timestamp
    header_string = "X-TC-Key={k}&X-TC-Nonce={n}&X-TC-Timestamp={t}".format(
        k=secret_id, n=nonce, t=ts
    )
    to_sign = "{m}\n{h}\n{u}\n{b}".format(m=method, h=header_string, u=uri, b=body)
    # 关键：先取 HMAC 的十六进制摘要，再对该 hex 字符串做 base64
    digest_hex = hmac.new(
        secret_key.encode(), to_sign.encode(), hashlib.sha256
    ).hexdigest()
    return base64.b64encode(digest_hex.encode()).decode()


# ---------------------------------------------------------------------------
# HTTP 请求：每次调用都重新生成 nonce / ts / 签名。
# 注意：用于签名的 uri 必须是「含 query string、且顺序与实际请求一致」的完整路径，
#       所以这里把 path 和 query 一次拼好，签名与请求复用同一个字符串，避免顺序不一致导致
#       "signature invalid"。
# ---------------------------------------------------------------------------
class TMeetingClient:
    def __init__(self, app_id, sdk_id, secret_id, secret_key, timeout=60):
        self.app_id = app_id
        self.sdk_id = sdk_id
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.timeout = timeout

    def _build_uri(self, path, params=None):
        """把 path + 有序 query 拼成一个字符串，签名与请求共用。"""
        if not params:
            return path
        # urlencode 会保持传入 (key, value) 列表的顺序；调用方用列表保证顺序稳定
        if isinstance(params, dict):
            items = list(params.items())
        else:
            items = list(params)
        # 过滤掉 None（但保留空字符串，部分接口要求传空参数占位）
        items = [(k, "" if v is None else str(v)) for k, v in items]
        qs = urllib.parse.urlencode(items)
        return "{}?{}".format(path, qs) if qs else path

    def get(self, path, params=None):
        """发起 GET 请求，返回解析后的 JSON dict（防御式，失败抛异常给上层处理）。"""
        uri = self._build_uri(path, params)  # 含 query，且只构造一次
        method = "GET"
        body = ""  # GET 的签名 body 为空字符串
        nonce = random.randint(10000, 99999999)
        ts = int(time.time())
        sig = tc_sign(self.secret_id, self.secret_key, method, nonce, ts, uri, body)

        url = API_HOST + uri
        headers = {
            "Content-Type": "application/json",
            "X-TC-Key": self.secret_id,
            "X-TC-Timestamp": str(ts),
            "X-TC-Nonce": str(nonce),
            "X-TC-Signature": sig,
            "AppId": self.app_id,
            "SdkId": self.sdk_id,
            "X-TC-Registered": "1",
        }
        req = urllib.request.Request(url, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "ignore")
        return _loads(raw)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _loads(s):
    """容错 JSON 解析：解析失败返回空 dict，绝不崩。"""
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {"_raw": v}
    except Exception:
        return {}


def _arr(d, *keys):
    """从 dict 里按多个候选 key 取出第一个非空 list，找不到返回 []。"""
    if not isinstance(d, dict):
        return []
    for k in keys:
        v = d.get(k)
        if isinstance(v, list):
            return v
    return []


def slugify(text):
    """把任意文本变成安全文件名片段：保留中文，替换路径分隔符/空白，截断 ~60 字符。"""
    text = text or ""
    # 替换 Windows/Unix 非法字符与空白
    text = re.sub(r'[/\\:*?"<>|]+', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-")
    return (text or "meeting")[:60]


def fetch_bytes(url, timeout=60):
    """抓取一个临时下载地址的字节内容（约 5 分钟有效）。失败返回 None，不抛。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tmeeting-archiver/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        warn("下载地址抓取失败（可能已过期）：{}".format(e))
        return None


def fmt_ts(v):
    """把 unix 秒（int 或字符串）格式化为可读时间；非数字原样返回。"""
    try:
        iv = int(v)
        if iv <= 0:
            return ""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(iv))
    except Exception:
        return str(v or "")


# ---------------------------------------------------------------------------
# 第 1 步：分页列出时间窗内的录制
# ---------------------------------------------------------------------------
def list_records(client, operator_id, operator_id_type, start_time, end_time, page_size=20):
    """返回 record_meetings 列表（已跨页聚合）。防御式：缺字段不崩，空结果返回 []。"""
    meetings = []
    page = 1
    while True:
        params = [
            ("operator_id", operator_id),
            ("operator_id_type", operator_id_type),
            ("start_time", start_time),
            ("end_time", end_time),
            ("page", page),
            ("page_size", page_size),
        ]
        data = client.get("/v1/records", params)
        batch = _arr(data, "record_meetings", "records")
        meetings.extend(batch)
        total_page = data.get("total_page") or data.get("total_pages") or 0
        try:
            total_page = int(total_page)
        except Exception:
            total_page = 0
        log("第 {} 页：{} 场录制{}".format(page, len(batch), "（共 {} 页）".format(total_page) if total_page else ""))
        # 翻页停止：本页空 / 不足一页（没有更多）/ 已达已知总页数 / 安全上限。
        # 有些版本不返回 total_page（默认 0）→ 不能据此停，靠「满页则可能还有」继续翻。
        if not batch or len(batch) < page_size:
            break
        if total_page and page >= total_page:
            break
        if page >= 500:
            log("已达分页安全上限 500，停止")
            break
        page += 1
    return meetings


# ---------------------------------------------------------------------------
# 第 2 步：取某个 record_file 的地址 + AI 纪要/转写/摘要数组
# ---------------------------------------------------------------------------
# AI 资源数组的字段名（不同版本可能并存，逐一尝试）
AI_ARRAY_KEYS = [
    ("meeting_summary", "会议摘要"),
    ("ai_meeting_transcripts", "AI 转写"),
    ("ai_minutes", "AI 纪要"),
    ("ai_topic_minutes", "AI 话题纪要"),
    ("ai_speaker_minutes", "AI 发言人纪要"),
    ("ai_ds_minutes", "AI 智能纪要"),
]

# 直接抓取正文的文本型文件类型（其余如 pdf/docx 仅记录链接，不内嵌正文）
TEXT_FILE_TYPES = {"txt", "htm", "html"}


def get_address(client, record_file_id, operator_id, operator_id_type):
    """取下载地址 + AI 资源。返回原始 dict（容错）。"""
    params = [
        ("operator_id", operator_id),
        ("operator_id_type", operator_id_type),
    ]
    return client.get("/v1/addresses/{}".format(record_file_id), params)


def collect_ai_sections(addr):
    """
    从 addresses 返回里收集各类 AI 资源，立即抓取文本型内容（5 分钟内）。
    返回 [(标题, 文件类型, 正文文本或None, 下载链接), ...]
    """
    sections = []
    for key, label in AI_ARRAY_KEYS:
        for item in _arr(addr, key):
            if not isinstance(item, dict):
                continue
            file_type = (item.get("file_type") or item.get("type") or "").lower()
            dl = item.get("download_address") or item.get("download_url") or ""
            text = None
            if file_type in TEXT_FILE_TYPES and dl:
                # 文本型：立刻抓取（地址约 5 分钟过期）
                raw = fetch_bytes(dl)
                if raw is not None:
                    text = raw.decode("utf-8", "ignore")
                    if file_type in ("htm", "html"):
                        text = strip_html(text)
            sections.append((label, file_type or "?", text, dl))
    return sections


def strip_html(html):
    """极简 HTML → 文本：去标签、解实体、压空行。避免引入第三方依赖。"""
    if not html:
        return ""
    # 去掉 script/style
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html)
    # 块级标签换成换行
    html = re.sub(r"(?i)<(br|/p|/div|/li|/tr|/h[1-6])\s*>", "\n", html)
    # 去掉其余标签
    text = re.sub(r"(?s)<[^>]+>", "", html)
    # 常见实体
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(a, b)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 第 3 步（可选）：结构化逐字稿
# ---------------------------------------------------------------------------
def get_transcript_details(client, record_file_id, meeting_id, operator_id, operator_id_type, limit=""):
    """取结构化逐字稿。返回 dict（容错）。失败上层 catch。"""
    params = [
        ("record_file_id", record_file_id),
        ("meeting_id", meeting_id),
        ("operator_id", operator_id),
        ("operator_id_type", operator_id_type),
        ("pid", ""),       # 分页游标，首页留空
        ("limit", limit),  # 留空走服务端默认
    ]
    return client.get("/v1/records/transcripts/details", params)


def render_transcript(details):
    """把逐字稿结构（段落/句子，带发言人）渲染成 markdown 文本。容错。"""
    if not isinstance(details, dict):
        return ""
    paragraphs = _arr(details, "minutes", "paragraphs", "transcripts", "details")
    lines = []
    for para in paragraphs:
        if not isinstance(para, dict):
            continue
        speaker = (para.get("username") or para.get("speaker")
                   or para.get("userid") or para.get("user_id") or "")
        # 句子可能在 sentences/contents 里，也可能直接是 content
        sents = _arr(para, "sentences", "contents")
        if sents:
            texts = []
            for s in sents:
                if isinstance(s, dict):
                    texts.append(s.get("text") or s.get("content") or "")
                else:
                    texts.append(str(s))
            content = "".join(texts).strip()
        else:
            content = (para.get("content") or para.get("text") or "").strip()
        if not content:
            continue
        if speaker:
            lines.append("**{}**：{}".format(speaker, content))
        else:
            lines.append(content)
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# 组装并落盘单场录制的 markdown
# ---------------------------------------------------------------------------
def write_meeting_md(dest_dir, meeting, record_file, addr, transcript_md):
    """
    把一个 record_file 写成一篇 markdown。已存在则跳过（仅追加，不覆盖底稿）。
    返回 (path, written: bool)。
    """
    meeting_id = meeting.get("meeting_id") or meeting.get("meeting_code") or ""
    subject = meeting.get("subject") or meeting.get("meeting_topic") or "未命名会议"
    rfid = record_file.get("record_file_id") or ""
    start = record_file.get("record_start_time") or record_file.get("start_time") or ""
    end = record_file.get("record_end_time") or record_file.get("end_time") or ""

    # 文件名日期取录制开始时间（unix 秒）；缺失则用今天
    date_str = ""
    try:
        if start:
            date_str = time.strftime("%Y-%m-%d", time.localtime(int(start)))
    except Exception:
        date_str = ""
    if not date_str:
        date_str = time.strftime("%Y-%m-%d")

    # 文件名要「跨次运行确定」，否则重跑同一录制会落到不同文件名、破坏仅追加幂等。
    # 策略：
    #   - 无 rfid（罕见）：用 <date>_<slug>.md。
    #   - 有 rfid：先尝试简洁的 <date>_<slug>.md；若该文件已被「别的录制」占用，
    #     则退到 <date>_<slug>_<rfid>.md（用「完整」rfid，避免不同录制末位相同而撞名覆盖）。
    #     判定是否已归档按 frontmatter 里 record_file_id「整行」匹配（防止前缀子串误判跳过）。
    slug = slugify(subject)
    base_path = os.path.join(dest_dir, "{}_{}.md".format(date_str, slug))

    def _belongs_to_this_rfid(p):
        # 已存在文件的 frontmatter 若有「整行」相同的 record_file_id，即本录制已归档。
        try:
            with open(p, encoding="utf-8") as fh:
                head = fh.read(2048)
        except Exception:
            return False
        target = "record_file_id: {}".format(rfid)
        return any(ln.strip() == target for ln in head.splitlines())

    if not rfid:
        # 无法用 rfid 去重：base 已存在就跳过
        if os.path.exists(base_path):
            return base_path, False
        path = base_path
    else:
        suffixed_path = os.path.join(dest_dir, "{}_{}_{}.md".format(date_str, slug, slugify(rfid)))
        # 本录制可能落在 base 名或 suffixed 名中任意一处 → 命中即跳过（幂等）
        if os.path.exists(base_path) and _belongs_to_this_rfid(base_path):
            return base_path, False
        if os.path.exists(suffixed_path) and _belongs_to_this_rfid(suffixed_path):
            return suffixed_path, False
        # 首次写：base 空着用 base；否则用带完整 rfid 的后缀名；仍冲突（极罕见）追加序号，
        # 绝不覆盖「别的录制」已有底稿（CLAUDE.md 金律：sources 只追加不改写）。
        if not os.path.exists(base_path):
            path = base_path
        else:
            path = suffixed_path
            i = 2
            while os.path.exists(path) and not _belongs_to_this_rfid(path):
                path = os.path.join(dest_dir, "{}_{}_{}-{}.md".format(date_str, slug, slugify(rfid), i))
                i += 1

    os.makedirs(dest_dir, exist_ok=True)

    # ---- frontmatter ----
    fm_lines = [
        "source: tencent-meeting",
        "channel: {}".format(subject),
        "type: meeting",
        "captured: {}".format(time.strftime("%Y-%m-%d")),
        "meeting_id: {}".format(meeting_id),
        "record_file_id: {}".format(rfid),
    ]
    if start:
        fm_lines.append("record_start: {}".format(fmt_ts(start)))
    if end:
        fm_lines.append("record_end: {}".format(fmt_ts(end)))

    # ---- body ----
    body = ["# {}".format(subject), ""]
    body.append("- 会议 ID：`{}`".format(meeting_id))
    body.append("- 录制文件 ID：`{}`".format(rfid))
    if start:
        body.append("- 录制开始：{}".format(fmt_ts(start)))
    if end:
        body.append("- 录制结束：{}".format(fmt_ts(end)))
    body.append("")

    # 视频/音频地址（约 5 分钟有效，仅作记录，不下载大文件）
    view = addr.get("view_address") or ""
    download = addr.get("download_address") or ""
    audio = addr.get("audio_address") or ""
    if view or download or audio:
        body.append("> 以下地址约 5 分钟有效，过期需重新拉取。")
        if view:
            body.append("> - 在线观看：{}".format(view))
        if download:
            body.append("> - 录制下载：{}".format(download))
        if audio:
            body.append("> - 音频下载：{}".format(audio))
        body.append("")

    # AI 资源各小节
    sections = collect_ai_sections(addr)
    if sections:
        body.append("## AI 纪要 / 转写 / 摘要")
        body.append("")
        for label, ftype, text, dl in sections:
            body.append("### {}（{}）".format(label, ftype))
            if text:
                body.append("")
                body.append(text)
            elif ftype in ("pdf", "docx", "doc"):
                body.append("")
                body.append("（{} 文件，未内嵌正文。下载链接 5 分钟有效：{}）".format(ftype, dl or "无"))
            else:
                body.append("")
                body.append("（无法获取正文，可能地址已过期。下载链接：{}）".format(dl or "无"))
            body.append("")
    else:
        body.append("（本场录制无 AI 纪要/转写/摘要，或当前账号无权限获取。）")
        body.append("")

    # 结构化逐字稿
    if transcript_md:
        body.append("## 结构化逐字稿")
        body.append("")
        body.append(transcript_md)
        body.append("")

    content = "---\n{}\n---\n\n{}\n".format("\n".join(fm_lines), "\n".join(body))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path, True


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    # 凭证从环境变量读（由 bash 包装脚本注入），缺一不可的硬性 4 项 + operator
    app_id = os.environ.get("TENCENT_MEETING_APP_ID", "").strip()
    sdk_id = os.environ.get("TENCENT_MEETING_SDK_ID", "").strip()
    secret_id = os.environ.get("TENCENT_MEETING_SECRET_ID", "").strip()
    secret_key = os.environ.get("TENCENT_MEETING_SECRET_KEY", "").strip()
    operator_id = os.environ.get("TENCENT_MEETING_OPERATOR_ID", "").strip()
    operator_id_type = os.environ.get("TENCENT_MEETING_OPERATOR_ID_TYPE", "1").strip() or "1"

    missing = [n for n, v in (
        ("TENCENT_MEETING_APP_ID", app_id),
        ("TENCENT_MEETING_SDK_ID", sdk_id),
        ("TENCENT_MEETING_SECRET_ID", secret_id),
        ("TENCENT_MEETING_SECRET_KEY", secret_key),
        ("TENCENT_MEETING_OPERATOR_ID", operator_id),
    ) if not v]
    if missing:
        warn("缺少必需凭证：{}。请在 .env.local 配置。".format(", ".join(missing)))
        sys.exit(2)

    # 时间窗：最近 N 天（默认 7，硬上限 31）
    try:
        since_days = int(os.environ.get("TENCENT_MEETING_SINCE_DAYS", "7"))
    except Exception:
        since_days = 7
    if since_days < 1:
        since_days = 1
    if since_days > 31:
        warn("SINCE_DAYS={} 超过 31 天硬上限，已收敛为 31。".format(since_days))
        since_days = 31

    now = int(time.time())
    start_time = now - since_days * 86400
    end_time = now

    # 落盘目录：sources/tencent-meeting/（相对仓库根；包装脚本会先 cd 到根）
    dest_dir = os.environ.get(
        "TENCENT_MEETING_DEST", "sources/tencent-meeting"
    )

    client = TMeetingClient(app_id, sdk_id, secret_id, secret_key)

    log("时间窗：{} ~ {}（最近 {} 天）".format(
        fmt_ts(start_time), fmt_ts(end_time), since_days))

    # 第 1 步：列录制
    try:
        meetings = list_records(client, operator_id, operator_id_type, start_time, end_time)
    except Exception as e:
        warn("列录制失败：{}".format(e))
        warn("常见原因：签名无效（检查 SECRET_ID/KEY）、operator 非会议创建者且无录制管理权限、"
             "或 2026-01-16 后新建的应用需额外携带 STS-Token（见 SKILL.md 说明）。")
        sys.exit(1)

    if not meetings:
        log("时间窗内没有可见的录制。结束。")
        return

    log("共 {} 场录制，开始处理各录制文件……".format(len(meetings)))

    written = 0
    skipped = 0
    for meeting in meetings:
        if not isinstance(meeting, dict):
            continue
        meeting_id = meeting.get("meeting_id") or meeting.get("meeting_code") or ""
        subject = meeting.get("subject") or meeting.get("meeting_topic") or "未命名会议"
        record_files = _arr(meeting, "record_files")
        if not record_files:
            log("「{}」无 record_files，跳过。".format(subject))
            continue

        for rf in record_files:
            if not isinstance(rf, dict):
                continue
            rfid = rf.get("record_file_id") or ""
            if not rfid:
                continue

            # 第 2 步：取地址 + AI 资源（文本型立即抓取）
            try:
                addr = get_address(client, rfid, operator_id, operator_id_type)
            except Exception as e:
                warn("取地址失败（record_file_id={}）：{}".format(rfid, e))
                addr = {}

            # 第 3 步（可选）：结构化逐字稿
            transcript_md = ""
            try:
                details = get_transcript_details(
                    client, rfid, meeting_id, operator_id, operator_id_type)
                transcript_md = render_transcript(details)
            except Exception as e:
                warn("逐字稿获取失败（record_file_id={}）：{}（已跳过逐字稿）".format(rfid, e))

            # 落盘
            try:
                path, did = write_meeting_md(dest_dir, meeting, rf, addr, transcript_md)
                if did:
                    log("写入 {}".format(path))
                    written += 1
                else:
                    log("已存在，跳过 {}".format(path))
                    skipped += 1
            except Exception as e:
                warn("写盘失败（{}）：{}".format(subject, e))

    log("完成：新写 {} 篇，跳过 {} 篇。产物在 {}/".format(written, skipped, dest_dir))


if __name__ == "__main__":
    main()
