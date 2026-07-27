import sys

import_paths = [
    "from langchain.retrievers import EnsembleRetriever",
    "from langchain.retrievers.ensemble import EnsembleRetriever",
    "from langchain_core.retrievers import EnsembleRetriever",
    "from langchain_community.retrievers import EnsembleRetriever",
    "from langchain_community.retrievers.ensemble import EnsembleRetriever",
    "from langchain_classic.retrievers import EnsembleRetriever"
]

print("Python version:", sys.version)
print("Scanning import paths for EnsembleRetriever...")

success = False
for path in import_paths:
    try:
        exec(path)
        print(f"[SUCCESS] Works: {path}")
        success = True
    except ImportError as e:
        print(f"[FAILED]  {path} -> {e}")
    except Exception as e:
        print(f"[ERROR]   {path} -> {type(e).__name__}: {e}")

if not success:
    print("\nCould not find EnsembleRetriever in any of the standard import paths.")
    print("Checking installed langchain packages:")
    try:
        import langchain
        print("langchain version:", getattr(langchain, "__version__", "unknown"))
        print("langchain path:", langchain.__file__)
    except ImportError:
        print("langchain package is not installed.")
