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

Use the Context below as your primary source. If it fully or partially answers the question,
base your answer on it and do not contradict it.

If the Context does NOT contain information relevant to the question, do this instead:
1. Say plainly that it wasn't found in the uploaded documents (e.g. "I couldn't find this in your
   uploaded documents.").
2. Then answer the question using your own general knowledge, clearly introduced with a label such
   as "Based on general knowledge:" so the user can tell this part did not come from their
   documents.

Never present a general-knowledge answer as if it came from the documents, and never invent or
imply a document citation for something the Context does not actually contain.

Context:
{context}

Conversation History:
{chat_history}

Question:
{question}

Answer:
""")

rag_chain = prompt_template | llm | StrOutputParser()

# Used when there is no document index at all yet (nothing uploaded) — lets the
# assistant still answer from general knowledge instead of refusing outright.
no_context_prompt_template = ChatPromptTemplate.from_template("""
You are a helpful assistant. No documents have been uploaded to the knowledge base yet, so there
is no document context available for this question.

Briefly note that no documents are indexed yet, then answer the question as best you can using
your own general knowledge.

Conversation History:
{chat_history}

Question:
{question}

Answer:
""")

no_context_chain = no_context_prompt_template | llm | StrOutputParser()
