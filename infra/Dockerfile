FROM python:3.13.1-slim@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f
WORKDIR /workspace
COPY backend/requirements.lock.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV PYTHONPATH=/workspace/backend
COPY backend /workspace/backend
CMD ["celery", "-A", "app.tasks.worker:celery", "worker", "--loglevel=INFO", "--concurrency=1"]
