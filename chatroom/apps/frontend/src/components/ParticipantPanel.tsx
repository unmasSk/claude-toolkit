import '../styles/components/Sidebar.css';
import { useAgentStore } from '../stores/agent-store';
import { ParticipantItem } from './ParticipantItem';

const SIDEBAR_ORDER = ['bilbo', 'ultron', 'cerberus', 'argus', 'moriarty', 'dante', 'yoda', 'house', 'alexandria', 'gitto'];

export function ParticipantPanel() {
  const agents = useAgentStore((s) => s.agents);
  const allAgents = Array.from(agents.values()).sort((a, b) => {
    const ai = SIDEBAR_ORDER.indexOf(a.agentName);
    const bi = SIDEBAR_ORDER.indexOf(b.agentName);
    const aIdx = ai === -1 ? SIDEBAR_ORDER.length : ai;
    const bIdx = bi === -1 ? SIDEBAR_ORDER.length : bi;
    return aIdx - bIdx;
  });

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
