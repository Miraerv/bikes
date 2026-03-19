# ---------- Build stage ----------
FROM python:3.14-slim AS builder

WORKDIR /app

# Install build dependencies (gcc + python dev headers for asyncmy/Cython)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies FIRST (cached if pyproject.toml unchanged)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---------- Runtime stage ----------
FROM python:3.14-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (changes here do NOT re-run pip install)
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

CMD ["python", "-m", "app"]
