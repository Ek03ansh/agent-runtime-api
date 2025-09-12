from fastapi import APIRouter, HTTPException
import subprocess
import asyncio
import re
import logging
import pty
import os
import select
import json
from pathlib import Path
from typing import Optional
from app.core.config import settings
from app.models import AuthLoginResponse, AuthStatusResponse, AuthInjectTokenRequest

# Set up logger for auth controller
logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Authentication timing constants
AUTH_TIMING = {
    'initial_wait': 4.0,       # Wait before typing
    'char_delay': 0.1,         # Delay between characters  
    'enter_delay': 1.0,        # Wait before pressing Enter
    'auth_timeout': 25,        # Device code extraction timeout
    'monitor_timeout': 600     # Background monitoring timeout (10 min)
}

GITHUB_DEVICE_URL = "https://github.com/login/device"

def clean_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text to make it readable"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def _get_github_copilot_refresh_token() -> Optional[str]:
    """Read GitHub Copilot refresh token from OpenCode auth.json file"""
    try:
        # Use the same path structure as the agent service
        opencode_storage_path = Path.home() / ".local" / "share" / "opencode"
        auth_file_path = opencode_storage_path / "auth.json"
        
        if not auth_file_path.exists():
            logger.debug(f"Auth file not found at {auth_file_path}")
            return None
        
        with open(auth_file_path, 'r', encoding='utf-8') as f:
            auth_data = json.load(f)
        
        # Extract GitHub Copilot refresh token
        github_copilot_auth = auth_data.get("github-copilot", {})
        refresh_token = github_copilot_auth.get("refresh")
        
        if refresh_token:
            logger.debug("Successfully retrieved GitHub Copilot refresh token")
            return refresh_token
        else:
            logger.debug("No refresh token found in auth data")
            return None
            
    except FileNotFoundError:
        logger.debug("OpenCode auth.json file not found")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse auth.json: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error reading refresh token: {e}")
        return None

def _inject_github_copilot_refresh_token(refresh_token: str) -> bool:
    """Inject/update GitHub Copilot refresh token in OpenCode auth.json file"""
    try:
        # Use the same path structure as the agent service
        opencode_storage_path = Path.home() / ".local" / "share" / "opencode"
        auth_file_path = opencode_storage_path / "auth.json"
        
        # Ensure the directory exists
        opencode_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing auth data or create new structure
        auth_data = {}
        if auth_file_path.exists():
            try:
                with open(auth_file_path, 'r', encoding='utf-8') as f:
                    auth_data = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read existing auth.json, creating new: {e}")
                auth_data = {}
        
        # Update/create GitHub Copilot auth entry
        if "github-copilot" not in auth_data:
            auth_data["github-copilot"] = {}
        
        auth_data["github-copilot"].update({
            "type": "oauth",
            "refresh": refresh_token,
            # Note: We don't set access token or expires as those will be handled by OpenCode
        })
        
        # Write updated auth data
        with open(auth_file_path, 'w', encoding='utf-8') as f:
            json.dump(auth_data, f, indent=2)
        
        logger.info("Successfully injected GitHub Copilot refresh token")
        return True
        
    except Exception as e:
        logger.error(f"Failed to inject refresh token: {e}")
        return False

# Store ongoing auth process
_auth_process = None

async def _monitor_auth_background(process, master_fd):
    """Monitor auth process in background after device code is returned"""
    try:
        start_time = asyncio.get_event_loop().time()
        max_wait_seconds = AUTH_TIMING['monitor_timeout']
        
        while (asyncio.get_event_loop().time() - start_time) < max_wait_seconds:
            try:
                ready, _, _ = select.select([master_fd], [], [], 1.0)  # 1 second timeout
                
                if ready:
                    data = os.read(master_fd, 1024).decode('utf-8', errors='replace')
                    if data:
                        clean_line = clean_ansi_codes(data).strip()
                        # Log only "Done" completion (specific message we know)
                        if "Done" in clean_line:
                            logger.info(f"🏁 AUTH COMPLETED: {clean_line}")
                            break
                            
            except (OSError, ValueError):
                # Process ended or PTY closed
                break
                
            await asyncio.sleep(1.0)
        
        # Cleanup
        try:
            os.close(master_fd)
            process.wait()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Background monitoring error: {e}")
        try:
            os.close(master_fd)
        except:
            pass

@router.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login():
    """Start OpenCode GitHub Copilot auth flow"""
    global _auth_process
    
    logger.info("Auth login request started")
    
    # Check OpenCode availability
    if not settings.opencode_available:
        raise HTTPException(
            status_code=500, 
            detail=f"OpenCode command not found: {settings.opencode_command}"
        )
    
    # Always clean up any previous process and start fresh
    if _auth_process:
        try:
            if _auth_process.poll() is None:  # Process still running
                logger.info("Terminating existing auth process to start fresh")
                _auth_process.terminate()
                try:
                    _auth_process.wait(timeout=2)  # Wait up to 2 seconds for graceful termination
                except subprocess.TimeoutExpired:
                    _auth_process.kill()  # Force kill if it doesn't terminate gracefully
        except:
            pass
    
    try:
        # Create PTY for interactive terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start auth process
        _auth_process = subprocess.Popen(
            [settings.opencode_command, "auth", "login"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        os.close(slave_fd)
        logger.info(f"Auth process started with PID: {_auth_process.pid}")
        
        # Wait and type "GitHub Copilot" (exact working sequence)
        await asyncio.sleep(AUTH_TIMING['initial_wait'])
        for char in 'GitHub Copilot':
            os.write(master_fd, char.encode())
            await asyncio.sleep(AUTH_TIMING['char_delay'])
        await asyncio.sleep(AUTH_TIMING['enter_delay'])
        os.write(master_fd, b'\r')
        
        # Monitor for device code and URL
        device_code = None
        verification_url = None
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < AUTH_TIMING['auth_timeout']:
            try:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                
                if ready:
                    data = os.read(master_fd, 1024).decode('utf-8', errors='replace')
                    clean_line = clean_ansi_codes(data).strip()
                    
                    # Extract device code (always format XXXX-XXXX after "Enter code:")
                    if not device_code and "Enter code:" in clean_line:
                        code_match = re.search(r'Enter code:\s*([A-Z0-9]{4}-[A-Z0-9]{4})', clean_line)
                        if code_match:
                            device_code = code_match.group(1)
                            logger.info(f"Found device code: {device_code}")
                    
                    # Extract verification URL (always same URL)
                    if not verification_url and GITHUB_DEVICE_URL in clean_line:
                        verification_url = GITHUB_DEVICE_URL
                        logger.info(f"Found verification URL: {verification_url}")
                    
                    # Return immediately when both found
                    if device_code and verification_url:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        logger.info(f"Got auth data after {elapsed:.1f} seconds")
                        
                        # Start background monitoring for completion
                        asyncio.create_task(_monitor_auth_background(_auth_process, master_fd))
                        
                        return AuthLoginResponse(
                            device_code=device_code,
                            verification_url=verification_url
                        )
                        
            except OSError:
                pass
            
            await asyncio.sleep(0.1)
        
        # Timeout - cleanup and return error
        logger.error("Timeout waiting for device code")
        try:
            os.close(master_fd)
            _auth_process.terminate()
        except:
            pass
        
        raise HTTPException(status_code=500, detail="Timeout waiting for authentication data")
            
    except Exception as e:
        logger.error(f"Auth process failed: {e}")
        if _auth_process:
            try:
                _auth_process.terminate()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check current OpenCode authentication status and return refresh token"""
    if not settings.opencode_available:
        raise HTTPException(
            status_code=500, 
            detail=f"OpenCode command not found: {settings.opencode_command}"
        )
    
    try:
        result = subprocess.run(
            [settings.opencode_command, "auth", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        
        # Check if GitHub Copilot is authenticated
        is_authenticated = (
            result.returncode == 0 and 
            result.stdout.strip() and
            "GitHub Copilot" in result.stdout and 
            "Commands:" not in result.stdout  # Not help text
        )
        
        # Get refresh token if authenticated
        refresh_token = None
        if is_authenticated:
            refresh_token = _get_github_copilot_refresh_token()
        
        return AuthStatusResponse(
            authenticated=is_authenticated,
            refreshToken=refresh_token
        )
            
    except subprocess.TimeoutExpired:
        return AuthStatusResponse(authenticated=False, refreshToken=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/auth", response_model=AuthStatusResponse)
async def inject_refresh_token(request: AuthInjectTokenRequest):
    """Inject GitHub Copilot refresh token and verify authentication"""
    if not settings.opencode_available:
        raise HTTPException(
            status_code=500, 
            detail=f"OpenCode command not found: {settings.opencode_command}"
        )
    
    try:
        # Inject the refresh token into auth.json
        success = _inject_github_copilot_refresh_token(request.refreshToken)
        
        if not success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to inject refresh token into auth.json"
            )
        
        # Verify authentication status after injection
        result = subprocess.run(
            [settings.opencode_command, "auth", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        
        # Check if GitHub Copilot is now authenticated
        is_authenticated = (
            result.returncode == 0 and 
            result.stdout.strip() and
            "GitHub Copilot" in result.stdout and 
            "Commands:" not in result.stdout  # Not help text
        )
        
        # Return the current status including the injected token
        return AuthStatusResponse(
            authenticated=is_authenticated,
            refreshToken=request.refreshToken if is_authenticated else None
        )
            
    except subprocess.TimeoutExpired:
        # Return failure status
        return AuthStatusResponse(authenticated=False, refreshToken=None)
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token injection failed: {str(e)}")

