from __future__ import annotations

import sys
from pathlib import Path

# Les fabriques de documents sont un module de test, pas du paquet.
sys.path.insert(0, str(Path(__file__).parent))
