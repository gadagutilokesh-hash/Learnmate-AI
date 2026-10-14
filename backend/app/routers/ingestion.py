import os
import shutil
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
from app.models.schema import DocumentResponse
from app.db.storage import storage
from app.core.config import settings
from app.core.gemini import gemini_service, sanitize_error
from app.core.auth import get_current_user, get_optional_user
from app.services.ingestion.pdf_parser import pdf_parser
from app.services.ingestion.pptx_parser import pptx_parser
from app.services.ingestion.video_parser import video_parser

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Ingestion"])

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".mp4": "mp4",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio"
}

def process_document_task(doc_id: str, file_path: str, file_type: str, course_id: str, topic: str):
    try:
        storage.update_document(doc_id, status="processing")
        # Ensure any stale chunks from previous failed runs are removed
        storage.delete_chunks_by_document(doc_id)
        chunks = []
        total_pages_or_slides = None
        duration_seconds = None

        if file_type == "pdf":
            chunks, total_pages_or_slides = pdf_parser.parse(file_path, default_topic=topic)
        elif file_type == "pptx":
            chunks, total_pages_or_slides = pptx_parser.parse(file_path, default_topic=topic)
        elif file_type in ("mp4", "audio"):
            chunks, duration_seconds = video_parser.parse(file_path, default_topic=topic)

        # Generate embeddings and prepare chunks
        formatted_chunks = []
        is_live = gemini_service.is_gemini_configured()
        for idx, c in enumerate(chunks):
            emb = gemini_service.get_embedding(c.content)
            chunk_meta = dict(c.metadata) if c.metadata else {}
            chunk_meta["is_pseudo"] = not is_live
            chunk_meta["embedding_model"] = gemini_service.embedding_model_name if is_live else "pseudo"
            chunk_meta["embedding_version"] = "v1"
            formatted_chunks.append({
                "document_id": doc_id,
                "course_id": course_id,
                "chunk_index": idx,
                "content": c.content,
                "chunk_type": c.chunk_type,
                "source_type": c.source_type,
                "page_number": c.page_number,
                "slide_number": c.slide_number,
                "start_timestamp": c.start_timestamp,
                "end_timestamp": c.end_timestamp,
                "topic": c.topic or topic,
                "concept": c.concept,
                "embedding": emb,
                "metadata": chunk_meta
            })

        storage.save_chunks(formatted_chunks, replace_for_document=True)
        storage.update_document(
            doc_id=doc_id,
            status="completed",
            total_pages_or_slides=total_pages_or_slides,
            duration_seconds=duration_seconds,
            error_message=None
        )
        logger.info(f"Successfully processed document {doc_id} with {len(formatted_chunks)} chunks.")
    except Exception as e:
        sanitized_msg = sanitize_error(e)
        logger.error(f"Error processing document {doc_id}: {sanitized_msg}", exc_info=True)
        # Purge any partial chunks on failure so document state is clean
        storage.delete_chunks_by_document(doc_id)
        storage.update_document(doc_id, status="failed", error_message=sanitized_msg)

@router.post("/courses/{course_id}/upload", response_model=DocumentResponse)
async def upload_document(
    course_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    topic: Optional[str] = Form("General Foundations"),
    current_user: dict = Depends(get_current_user)
):
    course = storage.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    is_admin = current_user.get("role") == "admin"

    # Enforce read-only restriction on shared demo courses
    if course.get("is_demo") or course.get("visibility") == "shared_demo":
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Shared demo courses are read-only. Create your own private course to upload documents."
            )

    # Enforce ownership on private courses
    if not is_admin and course.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Course not found")

    filename = file.filename or "upload"
    _, ext = os.path.splitext(filename.lower())

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, PPT, PPTX, MP4, MP3, WAV, M4A"
        )

    file_type = SUPPORTED_EXTENSIONS[ext]
    safe_filename = f"{course_id}_{filename.replace(' ', '_')}"
    save_path = os.path.join(settings.UPLOADS_DIR, safe_filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc_record = storage.create_document(
        course_id=course_id,
        filename=filename,
        file_type=file_type,
        file_path=save_path
    )

    # Process in background task
    background_tasks.add_task(
        process_document_task,
        doc_record["id"],
        save_path,
        file_type,
        course_id,
        topic or "General"
    )

    return DocumentResponse(
        id=doc_record["id"],
        course_id=course_id,
        filename=filename,
        file_type=file_type,
        ingestion_status="processing",
        chunks_count=0
    )

@router.get("/courses/{course_id}/documents", response_model=List[DocumentResponse])
def list_documents(course_id: str, optional_user: Optional[dict] = Depends(get_optional_user)):
    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False
    if not storage.is_course_accessible(course_id, user_id=user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Course not found")

    docs = storage.list_documents(course_id)
    return [DocumentResponse(**d) for d in docs]

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, optional_user: Optional[dict] = Depends(get_optional_user)):
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user_id = optional_user["id"] if optional_user else None
    is_admin = (optional_user.get("role") == "admin") if optional_user else False
    if not storage.is_course_accessible(doc["course_id"], user_id=user_id, is_admin=is_admin):
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(**doc)

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    course = storage.get_course(doc["course_id"])
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    is_admin = current_user.get("role") == "admin"
    if course.get("is_demo") or course.get("visibility") == "shared_demo":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Shared demo courses are read-only and documents cannot be deleted")

    if not is_admin and course.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Document not found")

    storage.delete_document(document_id)
    return {"deleted": True, "document_id": document_id}

@router.post("/documents/{document_id}/retry", response_model=DocumentResponse)
def retry_document_ingestion(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    course = storage.get_course(doc["course_id"])
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    is_admin = current_user.get("role") == "admin"
    if course.get("is_demo") or course.get("visibility") == "shared_demo":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Shared demo courses are read-only")

    if not is_admin and course.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Document not found")

    with storage._get_connection() as conn:
        row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (document_id,)).fetchone()
        file_path = row["file_path"] if row else None

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Original source file no longer found on server.")

    background_tasks.add_task(
        process_document_task,
        document_id,
        file_path,
        doc["file_type"],
        doc["course_id"],
        "Retry Ingestion"
    )

    return DocumentResponse(**doc)
