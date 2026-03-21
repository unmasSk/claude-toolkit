/**
 * Unit tests for generateRoomName() — adjective-animal slug generator.
 */

import { describe, it, expect } from 'bun:test';
import { generateRoomName } from '../src/utils-name.js';

describe('generateRoomName', () => {
  it('returns a non-empty string', () => {
    expect(typeof generateRoomName()).toBe('string');
    expect(generateRoomName().length).toBeGreaterThan(0);
  });

  it('matches adjective-animal slug format', () => {
    // e.g. "powerful-salamander" — two lowercase words separated by a hyphen
    for (let i = 0; i < 50; i++) {
      expect(generateRoomName()).toMatch(/^[a-z]+-[a-z]+$/);
    }
  });

  it('contains exactly one hyphen', () => {
    for (let i = 0; i < 50; i++) {
      expect(generateRoomName().split('-').length).toBe(2);
    }
  });

  it('produces varied output — not always the same name', () => {
    const names = new Set(Array.from({ length: 100 }, () => generateRoomName()));
    // With 25×25=625 combinations, 100 draws should yield at minimum 5 distinct values
    expect(names.size).toBeGreaterThan(5);
  });

  it('both parts are non-empty', () => {
    for (let i = 0; i < 20; i++) {
      const [adj, animal] = generateRoomName().split('-');
      expect(adj!.length).toBeGreaterThan(0);
      expect(animal!.length).toBeGreaterThan(0);
    }
  });
});
