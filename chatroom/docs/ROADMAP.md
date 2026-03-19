# Chatroom — Roadmap

Estado actualizado: 2026-03-19

## Leyenda

- **B** = Backend
- **F** = Frontend
- **B+F** = Ambos

---

## Fase 0 — Rediseño completo del frontend (Urgente)

Rediseño integral de la interfaz del chatroom basado en los mockups generados por los agentes. Esto define la estructura visual y de componentes sobre la que se montan todas las demás fases de frontend.

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 0.1 | Implementar mockups | PENDIENTE | Rediseño completo del frontend siguiendo los mockups existentes. Revisar mockups antes de empezar. |
| 0.2 | Layout principal | PENDIENTE | Estructura de paneles: sidebar de agentes, chat central, panel de detalle. Responsive. |
| 0.3 | Card de agente rediseñada | PENDIENTE | Card con estado visual (idle/thinking/tool/done/error/exhausted), métricas (tokens, turnos, herramientas), y controles (play/pause/stop/chat) al hacer hover. |
| 0.4 | Tema y design system | PENDIENTE | Colores, tipografía, espaciado, dark mode. Coherente con los mockups. |

---

## Fase 1 — Control de agentes

Prioridad máxima. Sin esto no se puede operar el chatroom de forma cómoda.

### Backend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 1.1 | Kill individual | MISSING | Endpoint o comando WS para matar un agente específico por PID/nombre. SIGTERM al subprocess + cleanup de cola + broadcast de estado `dead` a todos los clientes. |
| 1.2 | Kill all (mejora) | PARCIAL | `@everyone stop` existe pero solo pausa cola. Necesita matar procesos activos realmente (SIGTERM a cada subprocess). Iterar `runningAgents` y matar cada uno. |
| 1.3 | Pause/Resume agente | MISSING | SIGSTOP/SIGCONT al subprocess de Claude CLI. Validar primero si Claude CLI soporta SIGSTOP sin corromperse. Si no lo soporta, solo pause de cola (no aceptar nuevas invocaciones para ese agente). Broadcast estado `paused`/`resumed`. |
| 1.4 | Cola visible | MISSING | Broadcast por WS del estado de la cola cada vez que cambia: array de `{ agentName, position, priority, enqueuedAt }`. Nuevo tipo de mensaje WS `ServerQueueState`. |

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 1.5 | Botones de control en card | MISSING | Al hover sobre card de agente: botones play (invocar), pause, stop, chat (abrir conversación con ese agente). Iconos. Cada botón dispara el comando WS correspondiente. |
| 1.6 | Botón kill all global | PARCIAL | Botón visible en la toolbar que envía kill all. Confirmación antes de ejecutar. |
| 1.7 | Widget de cola | MISSING | Panel que muestra los agentes en cola con su posición y prioridad. Actualizado en tiempo real vía WS. |

---

## Fase 2 — Errores y resiliencia

Los errores ya se detectan en el backend pero no llegan bien al frontend.

### Backend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 2.1 | Error broadcast tipado | PARCIAL | Hoy los errores van como system messages genéricos. Crear un evento WS dedicado `ServerAgentError` con campos: `agentName`, `errorType` (enum: `overload`, `context_overflow`, `rate_limit`, `crash`, `timeout`), `message`, `retryable`. El front necesita distinguir qué pasó. |
| 2.2 | Estado exhausted/dead | MISSING | Cuando un agente muere o se queda sin contexto, persistir su estado en memoria como `exhausted` o `dead`. Broadcast `ServerAgentStatus` con ese estado. No hacer retry automático — exponer el estado y dejar que el usuario decida. |
| 2.3 | Endpoint re-invocar | MISSING | `POST /api/rooms/:id/reinvoke/:agentName` o comando WS `reinvoke_agent`. Crea una nueva sesión de Claude para ese agente con un resumen del contexto anterior. El agente arranca fresco pero con memoria de lo que pasó. |
| 2.4 | Contexto restante | PARCIAL | `contextWindow` ya se captura por mensaje. Falta calcular `remaining = contextWindow - inputTokens - outputTokens` acumulado por sesión de agente, persistirlo, y broadcasterlo con cada `ServerAgentStatus`. |

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 2.5 | Card muestra error tipado | MISSING | Cuando llega `ServerAgentError`, la card del agente muestra el tipo de error con icono y color específico. Overload = naranja, crash = rojo, context overflow = amarillo. |
| 2.6 | Botones re-invocar / matar | MISSING | Cuando un agente está en estado `exhausted` o `dead`, la card muestra dos botones: "Re-invocar" (nueva sesión) y "Matar" (eliminar definitivamente). El usuario elige. No se hace nada automáticamente. |
| 2.7 | Barra de contexto restante | PARCIAL | Barra de progreso en la card del agente que muestra % de contexto consumido. Se actualiza con cada mensaje. Haiku = 200K, Sonnet = 200K, Opus = 1M. Colores: verde >50%, amarillo 20-50%, rojo <20%. |

---

## Fase 3 — Multi-room y historiales

### Backend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 3.1 | Room CRUD | PARCIAL | Solo existe GET. Crear endpoints: `POST /api/rooms` (crear room con nombre aleatorio o dado), `DELETE /api/rooms/:id` (borrar room + todos sus mensajes), `PUT /api/rooms/:id` (renombrar), `POST /api/rooms/:id/clear` (vaciar mensajes pero mantener room). |
| 3.2 | Room resumen | MISSING | Endpoint `GET /api/rooms` devuelve para cada room: nombre, último mensaje (preview), fecha último mensaje, número de mensajes, agentes activos con su estado y contexto restante. |
| 3.3 | Archivar room | MISSING | `POST /api/rooms/:id/archive`. Marca el room como archivado (campo `archived_at` en DB). Mata todos los agentes de ese room. Los rooms archivados no aparecen en la lista principal pero sí en el histórico. Se pueden reabrir con `POST /api/rooms/:id/unarchive`. |
| 3.4 | Agentes por room | PARCIAL | Los agentes ya están scoped por room. Falta: al crear un room, no hay agentes activos. Al cerrar un room, se matan todos sus agentes. Persistir sesiones de agente por room. |

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 3.5 | Pestañas de rooms | PARCIAL | Backend soporta multi-room. Front necesita pestañas/tabs para cambiar entre rooms sin perder estado WS. Cada pestaña mantiene su scroll position y mensajes cargados. |
| 3.6 | Panel de histórico | MISSING | Vista de lista con todos los rooms (activos + archivados). Cada entrada muestra: nombre, resumen, fecha, agentes y contexto restante. Click para abrir/reabrir. Poder leer el chat desde aquí sin reactivar agentes. |
| 3.7 | Crear/borrar/vaciar room | MISSING | Botón "+" para crear room. Menú contextual en cada room: renombrar, vaciar, archivar, borrar. Confirmación para borrar y vaciar. |

---

## Fase 4 — Reacciones

### Backend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 4.1 | Modelo de reacciones | MISSING | Tabla `reactions` (`id`, `message_id`, `author`, `emoji`, `created_at`). Unique constraint en `(message_id, author, emoji)` para no duplicar. |
| 4.2 | WS commands | MISSING | Comando WS `add_reaction` y `remove_reaction` con `{ messageId, emoji }`. Broadcast `ServerReaction` a todos los clientes del room con `{ messageId, author, emoji, action: 'add'|'remove' }`. |
| 4.3 | API de reacciones | MISSING | `GET /api/rooms/:id/messages/:msgId/reactions` para cargar reacciones al scroll. Incluir reacciones en el payload de `load_history`. |
| 4.4 | Agentes leen reacciones | MISSING | Cuando un agente está activo y alguien reacciona a uno de sus mensajes o a un mensaje que lo menciona, incluir la reacción en el contexto del agente. Ej: "Bex reacted with 👍 to your message about..." — el agente lo interpreta como confirmación. |

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 4.5 | UI de reacciones | MISSING | Hover sobre mensaje muestra botón "+😀". Click abre picker de emojis (set reducido o libre). Reacciones aparecen debajo del mensaje como pills con emoji + conteo. Click en una pill existente = toggle tu reacción. |
| 4.6 | Reacciones en tiempo real | MISSING | Al recibir `ServerReaction`, actualizar el conteo en el mensaje correspondiente sin reload. Animación sutil al añadir. |

---

## Fase 5 — Mejoras de chat

### Backend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 5.1 | Upload de archivos | MISSING | `POST /api/rooms/:id/upload` con multipart. Guardar en `data/uploads/<roomId>/`. Límite de tamaño configurable. Devolver URL relativa. Broadcast mensaje de tipo `file` con metadata (nombre, tamaño, mime type, URL). |

### Frontend

| # | Feature | Estado | Descripción |
|---|---------|--------|-------------|
| 5.2 | Diff viewer inline | MISSING | Detectar code blocks con formato diff (```diff o líneas con +/-). Renderizar con syntax highlighting tipo GitHub: verde para añadidos, rojo para borrados, gris para contexto. Usar librería ligera (react-diff-viewer o custom con CSS). |
| 5.3 | Copy code block | MISSING | Botón "Copiar" en la esquina superior derecha de cada code block. Click → copia al clipboard → feedback visual "Copiado" durante 2s. |
| 5.4 | Links a IDE | MISSING | Parsear paths en mensajes tipo `src/foo.ts:42` o `/absolute/path.ts`. Generar links con protocolo configurable: `vscode://file/...`, `cursor://file/...`. Ctrl+click abre en el IDE. Configuración en settings del chat para elegir IDE. |
| 5.5 | Drag & drop archivos | MISSING | Drop zone en el área de chat. Al soltar archivos, subirlos vía endpoint de upload (5.1) y mostrar preview antes de enviar. Soportar imágenes, código, y documentos. |
| 5.6 | Preview imágenes inline | MISSING | Si un mensaje contiene una URL de imagen (subida o externa), renderizar preview inline con lightbox al click. Tamaño máximo configurable. Lazy loading. |
| 5.7 | File tree interactivo | MISSING | Cuando un agente menciona múltiples archivos, agruparlos en un árbol colapsable. Nodos clicables que abren el archivo en el IDE (usa misma config que 5.4). Parseo automático de paths en el contenido del mensaje. |

---

## Futuro (sin prioridad)

| # | Feature | Capa | Notas |
|---|---------|------|-------|
| F.1 | Búsqueda en historial | B+F | Full-text search en mensajes. Endpoint `GET /api/rooms/:id/search?q=...` con FTS5 de SQLite. UI con barra de búsqueda + filtros (agente, fecha, tipo de mensaje). Highlight de resultados. |
| F.2 | Exportar conversación | B+F | Export como MD, PDF o JSON. Endpoint `GET /api/rooms/:id/export?format=md`. Botón de descarga en el menú del room. Incluir metadata de agentes y métricas. |

---

## Ya implementado (referencia)

No tocar — solo para saber qué ya está hecho.

| Feature | Dónde |
|---------|-------|
| @mention con autocompletado | `useMentionAutocomplete` hook + `MentionDropdown` |
| Kill all (`@everyone stop`) | `ws-message-handlers.ts` — pausa cola |
| Prioridad usuario en cola | `agent-queue.ts` — `priority=true` para humanos |
| Markdown rendering | `MessageLine.tsx` con ReactMarkdown |
| Indicadores de estado (thinking/tool/done/error) | `ParticipantItem.tsx` + `ServerAgentStatus` WS |
| Métricas por mensaje (tokens, turnos, herramientas) | `protocol.ts` metadata + `MessageLine.tsx` |
| Persistencia de historial | SQLite + `load_history` WS command |
| Multi-room backend | DB schema con `room_id` + queries scoped |
| Detección de overload/429/context overflow | `agent-result.ts` — parseo de stderr |
| Re-invocación automática (stale session, overflow) | `agent-result.ts` — retry con flag `isRetry` |
| Auth por token | `auth-tokens.ts` + WS upgrade validation |
