import { GitBranch, Cpu, Gauge } from 'lucide-react';
import { useWsStore } from '../stores/ws-store';

export function StatusBar() {
  const status = useWsStore((s) => s.status);

  const dotClass = status === 'connected'
    ? 'statusbar-dot connected'
    : status === 'connecting'
    ? 'statusbar-dot connecting'
    : 'statusbar-dot disconnected';

  const statusLabel = status === 'connected'
    ? 'connected'
    : status === 'connecting'
    ? 'connecting...'
    : 'disconnected';

  return (
    <div className="statusbar">
      <div className="statusbar-left">
        <div className="statusbar-item">
          <GitBranch size={12} />
          <span>main</span>
        </div>
        <div className="statusbar-item">
          <div className={dotClass} />
          <span>{statusLabel}</span>
        </div>
      </div>
      <div className="statusbar-right">
        <div className="statusbar-item" style={{ opacity: 0.5, fontSize: '0.7em', letterSpacing: '0.01em' }}>
          <span>@agent — invoke&nbsp;&nbsp;@everyone &lt;msg&gt; — directive&nbsp;&nbsp;@everyone stop — halt all</span>
        </div>
        <div className="statusbar-item">
          <Cpu size={12} />
          <span>sonnet 4.6</span>
        </div>
        <div className="statusbar-item">
          <Gauge size={12} />
          <span>ctx —%</span>
        </div>
      </div>
    </div>
  );
}
