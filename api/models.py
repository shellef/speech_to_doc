from __future__ import annotations

from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel


class UtteranceModel(BaseModel):
    id: int
    text: str


class TranscriptionState(BaseModel):
    """Transcription state for speech mode (interim/final text)."""
    interim_text: str = ""
    finalized_text: str = ""


class StatusUpdate(BaseModel):
    """Status update sent to UI via WebSocket."""
    type: Literal["status_update"] = "status_update"
    mode: Literal["test", "speech", "idle"]
    is_running: bool
    transcription: Optional[TranscriptionState] = None  # Only in speech mode
    utterances: List[UtteranceModel] = []
    document: Dict[str, Any] = {}
    formatted_document: str = ""
    metrics: Optional[Dict[str, Any]] = None


class Command(BaseModel):
    """Command sent from UI to backend."""
    type: Literal["start", "stop", "speech_chunk"]
    mode: Optional[Literal["test", "speech"]] = None
    config: Optional[Dict[str, Any]] = None  # For test utterances, speech config, etc.
    chunk: Optional[Dict[str, Any]] = None  # For speech chunks from browser


class ErrorMessage(BaseModel):
    """Error message sent to UI."""
    type: Literal["error"] = "error"
    message: str

