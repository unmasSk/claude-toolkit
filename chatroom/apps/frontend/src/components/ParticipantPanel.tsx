import '../styles/components/Sidebar.css';
import { useAgentStore } from '../stores/agent-store';
import { ParticipantItem } from './ParticipantItem';

export function ParticipantPanel() {
  const agents = useAgentStore((s) => s.agents);
  const allAgents = Array.from(agents.values());

  return (
    <aside className="sidebar">
      <div className="agent-list">
        {allAgents.map((agent) => (
          <ParticipantItem key={agent.agentName} agent={agent} />
        ))}
      </div>
    </aside>
  );
}
