"""
skill_normalizer.py
───────────────────
Extensible service for normalizing technology and domain skills to canonical names.
Ensures fair matching across keyword search (BM25) and LLM evaluations.
"""

import re

# Comprehensive canonical mapping dictionary
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
    
    # Frontend Frameworks
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

def normalize_skill(skill: str) -> str:
    """
    Normalizes a single skill string to its canonical representation.
    
    Examples:
        'Postgres' -> 'PostgreSQL'
        'ReactJS' -> 'React'
        'k8s' -> 'Kubernetes'
    """
    if not skill or not isinstance(skill, str):
        return ""
        
    cleaned = skill.strip().lower()
    # Remove common punctuation or noise
    cleaned_simple = re.sub(r"[^\w\s\+\#\.]", "", cleaned)
    
    # Check exact match in dictionary
    if cleaned in SKILL_MAP:
        return SKILL_MAP[cleaned]
    if cleaned_simple in SKILL_MAP:
        return SKILL_MAP[cleaned_simple]
        
    # Titlecase fallback for unlisted skills
    return skill.strip().title()

def normalize_skill_list(skills: list[str]) -> list[str]:
    """
    Normalizes a list of skill strings and removes duplicates while preserving order.
    """
    if not skills:
        return []
        
    normalized = []
    seen = set()
    
    for s in skills:
        norm = normalize_skill(s)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            normalized.append(norm)
            
    return normalized
