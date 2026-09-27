import sys
import os

print("=== DIAGNOSTIC REPORT ===")
print("Python Executable:", sys.executable)
print("Python Version:", sys.version)

try:
    import langchain
    print("\n[SUCCESS] Imported 'langchain'")
except Exception as e:
    print("\n[FAILED] Importing 'langchain':", e)
