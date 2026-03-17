# Log de progreso — Chatroom

Sesion autonoma nocturna. El usuario se fue a dormir.

## Pendiente
- [x] Identidad en conexion WS: query param `?name=` para que cada cliente se identifique
- [x] AGENT_DIR corregido en config.ts para apuntar al cache del toolkit
- [x] Panel de participantes muestra usuarios reales conectados, no placeholders
- [x] Invocacion de agentes verificada: 10 agentes invokables en /api/agents
- [ ] Test real de @bilbo con claude -p (requiere sesion interactiva)
- [x] Dante escribio 52 tests nuevos para features de identidad WS, config, schemas
- [x] 458 tests totales, 0 fail
- [x] Commiteado: feat(plugin/chatroom) — 0a06fa7

## Log

- Fix 1 (WS identity): Agregado query param `?name=` en el WS. El servidor usa ese nombre como `author`. Sin param → default `user`.
- Fix 1 (validacion de nombre): Nombres de agentes invocables (bilbo, ultron, etc.) bloqueados. `claude` y `user` permitidos.
- Fix 1 (ConnectedUser): Nuevo tipo `ConnectedUser` en el protocolo compartido. Incluido en `room_state.connectedUsers`.
- Fix 2 (AGENT_DIR): Config.ts ahora usa `globSync` para encontrar el directorio de agentes en el cache del toolkit (`~/.claude/plugins/cache/.../agents`). Con fallback relativo.
- Fix 3 (participantes reales): El `open` handler registra el usuario conectado en un Map por sala. Los usuarios aparecen en `room_state.connectedUsers`.
- Fix 4 (verificacion agentes): Confirmado que `GET /api/agents` devuelve 10 agentes invocables. AGENT_DIR resuelve correctamente al path del toolkit.
- Fix 5 (frontend URL): `ws-store.ts` ahora conecta con `?name=user` en la URL del WS.
- Fix 6 (panel participantes): `ParticipantPanel.tsx` y `agent-store.ts` actualizados para mostrar usuarios humanos conectados (de `connectedUsers`) separados de los agentes.
- Schemas: `ConnectedUserSchema` agregado y `ServerRoomStateSchema` actualizado con `connectedUsers`. Tests actualizados.
- Tests: 405 pass, 0 fail.
- Backend y frontend reiniciados correctamente.
- Dante: 52 tests nuevos — WS identity (23), ConnectedUser schemas (9), config resolveAgentDir (9), integracion WS (6), mas schemas connectedUsers (5).
- Total: 458 tests, 0 fail, 757ms.
- Commit: feat(plugin/chatroom) — 75 archivos, 0a06fa7.
- Pendiente para manana: test real con @bilbo via claude -p (requiere sesion interactiva con Max plan).
