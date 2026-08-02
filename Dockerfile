FROM python:3.11-slim

WORKDIR /app

# Operator-selectable package index (default: PyPI). Override at build time
# without editing this file:
#   docker compose build --build-arg PIP_INDEX_URL=https://your.mirror/simple
# No mirror is recommended in operator docs: mirror coverage varies by
# location and package version (operator mirror test, Addis Ababa,
# 2026-08-02 — a mirror that works in one place failed there).
ARG PIP_INDEX_URL=https://pypi.org/simple

# Layered installs, heaviest and most stable first, so Docker's layer cache
# protects completed downloads: a dropped connection now costs ONE layer,
# not the whole build (the operator's single-transaction build failed twice
# at ~21 minutes on a ~320 kB/s line, 2026-08-01/02).
# If a build drops mid-layer, simply re-run the same command — finished
# layers are NOT downloaded again.
#
# Pins here MUST match pyproject.toml exactly — enforced by
# tests/test_docker_pins.py.

# Layer 1: OCCT kernel (~300 MB wheel — the long pole)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    cadquery-ocp-novtk==7.9.3.1.1

# Layer 2: scientific stack (hard requirements of build123d 0.11.1, ~100 MB)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    numpy==2.4.6 scipy==1.17.1 scikit-learn==1.9.0

# Layer 3: geometry kernel + mesh validation (plus build123d's remaining
# small deps: sympy, ipython, ezdxf, lib3mf, etc.)
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    build123d==0.11.1 trimesh==5.0.0

# Layer 4: Phase 1 backend deps
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url ${PIP_INDEX_URL} \
    fastapi==0.115.6 "uvicorn[standard]==0.32.1" sqlalchemy==2.0.36 \
    pydantic==2.10.4 pydantic-settings==2.7.0 pyyaml==6.0.2 httpx==0.28.1 \
    anthropic==0.42.0 openai==1.59.3 pillow==11.0.0 jsonschema==4.23.0 \
    pytest==8.3.4

# Layer 5: the app itself (deps already installed above)
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir --no-deps -e .
COPY . .

ENV LUXURYFORM_DB=/app/data/luxuryform.db
VOLUME /app/data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
