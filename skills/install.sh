#!/usr/bin/env bash
# Workspace Skill 安装器 —— 一行命令从 Git 仓库安装/更新 Skill 到目标仓库。
#
# 在「目标仓库根目录」运行其一即可：
#   远程一行装：
#     curl -fsSL https://raw.githubusercontent.com/WilsonLiu95/workspace-of-super-hero/main/skills/install.sh | bash -s -- install dingtalk
#   本地（已克隆本仓库时）：
#     skills/install.sh install dingtalk@0.1.0 --codex
#
# 命令：
#   list                            列出可安装的 skill 及版本
#   search <关键词>                 搜索 skill
#   install <skill>[@版本] [更多…]  安装一个或多个 skill（默认装到 ./skills/）
#   update  <skill> | --all         更新（= 重新安装最新）
#   installed                       列出当前目录已安装的 skill
#   check-sync                      检查根 skills 与 Agent 入口软链接是否一致
#
# 选项（可与命令混写）：
#   --gitee            从 Gitee 镜像拉取（默认 GitHub）
#   --codex            确保 ./.agents/skills -> ../skills（Codex 读这里）
#   --workbuddy        确保 ./.workbuddy/skills -> ../skills（腾讯 WorkBuddy 读这里）
#   --dir <path>       安装根目录（默认当前目录）
#   --ref <branch|tag> 覆盖拉取的 git ref（调试用；默认按版本/默认分支）
#
# 设计：tarball@ref 方案——按 ref 下载仓库归档，只取需要的子目录/文件，
#       不 clone、不留 .git。registry.json 是清单（版本/路径/依赖/环境变量）。
set -euo pipefail

# ---------- 默认仓库坐标（可被 registry.json 的 repo 段覆盖） ----------
GH_OWNER_REPO="WilsonLiu95/workspace-of-super-hero"
GITEE_OWNER_REPO=""                 # 留空=未配置 Gitee 镜像
DEFAULT_BRANCH="main"
RAW_GH="https://raw.githubusercontent.com"
CODELOAD_GH="https://codeload.github.com"
GITEE_BASE="https://gitee.com"

# ---------- 选项默认值 ----------
USE_GITEE=0; MIRROR_CODEX=0; MIRROR_WORKBUDDY=0; REF_OVERRIDE=""
INSTALL_DIR="$(pwd)"

_tty(){ [ -t 2 ]; }
log(){ if _tty; then printf '\033[36m[skill-install]\033[0m %s\n' "$*" >&2; else printf '[skill-install] %s\n' "$*" >&2; fi; }
warn(){ if _tty; then printf '\033[33m[skill-install] WARN\033[0m %s\n' "$*" >&2; else printf '[skill-install] WARN %s\n' "$*" >&2; fi; }
die(){ if _tty; then printf '\033[31m[skill-install] ERROR\033[0m %s\n' "$*" >&2; else printf '[skill-install] ERROR %s\n' "$*" >&2; fi; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

have curl    || die "需要 curl"
have tar     || die "需要 tar"
have python3 || die "需要 python3（用于解析 registry.json）"

# ---------- 拆出全局选项，剩下的是命令+参数 ----------
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --gitee)     USE_GITEE=1 ;;
    --codex)     MIRROR_CODEX=1 ;;
    --workbuddy) MIRROR_WORKBUDDY=1 ;;
    --dir)       INSTALL_DIR="${2:?--dir 需要路径}"; shift ;;
    --ref)       REF_OVERRIDE="${2:?--ref 需要值}"; shift ;;
    -h|--help)   sed -n '2,40p' "$0" 2>/dev/null || true; exit 0 ;;
    *)           ARGS+=("$1") ;;
  esac
  shift
done
set -- "${ARGS[@]:-}"
CMD="${1:-list}"; shift || true

# ---------- 拉取 registry.json ----------
REG_REF="${REF_OVERRIDE:-$DEFAULT_BRANCH}"
fetch_registry(){
  local url
  if [ "$USE_GITEE" = 1 ] && [ -n "$GITEE_OWNER_REPO" ]; then
    url="$GITEE_BASE/$GITEE_OWNER_REPO/raw/$REG_REF/skills/registry.json"
  else
    url="$RAW_GH/$GH_OWNER_REPO/$REG_REF/skills/registry.json"
  fi
  curl -fsSL "$url" 2>/dev/null || die "拉取 registry 失败：$url"
}

# 本地优先：如果脚本旁边就有 registry.json（在本仓库里跑），直接用，省一次网络。
# 经 curl|bash 管道执行时没有脚本文件，BASH_SOURCE[0] 未设 → set -u 会炸；回退到 $0 并容错。
SELF_SRC="${BASH_SOURCE[0]:-${0:-}}"
SELF_DIR="$(cd "$(dirname "$SELF_SRC")" 2>/dev/null && pwd || true)"
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/registry.json" ] && [ -z "$REF_OVERRIDE" ]; then
  REGISTRY="$(cat "$SELF_DIR/registry.json")"
else
  REGISTRY="$(fetch_registry)"
fi

# registry 里若声明了 repo 段，覆盖默认坐标
eval "$(REGISTRY="$REGISTRY" python3 - <<'PY'
import os, json
reg = json.loads(os.environ["REGISTRY"]); repo = reg.get("repo", {})
def emit(k, v):
    if v: print(f'{k}="{v}"')
emit("GH_OWNER_REPO", repo.get("github"))
emit("GITEE_OWNER_REPO", repo.get("gitee"))
emit("DEFAULT_BRANCH", repo.get("default_branch"))
PY
)"

# ---------- python 解析助手 ----------
PY_HELPER='
import os, sys, json
reg = json.loads(os.environ["REGISTRY"])
repo = reg.get("repo", {}); defbranch = repo.get("default_branch", "main")
skills = reg.get("skills", {})
cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
def meta(name, version):
    s = skills.get(name)
    if not s: sys.exit(3)
    if version and version not in ("", "latest"):
        ref = s.get("tag") or f"{name}-v{version}"
    else:
        ref = s.get("branch") or defbranch
    print(ref)
    print(s.get("path", ""))
    print("|".join(s.get("extra_paths", [])))
    print(" ".join(s.get("env", [])))
    print(" ".join(s.get("pip", [])))
    print(" ".join(s.get("system_deps", [])))
    print(s.get("title", name))
if cmd == "meta":
    meta(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
elif cmd == "list":
    for n, s in skills.items():
        cred = "[需凭证]" if s.get("needs_credentials") else "       "
        print("  %-18s v%-7s %s %s" % (n, s.get("version", "?"), cred, s.get("title", "")))
elif cmd == "search":
    q = sys.argv[2].lower()
    for n, s in skills.items():
        blob = (n + " " + s.get("title", "") + " " + s.get("description", "")).lower()
        if q in blob:
            print("  %-18s v%-7s %s" % (n, s.get("version", "?"), s.get("title", "")))
'
reg_py(){ REGISTRY="$REGISTRY" python3 -c "$PY_HELPER" "$@"; }

# ---------- tarball 下载 + 解压 ----------
download_and_extract(){   # $1=ref ; stdout=解压出的顶层目录绝对路径
  local ref="$1" tmp url
  tmp="$(mktemp -d)"
  if [ "$USE_GITEE" = 1 ] && [ -n "$GITEE_OWNER_REPO" ]; then
    url="$GITEE_BASE/$GITEE_OWNER_REPO/repository/archive/$ref.tar.gz"
  else
    # 裸 tar.gz/<ref> 同时支持 分支 / tag / commit SHA（codeload 三者皆 200），无需区分 ref 类型
    url="$CODELOAD_GH/$GH_OWNER_REPO/tar.gz/$ref"
  fi
  log "下载 $url"
  curl -fsSL "$url" -o "$tmp/archive.tgz" 2>/dev/null || die "下载失败（ref=$ref 可能不存在）：$url"
  # 校验是 gzip
  if ! tar -tzf "$tmp/archive.tgz" >/dev/null 2>&1; then die "归档无效（404/限流？）：$url"; fi
  tar -xzf "$tmp/archive.tgz" -C "$tmp" || die "解压失败"
  local top; top="$(tar -tzf "$tmp/archive.tgz" | head -1 | cut -d/ -f1)"   # 顶层目录名是 repo-ref，别写死
  [ -n "$top" ] && [ -d "$tmp/$top" ] || die "解压结构异常"
  printf '%s\n' "$tmp/$top"
}

copy_dir(){   # $1=src_dir $2=相对目标
  local src="$1" rel="$2"
  [ -d "$src" ] || die "源缺少目录：$src"
  mkdir -p "$INSTALL_DIR/$(dirname "$rel")"
  rm -rf "$INSTALL_DIR/$rel"
  cp -R "$src" "$INSTALL_DIR/$rel"
  log "→ $rel"
}
copy_file(){  # $1=src_file $2=相对目标
  local src="$1" rel="$2"
  [ -f "$src" ] || { warn "源缺少文件，跳过：$rel"; return 0; }
  mkdir -p "$INSTALL_DIR/$(dirname "$rel")"
  cp "$src" "$INSTALL_DIR/$rel"
  log "→ $rel"
}

ensure_skill_link(){  # $1=相对软链接路径 $2=相对目标 $3=说明
  local rel="$1" target="$2" label="$3" full
  full="$INSTALL_DIR/$rel"
  mkdir -p "$INSTALL_DIR/$(dirname "$rel")"
  if [ -L "$full" ]; then
    ln -sfn "$target" "$full"
  elif [ -e "$full" ]; then
    if [ -d "$full" ] && [ -z "$(find "$full" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
      rmdir "$full"
      ln -s "$target" "$full"
    else
      warn "$rel 已存在且不是空目录/软链接，保留不改；请手动迁移到 skills/ 后改成软链接"
      return 0
    fi
  else
    ln -s "$target" "$full"
  fi
  log "→ $rel -> $target（$label）"
}

ensure_loader_links(){
  ensure_skill_link ".claude/skills" "../skills" "Claude"
  [ "$MIRROR_CODEX" = 1 ]     && ensure_skill_link ".agents/skills" "../skills" "Codex"
  [ "$MIRROR_WORKBUDDY" = 1 ] && ensure_skill_link ".workbuddy/skills" "../skills" "WorkBuddy"
}

install_one(){
  local spec="$1" name version meta ref path extras envs pips deps title base
  name="${spec%@*}"; version=""
  case "$spec" in *@*) version="${spec#*@}";; esac
  meta="$(reg_py meta "$name" "$version" 2>/dev/null)" || die "registry 里没有 skill：${name}（试试 'list'）"
  ref="$(sed -n 1p <<<"$meta")"
  path="$(sed -n 2p <<<"$meta")"
  extras="$(sed -n 3p <<<"$meta")"
  envs="$(sed -n 4p <<<"$meta")"
  pips="$(sed -n 5p <<<"$meta")"
  deps="$(sed -n 6p <<<"$meta")"
  title="$(sed -n 7p <<<"$meta")"
  [ -n "$REF_OVERRIDE" ] && ref="$REF_OVERRIDE"
  [ -n "$path" ] || die "$name 缺少 path 字段"
  log "安装 ${name}（${title}）@ $ref"
  local root; root="$(download_and_extract "$ref")"
  base="${path##*/}"
  copy_dir "$root/$path" "skills/$base"
  ensure_loader_links
  if [ -n "$extras" ]; then
    local IFS='|'; read -ra EX <<<"$extras"
    for e in "${EX[@]}"; do [ -n "$e" ] && copy_file "$root/$e" "$e"; done
  fi
  rm -rf "$(dirname "$root")"
  # 安装后提示
  printf '\n' >&2
  log "✅ $name 已装好。落地：skills/$base/"
  [ -n "$envs" ] && log "   需在 .env.local 配置：$envs"
  [ -n "$pips" ] && log "   可选 Python 依赖：pip install $pips"
  [ -n "$deps" ] && log "   系统依赖：$deps"
  log "   体检：bash scripts/setup.sh doctor   （或对外部仓库手动核对凭证）"
}

check_sync(){
  local ok=1
  check_one_link(){
    local rel="$1" target="$2"
    if [ ! -L "$INSTALL_DIR/$rel" ]; then
      warn "$rel 不是软链接"
      ok=0
      return
    fi
    local got; got="$(readlink "$INSTALL_DIR/$rel")"
    if [ "$got" != "$target" ]; then
      warn "$rel 指向 $got，期望 $target"
      ok=0
    fi
  }
  check_one_link ".claude/skills" "../skills"
  if [ -e "$INSTALL_DIR/.agents/skills" ] || [ -L "$INSTALL_DIR/.agents/skills" ]; then
    check_one_link ".agents/skills" "../skills"
  fi
  if [ -e "$INSTALL_DIR/.workbuddy/skills" ] || [ -L "$INSTALL_DIR/.workbuddy/skills" ]; then
    check_one_link ".workbuddy/skills" "../skills"
  fi
  INSTALL_DIR="$INSTALL_DIR" REGISTRY="$REGISTRY" python3 - <<'PY' || ok=0
import json, os, re, sys
from pathlib import Path

root = Path(os.environ["INSTALL_DIR"])
reg = json.loads(os.environ["REGISTRY"])
skills = reg.get("skills", {})
errors = []

for name, meta in sorted(skills.items()):
    path = root / meta.get("path", "") / "SKILL.md"
    if not path.exists():
        errors.append(f"{name}: missing {path.relative_to(root)}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^version:\s*(.+)$", text, re.M)
    actual = match.group(1).strip().strip('"') if match else ""
    expected = str(meta.get("version", ""))
    if actual != expected:
        errors.append(f"{name}: version {actual or '(missing)'} != registry {expected}")

disk = {
    p.parent.name
    for p in (root / "skills").glob("*/SKILL.md")
}
missing = sorted(disk - set(skills))
for name in missing:
    errors.append(f"{name}: exists in skills/ but is missing from registry.json")

if errors:
    for error in errors:
        print(f"[skill-install] WARN {error}", file=sys.stderr)
    sys.exit(1)

print(f"[skill-install] OK {len(skills)} skills registered and version-matched")
PY
  [ "$ok" = 1 ] || die "skill 同步检查失败"
  log "skill 入口同步正常"
}

case "$CMD" in
  list)
    log "可安装的 skill（仓库：$GH_OWNER_REPO @ ${DEFAULT_BRANCH}）："
    reg_py list ;;
  search)
    [ $# -ge 1 ] || die "用法：search <关键词>"
    reg_py search "$1" ;;
  install)
    [ $# -ge 1 ] || die "用法：install <skill>[@版本] [更多…]"
    for s in "$@"; do install_one "$s"; done ;;
  update)
    if [ "${1:-}" = "--all" ]; then
      for n in $(REGISTRY="$REGISTRY" python3 -c '
import os,json;[print(k) for k in json.loads(os.environ["REGISTRY"]).get("skills",{})]'); do
        { [ -d "$INSTALL_DIR/skills/$n" ] || [ -d "$INSTALL_DIR/.claude/skills/$n" ]; } && install_one "$n"
      done
    else
      [ $# -ge 1 ] || die "用法：update <skill> | --all"
      for s in "$@"; do install_one "$s"; done
    fi ;;
  installed)
    log "已安装（$INSTALL_DIR/skills/）："
    for d in "$INSTALL_DIR"/skills/*/SKILL.md; do
      [ -f "$d" ] || continue
      n="$(basename "$(dirname "$d")")"
      v="$(grep -m1 '^version:' "$d" | sed 's/version:[[:space:]]*//' || true)"
      printf '  %-18s %s\n' "$n" "${v:-(无版本号)}"
    done ;;
  check-sync)
    check_sync ;;
  *) die "未知命令：${CMD}（list | search | install | update | installed | check-sync）" ;;
esac
