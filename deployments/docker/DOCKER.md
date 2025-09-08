# Docker Deployment Guide

## Quick Start

### 1. Build and Run with Docker Compose (Recommended)
```bash
# Build and start the container
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### 2. Using PowerShell Script (Windows)
```powershell
# Make script executable and build
./docker-build.ps1 build

# Start the container
./docker-build.ps1 start

# View logs
./docker-build.ps1 logs

# Stop the container
./docker-build.ps1 stop

# Rebuild and restart
./docker-build.ps1 rebuild
```

### 3. Manual Docker Commands
```bash
# Build the image
docker build -t agent-runtime-api:latest .

# Run the container
docker run -d \
  --name agent-runtime-api \
  -p 5001:5001 \
  -v agent-sessions:/app/sessions \
  -v agent-workspaces:/app/workspaces \
  agent-runtime-api:latest

# Check container status
docker ps

# View logs
docker logs -f agent-runtime-api

# Stop and remove
docker stop agent-runtime-api
docker rm agent-runtime-api
```

## Environment Variables

The following environment variables can be configured:

- `PYTHONPATH`: Python module path (default: `/app`)
- `PYTHONUNBUFFERED`: Disable Python output buffering (default: `1`)
- `NODE_ENV`: Node.js environment (default: `production`)

## Volumes

The container uses the following volumes for persistence:

- `agent-sessions:/app/sessions` - WebSocket and task session data
- `agent-workspaces:/app/workspaces` - OpenCode workspace files
- `agent-logs:/app/logs` - Application logs

## Health Check

The container includes a health check that verifies the API is responding:
- **Endpoint**: `http://localhost:5001/health`
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3

## Resource Limits

Default resource limits (configurable in docker-compose.yml):
- **CPU**: 2.0 cores
- **Memory**: 2GB limit, 512MB reserved

## Development Mode

For development, you can mount your local code:

```yaml
# Uncomment these lines in docker-compose.yml
volumes:
  - ./app:/app/app
  - ./main.py:/app/main.py
```

## Troubleshooting

### Check Container Logs
```bash
docker-compose logs agent-runtime-api
```

### Access Container Shell
```bash
docker-compose exec agent-runtime-api bash
```

### Rebuild Without Cache
```bash
docker-compose build --no-cache
```

### Check API Health
```bash
curl http://localhost:5001/health
```

## Production Deployment

For production deployment:

1. Remove development volume mounts from `docker-compose.yml`
2. Configure proper environment variables
3. Set up SSL termination (nginx configuration example included)
4. Configure log rotation
5. Set up monitoring and alerting

## Security Considerations

- The container runs as a non-root user for security
- Environment files (`.env`) are excluded from the Docker image
- Only necessary ports are exposed
- Resource limits prevent resource exhaustion
