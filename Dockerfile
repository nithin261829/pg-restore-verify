# pg_dump must be at least as new as the server, so build on the PostgreSQL 16 image.
FROM postgres:16-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir ".[dev]"
COPY tests ./tests
ENV PATH="/venv/bin:$PATH"
ENTRYPOINT ["pgrv"]
CMD ["serve"]
