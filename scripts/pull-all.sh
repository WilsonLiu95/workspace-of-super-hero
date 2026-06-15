#!/usr/bin/env bash
# 编排器：依次跑各来源的拉取脚本，供定时任务调用。
# 单个来源失败不中断其它来源；最后汇总。可用 PULL_SOURCES 限定来源。
#
#   scripts/pull-all.sh                      # 拉全部（feishu getnote wechat）
#   PULL_SOURCES="feishu getnote" scripts/pull-all.sh
SCRIPT_NAME="pull-all"
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_local_env

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 默认拉核心来源；用 PULL_SOURCES 覆盖，也可纳入自包含的新 skill，例：
#   PULL_SOURCES="feishu getnote dingtalk blog" scripts/pull-all.sh
SOURCES_LIST="${PULL_SOURCES:-feishu getnote wechat}"

# 解析来源 → 脚本路径：先看顶层 scripts/pull-<s>.sh，再看自包含 skill 的脚本
resolve_script() {
  local s="$1"
  [ -f "$HERE/pull-$s.sh" ] && { printf '%s\n' "$HERE/pull-$s.sh"; return 0; }
  local sk="$WORKSPACE_ROOT/.claude/skills/$s/scripts/pull-$s.sh"
  [ -f "$sk" ] && { printf '%s\n' "$sk"; return 0; }
  return 1
}

declare -a OK=() FAIL=()
for s in $SOURCES_LIST; do
  scr="$(resolve_script "$s")" || { warn "找不到来源「${s}」的拉取脚本，跳过"; FAIL+=("$s"); continue; }
  log "==== 开始 ${s}（${scr}）===="
  if bash "$scr"; then OK+=("$s"); else FAIL+=("$s"); warn "$s 失败（继续其它来源）"; fi
done

log "==== 汇总 ===="
log "成功: ${OK[*]:-无}"
[ ${#FAIL[@]} -gt 0 ] && warn "失败: ${FAIL[*]}" || true
log "提示：定时器/Agent 可在此后做归档整理与提交（注意 sources/ 默认不进 git）。"
# 有任一失败则非零退出，便于定时器感知
[ ${#FAIL[@]} -eq 0 ]
