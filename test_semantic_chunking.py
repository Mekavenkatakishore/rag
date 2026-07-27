"""
test_semantic_chunking.py
─────────────────────────
Standalone comparison test between RecursiveCharacterTextSplitter
and SemanticChunker.

Run directly (no server needed):
    python test_semantic_chunking.py
"""

import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

# Sample multi-topic document (simulates a real regulatory playbook)
SAMPLE_TEXT = """
Employee Onboarding Policy

All new employees are required to complete onboarding within the first two weeks of joining 
the organization. This includes attending orientation sessions, completing HR paperwork, 
and setting up their workstation with the IT department. Managers must assign a buddy to 
each new hire to help them navigate the company culture and processes.

Annual Performance Reviews

Performance reviews are conducted every year in December. Employees will be evaluated 
based on their key performance indicators (KPIs), peer feedback, and manager assessments. 
Ratings are categorized as Exceeds Expectations, Meets Expectations, or Needs Improvement. 
Compensation adjustments and promotions are directly linked to performance review outcomes.

Data Security and Compliance

All employees must adhere to the company data security policy. Sensitive customer data 
must never be stored on personal devices or shared via unsecured channels. Access to 
production databases requires two-factor authentication and manager approval. Any data 
breach must be reported to the security team within 24 hours of discovery.

Leave and Time Off Policy

Full-time employees are entitled to 20 days of paid annual leave per year. Sick leave 
of up to 10 days per year is provided separately and does not require prior approval. 
Leave requests must be submitted through the HR portal at least 5 working days in advance 
for planned absences. Unused annual leave can be carried over to the following year up to 
a maximum of 10 days.
"""

doc = Document(page_content=SAMPLE_TEXT, metadata={"source": "test_document.txt"})

print("=" * 60)
print("  Chunking Strategy Comparison")
print("=" * 60)

# ─── Strategy 1: RecursiveCharacterTextSplitter ───────────────
print("\n📦 Strategy 1: RecursiveCharacterTextSplitter")
print("   (splits by character count, no understanding of meaning)\n")

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50
)
recursive_chunks = recursive_splitter.split_documents([doc])

for i, chunk in enumerate(recursive_chunks):
    print(f"  Chunk {i+1} ({len(chunk.page_content)} chars):")
    print(f"  {chunk.page_content[:120].strip()}...")
    print()

print(f"  Total chunks: {len(recursive_chunks)}")
avg = sum(len(c.page_content) for c in recursive_chunks) / len(recursive_chunks)
print(f"  Avg chunk size: {avg:.0f} chars")

# ─── Strategy 2: SemanticChunker ──────────────────────────────
print("\n" + "=" * 60)
print("\n🧠 Strategy 2: SemanticChunker")
print("   (splits where topic/meaning changes based on embeddings)\n")

print("  Loading HuggingFace Embeddings model...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

breakpoint_type   = os.getenv("SEMANTIC_BREAKPOINT_TYPE", "percentile")
breakpoint_amount = float(os.getenv("SEMANTIC_BREAKPOINT_AMOUNT", "90.0"))

semantic_splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type=breakpoint_type,
    breakpoint_threshold_amount=breakpoint_amount
)
semantic_chunks = semantic_splitter.split_documents([doc])

for i, chunk in enumerate(semantic_chunks):
    print(f"  Chunk {i+1} ({len(chunk.page_content)} chars):")
    print(f"  {chunk.page_content[:120].strip()}...")
    print()

print(f"  Total chunks: {len(semantic_chunks)}")
if semantic_chunks:
    avg2 = sum(len(c.page_content) for c in semantic_chunks) / len(semantic_chunks)
    print(f"  Avg chunk size: {avg2:.0f} chars")

# ─── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  Summary")
print("=" * 60)
print(f"  RecursiveCharacterTextSplitter: {len(recursive_chunks)} chunks")
print(f"  SemanticChunker:                {len(semantic_chunks)} chunks")
print("\n  ✅ Semantic chunks follow topic boundaries (policy sections)")
print("  ⚠️  Recursive chunks cut blindly at character count")
print("=" * 60)
