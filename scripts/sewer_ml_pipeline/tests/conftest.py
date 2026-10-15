from pathlib import Path
import sys

# Tests live beside the cloud-only modules so they run without packaging or data access.
sys.path.insert(0, str(Path(__file__).parents[1]))
