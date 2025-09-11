# Use Ubuntu as base (similar to your WSL setup)
FROM ubuntu:22.04

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS (same as your WSL setup)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs

# Copy package.json and install Node dependencies
COPY ../../package.json .
RUN npm run setup:docker

# Copy requirements and create Python virtual environment
COPY ../../requirements.txt .
RUN python3 -m venv venv

# Install Python dependencies in virtual environment
RUN /app/venv/bin/pip install -r requirements.txt

# Copy application code
COPY ../../app/ ./app/
COPY ../../main.py .
COPY ../../.env.docker .env
COPY ../../opencode.json .
COPY ../../.opencode/ ./.opencode/

# Create sessions directory
RUN mkdir -p sessions

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run the app using virtual environment Python (same as your WSL setup)
CMD ["/app/venv/bin/python", "main.py"]
