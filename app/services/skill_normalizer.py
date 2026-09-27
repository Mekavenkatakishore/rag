"""
skill_normalizer.py
───────────────────
Extensible service for normalizing technology and domain skills to canonical names.
Ensures fair matching across keyword search (BM25) and LLM evaluations.
"""

import re

SKILL_MAP = {
    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgresql db": "PostgreSQL",
    "pg": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "my sql": "MySQL",
    "mysql": "MySQL",
    "redis": "Redis",
    "dynamodb": "DynamoDB",
    
    # Frontend Frameworks & Languages
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "react native": "React Native",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "html": "HTML5",
    "html5": "HTML5",
    "html5/css3": "HTML5/CSS3",
    "css": "CSS3",
    "css3": "CSS3",
    
    # Backend Frameworks & Languages
    "python": "Python",
    "py": "Python",
    "fastapi": "FastAPI",
    "fast api": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "golang": "Go",
    "go lang": "Go",
    "java": "Java",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "c#": "C#",
    "c++": "C++",
    "dotnet": ".NET",
    ".net": ".NET",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "amazon ec2": "AWS",
    "ec2": "AWS",
    "s3": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github": "GitHub",
    "github actions": "GitHub Actions",

    # AI / ML & Data Science
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "rag": "RAG",
    "retrieval augmented generation": "RAG",
    "langchain": "LangChain",
    "llama": "Llama",
    "ollama": "Ollama",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn"
}

def normalize_single_token(skill: str) -> str:
    """Normalizes a single skill string token."""
    if not skill or not isinstance(skill, str):
        return ""
    cleaned = skill.strip().lower()
    cleaned_simple = re.sub(r"[^\w\s\+\#\.]", "", cleaned)
    if cleaned in SKILL_MAP:
        return SKILL_MAP[cleaned]
    if cleaned_simple in SKILL_MAP:
        return SKILL_MAP[cleaned_simple]
    return skill.strip().title()

def normalize_skill(skill: str) -> str:
    """Normalizes a skill string, handling slash-separated tokens."""
    if not skill or not isinstance(skill, str):
        return ""
    tokens = [t.strip() for t in re.split(r"[/,]", skill) if t.strip()]
    if len(tokens) > 1:
        normalized_tokens = [normalize_single_token(t) for t in tokens]
        return " / ".join(normalized_tokens)
    return normalize_single_token(skill)

def normalize_skill_list(skills: list[str]) -> list[str]:
    """Normalizes a list of skill strings, splitting grouped slash skills into individual canonical skills."""
    if not skills:
        return []
    normalized = []
    seen = set()
    for item in skills:
        if not item or not isinstance(item, str):
            continue
        # Split slash or comma grouped skills (e.g. "Javascript/Typescript" -> "JavaScript", "TypeScript")
        tokens = [t.strip() for t in re.split(r"[/,]", item) if t.strip()]
        for t in tokens:
            norm = normalize_single_token(t)
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                normalized.append(norm)
    return normalized
