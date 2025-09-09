import math
from datetime import datetime
from pathlib import Path

def ensure_directory_exists(path: Path):
    """Ensure directory exists, create if not"""
    path.mkdir(parents=True, exist_ok=True)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def safe_str(obj, default: str = "Unknown") -> str:
    """Safely convert object to string with fallback"""
    try:
        return str(obj) if obj is not None else default
    except Exception:
        return default
