# Use Ubuntu as base (similar to your WSL setup)
FROM ubuntu:22.04


# Set non-interactive mode for apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (no nodejs/npm here)
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3.11-distutils python3-pip \
    curl git build-essential \
    wget ca-certificates gnupg \
    fonts-liberation fonts-unifont fonts-ubuntu \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libxcomposite1 \
    libxdamage1 libxrandr2 xdg-utils libu2f-udev libvulkan1 \
    libxshmfence1 libxfixes3 libxext6 libxi6 libxrender1 libxtst6 \
    libnss3-tools libxss1 libxcb1 libx11-6 libfontconfig1 \
    supervisor nginx \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
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
COPY ../../app/launch_chromium.sh ./launch_chromium.sh
COPY ../../app/wait_for_cdp_and_start_mcp.sh ./wait_for_cdp_and_start_mcp.sh
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

    
# Install Playwright and browsers (Chromium + deps) and also Chrome channel
RUN pip install playwright && playwright install --with-deps chromium
RUN npm i -g @playwright/mcp@next @playwright/test@next

    # Set environment for MCP Playwright server to be local SSE
ENV PLAYWRIGHT_MCP_SSE_URL="http://127.0.0.1:8931/sse"
ENV NODE_PATH="/usr/local/lib/node_modules:/usr/lib/node_modules"

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Start all services
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
