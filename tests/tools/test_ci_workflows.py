from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_push_ci_runs_core_test_gates_against_postgres_render_simulation():
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "postgres:16" in workflow
    assert "flow_test" in workflow
    assert "postgresql+psycopg://postgres:postgres@localhost:5432/flow_test" in workflow
    assert "alembic upgrade head" in workflow
    assert "python -m backend.seed" not in workflow
    assert "python -m pytest" in workflow
    assert "python -m playwright install --with-deps chromium" in workflow
    assert "node --check" in workflow
    assert "python desktop/main.py --smoke-test" in workflow


def test_render_production_build_does_not_run_seed():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "buildCommand:" in blueprint
    assert "alembic upgrade head" in blueprint
    assert "python -m backend.seed" not in blueprint


def test_windows_release_is_blocked_by_tests_before_packaging():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")

    assert workflow.index("Run pytest") < workflow.index("Build app package")
    assert workflow.index("Check frontend JavaScript syntax") < workflow.index("Build app package")
    assert workflow.index("Run desktop smoke test") < workflow.index("Build app package")
    assert "python -m playwright install chromium" in workflow
