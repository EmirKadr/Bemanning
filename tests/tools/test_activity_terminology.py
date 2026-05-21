from pathlib import Path

from tools.terminology_contracts import (
    TERMINOLOGY_RULES,
    forbidden_terms_in_text,
    terminology_compatibility_paths,
)


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


def iter_text_files():
    for path in SCAN_PATHS:
        if path.is_file():
            yield path
            continue
        for candidate in path.rglob("*"):
            if candidate.is_file() and candidate.suffix in TEXT_SUFFIXES:
                yield candidate


def test_terminology_rules_are_general_contracts():
    assert TERMINOLOGY_RULES
    for rule in TERMINOLOGY_RULES:
        assert rule.key
        assert rule.canonical_terms
        assert rule.forbidden_terms


def test_forbidden_terminology_only_exists_in_declared_compatibility_files():
    offenders = []
    compatibility_files = terminology_compatibility_paths()
    for path in iter_text_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        matches = forbidden_terms_in_text(text)
        if matches and relative not in compatibility_files:
            offenders.append(f"{relative}: {', '.join(matches)}")

    assert offenders == []
