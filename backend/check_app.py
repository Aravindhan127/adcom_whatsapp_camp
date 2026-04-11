import traceback
import sys
import os

# Set Python Path
sys.path.append(os.getcwd())

try:
    print("Attempting to import main.app...")
    from main import app
    print("SUCCESS: App imported correctly.")
except Exception:
    print("FAILED: Traceback follows:")
    traceback.print_exc()
