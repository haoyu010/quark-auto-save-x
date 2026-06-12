# Variety Naming Rule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated variety-show naming rule so综艺 files keep issue, segment, and bonus labels instead of being forced into plain TV episode names.

**Architecture:** Add small parsing helpers in `quark_auto_save.py` and route only综艺 tasks through them during episode renaming. The existing TV/anime episode naming path stays unchanged for non-variety tasks.

**Tech Stack:** Python, existing `unittest`/`pytest`, existing Quark rename flow.

---

### Task 1: Add Variety Filename Parser Tests

**Files:**
- Modify: `tests/test_tmdb_auto_season_naming.py`
- Modify: `tests/test_episode_notification_tree.py`

- [x] **Step 1: Write failing parser tests**

Add tests that expect:

```python
quark_auto_save.build_variety_episode_name(
    "超燃青春的合唱",
    1,
    "20260605.第7期上.mp4",
) == "超燃青春的合唱 - S01E07 - 上.mp4"

quark_auto_save.build_variety_episode_name(
    "超燃青春的合唱",
    1,
    "20260606.纯享版.mp4",
) == "超燃青春的合唱 - S01 - 20260606 - 纯享版.mp4"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py::TMDBAutoSeasonNamingTest -q`

Expected: FAIL because `build_variety_episode_name` does not exist.

### Task 2: Implement Variety Naming Helpers

**Files:**
- Modify: `quark_auto_save.py`

- [x] **Step 1: Add helpers near episode naming utilities**

Implement:

```python
def is_variety_task(task):
    text = f"{task.get('library_category','')} {task.get('savepath','')} {task.get('content_type','')}"
    return "综艺" in text

def parse_variety_filename(filename):
    # returns {"episode": 7, "date": "20260605", "label": "上"} for 第7期上
    # returns {"episode": None, "date": "20260606", "label": "纯享版"} for date-only bonus files

def build_variety_episode_name(title, season, filename):
    # episode file: 标题 - S01E07 - 上.ext
    # date-only bonus: 标题 - S01 - 20260606 - 纯享版.ext
```

- [x] **Step 2: Run parser tests**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py -q`

Expected: PASS for new parser tests.

### Task 3: Route Variety Tasks Through Dedicated Renamer

**Files:**
- Modify: `quark_auto_save.py`
- Modify: `tests/test_tmdb_auto_season_naming.py`

- [x] **Step 1: Add failing rename-flow test**

Create a fake `EpisodeRenameQuark` with files:

```python
[
    {"fid": "f1", "file_name": "20260604.第7期尝鲜.mp4", "dir": False, "size": 1},
    {"fid": "f2", "file_name": "20260605.第7期上.mp4", "dir": False, "size": 1},
    {"fid": "f3", "file_name": "20260606.纯享版.mp4", "dir": False, "size": 1},
]
```

Expect rename calls:

```python
[
    ("f1", "超燃青春的合唱 - S01E07 - 尝鲜.mp4"),
    ("f2", "超燃青春的合唱 - S01E07 - 上.mp4"),
    ("f3", "超燃青春的合唱 - S01 - 20260606 - 纯享版.mp4"),
]
```

- [x] **Step 2: Implement routing**

In `Quark.do_rename_task`, before generic `extract_episode_number` naming, if `is_variety_task(task)` is true, call `build_variety_episode_name(task["taskname"], season, file_name)`.

- [x] **Step 3: Run focused tests**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py tests\test_episode_notification_tree.py -q`

Expected: PASS.

### Task 4: Version, Verification, Commit, Deploy

**Files:**
- Modify: `VERSION`
- Modify: `docker-compose.ghcr.yml`

- [x] **Step 1: Bump version**

Change `1.0.32` to `1.0.33`.

- [ ] **Step 2: Verify**

Run:

```powershell
python -m pytest tests -q
python -m py_compile notify.py app\run.py app\sdk\resource_replacer.py app\sdk\telegram_channel.py app\sdk\telegram_inbox.py app\sdk\tmdb_service.py quark_auto_save.py
git diff --check
```

Expected: tests pass, compile succeeds, diff check has no errors.

- [ ] **Step 3: Commit and push**

```powershell
git add VERSION docker-compose.ghcr.yml quark_auto_save.py tests/test_tmdb_auto_season_naming.py tests/test_episode_notification_tree.py docs/superpowers/plans/2026-06-12-variety-naming-rule.md
git commit -m "feat: add variety show naming rule"
git push origin x
```

- [ ] **Step 4: Deploy v1.0.33**

Pull `ghcr.io/haoyu010/quark-auto-save-x:v1.0.33`, update remote compose image only, preserve `4005:5005`, restart, and verify `APP_VERSION=1.0.33`.
