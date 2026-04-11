import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, ArrowLeft, Command, RefreshCw, CheckCircle2 } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';

const ForgotPassword: React.FC = () => {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSent, setIsSent] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');
        
        try {
            await whatsappApi.forgotPassword(email);
            setIsSent(true);
        } catch (err: any) {
            setError('Failed to process request. Please try again.');
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
                            Reset Password
                        </h1>
                        <p className="text-slate-500 dark:text-slate-400 font-medium text-sm">
                            {isSent ? "Check your email for instructions" : "Enter your email to receive a reset link"}
                        </p>
                    </div>

                    {!isSent ? (
                        <form onSubmit={handleSubmit} className="space-y-8">
                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 ml-1">Email Address</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                                        <Mail size={18} />
                                    </div>
                                    <input 
                                        type="email" 
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg py-3 pl-12 pr-4 text-slate-900 dark:text-white font-medium placeholder-slate-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all"
                                        placeholder="admin@example.com"
                                        required
                                    />
                                </div>
                            </div>

                            {error && (
                                <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-medium text-center">
                                    {error}
                                </div>
                            )}

                            <button 
                                type="submit"
                                disabled={isLoading}
                                className="w-full bg-indigo-600 py-3.5 rounded-lg text-white font-bold shadow-lg hover:bg-indigo-700 active:scale-95 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                            >
                                {isLoading ? <RefreshCw size={18} className="animate-spin" /> : "Send Reset Link"}
                            </button>
                        </form>
                    ) : (
                        <div className="text-center space-y-6">
                            <div className="flex justify-center">
                                <div className="w-16 h-16 bg-emerald-50 dark:bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-500">
                                    <CheckCircle2 size={32} />
                                </div>
                            </div>
                            <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">
                                A reset link has been sent to <span className="font-bold text-slate-900 dark:text-white">{email}</span> if it is registered in our system.
                            </p>
                            <div className="pt-4">
                                <Link 
                                    to="/login"
                                    className="w-full bg-slate-100 dark:bg-slate-800 py-3 rounded-lg text-slate-900 dark:text-white font-bold hover:bg-slate-200 dark:hover:bg-slate-700 transition-all flex items-center justify-center gap-2"
                                >
                                    <ArrowLeft size={16} />
                                    <span>Back to Login</span>
                                </Link>
                            </div>
                        </div>
                    )}

                    {!isSent && (
                        <div className="mt-8 pt-8 border-t border-slate-100 dark:border-slate-800 text-center">
                            <Link to="/login" className="text-indigo-600 dark:text-indigo-400 text-sm font-bold hover:underline inline-flex items-center gap-2">
                                <ArrowLeft size={14} />
                                Back to Login
                            </Link>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ForgotPassword;
