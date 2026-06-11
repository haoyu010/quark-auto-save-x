import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


QUALITY_ORDER = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "2k": 1440,
    "1440p": 1440,
    "4k": 2160,
    "2160p": 2160,
    "8k": 4320,
    "4320p": 4320,
}

DEFAULT_MEDIA_EXCLUDE_KEYWORDS = (
    "海报,poster,posters,封面,cover,covers,图片,image,images,"
    "备用,backup,bak,重复,duplicate,duplicates,"
    "sample,samples,样片,预览,nfo,txt,url,jpg,jpeg,png,webp"
)


class ResourceAutoReplacer:
    """Search, validate, score, and replace invalid Quark share links."""

    def __init__(
        self,
        config_data: Dict[str, Any],
        account: Any,
        searchers: Optional[List[Callable[[str], Iterable[Dict[str, Any]]]]] = None,
        logger: Optional[Callable[[str], None]] = None,
        episode_extractor: Optional[Callable[[str], Any]] = None,
    ):
        self.config_data = config_data or {}
        self.account = account
        self.logger = logger or (lambda message: None)
        self.episode_extractor = episode_extractor
        self.settings = self._load_settings()
        self.searchers = searchers if searchers is not None else self._build_searchers()

    def try_replace(self, task: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
        result = {
            "attempted": False,
            "replaced": False,
            "message": "",
            "reason": reason,
            "best": None,
        }
        if not task:
            result["message"] = "任务为空"
            return result
        if not self.settings["enabled"]:
            result["message"] = "自动换源未启用"
            return result
        if not self.searchers:
            result["message"] = "未配置可用搜索来源"
            return result

        queries = self.build_search_queries(task)
        if not queries:
            result["message"] = "无法生成搜索关键词"
            return result

        result["attempted"] = True
        baseline = self._build_quality_baseline(task)
        candidates = self._collect_candidates(queries)
        scored = []
        for candidate in candidates:
            shareurl = candidate.get("shareurl") or ""
            if not shareurl or self._same_share(shareurl, task.get("shareurl") or ""):
                continue
            snapshot = self.validate_share(shareurl)
            if not snapshot["success"]:
                continue
            filtered_files = self.filter_files_by_task(snapshot["files"], task)
            if not filtered_files:
                continue
            snapshot["files"] = filtered_files
            score, score_reason = self.score_candidate(task, candidate, snapshot, baseline)
            if score >= self.settings["min_score"]:
                scored.append({
                    "candidate": candidate,
                    "score": score,
                    "reason": score_reason,
                    "snapshot": snapshot,
                })

        if not scored:
            result["message"] = "未找到达到质量阈值的有效替换链接"
            return result

        scored.sort(
            key=lambda item: (
                item["score"],
                self._to_ts(item["candidate"].get("publish_date") or item["candidate"].get("datetime")),
            ),
            reverse=True,
        )
        best = scored[0]
        best_url = best["candidate"].get("shareurl")
        old_url = task.get("shareurl")
        task["shareurl"] = best_url
        task["shareurl_ban"] = None
        result.update({
            "replaced": True,
            "message": f"已替换失效链接：{old_url} -> {best_url}",
            "old_shareurl": old_url,
            "best": {
                "shareurl": best_url,
                "taskname": best["candidate"].get("taskname", ""),
                "source": best["candidate"].get("source", ""),
                "score": best["score"],
                "reason": best["reason"],
                "files": best["snapshot"].get("files", []),
            },
        })
        return result

    def _load_settings(self) -> Dict[str, Any]:
        raw = self.config_data.get("auto_replace_invalid_shareurl")
        task_settings = self.config_data.get("task_settings", {}) or {}
        if raw is None:
            raw = task_settings.get("auto_replace_invalid_shareurl", "disabled")

        if isinstance(raw, dict):
            enabled = self._as_enabled(raw.get("enabled", False))
            min_score = raw.get("min_score", task_settings.get("auto_replace_min_score", 85))
            sources = raw.get("sources", ["telegram"])
            quality_policy = raw.get("quality_policy", "no_downgrade")
            search_timeout = raw.get("timeout_seconds", task_settings.get("auto_replace_timeout_seconds", 8))
        else:
            enabled = self._as_enabled(raw)
            min_score = task_settings.get("auto_replace_min_score", 85)
            sources = task_settings.get("auto_replace_sources", ["telegram"])
            quality_policy = task_settings.get("auto_replace_quality_policy", "no_downgrade")
            search_timeout = task_settings.get("auto_replace_timeout_seconds", 8)

        try:
            min_score = int(min_score)
        except Exception:
            min_score = 85
        if min_score < 0:
            min_score = 0
        if min_score > 100:
            min_score = 100
        try:
            search_timeout = int(search_timeout)
        except Exception:
            search_timeout = 8
        if search_timeout < 2:
            search_timeout = 2
        if search_timeout > 60:
            search_timeout = 60
        if isinstance(sources, str):
            sources = [item.strip().lower() for item in sources.split(",") if item.strip()]
        allowed_sources = {"telegram"}
        sources = [
            str(item).strip().lower()
            for item in (sources or [])
            if str(item).strip().lower() in allowed_sources
        ]
        return {
            "enabled": enabled,
            "min_score": min_score,
            "sources": sources or ["telegram"],
            "quality_policy": quality_policy or "no_downgrade",
            "search_timeout": search_timeout,
        }

    def _build_searchers(self) -> List[Callable[[str], Iterable[Dict[str, Any]]]]:
        searchers = []
        sources_cfg = self.config_data.get("source", {}) or {}
        enabled_sources = set(self.settings["sources"])

        if "telegram" in enabled_sources:
            tg_data = sources_cfg.get("telegram", {}) or {}
            try:
                from .telegram_channel import TelegramChannelCache

                tg_cfg = dict(tg_data)
                tg_cfg.setdefault("timeout_seconds", self.settings["search_timeout"])
                tg = TelegramChannelCache(tg_cfg)
            except Exception as exc:
                self.logger(f"Telegram 自动换源初始化失败: {exc}")
                tg = None

            if tg is not None and getattr(tg, "enabled", False) and getattr(tg, "channels", []):
                def telegram_search(query, client=tg):
                    client.ensure_fresh()
                    return client.search(query, limit=getattr(client, "verify_limit", 5))

                searchers.append(telegram_search)

        return searchers

    def build_search_queries(self, task: Dict[str, Any]) -> List[str]:
        seeds = [
            task.get("taskname", ""),
            task.get("episode_naming", ""),
            task.get("sequence_naming", ""),
            task.get("pattern", ""),
            os.path.basename(str(task.get("savepath", "")).replace("\\", "/")),
        ]
        queries = []
        for seed in seeds:
            clean = self._clean_query(seed)
            if clean and clean not in queries:
                queries.append(clean)
            no_quality = self._remove_quality_terms(clean)
            if no_quality and no_quality not in queries:
                queries.append(no_quality)
        return queries[:5]

    def validate_share(self, shareurl: str) -> Dict[str, Any]:
        try:
            pwd_id, passcode, pdir_fid, _ = self.account.extract_url(shareurl)
            if not pwd_id:
                return {"success": False, "files": [], "error": "提取链接参数失败"}
            is_sharing, stoken = self.account.get_stoken(pwd_id, passcode)
            if not is_sharing:
                return {"success": False, "files": [], "error": str(stoken)}
            detail = self.account.get_detail(pwd_id, stoken, pdir_fid, _fetch_share=1)
            if isinstance(detail, dict) and detail.get("error"):
                return {"success": False, "files": [], "error": str(detail.get("error"))}
            files = detail.get("list", []) if isinstance(detail, dict) else []
            if len(files) == 1 and files[0].get("dir"):
                sub_detail = self.account.get_detail(pwd_id, stoken, files[0].get("fid", ""))
                sub_files = sub_detail.get("list", []) if isinstance(sub_detail, dict) else []
                if sub_files:
                    files = sub_files
            if not files:
                return {"success": False, "files": [], "error": "分享为空"}
            return {"success": True, "files": files, "error": ""}
        except Exception as exc:
            return {"success": False, "files": [], "error": str(exc)}

    def filter_files_by_task(self, files: List[Dict[str, Any]], task: Dict[str, Any]) -> List[Dict[str, Any]]:
        usable = [item for item in files if isinstance(item, dict) and not item.get("dir")]
        filterwords = self._effective_filterwords(task)
        if not filterwords:
            return usable

        normalized = filterwords.replace("，", ",")
        if "|" not in normalized:
            blocked = [word.strip().lower() for word in normalized.split(",") if word.strip()]
            return [item for item in usable if not self._matches_any_filter(item, blocked)]

        parts = normalized.split("|")
        keep_parts = [part.strip() for part in parts[:-1] if part.strip()]
        block_part = parts[-1].strip()
        filtered = usable
        for keep_part in keep_parts:
            words = [word.strip().lower() for word in keep_part.split(",") if word.strip()]
            if words:
                filtered = [
                    item for item in filtered
                    if any(word in str(item.get("file_name", "")).lower() for word in words)
                ]
        blocked = [word.strip().lower() for word in block_part.split(",") if word.strip()]
        if blocked:
            filtered = [item for item in filtered if not self._matches_any_filter(item, blocked)]
        return filtered

    def _effective_filterwords(self, task: Dict[str, Any]) -> str:
        task_filterwords = str((task or {}).get("filterwords") or "").strip()
        task_settings = self.config_data.get("task_settings", {}) or {}
        if "media_exclude_keywords" in task_settings:
            default_filterwords = str(task_settings.get("media_exclude_keywords") or "").strip()
        else:
            default_filterwords = DEFAULT_MEDIA_EXCLUDE_KEYWORDS
        if not default_filterwords:
            return task_filterwords
        if not task_filterwords:
            return default_filterwords
        if "|" not in task_filterwords:
            return self._merge_filter_terms(task_filterwords, default_filterwords)
        parts = task_filterwords.split("|")
        block_part = parts[-1].strip()
        merged_block = self._merge_filter_terms(block_part, default_filterwords)
        return "|".join(parts[:-1] + [merged_block])

    def _merge_filter_terms(self, *groups: str) -> str:
        merged = []
        seen = set()
        for group in groups:
            text = str(group or "").replace("，", ",")
            for term in text.split(","):
                term = term.strip()
                if not term:
                    continue
                key = term.lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(term)
        return ",".join(merged)

    def score_candidate(
        self,
        task: Dict[str, Any],
        candidate: Dict[str, Any],
        snapshot: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> Tuple[int, str]:
        files = snapshot["files"]
        candidate_text = " ".join([
            str(candidate.get("taskname") or ""),
            str(candidate.get("content") or ""),
            " ".join(str(item.get("file_name", "")) for item in files),
        ])
        required_resolution = baseline.get("required_resolution") or 0
        candidate_resolution = self.extract_max_resolution(candidate_text)
        if required_resolution and candidate_resolution < required_resolution:
            return 0, f"清晰度降低: 需要 {required_resolution}p，候选 {candidate_resolution or '未知'}"
        if not required_resolution and candidate_resolution and candidate_resolution < 1080:
            return 0, f"候选清晰度低于自动换源底线: {candidate_resolution}p"

        required_season = self.extract_season(" ".join([
            str(task.get("taskname", "")),
            str(task.get("episode_naming", "")),
            str(task.get("sequence_naming", "")),
            str(task.get("savepath", "")),
        ]))
        candidate_season = self.extract_season(candidate_text)
        if required_season and candidate_season and candidate_season != required_season:
            return 0, f"季号不匹配: 需要 S{required_season:02d}，候选 S{candidate_season:02d}"

        baseline_avg_size = baseline.get("avg_size") or 0
        candidate_avg_size = self._avg_size(files)
        if baseline_avg_size and candidate_avg_size and candidate_avg_size < baseline_avg_size * 0.65:
            return 0, "文件体积明显下降"

        score = 30
        score += self._title_relevance_score(task, candidate, candidate_text)
        score += 15
        if required_resolution:
            score += 20
        elif candidate_resolution >= 2160:
            score += 18
        elif candidate_resolution >= 1080:
            score += 14
        elif candidate_resolution:
            score += 8
        else:
            score += 0
        if required_season:
            score += 10
        elif candidate_season:
            score += 6
        if baseline_avg_size:
            score += 10 if candidate_avg_size >= baseline_avg_size * 0.85 else 5
        elif candidate_avg_size:
            score += 5
        if candidate.get("source"):
            score += 3
        if candidate.get("publish_date") or candidate.get("datetime"):
            score += 2
        return min(score, 100), "有效链接且质量达标"

    def _build_quality_baseline(self, task: Dict[str, Any]) -> Dict[str, Any]:
        hint_text = " ".join([
            str(task.get("taskname", "")),
            str(task.get("savepath", "")),
            str(task.get("pattern", "")),
            str(task.get("replace", "")),
            str(task.get("filterwords", "")),
            str(task.get("episode_naming", "")),
            str(task.get("sequence_naming", "")),
        ])
        files = self._load_saved_files(task)
        saved_text = " ".join(str(item.get("file_name", "")) for item in files)
        required_resolution = max(
            self.extract_max_resolution(hint_text),
            self.extract_max_resolution(saved_text),
        )
        return {
            "required_resolution": required_resolution,
            "avg_size": self._avg_size(files),
        }

    def _load_saved_files(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            savepath = str(task.get("savepath", "")).lstrip("/")
            fid = getattr(self.account, "savepath_fid", {}).get(savepath)
            if not fid:
                fid = getattr(self.account, "savepath_fid", {}).get(f"/{savepath}")
            if not fid or not hasattr(self.account, "ls_dir"):
                return []
            files = self.account.ls_dir(fid)
            return files if isinstance(files, list) else []
        except Exception:
            return []

    def _collect_candidates(self, queries: List[str]) -> List[Dict[str, Any]]:
        candidates = []
        seen = set()
        for query in queries:
            for searcher in self.searchers:
                try:
                    results = searcher(query) or []
                except Exception as exc:
                    self.logger(f"自动换源搜索失败 [{query}]: {exc}")
                    continue
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    shareurl = item.get("shareurl") or ""
                    key = self._normalize_share_id(shareurl) or shareurl
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    candidates.append(item)
        return candidates

    def extract_max_resolution(self, text: str) -> int:
        if not text:
            return 0
        lower = str(text).lower()
        matches = []
        for token, value in QUALITY_ORDER.items():
            if re.search(rf"(?<!\d){re.escape(token)}(?!\d)", lower):
                matches.append(value)
        return max(matches) if matches else 0

    def extract_season(self, text: str) -> Optional[int]:
        if not text:
            return None
        s = str(text)
        match = re.search(r"[Ss](\d{1,2})(?:[Ee]\d{1,3})?", s)
        if match:
            return int(match.group(1))
        match = re.search(r"第\s*(\d{1,2})\s*季", s)
        if match:
            return int(match.group(1))
        return None

    def _title_relevance_score(self, task: Dict[str, Any], candidate: Dict[str, Any], candidate_text: str) -> int:
        query = self._remove_quality_terms(self._clean_query(str(task.get("taskname", "")))).lower()
        candidate_lower = candidate_text.lower()
        tokens = [token for token in re.split(r"[\s._\-]+", query) if len(token) >= 2 and not token.startswith("s0")]
        if not tokens:
            return 15
        matched = sum(1 for token in tokens if token in candidate_lower)
        ratio = matched / len(tokens)
        if ratio >= 0.8:
            return 25
        if ratio >= 0.5:
            return 18
        if ratio > 0:
            return 10
        return 0

    def _matches_any_filter(self, item: Dict[str, Any], words: List[str]) -> bool:
        name = str(item.get("file_name", "")).lower()
        text = " ".join([
            str(item.get("file_name", "")),
            str(item.get("relative_path", "")),
            str(item.get("path", "")),
        ]).lower()
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        return any(word in text or word == ext for word in words)

    def _avg_size(self, files: List[Dict[str, Any]]) -> float:
        sizes = [
            float(item.get("size") or 0)
            for item in files
            if isinstance(item, dict) and not item.get("dir") and float(item.get("size") or 0) > 0
        ]
        return sum(sizes) / len(sizes) if sizes else 0

    def _clean_query(self, value: str) -> str:
        if not value:
            return ""
        text = str(value)
        text = re.sub(r"https?://\S+", " ", text)
        text = text.replace("{}", " ").replace("[]", " ")
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" -_·")
        return text

    def _remove_quality_terms(self, value: str) -> str:
        if not value:
            return ""
        text = re.sub(r"(?i)\b(480p|720p|1080p|1440p|2160p|4320p|2k|4k|8k|web-dl|webrip|bluray|hdr|dv)\b", " ", value)
        text = re.sub(r"\s+", " ", text).strip(" -_·")
        return text

    def _same_share(self, left: str, right: str) -> bool:
        left_id = self._normalize_share_id(left)
        right_id = self._normalize_share_id(right)
        return bool(left_id and right_id and left_id == right_id)

    def _normalize_share_id(self, shareurl: str) -> str:
        if not shareurl:
            return ""
        match = re.search(r"/s/([a-zA-Z0-9]+)", str(shareurl))
        return match.group(1) if match else ""

    def _to_ts(self, value: Any) -> float:
        if not value:
            return 0
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).timestamp()
            except Exception:
                pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0

    def _as_enabled(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "enabled", "on"}
