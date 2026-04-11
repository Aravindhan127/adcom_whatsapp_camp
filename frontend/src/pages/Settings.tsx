import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  CreditCard, 
  TrendingUp, 
  Shield, 
  RefreshCw,
  Save,
  Zap,
  ChevronRight
} from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';

const Settings: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [settings, setSettings] = useState({
        meta_balance_inr: 0,
        meta_balance_usd: 0,
        marketing_rate_inr: 0.82,
        utility_rate_inr: 0.35,
        authentication_rate_inr: 0.35,
        exchange_rate: 84.0
    });

    const fetchSettings = async () => {
        setLoading(true);
        try {
            const stats = await whatsappApi.getStats();
            setSettings(prev => ({
                ...prev,
                meta_balance_inr: stats.balance.estimated_inr,
                meta_balance_usd: stats.balance.estimated_usd,
            }));
        } catch (error) {
            console.error('Error fetching settings:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSettings();
    }, []);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await new Promise(resolve => setTimeout(resolve, 800));
            alert('Settings updated successfully');
        } catch (error) {
            alert('Failed to update settings');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-32 gap-4">
                <RefreshCw className="text-indigo-600 animate-spin" size={40} />
                <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">Loading Settings</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 font-sans">
            <PageHeader 
                title="Settings" 
                description="Configure global application preferences and billing" 
            />

            <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <div className="lg:col-span-8 space-y-8">
                    {/* Billing Section */}
                    <section className="bg-white dark:bg-slate-900 p-8 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                        <div className="flex items-center gap-3 mb-8">
                            <div className="w-10 h-10 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg flex items-center justify-center text-indigo-600 shadow-sm">
                                <CreditCard size={20} />
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Billing & Balance</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider pl-1">Balance (INR)</label>
                                <div className="relative group">
                                    <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold text-slate-400 text-lg">₹</span>
                                    <input 
                                        type="number"
                                        value={settings.meta_balance_inr}
                                        onChange={(e) => setSettings({...settings, meta_balance_inr: parseFloat(e.target.value)})}
                                        className="w-full pl-10 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xl font-bold text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-indigo-500/20 tabular-nums transition-all"
                                    />
                                </div>
                                <p className="text-[10px] text-slate-400 font-medium pl-1 italic">Real-time estimation from Meta API</p>
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider pl-1">Balance (USD)</label>
                                <div className="relative group">
                                    <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold text-slate-400 text-lg">$</span>
                                    <input 
                                        type="number"
                                        value={settings.meta_balance_usd}
                                        onChange={(e) => setSettings({...settings, meta_balance_usd: parseFloat(e.target.value)})}
                                        className="w-full pl-10 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xl font-bold text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-indigo-500/20 tabular-nums transition-all"
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Pricing Grid */}
                    <section className="bg-white dark:bg-slate-900 p-8 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                        <div className="flex items-center gap-3 mb-8">
                            <div className="w-10 h-10 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg flex items-center justify-center text-indigo-600 shadow-sm">
                                <TrendingUp size={20} />
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Conversation Pricing</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <PriceInput label="Marketing" value={settings.marketing_rate_inr} onChange={(v: any) => setSettings({...settings, marketing_rate_inr: v})} />
                            <PriceInput label="Utility" value={settings.utility_rate_inr} onChange={(v: any) => setSettings({...settings, utility_rate_inr: v})} />
                            <PriceInput label="Authentication" value={settings.authentication_rate_inr} onChange={(v: any) => setSettings({...settings, authentication_rate_inr: v})} />
                        </div>
                    </section>
                </div>

                <div className="lg:col-span-4 space-y-6">
                    <section className="bg-slate-900 p-8 rounded-xl shadow-lg border border-slate-800">
                        <div className="flex items-center gap-3 mb-6">
                            <Shield className="text-indigo-400" size={20} />
                            <h3 className="text-lg font-bold text-white">System Security</h3>
                        </div>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/5">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">2-Factor Auth</span>
                                <div className="w-8 h-4 bg-indigo-500/30 rounded-full relative p-0.5 cursor-pointer">
                                    <div className="w-3 h-3 bg-indigo-500 rounded-full shadow-[0_0_8px_rgba(99,102,241,0.6)] ml-auto" />
                                </div>
                            </div>
                            <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/5">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Auto-Purge Logs</span>
                                <div className="w-8 h-4 bg-slate-700 rounded-full relative p-0.5 cursor-pointer">
                                    <div className="w-3 h-3 bg-slate-500 rounded-full" />
                                </div>
                            </div>
                        </div>
                    </section>

                    <button 
                        type="submit"
                        disabled={saving}
                        className="w-full py-3.5 bg-indigo-600 text-white rounded-lg font-bold shadow-md hover:bg-indigo-700 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
                    >
                        {saving ? <RefreshCw className="animate-spin" size={18} /> : <Save size={18} />}
                        {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    
                    <button 
                        type="button"
                        onClick={fetchSettings}
                        className="w-full py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all"
                    >
                        RESET DEFAULTS
                    </button>
                </div>
            </form>
        </div>
    );
};

const PriceInput = ({ label, value, onChange }: any) => (
    <div className="space-y-2">
        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider pl-1">{label}</label>
        <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 font-bold text-slate-400 text-sm">₹</span>
            <input 
                type="number"
                step="0.01"
                value={value}
                onChange={(e) => onChange(parseFloat(e.target.value))}
                className="w-full pl-8 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-bold text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all tabular-nums"
            />
        </div>
    </div>
);

export default Settings;
