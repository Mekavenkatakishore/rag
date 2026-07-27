from langchain_community.document_loaders import UnstructuredPowerPointLoader

def get_ppt_loader(file_path: str) -> UnstructuredPowerPointLoader:
    """Returns UnstructuredPowerPointLoader for loading PowerPoint files."""
    return UnstructuredPowerPointLoader(file_path)
