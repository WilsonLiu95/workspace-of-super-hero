---
name: cloud-computer
description: 通过 SSH 登录云电脑并执行运维操作、启动托管服务、把本地静态网页一键部署到云电脑并用用户自有域名访问。触发场景：「云电脑」「SSH 到服务器」「远程执行命令」「部署网页」「托管静态站点」「绑定域名」「Caddy/Nginx 反代」「把 dist 上传服务器」「cloud computer」「VPS」「SSH deploy」。适用于用户已拥有主机和 SSH 凭证；DNS 记录需用户自行在域名服务商配置。
version: 0.1.0
updated: "2026-06-15"
---

# cloud-computer — SSH 云电脑操作与网页托管

通过 SSH 操作一台用户自有云电脑：登录、远端执行命令、部署静态网页、配置 Caddy 作为托管/反代入口。实现是本技能自带脚本 `scripts/cloud-computer.sh`，凭证只从 gitignore 的本地 env 读取。

## 前置

在仓库根 `.env.local` 配置：

```bash
CLOUD_COMPUTER_HOST=1.2.3.4
CLOUD_COMPUTER_USER=root
CLOUD_COMPUTER_PORT=22
CLOUD_COMPUTER_SSH_KEY=~/.ssh/id_ed25519
# 或：CLOUD_COMPUTER_PASSWORD=<密码>   # 仅放 .env.local；非交互命令需要本机安装 sshpass
CLOUD_COMPUTER_REMOTE_ROOT=/srv/cloud-computer
CLOUD_COMPUTER_DOMAIN=example.com
```

云电脑上建议已有 Docker + Docker Compose；静态托管和反代默认用 `caddy:2-alpine` 容器监听 80/443。域名解析不由本技能代配，需用户自己在 DNS 服务商添加 `A/AAAA` 记录指向云电脑公网 IP。

多租户/多主机：把另一台云电脑配置写到 `.env.<租户>.local`，运行时加 `TENANT=<租户>`。

## 快速体检

```bash
skills/cloud-computer/scripts/cloud-computer.sh doctor
skills/cloud-computer/scripts/cloud-computer.sh --dry-run deploy-static ./dist example.com
```

`doctor` 检查本地 SSH 工具、环境变量、远端 Docker/Compose 状态。任何会改远端文件或启动服务的操作，先跑 `--dry-run` 给用户确认。

## 常用操作

### 登录或执行命令

```bash
skills/cloud-computer/scripts/cloud-computer.sh ssh
skills/cloud-computer/scripts/cloud-computer.sh run 'uptime && df -h'
```

### 一键托管静态网页

```bash
skills/cloud-computer/scripts/cloud-computer.sh --dry-run deploy-static ./dist example.com
skills/cloud-computer/scripts/cloud-computer.sh deploy-static ./dist example.com
```

流程：
1. 确认 `./dist` 存在，最好包含 `index.html`。
2. 用 `tar | ssh` 上传到 `${CLOUD_COMPUTER_REMOTE_ROOT}/sites/<domain>/public/`。
3. 生成/更新远端 `compose.yml` 与 `Caddyfile`。
4. 启动或刷新 Caddy 容器。
5. 提醒用户配置 DNS：`example.com A -> 云电脑公网 IP`；DNS 生效后 Caddy 自动申请 HTTPS。

未传域名时会使用 `.env.local` 的 `CLOUD_COMPUTER_DOMAIN`；仍未配置则默认发布到云电脑 80 端口的默认站点。

### 暴露已有本地服务

如果应用已在云电脑上监听 `127.0.0.1:3000`：

```bash
skills/cloud-computer/scripts/cloud-computer.sh --dry-run expose-service app example.com 3000
skills/cloud-computer/scripts/cloud-computer.sh expose-service app example.com 3000
```

第三个参数可写端口号、`127.0.0.1:3000` 或完整 upstream URL。该命令只配置 Caddy 反代，不负责启动应用进程；启动应用可用 `run` 执行用户指定的 Docker/systemd/pm2 命令。

### 查看托管服务

```bash
skills/cloud-computer/scripts/cloud-computer.sh status
skills/cloud-computer/scripts/cloud-computer.sh logs
```

## 操作红线

- 不把 SSH 私钥、SSH 密码、云厂商 key、DNS API token 写进仓库；只引用本机路径或 gitignore 的本地环境变量。
- DNS 必须由用户自己配置；不要假装已经替用户改了 DNS。
- 远端写操作、容器启动、反代变更前先 `--dry-run`，尤其是用户没有明确授权时。
- 不删除 `CLOUD_COMPUTER_REMOTE_ROOT` 之外的远端文件；部署静态站点只替换对应站点的 `public/` 内容。
- 生产站点迁移、已有 Nginx/Apache/Caddy 占用 80/443、或服务器上已有重要服务时，先用 `status`/`run` 查清现状，再给出风险说明。
