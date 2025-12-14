import React from 'react';

interface DocumentViewProps {
  formattedDocument: string;
}

export const DocumentView: React.FC<DocumentViewProps> = ({ formattedDocument }) => {
  // Convert formatted document (markdown-like) to HTML
  const formatText = (text: string): React.ReactNode => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      if (line.startsWith('# ')) {
        elements.push(<h1 key={i}>{line.substring(2)}</h1>);
      } else if (line.startsWith('## ')) {
        elements.push(<h2 key={i}>{line.substring(3)}</h2>);
      } else if (line.startsWith('**') && line.endsWith('**')) {
        const content = line.slice(2, -2);
        if (content.includes(':')) {
          const [label, ...valueParts] = content.split(':');
          elements.push(
            <p key={i} className="key-value">
              <strong>{label}:</strong> {valueParts.join(':')}
            </p>
          );
        } else {
          elements.push(<p key={i}><strong>{content}</strong></p>);
        }
      } else if (line.startsWith('  - ')) {
        elements.push(<li key={i}>{line.substring(4)}</li>);
      } else if (line.trim() === '') {
        elements.push(<br key={i} />);
      } else if (line.match(/^\d+\./)) {
        // Numbered list item
        elements.push(<li key={i} className="numbered">{line}</li>);
      } else {
        elements.push(<p key={i}>{line}</p>);
      }
    }
    
    return elements;
  };

  return (
    <div className="document-view">
      <h2>Document</h2>
      <div className="document-content">
        {formattedDocument ? (
          <div className="formatted-document">
            {formatText(formattedDocument)}
          </div>
        ) : (
          <div className="empty-state">No document content yet...</div>
        )}
      </div>
      <style>{`
        .document-view {
          display: flex;
          flex-direction: column;
          height: 100%;
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 16px;
          background: #fff;
        }
        .document-view h2 {
          margin: 0 0 12px 0;
          font-size: 18px;
          font-weight: 600;
          color: #333;
        }
        .document-content {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          background: #f9f9f9;
          border-radius: 4px;
        }
        .formatted-document {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
          font-size: 14px;
          line-height: 1.8;
          color: #333;
        }
        .formatted-document h1 {
          font-size: 24px;
          font-weight: 700;
          margin: 24px 0 16px 0;
          color: #1a1a1a;
          border-bottom: 2px solid #4CAF50;
          padding-bottom: 8px;
        }
        .formatted-document h2 {
          font-size: 20px;
          font-weight: 600;
          margin: 20px 0 12px 0;
          color: #2a2a2a;
        }
        .formatted-document p {
          margin: 8px 0;
        }
        .formatted-document .key-value {
          margin: 8px 0;
        }
        .formatted-document .key-value strong {
          color: #4CAF50;
        }
        .formatted-document li {
          margin: 6px 0;
          padding-left: 8px;
        }
        .formatted-document li.numbered {
          list-style: decimal;
          margin-left: 20px;
        }
        .formatted-document strong {
          font-weight: 600;
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

