import unittest
from app.agent.state import AgentState
from app.agent.graph import agent_graph
from app.agent.tools.rag_tools import search_hr_knowledge
from app.agent.tools.hr_tools import match_candidates, generate_interview_questions

class TestAgenticAIGraph(unittest.TestCase):

    def test_rag_tool_execution(self):
        """Tests search_hr_knowledge tool execution."""
        res = search_hr_knowledge.invoke({"query": "onboarding policy"})
        self.assertIsInstance(res, str)

    def test_hr_match_tool(self):
        """Tests match_candidates tool execution."""
        res = match_candidates.invoke({"job_id": "default_job_001"})
        self.assertIsInstance(res, str)

    def test_agent_graph_invocation(self):
        """Tests full LangGraph invocation for PLAYBOOK_QA intent."""
        config = {"configurable": {"thread_id": "test_unit_thread_001"}}
        initial_state = {
            "user_query": "What is our leave policy?",
            "messages": [("user", "What is our leave policy?")],
            "job_id": "default_job_001",
            "approval_required": False,
            "approval_status": "none",
            "activity_logs": []
        }
        final_state = agent_graph.invoke(initial_state, config=config)
        self.assertEqual(final_state["intent"], "PLAYBOOK_QA")
        self.assertIn("activity_logs", final_state)
        self.assertGreater(len(final_state["activity_logs"]), 0)

if __name__ == "__main__":
    unittest.main()
