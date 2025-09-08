from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime
import asyncio

from app.models import (
    Task, TaskRequest, TaskListResponse, TaskLogsResponse, HealthResponse,
    SessionFile, TaskStatus
)
from app.services.agent_service import agent_service
from app.services.websocket_manager import websocket_manager
from app.core.config import settings

router = APIRouter(tags=["tasks"])

@router.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task_request: TaskRequest
) -> Task:
    """Create a new task"""
    try:
        # Create the task
        task = await agent_service.create_task(
            task_type=task_request.task_type,
            configuration=task_request.configuration,
            session_id=task_request.session_id
        )
        
        # Start execution in background using asyncio
        asyncio.create_task(agent_service.execute_task(task.id))
        
        return task
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    """Get task by ID"""
    task = await agent_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks/{task_id}/logs", response_model=TaskLogsResponse)
async def get_task_logs(task_id: str) -> TaskLogsResponse:
    """Get detailed logs for a task"""
    task = await agent_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    logs = getattr(task, 'logs', [])
    debug_logs = getattr(task, 'debug_logs', [])
    return TaskLogsResponse(
        task_id=task_id,
        logs=logs,
        debug_logs=debug_logs,
        total_log_entries=len(logs),
        total_debug_entries=len(debug_logs)
    )

@router.websocket("/tasks/{task_id}/stream")
async def stream_task_logs(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task log streaming"""
    # Check if task exists
    task = await agent_service.get_task(task_id)
    if not task:
        await websocket.close(code=4004, reason="Task not found")
        return
    
    await websocket_manager.connect(websocket, task_id)
    
    try:
        # Send initial status
        await websocket_manager.send_status_update(
            task_id, 
            task.status.value, 
            task.current_phase
        )
        
        # Send existing debug logs if any
        if hasattr(task, 'debug_logs') and task.debug_logs:
            for debug_log in task.debug_logs:
                await websocket_manager.send_debug_message(
                    task_id, 
                    "DEBUG", 
                    debug_log
                )
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for client message (ping/pong or close)
                data = await websocket.receive_text()
                
                # Handle client messages if needed
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "status":
                    # Send current task status
                    current_task = await agent_service.get_task(task_id)
                    if current_task:
                        await websocket_manager.send_status_update(
                            task_id,
                            current_task.status.value,
                            current_task.current_phase
                        )
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"DEBUG: WebSocket error for task {task_id}: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket, task_id)

@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks() -> TaskListResponse:
    """List all tasks"""
    tasks = await agent_service.get_all_tasks()
    return TaskListResponse(
        tasks=tasks,
        total_tasks=len(tasks)
    )

@router.post("/tasks/{task_id}/cancel", response_model=Task)
async def cancel_task(task_id: str) -> Task:
    """Cancel a running task"""
    success = await agent_service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = await agent_service.get_task(task_id)
    return task

@router.get("/tasks/{task_id}/session/files", response_model=List[SessionFile])
async def get_session_files(task_id: str) -> List[SessionFile]:
    """Get files in task session"""
    task = await agent_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    files = await agent_service.get_session_files(task_id)
    return files

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(
        timestamp=datetime.now(),
        opencode_available=settings.opencode_available
    )

@router.get("/config")
async def get_configuration():
    """Get current API configuration"""
    return {
        "provider": settings.provider,
        "model": settings.model,
        "auth_type": settings.auth_type,
        "opencode_command": settings.opencode_command,
        "opencode_available": settings.opencode_available,
        "session_root": str(settings.session_root),
        "environment": "production" if not settings.debug else "development",
        "available_task_types": ["complete", "plan", "generate", "run", "fix"],
        "description": "Hardcoded GitHub Copilot configuration for deployment"
    }
