import asyncio
import json
import os
import uuid
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiofiles

# Fix for Windows subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.models import Task, TaskRequest, TaskType, TaskStatus, TaskConfiguration, LogEntry, SessionFile
from app.core.config import settings


class AgentService:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
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
        session_path = settings.session_root / session_id  # Use provided session_id for path
        
        task = Task(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.pending,
            configuration=configuration,
            session_path=str(session_path),
            session_id=session_id,  # Set the provided session_id
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # Create session directory
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
        
        # Kill the process if it's running
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                del self.active_processes[task_id]
            except Exception:
                pass
        
        # Update task status
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
            
            # Create opencode.json configuration (simplified - only copy if agents are defined there)
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
    
    async def _create_opencode_session(self, session_id: str, working_dir: Path):
        """Pre-create OpenCode session directory structure for user-provided session ID"""
        import time
        import json
        from pathlib import Path
        
        # OpenCode session storage directory - need to find the project's session directory
        opencode_storage = Path.home() / ".local" / "share" / "opencode" / "storage" / "session"
        
        # Look for existing project session directory (the hash-named directory)
        project_session_dirs = [d for d in opencode_storage.iterdir() if d.is_dir() and len(d.name) > 30]
        
        if project_session_dirs:
            # Use the first (most recent) project session directory
            project_session_dir = project_session_dirs[0]
        else:
            # Create a new project session directory if none exists
            import hashlib
            project_id = hashlib.sha1(str(working_dir).encode()).hexdigest()
            project_session_dir = opencode_storage / project_id
            project_session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session file INSIDE the project session directory
        current_time = int(time.time() * 1000)  # milliseconds
        session_data = {
            "id": f"{session_id}",  # Use session_id directly without 'ses_' prefix
            "version": "0.6.4",
            "projectID": project_session_dir.name,
            "directory": str(working_dir).replace("\\", "\\\\"),
            "title": f"User Session - {session_id}",
            "time": {
                "created": current_time,
                "updated": current_time
            }
        }
        
        # Write session file without prefix for user-defined session IDs
        session_file = project_session_dir / f"{session_id}.json"
        
        # Check if session already exists
        if session_file.exists():
            print(f"OpenCode session already exists at {session_file} - reusing existing session")
            return project_session_dir
        
        # Create new session file
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"Pre-created OpenCode session file at {session_file}")
        return project_session_dir
    
    async def _create_opencode_config(self, task: Task):
        """Create session directory and copy essential OpenCode configuration"""
        try:
            from app.core.config import Settings
            settings = Settings()
            
            session_path = Path(task.session_path)
            
            # Ensure session directory exists
            session_path.mkdir(parents=True, exist_ok=True)
            
            # Copy opencode.json from config directory to session
            session_config_path = session_path / "opencode.json"
            
            if settings.opencode_config_path.exists():
                import shutil
                shutil.copy2(settings.opencode_config_path, session_config_path)
                print(f"DEBUG: Copied config to session: {session_config_path}")
            else:
                print(f"WARNING: OpenCode config not found at {settings.opencode_config_path}")
            
            # Copy .opencode directory with prompts from config directory
            session_opencode_dir = session_path / ".opencode"
            
            if settings.opencode_prompts_path.exists():
                # Copy the entire .opencode directory structure
                if session_opencode_dir.exists():
                    import shutil
                    shutil.rmtree(session_opencode_dir)  # Remove if exists
                shutil.copytree(settings.opencode_prompts_path, session_opencode_dir)
                print(f"DEBUG: Copied .opencode directory to session: {session_opencode_dir}")
            else:
                print(f"WARNING: OpenCode prompts directory not found at {settings.opencode_prompts_path}")
            
        except Exception as e:
            raise Exception(f"Failed to create session configuration: {str(e)}")
    # Note: _setup_hardcoded_auth_for_task function removed - no longer needed
    # OpenCode automatically uses global auth at ~/.local/share/opencode/auth.json

    def _should_use_session_continuation(self, task_type: TaskType) -> bool:
        """Determine if task type should use session continuation"""
        # Now that session_id is required, all tasks can benefit from session continuation
        # Complete tasks need it for multi-agent workflows
        # Single-agent tasks (plan, generate, run, fix) can benefit from existing session context
        return task_type in [TaskType.complete, TaskType.fix, TaskType.generate, TaskType.plan, TaskType.run]

    async def _execute_opencode_pipeline(self, task: Task) -> Tuple[bool, str]:
        """Execute the OpenCode pipeline based on task type with proper session management"""
        await self._send_debug(task.id, f"Starting _execute_opencode_pipeline for task {task.id}")
        session_path = Path(task.session_path)
        use_sessions = self._should_use_session_continuation(task.task_type)
        
        try:
            await self._send_debug(task.id, f"Pre-creating OpenCode session for session_id: {task.session_id}")
            # Pre-create OpenCode session directory structure
            await self._create_opencode_session(task.session_id, session_path)
            
            await self._send_debug(task.id, f"Checking session path: {session_path}")
            # Check if session exists
            if not session_path.exists():
                return False, f"Session directory does not exist: {session_path}"
            
            await self._send_debug(task.id, f"Checking OpenCode path: {settings.opencode_path}")
            # Check if OpenCode executable exists
            if not settings.opencode_path.exists():
                return False, f"OpenCode executable not found: {settings.opencode_path}"
            
            await self._send_debug(task.id, "Using global hardcoded GitHub Copilot authentication")
            # No need to copy auth.json - OpenCode will use the global hardcoded auth at ~/.local/share/opencode/auth.json
            await self._send_debug(task.id, "Global auth file will be used automatically")
            
            await self._send_debug(task.id, f"Determining agents for task type: {task.task_type}")
            await self._send_debug(task.id, f"Session continuation enabled: {use_sessions}")
            
            # Determine which agents to run based on task type
            agents = []
            if task.task_type == TaskType.complete:
                agents = ["playwright-test-planner", "playwright-test-generator", "playwright-test-fixer"]
            elif task.task_type == TaskType.plan:
                agents = ["playwright-test-planner"]
            elif task.task_type == TaskType.generate:
                agents = ["playwright-test-generator"]
            elif task.task_type == TaskType.run:
                agents = ["playwright-test-fixer"]
            elif task.task_type == TaskType.fix:
                agents = ["playwright-test-fixer"]
            else:
                return False, f"Unknown task type: {task.task_type}"
            
            if not agents:
                return False, f"No agents configured for task type: {task.task_type}"
            
            await self._send_debug(task.id, f"Selected agents: {agents}")
            
            # Use the provided session ID from the task
            opencode_session_id = task.session_id
            
            # Execute each agent in sequence
            for i, agent_name in enumerate(agents):
                await self._send_debug(task.id, f"Starting agent {i+1}/{len(agents)}: {agent_name}", agent=agent_name)
                task.current_phase = f"Running {agent_name} ({i+1}/{len(agents)})"
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
                
                # Create instructions based on task type and app URL
                app_url = task.configuration.app_url
                if agent_name == "playwright-test-planner":
                    instructions = f"create a test plan for '{app_url}'. Save the test plan as `specs/test-plan.md`."
                elif agent_name == "playwright-test-generator":
                    if use_sessions and i > 0:
                        instructions = f"based on the test plan I created, generate comprehensive test source code into `tests/` folder for '{app_url}'."
                    else:
                        instructions = f"for each scenario in the generated test plan, perform the scenario and generate the test source code into `tests/` folder."
                elif agent_name == "playwright-test-fixer":
                    if task.task_type == TaskType.run:
                        instructions = f"run tests under `tests/` one by one and make all the tests either pass or marked as failing."
                    else:
                        if use_sessions and i > 0:
                            instructions = f"based on the tests I generated, debug and fix any failing tests under `tests/` until they pass."
                        else:
                            instructions = f"debug and fix failing tests under `tests/` one by one until they pass."
                
                # Add custom instructions if provided
                if task.configuration.instructions:
                    instructions = f"{task.configuration.instructions} {instructions}"
                
                # Build command with hardcoded GitHub Copilot configuration
                model_identifier = f"{settings.provider}/{settings.model}"  # github-copilot/claude-sonnet-4
                
                cmd_args = [
                    str(settings.opencode_path), 
                    "run", 
                    "-m", model_identifier
                ]
                
                # Always use the pre-created session since we created it above
                cmd_args.extend(["--session", opencode_session_id])
                await self._send_debug(task.id, f"Using pre-created OpenCode session: {opencode_session_id}", agent=agent_name)
                
                cmd_args.extend(["--agent", agent_name, instructions])
                
                # Set up environment - no Azure credentials needed with hardcoded GitHub Copilot auth
                env = os.environ.copy()
                
                # No need to set Azure environment variables - using hardcoded GitHub Copilot auth
                
                # Execute command from session directory where hardcoded auth.json exists
                await self._send_debug(task.id, f"About to execute command: {' '.join(cmd_args)}", agent=agent_name)
                await self._send_debug(task.id, f"Working directory: {session_path}", agent=agent_name)
                await self._send_debug(task.id, f"Using hardcoded GitHub Copilot configuration: {model_identifier}", agent=agent_name)
                await self._send_debug(task.id, f"Provider: {settings.provider}, Model: {settings.model}, Auth: {settings.auth_type}", agent=agent_name)
                if use_sessions and opencode_session_id:
                    await self._send_debug(task.id, f"Session continuation: {opencode_session_id}", agent=agent_name)
                await self._send_debug(task.id, "Command structure: executable + run + -m + model + [--session session_id] + --agent + agent_name + instructions", agent=agent_name)
                
                # Use thread executor to run subprocess with real-time output capture
                # This avoids the Windows asyncio subprocess issues
                import concurrent.futures
                import threading
                import queue
                
                async def run_subprocess_with_streaming():
                    """Run subprocess with real-time output streaming"""
                    try:
                        await self._send_debug(task.id, "Starting OpenCode subprocess...", agent=agent_name)
                        
                        # Create subprocess in executor
                        loop = asyncio.get_event_loop()
                        
                        def create_process():
                            return subprocess.Popen(
                                cmd_args,
                                cwd=session_path,
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
                            while True:
                                line = await loop.run_in_executor(None, stream.readline)
                                if not line:
                                    break
                                line = line.strip()
                                if line:
                                    # Send to WebSocket
                                    await self._send_debug(task.id, f"OpenCode {prefix}: {line}", agent=agent_name)
                        
                        # Start reading both streams concurrently
                        stdout_task = asyncio.create_task(read_stream(process.stdout, "STDOUT"))
                        stderr_task = asyncio.create_task(read_stream(process.stderr, "STDERR"))
                        
                        # Wait for process completion with timeout
                        try:
                            await asyncio.wait_for(
                                loop.run_in_executor(None, process.wait), 
                                timeout=900  # 15 minute timeout
                            )
                            returncode = process.returncode
                        except asyncio.TimeoutError:
                            await self._send_debug(task.id, "OpenCode process timed out after 15 minutes, killing...", "ERROR", agent=agent_name)
                            process.kill()
                            returncode = -1
                        
                        # Cancel stream reading tasks
                        stdout_task.cancel()
                        stderr_task.cancel()
                        
                        # Collect remaining output
                        stdout_remaining = process.stdout.read() if process.stdout else ""
                        stderr_remaining = process.stderr.read() if process.stderr else ""
                        
                        # Close streams
                        if process.stdout:
                            process.stdout.close()
                        if process.stderr:
                            process.stderr.close()
                        
                        await self._send_debug(task.id, f"OpenCode completed with exit code: {returncode}", agent=agent_name)
                        return returncode, stdout_remaining, stderr_remaining
                        
                    except Exception as e:
                        await self._send_debug(task.id, f"Exception in subprocess: {e}", "ERROR", agent=agent_name)
                        return -2, "", f"Failed to run subprocess: {e}"
                
                try:
                    await self._send_debug(task.id, "Running subprocess with streaming", agent=agent_name)
                    returncode, stdout, stderr = await run_subprocess_with_streaming()
                    
                    await self._send_debug(task.id, f"Subprocess completed, exit code: {returncode}", agent=agent_name)
                    
                    # Create a mock process object for compatibility
                    class MockProcess:
                        def __init__(self, returncode):
                            self.returncode = returncode
                    
                    process = MockProcess(returncode)
                    
                except Exception as e:
                    await self._send_debug(task.id, f"Exception during subprocess execution: {e}", "ERROR", agent=agent_name)
                    raise
                
                # Note: We're using thread executor now, so no active process tracking needed
                # if task.id in self.active_processes:
                #     del self.active_processes[task.id]
                
                # No need to extract session ID since it's provided upfront
                # Session ID is already set in task.session_id from the request
                
                # Store the output for debugging (even if successful)
                # Since we're using global hardcoded auth, there's no session-specific auth file
                auth_file_info = "Global hardcoded GitHub Copilot auth"
                log_entry = LogEntry(
                    agent=agent_name,
                    model=model_identifier,
                    command=' '.join(cmd_args),
                    working_directory=str(session_path),  # Task-specific session
                    auth_file=auth_file_info,
                    exit_code=returncode,
                    stdout=stdout.strip() if stdout else "",
                    stderr=stderr.strip() if stderr else "",
                    azure_resource="N/A (GitHub Copilot)",
                    azure_endpoint="N/A (GitHub Copilot)"
                )
                
                # Store logs in task for retrieval
                if not hasattr(task, 'logs'):
                    task.logs = []
                task.logs.append(log_entry)
                
                if returncode != 0:
                    error_msg = f"Agent '{agent_name}' failed with exit code {returncode}\n"
                    error_msg += f"Command: {' '.join(cmd_args)}\n"
                    error_msg += f"Working directory: {session_path}\n"
                    if stdout.strip():
                        error_msg += f"STDOUT: {stdout.strip()}\n"
                    if stderr.strip():
                        error_msg += f"STDERR: {stderr.strip()}"
                    return False, error_msg
                
                # Log successful completion
                await self._send_debug(task.id, f"Agent '{agent_name}' completed successfully", agent=agent_name)
                if stdout:
                    await self._send_debug(task.id, f"Agent output preview: {stdout[:500]}...", agent=agent_name)
            
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
            
            return True, "Pipeline execution completed successfully"
            
        except Exception as e:
            error_msg = f"Pipeline execution exception: {str(e)} (Type: {type(e).__name__})\n"
            error_msg += f"Task type: {task.task_type}\n"
            error_msg += f"Session: {session_path}"
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
