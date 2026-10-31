import { Navigate, Route, Routes } from 'react-router-dom';
import { api } from '../../shared/api.js';
import { Login, useAuth } from '../../shared/auth.jsx';
import { Notifications, Shell, useLoad } from '../../shared/ui.jsx';
import { Cases, Dashboard, Penalties, Queue } from './pages.jsx';
import { EmployeeDetail, Employees, FacesPage } from './people.jsx';
import { AccuracyPage } from '../../shared/about.jsx';
import { LiveFeed } from './feed.jsx';
import { Accidents, AccidentWatcher, LogPage, Report, Rules } from './safety.jsx';
import { SetupGuide } from './safety.jsx';
import { Sectors } from './sectors.jsx';

export default function App() {
  const { user, logout, autoOn } = useAuth();
  const counts = useLoad(() => (user ? api('/api/stats') : Promise.resolve(null)), [user?.id], 10000);
  if (!user && window.location.pathname === '/about') return <div className="page" style={{ maxWidth: 900, margin: '0 auto' }}><AccuracyPage standalone /></div>;
  if (!user) return <Login title="Run site safety from one panel." subtitle="Supervisor panel" points={['Review every catch with its picture', 'Confirm, dismiss, or send for a penalty decision', 'See your team, their record and their pay']} demo={['S001', '123456789']} demoNote="Dummy accounts: the supervisors S001, S002 and S003 sign in with the same password," signup />;
  const s = counts.data || {};
  return (
    <Shell site="SiteGuard" tag={user.isAdmin ? "Head supervisor · all sectors" : `Supervisor · ${user.sectorName || "your sector"}`} user={user} onLogout={autoOn ? undefined : logout}
      nav={[
        { to: '/', label: 'Overview', icon: 'dashboard' },
        { to: '/feed', label: 'Live feed', icon: 'camera' },
        { to: '/queue', label: 'Review queue', icon: 'inbox', count: s.pending },
        { to: '/cases', label: 'All cases', icon: 'folder' },
        { to: '/log', label: 'Log', icon: 'clock' },
        { to: '/accidents', label: 'Accident reports', icon: 'alert' },
        { to: '/penalties', label: 'Penalties', icon: 'shield', count: s.penaltiesWaiting },
        { to: '/rules', label: 'Rules and penalties', icon: 'shield' },
        { to: '/report', label: 'Monthly report', icon: 'chart' },
        { to: '/employees', label: 'Employees', icon: 'users' },
        { to: '/sectors', label: user.isAdmin ? 'Sectors and supervisors' : 'My sector', icon: 'hardhat' },
        { to: '/faces', label: 'Face matching', icon: 'face' },
        { to: '/notifications', label: 'Notifications', icon: 'bell' },
        { to: '/about', label: 'About accuracy', icon: 'dashboard' },
      ]}>
      <AccidentWatcher />
      <SetupGuide />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/feed" element={<LiveFeed />} />
        <Route path="/queue" element={<Queue onChanged={counts.reload} />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/penalties" element={<Penalties onChanged={counts.reload} />} />
        <Route path="/employees" element={<Employees />} />
        <Route path="/employees/:id" element={<EmployeeDetail />} />
        <Route path="/sectors" element={<Sectors />} />
        <Route path="/log" element={<LogPage />} />
        <Route path="/accidents" element={<Accidents />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/report" element={<Report />} />
        <Route path="/about" element={<AccuracyPage />} />
        <Route path="/faces" element={<FacesPage />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
