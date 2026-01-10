
import sys
from pathlib import Path
import os
sys.path.append(os.getcwd())

print(f"Checking imports from {os.getcwd()}")

try:
    import src.main
    print("Imports OK")
except Exception as e:
    print(f"Import Error: {e}")
    import traceback
    traceback.print_exc()
