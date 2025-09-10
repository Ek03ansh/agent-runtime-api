import asyncio
import os
import uuid
import logging
import shutil
import hashlib
import traceback
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models import Task, TaskType, TaskStatus, TaskConfiguration, SessionFile
from app.core.config import settings

logger = logging.getLogger(__name__)

# Constants
OPENCODE_TIMEOUT_SECONDS = 3600  # 1 hour
APP_HASH_LENGTH = 12  # Characters for app workspace hash


class AgentService:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        # Import websocket_manager here to avoid circular imports
        self._websocket_manager = None
        # Thread lock for task status updates to prevent race conditions
        self._task_locks: Dict[str, asyncio.Lock] = {}
        # Track running OpenCode processes for graceful shutdown
        self._running_processes: Dict[str, asyncio.subprocess.Process] = {}
    
    def _get_task_lock(self, task_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific task"""
        if task_id not in self._task_locks:
            self._task_locks[task_id] = asyncio.Lock()
        return self._task_locks[task_id]
    
    def _register_process(self, task_id: str, process: asyncio.subprocess.Process):
        """Register a running OpenCode process for tracking"""
        self._running_processes[task_id] = process
    
    def _unregister_process(self, task_id: str):
        """Unregister a completed OpenCode process"""
        self._running_processes.pop(task_id, None)
    
    async def shutdown_all_processes(self):
        """Gracefully shutdown all running OpenCode processes"""
        if not self._running_processes:
            return
        
        logger.info(f"Shutting down {len(self._running_processes)} running OpenCode processes...")
        
        # First, try graceful termination
        for task_id, process in self._running_processes.items():
            try:
                if process.returncode is None:  # Still running
                    logger.info(f"Terminating OpenCode process for task {task_id}")
                    process.terminate()
            except Exception as e:
                logger.warning(f"Failed to terminate process for task {task_id}: {e}")
        
        # Wait up to 10 seconds for graceful shutdown
        try:
            await asyncio.wait_for(
                asyncio.gather(*[p.wait() for p in self._running_processes.values() if p.returncode is None], 
                              return_exceptions=True),
                timeout=10
            )
            logger.info("All OpenCode processes terminated gracefully")
        except asyncio.TimeoutError:
            # Force kill remaining processes
            logger.warning("Some processes didn't terminate gracefully, force killing...")
            for task_id, process in self._running_processes.items():
                try:
                    if process.returncode is None:
                        logger.warning(f"Force killing OpenCode process for task {task_id}")
                        process.kill()
                        await process.wait()
                except Exception as e:
                    logger.error(f"Failed to kill process for task {task_id}: {e}")
        
        self._running_processes.clear()
        logger.info("All OpenCode processes shutdown complete")
    
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
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            task.debug_logs.append(formatted_message)
        
        # Send to WebSocket clients
        try:
            await self.websocket_manager.send_debug_message(task_id, level, message, agent)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
        
        # Log with appropriate level
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "INFO":
            logger.info(message)
        else:
            logger.debug(message)
        
    def _handle_file_operation_error(self, operation: str, path: Path, error: Exception):
        """Centralized error handling for file operations"""
        logger.error(f"Failed to {operation} {path}: {error}")
        raise
    
    def _ensure_directory_permissions(self, path: Path):
        """Ensure directory has proper permissions for Linux deployment"""
        try:
            # Set directory permissions: owner=rwx, group=rx, others=rx
            path.chmod(0o755)
            # Ensure all parent directories have proper permissions
            for parent in path.parents:
                if parent.exists():
                    parent.chmod(0o755)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not set directory permissions for {path}: {e}")
    
    def _ensure_file_permissions(self, file_path: Path):
        """Ensure file has proper permissions for Linux deployment"""
        try:
            if file_path.exists():
                # Set file permissions: owner=rw, group=r, others=r
                file_path.chmod(0o644)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not set file permissions for {file_path}: {e}")
    
    def _apply_permissions_recursively(self, path: Path):
        """Apply proper permissions recursively to a directory tree"""
        try:
            if path.is_dir():
                path.chmod(0o755)
                for item in path.iterdir():
                    self._apply_permissions_recursively(item)
            elif path.is_file():
                path.chmod(0o644)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not set permissions for {path}: {e}")

    def _safe_copy_file(self, src: Path, dst: Path):
        """Safely copy file with proper error handling and permissions"""
        try:
            shutil.copy2(src, dst)
            self._ensure_file_permissions(dst)
        except (OSError, PermissionError, shutil.Error) as e:
            self._handle_file_operation_error("copy file", f"{src} to {dst}", e)
    
    def _safe_copy_tree(self, src: Path, dst: Path):
        """Safely copy directory tree with proper error handling and permissions"""
        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            # Apply permissions recursively in one pass
            self._apply_permissions_recursively(dst)
        except (OSError, PermissionError, shutil.Error) as e:
            self._handle_file_operation_error("copy directory", f"{src} to {dst}", e)
    
    async def create_task(self, task_type: TaskType, configuration: TaskConfiguration, session_id: str) -> Task:
        """Create a new task with proper separation of OpenCode storage vs working directory"""
        task_id = str(uuid.uuid4())
        
        # Create app-specific directory structure in our repo for working files
        normalized_url = configuration.app_url.lower().strip().rstrip('/')
        app_hash = hashlib.sha1(normalized_url.encode()).hexdigest()[:APP_HASH_LENGTH]
        app_project_id = f"app-{app_hash}"
        
        # Working directory: Our repo's sessions folder (where artifacts go)
        working_dir = settings.session_root / app_project_id / session_id
        
        task = Task(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.pending,
            configuration=configuration,
            session_path=str(working_dir),
            session_id=session_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # Create working directory in our repo
        try:
            working_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_directory_permissions(working_dir)
            
            # Initialize git repo in working directory - MANDATORY for OpenCode project ID consistency
            await self._initialize_git_repo_for_app(working_dir, configuration.app_url)
            
            # Verify git initialization succeeded by getting the project ID
            git_project_id = await self._get_git_project_id(working_dir)
            if not git_project_id:
                raise Exception(f"Failed to initialize git repository in {working_dir}. Git initialization is required for OpenCode session management.")
            
            logger.info(f"Created task working directory with git project ID: {git_project_id}")
        except (OSError, PermissionError) as e:
            self._handle_file_operation_error("create task working directory", working_dir, e)
        except Exception as e:
            # Re-raise git initialization errors
            raise Exception(f"Task creation failed: {str(e)}")
        
        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    async def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        return list(self.tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task and terminate its OpenCode process"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        # Terminate OpenCode process if running
        if task_id in self._running_processes:
            process = self._running_processes[task_id]
            try:
                if process.returncode is None:  # Still running
                    logger.info(f"Terminating OpenCode process for cancelled task {task_id}")
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                self._unregister_process(task_id)
            except Exception as e:
                logger.error(f"Failed to terminate process for task {task_id}: {e}")
        
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
            
            # Create OpenCode configuration
            await self._create_opencode_config(task)
            
            task.status = TaskStatus.running
            task.updated_at = datetime.now()
            
            # Execute based on task type
            success, error_detail = await self._execute_opencode_pipeline(task)
            
            if success:
                task.status = TaskStatus.completed
                task.completed_at = datetime.now()
            else:
                task.status = TaskStatus.failed
                task.error = error_detail or "Task execution failed with unknown error"
            
            task.updated_at = datetime.now()
            return success
            
        except Exception as e:
            tb = traceback.format_exc()
            task.status = TaskStatus.failed
            task.error = f"Task execution exception: {str(e)} (Type: {type(e).__name__})\nTraceback: {tb}"
            task.updated_at = datetime.now()
            return False
    
    async def _create_opencode_config(self, task: Task):
        """Create session directory and copy essential OpenCode configuration"""
        try:
            session_path = Path(task.session_path)
            
            # Ensure session directory exists with proper permissions
            session_path.mkdir(parents=True, exist_ok=True)
            self._ensure_directory_permissions(session_path)
            
            # Copy opencode.json from config directory to session
            session_config_path = session_path / "opencode.json"
            
            if settings.opencode_config_path.exists():
                self._safe_copy_file(settings.opencode_config_path, session_config_path)
            else:
                logger.warning(f"OpenCode config not found at {settings.opencode_config_path}")
            
            # Copy .opencode directory from configured path (contains prompts and agent configs)
            project_opencode_dir = settings.opencode_dir
            session_opencode_dir = session_path / ".opencode"
            
            if project_opencode_dir.exists():
                # Copy the entire .opencode directory structure with proper permissions
                self._safe_copy_tree(project_opencode_dir, session_opencode_dir)
            else:
                logger.info(f"No .opencode directory found at {settings.opencode_dir} - using OpenCode defaults")
            
        except Exception as e:
            raise Exception(f"Failed to create session configuration: {str(e)}")

    def _detect_opencode_storage_path(self) -> Path:
        """Dynamically detect the correct OpenCode storage path for the current environment"""
        # Use standard home directory path for OpenCode storage
        opencode_storage_path = Path.home() / ".local" / "share" / "opencode" / "storage"
        
        # Create directory if it doesn't exist
        if not opencode_storage_path.exists():
            logger.info(f"Creating OpenCode storage at: {opencode_storage_path}")
            try:
                opencode_storage_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create OpenCode storage: {e}")
                raise Exception(f"Could not create OpenCode storage directory at {opencode_storage_path}")
        else:
            logger.info(f"Found OpenCode storage at: {opencode_storage_path}")
        
        return opencode_storage_path

    async def _create_opencode_session(self, session_id: str, working_dir: Path, app_url: str):
        """Pre-create OpenCode session directory structure using git-based project ID like OpenCode"""
        import time
        import json
        
        try:
            # Get project ID from git repository (REQUIRED - no fallbacks)
            git_project_id = await self._get_git_project_id(working_dir)
            
            if not git_project_id:
                raise Exception(f"No git project ID found in {working_dir}. Git repository must be properly initialized.")
            
            project_id = git_project_id
            logger.info(f"Using git project ID: {project_id} (from {working_dir})")
            
            # Dynamically detect OpenCode storage location
            opencode_storage = self._detect_opencode_storage_path()
            logger.info(f"Using OpenCode storage path: {opencode_storage}")
            
            # Create session directory structure
            session_base_dir = opencode_storage / "session"
            project_session_dir = session_base_dir / project_id
            
            logger.info(f"Creating session directory: {project_session_dir}")
            
            # Create directories with explicit error handling (if not already created by task creation)
            try:
                project_session_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Successfully ensured session directory exists: {project_session_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating session directory: {e}")
                raise Exception(f"Permission denied creating session directory: {project_session_dir}")
            except Exception as e:
                logger.error(f"Failed to create session directory: {e}")
                raise Exception(f"Failed to create session directory: {project_session_dir} - {e}")
            
            # Verify directory exists
            if not project_session_dir.exists():
                logger.error(f"Session directory was not created: {project_session_dir}")
                raise Exception(f"Session directory creation failed: {project_session_dir}")
            
            # Create session file following OpenCode's session structure
            current_time = int(time.time() * 1000)  # milliseconds
            session_data = {
                "id": session_id,
                "version": "0.6.4",  # Match OpenCode version
                "projectID": project_id,
                "directory": str(working_dir).replace("\\", "/"),  # Use forward slashes like OpenCode
                "title": f"User Session - {session_id}",
                "time": {
                    "created": current_time,
                    "updated": current_time
                }
            }
            
            # Write session file directly in the project session directory (OpenCode expects it here)
            session_file = project_session_dir / f"{session_id}.json"
            
            # Check if session already exists
            if session_file.exists():
                logger.info(f"OpenCode session already exists at {session_file} - reusing existing session")
                return project_session_dir
            
            # Create new session file with error handling
            try:
                with open(session_file, 'w') as f:
                    json.dump(session_data, f, indent=2)
                logger.info(f"Created OpenCode session file at {session_file} for app {app_url}")
            except PermissionError as e:
                logger.error(f"Permission denied writing session file: {e}")
                raise Exception(f"Permission denied writing session file: {session_file}")
            except Exception as e:
                logger.error(f"Failed to write session file: {e}")
                raise Exception(f"Failed to write session file: {session_file} - {e}")
            
            # Verify session file was created
            if not session_file.exists():
                logger.error(f"Session file was not created: {session_file}")
                raise Exception(f"Session file creation failed: {session_file}")
            
            logger.info(f"Successfully created OpenCode session: {session_file}")
            return project_session_dir
            
        except Exception as e:
            logger.error(f"Failed to create OpenCode session: {e}")
            raise

    async def _get_git_project_id(self, directory: Path) -> Optional[str]:
        """Get project ID from git repository like OpenCode does"""
        try:
            if not (directory / ".git").exists():
                return None
            
            # Check if git command is available
            git_check = await asyncio.create_subprocess_exec(
                "git", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await git_check.communicate()
            
            if git_check.returncode != 0:
                logger.warning("Git command not available")
                return None
                
            result = await asyncio.create_subprocess_exec(
                "git", "rev-list", "--max-parents=0", "--all",
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and stdout.strip():
                commit_hashes = [h.strip() for h in stdout.decode().strip().split('\n') if h.strip()]
                if commit_hashes:
                    # Use the first commit hash (sorted) as OpenCode does
                    return sorted(commit_hashes)[0]
            else:
                logger.debug(f"Git rev-list failed: {stderr.decode().strip()}")
            return None
        except Exception as e:
            logger.debug(f"Failed to get git project ID from {directory}: {e}")
            return None

    async def _initialize_git_repo_for_app(self, directory: Path, app_url: str) -> None:
        """Initialize git repository with consistent commit hash based on app URL - MUST succeed"""
        try:
            # Check if already a git repo
            if (directory / ".git").exists():
                logger.info(f"Git repository already exists in {directory}")
                return
            
            # Initialize git repo
            result = await asyncio.create_subprocess_exec(
                "git", "init",
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Git init failed: {stderr.decode().strip()}")
            
            # Create a dummy file for the initial commit
            dummy_file = directory / ".gitkeep"
            dummy_file.write_text(f"Project for: {app_url}\n")
            
            # Add and commit with consistent message and deterministic timestamp
            normalized_url = app_url.lower().strip().rstrip('/')
            commit_message = f"Initial commit for {normalized_url}"
            
            # Use a deterministic timestamp based on the app URL for consistent commit hashes
            app_hash = hashlib.sha1(normalized_url.encode()).hexdigest()
            # Convert hash to a deterministic timestamp (epoch + hash-based offset)
            hash_int = int(app_hash[:8], 16)  # Use first 8 chars of hash as int
            deterministic_timestamp = 1640995200 + (hash_int % 86400)  # Jan 1, 2022 + hash-based offset within a day
            commit_date = str(deterministic_timestamp)
            
            # Set git config for this repo
            result = await asyncio.create_subprocess_exec(
                "git", "config", "user.name", "OpenCode Agent",
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            if result.returncode != 0:
                raise Exception("Failed to set git user.name")
            
            result = await asyncio.create_subprocess_exec(
                "git", "config", "user.email", "agent@opencode.local",
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            if result.returncode != 0:
                raise Exception("Failed to set git user.email")
            
            # Add file
            result = await asyncio.create_subprocess_exec(
                "git", "add", ".gitkeep",
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            if result.returncode != 0:
                raise Exception(f"Git add failed: {stderr.decode().strip()}")
            
            # Commit with deterministic timestamp for consistent hash
            env = {**os.environ, "GIT_AUTHOR_DATE": commit_date, "GIT_COMMITTER_DATE": commit_date}
            result = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", commit_message,
                cwd=directory,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Git commit failed: {stderr.decode().strip()}")
                
            logger.info(f"Successfully initialized git repo for app {app_url} in {directory}")
                
        except Exception as e:
            logger.error(f"Git initialization failed for {app_url}: {e}")
            raise Exception(f"Git repository initialization failed: {str(e)}")

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
            
            # Pre-create OpenCode session directory structure
            await self._send_debug(task.id, f"Pre-creating OpenCode session for session_id: {task.session_id}")
            await self._create_opencode_session(task.session_id, session_path, task.configuration.app_url)
            await self._send_debug(task.id, f"OpenCode session {task.session_id} ready for use")
            
            # Use build agent for orchestration
            primary_agent = "build"
            
            await self._send_debug(task.id, f"Using primary agent: {primary_agent}")
            
            # Execute the primary agent which will orchestrate sub-agents
            await self._send_debug(task.id, f"Starting primary agent: {primary_agent}", agent=primary_agent)
            task.updated_at = datetime.now()
            
            # Send status update via WebSocket
            try:
                await self.websocket_manager.send_status_update(
                    task.id, 
                    task.status.value, 
                    f"Running {primary_agent} (orchestrating sub-agents)"
                )
            except Exception as e:
                logger.warning(f"Failed to send status update via WebSocket: {e}")
            
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
                "--print-logs",
                "--log-level", settings.opencode_log_level,  # Use configurable log level from environment
                "--session", task.session_id,  # Use the pre-created session
                "--agent", primary_agent,
                "-m", model_identifier,
                instructions
            ]
            await self._send_debug(task.id, f"Using {primary_agent} agent for {task.task_type} workflow with session {task.session_id}", agent=primary_agent)
            
            # Set up environment for Linux deployment
            env = os.environ.copy()
            
            # Ensure PATH includes standard Linux binary locations
            current_path = env.get('PATH', '')
            linux_paths = ['/usr/local/bin', '/usr/bin', '/bin']
            
            # Add missing paths (simple string manipulation for Linux)
            for linux_path in linux_paths:
                if linux_path not in current_path:
                    current_path = f"{linux_path}:{current_path}"
            env['PATH'] = current_path
            
            # Execute command from session directory where OpenCode project is located
            await self._send_debug(task.id, f"About to execute command: {' '.join(cmd_args)}", agent=primary_agent)
            await self._send_debug(task.id, f"Working directory: {session_path}", agent=primary_agent)
            
            # Simple subprocess execution - works reliably on Linux
            try:
                await self._send_debug(task.id, "Starting OpenCode subprocess...", agent=primary_agent)
                
                # Use asyncio.create_subprocess_exec for clean async subprocess handling
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    cwd=session_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                
                # Register process for shutdown tracking
                self._register_process(task.id, process)
                
                # Stream output in real-time
                stdout_lines = []
                stderr_lines = []
                
                async def stream_stdout():
                    """Stream stdout in real-time"""
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        line_text = line.decode('utf-8', errors='replace').rstrip()
                        if line_text:
                            stdout_lines.append(line_text)
                            await self._send_debug(task.id, f"[STDOUT] {line_text}", agent=primary_agent)
                
                async def stream_stderr():
                    """Stream stderr in real-time"""
                    while True:
                        line = await process.stderr.readline()
                        if not line:
                            break
                        line_text = line.decode('utf-8', errors='replace').rstrip()
                        if line_text:
                            stderr_lines.append(line_text)
                            await self._send_debug(task.id, f"[STDERR] {line_text}", agent=primary_agent)
                
                # Wait for completion with timeout and stream output
                try:
                    # Start streaming tasks
                    stdout_task = asyncio.create_task(stream_stdout())
                    stderr_task = asyncio.create_task(stream_stderr())
                    
                    # Wait for process completion with timeout
                    returncode = await asyncio.wait_for(
                        process.wait(),
                        timeout=OPENCODE_TIMEOUT_SECONDS
                    )
                    
                    # Ensure all output is captured
                    await stdout_task
                    await stderr_task
                    
                    # Join lines for final output
                    stdout = '\n'.join(stdout_lines)
                    stderr = '\n'.join(stderr_lines)
                    
                except asyncio.TimeoutError:
                    await self._send_debug(task.id, "OpenCode process timed out, terminating...", "ERROR", agent=primary_agent)
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    # Unregister timed out process
                    self._unregister_process(task.id)
                    returncode = -1
                    stdout = '\n'.join(stdout_lines)
                    stderr = '\n'.join(stderr_lines)
                
                await self._send_debug(task.id, f"OpenCode completed with exit code: {returncode}", agent=primary_agent)
                
                # Unregister completed process
                self._unregister_process(task.id)
                
                # Note: Output is already streamed in real-time above, no need to log it again here
            
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
            task.updated_at = datetime.now()
            
            # Send completion notification via WebSocket
            try:
                await self.websocket_manager.send_completion(task.id, True)
            except Exception as e:
                logger.warning(f"Failed to send completion via WebSocket: {e}")
            
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
        try:
            for file_path in session_path.rglob("*"):
                try:
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
                except (OSError, PermissionError) as e:
                    # Skip files we can't access (common on Linux with permission restrictions)
                    logger.debug(f"Skipping file due to access error: {file_path} - {e}")
                    continue
        except (OSError, PermissionError) as e:
            logger.error(f"Error listing session files in {session_path}: {e}")
        
        return files


# Global service instance
agent_service = AgentService()
