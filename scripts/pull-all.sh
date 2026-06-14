#!/usr/bin/env bash
# 编排器：依次跑各来源的拉取脚本，供定时任务调用。
# 单个来源失败不中断其它来源；最后汇总。可用 PULL_SOURCES 限定来源。
#
#   scripts/pull-all.sh                      # 拉全部（feishu getnote wechat）
#   PULL_SOURCES="feishu getnote" scripts/pull-all.sh
SCRIPT_NAME="pull-all"
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
load_local_env

HERE="$(dirname "${BASH_SOURCE[0]}")"
SOURCES_LIST="${PULL_SOURCES:-feishu getnote wechat}"

declare -a OK=() FAIL=()
for s in $SOURCES_LIST; do
  script="$HERE/pull-$s.sh"
  [ -x "$script" ] || script="bash $HERE/pull-$s.sh"
  log "==== 开始 $s ===="
  if bash "$HERE/pull-$s.sh"; then OK+=("$s"); else FAIL+=("$s"); warn "$s 失败（继续其它来源）"; fi
done

log "==== 汇总 ===="
log "成功: ${OK[*]:-无}"
[ ${#FAIL[@]} -gt 0 ] && warn "失败: ${FAIL[*]}" || true
log "提示：定时器/Agent 可在此后做归档整理与提交（注意 sources/ 默认不进 git）。"
# 有任一失败则非零退出，便于定时器感知
[ ${#FAIL[@]} -eq 0 ]
