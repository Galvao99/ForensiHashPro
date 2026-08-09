ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${PYTHON_IMAGE} AS python-base

FROM rust:1.88-slim-bookworm AS rust-builder
COPY --from=python-base /usr/local /usr/local
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir "maturin>=1.9,<2.0"
WORKDIR /build
COPY rust/forensihash_core/Cargo.toml rust/forensihash_core/Cargo.lock rust/forensihash_core/pyproject.toml ./
COPY rust/forensihash_core/src/ ./src/
RUN maturin build --release --interpreter python --out /wheels

FROM python-base AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORENSIHASH_TEMP_DIR=/tmp/forensihash
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        libimage-exiftool-perl \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/forensihash
COPY requirements-web.txt ./
COPY --from=rust-builder /wheels/*.whl /tmp/wheels/
RUN python -m pip install --no-cache-dir -r requirements-web.txt /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels
COPY app/ ./app/
COPY web/ ./web/
COPY alembic.ini ./
RUN groupadd --system forensihash \
    && useradd --system --gid forensihash --home-dir /nonexistent --no-create-home forensihash \
    && install -d -o forensihash -g forensihash -m 0750 /tmp/forensihash
USER forensihash
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3).read()"]
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn web.backend.app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]

FROM runtime-base AS test
USER root
RUN python -m pip install --no-cache-dir pytest==9.1.1 httpx==0.28.1
COPY tests/ ./tests/
COPY pytest.ini ./
ENV FORENSIHASH_CONTAINER_TESTS=1
USER forensihash
RUN python --version \
    && exiftool -ver \
    && tesseract --version \
    && pdftoppm -v \
    && python -c "import forensihash_core" \
    && python -m pytest -q -p no:cacheprovider \
        web/backend/tests \
        tests/test_analysis_input_immutability.py \
        tests/test_evidence_source.py \
        tests/test_processing_reliability.py \
        tests/test_settings_and_environment.py

FROM runtime-base AS runtime
