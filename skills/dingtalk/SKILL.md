---
name: dingtalk
description: 把钉钉的通讯录与文档/知识库归档进 sources/dingtalk/，用自建「企业内部应用」凭证。触发场景：「拉钉钉通讯录」「同步钉钉组织架构」「归档钉钉文档/知识库/钉盘」「导出钉钉部门成员」「DingTalk 通讯录」「钉钉 API」。实现是自包含脚本 scripts/pull-dingtalk.sh + scripts/dingtalk_client.py（仅标准库）。需 DINGTALK_APP_KEY / DINGTALK_APP_SECRET，且管理员已授予相应读权限。注意：钉钉不开放历史聊天记录 API，本技能不拉聊天。
version: 0.1.0
updated: "2026-06-15"
---

# 钉钉归档 (DingTalk)

用自建**企业内部应用**的凭证，把钉钉的**通讯录**（默认）和**文档/知识库/钉盘**（可选）归档进 `sources/dingtalk/<租户>/`。

> 重要边界：**钉钉不开放历史聊天记录 API**——无法拉取任意 1:1 / 群聊的历史消息（平台限制）。本技能**只**归档通讯录与文档/知识库/钉盘。聊天内容只能通过机器人 webhook **前向接收**（超出本技能范围），或走**企业版会话存档**（需专业版/专属版 + 审批）。`chat/get` 仅返回应用自建群的元数据，不是消息来源，本技能不用它。

## 何时使用

- 「拉一下钉钉通讯录 / 组织架构」「导出某租户的部门成员名册」。
- 「把钉钉知识库 / 文档清单归档下来」。
- 需要把钉钉侧的人员/部门信息作为底稿，供后续合成交付物。
- **不适用**：拉历史聊天记录（钉钉无此 API，别尝试）。

## 前置（凭证与依赖）

1. **建应用**：钉钉开放平台 → 创建**企业内部应用**，拿到 `AppKey` / `AppSecret`。
2. **授权限**（管理员在钉钉后台为该应用勾选）：
   - 通讯录：**部门读权限 + 成员读权限**（否则 `topapi` 返回权限错误，即使 token 有效）。
   - 文档/知识库：**知识库读权限 / 钉盘读权限**（仅当 `DINGTALK_ARCHIVE` 含 `docs` 时需要）。
3. **填凭证**：仓库根 `.env.local`（已被 `.gitignore` 忽略）：
   ```ini
   DINGTALK_APP_KEY=your_app_key
   DINGTALK_APP_SECRET=your_app_secret
   DINGTALK_TENANT=default          # 可选，落盘目录名
   DINGTALK_ARCHIVE=contacts        # 可选，csv：contacts,docs
   ```
4. **依赖**：仅 `python3`（标准库，零 pip）。
5. **多租户叠加**（可选）：设环境变量 `TENANT=acme` 运行时，会在 `.env.local` 之上再叠加 `.env.acme.local`，便于多套钉钉凭证切换。

## 用法

```bash
# 默认：归档通讯录 → sources/dingtalk/<租户>/contacts/<日期>_contacts.md
bash skills/dingtalk/scripts/pull-dingtalk.sh

# 同时归档知识库/文档清单
DINGTALK_ARCHIVE=contacts,docs bash skills/dingtalk/scripts/pull-dingtalk.sh

# 指定租户 + 多租户凭证叠加（读 .env.acme.local）
TENANT=acme DINGTALK_TENANT=acme bash skills/dingtalk/scripts/pull-dingtalk.sh
```

脚本会：加载 `.env.local`（可选叠加 `.env.$TENANT.local`）→ 校验凭证 → 取并缓存两套 token（缓存到 `.tmp/dingtalk_token.json`，2 小时）→ 遍历部门树拉通讯录（可选拉知识库）→ 写 markdown。

## 落盘约定

- 通讯录：`sources/dingtalk/<租户>/contacts/<YYYY-MM-DD>_contacts.md`，按部门分组的成员表，frontmatter：
  ```yaml
  source: dingtalk
  tenant: <租户>
  channel: 通讯录
  type: contacts
  captured: <YYYY-MM-DD>
  ```
- 文档/知识库：`sources/dingtalk/<租户>/docs/<YYYY-MM-DD>_wiki_index.md`（`type: doc`，列出各 workspace 的节点清单与链接）。
- **仅追加**：目标文件已存在则**跳过不覆盖**（同日重复运行不会改写底稿）。
- token / 临时缓存落 `.tmp/`（已 gitignore）。

## 红线

- **两套 API 别混**：新版 `api.dingtalk.com` token 走 **header** `x-acs-dingtalk-access-token`；旧版 `oapi.dingtalk.com` token 走 **query** `?access_token=`。混用是最常见的 bug。
- **不拉聊天记录**：钉钉没有历史消息 API，不要实现、不要伪造。
- **权限缺失**：即使 token 有效，未授权的接口会返回权限错误。脚本对知识库 scope 缺失会**告警跳过**而非崩溃；通讯录失败会明确提示去后台授权。
- **凭证只走 `.env.local`**，绝不硬编码或提交。`sources/` 含组织通讯录等敏感信息，默认不进 git（见根 `.gitignore`），勿外泄。
- 该脚本自包含、只从环境变量读凭证，可被 Codex / 定时器直接复用。
