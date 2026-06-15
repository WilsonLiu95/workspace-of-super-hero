#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉归档客户端（仅标准库，零 pip 依赖）。

支持归档：
  - 通讯录（contacts）：遍历部门树 → 列用户 → 取用户详情，按部门分组写 markdown 名册。
  - 文档/知识库（docs，可选）：列知识库 workspaces / nodes，能导出的节点取临时下载链接并立即抓取字节。

刻意不做：
  - 历史聊天记录。钉钉不开放拉取任意 1:1 / 群历史消息的 API（平台限制），不要伪造。

两套 API 互不相同，务必分清（这是最常见的坑）：
  * 新版 host  https://api.dingtalk.com   token 走 HEADER  x-acs-dingtalk-access-token
  * 旧版 host  https://oapi.dingtalk.com  token 走 QUERY  ?access_token=...

凭证只从环境变量读：DINGTALK_APP_KEY / DINGTALK_APP_SECRET。
可被 Codex / 定时器直接复用。
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error

# 两个 API host
NEW_HOST = "https://api.dingtalk.com"      # 新版：token 放 header
OAPI_HOST = "https://oapi.dingtalk.com"    # 旧版：token 放 query

# token 缓存（含两套 token），落到 .tmp/（已 gitignore）
TOKEN_CACHE = os.path.join(".tmp", "dingtalk_token.json")
TOKEN_TTL = 7000  # 钉钉给 7200s，留 200s 余量提前续期


# --------------------------------------------------------------------------- #
# 通用 HTTP 助手（防御式：超时、容错解析、清晰报错）
# --------------------------------------------------------------------------- #
def _log(msg):
    """统一往 stderr 打日志，便于 bash 包一层时归集。"""
    print(f"[dingtalk] {msg}", file=sys.stderr)


def _http(method, url, headers=None, body=None, timeout=60, raw=False):
    """
    发一个 HTTP 请求。
    - body 为 dict 时按 JSON 编码并自动补 Content-Type。
    - raw=True 时返回原始 bytes（用于下载文档导出文件）；否则解析 JSON 返回 dict。
    解析失败/网络异常都抛 RuntimeError，带上可读信息。
    """
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        # 钉钉的错误体通常也是 JSON，尽量带出来
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {url} {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误 {url}: {e}")
    if raw:
        return payload
    text = payload.decode("utf-8", "ignore")
    try:
        return json.loads(text)
    except Exception:
        # 容错：返回个壳，调用方自行判断
        return {"_raw": text}


def _safe_get(d, *keys, default=None):
    """逐层取嵌套字典字段，任一层缺失/类型不符都返回 default，绝不抛异常。"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #
class DingTalkClient:
    def __init__(self, app_key, app_secret):
        if not app_key or not app_secret:
            raise RuntimeError("缺少 DINGTALK_APP_KEY / DINGTALK_APP_SECRET")
        self.app_key = app_key
        self.app_secret = app_secret
        self._new_token = None   # api.dingtalk.com 用
        self._oapi_token = None  # oapi.dingtalk.com 用
        self._new_expire = 0     # 各 token「取时」记下的到期戳，避免续写另一套时被误延长
        self._oapi_expire = 0
        self._load_cache()

    # ----- token 缓存 ----------------------------------------------------- #
    def _load_cache(self):
        """从 .tmp 读已缓存的两套 token；过期或缺失则置空待重取。"""
        try:
            with open(TOKEN_CACHE, "r", encoding="utf-8") as f:
                c = json.load(f)
        except Exception:
            return
        now = time.time()
        # 用 app_key 隔离，避免换 app 后误用旧 token
        if c.get("app_key") != self.app_key:
            return
        if c.get("new_expire", 0) > now:
            self._new_token = c.get("new_token")
            self._new_expire = c.get("new_expire", 0)
        if c.get("oapi_expire", 0) > now:
            self._oapi_token = c.get("oapi_token")
            self._oapi_expire = c.get("oapi_expire", 0)

    def _save_cache(self):
        """把当前两套 token 落盘（含到期时间戳）。"""
        os.makedirs(os.path.dirname(TOKEN_CACHE), exist_ok=True)
        now = time.time()
        # 读旧的，仅更新已持有的 token 的到期时间
        prev = {}
        try:
            with open(TOKEN_CACHE, "r", encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}
        data = {
            "app_key": self.app_key,
            "new_token": self._new_token,
            "oapi_token": self._oapi_token,
            # 写各 token「取时」记录的真实到期，绝不在续写另一套 token 时顺手延长它
            "new_expire": self._new_expire or prev.get("new_expire", 0),
            "oapi_expire": self._oapi_expire or prev.get("oapi_expire", 0),
        }
        try:
            with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            _log(f"WARN 写 token 缓存失败（忽略）：{e}")

    # ----- 取 token（两套，分别处理） ----------------------------------- #
    def new_token(self):
        """
        新版 token：POST https://api.dingtalk.com/v1.0/oauth2/accessToken
        body {"appKey":..., "appSecret":...} → {"accessToken":..., "expireIn":7200}
        """
        if self._new_token:
            return self._new_token
        url = f"{NEW_HOST}/v1.0/oauth2/accessToken"
        resp = _http("POST", url, body={"appKey": self.app_key, "appSecret": self.app_secret})
        tok = resp.get("accessToken")
        if not tok:
            raise RuntimeError(f"取新版 accessToken 失败：{resp}")
        self._new_token = tok
        self._new_expire = time.time() + TOKEN_TTL
        self._save_cache()
        return tok

    def oapi_token(self):
        """
        旧版 token：GET https://oapi.dingtalk.com/gettoken?appkey=..&appsecret=..
        → {"access_token":..., "errcode":0}
        """
        if self._oapi_token:
            return self._oapi_token
        q = urllib.parse.urlencode({"appkey": self.app_key, "appsecret": self.app_secret})
        url = f"{OAPI_HOST}/gettoken?{q}"
        resp = _http("GET", url)
        if resp.get("errcode", 0) != 0:
            raise RuntimeError(f"取旧版 access_token 失败：errcode={resp.get('errcode')} {resp.get('errmsg')}")
        tok = resp.get("access_token")
        if not tok:
            raise RuntimeError(f"取旧版 access_token 失败：{resp}")
        self._oapi_token = tok
        self._oapi_expire = time.time() + TOKEN_TTL
        self._save_cache()
        return tok

    # ----- 两套 host 的调用封装 ----------------------------------------- #
    def _oapi(self, path, body):
        """
        旧版 oapi/topapi 调用：token 作为 query param，POST JSON body。
        errcode != 0 一律抛错（带 errmsg），由调用方决定是否吞掉（如权限缺失）。
        """
        url = f"{OAPI_HOST}{path}?access_token={urllib.parse.quote(self.oapi_token())}"
        resp = _http("POST", url, body=body)
        if isinstance(resp, dict) and resp.get("errcode", 0) != 0:
            raise RuntimeError(
                f"oapi {path} 失败：errcode={resp.get('errcode')} errmsg={resp.get('errmsg')}"
            )
        return resp

    def _new_get(self, path, params=None, raw=False):
        """新版 api.dingtalk.com GET：token 放 header x-acs-dingtalk-access-token。"""
        url = f"{NEW_HOST}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {"x-acs-dingtalk-access-token": self.new_token()}
        return _http("GET", url, headers=headers, raw=raw)

    # ----- 通讯录：遍历部门树 ------------------------------------------- #
    def list_sub_departments(self, dept_id):
        """
        列某部门的直接子部门。
        POST topapi/v2/department/listsub  body {"dept_id":D} → {"result":[{dept_id,name,...}]}
        """
        resp = self._oapi("/topapi/v2/department/listsub", {"dept_id": dept_id})
        return resp.get("result") or []

    def walk_departments(self, root=1):
        """
        从 root（1=根）BFS 遍历整棵部门树，返回 [(dept_id, name, parent_name), ...]。
        根部门本身（id=1）也纳入，名字标为「根部门」。
        """
        out = [(root, "根部门", "")]
        # 队列里存 (dept_id, name)
        queue = [(root, "根部门")]
        seen = {root}
        while queue:
            did, dname = queue.pop(0)
            try:
                subs = self.list_sub_departments(did)
            except RuntimeError as e:
                _log(f"WARN 列子部门失败 dept={did}：{e}")
                continue
            for s in subs:
                sid = s.get("dept_id")
                sname = s.get("name") or f"dept_{sid}"
                if sid is None or sid in seen:
                    continue
                seen.add(sid)
                out.append((sid, sname, dname))
                queue.append((sid, sname))
        return out

    def list_user_ids(self, dept_id):
        """
        列某部门下的 userid 列表。
        POST topapi/user/listid  body {"dept_id":D} → {"result":{"userid_list":[...]}}
        """
        resp = self._oapi("/topapi/user/listid", {"dept_id": dept_id})
        return _safe_get(resp, "result", "userid_list", default=[]) or []

    def get_user(self, userid):
        """
        取用户详情。
        POST topapi/v2/user/get  body {"userid":U,"language":"zh_CN"} → {"result":{...}}
        """
        resp = self._oapi("/topapi/v2/user/get", {"userid": userid, "language": "zh_CN"})
        return resp.get("result") or {}

    def collect_contacts(self):
        """
        汇总整张通讯录：返回 (departments, users_by_dept)
          departments    = [(dept_id, name, parent_name), ...]（遍历顺序）
          users_by_dept  = {dept_id: [user_detail, ...]}
        同一用户可能挂在多个部门，去重交给写出层（按 userid 全局去重展示一次）。
        """
        departments = self.walk_departments(root=1)
        users_by_dept = {}
        seen_uid = set()
        total = 0
        for did, dname, _ in departments:
            try:
                uids = self.list_user_ids(did)
            except RuntimeError as e:
                _log(f"WARN 列部门用户失败 dept={did}({dname})：{e}")
                continue
            bucket = []
            for uid in uids:
                # 同一 uid 只取一次详情，归到第一个遇到的部门
                if uid in seen_uid:
                    continue
                seen_uid.add(uid)
                try:
                    detail = self.get_user(uid)
                except RuntimeError as e:
                    _log(f"WARN 取用户详情失败 uid={uid}：{e}")
                    detail = {"userid": uid, "name": uid}
                bucket.append(detail)
                total += 1
            if bucket:
                users_by_dept[did] = bucket
        _log(f"通讯录采集完成：{len(departments)} 个部门，{total} 名成员（去重后）")
        return departments, users_by_dept

    # ----- 文档/知识库（可选） ------------------------------------------ #
    def list_wiki_workspaces(self):
        """
        列知识库 workspaces（新版 host，header token）。
        GET /v2.0/wiki/workspaces → 容错取 workspaces 列表，每个含 spaceUuid/name。
        若未授权知识库 scope，会抛权限错误，由调用方 catch 后告警。
        """
        resp = self._new_get("/v2.0/wiki/workspaces")
        return resp.get("workspaces") or resp.get("result") or []

    def list_wiki_nodes(self, space_uuid):
        """
        列某知识库空间下的节点。
        GET /v2.0/wiki/nodes?spaceUuid=... → nodes 列表，每个含 nodeId/name/url 等。
        """
        resp = self._new_get("/v2.0/wiki/nodes", params={"spaceUuid": space_uuid})
        return resp.get("nodes") or resp.get("result") or []


# --------------------------------------------------------------------------- #
# 写出层：markdown 名册 / 文档清单
# --------------------------------------------------------------------------- #
def _frontmatter(d):
    """把 dict 拼成 YAML frontmatter 文本（值简单字符串，够用）。"""
    lines = ["---"]
    for k, v in d.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def write_contacts_markdown(tenant, departments, users_by_dept, dest_dir, today):
    """
    写通讯录名册到 sources/dingtalk/<tenant>/contacts/<DATE>_contacts.md
    APPEND-ONLY：文件已存在则跳过（不覆盖）。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, f"{today}_contacts.md")
    if os.path.exists(path):
        _log(f"已存在，跳过（仅追加约定）：{path}")
        return path

    fm = _frontmatter({
        "source": "dingtalk",
        "tenant": tenant,
        "channel": "通讯录",
        "type": "contacts",
        "captured": today,
    })

    body = ["# 钉钉通讯录", "", f"采集日期：{today} ｜ 租户：{tenant}", ""]
    # 部门名映射，便于显示层级
    dept_name = {did: name for did, name, _ in departments}
    for did, dname, parent in departments:
        users = users_by_dept.get(did)
        if not users:
            continue
        title = dname if not parent else f"{parent} / {dname}"
        body.append(f"## {title}")
        body.append("")
        body.append("| 姓名 | 职位 | 手机 | 邮箱 | userid |")
        body.append("| --- | --- | --- | --- | --- |")
        for u in users:
            name = u.get("name") or u.get("userid") or ""
            title_ = u.get("title") or ""
            mobile = u.get("mobile") or ""
            email = u.get("email") or u.get("org_email") or ""
            uid = u.get("userid") or ""
            # 转义竖线，防止破坏表格
            cells = [str(c).replace("|", "\\|") for c in (name, title_, mobile, email, uid)]
            body.append("| " + " | ".join(cells) + " |")
        body.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + "\n\n" + "\n".join(body) + "\n")
    _log(f"写入 {path}")
    return path


def write_docs_index(tenant, items, dest_dir, today):
    """
    写知识库/文档清单到 sources/dingtalk/<tenant>/docs/<DATE>_wiki_index.md
    items = [(space_name, space_uuid, [node_dict,...]), ...]
    APPEND-ONLY：已存在则跳过。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, f"{today}_wiki_index.md")
    if os.path.exists(path):
        _log(f"已存在，跳过（仅追加约定）：{path}")
        return path

    fm = _frontmatter({
        "source": "dingtalk",
        "tenant": tenant,
        "channel": "知识库",
        "type": "doc",
        "captured": today,
    })
    body = ["# 钉钉知识库 / 文档清单", "", f"采集日期：{today} ｜ 租户：{tenant}", ""]
    for sname, suuid, nodes in items:
        body.append(f"## {sname}")
        body.append("")
        body.append(f"spaceUuid: `{suuid}`")
        body.append("")
        if not nodes:
            body.append("（无节点或未列出）")
            body.append("")
            continue
        body.append("| 节点 | nodeId | 链接 |")
        body.append("| --- | --- | --- |")
        for n in nodes:
            nname = n.get("name") or n.get("title") or ""
            nid = n.get("nodeId") or n.get("id") or ""
            nurl = n.get("url") or ""
            cells = [str(c).replace("|", "\\|") for c in (nname, nid, nurl)]
            body.append("| " + " | ".join(cells) + " |")
        body.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + "\n\n" + "\n".join(body) + "\n")
    _log(f"写入 {path}")
    return path


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    app_key = os.environ.get("DINGTALK_APP_KEY", "").strip()
    app_secret = os.environ.get("DINGTALK_APP_SECRET", "").strip()
    tenant = os.environ.get("DINGTALK_TENANT", "default").strip() or "default"
    archive = os.environ.get("DINGTALK_ARCHIVE", "contacts").strip() or "contacts"
    archive_set = {x.strip().lower() for x in archive.split(",") if x.strip()}

    # 落盘根：相对当前工作目录（包一层的 bash 会先 cd 到仓库根）
    base = os.path.join("sources", "dingtalk", tenant)
    today = datetime.date.today().strftime("%Y-%m-%d")

    client = DingTalkClient(app_key, app_secret)

    did_any = False

    # --- 通讯录（默认） --- #
    if "contacts" in archive_set:
        _log("开始归档通讯录 …")
        try:
            departments, users_by_dept = client.collect_contacts()
            write_contacts_markdown(
                tenant, departments, users_by_dept,
                os.path.join(base, "contacts"), today,
            )
            did_any = True
        except RuntimeError as e:
            # 通讯录是核心能力；权限缺失要明确提示但不一定 crash 全流程
            _log(f"ERROR 通讯录归档失败：{e}")
            _log("提示：需管理员在钉钉后台为本应用授予『通讯录读权限』（部门/成员读）。")

    # --- 文档/知识库（可选） --- #
    if "docs" in archive_set:
        _log("开始归档知识库/文档 …")
        try:
            workspaces = client.list_wiki_workspaces()
            items = []
            for ws in workspaces:
                suuid = ws.get("spaceUuid") or ws.get("spaceId") or ws.get("uuid")
                sname = ws.get("name") or ws.get("title") or (suuid or "未命名")
                if not suuid:
                    items.append((sname, "", []))
                    continue
                try:
                    nodes = client.list_wiki_nodes(suuid)
                except RuntimeError as e:
                    _log(f"WARN 列节点失败 space={sname}：{e}")
                    nodes = []
                items.append((sname, suuid, nodes))
            write_docs_index(tenant, items, os.path.join(base, "docs"), today)
            did_any = True
        except RuntimeError as e:
            # 知识库 scope 未授权时只告警，不影响通讯录结果
            _log(f"WARN 知识库/文档归档失败（可能未授予知识库读权限，已跳过）：{e}")

    if not did_any:
        _log("没有产出任何归档。检查 DINGTALK_ARCHIVE 与应用权限。")
        sys.exit(1)
    _log(f"完成。产物在 {base}/")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        _log(f"ERROR {e}")
        sys.exit(1)
