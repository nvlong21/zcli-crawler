# --- Builder Stage ---
# Use the target Python version passed as build argument
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim as builder

# Set environment variables for Python and Poetry
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_HOME="/opt/poetry"
# Pin poetry version for consistency
ENV POETRY_VERSION=1.8.3 
ENV POETRY_NO_INTERACTION=1
# Install globally within the image stage
ENV POETRY_VIRTUALENVS_CREATE=false 
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install build dependencies (if needed, e.g., for psycopg2 or C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl ffmpeg\
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION} && poetry --version

WORKDIR /app

# Copy only dependency definition files first to leverage Docker cache layer
COPY poetry.lock pyproject.toml ./

# Install production dependencies using Poetry
# --no-root: Don't install the project package itself yet
RUN poetry install --only main --no-root --sync
# Using --sync ensures the environment matches the lock file exactly
CMD ["python"]

# --- Runtime Stage ---
FROM python:${PYTHON_VERSION}-slim as runtime

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Default environment for the container
ENV ENVIRONMENT=production 
# Module path for Uvicorn/Gunicorn
ENV APP_MODULE="presentation.main:app" 
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHON_VERSION=3.12
# Set PYTHONPATH=/app if imports fail, but non-src layout should work without it
# ENV PYTHONPATH=/app

WORKDIR /app

# Install runtime system dependencies (e.g., libpq5 for psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     libpq5 \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy installed Python dependencies from the builder stage's site-packages
# Use VIRTUAL_ENV set by Poetry (might need adjustment based on Poetry version/config)
# Default location within standard python images:
COPY --from=builder /usr/local/lib/python${PYTHON_VERSION}/site-packages /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/celery /usr/local/bin/celery
# COPY --from=builder /usr/lib/x86_64-linux-gnu/libavdevice.so.59.7.100 /usr/lib/x86_64-linux-gnu/libavdevice.so.59.7.100
# COPY --from=builder /usr/lib/x86_64-linux-gnu/libavdevice.so.59.7.100 /usr/lib/x86_64-linux-gnu/libavdevice.so.59.7.100
# RUN ln -s /usr/lib/x86_64-linux-gnu/libavdevice.so.59.7.100 /usr/lib/x86_64-linux-gnu/libavdevice.so.59 && \
#     ln -s /usr/lib/x86_64-linux-gnu/libavdevice.so.59 /usr/lib/x86_64-linux-gnu/libavdevice.so
# Copy Poetry scripts if any dependencies install them globally (less common)
# COPY --from=builder /opt/poetry/bin /usr/local/bin
RUN apt-get update && apt-get install -y --no-install-recommends \
     ffmpeg nodejs npm
# Create a non-root user and group for security
RUN addgroup --system app && adduser --system --ingroup app app

# Copy the application code into the image (after dependencies)
# Copying with context '.' assumes Docker build runs from project root
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE ${PORT}

# Basic healthcheck (adjust endpoint and command as needed)
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD curl --fail http://localhost:${PORT}/health || exit 1

# Command to run the application
# Option 1: Uvicorn directly (simpler, less robust for high traffic)
CMD ["uvicorn", "${APP_MODULE}", "--host", "${HOST}", "--port", "${PORT}"]

# Option 2: Gunicorn with Uvicorn workers (Recommended for production)
# Requires 'gunicorn' to be added as a dependency in pyproject.toml
# Adjust worker count based on resources (e.g., 2 * num_cores + 1)
# CMD ["gunicorn", "--bind", "${HOST}:${PORT}", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "${APP_MODULE}"]

