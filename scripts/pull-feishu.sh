#!/usr/bin/env bash
# 拉飞书 → sources/feishu/<租户>/{dm,groups}/
# 工具：官方 lark-cli（@larksuite/cli）。凭证由 lark-cli 管理（~/.lark-cli），不在本仓库。
#
# 用法：
#   FEISHU_TENANT=mycorp FEISHU_SINCE_DAYS=1 scripts/pull-feishu.sh
# 环境变量：
#   FEISHU_TENANT      落盘用的租户目录名（默认 default）
#   FEISHU_SINCE_DAYS  只拉最近 N 天的消息（默认 1）
#   FEISHU_MAX_CHATS   最多处理多少个会话（默认 50，防止首次全量过大）
#
# 说明：sources 是"原始数据"，这里只做轻量落盘；精细解析/合成交给 Agent。
SCRIPT_NAME="pull-feishu"
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_local_env

have lark-cli || die "未安装 lark-cli。请先 'npm i -g @larksuite/cli'（见 .claude/skills/feishu-cli）。"
lark-cli auth status >/dev/null 2>&1 || die "lark-cli 未登录。请先 'lark-cli config init' + 'lark-cli auth login'。"

TENANT="${FEISHU_TENANT:-default}"
SINCE_DAYS="${FEISHU_SINCE_DAYS:-1}"
MAX_CHATS="${FEISHU_MAX_CHATS:-50}"
DEST="$SOURCES_DIR/feishu/$TENANT"

# 时间窗口（秒级 epoch），lark-cli 多数接口用秒
if date -v-1d >/dev/null 2>&1; then START_TS=$(date -v-"${SINCE_DAYS}"d +%s); else START_TS=$(date -d "-${SINCE_DAYS} days" +%s); fi
END_TS=$(date +%s)

log "租户=$TENANT 窗口=最近${SINCE_DAYS}天 上限=${MAX_CHATS}个会话"

# 1) 列出我所在的会话（拿 chat_id / 名称 / 类型）
chats_json="$(lark-cli im +chat-list --as user --page-all --format json 2>/dev/null || true)"
[ -n "$chats_json" ] || die "拉取会话列表为空（检查 lark-cli 权限/登录）。"

# 2) 遍历会话，拉时间窗口内消息，落到 dm/ 或 groups/。用 python 做 JSON→markdown（防御式解析）。
printf '%s' "$chats_json" | python3 - "$DEST" "$START_TS" "$END_TS" "$MAX_CHATS" "$TENANT" "$TODAY" <<'PY'
import json, os, subprocess, sys, re
dest, start_ts, end_ts, max_chats, tenant, today = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]

def load(s):
    try: return json.loads(s)
    except Exception: return {}

raw = load(sys.stdin.read())
# lark-cli 返回结构因版本而异：尽量从常见位置取列表
items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("data") or raw.get("chats") or [])
def slug(t): return (re.sub(r'[\\/:*?"<>|]+', "-", re.sub(r"\s+", "-", t or "")).strip("-") or "untitled")[:60]

count = 0
for ch in items:
    if count >= max_chats: break
    chat_id = ch.get("chat_id") or ch.get("id") or ""
    name    = ch.get("name") or ch.get("title") or chat_id
    ctype   = ch.get("chat_type") or ch.get("type") or "group"
    if not chat_id: continue
    kind = "dm" if ctype in ("p2p", "dm", "single") else "groups"
    # 拉该会话窗口内消息
    params = json.dumps({"chat_id": chat_id, "start_time": start_ts, "end_time": end_ts})
    try:
        out = subprocess.run(["lark-cli","im","+chat-messages-list","--as","user",
                              "--params",params,"--page-all","--format","json"],
                             capture_output=True, text=True, timeout=120)
        msgs = load(out.stdout)
    except Exception as e:
        msgs = {}
    mlist = msgs if isinstance(msgs, list) else (msgs.get("items") or msgs.get("data") or [])
    if not mlist:  # 窗口内没消息就跳过，不建空文件
        continue
    lines = []
    for m in mlist:
        sender = (m.get("sender") or {}).get("name") if isinstance(m.get("sender"), dict) else m.get("sender") or m.get("sender_id") or "?"
        body   = m.get("text") or m.get("content") or json.dumps(m.get("body", ""), ensure_ascii=False)
        ts     = m.get("create_time") or m.get("time") or ""
        lines.append(f"**{sender}** {ts}\n\n{body}\n")
    d = os.path.join(dest, kind); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{today}_{slug(name)}.md")
    fm = (f"source: feishu\ntenant: {tenant}\nchannel: {name}\n"
          f"type: {'dm' if kind=='dm' else 'group'}\ncaptured: {today}\nchat_id: {chat_id}")
    with open(path, "w") as f:
        f.write(f"---\n{fm}\n---\n\n# {name}\n\n" + "\n".join(lines) + "\n")
    print(f"[pull-feishu] 写入 {path}", file=sys.stderr)
    count += 1
print(f"[pull-feishu] 完成，处理 {count} 个会话", file=sys.stderr)
PY

log "完成。产物在 $DEST/（注意：sources 默认不进 git，见根 .gitignore）"
