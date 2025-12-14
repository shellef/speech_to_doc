import React, { useState } from 'react';
import { Utterance } from '../types';

interface UtteranceListProps {
  utterances: Utterance[];
}

export const UtteranceList: React.FC<UtteranceListProps> = ({ utterances }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (utterances.length > 0) {
      const textToCopy = utterances.map(u => `${u.id}. ${u.text}`).join('\n');
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="utterance-list">
      <div className="window-header">
        <h2>Utterances</h2>
        <button 
          className="copy-button" 
          onClick={handleCopy}
          disabled={utterances.length === 0}
          title="Copy utterances"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="5" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
            <rect x="2" y="2" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          </svg>
          {copied && <span className="copy-feedback">Copied!</span>}
        </button>
      </div>
      <div className="utterance-content">
        {utterances.length > 0 ? (
          <ol className="utterance-items">
            {utterances.map((utterance) => (
              <li key={utterance.id} className="utterance-item">
                <span className="utterance-number">{utterance.id}.</span>
                <span className="utterance-text">{utterance.text}</span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="empty-state">No utterances yet...</div>
        )}
      </div>
      <style>{`
        .utterance-list {
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
        .utterance-list h2 {
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
        .utterance-content {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          background: #f9f9f9;
          border-radius: 4px;
        }
        .utterance-items {
          margin: 0;
          padding-left: 0;
          list-style: none;
        }
        .utterance-item {
          margin-bottom: 12px;
          padding: 8px;
          background: #fff;
          border-radius: 4px;
          border-left: 3px solid #4CAF50;
          display: flex;
          gap: 8px;
        }
        .utterance-number {
          font-weight: 600;
          color: #4CAF50;
          min-width: 24px;
        }
        .utterance-text {
          flex: 1;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
          font-size: 14px;
          line-height: 1.6;
          color: #333;
        }
        .empty-state {
          color: #999;
          font-style: italic;
          padding: 20px;
          text-align: center;
        }
      `}</style>
    </div>
  );
};

