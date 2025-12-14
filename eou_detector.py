from __future__ import annotations

import re
from typing import Dict, List, Optional


class EndOfUtteranceDetector:
    """
    Detects when chunks from speech-to-text engine form a complete utterance.
    Uses is_eos flags, punctuation, and timing information.
    """
    
    def __init__(self):
        """Initialize the end-of-utterance detector."""
        pass
    
    def _should_finalize_by_punctuation(self, chunk_text: str) -> bool:
        """
        Determine if utterance should be finalized based on punctuation.
        Finalize on sentence-ending punctuation: . ! ?
        """
        return bool(re.search(r'[.!?]$', chunk_text))
    
    def process_chunks(self, chunks: List[Dict]) -> Optional[str]:
        """
        Process chunks and detect if they form a complete utterance.
        
        Args:
            chunks: List of chunk dictionaries from STT engine.
                    Expected fields: text, is_eos, attaches_to, etc.
        
        Returns:
            Complete utterance text if end-of-utterance detected, None otherwise
        """
        if not chunks:
            return None
        
        # Build utterance text from chunks
        utterance_parts = []
        
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get('text', '')
            if not chunk_text:
                continue
            
            attaches_to = chunk.get('attaches_to')
            
            # Handle punctuation that attaches to previous word
            if attaches_to == "previous" and utterance_parts:
                # Attach punctuation to previous word without space
                utterance_parts[-1] += chunk_text
            else:
                # Add chunk to utterance
                utterance_parts.append(chunk_text)
        
        # Check if we should finalize
        # Look for is_eos flag in any chunk
        has_eos = any(chunk.get('is_eos', False) for chunk in chunks)
        
        # Also check last chunk for punctuation-based EOU
        if chunks:
            last_chunk = chunks[-1]
            last_text = last_chunk.get('text', '')
            has_punctuation_eos = self._should_finalize_by_punctuation(last_text)
        else:
            has_punctuation_eos = False
        
        # Finalize if either condition is met
        if has_eos or has_punctuation_eos:
            # Join parts with spaces
            utterance = " ".join(utterance_parts)
            return utterance
        
        return None

