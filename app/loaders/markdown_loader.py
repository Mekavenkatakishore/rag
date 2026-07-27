from langchain_community.document_loaders import UnstructuredMarkdownLoader

def get_markdown_loader(file_path: str) -> UnstructuredMarkdownLoader:
    """Returns UnstructuredMarkdownLoader for loading Markdown documents."""
    return UnstructuredMarkdownLoader(file_path)
