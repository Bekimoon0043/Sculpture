FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching), then copy the repo.
COPY pyproject.toml ./
COPY backend ./backend
# --retries/--timeout: the operator's connection is unreliable; a pip read
# timeout already killed one Docker build (operator report, 2026-08-01).
RUN pip install --no-cache-dir --retries 10 --timeout 120 -e .[dev]
COPY . .

ENV LUXURYFORM_DB=/app/data/luxuryform.db
VOLUME /app/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
