import type { ServerMessage, Message } from '@agent-chatroom/shared';
import { createLogger } from '../logger.js';

const logger = createLogger('message-bus');

// ---------------------------------------------------------------------------
// Message bus
// ---------------------------------------------------------------------------

/**
 * Import the Elysia app singleton lazily (at call time, not module load).
 *
 * FIX 3: This avoids circular import issues during startup and lets index.ts
 * fully initialize before any broadcast call happens.
 */
async function getApp() {
  const { app } = await import('../index.js');
  return app;
}

/**
 * Strip sessionId from message metadata before broadcasting.
 *
 * SEC-FIX 5: Session IDs are server-internal identifiers used for `--resume`.
 * They must never reach the frontend — a client with a session ID could
 * potentially influence or hijack a future agent invocation.
 */
function stripSessionId(event: ServerMessage): ServerMessage {
  if (event.type === 'new_message') {
    const { sessionId: _omit, ...safeMetadata } = event.message.metadata;
    return {
      ...event,
      message: {
        ...event.message,
        metadata: safeMetadata,
      } as Message,
    };
  }

  if (event.type === 'room_state') {
    return {
      ...event,
      messages: event.messages.map((msg) => {
        const { sessionId: _omit, ...safeMetadata } = msg.metadata;
        return { ...msg, metadata: safeMetadata };
      }),
    };
  }

  return event;
}

/**
 * Broadcast a server event to all WebSocket clients subscribed to a room.
 *
 * Uses the Elysia app singleton via a lazy import to avoid circular deps (FIX 3).
 * Strips `metadata.sessionId` before sending (SEC-FIX 5).
 * Drops the event with a warning if the server is not yet ready.
 *
 * @param roomId - Target room; subscribers on `room:<roomId>` receive the event
 * @param event - The ServerMessage to broadcast
 */
export async function broadcast(roomId: string, event: ServerMessage): Promise<void> {
  const app = await getApp();

  if (!app.server) {
    logger.warn({ roomId, eventType: event.type }, 'broadcast called before server is ready — dropping event');
    return;
  }

  const safeEvent = stripSessionId(event);
  const topic = `room:${roomId}`;
  app.server.publish(topic, JSON.stringify(safeEvent));
}

/**
 * Synchronous broadcast variant for use within WS handlers.
 *
 * Requires the caller to pass the server instance directly, which is always
 * available inside Elysia WS handlers. Avoids the async overhead of the lazy
 * import on the hot path.
 *
 * @param roomId - Target room
 * @param event - The ServerMessage to broadcast
 * @param server - Elysia WS server instance with a `publish` method
 */
export function broadcastSync(
  roomId: string,
  event: ServerMessage,
  server: { publish: (topic: string, data: string) => void },
): void {
  const safeEvent = stripSessionId(event);
  const topic = `room:${roomId}`;
  server.publish(topic, JSON.stringify(safeEvent));
}
