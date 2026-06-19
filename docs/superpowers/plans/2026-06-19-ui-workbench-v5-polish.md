# UI Workbench v5 Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing WebUI feel more modern and coordinated without changing transfer, Telegram, TMDB, or configuration behavior.

**Architecture:** Keep this as a visual layer: add semantic template classes for the task page and top toolbar buttons, then append a final CSS section that overrides older theme layers. The new layer must target the existing Vue/Bootstrap markup and avoid broad JavaScript changes.

**Tech Stack:** Flask templates, Vue 2 template syntax, Bootstrap 4, Bootstrap Icons, CSS.

---

### Task 1: Guard the UI Refresh With Static Tests

**Files:**
- Modify: `tests/test_ui_workbench_css.py`

- [x] **Step 1: Add assertions for the v5 polish layer**

Add a test that requires the final CSS marker, task page class, semantic toolbar button classes, compact config section polish, discovery search polish, and poster hover finish.

- [x] **Step 2: Run the focused test and confirm it fails**

Run: `python -m pytest tests\test_ui_workbench_css.py -q`

Expected: failure mentioning missing `Workbench Refresh v5`.

### Task 2: Add Semantic Template Hooks

**Files:**
- Modify: `app/templates/index.html`

- [x] **Step 1: Add toolbar action classes**

Update the four top toolbar buttons to include `toolbar-action-save`, `toolbar-action-run`, `toolbar-action-scroll`, and `toolbar-action-width`.

- [x] **Step 2: Add the task page root class**

Change the task list root from `v-if="activeTab === 'tasklist'"` to include `class="tasklist-workbench-page"`.

### Task 3: Add the v5 Visual Layer

**Files:**
- Modify: `app/static/css/main.css`

- [x] **Step 1: Append `Workbench Refresh v5` CSS**

Add a final CSS section for toolbar buttons, task dashboard, compact config rows, Telegram/source panels, discovery search, poster cards, tables, and responsive behavior.

- [x] **Step 2: Keep v4 behavior intact**

Do not delete v4 rules. The v5 section should override only the visual details needed for this pass.

### Task 4: Version, Verify, Commit, Push, Deploy

**Files:**
- Modify: `VERSION`
- Modify: `docker-compose.ghcr.yml`

- [x] **Step 1: Bump version**

Change `1.0.35` to `1.0.36` in `VERSION` and the GHCR compose tag.

- [x] **Step 2: Verify**

Run:

```powershell
python -m pytest tests -q
python -m py_compile notify.py app\run.py app\sdk\resource_replacer.py app\sdk\telegram_channel.py app\sdk\telegram_inbox.py app\sdk\tmdb_service.py quark_auto_save.py
git diff --check
```

- [x] **Step 3: Browser check**

Reload the local app and inspect config, task list, and discovery. Confirm the toolbar icons look clean and the config rows are tighter.

- [ ] **Step 4: Commit, push, deploy**

Commit as `style: polish workbench ui`, push `origin x`, wait for the GHCR image, then update FlyingNAS to `v1.0.36`.
