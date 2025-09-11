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
    HealthResponse, SessionFile, Task, TaskResponse, TaskListResponse, TaskLogsResponse, 
    TaskRequest, TaskStatus, CleanupResponse, CleanupFailures, SessionListResponse, SessionFilesResponse
)
from app.services.agent_service import agent_service
from app.services.websocket_manager import websocket_manager

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)

# Constants
EXCLUDED_DIRS = {'node_modules', '.git', '__pycache__', '.vscode', '.idea', '.opencode'}
EXCLUDED_FILES = {'opencode.json', '.gitkeep'}
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
    # Check if any excluded directory is in the path
    if any(excluded in file_path.parts for excluded in EXCLUDED_DIRS):
        return True
    
    # Check if the file name itself should be excluded
    if file_path.name in EXCLUDED_FILES:
        return True
    
    return False

@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_request: TaskRequest
) -> TaskResponse:
    """Create a new task"""
    try:
        # Create the task
        task = await agent_service.create_task(
            task_type=task_request.task_type,
            configuration=task_request.configuration,
            session_id=task_request.session_id
        )
        
        # Start execution in background using asyncio with proper task reference storage
        background_task = asyncio.create_task(agent_service.execute_task(task.id))
        
        # Store background task reference to prevent garbage collection
        if not hasattr(agent_service, '_background_tasks'):
            agent_service._background_tasks = set()
        agent_service._background_tasks.add(background_task)
        background_task.add_done_callback(agent_service._background_tasks.discard)
        
        return TaskResponse.from_task(task)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    """Get task by ID"""
    task = await agent_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_task(task)

@router.get("/tasks/{task_id}/logs", response_model=TaskLogsResponse)
async def get_task_logs(task_id: str) -> TaskLogsResponse:
    """Get detailed logs for a task"""
    task = await agent_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskLogsResponse(
        task_id=task_id,
        debug_logs=task.debug_logs,
        total_debug_entries=len(task.debug_logs)
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
            None  # No phase info needed since we use status
        )
        
        # Send existing debug logs if any
        if task.debug_logs:
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
                            None  # No phase info needed since we use status
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
        tasks=[TaskResponse.from_task(task) for task in tasks],
        total_tasks=len(tasks)
    )

@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str) -> TaskResponse:
    """Cancel a running task"""
    success = await agent_service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = await agent_service.get_task(task_id)
    return TaskResponse.from_task(task)

@router.delete("/cleanup/all", response_model=CleanupResponse, status_code=200)
async def cleanup_all_sessions() -> CleanupResponse:
    """Delete all sessions, tasks, and associated storage (development/maintenance endpoint)"""
    try:
        # Get count before cleanup for response
        session_root = settings.session_root
        session_count = 0
        
        # Count sessions
        for app_dir in session_root.glob("app-*"):
            if app_dir.is_dir():
                for session_dir in app_dir.iterdir():
                    if session_dir.is_dir():
                        session_count += 1
        
        # Clean up via agent service with verification
        deleted_sessions, deleted_tasks, deleted_opencode_storage, failures = await agent_service.cleanup_all_sessions()
        
        # Determine if cleanup was fully successful
        has_failures = (len(failures['session_failures']) > 0 or 
                       len(failures['app_failures']) > 0 or 
                       failures['opencode_failure'])
        
        success_message = "All sessions and storage cleaned up successfully"
        if has_failures:
            success_message = "Cleanup completed with some failures - see details below"
        
        # Create failure details if any occurred
        failure_details = None
        if has_failures:
            failure_details = CleanupFailures(
                failed_session_deletions=failures['session_failures'],
                failed_app_deletions=failures['app_failures'], 
                opencode_deletion_failed=failures['opencode_failure'],
                total_failures=len(failures['session_failures']) + len(failures['app_failures']) + (1 if failures['opencode_failure'] else 0)
            )
        
        return CleanupResponse(
            message=success_message,
            deleted_sessions=deleted_sessions,
            deleted_tasks=deleted_tasks, 
            deleted_opencode_storage=deleted_opencode_storage,
            total_session_directories=session_count,
            success=not has_failures,
            failures=failure_details
        )
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Session management endpoints
@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions() -> SessionListResponse:
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
    
    session_list = sorted(list(sessions))
    return SessionListResponse(
        sessions=session_list,
        total_sessions=len(session_list)
    )

@router.get("/sessions/{session_id}/files", response_model=SessionFilesResponse)
async def get_session_files(session_id: str) -> SessionFilesResponse:
    """Get files in session by session ID"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    files = []
    try:
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
                    # Skip files we can't access
                    logger.debug(f"Skipping file due to access error: {file_path}")
                    continue
    except (OSError, PermissionError) as e:
        logger.error(f"Error listing session files in {session_path}: {e}")
    
    return SessionFilesResponse(
        files=files,
        total_files=len(files),
        session_id=session_id
    )

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
