from langchain_community.document_loaders import CSVLoader

def get_csv_loader(file_path: str) -> CSVLoader:
    """Returns CSVLoader for loading CSV documents."""
    return CSVLoader(file_path)
