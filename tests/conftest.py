import sys
from pathlib import Path

# Allow `from backend.main import ...` in tests
sys.path.insert(0, str(Path(__file__).parent.parent))
