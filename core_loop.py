"""
Legacy entry point - maintained for backward compatibility.
New code should use main.py instead.

This module re-exports the core functionality and maintains the old interface.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional

from openai import OpenAI

# Import from new architecture
from core import DocumentUpdater, PROCESS_TEMPLATE, SYSTEM_PROMPT, Utterance, Metrics
from input_handlers import InputHandler

# Re-export for backward compatibility
ProcessDocUpdater = DocumentUpdater

# Configuration via environment variables
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
DEBUG_LEVEL = os.getenv("DEBUG_LEVEL", "INFO").upper()

# Speech simulation configuration
SPEECH_SIMULATION_ENABLED = os.getenv("SPEECH_SIMULATION_ENABLED", "false").lower() == "true"
SPEECH_CHUNK_DELAY_MS = float(os.getenv("SPEECH_CHUNK_DELAY_MS", "50"))
SPEECH_FINALIZE_PAUSE_MS = float(os.getenv("SPEECH_FINALIZE_PAUSE_MS", "1000"))
SPEECH_INPUT_SOURCE = os.getenv("SPEECH_INPUT_SOURCE", "")  # File path or empty for inline text


class StdinInputHandler(InputHandler):
    """Input handler for stdin (legacy implementation)."""
    
    def get_next_utterance(self) -> Optional[str]:
        text = input("Utterance> ").strip()
        return text if text else None


def setup_logging(debug_level: str = DEBUG_LEVEL):
    """Configure logging based on debug level."""
    level = getattr(logging, debug_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def main():
    """
    Legacy main function - maintained for backward compatibility.
    For new code, use main.py instead.
    
    Minimal end-to-end loop:
    - Reads utterances from stdin (via InputHandler abstraction).
    - Calls LLM for each one.
    - Prints the change log and current doc.
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.warning("Using legacy core_loop.py - consider migrating to main.py")
    
    client = OpenAI()
    updater = DocumentUpdater(
        client,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE
    )
    
    # Choose input handler based on configuration
    if SPEECH_SIMULATION_ENABLED:
        from speech_simulator import SimulatedSpeechInputHandler
        
        # Determine text source
        if SPEECH_INPUT_SOURCE and os.path.isfile(SPEECH_INPUT_SOURCE):
            text_source = SPEECH_INPUT_SOURCE
        elif SPEECH_INPUT_SOURCE:
            # Assume it's inline text
            text_source = SPEECH_INPUT_SOURCE
        else:
            # Use default test text
            text_source = """Okay, let me walk you through how we handle a new customer.

When a new customer signs the contract, the sales rep creates a new company record in HubSpot and marks the deal as closed won.

That automatically triggers a Slack notification in the customer-success channel so the CSM knows they have a new account.

Within one business day, the CSM sends a welcome email from Gmail with a scheduling link for the kickoff call.

After the kickoff, the CSM fills out a short onboarding checklist in Notion: basic company info, stakeholders, key goals, and any risks.

If the customer doesn't schedule within three days, the CSM follows up with a reminder email and also pings the sales rep.

We consider onboarding complete once the customer has had their kickoff call and is actively using the product for at least two weeks."""
        
        # Callback for displaying interim results
        def on_interim_result(text: str):
            print(f"\r[Interim] {text[:80]}...", end="", flush=True)
        
        def on_final_result(text: str):
            print(f"\r[Final]   {text}\n", flush=True)
        
        input_handler = SimulatedSpeechInputHandler(
            text_source=text_source,
            chunk_delay_ms=SPEECH_CHUNK_DELAY_MS,
            finalize_pause_ms=SPEECH_FINALIZE_PAUSE_MS,
            on_interim_result=on_interim_result,
            on_final_result=on_final_result,
        )
        logger.info("Using speech simulation mode")
        logger.info("Chunk delay: %.1fms | Finalize pause: %.1fms", SPEECH_CHUNK_DELAY_MS, SPEECH_FINALIZE_PAUSE_MS)
    else:
        input_handler: InputHandler = StdinInputHandler()
        logger.info("Using stdin input mode")

    logger.info("Process documentation prototype")
    logger.info("Model: %s | Temperature: %.2f", DEFAULT_MODEL, DEFAULT_TEMPERATURE)
    print("Process documentation prototype")
    if not SPEECH_SIMULATION_ENABLED:
        print("Type utterances as if they were transcribed from speech.")
        print("Press ENTER on an empty line to finish.\n")
    else:
        print("Simulating speech-to-text input...\n")

    while True:
        text = input_handler.get_next_utterance()
        if text is None:
            break

        result = updater.apply_utterance(text)
        metrics = result.get("metrics", Metrics())

        print(f"\n[Latency: {metrics.latency_seconds:.2f}s | Cost: ${metrics.estimated_cost_usd:.6f}]")
        
        print("\nChange log from this utterance:")
        for change in result["change_log"]:
            if "error" in change:
                print(f"  ERROR: {change.get('error')} - {change.get('reason', '')}")
            else:
                print(f"  - {change.get('path', 'N/A')}: {change.get('op', 'N/A')}")

        print("\nCurrent document state (pretty-printed):")
        print(json.dumps(result["doc_state"], indent=2, ensure_ascii=False))
        print("\n---\n")

    # Print final summary
    agg_metrics = updater.get_aggregate_metrics()
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Total utterances: {agg_metrics.get('total_utterances', 0)}")
    print(f"Successful: {agg_metrics.get('successful', 0)}")
    print(f"Failed: {agg_metrics.get('failed', 0)}")
    print(f"Average latency: {agg_metrics.get('avg_latency_seconds', 0):.2f}s")
    print(f"Total cost: ${agg_metrics.get('total_cost_usd', 0):.6f}")
    print(f"Total tokens: {agg_metrics.get('total_tokens', 0):,}")
    hourly_cost = agg_metrics.get('estimated_hourly_cost_usd', 0)
    print(f"Estimated hourly cost: ${hourly_cost:.2f}")
    if hourly_cost > 10:
        print("⚠️  WARNING: Estimated hourly cost exceeds $10/hour target")
    print("="*60)
    
    print("\nFinal document:")
    print(json.dumps(updater.doc_state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
