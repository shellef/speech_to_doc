from __future__ import annotations

from typing import List, Optional
from .base import InputHandler


class ListInputHandler(InputHandler):
    """Input handler that reads from a pre-defined list of text utterances."""
    
    def __init__(self, utterances: List[str]):
        """
        Initialize with a list of utterances.
        
        Args:
            utterances: List of text utterances to process one at a time
        """
        self.utterances = utterances
        self.current_index = 0
    
    def get_next_utterance(self) -> Optional[str]:
        """Get the next utterance from the list. Returns None when done."""
        if self.current_index >= len(self.utterances):
            return None
        
        utterance = self.utterances[self.current_index]
        self.current_index += 1
        return utterance

