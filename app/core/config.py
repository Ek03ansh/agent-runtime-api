import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment-based configuration
class Settings:
    def __init__(self):
        self.session_root = Path(os.getenv("SESSION_ROOT", "./sessions"))
        self.opencode_command = os.getenv("OPENCODE_COMMAND", "opencode")
        self.opencode_config_path = Path(os.getenv("OPENCODE_CONFIG_PATH", "./opencode.json"))
        self.opencode_dir = Path(os.getenv("OPENCODE_DIR", "./.opencode"))
        
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5001"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.opencode_log_level = os.getenv("OPENCODE_LOG_LEVEL", "WARN").upper()
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        
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
    
    def validate_paths(self) -> dict:
        """Validate all configured paths and return status"""
        return {
            "session_root": self.session_root.exists(),
            "opencode_config": self.opencode_config_path.exists(),
            "opencode_dir": self.opencode_dir.exists(),
            "opencode_command": self.opencode_available
        }

settings = Settings()
