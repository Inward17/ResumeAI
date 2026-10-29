import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import BrandMark from './BrandMark';
import { ThemeToggle, UserAvatar } from './Sidebar';

/** Phone-only header; on desktop the sidebar carries brand, account and theme */
const TopNavbar = () => {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between border-b border-line bg-canvas/90 px-4 backdrop-blur md:hidden">
      <Link to="/dashboard" aria-label="ResumeAI home"><BrandMark /></Link>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <Link to="/profile" className="rounded-full p-1" aria-label="Your account">
          <UserAvatar user={user} />
        </Link>
      </div>
    </header>
  );
};

export default TopNavbar;
