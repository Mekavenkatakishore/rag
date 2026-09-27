import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

SAMPLE_TEXT = """
Employee Onboarding Policy

All new employees are required to complete onboarding within the first two weeks of joining 
the organization. This includes attending orientation sessions, completing HR paperwork, 
and setting up their workstation with the IT department. Managers must assign a buddy to 
each new hire to help them navigate the company culture and processes.
"""

def benchmark_chunking():
    doc = Document(page_content=SAMPLE_TEXT, metadata={"source": "test_document.txt"})
    recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    recursive_chunks = recursive_splitter.split_documents([doc])
    print(f"RecursiveCharacterTextSplitter Chunks: {len(recursive_chunks)}")

if __name__ == "__main__":
    benchmark_chunking()
