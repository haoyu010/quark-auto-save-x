from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app" / "static" / "css" / "main.css"
INDEX = ROOT / "app" / "templates" / "index.html"


def test_workbench_refresh_css_exists():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "Workbench Refresh v4" in css
    assert "--qasx-v4-bg" in css
    assert 'class="config-workbench-page"' in index
    assert ".config-workbench-page .form-group.row" in css
    assert ".config-workbench-page .input-group" in css
    assert "padding: 0 !important;" in css
    assert ".config-workbench-page .row.title h2" in css
    assert "color: #1e293b !important;" in css
    assert ".discovery-page-shell .discovery-poster" in css


def test_old_navbar_quick_actions_are_not_rendered():
    index = INDEX.read_text(encoding="utf-8")

    assert 'class="navbar-actions' not in index
    assert "toolbar-action-save" not in index
    assert "toolbar-action-run" not in index
    assert "toolbar-action-scroll" not in index
    assert "toolbar-action-width" not in index


def test_workbench_v5_polishes_global_ui_surfaces():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "Workbench Refresh v5" in css
    assert "tasklist-workbench-page" in index
    assert ".tasklist-workbench-page .task-dashboard-hero" in css
    assert ".config-workbench-page .row.title::after" in css
    assert ".config-workbench-page .notify-panel-main" in css
    assert ".discovery-page-shell .discovery-search-panel" in css
    assert ".tasklist-poster-mode .discovery-poster::after" in css


def test_config_page_uses_dropdown_accordion_sections():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "Config Accordion v1" in css
    assert "refreshConfigAccordion()" in index
    assert "handleConfigAccordionClick(event)" in index
    assert "setConfigAccordionOpen(title, isOpen)" in index
    assert "config-accordion-title" in index
    assert "config-accordion-toggle" in index
    assert ".config-workbench-page .row.title.config-accordion-title" in css
    assert ".config-workbench-page .config-accordion-title.is-open" in css
    assert ".config-workbench-page .config-accordion-content[hidden]" in css
    assert ".config-workbench-page .config-accordion-toggle" in css


def test_mobile_tasklist_layout_has_clean_non_overlapping_rules():
    css = CSS.read_text(encoding="utf-8")

    assert "Mobile Tasklist Refresh v1" in css
    assert "@media (max-width: 767.98px)" in css
    assert "body:has(.tasklist-workbench-page)" in css
    assert ".navbar .navbar-brand" in css
    assert ".navbar-toggler-square" in css
    assert ".tasklist-workbench-page .task-dashboard-hero" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert ".tasklist-filter-row > [class*=\"col-\"]" in css
    assert ".tasklist-workbench-page .tasklist-header-row" in css
    assert ".tasklist-type-filter" in css
    assert ".tasklist-sort-controls" in css
    assert "overflow-x: auto" in css


def test_glass_minimal_theme_overrides_core_surfaces():
    css = CSS.read_text(encoding="utf-8")

    assert "Glass Minimal v1" in css
    assert "--qasx-glass-bg" in css
    assert "--qasx-glass-blur" in css
    assert "backdrop-filter: var(--qasx-glass-blur)" in css
    assert ".tasklist-workbench-page .task-dashboard-hero" in css
    assert ".tasklist-workbench-page .task," in css
    assert ".config-workbench-page .form-group.row" in css
    assert ".discovery-page-shell .discovery-search-panel" in css
    assert ".modal-content" in css
    assert ".table-responsive" in css
    assert "@media (max-width: 767.98px)" in css
    assert "--qasx-glass-blur: blur(8px)" in css


def test_quick_actions_toolbar_removed_for_mui_layout():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert 'class="page-toolbar d-none d-md-flex"' not in index
    assert 'class="navbar-actions' not in index
    assert "page-toolbar-btn" not in index
    assert "navbar-action-btn" not in index
    assert "toolbar-action-save" not in index
    assert "toolbar-action-run" not in index
    assert "toolbar-action-scroll" not in index
    assert "toolbar-action-width" not in index
    assert "Page Toolbar Neumorphic Bootstrap v1" not in css
    assert "Quick Actions" not in index
    assert "\u5feb\u6377\u64cd\u4f5c" not in index
    assert "\u5e38\u7528\u64cd\u4f5c\u6536\u8fdb\u9875\u9762" not in index

def test_mui_material_refresh_overrides_global_surfaces():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "MUI Material Refresh v1" in css
    assert "--mui-primary" in css
    assert "--mui-radius-xl" in css
    assert "--mui-shadow-2" in css
    assert "body" in css and "font-family" in css
    assert ".navbar" in css
    assert ".sidebar" in css
    assert ".tasklist-workbench-page .task-dashboard-hero" in css
    assert ".tasklist-workbench-page .task" in css
    assert ".tasklist-filter-row" in css
    assert ".form-control" in css
    assert ".btn" in css
    assert ".config-workbench-page .form-group.row" in css
    assert ".discovery-page-shell" in css
    assert 'class="navbar-actions' not in index
    assert "toolbar-action-save" not in index
    assert ".navbar-actions" in css and "display: none !important" in css
