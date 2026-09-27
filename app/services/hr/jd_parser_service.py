import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.llm_factory import get_llm
from app.loaders.loader_factory import get_document_loader
from app.services.hr.skill_normalization_service import normalize_skill_list
from app.utils.logger import logger

def extract_text_from_file(file_path: str) -> str:
    """Extracts raw text from JD or resume file."""
    try:
        loader = get_document_loader(file_path)
        docs = loader.load()
        return "\n\n".join([doc.page_content for doc in docs if doc.page_content])
    except Exception as e:
        logger.error(f"Error reading file '{file_path}': {e}")
        return ""

def parse_job_description(jd_text: str, filename: str) -> dict:
    """Extracts structured JD requirements via Groq LLM."""
    if not jd_text:
        return {
            "title": filename,
            "required_skills": [],
            "preferred_skills": [],
            "min_experience_years": 0,
            "preferred_experience_years": 0,
            "education": [],
            "responsibilities": [],
            "domain": [],
            "summary": "Empty or unreadable JD file."
        }

    llm = get_llm(temperature=0.1)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert HR recruiter. Extract structured information from this Job Description (JD). Return ONLY valid JSON format without markdown code fences."),
        ("user", """Extract the following JSON structure from this Job Description:
{{
  "title": "Job Role Title",
  "required_skills": ["Skill1", "Skill2"],
  "preferred_skills": ["SkillA", "SkillB"],
  "min_experience_years": 3,
  "preferred_experience_years": 5,
  "education": ["Degree1"],
  "responsibilities": ["Responsibility 1", "Responsibility 2"],
  "domain": ["Software Engineering"],
  "summary": "Brief role summary"
}}

Job Description Text:
{jd_text}
""")
    ])

    chain = prompt | llm | StrOutputParser()
    try:
        response_text = chain.invoke({"jd_text": jd_text[:4000]})
        clean_text = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean_text)
        
        parsed["required_skills"] = normalize_skill_list(parsed.get("required_skills", []))
        parsed["preferred_skills"] = normalize_skill_list(parsed.get("preferred_skills", []))
        return parsed
    except Exception as e:
        logger.error(f"Failed to parse JD JSON via LLM: {e}")
        return {
            "title": filename,
            "required_skills": [],
            "preferred_skills": [],
            "min_experience_years": 0,
            "preferred_experience_years": 0,
            "education": [],
            "responsibilities": [],
            "domain": [],
            "summary": jd_text[:300]
        }
