FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy demo code into image
COPY ./demo /app

# Install system deps and Python deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV PORT=8080

# Default command
CMD ["gunicorn", "demo.app:app", "-b", "0.0.0.0:8080", "--workers", "2"]
