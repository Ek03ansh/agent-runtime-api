import asyncio
import json
import logging
import mimetypes
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse

from app.core.config import settings
from app.models import (
    HealthResponse, SessionFile, Task, TaskListResponse, TaskLogsResponse, 
    TaskRequest, TaskStatus
)
from app.services.agent_service import agent_service
from app.services.websocket_manager import websocket_manager

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)

# Constants
EXCLUDED_DIRS = {'node_modules', '.git', '__pycache__', '.vscode', '.idea'}
TEXT_FILE_ENCODING = 'utf-8'

def find_session_path(session_id: str) -> Optional[Path]:
    """Find session path across all app directories"""
    session_root = settings.session_root
    
    # Search for session across all app directories
    for app_dir in session_root.glob("app-*"):
        if app_dir.is_dir():
            potential_path = app_dir / session_id
            if potential_path.exists() and potential_path.is_dir():
                return potential_path
    
    return None

def should_exclude_path(file_path: Path) -> bool:
    """Check if path should be excluded from processing"""
    return any(excluded in file_path.parts for excluded in EXCLUDED_DIRS)

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
                # Log WebSocket errors but don't expose internal details
                logger.error(f"WebSocket error for task {task_id}: {e}")
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

# Session management endpoints
@router.get("/sessions", response_model=List[str])
async def get_sessions() -> List[str]:
    """Get list of all available sessions"""
    sessions = set()
    session_root = settings.session_root
    
    # Search for sessions across all app directories
    for app_dir in session_root.glob("app-*"):
        if app_dir.is_dir():
            # Each subdirectory in app-* is a session
            for session_dir in app_dir.iterdir():
                if session_dir.is_dir():
                    sessions.add(session_dir.name)
    
    return sorted(list(sessions))

@router.get("/sessions/{session_id}/files", response_model=List[SessionFile])
async def get_session_files(session_id: str) -> List[SessionFile]:
    """Get files in session by session ID - delegates to agent service"""
    # Use existing agent_service method to avoid duplication
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Find a task with this session path to reuse agent_service logic
    for task in (await agent_service.get_all_tasks()):
        if Path(task.session_path).name == session_id:
            return await agent_service.get_session_files(task.id)
    
    # Fallback to manual file listing if no task found
    files = []
    for file_path in session_path.rglob("*"):
        if file_path.is_file() and not should_exclude_path(file_path):
            try:
                stat = file_path.stat()
                relative_path = file_path.relative_to(session_path)
                
                files.append(SessionFile(
                    name=file_path.name,
                    path=str(relative_path),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    type="file"
                ))
            except (OSError, PermissionError):
                continue
    
    return files

@router.get("/sessions/{session_id}/files/{file_path:path}")
async def download_session_file(session_id: str, file_path: str):
    """Download a specific file from session"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    full_file_path = session_path / file_path
    
    # Security check: ensure file is within session directory
    try:
        full_file_path.resolve().relative_to(session_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: file outside session directory")
    
    if not full_file_path.exists() or not full_file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type
    content_type, _ = mimetypes.guess_type(str(full_file_path))
    
    # For text files, return as plain text to display in browser
    if content_type and content_type.startswith('text/'):
        try:
            with open(full_file_path, 'r', encoding=TEXT_FILE_ENCODING) as f:
                content = f.read()
            return PlainTextResponse(content=content, media_type=content_type)
        except (UnicodeDecodeError, PermissionError):
            pass  # Fall back to file download
    
    return FileResponse(
        path=str(full_file_path),
        filename=full_file_path.name,
        media_type=content_type or 'application/octet-stream'
    )

@router.get("/sessions/{session_id}/download")
async def download_session_zip(session_id: str):
    """Download complete session folder as ZIP file"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create temporary ZIP file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    zip_path = temp_zip.name
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in session_path.rglob("*"):
                if file_path.is_file() and not should_exclude_path(file_path):
                    try:
                        relative_path = file_path.relative_to(session_path)
                        zipf.write(file_path, relative_path)
                    except (OSError, PermissionError):
                        continue
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}_{timestamp}.zip"
        
        return FileResponse(
            path=zip_path,
            filename=filename,
            media_type='application/zip'
        )
        
    except Exception as e:
        Path(zip_path).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to create ZIP: {str(e)}")

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(
        timestamp=datetime.now(),
        opencode_available=settings.opencode_available
    )
