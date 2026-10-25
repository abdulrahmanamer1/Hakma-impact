FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HIKMA_ENV=production \
    HIKMA_DATA_DIR=/data \
    HIKMA_TRUST_PROXY=1 \
    HIKMA_COOKIE_SECURE=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    useradd --system --uid 10001 --create-home hikma && \
    mkdir -p /data/uploads && chown -R hikma:hikma /data /app

COPY --chown=hikma:hikma . /app
USER hikma

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()" || exit 1

CMD ["gunicorn", "--preload", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
