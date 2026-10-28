import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Briefcase, Calendar, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { cn } from '../lib/utils';
import BrandMark from './BrandMark';

export const NAV_ITEMS = [
  { to: '/dashboard', label: 'Overview', Icon: LayoutDashboard },
  { to: '/jobs', label: 'Postings', Icon: Briefcase },
  { to: '/interviews', label: 'Interviews', Icon: Calendar },
  { to: '/settings', label: 'Settings', Icon: Settings },
];

const Sidebar = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) navigate('/login');
  };

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="hidden h-full w-56 shrink-0 flex-col border-r border-slate-200 bg-slate-50 md:flex" aria-label="Main navigation">
        <div className="border-b border-slate-200 px-5 py-5">
          <BrandMark />
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
                isActive ? 'bg-brand-light text-brand' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
              )}
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn('h-4 w-4 shrink-0', isActive ? 'text-brand' : 'text-slate-500')} aria-hidden="true" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 px-3 py-3">
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-red-50 hover:text-red-700"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out
          </button>
        </div>
      </aside>

      {/* ── Mobile bottom navigation ── */}
      <nav className="relative z-40 flex h-16 w-full shrink-0 border-t border-slate-200 bg-white md:hidden" aria-label="Main navigation">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex flex-1 flex-col items-center justify-center gap-1 text-[11px] font-semibold transition-colors',
              isActive ? 'text-brand' : 'text-slate-500',
            )}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  );
};

export default Sidebar;
