"""
微信公众号平台 QR 码扫码登录（带 Session 持久化和自动刷新）

核心改进：
- 登录后自动将完整 session（token + 所有 cookies）持久化到 JSON 文件
- 后续操作自动加载已保存的 session，无需重新扫码
- 内置 session 有效性检查和自动刷新机制
- session 有效期约 4 小时，刷新可延长

典型使用方式：
    manager = SessionManager()
    client = manager.get_client()  # 自动处理登录/恢复/刷新
    # 直接使用 client 调 API...
"""

import json
import os
import random
import re
import time
from datetime import datetime
from typing import Optional, Tuple

import requests


# ============================================================
# 默认路径
# ============================================================

DEFAULT_SESSION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".wechat_session.json"
)
DEFAULT_QR_PATH = "wechat_qrcode.png"
DEFAULT_QR_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".wechat_qr_state.json"
)


# ============================================================
# 异常类
# ============================================================

class QRLoginError(Exception):
    """QR 登录错误"""
    pass


# ============================================================
# QR 登录
# ============================================================

class QRLogin:
    """微信公众号平台 QR 码登录"""

    BASE_URL = "https://mp.weixin.qq.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Origin": "https://mp.weixin.qq.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.token = None

    def start_login(self) -> bool:
        """第 1 步：发起登录会话"""
        print("正在初始化登录会话...")
        try:
            self.session.get(f"{self.BASE_URL}/", timeout=15, allow_redirects=True)
        except requests.exceptions.RequestException as e:
            raise QRLoginError(f"无法连接到 mp.weixin.qq.com: {e}")

        try:
            resp = self.session.post(
                f"{self.BASE_URL}/cgi-bin/bizlogin",
                params={"action": "startlogin"},
                data={
                    "userlang": "zh_CN", "redirect_url": "",
                    "login_type": "3",
                    "sessionid": str(random.randint(100000000, 999999999)),
                    "token": "", "lang": "zh_CN", "f": "json", "ajax": "1",
                },
                timeout=15,
            )
            print("  ✓ 登录会话已建立")
            return True
        except requests.exceptions.RequestException as e:
            raise QRLoginError(f"发起登录失败: {e}")

    def get_qrcode(self, save_path: str = DEFAULT_QR_PATH) -> str:
        """第 2 步：获取登录二维码"""
        print("正在获取登录二维码...")
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/cgi-bin/scanloginqrcode",
                params={"action": "getqrcode", "random": str(random.random())},
                timeout=15,
            )
            if resp.status_code != 200 or len(resp.content) < 100:
                raise QRLoginError(f"获取二维码失败: HTTP {resp.status_code}")

            with open(save_path, "wb") as f:
                f.write(resp.content)
            print(f"  ✓ 二维码已保存到: {save_path}")
            return save_path
        except requests.exceptions.RequestException as e:
            raise QRLoginError(f"获取二维码失败: {e}")

    def poll_scan_status(self, timeout: int = 180, interval: float = 2.0) -> int:
        """第 3 步：轮询扫码状态"""
        print("等待扫码...")
        print("  请用微信扫描二维码，然后在手机上确认登录")

        start_time = time.time()
        last_status = -1

        while time.time() - start_time < timeout:
            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/cgi-bin/scanloginqrcode",
                    params={"action": "ask", "token": "", "lang": "zh_CN",
                            "f": "json", "ajax": "1"},
                    timeout=10,
                )
                status = resp.json().get("status", 0)

                if status != last_status:
                    if status == 4:
                        print("  ✓ 已扫码，请在手机上确认登录...")
                    elif status == 1:
                        print("  ✓ 登录已确认！")
                        return status
                    elif status == 2:
                        raise QRLoginError("二维码已过期，请重新获取")
                    last_status = status

                if status == 1:
                    return status
            except (requests.exceptions.Timeout, json.JSONDecodeError):
                pass

            time.sleep(interval)

        raise QRLoginError(f"扫码超时（{timeout}秒），请重试")

    def complete_login(self) -> str:
        """第 4 步：完成登录，获取 token"""
        print("正在完成登录...")
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/cgi-bin/bizlogin",
                params={"action": "login"},
                data={
                    "userlang": "zh_CN", "redirect_url": "",
                    "cookie_forbidden": "0", "cookie_cleaned": "0",
                    "plugin_used": "0", "login_type": "3",
                    "token": "", "lang": "zh_CN", "f": "json", "ajax": "1",
                },
                timeout=15,
                allow_redirects=False,
            )
            data = resp.json()
            ret = data.get("base_resp", {}).get("ret", -1)

            if ret == 0:
                redirect_url = data.get("redirect_url", "")
                token_match = re.search(r"token=(\d+)", redirect_url)
                if token_match:
                    self.token = token_match.group(1)
                    print(f"  ✓ 登录成功！")
                    return self.token
                raise QRLoginError(f"未找到 token: {redirect_url}")
            else:
                err_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
                raise QRLoginError(f"登录失败 (ret={ret}): {err_msg}")
        except requests.exceptions.RequestException as e:
            raise QRLoginError(f"完成登录请求失败: {e}")

    def save_qr_state(self, state_file: str = DEFAULT_QR_STATE_FILE):
        """保存 QR 会话 cookies 到文件，供跨进程 poll 恢复使用"""
        state = {
            "cookies": {c.name: c.value for c in self.session.cookies},
            "saved_at": datetime.now().isoformat(),
        }
        os.makedirs(os.path.dirname(os.path.abspath(state_file)), exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(state, f)

    def load_qr_state(self, state_file: str = DEFAULT_QR_STATE_FILE) -> bool:
        """从文件恢复 QR 会话 cookies，使跨进程 poll 成为可能"""
        if not os.path.exists(state_file):
            return False
        try:
            with open(state_file) as f:
                state = json.load(f)
            for name, value in state.get("cookies", {}).items():
                self.session.cookies.set(name, value)
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def get_cookie_string(self) -> str:
        """获取完整 Cookie 字符串"""
        return "; ".join(f"{c.name}={c.value}" for c in self.session.cookies)

    def get_cookies_dict(self) -> dict:
        """获取 Cookie 字典（用于持久化）"""
        return {c.name: c.value for c in self.session.cookies}

    def login(self, qrcode_path: str = DEFAULT_QR_PATH, timeout: int = 180) -> Tuple[str, str]:
        """一键登录：完整流程"""
        self.start_login()
        self.get_qrcode(qrcode_path)
        print(f"\n{'='*50}")
        print(f"请用微信扫描二维码: {os.path.abspath(qrcode_path)}")
        print(f"{'='*50}\n")
        self.poll_scan_status(timeout=timeout)
        token = self.complete_login()
        cookie = self.get_cookie_string()
        return token, cookie


# ============================================================
# Session 持久化管理器
# ============================================================

class SessionManager:
    """
    Session 管理器：自动处理登录、持久化、恢复和刷新

    核心功能：
    1. 首次使用：QR 扫码登录，保存 session 到文件
    2. 后续使用：自动加载已保存的 session
    3. 过期检测：自动检测 session 是否有效
    4. 自动刷新：在过期前自动刷新 session
    """

    def __init__(self, session_file: str = DEFAULT_SESSION_FILE):
        self.session_file = session_file
        self.token = None
        self.cookie_string = None
        self.cookies_dict = {}
        self.login_time = None
        self.last_refresh_time = None

    def save_session(self, token: str, cookies_dict: dict, cookie_string: str):
        """保存 session 到 JSON 文件"""
        now = datetime.now().isoformat()
        data = {
            "token": token,
            "cookies": cookies_dict,
            "cookie_string": cookie_string,
            "login_time": now,
            "last_refresh_time": now,
            "version": 1,
        }
        with open(self.session_file, "w") as f:
            json.dump(data, f, indent=2)
        self.token = token
        self.cookies_dict = cookies_dict
        self.cookie_string = cookie_string
        self.login_time = now
        self.last_refresh_time = now
        print(f"  ✓ Session 已保存到: {self.session_file}")

    def load_session(self) -> bool:
        """从文件加载 session，成功返回 True"""
        if not os.path.exists(self.session_file):
            return False

        try:
            with open(self.session_file) as f:
                data = json.load(f)
            self.token = data["token"]
            self.cookies_dict = data["cookies"]
            self.cookie_string = data["cookie_string"]
            self.login_time = data.get("login_time")
            self.last_refresh_time = data.get("last_refresh_time")
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def check_session_valid(self) -> bool:
        """
        检测当前 session 是否仍然有效

        通过调用一个轻量级 API 来验证。
        """
        if not self.token or not self.cookie_string:
            return False

        try:
            from wechat_api import WeChatMPClient
            client = WeChatMPClient(
                token=self.token,
                cookie=self.cookie_string,
                request_interval=0,  # 检测时不需要限速
            )
            # 用搜索接口做轻量级验证
            client._request("searchbiz", {
                "action": "search_biz",
                "begin": 0, "count": 1,
                "query": "test",
            })
            return True
        except Exception:
            return False

    def refresh_session(self) -> bool:
        """
        刷新 session：通过访问后台页面让服务端续期 cookies

        微信 MP session 约 4 小时有效。每次成功调 API 实际上已经在
        隐式刷新了，但这个方法可以显式刷新。
        """
        if not self.token or not self.cookies_dict:
            return False

        try:
            session = requests.Session()
            for name, value in self.cookies_dict.items():
                session.cookies.set(name, value)
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            })

            # 访问后台首页来刷新 session
            resp = session.get(
                f"https://mp.weixin.qq.com/cgi-bin/home"
                f"?t=home/index&token={self.token}&lang=zh_CN",
                timeout=15,
                allow_redirects=False,
            )

            # 如果被重定向到登录页，说明 session 已彻底过期
            if resp.status_code in (301, 302) and "login" in resp.headers.get("Location", ""):
                return False

            # 更新 cookies（服务端可能返回新的 cookie 值）
            new_cookies = {c.name: c.value for c in session.cookies}
            if new_cookies:
                self.cookies_dict.update(new_cookies)
                self.cookie_string = "; ".join(
                    f"{k}={v}" for k, v in self.cookies_dict.items()
                )
                self.last_refresh_time = datetime.now().isoformat()
                # 更新保存的文件
                self.save_session(self.token, self.cookies_dict, self.cookie_string)

            return True
        except Exception:
            return False

    def login_with_qr(self, qrcode_path: str = DEFAULT_QR_PATH, timeout: int = 180):
        """执行 QR 扫码登录并保存 session"""
        qr = QRLogin()
        token, cookie = qr.login(qrcode_path=qrcode_path, timeout=timeout)

        # 关键：登录后保存完整的 cookies
        self.save_session(
            token=token,
            cookies_dict=qr.get_cookies_dict(),
            cookie_string=cookie,
        )
        return token, cookie

    def get_client(self, qrcode_path: str = DEFAULT_QR_PATH):
        """
        获取一个可用的 WeChatMPClient

        自动处理：
        1. 尝试加载已保存的 session
        2. 检查有效性，无效则尝试刷新
        3. 刷新失败则重新扫码登录
        4. 返回可用的 client

        Returns:
            WeChatMPClient 实例
        """
        from wechat_api import WeChatMPClient

        # 第 1 步：尝试加载已保存的 session
        if self.load_session():
            print(f"找到已保存的 session（登录于 {self.login_time}）")

            # 第 2 步：检查是否有效
            print("  检查 session 有效性...")
            if self.check_session_valid():
                print("  ✓ Session 有效，无需重新登录")
                return WeChatMPClient(
                    token=self.token,
                    cookie=self.cookie_string,
                )

            # 第 3 步：尝试刷新
            print("  Session 已过期，尝试刷新...")
            if self.refresh_session() and self.check_session_valid():
                print("  ✓ Session 刷新成功")
                return WeChatMPClient(
                    token=self.token,
                    cookie=self.cookie_string,
                )

            print("  ✗ Session 无法恢复，需要重新扫码登录")

        # 第 4 步：重新扫码登录
        print("\n需要扫码登录...")
        self.login_with_qr(qrcode_path=qrcode_path)

        return WeChatMPClient(
            token=self.token,
            cookie=self.cookie_string,
        )


# ============================================================
# 便捷入口函数
# ============================================================

def qr_login_and_fetch(
    account_keyword: str,
    output_dir: str,
    qrcode_path: str = DEFAULT_QR_PATH,
    session_file: str = DEFAULT_SESSION_FILE,
    export_formats: list = None,
    max_articles: int = None,
):
    """
    一站式：自动登录 + 搜索公众号 + 拉取文章 + 导出

    自动管理 session：首次扫码，后续自动复用。

    Args:
        account_keyword: 公众号名称
        output_dir: 导出目录
        qrcode_path: 二维码保存路径
        session_file: session 保存路径
        export_formats: 导出格式 ["json", "excel", "markdown", "txt"]
        max_articles: 最大文章数，None=全部
    """
    from exporter import ArticleExporter

    if export_formats is None:
        export_formats = ["json", "excel"]

    print("=" * 60)
    print(f"微信公众号文章导出 - {account_keyword}")
    print("=" * 60)

    # 自动获取 client（优先复用已有 session）
    manager = SessionManager(session_file=session_file)
    client = manager.get_client(qrcode_path=qrcode_path)

    # 搜索公众号
    print(f"\n正在搜索公众号: {account_keyword}")
    accounts = client.search_accounts(account_keyword, max_results=5)

    if not accounts:
        print("未找到相关公众号")
        return

    print(f"找到 {len(accounts)} 个结果:")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. {acc['nickname']} ({acc.get('alias', '')})")

    target = accounts[0]
    print(f"\n已选择: {target['nickname']}")

    # 拉取文章
    articles = client.fetch_all_articles(
        fakeid=target["fakeid"],
        max_articles=max_articles,
    )

    if not articles:
        print("未获取到文章")
        return

    # 导出
    exporter = ArticleExporter(
        articles=articles,
        output_dir=output_dir,
        account_name=target["nickname"],
    )

    results = {}
    if "json" in export_formats:
        results["json"] = exporter.export_json()
    if "excel" in export_formats:
        results["excel"] = exporter.export_excel()

    if any(fmt in export_formats for fmt in ["html", "markdown", "txt"]):
        html_dir = os.path.join(output_dir, "html")
        client.batch_download_html(articles, output_dir=html_dir)
        if "markdown" in export_formats:
            results["markdown"] = exporter.export_markdown(html_dir=html_dir)
        if "txt" in export_formats:
            results["txt"] = exporter.export_txt(html_dir=html_dir)

    print(f"\n{'='*60}")
    print(f"全部完成！")
    print(f"公众号: {target['nickname']}")
    print(f"文章数: {len(articles)} 篇")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    for fmt, path in results.items():
        print(f"  {fmt}: {path}")
    print(f"{'='*60}")

    return {
        "account": target,
        "article_count": len(articles),
        "articles": articles,
        "exports": results,
    }
