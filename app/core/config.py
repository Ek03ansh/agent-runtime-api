import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
SESSION_ROOT = Path("./sessions")
OPENCODE_PATH = Path("./bin/opencode.exe")

# Environment-based configuration
class Settings:
    def __init__(self):
        self.session_root = Path(os.getenv("SESSION_ROOT", "./sessions"))
        self.opencode_path = Path(os.getenv("OPENCODE_PATH", "./bin/opencode.exe"))
        self.opencode_config_path = Path(os.getenv("OPENCODE_CONFIG_PATH", "./config/opencode.json"))
        self.opencode_prompts_path = Path(os.getenv("OPENCODE_PROMPTS_PATH", "./config/.opencode"))
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "5001"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        
        # Hardcoded GitHub Copilot configuration for deployment
        # No need for Azure OpenAI environment variables - using hardcoded auth
        self.provider = "github-copilot"
        self.model = "claude-sonnet-4"
        self.auth_type = "hardcoded-oauth"
        
    @property
    def opencode_available(self) -> bool:
        """Check if OpenCode executable is available"""
        return self.opencode_path.exists()

settings = Settings()
