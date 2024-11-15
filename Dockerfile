# Build stage
FROM python:3.11-slim-bullseye AS builder

# Set work directory
WORKDIR /app

# Install system build dependencies, Tesseract, and ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
        curl \
        tesseract-ocr \
        ffmpeg \
        libsndfile1-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy pyproject.toml and poetry.lock
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# Final stage
FROM python:3.11-slim-bullseye

# Set work directory
WORKDIR /app

# Install runtime dependencies, Tesseract, and ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libsndfile1 \
        tesseract-ocr \
        ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy built artifacts from builder stage
COPY --from=builder /usr/local /usr/local

# Ensure pip and gunicorn are available
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Expose the ports
EXPOSE 8900 8800 4000

# Run the application
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.app:get_app"]