"""
Azure Storage Service for uploading artifacts to user-provided SAS URLs
"""
import logging
from pathlib import Path
from typing import Optional
from azure.storage.blob import BlobClient
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

class AzureStorageService:
    """Service for uploading files to Azure Blob Storage using SAS URLs"""
    
    @staticmethod
    async def upload_file_to_sas_url(file_path: Path, sas_url: str, blob_name: Optional[str] = None) -> str:
        """
        Upload a file to Azure Blob Storage using a SAS URL
        
        Args:
            file_path: Path to the local file to upload
            sas_url: Complete SAS URL for the container with write permissions
            blob_name: Optional blob name. If not provided, uses the file name
            
        Returns:
            The full URL to the uploaded blob
            
        Raises:
            Exception: If upload fails
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Use file name as blob name if not specified
            if not blob_name:
                blob_name = file_path.name
            
            # Create blob client using the SAS URL
            # We need to insert the blob name between the container path and query parameters
            if '?' in sas_url:
                # Split the URL at the query parameters
                base_url, query_params = sas_url.split('?', 1)
                # Ensure base_url ends with container name and add blob name
                if base_url.endswith('/'):
                    full_blob_url = f"{base_url}{blob_name}?{query_params}"
                else:
                    full_blob_url = f"{base_url}/{blob_name}?{query_params}"
            else:
                # No query parameters, simple append
                if sas_url.endswith('/'):
                    full_blob_url = f"{sas_url}{blob_name}"
                else:
                    full_blob_url = f"{sas_url}/{blob_name}"
            
            logger.info(f"Uploading {file_path} to Azure Blob Storage: {blob_name}")
            
            # Create blob client and upload
            blob_client = BlobClient.from_blob_url(full_blob_url)
            
            with open(file_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)
            
            # Return the blob URL (without SAS token for security)
            blob_url_without_sas = full_blob_url.split('?')[0]
            
            logger.info(f"Successfully uploaded {file_path} to {blob_url_without_sas}")
            return blob_url_without_sas
            
        except AzureError as e:
            logger.error(f"Azure Storage error uploading {file_path}: {e}")
            raise Exception(f"Failed to upload to Azure Storage: {str(e)}")
        except Exception as e:
            logger.error(f"Error uploading {file_path} to Azure Storage: {e}")
            raise Exception(f"Upload failed: {str(e)}")
    
    @staticmethod
    def validate_sas_url(sas_url: str) -> bool:
        """
        Basic validation of SAS URL format
        
        Args:
            sas_url: The SAS URL to validate
            
        Returns:
            True if URL appears to be a valid SAS URL
        """
        try:
            # Basic checks for SAS URL format
            if not sas_url.startswith('https://'):
                return False
            
            if '.blob.core.windows.net' not in sas_url:
                return False
            
            if 'sig=' not in sas_url:
                return False
                
            return True
        except Exception:
            return False
