# Agent Runtime API

FastAPI-based Agent Runtime API with WebSocket streaming support - orchestrates AI agents for automated test generation with real-time monitoring capabilities.

## Features

- 🚀 **FastAPI-based REST API** - Modern, fast, and async web framework
- 🔌 **WebSocket Streaming** - Real-time task monitoring and debug messages  
- 🤖 **AI Agent Orchestration** - Coordinates multiple specialized testing agents
- 🐳 **Docker Ready** - Complete containerization with docker-compose
- 📊 **Comprehensive Testing** - Built-in API testing and monitoring tools
- 🏥 **Health Monitoring** - Built-in health checks and status endpoints

## Project Structure

```
├── app/
│   ├── controllers/           # API route handlers
│   │   └── task_controller.py      # Task management + WebSocket endpoints
│   ├── core/                 # Core configuration and settings
│   │   └── config.py              # Application configuration
│   ├── models/               # Pydantic models and schemas
│   │   └── __init__.py            # Task, WebSocket, Configuration models
│   ├── services/             # Business logic layer
│   │   ├── agent_service.py       # Agent orchestration with streaming
│   │   └── websocket_manager.py   # WebSocket connection management
│   └── utils/                # Utility functions
│       └── helpers.py             # Common helper functions
├── sessions/                 # Task workspace directories (runtime)
├── main.py                   # Application entry point
├── setup_check.py           # Setup verification script
├── test_agent_api.py        # Comprehensive API testing tool
├── websocket_client.py      # WebSocket streaming client
├── requirements.txt         # Python dependencies
├── package.json            # Node.js dependencies and scripts
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker orchestration
├── DEVELOPMENT.md          # Development setup guide
└── DOCKER.md              # Docker deployment guide
```

## Prerequisites

Before running the Agent Runtime API, you need to install OpenCode:

### Install OpenCode

Choose one of the following methods:

```bash
# Recommended: Using npm setup script
npm run setup

# Manual installation with npm
npm install -g opencode-ai

# Other package managers  
npm run setup:bun    # Uses bun
npm run setup:pnpm   # Uses pnpm  
npm run setup:yarn   # Uses yarn

# Homebrew (Linux)
brew install sst/tap/opencode

# Install script
curl -fsSL https://opencode.ai/install | bash
```

Verify the installation:
```bash
npm run verify
# or
opencode --version
```

### Setup Verification

Run the comprehensive setup check:
```bash
npm run check
# or  
python setup_check.py
```

This will verify:
- ✅ Python dependencies are installed
- ✅ OpenCode is accessible 
- ✅ Configuration is valid
- ✅ OpenCode config file exists

> **📚 For detailed setup instructions, see [DEVELOPMENT.md](DEVELOPMENT.md)**

## Quick Start

### Option 1: Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the API
npm run dev
# or
python main.py

# Test all APIs
npm run test
# or
python test_agent_api.py test

# Create and monitor a task
npm run test:create
# or
python test_agent_api.py create complete
```

### Option 2: Docker Deployment

#### Quick Deployment (Linux)
```bash
# Deploy script
./deploy.sh

# Manual Docker commands
docker build -t agent-runtime-api .
docker run -d --name agent-runtime-api -p 5001:5001 agent-runtime-api
```

#### Production Deployment
```bash
# Build production image
docker build -t agent-runtime-api:prod .

# Run with environment variables
docker run -d \
  --name agent-runtime-api-prod \
  -p 5001:5001 \
  -e DEBUG=false \
  -e CORS_ORIGINS="https://yourdomain.com" \
  --restart unless-stopped \
  agent-runtime-api:prod
```

#### Docker Compose (Alternative)
```bash
# Build and run with Docker Compose
docker-compose up --build

# Production mode
docker-compose -f docker-compose.prod.yml up --build
```

## API Testing Tool

The `test_agent_api.py` script provides comprehensive testing capabilities:

```bash
# Test all API endpoints
python test_agent_api.py test

# Create a task and monitor progress
python test_agent_api.py create complete

# Interactive mode with all options
python test_agent_api.py interactive

# Monitor existing task
python test_agent_api.py monitor <task_id>

# View task logs
python test_agent_api.py logs <task_id>

# Get help
python test_agent_api.py help
```

The API will be available at:
- **API**: http://localhost:5001
- **Swagger Docs**: http://localhost:5001/docs
- **ReDoc**: http://localhost:5001/redoc

## Endpoints

### Tasks
- `POST /tasks` - Create new task
- `GET /tasks/{task_id}` - Get task status
- `GET /tasks/{task_id}/logs` - Get task execution logs
- `GET /tasks` - List all tasks
- `POST /tasks/{task_id}/cancel` - Cancel task
- `GET /tasks/{task_id}/session/files` - List session files

### System
- `GET /health` - Health check
- `GET /` - API information

## Task Types

- **complete**: Full pipeline (plan → generate → fix)
- **plan**: Analysis and test planning only
- **generate**: Generate tests from existing plan
- **fix**: Debug and repair failing tests
- **custom**: Execute direct user instructions (for iterative workflows)

## Configuration

The API can be configured via environment variables:

- `WORKSPACE_ROOT`: Directory for task workspaces (default: "./workspaces")
- `OPENCODE_COMMAND`: OpenCode command (default: "opencode")
- `OPENCODE_CONFIG_PATH`: Path to OpenCode configuration file (default: "./opencode.json")
- `OPENCODE_DIR`: Path to OpenCode directory containing prompts and agents (default: "./.opencode")
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: "5001")
- `CORS_ORIGINS`: Allowed CORS origins (default: "*")

## Example Usage

```python
import requests
import json

# Create a task
task_request = {
    "task_type": "complete",
    "configuration": {
        "app_url": "https://example.com",
        "instructions": "Focus on login and checkout flows"
    }
}

response = requests.post("http://localhost:5001/tasks", json=task_request)
task = response.json()

print(f"Task created: {task['id']}")
print(f"Status: {task['status']}")
```

## Monitoring Task Progress

Monitor task status using simple polling:

```javascript
// JavaScript polling example
async function monitorTask(taskId) {
    const checkStatus = async () => {
        try {
            const response = await fetch(`http://localhost:5001/tasks/${taskId}`);
            const task = await response.json();
            
            console.log(`Status: ${task.status}`);
            console.log(`Phase: ${task.current_phase || 'N/A'}`);
            
            // Update UI
            updateTaskUI(task);
            
            // Stop polling if task is complete
            if (['completed', 'failed', 'cancelled'].includes(task.status)) {
                console.log('Task finished!');
                return;
            }
            
            // Poll again in 5 seconds
            setTimeout(checkStatus, 5000);
        } catch (error) {
            console.error('Error checking task status:', error);
        }
    };
    
    checkStatus(); // Start polling
}
```

```python
# Python polling example
import time
import requests

def monitor_task(task_id):
    while True:
        try:
            response = requests.get(f"http://localhost:5001/tasks/{task_id}")
            task = response.json()
            
            print(f"Status: {task['status']}")
            print(f"Phase: {task.get('current_phase', 'N/A')}")
            
            if task['status'] in ['completed', 'failed', 'cancelled']:
                print("Task finished!")
                break
                
            time.sleep(5)  # Wait 5 seconds before next check
        except Exception as e:
            print(f"Error: {e}")
            break
```

## Development

The application uses modern Python patterns:

- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Pydantic**: Data validation using Python type annotations
- **Async/Await**: Asynchronous request handling for better performance
- **Type Hints**: Full type annotation for better code quality
- **Clean Architecture**: Separation of concerns with proper layering

## Workspace Structure

Each task creates an isolated workspace:
```
workspaces/
└── {task_id}/
    ├── opencode.json       # Task configuration
    ├── specs/              # Test plans (markdown)
    ├── tests/              # Generated test files
    └── artifacts/          # Videos, traces, screenshots
```
