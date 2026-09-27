from langchain_core.documents import Document
from flashrank import Ranker
from app.services.rag import vectorstore
from app.utils.logger import logger

def retrieve_candidate_evidence(job_id: str, candidate_id: str, jd_requirements: dict) -> list[Document]:
    """Retrieves evidence chunks for a candidate filtered by candidate_id and FlashRank reranked."""
    skills_query = " ".join(jd_requirements.get("required_skills", []) + jd_requirements.get("preferred_skills", []))
    query_text = f"{jd_requirements.get('title', '')} {skills_query}"
    
    try:
        retrieved_docs = vectorstore.similarity_search(
            query=query_text,
            k=15,
            filter={"candidate_id": candidate_id}
        )
        
        if not retrieved_docs:
            return []
            
        try:
            ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
            passages = [
                {"id": idx, "text": doc.page_content, "meta": doc.metadata}
                for idx, doc in enumerate(retrieved_docs)
            ]
            rerank_request = {"query": query_text, "passages": passages}
            rerank_results = ranker.rank(rerank_request)
            
            top_docs = []
            for r in rerank_results[:6]:
                top_docs.append(Document(page_content=r["text"], metadata=r["meta"]))
            return top_docs
        except Exception as re:
            logger.warning(f"FlashRank reranker fallback for candidate {candidate_id}: {re}")
            return retrieved_docs[:6]
            
    except Exception as e:
        logger.error(f"Error retrieving candidate evidence for {candidate_id}: {e}")
        return []
