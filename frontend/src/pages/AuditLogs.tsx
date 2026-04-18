import React, { useState, useEffect } from 'react';
import { Shield, Clock, HardDrive, User, Info, Search, Filter, ChevronLeft, ChevronRight, Loader2, Activity } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { CustomSelect } from '../components/CustomSelect';

const AuditLogs: React.FC = () => {
    const [logs, setLogs] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(0);
    const [limit] = useState(10);
    const [moduleFilter, setModuleFilter] = useState('');

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const res = await whatsappApi.getAuditLogs({
                skip: page * limit,
                limit,
                module: moduleFilter || undefined
            });
            setLogs(res.items);
            setTotal(res.total);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLogs();
    }, [page, limit, moduleFilter]);

    const getModuleIcon = (module: string) => {
        switch (module.toUpperCase()) {
            case 'CAMPAIGNS': return <Activity size={14} className="text-indigo-500" />;
            case 'TEMPLATES': return <HardDrive size={14} className="text-amber-500" />;
            case 'SYSTEM': return <Shield size={14} className="text-emerald-500" />;
            default: return <Info size={14} className="text-slate-400" />;
        }
    };

    return (
        <div className="space-y-8 font-sans">
            <PageHeader 
                title="Audit Logs" 
                description="Monitor system actions and administrative changes" 
            />

            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/30">
                     <div className="flex items-center gap-4">
                        <div className="min-w-[180px]">
                            <CustomSelect
                                value={moduleFilter}
                                onChange={v => { setModuleFilter(v); setPage(0); }}
                                icon={<Filter size={14} />}
                                options={[
                                    { value: "", label: "All Modules" },
                                    { value: "CAMPAIGNS", label: "Campaigns" },
                                    { value: "TEMPLATES", label: "Templates" },
                                    { value: "SYSTEM", label: "System" },
                                    { value: "CONTACTS", label: "Contacts" },
                                ]}
                            />
                        </div>
                     </div>
                </div>

                <div className="h-[55vh] overflow-auto custom-scrollbar relative">
                    <table className="w-full text-left text-sm">
                        <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900 shadow-sm">
                            <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] whitespace-nowrap">
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">Timestamp</th>
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">Action</th>
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">Module</th>
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">User</th>
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">IP Address</th>
                                <th className="px-5 py-4 bg-white dark:bg-slate-900">Context Details</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {logs.map(log => (
                                <tr key={log.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group whitespace-nowrap font-bold">
                                    <td className="px-5 py-3 text-slate-900 dark:text-white tabular-nums">
                                        <div className="flex items-center gap-2 text-slate-500 text-sm whitespace-nowrap">
                                            <Clock size={12} />
                                            {new Date(log.timestamp).toLocaleString(undefined, {
                                                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                            })}
                                        </div>
                                    </td>
                                    <td className="px-5 py-3 text-sm">
                                        <span className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-[10px] font-black text-slate-700 dark:text-slate-300 tracking-tight">
                                            {log.action.replace(/_/g, ' ')}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-sm">
                                        <div className="flex items-center gap-2 text-[10px] font-black uppercase text-slate-500 tracking-wider">
                                            {getModuleIcon(log.module)}
                                            {log.module}
                                        </div>
                                    </td>
                                    <td className="px-5 py-3 text-sm">
                                        <div className="flex items-center gap-2">
                                            <div className="w-6 h-6 rounded-full bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                                                <User size={12} />
                                            </div>
                                            <span className="text-sm font-bold text-slate-900 dark:text-white">{log.username || 'System'}</span>
                                        </div>
                                    </td>
                                    <td className="px-5 py-3 text-[11px] text-slate-500 font-mono italic">
                                        {log.ip_address || '--'}
                                    </td>
                                    <td className="px-5 py-3">
                                        <div className="flex flex-wrap gap-1.5 whitespace-normal max-w-[300px]">
                                            {log.details && Object.entries(log.details).map(([key, val]) => (
                                                <span key={key} className="px-1.5 py-0.5 rounded border border-slate-100 dark:border-slate-800 text-[9px] text-slate-500 bg-slate-50 dark:bg-slate-800/50">
                                                    <span className="font-bold opacity-60 mr-1">{key}:</span>
                                                    {String(val)}
                                                </span>
                                            ))}
                                            {!log.details && <span className="text-slate-300 text-[10px] italic">No metadata</span>}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {loading && <div className="flex items-center justify-center py-24"><Loader2 className="animate-spin text-indigo-600" size={32} /></div>}
                    {!loading && logs.length === 0 && (
                        <div className="flex flex-col items-center justify-center py-24 text-slate-400 space-y-2">
                            <Shield size={40} className="mb-2 opacity-20" />
                            <p className="text-sm font-medium">No audit entries found</p>
                        </div>
                    )}
                </div>

                {total > 0 && (
                    <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/30 dark:bg-slate-800/10">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest pl-2">
                            Showing {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total} entries
                        </span>
                        <div className="flex gap-2">
                            <button 
                                onClick={() => setPage(p => Math.max(0, p - 1))} 
                                disabled={page === 0}
                                className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white dark:hover:bg-slate-800 transition-all shadow-sm"
                            >
                                <ChevronLeft size={16} />
                            </button>
                            <button 
                                onClick={() => setPage(p => p + 1)} 
                                disabled={(page + 1) * limit >= total}
                                className="p-2 border border-slate-200 dark:border-slate-700 rounded-lg disabled:opacity-20 hover:bg-white dark:hover:bg-slate-800 transition-all shadow-sm"
                            >
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AuditLogs;
