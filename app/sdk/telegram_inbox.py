import re
import time
from dataclasses import dataclass
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
    for genre in (details or {}).get("genres") or []:
        name = str(genre.get("name") or "").lower()
        if genre.get("id") == 16 or "animation" in name or "动画" in name:
            return True
    return False


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


def _normalize_media_save_path(path: str) -> str:
    return re.sub(r"/{2,}", "/", str(path or "").replace("\\", "/")).strip().strip("/")


def _telegram_inbox_root_save_path(settings: Dict[str, Any], content_type: str, title: str, year: str = "", season: int = 1) -> str:
    root = _normalize_media_save_path(str((settings or {}).get("telegram_inbox_media_root") or ""))
    if not root:
        return ""

    category = {
        "movie": "电影",
        "tv": "电视剧",
        "anime": "动漫",
        "variety": "综艺",
        "documentary": "纪录片",
    }.get(content_type, "电影")

    if content_type == "movie":
        folder = f"{title} ({year})" if year else title
        return _normalize_media_save_path(f"{root}/{category}/{folder}")

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
        if series_like:
            tv_match = _safe_tmdb_call(tmdb_service.search_tv_show, query, year_seed or None)
        else:
            movie_match = _safe_tmdb_call(tmdb_service.search_movie, query, year_seed or None)
            if not movie_match:
                tv_match = _safe_tmdb_call(tmdb_service.search_tv_show, query, year_seed or None)

    if tv_match:
        details = _safe_tmdb_call(tmdb_service.get_tv_show_details, tv_match.get("id")) if tmdb_service and tv_match.get("id") else None
        title = str((details or {}).get("name") or tv_match.get("name") or query or fallback_title).strip()
        year = _tmdb_year(details or tv_match, "tv") or year_seed
        season = _extract_season_number(seed, " ".join(_share_file_names(files))) or _select_latest_season(details) or 1
        content_type = "anime" if _is_animation(seed, files, config_data, details) else "tv"
        settings = _task_settings(config_data)
        naming = _tv_naming_rule(str(settings.get("tv_naming_rule") or ""), title, season)
        savepath = _telegram_inbox_root_save_path(settings, content_type, title, year, season)
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
            "matched_latest_season_number": season,
            "calendar_info": {
                "extracted": {"show_name": title, "year": year, "content_type": content_type, "season_number": season},
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
        title = _remove_season_from_title(query) or _clean_media_title(fallback_title) or seed
        season = _extract_season_number(seed, " ".join(_share_file_names(files))) or 1
        content_type = "anime" if _is_animation(seed, files, config_data, None) else "tv"
        settings = _task_settings(config_data)
        naming = _tv_naming_rule(str(settings.get("tv_naming_rule") or ""), title, season)
        savepath = _telegram_inbox_root_save_path(settings, content_type, title, year_seed, season)
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
            "matched_latest_season_number": season,
            "calendar_info": {
                "extracted": {"show_name": title, "year": year_seed, "content_type": content_type, "season_number": season},
                "match": {
                    "matched_show_name": title,
                    "matched_year": year_seed,
                    "tmdb_id": None,
                    "latest_season_number": season,
                    "latest_season_fetch_url": "",
                },
            },
        }

    title = str((movie_match or {}).get("title") or _remove_season_from_title(query) or fallback_title).strip()
    year = _tmdb_year(movie_match, "movie") or year_seed
    settings = _task_settings(config_data)
    pattern = str(settings.get("movie_naming_pattern") or "")
    replace_template = str(settings.get("movie_naming_replace") or "")
    savepath = _telegram_inbox_root_save_path(settings, "movie", title, year, 1)
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
        "calendar_info": {
            "extracted": {"show_name": title, "year": year, "content_type": "movie"},
            "match": {
                "matched_show_name": title,
                "matched_year": year,
                "tmdb_id": (movie_match or {}).get("id"),
                "latest_season_number": 1,
            },
        },
    }
    return task


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
        self.save_config(self.config_data)
        self.run_task(task, task_index)
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
