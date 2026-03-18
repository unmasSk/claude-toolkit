/**
 * auth-tokens.ts
 *
 * Simple in-memory token store for WebSocket authentication.
 * Clients obtain a short-lived token via POST /api/auth/token and present
 * it on WS upgrade as ?token=<uuid>.
 *
 * SEC-AUTH-001: Token validation before WS upgrade
 */

import { AGENT_BY_NAME } from '@agent-chatroom/shared';

// ---------------------------------------------------------------------------
// Name validation (mirrors resolveConnectionName in ws.ts)
// ---------------------------------------------------------------------------

const RESERVED_AGENT_NAMES = new Set(
  Array.from(AGENT_BY_NAME.keys()).filter((n) => n !== 'user' && n !== 'claude')
);
const NAME_RE = /^[a-zA-Z0-9_-]{1,32}$/;

/** Returns the normalised name or null if invalid / reserved. */
export function validateName(rawName: string | undefined): string | null {
  if (!rawName || rawName.trim() === '') return 'user';
  const name = rawName.trim();
  if (!NAME_RE.test(name)) return null;
  if (RESERVED_AGENT_NAMES.has(name.toLowerCase())) return null;
  return name;
}

// ---------------------------------------------------------------------------
// Token store
// ---------------------------------------------------------------------------

const TOKEN_TTL_MS = 30 * 60 * 1000; // 30 minutes — survives reconnect backoff

interface TokenEntry {
  name: string;
  expiresAt: number;
}

const tokens = new Map<string, TokenEntry>();

/** Issue a new UUID token bound to a validated name. Returns null if the token store is full. */
export function issueToken(name: string): { token: string; expiresAt: string } | null {
  if (tokens.size >= 10_000) {
    return null;
  }
  const token = crypto.randomUUID();
  const expiresAt = Date.now() + TOKEN_TTL_MS;
  tokens.set(token, { name, expiresAt });
  return { token, expiresAt: new Date(expiresAt).toISOString() };
}

/**
 * Validate a token and return the associated name.
 * Returns null if the token is missing, unknown, or expired.
 */
export function validateToken(token: string | undefined): string | null {
  if (!token) return null;
  const entry = tokens.get(token);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    tokens.delete(token);
    return null;
  }
  return entry.name;
}

// Periodic GC — remove expired tokens every 10 minutes
setInterval(() => {
  const now = Date.now();
  for (const [tok, entry] of tokens) {
    if (now > entry.expiresAt) tokens.delete(tok);
  }
}, 10 * 60 * 1000);
