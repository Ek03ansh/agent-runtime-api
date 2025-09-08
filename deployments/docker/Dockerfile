# Use official Playwright image that includes browsers
FROM mcr.microsoft.com/playwright:v1.47.0-jammy

# Set working directory
WORKDIR /app

# Install Node.js LTS (Playwright image has it, but ensure latest)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs

# Install Python and pip (use default Python 3.10 from Ubuntu Jammy)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python/pip
RUN ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Copy requirements first for better caching
COPY ../../requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ../../app/ ./app/
COPY ../../main.py .
COPY ../../.env.production .env
COPY ../../opencode.json .
COPY ../../.opencode/ ./.opencode/

# Create sessions directory
RUN mkdir -p sessions

# Install OpenCode globally
RUN npm install -g opencode-ai

# Set environment variables for headless browsers
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run the application
CMD ["python", "main.py"]
