#!/usr/bin/env python3
"""
Import podcasts from Xiaoyuzhou FM (小宇宙) into the knowledge base.

Usage:
  python3 scripts/import_xiaoyuzhou.py login
  python3 scripts/import_xiaoyuzhou.py search --keyword "AI创业"
  python3 scripts/import_xiaoyuzhou.py fetch --pid 6603ea352d9eae5d0a5f9151
  python3 scripts/import_xiaoyuzhou.py batch --keyword "AI" --top-podcasts 5 --with-transcript
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_XYZ = "https://api.xiaoyuzhoufm.com"
API_BASE_JIKE = "https://api.ruguoapp.com"

DEFAULT_OUTPUT_DIR = os.environ.get(
    "XIAOYUZHOU_OUTPUT_DIR", "./xiaoyuzhou-podcasts"
)
EPISODE_ID_PATTERN = re.compile(r"^- Episode ID:\s*(\S+)\s*$", re.MULTILINE)

SESSION_HEADERS = {
    "Origin": "https://web.okjike.com",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "DNT": "1",
    "Content-Type": "application/json",
}

API_HEADERS = {
    "User-Agent": "okhttp/4.12.0",
    "applicationid": "app.podcast.cosmos",
    "app-version": "2.99.1",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip",
}

POLL_INTERVAL_SEC = 1
POLL_TIMEOUT_SEC = 180

SMS_HEADERS = {
    "User-Agent": "okhttp/4.12.0",
    "applicationid": "app.podcast.cosmos",
    "app-version": "2.99.1",
    "Content-Type": "application/json;charset=utf-8",
    "Accept-Encoding": "gzip",
}

# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------


def _credentials_path() -> Path:
    """Credentials live in ~/.xiaoyuzhou/credentials.json by default.
    Override with XIAOYUZHOU_CREDENTIALS_PATH env var.
    """
    override = os.environ.get("XIAOYUZHOU_CREDENTIALS_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".xiaoyuzhou" / "credentials.json"


def save_credentials(
    access_token: str, refresh_token: str, device_id: str = "",
) -> None:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "device_id": device_id,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Credentials saved to {path}", file=sys.stderr)


def load_credentials() -> dict[str, str] | None:
    path = _credentials_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        if data.get("access_token") and data.get("refresh_token"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# QR-code authentication  (primary path - xyz-web realm)
# ---------------------------------------------------------------------------

# The consumer-side QR login flow (clientId=xyz-web) produces tokens that
# work directly with api.xiaoyuzhoufm.com data endpoints (search, episode,
# transcript). This is the listener-facing auth realm, separate from the
# podcaster studio realm.

QR_API_BASE = "https://web-api.xiaoyuzhoufm.com/v1"
QR_HEADERS = {
    "Content-Type": "application/json",
    "x-midway-app-id": "v6worU4NnWyL",
    "Origin": "https://accounts.xiaoyuzhoufm.com",
    "Referer": "https://accounts.xiaoyuzhoufm.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def render_qr(data: str) -> bool:
    """Render QR code in terminal. Returns False if qrcode lib unavailable."""
    try:
        import qrcode as qr_mod

        qr = qr_mod.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        qr.print_ascii(out=sys.stderr)
        return True
    except ImportError:
        return False


def render_qr_image(data: str, path: str) -> bool:
    """Render QR code as PNG image. Returns False if qrcode lib unavailable."""
    try:
        import qrcode as qr_mod

        img = qr_mod.make(data)
        img.save(path)
        return True
    except (ImportError, Exception):
        return False


def qr_create_session() -> tuple[str, str]:
    """Create QR login session. Returns (qrcode_id, qr_url)."""
    resp = requests.post(
        f"{QR_API_BASE}/auth/qrcode/create",
        headers=QR_HEADERS,
        json={"clientId": "xyz-web"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["url"]


def qr_poll_confirmation(qrcode_id: str) -> tuple[str, str] | None:
    """Poll until QR is scanned and confirmed. Returns (access, refresh) or None on timeout.

    Status flow: WAITTING -> SCANNED -> CONFIRMED/USED
    Tokens are returned in response headers when status moves past WAITTING.
    """
    for i in range(POLL_TIMEOUT_SEC):
        try:
            resp = requests.post(
                f"{QR_API_BASE}/auth/qrcode/login",
                headers=QR_HEADERS,
                json={"id": qrcode_id},
                timeout=10,
            )
            if resp.status_code == 200:
                # Tokens may arrive in headers as soon as user confirms
                access = resp.headers.get("x-jike-access-token")
                refresh = resp.headers.get("x-jike-refresh-token")
                if access and refresh:
                    return access, refresh
                status = resp.json().get("status", "")
                if status not in ("WAITTING", "SCANNED"):
                    # USED, EXPIRED, or other terminal state without tokens
                    return None
        except requests.RequestException:
            pass
        time.sleep(POLL_INTERVAL_SEC)
    return None


def qr_login() -> tuple[str, str]:
    """Full xyz-web QR login flow. Returns (access_token, refresh_token)."""
    qrcode_id, qr_url = qr_create_session()
    print(f"Session: {qrcode_id}", file=sys.stderr)

    if not render_qr(qr_url):
        print("Install 'qrcode' for terminal rendering: pip install qrcode", file=sys.stderr)
        print(f"Or open this URL in a browser to view QR: {qr_url}", file=sys.stderr)

    # Also save as PNG for convenience
    qr_png = Path("/tmp/xiaoyuzhou_login_qr.png")
    if render_qr_image(qr_url, str(qr_png)):
        print(f"QR also saved to {qr_png}", file=sys.stderr)

    print("Scan the QR with the Xiaoyuzhou App, then tap '确认登录'... (timeout 180s)", file=sys.stderr)

    tokens = qr_poll_confirmation(qrcode_id)
    if not tokens:
        raise SystemExit("Timeout: no scan/confirmation detected within 180 seconds")

    print("Login successful!", file=sys.stderr)
    return tokens


def refresh_tokens(
    access_token: str, refresh_token: str, base: str = API_BASE_XYZ,
) -> tuple[str, str]:
    """Refresh tokens. Tries multiple endpoints since xyz-web vs SMS use different paths."""
    # xyz-web realm: /app_auth_tokens.refresh on web-api
    # mobile realm: /app_auth_tokens.refresh on api with mobile headers
    candidates = [
        ("https://web-api.xiaoyuzhoufm.com/app_auth_tokens.refresh", QR_HEADERS),
        (f"{base}/app_auth_tokens.refresh", SMS_HEADERS),
    ]
    last_err = None
    for url, hdrs in candidates:
        try:
            resp = requests.post(
                url,
                headers={
                    **hdrs,
                    "x-jike-access-token": access_token,
                    "x-jike-refresh-token": refresh_token,
                },
                json={},
                timeout=30,
            )
            if resp.status_code == 200:
                new_access = resp.headers.get("x-jike-access-token", access_token)
                new_refresh = resp.headers.get("x-jike-refresh-token", refresh_token)
                return new_access, new_refresh
            last_err = f"{url}: {resp.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
    raise RuntimeError(f"Token refresh failed: {last_err}")


def sms_send_code(phone: str, device_id: str) -> bool:
    """Send SMS verification code. Returns True on success."""
    headers = {**SMS_HEADERS, "x-jike-device-id": device_id}
    resp = requests.post(
        f"{API_BASE_XYZ}/v1/auth/sendCode",
        headers=headers,
        json={"areaCode": "+86", "mobilePhoneNumber": phone},
        timeout=15,
    )
    if resp.status_code == 200:
        return True
    try:
        msg = resp.json().get("toast", resp.text[:200])
    except Exception:
        msg = resp.text[:200]
    print(f"Send code failed: {msg}", file=sys.stderr)
    return False


def sms_login(phone: str, code: str, device_id: str) -> tuple[str, str]:
    """Login with SMS code. Returns (access_token, refresh_token)."""
    headers = {**SMS_HEADERS, "x-jike-device-id": device_id}
    resp = requests.post(
        f"{API_BASE_XYZ}/v1/auth/loginOrSignUpWithSMS",
        headers=headers,
        json={
            "areaCode": "+86",
            "mobilePhoneNumber": phone,
            "verifyCode": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    access = resp.headers.get("x-jike-access-token")
    refresh = resp.headers.get("x-jike-refresh-token")
    if not access or not refresh:
        raise RuntimeError("SMS login succeeded but no tokens in response headers")
    return access, refresh


def interactive_sms_login() -> tuple[str, str, str]:
    """Interactive SMS login. Returns (access_token, refresh_token, device_id)."""
    import uuid as uuid_mod

    device_id = str(uuid_mod.uuid4())
    phone = input("Enter phone number (e.g. 13800138000): ").strip()
    if not phone:
        raise SystemExit("Phone number required")

    print("Sending verification code...", file=sys.stderr)
    if not sms_send_code(phone, device_id):
        raise SystemExit("Failed to send code")
    print("Code sent! Check your phone.", file=sys.stderr)

    code = input("Enter verification code: ").strip()
    if not code:
        raise SystemExit("Verification code required")

    print("Logging in...", file=sys.stderr)
    access, refresh = sms_login(phone, code, device_id)
    print("Login successful!", file=sys.stderr)
    return access, refresh, device_id


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class XiaoyuzhouClient:
    """Authenticated API client for Xiaoyuzhou FM."""

    def __init__(self, access_token: str, refresh_token: str, device_id: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.device_id = device_id
        self.session = requests.Session()
        self.session.headers.update(API_HEADERS)
        self._update_auth_headers()

    def _update_auth_headers(self) -> None:
        self.session.headers["x-jike-access-token"] = self.access_token
        if self.device_id:
            self.session.headers["x-jike-device-id"] = self.device_id

    def _refresh(self) -> bool:
        try:
            self.access_token, self.refresh_token = refresh_tokens(
                self.access_token, self.refresh_token,
            )
            self._update_auth_headers()
            save_credentials(self.access_token, self.refresh_token, self.device_id)
            return True
        except Exception:
            return False

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict[str, Any]:
        url = f"{API_BASE_XYZ}{path}"
        for attempt in range(3):
            try:
                if method == "GET":
                    resp = self.session.get(url, params=params, timeout=30)
                else:
                    resp = self.session.post(url, json=body, timeout=30)

                if resp.status_code == 401 and attempt == 0:
                    if self._refresh():
                        continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                if attempt == 2:
                    raise RuntimeError(f"API request failed: {exc}") from exc
                time.sleep(1 + attempt)
        raise RuntimeError("Unreachable")

    # -- Search --

    def search(
        self,
        keyword: str,
        search_type: str = "PODCAST",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        load_more_key = None

        while len(results) < limit:
            body: dict[str, Any] = {
                "keyword": keyword,
                "type": search_type,
            }
            if load_more_key:
                body["loadMoreKey"] = load_more_key

            data = self._request("POST", "/v1/search/create", body=body)
            for item in data.get("data", []):
                if item.get("type") in ("PODCAST", "EPISODE"):
                    results.append(item)
            load_more_key = data.get("loadMoreKey")
            if not load_more_key:
                break
            time.sleep(random.uniform(0.5, 1.5))

        return results[:limit]

    # -- Episodes --

    def fetch_podcast_episodes(
        self, pid: str, limit: int | None = None, order: str = "desc",
    ) -> list[dict[str, Any]]:
        episodes: list[dict[str, Any]] = []
        load_more_key = None

        while True:
            body: dict[str, Any] = {"pid": pid, "order": order}
            if load_more_key:
                body["loadMoreKey"] = load_more_key

            data = self._request("POST", "/v1/episode/list", body=body)
            batch = data.get("data", [])
            episodes.extend(batch)
            print(
                f"  Fetched {len(episodes)} episodes",
                file=sys.stderr,
            )

            if limit and len(episodes) >= limit:
                return episodes[:limit]

            load_more_key = data.get("loadMoreKey")
            if not load_more_key or not batch:
                break
            time.sleep(random.uniform(0.5, 1.5))

        return episodes

    def fetch_episode_detail(self, eid: str) -> dict[str, Any]:
        return self._request("GET", "/v1/episode/get", params={"eid": eid})

    def fetch_transcript(self, eid: str, media_id: str) -> str | None:
        try:
            data = self._request(
                "POST",
                "/v1/episode-transcript/get",
                body={"eid": eid, "mediaId": media_id},
            )
            paragraphs = data.get("data", {}).get("paragraphs", [])
            if not paragraphs:
                return None
            lines: list[str] = []
            for p in paragraphs:
                text = p.get("text", "").strip()
                if text:
                    lines.append(text)
            return "\n\n".join(lines) if lines else None
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Text utilities (adapted from import_getnote.py)
# ---------------------------------------------------------------------------


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def html_to_text(html: str | None) -> str:
    """Convert show-notes HTML to plain text while preserving structure."""
    if not html:
        return ""
    text = html
    # Replace block-level tags with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|h[1-6]|li|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&hellip;", "…")
    )
    # Collapse excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_filename(value: str, max_length: int = 80) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    text = re.sub(r"[\u0000-\u001f\u007f]", " ", text)
    text = re.sub(r"[\\/:*?\"<>|#%&\[\]\{\}`$@!+=~]", " ", text)
    text = re.sub(r"[^\w\s\-\(\)]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"[_\s]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    if len(text) > max_length:
        text = text[:max_length].rstrip("-.")
    return text or "untitled"


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "-"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def extract_podcast_name(episode: dict[str, Any]) -> str:
    podcast = episode.get("podcast") or {}
    return clean_text(podcast.get("title")) or "unknown-podcast"


def build_episode_markdown(
    episode: dict[str, Any], transcript: str | None = None,
) -> str:
    title = clean_text(episode.get("title")) or "Untitled"
    eid = episode.get("eid", "")
    podcast = episode.get("podcast") or {}
    podcast_name = clean_text(podcast.get("title")) or "-"
    pid = podcast.get("pid", "")
    published = episode.get("pubDate") or episode.get("publishedAt") or "-"
    if isinstance(published, str) and len(published) >= 10:
        published = published[:10]
    duration = format_duration(episode.get("duration"))
    shownotes = html_to_text(episode.get("shownotes") or episode.get("description"))

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append("- Source: Xiaoyuzhou FM")
    lines.append(f"- Podcast: {podcast_name}")
    lines.append(f"- Podcast ID: {pid}")
    lines.append(f"- Episode ID: {eid}")
    lines.append(f"- Published: {published}")
    lines.append(f"- Duration: {duration}")
    lines.append(f"- Link: https://www.xiaoyuzhoufm.com/episode/{eid}")
    lines.append(f"- Tags: podcast, {sanitize_filename(podcast_name)}")
    lines.append("")

    if shownotes:
        lines.append("## Show Notes")
        lines.append("")
        lines.append(shownotes)
        lines.append("")

    lines.append("## Transcript")
    lines.append("")
    if transcript:
        lines.append(transcript)
    else:
        lines.append("(No transcript available)")
    lines.append("")
    return "\n".join(lines)


def build_podcast_readme(
    podcast_name: str,
    episodes: list[dict[str, Any]],
    episode_paths: dict[str, Path],
    output_dir: Path,
) -> str:
    lines: list[str] = []
    lines.append(f"# {podcast_name}")
    lines.append("")
    lines.append(f"- Source: Xiaoyuzhou FM")
    lines.append(f"- Total episodes exported: {len(episodes)}")
    lines.append("")
    lines.append("## Episodes")
    lines.append("")
    lines.append("| Date | Title | File |")
    lines.append("|---|---|---|")

    sorted_eps = sorted(
        episodes,
        key=lambda e: str(e.get("pubDate") or e.get("publishedAt") or ""),
        reverse=True,
    )
    for ep in sorted_eps[:50]:
        eid = ep.get("eid", "")
        title = clean_text(ep.get("title") or "Untitled").replace("|", "\\|")
        pub = str(ep.get("pubDate") or ep.get("publishedAt") or "-")[:10]
        path = episode_paths.get(eid)
        if path:
            rel = path.relative_to(output_dir).as_posix()
            lines.append(f"| {pub} | {title} | [{rel}]({rel}) |")
        else:
            lines.append(f"| {pub} | {title} | - |")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def episode_date(episode: dict[str, Any]) -> str:
    raw = str(episode.get("pubDate") or episode.get("publishedAt") or "1970-01-01")
    return raw[:10] if re.match(r"\d{4}-\d{2}-\d{2}", raw[:10]) else "unknown"


def build_episode_paths(
    output_dir: Path, podcast_name: str, episodes: list[dict[str, Any]],
) -> dict[str, Path]:
    podcast_dir_name = sanitize_filename(podcast_name)
    paths: dict[str, Path] = {}
    used: set[Path] = set()

    for ep in sorted(episodes, key=lambda e: episode_date(e)):
        eid = ep.get("eid", "")
        day = episode_date(ep)
        month = day[:7]
        title_part = sanitize_filename(clean_text(ep.get("title") or "untitled"))
        stem = f"{day}-{title_part}"
        path = output_dir / podcast_dir_name / month / f"{stem}.md"
        suffix = 2
        while path in used:
            path = output_dir / podcast_dir_name / month / f"{stem}-{suffix}.md"
            suffix += 1
        used.add(path)
        paths[eid] = path

    return paths


def discover_existing_eids(output_dir: Path) -> set[str]:
    eids: set[str] = set()
    if not output_dir.exists():
        return eids
    for p in output_dir.rglob("*.md"):
        if p.name == "README.md":
            continue
        try:
            content = p.read_text("utf-8")
        except OSError:
            continue
        match = EPISODE_ID_PATTERN.search(content)
        if match:
            eids.add(match.group(1))
    return eids


def export_episodes(
    output_dir: Path,
    podcast_name: str,
    episodes: list[dict[str, Any]],
    episode_paths: dict[str, Path],
    transcripts: dict[str, str],
) -> tuple[int, int]:
    written = 0
    unchanged = 0

    for idx, ep in enumerate(episodes, 1):
        eid = ep.get("eid", "")
        path = episode_paths.get(eid)
        if not path:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        md = build_episode_markdown(ep, transcripts.get(eid))

        existing = path.read_text("utf-8") if path.exists() else None
        if existing == md:
            unchanged += 1
        else:
            path.write_text(md, encoding="utf-8")
            written += 1

        print(
            f"  [{idx}/{len(episodes)}] {path.name}",
            file=sys.stderr,
        )

    # Write podcast README
    podcast_dir = output_dir / sanitize_filename(podcast_name)
    podcast_dir.mkdir(parents=True, exist_ok=True)
    readme_md = build_podcast_readme(podcast_name, episodes, episode_paths, output_dir)
    readme_path = podcast_dir / "README.md"
    old = readme_path.read_text("utf-8") if readme_path.exists() else None
    if old != readme_md:
        readme_path.write_text(readme_md, encoding="utf-8")
        written += 1
    else:
        unchanged += 1

    return written, unchanged


# ---------------------------------------------------------------------------
# High-level workflows
# ---------------------------------------------------------------------------


def ensure_client() -> XiaoyuzhouClient:
    """Load credentials or prompt login."""
    # Try env vars first
    env_refresh = os.environ.get("XYZ_REFRESH_TOKEN", "").strip()
    env_device = os.environ.get("XYZ_DEVICE_ID", "").strip()
    if env_refresh:
        access, refresh = refresh_tokens(
            "", env_refresh, API_BASE_XYZ,
        )
        return XiaoyuzhouClient(access, refresh, env_device)

    # Try saved credentials
    creds = load_credentials()
    if creds:
        client = XiaoyuzhouClient(
            creds["access_token"],
            creds["refresh_token"],
            creds.get("device_id", ""),
        )
        # Verify by refreshing
        try:
            client._refresh()
            return client
        except Exception:
            print("Saved credentials expired, re-login required.", file=sys.stderr)

    raise SystemExit(
        "No valid credentials. Run: python3 scripts/import_xiaoyuzhou.py login"
    )


def fetch_transcripts_for_episodes(
    client: XiaoyuzhouClient,
    episodes: list[dict[str, Any]],
) -> dict[str, str]:
    transcripts: dict[str, str] = {}
    for idx, ep in enumerate(episodes, 1):
        eid = ep.get("eid", "")
        media = ep.get("media") or ep.get("enclosure") or {}
        media_id = media.get("id", "")
        if not media_id:
            # Try to get from detail
            try:
                detail = client.fetch_episode_detail(eid)
                ep_data = detail.get("data", detail)
                media = ep_data.get("media") or ep_data.get("enclosure") or {}
                media_id = media.get("id", "")
            except Exception:
                pass

        if media_id:
            print(f"  [{idx}/{len(episodes)}] Fetching transcript for {eid}...", file=sys.stderr)
            text = client.fetch_transcript(eid, media_id)
            if text:
                transcripts[eid] = text
                print(f"    Got {len(text)} chars", file=sys.stderr)
            else:
                print(f"    No transcript", file=sys.stderr)
            time.sleep(random.uniform(2.0, 4.0))
        else:
            print(f"  [{idx}/{len(episodes)}] No media ID, skipping transcript", file=sys.stderr)

    return transcripts


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> int:
    if getattr(args, "sms", False):
        access, refresh, device_id = interactive_sms_login()
        save_credentials(access, refresh, device_id)
    elif getattr(args, "token", False):
        rt = input("Enter refresh_token: ").strip()
        did = input("Enter device_id: ").strip()
        if not rt or not did:
            raise SystemExit("Both refresh_token and device_id are required")
        access, refresh = refresh_tokens(rt, rt)
        save_credentials(access, refresh, did)
    else:
        # Default: QR code login (xyz-web realm)
        access, refresh = qr_login()
        save_credentials(access, refresh, "xyz-web-qr")
    print("Login complete. You can now use search/fetch/batch commands.", file=sys.stderr)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    client = ensure_client()
    search_type = args.type.upper()
    results = client.search(args.keyword, search_type, args.limit)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print("No results found.", file=sys.stderr)
        return 0

    for item in results:
        item_type = item.get("type", "?")
        if item_type == "PODCAST":
            pid = item.get("pid", "?")
            title = item.get("title", "?")
            author = item.get("author", "?")
            sub_count = item.get("subscriptionCount", 0)
            print(f"[PODCAST] {title}")
            print(f"  PID: {pid}  Author: {author}  Subs: {sub_count}")
            desc = clean_text(item.get("description", ""))
            if desc:
                print(f"  {desc[:120]}...")
            print()
        elif item_type == "EPISODE":
            eid = item.get("eid", "?")
            title = item.get("title", "?")
            podcast = item.get("podcast") or {}
            pname = podcast.get("title", "?")
            print(f"[EPISODE] {title}")
            print(f"  EID: {eid}  Podcast: {pname}")
            print()

    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    client = ensure_client()
    output_dir = Path(args.output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()

    pid = args.pid
    # Extract PID from URL if needed
    url_match = re.search(r"xiaoyuzhoufm\.com/podcast/([a-f0-9]+)", pid)
    if url_match:
        pid = url_match.group(1)

    print(f"Fetching episodes for podcast {pid}...", file=sys.stderr)
    episodes = client.fetch_podcast_episodes(pid, limit=args.limit)
    if not episodes:
        print("No episodes found.", file=sys.stderr)
        return 1

    podcast_name = extract_podcast_name(episodes[0])
    print(f"Podcast: {podcast_name} ({len(episodes)} episodes)", file=sys.stderr)

    # Fetch transcripts if requested
    transcripts: dict[str, str] = {}
    if args.with_transcript:
        print("Fetching transcripts...", file=sys.stderr)
        transcripts = fetch_transcripts_for_episodes(client, episodes)

    # Build paths and export
    episode_paths = build_episode_paths(output_dir, podcast_name, episodes)
    written, unchanged = export_episodes(
        output_dir, podcast_name, episodes, episode_paths, transcripts,
    )

    summary = {
        "podcast": podcast_name,
        "pid": pid,
        "total_episodes": len(episodes),
        "transcripts_fetched": len(transcripts),
        "written": written,
        "unchanged": unchanged,
        "output_dir": output_dir.as_posix(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    client = ensure_client()
    output_dir = Path(args.output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()

    pids: list[str] = []

    if args.pids:
        pids = [p.strip() for p in args.pids.split(",") if p.strip()]
        # Extract PIDs from URLs
        cleaned: list[str] = []
        for p in pids:
            m = re.search(r"xiaoyuzhoufm\.com/podcast/([a-f0-9]+)", p)
            cleaned.append(m.group(1) if m else p)
        pids = cleaned
    elif args.keyword:
        print(f"Searching for podcasts: {args.keyword}...", file=sys.stderr)
        results = client.search(args.keyword, "PODCAST", args.top_podcasts * 3)
        podcasts = [r for r in results if r.get("type") == "PODCAST"]
        pids = [p["pid"] for p in podcasts[: args.top_podcasts] if p.get("pid")]
        for p in podcasts[: args.top_podcasts]:
            print(f"  Found: {p.get('title', '?')} (PID: {p.get('pid', '?')})", file=sys.stderr)
    else:
        raise SystemExit("Provide --pids or --keyword")

    if not pids:
        print("No podcasts found.", file=sys.stderr)
        return 1

    all_summaries: list[dict[str, Any]] = []
    for i, pid in enumerate(pids, 1):
        print(f"\n[{i}/{len(pids)}] Fetching podcast {pid}...", file=sys.stderr)
        episodes = client.fetch_podcast_episodes(
            pid, limit=args.limit_per_podcast,
        )
        if not episodes:
            print(f"  No episodes for {pid}", file=sys.stderr)
            continue

        podcast_name = extract_podcast_name(episodes[0])
        print(f"  {podcast_name}: {len(episodes)} episodes", file=sys.stderr)

        transcripts: dict[str, str] = {}
        if args.with_transcript:
            print("  Fetching transcripts...", file=sys.stderr)
            transcripts = fetch_transcripts_for_episodes(client, episodes)

        episode_paths = build_episode_paths(output_dir, podcast_name, episodes)
        written, unchanged = export_episodes(
            output_dir, podcast_name, episodes, episode_paths, transcripts,
        )

        all_summaries.append({
            "podcast": podcast_name,
            "pid": pid,
            "episodes": len(episodes),
            "transcripts": len(transcripts),
            "written": written,
            "unchanged": unchanged,
        })
        time.sleep(random.uniform(1.0, 2.0))

    summary = {
        "total_podcasts": len(all_summaries),
        "podcasts": all_summaries,
        "output_dir": output_dir.as_posix(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xiaoyuzhou",
        description=(
            "小宇宙播客拉取工具 — 搜索 / 拉取单集 / 逐字稿 / 批量导入。"
            "默认 QR 扫码登录，凭据保存在 ~/.xiaoyuzhou/credentials.json。"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # login
    sp_login = sub.add_parser("login", help="Login to Xiaoyuzhou FM (default: QR code)")
    sp_login.add_argument("--sms", action="store_true", help="Use SMS verification code login instead of QR")
    sp_login.add_argument("--token", action="store_true", help="Manually input refresh_token + device_id")

    # search
    sp_search = sub.add_parser("search", help="Search for podcasts or episodes")
    sp_search.add_argument("--keyword", required=True, help="Search keyword")
    sp_search.add_argument(
        "--type", default="podcast", choices=["podcast", "episode", "all"],
        help="Search type (default: podcast)",
    )
    sp_search.add_argument("--limit", type=int, default=20, help="Max results")
    sp_search.add_argument("--json", action="store_true", help="Output as JSON")

    # fetch
    sp_fetch = sub.add_parser("fetch", help="Fetch episodes from a podcast")
    sp_fetch.add_argument("--pid", required=True, help="Podcast ID or URL")
    sp_fetch.add_argument("--with-transcript", action="store_true", help="Also fetch transcripts")
    sp_fetch.add_argument("--limit", type=int, help="Max episodes to fetch")
    sp_fetch.add_argument("--output-dir", help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")

    # batch
    sp_batch = sub.add_parser("batch", help="Batch fetch multiple podcasts")
    sp_batch.add_argument("--pids", help="Comma-separated podcast IDs or URLs")
    sp_batch.add_argument("--keyword", help="Search keyword to find podcasts")
    sp_batch.add_argument("--top-podcasts", type=int, default=3, help="Top N podcasts from search")
    sp_batch.add_argument("--with-transcript", action="store_true", help="Also fetch transcripts")
    sp_batch.add_argument("--limit-per-podcast", type=int, default=50, help="Max episodes per podcast")
    sp_batch.add_argument("--output-dir", help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "login": cmd_login,
        "search": cmd_search,
        "fetch": cmd_fetch,
        "batch": cmd_batch,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
