FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# gcc/python3-dev are often needed for compiling scientific packages (numpy, pandas, arch)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry==1.7.1

# Copy project files
COPY pyproject.toml poetry.lock ./

# Install dependencies
# We assume lock file exists. If not, remove poetry.lock from COPY and use 'poetry update'
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --without dev

# Copy source code
COPY . .

# Install the app itself (if needed, or just run from source)
# RUN poetry install --no-interaction --no-ansi --only-main

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV PYTHONPATH=/app/src

# Create data directory
RUN mkdir -p /data /app/logs

# Run the application
CMD ["python", "src/app/main.py"]
