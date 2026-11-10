FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY tools ./tools
# config is bind-mounted at /app/config (see docker-compose.yml); defaults are baked in as a fallback
COPY config /app/config
ENV CONFIG_DIR=/app/config DATA_DIR=/data TRANSCRIPTS_DIR=/data/transcripts
RUN mkdir -p /data/transcripts
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
