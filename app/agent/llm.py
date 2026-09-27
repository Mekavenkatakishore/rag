"""
app/agent/llm.py
────────────────
Re-exports the centralized ChatGroq LLM factory from app.core.llm_factory.
Maintains architectural rule: Agent uses core infrastructure without duplication.
"""

from app.core.llm_factory import get_llm

__all__ = ["get_llm"]
