import React from 'react';
import { Utterance } from '../types';

interface UtteranceListProps {
  utterances: Utterance[];
}

export const UtteranceList: React.FC<UtteranceListProps> = ({ utterances }) => {
  return (
    <div className="utterance-list">
      <h2>Utterances</h2>
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
        }
        .utterance-list h2 {
          margin: 0 0 12px 0;
          font-size: 18px;
          font-weight: 600;
          color: #333;
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

