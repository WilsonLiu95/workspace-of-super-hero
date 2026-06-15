# 小宇宙 API 反向工程笔记

> 小宇宙没有公开 API。这里记录通过反向工程其客户端（移动 App + Web Studio + 消费者 Web）发现的端点。
> **仅供学习研究**，请勿用于商业用途或大规模爬取。

## 三个独立认证 Realm

小宇宙后端共享 Jike (即刻) 的 token 体系（同公司，都用 `x-jike-*` header），但有 **3 个互不通用的认证域**：

| Realm | 用途 | 客户端 ID | 认证端点 host | 数据 API host |
|---|---|---|---|---|
| **mobile** | 小宇宙 App (consumer) | N/A (设备绑定) | `api.xiaoyuzhoufm.com` | `api.xiaoyuzhoufm.com` |
| **xyz-web** | 消费者 web (账号系统) | `xyz-web` | `web-api.xiaoyuzhoufm.com` | `api.xiaoyuzhoufm.com` ✅ |
| **podcaster-platform** | 创作者后台 Studio | `podcaster-platform` | `podcaster.xiaoyuzhoufm.com` | `podcaster.xiaoyuzhoufm.com` |

**关键发现**：xyz-web 拿到的 token 可以直接用于 `api.xiaoyuzhoufm.com` 的消费者数据接口（search, episode, transcript）。这是本 skill 选择 xyz-web 流程的原因。

## 认证流程 1: QR 扫码（xyz-web，本 skill 默认）

### Step 1: 创建会话

```http
POST https://web-api.xiaoyuzhoufm.com/v1/auth/qrcode/create
Content-Type: application/json
x-midway-app-id: v6worU4NnWyL
Origin: https://accounts.xiaoyuzhoufm.com

{"clientId": "xyz-web"}
```

返回：
```json
{
  "id": "69d9a799e2c8be3155e7ad84",
  "url": "https://h5.xiaoyuzhoufm.com/oauth?qrcode_id=69d9a799e2c8be3155e7ad84"
}
```

`url` 字段就是 QR 码内容，**普通 https URL**，小宇宙 App 原生支持扫码识别（不需要 `cosmos://` 或 `jike://` 协议）。

### Step 2: 轮询确认

```http
POST https://web-api.xiaoyuzhoufm.com/v1/auth/qrcode/login
Content-Type: application/json
x-midway-app-id: v6worU4NnWyL

{"id": "69d9a799e2c8be3155e7ad84"}
```

状态机：

| Status | 含义 | 下一步 |
|---|---|---|
| `WAITTING` | 还没扫码（注意：原始拼写就是 WAITTING） | 1 秒后再轮询 |
| `SCANNED` | App 已扫码，等待用户在 App 内点"确认登录" | 继续轮询 |
| `CONFIRMED` / 含 token | 用户已确认 | 从响应**头部**取 token |
| `USED` | 一次性流程已消费完成 | token 已经在某次响应里，停止轮询 |

### Step 3: 提取 Token

确认后，**响应头部**包含：
- `x-jike-access-token: <JWT>`
- `x-jike-refresh-token: <JWT>`

CORS 配置允许这两个 header 被跨域读取。

## 认证流程 2: SMS 短信验证码（备用）

### Step 1: 发送验证码

```http
POST https://api.xiaoyuzhoufm.com/v1/auth/sendCode
Content-Type: application/json;charset=utf-8
x-jike-device-id: <随机 UUID>
applicationid: app.podcast.cosmos
app-version: 2.99.1
User-Agent: okhttp/4.12.0

{"areaCode": "+86", "mobilePhoneNumber": "13800138000"}
```

### Step 2: 验证登录

```http
POST https://api.xiaoyuzhoufm.com/v1/auth/loginOrSignUpWithSMS
Content-Type: application/json;charset=utf-8
x-jike-device-id: <同上>
applicationid: app.podcast.cosmos
app-version: 2.99.1

{
  "areaCode": "+86",
  "mobilePhoneNumber": "13800138000",
  "verifyCode": "1234"
}
```

token 在响应头部：`x-jike-access-token`, `x-jike-refresh-token`

## Token 刷新

```http
POST https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh
x-jike-refresh-token: <current refresh>
applicationid: app.podcast.cosmos
app-version: 2.99.1

{}
```

新 token 在响应头部。

xyz-web realm 的 token 在 `https://web-api.xiaoyuzhoufm.com/app_auth_tokens.refresh` 也能刷新（路径前没有 /v1）。

## 数据 API 端点

所有认证后请求需要带：
```
x-jike-access-token: <token>
applicationid: app.podcast.cosmos
app-version: 2.99.1
User-Agent: okhttp/4.12.0
Content-Type: application/json
```

### 搜索

```http
POST https://api.xiaoyuzhoufm.com/v1/search/create
{
  "keyword": "AI",
  "type": "PODCAST",   // ALL | PODCAST | EPISODE | USER
  "limit": 20,
  "loadMoreKey": null  // 翻页用，从上次返回里取
}
```

返回的 `data` 是异构数组，每个元素有 `type` 字段（HEADER/PODCAST/EPISODE/SEARCHED_USERS/FOOTER）。`loadMoreKey` 是下一页 cursor。

### 拉取单个播客的所有单集

```http
POST https://api.xiaoyuzhoufm.com/v1/episode/list
{
  "pid": "63e9ef4de99bdef7d39944c8",
  "order": "desc",
  "limit": 20,
  "loadMoreKey": null
}
```

分页同 search。

### 单集详情

```http
GET https://api.xiaoyuzhoufm.com/v1/episode/get?eid=<episode_id>
```

返回里的 `media.id` 字段是 `mediaId`，下面拉逐字稿用。

### 逐字稿

```http
POST https://api.xiaoyuzhoufm.com/v1/episode-transcript/get
{
  "eid": "<episode_id>",
  "mediaId": "<media id from episode detail>"
}
```

⚠️ **不是所有节目都有逐字稿**，由主理人在 App 后台开启。没开的会返回错误或空数据。

### 评论（未在本 skill 实现）

```http
POST https://api.xiaoyuzhoufm.com/v1/comment/list-primary
{"owner": "<eid>", "order": "HOT|TIME|TIMESTAMP", "loadMoreKey": null}
```

## 必需 Header 总结

任何 `/v1/auth/*` 端点都需要 `x-midway-app-id: v6worU4NnWyL`，否则返回 `{"success":false,"code":1,"toast":"midway app id为空"}`。

数据 API 端点需要 `applicationid: app.podcast.cosmos` 和 `app-version`，否则可能返回 401。

## 速率限制

逐字稿端点比较敏感，建议每次请求之间随机延迟 2-5 秒。本 skill 默认就是这样做的。

## 致谢

- xyz-web realm 的发现：反向工程 `accounts.xiaoyuzhoufm.com` 的 Vite bundle
- podcaster-platform 流程：反向工程 `studio.xiaoyuzhoufm.com` 的 Next.js bundle
- SMS 流程参考：[shiquda/xyz-dl](https://github.com/shiquda/xyz-dl) 和 [AbCooly/podcastAnalyse](https://github.com/AbCooly/podcastAnalyse)
- QR 流程架构参考：[imHw/jike-skill](https://github.com/imHw/jike-skill)
