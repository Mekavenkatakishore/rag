from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document

class BaseDocumentLoaderWrapper(ABC):
    """Abstract Base Loader interface for parsing raw files into LangChain Document objects."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    @abstractmethod
    def load(self) -> List[Document]:
        """Loads and extracts text content into Document objects."""
        pass
