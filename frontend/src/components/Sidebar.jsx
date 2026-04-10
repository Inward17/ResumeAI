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
    <>
      {/* ── DESKTOP SIDEBAR (Original exactly as built) ── */}
      <div
        className="hidden md:flex w-56 flex-col h-full shrink-0"
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

      {/* ── MOBILE BOTTOM NAVIGATION (Responsive) ── */}
      <div className="md:hidden w-full flex flex-row h-16 shrink-0 bg-white border-t border-slate-200 z-40 relative">
        <nav className="flex-1 px-2 py-2 flex flex-row justify-around items-center">
          {NAV_ITEMS.map(({ id, label, Icon }) => {
            const isActive = activeView === id || (id === 'jobs' && activeView === 'pipeline');
            return (
              <button
                key={id}
                onClick={() => setActiveView(id)}
                className="flex-1 flex flex-col items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-semibold transition-all duration-150 bg-transparent"
                style={{ color: isActive ? C.primary : '#64748b' }}
              >
                <Icon
                  className="h-5 w-5 shrink-0 transition-transform duration-200"
                  style={{ color: isActive ? C.primary : '#94a3b8', transform: isActive ? 'translateY(-2px)' : 'none' }}
                />
                <span className={isActive ? 'font-bold' : 'font-medium'}>{label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </>
  );
};

export default Sidebar;