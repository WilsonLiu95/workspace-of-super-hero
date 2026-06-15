#!/usr/bin/env bash
# 首次配置向导 / 体检 —— 让"第一次导入这个工作区"的人最省力地把各集成打通。
#
# 子命令：
#   setup.sh status        首次运行检测（有没有 .env.local、装了几个 skill）
#   setup.sh init          从 .env.example 生成 .env.local（已存在则不覆盖）
#   setup.sh doctor        逐集成体检：凭证齐了吗？工具装了吗？能连吗？
#   setup.sh set KEY VALUE 写入/更新 .env.local 里的一个键（幂等；供引导逐项落盘）
#
# 实现单一：Claude 的 setup 技能、Codex/CodeBuddy、人手都调这一个脚本。
set -euo pipefail
SCRIPT_NAME="setup"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 优先复用 lib/common.sh（随 setup 一起分发）；找不到就用内置兜底，保证独立可跑。
if [ -f "$HERE/lib/common.sh" ]; then
  # shellcheck disable=SC1091
  source "$HERE/lib/common.sh"
else
  WORKSPACE_ROOT="$(cd "$HERE/.." && pwd)"; TODAY="$(date +%F)"
  log(){ printf '[setup] %s\n' "$*" >&2; }
  warn(){ printf '[setup] WARN %s\n' "$*" >&2; }
  die(){ printf '[setup] ERROR %s\n' "$*" >&2; exit 1; }
  have(){ command -v "$1" >/dev/null 2>&1; }
  load_local_env(){
    [ -f "$WORKSPACE_ROOT/.env.local" ] && { set -a; . "$WORKSPACE_ROOT/.env.local"; set +a; }
    local t="${TENANT:-}"; [ -n "$t" ] && [ -f "$WORKSPACE_ROOT/.env.$t.local" ] && { set -a; . "$WORKSPACE_ROOT/.env.$t.local"; set +a; }
  }
fi

ENVF="$WORKSPACE_ROOT/.env.local"
EXF="$WORKSPACE_ROOT/.env.example"

# ---------- 体检用小助手 ----------
_tty(){ [ -t 1 ]; }
ok(){   if _tty; then printf '  \033[32m✅\033[0m %s\n' "$*"; else printf '  [OK]   %s\n' "$*"; fi; }
miss(){ if _tty; then printf '  \033[33m⚠️ \033[0m %s\n' "$*"; else printf '  [TODO] %s\n' "$*"; fi; }
na(){   if _tty; then printf '  \033[2m—\033[0m  %s\n' "$*";  else printf '  [opt]  %s\n' "$*"; fi; }
# 变量已设且非占位符
have_env(){ local v="${!1:-}"; [ -n "$v" ] && [[ "$v" != *your-host* ]] && [[ "$v" != "<"*">"* ]]; }

do_status(){
  echo "== 工作区状态 =="
  if [ -f "$ENVF" ]; then ok ".env.local 已存在（非首次使用）"
  else miss "未发现 .env.local —— 像是首次使用。跑 'setup.sh init'，或在 Agent 里说「帮我配置工作区」走引导。"; fi
  local n=0 d
  for d in "$WORKSPACE_ROOT"/.claude/skills/*/SKILL.md; do [ -f "$d" ] && n=$((n+1)); done
  ok "已装 skill：$n 个（.claude/skills/）"
  [ -f "$WORKSPACE_ROOT/AGENTS.md" ] && ok "多 Agent 入口：CLAUDE.md / AGENTS.md 就位（Codex、CodeBuddy 复用 AGENTS.md）"
}

do_init(){
  if [ -f "$ENVF" ]; then warn ".env.local 已存在，未覆盖（要重置请先自行备份删除）。"; return 0; fi
  if [ -f "$EXF" ]; then cp "$EXF" "$ENVF"; log "已从 .env.example 生成 .env.local。"; else : >"$ENVF"; log "已建空 .env.local。"; fi
  log "下一步：在 Agent 里说「帮我配置工作区」逐项填，或手动编辑 .env.local，然后 'setup.sh doctor' 体检。"
}

# setup.sh set KEY VALUE —— 幂等写入 .env.local（供引导把用户给的凭证落盘）
do_set(){
  local key="${1:-}" val="${2:-}"
  [ -n "$key" ] || die "用法：setup.sh set KEY VALUE"
  [ -f "$ENVF" ] || { [ -f "$EXF" ] && cp "$EXF" "$ENVF" || : >"$ENVF"; }
  if grep -qE "^[[:space:]]*${key}=" "$ENVF"; then
    KEY="$key" VAL="$val" python3 - "$ENVF" <<'PY'
import os, re, sys
f = sys.argv[1]; key = os.environ["KEY"]; val = os.environ["VAL"]
lines = open(f, encoding="utf-8").read().splitlines()
out = [(f"{key}={val}" if re.match(rf"^\s*{re.escape(key)}=", ln) else ln) for ln in lines]
open(f, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENVF"
  fi
  log "已写入 ${key}（.env.local）"
}

do_doctor(){
  load_local_env
  echo "== 集成体检（⚠️=待办，✅=就绪，—=可选）=="

  # 飞书
  if have lark-cli; then
    if lark-cli auth status >/dev/null 2>&1; then ok "飞书 feishu-cli：lark-cli 已登录"
    else miss "飞书：装了 lark-cli 但未登录 → lark-cli config init && lark-cli auth login"; fi
  else miss "飞书：未装 lark-cli → npm i -g @larksuite/cli"; fi

  # 钉钉
  if have_env DINGTALK_APP_KEY && have_env DINGTALK_APP_SECRET; then
    ok "钉钉 dingtalk：凭证已配（确认管理员已授予通讯录/文档读权限）"
  else miss "钉钉：缺 DINGTALK_APP_KEY/DINGTALK_APP_SECRET（钉钉开放平台 → 企业内部应用）"; fi

  # 腾讯会议
  if have_env TENCENT_MEETING_APP_ID && have_env TENCENT_MEETING_SECRET_ID \
     && have_env TENCENT_MEETING_SECRET_KEY && have_env TENCENT_MEETING_OPERATOR_ID; then
    ok "腾讯会议 tencent-meeting：AKSK + operator 已配"
  else miss "腾讯会议：缺 AKSK（APP_ID/SDK_ID/SECRET_ID/SECRET_KEY）或 OPERATOR_ID（需企业版/商业版自建应用）"; fi

  # 得到 / Get笔记
  if have_env GET_BIJI_API_KEY; then
    if have_env GET_BIJI_CLIENT_ID; then ok "得到/Get笔记 get-biji：API_KEY + CLIENT_ID 已配"
    else miss "得到：有 API_KEY，缺 GET_BIJI_CLIENT_ID（notes list 需要）"; fi
  else miss "得到/Get笔记：缺 GET_BIJI_API_KEY"; fi

  # 微信 chatlog
  local base="${CHATLOG_BASE_URL:-http://127.0.0.1:5030}"
  if curl -fsS "$base/api/v1/session" -o /dev/null 2>/dev/null; then ok "微信 wechat-chatlog：chatlog 服务在线（${base}）"
  elif have chatlog; then miss "微信：装了 chatlog 但服务没起 → chatlog server"
  else miss "微信：未装 chatlog（github.com/sjzar/chatlog）"; fi

  # 公众号
  if python3 -c 'import requests' 2>/dev/null; then ok "公众号 wechat-exporter：python requests 就绪（运行时扫码登录）"
  else miss "公众号：缺依赖 → pip install requests openpyxl markdownify beautifulsoup4 --break-system-packages"; fi

  # 小宇宙
  if [ -f "$HOME/.xiaoyuzhou/credentials.json" ]; then ok "小宇宙 xiaoyuzhou：已登录"
  else miss "小宇宙：未登录 → python3 .claude/skills/xiaoyuzhou/xiaoyuzhou.py login（扫码）"; fi

  # 博客
  if have_env BLOG_FEEDS; then ok "博客 blog：BLOG_FEEDS 已配"
  else miss "博客：未配 BLOG_FEEDS（逗号分隔 feed/主页 URL；无需凭证）"; fi
  if python3 -c 'import feedparser, trafilatura' 2>/dev/null; then ok "博客增强：feedparser+trafilatura 已装（抽正文更好）"
  else na "博客可选增强：pip install feedparser trafilatura markdownify（不装也能跑，质量降级）"; fi

  # AI 生图
  if have_env AIPROXY_API_KEY && have_env AIPROXY_BASE_URL; then ok "AI 生图 ai-image：凭证已配"
  else miss "AI 生图：缺 AIPROXY_API_KEY / AIPROXY_BASE_URL"; fi

  echo
  echo "== 多 Agent 入口 =="
  [ -f "$WORKSPACE_ROOT/CLAUDE.md" ] && ok "Claude：CLAUDE.md + .claude/skills/" || na "缺 CLAUDE.md"
  [ -f "$WORKSPACE_ROOT/AGENTS.md" ] && ok "Codex / CodeBuddy：AGENTS.md（CodeBuddy 无 CODEBUDDY.md 时自动读它）" || na "缺 AGENTS.md"
  echo
  log "提示：多租户=把额外那套凭证写到 .env.<租户>.local，运行时 TENANT=<租户> 叠加。"
}

CMD="${1:-status}"; shift || true
case "$CMD" in
  status) do_status ;;
  init)   do_init ;;
  doctor) do_doctor ;;
  set)    do_set "${1:-}" "${2:-}" ;;
  *) die "未知命令：${CMD}（status | init | doctor | set KEY VALUE）" ;;
esac
