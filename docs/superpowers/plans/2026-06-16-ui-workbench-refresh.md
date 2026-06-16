# UI Workbench Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the selected modern workbench UI direction, with especially compact and polished configuration items.

**Architecture:** Keep behavior unchanged and implement the refresh as a final CSS layer in `app/static/css/main.css`, plus only minimal template class additions if needed. This avoids touching Vue logic while overriding the older stacked theme patches.

**Tech Stack:** HTML, CSS, Bootstrap 4, Bootstrap Icons, Vue 2 templates, Python Flask static serving.

---

### Task 1: Add Compact Configuration Styling

**Files:**
- Modify: `app/static/css/main.css`

- [ ] **Step 1: Add a final CSS section named `Workbench Refresh v4`**

Append a final CSS section at the end of `app/static/css/main.css`. Start with workbench tokens and compact config rules:

```css
/* --------------- Workbench Refresh v4 --------------- */
:root {
  --qasx-v4-bg: #f4f7fb;
  --qasx-v4-panel: #ffffff;
  --qasx-v4-soft: #f8fafc;
  --qasx-v4-line: #dbe5f0;
  --qasx-v4-line-strong: #c7d5e6;
  --qasx-v4-ink: #111827;
  --qasx-v4-muted: #64748b;
  --qasx-v4-blue: #2563eb;
  --qasx-v4-teal: #14b8a6;
  --qasx-v4-amber: #f59e0b;
  --qasx-v4-rose: #e11d48;
  --qasx-v4-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
}

.config-workbench-page .row.title {
  min-height: 44px !important;
  margin: 14px 0 8px !important;
  padding: 8px 12px !important;
  border-radius: 12px !important;
}

.config-workbench-page .row.title h2 {
  min-height: 24px;
  font-size: 1.02rem !important;
}

.config-workbench-page .row.title h2::before {
  height: 17px;
}

.config-workbench-page .form-group.row,
.config-workbench-page .row.mb-2,
.config-workbench-page .performance-setting-row,
.config-workbench-page .display-setting-row,
.config-workbench-page .task-auto-search-group {
  align-items: center;
  margin: 0 0 8px !important;
  padding: 10px 12px !important;
  border: 1px solid var(--qasx-v4-line);
  border-radius: 12px !important;
  background: #fbfdff;
  box-shadow: none;
}

.config-workbench-page .col-form-label,
.config-workbench-page label {
  margin-bottom: 0;
  color: #334155;
  font-size: 0.88rem;
  font-weight: 850;
}
```

- [ ] **Step 2: Tighten config controls**

In the same final CSS section, add rules to reduce vertical bulk and make inputs/buttons consistent:

```css
.config-workbench-page .input-group {
  min-height: 36px;
  border-radius: 10px !important;
  box-shadow: none !important;
}

.config-workbench-page .input-group-text,
.config-workbench-page .form-control,
.config-workbench-page select.form-control,
.config-workbench-page textarea.form-control,
.config-workbench-page .btn {
  min-height: 36px !important;
  font-size: 0.88rem;
}

.config-workbench-page textarea.form-control {
  min-height: 70px !important;
}

.config-workbench-page .input-group-text {
  padding: 0 10px !important;
  background: #f3f7fb !important;
}

.config-workbench-page .form-control {
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}
```

- [ ] **Step 3: Verify visually**

Start the app locally and open the config page. Check that:
- configuration rows are noticeably tighter,
- labels remain readable,
- inputs do not overlap,
- TG notification block no longer looks oversized compared to ordinary settings.

### Task 2: Unify Global Workbench Surface

**Files:**
- Modify: `app/static/css/main.css`

- [ ] **Step 1: Add final desktop shell overrides**

Append desktop rules after Task 1 rules:

```css
@media (min-width: 768px) {
  body:not(.login-page) {
    background: var(--qasx-v4-bg) !important;
  }

  main > form {
    border-color: rgba(219, 229, 240, 0.9) !important;
    border-radius: 18px !important;
    background: var(--qasx-v4-panel) !important;
    box-shadow: var(--qasx-v4-shadow) !important;
  }

  #sidebarMenu.col-md-2,
  .sidebar.bg-light,
  .sidebar {
    border-radius: 18px !important;
    background: linear-gradient(180deg, #111827 0%, #0f172a 58%, #07111f 100%) !important;
  }

  .sidebar .nav-link {
    border-radius: 10px !important;
  }

  .sidebar .nav-link.active {
    background: rgba(37, 99, 235, 0.22) !important;
    border-color: rgba(125, 211, 252, 0.22) !important;
  }
}
```

- [ ] **Step 2: Tighten common filters and tables**

Add rules:

```css
main .tasklist-filter-row,
main div[v-if="activeTab === 'history'"] .tasklist-filter-row,
main div[v-if="activeTab === 'runlogs'"] .tasklist-filter-row,
main div[v-if="activeTab === 'calendar'"] .tasklist-filter-row {
  padding: 10px !important;
  border-radius: 12px !important;
  background: #f8fafc !important;
}

.table-responsive,
.task,
.calendar-task-card,
.calendar-poster-card,
.notify-hub .notify-panel,
.source-panel {
  border-radius: 12px !important;
  border-color: var(--qasx-v4-line) !important;
}

main .table thead th {
  background: #f8fafc !important;
  color: #334155 !important;
}
```

- [ ] **Step 3: Verify existing UI behavior remains unchanged**

Open task list, history, run logs, calendar, and config. Confirm filters still work visually and no buttons disappear.

### Task 3: Improve Discovery Media Wall

**Files:**
- Modify: `app/static/css/main.css`

- [ ] **Step 1: Add poster wall polish**

Append discovery-specific rules:

```css
.discovery-page-shell .discovery-hero-panel {
  border-radius: 16px !important;
  background: linear-gradient(135deg, #111827 0%, #123c5d 52%, #0f766e 100%) !important;
}

.discovery-page-shell .discovery-grid.discovery-wall-grid,
.tasklist-poster-mode .discovery-grid {
  gap: 18px !important;
}

.discovery-page-shell .discovery-poster,
.tasklist-poster-mode .discovery-poster {
  border-radius: 13px !important;
  overflow: hidden;
  background: #111827;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.16) !important;
}

.discovery-page-shell .discovery-poster img,
.tasklist-poster-mode .discovery-poster img {
  filter: none !important;
  transform: translateZ(0);
}

.discovery-page-shell .discovery-poster:hover img,
.tasklist-poster-mode .discovery-poster:hover img {
  transform: scale(1.03);
}

.discovery-card-action,
.discovery-rating,
.discovery-refresh-metadata,
.discovery-edit-metadata {
  border-radius: 9px !important;
}
```

- [ ] **Step 2: Verify poster quality**

Open discovery and task poster view. Confirm images are not blurred by CSS filters, poster cards are evenly spaced, and action icons remain clickable.

### Task 4: Version, Verification, Commit, Deploy

**Files:**
- Modify: `VERSION`
- Modify: `docker-compose.ghcr.yml`

- [ ] **Step 1: Bump version**

Change `VERSION` from the current value to the next patch version and update `docker-compose.ghcr.yml` to the matching `ghcr.io/haoyu010/quark-auto-save-x:vX.Y.Z` tag.

- [ ] **Step 2: Run verification**

Run:

```powershell
python -m pytest tests -q
python -m py_compile notify.py app\run.py app\sdk\resource_replacer.py app\sdk\telegram_channel.py app\sdk\telegram_inbox.py app\sdk\tmdb_service.py quark_auto_save.py
git diff --check
```

Expected:
- tests pass,
- compile command exits 0,
- diff check has no errors.

- [ ] **Step 3: Commit and push**

Run:

```powershell
git add app/static/css/main.css VERSION docker-compose.ghcr.yml docs/superpowers/specs/2026-06-16-ui-workbench-refresh-design.md docs/superpowers/plans/2026-06-16-ui-workbench-refresh.md
git commit -m "style: refresh workbench ui"
git push origin x
```

- [ ] **Step 4: Deploy**

After GHCR publishes the new tag, update FlyingNAS compose image, preserve `4005:5005`, restart, and verify:

```sh
docker ps --filter name=quark-auto-save-x
docker exec quark-auto-save-x python -c 'import os; print(os.environ.get("APP_VERSION")); print(open("/app/VERSION").read().strip())'
```

