#!/usr/bin/env bash
# 拉 Get笔记（得到/Biji）→ sources/getnote/
# 工具：Biji OpenAPI 客户端 scripts/lib/get_biji.py（只从 env 读凭证）。
#
# 环境变量（见 skills/get-biji）：
#   GET_BIJI_API_KEY          必需
#   GET_BIJI_CLIENT_ID        notes list 必需
#   GET_BIJI_DEFAULT_TOPIC_ID 可选
#   GETNOTE_SINCE_ID          增量起点，默认 0（全量）
SCRIPT_NAME="pull-getnote"
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_local_env

[ -n "${GET_BIJI_API_KEY:-}" ]  || die "缺 GET_BIJI_API_KEY（见 skills/get-biji）。"
[ -n "${GET_BIJI_CLIENT_ID:-}" ] || die "缺 GET_BIJI_CLIENT_ID（notes list 必需）。"
have python3 || die "需要 python3。"

DEST="$SOURCES_DIR/getnote"
SINCE_ID="${GETNOTE_SINCE_ID:-0}"
CLIENT="$(dirname "${BASH_SOURCE[0]}")/lib/get_biji.py"

log "拉取笔记列表 since-id=$SINCE_ID"
notes_json="$(python3 "$CLIENT" notes list --since-id "$SINCE_ID" 2>/dev/null || true)"
[ -n "$notes_json" ] || die "笔记列表为空或接口失败（检查 GET_BIJI_API_KEY/CLIENT_ID，401/403 多为凭证问题）。"

printf '%s' "$notes_json" | python3 - "$DEST" "$TODAY" <<'PY'
import json, os, re, sys
dest, today = sys.argv[1], sys.argv[2]
def load(s):
    try: return json.loads(s)
    except Exception: return {}
raw = load(sys.stdin.read())
notes = raw if isinstance(raw, list) else (raw.get("notes") or raw.get("list") or raw.get("data") or raw.get("items") or [])
def slug(t): return (re.sub(r'[\\/:*?"<>|]+', "-", re.sub(r"\s+", "-", t or "")).strip("-") or "note")[:50]
os.makedirs(dest, exist_ok=True)
n = 0
for note in notes:
    nid = str(note.get("id") or note.get("note_id") or note.get("resource_id") or n)
    text = note.get("content") or note.get("text") or note.get("title") or ""
    created = note.get("created_at") or note.get("create_time") or today
    title = (text.strip().splitlines() or ["note"])[0][:40]
    path = os.path.join(dest, f"{today}_{nid}_{slug(title)}.md")
    fm = f"source: getnote\nchannel: 得到/Biji\ntype: note\ncaptured: {today}\nnote_id: {nid}"
    with open(path, "w") as f:
        f.write(f"---\n{fm}\n---\n\n{text}\n")
    n += 1
print(f"[pull-getnote] 写入 {n} 条笔记到 {dest}", file=sys.stderr)
PY

log "完成。产物在 $DEST/"
