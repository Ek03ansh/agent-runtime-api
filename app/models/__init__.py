from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

class TaskType(str, Enum):
    complete = "complete"
    plan = "plan"
    generate = "generate"
    run = "run"
    fix = "fix"

class TaskStatus(str, Enum):
    pending = "pending"
    initializing = "initializing"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class SignInDetails(BaseModel):
    method: Literal["none", "username-password"] = "none"
    username: Optional[str] = None
    password: Optional[str] = None

class TaskConfiguration(BaseModel):
    app_url: str = Field(..., description="Target application URL to test")
    sign_in: Optional[SignInDetails] = Field(default=None, description="Sign-in details if authentication required")
    instructions: Optional[str] = Field(default=None, description="Additional instructions for the agent")
    max_retries: Optional[int] = Field(default=3, description="Maximum number of retries for failed operations")

class TaskRequest(BaseModel):
    task_type: TaskType = Field(..., description="Type of task to execute")
    configuration: TaskConfiguration = Field(..., description="Task configuration")
    session_id: str = Field(..., description="OpenCode session ID to continue or create")

class LogEntry(BaseModel):
    agent: str = Field(..., description="Agent name that generated this log")
    model: str = Field(..., description="Model identifier used")
    command: str = Field(..., description="Command executed")
    working_directory: str = Field(..., description="Working directory")
    auth_file: str = Field(..., description="Authentication file path")
    exit_code: int = Field(..., description="Command exit code")
    stdout: str = Field(..., description="Standard output")
    stderr: str = Field(..., description="Standard error")

class SessionFile(BaseModel):
    name: str = Field(..., description="File name")
    path: str = Field(..., description="Relative path from session root")
    size: int = Field(..., description="File size in bytes")
    modified: datetime = Field(..., description="Last modified timestamp")
    type: str = Field(..., description="File type (file/directory)")

class TaskProgress(BaseModel):
    task_id: str
    status: TaskStatus
    current_phase: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Task(BaseModel):
    id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task")
    status: TaskStatus = Field(..., description="Current task status")
    current_phase: Optional[str] = Field(default=None, description="Current execution phase")
    configuration: TaskConfiguration = Field(..., description="Task configuration")
    session_path: str = Field(..., description="Path to task session directory")
    session_id: Optional[str] = Field(default=None, description="OpenCode session ID for multi-agent tasks")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    result: Optional[str] = Field(default=None, description="Task execution result summary")
    logs: List[LogEntry] = Field(default_factory=list, description="Detailed execution logs")
    debug_logs: List[str] = Field(default_factory=list, description="Real-time debug messages")

class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str = "1.0.0"
    opencode_available: bool

class TaskLogsResponse(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    logs: List[LogEntry] = Field(..., description="Detailed execution logs")
    debug_logs: List[str] = Field(..., description="Real-time debug messages")
    total_log_entries: int = Field(..., description="Total number of log entries")
    total_debug_entries: int = Field(..., description="Total number of debug entries")

class TaskListResponse(BaseModel):
    tasks: List[Task]
    total_tasks: int

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
