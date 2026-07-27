import sys
import os

print("=== DIAGNOSTIC REPORT ===")
print("Python Executable:", sys.executable)
print("Python Version:", sys.version)

try:
    import langchain
    print("\n[SUCCESS] Imported 'langchain'")
    print("langchain path:", langchain.__file__)
    print("langchain version:", getattr(langchain, "__version__", "unknown"))
    
    # List subdirectories in langchain package to see if retrievers exists
    langchain_dir = os.path.dirname(langchain.__file__)
    print("langchain dir contents:", os.listdir(langchain_dir))
except Exception as e:
    print("\n[FAILED] Importing 'langchain':", e)

print("\n--- Testing Imports ---")

imports_to_test = [
    "from langchain.retrievers import ContextualCompressionRetriever",
    "from langchain.retrievers.contextual_compression import ContextualCompressionRetriever",
    "from langchain_core.retrievers import ContextualCompressionRetriever",
    "from langchain_community.retrievers import ContextualCompressionRetriever"
]

for imp in imports_to_test:
    try:
        exec(imp)
        print(f"[SUCCESS] {imp}")
    except Exception as e:
        print(f"[FAILED]  {imp} -> {type(e).__name__}: {e}")
