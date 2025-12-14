from __future__ import annotations

import threading
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from core import DocumentUpdater, Utterance
from api.models import TranscriptionState


@dataclass
class ServerState:
    """Thread-safe server state management."""
    
    updater: Optional[DocumentUpdater] = None
    mode: str = "idle"  # "idle", "test", "speech"
    is_running: bool = False
    transcription: TranscriptionState = field(default_factory=TranscriptionState)
    active_connections: List = field(default_factory=list)
    processing_thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    speech_driver: Optional[Any] = None  # Store SpeechDriver instance
    _lock: threading.Lock = field(default_factory=threading.Lock)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    
    def set_updater(self, updater: DocumentUpdater):
        """Set the document updater instance."""
        with self._lock:
            self.updater = updater
    
    def set_mode(self, mode: str):
        """Set the processing mode."""
        with self._lock:
            self.mode = mode
            if mode != "speech":
                # Clear transcription when not in speech mode
                self.transcription = TranscriptionState()
    
    def set_running(self, running: bool):
        """Set running status."""
        with self._lock:
            self.is_running = running
    
    def update_transcription_interim(self, text: str):
        """Update interim transcription text (speech mode only)."""
        with self._lock:
            if self.mode == "speech":
                self.transcription.interim_text = text
    
    def update_transcription_final(self, text: str):
        """Add finalized text to transcription (speech mode only)."""
        with self._lock:
            if self.mode == "speech":
                # Append to finalized text
                if self.transcription.finalized_text:
                    self.transcription.finalized_text += " " + text
                else:
                    self.transcription.finalized_text = text
                # Clear interim after finalizing
                self.transcription.interim_text = ""
    
    def get_utterances(self) -> List[Utterance]:
        """Get list of utterances from updater."""
        with self._lock:
            if self.updater:
                return self.updater.utterances.copy()
            return []
    
    def get_document(self) -> Dict[str, Any]:
        """Get current document state."""
        with self._lock:
            if self.updater:
                return self.updater.doc_state.copy()
            return {}
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get aggregate metrics."""
        with self._lock:
            if self.updater:
                return self.updater.get_aggregate_metrics()
            return None
    
    def get_transcription_dict(self) -> Optional[Dict[str, str]]:
        """Get transcription as dictionary for serialization."""
        with self._lock:
            if self.mode == "speech":
                return {
                    "interim_text": self.transcription.interim_text,
                    "finalized_text": self.transcription.finalized_text
                }
            return None
    
    def add_connection(self, websocket):
        """Add a WebSocket connection."""
        with self._lock:
            if websocket not in self.active_connections:
                self.active_connections.append(websocket)
    
    def remove_connection(self, websocket):
        """Remove a WebSocket connection."""
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        with self._lock:
            connections = self.active_connections.copy()
        
        disconnected = []
        for ws in connections:
            try:
                import json
                await ws.send_text(json.dumps(message))
            except Exception as e:
                self.logger.warning("Failed to send to client: %s", e)
                disconnected.append(ws)
        
        # Clean up disconnected clients
        with self._lock:
            for ws in disconnected:
                if ws in self.active_connections:
                    self.active_connections.remove(ws)
    
    def set_speech_driver(self, driver):
        """Set the speech driver instance."""
        with self._lock:
            self.speech_driver = driver
    
    def get_speech_driver(self):
        """Get the speech driver instance."""
        with self._lock:
            return self.speech_driver
    
    def reset(self):
        """Reset state for new session."""
        self.logger.info("ServerState.reset() called")
        with self._lock:
            self.logger.info("  - Acquired lock, resetting state...")
            # Directly set is_running since we already have the lock
            # (don't call set_running() which would try to acquire the lock again)
            self.is_running = False
            self.logger.info("  - Set is_running=False")
            self.stop_event.set()
            self.logger.info("  - Set stop_event")
            self.transcription = TranscriptionState()
            self.logger.info("  - Reset transcription")
            self.speech_driver = None
            self.logger.info("  - Cleared speech_driver")
            if self.updater:
                # Keep updater but could reset if needed
                pass
            self.logger.info("  - Reset complete, releasing lock")
        self.logger.info("ServerState.reset() finished")


# Global singleton instance
server_state = ServerState()

