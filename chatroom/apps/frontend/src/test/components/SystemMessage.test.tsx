/**
 * SystemMessage — formatContent behavior.
 *
 * formatContent capitalizes the agent name but keeps the full text intact.
 * The "Agent" word is removed and the name is capitalized.
 *
 * Display structure: <te-agent>house</te-agent> › <te-badge>queued</te-badge> <te-desc>{formatContent(...)}</te-desc>
 * Example: "Agent yoda is busy." → "Yoda is busy."
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SystemMessage } from '../../components/SystemMessage';
import type { Message } from '@agent-chatroom/shared';

function makeMessage(content: string): Message {
  return {
    id: 'msg-1',
    roomId: 'default',
    role: 'system',
    content,
    createdAt: new Date().toISOString(),
    agentName: null,
    sessionId: null,
    thinkingContent: null,
    attachments: [],
  } as unknown as Message;
}

describe('SystemMessage — formatContent capitalizes agent name, keeps full text', () => {
  it('capitalizes agent name in queued message (mixed case)', () => {
    render(<SystemMessage message={makeMessage('Agent House is busy. Message queued (3 pending).')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('House is busy. Message queued (3 pending).');
  });

  it('capitalizes agent name from lowercase prefix', () => {
    render(<SystemMessage message={makeMessage('Agent house is busy. Message queued (1 pending).')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('House is busy. Message queued (1 pending).');
  });

  it('capitalizes agent name from uppercase prefix', () => {
    render(<SystemMessage message={makeMessage('AGENT BILBO is running.')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('BILBO is running.');
  });

  it('te-agent shows lowercase agent name, te-desc starts with capitalized name', () => {
    render(<SystemMessage message={makeMessage('Agent house is busy. Message queued (3 pending).')} />);
    const agent = document.querySelector('.te-agent');
    const desc = document.querySelector('.te-desc');
    expect(agent?.textContent).toBe('house');
    expect(desc?.textContent).toBe('House is busy. Message queued (3 pending).');
  });

  it('passes through content with no "Agent X" prefix unchanged', () => {
    render(<SystemMessage message={makeMessage('Connection established.')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('Connection established.');
  });

  it('returns "directiva" for DIRECTIVE FROM USER messages', () => {
    render(<SystemMessage message={makeMessage('[DIRECTIVE FROM USER] do something')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('directiva');
  });

  it('keeps text after agent name including a period boundary', () => {
    // "Agent Foo. Some message" — "Agent Foo" → "Foo", rest preserved as-is
    render(<SystemMessage message={makeMessage('Agent Foo. Some message.')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('Foo. Some message.');
  });

  it('only capitalizes the first word after Agent, keeps remaining words intact', () => {
    // "Agent House And Something." → "House And Something."
    render(<SystemMessage message={makeMessage('Agent House And Something.')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.textContent).toBe('House And Something.');
  });

  it('te-desc has te-desc-ltr class (RTL dot prevention)', () => {
    render(<SystemMessage message={makeMessage('Agent yoda is busy. Message queued (1 pending).')} />);
    const desc = document.querySelector('.te-desc');
    expect(desc?.classList.contains('te-desc-ltr')).toBe(true);
  });
});
