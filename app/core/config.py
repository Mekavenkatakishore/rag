import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from root .env file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings:
    # Project Info
    PROJECT_NAME: str = "Intelligent Hybrid RAG & HR Candidate Matching Platform"
    VERSION: str = "2.0.0"
    
    # API & Core Paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploaded_files"))
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", os.path.join(BASE_DIR, "chroma_db"))
    HR_DATABASE_PATH: str = os.getenv("HR_DATABASE_PATH", os.path.join(BASE_DIR, "app", "db", "hr_system.db"))
    USER_DATABASE_PATH: str = os.getenv("USER_DATABASE_PATH", os.path.join(BASE_DIR, "app", "db", "users.db"))
    
    # Security & Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "rag_pro_dev_secret_change_in_production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_TOKEN_EXPIRE_HOURS: int = int(os.getenv("JWT_TOKEN_EXPIRE_HOURS", "24"))
    
    # Groq & LLM Config
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # Embedding & Reranker Models
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "ms-marco-MiniLM-L-6-v2")
    
    # Retrieval Tuning
    CHUNKING_STRATEGY: str = os.getenv("CHUNKING_STRATEGY", "recursive")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    RETRIEVER_TOP_K: int = int(os.getenv("RETRIEVER_TOP_K", "15"))
    RERANKER_TOP_N: int = int(os.getenv("RERANKER_TOP_N", "4"))
    HYBRID_SEMANTIC_WEIGHT: float = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.5"))
    HYBRID_KEYWORD_WEIGHT: float = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.5"))

settings = Settings()
