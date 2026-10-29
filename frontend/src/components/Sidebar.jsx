import React, { useEffect, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Briefcase, CalendarCheck, Settings, LogOut, Sun, Moon, Monitor } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../lib/theme';
import { getOrg } from '../services/orgService';
import { cn } from '../lib/utils';
import BrandMark from './BrandMark';
import { IconButton } from './common';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';

export const NAV_ITEMS = [
  { to: '/dashboard', label: 'Overview', Icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', Icon: Briefcase },
  { to: '/interviews', label: 'Interviews', Icon: CalendarCheck },
  { to: '/settings', label: 'Settings', Icon: Settings },
];

const THEME_NEXT = { system: 'light', light: 'dark', dark: 'system' };
const THEME_ICON = { system: Monitor, light: Sun, dark: Moon };

/** Cycles system → light → dark */
export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  const Icon = THEME_ICON[theme];
  return (
    <IconButton label={`Theme: ${theme} (switch to ${THEME_NEXT[theme]})`} onClick={() => setTheme(THEME_NEXT[theme])}>
      <Icon aria-hidden="true" />
    </IconButton>
  );
};

export const UserAvatar = ({ user, className }) => {
  const name = user?.displayName || user?.email || '?';
  return (
    <Avatar className={cn('h-8 w-8', className)}>
      {user?.photoURL && <AvatarImage src={user.photoURL} alt="" referrerPolicy="no-referrer" />}
      <AvatarFallback className="text-xs font-semibold">{name.charAt(0).toUpperCase()}</AvatarFallback>
    </Avatar>
  );
};

const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const displayName = user?.displayName || user?.email?.split('@')[0] || 'Account';
  const [orgName, setOrgName] = useState(null);

  // Refetch when the workspace is renamed or the user joins another one
  useEffect(() => {
    const load = () => getOrg().then((o) => setOrgName(o.name)).catch(() => {});
    load();
    window.addEventListener('resumeai:org', load);
    return () => window.removeEventListener('resumeai:org', load);
  }, [user?.uid]);

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) navigate('/login');
  };

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="hidden h-full w-60 shrink-0 flex-col border-r border-line bg-canvas md:flex">
        <div className="flex h-16 items-center px-5">
          <BrandMark />
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-2" aria-label="Main navigation">
          <p className="truncate px-3 pb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3" title={orgName || undefined}>{orgName || 'Workspace'}</p>
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => cn(
                'flex items-center gap-3 rounded-md border px-3 py-[7px] text-sm transition-colors',
                isActive ? 'border-line bg-surface font-medium text-ink shadow-[0_1px_2px_rgb(0_0_0/0.05)]' : 'border-transparent text-ink-2 hover:bg-subtle hover:text-ink',
              )}
            >
              <Icon className="h-4 w-4 shrink-0 opacity-80" strokeWidth={1.75} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Account */}
        <div className="border-t border-line p-3">
          <div className="flex items-center gap-1">
            <Link
              to="/profile"
              className="flex min-w-0 flex-1 items-center gap-2.5 rounded-md p-1.5 transition-colors hover:bg-subtle"
              aria-label="Your account"
            >
              <UserAvatar user={user} />
              <div className="min-w-0 leading-tight">
                <p className="truncate text-sm font-medium text-ink">{displayName}</p>
                {user?.email && <p className="truncate text-xs text-ink-3">{user.email}</p>}
              </div>
            </Link>
            <ThemeToggle />
            <IconButton label="Log out" onClick={handleLogout} className="hover:bg-danger-soft hover:text-danger">
              <LogOut aria-hidden="true" />
            </IconButton>
          </div>
        </div>
      </aside>

      {/* ── Mobile bottom navigation ── */}
      <nav
        className="relative z-40 flex w-full shrink-0 border-t border-line bg-canvas pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label="Main navigation"
      >
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex h-14 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors',
              isActive ? 'text-ink' : 'text-ink-3',
            )}
          >
            <Icon className="h-5 w-5" strokeWidth={1.75} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  );
};

export default Sidebar;
