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
    set_update_callback
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

# Background task to periodically broadcast status updates
async def status_broadcaster():
    """Periodically broadcast status updates to all connected clients."""
    while True:
        await asyncio.sleep(0.5)  # Broadcast every 500ms
        if server_state.active_connections:
            await emit_status_update()


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup."""
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    
    asyncio.create_task(status_broadcaster())
    
    # Set callback for scheduling updates from sync context (background threads)
    def schedule_update():
        if _main_loop and not _main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(emit_status_update(), _main_loop)
    
    set_update_callback(schedule_update)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    server_state.reset()


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
                            daemon=True
                        )
                        thread.start()
                    elif mode == "speech":
                        thread = threading.Thread(
                            target=run_speech_mode_async,
                            args=(config,),
                            daemon=True
                        )
                        thread.start()
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

