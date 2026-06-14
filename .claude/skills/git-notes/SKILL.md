---
name: git-notes
description: Git 操作速查与本工作区的版本管理约定 —— 提交/分支/撤销/查看历史/.gitignore/解决冲突，以及本仓库"只跟踪结构与示例、忽略真实来源数据"的隐私规则。触发场景：「提交一下」「怎么撤销」「回退到上一个版本」「看看改了啥」「建个分支」「.gitignore 怎么写」「合并冲突」「git 笔记」「这个文件怎么没被跟踪」。
---

# Git 笔记（含本工作区约定）

实用 git 速查，并嵌入**本工作区的版本管理规则**。先读「本仓库特有」一节，再用下面的速查。

## 本仓库特有（重要）

- **隐私优先**：`sources/` 装私密聊天/文档。根 `.gitignore` 用 `sources/**` + 反向规则，**只跟踪目录结构、各 README 和 `_example-*` 示例**，忽略真实数据。
  - 验证某文件是否被忽略：`git check-ignore -v <path>`（有输出=被忽略，并显示命中规则）。
  - 想确认"我新加的真实飞书数据没进暂存区"：`git status --short`，不应看到它。
- **远端必须私有**：若 `git remote add` 接远端，仓库**必须设为 private**（含私密数据时）。推前自检：`git ls-files | grep -iE 'secret|token|\.env'` 应为空。
- `.claude/settings.local.json` 是每人本地设置，被全局 gitignore 忽略，不随模板分享；`.claude/skills/` 会跟踪并随模板分享。

## 日常速查

```bash
git status -s                 # 简洁看改动
git diff                      # 工作区 vs 暂存区（未 add 的改动）
git diff --staged             # 暂存区 vs 上次提交（已 add、将提交的）
git add -A                    # 暂存全部改动（含删除）
git add -p                    # 交互式逐块挑选要暂存的改动
git commit -m "msg"           # 提交
git commit --amend            # 改最近一次提交（信息或补文件）；已推送过就别 amend
git log --oneline -10         # 近 10 条提交
git log --oneline -- <path>   # 某文件的提交历史
git show <commit>             # 看某次提交的全部改动
```

## 撤销 / 回退（按"改到哪了"选）

```bash
# 还没 commit：
git restore <file>            # 丢弃工作区对该文件的修改（恢复到暂存/HEAD）
git restore --staged <file>   # 取消暂存（保留工作区改动）
git restore --source=HEAD .   # 丢弃全部未提交改动（危险，确认后再用）

# 已 commit、还没 push：
git reset --soft HEAD~1       # 撤销上一次提交，改动留在暂存区（最常用、最安全）
git reset --mixed HEAD~1      # 撤销提交，改动退回工作区（默认）
git reset --hard HEAD~1       # 撤销提交并丢弃改动（危险，不可逆）

# 已 push（不能改写历史）：
git revert <commit>           # 生成一个"反向提交"来抵消，安全

# 救命：
git reflog                    # 找回"误 reset/误删分支"前的提交，再 git reset --hard <hash>
```

## 分支

```bash
git switch -c <branch>        # 新建并切换（旧写法 git checkout -b）
git switch <branch>           # 切换
git branch -d <branch>        # 删除已合并分支（-D 强删）
git merge <branch>            # 把 <branch> 合并进当前分支
git stash / git stash pop     # 临时收起改动 / 取回，用于切分支前
```

## .gitignore 速记

- 反向放行用 `!`，但**父目录被忽略时，里面的文件无法被 `!` 放行** —— 需先用 `!dir/` 放行目录再放行文件（本仓库 `sources/**` + `!sources/**/` 就是这个套路）。
- 已被跟踪的文件，加进 .gitignore 不会自动停跟踪：`git rm --cached <path>` 后提交。
- 调试规则命中：`git check-ignore -v <path>`。

## 合并冲突

```bash
git status                    # 看哪些文件冲突（both modified）
# 手动编辑，删掉 <<<<<<< / ======= / >>>>>>> 标记，留下想要的内容
git add <file>                # 标记已解决
git commit                    # 完成合并（merge 时）
git merge --abort             # 放弃这次合并，回到合并前
```

## 提交信息小约定

- 一行祈使句概要（≤72 字），需要再空行加正文说明"为什么"。
- 常用前缀：`feat:` / `fix:` / `chore:` / `docs:` / `refactor:`。
