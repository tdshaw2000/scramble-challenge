FROM python:3.12-slim

RUN pip install --no-cache-dir "uv>=0.8,<0.10"

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    FLASK_APP="app:create_app"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ app/
COPY migrations/ migrations/
COPY docker/web/entrypoint.sh /entrypoint.sh

EXPOSE 5000

CMD ["/entrypoint.sh"]
