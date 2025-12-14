import React, { useState } from 'react';
import { TranscriptionState } from '../types';

interface TranscriptionWindowProps {
  transcription: TranscriptionState | null | undefined;
  mode: 'test' | 'speech' | 'idle';
}

export const TranscriptionWindow: React.FC<TranscriptionWindowProps> = ({ transcription, mode }) => {
  // Hide in test mode
  if (mode !== 'speech') {
    return null;
  }

  const [copied, setCopied] = useState(false);
  const interimText = transcription?.interim_text || '';
  const finalizedText = transcription?.finalized_text || '';
  const combinedText = finalizedText + (interimText ? ' ' + interimText : '');

  const handleCopy = async () => {
    if (combinedText) {
      await navigator.clipboard.writeText(combinedText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="transcription-window">
      <div className="window-header">
        <h2>Transcription</h2>
        <button 
          className="copy-button" 
          onClick={handleCopy}
          disabled={!combinedText}
          title="Copy transcription"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="5" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
            <rect x="2" y="2" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          </svg>
          {copied && <span className="copy-feedback">Copied!</span>}
        </button>
      </div>
      <div className="transcription-content">
        {combinedText ? (
          <div>
            {finalizedText && <span>{finalizedText}</span>}
            {interimText && <span className="interim-text">{interimText}</span>}
          </div>
        ) : (
          <div className="empty-state">No transcription yet...</div>
        )}
      </div>
      <style>{`
        .transcription-window {
          display: flex;
          flex-direction: column;
          height: 100%;
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 16px;
          background: #fff;
          position: relative;
        }
        .window-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .transcription-window h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: #333;
        }
        .copy-button {
          position: relative;
          background: transparent;
          border: none;
          cursor: pointer;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #666;
          transition: color 0.2s;
          width: 24px;
          height: 24px;
        }
        .copy-button:hover:not(:disabled) {
          color: #333;
        }
        .copy-button:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
        .copy-feedback {
          position: absolute;
          top: -28px;
          right: 0;
          background: #333;
          color: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          white-space: nowrap;
          pointer-events: none;
        }
        .copy-feedback::after {
          content: '';
          position: absolute;
          top: 100%;
          right: 8px;
          border: 4px solid transparent;
          border-top-color: #333;
        }
        .transcription-content {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          background: #f9f9f9;
          border-radius: 4px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
          font-size: 14px;
          line-height: 1.6;
          color: #333;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
        .interim-text {
          color: #888;
          font-style: italic;
        }
        .empty-state {
          color: #999;
          font-style: italic;
        }
      `}</style>
    </div>
  );
};

