#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP="$ROOT/scripts/setup.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

help_output="$(bash "$SETUP" help 2>&1)" || fail "setup.sh help should exit 0"
grep -q "wizard" <<<"$help_output" || fail "help should mention the wizard command"
grep -q "guide" <<<"$help_output" || fail "help should mention the guide alias"

wizard_output="$(bash "$SETUP" wizard --dry-run 2>&1)" || fail "setup.sh wizard --dry-run should exit 0"
grep -q "一键配置向导" <<<"$wizard_output" || fail "wizard should print the onboarding title"
grep -q "钉钉" <<<"$wizard_output" || fail "wizard should include DingTalk guidance"
grep -q "腾讯会议" <<<"$wizard_output" || fail "wizard should include Tencent Meeting guidance"
grep -q "公众号" <<<"$wizard_output" || fail "wizard should include WeChat MP guidance"
grep -q "小宇宙" <<<"$wizard_output" || fail "wizard should include Xiaoyuzhou guidance"
if grep -q "chatlog\\|微信聊天" <<<"$wizard_output"; then
  fail "wizard should not include WeChat chatlog while that integration is paused"
fi

doctor_output="$(bash "$SETUP" doctor 2>&1)" || fail "setup.sh doctor should exit 0"
if grep -q "chatlog\\|微信：" <<<"$doctor_output"; then
  fail "doctor should not report WeChat chatlog while that integration is paused"
fi

manual_meeting_output="$(TENCENT_MEETING_MODE=manual bash "$SETUP" doctor 2>&1)" || fail "setup.sh doctor should support manual Tencent Meeting mode"
grep -q "腾讯会议.*个人版手动归档" <<<"$manual_meeting_output" || fail "doctor should identify manual Tencent Meeting mode"
if grep -q "腾讯会议：缺 AKSK" <<<"$manual_meeting_output"; then
  fail "doctor should not require Tencent Meeting AKSK in manual mode"
fi

tmeet_output="$(TENCENT_MEETING_MODE=tmeet bash "$SETUP" doctor 2>&1)" || fail "setup.sh doctor should support Tencent Meeting CLI mode"
grep -q "腾讯会议.*tmeet CLI" <<<"$tmeet_output" || fail "doctor should identify Tencent Meeting CLI mode"
if grep -q "腾讯会议：缺 AKSK" <<<"$tmeet_output"; then
  fail "doctor should not require Tencent Meeting AKSK in tmeet mode"
fi

pull_all="$ROOT/scripts/pull-all.sh"
grep -q 'PULL_SOURCES:-feishu getnote}' "$pull_all" || fail "pull-all default should exclude wechat while chatlog is paused"

printf 'setup tests passed\n'
