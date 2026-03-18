# Sidebar Card Design — Sesión 2026-03-19

Notas para el próximo Claude que coja esto. Todo lo que decidimos sobre el rediseño del sidebar.

---

## Referencia visual obligatoria

Antes de tocar nada, lee y abre estos dos archivos:

- `chatroom/design-mocks/cerberus-mock-v2.html` — DNA visual de referencia. Este es el estilo que quiere Bex.
- `chatroom/design-mocks/sidebar-card-mockup.html` — El mockup completo que construimos esta sesión. Es el deliverable.

Si no los lees, harás algo mal. Ya pasó en v1.

---

## Qué tiene el mockup (`sidebar-card-mockup.html`)

Tiene tres secciones apiladas verticalmente:

1. **Chatroom real** (920×768) — replica fiel del chatroom actual, estilos de `globals.css`
2. **50px de separación**
3. **Sidebar demo** — panel de 260px con los 10 agentes en cards compactas
4. **States demo** — 3 cards horizontales mostrando los 3 estados de vida de un agente

---

## Anatomía de la card (~72px alto)

```
┌─────────────────────────────────────┐
│ [AVT] nombre          [model] [●]   │  ← fila superior: avatar 26px, nombre, chip modelo, pip estado
│ ~~~~ SVG animado role-specific ~~~  │  ← fila media: actividad visual 22px alto
│ 12.3s | 4 turns | 5.2K/800 tok      │  ← fila inferior: métricas mono 10px
└─────────────────────────────────────┘
```

- Sin session ID (quitado en v2)
- Sin sección de tools (quitado en v2)
- Hover → panel de control lateral (ver más abajo)

---

## Sistema visual — glassmorphism DNA

Variables CSS extraídas de `cerberus-mock-v2.html`:

```css
--glass-panel: rgba(255,255,255,0.04)
--glass-card:  rgba(255,255,255,0.06)
--glass-border: rgba(255,255,255,0.08)
--blur-deep:   blur(20px)
```

Colores OKLCH por agente:
- **Bilbo** (explorer): `oklch(65% 0.15 260)` — azul explorador
- **Ultron** (implementer): `oklch(65% 0.18 140)` — verde código
- **Cerberus** (reviewer): `oklch(65% 0.15 30)` — naranja revisión
- **Argus** (security): `oklch(65% 0.15 0)` — rojo seguridad
- **Dante** (tests): `oklch(65% 0.15 200)` — cyan pruebas
- **Moriarty** (adversarial): `oklch(65% 0.15 300)` — violeta disrupción
- **House** (diagnose): `oklch(65% 0.15 60)` — amarillo diagnóstico
- **Yoda** (judge): `oklch(65% 0.18 160)` — esmeralda sabiduría
- **Alexandria** (docs): `oklch(65% 0.15 240)` — índigo conocimiento
- **Gitto** (git): `oklch(65% 0.15 20)` — coral git

SVG por agente (role-specific):
- Bilbo: gauge animado (exploración)
- Ultron: ECG / heartbeat (implementación activa)
- Cerberus: compass girando (revisión metódica)
- Argus: radar sweep (vigilancia)
- Dante: scales balanceándose (testing equilibrio)
- Moriarty: glitch/distorsión (adversarial)
- House: síntoma pulse (diagnóstico)
- Yoda: branch/tree creciendo (juicio senior)
- Alexandria: libro abriendo páginas (documentación)
- Gitto: git branch flow (historia)

Fondo del sidebar: panel glassmorphism + orbs animados de color + grid overlay con `opacity: 0.03`.

---

## Estados de la card

Tres estados reales derivados del stream de `claude -p --output-format stream-json`:

### 1. THINKING (`assistant` event llegando)
- Pip: azul pulsando
- Chip estado: `thinking` con fondo azul
- Animación SVG: lenta, gauge moviéndose despacio
- Indicador texto: **3 puntos WhatsApp** — `● ● ●` animados con delay escalonado

### 2. TOOL_USE (`tool_use` event)
- Pip: naranja parpadeando
- Chip estado: `tool_use` con fondo naranja + nombre de la tool
- Animación SVG: rápida, código tipeándose
- Indicador texto: chip con nombre de la tool (ej. `Bash`, `Read`, `Edit`)

### 3. WRITING TO CHAT (post `tool_result` → siguiente `assistant` emitiendo texto)
- Pip: verde
- Chip estado: `writing` con fondo verde
- Animación SVG: ECG rápido con punto viajero
- Indicador texto: **burbuja WhatsApp** animada (3 puntos en burbuja gris)

**Importante**: Los tokens solo llegan en el evento `result` final. No hay contador en tiempo real posible con `claude -p`. Para estimación: `≈ 4 chars / token` acumulando el texto del evento `assistant`.

---

## Panel de control (hover lateral)

Se revela en hover de la card. **No visible en reposo** — sale deslizando desde el lado derecho.

```css
.card-actions {
  position: absolute;
  right: -44px;   /* fuera del card en reposo */
  opacity: 0;
  transition: right 0.2s ease, opacity 0.2s ease;
}
.card-wrap:hover .card-actions {
  right: -44px;   /* pegado al borde exterior */
  opacity: 1;
}
```

4 botones en columna (iconos SVG):
1. **Start** (▶) — invocar agente
2. **Pause** (⏸) — SIGSTOP o flag de pausa
3. **Stop** (⏹) — killSession
4. **Read-chat** (💬) — inyectar historial del chat al agente

---

## Lo que hay hecho vs lo que falta

### Hecho ✅
- [x] Mockup completo en `sidebar-card-mockup.html`
- [x] CSS variables glassmorphism sincronizadas con cerberus-mock-v2
- [x] Los 10 agentes con SVG role-specific y colores OKLCH
- [x] Demo de 3 estados con animaciones
- [x] Panel de control hover lateral en el mockup
- [x] Metrics pipeline: stream-parser → agent-invoker → WS → MessageLine.tsx
- [x] `.msg-metrics` en globals.css (`msg-metrics` clase)
- [x] Chat centrado + altura 768px
- [x] Pino structured logging en backend

### Pendiente ⏳
- [ ] **Implementar sidebar React real** — reemplazar el `.panel` actual con los nuevos componentes de card
- [ ] **WS intermediate events** — el backend solo emite el mensaje final; hay que emitir `assistant`, `tool_use`, `tool_result` para que el frontend pueda cambiar estado en tiempo real
- [ ] **Endpoints de control de agente** — Start/Pause/Stop/Read-chat necesitan WS endpoints en backend
- [ ] **Commit todos los cambios actuales** — hay varios archivos sin commitear
- [ ] **Issues GitHub pendientes**: tool event dedup ID, Tauri app, sidebar redesign, stream intermediate events
- [ ] **Tests de Dante**: stderr reading, staggering, rate-limit retry
- [ ] **9 security findings** (de commit `9cc9b6a`): XSS markdown, empty-name bypass, token reuse, token DoS, @everyone global scope, blacklist guard, React.cloneElement

---

## Lo que NO quiere Bex

- Cards grandes (side-by-side en 3 columnas) — v1 rechazada
- Botones siempre visibles — solo en hover
- Session ID en la card
- Sección de tools en la card
- Diseñar sin leer la skill de design primero
- Diseñar sin mirar cerberus-mock-v2.html como referencia

---

## Archivos tocados esta sesión

| Archivo | Qué cambió |
|---------|-----------|
| `chatroom/design-mocks/sidebar-card-mockup.html` | Creado desde cero (v2 completo) |
| `chatroom/apps/frontend/src/styles/globals.css` | `#root` flex centering, altura 768px, clase `.msg-metrics` |
| `chatroom/apps/backend/src/services/stream-parser.ts` | `ResultEvent` interface con todos los campos de métricas |
| `chatroom/apps/backend/src/services/agent-invoker.ts` | Fix 50KB log dump, captura métricas del result event |
| `chatroom/packages/shared/src/schemas.ts` | `MessageMetadataSchema` con durationMs, numTurns, tokens, contextWindow |
| `chatroom/apps/frontend/src/components/MessageLine.tsx` | `formatMetrics()`, `formatModelName()`, render `.msg-metrics` |
| `chatroom/apps/backend/src/logger.ts` | NUEVO — pino root logger con child loggers por módulo |
