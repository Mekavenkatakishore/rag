import os
from app.loaders.pdf_loader import get_pdf_loader
from app.loaders.docx_loader import get_docx_loader
from app.loaders.text_loader import get_text_loader
from app.loaders.csv_loader import get_csv_loader
from app.loaders.ppt_loader import get_ppt_loader
from app.loaders.html_loader import get_html_loader
from app.loaders.markdown_loader import get_markdown_loader

# Mapping of file extensions to their loader builders
LOADER_MAPPING = {
    '.pdf': get_pdf_loader,
    '.docx': get_docx_loader,
    '.txt': get_text_loader,
    '.csv': get_csv_loader,
    '.pptx': get_ppt_loader,
    '.html': get_html_loader,
    '.htm': get_html_loader,
    '.md': get_markdown_loader
}

def get_document_loader(file_path: str):
    """
    Loader Factory: returns the appropriate LangChain document loader based on extension.
    Validates file existence and file size.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    if os.path.getsize(file_path) == 0:
        raise ValueError(f"File is empty: {file_path}")

    _, ext = os.path.splitext(file_path.lower())
    if ext not in LOADER_MAPPING:
        raise ValueError(f"Unsupported file extension '{ext}' for file: {file_path}")
        
    # Get and return the document loader instance
    return LOADER_MAPPING[ext](file_path)
