from pathlib import Path
from typing import Optional, Union


DEFAULT_VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_ROOT / "VERSION"


def _clean(value: Optional[object]) -> str:
    return str(value or "").strip()


def read_project_version(
    version_file: Union[str, Path] = VERSION_FILE,
    default: str = DEFAULT_VERSION,
) -> str:
    try:
        version = Path(version_file).read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return version or default


def resolve_app_version(
    build_tag: Optional[str] = None,
    build_sha: Optional[str] = None,
    app_version: Optional[str] = None,
    version_file: Union[str, Path] = VERSION_FILE,
    default: str = DEFAULT_VERSION,
) -> str:
    tag = _clean(build_tag)
    sha = _clean(build_sha)
    explicit_version = _clean(app_version)

    if tag:
        if tag.startswith("v"):
            return tag
        return f"{tag}({sha[:7]})" if sha else tag

    if explicit_version:
        return explicit_version

    version = read_project_version(version_file, default)
    return f"{version}({sha[:7]})" if sha else version
