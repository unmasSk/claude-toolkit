import React, { memo, Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '@agent-chatroom/shared';
import { agentColorClass, mentionClass } from '../lib/colors';

// SEC-XSS-001: Allowed URL schemes for markdown links.
// javascript:, data:, and vbscript: are blocked to prevent XSS.
const ALLOWED_SCHEMES = /^(https?:|mailto:)/i;

function sanitizeHref(href: string | undefined): string | undefined {
  if (!href) return undefined;
  if (!ALLOWED_SCHEMES.test(href.trim())) return undefined;
  return href;
}

interface MessageLineProps {
  message: Message;
}

function formatTime(createdAt: string): string {
  try {
    const d = new Date(createdAt);
    const h = d.getHours().toString().padStart(2, '0');
    const m = d.getMinutes().toString().padStart(2, '0');
    return `${h}:${m}`;
  } catch {
    return '--:--';
  }
}

/**
 * Parse a text string and highlight @mentions.
 * Returns React nodes — plain text segments stay as strings, @mentions become
 * <span className="mention …"> elements.
 */
function splitMentions(text: string): React.ReactNode[] {
  const parts = text.split(/(@\w+)/g);
  return parts.map((part, i) => {
    if (part.startsWith('@')) {
      const name = part.slice(1).toLowerCase();
      return (
        <span key={i} className={`mention ${mentionClass(name)}`}>
          {part}
        </span>
      );
    }
    return part;
  });
}

/**
 * Walk a React node tree and replace every string leaf that contains an
 * @mention with the highlighted output of splitMentions.
 * Non-string nodes (elements, arrays) are recursed into so mentions inside
 * bold/italic/code siblings are still highlighted.
 */
function highlightMentionsInNode(node: React.ReactNode, keyPrefix: string): React.ReactNode {
  if (typeof node === 'string') {
    return node.includes('@') ? splitMentions(node) : node;
  }
  if (Array.isArray(node)) {
    return node.map((child, i) => highlightMentionsInNode(child, `${keyPrefix}-${i}`));
  }
  if (isValidElement(node)) {
    const el = node as React.ReactElement<{ children?: React.ReactNode }>;
    const newChildren = highlightMentionsInNode(el.props.children, keyPrefix);
    // Only clone if something actually changed (avoids unnecessary rerenders)
    if (newChildren === el.props.children) return node;
    return React.cloneElement(el, {}, newChildren);
  }
  return node;
}

/**
 * Custom paragraph renderer — renders inline content with @mention highlighting
 * instead of wrapping in a <p> tag (to preserve IRC-style inline layout).
 */
function MdParagraph({ children }: { children?: React.ReactNode }): React.ReactElement {
  const highlighted = Children.map(children, (child, i) =>
    highlightMentionsInNode(child, `mp-${i}`)
  );
  return <span className="md-para">{highlighted}</span>;
}

export const MessageLine = memo(function MessageLine({ message }: MessageLineProps) {
  const safeAuthor = message.author || 'unknown';
  const authorName = safeAuthor.charAt(0).toUpperCase() + safeAuthor.slice(1);
  const bgClass = message.authorType === 'agent' || message.authorType === 'user'
    ? `bg-${safeAuthor.toLowerCase().replace(/\s+/g, '-')}`
    : '';

  return (
    <div className={`message ${bgClass}`}>
      <span className={`msg-author ${agentColorClass(safeAuthor)}`}>
        {authorName}
      </span>
      <span className="msg-content">
        <ReactMarkdown
          components={{
            // SEC-XSS-001: Block javascript:, data:, vbscript: URIs in links
            a: ({ href, children }) => {
              const safeHref = sanitizeHref(href);
              if (!safeHref) return <span>{children}</span>;
              return (
                <a href={safeHref} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              );
            },
            // Render paragraphs inline to preserve IRC-style layout
            p: MdParagraph,
            // Inline code — styled via CSS .md-code-inline
            code: ({ children, className }) => {
              const isBlock = !!className;
              if (isBlock) {
                return <code className={`md-code-block ${className ?? ''}`}>{children}</code>;
              }
              return <code className="md-code-inline">{children}</code>;
            },
            // Code blocks — styled via CSS .md-pre
            pre: ({ children }) => <pre className="md-pre">{children}</pre>,
            // List items and lists
            ul: ({ children }) => <ul className="md-ul">{children}</ul>,
            ol: ({ children }) => <ol className="md-ol">{children}</ol>,
            li: ({ children }) => <li className="md-li">{children}</li>,
          }}
        >
          {message.content}
        </ReactMarkdown>
      </span>
      <span className="msg-time">{formatTime(message.createdAt)}</span>
    </div>
  );
});
