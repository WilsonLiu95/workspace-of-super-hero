---
name: feishu-cli
description: 用官方 lark-cli（@larksuite/cli）操作飞书/Lark —— 把单聊/群聊/文档/云盘内容拉进 sources/feishu/，或把 deliverables/feishu/ 的成品回写到飞书。触发场景：「拉飞书聊天/群消息」「同步飞书文档到本地」「把这份文档发到飞书」「飞书云文档/Drive/Wiki/多维表格/日历/通讯录」「lark-cli」「feishu CLI」「Lark API」。需采用者自带飞书应用凭证（app-id/app-secret）并登录；凭证存于 ~/.lark-cli，不进本仓库。
---

# 飞书 CLI（lark-cli）

用官方 **`lark-cli`**（npm 包 `@larksuite/cli`）在命令行操作飞书/Lark，并与本工作区的 `sources/` ↔ `deliverables/` 打通。

> **本模板不含任何飞书凭证。** 采用者自带自己的飞书应用（app-id/app-secret）并登录；凭证由 lark-cli 存在 `~/.lark-cli`（仓库外），不会进 git。

## 0. 安装与登录（一次性）

```bash
npm i -g @larksuite/cli           # 安装；lark-cli --version 验证
lark-cli config init              # 输入 app-id / app-secret（--app-secret-stdin 从 stdin 读）
lark-cli auth login               # 设备码（Device Flow）授权登录
lark-cli auth status              # 看当前登录身份
lark-cli doctor                   # 体检：配置 / 鉴权 / 连通性
```

- **身份**：很多命令支持 `--as user|bot`（用户身份 / 机器人身份）。读个人会话用 `--as user`，机器人发消息用 `--as bot`。
- 缺权限时：`lark-cli auth scopes` 看应用已开 scope，`lark-cli auth check` 验证某 scope 是否就绪。

## 1. 通用约定

- 命令形态：`lark-cli <命令组> <子命令> [--params <json>] [--data <json>]`。带 `+` 前缀的是封装好的高频动作（如 `im +chat-list`）。
- 发现命令/参数（**不要凭记忆猜方法名**）：`lark-cli <组> --help`、`lark-cli schema <service.resource.method>`。
- 输出：`--format json|ndjson|table|csv|pretty`；`--jq '<expr>'`（或 `-q`）过滤 JSON；`-o <path>` 存二进制。
- 分页：`--page-all` 自动翻页（配 `--page-limit`、`--page-size`、`--page-delay`）。
- **先 `--dry-run`**：写操作（发消息、建/改文档）前先 `--dry-run` 打印请求确认无误，再真正执行。

## 2. 拉数据 → 写入 sources/feishu/

落盘遵循本工作区契约（见 `sources/feishu/README.md`）：路径 `sources/feishu/<租户>/<dm|groups|docs>/`，文件名 `YYYY-MM-DD_<slug>.md`，并补 source frontmatter（`source: feishu` / `tenant` / `channel` / `type` / `captured`）。

**单聊 / 群聊消息（im）**

```bash
lark-cli im +chat-list --as user --format table          # 列出我所在的群/会话，拿 chat_id
lark-cli im +chat-search --query "产品周会" --as user      # 按群名搜 chat_id
lark-cli im +chat-messages-list --as user \
  --params '{"chat_id":"<chat_id>"}' --page-all           # 拉某会话消息（支持时间范围/分页）
lark-cli im +messages-search --query "评审" --as user      # 跨会话搜消息
```

把结果整理成 Markdown 写入 `sources/feishu/<租户>/groups/2026-06-14_产品周会同步.md`（单聊放 `dm/`）。

**云文档 / 云盘（docs / drive / markdown / wiki）**

```bash
lark-cli docs +search --query "PRD" --as user             # 搜文档，拿 URL/token
lark-cli docs +fetch --params '{"document_id":"<id>"}'     # 取文档内容
lark-cli drive +export ...                                 # 导出 doc/sheet/bitable 到本地文件
lark-cli drive +pull ...                                   # 把整个 Drive 文件夹单向镜像到本地目录
lark-cli wiki +node-list / +node-get                       # 浏览 Wiki 空间/节点
```

`drive +pull`（Drive→本地单向镜像）适合定期把某个飞书文件夹同步进 `sources/feishu/<租户>/docs/`。取回后补 frontmatter。

## 3. 回写 deliverables/feishu/ → 飞书

把 `deliverables/feishu/*.md` 成品发到飞书，再把回链写回该交付物 frontmatter 的 `published_url`、并把 `status` 改为 `final`/`published`：

```bash
# 方式 A：作为 Drive 原生 Markdown 文件
lark-cli markdown +create   --dry-run ...                  # 在 Drive 新建 md 文件
lark-cli markdown +overwrite ...                           # 覆盖已有 md 文件
lark-cli markdown +patch ...                               # fetch→本地替换→overwrite

# 方式 B：作为飞书云文档（docx）
lark-cli docs +create ... / lark-cli docs +update ...
lark-cli drive +import ...                                 # 本地文件导入为云文档

# 发到某个聊天/某人
lark-cli im +messages-send --as bot --dry-run \
  --params '{"receive_id":"<chat_id>"}' --data '{"msg_type":"text","content":"..."}'
```

具体参数以 `lark-cli <组> <子命令> --help` 为准。

## 4. 其它能力（按需）

`calendar`(日历) · `contact`(通讯录) · `base`/`sheets`(多维表格/电子表格) · `task`(任务) · `approval`(审批) · `mail`(邮箱) · `minutes`/`vc`(妙记/会议) · `okr`。用 `lark-cli <组> --help` 探索。

**通用 API 兜底**（封装命令没覆盖时）：

```bash
lark-cli api GET  /open-apis/im/v1/chats --params '{"page_size":20}'
lark-cli api POST /open-apis/... --data '{...}'
lark-cli schema im.message.list --format pretty            # 查某方法的参数/类型/所需 scope
```

飞书开放平台文档：https://open.feishu.cn/document/

## 红线

- 写操作（发消息、建/改/删文档）前先 `--dry-run` 确认；删除类操作格外谨慎。
- 拉回的会话/文档含私密信息：落到 `sources/`（默认不进 git，见根 `.gitignore`），不要外泄。
- 不要把 app-secret/token 写进仓库；凭证只在 `~/.lark-cli`，用 `lark-cli config`/`auth` 管理。
