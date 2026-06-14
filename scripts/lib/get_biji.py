#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def load_local_exports() -> None:
    path = os.path.expanduser("~/.zshrc.local")
    if not os.path.isfile(path):
        return

    pattern = re.compile(r"^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$")
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            match = pattern.match(line)
            if not match:
                continue

            key, raw_value = match.groups()
            if key in os.environ:
                continue

            value = raw_value.strip()
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in ("'", '"')
            ):
                value = value[1:-1]

            os.environ[key] = os.path.expandvars(value)


load_local_exports()

RESOURCE_BASE_URL = os.environ.get(
    "GET_BIJI_RESOURCE_BASE_URL", "https://openapi.biji.com/open/api/v1"
)
KNOWLEDGE_BASE_URL = os.environ.get(
    "GET_BIJI_KNOWLEDGE_BASE_URL", "https://open-api.biji.com/getnote/openapi"
)


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def parse_history(value: str | None):
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON for --history-json: {exc}")
    if not isinstance(parsed, list):
        fail("--history-json must be a JSON array")
    return parsed


def request_json(method: str, url: str, headers: dict[str, str], body=None):
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        fail(f"HTTP {exc.code} for {url}\n{error_body}", code=1)
    except urllib.error.URLError as exc:
        fail(f"Request failed for {url}: {exc}", code=1)

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw": payload}


def notes_list(args):
    api_key = require_env("GET_BIJI_API_KEY")
    client_id = require_env("GET_BIJI_CLIENT_ID")
    query = urllib.parse.urlencode({"since_id": args.since_id})
    url = f"{RESOURCE_BASE_URL}/resource/note/list?{query}"
    headers = {
        "Authorization": api_key,
        "X-Client-ID": client_id,
    }
    return request_json("GET", url, headers)


def resolve_topic_id(explicit_topic_id: str | None) -> str:
    if explicit_topic_id:
        return explicit_topic_id
    default_topic_id = os.environ.get("GET_BIJI_DEFAULT_TOPIC_ID")
    if default_topic_id:
        return default_topic_id
    fail(
        "Missing topic id. Pass --topic-id or set GET_BIJI_DEFAULT_TOPIC_ID for knowledge APIs."
    )


def knowledge_search(args):
    api_key = require_env("GET_BIJI_API_KEY")
    topic_id = resolve_topic_id(args.topic_id)
    url = f"{KNOWLEDGE_BASE_URL}/knowledge/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-OAuth-Version": "1",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    body = {
        "question": args.question,
        "topic_ids": [topic_id],
        "deep_seek": args.deep_seek,
        "refs": args.refs,
    }
    history = parse_history(args.history_json)
    if history:
        body["history"] = history
    return request_json("POST", url, headers, body)


def knowledge_recall(args):
    api_key = require_env("GET_BIJI_API_KEY")
    topic_id = resolve_topic_id(args.topic_id)
    url = f"{KNOWLEDGE_BASE_URL}/knowledge/search/recall"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-OAuth-Version": "1",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    body = {
        "question": args.question,
        "topic_ids": [topic_id],
        "top_k": args.top_k,
    }
    history = parse_history(args.history_json)
    if history:
        body["history"] = history
    if args.intent_rewrite is not None:
        body["intent_rewrite"] = args.intent_rewrite
    if args.select_matrix is not None:
        body["select_matrix"] = args.select_matrix
    return request_json("POST", url, headers, body)


def build_parser():
    parser = argparse.ArgumentParser(description="Get笔记 OpenAPI helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    notes_parser = subparsers.add_parser("notes", help="Resource APIs")
    notes_subparsers = notes_parser.add_subparsers(dest="notes_command", required=True)
    notes_list_parser = notes_subparsers.add_parser("list", help="List notes")
    notes_list_parser.add_argument("--since-id", type=int, default=0)
    notes_list_parser.set_defaults(handler=notes_list)

    knowledge_parser = subparsers.add_parser("knowledge", help="Knowledge APIs")
    knowledge_subparsers = knowledge_parser.add_subparsers(
        dest="knowledge_command", required=True
    )

    search_parser = knowledge_subparsers.add_parser(
        "search", help="Semantic knowledge search"
    )
    search_parser.add_argument("--question", required=True)
    search_parser.add_argument("--topic-id")
    search_parser.add_argument("--deep-seek", action="store_true")
    search_parser.add_argument("--refs", action="store_true")
    search_parser.add_argument("--history-json")
    search_parser.set_defaults(handler=knowledge_search)

    recall_parser = knowledge_subparsers.add_parser(
        "recall", help="Recall raw knowledge snippets"
    )
    recall_parser.add_argument("--question", required=True)
    recall_parser.add_argument("--topic-id")
    recall_parser.add_argument("--top-k", type=int, default=3)
    recall_parser.add_argument("--history-json")
    recall_parser.add_argument(
        "--intent-rewrite",
        dest="intent_rewrite",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    recall_parser.add_argument(
        "--select-matrix",
        dest="select_matrix",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    recall_parser.set_defaults(handler=knowledge_recall)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    result = args.handler(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
