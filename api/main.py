from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.models import Command, StatusUpdate
from api.server_state import server_state
from api.integration import (
    run_test_mode_async, 
    run_speech_mode_async, 
    emit_status_update,
    set_update_callback,
    schedule_update
)
from api.formatters import format_document

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Speech-to-Doc API")

# CORS middleware for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global reference to the main event loop for thread-safe scheduling
_main_loop = None
_status_broadcaster_task = None
_shutdown_flag = None

# Background task to periodically broadcast status updates
async def status_broadcaster():
    """Periodically broadcast status updates to all connected clients."""
    try:
        while True:
            await asyncio.sleep(0.5)  # Broadcast every 500ms
            if server_state.active_connections:
                await emit_status_update()
    except asyncio.CancelledError:
        logger.info("Status broadcaster cancelled")
        raise


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup."""
    global _main_loop, _status_broadcaster_task, _shutdown_flag
    _main_loop = asyncio.get_running_loop()
    
    _status_broadcaster_task = asyncio.create_task(status_broadcaster())
    
    # Set callback for scheduling updates from sync context (background threads)
    _shutdown_flag = threading.Event()
    
    def schedule_update():
        if _shutdown_flag.is_set():
            logger.debug("schedule_update called but shutdown flag is set, skipping")
            return
        if _main_loop and not _main_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(emit_status_update(), _main_loop)
            except RuntimeError as e:
                logger.debug(f"schedule_update: RuntimeError (likely event loop closed): {e}")
            except Exception as e:
                logger.warning(f"schedule_update: Unexpected error: {e}")
        else:
            logger.debug("schedule_update called but main_loop is None or closed")
    
    set_update_callback(schedule_update)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _status_broadcaster_task, _shutdown_flag
    logger.info("=== SHUTDOWN STARTED ===")
    
    # Set shutdown flag to prevent new schedule_update calls
    logger.info("Step 0: Setting shutdown flag...")
    _shutdown_flag.set()
    logger.info("  - Shutdown flag set")
    
    # Cancel background tasks
    logger.info("Step 1: Cancelling status broadcaster task...")
    if _status_broadcaster_task and not _status_broadcaster_task.done():
        logger.info("  - Status broadcaster task exists and is not done, cancelling...")
        _status_broadcaster_task.cancel()
        try:
            await _status_broadcaster_task
            logger.info("  - Status broadcaster task cancelled successfully")
        except asyncio.CancelledError:
            logger.info("  - Status broadcaster task cancellation confirmed")
        except Exception as e:
            logger.error(f"  - Error cancelling status broadcaster: {e}")
    else:
        logger.info("  - Status broadcaster task already done or doesn't exist")
    
    # Signal stop to all background threads
    logger.info("Step 2: Signaling stop to background threads...")
    logger.info(f"  - Current server state: mode={server_state.mode}, is_running={server_state.is_running}")
    logger.info(f"  - Stop event before set: {server_state.stop_event.is_set()}")
    server_state.stop_event.set()
    logger.info(f"  - Stop event after set: {server_state.stop_event.is_set()}")
    server_state.set_running(False)
    logger.info("  - Set is_running=False")
    
    # Check if there are active threads
    logger.info("Step 3: Checking for active processing threads...")
    logger.info(f"  - Processing thread: {server_state.processing_thread}")
    if server_state.processing_thread:
        logger.info(f"  - Thread is_alive: {server_state.processing_thread.is_alive()}")
        logger.info(f"  - Thread daemon: {server_state.processing_thread.daemon}")
    
    # Give threads a moment to respond (use async sleep to not block event loop)
    logger.info("Step 4: Waiting for threads to respond (0.1s)...")
    await asyncio.sleep(0.1)
    logger.info("  - Wait complete")
    
    logger.info("Step 5: Resetting server state...")
    server_state.reset()
    logger.info("  - Server state reset complete")
    
    logger.info("=== SHUTDOWN COMPLETE ===")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Speech-to-Doc API", "status": "running"}


@app.get("/api/status")
async def get_status():
    """Get current status via REST endpoint."""
    utterances = server_state.get_utterances()
    document = server_state.get_document()
    
    utterance_models = [
        {"id": u.id, "text": u.text} for u in utterances
    ]
    
    transcription = None
    if server_state.mode == "speech":
        transcription = server_state.transcription.model_dump()
    
    formatted_doc = format_document(document)
    metrics = server_state.get_metrics()
    
    return {
        "mode": server_state.mode,
        "is_running": server_state.is_running,
        "transcription": transcription,
        "utterances": utterance_models,
        "document": document,
        "formatted_document": formatted_doc,
        "metrics": metrics
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time bidirectional communication."""
    await websocket.accept()
    server_state.add_connection(websocket)
    logger.info("Client connected via WebSocket")
    
    try:
        # Send initial status
        await emit_status_update()
        
        while True:
            # Receive command from client
            data = await websocket.receive_text()
            try:
                command_data = json.loads(data)
                command = Command(**command_data)
                
                if command.type == "start":
                    if server_state.is_running:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Processing already running"
                        }))
                        continue
                    
                    # Start processing in background thread
                    mode = command.mode or "test"
                    config = command.config or {}
                    
                    if mode == "test":
                        thread = threading.Thread(
                            target=run_test_mode_async,
                            args=(config,),
                            daemon=True,
                            name="test-mode-thread"
                        )
                        logger.info(f"Starting test mode thread: {thread.name}, daemon={thread.daemon}")
                        thread.start()
                        logger.info(f"Test mode thread started, is_alive={thread.is_alive()}")
                        server_state.processing_thread = thread
                    elif mode == "speech":
                        thread = threading.Thread(
                            target=run_speech_mode_async,
                            args=(config,),
                            daemon=True,
                            name="speech-mode-thread"
                        )
                        logger.info(f"Starting speech mode thread: {thread.name}, daemon={thread.daemon}")
                        thread.start()
                        logger.info(f"Speech mode thread started, is_alive={thread.is_alive()}")
                        server_state.processing_thread = thread
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Invalid mode: {mode}"
                        }))
                    
                    logger.info(f"Started processing in {mode} mode")
                
                elif command.type == "stop":
                    if not server_state.is_running:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "No processing running"
                        }))
                        continue
                    
                    server_state.stop_event.set()
                    server_state.set_running(False)
                    logger.info("Stopped processing")
                    await emit_status_update()
                
                elif command.type == "speech_chunk":
                    # Handle speech chunk from browser
                    if not server_state.is_running or server_state.mode != "speech":
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Speech mode not running"
                        }))
                        continue
                    
                    # Get the speech driver from server state
                    driver = server_state.get_speech_driver()
                    if not driver:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Speech driver not initialized"
                        }))
                        continue
                    
                    # Convert browser chunk to backend format
                    chunk_data = command.chunk or {}
                    is_final = chunk_data.get('is_final', False)
                    chunk = {
                        'text': chunk_data.get('text', ''),
                        'is_eos': is_final,
                        'attaches_to': None,  # Browser API doesn't provide this
                    }
                    
                    # For interim chunks, we need to clear previous interim chunks
                    # to prevent accumulation. The browser sends the full interim text,
                    # so we replace previous interim state rather than accumulating.
                    if not is_final:
                        # Clear interim chunks from input handler before adding new one
                        # We'll do this by getting all chunks, filtering out non-final ones,
                        # then clearing and re-adding only final chunks
                        from input_handlers.stt_input_handler import STTInputHandler
                        if isinstance(driver.input_handler, STTInputHandler):
                            all_chunks = driver.input_handler.get_chunks()
                            # Keep only final chunks (is_eos=True)
                            final_chunks = [c for c in all_chunks if c.get('is_eos', False)]
                            # Clear all chunks
                            driver.input_handler.clear_chunks()
                            # Re-add only final chunks
                            for fc in final_chunks:
                                driver.input_handler.add_chunk(fc)
                    else:
                        # For final chunks, clear all existing chunks since the final chunk
                        # contains the complete cumulative text, not an incremental addition
                        from input_handlers.stt_input_handler import STTInputHandler
                        if isinstance(driver.input_handler, STTInputHandler):
                            driver.input_handler.clear_chunks()
                    
                    # Add chunk to driver
                    driver.add_chunk(chunk)
                    
                    # Schedule status update
                    schedule_update()
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
    
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        server_state.remove_connection(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

