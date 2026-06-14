---
name: ai-image
description: 通过 OpenAI 兼容的图片接口生成图片（主模型 gpt-image-2，效果/质感/广告图更强；备用 gemini-3.1-flash-image，主模型 429/5xx 时自动兜底）。触发场景：「画一张图」「生成一张图片」「生图」「做一张海报/封面/插画/配图/产品图/广告图/概念图」「text-to-image」「generate image」「draw an image」「AI绘画」「文生图」。只要用户没有明确指定其他生图模型（如 seedream、即梦、DALL·E、Midjourney），都优先用此技能。需先配置环境变量 AIPROXY_API_KEY 与 AIPROXY_ENDPOINT（本模板不含任何 key）。输出默认存到当前目录并返回绝对路径。
---

# AI 生图（gpt-image-2 + fallback）

通过一个 **OpenAI 兼容**的图片 endpoint 生成图片，封装脚本只用 Python 标准库、无三方依赖。

> **这是模板版本，不含任何密钥或私有地址。** 配置走环境变量，安全可分享。
> 用前先配置（见同目录 `config.example.sh`）：
>
> ```bash
> cp .claude/skills/ai-image/config.example.sh .claude/skills/ai-image/config.local.sh
> # 编辑 config.local.sh 填入真实 AIPROXY_API_KEY / AIPROXY_ENDPOINT
> source .claude/skills/ai-image/config.local.sh
> ```
>
> `config.local.sh` 已被 `.gitignore` 忽略，不会进 git。

## 何时使用

- 用户要画图 / 生成图片 / 海报 / 广告图 / 产品图 / 配图 / 插画 / 概念图，且未指定别的生图模型。
- 用户明确说「用 gpt-image」「用 gemini 画」时尊重其选择（`-m` 传模型名）。
- 不用于图像分析、OCR、修图等"非文本生成图片"的任务。

## 快速调用

```bash
python3 .claude/skills/ai-image/scripts/generate.py "<prompt>"
```

默认行为：
1. 用主模型（默认 `gpt-image-2`）POST 到 `AIPROXY_ENDPOINT`，`response_format=b64_json`。
2. 主模型返回 429/5xx → 自动改用 `gemini-3.1-flash-image` 重试一次。
3. `AIPROXY_ENDPOINT` 配了多个（逗号分隔）时，前一个网络错误/5xx 会降级到下一个。
4. 图写入输出目录，文件名含模型与时间戳：`gpt-image-2-YYYYMMDD-HHMMSS.jpg`。
5. 绝对路径打到 stdout；fallback/错误信息打到 stderr。

### 常用参数

| 参数 | 说明 |
|---|---|
| `-n N` | 生成几张，1-4，默认 1。除非用户明确要多张，保持 1 |
| `-m MODEL` | 模型名，默认 `gpt-image-2`。已知：`gpt-image-2`、`gemini-3.1-flash-image` |
| `-s SIZE` | 尺寸提示（服务端不严格保证），如 `1024x1024`、`1792x1024` |
| `-o DIR` | 输出目录，默认当前目录。本工作区建议存到 `assets/` |
| `--no-fallback` | 关闭兜底，主模型失败直接报错（调试用） |

### 示例

```bash
# 默认 gpt-image-2，失败自动切 fallback，存到本工作区 assets/
python3 .claude/skills/ai-image/scripts/generate.py -o assets \
  "a premium smart ring hero shot, cinematic studio lighting, dark reflective surface, ultra detailed, no text, no watermark"

# 明确用 gemini，海报尺寸
python3 .claude/skills/ai-image/scripts/generate.py -m gemini-3.1-flash-image -s 1792x1024 \
  "赛博朋克霓虹街景，电影感，超细节"
```

## 模型选择

| 场景 | 首选 |
|---|---|
| 产品/广告/海报、写实人像 | `gpt-image-2`（光影、材质、构图更精致） |
| 概念图、快速草稿 | 任一（默认 gpt-image-2 即可） |
| 用户明确要「快」或指定 gemini | `gemini-3.1-flash-image`（`-m` 显式传） |

## Prompt 套路

- **主体 + 风格 + 氛围 + 细节 + 相机/构图词**，英文更稳定，中文也可用。
- 构图词：`close-up`、`hero shot`、`wide shot`、`flat lay`、`isometric`、`35mm`。
- 负面词避免杂质：`no text, no watermark, no people, no logo`。
- 用户 prompt 太简略（如「画只猫」）可以帮他扩，但别改核心主体。

## 交付给用户

拿到路径后用 markdown 图片语法方便预览：

```markdown
![generated](/absolute/path/to/gpt-image-2-xxx.jpg)
```

发生了 fallback（stderr 有 `primary model ... failed`）就顺带告诉用户"主模型繁忙，已用 fallback 模型生成"。

## 失败处理

- 主模型 429/5xx → 自动切 fallback 模型重试，用户无感。
- 多 endpoint 时，网络错误/5xx → 切下一个 endpoint。
- 全失败 → 退出码 1，stderr 写明 `all attempts failed (tried: ...)` + 状态码 + 响应体前 500 字。
- 4xx（非 429）→ 不切换（通常是 prompt 违规/参数错），直接报错，建议改写 prompt。
- 缺 `AIPROXY_API_KEY` / `AIPROXY_ENDPOINT` → 退出码 2，提示先配置。

## 接口约定（OpenAI 兼容）

`POST {AIPROXY_ENDPOINT}`，Header `Authorization: Bearer {AIPROXY_API_KEY}`。请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `prompt` | 是 | 描述文本 |
| `model` | 否 | `gpt-image-2`（推荐）或 `gemini-3.1-flash-image` |
| `n` | 否 | 1-4，默认 1 |
| `size` | 否 | 仅提示 |
| `response_format` | 否 | `b64_json`（推荐） |

返回 `{"data": [{"b64_json": "..."}]}`，base64 解码即 JPEG。
