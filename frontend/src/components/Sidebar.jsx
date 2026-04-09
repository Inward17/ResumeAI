import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Briefcase, Calendar, Settings, HelpCircle,
  LogOut, Upload, Zap
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { C } from '../theme';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Overview',    Icon: LayoutDashboard },
  { id: 'jobs',       label: 'Postings',    Icon: Briefcase },
  { id: 'interviews', label: 'Interviews',  Icon: Calendar },
  { id: 'settings',   label: 'Settings',    Icon: Settings },
];

const Sidebar = ({ activeView, setActiveView }) => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) navigate('/login');
  };

  const aiQuota = 65;

  return (
    <div
      className="w-56 flex flex-col h-full shrink-0"
      style={{ background: C.sidebarBg, borderRight: '1px solid var(--color-border)' }}
    >
      {/* ── Logo ── */}
      <div className="px-5 py-5 border-b border-slate-200">
        <div className="flex items-center gap-2.5">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: C.primary }}
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke="white" strokeWidth="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-bold leading-tight" style={{ color: C.primary }}>ResumeAI</p>
            <p className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold">Precision Curator</p>
          </div>
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ id, label, Icon }) => {
          const isActive = activeView === id || (id === 'jobs' && activeView === 'pipeline');
          return (
            <button
              key={id}
              onClick={() => setActiveView(id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-150"
              style={isActive
                ? { background: C.primaryLight, color: C.primary }
                : { background: 'transparent', color: '#64748b' }
              }
            >
              <Icon
                className="h-4 w-4 shrink-0"
                style={{ color: isActive ? C.primary : '#94a3b8' }}
              />
              {label}
            </button>
          );
        })}
      </nav>

      {/* ── AI Quota + Upload CTA ──
      <div className="px-4 py-4 border-t border-slate-100">
        <div className="mb-3">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-widest" style={{ color: C.primary }}>AI Quota</span>
            <span className="text-[11px] font-semibold text-slate-400">{aiQuota}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${aiQuota}%`, background: 'var(--gradient-accent)' }}
            />
          </div>
        </div>
        <button
          onClick={() => setActiveView('jobs')}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-sm font-bold text-white transition-all hover:opacity-90"
          style={{ background: C.primary }}
        >
          <Upload className="h-4 w-4" />
          Upload Resumes
        </button>
      </div> */}

      {/* ── Bottom links ── */}
      <div className="px-3 py-3 border-t border-slate-100 space-y-0.5">
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-slate-100 transition-colors">
          <HelpCircle className="h-4 w-4 text-slate-400" />
          Help Center
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="h-4 w-4 text-slate-400" />
          Logout
        </button>
      </div>
    </div>
  );
};

export default Sidebar;