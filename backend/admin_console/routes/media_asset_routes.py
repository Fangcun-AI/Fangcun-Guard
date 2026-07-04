from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Query  # fcg-rewrite
from fastapi.responses import FileResponse  # fcg-rewrite
from typing import Optional  # fcg-rewrite
import uuid  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite
from config import settings  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.url_signature import (  # fcg-rewrite
    verify_media_url_signature,  # fcg-rewrite
    generate_signed_media_url  # fcg-rewrite
)

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Media"])  # fcg-rewrite

# Import authentication dependency (for upload, delete, list etc. authenticated interfaces)
# Note: Here we cannot directly import from main because it will cause a circular dependency
# We add authentication logic separately to each authenticated route

# Allowed image file types
ALLOWED_IMAGE_TYPES = {  # fcg-rewrite
    "image/jpeg", "image/jpg", "image/png", "image/gif",  # fcg-rewrite
    "image/bmp", "image/webp", "image/tiff"  # fcg-rewrite
}

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024  # fcg-rewrite

@router.post("/media/upload/image")  # fcg-rewrite
async def upload_image(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    file: UploadFile = File(...)  # fcg-rewrite
):
    """
    Upload image file

    The image file uploaded by the user will be stored in the /mnt/data/fangcunguard-data/media/{tenant_id}/ directory
    Return the relative path of the image, which can be used for subsequent detection requests
    """
    try:
        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        if auth_context:  # fcg-rewrite
            tenant_id = str(auth_context['data'].get('user_id'))  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite
        # Verify file type
        if file.content_type not in ALLOWED_IMAGE_TYPES:  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=400,  # fcg-rewrite
                detail=f"Unsupported file type: {file.content_type}. Supported types: {', '.join(ALLOWED_IMAGE_TYPES)}"  # fcg-rewrite
            )

        # Read file content
        file_content = await file.read()  # fcg-rewrite

        # Verify file size
        if len(file_content) > MAX_FILE_SIZE:  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=400,  # fcg-rewrite
                detail=f"File size exceeds limit: {len(file_content)} bytes > {MAX_FILE_SIZE} bytes (10MB)"  # fcg-rewrite
            )

        # Verify file is not empty
        if len(file_content) == 0:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="File content is empty")  # fcg-rewrite

        # Create user media directory
        user_media_dir = Path(settings.media_dir) / tenant_id  # fcg-rewrite
        user_media_dir.mkdir(parents=True, exist_ok=True)  # fcg-rewrite

        # Generate unique filename
        file_extension = Path(file.filename).suffix if file.filename else ".jpg"  # fcg-rewrite
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"  # fcg-rewrite
        file_path = user_media_dir / unique_filename  # fcg-rewrite

        # Save file
        with open(file_path, "wb") as f:  # fcg-rewrite
            f.write(file_content)  # fcg-rewrite

        logger.info(f"Image uploaded successfully: {file_path}")  # fcg-rewrite

        # Generate signed access URL
        signed_url = generate_signed_media_url(  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            filename=unique_filename,  # fcg-rewrite
            expires_in_seconds=86400  # 24 hours expiration  # fcg-rewrite
        )

        # Return file path (relative path and absolute path)
        return {  # fcg-rewrite
            "success": True,  # fcg-rewrite
            "file_path": str(file_path),  # fcg-rewrite
            "relative_path": f"{tenant_id}/{unique_filename}",  # fcg-rewrite
            "filename": unique_filename,  # fcg-rewrite
            "size": len(file_content),  # fcg-rewrite
            "content_type": file.content_type,  # fcg-rewrite
            "url": signed_url  # Signed access URL  # fcg-rewrite
        }

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Image upload error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")  # fcg-rewrite

@router.delete("/media/image/{filename}")  # fcg-rewrite
async def delete_image(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    filename: str  # fcg-rewrite
):
    """
    Delete the image uploaded by the user
    """
    try:
        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        if auth_context:  # fcg-rewrite
            tenant_id = str(auth_context['data'].get('user_id'))  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        # Build file path
        file_path = Path(settings.media_dir) / tenant_id / filename  # fcg-rewrite

        # Security check: ensure file is in user directory
        if not str(file_path).startswith(str(Path(settings.media_dir) / tenant_id)):  # fcg-rewrite
            raise HTTPException(status_code=403, detail="No permission to access this file")  # fcg-rewrite

        # Delete file
        if file_path.exists():  # fcg-rewrite
            file_path.unlink()  # fcg-rewrite
            logger.info(f"Image deleted successfully: {file_path}")  # fcg-rewrite
            return {"success": True, "message": "Image deleted successfully"}  # fcg-rewrite
        else:
            raise HTTPException(status_code=404, detail="Image does not exist")  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Image delete error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")  # fcg-rewrite

@router.get("/media/images")  # fcg-rewrite
async def list_images(request: Request):  # fcg-rewrite
    """
    List all images uploaded by the user
    """
    try:
        # Get user context
        auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        tenant_id = None  # fcg-rewrite
        if auth_context:  # fcg-rewrite
            tenant_id = str(auth_context['data'].get('user_id'))  # fcg-rewrite

        if not tenant_id:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="User ID not found in auth context")  # fcg-rewrite

        # User media directory
        user_media_dir = Path(settings.media_dir) / tenant_id  # fcg-rewrite

        # If directory does not exist, return empty list
        if not user_media_dir.exists():  # fcg-rewrite
            return {"images": []}  # fcg-rewrite

        # List all image files
        images = []  # fcg-rewrite
        for file_path in user_media_dir.iterdir():  # fcg-rewrite
            if file_path.is_file():  # fcg-rewrite
                stat = file_path.stat()  # fcg-rewrite
                # Generate signed access URL
                signed_url = generate_signed_media_url(  # fcg-rewrite
                    tenant_id=tenant_id,  # fcg-rewrite
                    filename=file_path.name,  # fcg-rewrite
                    expires_in_seconds=86400  # 24 hours expiration  # fcg-rewrite
                )
                images.append({  # fcg-rewrite
                    "filename": file_path.name,  # fcg-rewrite
                    "file_path": str(file_path),  # fcg-rewrite
                    "relative_path": f"{tenant_id}/{file_path.name}",  # fcg-rewrite
                    "size": stat.st_size,  # fcg-rewrite
                    "created_at": stat.st_ctime,  # fcg-rewrite
                    "url": signed_url  # Signed access URL  # fcg-rewrite
                })

        return {"images": images}  # fcg-rewrite

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"List images error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Get image list failed: {str(e)}")  # fcg-rewrite

@router.get("/media/image/{tenant_id}/{filename}")  # fcg-rewrite
async def get_image(  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    filename: str,  # fcg-rewrite
    token: str = Query(..., description="Signed token"),  # fcg-rewrite
    expires: int = Query(..., description="Expiration timestamp")  # fcg-rewrite
):
    """
    Get image file (requires signature verification)

    Return the image file based on the user ID and filename, requiring a valid signed token and expiration timestamp
    Image storage path: /mnt/data/fangcunguard-data/media/{tenant_id}/{filename}

    Query parameters:
        - token: Signed token
        - expires: Expiration timestamp
    """
    try:
        # Verify signature
        if not verify_media_url_signature(tenant_id, filename, token, expires):  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=403,  # fcg-rewrite
                detail="Signed token is invalid or expired"  # fcg-rewrite
            )

        # Build file path
        file_path = Path(settings.media_dir) / tenant_id / filename  # fcg-rewrite

        # Security check: ensure file is in media directory
        if not str(file_path).startswith(str(Path(settings.media_dir))):  # fcg-rewrite
            raise HTTPException(status_code=403, detail="No permission to access this file")  # fcg-rewrite

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():  # fcg-rewrite
            raise HTTPException(status_code=404, detail="File does not exist")  # fcg-rewrite

        # Dynamically set media type based on file extension
        media_type_map = {  # fcg-rewrite
            ".jpg": "image/jpeg",  # fcg-rewrite
            ".jpeg": "image/jpeg",  # fcg-rewrite
            ".png": "image/png",  # fcg-rewrite
            ".gif": "image/gif",  # fcg-rewrite
            ".bmp": "image/bmp",  # fcg-rewrite
            ".webp": "image/webp",  # fcg-rewrite
            ".tiff": "image/tiff"  # fcg-rewrite
        }
        file_extension = Path(filename).suffix.lower()  # fcg-rewrite
        media_type = media_type_map.get(file_extension, "image/jpeg")  # fcg-rewrite

        # Return image file
        return FileResponse(  # fcg-rewrite
            path=str(file_path),  # fcg-rewrite
            media_type=media_type,  # fcg-rewrite
            filename=filename  # fcg-rewrite
        )

    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Get image error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Get image failed: {str(e)}")  # fcg-rewrite
