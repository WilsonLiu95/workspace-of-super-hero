"""
微信公众号文章抓取客户端

支持两种模式：
1. Credential 模式（推荐，免登录）：通过微信流量中抓取的 credential 调用公开 API
2. MP 后台模式：通过 mp.weixin.qq.com 后台 token 调用管理 API

Credential 模式不需要公众号管理权限，只需要从微信客户端的网络流量中
提取 __biz、uin、key、pass_ticket 四个参数即可。
"""

import json
import os
import re
import time
import urllib.parse
from datetime import datetime
from typing import Optional

import requests


class WeChatMPClient:
    """微信公众号 MP 平台 API 客户端"""

    BASE_URL = "https://mp.weixin.qq.com/cgi-bin"
    ARTICLE_PAGE_SIZE = 20  # 微信 API 每页最大返回数
    ACCOUNT_PAGE_SIZE = 5   # 搜索账号每页最大返回数

    def __init__(self, token: str, cookie: str, request_interval: float = 3.0):
        """
        初始化客户端

        Args:
            token: 从 mp.weixin.qq.com 获取的 token（URL 参数中的 token=xxx）
            cookie: 从 mp.weixin.qq.com 获取的完整 Cookie 头
            request_interval: 每次请求之间的间隔秒数，默认 3 秒
        """
        self.token = token
        self.cookie = cookie
        self.request_interval = request_interval
        self.session = requests.Session()
        self.session.headers.update({
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })
        self._last_request_time = 0

    def _rate_limit(self):
        """速率控制：确保请求之间有足够的间隔"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, endpoint: str, params: dict, max_retries: int = 3) -> dict:
        """
        发送 API 请求，带自动重试和错误处理

        Args:
            endpoint: API 路径（不含 BASE_URL）
            params: 查询参数
            max_retries: 最大重试次数

        Returns:
            API 响应的 JSON 数据

        Raises:
            Exception: 当认证失效或重试耗尽时
        """
        params["token"] = self.token
        params["lang"] = "zh_CN"
        params["f"] = "json"
        params["ajax"] = "1"

        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(max_retries):
            self._rate_limit()

            try:
                resp = self.session.get(url, params=params, timeout=30)

                # 检查是否被重定向到登录页
                if "login" in resp.url and "token" not in resp.url:
                    raise AuthExpiredError(
                        "Token 已过期，请重新从 mp.weixin.qq.com 获取 token 和 cookie"
                    )

                data = resp.json()

                # 检查基础响应
                base_resp = data.get("base_resp", {})
                ret = base_resp.get("ret", 0)

                if ret == 200014:
                    raise AuthExpiredError(
                        "Token 已过期（错误码 200014），请重新获取 token 和 cookie"
                    )
                elif ret == 200013:
                    # 频率限制
                    wait_time = 60
                    print(f"  ⚠ 触发频率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                elif ret == -1:
                    # 系统繁忙
                    wait_time = 5
                    print(f"  ⚠ 系统繁忙，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                elif ret != 0:
                    raise APIError(f"API 返回错误码 {ret}: {base_resp.get('err_msg', '未知错误')}")

                return data

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"  ⚠ 请求超时，等待 10 秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(10)
                    continue
                raise
            except (AuthExpiredError, APIError):
                raise
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠ 网络错误: {e}，等待 5 秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(5)
                    continue
                raise

        raise APIError(f"请求 {endpoint} 失败，已重试 {max_retries} 次")

    # ============================================================
    # 公众号搜索
    # ============================================================

    def search_accounts(self, keyword: str, max_results: int = 10) -> list:
        """
        搜索公众号

        Args:
            keyword: 搜索关键词（公众号名称、微信号等）
            max_results: 最大返回数量

        Returns:
            公众号列表，每个包含 fakeid, nickname, alias, round_head_img, service_type
        """
        accounts = []
        begin = 0

        while len(accounts) < max_results:
            data = self._request("searchbiz", {
                "action": "search_biz",
                "begin": begin,
                "count": self.ACCOUNT_PAGE_SIZE,
                "query": keyword,
            })

            items = data.get("list", [])
            if not items:
                break

            for item in items:
                accounts.append({
                    "fakeid": item.get("fakeid", ""),
                    "nickname": item.get("nickname", ""),
                    "alias": item.get("alias", ""),
                    "round_head_img": item.get("round_head_img", ""),
                    "service_type": item.get("service_type", -1),
                })

            begin += self.ACCOUNT_PAGE_SIZE
            if len(items) < self.ACCOUNT_PAGE_SIZE:
                break

        return accounts[:max_results]

    # ============================================================
    # 文章列表拉取
    # ============================================================

    def fetch_articles_page(self, fakeid: str, begin: int = 0, keyword: str = "") -> dict:
        """
        拉取单页文章列表

        Args:
            fakeid: 公众号的 fakeid
            begin: 分页偏移量
            keyword: 搜索关键词（可选，用于在公众号内搜索）

        Returns:
            包含 articles（文章列表）和 total_count（总数）的字典
        """
        data = self._request("appmsgpublish", {
            "sub": "list",
            "search_field": "null",
            "begin": begin,
            "count": self.ARTICLE_PAGE_SIZE,
            "query": keyword,
            "fakeid": fakeid,
            "type": "101_1",
            "free_publish_type": "1",
            "sub_action": "list_ex",
        })

        publish_page = data.get("publish_page", {})

        # publish_page 可能是 JSON 字符串
        if isinstance(publish_page, str):
            publish_page = json.loads(publish_page)

        total_count = publish_page.get("total_count", 0)
        publish_list = publish_page.get("publish_list", [])

        articles = []
        for item in publish_list:
            publish_info = item.get("publish_info", {})
            if isinstance(publish_info, str):
                publish_info = json.loads(publish_info)

            appmsgex = publish_info.get("appmsgex", [])
            for msg in appmsgex:
                articles.append({
                    "aid": msg.get("aid", ""),
                    "title": msg.get("title", ""),
                    "link": msg.get("link", ""),
                    "digest": msg.get("digest", ""),
                    "cover": msg.get("cover", ""),
                    "create_time": msg.get("create_time", 0),
                    "update_time": msg.get("update_time", 0),
                    "item_show_type": msg.get("item_show_type", 0),
                })

        return {
            "articles": articles,
            "total_count": total_count,
        }

    def fetch_all_articles(
        self,
        fakeid: str,
        keyword: str = "",
        max_articles: Optional[int] = None,
        progress_callback=None,
    ) -> list:
        """
        拉取公众号的全部历史文章（自动翻页）

        Args:
            fakeid: 公众号的 fakeid
            keyword: 搜索关键词（可选）
            max_articles: 最大拉取数量，None 表示全部
            progress_callback: 进度回调函数，签名 callback(fetched, total)

        Returns:
            全部文章列表
        """
        all_articles = []
        begin = 0
        total_count = None
        empty_page_count = 0  # 连续空页计数
        MAX_EMPTY_PAGES = 3   # 连续空页超过此数才停止

        print(f"开始拉取文章列表...")

        while True:
            try:
                result = self.fetch_articles_page(fakeid, begin, keyword)
            except APIError as e:
                print(f"  ⚠ 第 {begin} 页请求失败: {e}")
                # 跳过这一页继续尝试下一页
                begin += self.ARTICLE_PAGE_SIZE
                empty_page_count += 1
                if empty_page_count >= MAX_EMPTY_PAGES:
                    print(f"  连续 {MAX_EMPTY_PAGES} 页失败，停止拉取")
                    break
                continue

            if total_count is None:
                total_count = result["total_count"]
                print(f"  总计约 {total_count} 条发布记录")

            page_articles = result["articles"]
            if not page_articles:
                empty_page_count += 1
                if empty_page_count >= MAX_EMPTY_PAGES:
                    break
                # 空页但还没到总数，跳到下一页继续
                begin += self.ARTICLE_PAGE_SIZE
                if begin >= total_count:
                    break
                continue

            empty_page_count = 0  # 有数据则重置空页计数
            all_articles.extend(page_articles)

            fetched = len(all_articles)
            print(f"  已拉取 {fetched} 篇（offset={begin}）")

            if progress_callback:
                progress_callback(fetched, total_count)

            if max_articles and fetched >= max_articles:
                all_articles = all_articles[:max_articles]
                break

            begin += self.ARTICLE_PAGE_SIZE
            if begin >= total_count:
                break

        print(f"拉取完成，共 {len(all_articles)} 篇文章")
        return all_articles

    # ============================================================
    # 文章内容下载
    # ============================================================

    def download_article_html(self, article_url: str) -> str:
        """
        下载单篇文章的完整 HTML

        Args:
            article_url: 文章链接

        Returns:
            HTML 字符串
        """
        self._rate_limit()

        resp = self.session.get(article_url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })
        resp.encoding = "utf-8"
        return resp.text

    def batch_download_html(
        self,
        articles: list,
        output_dir: str,
        skip_existing: bool = True,
        progress_callback=None,
    ) -> dict:
        """
        批量下载文章 HTML

        Args:
            articles: 文章列表（需包含 title, link, create_time）
            output_dir: 输出目录
            skip_existing: 是否跳过已下载的文件
            progress_callback: 进度回调 callback(downloaded, total, title)

        Returns:
            下载结果统计 {success, failed, skipped, errors}
        """
        os.makedirs(output_dir, exist_ok=True)

        stats = {"success": 0, "failed": 0, "skipped": 0, "errors": []}
        total = len(articles)

        for i, article in enumerate(articles):
            title = sanitize_filename(article.get("title", f"untitled_{i}"))
            create_time = article.get("create_time", 0)
            date_str = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d") if create_time else "unknown"
            filename = f"{date_str}_{title}.html"
            filepath = os.path.join(output_dir, filename)

            if skip_existing and os.path.exists(filepath):
                stats["skipped"] += 1
                print(f"  [{i+1}/{total}] 跳过（已存在）: {title}")
                continue

            try:
                link = article.get("link", "")
                if not link:
                    stats["failed"] += 1
                    stats["errors"].append({"title": title, "error": "无链接"})
                    continue

                html = self.download_article_html(link)

                # 检查是否为有效文章内容
                if "该内容已被发布者删除" in html or len(html) < 500:
                    stats["failed"] += 1
                    stats["errors"].append({"title": title, "error": "文章已删除或无效"})
                    print(f"  [{i+1}/{total}] 失败（已删除）: {title}")
                    continue

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)

                stats["success"] += 1
                print(f"  [{i+1}/{total}] 已下载: {title}")

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"title": title, "error": str(e)})
                print(f"  [{i+1}/{total}] 失败: {title} - {e}")

            if progress_callback:
                progress_callback(i + 1, total, article.get("title", ""))

        print(f"\n下载完成: 成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}")
        return stats


# ============================================================
# 辅助函数
# ============================================================

def sanitize_filename(name: str, max_length: int = 80) -> str:
    """清理文件名，移除非法字符"""
    # 替换非法字符
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', name)
    # 去除首尾空格和点
    name = name.strip('. ')
    # 截断
    if len(name) > max_length:
        name = name[:max_length]
    return name or "untitled"


# ============================================================
# 异常类
# ============================================================

class AuthExpiredError(Exception):
    """认证过期异常"""
    pass


class APIError(Exception):
    """API 调用异常"""
    pass


class CredentialExpiredError(Exception):
    """Credential 过期异常"""
    pass


# ============================================================
# Credential 模式客户端（免登录）
# ============================================================

class WeChatCredentialClient:
    """
    基于 Credential 的微信公众号文章客户端（免登录）

    使用微信公开的 profile_ext API 拉取文章列表，
    不需要登录 mp.weixin.qq.com 后台。

    Credential 来源：从微信客户端/网页版的网络请求中提取。
    用户只需在微信中打开目标公众号的任意一篇文章，
    然后从浏览器开发者工具 / 抓包工具中提取以下参数即可。
    """

    PROFILE_EXT_URL = "https://mp.weixin.qq.com/mp/profile_ext"
    PAGE_SIZE = 10  # profile_ext API 每页返回数

    def __init__(
        self,
        biz: str,
        uin: str,
        key: str,
        pass_ticket: str,
        request_interval: float = 3.0,
    ):
        """
        初始化 Credential 客户端

        Args:
            biz: 公众号的 __biz 参数（Base64 编码的公众号 ID）
            uin: 用户标识（从微信流量中提取）
            key: 会话密钥（从微信流量中提取）
            pass_ticket: 通行票据（从微信流量中提取）
            request_interval: 请求间隔秒数
        """
        self.biz = biz
        self.uin = uin
        self.key = key
        self.pass_ticket = pass_ticket
        self.request_interval = request_interval
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Mobile Safari/537.36 "
                          "MicroMessenger/8.0.44",
            "Referer": "https://mp.weixin.qq.com/",
            "Accept": "*/*",
            "X-Requested-With": "com.tencent.mm",
        })
        self._last_request_time = 0

    def _rate_limit(self):
        """速率控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self._last_request_time = time.time()

    def fetch_articles_page(self, offset: int = 0) -> dict:
        """
        通过 profile_ext API 拉取单页文章列表

        Args:
            offset: 分页偏移量

        Returns:
            dict: {articles, can_continue, next_offset}
        """
        self._rate_limit()

        params = {
            "action": "getmsg",
            "__biz": self.biz,
            "f": "json",
            "offset": offset,
            "count": self.PAGE_SIZE,
            "is_ok": "1",
            "scene": "124",
            "uin": self.uin,
            "key": self.key,
            "pass_ticket": self.pass_ticket,
        }

        try:
            resp = self.session.get(
                self.PROFILE_EXT_URL, params=params, timeout=30
            )
            data = resp.json()
        except requests.exceptions.RequestException as e:
            raise APIError(f"网络请求失败: {e}")
        except json.JSONDecodeError:
            raise APIError(f"返回数据格式错误（可能 credential 已过期）")

        ret = data.get("ret", -1)
        if ret != 0:
            errmsg = data.get("errmsg", "未知错误")
            if "invalid" in errmsg.lower() or ret in (-3, -4):
                raise CredentialExpiredError(
                    f"Credential 已过期（ret={ret}），请重新从微信流量中获取。"
                    f"\n提示：Credential 有效期约 25 分钟。"
                )
            raise APIError(f"profile_ext API 错误 (ret={ret}): {errmsg}")

        can_continue = data.get("can_msg_continue", 0)
        next_offset = data.get("next_offset", offset + self.PAGE_SIZE)

        # 解析文章列表
        general_msg_list_str = data.get("general_msg_list", "{}")
        if isinstance(general_msg_list_str, str):
            general_msg_list = json.loads(general_msg_list_str)
        else:
            general_msg_list = general_msg_list_str

        articles = []
        for msg in general_msg_list.get("list", []):
            comm_msg_info = msg.get("comm_msg_info", {})
            app_msg_ext_info = msg.get("app_msg_ext_info", {})

            if not app_msg_ext_info:
                continue

            # 主文章
            articles.append(self._parse_article(app_msg_ext_info, comm_msg_info))

            # 多图文消息中的子文章
            for sub in app_msg_ext_info.get("multi_app_msg_item_list", []):
                articles.append(self._parse_article(sub, comm_msg_info))

        return {
            "articles": articles,
            "can_continue": can_continue == 1,
            "next_offset": next_offset,
        }

    def _parse_article(self, ext_info: dict, comm_info: dict) -> dict:
        """解析单篇文章数据"""
        title = ext_info.get("title", "")
        link = ext_info.get("content_url", "")

        # 清理 HTML 实体
        if link:
            link = link.replace("&amp;", "&")

        return {
            "title": title,
            "link": link,
            "digest": ext_info.get("digest", ""),
            "cover": ext_info.get("cover", ""),
            "author": ext_info.get("author", ""),
            "create_time": comm_info.get("datetime", 0),
            "source_url": ext_info.get("source_url", ""),
            "content_url": link,
        }

    def fetch_all_articles(
        self,
        max_articles: Optional[int] = None,
        progress_callback=None,
    ) -> list:
        """
        拉取公众号全部历史文章（自动翻页）

        Args:
            max_articles: 最大拉取数量，None 表示全部
            progress_callback: 进度回调 callback(fetched_count)

        Returns:
            全部文章列表
        """
        all_articles = []
        offset = 0

        print(f"开始通过 Credential 模式拉取文章列表...")

        while True:
            try:
                result = self.fetch_articles_page(offset)
            except CredentialExpiredError:
                print(f"\n⚠ Credential 已过期，已拉取 {len(all_articles)} 篇")
                print("  提示：请重新获取 credential 后继续")
                break

            page_articles = result["articles"]
            if not page_articles:
                break

            all_articles.extend(page_articles)
            fetched = len(all_articles)
            print(f"  已拉取 {fetched} 篇（offset={offset}）")

            if progress_callback:
                progress_callback(fetched)

            if max_articles and fetched >= max_articles:
                all_articles = all_articles[:max_articles]
                break

            if not result["can_continue"]:
                break

            offset = result["next_offset"]

        print(f"拉取完成，共 {len(all_articles)} 篇文章")
        return all_articles

    def download_article_html(self, article_url: str) -> str:
        """下载单篇文章 HTML"""
        self._rate_limit()
        resp = self.session.get(article_url, timeout=30)
        resp.encoding = "utf-8"
        return resp.text

    def batch_download_html(
        self,
        articles: list,
        output_dir: str,
        skip_existing: bool = True,
        progress_callback=None,
    ) -> dict:
        """批量下载文章 HTML（与 WeChatMPClient.batch_download_html 同接口）"""
        os.makedirs(output_dir, exist_ok=True)
        stats = {"success": 0, "failed": 0, "skipped": 0, "errors": []}
        total = len(articles)

        for i, article in enumerate(articles):
            title = sanitize_filename(article.get("title", f"untitled_{i}"))
            create_time = article.get("create_time", 0)
            date_str = (
                datetime.fromtimestamp(create_time).strftime("%Y-%m-%d")
                if create_time
                else "unknown"
            )
            filename = f"{date_str}_{title}.html"
            filepath = os.path.join(output_dir, filename)

            if skip_existing and os.path.exists(filepath):
                stats["skipped"] += 1
                continue

            try:
                link = article.get("link", "") or article.get("content_url", "")
                if not link:
                    stats["failed"] += 1
                    stats["errors"].append({"title": title, "error": "无链接"})
                    continue

                html = self.download_article_html(link)

                if "该内容已被发布者删除" in html or len(html) < 500:
                    stats["failed"] += 1
                    stats["errors"].append({"title": title, "error": "文章已删除或无效"})
                    print(f"  [{i+1}/{total}] 失败（已删除）: {title}")
                    continue

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)

                stats["success"] += 1
                print(f"  [{i+1}/{total}] 已下载: {title}")

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"title": title, "error": str(e)})
                print(f"  [{i+1}/{total}] 失败: {title} - {e}")

            if progress_callback:
                progress_callback(i + 1, total, article.get("title", ""))

        print(f"\n下载完成: 成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}")
        return stats


# ============================================================
# 辅助函数：从文章 URL 中提取 __biz
# ============================================================

def extract_biz_from_url(article_url: str) -> Optional[str]:
    """
    从微信文章 URL 中提取 __biz 参数

    Args:
        article_url: 微信文章链接

    Returns:
        __biz 值，如果提取失败返回 None
    """
    parsed = urllib.parse.urlparse(article_url)
    params = urllib.parse.parse_qs(parsed.query)
    biz = params.get("__biz", [None])[0]
    return biz
