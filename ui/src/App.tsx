import React, { useState, useEffect } from 'react';
import { WebSocketClient } from './websocket';
import { StatusUpdate, ErrorMessage, Command } from './types';
import { TranscriptionWindow } from './components/TranscriptionWindow';
import { UtteranceList } from './components/UtteranceList';
import { DocumentView } from './components/DocumentView';

const App: React.FC = () => {
  const [status, setStatus] = useState<StatusUpdate>({
    type: 'status_update',
    mode: 'idle',
    is_running: false,
    utterances: [],
    document: {},
    formatted_document: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedMode, setSelectedMode] = useState<'test' | 'speech'>('test');
  const wsRef = React.useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const ws = new WebSocketClient();
    wsRef.current = ws;

    const unsubscribeMessage = ws.onMessage((message) => {
      if (message.type === 'status_update') {
        setStatus(message);
        setError(null);
      } else if (message.type === 'error') {
        setError((message as ErrorMessage).message);
      }
    });

    const unsubscribeConnect = ws.onConnect(() => {
      setIsConnected(true);
      setError(null);
    });

    const unsubscribeDisconnect = ws.onDisconnect(() => {
      setIsConnected(false);
    });

    ws.connect();

    return () => {
      unsubscribeMessage();
      unsubscribeConnect();
      unsubscribeDisconnect();
      ws.disconnect();
    };
  }, []);

  const handleStart = () => {
    if (!wsRef.current || status.is_running) return;

    const command: Command = {
      type: 'start',
      mode: selectedMode,
      config: {},
    };

    wsRef.current.send(command);
  };

  const handleStop = () => {
    if (!wsRef.current || !status.is_running) return;

    const command: Command = {
      type: 'stop',
    };

    wsRef.current.send(command);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Speech to Document</h1>
        <div className="controls">
          <div className="mode-selector">
            <label>
              <input
                type="radio"
                name="mode"
                value="test"
                checked={selectedMode === 'test'}
                onChange={() => setSelectedMode('test')}
                disabled={status.is_running}
              />
              Test Mode
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                value="speech"
                checked={selectedMode === 'speech'}
                onChange={() => setSelectedMode('speech')}
                disabled={status.is_running}
              />
              Speech Mode
            </label>
          </div>
          <button
            onClick={handleStart}
            disabled={status.is_running || !isConnected}
            className="btn btn-start"
          >
            Start
          </button>
          <button
            onClick={handleStop}
            disabled={!status.is_running || !isConnected}
            className="btn btn-stop"
          >
            Stop
          </button>
          <div className="status-indicator">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          Error: {error}
        </div>
      )}

      <main className="app-main">
        <div className="window-container">
          <div className="window-column">
            <TranscriptionWindow
              transcription={status.transcription}
              mode={status.mode}
            />
          </div>
          <div className="window-column">
            <UtteranceList utterances={status.utterances} />
          </div>
          <div className="window-column">
            <DocumentView formattedDocument={status.formatted_document} />
          </div>
        </div>
      </main>

      {status.metrics && (
        <footer className="app-footer">
          <div className="metrics">
            <span>Utterances: {status.metrics.total_utterances || 0}</span>
            <span>Cost: ${(status.metrics.total_cost_usd || 0).toFixed(6)}</span>
            <span>Avg Latency: {(status.metrics.avg_latency_seconds || 0).toFixed(2)}s</span>
          </div>
        </footer>
      )}

      <style>{`
        * {
          box-sizing: border-box;
        }
        body {
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }
        .app {
          display: flex;
          flex-direction: column;
          height: 100vh;
          background: #f5f5f5;
        }
        .app-header {
          background: #fff;
          border-bottom: 1px solid #ddd;
          padding: 16px 24px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .app-header h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 600;
          color: #333;
        }
        .controls {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .mode-selector {
          display: flex;
          gap: 12px;
        }
        .mode-selector label {
          display: flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
        }
        .btn {
          padding: 8px 16px;
          border: none;
          border-radius: 4px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .btn-start {
          background: #4CAF50;
          color: white;
        }
        .btn-start:hover:not(:disabled) {
          background: #45a049;
        }
        .btn-stop {
          background: #f44336;
          color: white;
        }
        .btn-stop:hover:not(:disabled) {
          background: #da190b;
        }
        .status-indicator {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 14px;
          color: #666;
        }
        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #999;
        }
        .status-dot.connected {
          background: #4CAF50;
        }
        .error-banner {
          background: #ffebee;
          color: #c62828;
          padding: 12px 24px;
          border-bottom: 1px solid #ef5350;
        }
        .app-main {
          flex: 1;
          padding: 24px;
          overflow: hidden;
        }
        .window-container {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 24px;
          height: 100%;
        }
        .window-column {
          display: flex;
          flex-direction: column;
          min-height: 0;
        }
        .app-footer {
          background: #fff;
          border-top: 1px solid #ddd;
          padding: 12px 24px;
        }
        .metrics {
          display: flex;
          gap: 24px;
          font-size: 14px;
          color: #666;
        }
        .metrics span {
          font-weight: 500;
        }
      `}</style>
    </div>
  );
};

export default App;

