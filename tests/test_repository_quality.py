from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_container_runs_as_non_root_with_a_healthcheck():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert dockerfile.index("USER app") < dockerfile.index('CMD ["uvicorn"')


def test_ci_runs_tests_static_checks_and_dependency_audit():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for command in ("python -m pytest", "python -m ruff check", "python -m mypy", "python -m pip_audit"):
        assert command in workflow


def test_ci_builds_the_production_container():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker build" in workflow


def test_runtime_dependency_lock_is_checked_in():
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    for package in ("boto3==", "fastapi==", "python-dotenv==", "uvicorn==", "yt-dlp=="):
        assert package in lock
