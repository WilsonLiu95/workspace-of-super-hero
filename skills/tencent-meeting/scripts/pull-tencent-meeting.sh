#!/usr/bin/env bash
# 腾讯会议归档（个人版）—— 用腾讯官方 tmeet CLI（OAuth 扫码登录，零密钥）。
#
# 个人版没有企业自建应用 AKSK，走 `tmeet auth login` 的 OAuth 即可；本脚本把时间窗内的录制
# 连同 AI 智能纪要 / 逐字稿可用性 归档到 sources/tencent-meeting/（带 frontmatter，仅追加）。
#
# 自包含技能：不依赖仓库顶层 scripts/lib/common.sh。
# 依赖：tmeet（npm i -g @tencentcloud/tmeet → tmeet auth login）、python3。
# 环境变量（可写进仓库根 .env.local；均可选）：
#   TMEET_SINCE_DAYS   拉最近 N 天录制（默认 30）
#   TENANT             多账号：在 .env.local 之上叠加 .env.<TENANT>.local
set -euo pipefail
SCRIPT_NAME="pull-tencent-meeting"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"   # -P 解析符号链接（.claude/skills -> ../skills）
ROOT="$(cd "$HERE/../../.." && pwd -P)"  # skills/tencent-meeting/scripts → 仓库根（符号链接已解析）
cd "$ROOT"
export PATH="$HOME/.npm-global/bin:$PATH"

log(){ printf '[tmeet] %s\n' "$*" >&2; }
die(){ printf '[tmeet] ERROR %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

# 可选加载本地配置（个人版凭证由 tmeet 自管，这里只读 TMEET_SINCE_DAYS 等）
[ -f "$ROOT/.env.local" ] && { set -a; . "$ROOT/.env.local"; set +a; log "已加载 .env.local"; }
[ -n "${TENANT:-}" ] && [ -f "$ROOT/.env.$TENANT.local" ] && { set -a; . "$ROOT/.env.$TENANT.local"; set +a; }

have tmeet    || die "未找到 tmeet。安装：npm i -g @tencentcloud/tmeet，然后 tmeet auth login 扫码登录。"
have python3  || die "需要 python3。"
tmeet auth status >/dev/null 2>&1 || die "tmeet 未登录。请在终端跑：tmeet auth login（扫码授权个人版），再重试。"

DAYS="${TMEET_SINCE_DAYS:-30}"
if date -v-1d >/dev/null 2>&1; then START="$(date -v-"${DAYS}"d +%Y-%m-%dT00:00+08:00)"
else START="$(date -d "-${DAYS} days" +%Y-%m-%dT00:00+08:00)"; fi
END="$(date +%Y-%m-%dT23:59+08:00)"
DEST="$ROOT/sources/tencent-meeting"
mkdir -p "$DEST"
log "登录态 OK; 窗口 ${START} .. ${END}; 产物 -> ${DEST}/"

LIST="$(tmeet record list --start "$START" --end "$END" --page-size 30 2>/dev/null || true)"
[ -n "$LIST" ] || die "拉取录制列表失败（检查登录态/时间窗）。"

LIST_JSON="$LIST" TMEET_BIN="$(command -v tmeet)" DEST="$DEST" python3 - <<'PY'
import json, os, re, subprocess, sys
dest = os.environ["DEST"]; tmeet = os.environ["TMEET_BIN"]

def run(args):
    """调 tmeet 子命令并解析 JSON；任何异常都返回空 dict（防御式）。"""
    try:
        out = subprocess.run([tmeet, *args], capture_output=True, text=True, timeout=120)
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except Exception:
        return {}

def slug(t):
    t = re.sub(r'^转写_', '', t or '')
    return (re.sub(r'[\\/:*?"<>|]+', "-", re.sub(r"\s+", "-", t)).strip("-") or "meeting")[:50]

raw = json.loads(os.environ["LIST_JSON"])
meetings = (raw.get("data") or {}).get("record_meetings") or []

# 同一会议常拆成「云录制 / 文字转写」多条，按 meeting_id 归并为一篇
groups = {}
for m in meetings:
    groups.setdefault(m.get("meeting_id") or m.get("meeting_record_id"), []).append(m)

n = 0
for mid, items in groups.items():
    subj = next((it.get("subject") for it in items
                 if it.get("subject") and not it.get("subject", "").startswith("转写_")), None) \
           or re.sub(r'^转写_', '', (items[0].get("subject") or "会议"))
    starts = sorted(it.get("media_start_time") for it in items if it.get("media_start_time"))
    day = starts[0][:10] if starts else ""
    code = items[0].get("meeting_code") or ""

    files = []
    for it in items:
        for rf in (it.get("record_files") or []):
            rf["_record_type"] = it.get("record_type")
            files.append(rf)

    # AI 智能纪要：在任一 record_file 上取到非空 minute 即用
    minute_txt = todo_txt = ""
    for rf in files:
        fid = rf.get("record_file_id")
        if not fid:
            continue
        mm = ((run(["record", "smart-minutes", "--record-file-id", fid]).get("data") or {})
              .get("meeting_minute") or {})
        if mm.get("minute"):
            minute_txt, todo_txt = mm["minute"], mm.get("todo", "") or ""
            break

    # 逐字稿段落数（paragraphs 接口只给时间轴，不给正文）
    para_count = 0
    for rf in files:
        fid = rf.get("record_file_id")
        if not fid:
            continue
        pids = (run(["record", "transcript-paragraphs", "--record-file-id", fid,
                     "--meeting-id", str(mid)]).get("data") or {}).get("pids") or []
        if pids:
            para_count = len(pids)
            break

    fname = f"{day}_{slug(subj)}.md" if day else f"{slug(subj)}_{mid}.md"
    path = os.path.join(dest, fname)
    if os.path.exists(path):
        print(f"[tmeet] 已存在，跳过（仅追加）：{path}", file=sys.stderr)
        continue

    fm = ("---\n"
          "source: tencent-meeting\n"
          "edition: personal\n"
          f"channel: {subj}\n"
          "type: meeting\n"
          f"captured: {day}\n"
          f"meeting_id: {mid}\n"
          f"meeting_code: {code}\n"
          f"record_start: {starts[0] if starts else ''}\n"
          "---\n")
    body = [f"# {subj}", "",
            f"会议ID：{mid}　会议号：{code}　开始：{starts[0] if starts else '—'}", "",
            "## 录制文件"]
    for rf in files:
        body.append(f"- [{rf.get('_record_type', '录制')}] "
                    f"{rf.get('sharing_url', '(无链接)')}  ·  record_file_id `{rf.get('record_file_id', '')}`")
    body.append("")
    if minute_txt:
        body += ["## AI 智能纪要", "", minute_txt, ""]
        if todo_txt.strip():
            body += ["### 待办", "", todo_txt, ""]
    else:
        body += ["## AI 智能纪要", "", "（该录制暂无智能纪要，或未开通）", ""]
    body += ["## 逐字稿", "",
             (f"共 {para_count} 段（带时间轴）。完整文本按需获取："
              "`tmeet record transcript-paragraphs --record-file-id <id>`。"
              if para_count else "（未获取到逐字稿）"), ""]

    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + "\n" + "\n".join(body) + "\n")
    print(f"[tmeet] 写入 {path}", file=sys.stderr)
    n += 1

print(f"[tmeet] 完成，写入 {n} 篇会议归档（共 {len(groups)} 个会议组）。", file=sys.stderr)
PY
log "完成。产物在 ${DEST}/"
