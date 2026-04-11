import React from 'react';
import { NavLink, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { LogOut, LayoutDashboard, Users, Send, ClipboardList, MessageSquare, Settings, Command } from 'lucide-react';
import GlobalStatus from './GlobalStatus';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  
  const userRole = localStorage.getItem('role') || 'agent';

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/contacts', label: 'Contacts', icon: Users },
    { to: '/templates', label: 'Templates', icon: ClipboardList },
    { to: '/campaigns', label: 'Campaigns', icon: Send },
    { to: '/chat', label: 'Live Chat', icon: MessageSquare },
  ];

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors duration-300">
      
      {/* Sidebar - Classic */}
      <aside className="w-64 h-full border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col z-40">
        <div className="p-6 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800/50 mb-4 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-8 h-8 bg-indigo-600 rounded flex items-center justify-center shadow-sm">
            <Command className="text-white" size={20} />
          </div>
          <span className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">Adcom</span>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
                ${isActive 
                  ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
              `}
            >
              <item.icon size={18} strokeWidth={2} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-100 dark:border-slate-800 mt-auto space-y-1">
          {userRole === 'admin' && (
            <NavLink
              to="/settings"
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
                ${isActive 
                  ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
              `}
            >
              <Settings size={18} strokeWidth={2} />
              Settings
            </NavLink>
          )}
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 hover:text-rose-600 transition-all"
          >
            <LogOut size={18} strokeWidth={2} />
            Logout
          </button>
          
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-50 dark:border-slate-800/50 px-2">
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Theme Mode</span>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Main Framework */}
      <main className="flex-1 overflow-auto bg-slate-50 dark:bg-slate-950 h-screen scrollbar-hide">
        <div className="max-w-[1400px] mx-auto p-10">
          {children || <Outlet />}
        </div>
      </main>

      {/* Persistent Live Stats & Health */}
      <GlobalStatus />
    </div>
  );
};

export default Layout;
