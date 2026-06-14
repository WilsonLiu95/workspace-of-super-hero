---
name: feishu-cli
description: 用官方 lark-cli（@larksuite/cli）操作飞书/Lark，并按本工作区契约归档。触发场景：「拉飞书聊天/群消息」「同步飞书文档」「飞书云文档/Drive/Wiki/多维表格/日历/通讯录」「把成品发到飞书」「lark-cli」「feishu CLI」「Lark API」。凭证由采用者在 ~/.lark-cli 管理；原始数据只写 sources/feishu/。
---

# 飞书 CLI

用官方 `lark-cli` 操作飞书/Lark。这个 Skill 只保留工作区规则；命令细节以 `lark-cli --help` 和 `lark-cli schema ...` 为准。

## 前置

- 若本机没有 `lark-cli`，提示安装：`npm i -g @larksuite/cli`。
- 操作前检查身份：`lark-cli auth status`；连通性问题用 `lark-cli doctor`。
- 凭证、token、app secret 只允许由 `lark-cli config/auth` 写到 `~/.lark-cli`，不要写入仓库。

## 命令规则

- 不要凭记忆猜接口名或参数。先用 `lark-cli <组> --help`、`lark-cli <组> <命令> --help` 或 `lark-cli schema <service.resource.method>` 查。
- 读个人会话/文档通常用 `--as user`；机器人发消息通常用 `--as bot`。
- 分页用 `--page-all`，必要时加 `--page-limit`、`--page-size`、`--page-delay`。
- 写操作必须先加 `--dry-run` 看请求内容；确认目标、正文、权限无误后再执行。

## 拉取到 sources

批量拉取优先用 `scripts/pull-feishu.sh`。交互式精细操作可直接用 `lark-cli im/docs/drive/wiki/...`。

所有原始数据只写入：

```text
sources/feishu/<tenant>/<dm|groups|docs>/YYYY-MM-DD_<slug>.md
```

frontmatter 必须包含：

```yaml
---
source: feishu
tenant: <租户名>
channel: <会话/群/文档名>
type: dm
captured: YYYY-MM-DD
---
```

`type` 取 `dm`、`group` 或 `doc`。不确定租户、类型或频道时，先写到 `sources/inbox/` 并说明待归档原因。

## 回写飞书

只有用户明确要求“发到飞书 / 创建飞书文档 / 覆盖飞书文档”时才回写。不要因为拉取或整理原始数据而修改 `deliverables/`。

回写前必须：

1. 用 `--dry-run` 预览请求。
2. 明确目标 chat/doc/drive 位置。
3. 不在仓库中保存 token、secret 或导出的私密临时文件。

## 红线

- 飞书会话、文档、云盘内容默认是私密原始数据，只能落到 `sources/`，不要外泄。
- 不要修改或删除 `sources/` 已有原始文件；需要更新时追加新文件。
- 删除、覆盖、群发等高风险操作必须再次向用户确认。
