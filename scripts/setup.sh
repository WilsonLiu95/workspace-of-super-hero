#!/usr/bin/env bash
# 首次配置向导 / 体检 —— 让"第一次导入这个工作区"的人最省力地把各集成打通。
#
# 子命令：
#   setup.sh status        首次运行检测（有没有 .env.local、装了几个 skill）
#   setup.sh init          从 .env.example 生成 .env.local（已存在则不覆盖）
#   setup.sh doctor        逐集成体检：凭证齐了吗？工具装了吗？能连吗？
#   setup.sh wizard        一键交互式引导：初始化、体检、逐项提示/写入配置
#   setup.sh set KEY VALUE 写入/更新 .env.local 里的一个键（幂等；供引导逐项落盘）
#
# 实现单一：Claude 的 setup 技能、Codex/WorkBuddy、人手都调这一个脚本。
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
valid_key(){ [[ "${1:-}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; }

do_help(){
  cat <<'EOF'
用法：bash scripts/setup.sh <command>

Commands:
  status                 检查是不是首次使用，以及 skill/Agent 入口是否就位
  init                   从 .env.example 生成 .env.local（已存在则不覆盖）
  doctor                 逐集成体检：凭证、工具、登录态、依赖
  wizard | guide         一键配置向导：初始化、体检、提示缺项、可交互写入 .env.local
  set KEY VALUE          幂等写入/更新 .env.local 里的一个键
  help                   显示本帮助

Options:
  wizard --dry-run       只打印体检与配置指引，不创建/写入任何文件
  wizard --yes           对可自动准备的步骤使用默认确认
EOF
}

do_status(){
  echo "== 工作区状态 =="
  if [ -f "$ENVF" ]; then ok ".env.local 已存在（非首次使用）"
  else miss "未发现 .env.local —— 像是首次使用。跑 'setup.sh init'，或在 Agent 里说「帮我配置工作区」走引导。"; fi
  local n=0 d
  for d in "$WORKSPACE_ROOT"/skills/*/SKILL.md; do [ -f "$d" ] && n=$((n+1)); done
  ok "已装 skill：$n 个（skills/，.claude/.agents 通过软链接读取）"
  [ -f "$WORKSPACE_ROOT/AGENTS.md" ] && ok "多 Agent 入口：CLAUDE.md / AGENTS.md 就位（Codex、WorkBuddy 复用 AGENTS.md）"
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
  valid_key "$key" || die "非法 key：${key}"
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

ask_yes_no(){
  local prompt="$1" default="${2:-n}" answer
  if [ "${SETUP_ASSUME_YES:-0}" = "1" ]; then
    return 0
  fi
  if ! [ -t 0 ]; then
    return 1
  fi
  if [ "$default" = "y" ]; then
    printf '%s [Y/n] ' "$prompt"
  else
    printf '%s [y/N] ' "$prompt"
  fi
  read -r answer || answer=""
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$|^[Yy][Ee][Ss]$|^是$ ]]
}

prompt_env(){
  local key="$1" label="$2" secret="${3:-0}" value
  if have_env "$key"; then
    ok "${label}：已存在 ${key}，跳过"
    return 0
  fi
  if ! [ -t 0 ]; then
    miss "${label}：缺 ${key}"
    return 0
  fi
  if [ "$secret" = "1" ]; then
    printf '请输入 %s（留空跳过）：' "$label"
    read -rs value || value=""
    printf '\n'
  else
    printf '请输入 %s（留空跳过）：' "$label"
    read -r value || value=""
  fi
  [ -n "$value" ] || { na "${label}：已跳过"; return 0; }
  do_set "$key" "$value"
  export "$key=$value"
}

print_guidance(){
  cat <<'EOF'

== 一键配置向导：下一步建议 ==

凭证型（可由 wizard 帮你写入 .env.local）：
  1. 钉钉：钉钉开放平台 → 企业内部应用，拿 DINGTALK_APP_KEY / DINGTALK_APP_SECRET。
     管理员需授权通讯录读权限；如要归档文档，再授权知识库/钉盘读权限。钉钉没有历史聊天记录 API。
  2. 腾讯会议（仅个人版）：官方 tmeet CLI（OAuth，零密钥）：npm i -g @tencentcloud/tmeet && tmeet auth login。
     无需任何 .env 凭证；归档跑 bash skills/tencent-meeting/scripts/pull-tencent-meeting.sh。
  3. 得到/Get笔记：Biji OpenAPI 的 GET_BIJI_API_KEY；列笔记还需要 GET_BIJI_CLIENT_ID。
  4. 博客/RSS：把 feed URL 或站点主页 URL 写进 BLOG_FEEDS，多个用逗号分隔。
  5. AI 生图：配置 AIPROXY_API_KEY / AIPROXY_BASE_URL。
  6. 云电脑：配置 CLOUD_COMPUTER_HOST / USER / SSH_KEY 或 PASSWORD；云电脑上准备 Docker + Docker Compose。域名 DNS 由你在域名服务商配置。

工具/登录态型（按命令操作，通常不写 secret 到仓库）：
  1. 飞书：npm i -g @larksuite/cli，然后 scripts/feishu-add-tenant.sh <租户名>。
  2. 公众号：pip install requests openpyxl --break-system-packages；运行导出时扫码，产物落 sources/mp/。
  3. 小宇宙：pip install requests qrcode pillow；python3 skills/xiaoyuzhou/xiaoyuzhou.py login 扫码。

多租户：
  - 飞书：一个租户一个 lark-cli profile，并写入 FEISHU_TENANTS。
  - 钉钉/腾讯会议/得到/生图/云电脑：另一套凭证写进 .env.<租户>.local，运行时 TENANT=<租户> <脚本>。
EOF
}

do_wizard(){
  local dry_run=0
  SETUP_ASSUME_YES=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run|--check) dry_run=1 ;;
      --yes|-y) SETUP_ASSUME_YES=1 ;;
      -h|--help) do_help; return 0 ;;
      *) die "未知 wizard 选项：$1" ;;
    esac
    shift
  done

  echo "== 一键配置向导 =="
  if [ "$dry_run" = "1" ]; then
    na "dry-run：只打印体检与指引，不创建/写入文件"
  else
    do_init
    mkdir -p "$WORKSPACE_ROOT/.tmp"
    ok "临时目录 .tmp 已就绪（二维码/session/token 缓存会放这里，已 gitignore）"
  fi

  echo
  do_status
  echo
  do_doctor
  print_guidance

  if [ "$dry_run" = "1" ]; then
    echo
    log "dry-run 完成。要交互式写入配置，请运行：bash scripts/setup.sh wizard"
    return 0
  fi

  if ! [ -t 0 ]; then
    echo
    log "当前不是交互式终端，已输出配置清单；请手动编辑 .env.local 后再跑 bash scripts/setup.sh doctor。"
    return 0
  fi

  echo
  if ask_yes_no "现在要把凭证型配置写进 .env.local 吗？"; then
    echo
    echo "== 写入钉钉（可留空跳过）=="
    prompt_env DINGTALK_APP_KEY "钉钉 AppKey"
    prompt_env DINGTALK_APP_SECRET "钉钉 AppSecret" 1
    prompt_env DINGTALK_TENANT "钉钉落盘租户名"
    prompt_env DINGTALK_ARCHIVE "钉钉归档范围（contacts 或 contacts,docs）"

    echo
    echo "== 腾讯会议（仅个人版，零密钥）=="
    echo "   无需写 .env：跑 npm i -g @tencentcloud/tmeet && tmeet auth login 扫码登录即可。"
    prompt_env TMEET_SINCE_DAYS "腾讯会议拉取天数（默认 30，可留空）"

    echo
    echo "== 写入得到/Get笔记、博客、生图、云电脑（可留空跳过）=="
    prompt_env GET_BIJI_API_KEY "Biji API Key" 1
    prompt_env GET_BIJI_CLIENT_ID "Biji Client ID"
    prompt_env BLOG_FEEDS "博客/RSS Feed 列表"
    prompt_env AIPROXY_API_KEY "AIProxy API Key" 1
    prompt_env AIPROXY_BASE_URL "AIProxy Base URL"
    prompt_env CLOUD_COMPUTER_HOST "云电脑 SSH Host/IP"
    prompt_env CLOUD_COMPUTER_USER "云电脑 SSH 用户"
    prompt_env CLOUD_COMPUTER_PORT "云电脑 SSH 端口"
    prompt_env CLOUD_COMPUTER_SSH_KEY "云电脑 SSH 私钥路径"
    prompt_env CLOUD_COMPUTER_PASSWORD "云电脑 SSH 密码（不推荐长期使用，建议后续换 SSH key）" 1
    prompt_env CLOUD_COMPUTER_REMOTE_ROOT "云电脑远端托管根目录"
    prompt_env CLOUD_COMPUTER_DOMAIN "云电脑默认托管域名"
  else
    na "已跳过写入凭证；你可以手动编辑 .env.local，或用 bash scripts/setup.sh set KEY VALUE。"
  fi

  echo
  echo "== 交互式登录命令（按需运行）=="
  cat <<'EOF'
飞书多租户： scripts/feishu-add-tenant.sh <租户名>
公众号导出： 运行 wechat-exporter 技能时按二维码扫码
小宇宙登录： python3 skills/xiaoyuzhou/xiaoyuzhou.py login
EOF

  echo
  if ask_yes_no "重新跑 doctor 看看现在还缺什么？" y; then
    echo
    do_doctor
  fi
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

  # 腾讯会议（仅个人版：官方 tmeet CLI / OAuth）
  if have tmeet; then
    if tmeet auth status >/dev/null 2>&1; then
      ok "腾讯会议 tencent-meeting：tmeet CLI 已登录（个人版，录制/AI纪要/逐字稿）"
    else miss "腾讯会议 tmeet：已装未登录 → tmeet auth login（扫码授权）"; fi
  else miss "腾讯会议：未装 tmeet → npm i -g @tencentcloud/tmeet，再 tmeet auth login"; fi

  # 得到 / Get笔记
  if have_env GET_BIJI_API_KEY; then
    if have_env GET_BIJI_CLIENT_ID; then ok "得到/Get笔记 get-biji：API_KEY + CLIENT_ID 已配"
    else miss "得到：有 API_KEY，缺 GET_BIJI_CLIENT_ID（notes list 需要）"; fi
  else miss "得到/Get笔记：缺 GET_BIJI_API_KEY"; fi

  # 公众号
  if python3 -c 'import requests, openpyxl' 2>/dev/null; then ok "公众号 wechat-exporter：核心依赖就绪（运行时扫码登录）"
  else miss "公众号：缺核心依赖 → pip install requests openpyxl --break-system-packages"; fi
  if python3 -c 'import markdownify, bs4' 2>/dev/null; then ok "公众号增强：markdownify+beautifulsoup4 已装（可转 Markdown/TXT）"
  else na "公众号可选增强：pip install markdownify beautifulsoup4 --break-system-packages"; fi

  # 小宇宙
  if python3 -c 'import requests, qrcode, PIL' 2>/dev/null; then ok "小宇宙 xiaoyuzhou：依赖就绪"
  else miss "小宇宙：缺依赖 → pip install requests qrcode pillow"; fi
  if [ -f "$HOME/.xiaoyuzhou/credentials.json" ]; then ok "小宇宙 xiaoyuzhou：已登录"
  else miss "小宇宙：未登录 → python3 skills/xiaoyuzhou/xiaoyuzhou.py login（扫码）"; fi

  # 博客
  if have_env BLOG_FEEDS; then ok "博客 blog：BLOG_FEEDS 已配"
  else miss "博客：未配 BLOG_FEEDS（逗号分隔 feed/主页 URL；无需凭证）"; fi
  if python3 -c 'import feedparser, trafilatura' 2>/dev/null; then ok "博客增强：feedparser+trafilatura 已装（抽正文更好）"
  else na "博客可选增强：pip install feedparser trafilatura markdownify（不装也能跑，质量降级）"; fi

  # AI 生图
  if have_env AIPROXY_API_KEY && have_env AIPROXY_BASE_URL; then ok "AI 生图 ai-image：凭证已配"
  else miss "AI 生图：缺 AIPROXY_API_KEY / AIPROXY_BASE_URL"; fi

  # 云电脑
  if have ssh; then ok "云电脑 cloud-computer：本机 ssh 可用"
  else miss "云电脑：本机缺 ssh 客户端"; fi
  if have_env CLOUD_COMPUTER_HOST; then
    ok "云电脑 cloud-computer：SSH Host 已配（发布前先跑 --dry-run；远端需 Docker + Compose）"
  else miss "云电脑：缺 CLOUD_COMPUTER_HOST"; fi
  if have_env CLOUD_COMPUTER_SSH_KEY; then ok "云电脑认证：SSH key 已配"
  elif have_env CLOUD_COMPUTER_PASSWORD; then
    if have sshpass; then ok "云电脑认证：密码已配，sshpass 可用"
    else miss "云电脑认证：密码已配但缺 sshpass（或改用 CLOUD_COMPUTER_SSH_KEY）"; fi
  else miss "云电脑认证：缺 CLOUD_COMPUTER_SSH_KEY 或 CLOUD_COMPUTER_PASSWORD"; fi
  if have_env CLOUD_COMPUTER_DOMAIN; then ok "云电脑默认域名：CLOUD_COMPUTER_DOMAIN 已配（DNS 仍需用户自行配置）"
  else na "云电脑默认域名可选：CLOUD_COMPUTER_DOMAIN"; fi

  echo
  echo "== 多 Agent 入口 =="
  [ -f "$WORKSPACE_ROOT/CLAUDE.md" ] && ok "Claude：CLAUDE.md + .claude/skills/" || na "缺 CLAUDE.md"
  [ -f "$WORKSPACE_ROOT/AGENTS.md" ] && ok "Codex / WorkBuddy：AGENTS.md（WorkBuddy 无 WORKBUDDY.md 时自动读它）" || na "缺 AGENTS.md"
  echo
  log "提示：多租户=把额外那套凭证写到 .env.<租户>.local，运行时 TENANT=<租户> 叠加。"
}

CMD="${1:-status}"; shift || true
case "$CMD" in
  help|-h|--help) do_help ;;
  status) do_status ;;
  init)   do_init ;;
  doctor) do_doctor ;;
  wizard|guide|onboarding) do_wizard "$@" ;;
  set)    do_set "${1:-}" "${2:-}" ;;
  *) die "未知命令：${CMD}（status | init | doctor | wizard | set KEY VALUE | help）" ;;
esac
