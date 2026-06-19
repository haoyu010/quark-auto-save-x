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
