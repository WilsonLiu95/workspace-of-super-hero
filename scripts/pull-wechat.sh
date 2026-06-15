#!/usr/bin/env bash
# 拉微信 → sources/wechat/
# 工具：chatlog（github.com/sjzar/chatlog）。微信无官方 API，chatlog 通过本地 HTTP 服务暴露聊天记录。
#
# 前置（一次性，按 chatlog 文档）：保持微信登录 → `chatlog key` / `chatlog decrypt` → `chatlog server`
# 之后本脚本查询其本地 HTTP API。
#
# 环境变量：
#   CHATLOG_BASE_URL    chatlog 服务地址（默认 http://127.0.0.1:5030）
#   WECHAT_SINCE_DAYS   拉最近 N 天（默认 1）
#   WECHAT_MAX_SESSIONS 最多处理多少个会话（默认 50）
SCRIPT_NAME="pull-wechat"
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_local_env

BASE="${CHATLOG_BASE_URL:-http://127.0.0.1:5030}"
SINCE_DAYS="${WECHAT_SINCE_DAYS:-1}"
MAX="${WECHAT_MAX_SESSIONS:-50}"
DEST="$SOURCES_DIR/wechat"

have python3 || die "需要 python3。"
have chatlog || warn "未在 PATH 找到 chatlog 二进制（仍会尝试访问 ${BASE}）。安装见 github.com/sjzar/chatlog。"
curl -fsS "$BASE/api/v1/session" -o /dev/null 2>/dev/null \
  || die "连不上 chatlog 服务 ${BASE}。请先按 chatlog 文档完成 key/decrypt 并运行 'chatlog server'。"

if date -v-1d >/dev/null 2>&1; then START=$(date -v-"${SINCE_DAYS}"d +%F); else START=$(date -d "-${SINCE_DAYS} days" +%F); fi
RANGE="${START}~${TODAY}"
log "服务=$BASE 窗口=$RANGE 上限=${MAX}个会话"

sessions="$(curl -fsS "$BASE/api/v1/session?format=json" 2>/dev/null || true)"
[ -n "$sessions" ] || die "拉取会话列表失败。"

printf '%s' "$sessions" | python3 - "$BASE" "$DEST" "$RANGE" "$MAX" "$TODAY" <<'PY'
import json, os, re, sys, urllib.parse, urllib.request
base, dest, time_range, max_n, today = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
def load(s):
    try: return json.loads(s)
    except Exception: return {}
def get(url):
    try:
        with urllib.request.urlopen(url, timeout=120) as r: return r.read().decode("utf-8","ignore")
    except Exception: return ""
raw = load(sys.stdin.read())
sess = raw if isinstance(raw, list) else (raw.get("items") or raw.get("sessions") or raw.get("data") or [])
def slug(t): return (re.sub(r'[\\/:*?"<>|]+', "-", re.sub(r"\s+", "-", t or "")).strip("-") or "chat")[:50]
os.makedirs(dest, exist_ok=True)
n = 0
for s in sess:
    if n >= max_n: break
    talker = s.get("userName") or s.get("talker") or s.get("wxid") or ""
    name   = s.get("nickName") or s.get("displayName") or s.get("remark") or talker
    if not talker: continue
    q = urllib.parse.urlencode({"time": time_range, "talker": talker, "format": "json"})
    body = load(get(f"{base}/api/v1/chatlog?{q}"))
    msgs = body if isinstance(body, list) else (body.get("items") or body.get("data") or [])
    if not msgs: continue
    lines = []
    for m in msgs:
        who = m.get("senderName") or m.get("nickName") or m.get("sender") or ("我" if m.get("isSelf") else "?")
        content = m.get("content") or m.get("text") or ""
        t = m.get("time") or m.get("createTime") or ""
        lines.append(f"**{who}** {t}\n\n{content}\n")
    is_group = bool(s.get("isChatRoom") or str(talker).endswith("@chatroom"))
    path = os.path.join(dest, f"{today}_{slug(name)}.md")
    fm = (f"source: wechat\nchannel: {name}\ntype: {'group' if is_group else 'dm'}\n"
          f"captured: {today}\ntalker: {talker}")
    with open(path, "w") as f:
        f.write(f"---\n{fm}\n---\n\n# {name}\n\n" + "\n".join(lines) + "\n")
    print(f"[pull-wechat] 写入 {path}", file=sys.stderr)
    n += 1
print(f"[pull-wechat] 完成，处理 {n} 个会话", file=sys.stderr)
PY

log "完成。产物在 $DEST/"
