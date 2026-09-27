from app.agent.state import AgentState
from app.utils.logger import logger

def response_generation_node(state: AgentState) -> AgentState:
    """Synthesizes final response for the user based on tool execution results."""
    logger.info("LangGraph Node [response_generation_node] synthesizing response")
    
    tool_result = state.get("tool_result", "")
    intent = state.get("intent", "GENERAL")
    logs = list(state.get("activity_logs", []))
    
    final_response = tool_result if tool_result else "No execution result available."
    logs.append({"step": "Workflow Complete", "detail": f"Agent finished execution for intent '{intent}'."})

    return {
        **state,
        "final_response": final_response,
        "activity_logs": logs
    }
