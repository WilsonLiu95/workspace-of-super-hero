#!/usr/bin/env bash
# 拉腾讯会议录制 + AI 纪要/转写/摘要 → sources/tencent-meeting/
#
# 自包含技能：本脚本不依赖仓库顶层 scripts/lib/common.sh，被复制到任意仓库后仍可独立运行。
# 内联一个极简的 env 加载器（见下），凭证从仓库根 .env.local（被 gitignore）读取。
#
# 凭证（.env.local）：
#   TENCENT_MEETING_APP_ID          必需  企业自建应用 AppId
#   TENCENT_MEETING_SDK_ID          必需  SdkId
#   TENCENT_MEETING_SECRET_ID       必需  SecretId
#   TENCENT_MEETING_SECRET_KEY      必需  SecretKey
#   TENCENT_MEETING_OPERATOR_ID     必需  操作者（会议创建者，或具录制管理权限者）
#   TENCENT_MEETING_OPERATOR_ID_TYPE 可选 默认 1（1=userid）
#   TENCENT_MEETING_SINCE_DAYS      可选  最近 N 天，默认 7，硬上限 31
#
# 多租户：若设置环境变量 TENANT，则在 .env.local 之上再叠加 .env.$TENANT.local。

set -euo pipefail

SCRIPT_NAME="pull-tencent-meeting"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- 极简日志（颜色仅在 TTY） ----
_c() { [ -t 2 ] && printf '%s' "$1" || true; }
log()  { printf '%s[%s]%s %s\n' "$(_c $'\033[36m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; }
warn() { printf '%s[%s] WARN%s %s\n' "$(_c $'\033[33m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; }
die()  { printf '%s[%s] ERROR%s %s\n' "$(_c $'\033[31m')" "$SCRIPT_NAME" "$(_c $'\033[0m')" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# ---- 定位仓库根 ----
# 优先用 git 顶层；失败则从技能目录向上推算（.claude/skills/tencent-meeting/scripts → 上 4 级）。
if WORKSPACE_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

# ---- 内联 env 加载器（自包含，不依赖 common.sh） ----
# (a) 若存在则 source 仓库根 .env.local；(b) 若设置了 TENANT，再叠加 .env.$TENANT.local。
load_env_file() {
  local f="$1"
  if [ -f "$f" ]; then
    set -a; . "$f"; set +a
    log "已加载 $f"
  fi
}
load_env_file "$WORKSPACE_ROOT/.env.local"
if [ -n "${TENANT:-}" ]; then
  load_env_file "$WORKSPACE_ROOT/.env.${TENANT}.local"
fi

# ---- 依赖检查 ----
have python3 || die "需要 python3。"

# ---- 凭证检查（4 项硬性 + operator），缺则给出可操作提示 ----
miss=""
for v in TENCENT_MEETING_APP_ID TENCENT_MEETING_SDK_ID TENCENT_MEETING_SECRET_ID \
         TENCENT_MEETING_SECRET_KEY TENCENT_MEETING_OPERATOR_ID; do
  if [ -z "${!v:-}" ]; then miss="$miss $v"; fi
done
if [ -n "$miss" ]; then
  die "缺少必需凭证：$miss
请在 $WORKSPACE_ROOT/.env.local 配置（企业版/商业版「自建应用」凭证）：
  TENCENT_MEETING_APP_ID / SDK_ID / SECRET_ID / SECRET_KEY / OPERATOR_ID
operator 必须是会议创建者，或持有企业「录制管理」权限的成员。"
fi

# ---- 落盘目录（相对仓库根） ----
DEST="sources/tencent-meeting"
export TENCENT_MEETING_DEST="$DEST"
mkdir -p "$WORKSPACE_ROOT/$DEST"

log "开始拉取（窗口=最近 ${TENCENT_MEETING_SINCE_DAYS:-7} 天，operator_type=${TENCENT_MEETING_OPERATOR_ID_TYPE:-1}）"

# 在仓库根运行 python，使 sources/tencent-meeting 相对路径落对位置
cd "$WORKSPACE_ROOT"
python3 "$SCRIPT_DIR/tmeeting_client.py"

log "完成。产物在 $WORKSPACE_ROOT/$DEST/"
