from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    intent: str
    job_id: Optional[str]
    candidate_id: Optional[str]
    selected_tool: Optional[str]
    tool_input: Optional[Dict[str, Any]]
    tool_result: Optional[str]
    approval_required: bool
    approval_status: str
    activity_logs: List[Dict[str, str]]
    final_response: Optional[str]
