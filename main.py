from __future__ import annotations

import os
import json
import logging
import re
import time
from typing import List

from openai import OpenAI

from core import DocumentUpdater
from drivers import TestDriver, SpeechDriver


# Configuration via environment variables
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
DEBUG_LEVEL = os.getenv("DEBUG_LEVEL", "INFO").upper()

# Driver mode configuration
DRIVER_MODE = os.getenv("DRIVER_MODE", "test").lower()  # "test" or "speech"

# Test mode configuration
TEST_UTTERANCES = os.getenv("TEST_UTTERANCES", "")  # JSON array of utterances or file path

# Speech mode configuration
SPEECH_SIMULATION_ENABLED = os.getenv("SPEECH_SIMULATION_ENABLED", "false").lower() == "true"
SPEECH_CHUNK_DELAY_MS = float(os.getenv("SPEECH_CHUNK_DELAY_MS", "50"))
SPEECH_FINALIZE_PAUSE_MS = float(os.getenv("SPEECH_FINALIZE_PAUSE_MS", "1000"))
SPEECH_INPUT_SOURCE = os.getenv("SPEECH_INPUT_SOURCE", "")  # File path or empty for inline text


def setup_logging(debug_level: str = DEBUG_LEVEL):
    """Configure logging based on debug level."""
    level = getattr(logging, debug_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def load_test_utterances() -> List[str]:
    """
    Load test utterances from environment variable or file.
    Returns list of utterance strings.
    """
    if not TEST_UTTERANCES:
        # Default test utterances
        return [
            "Okay, let me walk you through how we handle a new customer.",
            "When a new customer signs the contract, the sales rep creates a new company record in HubSpot and marks the deal as closed won.",
            "That automatically triggers a Slack notification in the customer-success channel so the CSM knows they have a new account.",
            "Within one business day, the CSM sends a welcome email from Gmail with a scheduling link for the kickoff call.",
            "After the kickoff, the CSM fills out a short onboarding checklist in Notion: basic company info, stakeholders, key goals, and any risks.",
            "If the customer doesn't schedule within three days, the CSM follows up with a reminder email and also pings the sales rep.",
            "We consider onboarding complete once the customer has had their kickoff call and is actively using the product for at least two weeks."
        ]
    
    # Check if it's a file path
    if os.path.isfile(TEST_UTTERANCES):
        with open(TEST_UTTERANCES, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Try to parse as JSON array
            try:
                utterances = json.loads(content)
                if isinstance(utterances, list):
                    return [str(u) for u in utterances]
                else:
                    # Treat as single utterance
                    return [str(utterances)]
            except json.JSONDecodeError:
                # Not JSON, treat as plain text (one utterance per line)
                return [line.strip() for line in content.split('\n') if line.strip()]
    else:
        # Try to parse as JSON array
        try:
            utterances = json.loads(TEST_UTTERANCES)
            if isinstance(utterances, list):
                return [str(u) for u in utterances]
            else:
                return [str(utterances)]
        except json.JSONDecodeError:
            # Treat as single utterance
            return [TEST_UTTERANCES]


def run_test_mode(logger: logging.Logger):
    """Run in test mode: process list of utterances."""
    logger.info("Starting in TEST mode")
    
    utterances = load_test_utterances()
    logger.info("Loaded %d test utterances", len(utterances))
    
    client = OpenAI()
    updater = DocumentUpdater(
        client,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        logger=logger
    )
    
    driver = TestDriver(updater, utterances, logger)
    driver.run()


def run_speech_mode(logger: logging.Logger):
    """Run in speech mode: process STT chunks through EOU detector."""
    logger.info("Starting in SPEECH mode")
    
    # For now, use speech simulator if enabled
    # In production, this would connect to a real STT engine
    if SPEECH_SIMULATION_ENABLED:
        from speech_simulator import SimulatedSpeechInputHandler
        
        # Determine text source
        if SPEECH_INPUT_SOURCE and os.path.isfile(SPEECH_INPUT_SOURCE):
            text_source = SPEECH_INPUT_SOURCE
        elif SPEECH_INPUT_SOURCE:
            # Assume it's inline text
            text_source = SPEECH_INPUT_SOURCE
        else:
            # Use default test text from file
            text_source = "test_speech.txt"
        
        logger.info("Using speech simulation mode")
        logger.info("Chunk delay: %.1fms | Finalize pause: %.1fms", SPEECH_CHUNK_DELAY_MS, SPEECH_FINALIZE_PAUSE_MS)
        
        client = OpenAI()
        updater = DocumentUpdater(
            client,
            model=DEFAULT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            logger=logger
        )
        
        # Callback for displaying interim results
        def on_interim_result(text: str):
            print(f"\r[Interim] {text[:80]}...", end="", flush=True)
        
        def on_final_result(text: str):
            print(f"\r[Final]   {text}\n", flush=True)
        
        driver = SpeechDriver(
            updater,
            on_interim_result=on_interim_result,
            on_final_result=on_final_result,
            logger=logger
        )
        
        # Create simulator that feeds chunks to driver
        simulator = SimulatedSpeechInputHandler(
            text_source=text_source,
            chunk_delay_ms=SPEECH_CHUNK_DELAY_MS,
            finalize_pause_ms=SPEECH_FINALIZE_PAUSE_MS,
            on_interim_result=on_interim_result,
            on_final_result=on_final_result,
        )
        
        # Process chunks from simulator
        # For JSON input, we need to parse and feed chunks with timing
        if simulator.is_json:
            # Feed JSON chunks to driver with timing delays
            last_end_time = None
            for chunk_data in simulator.json_chunks:
                start_time = chunk_data.get('start_time')
                
                # Calculate delay based on timing
                if last_end_time is not None and start_time is not None:
                    delay = start_time - last_end_time
                    if delay > 0:
                        time.sleep(delay)
                
                # Convert to format expected by driver
                chunk = {
                    'text': chunk_data['text'],
                    'start_time': start_time,
                    'end_time': chunk_data.get('end_time'),
                    'is_eos': chunk_data.get('is_eos', False),
                    'attaches_to': chunk_data.get('attaches_to'),
                }
                driver.add_chunk(chunk)
                
                # Update last_end_time
                if chunk_data.get('end_time') is not None:
                    last_end_time = chunk_data.get('end_time')
        else:
            # For text input, simulate chunk-by-chunk delivery with delays
            words = simulator.words
            for i, word in enumerate(words):
                # Simulate delay between chunks
                if i > 0:
                    time.sleep(simulator.chunk_delay_seconds)
                
                # Determine if this is end of sentence
                is_eos = bool(re.search(r'[.!?]$', word)) if word else False
                
                chunk = {
                    'text': word,
                    'is_eos': is_eos,
                    'attaches_to': None,
                }
                driver.add_chunk(chunk)
        
        driver.finalize()
    else:
        logger.info("Speech mode requires SPEECH_SIMULATION_ENABLED=true or real STT engine connection")
        logger.info("For now, use test mode or enable speech simulation")


def main():
    """
    Main entry point: chooses driver based on configuration.
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Process documentation prototype")
    logger.info("Model: %s | Temperature: %.2f", DEFAULT_MODEL, DEFAULT_TEMPERATURE)
    logger.info("Driver mode: %s", DRIVER_MODE)
    
    print("Process documentation prototype")
    print(f"Mode: {DRIVER_MODE.upper()}")
    print(f"Model: {DEFAULT_MODEL} | Temperature: {DEFAULT_TEMPERATURE}\n")
    
    # Determine mode (backward compatibility: if SPEECH_SIMULATION_ENABLED, use speech mode)
    if SPEECH_SIMULATION_ENABLED:
        actual_mode = "speech"
    else:
        actual_mode = DRIVER_MODE
    
    if actual_mode == "speech":
        print("Running in SPEECH mode (STT chunks → EOU detector → core module)\n")
        run_speech_mode(logger)
    else:
        print("Running in TEST mode (list of utterances → core module)\n")
        run_test_mode(logger)


if __name__ == "__main__":
    main()

