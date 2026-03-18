import { create } from 'zustand';
import type { Message } from '@agent-chatroom/shared';

interface ChatState {
  messages: Message[];
  isLoadingHistory: boolean;
  hasMoreHistory: boolean;

  appendMessage: (msg: Message) => void;
  appendMessages: (msgs: Message[]) => void;
  prependHistory: (msgs: Message[], hasMore: boolean) => void;
  clearMessages: () => void;
  setLoadingHistory: (loading: boolean) => void;
}

// Module-level dedup set — survives across Zustand set() race conditions
// that occur when 2 StrictMode WS connections deliver the same message
const seenIds = new Set<string>();

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoadingHistory: false,
  hasMoreHistory: false,

  appendMessage: (msg) => {
    if (seenIds.has(msg.id)) return;
    seenIds.add(msg.id);
    set((state) => ({ messages: [...state.messages, msg] }));
  },

  appendMessages: (msgs) => {
    const fresh = msgs.filter((m) => {
      if (seenIds.has(m.id)) return false;
      seenIds.add(m.id);
      return true;
    });
    if (fresh.length === 0) return;
    set((state) => ({ messages: [...state.messages, ...fresh] }));
  },

  prependHistory: (msgs, hasMore) => {
    const fresh = msgs.filter((m) => {
      if (seenIds.has(m.id)) return false;
      seenIds.add(m.id);
      return true;
    });
    set((state) => ({
      messages: [...fresh, ...state.messages],
      hasMoreHistory: hasMore,
      isLoadingHistory: false,
    }));
  },

  clearMessages: () => {
    seenIds.clear();
    set({ messages: [], hasMoreHistory: false });
  },

  setLoadingHistory: (loading) =>
    set({ isLoadingHistory: loading }),
}));
