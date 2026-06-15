#!/usr/bin/env bash
# 共享助手，被 scripts/pull-*.sh 用 `source` 引入。无副作用。
# 设计原则：拉取脚本只把"原始数据"落到 sources/<来源>/，尽量少加工——
# 真正的合成留给 Agent。每个落盘文件都带 frontmatter（见各 sources/*/README.md）。

set -euo pipefail

# 仓库根（scripts/lib/common.sh → 上两级）
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCES_DIR="$WORKSPACE_ROOT/sources"
TODAY="$(date +%F)"
NOW="$(date +%FT%T%z)"

_c() { [ -t 2 ] && printf '%s' "$1" || true; }  # 颜色仅在 TTY
log()  { printf '%s[%s]%s %s\n' "$(_c $'\033[36m')" "${SCRIPT_NAME:-pull}" "$(_c $'\033[0m')" "$*" >&2; }
warn() { printf '%s[%s] WARN%s %s\n' "$(_c $'\033[33m')" "${SCRIPT_NAME:-pull}" "$(_c $'\033[0m')" "$*" >&2; }
die()  { printf '%s[%s] ERROR%s %s\n' "$(_c $'\033[31m')" "${SCRIPT_NAME:-pull}" "$(_c $'\033[0m')" "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# 把任意文本变成安全的文件名片段（保留中文，替换路径分隔符/空白，截断 60 字符）
slugify() { printf '%s' "${1:-}" | sed $'s#[/\\\\]#-#g; s#[[:space:]][[:space:]]*#-#g; s#[:*?"<>|]##g' | cut -c1-60; }

# 确保目标目录存在
ensure_dir() { mkdir -p "$1"; }

# 写一个带 frontmatter 的 markdown 文件。
#   write_note <file> <frontmatter-yaml> <body>
# frontmatter 传入不含 --- 包裹的多行 YAML；本函数负责补 --- 包裹。
write_note() {
  local file="$1" fm="$2" body="$3"
  ensure_dir "$(dirname "$file")"
  { printf -- '---\n%s\n---\n\n%s\n' "$fm" "$body"; } > "$file"
  log "写入 $file"
}

# 可选：source 一个被 gitignore 的本地凭证文件（如果存在），便于定时任务无人值守运行。
# 约定放在 仓库根/.env.local（已被 .gitignore 忽略）。
load_local_env() {
  local f="$WORKSPACE_ROOT/.env.local"
  if [ -f "$f" ]; then set -a; . "$f"; set +a; log "已加载 $f"; fi
  # 多租户：设 TENANT=<名字> 时，在默认 .env.local 之上叠加 .env.<名字>.local
  #（凭证写在 .env 里的来源——钉钉/腾讯会议/得到/生图——靠这个切换不同租户的 key 与落盘目录；
  # 飞书的多租户走 lark-cli profile + FEISHU_TENANTS，见 scripts/pull-feishu.sh）。
  local tenant="${TENANT:-}"
  if [ -n "$tenant" ]; then
    local tf="$WORKSPACE_ROOT/.env.${tenant}.local"
    if [ -f "$tf" ]; then set -a; . "$tf"; set +a; log "已叠加租户配置 $tf"
    else warn "TENANT=$tenant 但未找到 ${tf}（沿用默认 .env.local 的值）"; fi
  fi
}
