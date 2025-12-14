from __future__ import annotations

import os
import time
import re
import json
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
            chunk_delay_ms: Delay between chunks in milliseconds (ignored if JSON has timing)
            finalize_pause_ms: Pause duration before finalizing (milliseconds) (ignored if JSON has timing)
            on_interim_result: Optional callback for interim results
            on_final_result: Optional callback for final results
        """
        self.chunk_delay_seconds = chunk_delay_ms / 1000.0
        self.finalize_pause_seconds = finalize_pause_ms / 1000.0
        self.on_interim_result = on_interim_result
        self.on_final_result = on_final_result
        
        # Check if input is a JSON file
        self.is_json = False
        self.json_chunks = []
        
        # Load text source
        if isinstance(text_source, str):
            # Check if it's a file path
            if os.path.isfile(text_source):
                with open(text_source, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Try to parse as JSON
                    try:
                        data = json.loads(content)
                        if isinstance(data, dict) and 'results' in data:
                            self.is_json = True
                            self._parse_json_transcript(data)
                        else:
                            self.text = content
                    except json.JSONDecodeError:
                        # Not JSON, treat as plain text
                        self.text = content
            else:
                # Assume it's the text itself
                self.text = text_source
        else:
            # File handle
            content = text_source.read()
            try:
                data = json.loads(content)
                if isinstance(data, dict) and 'results' in data:
                    self.is_json = True
                    self._parse_json_transcript(data)
                else:
                    self.text = content
            except json.JSONDecodeError:
                self.text = content
        
        if not self.is_json:
            # Split text into words/punctuation for chunking
            # Keep punctuation attached to words, split on whitespace
            self.words = re.findall(r'\S+', self.text)
        else:
            # For JSON, chunks are already parsed
            self.words = [chunk['text'] for chunk in self.json_chunks]
        
        self.current_index = 0
        self.current_utterance = ""
        self.finalized_utterances = []
        self._running = False
        self.last_end_time = None
        
    def _parse_json_transcript(self, data: dict):
        """
        Parse JSON transcript format and extract chunks with timing information.
        
        Expected format:
        {
            "results": [
                {"type": "word", "alternatives": [{"content": "word"}], "start_time": 1.0, "end_time": 1.5},
                {"type": "punctuation", "alternatives": [{"content": "."}], "start_time": 1.5, "end_time": 1.5, "is_eos": true}
            ]
        }
        """
        self.json_chunks = []
        results = data.get('results', [])
        
        for item in results:
            item_type = item.get('type', '')
            
            # Skip entity types, only process word and punctuation
            if item_type not in ('word', 'punctuation'):
                continue
            
            # Get content from alternatives
            alternatives = item.get('alternatives', [])
            if not alternatives:
                continue
            
            content = alternatives[0].get('content', '')
            if not content:
                continue
            
            # Get timing information
            start_time = item.get('start_time')
            end_time = item.get('end_time')
            is_eos = item.get('is_eos', False)
            attaches_to = item.get('attaches_to')
            
            # Store chunk information
            chunk = {
                'text': content,
                'start_time': start_time,
                'end_time': end_time,
                'is_eos': is_eos,
                'attaches_to': attaches_to,
            }
            self.json_chunks.append(chunk)
    
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
            if self.is_json:
                # Use JSON timing information
                chunk_data = self.json_chunks[self.current_index]
                chunk_text = chunk_data['text']
                start_time = chunk_data.get('start_time')
                end_time = chunk_data.get('end_time')
                is_eos = chunk_data.get('is_eos', False)
                attaches_to = chunk_data.get('attaches_to')
                
                # Calculate delay based on timing
                if self.last_end_time is not None and start_time is not None:
                    # Wait for the actual time difference between chunks
                    delay = start_time - self.last_end_time
                    if delay > 0:
                        time.sleep(delay)
                elif self.last_end_time is None:
                    # First chunk - start immediately, don't wait for initial start_time
                    # This preserves relative timing between chunks without initial delay
                    pass
                elif start_time is None:
                    # Fallback to default delay
                    time.sleep(self.chunk_delay_seconds)
                
                # Handle punctuation that attaches to previous word
                if attaches_to == "previous" and self.current_utterance:
                    # Attach punctuation to previous word without space
                    self.current_utterance += chunk_text
                else:
                    # Add chunk to current utterance
                    if self.current_utterance:
                        self.current_utterance += " " + chunk_text
                    else:
                        self.current_utterance = chunk_text
                
                # Update last_end_time
                if end_time is not None:
                    self.last_end_time = end_time
                
                # Emit interim result
                if self.on_interim_result:
                    self.on_interim_result(self.current_utterance)
                
                # Check if we should finalize (use is_eos from JSON or punctuation check)
                should_finalize = is_eos or self._should_finalize(chunk_text)
                
                self.current_index += 1
                
                # If we should finalize, add pause and return the utterance
                if should_finalize:
                    # If we have timing info, wait for the actual pause duration
                    # Otherwise use default pause
                    if end_time is not None and self.current_index < len(self.json_chunks):
                        next_chunk = self.json_chunks[self.current_index]
                        next_start = next_chunk.get('start_time')
                        if next_start is not None:
                            pause_duration = next_start - end_time
                            if pause_duration > 0:
                                time.sleep(pause_duration)
                        else:
                            time.sleep(self.finalize_pause_seconds)
                    else:
                        time.sleep(self.finalize_pause_seconds)
                    
                    # Emit final result
                    if self.on_final_result:
                        self.on_final_result(self.current_utterance)
                    
                    # Return finalized utterance
                    finalized = self.current_utterance
                    self.finalized_utterances.append(finalized)
                    self.current_utterance = ""
                    return finalized
            else:
                # Original text-based processing
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

