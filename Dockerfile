# Stage 1: Builder
FROM python:3.11-slim AS builder
WORKDIR /app

RUN pip install uv

# Copy dependency files only
COPY pyproject.toml .
COPY uv.lock .

# Export dependencies excluding the project itself
# --no-emit-project prevents the editable self-install line
RUN uv export --no-dev --no-emit-project --no-hashes > requirements.txt

# Install dependencies to a prefix directory
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Create required directories
RUN mkdir -p mlflow_tracking

# Environment
ENV PYTHONPATH=/app
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV LOG_LEVEL=INFO
ENV COGNEE_SKIP_CONNECTION_TEST=true

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
