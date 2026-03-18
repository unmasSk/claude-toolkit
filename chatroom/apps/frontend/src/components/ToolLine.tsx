import { memo } from 'react';
import type { Message } from '@agent-chatroom/shared';
import { getToolIcon } from '../lib/icons';

interface ToolLineProps {
  message: Message;
}

export const ToolLine = memo(function ToolLine({ message }: ToolLineProps) {
  const toolName = message.metadata?.tool ?? 'Tool';
  const Icon = getToolIcon(toolName);
  const safeAuthor = message.author || 'unknown';
  const authorName = safeAuthor.charAt(0).toUpperCase() + safeAuthor.slice(1);

  return (
    <div className="tool-line">
      <span className={`tool-agent c-${safeAuthor.toLowerCase()}`}>{authorName}</span>
      <Icon size={11} />
      <span className="tool-badge">{toolName}</span>
      <span>{message.content}</span>
    </div>
  );
});
