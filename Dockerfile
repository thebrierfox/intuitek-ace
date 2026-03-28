# WEBHOOK HANDLER DOCKERFILE
# This file copies ace_server.py which contains the POST /stripe/webhook endpoint
# Last updated: 2026-03-27T22:22Z

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# THE ACE SERVER WITH WEBHOOK HANDLER
COPY ace_server.py .

COPY package_generator.py .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost:8080/health || exit 1

# Run ace_server (NOT main.py)
CMD ["uvicorn", "ace_server:app", "--host", "0.0.0.0", "--port", "8080"]
