from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_uses_locked_python_and_frontend_dependencies():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "requirements.txt" not in dockerfile
    assert "COPY frontend/package.json frontend/package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile


def test_docker_build_prepares_frontend_and_static_without_migrations():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/" in dockerfile
    assert (
        "RUN python manage.py collectstatic --noinput "
        "--settings=config.settings_static"
    ) in dockerfile
    assert "manage.py migrate" not in dockerfile


def test_docker_runtime_is_non_root_wsgi_on_external_port():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]

    assert "COPY --from=python-deps /opt/venv/ /opt/venv/" in runtime
    assert "USER prolearn" in runtime
    assert "EXPOSE 8000" in runtime
    assert 'WEB_CONCURRENCY=3' in runtime
    assert (
        'CMD ["gunicorn", "config.wsgi:application", "--bind", '
        '"0.0.0.0:8000", "--access-logfile", "-", '
        '"--error-logfile", "-", "--no-control-socket"]'
    ) in runtime


def test_docker_context_excludes_secrets_and_local_build_artifacts():
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".git",
        ".env",
        ".env.*",
        ".venv",
        "frontend/node_modules",
        "frontend/dist",
        "staticfiles",
    } <= ignored
