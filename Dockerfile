FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching), then copy the repo.
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir -e .[dev]
COPY . .

ENV LUXURYFORM_DB=/app/data/luxuryform.db
VOLUME /app/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
