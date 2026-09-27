class RAGProException(Exception):
    """Base exception class for RAG Pro application."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class DocumentNotFoundError(RAGProException):
    def __init__(self, filename: str):
        super().__init__(f"Document '{filename}' not found.", status_code=404)

class InvalidDocumentError(RAGProException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class RetrievalError(RAGProException):
    def __init__(self, message: str):
        super().__init__(f"Retrieval failure: {message}", status_code=500)

class JobNotFoundError(RAGProException):
    def __init__(self, job_id: str):
        super().__init__(f"Job container '{job_id}' not found.", status_code=404)

class CandidateNotFoundError(RAGProException):
    def __init__(self, candidate_id: str):
        super().__init__(f"Candidate '{candidate_id}' not found.", status_code=404)

class AuthenticationError(RAGProException):
    def __init__(self, message: str = "Invalid credentials or token expired"):
        super().__init__(message, status_code=401)

class DatabaseError(RAGProException):
    def __init__(self, message: str):
        super().__init__(f"Database error: {message}", status_code=500)
