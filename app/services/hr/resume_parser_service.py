import os
from langchain_core.documents import Document

from app.core.config import settings
from app.db import hr_db
from app.services.rag import vectorstore, get_text_splitter
from app.services.hr.jd_parser_service import extract_text_from_file
from app.utils.logger import logger

RESUME_DIR = os.path.join(settings.UPLOAD_DIR, "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)

def process_single_resume(job_id: str, candidate_id: str, filename: str, file_bytes: bytes) -> dict:
    """Batch worker processing a single candidate resume."""
    resume_file_path = os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
    
    try:
        with open(resume_file_path, "wb") as f:
            f.write(file_bytes)
            
        resume_text = extract_text_from_file(resume_file_path)
        if not resume_text:
            hr_db.save_candidate(candidate_id, job_id, filename, "", filename, status="failed_extraction")
            return {"candidate_id": candidate_id, "filename": filename, "status": "failed_extraction"}
            
        candidate_name = os.path.splitext(filename)[0].replace("_", " ").title()
        
        splitter = get_text_splitter()
        raw_docs = [Document(page_content=resume_text, metadata={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "candidate_name": candidate_name,
            "document": filename,
            "source": filename
        })]
        chunks = splitter.split_documents(raw_docs)
        
        for idx, chunk in enumerate(chunks, 1):
            chunk.metadata["page"] = (idx // 3) + 1
            chunk.metadata["section"] = "Resume Section"
            
        vectorstore.add_documents(chunks)
        
        hr_db.save_candidate(
            candidate_id=candidate_id,
            job_id=job_id,
            name=candidate_name,
            email="",
            filename=filename,
            status="success"
        )
        
        return {"candidate_id": candidate_id, "filename": filename, "status": "success", "chunks_count": len(chunks)}
        
    except Exception as e:
        logger.error(f"Failed processing resume '{filename}': {e}")
        hr_db.save_candidate(candidate_id, job_id, filename, "", filename, status=f"failed: {e}")
        return {"candidate_id": candidate_id, "filename": filename, "status": "failed", "error": str(e)}
