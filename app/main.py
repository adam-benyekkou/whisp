from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta
from typing import Optional
import os
import uuid
import aiofiles
import json
from pathlib import Path
from cryptography.fernet import Fernet
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.db.session import engine, get_db
from app.db.models import Base, Whisp
from app.api import schemas
from app.core.security import get_password_hash, verify_password

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# Path configuration
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = os.getenv("STORAGE_DIR", "/app/data/storage")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))
os.makedirs(STORAGE_DIR, exist_ok=True)

app = FastAPI(
    title="Whisp API",
    root_path=os.getenv("ROOT_PATH", "")
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve directories relative to this file
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Verify directories exist for production stability
if not STATIC_DIR.exists():
    print(f"CRITICAL ERROR: Static directory not found at {STATIC_DIR}")
if not TEMPLATES_DIR.exists():
    print(f"CRITICAL ERROR: Templates directory not found at {TEMPLATES_DIR}")

print(f"Startup: BASE_DIR={BASE_DIR}")
print(f"Startup: STATIC_DIR={STATIC_DIR}")
print(f"Startup: TEMPLATES_DIR={TEMPLATES_DIR}")
print(f"Startup: STORAGE_DIR={STORAGE_DIR}")

# Mount static files and templates with absolute paths
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

async def cleanup_expired_whisps(db: AsyncSession):
    """
    Background task to clean up expired whisps from the database.
    
    Args:
        db (AsyncSession): The database session.
    """
    await db.execute(delete(Whisp).where(Whisp.expires_at < datetime.utcnow()))
    await db.commit()

@app.on_event("startup")
async def startup():
    """
    Startup event handler to initialize the database tables.
    """
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Kubernetes"""
    return {
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat(),
        "env": {
            "STORAGE_DIR": STORAGE_DIR,
            "BASE_DIR": str(BASE_DIR),
            "ROOT_PATH": app.root_path
        }
    }

@app.api_route("/debug-path/{full_path:path}")
async def debug_request(request: Request, full_path: str):
    """Catch-all debug endpoint to see what Traefik is sending"""
    return {
        "path": full_path,
        "method": request.method,
        "headers": dict(request.headers),
        "url": str(request.url),
        "base_url": str(request.base_url),
        "scope_path": request.scope.get("path"),
        "root_path": request.scope.get("root_path")
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint without templates"""
    return "pong"

@app.get("/")
async def read_index(request: Request):
    """
    Serve the main creation page.
    
    Args:
        request (Request): The incoming request.
        
    Returns:
        TemplateResponse: The rendered create.html template.
    """
    return templates.TemplateResponse("create.html", {"request": request})

@app.get("/reveal")
async def read_reveal(request: Request):
    """
    Serve the secret reveal page.
    
    Args:
        request (Request): The incoming request.
        
    Returns:
        TemplateResponse: The rendered reveal.html template.
    """
    return templates.TemplateResponse("reveal.html", {"request": request})

def delete_file(path: str):
    """
    Helper function to delete a file from the filesystem.
    
    Args:
        path (str): Absolute path to the file.
    """
    if os.path.exists(path):
        os.remove(path)

@app.post("/api/whisps", response_model=schemas.WhispRead)
@limiter.limit("50/minute")
async def create_whisp(
    request: Request,
    background_tasks: BackgroundTasks,
    encrypted_payload: str = Form(...),
    ttl_minutes: int = Form(60),
    password: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint to create a new whisp (text or file).
    
    The payload is expected to be encrypted client-side for text whisps.
    For files, the server performs encryption at rest.
    
    Args:
        request (Request): Incoming request (for rate limiting).
        background_tasks (BackgroundTasks): Task manager for cleanup.
        encrypted_payload (str): Encrypted secret or file metadata.
        ttl_minutes (int): Minutes until auto-destruction.
        password (Optional[str]): Optional server-side passphrase.
        file (Optional[UploadFile]): Optional file attachment.
        db (AsyncSession): Database session.
        
    Returns:
        Whisp: The created whisp metadata.
    """

    # Validate TTL
    if ttl_minutes < 1 or ttl_minutes > 10080:  # Max 1 week
        raise HTTPException(status_code=400, detail="TTL must be between 1 minute and 1 week")
    
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    
    password_hash = None
    if password:
        password_hash = get_password_hash(password)
        
    whisp_id = str(uuid.uuid4())
    file_path = None
    final_payload = encrypted_payload
    
    if file:
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(file.filename or "unnamed")
        file_path = os.path.join(STORAGE_DIR, f"{whisp_id}_{safe_filename}.enc")
        
        # Generate encryption key for this file (Encryption at Rest)
        key = Fernet.generate_key()
        f = Fernet(key)
        
        # Store metadata + key in encrypted_payload field
        # The client sent the filename as 'encrypted_payload', we wrap it
        metadata = {
            "filename": encrypted_payload, # Client sent filename here
            "key": key.decode('utf-8')
        }
        final_payload = json.dumps(metadata)
        
        # Stream file write with encryption
        total_size = 0
        CHUNK_SIZE = 1024 * 1024  # 1MB chunks
        
        try:
            async with aiofiles.open(file_path, "wb") as buffer:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE:
                        # Clean up partial file immediately
                        await buffer.close()
                        os.remove(file_path)
                        raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_FILE_SIZE} bytes")
                    
                    # Encrypt chunk
                    # Note: Fernet is not stream-friendly by default (adds padding/integrity). 
                    # For strict streaming we'd use AES-GCM directly or encrypt small blocks.
                    # Given 10MB limit, encrypting chunks individually is messy. 
                    # Better: Read full into memory (10MB is acceptable) -> Encrypt -> Write.
                    # Or use a stream cipher. Fernet wraps AES-CBC+HMAC.
                    # Let's pivot: Since we have 10MB limit, loading 10MB into RAM to encrypt safely is OK.
                    pass
            
            # Re-implementing with full read for safety with Fernet (10MB limit makes this safe)
            await file.seek(0)
            content = await file.read() 
            if len(content) > MAX_FILE_SIZE:
                 raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_FILE_SIZE} bytes")
            
            encrypted_content = f.encrypt(content)
            async with aiofiles.open(file_path, "wb") as buffer:
                await buffer.write(encrypted_content)
                
        except Exception as e:
            # Ensure cleanup on any error if file was created
            if os.path.exists(file_path):
                os.remove(file_path)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail="File upload failed")
            
    new_whisp = Whisp(
        id=whisp_id,
        encrypted_payload=final_payload,
        is_file=bool(file),
        file_path=file_path,
        password_hash=password_hash,
        expires_at=expires_at
    )
    
    db.add(new_whisp)
    await db.commit()
    await db.refresh(new_whisp)
    
    # Schedule background cleanup
    background_tasks.add_task(cleanup_expired_whisps, db)
    
    return new_whisp

@app.get("/api/whisps/{whisp_id}")
@limiter.limit("100/minute")
async def get_whisp(
    request: Request,
    whisp_id: str,
    password: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve metadata for a specific whisp.
    
    Implements one-time access: text whisps are deleted immediately upon retrieval.
    
    Args:
        request (Request): Incoming request.
        whisp_id (str): UUID of the whisp.
        password (Optional[str]): Server-side passphrase if required.
        db (AsyncSession): Database session.
        
    Returns:
        WhispRead: Whisp metadata.
    """
    result = await db.execute(select(Whisp).where(Whisp.id == whisp_id))
    whisp = result.scalars().first()
    
    # Check if exists and not expired
    if not whisp or whisp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Whisp not found or expired")
    
    if whisp.password_hash:
        if not password or not verify_password(password, whisp.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
    
    # One-time access: delete after retrieval (if it's just a message)
    # If it's a file, we keep it until the file is downloaded
    data = schemas.WhispRead.model_validate(whisp)
    
    if not whisp.is_file:
        await db.delete(whisp)
        if whisp.file_path and os.path.exists(whisp.file_path):
            os.remove(whisp.file_path)
        await db.commit()
    
    return data

@app.get("/api/whisps/{whisp_id}/file")
@limiter.limit("100/minute")
async def get_whisp_file(
    request: Request,
    whisp_id: str,
    background_tasks: BackgroundTasks,
    password: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Download and decrypt a file artifact.
    
    Implements one-time access: the whisp and file are deleted after download.
    
    Args:
        request (Request): Incoming request.
        whisp_id (str): UUID of the whisp.
        background_tasks (BackgroundTasks): Task manager for cleanup.
        password (Optional[str]): Server-side passphrase if required.
        db (AsyncSession): Database session.
        
    Returns:
        Response: Decrypted file content.
    """

    result = await db.execute(select(Whisp).where(Whisp.id == whisp_id))
    whisp = result.scalars().first()
    
    # Check if exists, is file, not expired
    if not whisp or not whisp.is_file or not whisp.file_path or whisp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    # Verify file actually exists on disk
    if not os.path.exists(whisp.file_path):
        await db.delete(whisp)
        await db.commit()
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    if whisp.password_hash:
        if not password or not verify_password(password, whisp.password_hash):
            raise HTTPException(status_code=401, detail="Invalid password")
            
    file_path = whisp.file_path
    
    # Retrieve encryption key and filename from payload
    try:
        metadata = json.loads(whisp.encrypted_payload)
        encryption_key = metadata.get("key")
        filename = metadata.get("filename")
    except:
        # Fallback for old unencrypted files (if any)
        encryption_key = None
        filename = "downloaded_file"

    content = None
    if encryption_key:
        # Decrypt file
        f = Fernet(encryption_key.encode('utf-8'))
        async with aiofiles.open(file_path, "rb") as buffer:
            encrypted_content = await buffer.read()
            content = f.decrypt(encrypted_content)
    else:
        # Serve plaintext (legacy or error)
        async with aiofiles.open(file_path, "rb") as buffer:
            content = await buffer.read()

    # Delete from DB immediately (one-time access)
    await db.delete(whisp)
    await db.commit()
    
    # Delete file from disk after sending
    background_tasks.add_task(delete_file, file_path)
    
    # Serve decrypted content
    return Response(
        content=content, 
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
