#!/usr/bin/env bash
# 拉飞书 → sources/feishu/<租户>/{dm,groups}/   —— 支持多租户
#
# 模型：每个租户 = 一个 lark-cli profile，profile 名 == 租户目录名。
#
# 多租户（推荐）：在 .env.local 设
#     FEISHU_TENANTS="acme globex"      # 空格或逗号分隔；每个名字 = profile 名 = sources/feishu/<名字>/
#   脚本逐个 `lark-cli profile use <租户>` 后拉取，结束后切回原 active profile。
# 单租户（兼容）：不设 FEISHU_TENANTS 时用当前 active profile，落到 sources/feishu/${FEISHU_TENANT:-default}/。
#
# 添加/登录某租户凭证：scripts/feishu-add-tenant.sh <租户名>
# 其它环境变量：FEISHU_SINCE_DAYS（默认 1）、FEISHU_MAX_CHATS（默认 50）
SCRIPT_NAME="pull-feishu"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib/common.sh"
load_local_env

have lark-cli || die "未安装 lark-cli：npm i -g @larksuite/cli（见 .claude/skills/feishu-cli）。"
have python3  || die "需要 python3。"

SINCE_DAYS="${FEISHU_SINCE_DAYS:-1}"
MAX_CHATS="${FEISHU_MAX_CHATS:-50}"
if date -v-1d >/dev/null 2>&1; then START_TS=$(date -v-"${SINCE_DAYS}"d +%s); else START_TS=$(date -d "-${SINCE_DAYS} days" +%s); fi
END_TS=$(date +%s)

# 拉一个租户（假定已切到其 profile）。$1 = 租户名(= 目录名)
pull_one_tenant() {
  local tenant="$1" dest="$SOURCES_DIR/feishu/$1"
  lark-cli auth status >/dev/null 2>&1 || { warn "租户「${tenant}」未登录，跳过：lark-cli profile use $tenant && lark-cli auth login"; return 1; }
  log "租户=$tenant 窗口=最近${SINCE_DAYS}天 上限=${MAX_CHATS}个会话"
  local chats_json; chats_json="$(lark-cli im +chat-list --as user --page-all --format json 2>/dev/null || true)"
  [ -n "$chats_json" ] || { warn "租户「${tenant}」会话列表为空，跳过"; return 1; }
  printf '%s' "$chats_json" | python3 "$HERE/lib/feishu_to_md.py" "$dest" "$START_TS" "$END_TS" "$MAX_CHATS" "$tenant" "$TODAY"
}

# 当前 active profile（用于结束后还原）
active_profile() {
  lark-cli profile list 2>/dev/null \
    | python3 -c 'import sys,json;d=json.load(sys.stdin);print(next((p["name"] for p in d if p.get("active")),""))' 2>/dev/null || true
}

if [ -n "${FEISHU_TENANTS:-}" ]; then
  RESTORE="$(active_profile)"
  ok=0; fail=0
  for t in $(printf '%s' "$FEISHU_TENANTS" | tr ',' ' '); do
    [ -n "$t" ] || continue
    if ! lark-cli profile use "$t" >/dev/null 2>&1; then
      warn "无此 profile：「${t}」。先建：scripts/feishu-add-tenant.sh $t"; fail=$((fail+1)); continue
    fi
    if pull_one_tenant "$t"; then ok=$((ok+1)); else fail=$((fail+1)); fi
  done
  [ -n "$RESTORE" ] && lark-cli profile use "$RESTORE" >/dev/null 2>&1 || true
  log "多租户完成：成功 ${ok}，失败/跳过 ${fail}（已切回 profile：${RESTORE:-未知}）"
  [ "$fail" -eq 0 ]
else
  lark-cli auth status >/dev/null 2>&1 || die "lark-cli 未登录（lark-cli auth login）；或在 .env.local 配 FEISHU_TENANTS 走多租户。"
  pull_one_tenant "${FEISHU_TENANT:-default}"
fi
