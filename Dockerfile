# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.13-slim-bookworm AS python-deps

COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build/backend

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project


FROM python-deps AS backend-builder

ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY apps/ ./apps/
COPY config/ ./config/
COPY manage.py ./manage.py
COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/

# The static-only settings use Django's dummy database backend, so this build
# step collects Django/Admin files without connecting to PostgreSQL.
RUN python manage.py collectstatic --noinput --settings=config.settings_static


FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=3

WORKDIR /app

RUN addgroup --system --gid 10001 prolearn \
    && adduser --system --uid 10001 --ingroup prolearn --home /app prolearn

COPY --from=python-deps /opt/venv/ /opt/venv/
COPY --from=backend-builder --chown=prolearn:prolearn /app/apps/ ./apps/
COPY --from=backend-builder --chown=prolearn:prolearn /app/config/ ./config/
COPY --from=backend-builder --chown=prolearn:prolearn /app/manage.py ./manage.py
COPY --from=backend-builder --chown=prolearn:prolearn /app/frontend/dist/ ./frontend/dist/
COPY --from=backend-builder --chown=prolearn:prolearn /app/staticfiles/ ./staticfiles/

USER prolearn

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--no-control-socket"]
