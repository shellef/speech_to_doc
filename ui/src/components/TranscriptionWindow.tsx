import React from 'react';
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

  const interimText = transcription?.interim_text || '';
  const finalizedText = transcription?.finalized_text || '';
  const combinedText = finalizedText + (interimText ? ' ' + interimText : '');

  return (
    <div className="transcription-window">
      <h2>Transcription</h2>
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
        }
        .transcription-window h2 {
          margin: 0 0 12px 0;
          font-size: 18px;
          font-weight: 600;
          color: #333;
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

