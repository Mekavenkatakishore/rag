from langchain_community.document_loaders import PyPDFLoader

def get_pdf_loader(file_path: str) -> PyPDFLoader:
    """Returns PyPDFLoader for loading PDF documents."""
    return PyPDFLoader(file_path)
