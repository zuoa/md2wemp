FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app.py ./app.py
COPY templates ./templates
COPY static ./static
COPY scripts ./scripts
COPY README.md ./README.md

RUN mkdir -p /app/data/shares /app/instance \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5566

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import sys, urllib.request; urllib.request.urlopen('http://127.0.0.1:5566/api/health', timeout=3); sys.exit(0)"

CMD ["gunicorn", "--bind", "0.0.0.0:5566", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
