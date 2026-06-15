---
name: xiaoyuzhou
description: 拉取小宇宙播客内容（搜索、单集详情、Show Notes、逐字稿）作为研究素材。当用户需要研究某个领域、批量收集播客内容、做交叉分析时使用。
version: 0.1.0
authors:
  - 虾宝宝 (Wilson Liu) + Claude Opus 4.6
license: MIT
---

# xiaoyuzhou — 小宇宙播客拉取 Skill

这是一个用于从**小宇宙 FM** 批量拉取播客内容的 Skill，输出标准化的 Markdown 文件，可作为知识库内容源。

> **本工作区集成**：在仓库根运行；产物落到 `sources/social/`（与本工作区"小宇宙/播客归社媒来源"的约定一致），
> 即 `export XIAOYUZHOU_OUTPUT_DIR=sources/social`（也可写进根 `.env.local`）。登录凭据存 `~/.xiaoyuzhou/`（仓库外）、
> QR 存 `/tmp`，均不进 git。依赖：`pip install requests qrcode pillow`。`sources/` 默认不进 git（见根 `.gitignore`）。
> 这是**交互式按需**技能（需扫码），不纳入 `pull-all.sh` 的每日自动拉取。

## 何时使用这个 Skill

**触发场景**：
- 用户说"我要研究 X 领域，去小宇宙找相关播客"
- 用户给一个小宇宙播客 URL，要拉取所有单集和逐字稿
- 用户要做某个主题的交叉分析，需要把多个播客的内容当作素材
- 用户要把某个小宇宙节目导入到自己的知识库

**不要使用**：
- 用户只是想听一集播客（让他直接打开 App）
- 用户想下载音频文件（这个 skill 只拉文本元数据，不下载 mp3）

## 工作流（默认）

1. **首次使用必须先登录**：`python3 xiaoyuzhou.py login`
   - 终端会显示 QR 码（同时保存到 `/tmp/xiaoyuzhou_login_qr.png`）
   - 用户用**小宇宙 App** 扫码 → 在 App 上点"确认登录"
   - 凭据自动保存到 `~/.xiaoyuzhou/credentials.json`，后续免登录
   - 401 时自动 refresh token

2. **搜索播客**：`python3 xiaoyuzhou.py search --keyword "AI创业" --json`
   - 输出每个播客的 pid、标题、作者、订阅数
   - 用 `--type episode` 搜单集，`--type all` 搜全部
   - 用 pid 进入下一步拉取

3. **拉取单个播客的所有单集**：
   ```bash
   python3 xiaoyuzhou.py fetch --pid 63e9ef4de99bdef7d39944c8 \
     --with-transcript --limit 50 \
     --output-dir ./my-podcasts
   ```
   - 自动分页拉所有单集
   - `--with-transcript` 同时拉逐字稿（很多节目没开，会显示 "No transcript available"）
   - `--limit N` 限制拉前 N 集
   - 输出 Markdown 文件到 `output_dir/{播客名}/{YYYY-MM}/{date}-{title}.md`
   - 增量更新：再次运行只会拉新增/变化的单集

4. **批量拉取（领域研究核心场景）**：
   ```bash
   # 方式 A：按关键词自动找 top N 个相关播客并拉取
   python3 xiaoyuzhou.py batch --keyword "AI Agent" --top-podcasts 5 --with-transcript

   # 方式 B：直接给一组 pid
   python3 xiaoyuzhou.py batch --pids pid1,pid2,pid3 --with-transcript
   ```

5. **整合到知识库** (可选)：
   - 配合 SQLite FTS5 / 任何全文检索工具
   - 输出的 Markdown 文件天然适合 Obsidian / Logseq / Dify

## 快速开始（5 分钟跑通）

```bash
# 1. 安装依赖
pip install requests qrcode pillow

# 2. 登录（需要小宇宙 App 扫码 + 确认）
python3 xiaoyuzhou.py login

# 3. 搜索 → 找到一个 pid
python3 xiaoyuzhou.py search --keyword "AI创业"

# 4. 拉取那个播客的全部单集
python3 xiaoyuzhou.py fetch --pid <粘贴 pid> --with-transcript
```

## 输出格式

每集生成一个 Markdown 文件：

```markdown
# 单集标题

## Metadata
- Source: Xiaoyuzhou FM
- Podcast: 节目名
- Podcast ID: xxx
- Episode ID: xxx
- Published: 2026-04-09
- Duration: 1h 14m 55s
- Link: https://www.xiaoyuzhoufm.com/episode/xxx
- Tags: podcast, 节目名

## Show Notes
（HTML 已自动转纯文本）

## Transcript
（逐字稿，如果有）
```

## 三种登录方式

| 方式 | 命令 | 适用场景 |
|---|---|---|
| **QR 扫码（默认）** | `xiaoyuzhou.py login` | 普通用户首选，最快 |
| SMS 短信验证码 | `xiaoyuzhou.py login --sms` | 没装小宇宙 App / 在 CI 环境 |
| 手动输入 token | `xiaoyuzhou.py login --token` | 已经有 refresh_token |

也支持环境变量（适合自动化）：
```bash
export XIAOYUZHOU_REFRESH_TOKEN="..."
export XIAOYUZHOU_DEVICE_ID="..."
```

## 关键技术细节

- **认证 realm**: 用 `xyz-web` 客户端 ID（消费者 web 端），通过 `web-api.xiaoyuzhoufm.com/v1/auth/qrcode/create` 创建会话
- **数据 API**: 走 `api.xiaoyuzhoufm.com/v1/{search/create, episode/list, episode/get, episode-transcript/get}`
- **必需 header**: `x-midway-app-id: v6worU4NnWyL`
- **凭据**: 默认 `~/.xiaoyuzhou/credentials.json`，可通过 `XIAOYUZHOU_CREDENTIALS_PATH` 覆盖

## 常见问题

**Q: QR 扫码后状态变成 USED 但没有 token？**
A: 你扫的可能是 podcaster studio 的 QR 流程，而不是这个 skill 用的 xyz-web 流程。本 skill 用的是消费者端，扫码后需要在 App 上**点"确认登录"按钮**。

**Q: 拉取后所有单集都显示 "No transcript available"？**
A: 不是所有节目都开了逐字稿功能。小宇宙的逐字稿是节目主理人主动开启的。

**Q: 401 报错？**
A: token 过期了。脚本会自动 refresh 一次，如果还是失败，重新 `login`。

**Q: 拉的太快被限流？**
A: 脚本已经在每个 transcript 请求之间加了随机延迟（2-5 秒）。如果还是被限，加 `--limit N` 减少单次拉取量。

## 项目地址

仓库内位置: `20-Projects/xiaoyuzhou-skill/`
分发包: `xiaoyuzhou-skill-v0.1.0.zip`

## License

MIT
