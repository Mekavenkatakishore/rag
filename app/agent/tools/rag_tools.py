from langchain_core.tools import tool
from app.services import rag_service
from app.utils.logger import logger

@tool
def search_hr_knowledge(query: str) -> str:
    """
    Searches organizational playbooks, policy documents, and onboarding guides using hybrid semantic and keyword retrieval.
    Use this tool when answering policy, process, leave, compliance, or company guidelines questions.
    """
    logger.info(f"Agent executing tool 'search_hr_knowledge' with query: '{query}'")
    try:
        res = rag_service.query_rag_service(query)
        answer = res.get("answer", "No answer found.")
        citations = res.get("citations", [])
        
        citation_str = ""
        if citations:
            citation_str = "\n\nSources:\n" + "\n".join([f"- {c['source']} ({c['page']})" for c in citations])
            
        return f"{answer}{citation_str}"
    except Exception as e:
        logger.error(f"Error in search_hr_knowledge tool: {e}")
        return f"Error searching knowledge base: {e}"
