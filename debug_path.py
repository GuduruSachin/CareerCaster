import sys
import os
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print("Path:")
for p in sys.path:
    print(f"  {p}")
sys.exit(1)
