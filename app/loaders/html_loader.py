from langchain_community.document_loaders import UnstructuredHTMLLoader

def get_html_loader(file_path: str) -> UnstructuredHTMLLoader:
    """Returns UnstructuredHTMLLoader for loading HTML documents."""
    return UnstructuredHTMLLoader(file_path)
