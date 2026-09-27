from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.llm_factory import get_llm

llm = get_llm(temperature=0.3)

condense_prompt_template = ChatPromptTemplate.from_template("""
Given the following conversation history and a follow-up question, rephrase the follow-up question to be a STANDALONE question that has all the context of the conversation. 
Do NOT answer the question. Just rephrase it and return ONLY the standalone question text. If the follow-up question is already a standalone question or if the conversation history is empty, return the follow-up question exactly as is.

Conversation History:
{chat_history}

Follow-up Question:
{question}

Standalone Question:
""")

condense_chain = condense_prompt_template | llm | StrOutputParser()

prompt_template = ChatPromptTemplate.from_template("""
You are an intelligent organizational playbook and troubleshooting assistant. 
Answer the user's question using ONLY the provided context.
If the answer is not in the context, say "I don't know based on the provided documents."

Context:
{context}

Conversation History:
{chat_history}

Question:
{question}

Answer:
""")

rag_chain = prompt_template | llm | StrOutputParser()
