from fastapi import APIRouter, HTTPException
import subprocess
import asyncio
import re
from app.core.config import settings
from app.models import AuthLoginResponse, AuthStatusResponse

router = APIRouter(tags=["auth"])

def clean_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text to make it readable"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Store ongoing auth process
_auth_process = None
_auth_output = {"stdout": "", "stderr": "", "device_code": None, "verification_url": None}

async def _monitor_auth_process(process):
    """Monitor auth process and extract device code info"""
    global _auth_output
    
    try:
        # Read output line by line to capture device code
        while True:
            line = await asyncio.get_event_loop().run_in_executor(
                None, process.stdout.readline
            )
            if not line:
                break
                
            line = line.strip()
            if line:
                # Store raw output for processing but clean for display
                _auth_output["stdout"] += line + "\n"
                clean_line = clean_ansi_codes(line)
                
                # Better device code extraction using regex on clean text
                if not _auth_output["device_code"]:
                    # Look for patterns like "Enter code: XXXX-XXXX" or "code: XXXX-XXXX"
                    code_match = re.search(r'(?:Enter code|code):\s*([A-Z0-9]{4}-[A-Z0-9]{4})', clean_line, re.IGNORECASE)
                    if code_match:
                        _auth_output["device_code"] = code_match.group(1)
                
                # Extract GitHub device URL
                if "https://github.com/login/device" in clean_line:
                    _auth_output["verification_url"] = "https://github.com/login/device"
        
        # Wait for process completion
        returncode = await asyncio.get_event_loop().run_in_executor(
            None, process.wait
        )
        
    except Exception as e:
        _auth_output["stderr"] += f"Monitoring error: {str(e)}\n"

@router.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login():
    """Start OpenCode GitHub Copilot auth flow in background"""
    global _auth_process, _auth_output
    
    try:
        # Same availability check as agent service
        if not settings.opencode_available:
            raise HTTPException(
                status_code=500, 
                detail=f"OpenCode command not found: {settings.opencode_command}"
            )
        
        # Check if auth process already running
        if _auth_process and _auth_process.poll() is None:
            return AuthLoginResponse(
                device_code=_auth_output.get("device_code"),
                verification_url=_auth_output.get("verification_url")
            )
        
        # Clean up any previous process
        if _auth_process:
            try:
                _auth_process.terminate()
            except:
                pass
        
        # Reset output buffer
        _auth_output = {"stdout": "", "stderr": "", "device_code": None, "verification_url": None}
        
        # Start auth process in background
        cmd_args = [settings.opencode_command, "auth", "login"]
        
        _auth_process = subprocess.Popen(
            cmd_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # Send GitHub Copilot selection
        _auth_process.stdin.write("GitHub Copilot\n")
        _auth_process.stdin.flush()
        
        # Start monitoring in background
        asyncio.create_task(_monitor_auth_process(_auth_process))
        
        # Wait a moment for initial output and device code
        await asyncio.sleep(3)
        
        return AuthLoginResponse(
            device_code=_auth_output.get("device_code"),
            verification_url=_auth_output.get("verification_url")
        )
            
    except Exception as e:
        # Clean up on error
        if _auth_process:
            try:
                _auth_process.terminate()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to start auth process: {str(e)}")

@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check current OpenCode authentication status"""
    try:
        # Same availability check as agent service
        if not settings.opencode_available:
            raise HTTPException(
                status_code=500, 
                detail=f"OpenCode command not found: {settings.opencode_command}"
            )
        
        # Use 'auth list' command which shows authenticated providers
        # This is more reliable than 'auth status' which sometimes shows help
        result = subprocess.run(
            [settings.opencode_command, "auth", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        
        is_authenticated = result.returncode == 0 and result.stdout.strip()
        output = result.stdout.strip() if result.stdout else ""
        
        # Check if output contains actual providers or just help text
        has_providers = (
            is_authenticated and 
            "GitHub Copilot" in output and 
            not "Commands:" in output  # Not help text
        )
        
        return AuthStatusResponse(
            authenticated=has_providers
        )
            
    except subprocess.TimeoutExpired:
        return AuthStatusResponse(
            authenticated=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
    