# Rate Limiting

## Algorithm

All rate limiting uses a shared token-bucket implementation (`services/rate-limiter.ts`). Each bucket is independent — buckets for different routes or connections do not share state.

```ts
const check = createTokenBucket(max, windowMs);
// max   = tokens per window (burst capacity)
// windowMs = rolling window duration in milliseconds

if (!check('key')) {
  // rejected
}
```

**Refill behavior:** Tokens are refilled proportionally to elapsed time within the window. A bucket for `max=20, windowMs=60000` refills at `20/60000` tokens per millisecond. The bucket never exceeds `max`.

## Deployed Limiters

### POST /api/auth/token

- **Limit:** 20 requests per 60 seconds
- **Key:** `'auth-token'` (global, not per-IP)
- **Response on limit:** `429 { error, code: 'RATE_LIMIT' }`

### POST /api/rooms/:id/invite

- **Limit:** 20 requests per 60 seconds
- **Key:** `'invite'` (global, not per-IP)
- **Response on limit:** `429 { error, code: 'RATE_LIMIT' }`

These two endpoints share the same `createTokenBucket` call in `api.ts` but use different string keys, so they have independent quotas. One cannot starve the other.

### WS upgrade rate limit

- **Limit:** 50 upgrades per 1 second
- **Key:** `'global'` (all connections share one bucket)
- **Response on limit:** `error` message sent, then `ws.close()`
- **Code:** `'UPGRADE_RATE_LIMIT'`

### WS per-connection message rate limit

- **Limit:** 5 messages per 10 seconds
- **Key:** `connId` (unique per connection)
- **Response on limit:** `error` message, connection stays open
- **Code:** `'RATE_LIMIT'`
- **Logging:** `logger.warn` on every rate-limit event (enables intrusion detection)

## Why Global Keys for API Routes

X-Forwarded-For headers are trivially spoofable when the backend does not control the upstream proxy. A global bucket provides a hard ceiling on token issuance throughput regardless of the source address. The trade-off: a legitimate client surge can briefly lock out all other clients. This is considered acceptable given the low limits and the 60-second window.

## Per-Room Connection Cap

Not a rate limiter but closely related: each room has a hard cap of 20 simultaneous connections. This check runs before the auth token is consumed, so an attacker cannot exhaust tokens by connecting to a full room.

Response: `error` message + `ws.close()`, code `'ROOM_FULL'`.

## Internal API Rate Limit (Claude API)

When a `claude` subprocess exits without producing a result, `stderrOutput` is checked for:
- `429`
- `rate limit` (case-insensitive)
- `overloaded` (case-insensitive)
- `too many requests` (case-insensitive)

If detected and this is the first attempt, the invocation is retried after 12 seconds. The in-flight lock is released during the wait so other agents can proceed. Only one retry per invocation chain.
