# PROGRESS — Agent Chatroom

## 2026-03-18 — Ultron: Issues #27, #30, #26, #32

### Issue #27 — WS_ALLOWED_ORIGINS configurable
- `config.ts`: añadida constante `WS_ALLOWED_ORIGINS` leída de env var (comma-separated), con fallback a los dos orígenes por defecto. En dev agrega `''` para wscat/curl.
- `ws.ts`: eliminado el `Set` hardcodeado de `ALLOWED_ORIGINS`. Ahora importa de config y construye el Set desde ahí.

### Issue #26 — Markdown en mensajes
- `bun add react-markdown` (v10.1.0) en `apps/frontend`.
- `MessageLine.tsx`: reemplaza el render de texto plano con `<ReactMarkdown>`. Usa componentes custom para párrafos (inline, no `<p>` block), code inline, code blocks, listas. Layout IRC-style preservado: timestamp y autor no se tocan.
- `globals.css`: añadidos estilos para `.md-para`, `.md-code-inline`, `.md-pre`, `.md-code-block`, `.md-ul`, `.md-ol`, `.md-li`.

### Validación
- `bun test`: 460 pass, 0 fail
- `bunx vite build`: build limpio (398 KB JS, 10 KB CSS)

## 2026-03-18 — Session 2: Agent behavior hardening

### triggerContent isolation (`agent-invoker.ts` — `buildPrompt`)
- El trigger original del `@mention` se inyecta como bloque separado (`[ORIGINAL TRIGGER]` / `[END ORIGINAL TRIGGER]`) antes del historial del chat.
- Sanitizado: se elimina el patrón `[END ORIGINAL TRIGGER]` del `triggerContent` para prevenir inyección de marcadores.
- Los agentes ya no confunden el trigger con mensajes posteriores del historial.

### SKIP suppression (`agent-invoker.ts` ~L522)
- Si un agente devuelve exactamente `"SKIP"` (case-insensitive, regex `/^skip\.?$/i`), el mensaje no se inserta en DB ni se emite WS event.
- El agente desaparece silenciosamente — no contamina el historial del chat.

### Agent identities + anti-spam rules (`agent-invoker.ts` — `buildSystemPrompt`)
- `AGENT_VOICE` map: voz/personalidad de cada agente inyectada como `"Your voice: ..."` en la primera línea del system prompt.
- 7 reglas anti-spam añadidas al system prompt: supresión de acks vacíos, prohibición de @mention solo por cortesía, SKIP como respuesta válida, etc.
- Regla 2 coherente con regla 1: los dos casos que producen silencio usan SKIP, no "nothing new in one sentence".

### Self-mention guard (`agent-invoker.ts` ~L574)
- `if (name === agentName) continue;` en el bucle de chained mentions.
- Un agente ya no puede auto-invocarse aunque escriba su propio `@nombre` en la respuesta.
