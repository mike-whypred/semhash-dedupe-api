# syntax=docker/dockerfile:1.6

FROM python:3.12-slim

# ---- system libs for NumPy / OpenBLAS ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libopenblas-dev && \
    rm -rf /var/lib/apt/lists/*

# ---- Python deps ----
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- your FastAPI code ----
COPY app .

# ---- run ----
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]