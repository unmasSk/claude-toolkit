/**
 * Unit tests for useRoomStore — room management Zustand store.
 *
 * Fetch is mocked globally. Each test resets store state via act().
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import { useRoomStore } from '../../stores/room-store';
import type { Room } from '@agent-chatroom/shared';

function makeRoom(id: string, name = id): Room {
  return { id, name, topic: '', createdAt: new Date().toISOString() };
}

function resetStore() {
  useRoomStore.setState({ rooms: [], activeRoomId: 'default', pendingDeleteId: null });
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetStore();
});

// ---------------------------------------------------------------------------
// loadRooms
// ---------------------------------------------------------------------------

describe('loadRooms', () => {
  it('populates rooms from API response', async () => {
    const mockRooms = [makeRoom('default'), makeRoom('swift-falcon')];
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockRooms), { status: 200 }),
    );

    await act(() => useRoomStore.getState().loadRooms());

    expect(useRoomStore.getState().rooms).toHaveLength(2);
    expect(useRoomStore.getState().rooms[1]!.id).toBe('swift-falcon');
  });

  it('leaves rooms unchanged when fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('network'));

    await act(() => useRoomStore.getState().loadRooms());

    expect(useRoomStore.getState().rooms).toHaveLength(0);
  });

  it('leaves rooms unchanged on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('Internal Server Error', { status: 500 }),
    );

    await act(() => useRoomStore.getState().loadRooms());

    expect(useRoomStore.getState().rooms).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// createRoom
// ---------------------------------------------------------------------------

describe('createRoom', () => {
  it('adds the new room to the list and activates it', async () => {
    const newRoom = makeRoom('brave-wolf');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ room: newRoom }), { status: 201 }),
    );

    const result = await act(() => useRoomStore.getState().createRoom());

    expect(result).toEqual(newRoom);
    expect(useRoomStore.getState().rooms).toContainEqual(newRoom);
    expect(useRoomStore.getState().activeRoomId).toBe('brave-wolf');
  });

  it('returns null and does not mutate state on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('network'));

    const result = await act(() => useRoomStore.getState().createRoom());

    expect(result).toBeNull();
    expect(useRoomStore.getState().rooms).toHaveLength(0);
    expect(useRoomStore.getState().activeRoomId).toBe('default');
  });

  it('returns null on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('error', { status: 500 }),
    );

    const result = await act(() => useRoomStore.getState().createRoom());

    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// setActiveRoomId
// ---------------------------------------------------------------------------

describe('setActiveRoomId', () => {
  it('changes active room', () => {
    useRoomStore.setState({ activeRoomId: 'default' });
    useRoomStore.getState().setActiveRoomId('brave-wolf');
    expect(useRoomStore.getState().activeRoomId).toBe('brave-wolf');
  });

  it('clears pendingDeleteId when switching rooms', () => {
    useRoomStore.setState({ pendingDeleteId: 'some-room' });
    useRoomStore.getState().setActiveRoomId('brave-wolf');
    expect(useRoomStore.getState().pendingDeleteId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// markForDelete / cancelDelete
// ---------------------------------------------------------------------------

describe('markForDelete', () => {
  it('sets pendingDeleteId', () => {
    useRoomStore.getState().markForDelete('swift-falcon');
    expect(useRoomStore.getState().pendingDeleteId).toBe('swift-falcon');
  });

  it('does nothing for the default room', () => {
    useRoomStore.getState().markForDelete('default');
    expect(useRoomStore.getState().pendingDeleteId).toBeNull();
  });
});

describe('cancelDelete', () => {
  it('clears pendingDeleteId', () => {
    useRoomStore.setState({ pendingDeleteId: 'swift-falcon' });
    useRoomStore.getState().cancelDelete();
    expect(useRoomStore.getState().pendingDeleteId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// confirmDelete
// ---------------------------------------------------------------------------

describe('confirmDelete', () => {
  it('removes the room from the list on success', async () => {
    const room = makeRoom('silent-hawk');
    useRoomStore.setState({ rooms: [makeRoom('default'), room], activeRoomId: 'default' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ deleted: 'silent-hawk' }), { status: 200 }),
    );

    await act(() => useRoomStore.getState().confirmDelete('silent-hawk'));

    expect(useRoomStore.getState().rooms.find((r) => r.id === 'silent-hawk')).toBeUndefined();
    expect(useRoomStore.getState().pendingDeleteId).toBeNull();
  });

  it('falls back to default when active room is deleted', async () => {
    const room = makeRoom('silent-hawk');
    useRoomStore.setState({ rooms: [makeRoom('default'), room], activeRoomId: 'silent-hawk' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ deleted: 'silent-hawk' }), { status: 200 }),
    );

    await act(() => useRoomStore.getState().confirmDelete('silent-hawk'));

    expect(useRoomStore.getState().activeRoomId).toBe('default');
  });

  it('keeps active room if a different room is deleted', async () => {
    const roomA = makeRoom('room-a');
    const roomB = makeRoom('room-b');
    useRoomStore.setState({ rooms: [makeRoom('default'), roomA, roomB], activeRoomId: 'room-a' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ deleted: 'room-b' }), { status: 200 }),
    );

    await act(() => useRoomStore.getState().confirmDelete('room-b'));

    expect(useRoomStore.getState().activeRoomId).toBe('room-a');
  });

  it('does nothing for the default room', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    await act(() => useRoomStore.getState().confirmDelete('default'));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('clears pendingDeleteId even when fetch fails', async () => {
    useRoomStore.setState({ pendingDeleteId: 'swift-falcon' });
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('network'));

    await act(() => useRoomStore.getState().confirmDelete('swift-falcon'));

    expect(useRoomStore.getState().pendingDeleteId).toBeNull();
  });

  it('does not remove room on non-ok response', async () => {
    const room = makeRoom('silent-hawk');
    useRoomStore.setState({ rooms: [makeRoom('default'), room] });
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('error', { status: 500 }),
    );

    await act(() => useRoomStore.getState().confirmDelete('silent-hawk'));

    expect(useRoomStore.getState().rooms.find((r) => r.id === 'silent-hawk')).toBeDefined();
  });
});
