# Chatroom Backend Documentation

## Documents

| Document                    | What it covers                                              |
|-----------------------------|-------------------------------------------------------------|
| [architecture-overview.md](architecture-overview.md) | System design, request flow, module map, concurrency model |
| [module-reference.md](module-reference.md)           | Every module: exported functions, constants, patterns       |
| [rest-api-reference.md](rest-api-reference.md)       | HTTP endpoints: request/response shapes, error codes        |
| [websocket-protocol.md](websocket-protocol.md)       | WS connection, client→server messages, server→client events |
| [auth-flow.md](auth-flow.md)                         | Token issuance, WS authentication, brute-force detection    |
| [agent-invocation-pipeline.md](agent-invocation-pipeline.md) | How agents are triggered, queued, spawned, and chained |
| [prompt-injection-defense.md](prompt-injection-defense.md)   | Threat model, sanitization layers, trust boundaries  |
| [rate-limiting.md](rate-limiting.md)                 | All rate limiters: algorithm, limits, locations             |
| [database-schema.md](database-schema.md)             | Tables, columns, indexes, pagination pattern                |
| [configuration.md](configuration.md)                 | All env vars, fixed constants, examples                     |
| [security.md](security.md)                           | Full security controls by category, known limitations       |
| [testing-guide.md](testing-guide.md)                 | How to run tests, database strategy, file inventory         |

## Quick Start

```bash
cd chatroom/apps/backend

# Run in development
bun run dev

# Run tests
bun test

# Check types
bun run build
```

See [configuration.md](configuration.md) for env var reference.
