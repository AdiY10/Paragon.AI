FROM python:3.12-slim-bookworm AS builder
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.13.1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-python-downloads

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgdal32 libgeos-c1v5 libpq5 && rm -rf /var/lib/apt/lists/*
RUN groupadd --system paragon && useradd --system --gid paragon --home-dir /app paragon
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=paragon:paragon backend ./backend
COPY --chown=paragon:paragon infra ./infra
COPY --chown=paragon:paragon config ./config
COPY --chown=paragon:paragon data/seed ./data/seed
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.production
USER paragon
EXPOSE 8000
CMD ["gunicorn", "--config", "infra/gunicorn.conf.py", "config.wsgi:application"]
