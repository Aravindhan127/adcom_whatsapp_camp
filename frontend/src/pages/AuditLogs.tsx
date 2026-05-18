import React, { useState, useEffect } from 'react';
import { Shield, Clock, HardDrive, User, Info, Search, Filter, ChevronLeft, ChevronRight, Loader2, Activity, Globe } from 'lucide-react';
import { whatsappApi } from '../services/whatsappApi';
import PageHeader from '../components/PageHeader';
import { CustomSelect } from '../components/CustomSelect';

const AuditLogs: React.FC = () => {
    const [logs, setLogs] = useState<any[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'audit' | 'service'>('audit');
    const [page, setPage] = useState(0);
    const [limit] = useState(15);
    const [moduleFilter, setModuleFilter] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedOrgId, setSelectedOrgId] = useState('');
    const [orgs, setOrgs] = useState<any[]>([]);

    const isSuperAdmin = localStorage.getItem('role') === 'super_admin' || localStorage.getItem('role') === 'superadmin';

    const fetchData = async () => {
        setLoading(true);
        try {
            const [logsRes, orgsRes] = await Promise.all([
                whatsappApi.getAuditLogs({
                    skip: page * limit,
                    limit,
                    module: activeTab === 'service' ? 'SERVICE' : (moduleFilter || undefined),
                    search: searchQuery || undefined,
                    organization_id: selectedOrgId || undefined
                }),
                isSuperAdmin ? whatsappApi.getOrganizations() : Promise.resolve([])
            ]);
            setLogs(logsRes.items);
            setTotal(logsRes.total);
            if (isSuperAdmin) setOrgs(orgsRes);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [page, limit, moduleFilter, searchQuery, selectedOrgId, activeTab]);

    const getModuleIcon = (module: string) => {
        switch (module.toUpperCase()) {
            case 'CAMPAIGNS': return <Activity size={14} className="text-indigo-500" />;
            case 'TEMPLATES': return <HardDrive size={14} className="text-amber-500" />;
            case 'SYSTEM': return <Shield size={14} className="text-emerald-500" />;
            case 'CONTACTS': return <User size={14} className="text-cyan-500" />;
            case 'SERVICE': return <Activity size={14} className="text-rose-500" />;
            default: return <Info size={14} className="text-slate-400" />;
        }
    };

    return (
        <div className="space-y-6 font-sans animate-in fade-in duration-500">
            <PageHeader 
                title={isSuperAdmin ? "System Intelligence Logs" : "Activity Logs"} 
                description={isSuperAdmin ? "Full forensic audit and service diagnostic logs for the entire platform" : "Monitor administrative changes and service events for your organization"} 
                actions={
                    <div className="flex gap-2">
                        <button 
                            onClick={() => fetchData()} 
                            className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-500 hover:text-indigo-500 transition-all shadow-sm"
                            title="Refresh Logs"
                        >
                            <Loader2 className={loading ? "animate-spin" : ""} size={18} />
                        </button>
                    </div>
                }
            />

            {/* TAB SYSTEM */}
            <div className="flex p-1 bg-slate-100 dark:bg-slate-800/50 rounded-2xl w-fit">
                <button
                    onClick={() => { setActiveTab('audit'); setPage(0); }}
                    className={`px-6 py-2.5 rounded-xl text-[11px] font-black uppercase tracking-widest transition-all ${activeTab === 'audit' ? 'bg-white dark:bg-slate-700 text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    Audit Trail
                </button>
                <button
                    onClick={() => { setActiveTab('service'); setPage(0); }}
                    className={`px-6 py-2.5 rounded-xl text-[11px] font-black uppercase tracking-widest transition-all ${activeTab === 'service' ? 'bg-white dark:bg-slate-700 text-rose-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                >
                    Service Diagnostics
                </button>
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
                <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-800/30">
                     <div className="flex flex-wrap items-center gap-4">
                        <div className="relative w-full md:w-64">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                            <input 
                                type="text"
                                placeholder={activeTab === 'service' ? "Search action or metadata..." : "Search user or action..."}
                                value={searchQuery}
                                onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
                                className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl text-[11px] font-bold focus:ring-2 focus:ring-indigo-500 transition-all outline-none"
                            />
                        </div>

                        {activeTab === 'audit' && (
                            <div className="min-w-[160px]">
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
                        )}

                        {isSuperAdmin && (
                            <div className="min-w-[180px]">
                                <CustomSelect
                                    value={selectedOrgId}
                                    onChange={v => { setSelectedOrgId(v); setPage(0); }}
                                    icon={<Globe size={14} />}
                                    options={[
                                        { value: "", label: "All Organizations" },
                                        ...orgs.map(o => ({ value: o.id, label: o.name }))
                                    ]}
                                />
                            </div>
                        )}
                     </div>
                     <div className="text-[10px] font-black uppercase text-slate-400 tracking-widest pl-2">
                        {total} Records Found
                     </div>
                </div>

                <div className="h-[55vh] overflow-auto custom-scrollbar relative">
                    <table className="w-full text-left text-sm border-separate border-spacing-0">
                        <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900 shadow-sm">
                            <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">
                                <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">Timestamp</th>
                                {isSuperAdmin && <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">Organization</th>}
                                <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">Action Event</th>
                                <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">Module</th>
                                <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">{activeTab === 'service' ? 'Identity' : 'Executed By'}</th>
                                <th className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">Payload / Context</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                            {logs.map(log => (
                                <tr key={log.id} className="hover:bg-indigo-50/30 dark:hover:bg-indigo-500/5 transition-all group whitespace-nowrap">
                                    <td className="px-6 py-3.5 text-[11px] font-bold text-slate-500 tabular-nums">
                                        {new Date(log.timestamp).toLocaleString(undefined, {
                                            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
                                        })}
                                    </td>
                                    {isSuperAdmin && (
                                        <td className="px-6 py-3.5">
                                            <div className="flex items-center gap-2">
                                                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                                                <span className="text-[11px] font-black uppercase text-slate-900 dark:text-white tracking-tighter">
                                                    {log.organization_name || 'System'}
                                                </span>
                                            </div>
                                        </td>
                                    )}
                                    <td className="px-6 py-3.5">
                                        <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[10px] font-black text-slate-700 dark:text-slate-300 tracking-tight">
                                            {log.action.replace(/_/g, ' ')}
                                        </span>
                                    </td>
                                    <td className="px-6 py-3.5">
                                        <div className="flex items-center gap-2 text-[10px] font-black uppercase text-slate-500 tracking-widest leading-none">
                                            {getModuleIcon(log.module)}
                                            {log.module}
                                        </div>
                                    </td>
                                    <td className="px-6 py-3.5">
                                        <div className="flex items-center gap-2">
                                            {activeTab === 'service' ? (
                                                <>
                                                    <div className="w-6 h-6 rounded-full bg-rose-500/10 flex items-center justify-center text-rose-600 font-black text-[10px]">
                                                        W
                                                    </div>
                                                    <span className="text-[11px] font-black text-rose-600 dark:text-rose-400 tracking-tighter">WEBHOOK / SYSTEM</span>
                                                </>
                                            ) : (
                                                <>
                                                    <div className="w-6 h-6 rounded-full bg-indigo-500/10 flex items-center justify-center text-indigo-600 font-black text-[10px]">
                                                        {log.username?.charAt(0).toUpperCase() || 'S'}
                                                    </div>
                                                    <span className="text-[11px] font-bold text-slate-900 dark:text-white">{log.username || 'System Account'}</span>
                                                </>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-6 py-3.5">
                                        <div className="flex flex-wrap gap-1.5 max-w-[280px]">
                                            {log.details && Object.entries(log.details).slice(0, 2).map(([key, val]) => (
                                                <span key={key} className="px-1.5 py-0.5 rounded-md border border-slate-100 dark:border-slate-800 text-[9px] font-bold text-slate-400 bg-slate-50 dark:bg-slate-800/30">
                                                    <span className="opacity-50 lowercase mr-1">{key}:</span>
                                                    <span className="text-slate-600 dark:text-slate-300">{String(val)}</span>
                                                </span>
                                            ))}
                                            {log.details && Object.keys(log.details).length > 2 && (
                                                <span className="text-[9px] font-black text-indigo-500 italic opacity-60">+{Object.keys(log.details).length - 2} more...</span>
                                            )}
                                            {!log.details && <span className="text-slate-300 text-[9px] italic">No parameters</span>}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {loading && (
                        <div className="absolute inset-0 bg-white/50 dark:bg-slate-900/50 backdrop-blur-[1px] flex flex-col items-center justify-center gap-4 z-20">
                            <Loader2 className="animate-spin text-indigo-600" size={32} />
                            <span className="text-[11px] font-black uppercase tracking-widest text-indigo-600/60 animate-pulse">Scanning audit history...</span>
                        </div>
                    )}
                    {!loading && logs.length === 0 && (
                        <div className="flex flex-col items-center justify-center py-32 text-slate-400 space-y-4">
                            <Shield size={64} className="opacity-10" />
                            <div className="text-center">
                                <p className="text-sm font-black uppercase tracking-widest">No entries found</p>
                                <p className="text-[10px] font-medium opacity-60 mt-1 italic">Try adjusting your filters or search query</p>
                            </div>
                        </div>
                    )}
                </div>

                {total > 0 && (
                    <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/30 dark:bg-slate-800/10">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">
                            Displaying {page * limit + 1} TO {Math.min((page + 1) * limit, total)} OF {total} LOGS
                        </span>
                        <div className="flex gap-3">
                            <button 
                                onClick={() => setPage(p => Math.max(0, p - 1))} 
                                disabled={page === 0}
                                className="px-4 py-2 border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl disabled:opacity-20 hover:border-indigo-500 transition-all shadow-sm flex items-center gap-1 text-[10px] font-black uppercase"
                            >
                                <ChevronLeft size={14} />
                                Previous
                            </button>
                            <button 
                                onClick={() => setPage(p => p + 1)} 
                                disabled={(page + 1) * limit >= total}
                                className="px-4 py-2 border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl disabled:opacity-20 hover:border-indigo-500 transition-all shadow-sm flex items-center gap-1 text-[10px] font-black uppercase"
                            >
                                Next
                                <ChevronRight size={14} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AuditLogs;
