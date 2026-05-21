import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCAN_PATHS = [
    ROOT / "app" / "backend",
    ROOT / "app" / "frontend",
    ROOT / "app" / "alembic" / "versions",
    ROOT / "tools",
    ROOT / "API_ROUTES.md",
    ROOT / "APP_MIGRATION_PLAN.md",
    ROOT / "TESTPROTOCOL.md",
]

TEXT_SUFFIXES = {".css", ".html", ".js", ".md", ".py"}
LEGACY_ACTIVITY_TERMS = re.compile(
    r"\b(stallen|stallenImport)\b|stallen\.html|"
    r"\b(Ställen|Ställe|ställen|ställe|stället|Huvudställe|huvudställe|huvudstalle)\b"
)

LEGACY_COMPATIBILITY_FILES = {
    "app/alembic/versions/0017_rename_activity_view_ids.py",
    "app/backend/main.py",
    "app/backend/routers/activities.py",
    "app/backend/routers/persons.py",
    "app/backend/user_access.py",
    "app/frontend/js/common.js",
    "app/frontend/stallen.html",
}


def iter_text_files():
    for path in SCAN_PATHS:
        if path.is_file():
            yield path
            continue
        for candidate in path.rglob("*"):
            if candidate.is_file() and candidate.suffix in TEXT_SUFFIXES:
                yield candidate


def test_legacy_stallen_terms_only_exist_as_compatibility_aliases():
    offenders = []
    for path in iter_text_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if LEGACY_ACTIVITY_TERMS.search(text) and relative not in LEGACY_COMPATIBILITY_FILES:
            offenders.append(relative)

    assert offenders == []
