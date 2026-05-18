import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { LogIn, User, Lock, Command, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { ThemeToggle } from '../components/ThemeToggle';
import { whatsappApi } from '../services/whatsappApi';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsLoading(true);
    setError('');
    
    try {
      // For development, if username is 'admin', password 'admin123'
      const data = await whatsappApi.login(username, password);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('role', data.role);
      
      if (data.role === 'super_admin' || data.role === 'superadmin') {
        navigate('/admin/dashboard');
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      console.error("Login Error Details:", err);
      const status = err?.response?.status;
      if (!err?.response) {
        setError('Network error. Please check your connection and try again.');
      } else if (status === 401) {
        setError('Invalid username or password. Please try again.');
      } else if (status === 500) {
        setError('Server error. Please contact support or try again later.');
      } else {
        setError(err?.response?.data?.detail || 'Login failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center bg-slate-50 dark:bg-slate-950 font-sans selection:bg-indigo-500/30 transition-colors duration-300">
      
      {/* Auth Interface */}
      <div className="w-full max-w-[440px] px-6 z-20">
        <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xl">
          
          {/* Header */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-indigo-600 mb-6 shadow-lg">
              <Command className="text-white" size={32} />
            </div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
              Adcom
            </h1>
            <p className="text-slate-500 dark:text-slate-400 font-medium text-sm">
              Sign in to your account
            </p>
          </div>

          <div className="space-y-8">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 ml-1">Username</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                  <User size={18} />
                </div>
                <input 
                  type="text" 
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin(e as any)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg py-3 pl-12 pr-4 text-slate-900 dark:text-white font-medium placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
                  placeholder="Enter username"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 ml-1">Password</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                  <Lock size={18} />
                </div>
                <input 
                  type={showPassword ? "text" : "password"} 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin(e as any)}
                  className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg py-3 pl-12 pr-12 text-slate-900 dark:text-white font-medium placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
                  placeholder="Enter password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-indigo-500 transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              <div className="flex justify-end">
                <Link 
                  to="/forgot-password" 
                  className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline transition-all"
                >
                  Forgot password?
                </Link>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-medium text-center">
                {error}
              </div>
            )}

            <button 
              type="button"
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full bg-indigo-600 py-3.5 rounded-lg text-white font-bold shadow-lg hover:bg-indigo-700 active:scale-95 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
            >
              {isLoading ? (
                <RefreshCw size={18} className="animate-spin" />
              ) : (
                <>
                  <span>Sign In</span>
                  <LogIn size={18} />
                </>
              )}
            </button>
          </div>
        </div>
        
        <div className="mt-8 flex items-center justify-center gap-6 text-xs font-medium text-slate-500">
           <ThemeToggle />
           <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-slate-700" />
           <span>Version 2.4.0</span>
        </div>
      </div>
    </div>
  );
};

export default Login;
