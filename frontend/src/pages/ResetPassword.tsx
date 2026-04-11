import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Lock, Command, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';

const ResetPassword: React.FC = () => {
    const [searchParams] = useSearchParams();
    const token = searchParams.get('token');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [error, setError] = useState('');
    const [countdown, setCountdown] = useState(5);
    const navigate = useNavigate();

    useEffect(() => {
        if (!token) {
            setError('Invalid or missing reset token. Please request a new one.');
        }
    }, [token]);

    useEffect(() => {
        let timer: any;
        if (isSuccess && countdown > 0) {
            timer = setInterval(() => {
                setCountdown(prev => prev - 1);
            }, 1000);
        } else if (isSuccess && countdown === 0) {
            navigate('/login');
        }
        return () => clearInterval(timer);
    }, [isSuccess, countdown, navigate]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }
        if (password.length < 6) {
            setError('Password must be at least 6 characters');
            return;
        }
        
        setIsLoading(true);
        setError('');
        
        try {
            await whatsappApi.resetPassword(token!, password);
            setIsSuccess(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to reset password. Token may be expired.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen relative flex items-center justify-center bg-slate-50 dark:bg-slate-950 font-sans transition-colors duration-300">
            <div className="w-full max-w-[440px] px-6 z-20">
                <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xl">
                    
                    <div className="text-center mb-10">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-indigo-600 mb-6 shadow-lg">
                            <Command className="text-white" size={32} />
                        </div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
                            New Password
                        </h1>
                        <p className="text-slate-500 dark:text-slate-400 font-medium text-sm">
                            {isSuccess ? "Password updated!" : "Create a secure new password"}
                        </p>
                    </div>

                    {!isSuccess ? (
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 ml-1">New Password</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                                        <Lock size={18} />
                                    </div>
                                    <input 
                                        type="password" 
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg py-3 pl-12 pr-4 text-slate-900 dark:text-white font-medium placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
                                        placeholder="••••••••"
                                        required
                                        disabled={!token}
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 ml-1">Confirm Password</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                                        <Lock size={18} />
                                    </div>
                                    <input 
                                        type="password" 
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg py-3 pl-12 pr-4 text-slate-900 dark:text-white font-medium placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
                                        placeholder="••••••••"
                                        required
                                        disabled={!token}
                                    />
                                </div>
                            </div>

                            {error && (
                                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-medium text-center flex items-center gap-2 justify-center">
                                    <AlertCircle size={14} />
                                    <span>{error}</span>
                                </div>
                            )}

                            <button 
                                type="submit"
                                disabled={isLoading || !token}
                                className="w-full bg-indigo-600 py-3.5 rounded-lg text-white font-bold shadow-lg hover:bg-indigo-700 active:scale-95 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                            >
                                {isLoading ? <RefreshCw size={18} className="animate-spin" /> : "Update Password"}
                            </button>
                        </form>
                    ) : (
                        <div className="text-center space-y-6">
                            <div className="flex justify-center">
                                <div className="w-16 h-16 bg-emerald-50 dark:bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-500">
                                    <CheckCircle2 size={32} />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <p className="text-slate-600 dark:text-slate-400 text-sm font-medium">
                                    Your password has been successfully updated.
                                </p>
                                <p className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                                    Redirecting to login in {countdown} seconds...
                                </p>
                            </div>
                        </div>
                    )}

                    <div className="mt-8 pt-8 border-t border-slate-100 dark:border-slate-800 text-center">
                        <Link to="/login" className="text-slate-400 dark:text-slate-500 text-xs font-medium hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                            Return to sign in
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResetPassword;
