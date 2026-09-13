# syntax=docker/dockerfile:1.4
# Multi‑stage build for VOLTERRA

# ---------- Builder stage ----------
FROM python:3.11-slim AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN python -m pip install --upgrade pip setuptools wheel

# Install runtime dependencies first (caching)
COPY requirements.txt pyproject.toml ./
RUN pip install -r requirements.txt

# Copy the rest of the source code
COPY . .

# Run tests (optional, fail fast)
RUN pip install pytest && pytest --maxfail=1 --disable-warnings

# ---------- Runtime stage ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

# Create a non‑root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Copy installed packages and app code from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app .

# Expose FastAPI default port
EXPOSE 8000

# Environment variables for production
ENV PYTHONUNBUFFERED=1
ENV LOGURU_LEVEL=INFO

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
