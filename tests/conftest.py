"""conftest.py: shared pytest configuration for the unit test suite."""
import sys
from pathlib import Path

# Add the repo root to sys.path so 'import providers.X' and 'import scripts._common' work
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Add scripts/ so 'from _common import ...' works in tests/ that use it
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
