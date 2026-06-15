#!/usr/bin/env python3
"""把 lark-cli 的会话列表(JSON via stdin) + 逐会话消息，落成 markdown 到 sources/feishu/<租户>/。

argv: <dest_dir> <start_ts> <end_ts> <max_chats> <tenant> <today>
假定调用前已 `lark-cli profile use <对应租户>`（多租户时由 pull-feishu.sh 负责切换）。
防御式解析：lark-cli 返回结构因版本而异，字段对不上时按需微调。
"""
import json, os, subprocess, sys, re

dest, start_ts, end_ts, max_chats, tenant, today = (
    sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]
)


def load(s):
    try:
        return json.loads(s)
    except Exception:
        return {}


def slug(t):
    return (re.sub(r'[\\/:*?"<>|]+', "-", re.sub(r"\s+", "-", t or "")).strip("-") or "untitled")[:60]


raw = load(sys.stdin.read())
items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("data") or raw.get("chats") or [])

count = 0
for ch in items:
    if count >= max_chats:
        break
    chat_id = ch.get("chat_id") or ch.get("id") or ""
    name = ch.get("name") or ch.get("title") or chat_id
    ctype = ch.get("chat_type") or ch.get("type") or "group"
    if not chat_id:
        continue
    kind = "dm" if ctype in ("p2p", "dm", "single") else "groups"
    params = json.dumps({"chat_id": chat_id, "start_time": start_ts, "end_time": end_ts})
    try:
        out = subprocess.run(
            ["lark-cli", "im", "+chat-messages-list", "--as", "user",
             "--params", params, "--page-all", "--format", "json"],
            capture_output=True, text=True, timeout=120,
        )
        msgs = load(out.stdout)
    except Exception:
        msgs = {}
    mlist = msgs if isinstance(msgs, list) else (msgs.get("items") or msgs.get("data") or [])
    if not mlist:  # 窗口内没消息就跳过，不建空文件
        continue
    lines = []
    for m in mlist:
        sender = (m.get("sender") or {}).get("name") if isinstance(m.get("sender"), dict) else m.get("sender") or m.get("sender_id") or "?"
        body = m.get("text") or m.get("content") or json.dumps(m.get("body", ""), ensure_ascii=False)
        ts = m.get("create_time") or m.get("time") or ""
        lines.append(f"**{sender}** {ts}\n\n{body}\n")
    d = os.path.join(dest, kind)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{today}_{slug(name)}.md")
    fm = (f"source: feishu\ntenant: {tenant}\nchannel: {name}\n"
          f"type: {'dm' if kind == 'dm' else 'group'}\ncaptured: {today}\nchat_id: {chat_id}")
    with open(path, "w") as f:
        f.write(f"---\n{fm}\n---\n\n# {name}\n\n" + "\n".join(lines) + "\n")
    print(f"[pull-feishu] 写入 {path}", file=sys.stderr)
    count += 1

print(f"[pull-feishu] 租户「{tenant}」完成，处理 {count} 个会话", file=sys.stderr)
