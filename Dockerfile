# ACE Server - Stripe Webhook Handler
# Schema is inlined in ace_server.py (no external schema.sql needed)
# Build timestamp: 2026-03-28T03:33:00Z

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create data directory for database
RUN mkdir -p /data && chmod 755 /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ace_server.py .
COPY package_generator.py .
COPY success.html .
COPY mcp/ ./mcp/
COPY api/ ./api/
COPY middleware/ ./middleware/

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Force rebuild timestamp: 2026-03-28T05:30:00Z - NEW IMAGE REQUIRED
CMD ["python", "-m", "uvicorn", "ace_server:app", "--host", "0.0.0.0", "--port", "8080"]
