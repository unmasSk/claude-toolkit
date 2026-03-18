/**
 * Unit tests for auth-tokens.ts — validateName and issueToken.
 *
 * These tests exercise the pure in-memory logic; no HTTP server needed.
 */
import { describe, it, expect } from 'bun:test';
import { validateName, issueToken, validateToken } from './auth-tokens.js';

// ---------------------------------------------------------------------------
// validateName
// ---------------------------------------------------------------------------

describe('validateName', () => {
  it('returns null for empty string (frontend must send explicit name)', () => {
    expect(validateName('')).toBeNull();
  });

  it('returns null for undefined (frontend must send explicit name)', () => {
    expect(validateName(undefined)).toBeNull();
  });

  it('returns null for whitespace only', () => {
    expect(validateName('   ')).toBeNull();
  });

  it('allows "user" as an explicit name (frontend default identity)', () => {
    expect(validateName('user')).toBe('user');
  });

  it('returns null for "claude" (bridge identity — must stay blocked)', () => {
    expect(validateName('claude')).toBeNull();
  });

  it('returns null for "claude" regardless of case', () => {
    expect(validateName('Claude')).toBeNull();
    expect(validateName('CLAUDE')).toBeNull();
  });

  it('returns the trimmed name for a valid custom name', () => {
    expect(validateName('alice')).toBe('alice');
    expect(validateName('  bob  ')).toBe('bob');
  });

  it('returns null for names with invalid characters', () => {
    expect(validateName('bad name')).toBeNull();   // space
    expect(validateName('bad@name')).toBeNull();   // @
    expect(validateName('bad/name')).toBeNull();   // /
  });

  it('returns null for names exceeding 32 characters', () => {
    expect(validateName('a'.repeat(33))).toBeNull();
  });

  it('accepts names at the 32-character boundary', () => {
    const name = 'a'.repeat(32);
    expect(validateName(name)).toBe(name);
  });

  it('allows hyphens and underscores', () => {
    expect(validateName('my-user')).toBe('my-user');
    expect(validateName('my_user')).toBe('my_user');
  });

  it('returns null for known agent names (e.g. "bilbo", "ultron")', () => {
    // Agent names are loaded from AGENT_BY_NAME — these must be blocked
    expect(validateName('bilbo')).toBeNull();
    expect(validateName('ultron')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// issueToken + validateToken
// ---------------------------------------------------------------------------

describe('issueToken + validateToken', () => {
  it('issues a token for a valid name', () => {
    const result = issueToken('user');
    expect(result).not.toBeNull();
    expect(typeof result!.token).toBe('string');
    expect(typeof result!.expiresAt).toBe('string');
  });

  it('issued token is a valid UUID', () => {
    const result = issueToken('alice');
    const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    expect(uuidRe.test(result!.token)).toBe(true);
  });

  it('validateToken returns the name for a valid token', () => {
    const result = issueToken('user');
    expect(validateToken(result!.token)).toBe('user');
  });

  it('validateToken returns null for an unknown token', () => {
    expect(validateToken('not-a-real-token')).toBeNull();
  });

  it('validateToken returns null when token is undefined', () => {
    expect(validateToken(undefined)).toBeNull();
  });

  it('expiresAt is an ISO date string in the future', () => {
    const result = issueToken('user');
    const exp = new Date(result!.expiresAt).getTime();
    expect(exp).toBeGreaterThan(Date.now());
  });
});
