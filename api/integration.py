from __future__ import annotations

import os
import json
import time
import re
import logging
import threading
from typing import List, Optional, Dict, Any

from openai import OpenAI

from core import DocumentUpdater
from drivers import TestDriver, SpeechDriver
from speech_simulator import SimulatedSpeechInputHandler
from api.server_state import server_state
from api.formatters import format_document
from api.models import StatusUpdate


def load_test_utterances_from_config(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Load test utterances from config or environment."""
    if config and "utterances" in config:
        utterances = config["utterances"]
        if isinstance(utterances, list):
            return [str(u) for u in utterances]
        elif isinstance(utterances, str):
            # Could be a file path or JSON string
            if os.path.isfile(utterances):
                with open(utterances, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            return [str(u) for u in parsed]
                        else:
                            return [str(parsed)]
                    except json.JSONDecodeError:
                        return [line.strip() for line in content.split('\n') if line.strip()]
            else:
                try:
                    parsed = json.loads(utterances)
                    if isinstance(parsed, list):
                        return [str(u) for u in parsed]
                    else:
                        return [str(parsed)]
                except json.JSONDecodeError:
                    return [utterances]
    
    # Fallback to default test utterances
    return [
        "Okay, let me walk you through how we handle a new customer.",
        "When a new customer signs the contract, the sales rep creates a new company record in HubSpot and marks the deal as closed won.",
        "That automatically triggers a Slack notification in the customer-success channel so the CSM knows they have a new account.",
        "Within one business day, the CSM sends a welcome email from Gmail with a scheduling link for the kickoff call.",
        "After the kickoff, the CSM fills out a short onboarding checklist in Notion: basic company info, stakeholders, key goals, and any risks.",
        "If the customer doesn't schedule within three days, the CSM follows up with a reminder email and also pings the sales rep.",
        "We consider onboarding complete once the customer has had their kickoff call and is actively using the product for at least two weeks."
    ]


async def emit_status_update():
    """Emit current status update to all connected clients."""
    utterances = server_state.get_utterances()
    document = server_state.get_document()
    
    # Build utterance models
    utterance_models = [
        {"id": u.id, "text": u.text} for u in utterances
    ]
    
    # Get transcription (only for speech mode)
    transcription = server_state.get_transcription_dict()
    
    # Format document
    formatted_doc = format_document(document)
    
    # Get metrics
    metrics = server_state.get_metrics()
    
    update = StatusUpdate(
        mode=server_state.mode,
        is_running=server_state.is_running,
        transcription=transcription,
        utterances=utterance_models,
        document=document,
        formatted_document=formatted_doc,
        metrics=metrics
    )
    
    await server_state.broadcast(update.model_dump())


# Global callback for scheduling async updates from sync context
_update_callback = None

def set_update_callback(callback):
    """Set callback function to schedule async updates."""
    global _update_callback
    _update_callback = callback

def schedule_update():
    """Schedule an async status update (called from sync context)."""
    if _update_callback:
        _update_callback()


def run_test_mode_async(config: Optional[Dict[str, Any]] = None):
    """Run test mode in background thread."""
    logger = logging.getLogger(__name__)
    logger.info("Starting test mode processing")
    
    # Get configuration
    model = config.get("model", os.getenv("OPENAI_MODEL", "gpt-4o")) if config else os.getenv("OPENAI_MODEL", "gpt-4o")
    temperature = float(config.get("temperature", os.getenv("OPENAI_TEMPERATURE", "0.2"))) if config else float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    utterances = load_test_utterances_from_config(config)
    
    # Create updater
    client = OpenAI()
    updater = DocumentUpdater(
        client,
        model=model,
        temperature=temperature,
        logger=logger
    )
    
    server_state.set_updater(updater)
    server_state.set_mode("test")
    server_state.set_running(True)
    server_state.stop_event.clear()
    
    # Wrap TestDriver to emit WebSocket updates
    class WebSocketTestDriver(TestDriver):
        def __init__(self, updater, utterances, logger):
            super().__init__(updater, utterances, logger)
        
        def run(self):
            """Modified run to emit WebSocket updates."""
            self.logger.info("Starting test driver with %d utterances", len(self.input_handler.utterances))
            
            utterance_count = 0
            while True:
                # Check for stop signal
                if server_state.stop_event.is_set():
                    self.logger.info("Stop signal received, stopping test driver")
                    break
                
                text = self.input_handler.get_next_utterance()
                if text is None:
                    break
                
                utterance_count += 1
                self.logger.info("Processing utterance %d: %s", utterance_count, text[:50] + "..." if len(text) > 50 else text)
                
                result = self.updater.apply_utterance(text)
                
                # Schedule status update after each utterance
                schedule_update()
    
    driver = WebSocketTestDriver(updater, utterances, logger)
    driver.run()
    
    server_state.set_running(False)
    # Final status update
    schedule_update()


def run_speech_mode_async(config: Optional[Dict[str, Any]] = None):
    """Run speech mode in background thread."""
    logger = logging.getLogger(__name__)
    logger.info("Starting speech mode processing")
    
    # Get configuration
    model = config.get("model", os.getenv("OPENAI_MODEL", "gpt-4o")) if config else os.getenv("OPENAI_MODEL", "gpt-4o")
    temperature = float(config.get("temperature", os.getenv("OPENAI_TEMPERATURE", "0.2"))) if config else float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    chunk_delay_ms = float(config.get("chunk_delay_ms", os.getenv("SPEECH_CHUNK_DELAY_MS", "50"))) if config else float(os.getenv("SPEECH_CHUNK_DELAY_MS", "50"))
    finalize_pause_ms = float(config.get("finalize_pause_ms", os.getenv("SPEECH_FINALIZE_PAUSE_MS", "1000"))) if config else float(os.getenv("SPEECH_FINALIZE_PAUSE_MS", "1000"))
    text_source = config.get("input_source", os.getenv("SPEECH_INPUT_SOURCE", "")) if config else os.getenv("SPEECH_INPUT_SOURCE", "")
    
    if not text_source:
        text_source = "real-time-transcript.json"  # Default
    
    # Create updater
    client = OpenAI()
    updater = DocumentUpdater(
        client,
        model=model,
        temperature=temperature,
        logger=logger
    )
    
    server_state.set_updater(updater)
    server_state.set_mode("speech")
    server_state.set_running(True)
    server_state.stop_event.clear()
    
    # Callbacks for WebSocket updates
    def on_interim_result(text: str):
        server_state.update_transcription_interim(text)
        schedule_update()
    
    def on_final_result(text: str):
        server_state.update_transcription_final(text)
        schedule_update()
    
    # Create driver with callbacks
    driver = SpeechDriver(
        updater,
        on_interim_result=on_interim_result,
        on_final_result=on_final_result,
        logger=logger
    )
    
    # Create simulator
    simulator = SimulatedSpeechInputHandler(
        text_source=text_source,
        chunk_delay_ms=chunk_delay_ms,
        finalize_pause_ms=finalize_pause_ms,
        on_interim_result=on_interim_result,
        on_final_result=on_final_result,
    )
    
    # Wrap driver to emit updates after processing
    original_add_chunk = driver.add_chunk
    
    def wrapped_add_chunk(chunk: Dict):
        original_add_chunk(chunk)
        # Schedule status update
        schedule_update()
    
    driver.add_chunk = wrapped_add_chunk
    
    # Process chunks
    if simulator.is_json:
        last_end_time = None
        for chunk_data in simulator.json_chunks:
            if server_state.stop_event.is_set():
                break
            
            start_time = chunk_data.get('start_time')
            if last_end_time is not None and start_time is not None:
                delay = start_time - last_end_time
                if delay > 0:
                    time.sleep(delay)
            
            chunk = {
                'text': chunk_data['text'],
                'start_time': start_time,
                'end_time': chunk_data.get('end_time'),
                'is_eos': chunk_data.get('is_eos', False),
                'attaches_to': chunk_data.get('attaches_to'),
            }
            driver.add_chunk(chunk)
            
            if chunk_data.get('end_time') is not None:
                last_end_time = chunk_data.get('end_time')
    else:
        words = simulator.words
        for i, word in enumerate(words):
            if server_state.stop_event.is_set():
                break
            
            if i > 0:
                time.sleep(simulator.chunk_delay_seconds)
            
            is_eos = bool(re.search(r'[.!?]$', word)) if word else False
            chunk = {
                'text': word,
                'is_eos': is_eos,
                'attaches_to': None,
            }
            driver.add_chunk(chunk)
    
    if not server_state.stop_event.is_set():
        driver.finalize()
    
    server_state.set_running(False)

