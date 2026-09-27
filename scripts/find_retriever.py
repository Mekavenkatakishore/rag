import importlib

modules = [
    "langchain.retrievers",
    "langchain_classic.retrievers",
    "langchain_community.retrievers",
    "langchain_core.retrievers"
]

for mod in modules:
    try:
        m = importlib.import_module(mod)
        if hasattr(m, "ContextualCompressionRetriever"):
            print(f"[FOUND] ContextualCompressionRetriever in {mod}")
    except Exception as e:
        print(f"[ERROR] Could not import {mod}: {e}")
