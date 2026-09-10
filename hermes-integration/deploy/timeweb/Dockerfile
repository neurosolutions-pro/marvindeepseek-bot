FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 hermes

COPY deploy/timeweb/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hermes_server.py /app/hermes_server.py
COPY hermes.config.example.yaml /app/hermes.config.yaml
RUN mkdir -p /app/logs && chown -R hermes:hermes /app

USER hermes
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -sf http://127.0.0.1:8000/health || exit 1

CMD ["python", "hermes_server.py"]
