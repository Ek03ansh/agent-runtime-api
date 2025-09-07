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
├── config/                   # OpenCode configuration
├── bin/                      # Binary files (opencode.exe - not in git)
├── sessions/                 # Task workspace directories (runtime)
├── main.py                   # Application entry point
├── test_agent_api.py        # Comprehensive API testing tool
├── websocket_client.py      # WebSocket streaming client
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker orchestration
└── DOCKER.md              # Docker deployment guide
```

## Quick Start

### Option 1: Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the API
python main.py

# Test all APIs
python test_agent_api.py test

# Create and monitor a task
python test_agent_api.py create complete
```

### Option 2: Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build

# Or use the PowerShell script (Windows)
./docker-build.ps1 rebuild
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

- **complete**: Full pipeline (plan → generate → run)
- **plan**: Analysis and test planning only
- **generate**: Generate tests from existing plan
- **run**: Execute existing tests
- **fix**: Debug and repair failing tests

## Configuration

The API can be configured via environment variables:

- `WORKSPACE_ROOT`: Directory for task workspaces (default: "./workspaces")
- `OPENCODE_PATH`: Path to OpenCode executable (default: "./bin/opencode.exe")
- `OPENCODE_CONFIG_PATH`: Path to OpenCode configuration file (default: "./config/opencode.json")
- `OPENCODE_PROMPTS_PATH`: Path to OpenCode prompts directory (default: "./config/.opencode")
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: "5001")
- `DEBUG`: Enable debug mode (default: "false")
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
