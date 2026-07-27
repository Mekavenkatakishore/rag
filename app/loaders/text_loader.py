from langchain_community.document_loaders import TextLoader

def get_text_loader(file_path: str) -> TextLoader:
    """Returns TextLoader for loading plain text documents with UTF-8 encoding."""
    return TextLoader(file_path, encoding='utf-8')
