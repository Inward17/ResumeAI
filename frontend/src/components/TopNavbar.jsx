import React, { useState } from 'react';
import { Search, Bell, HelpCircle, ChevronDown, Zap } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { C } from '../theme';

// Page title map — tells the navbar what to display per view
const PAGE_TITLES = {
  dashboard:  { title: 'Dashboard Overview',  sub: 'Recruitment Dept.' },
  jobs:       { title: 'Job Postings',         sub: 'Manage Talent Pipeline' },
  pipeline:   { title: 'Candidate Pipeline',   sub: 'AI-Curated Analysis' },
  interviews: { title: 'Interview Pipeline',   sub: 'Shortlisted Candidates' },
  profile:    { title: 'Account Settings',     sub: 'Profile & Preferences' },
  settings:   { title: 'Workspace Settings',   sub: 'Configuration' },
};

const TopNavbar = ({ activeView, setActiveView }) => {
  const { user } = useAuth();
  const [searchVal, setSearchVal] = useState('');
  const [notifOpen, setNotifOpen] = useState(false);

  const displayName = user?.displayName || user?.email?.split('@')[0] || 'User';
  const userPhoto   = user?.photoURL;
  const initials    = displayName.charAt(0).toUpperCase();
  const page        = PAGE_TITLES[activeView] || PAGE_TITLES.dashboard;

  return (
    <div
      className="h-14 flex items-center justify-between px-6 shrink-0"
      style={{
        background: 'white',
        borderBottom: `1px solid ${C.border}`,
        position: 'sticky',
        top: 0,
        zIndex: 40,
      }}
    >
      {/* Left: Page title + sub-label */}
      <div className="flex items-center gap-3">
        {/* MOBILE LOGO */}
        <div className="flex md:hidden h-8 w-8 rounded-lg items-center justify-center shrink-0" style={{ background: C.primary }}>
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke="white" strokeWidth="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>

        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 leading-none mb-0.5">
            {page.title}
          </p>
          <button
            className="flex items-center gap-1 text-sm font-bold text-slate-900 hover:text-indigo-700 transition-colors"
          >
            {page.sub}
            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          </button>
        </div>
      </div>

      {/* Right: search + actions */}
      <div className="flex items-center md:gap-2 gap-1">
        {/* Search bar */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <input
            value={searchVal}
            onChange={e => setSearchVal(e.target.value)}
            placeholder="Search insights..."
            className="pl-8 pr-4 py-1.5 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-700 outline-none focus:ring-2 focus:ring-indigo-200 w-44 focus:w-56 transition-all duration-200"
          />
        </div>

        {/* Notification bell */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(o => !o)}
            className="relative h-9 w-9 rounded-xl flex items-center justify-center hover:bg-slate-100 transition-colors"
          >
            <Bell className="h-4.5 w-4.5 text-slate-500" />
            {/* Unread dot */}
            <span
              className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full border-2 border-white"
              style={{ background: C.cyan }}
            />
          </button>

          {/* Dropdown stub */}
          {notifOpen && (
            <div className="absolute right-0 top-11 w-72 bg-white rounded-2xl border border-slate-200 shadow-xl z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <p className="text-sm font-bold text-slate-900">Notifications</p>
                <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: C.accent }}>Mark all read</span>
              </div>
              <div className="px-4 py-3 flex items-start gap-3">
                <Zap className="h-4 w-4 shrink-0 mt-0.5" style={{ color: C.cyan }} />
                <div>
                  <p className="text-sm font-semibold text-slate-900">AI scans complete</p>
                  <p className="text-xs text-slate-400 mt-0.5">3 new candidates scored for Full Stack Developer</p>
                  <p className="text-[10px] text-slate-300 mt-1">2 min ago</p>
                </div>
              </div>
              <div className="px-4 py-3 border-t border-slate-100 text-center">
                <button className="text-xs font-semibold" style={{ color: C.accent }}>View all notifications</button>
              </div>
            </div>
          )}
        </div>

        {/* Help */}
        <button className="hidden md:flex h-9 w-9 rounded-xl items-center justify-center hover:bg-slate-100 transition-colors">
          <HelpCircle className="h-4.5 w-4.5 text-slate-500" />
        </button>

        {/* User avatar → goes to profile */}
        <button
          onClick={() => setActiveView('profile')}
          className="h-8 w-8 rounded-full overflow-hidden border-2 hover:ring-2 transition-all"
          style={{ borderColor: C.primary }}
        >
          <Avatar className="h-full w-full">
            {userPhoto && <AvatarImage src={userPhoto} alt={displayName} />}
            <AvatarFallback
              className="text-xs font-bold text-white"
              style={{ background: C.primary }}
            >
              {initials}
            </AvatarFallback>
          </Avatar>
        </button>
      </div>
    </div>
  );
};

export default TopNavbar;
