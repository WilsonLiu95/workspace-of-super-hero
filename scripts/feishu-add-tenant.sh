#!/usr/bin/env bash
# 引导式添加一个飞书租户凭证。
#
# 命名约定：<人名>-<租户名>（如 liusheng-jingbaobao = 刘盛 在 晶宝宝 租户下的凭证）。
# 这个名字同时是 lark-cli profile 名 和 sources/feishu/<名>/ 目录名——一眼看清"谁在哪个租户"。
#
# 两种方式：
#   ① 浏览器创建新应用（推荐·免手输 Secret）：
#        scripts/feishu-add-tenant.sh <人名-租户名>
#      lark-cli 走浏览器流程创建自建应用并**自动回填 App ID/Secret**，你全程不碰 Secret。
#      （应用建在你浏览器当前登录的那个飞书租户下——先确认登录的是目标租户。）
#   ② 已有应用、手输凭证：
#        scripts/feishu-add-tenant.sh <人名-租户名> <app-id>
#      隐藏输入 App Secret，经 stdin 传给 lark-cli，不进 argv/进程列表/仓库。
SCRIPT_NAME="feishu-add-tenant"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib/common.sh"

have lark-cli || die "未安装 lark-cli：npm i -g @larksuite/cli"

NAME="${1:-}"
[ -n "$NAME" ] || die "用法：scripts/feishu-add-tenant.sh <人名-租户名> [app-id]
  ① scripts/feishu-add-tenant.sh liusheng-jingbaobao         # 浏览器建新应用，免输 Secret（推荐）
  ② scripts/feishu-add-tenant.sh liusheng-jingbaobao cli_xxx # 已有应用，手输 Secret"
APP_ID="${2:-}"

if [ -z "$APP_ID" ]; then
  log "方式①：浏览器创建自建应用并自动回填凭证（你不用复制 App Secret）"
  log "  ⚠ 应用会建在你浏览器当前登录的飞书租户下——先确认登录的是「$NAME」对应的租户。"
  lark-cli config init --new --name "$NAME"
else
  log "方式②：已有应用 app-id=$APP_ID，隐藏输入 App Secret"
  printf '请输入「%s」的 App Secret（输入时不显示，回车确认）: ' "$NAME" >&2
  read -r -s APP_SECRET; echo >&2
  [ -n "$APP_SECRET" ] || die "App Secret 不能为空"
  printf '%s' "$APP_SECRET" | lark-cli config init --app-id "$APP_ID" --app-secret-stdin --name "$NAME"
  unset APP_SECRET
fi

log "切到 profile「$NAME」做设备码登录（浏览器里确认授权）..."
lark-cli profile use "$NAME" >/dev/null 2>&1 || true
lark-cli auth login || warn "登录未完成；稍后重跑：lark-cli profile use $NAME && lark-cli auth login"

mkdir -p "$SOURCES_DIR/feishu/$NAME"/{dm,groups,docs}
log "已建目录 sources/feishu/$NAME/{dm,groups,docs}"
log "完成 ✅  最后把「$NAME」加进 .env.local 的 FEISHU_TENANTS，pull-feishu.sh 就会带上它。"
