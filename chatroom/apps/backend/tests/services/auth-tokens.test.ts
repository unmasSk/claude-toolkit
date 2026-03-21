/**
 * Unit tests for auth-tokens.ts — validateName, issueToken, validateToken, peekToken.
 *
 * These tests exercise the pure in-memory logic; no HTTP server needed.
 */
import { describe, it, expect, beforeEach, afterEach, setSystemTime } from 'bun:test';
import { validateName, issueToken, validateToken, peekToken, __resetForTests } from '../../src/services/auth-tokens.js';

beforeEach(() => {
  __resetForTests();
});

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

  it('allows "claude" as a valid user name (chatroom is private)', () => {
    expect(validateName('claude')).toBe('claude');
  });

  it('allows "claude" regardless of case', () => {
    expect(validateName('Claude')).toBe('Claude');
    expect(validateName('CLAUDE')).toBe('CLAUDE');
  });

  it('returns the trimmed name for a valid custom name', () => {
    expect(validateName('alice')).toBe('alice');
    expect(validateName('  bob  ')).toBe('bob');
  });

  it('returns null for names with invalid characters', () => {
    expect(validateName('bad name')).toBeNull(); // space
    expect(validateName('bad@name')).toBeNull(); // @
    expect(validateName('bad/name')).toBeNull(); // /
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

// ---------------------------------------------------------------------------
// peekToken — validates without consuming
// SEC-AUTH: peekToken must NOT delete the token from the store so the caller
// can still use the same token for a WS upgrade after calling /invite.
// ---------------------------------------------------------------------------

describe('peekToken', () => {
  it('returns the name for a valid token', () => {
    const result = issueToken('alice');
    expect(peekToken(result!.token)).toBe('alice');
  });

  it('does NOT consume the token — token is still valid after peek', () => {
    const result = issueToken('bob');
    const token = result!.token;
    // Peek once
    const name1 = peekToken(token);
    // Peek again — must still return the name (not null)
    const name2 = peekToken(token);
    expect(name1).toBe('bob');
    expect(name2).toBe('bob');
  });

  it('does NOT consume the token — validateToken can still use it after peek', () => {
    const result = issueToken('carol');
    const token = result!.token;
    // Peek first (non-consuming)
    const peeked = peekToken(token);
    // Then validate (consuming) — must succeed
    const validated = validateToken(token);
    expect(peeked).toBe('carol');
    expect(validated).toBe('carol');
    // Now the token IS consumed — a second validateToken returns null
    const reused = validateToken(token);
    expect(reused).toBeNull();
  });

  it('returns null for an unknown token', () => {
    expect(peekToken('not-a-real-token')).toBeNull();
  });

  it('returns null when token is undefined', () => {
    expect(peekToken(undefined)).toBeNull();
  });

  it('returns null for an empty string', () => {
    expect(peekToken('')).toBeNull();
  });

  it('returns null for an expired token (simulated via validateToken consumption + re-issue)', () => {
    // peekToken deletes expired entries from the store.
    // We cannot control Date.now() without monkey-patching, but we can verify
    // the expired-then-deleted path by inspecting that a consumed token returns null.
    // The token consumed by validateToken is the closest proxy available in unit tests.
    const result = issueToken('dave');
    const token = result!.token;
    validateToken(token); // consume it
    // Now the token no longer exists in the store — peekToken must return null
    expect(peekToken(token)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Token expiration — time-travel tests using setSystemTime
//
// TTL is 30 minutes (TOKEN_TTL_MS). We issue a token, fast-forward the clock
// past expiresAt, then assert the auth functions return null.
// setSystemTime is restored after each test via afterEach so real-time tests
// in other blocks are unaffected.
// ---------------------------------------------------------------------------

const TOKEN_TTL_MS = 30 * 60 * 1000; // mirrors auth-tokens.ts constant

describe('peekToken — token expiration', () => {
  afterEach(() => {
    // Restore real wall-clock time so subsequent tests are unaffected.
    setSystemTime();
  });

  it('returns null when clock is advanced past the token TTL', () => {
    const issuedAt = Date.now();
    const result = issueToken('expiry-peek-user');
    const token = result!.token;

    // Sanity: token is valid before expiry
    expect(peekToken(token)).toBe('expiry-peek-user');

    // Fast-forward 1 ms past expiresAt
    setSystemTime(new Date(issuedAt + TOKEN_TTL_MS + 1));

    expect(peekToken(token)).toBeNull();
  });

  it('removes the expired entry from the store (subsequent peekToken also returns null)', () => {
    const issuedAt = Date.now();
    const result = issueToken('expiry-peek-gc-user');
    const token = result!.token;

    setSystemTime(new Date(issuedAt + TOKEN_TTL_MS + 1));

    // First call detects expiry and deletes the entry
    expect(peekToken(token)).toBeNull();
    // Second call: entry is already gone — must still return null, not throw
    expect(peekToken(token)).toBeNull();
  });
});

describe('validateToken — token expiration', () => {
  afterEach(() => {
    setSystemTime();
  });

  it('returns null when clock is advanced past the token TTL', () => {
    const issuedAt = Date.now();
    const result = issueToken('expiry-validate-user');
    const token = result!.token;

    // Fast-forward 1 ms past expiresAt (token was issued at issuedAt, expires at issuedAt + TTL)
    setSystemTime(new Date(issuedAt + TOKEN_TTL_MS + 1));

    expect(validateToken(token)).toBeNull();
  });

  it('does not consume the token slot when rejecting due to expiry (token is deleted, not returned)', () => {
    const issuedAt = Date.now();
    const result = issueToken('expiry-no-consume-user');
    const token = result!.token;

    setSystemTime(new Date(issuedAt + TOKEN_TTL_MS + 1));

    // Expired — must return null (not the name)
    expect(validateToken(token)).toBeNull();
    // Token was deleted during expiry check — a second call also returns null
    expect(validateToken(token)).toBeNull();
  });
});
