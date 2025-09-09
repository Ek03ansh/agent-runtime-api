import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def find_opencode_command():
    """Find the correct OpenCode command for Linux deployment"""
    # Use standard npm global installation path for Linux
    return "opencode"

# Environment-based configuration
class Settings:
    def __init__(self):
        self.session_root = Path(os.getenv("SESSION_ROOT", "./sessions"))
        self.opencode_command = os.getenv("OPENCODE_COMMAND") or find_opencode_command()
        self.opencode_config_path = Path(os.getenv("OPENCODE_CONFIG_PATH", "./opencode.json"))
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5001"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        
        # Production-ready configuration
        self.provider = "github-copilot"
        self.model = "claude-sonnet-4"
        self.auth_type = "hardcoded-oauth"
        
        # Ensure required directories exist
        self.session_root.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup application-wide logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ]
        )
        
        # Reduce noise from watchfiles during development
        logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
        
    @property
    def opencode_available(self) -> bool:
        """Check if OpenCode command is available"""
        return shutil.which(self.opencode_command) is not None

settings = Settings()
