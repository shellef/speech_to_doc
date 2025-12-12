from __future__ import annotations

import jsonpatch
import time
import json
import os
import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from openai import OpenAI


# Configuration via environment variables
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
DEBUG_LEVEL = os.getenv("DEBUG_LEVEL", "INFO").upper()

# Speech simulation configuration
SPEECH_SIMULATION_ENABLED = os.getenv("SPEECH_SIMULATION_ENABLED", "false").lower() == "true"
SPEECH_CHUNK_DELAY_MS = float(os.getenv("SPEECH_CHUNK_DELAY_MS", "50"))
SPEECH_FINALIZE_PAUSE_MS = float(os.getenv("SPEECH_FINALIZE_PAUSE_MS", "1000"))
SPEECH_INPUT_SOURCE = os.getenv("SPEECH_INPUT_SOURCE", "")  # File path or empty for inline text


# ---------- Process template (initial empty document) ----------

PROCESS_TEMPLATE: Dict[str, Any] = {
    "process_name": "",
    "process_goal": "",
    "scope": {
        "start_trigger": "",
        "end_condition": "",
        "in_scope": [],
        "out_of_scope": [],
    },
    "actors": [],   # e.g. ["Sales rep", "Customer success", "New customer"]
    "systems": [],  # e.g. ["HubSpot", "Gmail", "Slack"]
    "main_flow": [
        # each step: {"id": "S1", "description": "...", "actor": "", "system": ""}
    ],
    "exceptions": [],
    "metrics": [],
    "open_questions": [],
}


SYSTEM_PROMPT = """Update a process document using JSON Patch (RFC 6902).

Given process_doc (JSON) and new_utterance (text), produce a JSON Patch with ONLY minimal changes.

Output format:
{
  "patch": [
    { "op": "add" | "replace" | "remove", "path": "/a/b/0", "value": ... }
  ]
}

Rules:
- Paths start with "/". Use numeric indices for arrays. Append with "-" (e.g., "/main_flow/-").
- Return minimal, valid JSON. If no update needed: { "patch": [] }.
- Never invent fields not clearly implied."""


@dataclass
class Utterance:
    id: int
    text: str


@dataclass
class Metrics:
    """Track metrics for each utterance processing."""
    latency_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    success: bool = True
    error_type: Optional[str] = None


class InputHandler(ABC):
    """Abstract base class for input handlers (stdin, speech-to-text, etc.)."""
    
    @abstractmethod
    def get_next_utterance(self) -> Optional[str]:
        """Get the next utterance from the input source. Returns None when done."""
        pass


class StdinInputHandler(InputHandler):
    """Input handler for stdin (current implementation)."""
    
    def get_next_utterance(self) -> Optional[str]:
        text = input("Utterance> ").strip()
        return text if text else None


class ProcessDocUpdater:
    def __init__(
        self, 
        client: OpenAI, 
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        logger: Optional[logging.Logger] = None
    ):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.logger = logger or logging.getLogger(__name__)
        self.doc_state: Dict[str, Any] = deepcopy(PROCESS_TEMPLATE)
        self.utterances: List[Utterance] = []
        self.metrics_history: List[Metrics] = []
        
        # Model pricing per 1M tokens (as of 2024, approximate)
        # Input/Output pricing for gpt-4o-mini
        self.model_pricing = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD based on token usage."""
        pricing = self.model_pricing.get(self.model, {"input": 0.15, "output": 0.60})
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def apply_utterance(self, text: str):
        """
        Send current doc_state + new utterance to LLM and get back RFC 6902 patches.
        Apply the patches to update self.doc_state.
        Returns dict with doc_state, change_log, and metrics.
        """
        metrics = Metrics()
        t0 = time.time()

        utterance = Utterance(id=len(self.utterances) + 1, text=text)
        self.utterances.append(utterance)

        payload = {
            "process_doc": self.doc_state,
            "new_utterance": utterance.text,
        }

        messages = [
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user", "content": json.dumps(payload, ensure_ascii=False) }
        ]

        self.logger.debug("LLM Request - Model: %s, Utterance ID: %d", self.model, utterance.id)
        self.logger.debug("System prompt: %s", SYSTEM_PROMPT)
        self.logger.debug("User payload: %s", json.dumps(payload, indent=2, ensure_ascii=False))

        try:
            # Use streaming for lower perceived latency
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature,
                stream=True,
            )

            # Collect streaming chunks
            raw = ""
            last_chunk = None
            for chunk in response:
                last_chunk = chunk
                if chunk.choices and chunk.choices[0].delta.content:
                    raw += chunk.choices[0].delta.content

            t1 = time.time()
            metrics.latency_seconds = t1 - t0

            # Extract token usage from the final chunk if available
            # In streaming mode, usage info comes in the final chunk
            if last_chunk and hasattr(last_chunk, 'usage') and last_chunk.usage:
                metrics.prompt_tokens = last_chunk.usage.prompt_tokens or 0
                metrics.completion_tokens = last_chunk.usage.completion_tokens or 0
                metrics.total_tokens = last_chunk.usage.total_tokens or 0
            else:
                # Fallback: estimate tokens (rough approximation: ~4 chars per token)
                prompt_text = json.dumps(payload, ensure_ascii=False)
                metrics.prompt_tokens = len(prompt_text) // 4
                metrics.completion_tokens = len(raw) // 4
                metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens

            metrics.estimated_cost_usd = self._estimate_cost(
                metrics.prompt_tokens, 
                metrics.completion_tokens
            )

            self.logger.debug("Raw LLM response: %s", raw)
            self.logger.info(
                "Response received in %.2fs | Tokens: %d/%d | Cost: $%.6f",
                metrics.latency_seconds,
                metrics.prompt_tokens,
                metrics.completion_tokens,
                metrics.estimated_cost_usd
            )

        except Exception as e:
            t1 = time.time()
            metrics.latency_seconds = t1 - t0
            metrics.success = False
            metrics.error_type = "API_ERROR"
            self.logger.error("API call failed: %s", e, exc_info=True)
            return {
                "doc_state": self.doc_state,
                "change_log": [
                    { "error": "API_ERROR", "reason": str(e) }
                ],
                "metrics": metrics,
            }

        # Parse JSON
        try:
            parsed = json.loads(raw)
            patch_ops = parsed.get("patch", [])
            self.logger.debug("Parsed patch ops: %s", patch_ops)
        except Exception as e:
            metrics.success = False
            metrics.error_type = "JSON_PARSE"
            self.logger.error("JSON parse error: %s | Raw: %s", e, raw)
            self.metrics_history.append(metrics)
            return {
                "doc_state": self.doc_state,
                "change_log": [
                    { "error": "JSON_PARSE", "reason": str(e) }
                ],
                "metrics": metrics,
            }

        # Apply patch
        try:
            if patch_ops:
                patch = jsonpatch.JsonPatch(patch_ops)
                new_doc = patch.apply(self.doc_state)
            else:
                new_doc = self.doc_state

            change_log = patch_ops
            self.doc_state = new_doc
            self.logger.debug("New doc state: %s", json.dumps(self.doc_state, indent=2, ensure_ascii=False))

        except Exception as e:
            metrics.success = False
            metrics.error_type = "PATCH_FAILED"
            self.logger.error("Patch application failed: %s | Patch: %s", e, patch_ops)
            self.metrics_history.append(metrics)
            return {
                "doc_state": self.doc_state,
                "change_log": [
                    { "error": "PATCH_FAILED", "reason": str(e), "patch": patch_ops }
                ],
                "metrics": metrics,
            }

        self.metrics_history.append(metrics)
        return {
            "doc_state": self.doc_state,
            "change_log": change_log,
            "metrics": metrics,
        }

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics across all processed utterances."""
        if not self.metrics_history:
            return {}
        
        total_latency = sum(m.latency_seconds for m in self.metrics_history)
        total_cost = sum(m.estimated_cost_usd for m in self.metrics_history)
        total_tokens = sum(m.total_tokens for m in self.metrics_history)
        success_count = sum(1 for m in self.metrics_history if m.success)
        
        return {
            "total_utterances": len(self.metrics_history),
            "successful": success_count,
            "failed": len(self.metrics_history) - success_count,
            "avg_latency_seconds": total_latency / len(self.metrics_history),
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "estimated_hourly_cost_usd": total_cost * (3600 / total_latency) if total_latency > 0 else 0,
        }


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
    Minimal end-to-end loop:
    - Reads utterances from stdin (via InputHandler abstraction).
    - Calls LLM for each one.
    - Prints the change log and current doc.
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    
    client = OpenAI()
    updater = ProcessDocUpdater(
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
