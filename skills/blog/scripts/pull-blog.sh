#!/usr/bin/env bash
# 拉博客 / RSS → sources/blog/
#
# 自包含技能：不依赖仓库顶层 scripts/lib/common.sh，被复制到任何仓库都能跑。
# 真正逻辑在同目录 blog_client.py（stdlib-first，可选 feedparser/trafilatura/markdownify 增强）。
#
# 环境变量（放仓库根 .env.local，已被 .gitignore 忽略）：
#   BLOG_FEEDS       逗号分隔的 feed URL 或站点主页 URL（主页会自动发现 feed）
#   BLOG_MAX_POSTS   每个 feed 最多归档多少篇（默认 20）
#   BLOG_SINCE_DAYS  跳过早于 N 天的条目（默认空 = 不限制）
#
# 用法：
#   scripts/pull-blog.sh                      # 读 .env.local 的 BLOG_FEEDS
#   scripts/pull-blog.sh <feedURL> [更多URL]  # 直接传 feed/主页 URL，覆盖 BLOG_FEEDS
#   TENANT=foo scripts/pull-blog.sh           # 额外叠加 .env.foo.local
set -euo pipefail

SCRIPT_NAME="pull-blog"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if WORKSPACE_ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  # 技能布局：<repo>/skills/blog/scripts/pull-blog.sh → 上三级 = 仓库根
  WORKSPACE_ROOT="$(cd "$HERE/../../.." && pwd)"
fi
export WORKSPACE_ROOT

# --- 极简日志（颜色仅在 TTY）---
_c() { [ -t 2 ] && printf '%s' "$1" || true; }
log()  { printf '%s[%s]%s %s\n' "$(_c $'\033[36m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; }
die()  { printf '%s[%s] ERROR%s %s\n' "$(_c $'\033[31m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; exit 1; }

# --- 内联 env 加载器（不依赖 common.sh）---
# (a) 先 source 仓库根 .env.local（若存在）
# (b) 若设置了 TENANT，再叠加 .env.$TENANT.local（后者覆盖前者）
load_env() {
  local base="$WORKSPACE_ROOT/.env.local"
  if [ -f "$base" ]; then
    set -a; . "$base"; set +a
    log "已加载 $base"
  fi
  if [ -n "${TENANT:-}" ]; then
    local overlay="$WORKSPACE_ROOT/.env.${TENANT}.local"
    if [ -f "$overlay" ]; then
      set -a; . "$overlay"; set +a
      log "已叠加 ${overlay}（TENANT=${TENANT}）"
    fi
  fi
}

command -v python3 >/dev/null 2>&1 || die "需要 python3。"

load_env

# CLI 参数里的 URL 优先；否则要求 .env.local 里有 BLOG_FEEDS
if [ "$#" -eq 0 ] && [ -z "${BLOG_FEEDS:-}" ]; then
  die "未配置任何 feed。请在仓库根 .env.local 设置 BLOG_FEEDS（逗号分隔的 feed/主页 URL），\
或把 feed/主页 URL 作为参数传入，例如：scripts/pull-blog.sh https://example.com/feed"
fi

log "落盘 → $WORKSPACE_ROOT/sources/blog/"
exec python3 "$HERE/blog_client.py" "$@"
