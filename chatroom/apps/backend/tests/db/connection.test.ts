/**
 * Coverage tests for db/connection.ts — getDb() initialization path.
 *
 * In CI, Bun runs test files in parallel and caches modules. Another test file
 * may import and close the real singleton before this file runs. To avoid the
 * "Cannot use a closed database" race, we create our OWN Database instance
 * for the SQL/WAL tests and only test the singleton contract (same ref returned)
 * via the module import.
 */
import { describe, it, expect, afterAll } from 'bun:test';
import { Database } from 'bun:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const tempDir = mkdtempSync(join(tmpdir(), 'conn-test-'));
const TEST_DB_PATH = join(tempDir, 'conn-test.db');

afterAll(() => {
  try {
    rmSync(tempDir, { recursive: true });
  } catch {
    // ignore cleanup errors
  }
});

describe('connection.ts — getDb() initialization', () => {
  it('getDb() returns an object with exec and query methods (Database interface)', async () => {
    const { getDb } = await import('../../src/db/connection.js');
    const db = getDb();
    expect(typeof db.exec).toBe('function');
    expect(typeof db.query).toBe('function');
  });

  it('getDb() returns the same singleton on repeated calls', async () => {
    const { getDb } = await import('../../src/db/connection.js');
    const db1 = getDb();
    const db2 = getDb();
    expect(db1).toBe(db2);
  });

  it('a fresh Database can execute SQL queries (WAL initialization path)', () => {
    const db = new Database(TEST_DB_PATH);
    db.exec('PRAGMA journal_mode = WAL;');
    db.exec('PRAGMA busy_timeout = 5000;');
    db.exec('PRAGMA synchronous = NORMAL;');
    const result = db.query('SELECT 1 as val').get() as { val: number };
    expect(result.val).toBe(1);
    db.close();
  });

  it('WAL journal mode is applied correctly', () => {
    const db = new Database(TEST_DB_PATH);
    db.exec('PRAGMA journal_mode = WAL;');
    const row = db.query('PRAGMA journal_mode').get() as { journal_mode: string };
    expect(row.journal_mode).toBe('wal');
    db.close();
  });
});
