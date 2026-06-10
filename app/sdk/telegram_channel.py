import html
import os
import re
import sqlite3
import time
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests


CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{3,64}$")
QUARK_LINK_RE = re.compile(
    r"(?:(?:https?://)?pan\.quark\.cn/s/[A-Za-z0-9]+(?:[^\s<>'\"]*)?)",
    re.IGNORECASE,
)


def normalize_channel(value: str) -> str:
    if not value:
        return ""
    raw = str(value).strip()
    if not raw or any(ch.isspace() for ch in raw):
        return ""
    raw = raw.lstrip("@")
    parsed = urlparse(raw if "://" in raw else f"https://t.me/{raw}")
    host = (parsed.netloc or "").lower()
    if host and host not in {"t.me", "telegram.me"}:
        return ""
    parts = [part for part in (parsed.path or "").split("/") if part]
    if parts and parts[0].lower() == "s":
        parts = parts[1:]
    channel = parts[0] if parts else raw
    channel = channel.strip().lstrip("@")
    if not CHANNEL_RE.match(channel):
        return ""
    return channel


def normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "enabled", "on"}


def normalize_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[\n,，]+", value) if item.strip()]
    return []


def extract_quark_links(text: str) -> List[str]:
    if not text:
        return []
    links = []
    seen = set()
    for match in QUARK_LINK_RE.finditer(str(text)):
        url = match.group(0).strip().rstrip(").,，。；;、]")
        if not url.startswith("http"):
            url = f"https://{url}"
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def normalize_share_id(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"/s/([^?/#\s]+)", str(url))
    return match.group(1) if match else str(url).split("?", 1)[0]


def build_taskname(content: str, fallback: str = "") -> str:
    text = re.sub(r"https?://\S+", " ", content or "")
    text = re.sub(r"\s+", " ", text).strip(" -_|:：,，")
    text = re.sub(r"(?:\s*(?:夸克|链接|网盘|点击查看|查看链接|保存链接))+$", "", text).strip(" -_|:：,，")
    if not text:
        return fallback
    return text[:160]


class TMeMessageParser(HTMLParser):
    def __init__(self, channel: str):
        super().__init__(convert_charrefs=True)
        self.channel = channel
        self.current: Optional[Dict[str, Any]] = None
        self.div_depth = 0
        self.in_text_depth = 0
        self.messages: List[Dict[str, Any]] = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs or [])
        classes = attr.get("class", "")
        if tag == "div" and attr.get("data-post") and self.current is None:
            data_post = attr.get("data-post") or ""
            post_channel, _, message_id = data_post.partition("/")
            self.current = {
                "channel": post_channel or self.channel,
                "message_id": message_id,
                "message_url": f"https://t.me/{post_channel or self.channel}/{message_id}" if message_id else "",
                "content_parts": [],
                "links": [],
                "publish_date": "",
            }
            self.div_depth = 1
            return

        if self.current is None:
            return

        if tag == "div":
            self.div_depth += 1
            if "tgme_widget_message_text" in classes or "js-message_text" in classes:
                self.in_text_depth += 1
        elif self.in_text_depth > 0 and tag == "br":
            self.current["content_parts"].append("\n")
        elif tag == "a":
            self.current["links"].extend(extract_quark_links(attr.get("href", "")))
        elif tag == "time" and attr.get("datetime"):
            self.current["publish_date"] = attr.get("datetime") or ""

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if tag == "div":
            if self.in_text_depth > 0:
                self.in_text_depth -= 1
            self.div_depth -= 1
            if self.div_depth <= 0:
                self.messages.append(self.current)
                self.current = None
                self.div_depth = 0
                self.in_text_depth = 0

    def handle_data(self, data):
        if self.current is not None and self.in_text_depth > 0 and data:
            self.current["content_parts"].append(data)


def parse_tme_messages(page_html: str, channel: str) -> List[Dict[str, Any]]:
    parser = TMeMessageParser(channel)
    parser.feed(page_html or "")
    candidates = []
    for message in parser.messages:
        content = html.unescape("".join(message.get("content_parts") or []))
        links = extract_quark_links(content) + list(message.get("links") or [])
        seen = set()
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            msg_channel = message.get("channel") or channel
            candidates.append({
                "channel": msg_channel,
                "message_id": message.get("message_id", ""),
                "message_url": message.get("message_url", ""),
                "taskname": build_taskname(content, fallback=f"{msg_channel}/{message.get('message_id', '')}"),
                "content": content.strip(),
                "shareurl": link,
                "publish_date": message.get("publish_date", ""),
                "datetime": message.get("publish_date", ""),
                "tags": ["quark", "telegram"],
                "source": "Telegram",
                "telegram_source": f"tg:{msg_channel}",
            })
    return candidates


class TelegramChannelCache:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_path: str = "config/data.db",
        session: Optional[requests.Session] = None,
        logger=None,
    ):
        self.config = config or {}
        self.db_path = db_path
        self.session = session or requests.Session()
        self.logger = logger or (lambda message: None)
        self.enabled = normalize_bool(self.config.get("enabled", True), True)
        self.timeout = normalize_int(self.config.get("timeout_seconds", 8), 8, 2, 60)
        self.cache_ttl = normalize_int(self.config.get("cache_ttl_seconds", 900), 900, 60, 86400)
        self.read_limit = normalize_int(self.config.get("read_limit", 99), 99, 1, 500)
        self.deep_limit = normalize_int(self.config.get("deep_limit", 600), 600, 1, 5000)
        self.search_limit = normalize_int(self.config.get("search_limit", 80), 80, 1, 500)
        self.verify_limit = normalize_int(self.config.get("verify_limit", 5), 5, 1, 50)
        self.channels = [normalize_channel(item) for item in normalize_list(self.config.get("channels", []))]
        self.channels = [item for item in self.channels if item]
        self.keywords = normalize_list(self.config.get("keywords", []))
        self.proxy = str(self.config.get("proxy", "") or "").strip()
        self._init_db()

    def _init_db(self):
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    share_id TEXT UNIQUE,
                    shareurl TEXT NOT NULL,
                    taskname TEXT,
                    content TEXT,
                    channel TEXT,
                    message_id TEXT,
                    message_url TEXT,
                    publish_date TEXT,
                    source TEXT,
                    telegram_source TEXT,
                    indexed_at INTEGER NOT NULL
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(telegram_resources)").fetchall()}
            if "telegram_source" not in columns:
                conn.execute("ALTER TABLE telegram_resources ADD COLUMN telegram_source TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_telegram_resources_text ON telegram_resources(taskname, content)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_telegram_resources_time ON telegram_resources(indexed_at)")
            conn.commit()
        finally:
            conn.close()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=5.0)

    def save_candidates(self, candidates: Iterable[Dict[str, Any]]) -> int:
        now = int(time.time())
        rows = []
        for item in candidates or []:
            shareurl = item.get("shareurl") or ""
            share_id = normalize_share_id(shareurl)
            if not share_id:
                continue
            rows.append((
                share_id,
                shareurl,
                item.get("taskname", ""),
                item.get("content", ""),
                item.get("channel", ""),
                item.get("message_id", ""),
                item.get("message_url", ""),
                item.get("publish_date") or item.get("datetime") or "",
                item.get("source", "Telegram"),
                item.get("telegram_source", f"tg:{item.get('channel', '')}"),
                now,
            ))
        if not rows:
            return 0
        conn = self._connect()
        try:
            conn.executemany(
                """
                INSERT INTO telegram_resources (
                    share_id, shareurl, taskname, content, channel, message_id,
                    message_url, publish_date, source, telegram_source, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(share_id) DO UPDATE SET
                    shareurl=excluded.shareurl,
                    taskname=excluded.taskname,
                    content=excluded.content,
                    channel=excluded.channel,
                    message_id=excluded.message_id,
                    message_url=excluded.message_url,
                    publish_date=excluded.publish_date,
                    source=excluded.source,
                    telegram_source=excluded.telegram_source,
                    indexed_at=excluded.indexed_at
                """,
                rows,
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def search(self, keyword: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        limit = normalize_int(limit or self.search_limit, self.search_limit, 1, 500)
        tokens = [token for token in re.split(r"[\s._\-]+", str(keyword or "").strip()) if token]
        if not tokens and keyword:
            tokens = [str(keyword).strip()]
        where = []
        params = []
        for token in tokens:
            where.append("(taskname LIKE ? OR content LIKE ?)")
            like = f"%{token}%"
            params.extend([like, like])
        where_sql = "WHERE " + " AND ".join(where) if where else ""
        conn = self._connect()
        try:
            cursor = conn.execute(
                f"""
                SELECT shareurl, taskname, content, channel, message_id, message_url,
                       publish_date, source, telegram_source
                FROM telegram_resources
                {where_sql}
                ORDER BY COALESCE(publish_date, '') DESC, indexed_at DESC
                LIMIT ?
                """,
                params + [limit],
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
        results = []
        for row in rows:
            results.append({
                "shareurl": row[0],
                "taskname": row[1] or "",
                "content": row[2] or "",
                "channel": row[3] or "",
                "message_id": row[4] or "",
                "message_url": row[5] or "",
                "publish_date": row[6] or "",
                "datetime": row[6] or "",
                "source": row[7] or "Telegram",
                "telegram_source": row[8] or "",
                "tags": ["quark", "telegram"],
            })
        return results

    def _request_kwargs(self):
        kwargs = {"timeout": self.timeout}
        if self.proxy:
            kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        return kwargs

    def fetch_channel_page(self, channel: str, before: str = "") -> str:
        url = f"https://t.me/s/{channel}"
        params = {"before": before} if before else None
        response = self.session.get(
            url,
            params=params,
            headers={"User-Agent": "QASX-TelegramChannelCache/1.0"},
            **self._request_kwargs(),
        )
        response.raise_for_status()
        return response.text

    def _next_before(self, page_html: str) -> str:
        match = re.search(r'data-before="(\d+)"', page_html or "")
        if match:
            return match.group(1)
        match = re.search(r"/s/[A-Za-z0-9_]+\?before=(\d+)", page_html or "")
        return match.group(1) if match else ""

    def _passes_keywords(self, candidate: Dict[str, Any]) -> bool:
        if not self.keywords:
            return True
        text = f"{candidate.get('taskname', '')} {candidate.get('content', '')}".lower()
        return any(keyword.lower() in text for keyword in self.keywords)

    def index_channels(self, deep: bool = False, max_messages: Optional[int] = None) -> Dict[str, Any]:
        if not self.enabled:
            return {"success": False, "message": "Telegram search disabled", "indexed": 0, "channels": 0}
        if not self.channels:
            return {"success": False, "message": "No Telegram channels configured", "indexed": 0, "channels": 0}
        target_messages = max_messages or (self.deep_limit if deep else self.read_limit)
        indexed = 0
        fetched_channels = 0
        errors = []
        for channel in self.channels:
            fetched_channels += 1
            before = ""
            visited = set()
            parsed_messages = 0
            while parsed_messages < target_messages:
                try:
                    page = self.fetch_channel_page(channel, before=before)
                except Exception as exc:
                    errors.append(f"{channel}: {exc}")
                    break
                candidates = [item for item in parse_tme_messages(page, channel) if self._passes_keywords(item)]
                parsed_messages += max(len(candidates), 1)
                indexed += self.save_candidates(candidates)
                next_before = self._next_before(page)
                if not next_before or next_before in visited:
                    break
                visited.add(next_before)
                before = next_before
        return {
            "success": indexed > 0 or not errors,
            "indexed": indexed,
            "channels": fetched_channels,
            "message": "; ".join(errors) if errors else "ok",
        }

    def last_indexed_at(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT MAX(indexed_at) FROM telegram_resources").fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            conn.close()

    def ensure_fresh(self):
        if not self.enabled or not self.channels:
            return
        if int(time.time()) - self.last_indexed_at() < self.cache_ttl:
            return
        self.index_channels(deep=False)

    def stats(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM telegram_resources").fetchone()[0]
            last = conn.execute("SELECT MAX(indexed_at) FROM telegram_resources").fetchone()[0] or 0
            return {"count": count, "last_indexed_at": int(last)}
        finally:
            conn.close()
