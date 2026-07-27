from langchain_community.document_loaders import Docx2txtLoader

def get_docx_loader(file_path: str) -> Docx2txtLoader:
    """Returns Docx2txtLoader for loading Word documents."""
    return Docx2txtLoader(file_path)
