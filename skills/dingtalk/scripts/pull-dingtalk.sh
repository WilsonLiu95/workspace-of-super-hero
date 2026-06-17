#!/usr/bin/env bash
# 拉钉钉 → sources/dingtalk/<租户>/
# 自建「企业内部应用」。归档通讯录（默认）与文档/知识库（可选）。
#
# 钉钉不开放历史聊天记录 API（平台限制）——本脚本不拉聊天，也不要伪造。
#
# 环境变量（统一放仓库根 .env.local，已被 .gitignore 忽略）：
#   DINGTALK_APP_KEY      必填，企业内部应用的 AppKey
#   DINGTALK_APP_SECRET   必填，企业内部应用的 AppSecret
#   DINGTALK_TENANT       落盘目录名（默认 default）
#   DINGTALK_ARCHIVE      要归档什么，csv：contacts,docs（默认 contacts）
#
# 多租户叠加：若设置了环境变量 TENANT，会在 .env.local 之上再叠加 .env.$TENANT.local。
#
# 本脚本自包含：不依赖仓库的 scripts/lib/common.sh，复制到任何仓库都能用。
set -euo pipefail

SCRIPT_NAME="pull-dingtalk"

# --- 颜色日志（仅 TTY 上色） --------------------------------------------- #
_c() { [ -t 2 ] && printf '%s' "$1" || true; }
log()  { printf '%s[%s]%s %s\n'      "$(_c $'\033[36m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; }
warn() { printf '%s[%s] WARN%s %s\n' "$(_c $'\033[33m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; }
die()  { printf '%s[%s] ERROR%s %s\n' "$(_c $'\033[31m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; exit 1; }

# --- 定位仓库根 ---------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if WORKSPACE_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  # 技能布局：<repo>/skills/dingtalk/scripts/pull-dingtalk.sh → 上三级 = 仓库根
  WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
fi

# --- 内联 env 加载器（自包含，不依赖 common.sh） ------------------------ #
# (a) 先 source 仓库根 .env.local（若存在）
# (b) 若设置了 TENANT，再叠加 .env.$TENANT.local（覆盖同名变量）
load_env() {
  local f="$WORKSPACE_ROOT/.env.local"
  if [ -f "$f" ]; then set -a; . "$f"; set +a; log "已加载 $f"; fi
  if [ -n "${TENANT:-}" ]; then
    local tf="$WORKSPACE_ROOT/.env.${TENANT}.local"
    if [ -f "$tf" ]; then set -a; . "$tf"; set +a; log "已叠加 $tf"; fi
  fi
}
load_env

# --- 依赖与凭证检查 ------------------------------------------------------ #
command -v python3 >/dev/null 2>&1 || die "需要 python3。"

if [ -z "${DINGTALK_APP_KEY:-}" ] || [ -z "${DINGTALK_APP_SECRET:-}" ]; then
  die "缺少凭证。请在 $WORKSPACE_ROOT/.env.local 设置 DINGTALK_APP_KEY 与 DINGTALK_APP_SECRET（钉钉开放平台→企业内部应用）。"
fi

export DINGTALK_APP_KEY DINGTALK_APP_SECRET
export DINGTALK_TENANT="${DINGTALK_TENANT:-default}"
export DINGTALK_ARCHIVE="${DINGTALK_ARCHIVE:-contacts}"

log "租户=${DINGTALK_TENANT} 归档=${DINGTALK_ARCHIVE}"

# --- 在仓库根执行，确保 sources/ 与 .tmp/ 落对位置 --------------------- #
cd "$WORKSPACE_ROOT"
python3 "$SCRIPT_DIR/dingtalk_client.py"

log "完成。产物在 sources/dingtalk/${DINGTALK_TENANT}/"
