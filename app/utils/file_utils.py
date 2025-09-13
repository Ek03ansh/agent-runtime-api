"""
File utilities for the Agent Runtime API.

This module contains common file operations, path utilities, and constants
used across multiple modules to avoid code duplication and circular dependencies.
"""

from pathlib import Path
from typing import Set

# File and directory exclusion constants
EXCLUDED_DIRS: Set[str] = {
    'node_modules', 
    '.git', 
    '__pycache__', 
    '.vscode', 
    '.idea', 
    '.opencode'
}

EXCLUDED_FILES: Set[str] = {
    'opencode.json', 
    '.gitkeep'
}

# File handling constants
TEXT_FILE_ENCODING = 'utf-8'


def should_exclude_path(file_path: Path) -> bool:
    """
    Check if a path should be excluded from processing (ZIP creation, file listing, etc.).
    
    This function centralizes the logic for determining which files and directories
    should be excluded from various operations like artifact creation, session browsing,
    and file uploads.
    
    Args:
        file_path: Path object to check for exclusion
        
    Returns:
        bool: True if the path should be excluded, False otherwise
    """
    # Check if any part of the path contains excluded directories
    for part in file_path.parts:
        if part in EXCLUDED_DIRS:
            return True
    
    # Check if the file name is in the excluded files list
    if file_path.name in EXCLUDED_FILES:
        return True
    
    return False


def ensure_directory_exists(directory: Path, permissions: int = 0o755) -> None:
    """
    Ensure a directory exists with proper permissions.
    
    Args:
        directory: Path to the directory to create
        permissions: Octal permissions to set (default: 0o755)
        
    Raises:
        OSError: If directory creation fails
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # Set permissions on Linux/Unix systems
        try:
            directory.chmod(permissions)
        except (OSError, NotImplementedError):
            # Windows or permission setting not supported
            pass
    except Exception as e:
        raise OSError(f"Failed to create directory {directory}: {e}")