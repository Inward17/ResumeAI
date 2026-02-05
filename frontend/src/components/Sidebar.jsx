import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, Briefcase, Settings, LogOut, User, ChevronDown } from 'lucide-react';
import { Button } from './ui/button';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';
import { useAuth } from '../hooks/useAuth';

const Sidebar = ({ activeView, setActiveView }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home },
    { id: 'jobs', label: 'Job Postings', icon: Briefcase },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) {
      navigate('/login');
    }
  };

  // Get display name or email
  const displayName = user?.displayName || user?.email?.split('@')[0] || 'User';
  const userEmail = user?.email || '';
  const userPhoto = user?.photoURL;

  return (
    <div className="w-64 bg-slate-900 text-white flex flex-col h-full">
      {/* Logo */}
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-2xl font-bold text-blue-400">TrueView</h1>
        <p className="text-sm text-slate-400 mt-1">AI Resume Screening</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <Button
                  variant={activeView === item.id ? "secondary" : "ghost"}
                  className={`w-full justify-start text-left transition-all duration-200 ${activeView === item.id
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800'
                    }`}
                  onClick={() => setActiveView(item.id)}
                >
                  <Icon className="mr-3 h-5 w-5" />
                  {item.label}
                </Button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User Profile - Now with real user data */}
      <div className="p-4 border-t border-slate-700">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-between text-left p-3 hover:bg-slate-800 transition-colors duration-200"
            >
              <div className="flex items-center space-x-3">
                <Avatar className="h-10 w-10">
                  {userPhoto && <AvatarImage src={userPhoto} alt={displayName} />}
                  <AvatarFallback className="bg-blue-600 text-white">
                    {displayName.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 text-left overflow-hidden">
                  <p className="text-sm font-medium text-white truncate">{displayName}</p>
                  <p className="text-xs text-slate-400 truncate">{userEmail}</p>
                </div>
              </div>
              <ChevronDown className="h-4 w-4 text-slate-400 flex-shrink-0" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuItem
              onClick={() => setActiveView('profile')}
              className="flex items-center space-x-2 cursor-pointer"
            >
              <User className="h-4 w-4" />
              <span>My Profile</span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleLogout}
              className="flex items-center space-x-2 cursor-pointer text-red-600 focus:text-red-600"
            >
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

export default Sidebar;