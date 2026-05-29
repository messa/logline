FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY logline_server /src/logline_server
COPY pyproject.toml README.md /src/

RUN uv pip install --system --no-cache /src

ENTRYPOINT ["logline-server"]
