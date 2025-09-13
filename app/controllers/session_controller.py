import logging
import mimetypes
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.core.config import settings
from app.models import SessionFile, SessionListResponse, SessionFilesResponse, ArtifactsUrl, UploadedArtifacts, UploadRequest
from app.services.azure_storage_service import AzureStorageService
from app.utils.file_utils import should_exclude_path, TEXT_FILE_ENCODING

router = APIRouter(tags=["sessions"])
logger = logging.getLogger(__name__)

def find_session_path(session_id: str) -> Optional[Path]:
    """Find session path across all app directories"""
    session_root = settings.session_root
    
    # Search for session across all app directories
    for app_dir in session_root.glob("app-*"):
        if app_dir.is_dir():
            potential_path = app_dir / session_id
            if potential_path.exists() and potential_path.is_dir():
                return potential_path
    
    return None

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions() -> SessionListResponse:
    """Get list of all available sessions"""
    sessions = set()
    session_root = settings.session_root
    
    # Search for sessions across all app directories
    for app_dir in session_root.glob("app-*"):
        if app_dir.is_dir():
            # Each subdirectory in app-* is a session
            for session_dir in app_dir.iterdir():
                if session_dir.is_dir():
                    sessions.add(session_dir.name)
    
    session_list = sorted(list(sessions))
    return SessionListResponse(
        sessions=session_list,
        total_sessions=len(session_list)
    )

@router.get("/sessions/{session_id}/files", response_model=SessionFilesResponse)
async def get_session_files(session_id: str) -> SessionFilesResponse:
    """Get files in session by session ID"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    files = []
    try:
        for file_path in session_path.rglob("*"):
            if file_path.is_file() and not should_exclude_path(file_path):
                try:
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(session_path)
                    
                    files.append(SessionFile(
                        name=file_path.name,
                        path=str(relative_path),
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        type="file"
                    ))
                except (OSError, PermissionError):
                    # Skip files we can't access
                    logger.debug(f"Skipping file due to access error: {file_path}")
                    continue
    except (OSError, PermissionError) as e:
        logger.error(f"Error listing session files in {session_path}: {e}")
    
    return SessionFilesResponse(
        files=files,
        total_files=len(files),
        session_id=session_id
    )

@router.get("/sessions/{session_id}/files/{file_path:path}")
async def download_session_file(session_id: str, file_path: str):
    """Download a specific file from session"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    full_file_path = session_path / file_path
    
    # Security check: ensure file is within session directory
    try:
        full_file_path.resolve().relative_to(session_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: file outside session directory")
    
    if not full_file_path.exists() or not full_file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type
    content_type, _ = mimetypes.guess_type(str(full_file_path))
    
    # For text files, return as plain text to display in browser
    if content_type and content_type.startswith('text/'):
        try:
            with open(full_file_path, 'r', encoding=TEXT_FILE_ENCODING) as f:
                content = f.read()
            return PlainTextResponse(content=content, media_type=content_type)
        except (UnicodeDecodeError, PermissionError):
            pass  # Fall back to file download
    
    return FileResponse(
        path=str(full_file_path),
        filename=full_file_path.name,
        media_type=content_type or 'application/octet-stream'
    )

@router.get("/sessions/{session_id}/download")
async def download_session_zip(session_id: str):
    """Download complete session folder as ZIP file"""
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create temporary ZIP file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    zip_path = temp_zip.name
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in session_path.rglob("*"):
                if file_path.is_file() and not should_exclude_path(file_path):
                    try:
                        relative_path = file_path.relative_to(session_path)
                        zipf.write(file_path, relative_path)
                    except (OSError, PermissionError):
                        continue
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session_id}_{timestamp}.zip"
        
        return FileResponse(
            path=zip_path,
            filename=filename,
            media_type='application/zip'
        )
        
    except Exception as e:
        Path(zip_path).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to create ZIP: {str(e)}")

@router.post("/sessions/{session_id}/upload", response_model=UploadedArtifacts)
async def upload_session_to_azure(session_id: str, request: UploadRequest) -> UploadedArtifacts:
    """
    Manually upload session ZIP to Azure Storage using SAS URL
    
    This endpoint allows manual upload of session artifacts independently of task completion.
    Useful for:
    - Re-uploading after modifications
    - Selective session backups  
    - Testing upload functionality
    - Manual artifact management
    """
    session_path = find_session_path(session_id)
    if not session_path:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Validate SAS URL format
    if not AzureStorageService.validate_sas_url(request.sas_url):
        raise HTTPException(status_code=400, detail="Invalid SAS URL format")
    
    # Create temporary ZIP file (reuse existing logic)
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    zip_path = temp_zip.name
    temp_zip.close()
    
    try:
        # Create ZIP file with session contents
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in session_path.rglob("*"):
                if file_path.is_file() and not should_exclude_path(file_path):
                    try:
                        relative_path = file_path.relative_to(session_path)
                        zipf.write(file_path, relative_path)
                    except (OSError, PermissionError):
                        logger.debug(f"Skipping file due to access error: {file_path}")
                        continue
        
        # Generate blob name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"session_{session_id}_{timestamp}.zip"
        
        # Upload to Azure Storage
        zip_file_path = Path(zip_path)
        blob_url = await AzureStorageService.upload_file_to_sas_url(
            file_path=zip_file_path,
            sas_url=request.sas_url,
            blob_name=blob_name
        )
        
        file_size = zip_file_path.stat().st_size
        logger.info(f"Successfully uploaded session {session_id} to Azure Storage: {blob_name} ({file_size} bytes)")
        
        # Return upload details
        return UploadedArtifacts(
            blob_url=blob_url,
            blob_name=blob_name,
            uploaded_at=datetime.now(),
            file_size=file_size
        )
        
    except Exception as e:
        logger.error(f"Failed to upload session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        # Clean up temporary ZIP file
        Path(zip_path).unlink(missing_ok=True)
