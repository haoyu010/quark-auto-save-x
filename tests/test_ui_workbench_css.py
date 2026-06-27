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


def test_navbar_toolbar_uses_clear_modern_icons():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "Workbench toolbar polish" in css
    assert '<i class="bi bi-cloud-arrow-up"></i>' in index
    assert '<i class="bi bi-play-fill"></i>' in index
    assert '<i class="bi bi-arrow-down-up"></i>' in index


def test_workbench_v5_polishes_global_ui_surfaces():
    css = CSS.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "Workbench Refresh v5" in css
    assert "tasklist-workbench-page" in index
    assert "toolbar-action-save" in index
    assert "toolbar-action-run" in index
    assert "toolbar-action-scroll" in index
    assert "toolbar-action-width" in index
    assert ".navbar-action-btn.toolbar-action-save" in css
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
    assert ".navbar-actions" in css
    assert ".tasklist-workbench-page .task-dashboard-hero" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert ".tasklist-filter-row > [class*=\"col-\"]" in css
    assert ".tasklist-workbench-page .tasklist-header-row" in css
    assert ".tasklist-type-filter" in css
    assert ".tasklist-sort-controls" in css
    assert "overflow-x: auto" in css
