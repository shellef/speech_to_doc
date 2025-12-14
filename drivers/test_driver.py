from __future__ import annotations

import json
import logging
from typing import List, Optional

from core import DocumentUpdater, Metrics
from input_handlers import ListInputHandler


class TestDriver:
    """
    Test driver: reads from a list of utterances and sends them one at a time to core module.
    Simple test mode for validating core functionality.
    """
    
    def __init__(
        self,
        updater: DocumentUpdater,
        utterances: List[str],
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize test driver.
        
        Args:
            updater: DocumentUpdater instance (core module)
            utterances: List of text utterances to process
            logger: Optional logger instance
        """
        self.updater = updater
        self.input_handler = ListInputHandler(utterances)
        self.logger = logger or logging.getLogger(__name__)
    
    def run(self):
        """
        Run the test driver: process all utterances one at a time.
        Prints results for each utterance and final summary.
        """
        self.logger.info("Starting test driver with %d utterances", len(self.input_handler.utterances))
        
        utterance_count = 0
        while True:
            text = self.input_handler.get_next_utterance()
            if text is None:
                break
            
            utterance_count += 1
            self.logger.info("Processing utterance %d: %s", utterance_count, text[:50] + "..." if len(text) > 50 else text)
            
            result = self.updater.apply_utterance(text)
            metrics = result.get("metrics", Metrics())
            
            print(f"\n[Utterance {utterance_count} | Latency: {metrics.latency_seconds:.2f}s | Cost: ${metrics.estimated_cost_usd:.6f}]")
            
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
        agg_metrics = self.updater.get_aggregate_metrics()
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
        print(json.dumps(self.updater.doc_state, indent=2, ensure_ascii=False))

