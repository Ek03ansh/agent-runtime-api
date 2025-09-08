import os
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def find_opencode_command():
    """Find the correct OpenCode command for the current platform"""
    
    # For development on Windows, try to find the direct executable path
    if os.name == 'nt':  # Windows (development only)
        try:
            result = subprocess.run("npm config get prefix", 
                                  shell=True,
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                npm_prefix = result.stdout.strip()
                opencode_exe = Path(npm_prefix) / "node_modules" / "opencode-ai" / "node_modules" / "opencode-windows-x64" / "bin" / "opencode.exe"
                if opencode_exe.exists():
                    return str(opencode_exe)
        except Exception:
            pass
    
    # Production/Linux: use standard npm global installation
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
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        
        # Production-ready configuration
        self.provider = "github-copilot"
        self.model = "claude-sonnet-4"
        self.auth_type = "hardcoded-oauth"
        
        # Ensure required directories exist
        self.session_root.mkdir(parents=True, exist_ok=True)
        
    @property
    def opencode_available(self) -> bool:
        """Check if OpenCode command is available"""
        # For direct paths, check if file exists
        if os.path.isabs(self.opencode_command):
            return Path(self.opencode_command).exists()
        # For commands in PATH, use which
        return shutil.which(self.opencode_command) is not None

settings = Settings()
