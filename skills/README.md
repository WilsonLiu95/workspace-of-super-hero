# skills/ — Skill 唯一真源（本体 + 清单 + 一行安装器）

这个目录是本工作区的 **skill 唯一真源**。每个 skill 的本体都在 `skills/<name>/`；Claude / Codex 的默认入口只保留软链接：

```text
.claude/skills -> ../skills
.agents/skills -> ../skills
```

因此不要维护 `.claude/skills` 与 `.agents/skills` 两份内容；改 skill 时只改 `skills/<name>/`。

| 文件 | 作用 |
| --- | --- |
| `<name>/SKILL.md` | Skill 本体，Claude / Codex 通过软链接读到同一份。 |
| `registry.json` | **清单**：每个 skill 的版本、路径、依赖、所需环境变量。安装器读它。 |
| `install.sh` | **一行安装器**：按 `registry.json` 从 Git 仓库 `tarball@ref` 拉取 skill 装进目标仓库。 |

## 一行安装（在「目标仓库根目录」执行）

```bash
# 装一个
curl -fsSL https://raw.githubusercontent.com/WilsonLiu95/workspace-of-super-hero/main/skills/install.sh | bash -s -- install dingtalk

# 装指定版本（需先打了 tag，见下）、并同时创建 Codex 和 WorkBuddy 入口软链接
curl -fsSL https://raw.githubusercontent.com/WilsonLiu95/workspace-of-super-hero/main/skills/install.sh | bash -s -- install tencent-meeting@0.1.0 --codex --workbuddy

# 看有哪些 / 搜
curl -fsSL .../skills/install.sh | bash -s -- list
curl -fsSL .../skills/install.sh | bash -s -- search 会议
```

本仓库内直接用本地副本（省一次网络，且优先读旁边的 registry.json）：

```bash
skills/install.sh list
skills/install.sh install blog
skills/install.sh installed
skills/install.sh update --all
skills/install.sh check-sync
```

### 装到哪

- 默认：`./skills/<name>/`，并确保 `./.claude/skills -> ../skills`（Claude）。
- `--codex`：确保 `./.agents/skills -> ../skills`（Codex）。
- `--workbuddy`：确保 `./.workbuddy/skills -> ../skills`（腾讯 WorkBuddy）。
- 共享脚本（如 `scripts/pull-feishu.sh`、`scripts/lib/common.sh`）按 `extra_paths` 原样放到对应位置。
- `--gitee` 走 Gitee 镜像（需在 `registry.json` 的 `repo.gitee` 填好）；`--dir <path>` 改安装根。

装完安装器会提示该 skill 需要的环境变量 / pip / 系统依赖，并建议跑 `scripts/setup.sh doctor` 体检。

## 版本与发布（维护者）

**版本号**写在两处且必须一致：
1. 每个 `skills/<name>/SKILL.md` frontmatter 的 `version:`（语义化版本 semver）。
2. `skills/registry.json` 里该 skill 的 `version`。

**发布一个不可变版本** = 打一个 git tag，命名 `<name>-v<版本>`：

```bash
# 例：发布 dingtalk 0.2.0
# 1) 改 skills/dingtalk/SKILL.md 的 version: 0.2.0
# 2) 同步 skills/registry.json 里 dingtalk.version
git add -A && git commit -m "feat(dingtalk): v0.2.0 …"
git tag dingtalk-v0.2.0
git push && git push --tags
```

之后 `install dingtalk@0.2.0` 会拉 `dingtalk-v0.2.0` 这个 tag（内容冻结）；不带 `@版本` 则永远拉 `default_branch`（main）上的最新。

> 没打 tag 时 `@版本` 会 404——先 push tag 再分发。日常迭代不打 tag、直接装 main 也完全可用。

## 新增一个 skill

1. 在 `skills/<name>/` 写 `SKILL.md`（frontmatter 必含 `name` `description` `version` `updated`）+ 实现脚本。
   - 新 skill 尽量**自包含**：实现放进自己的 `scripts/` 子目录，不依赖仓库顶层 `scripts/`，这样装到别的仓库也能跑。
2. 在 `registry.json` 的 `skills` 里加一条（version / title / description / path / extra_paths / needs_credentials / env / system_deps / pip）。
3. 若要可发版本：打 `<name>-v<版本>` tag。
4. 在 `scripts/setup.sh` 的集成清单里登记（让首次引导能勾选到它），并在 `.env.example` 补该 skill 的环境变量。
5. 跑 `skills/install.sh check-sync`，确认软链接、registry、frontmatter 版本一致。

## 设计取舍

- **tarball@ref，不 clone**：按 ref（分支或 tag）下载仓库归档，只取需要的子目录/文件，不留 `.git`，GitHub / Gitee 都通。
- **registry 是单一事实源**：安装、版本、依赖、环境变量都从这里读，安装器本身不写死 skill 列表。
- **跨 Agent 同源**：一份 skill，Agent 约定目录只做软链接；实现不分叉（见根 `CLAUDE.md` §8）。
