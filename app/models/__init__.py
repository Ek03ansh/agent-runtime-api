from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

class TaskType(str, Enum):
    complete = "complete"
    plan = "plan"
    generate = "generate"
    fix = "fix"
    custom = "custom"

class TaskStatus(str, Enum):
    pending = "pending"
    initializing = "initializing"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class TaskPhase(str, Enum):
    planning = "planning"
    generating_tests = "generating_tests"
    fixing_tests = "fixing_tests"

class SignInMethod(str, Enum):
    none = "none"
    username_password = "username-password"

class SignInDetails(BaseModel):
    method: SignInMethod = SignInMethod.none
    username: Optional[str] = None
    password: Optional[str] = None

class ArtifactsUrl(BaseModel):
    sas_url: str = Field(..., description="SAS URL for Azure Storage container with write permissions")

class UploadedArtifacts(BaseModel):
    blob_url: str = Field(..., description="Direct URL to the uploaded ZIP file in Azure Storage")
    blob_name: str = Field(..., description="Name of the uploaded blob/file")
    uploaded_at: datetime = Field(..., description="Timestamp when upload completed")
    file_size: int = Field(..., description="Size of uploaded file in bytes")

class TaskConfiguration(BaseModel):
    app_url: str = Field(..., description="Target application URL to test")
    sign_in: Optional[SignInDetails] = Field(default=None, description="Sign-in details if authentication required")
    instructions: Optional[str] = Field(default=None, description="Additional instructions for the agent")

class TaskRequest(BaseModel):
    task_type: TaskType = Field(..., description="Type of task to execute")
    configuration: TaskConfiguration = Field(..., description="Task configuration")
    session_id: str = Field(..., description="OpenCode session ID to continue or create")
    artifacts_url: Optional[ArtifactsUrl] = Field(default=None, description="Azure Storage SAS URL for artifacts upload")

class SessionFile(BaseModel):
    name: str = Field(..., description="File name")
    path: str = Field(..., description="Relative path from session root")
    size: int = Field(..., description="File size in bytes")
    modified: datetime = Field(..., description="Last modified timestamp")
    type: str = Field(..., description="File type (file/directory)")

# Core/Internal Models
class Task(BaseModel):
    """Core Task model for internal use"""
    id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(..., description="Current task status")
    current_phase: TaskPhase = Field(default=TaskPhase.planning, description="Current execution phase")
    current_activity: Optional[str] = Field(default=None, description="Current user-friendly activity description")
    configuration: TaskConfiguration = Field(..., description="Task configuration")
    session_path: str = Field(..., description="Path to task session directory")
    session_id: str = Field(..., description="OpenCode session ID for multi-agent tasks")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp")
    artifacts_url: Optional[ArtifactsUrl] = Field(default=None, description="Azure Storage SAS URL for artifacts")
    uploaded_artifacts: Optional[UploadedArtifacts] = Field(default=None, description="Details of uploaded artifacts")
    
    # Internal tracking fields (not exposed in API responses)
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    debug_logs: List[str] = Field(default_factory=list, description="Real-time debug messages")

# API Response Models
class TaskResponse(BaseModel):
    """Clean task response for API endpoints"""
    id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(..., description="Current task status")
    current_phase: TaskPhase = Field(..., description="Current execution phase")
    current_activity: Optional[str] = Field(default=None, description="Current user-friendly activity description")
    configuration: TaskConfiguration = Field(..., description="Task configuration")
    session_path: str = Field(..., description="Path to task session directory")
    session_id: str = Field(..., description="OpenCode session ID for multi-agent tasks")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp")
    artifacts_url: Optional[ArtifactsUrl] = Field(default=None, description="Azure Storage SAS URL for artifacts")
    uploaded_artifacts: Optional[UploadedArtifacts] = Field(default=None, description="Details of uploaded artifacts")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    
    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        """Convert internal Task to API response"""
        return cls(
            id=task.id,
            task_type=task.task_type,
            status=task.status,
            current_phase=task.current_phase,
            current_activity=task.current_activity,
            configuration=task.configuration,
            session_path=task.session_path,
            session_id=task.session_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
            artifacts_url=task.artifacts_url,
            uploaded_artifacts=task.uploaded_artifacts,
            error=task.error
        )

class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str = "1.0.0"
    opencode_available: bool

class TaskLogsResponse(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    debug_logs: List[str] = Field(..., description="Real-time debug messages")
    total_debug_entries: int = Field(..., description="Total number of debug entries")

class TaskListResponse(BaseModel):
    """Response model for listing tasks"""
    tasks: List[TaskResponse] = Field(..., description="List of tasks")
    total_tasks: int = Field(..., description="Total number of tasks")

class DebugMessage(BaseModel):
    timestamp: datetime = Field(..., description="Message timestamp")
    level: str = Field(..., description="Log level (DEBUG, INFO, ERROR)")
    message: str = Field(..., description="Debug message content")
    task_id: str = Field(..., description="Associated task ID")
    agent: Optional[str] = Field(default=None, description="Agent name if applicable")

class StreamEvent(BaseModel):
    event_type: str = Field(..., description="Event type (debug, status, error, complete)")
    data: dict = Field(..., description="Event data")


# Auth Models
class AuthLoginResponse(BaseModel):
    device_code: Optional[str] = Field(None, description="Device code for GitHub authentication")
    verification_url: Optional[str] = Field(None, description="URL to complete authentication")


class AuthStatusResponse(BaseModel):
    authenticated: bool = Field(..., description="Whether user is authenticated")
    refreshToken: Optional[str] = Field(None, description="GitHub Copilot refresh token")

class AuthInjectTokenRequest(BaseModel):
    refreshToken: str = Field(..., description="GitHub Copilot refresh token to inject")

# Cleanup API Models
class CleanupFailures(BaseModel):
    failed_session_deletions: List[str] = Field(..., description="Paths of sessions that failed to delete")
    failed_app_deletions: List[str] = Field(..., description="Paths of app directories that failed to delete")
    opencode_deletion_failed: bool = Field(..., description="Whether OpenCode storage deletion failed")
    total_failures: int = Field(..., description="Total number of failures")

class CleanupResponse(BaseModel):
    message: str = Field(..., description="Cleanup result message")
    deleted_sessions: int = Field(..., description="Number of sessions successfully deleted")
    deleted_tasks: int = Field(..., description="Number of in-memory tasks cleared")
    deleted_opencode_storage: bool = Field(..., description="Whether OpenCode storage was deleted")
    total_session_directories: int = Field(..., description="Total session directories found before cleanup")
    success: bool = Field(..., description="Whether cleanup completed without failures")
    failures: Optional[CleanupFailures] = Field(default=None, description="Failure details if any occurred")

# Session API Models
class SessionListResponse(BaseModel):
    sessions: List[str] = Field(..., description="List of available session IDs")
    total_sessions: int = Field(..., description="Total number of sessions")

class SessionFilesResponse(BaseModel):
    files: List[SessionFile] = Field(..., description="List of files in the session")
    total_files: int = Field(..., description="Total number of files")
    session_id: str = Field(..., description="Session identifier")

class UploadRequest(BaseModel):
    """Request model for manual session upload"""
    sas_url: str = Field(..., description="Azure Storage SAS URL with write permissions")
