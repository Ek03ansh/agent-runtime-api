import asyncio
import os
import uuid
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Fix for Windows subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.models import Task, TaskType, TaskStatus, TaskConfiguration, LogEntry, SessionFile
from app.core.config import settings

# Constants
OPENCODE_TIMEOUT_SECONDS = 3600  # 1 hour
STREAM_CLEANUP_TIMEOUT_SECONDS = 5
APP_HASH_LENGTH = 12  # Characters for app workspace hash


class AgentService:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        # Import websocket_manager here to avoid circular imports
        self._websocket_manager = None
    
    @property
    def websocket_manager(self):
        """Lazy loading of websocket manager to avoid circular imports"""
        if self._websocket_manager is None:
            from app.services.websocket_manager import websocket_manager
            self._websocket_manager = websocket_manager
        return self._websocket_manager
    
    async def _send_debug(self, task_id: str, message: str, level: str = "DEBUG", agent: str = None):
        """Send debug message to WebSocket clients and store in task"""
        # Store in task debug logs
        task = self.tasks.get(task_id)
        if task:
            if not hasattr(task, 'debug_logs'):
                task.debug_logs = []
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            task.debug_logs.append(formatted_message)
        
        # Send to WebSocket clients
        try:
            await self.websocket_manager.send_debug_message(task_id, level, message, agent)
        except Exception as e:
            print(f"DEBUG: Failed to send WebSocket message: {e}")
        
        # Also print to console (existing behavior)
        print(f"DEBUG: {message}")
        
    async def create_task(self, task_type: TaskType, configuration: TaskConfiguration, session_id: str) -> Task:
        """Create a new task with specified session ID"""
        task_id = str(uuid.uuid4())
        
        # Create app-specific directory structure first
        import hashlib
        normalized_url = configuration.app_url.lower().strip().rstrip('/')
        app_hash = hashlib.sha1(normalized_url.encode()).hexdigest()[:APP_HASH_LENGTH]
        
        # Structure: sessions/app-{hash}/{session_id}
        app_path = settings.session_root / f"app-{app_hash}"
        session_path = app_path / session_id
        
        task = Task(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.pending,
            configuration=configuration,
            session_path=str(session_path),
            session_id=session_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # Create session directory under app directory
        session_path.mkdir(parents=True, exist_ok=True)
        
        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    async def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        return list(self.tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        # Update task status (note: we're using thread executor so no process to kill)
        task.status = TaskStatus.cancelled
        task.updated_at = datetime.now()
        return True
    
    async def execute_task(self, task_id: str) -> bool:
        """Execute a task using OpenCode agents"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        try:
            task.status = TaskStatus.initializing
            task.updated_at = datetime.now()
            
            # Create OpenCode configuration
            await self._create_opencode_config(task)
            
            task.status = TaskStatus.running
            task.current_phase = f"Executing {task.task_type.value} pipeline"
            task.updated_at = datetime.now()
            
            # Execute based on task type
            success, error_detail = await self._execute_opencode_pipeline(task)
            
            if success:
                task.status = TaskStatus.completed
                task.current_phase = "Completed"
                task.completed_at = datetime.now()
            else:
                task.status = TaskStatus.failed
                task.error = error_detail or "Task execution failed with unknown error"
            
            task.updated_at = datetime.now()
            return success
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            task.status = TaskStatus.failed
            task.error = f"Task execution exception: {str(e)} (Type: {type(e).__name__})\nTraceback: {tb}"
            task.updated_at = datetime.now()
            return False
    
    async def _create_opencode_config(self, task: Task):
        """Create session directory and copy essential OpenCode configuration"""
        try:
            import shutil
            from app.core.config import Settings
            settings = Settings()
            
            session_path = Path(task.session_path)
            
            # Ensure session directory exists
            session_path.mkdir(parents=True, exist_ok=True)
            
            # Copy opencode.json from config directory to session
            session_config_path = session_path / "opencode.json"
            
            if settings.opencode_config_path.exists():
                shutil.copy2(settings.opencode_config_path, session_config_path)
                print(f"DEBUG: Copied config to session: {session_config_path}")
            else:
                print(f"WARNING: OpenCode config not found at {settings.opencode_config_path}")
            
            # Copy .opencode directory from project root (standard OpenCode structure)
            project_opencode_dir = Path(".opencode")
            session_opencode_dir = session_path / ".opencode"
            
            if project_opencode_dir.exists():
                # Copy the entire .opencode directory structure
                if session_opencode_dir.exists():
                    shutil.rmtree(session_opencode_dir)  # Remove if exists
                shutil.copytree(project_opencode_dir, session_opencode_dir)
                print(f"DEBUG: Copied .opencode directory to session: {session_opencode_dir}")
            else:
                print(f"INFO: No .opencode directory found in project root - using OpenCode defaults")
            
        except Exception as e:
            raise Exception(f"Failed to create session configuration: {str(e)}")


    async def _execute_opencode_pipeline(self, task: Task) -> Tuple[bool, str]:
        """Execute the OpenCode pipeline based on task type with proper session management"""
        await self._send_debug(task.id, f"Starting _execute_opencode_pipeline for task {task.id}")
        session_path = Path(task.session_path)
        
        try:
            await self._send_debug(task.id, f"Using session path: {session_path}")
            
            # Check if session directory exists
            if not session_path.exists():
                return False, f"Session directory does not exist: {session_path}"
            
            await self._send_debug(task.id, f"Checking OpenCode command: {settings.opencode_command}")
            # Check if OpenCode command is available
            if not settings.opencode_available:
                return False, f"OpenCode command not found in PATH: {settings.opencode_command}"
            
            await self._send_debug(task.id, "Using global hardcoded GitHub Copilot authentication")
            await self._send_debug(task.id, "Global auth file will be used automatically")
            
            # Use build agent for orchestration
            primary_agent = "build"
            
            await self._send_debug(task.id, f"Using primary agent: {primary_agent}")
            
            # Execute the primary agent which will orchestrate sub-agents
            await self._send_debug(task.id, f"Starting primary agent: {primary_agent}", agent=primary_agent)
            task.current_phase = f"Running {primary_agent} (orchestrating sub-agents)"
            task.updated_at = datetime.now()
            
            # Send status update via WebSocket
            try:
                await self.websocket_manager.send_status_update(
                    task.id, 
                    task.status.value, 
                    task.current_phase
                )
            except Exception as e:
                print(f"DEBUG: Failed to send status update via WebSocket: {e}")
            
            # Create task-specific instructions using external prompt files
            app_url = task.configuration.app_url
            
            # Read the appropriate prompt file and substitute the app_url
            prompt_files = {
                TaskType.complete: ".opencode/prompts/complete-testing-workflow.md",
                TaskType.plan: ".opencode/prompts/test-planning.md", 
                TaskType.generate: ".opencode/prompts/test-generation.md",
                TaskType.run: ".opencode/prompts/test-fixing.md",
                TaskType.fix: ".opencode/prompts/test-fixing.md"
            }
            
            # Get prompt file path (all task types are mapped)
            prompt_file_path = Path(prompt_files[task.task_type])
            
            try:
                with open(prompt_file_path, 'r', encoding='utf-8') as f:
                    instructions = f.read().replace("{app_url}", app_url)
            except Exception as e:
                await self._send_debug(task.id, f"Error reading prompt file {prompt_file_path}: {e}", "WARNING")
                instructions = f"Help me test the web application at '{app_url}' using the appropriate Playwright testing workflow and specialized agents."
            
            # Add custom instructions if provided
            if task.configuration.instructions:
                instructions = f"{task.configuration.instructions}\n\n{instructions}"
            
            # Build command with hardcoded GitHub Copilot configuration
            model_identifier = f"{settings.provider}/{settings.model}"  # github-copilot/claude-sonnet-4
            
            # Use build agent for all task types with appropriate instructions
            cmd_args = [
                settings.opencode_command, 
                "run", 
                "-m", model_identifier,
                "--agent", primary_agent,
                "--log-level", "DEBUG",
                instructions
            ]
            await self._send_debug(task.id, f"Using {primary_agent} agent for {task.task_type} workflow", agent=primary_agent)
            
            # Set up environment
            env = os.environ.copy()
            
            # Execute command from session directory where OpenCode project is located
            await self._send_debug(task.id, f"About to execute command: {' '.join(cmd_args)}", agent=primary_agent)
            await self._send_debug(task.id, f"Working directory: {session_path}", agent=primary_agent)
            
            # Use thread executor to run subprocess with real-time output capture
            import concurrent.futures
            
            async def run_subprocess_with_streaming():
                """Run subprocess with real-time output streaming"""
                try:
                    await self._send_debug(task.id, "Starting OpenCode subprocess...", agent=primary_agent)
                    
                    # Create subprocess in executor
                    loop = asyncio.get_event_loop()
                    
                    def create_process():
                        return subprocess.Popen(
                            cmd_args,
                            cwd=session_path,  # Use session path as working directory
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            bufsize=1,
                        )
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        process = await loop.run_in_executor(executor, create_process)
                    
                    # Create tasks to read output streams
                    async def read_stream(stream, prefix):
                        """Read from stream and send to WebSocket"""
                        try:
                            while True:
                                line = await loop.run_in_executor(None, stream.readline)
                                if not line:
                                    break
                                line = line.strip()
                                if line:
                                    # Send to WebSocket - capture all output for better debugging
                                    await self._send_debug(task.id, f"OpenCode {prefix}: {line}", agent=primary_agent)
                        except Exception as e:
                            await self._send_debug(task.id, f"Stream reading error ({prefix}): {e}", "ERROR", agent=primary_agent)
                    
                    # Start reading both streams concurrently
                    stdout_task = asyncio.create_task(read_stream(process.stdout, "STDOUT"))
                    stderr_task = asyncio.create_task(read_stream(process.stderr, "STDERR"))
                    
                    # Wait for process completion with timeout
                    try:
                        await asyncio.wait_for(
                            loop.run_in_executor(None, process.wait), 
                            timeout=OPENCODE_TIMEOUT_SECONDS
                        )
                        returncode = process.returncode
                    except asyncio.TimeoutError:
                        await self._send_debug(task.id, "OpenCode process timed out after 15 minutes, killing...", "ERROR", agent=primary_agent)
                        process.kill()
                        returncode = -1
                    
                    # Give stream reading tasks time to finish before canceling
                    try:
                        await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task, return_exceptions=True), timeout=STREAM_CLEANUP_TIMEOUT_SECONDS)
                    except asyncio.TimeoutError:
                        await self._send_debug(task.id, "Stream reading timeout, canceling tasks", "WARNING", agent=primary_agent)
                        stdout_task.cancel()
                        stderr_task.cancel()
                    
                    # Collect any remaining output
                    stdout_remaining = ""
                    stderr_remaining = ""
                    try:
                        if process.stdout:
                            stdout_remaining = process.stdout.read() or ""
                            if stdout_remaining.strip():
                                await self._send_debug(task.id, f"OpenCode STDOUT (final): {stdout_remaining.strip()}", agent=primary_agent)
                        if process.stderr:
                            stderr_remaining = process.stderr.read() or ""
                            if stderr_remaining.strip():
                                await self._send_debug(task.id, f"OpenCode STDERR (final): {stderr_remaining.strip()}", agent=primary_agent)
                    except Exception as e:
                        await self._send_debug(task.id, f"Error reading final output: {e}", "WARNING", agent=primary_agent)
                    
                    # Close streams
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    
                    await self._send_debug(task.id, f"OpenCode completed with exit code: {returncode}", agent=primary_agent)
                    return returncode, stdout_remaining, stderr_remaining
                    
                except Exception as e:
                    await self._send_debug(task.id, f"Exception in subprocess: {e}", "ERROR", agent=primary_agent)
                    return -2, "", f"Failed to run subprocess: {e}"
            
            try:
                await self._send_debug(task.id, "Running subprocess with streaming", agent=primary_agent)
                returncode, stdout, stderr = await run_subprocess_with_streaming()
                
                await self._send_debug(task.id, f"Subprocess completed, exit code: {returncode}", agent=primary_agent)
                
            except Exception as e:
                await self._send_debug(task.id, f"Exception during subprocess execution: {e}", "ERROR", agent=primary_agent)
                raise
            
            # Store the output for debugging
            auth_file_info = "Global hardcoded GitHub Copilot auth"
            log_entry = LogEntry(
                agent=primary_agent,
                model=model_identifier,
                command=' '.join(cmd_args),
                working_directory=str(session_path),
                auth_file=auth_file_info,
                exit_code=returncode,
                stdout=stdout.strip() if stdout else "",
                stderr=stderr.strip() if stderr else ""
            )
            
            # Store logs in task for retrieval
            if not hasattr(task, 'logs'):
                task.logs = []
            task.logs.append(log_entry)
            
            if returncode != 0:
                error_msg = f"Agent '{primary_agent}' failed with exit code {returncode}\n"
                error_msg += f"Command: {' '.join(cmd_args)}\n"
                error_msg += f"Working directory: {session_path}\n"
                if stdout.strip():
                    error_msg += f"STDOUT: {stdout.strip()}\n"
                if stderr.strip():
                    error_msg += f"STDERR: {stderr.strip()}"
                return False, error_msg
            
            # Log successful completion
            await self._send_debug(task.id, f"Agent '{primary_agent}' completed successfully", agent=primary_agent)
            if stdout:
                await self._send_debug(task.id, f"Agent output preview: {stdout[:500]}...", agent=primary_agent)
            
            # Ensure final task update
            task.current_phase = "Completed"
            task.updated_at = datetime.now()
            
            # Send completion notification via WebSocket
            try:
                await self.websocket_manager.send_completion(task.id, True)
            except Exception as e:
                print(f"DEBUG: Failed to send completion via WebSocket: {e}")
            
            await self._send_debug(task.id, "All agents completed successfully")
            return True, "All agents completed successfully"
            
        except Exception as e:
            error_msg = f"Pipeline execution exception: {str(e)} (Type: {type(e).__name__})\n"
            error_msg += f"Task type: {task.task_type}\n"
            error_msg += f"Session path: {session_path if 'session_path' in locals() else 'Not created'}"
            return False, error_msg
    
    async def get_session_files(self, task_id: str) -> List[SessionFile]:
        """Get list of files in task session"""
        task = self.tasks.get(task_id)
        if not task:
            return []
        
        session_path = Path(task.session_path)
        if not session_path.exists():
            return []
        
        files = []
        for file_path in session_path.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                relative_path = file_path.relative_to(session_path)
                
                files.append(SessionFile(
                    name=file_path.name,
                    path=str(relative_path),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    type="file"
                ))
        
        return files


# Global service instance
agent_service = AgentService()
