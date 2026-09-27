from app.agent.state import AgentState
from app.utils.logger import logger

def route_by_intent(state: AgentState) -> str:
    """Conditional routing function determining flow destination from analysis."""
    intent = state.get("intent", "PLAYBOOK_QA")
    logger.info(f"LangGraph Router evaluating intent: '{intent}'")
    return "tool_execution_node"

def check_human_approval_gate(state: AgentState) -> str:
    """Checks if state needs human approval intervention."""
    approval_required = state.get("approval_required", False)
    approval_status = state.get("approval_status", "none")
    
    if approval_required and approval_status == "pending":
        logger.info("Router: Pausing flow at Human Approval Gate.")
        return "response_generation_node"
        
    return "response_generation_node"
