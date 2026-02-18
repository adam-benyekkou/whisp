# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

# Install dependencies to a shared location
RUN pip install --no-cache-dir -r requirements.txt --target=/opt/app-libs

# Stage 2: Final runtime image
FROM python:3.11-slim

WORKDIR /app

# Environment variables
ENV PYTHONPATH=/opt/app-libs \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy installed dependencies from builder
COPY --from=builder /opt/app-libs /opt/app-libs

# Copy application code
COPY . .

# Create non-root user and setup directories
RUN useradd -m -u 1000 whisp && \
    mkdir -p /app/data/storage && \
    chown -R whisp:whisp /app /opt/app-libs /app/data/storage

# Switch to non-root user
USER whisp

EXPOSE 8000

# Healthcheck to ensure the container is running correctly
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -m httpx get http://localhost:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
