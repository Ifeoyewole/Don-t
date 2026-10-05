# ==============================================================================
# Vertex AI Custom Training Container for Pipe Joint Vision Models
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-training.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-training.txt

# Copy training module code
COPY . /app/training
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "-m", "training.task"]
