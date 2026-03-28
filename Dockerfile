FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ace_server.py .
COPY package_generator.py .
COPY schema.sql .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "ace_server:app", "--host", "0.0.0.0", "--port", "8080"]
