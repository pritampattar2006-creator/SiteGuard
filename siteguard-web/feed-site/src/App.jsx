import { DetectDesk } from '../../shared/detect.jsx';
import { Shell } from '../../shared/ui.jsx';

// The camera station: no sign-in, one page. Everything it flags goes to the supervisor's review queue.
export default function App() {
  return (
    <Shell site="SiteGuard" tag="Detection desk" nav={[{ to: '/', label: 'Detect', icon: 'camera' }]}>
      <DetectDesk title="Detection desk" />
    </Shell>
  );
}
