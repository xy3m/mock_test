# QueueStorm Warmup Classifier - production image.
# No secrets are baked in. Pass the API key and PORT at runtime.

FROM python:3.11-slim

# Don't write .pyc files and don't buffer stdout/stderr (better logs on Render).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached when only source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the rest of the source.
COPY . .

EXPOSE 8000

# Render sets $PORT; fall back to 8000 for local docker runs.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]