---
name: wechat-exporter
description: |
  微信公众号文章导出工具。拉取任意公众号的全部历史文章列表并导出为 JSON、Excel、Markdown、TXT。
  当用户提到以下意图时必须触发：「导出公众号文章」「拉取公众号」「微信文章」「公众号历史文章」
  「wechat article」「公众号导出」「下载公众号」「备份公众号」「公众号文章列表」。
  即使用户只说「帮我拉一下某某公众号的文章」也应该触发此技能。
version: 0.1.0
updated: "2026-06-15"
---

# 微信公众号文章导出 Skill

纯 Python 实现，零外部服务依赖。将任意微信公众号的全部历史文章拉取并导出。

> **本工作区集成**：这是 **公众号**（mp）导出，不是微信聊天（聊天记录用 `wechat-chatlog`）。
> **在仓库根运行**；产物落到 `sources/mp/<公众号名>/`；会话/二维码状态用仓库内 `.tmp/`（已 gitignored），
> 首次先 `mkdir -p .tmp`。`sources/` 默认不进 git（见根 `.gitignore`）。
> 这是**交互式按需**技能（需扫码登录微信公众平台），不纳入 `pull-all.sh` 的每日自动拉取。

## 依赖安装

首次使用前在 Bash 中执行：

```bash
pip install requests openpyxl --break-system-packages
# 可选（Markdown/TXT 导出需要）：
pip install markdownify beautifulsoup4 --break-system-packages
```

## 使用方式

所有脚本位于本 Skill 的 `scripts/` 目录下。使用时将该目录加入 `sys.path`。

**路径常量**（在所有代码段中直接使用这些值，无需替换占位符）：

```python
SKILL_DIR   = ".claude/skills/wechat-exporter"
OUTPUT_DIR  = "sources/mp"
SESSION_FILE = ".tmp/wechat_session.json"
QR_PATH     = ".tmp/wechat_qrcode.png"
QR_STATE_FILE = ".tmp/.wechat_qr_state.json"
```

---

## 完整流程（严格按步骤执行）

### 第 1 步：检查已有 Session

每次执行都必须先尝试复用已保存的 session，避免重复扫码：

```python
import sys, os
sys.path.insert(0, ".claude/skills/wechat-exporter/scripts")
from qr_login import SessionManager
from wechat_api import WeChatMPClient

session_file = ".tmp/wechat_session.json"
manager = SessionManager(session_file=session_file)

need_login = True
if manager.load_session() and manager.check_session_valid():
    print("Session 有效，无需扫码")
    client = WeChatMPClient(token=manager.token, cookie=manager.cookie_string)
    need_login = False
```

如果 `need_login` 为 False，**直接跳到第 3 步**。

---

### 第 2 步：QR 码扫码登录（仅 session 无效时）

⚠️ **这一步包含与用户的交互，必须严格分两段执行，中间等待用户回复。**

#### 第 2a 步：生成 QR 码并发给用户

执行以下代码生成 QR 码图片，**并保存 QR 会话状态**：

```python
from qr_login import QRLogin

qr = QRLogin()
qr.start_login()
qr_path = ".tmp/wechat_qrcode.png"
qr_state_file = ".tmp/.wechat_qr_state.json"
qr.get_qrcode(qr_path)
qr.save_qr_state(qr_state_file)   # ← 关键：持久化 session cookies，供下一 turn 恢复
```

然后 **必须立刻停止执行后续代码**，使用 Read 工具读取图片文件并将其嵌入回复发给用户：

```
read(qr_path)  # 调用 Read 工具读取 PNG，图片会内嵌在回复中
```

回复示例：

---
请用微信扫描下面的二维码，扫完后在手机上点「确认登录」，然后告诉我。

（此处嵌入 Read 工具读取的 QR 码图片）

二维码有效期约 5 分钟，请尽快扫码。
---

然后 **等待用户回复**（如「扫了」「扫码了」「扫完了」「ok」等）。

#### 第 2b 步：完成登录（用户确认扫码后才执行）

收到用户确认后，**先恢复 QR 状态再 poll**，否则跨 turn 会超时：

```python
from qr_login import QRLogin

qr = QRLogin()
qr_state_file = ".tmp/.wechat_qr_state.json"
qr.load_qr_state(qr_state_file)   # ← 关键：恢复上一 turn 的 session cookies
```

然后继续：

```python
qr.poll_scan_status(timeout=180)
token = qr.complete_login()
cookie = qr.get_cookie_string()
cookies_dict = qr.get_cookies_dict()

# 立即保存 session（关键！不保存下次还要扫码）
session_file = ".tmp/wechat_session.json"
manager = SessionManager(session_file=session_file)
manager.save_session(token, cookies_dict, cookie)

client = WeChatMPClient(token=token, cookie=cookie)
print("登录成功，session 已保存")
```

如果 poll 超时或报错（如二维码过期），需要 **回到第 2a 步重新生成 QR 码**。

---

### 第 3 步：搜索公众号

```python
keyword = "用户指定的公众号名称"
accounts = client.search_accounts(keyword)

if not accounts:
    print(f"未找到与「{keyword}」相关的公众号")
else:
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. {acc['nickname']} ({acc.get('alias', '')})")
    target = accounts[0]
```

如果搜索到多个结果，列出选项让用户确认。只有一个结果时直接使用。

### 第 4 步：拉取全部文章

```python
articles = client.fetch_all_articles(fakeid=target["fakeid"])
print(f"共拉取 {len(articles)} 篇文章")
```

此步骤会自动分页，每页间隔 3 秒。耐心等待即可。

### 第 5 步：导出文件

```python
from exporter import ArticleExporter

output_dir = os.path.join("sources/mp", target["nickname"])
exporter = ArticleExporter(
    articles=articles,
    output_dir=output_dir,
    account_name=target["nickname"],
)

json_path = exporter.export_json()    # → articles.json
excel_path = exporter.export_excel()  # → articles.xlsx
```

导出完成后，将文件路径告知用户：

```
导出完成！共 {len(articles)} 篇文章：
- 文章列表 JSON：{json_path}
- 文章列表 Excel：{excel_path}
```

#### 可选：下载文章全文并转为 Markdown/TXT

```python
# 下载 HTML 原文（较慢，每篇间隔 3 秒）
html_dir = os.path.join(output_dir, "html")
client.batch_download_html(articles, output_dir=html_dir)

# 转为 Markdown（需 pip install markdownify beautifulsoup4）
exporter.export_markdown(html_dir=html_dir)

# 转为纯文本
exporter.export_txt(html_dir=html_dir)
```

---

## 一站式函数（简化调用）

如不需要分步控制，可用一个函数搞定。但注意：**函数内部在 QR 码生成后会打印路径并轮询，Agent 需要在调用前先告知用户即将生成 QR 码**。

```python
from qr_login import qr_login_and_fetch

result = qr_login_and_fetch(
    account_keyword="公众号名称",
    output_dir="sources/mp/公众号名称",
    qrcode_path=".tmp/wechat_qrcode.png",
    session_file=".tmp/wechat_session.json",
    export_formats=["json", "excel"],
)
```

推荐用分步流程（第 1-5 步），交互体验更好。

---

## Credential 模式（免登录替代方案）

如果用户已有抓包参数（`__biz`、`uin`、`key`、`pass_ticket`）：

```python
from wechat_api import WeChatCredentialClient

client = WeChatCredentialClient(
    biz="MzI1...", uin="MTc...", key="a1b2...", pass_ticket="xxx"
)
articles = client.fetch_all_articles()
```

Credential 有效期约 25 分钟。一般用户不需要此模式。

---

## 关键注意事项

| 事项 | 说明 |
|------|------|
| QR 码有效期 | 约 5 分钟，生成后必须立刻展示给用户 |
| Session 有效期 | 约 4 小时，保存后可通过 `refresh_session()` 延长 |
| API 限速 | 默认每次请求间隔 3 秒，不要调低 |
| 空页处理 | 分页中可能有空页，连续 3 个空页才停止 |
| 频率限制 | 遇到 200013 错误码自动等 60 秒重试 |
| 文章总数 | `total_count` 是发布事件数，实际文章数可能更多（多图文） |
| 扫码报错 | 如出现「系统错误」，可能是 IP 被风控，等几分钟换网络再试 |

## 文件结构

```
.claude/skills/wechat-exporter/
├── SKILL.md              # 本文件
└── scripts/
    ├── __init__.py
    ├── qr_login.py       # QR 登录 + Session 持久化 + QR 状态持久化
    ├── wechat_api.py     # API 客户端（两种模式）
    └── exporter.py       # 多格式导出器
```
