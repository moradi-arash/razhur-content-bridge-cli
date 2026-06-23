#!/usr/bin/env python3
"""Local content archive and internal-link helper for Razhur Content Bridge."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "content-index.json"
TARGETS_PATH = ROOT / "internal-link-targets.json"
POSTS_DIR = ROOT / "content" / "posts"


class MarkdownHTMLParser(HTMLParser):
    """Small HTML-to-Markdown converter for article archives."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.list_depth = 0
        self.in_li = False
        self.href_stack: list[str | None] = []
        self.table_cells: list[str] = []
        self.in_td = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4"}:
            level = int(tag[1])
            self._blank()
            self.parts.append("#" * level + " ")
        elif tag == "p":
            self._blank()
        elif tag in {"ul", "ol"}:
            self.list_depth += 1
            self._blank()
        elif tag == "li":
            self.in_li = True
            self.parts.append("\n" + "  " * max(self.list_depth - 1, 0) + "- ")
        elif tag == "a":
            self.href_stack.append(attrs_dict.get("href"))
            self.parts.append("[")
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag in {"td", "th"}:
            self.in_td = True
            self.table_cells.append("")
        elif tag == "tr":
            self._blank()
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "h4", "p"}:
            self._blank()
        elif tag in {"ul", "ol"}:
            self.list_depth = max(self.list_depth - 1, 0)
            self._blank()
        elif tag == "li":
            self.in_li = False
        elif tag == "a":
            href = self.href_stack.pop() if self.href_stack else None
            self.parts.append(f"]({href})" if href else "]")
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag in {"td", "th"}:
            self.in_td = False
        elif tag == "tr" and self.table_cells:
            row = " | ".join(cell.strip() for cell in self.table_cells)
            self.parts.append(f"\n| {row} |\n")
            self.table_cells = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data)
        if self.in_td and self.table_cells:
            self.table_cells[-1] += text
        else:
            self.parts.append(text)

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"

    def _blank(self) -> None:
        current = "".join(self.parts)
        if not current.endswith("\n\n"):
            if current.endswith("\n"):
                self.parts.append("\n")
            else:
                self.parts.append("\n\n")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-_/]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "post"


def strip_image_data(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = json.loads(json.dumps(payload, ensure_ascii=False))
    featured = cleaned.get("featured_image")
    if isinstance(featured, dict) and featured.get("data"):
        featured["data"] = ""
    return cleaned


def html_to_markdown(content: str) -> str:
    parser = MarkdownHTMLParser()
    parser.feed(content)
    return parser.markdown()


def permalink(base_url: str, payload: dict[str, Any], response: dict[str, Any]) -> str:
    canonical = (payload.get("seo") or {}).get("canonical") if isinstance(payload.get("seo"), dict) else ""
    if canonical:
        return str(canonical)
    slug = str(payload.get("slug") or "").strip("/")
    if slug:
        return f"{base_url.rstrip('/')}/{slug}/"
    post_id = response.get("post_id")
    return f"{base_url.rstrip('/')}/?p={post_id}" if post_id else base_url.rstrip("/")


def entry_from_payload(payload: dict[str, Any], response: dict[str, Any], base_url: str) -> dict[str, Any]:
    seo = payload.get("seo") if isinstance(payload.get("seo"), dict) else {}
    featured = payload.get("featured_image") if isinstance(payload.get("featured_image"), dict) else {}
    return {
        "post_id": response.get("post_id"),
        "type": payload.get("post_type", "post"),
        "status": response.get("status", payload.get("status", "draft")),
        "title": payload.get("title", ""),
        "slug": payload.get("slug", ""),
        "url": permalink(base_url, payload, response),
        "edit_link": response.get("edit_link", ""),
        "preview_link": response.get("preview_link", ""),
        "focus_keyword": seo.get("focus_keyword") or seo.get("keyword") or "",
        "seo_title": seo.get("title", ""),
        "seo_description": seo.get("description", ""),
        "excerpt": payload.get("excerpt", ""),
        "categories": payload.get("categories", []),
        "tags": payload.get("tags", []),
        "featured_image_id": response.get("featured_image_id", 0),
        "featured_image_alt": featured.get("alt", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def archive_post(payload: dict[str, Any], response: dict[str, Any], entry: dict[str, Any]) -> tuple[Path, Path]:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(str(entry.get("slug") or entry.get("post_id") or entry.get("title") or "post"))
    stem = f"{date_prefix}-{slug}"
    json_path = POSTS_DIR / f"{stem}.json"
    md_path = POSTS_DIR / f"{stem}.md"

    save_json(json_path, {"entry": entry, "payload": strip_image_data(payload), "response": response})

    frontmatter = {
        "title": entry.get("title", ""),
        "post_id": entry.get("post_id"),
        "status": entry.get("status"),
        "url": entry.get("url"),
        "edit_link": entry.get("edit_link"),
        "focus_keyword": entry.get("focus_keyword"),
        "tags": entry.get("tags", []),
        "categories": entry.get("categories", []),
    }
    content = str(payload.get("content") or "")
    markdown = html_to_markdown(content) if content else ""
    md_path.write_text(
        "---\n"
        + json.dumps(frontmatter, ensure_ascii=False, indent=2)
        + "\n---\n\n"
        + markdown,
        encoding="utf-8",
    )
    return json_path, md_path


def upsert_index(entry: dict[str, Any]) -> None:
    index = load_json(INDEX_PATH, [])
    if not isinstance(index, list):
        index = []
    key = str(entry.get("post_id") or entry.get("slug") or entry.get("title"))
    updated = False
    for idx, item in enumerate(index):
        item_key = str(item.get("post_id") or item.get("slug") or item.get("title"))
        if item_key == key:
            index[idx] = {**item, **entry}
            updated = True
            break
    if not updated:
        index.append(entry)
    save_json(INDEX_PATH, index)


def record(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    payload = load_json(payload_path, {})
    try:
        response = json.loads(args.response_json)
    except json.JSONDecodeError as exc:
        print(f"Not recording: publish response was not JSON ({exc}).", file=sys.stderr)
        return 0

    if not isinstance(response, dict):
        print("Not recording: publish response was not a JSON object.", file=sys.stderr)
        return 0

    if not response.get("success"):
        print("Not recording: publish response was not successful.", file=sys.stderr)
        return 0
    entry = entry_from_payload(payload, response, args.base_url)
    json_path, md_path = archive_post(payload, response, entry)
    upsert_index(entry)
    print(f"Indexed local content: {entry.get('title')}", file=sys.stderr)
    print(f"Archive JSON: {json_path}", file=sys.stderr)
    print(f"Archive Markdown: {md_path}", file=sys.stderr)
    return 0


def tokenize(value: Any) -> set[str]:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    text = str(value or "").lower()
    words = re.findall(r"[\w\u0600-\u06FF]+", text)
    stop = {"از", "به", "در", "و", "یا", "که", "برای", "با", "را", "های", "این", "آن"}
    return {word for word in words if len(word) > 1 and word not in stop}


def target_score(target: dict[str, Any], query_tokens: set[str]) -> int:
    haystack = set()
    haystack |= tokenize(target.get("title"))
    haystack |= tokenize(target.get("anchor_keywords"))
    haystack |= tokenize(target.get("focus_keyword"))
    haystack |= tokenize(target.get("tags"))
    overlap = len(haystack & query_tokens)
    return overlap * 10 + int(target.get("priority", 0))


def suggest(args: argparse.Namespace) -> int:
    query = " ".join(part for part in [args.topic, args.keyword] if part)
    query_tokens = tokenize(query)
    targets = load_json(TARGETS_PATH, [])
    index = load_json(INDEX_PATH, [])
    candidates: list[dict[str, Any]] = []

    for target in targets if isinstance(targets, list) else []:
        item = {**target, "source": "landing"}
        item["_score"] = target_score(item, query_tokens)
        candidates.append(item)
    for entry in index if isinstance(index, list) else []:
        item = {
            "type": entry.get("type", "post"),
            "title": entry.get("title", ""),
            "url": entry.get("url", ""),
            "anchor_keywords": [entry.get("focus_keyword", ""), *(entry.get("tags") or [])],
            "priority": 5,
            "notes": entry.get("excerpt", ""),
            "source": "content-index",
        }
        item["_score"] = target_score(item, query_tokens)
        candidates.append(item)

    candidates = [item for item in candidates if item.get("_score", 0) > 0]
    candidates.sort(key=lambda item: item.get("_score", 0), reverse=True)
    candidates = candidates[: args.limit]

    if args.json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return 0

    if not candidates:
        print("No internal link suggestions found.")
        return 0

    print("| Score | Source | Title | Suggested anchors | URL |")
    print("|---:|---|---|---|---|")
    for item in candidates:
        anchors = "، ".join(str(anchor) for anchor in item.get("anchor_keywords", [])[:5] if anchor)
        print(f"| {item['_score']} | {item.get('source')} | {item.get('title')} | {anchors} | {item.get('url')} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="Archive a successful publish response.")
    record_parser.add_argument("--payload", required=True)
    record_parser.add_argument("--response-json", required=True)
    record_parser.add_argument("--base-url", required=True)
    record_parser.set_defaults(func=record)

    suggest_parser = subparsers.add_parser("suggest", help="Suggest internal link targets.")
    suggest_parser.add_argument("--topic", default="")
    suggest_parser.add_argument("--keyword", default="")
    suggest_parser.add_argument("--limit", type=int, default=8)
    suggest_parser.add_argument("--json", action="store_true")
    suggest_parser.set_defaults(func=suggest)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
