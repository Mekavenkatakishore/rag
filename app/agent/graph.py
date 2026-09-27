from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import AgentState
from app.agent.nodes import (
    analyze_query_node,
    tool_execution_node,
    response_generation_node,
)
from app.agent.router import route_by_intent
from app.utils.logger import logger

def build_agent_graph():
    """Assembles and compiles the Agentic AI StateGraph workflow."""
    logger.info("Building LangGraph StateGraph workflow...")
    
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("analyze_query_node", analyze_query_node)
    workflow.add_node("tool_execution_node", tool_execution_node)
    workflow.add_node("response_generation_node", response_generation_node)

    # 2. Add Edges
    workflow.add_edge(START, "analyze_query_node")
    workflow.add_conditional_edges(
        "analyze_query_node",
        route_by_intent,
        {"tool_execution_node": "tool_execution_node"}
    )
    workflow.add_edge("tool_execution_node", "response_generation_node")
    workflow.add_edge("response_generation_node", END)

    # 3. Memory Checkpointer
    checkpointer = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph workflow successfully built and compiled with MemorySaver checkpointer.")
    return compiled_graph

# Global compiled agent graph instance
agent_graph = build_agent_graph()
