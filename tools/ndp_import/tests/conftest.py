import sys
from pathlib import Path

# pdf_fixture lives beside the tests and is not an installed package.
sys.path.insert(0, str(Path(__file__).parent))
