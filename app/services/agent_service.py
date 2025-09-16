import asyncio
import os
import uuid
import logging
import shutil
import hashlib
import traceback
import time
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.utils.file_utils import should_exclude_path

from app.models import Task, TaskType, TaskStatus, TaskPhase, TaskConfiguration, SessionFile, ArtifactsUrl, UploadedArtifacts, SignInMethod
from app.services.azure_storage_service import AzureStorageService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Constants
OPENCODE_TIMEOUT_SECONDS = 7200  # 2 hours
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
    
    async def _load_phase_tracking_prompt(self) -> str:
        """Load the phase tracking prompt from file"""
        try:
            phase_tracking_path = Path(".opencode/prompts/system/phase-tracking.md")
            if phase_tracking_path.exists():
                with open(phase_tracking_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("Phase tracking prompt file not found")
                return ""
        except Exception as e:
            logger.warning(f"Failed to load phase tracking prompt: {e}")
            return ""
    
    async def _load_authentication_prompt(self, username: str, password: str) -> str:
        """Load and customize the authentication prompt with credentials"""
        try:
            auth_prompt_path = Path(".opencode/prompts/system/authentication.md")
            if auth_prompt_path.exists():
                with open(auth_prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Replace placeholders with actual credentials
                content = content.replace("{username}", username)
                content = content.replace("{password}", password)
                return content
            else:
                logger.warning("Authentication prompt file not found")
                return ""
        except Exception as e:
            logger.warning(f"Failed to load authentication prompt: {e}")
            return ""
    
    async def _monitor_phase_status_file(self, task_id: str):
        """Monitor the phase status file and update task accordingly"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        status_file_path = Path(task.session_path) / "status" / "phase.json"
        
        while task.status == TaskStatus.running:
            try:
                if status_file_path.exists():
                    with open(status_file_path, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                    
                    # Update task with phase information
                    phase_str = status_data.get('current_phase', 'planning')
                    try:
                        new_phase = TaskPhase(phase_str)
                        if new_phase != task.current_phase:
                            task.current_phase = new_phase
                            task.updated_at = datetime.now()
                            
                            # Send WebSocket update
                            try:
                                await self.websocket_manager.send_status_update(
                                    task_id, 
                                    task.status.value, 
                                    f"{new_phase.value.replace('_', ' ').title()}"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to send phase update via WebSocket: {e}")
                    except ValueError:
                        logger.warning(f"Invalid phase value in status file: {phase_str}")
                        
            except Exception as e:
                logger.debug(f"Error reading phase status file: {e}")
            
            # Check every 2 seconds
            await asyncio.sleep(2)
    
    async def _auto_upload_artifacts(self, task: Task) -> Optional[UploadedArtifacts]:
        """
        Auto-upload task artifacts to Azure Storage if artifacts_url is provided
        
        Args:
            task: The completed task
            
        Returns:
            UploadedArtifacts object if upload was successful, None otherwise
        """
        if not task.artifacts_url:
            logger.debug(f"No artifacts_url provided for task {task.id}, skipping auto-upload")
            return None
            
        try:
            
            # Validate SAS URL format
            if not AzureStorageService.validate_sas_url(task.artifacts_url.sas_url):
                logger.warning(f"Invalid SAS URL format for task {task.id}, skipping auto-upload")
                task.error = f"{task.error}\nNote: Invalid SAS URL, artifacts not uploaded" if task.error else "Invalid SAS URL, artifacts not uploaded"
                return None
            
            await self._send_debug(task.id, "Starting auto-upload of artifacts to Azure Storage...")
            
            # Create ZIP of session directory (reuse existing logic from session controller)
            session_path = Path(task.session_path)
            if not session_path.exists():
                logger.warning(f"Session path not found for task {task.id}: {session_path}")
                return None
            
            # Create temporary ZIP file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            zip_path = temp_zip.name
            temp_zip.close()
            
            try:
                # Create ZIP file with session contents
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in session_path.rglob("*"):
                        if file_path.is_file() and not self._should_exclude_path(file_path):
                            try:
                                relative_path = file_path.relative_to(session_path)
                                zipf.write(file_path, relative_path)
                            except (OSError, PermissionError):
                                continue
                
                # Generate blob name with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                blob_name = f"session_{task.session_id}_{timestamp}.zip"
                
                # Upload to Azure Storage
                zip_file_path = Path(zip_path)
                blob_url = await AzureStorageService.upload_file_to_sas_url(
                    file_path=zip_file_path,
                    sas_url=task.artifacts_url.sas_url,
                    blob_name=blob_name
                )
                
                file_size = zip_file_path.stat().st_size
                await self._send_debug(task.id, f"Successfully uploaded artifacts: {blob_name} ({file_size} bytes)")
                
                # Return UploadedArtifacts object with full details
                return UploadedArtifacts(
                    blob_url=blob_url,
                    blob_name=blob_name,
                    uploaded_at=datetime.now(),
                    file_size=file_size
                )
                
            finally:
                # Clean up temporary ZIP file
                Path(zip_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"Failed to auto-upload artifacts for task {task.id}: {e}")
            await self._send_debug(task.id, f"Auto-upload failed: {str(e)}", level="ERROR")
            # Don't fail the task, just log the upload failure
            task.error = f"{task.error}\nNote: Artifact upload failed: {str(e)}" if task.error else f"Artifact upload failed: {str(e)}"
            return None
    
    def _should_exclude_path(self, file_path: Path) -> bool:
        """Check if a path should be excluded from ZIP"""
        return should_exclude_path(file_path)
        
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
    
    async def create_task(self, task_type: TaskType, configuration: TaskConfiguration, session_id: str, artifacts_url: Optional[ArtifactsUrl] = None) -> Task:
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
            artifacts_url=artifacts_url,
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
            
            # Start phase monitoring in background
            monitor_task = asyncio.create_task(self._monitor_phase_status_file(task.id))
            
            try:
                # Execute based on task type
                success, error_detail = await self._execute_opencode_pipeline(task)
            finally:
                # Cancel phase monitoring
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
            if success:
                task.status = TaskStatus.completed
                task.completed_at = datetime.now()
            else:
                task.status = TaskStatus.failed
                task.error = error_detail or "Task execution failed with unknown error"
            
            # Auto-upload artifacts if artifacts_url is provided (for both success and failure)
            uploaded_artifacts = await self._auto_upload_artifacts(task)
            if uploaded_artifacts:
                # Store uploaded artifacts details in separate field (preserving original SAS URL)
                task.uploaded_artifacts = uploaded_artifacts
                logger.info(f"Task {task.id} artifacts uploaded to: {uploaded_artifacts.blob_url}")
            
            task.updated_at = datetime.now()
            return success
            
        except Exception as e:
            tb = traceback.format_exc()
            task.status = TaskStatus.failed
            task.error = f"Task execution exception: {str(e)} (Type: {type(e).__name__})\nTraceback: {tb}"
            
            # Auto-upload artifacts even on exception (partial artifacts may be useful)
            uploaded_artifacts = await self._auto_upload_artifacts(task)
            if uploaded_artifacts:
                # Store uploaded artifacts details in separate field (preserving original SAS URL)
                task.uploaded_artifacts = uploaded_artifacts
                logger.info(f"Task {task.id} artifacts uploaded after exception to: {uploaded_artifacts.blob_url}")
            
            task.updated_at = datetime.now()
            return False
    
    async def _create_opencode_config(self, task: Task):
        """Create session directory and copy essential OpenCode configuration"""
        try:
            session_path = Path(task.session_path)
            
            # Ensure session directory exists with proper permissions
            session_path.mkdir(parents=True, exist_ok=True)
            self._ensure_directory_permissions(session_path)
            
            # Create status directory for phase tracking
            status_dir = session_path / "status"
            status_dir.mkdir(exist_ok=True)
            self._ensure_directory_permissions(status_dir)
            
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
                TaskType.complete: ".opencode/prompts/tasks/complete-testing-workflow.md",
                TaskType.plan: ".opencode/prompts/tasks/test-planning.md", 
                TaskType.generate: ".opencode/prompts/tasks/test-generation.md",
                TaskType.fix: ".opencode/prompts/tasks/test-fixing.md",
                TaskType.custom: None  # Use instructions directly, no prompt file
            }
            
            # Get prompt file path (handle custom task type)
            prompt_file_path = prompt_files[task.task_type]
            
            if task.task_type == TaskType.custom:
                # For custom tasks, use instructions directly
                instructions = task.configuration.instructions
            else:
                # For other task types, read from prompt file
                with open(prompt_file_path, 'r', encoding='utf-8') as f:
                    instructions = f.read().replace("{app_url}", app_url)
                
                # Add custom instructions if provided
                if task.configuration.instructions:
                    instructions = f"{task.configuration.instructions}\n\n{instructions}"
            
            # Load and append authentication instructions if credentials are provided
            if (task.configuration.sign_in and 
                task.configuration.sign_in.method == SignInMethod.username_password and
                task.configuration.sign_in.username and 
                task.configuration.sign_in.password):
                
                auth_instructions = await self._load_authentication_prompt(
                    task.configuration.sign_in.username,
                    task.configuration.sign_in.password
                )
                if auth_instructions:
                    instructions = f"{instructions}\n\n---\n\n{auth_instructions}"
                    await self._send_debug(task.id, "Added authentication instructions to prompt")
            
            # Load and append phase tracking instructions
            phase_tracking_instructions = await self._load_phase_tracking_prompt()
            if phase_tracking_instructions:
                instructions = f"{instructions}\n\n---\n\n{phase_tracking_instructions}"
                await self._send_debug(task.id, "Added phase tracking instructions to prompt")
            
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
            session_idle_detected = False
            
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
                nonlocal session_idle_detected
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    line_text = line.decode('utf-8', errors='replace').rstrip()
                    if line_text:
                        stderr_lines.append(line_text)
                        await self._send_debug(task.id, f"[STDERR] {line_text}", agent=primary_agent)
                        
                        # Check for session.idle indicator - OpenCode work is done but process isn't ending
                        if "session.idle" in line_text:
                            await self._send_debug(task.id, "Detected session.idle - OpenCode work completed, terminating process", agent=primary_agent)
                            session_idle_detected = True
                            try:
                                process.terminate()
                                # Wait for graceful termination, force kill if needed
                                try:
                                    await asyncio.wait_for(process.wait(), timeout=3)
                                except asyncio.TimeoutError:
                                    process.kill()
                                    await process.wait()
                                # Break out of stderr loop since process is terminated
                                break
                            except Exception as e:
                                await self._send_debug(task.id, f"Failed to terminate process: {e}", "WARNING", agent=primary_agent)
            
            # Wait for completion with timeout and stream output
            try:
                # Start streaming tasks
                stdout_task = asyncio.create_task(stream_stdout())
                stderr_task = asyncio.create_task(stream_stderr())
                
                # Wait for process completion with timeout (unless already terminated by session.idle detection)
                if not session_idle_detected:
                    returncode = await asyncio.wait_for(
                        process.wait(),
                        timeout=OPENCODE_TIMEOUT_SECONDS
                    )
                else:
                    # Process was already terminated, get the return code
                    returncode = process.returncode
                
                # Handle streaming tasks completion
                if session_idle_detected:
                    # Cancel streaming tasks since process is terminated
                    stdout_task.cancel()
                    stderr_task.cancel()
                    try:
                        await stdout_task
                    except asyncio.CancelledError:
                        pass
                    try:
                        await stderr_task
                    except asyncio.CancelledError:
                        pass
                else:
                    # Normal completion - wait for streaming tasks to finish
                    await stdout_task
                    await stderr_task
                
                # Join lines for final output
                stdout = '\n'.join(stdout_lines)
                stderr = '\n'.join(stderr_lines)
                
                # If process was terminated due to session.idle, treat as successful completion
                if session_idle_detected:
                    await self._send_debug(task.id, "Process terminated after session.idle - treating as successful completion", agent=primary_agent)
                    returncode = 0
                
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
    
    async def cleanup_all_sessions(self) -> Tuple[int, int, bool, Dict[str, List[str]]]:
        """Clean up all sessions, tasks, and OpenCode storage with verification
        
        Returns:
            Tuple of (deleted_sessions_count, deleted_tasks_count, deleted_opencode_storage, failures)
            failures dict contains 'session_failures', 'app_failures', 'opencode_failure'
        """
        deleted_sessions = 0
        deleted_tasks = len(self.tasks)
        deleted_opencode_storage = False
        
        try:
            # First, cancel and shutdown all running processes
            await self.shutdown_all_processes()
            
            # Clear all in-memory tasks
            self.tasks.clear()
            self._task_locks.clear()
            
            # Delete all session directories from our storage with verification
            session_root = settings.session_root
            failed_session_deletions = []
            failed_app_deletions = []
            
            if session_root.exists():
                for app_dir in session_root.glob("app-*"):
                    if app_dir.is_dir():
                        for session_dir in app_dir.iterdir():
                            if session_dir.is_dir():
                                session_path_str = str(session_dir)
                                try:
                                    shutil.rmtree(session_dir)
                                    # Verify deletion was successful
                                    if session_dir.exists():
                                        failed_session_deletions.append(session_path_str)
                                        logger.error(f"Session directory still exists after deletion: {session_dir}")
                                    else:
                                        deleted_sessions += 1
                                        logger.info(f"Verified deletion of session directory: {session_dir}")
                                except Exception as e:
                                    failed_session_deletions.append(session_path_str)
                                    logger.error(f"Failed to delete session {session_dir}: {e}")
                        
                        # Remove empty app directory with verification
                        try:
                            if not any(app_dir.iterdir()):
                                app_path_str = str(app_dir)
                                app_dir.rmdir()
                                # Verify app directory deletion
                                if app_dir.exists():
                                    failed_app_deletions.append(app_path_str)
                                    logger.error(f"App directory still exists after deletion: {app_dir}")
                                else:
                                    logger.info(f"Verified deletion of empty app directory: {app_dir}")
                            else:
                                logger.info(f"App directory not empty, keeping: {app_dir}")
                        except Exception as e:
                            failed_app_deletions.append(str(app_dir))
                            logger.error(f"Failed to delete app directory {app_dir}: {e}")
            
            # Log summary of failed deletions
            if failed_session_deletions:
                logger.error(f"Failed to delete {len(failed_session_deletions)} session directories: {failed_session_deletions}")
            if failed_app_deletions:
                logger.error(f"Failed to delete {len(failed_app_deletions)} app directories: {failed_app_deletions}")
            
            # Delete entire OpenCode storage - complete cleanup with verification
            opencode_deletion_failed = False
            try:
                opencode_storage = self._detect_opencode_storage_path()
                if opencode_storage.exists():
                    opencode_path_str = str(opencode_storage)
                    logger.info(f"Attempting to delete entire OpenCode storage: {opencode_storage}")
                    
                    # Delete the entire OpenCode storage directory
                    # This removes sessions, auth tokens, extensions, settings - everything
                    shutil.rmtree(opencode_storage)
                    
                    # Verify OpenCode storage deletion was successful
                    if opencode_storage.exists():
                        opencode_deletion_failed = True
                        deleted_opencode_storage = False
                        logger.error(f"OpenCode storage still exists after deletion attempt: {opencode_storage}")
                    else:
                        deleted_opencode_storage = True
                        logger.info(f"Verified deletion of entire OpenCode storage: {opencode_storage}")
                        logger.info("Complete OpenCode cleanup verified - auth, extensions, settings all removed")
                else:
                    logger.info("No OpenCode storage found to delete")
                    deleted_opencode_storage = False
            except Exception as e:
                opencode_deletion_failed = True
                deleted_opencode_storage = False
                logger.error(f"Failed to delete OpenCode storage: {e}")
                # Don't fail the entire cleanup if OpenCode storage cleanup fails
            
            # Compile failure information
            failures = {
                'session_failures': failed_session_deletions,
                'app_failures': failed_app_deletions,
                'opencode_failure': opencode_deletion_failed
            }
            
            # Log comprehensive cleanup summary
            total_failures = len(failed_session_deletions) + len(failed_app_deletions) + (1 if opencode_deletion_failed else 0)
            logger.info(f"Cleanup completed: {deleted_sessions} sessions, {deleted_tasks} tasks, OpenCode storage: {deleted_opencode_storage}")
            
            if total_failures > 0:
                logger.warning(f"Cleanup had {total_failures} failures - see failure details in response")
            else:
                logger.info("All cleanup operations completed successfully with verification")
            
            return deleted_sessions, deleted_tasks, deleted_opencode_storage, failures
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise Exception(f"Cleanup operation failed: {str(e)}")



# Global service instance
agent_service = AgentService()
