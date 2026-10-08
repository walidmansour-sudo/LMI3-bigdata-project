FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data \
    EXPORT_DIR=/exports

WORKDIR /app

# run as a normal user, not root
RUN useradd --system --uid 1000 app && mkdir /data /exports && chown app /data /exports

COPY server.py exporter.py list_users.py export_users.py ./
COPY static ./static

USER app
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["python", "server.py"]
