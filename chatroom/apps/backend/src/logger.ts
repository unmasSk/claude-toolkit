import pino from 'pino';

/**
 * Structured logger for the chatroom backend.
 * In development: pretty-prints to stderr via pino-pretty.
 * In production: outputs NDJSON to stderr (structured, parseable by log aggregators).
 *
 * Usage:
 *   import { createLogger } from './logger';
 *   const log = createLogger('agent-invoker');
 *   log.info({ agentName, roomId }, 'invocation started');
 *   log.warn({ stderrOutput }, 'stderr from subprocess');
 *   log.error({ err }, 'invocation failed');
 */

// SEC-BOOT-001: allowlist pattern — only known safe envs enable dev mode.
// Blacklist (`!== 'production'`) would treat unknown/missing NODE_ENV as dev,
// leaking pretty-printed logs in staging or misconfigured deployments.
const isDev = process.env.NODE_ENV === 'development' || process.env.NODE_ENV === 'test';

const rootLogger = pino(
  {
    level: process.env.LOG_LEVEL ?? 'debug',
    // Add timestamp to every log line
    timestamp: pino.stdTimeFunctions.isoTime,
    // In production, output as NDJSON
    // In development, pino-pretty handles formatting
  },
  isDev
    ? pino.transport({
        target: 'pino-pretty',
        options: {
          colorize: true,
          translateTime: 'SYS:HH:MM:ss.l',
          ignore: 'pid,hostname',
          messageFormat: '[{module}] {msg}',
        },
      })
    : pino.destination(2), // fd 2 = stderr
);

/**
 * Create a child logger scoped to a module.
 * The `module` binding appears in every log line.
 */
export function createLogger(module: string): pino.Logger {
  return rootLogger.child({ module });
}

export default rootLogger;
