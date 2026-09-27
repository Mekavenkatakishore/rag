from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of speaker ('user' or 'assistant')")
    content: str = Field(..., description="Text content of message")

class QueryRequest(BaseModel):
    prompt: str = Field(..., description="User query prompt")
    chat_history: List[ChatMessage] = Field(default_factory=list, description="Recent conversational memory context")

class CitationResponse(BaseModel):
    source: str
    page: int
    content: Optional[str] = None

class RAGQueryResponse(BaseModel):
    answer: str
    citations: List[CitationResponse] = Field(default_factory=list)

class StatusResponse(BaseModel):
    total_documents: int
    uploaded_files: List[str]
    index_status: str

class FileUploadResponse(BaseModel):
    status: str
    message: str
    total_chunks: int

class FileDeleteResponse(BaseModel):
    status: str
    message: str
    total_chunks: int
