from __future__ import annotations

from typing import Dict, List, Optional
from .base import InputHandler


class STTInputHandler(InputHandler):
    """
    Input handler that receives sequence of chunks from speech-to-text engine.
    Stores chunks and provides access to them for end-of-utterance detection.
    """
    
    def __init__(self):
        """Initialize with empty chunk list."""
        self.chunks: List[Dict] = []
    
    def add_chunk(self, chunk: Dict):
        """
        Add a chunk from the speech-to-text engine.
        
        Args:
            chunk: Dictionary containing chunk data (e.g., from STT engine response)
                   Expected fields: text, start_time, end_time, is_eos, attaches_to, etc.
        """
        self.chunks.append(chunk)
    
    def get_chunks(self) -> List[Dict]:
        """
        Get the current sequence of chunks.
        
        Returns:
            List of chunk dictionaries
        """
        return self.chunks.copy()
    
    def clear_chunks(self):
        """Clear all stored chunks (typically called after utterance is finalized)."""
        self.chunks.clear()
    
    def get_next_utterance(self) -> Optional[str]:
        """
        This method is not used for STT input handler.
        Use add_chunk() and get_chunks() instead, with EndOfUtteranceDetector.
        
        Returns:
            None (this handler doesn't directly provide utterances)
        """
        return None

