import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.schemas.rag_schemas import QueryRequest
from app.services import rag_service
from app.loaders.loader_factory import LOADER_MAPPING
from app.utils.logger import logger
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Accepts document upload, validates extension, saves file, and re-indexes."""
    logger.info(f"Upload request by user: '{current_user['username']}'")
    file_name = file.filename
    _, ext = os.path.splitext(file_name.lower())
    
    if ext not in LOADER_MAPPING:
        logger.warning(f"Rejected upload of unsupported file type: {file_name}")
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file extension '{ext}'. Supported extensions are: {', '.join(LOADER_MAPPING.keys())}"
        )
        
    file_path = os.path.join(rag_service.UPLOAD_DIR, file_name)
    logger.info(f"File upload request received: {file_name}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if os.path.getsize(file_path) == 0:
            os.remove(file_path)
            logger.warning(f"Rejected empty file upload: {file_name}")
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            
        logger.info(f"File saved successfully: {file_name}")
        
    except HTTPException as he:
        raise he
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Failed to save uploaded file {file_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
        
    try:
        rag_service.rebuild_retrievers()
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Error indexing document {file_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error indexing document: {e}")
        
    return {
        "status": "success",
        "message": f"Successfully uploaded and indexed '{file_name}'",
        "total_chunks": len(rag_service.all_documents)
    }

@router.get("/status")
def get_status():
    """Returns indexing status, uploaded files list, and chunk counts."""
    try:
        return rag_service.get_rag_status()
    except Exception as e:
        logger.error(f"Error getting RAG status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
def query_rag(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """Submits prompt to RAG service and returns answer + citations."""
    logger.info(f"Query request by user: '{current_user['username']}' | prompt: '{request.prompt[:60]}'")
    try:
        return rag_service.query_rag_service(request.prompt, request.chat_history)
    except ValueError as ve:
        logger.warning(f"Query validation warning: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"Query execution runtime error: {re}")
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        logger.error(f"Unexpected query error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {e}")

@router.post("/query/stream")
def stream_query_rag(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """Submits prompt to RAG service and streams response via SSE tokens."""
    logger.info(f"Stream query request by user: '{current_user['username']}' | prompt: '{request.prompt[:60]}'")
    try:
        return StreamingResponse(
            rag_service.stream_query_rag_service(request.prompt, request.chat_history),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Unexpected stream query error: {e}")
        raise HTTPException(status_code=500, detail=f"Error initiating streaming query: {e}")

@router.delete("/files/{filename}")
def delete_file(filename: str, current_user: dict = Depends(get_current_user)):
    """Deletes an uploaded file from disk, vector store, and index registry."""
    logger.info(f"Delete request for file: '{filename}' by user: '{current_user['username']}'")
    file_path = os.path.join(rag_service.UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    try:
        os.remove(file_path)
        logger.info(f"File deleted from disk: '{filename}'")
    except Exception as e:
        logger.error(f"Failed to delete file '{filename}' from disk: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

    rag_service.delete_file_chunks(filename)

    registry = rag_service.load_index_registry()
    if filename in registry:
        del registry[filename]
        rag_service.save_index_registry(registry)
        logger.info(f"Removed '{filename}' from index registry.")

    try:
        rag_service.rebuild_retrievers()
    except Exception as e:
        logger.error(f"Failed to rebuild retrievers after deleting '{filename}': {e}")

    return {
        "status": "success",
        "message": f"File '{filename}' deleted and removed from index.",
        "total_chunks": len(rag_service.all_documents)
    }
