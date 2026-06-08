# Auto Replace Invalid Shareurl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically replace invalid Quark share links with verified search results without lowering resource quality.

**Architecture:** Add a focused `ResourceAutoReplacer` service under `app/sdk/` that searches existing CloudSaver/PanSou providers, validates candidate shares through the current `Quark` account, scores quality, and mutates the task only when the candidate clears the configured threshold. Wire it into `Quark.do_save_task()` before returning on invalid shares and add WebUI/config defaults for enabling and tuning the threshold.

**Tech Stack:** Python standard library, existing Quark API wrapper, existing CloudSaver/PanSou SDKs, Vue 2 template settings UI, `unittest`.

---

### Task 1: Core Replacer Tests

**Files:**
- Create: `tests/test_resource_replacer.py`
- Create: `app/sdk/resource_replacer.py`

- [ ] **Step 1: Write failing tests**

Create tests for these behaviors:

```python
import unittest

from app.sdk.resource_replacer import ResourceAutoReplacer


class FakeAccount:
    def __init__(self, shares):
        self.shares = shares

    def extract_url(self, url):
        share_id = url.rsplit("/", 1)[-1]
        return share_id, "", "", {}

    def get_stoken(self, pwd_id, passcode):
        return pwd_id in self.shares, pwd_id if pwd_id in self.shares else "失效"

    def get_detail(self, pwd_id, stoken, pdir_fid="", _fetch_share=0):
        return {"list": self.shares.get(pwd_id, [])}


class ResourceAutoReplacerTest(unittest.TestCase):
    def test_rejects_lower_resolution_than_task_hint(self):
        account = FakeAccount({
            "low": [{"file_name": "Show.S01E01.1080p.mkv", "size": 1000, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01", "shareurl": "https://pan.quark.cn/s/low"}]],
        )
        task = {"taskname": "Show S01 2160p", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertFalse(result["replaced"])
        self.assertEqual(task["shareurl"], "old")

    def test_replaces_with_verified_no_downgrade_candidate(self):
        account = FakeAccount({
            "good": [{"file_name": "Show.S01E01.2160p.mkv", "size": 4000, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01 2160p", "shareurl": "https://pan.quark.cn/s/good"}]],
        )
        task = {"taskname": "Show S01 2160p", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertTrue(result["replaced"])
        self.assertEqual(task["shareurl"], "https://pan.quark.cn/s/good")
        self.assertIsNone(task.get("shareurl_ban"))
```

- [ ] **Step 2: Run red tests**

Run: `python -m unittest tests.test_resource_replacer -v`

Expected: import fails because `app.sdk.resource_replacer` does not exist yet.

- [ ] **Step 3: Implement minimal `ResourceAutoReplacer`**

Create the module with config parsing, query building, share validation, resolution extraction, score calculation, and replacement mutation.

- [ ] **Step 4: Run green tests**

Run: `python -m unittest tests.test_resource_replacer -v`

Expected: 2 tests pass.

### Task 2: Runtime Integration

**Files:**
- Modify: `quark_auto_save.py`

- [ ] **Step 1: Add a helper on `Quark`**

Add `try_auto_replace_invalid_shareurl()` to call `ResourceAutoReplacer` with the global config and current account.

- [ ] **Step 2: Retry on existing `shareurl_ban`**

At the beginning of `do_save_task()`, attempt replacement when `task["shareurl_ban"]` already exists. Continue the task when replaced; keep the old warning when no acceptable replacement is found.

- [ ] **Step 3: Retry on newly detected invalid links**

After unrecoverable `get_stoken`, unrecoverable `get_detail`, and empty root share detection, attempt replacement and recursively retry once.

- [ ] **Step 4: Compile check**

Run: `python -m py_compile quark_auto_save.py app\sdk\resource_replacer.py`

Expected: exit code 0.

### Task 3: Config and UI Defaults

**Files:**
- Modify: `quark_config.json`
- Modify: `app/run.py`
- Modify: `app/templates/index.html`

- [ ] **Step 1: Add defaults**

Add `task_settings.auto_replace_invalid_shareurl = "enabled"` and `task_settings.auto_replace_min_score = 85`.

- [ ] **Step 2: Add settings controls**

Add two controls next to the existing auto-search settings: enable/disable automatic replacement and numeric minimum score.

- [ ] **Step 3: Verify template/config parse**

Run: `python -m py_compile app\run.py`

Expected: exit code 0.

### Task 4: Final Verification and Commit

**Files:**
- All changed files

- [ ] **Step 1: Run tests**

Run: `python -m unittest tests.test_resource_replacer -v`

- [ ] **Step 2: Run compile check**

Run: `python -m py_compile app\run.py quark_auto_save.py app\sdk\resource_replacer.py app\sdk\pansou.py app\sdk\cloudsaver.py`

- [ ] **Step 3: Run whitespace check**

Run: `git diff --check`

- [ ] **Step 4: Commit and push**

Commit: `Auto replace invalid share links`

Push: `git push origin x`
