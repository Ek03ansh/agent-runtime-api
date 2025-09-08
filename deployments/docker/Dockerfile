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
    openssh-server \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH for Azure Web Apps
RUN mkdir -p /var/run/sshd \
    && echo 'root:Docker!' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/Port 22/Port 2222/' /etc/ssh/sshd_config

# Create symlinks for python/pip
RUN ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Copy requirements first for better caching
COPY ../../requirements.txt .
COPY ../../package.json .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies (including Playwright Test)
RUN npm install

# Copy application code
COPY ../../app/ ./app/
COPY ../../main.py .
COPY ../../.env.docker .env
COPY ../../opencode.json .
COPY ../../.opencode/ ./.opencode/

# Create sessions directory for the app
RUN mkdir -p sessions


# Install OpenCode globally
RUN npm install -g opencode-ai

# Verify Playwright installation (browsers are already in the base image)
RUN npx playwright --version

# Set environment variables for headless browsers
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Expose ports (5001 for app, 2222 for SSH)
EXPOSE 5001 2222

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Create startup script that runs both SSH and the app
RUN echo '#!/bin/bash\n\
service ssh start\n\
exec python main.py' > /start.sh && chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]
