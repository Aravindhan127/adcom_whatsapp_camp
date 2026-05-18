import React from 'react';
import { NavLink, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { LogOut, LayoutDashboard, Users, Send, ClipboardList, MessageSquare, Settings, Command, Shield, Globe } from 'lucide-react';
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

  const queryParams = new URLSearchParams(location.search);
  const impersonateOrgId = queryParams.get('orgId');
  const isSuperAdmin = userRole === 'super_admin' || userRole === 'superadmin';
  const showOrgLinks = !isSuperAdmin || impersonateOrgId;

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
          {isSuperAdmin && !impersonateOrgId && (
            <div className="mb-4 space-y-1">
              <span className="px-3 text-[10px] font-black text-slate-400 uppercase tracking-[0.25em] block mb-2 opacity-70">Platform Control</span>
              <NavLink
                to="/admin/dashboard"
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all
                  ${isActive 
                    ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
                `}
              >
                <LayoutDashboard size={18} strokeWidth={2.5} />
                Global Overview
              </NavLink>
              <NavLink
                to="/admin/organizations"
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all
                  ${isActive 
                    ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
                `}
              >
                <Globe size={18} strokeWidth={2.5} />
                Organizations
              </NavLink>
              <NavLink
                to="/admin/users"
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all
                  ${isActive 
                    ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
                `}
              >
                <Users size={18} strokeWidth={2.5} />
                User Access
              </NavLink>
              <div className="pt-2 border-b border-slate-100 dark:border-slate-800/50 mb-2" />
            </div>
          )}

          {showOrgLinks && navItems.map((item) => {
            const toWithOrg = impersonateOrgId ? `${item.to}?orgId=${impersonateOrgId}` : item.to;
            return (
              <NavLink
                key={item.to}
                to={toWithOrg}
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
            );
          })}
        </nav>

        <div className="p-4 mt-auto space-y-1">
          {(userRole === 'admin' || isSuperAdmin) && (
            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-1">
              <span className="px-3 text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2">System Control</span>
              <NavLink
                to="/audit"
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
                  ${isActive 
                    ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400' 
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'}
                `}
              >
                <Shield size={18} strokeWidth={2} />
                Audit Logs
              </NavLink>
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
            </div>
          )}


          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold text-slate-500 dark:text-slate-400 hover:bg-rose-50 dark:hover:bg-rose-500/5 hover:text-rose-600 transition-all group mt-6"
          >
            <LogOut size={18} strokeWidth={2.5} className="group-hover:-translate-x-0.5 transition-transform" />
            Logout
          </button>
          
          <div className="flex items-center justify-between pt-10 mt-10 border-t border-slate-100 dark:border-slate-800/60 px-2 pb-2">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.25em] opacity-70">Theme Mode</span>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Main Framework */}
      <main className="flex-1 overflow-auto bg-slate-50 dark:bg-slate-950 h-screen scrollbar-hide flex flex-col">
        {isSuperAdmin && impersonateOrgId && (
          <div className="bg-amber-500 px-8 py-3 flex items-center justify-between text-white shadow-lg animate-in slide-in-from-top duration-500 z-50">
            <div className="flex items-center gap-3">
              <Shield size={18} />
              <span className="text-sm font-bold tracking-tight">
                VIEWING ORGANIZATION MODE: <span className="uppercase underline decoration-2 underline-offset-4 ml-1">Impersonating {impersonateOrgId}</span>
              </span>
            </div>
            <button 
              onClick={() => navigate('/admin/dashboard')}
              className="bg-white/20 hover:bg-white/30 px-4 py-1.5 rounded-lg text-xs font-black uppercase tracking-widest transition-all"
            >
              Exit View
            </button>
          </div>
        )}
        <div className="p-8 flex-1">
          {children || <Outlet />}
        </div>
      </main>

      {/* Persistent Live Stats & Health */}
      <GlobalStatus />
    </div>
  );
};

export default Layout;
