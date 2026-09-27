from langchain_core.prompts import ChatPromptTemplate

INTENT_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an intelligent HR & Playbook AI router. Analyze the user prompt and extract intent and context entities."),
    ("user", """Classify the user prompt into exactly ONE intent category and extract relevant parameters.

Categories:
- PLAYBOOK_QA: Questions about company policies, leave, guidelines, onboarding, benefits, troubleshooting.
- CANDIDATE_MATCHING: Requests to evaluate, score, rank, match, or list top candidates for a job role.
- CANDIDATE_DETAILS: Requests for score breakdown, matched/missing skills, or evidence for a specific candidate.
- INTERVIEW_GEN: Requests to generate interview questions or interview preparation for a candidate.
- EMAIL_GEN: Requests to draft or prepare an outreach email to a candidate.
- HR_ACTION: Requests to send emails or execute external actions.
- GENERAL: General greetings or questions.

User Prompt: {user_query}

Return ONLY a JSON object:
{{
  "intent": "PLAYBOOK_QA",
  "job_id": "default_job_001",
  "candidate_id": "C001",
  "reasoning": "Brief explanation"
}}
""")
])
