#!/usr/bin/env bash
# 引导式添加一个飞书租户凭证。
#   一个租户 = 一个 lark-cli profile = sources/feishu/<租户>/ 目录。
#
# 安全：App Secret 用隐藏输入(read -s) → 经 stdin 传给 lark-cli，绝不出现在命令行/进程列表/本仓库。
#
# 用法（在你自己的终端里跑，需要交互输入）：
#   scripts/feishu-add-tenant.sh <租户名> [app-id]
#   <租户名>：简短英文 slug，既作 lark-cli profile 名，也作 sources/feishu/<租户名>/ 目录名。
SCRIPT_NAME="feishu-add-tenant"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib/common.sh"

have lark-cli || die "未安装 lark-cli：npm i -g @larksuite/cli"

TENANT="${1:-}"
[ -n "$TENANT" ] || die "用法：scripts/feishu-add-tenant.sh <租户名> [app-id]"
APP_ID="${2:-}"

if [ -z "$APP_ID" ]; then
  read -r -p "租户「$TENANT」的 App ID (cli_...): " APP_ID
fi
[ -n "$APP_ID" ] || die "App ID 不能为空"

printf '请输入「%s」的 App Secret（输入时不显示，回车确认）: ' "$TENANT" >&2
read -r -s APP_SECRET; echo >&2
[ -n "$APP_SECRET" ] || die "App Secret 不能为空"

log "创建/更新 profile「$TENANT」(app-id=$APP_ID) ..."
printf '%s' "$APP_SECRET" | lark-cli profile add --name "$TENANT" --app-id "$APP_ID" --app-secret-stdin --use
unset APP_SECRET

log "对租户「$TENANT」做设备码登录（浏览器里确认授权）..."
lark-cli auth login || warn "登录未完成；稍后可重跑：lark-cli profile use $TENANT && lark-cli auth login"

mkdir -p "$SOURCES_DIR/feishu/$TENANT"/{dm,groups,docs}
log "已建目录 sources/feishu/$TENANT/{dm,groups,docs}"

log "完成 ✅  最后一步：把「$TENANT」加进 .env.local 的 FEISHU_TENANTS，例如："
log "    FEISHU_TENANTS=\"$TENANT ...\"   然后 scripts/pull-feishu.sh 就会带上它"
