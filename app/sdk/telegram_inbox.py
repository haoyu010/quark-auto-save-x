import copy
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional

import requests

from .telegram_channel import extract_quark_links, normalize_bool, normalize_int, normalize_share_id


VIDEO_EXT_RE = re.compile(r"\.(mkv|mp4|avi|mov|ts|m2ts|wmv|flv|webm|rmvb)$", re.I)
EPISODE_RE = re.compile(
    r"(?:[Ss]\d{1,2}[Ee]\d{1,4}|(?<![A-Za-z0-9])(?:EP|E)[\s._-]*\d{1,4}(?![A-Za-z0-9])|(?:第\s*)?[0-9一二三四五六七八九十零〇两]+\s*[集话話期])",
    re.I,
)
SEASON_RE = re.compile(
    r"(?:[Ss](\d{1,2})(?!\d)|Season\s*(\d{1,2})|第\s*([0-9一二三四五六七八九十零〇两]+)\s*季|(\d{1,2})\s*季)",
    re.I,
)
RELEASE_BRACKET_TAG_RE = re.compile(
    r"[\[【(（]\s*[^]】)）]*(?:原盘|字幕|中字|国语|粤语|国粤|双语|多音轨|内封|外挂|高清|蓝光|修复|合集|完结|REMUX|BluRay|WEB|4K|1080|2160|720)[^]】)）]*[\]】)）]",
    re.I,
)
RELEASE_METADATA_START_RE = re.compile(
    r"(?:"
    r"[Ss]\d{1,2}[Ee]\d{1,4}|Season\s*\d{1,2}|第\s*[0-9一二三四五六七八九十零〇两]+\s*季|(?<![A-Za-z0-9])(?:EP|E)[\s._-]*\d{1,4}(?![A-Za-z0-9])|(?:第\s*)?[0-9一二三四五六七八九十零〇两]+\s*[集话話期]|"
    r"(?:\s+年番|年番(?=\s|[\(（【\[]|[Ss]\d|$))|"
    r"\b(?:4K|8K|2160p|1080p|720p|REMUX|WEB[- ]?DL|BluRay|BDRip|HDRip|HDTV|H\.?264|H\.?265|x265|x264|AAC|DTS|DDP?\d?\.?\d?|Atmos|HDR|DV|HQ|HiveWeb|(?:8|10|12)[- ]?bit|\d{2,3}\s*FPS)\b|"
    r"\d{2,3}\s*帧|原盘|字幕|中字|外挂字幕|内封字幕|国语|粤语|国粤|双语|多音轨|简繁|高码率|高码|高帧率"
    r")",
    re.I,
)

MEDIA_TASK_DEFAULTS = {
    "telegram_inbox_media_root": "",
    "movie_save_path": "电影目录前缀/片名 (年份)",
    "tv_save_path": "剧集目录前缀/剧名/Season 季数",
    "anime_save_path": "动画目录前缀/剧名/Season 季数",
    "variety_save_path": "综艺目录前缀/剧名/Season 季数",
    "documentary_save_path": "纪录片目录前缀/剧名/Season 季数",
    "movie_naming_pattern": "^(.*)\\.([^.]+)",
    "movie_naming_replace": "片名 (年份).\\2",
    "tv_naming_rule": "剧名 - S季数E[]",
    "tv_ignore_extension": True,
}

DEFAULT_LIBRARY_CATEGORY_RULES = {
    "movie": [
        ("动画电影", {"genre_ids": "16"}),
        ("华语电影", {"original_language": "zh,cn,bo,za"}),
        ("日韩电影", {"original_language": "ja,ko"}),
        ("欧美电影", {"original_language": "en,fr,de,es,it,pt,nl,ru"}),
        ("其他电影", {}),
    ],
    "tv": [
        ("国漫", {"genre_ids": "16", "origin_country": "CN,TW,HK"}),
        ("日番", {"genre_ids": "16", "origin_country": "JP"}),
        ("纪录片", {"genre_ids": "99"}),
        ("儿童", {"genre_ids": "10762"}),
        ("综艺", {"genre_ids": "10764,10767"}),
        ("国产剧", {"origin_country": "CN,TW,HK"}),
        ("欧美剧", {"origin_country": "US,FR,GB,DE,ES,IT,NL,PT,RU,UK"}),
        ("日韩剧", {"origin_country": "JP,KP,KR,TH,IN,SG"}),
        ("未分类", {}),
    ],
}


@dataclass
class TelegramAutoCreateResult:
    status: str
    message: str
    task: Optional[Dict[str, Any]] = None
    task_index: Optional[int] = None
    shareurl: str = ""
    run_started: bool = False


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def extract_title_seed(text: str) -> str:
    """Return the useful title fragment from a Telegram message."""
    content = str(text or "")
    for link in extract_quark_links(content):
        content = content.replace(link, " ")
        content = content.replace(link.replace("https://", ""), " ")
    content = re.sub(r"https?://\S+", " ", content)
    lines = [_compact_text(line) for line in content.splitlines()]
    lines = [line.strip(" -_|:：，,。;；") for line in lines if line.strip(" -_|:：，,。;；")]
    if not lines:
        return ""
    seed = lines[0]
    seed = re.sub(r"^(资源|片名|剧名|名称|标题)[:：]\s*", "", seed).strip()
    return seed[:160]


def _message_text(message: Dict[str, Any]) -> str:
    return str(message.get("text") or message.get("caption") or "")


def is_authorized_message(message: Dict[str, Any], allowed_user_id: Any) -> bool:
    allowed = str(allowed_user_id or "").strip()
    if not allowed:
        return False
    chat_id = str(((message.get("chat") or {}).get("id")) or "").strip()
    from_id = str(((message.get("from") or {}).get("id")) or "").strip()
    return allowed in {chat_id, from_id}


def _chinese_number_to_int(value: str) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if raw == "十":
        return 10
    if "十" in raw:
        left, _, right = raw.partition("十")
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones
    return digits.get(raw)


def _extract_season_number(*texts: str) -> Optional[int]:
    for text in texts:
        for match in SEASON_RE.finditer(str(text or "")):
            for group in match.groups():
                if not group:
                    continue
                value = _chinese_number_to_int(group)
                if value and value > 0:
                    return value
    return None


def _extract_year(*texts: str) -> str:
    for text in texts:
        value = str(text or "")
        for match in re.finditer(r"(19\d{2}|20\d{2})", value):
            if re.match(r"\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", value[match.end():]):
                continue
            return match.group(1)
    return ""


def _strip_extension(name: str) -> str:
    return re.sub(r"\.(mkv|mp4|avi|mov|ts|m2ts|wmv|flv|webm|rmvb|srt|ass|ssa|zip|rar|7z)$", "", str(name or ""), flags=re.I).strip()


def _drop_release_metadata_tail(text: str) -> str:
    for match in RELEASE_METADATA_START_RE.finditer(text or ""):
        head = str(text or "")[: match.start()].strip(" -_|:：，,。.【[(")
        if head:
            return head
    return text


def _clean_media_title(value: str) -> str:
    text = _strip_extension(value)
    text = re.sub(r"[\._]+", " ", text)
    text = re.sub(r"^(?:资源|片名|剧名|名称|标题)\s*[:：]\s*", " ", text)
    text = RELEASE_BRACKET_TAG_RE.sub(" ", text)
    text = re.sub(r"^(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*", " ", text)
    text = re.sub(r"^(.+?)[\(（【\[]\s*(?:19|20)\d{2}\s*[\)）】\]].*$", r"\1", text)
    text = re.sub(r"[\(（【\[]\s*(?:19|20)\d{2}\s*[\)）】\]]", " ", text)
    text = _drop_release_metadata_tail(text)
    text = re.sub(r"(?:首更|更至|更新至|更新|已更|连载至|全)\s*(?:第\s*)?(?:EP|E)?[\s._-]*\d+\s*(?:集|话|話|期|回)?", " ", text, flags=re.I)
    text = re.sub(r"\[[^\]]+\]|\([^)]*(?:1080|2160|720|字幕|国语|中字|GB|MP4|MKV)[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"\b(4K|8K|2160p|1080p|720p|WEB[- ]?DL|BluRay|H\.?264|H\.?265|x265|x264|AAC|DDP?\d?\.?\d?|HDR|DV|HQ|(?:8|10|12)[- ]?bit|\d{2,3}\s*FPS)\b|\d{2,3}\s*帧|高码率|高码|高帧率", " ", text, flags=re.I)
    text = EPISODE_RE.sub(" ", text)
    text = SEASON_RE.sub(" ", text)
    text = re.sub(r"(19\d{2}|20\d{2})", " ", text)
    text = re.sub(r"^(电影|电视剧|剧集|动漫|动画|国漫|番剧)\s+", " ", text)
    text = re.sub(r"\s+(电影|电视剧|剧集|动漫|动画|国漫|番剧)$", " ", text)
    text = re.sub(r"[\(（【\[]\s*[\)）】\]]", " ", text)
    text = re.sub(r"\b(?:首更|更至|更新至|更新|已更|连载至)\b", " ", text, flags=re.I)
    return _compact_text(text).strip(" -_|:：，,。")


def _flatten_share_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in files or [] if isinstance(item, dict)]


def _share_file_names(files: List[Dict[str, Any]]) -> List[str]:
    return [str(item.get("file_name") or item.get("name") or "") for item in files or [] if item.get("file_name") or item.get("name")]


def _fallback_title_from_share(files: List[Dict[str, Any]]) -> str:
    names = _share_file_names(files)
    folder = next((name for item, name in zip(files, names) if item.get("dir") and name), "")
    if folder:
        return _clean_media_title(folder) or _strip_extension(folder)
    videos = [name for name in names if VIDEO_EXT_RE.search(name)]
    base = videos[0] if videos else (names[0] if names else "")
    return _clean_media_title(base) or _strip_extension(base)


def _looks_like_series(seed: str, files: List[Dict[str, Any]]) -> bool:
    names = " ".join(_share_file_names(files))
    if _extract_season_number(seed, names):
        return True
    if EPISODE_RE.search(seed or "") or EPISODE_RE.search(names):
        return True
    video_count = len([name for name in _share_file_names(files) if VIDEO_EXT_RE.search(name)])
    return video_count >= 3


def _is_animation(seed: str, files: List[Dict[str, Any]], config_data: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> bool:
    text = " ".join([seed] + _share_file_names(files))
    if re.search(r"(动漫|动画|国漫|番剧|追更动漫)", text):
        return True
    if "16" in _tmdb_genre_ids(details):
        return True
    for genre in (details or {}).get("genres") or []:
        name = str(genre.get("name") or "").lower()
        if genre.get("id") == 16 or "animation" in name or "动画" in name:
            return True
    return False


def _tmdb_genre_ids(*items: Optional[Dict[str, Any]]) -> set:
    ids = set()
    for item in items:
        if not item:
            continue
        for value in item.get("genre_ids") or []:
            ids.add(str(value))
        for genre in item.get("genres") or []:
            if isinstance(genre, dict) and genre.get("id") is not None:
                ids.add(str(genre.get("id")))
    return ids


def _tmdb_origin_countries(*items: Optional[Dict[str, Any]]) -> set:
    countries = set()
    for item in items:
        if not item:
            continue
        for value in item.get("origin_country") or []:
            if value:
                countries.add(str(value).upper())
    return countries


def _tmdb_production_countries(*items: Optional[Dict[str, Any]]) -> set:
    countries = set()
    for item in items:
        if not item:
            continue
        for value in item.get("production_countries") or []:
            if isinstance(value, dict):
                value = value.get("iso_3166_1")
            if value:
                countries.add(str(value).upper())
    return countries


def _tmdb_original_language(*items: Optional[Dict[str, Any]]) -> str:
    for item in items:
        value = str((item or {}).get("original_language") or "").strip().lower()
        if value:
            return value
    return ""


def _tmdb_release_year(media_type: str, *items: Optional[Dict[str, Any]]) -> int:
    key = "release_date" if media_type == "movie" else "first_air_date"
    for item in items:
        year = _year_from_date((item or {}).get(key))
        if year:
            return year
    return 0


def _rule_specificity(rule: Dict[str, str]) -> int:
    return sum(1 for key in ("genre_ids", "original_language", "origin_country", "production_countries", "release_year") if rule.get(key))


def _rule_values(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _match_rule_values(rule_values: str, actual_values: List[str]) -> bool:
    actual = {str(value).strip().upper() for value in actual_values if str(value).strip()}
    matched_positive = False
    for part in _rule_values(rule_values):
        if part.startswith("!"):
            if part[1:].upper() in actual:
                return False
            continue
        if part.upper() in actual:
            matched_positive = True
    return matched_positive


def _match_rule_value(rule_values: str, actual_value: str) -> bool:
    actual = str(actual_value or "").strip().lower()
    return any(part.lower() == actual for part in _rule_values(rule_values))


def _match_year_rule(rule_value: str, actual_year: int) -> bool:
    if not actual_year:
        return False
    value = str(rule_value or "").strip()
    if "-" in value:
        start, _, end = value.partition("-")
        try:
            return int(start) <= actual_year <= int(end)
        except Exception:
            return False
    try:
        return actual_year == int(value)
    except Exception:
        return False


def _library_rule_matches(media_type: str, rule: Dict[str, str], tmdb_data: Optional[Dict[str, Any]]) -> bool:
    if rule.get("genre_ids") and not _match_rule_values(rule["genre_ids"], list(_tmdb_genre_ids(tmdb_data))):
        return False
    if rule.get("original_language") and not _match_rule_value(rule["original_language"], _tmdb_original_language(tmdb_data)):
        return False
    if rule.get("origin_country") and not _match_rule_values(rule["origin_country"], list(_tmdb_origin_countries(tmdb_data))):
        return False
    if rule.get("production_countries") and not _match_rule_values(rule["production_countries"], list(_tmdb_production_countries(tmdb_data))):
        return False
    if rule.get("release_year") and not _match_year_rule(rule["release_year"], _tmdb_release_year(media_type, tmdb_data)):
        return False
    return True


def _classify_library_category(media_type: str, tmdb_data: Optional[Dict[str, Any]]) -> str:
    rules = DEFAULT_LIBRARY_CATEGORY_RULES.get(media_type)
    if not rules:
        return "未分类"
    ordered = sorted(rules, key=lambda item: -_rule_specificity(item[1]))
    fallback = ""
    for name, rule in ordered:
        if _rule_specificity(rule) == 0:
            if not fallback:
                fallback = name
            continue
        if _library_rule_matches(media_type, rule, tmdb_data):
            return name
    return fallback or "未分类"


def _has_library_classification_data(tmdb_data: Optional[Dict[str, Any]]) -> bool:
    return bool(
        _tmdb_genre_ids(tmdb_data)
        or _tmdb_origin_countries(tmdb_data)
        or _tmdb_original_language(tmdb_data)
        or _tmdb_production_countries(tmdb_data)
    )


def _classify_movie_library_category(tmdb_data: Optional[Dict[str, Any]]) -> str:
    if tmdb_data is None:
        return ""
    return _classify_library_category("movie", tmdb_data)


def _classify_tv_library_category(seed: str, files: List[Dict[str, Any]], tmdb_data: Optional[Dict[str, Any]], content_type: str) -> str:
    if tmdb_data is None:
        return ""
    return _classify_library_category("tv", tmdb_data)


def _select_latest_season(details: Optional[Dict[str, Any]]) -> Optional[int]:
    if not details:
        return None
    last = (details.get("last_episode_to_air") or {}).get("season_number")
    try:
        if int(last) > 0:
            return int(last)
    except Exception:
        pass
    seasons = []
    for season in details.get("seasons") or []:
        try:
            number = int(season.get("season_number") or 0)
        except Exception:
            number = 0
        if number > 0:
            seasons.append(number)
    if seasons:
        return max(seasons)
    try:
        number = int(details.get("number_of_seasons") or 0)
        return number if number > 0 else None
    except Exception:
        return None


def _task_settings(config_data: Dict[str, Any]) -> Dict[str, Any]:
    settings = dict(MEDIA_TASK_DEFAULTS)
    if isinstance((config_data or {}).get("task_settings"), dict):
        settings.update((config_data or {}).get("task_settings") or {})
    return settings


def _yesterday_date_string() -> str:
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))


def _task_content_type(task: Dict[str, Any]) -> str:
    if not isinstance(task, dict):
        return ""
    cal = task.get("calendar_info") or {}
    extracted = cal.get("extracted") or {}
    return str(task.get("content_type") or extracted.get("content_type") or "").strip().lower()


def mark_movie_task_completed(task: Dict[str, Any]) -> bool:
    """Make movie tasks one-shot: no scheduled reruns and no invalid-link replacement."""
    if _task_content_type(task) != "movie" and task.get("movie_once") is not True:
        return False
    before = {
        "runweek": task.get("runweek"),
        "enddate": task.get("enddate"),
        "auto_replace_invalid_shareurl": task.get("auto_replace_invalid_shareurl"),
        "movie_once": task.get("movie_once"),
        "skip_calendar_refresh": task.get("skip_calendar_refresh"),
    }
    task["runweek"] = []
    task["enddate"] = str(task.get("enddate") or _yesterday_date_string())
    task["auto_replace_invalid_shareurl"] = "disabled"
    task["movie_once"] = True
    task["skip_calendar_refresh"] = True
    after = {
        "runweek": task.get("runweek"),
        "enddate": task.get("enddate"),
        "auto_replace_invalid_shareurl": task.get("auto_replace_invalid_shareurl"),
        "movie_once": task.get("movie_once"),
        "skip_calendar_refresh": task.get("skip_calendar_refresh"),
    }
    return before != after


def mark_movie_tasks_completed(config_data: Optional[Dict[str, Any]] = None) -> int:
    if not isinstance(config_data, dict):
        return 0
    changed = 0
    for task in config_data.get("tasklist", []) or []:
        if isinstance(task, dict) and mark_movie_task_completed(task):
            changed += 1
    return changed


def _normalize_media_save_path(path: str) -> str:
    return re.sub(r"/{2,}", "/", str(path or "").replace("\\", "/")).strip().strip("/")


def _telegram_inbox_root_save_path(settings: Dict[str, Any], content_type: str, title: str, year: str = "", season: int = 1, library_category: str = "") -> str:
    root = _normalize_media_save_path(str((settings or {}).get("telegram_inbox_media_root") or ""))
    if not root:
        return ""

    category = {
        "movie": "电影",
        "tv": "电视剧",
        "anime": "电视剧",
        "variety": "综艺",
        "documentary": "纪录片",
    }.get(content_type, "电影")

    if content_type == "movie":
        folder = f"{title} ({year})" if year else title
        if library_category:
            return _normalize_media_save_path(f"{root}/电影/{library_category}/{folder}")
        return _normalize_media_save_path(f"{root}/{category}/{folder}")

    if content_type in {"tv", "anime"} and library_category:
        return _normalize_media_save_path(f"{root}/电视剧/{library_category}/{title}/Season {int(season or 1):02d}")

    return _normalize_media_save_path(f"{root}/{category}/{title}/Season {int(season or 1):02d}")


def _template_for_type(content_type: str, settings: Dict[str, Any]) -> str:
    key = {
        "movie": "movie_save_path",
        "tv": "tv_save_path",
        "anime": "anime_save_path",
        "variety": "variety_save_path",
        "documentary": "documentary_save_path",
    }.get(content_type, "movie_save_path")
    return str(settings.get(key) or MEDIA_TASK_DEFAULTS[key])


def _movie_save_path(template: str, title: str, year: str) -> str:
    path = str(template or MEDIA_TASK_DEFAULTS["movie_save_path"]).replace("片名", title)
    if year:
        path = path.replace("年份", year)
    else:
        path = re.sub(r"\s*\(年份\)", "", path)
    return _normalize_media_save_path(path)


def _tv_save_path(template: str, title: str, year: str, season: int) -> str:
    path = str(template or MEDIA_TASK_DEFAULTS["tv_save_path"]).replace("剧名", title).replace("季数", f"{season:02d}")
    if year and season == 1:
        path = path.replace("年份", year)
    else:
        path = re.sub(r"\s*\(年份\)/", "/", path)
        path = re.sub(r"\s*\(年份\)", "", path)
    return _normalize_media_save_path(path)


def _tv_naming_rule(template: str, title: str, season: int) -> str:
    return str(template or MEDIA_TASK_DEFAULTS["tv_naming_rule"]).replace("剧名", title).replace("季数", f"{season:02d}")


def _movie_naming_replace(template: str, title: str, year: str) -> str:
    value = str(template or "").replace("片名", title)
    if year:
        value = value.replace("年份", year)
    else:
        value = re.sub(r"\s*\(年份\)", "", value)
    return value


def _remove_season_from_title(seed: str) -> str:
    return _compact_text(SEASON_RE.sub(" ", seed or "")).strip(" -_|:：，,。")


def _normalize_tv_title(title: str, season: int = 0) -> str:
    text = str(title or "").strip()
    if season > 0:
        base = _remove_season_from_title(text)
        if base:
            return base
    return text


def _tmdb_year(result: Optional[Dict[str, Any]], media_type: str) -> str:
    if not result:
        return ""
    key = "release_date" if media_type == "movie" else "first_air_date"
    return str(result.get(key) or "")[:4]


def _safe_tmdb_call(func: Callable, *args):
    try:
        return func(*args)
    except Exception:
        return None


def _year_from_date(value: Any) -> int:
    text = str(value or "")
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return 0


def _confidence_score(query: str, title: str, original_title: str = "", query_year: Any = "", result_year: int = 0, query_season: int = 0) -> float:
    query_lower = str(query or "").strip().lower()
    title_lower = str(title or "").strip().lower()
    original_lower = str(original_title or "").strip().lower()
    if not query_lower or not title_lower:
        return 0.0

    if query_lower == title_lower or (original_lower and query_lower == original_lower):
        title_score = 100.0
    elif query_lower in title_lower or (original_lower and query_lower in original_lower):
        title_score = 80.0
    elif title_lower in query_lower or (original_lower and original_lower in query_lower):
        title_score = 70.0
    else:
        title_score = SequenceMatcher(None, query_lower, title_lower).ratio() * 100
        if original_lower and original_lower != title_lower:
            title_score = max(title_score, SequenceMatcher(None, query_lower, original_lower).ratio() * 100)

    try:
        query_year_int = int(query_year or 0)
    except Exception:
        query_year_int = 0
    year_score = 70.0
    if query_year_int > 0 and result_year > 0:
        diff = abs(result_year - query_year_int)
        if diff == 0:
            year_score = 100.0
        elif diff == 1:
            year_score = 80.0
        elif diff == 2:
            year_score = 50.0
        else:
            year_score = 20.0
    elif query_year_int == 0 and result_year > 0:
        year_score = 90.0
    elif query_year_int == 0 and result_year <= 0:
        year_score = 50.0

    season_score = 90.0 if query_season > 0 else 100.0
    return (title_score * 0.6 + year_score * 0.3 + season_score * 0.1) / 100.0


def _pick_best_tv_match(query: str, year: str, season: int, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if season > 0:
        season_best = None
        season_best_score = 0.0
        query_base = _normalize_tv_title(query, season).lower()
        for item in results or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("name") or "")
            original_title = str(item.get("original_name") or "")
            item_season = _extract_season_number(title, original_title) or 0
            if item_season != season:
                continue
            item_base = _normalize_tv_title(title or original_title, season).lower()
            if not item_base or not query_base:
                continue
            if not (query_base == item_base or query_base in item_base or item_base in query_base):
                continue
            score = _confidence_score(
                query_base,
                item_base,
                _normalize_tv_title(original_title, season),
                year,
                _year_from_date(item.get("first_air_date")),
                season,
            )
            if "16" in _tmdb_genre_ids(item):
                score += 0.08
            if score > season_best_score:
                season_best = item
                season_best_score = score
        if season_best is not None and season_best_score >= 0.6:
            return season_best

    best = None
    best_score = 0.0
    for item in results or []:
        if not isinstance(item, dict):
            continue
        score = _confidence_score(
            query,
            str(item.get("name") or ""),
            str(item.get("original_name") or ""),
            year,
            _year_from_date(item.get("first_air_date")),
            season,
        )
        if score > best_score:
            best = item
            best_score = score
    return best if best is not None and best_score >= 0.6 else None


def _pick_best_movie_match(query: str, year: str, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_score = 0.0
    for item in results or []:
        if not isinstance(item, dict):
            continue
        score = _confidence_score(
            query,
            str(item.get("title") or ""),
            str(item.get("original_title") or ""),
            year,
            _year_from_date(item.get("release_date")),
            0,
        )
        if score > best_score:
            best = item
            best_score = score
    return best if best is not None and best_score >= 0.6 else None


def _search_best_movie(tmdb_service: Any, query: str, year: str) -> Optional[Dict[str, Any]]:
    if not tmdb_service or not query:
        return None
    if hasattr(tmdb_service, "search_movie_all"):
        results = _safe_tmdb_call(tmdb_service.search_movie_all, query, year or None) or []
        best = _pick_best_movie_match(query, year, results)
        if best:
            return best
        if year:
            results = _safe_tmdb_call(tmdb_service.search_movie_all, query, None) or []
            best = _pick_best_movie_match(query, year, results)
            if best:
                return best
    return _safe_tmdb_call(tmdb_service.search_movie, query, year or None)


def _search_best_tv_show(tmdb_service: Any, query: str, year: str, season: int) -> Optional[Dict[str, Any]]:
    if not tmdb_service or not query:
        return None
    if hasattr(tmdb_service, "search_tv_show_all"):
        results = _safe_tmdb_call(tmdb_service.search_tv_show_all, query, year or None) or []
        best = _pick_best_tv_match(query, year, season, results)
        if best:
            return best
        if year:
            results = _safe_tmdb_call(tmdb_service.search_tv_show_all, query, None) or []
            best = _pick_best_tv_match(query, year, season, results)
            if best:
                return best
    return _safe_tmdb_call(tmdb_service.search_tv_show, query, year or None)


def build_media_task_from_share(
    shareurl: str,
    message_text: str,
    account: Any,
    config_data: Optional[Dict[str, Any]] = None,
    tmdb_service: Any = None,
) -> Dict[str, Any]:
    config_data = config_data or {}
    pwd_id, passcode, pdir_fid, _paths = account.extract_url(shareurl)
    if not pwd_id:
        raise ValueError("未识别到夸克分享ID")
    is_sharing, stoken = account.get_stoken(pwd_id, passcode)
    if not is_sharing:
        raise ValueError(str(stoken or "分享链接已失效"))
    share_detail = account.get_detail(pwd_id, stoken, pdir_fid, _fetch_share=1) or {}
    files = _flatten_share_files(share_detail.get("list") or [])
    if not files:
        raise ValueError("分享链接为空，无法创建任务")

    seed = extract_title_seed(message_text) or _fallback_title_from_share(files) or "Telegram资源"
    fallback_title = _fallback_title_from_share(files) or seed
    year_seed = _extract_year(seed, " ".join(_share_file_names(files)))
    series_like = _looks_like_series(seed, files)
    query = _clean_media_title(seed) or _clean_media_title(fallback_title) or seed

    movie_match = None
    tv_match = None
    details = None
    if tmdb_service and query:
        season_hint = _extract_season_number(seed, " ".join(_share_file_names(files))) or 0
        if series_like:
            tv_match = _search_best_tv_show(tmdb_service, query, year_seed, season_hint)
        else:
            movie_match = _search_best_movie(tmdb_service, query, year_seed)
            if not movie_match:
                tv_match = _search_best_tv_show(tmdb_service, query, year_seed, season_hint)

    if tv_match:
        details = _safe_tmdb_call(tmdb_service.get_tv_show_details, tv_match.get("id")) if tmdb_service and tv_match.get("id") else None
        year = _tmdb_year(details or tv_match, "tv") or year_seed
        season = _extract_season_number(seed, " ".join(_share_file_names(files))) or _select_latest_season(details) or 1
        title = _normalize_tv_title(str((details or {}).get("name") or tv_match.get("name") or query or fallback_title).strip(), season)
        classification_data = dict(tv_match or {})
        classification_data.update(details or {})
        content_type = "anime" if _is_animation(seed, files, config_data, classification_data) else "tv"
        library_category = (
            _classify_tv_library_category(seed, files, classification_data, content_type)
            if _has_library_classification_data(classification_data)
            else ""
        )
        settings = _task_settings(config_data)
        naming = _tv_naming_rule(str(settings.get("tv_naming_rule") or ""), title, season)
        savepath = _telegram_inbox_root_save_path(settings, content_type, title, year, season, library_category)
        task = {
            "taskname": title,
            "shareurl": shareurl,
            "savepath": savepath or _tv_save_path(_template_for_type(content_type, settings), title, year, season),
            "pattern": naming,
            "replace": "",
            "enddate": "",
            "runweek": [1, 2, 3, 4, 5, 6, 7],
            "filterwords": "",
            "startfid": "",
            "update_subdir": "",
            "addition": {},
            "use_sequence_naming": False,
            "sequence_naming": "",
            "use_episode_naming": True,
            "episode_naming": naming,
            "ignore_extension": bool(settings.get("tv_ignore_extension", True)),
            "content_type": content_type,
            "library_category": library_category,
            "matched_latest_season_number": season,
            "calendar_info": {
                "extracted": {"show_name": title, "year": year, "content_type": content_type, "library_category": library_category, "season_number": season},
                "match": {
                    "matched_show_name": title,
                    "matched_year": year,
                    "tmdb_id": tv_match.get("id"),
                    "latest_season_number": season,
                    "latest_season_fetch_url": f"/tv/{tv_match.get('id')}/season/{season}" if tv_match.get("id") else "",
                },
            },
        }
        return task

    if series_like:
        season = _extract_season_number(seed, " ".join(_share_file_names(files))) or 1
        title = _normalize_tv_title(query, season) or _clean_media_title(fallback_title) or seed
        content_type = "anime" if _is_animation(seed, files, config_data, None) else "tv"
        library_category = _classify_tv_library_category(seed, files, None, content_type)
        settings = _task_settings(config_data)
        naming = _tv_naming_rule(str(settings.get("tv_naming_rule") or ""), title, season)
        savepath = _telegram_inbox_root_save_path(settings, content_type, title, year_seed, season, library_category)
        return {
            "taskname": title,
            "shareurl": shareurl,
            "savepath": savepath or _tv_save_path(_template_for_type(content_type, settings), title, year_seed, season),
            "pattern": naming,
            "replace": "",
            "enddate": "",
            "runweek": [1, 2, 3, 4, 5, 6, 7],
            "filterwords": "",
            "startfid": "",
            "update_subdir": "",
            "addition": {},
            "use_sequence_naming": False,
            "sequence_naming": "",
            "use_episode_naming": True,
            "episode_naming": naming,
            "ignore_extension": bool(settings.get("tv_ignore_extension", True)),
            "content_type": content_type,
            "library_category": library_category,
            "matched_latest_season_number": season,
            "calendar_info": {
                "extracted": {"show_name": title, "year": year_seed, "content_type": content_type, "library_category": library_category, "season_number": season},
                "match": {
                    "matched_show_name": title,
                    "matched_year": year_seed,
                    "tmdb_id": None,
                    "latest_season_number": season,
                    "latest_season_fetch_url": "",
                },
            },
        }

    title = str((movie_match or {}).get("title") or _normalize_tv_title(query, 1) or fallback_title).strip()
    year = _tmdb_year(movie_match, "movie") or year_seed
    library_category = _classify_movie_library_category(movie_match)
    settings = _task_settings(config_data)
    pattern = str(settings.get("movie_naming_pattern") or "")
    replace_template = str(settings.get("movie_naming_replace") or "")
    savepath = _telegram_inbox_root_save_path(settings, "movie", title, year, 1, library_category)
    task = {
        "taskname": title,
        "shareurl": shareurl,
        "savepath": savepath or _movie_save_path(_template_for_type("movie", settings), title, year),
        "pattern": pattern,
        "replace": _movie_naming_replace(replace_template, title, year) if pattern and replace_template else "",
        "enddate": "",
        "runweek": [1, 2, 3, 4, 5, 6, 7],
        "filterwords": "",
        "startfid": "",
        "update_subdir": "",
        "addition": {},
        "use_sequence_naming": False,
        "sequence_naming": "",
        "use_episode_naming": False,
        "episode_naming": "",
        "ignore_extension": False,
        "content_type": "movie",
        "library_category": library_category,
        "calendar_info": {
            "extracted": {"show_name": title, "year": year, "content_type": "movie", "library_category": library_category},
            "match": {
                "matched_show_name": title,
                "matched_year": year,
                "tmdb_id": (movie_match or {}).get("id"),
                "latest_season_number": 1,
            },
        },
    }
    mark_movie_task_completed(task)
    return task


def repair_media_library_task(task: Dict[str, Any], config_data: Optional[Dict[str, Any]] = None, tmdb_service: Any = None) -> bool:
    """Repair a Telegram-created media-library path from its TMDB binding."""
    if not isinstance(task, dict) or not tmdb_service:
        return False
    config_data = config_data or {}
    settings = _task_settings(config_data)
    root = _normalize_media_save_path(str(settings.get("telegram_inbox_media_root") or ""))
    if not root:
        return False
    current_savepath = _normalize_media_save_path(str(task.get("savepath") or ""))
    if current_savepath and current_savepath != root and not current_savepath.startswith(root + "/"):
        return False

    cal = task.get("calendar_info") or {}
    match = cal.get("match") or {}
    extracted = cal.get("extracted") or {}
    existing_category = str(task.get("library_category") or extracted.get("library_category") or "").strip()
    if existing_category and f"/{existing_category}/" in f"/{current_savepath}/":
        return False
    tmdb_id = match.get("tmdb_id")
    try:
        tmdb_id = int(tmdb_id or 0)
    except Exception:
        tmdb_id = 0
    if tmdb_id <= 0:
        return False

    details = _safe_tmdb_call(tmdb_service.get_tv_show_details, tmdb_id) or {}
    classification_data = dict(details or {})
    title = str(
        details.get("name")
        or match.get("matched_show_name")
        or extracted.get("show_name")
        or task.get("taskname")
        or ""
    ).strip()
    if not title:
        return False
    year = _tmdb_year(classification_data, "tv") or str(match.get("matched_year") or extracted.get("year") or "")
    try:
        season = int(match.get("latest_season_number") or extracted.get("season_number") or task.get("matched_latest_season_number") or 1)
    except Exception:
        season = 1
    if season <= 0:
        season = 1
    title = _normalize_tv_title(title, season)

    content_type = "anime" if _is_animation(title, [], config_data, classification_data) else "tv"
    library_category = (
        _classify_tv_library_category(title, [], classification_data, content_type)
        if _has_library_classification_data(classification_data)
        else ""
    )
    if not library_category:
        return False

    naming = _tv_naming_rule(str(settings.get("tv_naming_rule") or ""), title, season)
    savepath = _telegram_inbox_root_save_path(settings, content_type, title, year, season, library_category)
    if not savepath:
        return False

    before = {
        "taskname": task.get("taskname"),
        "savepath": task.get("savepath"),
        "content_type": task.get("content_type"),
        "library_category": task.get("library_category"),
        "pattern": task.get("pattern"),
        "episode_naming": task.get("episode_naming"),
    }
    task["taskname"] = title
    task["savepath"] = savepath
    task["content_type"] = content_type
    task["library_category"] = library_category
    task["matched_latest_season_number"] = season
    task["pattern"] = naming
    task["episode_naming"] = naming
    task["use_episode_naming"] = True
    task["ignore_extension"] = bool(settings.get("tv_ignore_extension", True))

    cal.setdefault("extracted", {})
    cal["extracted"].update({
        "show_name": title,
        "year": year,
        "content_type": content_type,
        "library_category": library_category,
        "season_number": season,
    })
    cal.setdefault("match", {})
    cal["match"].update({
        "matched_show_name": title,
        "matched_year": year,
        "tmdb_id": tmdb_id,
        "latest_season_number": season,
        "latest_season_fetch_url": f"/tv/{tmdb_id}/season/{season}",
    })
    task["calendar_info"] = cal

    after = {
        "taskname": task.get("taskname"),
        "savepath": task.get("savepath"),
        "content_type": task.get("content_type"),
        "library_category": task.get("library_category"),
        "pattern": task.get("pattern"),
        "episode_naming": task.get("episode_naming"),
    }
    return before != after


def repair_media_library_tasks(config_data: Optional[Dict[str, Any]] = None, tmdb_service: Any = None) -> int:
    """Repair all existing Telegram media-library tasks in config."""
    if not isinstance(config_data, dict) or not tmdb_service:
        return 0
    repaired = 0
    for task in config_data.get("tasklist", []) or []:
        if isinstance(task, dict) and repair_media_library_task(task, config_data, tmdb_service):
            repaired += 1
    return repaired


def _message_chat_id(message: Dict[str, Any]) -> str:
    return str(((message.get("chat") or {}).get("id")) or "").strip()


class TelegramAutoCreateService:
    def __init__(
        self,
        config_data: Dict[str, Any],
        account_factory: Callable[[], Any],
        tmdb_factory: Optional[Callable[[], Any]] = None,
        save_config: Optional[Callable[[Dict[str, Any]], None]] = None,
        run_task: Optional[Callable[[Dict[str, Any], int], None]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.config_data = config_data
        self.account_factory = account_factory
        self.tmdb_factory = tmdb_factory or (lambda: None)
        self.save_config = save_config or (lambda data: None)
        self.run_task = run_task or (lambda task, index: None)
        self.logger = logger or (lambda message: None)

    def _is_duplicate(self, shareurl: str) -> bool:
        share_id = normalize_share_id(shareurl)
        for task in self.config_data.get("tasklist", []) or []:
            if normalize_share_id(task.get("shareurl", "")) == share_id:
                return True
        return False

    def handle_message(self, message: Dict[str, Any]) -> TelegramAutoCreateResult:
        push_config = self.config_data.get("push_config", {}) or {}
        if not is_authorized_message(message, push_config.get("TG_USER_ID")):
            self.logger(
                "Telegram 自动收链忽略非授权消息: "
                f"chat={((message.get('chat') or {}).get('id'))}, "
                f"from={((message.get('from') or {}).get('id'))}"
            )
            return TelegramAutoCreateResult("ignored", "非授权 Telegram 用户，已忽略")

        text = _message_text(message)
        links = extract_quark_links(text)
        if not links:
            self.logger("Telegram 自动收链收到消息，但未检测到夸克链接")
            return TelegramAutoCreateResult("no_link", "未检测到夸克链接")
        shareurl = links[0]
        if self._is_duplicate(shareurl):
            self.logger(f"Telegram 自动收链检测到重复链接: {shareurl}")
            return TelegramAutoCreateResult("duplicate", "这个夸克链接已经存在任务里了", shareurl=shareurl)

        account = self.account_factory()
        tmdb_service = self.tmdb_factory()
        task = build_media_task_from_share(shareurl, text, account, self.config_data, tmdb_service)
        task["telegram_inbox"] = {
            "message_id": message.get("message_id"),
            "chat_id": _message_chat_id(message),
            "created_at": int(time.time()),
        }
        self.config_data.setdefault("tasklist", []).append(task)
        task_index = len(self.config_data["tasklist"]) - 1
        run_task_snapshot = copy.deepcopy(task)
        self.save_config(self.config_data)
        self.run_task(run_task_snapshot, task_index)
        self.logger(f"Telegram 自动收链已创建任务: {task.get('taskname', '')} -> {task.get('savepath', '')}")
        return TelegramAutoCreateResult(
            "created",
            f"已创建任务并开始转存：{task.get('taskname', '')}",
            task=task,
            task_index=task_index,
            shareurl=shareurl,
            run_started=True,
        )


class TelegramInboxPoller:
    def __init__(
        self,
        config_getter: Callable[[], Dict[str, Any]],
        service_factory: Callable[[Dict[str, Any]], TelegramAutoCreateService],
        state_saver: Callable[[Dict[str, Any]], None],
        session: Optional[requests.Session] = None,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self.config_getter = config_getter
        self.service_factory = service_factory
        self.state_saver = state_saver
        self.session = session or requests.Session()
        self.logger = logger or (lambda message: None)
        self._running = False
        self._webhook_deleted = False

    @staticmethod
    def enabled(push_config: Dict[str, Any]) -> bool:
        return (
            normalize_bool(push_config.get("TG_INBOX_AUTO_CREATE"), False)
            and bool(push_config.get("TG_BOT_TOKEN"))
            and bool(push_config.get("TG_USER_ID"))
        )

    @staticmethod
    def api_base(push_config: Dict[str, Any]) -> str:
        host = str(push_config.get("TG_API_HOST") or "").strip().rstrip("/")
        if not host:
            host = "https://api.telegram.org"
        return f"{host}/bot{push_config.get('TG_BOT_TOKEN')}"

    @staticmethod
    def request_kwargs(push_config: Dict[str, Any]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"timeout": 35}
        proxy_host = str(push_config.get("TG_PROXY_HOST") or "").strip()
        proxy_port = str(push_config.get("TG_PROXY_PORT") or "").strip()
        if proxy_host and proxy_port:
            proxy_auth = str(push_config.get("TG_PROXY_AUTH") or "").strip()
            auth_prefix = f"{proxy_auth}@" if proxy_auth else ""
            proxy = f"http://{auth_prefix}{proxy_host}:{proxy_port}"
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        return kwargs

    def send_reply(self, push_config: Dict[str, Any], chat_id: str, text: str) -> None:
        if not chat_id:
            chat_id = str(push_config.get("TG_USER_ID") or "")
        try:
            self.session.post(
                f"{self.api_base(push_config)}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                **self.request_kwargs(push_config),
            )
        except Exception as exc:
            self.logger(f"Telegram 自动收链回复失败: {exc}")

    def ensure_long_polling_available(self, push_config: Dict[str, Any]) -> None:
        if self._webhook_deleted:
            return
        response = self.session.post(
            f"{self.api_base(push_config)}/deleteWebhook",
            data={"drop_pending_updates": "false"},
            **self.request_kwargs(push_config),
        )
        try:
            data = response.json()
        except Exception:
            data = {}
        if data and not data.get("ok", True):
            raise RuntimeError(str(data))
        self._webhook_deleted = True
        self.logger("Telegram 自动收链已切换为长轮询模式")

    def poll_once(self) -> int:
        config_data = self.config_getter()
        push_config = (config_data.get("push_config") or {}) if isinstance(config_data, dict) else {}
        if not self.enabled(push_config):
            return 0
        self.ensure_long_polling_available(push_config)
        offset = int(push_config.get("TG_INBOX_LAST_UPDATE_ID") or 0) + 1
        response = self.session.get(
            f"{self.api_base(push_config)}/getUpdates",
            params={"offset": offset, "timeout": 25, "allowed_updates": '["message"]'},
            **self.request_kwargs(push_config),
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(str(data))
        processed = 0
        service = self.service_factory(config_data)
        for update in data.get("result") or []:
            update_id = int(update.get("update_id") or 0)
            message = update.get("message") or {}
            if message:
                try:
                    result = service.handle_message(message)
                    if result.status in {"created", "duplicate", "no_link"}:
                        self.send_reply(push_config, _message_chat_id(message), result.message)
                except Exception as exc:
                    self.send_reply(push_config, _message_chat_id(message), f"自动创建任务失败：{exc}")
                    self.logger(f"Telegram 自动收链处理失败: {exc}")
            if update_id:
                push_config["TG_INBOX_LAST_UPDATE_ID"] = update_id
                self.state_saver(config_data)
            processed += 1
        return processed

    def run_forever(self, stop_event: Optional[Callable[[], bool]] = None) -> None:
        self._running = True
        while self._running and not (stop_event and stop_event()):
            try:
                processed = self.poll_once()
                if processed == 0:
                    time.sleep(3)
            except Exception as exc:
                self.logger(f"Telegram 自动收链轮询异常: {exc}")
                time.sleep(8)

    def stop(self) -> None:
        self._running = False
