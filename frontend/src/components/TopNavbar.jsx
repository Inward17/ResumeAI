import React from 'react';
import { Link, matchPath, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import BrandMark from './BrandMark';

// First match wins
const PAGE_TITLES = [
  ['/dashboard', 'Overview'],
  ['/jobs/:jobId/candidates/:candidateId/interview', 'Interview'],
  ['/jobs/:jobId', 'Candidate pipeline'],
  ['/jobs', 'Job postings'],
  ['/interviews', 'Interviews'],
  ['/settings', 'Settings'],
  ['/profile', 'Your account'],
];

const TopNavbar = () => {
  const { user } = useAuth();
  const { pathname } = useLocation();

  const displayName = user?.displayName || user?.email?.split('@')[0] || 'Account';
  const title = PAGE_TITLES.find(([pattern]) => matchPath(pattern, pathname))?.[1] || '';

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <BrandMark compact className="md:hidden" />
        <p className="truncate text-sm font-bold text-slate-900">{title}</p>
      </div>

      <Link
        to="/profile"
        className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-1 transition-colors hover:bg-slate-100 md:pr-3"
        aria-label="Your account"
      >
        <Avatar className="h-8 w-8 border-2 border-brand">
          {user?.photoURL && <AvatarImage src={user.photoURL} alt="" />}
          <AvatarFallback className="bg-brand text-xs font-bold text-white">
            {displayName.charAt(0).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <span className="hidden max-w-[12rem] truncate text-sm font-semibold text-slate-700 md:inline">{displayName}</span>
      </Link>
    </header>
  );
};

export default TopNavbar;
