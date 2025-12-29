# utils/files.py
from fastapi import UploadFile
import os
import uuid
import hashlib
from typing import Dict

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/topo_staging")

def validate_file(file: UploadFile) -> dict:
    """Valide un fichier uploadé"""
    errors = []
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    allowed_ext = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'webp']
    if ext not in allowed_ext:
        errors.append(f"Extension .{ext} non autorisée")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "file_info": {
            "original_name": file.filename,
            "extension": ext,
            "mime_type": file.content_type or "application/octet-stream"
        }
    }

async def save_file(file: UploadFile, category: str, import_id: int) -> Dict:
    """Sauvegarde un fichier uploadé"""
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'bin'
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    
    storage_dir = os.path.join(UPLOAD_DIR, str(import_id))
    os.makedirs(storage_dir, exist_ok=True)
    
    storage_path = os.path.join(storage_dir, stored_name)
    
    content = await file.read()
    file_size = len(content)
    
    max_size = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise ValueError(f"Fichier trop volumineux ({file_size} > {max_size})")
    
    file_hash = hashlib.sha256(content).hexdigest()
    
    with open(storage_path, "wb") as f:
        f.write(content)
    
    return {
        "stored_name": stored_name,
        "storage_path": storage_path,
        "file_hash": file_hash,
        "file_size": file_size
    }