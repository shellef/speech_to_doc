from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class InputHandler(ABC):
    """Abstract base class for input handlers (stdin, speech-to-text, etc.)."""
    
    @abstractmethod
    def get_next_utterance(self) -> Optional[str]:
        """Get the next utterance from the input source. Returns None when done."""
        pass

