import './styles/globals.css';
import { useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { Titlebar } from './components/Titlebar';
import { ParticipantPanel } from './components/ParticipantPanel';
import { ChatArea } from './components/ChatArea';
import { StatusBar } from './components/StatusBar';
import { useRoomStore } from './stores/room-store';

export function App() {
  const activeRoomId = useRoomStore((s) => s.activeRoomId);
  const loadRooms = useRoomStore((s) => s.loadRooms);

  // Load all rooms on mount
  useEffect(() => {
    void loadRooms();
  }, [loadRooms]);

  // Reconnect when active room changes
  useWebSocket(activeRoomId);

  return (
    <div className="chatroom">
      <Titlebar />
      <div className="main">
        <ParticipantPanel />
        <ChatArea />
      </div>
      <StatusBar />
    </div>
  );
}
