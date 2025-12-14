from __future__ import annotations

import json
import logging
from typing import Callable, Dict, List, Optional

from core import DocumentUpdater, Metrics
from input_handlers import STTInputHandler
from eou_detector import EndOfUtteranceDetector


class SpeechDriver:
    """
    Speech-to-text driver: processes STT chunk sequence through end-of-utterance detector,
    then sends complete utterances to core module.
    """
    
    def __init__(
        self,
        updater: DocumentUpdater,
        on_interim_result: Optional[Callable[[str], None]] = None,
        on_final_result: Optional[Callable[[str], None]] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize speech driver.
        
        Args:
            updater: DocumentUpdater instance (core module)
            on_interim_result: Optional callback for interim results (partial utterances)
            on_final_result: Optional callback for final results (complete utterances)
            logger: Optional logger instance
        """
        self.updater = updater
        self.input_handler = STTInputHandler()
        self.eou_detector = EndOfUtteranceDetector()
        self.on_interim_result = on_interim_result
        self.on_final_result = on_final_result
        self.logger = logger or logging.getLogger(__name__)
        self.utterance_count = 0
    
    def add_chunk(self, chunk: Dict):
        """
        Add a chunk from the speech-to-text engine.
        
        Args:
            chunk: Dictionary containing chunk data from STT engine
        """
        self.input_handler.add_chunk(chunk)
        
        # Build current utterance text for interim results
        chunks = self.input_handler.get_chunks()
        utterance_parts = []
        for c in chunks:
            chunk_text = c.get('text', '')
            if not chunk_text:
                continue
            attaches_to = c.get('attaches_to')
            if attaches_to == "previous" and utterance_parts:
                utterance_parts[-1] += chunk_text
            else:
                utterance_parts.append(chunk_text)
        
        current_text = " ".join(utterance_parts)
        
        # Emit interim result
        if self.on_interim_result:
            self.on_interim_result(current_text)
        
        # Check for end of utterance
        complete_utterance = self.eou_detector.process_chunks(chunks)
        
        if complete_utterance:
            # Emit final result
            if self.on_final_result:
                self.on_final_result(complete_utterance)
            
            # Process the complete utterance
            self.utterance_count += 1
            self.logger.info("Processing utterance %d: %s", self.utterance_count, complete_utterance[:50] + "..." if len(complete_utterance) > 50 else complete_utterance)
            
            result = self.updater.apply_utterance(complete_utterance)
            metrics = result.get("metrics", Metrics())
            
            print(f"\n[Utterance {self.utterance_count} | Latency: {metrics.latency_seconds:.2f}s | Cost: ${metrics.estimated_cost_usd:.6f}]")
            
            print("\nChange log from this utterance:")
            for change in result["change_log"]:
                if "error" in change:
                    print(f"  ERROR: {change.get('error')} - {change.get('reason', '')}")
                else:
                    print(f"  - {change.get('path', 'N/A')}: {change.get('op', 'N/A')}")
            
            print("\nCurrent document state (pretty-printed):")
            print(json.dumps(result["doc_state"], indent=2, ensure_ascii=False))
            print("\n---\n")
            
            # Clear chunks after processing
            self.input_handler.clear_chunks()
    
    def finalize(self):
        """
        Finalize any remaining chunks as a complete utterance.
        Call this when STT stream ends to process any remaining partial utterance.
        """
        chunks = self.input_handler.get_chunks()
        if chunks:
            # Build utterance from remaining chunks
            utterance_parts = []
            for chunk in chunks:
                chunk_text = chunk.get('text', '')
                if not chunk_text:
                    continue
                attaches_to = chunk.get('attaches_to')
                if attaches_to == "previous" and utterance_parts:
                    utterance_parts[-1] += chunk_text
                else:
                    utterance_parts.append(chunk_text)
            
            if utterance_parts:
                complete_utterance = " ".join(utterance_parts)
                
                # Emit final result
                if self.on_final_result:
                    self.on_final_result(complete_utterance)
                
                # Process the complete utterance
                self.utterance_count += 1
                self.logger.info("Processing final utterance %d: %s", self.utterance_count, complete_utterance[:50] + "..." if len(complete_utterance) > 50 else complete_utterance)
                
                result = self.updater.apply_utterance(complete_utterance)
                metrics = result.get("metrics", Metrics())
                
                print(f"\n[Utterance {self.utterance_count} | Latency: {metrics.latency_seconds:.2f}s | Cost: ${metrics.estimated_cost_usd:.6f}]")
                
                print("\nChange log from this utterance:")
                for change in result["change_log"]:
                    if "error" in change:
                        print(f"  ERROR: {change.get('error')} - {change.get('reason', '')}")
                    else:
                        print(f"  - {change.get('path', 'N/A')}: {change.get('op', 'N/A')}")
                
                print("\nCurrent document state (pretty-printed):")
                print(json.dumps(result["doc_state"], indent=2, ensure_ascii=False))
                print("\n---\n")
                
                # Clear chunks
                self.input_handler.clear_chunks()
        
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

