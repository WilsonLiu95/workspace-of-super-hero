#!/usr/bin/env python3
"""AI image generation via an OpenAI-compatible image endpoint.

Config comes from environment variables — NO secrets are baked in, so this file
is safe to commit and share. Set these before running (see config.example.sh):

  AIPROXY_API_KEY        (required)  Bearer token for the endpoint
  AIPROXY_ENDPOINT       (required)  full images URL, e.g.
                                     https://<host>/v1/images/generations
                                     comma-separate to add fallbacks (tried in order)
  AIPROXY_MODEL          (optional)  primary model, default gpt-image-2
  AIPROXY_FALLBACK_MODEL (optional)  fallback on 429/5xx, default gemini-3.1-flash-image

Primary model is higher quality (product/marketing shots); fallback is faster and
kicks in automatically when the primary returns 429/5xx.
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from urllib import request, error

PRIMARY_MODEL = os.environ.get("AIPROXY_MODEL", "gpt-image-2")
FALLBACK_MODEL = os.environ.get("AIPROXY_FALLBACK_MODEL", "gemini-3.1-flash-image")


def _endpoints() -> List[str]:
    raw = os.environ.get("AIPROXY_ENDPOINT", "").strip()
    return [e.strip() for e in raw.split(",") if e.strip()]


def _call_api(prompt: str, n: int, model: str, size: Optional[str], api_key: str,
              endpoint: str) -> Tuple[int, dict, Optional[str]]:
    """Return (status_code, body_json_or_empty, retry_after_or_none)."""
    payload = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "response_format": "b64_json",
    }
    if size:
        payload["size"] = size

    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body, None
    except error.HTTPError as e:
        retry_after = e.headers.get("Retry-After") if e.headers else None
        try:
            body = json.loads(e.read().decode("utf-8", "ignore"))
        except Exception:
            body = {"error": {"raw": "non-json error body"}}
        return e.code, body, retry_after
    except error.URLError as e:
        return 0, {"error": {"message": f"network: {e.reason}"}}, None


def generate(prompt: str, n: int, model: str, size: Optional[str], out_dir: Path,
             allow_fallback: bool = True) -> List[Path]:
    api_key = os.environ.get("AIPROXY_API_KEY", "").strip()
    if not api_key:
        sys.stderr.write(
            "[ai-image] AIPROXY_API_KEY is not set. Configure it first "
            "(see config.example.sh in this skill).\n"
        )
        sys.exit(2)

    endpoints = _endpoints()
    if not endpoints:
        sys.stderr.write(
            "[ai-image] AIPROXY_ENDPOINT is not set. Point it at your image "
            "endpoint, e.g. https://<host>/v1/images/generations "
            "(see config.example.sh).\n"
        )
        sys.exit(2)

    tried: List[str] = []
    status, body, retry_after = 0, {}, None
    for ep_idx, endpoint in enumerate(endpoints):
        ep_name = f"endpoint#{ep_idx + 1}"
        tried.append(f"{model}@{ep_name}")
        status, body, retry_after = _call_api(prompt, n, model, size, api_key, endpoint)

        # Retry on 429/5xx with the fallback model (once per endpoint).
        if status != 200 and allow_fallback and model != FALLBACK_MODEL and (status == 429 or 500 <= status < 600):
            sys.stderr.write(
                f"[ai-image] primary model '{model}' failed on {ep_name}: HTTP {status}"
                + (f" (Retry-After={retry_after})" if retry_after else "")
                + f". Falling back to '{FALLBACK_MODEL}'.\n"
            )
            tried.append(f"{FALLBACK_MODEL}@{ep_name}")
            status, body, retry_after = _call_api(prompt, n, FALLBACK_MODEL, size, api_key, endpoint)

        if status == 200:
            break
        # Network error or 5xx → try the next endpoint; 4xx (prompt/params) does not.
        if ep_idx + 1 < len(endpoints) and (status == 0 or status == 429 or 500 <= status < 600):
            sys.stderr.write(f"[ai-image] {ep_name} unusable (status {status}). Trying next endpoint.\n")
            continue
        break

    if status != 200:
        sys.stderr.write(
            f"[ai-image] all attempts failed (tried: {', '.join(tried)}). "
            f"Last status: {status}. Body: {json.dumps(body)[:500]}\n"
        )
        sys.exit(1)

    items = body.get("data") or []
    if not items:
        sys.stderr.write(f"Empty response: {json.dumps(body)[:500]}\n")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    used_model = tried[-1].split("@", 1)[0].replace(".", "-")
    paths: List[Path] = []
    for idx, item in enumerate(items):
        b64 = item.get("b64_json")
        if not b64 and item.get("url", "").startswith("data:"):
            b64 = item["url"].split(",", 1)[1]
        if not b64:
            sys.stderr.write(f"No image data in item {idx}\n")
            continue
        suffix = f"-{idx+1}" if len(items) > 1 else ""
        path = out_dir / f"{used_model}-{ts}{suffix}.jpg"
        path.write_bytes(base64.b64decode(b64))
        paths.append(path.resolve())
    return paths


def main() -> None:
    p = argparse.ArgumentParser(
        description="Generate images via an OpenAI-compatible endpoint (config from env)."
    )
    p.add_argument("prompt", help="Image prompt (required).")
    p.add_argument("-n", "--count", type=int, default=1, help="Number of images, 1-4.")
    p.add_argument("-m", "--model", default=PRIMARY_MODEL,
                   help=f"Model name. Default: {PRIMARY_MODEL}. "
                        f"Known: {PRIMARY_MODEL}, {FALLBACK_MODEL}.")
    p.add_argument("-s", "--size", default=None, help="Hint only; not strictly enforced.")
    p.add_argument("-o", "--out-dir", type=Path, default=Path.cwd(),
                   help="Output directory (default: current dir).")
    p.add_argument("--no-fallback", action="store_true",
                   help="Disable auto-fallback to the fallback model on 429/5xx.")
    args = p.parse_args()

    if not 1 <= args.count <= 4:
        sys.stderr.write("--count must be between 1 and 4\n")
        sys.exit(2)

    paths = generate(args.prompt, args.count, args.model, args.size, args.out_dir,
                     allow_fallback=not args.no_fallback)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
