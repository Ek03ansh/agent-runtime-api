from fastapi import APIRouter, HTTPException
import subprocess
import re
from app.core.config import settings
from app.models import AuthLoginResponse, AuthStatusResponse

router = APIRouter(tags=["auth"])


def _extract_device_code_from_output(output: str) -> tuple[str | None, str | None]:
    """Extract device code and verification URL from OpenCode output"""
    device_code = None
    verification_url = None
    
    # Look for device code pattern
    code_match = re.search(r'(?:Enter code|code):\s*([A-Z0-9]{4}-[A-Z0-9]{4})', output, re.IGNORECASE)
    if code_match:
        device_code = code_match.group(1)
    
    # Look for GitHub device URL
    if "https://github.com/login/device" in output:
        verification_url = "https://github.com/login/device"
    
    return device_code, verification_url


@router.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login():
    """Start OpenCode GitHub Copilot auth flow"""
    try:
        if not settings.opencode_available:
            raise HTTPException(
                status_code=500, 
                detail=f"OpenCode command not found: {settings.opencode_command}"
            )
        
        # Start auth process
        process = subprocess.Popen(
            [settings.opencode_command, "auth", "login"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Send GitHub Copilot selection and get initial output
        process.stdin.write("GitHub Copilot\n")
        process.stdin.flush()
        process.stdin.close()
        
        # Read output to extract device code (with timeout)
        try:
            stdout, stderr = process.communicate(timeout=10)
            device_code, verification_url = _extract_device_code_from_output(stdout)
            
            return AuthLoginResponse(
                device_code=device_code,
                verification_url=verification_url
            )
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise HTTPException(status_code=500, detail="Auth process timed out")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start auth process: {str(e)}")


@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check current OpenCode authentication status"""
    try:
        if not settings.opencode_available:
            raise HTTPException(
                status_code=500, 
                detail=f"OpenCode command not found: {settings.opencode_command}"
            )
        
        result = subprocess.run(
            [settings.opencode_command, "auth", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        
        # Check if authenticated by looking for GitHub Copilot in output
        has_auth = (
            result.returncode == 0 and 
            result.stdout.strip() and
            "GitHub Copilot" in result.stdout and 
            "Commands:" not in result.stdout  # Not help text
        )
        
        return AuthStatusResponse(authenticated=has_auth)
            
    except subprocess.TimeoutExpired:
        return AuthStatusResponse(authenticated=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
