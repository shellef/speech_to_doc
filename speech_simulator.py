from __future__ import annotations

import os
import time
import re
from typing import Optional, Callable, TextIO


class SimulatedSpeechInputHandler:
    """
    Simulates W3C Web Speech API behavior by delivering text in chunks with delays.
    Supports interim results that get finalized after a pause.
    """
    
    def __init__(
        self,
        text_source: str | TextIO,
        chunk_delay_ms: float = 50,
        finalize_pause_ms: float = 1000,
        on_interim_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize speech simulator.
        
        Args:
            text_source: Text string, file path, or file handle to simulate
            chunk_delay_ms: Delay between chunks in milliseconds
            finalize_pause_ms: Pause duration before finalizing (milliseconds)
            on_interim_result: Optional callback for interim results
            on_final_result: Optional callback for final results
        """
        self.chunk_delay_seconds = chunk_delay_ms / 1000.0
        self.finalize_pause_seconds = finalize_pause_ms / 1000.0
        self.on_interim_result = on_interim_result
        self.on_final_result = on_final_result
        
        # Load text source
        if isinstance(text_source, str):
            # Check if it's a file path
            if os.path.isfile(text_source):
                with open(text_source, 'r', encoding='utf-8') as f:
                    self.text = f.read()
            else:
                # Assume it's the text itself
                self.text = text_source
        else:
            # File handle
            self.text = text_source.read()
        
        # Split text into words/punctuation for chunking
        # Keep punctuation attached to words, split on whitespace
        self.words = re.findall(r'\S+', self.text)
        self.current_index = 0
        self.current_utterance = ""
        self.finalized_utterances = []
        self._running = False
        
    def _chunk_text(self) -> list[str]:
        """Split text into chunks (words) for incremental delivery."""
        return self.words
    
    def _should_finalize(self, chunk: str) -> bool:
        """
        Determine if utterance should be finalized based on punctuation.
        Finalize on sentence-ending punctuation: . ! ?
        """
        return bool(re.search(r'[.!?]$', chunk))
    
    def get_next_utterance(self) -> Optional[str]:
        """
        Get the next finalized utterance.
        Internally processes chunks with delays and emits interim results.
        Returns None when all text is processed.
        """
        if self.current_index >= len(self.words):
            return None
        
        # Process chunks until we have a finalized utterance
        while self.current_index < len(self.words):
            chunk = self.words[self.current_index]
            
            # Add chunk to current utterance
            if self.current_utterance:
                self.current_utterance += " " + chunk
            else:
                self.current_utterance = chunk
            
            # Emit interim result
            if self.on_interim_result:
                self.on_interim_result(self.current_utterance)
            
            # Check if we should finalize (sentence-ending punctuation)
            should_finalize = self._should_finalize(chunk)
            
            # Simulate delay between chunks
            time.sleep(self.chunk_delay_seconds)
            
            self.current_index += 1
            
            # If we should finalize, add pause and return the utterance
            if should_finalize:
                # Simulate pause before finalization
                time.sleep(self.finalize_pause_seconds)
                
                # Emit final result
                if self.on_final_result:
                    self.on_final_result(self.current_utterance)
                
                # Return finalized utterance
                finalized = self.current_utterance
                self.finalized_utterances.append(finalized)
                self.current_utterance = ""
                return finalized
        
        # If we have remaining text that wasn't finalized, return it
        if self.current_utterance:
            # Simulate final pause
            time.sleep(self.finalize_pause_seconds)
            
            if self.on_final_result:
                self.on_final_result(self.current_utterance)
            
            finalized = self.current_utterance
            self.finalized_utterances.append(finalized)
            self.current_utterance = ""
            return finalized
        
        return None

