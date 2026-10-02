"""La version de l'extracteur, écrite sur chaque document analysé et chaque
proposition (``documents.extractor_version``, ``extractions.model_name``).

ELLE CHANGE QUAND CE QUI EST PROPOSÉ PEUT CHANGER : une règle ajoutée, un seuil
de confiance déplacé, une borne d'OCR modifiée. Une proposition doit pouvoir
dire, dix ans plus tard, quel code l'a formée.
"""

from __future__ import annotations

from typing import Final

VERSION_EXTRACTEUR: Final[str] = "eurostruct-extraction/0.5.0"
