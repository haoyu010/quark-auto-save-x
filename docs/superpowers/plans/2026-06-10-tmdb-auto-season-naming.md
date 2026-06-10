# TMDB Auto Season Naming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically rewrite episode naming season tokens from TMDB/task metadata before transfer and rename operations.

**Architecture:** Add small pure helpers to `quark_auto_save.py` for extracting a season number and rewriting `SxxE[]` patterns. The transfer flow calls one applicator before existing episode naming logic, keeping current naming branches intact.

**Tech Stack:** Python, existing `TMDBService`, pytest.

---

### Task 1: Pure Season Naming Helpers

**Files:**
- Modify: `quark_auto_save.py`
- Test: `tests/test_tmdb_auto_season_naming.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert `Show - S01E[]` becomes `Show - S05E[]` when task metadata says season 5, that non-episode naming is unchanged, and that an injected resolver can supply season 6.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py -q`
Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Implement helpers**

Add `rewrite_episode_naming_season`, `get_task_tmdb_season_number`, `infer_tmdb_season_number_for_task`, and `apply_tmdb_season_to_episode_naming`.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py -q`
Expected: PASS.

### Task 2: Wire Into Transfer Flow

**Files:**
- Modify: `quark_auto_save.py`
- Test: `tests/test_tmdb_auto_season_naming.py`

- [ ] **Step 1: Write failing flow test**

Add a fake `Quark` test proving `dir_check_and_save` saves only files named with the resolved season pattern.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py -q`
Expected: FAIL because the transfer flow still uses the literal `S01E[]`.

- [ ] **Step 3: Apply helper in `do_save_task` and `do_rename_task`**

Call `apply_tmdb_season_to_episode_naming(task, CONFIG_DATA)` before the existing episode naming branches build regexes or rename patterns.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests\test_tmdb_auto_season_naming.py tests\test_auto_replace_persist.py -q`
Expected: PASS.

### Task 3: Version And Verification

**Files:**
- Modify: `VERSION`
- Modify: `docker-compose.ghcr.yml`

- [ ] **Step 1: Bump version**

Set `VERSION` to `1.0.14` and GHCR image tag to `v1.0.14`.

- [ ] **Step 2: Run verification**

Run: `python -m pytest tests -q`
Run: `python -m py_compile notify.py app\run.py app\sdk\resource_replacer.py app\sdk\telegram_channel.py quark_auto_save.py`
Run: `git diff --check`

- [ ] **Step 3: Commit and push**

Commit with message `Add TMDB auto season naming` and push `origin x`.

